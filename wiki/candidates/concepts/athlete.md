---
page_id: 'concept:athlete'
kind: concept
cssclasses:
  - swarmvault
  - sv-concept
title: athlete
source_class: first_party
tags:
  - concept
  - candidate
source_ids:
  - athlete-profile-eed5f509
  - coachctl-architecture-conventions-8a2f1253
  - personality-style-a474eea3
  - what-i-do-3becbaf3
  - what-i-do-a929e628
project_ids: []
node_ids:
  - 'concept:athlete'
freshness: fresh
status: candidate
confidence: 0.95
created_at: '2026-05-11T08:45:09.713Z'
updated_at: '2026-05-11T08:45:09.713Z'
compiled_from:
  - athlete-profile-eed5f509
  - coachctl-architecture-conventions-8a2f1253
  - personality-style-a474eea3
  - what-i-do-3becbaf3
  - what-i-do-a929e628
managed_by: system
backlinks:
  - 'source:athlete-profile-eed5f509'
  - 'source:coachctl-architecture-conventions-8a2f1253'
  - 'source:personality-style-a474eea3'
  - 'source:what-i-do-3becbaf3'
  - 'source:what-i-do-a929e628'
schema_hash: 874431dbbfdec0b254a4aa1bf002900574c9b485735a883690c2becb5f717720
source_hashes:
  athlete-profile-eed5f509: eed5f509845efbde460789c01d0e31f58c436420d254059ff62db613ba08949b
  coachctl-architecture-conventions-8a2f1253: 8a2f1253f49141594869f6e383c7fc66793a5be531cf71c84bd04d41d26b98a5
  personality-style-a474eea3: a474eea3d63fd2f89bf7901594917c5cb8130afdf196e88c2af1e8457a339090
  what-i-do-3becbaf3: 3becbaf3e9bee5955df0a2ca432f39e538e321256db56d7399a628aa3193ac86
  what-i-do-a929e628: a929e62826769be5ad430b6c2d6a0e0ca27ab0872066c1c5175099052367fcb3
source_semantic_hashes:
  athlete-profile-eed5f509: eed5f509845efbde460789c01d0e31f58c436420d254059ff62db613ba08949b
  coachctl-architecture-conventions-8a2f1253: 4640b691098a69816f4ddf9045ff7f8a0fa3148b3658f0c34fce533b4223ab1b
  personality-style-a474eea3: e72aeebb5f45a8f0ea3520fb1c3cd536b985a712ab1fb984a474c306fdcac141
  what-i-do-3becbaf3: bee949709918f5b49d6aafdb9307d0c4e98402c0beb63b62cf415bc32f0d3d92
  what-i-do-a929e628: ae7c4c220c832d699e5805d0fb61d507ebf1faabf675f1287863195942e86654
decay_score: 1
last_confirmed_at: '2026-05-11T08:45:13.849Z'
---
# athlete

## Summary

Frequently referenced concept in ── Athlete Profile ────────────────────────────────────.

## Seen In

- [[sources/athlete-profile-eed5f509|── Athlete Profile ────────────────────────────────────]]
- [[sources/coachctl-architecture-conventions-8a2f1253|coachctl — Architecture & Conventions]]
- [[sources/personality-style-a474eea3|Personality & style]]
- [[sources/what-i-do-3becbaf3|What I do]]
- [[sources/what-i-do-a929e628|What I do]]

## Source Claims

- ── Athlete Profile ──────────────────────────────────── # Example template. [source:athlete-profile-eed5f509]
- --- ## Two-repo split coachctl is published as two coupled repos : | Repo | Visibility | Contents | Watcher | |---|---|---|---| | coachctl (this repo) | public | code, general knowledge, dashboard UI source, public race captures | — | | coachctl-personal (per-athlete) | private | one athlete's wiki, secrets, activities DB, baked dashboard data, Vercel deploy surface | Vercel auto-deploy | Dependency direction is strictly one-way : the private repo depends on the public one via pip install . [source:coachctl-architecture-conventions-8a2f1253]
- Use when the athlete points you at a new file they have added to raw/ (papers, race captures, GPX, scans). [source:what-i-do-3becbaf3]
- Load when the athlete asks to set up a race, fill in race strategy, review a race plan, or edit any section of a race card (pacing, nutrition, climbs, logistics, kit, warmup, protocols, YoY, readiness gate). [source:what-i-do-a929e628]

