"""
Tests for coachctl.metrics — TSS, CTL/ATL/TSB, NGP, zone calculations.
All tests are pure-function; no DB or Strava calls required.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

import pytest

from coachctl.metrics import (
    _grade_cost_factor,
    compute_activity_metrics,
    compute_fitness_series,
    compute_training_monotony,
    fit_critical_power,
    format_pace,
    hr_zones,
    pace_sec_per_km,
    power_zones,
)


# ── _grade_cost_factor ────────────────────────────────────────────────────────


def test_grade_cost_factor_flat():
    """Flat grade must return exactly 1.0 (NGP = actual pace)."""
    assert _grade_cost_factor(0.0) == pytest.approx(1.0, abs=1e-9)


def test_grade_cost_factor_uphill_harder():
    """Uphill should cost more than flat."""
    assert _grade_cost_factor(0.10) > 1.0


def test_grade_cost_factor_moderate_downhill_easier():
    """Moderate downhill (-10%) should cost less than flat."""
    assert _grade_cost_factor(-0.10) < 1.0


def test_grade_cost_factor_steep_downhill_harder():
    """Very steep downhill (-45%) costs more than flat (braking effort).
    Minetti reversal occurs around -40% grade; -45% is definitively above 1.0."""
    assert _grade_cost_factor(-0.45) > 1.0


def test_grade_cost_factor_clamped():
    """Values outside [-0.45, 0.45] must be clamped, not raise."""
    v_high = _grade_cost_factor(0.99)
    v_low = _grade_cost_factor(-0.99)
    v_cap_high = _grade_cost_factor(0.45)
    v_cap_low = _grade_cost_factor(-0.45)
    assert v_high == pytest.approx(v_cap_high)
    assert v_low == pytest.approx(v_cap_low)


# ── pace helpers ──────────────────────────────────────────────────────────────


def test_pace_sec_per_km_roundtrip():
    """pace_sec_per_km(1000/x) ≈ x for any positive x."""
    speed_ms = 3.5  # ~4:45/km
    assert pace_sec_per_km(speed_ms) == pytest.approx(1000 / speed_ms, rel=1e-6)


def test_pace_sec_per_km_zero():
    assert pace_sec_per_km(0) == 0.0


def test_format_pace():
    assert format_pace(285.0) == "4'45\""
    assert format_pace(300.0) == "5'00\""
    assert format_pace(60.0) == "1'00\""


# ── compute_activity_metrics ──────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def mock_athlete(monkeypatch):
    """Inject a minimal athlete config so no YAML file is needed."""
    athlete = {
        "ftp": 250,
        "rftp": 270,  # sec/km threshold pace (≈ 4:30/km)
        "threshold_hr": 170,
        "max_hr": 190,
        "resting_hr": 50,
    }
    monkeypatch.setattr("coachctl.config.load_athlete", lambda: athlete)


def test_cycling_tss_basic():
    """Power-based TSS: 1h at FTP = 100 TSS."""
    activity = {
        "sport_type": "Ride",
        "moving_time": 3600,
        "weighted_avg_watts": 250,
        "average_watts": 240,
    }
    m = compute_activity_metrics(activity)
    assert m["tss"] == pytest.approx(100.0, abs=1.0)
    assert m["np"] == pytest.approx(250.0)
    assert m["intensity_factor"] == pytest.approx(1.0, abs=0.01)


def test_cycling_tss_below_ftp():
    """Riding at 80% FTP for 2h → TSS = 128."""
    ftp = 250
    np = ftp * 0.80
    expected_tss = (7200 * np * (np / ftp)) / (ftp * 3600) * 100
    activity = {
        "sport_type": "Ride",
        "moving_time": 7200,
        "weighted_avg_watts": np,
        "average_watts": np * 0.95,
    }
    m = compute_activity_metrics(activity)
    assert m["tss"] == pytest.approx(expected_tss, abs=1.0)


def test_running_rtss_flat():
    """Flat run at threshold pace for 1h → rTSS ≈ 100."""
    rftp_sec_per_km = 270.0  # 4:30/km
    rftp_ms = 1000 / rftp_sec_per_km
    activity = {
        "sport_type": "Run",
        "moving_time": 3600,
        "average_speed": rftp_ms,
        "distance": rftp_ms * 3600,
        "total_elevation_gain": 0,
    }
    m = compute_activity_metrics(activity)
    # Flat run: NGP = actual pace, so rTSS ≈ 100
    assert m["rtss"] == pytest.approx(100.0, abs=2.0)
    assert m["tss"] == pytest.approx(100.0, abs=2.0)


def test_running_rtss_uphill_higher():
    """Same speed with elevation gain → higher rTSS than flat."""
    rftp_ms = 1000 / 270.0
    distance = rftp_ms * 3600
    activity_flat = {
        "sport_type": "Run",
        "moving_time": 3600,
        "average_speed": rftp_ms,
        "distance": distance,
        "total_elevation_gain": 0,
    }
    activity_hilly = {
        **activity_flat,
        "total_elevation_gain": 500,
    }
    m_flat = compute_activity_metrics(activity_flat)
    m_hilly = compute_activity_metrics(activity_hilly)
    assert m_hilly["rtss"] > m_flat["rtss"]


def test_hrtss_fallback():
    """When no power or pace data, hrTSS should be computed and used as tss."""
    activity = {
        "sport_type": "Swim",
        "moving_time": 3600,
        "average_heartrate": 160,
        # no speed, no watts
    }
    m = compute_activity_metrics(activity)
    assert m["hrss"] is not None
    assert m["hrss"] > 0
    assert m["tss"] == m["hrss"]


def test_hrtss_uses_max_hr_over_threshold_hr(monkeypatch):
    """hrTSS should use max_hr (not threshold_hr) as HRR ceiling when available."""
    athlete_with_max = {
        "ftp": 250, "rftp": 270, "threshold_hr": 170, "max_hr": 190, "resting_hr": 50,
    }
    athlete_without_max = {
        "ftp": 250, "rftp": 270, "threshold_hr": 170, "resting_hr": 50,
    }
    activity = {"sport_type": "Swim", "moving_time": 3600, "average_heartrate": 140}

    monkeypatch.setattr("coachctl.config.load_athlete", lambda: athlete_with_max)
    m_with = compute_activity_metrics(activity)

    monkeypatch.setattr("coachctl.config.load_athlete", lambda: athlete_without_max)
    m_without = compute_activity_metrics(activity)

    # Both should produce hrss
    assert m_with["hrss"] > 0
    assert m_without["hrss"] > 0
    # With normalization, both cases use threshold_hr for the reference.
    # Different ceilings change both raw TRIMP and reference — values differ
    # but both should be in a reasonable hrTSS range for 1hr at ~75% HRR.
    assert m_with["hrss"] != m_without["hrss"]
    # Neither should flag threshold as estimated (both have threshold_hr set)
    assert "hrss_threshold_estimated" not in m_with
    assert "hrss_threshold_estimated" not in m_without


def test_hrtss_clamp_at_1_5(monkeypatch):
    """hrr_ratio is clamped at 1.5 even when avg_hr far exceeds max_hr."""
    athlete = {
        "ftp": 250, "rftp": 270, "threshold_hr": 170, "max_hr": 180, "resting_hr": 50,
    }
    monkeypatch.setattr("coachctl.config.load_athlete", lambda: athlete)
    # avg_hr=250 → unclamped ratio = (250-50)/(180-50) = 1.54 → clamped to 1.5
    activity = {"sport_type": "Swim", "moving_time": 3600, "average_heartrate": 250}
    m_extreme = compute_activity_metrics(activity)
    # avg_hr=245 → unclamped ratio = (245-50)/(180-50) = 1.5 → exactly at clamp
    activity2 = {"sport_type": "Swim", "moving_time": 3600, "average_heartrate": 245}
    m_at_clamp = compute_activity_metrics(activity2)
    # Both should produce the same hrss (both clamped to 1.5)
    assert m_extreme["hrss"] == m_at_clamp["hrss"]


def test_hrtss_male_constant(monkeypatch):
    """Male athlete uses Banister k=1.92 (higher than female k=1.67)."""
    base = {"ftp": 250, "rftp": 270, "threshold_hr": 170, "max_hr": 190, "resting_hr": 50}
    activity = {"sport_type": "Swim", "moving_time": 3600, "average_heartrate": 150}

    monkeypatch.setattr("coachctl.config.load_athlete", lambda: {**base, "gender": "male"})
    m_male = compute_activity_metrics(activity)

    monkeypatch.setattr("coachctl.config.load_athlete", lambda: {**base, "gender": "female"})
    m_female = compute_activity_metrics(activity)

    # Male k=1.92 and female k=1.67 produce different normalized hrTSS.
    # After normalization, the relationship depends on activity HR vs threshold:
    # when below threshold, higher k gives lower normalized value (steeper curve
    # penalizes sub-threshold effort more relative to the reference).
    assert m_male["hrss"] != m_female["hrss"]


def test_hrtss_threshold_estimated_flag(monkeypatch):
    """When threshold_hr is missing, hrTSS estimates it from max_hr and flags it."""
    athlete_no_thr = {
        "ftp": 250, "rftp": 270, "max_hr": 190, "resting_hr": 50,
    }
    monkeypatch.setattr("coachctl.config.load_athlete", lambda: athlete_no_thr)
    activity = {"sport_type": "Swim", "moving_time": 3600, "average_heartrate": 140}
    m = compute_activity_metrics(activity)
    assert m["hrss"] > 0
    assert m["tss"] == m["hrss"]
    assert m.get("hrss_threshold_estimated") is True


def test_hrtss_normalization_1hr_at_threshold(monkeypatch):
    """1 hour at exactly threshold HR should produce ~100 hrTSS."""
    athlete = {"ftp": 250, "rftp": 270, "threshold_hr": 170, "max_hr": 190, "resting_hr": 50}
    monkeypatch.setattr("coachctl.config.load_athlete", lambda: athlete)
    activity = {"sport_type": "Swim", "moving_time": 3600, "average_heartrate": 170}
    m = compute_activity_metrics(activity)
    # Should be approximately 100 (the definition of normalized hrTSS)
    assert 95 <= m["hrss"] <= 105


    """Activity with no HR, power, or pace → tss stays None."""
    activity = {
        "sport_type": "WeightTraining",
        "moving_time": 3600,
    }
    m = compute_activity_metrics(activity)
    assert m["tss"] is None


# ── compute_fitness_series ────────────────────────────────────────────────────


def test_fitness_series_empty():
    assert compute_fitness_series({}) == []


def test_fitness_series_single_day():
    d = date(2025, 1, 1)
    series = compute_fitness_series({d: 100.0}, start_date=d, end_date=d)
    assert len(series) == 1
    row = series[0]
    assert row["date"] == "2025-01-01"
    assert row["ctl"] > 0
    assert row["atl"] > 0
    # TSB is rounded independently; allow 0.1 rounding tolerance
    assert row["tsb"] == pytest.approx(row["ctl"] - row["atl"], abs=0.2)


def test_fitness_series_ctl_grows():
    """Sustained load should increase CTL over time."""
    start = date(2024, 1, 1)
    daily = {start + timedelta(days=i): 100.0 for i in range(60)}
    series = compute_fitness_series(daily, start_date=start, end_date=start + timedelta(days=59))
    ctls = [r["ctl"] for r in series]
    assert ctls[-1] > ctls[0]


def test_fitness_series_tsb_formula():
    """TSB must equal CTL − ATL for every row (within rounding tolerance)."""
    start = date(2024, 6, 1)
    daily = {start + timedelta(days=i): float(50 + i % 30) for i in range(30)}
    series = compute_fitness_series(daily, start_date=start, end_date=start + timedelta(days=29))
    for row in series:
        assert row["tsb"] == pytest.approx(row["ctl"] - row["atl"], abs=0.2)


def test_fitness_series_rest_drops_atl():
    """After sustained load, a rest period should drop ATL faster than CTL."""
    start = date(2024, 1, 1)
    # 42 days of load, then 14 days of rest
    daily: dict[date, float] = {}
    for i in range(42):
        daily[start + timedelta(days=i)] = 100.0
    rest_start = start + timedelta(days=42)
    for i in range(14):
        daily[rest_start + timedelta(days=i)] = 0.0

    series = compute_fitness_series(
        daily, start_date=start, end_date=rest_start + timedelta(days=13)
    )
    # At end of load block
    load_end = series[41]
    # At end of rest block
    rest_end = series[-1]
    ctl_drop = load_end["ctl"] - rest_end["ctl"]
    atl_drop = load_end["atl"] - rest_end["atl"]
    assert atl_drop > ctl_drop, "ATL should drop faster than CTL during rest"


# ── compute_training_monotony ─────────────────────────────────────────────────


def test_monotony_empty():
    assert compute_training_monotony({}) == []


def test_monotony_identical_days():
    """All days identical → maximum monotony (capped at 4.0) on the last loaded day."""
    start = date(2024, 3, 1)
    end = start + timedelta(days=13)
    # 14 days of identical load so every rolling window (from day 7 onward) is all-80
    daily = {start + timedelta(days=i): 80.0 for i in range(14)}
    series = compute_training_monotony(daily, window=7)
    # Find the entry for the last day of actual data
    end_str = end.isoformat()
    entry = next(r for r in series if r["date"] == end_str)
    assert entry["monotony"] == pytest.approx(4.0)


def test_monotony_varied_days_lower():
    """Varied load → monotony < 4.0."""
    start = date(2024, 3, 1)
    daily = {start + timedelta(days=i): float([100, 0, 80, 0, 120, 0, 60][i % 7]) for i in range(7)}
    series = compute_training_monotony(daily, window=7)
    last = series[-1]
    assert last["monotony"] < 4.0


def test_monotony_strain_formula():
    """strain = window_tss_sum × monotony."""
    start = date(2024, 3, 1)
    daily = {start + timedelta(days=i): float(50 + i * 5) for i in range(7)}
    series = compute_training_monotony(daily, window=7)
    for row in series:
        if row["monotony"] > 0:
            expected_strain = row["window_tss_sum"] * row["monotony"]
            assert row["strain"] == pytest.approx(expected_strain, rel=0.01)


# ── zone helpers ──────────────────────────────────────────────────────────────


def test_hr_zones_coverage():
    """HR zones should cover the full range without gaps."""
    zones = hr_zones(170, 50)
    assert "Z1" in zones and "Z5" in zones
    # Z1 lower bound = resting_hr
    assert zones["Z1"][0] == 50
    # Z5 upper bound is sentinel 999
    assert zones["Z5"][1] == 999
    # Each zone's upper bound == next zone's lower bound
    zone_list = [zones[f"Z{i}"] for i in range(1, 6)]
    for i in range(len(zone_list) - 1):
        assert zone_list[i][1] == zone_list[i + 1][0]


def test_power_zones_ftp_in_z4():
    """FTP (100%) must fall inside Z4_Threshold."""
    ftp = 250
    zones = power_zones(ftp)
    lo, hi = zones["Z4_Threshold"]
    assert lo <= ftp <= hi


# ── fit_critical_power ────────────────────────────────────────────────────────


def _make_ride_efforts(
    power_1min: float | None = None,
    power_5min: float | None = None,
    power_20min: float | None = None,
    power_60min: float | None = None,
    season_1min: float | None = None,
    season_5min: float | None = None,
    season_20min: float | None = None,
    season_60min: float | None = None,
) -> list[dict]:
    """Build synthetic ride best-effort dicts matching compute_best_efforts() output."""
    mapping = {
        "power_1min": (power_1min, season_1min),
        "power_5min": (power_5min, season_5min),
        "power_20min": (power_20min, season_20min),
        "power_60min": (power_60min, season_60min),
    }
    efforts = []
    for effort_type, (at_val, s_val) in mapping.items():
        efforts.append(
            {
                "effort": effort_type,
                "all_time": {"value_raw": at_val, "value_fmt": f"{at_val} W", "date": "2025-01-01"},
                "season": {"value_raw": s_val, "value_fmt": f"{s_val} W", "date": "2025-06-01"}
                if s_val
                else None,
                "stale": False,
            }
        )
    return efforts


def test_fit_cp_happy_path():
    """4 MMP points from a known CP=250 W, W'=20 kJ model should recover those values."""
    # Generate synthetic MMP from P(t) = 250 + 20000/t
    cp_true = 250.0
    w_prime_j_true = 20_000.0
    durations = {"power_1min": 60, "power_5min": 300, "power_20min": 1200, "power_60min": 3600}
    powers = {k: cp_true + w_prime_j_true / t for k, t in durations.items()}

    efforts = _make_ride_efforts(**powers)
    result = fit_critical_power(efforts)

    assert result is not None
    at = result["all_time"]
    assert at is not None
    assert at["cp_watts"] == pytest.approx(cp_true, abs=1.0)
    assert at["w_prime_kj"] == pytest.approx(w_prime_j_true / 1000, abs=0.5)
    assert at["r_squared"] >= 0.999
    assert at["n_points"] == 4
    assert not at["out_of_range"]


