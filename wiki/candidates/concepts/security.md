---
page_id: 'concept:security'
kind: concept
cssclasses:
  - swarmvault
  - sv-concept
title: security
source_class: first_party
tags:
  - concept
  - candidate
source_ids:
  - openai-786b054a
  - security-review-skill-58079098
project_ids: []
node_ids:
  - 'concept:security'
freshness: fresh
status: candidate
confidence: 0.8
created_at: '2026-05-11T08:45:09.818Z'
updated_at: '2026-05-11T08:45:09.818Z'
compiled_from:
  - openai-786b054a
  - security-review-skill-58079098
managed_by: system
backlinks:
  - 'source:openai-786b054a'
  - 'source:security-review-skill-58079098'
schema_hash: 874431dbbfdec0b254a4aa1bf002900574c9b485735a883690c2becb5f717720
source_hashes:
  openai-786b054a: 786b054ad769268d6c4b97754fc22c954489bbbe93785fb2814a532164a9ed03
  security-review-skill-58079098: 58079098ea5f95604452aef459cd58fb45370fa672926db914bda20f9890ff57
source_semantic_hashes:
  openai-786b054a: 786b054ad769268d6c4b97754fc22c954489bbbe93785fb2814a532164a9ed03
  security-review-skill-58079098: eac6e0263375c8932584f11a2c4ef86725af9c19ac757e04f83dbebb39d68e2b
decay_score: 1
last_confirmed_at: '2026-05-11T08:45:13.849Z'
---
# security

## Summary

Frequently referenced concept in openai.

## Seen In

- [[sources/openai-786b054a|openai]]
- [[sources/security-review-skill-58079098|Security Review Skill]]

## Source Claims

- openai Format: YAML Top-level: object Size: 2 Nested depth: 2 ## Schema - interface: object (4 keys) - policy: object (1 keys) ## Preview yaml interface: display_name: "Security Review" short_description: "Security checklist and vulnerability review" brand_color: "#EF4444" default_prompt: "Use $security-review to review sensitive code with the security checklist." policy: allow_implicit_invocation: true [source:openai-786b054a]
- Provides comprehensive security checklist and patterns. [source:security-review-skill-58079098]
- # Security Review Skill This skill ensures all code follows security best practices and identifies potential vulnerabilities. [source:security-review-skill-58079098]
- ## When to Activate - Implementing authentication or authorization - Handling user input or file uploads - Creating new API endpoints - Working with secrets or credentials - Implementing payment features - Storing or transmitting sensitive data - Integrating third-party APIs ## Security Checklist ### 1. [source:security-review-skill-58079098]

