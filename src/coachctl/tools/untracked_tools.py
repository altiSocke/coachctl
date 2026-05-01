"""Untracked activity tools: log hockey, gym, yoga etc. and weekly check-ins."""

from __future__ import annotations

import json
from datetime import date, timedelta

import yaml

from .. import paths
from ..db import get_conn

# TSS estimates per sport/intensity (minutes → TSS)
# Based on typical MET values and HR response relative to threshold
_TSS_PER_MIN = {
    "hockey": {"easy": 0.8, "moderate": 1.2, "hard": 1.6, "race": 2.0},
    "gym": {"easy": 0.4, "moderate": 0.6, "hard": 0.9, "race": 1.0},
    "yoga": {"easy": 0.2, "moderate": 0.3, "hard": 0.4, "race": 0.4},
    "default": {"easy": 0.5, "moderate": 0.8, "hard": 1.2, "race": 1.5},
}


def _estimate_tss(sport: str, duration_min: int, intensity: str) -> float:
    table = _TSS_PER_MIN.get(sport.lower(), _TSS_PER_MIN["default"])
    rate = table.get(intensity.lower(), table["moderate"])
    return round(rate * duration_min, 1)


def register(mcp) -> None:  # noqa: ANN001

    @mcp.tool()
    def log_untracked_activity(
        activity_date: str,
        sport: str,
        duration_min: int,
        intensity: str = "moderate",
        notes: str = "",
        tss_override: float | None = None,
    ) -> str:
        """
        Log an activity that wasn't tracked on Strava (e.g. hockey, gym, yoga).
        activity_date: YYYY-MM-DD
        sport: free text, e.g. 'hockey', 'gym', 'yoga'
        duration_min: session length in minutes
        intensity: 'easy', 'moderate', 'hard', or 'race'
        notes: optional free text
        tss_override: provide an explicit TSS if you don't want the auto-estimate
        """
        tss = (
            tss_override
            if tss_override is not None
            else _estimate_tss(sport, duration_min, intensity)
        )

        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO untracked_activities
                    (activity_date, sport, duration_min, intensity, tss_estimate, notes)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (activity_date, sport.lower(), duration_min, intensity.lower(), tss, notes),
            )

        paths.feedback_dir().mkdir(parents=True, exist_ok=True)
        ut_file = paths.feedback_dir() / f"{activity_date}_untracked.yaml"
        entries = []
        if ut_file.exists():
            with open(ut_file) as f:
                entries = yaml.safe_load(f) or []
        entries.append(
            {
                "date": activity_date,
                "sport": sport.lower(),
                "duration_min": duration_min,
                "intensity": intensity.lower(),
                "tss_estimate": tss,
                "notes": notes,
            }
        )
        with open(ut_file, "w") as f:
            yaml.dump(entries, f, default_flow_style=False)

        return (
            f"Logged {duration_min} min {intensity} {sport} on {activity_date} "
            f"(estimated TSS: {tss})"
        )

    @mcp.tool()
    def get_untracked_activities(weeks: int = 4) -> str:
        """
        Return untracked activities (hockey, gym, etc.) logged in the last N weeks.
        Includes TSS estimates so they can be factored into load calculations.
        """
        cutoff = (date.today() - timedelta(weeks=weeks)).isoformat()
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM untracked_activities
                WHERE activity_date >= ?
                ORDER BY activity_date DESC
                """,
                (cutoff,),
            ).fetchall()

        return json.dumps([dict(r) for r in rows], indent=2, default=str)

    @mcp.tool()
    def check_weekly_untracked() -> str:
        """
        Check whether the weekly untracked-activity check-in is due.
        Returns a status dict:
          - due: bool — True if no check-in recorded for the current week
          - current_week: YYYY-MM-DD (Monday)
          - last_checkin: YYYY-MM-DD or null
        Call mark_weekly_checkin_done() after collecting the athlete's untracked activities.
        """
        today = date.today()
        week_start = (today - timedelta(days=today.weekday())).isoformat()

        with get_conn() as conn:
            row = conn.execute(
                "SELECT checked_at FROM untracked_checkins WHERE week_start = ?",
                (week_start,),
            ).fetchone()
            last = conn.execute(
                "SELECT week_start FROM untracked_checkins ORDER BY week_start DESC LIMIT 1"
            ).fetchone()

        return json.dumps(
            {
                "due": row is None,
                "current_week": week_start,
                "last_checkin": last["week_start"] if last else None,
            },
            indent=2,
        )

    @mcp.tool()
    def mark_weekly_checkin_done() -> str:
        """
        Mark the weekly untracked-activity check-in as complete for the current week.
        Call this after you have asked the athlete about untracked sessions and logged them.
        """
        today = date.today()
        week_start = (today - timedelta(days=today.weekday())).isoformat()

        with get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO untracked_checkins (week_start) VALUES (?)",
                (week_start,),
            )

        return f"Weekly check-in marked complete for week of {week_start}."
