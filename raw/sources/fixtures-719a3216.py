"""
Tests for coachctl.events — calendar projection layer.
Uses an in-memory SQLite DB; no Strava calls, no file I/O.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, timedelta

import pytest

from coachctl.events import (
    KIND_ACTIVITY,
    KIND_RACE,
    KIND_TRAINING,
    STATUS_COMPLETED,
    STATUS_PLANNED,
    Event,
    _payload_hash,
    _row_to_event,
    get_calendar,
    get_event,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

_SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT UNIQUE NOT NULL,
        kind TEXT NOT NULL,
        date TEXT NOT NULL,
        start_time TEXT,
        duration_min INTEGER,
        name TEXT NOT NULL,
        summary TEXT,
        estimated_tss REAL,
        status TEXT DEFAULT 'planned',
        payload_json TEXT,
        plan_id INTEGER,
        activity_id INTEGER,
        notes TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS activities (
        id INTEGER PRIMARY KEY,
        name TEXT,
        sport_type TEXT,
        start_date TEXT,
        moving_time INTEGER,
        distance REAL,
        total_elevation_gain REAL,
        average_heartrate REAL,
        average_watts REAL,
        tss REAL,
        suffer_score INTEGER
    );
"""


@pytest.fixture
def mem_db(monkeypatch, tmp_path):
    """
    File-based SQLite DB in tmp_path with events + activities schema.
    Patches db.get_conn() as a proper contextmanager to avoid ResourceWarnings.
    """
    db_file = tmp_path / "activities.db"

    import coachctl.db as db_module
    import coachctl.paths as paths_module

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
    monkeypatch.setattr("coachctl.events.get_conn", _get_conn)
    monkeypatch.setattr("coachctl.events.paths.db_path", lambda: db_file)

    with _get_conn() as conn:
        conn.executescript(_SCHEMA_SQL)

    return _get_conn


def _insert_event(get_conn, slug, kind, date_str, name, status=STATUS_PLANNED,
                  payload=None, estimated_tss=None):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO events (slug, kind, date, name, status, payload_json, estimated_tss)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (slug, kind, date_str, name, status,
             json.dumps(payload) if payload else None, estimated_tss),
        )


def _insert_activity(get_conn, activity_id, name, sport_type, start_date,
                     moving_time=3600, tss=80.0):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO activities (id, name, sport_type, start_date, moving_time, tss)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (activity_id, name, sport_type, start_date, moving_time, tss),
        )


# ── _payload_hash ─────────────────────────────────────────────────────────────


def test_payload_hash_deterministic():
    ev = Event(slug="test", kind=KIND_TRAINING, date="2026-05-01", name="Easy run")
    assert _payload_hash(ev) == _payload_hash(ev)


def test_payload_hash_changes_on_date():
    ev1 = Event(slug="test", kind=KIND_TRAINING, date="2026-05-01", name="Easy run")
    ev2 = Event(slug="test", kind=KIND_TRAINING, date="2026-05-02", name="Easy run")
    assert _payload_hash(ev1) != _payload_hash(ev2)


def test_payload_hash_changes_on_name():
    ev1 = Event(slug="test", kind=KIND_TRAINING, date="2026-05-01", name="Easy run")
    ev2 = Event(slug="test", kind=KIND_TRAINING, date="2026-05-01", name="Tempo run")
    assert _payload_hash(ev1) != _payload_hash(ev2)


def test_payload_hash_length():
    ev = Event(slug="test", kind=KIND_TRAINING, date="2026-05-01", name="Easy run")
    assert len(_payload_hash(ev)) == 16


# ── get_calendar ──────────────────────────────────────────────────────────────


def test_get_calendar_empty(mem_db):
    events = get_calendar("2026-05-01", "2026-05-07")
    assert events == []


def test_get_calendar_returns_event_in_range(mem_db):
    _insert_event(mem_db, "run-2026-05-03", KIND_TRAINING, "2026-05-03", "Easy run")
    events = get_calendar("2026-05-01", "2026-05-07")
    assert any(e.slug == "run-2026-05-03" for e in events)


