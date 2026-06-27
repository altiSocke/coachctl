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
            # Date-aware current weight: latest weight_log entry, else YAML scalar.
            weight_kg = cfg.get("weight_kg")
            try:
                from datetime import date as _date

                from .config import weight_on
                from .db import get_conn

                with get_conn() as _conn:
                    resolved = weight_on(_conn, _date.today())
                if resolved is not None:
                    weight_kg = resolved
            except Exception:
                pass  # fall back to YAML scalar
            result["profile"] = {
                "ftp": cfg.get("ftp"),
                "rftp_sec_per_km": cfg.get("rftp"),
                "rftp_watts": cfg.get("rftp_watts"),
                "threshold_hr": cfg.get("threshold_hr"),
                "max_hr": cfg.get("max_hr"),
                "weight_kg": weight_kg,
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
    "log-weight",
    help=(
        "Record body weight on a date (YYYY-MM-DD). With --list, print the "
        "weight history instead. Weight drives display W/kg and cycling VO2max; "
        "it does NOT change stored TSS/CTL/ATL/TSB."
    ),
)
def log_weight_cmd(
    date_str: str = typer.Argument(
        "", metavar="DATE", help="Date YYYY-MM-DD (omit with --list)."
    ),
    weight: float = typer.Argument(
        0.0, metavar="KG", help="Body weight in kg (omit with --list)."
    ),
    source: str = typer.Option("manual", "--source", help="Measurement source label."),
    note: str = typer.Option("", "--note", help="Optional context note."),
    list_history: bool = typer.Option(
        False, "--list", help="Print weight history and exit (ignores DATE/KG)."
    ),
) -> None:
    """
    Log or view body weight.

    Examples
    --------
        coachctl log-weight 2026-06-27 85.5
        coachctl log-weight 2026-05-16 87 --source scale --note "morning, fasted"
        coachctl log-weight --list
    """
    _log_weight(
        date_str=date_str,
        weight=weight,
        source=source,
        note=note,
        list_history=list_history,
    )


