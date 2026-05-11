"""
Smoke tests for coachctl.tools — every module must be importable and register()
must run without errors against a minimal MCP-like mock.
"""

from __future__ import annotations

from unittest.mock import MagicMock


def _make_mock_mcp():
    """Create a minimal mock that satisfies @mcp.tool() registration calls."""
    mcp = MagicMock()
    # @mcp.tool() is called as a decorator: mcp.tool() returns a callable
    # that is then used as a decorator on the function.
    mcp.tool.return_value = lambda fn: fn
    return mcp


def test_activity_tools_register():
    from coachctl.tools import activity_tools
    mcp = _make_mock_mcp()
    activity_tools.register(mcp)
    assert mcp.tool.called


def test_athlete_tools_register():
    from coachctl.tools import athlete_tools
    mcp = _make_mock_mcp()
    athlete_tools.register(mcp)
    assert mcp.tool.called


def test_env_tools_register():
    from coachctl.tools import env_tools
    mcp = _make_mock_mcp()
    env_tools.register(mcp)
    assert mcp.tool.called


def test_event_tools_register():
    from coachctl.tools import event_tools
    mcp = _make_mock_mcp()
    event_tools.register(mcp)
    assert mcp.tool.called


def test_feedback_tools_register():
    from coachctl.tools import feedback_tools
    mcp = _make_mock_mcp()
    feedback_tools.register(mcp)
    assert mcp.tool.called


def test_fitness_tools_register():
    from coachctl.tools import fitness_tools
    mcp = _make_mock_mcp()
    fitness_tools.register(mcp)
    assert mcp.tool.called


def test_plan_tools_register():
    from coachctl.tools import plan_tools
    mcp = _make_mock_mcp()
    plan_tools.register(mcp)
    assert mcp.tool.called


def test_readiness_tools_register():
    from coachctl.tools import readiness_tools
    mcp = _make_mock_mcp()
    readiness_tools.register(mcp)
    assert mcp.tool.called


def test_site_tools_register():
    from coachctl.tools import site_tools
    mcp = _make_mock_mcp()
    site_tools.register(mcp)
    assert mcp.tool.called


def test_sync_tools_register():
    from coachctl.tools import sync_tools
    mcp = _make_mock_mcp()
    sync_tools.register(mcp)
    assert mcp.tool.called


def test_untracked_tools_register():
    from coachctl.tools import untracked_tools
    mcp = _make_mock_mcp()
    untracked_tools.register(mcp)
    assert mcp.tool.called


def test_wiki_tools_register():
    from coachctl.tools import wiki_tools
    mcp = _make_mock_mcp()
    wiki_tools.register(mcp)
    assert mcp.tool.called


def test_tools_init_register_all():
    """tools/__init__.py register_all should call every sub-module."""
    from coachctl.tools import register_all
    mcp = _make_mock_mcp()
    register_all(mcp)
    assert mcp.tool.called
