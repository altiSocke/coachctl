"""Expand a :class:`~coachctl.plan_templates.PlanTemplate` into workouts.

``expand_template`` walks a template week-by-week, day-by-day (Mon..Sun) and
calls the named archetype for each day-slot, producing a flat list of
``WorkoutSpec`` objects with concrete dates.

Determinism contract
---------------------
* ``seed=None`` — fully deterministic with **no** PRNG: every day-slot uses its
  base archetype (variant index 0) and zero duration jitter.
* ``seed=N`` — a single ``random.Random(N)`` drives the whole expansion. The
  random stream is consumed in a fixed order (week 0..K, each Mon..Sun; within a
  day: variant pick first, then duration jitter), so the same
  ``(template, start_date, seed)`` always yields identical output.

The expander stamps each workout's ``generator`` dict with template/seed/week
context (mirroring how :mod:`coachctl.workout_generators` stamps generator
context) so payloads round-trip stably through the events table.
"""

from __future__ import annotations

import random
from dataclasses import replace
from datetime import date, timedelta

from . import workout_archetypes as _arch
from .plan_templates import DaySlot, PlanTemplate
from .workouts import WorkoutSpec

PLAN_EXPANDER_VERSION = "plan_expander.v1"

# archetype name -> constructor. Kept explicit (no getattr/eval) so the set of
# callable archetypes is auditable and closed.
ARCHETYPE_DISPATCH = {
    "easy_run": _arch.easy_run,
    "z2_ride": _arch.z2_ride,
    "rest_day": _arch.rest_day,
    "cruise_intervals": _arch.cruise_intervals,
    "ladder_intervals": _arch.ladder_intervals,
    "mona_fartlek": _arch.mona_fartlek,
    "progressive_long_run": _arch.progressive_long_run,
    "easy_aerobic_run": _arch.easy_aerobic_run,
    "recovery_spin": _arch.recovery_spin,
    "shakeout": _arch.shakeout,
}


def expand_template(
    template: PlanTemplate,
    start_date: str,
    seed: int | None = None,
) -> list[WorkoutSpec]:
    """Expand ``template`` into a flat list of dated ``WorkoutSpec``.

    ``start_date`` (ISO ``YYYY-MM-DD``) anchors day 0 of week 0; the function
    lays out seven consecutive dates per week and does not enforce a particular
    weekday (callers that want Monday-aligned plans should pass a Monday).
    """
    base = date.fromisoformat(start_date)
    rng = random.Random(seed) if seed is not None else None

    workouts: list[WorkoutSpec] = []
    day_index = 0
    for week_number, week in enumerate(template.weeks):
        for slot in week.days:
            slot_date = (base + timedelta(days=day_index)).isoformat()
            workout = _expand_slot(
                slot,
                slot_date,
                rng,
                template_name=template.name,
                week_number=week_number,
                target_tss=week.target_tss,
                seed=seed,
            )
            workouts.append(workout)
            day_index += 1
    return workouts


def _expand_slot(
    slot: DaySlot,
    slot_date: str,
    rng: random.Random | None,
    *,
    template_name: str,
    week_number: int,
    target_tss: int,
    seed: int | None,
) -> WorkoutSpec:
    choices = slot.all_choices()

    # 1) variant selection (consumes RNG only when there is a real choice)
    if rng is not None and len(choices) > 1:
        archetype_name, params = rng.choice(choices)
    else:
        archetype_name, params = choices[0]

    call_kwargs = dict(params)
    call_kwargs["date"] = slot_date

    # 2) duration jitter (consumes RNG only when jitter is enabled). Applied to
    # the chosen archetype's duration; base archetypes for jitter slots omit
    # ``duration_min`` from params and rely on ``base_duration_min``.
    if slot.jitter_min and slot.base_duration_min is not None:
        duration = slot.base_duration_min
        if rng is not None:
            duration += rng.randint(-slot.jitter_min, slot.jitter_min)
        call_kwargs["duration_min"] = duration

    constructor = ARCHETYPE_DISPATCH.get(archetype_name)
    if constructor is None:
        raise ValueError(f"unknown archetype in template: {archetype_name!r}")

    workout = constructor(**call_kwargs)
    return _stamp(
        workout,
        template_name=template_name,
        week_number=week_number,
        target_tss=target_tss,
        seed=seed,
        variant=archetype_name,
    )


def _stamp(
    workout: WorkoutSpec,
    *,
    template_name: str,
    week_number: int,
    target_tss: int,
    seed: int | None,
    variant: str,
) -> WorkoutSpec:
    generator = dict(workout.generator)
    generator["generator_version"] = PLAN_EXPANDER_VERSION
    generator["template"] = template_name
    generator["week_number"] = week_number
    generator["target_tss"] = target_tss
    generator["seed"] = seed
    generator["variant"] = variant
    return replace(workout, generator=generator)
