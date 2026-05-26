"""
Extended tests for coachctl.metrics — DB-backed functions, pace_zones,
zone_distribution, monotony from DB, ACWR, session TSS estimation, VO2max.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from coachctl.metrics import (
    compute_acwr,
    compute_acwr_series,
    estimate_session_tss,
    estimate_vo2max_cycling,
    estimate_vo2max_running,
    estimate_vo2max_from_athlete,
    estimate_week_tss,
    get_acwr_from_db,
    get_best_recent_run,
    get_current_fitness,
    get_daily_tss_from_db,
    get_zone_distribution_from_db,
    pace_zones,
    power_zones,
    predict_race_times,
    riegel_predict,
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
            ],
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


# ── compute_acwr ──────────────────────────────────────────────────────────────


def _daily_tss(base_date: date, values: list[float]) -> dict[date, float]:
    """Helper: build a daily_tss dict from a list of values starting at base_date."""
    return {base_date + timedelta(days=i): v for i, v in enumerate(values)}


def test_acwr_empty():
    result = compute_acwr({})
    assert result["acwr_rolling"] is None
    assert result["acwr_ema"] is None
    assert result["risk_zone"] == "unknown"


def test_acwr_optimal_zone():
    """28 days of 80 TSS/day → ACWR ≈ 1.0 (optimal zone)."""
    today = date.today()
    daily = {today - timedelta(days=i): 80.0 for i in range(28)}
    result = compute_acwr(daily)
    assert result["acwr_rolling"] == pytest.approx(1.0, abs=0.05)
    assert result["risk_zone"] == "optimal"


def test_acwr_high_risk_after_spike():
    """Low chronic base + big acute spike → ACWR > 1.5 = high risk."""
    today = date.today()
    # 28 days at 30 TSS/day (low chronic base)
    daily = {today - timedelta(days=i): 30.0 for i in range(28)}
    # Then override last 7 days with 120 TSS/day (spike)
    for i in range(7):
        daily[today - timedelta(days=i)] = 120.0
    result = compute_acwr(daily)
    assert result["acwr_rolling"] > 1.5
    assert result["risk_zone"] == "high_risk"


def test_acwr_undertrained():
    """No training in last 7 days but chronic base from 28 days ago → ACWR < 0.8."""
    today = date.today()
    # 21+ days old training, recent 7 days = 0
    daily = {today - timedelta(days=i + 7): 80.0 for i in range(21)}
    result = compute_acwr(daily)
    assert result["acwr_rolling"] < 0.8
    assert result["risk_zone"] == "undertrained"


def test_acwr_ema_variant_present():
    """EMA variant should always be present when there is training data."""
    today = date.today()
    daily = {today - timedelta(days=i): 60.0 for i in range(28)}
    result = compute_acwr(daily)
    assert result["acwr_ema"] is not None
    assert result["acwr_ema"] > 0


def test_acwr_loads_are_rounded():
    """acute_load and chronic_load should be rounded floats."""
    today = date.today()
    daily = {today - timedelta(days=i): 75.5 for i in range(28)}
    result = compute_acwr(daily)
    assert isinstance(result["acute_load"], float)
    assert isinstance(result["chronic_load"], float)


def test_acwr_from_db(conn_with_activities):
    """get_acwr_from_db should return a dict with acwr_rolling key."""
    with conn_with_activities() as conn:
        result = get_acwr_from_db(conn)
    assert "acwr_rolling" in result
    assert "risk_zone" in result
    assert "interpretation" in result


def test_acwr_window_params():
    """Custom short/long windows should be reflected in the return dict."""
    today = date.today()
    daily = {today - timedelta(days=i): 50.0 for i in range(42)}
    result = compute_acwr(daily, short_days=14, long_days=42)
    assert result["acute_window_days"] == 14
    assert result["chronic_window_days"] == 42


def test_acwr_series_matches_single_call():
    """compute_acwr_series() should match compute_acwr() for today's date."""
    today = date.today()
    daily = {today - timedelta(days=i): 80.0 if i > 7 else 50.0 for i in range(28)}
    single = compute_acwr(daily)
    series = compute_acwr_series(daily)
    today_val = series[today.isoformat()]
    assert today_val["acwr_rolling"] == pytest.approx(single["acwr_rolling"], abs=0.05)
    assert today_val["acwr_ema"] == pytest.approx(single["acwr_ema"], abs=0.05)
    assert today_val["risk_zone"] == single["risk_zone"]


