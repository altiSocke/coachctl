"""
Athlete configuration loader.
Reads ``athlete.yaml`` from ``<DATA_ROOT>/profile/`` (see ``paths.athlete_yaml``).
"""

from __future__ import annotations

import logging
from datetime import date as _date

import yaml

from . import paths

logger = logging.getLogger(__name__)


def load_athlete() -> dict:
    """Load athlete config from the active profile. Returns {} if not found."""
    p = paths.athlete_yaml()
    if not p.exists():
        logger.warning("athlete.yaml not found at %s — using empty config", p)
        return {}
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def weight_on(conn, target_date: _date | str | None = None) -> float | None:
    """Body weight (kg) effective on ``target_date``.

    Resolution order (override-wins, base-is-fallback — same idiom as
    ``activity_overrides``):

    1. The most recent ``weight_log`` row whose ``date <= target_date``.
    2. Fallback to ``athlete.yaml``'s ``weight_kg`` scalar when the log has no
       entry on or before that date (or the table is empty).

    Body weight does **not** affect stored TSS/CTL/ATL/TSB — those are
    weight-independent. This drives display W/kg, specific power and cycling
    VO2max only.

    Parameters
    ----------
    conn :
        Open SQLite connection (participates in the caller's transaction and
        respects any sandbox DB override). The ``weight_log`` table is expected
        to exist; a missing-table error is treated as an empty log so callers
        on a not-yet-migrated DB degrade gracefully to the YAML fallback.
    target_date :
        Date to resolve weight for. Accepts a ``datetime.date``, an ISO
        ``YYYY-MM-DD`` string, or ``None`` (defaults to today).

    Returns
    -------
    float | None
        Weight in kg, or ``None`` when neither the log nor ``athlete.yaml``
        provides a value.
    """
    if target_date is None:
        target_date = _date.today()
    iso = target_date.isoformat() if isinstance(target_date, _date) else str(target_date)

    try:
        row = conn.execute(
            "SELECT weight_kg FROM weight_log WHERE date <= ? ORDER BY date DESC LIMIT 1",
            (iso,),
        ).fetchone()
    except Exception:  # noqa: BLE001 — missing table on un-migrated DB → fall back
        row = None

    if row is not None:
        # Support both sqlite3.Row and plain tuples.
        val = row["weight_kg"] if hasattr(row, "keys") else row[0]
        if val is not None:
            return float(val)

    fallback = load_athlete().get("weight_kg")
    return float(fallback) if fallback is not None else None
