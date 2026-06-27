from __future__ import annotations

from coachctl.events import KIND_TRAINING, STATUS_CANCELLED, STATUS_COMPLETED, STATUS_PLANNED, Event
from coachctl.events import KIND_RACE, upsert_event
from coachctl.workout_archetypes import easy_run
from coachctl.workout_preview import (
    format_preview_json,
    format_preview_text,
    preview_post_trail_race_week_from_db,
    preview_half_marathon_week_from_db,
    preview_plan_from_db,
    preview_sessions_from_db,
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
    # name is reconcile-preserved, so it is never reported as a diff
    assert "name" not in preview[0].field_diffs
    assert "summary" in preview[0].field_diffs
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


def test_preview_post_trail_race_week_from_db_reads_existing_events(mem_db) -> None:
    race = Event(
        slug="2026-07-04-steinbock",
        kind=KIND_RACE,
        date="2026-07-04",
        name="Bernina Ultraks Steinbock",
    )
    existing_training = Event(
        slug="legacy-2026-07-08",
        kind=KIND_TRAINING,
        date="2026-07-08",
        name="Mona fartlek",
        status=STATUS_PLANNED,
    )
    upsert_event(race)
    upsert_event(existing_training)

    result = preview_post_trail_race_week_from_db(
        race_slug="2026-07-04-steinbock",
        start_date="2026-07-05",
        slug_prefix="steinbock-post",
    )

    assert result.race_name == "Bernina Ultraks Steinbock"
    assert result.window_start == "2026-07-05"
    assert result.window_end == "2026-07-12"
    assert len(result.previews) == 8
    jul8 = next(p for p in result.previews if p.date == "2026-07-08")
    assert jul8.action == "update"
    assert jul8.target_slug == "legacy-2026-07-08"


def test_preview_post_trail_race_week_cancels_same_day_strength(mem_db) -> None:
    upsert_event(
        Event(
            slug="2026-07-04-steinbock",
            kind=KIND_RACE,
            date="2026-07-04",
            name="Bernina Ultraks Steinbock",
        )
    )
    upsert_event(
        Event(
            slug="plan-run-2026-07-06",
            kind=KIND_TRAINING,
            date="2026-07-06",
            name="40min easy Z1-Z2 run",
            status=STATUS_PLANNED,
        )
    )
    upsert_event(
        Event(
            slug="strength-2026-07-06",
            kind=KIND_TRAINING,
            date="2026-07-06",
            name="Strength M1 maintenance block",
            status=STATUS_PLANNED,
        )
    )

    result = preview_post_trail_race_week_from_db(
        race_slug="2026-07-04-steinbock",
        start_date="2026-07-05",
        slug_prefix="steinbock-post",
    )

    jul6 = [p for p in result.previews if p.date == "2026-07-06"]
    assert [(p.action, p.target_slug) for p in jul6] == [
        ("update", "plan-run-2026-07-06"),
        ("cancel", "strength-2026-07-06"),
    ]
    assert jul6[1].reason == "superseded_by_post_race_generator"


def test_preview_post_trail_race_week_ignores_cancelled_strength(mem_db) -> None:
    upsert_event(
        Event(
            slug="2026-07-04-steinbock",
            kind=KIND_RACE,
            date="2026-07-04",
            name="Bernina Ultraks Steinbock",
        )
    )
    upsert_event(
        Event(
            slug="plan-run-2026-07-06",
            kind=KIND_TRAINING,
            date="2026-07-06",
            name="25-35min mechanics-check easy jog or rest",
            status=STATUS_PLANNED,
            payload={
                "schema": "workout_spec.v1",
                "workout": {"archetype": "mechanics_check_run"},
            },
        )
    )
    upsert_event(
        Event(
            slug="strength-2026-07-06",
            kind=KIND_TRAINING,
            date="2026-07-06",
            name="Strength M1 maintenance block",
            status=STATUS_CANCELLED,
        )
    )

    result = preview_post_trail_race_week_from_db(
        race_slug="2026-07-04-steinbock",
        start_date="2026-07-05",
        slug_prefix="steinbock-post",
    )

    jul6 = [p for p in result.previews if p.date == "2026-07-06"]
    assert not any(p.action == "cancel" for p in jul6)
    assert len(jul6) == 1


def test_preview_sessions_from_db_dispatches_post_race_mode(mem_db) -> None:
    upsert_event(
        Event(
            slug="2026-07-04-steinbock",
            kind=KIND_RACE,
            date="2026-07-04",
            name="Bernina Ultraks Steinbock",
        )
    )

    result = preview_sessions_from_db(
        mode="post-race",
        race_slug="2026-07-04-steinbock",
        start_date="2026-07-05",
        slug_prefix="steinbock-post",
    )

    assert result.window_end == "2026-07-12"
    assert len(result.previews) == 8


def test_preview_sessions_from_db_rejects_unknown_mode(mem_db) -> None:
    result = preview_sessions_from_db(
        mode="bad-mode",
        race_slug="whatever",
        start_date="2026-07-05",
    )

    assert result.error == "unsupported_mode"


def test_preview_half_marathon_week_ignores_same_day_strength(mem_db) -> None:
    upsert_event(
        Event(
            slug="plan-run-2026-07-13",
            kind=KIND_TRAINING,
            date="2026-07-13",
            name="Old easy run",
            status=STATUS_PLANNED,
        )
    )
    upsert_event(
        Event(
            slug="strength-2026-07-13",
            kind=KIND_TRAINING,
            date="2026-07-13",
            name="Strength M2 maintenance block",
            status=STATUS_PLANNED,
        )
    )

    result = preview_half_marathon_week_from_db(
        start_date="2026-07-13",
        target_tss=400,
        phase="build",
        freshness="normal",
        slug_prefix="hm-build",
    )

    jul13 = [p for p in result.previews if p.date == "2026-07-13"]
    assert len(jul13) == 1
    assert jul13[0].action == "update"
    assert jul13[0].target_slug == "plan-run-2026-07-13"


def test_preview_half_marathon_week_creates_when_only_strength_exists(mem_db) -> None:
    upsert_event(
        Event(
            slug="strength-2026-07-13",
            kind=KIND_TRAINING,
            date="2026-07-13",
            name="Strength M2 maintenance block",
            status=STATUS_PLANNED,
        )
    )

    result = preview_half_marathon_week_from_db(
        start_date="2026-07-13",
        target_tss=400,
        phase="build",
        freshness="normal",
        slug_prefix="hm-build",
    )

    jul13 = [p for p in result.previews if p.date == "2026-07-13"]
    assert len(jul13) == 1
    assert jul13[0].action == "create"
    assert jul13[0].target_slug == "hm-build-2026-07-13-easy-run"


def test_preview_half_marathon_week_suppresses_rest_day_create_by_default(mem_db) -> None:
    result = preview_half_marathon_week_from_db(
        start_date="2026-07-13",
        target_tss=400,
        phase="build",
        freshness="normal",
        slug_prefix="hm-build",
    )

    assert not any(p.date == "2026-07-17" for p in result.previews)
    assert result.summary["suppressed_rest_creates"] == 1


def test_preview_half_marathon_week_can_create_rest_days_when_requested(mem_db) -> None:
    result = preview_half_marathon_week_from_db(
        start_date="2026-07-13",
        target_tss=400,
        phase="build",
        freshness="normal",
        slug_prefix="hm-build",
        create_rest_days=True,
    )

    jul17 = [p for p in result.previews if p.date == "2026-07-17"]
    assert len(jul17) == 1
    assert jul17[0].action == "create"
    assert result.summary["suppressed_rest_creates"] == 0


def test_preview_half_marathon_week_skips_multiple_endurance_events(mem_db) -> None:
    upsert_event(Event(slug="run-a", kind=KIND_TRAINING, date="2026-07-13", name="Run A"))
    upsert_event(Event(slug="run-b", kind=KIND_TRAINING, date="2026-07-13", name="Run B"))
    upsert_event(
        Event(
            slug="strength-2026-07-13",
            kind=KIND_TRAINING,
            date="2026-07-13",
            name="Strength",
        )
    )

    result = preview_half_marathon_week_from_db(
        start_date="2026-07-13",
        target_tss=400,
        phase="build",
        freshness="normal",
        slug_prefix="hm-build",
    )

    jul13 = [p for p in result.previews if p.date == "2026-07-13"]
    assert len(jul13) == 1
    assert jul13[0].action == "skip"
    assert jul13[0].reason == "ambiguous_existing_events"


def test_preview_sessions_from_db_dispatches_half_marathon_mode(mem_db) -> None:
    result = preview_sessions_from_db(
        mode="half-marathon-week",
        race_slug=None,
        start_date="2026-07-13",
        slug_prefix="hm-build",
        target_tss=400,
        phase="build",
        freshness="normal",
    )

    assert result.race_name == "Half-marathon build week"
    assert result.window_start == "2026-07-13"
    assert result.window_end == "2026-07-19"
    assert len(result.previews) == 6
    assert result.summary["target_tss"] == 400
    assert result.summary["generated_tss"] == 385.0
    assert result.summary["actions"]["create"] == 6


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

    assert "Preview: Bernina Ultraks Steinbock" in text
    assert "2026-06-29 CREATE" in text
    assert "target: steinbock-2026-06-29-easy-run" in text
    assert "generated: steinbock-2026-06-29-easy-run" in text
    assert '"action": "create"' in json_text
    assert '"target_slug": "steinbock-2026-06-29-easy-run"' in json_text
    assert '"diff_fields": []' in json_text


def test_format_preview_text_includes_summary() -> None:
    generated = [_generated_event()]
    preview = preview_workout_events(generated, existing=[])

    text = format_preview_text(
        race_name="Half-marathon build week",
        window_start="2026-07-13",
        window_end="2026-07-19",
        previews=preview,
        summary={
            "target_tss": 400,
            "generated_tss": 385.0,
            "existing_tss": 405.0,
            "delta_tss": -20.0,
            "actions": {"create": 1, "update": 0, "match": 0, "skip": 0, "cancel": 0},
            "strength_preserved": 1,
            "suppressed_rest_creates": 1,
        },
    )

    assert "Target TSS: 400" in text
    assert "Generated TSS: 385" in text
    assert "Existing planned TSS: 405" in text
    assert "Actions: 1 create, 0 update, 0 match, 0 skip, 0 cancel" in text
    assert "Strength preserved: 1" in text
    assert "Suppressed rest creates: 1" in text


def _clone_event(event: Event, **overrides: object) -> Event:
    fields = {
        "slug": event.slug,
        "kind": event.kind,
        "date": event.date,
        "name": event.name,
        "start_time": event.start_time,
        "duration_min": event.duration_min,
        "summary": event.summary,
        "estimated_tss": event.estimated_tss,
        "status": event.status,
        "payload": event.payload,
        "plan_id": event.plan_id,
        "activity_id": event.activity_id,
        "notes": event.notes,
    }
    fields.update(overrides)
    return Event(**fields)  # type: ignore[arg-type]


def test_normalize_text_maps_typography_and_whitespace() -> None:
    from coachctl.workout_preview import _normalize_text

    assert _normalize_text("5 \u2013 10min") == _normalize_text("5 - 10min")
    assert _normalize_text("5\u201410min") == "5-10min"
    assert _normalize_text("3\u00d72min") == "3x2min"
    assert _normalize_text("a   b\t c ") == "a b c"
    # non-strings pass through untouched
    assert _normalize_text(42) == 42
    assert _normalize_text(None) is None


def test_preview_matches_when_summary_differs_only_cosmetically() -> None:
    generated = _generated_event()
    base = generated.summary or ""
    # same text, but with en-dashes for hyphens, × for x, and padded/extra spaces
    cosmetic = "  " + base.replace("-", "\u2013").replace("x", "\u00d7") + "   "
    cosmetic = cosmetic.replace(" ", "  ")  # double every space
    existing = _clone_event(generated, slug="legacy-cosmetic", summary=cosmetic)

    assert existing.summary != generated.summary  # genuinely different bytes
    preview = preview_workout_events([generated], [existing])

    assert preview[0].action == "match"
    assert preview[0].field_diffs == {}


def test_preview_matches_when_only_name_differs() -> None:
    generated = _generated_event()
    existing = _clone_event(generated, slug="legacy-named", name="Human-edited title")

    preview = preview_workout_events([generated], [existing])

    assert preview[0].action == "match"
    assert "name" not in preview[0].field_diffs
    assert preview[0].field_diffs == {}


# ── preview_plan_from_db (multi-week, reconcile) ─────────────────────────────


def test_preview_plan_rejects_unknown_template(mem_db) -> None:
    result = preview_plan_from_db(
        template_name="nope",
        start_date="2026-07-13",
        weeks=1,
    )
    assert result.error == "unknown_template"
    assert result.previews == []


def test_preview_plan_rejects_weeks_out_of_range(mem_db) -> None:
    too_many = preview_plan_from_db(
        template_name="half_marathon_build",
        start_date="2026-07-13",
        weeks=99,
    )
    assert too_many.error == "weeks_out_of_range"

    zero = preview_plan_from_db(
        template_name="half_marathon_build",
        start_date="2026-07-13",
        weeks=0,
    )
    assert zero.error == "weeks_out_of_range"


def test_preview_plan_is_deterministic_for_seed_none(mem_db) -> None:
    a = preview_plan_from_db(
        template_name="half_marathon_build", start_date="2026-07-13", weeks=2
    )
    b = preview_plan_from_db(
        template_name="half_marathon_build", start_date="2026-07-13", weeks=2
    )
    assert [(p.date, p.action, p.target_slug) for p in a.previews] == [
        (p.date, p.action, p.target_slug) for p in b.previews
    ]
    assert a.summary == b.summary


def test_preview_plan_target_tss_is_sum_of_week_targets(mem_db) -> None:
    result = preview_plan_from_db(
        template_name="half_marathon_build", start_date="2026-07-13", weeks=2
    )
    # two build weeks at 400 each
    assert result.summary is not None
    assert result.summary["target_tss"] == 800
    assert result.window_start == "2026-07-13"
    assert result.window_end == "2026-07-26"  # 14 days inclusive


def test_preview_plan_updates_existing_ride_and_preserves_strength(mem_db) -> None:
    # Tue endurance ride should be updated; Mon strength must be preserved.
    upsert_event(
        Event(
            slug="my-ride-2026-07-14",
            kind=KIND_TRAINING,
            date="2026-07-14",
            name="Coach-named endurance ride",
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
            name="Strength M1 maintenance block",
            status=STATUS_PLANNED,
            estimated_tss=20.0,
        )
    )

    result = preview_plan_from_db(
        template_name="half_marathon_build", start_date="2026-07-13", weeks=1
    )

    tue = [p for p in result.previews if p.date == "2026-07-14"]
    assert len(tue) == 1
    assert tue[0].action == "update"
    assert tue[0].target_slug == "my-ride-2026-07-14"
    assert "name" not in tue[0].field_diffs  # name preserved

    # strength session is never proposed for create/update and is counted
    assert all(p.target_slug != "strength-2026-07-13" for p in result.previews)
    assert result.summary is not None
    assert result.summary["strength_preserved"] == 1


def test_preview_plan_blocks_generated_session_on_race_day(mem_db) -> None:
    upsert_event(
        Event(
            slug="2026-07-15-local-10k",
            kind=KIND_RACE,
            date="2026-07-15",  # Wednesday quality day
            name="Local 10k race",
            status=STATUS_PLANNED,
        )
    )

    result = preview_plan_from_db(
        template_name="half_marathon_build", start_date="2026-07-13", weeks=1
    )

    assert all(p.date != "2026-07-15" for p in result.previews)
    assert result.summary is not None
    assert result.summary["suppressed_race_days"] == 1


def test_preview_plan_skips_ambiguous_same_day_endurance(mem_db) -> None:
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

    result = preview_plan_from_db(
        template_name="half_marathon_build", start_date="2026-07-13", weeks=1
    )

    mon = [p for p in result.previews if p.date == "2026-07-13"]
    assert len(mon) == 1
    assert mon[0].action == "skip"
    assert mon[0].reason == "ambiguous_existing_events"


def test_preview_plan_suppresses_rest_create_by_default(mem_db) -> None:
    default = preview_plan_from_db(
        template_name="half_marathon_build", start_date="2026-07-13", weeks=1
    )
    # Friday is a rest day; with no existing event it would be a create, which
    # is suppressed by default.
    assert all(p.date != "2026-07-17" for p in default.previews)
    assert default.summary is not None
    assert default.summary["suppressed_rest_creates"] == 1

    explicit = preview_plan_from_db(
        template_name="half_marathon_build",
        start_date="2026-07-13",
        weeks=1,
        create_rest_days=True,
    )
    fri = [p for p in explicit.previews if p.date == "2026-07-17"]
    assert len(fri) == 1
    assert fri[0].action == "create"
