"""
Functional tests for all MCP tool modules.

Each test registers tools into a CaptureMCP instance, then calls the captured
functions directly.  DB-touching tools use the mem_db fixture; path-touching
tools use tmp_data_root (included transitively via mem_db).
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, timedelta
from unittest.mock import patch


# ---------------------------------------------------------------------------
# CaptureMCP — captures decorated functions so we can call them in tests
# ---------------------------------------------------------------------------


class CaptureMCP:
    def __init__(self):
        self.tools: dict = {}

    def tool(self, name: str | None = None, **kwargs):
        def decorator(fn):
            key = name or fn.__name__
            self.tools[key] = fn
            return fn

        return decorator


# ---------------------------------------------------------------------------
# Helper: patch a tool module's get_conn with the mem_db factory
# ---------------------------------------------------------------------------


def _patch_tool_get_conn(monkeypatch, module_name: str, get_conn_factory):
    import importlib

    mod = importlib.import_module(module_name)
    monkeypatch.setattr(mod, "get_conn", get_conn_factory, raising=False)


# ---------------------------------------------------------------------------
# fitness_tools
# ---------------------------------------------------------------------------


class TestFitnessTools:
    def _get_tools(self, mem_db, monkeypatch):
        import coachctl.tools.fitness_tools as m

        monkeypatch.setattr(m, "get_conn", mem_db)
        cap = CaptureMCP()
        m.register(cap)
        return cap.tools, mem_db

    def test_get_fitness_state_empty(self, mem_db, monkeypatch):
        tools, _ = self._get_tools(mem_db, monkeypatch)
        result = json.loads(tools["get_fitness_state"]())
        assert "ctl" in result

    def test_get_fitness_state_sport_filter(self, mem_db, monkeypatch):
        tools, _ = self._get_tools(mem_db, monkeypatch)
        result = json.loads(tools["get_fitness_state"](sport="run"))
        assert "ctl" in result

    def test_get_fitness_trend_no_data(self, mem_db, monkeypatch):
        tools, _ = self._get_tools(mem_db, monkeypatch)
        result = tools["get_fitness_trend"]()
        assert "No TSS data" in result or isinstance(json.loads(result), list)

    def test_get_fitness_trend_with_data(self, mem_db, monkeypatch):
        # Insert some activities with TSS
        with mem_db() as conn:
            for i in range(5):
                d = (date.today() - timedelta(days=i * 7)).isoformat()
                conn.execute(
                    "INSERT INTO activities (id, name, sport_type, start_date, tss) VALUES (?,?,?,?,?)",
                    (i + 1, f"run {i}", "Run", d, 60.0),
                )
        tools, _ = self._get_tools(mem_db, monkeypatch)
        result = tools["get_fitness_trend"](weeks=4)
        data = json.loads(result)
        # Tool returns {days: [...], sparklines: {...}} for short windows
        assert isinstance(data, dict)
        assert "days" in data
        assert isinstance(data["days"], list)

    def test_get_fitness_trend_weekly_summary(self, mem_db, monkeypatch):
        # Insert enough data to trigger weekly summary (weeks > 8 and > 60 points)
        with mem_db() as conn:
            for i in range(70):
                d = (date.today() - timedelta(days=i)).isoformat()
                conn.execute(
                    "INSERT INTO activities (id, name, sport_type, start_date, tss) VALUES (?,?,?,?,?)",
                    (i + 1, f"run {i}", "Run", d, 50.0),
                )
        tools, _ = self._get_tools(mem_db, monkeypatch)
        result = tools["get_fitness_trend"](weeks=10)
        data = json.loads(result)
        # Tool returns {weeks: [...], sparklines: {...}} for long windows
        assert isinstance(data, dict)
        assert "weeks" in data
        assert isinstance(data["weeks"], list)

    def test_get_zone_distribution(self, mem_db, monkeypatch):
        tools, _ = self._get_tools(mem_db, monkeypatch)
        result = json.loads(tools["get_zone_distribution"]())
        assert isinstance(result, dict)

    def test_get_weekly_summary_empty(self, mem_db, monkeypatch):
        tools, _ = self._get_tools(mem_db, monkeypatch)
        result = json.loads(tools["get_weekly_summary"]())
        # Tool returns {weeks: [...], sparklines: {...}}
        assert isinstance(result, dict)
        assert "weeks" in result
        assert isinstance(result["weeks"], list)

    def test_get_weekly_summary_with_data(self, mem_db, monkeypatch):
        with mem_db() as conn:
            d = (date.today() - timedelta(days=3)).isoformat()
            conn.execute(
                "INSERT INTO activities (id, name, sport_type, start_date, moving_time, distance, tss) "
                "VALUES (1, 'Morning Run', 'Run', ?, 3600, 10000, 55.0)",
                (d,),
            )
        tools, _ = self._get_tools(mem_db, monkeypatch)
        result = json.loads(tools["get_weekly_summary"]())
        # Tool returns {weeks: [...], sparklines: {...}}
        assert isinstance(result, dict)
        assert "weeks" in result
        assert len(result["weeks"]) > 0

    def test_get_efficiency_factor_trend_empty(self, mem_db, monkeypatch):
        tools, _ = self._get_tools(mem_db, monkeypatch)
        result = tools["get_efficiency_factor_trend"]()
        # Empty DB → returns a string message
        assert isinstance(result, str)

    def test_get_efficiency_factor_trend_with_ride_data(self, mem_db, monkeypatch):
        with mem_db() as conn:
            for i in range(6):
                d = (date.today() - timedelta(days=i * 10)).isoformat()
                conn.execute(
                    "INSERT INTO activities (id, name, sport_type, start_date, moving_time, "
                    "average_heartrate, weighted_avg_watts, intensity_factor) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (i + 1, f"Ride {i}", "Ride", d, 3600, 130.0, 180.0, 0.72),
                )
        tools, _ = self._get_tools(mem_db, monkeypatch)
        result = json.loads(tools["get_efficiency_factor_trend"](sport="ride", weeks=16))
        assert "summary" in result
        assert "sessions" in result
        summary = result["summary"]
        assert summary["trend"] in ("rising", "stable", "declining", "insufficient_data")

    def test_get_efficiency_factor_trend_with_run_data(self, mem_db, monkeypatch):
        with mem_db() as conn:
            for i in range(6):
                d = (date.today() - timedelta(days=i * 10)).isoformat()
                conn.execute(
                    "INSERT INTO activities (id, name, sport_type, start_date, moving_time, "
                    "average_heartrate, ngp) VALUES (?,?,?,?,?,?,?)",
                    (i + 1, f"Run {i}", "Run", d, 3600, 140.0, 3.5),
                )
        tools, _ = self._get_tools(mem_db, monkeypatch)
        result = json.loads(tools["get_efficiency_factor_trend"](sport="run", weeks=16))
        assert "sessions" in result

    def test_get_best_efforts_empty(self, mem_db, monkeypatch):
        tools, _ = self._get_tools(mem_db, monkeypatch)
        result = json.loads(tools["get_best_efforts"]())
        # Empty DB → empty run/ride lists
        assert "run" in result or "ride" in result

    def test_get_best_efforts_with_run(self, mem_db, monkeypatch):
        with mem_db() as conn:
            conn.execute(
                "INSERT INTO activities (id, name, sport_type, start_date, moving_time, distance) "
                "VALUES (1, '5km Race', 'Run', ?, 1200, 5000)",
                ((date.today() - timedelta(days=10)).isoformat(),),
            )
        tools, _ = self._get_tools(mem_db, monkeypatch)
        result = json.loads(tools["get_best_efforts"](sport="run"))
        assert "run" in result
        # Should have pace_5km entry
        efforts = {e["effort"]: e for e in result["run"]}
        assert "pace_5km" in efforts
        assert efforts["pace_5km"]["all_time"] is not None

    def test_get_best_efforts_sport_filter(self, mem_db, monkeypatch):
        tools, _ = self._get_tools(mem_db, monkeypatch)
        result_run = json.loads(tools["get_best_efforts"](sport="run"))
        assert "ride" not in result_run
        result_ride = json.loads(tools["get_best_efforts"](sport="ride"))
        assert "run" not in result_ride

    def test_get_critical_power_no_data(self, mem_db, monkeypatch):
        tools, _ = self._get_tools(mem_db, monkeypatch)
        result = json.loads(tools["get_critical_power"]())
        # No stream data → error key
        assert "error" in result

    def test_get_projected_fitness_invalid_date(self, mem_db, monkeypatch):
        tools, _ = self._get_tools(mem_db, monkeypatch)
        result = tools["get_projected_fitness"]("not-a-date")
        assert "Error" in result

    def test_get_projected_fitness_past_date(self, mem_db, monkeypatch):
        tools, _ = self._get_tools(mem_db, monkeypatch)
        past = (date.today() - timedelta(days=5)).isoformat()
        result = tools["get_projected_fitness"](past)
        # No TSS data in empty DB → plain string message, or JSON error
        try:
            parsed = json.loads(result)
            assert "error" in parsed
        except json.JSONDecodeError:
            assert "No TSS data" in result or "error" in result.lower()

    def test_get_projected_fitness_future(self, mem_db, monkeypatch):
        with mem_db() as conn:
            for i in range(60):
                d = (date.today() - timedelta(days=i)).isoformat()
                conn.execute(
                    "INSERT INTO activities (id, name, sport_type, start_date, tss) "
                    "VALUES (?,?,?,?,?)",
                    (i + 1, f"Run {i}", "Run", d, 50.0),
                )
        tools, _ = self._get_tools(mem_db, monkeypatch)
        target = (date.today() + timedelta(days=60)).isoformat()
        result = json.loads(tools["get_projected_fitness"](target, weekly_tss=350.0))
        assert "projected" in result
        assert "form_status" in result
        assert result["form_status"] in (
            "optimal",
            "under-tapered",
            "over-tapered",
            "heavily_over-tapered",
        )

    def test_get_intensity_distribution_empty(self, mem_db, monkeypatch):
        tools, _ = self._get_tools(mem_db, monkeypatch)
        result = json.loads(tools["get_intensity_distribution"]())
        # Tool returns {overall: {...}, run: {...}, ride: {...}}; each sub-dict has "error" when no data
        assert isinstance(result, dict)
        assert "overall" in result
        assert "error" in result["overall"]

    def test_get_intensity_distribution_with_data(self, mem_db, monkeypatch):
        with mem_db() as conn:
            for i in range(10):
                d = (date.today() - timedelta(days=i * 3)).isoformat()
                hr = 130 + (i % 3) * 20  # varies: 130, 150, 170
                conn.execute(
                    "INSERT INTO activities (id, name, sport_type, start_date, "
                    "moving_time, average_heartrate) VALUES (?,?,?,?,?,?)",
                    (i + 1, f"Run {i}", "Run", d, 3600, float(hr)),
                )
        tools, _ = self._get_tools(mem_db, monkeypatch)
        result = json.loads(tools["get_intensity_distribution"](weeks=8))
        # Tool returns {overall: {...}, run: {...}, ride: {...}}
        assert isinstance(result, dict)
        assert "overall" in result
        overall = result["overall"]
        assert "distribution_pct" in overall
        assert "classification" in overall
        dist = overall["distribution_pct"]
        assert abs(dist["easy"] + dist["moderate"] + dist["hard"] - 100.0) < 0.5

    def test_get_vo2max_estimate(self, mem_db, monkeypatch):
        import coachctl.tools.fitness_tools as m

        monkeypatch.setattr(
            m,
            "load_athlete",
            lambda: {"ftp": 250, "weight_kg": 70, "rftp": 270, "threshold_hr": 170},
            raising=False,
        )
        # Also patch via config module path used inside the tool
        import coachctl.config as cfg_mod

        monkeypatch.setattr(
            cfg_mod, "load_athlete", lambda: {"ftp": 250, "weight_kg": 70, "rftp": 270}
        )
        tools, _ = self._get_tools(mem_db, monkeypatch)
        result = json.loads(tools["get_vo2max_estimate"]())
        assert isinstance(result, dict)

    def test_estimate_week_tss_invalid_json(self, mem_db, monkeypatch):
        tools, _ = self._get_tools(mem_db, monkeypatch)
        result = tools["estimate_week_tss_tool"](sessions_json="not-json")
        assert "Error" in result

    def test_estimate_week_tss_not_list(self, mem_db, monkeypatch):
        tools, _ = self._get_tools(mem_db, monkeypatch)
        result = tools["estimate_week_tss_tool"](sessions_json='{"key": "val"}')
        assert "Error" in result

    def test_estimate_week_tss_with_sessions(self, mem_db, monkeypatch):
        tools, _ = self._get_tools(mem_db, monkeypatch)
        sessions = json.dumps(
            [
                {"sport": "run", "duration_min": 60, "intensity": "easy"},
                {"sport": "ride", "duration_min": 90, "intensity": "moderate"},
            ]
        )
        result = json.loads(tools["estimate_week_tss_tool"](sessions_json=sessions))
        assert "total_tss_estimate" in result
        assert result["total_tss_estimate"] > 0

    def test_predict_race_time_with_reference(self, mem_db, monkeypatch):
        tools, _ = self._get_tools(mem_db, monkeypatch)
        result = json.loads(
            tools["predict_race_time"](
                reference_distance_km=21.1,
                reference_time="1:45:00",
                mode="road",
            )
        )
        assert "predictions" in result
        assert any(p["distance"] == "Marathon" for p in result["predictions"])

    def test_predict_race_time_invalid_mode(self, mem_db, monkeypatch):
        tools, _ = self._get_tools(mem_db, monkeypatch)
        result = tools["predict_race_time"](
            reference_distance_km=10, reference_time="45:00", mode="bad"
        )
        assert "Error" in result

    def test_predict_race_time_only_dist_no_time(self, mem_db, monkeypatch):
        tools, _ = self._get_tools(mem_db, monkeypatch)
        result = tools["predict_race_time"](reference_distance_km=10.0, reference_time="")
        assert "Error" in result


# ---------------------------------------------------------------------------
# feedback_tools
# ---------------------------------------------------------------------------


class TestFeedbackTools:
    def _get_tools(self, mem_db, monkeypatch):
        import coachctl.tools.feedback_tools as m

        monkeypatch.setattr(m, "get_conn", mem_db)
        cap = CaptureMCP()
        m.register(cap)
        return cap.tools

    def test_log_feedback_basic(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        result = tools["log_feedback"](activity_date="2026-01-15", rpe=7, felt="good")
        assert "2026-01-15" in result
        assert "7" in result

    def test_log_feedback_with_activity_id(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        result = tools["log_feedback"](
            activity_date="2026-01-15", rpe=5, felt="ok", notes="felt fine", activity_id=123
        )
        assert "2026-01-15" in result

    def test_get_recent_feedback_empty(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        result = json.loads(tools["get_recent_feedback"]())
        assert result == []

    def test_get_recent_feedback_with_data(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        tools["log_feedback"](activity_date="2026-01-10", rpe=6, felt="good")
        tools["log_feedback"](activity_date="2026-01-11", rpe=7, felt="great")
        result = json.loads(tools["get_recent_feedback"](n=5))
        assert len(result) == 2

    def test_save_coaching_note(self, mem_db, monkeypatch, tmp_data_root):
        tools = self._get_tools(mem_db, monkeypatch)
        # Seed the training_history.md file
        profile_dir = tmp_data_root / "profile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        (profile_dir / "training_history.md").write_text("# History\n", encoding="utf-8")
        (profile_dir / "log.md").write_text("", encoding="utf-8")
        result = tools["save_coaching_note"](
            note="Great threshold run today", category="observation", tags="run,threshold"
        )
        assert "training_history.md" in result

    def test_get_coaching_notes_no_file(self, mem_db, monkeypatch, tmp_data_root):
        tools = self._get_tools(mem_db, monkeypatch)
        # Ensure file doesn't exist
        p = tmp_data_root / "profile" / "training_history.md"
        if p.exists():
            p.unlink()
        result = tools["get_coaching_notes"]()
        assert "not found" in result

    def test_get_coaching_notes_with_content(self, mem_db, monkeypatch, tmp_data_root):
        tools = self._get_tools(mem_db, monkeypatch)
        profile_dir = tmp_data_root / "profile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        content = "# History\n\n### 2026-01-10\n**general**:\nNote one\n\n### 2026-01-11\n**observation**:\nNote two\n"
        (profile_dir / "training_history.md").write_text(content, encoding="utf-8")
        result = tools["get_coaching_notes"](n=5)
        assert "Note" in result

    def test_get_coaching_notes_category_filter(self, mem_db, monkeypatch, tmp_data_root):
        tools = self._get_tools(mem_db, monkeypatch)
        profile_dir = tmp_data_root / "profile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        content = "# History\n\n### 2026-01-10\n**general**:\nGeneral note\n\n### 2026-01-11\n**observation**:\nObservation note\n"
        (profile_dir / "training_history.md").write_text(content, encoding="utf-8")
        result = tools["get_coaching_notes"](category="observation")
        assert "Observation" in result

    def test_log_feedback_invalid_date(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        result = tools["log_feedback"](activity_date="not-a-date", rpe=5, felt="ok")
        assert (
            "not a valid" in result.lower()
            or "invalid" in result.lower()
            or "refusing" in result.lower()
        )

    def test_log_feedback_invalid_rpe(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        result = tools["log_feedback"](activity_date="2026-01-15", rpe=11, felt="ok")
        assert "rpe" in result.lower()

    def test_log_feedback_invalid_felt(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        result = tools["log_feedback"](activity_date="2026-01-15", rpe=7, felt="meh")
        assert "felt" in result.lower()


# ---------------------------------------------------------------------------
# untracked_tools
# ---------------------------------------------------------------------------


class TestUntrackedTools:
    def _get_tools(self, mem_db, monkeypatch, tmp_data_root):
        import coachctl.tools.untracked_tools as m

        monkeypatch.setattr(m, "get_conn", mem_db)
        cap = CaptureMCP()
        m.register(cap)
        return cap.tools

    def test_log_untracked_hockey(self, mem_db, monkeypatch, tmp_data_root):
        tools = self._get_tools(mem_db, monkeypatch, tmp_data_root)
        result = tools["log_untracked_activity"](
            activity_date="2026-01-15", sport="hockey", duration_min=60
        )
        assert "hockey" in result
        assert "60" in result

    def test_log_untracked_tss_override(self, mem_db, monkeypatch, tmp_data_root):
        tools = self._get_tools(mem_db, monkeypatch, tmp_data_root)
        result = tools["log_untracked_activity"](
            activity_date="2026-01-15", sport="gym", duration_min=45, tss_override=30.0
        )
        assert "30.0" in result

    def test_log_untracked_hard_intensity(self, mem_db, monkeypatch, tmp_data_root):
        tools = self._get_tools(mem_db, monkeypatch, tmp_data_root)
        result = tools["log_untracked_activity"](
            activity_date="2026-01-15", sport="yoga", duration_min=30, intensity="hard"
        )
        assert "yoga" in result

    def test_get_untracked_activities_empty(self, mem_db, monkeypatch, tmp_data_root):
        tools = self._get_tools(mem_db, monkeypatch, tmp_data_root)
        result = json.loads(tools["get_untracked_activities"]())
        assert result == []

    def test_get_untracked_activities_with_data(self, mem_db, monkeypatch, tmp_data_root):
        tools = self._get_tools(mem_db, monkeypatch, tmp_data_root)
        tools["log_untracked_activity"](
            activity_date=date.today().isoformat(), sport="hockey", duration_min=60
        )
        result = json.loads(tools["get_untracked_activities"]())
        assert len(result) == 1
        assert result[0]["sport"] == "hockey"

    def test_check_weekly_untracked_due(self, mem_db, monkeypatch, tmp_data_root):
        tools = self._get_tools(mem_db, monkeypatch, tmp_data_root)
        result = json.loads(tools["check_weekly_untracked"]())
        assert result["due"] is True

    def test_mark_weekly_checkin_done(self, mem_db, monkeypatch, tmp_data_root):
        tools = self._get_tools(mem_db, monkeypatch, tmp_data_root)
        result = tools["mark_weekly_checkin_done"]()
        assert "complete" in result.lower()

    def test_check_weekly_untracked_not_due(self, mem_db, monkeypatch, tmp_data_root):
        tools = self._get_tools(mem_db, monkeypatch, tmp_data_root)
        tools["mark_weekly_checkin_done"]()
        result = json.loads(tools["check_weekly_untracked"]())
        assert result["due"] is False

    def test_log_untracked_invalid_date(self, mem_db, monkeypatch, tmp_data_root):
        tools = self._get_tools(mem_db, monkeypatch, tmp_data_root)
        result = tools["log_untracked_activity"](
            activity_date="not-a-date", sport="hockey", duration_min=60
        )
        assert (
            "not a valid" in result.lower()
            or "invalid" in result.lower()
            or "refusing" in result.lower()
        )


# ---------------------------------------------------------------------------
# activity_tools
# ---------------------------------------------------------------------------


class TestActivityTools:
    def _get_tools(self, mem_db, monkeypatch):
        import coachctl.tools.activity_tools as m

        monkeypatch.setattr(m, "get_conn", mem_db)
        cap = CaptureMCP()
        m.register(cap)
        return cap.tools

    def _insert_activity(self, mem_db, activity_id=1, sport="Run"):
        with mem_db() as conn:
            conn.execute(
                "INSERT INTO activities (id, name, sport_type, start_date, moving_time, distance, "
                "average_heartrate, average_speed, tss) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    activity_id,
                    "Test Run",
                    sport,
                    "2026-01-10T07:00:00Z",
                    3600,
                    12000,
                    145.0,
                    3.33,
                    55.0,
                ),
            )

    def test_get_activity_detail_not_found(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        result = tools["get_activity_detail"](activity_id=999)
        assert "not found" in result

    def test_get_activity_detail_found(self, mem_db, monkeypatch):
        self._insert_activity(mem_db)
        tools = self._get_tools(mem_db, monkeypatch)
        result = json.loads(tools["get_activity_detail"](activity_id=1))
        assert result["id"] == 1
        assert result["name"] == "Test Run"

    def test_get_activity_detail_run_has_pace(self, mem_db, monkeypatch):
        self._insert_activity(mem_db, sport="Run")
        tools = self._get_tools(mem_db, monkeypatch)
        result = json.loads(tools["get_activity_detail"](activity_id=1))
        # Should have average_pace for runs
        assert "average_pace" in result

    def test_get_recent_activities_empty(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        result = json.loads(tools["get_recent_activities"]())
        assert result == []

    def test_get_recent_activities_with_data(self, mem_db, monkeypatch):
        self._insert_activity(mem_db, 1, "Run")
        self._insert_activity(mem_db, 2, "Ride")
        tools = self._get_tools(mem_db, monkeypatch)
        result = json.loads(tools["get_recent_activities"]())
        assert len(result) == 2

    def test_get_recent_activities_sport_filter(self, mem_db, monkeypatch):
        self._insert_activity(mem_db, 1, "Run")
        self._insert_activity(mem_db, 2, "Ride")
        tools = self._get_tools(mem_db, monkeypatch)
        result = json.loads(tools["get_recent_activities"](sport="run"))
        assert len(result) == 1

    def test_find_similar_workouts(self, mem_db, monkeypatch):
        self._insert_activity(mem_db, 1, "Run")
        tools = self._get_tools(mem_db, monkeypatch)
        result = json.loads(tools["find_similar_workouts"](sport="run", min_tss=0, max_tss=100))
        assert len(result) == 1

    def test_find_similar_workouts_tss_filter(self, mem_db, monkeypatch):
        self._insert_activity(mem_db, 1, "Run")
        tools = self._get_tools(mem_db, monkeypatch)
        result = json.loads(tools["find_similar_workouts"](sport="run", min_tss=200, max_tss=999))
        assert result == []

    def test_get_new_activities_empty(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        result = json.loads(tools["get_new_activities"]())
        assert result == []

    def test_get_new_activities_returns_unreviewed(self, mem_db, monkeypatch):
        recent_date = (date.today() - timedelta(days=3)).isoformat() + "T08:00:00Z"
        with mem_db() as conn:
            conn.execute(
                "INSERT INTO activities (id, name, sport_type, start_date, moving_time, distance, tss) "
                "VALUES (1, 'Easy Run', 'Run', ?, 3600, 10000, 50.0)",
                (recent_date,),
            )
        tools = self._get_tools(mem_db, monkeypatch)
        result = json.loads(tools["get_new_activities"]())
        assert len(result) == 1

    def test_mark_activities_reviewed(self, mem_db, monkeypatch):
        self._insert_activity(mem_db)
        tools = self._get_tools(mem_db, monkeypatch)
        result = tools["mark_activities_reviewed"](activity_ids=[1])
        assert "1" in result
        with mem_db() as conn:
            row = conn.execute("SELECT reviewed_at FROM activities WHERE id=1").fetchone()
        assert row["reviewed_at"] is not None

    def test_get_activity_streams_cached(self, mem_db, monkeypatch):
        """Test that cached streams are returned without Strava call."""
        self._insert_activity(mem_db, 1, "Run")
        streams_data = {
            "time": {"data": [0, 1, 2, 3, 4]},
            "heartrate": {"data": [130, 135, 140, 138, 136]},
            "velocity_smooth": {"data": [3.0, 3.1, 3.2, 3.1, 3.0]},
        }
        with mem_db() as conn:
            conn.execute(
                "INSERT INTO activity_streams (activity_id, streams_json) VALUES (1, ?)",
                (json.dumps(streams_data),),
            )
        tools = self._get_tools(mem_db, monkeypatch)
        with patch(
            "coachctl.tools.activity_tools.load_athlete",
            return_value={"threshold_hr": 170, "resting_hr": 50, "ftp": 280},
        ):
            result = json.loads(tools["get_activity_streams"](activity_id=1))
        assert result["activity_id"] == 1

    def test_get_activity_streams_not_cached(self, mem_db, monkeypatch):
        """Test streams fetch failure path."""
        self._insert_activity(mem_db, 1, "Run")
        tools = self._get_tools(mem_db, monkeypatch)
        with patch(
            "coachctl.tools.activity_tools.get_strava_access_token",
            side_effect=Exception("no token"),
        ):
            result = tools["get_activity_streams"](activity_id=1)
        assert "Failed to fetch" in result


# ---------------------------------------------------------------------------
# athlete_tools
# ---------------------------------------------------------------------------


class TestAthleteTools:
    def _get_tools(self, mem_db, monkeypatch):
        import coachctl.tools.athlete_tools as m

        monkeypatch.setattr(m, "get_conn", mem_db)
        cap = CaptureMCP()
        m.register(cap)
        return cap.tools

    def test_get_athlete_profile_no_config(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        with patch("coachctl.tools.athlete_tools.load_athlete", return_value={}):
            result = tools["get_athlete_profile"]()
        assert "No athlete" in result

    def test_get_athlete_profile_with_config(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        athlete = {"name": "Alice", "ftp": 280, "threshold_hr": 170, "rftp": 270, "resting_hr": 50}
        with patch("coachctl.tools.athlete_tools.load_athlete", return_value=athlete):
            result = json.loads(tools["get_athlete_profile"]())
        assert result["name"] == "Alice"
        assert "power_zones" in result
        assert "pace_zones" in result
        assert "hr_zones" in result

    def test_get_athlete_profile_deep_empty_db(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        with patch(
            "coachctl.tools.athlete_tools.load_athlete",
            return_value={"threshold_hr": 170, "resting_hr": 50},
        ):
            result = json.loads(tools["get_athlete_profile_deep"]())
        assert "training_age_years" in result

    def test_get_athlete_profile_deep_with_activities(self, mem_db, monkeypatch):
        with mem_db() as conn:
            for i in range(3):
                d = (date.today() - timedelta(days=i * 30)).isoformat() + "T08:00:00Z"
                conn.execute(
                    "INSERT INTO activities (id, name, sport_type, start_date, moving_time, distance, "
                    "average_heartrate, tss) VALUES (?,?,?,?,?,?,?,?)",
                    (i + 1, f"Run {i}", "Run", d, 3600, 10000, 145.0, 55.0),
                )
        tools = self._get_tools(mem_db, monkeypatch)
        with patch(
            "coachctl.tools.athlete_tools.load_athlete",
            return_value={"threshold_hr": 170, "resting_hr": 50},
        ):
            result = json.loads(tools["get_athlete_profile_deep"]())
        assert result["total_activities"] == 3


# ---------------------------------------------------------------------------
# readiness_tools
# ---------------------------------------------------------------------------


class TestReadinessTools:
    def _get_tools(self, mem_db, monkeypatch):
        import coachctl.tools.readiness_tools as m

        monkeypatch.setattr(m, "get_conn", mem_db)
        cap = CaptureMCP()
        m.register(cap)
        return cap.tools

    def test_log_readiness_invalid_score(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        result = tools["log_readiness_checkin"](sleep=6, energy=3, soreness=3)
        assert "Invalid" in result

    def test_log_readiness_low_score_gate(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        result = tools["log_readiness_checkin"](
            sleep=2, energy=3, soreness=4, checkin_date="2026-01-10"
        )
        assert "Z2" in result or "<= 2" in result

    def test_log_readiness_good_scores(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        result = tools["log_readiness_checkin"](
            sleep=4, energy=4, soreness=5, checkin_date="2026-01-10"
        )
        assert "proceed" in result.lower()

    def test_log_readiness_mixed_scores(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        result = tools["log_readiness_checkin"](
            sleep=3, energy=3, soreness=3, checkin_date="2026-01-10"
        )
        assert "Mixed" in result or "judgement" in result

    def test_get_readiness_history_empty(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        result = tools["get_readiness_history"]()
        assert "No readiness" in result

    def test_get_readiness_history_with_data(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        recent = (date.today() - timedelta(days=5)).isoformat()
        tools["log_readiness_checkin"](sleep=4, energy=4, soreness=4, checkin_date=recent)
        result = tools["get_readiness_history"](days=30)
        assert recent in result

    def test_get_readiness_history_clamps_days(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        result = tools["get_readiness_history"](days=999)
        # Should not crash, just clamp to 90
        assert "No readiness" in result or "Date" in result

    def test_log_readiness_invalid_date(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        result = tools["log_readiness_checkin"](
            sleep=4, energy=4, soreness=4, checkin_date="bad-date"
        )
        assert (
            "not a valid" in result.lower()
            or "invalid" in result.lower()
            or "refusing" in result.lower()
        )


# ---------------------------------------------------------------------------
# event_tools
# ---------------------------------------------------------------------------


class TestEventTools:
    def _get_tools(self, mem_db, monkeypatch):
        import coachctl.tools.event_tools as m
        import coachctl.events as events_mod

        monkeypatch.setattr(events_mod, "get_conn", mem_db)
        cap = CaptureMCP()
        m.register(cap)
        return cap.tools

    def test_get_calendar_window_empty(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        result = json.loads(tools["get_calendar_window"]())
        assert isinstance(result, list)

    def test_get_calendar_window_invalid_date(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        try:
            tools["get_calendar_window"](start="not-a-date")
            assert False, "should raise"
        except ValueError:
            pass

    def test_get_calendar_window_unknown_kind(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        result = tools["get_calendar_window"](kinds="bogus")
        assert "Error" in result

    def test_get_event_detail_not_found(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        result = json.loads(tools["get_event_detail"](slug="nope"))
        assert result is None

    def test_date_is_free(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        result = json.loads(tools["date_is_free"](d=date.today().isoformat()))
        assert result["free"] is True

    def test_create_event_training(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        result = tools["create_event"](kind="training", date="2026-03-01", name="Long Run")
        assert "Created" in result

    def test_create_event_invalid_kind(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        result = tools["create_event"](kind="bogus", date="2026-03-01", name="x")
        assert "Error" in result

    def test_create_event_activity_reserved(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        result = tools["create_event"](kind="activity", date="2026-03-01", name="x")
        assert "Error" in result

    def test_create_event_duplicate_slug(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        tools["create_event"](kind="training", date="2026-03-01", name="Run", slug="my-run")
        result = tools["create_event"](
            kind="training", date="2026-03-02", name="Run2", slug="my-run"
        )
        assert "already exists" in result

    def test_create_race(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        result = tools["create_race"](date="2026-06-01", name="City Marathon", priority="A")
        assert "Created race" in result

    def test_create_race_invalid_priority(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        result = tools["create_race"](date="2026-06-01", name="x", priority="D")
        assert "Error" in result

    def test_update_event(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        tools["create_event"](kind="training", date="2026-03-01", name="Run", slug="test-ev")
        result = tools["update_event"](slug="test-ev", name="Long Run Updated")
        assert "Updated" in result

    def test_update_event_not_found(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        result = tools["update_event"](slug="ghost")
        assert "Error" in result

    def test_update_event_invalid_status(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        tools["create_event"](kind="training", date="2026-03-01", name="Run", slug="test-ev2")
        result = tools["update_event"](slug="test-ev2", status="flying")
        assert "Error" in result

    def test_cancel_event(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        tools["create_event"](kind="training", date="2026-03-01", name="Run", slug="canc-ev")
        result = tools["cancel_event"](slug="canc-ev", reason="sick")
        assert "Cancelled" in result

    def test_cancel_event_not_found(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        result = tools["cancel_event"](slug="ghost")
        assert "Error" in result

    def test_delete_event(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        tools["create_event"](kind="training", date="2026-03-01", name="Run", slug="del-ev")
        result = tools["delete_event"](slug="del-ev")
        assert "Deleted" in result

    def test_delete_event_not_found(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        result = tools["delete_event"](slug="ghost")
        assert "Error" in result or "not found" in result

    def test_propose_race_section(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        tools["create_race"](date="2026-06-01", name="Test Race", slug="test-race")
        result = tools["propose_race_pacing"](
            slug="test-race",
            content_json=json.dumps([{"km": 1, "target_pace": "4:30", "hr_zone": "Z2"}]),
        )
        # Returns a diff or "(no changes)"
        assert isinstance(result, str)

    def test_propose_race_section_not_found(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        result = tools["propose_race_pacing"](slug="ghost", content_json="{}")
        assert "Error" in result

    def test_propose_race_section_invalid_json(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        tools["create_race"](date="2026-06-01", name="Test Race 2", slug="test-race2")
        result = tools["propose_race_pacing"](slug="test-race2", content_json="{invalid}")
        assert "Error" in result

    def test_apply_race_section(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        tools["create_race"](date="2026-06-01", name="Apply Race", slug="apply-race")
        result = tools["apply_race_goal"](
            slug="apply-race",
            content_json=json.dumps({"a": "sub-3h", "b": "3:05", "c": "finish"}),
        )
        assert "Updated" in result

    def test_get_event_detail_after_create(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        tools["create_event"](kind="training", date="2026-04-01", name="Intervals", slug="int-ev")
        result = json.loads(tools["get_event_detail"](slug="int-ev"))
        assert result["name"] == "Intervals"


# ---------------------------------------------------------------------------
# wiki_tools
# ---------------------------------------------------------------------------


class TestWikiTools:
    def _get_tools(self, mem_db, monkeypatch):
        import coachctl.tools.wiki_tools as m
        import coachctl.events as events_mod

        monkeypatch.setattr(events_mod, "get_conn", mem_db)
        cap = CaptureMCP()
        m.register(cap)
        return cap.tools

    def _seed_wiki_files(self, tmp_data_root):
        profile_dir = tmp_data_root / "profile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        for fname in ["profile.md", "goals.md", "training_history.md", "plans_index.md", "log.md"]:
            if not (profile_dir / fname).exists():
                (profile_dir / fname).write_text(f"# {fname}\n", encoding="utf-8")

    def test_get_athlete_wiki_seeded(self, mem_db, monkeypatch, tmp_data_root):
        self._seed_wiki_files(tmp_data_root)
        tools = self._get_tools(mem_db, monkeypatch)
        result = tools["get_athlete_wiki"]()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_propose_wiki_update_invalid_section(self, mem_db, monkeypatch, tmp_data_root):
        self._seed_wiki_files(tmp_data_root)
        tools = self._get_tools(mem_db, monkeypatch)
        result = tools["propose_wiki_update"](
            section="nonexistent.md", proposed_content="x", reason="test"
        )
        assert "Invalid" in result

    def test_propose_wiki_update_valid(self, mem_db, monkeypatch, tmp_data_root):
        self._seed_wiki_files(tmp_data_root)
        tools = self._get_tools(mem_db, monkeypatch)
        result = tools["propose_wiki_update"](
            section="goals.md", proposed_content="# Goals\nNew goal here\n", reason="test update"
        )
        assert "goals.md" in result

    def test_apply_wiki_update_invalid_section(self, mem_db, monkeypatch, tmp_data_root):
        self._seed_wiki_files(tmp_data_root)
        tools = self._get_tools(mem_db, monkeypatch)
        result = tools["apply_wiki_update"](section="bogus.md", content="x")
        assert "Invalid" in result

    def test_apply_wiki_update_valid(self, mem_db, monkeypatch, tmp_data_root):
        self._seed_wiki_files(tmp_data_root)
        tools = self._get_tools(mem_db, monkeypatch)
        result = tools["apply_wiki_update"](section="goals.md", content="# Goals\nUpdated\n")
        assert "goals.md" in result

    def test_read_general_wiki_no_topic(self, mem_db, monkeypatch, tmp_data_root):
        tools = self._get_tools(mem_db, monkeypatch)
        result = tools["read_general_wiki"]()
        assert isinstance(result, str)

    def test_read_general_wiki_with_topic(self, mem_db, monkeypatch, tmp_data_root):
        tools = self._get_tools(mem_db, monkeypatch)
        # Create a wiki file
        import coachctl.paths as p

        wiki_dir = p.general_wiki_dir()
        wiki_dir.mkdir(parents=True, exist_ok=True)
        (wiki_dir / "nutrition.md").write_text("# Nutrition\nCarbs are good.\n", encoding="utf-8")
        result = tools["read_general_wiki"](topic="nutrition")
        assert "Carbs" in result

    def test_read_general_wiki_topic_not_found(self, mem_db, monkeypatch, tmp_data_root):
        tools = self._get_tools(mem_db, monkeypatch)
        result = tools["read_general_wiki"](topic="xyz_nonexistent")
        assert "No file found" in result

    def test_propose_general_wiki_update(self, mem_db, monkeypatch, tmp_data_root):
        tools = self._get_tools(mem_db, monkeypatch)
        import coachctl.paths as p

        wiki_dir = p.general_wiki_dir()
        wiki_dir.mkdir(parents=True, exist_ok=True)
        (wiki_dir / "log.md").write_text("", encoding="utf-8")
        result = tools["propose_general_wiki_update"](
            topic="nutrition", proposed_content="# Nutrition\nNew content\n", reason="test"
        )
        assert "nutrition" in result.lower()

    def test_apply_general_wiki_update(self, mem_db, monkeypatch, tmp_data_root):
        tools = self._get_tools(mem_db, monkeypatch)
        import coachctl.paths as p

        wiki_dir = p.general_wiki_dir()
        wiki_dir.mkdir(parents=True, exist_ok=True)
        (wiki_dir / "log.md").write_text("", encoding="utf-8")
        result = tools["apply_general_wiki_update"](
            topic="nutrition", content="# Nutrition\nApplied content\n"
        )
        assert "nutrition" in result.lower()

    def test_read_general_wiki_wiki_dir_missing(self, mem_db, monkeypatch, tmp_data_root):
        """Returns a helpful message when the wiki dir doesn't exist yet."""
        import coachctl.paths as p
        import shutil

        wiki_dir = p.general_wiki_dir()
        shutil.rmtree(wiki_dir, ignore_errors=True)
        tools = self._get_tools(mem_db, monkeypatch)
        result = tools["read_general_wiki"]()
        assert "not found" in result.lower()

    def test_read_general_wiki_no_topic_empty_dir(self, mem_db, monkeypatch, tmp_data_root):
        """Returns a helpful message when wiki dir exists but has no .md files."""
        tools = self._get_tools(mem_db, monkeypatch)
        result = tools["read_general_wiki"]()
        assert (
            "No knowledge files" in result or "Available" in result or "not found" in result.lower()
        )

    def test_read_general_wiki_no_topic_lists_files(self, mem_db, monkeypatch, tmp_data_root):
        """Lists available files when called with no topic."""
        import coachctl.paths as p

        wiki_dir = p.general_wiki_dir()
        (wiki_dir / "nutrition.md").write_text("# Nutrition\n", encoding="utf-8")
        (wiki_dir / "running.md").write_text("# Running\n", encoding="utf-8")
        tools = self._get_tools(mem_db, monkeypatch)
        result = tools["read_general_wiki"]()
        assert "nutrition" in result.lower()
        assert "running" in result.lower()

    def test_read_general_wiki_multiple_matches(self, mem_db, monkeypatch, tmp_data_root):
        """Returns all matches when multiple files match a topic prefix."""
        import coachctl.paths as p

        wiki_dir = p.general_wiki_dir()
        (wiki_dir / "running.md").write_text("# Running\nAerobic base.\n", encoding="utf-8")
        (wiki_dir / "running_intervals.md").write_text(
            "# Intervals\nVO2max work.\n", encoding="utf-8"
        )
        tools = self._get_tools(mem_db, monkeypatch)
        result = tools["read_general_wiki"](topic="running")
        # Either one or both files returned — should contain content from at least one
        assert "Running" in result or "Aerobic" in result

    def test_get_athlete_wiki_triggers_seed(self, mem_db, monkeypatch, tmp_data_root):
        """get_athlete_wiki seeds wiki files when they don't exist yet."""
        tools = self._get_tools(mem_db, monkeypatch)
        result = tools["get_athlete_wiki"]()
        # Should not crash; returns either seed message or empty wiki message
        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# plan_tools
