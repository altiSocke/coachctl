"""
Tests for the TSS estimation wiring in plan insertion and backfill.

Covers:
- _insert_plan_and_events() populates estimated_tss on training events
- backfill_event_tss() fills NULL estimated_tss from existing events
- Events with unparseable details retain estimated_tss = NULL
"""

from __future__ import annotations

import json
import textwrap

import pytest


PLAN_WITH_DURATIONS = textwrap.dedent("""\
    # Test Plan

    **Athlete:** Test Athlete
    **Period:** Jan 2026 – Mar 2026
    **A-Event:** Test Race Mar 1

    ---

    ### Week 1 (Jan 5–11) — Base Entry | Target TSS: ~200

    | Day | Session | Details |
    |-----|---------|---------|
    | Mon Jan 5 | Rest | - |
    | Tue Jan 6 | Easy run | 60 min easy Z2 run |
    | Wed Jan 7 | Strength | 45 min strength work |
    | Thu Jan 8 | Tempo run | 50 min with 20 min tempo |
    | Fri Jan 9 | Rest | - |
    | Sat Jan 10 | Long run | 90 min easy aerobic |
    | Sun Jan 11 | Recovery jog | 30 min recovery |
""")

PLAN_WITHOUT_DURATIONS = textwrap.dedent("""\
    # Bare Plan

    **Athlete:** Test Athlete
    **Period:** Jan 2026 – Mar 2026
    **A-Event:** Test Race Mar 1

    ---

    ### Week 1 (Jan 5–11) — Base Entry | Target TSS: ~200

    | Day | Session | Details |
    |-----|---------|---------|
    | Mon Jan 5 | Rest | - |
    | Tue Jan 6 | Easy run | Easy Z2 run (no duration) |
    | Wed Jan 7 | Tempo | Tempo blocks |
""")


# ── _insert_plan_and_events ───────────────────────────────────────────────────


def test_insert_plan_populates_estimated_tss(mem_db, tmp_data_root, monkeypatch):
    """Sessions with parseable duration + intensity get non-NULL estimated_tss."""
    import coachctl.tools.plan_tools as pt
    import coachctl.db as db_module

    # Patch get_conn in plan_tools to use our mem_db connection
    monkeypatch.setattr(
        pt, "get_conn" if hasattr(pt, "get_conn") else "_unused", mem_db, raising=False
    )

    # Write plan file
    plans_dir = tmp_data_root / "profile" / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    plan_file = plans_dir / "2026-01-05_test.md"
    plan_file.write_text(PLAN_WITH_DURATIONS, encoding="utf-8")

    plan_id = pt._insert_plan_and_events(plan_file, "test", "Test Race", "2026-03-01")
    assert plan_id is not None

    with mem_db() as conn:
        rows = conn.execute(
            "SELECT name, estimated_tss FROM events WHERE kind = 'training' ORDER BY date"
        ).fetchall()

    # Filter out rest days (they're skipped)
    rows_with_name = [(r["name"], r["estimated_tss"]) for r in rows]

    # Easy run: 60 min easy → should have TSS
    easy_row = next(r for r in rows_with_name if "Easy run" in r[0] or "easy" in r[0].lower())
    assert easy_row[1] is not None
    assert easy_row[1] > 0

    # Long run: 90 min easy → should have TSS > Easy run TSS (longer)
    long_row = next(r for r in rows_with_name if "Long" in r[0])
    assert long_row[1] is not None
    assert long_row[1] > easy_row[1]

    # Tempo run: same or higher intensity than easy
    tempo_row = next(r for r in rows_with_name if "Tempo" in r[0])
    assert tempo_row[1] is not None


def test_insert_plan_null_tss_when_no_duration(mem_db, tmp_data_root, monkeypatch):
    """Sessions with no parseable duration get estimated_tss = NULL."""
    import coachctl.tools.plan_tools as pt

    plans_dir = tmp_data_root / "profile" / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    plan_file = plans_dir / "2026-01-05_bare.md"
    plan_file.write_text(PLAN_WITHOUT_DURATIONS, encoding="utf-8")

    plan_id = pt._insert_plan_and_events(plan_file, "bare", "Test Race", "2026-03-01")
    assert plan_id is not None

    with mem_db() as conn:
        rows = conn.execute(
            "SELECT name, estimated_tss FROM events WHERE kind = 'training' ORDER BY date"
        ).fetchall()

    # Sessions without duration should have NULL TSS
    null_tss = [r for r in rows if r["estimated_tss"] is None]
    assert len(null_tss) > 0


def test_insert_plan_tss_values_are_reasonable(mem_db, tmp_data_root, monkeypatch):
    """Spot-check an easy run lands in a sane TSS band (sport-aware IF table)."""
    import coachctl.tools.plan_tools as pt

    plans_dir = tmp_data_root / "profile" / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    plan_file = plans_dir / "2026-01-05_check.md"
    plan_file.write_text(PLAN_WITH_DURATIONS, encoding="utf-8")

    pt._insert_plan_and_events(plan_file, "check", "Test Race", "2026-03-01")

    with mem_db() as conn:
        row = conn.execute(
            "SELECT estimated_tss FROM events WHERE name LIKE '%Easy run%' AND kind='training'"
        ).fetchone()

    assert row is not None
    # 60 min easy run: (60/60) × 0.75² × 100 ≈ 56 TSS (run IF table).
    assert 20 < row["estimated_tss"] < 80


