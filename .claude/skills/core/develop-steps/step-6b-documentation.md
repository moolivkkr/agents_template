<!-- Part of /develop (~/.claude/commands/startup/develop.md). Read when executing this step. -->

## Step 6b — Documentation (optional; runs in parallel with gate file writes)

**Agent:** `documentation_agent`
**Runs only when** `python3 .claude/hooks/docs-policy.py is-on developer_docs` exits 0 (off in the lean
docs profile). When off, skip it: record `developer_docs: skipped (docs policy)` in the manifest's
`skipped_agents[]` and don't list it in the roster. The user can generate a fresh set with `/docs developer`.

Generates or updates developer-facing documentation for all artifacts produced this phase:
- API endpoint docs (OpenAPI/Swagger update or equivalent)
- Updated `README.md` sections for new components
- Any doc annotations from code review comments

Output: `agent_state/phases/${PHASE}/reports/documentation_update.md` — summary of what was added/updated.

Does NOT block gate passage. Runs in parallel with gate file writes.

---
