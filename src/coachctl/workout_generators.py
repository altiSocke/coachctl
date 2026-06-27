"""Deterministic workout generators that compose archetypes."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

from .workout_archetypes import (
    cruise_intervals,
    easy_aerobic_run,
    easy_run,
    hill_activation,
    mechanics_check_run,
    mobility_rest,
    progressive_long_run,
    recovery_spin,
    rest_day,
    shakeout,
    trail_race_simulation,
    z2_ride,
)
from .workouts import WorkoutSpec

TRAIL_RACE_WEEK_GENERATOR_VERSION = "trail_race_week.v1"
POST_TRAIL_RACE_WEEK_GENERATOR_VERSION = "post_trail_race_week.v1"
HALF_MARATHON_BUILD_WEEK_GENERATOR_VERSION = "half_marathon_build_week.v1"


def generate_trail_race_week(
    *,
    race_date: str,
    race_name: str,
    start_date: str,
    simulation_title: str = "90min trail run - race simulation",
    start_time: str = "05:30",
) -> list[WorkoutSpec]:
    """Generate the final seven days before a short trail race.

    The race day itself is intentionally not emitted: the existing race event in
    ``events`` remains the source of truth and blocks same-day training.
    """
    race_day = date.fromisoformat(race_date)
    start = date.fromisoformat(start_date)
    expected_start = race_day - timedelta(days=7)
    if start != expected_start:
        raise ValueError("trail race-week generation currently requires start_date = race_date - 7d")

    workouts = [
        trail_race_simulation(
            date=_iso(race_day - timedelta(days=7)),
            title=simulation_title,
            duration_min=90,
            start_time=start_time,
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
        ),
        rest_day(
            date=_iso(race_day - timedelta(days=6)),
            title="Rest or 45min recovery spin",
            estimated_tss=20.0,
            notes=["Rest preferred."],
            optional_alternative="45min recovery spin <170W only if legs feel good",
        ),
        easy_run(
            date=_iso(race_day - timedelta(days=5)),
            duration_min=40,
            hr_cap=155,
            title="40min easy trail run + strides",
            sport="trail_run",
            strides=4,
            start_time="06:00",
            estimated_tss=35.0,
            notes=["Race-week rhythm only, low stress."],
        ),
        rest_day(date=_iso(race_day - timedelta(days=4))),
        hill_activation(
            date=_iso(race_day - timedelta(days=3)),
            duration_min=45,
            reps=3,
            rep_duration_min=2,
            recovery_min=3,
            hr_cap=165,
            rpe="7-8",
            start_time="06:00",
            estimated_tss=50.0,
        ),
        shakeout(date=_iso(race_day - timedelta(days=2)), duration_min=30, estimated_tss=20.0),
        rest_day(
            date=_iso(race_day - timedelta(days=1)),
            title="Rest / travel / pack",
            notes=["Pack kit and protect sleep."],
        ),
    ]
    return [
        _with_generator_context(w, race_name, TRAIL_RACE_WEEK_GENERATOR_VERSION)
        for w in workouts
    ]


def generate_post_trail_race_week(
    *,
    race_date: str,
    race_name: str,
    start_date: str,
) -> list[WorkoutSpec]:
    """Generate a conservative adaptive week after a steep trail race."""
    race_day = date.fromisoformat(race_date)
    start = date.fromisoformat(start_date)
    expected_start = race_day + timedelta(days=1)
    if start != expected_start:
        raise ValueError("post trail race-week generation requires start_date = race_date + 1d")

    workouts = [
        rest_day(
            date=_iso(race_day + timedelta(days=1)),
            title="Rest or 30-45min recovery spin",
            estimated_tss=10.0,
            notes=["Spin only if legs feel better after walking."],
            optional_alternative="30-45min recovery spin <160W",
        ),
        mechanics_check_run(date=_iso(race_day + timedelta(days=2)), estimated_tss=15.0),
        recovery_spin(
            date=_iso(race_day + timedelta(days=3)),
            title="45-60min Z1-Z2 ride or rest",
            duration_min=50,
            estimated_tss=20.0,
            power_cap_watts=180,
            notes=["Ride if quads are still sore; no run pressure."],
        ),
        easy_aerobic_run(
            date=_iso(race_day + timedelta(days=4)),
            title="35-45min easy run",
            duration_min=40,
            estimated_tss=25.0,
            hr_cap=150,
            notes=["No strides, no hills, no intensity."],
        ),
        mobility_rest(
            date=_iso(race_day + timedelta(days=5)),
            notes=["No strength yet; skip eccentric work this week."],
        ),
        easy_aerobic_run(
            date=_iso(race_day + timedelta(days=6)),
            title="45-55min easy run",
            duration_min=50,
            estimated_tss=35.0,
            hr_cap=150,
            notes=["Flat or soft surface only; Greifenseelauf block resumes after absorption."],
        ),
        easy_aerobic_run(
            date=_iso(race_day + timedelta(days=7)),
            title="60-75min easy aerobic run or Z2 ride",
            duration_min=60,
            estimated_tss=35.0,
            hr_cap=150,
            notes=["Run only if fully normal; otherwise ride Z2."],
            fallback="60-75min_Z2_ride",
        ),
        recovery_spin(
            date=_iso(race_day + timedelta(days=8)),
            title="60min optional Z2 ride",
            duration_min=60,
            estimated_tss=15.0,
            power_cap_watts=190,
            notes=["Low-stress aerobic only."],
        ),
    ]
    return [
        _with_generator_context(w, race_name, POST_TRAIL_RACE_WEEK_GENERATOR_VERSION)
        for w in workouts
    ]


def generate_half_marathon_build_week(
    *,
    week_start: str,
    target_tss: int,
    phase: str,
    freshness: str = "normal",
) -> list[WorkoutSpec]:
    """Generate one deterministic half-marathon training week.

    This is intentionally preview-first: it encodes the weekly skeleton and
    safety rules, but does not read or write database state.
    """
    start = date.fromisoformat(week_start)
    if phase not in {"build", "recovery"}:
        raise ValueError("phase must be 'build' or 'recovery'")
    if freshness == "fatigued":
        workouts = _half_marathon_fatigued_week(start)
    elif phase == "recovery":
        workouts = _half_marathon_recovery_week(start)
    else:
        workouts = _half_marathon_build_week(start, target_tss)
    return [
        _with_generator_context(
            w,
            "half_marathon",
            HALF_MARATHON_BUILD_WEEK_GENERATOR_VERSION,
        )
        for w in workouts
    ]


def _half_marathon_build_week(start: date, target_tss: int) -> list[WorkoutSpec]:
    # Keep the first version explicit and auditable; later versions can scale
    # durations/TSS from target_tss once the weekly shape is proven.
    return [
        easy_run(
            date=_iso(start),
            duration_min=55,
            hr_cap=154,
            title="55min easy Z2 run",
            estimated_tss=45.0,
        ),
        z2_ride(
            date=_iso(start + timedelta(days=1)),
            title="90min Z2 ride + cadence drills",
            duration_min=90,
            estimated_tss=70.0,
            notes=["Include 3x5min high cadence 100-110rpm inside Z2."],
        ),
        cruise_intervals(
            date=_iso(start + timedelta(days=2)),
            title="70min cruise intervals",
            duration_min=70,
            reps=5,
            rep_distance_km=1.0,
            float_distance_km=0.5,
            pace_range_sec_per_km=(248, 252),
            estimated_tss=85.0,
        ),
        easy_run(
            date=_iso(start + timedelta(days=3)),
            duration_min=50,
            hr_cap=154,
            title="50min easy Z2 run",
            estimated_tss=40.0,
        ),
        rest_day(date=_iso(start + timedelta(days=4))),
        progressive_long_run(
            date=_iso(start + timedelta(days=5)),
            title="105min progressive HM long run",
            duration_min=105,
            estimated_tss=110.0,
            easy_duration_min=70,
            finish_blocks=3,
            finish_block_min=10,
        ),
        z2_ride(
            date=_iso(start + timedelta(days=6)),
            title="60-75min recovery Z2 ride",
            duration_min=70,
            estimated_tss=35.0,
            power_range_watts=(154, 190),
            notes=["Easy spin only; absorb Saturday's long run."],
        ),
    ]


def _half_marathon_recovery_week(start: date) -> list[WorkoutSpec]:
    return [
        easy_run(
            date=_iso(start),
            duration_min=45,
            hr_cap=150,
            title="45min easy Z2 run",
            estimated_tss=35.0,
        ),
        z2_ride(
            date=_iso(start + timedelta(days=1)),
            title="60min easy Z2 ride",
            duration_min=60,
            estimated_tss=45.0,
            power_range_watts=(154, 185),
        ),
        easy_run(
            date=_iso(start + timedelta(days=2)),
            duration_min=40,
            hr_cap=150,
            title="40min easy run",
            estimated_tss=30.0,
        ),
        rest_day(date=_iso(start + timedelta(days=3))),
        easy_run(
            date=_iso(start + timedelta(days=4)),
            duration_min=35,
            hr_cap=150,
            title="35min easy run",
            estimated_tss=25.0,
        ),
        easy_aerobic_run(
            date=_iso(start + timedelta(days=5)),
            title="60min easy aerobic run",
            duration_min=60,
            estimated_tss=50.0,
            hr_cap=150,
        ),
        recovery_spin(
            date=_iso(start + timedelta(days=6)),
            title="45min recovery spin",
            duration_min=45,
            estimated_tss=30.0,
            power_cap_watts=170,
        ),
    ]


def _half_marathon_fatigued_week(start: date) -> list[WorkoutSpec]:
    return [
        easy_run(
            date=_iso(start),
            duration_min=40,
            hr_cap=148,
            title="40min easy run",
            estimated_tss=30.0,
        ),
        recovery_spin(
            date=_iso(start + timedelta(days=1)),
            title="45min recovery spin",
            duration_min=45,
            estimated_tss=25.0,
            power_cap_watts=170,
        ),
        easy_run(
            date=_iso(start + timedelta(days=2)),
            duration_min=35,
            hr_cap=148,
            title="35min easy run",
            estimated_tss=25.0,
        ),
        rest_day(date=_iso(start + timedelta(days=3))),
        easy_run(
            date=_iso(start + timedelta(days=4)),
            duration_min=40,
            hr_cap=148,
            title="40min easy run",
            estimated_tss=30.0,
        ),
        easy_aerobic_run(
            date=_iso(start + timedelta(days=5)),
            title="60min easy aerobic run or Z2 ride",
            duration_min=60,
            estimated_tss=45.0,
            hr_cap=148,
            fallback="60min_Z2_ride",
        ),
        recovery_spin(
            date=_iso(start + timedelta(days=6)),
            title="60min optional recovery ride",
            duration_min=60,
            estimated_tss=25.0,
            power_cap_watts=170,
        ),
    ]


def _with_generator_context(
    workout: WorkoutSpec, race_name: str, generator_version: str
) -> WorkoutSpec:
    generator = dict(workout.generator)
    generator["generator_version"] = generator_version
    generator["race_name"] = race_name
    return replace(workout, generator=generator)


def _iso(d: date) -> str:
    return d.isoformat()
