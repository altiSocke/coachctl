"""
Plan compliance engine.

Compares planned training events against completed activities to produce
TSS-based compliance metrics — overall and week-by-week.

Public API
----------
compute_plan_compliance(planned, actual) -> dict
    Pure function; takes pre-loaded data.

compute_weekly_compliance(planned, actual) -> list[dict]
    Pure function; breaks the same data into ISO-week buckets.

get_compliance_from_db(conn, plan_id=None) -> dict | None
    DB-backed wrapper; resolves the active plan when plan_id is None.

get_plan_compliance_tool() -> str
    MCP-ready string wrapper (JSON or human message).
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date
from typing import Any

from .db import get_conn


# ── Pure functions ─────────────────────────────────────────────────────────────


def compute_plan_compliance(
    planned: list[dict[str, Any]],
    actual: dict[str, float],
) -> dict[str, Any]:
    """
    Compute overall compliance metrics.

    Parameters
    ----------
    planned:
        List of dicts with keys ``date`` (ISO str) and ``estimated_tss``
        (float | None).  Only sessions on or before today count toward the
        compliance denominator; future sessions are included in raw totals
        but excluded from ``compliance_pct``.
    actual:
        Mapping of ISO date → total TSS recorded on that date.

    Returns
    -------
    dict with keys:
      sessions_planned, sessions_completed, planned_tss, actual_tss,
      compliance_pct, past_sessions_planned, past_planned_tss
    """
    today = date.today().isoformat()

    sessions_planned = len(planned)
    planned_tss = sum(float(s.get("estimated_tss") or 0) for s in planned)

    # Only sessions up to today count for completion/compliance_pct
    past = [s for s in planned if s["date"] <= today]
    past_sessions_planned = len(past)
    past_planned_tss = sum(float(s.get("estimated_tss") or 0) for s in past)

    sessions_completed = sum(1 for s in past if s["date"] in actual)
    actual_tss = sum(actual.get(s["date"], 0.0) for s in past)

    compliance_pct = round(actual_tss / past_planned_tss * 100, 1) if past_planned_tss > 0 else 0.0

    return {
        "sessions_planned": sessions_planned,
        "sessions_completed": sessions_completed,
        "planned_tss": round(planned_tss, 1),
        "actual_tss": round(actual_tss, 1),
        "compliance_pct": compliance_pct,
        "past_sessions_planned": past_sessions_planned,
        "past_planned_tss": round(past_planned_tss, 1),
    }


def compute_weekly_compliance(
    planned: list[dict[str, Any]],
    actual: dict[str, float],
) -> list[dict[str, Any]]:
    """
    Break compliance metrics into ISO-week buckets, sorted chronologically.

    Returns list of dicts:
      week (str, e.g. '2026-W02'), sessions_planned, sessions_completed,
      planned_tss, actual_tss, compliance_pct
    """
    today = date.today().isoformat()

    # Group planned sessions by ISO week
    by_week: dict[str, list[dict]] = defaultdict(list)
    for s in planned:
        d = date.fromisoformat(s["date"])
        iso = f"{d.isocalendar()[0]}-W{d.isocalendar()[1]:02d}"
        by_week[iso].append(s)

    result = []
    for week_label in sorted(by_week):
        sessions = by_week[week_label]
        past = [s for s in sessions if s["date"] <= today]

        planned_tss = sum(float(s.get("estimated_tss") or 0) for s in sessions)
        past_planned_tss = sum(float(s.get("estimated_tss") or 0) for s in past)
        actual_tss = sum(actual.get(s["date"], 0.0) for s in past)
        sessions_completed = sum(1 for s in past if s["date"] in actual)

        compliance_pct = (
            round(actual_tss / past_planned_tss * 100, 1) if past_planned_tss > 0 else 0.0
        )

        result.append(
            {
                "week": week_label,
                "sessions_planned": len(sessions),
                "sessions_completed": sessions_completed,
                "planned_tss": round(planned_tss, 1),
                "actual_tss": round(actual_tss, 1),
                "compliance_pct": compliance_pct,
            }
        )

    return result


# ── DB-backed functions ────────────────────────────────────────────────────────


def get_compliance_from_db(
    conn,
    plan_id: int | None = None,
) -> dict[str, Any] | None:
    """
    Load planned sessions and matched activities from DB, return compliance dict.

    If plan_id is None, the active plan (active=1) is used.
    Returns None if no matching plan is found.
    """
    # Resolve plan
    if plan_id is None:
        row = conn.execute(
            "SELECT id, slug, title, start_date, end_date FROM plans WHERE active = 1 LIMIT 1"
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT id, slug, title, start_date, end_date FROM plans WHERE id = ?",
            (plan_id,),
        ).fetchone()

    if row is None:
        return None

    pid = row["id"]
    plan_meta = {
        "plan_id": pid,
        "slug": row["slug"],
        "title": row["title"],
        "start_date": row["start_date"],
        "end_date": row["end_date"],
    }

    # Load planned training events for this plan
    event_rows = conn.execute(
        """
        SELECT date, estimated_tss
        FROM events
        WHERE plan_id = ? AND kind = 'training'
        ORDER BY date
        """,
        (pid,),
    ).fetchall()

    planned = [{"date": r["date"], "estimated_tss": r["estimated_tss"]} for r in event_rows]

    # Determine date window for activity lookup
    if planned:
        min_date = min(s["date"] for s in planned)
        max_date = max(s["date"] for s in planned)
    else:
        min_date = row["start_date"] or "2000-01-01"
        max_date = row["end_date"] or date.today().isoformat()

    # Aggregate activity TSS per day within the plan window
    act_rows = conn.execute(
        """
        SELECT date(start_date) as day, SUM(COALESCE(tss, 0)) as day_tss
        FROM activities
        WHERE date(start_date) BETWEEN ? AND ?
        GROUP BY day
        """,
        (min_date, max_date),
    ).fetchall()

    actual: dict[str, float] = {r["day"]: r["day_tss"] for r in act_rows}

    overall = compute_plan_compliance(planned, actual)
    weekly = compute_weekly_compliance(planned, actual)

    return {**plan_meta, "overall": overall, "weekly": weekly}


# ── MCP tool wrapper ───────────────────────────────────────────────────────────


def get_plan_compliance_tool(plan_id: int | None = None) -> str:
    """
    Return plan compliance as a JSON string, or an informative message if no plan exists.
    """
    with get_conn() as conn:
        result = get_compliance_from_db(conn, plan_id=plan_id)

    if result is None:
        return (
            "No active training plan found. "
            "Use save_plan to save a plan first, or pass plan_id= for a specific plan."
        )

    return json.dumps(result, indent=2)
