---
page_id: 'source:coachctl-architecture-conventions-8a2f1253'
kind: source
cssclasses:
  - swarmvault
  - sv-source
title: coachctl — Architecture & Conventions
source_class: first_party
tags:
  - source
source_ids:
  - coachctl-architecture-conventions-8a2f1253
project_ids: []
node_ids:
  - 'source:coachctl-architecture-conventions-8a2f1253'
  - 'concept:wiki'
  - 'concept:personal'
  - 'concept:repo'
  - 'concept:data'
  - 'concept:athlete'
  - 'concept:coachctl'
  - 'entity:architecture-conventions-canonical'
  - 'entity:two'
  - 'entity:repo'
  - 'entity:visibility'
  - 'entity:contents'
  - 'entity:watcher'
freshness: fresh
status: active
confidence: 1
created_at: '2026-05-11T08:45:09.597Z'
updated_at: '2026-05-11T08:45:09.597Z'
compiled_from:
  - coachctl-architecture-conventions-8a2f1253
managed_by: system
backlinks:
  - 'concept:wiki'
  - 'concept:personal'
  - 'concept:repo'
  - 'concept:data'
  - 'concept:athlete'
  - 'concept:coachctl'
  - 'entity:architecture-conventions-canonical'
  - 'entity:two'
  - 'entity:repo'
  - 'entity:visibility'
  - 'entity:contents'
  - 'entity:watcher'
schema_hash: 874431dbbfdec0b254a4aa1bf002900574c9b485735a883690c2becb5f717720
source_hashes:
  coachctl-architecture-conventions-8a2f1253: 8a2f1253f49141594869f6e383c7fc66793a5be531cf71c84bd04d41d26b98a5
source_semantic_hashes:
  coachctl-architecture-conventions-8a2f1253: 4640b691098a69816f4ddf9045ff7f8a0fa3148b3658f0c34fce533b4223ab1b
decay_score: 1
last_confirmed_at: '2026-05-11T08:45:13.849Z'
---
# coachctl — Architecture & Conventions

Source ID: `coachctl-architecture-conventions-8a2f1253`
Source Kind: `markdown`
Source Path: `C:/Users/tieschy/workspace/coachctl/AGENTS.md`

Source Class: `first_party`


## Summary

coachctl — Architecture & Conventions Canonical reference for the project's structure, knowledge layers, and conventions. README.md owns setup/install/deploy; .opencode/agents/coach.md owns operational workflows. This file is the single source of truth for architecture.

## Concepts

- [[concepts/wiki|wiki]]: Frequently referenced concept in coachctl — Architecture & Conventions.
- [[concepts/personal|personal]]: Frequently referenced concept in coachctl — Architecture & Conventions.
- [[concepts/repo|repo]]: Frequently referenced concept in coachctl — Architecture & Conventions.
- [[concepts/data|data]]: Frequently referenced concept in coachctl — Architecture & Conventions.
- [[concepts/athlete|athlete]]: Frequently referenced concept in coachctl — Architecture & Conventions.
- [[concepts/coachctl|coachctl]]: Frequently referenced concept in coachctl — Architecture & Conventions.

## Entities

- [[entities/architecture-conventions-canonical|Architecture & Conventions Canonical]]: Named entity mentioned in coachctl — Architecture & Conventions.
- [[entities/two|Two-]]: Named entity mentioned in coachctl — Architecture & Conventions.
- [[entities/repo|Repo]]: Named entity mentioned in coachctl — Architecture & Conventions.
- [[entities/visibility|Visibility]]: Named entity mentioned in coachctl — Architecture & Conventions.
- [[entities/contents|Contents]]: Named entity mentioned in coachctl — Architecture & Conventions.
- [[entities/watcher|Watcher]]: Named entity mentioned in coachctl — Architecture & Conventions.

## Claims

- coachctl — Architecture & Conventions Canonical reference for the project's structure, knowledge layers, and conventions. [source:coachctl-architecture-conventions-8a2f1253]
- README.md owns setup/install/deploy; .opencode/agents/coach.md owns operational workflows. [source:coachctl-architecture-conventions-8a2f1253]
- This file is the single source of truth for architecture. [source:coachctl-architecture-conventions-8a2f1253]
- --- ## Two-repo split coachctl is published as two coupled repos : | Repo | Visibility | Contents | Watcher | |---|---|---|---| | coachctl (this repo) | public | code, general knowledge, dashboard UI source, public race captures | — | | coachctl-personal (per-athlete) | private | one athlete's wiki, secrets, activities DB, baked dashboard data, Vercel deploy surface | Vercel auto-deploy | Dependency direction is strictly one-way : the private repo depends on the public one via pip install . [source:coachctl-architecture-conventions-8a2f1253]

## Questions

- How does wiki relate to coachctl — Architecture & Conventions?
- How does personal relate to coachctl — Architecture & Conventions?
- How does repo relate to coachctl — Architecture & Conventions?

