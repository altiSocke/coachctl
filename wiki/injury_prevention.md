# Injury Prevention — Science Reference

> Personal injury history, current rehabilitation protocols, and individual risk factors live in the personal repo's `profile/`.
> Key sources: Gabbett 2016 (Br J Sports Med — ACWR), Hulin et al. 2016 (Br J Sports Med), Drew & Finch 2016 (Sports Med — 10% rule limitations), Tenforde et al. 2016 (bone stress), Napier & Willy 2018 (running injury review), Meeuwisse 1994 (injury model), Van der Horst et al. 2015 (Nordic hamstring, Am J Sports Med), Petersen et al. 2011 (Am J Sports Med), FIFA 11+ protocol (Soligard et al. 2008, Lancet), Harøy et al. 2019 (Copenhagen adductor, Br J Sports Med), Walker et al. 2021 (return-to-run, Int J Sports Phys Ther), Milewski et al. 2012 (sleep and injury, J Pediatr Orthop).

---

## Load Monitoring and Injury Risk

### The ACWR Framework

The Acute:Chronic Workload Ratio (ACWR) quantifies injury risk by comparing recent load (7-day rolling average) to background load (28-day rolling average). Developed from Gabbett's 2016 synthesis of ~30 professional team sport cohort studies.

```
ACWR = ATL_7day / CTL_28day
```

**Risk zones:**

| ACWR | Zone | Interpretation |
|---|---|---|
| < 0.8 | Undertrained | Deconditioning; relative injury risk increases on return to normal load |
| 0.8–1.3 | Sweet spot | Optimal training stimulus; lowest injury risk in cohort studies |
| 1.3–1.5 | Caution | Elevated injury risk; monitor for early warning signs |
| > 1.5 | High risk | Spike zone; 2–3× injury rate vs sweet spot in elite football and cricket data (Hulin et al. 2016) |

**Critical nuance — not a hard threshold.** The ACWR predicts risk at a population level; an individual athlete at 1.6 is not guaranteed injury, and an athlete at 0.9 can be injured. The ACWR is most useful as a *trend signal*: a rising ACWR combined with poor sleep, high RPE, and decreasing HRV is a clear danger composite. An isolated ACWR spike with all other markers green is lower risk.

**The spike, not the sustained level, is the danger.** A well-conditioned athlete who has trained at ACWR 1.4–1.5 for months is at lower risk than an athlete whose ACWR jumps from 0.8 to 1.5 in one week.

### The 10% Rule — Evidence and Limitations

The widely-cited "increase mileage by no more than 10% per week" rule has a weaker evidence base than commonly assumed. Drew & Finch (2016) (*Sports Med*) reviewed the literature and found:
- No prospective RCT has validated 10% as an optimal threshold
- The rule applies to absolute load increases; it ignores the athlete's training history and fitness base
- A 10% increase from a low base is safer than 10% from an already high base
- Running economy and connective tissue adaptation are better predicted by chronic load history (CTL/ATL model) than by weekly percentage increases

**More useful rules:**
1. Keep ACWR in the 0.8–1.3 zone
2. Limit CTL ramp rate to ≤5–8 TSS/week for sustained build phases (see `wiki/training_principles.md`)
3. After any training interruption ≥1 week, return at ≤60% of pre-interruption weekly volume

### Absolute Load Thresholds (Running)

Observational cohort data from recreational runners suggests risk inflection points:
- Runners averaging **>64 km/week** (40 miles) have higher injury rates than those at <48 km/week — but this is confounded by training history; well-conditioned runners tolerate higher volumes
- Sudden increases of **>30%** in any week compared to the 4-week average are a reliable injury signal regardless of base
- Bone stress injuries cluster in the 6–8 week window after a significant load increase — the lag reflects bone remodelling timescales

---

## Running Injuries

### Bone Stress Injuries (BSI)

**Definition:** A spectrum from bone stress reaction (periosteal oedema) to complete stress fracture. Common sites: tibia (50%), metatarsals, femur, calcaneus.

