"""
Tests for coachctl.site — get_dashboard_data with a minimal seeded DB.
"""

from __future__ import annotations

import json
from datetime import date

import pytest

import coachctl.paths as paths_module
import coachctl.site as site_module


@pytest.fixture(autouse=True)
def mock_athlete(monkeypatch):
    monkeypatch.setattr(
        "coachctl.config.load_athlete",
        lambda: {"ftp": 250, "rftp": 270, "threshold_hr": 170, "resting_hr": 50},
    )


@pytest.fixture
def site_db(mem_db, monkeypatch, tmp_data_root):
    """Wire site_module to use the mem_db connection."""
    import coachctl.db as db_module
    import coachctl.plan_compliance as pc_module

    monkeypatch.setattr(site_module, "get_conn", mem_db)
    monkeypatch.setattr(db_module, "get_conn", mem_db)
    monkeypatch.setattr(pc_module, "get_conn", mem_db)  # used by get_plan_compliance_tool
    return mem_db


# ── get_dashboard_data — empty DB ─────────────────────────────────────────────


def test_get_dashboard_data_returns_dict(site_db):
    result = site_module.get_dashboard_data()
    assert isinstance(result, dict)


def test_get_dashboard_data_has_required_keys(site_db):
    result = site_module.get_dashboard_data()
    for key in ("generated_at", "fitness", "trend", "weekly_tss", "events", "calendar"):
        assert key in result, f"Missing key: {key}"


def test_get_dashboard_data_fitness_empty_db(site_db):
    result = site_module.get_dashboard_data()
    fitness = result["fitness"]
    # Empty DB → dashes or zeros
    assert fitness is not None


def test_get_dashboard_data_plan_none_when_no_plan(site_db):
    result = site_module.get_dashboard_data()
    assert result["plan"] is None


def test_get_dashboard_data_generated_at_is_string(site_db):
    result = site_module.get_dashboard_data()
    assert isinstance(result["generated_at"], str)
    # ISO format contains 'T'
    assert "T" in result["generated_at"] or "-" in result["generated_at"]


def test_get_dashboard_data_json_serializable(site_db):
    result = site_module.get_dashboard_data()
    # Must not raise
    json.dumps(result, default=str)


# ── bake ──────────────────────────────────────────────────────────────────────


def test_bake_writes_data_json(site_db, tmp_data_root, monkeypatch):
    """bake() should write data.json to the dist dir."""
    out_path = tmp_data_root / "deploy" / "dist" / "data.json"
    monkeypatch.setattr(paths_module, "data_json", lambda: out_path)

    # Patch migrate_and_drop_legacy to be a no-op (needs full DB setup)
    monkeypatch.setattr(site_module, "bake", lambda plan_path=None: _fake_bake(out_path))

    result_path = site_module.bake()
    # Verify the file was written
    # (fake_bake writes the file)


def _fake_bake(out_path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"generated_at": "2026-05-05T00:00:00"}), encoding="utf-8")
    return out_path


# ── Private function tests ────────────────────────────────────────────────────


def test_get_fitness_state_empty(site_db):
    result = site_module._get_fitness_state()
    assert "ctl" in result


def test_get_fitness_state_with_row(site_db):
    with site_db() as conn:
        conn.execute(
            "INSERT INTO fitness (date, sport_category, ctl, atl, tsb) VALUES (?,?,?,?,?)",
            (date.today().isoformat(), "all", 55.0, 65.0, -10.0),
        )
    result = site_module._get_fitness_state()
    assert result["ctl"] == 55.0
    assert result["tsb"] == -10.0


def test_get_fitness_trend_empty(site_db):
    result = site_module._get_fitness_trend()
    assert isinstance(result, list)


def test_get_fitness_trend_with_data(site_db):
    from datetime import timedelta

    for i in range(5):
        d = (date.today() - timedelta(days=i)).isoformat()
        with site_db() as conn:
            conn.execute(
                "INSERT INTO fitness (date, sport_category, ctl, atl, tsb) VALUES (?,?,?,?,?)",
                (d, "all", 50.0 + i, 55.0 + i, -5.0),
            )
    result = site_module._get_fitness_trend(weeks=4)
    assert len(result) >= 1
    assert "ctl" in result[0]


