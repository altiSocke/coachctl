# coachctl — Strava Training Agent

MCP server + OpenCode agent + dashboard for analysing Strava training data and
generating periodized training plans.

> **Architecture & conventions** live in [`AGENTS.md`](AGENTS.md).
> **Operational coach workflows** live in [`.opencode/agents/coach.md`](.opencode/agents/coach.md).
> This README owns setup, install, and deployment only.

## Features

- Sync Strava activities into a local SQLite database
- Compute CTL / ATL / TSB (fitness, fatigue, form) via exponential moving averages
- HR zone distribution and polarisation analysis (tripartite Seiler model)
- Power-based TSS for cycling; pace-based rTSS and grade-adjusted NGP for running
- Aerobic Efficiency Factor (EF) trend tracking across sessions
- Personal best efforts — running (5k/10k/HM/marathon) and cycling power (5s–60min)
- Critical Power (CP) and W' estimation from mean maximal power curve
- ACWR (acute:chronic workload ratio) injury risk monitoring
- CTL/ATL/TSB projection to a target race date with taper modelling
- Tripartite intensity distribution (Seiler polarized model) with gap-to-target analysis
- Generate and save periodized training plans as Markdown
- Race cards — structured per-section race strategy (pacing, nutrition, kit, climbs, warmup, protocols, YoY, readiness gate)
- Three-layer knowledge base (`<DATA_ROOT>/raw/` + `<DATA_ROOT>/wiki/` + `<DATA_ROOT>/profile/`) — all in the private personal repo
- Log untracked activities (hockey, gym, etc.) with TSS estimates
- Pre-session readiness check-in (sleep / energy / soreness) with session gate logic
- FastAPI training plan dashboard, deployable to Vercel from the personal repo

---

## Repo split

`coachctl` is split into two coupled repos:

| Repo | Visibility | Holds |
|---|---|---|
| `coachctl` (this) | public | code, general knowledge, dashboard UI source |
| `coachctl-personal` (per-athlete) | private | secrets, activities DB, personal wiki, baked `data.json`, Vercel deploy surface |

Dependency direction is **strictly one-way**: the private repo depends on the
public one via `pip install`. The public repo never reads, imports, or assumes
anything about the private repo.

`paths.py` resolves the personal data root in this order:

1. `AGENT_DATA_ROOT` env var.
2. Sibling `../coachctl-personal/` next to this checkout (auto-discovered).
3. Legacy fallback: `wiki/personal/<STRAVA_PROFILE>` (deprecation warning).

`STRAVA_PROFILE` is now optional — used as a label only.

---

## Quick start

### 1. Install dependencies

```bash
uv sync --extra dashboard
```

### 2. Scaffold a personal repo

```bash
uv run coachctl new-profile --target ~/workspace/coachctl-personal
```

Creates the personal-repo layout (`profile/`, `data/`, `dist/`, `raw/`,
`deploy/`, `.env`). Pass `--no-auth` to skip the Strava OAuth flow.

### 3. Point the code at your personal repo

```bash
export AGENT_DATA_ROOT=~/workspace/coachctl-personal
```

(Or skip this if you placed it as a sibling of `coachctl/` — auto-discovered.)

### 4. Edit your athlete config

Fill in `$AGENT_DATA_ROOT/profile/athlete.yaml`:
- `ftp` — Functional Threshold Power (watts), cycling
- `rftp` — threshold pace in sec/km (e.g. 300 = 5:00/km)
- `threshold_hr`, `max_hr`, `resting_hr`
- `weight_kg`
- `events` — list of target races with date and priority

### 5. Authenticate with Strava

```bash
uv run coachctl sync --auth
```

Browser opens for the OAuth consent flow. Tokens are written to
`$AGENT_DATA_ROOT/.env`.

### 6. Sync activities

```bash
uv run coachctl sync           # incremental
uv run coachctl sync --full    # full re-sync
```

### 7. Run the MCP server with OpenCode

```bash
opencode
```

`opencode.json` launches `coachctl serve` automatically. The coach agent is
defined by `.opencode/agents/coach.md`.

### 8. Bake + publish dashboard

```bash
uv run coachctl update         # sync → bake → git push (in personal repo)
```

Triggers Vercel redeploy of the personal repo.

---

## First-time Strava API setup

1. Go to https://www.strava.com/settings/api
2. Create an application (any name, e.g. "coachctl")
3. Set "Authorization Callback Domain" to `localhost`
4. Copy the **Client ID** and **Client Secret** into `$AGENT_DATA_ROOT/.env`
5. Run `uv run coachctl sync --auth` — opens a browser and writes
   `STRAVA_REFRESH_TOKEN` automatically

---

## Deployment — Vercel (personal repo)

The dashboard deploys from the **personal repo**, not this one.

1. In the personal repo, ensure `deploy/` contains `web.py`, `vercel.json`,
   `requirements.txt` (scaffolded by `coachctl new-profile`).
2. In Vercel: import the private personal repo. Set **root directory** to
   `deploy/`. No env vars needed — the dashboard reads `deploy/dist/data.json` at
   cold-start.
3. Each `uv run coachctl update` commits & pushes the refreshed `data.json`,
   triggering an auto-redeploy.

If `data.json` is missing or stale, the dashboard returns HTTP 503 with a setup
message rather than crashing the function.

To roll forward UI updates: bump the git ref in `deploy/requirements.txt`:

