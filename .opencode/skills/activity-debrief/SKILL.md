---
name: activity-debrief
description: Deliver structured feedback on new activities from get_new_activities. Covers the full debrief format (what was good, what to improve, plan fit, next session) plus stream analysis rules for HR decoupling, power curve, zone distribution, cadence flags, and nutrition signals. Load for every new-activity review at startup or mid-session.
compatibility: opencode
---

## What I do

Deliver structured, data-driven feedback on each unreviewed activity. Pull streams when available. Interpret the numbers. Give one clear next-session prescription. Then close the loop with `mark_activities_reviewed`.

---

## Step 1 — Route by sport type, then fetch data

For every activity returned by `get_new_activities`, first check `sport_type`, then fetch the appropriate data source.

### Runs and trail runs (sport_type = Run, TrailRun)

Use **COROS only**. Do not call `get_activity_streams` for runs.

1. Find the matching COROS activity:
   ```
   coros_querySportRecords(
     startDate=<activity_date as yyyyMMdd>,
     endDate=<activity_date as yyyyMMdd>,
     sportTypeCodes=[100, 102],   # 100=outdoor run, 102=trail run
     timezone="Europe/Zurich"
   )
   ```
2. Match by date and duration (closest duration to the Strava activity within ±10 min).
3. If a match is found → call `coros_analyzeActivityDetail(labelId, sportType, focus="pace stability")` for the primary analysis.
4. For long runs (>75 min) or races, also call:
   - `coros_queryHrvAssessment(days=3, timezone="Europe/Zurich")` — recovery context around the session
   - `coros_queryRecoveryStatus` — current recovery % to frame the next-session prescription
5. **Fallback:** if no matching COROS record is found, fall back to `get_activity_streams(activity_id)` and note: "COROS record not found — using Strava streams."

### Rides (sport_type = Ride, GravelRide, VirtualRide, MountainBikeRide, EBikeRide)

Use **Strava only**. Do not call any COROS tools for rides.

- **Always pull streams** for: races, intervals, threshold sessions, long rides (>90 min), any session where the athlete reported something unusual
- **Skip streams** for: easy Z2 sessions <60 min with no flags

Pull with: `get_activity_streams(activity_id)`  
Pull laps with: `get_activity_laps(activity_id)` for interval sessions where lap structure matters

### Other / untracked activities (gym, hockey, yoga, etc.)

Skip all stream/COROS calls. Brief debrief only based on Strava metadata.

---

## Step 2 — Stream interpretation rules

### HR drift vs aerobic decoupling

Do not conflate these two metrics.

**Simple HR drift** measures only cardiac strain over time:

`drift_pct = (second_half_avg_hr - first_half_avg_hr) / first_half_avg_hr × 100`

| drift_pct | Interpretation | Flag? |
|---|---|---|
| < 0% (negative) | First half HR higher than second — went out too hard, faded, or terrain made halves incomparable | ⚠️ Mention pacing/terrain context |
| 0–5% | HR stayed stable; good cardiovascular control | ✅ |
| 5–8% | Acceptable, minor cardiovascular drift | Mention if relevant |
| > 8% | HR rose materially; check heat, hydration, fueling, accumulated fatigue, or too-high intensity | 🚨 Flag if session was prescribed easy/aerobic |

**Aerobic decoupling** (`cardiac_decoupling_pct`, Pa:Hr for running or Pw:Hr for cycling) compares output-to-HR between halves. It is the better aerobic-durability metric when the effort is steady and output is reliable.

| decoupling_pct | Interpretation | Flag? |
|---|---|---|
| <5% | Well coupled; athlete handled that output economically | ✅ |
| 5–10% | Some durability/fatigue/heat/fueling signal | Mention and contextualise |
| >10% | Output-to-HR relationship degraded; likely above aerobic threshold, fatigued, heat-stressed, underfueled, or beyond current durability | 🚨 Flag on clean steady sessions |

Context rules:
- Low HR drift does **not** prove the session was easy. A well-paced tempo can have low drift but still be wrong for an easy/Z2 prescription.
- High decoupling on hilly trail runs is noisy: gradient, hiking, descents, footing, GPS error, and running-power models can distort output. Treat it as a rough fatigue/terrain-efficiency signal, not a clean aerobic diagnosis.
- For clean road Z2 runs or steady rides with power, decoupling is high-value. For technical trails, intervals, group rides, and stop-start files, down-weight it.
- If simple HR drift and decoupling disagree, explain why instead of averaging them.

Reference page: general wiki `training_metrics/hr_drift_decoupling`.

### HR zones (zone_distribution)

| Flag | Condition |
|---|---|
| Grey zone drift | Z3 > 20% on a prescribed Z2 session |
| Didn't execute hard session | Z4+Z5 < 10% on a prescribed intervals/threshold/race session |
| Polarization good | Z1+Z2 ≥ 80% on an easy day |
| VO2max work confirmed | Z5 > 15% on a prescribed VO2max session |

### Power curve (peak_power — cycling)

| Peak | What it tells you |
|---|---|
| 5s peak | Neuromuscular ceiling — relevant for sprints, attacks |
| 30s peak | Anaerobic capacity — short climbs, surges |
| 1min peak | Anaerobic / VO2max boundary |
| 5min peak | VO2max proxy — compare to 106–120% FTP |
| 20min peak | Threshold ceiling — compare to FTP; if >FTP, FTP may be underset |

Flag: if 20min peak > FTP × 1.05 on a non-all-out ride, note "FTP may be underestimated — consider a test."

