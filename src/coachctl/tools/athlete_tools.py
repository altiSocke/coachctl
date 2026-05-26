"""Athlete profile tools."""

from __future__ import annotations

import json
from datetime import date, timedelta

from ..config import load_athlete
from ..db import get_conn
from ..metrics import format_pace, hr_zones, pace_zones, power_zones


def register(mcp) -> None:  # noqa: ANN001

    @mcp.tool()
    def get_athlete_profile() -> str:
        """
        Return the athlete's profile: thresholds, weight, events, zones.
        Data comes from config/athlete.yaml.
        """
        athlete = load_athlete()
        if not athlete:
            return "No athlete profile found. Create config/athlete.yaml first."

        result = dict(athlete)

        if athlete.get("ftp"):
            result["power_zones"] = {
                k: f"{lo}-{hi}W" for k, (lo, hi) in power_zones(athlete["ftp"]).items()
            }
        if athlete.get("rftp"):
            result["pace_zones"] = {
                k: f"{format_pace(lo)}-{format_pace(hi)}/km"
                for k, (lo, hi) in pace_zones(athlete["rftp"]).items()
            }
        if athlete.get("threshold_hr"):
            result["hr_zones"] = {
                k: f"{lo}-{hi}bpm"
                for k, (lo, hi) in hr_zones(
                    athlete["threshold_hr"],
                    athlete.get("resting_hr", 50),
                    athlete.get("hr_zones"),
                ).items()
            }

        return json.dumps(result, indent=2, default=str)

    @mcp.tool()
    def get_athlete_profile_deep() -> str:
        """
        Build a comprehensive athlete profile from the full activity history.
        Covers: training age, sport mix, peak & current fitness, seasonal patterns,
        typical session characteristics, best efforts, pace/power trends, and
        zone tendencies. Use this at startup and when building or adjusting plans.
        """
        today = date.today()

        with get_conn() as conn:
            sport_rows = conn.execute("""
                SELECT
                    CASE
                        WHEN LOWER(sport_type) LIKE '%run%' OR LOWER(sport_type) LIKE '%trail%' THEN 'run'
                        WHEN LOWER(sport_type) LIKE '%ride%' THEN 'ride'
                        ELSE 'other'
                    END as category,
                    COUNT(*) as sessions,
                    ROUND(SUM(moving_time)/3600.0, 1) as total_hours,
                    ROUND(SUM(COALESCE(distance,0))/1000.0, 0) as total_km,
                    ROUND(SUM(COALESCE(tss,0)), 0) as total_tss,
                    MIN(date(start_date)) as first_date,
                    MAX(date(start_date)) as last_date
                FROM activities
                GROUP BY category
            """).fetchall()

            first_activity = conn.execute(
                "SELECT date(start_date) as d FROM activities ORDER BY start_date ASC LIMIT 1"
            ).fetchone()

            peak_ctl_row = conn.execute("""
                SELECT MAX(daily_tss) as peak
                FROM (
                    SELECT date(start_date) as day,
                           AVG(SUM(COALESCE(tss,0))) OVER (
                               ORDER BY date(start_date)
                               ROWS BETWEEN 41 PRECEDING AND CURRENT ROW
                           ) as daily_tss
                    FROM activities
                    WHERE tss IS NOT NULL
                    GROUP BY day
                )
            """).fetchone()

            typical_rows = conn.execute("""
                SELECT
                    CASE
                        WHEN LOWER(sport_type) LIKE '%run%' OR LOWER(sport_type) LIKE '%trail%' THEN 'run'
                        WHEN LOWER(sport_type) LIKE '%ride%' THEN 'ride'
                        ELSE 'other'
                    END as category,
                    ROUND(AVG(moving_time)/60.0, 0) as avg_duration_min,
                    ROUND(AVG(COALESCE(distance,0))/1000.0, 1) as avg_distance_km,
                    ROUND(AVG(COALESCE(tss,0)), 0) as avg_tss,
                    ROUND(AVG(average_heartrate), 0) as avg_hr,
                    ROUND(AVG(total_elevation_gain), 0) as avg_elevation_m
                FROM activities
                WHERE moving_time > 300
                GROUP BY category
            """).fetchall()

            best_run_rows = conn.execute("""
                SELECT date(start_date) as d,
                       name,
                       ROUND(distance/1000.0,1) as km,
                       moving_time,
                       ROUND(average_speed, 4) as avg_speed_ms,
                       tss
                FROM activities
                WHERE (LOWER(sport_type) LIKE '%run%' OR LOWER(sport_type) LIKE '%trail%')
                  AND distance IS NOT NULL AND distance > 5000
                  AND average_speed IS NOT NULL
                ORDER BY average_speed DESC
                LIMIT 5
            """).fetchall()

            best_ride_rows = conn.execute("""
                SELECT date(start_date) as d,
                       name,
                       ROUND(distance/1000.0,1) as km,
                       moving_time,
                       ROUND(COALESCE(np, average_watts), 0) as power_w,
                       tss
                FROM activities
                WHERE LOWER(sport_type) LIKE '%ride%'
                  AND (np IS NOT NULL OR average_watts IS NOT NULL)
                ORDER BY COALESCE(np, average_watts) DESC
                LIMIT 5
            """).fetchall()

            longest_run = conn.execute("""
                SELECT date(start_date) as d, name, ROUND(distance/1000.0,1) as km,
                       ROUND(moving_time/60.0,0) as min
                FROM activities
                WHERE (LOWER(sport_type) LIKE '%run%' OR LOWER(sport_type) LIKE '%trail%')
                  AND distance IS NOT NULL
                ORDER BY distance DESC LIMIT 3
            """).fetchall()

            longest_ride = conn.execute("""
                SELECT date(start_date) as d, name, ROUND(distance/1000.0,1) as km,
                       ROUND(moving_time/60.0,0) as min
                FROM activities
                WHERE LOWER(sport_type) LIKE '%ride%' AND distance IS NOT NULL
                ORDER BY distance DESC LIMIT 3
            """).fetchall()

            monthly_rows = conn.execute("""
                SELECT strftime('%m', start_date) as month,
                       ROUND(SUM(COALESCE(tss,0)) / COUNT(DISTINCT strftime('%Y-%W', start_date)), 0) as avg_weekly_tss,
                       COUNT(DISTINCT strftime('%Y-%W', start_date)) as weeks_sampled
                FROM activities
                GROUP BY month
                ORDER BY month
            """).fetchall()

            trend_rows = conn.execute(
                """
                SELECT strftime('%Y-W%W', start_date) as week,
                       ROUND(SUM(COALESCE(tss,0)), 0) as weekly_tss,
                       COUNT(*) as sessions,
                       ROUND(SUM(moving_time)/3600.0, 1) as hours
                FROM activities
                WHERE start_date >= ?
                GROUP BY week
                ORDER BY week
                """,
                ((today - timedelta(weeks=12)).isoformat(),),
            ).fetchall()

            athlete = load_athlete()
            thr_hr = athlete.get("threshold_hr", 178)
            rest_hr = athlete.get("resting_hr", 50)
            zones = hr_zones(thr_hr, rest_hr, athlete.get("hr_zones"))

            hr_rows = conn.execute("""
                SELECT average_heartrate, moving_time
                FROM activities
                WHERE average_heartrate IS NOT NULL AND moving_time > 300
            """).fetchall()

            zone_time: dict[str, float] = {z: 0.0 for z in zones}
            total_hr_time = 0.0
            for row in hr_rows:
                hr = row["average_heartrate"]
                mins = row["moving_time"] / 60
                for z, (lo, hi) in zones.items():
                    if lo <= hr < hi:
                        zone_time[z] += mins
                        break
                total_hr_time += mins

            zone_pct = {}
            if total_hr_time > 0:
                zone_pct = {z: round(t / total_hr_time * 100, 1) for z, t in zone_time.items()}

        training_age_days = (
            (today - date.fromisoformat(first_activity["d"])).days if first_activity else 0
        )

        sport_mix = {
            r["category"]: {
                "sessions": r["sessions"],
                "total_hours": r["total_hours"],
                "total_km": r["total_km"],
                "total_tss": r["total_tss"],
                "first_activity": r["first_date"],
                "last_activity": r["last_date"],
            }
            for r in sport_rows
        }

        typical = {
            r["category"]: {
                "avg_duration_min": r["avg_duration_min"],
                "avg_distance_km": r["avg_distance_km"],
                "avg_tss": r["avg_tss"],
                "avg_hr": r["avg_hr"],
                "avg_elevation_m": r["avg_elevation_m"],
            }
            for r in typical_rows
        }

        def _fmt_pace(speed_ms):
            if not speed_ms or speed_ms <= 0:
                return None
            secs = 1000 / speed_ms
            return f"{int(secs // 60)}:{int(secs % 60):02d}/km"

        def _fmt_dur(secs):
            if not secs:
                return None
            return f"{int(secs // 3600)}h{int((secs % 3600) // 60):02d}m"

        best_runs = [
            {
                "date": r["d"],
                "name": r["name"],
                "km": r["km"],
                "duration": _fmt_dur(r["moving_time"]),
                "avg_pace": _fmt_pace(r["avg_speed_ms"]),
                "tss": r["tss"],
            }
            for r in best_run_rows
        ]
        best_rides = [
            {
                "date": r["d"],
                "name": r["name"],
                "km": r["km"],
                "duration": _fmt_dur(r["moving_time"]),
                "np_or_avg_watts": r["power_w"],
                "tss": r["tss"],
            }
            for r in best_ride_rows
        ]

        profile = {
            "training_age_years": round(training_age_days / 365.25, 1),
            "first_activity": first_activity["d"] if first_activity else None,
            "total_activities": sum(r["sessions"] for r in sport_rows),
            "sport_mix": sport_mix,
            "typical_session": typical,
            "peak_ctl_estimate": round(float(peak_ctl_row["peak"] or 0), 1),
            "best_run_efforts": best_runs,
            "best_ride_efforts": best_rides,
            "longest_runs": [dict(r) for r in longest_run],
            "longest_rides": [dict(r) for r in longest_ride],
            "alltime_hr_zone_pct": zone_pct,
            "alltime_hr_hours_with_data": round(total_hr_time / 60, 1),
            "seasonal_avg_weekly_tss": {
                r["month"]: {
                    "avg_weekly_tss": r["avg_weekly_tss"],
                    "weeks_sampled": r["weeks_sampled"],
                }
                for r in monthly_rows
            },
            "recent_12w_trend": [dict(r) for r in trend_rows],
        }

        return json.dumps(profile, indent=2, default=str)
