---
skill: structured-lessons
description: Tagged, indexed lessons with confidence levels — the schema and write/read discipline for Tier 1 lessons
version: "1.0"
tags:
  - lessons
  - memory
  - tagging
  - confidence
  - core
---

# Structured Lessons Protocol

Lessons from each phase are currently stored as flat markdown (lessons.md + patterns.md).
This protocol adds structured indexing so downstream agents can query for relevant lessons
instead of loading the entire file.

---

## Enhanced lessons.md Format

Replace the flat format with tagged, categorized entries:

```markdown
# Phase ${PHASE} Lessons Learned
Generated: <timestamp>
Phase goal: <from PHASE_PLAN.md>

## Entries

### L-${PHASE}-001
- **Category:** testing
- **Tags:** go, table-driven, test-setup
- **Type:** pattern_that_worked
- **Summary:** Repository pattern with interface DI eliminated all mocking issues
- **Detail:** Using interfaces for repository layer allowed test agents to mock DB
  without testcontainers. Reduced test setup time by 60%.
- **Evidence:** unit_tests.md — 0 failures on mock-related assertions
- **Reuse:** Always use interface-based repositories for Go projects

### L-${PHASE}-002
- **Category:** implementation
- **Tags:** go, api, serialization
- **Type:** issue_encountered
- **Summary:** Response field `email` silently dropped during JSON serialization
- **Root cause:** struct field tag was `json:"-"` instead of `json:"email"`
- **Fix:** Fixed struct tag, added contract shape assertion in E2E tests
- **Prevention:** spec_impl_reconciler Level 4 (Data Flow) catches this

### L-${PHASE}-003
- **Category:** agent_performance
- **Tags:** context, test-agent
- **Type:** agent_issue
- **Summary:** Single test agent exhausted context on unit tests, produced 0 E2E
- **Root cause:** Agent tried all tiers in one session, ran out of context at tier 2
- **Fix:** Separate agents per tier (Wave 3a/3b/3c)
- **Prevention:** develop-orchestrator enforces separate agents
```

## Categories

| Category | What it captures |
|---|---|
| `testing` | Test patterns, coverage gaps, fixture strategies, flaky test fixes |
| `implementation` | Code patterns, architecture decisions, serialization issues |
| `security` | Auth patterns, IDOR fixes, injection prevention, token handling |
| `performance` | Query optimization, caching decisions, bundle size wins |
| `infrastructure` | Docker issues, migration problems, deployment fixes |
| `agent_performance` | Agent failures, context exhaustion, retry patterns |
| `planning` | Spec quality issues, missing requirements, scope problems |
| `ux` | UI patterns, accessibility fixes, interaction improvements |

## Types

| Type | Meaning |
|---|---|
| `pattern_that_worked` | Repeat this in future phases |
| `issue_encountered` | Bug found and fixed — include prevention strategy |
| `agent_issue` | Agent failure or inefficiency — framework-level fix |
| `anti_pattern` | Something that looked right but caused problems |
| `recommendation` | Suggestion for next phase based on this phase's experience |

## Enhanced patterns.md Format

Cross-phase patterns become a tagged index:

```markdown
# Accumulated Patterns
Last updated: <timestamp>

## Index by Category
- testing: P-001, P-003, P-007
- implementation: P-002, P-004
- security: P-005, P-006
- performance: P-008

## Index by Tag
- go: P-001, P-002, P-004, P-005
- react: P-003, P-007
- postgres: P-006, P-008

## Entries

### P-001
- **Source:** Phase 1, L-1-001
- **Category:** testing
- **Tags:** go, table-driven
- **Pattern:** Use table-driven tests with descriptive subtest names for all Go test functions
- **Evidence:** Phase 1 — 0 test naming issues in review; Phase 3 — adopted, 0 issues
- **Confidence:** HIGH (validated across 2+ phases)

### P-002
- **Source:** Phase 2, L-2-003
- **Category:** implementation
- **Tags:** go, api, middleware
- **Pattern:** Auth middleware must extract tenantID and inject into context before handler
- **Evidence:** Phase 2 — IDOR vulnerability caught by tenant_isolation_verifier
- **Confidence:** HIGH (security-validated)
```

## How Downstream Agents Query

### project_planner (during /plan)

```
When planning Phase N+1:
1. Read agent_state/patterns.md — check Index by Category for the phase's domain
2. If Phase N+1 is a "testing" phase → load all P-* entries tagged "testing"
3. If Phase N+1 is a "security" phase → load all P-* entries tagged "security"
4. Include relevant patterns in the phase_context.md "Lessons from Previous Phases" section
```

### fix agent (during Wave 5)

```
When fixing a failure:
1. Read agent_state/patterns.md Index by Category
2. Search for entries matching the failure's category (e.g., "testing" for test failure)
3. Check if any pattern addresses this exact issue type
4. If match found → apply the known fix pattern instead of reasoning from scratch
```

### backend_developer / api_developer (during Wave 2)

```
When implementing:
1. Read agent_state/patterns.md entries tagged with the project's language (e.g., "go")
2. Follow patterns marked as pattern_that_worked
3. Avoid patterns marked as anti_pattern
```

## Confidence Levels

Patterns accumulate confidence through cross-phase validation:

| Level | Criteria | Weight in planning |
|---|---|---|
| `LOW` | Observed in 1 phase, not yet validated | Informational only |
| `MEDIUM` | Observed in 1 phase, no contradicting evidence | Suggest adoption |
| `HIGH` | Validated across 2+ phases with consistent results | Mandate adoption |
| `DEPRECATED` | Once valid, later phases showed it causes issues | Avoid |

Confidence upgrades happen in the Post-Gate CONSOLIDATE step:
- Pattern used successfully in Phase N+1 → upgrade from LOW to MEDIUM or MEDIUM to HIGH
- Pattern caused issues in Phase N+1 → downgrade to DEPRECATED with reason

## Migration from Current Format

Existing flat `lessons.md` and `patterns.md` files continue to work. The structured format
is additive — agents check for structured entries first, fall back to reading the flat file
if no structured index exists. No breaking change.
