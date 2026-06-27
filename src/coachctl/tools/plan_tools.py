"""Training plan tools: save, retrieve, and override plan sessions."""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

from .. import paths
from ..db import get_conn
from ..wiki import build_plans_index_content, diff_section

logger = logging.getLogger(__name__)


def _insert_plan_and_events(
    plan_path: Path, slug: str, event_name: str, event_date: str
) -> int | None:
    """Parse a saved plan, insert a plans row, and upsert training events for each dated session."""
    try:
        from ..plan_parser import (
            detect_session_sport,
            parse_plan_file,
            parse_session_duration_intensity,
        )
        from ..metrics import estimate_session_tss
        from ..events import Event, KIND_TRAINING, STATUS_PLANNED, upsert_event
    except Exception:
        return None

    try:
        plan = parse_plan_file(plan_path)
    except Exception as e:
        logger.warning("Could not parse plan for events insertion: %s", e)
        return None

    # Insert/update plans table row
    plan_slug = f"{plan_path.stem}"
    now = date.today().isoformat()
    with get_conn() as conn:
        # Deactivate other plans
        conn.execute("UPDATE plans SET active = 0 WHERE active = 1")
        # Find start/end dates from sessions
        dates = sorted(s.date for w in plan.weeks for s in w.sessions if s.date)
        start_date = dates[0] if dates else now
        end_date = dates[-1] if dates else None
        conn.execute(
            """
            INSERT INTO plans (slug, title, start_date, end_date, active, overview_md, source_md_path)
            VALUES (?, ?, ?, ?, 1, ?, ?)
            ON CONFLICT(slug) DO UPDATE SET
                title = excluded.title, start_date = excluded.start_date,
                end_date = excluded.end_date, active = 1,
                overview_md = excluded.overview_md, source_md_path = excluded.source_md_path
            """,
            (plan_slug, plan.title or event_name, start_date, end_date, plan.title, plan_path.name),
        )
        row = conn.execute("SELECT id FROM plans WHERE slug = ?", (plan_slug,)).fetchone()
        plan_id = row["id"] if row else None

    if not plan_id:
        return None

    # Build week_tss_json mapping: week_number → target_tss
    week_tss = {w.number: w.target_tss for w in plan.weeks if w.target_tss}
    if week_tss:
        with get_conn() as conn:
            conn.execute(
                "UPDATE plans SET week_tss_json = ? WHERE id = ?",
                (json.dumps(week_tss), plan_id),
            )

    # Insert training events for each dated session
    inserted = 0
    for w in plan.weeks:
        for s in w.sessions:
            if not s.date:
                continue
            # Skip rest days
            if "rest" in (s.name or "").lower():
                continue

            # Estimate TSS from duration + intensity in the details string,
            # using the sport-specific IF table (run vs ride differ markedly at
            # easy/endurance intensities).
            estimated_tss: float | None = None
            details_text = s.details or ""
            duration_min, intensity = parse_session_duration_intensity(details_text)
            if duration_min is not None and intensity is not None:
                sport = detect_session_sport(f"{s.name or ''} {details_text}")
                try:
                    estimated_tss = estimate_session_tss(
                        duration_min, intensity, sport=sport
                    )["tss_estimate"]
                except Exception:
                    pass

            ev_slug = f"plan-{plan_slug}-{s.date}"
            ev = Event(
                slug=ev_slug,
                kind=KIND_TRAINING,
                date=s.date,
                name=s.name,
                summary=s.details[:120] if s.details else None,
                status=STATUS_PLANNED,
                payload={
                    "details": s.details,
                    "week_number": w.number,
                    "phase": w.phase,
                },
                plan_id=plan_id,
                estimated_tss=estimated_tss,
            )
            upsert_event(ev)
            inserted += 1

    logger.info("Plan '%s': inserted %d training events (plan_id=%d)", plan_slug, inserted, plan_id)
    return plan_id


