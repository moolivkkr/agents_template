---
command: accept
description: Global acceptance testing across all completed phases. Validates the full product against ALL BRD personas and use cases. Runs after all phases are implemented.
arguments:
  - name: persona
    required: false
    description: "Run acceptance for a specific persona only (e.g. --persona='Admin User')"
  - name: use_case
    required: false
    description: "Run a specific use case only (e.g. --use_case=FR-007)"
  - name: reseed
    required: false
    default: false
    description: "Force re-seed even if seed data exists from per-phase runs"
---

# /accept — Global Acceptance Testing

Full-product acceptance testing. Validates the complete system against ALL BRD personas and ALL FR-* use cases — not just those scoped to a single phase. This is the final human-readable proof that the product delivers its promises.

**Prerequisites:** All phases must have passing gates (`agent_state/phases/*/gate.passed`).

## Session Context Budget

**Do NOT load all phase manifests into conversation simultaneously.** Read each manifest to extract the `brd_requirements_met` and `acceptance_tests.personas_exercised` fields only — not the full JSON. Build the global use case map from these field extracts (~500 tokens per phase), not from full file loads.

**Per use case execution:** Load BRD persona description (1 paragraph) + the specific FR-* acceptance criteria rows (not the full requirement). Target ~2K tokens per use case execution context.

---

## Step 0 — Pre-flight

```bash
# Verify all phases gated
TOTAL_PLANNED=$(ls docs/design/phases/ | wc -l)
TOTAL_PASSED=$(ls agent_state/phases/*/gate.passed 2>/dev/null | wc -l)

if [ "$TOTAL_PLANNED" != "$TOTAL_PASSED" ]; then
  echo "⚠ Not all phases complete:"
  # diff planned vs passed — list missing
fi
```

Warn if phases are incomplete — but do not block. Acceptance can run on partially complete product (results will reflect gaps).

Start full stack:
```bash
# Read startup commands from docs/IMPLEMENTATION_GUIDELINES.md §Local Dev
docker compose up -d  # (or equivalent)
```

---

## Step 1 — Build Global Use Case Map

**Agent:** `acceptance_test_agent`

Read `docs/BRD.md`:
- ALL personas defined in §Personas
- ALL FR-* requirements with user-facing acceptance criteria
- ALL gate checklist items

Cross-reference with `agent_state/phases/*/manifest.json`:
- Which use cases were tested per-phase?
- Any unresolved acceptance failures carried forward?

Build a complete use case map:
```yaml
personas:
  - name: "Admin User"
    use_cases: [FR-001, FR-005, FR-010, FR-015]
  - name: "End User"
    use_cases: [FR-002, FR-003, FR-006, FR-007, FR-011]
  - name: "Analyst"
    use_cases: [FR-008, FR-012, FR-013]

cross_persona_flows:
  - name: "Admin creates resource, End User consumes it"
    use_cases: [FR-005, FR-006]
    description: "Tests that admin and user workflows interact correctly"
```

---

## Step 2 — Prepare Global Seed Data

### Priority order for seed data:
1. `requirements/test-data/global.yaml` — user-provided global dataset (highest priority)
2. `requirements/test-data/` — any phase-specific files, merged
3. Auto-generated from BRD personas and use cases

```yaml
# requirements/test-data/global.yaml (optional — user provides this)
# Drop this file in requirements/test-data/ before running /accept
# to control exactly what data the acceptance suite uses

personas:
  admin_user:
    credentials: { email: "admin@accept-test.com", password: "GlobalAccept!1" }
    pre_created_data:
      - entity: Role
        data: { name: "admin", ... }

  end_user:
    credentials: { email: "user@accept-test.com", password: "GlobalAccept!1" }

  analyst:
    credentials: { email: "analyst@accept-test.com", password: "GlobalAccept!1" }

shared_data:
  - entity: Category
    data: { name: "Test Category", slug: "test-category" }
```

