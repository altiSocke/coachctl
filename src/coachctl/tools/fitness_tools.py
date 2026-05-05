"""Fitness metrics tools: CTL/ATL/TSB, zone distribution, weekly summary."""

from __future__ import annotations

import json
from datetime import date, timedelta
from itertools import groupby

from ..db import get_conn
from ..metrics import (
    compute_fitness_series,
    get_current_fitness,
    get_daily_tss_from_db,
    get_zone_distribution_from_db,
)


def _weekly_summary(daily: list[dict]) -> list[dict]:
    """Aggregate daily CTL/ATL/TSB into weekly summaries."""
    result = []
    for week_key, days in groupby(
        daily,
        key=lambda d: (
            d["date"][:4] + "-W" + str(date.fromisoformat(d["date"]).isocalendar()[1]).zfill(2)
        ),
    ):
        days_list = list(days)
        result.append(
            {
                "week": week_key,
                "ctl": days_list[-1]["ctl"],
                "atl": days_list[-1]["atl"],
                "tsb": days_list[-1]["tsb"],
                "total_tss": round(sum(d["tss"] for d in days_list), 1),
                "days_trained": sum(1 for d in days_list if d["tss"] > 0),
            }
        )
    return result


def register(mcp) -> None:  # noqa: ANN001

    @mcp.tool()
    def get_fitness_state(sport: str = "all") -> str:
        """
        Current fitness snapshot: CTL (fitness), ATL (fatigue), TSB (form).
        Sport filter: 'all', 'run', or 'ride'.
        """
        with get_conn() as conn:
            current = get_current_fitness(conn, sport)
        return json.dumps(current, indent=2)

    @mcp.tool()
    def get_fitness_trend(weeks: int = 12, sport: str = "all") -> str:
        """
        CTL/ATL/TSB trend over the last N weeks.
        Returns daily values as a JSON array.
        Sport filter: 'all', 'run', or 'ride'.
        """
        weeks = max(1, min(weeks, 260))  # cap at 5 years
        with get_conn() as conn:
            daily = get_daily_tss_from_db(conn, sport)
        if not daily:
            return "No TSS data found. Run sync_activities first."

        start = date.today() - timedelta(weeks=weeks)
        series = compute_fitness_series(daily, start_date=min(min(daily), start))
        cutoff = start.isoformat()
        filtered = [s for s in series if s["date"] >= cutoff]

        if weeks > 8 and len(filtered) > 60:
            return json.dumps(_weekly_summary(filtered), indent=2)
        return json.dumps(filtered, indent=2)

    @mcp.tool()
    def get_zone_distribution(weeks: int = 8) -> str:
        """
        HR zone distribution over last N weeks.
        Shows % time in each zone, polarization index, and interpretation.
        """
        weeks = max(1, min(weeks, 260))
        with get_conn() as conn:
            dist = get_zone_distribution_from_db(conn, weeks)
        return json.dumps(dist, indent=2)

    @mcp.tool()
    def get_weekly_summary(weeks: int = 8) -> str:
        """
        Weekly training summary: volume, TSS, intensity breakdown per sport.
        """
        weeks = max(1, min(weeks, 260))
        cutoff = (date.today() - timedelta(weeks=weeks)).isoformat()
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT
                    strftime('%Y-W%W', start_date) as week,
                    sport_type,
                    COUNT(*) as sessions,
                    SUM(moving_time) as total_time_s,
                    SUM(distance) as total_distance_m,
                    SUM(total_elevation_gain) as total_elev,
                    SUM(COALESCE(tss, 0)) as total_tss,
                    AVG(average_heartrate) as avg_hr
                FROM activities
                WHERE start_date >= ?
                GROUP BY week, sport_type
                ORDER BY week DESC, sport_type
                """,
                (cutoff,),
            ).fetchall()

        result = {}
        for r in rows:
            w = r["week"]
            if w not in result:
                result[w] = {"week": w, "sports": {}, "total_tss": 0, "total_hours": 0}
            sport = r["sport_type"]
            hours = round((r["total_time_s"] or 0) / 3600, 1)
            result[w]["sports"][sport] = {
                "sessions": r["sessions"],
                "hours": hours,
                "km": round((r["total_distance_m"] or 0) / 1000, 1),
                "elevation": round(r["total_elev"] or 0),
                "tss": round(r["total_tss"] or 0),
                "avg_hr": round(r["avg_hr"] or 0),
            }
            result[w]["total_tss"] += round(r["total_tss"] or 0)
            result[w]["total_hours"] += hours

        for w in result.values():
            w["total_hours"] = round(w["total_hours"], 1)

        return json.dumps(list(result.values()), indent=2)
