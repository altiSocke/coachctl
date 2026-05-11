---
page_id: 'source:settings-b7c2c769'
kind: source
cssclasses:
  - swarmvault
  - sv-source
title: settings
source_class: first_party
tags:
  - source
source_ids:
  - settings-b7c2c769
project_ids: []
node_ids:
  - 'source:settings-b7c2c769'
  - 'concept:hooks'
  - 'concept:claude'
  - 'concept:command'
  - 'concept:matcher'
  - 'concept:node'
  - 'concept:project'
  - 'entity:format'
  - 'entity:top'
  - 'entity:size'
  - 'entity:nested'
  - 'entity:schema'
  - 'entity:preview'
freshness: fresh
status: active
confidence: 1
created_at: '2026-05-11T08:45:09.677Z'
updated_at: '2026-05-11T08:45:09.677Z'
compiled_from:
  - settings-b7c2c769
managed_by: system
backlinks:
  - 'concept:hooks'
  - 'concept:claude'
  - 'concept:command'
  - 'concept:matcher'
  - 'concept:node'
  - 'concept:project'
  - 'entity:format'
  - 'entity:top'
  - 'entity:size'
  - 'entity:nested'
  - 'entity:schema'
  - 'entity:preview'
schema_hash: 874431dbbfdec0b254a4aa1bf002900574c9b485735a883690c2becb5f717720
source_hashes:
  settings-b7c2c769: b7c2c769e7a7d898e93fb177cc969cc7f681c086a44dd54ef7a84b7ae0bda194
source_semantic_hashes:
  settings-b7c2c769: b7c2c769e7a7d898e93fb177cc969cc7f681c086a44dd54ef7a84b7ae0bda194
decay_score: 1
last_confirmed_at: '2026-05-11T08:45:13.849Z'
---
# settings

Source ID: `settings-b7c2c769`
Source Kind: `data`
Source Path: `C:/Users/tieschy/workspace/coachctl/.claude/settings.json`

Source Class: `first_party`


## Source Details

- format: json
- top level type: object
- top level size: 1
- nested depth: 6


## Summary

settings Format: JSON Top-level: object Size: 1 Nested depth: 6 ## Schema - hooks: object (2 keys) ## Preview json { "hooks": { "SessionStart": [ { "matcher": "startup", "hooks": [ { "type": "command", "command": "node \"$CLAUDE_PROJECT_DIR/.claude/hooks/swarmvault-graph-first.js\" session-start" } ] }, { "matcher": "resume", "hooks": [ { "type": "command", "command": "node \"$CLAUDE_PROJECT_DIR/.claude/hooks/swarmvault-graph-first.js\" session-start" } ] }, { "matcher": "clear", "hooks": [ { "type": "command", "command": "node \"$CLAUDE_PROJECT_DIR/.claude/hooks/swarmvault-graph-first.js\" session-start" } ] }, { "matcher": "compact", "hooks": [ { "type": "command", "command": "node \"$CLAUDE_PROJECT_DIR/.claude/hooks/swarmvault-graph-first.js\" session-start" } ] } ], …

## Concepts

- [[concepts/hooks|hooks]]: Frequently referenced concept in settings.
- [[concepts/claude|claude]]: Frequently referenced concept in settings.
- [[concepts/command|command]]: Frequently referenced concept in settings.
- [[concepts/matcher|matcher]]: Frequently referenced concept in settings.
- [[concepts/node|node]]: Frequently referenced concept in settings.
- [[concepts/project|project]]: Frequently referenced concept in settings.

## Entities

- [[entities/format|Format:]]: Named entity mentioned in settings.
- [[entities/top|Top-]]: Named entity mentioned in settings.
- [[entities/size|Size:]]: Named entity mentioned in settings.
- [[entities/nested|Nested]]: Named entity mentioned in settings.
- [[entities/schema|Schema -]]: Named entity mentioned in settings.
- [[entities/preview|Preview]]: Named entity mentioned in settings.

## Claims

- settings Format: JSON Top-level: object Size: 1 Nested depth: 6 ## Schema - hooks: object (2 keys) ## Preview json { "hooks": { "SessionStart": [ { "matcher": "startup", "hooks": [ { "type": "command", "command": "node \"$CLAUDE_PROJECT_DIR/.claude/hooks/swarmvault-graph-first.js\" session-start" } ] }, { "matcher": "resume", "hooks": [ { "type": "command", "command": "node \"$CLAUDE_PROJECT_DIR/.claude/hooks/swarmvault-graph-first.js\" session-start" } ] }, { "matcher": "clear", "hooks": [ { "type": "command", "command": "node \"$CLAUDE_PROJECT_DIR/.claude/hooks/swarmvault-graph-first.js\" session-start" } ] }, { "matcher": "compact", "hooks": [ { "type": "command", "command": "node \"$CLAUDE_PROJECT_DIR/.claude/hooks/swarmvault-graph-first.js\" session-start" } ] } ], … [source:settings-b7c2c769]

## Questions

- How does hooks relate to settings?
- How does claude relate to settings?
- How does command relate to settings?

