# Dual-Ledger Replanning Protocol

`adaptive-replan.md` answers **what to re-run** once you've decided to replan. It does not
answer the harder question: **should you replan at all, keep iterating, or escalate to a
human?** A fix agent that "keeps trying" can loop forever on a falsified assumption, burning
tokens while making zero real progress.

This protocol adds the missing self-monitoring loop, inspired by Magentic-One's orchestrator,
which maintains **two ledgers**:

- **Task Ledger** (outer loop) — the known FACTS, the EDUCATED GUESSES/assumptions, and the
  current PLAN. Re-read and updated as facts are learned.
- **Progress Ledger** (inner loop, per step/wave) — is the task done? who owns the current
  step? are we making progress, or looping/stalled?

The orchestrator watches the Progress Ledger. When it stalls — no NEW fact learned, or the
same action repeats — it self-reflects on the failure mode, revises its guesses, and
**rewrites the plan**. This is the mechanism that turns "retry N times" into "notice we're
stuck, and change strategy."

> **Where this runs:** `develop-orchestrator` Wave 5 (Collective Feedback + Iterate). The
> **parent orchestrator owns both ledgers** — it is the only actor with cross-wave memory.
> Fix agents spawned in Wave 5 report facts back up; they do not maintain the ledger
> themselves. (The orchestrator wiring lives in `develop-orchestrator.md`, maintained
> separately — this skill only defines the format and rules.)

---

## Task Ledger — outer loop

Stored at `agent_state/phases/${PHASE}/ledger.md`. Read at the start of every Wave 5 cycle,
rewritten at the end of one that replans.

The **hard separation of `facts` from `assumptions` is not cosmetic** — it is this
framework's honesty mandate encoded in state. A fact is verified (a test output, a git diff,
a health-check response). An assumption is an educated guess we have not yet falsified.
Never let a guess sit in `facts`. When Wave 5 acts on an assumption as if it were a fact and
gets a surprising failure, that is exactly the signal that the assumption was wrong.

```markdown
# Task Ledger — Phase ${PHASE}
updated: 2026-07-06T14:20:00Z
cycle: 2

## facts            # VERIFIED — a test result, git diff, health check, error output
- [F1] Unit suite `service/order_test.go` passes (Wave 3 report).
- [F2] Integration test POST /orders returns 500, body: "nil pointer in tax calc".
- [F3] git diff Cycle 1 touched only service/tax.go (predicted scope held).

## assumptions       # EDUCATED GUESS — not yet verified, MUST NOT be treated as fact
- [A1] The 500 is a LOGIC failure in tax.go (classification guess).           conf: medium
- [A2] The DB schema is correct; the bug is application-side.                  conf: high
- [A3] No other endpoint depends on the tax helper.                           conf: low

## plan              # current strategy; rewritten on replan
- [P1] Fix nil guard in service/tax.go  → assignee: fix_agent
- [P2] Re-run unit + integration (LOGIC scope from adaptive-replan)
- [P3] If green, hand back to Wave 6 gate
```

Rules:
- Every `assumption` carries a confidence (`low | medium | high`) so the orchestrator knows
  which guess to distrust first when a stall hits.
- When an assumption is **verified**, move it to `facts` (with the evidence). When it is
  **falsified**, delete it from wherever it lives and record the correction as a new fact.
- Never silently upgrade an assumption to a fact without evidence — that reintroduces the
  exact stale-guess problem the ledger exists to prevent.

---

## Progress Ledger — inner loop (per wave/iteration)

Appended once per Wave 5 cycle. This is the stall sensor.

```json
{
  "cycle": 2,
  "step": "P1 — fix nil guard in service/tax.go",
  "assignee": "fix_agent",
  "done": false,
  "new_fact_this_cycle": false,
  "progress_since_last": false,
  "repeated_action": true,
  "loop_count": 2
}
```

| Field | Meaning | How the orchestrator sets it |
|---|---|---|
| `step` | The current `plan[]` item being worked | Copied from active `plan[]` entry |
| `assignee` | Which agent owns this step | The Wave 5 agent name |
| `done` | Is the phase-level task complete? | True only when all tiers in scope pass |
| `new_fact_this_cycle` | Did this cycle add a row to `facts[]`? | True if the ledger's `facts[]` grew |
| `progress_since_last` | Fewer failures than last cycle? | Compare failure count vs prior cycle |
| `repeated_action` | Same fix target as last cycle? | Same files/step as prior cycle |
| `loop_count` | Consecutive cycles with no new fact | `+1` if `new_fact_this_cycle==false`, else reset to 0 |

---

## The stall → replan → escalate rule

Evaluate after **every** Wave 5 cycle, before spawning the next fix agent:

```
if done:
    → exit Wave 5, proceed to Wave 6 gate.

elif loop_count > 2 (i.e. 3+ cycles with no new fact)
     OR (repeated_action AND not progress_since_last):
    → STALL. Trigger REPLAN (steps a–d below).

else:
    → keep iterating: apply adaptive-replan minimum re-test scope, next cycle.
```

