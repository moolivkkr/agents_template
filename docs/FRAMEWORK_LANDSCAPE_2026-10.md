# Framework landscape review — what we're missing (2026-10-02)

Six parallel research tracks compared startup-agents with the current state of the art. Every external
claim was checked against a source on 2026-10-02 (URLs in the track reports), and every "gap" was checked
against `main` before it was called one. Vendor numbers are labelled as such. This review builds on
[FRAMEWORK_REVIEW_2026-09-30.md](FRAMEWORK_REVIEW_2026-09-30.md) §2–3 and does not repeat it.

| Track | Scope | Report |
|---|---|---|
| A | Autonomous coding agents (Devin, Codex, Jules, Copilot, Cursor, Factory, Amp, OpenHands, Aider, …) and new Claude Code features | [A-coding-agents.md](research/landscape-2026-10/A-coding-agents.md) |
| B | Orchestration frameworks (LangGraph, MAF, ADK, CrewAI, OpenAI Agents SDK, Temporal/DBOS/Inngest/Restate, Mastra, DSPy) | [B-orchestration.md](research/landscape-2026-10/B-orchestration.md) |
| C | Spec-driven SDLC frameworks (Kiro, Spec Kit, OpenSpec, BMAD, cc-sdd, Tessl, Agent OS, …) | [C-spec-sdlc.md](research/landscape-2026-10/C-spec-sdlc.md) |
| D | Memory, context engineering, code intelligence | [D-memory-context.md](research/landscape-2026-10/D-memory-context.md) |
| E | Review quality, test quality, agent security, supply chain | [E-quality-security.md](research/landscape-2026-10/E-quality-security.md) |
| F | Observability, cost, evals, MCP/A2A, DevOps for built apps | [F-ops-cost.md](research/landscape-2026-10/F-ops-cost.md) |

## Bottom line

1. **The biggest lever is Claude Code itself, not another framework.** Since July it ships primitives
   that do in config what we do in prose: subagent frontmatter (`disallowedTools`, `maxTurns`,
   `isolation: worktree`, `omitClaudeMd`, `skills`, `memory`, agent-scoped `hooks`,
   `experimental.cacheTtl`), a blocking `SubagentStop` hook that receives the agent's final message,
   saved dynamic Workflows with schema-validated results, an OS sandbox, and OTel cost telemetry
   labelled per agent. **None of our 69 core agents uses any of these frontmatter fields except
   `effort`** (verified on `main`), so every reviewer can edit the code it judges and no agent has a
   turn cap.
2. **No framework treats a release as a unit** (Track C). Ours has one release: `/accept` stamps
   v1.0.0 and nothing represents release 2. That is the owner's immediate situation.
3. **Every serious peer verifies review findings before acting on them** (Claude Code Review, Jules,
   Copilot). Our Wave 4 findings go straight into the fix loop; refutation exists only at the gate and
   in `/board-review`, and no reviewer separates findings this phase introduced from pre-existing debt.
4. **Our own samples have a live supply-chain hole**: `dockerfile-go.md:451` uses
   `aquasecurity/trivy-action@master` — the action whose tags were force-pushed to a credential
   stealer in March 2026 — and none of the 21 action references in skills is SHA-pinned, against our own
   `github-actions.md` rule. Dependency vetting checks package age, not the age of the version installed.
5. **Our cost model is confirmed outside our repo** (Anthropic's cost/caching docs; a 2026 preprint
   linking failure to step count). The levers are fewer steps and less fixed context per step. Memory
   products that add a retrieval step (mem0, Zep, Cognee, Serena, Augment) are the wrong direction for
   us, and their benchmarks are vendor-disputed.
6. **Orchestration frameworks aren't runtimes for us** (our agents are Claude Code subagents), but
   their execution semantics map one-to-one onto ledger steps 2–3: result guardrails with a retry
   budget, memoized task state, three clocks per task, typed error handlers, typed human requests.

## Ranked plan, timed to rera's next phase

### Now (small, high value, no behaviour change for running work)

