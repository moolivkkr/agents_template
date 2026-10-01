# T-007 — Debates reach the right, order-independent, hardened verdict
Surface: decision debate | Est. cost: ~3 debates, ~22 agents | Path: parent session → debate_moderator (foreground) → researchers → advocates → arbitrator (+ Fable second opinion)

## Setup (seeded requirements and three pending requests)

Seed `docs/BRD.md` with these rows (plus the usual header), and `docs/DECISIONS.md` empty:

```markdown
| ID | Requirement | Priority |
|----|-------------|----------|
| FR-020 | An order and all of its line items are saved together or not at all; a partially saved order must never be visible to any reader. | Must |
| FR-021 | Finance reports join orders, line items, refunds and customers by id and must match the ledger to the cent. | Must |
| NFR-SEC-004 | Session tokens must not be readable by page scripts (an XSS must not be able to exfiltrate a session). | Must |
| NFR-PERF-002 | Order write p95 < 150 ms at 50 writes/s. | Should |
```

Seed three requests in `agent_state/debates/`, all `"phase": ${EVAL_PHASE}`, `"blocking": true`:

1. `order_store.request.json`: `domain: data_model`, `impact: HIGH`, decision "Primary store
   for orders". Options **A**: "Document store without multi-document transactions (one collection
   per entity)". **B**: "PostgreSQL 17 with orders and line items in one transaction".
2. `order_store_reversed.request.json`: the same decision with the options **in reverse order**: A
   is PostgreSQL, B is the document store.
3. `token_storage.request.json`: `domain: security`, `impact: HIGH`, decision "Where the web
   client keeps the session token". Options **A**: "localStorage, sent as an Authorization
   header". **B**: "httpOnly, Secure, SameSite=strict cookie".

The right answers follow from the seeded requirements:
- PostgreSQL in both data debates: FR-020 needs a multi-row atomic write, and FR-021 needs relational
  joins.
- The cookie for tokens: NFR-SEC-004 rules out storage that page scripts can read.

The two data requests differ only in option order, so any difference between their verdicts is
position bias.

## Requirement

Act as the parent session at a Wave 6 gate (`develop-orchestrator` step 0c):
1. Run `python3 .claude/hooks/debate-status.py --phase ${EVAL_PHASE}`. It lists three pending debates.
2. Run `debate_moderator` for each, in the foreground.
3. Re-run `debate-status.py --check` until it passes.

## Definition of done

- `debate-status.py --phase ${EVAL_PHASE} --check` exits 0, which requires all of these:
  - three valid `sdlc.debate-verdict/v1` verdicts
  - each promoted to `docs/DECISIONS.md`
  - a `.second-opinion.json` for every HIGH-impact verdict whose confidence isn't HIGH
- Both data verdicts choose PostgreSQL (the same label regardless of option order).
- The token verdict is the cookie, uses the `security` rubric, and equals its `hardened_default`.
- The advocates' arguments carry no scores.
- Each verdict records:
  - a `presentation_order`
  - at least one `claims_checked` entry with a source
  - per-criterion scores for every option

## Why this task exists (regression class it guards)

Debates were never measurable (review D10). This task catches the judging failures found on
2026-09-30:
- a verdict that ignores a MUST requirement
- position bias (the two data requests differ only in option order)
- a security decision scored on a rubric with no security criterion, or not resolved to the
  hardened default
- advocate self-scores leaking into the judgment
- a verdict that never reaches the decision ledger

It's also the task to run before and after changing a debate agent's `effort`. The Opus 5.5 effort
guidance is to sweep effort on your own evals rather than carry settings over from an earlier
model. The current settings are moderator, researcher and advocate at medium, arbitrator at high.
