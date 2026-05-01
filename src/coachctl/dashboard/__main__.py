"""Local dev server: ``strava-web`` runs uvicorn against the active data root."""

from __future__ import annotations

import argparse

from .. import paths
from .server import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the dashboard locally")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    import uvicorn

    app = create_app(paths.data_json())

    if args.reload:
        uvicorn.run(
            "coachctl.dashboard._dev_app:app",
            host=args.host,
            port=args.port,
            reload=True,
        )
    else:
        uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
