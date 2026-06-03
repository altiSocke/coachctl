# Startup Fallback — Path B Quick Reference

Load this skill only when MCP tools are unavailable and you are operating via bash (Path B).

## Correct import paths

| Need | Import / call |
|---|---|
| DB connection | `from coachctl.db import get_conn` |
| Strava sync | `from coachctl.sync import sync; sync(full=False)` |
| Fitness state | `SELECT date, ctl, atl, tsb FROM fitness ORDER BY date DESC LIMIT 1` |
| Activities columns | `start_date`, `sport_type`, `moving_time`, `average_heartrate`, `average_watts` |
| Events columns | `kind` (not `event_type`), `slug`, `date`, `name`, `summary`, `status` |

## Path resolution

Use `code_root()` and `data_root()` from `src/coachctl/paths.py`.
`AGENT_DATA_ROOT` is the canonical env var for the personal repo path.

## Full startup bash sequence (Path B)

```bash
# Step 1 — git pull both repos
git -C /path/to/coachctl pull && git -C /path/to/coachctl-personal pull

# Step 2 — single startup call (sync + fitness + new activities + events + profile)
uv run coachctl startup
```

After startup, load recent coaching notes:

```bash
tail -n 20 <DATA_ROOT>/profile/training_history.md
```

Then load additional wiki files based on intent only:

```bash
# RACE_PLANNING or PLAN_BUILDING intent:
cat <DATA_ROOT>/profile/goals.md
cat <DATA_ROOT>/profile/profile.md

# PLAN_BUILDING intent (also):
cat <DATA_ROOT>/profile/training_history.md

# NUTRITION intent:
cat <DATA_ROOT>/profile/nutrition.md
```

Then bake: `uv run coachctl bake`
