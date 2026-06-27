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

import json
import math
from datetime import date, datetime, timedelta
from typing import Any

# ── Constants ─────────────────────────────────────────────────────────────────

CTL_DAYS = 42
ATL_DAYS = 7


# ── Activity-level metrics ────────────────────────────────────────────────────


def compute_activity_metrics(
    activity: dict,
    streams: dict | None = None,
    athlete: dict | None = None,
) -> dict:
    """
    Return a dict of computed metrics ready to store alongside the raw activity.
    Falls back gracefully when data is missing.

    Parameters
    ----------
    activity : dict
        Raw Strava activity fields.
    streams : dict | None
        Optional pre-fetched activity streams (unused in summary-level path).
    athlete : dict | None
        Athlete config dict (from ``load_athlete()``). If None, loaded from disk.
        Pass the dict explicitly when calling in a batch (e.g. sync) to avoid
        re-reading the YAML file for every activity.
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

    # Load athlete config once — injected by caller when batch-processing.
    if athlete is None:
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

    # ── Cycling: average_watts fallback (no NP recorded) ─────────────────────
    # When Strava does not return weighted_average_watts (e.g. incomplete power
    # file, sensor dropout), fall back to average_watts.  average_watts-based
    # TSS under-estimates true TSS for variable-effort rides (no variability
    # penalty) but is substantially better than NULL for load-tracking purposes.
    # This branch is preferred over hrTSS for cycling (power is more reliable
    # than HR for estimating training load on the bike).
    if "ride" in sport and not result["tss"] and activity.get("average_watts"):
        ftp = athlete.get("ftp")
        if ftp and ftp > 0:
            avg_w = float(activity["average_watts"])
            if avg_w > 0:
                intensity_factor = avg_w / ftp
                tss = (moving_time * avg_w * intensity_factor) / (ftp * 3600) * 100
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
                    # For road/track runs: pace-based rTSS is primary (Minetti accurate on flat)
                    # For trail runs: defer to rtss_power if available (computed below);
                    # fall back to rtss if power not available.
                    is_trail = "trail" in sport
                    if not result["tss"] and not is_trail:
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
        run_np = (
            activity.get("weighted_average_watts")
            or activity.get("weighted_avg_watts")
            or activity.get("average_watts")
        )
        if rftp_watts and rftp_watts > 0 and run_np and run_np > 0:
            run_np = float(run_np)
            run_if = run_np / rftp_watts
            rtss_power = (moving_time * run_np * run_if) / (rftp_watts * 3600) * 100
            result["rtss_power"] = round(rtss_power, 1)
            # Trail runs: use power-based TSS as primary (more accurate on variable terrain)
            if "trail" in sport and not result["tss"]:
                result["tss"] = round(rtss_power, 1)

    # ── HR-based TSS (fallback for any sport) ────────────────────────────────
    avg_hr = activity.get("average_heartrate")
    if avg_hr and moving_time > 0:
        max_hr = athlete.get("max_hr")
        threshold_hr = athlete.get("threshold_hr")
        resting_hr = athlete.get("resting_hr", 50)
        # Banister TRIMP uses HRmax for HRR; fall back to threshold_hr if unavailable
        hr_ceiling = max_hr or threshold_hr
        if hr_ceiling and hr_ceiling > resting_hr:
            # Banister hrTSS — HRR as fraction of heart rate reserve
            hrr_ratio = (avg_hr - resting_hr) / (hr_ceiling - resting_hr)
            hrr_ratio = max(0.0, min(hrr_ratio, 1.5))
            # Trimp multiplier — gender-specific Banister coefficients:
            #   male=1.92, female=1.67 (Banister 1975); neutral midpoint=1.80
            _BANISTER_K = {"male": 1.92, "female": 1.67, "neutral": 1.80}
            gender = (athlete.get("gender") or "neutral").lower()
            banister_k = _BANISTER_K.get(gender, 1.80)
            trimp_factor = 0.64 * math.exp(banister_k * hrr_ratio)
            hrss_raw = (moving_time / 60) * hrr_ratio * trimp_factor

            # Normalize so that 1 hour at threshold HR = 100 hrTSS
            _thr_hr_ref = threshold_hr
            if not _thr_hr_ref and hr_ceiling:
                # Estimate LTHR as 85% of heart rate reserve (Karvonen)
                _thr_hr_ref = resting_hr + 0.85 * (hr_ceiling - resting_hr)
                result["hrss_threshold_estimated"] = True
            ref_hrr = (_thr_hr_ref - resting_hr) / (hr_ceiling - resting_hr)
            ref_trimp_factor = 0.64 * math.exp(banister_k * ref_hrr)
            ref_trimp = 60 * ref_hrr * ref_trimp_factor  # 1hr at LTHR
            hrss = (hrss_raw / ref_trimp) * 100 if ref_trimp > 0 else hrss_raw

            result["hrss"] = round(hrss, 1)
            # Use hrTSS if no power/pace TSS computed
            if not result["tss"]:
                result["tss"] = round(hrss, 1)

    # Trail run fallback: if power unavailable, use pace-based rtss
    if (
        "trail" in (activity.get("sport_type") or "").lower()
        and not result["tss"]
        and result["rtss"]
    ):
        result["tss"] = result["rtss"]

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
      - Cycling with average_watts only → average_watts-based TSS (fallback)
      - Running → rTSS via NGP/Minetti grade-adjusted pace
      - Any sport with HR → Banister hrTSS (fallback)

    ``activity_overrides.tss_override`` takes priority over the computed
    ``activities.tss`` column when set, allowing manual corrections for
    activities that lack power/HR data.

    Only activities with a non-NULL effective TSS (override or computed) are included.
    """
    _SPORT_SQL: dict[str, tuple[str, list]] = {
        "all": ("WHERE COALESCE(o.tss_override, a.tss) IS NOT NULL", []),
        "run": (
            "WHERE COALESCE(o.tss_override, a.tss) IS NOT NULL AND (a.sport_type LIKE ? OR a.sport_type LIKE ?)",
            ["%Run%", "%Trail%"],
        ),
        "ride": (
            "WHERE COALESCE(o.tss_override, a.tss) IS NOT NULL AND a.sport_type LIKE ?",
            ["%Ride%"],
        ),
    }
    if sport_category not in _SPORT_SQL:
        raise ValueError(
            f"Unknown sport_category {sport_category!r}; expected 'all', 'run', or 'ride'"
        )
    where_clause, params = _SPORT_SQL[sport_category]

    rows = conn.execute(
        f"""
        SELECT date(a.start_date) as day, SUM(COALESCE(o.tss_override, a.tss)) as daily_tss
        FROM activities a
        LEFT JOIN activity_overrides o ON o.activity_id = a.id
        {where_clause}
        GROUP BY day
        ORDER BY day
    """,
        params,
    ).fetchall()

    daily: dict[date, float] = {
        date.fromisoformat(row["day"]): float(row["daily_tss"]) for row in rows
    }

    # Merge untracked activities into the 'all' category only.
    # Untracked activities don't have a reliable sport classification so we
    # keep sport-specific filters (run/ride) clean and unaffected.
    if sport_category == "all":
        untracked_rows = conn.execute(
            """
            SELECT date(activity_date) as day, SUM(tss_estimate) as daily_tss
            FROM untracked_activities
            WHERE tss_estimate IS NOT NULL
            GROUP BY day
            """
        ).fetchall()
        for row in untracked_rows:
            d = date.fromisoformat(row["day"])
            daily[d] = daily.get(d, 0.0) + float(row["daily_tss"])

    return daily


def get_current_fitness(conn, sport_category: str = "all") -> dict:
    """Return today's CTL/ATL/TSB snapshot."""
    daily_tss = get_daily_tss_from_db(conn, sport_category)
    if not daily_tss:
        return {"ctl": 0, "atl": 0, "tsb": 0, "date": date.today().isoformat()}
    series = compute_fitness_series(daily_tss)
    return series[-1] if series else {"ctl": 0, "atl": 0, "tsb": 0}


# ── Zone distributions ────────────────────────────────────────────────────────


def hr_zones(
    threshold_hr: int,
    resting_hr: int = 50,
    hr_zones_config: dict | None = None,
) -> dict[str, tuple[int, int]]:
    """Return HR zones as {label: (lo, hi)} tuples.

    If *hr_zones_config* is supplied (the ``hr_zones`` dict from athlete.yaml),
    those zones are parsed and returned verbatim.  String ranges may use either
    a hyphen (``-``) or an en-dash (``–``) as separator; the upper bound of the
    last zone is set to 999 when absent.

    Falls back to a computed 5-zone HRR model when no config is provided, for
    backwards compatibility with athletes that have no ``hr_zones:`` block.
    """
    if hr_zones_config:
        result: dict[str, tuple[int, int]] = {}
        keys = list(hr_zones_config.keys())
        for i, key in enumerate(keys):
            raw = str(hr_zones_config[key])
            # normalise en-dash / em-dash to hyphen, then split
            raw = raw.replace("\u2013", "-").replace("\u2014", "-")
            parts = raw.split("-")
            lo = int(parts[0].strip())
            hi = int(parts[1].strip()) if len(parts) > 1 else 999
            result[key] = (lo, hi)
        return result

    # fallback: computed 5-zone HRR model
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


