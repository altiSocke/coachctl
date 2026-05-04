---
name: plan-builder
description: Build or revise a periodized endurance training plan. Load when the athlete asks to create a new plan, revise an existing one, or adjust the phase structure. Encodes the full generic periodization schema (phase lengths, TSS targets, workout type mix, session archetypes) parameterized by event type and plan duration, plus the complete save→bake→commit sequence.
compatibility: opencode
---

## What I do

Build a fully periodized, sport-specific training plan for any endurance event, calibrated to the athlete's current fitness and target event. Output a compact Markdown table plan, save it, and keep the dashboard current.

---

## Step 1 — Gather inputs

Run these tools before drafting anything:

```
get_athlete_profile_deep   # training age, sport mix, peak CTL, best efforts, seasonal patterns
get_fitness_state          # current CTL / ATL / TSB
get_athlete_profile        # FTP, rFTP, HR zones, weight, target events
get_previous_plans         # avoid repeating a structure that didn't work
get_recent_feedback        # RPE trends — high RPE → reduce load prescription
```

From this, determine:
- **Current CTL** (fitness baseline)
- **Peak CTL** (historical ceiling — don't plan above it in first 4 weeks)
- **Weeks to A event** (plan duration)
- **Sport mix** (run-dominant, ride-dominant, or dual-sport)
- **Limiters** (economy, threshold, VO2max, volume, strength)

Ask the athlete to confirm event date, priority (A/B/C), and any hard constraints (travel weeks, B races, blocked days) before drafting.

---

## Step 2 — Select phase schema

Choose the schema that matches weeks-to-event:

### 8-week (short block / race-specific)
| Phase | Weeks | Focus |
|---|---|---|
| Base | 1–3 | Aerobic foundation, high Z2, low intensity |
| Build | 4–5 | Threshold + race-pace introduction |
| Peak | 6–7 | Race-specific intensity, specificity max |
| Taper | 8 | Volume drop 50%, intensity preserved |

### 12-week
| Phase | Weeks | Focus |
|---|---|---|
| Base | 1–4 | Aerobic volume, polarized 80/20 |
| Build | 5–8 | Threshold work enters, 75/25 |
| Peak | 9–10 | Race-pace, specificity, 65/35 |
| Taper | 11–12 | Volume −50%, sharpening |

### 16-week
| Phase | Weeks | Focus |
|---|---|---|
| Base | 1–5 | Aerobic foundation, economy, strides |
| Build 1 | 6–10 | Threshold + sweet spot, tempo runs |
| Peak | 11–13 | Race-pace intervals, specificity |
| Taper | 14–16 | Progressive unload, race-day sharpening |

### 20-week
| Phase | Weeks | Focus |
|---|---|---|
| Base | 1–6 | High Z2 volume, strides, aerobic base cycling |
| Build 1 | 7–10 | Threshold introduction, Z3-Z4 intervals |
| Build 2 | 11–14 | Race-pace work, back-to-back long sessions |
| Peak | 15–18 | Specificity max, tune-up races, CTL peak |
| Taper | 19–20 | Volume −50%, intensity preserved, race sharpening |

**Recovery weeks:** Insert a recovery week (TSS −30–40%) every 3–4 build weeks. Never skip. Mark in the plan as "Recovery".

---

## Step 3 — Set TSS targets

### Weekly TSS by phase (as % of target peak weekly TSS)

Target peak TSS = `peak_CTL × 1.5` (sustainable upper bound).  
If current CTL is more than 15% below historical peak, scale down: start at `current_CTL × 1.3`.

| Phase | Weekly TSS | Intensity mix (Z1+Z2 / Z4+Z5) | Notes |
|---|---|---|---|
| Base | 60–70% of peak | 85 / 15 | Polarized. Long slow distance. No Z3 grey zone. |
| Build 1 | 75–85% of peak | 78 / 22 | Threshold enters. 1 hard session/week. |
| Build 2 | 85–95% of peak | 72 / 28 | 2 hard sessions/week. Race-pace work begins. |
| Peak | 90–100% of peak | 65 / 35 | Specificity max. Tune-up race if available. |
| Taper week 1 | 65% of peak | 70 / 30 | Volume drops, intensity preserved. |
| Taper week 2 (race week) | 40–50% of peak | 70 / 30 | 2–3 short sessions, 1 activation day, rest. |
| Recovery weeks | 55–60% of prior week | 90 / 10 | All easy. No intervals. |

**CTL ramp rate target:** 3–7 TSS/week sustainable. >10 TSS/week per week is injury risk — flag and reduce.

### Sport TSS split (dual-sport athletes)

For run-primary plans (e.g. half marathon A race):
- Base: 50% run / 50% ride
- Build: 60% run / 40% ride
- Peak: 70% run / 30% ride
- Taper: 80% run / 20% ride (keep legs in run mode)

For ride-primary plans (e.g. gran fondo A race):
- Base: 30% run / 70% ride
- Build: 20% run / 80% ride
- Peak: 10% run / 90% ride
- Taper: 10% run / 90% ride

Adjust based on athlete's stated sport mix and time constraints.

---

## Step 4 — Session archetypes

Use these as building blocks. Fill in zone values from `get_athlete_profile` at plan time.

### Running archetypes

| Name | Format string |
|---|---|
| Long run (Z2) | `{duration}min easy run, HR <{z2_max}bpm, RPE 4–5, flat terrain, conversational pace` |
| Aerobic base run | `{duration}min Z2 run, HR {z2_min}–{z2_max}bpm, RPE 4, no surges` |
| Strides | `After easy run: 6×20s strides @ {stride_pace}/km, 40s walk recovery, stay relaxed` |
| Tempo run | `{wu}min WU + {main}min Z3 tempo @ {tempo_pace}/km + {cd}min CD, HR {z3_min}–{z3_max}bpm, RPE 6–7` |
| Threshold intervals | `{wu}min WU + {reps}×{rep_min}min @ {threshold_pace}/km (rFTP ±5s), {recovery}min Z1 recovery + {cd}min CD` |
| VO2max intervals | `{wu}min WU + {reps}×{rep_min}min @ {vo2_pace}/km (95–100% max HR), {recovery}min walk/jog + {cd}min CD` |
| Race-pace run | `{wu}min WU + {main}min @ goal pace {race_pace}/km + {cd}min CD, RPE 7–8` |
| Hill repeats | `{wu}min WU + {reps}×{rep_min}min uphill effort Z4–Z5, walk/jog down recovery + {cd}min CD` |

### Cycling archetypes

| Name | Format string |
|---|---|
| Endurance ride (Z2) | `{duration}min Z2 ride, power {z2_min}–{z2_max}W, HR <{z2_hr_max}bpm, cadence 85–95rpm, RPE 4–5` |
| Sweet spot | `{wu}min WU + {reps}×{rep_min}min @ {ss_min}–{ss_max}W (88–93% FTP), {recovery}min Z1 + {cd}min CD` |
| Threshold intervals | `{wu}min WU + {reps}×{rep_min}min @ {ftp_min}–{ftp_max}W (FTP ±5%), {recovery}min Z1 + {cd}min CD` |
| VO2max intervals | `{wu}min WU + {reps}×{rep_min}min @ {vo2_min}–{vo2_max}W (106–120% FTP), {recovery}min Z1 + {cd}min CD` |
| Long ride | `{duration}min Z2 ride, power {z2_min}–{z2_max}W, include {climbing}m elevation, fuel 60–90g carbs/hr from km 0` |
| High-cadence drill | `Within Z2 ride: 3×5min @ 100–110rpm, {z2_min}–{z2_max}W, no resistance increase` |
| Race-simulation ride | `{duration}min with {reps}×{rep_min}min race-effort climbs @ {z3_max}–{z4_max}W, Z2 between` |

### Strength archetype (dual-sport support)

| Name | Format string |
|---|---|
| Leg strength | `3×8–12 reps: squats, leg press, single-leg step-ups, Romanian deadlift. RPE 7. {duration}min total.` |
| Maintenance strength | `2×10 reps: squats, step-ups, calf raises. Light load. RPE 5. {duration}min total.` |

---

## Step 5 — Race-back scheduling

1. **Pin the A event** — mark as rest/travel day before, easy activation day 2 days before.
2. **Count backward** from A event to today — that gives plan duration in weeks.
3. **Place B races** — treat as quality sessions within their week. 6–8 days easy after a B race before resuming intensity. No taper for B races unless within 4 weeks of A event.
4. **Place C races** — replace a quality session in that week. No taper. Easy day after.
5. **Check for conflicts** — call `get_calendar_window` to see what's already on the calendar before placing any session. Never overwrite a confirmed race.
6. **Blocked weeks** — if athlete has travel or life constraints, pre-load those as reduced-TSS weeks in the plan and adjust surrounding weeks to compensate.

---

## Step 6 — Draft the plan

Format as a compact Markdown table. One row per week. Columns:

```
| Wk | Phase | Mon | Tue | Wed | Thu | Fri | Sat | Sun | TSS | Notes |
```

- Use short session descriptors in cells (e.g. `60min Z2 run`, `90min ride SS`, `Intervals`, `Rest`, `Race`)
- Bold any race day
- Italicize recovery weeks
- Add a "Notes" column for key cues (e.g. "introduce strides", "back-to-back", "tune-up race")

Below the table, add a **Phase summary** block:
```
### Phase summary
- Base (W1–6): build aerobic base, economy strides, CTL target X→Y
- Build 1 (W7–10): threshold introduction, CTL target Y→Z
...
```

---

## Step 7 — Save, bake, commit

After athlete approves the plan:

```
save_plan(plan_markdown, event_name, event_date)
bake()
```

Then commit and push both repos:
- Personal repo: `git add -A && git commit -m "Add <event> training plan" && git push`
- Public repo: commit only if general wiki was updated during this session

Confirm to the athlete: plan saved, dashboard updated, link to view it.

---

## Plan revision rules

When revising an existing plan (not building from scratch):
1. `get_previous_plans` — load the current plan
2. Identify what changed (injury, new race, fitness update, schedule change)
3. Only modify affected weeks — do not rebuild the whole plan unless the A event date changed
4. Re-run `save_plan` with the full revised markdown (it overwrites the previous file)
5. `bake()` after saving

---

## Coaching guardrails

- **Never plan above peak historical CTL** in the first 4 weeks. Athlete must earn it.
- **Never skip recovery weeks** to fit more build. If the math doesn't fit, shorten the peak phase, not the recovery.
- **Flag grey-zone sessions** (Z3 tempo that isn't prescribed) — if the athlete has a tendency to drift into Z3, note it in the plan and prescribe specific HR/power caps.
- **Nutrition note on every session >2h ride or >90min run** — include fueling target in the session descriptor.
- **Power targets on all cycling sessions** — never HR-only for a power-meter athlete.
