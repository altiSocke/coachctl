description: Create, review, or update a structured race card. Load when the athlete asks to set up a race, fill in race strategy, review a race plan, or edit any section of a race card (pacing, nutrition, climbs, logistics, kit, warmup, protocols, YoY, readiness gate). Encodes the full section-by-section propose/confirm/apply flow and general-vs-personal boundary rules.
## What I do

Build and maintain structured race cards — per-event strategy documents stored in the events table `payload_json`. Each section is edited independently via a propose → confirm → apply flow. The dashboard renders them at `#race/<slug>` with print optimization.

---

## Before touching any race card

Always call `get_calendar_window` first to confirm the event exists in the events table. Never trust dates or race names from narrative wiki text — the events table is the single source of truth.

If the race does not exist yet:
```
create_race(name, date, priority, slug)
```
This seeds an empty payload skeleton with all sections as `{}` / `[]`. Do not create a race event via `create_event` — use `create_race` so the payload skeleton is initialized correctly.

Then call `get_event_detail(slug)` to load the current payload before editing any section.

---

## Section edit order

Work through sections in this order when building a card from scratch. When revising, jump directly to the relevant section.

| # | Section | Tool pair | Content |
|---|---|---|---|
| 1 | Course | `propose_race_course` / `apply_race_course` | Distance, elevation, surface, profile, key climbs summary |
| 2 | Goal | `propose_race_goal` / `apply_race_goal` | A/B/C targets, target pace/power, key metric |
| 3 | Key principles | `propose_race_key_principles` / `apply_race_key_principles` | 3–5 top-of-mind race day rules (e.g. "Start conservative", "Fuel from km 0") |
| 4 | Pacing | `propose_race_pacing` / `apply_race_pacing` | Km-by-km or segment-by-segment table: pace/power, HR cap, cues |
| 5 | Climbs | `propose_race_climbs` / `apply_race_climbs` | Cycling only: climb card with power cap, HR cap, strategy per climb |
| 6 | Warmup | `propose_race_warmup` / `apply_race_warmup` | Pre-race sequence: timing, drills, strides, gel timing |
| 7 | Nutrition | `propose_race_nutrition` / `apply_race_nutrition` | Pre/during/post fueling: gel timing, carb targets, electrolytes, caffeine |
| 8 | Logistics | `propose_race_logistics` / `apply_race_logistics` | Travel, parking, bib pickup, bag drop, start time, transport |
| 9 | Kit | `propose_race_kit` / `apply_race_kit` | Shoes, clothing, accessories, what to carry |
| 10 | Protocols | `propose_race_protocols` / `apply_race_protocols` | Contingency cards: cramp, bonk, mechanical, weather |
| 11 | YoY | `propose_race_yoy` / `apply_race_yoy` | Year-over-year comparison table: time, power, HR, notes |
| 12 | Readiness gate | `propose_race_readiness_gate` / `apply_race_readiness_gate` | Start criteria, bail criteria, decision rules |

---

## Propose → confirm → apply flow

For every section edit:

1. **Draft** the section content
2. **Propose:** call `propose_race_<section>(slug, content)` — this returns a unified diff
3. **Present the diff** to the athlete. Do not apply yet.
4. **Wait for explicit approval** ("yes", "looks good", "apply it")
5. **Apply:** call `apply_race_<section>(slug, content)`

Never batch multiple section applies without confirmation between them. One section at a time.

---

## General-vs-personal boundary per section

| Section | What goes here | What goes in `wiki/races/<race>.md` instead |
|---|---|---|
| Course | Personal course notes, athlete-specific cues ("the false flat at km 14 always feels hard") | Course facts applicable to any runner: gradients, distances, surface, aid station locations |
| Goal | Athlete's specific A/B/C targets, personal bests, gate conditions | — (always personal) |
| Key principles | Athlete-specific reminders based on past errors | — (always personal) |
| Pacing | Athlete-specific pace/power targets | Generic pacing zones for the course |
| Climbs | Athlete-specific power caps and HR caps | Climb gradients, lengths, elevation — put in `wiki/races/<race>.md` |
| Warmup | Athlete's personal warmup routine | — (always personal) |
| Nutrition | Athlete's specific gel plan, product inventory | Generic nutrition science for the distance → `wiki/nutrition.md` |
| Logistics | Athlete's personal travel, parking, bib logistics | Publicly available race logistics → `wiki/races/<race>.md` |
| Kit | Athlete's personal gear choices | — (always personal) |
| Protocols | Athlete's contingency responses | — (always personal) |
| YoY | Athlete's past results | — (always personal) |
| Readiness gate | Athlete's personal start/bail criteria | — (always personal) |

