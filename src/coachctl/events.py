"""
Calendar projection layer — the single source of truth for date-anchored items.

Every consumer that needs to know "what's on date X" reads from here:
  * bake / dashboard
  * coach agent (via `get_calendar_window` MCP tool)

Sources merged (in order of precedence on date conflict):
  1. ``events`` table, kind='race'  → race events (block training that day)
  2. ``events`` table, kind='training'/'untracked'/'appointment'
  3. ``schedule_overrides`` rows applied to plan-markdown sessions (legacy)
  4. ``plans/*.md`` parsed sessions (legacy, only if not yet migrated to ``events``)
  5. ``activities`` rows projected as kind='activity'
  6. ``untracked_activities`` rows projected as kind='untracked' (legacy)

Once migration to events-only is complete, sources 3, 4, 6 disappear.
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
    include_legacy: bool = True,
) -> list[Event]:
    """
    Return all events in [start, end] inclusive, sorted by (date, start_time).

    Parameters
    ----------
    start, end :
        ISO date strings or ``datetime.date`` objects.
    kinds :
        Filter to specific kinds. Default: all kinds.
    include_legacy :
        If True, also project plan-markdown sessions and untracked_activities
        rows that haven't been migrated into the ``events`` table.
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

        # Source 3 (legacy): untracked_activities, only if not already in events
        if include_legacy and KIND_UNTRACKED in kinds_set:
            existing_dates = {e.date for e in events if e.kind == KIND_UNTRACKED}
            urows = conn.execute(
                """
                SELECT id, activity_date, sport, duration_min, intensity,
                       tss_estimate, notes
                FROM untracked_activities
                WHERE activity_date BETWEEN ? AND ?
                ORDER BY activity_date
                """,
                (start, end),
            ).fetchall()
            for ur in urows:
                # avoid double-counting if migrated already (slug convention below)
                slug_guess = f"untracked-{ur['id']}"
                if any(e.slug == slug_guess for e in events):
                    continue
                events.append(
                    Event(
                        slug=slug_guess,
                        kind=KIND_UNTRACKED,
                        date=ur["activity_date"],
                        name=ur["sport"],
                        summary=f"{ur['sport']} ({ur['intensity']})",
                        duration_min=ur["duration_min"],
                        estimated_tss=ur["tss_estimate"],
                        status=STATUS_COMPLETED,
                        payload={
                            "sport": ur["sport"],
                            "intensity": ur["intensity"],
                            "notes": ur["notes"],
                        },
                        notes=ur["notes"],
                        source=("untracked_activities_legacy", str(ur["id"])),
                    )
                )

    # Source 4 (legacy): plan markdown + schedule_overrides — only training sessions
    # not yet present in events table for that date.
    if include_legacy and KIND_TRAINING in kinds_set:
        events.extend(_legacy_plan_training_events(start, end, existing=events))

    # Conflict resolution: race events block training/untracked on the same date
    events = _resolve_conflicts(events)

    events.sort(key=lambda e: (e.date, e.start_time or "00:00"))
    return events


def _legacy_plan_training_events(start: str, end: str, existing: list[Event]) -> list[Event]:
    """Project training sessions from plan markdown + overrides as Events."""
    from .plan_parser import get_latest_plan_path, parse_plan_file

    plan_path = get_latest_plan_path()
    if not plan_path:
        return []

    try:
        plan = parse_plan_file(plan_path)
    except Exception:
        return []

    # Load overrides keyed by date
    overrides: dict[str, dict] = {}
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT session_date, original_name, new_name, new_details, reason
            FROM schedule_overrides
            WHERE plan_file = ?
            """,
            (plan_path.name,),
        ).fetchall()
    for r in rows:
        overrides[r["session_date"]] = {
            "name": r["new_name"],
            "details": r["new_details"],
            "reason": r["reason"],
        }

    existing_by_date_kind = {(e.date, e.kind) for e in existing}
    out: list[Event] = []
    for w in plan.weeks:
        for s in w.sessions:
            if not s.date or s.date < start or s.date > end:
                continue
            ov = overrides.get(s.date)
            if ov:
                name = ov["name"] or "Rest"
                details = ov["details"] or ""
                notes = ov["reason"]
            else:
                name = s.name
                details = s.details
                notes = None
            if "rest" in (name or "").lower():
                continue
            slug = f"plan-{plan_path.stem}-{s.date}"
            # Skip if a training event already exists for this date in the events table
            if (s.date, KIND_TRAINING) in existing_by_date_kind:
                continue
            out.append(
                Event(
                    slug=slug,
                    kind=KIND_TRAINING,
                    date=s.date,
                    name=name,
                    summary=_first_line(details),
                    payload={
                        "details": details,
                        "week_number": w.number,
                        "phase": w.phase,
                    },
                    notes=notes,
                    source=("plan_markdown", plan_path.name),
                )
            )
    return out


def _first_line(text: str | None, max_len: int = 120) -> str | None:
    if not text:
        return None
    line = text.splitlines()[0].strip()
    return line if len(line) <= max_len else line[: max_len - 1] + "…"


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
