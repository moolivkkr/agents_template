# Harness and memory review: token reduction and code quality

Date: 2026-09-29. Scope: the `~/.claude` framework (41 `/startup` commands, 74 agents, skill packs, the memory protocols) as used on `rera` and `vertix`, compared against current open-source projects and Anthropic's own guidance. Target model: Claude Opus 5.5 for agents; Fable for the main session.

**Evidence limits.** Only 4 session transcripts for these projects survive on macm4 (Claude Code deletes them after 30 days), so there is no per-agent token breakdown yet. External benchmark numbers below are mostly vendor-run; they are labeled as such.

## Bottom line

The framework's design is sound and in places ahead of the open-source field (tiered memory, deterministic grep retrieval, a PageRank repo map, lesson-to-rule promotion). The biggest losses are not design gaps but plumbing: shared knowledge the agents are told to read does not resolve inside projects, the skill packs never load, and the main session carries very large command files on every request. Fixing plumbing first is cheap and should improve both token use and code quality; the one external tool worth piloting is a deterministic code graph on `vertix`, plus Anthropic's language-server plugins everywhere.

## Where tokens go today (measured)

| Item | Size | Loaded |
|---|---|---|
| Main session context per request | ~124k tokens average, 95% served from cache (4 sessions) | every request |
| `/develop` command file | ~31k tokens | every request while `/develop` runs in the main session |
| `/develop-orchestrator` | ~15k tokens | same |
| All 41 commands | ~178k tokens | per invocation |
| Global `~/.claude/CLAUDE.md` | ~2.4k tokens | every session and every subagent spawn |
| Skill packs listed by 40 agents | ~337k tokens if each agent read its list once | in practice, never (see F2) |

Cost is dominated by re-reading a large context on every request, not by output. Cache reads are cheap per token but multiply with context size and request count.

## Findings in the framework

**F1. Shared-file paths do not resolve inside projects (high impact, easy fix).** All 74 agents reference `.claude/skills/...` (project-relative), but the files live in `~/.claude/skills/`. In `rera`, `.claude/skills/core/agent-common.md`, `.claude/skills/core/shared-context-protocol.md` and every skill pack path are missing. Agents either skip the knowledge or spend Glob/Read calls hunting for it. Fix: rewrite references to `~/.claude/skills/...`, or convert the packs into real Skills (F2).

**F2. Skill packs never load (high impact).** `skill_packs:` is a custom frontmatter key; Claude Code ignores it, and no command or agent body instructs agents to read the listed files (only `/init` checks they exist). About 337k tokens of curated domain knowledge are effectively unused. Fix: convert packs into real Claude Code Skills (`skills/<name>/SKILL.md` with a `description` and, for language/framework/database packs, `paths:` globs). Skills load by relevance - only the description (capped at 1,536 characters) sits in context until a skill is used - so this adds knowledge without adding baseline tokens. Use the subagent `skills:` field only for the one or two packs an agent always needs, because preloading injects the full text.

**F3. The shared agent protocol never reached agents (fixed in pilot).** Subagents load only their own file plus CLAUDE.md. `agent-common.md` (Definition of Done, no self-correction, lessons, severity) was referenced 230+ times but never loaded. The pilot adds an inline operating contract, synced from one source by `~/.claude/agents/_sync-contract.sh`.

**F4. No agent defined its final message (fixed in pilot).** The orchestrator sees only a subagent's final message. The contract now fixes it to status, files written, gate counts, and blockers - Anthropic recommends subagents return a condensed summary of roughly 1-2k tokens.

**F5. Monolithic command files (medium-high impact).** `/develop` is 124 KB. Commands are now Skills in Claude Code: a skill directory can keep the core flow in `SKILL.md` and put per-wave detail in supporting files read only when that wave runs. Cutting ~25k tokens from a ~124k context removes about a fifth of input on every `/develop` request.

**F6. Effort was never set (fixed in pilot; roll out).** Opus 5.5 defaults to `medium`. Reviewers and security agents should run at `high`, writers at `medium`, mechanical runners at `low`.

**F7. No code intelligence installed.** `vertix` is 79k tracked files (21.7k Go, ~2k TS/TSX); `rera` is Python. No language server binaries are installed (`gopls`, `typescript-language-server`, `pyright` all missing), so agents navigate by grep and learn about type errors only by running builds.

**F8. Tier 2 memory is LLM-written and goes stale.** `/map` has `codebase_mapper` agents write markdown summaries into `agent_state/codebase/`. Research comparing codebase graphs found deterministic AST-derived graphs give better coverage and multi-hop grounding than LLM-extracted ones at much lower indexing cost. Keep the PageRank repo map (a benchmark found RepoMap gives the best context yield under an 8k-token budget), but back structural questions with a deterministic, auto-synced code graph instead of prose.

**F9. Context-warning hook should stay off.** `gsd-context-monitor.js` is copied but not wired in settings. Anthropic's guidance is that surfacing remaining-context counts to the model causes premature wrap-up; leave it disabled. The `gsd-*` hooks came from the original GSD project, which moved to community governance (open-gsd) in May 2026 after trust concerns - audit before enabling any of them.

**F10. Global CLAUDE.md rides along with every subagent.** It is loaded into all 74 agents on every spawn and is written in heavy `⛔ CRITICAL`/`MUST` register, which on current models increases over-cautious, rigid behavior. The "pre-approved commands" list restates what `settings.json` permissions already enforce. Trimming duplicated policy prose and restating the real constraints at normal volume, with reasons, reduces baseline tokens everywhere. (Edits to user-level files affect every project; propose, review, then apply.)

