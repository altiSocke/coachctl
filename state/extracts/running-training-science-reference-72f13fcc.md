# Running Training — Science Reference


---

## Pace and Threshold

### rFTP (Running Functional Threshold Pace)

The pace sustainable for approximately 60 minutes — equivalent to lactate threshold. Expressed in seconds per kilometre.

Typical test: 30-minute time trial. rFTP = average pace for the full 30min (not 95% correction, unlike cycling — running uses the full effort).

Alternative: recent race results:
- 5km race pace × 1.10 ≈ rFTP
- 10km race pace × 1.04 ≈ rFTP
- Half marathon pace ≈ rFTP (slightly slower for most)

### Lactate threshold running

At lactate threshold pace, lactate production equals clearance — the highest steady-state effort. Running above this pace causes exponential lactate accumulation and rapid performance degradation.

**Key training zone:** Z4 threshold work (10–30min intervals at rFTP) is the primary driver of half marathon and marathon performance improvement.

---

## Grade-Adjusted Pace (GAP) / Normalised Graded Pace (NGP)

On hilly terrain, comparing raw pace across flat and hilly routes is meaningless. Grade-adjusted pace corrects for gradient using the energetic cost of running at a given slope.

### Minetti Cost Function

The energy cost of running per metre on a slope `i` (expressed as decimal, e.g. 0.10 for 10%):

```
C(i) = 155.4i^5 − 30.4i^4 − 43.3i^3 + 46.3i^2 + 19.5i + 3.6
```

Where `C` is in J/(kg·m). The baseline (flat) cost is ~3.6 J/(kg·m).

**GAP calculation:** for a segment with grade `i`, adjust the actual pace by `C(i) / C(0)` to get the equivalent flat pace.

### Symmetric grade model (used in this app)

For an out-and-back or loop course with both climbing and descending:
```
half_grade = 2 × total_gain / total_distance
```
This approximates average energy cost as the mean of the uphill and downhill Minetti costs.

**Why it matters:** on a hilly long run at 5:30/km average pace with 800m of climbing, the NGP might be 5:00/km — equivalent to running 5:00/km on flat. This is the relevant metric for TSS and intensity assessment.

---

## Running Economy

Running economy (RE) is the oxygen cost of running at a given velocity. More economical runners use less oxygen for the same pace — a significant determinant of distance running performance alongside VO2max and lactate threshold.

**Factors improving running economy:**
- Higher cadence (168–180 spm) — reduces vertical oscillation and ground contact time
- Shorter stride length at same pace (more steps, lighter contact)
- Core strength — reduces energy leak through trunk rotation
- Plyometric training — improves tendon stiffness and elastic energy return
- Accumulated running mileage — neuromuscular adaptation over years

**Cadence:** a cadence of 170–180 spm at most paces improves efficiency by reducing braking forces and ground contact time. Low cadence (<160 spm) is associated with higher injury risk (overstriding, heel striking).

---

## Running Cadence

Cadence (steps per minute) is one of the highest-leverage form variables — easy to measure, easy to change, and strongly evidence-backed.

**Target:** 90 strides/min per foot (180 steps/min counting both feet) at comfortable training pace on flat ground.

- Below 85 spm: too low unless very slow jogging
- 85–95 spm: normal training range
- Above 95 spm: interval/race pace
- Above 95 spm in easy training: stride becomes inefficient — higher is not always better

**Why cadence matters:**
- Efficient running requires elastic energy return ("bounce") from ankles — below a critical cadence this bounce is lost
- Higher cadence reduces ground contact time (GCT), which reduces impact forces
- Peak impact force at cadence 88 is just over half that at cadence 64 (Hamill 1995)
- Higher cadence reduces overstriding, ankle/knee/hip peak forces, and DOMS (Heiderscheit 2011; Schubert 2013)
- Cadence ~90 spm is associated with best running economy (Hamill 1995); one study found 85 optimal (Lieberman 2015)

**Changing cadence:**
- Focus on shorter steps, not faster running
- Use a metronome app or music remixed to 180 BPM
- Garmin/watch cadence alerts help maintain target
- Adaptation takes several weeks — initially feels unnatural ("shoes tied together")
- Higher cadence naturally improves other form elements: reduces overstriding, improves foot strike

**Cadence and fatigue:** as runners tire, cadence naturally rises and impact forces decrease — a protective mechanism (Willson 1999).

**Downhill cadence:** should be *higher* than flat, not lower — reduces impact on quads and maintains control.

---

## Running Form

Key components of good running form (source: Fellrnr.com, 2017):

