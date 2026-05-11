# Cycling Training — Science Reference


---

## Power Meter Fundamentals

### Why power matters

Heart rate lags effort by 30–90 seconds and is confounded by heat, caffeine, fatigue, and stress. Power is instantaneous and objective. For pacing climbs, intervals, and long events, power gives the clearest signal.

### Key metrics

- **Average Power:** mean watts including zeros. Misleading for rides with stops or variable effort.
- **Normalised Power (NP):** 30-second rolling average raised to 4th power, averaged over ride, then 4th root. Better reflects physiological cost.
- **Intensity Factor (IF):** NP / FTP. IF=0.75 = endurance ride; IF=1.0 = full FTP hour.
- **Variability Index (VI):** NP / Average Power. VI=1.0 = perfectly steady; VI>1.1 = highly variable (typical of crits and climbs).
- **TSS:** see training_principles.md

---

## FTP (Functional Threshold Power)

The highest power an athlete can sustain for approximately 60 minutes. The foundation of all power-based training zones.

### Testing protocols

**20-minute test:** 20min all-out effort after proper warm-up. FTP = 95% of 20min avg power. Standard protocol but requires motivation.

**Ramp test:** 1-minute increments increasing by a fixed wattage. FTP = 75% of the peak 1-minute average power. Easier to execute. Common in lab/structured training apps.

**8-minute test:** 2×8min all-out with 10min recovery. FTP = 90% of average of the two 8min efforts.

### FTP and W/kg

W/kg (watts per kilogram) is the primary metric for climbing speed and relative performance:

| W/kg (FTP) | Level |
|---|---|
| <2.5 | Recreational |
| 2.5–3.5 | Club / sportive rider |
| 3.5–4.5 | Trained amateur |
| 4.5–5.5 | Cat 3–4 racer |
| >5.5 | Elite/Cat 1–2 |

Every kg lost (at same power) increases W/kg. A 250W athlete at 75kg = 3.33 W/kg. At 70kg = 3.57 W/kg.

---

## Climbing

### VAM (Velocità Ascensionale Media)

Vertical ascent in metres per hour. A proxy for climbing power-to-weight ratio.

```
VAM = (elevation_gain_m × 3600) / duration_s
```

Typical VAM values:
- Recreational cyclist: 500–800 m/hr
- Trained amateur: 900–1200 m/hr
- Pro peloton (mountain stages): 1500–1800 m/hr

### Pacing climbs

The most common mistake is going too hard early on a long climb. Power drops exponentially once lactate clears threshold.

**For climbs >20 minutes:**
- Start at 85–90% FTP (sweet spot low)
- Do not exceed 100% FTP in the first third
- Save any surge for the final 2–5 minutes

**For climbs <10 minutes:**
- Can start at 100–110% FTP
- Hard effort is sustainable for the duration

**Gradient effect:** steeper = lower cadence, higher torque, more muscular fatigue. Use gearing to maintain 70–85 rpm on steep sections.

### Drafting

At 35–40 km/h on flat terrain, aerodynamic drag accounts for ~85–90% of total resistance. Riding in the slipstream of another rider reduces drag by 25–35%, saving 20–30% power for the same speed.

**Practical implication:** staying in a group on flat sections between climbs saves enormous energy for the next ascent. Losing the group = riding solo = ~25% more energy expenditure.

---

## Cadence

Optimal cadence for endurance cycling is approximately **85–95 rpm**.

- **Higher cadence (>95 rpm):** shifts load from muscles to cardiovascular system. Reduces muscular fatigue but increases oxygen cost.
- **Lower cadence (<75 rpm):** shifts load to muscles (more torque per pedal stroke). Increases glycogen use and muscular fatigue. Higher cramp risk on long events.

On long climbs, maintaining 75–85 rpm preserves neuromuscular function for the final hours. Grinding big gears (60–65 rpm) is hard on quads and accelerates fatigue.

