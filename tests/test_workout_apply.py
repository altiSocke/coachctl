from __future__ import annotations

import pytest

from coachctl.events import (
    KIND_RACE,
    KIND_TRAINING,
    STATUS_COMPLETED,
    STATUS_PLANNED,
    Event,
    get_event,
    upsert_event,
)
from coachctl.workout_apply import apply_trail_race_week_from_db, apply_workout_previews
from coachctl.workout_preview import preview_workout_events
from coachctl.workout_archetypes import easy_run
from coachctl.workout_preview import workouts_to_events


def _race() -> Event:
    return Event(
        slug="2026-07-04-steinbock",
        kind=KIND_RACE,
        date="2026-07-04",
        name="Bernina Ultraks Steinbock",
    )


def _generated(date: str = "2026-06-29", plan_id: int | None = None) -> Event:
    workout = easy_run(
        date=date,
        duration_min=40,
        hr_cap=155,
        title="40min easy trail run",
        sport="trail_run",
        estimated_tss=35.0,
    )
    return workouts_to_events([workout], slug_prefix="steinbock", plan_id=plan_id)[0]


def test_apply_preview_create_inserts_generated_event(mem_db) -> None:
    generated = _generated()
    previews = preview_workout_events([generated], existing=[])

    result = apply_workout_previews(previews)

    fetched = get_event(generated.slug)
    assert fetched is not None
    assert fetched.name == "40min easy trail run"
    assert fetched.payload["schema"] == "workout_spec.v1"
    assert result.created == 1
    assert result.updated == 0


def test_apply_preview_update_preserves_existing_slug(mem_db) -> None:
    existing = Event(
        slug="legacy-2026-06-29",
        kind=KIND_TRAINING,
        date="2026-06-29",
        name="55min easy Z2 run",
        status=STATUS_PLANNED,
    )
    upsert_event(existing)
    generated = _generated()
    previews = preview_workout_events([generated], [existing])

    result = apply_workout_previews(previews)

    assert get_event(generated.slug) is None
    fetched = get_event(existing.slug)
    assert fetched is not None
    assert fetched.name == generated.name
    assert fetched.slug == existing.slug
    assert fetched.payload["schema"] == "workout_spec.v1"
    assert result.updated == 1


def test_apply_update_preserves_plan_id_when_generated_is_none(mem_db) -> None:
    existing = Event(
        slug="legacy-2026-06-29",
        kind=KIND_TRAINING,
        date="2026-06-29",
        name="55min easy Z2 run",
        status=STATUS_PLANNED,
        plan_id=2,
    )
    upsert_event(existing)
    generated = _generated(plan_id=None)
    previews = preview_workout_events([generated], [existing])

    apply_workout_previews(previews)

    fetched = get_event(existing.slug)
    assert fetched is not None
    assert fetched.plan_id == 2


def test_apply_update_allows_explicit_plan_id_override(mem_db) -> None:
    existing = Event(
        slug="legacy-2026-06-29",
        kind=KIND_TRAINING,
        date="2026-06-29",
        name="55min easy Z2 run",
        status=STATUS_PLANNED,
        plan_id=2,
    )
    upsert_event(existing)
    generated = _generated(plan_id=3)
    previews = preview_workout_events([generated], [existing])

    apply_workout_previews(previews)

    fetched = get_event(existing.slug)
    assert fetched is not None
    assert fetched.plan_id == 3


def test_apply_rejects_skips_by_default(mem_db) -> None:
    generated = _generated()
    existing = Event(
        slug="completed-2026-06-29",
        kind=KIND_TRAINING,
        date="2026-06-29",
        name="Completed",
        status=STATUS_COMPLETED,
    )
    previews = preview_workout_events([generated], [existing])

    with pytest.raises(RuntimeError, match="skip"):
        apply_workout_previews(previews)


def test_apply_allow_skips_does_not_update_completed(mem_db) -> None:
    existing = Event(
        slug="completed-2026-06-29",
        kind=KIND_TRAINING,
        date="2026-06-29",
        name="Completed",
        status=STATUS_COMPLETED,
    )
    upsert_event(existing)
    previews = preview_workout_events([_generated()], [existing])

    result = apply_workout_previews(previews, allow_skips=True)

    fetched = get_event(existing.slug)
    assert fetched is not None
    assert fetched.name == "Completed"
    assert result.skipped == 1


def test_apply_rejects_create_when_target_slug_exists(mem_db) -> None:
    generated = _generated()
    upsert_event(Event(slug=generated.slug, kind=KIND_TRAINING, date="2026-06-30", name="Other"))
    previews = preview_workout_events([generated], existing=[])

    with pytest.raises(RuntimeError, match="already exists"):
        apply_workout_previews(previews)


def test_apply_trail_race_week_from_db_writes_preview_actions(mem_db) -> None:
    upsert_event(_race())
    upsert_event(
        Event(
            slug="legacy-2026-06-29",
            kind=KIND_TRAINING,
            date="2026-06-29",
            name="55min easy Z2 run",
            status=STATUS_PLANNED,
            plan_id=2,
        )
    )

    result = apply_trail_race_week_from_db(
        race_slug="2026-07-04-steinbock",
        start_date="2026-06-27",
        slug_prefix="steinbock",
    )

    assert result.created == 6
    assert result.updated == 1
    updated = get_event("legacy-2026-06-29")
    assert updated is not None
    assert updated.plan_id == 2
    assert updated.payload["schema"] == "workout_spec.v1"
    assert get_event("steinbock-2026-07-03-rest") is not None
