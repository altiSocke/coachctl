---
page_id: 'concept:object'
kind: concept
cssclasses:
  - swarmvault
  - sv-concept
title: object
source_class: first_party
tags:
  - concept
  - candidate
source_ids:
  - hooks-a17f6f95
  - openai-17bab3f1
  - openai-786b054a
  - openai-df0ed566
  - openai-f9bd5846
  - pyproject-0d00c775
  - swarmvault-config-b6c23841
project_ids: []
node_ids:
  - 'concept:object'
freshness: fresh
status: candidate
confidence: 0.95
created_at: '2026-05-11T08:45:09.805Z'
updated_at: '2026-05-11T08:45:09.805Z'
compiled_from:
  - hooks-a17f6f95
  - openai-17bab3f1
  - openai-786b054a
  - openai-df0ed566
  - openai-f9bd5846
  - pyproject-0d00c775
  - swarmvault-config-b6c23841
managed_by: system
backlinks:
  - 'source:hooks-a17f6f95'
  - 'source:openai-17bab3f1'
  - 'source:openai-786b054a'
  - 'source:openai-df0ed566'
  - 'source:openai-f9bd5846'
  - 'source:pyproject-0d00c775'
  - 'source:swarmvault-config-b6c23841'
schema_hash: 874431dbbfdec0b254a4aa1bf002900574c9b485735a883690c2becb5f717720
source_hashes:
  hooks-a17f6f95: a17f6f95d4075e1e563abfa9d2a8f6c00acb3f884b3eb34a64744a6070a2aee2
  openai-17bab3f1: 17bab3f1fef6ad02d8f2fa513767d9bc010750c26add61e04dc4e246be17f2e7
  openai-786b054a: 786b054ad769268d6c4b97754fc22c954489bbbe93785fb2814a532164a9ed03
  openai-df0ed566: df0ed5667105918b3d5ba38b4e5a85f6ae9d9901e020ca1aadd49ab8d1ceb680
  openai-f9bd5846: f9bd58463a728823a9a2427ff3b185f2a9dae368b2ef1f28f43aef52c93617e6
  pyproject-0d00c775: 0d00c7757bc8936d6b844bf5842c6d0ed1e809cb07d8001fc8295595deac950e
  swarmvault-config-b6c23841: b6c2384189fa20d8f52617692a62883a68b118609c509a52cf3351feaa1f9a3e
source_semantic_hashes:
  hooks-a17f6f95: a17f6f95d4075e1e563abfa9d2a8f6c00acb3f884b3eb34a64744a6070a2aee2
  openai-17bab3f1: 17bab3f1fef6ad02d8f2fa513767d9bc010750c26add61e04dc4e246be17f2e7
  openai-786b054a: 786b054ad769268d6c4b97754fc22c954489bbbe93785fb2814a532164a9ed03
  openai-df0ed566: df0ed5667105918b3d5ba38b4e5a85f6ae9d9901e020ca1aadd49ab8d1ceb680
  openai-f9bd5846: f9bd58463a728823a9a2427ff3b185f2a9dae368b2ef1f28f43aef52c93617e6
  pyproject-0d00c775: 0d00c7757bc8936d6b844bf5842c6d0ed1e809cb07d8001fc8295595deac950e
  swarmvault-config-b6c23841: b6c2384189fa20d8f52617692a62883a68b118609c509a52cf3351feaa1f9a3e
decay_score: 1
last_confirmed_at: '2026-05-11T08:45:13.849Z'
---
# object

## Summary

Frequently referenced concept in hooks.

## Seen In

- [[sources/hooks-a17f6f95|hooks]]
- [[sources/openai-17bab3f1|openai]]
- [[sources/openai-786b054a|openai]]
- [[sources/openai-df0ed566|openai]]
- [[sources/openai-f9bd5846|openai]]
- [[sources/pyproject-0d00c775|pyproject]]
- [[sources/swarmvault-config-b6c23841|swarmvault.config]]

## Source Claims

