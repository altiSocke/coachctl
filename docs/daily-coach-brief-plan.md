# Daily Coach Brief Plan

## Goal

Create a daily unattended `coachctl` workflow that runs on the UGREEN NAS, pulls
latest Strava data, refreshes the Vercel dashboard, generates useful coaching
feedback on the previous session and the next planned session, and sends a
Telegram notification — without requiring OpenCode to be running.

The brief should feel like Strava Athlete Intelligence but more valuable because
it knows the active training plan, live CTL/ATL/TSB, the race calendar, personal
thresholds, and the full coachctl coaching history.

---

## Non-Goals for V1

- Do not require OpenCode or an interactive agent session.
- Do not expose a public MCP server or web API.
- Do not auto-modify the training plan.
- Do not allow inbound Telegram messages to mutate data.
- Do not depend on an LLM for the first version.

V1 generates deterministic, safe coaching intelligence from existing SQLite data.
LLM rewriting of the prose can be added later as an optional `--llm` flag.

---

## Target User Flow

Every morning at 06:30 the UGREEN NAS runs the container job:

1. `coachctl` syncs the latest Strava activities into `activities.db`.
2. Fitness metrics (CTL/ATL/TSB, ACWR) are recomputed.
3. A daily coach brief is generated from deterministic rules.
4. Dashboard data is baked into `deploy/dist/data.json`.
5. The personal repo is committed and pushed.
6. Vercel redeploys the refreshed dashboard automatically.
7. Telegram sends a concise coaching note to the athlete.

Optional second run at 21:30 to catch evening workouts.

**Example Telegram message:**

```text
🏃 Daily Coach Brief · Wed 4 Jun

Status: ⚠️ Watch fatigue

Yesterday:
45 min Z2 run · 8.4 km · TSS 52 · HR drift 3.8% — good aerobic control.

Fitness:
CTL 61 · ATL 74 · TSB -13 · Carrying load.

Next planned (Thu):
Threshold intervals · 55 min · est. TSS 75

Cue:
Do the intervals only if sleep, energy, and legs feel normal.
Otherwise swap to 45 min Z2 easy.
```

---

## Architecture

```text
UGREEN NAS
  Docker container (coachctl-daily)
    └── uv run coachctl daily --push --telegram
          ├── Strava sync  →  activities.db
          ├── build_daily_brief()  →  flags, cues, text
          ├── bake()  →  deploy/dist/data.json  (includes daily_brief)
          ├── git commit + push  →  coachctl-personal
          │     └── Vercel auto-redeploy  →  mobile dashboard
          └── send_telegram_message()  →  Telegram Bot API
```

---

## Implementation Scope

### 1. Daily Brief Module

**New file:** `src/coachctl/daily.py`

Responsibilities:

- Load current CTL/ATL/TSB from the `fitness` table.
- Find the latest activity from `activities`.
- Find unreviewed activities (reviewed_at IS NULL).
- Find the next planned training event from `events` (kind = 'training', date > today).
- Compare the next session's estimated TSS against current fatigue.
- Apply deterministic rules to generate a `status` and `flags`.
- Produce a short Telegram-ready plain-text message.
- Return a JSON-serializable `dict` for dashboard inclusion.

**Public interface:**

```python
def build_daily_brief() -> dict:
    """Return structured daily brief dict; safe with empty DB."""

def format_telegram_message(brief: dict) -> str:
    """Return concise plain-text coaching note for Telegram."""
```

**Output JSON shape:**

```json
{
  "generated_at": "2026-06-03T06:30:00+02:00",
  "status": "watch_fatigue",
  "headline": "Good aerobic work, but fatigue is elevated.",
  "latest_activity": {
    "id": 11223344,
    "name": "Morning Run",
    "sport_type": "Run",
    "date": "2026-06-02",
    "duration": "0h45m",
    "distance_km": 8.4,
    "tss": 52,
    "intensity_factor": 0.74,
    "average_heartrate": 143
  },
  "fitness": {
    "ctl": 61.0,
    "atl": 74.0,
    "tsb": -13.0
  },
  "next_session": {
    "slug": "2026-06-04-threshold-run",
    "date": "2026-06-04",
    "name": "Threshold intervals",
    "duration_min": 55,
    "estimated_tss": 75
  },
  "flags": [
    "TSB is moderately negative — fatigue is elevated.",
    "Next planned session is hard — readiness check required."
  ],
  "cue": "Do the intervals only if sleep, energy, and legs feel normal. Otherwise swap to 45 min Z2 easy."
}
```

