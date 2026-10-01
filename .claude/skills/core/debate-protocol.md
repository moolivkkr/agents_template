---
skill: debate-protocol
description: Multi-specialist debate — research, debate, collaborate, decide; produces a durable verdict promoted to the decisions ledger
version: "2.0"
tags:
  - debate
  - decisions
  - multi-agent
  - consensus
  - core
---

# Debate Protocol — Research, Debate, Decide

## Purpose

When a pipeline agent faces a contested, high-impact choice between known options, the debate team
researches each option, argues for each, and an arbitrator scores them against the project's own
requirements. The pipeline continues with a reasoned, recorded decision instead of a guess.

Version 2.0 (2026-09-30) fixes what stopped version 1 working as written: requests and verdicts
under names the gate never looked for, a moderator that could return before its researchers
finished, a requesting subagent that couldn't wait for a verdict, one rubric for every kind of
decision, and fallbacks that always picked the first option. The review behind each rule is
`docs/DEBATE_AND_BOARD_REVIEW_2026-09-30.md` (D1–D11).

## When a debate is the right tool

A debate decides between **options that already exist**, using evidence and the project's
requirements. Raise one when:

1. **Conflicting options**: two or more valid approaches with real trade-offs.
2. **High-impact choice**: it shapes architecture, security or the data model, and is hard to
   change later.
3. **Low confidence**: auto-research (levels 4–5) found no confident answer between known options.

A debate **can't** settle these, so they go to the human instead (D9):

| Situation | Why a debate can't settle it | What to do |
|---|---|---|
| **Missing data**: the decision needs a fact nobody has written down (a volume, a contract term, a vendor limit) | Researchers can't create a fact about this project | Return `NEEDS_INPUT` with the question. Under `/autonomous`, record a default in `unresolved.json` (below) with `confidence: LOW` and carry it to the checkpoint |
| **Ambiguous requirement**: the BRD or spec reads two ways | What the product owner meant isn't decided by scoring options | Same as above: `NEEDS_INPUT`, or an `unresolved.json` default under `/autonomous` |

If the work can't wait, a debate may still propose a working default for one of these; the request
then carries `"kind": "assumption"` and the verdict is always flagged for the human to confirm.

Don't raise a debate when the answer is in the docs (auto-research levels 1–2), when the choice is
trivially reversible (naming, file layout), or when a reasonable default has no meaningful
trade-off.

## Files: one naming contract

Everything lives in `agent_state/debates/`, joined on the **topic slug** (`[a-z0-9][a-z0-9_-]*`,
e.g. `token_storage`). Both files also carry the slug in `"topic"`.

| File | Written by | Format |
|---|---|---|
| `<topic>.request.json` | the agent that needs the decision | `sdlc.debate-request/v1` |
| `<topic>.research-<option>.md` | `debate_researcher` | evidence brief |
| `<topic>.argument-<option>.md` | `debate_advocate` (HIGH impact) | argument |
| `<topic>.verdict.json` | `debate_arbitrator` **only** | `sdlc.debate-verdict/v1` |
| `<topic>.verdict-detailed.md` | `debate_arbitrator` | scoring matrix + claim checks |
| `<topic>.second-opinion.json` | `debate_arbitrator` in second-opinion mode (Fable) | `sdlc.debate-second-opinion/v1` |
| `<topic>.transcript.md` | `debate_moderator` | who ran, what each returned, presentation order |
| `<topic>.override.json` | the parent session, when the user overrides a verdict | override record |
| `unresolved.json` | the parent session | decisions auto-resolved with a default |

**Read debates only through `.claude/hooks/debate-status.py`** (`--phase N`, `--json`, `--check`).
It classifies files by content, so older names (`<step>-<topic>.json`, `<topic>-verdict.json`) are
still found. The gate (`verify-gate.sh` check (f)), `/health`, `/pause`, `/worklog` and the human
checkpoint all use it; none of them glob file names.

### Request (`sdlc.debate-request/v1`)

```json
{
  "schema": "sdlc.debate-request/v1",
  "type": "debate_request",
  "topic": "token_storage",
  "phase": 3,
  "from_agent": "backend_developer",
  "from_step": "wave2",
  "decision": "Where the web client keeps the session token",
  "options": [
    { "id": "A", "label": "httpOnly SameSite=strict cookie", "initial_reasoning": "..." },
    { "id": "B", "label": "localStorage + Authorization header", "initial_reasoning": "..." }
  ],
  "context": "FR-012, NFR-SEC-003; IMPLEMENTATION_GUIDELINES §Auth; what is already known",
  "impact": "HIGH",
  "domain": "security",
  "kind": "decision",
  "blocking": true
}
```

