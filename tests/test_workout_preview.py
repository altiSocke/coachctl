from __future__ import annotations

from coachctl.events import KIND_TRAINING, STATUS_COMPLETED, STATUS_PLANNED, Event
from coachctl.events import KIND_RACE, upsert_event
from coachctl.workout_archetypes import easy_run
from coachctl.workout_preview import (
    format_preview_json,
    format_preview_text,
    preview_trail_race_week_from_db,
    preview_workout_events,
    workouts_to_events,
)


def _generated_event(date: str = "2026-06-29", title: str = "40min easy trail run") -> Event:
    workout = easy_run(
        date=date,
        duration_min=40,
        hr_cap=155,
        title=title,
        sport="trail_run",
        estimated_tss=35.0,
    )
    return workouts_to_events([workout], slug_prefix="steinbock", plan_id=2, week_number=10)[0]


def test_workouts_to_events_uses_deterministic_slugs() -> None:
    event = _generated_event()

    assert event.slug == "steinbock-2026-06-29-easy-run"
    assert event.kind == KIND_TRAINING
    assert event.plan_id == 2
    assert event.payload["week_number"] == 10
    assert event.payload["schema"] == "workout_spec.v1"


def test_preview_creates_when_no_existing_event() -> None:
    generated = [_generated_event()]

    preview = preview_workout_events(generated, existing=[])

    assert len(preview) == 1
    assert preview[0].action == "create"
    assert preview[0].reason == "no_existing_event"
    assert preview[0].target_slug == generated[0].slug
    assert preview[0].existing is None
    assert preview[0].generated == generated[0]


def test_preview_updates_same_date_planned_event() -> None:
    generated = _generated_event(title="40min easy trail run")
    existing = Event(
        slug="legacy-2026-06-29",
        kind=KIND_TRAINING,
        date="2026-06-29",
        name="55min easy Z2 run",
        duration_min=55,
        summary="55min easy Z2 run",
        estimated_tss=None,
        status=STATUS_PLANNED,
        payload={"details": "55min easy Z2 run"},
    )

    preview = preview_workout_events([generated], [existing])

    assert preview[0].action == "update"
    assert preview[0].reason == "fields_differ"
    assert preview[0].target_slug == existing.slug
    assert preview[0].existing == existing
    assert preview[0].generated == generated
    assert preview[0].field_diffs["name"] == (existing.name, generated.name)
    assert "payload" in preview[0].field_diffs


def test_preview_matches_identical_generated_event() -> None:
    generated = _generated_event()
    existing = generated

    preview = preview_workout_events([generated], [existing])

    assert preview[0].action == "match"
    assert preview[0].reason == "no_changes"
    assert preview[0].field_diffs == {}


def test_preview_skips_completed_event() -> None:
    generated = _generated_event()
    existing = Event(
        slug="legacy-2026-06-29",
        kind=KIND_TRAINING,
        date="2026-06-29",
        name="Completed run",
        status=STATUS_COMPLETED,
    )

    preview = preview_workout_events([generated], [existing])

    assert preview[0].action == "skip"
    assert preview[0].reason == "existing_completed"
    assert preview[0].generated == generated


def test_preview_skips_locked_event() -> None:
    generated = _generated_event()
    existing = Event(
        slug="legacy-2026-06-29",
        kind=KIND_TRAINING,
        date="2026-06-29",
        name="Locked run",
        status=STATUS_PLANNED,
        payload={"locked": True},
    )

    preview = preview_workout_events([generated], [existing])

    assert preview[0].action == "skip"
    assert preview[0].reason == "existing_locked"


def test_preview_skips_ambiguous_same_date_events() -> None:
    generated = _generated_event()
    existing = [
        Event(slug="a", kind=KIND_TRAINING, date="2026-06-29", name="A"),
        Event(slug="b", kind=KIND_TRAINING, date="2026-06-29", name="B"),
    ]

    preview = preview_workout_events([generated], existing)

    assert preview[0].action == "skip"
    assert preview[0].reason == "ambiguous_existing_events"
    assert preview[0].existing is None


def test_preview_prefers_exact_slug_match_over_date_match() -> None:
    generated = _generated_event()
    same_slug = Event(
        slug=generated.slug,
        kind=KIND_TRAINING,
        date="2026-06-29",
        name="Same slug old title",
        status=STATUS_PLANNED,
    )
    same_date_other_slug = Event(
        slug="other",
        kind=KIND_TRAINING,
        date="2026-06-29",
        name="Other",
        status=STATUS_PLANNED,
    )

    preview = preview_workout_events([generated], [same_date_other_slug, same_slug])

    assert preview[0].action == "update"
    assert preview[0].existing == same_slug


def test_preview_ignores_implicit_plan_id_diff() -> None:
    generated = _generated_event()
    generated.plan_id = None
    existing = _generated_event()
    existing.plan_id = 2

    preview = preview_workout_events([generated], [existing])

    assert "plan_id" not in preview[0].field_diffs


def test_preview_shows_explicit_plan_id_diff() -> None:
    generated = _generated_event()
    generated.plan_id = 3
    existing = _generated_event()
    existing.plan_id = 2

    preview = preview_workout_events([generated], [existing])

    assert preview[0].field_diffs["plan_id"] == (2, 3)


def test_preview_trail_race_week_from_db_reads_existing_events(mem_db) -> None:
    race = Event(
        slug="2026-07-04-steinbock",
        kind=KIND_RACE,
        date="2026-07-04",
        name="Bernina Ultraks Steinbock",
    )
    existing_training = Event(
        slug="legacy-2026-06-29",
        kind=KIND_TRAINING,
        date="2026-06-29",
        name="55min easy Z2 run",
        status=STATUS_PLANNED,
    )
    upsert_event(race)
    upsert_event(existing_training)

    with mem_db() as conn:
        before = conn.execute("SELECT COUNT(*) AS c FROM events").fetchone()["c"]

    result = preview_trail_race_week_from_db(
        race_slug="2026-07-04-steinbock",
        start_date="2026-06-27",
        slug_prefix="steinbock",
    )

    with mem_db() as conn:
        after = conn.execute("SELECT COUNT(*) AS c FROM events").fetchone()["c"]

    assert before == after
    assert result.race_name == "Bernina Ultraks Steinbock"
    assert result.window_start == "2026-06-27"
    assert result.window_end == "2026-07-03"
    assert len(result.previews) == 7
    assert any(p.date == "2026-06-29" and p.action == "update" for p in result.previews)


def test_preview_trail_race_week_from_db_errors_for_missing_race(mem_db) -> None:
    result = preview_trail_race_week_from_db(
        race_slug="missing-race",
        start_date="2026-06-27",
    )

    assert result.error == "race_not_found"
    assert result.previews == []


def test_format_preview_text_and_json() -> None:
    generated = [_generated_event()]
    preview = preview_workout_events(generated, existing=[])

    text = format_preview_text(
        race_name="Bernina Ultraks Steinbock",
        window_start="2026-06-27",
        window_end="2026-07-03",
        previews=preview,
    )
    json_text = format_preview_json(preview)

    assert "Preview: Bernina Ultraks Steinbock race week" in text
    assert "2026-06-29 CREATE" in text
    assert "target: steinbock-2026-06-29-easy-run" in text
    assert "generated: steinbock-2026-06-29-easy-run" in text
    assert '"action": "create"' in json_text
    assert '"target_slug": "steinbock-2026-06-29-easy-run"' in json_text
    assert '"diff_fields": []' in json_text
