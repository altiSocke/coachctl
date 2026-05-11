"""
Legacy data migration — moves rows from pre-events-table sources into the
``events`` table. All functions are idempotent: they check for existing slugs
before inserting and skip rows that are already migrated.

Run via:
    coachctl migrate

Also called automatically by ``migrate_and_drop_legacy()`` at every ``bake``.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from datetime import date

logger = logging.getLogger(__name__)


def _slugify(text: str) -> str:
    """Convert a name to a URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:60]


def migrate_untracked_activities(conn: sqlite3.Connection) -> int:
    """
    Migrate rows from ``untracked_activities`` into the ``events`` table.

    Slug convention: ``untracked-{id}``
    Skips rows whose slug already exists in ``events``.

    Returns the number of rows inserted.
    """
    rows = conn.execute(
        """
        SELECT id, activity_date, sport, duration_min, intensity,
               tss_estimate, notes
        FROM untracked_activities
        ORDER BY activity_date
        """
    ).fetchall()

    inserted = 0
    now = date.today().isoformat()
    for r in rows:
        slug = f"untracked-{r['id']}"
        existing = conn.execute(
            "SELECT id FROM events WHERE slug = ?", (slug,)
        ).fetchone()
        if existing:
            continue

        payload = json.dumps(
            {
                "sport": r["sport"],
                "intensity": r["intensity"],
                "notes": r["notes"],
            },
            sort_keys=True,
        )
        conn.execute(
            """
            INSERT INTO events (
                slug, kind, date, name, summary, duration_min,
                estimated_tss, status, payload_json, notes,
                created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                slug,
                "untracked",
                r["activity_date"],
                r["sport"],
                f"{r['sport']} ({r['intensity']})",
                r["duration_min"],
                r["tss_estimate"],
                "completed",
                payload,
                r["notes"],
                now,
                now,
            ),
        )
        inserted += 1

    if inserted:
        logger.info("migrate_untracked_activities: inserted %d events", inserted)
    return inserted


def migrate_schedule_overrides(conn: sqlite3.Connection) -> int:
    """
    Apply ``schedule_overrides`` rows onto their corresponding ``events`` table
    training events.

    For each override, the matching event slug is ``plan-<stem>-<date>``
    (where stem = plan_file without the ``.md`` extension). If the event exists,
    its ``name``, ``payload_json``, and ``notes`` are updated to reflect the
    override. If the event doesn't exist (plan not yet in events table), the
    override is skipped.

    Returns the number of events updated.
    """
    rows = conn.execute(
        """
        SELECT plan_file, session_date, original_name,
               new_name, new_details, reason
        FROM schedule_overrides
        ORDER BY session_date
        """
    ).fetchall()

    updated = 0
    now = date.today().isoformat()
    for r in rows:
        stem = r["plan_file"]
        if stem.endswith(".md"):
            stem = stem[:-3]
        slug = f"plan-{stem}-{r['session_date']}"

        existing = conn.execute(
            "SELECT id, payload_json FROM events WHERE slug = ?", (slug,)
        ).fetchone()
        if not existing:
            logger.debug("migrate_schedule_overrides: no event for slug %s — skipping", slug)
            continue

        # Merge override into existing payload
        try:
            payload = json.loads(existing["payload_json"]) if existing["payload_json"] else {}
        except json.JSONDecodeError:
            payload = {}

        if r["new_details"]:
            payload["details"] = r["new_details"]
        payload["overridden"] = True
        if r["original_name"]:
            payload["original_name"] = r["original_name"]

        new_name = r["new_name"] if r["new_name"] else "Rest"
        conn.execute(
            """
            UPDATE events SET
                name = ?,
                payload_json = ?,
                notes = ?,
                updated_at = ?
            WHERE slug = ?
            """,
            (
                new_name,
                json.dumps(payload, sort_keys=True),
                r["reason"],
                now,
                slug,
            ),
        )
        updated += 1

    if updated:
        logger.info("migrate_schedule_overrides: updated %d events", updated)
    return updated


def migrate_athlete_yaml_events(conn: sqlite3.Connection) -> int:
    """
    Migrate races from ``athlete.yaml`` ``events:`` list into the ``events`` table.

    Slug convention: ``{date}-{slugified-name}``
    Skips entries whose slug already exists in ``events``.

    Returns the number of rows inserted.
    """
    try:
        from . import paths
        from .config import load_athlete
        cfg = load_athlete()
    except Exception as exc:
        logger.warning("migrate_athlete_yaml_events: could not load athlete.yaml: %s", exc)
        return 0

    yaml_events = cfg.get("events", [])
    if not yaml_events:
        return 0

    inserted = 0
    now = date.today().isoformat()
    for e in yaml_events:
        ev_date = e.get("date")
        name = e.get("name", "")
        if not ev_date or not name:
            continue
        if hasattr(ev_date, "isoformat"):
            ev_date = ev_date.isoformat()
        else:
            ev_date = str(ev_date)

        slug = f"{ev_date}-{_slugify(name)}"
        existing = conn.execute(
            "SELECT id FROM events WHERE slug = ?", (slug,)
        ).fetchone()
        if existing:
            continue

        payload = json.dumps(
            {
                "priority": e.get("priority", "C"),
                "goal_time": e.get("goal_time"),
                "goal": {},
                "course": {},
                "key_principles": [],
                "pacing": [],
                "warmup": [],
                "nutrition": {},
                "logistics": {},
                "kit": {},
                "protocols": [],
            },
            sort_keys=True,
        )
        conn.execute(
            """
            INSERT INTO events (
                slug, kind, date, name, status, payload_json,
                created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                slug,
                "race",
                ev_date,
                name,
                "planned",
                payload,
                now,
                now,
            ),
        )
        inserted += 1

    if inserted:
        logger.info("migrate_athlete_yaml_events: inserted %d race events", inserted)
    return inserted


def run_all(conn: sqlite3.Connection) -> str:
    """
    Run all three migrations in order. Idempotent — safe to call on every bake.
    Returns a human-readable summary string.
    """
    n_untracked = migrate_untracked_activities(conn)
    n_overrides = migrate_schedule_overrides(conn)
    n_races = migrate_athlete_yaml_events(conn)
    total = n_untracked + n_overrides + n_races
    if total == 0:
        return "Migration: nothing to migrate (all sources already in events table)."
    parts = []
    if n_untracked:
        parts.append(f"{n_untracked} untracked activit{'y' if n_untracked == 1 else 'ies'}")
    if n_overrides:
        parts.append(f"{n_overrides} schedule override{'s' if n_overrides != 1 else ''}")
    if n_races:
        parts.append(f"{n_races} race event{'s' if n_races != 1 else ''}")
    return f"Migration: migrated {', '.join(parts)}."