- `options`: 2–4, ids `A`–`D`. The order means nothing; the moderator randomizes it for judging.
- `impact`: `HIGH` (architecture, security, data model) or `MEDIUM` (library or pattern choice).
- `domain`: `architecture | security | data_model | feature | testing | operations`. It picks the
  rubric below, so set it honestly: auth, tokens, crypto, PII, CORS/CSRF, rate limits and tenant
  isolation are `security`.
- `kind`: `decision` (default) or `assumption` (a working default for missing data or ambiguity).
- `blocking`: `true` when the work can't continue correctly without the answer.
  - A non-blocking request (`false`) lets the agent continue on its default. It names that default as
    `default_taken`.
  - The debate still runs, right after the wave that raised it. The gate blocks until it has and,
    if the verdict differs, until the agent was relaunched with it and `default_taken` updated.
- `applied`: set by the parent when it relaunches the requester with the decision. The gate checks
  that the decision was applied, not just made. A non-blocking request's `default_taken` counts as
  applied when the verdict agrees with it.
- `domain_reason`: required when the request reads like a security decision (tokens, sessions,
  auth, tenants, rate limits…) but `domain` isn't `security`. Every security protection keys on the
  domain, so the gate asks why.
- To drop a request that no longer applies, set `"status": "withdrawn"` and a `"withdrawn_reason"`
  (at least a sentence). Don't delete it. A security or blocking request also needs
  `"withdrawn_by": "human:<name>"` or a reason citing the `D-NNN` that settles it.

### Verdict (`sdlc.debate-verdict/v1`)

```json
{
  "schema": "sdlc.debate-verdict/v1",
  "topic": "token_storage",
  "phase": 3,
  "impact": "HIGH",
  "domain": "security",
  "status": "RESOLVED",
  "verdict": "A",
  "verdict_label": "httpOnly SameSite=strict cookie",
  "confidence": "HIGH",
  "rubric": "security",
  "request_sha": "<python3 .claude/hooks/debate-status.py --request-sha token_storage>",
  "presentation_order": ["B", "A"],
  "scores": {
    "A": { "total": 8.1, "security_posture": 9, "brd_alignment": 8, "feasibility": 7, "constraint_fit": 8, "operability": 7 },
    "B": { "total": 5.2, "security_posture": 3, "brd_alignment": 7, "feasibility": 8, "constraint_fit": 6, "operability": 6 }
  },
  "gap": 2.9,
  "decisive_factor": "security_posture: B exposes the token to any XSS (OWASP ASVS V3)",
  "claims_checked": [
    { "claim": "SameSite=strict blocks the CSRF vector in FR-012's flow", "source": "https://…",
      "quote": "the exact sentences", "as_of": "2026-05 / RFC 6265bis-15", "result": "confirmed" }
  ],
  "hardened_default": "A",
  "rationale": "2-3 sentences",
  "rejected": { "B": "one sentence" },
  "reconsider_if": ["a native client without cookie support enters scope"],
  "risk": "…",
  "mitigation": "…",
  "decision_id": "D-014"
}
```

- `status`: `RESOLVED`, or `INCOMPLETE` with a `reason` when the arbitrator decided on evidence it
  knows is incomplete. `INCOMPLETE` always has `confidence: LOW`.
- `request_sha`: ties the verdict to the request it answered, including the text of every BRD row
  (`FR-…`, `NFR-…`, `OBJ-…`) and `PROJECT_FACTS` entry (`F-…`) the request cites. If the request or
  one of those requirements changes or is retired afterwards, the verdict is stale. The gate blocks
  until the debate runs again, and the old round is archived first. Overrides carry it too.