---

### 2. Deterministic Rules

Status values (in order of precedence):

| Status | Meaning |
|---|---|
| `stale_data` | No activity in last 5 days and no new sync |
| `no_plan` | No active plan or no upcoming events |
| `recovery_needed` | TSB ≤ -20 |
| `watch_fatigue` | TSB ≤ -10 |
| `green` | TSB > -10 |

Flag rules:

| Signal | Flag |
|---|---|
| TSB ≤ -20 | "TSB is deeply negative — recovery priority." |
| TSB -10 to -20 | "TSB is moderately negative — fatigue is elevated." |
| ATL ≥ CTL + 15 | "Acute load spike relative to fitness." |
| Last activity IF ≥ 0.90 | "Last session was hard — protect recovery." |
| Last activity TSS ≥ 100 | "Big session yesterday." |
| Next session est. TSS ≥ 70 and TSB < -10 | "Next planned session is hard — readiness check required." |
| Next session est. TSS < 50 | "Light session ahead — good recovery opportunity." |

Cue logic (derived from status + flags):

| Condition | Cue |
|---|---|
| `recovery_needed` | "Rest or very easy movement only. Do not execute planned intensity." |
| `watch_fatigue` + hard next session | "Do the session only if all readiness scores are 4 or 5. Otherwise swap to Z2." |
| `watch_fatigue` + easy next session | "Execute the easy session as planned. No additional load." |
| `green` + hard next session | "Good form. Execute the session as planned and hit the targets." |
| `green` + easy next session | "Good form. Easy session or optional extension if legs feel good." |
| `stale_data` | "No recent activity found. Check Strava sync and NAS logs." |
| `no_plan` | "No active plan. Review plan status in the dashboard." |

V1 does not fetch Strava streams during the cron job. If stream data is already
cached in `activity_streams`, a later version can add HR drift, decoupling, or
power curve detail to the brief.

---

### 3. CLI Command

**Update:** `src/coachctl/cli.py`

Add the `daily` subcommand:

```text
coachctl daily [OPTIONS]

Options:
  --no-sync     Skip Strava sync; use cached data only.
  --push        Commit and push personal repo after bake.
  --telegram    Send Telegram notification.
  --dry-run     Print brief; do not bake, push, or notify.
  --json        Print raw JSON to stdout instead of text.
  --help
```

Execution order:

1. Load `<DATA_ROOT>/.env`.
2. Ensure DB is initialized.
3. Sync (unless `--no-sync`).
4. Call `build_daily_brief()`.
5. Bake dashboard with brief included.
6. Send Telegram if `--telegram`.
7. Commit/push if `--push`.

Exit codes:

- `0` — success.
- `1` — fatal failure (sync auth broken, bake error).
- `2` — partial failure (e.g. Telegram failed but bake/push succeeded) — log warning, exit 0 to avoid NAS alerting.

Example cron invocation:

```bash
uv run coachctl daily --push --telegram
```

---

### 4. Dashboard Integration

**Update:** `src/coachctl/site.py`

Add `daily_brief` key to `get_dashboard_data()`:

```python
from .daily import build_daily_brief

def get_dashboard_data() -> dict:
    ...
    try:
        brief = build_daily_brief()
    except Exception:
        brief = None
    return {
        ...
        "daily_brief": brief,
    }
```

`build_daily_brief()` must never raise — it returns a safe minimal dict on any
error so bake never fails due to the brief generator.

---

### 5. Dashboard UI

**Update:** `src/coachctl/dashboard/app.html`

Add a "Today's Coach Brief" card at the top, above the fitness chart.

Card structure:

- Status badge (green / amber / red).
- Headline.
- Latest activity summary — sport, duration, distance, TSS.
- Fitness row — CTL, ATL, TSB.
- Next planned session — date, name, estimated TSS.
- Flags list (collapsed by default on mobile).
- Cue (highlighted, readable font).

Mobile priority:

- Brief card is the first visible element on phone.
- Charts scroll below the fold.
- Status color is visible at a glance.

---

### 6. Telegram Notification

**New file:** `src/coachctl/notifications.py`

Required secrets in `<DATA_ROOT>/.env`:

```dotenv
TELEGRAM_BOT_TOKEN=7xxxxxxxxxx:AAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TELEGRAM_CHAT_ID=123456789
```