### Cadence
See section above. The single most impactful and lowest-risk form change.

### Overstriding
Foot landing ahead of the hips creates braking forces and exacerbates heel strike. Fix: increase cadence and add a slight forward lean — overstriding often self-corrects.

### Forward lean
Slight forward lean from the ankles (not the waist) vectors muscular force backward for propulsion. A useful cue: stand tall, lean forward until you must step to avoid falling — that's the right lean angle.

### Run tall
Back straight, no hunching. Mental cue: imagine a thread pulling the top of your head upward. Look ahead, not at your feet.

### Arm position
Arms should swing naturally as a counterbalance — not driven consciously. Elbows ~90°, hands relaxed (not fists). Shoulders relaxed, not hunched. High cadence naturally keeps arms high; low arms create a slow pendulum that fights cadence.

### Foot strike
Controversial — insufficient evidence for clear recommendations. Focus on cadence and reducing overstriding first; foot strike often improves naturally. Dramatic heel-to-forefoot changes carry injury risk (stress fractures, tendon problems) — if changing, reduce mileage significantly.

### Vertical oscillation
Intuitive that less bounce = better economy, but science does not clearly support this. Not a priority for most runners.

### Step width
Optimal: feet landing ~3.6cm from body midline. Wider step width increases energy cost by up to 11% (Arellano 2011). Most runners don't need to address this.

### Listening to your feet
- **Pat sound:** good form — gentle, quiet landing
- **Scrape sound:** foot still moving forward on contact → overstriding
- **Slap sound:** high impact → investigate form or footwear
- **Asymmetry:** any difference between left and right → imbalance to address

### Changing form — risk hierarchy
1. **Cadence** — easiest, lowest risk, highest reward
2. **Overstriding** — easy to fix, low risk
3. **Forward lean** — easy, goes with overstriding fix
4. **Run tall** — requires awareness; reverts under fatigue
5. **Arm position** — linked to cadence
6. **Foot strike** — highest risk; change gradually with reduced mileage
7. **Step width** — change carefully; alters hip/leg stress

---

## Downhill Running

Downhill running is the most underutilised training tool for endurance athletes. It builds eccentric strength and resistance to muscle damage that cannot be achieved on flat or uphill terrain.

**Source:** Fellrnr.com (Downhill Running); DOMS research (Jones 1989, Child 1998).

### Why downhill matters
- Downhill running causes more muscle damage (eccentric loading) than uphill or flat
- This damage triggers structural muscle adaptation — creating lasting resistance to future damage
- Protects muscles in long flat races (all running has some eccentric component)
- Critical for hilly trail races: descending efficiently saves more time than climbing hard
- TSS/TRIMP underestimates the true training stress of downhill running — recovery takes longer than the score suggests

### Eccentric adaptation
- Muscle damage peaks 24–48h after downhill running (DOMS)
- Full recovery: ~14 days after severe downhill effort
- Steeper descents produce disproportionately more DOMS (muscles work at longer lengths)
- Repeated exposure progressively reduces DOMS — the "repeated bout effect"

### Downhill training progression
Progress through stages, each producing mild DOMS that resolves in 1–2 days before advancing:

| Stage | Method | Description |
|---|---|---|
| 1 | Constant pace repeats | Run up and down a 6–8% hill at even pace. Start with ~3km total descent. |
| 2 | Constant effort repeats | Same effort up and down → much faster downhill. Builds downhill-specific strength. |
| 3 | QU4DBUSTER | Push downhill hard (aerobic interval effort), recover on uphill. |
| 4 | Anaerobic QU4DBUSTER | Downhill at anaerobic effort. High injury risk — requires solid foundation. |

**Best option if available:** treadmill descents (set to negative incline) — allows extended downhill without uphill recovery interruption.

### Downhill technique
- **Cadence:** higher than flat — reduces impact, maintains control
- Stay relaxed; tension causes injury on missteps
- Keep hips and back loose
- Remain in control — if flailing, slow down
- Short, quick steps on steep technical terrain (cadence can exceed 120 spm)

### Race strategy for hilly courses
- Running hard uphill and recovering downhill = slower race times
- Running efficiently downhill (controlled, high cadence) saves more time than surging uphill
- Downhill training helps flat ultramarathons too — reduces late-race DOMS and maintains form

### Boston Marathon principle
The difficulty of Boston is not Heartbreak Hill (90m climb) — it's the preceding descents that gradually destroy the quads. Downhill training is the specific preparation.

---

## Injury Prevention

