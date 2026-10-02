# Track A: autonomous and cloud coding agents (checked 2026-10-02)

Scope: how commercial and open coding agents plan, parallelize, verify and hand off work, plus Claude
Code features shipped since 2026-07 that we don't use. FRAMEWORK_REVIEW_2026-09-30 §2–3 covered
spec-driven frameworks (GSD, Spec Kit, BMAD, Superpowers and others), not these products, so almost
everything here is outside its scope. Our repo was checked on `main` (1550e16).

**Bottom line.** The biggest lever is Claude Code itself. Since July it has shipped primitives that
cover several of our open items in code rather than prose:
- dynamic Workflows: a script holds the loop, results are schema-validated, runs resume;
- subagent frontmatter for `disallowedTools`, `maxTurns`, `isolation: worktree` and agent-scoped `hooks`;
- a blocking `SubagentStop` hook whose payload carries `last_assistant_message`;
- `/goal`'s error taxonomy;
- `claude plugin eval` with a no-plugin baseline.

None of our 69 core agents sets `tools`, `disallowedTools`, `maxTurns`, `isolation` or `hooks`
(frontmatter count on `main`). The commercial agents' main lesson is the **verified-finding review
loop**: finder → independent verifier → severity including "pre-existing" → learning from human
reactions. Our Wave 4 does only the first part.

## 1. Capability table