| # | What | Source | Effort |
|---|---|---|---|
| 1 | **SHA-pin every third-party `uses:` in skills** (fix `trivy-action@master` first) + a harness test that fails on any non-SHA third-party action | E | S |
| 2 | **Version-age cooldown**: archetypes/guidelines emit npm `min-release-age`, pnpm `minimumReleaseAge`, uv `exclude-newer` (with a security-fix exemption list); `vet-package.py` also checks the *resolved version's* publish time | E | S |
| 3 | **Judges can't edit**: `disallowedTools: Edit, Write, NotebookEdit` on reviewers, reconcilers and verifiers; `maxTurns` on every agent (partial output instead of unbounded runs); candidates use `isolation: worktree` instead of hand-made worktrees. Carry the keys through `_sync-contract.sh` and the dependency-graph test | A, D | S |

### Before / at the start of the next phase

| # | What | Source | Effort |
|---|---|---|---|
| 4 | **Release model**: `/release` + `docs/RELEASES.md` + `agent_state/releases/<R>/release.json` (phases, FR set, baseline tag `release-1.0.0`, semver rule: MAJOR on breaking changes, MINOR new FRs, PATCH hotfixes); `/accept --release=R`; Keep-a-Changelog `CHANGELOG.md` from deltas; `/status` shows the current release. Freeze release 1 as the baseline | C | M |
| 5 | **Cost per phase/agent**: collect Claude Code's own OTel locally (file exporter, no vendor) with `phase/project/run` attributes; `ledger.py report --cost` (USD, tokens, cache-read % per phase × agent × model). First confirm with a probe that the agent label covers background subagents on 2.1.285 | F | S |

### During the phase (ledger steps 2–3a, warning-first per D-002)

