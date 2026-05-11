---
page_id: 'concept:personal'
kind: concept
cssclasses:
  - swarmvault
  - sv-concept
title: personal
source_class: first_party
tags:
  - concept
  - candidate
source_ids:
  - coachctl-architecture-conventions-8a2f1253
  - coachctl-strava-training-agent-7a3ae9ac
  - >-
    opencode-local-config-contains-live-api-tokens-use-opencode-json-example-as-temp-fe834141
  - what-i-do-3becbaf3
  - what-i-do-a929e628
project_ids: []
node_ids:
  - 'concept:personal'
freshness: fresh
status: candidate
confidence: 0.95
created_at: '2026-05-11T08:45:09.721Z'
updated_at: '2026-05-11T08:45:09.721Z'
compiled_from:
  - coachctl-architecture-conventions-8a2f1253
  - coachctl-strava-training-agent-7a3ae9ac
  - >-
    opencode-local-config-contains-live-api-tokens-use-opencode-json-example-as-temp-fe834141
  - what-i-do-3becbaf3
  - what-i-do-a929e628
managed_by: system
backlinks:
  - 'source:coachctl-architecture-conventions-8a2f1253'
  - 'source:coachctl-strava-training-agent-7a3ae9ac'
  - >-
    source:opencode-local-config-contains-live-api-tokens-use-opencode-json-example-as-temp-fe834141
  - 'source:what-i-do-3becbaf3'
  - 'source:what-i-do-a929e628'
schema_hash: 874431dbbfdec0b254a4aa1bf002900574c9b485735a883690c2becb5f717720
source_hashes:
  coachctl-architecture-conventions-8a2f1253: 8a2f1253f49141594869f6e383c7fc66793a5be531cf71c84bd04d41d26b98a5
  coachctl-strava-training-agent-7a3ae9ac: 7a3ae9ac2245b81e6b8266fe7349bbaf1bad2a1e4cb89accdef9dcd0dca67412
  opencode-local-config-contains-live-api-tokens-use-opencode-json-example-as-temp-fe834141: fe83414169764eed83893678b9d39ddbad1ca33ef9b7676514761226e5e6aee5
  what-i-do-3becbaf3: 3becbaf3e9bee5955df0a2ca432f39e538e321256db56d7399a628aa3193ac86
  what-i-do-a929e628: a929e62826769be5ad430b6c2d6a0e0ca27ab0872066c1c5175099052367fcb3
source_semantic_hashes:
  coachctl-architecture-conventions-8a2f1253: 4640b691098a69816f4ddf9045ff7f8a0fa3148b3658f0c34fce533b4223ab1b
  coachctl-strava-training-agent-7a3ae9ac: 571fd3b7d9213a3df91b8b96fc33f430a32181629f2536f9decd371c91bb8f56
  opencode-local-config-contains-live-api-tokens-use-opencode-json-example-as-temp-fe834141: fe83414169764eed83893678b9d39ddbad1ca33ef9b7676514761226e5e6aee5
  what-i-do-3becbaf3: bee949709918f5b49d6aafdb9307d0c4e98402c0beb63b62cf415bc32f0d3d92
  what-i-do-a929e628: ae7c4c220c832d699e5805d0fb61d507ebf1faabf675f1287863195942e86654
decay_score: 1
last_confirmed_at: '2026-05-11T08:45:13.849Z'
---
# personal

## Summary

Frequently referenced concept in coachctl — Architecture & Conventions.

## Seen In

- [[sources/coachctl-architecture-conventions-8a2f1253|coachctl — Architecture & Conventions]]
- [[sources/coachctl-strava-training-agent-7a3ae9ac|coachctl — Strava Training Agent]]
- [[sources/opencode-local-config-contains-live-api-tokens-use-opencode-json-example-as-temp-fe834141|opencode local config — contains live API tokens; use opencode.json.example as template]]
- [[sources/what-i-do-3becbaf3|What I do]]
- [[sources/what-i-do-a929e628|What I do]]

## Source Claims

- --- ## Two-repo split coachctl is published as two coupled repos : | Repo | Visibility | Contents | Watcher | |---|---|---|---| | coachctl (this repo) | public | code, general knowledge, dashboard UI source, public race captures | — | | coachctl-personal (per-athlete) | private | one athlete's wiki, secrets, activities DB, baked dashboard data, Vercel deploy surface | Vercel auto-deploy | Dependency direction is strictly one-way : the private repo depends on the public one via pip install . [source:coachctl-architecture-conventions-8a2f1253]
- .env pycache / *.pyc .ruff_cache/ .venv/ dist/ *.egg-info/ # opencode local config — contains live API tokens; use opencode.json.example as template opencode.json # Editor / IDE state .obsidian/ .idea/ *.code-workspace # Defensive — these directories belong in the personal repo, never here wiki/personal/ data/ config/profiles/ profile/ [source:opencode-local-config-contains-live-api-tokens-use-opencode-json-example-as-temp-fe834141]
- Encodes the full section-by-section propose/confirm/apply flow and general-vs-personal boundary rules. [source:what-i-do-a929e628]