Running injuries are primarily load errors — too much, too fast, too soon.

### Common injury sites

| Injury | Typical cause | Prevention |
|---|---|---|
| Shin splints (MTSS) | Rapid volume increase, hard surfaces | Gradual build, surface variation, calf strength |
| Patellofemoral pain | Weak glutes/quads, overpronation | Glute strengthening, cadence increase |
| Plantar fasciitis | Sudden mileage increase, inadequate footwear | Calf/foot eccentric exercises, gradual build |
| Achilles tendinopathy | Speedwork too early, inadequate recovery | Eccentric heel drops, avoid speed before base |
| IT band syndrome | Rapid hill work increase, weak hip abductors | Hip strengthening, not increasing hills too quickly |
| Stress fractures | Bone loading before structural adaptation | Slow build, adequate calcium/D3, avoid overtraining |

### 10% rule

Do not increase weekly mileage by more than 10% per week. Even more conservative (5–7%) for athletes returning from injury or building from low base.

### Red flags requiring rest/evaluation

- Pain during a run that alters gait → stop immediately
- Joint swelling → rest until resolved
- Night pain → consult a physio
- Pain that worsens with continued running → not "running through" territory

---

## Half Marathon Training Principles

### Target pace setting

Half marathon race pace is typically 3–6% faster than rFTP pace.

At rFTP = 290s/km (4:50/km), HM race pace target ≈ 276s/km (4:36/km). For a sub-1:30 target (4:16/km), rFTP needs to be ~4:28/km (268s/km) or faster.

**Implication:** if current rFTP is 290s/km and goal is 4:16/km HM pace, a significant improvement in threshold pace is required (≈14% faster). This requires sustained threshold development over 12–20 weeks.

### Key session types

| Session | Purpose | Example |
|---|---|---|
| Easy Z2 run | Volume, aerobic base, recovery | 60min at 5:45–6:15/km |
| Long run (Z2) | Endurance, fat oxidation, glycogen capacity | 90–120min at easy pace |
| Tempo (Z3) | Lactate clearance, sustained effort | 20–30min at 5:00–5:20/km |
| Threshold intervals (Z4) | Raise lactate threshold | 3×10min or 2×20min at rFTP pace |
| Race pace intervals (Z5 low) | Neuromuscular specificity, pace economy | 6×1km at goal HM pace |
| VO2max intervals (Z5–Z6) | VO2max ceiling, top-end speed | 5×3–4min at 4:10–4:20/km |

### Pacing strategy for HM race

Even split or slight negative split (second half 1–2% faster) is optimal for most recreational athletes.

**Common mistake:** going out at goal pace feels easy in the first 5km (glycogen-fuelled, adrenaline). The lactic acid cost is front-loaded. Athletes who go 5–10s/km too fast in km 1–7 often fade dramatically in km 14–21.

**Prescription for sub-1:30:** start km 1–5 at 4:20–4:22/km. Settle into 4:16/km for km 5–18. If surplus remains, push to 4:10/km for final 3km.

---

## Stretching for Runners

See `wiki/general/stretching.md` for full protocol. Summary:

- **Pre-run:** dynamic only (leg swings, hip circles, walking lunges) after 5–10 min easy jog. Short SS (≤30s) acceptable if preferred.
- **Post-run:** static stretching (calf, hamstring, hip flexor lunge, figure-4 glute, ITB/TFL) — 60s × 2 per muscle group.
- **Standalone (3×/week):** PNF or 2–3 min holds for chronic tight areas (most runners: hip flexors, calves).

**Key evidence:** Warneke et al. 2025 (meta-analysis, n=181): no stretching type impairs running economy acutely at normal warm-up durations. The old "skip stretching to protect stiffness" advice is not supported. Dynamic stretching (60s/leg) actively improves RE and time-to-exhaustion (Panascì 2024 RCT).

---

## Seitenstechen (Side Stitch)

A sharp, localised pain under the ribcage during running, usually on the right side.

**Mechanism:** likely related to ischaemia of the diaphragm and/or stress on the peritoneal ligaments that support abdominal organs. More common when running with a full stomach or inadequate breathing pattern.

**Prevention:**
- Avoid eating within 2 hours before hard running
- Breathe deeply and rhythmically (in for 3 steps, out for 2)
- Core strength (lateral core stabilisation — side planks, oblique work)
- Gradual warm-up

**During a stitch:** slow down, breathe in on the opposite foot strike to the stitch side, exhale forcefully. Press fingers firmly into the pain site while exhaling. Usually resolves in 1–3 minutes.