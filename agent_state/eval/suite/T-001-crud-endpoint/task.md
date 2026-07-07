# T-001 — CRUD endpoint (backend slice)
Surface: backend endpoint | Est. cost: ~9 agents | Path: /develop (single small phase)

## Requirement
Implement a tenant-scoped `GET /api/v1/widgets/:id` endpoint that returns a single widget owned by
the caller's tenant. Return **404** if the widget does not exist **OR** is not owned by the caller's
tenant (no existence oracle — a cross-tenant read must not reveal that the row exists). Emit unit +
integration tests.

TC IDs the spec must enumerate and the tests must annotate:
- **TC-U-001** — service returns the owned widget for the caller's tenant.
- **TC-I-001** — a cross-tenant read of an existing widget returns 404 (not 403, not the row).

## Definition of done
- Handler → service → repository, with `tenantID` threaded end-to-end (no global/ambient tenant).
- Cross-tenant read returns 404, never 403 and never the row body.
- Unit + integration tests exist, annotate TC-U-001 / TC-I-001, and pass.
- No `TODO`, stub, or suppression (`t.Skip`, `@ts-ignore`) introduced.

## Why this task exists (regression class it guards)
Catches the IDOR / missing-tenant-scope class and the "endpoint shipped without integration tests"
class. If a wave change drops the integration_test_agent or the security review, this task's
trajectory score falls even when the handler still compiles.
