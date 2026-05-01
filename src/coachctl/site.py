"""
Dashboard data assembly and JSON bake.

Usage:
    bake

Outputs: ``<DATA_ROOT>/deploy/dist/data.json`` (see ``paths.py`` for resolution).
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from . import paths
from .db import get_conn
from .plan_parser import Plan, get_latest_plan_path, parse_plan_file


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


def _get_weekly_tss(plan: Plan, weeks: int = 12) -> list[dict]:
    """Weekly TSS by sport category + plan target TSS."""
    if not paths.db_path().exists():
        return []

    MON_EXPR = (
        "date(start_date, '-' || cast((strftime('%w', start_date) + 6) % 7 as text) || ' days')"
    )

    target_map: dict[str, int] = {}
    for w in plan.weeks:
        if w.target_tss:
            dates = [s.date for s in w.sessions if s.date]
            if dates:
                first = date.fromisoformat(min(dates))
                mon = first - timedelta(days=first.weekday())
                target_map[str(mon)] = w.target_tss

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


def _project_fitness(plan: Plan, fitness: dict, weeks: int = 8) -> list[dict]:
    """
    Project CTL/ATL/TSB forward using plan sessions day-by-day.

    For each future session:
    - If details contain 'Est. TSS ~NN', use that directly.
    - Otherwise distribute the week's remaining target TSS evenly across
      non-rest training days.
    Rest days and unplanned days get TSS = 0.
    """
    import re as _re

    try:
        ctl = float(fitness["ctl"])
        atl = float(fitness["atl"])
    except (ValueError, KeyError):
        return []

    today = date.today()

    daily_tss: dict[str, float] = {}

    for w in plan.weeks:
        if not w.target_tss:
            continue

        training_sessions = []
        for s in w.sessions:
            if not s.date or s.date <= str(today):
                continue
            if "rest" in s.name.lower():
                daily_tss[s.date] = 0.0
            else:
                training_sessions.append(s)

        if not training_sessions:
            continue

        assigned: dict[str, float] = {}
        for s in training_sessions:
            m = _re.search(r"[Ee]st\.?\s*TSS\s*[~≈]?\s*(\d+)", s.details)
            if m:
                assigned[s.date] = float(m.group(1))

        remaining_tss = w.target_tss - sum(assigned.values())
        unassigned = [s for s in training_sessions if s.date not in assigned]
        per_session = (remaining_tss / len(unassigned)) if unassigned else 0.0

        for s in training_sessions:
            daily_tss[s.date] = assigned.get(s.date, max(0.0, per_session))

    projected = []
    for i in range(1, weeks * 7 + 1):
        d = today + timedelta(days=i)
        tss = daily_tss.get(str(d), 0.0)
        ctl = ctl + (tss - ctl) / 42
        atl = atl + (tss - atl) / 7
        projected.append(
            {
                "date": str(d),
                "ctl": round(ctl, 1),
                "atl": round(atl, 1),
                "tsb": round(ctl - atl, 1),
            }
        )

    return projected


def _get_upcoming_events() -> list[dict]:
    """Return upcoming events from athlete.yaml with days-out."""
    try:
        from .config import load_athlete

        cfg = load_athlete()
    except Exception:
        return []

    today = date.today()
    events = []
    for e in cfg.get("events", []):
        ev_date = e.get("date")
        if not ev_date:
            continue
        if isinstance(ev_date, str):
            ev_date = date.fromisoformat(ev_date)
        days_out = (ev_date - today).days
        if days_out < -7:
            continue
        events.append(
            {
                "name": e.get("name", ""),
                "date": str(ev_date),
                "days_out": days_out,
                "priority": e.get("priority", "C"),
                "goal_time": e.get("goal_time"),
            }
        )
    return sorted(events, key=lambda x: x["days_out"])


def _determine_current_week(plan: Plan) -> int:
    """Find which week number we're currently in based on session dates."""
    today = str(date.today())
    for week in plan.weeks:
        dates = [s.date for s in week.sessions if s.date]
        if dates and dates[0] and dates[-1]:
            if dates[0] <= today <= dates[-1]:
                return week.number
    for week in plan.weeks:
        if not all(s.completed for s in week.sessions):
            return week.number
    return 1


def _mark_completion_from_db(plan: Plan) -> None:
    """Cross-reference plan sessions with activities DB to mark completed."""
    import sqlite3

    db = paths.db_path()
    if not db.exists():
        return

    conn = sqlite3.connect(str(db))
    rows = conn.execute("SELECT DISTINCT date(start_date) as d FROM activities").fetchall()
    conn.close()

    activity_dates = {r[0] for r in rows}

    for week in plan.weeks:
        for session in week.sessions:
            if (
                session.date
                and session.date in activity_dates
                and "rest" not in session.name.lower()
            ):
                session.completed = True


