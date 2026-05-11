"""Fitness metrics tools: CTL/ATL/TSB, ACWR, session TSS estimate, VO2max, zone distribution, weekly summary."""

from __future__ import annotations

import json
from datetime import date, timedelta
from itertools import groupby

from ..db import get_conn
from ..metrics import (
    compute_acwr,
    compute_fitness_series,
    estimate_session_tss,
    estimate_week_tss,
    estimate_vo2max_from_athlete,
    get_acwr_from_db,
    get_best_recent_run,
    get_current_fitness,
    get_daily_tss_from_db,
    get_zone_distribution_from_db,
    predict_race_times,
)


def _fmt_seconds(total_seconds: int) -> str:
    """Format seconds as H:MM:SS."""
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    return f"{h}:{m:02d}:{s:02d}"


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

    # ── ACWR ──────────────────────────────────────────────────────────────────

    @mcp.tool()
    def get_acwr(sport: str = "all") -> str:
        """
        Acute:Chronic Workload Ratio (ACWR) — injury risk indicator.

        Returns two variants:
        - rolling_average (Gabbett 2016): 7-day rolling mean / 28-day rolling mean.
        - ema: uses the same exponential moving averages as the CTL/ATL model.

        Risk zones (rolling average):
        - <0.8  → undertrained / detraining risk
        - 0.8–1.3 → optimal training zone
        - 1.3–1.5 → caution — elevated injury risk
        - >1.5  → high injury risk — reduce load

        Sport filter: 'all', 'run', or 'ride'.
        """
        with get_conn() as conn:
            result = get_acwr_from_db(conn, sport)
        return json.dumps(result, indent=2)

    # ── Session TSS Estimation ─────────────────────────────────────────────────

    @mcp.tool()
    def estimate_session_tss_tool(
        duration_min: float,
        intensity: str = "moderate",
        sport: str = "any",
    ) -> str:
        """
        Estimate TSS for a planned session from duration and intensity label.

        Intensity options (maps to approximate IF):
        - recovery   → IF 0.65 (Z1, very easy)
        - easy       → IF 0.72 (Z2, aerobic base)
        - moderate   → IF 0.80 (Z2/Z3, comfortable endurance)
        - tempo      → IF 0.88 (Z3, comfortably hard)
        - threshold  → IF 1.00 (Z4, ~1hr race pace)
        - vo2max     → IF 1.12 (Z5, intervals)
        - anaerobic  → IF 1.30 (Z6, short hard efforts)

        Formula: TSS = (duration_min / 60) × IF² × 100

        Use this to validate week TSS targets when building a training plan.
        """
        try:
            result = estimate_session_tss(duration_min, intensity, sport)
        except ValueError as e:
            return f"Error: {e}"
        return json.dumps(result, indent=2)

    @mcp.tool()
    def estimate_week_tss_tool(sessions_json: str) -> str:
        """
        Estimate total TSS for a planned training week.

        sessions_json: JSON array of session objects, each with:
          - duration_min (required)
          - intensity (required): recovery/easy/moderate/tempo/threshold/vo2max/anaerobic
          - sport (optional): label only

        Example:
          [
            {"sport": "run", "duration_min": 60, "intensity": "easy"},
            {"sport": "run", "duration_min": 45, "intensity": "threshold"},
            {"sport": "ride", "duration_min": 120, "intensity": "moderate"}
          ]

        Returns total estimated TSS plus per-session breakdown.
        """
        try:
            sessions = json.loads(sessions_json)
        except json.JSONDecodeError as e:
            return f"Error: invalid JSON — {e}"
        if not isinstance(sessions, list):
            return "Error: sessions_json must be a JSON array."

        breakdown = []
        total = 0.0
        errors = []
        for i, s in enumerate(sessions):
            try:
                r = estimate_session_tss(
                    duration_min=s["duration_min"],
                    intensity=s.get("intensity", "moderate"),
                    sport=s.get("sport", "any"),
                )
                breakdown.append(r)
                total += r["tss_estimate"]
            except (ValueError, KeyError) as e:
                errors.append(f"Session {i}: {e}")

        result: dict = {"total_tss_estimate": round(total, 1), "sessions": breakdown}
        if errors:
            result["errors"] = errors
        return json.dumps(result, indent=2)

    # ── Race Time Prediction ───────────────────────────────────────────────────

    @mcp.tool()
    def predict_race_time(
        reference_distance_km: float = 0.0,
        reference_time: str = "",
        mode: str = "road",
    ) -> str:
        """
        Predict finish times at standard race distances using the Riegel model.

        T2 = T1 × (D2 / D1) ^ exponent

        Reference performance
        ---------------------
        Provide BOTH reference_distance_km and reference_time, or leave both
        empty to auto-detect from the longest recent run in the last 12 months.

        reference_distance_km: distance of the known performance (km), e.g. 21.1
        reference_time: finish time as "HH:MM:SS" or "MM:SS", e.g. "1:45:30"

        Mode
        ----
        mode='road'  → exponent 1.06 (Riegel 1977 — calibrated for 5k–marathon)
        mode='ultra' → exponent 1.15 (higher fatigue penalty beyond 42 km)

        Outputs predictions for: 5k, 10k, Half marathon, Marathon, 50k.

        Confidence note: predictions beyond 3× the reference distance carry
        increasing uncertainty — physiological factors not captured by the
        power-law model (nutrition, terrain, sleep) become dominant.
        """
        # ── Parse / validate inputs ───────────────────────────────────────────
        provided_dist = reference_distance_km > 0
        provided_time = bool(reference_time.strip())

        if provided_dist != provided_time:
            return (
                "Error: provide BOTH reference_distance_km and reference_time, "
                "or leave both empty for auto-detection from DB."
            )

        if mode not in ("road", "ultra"):
            return "Error: mode must be 'road' or 'ultra'."

        # ── Auto-detect from DB ───────────────────────────────────────────────
        if not provided_dist:
            with get_conn() as conn:
                ref = get_best_recent_run(conn)
            if ref is None:
                return (
                    "No qualifying run found in the last 12 months "
                    "(need at least one run >3 km). "
                    "Provide reference_distance_km and reference_time manually."
                )
            d1_km = ref["distance_km"]
            t1_s = float(ref["time_seconds"])
            source_note = (
                f"Auto-detected from activity {ref['activity_id']} "
                f"on {ref['date']}: {ref['distance_km']} km"
            )
        else:
            # ── Parse time string ─────────────────────────────────────────────
            parts = reference_time.strip().split(":")
            try:
                if len(parts) == 3:
                    t1_s = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                elif len(parts) == 2:
                    t1_s = int(parts[0]) * 60 + int(parts[1])
                else:
                    return "Error: reference_time must be 'HH:MM:SS' or 'MM:SS'."
            except ValueError:
                return "Error: could not parse reference_time. Use 'HH:MM:SS' or 'MM:SS'."

            if t1_s <= 0:
                return "Error: reference_time must be positive."

            d1_km = reference_distance_km
            source_note = f"User-provided: {d1_km} km in {reference_time}"

        # ── Run predictions ───────────────────────────────────────────────────
        try:
            predictions = predict_race_times(t1_s, d1_km, mode=mode)
        except ValueError as e:
            return f"Error: {e}"

        # ── Confidence flag ───────────────────────────────────────────────────
        confidence_warnings = [
            p["distance_label"] for p in predictions if p["distance_km"] > d1_km * 3
        ]

        # ── Format output ─────────────────────────────────────────────────────
        result = {
            "reference": source_note,
            "mode": mode,
            "exponent": predictions[0]["exponent_used"] if predictions else None,
            "predictions": [
                {
                    "distance": p["distance_label"],
                    "predicted_time": _fmt_seconds(p["predicted_seconds"]),
                    "pace_per_km": p["predicted_pace_formatted"],
                }
                for p in predictions
            ],
        }
        if confidence_warnings:
            result["confidence_note"] = (
                f"Predictions for {', '.join(confidence_warnings)} are >3× the reference "
                "distance — treat as rough estimates only."
            )

        return json.dumps(result, indent=2)

    # ── Plan Compliance ────────────────────────────────────────────────────────

    @mcp.tool()
    def get_plan_compliance(plan_id: int = 0) -> str:
        """
        Plan compliance report: planned vs actual TSS, session completion rate.

        Compares training events (planned sessions) in the active plan against
        recorded activities. Only sessions on or before today count toward the
        compliance percentage — future sessions are shown in totals but not
        penalised.

        plan_id: optional plan ID to query a specific plan (0 = active plan).

        Returns:
          - overall: sessions_planned/completed, planned_tss, actual_tss,
                     compliance_pct (actual/past_planned × 100)
          - weekly: same metrics broken down by ISO week (sorted chronologically)
        """
        from ..plan_compliance import get_plan_compliance_tool

        pid = plan_id if plan_id > 0 else None
        return get_plan_compliance_tool(plan_id=pid)

    # ── VO2max Estimation ──────────────────────────────────────────────────────

    @mcp.tool()
    def get_vo2max_estimate() -> str:
        """
        Estimate VO2max from athlete config (athlete.yaml).

        Uses whichever thresholds are set:
        - rftp (sec/km)     → ACSM formula via vVO2max
        - ftp + weight_kg   → Coggan formula from W/kg

        Both methods produce medium-confidence estimates (±5–10%).
        Lab testing (CPET or Cooper/Balke field test) gives higher accuracy.

        Returns estimates per method, a consensus average, and interpretation.
        """
        from ..config import load_athlete

        athlete = load_athlete()
        result = estimate_vo2max_from_athlete(athlete)
        return json.dumps(result, indent=2)
