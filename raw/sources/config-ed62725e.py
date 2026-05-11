"""
Athlete configuration loader.
Reads ``athlete.yaml`` from ``<DATA_ROOT>/profile/`` (see ``paths.athlete_yaml``).
"""

from __future__ import annotations

import logging

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
