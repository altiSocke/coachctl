description: Generate a structured weekly training scorecard. Load when the athlete asks for a weekly review, weekly summary, training check-in, or "how's my training going". Pulls weekly TSS, zone distribution, CTL/ATL/TSB trend, untracked activities, and RPE feedback, then produces a compact scorecard with flag analysis and next-week adjustments. Always saves a coaching note.
## What I do

Pull the last 2 weeks of training data, produce a compact scorecard, flag any concerns, and propose next-week adjustments. Always save the summary as a coaching note.

---

## Step 1 — Data gathering

Run all of these before drafting anything:

```
get_weekly_summary(weeks=4)        # TSS, volume, intensity by sport for last 4 weeks
get_zone_distribution(weeks=4)     # HR zone time distribution and polarization index
get_fitness_trend(weeks=8)         # CTL/ATL/TSB daily values
get_untracked_activities(weeks=2)  # hockey, gym, golf, etc.
get_recent_feedback(n=10)          # RPE trends from last ~2 weeks
get_athlete_profile                # zones, FTP, rFTP, events (for plan targets)
get_previous_plans(n=1)            # active plan — to compare actual vs target TSS
```

---

## Step 2 — Scorecard format

Output a compact Markdown table:

```
### Week of [Mon date] — Training Scorecard

| Metric | This week | Last week | Plan target | Status |
|---|---|---|---|---|
| Total TSS | | | | |
| Run TSS | | | | |
| Ride TSS | | | | |
| CTL (end of week) | | | — | |
| ATL (end of week) | | | — | |
| TSB (end of week) | | | — | |
| Z1+Z2 % | | | ≥80% | |
| Z4+Z5 % | | | ≥15% | |
| Sessions completed | | | | |
| Untracked sessions | | | — | |
| Avg RPE | | | — | |
```

**Status column values:**
- ✅ On target
- ⚠️ Slightly off (within 15% of target, or amber threshold)
- 🚨 Flag (outside 15% of target, or red threshold)
- — Not applicable

**Plan target column:** pull from the active plan's prescribed week if available. If no plan is active or the week can't be matched, leave as "—".

---

## Step 3 — Flag analysis

Check each of these and surface only the ones that trigger:

### Load flags

| Flag | Condition | Message |
|---|---|---|
| Overreach | Week TSS > plan target × 1.20 | "TSS ran {X}% over plan — watch recovery next week" |
| Underdone | Week TSS < plan target × 0.70 | "TSS {X}% below plan — reason? If life, note it. If fatigue, it was right." |
| CTL ramp too fast | CTL gained >10 TSS in 7 days | "CTL ramp {X} TSS/week — above safe ceiling of 10. Injury risk elevated." |
| CTL ramp too slow | In a build phase, CTL gained <2 TSS in 7 days | "CTL barely moved. Check for missed sessions or excessive easy running." |
| High fatigue | TSB < −20 | "TSB {X} — deep fatigue hole. If no race incoming, reduce load this week." |
| Race approaching + negative TSB | TSB < −10 with A/B race in ≤14 days | "Race in {N} days, TSB {X}. Start tapering now — target TSB +15 to +25 on race day." |

### Intensity flags

| Flag | Condition | Message |
|---|---|---|
| Grey zone drift | Z3 > 20% | "Z3 at {X}% — grey zone. Push easy sessions easier, hard sessions harder." |
| Not enough intensity | Z4+Z5 < 10% in a build/peak week | "Almost no Z4+Z5 this week. If a hard session was planned, it didn't execute." |
| Polarization good | Z1+Z2 ≥ 80% and Z4+Z5 ≥ 15% | ✅ no flag needed — note it's on target |

### RPE flags

| Flag | Condition | Message |
|---|---|---|
| High RPE trend | Avg RPE ≥ 7 across last 5 sessions | "RPE averaging {X} — athlete is working hard. Monitor for cumulative fatigue." |
| RPE/TSS mismatch | High RPE on low-TSS sessions | "Effort feels harder than data shows — possible fatigue accumulation not captured in TSS." |

### Compliance flags

| Flag | Condition | Message |
|---|---|---|
| Sessions missed | Completed < planned - 1 | "Missed {N} session(s) this week. Note reason in coaching note if known." |
| Untracked load | Untracked TSS > 30 | "Untracked sessions added {X} TSS — factor into fatigue picture." |

---

## Step 4 — Interpretation paragraph

After the scorecard table and flags, write 2–4 sentences:
- Overall assessment: was this a good week?
- One key positive
- One key concern (if any)
- One adjustment for next week (if any)

Keep it direct. Lead with the most important signal.

---

## Step 5 — Next-week adjustments

If any red flags triggered, propose a specific adjustment:

| Flag triggered | Proposed adjustment |
|---|---|
| CTL ramp too fast | Cap next week TSS at current week − 15% |
| TSB < −20 | Recovery week: next week TSS = 55–60% of this week, all easy |
| Race in ≤14 days, TSB negative | Begin taper: volume −30%, keep 1 quality session, rest 2 days pre-race |
| Grey zone drift | Next easy sessions: explicit HR cap at Z2 max, RPE 4 max |
| TSS significantly under plan | Identify missed session type, reschedule if still in build phase |

State the adjustment as a single actionable sentence. Do not prescribe the full next week here — that's a `plan-builder` task.

---

## Step 6 — Save coaching note

Always call:

```
save_coaching_note(
  note="[week scorecard summary in 3–5 sentences including key numbers]",
  category="observation",
  tags="weekly-review,ctl,tsb,[sport]",
  session_date="[Monday of the reviewed week]"
)
```

Include: week-of date, total TSS, CTL, TSB, polarization index, any red flags triggered, and the proposed adjustment.

Example note:
> "Week of May 4: TSS 312 (plan 290, +8%). CTL 38.4 → 40.1, ramp 1.7/day = 11.9/week — above safe ceiling. TSB −18. Z3 22% — grey zone drift. Adjustment: cap next week at 265 TSS, enforce HR cap on easy sessions. SOLA 04 in 12 days — taper begins W/C May 11."