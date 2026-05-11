"""
Event tools — read/write the unified ``events`` calendar table.

This is the single MCP surface for date-anchored items (races, training
sessions, untracked activities, appointments). Use ``get_calendar_window``
before any date-related action to confirm what is actually scheduled —
NEVER trust a date pulled from narrative wiki text.

Race cards are authored section-by-section via ``propose_race_*`` /
``apply_race_*`` tools. Each section is a key inside ``payload_json`` and
edits are presented as a unified diff for athlete approval before write.
"""

from __future__ import annotations

import difflib
import json
import re
from datetime import date as _date
from datetime import timedelta
from typing import Any

from ..events import (
    ALL_KINDS,
    KIND_RACE,
    KIND_TRAINING,
    KIND_UNTRACKED,
    KIND_APPOINTMENT,
    STATUS_CANCELLED,
    STATUS_PLANNED,
    Event,
    delete_event as _delete_event,
    empty_race_payload,
    get_calendar,
    get_event,
    update_event_payload,
    upsert_event,
)


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-")[:60] or "event"


def _validate_date(d: str) -> str:
    """Raise ValueError unless ``d`` is a valid ISO YYYY-MM-DD string."""
    try:
        _date.fromisoformat(d)
    except ValueError as exc:
        raise ValueError(f"date '{d}' is not a valid YYYY-MM-DD — refusing to write.") from exc
    return d


def _diff_payload_section(slug: str, key: str, new_value: Any) -> str:
    ev = get_event(slug)
    if not ev:
        return f"(error: event '{slug}' not found)"
    current = ev.payload.get(key)
    cur_text = (
        json.dumps(current, indent=2, sort_keys=True, ensure_ascii=False)
        if current is not None
        else ""
    )
    new_text = (
        json.dumps(new_value, indent=2, sort_keys=True, ensure_ascii=False)
        if new_value is not None
        else ""
    )
    diff = difflib.unified_diff(
        cur_text.splitlines(),
        new_text.splitlines(),
        fromfile=f"{slug}.{key} (current)",
        tofile=f"{slug}.{key} (proposed)",
        lineterm="",
    )
    text = "\n".join(diff)
    return text if text.strip() else "(no changes)"


