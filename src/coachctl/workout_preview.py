"""Preview generated workouts against existing calendar events.

This module is intentionally read-only. It converts structured workouts into
``Event`` objects and decides what would happen if they were applied later.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
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
    summary: dict[str, Any] | None = None


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
    create_rest_days: bool = False,
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
    suppressed_rest_creates = 0
    if not create_rest_days:
        kept: list[WorkoutEventPreview] = []
        for item in previews:
            if item.action == "create" and item.generated and _is_rest_event(item.generated):
                suppressed_rest_creates += 1
                continue
            kept.append(item)
        previews = kept
    return WorkoutPreviewResult(
        race_slug="",
        race_name="Half-marathon build week",
        window_start=start_date,
        window_end=window_end,
        previews=previews,
        summary=_preview_summary(
            target_tss=target_tss,
            generated=generated,
            existing=existing,
            previews=previews,
            suppressed_rest_creates=suppressed_rest_creates,
        ),
    )


def _preview_ignore_strength_events(
    generated: list[Event],
    existing: list[Event],
) -> list[WorkoutEventPreview]:
    """Preview generated endurance sessions while leaving strength untouched."""
    non_strength = [event for event in existing if not _is_strength_event(event)]
    return preview_workout_events(generated, non_strength)


def preview_plan_from_db(
    *,
    template_name: str,
    start_date: str,
    weeks: int,
    seed: int | None = None,
    slug_prefix: str | None = None,
    plan_id: int | None = None,
    create_rest_days: bool = False,
) -> WorkoutPreviewResult:
    """Preview an expanded multi-week plan template against the real calendar.

    Reconcile semantics (reuse of the single-week machinery):

    * Existing endurance sessions on a generated day are updated (names
      preserved) or matched.
    * Strength sessions are ignored (never created/updated/overwritten) via
      :func:`_preview_ignore_strength_events`.
    * Races block training on their date: any generated session that lands on a
      race day is dropped here (and counted as ``suppressed_race_days``), so the
      engine never proposes creating/updating training there.
    * Two or more existing endurance sessions on the same day yield a ``skip``
      (ambiguous) row from the underlying engine.
    * Rest-day creates are suppressed unless ``create_rest_days`` is set.

    The summary's ``target_tss`` is the sum of the expanded weeks' hardcoded
    per-week targets.
    """
    from datetime import date, timedelta

    from .plan_expander import expand_template
    from .plan_templates import get_template

    template = get_template(template_name)
    start = date.fromisoformat(start_date)
    prefix = slug_prefix or "plan"

    if template is None:
        return WorkoutPreviewResult(
            race_slug="",
            race_name=f"Plan: {template_name}",
            window_start=start_date,
            window_end=start_date,
            previews=[],
            error="unknown_template",
        )

    available = len(template.weeks)
    if weeks < 1 or weeks > available:
        return WorkoutPreviewResult(
            race_slug="",
            race_name=f"Plan: {template.name}",
            window_start=start_date,
            window_end=start_date,
            previews=[],
            error="weeks_out_of_range",
        )

    window_end = (start + timedelta(days=7 * weeks - 1)).isoformat()

    # Expand only the requested number of weeks by slicing the template, then
    # laying out dates from start_date.
    trimmed = replace(template, weeks=template.weeks[:weeks])
    workouts = expand_template(trimmed, start_date, seed=seed)
    generated = workouts_to_events(workouts, slug_prefix=prefix, plan_id=plan_id)

    # Load training AND races over the window. Races block training on their
    # date: drop any generated session that lands on a race day so the engine
    # never proposes creating/updating training there. (get_calendar's own
    # conflict resolution only fires when races are in the returned set, which
    # is why we must request them explicitly and filter generated here.)
    calendar = get_calendar(start_date, window_end, kinds=[KIND_TRAINING, KIND_RACE])
    race_dates = {
        event.date
        for event in calendar
        if event.kind == KIND_RACE and event.status != STATUS_CANCELLED
    }
    existing = [event for event in calendar if event.kind == KIND_TRAINING]

    suppressed_race_days = 0
    if race_dates:
        kept_generated: list[Event] = []
        for event in generated:
            if event.date in race_dates:
                suppressed_race_days += 1
                continue
            kept_generated.append(event)
        generated = kept_generated

    previews = _preview_ignore_strength_events(generated, existing)

    suppressed_rest_creates = 0
    if not create_rest_days:
        kept: list[WorkoutEventPreview] = []
        for item in previews:
            if item.action == "create" and item.generated and _is_rest_event(item.generated):
                suppressed_rest_creates += 1
                continue
            kept.append(item)
        previews = kept

    target_tss = sum(week.target_tss for week in trimmed.weeks)
    return WorkoutPreviewResult(
        race_slug="",
        race_name=f"Plan: {template.name}",
        window_start=start_date,
        window_end=window_end,
        previews=previews,
        summary=_preview_summary(
            target_tss=target_tss,
            generated=generated,
            existing=existing,
            previews=previews,
            suppressed_rest_creates=suppressed_rest_creates,
            extra={"suppressed_race_days": suppressed_race_days},
        ),
    )


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
    create_rest_days: bool = False,
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
            create_rest_days=create_rest_days,
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
    summary: dict[str, Any] | None = None,
) -> str:
    """Format a compact human-readable preview."""
    lines = [
        f"Preview: {race_name}".rstrip(),
        f"Window: {window_start} -> {window_end}",
        "",
    ]
    if summary:
        lines.extend(_format_summary_lines(summary))
        lines.append("")
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


def _format_summary_lines(summary: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    if "target_tss" in summary:
        lines.append(f"Target TSS: {summary['target_tss']}")
    if "generated_tss" in summary:
        lines.append(f"Generated TSS: {summary['generated_tss']:.0f}")
    if "existing_tss" in summary:
        lines.append(f"Existing planned TSS: {summary['existing_tss']:.0f}")
    if "delta_tss" in summary:
        lines.append(f"Delta: {summary['delta_tss']:+.0f}")
    actions = summary.get("actions")
    if isinstance(actions, dict):
        lines.append(
            "Actions: "
            f"{actions.get('create', 0)} create, "
            f"{actions.get('update', 0)} update, "
            f"{actions.get('match', 0)} match, "
            f"{actions.get('skip', 0)} skip, "
            f"{actions.get('cancel', 0)} cancel"
        )
    if "strength_preserved" in summary:
        lines.append(f"Strength preserved: {summary['strength_preserved']}")
    if "suppressed_rest_creates" in summary:
        lines.append(f"Suppressed rest creates: {summary['suppressed_rest_creates']}")
    if "suppressed_race_days" in summary:
        lines.append(f"Suppressed (race day): {summary['suppressed_race_days']}")
    return lines


def _preview_summary(
    *,
    target_tss: int,
    generated: list[Event],
    existing: list[Event],
    previews: list[WorkoutEventPreview],
    suppressed_rest_creates: int,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    generated_tss = sum(float(event.estimated_tss or 0.0) for event in generated)
    existing_tss = sum(
        float(event.estimated_tss or 0.0)
        for event in existing
        if event.status != STATUS_CANCELLED and not _is_strength_event(event)
    )
    actions = {action: 0 for action in ("create", "update", "match", "skip", "cancel")}
    for item in previews:
        actions[item.action] += 1
    strength_preserved = sum(
        1
        for event in existing
        if event.status != STATUS_CANCELLED and _is_strength_event(event)
    )
    summary = {
        "target_tss": target_tss,
        "generated_tss": round(generated_tss, 1),
        "existing_tss": round(existing_tss, 1),
        "delta_tss": round(generated_tss - existing_tss, 1),
        "actions": actions,
        "strength_preserved": strength_preserved,
        "suppressed_rest_creates": suppressed_rest_creates,
    }
    if extra:
        summary.update(extra)
    return summary


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


_NORMALIZED_TEXT_FIELDS = frozenset({"summary"})


def _normalize_text(value: Any) -> Any:
    """Normalize cosmetic text differences before reconcile comparison.

    Maps en/em dashes to ``-`` and ``×`` to ``x``, then collapses and trims
    runs of whitespace. Non-string values pass through unchanged. This makes
    cosmetic-only deltas (typography, spacing) compare equal so they do not
    force ``update`` actions on existing events.
    """
    if not isinstance(value, str):
        return value
    out = value.replace("\u2013", "-").replace("\u2014", "-")  # – —  -> -
    out = out.replace("\u00d7", "x")  # ×    -> x
    return " ".join(out.split())  # collapse + trim whitespace


def _event_diffs(existing: Event, generated: Event) -> dict[str, tuple[Any, Any]]:
    # ``name`` is intentionally excluded: in reconcile mode the existing
    # (human/prior) name is preserved on update (see _apply_update). An
    # author/regenerate path, if added later, owns names itself and must not
    # rely on this exclusion.
    fields = (
        "date",
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
        if field in _NORMALIZED_TEXT_FIELDS:
            if _normalize_text(old) != _normalize_text(new):
                diffs[field] = (old, new)
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


def _is_rest_event(event: Event) -> bool:
    workout = event.payload.get("workout") if isinstance(event.payload, dict) else None
    if isinstance(workout, dict) and workout.get("sport") == "rest":
        return True
    return event.name.strip().lower() == "rest"