**Causes and risk factors:**
- Rapid load increase (ACWR >1.5; volume jump >25%)
- Low energy availability / RED-S (Relative Energy Deficiency in Sport) — the single strongest modifiable risk factor
- Low bone mineral density (female athletes, vitamin D deficiency, inadequate calcium)
- High training monotony — repetitive loading without recovery days
- Hard surfaces combined with shoe mileage >800 km

**Prevention:**
- Progressive load introduction (see ACWR rules above)
- Adequate energy intake — bone stress injuries are the sentinel injury for RED-S; any athlete with recurrent BSI should be evaluated for energy deficiency
- Strength training: progressive resistance training increases bone density and cortical thickness
- Calcium 1000–1500 mg/day + vitamin D 2000–4000 IU/day for athletes training >10h/week
- Shoe rotation (varied midsole geometry changes impact distribution)

**Warning signs:** localised bone pain that worsens with loading and is point-tender on palpation. Unlike soft tissue injuries, BSI pain typically does not warm up. Requires imaging (MRI preferred) and medical clearance before return to running.

### IT Band Syndrome (ITBS)

**Mechanism:** Friction of the iliotibial band over the lateral femoral epicondyle during the knee flexion arc (30–35°) — typically at initial contact. Compression model (Van der Worp et al. 2012): the ITB compresses the highly innervated fat pad beneath it rather than causing friction.

**Risk factors:** Rapid mileage increase, downhill running, hip abductor weakness, varus knee alignment, worn footwear.

**Prevention and management:**
- Hip abductor strengthening (clamshell, side-lying abduction, single-leg squat) — the most consistent intervention
- Reduce downhill running and camber during acute phases
- Foam rolling the ITB reduces symptoms but does not address the underlying cause; combine with hip strengthening
- Running cadence increase of 5–10% reduces knee flexion range at foot contact, moving contact away from the compression arc

### Patellofemoral Pain Syndrome (PFPS)

**Mechanism:** Pain arising from the patellofemoral joint — attributed to altered patellar tracking, cartilage stress, and subchondral bone loading. Running with excessive hip adduction (hip drop) increases lateral patellar tilt and compression.

**Risk factors:** Weak hip abductors/external rotators (allowing hip adduction during stance), high patella, female sex (wider Q-angle), rapid volume increases.

**Prevention:**
- Hip abductor and external rotator strengthening (as for ITBS; the two conditions share a root cause)
- Single-leg squat training — identifies and corrects hip drop
- Gradual load introduction; avoid sudden increases in hill work or stair training
- Temporary reduction in running volume and step rate increase (reduces ground reaction force) during symptomatic phase

### Achilles Tendinopathy

**Mechanism:** Degenerative changes in tendon collagen microstructure from accumulated load exceeding repair capacity. Most common at the mid-tendon (2–6 cm above insertion) and insertional zones.

**Risk factors:** Sudden mileage increase, inadequate calf strength, prior Achilles injury, fluoroquinolone antibiotics (collagen toxicity), rapid transition to minimalist footwear.

**Prevention (Baar 2017; Cook & Purdam 2009):**
- Progressive calf loading: eccentric calf raises → heavy slow resistance (bent and straight knee) → explosive loading
- Avoid sudden mileage spikes — the tendon's collagen remodelling cycle takes 60–90 days; acute overload outpaces repair capacity
- Running volume ramp consistent with ACWR guidelines
- Morning stiffness that resolves in <20 min with warm-up: manageable with load modification. Morning stiffness lasting >45 min or pain that worsens during a run: reduce load and seek assessment.

**Alfredson's eccentric protocol (first-line evidence-based treatment):**
- Straight-knee calf raise eccentric: 3×15, twice daily, over 12 weeks
- Bent-knee (soleus-focused): same protocol
- This strengthens both gastrocnemius and soleus, thickens the tendon, and stimulates collagen synthesis

### Plantar Fasciitis

**Mechanism:** Degenerative changes at the plantar fascia origin (calcaneal insertion), typically from repetitive tensile overload.

**Risk factors:** High training volume, limited ankle dorsiflexion, high or low arch, overweight, sudden volume increase, hard surfaces.

