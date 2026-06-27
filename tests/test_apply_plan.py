from __future__ import annotations

import pytest

import coachctl.db as db_module
from coachctl import paths
from coachctl.db import init_db
from coachctl.events import (
    KIND_RACE,
    KIND_TRAINING,
    STATUS_PLANNED,
    Event,
    get_event,
    upsert_event,
)
from coachctl.workout_apply import apply_plan_from_db


@pytest.fixture(autouse=True)
def _reset_db_init_guard():
    db_module._DB_INITIALISED = False
    yield
    db_module._DB_INITIALISED = False


@pytest.fixture
def real_db(tmp_data_root):
    """A real (non-mocked) DB so the sandbox override + bake paths resolve."""
    db_module._DB_INITIALISED = False
    init_db()
    return paths.db_path()


def test_apply_plan_writes_to_live_db(real_db) -> None:
    result = apply_plan_from_db(
        template_name="half_marathon_build", start_date="2026-07-13", weeks=1
    )

    # 6 sessions created (Fri rest is suppressed by default)
    assert result.created == 6
    assert result.updated == 0
    # the generated sessions are now in the live DB
    assert get_event("plan-2026-07-13-easy-run") is not None
    assert get_event("plan-2026-07-15-cruise-intervals") is not None
    # apply only writes events; it does NOT publish the dashboard payload.
    # (the sandbox validation bake is isolated to a throwaway dir.)
    assert not paths.data_json().exists()


def test_apply_plan_is_idempotent(real_db) -> None:
    first = apply_plan_from_db(
        template_name="half_marathon_build", start_date="2026-07-13", weeks=1
    )
    assert first.created == 6

    second = apply_plan_from_db(
        template_name="half_marathon_build", start_date="2026-07-13", weeks=1
    )
    assert second.created == 0
    assert second.updated == 0
    assert second.matched == 6


def test_apply_plan_preserves_existing_name_and_strength(real_db) -> None:
    upsert_event(
        Event(
            slug="ride-2026-07-14",
            kind=KIND_TRAINING,
            date="2026-07-14",
            name="Coach-named ride",
            status=STATUS_PLANNED,
            estimated_tss=50.0,
            summary="endurance ride",
        )
    )
    upsert_event(
        Event(
            slug="strength-2026-07-13",
            kind=KIND_TRAINING,
            date="2026-07-13",
            name="Strength M1 block",
            status=STATUS_PLANNED,
        )
    )

    result = apply_plan_from_db(
        template_name="half_marathon_build", start_date="2026-07-13", weeks=1
    )

    assert result.updated == 1
    ride = get_event("ride-2026-07-14")
    assert ride is not None
    assert ride.name == "Coach-named ride"  # preserved
    assert ride.payload.get("schema") == "workout_spec.v1"  # payload updated
    strength = get_event("strength-2026-07-13")
    assert strength is not None
    assert strength.name == "Strength M1 block"  # untouched


def test_apply_plan_does_not_create_on_race_day(real_db) -> None:
    upsert_event(
        Event(
            slug="2026-07-15-local-10k",
            kind=KIND_RACE,
            date="2026-07-15",
            name="Local 10k race",
            status=STATUS_PLANNED,
        )
    )

    apply_plan_from_db(
        template_name="half_marathon_build", start_date="2026-07-13", weeks=1
    )

    # no generated training created on the race date
    assert get_event("plan-2026-07-15-cruise-intervals") is None
    # the race itself is untouched
    race = get_event("2026-07-15-local-10k")
    assert race is not None
    assert race.kind == KIND_RACE


def test_apply_plan_rejects_unknown_template(real_db) -> None:
    with pytest.raises(RuntimeError, match="unknown_template"):
        apply_plan_from_db(template_name="nope", start_date="2026-07-13", weeks=1)


def test_apply_plan_rejects_skips_by_default(real_db) -> None:
    # Two endurance sessions on Monday make that day ambiguous -> skip row.
    upsert_event(
        Event(
            slug="ride-a-2026-07-13",
            kind=KIND_TRAINING,
            date="2026-07-13",
            name="Ride A",
            status=STATUS_PLANNED,
            summary="ride a",
        )
    )
    upsert_event(
        Event(
            slug="ride-b-2026-07-13",
            kind=KIND_TRAINING,
            date="2026-07-13",
            name="Ride B",
            status=STATUS_PLANNED,
            summary="ride b",
        )
    )

    with pytest.raises(RuntimeError, match="skip"):
        apply_plan_from_db(
            template_name="half_marathon_build", start_date="2026-07-13", weeks=1
        )

    # nothing was written to the live DB (sandbox aborted before live replay)
    assert get_event("plan-2026-07-14-z2-ride") is None


def test_apply_plan_create_rest_days_when_requested(real_db) -> None:
    result = apply_plan_from_db(
        template_name="half_marathon_build",
        start_date="2026-07-13",
        weeks=1,
        create_rest_days=True,
    )
    # 7 created now (Fri rest day included)
    assert result.created == 7
    assert get_event("plan-2026-07-17-rest") is not None


def test_apply_plan_raises_when_sandbox_does_not_converge(real_db, monkeypatch) -> None:
    # Stub the preview to always report a pending "update" so the post-apply
    # re-preview never converges -> the sandbox guard must fire and nothing is
    # written to the live DB.
    import coachctl.workout_preview as wp

    existing = Event(
        slug="ghost-2026-07-13",
        kind=KIND_TRAINING,
        date="2026-07-13",
        name="Ghost",
        status=STATUS_PLANNED,
    )
    generated = Event(
        slug="ghost-2026-07-13",
        kind=KIND_TRAINING,
        date="2026-07-13",
        name="Ghost",
        status=STATUS_PLANNED,
        summary="changed",
    )
    never_converges = wp.WorkoutPreviewResult(
        race_slug="",
        race_name="Plan: stub",
        window_start="2026-07-13",
        window_end="2026-07-19",
        previews=[
            wp.WorkoutEventPreview(
                date="2026-07-13",
                slug="ghost-2026-07-13",
                target_slug="ghost-2026-07-13",
                action="update",
                reason="fields_differ",
                existing=existing,
                generated=generated,
                field_diffs={"summary": (None, "changed")},
            )
        ],
        summary={},
    )

    def _stub(**kwargs):
        return never_converges

    monkeypatch.setattr(wp, "preview_plan_from_db", _stub)
    # Make the (stubbed) update target exist so apply_workout_previews can run.
    upsert_event(existing)

    with pytest.raises(RuntimeError, match="sandbox_not_converged"):
        apply_plan_from_db(
            template_name="half_marathon_build", start_date="2026-07-13", weeks=1
        )

