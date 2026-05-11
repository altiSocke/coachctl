---
page_id: 'entity:visibility'
kind: entity
cssclasses:
  - swarmvault
  - sv-entity
title: Visibility
source_class: first_party
tags:
  - entity
  - candidate
source_ids:
  - coachctl-architecture-conventions-8a2f1253
project_ids: []
node_ids:
  - 'entity:visibility'
freshness: fresh
status: candidate
confidence: 0.65
created_at: '2026-05-11T08:45:09.908Z'
updated_at: '2026-05-11T08:45:09.908Z'
compiled_from:
  - coachctl-architecture-conventions-8a2f1253
managed_by: system
backlinks:
  - 'source:coachctl-architecture-conventions-8a2f1253'
schema_hash: 874431dbbfdec0b254a4aa1bf002900574c9b485735a883690c2becb5f717720
source_hashes:
  coachctl-architecture-conventions-8a2f1253: 8a2f1253f49141594869f6e383c7fc66793a5be531cf71c84bd04d41d26b98a5
source_semantic_hashes:
  coachctl-architecture-conventions-8a2f1253: 4640b691098a69816f4ddf9045ff7f8a0fa3148b3658f0c34fce533b4223ab1b
decay_score: 1
last_confirmed_at: '2026-05-11T08:45:13.849Z'
---
# Visibility

## Summary

Named entity mentioned in coachctl — Architecture & Conventions.

## Seen In

- [[sources/coachctl-architecture-conventions-8a2f1253|coachctl — Architecture & Conventions]]

## Source Claims

- --- ## Two-repo split coachctl is published as two coupled repos : | Repo | Visibility | Contents | Watcher | |---|---|---|---| | coachctl (this repo) | public | code, general knowledge, dashboard UI source, public race captures | — | | coachctl-personal (per-athlete) | private | one athlete's wiki, secrets, activities DB, baked dashboard data, Vercel deploy surface | Vercel auto-deploy | Dependency direction is strictly one-way : the private repo depends on the public one via pip install . [source:coachctl-architecture-conventions-8a2f1253]

