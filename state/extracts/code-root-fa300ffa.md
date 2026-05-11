"""
Tests for coachctl.paths — data_root / personal_dir resolution.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import coachctl.paths as paths_module


@pytest.fixture(autouse=True)
def clear_cache():
    """Always clear the lru_cache before and after each test."""
    paths_module._resolve_data_root.cache_clear()
    yield
    paths_module._resolve_data_root.cache_clear()


# ── code_root ─────────────────────────────────────────────────────────────────


def test_code_root_is_path():
    assert isinstance(paths_module.code_root(), Path)


def test_code_root_contains_src():
    assert (paths_module.code_root() / "src").exists()


def test_root_alias_equals_code_root():
    assert paths_module.ROOT == paths_module.code_root()


# ── data_root via AGENT_DATA_ROOT ────────────────────────────────────────────


def test_data_root_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DATA_ROOT", str(tmp_path))
    monkeypatch.delenv("STRAVA_PROFILE", raising=False)
    assert paths_module.data_root() == tmp_path.resolve()


def test_data_root_env_expanduser(tmp_path, monkeypatch):
    """Tilde expansion should work."""
    monkeypatch.setenv("AGENT_DATA_ROOT", str(tmp_path))
    assert paths_module.data_root().is_absolute()


def test_data_root_raises_when_no_config(tmp_path, monkeypatch):
    """Without any resolution strategy, RuntimeError is raised."""
    monkeypatch.delenv("AGENT_DATA_ROOT", raising=False)
    monkeypatch.delenv("STRAVA_PROFILE", raising=False)
    # Ensure no sibling coachctl-personal exists by faking code_root
    monkeypatch.setattr(paths_module, "code_root", lambda: tmp_path)
    with pytest.raises(RuntimeError, match="No personal data root"):
        paths_module.data_root()


# ── data_root via sibling directory ───────────────────────────────────────────


def test_data_root_sibling_discovery(tmp_path, monkeypatch):
    """Sibling coachctl-personal with profile/ dir is auto-discovered."""
    monkeypatch.delenv("AGENT_DATA_ROOT", raising=False)
    monkeypatch.delenv("STRAVA_PROFILE", raising=False)

    # Create fake coachctl-personal sibling
    sibling = tmp_path / "coachctl-personal"
    (sibling / "profile").mkdir(parents=True)

    # Make code_root() point to a child of tmp_path so sibling resolves
    fake_code = tmp_path / "coachctl"
    fake_code.mkdir()
    monkeypatch.setattr(paths_module, "code_root", lambda: fake_code)

    assert paths_module.data_root() == sibling.resolve()


# ── get_profile ───────────────────────────────────────────────────────────────


def test_get_profile_empty(monkeypatch):
    monkeypatch.delenv("STRAVA_PROFILE", raising=False)
    assert paths_module.get_profile() == ""


def test_get_profile_set(monkeypatch):
    monkeypatch.setenv("STRAVA_PROFILE", "alice")
    assert paths_module.get_profile() == "alice"


# ── Derived paths ─────────────────────────────────────────────────────────────


def test_personal_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DATA_ROOT", str(tmp_path))
    assert paths_module.personal_dir() == tmp_path.resolve() / "profile"


def test_plans_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DATA_ROOT", str(tmp_path))
    assert paths_module.plans_dir() == tmp_path.resolve() / "profile" / "plans"


def test_feedback_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DATA_ROOT", str(tmp_path))
    assert paths_module.feedback_dir() == tmp_path.resolve() / "profile" / "feedback"


def test_athlete_yaml(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DATA_ROOT", str(tmp_path))
    assert paths_module.athlete_yaml() == tmp_path.resolve() / "profile" / "athlete.yaml"


def test_db_path(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DATA_ROOT", str(tmp_path))
    assert paths_module.db_path() == tmp_path.resolve() / "data" / "activities.db"


def test_data_json(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DATA_ROOT", str(tmp_path))
    assert paths_module.data_json() == tmp_path.resolve() / "deploy" / "dist" / "data.json"


def test_dist_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DATA_ROOT", str(tmp_path))
    assert paths_module.dist_dir() == tmp_path.resolve() / "deploy" / "dist"


def test_env_file(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DATA_ROOT", str(tmp_path))
    assert paths_module.env_file() == tmp_path.resolve() / ".env"


def test_raw_personal_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DATA_ROOT", str(tmp_path))
    assert paths_module.raw_personal_dir() == tmp_path.resolve() / "raw"


def test_general_wiki_dir():
    d = paths_module.general_wiki_dir()
    assert d == paths_module.code_root() / "wiki"


def test_raw_general_dir():
    d = paths_module.raw_general_dir()
    assert d == paths_module.code_root() / "raw"


# ── ensure_profile_dirs ───────────────────────────────────────────────────────


def test_ensure_profile_dirs_creates_dirs(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DATA_ROOT", str(tmp_path))
    paths_module.ensure_profile_dirs()
    assert paths_module.personal_dir().exists()
    assert paths_module.plans_dir().exists()
    assert paths_module.feedback_dir().exists()


def test_ensure_profile_dirs_no_error_when_no_root(tmp_path, monkeypatch):
    """Should silently return when no data root is configured."""
    monkeypatch.delenv("AGENT_DATA_ROOT", raising=False)
    monkeypatch.delenv("STRAVA_PROFILE", raising=False)
    monkeypatch.setattr(paths_module, "code_root", lambda: tmp_path)
    # Must not raise
    paths_module.ensure_profile_dirs()
