"""
Tests for coachctl.wiki — personal wiki read/write/diff/seed.
"""

from __future__ import annotations

import sqlite3

import pytest
import yaml

import coachctl.paths as paths_module
import coachctl.wiki as wiki_module


@pytest.fixture(autouse=True)
def clear_cache():
    paths_module._resolve_data_root.cache_clear()
    yield
    paths_module._resolve_data_root.cache_clear()


@pytest.fixture
def personal_dir(tmp_path, monkeypatch):
    """Patch paths so personal_dir() returns a tmp subdir."""
    pdir = tmp_path / "profile"
    pdir.mkdir()
    monkeypatch.setattr(paths_module, "personal_dir", lambda: pdir)
    monkeypatch.setattr(paths_module, "plans_dir", lambda: pdir / "plans")
    return pdir


@pytest.fixture
def minimal_athlete(personal_dir, monkeypatch):
    """Provide a minimal athlete config for seed functions."""
    cfg = {"ftp": 250, "threshold_hr": 170, "resting_hr": 50}
    monkeypatch.setattr("coachctl.wiki.load_athlete", lambda: cfg)
    monkeypatch.setattr("coachctl.config.load_athlete", lambda: cfg)
    return cfg


# ── read_wiki ─────────────────────────────────────────────────────────────────


def test_read_wiki_empty_when_no_files(personal_dir):
    result = wiki_module.read_wiki()
    assert result == {}


def test_read_wiki_returns_existing_files(personal_dir):
    (personal_dir / "profile.md").write_text("# Profile\n", encoding="utf-8")
    (personal_dir / "goals.md").write_text("# Goals\n", encoding="utf-8")
    result = wiki_module.read_wiki()
    assert "profile.md" in result
    assert "goals.md" in result
    assert "# Profile" in result["profile.md"]


# ── read_wiki_combined ────────────────────────────────────────────────────────


def test_read_wiki_combined_empty(personal_dir):
    result = wiki_module.read_wiki_combined()
    assert "empty" in result.lower()


def test_read_wiki_combined_has_sections(personal_dir):
    (personal_dir / "profile.md").write_text("profile content\n", encoding="utf-8")
    result = wiki_module.read_wiki_combined()
    assert "profile.md" in result
    assert "profile content" in result


# ── diff_section ──────────────────────────────────────────────────────────────


def test_diff_section_new_file(personal_dir):
    diff = wiki_module.diff_section("goals.md", "# New Goals\n")
    assert "+" in diff


def test_diff_section_no_changes(personal_dir):
    (personal_dir / "goals.md").write_text("# Goals\n", encoding="utf-8")
    diff = wiki_module.diff_section("goals.md", "# Goals\n")
    assert diff == "(no changes)"


# ── write_section ─────────────────────────────────────────────────────────────


def test_write_section_creates_file(personal_dir):
    wiki_module.write_section("profile.md", "# Profile\nContent\n")
    assert (personal_dir / "profile.md").exists()
    assert "Content" in (personal_dir / "profile.md").read_text(encoding="utf-8")


def test_write_section_overwrites(personal_dir):
    wiki_module.write_section("profile.md", "old\n")
    wiki_module.write_section("profile.md", "new\n")
    assert "new" in (personal_dir / "profile.md").read_text(encoding="utf-8")


# ── append_section ────────────────────────────────────────────────────────────


def test_append_section_creates_and_appends(personal_dir):
    wiki_module.append_section("training_history.md", "first\n")
    wiki_module.append_section("training_history.md", "second\n")
    content = (personal_dir / "training_history.md").read_text(encoding="utf-8")
    assert "first" in content
    assert "second" in content


# ── append_log ────────────────────────────────────────────────────────────────


def test_append_log_creates_log(personal_dir):
    wiki_module.append_log("session reviewed")
    log_path = personal_dir / "log.md"
    assert log_path.exists()
    content = log_path.read_text(encoding="utf-8")
    assert "session reviewed" in content


def test_append_log_multiple_entries(personal_dir):
    wiki_module.append_log("entry A")
    wiki_module.append_log("entry B")
    content = (personal_dir / "log.md").read_text(encoding="utf-8")
    assert "entry A" in content
    assert "entry B" in content


# ── is_seeded ─────────────────────────────────────────────────────────────────


def test_is_seeded_false_when_empty(personal_dir):
    assert wiki_module.is_seeded() is False


def test_is_seeded_true_when_profile_exists(personal_dir):
    (personal_dir / "profile.md").write_text("# Profile\n", encoding="utf-8")
    assert wiki_module.is_seeded() is True


# ── seed_wiki ─────────────────────────────────────────────────────────────────


def _make_conn(tmp_path):
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS coaching_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_date TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'general',
            tags TEXT,
            note TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    return conn


def test_seed_wiki_creates_files(personal_dir, minimal_athlete, tmp_path):
    conn = _make_conn(tmp_path)
    created = wiki_module.seed_wiki(conn)
    conn.close()
    # At minimum readiness.md is always created; others depend on athlete config
    assert len(created) > 0


def test_seed_wiki_creates_profile(personal_dir, minimal_athlete, tmp_path):
    conn = _make_conn(tmp_path)
    wiki_module.seed_wiki(conn)
    conn.close()
    assert (personal_dir / "profile.md").exists()
    content = (personal_dir / "profile.md").read_text(encoding="utf-8")
    assert "FTP" in content


