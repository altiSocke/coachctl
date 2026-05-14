"""
SQLite database layer — schema creation and core queries.
Database path resolves to ``<DATA_ROOT>/data/activities.db`` (see ``paths.db_path``).
"""

import logging
import sqlite3
from contextlib import contextmanager

from . import paths

logger = logging.getLogger(__name__)

_DB_INITIALISED = False


@contextmanager
def get_conn():
    conn = sqlite3.connect(paths.db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create all tables if they don't exist. Idempotent — safe to call multiple times."""
    global _DB_INITIALISED
    if _DB_INITIALISED:
        return
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS activities (
                id              INTEGER PRIMARY KEY,   -- Strava activity ID
                name            TEXT NOT NULL,
                sport_type      TEXT NOT NULL,         -- Run, Ride, VirtualRide, etc.
                start_date      TEXT NOT NULL,         -- ISO8601 UTC
                elapsed_time    INTEGER,               -- seconds
                moving_time     INTEGER,               -- seconds
                distance        REAL,                  -- metres
                total_elevation_gain REAL,             -- metres
                average_speed   REAL,                  -- m/s
                max_speed       REAL,
                average_heartrate REAL,
                max_heartrate   REAL,
                average_watts   REAL,                  -- cycling power
                weighted_avg_watts REAL,               -- NP proxy from Strava
                average_cadence REAL,
                suffer_score    INTEGER,               -- Strava suffer score
                -- computed metrics stored after sync
                tss             REAL,                  -- Training Stress Score
                np              REAL,                  -- Normalised Power (cycling)
                intensity_factor REAL,                 -- IF = NP/FTP
                hrss            REAL,                  -- HR-based TSS
                rtss            REAL,                  -- Running TSS
                ngp             REAL,                  -- Normalised Graded Pace (m/s)
                raw_json        TEXT,                  -- full Strava JSON blob
                synced_at       TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_activities_start_date
                ON activities(start_date);
            CREATE INDEX IF NOT EXISTS idx_activities_sport_type
                ON activities(sport_type);

            CREATE TABLE IF NOT EXISTS fitness (
                -- Daily snapshot of CTL/ATL/TSB per sport category
                date            TEXT NOT NULL,
                sport_category  TEXT NOT NULL,         -- 'all', 'run', 'ride'
                ctl             REAL,                  -- chronic training load (42-day)
                atl             REAL,                  -- acute training load (7-day)
                tsb             REAL,                  -- form = CTL - ATL
                PRIMARY KEY (date, sport_category)
            );

            CREATE TABLE IF NOT EXISTS feedback (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_date   TEXT NOT NULL,         -- YYYY-MM-DD
                activity_id     INTEGER REFERENCES activities(id),
                rpe             INTEGER,               -- 1-10
                felt            TEXT,                  -- 'great','good','ok','bad','terrible'
                notes           TEXT,
                created_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS sync_state (
                key             TEXT PRIMARY KEY,
                value           TEXT
            );

            CREATE TABLE IF NOT EXISTS untracked_activities (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_date   TEXT NOT NULL,             -- YYYY-MM-DD
                sport           TEXT NOT NULL,             -- e.g. 'hockey', 'gym', 'yoga'
                duration_min    INTEGER,                   -- minutes
                intensity       TEXT DEFAULT 'moderate',  -- 'easy','moderate','hard','race'
                tss_estimate    REAL,                      -- manually estimated or auto-computed
                notes           TEXT,
                created_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_untracked_date
                ON untracked_activities(activity_date);

            CREATE TABLE IF NOT EXISTS untracked_checkins (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                week_start      TEXT NOT NULL UNIQUE,      -- YYYY-MM-DD (Monday of the week)
                checked_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS activity_streams (
                activity_id     INTEGER PRIMARY KEY REFERENCES activities(id),
                streams_json    TEXT NOT NULL,          -- cached Strava streams response
                fetched_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS readiness_checkins (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                checkin_date    TEXT NOT NULL UNIQUE,   -- YYYY-MM-DD
                sleep           INTEGER,                -- 1-5 (1=terrible, 5=great)
                energy          INTEGER,                -- 1-5 (1=exhausted, 5=great)
                soreness        INTEGER,                -- 1-5 (1=very sore, 5=fresh legs)
                notes           TEXT,
                created_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_readiness_checkins_date
                ON readiness_checkins(checkin_date);

            CREATE TABLE IF NOT EXISTS schedule_overrides (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_file     TEXT NOT NULL,   -- basename of plan .md file
                session_date  TEXT NOT NULL,   -- YYYY-MM-DD
                original_name TEXT,            -- original session name from plan
                new_name      TEXT,            -- NULL = session dropped / rest day
                new_details   TEXT,            -- replacement details text
                reason        TEXT,            -- e.g. "traveling", "fatigue"
                created_at    TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_overrides_plan_date
                ON schedule_overrides(plan_file, session_date);

            -- ── Calendar (single source of truth for date-anchored items) ──
            -- Plans are versioned overview snapshots. Live training-session
            -- truth is the rows in `events` referencing this plan_id.
            CREATE TABLE IF NOT EXISTS plans (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                slug            TEXT UNIQUE NOT NULL,    -- e.g. 'half-marathon-1h35-2026'
                title           TEXT,
                start_date      TEXT,                    -- ISO YYYY-MM-DD
                end_date        TEXT,                    -- ISO YYYY-MM-DD
                active          INTEGER DEFAULT 1,       -- 1 = current plan
                overview_md     TEXT,                    -- high-level narrative (phases, focus, goals)
                source_md_path  TEXT,                    -- archive path under profile/plans/
                created_at      TEXT NOT NULL DEFAULT (datetime('now'))
            );

            -- Events: one row per scheduled or logged date-anchored item.
            -- kind in ('race','training','untracked','appointment').
            -- payload_json holds kind-specific structured content (race card,
            -- intervals, etc). status in ('planned','completed','cancelled').
            CREATE TABLE IF NOT EXISTS events (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                slug            TEXT UNIQUE NOT NULL,
                kind            TEXT NOT NULL,
                date            TEXT NOT NULL,            -- ISO YYYY-MM-DD
                start_time      TEXT,                     -- HH:MM (local)
                duration_min    INTEGER,
                name            TEXT NOT NULL,
                summary         TEXT,
                estimated_tss   REAL,
                status          TEXT DEFAULT 'planned',
                payload_json    TEXT,                     -- JSON, kind-specific
                plan_id         INTEGER REFERENCES plans(id),
                activity_id     INTEGER REFERENCES activities(id),
                notes           TEXT,
                created_at      TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_events_date ON events(date);
            CREATE INDEX IF NOT EXISTS idx_events_kind ON events(kind);
            CREATE INDEX IF NOT EXISTS idx_events_status ON events(status);

            -- Manual TSS overrides for activities that lack power/HR data.
            -- COALESCE(o.tss_override, a.tss) in metrics queries gives these
            -- priority over the computed tss column without touching activity rows.
            CREATE TABLE IF NOT EXISTS activity_overrides (
                activity_id   INTEGER PRIMARY KEY REFERENCES activities(id),
                tss_override  REAL,                        -- manually assigned TSS
                notes         TEXT,                        -- reason / source
                updated_at    TEXT DEFAULT (datetime('now'))
            );

            -- ── Best Efforts cache ───────────────────────────────────────────
            -- One row per (sport, effort_type) — always the athlete's all-time best.
            -- Populated lazily by compute_best_efforts(); invalidated when new
            -- activities arrive (computed_at < MAX(activities.synced_at)).
            -- effort_type values:
            --   Running pace:  'pace_1km','pace_5km','pace_10km','pace_half','pace_marathon'
            --   Cycling power: 'power_5s','power_30s','power_1min','power_5min',
            --                  'power_20min','power_60min'
            CREATE TABLE IF NOT EXISTS best_efforts (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                sport           TEXT NOT NULL,          -- 'run' or 'ride'
                effort_type     TEXT NOT NULL,          -- see above
                activity_id     INTEGER REFERENCES activities(id),
                activity_date   TEXT NOT NULL,          -- YYYY-MM-DD of the best effort
                value           REAL NOT NULL,          -- sec/km (pace) or watts (power)
                value_per_kg    REAL,                   -- W/kg for power efforts (NULL for pace)
                season_activity_id  INTEGER REFERENCES activities(id),
                season_date         TEXT,               -- YYYY-MM-DD of current-season best
                season_value        REAL,               -- season best value (same units as value)
                season_value_per_kg REAL,
                computed_at     TEXT DEFAULT (datetime('now'))
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_best_efforts_type
                ON best_efforts(sport, effort_type);
        """)

        # Idempotent column additions (ALTER TABLE IF NOT EXISTS not supported in older SQLite)
        existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(activities)").fetchall()}
        if "reviewed_at" not in existing_cols:
            conn.execute("ALTER TABLE activities ADD COLUMN reviewed_at TEXT")
        if "rtss_power" not in existing_cols:
            conn.execute(
                "ALTER TABLE activities ADD COLUMN rtss_power REAL"
            )  # power-based running TSS

        plans_cols = {row[1] for row in conn.execute("PRAGMA table_info(plans)").fetchall()}
        if "week_tss_json" not in plans_cols:
            conn.execute("ALTER TABLE plans ADD COLUMN week_tss_json TEXT")

        # ── fitness table extensions ─────────────────────────────────────────
        # New aggregate metrics added alongside CTL/ATL/TSB.
        # Existing rows get NULL and are filled on the next _refresh_fitness_table().
        fitness_cols = {row[1] for row in conn.execute("PRAGMA table_info(fitness)").fetchall()}
        _fitness_additions = [
            ("tss", "REAL"),  # daily TSS total (sum across activities)
            ("acwr_rolling", "REAL"),  # acute:chronic workload ratio (rolling avg)
            ("acwr_ema", "REAL"),  # ACWR via EMA (consistent with CTL/ATL model)
            ("acwr_risk_zone", "TEXT"),  # undertrained/optimal/caution/high_risk
            ("monotony", "REAL"),  # Foster training monotony (7-day window)
            ("strain", "REAL"),  # Training strain = weekly TSS × monotony
        ]
        for col_name, col_type in _fitness_additions:
            if col_name not in fitness_cols:
                conn.execute(f"ALTER TABLE fitness ADD COLUMN {col_name} {col_type}")

    _DB_INITIALISED = True
    logger.info("Database initialised at %s", paths.db_path())


def migrate_and_drop_legacy() -> None:
    """
    One-time migration: ensure DB schema is up to date and migrate legacy data
    into the events table. Safe to call multiple times — idempotent.
    """
    init_db()
    from .migrate import run_all

    with get_conn() as conn:
        run_all(conn)


if __name__ == "__main__":
    init_db()
