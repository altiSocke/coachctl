"""
Single ``coachctl`` entrypoint with subcommands.

All previously-separate console scripts (``sync``, ``bake``, ``update``,
``new-profile``, ``strava-web``) now live as subcommands here:

    coachctl sync [--full] [--auth]
    coachctl bake
    coachctl update
    coachctl new-profile [--target PATH] [--label LABEL] [--no-auth]
    coachctl web [--host H] [--port P] [--reload]
    coachctl serve                 # MCP server (stdio)
    coachctl --version
"""

from __future__ import annotations

import importlib.metadata as _md

import typer

app = typer.Typer(
    add_completion=True,
    no_args_is_help=True,
    help="coachctl — endurance training coach (MCP server + dashboard).",
)


def _version_callback(value: bool) -> None:
    if value:
        try:
            v = _md.version("coachctl")
        except _md.PackageNotFoundError:
            v = "unknown (not installed)"
        typer.echo(f"coachctl {v}")
        raise typer.Exit()


@app.callback()
def _root(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=_version_callback,
        is_eager=True,
        help="Print version and exit.",
    ),
) -> None:
    """coachctl CLI."""


# ── Subcommands ────────────────────────────────────────────────────────────


@app.command("sync", help="Sync Strava activities into the local DB.")
def sync_cmd(
    full: bool = typer.Option(False, "--full", help="Re-sync all activities."),
    auth: bool = typer.Option(False, "--auth", help="Run OAuth flow first."),
) -> None:
    from .sync import do_auth_flow, sync as _sync

    if auth:
        token = do_auth_flow()
        _sync(full=full, access_token=token)
    else:
        _sync(full=full)


@app.command("bake", help="Compute dashboard data and write <DATA_ROOT>/deploy/dist/data.json.")
def bake_cmd() -> None:
    from .site import bake as _bake

    out = _bake()
    typer.echo(f"Baked: {out}")


@app.command("update", help="Sync, bake, and push the personal repo (triggers Vercel).")
def update_cmd() -> None:
    from .update import main as _main

    _main()


@app.command("new-profile", help="Scaffold a new coachctl-personal repo.")
def new_profile_cmd(
    target: str = typer.Option(None, "--target", help="Path to create the personal repo at."),
    label: str = typer.Option(None, "--label", help="Optional STRAVA_PROFILE label."),
    no_auth: bool = typer.Option(False, "--no-auth", help="Skip the Strava OAuth flow."),
) -> None:
    # Reuse new_profile.main's argparse by passing argv through.
    import sys as _sys

    from .new_profile import main as _main

    argv = []
    if target:
        argv += ["--target", target]
    if label:
        argv += ["--label", label]
    if no_auth:
        argv += ["--no-auth"]
    saved = _sys.argv
    _sys.argv = ["coachctl new-profile", *argv]
    try:
        _main()
    finally:
        _sys.argv = saved


@app.command("web", help="Run the dashboard locally.")
def web_cmd(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8080, "--port"),
    reload: bool = typer.Option(False, "--reload", help="Auto-reload on source changes."),
) -> None:
    import uvicorn

    from . import paths
    from .dashboard.server import create_app

    if reload:
        uvicorn.run(
            "coachctl.dashboard._dev_app:app",
            host=host,
            port=port,
            reload=True,
        )
    else:
        uvicorn.run(create_app(paths.data_json()), host=host, port=port)


@app.command(
    "migrate",
    help="Migrate legacy data (untracked activities, schedule overrides, athlete.yaml events) into the events table.",
)
def migrate_cmd() -> None:
    from .db import get_conn, init_db
    from .migrate import run_all

    init_db()
    with get_conn() as conn:
        summary = run_all(conn)
    typer.echo(summary)


