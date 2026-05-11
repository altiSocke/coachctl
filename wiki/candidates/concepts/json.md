---
page_id: 'concept:json'
kind: concept
cssclasses:
  - swarmvault
  - sv-concept
title: json
source_class: first_party
tags:
  - concept
  - candidate
source_ids:
  - hooks-a17f6f95
  - >-
    opencode-local-config-contains-live-api-tokens-use-opencode-json-example-as-temp-fe834141
  - skillfish-1c853384
  - skillfish-3d8fffc6
  - skillfish-65c158e0
  - skillfish-a264adc7
  - skillfish-e96604ef
project_ids: []
node_ids:
  - 'concept:json'
freshness: fresh
status: candidate
confidence: 0.95
created_at: '2026-05-11T08:45:09.804Z'
updated_at: '2026-05-11T08:45:09.804Z'
compiled_from:
  - hooks-a17f6f95
  - >-
    opencode-local-config-contains-live-api-tokens-use-opencode-json-example-as-temp-fe834141
  - skillfish-1c853384
  - skillfish-3d8fffc6
  - skillfish-65c158e0
  - skillfish-a264adc7
  - skillfish-e96604ef
managed_by: system
backlinks:
  - 'source:hooks-a17f6f95'
  - >-
    source:opencode-local-config-contains-live-api-tokens-use-opencode-json-example-as-temp-fe834141
  - 'source:skillfish-1c853384'
  - 'source:skillfish-3d8fffc6'
  - 'source:skillfish-65c158e0'
  - 'source:skillfish-a264adc7'
  - 'source:skillfish-e96604ef'
schema_hash: 874431dbbfdec0b254a4aa1bf002900574c9b485735a883690c2becb5f717720
source_hashes:
  hooks-a17f6f95: a17f6f95d4075e1e563abfa9d2a8f6c00acb3f884b3eb34a64744a6070a2aee2
  opencode-local-config-contains-live-api-tokens-use-opencode-json-example-as-temp-fe834141: fe83414169764eed83893678b9d39ddbad1ca33ef9b7676514761226e5e6aee5
  skillfish-1c853384: 1c8533844a98b504ac5aee73ce49204dc98e4ff5fdb7e72dce62565b64e7772b
  skillfish-3d8fffc6: 3d8fffc64a29fa91ddd090999087cd643cffcd6debdb0629d7d1157a9a5084de
  skillfish-65c158e0: 65c158e040815056d0bf9007ba4b03062e3eb5581419deba03f239d0599af39d
  skillfish-a264adc7: a264adc74326dc653481c89850fa4a4427377b3645eb7c93ac566996ca534d42
  skillfish-e96604ef: e96604ef95cd2d2f7809c93df7d25db1580b6827e8fa15ef3f4aaa722a796315
source_semantic_hashes:
  hooks-a17f6f95: a17f6f95d4075e1e563abfa9d2a8f6c00acb3f884b3eb34a64744a6070a2aee2
  opencode-local-config-contains-live-api-tokens-use-opencode-json-example-as-temp-fe834141: fe83414169764eed83893678b9d39ddbad1ca33ef9b7676514761226e5e6aee5
  skillfish-1c853384: 1c8533844a98b504ac5aee73ce49204dc98e4ff5fdb7e72dce62565b64e7772b
  skillfish-3d8fffc6: 3d8fffc64a29fa91ddd090999087cd643cffcd6debdb0629d7d1157a9a5084de
  skillfish-65c158e0: 65c158e040815056d0bf9007ba4b03062e3eb5581419deba03f239d0599af39d
  skillfish-a264adc7: a264adc74326dc653481c89850fa4a4427377b3645eb7c93ac566996ca534d42
  skillfish-e96604ef: e96604ef95cd2d2f7809c93df7d25db1580b6827e8fa15ef3f4aaa722a796315
decay_score: 1
last_confirmed_at: '2026-05-11T08:45:13.849Z'
---
# json

## Summary

Frequently referenced concept in hooks.

## Seen In

