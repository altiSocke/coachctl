from __future__ import annotations

import pytest

from coachctl.events import KIND_TRAINING, STATUS_PLANNED
from coachctl.workouts import (
    WorkoutSpec,
    WorkoutStep,
    render_workout_summary,
    workout_from_payload,
    workout_to_event,
    workout_to_payload,
)


def test_workout_payload_round_trip() -> None:
    workout = WorkoutSpec(
        date="2026-06-29",
        sport="trail_run",
        archetype="easy_run_strides",
        title="40min easy trail run + strides",
        duration_min=40,
        intensity="easy",
        priority="support",
        estimated_tss=34.6,
        steps=[
            WorkoutStep(
                kind="main",
                duration_min=40,
                target={"hr_cap": 155, "rpe_max": 4},
                cue="Keep this genuinely easy.",
            ),
            WorkoutStep(
                kind="stride",
                reps=4,
                repeat_duration_min=0.25,
                recovery_min=0.75,
                target={"effort": "relaxed_fast"},
            ),
        ],
        constraints={"stop_if": ["hamstring_warning"]},
        notes=["Race-week rhythm only."],
        generator={"name": "deterministic", "version": "0.1"},
    )

    payload = workout_to_payload(workout)

    assert payload["schema"] == "workout_spec.v1"
    assert workout_from_payload(payload) == workout


def test_workout_validation_rejects_unknown_labels() -> None:
    with pytest.raises(ValueError, match="sport"):
        WorkoutSpec(
            date="2026-06-29",
            sport="swim",  # type: ignore[arg-type]
            archetype="easy_swim",
            title="Easy swim",
            duration_min=30,
            intensity="easy",
            priority="support",
        )

    with pytest.raises(ValueError, match="intensity"):
        WorkoutSpec(
            date="2026-06-29",
            sport="run",
            archetype="steady_run",
            title="Steady run",
            duration_min=45,
            intensity="steady",  # type: ignore[arg-type]
            priority="support",
        )


def test_render_workout_summary_is_deterministic() -> None:
    workout = WorkoutSpec(
        date="2026-06-27",
        sport="trail_run",
        archetype="trail_race_simulation",
        title="90min trail race simulation",
        duration_min=90,
        intensity="tempo",
        priority="key",
        estimated_tss=85.0,
        steps=[
            WorkoutStep(kind="warmup", duration_min=15, target={"hr_cap": 155}),
            WorkoutStep(
                kind="interval",
                reps=2,
                repeat_duration_min=10,
                recovery_min=8,
                target={"hr_range": [160, 165], "rpe": 7},
                cue="Power-hike steep ramps. No racing.",
            ),
            WorkoutStep(
                kind="main",
                duration_min=20,
                target={"terrain": "sustained_descent", "cadence_spm": [170, 180]},
            ),
        ],
        constraints={"fuel_carbs_g_per_hr": [65, 75], "max_elevation_gain_m": 800},
        notes=["Rehearsal only."],
    )

    assert render_workout_summary(workout) == (
        "90min trail race simulation. 15min warmup, HR cap 155; "
        "2x10min interval, 8min recovery, HR 160-165, RPE 7, "
        "Power-hike steep ramps. No racing; 20min main, terrain sustained descent, "
        "cadence 170-180 spm. Fuel 65-75g carbs/hr. Max elevation gain 800m. "
        "Rehearsal only."
    )
    assert render_workout_summary(workout) == render_workout_summary(workout)


def test_workout_to_event_populates_existing_event_fields() -> None:
    workout = WorkoutSpec(
        date="2026-07-01",
        sport="trail_run",
        archetype="hill_activation",
        title="45min easy run + 3x2min uphill activation",
        duration_min=45,
        intensity="moderate",
        priority="support",
        estimated_tss=50.0,
        steps=[
            WorkoutStep(kind="main", duration_min=39, target={"hr_cap": 155}),
            WorkoutStep(
                kind="interval",
                reps=3,
                repeat_duration_min=2,
                recovery_min=3,
                target={"rpe": "7-8"},
            ),
        ],
        generator={"name": "deterministic", "version": "0.1"},
    )

    event = workout_to_event(workout, slug="generated-2026-07-01", plan_id=2, week_number=11)

    assert event.slug == "generated-2026-07-01"
    assert event.kind == KIND_TRAINING
    assert event.status == STATUS_PLANNED
    assert event.date == "2026-07-01"
    assert event.name == workout.title
    assert event.duration_min == 45
    assert event.estimated_tss == 50.0
    assert event.plan_id == 2
    assert event.payload["schema"] == "workout_spec.v1"
    assert event.payload["workout"]["archetype"] == "hill_activation"
    assert event.payload["week_number"] == 11
    assert "3x2min interval" in (event.summary or "")


def test_render_workout_summary_includes_common_constraints_readably() -> None:
    workout = WorkoutSpec(
        date="2026-06-27",
        sport="trail_run",
        archetype="trail_race_simulation",
        title="90min trail run - Steinbock race simulation (05:30)",
        duration_min=90,
        intensity="tempo",
        priority="key",
        steps=[
            WorkoutStep(
                kind="main",
                duration_min=20,
                target={"elevation_loss_m": [300, 400], "terrain": "sustained_descent"},
            )
        ],
        constraints={
            "start_time": "05:30",
            "elevation_gain_target_m": [600, 800],
            "fuel_carbs_g_per_hr": [65, 75],
            "route_options": [
                "shaded forest trail (Uetliberg/Albis)",
                "higher altitude if possible",
            ],
            "stop_if": ["hamstring_warning", "quad_pain", "mechanics_fade"],
        },
    )

    summary = render_workout_summary(workout)

    assert "Start 05:30." in summary
    assert "descent 300-400m" in summary
    assert "Elevation gain target 600-800m." in summary
    assert "Fuel 65-75g carbs/hr." in summary
    assert (
        "Route: shaded forest trail (Uetliberg/Albis) or higher altitude if possible."
        in summary
    )
    assert "Stop if hamstring warning, quad pain, mechanics fade." in summary
