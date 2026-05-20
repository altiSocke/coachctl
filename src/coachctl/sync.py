"""
Strava OAuth2 + activity sync.

First-time setup:
    python -m coachctl.sync --auth

Subsequent syncs (incremental):
    python -m coachctl.sync
    python -m coachctl.sync --full   # re-pull everything
"""

import argparse
import json
import os
import secrets
import time
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
from dotenv import load_dotenv

from . import paths
from .db import get_conn, init_db
from .metrics import (
    compute_activity_metrics,
    compute_acwr,
    compute_fitness_series,
    compute_training_monotony,
    get_daily_tss_from_db,
)

STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_API_BASE = "https://www.strava.com/api/v3"
REDIRECT_URI = "http://localhost:8765/callback"
SCOPE = "activity:read_all"


def _load_env():
    """Load the active profile's .env into the process environment."""
    load_dotenv(paths.env_file(), override=True)


def _client_id() -> str:
    val = os.environ.get("STRAVA_CLIENT_ID", "")
    if not val:
        raise RuntimeError("STRAVA_CLIENT_ID is not set in .env — cannot authenticate with Strava.")
    return val


def _client_secret() -> str:
    val = os.environ.get("STRAVA_CLIENT_SECRET", "")
    if not val:
        raise RuntimeError(
            "STRAVA_CLIENT_SECRET is not set in .env — cannot authenticate with Strava."
        )
    return val


# ── OAuth helpers ─────────────────────────────────────────────────────────────


def get_access_token(refresh_token: str) -> str:
    """Exchange refresh token for a fresh access token."""
    _load_env()
    resp = httpx.post(
        STRAVA_TOKEN_URL,
        data={
            "client_id": _client_id(),
            "client_secret": _client_secret(),
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
    )
    resp.raise_for_status()
    data = resp.json()
    # Persist potentially-rotated refresh token
    _update_env_file("STRAVA_REFRESH_TOKEN", data["refresh_token"])
    return data["access_token"]


def get_strava_access_token() -> str:
    """Load refresh token from profile .env and exchange for a fresh access token."""
    _load_env()
    refresh_token = os.environ.get("STRAVA_REFRESH_TOKEN")
    if not refresh_token:
        raise RuntimeError("No STRAVA_REFRESH_TOKEN in .env — run sync_activities --auth first.")
    return get_access_token(refresh_token)


def _update_env_file(key: str, value: str):
    """Update a single key in the active profile's .env file (atomic write)."""
    env = paths.env_file()
    if not env.exists():
        tmp = env.with_suffix(".tmp")
        tmp.write_text(f"{key}={value}\n")
        tmp.replace(env)
        return
    lines = env.read_text().splitlines()
    updated = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}"
            updated = True
            break
    if not updated:
        lines.append(f"{key}={value}")
    tmp = env.with_suffix(".tmp")
    tmp.write_text("\n".join(lines) + "\n")
    tmp.replace(env)


def do_auth_flow():
    """Interactive OAuth flow — opens browser, captures code via local server."""
    _load_env()
    state_nonce = secrets.token_urlsafe(16)
    auth_url = (
        f"{STRAVA_AUTH_URL}?client_id={_client_id()}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code&scope={SCOPE}"
        f"&approval_prompt=force"
        f"&state={state_nonce}"
    )
    print(f"\nOpening Strava authorisation...\n{auth_url}\n")
    webbrowser.open(auth_url)

    code_holder: dict = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            params = parse_qs(urlparse(self.path).query)
            returned_state = params.get("state", [None])[0]
            if returned_state != state_nonce:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"<h2>Invalid state parameter - possible CSRF. Please retry.</h2>")
                return
            code_holder["code"] = params.get("code", [None])[0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"<h2>Authorised! You can close this tab.</h2>")

        def log_message(self, *args):
            pass  # suppress server logs

    server = HTTPServer(("localhost", 8765), Handler)
    server.handle_request()

    code = code_holder.get("code")
    if not code:
        raise RuntimeError("No auth code received from Strava.")

    resp = httpx.post(
        STRAVA_TOKEN_URL,
        data={
            "client_id": _client_id(),
            "client_secret": _client_secret(),
            "code": code,
            "grant_type": "authorization_code",
        },
    )
    resp.raise_for_status()
    data = resp.json()

    _update_env_file("STRAVA_REFRESH_TOKEN", data["refresh_token"])
    print(f"\nAuthorisation successful! Refresh token saved to {paths.env_file()}")
    print(f"Athlete: {data['athlete']['firstname']} {data['athlete']['lastname']}")
    return data["access_token"]


