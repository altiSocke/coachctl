# Endurance Training Principles — Science Reference


---

## Training Stress Score (TSS)

TSS quantifies training load as a single number, combining duration and intensity.

### Power-based TSS (Coggan) — Cycling

```
TSS = (duration_s × NP × IF) / (FTP × 3600) × 100
```

Where:
- **NP** (Normalised Power) = 30s rolling average, raised to 4th power, averaged, then 4th root
- **IF** (Intensity Factor) = NP / FTP
- 100 TSS = 1 hour at exactly FTP

Requires a calibrated power meter. Gold standard for cycling load quantification.

### Pace-based rTSS — Running

```
rTSS = (duration_s × NGP × RI) / (rFTP_ms × 3600) × 100
```

Where:
- **NGP** (Normalised Graded Pace) = grade-adjusted pace using Minetti cost function
- **RI** = NGP / rFTP_ms (running Intensity Factor)
- **rFTP** = functional threshold pace (sustainable for ~60min)

### hrTSS (Banister TRIMP) — Fallback

Used when no power meter or pace data is available (e.g. swimming, gym, HR-only sessions).

```
hrTSS = duration_min × HRR × (0.64 × e^(1.92 × HRR))
```

Where `HRR = (avg_hr − resting_hr) / (threshold_hr − resting_hr)`

**Priority:** power-TSS > rTSS > hrTSS. hrTSS is a rough approximation only.

### Typical TSS values by session type

| Session | Typical TSS |
|---|---|
| Easy 1hr Z2 ride | 40–60 |
| Threshold 1hr ride | 80–100 |
| 3hr endurance ride | 120–180 |
| Long race-pace run 1hr | 80–100 |
| 200km alpine race (Alpenbrevet) | 800–1000 |
| Marathon | 250–350 |

### TSS Recovery Guidelines (Fellrnr)

| TSS | Recovery time needed |
|---|---|
| <150 | Complete by next day |
| 150–300 | Complete by second day |
| 300–450 | More than two days |
| >450 | Several days |

Note: runs with significant downhill content may require more recovery than TSS suggests, due to eccentric muscle damage not captured by the metric.

---

## TRIMP Variants

TRIMP (TRaining IMPulse) is the generic term for any training load metric. Several methods exist:

| Method | Basis | Pros | Cons |
|---|---|---|---|
| **TRIMPcr10** | Session RPE × duration (min) | No tech needed; captures mood/fatigue | Subjective; end-of-session bias |
| **TRIMPavg** | Avg HR × duration | Simple | Doesn't distinguish interval vs steady effort |
| **TRIMPzone** | HR zone × zone multiplier | Works with basic HR monitor | Cliff-edge zone boundaries; linear scaling |
| **TRIMPexp** | HRR × exponential scaling (Banister) | Physiologically grounded; accounts for non-linearity | Requires HR data; gender-specific constants |
| **TSS** (power) | NP²/FTP × duration | Objective; cross-athlete comparable | Requires power meter |
| **rTSS** (pace) | NGP/rFTP × duration | Objective for running | Requires GPS + grade data |

**TRIMPexp formula (Banister, men):**
```
TRIMPexp = Σ(D × HRR × 0.64 × e^(1.92 × HRR))
```
Where D = duration in minutes at a given HR, HRR = (HR − HRrest) / (HRmax − HRrest).
For women, replace 1.92 with 1.67.

**Key insight:** TSS is normalised so 100 = 1hr at FTP/rFTP, enabling cross-athlete comparison. TRIMPexp is not normalised but is more physiologically accurate for HR-only training.

---

## Fitness Model: CTL / ATL / TSB

Based on Banister's impulse-response model (1975). All three metrics are exponential moving averages of daily TSS.

### CTL — Chronic Training Load (Fitness)

```
CTL_today = CTL_yesterday × e^(-1/42) + TSS_today × (1 − e^(-1/42))
```

42-day time constant. Tracks the average daily training load over the past ~6 weeks. Represents the athlete's fitness capacity. Also called "fitness".

**Important nuance:** the 42-day constant does not mean workouts are averaged over 42 days. The impact of any single workout halves every 14.7 days — it never fully disappears, it just approaches zero asymptotically.

**Target CTL ramp rates:**
- 3–5 TSS/week: conservative, suitable for beginners or high-stress life periods
- 5–7 TSS/week: sustainable for most trained athletes
- 7–10 TSS/week: aggressive, monitor closely for signs of overtraining
- >10 TSS/week: overreaching territory — not sustainable for more than 2–3 weeks

### ATL — Acute Training Load (Fatigue)

```
ATL_today = ATL_yesterday × e^(-1/7) + TSS_today × (1 − e^(-1/7))
```

7-day time constant. Impact of a workout halves every 2.4 days. Tracks recent training load. Represents current fatigue state.

### TSB — Training Stress Balance (Form)

