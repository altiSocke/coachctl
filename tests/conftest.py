"""
Shared fixtures for the coachctl test suite.

All fixtures that involve path patching clear the lru_cache on
paths._resolve_data_root to avoid cross-test contamination.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager

import pytest

# ── Full DB schema (mirror of db.py init_db) ──────────────────────────────────

_FULL_SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS activities (
        id              INTEGER PRIMARY KEY,
        name            TEXT NOT NULL DEFAULT '',
        sport_type      TEXT NOT NULL DEFAULT '',
        start_date      TEXT NOT NULL DEFAULT '',
        elapsed_time    INTEGER,
        moving_time     INTEGER,
        distance        REAL,
        total_elevation_gain REAL,
        average_speed   REAL,
        max_speed       REAL,
        average_heartrate REAL,
        max_heartrate   REAL,
        average_watts   REAL,
        weighted_avg_watts REAL,
        average_cadence REAL,
        suffer_score    INTEGER,
        tss             REAL,
        np              REAL,
        intensity_factor REAL,
        hrss            REAL,
        rtss            REAL,
        ngp             REAL,
        rtss_power      REAL,
        raw_json        TEXT,
        reviewed_at     TEXT,
        synced_at       TEXT DEFAULT (datetime('now'))
    );
    CREATE INDEX IF NOT EXISTS idx_activities_start_date ON activities(start_date);
    CREATE INDEX IF NOT EXISTS idx_activities_sport_type ON activities(sport_type);

    CREATE TABLE IF NOT EXISTS fitness (
        date            TEXT NOT NULL,
        sport_category  TEXT NOT NULL,
        ctl             REAL,
        atl             REAL,
        tsb             REAL,
        PRIMARY KEY (date, sport_category)
    );

    CREATE TABLE IF NOT EXISTS feedback (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        activity_date   TEXT NOT NULL,
        activity_id     INTEGER,
        rpe             INTEGER,
        felt            TEXT,
        notes           TEXT,
        created_at      TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS sync_state (
        key             TEXT PRIMARY KEY,
        value           TEXT
    );

    CREATE TABLE IF NOT EXISTS untracked_activities (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        activity_date   TEXT NOT NULL,
        sport           TEXT NOT NULL,
        duration_min    INTEGER,
        intensity       TEXT DEFAULT 'moderate',
        tss_estimate    REAL,
        notes           TEXT,
        created_at      TEXT DEFAULT (datetime('now'))
    );
    CREATE INDEX IF NOT EXISTS idx_untracked_date ON untracked_activities(activity_date);

    CREATE TABLE IF NOT EXISTS untracked_checkins (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        week_start      TEXT NOT NULL UNIQUE,
        checked_at      TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS activity_streams (
        activity_id     INTEGER PRIMARY KEY,
        streams_json    TEXT NOT NULL,
        fetched_at      TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS readiness_checkins (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        checkin_date    TEXT NOT NULL UNIQUE,
        sleep           INTEGER,
        energy          INTEGER,
        soreness        INTEGER,
        notes           TEXT,
        created_at      TEXT DEFAULT (datetime('now'))
    );
    CREATE INDEX IF NOT EXISTS idx_readiness_checkins_date ON readiness_checkins(checkin_date);

    CREATE TABLE IF NOT EXISTS schedule_overrides (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_file     TEXT NOT NULL,
        session_date  TEXT NOT NULL,
        original_name TEXT,
        new_name      TEXT,
        new_details   TEXT,
        reason        TEXT,
        created_at    TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE UNIQUE INDEX IF NOT EXISTS idx_overrides_plan_date
        ON schedule_overrides(plan_file, session_date);

    CREATE TABLE IF NOT EXISTS plans (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        slug            TEXT UNIQUE NOT NULL,
        title           TEXT,
        start_date      TEXT,
        end_date        TEXT,
        active          INTEGER DEFAULT 1,
        overview_md     TEXT,
        week_tss_json   TEXT,
        source_md_path  TEXT,
        created_at      TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS events (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        slug            TEXT UNIQUE NOT NULL,
        kind            TEXT NOT NULL,
        date            TEXT NOT NULL,
        start_time      TEXT,
        duration_min    INTEGER,
        name            TEXT NOT NULL,
        summary         TEXT,
        estimated_tss   REAL,
        status          TEXT DEFAULT 'planned',
        payload_json    TEXT,
        plan_id         INTEGER,
        activity_id     INTEGER,
        notes           TEXT,
        created_at      TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE INDEX IF NOT EXISTS idx_events_date ON events(date);
    CREATE INDEX IF NOT EXISTS idx_events_kind ON events(kind);
    CREATE INDEX IF NOT EXISTS idx_events_status ON events(status);

    CREATE TABLE IF NOT EXISTS coaching_notes (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        session_date    TEXT NOT NULL,
        category        TEXT NOT NULL DEFAULT 'general',
        tags            TEXT,
        note            TEXT NOT NULL,
        created_at      TEXT NOT NULL DEFAULT (datetime('now'))
    );
"""


@pytest.fixture
def tmp_data_root(tmp_path, monkeypatch):
    """
    Scaffold a minimal coachctl-personal directory tree in tmp_path,
    patch AGENT_DATA_ROOT to point at it, and clear the lru_cache.
    """
    import coachctl.paths as paths_module

    data_root = tmp_path / "personal"
    data_root.mkdir()
    (data_root / "profile").mkdir()
    (data_root / "data").mkdir()
    (data_root / "deploy" / "dist").mkdir(parents=True)

    # Redirect general wiki to a temp directory so tests never touch the real wiki/
    general_wiki = tmp_path / "wiki"
    general_wiki.mkdir()
    monkeypatch.setattr(paths_module, "general_wiki_dir", lambda: general_wiki)

    # Clear cache before AND after so other tests aren't affected
    paths_module._resolve_data_root.cache_clear()
    monkeypatch.setenv("AGENT_DATA_ROOT", str(data_root))
    # Remove any sibling detection interference
    monkeypatch.delenv("STRAVA_PROFILE", raising=False)

    yield data_root

    paths_module._resolve_data_root.cache_clear()


@pytest.fixture
def mem_db(tmp_data_root, monkeypatch):
    """
    Full-schema SQLite DB in tmp_data_root/data/activities.db.
    Patches db.get_conn, events.get_conn, and all paths.db_path references.
    Returns the _get_conn contextmanager factory for use in helper functions.
    """
    import coachctl.db as db_module
    import coachctl.events as events_module
    import coachctl.paths as paths_module

    db_file = tmp_data_root / "data" / "activities.db"
    db_file.parent.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(paths_module, "db_path", lambda: db_file)

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
    monkeypatch.setattr(events_module, "get_conn", _get_conn)

    # Also patch _DB_INITIALISED so init_db() re-runs if called
    monkeypatch.setattr(db_module, "_DB_INITIALISED", False)

    with _get_conn() as conn:
        conn.executescript(_FULL_SCHEMA_SQL)

    return _get_conn
