# Track D: memory, context engineering, code understanding (checked 2026-10-02)

**The lens.** We measured on rera that every API step re-sends about 35–40k tokens of fixed context
(system prompt, tools, CLAUDE.md), so total tokens ≈ steps × fixed context. Adding a retrieval step cost
+32% (`docs/evals/graph-find/`), and slimming CLAUDE.md from 62 KB to 12.7 KB saved 44%
(`docs/evals/claude-md-slim/`). Anthropic's own Claude Code docs now describe the same mechanism:
"Claude Code sends your full conversation with every request… re-reads that history at the cached token
rate" (https://code.claude.com/docs/en/costs). A 2026 preprint also finds agent failure tracks **step
count** more than context length (arXiv 2609.01660, Mittal, 2026-08-31). Both point the same way: the
levers are **fewer steps** and **less fixed context per step**, not more retrieval.

Our biggest finding is not outside the repo. **Our subagents carry the most fixed context, and Claude Code
now has first-party switches to cut it that we don't use.** None of our 69 core agents sets `omitClaudeMd`,
`skills`, `memory`, `maxTurns` or `experimental.cacheTtl` in its frontmatter (`git grep` on main; 0 hits each).
Every agent also opens with Required Reading 0/0b, which reads all of `docs/PROJECT_FACTS.md` (35 KB on
rera) and `docs/DECISIONS.md`, and those tokens then ride along on every later step.

## 1. Capability table