# ── backfill_event_tss ────────────────────────────────────────────────────────


def test_backfill_updates_null_events(mem_db, monkeypatch):
    """backfill_event_tss() updates events that have parseable details."""
    import coachctl.tools.plan_tools as pt

    # Insert a plan row first
    with mem_db() as conn:
        conn.execute("INSERT INTO plans (slug, title, active) VALUES ('p1', 'Plan', 1)")
        plan_id = conn.execute("SELECT id FROM plans WHERE slug='p1'").fetchone()["id"]

        # Event with parseable details in payload_json
        conn.execute(
            """
            INSERT INTO events (slug, kind, date, name, status, payload_json, plan_id, estimated_tss)
            VALUES ('ev-1', 'training', '2026-01-06', 'Easy run', 'planned',
                    ?, ?, NULL)
            """,
            (json.dumps({"details": "60 min easy Z2 run"}), plan_id),
        )
        # Event with no parseable duration
        conn.execute(
            """
            INSERT INTO events (slug, kind, date, name, status, payload_json, plan_id, estimated_tss)
            VALUES ('ev-2', 'training', '2026-01-07', 'Strength', 'planned',
                    ?, ?, NULL)
            """,
            (json.dumps({"details": "Core and strength work"}), plan_id),
        )

    result = pt.backfill_event_tss()

    assert result["updated"] == 1
    assert result["skipped_no_duration"] == 1

    with mem_db() as conn:
        ev1 = conn.execute("SELECT estimated_tss FROM events WHERE slug='ev-1'").fetchone()
        ev2 = conn.execute("SELECT estimated_tss FROM events WHERE slug='ev-2'").fetchone()

    assert ev1["estimated_tss"] is not None
    assert ev1["estimated_tss"] > 0
    assert ev2["estimated_tss"] is None


def test_backfill_falls_back_to_summary(mem_db, monkeypatch):
    """backfill_event_tss() uses summary when payload_json has no details."""
    import coachctl.tools.plan_tools as pt

    with mem_db() as conn:
        conn.execute("INSERT INTO plans (slug, title, active) VALUES ('p2', 'Plan 2', 1)")
        plan_id = conn.execute("SELECT id FROM plans WHERE slug='p2'").fetchone()["id"]
        conn.execute(
            """
            INSERT INTO events (slug, kind, date, name, status, summary, plan_id, estimated_tss)
            VALUES ('ev-s1', 'training', '2026-01-06', 'Tempo run', 'planned',
                    '45 min tempo intervals', ?, NULL)
            """,
            (plan_id,),
        )

    result = pt.backfill_event_tss()

    assert result["updated"] == 1

    with mem_db() as conn:
        row = conn.execute("SELECT estimated_tss FROM events WHERE slug='ev-s1'").fetchone()

    assert row["estimated_tss"] is not None


def test_backfill_skips_already_set(mem_db, monkeypatch):
    """backfill_event_tss() does not touch events that already have estimated_tss."""
    import coachctl.tools.plan_tools as pt

    with mem_db() as conn:
        conn.execute("INSERT INTO plans (slug, title, active) VALUES ('p3', 'Plan 3', 1)")
        plan_id = conn.execute("SELECT id FROM plans WHERE slug='p3'").fetchone()["id"]
        conn.execute(
            """
            INSERT INTO events (slug, kind, date, name, status, payload_json, plan_id, estimated_tss)
            VALUES ('ev-set', 'training', '2026-01-06', 'Easy run', 'planned',
                    ?, ?, 42.0)
            """,
            (json.dumps({"details": "60 min easy run"}), plan_id),
        )

    result = pt.backfill_event_tss()

    # Nothing to update (the event already had a value)
    assert result["updated"] == 0

    with mem_db() as conn:
        row = conn.execute("SELECT estimated_tss FROM events WHERE slug='ev-set'").fetchone()
    # Value should remain untouched
    assert row["estimated_tss"] == 42.0