# ── Strava API ────────────────────────────────────────────────────────────────


def fetch_activities(access_token: str, after: int | None = None, per_page: int = 100):
    """Yield all activities, paginated. Retries up to 3 times on transient errors."""
    page = 1
    headers = {"Authorization": f"Bearer {access_token}"}
    while True:
        params = {"per_page": per_page, "page": page}
        if after:
            params["after"] = after
        for attempt in range(3):
            try:
                resp = httpx.get(
                    f"{STRAVA_API_BASE}/athlete/activities",
                    headers=headers,
                    params=params,
                    timeout=30,
                )
                resp.raise_for_status()
                break
            except (httpx.HTTPStatusError, httpx.TransportError) as exc:
                if attempt == 2:
                    raise
                wait = 2**attempt
                print(f"  Retrying page {page} after {wait}s ({exc})...")
                time.sleep(wait)
        batch = resp.json()
        if not batch:
            break
        yield from batch
        page += 1
        time.sleep(0.3)  # respect rate limit (~100 req/15min)


def fetch_activity_streams(access_token: str, activity_id: int) -> dict:
    """Fetch time-series streams for power curve / pace analysis."""
    headers = {"Authorization": f"Bearer {access_token}"}
    keys = "time,heartrate,watts,velocity_smooth,altitude,cadence"
    resp = httpx.get(
        f"{STRAVA_API_BASE}/activities/{activity_id}/streams",
        headers=headers,
        params={"keys": keys, "key_by_type": "true"},
    )
    if resp.status_code == 404:
        return {}
    resp.raise_for_status()
    return resp.json()


def fetch_activity_laps(access_token: str, activity_id: int) -> list[dict]:
    """Fetch lap data for an activity from the Strava API."""
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = httpx.get(
        f"{STRAVA_API_BASE}/activities/{activity_id}/laps",
        headers=headers,
    )
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    return resp.json()


# ── Routes ────────────────────────────────────────────────────────────────────


