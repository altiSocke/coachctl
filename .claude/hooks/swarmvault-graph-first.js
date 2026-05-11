#!/usr/bin/env node

// src/hooks/marker-state.ts
import crypto from "crypto";
import fs from "fs/promises";
import os from "os";
import path from "path";
function markerState(cwd, agentKey) {
  const hash = crypto.createHash("sha256").update(cwd).digest("hex");
  const dir = path.join(os.tmpdir(), "swarmvault-agent-hooks", agentKey, hash);
  return {
    dir,
    markerPath: path.join(dir, "report-read")
  };
}
function isReportPath(value, cwd) {
  if (typeof value !== "string" || value.length === 0) {
    return false;
  }
  const reportSuffix = path.join("wiki", "graph", "report.md");
  const normalized = value.replaceAll("\\", "/");
  const reportNormalized = reportSuffix.replaceAll("\\", "/");
  if (normalized.endsWith(reportNormalized)) {
    return true;
  }
  return path.resolve(cwd, value) === reportPath(cwd);
}
function collectCandidatePaths(node, acc = []) {
  if (typeof node === "string") {
    acc.push(node);
    return acc;
  }
  if (!node || typeof node !== "object") {
    return acc;
  }
  if (Array.isArray(node)) {
    for (const item of node) {
      collectCandidatePaths(item, acc);
    }
    return acc;
  }
  for (const [key, value] of Object.entries(node)) {
    if (["path", "filePath", "file_path", "paths", "target", "targets"].includes(key)) {
      collectCandidatePaths(value, acc);
      continue;
    }
    collectCandidatePaths(value, acc);
  }
  return acc;
}
function resolveInputCwd(input) {
  const shaped = input ?? {};
  const candidate = typeof shaped.cwd === "string" && shaped.cwd || typeof shaped.directory === "string" && shaped.directory || typeof shaped.workspace?.cwd === "string" && shaped.workspace.cwd || typeof shaped.toolInput?.cwd === "string" && shaped.toolInput.cwd || process.cwd();
  return path.resolve(candidate);
}
function resolveToolName(input) {
  const shaped = input ?? {};
  return String(shaped.toolName ?? shaped.tool_name ?? shaped.tool?.name ?? shaped.name ?? "");
}
async function hasReport(cwd) {
  try {
    await fs.access(reportPath(cwd));
    return true;
  } catch {
    return false;
  }
}
function artifactRootDir(cwd) {
  const override = process.env.SWARMVAULT_OUT?.trim();
  if (!override) {
    return path.resolve(cwd);
  }
  return path.isAbsolute(override) ? path.resolve(override) : path.resolve(cwd, override);
}
function reportPath(cwd) {
  return path.join(artifactRootDir(cwd), "wiki", "graph", "report.md");
}
async function markReportRead(cwd, agentKey) {
  const state = markerState(cwd, agentKey);
  await fs.mkdir(state.dir, { recursive: true });
  await fs.writeFile(state.markerPath, "seen\n", "utf8");
}
async function hasSeenReport(cwd, agentKey) {
  const state = markerState(cwd, agentKey);
  try {
    await fs.access(state.markerPath);
    return true;
  } catch {
    return false;
  }
}
async function resetSession(cwd, agentKey) {
  const state = markerState(cwd, agentKey);
  await fs.rm(state.dir, { recursive: true, force: true });
}
function isBroadSearchTool(toolName) {
  return /grep|glob|search|find/i.test(toolName);
}
function collectCommandCandidates(node, acc = []) {
  if (!node || typeof node !== "object") {
    return acc;
  }
  if (Array.isArray(node)) {
    for (const item of node) {
      collectCommandCandidates(item, acc);
    }
    return acc;
  }
  for (const [key, value] of Object.entries(node)) {
    if (["command", "cmd", "script", "bash", "shell"].includes(key) && typeof value === "string") {
      acc.push(value);
      continue;
    }
    collectCommandCandidates(value, acc);
  }
  return acc;
}
function commandLooksLikeBroadSearch(command) {
  const tokens = command.replace(/[;&|()]/g, " ").split(/\s+/).map((token) => path.basename(token.replace(/^['"]|['"]$/g, ""))).filter(Boolean);
  for (let index = 0; index < tokens.length; index += 1) {
    const token = tokens[index];
    if (["rg", "grep", "find", "fd", "ag", "ack"].includes(token)) {
      return true;
    }
    if (token === "git" && tokens[index + 1] === "grep") {
      return true;
    }
  }
  return false;
}
function isBroadSearchInput(input) {
  const toolName = resolveToolName(input);
  if (isBroadSearchTool(toolName)) {
    return true;
  }
  return collectCommandCandidates(input).some(commandLooksLikeBroadSearch);
}
async function readHookInput() {
  let body = "";
  for await (const chunk of process.stdin) {
    body += chunk;
  }
  if (!body.trim()) {
    return {};
  }
  try {
    return JSON.parse(body);
  } catch {
    return {};
  }
}
var REPORT_NOTE = "SwarmVault graph report exists at wiki/graph/report.md, or at $SWARMVAULT_OUT/wiki/graph/report.md when SWARMVAULT_OUT is set. Read it before broad grep/glob searching.";

// src/hooks/claude.ts
var AGENT_KEY = "claude";
function emit(value) {
  process.stdout.write(`${JSON.stringify(value)}
`);
}
async function main() {
  const mode = process.argv[2] ?? "";
  const input = await readHookInput();
  const cwd = resolveInputCwd(input);
  if (!await hasReport(cwd)) {
    emit({});
    process.exit(0);
  }
  if (mode === "session-start") {
    await resetSession(cwd, AGENT_KEY);
    emit({
      hookSpecificOutput: {
        hookEventName: "SessionStart",
        additionalContext: REPORT_NOTE
      }
    });
    process.exit(0);
  }
  if (collectCandidatePaths(input).some((value) => isReportPath(value, cwd))) {
    await markReportRead(cwd, AGENT_KEY);
    emit({});
    process.exit(0);
  }
  if (isBroadSearchInput(input) && !await hasSeenReport(cwd, AGENT_KEY)) {
    emit({
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        additionalContext: REPORT_NOTE
      }
    });
    process.exit(0);
  }
  emit({});
}
await main();