## External landscape

| Project / guidance | What it does | Evidence | Fit here | Recommendation |
|---|---|---|---|---|
| Anthropic code-intelligence plugins (`gopls-lsp`, `typescript-lsp`, `pyright-lsp`) | LSP go-to-definition/references and diagnostics after every edit | Official, maintained by Anthropic; docs cite fewer file reads and catching type errors without a build | Strong: Go/TS in vertix, Python in rera | **Adopt now** |
| CodeGraph (`colbymchenry/codegraph`, MIT, ~72k stars) | tree-sitter graph in local SQLite, file-watcher auto-sync, MCP `codegraph_explore` (symbols, call paths, impact) | Vendor benchmark, Opus 4.8, 7 repos, architecture Q&A: 88% fewer tool calls, 62% fewer tokens, 53% faster | Strong for vertix size; unmeasured for code generation | **Pilot on vertix, measure** |
| Serena (`oraios/serena`, MIT, ~25k) | LSP-backed symbolic retrieval and editing over MCP | Popular, no neutral benchmark | Overlaps with official LSP plugins plus a code graph | Skip unless symbolic editing is needed |
| RTK (`mvanhorn/rtk`) | Bash hook that rewrites commands through a compressing proxy | Claims 60-90% output reduction | Useful, but can hide output agents need (test failures) | Prefer a small own hook for test/log output; pilot RTK only after |
| claude-mem (~75k stars) | Records every session, compresses with an LLM, injects at session start | Popular; adds per-session LLM cost and automatic injection | Overlaps with your explicit lessons and `/remember`, less controllable | Skip |
| Graphiti/Zep, Cognee, Mem0 | Graph/vector memory services for entity and conversation facts | Vendor benchmarks, not comparable across vendors | Needs a graph DB; your durable facts are small and file-based | Skip |
| GSD (now open-gsd), Superpowers, Compound Engineering, BMAD, Spec Kit | Spec-driven workflows, fresh context per task, learning loops | Community frameworks | You already implement the useful parts (waves, fresh subagents, lessons, promotion) | Borrow ideas only; audit GSD hooks before use |
| Anthropic "code execution with MCP" | Load tool definitions on demand, process results in code | 150k to 2k tokens in their example | You run one MCP server; tool search is already on by default | Not needed now |
| Anthropic context-engineering guidance | Just-in-time retrieval, subagents returning condensed summaries, compaction and tool-result clearing | Official | Matches F2, F4, F5 | Applied in the plan below |

## Plan

**P0 - now (low risk, high value)**
1. Roll the Opus 5.5 pilot out to the remaining 71 agents: model, effort, descriptions, the operating contract, conflicts and emphasis cleanup.
2. Fix every `.claude/skills/...` reference to resolve (`~/.claude/skills/...`), in agents and commands.
3. Install language servers and plugins: `gopls` + `gopls-lsp`, `typescript-language-server` + `typescript-lsp`, `pyright` + `pyright-lsp`.

**P1 - next**
4. Convert skill packs to real Skills with descriptions and `paths:` globs; preload at most one or two per agent via `skills:`.
5. Split `/develop` and `/develop-orchestrator` into skill directories with per-wave supporting files.
6. Trim the global CLAUDE.md (duplicate permission prose, emphasis register); measure one `/develop` run before and after.

**P2 - measure first**
7. Pilot CodeGraph on vertix: run one `/map` + `/develop` phase with and without it; compare `/usage` attribution, tool calls, gate pass rate.
8. Add a small PreToolUse hook that trims test and log output to failures (the pattern in Anthropic's cost docs); consider RTK afterwards.
9. Keep evidence: raise `cleanupPeriodDays` (e.g. 90) on both Macs and check `/usage` attribution after each phase, so later changes can be measured per agent.

**Not recommended:** graph-memory databases, claude-mem, enabling the context-monitor hook.

## Sources

- Anthropic: [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents); [Code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp)
- Claude Code docs: [Subagents](https://code.claude.com/docs/en/sub-agents), [Skills](https://code.claude.com/docs/en/skills), [Manage costs](https://code.claude.com/docs/en/costs), [Code intelligence plugins](https://code.claude.com/docs/en/plugins/code-intelligence)
- Research: [AST-derived graphs vs LLM-extracted knowledge graphs for codebases (arXiv 2601.08773)](https://arxiv.org/abs/2601.08773); [Agent Retrieval Bench (arXiv 2607.24882)](https://arxiv.org/abs/2607.24882)
- Projects: [CodeGraph](https://github.com/colbymchenry/codegraph), [code-graph-mcp](https://github.com/sdsrss/code-graph-mcp), [tokensave](https://github.com/aovestdipaperino/tokensave), [Serena](https://mcp.directory/blog/serena-mcp-complete-guide-2026), [RTK](https://github.com/mvanhorn/rtk), [claude-mem](https://www.augmentcode.com/learn/claude-mem-74k-stars-agent-memory), [GSD](https://github.com/gsd-build/get-shit-done) and [framework comparison](https://reinvently.co.uk/blog/ai-dev-workflow-frameworks-gsd-bmad-openspec-speckit/), [agent memory comparison](https://codepointer.substack.com/p/agent-memory-systems-and-knowledge)