**Rule:** If a fact is true for any participant (e.g. "aid station at km 11.5"), put it in `wiki/races/<race>.md`. If it's only meaningful for this athlete (e.g. "take gel at km 5 before the hill"), it goes in the race card payload.

---

## Section content guidelines

### Course
- Distance, total elevation gain/loss, surface breakdown (% road / % gravel / % trail)
- Key segments: name, km range, elevation gain, avg gradient
- Aid stations: km positions and what's typically available
- Weather: typical race-day conditions for the month/region

### Goal
- Primary goal: target time, pace/power, conditions assumed
- Stretch goal: if gate race or fitness check confirms it
- Gate conditions: what result from a prior race unlocks the stretch
- Key metric: what to watch during the race (HR cap, pace, power, perceived effort)

### Key principles
- 3–5 rules, short and imperative
- Based on past errors or known tendencies
- Examples: "Never go out faster than goal pace in first 3km", "Eat before the first climb, not after", "Stay with the group past km 88"

### Pacing (running)
Table format: `| Km | Target pace | HR cap | Cues |`
- First 20%: conservative (5–10s/km slower than goal pace)
- Middle: settle to goal pace
- Final 20%: race by feel / HR ceiling only

### Pacing (cycling — general)
Table format: `| Segment | Km range | Power cap | HR cap | Notes |`
- Flats/rolling: Z2 power band
- Climbs: Z3 cap early, Z4 allowed mid-race, Z4–Z5 final climb

### Climbs (cycling)
Table format: `| # | Km | Gain | Power cap | HR cap | Notes |`
- Numbered in race order
- Strategy note per climb (e.g. "LET GROUP GO — they wait after this one")
- Post-climb: "if overcook → drop to Z1 for 5min + eat immediately"

### Nutrition
- Pre-race: T-3h meal (g carbs), T-30min gel/banana
- During: gel timing by km or time marker, carb target (g/hr), electrolyte schedule, caffeine timing
- Post-race: within 30min recovery window

### Warmup
- T-minus timing: when to eat, when to start moving, when to do strides
- Sequence: easy jog duration, drills, strides (reps × duration × pace)
- No static stretching in warmup — dynamic only

### Protocols (contingency cards)
- **Cramp:** easy gear, high cadence, spin through it. Full cramp: stop 30s, stretch, salt capsule, restart Z2.
- **Bonk:** drop to Z1 immediately, eat 40g carbs fast, wait 10min, reassess.
- **Mechanical (cycling):** tyre, chain, derailleur — basic roadside fix steps.
- **Weather:** heat → reduce target pace 6–8s/km per 5°C above 20°C, increase fluid intake.

### Readiness gate
- **Start criteria:** minimum fitness/health to toe the line (e.g. "No fever", "TSB > −10")
- **Bail criteria:** during-race decision points (e.g. "If HR >185 for >5min at km 5 → pull back to Z2")
- **Decision rule:** who decides (athlete only), what info they need

---

## After the card is complete

1. Tell the athlete they can view the printable card at `#race/<slug>` in the dashboard.
2. Save a coaching note summarising the strategy decisions made: `save_coaching_note(note, category='race', tags='race-card,<event-name>')`.
3. Commit and push the personal repo.

---

## Updating an existing card

When the athlete wants to revise a section:
1. `get_event_detail(slug)` — load current payload
2. Identify the specific section to change
3. Draft revised content for that section only
4. Propose → confirm → apply
5. No need to re-run other sections unless they're affected by the change