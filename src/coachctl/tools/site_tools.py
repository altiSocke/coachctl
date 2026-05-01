"""Bake tool — compute and write dashboard data.json."""

from __future__ import annotations


def register(mcp) -> None:  # noqa: ANN001

    @mcp.tool()
    def bake() -> str:
        """
        Bake dashboard data to <DATA_ROOT>/dist/data.json.
        Run this after syncing new activities to update the dashboard.
        Also runs the one-time migration of legacy DB tables on first call.
        """
        from ..site import bake as _bake

        out = _bake()
        return f"Baked: {out}"