# ── ACWR — Acute:Chronic Workload Ratio ───────────────────────────────────────


def compute_acwr(
    daily_tss: dict[date, float],
    short_days: int = 7,
    long_days: int = 28,
    reference_date: date | None = None,
) -> dict:
    """
    Compute the Acute:Chronic Workload Ratio (ACWR) for a given reference date.

    Two variants are returned:
    - **rolling_average** (Gabbett 2016): simple rolling mean of the acute
      window divided by the rolling mean of the chronic window.
      Sweet-spot 0.8–1.3; >1.5 = high injury-risk flag.
    - **ema** (exponential moving average): uses the existing ATL/CTL EMA
      values (short_days and long_days as time constants) so the result is
      consistent with the fitness model already shown on the dashboard.

    Parameters
    ----------
    daily_tss      : dict mapping date → daily TSS
    short_days     : acute window in days (default 7)
    long_days      : chronic window in days (default 28)
    reference_date : date to compute ACWR for (default: today). Pass a
                     historical date when building the full time-series.

    Returns
    -------
    dict with keys: acwr_rolling, acwr_ema, acute_load, chronic_load,
                    risk_zone, interpretation
    """
    if not daily_tss:
        return {
            "acwr_rolling": None,
            "acwr_ema": None,
            "acute_load": 0.0,
            "chronic_load": 0.0,
            "risk_zone": "unknown",
            "interpretation": "No training data available.",
        }

    ref = reference_date if reference_date is not None else date.today()

    # Rolling-average ACWR
    acute_vals = [daily_tss.get(ref - timedelta(days=i), 0.0) for i in range(short_days)]
    chronic_vals = [daily_tss.get(ref - timedelta(days=i), 0.0) for i in range(long_days)]
    acute_avg = sum(acute_vals) / short_days
    chronic_avg = sum(chronic_vals) / long_days
    acwr_rolling = round(acute_avg / chronic_avg, 3) if chronic_avg > 0 else None

    # EMA-based ACWR: run EMA from earliest available date to ref
    all_dates = sorted(daily_tss.keys())
    start = all_dates[0]
    k_short = 1 - math.exp(-1 / short_days)
    k_long = 1 - math.exp(-1 / long_days)
    ema_short = 0.0
    ema_long = 0.0
    current = start
    while current <= ref:
        tss = daily_tss.get(current, 0.0)
        ema_short = ema_short + k_short * (tss - ema_short)
        ema_long = ema_long + k_long * (tss - ema_long)
        current += timedelta(days=1)
    acwr_ema = round(ema_short / ema_long, 3) if ema_long > 0 else None

    # Use rolling ACWR for risk zone (literature thresholds are based on rolling avg)
    ratio = acwr_rolling
    if ratio is None:
        risk_zone = "unknown"
        interpretation = "Insufficient chronic load to compute ratio."
    elif ratio < 0.8:
        risk_zone = "undertrained"
        interpretation = (
            f"ACWR {ratio:.2f} — below 0.8. Load is low relative to chronic base. "
            "Detraining risk if sustained. Consider a moderate build week."
        )
    elif ratio <= 1.3:
        risk_zone = "optimal"
        interpretation = (
            f"ACWR {ratio:.2f} — sweet spot (0.8–1.3). "
            "Acute load is well-matched to chronic fitness. Training is sustainable."
        )
    elif ratio <= 1.5:
        risk_zone = "caution"
        interpretation = (
            f"ACWR {ratio:.2f} — caution zone (1.3–1.5). "
            "Acute load is elevated relative to chronic base. "
            "Monitor for early fatigue signs; avoid adding more intensity."
        )
    else:
        risk_zone = "high_risk"
        interpretation = (
            f"ACWR {ratio:.2f} — high injury risk (>1.5). "
            "Acute load has spiked significantly above chronic fitness. "
            "Mandatory load reduction this week."
        )

    return {
        "acwr_rolling": acwr_rolling,
        "acwr_ema": acwr_ema,
        "acute_load": round(acute_avg, 1),
        "chronic_load": round(chronic_avg, 1),
        "acute_window_days": short_days,
        "chronic_window_days": long_days,
        "risk_zone": risk_zone,
        "interpretation": interpretation,
    }


def compute_acwr_series(
    daily_tss: dict[date, float],
    short_days: int = 7,
    long_days: int = 28,
) -> dict[str, dict]:
    """
    Compute per-day ACWR values in a single O(N) forward pass.

    Replaces the O(N²) pattern of calling compute_acwr() in a loop for each
    historical date. Produces identical rolling and EMA ACWR values.

    Returns dict keyed by ISO date string, each value containing:
      acwr_rolling, acwr_ema, risk_zone
    """
    from collections import deque

    if not daily_tss:
        return {}

    all_dates = sorted(daily_tss.keys())
    start = all_dates[0]
    end = date.today()

    # EMA constants
    k_short = 1 - math.exp(-1 / short_days)
    k_long = 1 - math.exp(-1 / long_days)
    ema_short = 0.0
    ema_long = 0.0

    # Rolling window: keep last `long_days` values in a deque
    window: deque[float] = deque(maxlen=long_days)

    result: dict[str, dict] = {}
    current = start
    while current <= end:
        tss = daily_tss.get(current, 0.0)

        # Update EMA
        ema_short += k_short * (tss - ema_short)
        ema_long += k_long * (tss - ema_long)

        # Update rolling window
        window.append(tss)

        # Rolling ACWR: acute (last short_days) / chronic (last long_days)
        window_list = list(window)
        chronic_n = len(window_list)
        acute_n = min(short_days, chronic_n)
        chronic_avg = sum(window_list) / chronic_n
        acute_avg = sum(window_list[-acute_n:]) / acute_n
        acwr_rolling = round(acute_avg / chronic_avg, 3) if chronic_avg > 0 else None

        # EMA ACWR
        acwr_ema = round(ema_short / ema_long, 3) if ema_long > 0 else None

        # Risk zone (based on rolling, per Gabbett 2016)
        ratio = acwr_rolling
        if ratio is None:
            risk_zone = "unknown"
        elif ratio < 0.8:
            risk_zone = "undertrained"
        elif ratio <= 1.3:
            risk_zone = "optimal"
        elif ratio <= 1.5:
            risk_zone = "caution"
        else:
            risk_zone = "high_risk"

        result[current.isoformat()] = {
            "acwr_rolling": acwr_rolling,
            "acwr_ema": acwr_ema,
            "risk_zone": risk_zone,
        }
        current += timedelta(days=1)

    return result


def get_acwr_from_db(conn, sport_category: str = "all") -> dict:
    """Load daily TSS from DB and return today's ACWR snapshot."""
    daily_tss = get_daily_tss_from_db(conn, sport_category)
    return compute_acwr(daily_tss)


# ── Session TSS Estimation ────────────────────────────────────────────────────

# Intensity Factor lookup by session intensity label (as fraction of threshold).
# Intensity → Intensity Factor (IF), used for planned-session TSS estimation
# via TSS = hours × IF² × 100. The tables are sport-specific because the same
# subjective intensity costs differently per sport:
#
#   * Cycling: freewheeling / coasting drags normalised power down, so easy and
#     endurance rides land at a markedly lower IF than running. Measured athlete
#     Z2 rides cluster around IF 0.62–0.65.
#   * Running: little to no coasting, plus higher cardiovascular cost per minute,
#     so even easy runs sit higher (measured median ~0.80).
#
# Threshold and above converge near 1.0 for both (threshold is threshold). The
# divergence is concentrated in the recovery/easy/endurance range — exactly
# where the old single (cycling-mislabelled) table over-credited easy rides.
#
# ``threshold`` for the running/default table is held at exactly 1.00 so that
# "1 hour at threshold = 100 TSS" remains true by definition.
_INTENSITY_IF_RUN: dict[str, float] = {
    "recovery": 0.65,  # Z1 — very easy jog / walk-run
    "easy": 0.75,  # Z2 — aerobic base run
    "moderate": 0.83,  # Z2/Z3 — steady endurance
    "tempo": 0.90,  # Z3 — comfortably hard
    "threshold": 1.00,  # Z4 — lactate threshold, ~1h pace
    "vo2max": 1.10,  # Z5 — VO2max intervals
    "anaerobic": 1.25,  # Z6 — short hard efforts
}

_INTENSITY_IF_RIDE: dict[str, float] = {
    "recovery": 0.55,  # Z1 — active-recovery spin (lots of soft-pedalling)
    "easy": 0.63,  # Z2 — aerobic base ride
    "moderate": 0.72,  # Z2/Z3 — endurance / low sweet-spot
    "tempo": 0.82,  # Z3 — tempo / sweet-spot
    "threshold": 0.95,  # Z4 — FTP work (rarely pure 1.0 NP outdoors)
    "vo2max": 1.05,  # Z5 — VO2max intervals
    "anaerobic": 1.20,  # Z6 — short hard efforts
}