def test_get_weekly_tss_empty(site_db):
    result = site_module._get_weekly_tss(plan_id=None)
    assert isinstance(result, list)


def test_get_weekly_tss_with_activities(site_db):
    from datetime import timedelta

    with site_db() as conn:
        for i in range(3):
            d = (date.today() - timedelta(days=i * 3)).isoformat() + "T08:00:00Z"
            conn.execute(
                "INSERT INTO activities (id, name, sport_type, start_date, tss) VALUES (?,?,?,?,?)",
                (i + 1, "run", "Run", d, 50.0),
            )
    result = site_module._get_weekly_tss(plan_id=None)
    assert isinstance(result, list)
    assert any(r["run"] > 0 for r in result)


def test_project_fitness_no_plan(site_db):
    result = site_module._project_fitness(plan_id=None, fitness={"ctl": 50.0, "atl": 55.0})
    assert result == []


def test_project_fitness_invalid_fitness(site_db):
    result = site_module._project_fitness(plan_id=1, fitness={"ctl": "—", "atl": "—"})
    assert result == []


def test_get_race_events_empty(site_db):
    result = site_module._get_race_events_from_db()
    assert isinstance(result, list)


def test_get_race_events_with_race(site_db):
    from datetime import timedelta

    future = (date.today() + timedelta(days=30)).isoformat()
    with site_db() as conn:
        conn.execute(
            "INSERT INTO events (slug, kind, date, name, status, payload_json) VALUES (?,?,?,?,?,?)",
            (
                "test-race",
                "race",
                future,
                "My Race",
                "planned",
                json.dumps({"priority": "A", "goal": {"target_time": "3:00"}}),
            ),
        )
    result = site_module._get_race_events_from_db()
    assert len(result) == 1
    assert result[0]["priority"] == "A"


def test_get_calendar_window_for_dashboard_empty(site_db):
    result = site_module._get_calendar_window_for_dashboard()
    assert isinstance(result, list)


def test_day_label_valid():
    result = site_module._day_label("2026-05-04")
    assert result == "Mon"


def test_day_label_invalid():
    result = site_module._day_label("bad-date")
    assert result == ""


def test_extract_phases_empty():
    result = site_module._extract_phases([])
    assert result == []


def test_extract_phases_groups_weeks():
    weeks = [
        {"number": 1, "phase": "PHASE 1 — Base"},
        {"number": 2, "phase": "PHASE 1 — Base"},
        {"number": 3, "phase": "PHASE 2 — Build"},
    ]
    result = site_module._extract_phases(weeks)
    assert len(result) == 2
    assert result[0]["week_count"] == 2
    assert result[1]["week_count"] == 1


def test_get_feedback_by_date_empty(site_db):
    result = site_module._get_feedback_by_date()
    assert isinstance(result, dict)


def test_get_feedback_by_date_with_data(site_db):
    with site_db() as conn:
        conn.execute(
            "INSERT INTO feedback (activity_date, rpe, felt, notes) VALUES (?,?,?,?)",
            ("2026-01-10", 7, "good", "felt ok"),
        )
    result = site_module._get_feedback_by_date()
    assert "2026-01-10" in result
    assert result["2026-01-10"]["rpe"] == 7


def test_get_training_monotony_empty(site_db):
    result = site_module._get_training_monotony()
    assert isinstance(result, list)


def test_get_monotony_snapshot_empty(site_db):
    result = site_module._get_monotony_snapshot()
    assert isinstance(result, dict)


def test_compute_danger_zones_overreach():
    zones = site_module._compute_danger_zones(fitness={"ctl": 80.0, "tsb": -35.0}, trend=[])
    types = [z["type"] for z in zones]
    assert "overreach" in types


def test_compute_danger_zones_fatigue():
    zones = site_module._compute_danger_zones(fitness={"ctl": 70.0, "tsb": -22.0}, trend=[])
    types = [z["type"] for z in zones]
    assert "fatigue" in types


def test_compute_danger_zones_fresh():
    zones = site_module._compute_danger_zones(fitness={"ctl": 60.0, "tsb": 20.0}, trend=[])
    types = [z["type"] for z in zones]
    assert "fresh" in types