def test_acwr_series_empty():
    """Empty input returns empty dict."""
    assert compute_acwr_series({}) == {}


def test_acwr_series_covers_all_days():
    """Series should have an entry for every day from first data to today."""
    today = date.today()
    start = today - timedelta(days=30)
    daily = {start + timedelta(days=i): 60.0 for i in range(31)}
    series = compute_acwr_series(daily)
    expected_days = (today - start).days + 1
    assert len(series) == expected_days


# ── estimate_session_tss ──────────────────────────────────────────────────────


def test_session_tss_threshold_one_hour():
    """1h at threshold intensity must equal 100 TSS by definition."""
    result = estimate_session_tss(60.0, "threshold")
    assert result["tss_estimate"] == pytest.approx(100.0, abs=0.1)


def test_session_tss_easy_less_than_threshold():
    """Easy session at the same duration must produce less TSS than threshold."""
    easy = estimate_session_tss(60.0, "easy")
    threshold = estimate_session_tss(60.0, "threshold")
    assert easy["tss_estimate"] < threshold["tss_estimate"]


def test_session_tss_duration_scales_linearly():
    """Doubling duration at the same intensity should double TSS."""
    r1 = estimate_session_tss(60.0, "moderate")
    r2 = estimate_session_tss(120.0, "moderate")
    assert r2["tss_estimate"] == pytest.approx(r1["tss_estimate"] * 2, rel=0.01)


def test_session_tss_intensity_ordering():
    """TSS ordering: recovery < easy < moderate < tempo < threshold < vo2max < anaerobic."""
    levels = ["recovery", "easy", "moderate", "tempo", "threshold", "vo2max", "anaerobic"]
    tss_values = [estimate_session_tss(60.0, lvl)["tss_estimate"] for lvl in levels]
    for i in range(len(tss_values) - 1):
        assert tss_values[i] < tss_values[i + 1], (
            f"{levels[i]} ({tss_values[i]}) should be < {levels[i + 1]} ({tss_values[i + 1]})"
        )


def test_session_tss_invalid_intensity():
    with pytest.raises(ValueError, match="Unknown intensity"):
        estimate_session_tss(60.0, "very_hard")


def test_session_tss_sport_label_passthrough():
    result = estimate_session_tss(45.0, "easy", sport="run")
    assert result["sport"] == "run"


def test_estimate_week_tss_sums_correctly():
    sessions = [
        {"duration_min": 60, "intensity": "easy"},
        {"duration_min": 45, "intensity": "threshold"},
        {"duration_min": 90, "intensity": "moderate"},
    ]
    total = estimate_week_tss(sessions)
    expected = (
        estimate_session_tss(60, "easy")["tss_estimate"]
        + estimate_session_tss(45, "threshold")["tss_estimate"]
        + estimate_session_tss(90, "moderate")["tss_estimate"]
    )
    assert total == pytest.approx(expected, rel=0.01)


# ── VO2max estimation ─────────────────────────────────────────────────────────


def test_vo2max_running_plausible_range():
    """A 4:30/km threshold pace should give VO2max in a realistic range (45–65)."""
    rftp = 270.0  # 4:30/km
    vo2 = estimate_vo2max_running(rftp)
    assert 45.0 <= vo2 <= 70.0


def test_vo2max_running_faster_threshold_higher_vo2():
    """Better runner (lower sec/km) should have higher VO2max estimate."""
    vo2_elite = estimate_vo2max_running(200.0)  # 3:20/km
    vo2_good = estimate_vo2max_running(270.0)  # 4:30/km
    vo2_avg = estimate_vo2max_running(360.0)  # 6:00/km
    assert vo2_elite > vo2_good > vo2_avg


def test_vo2max_running_zero_pace():
    assert estimate_vo2max_running(0.0) == 0.0


def test_vo2max_cycling_plausible_range():
    """FTP 250W at 70kg → ≈50–60 mL/kg/min range."""
    vo2 = estimate_vo2max_cycling(250.0, 70.0)
    assert 45.0 <= vo2 <= 70.0


def test_vo2max_cycling_better_power_to_weight_higher_vo2():
    """Higher W/kg → higher VO2max."""
    vo2_high = estimate_vo2max_cycling(350.0, 65.0)  # 5.4 W/kg
    vo2_mid = estimate_vo2max_cycling(250.0, 75.0)  # 3.3 W/kg
    assert vo2_high > vo2_mid


