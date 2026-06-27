"""Sandbox harness for validating writes before touching the live database.

``sandboxed_db()`` copies the live ``activities.db`` to a temporary file and
redirects all DB reads/writes to the copy for the duration of the context. This
lets the apply path run a full apply + re-preview + bake against a throwaway
database, prove the result is idempotent and bakes cleanly, and only then replay
the same change against the live DB.

Redirection works through :func:`coachctl.paths.set_db_path_override`, which the
DB layer's ``get_conn`` consults on every connection (see ``coachctl.db``).
"""

from __future__ import annotations

import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from . import db as _db
from . import paths


@contextmanager
def sandboxed_db(*, copy_from: Path | None = None) -> Iterator[Path]:
    """Redirect the DB layer at a temp copy of the live database.

    On enter: copy the current ``paths.db_path()`` (or ``copy_from``) to a temp
    file, point ``paths.db_path()`` at the copy, redirect ``paths.data_json()``
    into the temp dir (so a validation bake stays isolated), and reset the
    schema-init guard so the sandbox connection initialises cleanly. Yields the
    temp DB path.

    On exit (always): restore the previous overrides, reset the init guard, and
    delete the temp dir. If the source DB does not exist, an empty sandbox DB is
    created and initialised so callers still get a usable database.
    """
    source = Path(copy_from) if copy_from is not None else paths.db_path()

    tmp_dir = Path(tempfile.mkdtemp(prefix="coachctl-sandbox-"))
    sandbox_path = tmp_dir / "activities.db"
    sandbox_data_json = tmp_dir / "data.json"

    previous_db_override = paths.get_db_path_override()
    previous_data_json_override = paths.get_data_json_override()
    previous_initialised = _db._DB_INITIALISED

    try:
        if source.exists():
            shutil.copy2(source, sandbox_path)

        paths.set_db_path_override(sandbox_path)
        paths.set_data_json_override(sandbox_data_json)
        # Force re-init against the sandbox file (idempotent CREATE IF NOT EXISTS).
        _db._DB_INITIALISED = False
        _db.init_db()

        yield sandbox_path
    finally:
        paths.set_db_path_override(previous_db_override)
        paths.set_data_json_override(previous_data_json_override)
        _db._DB_INITIALISED = previous_initialised
        shutil.rmtree(tmp_dir, ignore_errors=True)
