"""
Tests for coachctl.plan_parser — Markdown plan → dataclasses.
"""

from __future__ import annotations

import textwrap

import pytest

from coachctl.plan_parser import (
    Plan,
    Session,
    Week,
    _parse_date,
    parse_plan_file,
    parse_session_duration_intensity,
)


# ── _parse_date ───────────────────────────────────────────────────────────────


def test_parse_date_standard():
    assert _parse_date("Mon Apr 20", year="2026") == "2026-04-20"


def test_parse_date_single_digit_day():
    assert _parse_date("Tue Jun 3", year="2026") == "2026-06-03"


def test_parse_date_no_match():
    assert _parse_date("Rest Day", year="2026") is None


def test_parse_date_slash_format():
    """Sat/Sun Sep 6 — first date extracted."""
    result = _parse_date("Sat/Sun Sep 6", year="2026")
    assert result == "2026-09-06"


# ── parse_plan_file ───────────────────────────────────────────────────────────

MINIMAL_PLAN = textwrap.dedent("""\
    # Half Marathon Plan

    **Athlete:** Test Athlete
    **Period:** Apr 2026 - Sep 2026
    **A-Event:** Half Marathon Sep 6

    ---

    ### Week 1 (Apr 20-26) — Base Entry | Target TSS: ~200

    | Day | Session | Details |
    |-----|---------|---------|
    | Mon Apr 20 | Rest | - |
    | Tue Apr 21 | Easy run | 45min Z2, RPE 4 |
    | Wed Apr 22 | Core | 30min strength |
    | Thu Apr 23 | Tempo run | 50min with 20min tempo |
    | Fri Apr 24 | Rest | - |
    | Sat Apr 25 | Long run | 90min easy |
    | Sun Apr 26 | Recovery | 30min walk |

    ### Week 2 (Apr 27-May 3) — Base Build | Target TSS: ~240

    | Day | Session | Details |
    |-----|---------|---------|
    | Mon Apr 27 | Rest | - |
    | Tue Apr 28 | Intervals | 8x400m |
    | Wed Apr 29 | Easy run | 40min Z2 |
    | Thu Apr 30 | Threshold | 55min with 25min threshold |
    | Fri May 1 | Rest | - |
    | Sat May 2 | Long run | 100min easy |
    | Sun May 3 | Recovery | 30min walk |
""")


@pytest.fixture
def plan_file(tmp_path):
    p = tmp_path / "plan.md"
    p.write_text(MINIMAL_PLAN, encoding="utf-8")
    return p


def test_parse_plan_title(plan_file):
    plan = parse_plan_file(plan_file)
    assert "Half Marathon" in plan.title


def test_parse_plan_week_count(plan_file):
    plan = parse_plan_file(plan_file)
    assert len(plan.weeks) == 2


def test_parse_plan_week_numbers(plan_file):
    plan = parse_plan_file(plan_file)
    assert plan.weeks[0].number == 1
    assert plan.weeks[1].number == 2


def test_parse_plan_target_tss(plan_file):
    plan = parse_plan_file(plan_file)
    assert plan.weeks[0].target_tss == 200
    assert plan.weeks[1].target_tss == 240


def test_parse_plan_sessions_per_week(plan_file):
    plan = parse_plan_file(plan_file)
    # 7 rows per week in the table
    assert len(plan.weeks[0].sessions) == 7
    assert len(plan.weeks[1].sessions) == 7


def test_parse_plan_session_dates(plan_file):
    plan = parse_plan_file(plan_file)
    first_session = plan.weeks[0].sessions[0]
    assert first_session.date == "2026-04-20"


def test_parse_plan_session_names(plan_file):
    plan = parse_plan_file(plan_file)
    names = [s.name for s in plan.weeks[0].sessions]
    assert "Easy run" in names
    assert "Tempo run" in names


def test_parse_plan_period_year(plan_file):
    plan = parse_plan_file(plan_file)
    assert "2026" in plan.period


def test_parse_plan_event(plan_file):
    plan = parse_plan_file(plan_file)
    assert "Half Marathon" in plan.event


def test_parse_plan_missing_file():
    from pathlib import Path

    with pytest.raises(FileNotFoundError):
        parse_plan_file(Path("/nonexistent/plan.md"))


def test_parse_plan_empty_file(tmp_path):
    p = tmp_path / "empty.md"
    p.write_text("")
    plan = parse_plan_file(p)
    assert isinstance(plan, Plan)
    assert plan.weeks == []


# ── parse_session_duration_intensity ─────────────────────────────────────────


def test_duration_intensity_easy():
    dur, intensity = parse_session_duration_intensity("60 min easy Z2 run")
    assert dur == 60.0
    assert intensity == "easy"


def test_duration_intensity_threshold():
    dur, intensity = parse_session_duration_intensity("45 min threshold intervals + cool-down")
    assert dur == 45.0
    assert intensity == "threshold"


def test_duration_intensity_recovery():
    dur, intensity = parse_session_duration_intensity("30 min recovery jog")
    assert dur == 30.0
    assert intensity == "recovery"


def test_duration_intensity_tempo():
    dur, intensity = parse_session_duration_intensity("50 min with 20 min tempo block")
    assert dur == 50.0
    assert intensity == "tempo"


def test_duration_intensity_vo2max():
    dur, intensity = parse_session_duration_intensity("40 min vo2max intervals")
    assert dur == 40.0
    assert intensity == "vo2max"


def test_duration_intensity_z2_maps_to_easy():
    dur, intensity = parse_session_duration_intensity("75 min Z2 long run")
    assert dur == 75.0
    assert intensity == "easy"


def test_duration_intensity_z1_maps_to_recovery():
    dur, intensity = parse_session_duration_intensity("30 min Z1 walk")
    assert dur == 30.0
    assert intensity == "recovery"


def test_duration_intensity_no_duration():
    dur, intensity = parse_session_duration_intensity("Rest")
    assert dur is None
    assert intensity is None


def test_duration_intensity_duration_no_intensity():
    dur, intensity = parse_session_duration_intensity("60 min cross-training")
    assert dur == 60.0
    assert intensity is None  # no keyword matches


def test_duration_intensity_fractional():
    dur, intensity = parse_session_duration_intensity("90 minutes easy aerobic")
    assert dur == 90.0
    assert intensity == "easy"
