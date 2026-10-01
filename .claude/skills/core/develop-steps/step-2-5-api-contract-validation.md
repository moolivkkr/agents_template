<!-- Part of /develop (~/.claude/commands/startup/develop.md). Read when executing this step. -->

## Step 2.5 — API Contract Validation (UI phases only)

**When:** `frontend.enabled = true` in IMPLEMENTATION_GUIDELINES AND this phase includes UI screens
**Runs after:** Build-step B2b (backend_developer + api_developer complete) — this IS Build-step B2-contract
**Blocks:** Build-step B3 (ui_developer will NOT start until this passes)

Validate that `api_developer` produced a complete, unambiguous contract artifact:

```bash
CONTRACT_FILE="docs/design/phases/${PHASE}/specs/api-contracts.md"
```

**Checks (inline — no separate agent needed):**

1. **File exists:** `api-contracts.md` must exist and be non-empty
2. **All routes covered:** every route in `agent_state/phases/${PHASE}/api_developer/manifest.json` must have a matching entry in `api-contracts.md`
3. **Shape unambiguity:** for each endpoint entry:
   - Response shows explicit `"data": [...]` (array) or `"data": {...}` (object) — not just `"data": ...`
   - Empty state documented (list: `[]`, single: `null`)
   - All fields have types (no untyped `"field": "object"`)
4. **Data contract compliance:** every endpoint in `api-contracts.md` matches the TypeScript interface in `data-contracts.md` from /plan:
   - Field names match exactly
   - Array vs object matches exactly
   - If mismatch: `⚠ api-contracts.md GET /api/v1/users returns data as object, but data-contracts.md defines it as User[] (array)`
   - Route back to `api_developer` for fix (max 1 retry)
5. **Wireframe cross-reference:** for each wireframe API binding (`| Component | Endpoint | Fields Used |`):
   - The endpoint exists in `api-contracts.md`
   - The fields referenced exist in the contract's response shape
   - List vs single matches what the UI component expects (e.g., a table expects an array, a detail view expects an object)

**If validation fails:**
- Surface specific mismatches: `⚠ Wireframe <screen>.wireframe.md binds <Component> to GET /api/v1/items expecting array, but api-contracts.md shows data as object`
- Route back to `api_developer` for contract fix (max 1 retry)
- After fix: re-validate → then proceed to Build-step B3

**If validation passes:**
```
✅ API Contract Validation — PASS
   Endpoints documented: N/N
   Shape checks: all unambiguous
   Wireframe cross-refs: all matched
   → Proceeding to Build-step B3 (ui_developer)
```

---

> Config blocks checked 2026-09-30 (`bash tests/archetype-compile/config-packs/run.sh --live`): 1 bash block: bash -n (macOS bash 3.2.57) + shellcheck 0.11.0.
