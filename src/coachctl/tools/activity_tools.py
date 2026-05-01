"""Activity query and analysis tools."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

from ..config import load_athlete
from ..db import get_conn
from ..metrics import format_pace, hr_zones, power_zones
from ..sync import fetch_activity_laps, fetch_activity_streams, get_strava_access_token


def register(mcp) -> None:  # noqa: ANN001

    @mcp.tool()
    def get_activity_detail(activity_id: int) -> str:
        """
        Detailed view of a single activity by Strava ID.
        Includes all raw fields and computed metrics.
        """
        with get_conn() as conn:
            row = conn.execute("SELECT * FROM activities WHERE id = ?", (activity_id,)).fetchone()
        if not row:
            return f"Activity {activity_id} not found."

        d = dict(row)
        d.pop("raw_json", None)
        if d.get("average_speed") and "run" in (d.get("sport_type") or "").lower():
            d["average_pace"] = format_pace(1000 / d["average_speed"])
        return json.dumps(d, indent=2, default=str)

    @mcp.tool()
    def get_activity_streams(activity_id: int) -> str:
        """
        Fetch and analyse time-series streams for an activity.
        Returns: power curve, HR drift/decoupling, zone time distribution,
        cadence stats, elevation profile, and per-km splits with pace/power/HR.
        Streams are cached locally after the first fetch.
        """
        # Check cache
        with get_conn() as conn:
            cached = conn.execute(
                "SELECT streams_json FROM activity_streams WHERE activity_id = ?",
                (activity_id,),
            ).fetchone()

        if cached:
            raw_streams = json.loads(cached["streams_json"])
        else:
            try:
                access_token = get_strava_access_token()
                raw_streams = fetch_activity_streams(access_token, activity_id)
            except Exception as e:
                return f"Failed to fetch streams: {e}"
            if not raw_streams:
                return f"No stream data available for activity {activity_id}."
            with get_conn() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO activity_streams (activity_id, streams_json) VALUES (?, ?)",
                    (activity_id, json.dumps(raw_streams)),
                )

        def _data(key: str) -> list | None:
            s = raw_streams.get(key)
            if isinstance(s, dict):
                return s.get("data")
            return None

        time_s = _data("time")
        hr = _data("heartrate")
        watts = _data("watts")
        velocity = _data("velocity_smooth")
        altitude = _data("altitude")
        cadence = _data("cadence")

        if not time_s:
            return f"Stream data for activity {activity_id} has no time series."

        n = len(time_s)

        with get_conn() as conn:
            act_row = conn.execute(
                "SELECT sport_type, distance, moving_time FROM activities WHERE id = ?",
                (activity_id,),
            ).fetchone()
        sport_type = (dict(act_row).get("sport_type") or "").lower() if act_row else ""
        is_run = "run" in sport_type or "trail" in sport_type
        is_ride = "ride" in sport_type
        total_dist = dict(act_row).get("distance") or 0 if act_row else 0

        athlete = load_athlete()
        thr_hr = athlete.get("threshold_hr", 178)
        rest_hr = athlete.get("resting_hr", 50)
        ftp = athlete.get("ftp", 280)

        result: dict = {"activity_id": activity_id, "stream_points": n}

        if hr:
            zones = hr_zones(thr_hr, rest_hr)
            zone_secs: dict[str, float] = {z: 0.0 for z in zones}
            for i in range(1, len(hr)):
                dt = time_s[i] - time_s[i - 1] if i < len(time_s) else 1
                for z, (lo, hi) in zones.items():
                    if lo <= hr[i] < hi:
                        zone_secs[z] += dt
                        break
            total_hr_s = sum(zone_secs.values())
            if total_hr_s > 0:
                result["hr_zone_distribution"] = {
                    z: {"seconds": round(s), "pct": round(s / total_hr_s * 100, 1)}
                    for z, s in zone_secs.items()
                }

            mid = len(hr) // 2
            avg_hr_first = sum(hr[:mid]) / mid if mid > 0 else 0
            avg_hr_second = sum(hr[mid:]) / (len(hr) - mid) if (len(hr) - mid) > 0 else 0
            result["hr_drift"] = {
                "first_half_avg_hr": round(avg_hr_first, 1),
                "second_half_avg_hr": round(avg_hr_second, 1),
                "drift_pct": round((avg_hr_second - avg_hr_first) / max(avg_hr_first, 1) * 100, 1),
            }

            if watts and is_ride:
                avg_pw_first = sum(watts[:mid]) / mid if mid > 0 else 0
                avg_pw_second = (
                    sum(watts[mid:]) / (len(watts) - mid) if (len(watts) - mid) > 0 else 0
                )
                eff_first = avg_pw_first / max(avg_hr_first, 1)
                eff_second = avg_pw_second / max(avg_hr_second, 1)
                result["cardiac_decoupling_pct"] = round(
                    (eff_first - eff_second) / max(eff_first, 0.01) * 100, 1
                )
            elif velocity and is_run:
                avg_vel_first = sum(velocity[:mid]) / mid if mid > 0 else 0
                avg_vel_second = (
                    sum(velocity[mid:]) / (len(velocity) - mid) if (len(velocity) - mid) > 0 else 0
                )
                eff_first = avg_vel_first / max(avg_hr_first, 1)
                eff_second = avg_vel_second / max(avg_hr_second, 1)
                result["cardiac_decoupling_pct"] = round(
                    (eff_first - eff_second) / max(eff_first, 0.01) * 100, 1
                )

        if watts:
            non_zero = [w for w in watts if w > 0]
            result["power_stats"] = {
                "avg_watts": round(sum(watts) / len(watts), 1),
                "max_watts": max(watts),
                "avg_watts_non_zero": round(sum(non_zero) / len(non_zero), 1) if non_zero else 0,
            }

            window = 30
            if len(watts) > window:
                rolling = []
                for i in range(window, len(watts)):
                    avg30 = sum(watts[i - window : i]) / window
                    rolling.append(avg30**4)
                np_val = (sum(rolling) / len(rolling)) ** 0.25
                result["power_stats"]["normalised_power"] = round(np_val, 1)
                result["power_stats"]["intensity_factor"] = round(np_val / ftp, 3)
                result["power_stats"]["variability_index"] = round(
                    np_val / (sum(watts) / len(watts)), 2
                )

            pzones = power_zones(ftp)
            pz_secs: dict[str, float] = {z: 0.0 for z in pzones}
            for i in range(1, len(watts)):
                dt = time_s[i] - time_s[i - 1] if i < len(time_s) else 1
                for z, (lo, hi) in pzones.items():
                    if lo <= watts[i] < hi:
                        pz_secs[z] += dt
                        break
            total_pw_s = sum(pz_secs.values())
            if total_pw_s > 0:
                result["power_zone_distribution"] = {
                    z: {"seconds": round(s), "pct": round(s / total_pw_s * 100, 1)}
                    for z, s in pz_secs.items()
                }

            peaks = {}
            for dur_label, dur_s in [
                ("5s", 5),
                ("30s", 30),
                ("1min", 60),
                ("5min", 300),
                ("20min", 1200),
            ]:
                if len(watts) >= dur_s:
                    running = sum(watts[:dur_s])
                    best = running
                    for i in range(dur_s, len(watts)):
                        running += watts[i] - watts[i - dur_s]
                        if running > best:
                            best = running
                    peaks[dur_label] = round(best / dur_s, 1)
            if peaks:
                result["peak_power"] = peaks

        if velocity and is_run:
            moving_vel = [v for v in velocity if v > 0.5]
            if moving_vel:
                avg_vel = sum(moving_vel) / len(moving_vel)
                result["pace_stats"] = {
                    "avg_pace": format_pace(1000 / avg_vel),
                    "max_pace": format_pace(1000 / max(moving_vel)),
                    "avg_speed_ms": round(avg_vel, 2),
                }

        if cadence:
            non_zero_cad = [c for c in cadence if c > 0]
            if non_zero_cad:
                result["cadence_stats"] = {
                    "avg": round(sum(non_zero_cad) / len(non_zero_cad), 1),
                    "max": max(non_zero_cad),
                    "min": min(non_zero_cad),
                }

        if altitude:
            result["elevation_stats"] = {
                "start_m": round(altitude[0], 0),
                "max_m": round(max(altitude), 0),
                "min_m": round(min(altitude), 0),
                "end_m": round(altitude[-1], 0),
            }

        if velocity and total_dist > 0:
            cum_dist = [0.0]
            for i in range(1, n):
                dt = time_s[i] - time_s[i - 1]
                cum_dist.append(cum_dist[-1] + velocity[i] * dt)

            splits = []
            km = 1
            j = 0
            while km * 1000 <= cum_dist[-1]:
                target = km * 1000
                while j < len(cum_dist) - 1 and cum_dist[j] < (km - 1) * 1000:
                    j += 1
                si = j
                ei = si
                while ei < len(cum_dist) - 1 and cum_dist[ei] < target:
                    ei += 1
                if ei <= si:
                    km += 1
                    continue

                split_time = time_s[ei] - time_s[si]
                split: dict = {"km": km, "time_s": round(split_time)}
                if split_time > 0:
                    split["pace"] = format_pace(split_time)
                if hr:
                    seg_hr = hr[si : ei + 1]
                    split["avg_hr"] = round(sum(seg_hr) / len(seg_hr), 1) if seg_hr else None
                if watts:
                    seg_w = watts[si : ei + 1]
                    split["avg_watts"] = round(sum(seg_w) / len(seg_w), 1) if seg_w else None
                if altitude:
                    split["elev_change_m"] = round(
                        altitude[min(ei, len(altitude) - 1)] - altitude[si], 1
                    )
                if cadence:
                    seg_c = [c for c in cadence[si : ei + 1] if c > 0]
                    split["avg_cadence"] = round(sum(seg_c) / len(seg_c), 1) if seg_c else None
                splits.append(split)
                km += 1

            result["km_splits"] = splits

        return json.dumps(result, indent=2, default=str)

    @mcp.tool()
    def get_activity_laps(activity_id: int) -> str:
        """
        Fetch lap-by-lap breakdown for an activity.
        Returns each lap's index, distance, moving time, pace/speed, average HR,
        max HR, average power, average cadence, and elevation gain.
        Useful for analysing interval workouts, strides, and structured sessions.
        """
        try:
            access_token = get_strava_access_token()
            laps_raw = fetch_activity_laps(access_token, activity_id)
        except Exception as e:
            return f"Failed to fetch laps: {e}"

        if not laps_raw:
            return f"No lap data available for activity {activity_id}."

        laps = []
        for lap in laps_raw:
            entry: dict = {
                "lap": lap.get("lap_index"),
                "name": lap.get("name"),
                "distance_m": round(lap.get("distance", 0), 1),
                "moving_time_s": lap.get("moving_time"),
                "elapsed_time_s": lap.get("elapsed_time"),
                "avg_speed_ms": lap.get("average_speed"),
                "max_speed_ms": lap.get("max_speed"),
                "avg_hr": lap.get("average_heartrate"),
                "max_hr": lap.get("max_heartrate"),
                "avg_watts": lap.get("average_watts"),
                "avg_cadence": lap.get("average_cadence"),
                "total_elevation_gain_m": lap.get("total_elevation_gain"),
            }
            if lap.get("average_speed") and lap.get("average_speed", 0) > 0:
                entry["avg_pace"] = format_pace(1000 / lap["average_speed"])
            if lap.get("max_speed") and lap.get("max_speed", 0) > 0:
                entry["max_pace"] = format_pace(1000 / lap["max_speed"])
            laps.append(entry)

        return json.dumps({"activity_id": activity_id, "laps": laps}, indent=2, default=str)

    @mcp.tool()
    def get_recent_activities(n: int = 20, sport: str = "all") -> str:
        """
        List the N most recent activities with key metrics.
        Sport filter: 'all', 'run', 'ride', or any Strava sport_type substring.
        """
        sport_clause = ""
        sport_params: list = []
        if sport != "all":
            sport_clause = "AND LOWER(sport_type) LIKE ?"
            sport_params = [f"%{sport.lower()}%"]

        with get_conn() as conn:
            rows = conn.execute(
                f"""
                SELECT id, name, sport_type, start_date, moving_time, distance,
                       total_elevation_gain, average_heartrate, average_watts,
                       tss, intensity_factor
                FROM activities
                WHERE 1=1 {sport_clause}
                ORDER BY start_date DESC
                LIMIT ?
                """,
                (*sport_params, n),
            ).fetchall()

        activities = []
        for r in rows:
            d = dict(r)
            mt = d.get("moving_time") or 0
            d["duration"] = f"{mt // 3600}h{(mt % 3600) // 60:02d}m"
            dist = d.get("distance")
            if dist:
                d["distance_km"] = round(dist / 1000, 2)
            activities.append(d)

        return json.dumps(activities, indent=2, default=str)

    @mcp.tool()
    def find_similar_workouts(
        sport: str, min_tss: float = 0, max_tss: float = 999, limit: int = 10
    ) -> str:
        """
        Find past workouts matching criteria. Useful for comparing progression.
        Filters by sport type and TSS range.
        """
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT id, name, sport_type, start_date, moving_time, distance,
                       total_elevation_gain, average_heartrate, average_watts, tss
                FROM activities
                WHERE LOWER(sport_type) LIKE ?
                  AND COALESCE(tss, 0) BETWEEN ? AND ?
                ORDER BY start_date DESC
                LIMIT ?
                """,
                (f"%{sport.lower()}%", min_tss, max_tss, limit),
            ).fetchall()

        return json.dumps([dict(r) for r in rows], indent=2, default=str)

    @mcp.tool()
    def get_new_activities() -> str:
        """
        Return activities that have not yet been reviewed by the coach.
        Capped at the last 4 weeks and a maximum of 10 activities, so a first-run
        or long absence never floods the session with stale history.
        Returns full metrics so the coach can give detailed feedback on each session.
        """
        cutoff = (date.today() - timedelta(weeks=4)).isoformat()
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT id, name, sport_type, start_date, moving_time, distance,
                       total_elevation_gain, average_heartrate, max_heartrate,
                       average_watts, weighted_avg_watts, average_cadence,
                       tss, intensity_factor, np, ngp, suffer_score
                FROM activities
                WHERE reviewed_at IS NULL
                  AND start_date >= ?
                ORDER BY start_date ASC
                LIMIT 10
                """,
                (cutoff,),
            ).fetchall()

        activities = []
        for r in rows:
            d = dict(r)
            mt = d.get("moving_time") or 0
            d["duration"] = f"{mt // 3600}h{(mt % 3600) // 60:02d}m"
            dist = d.get("distance")
            if dist:
                d["distance_km"] = round(dist / 1000, 2)
            activities.append(d)

        return json.dumps(activities, indent=2, default=str)

    @mcp.tool()
    def mark_activities_reviewed(activity_ids: list[int]) -> str:
        """
        Mark a list of activity IDs as reviewed by the coach.
        Call this after delivering feedback on new activities so they are not shown again.
        activity_ids: list of Strava activity IDs
        """
        now = datetime.now(timezone.utc).isoformat()
        with get_conn() as conn:
            conn.executemany(
                "UPDATE activities SET reviewed_at = ? WHERE id = ?",
                [(now, aid) for aid in activity_ids],
            )
        return f"Marked {len(activity_ids)} activities as reviewed."
