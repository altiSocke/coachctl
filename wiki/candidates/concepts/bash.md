---
page_id: 'concept:bash'
kind: concept
cssclasses:
  - swarmvault
  - sv-concept
title: bash
source_class: first_party
tags:
  - concept
  - candidate
source_ids:
  - verification-loop-skill-beeb59cf
project_ids: []
node_ids:
  - 'concept:bash'
freshness: fresh
status: candidate
confidence: 0.65
created_at: '2026-05-11T08:45:09.887Z'
updated_at: '2026-05-11T08:45:09.887Z'
compiled_from:
  - verification-loop-skill-beeb59cf
managed_by: system
backlinks:
  - 'source:verification-loop-skill-beeb59cf'
schema_hash: 874431dbbfdec0b254a4aa1bf002900574c9b485735a883690c2becb5f717720
source_hashes:
  verification-loop-skill-beeb59cf: beeb59cfb3d9ba8aaad0d4d6d99d534f37d6d25dc42561f6cea64b102625a141
source_semantic_hashes:
  verification-loop-skill-beeb59cf: 44d9656e0fc563db04d79e19922bee6105e0293cfb0c9473995e81e2caf6ed6b
decay_score: 1
last_confirmed_at: '2026-05-11T08:45:13.849Z'
---
# bash

## Summary

Frequently referenced concept in Verification Loop Skill.

## Seen In

- [[sources/verification-loop-skill-beeb59cf|Verification Loop Skill]]

## Source Claims

- ## When to Use Invoke this skill: - After completing a feature or significant code change - Before creating a PR - When you want to ensure quality gates pass - After refactoring ## Verification Phases ### Phase 1: Build Verification bash # Check if project builds npm run build 2>&1 | tail -20 # OR pnpm build 2>&1 | tail -20 If build fails, STOP and fix before continuing. [source:verification-loop-skill-beeb59cf]
- ### Phase 2: Type Check bash # TypeScript projects npx tsc --noEmit 2>&1 | head -30 # Python projects pyright . [source:verification-loop-skill-beeb59cf]

