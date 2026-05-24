# Development Plan

Goal: make `coachctl` a simple, flexible, powerful training command center that is slim, fast, and easy to extend.

This plan optimizes for a small core, explicit boundaries, cheap iteration, and durable data. It should guide future work without turning the project into a framework.

## Product Principles

- **One clear mental model:** activities, events, plans, wiki notes, and dashboard data all flow from the same local SQLite-backed personal repo.
- **Small public core:** the public repo contains code and UI only; all athlete data, generated artifacts, secrets, and private knowledge stay in `coachctl-personal`.
- **Local-first:** every important action should work locally without a hosted service dependency beyond Strava sync and optional deployment.
- **Agent-friendly APIs:** MCP tools should expose high-level coaching operations, not raw implementation details.
- **Fast by default:** reads should use cached SQLite data; expensive Strava stream fetches should be explicit and cached.
- **Extensible by seams, not abstractions:** add narrow modules and tool groups only when a feature needs them. Avoid generic plugin systems until a real external extension use case exists.
- **Human-readable persistence:** plans and wiki content remain Markdown/YAML where useful; structured calendar truth remains in SQLite.
- **Safe writes:** mutating personal knowledge uses propose/apply flows unless the operation is an append-only coaching note or explicit logged activity.

## Current Architecture Assessment

Strong foundations already in place:

- `paths.py` cleanly separates public code from private data.
- `events` is the right single source of truth for scheduled items.
- MCP tools are grouped by domain and registered through one simple `register_all` seam.
- Dashboard deployment soft-fails when `data.json` is missing, which keeps Vercel robust.
- SQLite is the correct storage layer for local-first querying, portability, and easy backups.
- Tests cover core metrics, events, paths, dashboard, wiki, plan parsing, and tool smoke checks.

Main risks to control:

- Feature growth can make MCP tools broad and repetitive.
- Dashboard bake logic can become a large catch-all if data assembly is not kept modular.
- Legacy paths and back-compat should not keep expanding without a concrete migration need.
- Generated artifacts and personal data must never leak into the public repo.

## Architecture Direction

Keep the system as four slim layers:

1. **Storage layer:** SQLite schema, migrations, path resolution, and file-backed wiki helpers.
2. **Domain layer:** metrics, events, plans, sync, wiki, dashboard data assembly.
3. **Interface layer:** Typer CLI, MCP tools, FastAPI dashboard server.
4. **Presentation layer:** single-page dashboard that reads baked `data.json`.

Avoid adding cross-cutting frameworks. If repeated patterns appear, extract the smallest shared helper that removes duplication without hiding behavior.

## Near-Term Priorities

### 1. Tighten CLI Ergonomics

Make `coachctl` feel like one coherent tool.

- Keep the existing Typer command group as the only public CLI entrypoint.
- Prefer commands that map to user jobs: `sync`, `bake`, `update`, `web`, `serve`, `new-profile`, `migrate`, `startup`.
- Add new commands only when they are useful outside the agent flow.
- Ensure each command prints concise success/failure output and exits non-zero on real failure.
- Replace any stale setup text that references old binaries with `uv run coachctl ...` commands.

Best next checks:

- Verify dashboard setup HTML uses `uv run coachctl bake`, not legacy `uv run bake`.
- Confirm README, dashboard error pages, and scaffold templates use the same command names.

### 2. Keep MCP Tools High-Level

MCP tools should remain stable, coach-oriented operations.

- Keep one module per domain: activity, athlete, event, feedback, fitness, plan, readiness, sync, untracked, wiki, site.
- Avoid exposing low-level SQL or file operations as tools.
- Use `check_environment` before workflows that depend on private data.
- For writes, prefer explicit tools with narrow parameters over generic mutation tools.
- Return JSON-shaped data with stable keys; avoid human-formatted strings unless the tool is specifically for display.

Best next checks:

- Identify tools that return mixed prose and structured data, then normalize where practical.
- Keep `register_all` explicit; do not replace it with auto-discovery unless module count becomes painful.

### 3. Simplify Dashboard Data Assembly

The dashboard should stay fast because it reads one static `data.json`.

- Keep all expensive computation in `bake`, not request handlers.
- Keep `/api/data` as a static JSON response from memory.
- Split `site.py` only when a section becomes independently testable and hard to reason about.
- Prefer small pure functions for each dashboard card payload.
- Preserve soft-fail behavior in `create_app` for missing or invalid data.

Best next checks:

- Audit `site.py` for repeated SQL/date logic that can be reduced without adding abstraction.
- Add tests around any dashboard payload changes before visual changes.

### 4. Make Events the Calendar Contract

All dated training, race, appointment, and untracked-session logic should go through `events`.

