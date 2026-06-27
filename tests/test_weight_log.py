"""
Tests for the date-aware body-weight log:
  - config.weight_on(conn, date) resolution + YAML fallback
  - cli.log_weight_cmd insert / upsert / validation / --list
  - regression: stored TSS is weight-independent
"""

from __future__ import annotations

import sqlite3
from datetime import date

import pytest

import coachctl.db as db_module
import coachctl.paths as paths_module
from coachctl.config import weight_on


@pytest.fixture(autouse=True)
def clear_cache():
    paths_module._resolve_data_root.cache_clear()
    yield
    paths_module._resolve_data_root.cache_clear()


@pytest.fixture
def patched_db(tmp_path, monkeypatch):
    """Tmp DB + reset init flag (mirrors tests/test_db.py)."""
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("AGENT_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(paths_module, "db_path", lambda: db_file)
    monkeypatch.setattr(db_module, "_DB_INITIALISED", False)
    db_module.init_db()
    return db_file


def _insert(conn, d, kg, source="manual", note=None):
    conn.execute(
        "INSERT INTO weight_log (date, weight_kg, source, note) VALUES (?, ?, ?, ?)",
        (d, kg, source, note),
    )


# ── weight_on resolution ──────────────────────────────────────────────────────


def test_weight_on_empty_log_falls_back_to_yaml(patched_db, monkeypatch):
    monkeypatch.setattr("coachctl.config.load_athlete", lambda: {"weight_kg": 87})
    with db_module.get_conn() as conn:
        assert weight_on(conn, date(2026, 6, 27)) == 87.0


def test_weight_on_empty_log_and_no_yaml_returns_none(patched_db, monkeypatch):
    monkeypatch.setattr("coachctl.config.load_athlete", lambda: {})
    with db_module.get_conn() as conn:
        assert weight_on(conn, date(2026, 6, 27)) is None


def test_weight_on_exact_date_hit(patched_db, monkeypatch):
    monkeypatch.setattr("coachctl.config.load_athlete", lambda: {"weight_kg": 87})
    with db_module.get_conn() as conn:
        _insert(conn, "2026-05-16", 86.0)
    with db_module.get_conn() as conn:
        assert weight_on(conn, date(2026, 5, 16)) == 86.0


def test_weight_on_returns_most_recent_on_or_before(patched_db, monkeypatch):
    monkeypatch.setattr("coachctl.config.load_athlete", lambda: {"weight_kg": 87})
    with db_module.get_conn() as conn:
        _insert(conn, "2026-05-16", 87.0)
        _insert(conn, "2026-06-27", 85.5)
    with db_module.get_conn() as conn:
        # Between the two entries → earlier one wins.
        assert weight_on(conn, date(2026, 6, 1)) == 87.0
        # On/after the later entry → later one.
        assert weight_on(conn, date(2026, 6, 27)) == 85.5
        assert weight_on(conn, date(2026, 7, 10)) == 85.5


def test_weight_on_before_first_entry_uses_yaml(patched_db, monkeypatch):
    monkeypatch.setattr("coachctl.config.load_athlete", lambda: {"weight_kg": 90})
    with db_module.get_conn() as conn:
        _insert(conn, "2026-05-16", 86.0)
    with db_module.get_conn() as conn:
        # Target predates the only log entry → no row <= target → YAML fallback.
        assert weight_on(conn, date(2026, 1, 1)) == 90.0


def test_weight_on_accepts_iso_string(patched_db, monkeypatch):
    monkeypatch.setattr("coachctl.config.load_athlete", lambda: {"weight_kg": 87})
    with db_module.get_conn() as conn:
        _insert(conn, "2026-06-27", 85.5)
    with db_module.get_conn() as conn:
        assert weight_on(conn, "2026-06-27") == 85.5


def test_weight_on_defaults_to_today(patched_db, monkeypatch):
    monkeypatch.setattr("coachctl.config.load_athlete", lambda: {"weight_kg": 87})
    with db_module.get_conn() as conn:
        _insert(conn, "2000-01-01", 85.5)  # far in the past → still latest <= today
    with db_module.get_conn() as conn:
        assert weight_on(conn) == 85.5


def test_weight_on_missing_table_falls_back(tmp_path, monkeypatch):
    """If weight_log doesn't exist (un-migrated DB), degrade to YAML."""
    monkeypatch.setattr("coachctl.config.load_athlete", lambda: {"weight_kg": 88})
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    assert weight_on(conn, date(2026, 6, 27)) == 88.0
    conn.close()


# ── log_weight_cmd (CLI function called directly) ─────────────────────────────


def test_log_weight_cmd_inserts(patched_db, monkeypatch, capsys):
    monkeypatch.setattr("coachctl.config.load_athlete", lambda: {"ftp": 280, "weight_kg": 87})
    from coachctl.cli import _log_weight

    _log_weight("2026-06-27", 85.5)
    with db_module.get_conn() as conn:
        row = conn.execute(
            "SELECT weight_kg, source FROM weight_log WHERE date='2026-06-27'"
        ).fetchone()
    assert row["weight_kg"] == 85.5
    assert row["source"] == "manual"
    out = capsys.readouterr().out
    assert "85.5 kg" in out and "W/kg" in out  # FTP-derived feedback shown


def test_log_weight_cmd_upserts_same_date(patched_db, monkeypatch):
    monkeypatch.setattr("coachctl.config.load_athlete", lambda: {"weight_kg": 87})
    from coachctl.cli import _log_weight

    _log_weight("2026-06-27", 85.5)
    _log_weight("2026-06-27", 84.9, source="scale")
    with db_module.get_conn() as conn:
        rows = conn.execute(
            "SELECT weight_kg, source FROM weight_log WHERE date='2026-06-27'"
        ).fetchall()
    assert len(rows) == 1  # UPSERT, not duplicate
    assert rows[0]["weight_kg"] == 84.9
    assert rows[0]["source"] == "scale"


def test_log_weight_cmd_rejects_bad_date(patched_db, monkeypatch):
    monkeypatch.setattr("coachctl.config.load_athlete", lambda: {"weight_kg": 87})
    import typer

    from coachctl.cli import _log_weight

    with pytest.raises(typer.Exit):
        _log_weight("not-a-date", 85.5)


def test_log_weight_cmd_rejects_out_of_range(patched_db, monkeypatch):
    monkeypatch.setattr("coachctl.config.load_athlete", lambda: {"weight_kg": 87})
    import typer

    from coachctl.cli import _log_weight

    with pytest.raises(typer.Exit):
        _log_weight("2026-06-27", 12.0)  # below 30kg floor
    with pytest.raises(typer.Exit):
        _log_weight("2026-06-27", 250.0)  # above 200kg ceiling


def test_log_weight_cmd_requires_date_without_list(patched_db, monkeypatch):
    monkeypatch.setattr("coachctl.config.load_athlete", lambda: {"weight_kg": 87})
    import typer

    from coachctl.cli import _log_weight

    with pytest.raises(typer.Exit):
        _log_weight("", 0.0)


def test_log_weight_cmd_list(patched_db, monkeypatch, capsys):
    monkeypatch.setattr("coachctl.config.load_athlete", lambda: {"ftp": 280, "weight_kg": 87})
    from coachctl.cli import _log_weight

    _log_weight("2026-05-16", 87.0)
    _log_weight("2026-06-27", 85.5)
    capsys.readouterr()  # clear
    _log_weight("", 0.0, list_history=True)
    out = capsys.readouterr().out
    assert "2026-05-16" in out and "2026-06-27" in out
    assert "87.0" in out and "85.5" in out


def test_log_weight_cmd_list_empty(patched_db, monkeypatch, capsys):
    monkeypatch.setattr("coachctl.config.load_athlete", lambda: {"weight_kg": 87})
    from coachctl.cli import _log_weight

    _log_weight("", 0.0, list_history=True)
    out = capsys.readouterr().out
    assert "No weight entries" in out and "87" in out


# ── regression: stored TSS is weight-independent ──────────────────────────────


def test_stored_tss_is_weight_independent():
    """Body weight must NOT change any stored TSS/power metric.

    Guards the core invariant behind this feature: weight only affects display
    W/kg and cycling VO2max, never the load model.
    """
    from coachctl.metrics import compute_activity_metrics

    base = {
        "ftp": 280,
        "rftp": 270,
        "rftp_watts": 315,
        "threshold_hr": 178,
        "max_hr": 195,
        "resting_hr": 50,
    }
    # A run with power + HR + pace, so every TSS branch is exercised.
    activity = {
        "sport_type": "Run",
        "type": "Run",
        "moving_time": 2919,
        "distance": 10274.1,
        "total_elevation_gain": 220.0,
        "average_speed": 3.52,
        "weighted_average_watts": 357.0,
        "average_watts": 349.6,
        "average_heartrate": 174.5,
    }
    m87 = compute_activity_metrics(dict(activity), athlete={**base, "weight_kg": 87})
    m80 = compute_activity_metrics(dict(activity), athlete={**base, "weight_kg": 80})
    for k in ("tss", "np", "intensity_factor", "hrss", "rtss", "ngp", "rtss_power"):
        assert m87[k] == m80[k], f"{k} changed with weight: {m87[k]} vs {m80[k]}"