def test_vo2max_cycling_zero_weight():
    assert estimate_vo2max_cycling(250.0, 0.0) == 0.0


def test_vo2max_cycling_zero_ftp():
    assert estimate_vo2max_cycling(0.0, 70.0) == 0.0


def test_estimate_vo2max_from_athlete_no_data():
    result = estimate_vo2max_from_athlete({})
    assert result["consensus"] is None
    assert result["estimates"] == []


def test_estimate_vo2max_from_athlete_run_only():
    athlete = {"rftp": 270}
    result = estimate_vo2max_from_athlete(athlete)
    assert len(result["estimates"]) == 1
    assert result["estimates"][0]["method"] == "running_threshold_pace"
    assert result["consensus"] is not None


def test_estimate_vo2max_from_athlete_both_methods():
    athlete = {"rftp": 270, "ftp": 280, "weight_kg": 72}
    result = estimate_vo2max_from_athlete(athlete)
    assert len(result["estimates"]) == 2
    # Consensus is the average of both estimates
    methods = {e["method"] for e in result["estimates"]}
    assert "running_threshold_pace" in methods
    assert "cycling_ftp" in methods


def test_estimate_vo2max_interpretation_present():
    athlete = {"rftp": 270}
    result = estimate_vo2max_from_athlete(athlete)
    assert "interpretation" in result
    assert len(result["interpretation"]) > 0


# ── Riegel race time prediction ────────────────────────────────────────────────


class TestRiegelPredict:
    def test_same_distance_returns_same_time(self):
        """Predicting the same distance must return exactly the reference time."""
        assert riegel_predict(3600.0, 10.0, 10.0) == pytest.approx(3600.0)

    def test_double_distance_takes_more_than_double_time(self):
        """Exponent > 1.0 means time grows super-linearly with distance."""
        t2 = riegel_predict(3600.0, 10.0, 20.0)
        assert t2 > 2 * 3600.0

    def test_known_value_10k_to_marathon(self):
        """
        Riegel sanity check: a 52-minute 10k should predict ~4h00 marathon (3:55–4:05).
        52 min × (42.2/10)^1.06 ≈ 239 min.
        """
        t1 = 52 * 60  # 3120 seconds
        t_marathon = riegel_predict(float(t1), 10.0, 42.2)
        minutes = t_marathon / 60
        # 235–245 minute window (3:55–4:05)
        assert 235 <= minutes <= 245

    def test_ultra_exponent_gives_longer_prediction(self):
        """Ultra exponent (1.15) must produce longer time than road exponent (1.06)."""
        t_road = riegel_predict(3600.0, 10.0, 50.0, exponent=1.06)
        t_ultra = riegel_predict(3600.0, 10.0, 50.0, exponent=1.15)
        assert t_ultra > t_road

    def test_shorter_distance_returns_shorter_time(self):
        """Predicting a shorter distance should give a faster time."""
        t_5k = riegel_predict(3600.0, 10.0, 5.0)
        assert t_5k < 3600.0

    def test_invalid_time_raises(self):
        with pytest.raises(ValueError, match="t1_seconds"):
            riegel_predict(0.0, 10.0, 42.2)

    def test_negative_time_raises(self):
        with pytest.raises(ValueError, match="t1_seconds"):
            riegel_predict(-100.0, 10.0, 10.0)

    def test_invalid_d1_raises(self):
        with pytest.raises(ValueError, match="d1_km"):
            riegel_predict(3600.0, 0.0, 42.2)

    def test_invalid_d2_raises(self):
        with pytest.raises(ValueError, match="d2_km"):
            riegel_predict(3600.0, 10.0, 0.0)


