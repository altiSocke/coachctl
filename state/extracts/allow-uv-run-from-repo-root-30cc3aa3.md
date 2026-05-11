#!/usr/bin/env python
"""
One-shot migration: lift the 2026 race calendar from goals.md +
athlete.yaml into the unified ``events`` table.

Usage:
    uv run python scripts/migrate_races_to_events.py            # dry-run
    uv run python scripts/migrate_races_to_events.py --apply    # write

After applying:
    1. Verify with: get_calendar_window(start='2026-05-01', end='2026-09-30')
    2. Edit per-section content via propose_race_* MCP tools.
    3. Eventually trim athlete.yaml events[] and goals.md race blocks
       (those become slug pointers / narrative only).

Idempotent: re-running with --apply will UPDATE existing rows by slug.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# allow `uv run` from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from coachctl.events import (  # noqa: E402
    Event,
    KIND_RACE,
    empty_race_payload,
    get_event,
    upsert_event,
)


# ── Race definitions ─────────────────────────────────────────────────────────
# Structured payloads transcribed from profile/goals.md +
# profile/athlete.yaml (canonical at migration time).
# Sections left as empty list/dict can be filled via propose_race_* later.


def _race(slug, date, name, priority, summary=None, start_time=None, **payload_overrides) -> Event:
    p = empty_race_payload()
    p["priority"] = priority
    for k, v in payload_overrides.items():
        p[k] = v
    return Event(
        slug=slug,
        kind=KIND_RACE,
        date=date,
        name=name,
        summary=summary,
        start_time=start_time,
        payload=p,
    )


RACES: list[Event] = [
    # ── May 6: Hot Roger (TdU Stage 3) — race effort ──────────────────────
    _race(
        slug="2026-05-06-tdu-hot-roger",
        date="2026-05-06",
        name="TdU Stage 3 — Hot Roger",
        priority="C",
        summary="3.2km / 390m. Scramble race, all-out ~30:00. 10d pre-SOLA — manage quad damage on descent.",
        course={
            "distance_km": 3.2,
            "elevation_m": 390,
            "surface": "trail / scramble",
            "terrain": "wurzel-grat with all-fours sections",
            "notes": "Friends report sections require climbing on all fours.",
        },
        goal={"target_time": "~30:00", "key_metric": "all-out, but protect quads on descent"},
        key_principles=[
            "Effort by breathing/RPE on technical terrain — HR may drop on all-fours sections",
            "Falls are the primary risk",
            "Protect quads on descent — short stride, soft feet",
        ],
        readiness_gate="Skip if legs heavy on warmup. SOLA chip time is the prize.",
    ),
    # ── May 16: SOLA 06 Buchlern → Hönggerberg ────────────────────────────
    _race(
        slug="2026-05-16-sola-06",
        date="2026-05-16",
        name="SOLA 06 — Buchlern → Hönggerberg",
        priority="C",
        summary="10.4km / 234hm. Mostly tarmac (road shoes). Profile: rolling → big descent → neutral zone → monster +133m climb → ETH plateau finish.",
        course={
            "distance_km": 10.4,
            "elevation_m": 234,
            "surface": "tarmac / open terrain (NOT trail)",
            "profile": "rolling +37/−28/+27/−90m descent km 0–3.6 → flat Zürcherstrasse km 3.6–6.5 (timer-neutral) → +133m climb (max 45%) km 6.7–7.9 → undulating ETH plateau to finish",
            "marker_color": "RED jalons (NOT yellow — those are Strecke 2 opposite direction)",
        },
        goal={
            "target_time_raw": "~50–53min",
            "target_time_effective": "~46–49min (after neutral zone)",
            "key_metric": "Recalibrate after Hot Roger May 6",
        },
        key_principles=[
            "Tactical key: Zeitneutralisation km ~3.7–5.5 — timer pauses, drop HR, eat gel",
            "PROTECT QUADS on −90m descent km 2.0–3.6 — short stride, cad 95+",
            "Hitting monster climb at HR 165 vs 188 = ~50s saved",
        ],
        pacing=[
            {
                "section": "Opening climb",
                "km": "0–0.8",
                "hr": "170–175",
                "cue": "Don't sprint exit — 36% grade, short steps",
            },
            {"section": "Rolling", "km": "0.8–2.0", "hr": "≤175", "cue": "Settle, find rhythm"},
            {
                "section": "Big descent",
                "km": "2.0–3.6",
                "hr": "drift down",
                "cue": "PROTECT QUADS — short stride, soft feet, cad 95+, do NOT pound −47% sections",
            },
            {
                "section": "Neutral zone",
                "km": "3.6–5.5",
                "hr": "<150",
                "cue": "Active recovery jog. Eat gel. Shake out. Timer is OFF.",
            },
            {
                "section": "Re-engage",
                "km": "5.5–6.7",
                "hr": "165 ceiling",
                "cue": "Build pace, prep for the monster",
            },
            {
                "section": "Monster climb",
                "km": "6.7–7.9",
                "hr": "178+ → all-out final 200m",
                "cue": "Power-hike 45% sections, hands on knees OK, cad 80+ when running",
            },
            {
                "section": "ETH plateau finish",
                "km": "7.9–10.4",
                "hr": "ceiling lifts",
                "cue": "Hold the highest pace you can — undulating, mostly flat",
            },
        ],
        nutrition={
            "pre_race": "T−10min: 1× MNSTRY 1:0.8 with caffeine (40g, 100mg) — peaks ~30min into race",
            "on_course": "Neutral zone (~km 4.5): 1× MNSTRY 2:1 no-caff (40g) — gut-friendly mid-race carb hit",
            "post": "Water + carbs within 30min",
        },
        kit={
            "shoes": "Road trainers (NOT trail — tarmac-dominant)",
        },
        logistics={
            "start": "Sportanlage Buchlern, Friedhofstrasse 89, 8048 Zürich",
            "clothing_drop": "10:10–12:00 (Hönggerberg destination)",
            "catering": "Buchlern from 07:30 — catering + showers",
        },
    ),
    # ── June 14: Aare Lauf 10k ────────────────────────────────────────────
    _race(
        slug="2026-06-14-aare-10k",
        date="2026-06-14",
        name="Aare Lauf 10k",
        priority="C",
        start_time="09:00",
        summary="Mandatory rFTP gate race for Greifenseelauf calibration. Flat (+30m/-15m), point-to-point Auenstein→Aarau.",
        course={
            "distance_km": 10.0,
            "elevation_m": 30,
            "surface": "asphalt",
            "profile": "flat point-to-point along the Aare",
            "url": "https://aare-halbmarathon.ch/AareLauf10/",
        },
        goal={
            "a": "<43:00 (4:18/km) → push toward 1:32 stretch on Greifensee",
            "b": "43–46:00 → hold 1:35 primary",
            "c": ">46:00 → revise down",
            "key_metric": "rFTP gate for Phase 3 prescription",
        },
        key_principles=[
            "Week 8 recovery week — arrives fresh",
            "Result feeds Phase 3 prescription directly",
        ],
        logistics={
            "start": "Auenstein 09:00",
            "finish": "Aarau AG",
            "transport": "Free public transport with bib (ZVV/A-Welle)",
            "registration_deadline": "2026-06-01",
        },
    ),
    # ── Aug 2: Dillier Classic ────────────────────────────────────────────
    _race(
        slug="2026-08-02-dillier-classic",
        date="2026-08-02",
        name="Dillier Classic",
        priority="B",
        summary="127km / ~2600m. 6 timed climbs aggregate. First year with power meter — pace by power. 2025 lost group at km 88 to quad cramps.",
        course={
            "distance_km": 127,
            "elevation_m": 2600,
            "surface": "road",
            "format": "6 timed climbs, aggregate time = result. Group waits after early climbs but NOT later.",
        },
        goal={
            "target_avg_power": "200W+",
            "target_np": "~220W",
            "target_moving_time": "≤5h05m",
            "key_metric": "Stay with the group past km 88",
        },
        key_principles=[
            "Pace by power, not HR/feel (first year with power meter)",
            "Climbing power cap ≤252W (Z3) on climbs 1-2 — save Z4 for mid-race",
            "Flat/rolling target: 180-210W (Z2)",
            "Aim for negative split on final climb (km 109-112)",
            "Spin 90+ rpm on flats (cramp prevention)",
            "Training: 2-3 rides 4h+ with climbing in 8 weeks pre-race",
            "Training: leg strength 2x/week May–June, taper to 1x/week July",
            "Training: high-cadence drills 3-5 min @ 100-110 rpm, 1-2x per ride",
        ],
        climbs=[
            {
                "n": 1,
                "km": "15–17",
                "gain_m": 170,
                "power_cap": "≤252W (Z3)",
                "hr_cap": 154,
                "notes": "TIMED. LET THE GROUP GO. Save matches. Eat a gel on top. Group waits.",
            },
            {
                "n": 2,
                "km": "20–23",
                "gain_m": 179,
                "power_cap": "≤252W (Z3)",
                "hr_cap": 154,
                "notes": "TIMED. Steady rhythm. Fuel on descent.",
            },
            {
                "n": 3,
                "km": "38–41",
                "gain_m": 174,
                "power_cap": "≤270W (low Z4)",
                "hr_cap": 164,
                "notes": "TIMED. First climb you can push. Controlled effort.",
            },
            {
                "n": 4,
                "km": "48–51",
                "gain_m": 186,
                "power_cap": "≤270W (low Z4)",
                "hr_cap": 164,
                "notes": "TIMED. Long one — start at 240W, build to 270W max in final km.",
            },
            {
                "n": 5,
                "km": "54–55",
                "gain_m": 158,
                "power_cap": "≤260W (Z3-Z4)",
                "hr_cap": 160,
                "notes": "Short but steep. Don't surge — came right after descent.",
            },
            {
                "n": 6,
                "km": "62–65",
                "gain_m": 201,
                "power_cap": "≤280W (Z4)",
                "hr_cap": 167,
                "notes": "TIMED. Biggest climb. This is where you race. Controlled attack.",
            },
            {
                "n": "—",
                "km": "67–88",
                "gain_m": None,
                "power_cap": "180-210W",
                "hr_cap": None,
                "notes": "⚠️ CRITICAL: stay with group. Draft = free watts. Spin 90+ rpm. Cramp danger zone (2025).",
            },
            {
                "n": 7,
                "km": "89–94",
                "gain_m": 216,
                "power_cap": "≤280W (Z4)",
                "hr_cap": None,
                "notes": "TIMED. Longest climb. Start 240W, ramp to 280W. All remaining matches here.",
            },
            {
                "n": 8,
                "km": "109–112",
                "gain_m": 207,
                "power_cap": "SEND IT (≤294W)",
                "hr_cap": None,
                "notes": "Final climb. Empty the tank. Negative split this one.",
            },
        ],
        nutrition={
            "rate": "60-90g carbs/hr from km 0",
            "schedule": "Gel or 30g carbs every 25–30 min from km 0. Don't wait for the stops.",
            "race_week": "Sodium loading 1,500-2,000mg extra/day for 3 days pre-race. Practice race nutrition on final long ride.",
            "race_day_sodium": "500-700mg/L in drink mix; salt capsule every 45-60 min",
        },
        protocols=[
            {
                "title": "Cramp prevention",
                "body": "Cadence ≥90 rpm on flats (esp. km 67-88). Stretch quads on every descent (15-20 sec, drop heels, heel-to-butt). Fuel 60-90g carbs/hr from km 0 (cramp multiplier when depleted).",
            },
            {
                "title": "If overcooked a climb",
                "body": "Drop to ≤154W (Z1) for 5 min after + eat a gel immediately.",
            },
            {
                "title": "If cramps start",
                "body": "Easy gear, high cadence, spin through it. Full cramp: stop 30 sec, stretch, salt capsule, restart at Z2.",
            },
        ],
        yoy={
            "columns": ["Metric", "2024", "2025", "2026 Target"],
            "rows": [
                ["Moving time", "5h14m", "5h10m", "≤5h05m"],
                ["Avg Power", "189W", "196W", "200W+"],
                ["NP", "n/a", "n/a", "~220W"],
                ["Avg HR", "144", "147", "≤145 (better pacing)"],
                ["TSS", "598", "642", "~620 (faster, smarter)"],
                ["Z4+Z5 time", "26.2%", "31.2%", "~28% (more targeted)"],
                ["Km 112 pace", "9:59", "7:55", "≤7:30"],
                ["Power meter", "❌", "❌", "✅"],
                ["Group contact lost", "?", "~km 88 (cramps)", "Past km 103+"],
            ],
        },
    ),
    # ── Aug 29: Stelvio Epic (fun ride) ───────────────────────────────────
    _race(
        slug="2026-08-29-stelvio-epic",
        date="2026-08-29",
        name="Stelvio Epic",
        priority="C",
        summary="Fun ride, ~130km. Stelvio pass. No racing — aerobic/Z2 all day, IF cap 0.70.",
        course={"distance_km": 130, "notes": "Stelvio pass from Pontresina or Val Müstair"},
        goal={"key_metric": "Adventure day, IF cap 0.70"},
        key_principles=[
            "21d before Greifenseelauf — TSB impact negligible",
            "No racing. Fuel well from km 0.",
        ],
    ),
    # ── Sep 6: Albula + Flüela Roundtrip (fun ride) ───────────────────────
    _race(
        slug="2026-09-06-albula-fluela",
        date="2026-09-06",
        name="Albula + Flüela Roundtrip",
        priority="C",
        summary="Fun ride. Social/touring pace only — 13d before Greifenseelauf.",
        course={"notes": "Albula + Flüela passes, comparable to pre-2024 Alpenbrevet prep"},
        goal={"key_metric": "Keep IF below 0.65"},
        key_principles=[
            "13d before Greifenseelauf — TSB on race day virtually unchanged",
            "Legs must arrive at race fresh; save the heroics for Sep 19",
        ],
    ),
    # ── Sep 19: Greifenseelauf — A race ───────────────────────────────────
    _race(
        slug="2026-09-19-greifenseelauf",
        date="2026-09-19",
        name="Greifenseelauf (47th ed.)",
        priority="A",
        summary="HM 21.1km, ~60% asphalt / 40% gravel. Primary 1:35 (4:30/km), stretch 1:32 (4:16/km).",
        course={
            "distance_km": 21.1,
            "surface": "~60% asphalt / 40% gravel",
            "profile": "around Greifensee nature reserve, net chip timing",
            "start": "Seestrasse Uster",
            "finish": "Stadtpark Uster",
        },
        goal={
            "primary_time": "1:35:00",
            "primary_pace": "4:30/km",
            "stretch_time": "1:32:00",
            "stretch_pace": "4:16/km",
            "key_metric": "Stretch only if Jun 14 gate race confirms rFTP < 252s/km",
        },
        key_principles=[
            "20yr floorball base = elite VO2max — economy is the unlock mechanism",
            "Run by HR cap 172 in first half (primary)",
            "Don't skip aid station at km 19.5 (Talacker)",
        ],
        pacing=[
            {
                "section": "Primary 1:35 — opening",
                "km": "0–3",
                "target_pace": "4:35/km",
                "hr_cap": 172,
                "cue": "Conservative start",
            },
            {
                "section": "Primary 1:35 — settle",
                "km": "3–21.1",
                "target_pace": "4:30/km",
                "hr_cap": 172,
                "cue": "Run by HR in first half",
            },
            {
                "section": "Stretch 1:32 — opening",
                "km": "0–3",
                "target_pace": "4:20/km",
                "hr_cap": None,
                "cue": "Only if Jun 14 confirms",
            },
            {
                "section": "Stretch 1:32 — settle",
                "km": "3–21.1",
                "target_pace": "4:16/km",
                "hr_cap": None,
                "cue": "Only if Jun 14 confirms",
            },
        ],
        nutrition={
            "on_course": "Gel at km ~5 (covers to banana station at km 11.5). Take isotonic at each station. Don't skip km 19.5 (Talacker).",
        },
        kit={
            "shoes": "Versatile trainer (not pure road — 40% gravel surface)",
        },
        logistics={
            "bib_pickup": "Stadthalle Uster",
            "gear_drop": "Bag drop with envelope+coupon",
            "transport": "SwissRunners SBB ticket via registration email",
        },
    ),
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="Actually write to DB.")
    args = ap.parse_args()

    print(f"=== {'APPLY' if args.apply else 'DRY-RUN'}: migrate races to events table ===\n")

    created = updated = 0
    for ev in RACES:
        existing = get_event(ev.slug)
        action = "UPDATE" if existing else "CREATE"
        print(f"[{action}] {ev.slug}  ({ev.date} · {ev.name})")
        print(
            f"        priority={ev.payload.get('priority')}  "
            f"sections={[k for k, v in ev.payload.items() if v]}"
        )
        if args.apply:
            upsert_event(ev)
            if existing:
                updated += 1
            else:
                created += 1

    print()
    if args.apply:
        print(f"Done. Created {created}, updated {updated}.")
        print("Next: run `bake` to refresh data.json, then verify on the dashboard.")
    else:
        print("Dry-run complete. Re-run with --apply to write.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
