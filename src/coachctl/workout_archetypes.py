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


def recovery_spin(
    *,
    date: str,
    title: str,
    duration_min: int,
    estimated_tss: float | None,
    power_cap_watts: int | None = None,
    optional: bool = True,
    notes: list[str] | None = None,
) -> WorkoutSpec:
    """Build an easy post-race recovery ride option."""
    target: dict[str, object] = {"effort": "very_easy" if optional else "easy"}
    if power_cap_watts is not None:
        target["power_cap_watts"] = power_cap_watts
    return WorkoutSpec(
        date=date,
        sport="ride",
        archetype="recovery_spin",
        title=title,
        duration_min=duration_min,
        intensity="recovery",
        priority="optional" if optional else "recovery",
        estimated_tss=estimated_tss,
        steps=[
            WorkoutStep(
                kind="main",
                duration_min=duration_min,
                target=target,
                cue="Keep cadence light and stop if legs feel worse.",
            )
        ],
        notes=notes or [],
        generator=_generator("recovery_spin.v1"),
    )


def mechanics_check_run(
    *,
    date: str,
    title: str = "25-35min mechanics-check easy jog or rest",
    duration_min: int = 30,
    estimated_tss: float | None = 20.0,
) -> WorkoutSpec:
    """Build the first post-race run with explicit mechanics gates."""
    return WorkoutSpec(
        date=date,
        sport="run",
        archetype="mechanics_check_run",
        title=title,
        duration_min=duration_min,
        intensity="recovery",
        priority="optional",
        estimated_tss=estimated_tss,
        steps=[
            WorkoutStep(
                kind="main",
                duration_min=duration_min,
                target={"hr_cap": 145, "terrain": "flat_soft_surface", "effort": "very_easy"},
                cue="Stop immediately if mechanics are not symmetric.",
            )
        ],
        constraints={
            "run_allowed_if": [
                "normal_downstairs_walking",
                "no_hamstring_warning",
                "symmetric_jog_after_10min",
            ],
            "fallback": "rest_or_30min_recovery_spin",
            "stop_if": ["limp", "sharp_quad_pain", "hamstring_warning"],
        },
        notes=["First run back is mechanics-gated, not load-gated."],
        generator=_generator("mechanics_check_run.v1"),
    )


def easy_aerobic_run(
    *,
    date: str,
    title: str,
    duration_min: int,
    estimated_tss: float | None,
    hr_cap: int = 150,
    terrain: str = "flat_soft_surface",
    notes: list[str] | None = None,
    fallback: str = "rest_or_recovery_spin",
) -> WorkoutSpec:
    """Build a post-race easy run with conservative stop rules."""
    return WorkoutSpec(
        date=date,
        sport="run",
        archetype="easy_aerobic_run",
        title=title,
        duration_min=duration_min,
        intensity="easy",
        priority="support",
        estimated_tss=estimated_tss,
        steps=[
            WorkoutStep(
                kind="main",
                duration_min=duration_min,
                target={"hr_cap": hr_cap, "terrain": terrain, "effort": "easy"},
                cue="Keep it flat and conversational.",
            )
        ],
        constraints={
            "fallback": fallback,
            "stop_if": ["limp", "sharp_quad_pain", "hamstring_warning", "mechanics_fade"],
        },
        notes=notes or [],
        generator=_generator("easy_aerobic_run.v1"),
    )


def mobility_rest(
    *,
    date: str,
    title: str = "Rest or mobility only",
    notes: list[str] | None = None,
) -> WorkoutSpec:
    """Build a post-race rest day that explicitly suppresses strength."""
    return WorkoutSpec(
        date=date,
        sport="rest",
        archetype="mobility_rest",
        title=title,
        duration_min=0,
        intensity="rest",
        priority="recovery",
        estimated_tss=0.0,
        steps=[WorkoutStep(kind="note", cue="No training.")],
        constraints={"stop_if": ["fatigue_spike"]},
        notes=notes or ["No strength yet; skip eccentric work this week."],
        generator=_generator("mobility_rest.v1"),
    )


def z2_ride(
    *,
    date: str,
    title: str,
    duration_min: int,
    estimated_tss: float | None,
    power_range_watts: tuple[int, int] = (154, 210),
    notes: list[str] | None = None,
) -> WorkoutSpec:
    """Build an aerobic Z2 ride."""
    return WorkoutSpec(
        date=date,
        sport="ride",
        archetype="z2_ride",
        title=title,
        duration_min=duration_min,
        intensity="easy",
        priority="support",
        estimated_tss=estimated_tss,
        steps=[
            WorkoutStep(
                kind="main",
                duration_min=duration_min,
                target={"power_range_watts": list(power_range_watts), "effort": "easy"},
                cue="Keep pressure aerobic; no sweet spot unless explicitly prescribed.",
            )
        ],
        notes=notes or [],
        generator=_generator("z2_ride.v1"),
    )


