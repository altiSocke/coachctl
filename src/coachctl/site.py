"""
Dashboard data assembly and JSON bake.

Usage:
    bake

Outputs: ``<DATA_ROOT>/deploy/dist/data.json`` (see ``paths.py`` for resolution).
"""

from __future__ import annotations

import json
import math
import re as _re
from datetime import date, datetime, timedelta
from pathlib import Path

from . import paths
from .db import get_conn


def _get_fitness_state() -> dict:
    """Query current CTL/ATL/TSB from the database."""
    if not paths.db_path().exists():
        return {"ctl": "—", "atl": "—", "tsb": "—", "date": str(date.today())}

    with get_conn() as conn:
        row = conn.execute(
            "SELECT date, ctl, atl, tsb FROM fitness WHERE sport_category='all' ORDER BY date DESC LIMIT 1"
        ).fetchone()

    if row:
        return {
            "ctl": round(row["ctl"], 1),
            "atl": round(row["atl"], 1),
            "tsb": round(row["tsb"], 1),
            "date": row["date"],
        }
    return {"ctl": "—", "atl": "—", "tsb": "—", "date": str(date.today())}


def _get_fitness_trend(weeks: int = 12) -> list[dict]:
    """Get daily CTL/ATL/TSB for the chart."""
    if not paths.db_path().exists():
        return []

    start = str(date.today() - timedelta(days=weeks * 7))
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT date, ctl, atl, tsb FROM fitness WHERE sport_category='all' AND date >= ? ORDER BY date",
            (start,),
        ).fetchall()

    return [
        {
            "date": r["date"],
            "ctl": round(r["ctl"], 1),
            "atl": round(r["atl"], 1),
            "tsb": round(r["tsb"], 1),
        }
        for r in rows
    ]


