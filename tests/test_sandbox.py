from __future__ import annotations

import coachctl.db as db_module
from coachctl import paths
from coachctl.db import init_db
from coachctl.events import (
    KIND_TRAINING,
    STATUS_PLANNED,
    Event,
    get_event,
    upsert_event,
)
from coachctl.sandbox import sandboxed_db
import pytest


@pytest.fixture(autouse=True)
def _reset_db_init_guard():
    """Keep the process-global init guard from leaking across tests."""
    db_module._DB_INITIALISED = False
    yield
    db_module._DB_INITIALISED = False


def _real_db(tmp_data_root):
    """Initialise the real (non-mocked) DB at the resolved path and return it."""
    # _DB_INITIALISED is a process-global guard; reset it so init_db() actually
    # creates the schema in this test's fresh data root.
    db_module._DB_INITIALISED = False
    init_db()
    return paths.db_path()


def test_sandbox_redirects_db_path(tmp_data_root) -> None:
    live = _real_db(tmp_data_root)
    assert paths.get_db_path_override() is None

    with sandboxed_db() as sandbox_path:
        assert paths.db_path() == sandbox_path
        assert sandbox_path != live

    # restored on exit
    assert paths.get_db_path_override() is None
    assert paths.db_path() == live


def test_sandbox_copies_live_data(tmp_data_root) -> None:
    _real_db(tmp_data_root)
    upsert_event(
        Event(
            slug="live-1",
            kind=KIND_TRAINING,
            date="2026-07-13",
            name="Live event",
            status=STATUS_PLANNED,
        )
    )

    with sandboxed_db():
        # the live row is visible inside the sandbox copy
        assert get_event("live-1") is not None


def test_sandbox_writes_do_not_leak_to_live(tmp_data_root) -> None:
    _real_db(tmp_data_root)

    with sandboxed_db():
        upsert_event(
            Event(
                slug="sandbox-1",
                kind=KIND_TRAINING,
                date="2026-07-14",
                name="Sandbox only",
                status=STATUS_PLANNED,
            )
        )
        assert get_event("sandbox-1") is not None

    # the sandbox write is gone once we are back on the live DB
    assert get_event("sandbox-1") is None


def test_sandbox_cleans_up_temp_dir(tmp_data_root) -> None:
    _real_db(tmp_data_root)

    with sandboxed_db() as sandbox_path:
        assert sandbox_path.exists()

    assert not sandbox_path.exists()
    assert not sandbox_path.parent.exists()


def test_sandbox_restores_override_on_exception(tmp_data_root) -> None:
    _real_db(tmp_data_root)
    live = paths.db_path()

    class _Boom(RuntimeError):
        pass

    try:
        with sandboxed_db():
            raise _Boom()
    except _Boom:
        pass

    assert paths.get_db_path_override() is None
    assert paths.db_path() == live


def test_sandbox_handles_missing_source_db(tmp_data_root) -> None:
    # Do NOT init the live DB; the source file does not exist yet.
    live = paths.db_path()
    assert not live.exists()

    with sandboxed_db() as sandbox_path:
        # an empty, initialised sandbox DB is created and usable
        assert sandbox_path.exists()
        upsert_event(
            Event(
                slug="sb-empty",
                kind=KIND_TRAINING,
                date="2026-07-13",
                name="Works",
                status=STATUS_PLANNED,
            )
        )
        assert get_event("sb-empty") is not None


def test_sandbox_redirects_data_json_and_restores(tmp_data_root) -> None:
    _real_db(tmp_data_root)
    real_json = paths.data_json()
    assert paths.get_data_json_override() is None

    with sandboxed_db() as sandbox_path:
        # data.json is redirected into the sandbox temp dir, not the real path
        sandboxed = paths.data_json()
        assert sandboxed != real_json
        assert sandboxed.parent == sandbox_path.parent

    # restored on exit
    assert paths.get_data_json_override() is None
    assert paths.data_json() == real_json


def test_sandbox_bake_does_not_write_real_data_json(tmp_data_root) -> None:
    _real_db(tmp_data_root)
    real_json = paths.data_json()
    assert not real_json.exists()

    from coachctl.site import bake

    with sandboxed_db() as sandbox_path:
        out = bake()
        # the bake landed in the sandbox, not at the published path
        assert out.parent == sandbox_path.parent
        assert out.exists()

    # the real artifact was never published by the sandbox bake
    assert not real_json.exists()