# Sport label → IF table. Running and unspecified ("any") default to the run
# table (the more conservative/general case); all cycling variants use the ride
# table. Backwards-compatible default is the run table so existing callers that
# omit ``sport`` keep "threshold 1h = 100 TSS".
_RIDE_SPORTS = {"ride", "virtualride", "gravelride", "mountainbikeride", "cycling", "bike"}
_RUN_SPORTS = {"run", "trailrun", "trail_run", "running"}

# Back-compat alias: some code/tests may import the old name. Points at the run
# table (which preserves the historical threshold=1.00 behaviour).
_INTENSITY_IF = _INTENSITY_IF_RUN


def _intensity_table_for_sport(sport: str) -> dict[str, float]:
    """Return the IF table for a sport label (defaults to the run/any table)."""
    key = (sport or "").lower().strip()
    if key in _RIDE_SPORTS:
        return _INTENSITY_IF_RIDE
    return _INTENSITY_IF_RUN


def estimate_session_tss(
    duration_min: float,
    intensity: str = "moderate",
    sport: str = "any",
) -> dict:
    """
    Estimate TSS for a planned session from duration and qualitative intensity.

    Uses the standard Coggan formula:
        TSS = (duration_hours) × IF² × 100

    The IF is looked up from ``intensity`` in a **sport-specific** table, because
    the same subjective intensity costs differently per sport (cyclists coast,
    runners do not). For example ``easy``:
        run  → IF 0.75 (≈ 56 TSS/hr)
        ride → IF 0.63 (≈ 40 TSS/hr)

    ``sport`` is normalised: ``ride``/``virtualride``/``gravelride``/
    ``mountainbikeride`` use the cycling table; ``run``/``trailrun`` and anything
    else (including ``"any"``) use the running table. Threshold and above are
    near-identical across sports; the divergence is in the easy/endurance range.

    The IF ratios are athlete-agnostic (TSS is normalised to 100 = 1h at
    threshold), so they do not depend on FTP or rFTP.

    Parameters
    ----------
    duration_min : session duration in minutes
    intensity    : one of the labels above (case-insensitive)
    sport        : sport label selecting the IF table (see above)

    Returns
    -------
    dict with: tss_estimate, duration_min, intensity, intensity_factor, sport
    """
    key = intensity.lower().strip()
    table = _intensity_table_for_sport(sport)
    if key not in table:
        valid = ", ".join(sorted(table))
        raise ValueError(f"Unknown intensity '{intensity}'. Valid values: {valid}")
    if_val = table[key]
    duration_s = duration_min * 60
    tss = round((duration_s / 3600) * (if_val**2) * 100, 1)
    return {
        "tss_estimate": tss,
        "duration_min": duration_min,
        "intensity": key,
        "intensity_factor": if_val,
        "sport": sport,
        "formula": f"({duration_min}min / 60) × IF²({if_val}) × 100 = {tss}",
    }


def estimate_week_tss(sessions: list[dict]) -> float:
    """
    Sum TSS estimates for a list of session dicts.
    Each dict must have 'duration_min' and 'intensity'.
    Convenience wrapper for plan validation.
    """
    total = 0.0
    for s in sessions:
        result = estimate_session_tss(
            duration_min=s["duration_min"],
            intensity=s.get("intensity", "moderate"),
            sport=s.get("sport", "any"),
        )
        total += result["tss_estimate"]
    return round(total, 1)


# ── VO2max Estimation ─────────────────────────────────────────────────────────


def estimate_vo2max_running(rftp_sec_per_km: float) -> float:
    """
    Estimate VO2max from running threshold pace (ACSM formula).

    ACSM flat-running oxygen cost formula:
        VO2 (mL/kg/min) = 0.2 × speed_m_per_min + 3.5

    Threshold pace is assumed to be ~88% of vVO2max speed (Daniels 2005), so:
        vVO2max = rFTP_speed / 0.88
        VO2max  = 0.2 × vVO2max_m_per_min + 3.5

    This formula is calibrated for flat road running; results for trail or
    hilly athletes may be slightly underestimated.

    Parameters
    ----------
    rftp_sec_per_km : threshold pace in seconds per km

    Returns
    -------
    Estimated VO2max in mL/kg/min
    """
    if rftp_sec_per_km <= 0:
        return 0.0
    rftp_km_per_min = 60 / rftp_sec_per_km          # km/min at threshold
    v_vo2max_km_per_min = rftp_km_per_min / 0.88    # threshold ≈ 88% of vVO2max
    v_vo2max_m_per_min = v_vo2max_km_per_min * 1000 # convert to m/min
    vo2max = 0.2 * v_vo2max_m_per_min + 3.5         # ACSM formula
    return round(vo2max, 1)


def estimate_vo2max_cycling(ftp_watts: float, weight_kg: float) -> float:
    """
    Estimate VO2max from cycling FTP and body weight (Coggan formula).

        VO2max (mL/kg/min) ≈ 10.8 × (FTP / weight_kg) + 7

    This is an approximation. FTP ≈ 75% of MAP (Maximum Aerobic Power),
    so MAP = FTP / 0.75, and VO2max ≈ MAP × 10.8/weight + 7.

    Parameters
    ----------
    ftp_watts : cycling functional threshold power in watts
    weight_kg : athlete body weight in kg

    Returns
    -------
    Estimated VO2max in mL/kg/min
    """
    if weight_kg <= 0 or ftp_watts <= 0:
        return 0.0
    ftp_per_kg = ftp_watts / weight_kg
    # MAP ≈ FTP / 0.75; VO2max ≈ (MAP / weight_kg) × 10.8 + 7
    # Simplified directly from FTP/kg:
    vo2max = (ftp_per_kg / 0.75) * 10.8 + 7
    return round(vo2max, 1)


def estimate_vo2max_from_athlete(athlete: dict, weight_override: float | None = None) -> dict:
    """
    Compute VO2max estimates from available athlete config.
    Returns all available estimates with their method and confidence level.

    Parameters
    ----------
    athlete : dict from ``load_athlete()``
    weight_override : optional body weight (kg) to use instead of
        ``athlete["weight_kg"]``. Pass the date-aware value from
        ``config.weight_on(conn, date)`` so the cycling estimate reflects
        current body weight rather than the static YAML scalar.

    Returns
    -------
    dict with estimates per method, plus a consensus value.
    """
    estimates: list[dict] = []

    rftp = athlete.get("rftp")  # sec/km
    if rftp and rftp > 0:
        val = estimate_vo2max_running(rftp)
        estimates.append(
            {
                "method": "running_threshold_pace",
                "vo2max": val,
                "confidence": "medium",
                "note": f"ACSM formula from rFTP={rftp}s/km → vVO2max pace",
            }
        )

    ftp = athlete.get("ftp")
    weight = weight_override if weight_override is not None else athlete.get("weight_kg")
    if ftp and weight and ftp > 0 and weight > 0:
        val = estimate_vo2max_cycling(ftp, weight)
        estimates.append(
            {
                "method": "cycling_ftp",
                "vo2max": val,
                "confidence": "medium",
                "note": f"Coggan formula from FTP={ftp}W, weight={weight}kg",
            }
        )

    if not estimates:
        return {
            "estimates": [],
            "consensus": None,
            "note": "Set rftp (sec/km) and/or ftp + weight_kg in athlete.yaml to enable VO2max estimation.",
        }

    consensus = round(sum(e["vo2max"] for e in estimates) / len(estimates), 1)
    return {
        "estimates": estimates,
        "consensus": consensus,
        "interpretation": _vo2max_interpretation(consensus),
    }


def _vo2max_interpretation(vo2max: float) -> str:
    """Qualitative interpretation of VO2max for endurance athletes."""
    if vo2max >= 70:
        return "Elite / professional level (≥70 mL/kg/min)."
    if vo2max >= 60:
        return "Highly trained amateur — competitive age-group level (60–70)."
    if vo2max >= 50:
        return "Well-trained — solid recreational endurance athlete (50–60)."
    if vo2max >= 40:
        return "Moderately trained — average recreational athlete (40–50)."
    return "Beginner / untrained level (<40). Significant aerobic gains still available."


# ── Race Time Prediction (Riegel model) ───────────────────────────────────────

#: Standard Riegel exponents by mode.
_RIEGEL_EXPONENTS: dict[str, float] = {
    "road": 1.06,  # Riegel 1977 — validated 5k–marathon
    "ultra": 1.15,  # Empirical adjustment for fatigue beyond 42 km
}

#: Target distances shown in predictions, with friendly labels.
_RACE_DISTANCES: list[tuple[float, str]] = [
    (5.0, "5k"),
    (10.0, "10k"),
    (21.1, "Half marathon"),
    (42.2, "Marathon"),
    (50.0, "50k"),
]


