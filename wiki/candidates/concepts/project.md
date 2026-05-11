---
page_id: 'concept:project'
kind: concept
cssclasses:
  - swarmvault
  - sv-concept
title: project
source_class: first_party
tags:
  - concept
  - candidate
source_ids:
  - projects-ae86e2f4
  - pyproject-0d00c775
  - settings-b7c2c769
project_ids: []
node_ids:
  - 'concept:project'
freshness: fresh
status: candidate
confidence: 0.95
created_at: '2026-05-11T08:45:09.830Z'
updated_at: '2026-05-11T08:45:09.830Z'
compiled_from:
  - projects-ae86e2f4
  - pyproject-0d00c775
  - settings-b7c2c769
managed_by: system
backlinks:
  - 'source:projects-ae86e2f4'
  - 'source:pyproject-0d00c775'
  - 'source:settings-b7c2c769'
schema_hash: 874431dbbfdec0b254a4aa1bf002900574c9b485735a883690c2becb5f717720
source_hashes:
  projects-ae86e2f4: ae86e2f4312bd521e3b137601cb376a4f42b91fed3ccabbb73f7ef410084a7eb
  pyproject-0d00c775: 0d00c7757bc8936d6b844bf5842c6d0ed1e809cb07d8001fc8295595deac950e
  settings-b7c2c769: b7c2c769e7a7d898e93fb177cc969cc7f681c086a44dd54ef7a84b7ae0bda194
source_semantic_hashes:
  projects-ae86e2f4: c17f3824f10f7496c534034df6643e9aab08bdb9431f5d9bfa9f2ac000bf6187
  pyproject-0d00c775: 0d00c7757bc8936d6b844bf5842c6d0ed1e809cb07d8001fc8295595deac950e
  settings-b7c2c769: b7c2c769e7a7d898e93fb177cc969cc7f681c086a44dd54ef7a84b7ae0bda194
decay_score: 1
last_confirmed_at: '2026-05-11T08:45:13.849Z'
---
# project

## Summary

Frequently referenced concept in Projects.

## Seen In

- [[sources/projects-ae86e2f4|Projects]]
- [[sources/pyproject-0d00c775|pyproject]]
- [[sources/settings-b7c2c769|settings]]

## Source Claims

- title: Projects tags: index, projects # Projects - Run swarmvault compile to build project rollups. [source:projects-ae86e2f4]
- pyproject Format: TOML Top-level: object Size: 2 Nested depth: 5 ## Schema - project: object (7 keys) - tool: object (4 keys) ## Preview toml [project] name = "coachctl" version = "0.1.0" description = "coachctl — endurance training coach (MCP server + dashboard)" requires-python = ">=3.11" dependencies = [ "mcp>=1.0.0", "httpx>=0.27.0", "pyyaml>=6.0.2", "python-dotenv>=1.0.0", "jinja2>=3.1.0", "typer>=0.12", ] [project.optional-dependencies] dashboard = [ "fastapi>=0.110", "uvicorn>=0.27", ] dev = [ "pytest>=8.0", "pytest-cov>=5.0", "pytest-asyncio>=0.23", "httpx>=0.27.0", ] [project.scripts] coachctl = "coachctl.cli:main" [tool.setuptools.package-data] "coachctl.dashboard" = ["app.html"] [tool.pytest.ini_options] testpaths = ["tests"] addopts = "-v --cov=src/coachctl --cov-report=term-missing" asyncio_mode = "auto" [tool.coverage.run] source = ["src/coachctl"] omit = ["*/dashboard/__main__.py", "*/cli.py", "*/update.py", "*/new_profile.py"] … [source:pyproject-0d00c775]
- settings Format: JSON Top-level: object Size: 1 Nested depth: 6 ## Schema - hooks: object (2 keys) ## Preview json { "hooks": { "SessionStart": [ { "matcher": "startup", "hooks": [ { "type": "command", "command": "node \"$CLAUDE_PROJECT_DIR/.claude/hooks/swarmvault-graph-first.js\" session-start" } ] }, { "matcher": "resume", "hooks": [ { "type": "command", "command": "node \"$CLAUDE_PROJECT_DIR/.claude/hooks/swarmvault-graph-first.js\" session-start" } ] }, { "matcher": "clear", "hooks": [ { "type": "command", "command": "node \"$CLAUDE_PROJECT_DIR/.claude/hooks/swarmvault-graph-first.js\" session-start" } ] }, { "matcher": "compact", "hooks": [ { "type": "command", "command": "node \"$CLAUDE_PROJECT_DIR/.claude/hooks/swarmvault-graph-first.js\" session-start" } ] } ], … [source:settings-b7c2c769]