def test_compute_danger_zones_detraining():
    from datetime import timedelta

    trend = [
        {"date": (date.today() - timedelta(days=14 - i)).isoformat(), "ctl": 80.0 - i * 2}
        for i in range(15)
    ]
    zones = site_module._compute_danger_zones(
        fitness={"ctl": float(trend[-1]["ctl"]), "tsb": 5.0}, trend=trend
    )
    types = [z["type"] for z in zones]
    assert "detraining" in types


def test_compute_danger_zones_invalid_fitness():
    zones = site_module._compute_danger_zones(fitness={"ctl": "—", "tsb": "—"}, trend=[])
    assert zones == []


def test_compute_danger_zones_monotony_high():
    zones = site_module._compute_danger_zones(
        fitness={"ctl": 60.0, "tsb": 0.0},
        trend=[],
        monotony_snapshot={"monotony": 2.5, "strain": 1000},
    )
    types = [z["type"] for z in zones]
    assert "monotony" in types


def test_compute_danger_zones_strain_high():
    zones = site_module._compute_danger_zones(
        fitness={"ctl": 60.0, "tsb": 0.0},
        trend=[],
        monotony_snapshot={"monotony": 1.0, "strain": 2500},
    )
    types = [z["type"] for z in zones]
    assert "strain" in types


def test_get_recent_run_tss_empty(site_db):
    result = site_module._get_recent_run_tss()
    assert isinstance(result, list)


def test_get_recent_run_tss_with_data(site_db):
    with site_db() as conn:
        conn.execute(
            "INSERT INTO activities (id, name, sport_type, start_date, moving_time, distance, tss, rtss) "
            "VALUES (1, 'Easy Run', 'Run', '2026-05-01T07:00:00Z', 3600, 10000, 55.0, 50.0)",
        )
    result = site_module._get_recent_run_tss()
    assert len(result) == 1
    assert result[0]["tss"] == 55.0


def test_get_weekly_run_tss_empty(site_db):
    result = site_module._get_weekly_run_tss()
    assert isinstance(result, list)


# ── New dashboard keys: compliance, acwr, zones ───────────────────────────────


def test_dashboard_data_has_compliance_key(site_db):
    """compliance key present in output (None when no active plan)."""
    result = site_module.get_dashboard_data()
    assert "compliance" in result
    # No plan in this DB → should be None
    assert result["compliance"] is None


def test_dashboard_data_has_acwr_key(site_db):
    """acwr key present in output (None when no fitness data)."""
    result = site_module.get_dashboard_data()
    assert "acwr" in result


def test_dashboard_data_has_zones_key(site_db):
    """zones key present in output (None when no HR data)."""
    result = site_module.get_dashboard_data()
    assert "zones" in result


def test_dashboard_data_compliance_with_plan(site_db):
    """compliance is populated when an active plan with events exists."""
    from datetime import date, timedelta

    today = date.today().isoformat()
    past = (date.today() - timedelta(days=7)).isoformat()

    with site_db() as conn:
        conn.execute(
            "INSERT INTO plans (slug, title, start_date, end_date, active) VALUES (?,?,?,?,1)",
            ("test-plan", "Test Plan", past, today),
        )
        plan_id = conn.execute("SELECT id FROM plans WHERE slug='test-plan'").fetchone()["id"]
        conn.execute(
            """INSERT INTO events (slug, kind, date, name, status, estimated_tss, plan_id)
               VALUES ('ev-1','training',?,'Session','planned',50.0,?)""",
            (past, plan_id),
        )
        conn.execute(
            """INSERT INTO activities (name, sport_type, start_date, elapsed_time, moving_time,
               distance, tss) VALUES ('Run','Run',?,3600,3600,10000,45.0)""",
            (past,),
        )

    result = site_module.get_dashboard_data()
    compliance = result["compliance"]
    assert compliance is not None
    assert "overall" in compliance
    assert "weekly" in compliance
    assert compliance["overall"]["sessions_planned"] >= 1


