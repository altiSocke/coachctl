"""
Tests for the metrics recalculation pipeline:
  - fitness table schema extensions (new columns added by init_db)
  - recalculate_activity_metrics() — backfill from raw_json
  - _refresh_fitness_table() — new ACWR + Monotony columns written
  - Column values are numerically coherent
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, timedelta

import pytest

import coachctl.db as db_module
import coachctl.paths as paths_module


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def clear_cache():
    paths_module._resolve_data_root.cache_clear()
    yield
    paths_module._resolve_data_root.cache_clear()


@pytest.fixture
def patched_db(tmp_path, monkeypatch):
    """Fresh DB in a temp dir; all path references redirected."""
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("AGENT_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(paths_module, "db_path", lambda: db_file)
    monkeypatch.setattr(db_module, "_DB_INITIALISED", False)

    @contextmanager
    def _get_conn():
        conn = sqlite3.connect(str(db_file))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    monkeypatch.setattr(db_module, "get_conn", _get_conn)

    # Also patch sync and metrics modules that import get_conn directly
    import coachctl.sync as sync_module

    monkeypatch.setattr(sync_module, "get_conn", _get_conn)

    import coachctl.metrics as metrics_module

    monkeypatch.setattr(metrics_module, "get_conn", _get_conn, raising=False)

    db_module.init_db()
    return db_file, _get_conn


@pytest.fixture
def mock_athlete(monkeypatch):
    athlete = {"ftp": 250, "rftp": 270, "threshold_hr": 170, "resting_hr": 50}
    monkeypatch.setattr("coachctl.config.load_athlete", lambda: athlete)
    return athlete


# ── Unit 1: Schema — new fitness columns exist after init_db ──────────────────


def test_fitness_table_has_tss_column(patched_db):
    _, _get_conn = patched_db
    with _get_conn() as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(fitness)").fetchall()}
    assert "tss" in cols


def test_fitness_table_has_acwr_columns(patched_db):
    _, _get_conn = patched_db
    with _get_conn() as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(fitness)").fetchall()}
    assert "acwr_rolling" in cols
    assert "acwr_ema" in cols
    assert "acwr_risk_zone" in cols


def test_fitness_table_has_monotony_columns(patched_db):
    _, _get_conn = patched_db
    with _get_conn() as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(fitness)").fetchall()}
    assert "monotony" in cols
    assert "strain" in cols


def test_fitness_table_columns_nullable(patched_db):
    """Inserting a row with only the PK columns must not raise (new cols nullable)."""
    _, _get_conn = patched_db
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO fitness (date, sport_category, ctl, atl, tsb) VALUES (?,?,?,?,?)",
            ("2026-01-01", "all", 50.0, 55.0, -5.0),
        )
        row = conn.execute(
            "SELECT acwr_rolling, acwr_ema, acwr_risk_zone, monotony, strain "
            "FROM fitness WHERE date='2026-01-01'"
        ).fetchone()
    # New columns default to NULL when not supplied
    assert row["acwr_rolling"] is None
    assert row["monotony"] is None


# ── Unit 2: recalculate_activity_metrics() ────────────────────────────────────


def _make_ride_raw_json(activity_id: int, start_date: str, watts: float = 250) -> str:
    """Minimal Strava-style activity dict for a cycling activity."""
    return json.dumps(
        {
            "id": activity_id,
            "name": f"Ride {activity_id}",
            "sport_type": "Ride",
            "type": "Ride",
            "start_date": start_date,
            "elapsed_time": 3600,
            "moving_time": 3600,
            "distance": 40000.0,
            "total_elevation_gain": 200.0,
            "average_speed": 11.1,
            "max_speed": 15.0,
            "average_heartrate": 150.0,
            "max_heartrate": 175.0,
            "average_watts": watts * 0.95,
            "weighted_average_watts": watts,
            "average_cadence": 85.0,
            "suffer_score": 60,
        }
    )


def _make_run_raw_json(activity_id: int, start_date: str) -> str:
    """Minimal Strava-style activity dict for a flat running activity at threshold pace."""
    rftp_ms = 1000 / 270.0  # 4:30/km
    dist = rftp_ms * 3600  # 1h at threshold
    return json.dumps(
        {
            "id": activity_id,
            "name": f"Run {activity_id}",
            "sport_type": "Run",
            "type": "Run",
            "start_date": start_date,
            "elapsed_time": 3600,
            "moving_time": 3600,
            "distance": dist,
            "total_elevation_gain": 0.0,
            "average_speed": rftp_ms,
            "max_speed": rftp_ms * 1.1,
            "average_heartrate": 165.0,
            "max_heartrate": 178.0,
            "average_watts": None,
            "weighted_average_watts": None,
            "average_cadence": 90.0,
            "suffer_score": 50,
        }
    )


@pytest.fixture
def db_with_activities(patched_db, mock_athlete):
    """DB pre-populated with 10 ride activities across 10 days, all with raw_json."""
    db_file, _get_conn = patched_db
    base = date(2026, 3, 1)
    with _get_conn() as conn:
        for i in range(10):
            d = (base + timedelta(days=i)).isoformat() + "T08:00:00Z"
            raw = _make_ride_raw_json(i + 1, d, watts=240 + i * 2)
            conn.execute(
                """INSERT INTO activities
                   (id, name, sport_type, start_date, moving_time, distance,
                    total_elevation_gain, average_speed, average_heartrate,
                    average_watts, weighted_avg_watts, raw_json)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    i + 1,
                    f"Ride {i + 1}",
                    "Ride",
                    d,
                    3600,
                    40000.0,
                    200.0,
                    11.1,
                    150.0,
                    240 + i * 2 - 5,
                    240 + i * 2,
                    raw,
                ),
            )
    return db_file, _get_conn