def _get_weekly_tss(plan_id: int | None, weeks: int = 12) -> list[dict]:
    """Weekly TSS by sport category + plan target TSS (from plans.week_tss_json)."""
    if not paths.db_path().exists():
        return []

    MON_EXPR = (
        "date(start_date, '-' || cast((strftime('%w', start_date) + 6) % 7 as text) || ' days')"
    )

    # Load target TSS map from DB: week_number → tss
    # We need to map that to Monday dates via the training events for that plan.
    target_map: dict[str, int] = {}
    if plan_id is not None:
        with get_conn() as conn:
            plan_row = conn.execute(
                "SELECT week_tss_json FROM plans WHERE id = ?", (plan_id,)
            ).fetchone()
            if plan_row and plan_row["week_tss_json"]:
                try:
                    week_tss_by_num: dict[str, int] = json.loads(plan_row["week_tss_json"])
                except (json.JSONDecodeError, TypeError):
                    week_tss_by_num = {}

                # Map week_number → earliest session date → Monday of that week
                ev_rows = conn.execute(
                    """
                    SELECT MIN(date) as first_date,
                           json_extract(payload_json, '$.week_number') as week_num
                    FROM events
                    WHERE plan_id = ? AND kind = 'training'
                    GROUP BY week_num
                    """,
                    (plan_id,),
                ).fetchall()
                for er in ev_rows:
                    wn = str(er["week_num"])
                    if wn in week_tss_by_num and er["first_date"]:
                        first = date.fromisoformat(er["first_date"])
                        mon = first - timedelta(days=first.weekday())
                        target_map[str(mon)] = week_tss_by_num[wn]

    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT
                {MON_EXPR} as week_mon,
                CASE
                    WHEN sport_type IN ('Run','TrailRun','VirtualRun') THEN 'run'
                    WHEN sport_type IN ('Ride','VirtualRide','GravelRide','MountainBikeRide','EBikeRide') THEN 'ride'
                    ELSE 'other'
                END as sport_cat,
                SUM(COALESCE(tss, 0)) as tss
            FROM activities
            WHERE start_date >= date('now', ?)
            GROUP BY week_mon, sport_cat
            ORDER BY week_mon
            """,
            (f"-{weeks * 7} days",),
        ).fetchall()

    week_data: dict[str, dict] = {}
    for r in rows:
        wk = r["week_mon"]
        if wk not in week_data:
            week_data[wk] = {"week": wk, "run": 0.0, "ride": 0.0, "other": 0.0}
        week_data[wk][r["sport_cat"]] += r["tss"]

    result = []
    for wk, d in sorted(week_data.items()):
        d["target"] = target_map.get(wk)
        d["total"] = round(d["run"] + d["ride"] + d["other"], 1)
        d["run"] = round(d["run"], 1)
        d["ride"] = round(d["ride"], 1)
        d["other"] = round(d["other"], 1)
        result.append(d)

    today_mon = date.today() - timedelta(days=date.today().weekday())
    future_weeks = sorted((wk for wk in target_map if wk > str(today_mon)), key=lambda x: x)[:8]
    existing_weeks = {d["week"] for d in result}
    for wk in future_weeks:
        if wk not in existing_weeks:
            result.append(
                {
                    "week": wk,
                    "run": 0.0,
                    "ride": 0.0,
                    "other": 0.0,
                    "total": 0.0,
                    "target": target_map[wk],
                }
            )

    result.sort(key=lambda x: x["week"])
    return result


def _project_fitness(plan_id: int | None, fitness: dict, weeks: int = 8) -> list[dict]:
    """
    Project CTL/ATL/TSB forward using training events for the active plan.

    For each future training event:
    - If payload.details contains 'Est. TSS ~NN', use that directly.
    - Otherwise distribute the week's target TSS evenly across unassigned sessions
      for that week (from plans.week_tss_json).
    """
    try:
        ctl = float(fitness["ctl"])
        atl = float(fitness["atl"])
    except (ValueError, KeyError):
        return []

    if plan_id is None or not paths.db_path().exists():
        return []

    today = date.today()

    # Load week_tss_json from plans table
    week_tss_by_num: dict[str, int] = {}
    with get_conn() as conn:
        plan_row = conn.execute(
            "SELECT week_tss_json FROM plans WHERE id = ?", (plan_id,)
        ).fetchone()
        if plan_row and plan_row["week_tss_json"]:
            try:
                week_tss_by_num = json.loads(plan_row["week_tss_json"])
            except (json.JSONDecodeError, TypeError):
                week_tss_by_num = {}

        # Load future training events
        ev_rows = conn.execute(
            """
            SELECT date, payload_json,
                   json_extract(payload_json, '$.week_number') as week_num
            FROM events
            WHERE plan_id = ? AND kind = 'training' AND date > ?
            ORDER BY date
            """,
            (plan_id, str(today)),
        ).fetchall()

    # Build daily_tss map
    daily_tss: dict[str, float] = {}

    # Group events by week_num so we can distribute remaining TSS
    from collections import defaultdict

    week_sessions: dict[str, list[dict]] = defaultdict(list)
    for er in ev_rows:
        wn = str(er["week_num"]) if er["week_num"] is not None else "0"
        payload = {}
        try:
            payload = json.loads(er["payload_json"]) if er["payload_json"] else {}
        except (json.JSONDecodeError, TypeError):
            pass
        week_sessions[wn].append({"date": er["date"], "details": payload.get("details", "")})

    for wn, sessions in week_sessions.items():
        target = week_tss_by_num.get(wn, 0)
        assigned: dict[str, float] = {}
        for s in sessions:
            m = _re.search(r"[Ee]st\.?\s*TSS\s*[~≈]?\s*(\d+)", s["details"])
            if m:
                assigned[s["date"]] = float(m.group(1))
        remaining = max(0.0, target - sum(assigned.values()))
        unassigned = [s for s in sessions if s["date"] not in assigned]
        per_session = (remaining / len(unassigned)) if unassigned else 0.0
        for s in sessions:
            daily_tss[s["date"]] = assigned.get(s["date"], max(0.0, per_session))

    projected = []
    _ctl_k = 1 - math.exp(-1 / 42)
    _atl_k = 1 - math.exp(-1 / 7)
    for i in range(1, weeks * 7 + 1):
        d = today + timedelta(days=i)
        tss = daily_tss.get(str(d), 0.0)
        ctl = ctl + _ctl_k * (tss - ctl)
        atl = atl + _atl_k * (tss - atl)
        projected.append(
            {
                "date": str(d),
                "ctl": round(ctl, 1),
                "atl": round(atl, 1),
                "tsb": round(ctl - atl, 1),
            }
        )

    return projected


def _get_race_events_from_db() -> list[dict]:
    """Return upcoming race events from the events table with days-out."""
    if not paths.db_path().exists():
        return []
    today = date.today()
    cutoff = (today - timedelta(days=7)).isoformat()
    try:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT slug, name, date, payload_json
                FROM events
                WHERE kind = 'race' AND date >= ? AND status NOT IN ('cancelled', 'completed')
                ORDER BY date
                """,
                (cutoff,),
            ).fetchall()
    except Exception:
        return []

    result = []
    for r in rows:
        ev_date = date.fromisoformat(r["date"])
        days_out = (ev_date - today).days
        payload: dict = {}
        try:
            payload = json.loads(r["payload_json"]) if r["payload_json"] else {}
        except (json.JSONDecodeError, TypeError):
            pass
        result.append(
            {
                "name": r["name"],
                "date": r["date"],
                "days_out": days_out,
                "priority": payload.get("priority", "C"),
                "goal_time": payload.get("goal", {}).get("target_time")
                if isinstance(payload.get("goal"), dict)
                else payload.get("goal_time"),
            }
        )
    return result