- [[sources/hooks-a17f6f95|hooks]]
- [[sources/opencode-local-config-contains-live-api-tokens-use-opencode-json-example-as-temp-fe834141|opencode local config — contains live API tokens; use opencode.json.example as template]]
- [[sources/skillfish-1c853384|.skillfish]]
- [[sources/skillfish-3d8fffc6|.skillfish]]
- [[sources/skillfish-65c158e0|.skillfish]]
- [[sources/skillfish-a264adc7|.skillfish]]
- [[sources/skillfish-e96604ef|.skillfish]]

## Source Claims

- hooks Format: JSON Top-level: object Size: 1 Nested depth: 6 ## Schema - hooks: object (2 keys) ## Preview json { "hooks": { "SessionStart": [ { "hooks": [ { "type": "command", "command": "node .codex/hooks/swarmvault-graph-first.js session-start" } ] } ], "PreToolUse": [ { "matcher": "Bash", "hooks": [ { "type": "command", "command": "node .codex/hooks/swarmvault-graph-first.js pre-tool-use" } ] } ] } } [source:hooks-a17f6f95]
- .env pycache / *.pyc .ruff_cache/ .venv/ dist/ *.egg-info/ # opencode local config — contains live API tokens; use opencode.json.example as template opencode.json # Editor / IDE state .obsidian/ .idea/ *.code-workspace # Defensive — these directories belong in the personal repo, never here wiki/personal/ data/ config/profiles/ profile/ [source:opencode-local-config-contains-live-api-tokens-use-opencode-json-example-as-temp-fe834141]
- .skillfish Format: JSON Top-level: object Size: 8 Nested depth: 1 ## Schema - version: number - name: string - owner: string - repo: string - path: string - branch: string - sha: string - source: string ## Preview json { "version": 2, "name": "verification-loop", "owner": "affaan-m", "repo": "everything-claude-code", "path": ".agents/skills/verification-loop", "branch": "main", "sha": "77f2554af6c5a62256ddd056c9e2accb46843236", "source": "manual" } [source:skillfish-1c853384]
- .skillfish Format: JSON Top-level: object Size: 8 Nested depth: 1 ## Schema - version: number - name: string - owner: string - repo: string - path: string - branch: string - sha: string - source: string ## Preview json { "version": 2, "name": "deep-research", "owner": "affaan-m", "repo": "everything-claude-code", "path": ".agents/skills/deep-research", "branch": "main", "sha": "0c505db60e5d0eeb10ba045f8dd113ff04bb1a60", "source": "manual" } [source:skillfish-3d8fffc6]
- .skillfish Format: JSON Top-level: object Size: 8 Nested depth: 1 ## Schema - version: number - name: string - owner: string - repo: string - path: string - branch: string - sha: string - source: string ## Preview json { "version": 2, "name": "tdd-workflow", "owner": "affaan-m", "repo": "everything-claude-code", "path": ".agents/skills/tdd-workflow", "branch": "main", "sha": "8f167ba6170e97b0bf05048a5f0ce595a21a8acc", "source": "manual" } [source:skillfish-65c158e0]
- .skillfish Format: JSON Top-level: object Size: 8 Nested depth: 1 ## Schema - version: number - name: string - owner: string - repo: string - path: string - branch: string - sha: string - source: string ## Preview json { "version": 2, "name": "python-patterns", "owner": "affaan-m", "repo": "everything-claude-code", "path": ".kiro/skills/python-patterns", "branch": "main", "sha": "114c27672ffb64f63c1e755a864810567a45faa7", "source": "manual" } [source:skillfish-a264adc7]
- .skillfish Format: JSON Top-level: object Size: 8 Nested depth: 1 ## Schema - version: number - name: string - owner: string - repo: string - path: string - branch: string - sha: string - source: string ## Preview json { "version": 2, "name": "security-review", "owner": "affaan-m", "repo": "everything-claude-code", "path": ".agents/skills/security-review", "branch": "main", "sha": "411c09e93264fb1e2cc4e5f8380497e0d91aa79f", "source": "manual" } [source:skillfish-e96604ef]