Implementation:

```python
import httpx, os

def send_telegram_message(text: str) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = httpx.post(url, json={"chat_id": chat_id, "text": text}, timeout=15)
    resp.raise_for_status()
```

Bot setup (one-time, takes 2 minutes):

1. Open Telegram and search for `@BotFather`.
2. Send `/newbot`, follow the prompts, copy the token.
3. Open `https://api.telegram.org/bot<TOKEN>/getUpdates` — send any message to
   the bot first, then read `result[0].message.chat.id`.
4. Add both to `<DATA_ROOT>/.env`.

Security rules for V1:

- Push-only. The bot sends messages; it does not listen.
- No inbound webhook server.
- No public port opened.
- No mutation of any data via Telegram.
- `--telegram` is opt-in; job works without it.

Failure handling:

- Telegram failure does not fail the job.
- Log a warning to stderr.
- Exit 0 so the NAS scheduler does not alarm.
- Include a timeout on the HTTP call.

---

### 7. Personal Repo Push

Reuse `update.py` logic. For `daily --push`, stage:

```text
deploy/dist/data.json
data/activities.db
```

Commit message:

```text
daily brief YYYY-MM-DD
```

If no changes:

```text
No changes — nothing to commit.
```

---

### 8. UGREEN NAS Deployment — Docker

The cron job runs as a Docker container on the UGREEN NAS. The container
includes all Python dependencies and runs the `coachctl daily` command.
No NAS-level Python or `uv` installation is required.

#### 8.1 Directory Layout on NAS

```text
/volume1/docker/coachctl/
├── docker-compose.yml
├── coachctl/              ← git clone of public coachctl repo
└── coachctl-personal/    ← git clone of private personal repo
```

#### 8.2 Dockerfile

**New file:** `Dockerfile`

```dockerfile
FROM python:3.12-slim

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    ca-certificates \
  && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install coachctl dependencies
COPY pyproject.toml .
RUN uv pip install --system -e ".[dashboard]"

# Copy source
COPY src/ src/

# Git identity for commits inside container
RUN git config --global user.email "coachctl@nas" && \
    git config --global user.name "coachctl"

CMD ["uv", "run", "coachctl", "daily", "--push", "--telegram"]
```

#### 8.3 Docker Compose

**New file:** `docker-compose.nas.yml`

```yaml
services:
  coachctl-daily:
    build: .
    image: coachctl-daily:latest
    container_name: coachctl-daily

    environment:
      # Point coachctl at the personal repo inside the container
      - AGENT_DATA_ROOT=/data/coachctl-personal

    volumes:
      # Personal repo (contains .env, activities.db, wiki, plans, deploy/)
      - /volume1/docker/coachctl/coachctl-personal:/data/coachctl-personal

      # Git credentials for pushing personal repo
      - /root/.gitconfig:/root/.gitconfig:ro
      - /root/.ssh:/root/.ssh:ro

    # Container exits after running the job; restart is handled by cron
    restart: "no"

    # Timezone must match the athlete's local time for correct date labels
    environment:
      - TZ=Europe/Zurich
      - AGENT_DATA_ROOT=/data/coachctl-personal
```

> The public `coachctl` repo is baked into the image at build time.
> The personal repo is mounted as a volume so it persists across runs.

#### 8.4 NAS Cron Configuration

On UGREEN NAS, add a scheduled task in the management UI, or use the
NAS shell crontab.

Shell crontab entry:

```cron
30 6 * * * docker compose -f /volume1/docker/coachctl/docker-compose.nas.yml run --rm coachctl-daily >> /volume1/docker/coachctl/daily.log 2>&1
```

For an evening run to catch late workouts:

```cron
30 21 * * * docker compose -f /volume1/docker/coachctl/docker-compose.nas.yml run --rm coachctl-daily >> /volume1/docker/coachctl/daily.log 2>&1
```

> Use `--rm` so each run starts a fresh container and containers do not
> accumulate. The personal-repo state (DB, baked JSON) persists via the volume.

#### 8.5 First-Run Setup on NAS

