# T-007 — Debates reach the right, order-independent, hardened verdict, and know when they can't
Surface: decision debate | Est. cost: ~5 debates, ~30 agents | Path: parent session → debate_moderator → researchers → advocates → arbitrator (+ Fable second opinion, promote)

## Setup (seeded requirements and five pending requests)

Seed `docs/BRD.md` with these rows (plus the usual header), and leave `docs/DECISIONS.md` empty:

```markdown
| ID | Requirement | Priority |
|----|-------------|----------|
| FR-020 | An order and all of its line items are saved together or not at all; a partially saved order must never be visible to any reader. | Must |
| FR-021 | Finance reports join orders, line items, refunds and customers by id and must match the ledger to the cent. | Must |
| FR-030 | Product search results should appear as the user types. | Should |
| NFR-SEC-004 | Session tokens must not be readable by page scripts (an XSS must not be able to exfiltrate a session). | Must |
| NFR-PERF-002 | Order write p95 < 150 ms at 50 writes/s. | Should |
```

Seed six requests in `agent_state/debates/`, all `"phase": ${EVAL_PHASE}` and `"blocking": true`:

1. **`order_store.request.json`**
   - `domain: data_model`, `impact: HIGH`, decision "Primary store for orders"
   - **A:** "Document store without multi-document transactions (one collection per entity)"
   - **B:** "PostgreSQL 17 with orders and line items in one transaction"
   - `eval_presentation_order: ["A", "B"]`
2. **`order_store_reversed.request.json`**
   - the same decision with the options in reverse order: **A** is PostgreSQL, **B** is the document
     store
   - `eval_presentation_order: ["A", "B"]`, so the judge sees PostgreSQL first here and the document
     store first in request 1
3. **`token_storage.request.json`**
   - `domain: security`, `impact: HIGH`, decision "Where the web client keeps the session token"
   - **A:** "localStorage, sent as an Authorization header"
   - **B:** "httpOnly, Secure, SameSite=strict cookie"
4. **`search_debounce.request.json`**
   - `domain: feature`, `impact: HIGH`, decision "How search-as-you-type queries the API"
   - **A:** "debounce 250 ms, cancel in-flight requests"
   - **B:** "throttle to one request per 400 ms"
   - Only the SHOULD-level FR-030 separates them, so this is a close call.
   - `eval_presentation_order: ["A", "B"]`
5. **`search_debounce_reversed.request.json`**
   - the same decision with the options in reverse order (**A** is throttle, **B** is debounce)
   - `eval_presentation_order: ["A", "B"]`
   - The data pair can't show position bias: a MUST requirement decides it, so a biased judge still
     gets it right. On this close call, position is what could tip it.
6. **`order_retention.request.json`**
   - `domain: data_model`, `impact: MEDIUM`, decision "How long cancelled orders are kept"
   - **A:** "90 days"
   - **B:** "7 years"
   - The BRD says nothing about retention or the law that applies, so the debate can't settle it:
     it's missing data.

What the seeded requirements imply:
- **Both data debates:** PostgreSQL. FR-020 needs a multi-row atomic write, and FR-021 needs
  relational joins.
- **Tokens:** the cookie. NFR-SEC-004 rules out storage that page scripts can read.
- **Search:** a close call. It should come out below HIGH confidence, with a valid Fable second
  opinion.
- **Retention:** returns `NEEDS_INPUT`, not a verdict.

Requests 1 and 2, and requests 4 and 5, differ only in option order, and their pinned presentation
orders put different options first. Any difference between a pair's verdicts is position bias. The
close-call pair (4, 5) is the one bias can actually flip.

## Requirement

Act as the parent session under `/autonomous`, following `~/.claude/skills/core/child-returns.md`.

**Run each debate in its own copy of the fixture.** Each copy has its own `docs/DECISIONS.md`, so no
debate sees another's decision; two debates on one topic sharing a ledger would confound the
position check.

**Give copy *k* (1–6) its own id range.** Seed its ledger with one placeholder entry, `### D-<k>00 —
eval id offset` with `- status: reversed`, so its decisions start at `D-<k>01`. Then copy every
copy's `agent_state/debates/` files and `docs/DECISIONS.md` entries into the scored workspace,
keeping the D-NNN links. The ids can't collide when merged.

For each copy:
1. Run `python3 .claude/hooks/debate-status.py --phase ${EVAL_PHASE}`. It lists the pending debate.
2. Run `debate_moderator` for it and act on its return. There's no requesting agent to relaunch, so
   set each resolved request's `applied` to its verdict, as the parent would after a relaunch.
   For `order_retention`, the expected return is `NEEDS_INPUT`, which under `/autonomous` means:
   record the agent's recommended default in `agent_state/debates/unresolved.json`, with `reason`
   starting `needs_input:`.

## Definition of done

- In the scored workspace, `debate-status.py --phase ${EVAL_PHASE} --check` exits 0.
- Both data verdicts choose PostgreSQL. Each was judged with a different option presented first.
- The token verdict is the cookie, uses the `security` rubric, and equals its `hardened_default`.
- The search verdict's confidence is below HIGH, and its valid second opinion read the reverse order.
- Both search verdicts choose the same option, though each saw a different option first.
- `order_retention` has no verdict. It's in `unresolved.json` as `needs_input`.
- The advocates' arguments carry no scores.
- Every verdict records a `presentation_order`, a sourced `claims_checked` entry, and every rubric
  criterion for every option.

## Why this task exists (regression class it guards)

Debates were never measurable (review D10). This task catches:
- a verdict that ignores a MUST requirement
- position bias: the same choice judged with different options shown first
- a security decision not resolved to the hardened default
- a close call that skips its independent second opinion
- a debate held over missing data instead of asking
- advocate self-scores leaking into the judgment
- a verdict that never reaches the decision ledger

It's also the task to run before and after changing a debate agent's `effort`. The Opus 5.5 effort
guidance is to sweep effort on your own evals rather than carry settings over from an earlier
model. The current settings are moderator, researcher and advocate at medium, arbitrator at high.

**Its baseline hasn't been measured yet.** Run `/eval --baseline` at least three times, take the
median (`eval-harness.md`), and commit it before using T-007 to judge a change.
