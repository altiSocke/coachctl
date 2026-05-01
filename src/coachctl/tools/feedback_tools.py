"""Feedback and coaching notes tools."""

from __future__ import annotations

import json
from datetime import date

from .. import paths
from ..db import get_conn


def register(mcp) -> None:  # noqa: ANN001

    @mcp.tool()
    def log_feedback(
        activity_date: str,
        rpe: int,
        felt: str = "ok",
        notes: str = "",
        activity_id: int | None = None,
    ) -> str:
        """
        Log post-session feedback.
        activity_date: YYYY-MM-DD
        rpe: 1-10 (Rate of Perceived Exertion)
        felt: 'great','good','ok','bad','terrible'
        notes: free text
        activity_id: optional Strava activity ID to link
        """
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO feedback (activity_date, activity_id, rpe, felt, notes)
                VALUES (?, ?, ?, ?, ?)
                """,
                (activity_date, activity_id, rpe, felt, notes),
            )

        return f"Feedback logged for {activity_date} (RPE: {rpe}, felt: {felt})"

    @mcp.tool()
    def get_recent_feedback(n: int = 10) -> str:
        """Get the N most recent feedback entries."""
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT f.*, a.name as activity_name, a.sport_type
                FROM feedback f
                LEFT JOIN activities a ON f.activity_id = a.id
                ORDER BY f.activity_date DESC
                LIMIT ?
                """,
                (n,),
            ).fetchall()

        return json.dumps([dict(r) for r in rows], indent=2, default=str)

    @mcp.tool()
    def save_coaching_note(
        note: str,
        category: str = "general",
        tags: str = "",
        session_date: str = "",
    ) -> str:
        """
        Persist a coaching observation, decision, or summary for future sessions.
        Appends to training_history.md in the personal wiki.
        category: 'general', 'goal', 'observation', 'adjustment', 'schedule'
        tags: comma-separated keywords e.g. 'fatigue,run,plan'
        session_date: YYYY-MM-DD (defaults to today)
        """
        from ..wiki import append_log, append_section

        session_date = session_date or date.today().isoformat()
        tag_str = f" `[{tags}]`" if tags else ""
        block = f"\n### {session_date}\n**{category}**{tag_str}:\n{note}\n"

        append_section("training_history.md", block)
        append_log(f"save_coaching_note: {category} {session_date}")

        return f"Coaching note saved to training_history.md ({category}, {session_date}): {note[:80]}..."

    @mcp.tool()
    def get_coaching_notes(n: int = 20, category: str = "") -> str:
        """
        Retrieve recent coaching notes from training_history.md.
        Optionally filter by category keyword.
        """
        wiki_file = paths.personal_dir() / "training_history.md"
        if not wiki_file.exists():
            return "training_history.md not found."

        text = wiki_file.read_text(encoding="utf-8")

        # Split into note blocks by ### date headers
        import re
        blocks = re.split(r"\n(?=### \d{4}-\d{2}-\d{2})", text)

        # Filter by category if requested
        if category:
            blocks = [b for b in blocks if f"**{category}**" in b]

        # Return last n blocks (most recent last in file → reverse for recency)
        recent = blocks[-n:] if len(blocks) > n else blocks
        recent = list(reversed(recent))

        if not recent:
            return f"No coaching notes found{' for category: ' + category if category else ''}."

        return "\n---\n".join(b.strip() for b in recent)
