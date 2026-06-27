# coachctl — Architecture & Conventions

Canonical reference for the project's structure, knowledge layers, and conventions.
README.md owns setup/install/deploy; `.opencode/agents/coach.md` owns operational
workflows. **This file is the single source of truth for architecture.**

---

## Two-repo split

`coachctl` is published as **two coupled repos**:

| Repo | Visibility | Contents | Watcher |
|---|---|---|---|
| `coachctl` (this repo) | public | code, dashboard UI source | — |
| `coachctl-personal` (per-athlete) | private | wiki (general + personal), secrets, activities DB, baked dashboard data, Vercel deploy surface | Vercel auto-deploy |

Dependency direction is **strictly one-way**: the private repo depends on the
public one via `pip install`. The public repo never reads, imports, or assumes
anything about the private repo.

```
 ┌──────────────── coachctl  (public)  ────────────────┐
 │                                       src/...       │
 │                                       (code + UI)   │
 └──────────────────────────────────────────┬──────────┘
                                            │ pip install
                                            ▼
 ┌─────────── coachctl-personal (private) ───────────────┐
 │  raw/   wiki/          profile/*.md   data/activities.db│
 │         (general)      athlete.yaml   deploy/dist/data.json│
 │                                       .env              │
 │         deploy/web.py ─────────────► Vercel             │
 └──────────────────────────────────────────────────────────┘
                                           ▲
                   coachctl update ──┘  (sync→bake→push)
```

Path resolution lives in `src/coachctl/paths.py`:

* **`code_root()`** — this checkout. Hosts code, dashboard UI source, and templates only.
* **`data_root()`** — resolved in this order:
  1. `AGENT_DATA_ROOT` environment variable.
  2. Sibling `../coachctl-personal/` directory (auto-discovered).
  3. Legacy fallback: `<code_root>/wiki/personal/<STRAVA_PROFILE>` — emits a
     `DeprecationWarning`.

`STRAVA_PROFILE` is **optional** — used as a label and for the legacy fallback only.

---

## Public-repo layout

```
src/coachctl/         ← Python package
  mcp_server.py            — MCP server entrypoint (FastMCP)
  paths.py                 — code_root + data_root resolver
  config.py                — athlete.yaml loader
  db.py                    — SQLite schema + connection
  sync.py                  — Strava OAuth2 + incremental activity sync
  metrics.py               — TSS, CTL/ATL/TSB, NGP, zone calculations
  plan_parser.py           — Markdown plan → dataclasses
  workouts.py              — WorkoutSpec/WorkoutStep schema + Event bridge
  workout_archetypes.py    — pure WorkoutSpec constructors (one per session type)
  workout_generators.py    — week generators (race-week, post-race, half-marathon)
  plan_templates.py        — plan templates as Python data (DaySlot/WeekTemplate/PlanTemplate)
  plan_expander.py         — expand_template(template, start, seed) → list[WorkoutSpec]
  workout_preview.py       — reconcile engine (preview create/update/match/skip; no writes)
  workout_apply.py         — apply previews to events (the only writer); sandbox-first plan apply
  sandbox.py               — sandboxed_db() — temp DB copy for validate-before-write
  site.py                  — bake data.json
  new_profile.py           — scaffolds a new coachctl-personal repo
  update.py                — sync + bake + git push (in personal repo)
  wiki_base.py             — shared diff/write/log/safe-resolve helpers
  wiki.py                  — Personal Wiki (binds wiki_base to personal_dir)
  general_wiki.py          — General Wiki (binds wiki_base to general_wiki_dir)
  dashboard/               — FastAPI factory + app.html + dev server
    __init__.py            — exports create_app()
    server.py              — soft-failing dashboard factory
    app.html               — single-page UI
    __main__.py            — `strava-web` CLI entry (local dev)
  tools/                   — MCP @tool registrations (one module per domain)

config/athlete.yaml.template
.opencode/agents/coach.md  ← coach agent operational workflows
AGENTS.md                  ← this file
README.md                  ← user-facing setup, install, deployment
```

## Personal-repo layout (`coachctl-personal`)

