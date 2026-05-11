---
page_id: 'concept:local'
kind: concept
cssclasses:
  - swarmvault
  - sv-concept
title: local
source_class: first_party
tags:
  - concept
  - candidate
source_ids:
  - opencode-json-a0cbc058
  - swarmvault-config-b6c23841
project_ids: []
node_ids:
  - 'concept:local'
freshness: fresh
status: candidate
confidence: 0.8
created_at: '2026-05-11T08:45:09.821Z'
updated_at: '2026-05-11T08:45:09.821Z'
compiled_from:
  - opencode-json-a0cbc058
  - swarmvault-config-b6c23841
managed_by: system
backlinks:
  - 'source:opencode-json-a0cbc058'
  - 'source:swarmvault-config-b6c23841'
schema_hash: 874431dbbfdec0b254a4aa1bf002900574c9b485735a883690c2becb5f717720
source_hashes:
  opencode-json-a0cbc058: a0cbc058f08f809a1e8b3a66ecb90128f0f570a860da50943e25cd316efb015e
  swarmvault-config-b6c23841: b6c2384189fa20d8f52617692a62883a68b118609c509a52cf3351feaa1f9a3e
source_semantic_hashes:
  opencode-json-a0cbc058: a0cbc058f08f809a1e8b3a66ecb90128f0f570a860da50943e25cd316efb015e
  swarmvault-config-b6c23841: b6c2384189fa20d8f52617692a62883a68b118609c509a52cf3351feaa1f9a3e
decay_score: 1
last_confirmed_at: '2026-05-11T08:45:13.849Z'
---
# local

## Summary

Frequently referenced concept in opencode.json.

## Seen In

- [[sources/opencode-json-a0cbc058|opencode.json]]
- [[sources/swarmvault-config-b6c23841|swarmvault.config]]

## Source Claims

- { "$schema": "https://opencode.ai/config.json", "mcp": { "coachctl": { "type": "local", "command": ["uv", "run", "coachctl", "serve"], "environment": { "AGENT_DATA_ROOT": "{env:AGENT_DATA_ROOT}", "STRAVA_PROFILE": "{env:STRAVA_PROFILE}" }, "enabled": true }, "garmin": { "type": "local", "command": [" /.venv/bin/garmin-mcp"], "enabled": false }, "coros": { "type": "local", "command": [" /.venv/bin/coros-mcp", "serve"], "enabled": false } } } [source:opencode-json-a0cbc058]
- swarmvault.config Format: JSON Top-level: object Size: 13 Nested depth: 4 ## Schema - workspace: object (5 keys) - providers: object (1 keys) - tasks: object (5 keys) - viewer: object (1 keys) - profile: object (6 keys) - projects: object (0 keys) - agents: array (3 items) - schedules: object (0 keys) - orchestration: object (3 keys) - benchmark: object (3 keys) - repoAnalysis: object (2 keys) - graphSinks: object (0 keys) - retrieval: object (4 keys) ## Preview json { "workspace": { "rawDir": "raw", "wikiDir": "wiki", "stateDir": "state", "agentDir": "agent", "inboxDir": "inbox" }, "providers": { "local": { "type": "heuristic", "model": "heuristic-v1", "capabilities": [ "chat", "structured", "vision", "local" ] } }, "tasks": { "compileProvider": "local", "queryProvider": "local", "lintProvider": "local", "visionProvider": "local", "imageProvider": "local" }, "viewer": { "port": 4123 }, "profile": { "presets": [], "dashboardPack": "default", "guidedSessionMode": "insights_only", "dataviewBlocks": false, "guidedIngestDefault": false, "deepLintDefault": false }, "projects": {}, "agents": [ … [source:swarmvault-config-b6c23841]

