"""
Metrics engine.

Computes:
  - TSS  (Training Stress Score) for cycling (power-based) and running (pace-based)
  - hrTSS (HR-based TSS) as fallback for any sport
  - NP   (Normalised Power, cycling)
  - IF   (Intensity Factor, cycling)
  - NGP  (Normalised Graded Pace, running)
  - CTL  (Chronic Training Load, 42-day EMA)
  - ATL  (Acute Training Load, 7-day EMA)
  - TSB  (Form = CTL − ATL)
  - Zone distributions (power zones, pace zones, HR zones)
  - Grade Adjusted Pace

## NGP algorithm

NGP (Normalised Graded Pace) converts actual pace on hilly terrain to an
equivalent flat pace representing the same physiological effort.

### Cost function
Minetti et al. (2002) polynomial energy cost model (J/kg/m):
  C(g) = 155.4g⁵ − 30.4g⁴ − 43.3g³ + 46.3g² + 19.5g + 3.6
where g is grade as a fraction (0.1 = 10% incline).  C(0) = 3.6.

NGP factor = C(g) / C(0): values >1 mean the effort is harder than flat.

### Grade approximation (summary-level)
Strava activity summaries provide total_elevation_gain but NOT elevation_loss.
Using net grade = gain / distance (always ≥ 0) systematically over-inflates NGP
for any loop or out-and-back route where gain ≈ loss.

Correct approach for summary data: symmetric half-grade model.
Assume the route is composed of two equal halves — one ascending, one descending —
each with absolute grade = 2 × gain / distance.  Average the Minetti factors:

  half_grade  = 2 × gain / distance          (clamped to ±0.45)
  ngp_factor  = ( C(+half_grade) + C(−half_grade) ) / ( 2 × C(0) )
  NGP         = actual_speed × ngp_factor

For a flat route (gain=0): ngp_factor = 1.0 (no adjustment).
For a typical 500m gain / 20km loop: ngp_factor ≈ 1.032 (+3.2%), vs 1.143
(+14.3%) with the naive net-grade formula.

Limitation: for strongly net-uphill or net-downhill point-to-point routes the
symmetric assumption underestimates or overestimates the grade effect.  A future
improvement is to use per-point altitude streams from activity_streams when
available (30s rolling NP-style 4th-power average — Coggan & Allen).
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from typing import Any

# ── Constants ─────────────────────────────────────────────────────────────────

CTL_DAYS = 42
ATL_DAYS = 7


# ── Activity-level metrics ────────────────────────────────────────────────────


def compute_activity_metrics(activity: dict, streams: dict | None = None) -> dict:
    """
    Return a dict of computed metrics ready to store alongside the raw activity.
    Falls back gracefully when data is missing.
    """
    sport = (activity.get("sport_type") or activity.get("type", "")).lower()
    moving_time = activity.get("moving_time") or 0  # seconds
    hours = moving_time / 3600

    result: dict[str, float | None] = {
        "tss": None,
        "np": None,
        "intensity_factor": None,
        "hrss": None,
        "rtss": None,
        "ngp": None,
        "rtss_power": None,
    }

    # Load athlete config once for all metric calculations
    from .config import load_athlete

    athlete = load_athlete()

    # ── Cycling: power-based TSS ──────────────────────────────────────────────
    # Strava API uses "weighted_average_watts"; normalise to short form
    if "weighted_average_watts" in activity and "weighted_avg_watts" not in activity:
        activity["weighted_avg_watts"] = activity["weighted_average_watts"]

    if "ride" in sport and activity.get("weighted_avg_watts") and activity.get("average_watts"):
        ftp = athlete.get("ftp")
        if ftp and ftp > 0:
            np = float(activity["weighted_avg_watts"])
            intensity_factor = np / ftp
            tss = (moving_time * np * intensity_factor) / (ftp * 3600) * 100
            result["np"] = round(np, 1)
            result["intensity_factor"] = round(intensity_factor, 3)
            result["tss"] = round(tss, 1)

    # ── Running: pace-based rTSS ──────────────────────────────────────────────
    if "run" in sport and activity.get("average_speed") and moving_time > 0:
        rftp_sec_per_km = athlete.get("rftp")  # sec/km threshold pace
        if rftp_sec_per_km and rftp_sec_per_km > 0:
            # NGP: grade-adjusted pace using elevation data
            distance_m = activity.get("distance") or 0
            elev_gain = activity.get("total_elevation_gain") or 0
            avg_speed_ms = activity["average_speed"]  # m/s

            if distance_m > 0:
                # Symmetric grade approximation:
                # Strava summary only provides total_elevation_gain, not loss.
                # For typical training runs (loops / out-and-backs) gain ≈ loss,
                # so we model the route as two equal halves:
                #   • ascending half: grade = +2*gain/distance
                #   • descending half: grade = −2*gain/distance
                # The average Minetti cost factor correctly captures the energy
                # asymmetry (climbs cost more than flat; descents cost less but
                # not symmetrically).  Using raw gain/distance as a single net
                # grade over-inflates NGP for loops (all uphill bias).
                half_grade = min((elev_gain * 2) / distance_m, 0.45)
                ngp_factor = (_grade_cost_factor(half_grade) + _grade_cost_factor(-half_grade)) / 2
                ngp_ms = avg_speed_ms * ngp_factor
                ngp_sec_per_km = 1000 / ngp_ms if ngp_ms > 0 else None

                if ngp_sec_per_km:
                    rftp_ms = 1000 / rftp_sec_per_km
                    ri = ngp_ms / rftp_ms  # running intensity
                    rtss = (moving_time * ngp_ms * ri) / (rftp_ms * 3600) * 100
                    result["ngp"] = round(ngp_ms, 4)
                    result["rtss"] = round(rtss, 1)
                    if not result["tss"]:
                        result["tss"] = round(rtss, 1)

    # ── Running: power-based rTSS (parallel metric, Coggan formula) ──────────
    # Uses device-recorded running power (average_watts / weighted_average_watts).
    # Identical formula to cycling TSS: (duration_s × NP × IF) / (rFTP_W × 3600) × 100
    # rFTP_W = athlete.rftp_watts (95% of best 20-min run power).
    # Stored as rtss_power alongside pace-based rtss; tss column uses pace-based
    # rTSS as primary (more widely validated) — rtss_power is a supplementary metric.
    if "run" in sport and moving_time > 0:
        rftp_watts = athlete.get("rftp_watts")
        # Prefer weighted_average_watts (NP proxy) over average_watts
        run_np = activity.get("weighted_average_watts") or activity.get("weighted_avg_watts") or activity.get("average_watts")
        if rftp_watts and rftp_watts > 0 and run_np and run_np > 0:
            run_np = float(run_np)
            run_if = run_np / rftp_watts
            rtss_power = (moving_time * run_np * run_if) / (rftp_watts * 3600) * 100
            result["rtss_power"] = round(rtss_power, 1)

    # ── HR-based TSS (fallback for any sport) ────────────────────────────────
    avg_hr = activity.get("average_heartrate")
    if avg_hr and moving_time > 0:
        threshold_hr = athlete.get("threshold_hr")
        resting_hr = athlete.get("resting_hr", 50)
        if threshold_hr and threshold_hr > 0:
            # Banister hrTSS
            hrr_ratio = (avg_hr - resting_hr) / (threshold_hr - resting_hr)
            hrr_ratio = max(0.0, min(hrr_ratio, 1.5))
            # Trimp multiplier (gender-neutral approximation)
            trimp_factor = 0.64 * math.exp(1.92 * hrr_ratio)
            hrss = (moving_time / 60) * hrr_ratio * trimp_factor
            result["hrss"] = round(hrss, 1)
            # Use hrTSS if no power/pace TSS computed
            if not result["tss"]:
                result["tss"] = round(hrss, 1)

    return result


def _grade_cost_factor(grade: float) -> float:
    """
    Energy cost ratio relative to flat running, based on Minetti et al. (2002).
    grade is fractional (e.g. 0.1 = 10% incline, −0.1 = 10% decline).
    Returns C(grade) / C(0):
      >1 → terrain is harder than flat (uphill or very steep downhill)
      <1 → terrain is easier than flat (moderate downhill)
    Multiply actual speed by this factor to get equivalent flat speed (NGP).
    Input is clamped to [−0.45, +0.45] (Minetti validity range).
    """
    g = max(-0.45, min(0.45, grade))
    # Minetti polynomial (positive = uphill, slows you down → factor > 1)
    cost = 155.4 * g**5 - 30.4 * g**4 - 43.3 * g**3 + 46.3 * g**2 + 19.5 * g + 3.6
    flat_cost = 3.6  # J/kg/m at 0% grade
    return cost / flat_cost


def pace_sec_per_km(speed_ms: float) -> float:
    """Convert m/s to sec/km."""
    if speed_ms <= 0:
        return 0.0
    return 1000 / speed_ms


def format_pace(sec_per_km: float) -> str:
    """Format sec/km as MM'SS\"/km."""
    mins = int(sec_per_km // 60)
    secs = int(sec_per_km % 60)
    return f"{mins}'{secs:02d}\""


# ── Fitness model: CTL / ATL / TSB ───────────────────────────────────────────


def compute_fitness_series(
    daily_tss: dict[date, float],
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict]:
    """
    Compute CTL/ATL/TSB for every day in the range.

    daily_tss: {date: tss_value}
    Returns list of dicts: {date, ctl, atl, tsb}
    """
    if not daily_tss:
        return []

    all_dates = sorted(daily_tss.keys())
    start = start_date or all_dates[0]
    end = end_date or date.today()

    ctl_k = 1 - math.exp(-1 / CTL_DAYS)
    atl_k = 1 - math.exp(-1 / ATL_DAYS)

    ctl = 0.0
    atl = 0.0
    results = []
    current = start
    while current <= end:
        tss = daily_tss.get(current, 0.0)
        ctl = ctl + ctl_k * (tss - ctl)
        atl = atl + atl_k * (tss - atl)
        tsb = ctl - atl
        results.append(
            {
                "date": current.isoformat(),
                "ctl": round(ctl, 1),
                "atl": round(atl, 1),
                "tsb": round(tsb, 1),
                "tss": tss,
            }
        )
        current += timedelta(days=1)

    return results


def get_daily_tss_from_db(conn, sport_category: str = "all") -> dict[date, float]:
    """
    Load daily TSS from the DB, optionally filtered by sport category.

    TSS is computed deterministically at sync time from Strava data:
      - Cycling with power meter → Coggan power-based TSS
      - Running → rTSS via NGP/Minetti grade-adjusted pace
      - Any sport with HR → Banister hrTSS (fallback)

    Only activities with a non-NULL tss value are included.
    """
    _SPORT_SQL: dict[str, tuple[str, list]] = {
        "all": ("WHERE tss IS NOT NULL", []),
        "run": (
            "WHERE tss IS NOT NULL AND (sport_type LIKE ? OR sport_type LIKE ?)",
            ["%Run%", "%Trail%"],
        ),
        "ride": ("WHERE tss IS NOT NULL AND sport_type LIKE ?", ["%Ride%"]),
    }
    if sport_category not in _SPORT_SQL:
        raise ValueError(
            f"Unknown sport_category {sport_category!r}; expected 'all', 'run', or 'ride'"
        )
    where_clause, params = _SPORT_SQL[sport_category]

    rows = conn.execute(
        f"""
        SELECT date(start_date) as day, SUM(tss) as daily_tss
        FROM activities
        {where_clause}
        GROUP BY day
        ORDER BY day
    """,
        params,
    ).fetchall()

    return {date.fromisoformat(row["day"]): float(row["daily_tss"]) for row in rows}


def get_current_fitness(conn, sport_category: str = "all") -> dict:
    """Return today's CTL/ATL/TSB snapshot."""
    daily_tss = get_daily_tss_from_db(conn, sport_category)
    if not daily_tss:
        return {"ctl": 0, "atl": 0, "tsb": 0, "date": date.today().isoformat()}
    series = compute_fitness_series(daily_tss)
    return series[-1] if series else {"ctl": 0, "atl": 0, "tsb": 0}


# ── Zone distributions ────────────────────────────────────────────────────────


def hr_zones(threshold_hr: int, resting_hr: int = 50) -> dict[str, tuple[int, int]]:
    """5-zone HR model based on threshold HR."""
    hrr = threshold_hr - resting_hr
    return {
        "Z1": (resting_hr, int(resting_hr + 0.60 * hrr)),
        "Z2": (int(resting_hr + 0.60 * hrr), int(resting_hr + 0.72 * hrr)),
        "Z3": (int(resting_hr + 0.72 * hrr), int(resting_hr + 0.82 * hrr)),
        "Z4": (int(resting_hr + 0.82 * hrr), int(resting_hr + 0.92 * hrr)),
        "Z5": (int(resting_hr + 0.92 * hrr), 999),
    }


def power_zones(ftp: int) -> dict[str, tuple[int, int]]:
    """Coggan 7-zone power model."""
    return {
        "Z1_Active_Recovery": (0, int(0.55 * ftp)),
        "Z2_Endurance": (int(0.55 * ftp), int(0.75 * ftp)),
        "Z3_Tempo": (int(0.75 * ftp), int(0.90 * ftp)),
        "Z4_Threshold": (int(0.90 * ftp), int(1.05 * ftp)),
        "Z5_VO2max": (int(1.05 * ftp), int(1.20 * ftp)),
        "Z6_Anaerobic": (int(1.20 * ftp), int(1.50 * ftp)),
        "Z7_Neuromuscular": (int(1.50 * ftp), 9999),
    }


def pace_zones(rftp_sec_per_km: float) -> dict[str, tuple[float, float]]:
    """Running pace zones based on threshold pace (sec/km)."""
    # Faster pace = lower sec/km number, so zones are inverted
    return {
        "Z1_Easy": (rftp_sec_per_km * 1.30, rftp_sec_per_km * 1.60),
        "Z2_Aerobic": (rftp_sec_per_km * 1.15, rftp_sec_per_km * 1.30),
        "Z3_Tempo": (rftp_sec_per_km * 1.05, rftp_sec_per_km * 1.15),
        "Z4_Threshold": (rftp_sec_per_km * 0.97, rftp_sec_per_km * 1.05),
        "Z5_VO2max": (rftp_sec_per_km * 0.88, rftp_sec_per_km * 0.97),
        "Z6_Anaerobic": (0, rftp_sec_per_km * 0.88),
    }


def get_zone_distribution_from_db(conn, weeks: int = 8) -> dict:
    """
    Summarise zone distribution over last N weeks using avg HR as proxy.
    Returns counts per zone and polarization ratio (Z1+Z2 vs Z4+Z5).
    """
    from .config import load_athlete

    athlete = load_athlete()
    threshold_hr = athlete.get("threshold_hr", 175)
    resting_hr = athlete.get("resting_hr", 50)
    zones = hr_zones(threshold_hr, resting_hr)

    cutoff = (date.today() - timedelta(weeks=weeks)).isoformat()
    rows = conn.execute(
        """
        SELECT average_heartrate, moving_time, sport_type
        FROM activities
        WHERE start_date >= ? AND average_heartrate IS NOT NULL AND moving_time > 0
        ORDER BY start_date
    """,
        (cutoff,),
    ).fetchall()

    zone_time: dict[str, float] = {z: 0.0 for z in zones}
    total_time = 0.0

    for row in rows:
        hr = row["average_heartrate"]
        mins = row["moving_time"] / 60
        for zone, (lo, hi) in zones.items():
            if lo <= hr < hi:
                zone_time[zone] += mins
                break
        total_time += mins

    if total_time == 0:
        return {"error": "No activities with HR data in this period."}

    pct = {z: round(t / total_time * 100, 1) for z, t in zone_time.items()}
    low_intensity = pct.get("Z1", 0) + pct.get("Z2", 0)
    high_intensity = pct.get("Z4", 0) + pct.get("Z5", 0)
    polarization_index = round(low_intensity / max(high_intensity, 0.1), 2)

    return {
        "weeks_analysed": weeks,
        "total_hours": round(total_time / 60, 1),
        "zone_pct": pct,
        "zone_hours": {z: round(t / 60, 1) for z, t in zone_time.items()},
        "low_intensity_pct": low_intensity,
        "high_intensity_pct": high_intensity,
        "polarization_index": polarization_index,
        "interpretation": _polarization_comment(polarization_index),
    }


def _polarization_comment(pi: float) -> str:
    if pi > 3.0:
        return "Very polarized — heavy Z1/Z2 base with little threshold work."
    if pi > 1.5:
        return "Polarized distribution — healthy aerobic base with targeted intensity."
    if pi > 0.8:
        return "Pyramidal distribution — balanced mix across zones."
    return "Threshold-heavy — significant Z3/Z4 volume; monitor fatigue closely."


# ── Training Monotony & Training Strain ──────────────────────────────────────


def compute_training_monotony(daily_tss: dict[date, float], window: int = 7) -> list[dict]:
    """
    Compute rolling Training Monotony and Training Strain for each day.

    Training Monotony (Foster 1998):
        monotony = mean(daily_tss) / stdev(daily_tss)
        where mean and stdev are computed over the rolling `window` days ending on that day.

    Stable variant (bounded 0.29–1.0):
        stable_monotony = mean / (mean + stdev)

    Training Strain:
        strain = sum(window TSS) × monotony

    Thresholds:
        monotony > 2.0  → too high (injury/illness risk)
        monotony < 1.5  → preferable (varied stimulus)

    Returns list of dicts: {date, monotony, stable_monotony, strain, window_tss_sum}
    """
    if not daily_tss:
        return []

    all_dates = sorted(daily_tss.keys())
    start = all_dates[0]
    end = date.today()

    results = []
    current = start
    while current <= end:
        # Collect TSS values for the rolling window ending on `current`
        window_values = []
        for i in range(window):
            d = current - timedelta(days=window - 1 - i)
            window_values.append(daily_tss.get(d, 0.0))

        n = len(window_values)
        mean_tss = sum(window_values) / n
        variance = sum((x - mean_tss) ** 2 for x in window_values) / n
        stdev_tss = math.sqrt(variance)

        # Foster monotony: avoid division by zero
        if stdev_tss > 0:
            monotony = mean_tss / stdev_tss
        else:
            # All days identical → perfectly monotonous; cap at 4.0
            monotony = 4.0 if mean_tss > 0 else 0.0

        # Stable variant: bounded [0, 1], avoids infinity
        denom = mean_tss + stdev_tss
        stable_monotony = (mean_tss / denom) if denom > 0 else 0.0

        window_sum = sum(window_values)
        strain = window_sum * monotony

        results.append(
            {
                "date": current.isoformat(),
                "monotony": round(monotony, 2),
                "stable_monotony": round(stable_monotony, 3),
                "strain": round(strain, 1),
                "window_tss_sum": round(window_sum, 1),
            }
        )
        current += timedelta(days=1)

    return results


def get_training_monotony_from_db(conn, sport_category: str = "all", window: int = 7) -> list[dict]:
    """
    Load daily TSS from DB and compute rolling Training Monotony + Strain.
    Returns list of dicts for the last 90 days (suitable for dashboard chart).
    """
    daily_tss = get_daily_tss_from_db(conn, sport_category)
    series = compute_training_monotony(daily_tss, window=window)
    # Return only last 90 days for dashboard
    cutoff = (date.today() - timedelta(days=90)).isoformat()
    return [r for r in series if r["date"] >= cutoff]


def get_current_monotony_snapshot(conn, sport_category: str = "all", window: int = 7) -> dict:
    """Return today's Training Monotony and Strain snapshot."""
    daily_tss = get_daily_tss_from_db(conn, sport_category)
    series = compute_training_monotony(daily_tss, window=window)
    if not series:
        return {"monotony": 0.0, "stable_monotony": 0.0, "strain": 0.0, "window_tss_sum": 0.0}
    today_str = date.today().isoformat()
    # Find today's entry or last available
    for entry in reversed(series):
        if entry["date"] <= today_str:
            return entry
    return series[-1]
