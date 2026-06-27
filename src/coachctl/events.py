"""
Calendar projection layer — the single source of truth for date-anchored items.

Every consumer that needs to know "what's on date X" reads from here:
  * bake / dashboard
  * coach agent (via `get_calendar_window` MCP tool)

Sources merged (in order of precedence on date conflict):
  1. ``events`` table, kind='race'  → race events (block training that day)
  2. ``events`` table, kind='training'/'untracked'/'appointment'
  3. ``activities`` rows projected as kind='activity'
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import date as Date
from datetime import datetime, timedelta
from typing import Any, Iterable

from . import paths
from .db import get_conn

KIND_RACE = "race"
KIND_TRAINING = "training"
KIND_UNTRACKED = "untracked"
KIND_APPOINTMENT = "appointment"
KIND_ACTIVITY = "activity"

ALL_KINDS = {KIND_RACE, KIND_TRAINING, KIND_UNTRACKED, KIND_APPOINTMENT, KIND_ACTIVITY}

STATUS_PLANNED = "planned"
STATUS_COMPLETED = "completed"
STATUS_CANCELLED = "cancelled"


@dataclass
class Event:
    slug: str
    kind: str
    date: str  # ISO YYYY-MM-DD
    name: str
    start_time: str | None = None  # HH:MM
    duration_min: int | None = None
    summary: str | None = None
    estimated_tss: float | None = None
    status: str = STATUS_PLANNED
    payload: dict[str, Any] = field(default_factory=dict)
    plan_id: int | None = None
    activity_id: int | None = None
    notes: str | None = None
    source: tuple[str, str] = ("", "")  # (source_kind, source_ref) — proves single truth

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["source"] = list(self.source)
        return d


# ── Helpers ──────────────────────────────────────────────────────────────────


def _row_to_event(row: sqlite3.Row) -> Event:
    payload: dict[str, Any] = {}
    if row["payload_json"]:
        try:
            payload = json.loads(row["payload_json"])
        except json.JSONDecodeError:
            payload = {"_raw": row["payload_json"]}
    return Event(
        slug=row["slug"],
        kind=row["kind"],
        date=row["date"],
        start_time=row["start_time"],
        duration_min=row["duration_min"],
        name=row["name"],
        summary=row["summary"],
        estimated_tss=row["estimated_tss"],
        status=row["status"] or STATUS_PLANNED,
        payload=payload,
        plan_id=row["plan_id"],
        activity_id=row["activity_id"],
        notes=row["notes"],
        source=("events_table", str(row["id"])),
    )


def _payload_hash(event: Event) -> str:
    """Stable hash of an event's content — for change detection (calendar sync)."""
    parts = [
        event.slug,
        event.kind,
        event.date,
        event.start_time or "",
        str(event.duration_min or ""),
        event.name,
        event.summary or "",
        event.status,
        json.dumps(event.payload, sort_keys=True),
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


# ── Reads ────────────────────────────────────────────────────────────────────


def get_event(slug: str) -> Event | None:
    """Look up a single event by slug."""
    if not paths.db_path().exists():
        return None
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM events WHERE slug = ?",
            (slug,),
        ).fetchone()
    return _row_to_event(row) if row else None


def get_calendar(
    start: str | Date,
    end: str | Date,
    kinds: Iterable[str] | None = None,
) -> list[Event]:
    """
    Return all events in [start, end] inclusive, sorted by (date, start_time).

    Parameters
    ----------
    start, end :
        ISO date strings or ``datetime.date`` objects.
    kinds :
        Filter to specific kinds. Default: all kinds.
    """
    if isinstance(start, Date):
        start = start.isoformat()
    if isinstance(end, Date):
        end = end.isoformat()
    kinds_set = set(kinds) if kinds else set(ALL_KINDS)

    if not paths.db_path().exists():
        return []

    events: list[Event] = []

    with get_conn() as conn:
        # Source 1: events table
        rows = conn.execute(
            """
            SELECT * FROM events
            WHERE date BETWEEN ? AND ?
            ORDER BY date, start_time
            """,
            (start, end),
        ).fetchall()
        for r in rows:
            ev = _row_to_event(r)
            if ev.kind in kinds_set:
                events.append(ev)

        # Source 2: activities → project as kind='activity'
        if KIND_ACTIVITY in kinds_set:
            arows = conn.execute(
                """
                SELECT id, name, sport_type, start_date, moving_time, distance,
                       total_elevation_gain, average_heartrate, average_watts,
                       tss, suffer_score
                FROM activities
                WHERE date(start_date) BETWEEN ? AND ?
                ORDER BY start_date
                """,
                (start, end),
            ).fetchall()
            for ar in arows:
                act_date = ar["start_date"][:10]
                events.append(
                    Event(
                        slug=f"activity-{ar['id']}",
                        kind=KIND_ACTIVITY,
                        date=act_date,
                        start_time=ar["start_date"][11:16] if len(ar["start_date"]) >= 16 else None,
                        duration_min=int(ar["moving_time"] / 60) if ar["moving_time"] else None,
                        name=ar["name"] or ar["sport_type"],
                        summary=ar["sport_type"],
                        estimated_tss=ar["tss"],
                        status=STATUS_COMPLETED,
                        payload={
                            "sport_type": ar["sport_type"],
                            "distance_m": ar["distance"],
                            "elev_m": ar["total_elevation_gain"],
                            "avg_hr": ar["average_heartrate"],
                            "avg_watts": ar["average_watts"],
                            "suffer": ar["suffer_score"],
                        },
                        activity_id=ar["id"],
                        source=("activities_table", str(ar["id"])),
                    )
                )

    # Conflict resolution: race events block training/untracked on the same date
    events = _resolve_conflicts(events)

    events.sort(key=lambda e: (e.date, e.start_time or "00:00"))
    return events


