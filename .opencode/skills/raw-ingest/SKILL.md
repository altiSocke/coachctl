---
name: raw-ingest
description: Ingest a new file from raw/ into the wiki knowledge layers. Use when the athlete points you at a new file they have added to raw/ (papers, race captures, GPX, scans). Encodes the full 7-step read→classify→load→draft→propose→wait→apply workflow including layer boundary rules and wiki target path mapping.
compatibility: opencode
---

## What I do

Guide the full ingestion of a new `raw/` source document into the appropriate wiki layer, with correct boundary classification, propose/confirm flow, and audit logging.

---

## Layer boundary rule

> *If two athletes could share it → **general** (`wiki/`); otherwise → **personal** (`<DATA_ROOT>/profile/`). If unsure, **personal wins**.*

### Content → target path mapping

| Content type | Layer | Target path |
|---|---|---|
| Peer-reviewed paper or evidence summary | general | `wiki/sources/<topic>.md` + update matching topical page |
| Race website capture / course data / GPX | general | `wiki/races/<race>.md` |
| Generic recovery or training protocol | general | `wiki/recovery/<protocol>.md` |
| Topical synthesis (cycling, running, nutrition science) | general | `wiki/<topic>.md` |
| Athlete's personal race result or time | personal | `<DATA_ROOT>/profile/goals.md` |
| Athlete's personal fueling inventory or race-day plan | personal | `<DATA_ROOT>/profile/nutrition.md` |
| Athlete's injury, cramp, or incident | personal | `<DATA_ROOT>/profile/training_history.md` |
| Coach observation about this athlete | personal | via `save_coaching_note` |
| Race plan for a partner / second athlete | personal | `<DATA_ROOT>/profile/<race>_<name>.md` |

### Boundary cheat sheet

| Goes to **general** `wiki/` | Goes to **personal** `profile/` |
|---|---|
| Course profile facts, climb gradients, cutoffs | "I cramped on Furka in 2024" |
| Polarized training theory, periodization models | My Z2 HR cap is 148 |
| Gel science, carb-oxidation rates, hydration norms | What's in my race-day fuel kit |
| Generic recovery protocols (massage, sauna) | My current injury & rehab plan |
| Race logistics open to any participant | My A/B/C goals and pacing strategy |

---

## 7-step ingest workflow

Execute these steps in order. Do not skip or batch.

### Step 1 — Read
Read the file using the OpenCode `read` file tool. Do not call any wiki tool yet.

### Step 2 — Classify
Apply the boundary rule:
- **Peer-reviewed paper or evidence summary** → `wiki/sources/<topic>.md` catalogue (and possibly the matching topical page e.g. `running.md`, `nutrition.md`)
- **Race website capture / GPX / course data** → `wiki/races/<race>.md`
- **Anything specific to this athlete** (their result, their plan, their incident) → personal wiki, not general

Tell the athlete your classification decision and the target path before proceeding.

### Step 3 — Load current state
Call `read_general_wiki(topic)` for every general page you intend to touch. For personal pages, read the current file content. Do this for **all** pages, not just the primary one — a paper may touch both `wiki/sources/training.md` and `wiki/running.md`.

### Step 4 — Draft
Before writing, check whether the raw file alone is sufficient:

- **If the raw file is a full document** (paper, detailed GPX, comprehensive race capture): draft directly from its content.
- **If the raw file is sparse, a brief website capture, or you need supplementary facts** (elevation data, race logistics, updated evidence, scientific context): load the `deep-research` skill and run a targeted search before drafting. Use the research findings to enrich the wiki page. Attach all sources — raw file path plus any web sources — in the `## Sources` section.

Write the updated content:
- Keep general pages completely athlete-agnostic. Never include personal results, names, or targets.
- Add or extend a `## Sources` section at the bottom of every general page you touch, listing the `raw/` path(s) it now synthesises. Example:
  ```
  ## Sources
  - raw/knowledge/polarized_training_seiler_2010.pdf
  - raw/races/greifenseelauf_course_capture.md
  ```
- For paper catalogues (`wiki/sources/`): include abstract summary, key findings, citation, and practical implications for endurance athletes.
- For race pages (`wiki/races/`): include course distance, elevation profile, key climbs (gradient, length), surface, typical weather, aid stations, cutoffs, logistics. No personal targets.

### Step 5 — Propose
Call `propose_general_wiki_update(topic, content, reason)` for each general page changed.
Call `propose_wiki_update(section, content, reason)` for each personal page changed.

**One call per page.** Do not batch unrelated pages into a single propose call. Present each diff to the athlete before moving to the next.

### Step 6 — Wait for approval
**Do not apply anything until the athlete explicitly says yes.** If they request changes, redraft and propose again. Only proceed to Step 7 when you have a clear approval for each page.

### Step 7 — Apply
Call `apply_general_wiki_update(topic, content)` for approved general pages.
Call `apply_wiki_update(section, content)` for approved personal pages.
Each apply auto-logs to the relevant `log.md`. Confirm to the athlete which pages were updated.

### Step 8 — Rebuild SwarmVault index
After all general wiki pages have been applied, run:
```bash
swarmvault compile
```
This rebuilds the knowledge graph and FTS index in `state/` so future `swarmvault_query` calls reflect the new content. Skip this step if only personal (`profile/`) pages were updated — SwarmVault indexes the public `wiki/` layer only.

---

## Immutability rules

- **Never** edit, append to, rename, or delete anything inside `raw/` — even to fix a typo.
- If a raw file contains an error, ask the human to add a corrected version as a new file.
- `raw/` is the source of record. The wiki is the synthesis. They are separate layers.

---

## After ingest

If the new source materially changes a training recommendation (e.g. new evidence on carb oxidation rates, revised course profile), flag this to the athlete and propose updating the relevant coaching note or plan section as a follow-up action.