- hooks Format: JSON Top-level: object Size: 1 Nested depth: 6 ## Schema - hooks: object (2 keys) ## Preview json { "hooks": { "SessionStart": [ { "hooks": [ { "type": "command", "command": "node .codex/hooks/swarmvault-graph-first.js session-start" } ] } ], "PreToolUse": [ { "matcher": "Bash", "hooks": [ { "type": "command", "command": "node .codex/hooks/swarmvault-graph-first.js pre-tool-use" } ] } ] } } [source:hooks-a17f6f95]
- openai Format: YAML Top-level: object Size: 2 Nested depth: 2 ## Schema - interface: object (4 keys) - policy: object (1 keys) ## Preview yaml interface: display_name: "Deep Research" short_description: "Multi-source cited research reports" brand_color: "#6366F1" default_prompt: "Use $deep-research to produce a cited multi-source research report." policy: allow_implicit_invocation: true [source:openai-17bab3f1]
- openai Format: YAML Top-level: object Size: 2 Nested depth: 2 ## Schema - interface: object (4 keys) - policy: object (1 keys) ## Preview yaml interface: display_name: "Security Review" short_description: "Security checklist and vulnerability review" brand_color: "#EF4444" default_prompt: "Use $security-review to review sensitive code with the security checklist." policy: allow_implicit_invocation: true [source:openai-786b054a]
- openai Format: YAML Top-level: object Size: 2 Nested depth: 2 ## Schema - interface: object (4 keys) - policy: object (1 keys) ## Preview yaml interface: display_name: "Verification Loop" short_description: "Build, test, lint, and typecheck verification" brand_color: "#10B981" default_prompt: "Use $verification-loop to run build, test, lint, and typecheck verification." policy: allow_implicit_invocation: true [source:openai-df0ed566]
- openai Format: YAML Top-level: object Size: 2 Nested depth: 2 ## Schema - interface: object (4 keys) - policy: object (1 keys) ## Preview yaml interface: display_name: "TDD Workflow" short_description: "Test-driven development with coverage gates" brand_color: "#22C55E" default_prompt: "Use $tdd-workflow to drive the change with tests before implementation." policy: allow_implicit_invocation: true [source:openai-f9bd5846]
- pyproject Format: TOML Top-level: object Size: 2 Nested depth: 5 ## Schema - project: object (7 keys) - tool: object (4 keys) ## Preview toml [project] name = "coachctl" version = "0.1.0" description = "coachctl — endurance training coach (MCP server + dashboard)" requires-python = ">=3.11" dependencies = [ "mcp>=1.0.0", "httpx>=0.27.0", "pyyaml>=6.0.2", "python-dotenv>=1.0.0", "jinja2>=3.1.0", "typer>=0.12", ] [project.optional-dependencies] dashboard = [ "fastapi>=0.110", "uvicorn>=0.27", ] dev = [ "pytest>=8.0", "pytest-cov>=5.0", "pytest-asyncio>=0.23", "httpx>=0.27.0", ] [project.scripts] coachctl = "coachctl.cli:main" [tool.setuptools.package-data] "coachctl.dashboard" = ["app.html"] [tool.pytest.ini_options] testpaths = ["tests"] addopts = "-v --cov=src/coachctl --cov-report=term-missing" asyncio_mode = "auto" [tool.coverage.run] source = ["src/coachctl"] omit = ["*/dashboard/__main__.py", "*/cli.py", "*/update.py", "*/new_profile.py"] … [source:pyproject-0d00c775]
- swarmvault.config Format: JSON Top-level: object Size: 13 Nested depth: 4 ## Schema - workspace: object (5 keys) - providers: object (1 keys) - tasks: object (5 keys) - viewer: object (1 keys) - profile: object (6 keys) - projects: object (0 keys) - agents: array (3 items) - schedules: object (0 keys) - orchestration: object (3 keys) - benchmark: object (3 keys) - repoAnalysis: object (2 keys) - graphSinks: object (0 keys) - retrieval: object (4 keys) ## Preview json { "workspace": { "rawDir": "raw", "wikiDir": "wiki", "stateDir": "state", "agentDir": "agent", "inboxDir": "inbox" }, "providers": { "local": { "type": "heuristic", "model": "heuristic-v1", "capabilities": [ "chat", "structured", "vision", "local" ] } }, "tasks": { "compileProvider": "local", "queryProvider": "local", "lintProvider": "local", "visionProvider": "local", "imageProvider": "local" }, "viewer": { "port": 4123 }, "profile": { "presets": [], "dashboardPack": "default", "guidedSessionMode": "insights_only", "dataviewBlocks": false, "guidedIngestDefault": false, "deepLintDefault": false }, "projects": {}, "agents": [ … [source:swarmvault-config-b6c23841]

