"""
Central path resolver — splits public code paths from private personal data.

Two roots:

* ``code_root()``      — the public coachctl checkout (this package's repo).
                          Hosts general knowledge: ``wiki/``, ``raw/``,
                          dashboard UI source, code templates.

* ``data_root()``      — the private per-athlete data repo (e.g.
                          ``coachctl-personal``). Hosts ``profile/`` (was
                          ``wiki/personal/<profile>/``), ``data/activities.db``,
                          ``deploy/dist/data.json`` (baked dashboard payload),
                          ``raw/`` (personal source documents), and ``.env``.

Resolution order for ``data_root()``:

1. ``AGENT_DATA_ROOT`` environment variable (absolute path).
2. Sibling directory ``../coachctl-personal`` next to the code repo.
3. Legacy fallback: ``<code_root>/wiki/personal/<STRAVA_PROFILE>`` — emits a
   :class:`DeprecationWarning` and synthesises a virtual data root that maps the
   old layout (``wiki/personal/<profile>``, ``data/profiles/<profile>``,
   ``config/profiles/<profile>``) to the new function names.

``STRAVA_PROFILE`` is now optional. Personal repos are implicitly single-athlete;
the env var only acts as a label when set, and as a disambiguator for the legacy
fallback.
"""

from __future__ import annotations

import os
import warnings
from functools import lru_cache
from pathlib import Path

# ── Code repo ────────────────────────────────────────────────────────────────


def code_root() -> Path:
    """Public coachctl checkout root (two levels above this file)."""
    return Path(__file__).parent.parent.parent


# Back-compat alias — some modules import paths.ROOT directly.
ROOT = code_root()


# ── Data root resolver ───────────────────────────────────────────────────────


class _LegacyRoot:
    """Marker for the legacy ``wiki/personal/<profile>`` layout."""

    __slots__ = ("profile",)

    def __init__(self, profile: str) -> None:
        self.profile = profile


@lru_cache(maxsize=1)
def _resolve_data_root() -> Path | _LegacyRoot:
    env = os.getenv("AGENT_DATA_ROOT", "").strip()
    if env:
        return Path(env).expanduser().resolve()

    sibling = code_root().parent / "coachctl-personal"
    if sibling.exists() and (sibling / "profile").exists():
        return sibling.resolve()

    profile = os.getenv("STRAVA_PROFILE", "").strip()
    if profile:
        legacy = code_root() / "wiki" / "personal" / profile
        if legacy.exists():
            warnings.warn(
                "Using legacy wiki/personal/<profile> layout. "
                "Migrate to a sibling coachctl-personal repo and set AGENT_DATA_ROOT.",
                DeprecationWarning,
                stacklevel=3,
            )
            return _LegacyRoot(profile)

    raise RuntimeError(
        "No personal data root found. Either:\n"
        "  • set AGENT_DATA_ROOT to your private personal-repo checkout, or\n"
        "  • clone coachctl-personal as a sibling of this code repo, or\n"
        "  • set STRAVA_PROFILE and keep a legacy wiki/personal/<profile>/ tree."
    )


def data_root() -> Path:
    """Resolved root of the private personal-data repo (raises if unset)."""
    r = _resolve_data_root()
    if isinstance(r, _LegacyRoot):
        return code_root()
    return r


def get_profile() -> str:
    """Active profile label, or '' if unset.

    Personal repos are single-athlete; this is informational only.
    """
    return os.getenv("STRAVA_PROFILE", "").strip()


# ── Personal (private) ───────────────────────────────────────────────────────


def personal_dir() -> Path:
    """``<DATA_ROOT>/profile/`` — the athlete's wiki root."""
    r = _resolve_data_root()
    if isinstance(r, _LegacyRoot):
        return code_root() / "wiki" / "personal" / r.profile
    return r / "profile"


def plans_dir() -> Path:
    return personal_dir() / "plans"


def feedback_dir() -> Path:
    return personal_dir() / "feedback"


def athlete_yaml() -> Path:
    return personal_dir() / "athlete.yaml"


def env_file() -> Path:
    """``<DATA_ROOT>/.env`` — Strava + Google OAuth secrets (git-ignored)."""
    r = _resolve_data_root()
    if isinstance(r, _LegacyRoot):
        return code_root() / "config" / "profiles" / r.profile / ".env"
    return r / ".env"


def db_path() -> Path:
    """``<DATA_ROOT>/data/activities.db``."""
    r = _resolve_data_root()
    if isinstance(r, _LegacyRoot):
        return code_root() / "data" / "profiles" / r.profile / "activities.db"
    return r / "data" / "activities.db"


def data_json() -> Path:
    """``<DATA_ROOT>/deploy/dist/data.json`` — baked dashboard payload.

    Lives inside ``deploy/`` (the Vercel project root) so the artifact is
    bundled into the serverless function alongside ``web.py``. The legacy
    fallback keeps the historical location under ``wiki/personal/<profile>/``
    for back-compat.
    """
    r = _resolve_data_root()
    if isinstance(r, _LegacyRoot):
        return code_root() / "wiki" / "personal" / r.profile / "data.json"
    return r / "deploy" / "dist" / "data.json"


def dist_dir() -> Path:
    """``<DATA_ROOT>/deploy/dist/`` — generated build artifacts (data.json, etc.)."""
    r = _resolve_data_root()
    if isinstance(r, _LegacyRoot):
        return code_root() / "wiki" / "personal" / r.profile
    return r / "deploy" / "dist"


def raw_personal_dir() -> Path:
    """``<DATA_ROOT>/raw/`` — personal source documents (GPX, photos, scans)."""
    r = _resolve_data_root()
    if isinstance(r, _LegacyRoot):
        return code_root() / "raw"
    return r / "raw"


# ── General (public) ─────────────────────────────────────────────────────────


def general_wiki_dir() -> Path:
    """LLM-maintained, athlete-agnostic knowledge.

    Resolves to ``<DATA_ROOT>/wiki/`` when it exists (personal repo — preferred),
    otherwise falls back to ``<CODE_ROOT>/wiki/`` for CI or fresh clones without
    a personal repo configured.
    """
    try:
        personal_wiki = data_root() / "wiki"
        if personal_wiki.exists():
            return personal_wiki
    except RuntimeError:
        pass
    return code_root() / "wiki"


def raw_general_dir() -> Path:
    """``<CODE_ROOT>/raw/`` — public source documents."""
    return code_root() / "raw"


# ── Bootstrap ────────────────────────────────────────────────────────────────


def ensure_profile_dirs() -> None:
    """Create all required directories on first run.

    Skips silently if no data root is configured (e.g. CI / lint runs).
    """
    try:
        _resolve_data_root()
    except RuntimeError:
        return

    personal_dir().mkdir(parents=True, exist_ok=True)
    plans_dir().mkdir(parents=True, exist_ok=True)
    feedback_dir().mkdir(parents=True, exist_ok=True)
    dist_dir().mkdir(parents=True, exist_ok=True)
    general_wiki_dir().mkdir(parents=True, exist_ok=True)
    raw_general_dir().mkdir(parents=True, exist_ok=True)
    raw_personal_dir().mkdir(parents=True, exist_ok=True)
    db_path().parent.mkdir(parents=True, exist_ok=True)
    env_file().parent.mkdir(parents=True, exist_ok=True)