### Seed the system
Apply all seed data via API or direct DB (prefer API — exercises the API surface):
```bash
# Via seed endpoint if available
curl -sf -X POST http://localhost:PORT/api/v1/_test/seed \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d @agent_state/accept/seed-data.yaml

# Or per-entity via normal API routes
```

Write applied seed to `agent_state/accept/seed-applied.yaml` for traceability.

---

## Step 3 — Execute Global Use Cases

**Agent:** `acceptance_test_agent`

Execute use cases in this order:
1. **Foundation use cases** — auth, basic CRUD (unblocks all other tests)
2. **Per-persona use cases** — each persona's primary workflows
3. **Cross-persona flows** — interactions between personas
4. **Edge case use cases** — error paths, permission boundaries, limits

### Cross-persona flow example
```
CROSS-PERSONA FLOW: Admin creates resource → End User consumes it

Step 1 [Admin User]:
  POST /api/v1/resources { "name": "Shared Resource" }
  Expected: 201 Created → resource_id captured

Step 2 [End User]:
  GET /api/v1/resources/:resource_id
  Expected: 200 OK — End User can access Admin-created resource

Step 3 [Analyst]:
  GET /api/v1/analytics/resources
  Expected: 200 OK — resource appears in analytics

Acceptance criteria:
  ✅ Admin created resource visible to End User immediately
  ✅ Analyst analytics reflect the new resource
  ✅ Permissions enforced (End User cannot DELETE the resource)
```

### Iteration on failure
- Fix → re-test → max 2 rounds per use case
- Failures after 2 rounds: logged as unresolved, product owner must accept risk before release

---

## Step 4 — BRD Traceability Validation

After all use cases run, produce a traceability matrix:

```markdown
| FR-*  | Use Case Title | Persona | Acceptance Criteria Met | Status |
|-------|---------------|---------|------------------------|--------|
| FR-001 | User Registration | New User | 3/3 | ✅ PASS |
| FR-002 | User Login | End User | 2/2 | ✅ PASS |
| FR-007 | Export Report | Analyst | 2/3 | ⚠ PARTIAL |
| FR-010 | Admin Invite | Admin | FAIL — endpoint 404 | ❌ FAIL |
```

Every FR-* in the BRD must appear in this matrix. Uncovered = not implemented or not tested.

---

## Step 5 — Seed Cleanup Documentation

Write `agent_state/accept/cleanup.md`:
```markdown
# Acceptance Test Cleanup

## What was seeded
[Entity list with counts]

## Reset commands
[Exact commands to remove test data — SQL, API calls, or docker volume reset]
```

---

## Output: `agent_state/accept/acceptance_report.md`

```markdown
# Global Acceptance Report
<project> — <timestamp>

## Executive Summary
N/N use cases PASSED | N PARTIAL | N FAILED
N/N personas fully covered
N/N FR-* requirements validated

## Persona Coverage
| Persona | Use Cases | Passed | Partial | Failed |
|---------|-----------|--------|---------|--------|

## BRD Traceability Matrix
| FR-* | Use Case | Persona | Criteria | Status |

## Cross-Persona Flows
| Flow | Steps | Status |

## Carried Forward Issues
[Unresolved failures from per-phase acceptance runs]

## Unresolved Failures (new)
[Use cases that failed in global run with reproduction steps]

## Seed Data
Source: <user-provided | auto-generated>
File: agent_state/accept/seed-applied.yaml
Cleanup: agent_state/accept/cleanup.md

## Release Readiness
READY — all use cases pass
NOT READY — N failures must be resolved before release
CONDITIONAL — N partial passes, product owner acceptance required
```

---

## Rules

- `/accept` does not replace per-phase acceptance tests — it complements them
- User-provided `requirements/test-data/global.yaml` always takes precedence over generated data
- Realistic seed data — plausible names, valid emails, meaningful content
- Cross-persona flows must be explicit — don't assume inter-persona behavior works without testing it
- Every FR-* in BRD §FR-* must appear in the traceability matrix — gaps are findings
- Unresolved failures block release, not just documentation
