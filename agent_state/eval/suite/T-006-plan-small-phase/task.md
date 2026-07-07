# T-006 — Plan a small phase (spec generation with exhaustive TC-* IDs)
Surface: planning | Est. cost: ~5 agents | Path: /plan --phase=N

## Requirement
Given a one-line BRD slice — "FR-020: an authenticated user can rename their own widget" — produce a
phase spec set the way `/plan` does: a TRD, a data-contract delta, and an EXHAUSTIVE enumeration of
TC-* IDs across tiers (not a token sample). The spec must be implementable and testable without
further clarification.

## Definition of done
- A TRD exists for the phase and cites FR-020.
- A data-contract delta describes the rename operation (endpoint shape, request/response, error
  cases: not-found → 404, cross-tenant → 404, empty name → 400).
- TC-* IDs are exhaustively enumerated per the generation matrices: at least unit (>=8), integration
  (>=6 incl. the cross-tenant 404), and E2E (>=3) IDs, each with a one-line intent.
- Every TC-* ID is unique and well-formed (`TC-[A-Z]+-\d+`).
- The spec surfaces at least one open assumption/risk rather than silently guessing (e.g. "rename
  audit log — in scope?").

## Why this task exists (regression class it guards)
Catches the "spec that under-enumerates test cases" class — the root cause of downstream traceability
gate failures. If a change makes spec_writer emit a thin TC-* list, this task's outcome falls because
the tier minimums are machine-checked here, before any code is written.
