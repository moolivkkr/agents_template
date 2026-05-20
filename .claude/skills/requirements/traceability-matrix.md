# Traceability Matrix Patterns — Source → BRD → Spec → Test → Deploy

## Matrix Structure

Every requirement must be traceable end-to-end:

```markdown
| Req ID | Source | Design Artifact | Test ID | Deploy Check | Status |
|--------|--------|----------------|---------|--------------|--------|
| FR-001 | requirements/user-stories.md:L12 | specs/auth-flow.md | UT-001, IT-001, AT-001 | /api/v1/auth/login responds 200 | Verified |
| FR-002 | requirements/pitch-deck.md:S5 | specs/user-mgmt.md | UT-010, IT-005 | GET /api/v1/users returns list | Verified |
| NFR-PERF-001 | requirements/nfr.md:L3 | specs/performance-budget.md | PERF-001 | k6 load test passes | Pending |
```

## Bidirectional Tracing

### Forward Trace (requirement → implementation)
Every FR-* must have:
- At least 1 design artifact (spec/wireframe)
- At least 1 test (unit, integration, or acceptance)
- A deployment verification method

**Gap = BLOCKER:** If any FR-* has no test, it cannot pass the phase gate.

### Reverse Trace (implementation → requirement)
Every spec behavior and test must trace back to a requirement:
- Spec behaviors without FR-* source → potential scope creep
- Tests without FR-* source → potentially testing invented behavior

**Gap = WARNING:** Flag for review (may be valid technical necessity).

## When to Update the Matrix

| Event | Matrix Action |
|---|---|
| BRD finalized | Create initial matrix (all FR/NFR, Source filled, rest TBD) |
| Specs written | Fill Design Artifact column |
| Tests written | Fill Test ID column |
| Phase gate passed | Fill Deploy Check column, mark as Verified |
| Requirement changed | Update row, mark downstream artifacts as "needs review" |
| Requirement removed | Mark row as "removed" with reason (don't delete) |

## Coverage Metrics

```markdown
## Traceability Coverage — Phase N

| Metric | Count | Percentage |
|--------|-------|-----------|
| FR-* with source | 24/24 | 100% |
| FR-* with design artifact | 24/24 | 100% |
| FR-* with test coverage | 22/24 | 92% |
| FR-* with deploy check | 20/24 | 83% |
| NFR-* with verification method | 8/10 | 80% |
| Untraced specs (no FR source) | 2 | Flag for review |
| Untraced tests (no FR source) | 1 | Flag for review |
```

**Phase gate requires:** FR-* with test coverage >= 95%

## Source Attribution Rules

Valid sources (trace back to these):
- `requirements/*.md` — user-provided documents
- Interview answers — recorded in `agent_state/brd_refiner/decisions.yaml`
- User story cards — if in requirements folder
- Support tickets / bug reports — if referenced explicitly

NOT valid sources:
- "Common sense" — if it's not documented, it's an assumption
- "Industry standard" — cite the specific standard (OWASP, WCAG, RFC)
- Agent inference — if the agent deduced a requirement, flag as "inferred" for user review

## Anti-Patterns

| Pattern | Problem | Fix |
|---------|---------|-----|
| Matrix not updated after spec changes | Stale links, false coverage | Update matrix as part of every spec/test change |
| "TBD" in test column at gate time | Can't verify requirement is met | Write test before gate, or flag as gap |
| Deleting removed requirements | Lose audit trail | Mark as "removed" with reason |
| One test covers multiple FR-* | If test breaks, unclear which FR is affected | 1:1 mapping preferred; shared tests noted |
| No deploy verification | "It works on my machine" | Every FR needs a production-verifiable check |
