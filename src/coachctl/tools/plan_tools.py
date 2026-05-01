"""Training plan tools: save, retrieve, and override plan sessions."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from .. import paths
from ..db import get_conn
from ..wiki import build_plans_index_content, diff_section


def register(mcp) -> None:  # noqa: ANN001

    @mcp.tool()
    def save_plan(plan_markdown: str, event_name: str = "", event_date: str = "") -> str:
        """
        Persist a generated training plan as a Markdown file in plans/.
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

        new_index = build_plans_index_content()
        index_diff = diff_section("plans_index.md", new_index)

        result = f"Plan saved: {plan_path.name}"
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