def _get_calendar_window_for_dashboard(past_days: int = 7, future_days: int = 200) -> list[dict]:
    """
    Project the unified events table for the dashboard.
    Returns a list of event dicts (race, training, untracked, appointment,
    activity) ready for ``data.json``.
    """
    try:
        from .events import get_calendar
    except Exception:
        return []
    today = date.today()
    start = (today - timedelta(days=past_days)).isoformat()
    end = (today + timedelta(days=future_days)).isoformat()
    try:
        events = get_calendar(start, end)
    except Exception:
        return []
    out = []
    for e in events:
        d = e.to_dict()
        try:
            ev_date = date.fromisoformat(d["date"])
            d["days_out"] = (ev_date - today).days
        except Exception:
            d["days_out"] = None
        out.append(d)
    return out


def _get_plan_from_db() -> dict | None:
    """
    Load the active plan and its training events from the DB.

    Returns a dict with keys: plan_id, title, period, event, current_week,
    total_weeks, weeks (list of week dicts). Returns None if no active plan.
    """
    if not paths.db_path().exists():
        return None

    with get_conn() as conn:
        plan_row = conn.execute(
            "SELECT id, title, start_date, end_date, source_md_path FROM plans WHERE active = 1 ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not plan_row:
            return None
        plan_id = plan_row["id"]

        ev_rows = conn.execute(
            """
            SELECT date, name, summary, status, notes, payload_json
            FROM events
            WHERE plan_id = ? AND kind = 'training'
            ORDER BY date
            """,
            (plan_id,),
        ).fetchall()

        # Fetch (date, sport_type) pairs for sport-aware completion detection.
        # Using a set of (date, sport_category) tuples avoids false positives
        # where any activity on a planned day marks the session complete.
        activity_sport_dates: set[tuple[str, str]] = set()
        for r in conn.execute(
            "SELECT date(start_date) as d, sport_type FROM activities"
        ).fetchall():
            sport_type = (r["sport_type"] or "").lower()
            if "run" in sport_type or "trail" in sport_type:
                cat = "run"
            elif "ride" in sport_type or "cycle" in sport_type or "virtual" in sport_type:
                cat = "ride"
            else:
                cat = "other"
            activity_sport_dates.add((r["d"], cat))
            activity_sport_dates.add((r["d"], "any"))  # always allow any-sport match

    def _infer_session_sport(name: str) -> str:
        """Return 'run', 'ride', or 'any' based on session name keywords."""
        n = name.lower()
        if any(w in n for w in ("run", "jog", "tempo", "interval", "long run", "trail", "5k", "10k", "half", "marathon")):
            return "run"
        if any(w in n for w in ("ride", "bike", "cycle", "cycling", "zwift", "criterium", "fondo")):
            return "ride"
        return "any"

    # Group events by week_number from payload
    from collections import defaultdict

    weeks_map: dict[int, list[dict]] = defaultdict(list)
    phases_map: dict[int, str] = {}
    today = str(date.today())

    for er in ev_rows:
        payload: dict = {}
        try:
            payload = json.loads(er["payload_json"]) if er["payload_json"] else {}
        except (json.JSONDecodeError, TypeError):
            pass
        wn: int = payload.get("week_number", 1)
        phases_map[wn] = payload.get("phase", "")
        session_sport = _infer_session_sport(er["name"] or "")
        activity_match = (er["date"], session_sport) in activity_sport_dates
        completed = er["status"] == "completed" or activity_match
        weeks_map[wn].append(
            {
                "day_label": _day_label(er["date"]),
                "date": er["date"],
                "name": er["name"],
                "details": payload.get("details", er["summary"] or ""),
                "completed": completed,
                "overridden": payload.get("overridden", False),
                "override_reason": er["notes"] or "",
                "feedback": None,  # populated later
            }
        )

    if not weeks_map:
        return None

    # Determine current week
    current_week = 1
    for wn in sorted(weeks_map.keys()):
        sessions = weeks_map[wn]
        dates = [s["date"] for s in sessions if s["date"]]
        if dates and dates[0] <= today <= dates[-1]:
            current_week = wn
            break
    else:
        # Default to first incomplete week
        for wn in sorted(weeks_map.keys()):
            if not all(s["completed"] for s in weeks_map[wn]):
                current_week = wn
                break

    weeks_data = []
    for wn in sorted(weeks_map.keys()):
        sessions = weeks_map[wn]
        non_rest = [s for s in sessions if "rest" not in s["name"].lower()]
        all_completed = bool(non_rest) and all(s["completed"] for s in non_rest)
        weeks_data.append(
            {
                "number": wn,
                "title": f"Week {wn}",
                "target_tss": None,  # populated from week_tss_json if needed
                "phase": phases_map.get(wn, ""),
                "all_completed": all_completed,
                "sessions": sessions,
            }
        )

    # Populate target_tss per week from plans.week_tss_json
    with get_conn() as conn:
        ptss_row = conn.execute(
            "SELECT week_tss_json FROM plans WHERE id = ?", (plan_id,)
        ).fetchone()
    if ptss_row and ptss_row["week_tss_json"]:
        try:
            week_tss_map: dict[str, int] = json.loads(ptss_row["week_tss_json"])
            for wd in weeks_data:
                wd["target_tss"] = week_tss_map.get(str(wd["number"]))
        except (json.JSONDecodeError, TypeError):
            pass

    title = plan_row["title"] or ""
    start_date = plan_row["start_date"] or ""
    end_date = plan_row["end_date"] or ""
    # Fallback: derive end_date from last event date if missing
    if not end_date and ev_rows:
        end_date = ev_rows[-1]["date"] or ""
    period = f"{start_date} – {end_date}" if start_date and end_date else ""
    # Extract event name from source_md_path if title doesn't carry it
    event_name = ""
    if plan_row["source_md_path"]:
        stem = plan_row["source_md_path"].replace(".md", "")
        event_name = stem.replace("-", " ").title()

    return {
        "plan_id": plan_id,
        "title": title,
        "period": period,
        "event": event_name,
        "current_week": current_week,
        "total_weeks": len(weeks_data),
        "weeks": weeks_data,
    }


def _day_label(iso_date: str) -> str:
    """Return short day label from an ISO date string, e.g. 'Mon'."""
    try:
        return date.fromisoformat(iso_date).strftime("%a")
    except (ValueError, TypeError):
        return ""


def _extract_phases(weeks_data: list[dict]) -> list[dict]:
    """Group consecutive weeks with the same phase into phase blocks."""
    phases: list[dict] = []
    for week in weeks_data:
        phase_raw = week.get("phase") or "Training"
        if not phases or phases[-1]["_raw"] != phase_raw:
            m = _re.search(r"—\s*(.+?)(?:\s*\(|$)", phase_raw)
            short = m.group(1).strip() if m else phase_raw
            nm = _re.search(r"PHASE\s+(\d+)", phase_raw, _re.IGNORECASE)
            phases.append(
                {
                    "_raw": phase_raw,
                    "name": short,
                    "number": int(nm.group(1)) if nm else len(phases) + 1,
                    "start_week": week["number"],
                    "end_week": week["number"],
                }
            )
        else:
            phases[-1]["end_week"] = week["number"]

    for p in phases:
        p["week_count"] = p["end_week"] - p["start_week"] + 1
        del p["_raw"]

    return phases


def _get_feedback_by_date() -> dict[str, dict]:
    """Return feedback entries keyed by ISO date string."""
    if not paths.db_path().exists():
        return {}

    with get_conn() as conn:
        rows = conn.execute(
            "SELECT activity_date, rpe, felt, notes FROM feedback ORDER BY activity_date DESC LIMIT 200"
        ).fetchall()

    return {
        r["activity_date"]: {
            "rpe": r["rpe"],
            "felt": r["felt"],
            "notes": r["notes"],
        }
        for r in rows
    }


def _get_training_monotony(weeks: int = 13) -> list[dict]:
    """Get rolling Training Monotony and Strain for the chart (last ~90 days)."""
    if not paths.db_path().exists():
        return []

    with get_conn() as conn:
        from .metrics import get_training_monotony_from_db

        return get_training_monotony_from_db(conn, sport_category="all", window=7)


def _get_monotony_snapshot() -> dict:
    """Return today's Training Monotony and Strain snapshot."""
    if not paths.db_path().exists():
        return {}

    with get_conn() as conn:
        from .metrics import get_current_monotony_snapshot

        return get_current_monotony_snapshot(conn, sport_category="all", window=7)


def _compute_danger_zones(
    fitness: dict, trend: list[dict], monotony_snapshot: dict | None = None
) -> list[dict]:
    """Return list of active warnings based on fitness metrics."""
    zones: list[dict] = []
    try:
        tsb = float(fitness["tsb"])
        ctl = float(fitness["ctl"])
    except (ValueError, KeyError, TypeError):
        return zones

    if tsb < -30:
        zones.append(
            {
                "type": "overreach",
                "message": "Overreaching risk — TSB below -30. Prioritise recovery.",
                "severity": "high",
            }
        )
    elif tsb < -20:
        zones.append(
            {
                "type": "fatigue",
                "message": "High fatigue — TSB below -20. Monitor sleep and soreness.",
                "severity": "medium",
            }
        )

    if tsb > 15:
        zones.append(
            {
                "type": "fresh",
                "message": "Race-ready form — TSB above +15.",
                "severity": "info",
            }
        )

    if len(trend) >= 14:
        try:
            old_ctl = float(trend[-14]["ctl"])
            if ctl < old_ctl - 5:
                zones.append(
                    {
                        "type": "detraining",
                        "message": "Fitness declining — CTL dropped more than 5 points in 2 weeks.",
                        "severity": "medium",
                    }
                )
        except (ValueError, KeyError, TypeError):
            pass

    # Training Monotony warning
    if monotony_snapshot:
        try:
            monotony = float(monotony_snapshot.get("monotony", 0))
            strain = float(monotony_snapshot.get("strain", 0))
            if monotony > 2.0:
                zones.append(
                    {
                        "type": "monotony",
                        "message": f"Training Monotony {monotony:.1f} — too repetitive. Vary session intensity.",
                        "severity": "high",
                    }
                )
            elif monotony > 1.5:
                zones.append(
                    {
                        "type": "monotony",
                        "message": f"Training Monotony {monotony:.1f} — moderate. Consider adding variety.",
                        "severity": "medium",
                    }
                )
            if strain > 2000:
                zones.append(
                    {
                        "type": "strain",
                        "message": f"Training Strain {strain:.0f} — very high. Risk of overtraining.",
                        "severity": "high",
                    }
                )
        except (ValueError, TypeError):
            pass

    return zones


def _get_recent_run_tss(limit: int = 14) -> list[dict]:
    """
    Return the most recent run activities with pace-based rTSS and power-based rTSS_P.
    Used to show the two metrics side-by-side on the dashboard.
    """
    if not paths.db_path().exists():
        return []

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                name,
                date(start_date) as day,
                moving_time,
                distance,
                tss,
                rtss,
                rtss_power,
                average_watts,
                weighted_avg_watts,
                total_elevation_gain,
                sport_type
            FROM activities
            WHERE (sport_type LIKE '%Run%' OR sport_type LIKE '%Trail%')
            ORDER BY start_date DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    result = []
    for r in rows:
        dist_km = round(r["distance"] / 1000, 1) if r["distance"] else None
        pace_sec = round(r["moving_time"] / (r["distance"] / 1000), 0) if r["distance"] else None
        pace_fmt = None
        if pace_sec:
            m, s = divmod(int(pace_sec), 60)
            pace_fmt = f"{m}:{s:02d}"
        result.append(
            {
                "name": r["name"],
                "date": r["day"],
                "dist_km": dist_km,
                "pace": pace_fmt,
                "elev_m": round(r["total_elevation_gain"]) if r["total_elevation_gain"] else None,
                "tss": round(r["tss"], 1) if r["tss"] is not None else None,
                "rtss": round(r["rtss"], 1) if r["rtss"] is not None else None,
                "rtss_power": round(r["rtss_power"], 1) if r["rtss_power"] is not None else None,
                "avg_watts": round(r["average_watts"]) if r["average_watts"] else None,
                "sport_type": r["sport_type"],
            }
        )
    return result


def _get_weekly_run_tss(weeks: int = 12) -> list[dict]:
    """
    Weekly run TSS comparison: pace-based rTSS sum vs power-based rTSS_P sum.
    Only weeks where at least one run has power data are included in rtss_power.
    """
    if not paths.db_path().exists():
        return []

    MON_EXPR = (
        "date(start_date, '-' || cast((strftime('%w', start_date) + 6) % 7 as text) || ' days')"
    )
    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT
                {MON_EXPR} as week_mon,
                SUM(COALESCE(rtss, 0))       as rtss_sum,
                SUM(COALESCE(rtss_power, 0)) as rtss_power_sum,
                COUNT(rtss_power)            as power_count
            FROM activities
            WHERE (sport_type LIKE '%Run%' OR sport_type LIKE '%Trail%')
              AND start_date >= date('now', ?)
            GROUP BY week_mon
            ORDER BY week_mon
            """,
            (f"-{weeks * 7} days",),
        ).fetchall()

    return [
        {
            "week": r["week_mon"],
            "rtss": round(r["rtss_sum"], 1),
            "rtss_power": round(r["rtss_power_sum"], 1) if r["power_count"] > 0 else None,
        }
        for r in rows
    ]


def _extract_decision_gates_from_plan() -> list[dict]:
    """Parse decision gates table from the active plan's markdown."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT source_md_path, start_date, end_date FROM plans WHERE active = 1 ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if not row or not row["source_md_path"]:
        return []

    md_path = paths.data_root() / "profile" / "plans" / row["source_md_path"]
    if not md_path.exists():
        # Fallback: try direct path
        md_path = paths.data_root() / row["source_md_path"]
        if not md_path.exists():
            return []

    # Determine base year from plan dates for accurate gate date parsing
    plan_start = date.fromisoformat(row["start_date"]) if row["start_date"] else None

    import re

    text = md_path.read_text(encoding="utf-8")
    # Find "## Decision Gates" section
    match = re.search(r"## Decision Gates\s*\n(.*?)(?=\n## |\n---|\Z)", text, re.DOTALL)
    if not match:
        return []

    gates: list[dict] = []
    for line in match.group(1).strip().splitlines():
        line = line.strip()
        if not line.startswith("|") or line.startswith("|--") or line.startswith("| Date"):
            continue
        cols = [c.strip() for c in line.split("|")[1:-1]]
        if len(cols) < 5:
            continue
        gate_date_str = cols[0]
        # Parse date like "Jun 14" → YYYY-MM-DD using plan start year
        try:
            from datetime import datetime as _dt

            base_year = plan_start.year if plan_start else date.today().year
            dt = _dt.strptime(f"{gate_date_str} {base_year}", "%b %d %Y")
            gate_date_candidate = dt.date()
            # If gate is before plan start, it likely belongs to the next year
            if plan_start and gate_date_candidate < plan_start:
                gate_date_candidate = gate_date_candidate.replace(year=base_year + 1)
            gate_date = gate_date_candidate.isoformat()
        except Exception:
            gate_date = gate_date_str

        today_str = str(date.today())
        status = "upcoming"
        if gate_date <= today_str:
            status = "past"  # UI will mark pass/fail based on actual results

        gates.append(
            {
                "date": gate_date,
                "test": cols[1],
                "a_goal": cols[2],
                "b_goal": cols[3],
                "revise": cols[4],
                "status": status,
            }
        )
    return gates


def _extract_key_metrics_from_plan() -> list[dict]:
    """Parse key metrics table from the active plan's markdown."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT source_md_path FROM plans WHERE active = 1 ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if not row or not row["source_md_path"]:
        return []

    md_path = paths.data_root() / "profile" / "plans" / row["source_md_path"]
    if not md_path.exists():
        md_path = paths.data_root() / row["source_md_path"]
        if not md_path.exists():
            return []

    import re

    text = md_path.read_text(encoding="utf-8")
    match = re.search(r"## Key Metrics & Targets\s*\n(.*?)(?=\n## |\n---|\Z)", text, re.DOTALL)
    if not match:
        return []

    metrics: list[dict] = []
    lines = [l.strip() for l in match.group(1).strip().splitlines() if l.strip().startswith("|")]
    if len(lines) < 2:
        return []

    # First row is header
    headers = [c.strip() for c in lines[0].split("|")[1:-1]]
    for line in lines[2:]:  # skip header + separator
        cols = [c.strip() for c in line.split("|")[1:-1]]
        if len(cols) < len(headers):
            continue
        metrics.append(
            {
                "metric": cols[0],
                "start": cols[1] if len(cols) > 1 else "",
                "mid": cols[2] if len(cols) > 2 else "",
                "peak": cols[3] if len(cols) > 3 else "",
                "race_day": cols[4] if len(cols) > 4 else "",
            }
        )
    return metrics


def _build_iso_to_plan_week_map(plan_id: int) -> dict[str, int]:
    """
    Return a mapping of ISO-week string (e.g. '2026-W19') → plan week number
    for all training events belonging to the given plan.
    """
    if not paths.db_path().exists():
        return {}

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT MIN(date) as first_date,
                   json_extract(payload_json, '$.week_number') as week_num
            FROM events
            WHERE plan_id = ? AND kind = 'training'
            GROUP BY week_num
            """,
            (plan_id,),
        ).fetchall()

    iso_map: dict[str, int] = {}
    for r in rows:
        if r["first_date"] is None or r["week_num"] is None:
            continue
        try:
            d = date.fromisoformat(r["first_date"])
            # ISO week: use isocalendar()
            iso_year, iso_week, _ = d.isocalendar()
            key = f"{iso_year}-W{iso_week:02d}"
            iso_map[key] = int(r["week_num"])
        except (ValueError, TypeError):
            pass

    return iso_map


