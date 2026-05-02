"""Athlete wiki tools: read, propose, and apply wiki updates (personal + general)."""

from __future__ import annotations

from .. import paths
from ..db import get_conn
from ..general_wiki import (
    append_general_log,
    diff_general_section,
    resolve_topic,
    write_general_section,
)
from ..wiki import (
    VALID_SECTIONS,
    append_log,
    diff_section,
    is_seeded,
    read_wiki_combined,
    seed_wiki,
    write_section,
)


def register(mcp) -> None:  # noqa: ANN001

    @mcp.tool()
    def get_athlete_wiki() -> str:
        """
        Load the athlete wiki — persistent markdown knowledge about the athlete.
        Returns all wiki files (profile, goals, training history, plans index)
        concatenated for context injection.
        Auto-seeds from athlete.yaml and coaching notes on first call.
        Call this at the start of every session.
        """
        if not is_seeded():
            with get_conn() as conn:
                created = seed_wiki(conn)
            if created:
                header = f"Wiki seeded from existing data: {', '.join(created)}\n\n"
            else:
                header = "Wiki is empty and no seed data found.\n\n"
            return header + read_wiki_combined()
        return read_wiki_combined()

    @mcp.tool()
    def propose_wiki_update(section: str, proposed_content: str, reason: str) -> str:
        """
        Propose a change to a wiki file and return the unified diff.
        Does NOT write anything — present the diff to the athlete for confirmation.
        section: filename, e.g. 'goals.md', 'training_history.md', 'profile.md', 'plans_index.md'
        proposed_content: the full new content for the file
        reason: short explanation of why this update is proposed
        """
        if section not in VALID_SECTIONS:
            return (
                f"Invalid section '{section}'. Must be one of: {', '.join(sorted(VALID_SECTIONS))}"
            )

        diff_text = diff_section(section, proposed_content)
        return (
            f"**Proposed update to {section}**\n"
            f"Reason: {reason}\n\n"
            f"```diff\n{diff_text}\n```\n\n"
            "Reply 'yes' to apply, or suggest changes."
        )

    @mcp.tool()
    def apply_wiki_update(section: str, content: str) -> str:
        """
        Write a confirmed update to a wiki file.
        Only call this after the athlete has explicitly approved the proposed diff.
        section: filename, e.g. 'goals.md'
        content: the full new content for the file
        """
        if section not in VALID_SECTIONS:
            return (
                f"Invalid section '{section}'. Must be one of: {', '.join(sorted(VALID_SECTIONS))}"
            )

        p = write_section(section, content)
        append_log(f"apply_wiki_update: {section}")
        return f"Wiki updated: {p.name}"

    @mcp.tool()
    def read_general_wiki(topic: str = "") -> str:
        """
        Read from the general fitness knowledge wiki (wiki/).
        The general wiki is LLM-maintained — update it via
        propose_general_wiki_update / apply_general_wiki_update when new
        raw/ sources arrive or content needs revision.
        raw/ is the immutable layer — source documents added by humans only.
        Never write to raw/ via any tool.

        topic: optional subdirectory or filename stem, e.g. 'nutrition',
               'races/alpenbrevet', 'sources/foot_health'.
               Leave empty to list available files.
        """
        wiki_dir = paths.general_wiki_dir()
        if not wiki_dir.exists():
            return "wiki/ directory not found."

        if not topic:
            files = sorted(wiki_dir.rglob("*.md"))
            if not files:
                return "No knowledge files found in wiki/."
            lines = ["Available general wiki files:\n"]
            for f in files:
                lines.append(f"  - {f.relative_to(wiki_dir)}")
            return "\n".join(lines)

        matches = resolve_topic(topic)
        if not matches:
            return (
                f"No file found matching '{topic}'. "
                "Call read_general_wiki() with no argument to list all files."
            )
        if len(matches) == 1:
            return matches[0].read_text(encoding="utf-8")
        parts = []
        for m in matches:
            rel = m.relative_to(wiki_dir)
            parts.append(f"═══ {rel} ═══\n{m.read_text(encoding='utf-8')}")
        return "\n\n".join(parts)

    @mcp.tool()
    def propose_general_wiki_update(topic: str, proposed_content: str, reason: str) -> str:
        """
        Propose a change to a general wiki file and return the unified diff.
        Does NOT write anything — present the diff for confirmation before applying.

        Use this when:
        - A new raw/ source has been added and general wiki needs updating.
        - Existing general wiki content is outdated or incorrect.
        - A new topic page needs to be created in wiki/.

        IMPORTANT: Only write content that applies to any athlete (physiology,
        training theory, course facts, nutrition science). Athlete-specific data
        (personal results, personal targets, personal incidents) belongs in
        wiki/personal/ — use propose_wiki_update instead.

        topic: relative path within wiki/, e.g. 'nutrition',
               'races/alpenbrevet', 'recovery/percussion_massage'.
               A new file will be created if it doesn't exist.
        proposed_content: the full new content for the file (Markdown).
        reason: short explanation of why this update is proposed.
        """
        try:
            diff_text = diff_general_section(topic, proposed_content)
        except ValueError as e:
            return f"Error: {e}"

        return (
            f"**Proposed update to wiki/{topic}**\n"
            f"Reason: {reason}\n\n"
            f"```diff\n{diff_text}\n```\n\n"
            "Reply 'yes' to apply, or suggest changes."
        )

    @mcp.tool()
    def apply_general_wiki_update(topic: str, content: str) -> str:
        """
        Write a confirmed update to a general wiki file.
        Only call this after the proposed diff has been reviewed and approved.
        Logs the change to wiki/log.md.

        topic: relative path within wiki/, e.g. 'nutrition',
               'races/alpenbrevet'. Parent directories are created automatically.
        content: the full new content for the file (Markdown).
        """
        try:
            p = write_general_section(topic, content)
        except ValueError as e:
            return f"Error: {e}"

        append_general_log(f"apply_general_wiki_update: {topic}")
        return f"General wiki updated: wiki/{p.relative_to(paths.general_wiki_dir())}"
