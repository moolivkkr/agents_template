---
skill: candidate-selection
description: Parallel candidate-solution generation + model-test-voting selection (test-time compute scaling). Gate-triggered, N independent implementations in isolated worktrees, one winner rejoins the pipeline.
version: "1.0"
tags:
  - test-time-compute
  - candidate-selection
  - parallel-implementation
  - selection
  - cost-gated
  - core
---

# Candidate-Selection Protocol — parallel solutions + selection (test-time compute scaling)

> **Read Tier 0 first.** Before applying this protocol, load `docs/PROJECT_FACTS.md` (ground-truth
> invariants) and `docs/DECISIONS.md` (settled decisions). A retired/renamed component or a settled
> architectural decision constrains what a candidate is even allowed to try — honor it in every
> candidate.

The default pipeline generates **one** implementation for Wave 2 and then reviews/tests it. On
genuinely hard phases that single attempt is the ceiling: whatever the first solver missed, the
reviewers can only *find* — they can't re-derive a better solution. This protocol adds **test-time
compute scaling**: generate **N independent candidate implementations of the same spec, each with its
own tests**, then select the winner by combining **model-test voting** with a dedicated
`solution_selector` judge. The winner rejoins the pipeline in place of the single Wave-2 output.

**Evidence.** CodeMonkeys (Stanford, arXiv 2501.14723) and the SWE-bench ensemble leaders show that
generating many candidate solutions, each carrying its own tests, and selecting via test-execution
voting + a selection model beats the best single solver (roughly ~57% → ~66% on SWE-bench Verified).
The gain comes from **diversity + verification**, not from one model "trying harder."

---

## ⛔ When it triggers (this is EXPENSIVE — gate it)

Candidate-selection multiplies Wave-2 cost by N (Anthropic reports multi-agent systems burn ≈15× the
tokens of a single-agent chat; Cognition's "Don't Build Multi-Agents" warns that over-parallelizing
work that shares state produces conflicting, un-mergeable output). **It is OPT-IN and gated. It is NOT
the default for every phase.** Run it ONLY when at least one trigger fires:

| Trigger | Source of truth | Rationale |
|---|---|---|
| **scale-class = PLATFORM** | `.claude/skills/core/scale-adaptive-depth.md` classifier (Wave 0) | New subsystem / shared-contract change — highest correctness value, worth the spend. |
| **High model-routing complexity** | `.claude/skills/core/model-routing.md` `RAW_SCORE > 60` (well above the opus threshold of 40) | Large, multi-file, high-FR work where a single pass most often misses cases. |
| **Previous-phase failure on this component** | `agent_state/phases/$((PHASE-1))/reports/collective_feedback.md` names this component / area | The single-attempt approach already failed here once; diversity is the cheapest fix. |
| **Explicit `--candidates=N` flag** | User invocation (`/develop --candidates=3`) | Manual override — the human decided this phase is worth it. Always honored. |

**Default N = 2. Cap N = 3.** More than 3 rarely pays for itself (diminishing returns vs. linear
cost) and strains isolation/merge. `--candidates=N` clamps to `[2,3]`; `--candidates=1` disables the
protocol (falls back to the normal single Wave-2 implementation).

**Explicitly does NOT run for TRIVIAL / SMALL / STANDARD phases.** For these, one implementation is
both correct and cheaper — spending 2–3× tokens to re-derive a straightforward CRUD handler is pure
waste. State the class in the Wave-0 checkpoint; if it isn't PLATFORM and no other trigger fired,
skip this protocol and record `candidate_selection: skipped (class=<class>, no trigger)` in the
manifest. **A STANDARD phase does NOT auto-upgrade** — only the four triggers above turn it on.

> Cost guardrail restated: this is a correctness lever for the *hard* phases, paid for in tokens. If
> you can't name which trigger fired, it should not run.

---

## How candidates are generated (isolation + diversity)

N candidates implement the **same spec** but must not collide on files, and must not be near-identical
(N identical candidates = N× cost for 1× diversity — the anti-pattern). Two requirements:

### 1. Isolation — one git worktree per candidate

Each candidate implements on its own branch in its own worktree directory, so parallel implementers
never touch the same working tree. This is the "architecture follows task structure" principle: the
candidates are genuinely independent (they explore the *same* task in isolation), so parallelism is
safe — unlike splitting one implementation across agents that must share files.