def riegel_predict(
    t1_seconds: float,
    d1_km: float,
    d2_km: float,
    exponent: float = 1.06,
) -> float:
    """
    Predict finish time (seconds) for *d2_km* from a known performance *t1_seconds*
    over *d1_km* using Riegel's (1977) power-law model:

        T2 = T1 × (D2 / D1) ^ exponent

    Parameters
    ----------
    t1_seconds:
        Known performance time in seconds (must be > 0).
    d1_km:
        Reference distance in kilometres (must be > 0).
    d2_km:
        Target distance in kilometres (must be > 0).
    exponent:
        Fatigue exponent. Default 1.06 (road racing, Riegel 1977).
        Use 1.15 for ultra distances (>42 km).

    Returns
    -------
    float
        Predicted finish time in seconds.

    Raises
    ------
    ValueError
        If t1_seconds ≤ 0 or d1_km ≤ 0 or d2_km ≤ 0.
    """
    if t1_seconds <= 0:
        raise ValueError(f"t1_seconds must be positive, got {t1_seconds}")
    if d1_km <= 0:
        raise ValueError(f"d1_km must be positive, got {d1_km}")
    if d2_km <= 0:
        raise ValueError(f"d2_km must be positive, got {d2_km}")
    return t1_seconds * (d2_km / d1_km) ** exponent


def predict_race_times(
    t1_seconds: float,
    d1_km: float,
    mode: str = "road",
) -> list[dict]:
    """
    Apply Riegel's model to all standard race distances and return predictions.

    Parameters
    ----------
    t1_seconds:
        Known performance time in seconds.
    d1_km:
        Reference distance in kilometres.
    mode:
        ``'road'`` → exponent 1.06 (5k–marathon).
        ``'ultra'`` → exponent 1.15 (50k+, higher fatigue penalty).

    Returns
    -------
    list of dict, one per target distance:
        distance_km, distance_label, predicted_seconds,
        predicted_pace_sec_per_km, predicted_pace_formatted, exponent_used
    """
    if mode not in _RIEGEL_EXPONENTS:
        raise ValueError(f"Unknown mode '{mode}'. Choose from: {list(_RIEGEL_EXPONENTS)}")

    exponent = _RIEGEL_EXPONENTS[mode]
    results = []
    for d2_km, label in _RACE_DISTANCES:
        predicted_s = riegel_predict(t1_seconds, d1_km, d2_km, exponent)
        pace_sec_per_km = predicted_s / d2_km
        results.append(
            {
                "distance_km": d2_km,
                "distance_label": label,
                "predicted_seconds": round(predicted_s),
                "predicted_pace_sec_per_km": round(pace_sec_per_km, 1),
                "predicted_pace_formatted": format_pace(pace_sec_per_km),
                "exponent_used": exponent,
            }
        )
    return results


# ── Efficiency Factor Trend ───────────────────────────────────────────────────