def _resolve_conflicts(events: list[Event]) -> list[Event]:
    """A race event on a date cancels any training/untracked event on the same date."""
    race_dates = {e.date for e in events if e.kind == KIND_RACE and e.status != STATUS_CANCELLED}
    if not race_dates:
        return events
    out: list[Event] = []
    for e in events:
        if (
            e.kind in (KIND_TRAINING, KIND_UNTRACKED, KIND_APPOINTMENT)
            and e.date in race_dates
            and e.status != STATUS_COMPLETED
        ):
            # Skip — superseded by a race event on this date
            continue
        out.append(e)
    return out


# ── Writes (low-level — high-level wrappers in tools/event_tools.py) ─────────


def upsert_event(event: Event) -> int:
    """Insert or update an event by slug. Returns the row id."""
    if event.kind not in ALL_KINDS:
        raise ValueError(f"unknown kind: {event.kind}")
    payload_json = json.dumps(event.payload, sort_keys=True) if event.payload else None
    now = datetime.now().isoformat(timespec="seconds")
    with get_conn() as conn:
        existing = conn.execute("SELECT id FROM events WHERE slug = ?", (event.slug,)).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE events SET
                    kind = ?, date = ?, start_time = ?, duration_min = ?,
                    name = ?, summary = ?, estimated_tss = ?, status = ?,
                    payload_json = ?, plan_id = ?, activity_id = ?, notes = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    event.kind,
                    event.date,
                    event.start_time,
                    event.duration_min,
                    event.name,
                    event.summary,
                    event.estimated_tss,
                    event.status,
                    payload_json,
                    event.plan_id,
                    event.activity_id,
                    event.notes,
                    now,
                    existing["id"],
                ),
            )
            return int(existing["id"])
        cur = conn.execute(
            """
            INSERT INTO events (
                slug, kind, date, start_time, duration_min, name, summary,
                estimated_tss, status, payload_json, plan_id, activity_id,
                notes, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                event.slug,
                event.kind,
                event.date,
                event.start_time,
                event.duration_min,
                event.name,
                event.summary,
                event.estimated_tss,
                event.status,
                payload_json,
                event.plan_id,
                event.activity_id,
                event.notes,
                now,
                now,
            ),
        )
        return int(cur.lastrowid or 0)


def update_event_payload(slug: str, key: str, value: Any) -> None:
    """Patch a single key inside payload_json. Used by per-section race tools."""
    ev = get_event(slug)
    if not ev:
        raise KeyError(f"event not found: {slug}")
    payload = dict(ev.payload)
    if value is None:
        payload.pop(key, None)
    else:
        payload[key] = value
    ev.payload = payload
    upsert_event(ev)


def delete_event(slug: str) -> bool:
    """Hard delete. Returns True if a row was removed."""
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM events WHERE slug = ?", (slug,))
        return cur.rowcount > 0


def _event_sport(name: str, summary: str | None, payload: dict) -> str | None:
    """Resolve a planned training event's sport (structured payload → text)."""
    from .plan_parser import resolve_sport

    structured = ""
    workout = payload.get("workout") if isinstance(payload, dict) else None
    if isinstance(workout, dict):
        structured = (workout.get("sport") or "").strip()
    return resolve_sport(
        structured_sport=structured or None,
        text=f"{name or ''} {summary or ''}",
    )


def link_completed_activities(*, on_date: str | None = None) -> dict:
    """Link past planned training events to the activity that fulfilled them.

    For each ``training`` event that is still ``planned``, unlinked, and dated on
    or before today (or exactly ``on_date`` if given), find same-date activities
    whose Strava sport matches the event's resolved sport. When exactly one
    candidate matches, set ``activity_id`` and mark the event ``completed``.

    The planned ``estimated_tss`` is left intact (it remains the *planned*
    number); the linked activity supplies the *actual* TSS via its own row. This
    is deliberately conservative: ambiguous days (0 or >1 sport matches) are
    skipped rather than guessed, and an activity is never linked to two events.

    Returns ``{linked, skipped_ambiguous, already_linked, candidates}``.
    """
    from .plan_parser import normalize_strava_sport

    today = Date.today().isoformat()
    cutoff = on_date or today

    linked = 0
    skipped_ambiguous = 0
    already_linked = 0
    candidates = 0

    with get_conn() as conn:
        if on_date is not None:
            ev_rows = conn.execute(
                "SELECT id, slug, date, name, summary, payload_json, activity_id, status "
                "FROM events WHERE kind='training' AND date = ?",
                (on_date,),
            ).fetchall()
        else:
            ev_rows = conn.execute(
                "SELECT id, slug, date, name, summary, payload_json, activity_id, status "
                "FROM events WHERE kind='training' AND date <= ?",
                (cutoff,),
            ).fetchall()

        # Activities already claimed by an event must not be linked twice.
        used = {
            r["activity_id"]
            for r in conn.execute(
                "SELECT activity_id FROM events WHERE activity_id IS NOT NULL"
            ).fetchall()
        }

        for ev in ev_rows:
            if ev["activity_id"] is not None:
                already_linked += 1
                continue
            if ev["status"] != STATUS_PLANNED:
                continue

            payload: dict[str, Any] = {}
            if ev["payload_json"]:
                try:
                    payload = json.loads(ev["payload_json"])
                except json.JSONDecodeError:
                    payload = {}
            want = _event_sport(ev["name"], ev["summary"], payload)
            if want in (None, "rest"):
                continue

            acts = conn.execute(
                "SELECT id, sport_type FROM activities WHERE substr(start_date,1,10) = ?",
                (ev["date"],),
            ).fetchall()
            matches = [
                a
                for a in acts
                if a["id"] not in used and normalize_strava_sport(a["sport_type"]) == want
            ]
            if not matches:
                continue
            candidates += 1
            if len(matches) != 1:
                skipped_ambiguous += 1
                continue

            act_id = matches[0]["id"]
            conn.execute(
                "UPDATE events SET activity_id = ?, status = ?, "
                "updated_at = datetime('now') WHERE id = ?",
                (act_id, STATUS_COMPLETED, ev["id"]),
            )
            used.add(act_id)
            linked += 1

    return {
        "linked": linked,
        "skipped_ambiguous": skipped_ambiguous,
        "already_linked": already_linked,
        "candidates": candidates,
    }


def date_has_event(d: str, kinds: Iterable[str] | None = None) -> bool:
    """Quick guard for date-validation in write tools."""
    placeholders = ""
    params: list[Any] = [d]
    if kinds:
        kinds_list = list(kinds)
        placeholders = " AND kind IN (" + ",".join(["?"] * len(kinds_list)) + ")"
        params.extend(kinds_list)
    with get_conn() as conn:
        row = conn.execute(
            f"SELECT 1 FROM events WHERE date = ?{placeholders} LIMIT 1",
            params,
        ).fetchone()
    return row is not None


# ── Race card schema helpers ─────────────────────────────────────────────────

RACE_PAYLOAD_KEYS = {
    "priority",  # 'A'|'B'|'C'
    "course",  # dict
    "goal",  # dict
    "key_principles",  # list[str]
    "pacing",  # list[dict]
    "climbs",  # list[dict] (cycling only)
    "warmup",  # list[dict]
    "nutrition",  # dict
    "logistics",  # dict
    "kit",  # dict
    "protocols",  # list[{title, body}]
    "yoy",  # dict {columns, rows}
    "readiness_gate",  # str
    "shoes",  # str (convenience top-level)
    "map_url",  # str
}


def empty_race_payload() -> dict[str, Any]:
    """Return an empty race-card payload skeleton."""
    return {
        "priority": "C",
        "course": {},
        "goal": {},
        "key_principles": [],
        "pacing": [],
        "warmup": [],
        "nutrition": {},
        "logistics": {},
        "kit": {},
        "protocols": [],
    }


def event_payload_hash(event: Event) -> str:
    """Public re-export for callers that need change detection (e.g. calendar sync)."""
    return _payload_hash(event)