| Capability | Who does it best (how; source, checked 2026-10-02) | Do we have it? | Value | Effort | Risk / caveats |
|---|---|---|---|---|---|
| Orchestration in code, resumable, with schema-checked results | **Claude Code dynamic Workflows**. A JS script calls `agent()/parallel()/pipeline()/phase()`. `schema` gives validated JSON with up to 5 retries. Results resume within the session or a backgrounded one. 16 concurrent agents (tunable to 256), 1,000 per run. Runs in `-p` once `Workflow(<name>)` is in the allow rules. Saved under `.claude/workflows/`; plugins can ship them. [workflows](https://code.claude.com/docs/en/workflows.md) | **Partial**: candidate fan-out is prose in `.claude/commands/develop-orchestrator.md`; "saved Workflow for /develop fan-out" is P2 in FRAMEWORK_REVIEW §6 | **H** | M | No mid-run user input. `Date.now()`/`Math.random()` throw. Relaunch reruns everything after the first failed agent. In `-p` and background sessions a usage limit fails the agent instead of pausing |
| Per-agent tool limits, turn caps, worktree isolation | **Claude Code subagent frontmatter**: `tools`/`disallowedTools`, `maxTurns` (output marked partial), `isolation: worktree` (auto-cleaned if no changes), `hooks`, `effort`, `skills`, `permissionMode`. Since w32, worktree isolation also blocks Bash and git that reach the main checkout. [sub-agents](https://code.claude.com/docs/en/sub-agents.md), [w32](https://code.claude.com/docs/en/whats-new/2026-w32.md) | **No**: reviewers and reconcilers have all tools; candidates use manual `git worktree add` (`.claude/skills/core/candidate-selection.md`) | **H** | S | Our template/`_sync-contract.sh` must carry the new keys. Teammates ignore the `skills` field (agent-teams doc), which doesn't affect us |
| Completion recorded by a hook, not by the agent's own claim | **Claude Code `SubagentStop`**: can block (`decision: block`); payload has `agent_type`, `last_assistant_message`, `transcript_path`. **`agent`-type hooks** (experimental) spawn a verifier subagent. [hooks](https://code.claude.com/docs/en/hooks.md) | **Partial**: `ledger.py` observes SubagentStop but never blocks (docs/PHASE_LEDGER.md: "Later: enforcement"); known item B7 | H | S–M | `agent` hooks are experimental. Block only on a missing or invalid sidecar, never on content judgement |
| Verified-finding code review | **Claude Code Code Review**: per-class finder agents, then "a verification step checks candidates against actual code behavior", then dedupe and rank. Severity is Important / Nit / **Pre-existing**. `REVIEW.md` sets the verification bar, nit cap and re-review convergence. The check run is neutral and ends with machine-readable severity counts. [code-review](https://code.claude.com/docs/en/code-review.md). **Copilot coding agent** reviews its own PR and runs CodeQL, advisory-DB and secret scanning before opening it ([changelog 2025-10-28](https://github.blog/changelog/2025-10-28-copilot-coding-agent-now-automatically-validates-code-security-and-quality/)). **Jules** runs a critic pass before "done" ([Google blog](https://developers.googleblog.com/ja/meet-jules-sharpest-critic-and-most-valuable-ally/)) | **Partial**: named Wave 4 reviewers with fix→re-review loops; blind refutation exists only in `/board-review`; no "pre-existing" class (grep on `main`) | **H** | M | Managed Code Review is Team/Enterprise, $15–25 per review (vendor docs); local `/code-review` doesn't read `REVIEW.md` |
| Learned review rules from human reactions | **Cursor Bugbot learned rules**: signals are 👎, replies and human-reviewer comments. Candidate rules are promoted when evidence accumulates and disabled on negative feedback; editable in the dashboard. Vendor metric: 78% resolution, LLM-judged, public repos ([blog 2026-04-08](https://cursor.com/blog/bugbot-learning)). **Devin**: suggested knowledge in the worklog ([release notes](https://docs.devin.ai/release-notes/overview)) | **Partial**: lessons + procedural promotion (Tier 1.5); no signal from the owner accepting or dismissing findings | M | M | The resolution rate is a vendor number from its own judge |
| Unattended-loop error handling | **Claude Code `/goal`** (a prompt Stop hook on a small model):<br>- skips evaluation while background work runs;<br>- check-ins at 30 min with backoff, at most 3 idle;<br>- stops after several turns with no tool use;<br>- **clears** on auth, credit, unrecoverable context overflow or model unavailable; **retries ×3** on overload or dropped connection; **pauses** on a rate or usage limit;<br>- restored on resume; works in `-p`.<br>[goal](https://code.claude.com/docs/en/goal.md) | **Partial**: `autonomous-continue.sh` + `scripts/startup-autonomous-run.sh`; A2–A4/A5 fixes listed in the review | M | S | The evaluator sees only the transcript and has no tools, so it is no substitute for `verify-gate.sh` |
| Spend caps that reach subagents | `--max-budget-usd` now caps subagents too (w30); `CLAUDE_CODE_MAX_SUBAGENTS_PER_SESSION` (default 200), `maxEffortLevel`, `workflowSizeGuideline`. [w29](https://code.claude.com/docs/en/whats-new/2026-w29.md), [w30](https://code.claude.com/docs/en/whats-new/2026-w30.md), [w37](https://code.claude.com/docs/en/whats-new/2026-w37.md) | **Yes**: supervisor passes `--max-budget-usd` (`scripts/startup-autonomous-run.sh:161`) | — | — | Make sure the docs reflect the subagent enforcement |
| Measured value against no framework | **`claude plugin eval`**: with/without-plugin ablation, `--runs` (default 3), free graders (`regex`, `tool_used`, `tool_order`, `file_exists`) plus model-judged `llm`/`baseline`, sandboxed Bash, `--json` and exit codes for CI. [plugin-evals](https://code.claude.com/docs/en/plugin-evals.md) | **Partial**: `/eval` scores outcome + trajectory against our own baseline, never against vanilla Claude Code | M | M (needs plugin packaging) | Troubleshooting mentions "currently in early access", so availability is unverified. Every case is real spend |
| PR-based handoff with evidence | **Cursor cloud agents**: PRs with video, screenshots and logs. **Devin Review**: ordered diffs, autofix of flagged bugs. **Copilot**: iterate with `@copilot` on the PR. [Cursor changelog](https://cursor.com/changelog), [Copilot docs](https://docs.github.com/en/copilot/concepts/agents/coding-agent/about-coding-agent) | **No**: phases commit on branches; no `gh pr create` anywhere in `.claude/` | M | S | Solo owner, so value is the record plus an external reviewer, not team review |
| Post-deploy change health | **Cursor Rollouts** (2026-09-23): a monitor per PR across environments → healthy / regression / inconclusive; can open revert PRs. [changelog](https://cursor.com/changelog) | **Partial**: Wave 3.5 health check, `/rollback`, k6 | L–M | M | New and unproven; needs telemetry we may not have on k3s |
| Milestone→feature decomposition, fresh worker per feature, app-driving validators | **Factory Missions**: orchestrator → milestones → features; "each feature gets a fresh worker session"; validators "launch the application, navigate through flows"; a different model per role. Vendor: ~12× tokens, median ~2 h. [factory.com/news/missions](https://factory.com/news/missions) | **Mostly yes** (phases, waves, deploy + e2e/acceptance); fresh session per unit is a known item | L (already planned) | — | Cross-vendor validator sends code to another provider |
| Strong-model consult mid-task | **Claude Code advisor tool** (experimental, Anthropic API only): a stronger model reads the full transcript at decision points. **Amp Oracle** is similar. [advisor](https://code.claude.com/docs/en/advisor.md), [Amp](https://ampcode.com/docs/models-and-subagents) | **Partial**: debate protocol | L | S | Model-timed and can't be forced; not on Bedrock; uncached full-transcript reads |
| Lint/test after every edit | **Aider** lints edited files by default; `--auto-test --test-cmd` runs tests and tries to fix on a non-zero exit. [aider docs](https://aider.chat/docs/usage/lint-test.html) | **Partial**: Wave 2A build gate; gate-time lint via `commands-table.py`; no per-edit hook | M | S | Keep it to formatter/typecheck of the edited file, or edits slow down |
| Reusable environment snapshots | **Jules** Environment Snapshots; **Devin** machine snapshots / blueprints; **Codex** cached environments | N/A (local + k3s lab) | L | — | Matters only if we move to cloud sessions |
| Parallel peer agents with a shared task list | **Claude Code agent teams**: still "experimental and disabled by default"; no teammates in `-p`; no resume; no nesting. [agent-teams](https://code.claude.com/docs/en/agent-teams.md) | No (deliberately) | L | — | Unchanged since the earlier review: don't build on it |
| Coordinator over many long-running cloud threads | **Claude Code Projects** (public beta, Pro/Max, cloud threads share memory); **Cursor Projects** (2026-09-10) | No | L | — | Cloud sessions can't reach the lab k3s without self-hosted runners, which are Team/Enterprise |

## 2. Strongest recommendations

**R1. Put Claude Code's own enforcement into our agent frontmatter (S, H).**
This is the cheapest real hardening available, and it moves policy from prose into config, which
the harness paper below also observes across the field.
- Reviewers, reconcilers and verifiers get `disallowedTools: Edit, Write, NotebookEdit`, so a judge
  can't "fix" what it judges.
- Every agent gets `maxTurns`, so it returns partial output instead of running unbounded.
- Candidate implementers use `isolation: worktree` in place of the manual `git worktree add` block.
- Each roster agent gets a frontmatter `hooks.Stop` (it runs as SubagentStop for that agent) that
  exits 2 when its evidence sidecar is missing or fails `sdlc.test-results/v1`. That is B7 enforced
  per agent; the observe-only `ledger.py` stays as is.

Update `_sync-contract.sh` and the dependency-graph test so the keys can't drift.

**R2. Move Wave 3→3v→4→5 into a saved dynamic Workflow (M, H). This raises an existing P2 to P1.**
Write `.claude/workflows/develop-review.js`:
- `phase('tests')` runs the tier writers through `parallel()`, each with a `schema` matching the sidecar;
- `phase('verify')` runs `test_runner`;
- `phase('review')` runs the named reviewers;
- a bounded fix loop in code: "until no BLOCKING findings, or 2 rounds without progress → mark blocked".

The script's return value is the gate's input. The roster is then guaranteed by the code that
spawned the agents, not by the agents' own reports. It covers four open items: the per-wave split,
the bounded fix ladder, mid-wave checks and hook-written completion.

Keep human checkpoints outside the workflow, since there's no mid-run input. Add
`Workflow(develop-review)` to the allow rules for `-p` runs. Before relying on it, test resume after
a mid-fan-out failure: everything after the first failed agent reruns.

**R3. Add a verify-and-classify step to Wave 4 findings (M, H).**
Copy Code Review's pipeline shape, not the product:
- Every BLOCKING finding goes to a refuter on a different model that sees the finding without its
  severity. `/board-review` already does this.
- A finding is BLOCKING only if it survives and cites file:line evidence.
- Add a **pre-existing** severity so phase N can't be blocked by phase N-1 debt; those findings go
  to DECISIONS or the backlog.
- Add a `REVIEW.md`-style project file (verification bar, nit cap, "after round 1, Important only")
  that every reviewer reads.

This cuts false blocks, the same failure FRAMEWORK_REVIEW §1-B found in the gate.

**R4. Hand each phase off as a PR with an external second opinion (S, M).**
At the gate, `gh pr create` from the phase branch with:
- PHASE_SUMMARY;
- links to roster and evidence;
- e2e and mobile screenshots or videos;
- the output of an out-of-pipeline `claude -p "/code-review high"`, or `claude ultrareview` when
  available. It has a different context and none of our prompts, so it catches what our reviewers
  share as blind spots.

Record which findings the owner accepts or dismisses. That gives R5 its signal.

**R5. Learned reviewer rules with retirement (M, M).**
The Bugbot pattern on top of our Tier 1.5 promotion:
- each accepted or dismissed finding becomes a candidate rule `{pattern, applies_when, evidence_count, negative_count}`;
- `/consolidate` promotes a rule into the reviewer checklist at N confirmations and retires it at M dismissals.

This is the known "learnings applies_when/retire_when" item, with a real signal source.

Also take two cheap items from `/goal` and Aider:
- **`/goal`'s error taxonomy in the supervisor.** Clear on auth, credit or context failures;
  retry ×3 on transient errors; pause on rate limits; defer while background work runs; stop after
  N turns with no tool use. These map onto A2–A5 and exit codes 0/1/10/11.
- **Per-edit lint hook.** A PostToolUse `Edit|Write` hook that runs the formatter/typecheck for the
  edited file only.

## 3. Do NOT copy

- **Agent teams as the core.** Still experimental: no `-p`, no resume, auto-approved teammate plans,
  silent conversion of named subagents into teammates when enabled.
- **`/goal` or `ultracode` as gates.** The goal evaluator reads only the transcript with no tools.
  Ultracode turns off the large-workflow warning and the concurrency cap, and opts every task into
  workflows (more tokens).
- **Mods to replace `sdlc-guard`.** Mods "aren't sandboxed", run with user permissions and can
  approve tool calls that `ask` rules or PreToolUse hooks would block. More attack surface, no gain.
  The built-in "You should know" side agent is off by default and the docs give no evaluation of it.
- **Cross-vendor validators** (Factory uses GPT for validation). This sends code to another provider.
  Keep cross-model checks within Anthropic models, as `/board-review` does.
- **Benchmark-driven choices.** OpenAI stopped reporting SWE-bench Verified in Feb 2026 over
  contamination and flawed tasks ([openai.com](https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/)).
  A May 2026 audit reportedly found SWE-bench Pro graders mis-grading about a third of trials (secondary
  source). Augment's "#1 SWE-bench Pro" and Cursor/Bugbot resolution rates are vendor claims. Our own
  `/eval` on our task types is the right instrument.
- **Cloud environments and snapshots** (Jules, Devin, Codex, Claude Code cloud) for now. Our tests
  need the lab k3s and local Docker, and self-hosted runners are Team/Enterprise only.
- **Memory Bank-style always-loaded files** (Cline/Roo, now AGENTS.md in Kilo). Our Tier 0 + graph
  retrieval is the better-measured design; the harness paper finds none of 11 systems use embedding
  retrieval.

## 4. Unverified items

- **Factory Missions publication date.** The fetched page said "February 26, 2025", but it names
  Opus 4.6 and GPT-5.3-Codex, which suggests 2026. Its token and duration figures are vendor numbers.
- **Codex Cloud best-of-N.** The `--attempts 1–4` flag comes from a third-party site
  (codex.danielvaughan.com) and BleepingComputer; the OpenAI cloud docs page I fetched didn't mention it.
- **Harness paper date.** arXiv 2609.00006 (Barbaste et al.) shows "submitted July 15, 2026" in the
  fetched summary, but the ID implies September. I relied only on its qualitative findings (no
  embeddings; policy moving from prose to config).
- **Mini-SWE-agent bash-only scores** (Gemini 3 Flash 75.8% and others) come from secondary pages.
- **Devin details.** "Devin 2.2 self-review/autofix" is from a secondary review site; the release-notes
  summary came via a fetch model, not verbatim text.
- **`claude plugin eval` availability.** The docs troubleshooting mentions "early access", so it may
  not be enabled on the owner's account.
- **Plugin agent naming (open question from the 2026-09-30 review).** The sub-agents doc says plugin
  agents are referenced as `plugin-name:agent-name`. Whether bare names still resolve is not stated.
  Packaging would likely mean renaming every `subagent_type` in the orchestrator, so test before
  packaging.
- **Whether a frontmatter `Stop` hook converts to SubagentStop** for that agent. The docs list
  frontmatter hooks as scoped to the subagent run; I did not read the exact conversion rule, so check
  it before R1's hook part.
- **Copilot coding agent's 59-minute session cap** (docs fetched; a hard limit, cited as stated).
- **Cursor's Aug–Sep 2026 changelog** (`/goal`, subagents on own VMs, Projects, Rollouts) came via a
  fetch summary of cursor.com/changelog; the wording was not checked verbatim.