def test_seed_wiki_creates_readiness(personal_dir, minimal_athlete, tmp_path):
    conn = _make_conn(tmp_path)
    wiki_module.seed_wiki(conn)
    conn.close()
    assert (personal_dir / "readiness.md").exists()


def test_seed_wiki_skips_existing_files(personal_dir, minimal_athlete, tmp_path):
    (personal_dir / "profile.md").write_text("# Existing\n", encoding="utf-8")
    conn = _make_conn(tmp_path)
    created = wiki_module.seed_wiki(conn)
    conn.close()
    assert "profile.md" not in created
    # File not overwritten
    assert "Existing" in (personal_dir / "profile.md").read_text(encoding="utf-8")


def test_seed_wiki_empty_athlete_skips_profile(personal_dir, monkeypatch, tmp_path):
    """Empty athlete config → profile.md and goals.md not created."""
    monkeypatch.setattr("coachctl.wiki.load_athlete", lambda: {})
    conn = _make_conn(tmp_path)
    created = wiki_module.seed_wiki(conn)
    conn.close()
    assert "profile.md" not in created


# ── build_plans_index_content ─────────────────────────────────────────────────


def test_build_plans_index_no_plans(personal_dir, monkeypatch):
    plans = personal_dir / "plans"
    plans.mkdir()
    monkeypatch.setattr(paths_module, "plans_dir", lambda: plans)
    content = wiki_module.build_plans_index_content()
    assert "no plans yet" in content


def test_build_plans_index_with_plan(personal_dir, monkeypatch):
    plans = personal_dir / "plans"
    plans.mkdir()
    monkeypatch.setattr(paths_module, "plans_dir", lambda: plans)
    plan_file = plans / "2026-04-20_half.md"
    plan_file.write_text("# Half Marathon Plan\n", encoding="utf-8")
    content = wiki_module.build_plans_index_content()
    assert "Half Marathon Plan" in content
    assert "2026-04-20" in content


# ── seed with rich athlete config (covers rftp, max_hr, weight_kg, events, goals, notes) ──


import sqlite3 as _sqlite3


def _make_conn_local(tmp_path):
    db = tmp_path / "data.db"
    conn = _sqlite3.connect(str(db))
    conn.row_factory = _sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS coaching_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_date TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'general',
            tags TEXT,
            note TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    return conn


def test_seed_profile_with_full_config(personal_dir, monkeypatch, tmp_path):
    """_seed_profile covers rftp, max_hr, weight_kg+ftp, athlete_notes paths."""
    cfg = {
        "ftp": 280,
        "rftp": 270,
        "threshold_hr": 170,
        "max_hr": 190,
        "resting_hr": 48,
        "weight_kg": 70.0,
        "athlete_notes": ["Good heat tolerance", "Prefers early morning sessions"],
    }
    monkeypatch.setattr("coachctl.wiki.load_athlete", lambda: cfg)
    conn = _make_conn_local(tmp_path)
    created = wiki_module.seed_wiki(conn)
    conn.close()
    assert "profile.md" in created
    content = (personal_dir / "profile.md").read_text()
    assert "rFTP" in content
    assert "Max HR" in content
    assert "W/kg" in content
    assert "Good heat tolerance" in content


def test_seed_goals_with_events_and_goals(personal_dir, monkeypatch, tmp_path):
    """_seed_goals covers events + goals paths."""
    cfg = {
        "ftp": 280,
        "threshold_hr": 170,
        "events": [
            {"priority": "A", "name": "City Marathon", "date": "2026-10-01",
             "goal_time": "3:00:00", "goal_pace_per_km": "4:16", "notes": "Target sub-3"},
        ],
        "goals": {
            "run": ["Sub-3h marathon", "5km PB under 19min"],
            "ride": ["Complete 300km gran fondo"],
        },
    }
    monkeypatch.setattr("coachctl.wiki.load_athlete", lambda: cfg)
    conn = _make_conn_local(tmp_path)
    created = wiki_module.seed_wiki(conn)
    conn.close()
    assert "goals.md" in created
    content = (personal_dir / "goals.md").read_text()
    assert "City Marathon" in content
    assert "Sub-3h marathon" in content
    assert "Target sub-3" in content


def test_seed_training_history_with_notes(personal_dir, monkeypatch, tmp_path):
    """_seed_training_history covers coaching_notes path."""
    cfg = {"ftp": 250, "threshold_hr": 170}
    monkeypatch.setattr("coachctl.wiki.load_athlete", lambda: cfg)
    conn = _make_conn_local(tmp_path)
    conn.execute(
        "INSERT INTO coaching_notes (session_date, category, tags, note) VALUES (?,?,?,?)",
        ("2026-01-10", "observation", "run,threshold", "Great tempo run today"),
    )
    conn.execute(
        "INSERT INTO coaching_notes (session_date, category, tags, note) VALUES (?,?,?,?)",
        ("2026-01-10", "general", None, "Second note same day"),
    )
    conn.commit()
    created = wiki_module.seed_wiki(conn)
    conn.close()
    assert "training_history.md" in created
    content = (personal_dir / "training_history.md").read_text()
    assert "Great tempo run today" in content