# ---------------------------------------------------------------------------


class TestPlanTools:
    def _get_tools(self, mem_db, monkeypatch, tmp_data_root):
        import coachctl.tools.plan_tools as m
        import coachctl.events as events_mod

        monkeypatch.setattr(events_mod, "get_conn", mem_db)
        cap = CaptureMCP()
        m.register(cap)
        return cap.tools

    def test_save_plan_empty_markdown(self, mem_db, monkeypatch, tmp_data_root):
        tools = self._get_tools(mem_db, monkeypatch, tmp_data_root)
        profile_dir = tmp_data_root / "profile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        for f in ["plans_index.md", "log.md"]:
            (profile_dir / f).write_text("", encoding="utf-8")
        result = tools["save_plan"](plan_markdown="")
        assert "Error" in result

    def test_save_plan_basic(self, mem_db, monkeypatch, tmp_data_root):
        tools = self._get_tools(mem_db, monkeypatch, tmp_data_root)
        profile_dir = tmp_data_root / "profile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        for f in ["plans_index.md", "log.md"]:
            (profile_dir / f).write_text("", encoding="utf-8")
        result = tools["save_plan"](
            plan_markdown="# My Plan\n\nWeek 1: Easy week\n",
            event_name="Test Race",
        )
        assert "Plan saved" in result

    def test_get_previous_plans_no_dir(self, mem_db, monkeypatch, tmp_data_root):
        tools = self._get_tools(mem_db, monkeypatch, tmp_data_root)
        result = tools["get_previous_plans"]()
        assert "No plans" in result

    def test_get_previous_plans_with_plans(self, mem_db, monkeypatch, tmp_data_root):
        tools = self._get_tools(mem_db, monkeypatch, tmp_data_root)
        profile_dir = tmp_data_root / "profile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        for f in ["plans_index.md", "log.md"]:
            (profile_dir / f).write_text("", encoding="utf-8")
        tools["save_plan"](plan_markdown="# Plan A\nWeek 1 details\n", event_name="Race A")
        result = json.loads(tools["get_previous_plans"]())
        assert len(result) >= 1