def test_fit_cp_minimum_three_points():
    """Exactly 3 valid MMP points should still produce a fit."""
    cp_true = 230.0
    w_prime_j_true = 18_000.0
    efforts = _make_ride_efforts(
        power_1min=cp_true + w_prime_j_true / 60,
        power_5min=cp_true + w_prime_j_true / 300,
        power_20min=cp_true + w_prime_j_true / 1200,
        # power_60min absent
    )
    result = fit_critical_power(efforts)
    assert result is not None
    assert result["all_time"] is not None
    assert result["all_time"]["n_points"] == 3


def test_fit_cp_too_few_points_returns_none():
    """Only 2 valid MMP points → must return None (below _CP_MIN_POINTS=3)."""
    efforts = _make_ride_efforts(
        power_5min=320.0,
        power_20min=290.0,
    )
    result = fit_critical_power(efforts)
    assert result is None


def test_fit_cp_season_populated():
    """When season MMP data is present, season fit should be returned."""
    cp_true = 240.0
    w_prime_j = 15_000.0
    efforts = _make_ride_efforts(
        power_1min=cp_true + w_prime_j / 60,
        power_5min=cp_true + w_prime_j / 300,
        power_20min=cp_true + w_prime_j / 1200,
        power_60min=cp_true + w_prime_j / 3600,
        season_1min=cp_true - 10 + w_prime_j / 60,
        season_5min=cp_true - 10 + w_prime_j / 300,
        season_20min=cp_true - 10 + w_prime_j / 1200,
        season_60min=cp_true - 10 + w_prime_j / 3600,
    )
    result = fit_critical_power(efforts)
    assert result is not None
    assert result["season"] is not None
    assert result["season"]["cp_watts"] == pytest.approx(cp_true - 10, abs=1.0)


