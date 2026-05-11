---
page_id: 'concept:agents'
kind: concept
cssclasses:
  - swarmvault
  - sv-concept
title: agents
source_class: first_party
tags:
  - concept
  - candidate
source_ids:
  - swarmvault-config-b6c23841
project_ids: []
node_ids:
  - 'concept:agents'
freshness: fresh
status: candidate
confidence: 0.65
created_at: '2026-05-11T08:45:09.866Z'
updated_at: '2026-05-11T08:45:09.866Z'
compiled_from:
  - swarmvault-config-b6c23841
managed_by: system
backlinks:
  - 'source:swarmvault-config-b6c23841'
schema_hash: 874431dbbfdec0b254a4aa1bf002900574c9b485735a883690c2becb5f717720
source_hashes:
  swarmvault-config-b6c23841: b6c2384189fa20d8f52617692a62883a68b118609c509a52cf3351feaa1f9a3e
source_semantic_hashes:
  swarmvault-config-b6c23841: b6c2384189fa20d8f52617692a62883a68b118609c509a52cf3351feaa1f9a3e
decay_score: 1
last_confirmed_at: '2026-05-11T08:45:13.849Z'
---
# agents

## Summary

Frequently referenced concept in swarmvault.config.

## Seen In

- [[sources/swarmvault-config-b6c23841|swarmvault.config]]

## Source Claims

- swarmvault.config Format: JSON Top-level: object Size: 13 Nested depth: 4 ## Schema - workspace: object (5 keys) - providers: object (1 keys) - tasks: object (5 keys) - viewer: object (1 keys) - profile: object (6 keys) - projects: object (0 keys) - agents: array (3 items) - schedules: object (0 keys) - orchestration: object (3 keys) - benchmark: object (3 keys) - repoAnalysis: object (2 keys) - graphSinks: object (0 keys) - retrieval: object (4 keys) ## Preview json { "workspace": { "rawDir": "raw", "wikiDir": "wiki", "stateDir": "state", "agentDir": "agent", "inboxDir": "inbox" }, "providers": { "local": { "type": "heuristic", "model": "heuristic-v1", "capabilities": [ "chat", "structured", "vision", "local" ] } }, "tasks": { "compileProvider": "local", "queryProvider": "local", "lintProvider": "local", "visionProvider": "local", "imageProvider": "local" }, "viewer": { "port": 4123 }, "profile": { "presets": [], "dashboardPack": "default", "guidedSessionMode": "insights_only", "dataviewBlocks": false, "guidedIngestDefault": false, "deepLintDefault": false }, "projects": {}, "agents": [ … [source:swarmvault-config-b6c23841]