def test_get_calendar_excludes_out_of_range(mem_db):
    _insert_event(mem_db, "run-2026-05-10", KIND_TRAINING, "2026-05-10", "Easy run")
    events = get_calendar("2026-05-01", "2026-05-07")
    assert not any(e.slug == "run-2026-05-10" for e in events)


def test_get_calendar_inclusive_bounds(mem_db):
    _insert_event(mem_db, "start-event", KIND_TRAINING, "2026-05-01", "Start")
    _insert_event(mem_db, "end-event", KIND_TRAINING, "2026-05-07", "End")
    events = get_calendar("2026-05-01", "2026-05-07")
    slugs = {e.slug for e in events}
    assert "start-event" in slugs
    assert "end-event" in slugs


def test_get_calendar_kind_filter(mem_db):
    _insert_event(mem_db, "race-1", KIND_RACE, "2026-05-03", "Race")
    _insert_event(mem_db, "train-1", KIND_TRAINING, "2026-05-03", "Training")
    events = get_calendar("2026-05-01", "2026-05-07", kinds=[KIND_RACE])
    assert all(e.kind == KIND_RACE for e in events)
    assert any(e.slug == "race-1" for e in events)
    assert not any(e.slug == "train-1" for e in events)


def test_get_calendar_activities_projected(mem_db):
    _insert_activity(mem_db, 1001, "Morning run", "Run", "2026-05-04T07:00:00Z")
    events = get_calendar("2026-05-01", "2026-05-07", kinds=[KIND_ACTIVITY])
    assert any(e.kind == KIND_ACTIVITY and e.activity_id == 1001 for e in events)


def test_get_calendar_activity_status_completed(mem_db):
    _insert_activity(mem_db, 1002, "Evening ride", "Ride", "2026-05-05T18:00:00Z")
    events = get_calendar("2026-05-01", "2026-05-07", kinds=[KIND_ACTIVITY])
    act = next(e for e in events if e.activity_id == 1002)
    assert act.status == STATUS_COMPLETED


def test_get_calendar_date_objects(mem_db):
    """get_calendar should accept date objects as well as strings."""
    _insert_event(mem_db, "date-obj-test", KIND_TRAINING, "2026-05-03", "Test")
    events = get_calendar(date(2026, 5, 1), date(2026, 5, 7))
    assert any(e.slug == "date-obj-test" for e in events)


def test_get_calendar_sorted_by_date(mem_db):
    _insert_event(mem_db, "ev-c", KIND_TRAINING, "2026-05-07", "C")
    _insert_event(mem_db, "ev-a", KIND_TRAINING, "2026-05-01", "A")
    _insert_event(mem_db, "ev-b", KIND_TRAINING, "2026-05-04", "B")
    events = get_calendar("2026-05-01", "2026-05-07", kinds=[KIND_TRAINING])
    dates = [e.date for e in events]
    assert dates == sorted(dates)


def test_get_calendar_payload_parsed(mem_db):
    payload = {"pacing": {"km1": "4:30"}}
    _insert_event(mem_db, "race-payload", KIND_RACE, "2026-05-03", "Race",
                  payload=payload)
    events = get_calendar("2026-05-01", "2026-05-07", kinds=[KIND_RACE])
    ev = next(e for e in events if e.slug == "race-payload")
    assert ev.payload == payload


# ── get_event ─────────────────────────────────────────────────────────────────


def test_get_event_found(mem_db):
    _insert_event(mem_db, "my-race", KIND_RACE, "2026-06-01", "My Race")
    ev = get_event("my-race")
    assert ev is not None
    assert ev.slug == "my-race"
    assert ev.kind == KIND_RACE


def test_get_event_not_found(mem_db):
    assert get_event("nonexistent-slug") is None


def test_get_event_estimated_tss(mem_db):
    _insert_event(mem_db, "hard-session", KIND_TRAINING, "2026-05-10",
                  "Intervals", estimated_tss=95.0)
    ev = get_event("hard-session")
    assert ev.estimated_tss == pytest.approx(95.0)