def get_dashboard_data(plan_path: Path | None = None) -> dict:
    """Assemble all dashboard data as a JSON-serialisable dict."""
    # plan_path argument retained for API compatibility but ignored —
    # plan data now comes from the events/plans tables.
    plan_data = _get_plan_from_db()
    plan_id = plan_data["plan_id"] if plan_data else None

    # Inject feedback into session dicts
    if plan_data:
        feedback = _get_feedback_by_date()
        for week in plan_data["weeks"]:
            for session in week["sessions"]:
                if session.get("date"):
                    session["feedback"] = feedback.get(session["date"])

    fitness = _get_fitness_state()
    trend = _get_fitness_trend(16)
    weekly_tss = _get_weekly_tss(plan_id, 16)
    events = _get_race_events_from_db()
    calendar = _get_calendar_window_for_dashboard()
    projected = _project_fitness(plan_id, fitness, weeks=16)
    phases = _extract_phases(plan_data["weeks"]) if plan_data else []
    monotony_trend = _get_training_monotony()
    monotony_snapshot = _get_monotony_snapshot()
    danger_zones = _compute_danger_zones(fitness, trend, monotony_snapshot)
    recent_runs = _get_recent_run_tss(14)
    weekly_run_tss = _get_weekly_run_tss(12)

    # ── New metrics ───────────────────────────────────────────────────────────
    compliance = None
    try:
        from .plan_compliance import get_plan_compliance_tool
        import json as _json

        raw = get_plan_compliance_tool()
        if isinstance(raw, str) and raw.startswith("{"):
            compliance = _json.loads(raw)
    except Exception:
        pass

    # Enrich compliance weekly entries with plan_week numbers
    if compliance and plan_id:
        iso_to_plan_week = _build_iso_to_plan_week_map(plan_id)
        for w in compliance.get("weekly", []):
            w["plan_week"] = iso_to_plan_week.get(w.get("week"))

    acwr = None
    try:
        from .metrics import get_acwr_from_db
        from .db import get_conn as _get_conn

        with _get_conn() as _conn:
            acwr = get_acwr_from_db(_conn)
    except Exception:
        pass

    zones = None
    try:
        from .metrics import get_zone_distribution_from_db
        from .db import get_conn as _get_conn

        with _get_conn() as _conn:
            zd = get_zone_distribution_from_db(_conn, weeks=8)
        if "zone_pct" in zd:
            # Transform to ordered array [Z1%,Z2%,...,Z5%] for the dashboard bar
            pct = zd["zone_pct"]
            distribution = [pct.get(f"Z{i}", 0) for i in range(1, 6)]
            zones = {
                "distribution": distribution,
                "zone_pct": pct,
                "zone_hours": zd.get("zone_hours"),
                "total_hours": zd.get("total_hours"),
                "polarization_index": zd.get("polarization_index"),
                "low_intensity_pct": zd.get("low_intensity_pct"),
                "high_intensity_pct": zd.get("high_intensity_pct"),
                "interpretation": zd.get("interpretation"),
                "weeks_analysed": zd.get("weeks_analysed"),
            }
    except Exception:
        pass

    critical_power = None
    try:
        from .metrics import compute_best_efforts as _compute_be, fit_critical_power
        from .config import load_athlete as _load_athlete
        from .db import get_conn as _get_conn

        with _get_conn() as _conn:
            _be = _compute_be(_conn)
        _athlete_cfg = _load_athlete()
        critical_power = fit_critical_power(
            _be.get("ride", []),
            ftp=_athlete_cfg.get("ftp"),
        )
    except Exception:
        pass

    try:
        from .config import load_athlete

        cfg = load_athlete()
        goals = cfg.get("goals", {})
        # Format rftp (sec/km) as MM:SS/km string
        rftp_raw = cfg.get("rftp")
        if rftp_raw:
            rftp_min = int(rftp_raw) // 60
            rftp_sec = int(rftp_raw) % 60
            rftp_str = f"{rftp_min}:{rftp_sec:02d}/km"
        else:
            rftp_str = None
        thresholds = {
            "ftp": cfg.get("ftp"),
            "lthr": cfg.get("threshold_hr"),
            "rftp": rftp_str,
            "vo2max": cfg.get("vo2max"),
        }
    except Exception:
        goals = {}
        thresholds = {}

    # Decision gates & key metrics from plan markdown
    decision_gates: list = []
    key_metrics: list = []
    try:
        decision_gates = _extract_decision_gates_from_plan()
        key_metrics = _extract_key_metrics_from_plan()
    except Exception:
        pass

    return {
        "generated_at": datetime.now().isoformat(),
        "plan": {
            "title": plan_data["title"],
            "period": plan_data["period"],
            "event": plan_data["event"],
            "current_week": plan_data["current_week"],
            "total_weeks": plan_data["total_weeks"],
            "weeks": plan_data["weeks"],
        }
        if plan_data
        else None,
        "phases": phases,
        "fitness": fitness,
        "monotony": monotony_snapshot,
        "danger_zones": danger_zones,
        "trend": trend,
        "monotony_trend": monotony_trend,
        "projected": projected,
        "weekly_tss": weekly_tss,
        "events": events,
        "calendar": calendar,
        "goals": goals,
        "thresholds": thresholds,
        "recent_runs": recent_runs,
        "weekly_run_tss": weekly_run_tss,
        "compliance": compliance,
        "acwr": acwr,
        "zones": zones,
        "critical_power": critical_power,
        "decision_gates": decision_gates,
        "key_metrics": key_metrics,
    }


def bake(plan_path: Path | None = None) -> Path:
    """
    Compute dashboard data and write it to ``<DATA_ROOT>/deploy/dist/data.json``.

    This is the only output artifact — no HTML is generated. The dashboard
    server (``coachctl.dashboard``) reads this file at request time.
    """
    from .db import migrate_and_drop_legacy

    migrate_and_drop_legacy()

    data = get_dashboard_data(plan_path)
    out = paths.data_json()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return out


def main() -> None:
    """CLI entry point for `bake`."""
    from dotenv import load_dotenv

    load_dotenv(paths.env_file())

    out = bake()
    print(f"Baked: {out}")


if __name__ == "__main__":
    main()
