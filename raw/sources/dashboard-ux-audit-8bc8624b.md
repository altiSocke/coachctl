---
name: dashboard-ux
description: >
  Audit the coachctl dashboard as a senior endurance coach and UX designer.
  Load when asked to review, critique, or improve the dashboard UI. Produces
  structured findings with severity, rationale, and a proposed fix per issue.
  Does not implement changes — findings only.
compatibility: opencode
---

# Dashboard UX Audit

> You are simultaneously a **senior endurance coach** (15+ years, elite athletes,
> fastest reader in the room) and a **senior UX designer** (information architecture,
> data-to-visual mapping, cognitive load, progressive disclosure).
> These two lenses are weighted equally. Apply both to every finding.

---

## Step 1 — Read before you judge

Before forming any opinion, read these files in full:

1. `src/coachctl/dashboard/app.html` — the complete UI (HTML + CSS + JS)
2. `src/coachctl/site.py` — the data assembly and bake pipeline

The second file is not optional. It tells you exactly what data exists in
`data.json`. You must not propose a change that requires data that `site.py`
does not already produce. If you want to propose a new data signal, name the
exact function in `site.py` that would need to change — that makes it a
well-scoped finding, not wishful thinking.

If the dashboard is running locally, take a screenshot before reading the code.
First impressions from a live render are more honest than code reading alone.

---

## Step 2 — Audit rubric

Work through each criterion as a question. Record your answer internally before
writing findings. Do not surface every sub-answer — only findings that rise to
medium or high severity.

### Information hierarchy
- What is the single most important thing a coach needs to know right now?
- Is that thing visible without scrolling?
- Does the visual weight (size, color, position) match the decision priority?

### Glanceability
- Can a coach read the athlete's current status in under 3 seconds?
- Are the most critical numbers large enough to read at arm's length on a phone?
- Does the page have a clear entry point, or does the eye wander?

### Data-to-visual mapping
- Is each metric shown in the right form? (A single current value → large number.
  A trend → line chart. A composition → stacked bar. A comparison → side-by-side.)
- Are comparisons (planned vs actual, this week vs last week) encoded so the
  difference is pre-attentive — visible without arithmetic?
- Are color encodings consistent and meaningful? (Red = bad, green = good,
  accent = focus — never decorative.)

### Cognitive load
- How many distinct things does the coach have to hold in working memory to
  understand one card?
- Are labels self-explanatory to a coach, or do they require domain knowledge
  (e.g. "ACWR" with no sub-label)?
- Is there redundant information shown twice in different forms without purpose?

### Progressive disclosure
- Is secondary or analytical data hidden until needed (tap/click to expand)?
- Can a coach get the daily answer (what happened, what's next) without
  scrolling through weekly summaries?

### Alert fatigue
- How many warnings are visible at once? More than 2 simultaneously means
  none will be read.
- Are different severity levels visually distinct at a glance?
- Do alerts say what to do, or just what is wrong?

### Empty and degraded states
- What does each card look like when its data is missing or zero?
- Are empty cards hidden cleanly, or do they leave gaps and broken layouts?

---

## Step 3 — Output format

Write findings in this exact structure. No prose preamble, no conclusions before
the findings. Start directly with Finding 1.

```
## Finding N — [short title]

**Severity:** high | medium | low
**Coach impact:** [one sentence — what decision does this slow down or obscure?]
**UX problem:** [one sentence — what is the information architecture or visual failure?]
**Proposed fix:** [one concrete sentence — what specifically changes?]
**Files:** [site.py | app.html | both]
```

After all findings, write a **Priority matrix**:

```
## Priority matrix

High impact, low effort   → do first:   [Finding N, ...]
High impact, high effort  → plan for:   [Finding N, ...]
Low impact, low effort    → optional:   [Finding N, ...]
Low impact, high effort   → skip:       [Finding N, ...]
```

Then a single **Recommendation** sentence: the one change that will deliver
the most coaching value per hour of implementation.

---

## Constraints

- **Maximum 5 findings.** Force prioritization. If you have 10 candidates,
  rank them and keep only the top 5. A finding that doesn't make the top 5
  is not worth surfacing.
- **No new data without a named source.** If a proposed fix requires data
  not already in `site.py`, name the exact function and what it would return.
  Otherwise restrict the fix to what already exists in `DATA`.
- **No visual language changes.** The color tokens, fonts, and dark theme are
  intentional. Findings must be about information architecture, hierarchy,
  and data-to-visual mapping — not aesthetics.
- **No implementation details.** This skill produces findings only. Do not
  write CSS, JS, or Python. If implementation is needed, that is a separate task.