class TestPredictRaceTimes:
    def test_returns_all_standard_distances(self):
        results = predict_race_times(3600.0, 10.0)
        labels = {r["distance_label"] for r in results}
        assert "5k" in labels
        assert "10k" in labels
        assert "Half marathon" in labels
        assert "Marathon" in labels
        assert "50k" in labels

    def test_road_mode_uses_1_06_exponent(self):
        results = predict_race_times(3600.0, 10.0, mode="road")
        assert all(r["exponent_used"] == 1.06 for r in results)

    def test_ultra_mode_uses_1_15_exponent(self):
        results = predict_race_times(3600.0, 10.0, mode="ultra")
        assert all(r["exponent_used"] == 1.15 for r in results)

    def test_ultra_mode_gives_longer_marathon_than_road(self):
        road = predict_race_times(3600.0, 10.0, mode="road")
        ultra = predict_race_times(3600.0, 10.0, mode="ultra")
        road_marathon = next(r for r in road if r["distance_label"] == "Marathon")
        ultra_marathon = next(r for r in ultra if r["distance_label"] == "Marathon")
        assert ultra_marathon["predicted_seconds"] > road_marathon["predicted_seconds"]

    def test_predictions_are_monotonically_increasing(self):
        """Longer distances must take longer."""
        results = predict_race_times(3600.0, 10.0)
        times = [r["predicted_seconds"] for r in results]
        assert times == sorted(times)

    def test_pace_formatted_present(self):
        results = predict_race_times(3600.0, 10.0)
        for r in results:
            assert "predicted_pace_formatted" in r
            assert len(r["predicted_pace_formatted"]) > 0

    def test_invalid_mode_raises(self):
        with pytest.raises(ValueError, match="Unknown mode"):
            predict_race_times(3600.0, 10.0, mode="swim")

    def test_reference_distance_included_in_results(self):
        """The 10k reference distance should be one of the returned rows."""
        results = predict_race_times(3600.0, 10.0)
        d10 = next(r for r in results if r["distance_label"] == "10k")
        # Prediction for d1 == d2 must equal reference time
        assert d10["predicted_seconds"] == pytest.approx(3600.0, abs=1)


class TestGetBestRecentRun:
    def test_returns_none_when_no_activities(self, mem_db):
        with mem_db() as conn:
            result = get_best_recent_run(conn)
        assert result is None

    def test_returns_none_when_only_short_runs(self, mem_db):
        """Runs under 3 km should be excluded (warm-up jogs)."""
        with mem_db() as conn:
            conn.execute(
                """
                INSERT INTO activities
                    (id, name, sport_type, start_date, distance, moving_time, elapsed_time)
                VALUES (1, 'Warm up', 'Run', '2026-01-05T08:00:00Z', 1500, 600, 600)
                """
            )
        with mem_db() as conn:
            result = get_best_recent_run(conn)
        assert result is None

    def test_returns_longest_run(self, mem_db):
        """Should prefer longest distance over shorter faster runs."""
        with mem_db() as conn:
            # 10k in 50min (faster pace)
            conn.execute(
                """
                INSERT INTO activities
                    (id, name, sport_type, start_date, distance, moving_time, elapsed_time)
                VALUES (1, 'Fast 10k', 'Run', '2026-01-05T08:00:00Z', 10000, 3000, 3000)
                """
            )
            # 20k in 110min (slower pace, longer distance)
            conn.execute(
                """
                INSERT INTO activities
                    (id, name, sport_type, start_date, distance, moving_time, elapsed_time)
                VALUES (2, 'Long run', 'Run', '2026-01-07T08:00:00Z', 20000, 6600, 6600)
                """
            )
        with mem_db() as conn:
            result = get_best_recent_run(conn)
        assert result is not None
        assert result["activity_id"] == 2
        assert result["distance_km"] == pytest.approx(20.0, abs=0.01)

    def test_result_has_required_fields(self, mem_db):
        with mem_db() as conn:
            conn.execute(
                """
                INSERT INTO activities
                    (id, name, sport_type, start_date, distance, moving_time, elapsed_time)
                VALUES (1, 'Half marathon', 'Run', '2026-01-10T08:00:00Z', 21100, 5700, 5700)
                """
            )
        with mem_db() as conn:
            result = get_best_recent_run(conn)
        assert result is not None
        assert "activity_id" in result
        assert "date" in result
        assert "distance_km" in result
        assert "time_seconds" in result
        assert "pace_sec_per_km" in result

    def test_excludes_old_activities(self, mem_db):
        """Activities beyond lookback_days should not be returned."""
        with mem_db() as conn:
            conn.execute(
                """
                INSERT INTO activities
                    (id, name, sport_type, start_date, distance, moving_time, elapsed_time)
                VALUES (1, 'Old run', 'Run', '2020-01-01T08:00:00Z', 15000, 4500, 4500)
                """
            )
        with mem_db() as conn:
            result = get_best_recent_run(conn, lookback_days=365)
        assert result is None