```bash
# From the repo root. BASE is the current HEAD the phase builds on.
BASE="$(git rev-parse --short HEAD)"
WT_ROOT="agent_state/phases/${PHASE}/candidates"
mkdir -p "$WT_ROOT"

for i in $(seq 1 "${N}"); do
  BR="cand/phase-${PHASE}/c${i}"
  WT="${WT_ROOT}/c${i}"
  # Fresh branch off BASE, checked out into an isolated worktree.
  git worktree add -b "$BR" "$WT" "$BASE"
done
git worktree list   # verify N isolated trees
```

Each candidate implementer is spawned with `WORKING DIRECTORY: <repo>/agent_state/phases/${PHASE}/candidates/cI`
and told to commit within its own worktree only. No candidate reads or writes another candidate's tree.

### 2. Diversity — assign each candidate a distinct starting strategy

Give candidate _i_ a different **entry strategy** so they explore different shapes of the solution
space. Assign round-robin from this list (use the first N):

| Candidate | Starting strategy | What it front-loads |
|---|---|---|
| c1 | **interface-first** | Define the interfaces/contracts, then implement against them. |
| c2 | **test-first (TDD)** | Write the spec's TC-* tests first, then make them pass. |
| c3 | **data-model-first** | Design the schema/types/state, then build behavior around them. |

Each candidate **MUST** produce its own tests alongside its implementation (this is what makes
model-test voting possible — a candidate with no tests cannot vote and cannot be cross-checked). The
tests live inside the candidate's worktree.

Spawn prompt skeleton (the orchestrator fills `${STRATEGY}` per candidate):

```
[GROUND TRUTH line] You are candidate implementer c${i} for Phase ${PHASE}.
WORKING DIRECTORY: <repo>/agent_state/phases/${PHASE}/candidates/c${i}   (your OWN git worktree — commit only here)
STARTING STRATEGY: ${STRATEGY}   (${STRATEGY_DESC})
Read the SAME specs as a normal Wave 2: docs/design/phases/${PHASE}/specs/ + IMPLEMENTATION_GUIDELINES.md.
Honor docs/PROJECT_FACTS.md and docs/DECISIONS.md.
Implement ALL in-scope components AND write your own tests (unit + the spec's TC-* for this surface).
HARDENING RULES apply (interfaces not concrete types, repository pattern, literal Unicode, table-driven tests).
Do NOT look at or merge from sibling candidate worktrees. Commit your work in THIS worktree.
Return: files created + a one-line note on how your strategy shaped the design.
```

Spawn all N candidate implementers **in parallel** (they are independent by construction).

---

## How selection works (two signals — neither alone decides)

### Signal A — model-test voting (execution-grounded)

Run each candidate's own test suite, and **cross-run** candidates' tests against each other where the
suites are meaningfully comparable (same public interface / same TC-* IDs). A candidate that passes
its own tests **and** its siblings' tests is more likely correct than one that only passes the tests
it wrote to be lenient. Build the cross-test matrix:

```
             tests_c1   tests_c2   tests_c3     own   cross   VOTE
impl_c1        PASS       PASS       FAIL       ✓     1/2     ...
impl_c2        PASS       PASS       PASS       ✓     2/2     ...
impl_c3        FAIL       PASS       PASS       ✓*    1/2     ...
```

- **Own-test pass** is table stakes (a candidate that fails its own tests is disqualified from the
  vote — it self-reported broken).
- **Cross-test pass rate** is the discriminator: `cross_score = (# sibling suites this impl passes) /
  (# comparable sibling suites)`.
- Where suites aren't comparable (a candidate's tests bind to a private shape), mark `N/A` and exclude
  from that pair — never fabricate a PASS/FAIL.

This is *execution* evidence, not opinion — it is why it must be combined with, and can override, the
judge's aesthetic preference.

### Signal B — the `solution_selector` judge (rubric-constrained)

Spawn the `solution_selector` agent (`.claude/agents/core/solution_selector.md`, model: opus). It
scores each candidate against a fixed rubric (spec/TC-* coverage, test results incl. the cross-test
matrix from Signal A, code quality, architecture fit, risk) — **rubric-constrained, not open-ended
"which looks best"** (open-ended LLM-judge prompts are biased toward verbosity/familiarity). It emits
a winner + rationale + a **graft list** (superior elements from runners-up to fold into the winner).

### Combine — the decision rule

Neither signal decides alone:

1. **Disqualify** any candidate that fails its own tests (Signal A).
2. Among survivors, compute a combined score: **`0.5 * normalized(cross_score)` (Signal A) + `0.5 *
   normalized(rubric_score)` (Signal B).**