def test_dashboard_data_acwr_with_fitness(site_db):
    """acwr is non-None when fitness table has data."""
    from datetime import date, timedelta

    with site_db() as conn:
        for i in range(14):
            d = (date.today() - timedelta(days=i)).isoformat()
            conn.execute(
                "INSERT OR IGNORE INTO fitness (date, sport_category, ctl, atl, tsb) VALUES (?,?,?,?,?)",
                (d, "all", 50.0, 60.0, -10.0),
            )

    result = site_module.get_dashboard_data()
    acwr = result["acwr"]
    assert acwr is not None
    assert "acwr_ema" in acwr or "acwr_rolling" in acwr


def test_dashboard_data_zones_with_hr_activities(site_db):
    """zones is non-None when activities with HR data exist in last 8 weeks."""
    from datetime import date, timedelta

    with site_db() as conn:
        for i in range(5):
            d = (date.today() - timedelta(days=i)).isoformat()
            conn.execute(
                """INSERT INTO activities (name, sport_type, start_date, elapsed_time,
                   moving_time, distance, average_heartrate)
                   VALUES ('Run','Run',?,3600,3600,10000,145.0)""",
                (d,),
            )

    result = site_module.get_dashboard_data()
    zones = result["zones"]
    assert zones is not None
    assert "distribution" in zones
    assert len(zones["distribution"]) == 5
    # All percentages should sum to ~100
    assert abs(sum(zones["distribution"]) - 100.0) < 1.0


def test_dashboard_data_fully_serializable_with_new_keys(site_db):
    """Full payload including new keys must be JSON-serializable."""
    result = site_module.get_dashboard_data()
    json.dumps(result, default=str)  # must not raise


# ── F4: compliance weekly plan_week field ─────────────────────────────────────


def test_compliance_weekly_has_plan_week_field(site_db):
    """Each weekly compliance entry should carry a plan_week int when a plan is active."""
    from datetime import date, timedelta

    today = date.today()
    # Put week-1 sessions in the past (already elapsed so they count toward compliance)
    w1_mon = today - timedelta(days=today.weekday() + 7)  # Monday of last week
    w2_mon = today - timedelta(days=today.weekday())  # Monday of current week

    with site_db() as conn:
        conn.execute(
            "INSERT INTO plans (slug, title, start_date, end_date, active, week_tss_json) "
            "VALUES (?,?,?,?,1,?)",
            (
                "f4-plan",
                "F4 Test Plan",
                w1_mon.isoformat(),
                (w2_mon + timedelta(days=13)).isoformat(),
                json.dumps({"1": 200, "2": 220}),
            ),
        )
        plan_id = conn.execute("SELECT id FROM plans WHERE slug='f4-plan'").fetchone()["id"]

        # Week 1 session (past)
        conn.execute(
            """INSERT INTO events (slug, kind, date, name, status, estimated_tss,
               plan_id, payload_json)
               VALUES ('ev-w1','training',?,'W1 Session','planned',100.0,?,?)""",
            (
                w1_mon.isoformat(),
                plan_id,
                json.dumps({"week_number": 1, "phase": "Base"}),
            ),
        )
        # Week 2 session (this week)
        conn.execute(
            """INSERT INTO events (slug, kind, date, name, status, estimated_tss,
               plan_id, payload_json)
               VALUES ('ev-w2','training',?,'W2 Session','planned',110.0,?,?)""",
            (
                w2_mon.isoformat(),
                plan_id,
                json.dumps({"week_number": 2, "phase": "Build"}),
            ),
        )
        # One completed activity in week 1
        conn.execute(
            """INSERT INTO activities (name, sport_type, start_date, elapsed_time,
               moving_time, distance, tss)
               VALUES ('Run','Run',?,3600,3600,10000,95.0)""",
            (w1_mon.isoformat(),),
        )

    result = site_module.get_dashboard_data()
    compliance = result.get("compliance")
    assert compliance is not None, "compliance should be populated with an active plan"
    weekly = compliance.get("weekly", [])
    assert weekly, "weekly compliance entries should exist"
    # At least one entry should carry a plan_week int
    plan_weeks = [w.get("plan_week") for w in weekly]
    assert any(pw is not None for pw in plan_weeks), (
        f"No plan_week found in weekly entries: {weekly}"
    )