```
wiki/                      ← Layer 2a — LLM-maintained, athlete-agnostic knowledge
  races/  recovery/  sources/  ...
profile/                  ← Layer 2b — LLM-maintained, this athlete only
  athlete.yaml             thresholds, events, weight
  profile.md  goals.md  nutrition.md  training_history.md
  readiness.md  index.md  log.md  plans_index.md
  plans/                   generated training plan markdown
  feedback/                session feedback (YAML)
data/
  activities.db            Strava activity cache (committed; LFS once large)
raw/                      ← Layer 1 — all source documents (papers, race captures, GPX, scans)
  races/  sources/  ...
deploy/                    ← Vercel project root
  web.py                   from coachctl.dashboard import create_app; ...
  vercel.json
  requirements.txt         pins coachctl[dashboard] @ git+https://...
  dist/                    ← Build artifacts (generated by `bake`)
    data.json              baked dashboard payload (read by Vercel)
.env                       Strava + Google secrets (git-ignored)
.env.example
README.md
```

---

## Three-layer knowledge architecture

The knowledge model has three layers with strictly different write rules.

### Layer 1 — `raw/` (immutable, human-write-only)

Source material as it arrived. Lives in `<DATA_ROOT>/raw/` (`coachctl-personal/raw/`):
papers, race-website captures, public data exports, GPX files, race photos, scans,
training-camp notes — everything in one place.

**Rules:**

- Humans (or an ingest pipeline) are the only writers.
- The LLM **reads** raw files when synthesising wiki updates. It **never**
  modifies, appends, deletes, or renames anything in `raw/`.
- Treat files as immutable once added — create a new file rather than editing.

> If the LLM produces a synthesis (paper catalogue, course summary, distilled
> protocol), that synthesis lives in a `wiki/` layer — never in `raw/`.

### Layer 2a — `wiki/` (LLM-maintained, athlete-agnostic, private)

Lives in the **personal repo** (`coachctl-personal/wiki/`). Synthesised from `raw/` and from coaching
expertise. Useful to **any** athlete using the system but kept private to avoid
leaking context about which races or protocols are in use.

- **Write rule:** content here must be useful to *any* athlete using the system.
  Physiology, training theory, course facts, nutrition science, evidence reviews.
- **Never** put personal results, personal targets, or personal incidents here —
  they belong in Layer 2b.
- **Update workflow:**
  1. `read_general_wiki(topic)` — load current content.
  2. Draft updated content incorporating the new source.
  3. `propose_general_wiki_update(topic, content, reason)` — present diff.
  4. Athlete approves → `apply_general_wiki_update(topic, content)`.
- Auto-logged to `wiki/log.md`.
- Pages may include a `## Sources` section listing the `raw/` paths they
  synthesise.

#### Subdirectories

- `wiki/sources/` — paper catalogues (abstracts + citations).
- `wiki/races/` — course facts, profiles, logistics, athlete-agnostic.
- `wiki/recovery/` — protocol-level guides.

### Layer 2b — `<data_root>/profile/` (LLM-maintained, this athlete, private)

Lives in the personal repo. Athlete-specific facts: thresholds, goals, past
results, injury history, coaching notes, race-day plans.

- **Write rule:** anything specific to *this* athlete — including race targets,
  past times, cramps, preferences, nutrition inventory — goes here.
- **Update workflow:**
  - Narrative updates: `propose_wiki_update` → athlete approves → `apply_wiki_update`.
  - Additive coaching notes: `save_coaching_note` (no approval, appends directly).
- Every `apply_wiki_update` auto-appends a timestamped entry to `log.md`.
- `log.md` is **append-only** — never rewritten or truncated by the LLM.

#### Schema

