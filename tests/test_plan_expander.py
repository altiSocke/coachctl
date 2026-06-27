from __future__ import annotations

from coachctl.plan_expander import PLAN_EXPANDER_VERSION, expand_template
from coachctl.plan_templates import (
    HALF_MARATHON_BUILD,
    TEMPLATES,
    DaySlot,
    PlanTemplate,
    WeekTemplate,
    get_template,
)

START = "2026-07-13"  # a Monday


def test_registry_exposes_half_marathon_build() -> None:
    assert get_template("half_marathon_build") is HALF_MARATHON_BUILD
    assert get_template("does_not_exist") is None
    assert "half_marathon_build" in TEMPLATES


def test_week_template_requires_seven_days() -> None:
    slot = DaySlot(archetype="rest_day", params={"title": "Rest"})
    try:
        WeekTemplate(target_tss=100, days=(slot, slot, slot))
    except ValueError as exc:
        assert "7" in str(exc)
    else:  # pragma: no cover - failure path
        raise AssertionError("expected ValueError for non-7-day week")


def test_plan_template_rejects_empty_weeks() -> None:
    try:
        PlanTemplate(name="empty", weeks=())
    except ValueError:
        pass
    else:  # pragma: no cover - failure path
        raise AssertionError("expected ValueError for empty weeks")


# ── Determinism (seed=None) ──────────────────────────────────────────────────


def test_expand_seed_none_is_deterministic() -> None:
    a = expand_template(HALF_MARATHON_BUILD, START, seed=None)
    b = expand_template(HALF_MARATHON_BUILD, START, seed=None)
    assert a == b


def test_expand_seed_none_uses_base_variant_and_no_jitter() -> None:
    workouts = expand_template(HALF_MARATHON_BUILD, START, seed=None)

    # 4 weeks x 7 days
    assert len(workouts) == 28

    first_week = workouts[:7]
    assert [w.archetype for w in first_week] == [
        "easy_run",
        "z2_ride",
        "cruise_intervals",  # base variant, not a rotation
        "easy_run",
        "rest",
        "progressive_long_run",
        "z2_ride",
    ]
    # base durations, no jitter applied
    assert first_week[0].duration_min == 55
    assert first_week[3].duration_min == 50
    assert first_week[5].duration_min == 105


def test_expand_lays_out_contiguous_dates_from_start() -> None:
    workouts = expand_template(HALF_MARATHON_BUILD, START, seed=None)
    dates = [w.date for w in workouts]
    assert dates[0] == START
    assert dates[6] == "2026-07-19"
    assert dates[7] == "2026-07-20"  # week 2 starts the next day
    # strictly increasing, one day apart
    from datetime import date

    parsed = [date.fromisoformat(d) for d in dates]
    deltas = {(parsed[i + 1] - parsed[i]).days for i in range(len(parsed) - 1)}
    assert deltas == {1}


# ── Reproducibility (seed=N) ─────────────────────────────────────────────────


def test_expand_seeded_is_reproducible() -> None:
    a = expand_template(HALF_MARATHON_BUILD, START, seed=7)
    b = expand_template(HALF_MARATHON_BUILD, START, seed=7)
    assert a == b


def test_expand_seeded_differs_from_deterministic() -> None:
    seeded = expand_template(HALF_MARATHON_BUILD, START, seed=7)
    deterministic = expand_template(HALF_MARATHON_BUILD, START, seed=None)
    assert seeded != deterministic


def test_expand_different_seeds_can_differ() -> None:
    a = expand_template(HALF_MARATHON_BUILD, START, seed=1)
    b = expand_template(HALF_MARATHON_BUILD, START, seed=2)
    # Not guaranteed for every pair, but these two should diverge somewhere.
    assert a != b


# ── Variation bounds ─────────────────────────────────────────────────────────


def test_seeded_quality_day_rotates_within_pool() -> None:
    # Scan several seeds; the Wednesday quality slot must only ever be one of
    # the three declared variants, and at least one seed must pick a non-base.
    allowed = {"cruise_intervals", "ladder_intervals", "mona_fartlek"}
    seen: set[str] = set()
    for seed in range(25):
        workouts = expand_template(HALF_MARATHON_BUILD, START, seed=seed)
        weds = [workouts[i].archetype for i in range(2, len(workouts), 7)]
        assert set(weds) <= allowed
        seen.update(weds)
    assert "cruise_intervals" in seen
    assert seen - {"cruise_intervals"}  # at least one rotation happened


def test_seeded_easy_and_long_durations_stay_within_jitter() -> None:
    for seed in range(25):
        workouts = expand_template(HALF_MARATHON_BUILD, START, seed=seed)
        for w in workouts:
            if w.archetype == "easy_run":
                # Mon base 55, Thu base 50 -> overall window 45..60
                assert 45 <= (w.duration_min or 0) <= 60
            if w.archetype == "progressive_long_run":
                assert 100 <= (w.duration_min or 0) <= 110


def test_non_jitter_slots_are_exact() -> None:
    # Rides and rest have no jitter, regardless of seed.
    for seed in (None, 1, 2, 99):
        workouts = expand_template(HALF_MARATHON_BUILD, START, seed=seed)
        rides = [w.duration_min for w in workouts if w.archetype == "z2_ride"]
        # Tue 90 and Sun 70, repeated each week.
        assert set(rides) == {90, 70}
        rests = [w.duration_min for w in workouts if w.archetype == "rest"]
        assert set(rests) == {0}


# ── Generator stamp ──────────────────────────────────────────────────────────


def test_expander_stamps_generator_context() -> None:
    workouts = expand_template(HALF_MARATHON_BUILD, START, seed=7)
    gen = workouts[0].generator
    assert gen["generator_version"] == PLAN_EXPANDER_VERSION
    assert gen["template"] == "half_marathon_build"
    assert gen["week_number"] == 0
    assert gen["target_tss"] == 400
    assert gen["seed"] == 7
    assert gen["variant"] == workouts[0].archetype
    # week_number increments across weeks
    assert workouts[7].generator["week_number"] == 1


def test_target_tss_available_per_week_from_template() -> None:
    # The per-week target is hardcoded in the template and surfaced on stamps.
    for week_idx, week in enumerate(HALF_MARATHON_BUILD.weeks):
        assert week.target_tss == 400
    total_target = sum(w.target_tss for w in HALF_MARATHON_BUILD.weeks)
    assert total_target == 1600