def cruise_intervals(
    *,
    date: str,
    title: str,
    duration_min: int,
    reps: int,
    rep_distance_km: float,
    float_distance_km: float,
    pace_range_sec_per_km: tuple[int, int],
    estimated_tss: float | None,
) -> WorkoutSpec:
    """Build controlled threshold/cruise intervals for HM preparation."""
    return WorkoutSpec(
        date=date,
        sport="run",
        archetype="cruise_intervals",
        title=title,
        duration_min=duration_min,
        intensity="threshold",
        priority="key",
        estimated_tss=estimated_tss,
        steps=[
            WorkoutStep(kind="warmup", duration_min=15, target={"effort": "easy"}),
            WorkoutStep(
                kind="interval",
                reps=reps,
                target={
                    "rep_distance_km": rep_distance_km,
                    "float_distance_km": float_distance_km,
                    "pace_range_sec_per_km": list(pace_range_sec_per_km),
                },
                cue="Float is controlled, not another rep.",
            ),
            WorkoutStep(kind="cooldown", duration_min=10, target={"effort": "easy"}),
        ],
        constraints={"stop_if": ["hamstring_warning", "mechanics_fade"]},
        generator=_generator("cruise_intervals.v1"),
    )


def ladder_intervals(
    *,
    date: str,
    title: str,
    duration_min: int,
    rungs_min: tuple[int, ...],
    pace_range_sec_per_km: tuple[int, int],
    recovery_min: float,
    estimated_tss: float | None,
) -> WorkoutSpec:
    """Build a threshold ladder: one interval rung per entry in ``rungs_min``.

    ``rungs_min`` is the ordered sequence of rep durations in minutes (e.g.
    ``(3, 4, 5, 4, 3)`` for an up-and-down ladder). Each rung is a single rep
    at the target pace, separated by ``recovery_min`` of easy floating.
    """
    if not rungs_min:
        raise ValueError("ladder_intervals requires at least one rung")
    rung_steps = [
        WorkoutStep(
            kind="interval",
            reps=1,
            repeat_duration_min=float(minutes),
            recovery_min=recovery_min,
            target={"pace_range_sec_per_km": list(pace_range_sec_per_km)},
            cue="Hold pace as the rung length changes.",
        )
        for minutes in rungs_min
    ]
    return WorkoutSpec(
        date=date,
        sport="run",
        archetype="ladder_intervals",
        title=title,
        duration_min=duration_min,
        intensity="threshold",
        priority="key",
        estimated_tss=estimated_tss,
        steps=[
            WorkoutStep(kind="warmup", duration_min=15, target={"effort": "easy"}),
            *rung_steps,
            WorkoutStep(kind="cooldown", duration_min=10, target={"effort": "easy"}),
        ],
        constraints={"stop_if": ["hamstring_warning", "mechanics_fade"]},
        generator=_generator("ladder_intervals.v1"),
    )


def mona_fartlek(
    *,
    date: str,
    title: str,
    duration_min: int,
    estimated_tss: float | None,
) -> WorkoutSpec:
    """Build the canonical 20-minute Mona fartlek.

    Surge ladder with equal-time floating recoveries: 2x90s, 4x60s, 4x30s,
    4x15s. Floats are easy running, not standing rest, so the whole block is
    continuous.
    """
    surge_groups = (
        (2, 1.5),   # 2 x 90s
        (4, 1.0),   # 4 x 60s
        (4, 0.5),   # 4 x 30s
        (4, 0.25),  # 4 x 15s
    )
    surge_steps = [
        WorkoutStep(
            kind="interval",
            reps=reps,
            repeat_duration_min=surge_min,
            recovery_min=surge_min,
            target={"effort": "mona_fartlek"},
            cue="Float is easy running, not standing rest.",
        )
        for reps, surge_min in surge_groups
    ]
    return WorkoutSpec(
        date=date,
        sport="run",
        archetype="mona_fartlek",
        title=title,
        duration_min=duration_min,
        intensity="threshold",
        priority="key",
        estimated_tss=estimated_tss,
        steps=[
            WorkoutStep(kind="warmup", duration_min=15, target={"effort": "easy"}),
            *surge_steps,
            WorkoutStep(kind="cooldown", duration_min=10, target={"effort": "easy"}),
        ],
        constraints={"stop_if": ["hamstring_warning", "mechanics_fade"]},
        generator=_generator("mona_fartlek.v1"),
    )


def progressive_long_run(
    *,
    date: str,
    title: str,
    duration_min: int,
    estimated_tss: float | None,
    easy_duration_min: int,
    finish_blocks: int,
    finish_block_min: int,
    fuel_carbs_g_per_hr: tuple[int, int] = (55, 65),
) -> WorkoutSpec:
    """Build a half-marathon progressive long run."""
    return WorkoutSpec(
        date=date,
        sport="run",
        archetype="progressive_long_run",
        title=title,
        duration_min=duration_min,
        intensity="tempo",
        priority="key",
        estimated_tss=estimated_tss,
        steps=[
            WorkoutStep(
                kind="main",
                duration_min=easy_duration_min,
                target={"hr_cap": 154, "effort": "easy"},
                cue="Do not race the first hour.",
            ),
            WorkoutStep(
                kind="interval",
                reps=finish_blocks,
                repeat_duration_min=finish_block_min,
                recovery_min=3,
                target={"effort": "hm_steady"},
                cue="Progress only if mechanics stay clean.",
            ),
        ],
        constraints={
            "fuel_carbs_g_per_hr": list(fuel_carbs_g_per_hr),
            "stop_if": ["hamstring_warning", "mechanics_fade", "hr_drift_high"],
        },
        generator=_generator("progressive_long_run.v1"),
    )


def _generator(archetype_version: str) -> dict[str, str]:
    return {
        "name": GENERATOR_NAME,
        "version": GENERATOR_VERSION,
        "archetype_version": archetype_version,
    }