| # | What | Source | Effort |
|---|---|---|---|
| 6 | **Hook-validated results (closes B7)**: agents end with a fenced `RESULT` JSON block; the `SubagentStop` hook validates it against a per-agent schema and checks declared outputs exist and changed; on failure it sends the agent back (max 2), then records `guardrail_failed`. Completion is written by the hook only. Start warn-only | A, B | M |
| 7 | **`plan.json` as a task state machine**: A2A state names; `inputs_hash` (specs, facts/decisions versions, base sha) so resume skips unchanged tasks and marks changed ones and their dependents stale; stable task ids; typed `retry`/`on_exhausted` (the bounded fix ladder + rulings ledger in one schema); three clocks per task (schedule-to-start, idle from ledger events, hard cap from each agent type's history); typed human requests (`pending_requests.json`, supervisor `--answers`) | B | M |
| 8 | **Verify findings before fixing**: a different-model verifier sees each BLOCKING/HIGH finding without its severity and must reproduce it or refute it; refuted findings never reach Wave 5; every finding is tagged `introduced` or `pre-existing` (pre-existing → backlog unless security); a project `REVIEW.md` sets the evidence bar and suppresses nits after round 1 | A, E | M |
| 9 | **Lean subagent start, A/B-measured**: a `SubagentStart` hook injects active fact/decision *headings*; agents read a full entry only when their task names it; `omitClaudeMd` on pipeline agents plus a short digest of the owner's global rules (it also drops `~/.claude/CLAUDE.md`). Ship only if tokens fall ≥20% with outcomes held. Also: path-scoped `.claude/rules/*.md` from `/init`, and `experimental.cacheTtl: 1h` only on agents that idle past 5 min (test runner, e2e, mobile, deploy, performance) | D | M |

### After the phase (larger, needs the phase's data or a spike first)

| # | What | Source | Effort |
|---|---|---|---|
| 10 | **Saved Workflow for Waves 3→3v→4→5**: the loop in code, schema-checked results, bounded fix loop, resumable. Covers the per-wave split, fix ladder and mid-wave checks. First test resume after a mid-fan-out failure and whether it runs under `claude -p` | A | M–L |
| 11 | **Delta specs against the frozen release baseline** (ADDED/MODIFIED/REMOVED; refuse merges that drop a TC row without a REMOVED entry), an **`/intake` router** (extend spec / new spec / bugfix with "SHALL CONTINUE TO" regression clauses / roadmap-sized), and a **phase retrospective with a verdict** that checks the previous retro's action items | C | M |
| 12 | **OS sandbox for unattended runs**: strict mode, egress allowlist (registries, github.com, lab hosts, `*.localhost`), credential deny for `~/.ssh`, `~/.aws`, other kubeconfigs. sdlc-guard stays as the command-semantics layer. Needs a spike with Lima/Docker on the lab Macs first | E | M |
| 13 | **Security for products with LLM features** — rera has them (buyer agent, batch LLM extraction): `threat_model_agent` adds an OWASP Agentic/LLM section with TC-SEC rows when the BRD has LLM features; web-reading research agents run without Bash/kube tools (Rule of Two); mutation-guided tests for authz/tenant/RLS code (survivors become work items) | E | M |
| 14 | **Eval reliability**: `/eval --trials=3` (pass^3, measured noise instead of a fixed ±0.05); a ~30-item human-labelled judge set from real rera reviews to score code_reviewer_II, security_reviewer and debate_arbitrator | F | M |
| 15 | **Learning that retires**: reviewer rules promoted on confirmation and disabled after repeated refutation (Bugbot pattern, signals from the fix loop and the owner); lessons as append-only bullets with helpful/harmful counters and `applies_when`/`retire_when` instead of LLM rewrites (ACE showed a rewrite collapsing 18k tokens to 122 and losing accuracy) | A, D, E | M |
| 16 | **Delivery extras**: phase handoff as a PR with evidence + an out-of-pipeline `/code-review`; per-PR preview namespaces on the lab (TTL, max 2); pipeline DORA (5 metrics incl. rework rate) from deploy evidence; LSP plugin for diagnostics after each edit (not for navigation); TC-PROP property rows from EARS | A, C, D, F | S–M each |

## Don't copy

- **Any orchestration framework as our runtime** (LangGraph, MAF, ADK, CrewAI, Temporal): they run SDK
  agents with their own model loop; we'd rewrite everything for semantics a ~300-line hook gives us.
- **Agent teams** (still experimental; no `-p`, no resume) and **`/goal`/ultracode as gates** (the goal
  evaluator only reads the transcript).
- **External memory stores** (mem0, Zep, Cognee, LangMem) and **retrieval MCPs as default navigation**
  (Serena, Augment): mutually disputed benchmarks, an extra step per lookup, and Augment indexes code in
  its cloud. Graphiti ships telemetry on.
- **Hosted review bots or tracing SaaS as gates** (CodeRabbit, Greptile, Bugbot, Braintrust, LangSmith
  cloud) and **their Claude Code plugins/hooks** — code leaves the machine; supply-chain rule.
- **Tessl spec-as-source** (closed beta; same spec, different code), **Agent OS v3's removal of
  orchestration**, **Qodo Cover** (unmaintained), **CaMeL as an implementation**, **A2A transport**,
  **DSPy/GEPA** (needs a large labelled set), **Argo Rollouts on the lab** (no real traffic),
  **a cheaper-model cascade** (one cache namespace is cheaper at Opus 5.5's 0.05× cache-read price).
- **Benchmarks as evidence**: OpenAI dropped SWE-bench Verified over contamination; Pro's grading is
  disputed; vendor precision/resolution rates are self-measured.

## Unverified (needs a probe or a primary source before we rely on it)

- Whether Claude Code's OTel agent label covers background subagents (2.1.285).
- Whether a saved Workflow runs under `claude -p` and how resume behaves after a mid-fan-out failure.
- Whether a frontmatter `Stop` hook acts as `SubagentStop` for that agent.
- Whether the Claude Code sandbox works with Lima and the Docker socket on the lab Macs.
- The real saving of `omitClaudeMd` + heading injection in our pipeline (A/B before shipping).
- Whether sibling subagents share a cached prefix.
- The Auto Mode prompt-injection RCE chain (from a CSA note; primary disclosure not fetched).
- `claude plugin eval` availability ("early access") and whether plugin agents resolve by bare name.
- Each track report lists its own remaining items.
