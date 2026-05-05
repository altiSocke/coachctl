"""
Tests for coachctl.general_wiki — general (public) wiki layer.
"""

from __future__ import annotations

import pytest

import coachctl.general_wiki as gw
import coachctl.paths as paths_module


@pytest.fixture
def wiki_dir(tmp_path, monkeypatch):
    """Patch general_wiki_dir() to a tmp directory."""
    wdir = tmp_path / "wiki"
    wdir.mkdir()
    monkeypatch.setattr(paths_module, "general_wiki_dir", lambda: wdir)
    return wdir


# ── list_files ────────────────────────────────────────────────────────────────


def test_list_files_empty(wiki_dir):
    assert gw.list_files() == []


def test_list_files_returns_md_files(wiki_dir):
    (wiki_dir / "nutrition.md").write_text("# Nutrition\n", encoding="utf-8")
    (wiki_dir / "recovery.md").write_text("# Recovery\n", encoding="utf-8")
    files = gw.list_files()
    assert "nutrition.md" in files
    assert "recovery.md" in files


def test_list_files_sorted(wiki_dir):
    for name in ["zzz.md", "aaa.md", "mmm.md"]:
        (wiki_dir / name).write_text("x\n", encoding="utf-8")
    files = gw.list_files()
    assert files == sorted(files)


def test_list_files_subdirectory(wiki_dir):
    sub = wiki_dir / "races"
    sub.mkdir()
    (sub / "alpenbrevet.md").write_text("# Alpenbrevet\n", encoding="utf-8")
    files = gw.list_files()
    assert any("alpenbrevet" in f for f in files)


def test_list_files_nonexistent_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(paths_module, "general_wiki_dir", lambda: tmp_path / "missing")
    assert gw.list_files() == []


# ── resolve_topic ─────────────────────────────────────────────────────────────


def test_resolve_topic_finds_exact(wiki_dir):
    f = wiki_dir / "nutrition.md"
    f.write_text("# Nutrition\n", encoding="utf-8")
    result = gw.resolve_topic("nutrition")
    assert f in result


def test_resolve_topic_no_match(wiki_dir):
    (wiki_dir / "other.md").write_text("x\n", encoding="utf-8")
    assert gw.resolve_topic("nomatch") == []


# ── diff_general_section ──────────────────────────────────────────────────────


def test_diff_general_section_new_file(wiki_dir):
    diff = gw.diff_general_section("newpage.md", "# New\n")
    assert "+" in diff


def test_diff_general_section_no_changes(wiki_dir):
    (wiki_dir / "existing.md").write_text("# Same\n", encoding="utf-8")
    diff = gw.diff_general_section("existing.md", "# Same\n")
    assert diff == "(no changes)"


def test_diff_general_section_traversal_blocked(wiki_dir):
    with pytest.raises(ValueError):
        gw.diff_general_section("../escape.md", "content")


# ── write_general_section ─────────────────────────────────────────────────────


def test_write_general_section_creates_file(wiki_dir):
    gw.write_general_section("nutrition.md", "# Nutrition\nContent\n")
    assert (wiki_dir / "nutrition.md").exists()
    assert "Content" in (wiki_dir / "nutrition.md").read_text(encoding="utf-8")


def test_write_general_section_subdirectory(wiki_dir):
    gw.write_general_section("races/alpenbrevet.md", "# Alpenbrevet\n")
    assert (wiki_dir / "races" / "alpenbrevet.md").exists()


# ── append_general_log ────────────────────────────────────────────────────────


def test_append_general_log_creates_log(wiki_dir):
    gw.append_general_log("added nutrition page")
    log = wiki_dir / "log.md"
    assert log.exists()
    content = log.read_text(encoding="utf-8")
    assert "added nutrition page" in content
    assert "General Wiki Log" in content


def test_append_general_log_multiple_entries(wiki_dir):
    gw.append_general_log("first")
    gw.append_general_log("second")
    content = (wiki_dir / "log.md").read_text(encoding="utf-8")
    assert "first" in content
    assert "second" in content
