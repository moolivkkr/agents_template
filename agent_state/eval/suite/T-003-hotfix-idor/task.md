# T-003 — Hotfix an IDOR bug (reproduction-test-first)
Surface: bug fix | Est. cost: ~5 agents | Path: /hotfix (scoped fix → scoped test → scoped review)

## Symptom (the bug report)
`GET /api/v1/widgets/:id` returns another tenant's widget when the caller passes a widget id they
do not own. Expected: **404** (no existence oracle). Observed: **200** with the other tenant's row.
The regression was introduced when a `WHERE tenant_id = ?` clause was dropped from the repository
query during a refactor.

## Definition of done (hotfix discipline — reproduction test FIRST)
- A **failing** regression test is written FIRST that reproduces the cross-tenant 200 (this test must
  exist and be red before the fix). Annotate it **TC-R-003**.
- The fix restores tenant scoping in the repository query (`tenant_id` filter re-added).
- After the fix, TC-R-003 passes AND the previously-passing suite still passes (no new red).
- Scoped review runs (a hotfix still gets a security review — an IDOR fix is security-sensitive).
- No unrelated files touched; the diff is scoped to the repository + the new regression test.

## Why this task exists (regression class it guards)
This is the canonical "fast-track fix that skips the reproduction test or the review" failure. If a
framework change lets /hotfix merge without a red-first regression test, or drops the
security_reviewer from the hotfix path, this task's outcome AND trajectory both fall — exactly the
signal a pass/fail eval would miss.
