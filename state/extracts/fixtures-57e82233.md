"""
Tests for coachctl.migrate — legacy data migration into the events table.
"""

from __future__ import annotations

import json

import pytest

from coachctl.migrate import (
    migrate_athlete_yaml_events,
    migrate_schedule_overrides,
    migrate_untracked_activities,
    run_all,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def conn(mem_db):
    """Open a connection and yield it; the mem_db fixture owns DB setup."""
    with mem_db() as c:
        yield c


# ── migrate_untracked_activities ──────────────────────────────────────────────


def test_migrate_untracked_empty(conn):
    n = migrate_untracked_activities(conn)
    assert n == 0


def test_migrate_untracked_inserts_rows(conn):
    conn.execute("""
        INSERT INTO untracked_activities (activity_date, sport, duration_min, intensity, tss_estimate, notes)
        VALUES ('2026-01-10', 'hockey', 60, 'moderate', 45.0, 'pickup game')
    """)
    n = migrate_untracked_activities(conn)
    assert n == 1

    row = conn.execute("SELECT * FROM events WHERE kind='untracked'").fetchone()
    assert row is not None
    assert row["name"] == "hockey"
    assert row["status"] == "completed"
    assert row["date"] == "2026-01-10"
    payload = json.loads(row["payload_json"])
    assert payload["sport"] == "hockey"
    assert payload["intensity"] == "moderate"


def test_migrate_untracked_idempotent(conn):
    conn.execute("""
        INSERT INTO untracked_activities (activity_date, sport, duration_min, intensity, tss_estimate, notes)
        VALUES ('2026-01-10', 'yoga', 45, 'easy', 20.0, null)
    """)
    n1 = migrate_untracked_activities(conn)
    n2 = migrate_untracked_activities(conn)
    assert n1 == 1
    assert n2 == 0  # already migrated


def test_migrate_untracked_multiple_rows(conn):
    for i in range(3):
        conn.execute(
            "INSERT INTO untracked_activities (activity_date, sport, duration_min, intensity) VALUES (?,?,?,?)",
            (f"2026-01-{10 + i:02d}", f"sport{i}", 30, "moderate"),
        )
    n = migrate_untracked_activities(conn)
    assert n == 3


# ── migrate_schedule_overrides ────────────────────────────────────────────────


def test_migrate_schedule_overrides_empty(conn):
    n = migrate_schedule_overrides(conn)
    assert n == 0


def test_migrate_schedule_overrides_skips_missing_event(conn):
    conn.execute("""
        INSERT INTO schedule_overrides (plan_file, session_date, original_name, new_name, reason)
        VALUES ('myplan.md', '2026-04-20', 'Easy run', 'Rest', 'tired')
    """)
    # No matching event exists → should skip
    n = migrate_schedule_overrides(conn)
    assert n == 0


def test_migrate_schedule_overrides_updates_event(conn):
    # Insert the matching event first
    conn.execute("""
        INSERT INTO events (slug, kind, date, name, status, payload_json)
        VALUES ('plan-myplan-2026-04-20', 'training', '2026-04-20', 'Easy run', 'planned', '{}')
    """)
    conn.execute("""
        INSERT INTO schedule_overrides (plan_file, session_date, original_name, new_name, new_details, reason)
        VALUES ('myplan.md', '2026-04-20', 'Easy run', 'Rest', null, 'too tired')
    """)
    n = migrate_schedule_overrides(conn)
    assert n == 1
    row = conn.execute("SELECT name, notes FROM events WHERE slug='plan-myplan-2026-04-20'").fetchone()
    assert row["name"] == "Rest"
    assert row["notes"] == "too tired"


def test_migrate_schedule_overrides_idempotent(conn):
    conn.execute("""
        INSERT INTO events (slug, kind, date, name, status, payload_json)
        VALUES ('plan-p-2026-04-21', 'training', '2026-04-21', 'Tempo', 'planned', '{}')
    """)
    conn.execute("""
        INSERT INTO schedule_overrides (plan_file, session_date, original_name, new_name, reason)
        VALUES ('p.md', '2026-04-21', 'Tempo', 'Easy', 'recovery')
    """)
    n1 = migrate_schedule_overrides(conn)
    n2 = migrate_schedule_overrides(conn)
    # Second run still updates (UPDATE, not INSERT) → 1 again
    assert n1 == 1
    assert n2 == 1


# ── migrate_athlete_yaml_events ───────────────────────────────────────────────


def test_migrate_athlete_yaml_events_no_events(conn, monkeypatch):
    monkeypatch.setattr("coachctl.config.load_athlete", lambda: {})
    n = migrate_athlete_yaml_events(conn)
    assert n == 0


def test_migrate_athlete_yaml_events_inserts(conn, monkeypatch):
    monkeypatch.setattr("coachctl.config.load_athlete", lambda: {
        "events": [
            {"name": "Alpenbrevet", "date": "2026-08-22", "priority": "A"},
            {"name": "Half Marathon", "date": "2026-09-06", "priority": "B"},
        ]
    })
    n = migrate_athlete_yaml_events(conn)
    assert n == 2
    rows = conn.execute("SELECT * FROM events WHERE kind='race'").fetchall()
    names = {r["name"] for r in rows}
    assert "Alpenbrevet" in names
    assert "Half Marathon" in names


def test_migrate_athlete_yaml_events_idempotent(conn, monkeypatch):
    monkeypatch.setattr("coachctl.config.load_athlete", lambda: {
        "events": [{"name": "Tour de France", "date": "2027-07-01", "priority": "C"}]
    })
    n1 = migrate_athlete_yaml_events(conn)
    n2 = migrate_athlete_yaml_events(conn)
    assert n1 == 1
    assert n2 == 0


def test_migrate_athlete_yaml_events_skips_incomplete(conn, monkeypatch):
    """Events without date or name are skipped."""
    monkeypatch.setattr("coachctl.config.load_athlete", lambda: {
        "events": [
            {"name": "", "date": "2026-01-01"},   # empty name
            {"name": "No Date"},                   # missing date
            {"name": "Valid", "date": "2026-06-01"},
        ]
    })
    n = migrate_athlete_yaml_events(conn)
    assert n == 1


def test_migrate_athlete_yaml_events_config_error(conn, monkeypatch):
    """Exception in load_athlete → returns 0, no crash."""
    def broken():
        raise RuntimeError("no yaml")
    monkeypatch.setattr("coachctl.config.load_athlete", broken)
    n = migrate_athlete_yaml_events(conn)
    assert n == 0


# ── run_all ───────────────────────────────────────────────────────────────────


def test_run_all_nothing_to_migrate(conn, monkeypatch):
    monkeypatch.setattr("coachctl.config.load_athlete", lambda: {})
    msg = run_all(conn)
    assert "nothing to migrate" in msg


def test_run_all_summary_message(conn, monkeypatch):
    conn.execute("""
        INSERT INTO untracked_activities (activity_date, sport, duration_min, intensity)
        VALUES ('2026-02-01', 'gym', 60, 'moderate')
    """)
    monkeypatch.setattr("coachctl.config.load_athlete", lambda: {
        "events": [{"name": "Race X", "date": "2026-06-01"}]
    })
    msg = run_all(conn)
    assert "migrated" in msg
    assert "untracked" in msg or "race" in msg
