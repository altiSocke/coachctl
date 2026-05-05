"""
Tests for coachctl.config — athlete.yaml loader.
"""

from __future__ import annotations

import pytest
import yaml

import coachctl.paths as paths_module
from coachctl.config import load_athlete


@pytest.fixture(autouse=True)
def clear_path_cache():
    paths_module._resolve_data_root.cache_clear()
    yield
    paths_module._resolve_data_root.cache_clear()


@pytest.fixture
def athlete_yaml_path(tmp_path, monkeypatch):
    """Scaffold personal dir, patch paths.athlete_yaml to point inside it."""
    personal = tmp_path / "profile"
    personal.mkdir()
    monkeypatch.setenv("AGENT_DATA_ROOT", str(tmp_path))
    yaml_file = personal / "athlete.yaml"
    return yaml_file


def test_load_athlete_returns_dict(athlete_yaml_path):
    athlete_yaml_path.write_text("ftp: 250\nthreshold_hr: 170\n", encoding="utf-8")
    result = load_athlete()
    assert isinstance(result, dict)
    assert result["ftp"] == 250
    assert result["threshold_hr"] == 170


def test_load_athlete_missing_file_returns_empty(athlete_yaml_path, monkeypatch):
    """Missing athlete.yaml → empty dict, no exception."""
    # Don't create the file
    result = load_athlete()
    assert result == {}


def test_load_athlete_empty_file(athlete_yaml_path):
    athlete_yaml_path.write_text("", encoding="utf-8")
    result = load_athlete()
    assert result == {}


def test_load_athlete_full_config(athlete_yaml_path):
    config = {
        "ftp": 300,
        "rftp": 260,
        "threshold_hr": 175,
        "resting_hr": 48,
        "weight_kg": 72,
        "events": [{"name": "Half Marathon", "date": "2026-09-06", "priority": "A"}],
        "goals": {"run": ["sub-1:35 half marathon"]},
    }
    athlete_yaml_path.write_text(yaml.dump(config), encoding="utf-8")
    result = load_athlete()
    assert result["ftp"] == 300
    assert result["weight_kg"] == 72
    assert len(result["events"]) == 1
    assert result["goals"]["run"][0] == "sub-1:35 half marathon"