- **What the gate recomputes, rather than trusting the verdict's own claims** (`debate-status.py
  --check`):
  - every option's total, from its per-criterion `scores` and the domain's weights
  - the gap, and the confidence band it allows: a verdict may claim less confidence, never more
  - that the winner is the highest total
  - that `claims_checked` has a sourced entry
  - that the research, arguments and transcript behind the verdict exist
- **Exceptions to "the winner is the highest total"** must be written down:
  - `hardened_default` for a security call below HIGH confidence
  - `tie_break` for totals equal at one decimal place
- `hardened_default`: required for `domain: security` unless the status is `INCOMPLETE`. It names
  the more restrictive option, the one that fails closed. A security call below HIGH confidence that
  isn't the hardened default needs `must_override`, naming the MUST requirement that rules it out.
- `decision_id`: the `D-NNN` that `remember.sh decide` returned. Exactly one active ledger block
  may link to this verdict. It must be this id, and its decision must name `verdict_label`.
  `remember.sh` refuses a second active entry for the same link unless it reverses the first.
- `evidence_gaps`: the moderator's `EVIDENCE INCOMPLETE:` lines. Any gap (here or in the transcript),
  or a decisive claim checked as `unverifiable`, caps the confidence at MEDIUM.
- `kind: "assumption"` and `none_ideal: true` are carried when they apply.

### Second opinion (`sdlc.debate-second-opinion/v1`)

`{"schema":"sdlc.debate-second-opinion/v1","topic":"…","model":"<exact model id>","verdict":"A","gap":0.6,"presentation_order":["A","B"],"scores":{…},"decisive_factor":"…"}`.

**When it's required:** for HIGH impact whenever the recomputed gap, or the verdict's own
confidence, is below HIGH.

**It must belong to this request:** it carries the same `request_sha` as the verdict. A second
opinion left from an earlier version of the request doesn't count. Its verdict must be its own
highest total, with the same exceptions as the primary's.

**The primary can't be rewritten after it:** the moderator records `VERDICT_SHA` in the transcript
after the primary arbitration. The gate rejects a verdict that changed afterwards; `promote` adds
only `decision_id`.

**How it stays independent:**
- It reads the options in the reverse presentation order.
- It never sees the first judgment. The primary leaves the ledger alone in this case, and a short
  `MODE: promote` step records the `D-NNN` after the second opinion returns.
- It runs on Fable. A non-Fable model goes to review.
- `debate-status.py` validates it, so an empty or same-order file doesn't count.

**When it disagrees:** on a non-security topic, the disagreement goes to the review list. On a
security topic, a person decides (`<topic>.override.json`) before the gate passes.

## Who runs a debate (hand-back, not a watcher)

No watcher picks up a request file. The agent that needs the decision hands it back to its parent,
and the parent runs the debate. A subagent has finished its turn before anyone could run a debate
for it, so "write a request and wait" doesn't work (D4).

1. **Requesting subagent.** It writes `<topic>.request.json`.
   - **Blocking:** it ends its turn with the first line `NEEDS_DECISION <topic>` and one sentence. The
     rest of the message says what it finished and what it will do once decided. It doesn't guess.
   - **Non-blocking:** it continues on its recommended default, says so in its final message, and
     returns normally.
2. **Parent session** (the orchestrator or command that spawned the subagent) spawns
   `debate_moderator` with the request path, and waits for it (`~/.claude/skills/core/child-returns.md`).
   Every command that spawns agents follows that skill, so this works from `/plan` and `/discuss` as
   well as `/develop`.
   - The moderator runs at depth 1 and its researchers, advocates and arbitrators at depth 2. A
     subagent never spawns the moderator itself: that would put the researchers at depth 3 and hide
     the decision from the parent's checkpoint.
3. **Moderator returns** `COMPLETE <topic>: <verdict_label> (<confidence>)` once the arbitrator has
   written the verdict.
4. **Parent relaunches** the requesting agent with its original prompt plus `DECISION <topic>:
   <verdict_label> — agent_state/debates/<topic>.verdict.json. Continue from where you stopped.`
5. **Before the gate**, `debate-status.py --phase N --check` must pass. Every request needs a
   verdict, a recorded default, a withdrawal or a person's override, non-blocking ones included.

**Limits** you can count:
- **Per step:** at most 3 requests; per phase at most 10. Beyond that, record recommended defaults
  in `unresolved.json` and, under `/autonomous`, exit auto mode at the phase limit.
- **Per debate:** 2–4 options, at most 10 web searches per researcher, one advocacy round, one
  arbitration, plus one second opinion and one promote step when required.
- **Concurrent debates:** at most four moderators at a time. Each holds itself plus up to four
  children, against the default limit of 20 subagents.
- **No nested debates:** an arbitrator that can't decide writes a `LOW`/`INCOMPLETE` verdict. It
  never raises another debate.

There are no minute budgets. A subagent can't measure wall-clock time. The Opus 5.5 guidance also
notes that a model told it is short on time verifies less, which is the wrong trade for a decision.

## The process

| Impact | Research | Advocacy | Arbitration | Second opinion |
|---|---|---|---|---|
| **HIGH** | one researcher per option | one advocate per option | one arbitrator | when confidence isn't HIGH: a second arbitrator on Fable, reverse order |
| **MEDIUM** | one researcher per option | skipped (the arbitrator judges the research directly) | one arbitrator | no |

### Phase 1: Research (parallel, one researcher per option)

Each researcher gathers evidence for and against its option: the project's documents first, then
web sources (current-year benchmarks, production reports, known limitations), then ecosystem
health. It cites every claim with a path or URL, which is what lets the arbitrator re-check the
decisive one. It doesn't argue or recommend.

### Phase 2: Advocacy (parallel, HIGH impact only)

Each advocate reads **all** the research and makes the strongest honest case for its option:
strengths with evidence, specific reasons the alternatives fit this project worse, and its own
option's weaknesses with mitigations. **Advocates don't score.** A self-assigned number anchors the
judge even when the judge is told to ignore it (D8.2), so the score belongs to the arbitrator alone.

### Phase 3: Arbitration

The arbitrator:
1. Reads the request and the PROJECT_FACTS and DECISIONS constraints.
2. Reads the arguments (or, for MEDIUM, the research) **in the presentation order the moderator
   gives**. The moderator randomizes that order and records it.
3. Scores **one criterion at a time across all options** using the domain's rubric and anchors below.
   Going criterion by criterion compares like with like and reduces order and halo effects (D8.3).
4. Re-opens the source of the one or two claims behind the decisive factor and records what it found
   in `claims_checked` (D8.6).
5. Applies the confidence and tie rules, writes the verdict, and records the `D-NNN`.

## Rubrics by domain (D8.1)

Weights sum to 100. The request's `domain` picks the rubric. A request with no domain uses
`architecture`.

| Domain | Criteria (weight) |
|---|---|
| `architecture` | brd_alignment 30 · feasibility 25 · constraint_fit 20 · scalability 15 · ecosystem 10 |
| `security` | **security_posture 35** · brd_alignment 25 · feasibility 20 · constraint_fit 10 · operability 10 |
| `data_model` | brd_alignment 25 · data_integrity 25 · access_fit 20 · evolution_cost 20 · operability 10 |
| `feature` | brd_alignment 30 · implementation_risk 25 · maintainability 20 · ecosystem 15 · performance 10 |
| `testing` | detection_power 35 · determinism 25 · run_cost 20 · constraint_fit 20 |
| `operations` | reliability 30 · operability 25 · run_cost 20 · constraint_fit 15 · ecosystem 10 |

### Score anchors (D8.4)

Score 1–10 against these anchors. A 2, 5 or 8 means the same thing in every debate. Use the numbers
between them for "between these two descriptions". A 10 needs evidence from this project, not
general reputation.

| Criterion | 2 | 5 | 8 |
|---|---|---|---|
| brd_alignment | conflicts with a MUST FR/NFR or a PROJECT_FACTS constraint | meets the in-scope requirements through a workaround or an unverified assumption | meets every in-scope FR/NFR directly; cited |
| feasibility | needs skills, infrastructure or maturity the project lacks; no production precedent found | buildable with a learning curve or one unproven component | the project's stack already does this; production precedent cited |
| constraint_fit | breaks an IMPLEMENTATION_GUIDELINES constraint or an active DECISIONS.md entry | fits with one exception that would need recording | fits with no exception |
| scalability | a known ceiling below the NFR target | reaches the target but needs re-architecture later | reaches 10× the NFR target as designed; evidence cited |
| ecosystem | unmaintained (no release in 12 months) or a single maintainer | maintained; thin docs or missing integrations | active releases, good docs, the integrations this project needs |
| security_posture | weaker default, larger attack surface, or fails open | secure only when configured correctly; needs compensating controls | secure by default, fails closed, smallest surface; matches the secure-coding rules |
| data_integrity | allows lost, duplicated or inconsistent writes the BRD forbids | integrity depends on application code being right | guaranteed by constraints or transactions in the store |
| access_fit | the main access paths need scans or joins the store does poorly | works with indexes or denormalization | the main access paths are direct lookups |
| evolution_cost | changes need downtime or rewriting data | online migrations, with care | additive changes are routine |
| implementation_risk | many moving parts, untested paths, new failure modes | moderate surface, some new code paths | small change on well-trodden paths |
| maintainability | specialist knowledge to change; tangles layers | understandable with documentation | conventional for this codebase; clear ownership |
| performance | misses the NFR-PERF target in cited measurements | meets it without headroom, or unmeasured | meets it with headroom; measured |
| detection_power | would miss the defect classes this phase risks | catches some of them | catches the classes in the threat model and risk list |
| determinism | depends on timing, network or shared state | deterministic with care | deterministic by construction |
| run_cost | expensive to run or keep green | moderate | cheap to run and maintain |
| reliability | a single failure takes the feature down | degrades with manual recovery | fails over or degrades gracefully, automatically |
| operability | no way to observe or roll it back | observable, with a manual rollback | observable, with an automatic or one-step rollback |

## Confidence, ties and the hardened default (D7)

The confidence comes from the gap between the top two weighted totals:

| Gap | Confidence | What the arbitrator writes |
|---|---|---|
| > 1.0 | HIGH | the verdict |
| 0.3–1.0 | MEDIUM | the verdict and the one decisive factor |
| < 0.3 | LOW | the verdict and both options explained, flagged for the checkpoint |

- **Ties** (totals equal at one decimal place): break them on the domain's heaviest criterion, then
  its second heaviest, then (security) the hardened default, then lower implementation risk. Record
  how in `tie_break`. If they're still tied, the verdict is `INCOMPLETE` and `LOW`, with both options
  explained.
  - **Interactive runs:** the parent shows the choice to the user.
  - **`/autonomous` runs:** a non-security verdict stands and goes on the review list. A security one
    stops the run for the user.
- **Security.** For `domain: security`, when the confidence isn't HIGH, the verdict is the
  `hardened_default` unless `must_override` names the MUST requirement that rules it out.
  - **No hardened option:** if you can't name one, the verdict is `LOW` with `status: INCOMPLETE`.
  - **That case, and a second opinion that disagrees:** both block the gate until a person's choice
    is in `<topic>.override.json`. The gate counts them as security findings, so a forced gate needs
    an acknowledgement for each.
- **None ideal.** If every option scores below 5 on the heaviest criterion, the verdict is the least
  bad option with `"none_ideal": true`, flagged for the checkpoint.
- **Second opinion.** HIGH impact and confidence below HIGH means the moderator runs a second
  arbitration on `model: fable`, with the presentation order reversed (D8.5). Order sensitivity and
  same-model blind spots then show up as disagreement. Disagreement doesn't change the verdict. It
  goes to the review list, or to a person for security.

## Decided without a debate: `unresolved.json`

The circuit breaker and `/autonomous` record each default they apply in
`agent_state/debates/unresolved.json`, so it reaches the checkpoint and counts as resolved for the
gate:

```json
{ "decisions": [
  { "topic": "cache_strategy", "phase": 3, "from_agent": "backend_developer", "domain": "architecture",
    "auto_resolved_with": "A", "confidence": "LOW", "reason": "escalation_limit_exceeded", "needs_review": true },
  { "topic": "token_ttl", "phase": 3, "domain": "security", "auto_resolved_with": "B", "hardened": true,
    "confidence": "LOW", "reason": "needs_input under --auto: no session-length requirement in the BRD", "needs_review": true }
] }
```

The default is the option with the stronger BRD-alignment case in the request, and for security the
hardened option, marked `"hardened": true`. The gate rejects a security default without that marker,
and any default that isn't one of the request's options. It's never simply "the first option".

## The human checkpoint

```bash
python3 .claude/hooks/debate-status.py --phase N   # every topic, its status, and why it needs review
```

Show the user:
- **Every topic with review reasons:** LOW confidence, INCOMPLETE, a second opinion that disagrees,
  a security verdict that isn't the hardened default, an assumption, auto-resolved, or none ideal.
- **HIGH-impact verdicts** with their score table.
- **MEDIUM-impact verdicts** with verdict and confidence.

Under `/autonomous` nobody is at a checkpoint mid-run. After each phase, the run appends each topic
with review reasons to `agent_state/autonomous/auto-resolved.jsonl`, so its final report carries
them. Security topics that need a person block the gate themselves.

The user can override any verdict. The override needs a `user_rationale`, and its `user_override`
must be one of the options. Writing it, reversing the ledger entry and relaunching whoever built on
the old verdict are in `child-returns.md` § "When the user overrides a verdict".

## Anti-patterns

| Don't | Instead |
|---|---|
| Raise a debate for missing data or an ambiguous requirement | `NEEDS_INPUT` to the human, or an `unresolved.json` default under `/autonomous` |
| Write a request and keep working as if it were decided | Blocking: return `NEEDS_DECISION <topic>`. Non-blocking: state the default you took |
| Spawn the debate team in the background | One message, `run_in_background: false`, so the turn waits for every child |
| Let advocates score their own option | Advocates argue with evidence; only the arbitrator scores |
| Judge options one at a time in request order | Randomized order, one criterion at a time across all options |
| Fall back to "the first option" | The stronger BRD case, the hardened option for security, or `LOW`/`INCOMPLETE` |
| Glob `agent_state/debates/` file names | `debate-status.py` |
| Leave a verdict only in `agent_state/` | `remember.sh decide`, and put the `D-NNN` in the verdict |

> Config blocks checked 2026-09-30 (`bash tests/archetype-compile/config-packs/run.sh --live`): 1 JSON block parsed.
