"""Plan templates as pure Python data structures.

A template is a list of weeks; each week is seven day-slots (Mon..Sun). A
day-slot names an archetype and the keyword arguments to call it with. Quality
days may offer several *variants* (alternative archetypes) that the expander
rotates between under a seed; easy/long days may carry a duration ``jitter_min``
so the expander can vary their length by ``+/- jitter_min`` minutes.

This module contains data only — no I/O, no randomness, no archetype calls. The
expander (:mod:`coachctl.plan_expander`) consumes these structures and produces
``WorkoutSpec`` objects.

Conventions
-----------
* ``days`` always has exactly seven entries, ordered Monday..Sunday.
* ``DaySlot.archetype`` is the *base* archetype name (the one chosen when
  ``seed is None``). It must be a key in :data:`ARCHETYPE_DISPATCH` in the
  expander.
* ``DaySlot.params`` are the archetype call kwargs *minus* ``date`` (and minus
  ``duration_min`` when ``jitter_min`` is set — the expander supplies the
  jittered duration). ``title`` is included so generated sessions get a stable
  name on new dates.
* ``DaySlot.variants`` is an ordered tuple of alternative ``(archetype, params)``
  pairs. The base slot (``archetype`` + ``params``) is always variant index 0;
  ``variants`` lists the *additional* choices (index 1..N). Empty means the slot
  is fixed.
* ``WeekTemplate.target_tss`` is hardcoded per the design (no ramp engine).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ── Data model ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DaySlot:
    """One day of a week template.

    ``archetype``/``params`` is the base (seed=None) choice. ``variants`` lists
    additional ``(archetype_name, params)`` alternatives the expander may rotate
    to under a seed. ``jitter_min`` (easy/long days only) lets the expander vary
    the session duration by ``+/- jitter_min`` minutes; when set, ``params`` must
    NOT include ``duration_min`` (the expander injects ``base_duration_min`` +/-
    jitter). When ``jitter_min`` is 0, ``params`` carries the duration directly.
    """

    archetype: str
    params: dict[str, Any] = field(default_factory=dict)
    variants: tuple[tuple[str, dict[str, Any]], ...] = ()
    jitter_min: int = 0
    base_duration_min: int | None = None

    def all_choices(self) -> tuple[tuple[str, dict[str, Any]], ...]:
        """Return the full ordered choice list: base first, then variants."""
        return ((self.archetype, self.params), *self.variants)


@dataclass(frozen=True)
class WeekTemplate:
    """One week: a hardcoded TSS target and seven day-slots (Mon..Sun)."""

    target_tss: int
    days: tuple[DaySlot, ...]

    def __post_init__(self) -> None:
        if len(self.days) != 7:
            raise ValueError(
                f"WeekTemplate.days must have exactly 7 entries, got {len(self.days)}"
            )


@dataclass(frozen=True)
class PlanTemplate:
    """A named plan: an ordered list of week templates."""

    name: str
    weeks: tuple[WeekTemplate, ...]

    def __post_init__(self) -> None:
        if not self.weeks:
            raise ValueError("PlanTemplate.weeks must not be empty")


# ── Reusable slot builders ───────────────────────────────────────────────────


def _easy_run(
    duration_min: int, hr_cap: int, *, estimated_tss: float, jitter_min: int = 5
) -> DaySlot:
    return DaySlot(
        archetype="easy_run",
        params={
            "hr_cap": hr_cap,
            "sport": "run",
            "terrain": "road",
            "title": f"{duration_min}min easy run",
            "estimated_tss": estimated_tss,
        },
        jitter_min=jitter_min,
        base_duration_min=duration_min,
    )


def _z2_ride(duration_min: int, *, estimated_tss: float, title: str | None = None) -> DaySlot:
    return DaySlot(
        archetype="z2_ride",
        params={
            "duration_min": duration_min,
            "estimated_tss": estimated_tss,
            "title": title or f"{duration_min}min Z2 ride",
        },
    )


def _rest() -> DaySlot:
    return DaySlot(archetype="rest_day", params={"title": "Rest"})


def _quality_day() -> DaySlot:
    """Wednesday quality session with a rotatable variant pool.

    Base (seed=None) is ``cruise_intervals``; under a seed the expander may
    rotate to ``ladder_intervals`` or ``mona_fartlek``. All three target ~70min
    and similar load so the weekly TSS stays comparable regardless of choice.
    """
    return DaySlot(
        archetype="cruise_intervals",
        params={
            "title": "Cruise intervals 5x1km",
            "duration_min": 70,
            "reps": 5,
            "rep_distance_km": 1.0,
            "float_distance_km": 0.2,
            "pace_range_sec_per_km": (248, 252),
            "estimated_tss": 75.0,
        },
        variants=(
            (
                "ladder_intervals",
                {
                    "title": "Threshold ladder 3-4-5-4-3",
                    "duration_min": 70,
                    "rungs_min": (3, 4, 5, 4, 3),
                    "pace_range_sec_per_km": (248, 252),
                    "recovery_min": 2.0,
                    "estimated_tss": 75.0,
                },
            ),
            (
                "mona_fartlek",
                {
                    "title": "Mona fartlek",
                    "duration_min": 70,
                    "estimated_tss": 75.0,
                },
            ),
        ),
    )


def _progressive_long_run(
    duration_min: int,
    *,
    easy_duration_min: int,
    finish_blocks: int,
    finish_block_min: int,
    jitter_min: int = 5,
) -> DaySlot:
    return DaySlot(
        archetype="progressive_long_run",
        params={
            "title": f"{duration_min}min progressive long run",
            "estimated_tss": 95.0,
            "easy_duration_min": easy_duration_min,
            "finish_blocks": finish_blocks,
            "finish_block_min": finish_block_min,
        },
        jitter_min=jitter_min,
        base_duration_min=duration_min,
    )


# ── Templates ────────────────────────────────────────────────────────────────


def _half_marathon_build_week() -> WeekTemplate:
    """Mirror of the proven half-marathon build week shape.

    Mon easy (jitter) | Tue Z2 ride | Wed quality (rotatable) | Thu easy (jitter)
    | Fri rest | Sat progressive long run (jitter) | Sun Z2 recovery ride.
    """
    return WeekTemplate(
        target_tss=400,
        days=(
            _easy_run(55, hr_cap=152, estimated_tss=45.0),  # Mon
            _z2_ride(90, estimated_tss=55.0, title="90min Z2 ride + cadence work"),  # Tue
            _quality_day(),  # Wed (~75 TSS)
            _easy_run(50, hr_cap=152, estimated_tss=40.0),  # Thu
            _rest(),  # Fri
            _progressive_long_run(  # Sat (~95 TSS)
                105,
                easy_duration_min=70,
                finish_blocks=3,
                finish_block_min=10,
            ),
            _z2_ride(70, estimated_tss=40.0, title="70min Z2 recovery ride"),  # Sun
        ),
    )


HALF_MARATHON_BUILD = PlanTemplate(
    name="half_marathon_build",
    weeks=(
        _half_marathon_build_week(),
        _half_marathon_build_week(),
        _half_marathon_build_week(),
        _half_marathon_build_week(),
    ),
)


# ── Registry ─────────────────────────────────────────────────────────────────

TEMPLATES: dict[str, PlanTemplate] = {
    "half_marathon_build": HALF_MARATHON_BUILD,
}


def get_template(name: str) -> PlanTemplate | None:
    """Return the template registered under ``name`` (or ``None``)."""
    return TEMPLATES.get(name)
