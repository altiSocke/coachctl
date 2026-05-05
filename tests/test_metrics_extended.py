"""
Extended tests for coachctl.metrics — DB-backed functions, pace_zones,
zone_distribution, and monotony from DB.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from coachctl.metrics import (
    get_current_fitness,
    get_daily_tss_from_db,
    get_zone_distribution_from_db,
    pace_zones,
    power_zones,
)


# ── Mock athlete fixture ──────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def mock_athlete(monkeypatch):
    athlete = {"ftp": 250, "rftp": 270, "threshold_hr": 170, "resting_hr": 50}
    monkeypatch.setattr("coachctl.config.load_athlete", lambda: athlete)
    monkeypatch.setattr("coachctl.metrics.load_athlete", lambda: athlete, raising=False)


# ── pace_zones ────────────────────────────────────────────────────────────────


def test_pace_zones_has_expected_keys():
    zones = pace_zones(270.0)
    for key in ("Z1_Easy", "Z2_Aerobic", "Z3_Tempo", "Z4_Threshold", "Z5_VO2max", "Z6_Anaerobic"):
        assert key in zones


def test_pace_zones_threshold_in_z4():
    rftp = 270.0
    zones = pace_zones(rftp)
    lo, hi = zones["Z4_Threshold"]
    assert lo <= rftp <= hi


def test_pace_zones_z1_slowest():
    """Z1 should be the slowest zone (highest sec/km values)."""
    zones = pace_zones(270.0)
    z1_lo, z1_hi = zones["Z1_Easy"]
    z5_lo, z5_hi = zones["Z5_VO2max"]
    assert z1_lo > z5_lo  # slower = more sec/km


def test_pace_zones_scale_with_rftp():
    """Faster threshold (lower sec/km) → faster zones."""
    zones_slow = pace_zones(320.0)  # 5:20/km threshold
    zones_fast = pace_zones(240.0)  # 4:00/km threshold
    assert zones_fast["Z4_Threshold"][0] < zones_slow["Z4_Threshold"][0]


# ── power_zones extended ──────────────────────────────────────────────────────


def test_power_zones_z7_upper_bound():
    zones = power_zones(250)
    assert zones["Z7_Neuromuscular"][1] == 9999


def test_power_zones_z1_starts_at_zero():
    zones = power_zones(250)
    assert zones["Z1_Active_Recovery"][0] == 0


# ── get_daily_tss_from_db ─────────────────────────────────────────────────────


@pytest.fixture
def conn_with_activities(mem_db):
    with mem_db() as conn:
        conn.executemany(
            """INSERT INTO activities (id, name, sport_type, start_date, moving_time, tss)
               VALUES (?,?,?,?,?,?)""",
            [
                (1, "Run 1", "Run", "2026-04-01T07:00:00Z", 3600, 80.0),
                (2, "Run 2", "Run", "2026-04-02T07:00:00Z", 3600, 90.0),
                (3, "Ride 1", "Ride", "2026-04-01T17:00:00Z", 7200, 120.0),
                (4, "Swim", "Swim", "2026-04-03T08:00:00Z", 1800, 40.0),
                (5, "No TSS Run", "Run", "2026-04-04T08:00:00Z", 3600, None),
            ]
        )
    return mem_db


def test_get_daily_tss_all(conn_with_activities):
    with conn_with_activities() as conn:
        daily = get_daily_tss_from_db(conn, "all")
    assert date(2026, 4, 1) in daily
    assert daily[date(2026, 4, 1)] == pytest.approx(200.0)  # run + ride


def test_get_daily_tss_run_only(conn_with_activities):
    with conn_with_activities() as conn:
        daily = get_daily_tss_from_db(conn, "run")
    assert date(2026, 4, 1) in daily
    assert daily[date(2026, 4, 1)] == pytest.approx(80.0)
    assert date(2026, 4, 3) not in daily  # Swim excluded


def test_get_daily_tss_ride_only(conn_with_activities):
    with conn_with_activities() as conn:
        daily = get_daily_tss_from_db(conn, "ride")
    assert date(2026, 4, 1) in daily
    assert daily[date(2026, 4, 1)] == pytest.approx(120.0)


def test_get_daily_tss_excludes_null_tss(conn_with_activities):
    with conn_with_activities() as conn:
        daily = get_daily_tss_from_db(conn, "run")
    assert date(2026, 4, 4) not in daily


def test_get_daily_tss_invalid_category(conn_with_activities):
    with conn_with_activities() as conn:
        with pytest.raises(ValueError, match="Unknown sport_category"):
            get_daily_tss_from_db(conn, "swim")


def test_get_daily_tss_empty_db(mem_db):
    with mem_db() as conn:
        daily = get_daily_tss_from_db(conn, "all")
    assert daily == {}


# ── get_current_fitness ───────────────────────────────────────────────────────


def test_get_current_fitness_empty_db(mem_db):
    with mem_db() as conn:
        result = get_current_fitness(conn)
    assert result["ctl"] == 0
    assert result["atl"] == 0
    assert result["tsb"] == 0


def test_get_current_fitness_with_data(conn_with_activities):
    with conn_with_activities() as conn:
        result = get_current_fitness(conn)
    assert result["ctl"] >= 0
    assert result["atl"] >= 0
    assert "date" in result


# ── get_zone_distribution_from_db ─────────────────────────────────────────────


def test_zone_distribution_no_hr_data(mem_db):
    with mem_db() as conn:
        result = get_zone_distribution_from_db(conn, weeks=8)
    assert "error" in result


def test_zone_distribution_with_hr_data(mem_db):
    with mem_db() as conn:
        # Insert activity with HR data in the last 8 weeks
        conn.execute(
            """INSERT INTO activities (id, name, sport_type, start_date, moving_time, average_heartrate, tss)
               VALUES (?,?,?,?,?,?,?)""",
            (100, "Easy Run", "Run", "2026-04-25T07:00:00Z", 3600, 140.0, 70.0),
        )
        result = get_zone_distribution_from_db(conn, weeks=8)
    assert "zone_pct" in result
    assert "total_hours" in result
    assert "polarization_index" in result
    total_pct = sum(result["zone_pct"].values())
    assert total_pct == pytest.approx(100.0, abs=1.0)
