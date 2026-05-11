"""
Tests for coachctl.wiki_base — safe_resolve, diff_file, write_file, append_text, append_log, resolve_topic.
"""

from __future__ import annotations

import pytest

from coachctl.wiki_base import (
    append_log,
    append_text,
    diff_file,
    resolve_topic,
    safe_resolve,
    write_file,
)


# ── safe_resolve ──────────────────────────────────────────────────────────────


def test_safe_resolve_simple(tmp_path):
    result = safe_resolve(tmp_path, "goals.md")
    assert result == tmp_path.resolve() / "goals.md"


def test_safe_resolve_auto_appends_md(tmp_path):
    result = safe_resolve(tmp_path, "goals")
    assert result.suffix == ".md"


def test_safe_resolve_strips_leading_slash(tmp_path):
    result = safe_resolve(tmp_path, "/goals.md")
    assert result == tmp_path.resolve() / "goals.md"


def test_safe_resolve_strips_dotslash(tmp_path):
    result = safe_resolve(tmp_path, "./goals.md")
    assert result == tmp_path.resolve() / "goals.md"


def test_safe_resolve_subdirectory(tmp_path):
    result = safe_resolve(tmp_path, "races/alpenbrevet.md")
    assert result == tmp_path.resolve() / "races" / "alpenbrevet.md"


def test_safe_resolve_traversal_blocked(tmp_path):
    with pytest.raises(ValueError, match="resolves outside"):
        safe_resolve(tmp_path, "../secret.md")


def test_safe_resolve_deep_traversal_blocked(tmp_path):
    with pytest.raises(ValueError, match="resolves outside"):
        safe_resolve(tmp_path, "sub/../../outside.md")


# ── diff_file ─────────────────────────────────────────────────────────────────


def test_diff_file_new_file(tmp_path):
    target = tmp_path / "new.md"
    diff = diff_file(target, "# Hello\n")
    assert "Hello" in diff
    assert "+" in diff


def test_diff_file_no_changes(tmp_path):
    target = tmp_path / "same.md"
    target.write_text("# Same\n", encoding="utf-8")
    diff = diff_file(target, "# Same\n")
    assert diff == "(no changes)"


def test_diff_file_shows_removed_line(tmp_path):
    target = tmp_path / "mod.md"
    target.write_text("# Old\n", encoding="utf-8")
    diff = diff_file(target, "# New\n")
    assert "-" in diff and "+" in diff


def test_diff_file_custom_label(tmp_path):
    target = tmp_path / "x.md"
    diff = diff_file(target, "content\n", label="custom-label")
    assert "custom-label" in diff


# ── write_file ────────────────────────────────────────────────────────────────


def test_write_file_creates_file(tmp_path):
    target = tmp_path / "sub" / "new.md"
    write_file(target, "# Content\n")
    assert target.exists()
    assert target.read_text(encoding="utf-8") == "# Content\n"


def test_write_file_overwrites(tmp_path):
    target = tmp_path / "existing.md"
    target.write_text("old", encoding="utf-8")
    write_file(target, "new")
    assert target.read_text(encoding="utf-8") == "new"


def test_write_file_returns_path(tmp_path):
    target = tmp_path / "ret.md"
    result = write_file(target, "x")
    assert result == target


# ── append_text ───────────────────────────────────────────────────────────────


def test_append_text_creates_file(tmp_path):
    target = tmp_path / "log.md"
    append_text(target, "first line")
    assert target.exists()
    assert "first line" in target.read_text(encoding="utf-8")


def test_append_text_appends_to_existing(tmp_path):
    target = tmp_path / "log.md"
    target.write_text("line1\n", encoding="utf-8")
    append_text(target, "line2")
    content = target.read_text(encoding="utf-8")
    assert "line1" in content
    assert "line2" in content


def test_append_text_adds_newline(tmp_path):
    target = tmp_path / "log.md"
    append_text(target, "no newline")
    assert target.read_text(encoding="utf-8").endswith("\n")


def test_append_text_returns_path(tmp_path):
    target = tmp_path / "r.md"
    result = append_text(target, "x")
    assert result == target


# ── append_log ────────────────────────────────────────────────────────────────


def test_append_log_creates_with_header(tmp_path):
    log = tmp_path / "log.md"
    append_log(log, "My Log", "first entry")
    content = log.read_text(encoding="utf-8")
    assert "My Log" in content
    assert "first entry" in content


def test_append_log_appends_to_existing(tmp_path):
    log = tmp_path / "log.md"
    append_log(log, "Log", "entry one")
    append_log(log, "Log", "entry two")
    content = log.read_text(encoding="utf-8")
    assert "entry one" in content
    assert "entry two" in content


def test_append_log_contains_timestamp(tmp_path):
    log = tmp_path / "log.md"
    append_log(log, "Log", "timestamped entry")
    content = log.read_text(encoding="utf-8")
    # ISO timestamp has T separator and colons
    assert "T" in content  # e.g. 2026-05-05T10:23:45


def test_append_log_returns_path(tmp_path):
    log = tmp_path / "log.md"
    result = append_log(log, "Log", "x")
    assert result == log


# ── resolve_topic ─────────────────────────────────────────────────────────────


def test_resolve_topic_empty_string(tmp_path):
    assert resolve_topic(tmp_path, "") == []


def test_resolve_topic_exact_file(tmp_path):
    f = tmp_path / "nutrition.md"
    f.write_text("# Nutrition\n", encoding="utf-8")
    result = resolve_topic(tmp_path, "nutrition.md")
    assert f in result


def test_resolve_topic_without_extension(tmp_path):
    f = tmp_path / "nutrition.md"
    f.write_text("# Nutrition\n", encoding="utf-8")
    result = resolve_topic(tmp_path, "nutrition")
    assert f in result


def test_resolve_topic_substring_match(tmp_path):
    f = tmp_path / "race_nutrition.md"
    f.write_text("# Race Nutrition\n", encoding="utf-8")
    result = resolve_topic(tmp_path, "nutrition")
    assert f in result


def test_resolve_topic_no_match(tmp_path):
    (tmp_path / "unrelated.md").write_text("x\n", encoding="utf-8")
    result = resolve_topic(tmp_path, "zzznomatch")
    assert result == []


def test_resolve_topic_traversal_returns_empty(tmp_path):
    result = resolve_topic(tmp_path, "../escape")
    assert result == []


def test_resolve_topic_nonexistent_base(tmp_path):
    result = resolve_topic(tmp_path / "nonexistent", "topic")
    assert result == []