```
TSB = CTL − ATL
```

Positive TSB = fresh (fitness > fatigue) → good for racing.
Negative TSB = fatigued → good for adaptation.

**Interpretation:**

| TSB | State | Typical scenario |
|---|---|---|
| +20 to +25 | Peak form | A race day target |
| +5 to +20 | Fresh, performing well | B race, quality sessions |
| −5 to +5 | Moderate fatigue | Normal training |
| −10 to −20 | Building fatigue | Hard training block |
| −20 to −30 | High fatigue | Heavy training, monitor |
| < −30 | Overtraining risk | Mandatory rest |

**Race day targeting:** TSB +15 to +25 for A events. Achieved through a 10–14 day taper where volume drops 40–50% but intensity is preserved.

**Practical note (Fellrnr):** in practice, CTL is used to measure both fitness AND overall fatigue load. ATL is mostly used to compute TSB for short-term taper management. Most published guidance around "target CTL levels" uses CTL as the primary load metric.

---

## Performance Models (Banister / Busso / TSB)

Three models exist for predicting how training changes performance:

### TSB Model (Coggan simplification)
- Simplest; widely supported in software (TrainingPeaks, Runalyze)
- Only detects *relative* changes: reduced training → improved TSB → better performance
- Does not predict absolute performance
- Ignores Training Monotony and overtraining

### Banister Model (1975)
- Most experimentally validated (verified in runners: Morton et al. 1990)
- Shows that steady-state training *does* improve performance (unlike TSB)
- Uses four constants: k1 (fitness weighting), k2 (fatigue weighting), r1 (fitness decay ~49d), r2 (fatigue decay ~11d)
- Constants are individual-specific — must be reverse-engineered from performance data

### Busso Model (2003)
- Refinement of Banister: k2 becomes an exponential decay of training stress
- The only model that accounts for Training Monotony's effect on fatigue
- Most complex; rarely used in practice

**Bottom line:** use TSB for day-to-day training management. Understand that it underestimates the cost of monotonous training.

---

## Supercompensation

The fundamental mechanism of fitness adaptation: exercise causes a temporary decrease in fitness, followed by recovery and a *supercompensation* above the original baseline — provided adequate rest is given.

### The four scenarios

1. **Adequate rest:** next session starts near the peak of supercompensation → progressive fitness gain
2. **Insufficient rest (stagnation):** next session starts at end of recovery, before supercompensation → no improvement, just maintenance
3. **Overtraining:** insufficient rest → each session further reduces fitness → downward spiral
4. **Too much rest:** supercompensation peak passes before next session → fitness returns to baseline → no net gain

### Intensity and supercompensation

- Too little intensity → small supercompensation signal
- Too much intensity → recovery takes so long that supercompensation is minimal
- Far too much → no supercompensation; injury risk
- Optimal: "Goldilocks" intensity that produces mild DOMS resolving in 1–2 days

### Different systems, different timescales

Long runs and speedwork can be combined because they stress different systems:
- Long run → endurance supercompensation curve (slower, longer)
- Speedwork → aerobic/neuromuscular supercompensation curve (faster, shorter)

This is why a quality session can follow a long run within 24–48h without compromising either adaptation.

### Practical rules
- **Hard/easy alternation:** the biggest mistake recreational athletes make is training too hard on easy days, blunting supercompensation from hard days
- **4 days/week running** is often cited as optimal: allows hard sessions with full recovery between them
- Easy days should be genuinely easy — not "moderate" — to allow full recovery

---

## Training Monotony

Training Monotony measures the *similarity* of daily training stress — not boredom. High monotony = similar load every day = insufficient variation for supercompensation = overtraining risk.

**Source:** Foster 1998 (Med Sci Sports Exerc); Busso 2003.

### Formula

```
Monotony = avg(daily TRIMP) / stddev(daily TRIMP)   [rolling 7-day window]
```

- Values **>2.0** are generally too high
- Values **<1.5** are preferable
- Cap at 10 to avoid sensitivity to near-zero stddev

**Updated formula (more stable):**
```
Monotony = avg(TRIMP) / (stddev(TRIMP) + avg(TRIMP))
```
This bounds monotony between 0.29 (single training day, 6 rest days) and 1.0 (identical load every day).

### Training Strain

```
Training Strain = sum(weekly TRIMP) × Monotony
```

Training Strain is a better overall stress metric than volume alone — it penalises monotonous training even at moderate volume.

**Example (Fellrnr):** a week of 50 miles with 3 hard days + 4 easy days gives Monotony ~1.36 and Strain ~903. The same week with 2 rest days drops Strain by 22% despite only 8% less mileage. A monotonous week of 46 miles at the same easy pace every day gives Monotony 4.69 and Strain 1,944 — more than double the strain at lower volume.

### Practical implications