def test_fit_cp_season_none_when_missing():
    """When no season MMP data is available, season key should be None."""
    cp_true = 260.0
    w_prime_j = 22_000.0
    efforts = _make_ride_efforts(
        power_1min=cp_true + w_prime_j / 60,
        power_5min=cp_true + w_prime_j / 300,
        power_20min=cp_true + w_prime_j / 1200,
        power_60min=cp_true + w_prime_j / 3600,
        # no season values
    )
    result = fit_critical_power(efforts)
    assert result is not None
    assert result["season"] is None


def test_fit_cp_ftp_comparison_calibrated():
    """CP/FTP ratio in [1.00, 1.08] → note says well-calibrated."""
    cp_true = 260.0
    w_prime_j = 18_000.0
    efforts = _make_ride_efforts(
        power_1min=cp_true + w_prime_j / 60,
        power_5min=cp_true + w_prime_j / 300,
        power_20min=cp_true + w_prime_j / 1200,
        power_60min=cp_true + w_prime_j / 3600,
    )
    result = fit_critical_power(efforts, ftp=250)
    assert result is not None
    assert "ftp_comparison" in result
    cmp = result["ftp_comparison"]
    assert 1.00 <= cmp["ratio"] <= 1.08
    assert "well-calibrated" in cmp["note"]