@app.command(
    "startup",
    help="Run full startup sequence and print a JSON summary (sync + fitness + new activities + events).",
)
def startup_cmd(
    no_sync: bool = typer.Option(False, "--no-sync", help="Skip Strava sync (use cached data)."),
) -> None:
    """
    Single-call startup for the coach agent when MCP tools are unavailable.

    Outputs a JSON object with keys:
      env, sync, fitness, new_activities, upcoming_events, profile, last_coaching_note
    """
    import io as _io
    import json as _json
    import re as _re
    import sys as _sys
    from contextlib import redirect_stdout as _redirect_stdout
    from datetime import date as _date, timedelta as _td

    from dotenv import load_dotenv as _load_dotenv

    from . import paths as _paths
    from .db import get_conn as _get_conn, init_db as _init_db

    result: dict = {
        "env": {"ok": False, "data_root": None, "warnings": []},
        "sync": {"new_activities": 0, "total_activities": 0},
        "fitness": None,
        "new_activities": [],
        "upcoming_events": [],
        "profile": {},
        "last_coaching_note": None,
    }

    # ── env ──────────────────────────────────────────────────────────────
    try:
        dr = _paths.data_root()
        result["env"]["data_root"] = str(dr)
        env_file = _paths.env_file()
        if env_file.exists():
            _load_dotenv(env_file)
        else:
            result["env"]["warnings"].append(f"Missing .env at {env_file}")
        result["env"]["ok"] = True
    except Exception as exc:
        result["env"]["warnings"].append(f"data_root failed: {exc}")
        typer.echo(_json.dumps(result, indent=2))
        raise typer.Exit(1)

    _init_db()

    # ── sync ─────────────────────────────────────────────────────────────
    if not no_sync:
        try:
            from .sync import sync as _sync

            # redirect sync's progress prints to stderr so they don't corrupt JSON output
            with _redirect_stdout(_io.TextIOWrapper(_io.FileIO("/dev/stderr", "w"))):
                _sync(full=False)
        except Exception as exc:
            result["sync"]["error"] = str(exc)

    try:
        with _get_conn() as _conn:
            row = _conn.execute("SELECT COUNT(*) AS c FROM activities").fetchone()
            result["sync"]["total_activities"] = row["c"] if row else 0
    except Exception:
        pass

    # ── fitness ───────────────────────────────────────────────────────────
    try:
        with _get_conn() as _conn:
            f = _conn.execute(
                "SELECT date, ctl, atl, tsb FROM fitness ORDER BY date DESC LIMIT 1"
            ).fetchone()
            if f:
                result["fitness"] = dict(f)
    except Exception as exc:
        result["fitness"] = {"error": str(exc)}

    # ── new (unreviewed) activities — last 28 days ────────────────────────
    try:
        cutoff = (_date.today() - _td(days=28)).isoformat()
        with _get_conn() as _conn:
            rows = _conn.execute(
                """
                SELECT id, start_date, name, sport_type,
                       ROUND(distance / 1000.0, 2)   AS distance_km,
                       ROUND(moving_time / 60.0, 1)  AS moving_time_min,
                       tss,
                       average_heartrate              AS avg_hr,
                       average_watts                  AS avg_watts,
                       total_elevation_gain           AS elevation_m
                FROM activities
                WHERE reviewed_at IS NULL
                  AND start_date >= ?
                ORDER BY start_date DESC
                LIMIT 10
                """,
                (cutoff,),
            ).fetchall()
            result["new_activities"] = [dict(r) for r in rows]
    except Exception as exc:
        result["new_activities"] = [{"error": str(exc)}]

    # ── upcoming events — today + 28 days ─────────────────────────────────
    try:
        today = _date.today().isoformat()
        end = (_date.today() + _td(days=28)).isoformat()
        with _get_conn() as _conn:
            rows = _conn.execute(
                """
                SELECT id, slug, kind, date, name, summary, status, estimated_tss
                FROM events
                WHERE date BETWEEN ? AND ?
                  AND status != 'cancelled'
                ORDER BY date
                """,
                (today, end),
            ).fetchall()
            result["upcoming_events"] = [dict(r) for r in rows]
    except Exception as exc:
        result["upcoming_events"] = [{"error": str(exc)}]

    # ── profile ───────────────────────────────────────────────────────────
    try:
        import yaml as _yaml

        athlete_yaml = _paths.athlete_yaml()
        if athlete_yaml.exists():
            cfg = _yaml.safe_load(athlete_yaml.read_text("utf-8")) or {}
            result["profile"] = {
                "ftp": cfg.get("ftp"),
                "rftp_sec_per_km": cfg.get("rftp"),
                "rftp_watts": cfg.get("rftp_watts"),
                "threshold_hr": cfg.get("threshold_hr"),
                "max_hr": cfg.get("max_hr"),
                "weight_kg": cfg.get("weight_kg"),
                "vo2max": cfg.get("vo2max"),
                "goals": cfg.get("goals", {}),
            }
    except Exception as exc:
        result["profile"] = {"error": str(exc)}

    # ── last coaching note ─────────────────────────────────────────────────
    try:
        history_path = _paths.data_root() / "profile" / "training_history.md"
        if history_path.exists():
            text = history_path.read_text("utf-8")
            sections = _re.split(r"(?=^### \d{4}-\d{2}-\d{2})", text, flags=_re.MULTILINE)
            if sections:
                last = sections[-1].strip()
                m = _re.match(r"### (\d{4}-\d{2}-\d{2})\s*(.*)", last, _re.DOTALL)
                if m:
                    result["last_coaching_note"] = {
                        "date": m.group(1),
                        "text": m.group(2).strip()[:300],
                    }
    except Exception:
        pass

    typer.echo(_json.dumps(result, indent=2))


