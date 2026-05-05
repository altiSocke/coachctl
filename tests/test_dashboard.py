"""
Tests for coachctl.dashboard.server — create_app() factory.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from coachctl.dashboard.server import create_app


@pytest.fixture
def valid_data_json(tmp_path):
    data = {"generated_at": "2026-05-05T00:00:00", "fitness": {"ctl": 50}}
    f = tmp_path / "data.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    return f


@pytest.fixture
def missing_data_json(tmp_path):
    return tmp_path / "data.json"  # does not exist


# ── With valid data.json ───────────────────────────────────────────────────────


def test_health_ok(valid_data_json):
    app = create_app(valid_data_json)
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_api_data_returns_200(valid_data_json):
    app = create_app(valid_data_json)
    client = TestClient(app)
    resp = client.get("/api/data")
    assert resp.status_code == 200
    data = resp.json()
    assert data["generated_at"] == "2026-05-05T00:00:00"


def test_index_returns_html(valid_data_json):
    app = create_app(valid_data_json)
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "html" in resp.headers["content-type"]


# ── With missing data.json ────────────────────────────────────────────────────


def test_health_no_data(missing_data_json):
    app = create_app(missing_data_json)
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "no-data"


def test_api_data_returns_503_when_missing(missing_data_json):
    app = create_app(missing_data_json)
    client = TestClient(app)
    resp = client.get("/api/data")
    assert resp.status_code == 503
    assert "error" in resp.json()


def test_index_returns_503_when_missing(missing_data_json):
    app = create_app(missing_data_json)
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 503


# ── POST /api/reload ─────────────────────────────────────────────────────────


def test_reload_picks_up_new_data(tmp_path):
    """Creating data.json after app start → reload makes it available."""
    data_path = tmp_path / "data.json"
    app = create_app(data_path)
    client = TestClient(app)

    # Initially missing
    assert client.get("/health").json()["status"] == "no-data"

    # Write the file
    data_path.write_text(json.dumps({"generated_at": "2026-01-01T00:00:00"}), encoding="utf-8")

    # Reload
    resp = client.post("/api/reload")
    assert resp.json()["ok"] is True

    # Now data is available
    assert client.get("/health").json()["status"] == "ok"