def register(mcp) -> None:  # noqa: ANN001

    # ── Calendar reads ────────────────────────────────────────────────────

    @mcp.tool()
    def get_calendar_window(
        start: str = "",
        end: str = "",
        kinds: str = "",
    ) -> str:
        """
        Return all calendar items in [start, end] inclusive — the AUTHORITATIVE
        source for "what's scheduled on date X". Always call this before
        creating, moving, or referencing dated items.

        Parameters
        ----------
        start, end : ISO YYYY-MM-DD. Defaults to today and today+28 days.
        kinds : optional CSV filter (e.g. 'race,training'). Empty = all.
        """
        if not start:
            start = _date.today().isoformat()
        if not end:
            end = (_date.today() + timedelta(days=28)).isoformat()
        _validate_date(start)
        _validate_date(end)
        kind_set = None
        if kinds.strip():
            kind_set = {k.strip() for k in kinds.split(",") if k.strip()}
            unknown = kind_set - ALL_KINDS
            if unknown:
                return f"Error: unknown kinds: {sorted(unknown)}"

        events = get_calendar(start, end, kinds=kind_set)
        return json.dumps([e.to_dict() for e in events], indent=2, default=str)

    @mcp.tool()
    def get_event_detail(slug: str) -> str:
        """
        Return the full event row (including ``payload`` race-card content).
        Returns 'null' if not found.
        """
        ev = get_event(slug)
        return json.dumps(ev.to_dict() if ev else None, indent=2, default=str)

    @mcp.tool()
    def date_is_free(d: str, ignore_kinds: str = "activity") -> str:
        """
        Check whether ``d`` is free of scheduled events.
        ignore_kinds: CSV of kinds to ignore (default 'activity' so completed
        sessions don't count). Returns JSON {free: bool, conflicts: [...]}.
        """
        _validate_date(d)
        ignore = {k.strip() for k in ignore_kinds.split(",") if k.strip()}
        events = get_calendar(d, d)
        conflicts = [e.to_dict() for e in events if e.kind not in ignore]
        return json.dumps({"free": not conflicts, "conflicts": conflicts}, indent=2, default=str)

    # ── Generic event writes ──────────────────────────────────────────────

    @mcp.tool()
    def create_event(
        kind: str,
        date: str,
        name: str,
        slug: str = "",
        start_time: str = "",
        duration_min: int = 0,
        summary: str = "",
        estimated_tss: float = 0.0,
        notes: str = "",
    ) -> str:
        """
        Create a planned calendar event (training, untracked, appointment).
        For races prefer ``create_race`` which seeds the payload skeleton.

        Returns the slug of the created event.
        """
        if kind not in ALL_KINDS:
            return f"Error: unknown kind '{kind}'. Use one of {sorted(ALL_KINDS)}."
        if kind == "activity":
            return "Error: kind='activity' is reserved for synced Strava rows."
        _validate_date(date)
        slug = slug.strip() or f"{kind}-{date}-{_slugify(name)}"
        if get_event(slug):
            return f"Error: event with slug '{slug}' already exists. Use update_event."
        ev = Event(
            slug=slug,
            kind=kind,
            date=date,
            start_time=start_time or None,
            duration_min=duration_min or None,
            name=name,
            summary=summary or None,
            estimated_tss=estimated_tss or None,
            status=STATUS_PLANNED,
            notes=notes or None,
        )
        upsert_event(ev)
        return f"Created event '{slug}' ({kind}) on {date}: {name}"

    @mcp.tool()
    def create_race(
        date: str,
        name: str,
        priority: str = "C",
        slug: str = "",
        start_time: str = "",
        duration_min: int = 0,
        summary: str = "",
    ) -> str:
        """
        Create a race event with an empty race-card payload skeleton.
        Fill in sections via ``propose_race_*`` / ``apply_race_*`` tools.

        Parameters
        ----------
        priority : 'A', 'B', or 'C'.
        slug : optional override (defaults to '<date>-<slugified-name>').
        """
        priority = priority.upper().strip()
        if priority not in {"A", "B", "C"}:
            return "Error: priority must be 'A', 'B', or 'C'."
        _validate_date(date)
        slug = slug.strip() or f"{date}-{_slugify(name)}"
        if get_event(slug):
            return f"Error: race '{slug}' already exists. Use update_event or propose_race_* tools."
        payload = empty_race_payload()
        payload["priority"] = priority
        ev = Event(
            slug=slug,
            kind=KIND_RACE,
            date=date,
            start_time=start_time or None,
            duration_min=duration_min or None,
            name=name,
            summary=summary or None,
            status=STATUS_PLANNED,
            payload=payload,
        )
        upsert_event(ev)
        return (
            f"Created race '{slug}' on {date} (priority {priority}). "
            f"Now fill in sections via propose_race_pacing, propose_race_kit, etc."
        )

    @mcp.tool()
    def update_event(
        slug: str,
        date: str = "",
        name: str = "",
        start_time: str = "",
        duration_min: int = -1,
        summary: str = "",
        status: str = "",
        notes: str = "",
        estimated_tss: float = -1.0,
    ) -> str:
        """
        Patch top-level fields of an event. Empty / sentinel values are ignored.
        For race-card payload sections use ``apply_race_*`` instead.
        """
        ev = get_event(slug)
        if not ev:
            return f"Error: event '{slug}' not found."
        if date:
            _validate_date(date)
            ev.date = date
        if name:
            ev.name = name
        if start_time:
            ev.start_time = start_time
        if duration_min >= 0:
            ev.duration_min = duration_min or None
        if summary:
            ev.summary = summary
        if status:
            if status not in {"planned", "completed", "cancelled"}:
                return "Error: status must be planned|completed|cancelled."
            ev.status = status
        if notes:
            ev.notes = notes
        if estimated_tss >= 0:
            ev.estimated_tss = estimated_tss or None
        upsert_event(ev)
        return f"Updated event '{slug}'."

    @mcp.tool()
    def cancel_event(slug: str, reason: str = "") -> str:
        """Mark an event cancelled (kept in DB for history)."""
        ev = get_event(slug)
        if not ev:
            return f"Error: event '{slug}' not found."
        ev.status = STATUS_CANCELLED
        if reason:
            ev.notes = (ev.notes + "\n" if ev.notes else "") + f"Cancelled: {reason}"
        upsert_event(ev)
        return f"Cancelled '{slug}'."

    @mcp.tool()
    def delete_event(slug: str) -> str:
        """Hard-delete an event row. Prefer ``cancel_event`` for history."""
        ok = _delete_event(slug)
        return f"Deleted '{slug}'." if ok else f"Error: '{slug}' not found."

    # ── Race-card section editors ─────────────────────────────────────────
    #
    # Per-section propose/apply pair pattern: `propose_*` returns a unified
    # diff WITHOUT writing; `apply_*` writes after athlete confirmation.

    def _make_section_pair(key: str, doc: str) -> None:
        @mcp.tool(name=f"propose_race_{key}")
        def _propose(slug: str, content_json: str) -> str:  # type: ignore[no-redef]
            f"""Propose update to race '{slug}' section '{key}'. {doc}

            content_json: JSON-encoded value for the section.
            Returns a unified diff. Call apply_race_{key} after approval.
            """
            ev = get_event(slug)
            if not ev or ev.kind != KIND_RACE:
                return f"Error: race '{slug}' not found."
            try:
                value = json.loads(content_json) if content_json.strip() else None
            except json.JSONDecodeError as exc:
                return f"Error: invalid JSON — {exc}"
            return _diff_payload_section(slug, key, value)

        _propose.__doc__ = (
            f"Propose update to race '<slug>' section '{key}'. {doc}\n\n"
            "content_json: JSON-encoded value for the section.\n"
            f"Returns a unified diff. Call apply_race_{key} after approval."
        )

        @mcp.tool(name=f"apply_race_{key}")
        def _apply(slug: str, content_json: str) -> str:  # type: ignore[no-redef]
            ev = get_event(slug)
            if not ev or ev.kind != KIND_RACE:
                return f"Error: race '{slug}' not found."
            try:
                value = json.loads(content_json) if content_json.strip() else None
            except json.JSONDecodeError as exc:
                return f"Error: invalid JSON — {exc}"
            update_event_payload(slug, key, value)
            return f"Updated '{slug}'.payload.{key}."

        _apply.__doc__ = (
            f"Apply previously-proposed update to race '<slug>' section '{key}'.\n"
            "Only call after athlete approval of the diff from propose_race_"
            f"{key}."
        )

    _make_section_pair(
        "course",
        "Course facts: distance_km, elevation_m, surface, terrain, profile_url.",
    )
    _make_section_pair(
        "goal",
        "Goal block: a/b/c targets, target_pace, target_time, key_metric.",
    )
    _make_section_pair(
        "key_principles",
        "List of one-line principles to keep top-of-mind on race day.",
    )
    _make_section_pair(
        "pacing",
        "List of pacing rows: [{km, segment, target_pace, hr_zone, notes}, ...].",
    )
    _make_section_pair(
        "climbs",
        "Cycling: list of climb rows: [{name, km, length_km, gradient_pct, strategy}, ...].",
    )
    _make_section_pair(
        "warmup",
        "List of warmup rows: [{minutes, action, intensity}, ...].",
    )
    _make_section_pair(
        "nutrition",
        "Fueling block: pre_race, on_course (g_carbs_per_hour, schedule), post.",
    )
    _make_section_pair(
        "logistics",
        "Logistics block: travel, parking, bib_pickup, gear_drop, weather, contacts.",
    )
    _make_section_pair(
        "kit",
        "Kit list: clothing, shoes, accessories, nutrition_carried, contingency.",
    )
    _make_section_pair(
        "protocols",
        "List of protocol cards: [{title, body}] for cramping, bonk, mechanicals, etc.",
    )
    _make_section_pair(
        "yoy",
        "Year-over-year comparison: {columns: [...], rows: [[...], ...]}.",
    )
    _make_section_pair(
        "readiness_gate",
        "Free-text readiness criteria — when to start, when to bail.",
    )
