---
page_id: 'concept:coachctl'
kind: concept
cssclasses:
  - swarmvault
  - sv-concept
title: coachctl
source_class: first_party
tags:
  - concept
  - candidate
source_ids:
  - coachctl-architecture-conventions-8a2f1253
  - coachctl-strava-training-agent-7a3ae9ac
  - opencode-json-a0cbc058
  - pyproject-0d00c775
  - skill-show-dashboard-cf665da6
project_ids: []
node_ids:
  - 'concept:coachctl'
freshness: fresh
status: candidate
confidence: 0.95
created_at: '2026-05-11T08:45:09.724Z'
updated_at: '2026-05-11T08:45:09.724Z'
compiled_from:
  - coachctl-architecture-conventions-8a2f1253
  - coachctl-strava-training-agent-7a3ae9ac
  - opencode-json-a0cbc058
  - pyproject-0d00c775
  - skill-show-dashboard-cf665da6
managed_by: system
backlinks:
  - 'source:coachctl-architecture-conventions-8a2f1253'
  - 'source:coachctl-strava-training-agent-7a3ae9ac'
  - 'source:opencode-json-a0cbc058'
  - 'source:pyproject-0d00c775'
  - 'source:skill-show-dashboard-cf665da6'
schema_hash: 874431dbbfdec0b254a4aa1bf002900574c9b485735a883690c2becb5f717720
source_hashes:
  coachctl-architecture-conventions-8a2f1253: 8a2f1253f49141594869f6e383c7fc66793a5be531cf71c84bd04d41d26b98a5
  coachctl-strava-training-agent-7a3ae9ac: 7a3ae9ac2245b81e6b8266fe7349bbaf1bad2a1e4cb89accdef9dcd0dca67412
  opencode-json-a0cbc058: a0cbc058f08f809a1e8b3a66ecb90128f0f570a860da50943e25cd316efb015e
  pyproject-0d00c775: 0d00c7757bc8936d6b844bf5842c6d0ed1e809cb07d8001fc8295595deac950e
  skill-show-dashboard-cf665da6: cf665da67ae425649a4bcf1b9c0ac35004e5cce082c0dd85f0a1ecd7bb12ebaf
source_semantic_hashes:
  coachctl-architecture-conventions-8a2f1253: 4640b691098a69816f4ddf9045ff7f8a0fa3148b3658f0c34fce533b4223ab1b
  coachctl-strava-training-agent-7a3ae9ac: 571fd3b7d9213a3df91b8b96fc33f430a32181629f2536f9decd371c91bb8f56
  opencode-json-a0cbc058: a0cbc058f08f809a1e8b3a66ecb90128f0f570a860da50943e25cd316efb015e
  pyproject-0d00c775: 0d00c7757bc8936d6b844bf5842c6d0ed1e809cb07d8001fc8295595deac950e
  skill-show-dashboard-cf665da6: a1fdb8695f52bd117640c594a166de3262dab79560ed3e4a302db30d1d3fa726
decay_score: 1
last_confirmed_at: '2026-05-11T08:45:13.849Z'
---
# coachctl

## Summary

Frequently referenced concept in coachctl — Architecture & Conventions.

## Seen In

- [[sources/coachctl-architecture-conventions-8a2f1253|coachctl — Architecture & Conventions]]
- [[sources/coachctl-strava-training-agent-7a3ae9ac|coachctl — Strava Training Agent]]
- [[sources/opencode-json-a0cbc058|opencode.json]]
- [[sources/pyproject-0d00c775|pyproject]]
- [[sources/skill-show-dashboard-cf665da6|Skill: show-dashboard]]

## Source Claims

- coachctl — Architecture & Conventions Canonical reference for the project's structure, knowledge layers, and conventions. [source:coachctl-architecture-conventions-8a2f1253]
- --- ## Two-repo split coachctl is published as two coupled repos : | Repo | Visibility | Contents | Watcher | |---|---|---|---| | coachctl (this repo) | public | code, general knowledge, dashboard UI source, public race captures | — | | coachctl-personal (per-athlete) | private | one athlete's wiki, secrets, activities DB, baked dashboard data, Vercel deploy surface | Vercel auto-deploy | Dependency direction is strictly one-way : the private repo depends on the public one via pip install . [source:coachctl-architecture-conventions-8a2f1253]
- coachctl — Strava Training Agent MCP server + OpenCode agent + dashboard for analysing Strava training data and generating periodized training plans. [source:coachctl-strava-training-agent-7a3ae9ac]
- { "$schema": "https://opencode.ai/config.json", "mcp": { "coachctl": { "type": "local", "command": ["uv", "run", "coachctl", "serve"], "environment": { "AGENT_DATA_ROOT": "{env:AGENT_DATA_ROOT}", "STRAVA_PROFILE": "{env:STRAVA_PROFILE}" }, "enabled": true }, "garmin": { "type": "local", "command": [" /.venv/bin/garmin-mcp"], "enabled": false }, "coros": { "type": "local", "command": [" /.venv/bin/coros-mcp", "serve"], "enabled": false } } } [source:opencode-json-a0cbc058]
- pyproject Format: TOML Top-level: object Size: 2 Nested depth: 5 ## Schema - project: object (7 keys) - tool: object (4 keys) ## Preview toml [project] name = "coachctl" version = "0.1.0" description = "coachctl — endurance training coach (MCP server + dashboard)" requires-python = ">=3.11" dependencies = [ "mcp>=1.0.0", "httpx>=0.27.0", "pyyaml>=6.0.2", "python-dotenv>=1.0.0", "jinja2>=3.1.0", "typer>=0.12", ] [project.optional-dependencies] dashboard = [ "fastapi>=0.110", "uvicorn>=0.27", ] dev = [ "pytest>=8.0", "pytest-cov>=5.0", "pytest-asyncio>=0.23", "httpx>=0.27.0", ] [project.scripts] coachctl = "coachctl.cli:main" [tool.setuptools.package-data] "coachctl.dashboard" = ["app.html"] [tool.pytest.ini_options] testpaths = ["tests"] addopts = "-v --cov=src/coachctl --cov-report=term-missing" asyncio_mode = "auto" [tool.coverage.run] source = ["src/coachctl"] omit = ["*/dashboard/__main__.py", "*/cli.py", "*/update.py", "*/new_profile.py"] … [source:pyproject-0d00c775]
- description: Open the coachctl dashboard locally in the browser. [source:skill-show-dashboard-cf665da6]
- # Skill: show-dashboard ## What I do Bake fresh dashboard data and open the coachctl dashboard in the browser. [source:skill-show-dashboard-cf665da6]

