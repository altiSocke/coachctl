description: Deliver structured feedback on new activities from get_new_activities. Covers the full debrief format (what was good, what to improve, plan fit, next session) plus stream analysis rules for HR decoupling, power curve, zone distribution, cadence flags, and nutrition signals. Load for every new-activity review at startup or mid-session.
## What I do

Deliver structured, data-driven feedback on each unreviewed activity. Pull streams when available. Interpret the numbers. Give one clear next-session prescription. Then close the loop with `mark_activities_reviewed`.

---

## Step 1 — For each activity in `get_new_activities`

For every activity returned, decide whether to pull streams:

- **Always pull streams** for: races, intervals, threshold sessions, long runs (>75min), long rides (>90min), any session where the athlete reported something unusual
- **Skip streams** for: easy Z2 sessions <60min with no flags, rest days, untracked activities (Badminton, gym, golf)

Pull with: `get_activity_streams(activity_id)`  
Pull laps with: `get_activity_laps(activity_id)` for interval sessions where lap structure matters

---

## Step 2 — Stream interpretation rules

### HR decoupling (cardiac drift)

`drift_pct = (second_half_avg_hr - first_half_avg_hr) / first_half_avg_hr × 100`

| drift_pct | Interpretation | Flag? |
|---|---|---|
| < 0% (negative) | First half HR higher than second — went out too hard, faded | ⚠️ Flag: pacing error |
| 0–5% | Good aerobic conditioning, well-paced | ✅ |
| 5–8% | Acceptable, minor cardiovascular drift | Mention if relevant |
| > 8% | Cardiac decoupling — effort exceeded aerobic capacity, or underfueled | 🚨 Flag: overcooked or bonk |

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
- Aerobic decoupling (key metric)
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
- Cadence on climbs vs descents
- Descent-then-climb pattern (classic quad depletion trap)

---

## Step 4 — Post-debrief actions

After delivering feedback on **all** new activities in the batch:

1. **`mark_activities_reviewed([id1, id2, ...])`** — pass all IDs in one call
2. **`log_feedback(activity_date, rpe, felt, notes, activity_id)`** — only if athlete provides RPE in conversation

---

## Step 5 — Weekly untracked check-in

If `check_weekly_untracked` returned `due: true` at startup, ask after the activity debrief:

> "Weekly check-in: any untracked sessions this week (hockey, gym, golf, other)? If yes: sport, duration, intensity."

Log each with `log_untracked_activity`, then call `mark_weekly_checkin_done` — even if nothing to log.

---

## Interpretation shortcuts (quick reference)

| Metric | Green | Amber | Red |
|---|---|---|---|
| HR decoupling | <5% | 5–8% | >8% or negative |
| Z3 time (easy session) | <10% | 10–20% | >20% |
| Z4+Z5 (hard session) | >25% | 15–25% | <15% |
| Cycling cadence (flat) | >85rpm | 80–85rpm | <80rpm |
| Running cadence (flat) | >162spm | 155–162spm | <155spm |
| VI (cycling) | <1.10 | 1.10–1.18 | >1.18 |
| IF (Z2 session) | <0.75 | 0.75–0.80 | >0.80 |
| Nutrition (>2h) | On plan | 1 missed gel | Multiple misses or bonk signal |