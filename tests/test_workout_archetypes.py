from __future__ import annotations

from coachctl.workout_archetypes import easy_run, hill_activation, trail_race_simulation
from coachctl.workouts import render_workout_summary


def test_easy_run_archetype_is_stable() -> None:
    workout = easy_run(
        date="2026-06-29",
        duration_min=40,
        hr_cap=155,
        title="40min easy trail run + strides",
        sport="trail_run",
        strides=4,
        start_time="06:00",
        estimated_tss=35.0,
        notes=["Race-week rhythm only, low stress."],
    )

    assert workout.archetype == "easy_run_strides"
    assert workout.intensity == "easy"
    assert workout.priority == "support"
    assert workout.estimated_tss == 35.0
    assert workout.generator == {
        "name": "deterministic",
        "version": "0.1",
        "archetype_version": "easy_run.v1",
    }
    assert [step.kind for step in workout.steps] == ["main", "stride"]
    assert workout.steps[1].reps == 4
    assert render_workout_summary(workout) == (
        "40min easy trail run + strides. 40min main, HR cap 155, terrain trail, "
        "effort easy; 4x0.25min stride, 0.75min recovery, effort relaxed fast. "
        "Start 06:00. Race-week rhythm only, low stress."
    )


def test_hill_activation_archetype_is_stable() -> None:
    workout = hill_activation(
        date="2026-07-01",
        duration_min=45,
        reps=3,
        rep_duration_min=2,
        recovery_min=3,
        hr_cap=165,
        rpe="7-8",
        start_time="06:00",
        estimated_tss=50.0,
    )

    assert workout.archetype == "hill_activation"
    assert workout.intensity == "moderate"
    assert workout.priority == "support"
    assert workout.steps[0].duration_min == 39
    assert workout.steps[1].reps == 3
    assert workout.steps[1].repeat_duration_min == 2
    assert render_workout_summary(workout) == (
        "45min easy run + 3x2min uphill activation. 39min main, HR cap 155, "
        "terrain easy trail or road, effort easy; 3x2min interval, 3min recovery, "
        "HR cap 165, RPE 7-8, terrain uphill, Sharpening only - not a workout. "
        "Start 06:00. Stop if hamstring warning."
    )


def test_trail_race_simulation_archetype_matches_saturday_fixture() -> None:
    workout = trail_race_simulation(
        date="2026-06-27",
        title="90min trail run - Steinbock race simulation (05:30)",
        duration_min=90,
        start_time="05:30",
        estimated_tss=85.0,
        climb_reps=2,
        climb_rep_duration_min=10,
        climb_recovery_min=8,
        climb_hr_range=(160, 165),
        descent_duration_min=20,
        descent_loss_m=(300, 400),
        elevation_gain_target_m=(600, 800),
        fuel_carbs_g_per_hr=(65, 75),
        route_options=(
            "shaded forest trail (Uetliberg/Albis)",
            "higher altitude if possible",
        ),
    )

    assert workout.sport == "trail_run"
    assert workout.archetype == "trail_race_simulation"
    assert workout.intensity == "tempo"
    assert workout.priority == "key"
    assert workout.steps[1].target == {
        "terrain": "hiking_climb",
        "hr_range": [160, 165],
        "rpe": 7,
    }
    assert workout.constraints["elevation_gain_target_m"] == [600, 800]
    assert workout.generator == {
        "name": "deterministic",
        "version": "0.1",
        "archetype_version": "trail_race_simulation.v1",
    }
    assert render_workout_summary(workout) == (
        "90min trail run - Steinbock race simulation (05:30). "
        "15min warmup, HR cap 155, Valley approach, relaxed; "
        "2x10min interval, 8min recovery, HR 160-165, RPE 7, terrain hiking climb, "
        "Steinbock main-climb effort. Power-hike steep ramps; "
        "20min main, HR cap 155, terrain rolling trail, Settle back to Z2 after climbs; "
        "20min main, terrain sustained descent, cadence 170-180 spm, descent 300-400m, "
        "effort controlled fast, Short stride, soft feet, eyes ahead. No braking heroics; "
        "10min cooldown. Start 05:30. Fuel 65-75g carbs/hr. "
        "Elevation gain target 600-800m. Route: shaded forest trail (Uetliberg/Albis) "
        "or higher altitude if possible. Stop if hamstring warning, quad pain, mechanics fade. "
        "Race rehearsal only; do not turn this into a fitness test."
    )
