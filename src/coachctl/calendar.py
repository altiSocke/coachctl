"""
Google Calendar integration — push training sessions as calendar events.

Auth flow mirrors Strava's pattern: OAuth2 user consent, tokens stored in .env.
"""

from __future__ import annotations

import hashlib
import http.server
import json
import os
import threading
import webbrowser
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import paths
from .db import get_conn, init_db
from .plan_parser import Plan, Session, get_latest_plan_path, parse_plan_file
from .sync import _update_env_file


# ── Auth ──────────────────────────────────────────────────────────────────────

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
REDIRECT_URI = "http://localhost:8766/callback"


def _get_google_credentials() -> dict:
    """Load Google OAuth credentials from environment."""
    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")
    refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN", "")
    calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "primary")
    if not client_id or not client_secret:
        raise RuntimeError(
            "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set in your profile .env file.\n"
            "Create OAuth 2.0 credentials at https://console.cloud.google.com/apis/credentials"
        )
    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "calendar_id": calendar_id,
    }


def _get_access_token() -> str:
    """Exchange refresh token for access token."""
    import httpx

    creds = _get_google_credentials()
    if not creds["refresh_token"]:
        raise RuntimeError("No GOOGLE_REFRESH_TOKEN. Run calendar_auth() first.")

    resp = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": creds["client_id"],
            "client_secret": creds["client_secret"],
            "refresh_token": creds["refresh_token"],
            "grant_type": "refresh_token",
        },
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def do_google_auth() -> str:
    """Run OAuth2 consent flow for Google Calendar. Returns refresh token."""
    import httpx

    creds = _get_google_credentials()
    auth_code = None

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            nonlocal auth_code
            qs = parse_qs(urlparse(self.path).query)
            auth_code = qs.get("code", [None])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>Auth complete! You can close this tab.</h1>")

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("localhost", 8766), Handler)
    thread = threading.Thread(target=server.handle_request)
    thread.start()

    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={creds['client_id']}"
        f"&redirect_uri={REDIRECT_URI}"
        "&response_type=code"
        f"&scope={'%20'.join(SCOPES)}"
        "&access_type=offline"
        "&prompt=consent"
    )
    print(f"Opening browser for Google auth: {auth_url}")
    webbrowser.open(auth_url)
    thread.join(timeout=120)
    server.server_close()

    if not auth_code:
        raise RuntimeError("No authorization code received")

    # Exchange code for tokens
    resp = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": creds["client_id"],
            "client_secret": creds["client_secret"],
            "code": auth_code,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        },
    )
    resp.raise_for_status()
    tokens = resp.json()
    refresh_token = tokens.get("refresh_token", "")

    # Persist refresh token to .env
    if refresh_token:
        _update_env_file("GOOGLE_REFRESH_TOKEN", refresh_token)

    return refresh_token


# ── Calendar sync ─────────────────────────────────────────────────────────────


def _session_hash(session_date: str, title: str, details: str) -> str:
    """Deterministic hash for diffing calendar events."""
    content = f"{session_date}|{title}|{details}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def _build_event(session: Session, plan_title: str) -> dict:
    """Build a Google Calendar event body from a session."""
    if not session.date:
        return {}

    # Determine if this is a rest day
    is_rest = "rest" in session.name.lower()
    if is_rest:
        return {}

    summary = f"🏋️ {session.name}"
    description = session.details
    if plan_title:
        description += f"\n\n📋 {plan_title}"

    return {
        "summary": summary,
        "description": description,
        "start": {"date": session.date},
        "end": {"date": session.date},
        "transparency": "transparent",  # Don't block time
        "reminders": {"useDefault": False, "overrides": []},
    }


def _build_race_event(event_config: dict) -> dict:
    """Build a calendar event for a race/target event from athlete.yaml."""
    return {
        "summary": f"🏁 {event_config['name']}",
        "description": (
            f"Priority: {event_config.get('priority', 'A')}\n"
            f"Goal: {event_config.get('goal_time', '')}\n"
            f"Pace: {event_config.get('goal_pace_per_km', '')}\n"
            f"{event_config.get('notes', '')}"
        ),
        "start": {"date": event_config["date"]},
        "end": {"date": event_config["date"]},
        "colorId": "11",  # Red for races
        "transparency": "opaque",
    }