**High-cadence drills:** 3–5 minutes at 100–110 rpm in a light gear. Trains neuromuscular coordination and efficiency at higher cadences.

---

## Cramp Prevention in Long Rides

Muscle cramping in endurance cycling is multi-factorial. No single cause, no single fix.

**Contributing factors:**
1. **Fatigue:** motor unit failure after sustained effort → involuntary contraction
2. **Dehydration:** reduced plasma volume → nerve sensitivity changes
3. **Sodium deficit:** altered chloride channel function in muscle
4. **Glycogen depletion:** aerobic fatigue accelerates motor unit recruitment failures
5. **Inadequate training load:** undertrained for the specific demand (cadence, duration, gradient)

**Prevention strategies:**
- Train the specific muscles for the specific demand (leg strength + long rides)
- Maintain cadence ≥90 rpm on flat sections (reduces torque per pedal stroke)
- Sodium in bottles from the start (500–700mg/hr minimum)
- Carbs from the start (glycogen preservation)
- Eccentric leg strength work (Romanian deadlifts, single-leg step-ups)
- Stretch quads on every descent (15–20s, drop heels, heel-to-butt stretch)

**During a cramp:** easy gear, spin high cadence (100+ rpm if possible). Stop for 30s stretch if full cramp. Salt capsule. Restart at Z2 for 5 minutes before resuming effort.

---

## Stretching, Flexibility & Bike Position

See `wiki/general/stretching.md` for full protocol. Cycling-specific summary:

**Why flexibility matters more for cyclists than runners:**
The bike locks you in sustained hip flexion (~90–110° at top of pedal stroke) for hours. This chronically shortens hip flexors, loads the lumbar spine, and compresses the thoracic spine into kyphosis. Unlike running where limited range of motion is a moderate issue, on the bike **flexibility deficits directly constrain how aggressive a fit you can achieve and sustain**.

| Flexibility deficit | Consequence | Impact |
|---|---|---|
| Tight hip flexors | Anterior pelvic tilt; altered saddle contact | Knee tracking / PFPS; can't hold low front end |
| Tight hamstrings | Forced posterior pelvic tilt at BDC | Dead spots in pedal stroke; limits reach to drops |
| Restricted thoracic extension | Compensated by cervical extension | Neck pain; increased aerodynamic drag |
| Tight calves/soleus | Heel drop at BDC; reduced ankle stability | Platform efficiency loss; Achilles risk |

**Post-ride (15 min) — highest priority for cyclists:**
Hip flexors (kneeling lunge), hamstrings, adductor butterfly, thoracic extension on foam roller, glutes (figure-4), calves, neck. Post-ride stretching is more critical than pre-ride for cyclists.

**Thoracic foam roller extension:** lie transversely over foam roller at mid-thoracic level, arms crossed, extend gently over roller for 90s. Move roller 2–3 positions. Single highest-ROI flexibility intervention for road/gravel cyclists.

**Standalone (3×/week off-day):** pigeon pose, lizard lunge, seated forward fold, thoracic rotation drills — 20–30 min. 4–8 weeks of consistent practice enables meaningfully more aggressive bike fit.

---

## Sweet Spot Training

Sweet spot (88–95% FTP) is the most efficient training zone for improving FTP in trained athletes:

- High enough to drive significant physiological adaptation (mitochondrial density, lactate clearance)
- Low enough to be sustainable for 20–40 minute intervals without full glycogen depletion
- Recoverable within 24–48 hours (unlike full-threshold work which needs 48–72hr)

**Typical sweet spot sessions:**
- 3×20min at 88–95% FTP, 5min rest
- 2×30min at 88–92% FTP
- 1×45–60min at 85–90% FTP (long sweet spot — very effective for climbing)

**Overuse of sweet spot:** more than 2–3 sessions per week without polarizing with Z2 and Z5 work leads to grey-zone accumulation and plateau.