---
page_id: 'concept:repo'
kind: concept
cssclasses:
  - swarmvault
  - sv-concept
title: repo
source_class: first_party
tags:
  - concept
  - candidate
source_ids:
  - coachctl-architecture-conventions-8a2f1253
  - coachctl-strava-training-agent-7a3ae9ac
project_ids: []
node_ids:
  - 'concept:repo'
freshness: fresh
status: candidate
confidence: 0.8
created_at: '2026-05-11T08:45:09.722Z'
updated_at: '2026-05-11T08:45:09.722Z'
compiled_from:
  - coachctl-architecture-conventions-8a2f1253
  - coachctl-strava-training-agent-7a3ae9ac
managed_by: system
backlinks:
  - 'source:coachctl-architecture-conventions-8a2f1253'
  - 'source:coachctl-strava-training-agent-7a3ae9ac'
schema_hash: 874431dbbfdec0b254a4aa1bf002900574c9b485735a883690c2becb5f717720
source_hashes:
  coachctl-architecture-conventions-8a2f1253: 8a2f1253f49141594869f6e383c7fc66793a5be531cf71c84bd04d41d26b98a5
  coachctl-strava-training-agent-7a3ae9ac: 7a3ae9ac2245b81e6b8266fe7349bbaf1bad2a1e4cb89accdef9dcd0dca67412
source_semantic_hashes:
  coachctl-architecture-conventions-8a2f1253: 4640b691098a69816f4ddf9045ff7f8a0fa3148b3658f0c34fce533b4223ab1b
  coachctl-strava-training-agent-7a3ae9ac: 571fd3b7d9213a3df91b8b96fc33f430a32181629f2536f9decd371c91bb8f56
decay_score: 1
last_confirmed_at: '2026-05-11T08:45:13.849Z'
---
# repo

## Summary

Frequently referenced concept in coachctl — Architecture & Conventions.

## Seen In

- [[sources/coachctl-architecture-conventions-8a2f1253|coachctl — Architecture & Conventions]]
- [[sources/coachctl-strava-training-agent-7a3ae9ac|coachctl — Strava Training Agent]]

## Source Claims

- --- ## Two-repo split coachctl is published as two coupled repos : | Repo | Visibility | Contents | Watcher | |---|---|---|---| | coachctl (this repo) | public | code, general knowledge, dashboard UI source, public race captures | — | | coachctl-personal (per-athlete) | private | one athlete's wiki, secrets, activities DB, baked dashboard data, Vercel deploy surface | Vercel auto-deploy | Dependency direction is strictly one-way : the private repo depends on the public one via pip install . [source:coachctl-architecture-conventions-8a2f1253]

