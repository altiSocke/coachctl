# Next steps — deterministic workout engine

Status snapshot (this branch): Phases 1–4 of the deterministic plan engine are
implemented and tested; the engine is exposed as MCP tools (`list_plan_templates`,
`preview_plan`, `apply_plan`) and documented in `AGENTS.md`. Full suite: 731
passing. Nothing committed yet.

This file tracks the remaining work, ordered by value. Items are scoped so each
can be picked up independently.

---

## 1. Second plan template (validate the abstraction)

Only `half_marathon_build` exists. The template model (`DaySlot`/`WeekTemplate`/
`PlanTemplate`) and expander are unproven against a second shape.

- Add a contrasting template — e.g. `base_aerobic_build` (ride-primary, no quality
  rotation) or an 8-week race-specific block — to `plan_templates.py`, register in
  `TEMPLATES`.
- Confirm `expand_template` handles a template whose quality day has **no** variant
  pool (pure deterministic) and one with **different** jitter slots.
- Tests: determinism + reproducibility for the new template; `list_plan_templates`
  surfaces it.
- **Why:** flushes out any hardcoded assumptions in the expander/preview before the
  agent relies on templates broadly.

## 2. Phase variation: recovery / taper weeks in templates

`half_marathon_build` is 4 identical build weeks (all `target_tss=400`). Real plans
need recovery weeks (−30–40% TSS) and a taper.

- Extend the template data with reduced-volume weeks (the model already supports
  per-week `target_tss` and different `DaySlot`s; just author them).
- Decide whether `estimated_tss` per archetype should **scale** with the week's
  target or stay hardcoded per slot (currently hardcoded). If scaling: thread a
  factor through `expand_template` → archetype kwargs. This is the first real use
  of `WeekTemplate.target_tss` as more than a label.
- Tests: recovery week sums below build week; taper week structure.

## 3. `target_tss`-driven volume (deferred from original scope)

Today `target_tss` is a label compared against generated TSS in the preview summary;
it does **not** drive durations. The original handoff explicitly deferred a goal/ramp
engine. If/when wanted:

- Add an optional scaler in `plan_expander` that nudges easy/long durations to hit
  the week target within a tolerance, **without** breaking determinism (scale before
  jitter; same seed → same output).
- Keep it opt-in (a template flag) so existing templates stay byte-stable.
- Hard guard: never let scaling push a quality session out of its archetype's intent.

## 4. Author/regenerate path (name ownership)

Name preservation is currently **reconcile-scoped** (existing names kept on update;
generated names only on new dates). If an "author mode" is added (regenerate a plan
the engine owns, overwriting names):

- It must own names itself — do **not** rely on the reconcile name-preservation in
  `_apply_update` / `_event_diffs`. Add an explicit `author` flag or a separate code
  path; today both deliberately exclude `name` from the diff.
- Re-read the comments in `workout_preview.py:_event_diffs` and
  `workout_apply.py:_apply_update` — they flag this boundary.
- Tests: author path overwrites name; reconcile path still preserves it.

## 5. Engine vs `save_plan` — single front door (behavioral)

The coach can now reach **two** plan systems: free-text `save_plan` (blind upsert,
no reconcile) and the deterministic engine (reconcile, sandbox-validated). `AGENTS.md`
and `coach.md` steer the choice, but there's no enforcement.

- Option A: teach the `plan-builder` skill to prefer `preview_plan`/`apply_plan` for
  template-shaped plans and reserve `save_plan` for genuinely bespoke/narrative plans.
- Option B: give `save_plan` reconcile semantics too (factor the reconcile out of
  `workout_preview` so both writers share it). Larger refactor; removes the blind
  `upsert_event` in `plan_tools._insert_plan_and_events`.
- **Decision needed** before broad agent use, to avoid the agent picking the weaker
  path by habit.

## 6. Expose single-week generators as tools (optional)

`preview-sessions`/`apply-sessions` (race-week, post-race, half-marathon-week
generators) remain **CLI-only** — the agent can't reach them. If race-week tapers
should be agent-driven, mirror the `workout_tools.py` pattern for them. Currently the
agent builds taper weeks via free-text; the deterministic race-week generator already
exists and is tested.

---

## Housekeeping / smaller items