def fetch_athlete_routes(access_token: str, per_page: int = 50) -> list[dict]:
    """List the authenticated athlete's saved routes."""
    headers = {"Authorization": f"Bearer {access_token}"}
    # Need athlete ID first
    resp = httpx.get(f"{STRAVA_API_BASE}/athlete", headers=headers)
    resp.raise_for_status()
    athlete_id = resp.json()["id"]

    routes: list[dict] = []
    page = 1
    while True:
        resp = httpx.get(
            f"{STRAVA_API_BASE}/athletes/{athlete_id}/routes",
            headers=headers,
            params={"per_page": per_page, "page": page},
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        routes.extend(batch)
        page += 1
        time.sleep(0.3)
    return routes


def fetch_route(access_token: str, route_id: int) -> dict:
    """Get detailed route info by ID."""
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = httpx.get(f"{STRAVA_API_BASE}/routes/{route_id}", headers=headers)
    resp.raise_for_status()
    return resp.json()


def fetch_route_streams(access_token: str, route_id: int) -> dict:
    """Fetch altitude/distance/latlng streams for a route."""
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = httpx.get(
        f"{STRAVA_API_BASE}/routes/{route_id}/streams",
        headers=headers,
    )
    if resp.status_code == 404:
        return {}
    resp.raise_for_status()
    # Route streams return as a list of stream objects, convert to dict keyed by type
    data = resp.json()
    if isinstance(data, list):
        return {s["type"]: s for s in data}
    return data


# ── Upsert activity ───────────────────────────────────────────────────────────


def upsert_activity(conn, activity: dict, streams: dict | None = None, athlete: dict | None = None):
    """Insert or replace an activity with computed metrics.

    Parameters
    ----------
    athlete : dict | None
        Athlete config (from ``load_athlete()``). Pass once per sync batch to
        avoid re-reading athlete.yaml for every activity.
    """
    metrics = compute_activity_metrics(activity, streams, athlete=athlete)

    conn.execute(
        """
        INSERT INTO activities (
            id, name, sport_type, start_date, elapsed_time, moving_time,
            distance, total_elevation_gain, average_speed, max_speed,
            average_heartrate, max_heartrate, average_watts, weighted_avg_watts,
            average_cadence, suffer_score,
            tss, np, intensity_factor, hrss, rtss, ngp, rtss_power, raw_json
        ) VALUES (
            :id, :name, :sport_type, :start_date, :elapsed_time, :moving_time,
            :distance, :total_elevation_gain, :average_speed, :max_speed,
            :average_heartrate, :max_heartrate, :average_watts, :weighted_avg_watts,
            :average_cadence, :suffer_score,
            :tss, :np, :intensity_factor, :hrss, :rtss, :ngp, :rtss_power, :raw_json
        )
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,
            sport_type=excluded.sport_type,
            start_date=excluded.start_date,
            elapsed_time=excluded.elapsed_time,
            moving_time=excluded.moving_time,
            distance=excluded.distance,
            total_elevation_gain=excluded.total_elevation_gain,
            average_speed=excluded.average_speed,
            max_speed=excluded.max_speed,
            average_heartrate=excluded.average_heartrate,
            max_heartrate=excluded.max_heartrate,
            average_watts=excluded.average_watts,
            weighted_avg_watts=excluded.weighted_avg_watts,
            average_cadence=excluded.average_cadence,
            suffer_score=excluded.suffer_score,
            tss=excluded.tss, np=excluded.np,
            intensity_factor=excluded.intensity_factor, hrss=excluded.hrss,
            rtss=excluded.rtss, ngp=excluded.ngp,
            rtss_power=excluded.rtss_power,
            raw_json=excluded.raw_json,
            synced_at=datetime('now')
    """,
        {
            **{
                k: activity.get(k)
                for k in [
                    "id",
                    "name",
                    "elapsed_time",
                    "moving_time",
                    "distance",
                    "total_elevation_gain",
                    "average_speed",
                    "max_speed",
                    "average_heartrate",
                    "max_heartrate",
                    "average_watts",
                    "average_cadence",
                    "suffer_score",
                ]
            },
            "weighted_avg_watts": activity.get("weighted_average_watts"),
            "sport_type": activity.get("sport_type") or activity.get("type", "Unknown"),
            "start_date": activity.get("start_date"),
            "raw_json": json.dumps(activity),
            **metrics,
        },
    )


# ── Main sync ─────────────────────────────────────────────────────────────────


def sync(full: bool = False, access_token: str | None = None):
    """Pull activities from Strava into SQLite."""
    init_db()

    if not access_token:
        # Re-read profile .env to pick up any freshly-written refresh token
        _load_env()
        refresh_token = os.environ.get("STRAVA_REFRESH_TOKEN")
        if not refresh_token:
            raise RuntimeError("No STRAVA_REFRESH_TOKEN in .env — run with --auth first.")
        access_token = get_access_token(refresh_token)

    with get_conn() as conn:
        after = None
        if not full:
            row = conn.execute(
                "SELECT value FROM sync_state WHERE key='last_sync_epoch'"
            ).fetchone()
            if row:
                after = int(row["value"])

        count = 0
        from .config import load_athlete as _load_athlete

        athlete_cfg = _load_athlete()  # load once for entire sync batch
        for activity in fetch_activities(access_token, after=after):
            upsert_activity(conn, activity, athlete=athlete_cfg)
            count += 1
            if count % 20 == 0:
                print(f"  synced {count} activities...")

        # Update last sync timestamp
        conn.execute(
            """
            INSERT INTO sync_state(key, value) VALUES('last_sync_epoch', :ts)
            ON CONFLICT(key) DO UPDATE SET value=:ts
        """,
            {"ts": str(int(time.time()))},
        )

    # Recompute and persist CTL/ATL/TSB for all sport categories
    _refresh_fitness_table()

    print(f"Sync complete — {count} activities processed.")


def _refresh_fitness_table():
    """
    Rebuild the full daily athlete-metrics series and write to the ``fitness`` table.

    For each sport_category ('all', 'run', 'ride') and every day in the series,
    computes and persists:
      - ctl, atl, tsb, tss  (fitness model)
      - acwr_rolling, acwr_ema, acwr_risk_zone  (injury risk)
      - monotony, strain  (training monotony / Foster 1998)

    All three series are computed from ``daily_tss`` in a single pass and joined
    by date before the batch upsert.  The table is fully rebuilt on every call
    (ON CONFLICT … DO UPDATE), so it is always consistent with the activity data.

    Called automatically at the end of ``sync()`` and ``recalculate_activity_metrics()``.
    """
    from datetime import date as _date

    with get_conn() as conn:
        for category in ("all", "run", "ride"):
            daily_tss = get_daily_tss_from_db(conn, category)
            if not daily_tss:
                continue

            # ── Series 1: fitness (CTL/ATL/TSB/daily TSS) ────────────────────
            fitness_series = compute_fitness_series(daily_tss)
            # Index by date string for O(1) merge
            fitness_by_date = {row["date"]: row for row in fitness_series}

            # ── Series 2: ACWR (per day) ──────────────────────────────────────
            # We need a daily ACWR value for every day in the series.
            # compute_acwr() returns today's value; we need to compute it for
            # every historical date by slicing the daily_tss dict up to that date.
            # For performance: build rolling cumulative slices using a deque.
            from collections import deque
            from datetime import timedelta as _td

            all_dates_sorted = sorted(daily_tss.keys())
            series_start = all_dates_sorted[0]
            series_end = _date.today()

            acwr_by_date: dict[str, dict] = {}
            current = series_start
            while current <= series_end:
                # Slice daily_tss up to and including current date, then compute
                # ACWR relative to that date (not today) so historical values
                # reflect the actual load state on each past day.
                tss_slice = {d: v for d, v in daily_tss.items() if d <= current}
                acwr_result = compute_acwr(tss_slice, reference_date=current)
                acwr_by_date[current.isoformat()] = acwr_result
                current += _td(days=1)

            # ── Series 3: Monotony & Strain ───────────────────────────────────
            monotony_series = compute_training_monotony(daily_tss, window=7)
            monotony_by_date = {row["date"]: row for row in monotony_series}

            # ── Merge and upsert ──────────────────────────────────────────────
            rows = []
            for fit in fitness_series:
                d = fit["date"]
                acwr = acwr_by_date.get(d, {})
                mono = monotony_by_date.get(d, {})
                rows.append(
                    (
                        d,
                        category,
                        fit["ctl"],
                        fit["atl"],
                        fit["tsb"],
                        fit["tss"],
                        acwr.get("acwr_rolling"),
                        acwr.get("acwr_ema"),
                        acwr.get("risk_zone"),
                        mono.get("monotony"),
                        mono.get("strain"),
                    )
                )

            conn.executemany(
                """
                INSERT INTO fitness (
                    date, sport_category,
                    ctl, atl, tsb, tss,
                    acwr_rolling, acwr_ema, acwr_risk_zone,
                    monotony, strain
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(date, sport_category) DO UPDATE SET
                    ctl             = excluded.ctl,
                    atl             = excluded.atl,
                    tsb             = excluded.tsb,
                    tss             = excluded.tss,
                    acwr_rolling    = excluded.acwr_rolling,
                    acwr_ema        = excluded.acwr_ema,
                    acwr_risk_zone  = excluded.acwr_risk_zone,
                    monotony        = excluded.monotony,
                    strain          = excluded.strain
                """,
                rows,
            )

    print("Fitness table updated (CTL/ATL/TSB + ACWR + Monotony).")


def recalculate_activity_metrics(verbose: bool = False) -> int:
    """
    Recompute all per-activity metrics from stored ``raw_json`` and write back
    to the ``activities`` table.  No Strava API call required.

    Uses the current ``compute_activity_metrics()`` formula, so running this
    after a formula change (new NGP model, FTP update, etc.) brings the whole
    history into sync.

    Returns the number of activities updated.
    """
    from .config import load_athlete as _load_athlete

    athlete = _load_athlete()

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, raw_json
            FROM activities
            WHERE raw_json IS NOT NULL
            ORDER BY start_date
            """
        ).fetchall()

        if not rows:
            if verbose:
                print("No activities with raw_json found — nothing to recompute.")
            return 0

        updates: list[tuple] = []
        for row in rows:
            try:
                activity = json.loads(row["raw_json"])
            except (json.JSONDecodeError, TypeError):
                continue  # corrupt blob — skip silently

            m = compute_activity_metrics(activity, athlete=athlete)
            updates.append(
                (
                    m["tss"],
                    m["np"],
                    m["intensity_factor"],
                    m["hrss"],
                    m["rtss"],
                    m["ngp"],
                    m["rtss_power"],
                    row["id"],
                )
            )

        conn.executemany(
            """
            UPDATE activities
            SET tss             = ?,
                np              = ?,
                intensity_factor = ?,
                hrss            = ?,
                rtss            = ?,
                ngp             = ?,
                rtss_power      = ?
            WHERE id = ?
            """,
            updates,
        )

    n = len(updates)
    if verbose:
        print(f"Recomputed metrics for {n} activities.")

    # Rebuild the daily fitness/ACWR/monotony table from fresh per-activity values.
    _refresh_fitness_table()
    return n


def main():
    parser = argparse.ArgumentParser(description="Sync Strava activities")
    parser.add_argument("--auth", action="store_true", help="Run OAuth flow")
    parser.add_argument("--full", action="store_true", help="Re-sync all activities")
    args = parser.parse_args()

    if args.auth:
        token = do_auth_flow()
        sync(full=args.full, access_token=token)
    else:
        sync(full=args.full)


if __name__ == "__main__":
    main()
