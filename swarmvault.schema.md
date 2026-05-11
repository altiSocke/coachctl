# SwarmVault Schema — coachctl general wiki

This vault holds **athlete-agnostic** endurance coaching knowledge synthesised from
`raw/` source documents. It is the general layer (Layer 2a) of the coachctl
three-layer knowledge architecture. See `AGENTS.md` for the full architecture.

## Boundary rule (strict)

> *If two athletes could share it, it belongs here.*
> *Personal results, personal targets, personal incidents, and anything that names
> a specific athlete do not belong here — they go in the private personal repo.*

When in doubt: **personal wins**. A claim can always be promoted to general later
if it generalises; removing personal data from a public repo is much harder.

## Three-layer architecture

1. **`raw/`** — immutable source documents. Human-write-only. The LLM reads but
   never modifies, renames, or deletes anything here.
2. **`wiki/`** — LLM-maintained synthesis. Every page here is athlete-agnostic.
   The LLM creates, updates, and cross-references pages as new sources arrive.
3. **`swarmvault.schema.md`** (this file) — domain conventions, naming rules,
   grounding requirements. Co-evolved by humans and the LLM.

## Directory conventions

Match the existing layout exactly. Do not create new top-level subdirectories
without updating this schema.

```
wiki/
  <topic>.md           top-level topical pages (cycling, running, nutrition, …)
  races/               course facts, profiles, logistics — no personal targets
    <slug>.md
  recovery/            protocol-level guides
    <slug>.md
  sources/             per-source summary pages synthesised from raw/
    <slug>.md
  outputs/             query results, reports filed back (auto-generated)
  log.md               append-only chronological record of all wiki operations
```

## Page naming

- Use lowercase kebab-case slugs matching the `raw/` source filename where
  applicable (e.g. `raw/races/greifensee_halbmarathon_2026.md` →
  `wiki/races/greifensee_halbmarathon.md`).
- Top-level topical pages use a single noun or short noun phrase
  (`cycling.md`, `nutrition.md`, `strength.md`).
- Source pages mirror the topic they catalogue
  (`sources/nutrition_endurance_elite.md`).

## Categories

Concept categories used during compile and graph clustering:

- `physiology` — exercise physiology, VO2max, lactate, HR zones, power zones
- `training-theory` — periodization, polarized training, load management, ACWR
- `race-courses` — course profiles, elevation data, logistics, climate
- `nutrition-science` — carbohydrate oxidation, hydration, timing, supplements
- `gear` — footwear, clothing, bike fit, equipment selection
- `recovery-protocols` — sleep, massage, sauna, cold exposure, stretching
- `injury-prevention` — biomechanics, strength, mobility, overuse patterns

## Entity types

- **Race** — a named race event with course facts (not an athlete's entry or result)
- **Supplement** — a named product or compound reviewed in the literature
- **GearItem** — a named piece of equipment with evaluated properties
- **BodyStructure** — anatomical structure referenced in injury or physiology pages
- **Technique** — a named training method or drill

## Source page conventions (`wiki/sources/`)

Every page in `wiki/sources/` must include:

- **Title** — author, year, and short descriptor
- **Citation** — full reference (author, title, journal, year, DOI if available)
- **Abstract summary** — 3–5 sentences, grounded in the paper's own content
- **Key findings** — bullet list of claims with supporting data
- **Practical implications** — what this means for endurance athletes in general
- **Limitations** — study population, design weaknesses, generalisability caveats
- **`## Sources` section** — list the `raw/` path(s) this page synthesises

## Race page conventions (`wiki/races/`)

Every page in `wiki/races/` must include (where data is available):

- Distance and total elevation gain/loss
- Key climbs: name, length, average gradient, max gradient
- Surface type(s) and technical character
- Typical weather conditions by season
- Aid station spacing and what is available
- Official cutoff times (if applicable)
- Logistics: start location, parking, bib pickup, bag drop
- `## Sources` section listing raw/ capture files used

**Never include:** athlete-specific targets, predicted times, personal strategy,
or any named athlete's result. Those belong in the personal repo.

## Topical page conventions (`wiki/<topic>.md`)

- Aggregate claims from multiple source pages with citations to `wiki/sources/`.
- Cross-reference related topical pages with plain markdown links.
- Track how understanding has evolved as sources accumulated (note date ranges
  of evidence where relevant).
- Never embed a single athlete's numbers as examples. Use ranges or population
  averages from cited sources.

## Grounding rules

- **Prefer raw sources over summaries.** When a topical page and a source page
  conflict, the raw document is authoritative.
- **Cite source filenames** (`raw/nutrients-17-00918.pdf`) or source page paths
  (`wiki/sources/nutrition_endurance_elite.md`) whenever making specific claims.
- **Flag contradictions** — do not smooth conflicting evidence away. Use a
  `> ⚠ Contradiction:` blockquote to surface conflicts between sources.
- **Preserve uncertainty.** If evidence is weak or mixed, say so explicitly.
- **No speculation** beyond what the cited sources support.

## Relationship types

Used to tag edges in the knowledge graph:

- `Mentions` — page references an entity without detailed analysis
- `Supports` — source supports a claim on a topical page
- `Contradicts` — source contradicts a claim; flag explicitly
- `Builds On` — page extends or updates an earlier source's findings
- `Questions` — source raises doubt about a previously established claim
- `Describes` — race page describes a course entity

## Compile behaviour

- New concepts and entities land in `wiki/candidates/` for review before
  promotion to main wiki pages.
- Use `swarmvault compile --approve` when changes should go through the local
  review queue rather than applying immediately.
- After any `apply_general_wiki_update` via the coachctl MCP, run
  `swarmvault compile` to incorporate the change into the graph and FTS index.

## Rebuild instructions (fresh clone)

The `state/` directory is gitignored. After cloning, rebuild with:

```bash
npm install -g @swarmvaultai/cli   # requires Node >=24, one-time
swarmvault compile                  # builds state/graph.json + state/retrieval/
```

`GITHUB_TOKEN` must be set in the environment (see `.env.example`) for the
`github-models` provider to function. Without it, SwarmVault falls back to the
offline `heuristic` provider automatically — FTS search still works, semantic
synthesis does not.
