"""
MCP server exposing Strava training tools to OpenCode.

Run via:
    uv run python -m coachctl.mcp_server
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# Bootstrap: load secrets from <DATA_ROOT>/.env if AGENT_DATA_ROOT is set,
# else fall back to a code-repo .env (legacy / dev-only).
_DATA_ROOT_ENV = os.environ.get("AGENT_DATA_ROOT", "").strip()
if _DATA_ROOT_ENV:
    _env = Path(_DATA_ROOT_ENV).expanduser() / ".env"
    if _env.exists():
        load_dotenv(_env)
else:
    _ROOT_ENV = Path(__file__).parent.parent.parent / ".env"
    if _ROOT_ENV.exists():
        load_dotenv(_ROOT_ENV)

from . import paths
from .db import init_db
from .tools import register_all

mcp = FastMCP("coachctl")
register_all(mcp)


def main():
    paths.ensure_profile_dirs()
    init_db()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
