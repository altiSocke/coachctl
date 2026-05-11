---
page_id: 'source:verification-loop-skill-beeb59cf'
kind: source
cssclasses:
  - swarmvault
  - sv-source
title: Verification Loop Skill
source_class: first_party
tags:
  - source
source_ids:
  - verification-loop-skill-beeb59cf
project_ids: []
node_ids:
  - 'source:verification-loop-skill-beeb59cf'
  - 'concept:verification'
  - 'concept:head'
  - 'concept:check'
  - 'concept:after'
  - 'concept:bash'
  - 'concept:include'
  - 'entity:claude-code'
  - 'entity:verification-loop-skill'
  - 'entity:when'
  - 'entity:use-invoke'
  - 'entity:after'
  - 'entity:before'
freshness: fresh
status: active
confidence: 1
created_at: '2026-05-11T08:45:09.699Z'
updated_at: '2026-05-11T08:45:09.699Z'
compiled_from:
  - verification-loop-skill-beeb59cf
managed_by: system
backlinks:
  - 'concept:verification'
  - 'concept:head'
  - 'concept:check'
  - 'concept:after'
  - 'concept:bash'
  - 'concept:include'
  - 'entity:claude-code'
  - 'entity:verification-loop-skill'
  - 'entity:when'
  - 'entity:use-invoke'
  - 'entity:after'
  - 'entity:before'
schema_hash: 874431dbbfdec0b254a4aa1bf002900574c9b485735a883690c2becb5f717720
source_hashes:
  verification-loop-skill-beeb59cf: beeb59cfb3d9ba8aaad0d4d6d99d534f37d6d25dc42561f6cea64b102625a141
source_semantic_hashes:
  verification-loop-skill-beeb59cf: 44d9656e0fc563db04d79e19922bee6105e0293cfb0c9473995e81e2caf6ed6b
decay_score: 1
last_confirmed_at: '2026-05-11T08:45:13.849Z'
---
# Verification Loop Skill

Source ID: `verification-loop-skill-beeb59cf`
Source Kind: `markdown`
Source Path: `C:/Users/tieschy/workspace/coachctl/.opencode/skills/verification-loop/SKILL.md`

Source Class: `first_party`


## Summary

description: A comprehensive verification system for Claude Code sessions. # Verification Loop Skill A comprehensive verification system for Claude Code sessions. ## When to Use Invoke this skill: - After completing a feature or significant code change - Before creating a PR - When you want to ensure quality gates pass - After refactoring ## Verification Phases ### Phase 1: Build Verification bash # Check if project builds npm run build 2>&1 | tail -20 # OR pnpm build 2>&1 | tail -20 If build fails, STOP and fix before continuing.

## Concepts

- [[concepts/verification|verification]]: Frequently referenced concept in Verification Loop Skill.
- [[concepts/head|head]]: Frequently referenced concept in Verification Loop Skill.
- [[concepts/check|check]]: Frequently referenced concept in Verification Loop Skill.
- [[concepts/after|after]]: Frequently referenced concept in Verification Loop Skill.
- [[concepts/bash|bash]]: Frequently referenced concept in Verification Loop Skill.
- [[concepts/include|include]]: Frequently referenced concept in Verification Loop Skill.

## Entities

- [[entities/claude-code|Claude Code]]: Named entity mentioned in Verification Loop Skill.
- [[entities/verification-loop-skill|Verification Loop Skill]]: Named entity mentioned in Verification Loop Skill.
- [[entities/when|When]]: Named entity mentioned in Verification Loop Skill.
- [[entities/use-invoke|Use Invoke]]: Named entity mentioned in Verification Loop Skill.
- [[entities/after|After]]: Named entity mentioned in Verification Loop Skill.
- [[entities/before|Before]]: Named entity mentioned in Verification Loop Skill.

## Claims

- description: A comprehensive verification system for Claude Code sessions. [source:verification-loop-skill-beeb59cf]
- # Verification Loop Skill A comprehensive verification system for Claude Code sessions. [source:verification-loop-skill-beeb59cf]
- ## When to Use Invoke this skill: - After completing a feature or significant code change - Before creating a PR - When you want to ensure quality gates pass - After refactoring ## Verification Phases ### Phase 1: Build Verification bash # Check if project builds npm run build 2>&1 | tail -20 # OR pnpm build 2>&1 | tail -20 If build fails, STOP and fix before continuing. [source:verification-loop-skill-beeb59cf]
- ### Phase 2: Type Check bash # TypeScript projects npx tsc --noEmit 2>&1 | head -30 # Python projects pyright . [source:verification-loop-skill-beeb59cf]

## Questions

- How does verification relate to Verification Loop Skill?
- How does head relate to Verification Loop Skill?
- How does check relate to Verification Loop Skill?