def test_recalculate_returns_count(db_with_activities, mock_athlete):
    from coachctl.sync import recalculate_activity_metrics

    n = recalculate_activity_metrics(verbose=False)
    assert n == 10


def test_recalculate_populates_tss(db_with_activities, mock_athlete):
    """After recalculate, all activities should have a non-null tss."""
    from coachctl.sync import recalculate_activity_metrics

    _, _get_conn = db_with_activities
    recalculate_activity_metrics(verbose=False)
    with _get_conn() as conn:
        rows = conn.execute("SELECT tss FROM activities").fetchall()
    assert all(r["tss"] is not None for r in rows)
    assert all(r["tss"] > 0 for r in rows)


def test_recalculate_tss_coherent_with_formula(db_with_activities, mock_athlete):
    """1h ride at FTP (250W) → tss ≈ 100. Our rides are close to FTP so tss ≈ 80–120."""
    from coachctl.sync import recalculate_activity_metrics

    _, _get_conn = db_with_activities
    recalculate_activity_metrics(verbose=False)
    with _get_conn() as conn:
        rows = conn.execute("SELECT tss FROM activities ORDER BY id").fetchall()
    for r in rows:
        assert 60 <= r["tss"] <= 150, f"Unexpected TSS: {r['tss']}"


def test_recalculate_idempotent(db_with_activities, mock_athlete):
    """Running recalculate twice should give the same tss values."""
    from coachctl.sync import recalculate_activity_metrics

    _, _get_conn = db_with_activities

    recalculate_activity_metrics(verbose=False)
    with _get_conn() as conn:
        first = [
            r["tss"] for r in conn.execute("SELECT tss FROM activities ORDER BY id").fetchall()
        ]

    recalculate_activity_metrics(verbose=False)
    with _get_conn() as conn:
        second = [
            r["tss"] for r in conn.execute("SELECT tss FROM activities ORDER BY id").fetchall()
        ]

    assert first == second


def test_recalculate_empty_db(patched_db, mock_athlete):
    """recalculate on an empty DB must return 0 and not raise."""
    from coachctl.sync import recalculate_activity_metrics

    n = recalculate_activity_metrics(verbose=False)
    assert n == 0


def test_recalculate_skips_null_raw_json(patched_db, mock_athlete):
    """Activities without raw_json are silently skipped."""
    _, _get_conn = patched_db
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO activities (id, name, sport_type, start_date, moving_time) "
            "VALUES (99, 'No raw', 'Ride', '2026-01-01T08:00:00Z', 3600)"
        )
    from coachctl.sync import recalculate_activity_metrics

    n = recalculate_activity_metrics(verbose=False)
    assert n == 0  # no raw_json → nothing processed


# ── Unit 3: _refresh_fitness_table() writes ACWR + Monotony ──────────────────


