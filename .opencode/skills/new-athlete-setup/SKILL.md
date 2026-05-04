---
name: new-athlete-setup
description: First-time athlete onboarding and environment repair. Load when check_environment returns ok=false, or when the athlete reports missing data, auth errors, or a broken setup. Covers all failure modes: missing personal repo, missing .env, unset Strava credentials, missing athlete.yaml, empty activities DB.
compatibility: opencode
---

## What I do

Walk the athlete through setting up or repairing their `coachctl-personal` environment. Handle each failure mode with the minimum number of shell commands. Surface the single most actionable step first.

**Communication rule:** Show the single most actionable next step first. Do not dump the full diagnostic. Show `check_environment` JSON only if the athlete asks for it. Be concise — one failure mode at a time.

---

## Failure mode 1 — No data root resolved

**Symptom:** `check_environment` errors include "Data root unresolved"  
**Cause:** No personal repo exists, or `AGENT_DATA_ROOT` is not exported.

**Steps:**

1. Decide where to put the personal repo (default: `~/workspace/coachctl-personal` — sibling to the code repo, auto-discovered without any env var).

2. Scaffold it:
   ```bash
   uv run coachctl new-profile --target ~/workspace/coachctl-personal
   ```
   This creates: `profile/`, `data/`, `raw/`, `deploy/`, `.env`, `.env.example`, `.gitignore`, `deploy/web.py`, `deploy/vercel.json`, `deploy/requirements.txt`. Pass `--no-auth` to skip OAuth for now.

3. *(Optional but recommended)* If using a non-default path, add to shell rc:
   ```bash
   export AGENT_DATA_ROOT=<path>
   ```
   Skip if using the auto-discovered sibling path.

4. *(Optional)* Set a profile label:
   ```bash
   export STRAVA_PROFILE=<yourname>
   ```
   Informational only — used in metadata and the legacy path fallback.

5. *(Optional)* Initialise as a private git repo:
   ```bash
   cd <path> && git init && git remote add origin git@github.com:<you>/coachctl-personal.git
   ```

6. Restart OpenCode so the MCP server picks up the new env. Then re-run `check_environment` to confirm.

---

## Failure mode 2 — Missing `.env` file

**Symptom:** `check_environment` errors include "Missing secrets file"  
**Cause:** `.env` was not created during scaffolding, or was deleted.

**Steps:**

1. Copy the template:
   ```bash
   cp <data_root>/.env.example <data_root>/.env
   ```

2. Get a Strava API client at https://www.strava.com/settings/api  
   - Set callback domain to `localhost`
   - Copy `Client ID` and `Client Secret`

3. Fill in the `.env`:
   ```
   STRAVA_CLIENT_ID=<your_client_id>
   STRAVA_CLIENT_SECRET=<your_client_secret>
   ```

4. Run OAuth to write the refresh token automatically:
   ```bash
   uv run coachctl sync --auth
   ```
   This opens a browser window for Strava authorization.

5. Re-run `check_environment`.

---

## Failure mode 3 — Strava credentials unset or invalid

**Symptom:** `check_environment` warnings mention `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`, or `STRAVA_REFRESH_TOKEN` unset  
**Cause:** `.env` exists but credentials were not filled in, or the refresh token expired.

**Steps:**

1. Open `<data_root>/.env` and verify `STRAVA_CLIENT_ID` and `STRAVA_CLIENT_SECRET` are set (not placeholder values).

2. Re-run OAuth:
   ```bash
   uv run coachctl sync --auth
   ```
   This overwrites `STRAVA_REFRESH_TOKEN` in `.env` automatically.

3. Re-run `check_environment`.

---

## Failure mode 4 — Missing `athlete.yaml`

**Symptom:** `check_environment` errors include "Missing athlete.yaml" or "athlete.yaml not found"  
**Cause:** Config file was not created or was moved.

**Steps:**

1. Create `<data_root>/profile/athlete.yaml`. Required keys:

   ```yaml
   ftp: 280              # Cycling FTP in watts
   rftp: 290             # Run threshold pace in sec/km (290 = 4:50/km)
   threshold_hr: 178     # Lactate threshold heart rate (bpm)
   max_hr: 190           # Maximum heart rate (bpm)
   resting_hr: 50        # Resting heart rate (bpm)
   weight_kg: 87         # Body weight in kg

   # Optional: target events
   events:
     - name: "Half Marathon"
       date: "2026-09-19"
       priority: "A"
       goal_time: "1:35:00"

   # Optional: narrative goals
   goals:
     running:
       - "Sub 1:35 half marathon"
     cycling:
       - "Improve climbing performance"
   ```

2. Re-run `check_environment`. If it passes, proceed with `sync_activities` to seed the DB.

---

## Failure mode 5 — Activities DB missing or empty

**Symptom:** `check_environment` warning mentions "Activities DB missing" or fitness tools return empty results  
**Cause:** First run, or DB was deleted. This is a warning — wiki and profile still load.

**Steps:**

1. Run the initial sync:
   ```bash
   uv run coachctl sync
   ```
   If auth has not been done yet, run `uv run coachctl sync --auth` first (see Failure mode 2/3).

2. First sync may take 1–2 minutes depending on activity history. Subsequent syncs are incremental.

3. Re-run `check_environment`. The warning should clear once at least one activity is in the DB.

---

## Failure mode 6 — `data.json` missing (dashboard not baked)

**Symptom:** `check_environment` warning mentions "`data.json` missing" or dashboard returns 503  
**Cause:** `bake` has not been run yet after setup.

**Steps:**

This resolves automatically — `bake` is always called at startup step 7. If the warning persists after a full startup cycle, call `bake` manually and check for errors in the output.

---

## Failure mode 7 — Legacy layout warning

**Symptom:** Warning mentions "legacy layout" or `wiki/personal/<profile>` path  
**Cause:** Personal data is still in the old single-repo layout inside the public code repo.

**Steps:**

This is not blocking — the agent continues normally. To migrate, refer the athlete to `README.md` §"Migrating from the legacy single-repo layout". Do not attempt the migration yourself during a coaching session.

---

## After setup is complete

Once `check_environment` returns `ok: true`, resume the normal startup sequence from step 1 (`sync_activities`). Do not skip any startup steps even if the environment was just freshly configured — the sync and wiki load are always needed.
