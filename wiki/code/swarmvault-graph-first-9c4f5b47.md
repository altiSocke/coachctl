---
page_id: 'module:swarmvault-graph-first-9c4f5b47'
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
  - swarmvault-graph-first-9c4f5b47
project_ids: []
node_ids:
  - 'module:swarmvault-graph-first-9c4f5b47'
  - 'symbol:swarmvault-graph-first-9c4f5b47:markerstate.function'
  - 'symbol:swarmvault-graph-first-9c4f5b47:isreportpath.function'
  - 'symbol:swarmvault-graph-first-9c4f5b47:collectcandidatepaths.function'
  - 'symbol:swarmvault-graph-first-9c4f5b47:resolveinputcwd.function'
  - 'symbol:swarmvault-graph-first-9c4f5b47:resolvetoolname.function'
  - 'symbol:swarmvault-graph-first-9c4f5b47:hasreport.function'
  - 'symbol:swarmvault-graph-first-9c4f5b47:artifactrootdir.function'
  - 'symbol:swarmvault-graph-first-9c4f5b47:reportpath.function'
  - 'symbol:swarmvault-graph-first-9c4f5b47:markreportread.function'
  - 'symbol:swarmvault-graph-first-9c4f5b47:hasseenreport.function'
  - 'symbol:swarmvault-graph-first-9c4f5b47:resetsession.function'
  - 'symbol:swarmvault-graph-first-9c4f5b47:isbroadsearchtool.function'
  - 'symbol:swarmvault-graph-first-9c4f5b47:collectcommandcandidates.function'
  - 'symbol:swarmvault-graph-first-9c4f5b47:commandlookslikebroadsearch.function'
  - 'symbol:swarmvault-graph-first-9c4f5b47:isbroadsearchinput.function'
  - 'symbol:swarmvault-graph-first-9c4f5b47:readhookinput.function'
  - 'symbol:swarmvault-graph-first-9c4f5b47:report-note.variable'
  - 'symbol:swarmvault-graph-first-9c4f5b47:agent-key.variable'
  - 'symbol:swarmvault-graph-first-9c4f5b47:emit.function'
  - 'symbol:swarmvault-graph-first-9c4f5b47:note.function'
  - 'symbol:swarmvault-graph-first-9c4f5b47:main.function'
freshness: fresh
status: active
confidence: 1
created_at: '2026-05-11T08:45:09.689Z'
updated_at: '2026-05-11T08:45:09.689Z'
compiled_from:
  - swarmvault-graph-first-9c4f5b47
managed_by: system
backlinks:
  - 'source:swarmvault-graph-first-9c4f5b47'
schema_hash: 874431dbbfdec0b254a4aa1bf002900574c9b485735a883690c2becb5f717720
source_hashes:
  swarmvault-graph-first-9c4f5b47: 9c4f5b473ac374dfd70995cbda6d2ea03484c0dee57a85da4c48a9b7aa9348a6
source_semantic_hashes:
  swarmvault-graph-first-9c4f5b47: 9c4f5b473ac374dfd70995cbda6d2ea03484c0dee57a85da4c48a9b7aa9348a6
related_page_ids:
  - 'source:swarmvault-graph-first-9c4f5b47'
related_node_ids: []
related_source_ids:
  - swarmvault-graph-first-9c4f5b47
language: javascript
decay_score: 1
last_confirmed_at: '2026-05-11T08:45:13.849Z'
---
# swarmvault-graph-first module

Source ID: `swarmvault-graph-first-9c4f5b47`
Source Path: `C:/Users/tieschy/workspace/coachctl/.codex/hooks/swarmvault-graph-first.js`
Repo Path: `.codex/hooks/swarmvault-graph-first.js`
Source Class: `first_party`
Language: `javascript`
Module Name: `.codex/hooks/swarmvault-graph-first`
Source Page: [[sources/swarmvault-graph-first-9c4f5b47|swarmvault-graph-first]]

## Summary

swarmvault-graph-first is a javascript module, defining 21 top-level symbol(s), exporting 0 symbol(s), depending on 4 external package import(s).

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
- `AGENT_KEY` (variable): var AGENT_KEY = "codex";
- `emit` (function): function emit(value)
- `note` (function): function note()
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
- `main` calls `note`
- `main` calls `collectCandidatePaths`
- `main` calls `isReportPath`
- `main` calls `markReportRead`
- `main` calls `isBroadSearchInput`
- `main` calls `hasSeenReport`

## Diagnostics

- No parser diagnostics.