### REPLAN (when stalled)

**(a) Name the failure mode.** Write a one-line self-reflection into `ledger.md`:
what is actually happening? (e.g. "Cycle 1 and 2 both patched tax.go and both still 500 —
the fault is not in tax.go.") This is the orchestrator reasoning about *why* it is stuck,
not just *that* it is stuck.

**(b) Falsify a guess.** Identify the lowest-confidence assumption consistent with the
stall and **move it out of `facts`/`assumptions`**. In the example, `[A1] it's a LOGIC bug
in tax.go` is falsified — replace it with a new assumption (`[A4] the nil comes from the
handler passing an unparsed body`, conf: medium). The stall is *evidence*: whatever you
assumed and kept acting on is probably the wrong assumption.

**(c) Rewrite `plan[]`.** Not "try the same fix harder" — a *different* strategy that follows
from the revised guess. New `plan[]` → new step → `loop_count` resets to 0 on the next new
fact.

**(d) Escalate after N replans.** The ledger caps replans in alignment with the existing
retry caps in `sdlc-config.json`. Use the **tightest cap relevant to the failing tier** so
the ledger never out-loops the tier's own budget:

| Failing tier (from classification) | Config cap | Max ledger replans |
|---|---|---|
| review findings | `review_retry_max` | 2 |
| unit / integration | `test_retry_max` | 3 |
| e2e | `e2e_retry_max` | 2 |
| acceptance | `acceptance_retry_max` | 2 |

When `replan_count` reaches the cap, **stop** and escalate to `debate_moderator` (if the
disagreement is about approach) or the human (if it is a missing fact only they hold).
Escalation writes the full Task Ledger — facts, surviving assumptions, and every failure-mode
note — so the human/moderator inherits the reasoning, not just "it failed 3 times."

---

## How this wraps `adaptive-replan.md` (it does NOT replace it)

The two protocols compose along a clean seam:

| Question | Answered by | Mechanism |
|---|---|---|
| **WHEN** do we replan vs iterate vs escalate? | **This skill** | Progress Ledger stall detection + replan cap |
| **WHAT** do we re-run once we've decided to fix? | `adaptive-replan.md` | Failure-classification table → minimum re-test scope |

The failure-classification table (`LOGIC / WIRING / CONTRACT / SCHEMA / UI / CONFIG / FLAKY`)
is **not discarded** — it becomes the tool the orchestrator uses **after** the ledger decides
to act:

1. Ledger detects the current step is not `done` but is not yet stalled → **keep iterating**.
   Derive re-test scope from the classification table. Normal Wave 5.
2. Ledger detects a **stall** → REPLAN. The failure-mode reflection (step a) usually reveals
   the *class* was misdiagnosed (e.g. we called it LOGIC, it's actually WIRING). The rewritten
   plan re-classifies, and *that new class* drives the new minimum re-test scope.

So classification still owns scope end-to-end; the ledger just decides when to trust the
current classification versus tear it up and re-classify.

---

## Promoting a validated assumption to a Tier 0 fact

Some assumptions, once verified, are true not just for this cycle but for the whole project
("the tax helper is only called from the order service", "port 5432 is the shared PG"). These
belong in the **shared-context protocol's Tier 0** (`docs/PROJECT_FACTS.md`), not buried in a
phase ledger that dies at the gate.

Promotion rule (see `shared-context-protocol.md`):
- An assumption verified during Wave 5 that is **broadly and durably true** (a hard
  constraint, a retired/renamed component, an environment gotcha) → propose it via
  `/remember` so it becomes a Tier 0 fact loaded into every future session and subagent.
- An agent-proposed promotion is written with `confidence: reported` / `source: agent:*`;
  per the shared-context rules only a human `/remember` marks it `confidence: confirmed`.
- Phase-local truths (this endpoint's shape, this cycle's fix) stay in the ledger and, if
  reusable, flow to Tier 1 `lessons.md` via `structured-lessons.md` — **not** Tier 0.

This closes the loop: the ledger's honesty separation (fact vs guess) feeds the framework's
long-term memory only for guesses that earned promotion by being verified.

---

## Logging

The replan trail lives in `agent_state/phases/${PHASE}/ledger.md` (rewritten each replan) and
a per-cycle line in `collective_feedback.md`, so it sits alongside the adaptive-replan cycle
log:

```markdown
## Ledger Cycle N
new_fact: NO
loop_count: 3  → STALL
failure_mode: "Cycles 1-2 both patched tax.go, both 500 — fault is upstream"
falsified: [A1] LOGIC-in-tax.go  →  [A4] handler passes unparsed body (WIRING)
replan: plan rewritten (re-classified LOGIC → WIRING)
replan_count: 1 / 3 (test_retry_max)
```

Every replan feeds Post-Gate lessons: a phase that took 3 replans and a re-classification is
a signal the spec or classification heuristics under-served this area.
