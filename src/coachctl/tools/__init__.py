"""
Tool registration subpackage for the Strava MCP server.

Each module exposes a ``register(mcp)`` function that decorates and
registers its tools on the shared FastMCP instance.
"""

from . import (
    activity_tools,
    athlete_tools,
    calendar_tools,
    env_tools,
    feedback_tools,
    fitness_tools,
    plan_tools,
    readiness_tools,
    site_tools,
    sync_tools,
    untracked_tools,
    wiki_tools,
)

_MODULES = [
    env_tools,
    sync_tools,
    athlete_tools,
    fitness_tools,
    activity_tools,
    feedback_tools,
    plan_tools,
    wiki_tools,
    untracked_tools,
    readiness_tools,
    site_tools,
    calendar_tools,
]


def register_all(mcp) -> None:
    """Register every tool group on *mcp*."""
    for mod in _MODULES:
        mod.register(mcp)
