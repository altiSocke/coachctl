"""
FastAPI dashboard factory — soft-fails when ``data.json`` is missing.

Cold-start contract:
  * Always succeeds at import time, even if ``data_path`` is missing.
  * If data is missing or unreadable, ``/`` returns HTTP 503 with a setup
    message, ``/api/data`` returns 503 JSON, and ``/health`` reports
    ``{"status": "no-data"}``.
  * ``POST /api/reload`` re-reads the data file (useful for local dev).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

logger = logging.getLogger(__name__)


def _setup_html(error: str | None) -> str:
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>coachctl — setup needed</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 640px; margin: 4rem auto; padding: 0 1rem; color: #222; }}
  code {{ background: #f4f4f4; padding: .15rem .35rem; border-radius: 3px; }}
  pre {{ background: #f4f4f4; padding: .75rem; border-radius: 4px; overflow-x: auto; }}
  .err {{ color: #a00; font-size: .9em; }}
</style></head><body>
<h1>coachctl dashboard</h1>
<p>No <code>data.json</code> available yet.</p>
<p>Run <code>bake</code> in your personal repo to generate it, then commit and push:</p>
<pre>uv run bake
git -C $AGENT_DATA_ROOT add deploy/dist/data.json
git -C $AGENT_DATA_ROOT commit -m "bake $(date -I)"
git -C $AGENT_DATA_ROOT push</pre>
<p>Vercel will redeploy automatically once the new commit lands.</p>
{f'<p class="err">Last error: {error}</p>' if error else ""}
</body></html>"""


def create_app(data_path: Path, html_path: Path | None = None) -> FastAPI:
    """Build a FastAPI app that serves the dashboard from ``data_path``."""
    html_path = html_path or Path(__file__).parent / "app.html"

    state: dict = {"data": None, "error": None}

    def load() -> None:
        try:
            state["data"] = json.loads(Path(data_path).read_text(encoding="utf-8"))
            state["error"] = None
        except Exception as e:  # noqa: BLE001 — soft-fail by design
            state["data"] = None
            logger.error("Failed to load data.json: %s", e)
            state["error"] = "data unavailable"

    load()

    try:
        html = Path(html_path).read_text(encoding="utf-8")
    except FileNotFoundError:
        html = "<h1>app.html missing</h1>"

    app = FastAPI(docs_url=None, redoc_url=None)

    @app.get("/", response_class=HTMLResponse)
    def index():
        if state["data"] is None:
            return HTMLResponse(_setup_html(None), status_code=503)
        return HTMLResponse(html)

    @app.get("/api/data")
    def api_data():
        if state["data"] is None:
            return JSONResponse(
                {"error": "data not available"},
                status_code=503,
            )
        return JSONResponse(state["data"])

    @app.get("/health")
    def health():
        return JSONResponse({"status": "ok" if state["data"] is not None else "no-data"})

    @app.post("/api/reload")
    def reload():
        """Re-read data.json from disk — useful after bake in local dev."""
        load()
        if state["data"] is None:
            return JSONResponse({"status": "error", "detail": state["error"]}, status_code=503)
        return JSONResponse({"status": "ok"})

    return app
