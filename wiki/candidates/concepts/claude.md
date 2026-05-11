---
page_id: 'concept:claude'
kind: concept
cssclasses:
  - swarmvault
  - sv-concept
title: claude
source_class: first_party
tags:
  - concept
  - candidate
source_ids:
  - settings-b7c2c769
project_ids: []
node_ids:
  - 'concept:claude'
freshness: fresh
status: candidate
confidence: 0.65
created_at: '2026-05-11T08:45:09.845Z'
updated_at: '2026-05-11T08:45:09.845Z'
compiled_from:
  - settings-b7c2c769
managed_by: system
backlinks:
  - 'source:settings-b7c2c769'
schema_hash: 874431dbbfdec0b254a4aa1bf002900574c9b485735a883690c2becb5f717720
source_hashes:
  settings-b7c2c769: b7c2c769e7a7d898e93fb177cc969cc7f681c086a44dd54ef7a84b7ae0bda194
source_semantic_hashes:
  settings-b7c2c769: b7c2c769e7a7d898e93fb177cc969cc7f681c086a44dd54ef7a84b7ae0bda194
decay_score: 1
last_confirmed_at: '2026-05-11T08:45:13.849Z'
---
# claude

## Summary

Frequently referenced concept in settings.

## Seen In

- [[sources/settings-b7c2c769|settings]]

## Source Claims

- settings Format: JSON Top-level: object Size: 1 Nested depth: 6 ## Schema - hooks: object (2 keys) ## Preview json { "hooks": { "SessionStart": [ { "matcher": "startup", "hooks": [ { "type": "command", "command": "node \"$CLAUDE_PROJECT_DIR/.claude/hooks/swarmvault-graph-first.js\" session-start" } ] }, { "matcher": "resume", "hooks": [ { "type": "command", "command": "node \"$CLAUDE_PROJECT_DIR/.claude/hooks/swarmvault-graph-first.js\" session-start" } ] }, { "matcher": "clear", "hooks": [ { "type": "command", "command": "node \"$CLAUDE_PROJECT_DIR/.claude/hooks/swarmvault-graph-first.js\" session-start" } ] }, { "matcher": "compact", "hooks": [ { "type": "command", "command": "node \"$CLAUDE_PROJECT_DIR/.claude/hooks/swarmvault-graph-first.js\" session-start" } ] } ], … [source:settings-b7c2c769]

