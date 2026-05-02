# raw/general/ — Immutable public source documents

This directory holds source material that informs the **general** wiki layer:
peer-reviewed papers, race-website captures, public data exports, course maps.

> Personal source documents (your GPX files, race photos, scans, training-camp
> notes) live in your private personal repo at ``<DATA_ROOT>/raw/`` — never here.

## Rules

- **Human-write-only.** Files are added only by humans (or an ingest pipeline).
- **The LLM never modifies anything in `raw/`.** It only reads.
- **Treat as immutable** once added. Create a new file rather than editing.
- **Organise by domain** under subdirectories: `races/`, etc.

> LLM-written knowledge syntheses live in `wiki/general/`, not here.
> See `AGENTS.md` for the three-layer architecture.

## Adding a source

1. Copy or download the file into an appropriate subdirectory.
2. Tell the coach: *"I've added a new source at `raw/general/path/to/file` —
   please ingest it."*
3. The coach reads it and proposes updates to the relevant `wiki/general/` pages
   via `propose_general_wiki_update`.

## Current contents

### races/

| File | Topic | Added |
|------|-------|-------|
| `greifensee_halbmarathon_2026.md` | Race-day capture: course, aid stations, logistics | 2026-04 |
| `sola_strecken_asvz.md` | ASVZ SOLA stage descriptions (website capture) | 2026-04 |
