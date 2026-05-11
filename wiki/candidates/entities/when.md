---
page_id: 'entity:when'
kind: entity
cssclasses:
  - swarmvault
  - sv-entity
title: When
source_class: first_party
tags:
  - entity
  - candidate
source_ids:
  - deep-research-2f018e7c
  - security-review-skill-58079098
  - test-driven-development-workflow-2f5af84b
  - verification-loop-skill-beeb59cf
project_ids: []
node_ids:
  - 'entity:when'
freshness: fresh
status: candidate
confidence: 0.95
created_at: '2026-05-11T08:45:09.921Z'
updated_at: '2026-05-11T08:45:09.921Z'
compiled_from:
  - deep-research-2f018e7c
  - security-review-skill-58079098
  - test-driven-development-workflow-2f5af84b
  - verification-loop-skill-beeb59cf
managed_by: system
backlinks:
  - 'source:deep-research-2f018e7c'
  - 'source:security-review-skill-58079098'
  - 'source:test-driven-development-workflow-2f5af84b'
  - 'source:verification-loop-skill-beeb59cf'
schema_hash: 874431dbbfdec0b254a4aa1bf002900574c9b485735a883690c2becb5f717720
source_hashes:
  deep-research-2f018e7c: 2f018e7cf5ea057956ad499b4abbb8c6d77bd7ac2c4c8a56d2aab851c8bdd35f
  security-review-skill-58079098: 58079098ea5f95604452aef459cd58fb45370fa672926db914bda20f9890ff57
  test-driven-development-workflow-2f5af84b: 2f5af84b4db9206be5b1e0f6b9e9b06a3423faa6e73f6cd16bf65d80a6e9ac7b
  verification-loop-skill-beeb59cf: beeb59cfb3d9ba8aaad0d4d6d99d534f37d6d25dc42561f6cea64b102625a141
source_semantic_hashes:
  deep-research-2f018e7c: e5908ea7625c27391840bc64c235dac6ee019b6b5d1bdfcaac77366033b99d90
  security-review-skill-58079098: eac6e0263375c8932584f11a2c4ef86725af9c19ac757e04f83dbebb39d68e2b
  test-driven-development-workflow-2f5af84b: 42049fc0abd07acdab8e967b56d47e553fd8f41c4f75f08eb7273a222e03bc81
  verification-loop-skill-beeb59cf: 44d9656e0fc563db04d79e19922bee6105e0293cfb0c9473995e81e2caf6ed6b
decay_score: 1
last_confirmed_at: '2026-05-11T08:45:13.849Z'
---
# When

## Summary

Named entity mentioned in Deep Research.

## Seen In

- [[sources/deep-research-2f018e7c|Deep Research]]
- [[sources/security-review-skill-58079098|Security Review Skill]]
- [[sources/test-driven-development-workflow-2f5af84b|Test-Driven Development Workflow]]
- [[sources/verification-loop-skill-beeb59cf|Verification Loop Skill]]

## Source Claims

- Use when the user wants thorough research on any topic with evidence and citations. [source:deep-research-2f018e7c]
- description: Use this skill when adding authentication, handling user input, working with secrets, creating API endpoints, or implementing payment/sensitive features. [source:security-review-skill-58079098]
- ## When to Activate - Implementing authentication or authorization - Handling user input or file uploads - Creating new API endpoints - Working with secrets or credentials - Implementing payment features - Storing or transmitting sensitive data - Integrating third-party APIs ## Security Checklist ### 1. [source:security-review-skill-58079098]
- description: Use this skill when writing new features, fixing bugs, or refactoring code. [source:test-driven-development-workflow-2f5af84b]
- ## When to Activate - Writing new features or functionality - Fixing bugs or issues - Refactoring existing code - Adding API endpoints - Creating new components ## Core Principles ### 1. [source:test-driven-development-workflow-2f5af84b]
- ## When to Use Invoke this skill: - After completing a feature or significant code change - Before creating a PR - When you want to ensure quality gates pass - After refactoring ## Verification Phases ### Phase 1: Build Verification bash # Check if project builds npm run build 2>&1 | tail -20 # OR pnpm build 2>&1 | tail -20 If build fails, STOP and fix before continuing. [source:verification-loop-skill-beeb59cf]

