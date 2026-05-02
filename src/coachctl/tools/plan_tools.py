"""Training plan tools: save, retrieve, and override plan sessions."""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
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
        from ..plan_parser import parse_plan_file
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

    # Insert training events for each dated session
    inserted = 0
    for w in plan.weeks:
        for s in w.sessions:
            if not s.date:
                continue
            # Skip rest days
            if "rest" in (s.name or "").lower():
                continue
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
            )
            upsert_event(ev)
            inserted += 1

    logger.info("Plan '%s': inserted %d training events (plan_id=%d)", plan_slug, inserted, plan_id)
    return plan_id


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
        slug = event_name.lower().replace(" ", "-").replace(":", "h")[:30] if event_name else "plan"
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

    @mcp.tool()
    def patch_plan_session(
        session_date: str,
        new_name: str = "",
        new_details: str = "",
        reason: str = "",
        original_name: str = "",
    ) -> str:
        """
        Persist a schedule change for a specific plan session.

        .. deprecated::
            Prefer ``update_event(slug, ...)`` from event_tools for new changes.
            This tool remains functional during the transition period but writes
            to the legacy ``schedule_overrides`` table only.

        Stores the override in the schedule_overrides DB table. The original plan
        Markdown file is never modified — overrides are applied at bake time,
        so data.json always reflects actual intent.

        Parameters
        ----------
        session_date : str
            ISO date of the session being changed (YYYY-MM-DD).
        new_name : str
            New session name. Pass empty string or "Rest" to mark the day as rest/dropped.
        new_details : str
            New session details text (e.g. "75min easy ride, Z2, 154–210W").
            Pass empty string to clear details (rest day).
        reason : str
            Brief reason for the change (e.g. "traveling", "fatigue", "swap with Thu").
        original_name : str
            Original session name from the plan (for reference in the DB). If omitted,
            the tool looks it up from the parsed plan automatically.
        """
        from ..plan_parser import get_latest_plan_path, parse_plan_file

        plan_path = get_latest_plan_path()
        if plan_path is None:
            return "Error: no training plan found."

        plan_file = plan_path.name

        if not original_name:
            try:
                plan = parse_plan_file(plan_path)
                for week in plan.weeks:
                    for session in week.sessions:
                        if session.date == session_date:
                            original_name = session.name
                            break
            except Exception:
                pass

        new_name_val = new_name.strip() if new_name.strip() else None
        new_details_val = new_details.strip() if new_details.strip() else None

        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO schedule_overrides
                    (plan_file, session_date, original_name, new_name, new_details, reason)
                VALUES (:plan_file, :session_date, :original_name, :new_name, :new_details, :reason)
                ON CONFLICT(plan_file, session_date) DO UPDATE SET
                    original_name = excluded.original_name,
                    new_name      = excluded.new_name,
                    new_details   = excluded.new_details,
                    reason        = excluded.reason,
                    created_at    = datetime('now')
                """,
                {
                    "plan_file": plan_file,
                    "session_date": session_date,
                    "original_name": original_name or None,
                    "new_name": new_name_val,
                    "new_details": new_details_val,
                    "reason": reason.strip() or None,
                },
            )

        action = f"→ {new_name_val}" if new_name_val else "→ Rest / dropped"
        orig = f" (was: {original_name})" if original_name else ""
        why = f"  Reason: {reason}" if reason else ""
        return (
            f"Override saved: {session_date}{orig} {action}{why}\n"
            f"Plan file: {plan_file}\n"
            "Run `bake` to update data.json."
        )

    @mcp.tool()
    def list_schedule_overrides(weeks: int = 8) -> str:
        """
        List all schedule overrides for the active plan within the next N weeks.
        """
        from ..plan_parser import get_latest_plan_path

        plan_path = get_latest_plan_path()
        if plan_path is None:
            return "Error: no training plan found."

        plan_file = plan_path.name
        start = (date.today() - timedelta(days=7)).isoformat()
        end = (date.today() + timedelta(days=weeks * 7)).isoformat()

        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT session_date, original_name, new_name, new_details, reason, created_at
                FROM schedule_overrides
                WHERE plan_file = ? AND session_date BETWEEN ? AND ?
                ORDER BY session_date
                """,
                (plan_file, start, end),
            ).fetchall()

        if not rows:
            return f"No schedule overrides for {plan_file} in the next {weeks} weeks."

        lines = [f"Schedule overrides — {plan_file}", ""]
        for r in rows:
            action = r["new_name"] if r["new_name"] else "Rest / dropped"
            orig = f" (was: {r['original_name']})" if r["original_name"] else ""
            why = f"  [{r['reason']}]" if r["reason"] else ""
            lines.append(f"  {r['session_date']}{orig} → {action}{why}")
            if r["new_details"]:
                lines.append(f"    Details: {r['new_details']}")
        return "\n".join(lines)