**Prevention and management:**
- Calf stretching (both gastrocnemius and soleus) to improve ankle dorsiflexion
- Intrinsic foot strengthening (short foot exercise, towel scrunches)
- Load reduction + gradual reintroduction; first-step morning pain is the reliable marker of overload
- Plantar fascia-specific stretching (foot dorsiflexion + toe extension for 30s, 10 reps before first steps each morning) — Digiovanni et al. (2003) showed superior outcomes vs. Achilles stretching alone

---

## Cycling Injuries

Cycling injuries are predominantly overuse — the fixed, repetitive mechanics of pedalling make bike fit the primary preventive lever.

### Saddle Height

The most common source of overuse injury in cyclists. Both too high and too low cause problems:

| Saddle height | Injury mechanism |
|---|---|
| **Too high** | Excessive knee extension at bottom of stroke; Achilles and IT band stress; hip rocking → lumbar pain |
| **Too low** | Excessive knee flexion; patellofemoral compression; anterior knee pain |

**Optimal saddle height (LeMond method):** inseam × 0.883 = saddle height from centre of bottom bracket to top of saddle. Fine-tune by feel — heel should lightly brush the pedal at 6 o'clock with the leg almost fully extended.

### IT Band Friction Syndrome (Cycling)

Less common than in running; caused by saddle too high (hip rocking) or cleat misalignment. Same hip abductor strengthening approach as in running; cleat toe-out adjustment often resolves lateral knee pain.

### Patellar Tendinopathy

Associated with high force production in big gears at low cadence (high muscular loading per pedal stroke). Prevention: avoid sustained low-cadence grinding climbs before adequate conditioning; perform eccentric quad loading (decline squat, reverse nordic) as preventive strength work.

### Cleat Alignment

Rotational misalignment of cleats forces the knee to deviate medially or laterally through each pedal stroke. Even 3–4° of misalignment accumulates over 5000+ pedal strokes per hour into significant stress.
- Allow 2–4° of float in cleats to accommodate natural variation in knee tracking
- Shims under cleats for leg length discrepancy >5mm

### Lower Back Pain

Common in cyclists, especially on long climbs with sustained hip flexion. Primary causes: insufficient hip flexor flexibility, excessive anterior pelvic tilt, saddle fore-aft position too far forward. Prevention: hip flexor stretching, core stability work (plank, bird-dog), bike fit review.

---

## Team Sport Injuries

### Ankle Sprains

The most common team sport injury across all field sports. Lateral ankle sprains (anterior talofibular ligament) account for ~80%.

**Prevention — balance and proprioception training:**
- Single-leg balance and perturbation training reduces lateral ankle sprain incidence by ~35–50% in RCTs (McKeon & Hertel 2008, meta-analysis)
- Balance board, single-leg stance on unstable surfaces, jump-landing technique
- Ankle bracing or taping reduces recurrence in athletes with prior sprains (40–70% reduction in RCT data), but does not address the underlying neuromuscular deficit

**FIFA 11+ (Soligard et al. 2008, *Lancet*):**
The FIFA 11+ warmup protocol — 15 minutes of running drills, strength, balance, and plyometric exercises — reduced overall injury rates by **11–12%** and severe injuries by **17%** in amateur football. Ankle sprains, knee injuries, and hamstring strains all reduced. The protocol takes 15–20 min to execute. Implementation fidelity is the primary variable — teams that fully comply achieve the stated benefits; partial compliance yields negligible results.

### ACL Injuries

Non-contact ACL injuries (cutting, deceleration, landing) are preventable via neuromuscular training.

**FIFA 11+ evidence:** Soligard et al. (2008) showed significant ACL injury reduction in a cluster RCT of 1892 amateur female football players. Systematic reviews of neuromuscular warmup programs show 50–70% ACL injury reduction in female athletes; ~30–40% in male athletes (Mandelbaum et al. 2005; Hewett et al. 1999).

**Mechanism:** Landing and deceleration technique training reduces knee valgus collapse — the primary injury mechanism. Hip abductor and external rotator strength (the same muscles targeted for running injury prevention) are central to ACL stability.

### Hamstring Strains

**Most common soft tissue injury in sprint-dominant team sports.** Mechanism: maximal eccentric loading in late swing phase when the hamstring decelerates thigh flexion.