def _add_all_completed_flag(plan: Plan) -> None:
    """Add a helper flag to weeks for tab styling."""
    for week in plan.weeks:
        non_rest = [s for s in week.sessions if "rest" not in s.name.lower()]
        week.all_completed = len(non_rest) > 0 and all(s.completed for s in non_rest)  # type: ignore[attr-defined]


def _load_overrides(plan_path: Path) -> dict[str, dict]:
    """Load schedule_overrides from DB for the given plan file."""
    if not paths.db_path().exists():
        return {}

    plan_file = plan_path.name
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT session_date, original_name, new_name, new_details, reason
            FROM schedule_overrides
            WHERE plan_file = ?
            """,
            (plan_file,),
        ).fetchall()

    return {
        r["session_date"]: {
            "new_name": r["new_name"],
            "new_details": r["new_details"],
            "reason": r["reason"],
            "original_name": r["original_name"],
        }
        for r in rows
    }


def _apply_overrides(plan: Plan, overrides: dict[str, dict]) -> None:
    """Mutate plan sessions in-place to reflect schedule overrides."""
    for week in plan.weeks:
        for session in week.sessions:
            if session.date and session.date in overrides:
                ov = overrides[session.date]
                if ov["new_name"] is not None:
                    session.name = ov["new_name"]
                else:
                    session.name = "Rest"
                session.details = ov["new_details"] or ""
                session.overridden = True  # type: ignore[attr-defined]
                session.override_reason = ov["reason"] or ""  # type: ignore[attr-defined]


def _extract_phases(plan: Plan) -> list[dict]:
    """Group consecutive weeks with the same phase into phase blocks."""
    import re as _re

    phases: list[dict] = []
    for week in plan.weeks:
        phase_raw = week.phase or "Training"
        if not phases or phases[-1]["_raw"] != phase_raw:
            m = _re.search(r"—\s*(.+?)(?:\s*\(|$)", phase_raw)
            short = m.group(1).strip() if m else phase_raw
            nm = _re.search(r"PHASE\s+(\d+)", phase_raw, _re.IGNORECASE)
            phases.append(
                {
                    "_raw": phase_raw,
                    "name": short,
                    "number": int(nm.group(1)) if nm else len(phases) + 1,
                    "start_week": week.number,
                    "end_week": week.number,
                }
            )
        else:
            phases[-1]["end_week"] = week.number

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


def get_dashboard_data(plan_path: Path | None = None) -> dict:
    """Assemble all dashboard data as a JSON-serialisable dict."""
    if plan_path is None:
        plan_path = get_latest_plan_path()
    if plan_path is None:
        raise FileNotFoundError("No training plan found in plans directory")

    plan = parse_plan_file(plan_path)
    overrides = _load_overrides(plan_path)
    _apply_overrides(plan, overrides)
    _mark_completion_from_db(plan)
    _add_all_completed_flag(plan)

    fitness = _get_fitness_state()
    trend = _get_fitness_trend(16)
    weekly_tss = _get_weekly_tss(plan, 16)
    events = _get_upcoming_events()
    projected = _project_fitness(plan, fitness, weeks=16)
    current_week = _determine_current_week(plan)
    phases = _extract_phases(plan)
    feedback = _get_feedback_by_date()
    monotony_trend = _get_training_monotony()
    monotony_snapshot = _get_monotony_snapshot()
    danger_zones = _compute_danger_zones(fitness, trend, monotony_snapshot)
    recent_runs = _get_recent_run_tss(14)
    weekly_run_tss = _get_weekly_run_tss(12)

    try:
        from .config import load_athlete

        cfg = load_athlete()
        goals = cfg.get("goals", {})
    except Exception:
        goals = {}

    weeks_data = []
    for w in plan.weeks:
        sessions_data = []
        for s in w.sessions:
            fb = feedback.get(s.date) if s.date else None
            sessions_data.append(
                {
                    "day_label": s.day_label,
                    "date": s.date,
                    "name": s.name,
                    "details": s.details,
                    "completed": s.completed,
                    "overridden": getattr(s, "overridden", False),
                    "override_reason": getattr(s, "override_reason", ""),
                    "feedback": fb,
                }
            )
        weeks_data.append(
            {
                "number": w.number,
                "title": w.title,
                "target_tss": w.target_tss,
                "phase": w.phase,
                "all_completed": w.all_completed,
                "sessions": sessions_data,
            }
        )

    return {
        "generated_at": datetime.now().isoformat(),
        "plan": {
            "title": plan.title,
            "period": plan.period,
            "event": plan.event,
            "current_week": current_week,
            "total_weeks": len(plan.weeks),
            "weeks": weeks_data,
        },
        "phases": phases,
        "fitness": fitness,
        "monotony": monotony_snapshot,
        "danger_zones": danger_zones,
        "trend": trend,
        "monotony_trend": monotony_trend,
        "projected": projected,
        "weekly_tss": weekly_tss,
        "events": events,
        "goals": goals,
        "recent_runs": recent_runs,
        "weekly_run_tss": weekly_run_tss,
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