```
coachctl[dashboard] @ git+https://github.com/altiSocke/coachctl.git@<sha-or-tag>
```

---

## Local development

```bash
# Run the dashboard against your active personal repo:
uv run coachctl web                      # → http://127.0.0.1:8080
uv run coachctl web --reload --port 8000 # auto-reload mode
```

---

## CLI

`coachctl` is a single typer-based binary. Subcommands:

| Command | Purpose |
|---|---|
| `coachctl sync [--auth] [--full]` | Sync Strava activities (or run OAuth flow) |
| `coachctl bake` | Build `deploy/dist/data.json` from the activities DB |
| `coachctl update` | sync → bake → git commit/push (in personal repo) |
| `coachctl new-profile --target <dir>` | Scaffold a new personal repo |
| `coachctl web [--port N] [--reload]` | Serve dashboard locally |
| `coachctl serve` | Run the MCP server (used by opencode) |

---

## MCP tools

Full catalogue lives in [`.opencode/agents/coach.md`](.opencode/agents/coach.md).
Categories:

| Category | Tools |
|---|---|
| Environment | `check_environment` |
| Sync & routes | `sync_activities`, `list_routes`, `get_route_detail` |
| Athlete profile | `get_athlete_profile`, `get_athlete_profile_deep` |
| Fitness | `get_fitness_state`, `get_fitness_trend`, `get_zone_distribution`, `get_weekly_summary`, `get_acwr`, `get_intensity_distribution`, `get_efficiency_factor_trend`, `get_projected_fitness` |
| Performance | `get_best_efforts`, `get_critical_power`, `predict_race_time`, `get_vo2max_estimate` |
| Load planning | `estimate_session_tss_tool`, `estimate_week_tss_tool`, `get_plan_compliance` |
| Activities | `get_recent_activities`, `get_activity_detail`, `get_activity_streams`, `get_activity_laps`, `find_similar_workouts`, `get_new_activities`, `mark_activities_reviewed`, `set_activity_tss_override` |
| Feedback & notes | `log_feedback`, `get_recent_feedback`, `save_coaching_note`, `get_coaching_notes` |
| Readiness | `log_readiness_checkin`, `get_readiness_history` |
| Untracked | `log_untracked_activity`, `get_untracked_activities`, `check_weekly_untracked`, `mark_weekly_checkin_done` |
| Plans | `save_plan`, `get_previous_plans` |
| Personal wiki | `get_athlete_wiki`, `propose_wiki_update`, `apply_wiki_update`, `search_wiki` |
| General wiki | `read_general_wiki`, `propose_general_wiki_update`, `apply_general_wiki_update` |
| Site / dashboard | `bake` |
| Events & calendar | `get_calendar_window`, `get_event_detail`, `date_is_free`, `create_event`, `create_race`, `update_event`, `cancel_event`, `delete_event` |
| Race cards | `propose_race_course`, `apply_race_course`, `propose_race_goal`, `apply_race_goal`, `propose_race_pacing`, `apply_race_pacing`, `propose_race_nutrition`, `apply_race_nutrition`, `propose_race_logistics`, `apply_race_logistics`, `propose_race_kit`, `apply_race_kit`, `propose_race_warmup`, `apply_race_warmup`, `propose_race_climbs`, `apply_race_climbs`, `propose_race_protocols`, `apply_race_protocols`, `propose_race_yoy`, `apply_race_yoy`, `propose_race_readiness_gate`, `apply_race_readiness_gate`, `propose_race_key_principles`, `apply_race_key_principles` |

## Dashboard

The dashboard (`uv run coachctl web`) is a single-page app baked from `data.json`.
Cards visible at a glance:

| Card | What it shows |
|---|---|
| **This Week** | Day-by-day plan sessions + completed activities, TSS per item, click to expand |
| **Fitness** | CTL · ATL · Form (TSB) · ACWR pills, 7-day CTL ramp rate, fatigue alerts |
| **Phase bar** | Current training phase + progress within it, weeks remaining |
| **Race strip** | Upcoming races with days-out countdown, priority badge, and goal time |
| **Recent Runs** | Last 14 runs — pace, distance, elevation, rTSS |
| **Thresholds** | FTP · LTHR · rFTP · VO₂max reference values |
| **Plan Compliance** | Overall % + week-by-week sessions and TSS actual vs planned |
| **Decision Gates** | Upcoming test-race gates with A/B targets and revision rules |
| **Key Metrics** | Metric progression table (start → mid → peak → race day) |
| **CTL · ATL · Form chart** | 16-week fitness trend with projected taper line |
| **Weekly Load chart** | Bar chart TSS by sport (run / ride / other) vs plan target |
| **Running Load chart** | Weekly rTSS (pace-based vs power-based comparison) |
| **Zone Distribution** | 8-week HR zone bar with polarization index and target reference |
| **Goals** | Running and cycling season goals |

Race cards (click any race in the strip) show: course profile, goal, key principles,
pacing table, warmup timeline, nutrition plan, logistics + weather, kit, race-day
protocols (IF/THEN), year-on-year comparison, and readiness gate.

---


## Roadmap

- [ ] Auto-detect activity type (race, interval, easy) and adapt analysis depth
- [ ] Persist stream data for key workouts for retrospective comparison
- [ ] Dashboard: athlete profile card (thresholds, W/kg, VO₂max, weight) with edit link
- [ ] Dashboard: race map panel showing GPX routes for available upcoming races