**Nordic hamstring curl — evidence for team sports:**
- Van der Horst et al. 2015: **65% reduction** in amateur football
- Petersen et al. 2011: **60% total reduction, 85% recurrence reduction** in Danish football
- Full evidence base covered in `wiki/strength.md`

**Risk factors:** Prior hamstring strain (the single strongest predictor — recurrence risk is 2–3× baseline), short biceps femoris fascicle length, inadequate warm-up at high speeds, fatigue.

**Pre-match screening:** athletes with prior hamstring strain should be screened with the single-leg hamstring bridge or isometric test. Asymmetry >15% vs. contralateral limb is a return-to-play risk flag.

### Groin and Adductor Injuries

Common in skating-stride and lateral-cutting sports (floorball, ice hockey, football).

**Copenhagen adductor exercise — evidence:**
Harøy et al. (2019) (*Br J Sports Med*): **46% reduction** in adductor muscle injuries in elite football with 2×/week in-season protocol. Full protocol description in `wiki/strength.md`.

**Hip flexor strengthening** (lunge matrix, hip flexor isometric holds) is complementary — hip flexor injuries and adductor injuries often co-occur in high-velocity cutting sports.

---

## Return-to-Run Protocol

### When to Begin

Return to running is appropriate when:
1. Walking is pain-free at normal pace
2. Single-leg calf raise (20 reps) and single-leg squat are pain-free
3. No limping during daily activities
4. For bone stress injuries: radiological evidence of healing AND medical clearance

**Do not return to running if any of the above are not met** — early return before these criteria prolong total recovery time more than the delay.

### Walk-Run Ladder (Standard Progressive Protocol)

Based on Walker et al. (2021) and the Couch-to-5K template adapted for injury return. Start at Level 1 if any pain during walking. Start at Level 3 if walking is fully pain-free and 2 weeks post-injury.

All sessions performed on flat, forgiving surface (grass or track). Session frequency: 3×/week (rest days between). Progress to the next level only when the current level is pain-free throughout AND 24h post-session.

| Level | Session Structure | Total Time |
|---|---|---|
| 1 | Walk 5 min × 4 | 20 min |
| 2 | Walk 7 min / jog 1 min × 3 | 24 min |
| 3 | Walk 5 min / jog 2 min × 3 | 21 min |
| 4 | Walk 3 min / jog 3 min × 4 | 24 min |
| 5 | Walk 2 min / jog 5 min × 4 | 28 min |
| 6 | Walk 1 min / jog 8 min × 3 | 27 min |
| 7 | Continuous jog 20 min | 20 min |
| 8 | Continuous jog 25 min | 25 min |
| 9 | Continuous jog 30 min | 30 min |

**After Level 9 is achieved:** return to normal training structure starting at ≤60% of pre-injury weekly TSS. Keep ACWR ≤1.0 for the first 3–4 weeks post-return.

### Return-to-Sport Protocol (Team Sports)

For team sport athletes returning from lower-limb injury (ligament, muscle, bone):

1. **Phase 1 — Low-intensity, straight-line jogging** (Levels 1–7 above, no cutting)
2. **Phase 2 — Running with change of direction** at low speed; no reactive or contact drill
3. **Phase 3 — Sport-specific agility drills** (planned, controlled patterns)
4. **Phase 4 — Reactive agility and contact** (unpredictable movement; light contact)
5. **Phase 5 — Full training participation** (team session without restriction)
6. **Phase 6 — Return to match play**

Progress one phase per week minimum. Regression criteria: any pain, limping, or swelling at or after a session = return to previous phase.

**ACL-specific return-to-sport:** minimum 9 months post-ACL reconstruction before return to competitive match play (van Melick et al. 2016 evidence-based guidelines). Psychological readiness (ACL-RSI questionnaire) is an independent predictor of re-injury and should be assessed.

### Red Flags — Seek Medical Assessment

- **Point-tender bone pain** that does not warm up: possible stress fracture — stop running; MRI/bone scan required
- **Joint swelling** (effusion) within 24h of activity: intra-articular injury
- **Neurological symptoms** (numbness, tingling, weakness distal to injury): nerve involvement
- **Bilateral leg symptoms** in a runner: consider spinal or vascular cause
- **Fever + joint pain**: exclude septic joint (medical emergency)
- **Achilles tendon snap felt or heard + inability to plantarflex**: complete Achilles tendon rupture — surgical emergency

