---
description: SwarmVault graph-first repository instructions.
alwaysApply: true
---

<!-- swarmvault:managed:start -->
# SwarmVault Rules

- Read `swarmvault.schema.md` before compile or query style work. It is the canonical schema path.
- Treat `raw/` as immutable source input.
- Treat `wiki/` as generated markdown owned by the agent and compiler workflow.
- If `SWARMVAULT_OUT` is set, resolve generated artifact paths like `raw/`, `wiki/`, and `state/` under that directory.
- Read `wiki/graph/report.md` before broad file searching when it exists; otherwise start with `wiki/index.md`.
- For graph questions, prefer `swarmvault graph query`, `swarmvault graph path`, and `swarmvault graph explain` before broad grep/glob searching.
- Preserve frontmatter fields including `page_id`, `source_ids`, `node_ids`, `freshness`, and `source_hashes`.
- Save high-value answers back into `wiki/outputs/` instead of leaving them only in chat.
- Prefer `swarmvault ingest`, `swarmvault compile`, `swarmvault query`, and `swarmvault lint` for SwarmVault maintenance tasks.
<!-- swarmvault:managed:end -->
