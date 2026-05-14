"""Fitness metrics tools: CTL/ATL/TSB, ACWR, session TSS estimate, VO2max, zone distribution, weekly summary."""

from __future__ import annotations

import json
from datetime import date, timedelta
from itertools import groupby

from ..db import get_conn
from ..metrics import (
    compute_acwr,
    compute_efficiency_factor_trend,
    compute_best_efforts,
    fit_critical_power,
    project_fitness,
    project_fitness_split,
    compute_intensity_distribution,
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

    # ── Efficiency Factor Trend ────────────────────────────────────────────────

    @mcp.tool()
    def get_efficiency_factor_trend(sport: str = "all", weeks: int = 16) -> str:
        """
        Aerobic Efficiency Factor (EF) trend over the last N weeks.

        EF measures aerobic output per unit of cardiac strain:
          - Cycling: EF = normalised power (W) ÷ avg HR
          - Running: EF = NGP (m/s) ÷ avg HR

        Only aerobic sessions are included (IF < 0.85; sessions ≥ 45min).
        A rising EF trend = improving aerobic economy / fitness adaptation.

        Sport filter: 'all', 'run', or 'ride'.
        weeks: history window (default 16 — enough to see a training block trend).

        Returns per-session EF values, a 4-week rolling mean, and a trend
        summary (rising / stable / declining with % change).

        Sources: Allen & Coggan "Training and Racing with a Power Meter" (2010);
        Friel "The Cyclist's Training Bible" (2009).
        """
        weeks = max(4, min(weeks, 104))
        with get_conn() as conn:
            entries = compute_efficiency_factor_trend(conn, sport=sport, weeks=weeks)

        if not entries:
            return "No aerobic sessions with HR + power/pace data found in this period."

        # Peel off the summary entry
        summary = None
        if entries and entries[-1].get("__summary__"):
            summary = entries[-1]
            sessions = entries[:-1]
        else:
            sessions = entries

        result: dict = {"sessions": sessions}

        if sport == "all":
            # Present per-sport summaries as top-level keys for clarity.
            # Mixed-scale rolling mean (W/bpm vs m·s⁻¹/bpm) is meaningless — suppress it.
            by_sport = (summary or {}).get("by_sport", {})
            result["run"] = by_sport.get("run")
            result["ride"] = by_sport.get("ride")
            result["note"] = (summary or {}).get("note", "")
            result["sessions_analysed"] = (summary or {}).get("sessions_analysed", len(sessions))
        else:
            result["summary"] = summary

        return json.dumps(result, indent=2, default=str)

    # ── Best Efforts ───────────────────────────────────────────────────────────

    @mcp.tool()
    def get_best_efforts(sport: str = "all") -> str:
        """
        Personal best efforts across standard distances (running) and power
        durations (cycling).

        Running — fastest average pace in distance brackets:
          1km, 5km, 10km, Half Marathon, Marathon

        Cycling — best mean power over standard durations (from cached streams):
          5s, 30s, 1min, 5min, 20min, 60min
          W/kg shown where body weight is set in athlete.yaml.

        Each effort shows:
          - all_time: best ever value + date
          - season:   best in last 365 days
          - stale:    True if all-time best is >12 months old (retest suggested)

        Cycling power bests are computed from cached activity streams and
        written to the best_efforts table for fast repeated calls.
        Run best_efforts table when new activities are synced.

        Sources: Coggan "Power Profiling" (2003/2010);
        Péronnet & Thibault (1989).
        """
        with get_conn() as conn:
            result = compute_best_efforts(conn)

        if sport == "run":
            result.pop("ride", None)
        elif sport == "ride":
            result.pop("run", None)

        return json.dumps(result, indent=2, default=str)

    # ── Critical Power ─────────────────────────────────────────────────────────

    @mcp.tool()
    def get_critical_power() -> str:
        """
        Estimate Critical Power (CP) and anaerobic work capacity (W') from the
        athlete's mean maximal power curve.

        CP is the highest power output that can be sustained aerobically over a
        long duration. W' (pronounced "W-prime") is the finite anaerobic energy
        reserve above CP — depleted during hard efforts, replenished below CP.

        Model
        -----
        Fits the 2-parameter hyperbolic model ``P(t) = CP + W'/t`` linearised as
        ``E(t) = W' + CP × t`` (total work vs duration) via ordinary least squares.
        Uses MMP durations ≥ 1 min (power_1min through power_60min).
        The 5s and 30s durations are excluded — they are neuromuscular/anaerobic
        and would inflate W' artificially.

        Requires ≥ 3 cached power stream best efforts to produce a fit.
        Run ``get_best_efforts`` or sync activities first if the result is empty.

        Returns
        -------
        - all_time : CP/W' from all-time MMP bests
        - season   : CP/W' from last-365-day MMP bests (None if insufficient)
        - ftp_comparison : CP vs athlete FTP ratio + coaching note
        - r_squared : model fit quality (≥0.95 = excellent; <0.90 = check max efforts)
        - out_of_range : True if values fall outside physiological norms

        Sources
        -------
        Morton (1996) J Sports Sci 14(6):491–514;
        Monod & Scherrer (1965);
        Coggan (2003/2010) Power Profiling.
        """
        from ..config import load_athlete

        with get_conn() as conn:
            best_efforts = compute_best_efforts(conn)

        athlete = load_athlete()
        ftp = athlete.get("ftp")

        ride_efforts = best_efforts.get("ride", [])
        cp_result = fit_critical_power(ride_efforts, ftp=ftp)

        if cp_result is None:
            return json.dumps(
                {
                    "error": (
                        "Insufficient MMP data to fit CP model. "
                        f"Need ≥{3} power duration bests (power_1min through power_60min). "
                        "Sync activities with power data and ensure activity streams are cached."
                    ),
                    "mmp_points_available": len(
                        [e for e in ride_efforts if e.get("all_time", {}).get("value_raw")]
                    ),
                },
                indent=2,
            )

        return json.dumps(cp_result, indent=2, default=str)

    # ── Fitness Projection ─────────────────────────────────────────────────────

    @mcp.tool()
    def get_projected_fitness(
        target_date: str,
        weekly_tss: float = 0.0,
        taper_weeks: int = 3,
        sport: str = "all",
        split: bool = False,
    ) -> str:
        """
        Project CTL/ATL/TSB forward to a target race date.

        Models a standard taper: full load maintained until taper_weeks before
        the race, then load reduced by ~30% per week (taper_factor=0.70).

        Parameters
        ----------
        target_date : race date in YYYY-MM-DD format
        weekly_tss  : assumed weekly TSS going forward.
                      0 = auto-detect from last 4-week average.
        taper_weeks : weeks of taper before race (default 3; use 2 for B/C races)
        sport       : 'all', 'run', or 'ride' — affects load history used.
                      Ignored when split=True (all three are returned).
        split       : if True and sport='all', returns three parallel projections:
                      combined / run / ride — each with independent CTL history
                      and auto-detected weekly TSS. Useful for sport-specific
                      race preparation (e.g. run-CTL for a half marathon).

        Returns
        -------
        - current CTL/ATL/TSB today
        - projected CTL/ATL/TSB on race day
        - taper_start_date
        - form_status: optimal (+10 to +25 TSB) / under-tapered / over-tapered
        - recommendation: actionable coaching text
        - daily_series: last 4 weeks history + projected forward (for charting)

        Sources: Banister et al. (1975); Mujika & Padilla (2003) Med Sci Sports
        Exerc 35(7); Coggan (2003) TSB +15 to +25 optimal window.
        """
        try:
            from datetime import date as _date

            td = _date.fromisoformat(target_date)
        except ValueError:
            return f"Error: target_date must be YYYY-MM-DD, got '{target_date}'."

        taper_weeks = max(1, min(taper_weeks, 8))

        if split and sport == "all":
            with get_conn() as conn:
                result = project_fitness_split(
                    conn=conn,
                    target_date=td,
                    weekly_tss=weekly_tss if weekly_tss > 0 else None,
                    taper_weeks=taper_weeks,
                )
            return json.dumps(result, indent=2, default=str)

        with get_conn() as conn:
            daily_tss = get_daily_tss_from_db(conn, sport)

        if not daily_tss:
            return "No TSS data found. Run sync_activities first."

        result = project_fitness(
            daily_tss=daily_tss,
            target_date=td,
            weekly_tss=weekly_tss if weekly_tss > 0 else None,
            taper_weeks=taper_weeks,
            sport_label=sport,
        )
        return json.dumps(result, indent=2, default=str)

    # ── Intensity Distribution (Seiler tripartite model) ──────────────────────

    @mcp.tool()
    def get_intensity_distribution(weeks: int = 8, sport: str = "all") -> str:
        """
        Tripartite intensity distribution over the last N weeks (Seiler model).

        Bins training time with HR data into three physiological zones:
          Easy     — below LT1 (< 72% HRR) — aerobic base work
          Moderate — LT1 to LT2 (72–82% HRR) — the metabolic 'no-man's land'
          Hard     — above LT2 (> 82% HRR) — threshold and VO2max work

        LT1 and LT2 are derived from threshold_hr and resting_hr in athlete.yaml.

        Classifies the current distribution as:
          polarized     : ~80% easy, <10% moderate, ~15% hard
          pyramidal     : ~70% easy, ~20% moderate, ~10% hard
          threshold-heavy : >30% moderate (common issue for amateur athletes)

        Includes gap analysis vs polarized target and an actionable interpretation.

        sport : 'all' (default) — returns nested overall / run / ride breakdown.
                'run' or 'ride' — returns a flat result for that sport only.

        Note: uses session average HR as a proxy — polarized sessions (long easy
        + short hard intervals) will appear shifted toward moderate. Use
        get_activity_streams on key sessions for second-by-second precision.

        Sources: Seiler & Tønnessen (2009) Sportscience 13; Seiler (2010)
        Int J Sports Physiol Perform 5(3); Stoggl & Sperlich (2014) Front Physiol.
        """
        weeks = max(1, min(weeks, 104))
        with get_conn() as conn:
            result = compute_intensity_distribution(conn, weeks=weeks, sport=sport)
        return json.dumps(result, indent=2)
