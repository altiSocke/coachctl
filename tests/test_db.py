"""
Tests for coachctl.db — schema creation, connection management.
"""

from __future__ import annotations

import sqlite3

import pytest

import coachctl.db as db_module
import coachctl.paths as paths_module


@pytest.fixture(autouse=True)
def clear_cache():
    paths_module._resolve_data_root.cache_clear()
    yield
    paths_module._resolve_data_root.cache_clear()


@pytest.fixture
def patched_db(tmp_path, monkeypatch):
    """Patch db_path to a tmp file and reset _DB_INITIALISED."""
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("AGENT_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(paths_module, "db_path", lambda: db_file)
    monkeypatch.setattr(db_module, "_DB_INITIALISED", False)
    return db_file


# ── get_conn ──────────────────────────────────────────────────────────────────


def test_get_conn_is_contextmanager(patched_db):
    """get_conn() must be usable as a context manager."""
    with db_module.get_conn() as conn:
        assert conn is not None
        row = conn.execute("SELECT 1 AS val").fetchone()
        assert row["val"] == 1


def test_get_conn_auto_closes(patched_db):
    """Connection should be closed after exiting the context."""
    with db_module.get_conn() as conn:
        pass  # just enter and exit
    # Trying to use it after close raises ProgrammingError
    with pytest.raises(Exception):
        conn.execute("SELECT 1")


def test_get_conn_rollback_on_error(patched_db):
    """Exception inside context → rollback, connection closed."""
    db_module.init_db()  # create tables first
    with db_module.get_conn() as conn:
        conn.execute("INSERT INTO sync_state (key, value) VALUES ('k', 'v')")

    with pytest.raises(ValueError):
        with db_module.get_conn() as conn:
            conn.execute("INSERT INTO sync_state (key, value) VALUES ('k2', 'v2')")
            raise ValueError("deliberate rollback")

    with db_module.get_conn() as conn:
        row = conn.execute("SELECT value FROM sync_state WHERE key='k2'").fetchone()
        assert row is None  # rolled back


# ── init_db ───────────────────────────────────────────────────────────────────

EXPECTED_TABLES = {
    "activities", "fitness", "feedback", "sync_state",
    "untracked_activities", "untracked_checkins", "activity_streams",
    "readiness_checkins", "schedule_overrides", "plans", "events",
}


def test_init_db_creates_tables(patched_db):
    db_module.init_db()
    with db_module.get_conn() as conn:
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
    assert EXPECTED_TABLES.issubset(tables)


def test_init_db_idempotent(patched_db):
    """Calling init_db() twice must not raise."""
    db_module.init_db()
    # Reset the flag to force a re-run
    db_module._DB_INITIALISED = False
    db_module.init_db()
    with db_module.get_conn() as conn:
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
    assert "events" in tables


def test_init_db_adds_reviewed_at_column(patched_db):
    """reviewed_at column must exist in activities after init."""
    db_module.init_db()
    with db_module.get_conn() as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(activities)").fetchall()}
    assert "reviewed_at" in cols


def test_init_db_adds_rtss_power_column(patched_db):
    db_module.init_db()
    with db_module.get_conn() as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(activities)").fetchall()}
    assert "rtss_power" in cols


def test_init_db_adds_week_tss_json_column(patched_db):
    db_module.init_db()
    with db_module.get_conn() as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(plans)").fetchall()}
    assert "week_tss_json" in cols


def test_init_db_sets_flag(patched_db):
    db_module.init_db()
    assert db_module._DB_INITIALISED is True
