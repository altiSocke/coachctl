"""
Tests for the plan compliance engine.

Covers:
- compute_plan_compliance() pure function
- get_plan_compliance() MCP tool (via mem_db fixture)
- Edge cases: no plan, no activities, partial completion, multi-week
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────


def _insert_plan(conn, plan_id=1, slug="test-plan", start_date="2026-01-05", end_date="2026-01-25"):
    conn.execute(
        """
        INSERT OR REPLACE INTO plans (id, slug, title, start_date, end_date, active)
        VALUES (?, ?, ?, ?, ?, 1)
        """,
        (plan_id, slug, "Test Plan", start_date, end_date),
    )


def _insert_training_event(conn, slug, event_date, estimated_tss, plan_id=1, status="planned"):
    conn.execute(
        """
        INSERT OR REPLACE INTO events
            (slug, kind, date, name, estimated_tss, status, plan_id)
        VALUES (?, 'training', ?, ?, ?, ?, ?)
        """,
        (slug, event_date, "Session " + slug, estimated_tss, status, plan_id),
    )


def _insert_activity(conn, activity_id, start_date, tss, sport_type="Run"):
    conn.execute(
        """
        INSERT OR REPLACE INTO activities
            (id, name, sport_type, start_date, elapsed_time, moving_time,
             distance, tss)
        VALUES (?, ?, ?, ?, 3600, 3600, 10000, ?)
        """,
        (activity_id, "Run " + start_date, sport_type, start_date + "T08:00:00Z", tss),
    )


# ── Unit tests: compute_plan_compliance() ─────────────────────────────────────


class TestComputePlanCompliance:
    def test_perfect_compliance(self):
        from coachctl.plan_compliance import compute_plan_compliance

        planned = [
            {"date": "2026-01-05", "estimated_tss": 80.0},
            {"date": "2026-01-07", "estimated_tss": 100.0},
        ]
        actual = {"2026-01-05": 80.0, "2026-01-07": 100.0}
        result = compute_plan_compliance(planned, actual)

        assert result["sessions_planned"] == 2
        assert result["sessions_completed"] == 2
        assert result["planned_tss"] == 180.0
        assert result["actual_tss"] == 180.0
        assert result["compliance_pct"] == 100.0

    def test_zero_compliance_no_activities(self):
        from coachctl.plan_compliance import compute_plan_compliance

        planned = [{"date": "2026-01-05", "estimated_tss": 80.0}]
        result = compute_plan_compliance(planned, {})

        assert result["sessions_completed"] == 0
        assert result["actual_tss"] == 0.0
        assert result["compliance_pct"] == 0.0

    def test_partial_compliance(self):
        from coachctl.plan_compliance import compute_plan_compliance

        planned = [
            {"date": "2026-01-05", "estimated_tss": 80.0},
            {"date": "2026-01-07", "estimated_tss": 100.0},
            {"date": "2026-01-09", "estimated_tss": 60.0},
        ]
        # Only completed first two, and first one was under-performed
        actual = {"2026-01-05": 40.0, "2026-01-07": 100.0}
        result = compute_plan_compliance(planned, actual)

        assert result["sessions_planned"] == 3
        assert result["sessions_completed"] == 2
        assert result["planned_tss"] == 240.0
        assert result["actual_tss"] == 140.0
        assert round(result["compliance_pct"], 1) == round(140.0 / 240.0 * 100, 1)

    def test_empty_planned(self):
        from coachctl.plan_compliance import compute_plan_compliance

        result = compute_plan_compliance([], {})

        assert result["sessions_planned"] == 0
        assert result["planned_tss"] == 0.0
        assert result["compliance_pct"] == 0.0

    def test_over_performance(self):
        """Athlete did more TSS than planned — compliance can exceed 100%."""
        from coachctl.plan_compliance import compute_plan_compliance

        planned = [{"date": "2026-01-05", "estimated_tss": 80.0}]
        actual = {"2026-01-05": 120.0}
        result = compute_plan_compliance(planned, actual)

        assert result["actual_tss"] == 120.0
        assert result["compliance_pct"] > 100.0

    def test_session_counted_as_completed_even_with_different_tss(self):
        """A session counts as completed if an activity exists on that date, regardless of TSS delta."""
        from coachctl.plan_compliance import compute_plan_compliance

        planned = [{"date": "2026-01-05", "estimated_tss": 100.0}]
        actual = {"2026-01-05": 50.0}  # only half the TSS
        result = compute_plan_compliance(planned, actual)

        assert result["sessions_completed"] == 1

    def test_null_estimated_tss_treated_as_zero(self):
        """Sessions with None estimated_tss are counted but contribute 0 planned TSS."""
        from coachctl.plan_compliance import compute_plan_compliance

        planned = [{"date": "2026-01-05", "estimated_tss": None}]
        actual = {"2026-01-05": 60.0}
        result = compute_plan_compliance(planned, actual)

        assert result["sessions_planned"] == 1
        assert result["planned_tss"] == 0.0
        assert result["actual_tss"] == 60.0


# ── Unit tests: compute_weekly_compliance() ───────────────────────────────────


class TestComputeWeeklyCompliance:
    def test_groups_by_iso_week(self):
        from coachctl.plan_compliance import compute_weekly_compliance

        # Week 2026-W02: Jan 5–11
        planned = [
            {"date": "2026-01-05", "estimated_tss": 80.0},
            {"date": "2026-01-07", "estimated_tss": 100.0},
            # Week 2026-W03: Jan 12–18
            {"date": "2026-01-12", "estimated_tss": 90.0},
        ]
        actual = {"2026-01-05": 80.0, "2026-01-07": 90.0, "2026-01-12": 85.0}
        weeks = compute_weekly_compliance(planned, actual)

        assert len(weeks) == 2
        week_labels = [w["week"] for w in weeks]
        assert "2026-W02" in week_labels
        assert "2026-W03" in week_labels

    def test_week_totals(self):
        from coachctl.plan_compliance import compute_weekly_compliance

        planned = [
            {"date": "2026-01-05", "estimated_tss": 80.0},
            {"date": "2026-01-07", "estimated_tss": 100.0},
        ]
        actual = {"2026-01-05": 80.0, "2026-01-07": 100.0}
        weeks = compute_weekly_compliance(planned, actual)

        assert len(weeks) == 1
        w = weeks[0]
        assert w["planned_tss"] == 180.0
        assert w["actual_tss"] == 180.0
        assert w["sessions_planned"] == 2
        assert w["sessions_completed"] == 2

    def test_returns_sorted_by_week(self):
        from coachctl.plan_compliance import compute_weekly_compliance

        planned = [
            {"date": "2026-01-19", "estimated_tss": 70.0},
            {"date": "2026-01-05", "estimated_tss": 80.0},
        ]
        weeks = compute_weekly_compliance(planned, {})
        assert weeks[0]["week"] < weeks[1]["week"]


# ── Integration tests: get_compliance_from_db() ───────────────────────────────


class TestGetComplianceFromDb:
    def test_basic_compliance(self, mem_db):
        from coachctl.plan_compliance import get_compliance_from_db

        with mem_db() as conn:
            _insert_plan(conn, start_date="2026-01-05", end_date="2026-01-11")
            _insert_training_event(conn, "ev-1", "2026-01-05", 80.0)
            _insert_training_event(conn, "ev-2", "2026-01-07", 100.0)
            _insert_activity(conn, 1, "2026-01-05", 80.0)
            _insert_activity(conn, 2, "2026-01-07", 95.0)

        with mem_db() as conn:
            result = get_compliance_from_db(conn, plan_id=1)

        assert result["plan_id"] == 1
        assert result["overall"]["sessions_planned"] == 2
        assert result["overall"]["sessions_completed"] == 2

    def test_returns_none_for_missing_plan(self, mem_db):
        from coachctl.plan_compliance import get_compliance_from_db

        with mem_db() as conn:
            result = get_compliance_from_db(conn, plan_id=999)

        assert result is None

    def test_no_activities_zero_completion(self, mem_db):
        from coachctl.plan_compliance import get_compliance_from_db

        with mem_db() as conn:
            _insert_plan(conn)
            _insert_training_event(conn, "ev-1", "2026-01-05", 80.0)
            _insert_training_event(conn, "ev-2", "2026-01-07", 100.0)

        with mem_db() as conn:
            result = get_compliance_from_db(conn, plan_id=1)

        assert result["overall"]["sessions_completed"] == 0
        assert result["overall"]["actual_tss"] == 0.0

    def test_weekly_breakdown_present(self, mem_db):
        from coachctl.plan_compliance import get_compliance_from_db

        with mem_db() as conn:
            _insert_plan(conn, start_date="2026-01-05", end_date="2026-01-18")
            _insert_training_event(conn, "ev-1", "2026-01-05", 80.0)
            _insert_training_event(conn, "ev-2", "2026-01-12", 90.0)

        with mem_db() as conn:
            result = get_compliance_from_db(conn, plan_id=1)

        assert "weekly" in result
        assert len(result["weekly"]) == 2

    def test_uses_active_plan_when_no_id_given(self, mem_db):
        from coachctl.plan_compliance import get_compliance_from_db

        with mem_db() as conn:
            _insert_plan(conn, plan_id=5, slug="active-plan")
            _insert_training_event(conn, "ev-1", "2026-01-05", 80.0, plan_id=5)

        with mem_db() as conn:
            result = get_compliance_from_db(conn)

        assert result is not None
        assert result["plan_id"] == 5

    def test_future_sessions_excluded_from_completion(self, mem_db):
        """Sessions after today should not be counted as missed — only sessions up to today matter."""
        from coachctl.plan_compliance import get_compliance_from_db

        far_future = (date.today() + timedelta(days=30)).isoformat()
        with mem_db() as conn:
            _insert_plan(conn, start_date="2026-01-05", end_date=far_future)
            _insert_training_event(conn, "ev-past", "2026-01-05", 80.0)
            _insert_training_event(conn, "ev-future", far_future, 100.0)
            _insert_activity(conn, 1, "2026-01-05", 80.0)

        with mem_db() as conn:
            result = get_compliance_from_db(conn, plan_id=1)

        # Both sessions counted in plan total
        assert result["overall"]["sessions_planned"] == 2
        # But compliance_pct denominator only uses past sessions
        assert result["overall"]["sessions_completed"] == 1


# ── MCP tool integration ───────────────────────────────────────────────────────


class TestGetPlanComplianceTool:
    def test_returns_json(self, mem_db, monkeypatch):
        import coachctl.db as db_module
        import coachctl.plan_compliance as pc_module

        # Patch get_conn used inside plan_compliance
        monkeypatch.setattr(pc_module, "get_conn", db_module.get_conn)

        with mem_db() as conn:
            _insert_plan(conn)
            _insert_training_event(conn, "ev-1", "2026-01-05", 80.0)

        from coachctl.plan_compliance import get_plan_compliance_tool

        output = get_plan_compliance_tool()
        data = json.loads(output)
        assert "overall" in data

    def test_no_plan_returns_message(self, mem_db, monkeypatch):
        import coachctl.db as db_module
        import coachctl.plan_compliance as pc_module

        monkeypatch.setattr(pc_module, "get_conn", db_module.get_conn)

        from coachctl.plan_compliance import get_plan_compliance_tool

        output = get_plan_compliance_tool()
        # Should return informative message not a crash
        assert "plan" in output.lower() or "{" in output