@app.command("serve", help="Start the MCP server (stdio).")
def serve_cmd() -> None:
    from .mcp_server import main as _main

    _main()


@app.command(
    "recalculate",
    help=(
        "Recompute all per-activity metrics from stored raw_json, then rebuild "
        "the fitness table (CTL/ATL/TSB + ACWR + Monotony). No Strava API call required."
    ),
)
def recalculate_cmd(
    verbose: bool = typer.Option(True, "--verbose/--quiet", help="Print progress."),
) -> None:
    """
    Recalculate metrics without touching Strava.

    Useful after:
    - Updating athlete.yaml thresholds (FTP, rFTP, HR)
    - A formula change in metrics.py
    - A fresh install that skipped --full sync

    Steps:
      1. Read raw_json from every activity row.
      2. Recompute tss / np / intensity_factor / hrss / rtss / ngp / rtss_power.
      3. Batch-UPDATE all activities in one SQL call.
      4. Rebuild the fitness table (CTL/ATL/TSB, ACWR, Monotony) from fresh data.
    """
    from .db import init_db
    from .sync import recalculate_activity_metrics

    init_db()
    n = recalculate_activity_metrics(verbose=verbose)
    if verbose:
        typer.echo(f"Done — {n} activities recalculated.")


@app.command(
    "backfill-event-tss",
    help="Backfill estimated_tss for training events that have NULL (re-parses duration + intensity from details).",
)
def backfill_event_tss_cmd(
    verbose: bool = typer.Option(True, "--verbose/--quiet"),
) -> None:
    from .db import init_db
    from .tools.plan_tools import backfill_event_tss

    init_db()
    result = backfill_event_tss()
    if verbose:
        typer.echo(
            f"Backfill complete — updated: {result['updated']}, "
            f"skipped (no parseable duration): {result['skipped_no_duration']}"
        )


@app.command("preview-sessions", help="Preview deterministic generated sessions without writing.")
def preview_sessions_cmd(
    mode: str = typer.Option("race-week", "--mode", help="Generation mode: race-week or post-race."),
    race: str = typer.Option("", "--race", help="Race event slug."),
    start: str = typer.Option(..., "--start", help="Preview start date YYYY-MM-DD."),
    slug_prefix: str = typer.Option("", "--slug-prefix", help="Generated slug prefix."),
    plan_id: int | None = typer.Option(None, "--plan-id", help="Optional plan id."),
    output_format: str = typer.Option("text", "--format", help="Output format: text or json."),
    target_tss: int | None = typer.Option(None, "--target-tss", help="Target week TSS."),
    phase: str = typer.Option("", "--phase", help="Training phase: build or recovery."),
    freshness: str = typer.Option("normal", "--freshness", help="Freshness: normal or fatigued."),
) -> None:
    from .db import init_db
    from .workout_preview import (
        format_preview_json,
        format_preview_text,
        preview_sessions_from_db,
    )

    init_db()
    result = preview_sessions_from_db(
        mode=mode,
        race_slug=race or None,
        start_date=start,
        slug_prefix=slug_prefix or None,
        plan_id=plan_id,
        target_tss=target_tss,
        phase=phase or None,
        freshness=freshness,
    )
    if result.error:
        typer.echo(f"Error: {result.error}", err=True)
        raise typer.Exit(1)
    if output_format == "json":
        typer.echo(format_preview_json(result.previews))
    elif output_format == "text":
        typer.echo(
            format_preview_text(
                race_name=result.race_name,
                window_start=result.window_start,
                window_end=result.window_end,
                previews=result.previews,
            )
        )
    else:
        typer.echo("Error: --format must be 'text' or 'json'", err=True)
        raise typer.Exit(1)