def sync_calendar(horizon_days: int = 7) -> dict:
    """
    Push training sessions to Google Calendar.

    - Races/events from athlete.yaml: always pushed regardless of horizon
    - Training sessions: pushed for the next `horizon_days` days
    - Use horizon_days=0 for races only, or a large number for full plan

    Returns summary of created/updated/deleted events.
    """
    import httpx

    from .config import load_athlete

    init_db()
    access_token = _get_access_token()
    creds = _get_google_credentials()
    calendar_id = creds["calendar_id"]
    base_url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

    plan_path = get_latest_plan_path()
    if not plan_path:
        return {"error": "No training plan found"}

    plan = parse_plan_file(plan_path)
    athlete = load_athlete()
    today = date.today()
    horizon_end = today + timedelta(days=horizon_days) if horizon_days > 0 else None

    # Collect sessions to push
    events_to_push: list[tuple[str, str, dict]] = []  # (date, hash, event_body)

    # 1. Races/events — always
    for evt in athlete.get("events", []):
        if evt.get("date"):
            event_body = _build_race_event(evt)
            h = _session_hash(evt["date"], evt["name"], "race")
            events_to_push.append((evt["date"], h, event_body))

    # 2. Training sessions within horizon
    for week in plan.weeks:
        for session in week.sessions:
            if not session.date:
                continue
            session_date = date.fromisoformat(session.date)
            # Skip past sessions
            if session_date < today:
                continue
            # Skip if beyond horizon (unless horizon is None = full plan)
            if horizon_end and session_date > horizon_end:
                continue
            event_body = _build_event(session, plan.title)
            if not event_body:
                continue
            h = _session_hash(session.date, session.name, session.details)
            events_to_push.append((session.date, h, event_body))

    # Load existing pushed events from DB
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT activity_date, session_hash, google_event_id FROM calendar_events"
        ).fetchall()
    existing_map = {(r["activity_date"], r["session_hash"]): r["google_event_id"] for r in existing}

    created = 0
    updated = 0
    skipped = 0

    with httpx.Client(headers=headers, timeout=30) as client:
        for evt_date, evt_hash, event_body in events_to_push:
            key = (evt_date, evt_hash)
            if key in existing_map:
                # Already pushed with same hash — skip
                skipped += 1
                continue

            # Check if there's an old event for this date with different hash — update
            old_event_id = None
            with get_conn() as conn:
                old = conn.execute(
                    "SELECT id, google_event_id FROM calendar_events WHERE activity_date = ? AND session_hash != ?",
                    (evt_date, evt_hash),
                ).fetchone()
                if old:
                    old_event_id = old["google_event_id"]

            if old_event_id:
                # Update existing event
                resp = client.patch(f"{base_url}/{old_event_id}", json=event_body)
                if resp.status_code in (200, 201):
                    with get_conn() as conn:
                        conn.execute(
                            "UPDATE calendar_events SET session_title=?, session_hash=?, pushed_at=datetime('now') WHERE google_event_id=?",
                            (event_body.get("summary", ""), evt_hash, old_event_id),
                        )
                    updated += 1
                else:
                    # If update fails (deleted externally), create new
                    resp = client.post(base_url, json=event_body)
                    if resp.status_code in (200, 201):
                        new_id = resp.json()["id"]
                        with get_conn() as conn:
                            conn.execute(
                                "DELETE FROM calendar_events WHERE google_event_id=?",
                                (old_event_id,),
                            )
                            conn.execute(
                                "INSERT INTO calendar_events (activity_date, session_title, session_hash, google_event_id, calendar_id) VALUES (?,?,?,?,?)",
                                (
                                    evt_date,
                                    event_body.get("summary", ""),
                                    evt_hash,
                                    new_id,
                                    calendar_id,
                                ),
                            )
                        created += 1
            else:
                # Create new event
                resp = client.post(base_url, json=event_body)
                if resp.status_code in (200, 201):
                    new_id = resp.json()["id"]
                    with get_conn() as conn:
                        conn.execute(
                            "INSERT INTO calendar_events (activity_date, session_title, session_hash, google_event_id, calendar_id) VALUES (?,?,?,?,?)",
                            (
                                evt_date,
                                event_body.get("summary", ""),
                                evt_hash,
                                new_id,
                                calendar_id,
                            ),
                        )
                    created += 1

    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "total_pushed": len(events_to_push),
    }


def clear_calendar() -> dict:
    """Delete all agent-created events from Google Calendar."""
    import httpx

    init_db()
    access_token = _get_access_token()
    creds = _get_google_credentials()
    calendar_id = creds["calendar_id"]
    base_url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
    headers = {"Authorization": f"Bearer {access_token}"}

    with get_conn() as conn:
        rows = conn.execute("SELECT google_event_id FROM calendar_events").fetchall()

    deleted = 0
    with httpx.Client(headers=headers, timeout=30) as client:
        for row in rows:
            resp = client.delete(f"{base_url}/{row['google_event_id']}")
            if resp.status_code in (200, 204, 410):  # 410 = already deleted
                deleted += 1

    with get_conn() as conn:
        conn.execute("DELETE FROM calendar_events")

    return {"deleted": deleted}
