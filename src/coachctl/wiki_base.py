"""
Wiki base — shared diff/write/log/safe-resolve helpers.

Both `wiki.py` (personal) and `general_wiki.py` (general) wrap this module
with their own base directory. All path resolution is hardened against
traversal escapes.
"""

from __future__ import annotations

import datetime
import difflib
from pathlib import Path


def safe_resolve(base: Path, rel_path: str) -> Path:
    """
    Resolve `rel_path` to an absolute path inside `base`.

    - Strips leading slashes / `./` to keep the path relative.
    - Auto-appends `.md` if no suffix is present.
    - Raises ValueError if the resolved path escapes `base`.
    """
    base_resolved = base.resolve()
    clean = rel_path.lstrip("/\\")
    while clean.startswith("./"):
        clean = clean[2:]
    candidate = (base_resolved / clean).resolve()
    try:
        candidate.relative_to(base_resolved)
    except ValueError as exc:
        raise ValueError(
            f"Path '{rel_path}' resolves outside {base_resolved} — refusing to write."
        ) from exc
    if not candidate.suffix:
        candidate = candidate.with_suffix(".md")
    return candidate


def diff_file(target: Path, proposed_content: str, label: str | None = None) -> str:
    """Unified diff between `target` (current on disk) and `proposed_content`."""
    if target.exists():
        current_lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
    else:
        current_lines = []

    proposed_lines = proposed_content.splitlines(keepends=True)
    if proposed_lines and not proposed_lines[-1].endswith("\n"):
        proposed_lines[-1] += "\n"
    if current_lines and not current_lines[-1].endswith("\n"):
        current_lines[-1] += "\n"

    name = label or target.name
    diff = difflib.unified_diff(
        current_lines,
        proposed_lines,
        fromfile=f"{name} (current)",
        tofile=f"{name} (proposed)",
        lineterm="",
    )
    diff_text = "\n".join(diff)
    return diff_text if diff_text.strip() else "(no changes)"


def write_file(target: Path, content: str) -> Path:
    """Write `content` to `target`. Creates parent dirs."""
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def append_text(target: Path, block: str) -> Path:
    """Append `block` to `target`, ensuring trailing newline. Creates the file."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_text("", encoding="utf-8")
    with open(target, "a", encoding="utf-8") as f:
        f.write(block if block.endswith("\n") else block + "\n")
    return target


def append_log(log_path: Path, header: str, entry: str) -> Path:
    """
    Append a timestamped entry to `log_path`. Creates the file with `header`
    as the markdown title if absent.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    line = f"\n- **{ts}** — {entry.strip()}\n"
    if not log_path.exists():
        log_path.write_text(
            f"# {header}\n\n*Append-only record.*\n",
            encoding="utf-8",
        )
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line)
    return log_path


def resolve_topic(base: Path, topic: str) -> list[Path]:
    """
    Resolve a fuzzy `topic` string to one or more `.md` files inside `base`.

    Resolution order:
      1. Exact path match (with or without `.md` suffix).
      2. Substring match against stem and relative path of every `.md`.

    Returns a list (possibly empty). Path-traversal safe.
    """
    if not topic:
        return []
    try:
        target = safe_resolve(base, topic)
    except ValueError:
        return []
    if target.is_file():
        return [target]
    # Substring fallback
    if not base.exists():
        return []
    needle = topic.lower()
    matches = [
        p
        for p in base.rglob("*.md")
        if needle in p.stem.lower() or needle in str(p.relative_to(base)).lower()
    ]
    return sorted(matches)
