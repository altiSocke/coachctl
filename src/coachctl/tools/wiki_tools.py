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
        <DATA_ROOT>/profile/ — use propose_wiki_update instead.

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

    # ── Wiki search ───────────────────────────────────────────────────────────

    @mcp.tool()
    def search_wiki(query: str, max_results: int = 15) -> str:
        """
        Full-text keyword search across both wiki layers.

        Searches:
        - General wiki: wiki/ (athlete-agnostic knowledge)
        - Personal wiki: <data_root>/profile/ (athlete-specific knowledge)

        Returns matching lines with file path and line number, sorted by
        relevance (files with more matches appear first).

        Parameters
        ----------
        query       : keyword or phrase to search for (case-insensitive).
        max_results : maximum number of matching lines to return (default 15).

        Use this when you know a topic exists somewhere in the wiki but you
        don't know the exact filename. For reading a full page use
        read_general_wiki(topic) or get_athlete_wiki() instead.
        """
        import re as _re

        if not query or not query.strip():
            return "Error: query must be a non-empty string."

        max_results = max(1, min(max_results, 100))
        pattern = _re.compile(_re.escape(query.strip()), _re.IGNORECASE)

        search_dirs = []
        wiki_dir = paths.general_wiki_dir()
        if wiki_dir.exists():
            search_dirs.append(("general_wiki", wiki_dir))
        profile_dir = paths.personal_dir()
        if profile_dir.exists():
            search_dirs.append(("personal_wiki", profile_dir))

        # Collect all matches: (layer, rel_path, line_number, line_text)
        file_hits: dict[str, list[dict]] = {}  # file_key → list of match dicts

        for layer, base_dir in search_dirs:
            for md_file in sorted(base_dir.rglob("*.md")):
                try:
                    text = md_file.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                rel = str(md_file.relative_to(base_dir))
                file_key = f"{layer}:{rel}"
                for lineno, line in enumerate(text.splitlines(), start=1):
                    if pattern.search(line):
                        if file_key not in file_hits:
                            file_hits[file_key] = []
                        file_hits[file_key].append(
                            {
                                "line": lineno,
                                "text": line.strip()[:200],
                            }
                        )

        if not file_hits:
            return f"No matches found for '{query}' in either wiki layer."

        # Sort files by hit count descending, then alphabetically
        sorted_files = sorted(file_hits.items(), key=lambda x: (-len(x[1]), x[0]))

        results = []
        total_shown = 0
        for file_key, hits in sorted_files:
            if total_shown >= max_results:
                break
            layer, rel_path = file_key.split(":", 1)
            remaining = max_results - total_shown
            shown_hits = hits[:remaining]
            results.append(
                {
                    "file": rel_path,
                    "layer": layer,
                    "total_matches": len(hits),
                    "matches": shown_hits,
                }
            )
            total_shown += len(shown_hits)

        import json as _json

        return _json.dumps(
            {
                "query": query,
                "files_matched": len(file_hits),
                "results": results,
            },
            indent=2,
        )
