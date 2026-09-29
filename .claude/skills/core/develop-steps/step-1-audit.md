<!-- Part of /develop (~/.claude/commands/startup/develop.md). Read when executing this step. -->

## Step 1 — Audit

**Agents (parallel):**
- `backend_audit_agent` — always runs
- `ui_audit_agent` — runs only if `frontend.enabled = true` in `docs/IMPLEMENTATION_GUIDELINES.md`

Both agents read all Step 0 context. `backend_audit_agent` writes `agent_state/phases/${PHASE}/audit_report.md`. `ui_audit_agent` writes `agent_state/phases/${PHASE}/audit_report_ui.md`.

```markdown
# Phase N Audit Report

## Carried Forward Issues (from Phase N-1)
[Issues from previous manifest's carried_forward[] — MUST appear here]

## Gap Analysis
| Component | Expected (from spec) | Found (in codebase) | Gap |
|-----------|---------------------|---------------------|-----|

## Missing Implementations
- [ ] <component/function> — required by spec <file.md>

## Broken/Incomplete Items
- [ ] <item> — reason

## Recommended Implementation Order
1. ...
```

If `--audit_only` flag: stop here and print the report.

---