def test_refresh_writes_acwr_columns(db_with_activities, mock_athlete):
    """After _refresh_fitness_table, acwr_rolling and acwr_ema must be non-null
    for dates with enough history (≥7 days of data)."""
    from coachctl.sync import recalculate_activity_metrics

    _, _get_conn = db_with_activities
    recalculate_activity_metrics(verbose=False)
    with _get_conn() as conn:
        # At least one row should have acwr data (the later dates in the series)
        rows = conn.execute(
            "SELECT acwr_rolling, acwr_ema, acwr_risk_zone "
            "FROM fitness WHERE sport_category='all' ORDER BY date"
        ).fetchall()
    assert len(rows) > 0
    # acwr_rolling must be present somewhere (once chronic window has data)
    acwr_values = [r["acwr_rolling"] for r in rows if r["acwr_rolling"] is not None]
    assert len(acwr_values) > 0
    # Values are non-negative (0.0 = no acute load, valid undertrained state)
    for v in acwr_values:
        assert v >= 0


def test_refresh_writes_monotony_columns(db_with_activities, mock_athlete):
    """After _refresh_fitness_table, monotony and strain must appear in the table."""
    from coachctl.sync import recalculate_activity_metrics

    _, _get_conn = db_with_activities
    recalculate_activity_metrics(verbose=False)
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT monotony, strain FROM fitness WHERE sport_category='all' ORDER BY date"
        ).fetchall()
    monotony_values = [r["monotony"] for r in rows if r["monotony"] is not None]
    strain_values = [r["strain"] for r in rows if r["strain"] is not None]
    assert len(monotony_values) > 0
    assert len(strain_values) > 0


def test_refresh_writes_tss_column(db_with_activities, mock_athlete):
    """fitness.tss must equal the sum of activities.tss for each date."""
    from coachctl.sync import recalculate_activity_metrics

    _, _get_conn = db_with_activities
    recalculate_activity_metrics(verbose=False)
    with _get_conn() as conn:
        # Pick a date we know has exactly one activity (day 1 = 2026-03-01)
        fit_row = conn.execute(
            "SELECT tss FROM fitness WHERE date='2026-03-01' AND sport_category='all'"
        ).fetchone()
        act_row = conn.execute(
            "SELECT SUM(tss) AS total FROM activities WHERE date(start_date)='2026-03-01'"
        ).fetchone()
    assert fit_row is not None
    assert fit_row["tss"] == pytest.approx(act_row["total"], rel=0.01)


def test_refresh_acwr_risk_zone_valid_values(db_with_activities, mock_athlete):
    """acwr_risk_zone must be one of the four expected labels or NULL."""
    from coachctl.sync import recalculate_activity_metrics

    _, _get_conn = db_with_activities
    recalculate_activity_metrics(verbose=False)
    valid = {"undertrained", "optimal", "caution", "high_risk", "unknown", None}
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT acwr_risk_zone FROM fitness WHERE sport_category='all'"
        ).fetchall()
    for r in rows:
        assert r["acwr_risk_zone"] in valid, f"Unexpected risk zone: {r['acwr_risk_zone']}"


def test_refresh_ctl_atl_still_populated(db_with_activities, mock_athlete):
    """The existing CTL/ATL/TSB columns must still be correctly written."""
    from coachctl.sync import recalculate_activity_metrics

    _, _get_conn = db_with_activities
    recalculate_activity_metrics(verbose=False)
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT ctl, atl, tsb FROM fitness WHERE sport_category='all' ORDER BY date"
        ).fetchall()
    assert len(rows) > 0
    # CTL must be positive after 10 days of ~90 TSS/day; check at peak (last active day).
    # compute_fitness_series extends to date.today() so the tail rows have decayed ATL.
    # Find the highest ATL row — it should be during or just after the training block.
    max_atl = max(r["atl"] for r in rows)
    assert max_atl > 0
    # CTL should also be positive
    max_ctl = max(r["ctl"] for r in rows)
    assert max_ctl > 0


def test_refresh_sport_categories_all_written(db_with_activities, mock_athlete):
    """All three sport categories must be present in fitness after recalculate."""
    from coachctl.sync import recalculate_activity_metrics

    _, _get_conn = db_with_activities
    recalculate_activity_metrics(verbose=False)
    with _get_conn() as conn:
        cats = {
            r["sport_category"]
            for r in conn.execute("SELECT DISTINCT sport_category FROM fitness").fetchall()
        }
    # 'all' and 'ride' must be present (no run activities in this fixture)
    assert "all" in cats
    assert "ride" in cats
