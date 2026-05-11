---
page_id: 'source:opencode-json-a0cbc058'
kind: source
cssclasses:
  - swarmvault
  - sv-source
title: opencode.json
source_class: first_party
tags:
  - source
source_ids:
  - opencode-json-a0cbc058
project_ids: []
node_ids:
  - 'source:opencode-json-a0cbc058'
  - 'concept:command'
  - 'concept:enabled'
  - 'concept:local'
  - 'concept:type'
  - 'concept:agent'
  - 'concept:coachctl'
freshness: fresh
status: active
confidence: 1
created_at: '2026-05-11T08:45:09.660Z'
updated_at: '2026-05-11T08:45:09.660Z'
compiled_from:
  - opencode-json-a0cbc058
managed_by: system
backlinks:
  - 'concept:command'
  - 'concept:enabled'
  - 'concept:local'
  - 'concept:type'
  - 'concept:agent'
  - 'concept:coachctl'
schema_hash: 874431dbbfdec0b254a4aa1bf002900574c9b485735a883690c2becb5f717720
source_hashes:
  opencode-json-a0cbc058: a0cbc058f08f809a1e8b3a66ecb90128f0f570a860da50943e25cd316efb015e
source_semantic_hashes:
  opencode-json-a0cbc058: a0cbc058f08f809a1e8b3a66ecb90128f0f570a860da50943e25cd316efb015e
decay_score: 1
last_confirmed_at: '2026-05-11T08:45:13.849Z'
---
# opencode.json

Source ID: `opencode-json-a0cbc058`
Source Kind: `text`
Source Path: `C:/Users/tieschy/workspace/coachctl/opencode.json.example`

Source Class: `first_party`


## Summary

{ "$schema": "https://opencode.ai/config.json", "mcp": { "coachctl": { "type": "local", "command": ["uv", "run", "coachctl", "serve"], "environment": { "AGENT_DATA_ROOT": "{env:AGENT_DATA_ROOT}", "STRAVA_PROFILE": "{env:STRAVA_PROFILE}" }, "enabled": true }, "garmin": { "type": "local", "command": [" /.venv/bin/garmin-mcp"], "enabled": false }, "coros": { "type": "local", "command": [" /.venv/bin/coros-mcp", "serve"], "enabled": false } } }

## Concepts

- [[concepts/command|command]]: Frequently referenced concept in opencode.json.
- [[concepts/enabled|enabled]]: Frequently referenced concept in opencode.json.
- [[concepts/local|local]]: Frequently referenced concept in opencode.json.
- [[concepts/type|type]]: Frequently referenced concept in opencode.json.
- [[concepts/agent|agent]]: Frequently referenced concept in opencode.json.
- [[concepts/coachctl|coachctl]]: Frequently referenced concept in opencode.json.

## Entities

- None detected.

## Claims

- { "$schema": "https://opencode.ai/config.json", "mcp": { "coachctl": { "type": "local", "command": ["uv", "run", "coachctl", "serve"], "environment": { "AGENT_DATA_ROOT": "{env:AGENT_DATA_ROOT}", "STRAVA_PROFILE": "{env:STRAVA_PROFILE}" }, "enabled": true }, "garmin": { "type": "local", "command": [" /.venv/bin/garmin-mcp"], "enabled": false }, "coros": { "type": "local", "command": [" /.venv/bin/coros-mcp", "serve"], "enabled": false } } } [source:opencode-json-a0cbc058]

## Questions

- How does command relate to opencode.json?
- How does enabled relate to opencode.json?
- How does local relate to opencode.json?

