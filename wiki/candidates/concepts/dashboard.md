---
page_id: 'concept:dashboard'
kind: concept
cssclasses:
  - swarmvault
  - sv-concept
title: dashboard
source_class: first_party
tags:
  - concept
  - candidate
source_ids:
  - pyproject-0d00c775
  - skill-show-dashboard-cf665da6
project_ids: []
node_ids:
  - 'concept:dashboard'
freshness: fresh
status: candidate
confidence: 0.8
created_at: '2026-05-11T08:45:09.831Z'
updated_at: '2026-05-11T08:45:09.831Z'
compiled_from:
  - pyproject-0d00c775
  - skill-show-dashboard-cf665da6
managed_by: system
backlinks:
  - 'source:pyproject-0d00c775'
  - 'source:skill-show-dashboard-cf665da6'
schema_hash: 874431dbbfdec0b254a4aa1bf002900574c9b485735a883690c2becb5f717720
source_hashes:
  pyproject-0d00c775: 0d00c7757bc8936d6b844bf5842c6d0ed1e809cb07d8001fc8295595deac950e
  skill-show-dashboard-cf665da6: cf665da67ae425649a4bcf1b9c0ac35004e5cce082c0dd85f0a1ecd7bb12ebaf
source_semantic_hashes:
  pyproject-0d00c775: 0d00c7757bc8936d6b844bf5842c6d0ed1e809cb07d8001fc8295595deac950e
  skill-show-dashboard-cf665da6: a1fdb8695f52bd117640c594a166de3262dab79560ed3e4a302db30d1d3fa726
decay_score: 1
last_confirmed_at: '2026-05-11T08:45:13.849Z'
---
# dashboard

## Summary

Frequently referenced concept in pyproject.

## Seen In

- [[sources/pyproject-0d00c775|pyproject]]
- [[sources/skill-show-dashboard-cf665da6|Skill: show-dashboard]]

## Source Claims

- pyproject Format: TOML Top-level: object Size: 2 Nested depth: 5 ## Schema - project: object (7 keys) - tool: object (4 keys) ## Preview toml [project] name = "coachctl" version = "0.1.0" description = "coachctl — endurance training coach (MCP server + dashboard)" requires-python = ">=3.11" dependencies = [ "mcp>=1.0.0", "httpx>=0.27.0", "pyyaml>=6.0.2", "python-dotenv>=1.0.0", "jinja2>=3.1.0", "typer>=0.12", ] [project.optional-dependencies] dashboard = [ "fastapi>=0.110", "uvicorn>=0.27", ] dev = [ "pytest>=8.0", "pytest-cov>=5.0", "pytest-asyncio>=0.23", "httpx>=0.27.0", ] [project.scripts] coachctl = "coachctl.cli:main" [tool.setuptools.package-data] "coachctl.dashboard" = ["app.html"] [tool.pytest.ini_options] testpaths = ["tests"] addopts = "-v --cov=src/coachctl --cov-report=term-missing" asyncio_mode = "auto" [tool.coverage.run] source = ["src/coachctl"] omit = ["*/dashboard/__main__.py", "*/cli.py", "*/update.py", "*/new_profile.py"] … [source:pyproject-0d00c775]
- description: Open the coachctl dashboard locally in the browser. [source:skill-show-dashboard-cf665da6]
- Bakes fresh data, checks if the dev server is already running, starts it if not, then navigates the browser to the dashboard. [source:skill-show-dashboard-cf665da6]
- Use when the athlete asks to see, open, or show the dashboard. [source:skill-show-dashboard-cf665da6]
- # Skill: show-dashboard ## What I do Bake fresh dashboard data and open the coachctl dashboard in the browser. [source:skill-show-dashboard-cf665da6]

