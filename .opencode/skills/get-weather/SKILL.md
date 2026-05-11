---
name: get-weather
description: Fetch the MeteoSwiss 7-day weather forecast for a Swiss location and return a structured race-relevant summary. If the forecast is for a race date, update the race card logistics section with the weather details. Switzerland only (MeteoSwiss). Default location: Zürich (PLZ 8001).
compatibility: opencode
---

# Skill: get-weather

## What I do

Fetch the MeteoSwiss 7-day forecast for a Swiss location, format it into a race-relevant summary (temperature, precipitation, wind), and optionally update the race card logistics section if the query is tied to a race event.

---

## Steps

### 1 — Determine location

- If the athlete named a specific location, identify the Ort and PLZ (e.g. "Zürich" → `zuerich/8001`, "Bern" → `bern/3004`, "Rapperswil" → `rapperswil-jona/8640`).
- If no location was given, **default to Zürich (8001)** — but state the assumption and ask if it should be somewhere else.
- Switzerland only. If the athlete asks about a non-Swiss location (e.g. Italy for Stelvio), say: "MeteoSwiss only covers Switzerland. For Stelvio, check meteo.it or yr.no directly."

### 2 — Navigate to MeteoSwiss local forecast

Navigate to the location-specific forecast page:

```
https://www.meteoschweiz.admin.ch/lokalprognose/<ort>/<plz>.html
```

Examples:
- Zürich: `https://www.meteoschweiz.admin.ch/lokalprognose/zuerich/8001.html`
- Bern: `https://www.meteoschweiz.admin.ch/lokalprognose/bern/3004.html`
- Rapperswil-Jona: `https://www.meteoschweiz.admin.ch/lokalprognose/rapperswil-jona/8640.html`

If the page 404s (wrong Ort slug), fall back to the homepage:
```
https://www.meteoschweiz.admin.ch/
```
The homepage snapshot contains the Zürich 7-day text forecast in the `Wetterbericht` section — parse it from there.

### 3 — Take snapshot and parse forecast

Call `chrome-devtools_take_snapshot`. Parse the `Wetterbericht` section (Deutschschweiz tab):

- **Today + up to 6 days** (daily headings: Heute, Dienstag, Mittwoch, …)
- For each day extract:
  - Condition summary (e.g. "stark bewölkt, anhaltender Regen")
  - Max temperature (look for "Niederungen … X Grad" or "Höchsttemperatur um X Grad")
  - Precipitation flag (any mention of Regen, Schauer, Gewitter = yes)
  - Wind note (if "kräftiger", "starker", "Sturmböen" → flag it)

If the snapshot is too long, use `chrome-devtools_take_screenshot` to read the visual layout instead.

### 4 — Format output

Present a compact table:

```
| Tag        | Bedingung                        | Max  | Regen | Wind  |
|------------|----------------------------------|------|-------|-------|
| Mo 11. Mai | stark bewölkt, anhaltender Regen | 15°C | ✓     | SW mäßig |
| Di 12. Mai | sonnig                           | 12°C | —     | NW mäßig |
| ...        | ...                              | ...  | ...   | ...  |
```

Then add **race-relevant flags** as bullet points:

- **Nasse Straßen** (Regen = yes): "Descent km X–Y: nass → kurze Schritte, kein Vertrauen in Kurven."
- **Kalt (<12°C)**: "Muskeln brauchen längeres Warmup. Handschuhe mitbringen."
- **Wind (stark/Sturm)**: "Exponierte Abschnitte (Zürcherstrasse, Gratweg) — Windschatten suchen, Pace-Erwartung anpassen."
- **Gewitter**: "Prüfe race-day ob Start verschoben wird."

### 5 — Link to race (if applicable)

If the weather query is tied to an upcoming race:

1. Call `get_calendar_window` to find events in the next 28 days.
2. If the target date matches a race event, call `get_event_detail(slug)` to get the current logistics payload.
3. Propose an update to the logistics section via `propose_race_logistics`:
   - Add a `weather` field to the logistics notes with the forecast summary and race-relevant flags.
   - Example content:

```json
{
  "weather": {
    "source": "MeteoSwiss",
    "fetched": "2026-05-11",
    "forecast_date": "2026-05-16",
    "condition": "stark bewölkt, einige Niederschläge",
    "max_temp_c": 11,
    "rain": true,
    "wind": "mäßig",
    "race_flags": [
      "Nasse Straßen — Descent km 2–3.6 kurze Schritte",
      "Kalt (11°C) — längeres Warmup, Handschuhe",
      "Hydration: Durstgefühl reduziert bei Kälte — Gel-Plan trotzdem einhalten"
    ]
  }
}
```

4. Show the diff and ask the athlete to confirm.
5. After `apply_race_logistics`, call `bake`.

### 6 — No race match

If no race matches the queried date (or the athlete just asked about general training weather), skip step 5 and deliver only the formatted forecast + race-relevant flags.

---

## URL slug reference (common Swiss locations)

| Location | URL slug |
|---|---|
| Zürich | `zuerich/8001` |
| Bern | `bern/3004` |
| Basel | `basel/4001` |
| Luzern | `luzern/6003` |
| Rapperswil-Jona | `rapperswil-jona/8640` |
| Winterthur | `winterthur/8400` |
| St. Gallen | `st-gallen/9000` |
| Davos | `davos/7270` |
| Andermatt | `andermatt/6490` |
| Zermatt | `zermatt/3920` |

For unlisted locations, try `<lowercase-ort-name>/<plz>`. If it 404s, use the homepage fallback.
