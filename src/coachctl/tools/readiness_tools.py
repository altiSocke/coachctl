"""Readiness check-in tools."""

from __future__ import annotations

from datetime import date, timedelta

from ..db import get_conn


def register(mcp) -> None:  # noqa: ANN001

    @mcp.tool()
    def log_readiness_checkin(
        sleep: int,
        energy: int,
        soreness: int,
        notes: str = "",
        checkin_date: str = "",
    ) -> str:
        """
        Log a subjective readiness check-in before a hard session.

        Call this only before prescribed hard sessions (intervals, threshold,
        VO2max, race-pace). Ask the athlete three questions on a 1–5 scale:
          - sleep:    How did you sleep last night? (1=terrible, 5=great)
          - energy:   How is your energy right now? (1=exhausted, 5=great)
          - soreness: How are your legs? (1=very sore/heavy, 5=totally fresh)

        After logging, gate the session:
          - Any score ≤ 2  → downgrade to Z2, flag concern to athlete
          - All scores ≥ 4 → proceed as planned
          - Mixed          → use judgement, note the concern

        Parameters
        ----------
        sleep, energy, soreness : int
            Each 1–5 (1 = worst, 5 = best).
        notes : str
            Optional free-text from athlete (e.g. "legs heavy from yesterday's climb").
        checkin_date : str
            YYYY-MM-DD. Defaults to today.
        """
        for val, name in [(sleep, "sleep"), (energy, "energy"), (soreness, "soreness")]:
            if not 1 <= val <= 5:
                return f"Invalid {name} score {val} — must be 1–5."

        today = checkin_date or date.today().isoformat()

        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO readiness_checkins (checkin_date, sleep, energy, soreness, notes)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(checkin_date) DO UPDATE SET
                    sleep=excluded.sleep,
                    energy=excluded.energy,
                    soreness=excluded.soreness,
                    notes=excluded.notes,
                    created_at=datetime('now')
                """,
                (today, sleep, energy, soreness, notes),
            )

        avg = (sleep + energy + soreness) / 3
        if min(sleep, energy, soreness) <= 2:
            gate = "One or more scores <= 2 — recommend downgrading to Z2 today."
        elif avg >= 4:
            gate = "Scores good — proceed as planned."
        else:
            gate = "Mixed readiness — use judgement. Consider reducing intensity slightly."

        return (
            f"Readiness logged for {today}: sleep={sleep} energy={energy} soreness={soreness}\n"
            f"{gate}"
        )

    @mcp.tool()
    def get_readiness_history(days: int = 14) -> str:
        """
        Return recent readiness check-ins as a formatted table.

        Shows subjective sleep/energy/soreness scores and notes for the last N days.
        Use this to spot fatigue trends before prescribing load changes.

        Parameters
        ----------
        days : int
            Number of days to look back (default 14, max 90).
        """
        days = max(1, min(days, 90))
        cutoff = (date.today() - timedelta(days=days)).isoformat()

        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT checkin_date, sleep, energy, soreness, notes
                FROM readiness_checkins
                WHERE checkin_date >= ?
                ORDER BY checkin_date DESC
                """,
                (cutoff,),
            ).fetchall()

        if not rows:
            return f"No readiness check-ins in the last {days} days."

        header = f"{'Date':<12} {'Sleep':>5} {'Energy':>6} {'Soreness':>8} {'Avg':>5}  Notes"
        sep = "─" * 65
        lines = [f"Readiness check-ins — last {days} days", "", header, sep]
        for r in rows:
            avg = round((r["sleep"] + r["energy"] + r["soreness"]) / 3, 1)
            flag = " [!]" if min(r["sleep"], r["energy"], r["soreness"]) <= 2 else ""
            lines.append(
                f"{r['checkin_date']:<12} {r['sleep']:>5} {r['energy']:>6} {r['soreness']:>8} "
                f"{avg:>5.1f}  {r['notes'] or ''}{flag}"
            )
        return "\n".join(lines)
