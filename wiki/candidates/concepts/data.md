---
page_id: 'concept:data'
kind: concept
cssclasses:
  - swarmvault
  - sv-concept
title: data
source_class: first_party
tags:
  - concept
  - candidate
source_ids:
  - coachctl-architecture-conventions-8a2f1253
  - coachctl-strava-training-agent-7a3ae9ac
  - dashboard-ux-audit-8bc8624b
  - personality-style-a474eea3
project_ids: []
node_ids:
  - 'concept:data'
freshness: fresh
status: candidate
confidence: 0.95
created_at: '2026-05-11T08:45:09.723Z'
updated_at: '2026-05-11T08:45:09.723Z'
compiled_from:
  - coachctl-architecture-conventions-8a2f1253
  - coachctl-strava-training-agent-7a3ae9ac
  - dashboard-ux-audit-8bc8624b
  - personality-style-a474eea3
managed_by: system
backlinks:
  - 'source:coachctl-architecture-conventions-8a2f1253'
  - 'source:coachctl-strava-training-agent-7a3ae9ac'
  - 'source:dashboard-ux-audit-8bc8624b'
  - 'source:personality-style-a474eea3'
schema_hash: 874431dbbfdec0b254a4aa1bf002900574c9b485735a883690c2becb5f717720
source_hashes:
  coachctl-architecture-conventions-8a2f1253: 8a2f1253f49141594869f6e383c7fc66793a5be531cf71c84bd04d41d26b98a5
  coachctl-strava-training-agent-7a3ae9ac: 7a3ae9ac2245b81e6b8266fe7349bbaf1bad2a1e4cb89accdef9dcd0dca67412
  dashboard-ux-audit-8bc8624b: 8bc8624bb9f84a4df5c240f788e4e94f1b7a79f6aaf5f970e7f1398611f863ce
  personality-style-a474eea3: a474eea3d63fd2f89bf7901594917c5cb8130afdf196e88c2af1e8457a339090
source_semantic_hashes:
  coachctl-architecture-conventions-8a2f1253: 4640b691098a69816f4ddf9045ff7f8a0fa3148b3658f0c34fce533b4223ab1b
  coachctl-strava-training-agent-7a3ae9ac: 571fd3b7d9213a3df91b8b96fc33f430a32181629f2536f9decd371c91bb8f56
  dashboard-ux-audit-8bc8624b: e456d0303ae5fb91a5c5d400de36a2c481fc93472f5770235b923442b83239ba
  personality-style-a474eea3: e72aeebb5f45a8f0ea3520fb1c3cd536b985a712ab1fb984a474c306fdcac141
decay_score: 1
last_confirmed_at: '2026-05-11T08:45:13.849Z'
---
# data

## Summary

Frequently referenced concept in coachctl — Architecture & Conventions.

## Seen In

- [[sources/coachctl-architecture-conventions-8a2f1253|coachctl — Architecture & Conventions]]
- [[sources/coachctl-strava-training-agent-7a3ae9ac|coachctl — Strava Training Agent]]
- [[sources/dashboard-ux-audit-8bc8624b|Dashboard UX Audit]]
- [[sources/personality-style-a474eea3|Personality & style]]

## Source Claims

- --- ## Two-repo split coachctl is published as two coupled repos : | Repo | Visibility | Contents | Watcher | |---|---|---|---| | coachctl (this repo) | public | code, general knowledge, dashboard UI source, public race captures | — | | coachctl-personal (per-athlete) | private | one athlete's wiki, secrets, activities DB, baked dashboard data, Vercel deploy surface | Vercel auto-deploy | Dependency direction is strictly one-way : the private repo depends on the public one via pip install . [source:coachctl-architecture-conventions-8a2f1253]
- coachctl — Strava Training Agent MCP server + OpenCode agent + dashboard for analysing Strava training data and generating periodized training plans. [source:coachctl-strava-training-agent-7a3ae9ac]
- description: Endurance training coach — analyses Strava data, builds periodized training plans, and tracks long-term athletic development You are an expert endurance coach with deep knowledge of exercise physiology, periodization, and race preparation for running and cycling. [source:personality-style-a474eea3]
- If the data shows accumulated fatigue, you say "you're tired — back off" not "consider managing your load." If a goal is unrealistic, you say so with reasons, not hedges. [source:personality-style-a474eea3]

