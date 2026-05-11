---
page_id: 'concept:wiki'
kind: concept
cssclasses:
  - swarmvault
  - sv-concept
title: wiki
source_class: first_party
tags:
  - concept
  - candidate
source_ids:
  - coachctl-architecture-conventions-8a2f1253
  - >-
    description-swarmvault-graph-first-repository-instructions-alwaysapply-true-8fbb18f6
  - personality-style-a474eea3
  - raw-general-immutable-public-source-documents-1d455c7d
  - swarmvault-rules-7d1dab2a
  - what-i-do-3becbaf3
project_ids: []
node_ids:
  - 'concept:wiki'
freshness: fresh
status: candidate
confidence: 0.95
created_at: '2026-05-11T08:45:09.721Z'
updated_at: '2026-05-11T08:45:09.721Z'
compiled_from:
  - coachctl-architecture-conventions-8a2f1253
  - >-
    description-swarmvault-graph-first-repository-instructions-alwaysapply-true-8fbb18f6
  - personality-style-a474eea3
  - raw-general-immutable-public-source-documents-1d455c7d
  - swarmvault-rules-7d1dab2a
  - what-i-do-3becbaf3
managed_by: system
backlinks:
  - 'source:coachctl-architecture-conventions-8a2f1253'
  - >-
    source:description-swarmvault-graph-first-repository-instructions-alwaysapply-true-8fbb18f6
  - 'source:personality-style-a474eea3'
  - 'source:raw-general-immutable-public-source-documents-1d455c7d'
  - 'source:swarmvault-rules-7d1dab2a'
  - 'source:what-i-do-3becbaf3'
schema_hash: 874431dbbfdec0b254a4aa1bf002900574c9b485735a883690c2becb5f717720
source_hashes:
  coachctl-architecture-conventions-8a2f1253: 8a2f1253f49141594869f6e383c7fc66793a5be531cf71c84bd04d41d26b98a5
  description-swarmvault-graph-first-repository-instructions-alwaysapply-true-8fbb18f6: 8fbb18f69b4c54f078a118042ffe04d94b0344a313c817691a504975fc03f8cf
  personality-style-a474eea3: a474eea3d63fd2f89bf7901594917c5cb8130afdf196e88c2af1e8457a339090
  raw-general-immutable-public-source-documents-1d455c7d: 1d455c7d3ad7b07b2bf4c29250b9c0a07edc764174f0ae05865d04f0df5b0e2f
  swarmvault-rules-7d1dab2a: 7d1dab2ae6ab8a6aa7cd5897211c8f240d4860d04cc6fb58fcdfbd5740040103
  what-i-do-3becbaf3: 3becbaf3e9bee5955df0a2ca432f39e538e321256db56d7399a628aa3193ac86
source_semantic_hashes:
  coachctl-architecture-conventions-8a2f1253: 4640b691098a69816f4ddf9045ff7f8a0fa3148b3658f0c34fce533b4223ab1b
  description-swarmvault-graph-first-repository-instructions-alwaysapply-true-8fbb18f6: 8fbb18f69b4c54f078a118042ffe04d94b0344a313c817691a504975fc03f8cf
  personality-style-a474eea3: e72aeebb5f45a8f0ea3520fb1c3cd536b985a712ab1fb984a474c306fdcac141
  raw-general-immutable-public-source-documents-1d455c7d: 535638b9511f8e5fa85ed534572d1d9646928415b6c6a54bf3e652101070bed4
  swarmvault-rules-7d1dab2a: 6003d063e47e89c5ec8ae9e060cbb4ce971526d5368e0a1912d774eae5142030
  what-i-do-3becbaf3: bee949709918f5b49d6aafdb9307d0c4e98402c0beb63b62cf415bc32f0d3d92
decay_score: 1
last_confirmed_at: '2026-05-11T08:45:13.849Z'
---
# wiki

## Summary

Frequently referenced concept in coachctl — Architecture & Conventions.

## Seen In

- [[sources/coachctl-architecture-conventions-8a2f1253|coachctl — Architecture & Conventions]]
- [[sources/description-swarmvault-graph-first-repository-instructions-alwaysapply-true-8fbb18f6|description: SwarmVault graph-first repository instructions. alwaysApply: true]]
- [[sources/personality-style-a474eea3|Personality & style]]
- [[sources/raw-general-immutable-public-source-documents-1d455c7d|raw/general/ — Immutable public source documents]]
- [[sources/swarmvault-rules-7d1dab2a|SwarmVault Rules]]
- [[sources/what-i-do-3becbaf3|What I do]]

## Source Claims

- --- ## Two-repo split coachctl is published as two coupled repos : | Repo | Visibility | Contents | Watcher | |---|---|---|---| | coachctl (this repo) | public | code, general knowledge, dashboard UI source, public race captures | — | | coachctl-personal (per-athlete) | private | one athlete's wiki, secrets, activities DB, baked dashboard data, Vercel deploy surface | Vercel auto-deploy | Dependency direction is strictly one-way : the private repo depends on the public one via pip install . [source:coachctl-architecture-conventions-8a2f1253]
- raw/general/ — Immutable public source documents This directory holds source material that informs the general wiki layer: peer-reviewed papers, race-website captures, public data exports, course maps. [source:raw-general-immutable-public-source-documents-1d455c7d]
- - Treat `wiki/` as generated markdown owned by the agent and compiler workflow. [source:swarmvault-rules-7d1dab2a]
- description: Ingest a new file from raw/ into the wiki knowledge layers. [source:what-i-do-3becbaf3]
- Encodes the full 7-step read→classify→load→draft→propose→wait→apply workflow including layer boundary rules and wiki target path mapping. [source:what-i-do-3becbaf3]
- ## What I do Guide the full ingestion of a new raw/ source document into the appropriate wiki layer, with correct boundary classification, propose/confirm flow, and audit logging. [source:what-i-do-3becbaf3]

