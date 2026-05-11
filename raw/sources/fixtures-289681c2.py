"""
Extended tests for coachctl.events — upsert, update_payload, delete, date_has_event,
empty_race_payload, and conflict resolution.
"""

from __future__ import annotations

import json

import pytest

from coachctl.events import (
    KIND_APPOINTMENT,
    KIND_RACE,
    KIND_TRAINING,
    KIND_UNTRACKED,
    STATUS_CANCELLED,
    STATUS_COMPLETED,
    STATUS_PLANNED,
    Event,
    date_has_event,
    delete_event,
    empty_race_payload,
    event_payload_hash,
    get_calendar,
    get_event,
    upsert_event,
    update_event_payload,
    _resolve_conflicts,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────




def _make_event(**kwargs) -> Event:
    defaults = dict(slug="ev-1", kind=KIND_TRAINING, date="2026-05-10", name="Easy run")
    defaults.update(kwargs)
    return Event(**defaults)


# ── upsert_event ──────────────────────────────────────────────────────────────


def test_upsert_event_insert(mem_db):
    ev = _make_event()
    row_id = upsert_event(ev)
    assert row_id > 0
    fetched = get_event("ev-1")
    assert fetched is not None
    assert fetched.name == "Easy run"


def test_upsert_event_update(mem_db):
    ev = _make_event()
    upsert_event(ev)
    ev2 = _make_event(name="Updated Run")
    row_id2 = upsert_event(ev2)
    fetched = get_event("ev-1")
    assert fetched.name == "Updated Run"


def test_upsert_event_invalid_kind(mem_db):
    ev = _make_event(kind="bogus")
    with pytest.raises(ValueError, match="unknown kind"):
        upsert_event(ev)


def test_upsert_event_with_payload(mem_db):
    payload = {"priority": "A", "goal": {"time": "1:35"}}
    ev = _make_event(kind=KIND_RACE, payload=payload)
    upsert_event(ev)
    fetched = get_event("ev-1")
    assert fetched.payload["priority"] == "A"
    assert fetched.payload["goal"]["time"] == "1:35"


def test_upsert_event_returns_same_id_on_update(mem_db):
    ev = _make_event()
    id1 = upsert_event(ev)
    id2 = upsert_event(_make_event(name="Updated"))
    assert id1 == id2


def test_upsert_event_status(mem_db):
    ev = _make_event(status=STATUS_COMPLETED)
    upsert_event(ev)
    fetched = get_event("ev-1")
    assert fetched.status == STATUS_COMPLETED


# ── update_event_payload ──────────────────────────────────────────────────────


def test_update_event_payload_adds_key(mem_db):
    upsert_event(_make_event(kind=KIND_RACE))
    update_event_payload("ev-1", "priority", "B")
    fetched = get_event("ev-1")
    assert fetched.payload["priority"] == "B"


def test_update_event_payload_removes_key_when_none(mem_db):
    upsert_event(_make_event(kind=KIND_RACE, payload={"priority": "A"}))
    update_event_payload("ev-1", "priority", None)
    fetched = get_event("ev-1")
    assert "priority" not in fetched.payload


def test_update_event_payload_raises_for_missing_event(mem_db):
    with pytest.raises(KeyError, match="event not found"):
        update_event_payload("nonexistent", "key", "value")


# ── delete_event ──────────────────────────────────────────────────────────────


def test_delete_event_returns_true(mem_db):
    upsert_event(_make_event())
    result = delete_event("ev-1")
    assert result is True
    assert get_event("ev-1") is None


def test_delete_event_returns_false_when_not_found(mem_db):
    result = delete_event("doesnt-exist")
    assert result is False


# ── date_has_event ────────────────────────────────────────────────────────────


def test_date_has_event_true(mem_db):
    upsert_event(_make_event(date="2026-05-15"))
    assert date_has_event("2026-05-15") is True


def test_date_has_event_false(mem_db):
    assert date_has_event("2026-12-31") is False


def test_date_has_event_kind_filter_match(mem_db):
    upsert_event(_make_event(kind=KIND_RACE, date="2026-06-01"))
    assert date_has_event("2026-06-01", kinds=[KIND_RACE]) is True


def test_date_has_event_kind_filter_no_match(mem_db):
    upsert_event(_make_event(kind=KIND_TRAINING, date="2026-06-01"))
    assert date_has_event("2026-06-01", kinds=[KIND_RACE]) is False


# ── empty_race_payload ────────────────────────────────────────────────────────


def test_empty_race_payload_has_required_keys():
    p = empty_race_payload()
    for key in ("priority", "course", "goal", "key_principles", "pacing",
                "warmup", "nutrition", "logistics", "kit", "protocols"):
        assert key in p


def test_empty_race_payload_default_priority():
    assert empty_race_payload()["priority"] == "C"


def test_empty_race_payload_returns_new_dict():
    p1 = empty_race_payload()
    p2 = empty_race_payload()
    p1["priority"] = "A"
    assert p2["priority"] == "C"  # not mutated


# ── event_payload_hash (public wrapper) ───────────────────────────────────────


def test_event_payload_hash_is_16_chars():
    ev = Event(slug="x", kind=KIND_TRAINING, date="2026-05-01", name="Run")
    assert len(event_payload_hash(ev)) == 16


# ── _resolve_conflicts ────────────────────────────────────────────────────────


def _ev(slug, kind, date, status=STATUS_PLANNED):
    return Event(slug=slug, kind=kind, date=date, name="x", status=status)


def test_resolve_conflicts_race_blocks_training():
    events = [
        _ev("race-1", KIND_RACE, "2026-06-01"),
        _ev("train-1", KIND_TRAINING, "2026-06-01"),
    ]
    result = _resolve_conflicts(events)
    slugs = {e.slug for e in result}
    assert "race-1" in slugs
    assert "train-1" not in slugs


def test_resolve_conflicts_race_blocks_untracked():
    events = [
        _ev("race-1", KIND_RACE, "2026-06-01"),
        _ev("untracked-1", KIND_UNTRACKED, "2026-06-01"),
    ]
    result = _resolve_conflicts(events)
    assert not any(e.kind == KIND_UNTRACKED for e in result)


def test_resolve_conflicts_completed_training_survives_race():
    """Completed training on race day should NOT be suppressed."""
    events = [
        _ev("race-1", KIND_RACE, "2026-06-01"),
        _ev("train-done", KIND_TRAINING, "2026-06-01", status=STATUS_COMPLETED),
    ]
    result = _resolve_conflicts(events)
    assert any(e.slug == "train-done" for e in result)


def test_resolve_conflicts_cancelled_race_does_not_block():
    events = [
        _ev("race-cancelled", KIND_RACE, "2026-06-01", status=STATUS_CANCELLED),
        _ev("train-1", KIND_TRAINING, "2026-06-01"),
    ]
    result = _resolve_conflicts(events)
    assert any(e.slug == "train-1" for e in result)


def test_resolve_conflicts_no_race_returns_all():
    events = [
        _ev("train-a", KIND_TRAINING, "2026-06-01"),
        _ev("train-b", KIND_TRAINING, "2026-06-02"),
    ]
    result = _resolve_conflicts(events)
    assert len(result) == 2
