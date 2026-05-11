---
page_id: 'concept:command'
kind: concept
cssclasses:
  - swarmvault
  - sv-concept
title: command
source_class: first_party
tags:
  - concept
  - candidate
source_ids:
  - hooks-a17f6f95
  - opencode-json-a0cbc058
  - settings-b7c2c769
project_ids: []
node_ids:
  - 'concept:command'
freshness: fresh
status: candidate
confidence: 0.95
created_at: '2026-05-11T08:45:09.804Z'
updated_at: '2026-05-11T08:45:09.804Z'
compiled_from:
  - hooks-a17f6f95
  - opencode-json-a0cbc058
  - settings-b7c2c769
managed_by: system
backlinks:
  - 'source:hooks-a17f6f95'
  - 'source:opencode-json-a0cbc058'
  - 'source:settings-b7c2c769'
schema_hash: 874431dbbfdec0b254a4aa1bf002900574c9b485735a883690c2becb5f717720
source_hashes:
  hooks-a17f6f95: a17f6f95d4075e1e563abfa9d2a8f6c00acb3f884b3eb34a64744a6070a2aee2
  opencode-json-a0cbc058: a0cbc058f08f809a1e8b3a66ecb90128f0f570a860da50943e25cd316efb015e
  settings-b7c2c769: b7c2c769e7a7d898e93fb177cc969cc7f681c086a44dd54ef7a84b7ae0bda194
source_semantic_hashes:
  hooks-a17f6f95: a17f6f95d4075e1e563abfa9d2a8f6c00acb3f884b3eb34a64744a6070a2aee2
  opencode-json-a0cbc058: a0cbc058f08f809a1e8b3a66ecb90128f0f570a860da50943e25cd316efb015e
  settings-b7c2c769: b7c2c769e7a7d898e93fb177cc969cc7f681c086a44dd54ef7a84b7ae0bda194
decay_score: 1
last_confirmed_at: '2026-05-11T08:45:13.849Z'
---
# command

## Summary

Frequently referenced concept in hooks.

## Seen In

- [[sources/hooks-a17f6f95|hooks]]
- [[sources/opencode-json-a0cbc058|opencode.json]]
- [[sources/settings-b7c2c769|settings]]

## Source Claims

- hooks Format: JSON Top-level: object Size: 1 Nested depth: 6 ## Schema - hooks: object (2 keys) ## Preview json { "hooks": { "SessionStart": [ { "hooks": [ { "type": "command", "command": "node .codex/hooks/swarmvault-graph-first.js session-start" } ] } ], "PreToolUse": [ { "matcher": "Bash", "hooks": [ { "type": "command", "command": "node .codex/hooks/swarmvault-graph-first.js pre-tool-use" } ] } ] } } [source:hooks-a17f6f95]
- { "$schema": "https://opencode.ai/config.json", "mcp": { "coachctl": { "type": "local", "command": ["uv", "run", "coachctl", "serve"], "environment": { "AGENT_DATA_ROOT": "{env:AGENT_DATA_ROOT}", "STRAVA_PROFILE": "{env:STRAVA_PROFILE}" }, "enabled": true }, "garmin": { "type": "local", "command": [" /.venv/bin/garmin-mcp"], "enabled": false }, "coros": { "type": "local", "command": [" /.venv/bin/coros-mcp", "serve"], "enabled": false } } } [source:opencode-json-a0cbc058]
- settings Format: JSON Top-level: object Size: 1 Nested depth: 6 ## Schema - hooks: object (2 keys) ## Preview json { "hooks": { "SessionStart": [ { "matcher": "startup", "hooks": [ { "type": "command", "command": "node \"$CLAUDE_PROJECT_DIR/.claude/hooks/swarmvault-graph-first.js\" session-start" } ] }, { "matcher": "resume", "hooks": [ { "type": "command", "command": "node \"$CLAUDE_PROJECT_DIR/.claude/hooks/swarmvault-graph-first.js\" session-start" } ] }, { "matcher": "clear", "hooks": [ { "type": "command", "command": "node \"$CLAUDE_PROJECT_DIR/.claude/hooks/swarmvault-graph-first.js\" session-start" } ] }, { "matcher": "compact", "hooks": [ { "type": "command", "command": "node \"$CLAUDE_PROJECT_DIR/.claude/hooks/swarmvault-graph-first.js\" session-start" } ] } ], … [source:settings-b7c2c769]