def compute_efficiency_factor_trend(
    conn,
    sport: str = "all",
    weeks: int = 16,
) -> list[dict]:
    """
    Compute Efficiency Factor (EF) for each aerobic session over the last N weeks.

    EF measures aerobic output per unit of cardiac strain:
      - Cycling: EF = normalised_power (W) / avg_HR
      - Running: EF = NGP (m/s) / avg_HR

    Only aerobic sessions are included (intensity_factor < 0.85 for rides;
    for runs: sessions where avg HR < threshold_hr × 0.95).  Sessions shorter
    than 45 minutes are excluded (insufficient steady-state signal).

    A rising EF trend at constant RPE indicates improving aerobic economy.

    Parameters
    ----------
    conn        : SQLite connection
    sport       : 'all', 'run', or 'ride'
    weeks       : how many weeks of history to include (default 16)

    Returns
    -------
    list of per-activity dicts plus a summary:
      {date, activity_id, name, sport_type, ef, if_val, avg_hr, notes}
    Plus a top-level summary with rolling_4w_mean and trend direction.

    Sources
    -------
    Allen & Coggan, "Training and Racing with a Power Meter" (2010), Ch.4
    Friel, "The Cyclist's Training Bible" (2009) — Pa:HR ratio
    Coggan, "Power Training Levels" (2003) — IF < 0.85 aerobic filter
    """
    from .config import load_athlete

    athlete = load_athlete()
    threshold_hr = athlete.get("threshold_hr", 175)

    cutoff = (date.today() - timedelta(weeks=weeks)).isoformat()

    sport_filter = ""
    params: list = [cutoff]
    if sport == "run":
        sport_filter = "AND (LOWER(sport_type) LIKE '%run%' OR LOWER(sport_type) LIKE '%trail%')"
    elif sport == "ride":
        sport_filter = "AND LOWER(sport_type) LIKE '%ride%'"

    rows = conn.execute(
        f"""
        SELECT
            id, name, sport_type,
            date(start_date) AS day,
            average_heartrate,
            average_watts,
            weighted_avg_watts,
            ngp,
            intensity_factor,
            moving_time
        FROM activities
        WHERE start_date >= ?
          AND average_heartrate IS NOT NULL
          AND average_heartrate > 0
          AND moving_time >= 2700           -- ≥ 45 minutes
          {sport_filter}
        ORDER BY start_date ASC
        """,
        params,
    ).fetchall()

    entries: list[dict] = []
    for row in rows:
        r = dict(row)
        stype = (r.get("sport_type") or "").lower()
        is_run = "run" in stype or "trail" in stype
        is_ride = "ride" in stype
        avg_hr = r["average_heartrate"]
        if_val = r.get("intensity_factor")

        ef: float | None = None
        note = ""

        if is_ride:
            # Use NP (weighted_avg_watts) if available, else average_watts
            power = r.get("weighted_avg_watts") or r.get("average_watts")
            if not power or avg_hr <= 0:
                continue
            # Skip threshold/intensity sessions
            if if_val is not None and if_val >= 0.85:
                continue
            ef = round(power / avg_hr, 4)
            note = f"NP/HR ({power:.0f}W / {avg_hr:.0f}bpm)"

        elif is_run:
            ngp = r.get("ngp")  # stored in m/s
            if not ngp or ngp <= 0 or avg_hr <= 0:
                continue
            # Skip hard running sessions (avg HR > 95% of threshold)
            if avg_hr >= threshold_hr * 0.95:
                continue
            ef = round(ngp / avg_hr, 6)
            ngp_pace = format_pace(1000 / ngp)
            note = f"NGP/HR ({ngp_pace}/km / {avg_hr:.0f}bpm)"

        else:
            continue

        entries.append(
            {
                "date": r["day"],
                "activity_id": r["id"],
                "name": r["name"],
                "sport_type": r["sport_type"],
                "ef": ef,
                "if_val": if_val,
                "avg_hr": avg_hr,
                "duration_min": round(r["moving_time"] / 60),
                "note": note,
            }
        )

    if not entries:
        return []

    def _compute_sport_ef_stats(sport_entries: list[dict]) -> dict:
        """Compute rolling 4-week EF mean and trend for a homogeneous sport list."""
        # 4-week rolling mean (per-session)
        for i, e in enumerate(sport_entries):
            d = date.fromisoformat(e["date"])
            window_start = (d - timedelta(weeks=4)).isoformat()
            window = [x["ef"] for x in sport_entries[: i + 1] if x["date"] >= window_start]
            e["rolling_4w_ef"] = round(sum(window) / len(window), 6) if window else e["ef"]

        # Trend: compare first-half mean to last-4-week mean
        if len(sport_entries) >= 4:
            split = max(len(sport_entries) // 2, 1)
            early_mean = sum(x["ef"] for x in sport_entries[:split]) / split
            late_mean = sum(x["ef"] for x in sport_entries[split:]) / (len(sport_entries) - split)
            delta_pct = (late_mean - early_mean) / max(early_mean, 1e-9) * 100
            if delta_pct >= 2.0:
                trend = "rising"
            elif delta_pct <= -2.0:
                trend = "declining"
            else:
                trend = "stable"
            trend_pct = round(delta_pct, 1)
        else:
            trend = "insufficient_data"
            trend_pct = 0.0

        _trend_msg = {
            "rising": "Aerobic fitness improving — good adaptation signal.",
            "declining": "Aerobic efficiency dropping — review recovery, illness, or heat stress.",
            "stable": "EF holding steady — consistent aerobic base.",
            "insufficient_data": "Not enough sessions to assess trend.",
        }
        current_4w_ef = sport_entries[-1]["rolling_4w_ef"] if sport_entries else None
        return {
            "sessions_analysed": len(sport_entries),
            "earliest_date": sport_entries[0]["date"] if sport_entries else None,
            "latest_date": sport_entries[-1]["date"] if sport_entries else None,
            "current_4w_ef": current_4w_ef,
            "trend": trend,
            "trend_pct": trend_pct,
            "interpretation": f"EF is {trend} ({trend_pct:+.1f}% from first half to recent 4 weeks). "
            + _trend_msg[trend],
        }

    # Split entries by sport category
    run_entries = [
        e
        for e in entries
        if "run" in (e["sport_type"] or "").lower() or "trail" in (e["sport_type"] or "").lower()
    ]
    ride_entries = [e for e in entries if "ride" in (e["sport_type"] or "").lower()]

    # When sport='all', compute rolling means per-sport to avoid cross-sport scale pollution.
    # When filtered to a single sport, all entries belong to that sport.
    if sport == "all":
        if run_entries:
            _compute_sport_ef_stats(run_entries)
        if ride_entries:
            _compute_sport_ef_stats(ride_entries)
        # Backfill rolling_4w_ef for any entry that wasn't covered (shouldn't happen)
        for e in entries:
            e.setdefault("rolling_4w_ef", e["ef"])
        # Merge back in date order (already sorted from SQL)
    else:
        _compute_sport_ef_stats(entries)

    # Build by-sport summary for the 'all' case
    by_sport: dict = {}
    if sport == "all":
        if run_entries:
            by_sport["run"] = _compute_sport_ef_stats(run_entries)
        if ride_entries:
            by_sport["ride"] = _compute_sport_ef_stats(ride_entries)
        # Overall combined summary (directional only — not a meaningful EF value)
        combined_sessions = len(entries)
        summary_entry: dict = {
            "__summary__": True,
            "sessions_analysed": combined_sessions,
            "earliest_date": entries[0]["date"],
            "latest_date": entries[-1]["date"],
            "by_sport": by_sport,
            "note": (
                "Run EF (m/s ÷ bpm) and ride EF (W ÷ bpm) are on different scales — "
                "compare within each sport only. See by_sport for per-sport trends."
            ),
        }
    else:
        stats = _compute_sport_ef_stats(entries)
        summary_entry = {"__summary__": True, **stats, "by_sport": {}}

    entries.append(summary_entry)
    return entries


# ── Best Efforts ──────────────────────────────────────────────────────────────

# Standard brackets for running best efforts: (label, min_m, max_m, canonical_km)
_RUN_EFFORT_BRACKETS: list[tuple[str, float, float, float]] = [
    ("pace_1km", 900, 1100, 1.0),
    ("pace_5km", 4750, 5250, 5.0),
    ("pace_10km", 9500, 10500, 10.0),
    ("pace_half", 20000, 22200, 21.1),
    ("pace_marathon", 41000, 43400, 42.2),
]

# Standard durations for cycling power best efforts (label, seconds)
_RIDE_EFFORT_DURATIONS: list[tuple[str, int]] = [
    ("power_5s", 5),
    ("power_30s", 30),
    ("power_1min", 60),
    ("power_5min", 300),
    ("power_20min", 1200),
    ("power_60min", 3600),
]


def _is_best_efforts_stale(conn) -> bool:
    """Return True if best_efforts table needs recomputation (new activities since last compute)."""
    row = conn.execute("SELECT MAX(computed_at) FROM best_efforts WHERE sport = 'ride'").fetchone()
    last_computed = row[0] if row else None
    if not last_computed:
        return True
    row2 = conn.execute("SELECT MAX(synced_at) FROM activities").fetchone()
    last_synced = row2[0] if row2 else None
    if not last_synced:
        return False
    return last_synced > last_computed


def _compute_run_best_efforts(conn) -> list[dict]:
    """Compute running best efforts from activities table (no streams needed)."""
    season_cutoff = (date.today() - timedelta(days=365)).isoformat()
    results = []

    for effort_type, min_m, max_m, canonical_km in _RUN_EFFORT_BRACKETS:
        # All-time best
        row = conn.execute(
            """
            SELECT id, date(start_date) AS day, distance, moving_time
            FROM activities
            WHERE (LOWER(sport_type) LIKE '%run%' OR LOWER(sport_type) LIKE '%trail%')
              AND distance BETWEEN ? AND ?
              AND moving_time > 0
            ORDER BY (CAST(moving_time AS REAL) / distance) ASC
            LIMIT 1
            """,
            (min_m, max_m),
        ).fetchone()

        if not row:
            continue

        d_km = row["distance"] / 1000.0
        pace_sec_per_km = row["moving_time"] / d_km

        # Season best (last 365 days)
        srow = conn.execute(
            """
            SELECT id, date(start_date) AS day, distance, moving_time
            FROM activities
            WHERE (LOWER(sport_type) LIKE '%run%' OR LOWER(sport_type) LIKE '%trail%')
              AND distance BETWEEN ? AND ?
              AND moving_time > 0
              AND date(start_date) >= ?
            ORDER BY (CAST(moving_time AS REAL) / distance) ASC
            LIMIT 1
            """,
            (min_m, max_m, season_cutoff),
        ).fetchone()

        season_pace = None
        season_date = None
        season_act_id = None
        if srow:
            s_d_km = srow["distance"] / 1000.0
            season_pace = srow["moving_time"] / s_d_km
            season_date = srow["day"]
            season_act_id = srow["id"]

        results.append(
            {
                "sport": "run",
                "effort_type": effort_type,
                "activity_id": row["id"],
                "activity_date": row["day"],
                "value": round(pace_sec_per_km, 1),
                "value_per_kg": None,
                "season_activity_id": season_act_id,
                "season_date": season_date,
                "season_value": round(season_pace, 1) if season_pace else None,
                "season_value_per_kg": None,
            }
        )

    return results


def _compute_ride_best_efforts(conn, weight_kg: float | None) -> list[dict]:
    """
    Compute cycling power best efforts by scanning all cached activity streams.

    Uses a sliding-window mean over each duration to find the best mean power.
    Results are cached in the best_efforts table.

    Sources
    -------
    Coggan, "Power Profiling" (2003/2010) — standard 5s/1min/5min/20min durations
    """
    # Collect all cached streams for rides
    stream_rows = conn.execute(
        """
        SELECT a.id, date(a.start_date) AS day, s.streams_json
        FROM activity_streams s
        JOIN activities a ON a.id = s.activity_id
        WHERE LOWER(a.sport_type) LIKE '%ride%'
          AND a.moving_time > 0
        ORDER BY a.start_date ASC
        """,
    ).fetchall()

    season_cutoff = (date.today() - timedelta(days=365)).isoformat()

    # all_time best: {effort_type: (value, activity_id, date)}
    best_all: dict[str, tuple[float, int, str]] = {}
    best_season: dict[str, tuple[float, int, str]] = {}

    for srow in stream_rows:
        act_id = srow["id"]
        act_date = srow["day"]
        try:
            streams = json.loads(srow["streams_json"])
        except Exception:
            continue

        watts_stream = streams.get("watts")
        if isinstance(watts_stream, dict):
            watts = watts_stream.get("data") or []
        elif isinstance(watts_stream, list):
            watts = watts_stream
        else:
            continue

        if not watts or len(watts) < 5:
            continue

        for effort_type, dur_s in _RIDE_EFFORT_DURATIONS:
            if len(watts) < dur_s:
                continue

            # Sliding window sum
            window_sum = float(sum(watts[:dur_s]))
            best_sum = window_sum
            for i in range(dur_s, len(watts)):
                window_sum += watts[i] - watts[i - dur_s]
                if window_sum > best_sum:
                    best_sum = window_sum
            mean_power = best_sum / dur_s

            if mean_power <= 0:
                continue

            if effort_type not in best_all or mean_power > best_all[effort_type][0]:
                best_all[effort_type] = (mean_power, act_id, act_date)

            if act_date >= season_cutoff:
                if effort_type not in best_season or mean_power > best_season[effort_type][0]:
                    best_season[effort_type] = (mean_power, act_id, act_date)

    results = []
    for effort_type, _ in _RIDE_EFFORT_DURATIONS:
        if effort_type not in best_all:
            continue
        val, act_id, act_date = best_all[effort_type]
        vpkg = round(val / weight_kg, 3) if weight_kg and weight_kg > 0 else None

        s_val = s_act_id = s_date = s_vpkg = None
        if effort_type in best_season:
            s_val, s_act_id, s_date = best_season[effort_type]
            s_vpkg = round(s_val / weight_kg, 3) if weight_kg and weight_kg > 0 else None

        results.append(
            {
                "sport": "ride",
                "effort_type": effort_type,
                "activity_id": act_id,
                "activity_date": act_date,
                "value": round(val, 1),
                "value_per_kg": vpkg,
                "season_activity_id": s_act_id,
                "season_date": s_date,
                "season_value": round(s_val, 1) if s_val is not None else None,
                "season_value_per_kg": s_vpkg,
            }
        )

    return results


def compute_best_efforts(conn, athlete: dict | None = None) -> dict:
    """
    Return the athlete's best efforts for standard running distances and
    cycling power durations.  Results are lazily cached in the best_efforts
    table — only recomputed when new activities have been synced since the
    last computation.

    Running efforts (from activities table):
      pace_1km, pace_5km, pace_10km, pace_half, pace_marathon

    Cycling power efforts (from cached activity_streams):
      power_5s, power_30s, power_1min, power_5min, power_20min, power_60min

    Each effort shows:
      - all_time: best ever value + date
      - season:   best in last 365 days (None if no qualifying activity)
      - stale:    True if the all-time best is > 12 months old (consider re-testing)

    Sources
    -------
    Coggan, "Power Profiling" (2003/2010) — standard cycling power durations
    Péronnet & Thibault (1989) — distance effort model basis
    """
    if athlete is None:
        from .config import load_athlete

        athlete = load_athlete()

    weight_kg = athlete.get("weight_kg")
    recompute_rides = _is_best_efforts_stale(conn)

    if recompute_rides:
        # Recompute runs too (cheap) to keep everything consistent
        run_rows = _compute_run_best_efforts(conn)
        ride_rows = _compute_ride_best_efforts(conn, weight_kg)
        all_rows = run_rows + ride_rows

        now_str = datetime.now().isoformat()
        for r in all_rows:
            conn.execute(
                """
                INSERT INTO best_efforts (
                    sport, effort_type, activity_id, activity_date,
                    value, value_per_kg,
                    season_activity_id, season_date, season_value, season_value_per_kg,
                    computed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(sport, effort_type) DO UPDATE SET
                    activity_id         = excluded.activity_id,
                    activity_date       = excluded.activity_date,
                    value               = excluded.value,
                    value_per_kg        = excluded.value_per_kg,
                    season_activity_id  = excluded.season_activity_id,
                    season_date         = excluded.season_date,
                    season_value        = excluded.season_value,
                    season_value_per_kg = excluded.season_value_per_kg,
                    computed_at         = excluded.computed_at
                """,
                (
                    r["sport"],
                    r["effort_type"],
                    r["activity_id"],
                    r["activity_date"],
                    r["value"],
                    r["value_per_kg"],
                    r["season_activity_id"],
                    r["season_date"],
                    r["season_value"],
                    r["season_value_per_kg"],
                    now_str,
                ),
            )

    rows = conn.execute("SELECT * FROM best_efforts ORDER BY sport, effort_type").fetchall()

    season_cutoff = (date.today() - timedelta(days=365)).isoformat()
    run_efforts: list[dict] = []
    ride_efforts: list[dict] = []

    for row in rows:
        r = dict(row)
        is_stale = r["activity_date"] < season_cutoff if r["activity_date"] else True
        effort_type = r["effort_type"]
        sport = r["sport"]

        # Human-readable formatting
        if sport == "run":
            val_fmt = format_pace(r["value"]) + "/km"
            s_val_fmt = format_pace(r["season_value"]) + "/km" if r["season_value"] else None
        else:
            val_fmt = f"{r['value']:.0f} W"
            if r.get("value_per_kg"):
                val_fmt += f" ({r['value_per_kg']:.2f} W/kg)"
            s_val_fmt = None
            if r["season_value"]:
                s_val_fmt = f"{r['season_value']:.0f} W"
                if r.get("season_value_per_kg"):
                    s_val_fmt += f" ({r['season_value_per_kg']:.2f} W/kg)"

        entry = {
            "effort": effort_type,
            "all_time": {
                "value_raw": r["value"],
                "value_fmt": val_fmt,
                "activity_id": r["activity_id"],
                "date": r["activity_date"],
            },
            "season": (
                {
                    "value_raw": r["season_value"],
                    "value_fmt": s_val_fmt,
                    "activity_id": r["season_activity_id"],
                    "date": r["season_date"],
                }
                if r["season_value"]
                else None
            ),
            "stale": is_stale,
            "stale_note": "All-time best is >12 months old — consider a test effort."
            if is_stale
            else None,
        }

        if sport == "run":
            run_efforts.append(entry)
        else:
            ride_efforts.append(entry)

    return {
        "run": run_efforts,
        "ride": ride_efforts,
        "cache_status": "recomputed" if recompute_rides else "cached",
        "season_window": "last 365 days",
    }


# ── Critical Power / W' model ─────────────────────────────────────────────────

# Durations used for the CP fit — long enough to be aerobically dominated.
# 5s and 30s are excluded: both are largely anaerobic and inflate W'.
_CP_FIT_EFFORTS: dict[str, int] = {
    "power_1min": 60,
    "power_5min": 300,
    "power_20min": 1200,
    "power_60min": 3600,
}

_CP_MIN_POINTS = 3  # minimum MMP points to attempt a fit

# Physiological sanity bounds (flag if outside, but still return the value)
_CP_BOUNDS = (80.0, 700.0)  # watts
_W_PRIME_BOUNDS = (1_000.0, 80_000.0)  # joules (1–80 kJ)


def _ols_fit(x: list[float], y: list[float]) -> tuple[float, float, float]:
    """
    Ordinary least-squares linear regression of y on x.

    Returns (slope, intercept, r_squared).

    Uses stdlib ``statistics`` (Python ≥ 3.10).  No external dependencies.

    The CP linearisation maps the 2-param hyperbola ``P = CP + W'/t`` to:
        E = P × t = W' + CP × t
    so slope = CP, intercept = W' (in joules).
    """
    from statistics import linear_regression, mean

    n = len(x)
    if n < 2:
        return 0.0, 0.0, 0.0

    slope, intercept = linear_regression(x, y)

    # R²
    y_mean = mean(y)
    ss_tot = sum((yi - y_mean) ** 2 for yi in y)
    if ss_tot == 0:
        r_sq = 1.0
    else:
        ss_res = sum((yi - (slope * xi + intercept)) ** 2 for xi, yi in zip(x, y))
        r_sq = max(0.0, 1.0 - ss_res / ss_tot)

    return slope, intercept, round(r_sq, 4)


def _fit_cp_from_mmp_points(
    mmp_points: list[tuple[str, float]],
) -> dict | None:
    """
    Fit the CP / W' model from a list of (effort_type, mean_power_watts) tuples.

    Only effort types listed in ``_CP_FIT_EFFORTS`` are used; others are ignored.
    Returns ``None`` if fewer than ``_CP_MIN_POINTS`` valid points are available.

    Returns
    -------
    dict with keys:
        cp_watts      : Critical Power in watts (slope of linearised fit)
        w_prime_kj    : Anaerobic capacity W' in kilojoules
        w_prime_j     : W' in joules (raw)
        r_squared     : Goodness-of-fit (0–1; ≥0.95 is excellent)
        n_points      : Number of MMP durations used
        durations_used: list of effort_type labels
        out_of_range  : True if CP or W' fall outside physiological bounds
    """
    xs: list[float] = []
    ys: list[float] = []
    labels: list[str] = []

    for effort_type, dur_s in _CP_FIT_EFFORTS.items():
        # Find matching point
        power_w = next(
            (p for et, p in mmp_points if et == effort_type and p and p > 0),
            None,
        )
        if power_w is None:
            continue
        xs.append(float(dur_s))
        ys.append(float(power_w) * dur_s)  # E = P × t  (joules)
        labels.append(effort_type)

    if len(xs) < _CP_MIN_POINTS:
        return None

    cp, w_prime_j, r_sq = _ols_fit(xs, ys)

    if cp <= 0 or w_prime_j <= 0:
        return None

    w_prime_kj = round(w_prime_j / 1000, 2)
    cp_rounded = round(cp, 1)
    out_of_range = not (
        _CP_BOUNDS[0] <= cp <= _CP_BOUNDS[1]
        and _W_PRIME_BOUNDS[0] <= w_prime_j <= _W_PRIME_BOUNDS[1]
    )

    return {
        "cp_watts": cp_rounded,
        "w_prime_kj": w_prime_kj,
        "w_prime_j": round(w_prime_j, 1),
        "r_squared": r_sq,
        "n_points": len(xs),
        "durations_used": labels,
        "out_of_range": out_of_range,
    }


def fit_critical_power(
    ride_best_efforts: list[dict],
    ftp: float | int | None = None,
) -> dict | None:
    """
    Estimate Critical Power (CP) and anaerobic work capacity (W') from the
    athlete's mean maximal power best efforts.

    Parameters
    ----------
    ride_best_efforts :
        List of ride effort dicts as returned by ``compute_best_efforts()["ride"]``.
        Each dict must have ``effort`` (str) and ``all_time.value_raw`` /
        ``season.value_raw`` (float | None).
    ftp :
        Athlete's current FTP in watts (from ``athlete.yaml``).
        Used only for the FTP comparison note.

    Returns
    -------
    dict | None
        ``None`` if insufficient MMP data to fit either model.

        Otherwise a dict with:
          all_time      : CP/W' fit from all-time MMP (may be None)
          season        : CP/W' fit from season MMP (may be None)
          ftp_comparison: CP vs athlete FTP ratio + interpretation note
                          (only present when ftp is provided and all_time fit succeeded)

    Algorithm
    ---------
    Linearises ``P(t) = CP + W'/t`` as ``E(t) = W' + CP × t`` where
    ``E = P × t`` is total mechanical work.  OLS slope = CP, intercept = W'.
    Uses durations ≥ 1 min to stay in the aerobic-dominated domain.

    Sources
    -------
    Morton (1996) — CP model review, J Sports Sci 14(6):491–514.
    Monod & Scherrer (1965) — original W' / limit-of-work concept.
    Coggan (2003/2010) — MMP profiling and FTP as ≈95–97% CP.
    """
    # Build (effort_type, power_w) lists for all_time and season
    all_time_pts: list[tuple[str, float]] = []
    season_pts: list[tuple[str, float]] = []

    for entry in ride_best_efforts:
        effort_type = entry.get("effort", "")
        if effort_type not in _CP_FIT_EFFORTS:
            continue

        at = entry.get("all_time") or {}
        if at.get("value_raw") and at["value_raw"] > 0:
            all_time_pts.append((effort_type, float(at["value_raw"])))

        s = entry.get("season") or {}
        if s.get("value_raw") and s["value_raw"] > 0:
            season_pts.append((effort_type, float(s["value_raw"])))

    all_time_fit = _fit_cp_from_mmp_points(all_time_pts)
    season_fit = _fit_cp_from_mmp_points(season_pts)

    if all_time_fit is None and season_fit is None:
        return None

    result: dict = {
        "all_time": all_time_fit,
        "season": season_fit,
    }

    # FTP comparison (uses all_time CP as the reference)
    if ftp and ftp > 0 and all_time_fit:
        cp = all_time_fit["cp_watts"]
        ratio = round(cp / ftp, 3)
        if ratio < 1.00:
            note = (
                f"CP ({cp:.0f} W) is below FTP ({ftp} W) — FTP may be set too high "
                f"or CP estimate needs more max efforts."
            )
        elif ratio <= 1.08:
            note = (
                f"CP/FTP ratio {ratio:.2f} is within the expected 1.00–1.08 range — "
                f"FTP looks well-calibrated."
            )
        else:
            note = (
                f"CP/FTP ratio {ratio:.2f} is above 1.08 — FTP may be underestimated "
                f"(consider a 20-min or ramp test)."
            )
        result["ftp_comparison"] = {
            "athlete_ftp": ftp,
            "cp_watts": cp,
            "ratio": ratio,
            "note": note,
        }

    return result


# ── Fitness Projection ────────────────────────────────────────────────────────


def project_fitness(
    daily_tss: dict[date, float],
    target_date: date,
    weekly_tss: float | None = None,
    taper_weeks: int = 3,
    taper_factor: float = 0.70,
    sport_label: str = "all",
) -> dict:
    """
    Project CTL/ATL/TSB forward from today to a target race date.

    The model extends the historical EMA fitness series with an assumed
    future daily TSS, applying a standard taper in the final ``taper_weeks``
    before the target date.

    Taper schedule (default taper_factor = 0.70, i.e. 30% load reduction):
      Week -N to -3 : 100% of weekly_tss / 7 per day  (build phase)
      Week -2       : weekly_tss × taper_factor / 7   (~70%)
      Week -1       : weekly_tss × taper_factor² / 7  (~49%)
      Race day      : 0 TSS

    Parameters
    ----------
    daily_tss    : historical {date: tss} dict (from get_daily_tss_from_db)
    target_date  : race/event date to project to
    weekly_tss   : assumed weekly training load going forward.
                   If None or 0: auto-detected as the mean of the last 4 weeks.
    taper_weeks  : how many weeks before race to begin taper (default 3)
    taper_factor : fractional load reduction per taper week (default 0.70)
    sport_label  : informational only (used in output)

    Returns
    -------
    dict with:
      current          : {ctl, atl, tsb} today
      projected        : {ctl, atl, tsb, date} on race day
      taper_start_date : ISO date when taper begins
      weekly_tss_used  : assumed weekly TSS (auto or provided)
      form_status      : 'under-tapered' / 'optimal' / 'over-tapered'
      recommendation   : coaching text
      daily_series     : [{date, ctl, atl, tsb, tss, projected: bool}]
                         last 4 weeks of history + full projection window

    Sources
    -------
    Banister et al. (1975), "A systems model of training for athletic performance"
    Busso (2003), "Variable dose-response relationship between exercise training
      and performance" — EMA fitness-fatigue model
    Mujika & Padilla (2003), "Scientific bases for precompetition tapering
      strategies", Med Sci Sports Exerc 35(7) — taper duration/load reduction
    Coggan (2003) — TSB +15 to +25 optimal A-race form window
    """
    today = date.today()

    if target_date <= today:
        return {"error": f"target_date {target_date} must be in the future."}

    days_to_target = (target_date - today).days

    # ── Determine assumed weekly TSS ─────────────────────────────────────────
    if not weekly_tss:
        lookback = 28
        recent = [daily_tss.get(today - timedelta(days=i), 0.0) for i in range(1, lookback + 1)]
        weekly_tss = round(sum(recent) / lookback * 7, 1)

    daily_tss_per_day = weekly_tss / 7.0
    taper_start = target_date - timedelta(weeks=taper_weeks)

    # ── Build projected daily TSS ─────────────────────────────────────────────
    combined_tss: dict[date, float] = dict(daily_tss)  # historical copy

    for i in range(1, days_to_target + 1):
        d = today + timedelta(days=i)
        days_before_race = (target_date - d).days

        if days_before_race == 0:
            tss_val = 0.0  # race day — no training load
        elif days_before_race < taper_weeks * 7:
            # Progressive exponential taper (Bosquet et al. 2007):
            # Higher exponent closer to race → steeper reduction.
            weeks_out = days_before_race // 7  # 0=race week, 1=week-2, ...
            exponent = taper_weeks - weeks_out
            tss_val = daily_tss_per_day * (taper_factor ** exponent)
        else:
            tss_val = daily_tss_per_day  # maintain load in build phase

        combined_tss[d] = tss_val

    # ── Run EMA model over combined series ────────────────────────────────────
    full_series = compute_fitness_series(combined_tss, end_date=target_date)

    # Identify today's values
    today_str = today.isoformat()
    current = {"ctl": 0.0, "atl": 0.0, "tsb": 0.0}
    for entry in full_series:
        if entry["date"] == today_str:
            current = {"ctl": entry["ctl"], "atl": entry["atl"], "tsb": entry["tsb"]}
            break

    # Race-day values
    target_str = target_date.isoformat()
    projected_entry = None
    for entry in full_series:
        if entry["date"] == target_str:
            projected_entry = entry
            break

    if not projected_entry:
        return {"error": "Could not project to target_date — series ended before that date."}

    projected_tsb = projected_entry["tsb"]

    # ── Form status and recommendation ───────────────────────────────────────
    if projected_tsb < 10:
        form_status = "under-tapered"
        recommendation = (
            f"Projected TSB {projected_tsb:+.1f} on race day is too low. "
            f"Target is +10 to +25. Consider starting the taper earlier "
            f"(try taper_weeks={taper_weeks + 1}) or reducing load this week."
        )
    elif projected_tsb <= 25:
        form_status = "optimal"
        recommendation = (
            f"Projected TSB {projected_tsb:+.1f} is in the optimal window (+10 to +25). "
            f"Execute the plan as designed — taper begins {taper_start.isoformat()}."
        )
    elif projected_tsb <= 35:
        form_status = "over-tapered"
        recommendation = (
            f"Projected TSB {projected_tsb:+.1f} is high (>+25). "
            "Risk of detraining during taper. Consider a shorter taper or "
            f"adding a quality session 10–12 days out."
        )
    else:
        form_status = "heavily_over-tapered"
        recommendation = (
            f"Projected TSB {projected_tsb:+.1f} is very high (>+35). "
            "Significant detraining risk. Shorten taper to 1–2 weeks or maintain "
            "higher volume in weeks -3 and -2."
        )

    # ── Build output daily series (last 4 weeks history + projection) ─────────
    series_cutoff = (today - timedelta(weeks=4)).isoformat()
    output_series = []
    for entry in full_series:
        if entry["date"] < series_cutoff:
            continue
        out = dict(entry)
        out["projected"] = entry["date"] > today_str
        output_series.append(out)

    return {
        "sport": sport_label,
        "target_date": target_str,
        "days_to_target": days_to_target,
        "current": current,
        "projected": {
            "ctl": projected_entry["ctl"],
            "atl": projected_entry["atl"],
            "tsb": projected_entry["tsb"],
            "date": target_str,
        },
        "taper_start_date": taper_start.isoformat(),
        "taper_weeks": taper_weeks,
        "weekly_tss_used": weekly_tss,
        "form_status": form_status,
        "recommendation": recommendation,
        "daily_series": output_series,
    }


def project_fitness_split(
    conn,
    target_date: date,
    weekly_tss: float | None = None,
    taper_weeks: int = 3,
    taper_factor: float = 0.70,
) -> dict:
    """
    Project CTL/ATL/TSB forward split by sport (run + ride + combined).

    Calls project_fitness three times — once per sport category — using
    independent TSS histories so the projections are not cross-contaminated.

    Parameters
    ----------
    conn         : SQLite connection
    target_date  : race/event date to project to
    weekly_tss   : assumed weekly TSS per sport going forward.
                   If None: auto-detected per sport from last 4-week mean.
    taper_weeks  : weeks of taper before race (default 3)
    taper_factor : fractional load reduction per taper week (default 0.70)

    Returns
    -------
    dict with keys:
      "combined" : project_fitness result using all-sport TSS
      "run"      : project_fitness result using run-only TSS
      "ride"     : project_fitness result using ride-only TSS
    """
    combined_tss = get_daily_tss_from_db(conn, "all")
    run_tss = get_daily_tss_from_db(conn, "run")
    ride_tss = get_daily_tss_from_db(conn, "ride")

    combined = project_fitness(
        combined_tss, target_date, weekly_tss, taper_weeks, taper_factor, "combined"
    )
    run = project_fitness(run_tss, target_date, weekly_tss, taper_weeks, taper_factor, "run")
    ride = project_fitness(ride_tss, target_date, weekly_tss, taper_weeks, taper_factor, "ride")

    return {"combined": combined, "run": run, "ride": ride}


# ── Intensity Distribution (Tripartite model) ─────────────────────────────────


def compute_intensity_distribution(conn, weeks: int = 8, sport: str = "all") -> dict:
    """
    Tripartite intensity distribution using HR-based zone boundaries.

    Bins training time into three physiological zones based on LT1 and LT2:
      Easy     (< LT1) — below aerobic threshold (Z1+Z2 in 5-zone model)
      Moderate (LT1 to LT2) — the metabolic "no-man's land" (Z3)
      Hard     (> LT2) — at and above lactate threshold (Z4+Z5)

    LT1 and LT2 are derived from the athlete's threshold HR and resting HR:
      LT1_HR = resting_hr + 0.72 × HRR   (top of Z2 / aerobic threshold)
      LT2_HR = resting_hr + 0.82 × HRR   (top of Z3 / lactate threshold)

    Note: these use the session avg HR as a proxy, which underestimates true
    zone time slightly for polarized sessions (avg can be Z2 even if intervals
    crossed Z4).  For more accuracy, stream-level analysis per second is needed.

    Compares to three canonical distributions:
      Polarized  : ~80% easy, <10% moderate, ~15% hard  (Seiler 2010)
      Pyramidal  : ~70% easy, ~20% moderate, ~10% hard
      Threshold  : ~50% easy, ~30% moderate, ~20% hard

    Classifies the current distribution and outputs gap analysis.

    Parameters
    ----------
    conn  : SQLite connection
    weeks : how many weeks of history to analyse (default 8)
    sport : 'all' (default), 'run', or 'ride'.
            'all' returns a nested dict with keys 'overall', 'run', 'ride'.
            'run' / 'ride' return a single flat result dict.

    Sources
    -------
    Seiler & Tønnessen (2009), "Intervals, Thresholds, and Long Slow Distance",
      Sportscience 13 — tripartite model + LT1/LT2 HR boundaries
    Seiler (2010), "What is best practice for training intensity and duration
      distribution?", Int J Sports Physiol Perform 5(3)
    Stoggl & Sperlich (2014), "Polarized training has greater impact on key
      endurance variables", Front Physiol — polarized vs threshold RCT
    """
    from .config import load_athlete

    athlete = load_athlete()
    threshold_hr = athlete.get("threshold_hr", 175)
    resting_hr = athlete.get("resting_hr", 50)
    hrr = threshold_hr - resting_hr

    lt1_hr = resting_hr + 0.72 * hrr  # aerobic threshold (top of Z2)
    lt2_hr = resting_hr + 0.82 * hrr  # lactate threshold (top of Z3)

    thresholds = {
        "lt1_hr": round(lt1_hr, 0),
        "lt2_hr": round(lt2_hr, 0),
        "threshold_hr_config": threshold_hr,
        "resting_hr_config": resting_hr,
    }

    polarized_target = {"easy": 80.0, "moderate": 5.0, "hard": 15.0}
    pyramidal_target = {"easy": 70.0, "moderate": 20.0, "hard": 10.0}
    threshold_target = {"easy": 50.0, "moderate": 30.0, "hard": 20.0}
    canonical_targets = {
        "polarized": polarized_target,
        "pyramidal": pyramidal_target,
        "threshold": threshold_target,
    }
    caveat = (
        "Binning uses session average HR as a proxy. "
        "Polarized sessions (easy + hard intervals) will appear as moderate. "
        "For precision, use get_activity_streams on key sessions."
    )

    cutoff = (date.today() - timedelta(weeks=weeks)).isoformat()

    def _sport_filter(s: str) -> str:
        if s == "run":
            return "AND (LOWER(sport_type) LIKE '%run%' OR LOWER(sport_type) LIKE '%trail%')"
        elif s == "ride":
            return "AND LOWER(sport_type) LIKE '%ride%'"
        return ""

    def _fetch_and_classify(sport_key: str) -> dict:
        rows = conn.execute(
            f"""
            SELECT average_heartrate, moving_time, sport_type
            FROM activities
            WHERE start_date >= ?
              AND average_heartrate IS NOT NULL
              AND average_heartrate > 0
              AND moving_time > 0
              {_sport_filter(sport_key)}
            """,
            (cutoff,),
        ).fetchall()

        if not rows:
            return {"error": f"No activities with HR data in this period ({sport_key})."}

        easy_min = moderate_min = hard_min = 0.0
        total_min = 0.0
        for row in rows:
            avg_hr = row["average_heartrate"]
            mins = row["moving_time"] / 60.0
            total_min += mins
            if avg_hr < lt1_hr:
                easy_min += mins
            elif avg_hr < lt2_hr:
                moderate_min += mins
            else:
                hard_min += mins

        if total_min == 0:
            return {"error": "No training time with HR data found."}

        easy_pct = round(easy_min / total_min * 100, 1)
        moderate_pct = round(moderate_min / total_min * 100, 1)
        hard_pct = round(hard_min / total_min * 100, 1)

        # Classify
        if moderate_pct <= 10 and hard_pct >= 8:
            classification = "polarized"
            class_note = (
                "Distribution is polarized — healthy aerobic base with targeted intensity. "
                "Consistent with high-performance endurance evidence."
            )
        elif moderate_pct <= 25 and hard_pct >= 5:
            classification = "pyramidal"
            class_note = (
                "Pyramidal distribution — majority of work is easy with moderate threshold work. "
                "Effective model for many amateur athletes."
            )
        elif moderate_pct > 30:
            classification = "threshold-heavy"
            class_note = (
                "Threshold-heavy distribution — high proportion of moderate Z3 work. "
                "Often leads to chronic fatigue without maximising adaptation. "
                "Consider reducing Z3 and shifting either easier or harder."
            )
        else:
            classification = "mixed"
            class_note = "Distribution does not match a standard model cleanly. Review session intensity targets."

        gap_vs_polarized = {
            "easy_gap": round(easy_pct - polarized_target["easy"], 1),
            "moderate_gap": round(moderate_pct - polarized_target["moderate"], 1),
            "hard_gap": round(hard_pct - polarized_target["hard"], 1),
        }

        return {
            "weeks_analysed": weeks,
            "total_hours": round(total_min / 60, 1),
            "athlete_thresholds": thresholds,
            "distribution_pct": {
                "easy": easy_pct,
                "moderate": moderate_pct,
                "hard": hard_pct,
            },
            "distribution_hours": {
                "easy": round(easy_min / 60, 1),
                "moderate": round(moderate_min / 60, 1),
                "hard": round(hard_min / 60, 1),
            },
            "classification": classification,
            "classification_note": class_note,
            "canonical_targets": canonical_targets,
            "gap_vs_polarized": gap_vs_polarized,
            "interpretation": f"{easy_pct}% easy / {moderate_pct}% moderate / {hard_pct}% hard. "
            + class_note,
            "caveat": caveat,
        }

    if sport in ("run", "ride"):
        return _fetch_and_classify(sport)

    # sport == "all": return nested overall + run + ride
    return {
        "overall": _fetch_and_classify("all"),
        "run": _fetch_and_classify("run"),
        "ride": _fetch_and_classify("ride"),
    }


def get_best_recent_run(conn, lookback_days: int = 365) -> dict | None:
    """
    Return the best recent running performance from the activities table.

    Selection strategy: among all runs longer than 3 km in the last
    *lookback_days* days, pick the one with the longest distance; break
    ties by fastest pace (lowest moving_time / distance).

    Parameters
    ----------
    conn:
        SQLite connection with row_factory set.
    lookback_days:
        How far back to look.  Default 365 days.

    Returns
    -------
    dict with keys: activity_id, date, distance_km, time_seconds, pace_sec_per_km
    or None if no qualifying run is found.
    """
    cutoff = (date.today() - timedelta(days=lookback_days)).isoformat()
    row = conn.execute(
        """
        SELECT
            id,
            date(start_date) AS day,
            distance,
            moving_time
        FROM activities
        WHERE sport_type LIKE '%Run%'
          AND distance > 3000
          AND moving_time > 0
          AND date(start_date) >= ?
        ORDER BY distance DESC, (CAST(moving_time AS REAL) / distance) ASC
        LIMIT 1
        """,
        (cutoff,),
    ).fetchone()

    if row is None:
        return None

    d_km = row["distance"] / 1000.0
    t_s = row["moving_time"]
    return {
        "activity_id": row["id"],
        "date": row["day"],
        "distance_km": round(d_km, 2),
        "time_seconds": t_s,
        "pace_sec_per_km": round(t_s / d_km, 1),
    }
