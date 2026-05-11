"""
Athlete Wiki — persistent markdown-based knowledge layer.

Provides structured, human-readable, git-tracked files that give the LLM
rich context about the athlete across sessions. All files live under
``<DATA_ROOT>/profile/`` (see ``paths.personal_dir``).

Diff/write/log/safe-resolve mechanics live in ``wiki_base``; this module
binds them to the personal directory and owns the seed-from-database flow.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import date
from pathlib import Path

from . import paths, wiki_base
from .config import load_athlete

# The canonical set of wiki files and their purpose. Single source of truth.
WIKI_FILES = [
    "profile.md",
    "goals.md",
    "training_history.md",
    "plans_index.md",
    "readiness.md",
    "nutrition.md",
]
VALID_SECTIONS = frozenset(WIKI_FILES)

# Files that are append-only (LLM never rewrites, only appends with timestamp).
APPEND_ONLY_FILES = {"log.md"}


def _resolve(filename: str) -> Path:
    """Resolve a wiki filename inside the personal dir (path-traversal safe)."""
    return wiki_base.safe_resolve(paths.personal_dir(), filename)


# ── Read ──────────────────────────────────────────────────────────────────────


def read_wiki() -> dict[str, str]:
    """Return {filename: content} for every wiki file that exists."""
    wdir = paths.personal_dir()
    result: dict[str, str] = {}
    for name in WIKI_FILES:
        p = wdir / name
        if p.exists():
            result[name] = p.read_text(encoding="utf-8")
    return result


def read_wiki_combined() -> str:
    """All wiki files concatenated with clear section headers."""
    sections = read_wiki()
    if not sections:
        return "(Wiki is empty — no files found.)"

    parts: list[str] = []
    for name in WIKI_FILES:
        if name in sections:
            parts.append(f"═══ {name} ═══\n{sections[name]}")
    return "\n\n".join(parts)


# ── Diff / Write ──────────────────────────────────────────────────────────────


def diff_section(filename: str, proposed_content: str) -> str:
    """Unified diff between current wiki file and proposed content."""
    return wiki_base.diff_file(_resolve(filename), proposed_content, label=filename)


def write_section(filename: str, content: str) -> Path:
    """Write content to a wiki file. Returns the path written."""
    return wiki_base.write_file(_resolve(filename), content)


def append_section(filename: str, block: str) -> Path:
    """Append a text block to a wiki file. Creates the file if absent."""
    return wiki_base.append_text(_resolve(filename), block)


def append_log(entry: str) -> Path:
    """Append a timestamped entry to ``<DATA_ROOT>/profile/log.md``."""
    return wiki_base.append_log(
        paths.personal_dir() / "log.md",
        header="Wiki Log",
        entry=entry,
    )


# ── Seed ──────────────────────────────────────────────────────────────────────


def is_seeded() -> bool:
    """True if at least one wiki file already exists."""
    wdir = paths.personal_dir()
    return any((wdir / name).exists() for name in WIKI_FILES)


def seed_wiki(conn: sqlite3.Connection) -> list[str]:
    """
    Populate the wiki from existing data sources.
    Returns list of files created.  Skips files that already exist.
    """
    wdir = paths.personal_dir()
    wdir.mkdir(parents=True, exist_ok=True)
    created: list[str] = []

    # profile.md
    if not (wdir / "profile.md").exists():
        content = _seed_profile()
        if content:
            write_section("profile.md", content)
            created.append("profile.md")

    # goals.md
    if not (wdir / "goals.md").exists():
        content = _seed_goals()
        if content:
            write_section("goals.md", content)
            created.append("goals.md")

    # training_history.md
    if not (wdir / "training_history.md").exists():
        content = _seed_training_history(conn)
        if content:
            write_section("training_history.md", content)
            created.append("training_history.md")

    # plans_index.md
    if not (wdir / "plans_index.md").exists():
        content = _seed_plans_index()
        if content:
            write_section("plans_index.md", content)
            created.append("plans_index.md")

    # readiness.md
    # Seeded as a template; live Coros data is written by the coach via
    # apply_wiki_update after calling get_readiness() / get_merged_fitness_state().
    # seed_wiki() is intentionally sync and does not call the Coros MCP.
    if not (wdir / "readiness.md").exists():
        rc = _seed_readiness()
        write_section("readiness.md", rc)
        created.append("readiness.md")

    return created


def _seed_profile() -> str:
    """Generate profile.md from athlete.yaml."""
    a = load_athlete()
    if not a:
        return ""

    lines = ["# Athlete Profile\n"]

    # Thresholds
    lines.append("## Thresholds & Physiology\n")
    if a.get("ftp"):
        lines.append(f"- **FTP**: {a['ftp']}W")
    if a.get("rftp"):
        mins, secs = divmod(a["rftp"], 60)
        lines.append(f"- **rFTP**: {a['rftp']}s/km ({mins}'{secs:02d}\"/km)")
    if a.get("threshold_hr"):
        lines.append(f"- **Threshold HR**: {a['threshold_hr']} bpm")
    if a.get("max_hr"):
        lines.append(f"- **Max HR**: {a['max_hr']} bpm")
    if a.get("resting_hr"):
        lines.append(f"- **Resting HR**: {a['resting_hr']} bpm")
    if a.get("weight_kg"):
        lines.append(f"- **Weight**: {a['weight_kg']} kg")
        if a.get("ftp"):
            wkg = round(a["ftp"] / a["weight_kg"], 2)
            lines.append(f"- **W/kg**: {wkg}")
    lines.append("")

    # Performance estimates — manually maintained by coach
    lines.append("## Performance Estimates\n")
    lines.append("<!-- Manually maintained — update when testing or athlete.yaml changes -->")
    lines.append("- **Last updated**: *(not yet populated)*")
    lines.append("- **VO2max**: —  ml/kg/min  *(estimated from running performance)*")
    lines.append("- **LTHR**: —  bpm  |  **LTSP**: —  s/km")
    lines.append("- **HRV**: not tracked  |  **Resting HR (typical)**: —  bpm")
    lines.append("")

    # Notes / preferences
    notes = a.get("athlete_notes", [])
    if notes:
        lines.append("## Notes & Preferences\n")
        for n in notes:
            lines.append(f"- {n}")
        lines.append("")

    return "\n".join(lines) + "\n"


def _seed_goals() -> str:
    """Generate goals.md from athlete.yaml events + goals."""
    a = load_athlete()
    if not a:
        return ""

    lines = ["# Goals\n"]

    # Events
    events = a.get("events", [])
    if events:
        lines.append("## Target Events\n")
        for e in events:
            pri = e.get("priority", "?")
            name = e.get("name", "Unnamed")
            dt = e.get("date", "TBD")
            goal = e.get("goal_time", "")
            pace = e.get("goal_pace_per_km", "")
            notes = e.get("notes", "")
            line = f"- **{pri} race**: {name} — {dt}"
            if goal:
                line += f" (goal: {goal})"
            if pace:
                line += f" @ {pace}/km"
            lines.append(line)
            if notes:
                lines.append(f"  - {notes}")
        lines.append("")

    # Goals by sport
    goals = a.get("goals", {})
    if goals:
        lines.append("## Sport Goals\n")
        for sport, items in goals.items():
            lines.append(f"### {sport.title()}\n")
            for g in items:
                lines.append(f"- {g}")
            lines.append("")

    # Past goals — omit placeholder table; populated by coach as races complete
    lines.append("## Past Goals\n")
    lines.append("*(Populated by coach as races complete.)*")
    lines.append("")

    return "\n".join(lines) + "\n"


def _seed_training_history(conn: sqlite3.Connection) -> str:
    """Generate training_history.md from coaching_notes in SQLite."""
    lines = ["# Training History\n"]

    rows = conn.execute(
        """
        SELECT session_date, category, tags, note
        FROM coaching_notes
        ORDER BY session_date ASC, id ASC
        """
    ).fetchall()

    if rows:
        lines.append("## Coaching Notes (imported from database)\n")
        current_date = None
        for row in rows:
            d = row["session_date"] if hasattr(row, "keys") else row[0]
            cat = row["category"] if hasattr(row, "keys") else row[1]
            tags = row["tags"] if hasattr(row, "keys") else row[2]
            note = row["note"] if hasattr(row, "keys") else row[3]

            if d != current_date:
                lines.append(f"\n### {d}\n")
                current_date = d

            tag_str = f" `[{tags}]`" if tags else ""
            lines.append(f"**{cat}**{tag_str}:\n{note}\n")
    else:
        lines.append(
            "*(No coaching notes found — history will be added as sessions are reviewed.)*\n"
        )

    # Injury log placeholder
    lines.append("\n## Injury Log\n")
    lines.append("| Date | Issue | Duration | Notes |")
    lines.append("|------|-------|----------|-------|")
    lines.append("| *(none recorded)* | | | |")
    lines.append("")

    return "\n".join(lines) + "\n"


def _seed_plans_index() -> str:
    """Generate plans_index.md by scanning the plans/ directory."""
    lines = ["# Training Plans Index\n"]
    lines.append("| Date | File | Title | Outcome |")
    lines.append("|------|------|-------|---------|")

    plans_dir = paths.plans_dir()
    if plans_dir.exists():
        plan_files = sorted(plans_dir.glob("*.md"))
        for pf in plan_files:
            # Extract date from filename (YYYY-MM-DD_slug.md)
            date_match = re.match(r"(\d{4}-\d{2}-\d{2})", pf.name)
            plan_date = date_match.group(1) if date_match else "?"

            # Extract first H1 title from file
            title = pf.name
            try:
                text = pf.read_text(encoding="utf-8")
                for line in text.splitlines():
                    if line.startswith("# "):
                        title = line[2:].strip()
                        break
            except Exception:
                pass

            lines.append(f"| {plan_date} | {pf.name} | {title} | In progress |")

    if not plans_dir.exists() or not list(plans_dir.glob("*.md")):
        lines.append("| *(no plans yet)* | | | |")

    lines.append("")
    return "\n".join(lines) + "\n"


def build_plans_index_content() -> str:
    """Rebuild plans_index.md content from current plans/ directory."""
    return _seed_plans_index()


def _seed_readiness() -> str:
    """
    Generate the initial readiness.md template.

    Uses a subjective check-in format (sleep/energy/soreness 1-5).
    Populated by the coach agent via log_readiness_checkin() before hard sessions.
    """
    today = date.today().isoformat()
    lines = [
        "# Athlete Readiness",
        "",
        f"*Subjective check-in log. Updated before hard sessions via `log_readiness_checkin()`.*",
        "",
        "## Check-in Log",
        "",
        "<!-- One row per check-in, most-recent first. -->",
        "<!-- Scores: 1=very poor / 5=excellent -->",
        "| Date | Sleep (1-5) | Energy (1-5) | Soreness (1-5) | Notes |",
        "|------|------------|--------------|----------------|-------|",
        f"| *(no check-ins yet)* | | | | |",
        "",
    ]
    return "\n".join(lines) + "\n"
