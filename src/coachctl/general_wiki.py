"""
General Wiki — LLM-maintained, athlete-agnostic fitness knowledge layer.

Thin wrapper around `wiki_base` bound to `wiki/general/`. All paths are
validated to stay inside that directory; `raw/` is never touched.
"""

from __future__ import annotations

from pathlib import Path

from . import paths, wiki_base


def _base() -> Path:
    return paths.general_wiki_dir()


# ── Read ──────────────────────────────────────────────────────────────────────


def list_files() -> list[str]:
    """Return sorted list of relative paths for all .md files in wiki/general/."""
    base = _base()
    if not base.exists():
        return []
    return sorted(str(f.relative_to(base)) for f in base.rglob("*.md"))


def resolve_topic(topic: str) -> list[Path]:
    """Resolve a fuzzy topic string to one or more files in wiki/general/."""
    return wiki_base.resolve_topic(_base(), topic)


# ── Diff / Write ──────────────────────────────────────────────────────────────


def diff_general_section(rel_path: str, proposed_content: str) -> str:
    """Unified diff between the current general wiki file and proposed content."""
    target = wiki_base.safe_resolve(_base(), rel_path)
    return wiki_base.diff_file(target, proposed_content, label=target.name)


def write_general_section(rel_path: str, content: str) -> Path:
    """Write content to a general wiki file. Creates parent dirs as needed."""
    target = wiki_base.safe_resolve(_base(), rel_path)
    return wiki_base.write_file(target, content)


# ── Log ───────────────────────────────────────────────────────────────────────


def append_general_log(entry: str) -> Path:
    """Append a timestamped entry to wiki/general/log.md."""
    return wiki_base.append_log(
        _base() / "log.md",
        header="General Wiki Log",
        entry=entry,
    )
