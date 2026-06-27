"""Apply deterministic workout previews to the events table."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Literal

from .events import KIND_TRAINING, STATUS_CANCELLED, STATUS_COMPLETED, Event, get_event, upsert_event
from .workout_preview import (
    WorkoutEventPreview,
    preview_post_trail_race_week_from_db,
    preview_sessions_from_db,
    preview_trail_race_week_from_db,
)

ApplyAction = Literal["created", "updated", "matched", "skipped", "cancelled"]
_UNSET = object()


@dataclass(frozen=True)
class WorkoutApplyRow:
    date: str
    action: ApplyAction
    target_slug: str
    reason: str


@dataclass(frozen=True)
class WorkoutApplyResult:
    race_slug: str = ""
    race_name: str = ""
    window_start: str = ""
    window_end: str = ""
    rows: list[WorkoutApplyRow] | None = None

    @property
    def created(self) -> int:
        return self._count("created")

    @property
    def updated(self) -> int:
        return self._count("updated")

    @property
    def matched(self) -> int:
        return self._count("matched")

    @property
    def skipped(self) -> int:
        return self._count("skipped")

    @property
    def cancelled(self) -> int:
        return self._count("cancelled")

    def _count(self, action: ApplyAction) -> int:
        return sum(1 for row in (self.rows or []) if row.action == action)


def apply_trail_race_week_from_db(
    *,
    race_slug: str,
    start_date: str,
    slug_prefix: str | None = None,
    plan_id: int | None = None,
    allow_skips: bool = False,
) -> WorkoutApplyResult:
    """Re-run preview and apply the current deterministic trail race week."""
    preview = preview_trail_race_week_from_db(
        race_slug=race_slug,
        start_date=start_date,
        slug_prefix=slug_prefix,
        plan_id=plan_id,
    )
    if preview.error:
        raise RuntimeError(preview.error)
    result = apply_workout_previews(preview.previews, allow_skips=allow_skips)
    return WorkoutApplyResult(
        race_slug=preview.race_slug,
        race_name=preview.race_name,
        window_start=preview.window_start,
        window_end=preview.window_end,
        rows=result.rows or [],
    )


def apply_post_trail_race_week_from_db(
    *,
    race_slug: str,
    start_date: str,
    slug_prefix: str | None = None,
    plan_id: int | None = None,
    allow_skips: bool = False,
) -> WorkoutApplyResult:
    """Re-run preview and apply the deterministic post-trail-race week."""
    preview = preview_post_trail_race_week_from_db(
        race_slug=race_slug,
        start_date=start_date,
        slug_prefix=slug_prefix,
        plan_id=plan_id,
    )
    if preview.error:
        raise RuntimeError(preview.error)
    result = apply_workout_previews(preview.previews, allow_skips=allow_skips)
    return WorkoutApplyResult(
        race_slug=preview.race_slug,
        race_name=preview.race_name,
        window_start=preview.window_start,
        window_end=preview.window_end,
        rows=result.rows or [],
    )


def apply_sessions_from_db(
    *,
    mode: str,
    race_slug: str | None,
    start_date: str,
    slug_prefix: str | None = None,
    plan_id: int | None = None,
    allow_skips: bool = False,
    target_tss: int | None = None,
    phase: str | None = None,
    freshness: str = "normal",
) -> WorkoutApplyResult:
    """Dispatch session apply by mode."""
    if mode == "half-marathon-week":
        raise RuntimeError("apply_unsupported_for_half_marathon_week")
    preview = preview_sessions_from_db(
        mode=mode,
        race_slug=race_slug,
        start_date=start_date,
        slug_prefix=slug_prefix,
        plan_id=plan_id,
        target_tss=target_tss,
        phase=phase,
        freshness=freshness,
    )
    if preview.error:
        raise RuntimeError(preview.error)
    result = apply_workout_previews(preview.previews, allow_skips=allow_skips)
    return WorkoutApplyResult(
        race_slug=preview.race_slug,
        race_name=preview.race_name,
        window_start=preview.window_start,
        window_end=preview.window_end,
        rows=result.rows or [],
    )


def apply_plan_from_db(
    *,
    template_name: str,
    start_date: str,
    weeks: int,
    seed: int | None = None,
    slug_prefix: str | None = None,
    plan_id: int | None = None,
    allow_skips: bool = False,
    create_rest_days: bool = False,
) -> WorkoutApplyResult:
    """Apply an expanded plan template, sandbox-validated before touching live.

    Protocol:

    1. In a sandbox (a temp copy of the live DB), preview the plan, apply it,
       then re-preview. The re-preview must contain no ``create``/``update``
       rows — proving the apply is idempotent (it converged). Then ``bake`` in
       the sandbox to prove the payload is serialisable.
    2. Only if the sandbox run succeeds, re-preview against the live DB and apply
       for real.

    Reconcile rules are inherited from :func:`preview_plan_from_db` and
    :func:`apply_workout_previews`: existing names/plan_id/strength are
    preserved, rest days are not created unless ``create_rest_days``, and skips
    are rejected unless ``allow_skips``.
    """
    from .sandbox import sandboxed_db
    from .workout_preview import preview_plan_from_db

    def _preview():
        return preview_plan_from_db(
            template_name=template_name,
            start_date=start_date,
            weeks=weeks,
            seed=seed,
            slug_prefix=slug_prefix,
            plan_id=plan_id,
            create_rest_days=create_rest_days,
        )

    # ── Phase 1: validate in a throwaway copy of the live DB ──────────────────
    with sandboxed_db():
        preview = _preview()
        if preview.error:
            raise RuntimeError(preview.error)
        apply_workout_previews(preview.previews, allow_skips=allow_skips)

        reverify = _preview()
        if reverify.error:
            raise RuntimeError(reverify.error)
        residual = [
            item for item in reverify.previews if item.action in ("create", "update")
        ]
        if residual:
            slugs = ", ".join(sorted(item.target_slug for item in residual))
            raise RuntimeError(f"sandbox_not_converged: {slugs}")

        # Prove the payload bakes cleanly inside the sandbox.
        from .site import bake

        bake()

    # ── Phase 2: replay against the live DB ───────────────────────────────────
    live_preview = _preview()
    if live_preview.error:
        raise RuntimeError(live_preview.error)
    result = apply_workout_previews(live_preview.previews, allow_skips=allow_skips)
    return WorkoutApplyResult(
        race_slug=live_preview.race_slug,
        race_name=live_preview.race_name,
        window_start=live_preview.window_start,
        window_end=live_preview.window_end,
        rows=result.rows or [],
    )


def format_apply_text(result: WorkoutApplyResult) -> str:
    """Format a compact apply result."""
    lines = [
        f"Applied deterministic sessions for {result.race_name}".rstrip(),
        f"Window: {result.window_start} -> {result.window_end}",
        "",
    ]
    for row in result.rows or []:
        lines.append(f"{row.action.upper()} {row.target_slug}")
    lines.extend(
        [
            "",
            "Summary: "
            f"{result.created} created, {result.updated} updated, "
            f"{result.matched} matched, {result.skipped} skipped, "
            f"{result.cancelled} cancelled",
        ]
    )
    return "\n".join(lines).rstrip()


def format_apply_json(result: WorkoutApplyResult) -> str:
    """Serialize apply result as compact JSON."""
    return json.dumps(
        {
            "race_slug": result.race_slug,
            "race_name": result.race_name,
            "window_start": result.window_start,
            "window_end": result.window_end,
            "created": result.created,
            "updated": result.updated,
            "matched": result.matched,
            "skipped": result.skipped,
            "cancelled": result.cancelled,
            "rows": [
                {
                    "date": row.date,
                    "action": row.action,
                    "target_slug": row.target_slug,
                    "reason": row.reason,
                }
                for row in (result.rows or [])
            ],
        },
        indent=2,
    )


def apply_workout_previews(
    previews: list[WorkoutEventPreview],
    *,
    allow_skips: bool = False,
) -> WorkoutApplyResult:
    """Apply preview decisions to the events table."""
    if not allow_skips and any(item.action == "skip" for item in previews):
        raise RuntimeError("preview contains skip actions; use allow_skips to apply partial changes")

    rows: list[WorkoutApplyRow] = []
    for item in previews:
        if item.action == "create":
            _apply_create(item)
            rows.append(
                WorkoutApplyRow(
                    date=item.date,
                    action="created",
                    target_slug=item.target_slug,
                    reason=item.reason,
                )
            )
        elif item.action == "update":
            _apply_update(item)
            rows.append(
                WorkoutApplyRow(
                    date=item.date,
                    action="updated",
                    target_slug=item.target_slug,
                    reason=item.reason,
                )
            )
        elif item.action == "match":
            rows.append(
                WorkoutApplyRow(
                    date=item.date,
                    action="matched",
                    target_slug=item.target_slug,
                    reason=item.reason,
                )
            )
        elif item.action == "skip":
            rows.append(
                WorkoutApplyRow(
                    date=item.date,
                    action="skipped",
                    target_slug=item.target_slug,
                    reason=item.reason,
                )
            )
        elif item.action == "cancel":
            _apply_cancel(item)
            rows.append(
                WorkoutApplyRow(
                    date=item.date,
                    action="cancelled",
                    target_slug=item.target_slug,
                    reason=item.reason,
                )
            )
    return WorkoutApplyResult(rows=rows)


def _apply_create(item: WorkoutEventPreview) -> None:
    generated = _require_generated(item)
    if generated.kind != KIND_TRAINING:
        raise RuntimeError(f"refusing to create non-training event: {generated.slug}")
    if get_event(item.target_slug) is not None:
        raise RuntimeError(f"target slug already exists: {item.target_slug}")
    event = _copy_event(generated, slug=item.target_slug)
    upsert_event(event)


def _apply_update(item: WorkoutEventPreview) -> None:
    generated = _require_generated(item)
    existing = get_event(item.target_slug)
    if existing is None:
        raise RuntimeError(f"update target missing: {item.target_slug}")
    if existing.status == STATUS_COMPLETED:
        raise RuntimeError(f"refusing to update completed event: {item.target_slug}")
    if existing.payload.get("locked") is True:
        raise RuntimeError(f"refusing to update locked event: {item.target_slug}")
    if generated.kind != KIND_TRAINING or existing.kind != KIND_TRAINING:
        raise RuntimeError(f"refusing to update non-training event: {item.target_slug}")

    # Reconcile: preserve the existing (human/prior) name on update. Summary,
    # estimated_tss, duration, status and payload are taken from the generated
    # event. An author/regenerate path, if added later, is generator-owned and
    # must set the name itself rather than relying on this preservation.
    event = _copy_event(
        generated,
        slug=existing.slug,
        name=existing.name,
        plan_id=existing.plan_id if generated.plan_id is None else generated.plan_id,
        activity_id=existing.activity_id,
        notes=existing.notes,
    )
    upsert_event(event)


def _apply_cancel(item: WorkoutEventPreview) -> None:
    existing = get_event(item.target_slug)
    if existing is None:
        raise RuntimeError(f"cancel target missing: {item.target_slug}")
    if existing.status == STATUS_COMPLETED:
        raise RuntimeError(f"refusing to cancel completed event: {item.target_slug}")
    if existing.payload.get("locked") is True:
        raise RuntimeError(f"refusing to cancel locked event: {item.target_slug}")
    event = _copy_event(existing, slug=existing.slug)
    event.status = STATUS_CANCELLED
    upsert_event(event)


def _require_generated(item: WorkoutEventPreview) -> Event:
    if item.generated is None:
        raise RuntimeError(f"preview row has no generated event: {item.target_slug}")
    return item.generated


def _copy_event(
    event: Event,
    *,
    slug: str,
    name: str | object = _UNSET,
    plan_id: int | None | object = _UNSET,
    activity_id: int | None | object = _UNSET,
    notes: str | None | object = _UNSET,
) -> Event:
    return Event(
        slug=slug,
        kind=event.kind,
        date=event.date,
        start_time=event.start_time,
        duration_min=event.duration_min,
        name=event.name if name is _UNSET else name,
        summary=event.summary,
        estimated_tss=event.estimated_tss,
        status=event.status,
        payload=dict(event.payload),
        plan_id=event.plan_id if plan_id is _UNSET else plan_id,
        activity_id=event.activity_id if activity_id is _UNSET else activity_id,
        notes=event.notes if notes is _UNSET else notes,
    )
