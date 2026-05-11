---
page_id: 'entity:before'
kind: entity
cssclasses:
  - swarmvault
  - sv-entity
title: Before
source_class: first_party
tags:
  - entity
  - candidate
source_ids:
  - verification-loop-skill-beeb59cf
  - what-i-do-a929e628
project_ids: []
node_ids:
  - 'entity:before'
freshness: fresh
status: candidate
confidence: 0.8
created_at: '2026-05-11T08:45:10.017Z'
updated_at: '2026-05-11T08:45:10.017Z'
compiled_from:
  - verification-loop-skill-beeb59cf
  - what-i-do-a929e628
managed_by: system
backlinks:
  - 'source:verification-loop-skill-beeb59cf'
  - 'source:what-i-do-a929e628'
schema_hash: 874431dbbfdec0b254a4aa1bf002900574c9b485735a883690c2becb5f717720
source_hashes:
  verification-loop-skill-beeb59cf: beeb59cfb3d9ba8aaad0d4d6d99d534f37d6d25dc42561f6cea64b102625a141
  what-i-do-a929e628: a929e62826769be5ad430b6c2d6a0e0ca27ab0872066c1c5175099052367fcb3
source_semantic_hashes:
  verification-loop-skill-beeb59cf: 44d9656e0fc563db04d79e19922bee6105e0293cfb0c9473995e81e2caf6ed6b
  what-i-do-a929e628: ae7c4c220c832d699e5805d0fb61d507ebf1faabf675f1287863195942e86654
decay_score: 1
last_confirmed_at: '2026-05-11T08:45:13.849Z'
---
# Before

## Summary

Named entity mentioned in Verification Loop Skill.

## Seen In

- [[sources/verification-loop-skill-beeb59cf|Verification Loop Skill]]
- [[sources/what-i-do-a929e628|What I do]]

## Source Claims

- ## When to Use Invoke this skill: - After completing a feature or significant code change - Before creating a PR - When you want to ensure quality gates pass - After refactoring ## Verification Phases ### Phase 1: Build Verification bash # Check if project builds npm run build 2>&1 | tail -20 # OR pnpm build 2>&1 | tail -20 If build fails, STOP and fix before continuing. [source:verification-loop-skill-beeb59cf]