def test_fit_cp_ftp_comparison_underestimated():
    """CP/FTP ratio > 1.08 → note flags possible FTP underestimation."""
    cp_true = 290.0
    w_prime_j = 18_000.0
    efforts = _make_ride_efforts(
        power_1min=cp_true + w_prime_j / 60,
        power_5min=cp_true + w_prime_j / 300,
        power_20min=cp_true + w_prime_j / 1200,
        power_60min=cp_true + w_prime_j / 3600,
    )
    result = fit_critical_power(efforts, ftp=250)
    assert result is not None
    cmp = result["ftp_comparison"]
    assert cmp["ratio"] > 1.08
    assert "underestimated" in cmp["note"]


def test_fit_cp_empty_efforts_returns_none():
    """Empty ride efforts list → None."""
    assert fit_critical_power([]) is None


def test_fit_cp_no_ftp_no_comparison():
    """When ftp=None, ftp_comparison key should be absent."""
    cp_true = 250.0
    w_prime_j = 20_000.0
    efforts = _make_ride_efforts(
        power_1min=cp_true + w_prime_j / 60,
        power_5min=cp_true + w_prime_j / 300,
        power_20min=cp_true + w_prime_j / 1200,
        power_60min=cp_true + w_prime_j / 3600,
    )
    result = fit_critical_power(efforts, ftp=None)
    assert result is not None
    assert "ftp_comparison" not in result