3. **Voting overrides the judge on execution facts:** if the judge's pick fails a sibling's test that
   the runner-up passes, the judge MUST justify the pick on a concrete spec/quality ground or defer to
   the test-passing candidate. A judge preference cannot beat a reproducible failing test.
4. **Ties** (within 0.05) → prefer the candidate with the higher cross-test pass rate; if still tied,
   prefer the smaller diff / simpler design (lower future maintenance).
5. Record the winner, the losers, and the **graft list** in `candidate_selection.md`.

---

## How the winner rejoins the pipeline

Candidate-selection **replaces the single Wave-2 implementation** for hard phases. It does **NOT**
replace the gate — the winner still runs the full Wave 3 (tests) + Wave 4 (reviews/reconcilers) +
Wave 6 (gate) exactly as a normal single implementation would.

```bash
WINNER="c${WIN}"                       # e.g. c2
WT_ROOT="agent_state/phases/${PHASE}/candidates"
WIN_BR="cand/phase-${PHASE}/${WINNER}"

# 1. Merge the winner's branch into the working tree (the phase's real branch).
git merge --no-ff "$WIN_BR" -m "phase ${PHASE}: adopt candidate ${WINNER} (selected — see candidate_selection.md)"

# 2. Apply grafts, if any. Prefer cherry-picking the specific commits/files named in the graft list
#    from the runner-up branch; otherwise a scoped follow-up commit. NEVER blind-merge a whole loser.
#    e.g. git checkout cand/phase-${PHASE}/c1 -- path/to/superior_file.go   (then review + commit)

# 3. Discard the losers' worktrees and branches (isolation cleanup — do NOT leave dangling trees).
for i in $(seq 1 "${N}"); do
  C="c${i}"
  [ "$C" = "$WINNER" ] && continue
  git worktree remove --force "${WT_ROOT}/${C}" 2>/dev/null || true
  git branch -D "cand/phase-${PHASE}/${C}" 2>/dev/null || true
done
# Retain the winner's worktree until the merge is verified, then remove it too.
git worktree remove --force "${WT_ROOT}/${WINNER}" 2>/dev/null || true
git worktree prune
```

After the merge + grafts land in the working tree, **continue to Wave 3 on the winner** — the winner's
own tests are a starting point, but Wave 3's separate-agent-per-tier discipline and Wave 4's reviewers
still run against the merged result. The gate is unchanged.

---

## Cost guardrail + logging (required)

- **Cost tradeoff, stated:** N candidates ≈ N× the Wave-2 implementation cost (plus the selector).
  This buys a correctness lift *only* on hard phases where a single attempt is unreliable. On easy
  phases it is pure waste — hence the trigger gate above.
- **When NOT to use it:** TRIVIAL/SMALL/STANDARD phases; phases with no independent solution space
  (a one-line change has no diverse candidates); any time no trigger fired. If in doubt and no trigger
  fired, don't run it.
- **Architecture-follows-task-structure:** only parallelize work that is genuinely independent.
  Candidates are safe to parallelize *because each is a complete, isolated attempt at the same task* —
  do not confuse this with slicing one implementation across agents that must share files (that
  produces merge conflicts and dropped work, per Cognition's warning).
- **Log it.** Record the decision so it is auditable:

```bash
echo "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"candidate_selection\",\"phase\":${PHASE},\
\"n\":${N},\"trigger\":\"${TRIGGER}\",\"strategies\":[${STRATEGY_LIST}],\
\"winner\":\"c${WIN}\",\"grafts\":${GRAFT_COUNT},\"report\":\"agent_state/phases/${PHASE}/reports/candidate_selection.md\"}" \
  >> "agent_state/phases/${PHASE}/execution.jsonl"
```

The `solution_selector` agent additionally writes the full rationale + rubric table + graft list to
`agent_state/phases/${PHASE}/reports/candidate_selection.md` and logs its own `completed` line to
`execution.jsonl` (so the roster/gate can prove it ran).

---

## Interaction with the other depth/routing skills

| Concern | Skill | Question answered |
|---|---|---|
| Which **model** per agent | `model-routing.md` | haiku / sonnet / opus |
| Which **workflow depth** (waves) | `scale-adaptive-depth.md` | skip / light / full / full+ADR |
| **How many Wave-2 attempts** (this skill) | `candidate-selection.md` | 1 (default) vs N candidates + select |

They compose: a PLATFORM class runs full+ADR depth, routes opus for the implementers and selector, and
turns on N-candidate generation. A STANDARD class runs full waves, one implementation, no candidates.