def test_backfill_recompute_overwrites_existing(mem_db, monkeypatch):
    """recompute=True recomputes events that already have an estimate."""
    import coachctl.tools.plan_tools as pt

    with mem_db() as conn:
        conn.execute("INSERT INTO plans (slug, title, active) VALUES ('p4', 'Plan 4', 1)")
        plan_id = conn.execute("SELECT id FROM plans WHERE slug='p4'").fetchone()["id"]
        conn.execute(
            """
            INSERT INTO events (slug, kind, date, name, status, payload_json, plan_id, estimated_tss)
            VALUES ('ev-ride', 'training', '2026-01-06', 'Z2 ride', 'planned',
                    ?, ?, 999.0)
            """,
            (json.dumps({"details": "90 min easy Z2 ride"}), plan_id),
        )

    result = pt.backfill_event_tss(recompute=True)

    assert result["updated"] == 1
    with mem_db() as conn:
        row = conn.execute("SELECT estimated_tss FROM events WHERE slug='ev-ride'").fetchone()
    # 90min easy ride -> ride IF 0.63 -> ~60 TSS (not the bogus 999, and not the
    # run-table ~84 it would be without sport detection)
    assert row["estimated_tss"] == pytest.approx(0.63**2 * 100 * 1.5, abs=1.0)


def test_backfill_recompute_uses_structured_sport_from_payload(mem_db, monkeypatch):
    """Deterministic-engine events carry payload.workout.sport -> use it directly."""
    import coachctl.tools.plan_tools as pt

    with mem_db() as conn:
        conn.execute("INSERT INTO plans (slug, title, active) VALUES ('p5', 'Plan 5', 1)")
        plan_id = conn.execute("SELECT id FROM plans WHERE slug='p5'").fetchone()["id"]
        # summary says nothing about sport; structured payload says 'ride'
        payload = {
            "schema": "workout_spec.v1",
            "workout": {"sport": "ride", "archetype": "z2_ride"},
        }
        conn.execute(
            """
            INSERT INTO events (slug, kind, date, name, status, summary, payload_json, plan_id, estimated_tss)
            VALUES ('ev-eng', 'training', '2026-01-06', '90min session', 'planned',
                    '90min easy', ?, ?, NULL)
            """,
            (json.dumps(payload), plan_id),
        )

    result = pt.backfill_event_tss()
    assert result["updated"] == 1
    with mem_db() as conn:
        row = conn.execute("SELECT estimated_tss FROM events WHERE slug='ev-eng'").fetchone()
    # ride table, not run table
    assert row["estimated_tss"] == pytest.approx(0.63**2 * 100 * 1.5, abs=1.0)


def test_backfill_uses_strava_sport_from_linked_activity(mem_db, monkeypatch):
    """A linked completed activity's Strava sport_type overrides text keywords."""
    import coachctl.tools.plan_tools as pt

    with mem_db() as conn:
        # The activity is a Run per Strava; the event text misleadingly says 'ride'.
        conn.execute(
            """
            INSERT INTO activities (id, name, sport_type, start_date, moving_time)
            VALUES (5001, 'Morning Run', 'Run', '2026-01-06', 3600)
            """
        )
        conn.execute("INSERT INTO plans (slug, title, active) VALUES ('p6', 'Plan 6', 1)")
        plan_id = conn.execute("SELECT id FROM plans WHERE slug='p6'").fetchone()["id"]
        conn.execute(
            """
            INSERT INTO events (slug, kind, date, name, status, summary, plan_id, activity_id, estimated_tss)
            VALUES ('ev-link', 'training', '2026-01-06', '60min Z2 ride', 'completed',
                    '60min easy Z2 ride', ?, 5001, NULL)
            """,
            (plan_id,),
        )

    result = pt.backfill_event_tss()
    assert result["updated"] == 1
    with mem_db() as conn:
        row = conn.execute("SELECT estimated_tss FROM events WHERE slug='ev-link'").fetchone()
    # Strava says Run -> run IF table (0.75), NOT the ride table the text implies.
    assert row["estimated_tss"] == pytest.approx(0.75**2 * 100, abs=1.0)


def test_recompute_does_not_overwrite_completed_or_linked(mem_db, monkeypatch):
    """--recompute must skip completed/linked events (their estimate is trusted)."""
    import coachctl.tools.plan_tools as pt

    with mem_db() as conn:
        conn.execute(
            "INSERT INTO activities (id, name, sport_type, start_date, moving_time, tss) "
            "VALUES (7777, 'Big ride', 'Ride', '2026-01-06', 16000, 187.7)"
        )
        conn.execute("INSERT INTO plans (slug, title, active) VALUES ('p7', 'Plan 7', 1)")
        plan_id = conn.execute("SELECT id FROM plans WHERE slug='p7'").fetchone()["id"]
        # Completed + linked event whose summary text is WRONG ("95min Z2 run").
        # Recompute from that text would give garbage; it must be left alone.
        conn.execute(
            """
            INSERT INTO events (slug, kind, date, name, status, summary, plan_id, activity_id, estimated_tss)
            VALUES ('ev-done', 'training', '2026-01-06', 'Dolomites Bike Day', 'completed',
                    '95min Z2 run, HR <142bpm', ?, 7777, 190.0)
            """,
            (plan_id,),
        )

    result = pt.backfill_event_tss(recompute=True)

    with mem_db() as conn:
        row = conn.execute("SELECT estimated_tss FROM events WHERE slug='ev-done'").fetchone()
    # untouched — the good planned estimate (190) survives the recompute
    assert row["estimated_tss"] == pytest.approx(190.0)