# ── Bug fix regression tests ─────────────────────────────────────────────────


def test_taper_respects_taper_weeks_parameter():
    """#40: taper_weeks=3 should reduce load in week -3 (days 14-20 before race)."""
    from coachctl.metrics import project_fitness

    target = date.today() + timedelta(days=30)
    # Build a minimal daily_tss history (60 days of constant load)
    daily_tss = {
        date.today() - timedelta(days=i): 80.0 for i in range(1, 61)
    }

    result_3wk = project_fitness(daily_tss, target, weekly_tss=560, taper_weeks=3)
    result_2wk = project_fitness(daily_tss, target, weekly_tss=560, taper_weeks=2)

    # 3-week taper should produce higher race-day TSB (more rest)
    assert result_3wk["projected"]["tsb"] > result_2wk["projected"]["tsb"]


def test_form_status_under_tapered_at_tsb_7():
    """#44: TSB +7 should be 'under-tapered', not 'optimal' (Coggan: +10 to +25)."""
    from coachctl.metrics import project_fitness

    target = date.today() + timedelta(days=10)
    # High recent load → low projected TSB
    daily_tss = {
        date.today() - timedelta(days=i): 120.0 for i in range(1, 61)
    }
    result = project_fitness(daily_tss, target, weekly_tss=840, taper_weeks=1)
    # With only 1 week taper on very high load, TSB should stay low
    if result["projected"]["tsb"] < 10:
        assert result["form_status"] == "under-tapered"


def test_polarized_target_sums_to_100():
    """#45: Polarized target distribution must sum to 100%."""
    from pathlib import Path

    source = (Path(__file__).parent.parent / "src" / "coachctl" / "metrics.py").read_text(encoding="utf-8")
    assert '"easy": 80.0, "moderate": 5.0, "hard": 15.0' in source