```bash
# 1. SSH into the NAS
ssh admin@<nas-ip>

# 2. Clone repos
mkdir -p /volume1/docker/coachctl
cd /volume1/docker/coachctl
git clone https://github.com/<you>/coachctl.git
git clone git@github.com:<you>/coachctl-personal.git

# 3. Configure secrets in personal repo
nano /volume1/docker/coachctl/coachctl-personal/.env
# Add STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, STRAVA_REFRESH_TOKEN,
#     TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

# 4. Build the image
cd /volume1/docker/coachctl/coachctl
docker compose -f docker-compose.nas.yml build

# 5. Test run
docker compose -f docker-compose.nas.yml run --rm coachctl-daily \
  coachctl daily --no-sync --dry-run

# 6. Full test run with sync
docker compose -f docker-compose.nas.yml run --rm coachctl-daily \
  coachctl daily --push --telegram
```

#### 8.6 Updating the Code

When a new version of `coachctl` is released:

```bash
cd /volume1/docker/coachctl/coachctl
git pull
docker compose -f docker-compose.nas.yml build --no-cache
```

#### 8.7 Log Rotation

The NAS cron appends to `daily.log`. Add a simple weekly rotation:

```bash
# weekly-log-rotate.sh
LOG=/volume1/docker/coachctl/daily.log
[ -f "$LOG" ] && mv "$LOG" "${LOG}.$(date +%Y%m%d)" && gzip "${LOG}.$(date +%Y%m%d)"
```

```cron
0 3 * * 1 /volume1/docker/coachctl/weekly-log-rotate.sh
```

---

### 9. Security

| Surface | Rule |
|---|---|
| `.env` file | Stored only in personal repo on NAS volume; never in image |
| Telegram token | Push-only; no inbound webhook; no public port |
| Git credentials | SSH key mounted read-only; scope limited to personal repo |
| Strava token | Refresh token stored in `.env`; never logged |
| Dashboard | Served by Vercel; read-only static JSON; no write API |
| MCP server | Not exposed in cron workflow; only available when OpenCode is running locally |
| Container user | Run as non-root if NAS Docker version supports `user:` directive |
| Logs | Code must not log `.env` values, tokens, or credentials at any level |

---

### 10. Tests

**New file:** `tests/test_daily.py`

Cases:

- Empty database returns a safe `stale_data` brief without error.
- Latest activity is correctly formatted.
- `TSB <= -20` produces `recovery_needed` status.
- `TSB -13` produces `watch_fatigue` status.
- Hard next session and negative TSB produces readiness gate cue.
- No active plan produces `no_plan` status.
- Brief output is JSON serializable.
- `format_telegram_message()` produces a non-empty string.
- `format_telegram_message()` output is under 4096 characters (Telegram limit).

**New file:** `tests/test_notifications.py`

Cases:

- Missing `TELEGRAM_BOT_TOKEN` raises a clear `KeyError` or `ConfigError`.
- Successful send calls the correct Telegram API endpoint.
- HTTP error logs a warning but does not raise (for cron resilience).

**Update:** `tests/test_site.py`

Add:

```python
assert "daily_brief" in result
```

---

### 11. Future Enhancements (V2+)

These are out of scope for V1 but noted for planning:

- Optional `--llm` flag: LLM rewrites the deterministic cue into natural coaching language.
- Include cached stream data in brief (HR drift, decoupling, power peak).
- Telegram inline buttons: "Log RPE", "I skipped it".
- `/approve` flow for Telegram-initiated plan adjustments.
- Archive daily briefs in personal repo for trend analysis.
- Race-week special brief with countdown, pacing reminder, and logistics checklist.
- Weather cue integrated before planned outdoor sessions.
- Evening run option with "well done" vs "rest tomorrow" judgment.

---

## V1 Delivery Checklist

- [ ] `src/coachctl/daily.py` — `build_daily_brief`, `format_telegram_message`
- [ ] `src/coachctl/notifications.py` — `send_telegram_message`
- [ ] `src/coachctl/cli.py` — `daily` command with `--no-sync`, `--push`, `--telegram`, `--dry-run`, `--json`
- [ ] `src/coachctl/site.py` — add `daily_brief` to `get_dashboard_data()`
- [ ] `src/coachctl/dashboard/app.html` — "Today's Coach Brief" card
- [ ] `Dockerfile` — self-contained image with `uv` and `coachctl`
- [ ] `docker-compose.nas.yml` — volume mounts, timezone, no restart policy
- [ ] `tests/test_daily.py`
- [ ] `tests/test_notifications.py`
- [ ] `tests/test_site.py` updated
- [ ] `docs/daily-coach-brief-plan.md` — this document