def backfill_event_tss(recompute: bool = False) -> dict:
    """Backfill ``estimated_tss`` for training events from their text.

    Reads ``summary`` / ``payload_json`` details from the events table,
    re-parses duration + intensity, detects sport, and writes the sport-aware
    TSS estimate in place.

    Parameters
    ----------
    recompute : if False (default) only fills events whose ``estimated_tss`` is
        NULL. If True, recomputes ALL training events — use this after changing
        the IF model to correct previously-stored estimates.

    Returns a summary dict: {updated, skipped_no_duration, already_set}.
    """
    from ..plan_parser import resolve_sport, parse_session_duration_intensity
    from ..metrics import estimate_session_tss

    updated = 0
    skipped = 0
    already_set = 0

    with get_conn() as conn:
        # LEFT JOIN the linked activity so we can use Strava's authoritative
        # sport_type when the planned event has been fulfilled.
        base = (
            "SELECT e.id AS id, e.name AS name, e.summary AS summary, "
            "e.payload_json AS payload_json, a.sport_type AS strava_sport "
            "FROM events e LEFT JOIN activities a ON a.id = e.activity_id "
            "WHERE e.kind = 'training'"
        )
        if recompute:
            # Never recompute completed/linked events: their estimate is the
            # planned baseline and their summary text may have drifted from the
            # real session. Recomputing from stale text would corrupt good values.
            rows = conn.execute(
                base + " AND e.status != 'completed' AND e.activity_id IS NULL"
            ).fetchall()
        else:
            rows = conn.execute(base + " AND e.estimated_tss IS NULL").fetchall()

        for row in rows:
            # Prefer full details from payload_json, fall back to summary.
            details = ""
            payload_sport = ""
            if row["payload_json"]:
                try:
                    payload = json.loads(row["payload_json"])
                    details = payload.get("details", "") or ""
                    # Deterministic-engine events carry an explicit sport.
                    workout = payload.get("workout")
                    if isinstance(workout, dict):
                        payload_sport = (workout.get("sport") or "").strip()
                except Exception:
                    pass
            if not details and row["summary"]:
                details = row["summary"]

            duration_min, intensity = parse_session_duration_intensity(details)
            if duration_min is None or intensity is None:
                skipped += 1
                continue

            # Resolve sport best-first: linked Strava activity (authoritative)
            # → structured engine payload → free-text keyword heuristic.
            sport = resolve_sport(
                strava_sport_type=row["strava_sport"],
                structured_sport=payload_sport,
                text=f"{row['name'] or ''} {details}",
            )

            try:
                tss = estimate_session_tss(duration_min, intensity, sport=sport)[
                    "tss_estimate"
                ]
                conn.execute(
                    "UPDATE events SET estimated_tss = ? WHERE id = ?",
                    (tss, row["id"]),
                )
                updated += 1
            except Exception:
                skipped += 1

    return {"updated": updated, "skipped_no_duration": skipped, "already_set": already_set}


def register(mcp) -> None:  # noqa: ANN001

    @mcp.tool()
    def save_plan(plan_markdown: str, event_name: str = "", event_date: str = "") -> str:
        """
        Persist a generated training plan as a Markdown file in plans/.
        Also inserts a row in the ``plans`` table and creates ``training``
        events in the events table for each dated session.
        plan_markdown: the full plan text (must be non-empty)
        event_name: optional target event
        event_date: optional event date (YYYY-MM-DD)
        """
        if not plan_markdown or not plan_markdown.strip():
            return "Error: plan_markdown is empty — refusing to write."

        paths.plans_dir().mkdir(parents=True, exist_ok=True)
        # Sanitise event_name before embedding in a filename: strip path separators and
        # limit length so the result is always a safe basename under plans/.
        import re as _re

        safe_name = _re.sub(r"[^\w\s\-]", "", event_name).strip() if event_name else ""
        slug = safe_name.lower().replace(" ", "-")[:30] if safe_name else "plan"
        filename = f"{date.today().isoformat()}_{slug}.md"
        if not filename.endswith(".md"):
            filename += ".md"
        plan_path = paths.plans_dir() / filename
        plan_path.write_text(plan_markdown, encoding="utf-8")

        # Parse plan and insert into events table
        plan_row_id = _insert_plan_and_events(plan_path, slug, event_name, event_date)

        new_index = build_plans_index_content()
        index_diff = diff_section("plans_index.md", new_index)

        result = f"Plan saved: {plan_path.name}"
        if plan_row_id:
            result += f" (plan_id={plan_row_id}, sessions inserted into events table)"
        if index_diff != "(no changes)":
            result += (
                "\n\nProposed update to plans_index.md:\n"
                f"```diff\n{index_diff}\n```\n"
                "Call apply_wiki_update('plans_index.md', ...) to apply."
            )
        return result

    @mcp.tool()
    def get_previous_plans(n: int = 5) -> str:
        """Get the N most recent training plans from the plans/ directory."""
        plans_dir = paths.plans_dir()
        if not plans_dir.exists():
            return "No plans directory found."

        plan_files = sorted(plans_dir.glob("*.md"), reverse=True)[:n]
        if not plan_files:
            return "No plans found."

        results = []
        for p in plan_files:
            lines = p.read_text(encoding="utf-8").splitlines()
            preview = " ".join(lines[:5]).strip()[:300]
            results.append(
                {
                    "filename": p.name,
                    "modified": p.stat().st_mtime,
                    "preview": preview,
                }
            )

        return json.dumps(results, indent=2, default=str)