- Keep `get_calendar()` as the read contract for dashboard and tools.
- Keep race cards as structured `payload_json` on race events.
- Avoid adding date-anchored schedules to narrative wiki files as authoritative state.
- Keep migration idempotent and safe to rerun.
- Treat generated activity projections as read-only views, not editable events.

Best next checks:

- Ensure future plan save/edit flows always write training rows to `events`.
- Add regression tests whenever conflict resolution changes.

### 5. Preserve Fast Metrics

Metrics should be computed once, cached, and queried cheaply.

- Keep TSS and derived load values stored at sync/bake time where possible.
- Cache Strava streams in `activity_streams`; do not fetch streams during broad summary calls.
- Use manual TSS overrides through `activity_overrides`, not edits to raw activity rows.
- Keep sport-category calculations explicit and easy to audit.
- Prefer SQLite indexes for repeated query paths before adding in-memory caches.

Best next checks:

- Profile slow dashboard bake sections before refactoring.
- Add indexes only for proven repeated queries.

### 6. Keep Knowledge Layers Strict

The three-layer model is a major strength; keep it boring and strict.

- `raw/` is human-write-only and immutable.
- `wiki/` is athlete-agnostic synthesized knowledge.
- `profile/` is athlete-specific knowledge and plans.
- Use propose/apply workflows for wiki rewrites.
- Use append-only coaching notes for observations and decisions.

Best next checks:

- Review any new tool or command that writes files and verify it targets the correct layer.
- Add tests for safe path handling when adding wiki features.

## Medium-Term Improvements

### Better Startup Flow

Create one consistent startup path for humans and agents.

- Keep `coachctl startup` as the no-MCP fallback.
- Mirror the same sequence in MCP startup: environment check, optional sync, fitness snapshot, new activities, calendar window, recent coaching notes.
- Return concise structured summaries that agents can act on directly.

### Plan Editing Instead of Plan Regeneration

A flexible tool needs small changes to existing plans.

- Add focused event-level edits: move session, resize duration/TSS, cancel, replace workout.
- Keep generated plan Markdown as an archive, not the editable source of truth.
- Use `events` rows for active schedule updates.

### Dashboard as Decision Surface

The dashboard should answer "what should I do next?" quickly.

- Prioritize current week, fatigue/form, compliance, next race, and next decision gate.
- Avoid adding charts that do not change a training decision.
- Keep mobile layout first-class.

### Narrow Extension Points

Add extension seams only where they have real value.

- Sport classifiers: centralize run/ride/other mapping if more sports become important.
- Metric calculators: keep functions pure and independently testable.
- Dashboard cards: add card data builders before adding UI complexity.
- Race-card sections: keep section-specific propose/apply tools rather than a generic blob editor.

## Engineering Practices

- Make the smallest correct change.
- Write tests for behavior, not implementation details.
- Keep public interfaces stable unless simplifying them clearly improves the product.
- Do not add backward compatibility unless there is persisted data, shipped behavior, or an explicit user requirement.
- Prefer explicit SQL over hidden ORM behavior.
- Keep dependencies minimal; add one only when it removes substantial code or risk.
- Use type hints for public functions and dataclasses where they clarify contracts.
- Keep generated data deterministic so git diffs remain useful.
- Never commit secrets or generated personal data to the public repo.

## Performance Rules

- Database reads should be bounded by date windows or indexed keys.
- Broad dashboard and weekly summaries must not fetch Strava streams.
- Stream analysis must be opt-in per activity and cached.
- `bake` can do heavier work, but should still complete quickly enough for frequent local iteration.
- Request handlers should serve cached in-memory data, not compute metrics.

## Testing Strategy

- Keep unit tests around pure metrics and parsers.
- Keep integration tests around SQLite-backed flows: events, plans, migrations, wiki path safety.
- Keep smoke tests for MCP tool registration and CLI-facing workflows.
- Add regression tests for every fixed bug before or with the fix.
- Run targeted tests during iteration, then full tests before release-level changes.

Useful commands:

```bash
uv run pytest tests/test_events.py tests/test_site.py
uv run pytest
```

## Definition of Done

A change is done when:

- The behavior is available through the appropriate interface: CLI, MCP, dashboard, or wiki tool.
- The data boundary is correct: public code versus private data, general wiki versus personal profile.
- The implementation is smaller than the problem, not larger.
- Existing tests pass and new behavior has focused coverage.
- Dashboard-facing changes still work with missing `data.json` and on mobile layout.
- The user workflow is documented only where documentation prevents confusion.

## Recommended Next Iteration

Start with small cleanup that improves polish without changing the architecture:

1. Fix stale command references in dashboard setup/help text.
2. Audit `site.py` for one or two obvious extraction points with test coverage.
3. Normalize any MCP tool outputs that mix prose and JSON.
4. Add one or two plan-editing tools that mutate `events` directly instead of regenerating plans.
5. Keep dashboard work focused on decision quality, not more charts.
