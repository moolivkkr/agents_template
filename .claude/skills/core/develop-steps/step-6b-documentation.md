<!-- Part of /develop (~/.claude/commands/startup/develop.md). Read when executing this step. -->

## Step 6b — Documentation (runs in parallel with gate file writes)

**Agent:** `documentation_agent`

Generates or updates developer-facing documentation for all artifacts produced this phase:
- API endpoint docs (OpenAPI/Swagger update or equivalent)
- Updated `README.md` sections for new components
- Any doc annotations from code review comments

Output: `agent_state/phases/${PHASE}/reports/documentation_update.md` — summary of what was added/updated.

Does NOT block gate passage. Runs in parallel with gate file writes.

---
