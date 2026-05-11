---
page_id: 'module:swarmvault-graph-first-01587800'
kind: module
cssclasses:
  - swarmvault
  - sv-module
title: swarmvault-graph-first module
source_class: first_party
tags:
  - module
  - code
  - javascript
source_ids:
  - swarmvault-graph-first-01587800
project_ids: []
node_ids:
  - 'module:swarmvault-graph-first-01587800'
  - 'symbol:swarmvault-graph-first-01587800:markerstate.function'
  - 'symbol:swarmvault-graph-first-01587800:isreportpath.function'
  - 'symbol:swarmvault-graph-first-01587800:collectcandidatepaths.function'
  - 'symbol:swarmvault-graph-first-01587800:resolveinputcwd.function'
  - 'symbol:swarmvault-graph-first-01587800:resolvetoolname.function'
  - 'symbol:swarmvault-graph-first-01587800:hasreport.function'
  - 'symbol:swarmvault-graph-first-01587800:artifactrootdir.function'
  - 'symbol:swarmvault-graph-first-01587800:reportpath.function'
  - 'symbol:swarmvault-graph-first-01587800:markreportread.function'
  - 'symbol:swarmvault-graph-first-01587800:hasseenreport.function'
  - 'symbol:swarmvault-graph-first-01587800:resetsession.function'
  - 'symbol:swarmvault-graph-first-01587800:isbroadsearchtool.function'
  - 'symbol:swarmvault-graph-first-01587800:collectcommandcandidates.function'
  - 'symbol:swarmvault-graph-first-01587800:commandlookslikebroadsearch.function'
  - 'symbol:swarmvault-graph-first-01587800:isbroadsearchinput.function'
  - 'symbol:swarmvault-graph-first-01587800:readhookinput.function'
  - 'symbol:swarmvault-graph-first-01587800:report-note.variable'
  - 'symbol:swarmvault-graph-first-01587800:agent-key.variable'
  - 'symbol:swarmvault-graph-first-01587800:emit.function'
  - 'symbol:swarmvault-graph-first-01587800:main.function'
freshness: fresh
status: active
confidence: 1
created_at: '2026-05-11T08:45:09.688Z'
updated_at: '2026-05-11T08:45:09.688Z'
compiled_from:
  - swarmvault-graph-first-01587800
managed_by: system
backlinks:
  - 'source:swarmvault-graph-first-01587800'
schema_hash: 874431dbbfdec0b254a4aa1bf002900574c9b485735a883690c2becb5f717720
source_hashes:
  swarmvault-graph-first-01587800: 01587800fd2d6a8c0efc962c2de5c3d82656e57e70163377e473316da2c5c650
source_semantic_hashes:
  swarmvault-graph-first-01587800: 01587800fd2d6a8c0efc962c2de5c3d82656e57e70163377e473316da2c5c650
related_page_ids:
  - 'source:swarmvault-graph-first-01587800'
related_node_ids: []
related_source_ids:
  - swarmvault-graph-first-01587800
language: javascript
decay_score: 1
last_confirmed_at: '2026-05-11T08:45:13.849Z'
---
# swarmvault-graph-first module

Source ID: `swarmvault-graph-first-01587800`
Source Path: `C:/Users/tieschy/workspace/coachctl/.claude/hooks/swarmvault-graph-first.js`
Repo Path: `.claude/hooks/swarmvault-graph-first.js`
Source Class: `first_party`
Language: `javascript`
Module Name: `.claude/hooks/swarmvault-graph-first`
Source Page: [[sources/swarmvault-graph-first-01587800|swarmvault-graph-first]]

## Summary

swarmvault-graph-first is a javascript module, defining 20 top-level symbol(s), exporting 0 symbol(s), depending on 4 external package import(s).

## Imports

- imports `crypto` (default `crypto`)
- imports `fs/promises` (default `fs`)
- imports `os` (default `os`)
- imports `path` (default `path`)

## Exports

- No exports detected.

## Symbols

- `markerState` (function): function markerState(cwd, agentKey)
- `isReportPath` (function): function isReportPath(value, cwd)
- `collectCandidatePaths` (function): function collectCandidatePaths(node, acc = [])
- `resolveInputCwd` (function): function resolveInputCwd(input)
- `resolveToolName` (function): function resolveToolName(input)
- `hasReport` (function): async function hasReport(cwd)
- `artifactRootDir` (function): function artifactRootDir(cwd)
- `reportPath` (function): function reportPath(cwd)
- `markReportRead` (function): async function markReportRead(cwd, agentKey)
- `hasSeenReport` (function): async function hasSeenReport(cwd, agentKey)
- `resetSession` (function): async function resetSession(cwd, agentKey)
- `isBroadSearchTool` (function): function isBroadSearchTool(toolName)
- `collectCommandCandidates` (function): function collectCommandCandidates(node, acc = [])
- `commandLooksLikeBroadSearch` (function): function commandLooksLikeBroadSearch(command)
- `isBroadSearchInput` (function): function isBroadSearchInput(input)
- `readHookInput` (function): async function readHookInput()
- `REPORT_NOTE` (variable): var REPORT_NOTE = "SwarmVault graph report exists at wiki/graph/report.md, or at $SWARMVAULT_OUT/wiki/graph/report.md when SWARMVAULT_OUT is set. Read it before broad grep/glob ...
- `AGENT_KEY` (variable): var AGENT_KEY = "claude";
- `emit` (function): function emit(value)
- `main` (function): async function main()

## External Dependencies

- `crypto`
- `fs/promises`
- `os`
- `path`

## Unresolved Local References

- No unresolved local references detected.

## Inheritance

- No inheritance relationships detected.

## Calls

- `isReportPath` calls `reportPath`
- `hasReport` calls `reportPath`
- `reportPath` calls `artifactRootDir`
- `markReportRead` calls `markerState`
- `hasSeenReport` calls `markerState`
- `resetSession` calls `markerState`
- `isBroadSearchInput` calls `resolveToolName`
- `isBroadSearchInput` calls `isBroadSearchTool`
- `isBroadSearchInput` calls `collectCommandCandidates`
- `main` calls `readHookInput`
- `main` calls `resolveInputCwd`
- `main` calls `hasReport`
- `main` calls `emit`
- `main` calls `resetSession`
- `main` calls `collectCandidatePaths`
- `main` calls `isReportPath`
- `main` calls `markReportRead`
- `main` calls `isBroadSearchInput`
- `main` calls `hasSeenReport`

## Diagnostics

- No parser diagnostics.

