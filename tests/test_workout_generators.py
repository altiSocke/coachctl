from __future__ import annotations

from coachctl.workout_generators import generate_trail_race_week
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
