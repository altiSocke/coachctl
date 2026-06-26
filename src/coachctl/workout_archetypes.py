"""Deterministic workout archetype builders.

These functions are pure constructors: inputs in, ``WorkoutSpec`` out. They do
not read profile/wiki state and do not write to the database.
"""

from __future__ import annotations

from typing import Iterable

from .workouts import Sport, WorkoutSpec, WorkoutStep

GENERATOR_NAME = "deterministic"
GENERATOR_VERSION = "0.1"


def easy_run(
    *,
    date: str,
    duration_min: int,
    hr_cap: int,
    title: str | None = None,
    sport: Sport = "run",
    terrain: str = "trail",
    strides: int = 0,
    start_time: str | None = None,
    estimated_tss: float | None = None,
    notes: list[str] | None = None,
) -> WorkoutSpec:
    """Build an easy aerobic run, optionally with relaxed strides."""
    steps = [
        WorkoutStep(
            kind="main",
            duration_min=duration_min,
            target={"hr_cap": hr_cap, "terrain": terrain, "effort": "easy"},
        )
    ]
    archetype = "easy_run"
    if strides:
        archetype = "easy_run_strides"
        steps.append(
            WorkoutStep(
                kind="stride",
                reps=strides,
                repeat_duration_min=0.25,
                recovery_min=0.75,
                target={"effort": "relaxed_fast"},
            )
        )

    constraints: dict[str, object] = {}
    if start_time:
        constraints["start_time"] = start_time

    return WorkoutSpec(
        date=date,
        sport=sport,
        archetype=archetype,
        title=title or f"{duration_min}min easy run",
        duration_min=duration_min,
        intensity="easy",
        priority="support",
        estimated_tss=estimated_tss,
        steps=steps,
        constraints=constraints,
        notes=notes or [],
        generator=_generator("easy_run.v1"),
    )


def hill_activation(
    *,
    date: str,
    duration_min: int,
    reps: int,
    rep_duration_min: int,
    recovery_min: int,
    hr_cap: int,
    rpe: int | str,
    start_time: str | None = None,
    estimated_tss: float | None = None,
) -> WorkoutSpec:
    """Build a short race-week uphill activation session."""
    interval_total = reps * rep_duration_min
    main_duration = max(duration_min - interval_total, 0)
    constraints: dict[str, object] = {"stop_if": ["hamstring_warning"]}
    if start_time:
        constraints["start_time"] = start_time

    return WorkoutSpec(
        date=date,
        sport="trail_run",
        archetype="hill_activation",
        title=f"{duration_min}min easy run + {reps}x{rep_duration_min}min uphill activation",
        duration_min=duration_min,
        intensity="moderate",
        priority="support",
        estimated_tss=estimated_tss,
        steps=[
            WorkoutStep(
                kind="main",
                duration_min=main_duration,
                target={"hr_cap": 155, "terrain": "easy_trail_or_road", "effort": "easy"},
            ),
            WorkoutStep(
                kind="interval",
                reps=reps,
                repeat_duration_min=rep_duration_min,
                recovery_min=recovery_min,
                target={"hr_cap": hr_cap, "rpe": rpe, "terrain": "uphill"},
                cue="Sharpening only - not a workout.",
            ),
        ],
        constraints=constraints,
        generator=_generator("hill_activation.v1"),
    )


def trail_race_simulation(
    *,
    date: str,
    title: str,
    duration_min: int,
    start_time: str,
    estimated_tss: float | None,
    climb_reps: int,
    climb_rep_duration_min: int,
    climb_recovery_min: int,
    climb_hr_range: tuple[int, int],
    descent_duration_min: int,
    descent_loss_m: tuple[int, int],
    elevation_gain_target_m: tuple[int, int],
    fuel_carbs_g_per_hr: tuple[int, int],
    route_options: Iterable[str],
) -> WorkoutSpec:
    """Build a controlled trail-race rehearsal session."""
    return WorkoutSpec(
        date=date,
        sport="trail_run",
        archetype="trail_race_simulation",
        title=title,
        duration_min=duration_min,
        intensity="tempo",
        priority="key",
        estimated_tss=estimated_tss,
        steps=[
            WorkoutStep(
                kind="warmup",
                duration_min=15,
                target={"hr_cap": 155},
                cue="Valley approach, relaxed.",
            ),
            WorkoutStep(
                kind="interval",
                reps=climb_reps,
                repeat_duration_min=climb_rep_duration_min,
                recovery_min=climb_recovery_min,
                target={
                    "terrain": "hiking_climb",
                    "hr_range": list(climb_hr_range),
                    "rpe": 7,
                },
                cue="Steinbock main-climb effort. Power-hike steep ramps.",
            ),
            WorkoutStep(
                kind="main",
                duration_min=20,
                target={"hr_cap": 155, "terrain": "rolling_trail"},
                cue="Settle back to Z2 after climbs.",
            ),
            WorkoutStep(
                kind="main",
                duration_min=descent_duration_min,
                target={
                    "terrain": "sustained_descent",
                    "cadence_spm": [170, 180],
                    "elevation_loss_m": list(descent_loss_m),
                    "effort": "controlled_fast",
                },
                cue="Short stride, soft feet, eyes ahead. No braking heroics.",
            ),
            WorkoutStep(kind="cooldown", duration_min=10, target={"intensity": "Z1"}),
        ],
        constraints={
            "start_time": start_time,
            "fuel_carbs_g_per_hr": list(fuel_carbs_g_per_hr),
            "elevation_gain_target_m": list(elevation_gain_target_m),
            "route_options": list(route_options),
            "stop_if": ["hamstring_warning", "quad_pain", "mechanics_fade"],
        },
        notes=["Race rehearsal only; do not turn this into a fitness test."],
        generator=_generator("trail_race_simulation.v1"),
    )


def shakeout(
    *,
    date: str,
    duration_min: int = 30,
    title: str = "30min shakeout or rest",
    hr_cap: int = 145,
    estimated_tss: float | None = 20.0,
) -> WorkoutSpec:
    """Build a short race-week shakeout option."""
    return WorkoutSpec(
        date=date,
        sport="run",
        archetype="shakeout",
        title=title,
        duration_min=duration_min,
        intensity="recovery",
        priority="optional",
        estimated_tss=estimated_tss,
        steps=[
            WorkoutStep(
                kind="main",
                duration_min=duration_min,
                target={"hr_cap": hr_cap, "effort": "very_easy"},
                cue="Skip and rest if legs feel heavy.",
            )
        ],
        generator=_generator("shakeout.v1"),
    )


def rest_day(
    *,
    date: str,
    title: str = "Rest",
    estimated_tss: float | None = 0.0,
    notes: list[str] | None = None,
    optional_alternative: str | None = None,
) -> WorkoutSpec:
    """Build a structured rest day."""
    constraints: dict[str, object] = {}
    if optional_alternative:
        constraints["optional_alternative"] = optional_alternative
    return WorkoutSpec(
        date=date,
        sport="rest",
        archetype="rest",
        title=title,
        duration_min=0,
        intensity="rest",
        priority="recovery",
        estimated_tss=estimated_tss,
        steps=[WorkoutStep(kind="note", cue="No training.")],
        constraints=constraints,
        notes=notes or [],
        generator=_generator("rest_day.v1"),
    )


def _generator(archetype_version: str) -> dict[str, str]:
    return {
        "name": GENERATOR_NAME,
        "version": GENERATOR_VERSION,
        "archetype_version": archetype_version,
    }
