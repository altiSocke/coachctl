from __future__ import annotations

from coachctl.workout_generators import generate_post_trail_race_week, generate_trail_race_week
from coachctl.workouts import render_workout_summary


def test_generate_trail_race_week_is_deterministic_for_steinbock() -> None:
    workouts = generate_trail_race_week(
        race_date="2026-07-04",
        race_name="Bernina Ultraks Steinbock",
        start_date="2026-06-27",
        simulation_title="90min trail run - Steinbock race simulation (05:30)",
        start_time="05:30",
    )

    assert [(w.date, w.archetype, w.title) for w in workouts] == [
        (
            "2026-06-27",
            "trail_race_simulation",
            "90min trail run - Steinbock race simulation (05:30)",
        ),
        ("2026-06-28", "rest", "Rest or 45min recovery spin"),
        ("2026-06-29", "easy_run_strides", "40min easy trail run + strides"),
        ("2026-06-30", "rest", "Rest"),
        (
            "2026-07-01",
            "hill_activation",
            "45min easy run + 3x2min uphill activation",
        ),
        ("2026-07-02", "shakeout", "30min shakeout or rest"),
        ("2026-07-03", "rest", "Rest / travel / pack"),
    ]
    assert generate_trail_race_week(
        race_date="2026-07-04",
        race_name="Bernina Ultraks Steinbock",
        start_date="2026-06-27",
        simulation_title="90min trail run - Steinbock race simulation (05:30)",
        start_time="05:30",
    ) == workouts


def test_generate_trail_race_week_sets_safe_taper_loads() -> None:
    workouts = generate_trail_race_week(
        race_date="2026-07-04",
        race_name="Bernina Ultraks Steinbock",
        start_date="2026-06-27",
        simulation_title="90min trail run - Steinbock race simulation (05:30)",
        start_time="05:30",
    )

    by_date = {w.date: w for w in workouts}

    assert by_date["2026-06-27"].estimated_tss == 85.0
    assert by_date["2026-06-28"].estimated_tss == 20.0
    assert by_date["2026-06-29"].estimated_tss == 35.0
    assert by_date["2026-06-30"].estimated_tss == 0.0
    assert by_date["2026-07-01"].estimated_tss == 50.0
    assert by_date["2026-07-02"].estimated_tss == 20.0
    assert by_date["2026-07-03"].estimated_tss == 0.0
    assert sum(w.estimated_tss or 0 for w in workouts) == 210.0
    assert all(w.date < "2026-07-04" for w in workouts)


def test_generate_trail_race_week_includes_generator_provenance() -> None:
    workouts = generate_trail_race_week(
        race_date="2026-07-04",
        race_name="Bernina Ultraks Steinbock",
        start_date="2026-06-27",
    )

    assert all(w.generator["name"] == "deterministic" for w in workouts)
    assert all(w.generator["generator_version"] == "trail_race_week.v1" for w in workouts)
    assert {w.generator["race_name"] for w in workouts} == {"Bernina Ultraks Steinbock"}


def test_generate_trail_race_week_summary_uses_archetypes() -> None:
    workouts = generate_trail_race_week(
        race_date="2026-07-04",
        race_name="Bernina Ultraks Steinbock",
        start_date="2026-06-27",
    )

    summaries = [render_workout_summary(w) for w in workouts]

    assert "Fuel 65-75g carbs/hr" in summaries[0]
    assert summaries[2].startswith("40min easy trail run + strides.")
    assert "3x2min interval" in summaries[4]
    assert summaries[-1] == "Rest / travel / pack. No training. Pack kit and protect sleep."


def test_generate_post_trail_race_week_is_adaptive_and_deterministic() -> None:
    workouts = generate_post_trail_race_week(
        race_date="2026-07-04",
        race_name="Bernina Ultraks Steinbock",
        start_date="2026-07-05",
    )

    assert [(w.date, w.archetype, w.title) for w in workouts] == [
        ("2026-07-05", "rest", "Rest or 30-45min recovery spin"),
        ("2026-07-06", "mechanics_check_run", "25-35min mechanics-check easy jog or rest"),
        ("2026-07-07", "recovery_spin", "45-60min Z1-Z2 ride or rest"),
        ("2026-07-08", "easy_aerobic_run", "35-45min easy run"),
        ("2026-07-09", "mobility_rest", "Rest or mobility only"),
        ("2026-07-10", "easy_aerobic_run", "45-55min easy run"),
        ("2026-07-11", "easy_aerobic_run", "60-75min easy aerobic run or Z2 ride"),
        ("2026-07-12", "recovery_spin", "60min optional Z2 ride"),
    ]
    assert generate_post_trail_race_week(
        race_date="2026-07-04",
        race_name="Bernina Ultraks Steinbock",
        start_date="2026-07-05",
    ) == workouts


def test_generate_post_trail_race_week_rules_are_conservative() -> None:
    workouts = generate_post_trail_race_week(
        race_date="2026-07-04",
        race_name="Bernina Ultraks Steinbock",
        start_date="2026-07-05",
    )

    assert all(w.intensity in {"rest", "recovery", "easy"} for w in workouts)
    assert all(w.sport != "strength" for w in workouts)
    assert not any("strength" in w.archetype for w in workouts)
    assert sum(w.estimated_tss or 0 for w in workouts) == 155.0

    runs = [w for w in workouts if w.sport in {"run", "trail_run"}]
    assert runs
    assert all("stop_if" in w.constraints for w in runs)
    assert all("hamstring_warning" in w.constraints["stop_if"] for w in runs)


def test_generate_post_trail_race_week_mechanics_gate_and_provenance() -> None:
    workouts = generate_post_trail_race_week(
        race_date="2026-07-04",
        race_name="Bernina Ultraks Steinbock",
        start_date="2026-07-05",
    )
    by_date = {w.date: w for w in workouts}
    mechanics = by_date["2026-07-06"]

    assert mechanics.constraints["run_allowed_if"] == [
        "normal_downstairs_walking",
        "no_hamstring_warning",
        "symmetric_jog_after_10min",
    ]
    assert mechanics.constraints["fallback"] == "rest_or_30min_recovery_spin"
    assert all(w.generator["generator_version"] == "post_trail_race_week.v1" for w in workouts)
    assert {w.generator["race_name"] for w in workouts} == {"Bernina Ultraks Steinbock"}


def test_generate_post_trail_race_week_summary_is_stable() -> None:
    workouts = generate_post_trail_race_week(
        race_date="2026-07-04",
        race_name="Bernina Ultraks Steinbock",
        start_date="2026-07-05",
    )
    summaries = [render_workout_summary(w) for w in workouts]

    assert summaries[1] == (
        "25-35min mechanics-check easy jog or rest. 30min main, HR cap 145, "
        "terrain flat soft surface, effort very easy, Stop immediately if mechanics are not symmetric. "
        "Fallback: rest_or_30min_recovery_spin. Run allowed if normal downstairs walking, "
        "no hamstring warning, symmetric jog after 10min. Stop if limp, sharp quad pain, "
        "hamstring warning. First run back is mechanics-gated, not load-gated."
    )
    assert "No strength yet" in summaries[4]
