"""Structured workout schema and deterministic rendering.

This module is the first step away from free-text session creation.  A
``WorkoutSpec`` is the canonical representation of a planned training session;
human-facing text is rendered from it, not parsed back into it.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from .events import Event, KIND_TRAINING, STATUS_PLANNED

WORKOUT_SCHEMA = "workout_spec.v1"

Sport = Literal["run", "trail_run", "ride", "strength", "rest"]
Intensity = Literal[
    "rest",
    "recovery",
    "easy",
    "moderate",
    "tempo",
    "threshold",
    "vo2max",
    "anaerobic",
    "race",
]
Priority = Literal["key", "support", "optional", "recovery"]
StepKind = Literal[
    "warmup",
    "main",
    "interval",
    "recovery",
    "cooldown",
    "stride",
    "drill",
    "strength",
    "fuel",
    "note",
]

VALID_SPORTS = {"run", "trail_run", "ride", "strength", "rest"}
VALID_INTENSITIES = {
    "rest",
    "recovery",
    "easy",
    "moderate",
    "tempo",
    "threshold",
    "vo2max",
    "anaerobic",
    "race",
}
VALID_PRIORITIES = {"key", "support", "optional", "recovery"}
VALID_STEP_KINDS = {
    "warmup",
    "main",
    "interval",
    "recovery",
    "cooldown",
    "stride",
    "drill",
    "strength",
    "fuel",
    "note",
}


@dataclass(frozen=True)
class WorkoutStep:
    """One structured component of a workout."""

    kind: StepKind
    duration_min: float | None = None
    reps: int | None = None
    repeat_duration_min: float | None = None
    recovery_min: float | None = None
    target: dict[str, Any] = field(default_factory=dict)
    cue: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in VALID_STEP_KINDS:
            raise ValueError(f"unknown step kind: {self.kind}")
        for name, value in (
            ("duration_min", self.duration_min),
            ("repeat_duration_min", self.repeat_duration_min),
            ("recovery_min", self.recovery_min),
        ):
            if value is not None and value < 0:
                raise ValueError(f"{name} must be >= 0")
        if self.reps is not None and self.reps < 1:
            raise ValueError("reps must be >= 1")


@dataclass(frozen=True)
class WorkoutSpec:
    """Canonical structured workout/session representation."""

    date: str
    sport: Sport
    archetype: str
    title: str
    duration_min: int | None
    intensity: Intensity
    priority: Priority
    estimated_tss: float | None = None
    steps: list[WorkoutStep] = field(default_factory=list)
    constraints: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    generator: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.sport not in VALID_SPORTS:
            raise ValueError(f"unknown sport: {self.sport}")
        if self.intensity not in VALID_INTENSITIES:
            raise ValueError(f"unknown intensity: {self.intensity}")
        if self.priority not in VALID_PRIORITIES:
            raise ValueError(f"unknown priority: {self.priority}")
        if self.duration_min is not None and self.duration_min < 0:
            raise ValueError("duration_min must be >= 0")
        if self.estimated_tss is not None and self.estimated_tss < 0:
            raise ValueError("estimated_tss must be >= 0")
        if not self.date:
            raise ValueError("date is required")
        if not self.archetype:
            raise ValueError("archetype is required")
        if not self.title:
            raise ValueError("title is required")


def workout_to_payload(workout: WorkoutSpec, **extra: Any) -> dict[str, Any]:
    """Serialize a workout into the payload shape stored on events."""
    payload: dict[str, Any] = {
        "schema": WORKOUT_SCHEMA,
        "workout": asdict(workout),
    }
    payload.update(extra)
    return payload


def workout_from_payload(payload: dict[str, Any]) -> WorkoutSpec:
    """Deserialize a ``workout_spec.v1`` payload."""
    schema = payload.get("schema")
    if schema != WORKOUT_SCHEMA:
        raise ValueError(f"unsupported workout schema: {schema}")
    raw = payload.get("workout")
    if not isinstance(raw, dict):
        raise ValueError("payload missing workout object")
    steps = [WorkoutStep(**step) for step in raw.get("steps", [])]
    return WorkoutSpec(
        date=raw["date"],
        sport=raw["sport"],
        archetype=raw["archetype"],
        title=raw["title"],
        duration_min=raw.get("duration_min"),
        intensity=raw["intensity"],
        priority=raw["priority"],
        estimated_tss=raw.get("estimated_tss"),
        steps=steps,
        constraints=raw.get("constraints", {}),
        notes=raw.get("notes", []),
        generator=raw.get("generator", {}),
    )


def render_workout_summary(workout: WorkoutSpec) -> str:
    """Render stable human-facing workout text from structured data."""
    parts = [workout.title]
    step_text = [_render_step(step) for step in workout.steps]
    step_text = [text for text in step_text if text]
    if step_text:
        parts.append("; ".join(step_text))

    constraint_text = _render_constraints(workout.constraints)
    if constraint_text:
        parts.append(constraint_text)
    if workout.notes:
        parts.extend(note.strip().rstrip(".") for note in workout.notes if note.strip())

    return ". ".join(parts).rstrip(".") + "."


def workout_to_event(
    workout: WorkoutSpec,
    slug: str,
    plan_id: int | None = None,
    week_number: int | None = None,
) -> Event:
    """Convert a structured workout into the existing calendar event model."""
    extra: dict[str, Any] = {}
    if week_number is not None:
        extra["week_number"] = week_number
    return Event(
        slug=slug,
        kind=KIND_TRAINING,
        date=workout.date,
        duration_min=workout.duration_min,
        name=workout.title,
        summary=render_workout_summary(workout),
        estimated_tss=workout.estimated_tss,
        status=STATUS_PLANNED,
        payload=workout_to_payload(workout, **extra),
        plan_id=plan_id,
    )


def _render_step(step: WorkoutStep) -> str:
    if step.kind == "note" and step.cue:
        return step.cue.strip().rstrip(".")
    base = _render_step_base(step)
    details = _render_target(step.target)
    if step.cue:
        details.append(step.cue.strip().rstrip("."))
    if not details:
        return base
    return f"{base}, {', '.join(details)}"


def _render_step_base(step: WorkoutStep) -> str:
    if step.reps is not None and step.repeat_duration_min is not None:
        text = f"{step.reps}x{_fmt_num(step.repeat_duration_min)}min {step.kind}"
    elif step.duration_min is not None:
        text = f"{_fmt_num(step.duration_min)}min {step.kind}"
    else:
        text = step.kind
    if step.recovery_min is not None:
        text += f", {_fmt_num(step.recovery_min)}min recovery"
    return text


def _render_target(target: dict[str, Any]) -> list[str]:
    out: list[str] = []
    if "hr_cap" in target:
        out.append(f"HR cap {target['hr_cap']}")
    if "hr_range" in target:
        out.append(f"HR {_fmt_range(target['hr_range'])}")
    if "rpe" in target:
        out.append(f"RPE {target['rpe']}")
    if "rpe_max" in target:
        out.append(f"RPE max {target['rpe_max']}")
    if "terrain" in target:
        out.append(f"terrain {_fmt_label(target['terrain'])}")
    if "cadence_spm" in target:
        out.append(f"cadence {_fmt_range(target['cadence_spm'])} spm")
    if "elevation_loss_m" in target:
        out.append(f"descent {_fmt_range(target['elevation_loss_m'])}m")
    if "effort" in target:
        out.append(f"effort {_fmt_label(target['effort'])}")
    return out


def _render_constraints(constraints: dict[str, Any]) -> str:
    out: list[str] = []
    if "start_time" in constraints:
        out.append(f"Start {constraints['start_time']}")
    if "fuel_carbs_g_per_hr" in constraints:
        out.append(f"Fuel {_fmt_range(constraints['fuel_carbs_g_per_hr'])}g carbs/hr")
    if "elevation_gain_target_m" in constraints:
        out.append(f"Elevation gain target {_fmt_range(constraints['elevation_gain_target_m'])}m")
    if "route_options" in constraints:
        values = constraints["route_options"]
        if isinstance(values, list) and values:
            out.append("Route: " + " or ".join(str(v) for v in values))
    if "optional_alternative" in constraints:
        out.append(f"Optional: {constraints['optional_alternative']}")
    if "max_elevation_gain_m" in constraints:
        out.append(f"Max elevation gain {constraints['max_elevation_gain_m']}m")
    if "stop_if" in constraints:
        values = constraints["stop_if"]
        if isinstance(values, list) and values:
            out.append("Stop if " + ", ".join(_fmt_label(v) for v in values))
    return ". ".join(out)


def _fmt_range(value: Any) -> str:
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return f"{value[0]}-{value[1]}"
    return str(value)


def _fmt_num(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)


def _fmt_label(value: Any) -> str:
    return str(value).replace("_", " ")
