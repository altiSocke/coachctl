"""Preview generated workouts against existing calendar events.

This module is intentionally read-only. It converts structured workouts into
``Event`` objects and decides what would happen if they were applied later.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Literal

from .events import (
    KIND_RACE,
    KIND_TRAINING,
    STATUS_CANCELLED,
    STATUS_COMPLETED,
    Event,
    get_calendar,
    get_event,
)
from .workout_generators import (
    generate_half_marathon_build_week,
    generate_post_trail_race_week,
    generate_trail_race_week,
)
from .workouts import WorkoutSpec, workout_to_event

PreviewAction = Literal["create", "update", "match", "skip", "cancel"]


@dataclass(frozen=True)
class WorkoutEventPreview:
    date: str
    slug: str
    target_slug: str
    action: PreviewAction
    reason: str
    existing: Event | None
    generated: Event | None
    field_diffs: dict[str, tuple[Any, Any]]


@dataclass(frozen=True)
class WorkoutPreviewResult:
    race_slug: str
    race_name: str
    window_start: str
    window_end: str
    previews: list[WorkoutEventPreview]
    error: str | None = None


def workouts_to_events(
    workouts: list[WorkoutSpec],
    *,
    slug_prefix: str,
    plan_id: int | None = None,
    week_number: int | None = None,
) -> list[Event]:
    """Convert workouts to deterministic generated training events."""
    return [
        workout_to_event(
            workout,
            slug=f"{slug_prefix}-{workout.date}-{_slugify(workout.archetype)}",
            plan_id=plan_id,
            week_number=week_number,
        )
        for workout in workouts
    ]


def preview_workout_events(
    generated: list[Event],
    existing: list[Event],
) -> list[WorkoutEventPreview]:
    """Compare generated events to existing events without writing anything."""
    existing_training = [event for event in existing if event.kind == KIND_TRAINING]
    by_slug = {event.slug: event for event in existing_training}
    by_date: dict[str, list[Event]] = {}
    for event in existing_training:
        by_date.setdefault(event.date, []).append(event)

    previews: list[WorkoutEventPreview] = []
    for event in generated:
        match = by_slug.get(event.slug)
        if match is None:
            same_date = by_date.get(event.date, [])
            if len(same_date) > 1:
                previews.append(
                    _preview(
                        event,
                        action="skip",
                        reason="ambiguous_existing_events",
                        existing=None,
                    )
                )
                continue
            match = same_date[0] if same_date else None

        if match is None:
            previews.append(_preview(event, action="create", reason="no_existing_event"))
            continue

        if match.status == STATUS_COMPLETED:
            previews.append(
                _preview(event, action="skip", reason="existing_completed", existing=match)
            )
            continue

        if match.payload.get("locked") is True:
            previews.append(_preview(event, action="skip", reason="existing_locked", existing=match))
            continue

        diffs = _event_diffs(match, event)
        if diffs:
            previews.append(
                _preview(
                    event,
                    action="update",
                    reason="fields_differ",
                    existing=match,
                    field_diffs=diffs,
                )
            )
        else:
            previews.append(
                _preview(event, action="match", reason="no_changes", existing=match, field_diffs={})
            )

    return previews


def preview_trail_race_week_from_db(
    *,
    race_slug: str,
    start_date: str,
    slug_prefix: str | None = None,
    plan_id: int | None = None,
) -> WorkoutPreviewResult:
    """Build a read-only trail race-week preview from the events table."""
    race = get_event(race_slug)
    if race is None:
        return WorkoutPreviewResult(
            race_slug=race_slug,
            race_name="",
            window_start=start_date,
            window_end=start_date,
            previews=[],
            error="race_not_found",
        )
    if race.kind != KIND_RACE:
        return WorkoutPreviewResult(
            race_slug=race_slug,
            race_name=race.name,
            window_start=start_date,
            window_end=start_date,
            previews=[],
            error="event_is_not_race",
        )

    from datetime import date, timedelta

    window_end = (date.fromisoformat(race.date) - timedelta(days=1)).isoformat()
    prefix = slug_prefix or _default_slug_prefix(race_slug)
    workouts = generate_trail_race_week(
        race_date=race.date,
        race_name=race.name,
        start_date=start_date,
        simulation_title=f"90min trail run - {race.name.split()[-1]} race simulation (05:30)",
        start_time="05:30",
    )
    generated = workouts_to_events(workouts, slug_prefix=prefix, plan_id=plan_id)
    existing = get_calendar(start_date, window_end, kinds=[KIND_TRAINING])
    previews = preview_workout_events(generated, existing)
    return WorkoutPreviewResult(
        race_slug=race_slug,
        race_name=race.name,
        window_start=start_date,
        window_end=window_end,
        previews=previews,
    )


def preview_post_trail_race_week_from_db(
    *,
    race_slug: str,
    start_date: str,
    slug_prefix: str | None = None,
    plan_id: int | None = None,
) -> WorkoutPreviewResult:
    """Build a read-only post-trail-race week preview from the events table."""
    race = get_event(race_slug)
    if race is None:
        return WorkoutPreviewResult(
            race_slug=race_slug,
            race_name="",
            window_start=start_date,
            window_end=start_date,
            previews=[],
            error="race_not_found",
        )
    if race.kind != KIND_RACE:
        return WorkoutPreviewResult(
            race_slug=race_slug,
            race_name=race.name,
            window_start=start_date,
            window_end=start_date,
            previews=[],
            error="event_is_not_race",
        )

    from datetime import date, timedelta

    window_end = (date.fromisoformat(race.date) + timedelta(days=8)).isoformat()
    prefix = slug_prefix or f"{_default_slug_prefix(race_slug)}-post"
    workouts = generate_post_trail_race_week(
        race_date=race.date,
        race_name=race.name,
        start_date=start_date,
    )
    generated = workouts_to_events(workouts, slug_prefix=prefix, plan_id=plan_id)
    existing = get_calendar(start_date, window_end, kinds=[KIND_TRAINING])
    previews = _preview_post_race_events(generated, existing)
    return WorkoutPreviewResult(
        race_slug=race_slug,
        race_name=race.name,
        window_start=start_date,
        window_end=window_end,
        previews=previews,
    )


def preview_half_marathon_week_from_db(
    *,
    start_date: str,
    target_tss: int,
    phase: str,
    freshness: str = "normal",
    slug_prefix: str | None = None,
    plan_id: int | None = None,
) -> WorkoutPreviewResult:
    """Build a read-only half-marathon training week preview from the events table."""
    from datetime import date, timedelta

    start = date.fromisoformat(start_date)
    window_end = (start + timedelta(days=6)).isoformat()
    prefix = slug_prefix or "hm-week"
    try:
        workouts = generate_half_marathon_build_week(
            week_start=start_date,
            target_tss=target_tss,
            phase=phase,
            freshness=freshness,
        )
    except ValueError as exc:
        return WorkoutPreviewResult(
            race_slug="",
            race_name="Half-marathon build week",
            window_start=start_date,
            window_end=window_end,
            previews=[],
            error=str(exc),
        )
    generated = workouts_to_events(workouts, slug_prefix=prefix, plan_id=plan_id)
    existing = get_calendar(start_date, window_end, kinds=[KIND_TRAINING])
    previews = _preview_ignore_strength_events(generated, existing)
    return WorkoutPreviewResult(
        race_slug="",
        race_name="Half-marathon build week",
        window_start=start_date,
        window_end=window_end,
        previews=previews,
    )


def _preview_ignore_strength_events(
    generated: list[Event],
    existing: list[Event],
) -> list[WorkoutEventPreview]:
    """Preview generated endurance sessions while leaving strength untouched."""
    non_strength = [event for event in existing if not _is_strength_event(event)]
    return preview_workout_events(generated, non_strength)


def _preview_post_race_events(
    generated: list[Event],
    existing: list[Event],
) -> list[WorkoutEventPreview]:
    """Preview post-race events, cancelling same-day strength where needed."""
    existing_training = [
        event
        for event in existing
        if event.kind == KIND_TRAINING
        and not (_is_strength_event(event) and event.status == STATUS_CANCELLED)
    ]
    out: list[WorkoutEventPreview] = []
    for event in generated:
        same_date = [e for e in existing_training if e.date == event.date]
        if len(same_date) <= 1:
            out.extend(preview_workout_events([event], existing_training))
            continue

        non_strength = [e for e in same_date if not _is_strength_event(e)]
        strength = [e for e in same_date if _is_strength_event(e)]
        if len(non_strength) == 1 and strength:
            out.extend(preview_workout_events([event], [non_strength[0]]))
            for existing_strength in strength:
                out.append(
                    WorkoutEventPreview(
                        date=existing_strength.date,
                        slug=existing_strength.slug,
                        target_slug=existing_strength.slug,
                        action="cancel",
                        reason="superseded_by_post_race_generator",
                        existing=existing_strength,
                        generated=None,
                        field_diffs={"status": (existing_strength.status, "cancelled")},
                    )
                )
            continue
        out.extend(preview_workout_events([event], existing_training))
    return out


def preview_sessions_from_db(
    *,
    mode: str,
    race_slug: str | None,
    start_date: str,
    slug_prefix: str | None = None,
    plan_id: int | None = None,
    target_tss: int | None = None,
    phase: str | None = None,
    freshness: str = "normal",
) -> WorkoutPreviewResult:
    """Dispatch session preview generation by mode."""
    if mode == "race-week":
        if not race_slug:
            return WorkoutPreviewResult(
                race_slug="",
                race_name="",
                window_start=start_date,
                window_end=start_date,
                previews=[],
                error="race_required",
            )
        return preview_trail_race_week_from_db(
            race_slug=race_slug,
            start_date=start_date,
            slug_prefix=slug_prefix,
            plan_id=plan_id,
        )
    if mode == "post-race":
        if not race_slug:
            return WorkoutPreviewResult(
                race_slug="",
                race_name="",
                window_start=start_date,
                window_end=start_date,
                previews=[],
                error="race_required",
            )
        return preview_post_trail_race_week_from_db(
            race_slug=race_slug,
            start_date=start_date,
            slug_prefix=slug_prefix,
            plan_id=plan_id,
        )
    if mode == "half-marathon-week":
        if target_tss is None:
            return WorkoutPreviewResult(
                race_slug="",
                race_name="Half-marathon build week",
                window_start=start_date,
                window_end=start_date,
                previews=[],
                error="target_tss_required",
            )
        if not phase:
            return WorkoutPreviewResult(
                race_slug="",
                race_name="Half-marathon build week",
                window_start=start_date,
                window_end=start_date,
                previews=[],
                error="phase_required",
            )
        return preview_half_marathon_week_from_db(
            start_date=start_date,
            target_tss=target_tss,
            phase=phase,
            freshness=freshness,
            slug_prefix=slug_prefix,
            plan_id=plan_id,
        )
    return WorkoutPreviewResult(
        race_slug=race_slug,
        race_name="",
        window_start=start_date,
        window_end=start_date,
        previews=[],
        error="unsupported_mode",
    )


def format_preview_text(
    *,
    race_name: str,
    window_start: str,
    window_end: str,
    previews: list[WorkoutEventPreview],
) -> str:
    """Format a compact human-readable preview."""
    lines = [
        f"Preview: {race_name}".rstrip(),
        f"Window: {window_start} -> {window_end}",
        "",
    ]
    for item in previews:
        generated = item.generated
        existing = item.existing
        archetype = ""
        if generated and isinstance(generated.payload.get("workout"), dict):
            archetype = generated.payload["workout"].get("archetype", "")
        header = f"{item.date} {item.action.upper()}"
        if archetype:
            header += f"  {archetype}"
        lines.append(header)
        if existing:
            lines.append(f"  target: {item.target_slug}")
            lines.append(f"  existing: {existing.slug} | {existing.name}")
        elif generated:
            lines.append(f"  target: {item.target_slug}")
        if generated:
            lines.append(f"  generated: {generated.slug} | {generated.name}")
        if item.field_diffs:
            lines.append(f"  diffs: {', '.join(item.field_diffs)}")
        if item.action == "skip":
            lines.append(f"  reason: {item.reason}")
        if item.action == "cancel":
            lines.append(f"  reason: {item.reason}")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_preview_json(previews: list[WorkoutEventPreview]) -> str:
    """Serialize preview rows without full payloads by default."""
    rows = []
    for item in previews:
        rows.append(
            {
                "date": item.date,
                "slug": item.slug,
                "target_slug": item.target_slug,
                "action": item.action,
                "reason": item.reason,
                "existing_slug": item.existing.slug if item.existing else None,
                "existing_name": item.existing.name if item.existing else None,
                "generated_slug": item.generated.slug if item.generated else None,
                "generated_name": item.generated.name if item.generated else None,
                "diff_fields": list(item.field_diffs),
            }
        )
    return json.dumps(rows, indent=2)


def _preview(
    generated: Event,
    *,
    action: PreviewAction,
    reason: str,
    existing: Event | None = None,
    field_diffs: dict[str, tuple[Any, Any]] | None = None,
) -> WorkoutEventPreview:
    return WorkoutEventPreview(
        date=generated.date,
        slug=generated.slug,
        target_slug=existing.slug if existing else generated.slug,
        action=action,
        reason=reason,
        existing=existing,
        generated=generated,
        field_diffs=field_diffs or {},
    )


def _event_diffs(existing: Event, generated: Event) -> dict[str, tuple[Any, Any]]:
    fields = (
        "date",
        "name",
        "duration_min",
        "summary",
        "estimated_tss",
        "status",
        "payload",
        "plan_id",
    )
    diffs: dict[str, tuple[Any, Any]] = {}
    for field in fields:
        old = getattr(existing, field)
        new = getattr(generated, field)
        if field == "plan_id" and new is None:
            continue
        if old != new:
            diffs[field] = (old, new)
    return diffs


def _slugify(value: str) -> str:
    return value.replace("_", "-").replace(" ", "-").lower()


def _default_slug_prefix(race_slug: str) -> str:
    parts = race_slug.split("-")
    if len(parts) > 3 and all(part.isdigit() for part in parts[:3]):
        return "-".join(parts[3:])
    return race_slug


def _is_strength_event(event: Event) -> bool:
    text = f"{event.slug} {event.name} {event.summary or ''}".lower()
    return "strength" in text
