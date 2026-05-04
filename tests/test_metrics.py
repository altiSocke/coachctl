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


def test_no_tss_when_no_data():
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

    series = compute_fitness_series(daily, start_date=start, end_date=rest_start + timedelta(days=13))
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