| File | Purpose | Writer |
|---|---|---|
| `athlete.yaml` | Thresholds, weight, events, zones | Human-maintained config |
| `profile.md` | Physiology, performance estimates, coaching instructions | LLM (propose/apply) |
| `goals.md` | Target events, race strategies, YoY benchmarks | LLM (propose/apply) |
| `nutrition.md` | Personal fueling protocols, gel inventory, race-day plans | LLM (propose/apply) |
| `training_history.md` | Coaching notes index, injury log | LLM (propose/apply) |
| `readiness.md` | Subjective check-in log | LLM (propose/apply after `log_readiness_checkin`) |
| `plans_index.md` | Table of saved plans | Auto-proposed by `save_plan` |
| `index.md` | Catalog of all wiki files | LLM (manually maintained) |
| `log.md` | Append-only audit log | Auto-written by `apply_wiki_update` |
| `plans/` | LLM-generated training plan markdown files | `save_plan` |
| `feedback/` | Human-entered session feedback (YAML) | `log_feedback` |

Race-specific personal plans (e.g. a partner's race) may live as additional
markdown files alongside the schema; reference them from `index.md`.

#### Build artifacts

| Path | Purpose | Writer |
|---|---|---|
| `deploy/dist/data.json` | Baked dashboard payload, bundled into the Vercel function and read at cold-start | `bake` |
| `data/activities.db` | Strava activity cache, queryable via SQL | `sync_activities` |

`deploy/dist/` and `data/` are committed to the personal repo (so Vercel and
other clones get them) but contain only generated content — never hand-edit.
The bake target lives inside `deploy/` so the Vercel `@vercel/python` builder
bundles it alongside `web.py`.

### Boundary rule

> *"If two athletes could share it, it belongs in **general** (private wiki);
>  otherwise **personal** (private profile). If unsure, **personal** wins."*

A course-level fact about a race → general. A time, a cramp, a goal, a
strategy → personal.

#### Cheat sheet

| Goes to **general** `wiki/` | Goes to **private** `profile/` |
|---|---|
| Course profile facts, climb gradients, cutoffs | "I cramped on Furka in 2024" |
| Polarized training theory, periodization models | My Z2 HR cap is 148 |
| Gel science, carb-oxidation rates, hydration norms | What's in my race-day fuel kit |
| Generic recovery protocols (massage, sauna) | My current injury & rehab plan |
| Race logistics open to any participant | My A/B/C goals and pacing strategy |

### Two-repo write semantics

A coaching session that updates both layers will commit to two repos:

* General-wiki edits land in the **personal repo** (`coachctl-personal/wiki/`).
  `uv run coachctl update` automates sync → bake → commit → push for all personal-repo changes.
* Personal-wiki edits, plans, feedback, baked `data.json` also land in the **personal
  repo**. `uv run coachctl update` automates sync → bake → commit → push.

---

## Dashboard deployment (Vercel)

* The personal repo is connected to Vercel; root directory is `deploy/`.
* `deploy/web.py` calls `coachctl.dashboard.create_app(deploy/dist/data.json)`.
* `requirements.txt` pins the public package via `pip install`. Bumping the ref
  rolls UI updates forward without touching the personal repo's content.
* Cold-start is **soft-fail**: a missing or unreadable `data.json` returns HTTP
  503 with a setup message instead of crashing the function.
* `bake` writes `deploy/dist/data.json` (inside Vercel's project root, so the
  artifact is bundled into the function); `git push` of that file triggers
  Vercel redeploy.

---

## Key design decisions

- **SQLite** for activity storage — queryable, portable. Lives in the personal
  repo, committed (Git LFS recommended once >50MB).
- **`events` table as single calendar truth.** All date-anchored items (races,
  training sessions, untracked activities, appointments) live in one table.
  The projection layer (`events.py`) merges events-table rows with activities
  and legacy sources (plan markdown, schedule_overrides, untracked_activities)
  during migration. Races block training/untracked on the same date. Consumers
  (`bake`, MCP tools) read from `get_calendar()` — never from
  narrative wiki text.
- **Race cards as structured payload.** Each race event has a `payload_json`
  column holding all sections (pacing, climbs, nutrition, kit, logistics,
  protocols, YoY, readiness gate). Edited per-section via `propose_race_*` /
  `apply_race_*` MCP tools with unified-diff confirmation flow.
- **YAML** for feedback, **Markdown** for plans — human-readable, git-diffable.
- **No multi-tenant code repo.** One personal repo per athlete; switch via
  `AGENT_DATA_ROOT`.
- **Code-data decoupling.** UI updates flow to deployed dashboards through a
  `pip install -U coachctl` bump in the personal repo's `requirements.txt`.

## Deterministic workout engine

A structured, reproducible alternative to free-text plan markdown. Generates
sessions from Python data, reconciles them against the real multi-sport
calendar, and never overwrites non-endurance work. Two plan paths coexist:

| Path | Entry | Use when |
|---|---|---|
| **Markdown plan** | `save_plan(markdown)` MCP tool (`plan_tools.py`) → `plan_parser` → blind `upsert_event` per session | bespoke, narrative, athlete-reviewed plans; full prose control |
| **Deterministic engine** | `preview_plan` / `apply_plan` MCP tools (`workout_tools.py`) | reproducible, template-driven plans that must coexist with existing rides / strength / races |

### Pipeline (one-way)

```
plan_templates.py   (PlanTemplate = weeks[] of DaySlot, hardcoded per-week TSS)
      │  expand_template(template, start, seed)
      ▼
plan_expander.py    → list[WorkoutSpec]   (seed=None deterministic; seed=N reproducible variation)
      │  workout_archetypes.py  (pure WorkoutSpec constructors)
      ▼
workout_preview.py  → preview_plan_from_db   (read-only reconcile: create/update/match/skip)
      │
      ▼
workout_apply.py    → apply_plan_from_db   (sandbox-validated; the ONLY writer)
      │  sandbox.py: copy DB → apply → re-preview (must converge) → bake → then live
      ▼
events table
```

### Reconcile rules (apply never clobbers the calendar)

- **Names preserved on update.** An existing event's `name` is kept; only
  `summary`/`estimated_tss`/`duration`/`payload`/`status` are updated. New dates
  get the generated name. (Reconcile-scoped — an author/regenerate path, if
  added, would own names.)
- **Strength untouched.** Strength sessions are never created, updated, or
  overwritten — only counted (`strength_preserved`).
- **Races block their day.** Generated sessions landing on a race date are
  dropped (`suppressed_race_days`).
- **Ambiguous days skipped.** Two existing endurance sessions on one date →
  `skip`, never a blind overwrite.
- **Rest creates suppressed** unless `create_rest_days=True`.
- **Semantic diff.** Cosmetic-only deltas (en/em dash, `×`→`x`, whitespace) in
  `summary` do not force an update.

### Determinism & variation

- `seed=None` (or MCP `seed=-1`) — fully deterministic, no PRNG: base variant,
  no jitter. Same `(template, start)` → identical output.
- `seed=N` — one `random.Random(N)` drives quality-session rotation
  (`cruise_intervals` / `ladder_intervals` / `mona_fartlek`) and ±5min jitter on
  easy/long runs. Same `(template, start, seed)` → identical output.

### Sandbox-first apply

`apply_plan_from_db` validates before writing live: it copies the DB to a temp
file (`sandboxed_db()`, via `paths.set_db_path_override`), applies there,
re-previews (must converge to no further create/update or it raises
`sandbox_not_converged`), and bakes into an isolated `data.json` override — only
then replays the same changes against the live DB. `apply_plan` writes events
only; it does **not** publish `data.json` (call `bake` separately, like every
other apply path). CLI equivalents: `coachctl preview-plan` / `apply-plan`.

## Key metrics

- **TSS** — power-based for cycling (Coggan), pace-based rTSS for running
  (Minetti grade-adjusted), hrTSS (Banister TRIMP) as fallback.
  Priority: power > pace > HR.
- **CTL** (Chronic Training Load) — 42-day EMA, fitness proxy.
  Sustainable ramp 3–7 TSS/week; >10/week is risky.
- **ATL** (Acute Training Load) — 7-day EMA, fatigue proxy.
- **TSB** (Training Stress Balance) — `CTL − ATL`, form. Peak A races at +15 to +25.
- **Polarization index** — ratio of low-intensity (Z1+Z2) to high-intensity (Z4+Z5) time.

Formulas live in `src/coachctl/metrics.py`. All TSS values are computed at
sync time and stored in `activities.tss`.