# ---------------------------------------------------------------------------
# env_tools (smoke + basic functional)
# ---------------------------------------------------------------------------


class TestEnvTools:
    def test_check_environment(self, tmp_data_root, monkeypatch):
        import coachctl.tools.env_tools as m

        cap = CaptureMCP()
        m.register(cap)
        result = json.loads(cap.tools["check_environment"]())
        assert "ok" in result


# ---------------------------------------------------------------------------
# site_tools (smoke)
# ---------------------------------------------------------------------------


class TestSiteTools:
    def test_register_and_bake(self, mem_db, monkeypatch, tmp_data_root):
        import coachctl.tools.site_tools as m
        import coachctl.site as site_mod

        monkeypatch.setattr(site_mod, "get_conn", mem_db, raising=False)

        def _mock_bake():
            return {"baked": True}

        cap = CaptureMCP()
        m.register(cap)
        assert "bake" in cap.tools


# ---------------------------------------------------------------------------
# sync_tools (error paths via mocked Strava)
# ---------------------------------------------------------------------------


class TestSyncTools:
    def _get_tools(self, mem_db, monkeypatch):
        import coachctl.tools.sync_tools as m

        monkeypatch.setattr(m, "get_conn", mem_db)
        cap = CaptureMCP()
        m.register(cap)
        return cap.tools

    def test_sync_activities_failure(self, mem_db, monkeypatch):
        from unittest.mock import patch

        tools = self._get_tools(mem_db, monkeypatch)
        with patch("coachctl.sync.sync", side_effect=Exception("Strava down")):
            result = tools["sync_activities"](full=False)
        assert "Sync failed" in result

    def test_list_routes_failure(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        with patch(
            "coachctl.tools.sync_tools.get_strava_access_token", side_effect=Exception("no creds")
        ):
            result = tools["list_routes"]()
        assert "Failed" in result

    def test_list_routes_empty(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        with (
            patch("coachctl.tools.sync_tools.get_strava_access_token", return_value="tok"),
            patch("coachctl.tools.sync_tools.fetch_athlete_routes", return_value=[]),
        ):
            result = tools["list_routes"]()
        assert "No saved routes" in result

    def test_list_routes_with_data(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        routes = [
            {
                "id": 1,
                "name": "Sunday Loop",
                "distance": 50000,
                "elevation_gain": 800,
                "type": 1,
                "sub_type": 1,
                "starred": True,
                "estimated_moving_time": 5400,
            }
        ]
        with (
            patch("coachctl.tools.sync_tools.get_strava_access_token", return_value="tok"),
            patch("coachctl.tools.sync_tools.fetch_athlete_routes", return_value=routes),
        ):
            result = json.loads(tools["list_routes"]())
        assert result[0]["name"] == "Sunday Loop"

    def test_get_route_detail_failure(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        with patch(
            "coachctl.tools.sync_tools.get_strava_access_token", side_effect=Exception("no creds")
        ):
            result = tools["get_route_detail"](route_id=123)
        assert "Failed" in result

    def test_get_route_detail_no_streams(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        route = {
            "name": "Alps Loop",
            "distance": 80000,
            "elevation_gain": 3000,
            "type": 1,
            "sub_type": 1,
            "estimated_moving_time": 14400,
        }
        with (
            patch("coachctl.tools.sync_tools.get_strava_access_token", return_value="tok"),
            patch("coachctl.tools.sync_tools.fetch_route", return_value=route),
            patch("coachctl.tools.sync_tools.fetch_route_streams", return_value=None),
        ):
            result = json.loads(tools["get_route_detail"](route_id=123))
        assert result["name"] == "Alps Loop"
        assert "note" in result

    def test_get_route_detail_with_streams(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        route = {
            "name": "Hill Route",
            "distance": 10000,
            "elevation_gain": 500,
            "type": 2,
            "sub_type": 4,
            "estimated_moving_time": 3600,
        }
        alt = [100.0, 110.0, 150.0, 200.0, 180.0, 160.0, 120.0, 100.0]
        dist = [0.0, 1000.0, 2000.0, 3000.0, 4000.0, 5000.0, 6000.0, 7000.0]
        streams = {"altitude": {"data": alt}, "distance": {"data": dist}}
        with (
            patch("coachctl.tools.sync_tools.get_strava_access_token", return_value="tok"),
            patch("coachctl.tools.sync_tools.fetch_route", return_value=route),
            patch("coachctl.tools.sync_tools.fetch_route_streams", return_value=streams),
        ):
            result = json.loads(tools["get_route_detail"](route_id=456))
        assert "elevation_profile" in result
        assert "km_splits" in result

    def test_get_route_detail_no_altitude(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        route = {
            "name": "Flat",
            "distance": 5000,
            "elevation_gain": 0,
            "type": 1,
            "sub_type": 1,
            "estimated_moving_time": 600,
        }
        with (
            patch("coachctl.tools.sync_tools.get_strava_access_token", return_value="tok"),
            patch("coachctl.tools.sync_tools.fetch_route", return_value=route),
            patch(
                "coachctl.tools.sync_tools.fetch_route_streams",
                return_value={"altitude": {"data": []}, "distance": {"data": []}},
            ),
        ):
            result = json.loads(tools["get_route_detail"](route_id=789))
        assert "note" in result


# ---------------------------------------------------------------------------
# activity_tools — ride streams with power + run with velocity/cadence
# ---------------------------------------------------------------------------


class TestActivityStreams:
    def _get_tools(self, mem_db, monkeypatch):
        import coachctl.tools.activity_tools as m

        monkeypatch.setattr(m, "get_conn", mem_db)
        cap = CaptureMCP()
        m.register(cap)
        return cap.tools

    def _insert_streams(self, mem_db, activity_id, sport, streams_data):
        with mem_db() as conn:
            conn.execute(
                "INSERT INTO activities (id, name, sport_type, start_date, moving_time, distance) "
                "VALUES (?,?,?,?,?,?)",
                (activity_id, "Test", sport, "2026-05-01T07:00:00Z", 3600, 40000),
            )
            conn.execute(
                "INSERT INTO activity_streams (activity_id, streams_json) VALUES (?,?)",
                (activity_id, json.dumps(streams_data)),
            )

    def test_ride_with_power(self, mem_db, monkeypatch):
        n = 120
        self._insert_streams(
            mem_db,
            1,
            "Ride",
            {
                "time": {"data": list(range(n))},
                "watts": {"data": [250 + (i % 30) for i in range(n)]},
                "heartrate": {"data": [150 + (i % 10) for i in range(n)]},
                "velocity_smooth": {"data": [10.0 + (i % 5) * 0.1 for i in range(n)]},
                "altitude": {"data": [100.0 + i * 0.5 for i in range(n)]},
                "cadence": {"data": [85 + (i % 5) for i in range(n)]},
            },
        )
        tools = self._get_tools(mem_db, monkeypatch)
        with patch(
            "coachctl.tools.activity_tools.load_athlete",
            return_value={"threshold_hr": 170, "resting_hr": 50, "ftp": 280},
        ):
            result = json.loads(tools["get_activity_streams"](activity_id=1))
        assert "power_stats" in result
        assert "power_zone_distribution" in result
        assert "peak_power" in result
        assert "cardiac_decoupling_pct" in result

    def test_run_with_velocity(self, mem_db, monkeypatch):
        n = 200
        self._insert_streams(
            mem_db,
            2,
            "Run",
            {
                "time": {"data": list(range(n))},
                "heartrate": {"data": [145 + (i % 15) for i in range(n)]},
                "velocity_smooth": {"data": [3.0 + (i % 5) * 0.05 for i in range(n)]},
                "altitude": {"data": [200.0 + (i % 20) for i in range(n)]},
                "cadence": {"data": [88 + (i % 3) for i in range(n)]},
            },
        )
        tools = self._get_tools(mem_db, monkeypatch)
        with patch(
            "coachctl.tools.activity_tools.load_athlete",
            return_value={"threshold_hr": 170, "resting_hr": 50, "ftp": 280},
        ):
            result = json.loads(tools["get_activity_streams"](activity_id=2))
        assert "pace_stats" in result
        assert "cadence_stats" in result
        assert "cardiac_decoupling_pct" in result
        assert "km_splits" in result

    def test_streams_no_time(self, mem_db, monkeypatch):
        self._insert_streams(
            mem_db,
            3,
            "Run",
            {
                "heartrate": {"data": [140]},
            },
        )
        tools = self._get_tools(mem_db, monkeypatch)
        with patch(
            "coachctl.tools.activity_tools.load_athlete",
            return_value={"threshold_hr": 170, "resting_hr": 50, "ftp": 280},
        ):
            result = tools["get_activity_streams"](activity_id=3)
        assert "no time series" in result

    def test_get_activity_laps_failure(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        with patch(
            "coachctl.tools.activity_tools.get_strava_access_token",
            side_effect=Exception("no creds"),
        ):
            result = tools["get_activity_laps"](activity_id=1)
        assert "Failed" in result

    def test_get_activity_laps_no_data(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        with (
            patch("coachctl.tools.activity_tools.get_strava_access_token", return_value="tok"),
            patch("coachctl.tools.activity_tools.fetch_activity_laps", return_value=[]),
        ):
            result = tools["get_activity_laps"](activity_id=1)
        assert "No lap data" in result

    def test_get_activity_laps_with_data(self, mem_db, monkeypatch):
        tools = self._get_tools(mem_db, monkeypatch)
        laps = [
            {
                "lap_index": 1,
                "name": "Lap 1",
                "distance": 1000,
                "moving_time": 240,
                "elapsed_time": 245,
                "average_speed": 4.17,
                "max_speed": 4.5,
                "average_heartrate": 155,
                "max_heartrate": 165,
                "average_watts": None,
                "average_cadence": 88,
                "total_elevation_gain": 10,
            }
        ]
        with (
            patch("coachctl.tools.activity_tools.get_strava_access_token", return_value="tok"),
            patch("coachctl.tools.activity_tools.fetch_activity_laps", return_value=laps),
        ):
            result = json.loads(tools["get_activity_laps"](activity_id=1))
        assert result["activity_id"] == 1
        assert len(result["laps"]) == 1
        assert "avg_pace" in result["laps"][0]


# ---------------------------------------------------------------------------
# env_tools — extended paths (sibling/legacy/.env parsing)
# ---------------------------------------------------------------------------


class TestEnvToolsExtended:
    def _get_tools(self):
        import coachctl.tools.env_tools as m

        cap = CaptureMCP()
        m.register(cap)
        return cap.tools

    def test_check_env_with_env_file_partial_vars(self, tmp_data_root, monkeypatch):
        """Cover .env file exists but some Strava vars missing."""
        tools = self._get_tools()
        env_file = tmp_data_root / ".env"
        env_file.write_text(
            "STRAVA_CLIENT_ID=\nSTRAVA_CLIENT_SECRET=your_secret\n", encoding="utf-8"
        )
        # Create athlete.yaml to avoid that error
        (tmp_data_root / "config").mkdir(exist_ok=True)
        (tmp_data_root / "config" / "athlete.yaml").write_text("ftp: 250\n", encoding="utf-8")
        result = json.loads(tools["check_environment"]())
        # Should have warnings about missing/unset vars
        assert isinstance(result["warnings"], list)

    def test_check_env_missing_data_root(self, monkeypatch):
        """Cover RuntimeError path when data_root cannot be resolved."""
        import coachctl.paths as p
        import coachctl.tools.env_tools as env_mod

        tools = self._get_tools()
        monkeypatch.setattr(
            p, "data_root", lambda: (_ for _ in ()).throw(RuntimeError("no data root"))
        )
        result = json.loads(tools["check_environment"]())
        assert result["ok"] is False
        assert any("unresolved" in e for e in result["errors"])