| Capability | Who does it best (how, URL, checked 2026-10-02) | Do we have it? | Value | Effort | Risk / caveats |
|---|---|---|---|---|---|
| **Per-subagent fixed-context control** | Claude Code subagent frontmatter. `omitClaudeMd: true` skips the user, project and local CLAUDE.md (v2.1.271+). `skills:` preloads full skill content at startup. `SubagentStart` hooks can return `additionalContext`. Sources: https://code.claude.com/docs/en/sub-agents, https://code.claude.com/docs/en/hooks | **No.** 0 agents use these. Every agent Reads PROJECT_FACTS + DECISIONS in full (e.g. `.claude/agents/core/code_reviewer_I.md:35-36`) | **H** | M | `omitClaudeMd` also drops `~/.claude/CLAUDE.md`, which holds the owner's honesty rules. Re-inject a digest. Our skill packs are plain `.md`, not Claude Code skills, so `skills:` needs a format change. Must be A/B'd: our 7.7% "verbose wins" finding covers task context, not boilerplate |
| **Path-scoped instructions** | Claude Code `.claude/rules/*.md` with `paths:` frontmatter. These load only when Claude reads matching files. `@imports` do NOT reduce cost, because they load at launch. Docs say keep CLAUDE.md under 200 lines, and Claude Code warns above that. https://code.claude.com/docs/en/memory | **No.** No `.claude/rules/` in the template. The slim-CLAUDE.md fix moved runbooks to `docs/ops/` behind an index, which costs a Read step when needed | **H** | S | Rules trigger on file reads, not on topics, so they only fit file-scoped guidance (migrations, k8s, mobile, RLS policies). Topic runbooks stay in `docs/ops` |
| **Prompt-cache hygiene** | Claude Code. Subagents default to a **5-min** TTL even on a subscription. The per-agent `experimental.cacheTtl: 1h` needs v2.1.248+. Workflow fan-outs hold siblings ≤5 s so they read the first agent's cache. `/usage` shows a "Prompt cache (main)" line with misses and their likely cause. Switching models, effort or MCP tools mid-session invalidates the cache. https://code.claude.com/docs/en/prompt-caching. Design notes: https://claude.dev/blog/lessons-from-building-claude-code-prompt-caching-is-everything | **Partial.** The eval harness pins the TTL (`scripts/eval-question-tokens.py:111`). The pipeline does nothing | M | S | 1h writes bill at a higher rate, so only worth it for agents that idle past 5 min between steps (test runs, deploys, device boots). Whether sibling subagents share a prefix is unverified (see §4) |
| **Context editing / server compaction** | Claude API. `clear_tool_uses_20250919` (trigger, keep, `clear_at_least`, `exclude_tools`), `clear_thinking_20251015`, and on-demand compaction under the `compact-2026-09-04` beta. Clearing **invalidates the cache**, so `clear_at_least` exists to make each clearing worth it. https://platform.claude.com/docs/en/build-with-claude/context-editing, https://platform.claude.com/docs/en/build-with-claude/compaction | **N/A today.** We run inside Claude Code, which compacts by itself. Matters only if the `/autonomous` supervisor moves to an Agent SDK loop | L now (M if we go SDK) | M | API-level only |
| **Handoff instead of compaction** | Amp replaced compaction with `/handoff` (Jan 2026): a new thread with a stated goal and selected files, which the user reviews. Rationale: compaction is lossy and encourages long threads. https://ampcode.com/news (direct page returned a header error; corroborated via hackernoon coverage) | **Partial.** `checkpoints/compact-context.md` at every wave boundary plus `/resume`. "Fresh session per phase" is a known open item | M | M | Amp's quality claim is the vendor's. The step-count preprint supports short sessions |
| **Pre/post-compaction hooks** | Claude Code `PreCompact` (can block), `PostCompact` (observe only), and `SessionStart` with matcher `compact` (can inject). https://code.claude.com/docs/en/hooks | **Yes.** `SessionStart` `compact\|resume` re-injects facts (`.claude/settings.json`) | — | — | — |
| **Bi-temporal facts** | Graphiti/Zep track four timestamps per edge (valid_at, invalid_at, created_at, expired_at). A contradiction invalidates the old edge instead of deleting it, and retrieval is hybrid (embeddings + BM25 + graph). 31.4k stars, Apache-2.0, **telemetry opt-out (on by default)**. https://github.com/getzep/graphiti | **Yes, safer.** Deterministic `(subject, relation)` supersession with `valid_from`/`invalid_at`/`superseded_by` (`.claude/skills/core/shared-context-protocol.md:95-105`). We have no separate *recorded-at* (transaction time) | L | S | The README doesn't say how contradictions are detected (unverified; secondary sources say an LLM does it). Ours never invalidates on a semantic guess, so keep it |
| **Memory layers (mem0, Zep, Cognee, LangMem)** | Active repos: mem0 66.5k stars, Cognee 31.3k, LangMem 1.7k (GitHub API). Benchmarks are **disputed**: Zep and mem0 each published corrections of the other's LoCoMo numbers (https://blog.getzep.com/lies-damn-lies-statistics-is-mem0-really-sota-in-agent-memory/). Letta got 74.0% on LoCoMo with plain files vs mem0's reported 68.5% (https://www.letta.com/blog/benchmarking-ai-agent-memory, Aug 2025) | We have file-based tiers, which is what the Letta result favours | L | — | Chat-memory benchmarks, not SDLC. mem0's "90% fewer tokens" is measured against stuffing full history into context, not against an agent that already greps files |
| **Git-versioned memory with an always/on-demand split + background consolidation** | Letta Code MemFS ("context repository"). `system/` files are always loaded. Other files show only as a tree of names and descriptions until opened. Memory is git-committed, and "sleep-time/dream" subagents consolidate it in the background. https://docs.letta.com/letta-code/memfs, https://www.letta.com/blog/context-repositories | **Mostly yes.** Tier 0 headings always load, lessons load on demand, `/consolidate` runs off-path, and it's all in git | L | — | Letta's background agents run "for many steps", which costs tokens. Ours runs on demand |
| **Incremental "playbook" updates that avoid collapse** | ACE (ICLR 2026, arXiv 2510.04618). Itemised bullets with helpful/harmful counters, updated as deltas, never by wholesale rewrite. The paper shows "context collapse": a context went from 18,282 to 122 tokens in one rewrite and accuracy fell from 66.7 to 57.1. https://arxiv.org/abs/2510.04618 | **Partial.** `/consolidate` step 3 *compresses* `Detail:` prose with an LLM (`.claude/commands/consolidate.md:66`). `applies_when`/`retire_when` is a known open item | M | S | ACE's playbooks *grow* and it ignores per-step re-send cost. Borrow the delta and counter mechanics, not the "bigger context" stance |
| **Code navigation via LSP** | Claude Code official LSP plugins for 13 languages: a read-only `LSP` tool plus **diagnostics after every edit**. https://code.claude.com/docs/en/plugins/code-intelligence. **Independent counter-evidence:** arXiv 2608.13568 (Xu, 2026-06-29) measured LSP **+6% to +118% tokens** vs grep on symbol localization. A location-only LSP failed ¾ of multi-file renames that grep solved. Savings appeared only with the weakest model | **Partial.** Templates mention "LSP diagnostics" (`.claude/agents/templates/backend_developer.tmpl:196`). Repo-map rung ladder in `codebase_mapper.md:171`. Plugins aren't part of `/init` | M | S | One preprint, one author, called "preliminary". Its result matches ours: a lookup that adds a step doesn't pay off with a strong model |
| **Serena (LSP over MCP)** | 29.9k stars, active. GitHub API reports the license as "Other", although secondary sources say MIT (**unverified**). Token-saving claims carry no benchmark numbers (https://rywalker.com/research/serena) | No | L | M | An MCP server adds tool listings and steps. The first-party plugin covers the same ground |
| **Augment Context Engine (MCP)** | Launched Feb 2026. Vendor claims +70–80% quality on 300 Elasticsearch PRs, 900 attempts (https://www.augmentcode.com/blog/context-engine-mcp-now-live) | No | L | — | Vendor benchmark. Code is indexed in their cloud. Conflicts with the supply-chain rule and with tenant data |
| **Ranked repo map** | Aider: tree-sitter tags plus graph ranking, `--map-tokens` default 1k, grows when no files are in chat. https://aider.chat/docs/repomap.html | **Yes** (`codebase_mapper.md` Phase 4, `/map` 2.5) | — | — | — |
| **stack-graphs** | GitHub **archived it on 2025-09-09** ("no longer supported"). https://github.com/github/stack-graphs | No | — | — | Don't build on it |
| **Instruction-file audit** | Claude Code `/doctor prompt-audit` (v2.1.283+). Finds stale, contradictory or missing-reference instructions across CLAUDE.md, rules, skills, commands and subagents, and proposes edits only. https://code.claude.com/docs/en/memory | **Partial.** `/health` 5.5f checks facts. Nothing audits ~90 agents and ~230 skills for contradictions | M | S | Runs through the bundled claude-api skill. Report-only |
| **Turn bounds per agent** | Claude Code `maxTurns` frontmatter. The step-count decay law (arXiv 2609.01660) argues for budgets per step | **No** (0 agents) | M | S | A hard stop mid-task must map to a typed failure, not a silent partial |

## 2. Strongest recommendations

**R1. A lean subagent prelude, measured before it ships (H, M).**
- What we'd build:
  - A `SubagentStart` hook that injects the same active fact and decision *headings* the session hook already prints.
  - Required Reading 0/0b changes from "Read the file" to "Read the entry when your task names its subject".
  - `omitClaudeMd: true` on pipeline agents that receive `phase_context.md` (developers, testers, reviewers), plus a 5-line digest of the owner's global rules.
- How to test: A/B on a frozen rera phase with the `eval-question-tokens.py` method, plus `/eval` outcome scores. Keep it only if tokens fall ≥20% and outcome holds.

**R2. Path-scoped rules from `/init` (H, S).**
- `/init` writes `.claude/rules/{migrations,k8s,mobile,rls,…}.md` with `paths:` globs, taken from the guidelines' file-scoped constraints.
- `/health` warns when CLAUDE.md passes 200 lines.
- This extends the measured −44% result without adding a Read step: the rule arrives with the file the agent was already reading.

**R3. Cache hygiene in the orchestrator (M, S).**
- Set `experimental.cacheTtl: 1h` only on agents that wait more than 5 min between steps: `test_runner`, `e2e_orchestrator`, `mobile_e2e_orchestrator`, `deployment_agent`, `performance_agent`.
- Have `ledger.py` record each subagent's `cache_read` and `cache_creation` from its transcript, so a cache-miss regression (for example a mid-wave model or effort switch) shows up in the phase ledger.
- Then test whether spawning one same-type agent first and its siblings a few seconds later raises cache reads.

**R4. Use LSP for diagnostics, grep for navigation (M, S).**
- `/init` installs the official LSP plugin for the stack (pyright, typescript, gopls), so developer agents get type errors after every edit at no step cost.
- Do **not** route reviewers' searches through LSP by default, because the preprint and our graph eval both show added steps.
- Use `findReferences` only in `breaking_change_reviewer`'s consumer checks.

**R5. ACE-style delta lessons (M, S).**
- Replace `/consolidate` step 3 (LLM compression) with append-only deltas.
- Each lesson bullet gets `helpful`/`harmful` counters bumped at gates, plus `applies_when`/`retire_when`.
- A lesson is retired by counter, not rewritten. This closes the existing open item with published evidence that rewrites lose detail.

## 3. Do NOT copy

- **External memory stores** (mem0, Zep, Cognee, LangMem) as our memory tier. The benchmarks are mutually disputed, plain files did as well, and each adds a retrieval step. Graphiti also ships with telemetry on.
- **Serena or Augment MCP as default navigation.** Their claims count the file-read tokens they avoid but ignore the extra step and its re-sent fixed context. Augment's code also leaves the machine.
- **Claude Code's own "one go-to-definition replaces grep + reads" claim** (costs page) taken as fact. The one independent measurement contradicts it for strong models.
- **API context editing inside Claude Code sessions.** It isn't exposed there, and clearing invalidates the cache.
- **Letta-style always-running sleep-time agents.** They spend many steps continuously, while our `/consolidate` runs on demand.
- **Building on stack-graphs** (archived).

## 4. Unverified

- Whether sibling subagents of the same type share a cached prefix. Their task messages differ, and the git status snapshot may differ too.
- The real per-step saving of `omitClaudeMd` and of fact-heading injection in our pipeline (not measured).
- How Graphiti detects contradictions (LLM or not; the README is silent).
- Serena's license (the GitHub API says "Other").
- Amp's handoff page content: fetched only through secondary coverage.
- arXiv 2608.13568 and 2609.01660 are single-author preprints and not peer-reviewed.
- The Augment, mem0 and Zep benchmark figures are all vendor claims.
