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


@app.command("serve", help="Start the MCP server (stdio).")
def serve_cmd() -> None:
    from .mcp_server import main as _main

    _main()


def main() -> None:
    app()


if __name__ == "__main__":
    main()