def _log_weight(
    date_str: str = "",
    weight: float = 0.0,
    source: str = "manual",
    note: str = "",
    list_history: bool = False,
) -> None:
    """Implementation of ``log-weight`` (plain function, directly testable).

    Kept separate from the Typer command wrapper because Typer replaces a
    command function's parameter defaults with sentinel ``ArgumentInfo`` /
    ``OptionInfo`` objects, which makes the decorated function non-callable
    with real values in unit tests.
    """
    from datetime import date as _date

    from .config import load_athlete
    from .db import get_conn, init_db

    init_db()

    if list_history:
        athlete = load_athlete()
        ftp = athlete.get("ftp")
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT date, weight_kg, source, note FROM weight_log ORDER BY date ASC"
            ).fetchall()
        if not rows:
            typer.echo("No weight entries logged. Falling back to athlete.yaml "
                       f"weight_kg = {athlete.get('weight_kg')}.")
            return
        typer.echo(f"{'date':12} {'kg':>6} {'W/kg':>6}  source / note")
        typer.echo("-" * 50)
        for r in rows:
            wkg = f"{ftp / r['weight_kg']:.2f}" if ftp and r["weight_kg"] else "-"
            tail = r["source"] or ""
            if r["note"]:
                tail = f"{tail} - {r['note']}" if tail else r["note"]
            typer.echo(f"{r['date']:12} {r['weight_kg']:6.1f} {wkg:>6}  {tail}")
        return

    # ── Logging path: validate inputs ────────────────────────────────────────
    if not date_str:
        typer.echo("Error: DATE is required (or use --list).", err=True)
        raise typer.Exit(1)
    try:
        iso = _date.fromisoformat(date_str).isoformat()
    except ValueError:
        typer.echo(f"Error: invalid date '{date_str}' - expected YYYY-MM-DD.", err=True)
        raise typer.Exit(1)
    if not (30.0 <= weight <= 200.0):
        typer.echo(
            f"Error: weight {weight} kg out of sane range (30-200).", err=True
        )
        raise typer.Exit(1)

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO weight_log (date, weight_kg, source, note, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'))
            ON CONFLICT(date) DO UPDATE SET
                weight_kg = excluded.weight_kg,
                source    = excluded.source,
                note      = excluded.note,
                updated_at = datetime('now')
            """,
            (iso, weight, source or None, note or None),
        )

    athlete = load_athlete()
    ftp = athlete.get("ftp")
    extra = f"  (FTP {ftp}W -> {ftp / weight:.2f} W/kg)" if ftp else ""
    typer.echo(f"Logged {weight} kg on {iso}.{extra}")


@app.command(
    "link-activities",
    help="Link past planned training events to the activities that fulfilled them (sets activity_id + completed).",
)
def link_activities_cmd(
    on_date: str = typer.Option("", "--date", help="Only link this date (YYYY-MM-DD); default = all past."),
) -> None:
    from .db import init_db
    from .events import link_completed_activities

    init_db()
    result = link_completed_activities(on_date=on_date or None)
    typer.echo(
        f"Linked: {result['linked']}, ambiguous (skipped): {result['skipped_ambiguous']}, "
        f"already linked: {result['already_linked']}, candidates: {result['candidates']}"
    )


@app.command(
    "backfill-event-tss",
    help="Backfill estimated_tss for training events that have NULL (re-parses duration + intensity from details).",
)
def backfill_event_tss_cmd(
    verbose: bool = typer.Option(True, "--verbose/--quiet"),
    recompute: bool = typer.Option(
        False,
        "--recompute",
        help="Recompute ALL training events (not just NULL) — use after changing the IF model.",
    ),
) -> None:
    from .db import init_db
    from .tools.plan_tools import backfill_event_tss

    init_db()
    result = backfill_event_tss(recompute=recompute)
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
    create_rest_days: bool = typer.Option(False, "--create-rest-days", help="Create explicit rest-day rows."),
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
        create_rest_days=create_rest_days,
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
                summary=result.summary,
            )
        )
    else:
        typer.echo("Error: --format must be 'text' or 'json'", err=True)
        raise typer.Exit(1)


@app.command("preview-plan", help="Preview an expanded multi-week plan template against the calendar.")
def preview_plan_cmd(
    template: str = typer.Option(..., "--template", help="Plan template name, e.g. half_marathon_build."),
    start: str = typer.Option(..., "--start", help="Plan start date YYYY-MM-DD (Monday)."),
    weeks: int = typer.Option(..., "--weeks", help="Number of weeks to expand."),
    seed: int | None = typer.Option(None, "--seed", help="Variation seed; omit for deterministic output."),
    slug_prefix: str = typer.Option("", "--slug-prefix", help="Generated slug prefix."),
    plan_id: int | None = typer.Option(None, "--plan-id", help="Optional plan id."),
    create_rest_days: bool = typer.Option(False, "--create-rest-days", help="Create explicit rest-day rows."),
    output_format: str = typer.Option("text", "--format", help="Output format: text or json."),
) -> None:
    from .db import init_db
    from .workout_preview import (
        format_preview_json,
        format_preview_text,
        preview_plan_from_db,
    )

    init_db()
    result = preview_plan_from_db(
        template_name=template,
        start_date=start,
        weeks=weeks,
        seed=seed,
        slug_prefix=slug_prefix or None,
        plan_id=plan_id,
        create_rest_days=create_rest_days,
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
                summary=result.summary,
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
    create_rest_days: bool = typer.Option(False, "--create-rest-days", help="Create explicit rest-day rows."),
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
            create_rest_days=create_rest_days,
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
                    summary=result.summary,
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


@app.command("apply-plan", help="Apply an expanded multi-week plan template (sandbox-validated).")
def apply_plan_cmd(
    template: str = typer.Option(..., "--template", help="Plan template name, e.g. half_marathon_build."),
    start: str = typer.Option(..., "--start", help="Plan start date YYYY-MM-DD (Monday)."),
    weeks: int = typer.Option(..., "--weeks", help="Number of weeks to expand."),
    seed: int | None = typer.Option(None, "--seed", help="Variation seed; omit for deterministic output."),
    slug_prefix: str = typer.Option("", "--slug-prefix", help="Generated slug prefix."),
    plan_id: int | None = typer.Option(None, "--plan-id", help="Optional plan id."),
    output_format: str = typer.Option("text", "--format", help="Output format: text or json."),
    yes: bool = typer.Option(False, "--yes", help="Actually write changes."),
    allow_skips: bool = typer.Option(False, "--allow-skips", help="Apply non-skipped rows."),
    create_rest_days: bool = typer.Option(False, "--create-rest-days", help="Create explicit rest-day rows."),
) -> None:
    from .db import init_db
    from .workout_apply import (
        apply_plan_from_db,
        format_apply_json,
        format_apply_text,
    )
    from .workout_preview import (
        format_preview_json,
        format_preview_text,
        preview_plan_from_db,
    )

    init_db()
    if not yes:
        result = preview_plan_from_db(
            template_name=template,
            start_date=start,
            weeks=weeks,
            seed=seed,
            slug_prefix=slug_prefix or None,
            plan_id=plan_id,
            create_rest_days=create_rest_days,
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
                    summary=result.summary,
                )
            )
        else:
            typer.echo("Error: --format must be 'text' or 'json'", err=True)
            raise typer.Exit(1)
        return

    try:
        result = apply_plan_from_db(
            template_name=template,
            start_date=start,
            weeks=weeks,
            seed=seed,
            slug_prefix=slug_prefix or None,
            plan_id=plan_id,
            allow_skips=allow_skips,
            create_rest_days=create_rest_days,
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