- **`hill_activation` latent bug** (`workout_archetypes.py`): the main step's `hr_cap`
  is hardcoded to 155, ignoring the `hr_cap` parameter (only the interval step uses
  it). Confirm intended; fix if not.
- **`estimated_tss` exact compare** in `_event_diffs`: uses raw `!=` (no tolerance).
  Float drift or `None`↔value transitions force updates. Consider a small tolerance
  if real-world re-previews churn.
- **`_is_strength_event` is a text heuristic** (`"strength"` substring in slug/name/
  summary), not payload/sport-based. Could misclassify. Consider checking
  `payload["workout"]["sport"] == "strength"` first, falling back to text.
- **Pre-existing lint** (out of scope, noted for a cleanup pass): `F401` in
  `cli.py:163` (`_sys`), `cli.py:682` (`_detect_dominant_sport`), and
  `tests/test_tools_functional.py:12,13,1816` (`sqlite3`, `contextmanager`,
  `env_tools`). None introduced by the engine work.

## Audit: fragile heuristics / classifiers

We already hit one real bug of this class — `detect_session_sport` matched the
substring `ride` inside `strides`, misclassifying easy runs as rides (now fixed
with whole-word matching + a regression test). Do a focused sweep for the same
failure modes elsewhere. Each item below is "find it, write a test that proves
the current behavior, then harden":

- [ ] **Substring keyword matching anywhere** — grep for `in text`, `in t`,
      `in name.lower()`, `.find(`, `any(k in` patterns used for classification.
      Each is a candidate for the `strides`→`ride` trap. Prefer whole-word regex
      (`\bword\b`) or a structured field. Known instances to check:
      `_is_strength_event` (`workout_preview.py`), `_is_rest_event`,
      `signal_bot._detect_dominant_sport`, plan-parser intensity keywords,
      activity-type detection in `activity_tools` / `metrics`.
- [ ] **`_is_strength_event`** (`workout_preview.py`) — `"strength"` substring in
      slug/name/summary. Should prefer `payload["workout"]["sport"]=="strength"`
      then fall back to text. Misclassifying a strength session as endurance lets
      the engine overwrite it.
- [ ] **Sport classification priority** — `resolve_sport` now does
      Strava `sport_type` → structured payload → text. Audit every *other* place
      that guesses sport from text only and route it through `resolve_sport`
      (e.g. the markdown writer at plan-author time has no Strava data, but any
      post-completion path should use the linked activity).
- [ ] **Intensity parsing** (`parse_session_duration_intensity`) — first-keyword
      match in priority order; verify a session like "easy warmup then threshold"
      classifies as the *main set*, not the warmup. Add cases for compound
      descriptions.
- [ ] **Duration parsing** — `parse_session_duration_intensity` takes the *first*
      `\d+min`. Sessions like "10min WU + 3x8min + 10min CD" or "60-75min" or
      "Dolomites Bike Day" (no minutes) mis-parse. Observed live: a long ride
      estimated at 63 TSS because only a sub-duration was read. Decide whether to
      sum components or read a total.
- [ ] **`normalize_strava_sport` coverage** — the live DB has `Road Bike`,
      `Sport 10001`, `Running`, `VirtualRun`, `EBikeRide`, ski/hike/swim. Confirm
      each maps correctly or returns `None` (so it falls through rather than
      silently defaulting to run). Add a test that iterates the distinct
      `sport_type` values actually present.
- [ ] **General rule** — any classifier that picks a label from free text should:
      (1) prefer an authoritative structured/API field, (2) match whole words not
      substrings, (3) have an explicit, tested default, and (4) fail *towards* the
      conservative estimate (for TSS that's the higher-IF run table).

## Before merge

- [ ] `uv run pytest` green (currently 750 passing).
- [ ] `uvx ruff check` clean on engine + tool files (currently clean; pre-existing
      unrelated F401s remain — see Audit/lint note).
- [ ] Decide commit grouping: (1) deterministic engine Phases 1–4, (2) MCP tools +
      docs, (3) sport-aware TSS model + sport resolution. Suggest three commits.
- [ ] Run `coachctl backfill-event-tss --recompute` on the personal repo to correct
      existing events, then `coachctl bake`. (Writes to personal repo data only.)
- [ ] Personal-repo side: only data (events `estimated_tss`, baked `data.json`)
      changes — no code. Engine + model code is public-repo only.
