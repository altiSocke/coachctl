---
page_id: 'concept:verification'
kind: concept
cssclasses:
  - swarmvault
  - sv-concept
title: verification
source_class: first_party
tags:
  - concept
  - candidate
source_ids:
  - openai-df0ed566
  - verification-loop-skill-beeb59cf
project_ids: []
node_ids:
  - 'concept:verification'
freshness: fresh
status: candidate
confidence: 0.8
created_at: '2026-05-11T08:45:09.819Z'
updated_at: '2026-05-11T08:45:09.819Z'
compiled_from:
  - openai-df0ed566
  - verification-loop-skill-beeb59cf
managed_by: system
backlinks:
  - 'source:openai-df0ed566'
  - 'source:verification-loop-skill-beeb59cf'
schema_hash: 874431dbbfdec0b254a4aa1bf002900574c9b485735a883690c2becb5f717720
source_hashes:
  openai-df0ed566: df0ed5667105918b3d5ba38b4e5a85f6ae9d9901e020ca1aadd49ab8d1ceb680
  verification-loop-skill-beeb59cf: beeb59cfb3d9ba8aaad0d4d6d99d534f37d6d25dc42561f6cea64b102625a141
source_semantic_hashes:
  openai-df0ed566: df0ed5667105918b3d5ba38b4e5a85f6ae9d9901e020ca1aadd49ab8d1ceb680
  verification-loop-skill-beeb59cf: 44d9656e0fc563db04d79e19922bee6105e0293cfb0c9473995e81e2caf6ed6b
decay_score: 1
last_confirmed_at: '2026-05-11T08:45:13.849Z'
---
# verification

## Summary

Frequently referenced concept in openai.

## Seen In

- [[sources/openai-df0ed566|openai]]
- [[sources/verification-loop-skill-beeb59cf|Verification Loop Skill]]

## Source Claims

- openai Format: YAML Top-level: object Size: 2 Nested depth: 2 ## Schema - interface: object (4 keys) - policy: object (1 keys) ## Preview yaml interface: display_name: "Verification Loop" short_description: "Build, test, lint, and typecheck verification" brand_color: "#10B981" default_prompt: "Use $verification-loop to run build, test, lint, and typecheck verification." policy: allow_implicit_invocation: true [source:openai-df0ed566]
- description: A comprehensive verification system for Claude Code sessions. [source:verification-loop-skill-beeb59cf]
- # Verification Loop Skill A comprehensive verification system for Claude Code sessions. [source:verification-loop-skill-beeb59cf]
- ## When to Use Invoke this skill: - After completing a feature or significant code change - Before creating a PR - When you want to ensure quality gates pass - After refactoring ## Verification Phases ### Phase 1: Build Verification bash # Check if project builds npm run build 2>&1 | tail -20 # OR pnpm build 2>&1 | tail -20 If build fails, STOP and fix before continuing. [source:verification-loop-skill-beeb59cf]

