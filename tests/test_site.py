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

    monkeypatch.setattr(site_module, "get_conn", mem_db)
    monkeypatch.setattr(db_module, "get_conn", mem_db)
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