@app.command("apply-sessions", help="Apply deterministic generated sessions to events.")
def apply_sessions_cmd(
    mode: str = typer.Option("race-week", "--mode", help="Generation mode: race-week or post-race."),
    race: str = typer.Option("", "--race", help="Race event slug."),
    start: str = typer.Option(..., "--start", help="Preview/apply start date YYYY-MM-DD."),
    slug_prefix: str = typer.Option("", "--slug-prefix", help="Generated slug prefix."),
    plan_id: int | None = typer.Option(None, "--plan-id", help="Optional plan id override."),
    output_format: str = typer.Option("text", "--format", help="Output format: text or json."),
    yes: bool = typer.Option(False, "--yes", help="Actually write changes."),
    allow_skips: bool = typer.Option(False, "--allow-skips", help="Apply non-skipped rows."),
    target_tss: int | None = typer.Option(None, "--target-tss", help="Target week TSS."),
    phase: str = typer.Option("", "--phase", help="Training phase: build or recovery."),
    freshness: str = typer.Option("normal", "--freshness", help="Freshness: normal or fatigued."),
) -> None:
    from .db import init_db
    from .workout_apply import (
        apply_sessions_from_db,
        format_apply_json,
        format_apply_text,
    )
    from .workout_preview import (
        format_preview_json,
        format_preview_text,
        preview_sessions_from_db,
    )

    init_db()
    if not yes:
        result = preview_sessions_from_db(
            mode=mode,
            race_slug=race or None,
            start_date=start,
            slug_prefix=slug_prefix or None,
            plan_id=plan_id,
            target_tss=target_tss,
            phase=phase or None,
            freshness=freshness,
        )
        if result.error:
            typer.echo(f"Error: {result.error}", err=True)
            raise typer.Exit(1)
        typer.echo("Dry run only. Re-run with --yes to apply.\n")
        if output_format == "json":
            typer.echo(format_preview_json(result.previews))
        elif output_format == "text":
            typer.echo(
                format_preview_text(
                    race_name=result.race_name,
                    window_start=result.window_start,
                    window_end=result.window_end,
                    previews=result.previews,
                )
            )
        else:
            typer.echo("Error: --format must be 'text' or 'json'", err=True)
            raise typer.Exit(1)
        return

    try:
        result = apply_sessions_from_db(
            mode=mode,
            race_slug=race or None,
            start_date=start,
            slug_prefix=slug_prefix or None,
            plan_id=plan_id,
            allow_skips=allow_skips,
            target_tss=target_tss,
            phase=phase or None,
            freshness=freshness,
        )
    except RuntimeError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    if output_format == "json":
        typer.echo(format_apply_json(result))
    elif output_format == "text":
        typer.echo(format_apply_text(result))
    else:
        typer.echo("Error: --format must be 'text' or 'json'", err=True)
        raise typer.Exit(1)


# ── Signal bot sub-app ─────────────────────────────────────────────────────


_signal_app = typer.Typer(
    help="Signal bot — send training plans to your phone.",
    no_args_is_help=True,
)
app.add_typer(_signal_app, name="signal")


@_signal_app.command("daily-plan", help="Send tomorrow's training plan via Signal.")
def signal_daily_plan_cmd(
    date: str = typer.Option(
        "",
        "--date",
        "-d",
        help="Target date YYYY-MM-DD (default: tomorrow).",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Resend even if already sent for this date.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Print the message without sending.",
    ),
    dashboard_url: str = typer.Option(
        "",
        "--dashboard-url",
        help="URL appended to the message footer.",
        envvar="SIGNAL_DASHBOARD_URL",
    ),
) -> None:
    if dry_run:
        from datetime import date as _date, timedelta as _td

        from dotenv import load_dotenv as _load_dotenv

        from . import paths as _paths
        from .events import get_calendar as _get_cal
        from .config import load_athlete as _load_athlete
        from .db import get_conn as _get_conn
        from .signal_bot import format_daily_plan, _detect_dominant_sport

        dr = _paths.data_root()
        env_file = dr / ".env"
        if env_file.exists():
            _load_dotenv(env_file)

        target = date or (_date.today() + _td(days=1)).isoformat()
        all_events = _get_cal(target, target)
        events = [e for e in all_events if e.status != "cancelled" and e.kind != "activity"]
        athlete = _load_athlete()
        fitness_by_sport: dict = {}
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT sport_category, ctl, atl, tsb FROM fitness "
                "WHERE date = (SELECT MAX(date) FROM fitness)"
            ).fetchall()
            for row in rows:
                fitness_by_sport[row["sport_category"]] = {
                    "ctl": float(row["ctl"] or 0.0),
                    "atl": float(row["atl"] or 0.0),
                    "tsb": float(row["tsb"] or 0.0),
                }
        msg = format_daily_plan(target, events, athlete, fitness_by_sport, dashboard_url)
        typer.echo(msg)
        return

    from .signal_bot import send_tomorrows_plan

    try:
        result = send_tomorrows_plan(
            target_date=date,
            force=force,
            dashboard_url=dashboard_url,
        )
        typer.echo(result)
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)


@_signal_app.command("check", help="Test connectivity to signal-cli-rest-api.")
def signal_check_cmd() -> None:
    from dotenv import load_dotenv as _load_dotenv

    from . import paths as _paths
    from .signal_bot import check_connectivity, get_signal_config

    dr = _paths.data_root()
    env_file = dr / ".env"
    if env_file.exists():
        _load_dotenv(env_file)

    try:
        cfg = get_signal_config()
    except RuntimeError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)

    ok, msg = check_connectivity(cfg["SIGNAL_API_URL"])
    typer.echo(msg)
    if not ok:
        raise typer.Exit(1)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