- **Rest days are not wasted days** — they reduce Training Strain disproportionately
- **Vary session types:** long run + tempo + easy + rest produces lower monotony than daily easy runs
- **Grey zone trap:** athletes who train at Z3 every day have high monotony AND high fatigue — worst of both worlds
- **Recovery weeks** (40–50% volume cut) dramatically reduce Training Strain and allow supercompensation

---

## Periodization

### Mesocycle structure

Standard 4-week mesocycle: 3 build weeks + 1 recovery week.

- **Build weeks:** progressive load increase (5–10% TSS per week)
- **Recovery week:** volume cut 40–50%, maintain one quality session to prevent detuning. CTL drops slightly. TSB recovers to positive.

Skipping recovery weeks leads to accumulated fatigue, stagnating fitness, and injury.

### Phase progression (general)

| Phase | Duration | Focus |
|---|---|---|
| Base | 4–8 weeks | Aerobic capacity (Z1–Z2), volume building |
| Build | 8–12 weeks | Threshold development, sport-specific intensity |
| Peak | 4–6 weeks | Race-specific pacing, VO2max intervals, volume reduction |
| Taper | 10–14 days | Sharpening, fatigue clearance, TSB positive |
| Race | Event | — |
| Recovery | 1–3 weeks | Easy volume only, no intensity |

### Training age and adaptation

Newer athletes adapt faster to volume. Experienced athletes require more intensity stimulus. General rule: athletes with <3 years structured training respond well to volume increases; >3 years need intensity periodization.

---

## Polarized Training

The 80/20 model: 80% of training time in low intensity (Z1–Z2), 20% in high intensity (Z4–Z5). Minimal time in the "grey zone" (Z3 tempo).

**Why it works:**
- High volume Z1–Z2 develops mitochondrial density, fat oxidation capacity, cardiac stroke volume
- Z4–Z5 sessions develop VO2max, lactate clearance, neuromuscular power
- Z3 (tempo) is metabolically costly but provides less adaptive stimulus per unit of fatigue than either extreme

**Grey zone trap:** athletes naturally drift toward Z3 because it "feels hard enough." But Z3 fatigues the body enough to prevent adequate Z4–Z5 quality while not being easy enough to allow full Z1–Z2 volume. It is the zone that produces mediocre results with high RPE.

**Polarization index:** ratio of Z1+Z2 time to Z4+Z5 time. Target ≥4:1 (e.g. 80% easy, 20% hard). Tempo (Z3) should be <10% of total time.

---

## Zone Models

### Heart Rate Zones (5-zone model, Friel)

Based on Lactate Threshold Heart Rate (LTHR):

| Zone | % of LTHR | Character |
|---|---|---|
| Z1 Recovery | <82% | Conversational, fat-burning |
| Z2 Aerobic | 82–89% | Comfortable but purposeful |
| Z3 Tempo | 89–94% | Comfortably hard |
| Z4 Threshold | 94–100% | Hard, speech disrupted |
| Z5 VO2max | >100% | Very hard, unsustainable >8min |

### Power Zones (Coggan, 7-zone model)

| Zone | % of FTP | Name |
|---|---|---|
| Z1 | <55% | Active recovery |
| Z2 | 56–75% | Endurance |
| Z3 | 76–90% | Tempo |
| Z4 (SS) | 88–95% | Sweet spot |
| Z5 | 96–105% | Threshold |
| Z6 | 106–120% | VO2max |
| Z7 | >121% | Neuromuscular |

Sweet spot (88–95% FTP) is particularly efficient: high aerobic stimulus with lower glycolytic cost than pure threshold. Useful for long climb intervals and race-specific work.

### Pace Zones (Running, 6-zone model)

Based on rFTP (Functional Threshold Pace):

| Zone | % of rFTP speed | Character |
|---|---|---|
| Z1 Recovery | <76% | Very easy jog |
| Z2 Aerobic | 76–85% | Easy, conversational |
| Z3 Tempo | 85–92% | Comfortably hard |
| Z4 Threshold | 92–100% | Hard, ~1hr pace |
| Z5 VO2max | 100–112% | Very hard, ~6–10min max |
| Z6 Anaerobic | >112% | Sprint/neuro |

---

## Tapering

**Goal:** arrive at race day with peak fitness (CTL maintained) and minimal fatigue (ATL reduced), achieving TSB +15 to +25.

**Protocol:**
- Duration: 10–14 days for A events; 5–7 days for B events
- Volume: reduce 40–50% (CTL will drop slightly — acceptable)
- Intensity: preserve; at least 2 quality sessions in the taper to maintain neuromuscular sharpness
- Avoid: complete rest (leads to detraining feeling), new stimuli, heavy legs from unexpected activity

**Common taper mistakes:**
- Cutting volume AND intensity → legs feel dead on race day
- No quality sessions in final week → neuromuscular dullness
- Taper anxiety leading to extra sessions → insufficient rest
- Race-week illness from sudden drop in training stress (immune system stress response)
