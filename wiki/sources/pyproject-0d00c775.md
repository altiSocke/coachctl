---
page_id: 'source:pyproject-0d00c775'
kind: source
cssclasses:
  - swarmvault
  - sv-source
title: pyproject
source_class: first_party
tags:
  - source
source_ids:
  - pyproject-0d00c775
project_ids: []
node_ids:
  - 'source:pyproject-0d00c775'
  - 'concept:coachctl'
  - 'concept:dashboard'
  - 'concept:project'
  - 'concept:pytest'
  - 'concept:tool'
  - 'concept:object'
  - 'entity:format'
  - 'entity:top'
  - 'entity:size'
  - 'entity:nested'
  - 'entity:schema'
  - 'entity:preview'
freshness: fresh
status: active
confidence: 1
created_at: '2026-05-11T08:45:09.668Z'
updated_at: '2026-05-11T08:45:09.668Z'
compiled_from:
  - pyproject-0d00c775
managed_by: system
backlinks:
  - 'concept:coachctl'
  - 'concept:dashboard'
  - 'concept:project'
  - 'concept:pytest'
  - 'concept:tool'
  - 'concept:object'
  - 'entity:format'
  - 'entity:top'
  - 'entity:size'
  - 'entity:nested'
  - 'entity:schema'
  - 'entity:preview'
schema_hash: 874431dbbfdec0b254a4aa1bf002900574c9b485735a883690c2becb5f717720
source_hashes:
  pyproject-0d00c775: 0d00c7757bc8936d6b844bf5842c6d0ed1e809cb07d8001fc8295595deac950e
source_semantic_hashes:
  pyproject-0d00c775: 0d00c7757bc8936d6b844bf5842c6d0ed1e809cb07d8001fc8295595deac950e
decay_score: 1
last_confirmed_at: '2026-05-11T08:45:13.849Z'
---
# pyproject

Source ID: `pyproject-0d00c775`
Source Kind: `data`
Source Path: `C:/Users/tieschy/workspace/coachctl/pyproject.toml`

Source Class: `first_party`


## Source Details

- format: toml
- top level type: object
- top level size: 2
- nested depth: 5


## Summary

pyproject Format: TOML Top-level: object Size: 2 Nested depth: 5 ## Schema - project: object (7 keys) - tool: object (4 keys) ## Preview toml [project] name = "coachctl" version = "0.1.0" description = "coachctl — endurance training coach (MCP server + dashboard)" requires-python = ">=3.11" dependencies = [ "mcp>=1.0.0", "httpx>=0.27.0", "pyyaml>=6.0.2", "python-dotenv>=1.0.0", "jinja2>=3.1.0", "typer>=0.12", ] [project.optional-dependencies] dashboard = [ "fastapi>=0.110", "uvicorn>=0.27", ] dev = [ "pytest>=8.0", "pytest-cov>=5.0", "pytest-asyncio>=0.23", "httpx>=0.27.0", ] [project.scripts] coachctl = "coachctl.cli:main" [tool.setuptools.package-data] "coachctl.dashboard" = ["app.html"] [tool.pytest.ini_options] testpaths = ["tests"] addopts = "-v --cov=src/coachctl --cov-report=term-missing" asyncio_mode = "auto" [tool.coverage.run] source = ["src/coachctl"] omit = ["*/dashboard/__main__.py", "*/cli.py", "*/update.py", "*/new_profile.py"] …

## Concepts

- [[concepts/coachctl|coachctl]]: Frequently referenced concept in pyproject.
- [[concepts/dashboard|dashboard]]: Frequently referenced concept in pyproject.
- [[concepts/project|project]]: Frequently referenced concept in pyproject.
- [[concepts/pytest|pytest]]: Frequently referenced concept in pyproject.
- [[concepts/tool|tool]]: Frequently referenced concept in pyproject.
- [[concepts/object|object]]: Frequently referenced concept in pyproject.

## Entities

- [[entities/format|Format:]]: Named entity mentioned in pyproject.
- [[entities/top|Top-]]: Named entity mentioned in pyproject.
- [[entities/size|Size:]]: Named entity mentioned in pyproject.
- [[entities/nested|Nested]]: Named entity mentioned in pyproject.
- [[entities/schema|Schema -]]: Named entity mentioned in pyproject.
- [[entities/preview|Preview]]: Named entity mentioned in pyproject.

## Claims

- pyproject Format: TOML Top-level: object Size: 2 Nested depth: 5 ## Schema - project: object (7 keys) - tool: object (4 keys) ## Preview toml [project] name = "coachctl" version = "0.1.0" description = "coachctl — endurance training coach (MCP server + dashboard)" requires-python = ">=3.11" dependencies = [ "mcp>=1.0.0", "httpx>=0.27.0", "pyyaml>=6.0.2", "python-dotenv>=1.0.0", "jinja2>=3.1.0", "typer>=0.12", ] [project.optional-dependencies] dashboard = [ "fastapi>=0.110", "uvicorn>=0.27", ] dev = [ "pytest>=8.0", "pytest-cov>=5.0", "pytest-asyncio>=0.23", "httpx>=0.27.0", ] [project.scripts] coachctl = "coachctl.cli:main" [tool.setuptools.package-data] "coachctl.dashboard" = ["app.html"] [tool.pytest.ini_options] testpaths = ["tests"] addopts = "-v --cov=src/coachctl --cov-report=term-missing" asyncio_mode = "auto" [tool.coverage.run] source = ["src/coachctl"] omit = ["*/dashboard/__main__.py", "*/cli.py", "*/update.py", "*/new_profile.py"] … [source:pyproject-0d00c775]

## Questions

- How does coachctl relate to pyproject?
- How does dashboard relate to pyproject?
- How does project relate to pyproject?