### Running power / NGP (pace-based)

- NGP (grade-adjusted pace) is the primary running intensity signal, not raw pace
- Compare NGP to rFTP: NGP/rFTP = Intensity Factor equivalent
- If IF > 1.05 on a prescribed Z2 run, it was harder than planned — flag

### Nutrition flags (combined signal)

Look for **both** of these simultaneously in km splits:

1. Late-session pace/power fade: last 20% of session pace/power drops >8% vs middle 60%
2. Late-session HR spike or plateau: HR rises or stays high while pace/power drops

Both present → bonk signal. Flag fueling for that session. Check if athlete reported eating.

Single signal only (pace fade without HR spike, or HR spike without pace fade) → fatigue or pacing, not fueling. Different diagnosis.

### Cadence flags

**Cycling:**
| Condition | Flag |
|---|---|
| Avg cadence < 80rpm on flats | Grinding — neuromuscular fatigue risk, especially on long rides |
| Avg cadence < 75rpm overall | Flag for cramp risk on subsequent hard efforts |
| Cadence < 70rpm on >8% gradient | Acceptable — gearing/gradient constrained |

**Running:**
| Condition | Flag |
|---|---|
| Avg cadence < 160 spm (80 per foot) on flat/downhill | Overstriding or fatigue |
| Cadence < 75 spm on steep climb | Flag only if power also low — may indicate form collapse |

### Variability index (cycling)

`VI = NP / avg_power`

| VI | Interpretation |
|---|---|
| 1.00–1.05 | Very steady (TT, flat Z2) |
| 1.05–1.10 | Normal for rolling terrain |
| 1.10–1.20 | Punchy/variable — climbs, group riding |
| > 1.20 | Very variable — surging, not pacing to plan |

---

## Step 3 — Debrief format

Use this exact structure for every activity. Keep each section to 1–3 lines.

---
**[Activity name] — [date] · [sport] · [duration] · [distance or TSS]**

**What was good:** [specific positives grounded in data — pace, power, HR, cadence, zone compliance]

**What to improve:** [specific issues with data evidence — "HR 181 at km 3 = Z5, above threshold; classic overcooking on the climb"]

**Plan fit:** [did this match what was prescribed? Reference CTL ramp, TSB, weekly TSS target if relevant]

**Next session:** [exact prescription — sport, duration, pace/power/HR zone, RPE, key focus cue]

---

### Session-type-specific guidance

**Race debrief:**
- Lead with result vs goal time/pace
- Pacing: was it even? Negative split? Blowup?
- HR: did it match the race card? Any surprises?
- Nutrition: did the gel plan execute?
- Key takeaway for next race card revision

**Long run / long ride:**
- Aerobic decoupling (key metric on steady road/ride files; down-weight on technical trail)
- Simple HR drift as a separate cardiac-stability signal; do not call simple HR drift "decoupling"
- Fueling compliance (flag if >2h and no mention of eating)
- Fatigue signature in final 20% of splits

**Interval session:**
- Did reps hit target power/pace?
- Recovery quality: did HR come down between reps?
- Lap-by-lap consistency or fade

**Z2 easy session:**
- Was it actually Z2? (HR, power)
- Grey zone drift?
- Brief — 2–3 lines max

**Trail run / race:**
- NGP vs rFTP (not raw pace — trail gradient adjustment matters)
- Interpret HR drift and decoupling cautiously; terrain can make halves non-comparable
- Cadence on climbs vs descents
- Descent-then-climb pattern (classic quad depletion trap)

---

## Step 4 — Post-debrief actions

After delivering feedback on **all** new activities in the batch:

1. **`mark_activities_reviewed([id1, id2, ...])`** — pass all IDs in one call
2. **`log_feedback(activity_date, rpe, felt, notes, activity_id)`** — only if athlete provides RPE in conversation
3. **Mark race events completed** — for each debriefed activity that is a race (sport_type contains "Race" or the activity name/date matches a race-day event):
   - Call `get_calendar_window(start=<activity_date>, end=<activity_date>, kinds='race')`
   - If a race event is returned with `status = 'planned'`, call `update_event(slug, status='completed')`
   - If no race event found on that date, skip silently
   - This ensures the event disappears from upcoming-race queries at the data layer — no LLM inference needed at next startup

---

## Step 5 — Weekly untracked check-in

If `check_weekly_untracked` returned `due: true` at startup, ask after the activity debrief:

> "Weekly check-in: any untracked sessions this week (hockey, gym, golf, other)? If yes: sport, duration, intensity."

Log each with `log_untracked_activity`, then call `mark_weekly_checkin_done` — even if nothing to log.

---

## Interpretation shortcuts (quick reference)

| Metric | Green | Amber | Red |
|---|---|---|---|
| Simple HR drift | 0–5% | 5–8% | >8% |
| Aerobic decoupling (Pa:Hr/Pw:Hr) | <5% | 5–10% | >10% on clean steady sessions |
| Z3 time (easy session) | <10% | 10–20% | >20% |
| Z4+Z5 (hard session) | >25% | 15–25% | <15% |
| Cycling cadence (flat) | >85rpm | 80–85rpm | <80rpm |
| Running cadence (flat) | >162spm | 155–162spm | <155spm |
| VI (cycling) | <1.10 | 1.10–1.18 | >1.18 |
| IF (Z2 session) | <0.75 | 0.75–0.80 | >0.80 |
| Nutrition (>2h) | On plan | 1 missed gel | Multiple misses or bonk signal |