---

## Sleep and Injury Risk

Sleep deprivation is an independent and underappreciated injury risk factor.

**Milewski et al. (2012)** (*J Pediatr Orthop*): Young athletes sleeping <8 hours/night were **1.7× more likely** to sustain an injury than those sleeping ≥8 hours, after controlling for hours of sport participation. The association held across sport types.

**Mechanisms:**
- Sleep deprivation impairs motor accuracy, reaction time, and neuromuscular control — direct injury risk
- Cortisol elevation with poor sleep blunts tendon and bone collagen synthesis (Baar 2017)
- Immune suppression from chronic sleep restriction impairs soft tissue repair
- Decision-making degradation → risky play and inadequate warmup choices

**Practical rule:** an athlete with ≥2 consecutive nights of <6h sleep should reduce session intensity and skip high-risk training (plyometrics, max-effort sprints, heavy single-leg work) until sleep recovers. Full recovery of neuromuscular performance typically requires 2–3 nights of normal sleep (7–9h).

---

## Strength Training as Injury Prevention — Summary

The overlap between the strength training and injury prevention evidence bases is substantial. The following is a priority summary for athletes with limited time:

| Injury target | Key exercise(s) | Frequency | Evidence level |
|---|---|---|---|
| Hamstring strain (team sport) | Nordic hamstring curl | 3×/week pre-season, 1×/week in-season | High (multiple RCTs) |
| Groin/adductor (team sport) | Copenhagen adductor exercise | 2×/week | Moderate (1 RCT, elite football) |
| Knee valgus / ACL / PFPS | Single-leg squat, hip abductor work | 2×/week | Moderate–high |
| Achilles tendinopathy | Heavy slow resistance calf raises (straight + bent knee) | 2–3×/week | High (Alfredson protocol) |
| IT band syndrome | Hip abductor strengthening | 2×/week | Moderate |
| Bone stress injury | Progressive resistance training (general lower body) | 2×/week | Moderate |
| Ankle sprain recurrence | Single-leg balance + proprioception | 2×/week or daily | Moderate |

---

## Sources

- Gabbett 2016 — *Br J Sports Med* — ACWR framework; risk zones from ~30 cohort studies
- Hulin et al. 2016 — *Br J Sports Med* — ACWR 1.5 spike zone; 2–3× injury rate in cricket and football
- Drew & Finch 2016 — *Sports Med* — 10% rule limitations; lack of RCT evidence
- Tenforde et al. 2016 — *Br J Sports Med* — bone stress injuries: RED-S link, female athlete risk
- Van der Worp et al. 2012 — *Br J Sports Med* — ITBS compression model review
- Digiovanni et al. 2003 — *J Bone Joint Surg* — plantar fascia-specific stretching RCT
- Baar 2017 — *Sports Med* (PMC5371618) — tendon loading protocols; sleep + cortisol + collagen synthesis
- Cook & Purdam 2009 — *Br J Sports Med* — tendinopathy continuum model; load management
- Soligard et al. 2008 — *Lancet* — FIFA 11+ RCT; 11% injury reduction; 1892 female amateur footballers
- McKeon & Hertel 2008 — meta-analysis — balance training for ankle sprain prevention
- Van der Horst et al. 2015 — *Am J Sports Med* — Nordic hamstring: 65% reduction in football
- Petersen et al. 2011 — *Am J Sports Med* — Nordic hamstring: 60% total, 85% recurrent injury reduction
- Harøy et al. 2019 — *Br J Sports Med* — Copenhagen adductor: 46% groin injury reduction
- van Melick et al. 2016 — *Br J Sports Med* — ACL return-to-sport: minimum 9 months post-reconstruction
- Walker et al. 2021 — *Int J Sports Phys Ther* — return-to-run progressive protocol guidelines
- Milewski et al. 2012 — *J Pediatr Orthop* — sleep <8h → 1.7× injury risk in youth athletes
