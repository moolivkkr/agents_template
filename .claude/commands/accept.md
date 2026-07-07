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
  - name: force_accept
    required: false
    default: false
    description: "Proceed past a failing cross-phase regression with a logged NOT-READY waiver (sets FORCE_ACCEPT=true). Never produces a READY verdict — it records an explicit override. Use only with a documented reason."
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

### Pre-flight audit

Before running any tests, validate that completed phases are actually complete:

```bash
for PHASE_DIR in agent_state/phases/*/; do
  PHASE_NUM=$(basename "$PHASE_DIR")
  MANIFEST="$PHASE_DIR/manifest.json"
  GATE="$PHASE_DIR/gate.passed"

  # Check 1: gate.passed exists
  [ -f "$GATE" ] || echo "⚠ Phase $PHASE_NUM: gate.passed missing"

  # Check 2: manifest exists and has artifacts
  [ -f "$MANIFEST" ] || echo "⚠ Phase $PHASE_NUM: manifest.json missing"

  # Check 3: artifacts referenced in manifest actually exist on disk
  # (parse manifest.artifacts.code[] and verify each file)

  # Check 4: gate.passed is not stale (warn if > 30 days old)
  if [ -f "$GATE" ]; then
    GATE_AGE=$(( ($(date +%s) - $(stat -f %m "$GATE" 2>/dev/null || stat -c %Y "$GATE" 2>/dev/null)) / 86400 ))
    [ "$GATE_AGE" -gt 30 ] && echo "⚠ Phase $PHASE_NUM: gate is ${GATE_AGE} days old — consider re-running /develop"
  fi

  # Check 5: if gate was forced, surface it
  if [ -f "$GATE" ] && grep -q "FORCED" "$GATE" 2>/dev/null; then
    echo "⚠ Phase $PHASE_NUM: gate was FORCED — review overridden blockers"
  fi
done
```

**Report pre-flight findings before proceeding:**
```
Pre-flight audit:
  Phases planned: N
  Phases gated: N (M forced)
  Missing artifacts: [list or "none"]
  Stale gates: [list or "none"]
  → Proceeding with acceptance testing
```

## Step 0a — Local Deploy + Health Gate

**Acceptance tests run against a LIVE app. This step ensures it is actually built, deployed, and healthy.**

```bash
echo "Deploying locally for acceptance testing..."

# Determine project type from IMPLEMENTATION_GUIDELINES
if [ -f "docker-compose.yml" ] || [ -f "compose.yml" ]; then
  # ── Containerized project ──────────────────────────────────────────
  echo "  Building containers (--no-cache for clean acceptance run)..."
  docker compose build --no-cache 2>&1 | tail -5

  echo "  Starting services..."
  docker compose up -d 2>&1

  # Run pending migrations
  echo "  Running migrations..."
  # Read migration command from IMPLEMENTATION_GUIDELINES
  # e.g., docker compose exec -T api goose up
  # e.g., docker compose exec -T api npx prisma migrate deploy

  # Health check with retry (up to 90s — acceptance needs all services warm)
  echo "  Health checking..."
  HEALTH_URL="http://localhost:${APP_PORT:-8080}/health"
  HEALTHY=false
  for i in $(seq 1 18); do
    if curl -sf "$HEALTH_URL" > /dev/null 2>&1; then
      HEALTHY=true
      break
    fi
    sleep 5
  done

  if [ "$HEALTHY" = true ]; then
    echo "  App healthy at $HEALTH_URL"

    # Verify all required services are running (not just the API)
    EXPECTED_SERVICES=$(docker compose config --services | wc -l | tr -d ' ')
    RUNNING_SERVICES=$(docker compose ps --status running --format json | wc -l | tr -d ' ')
    if [ "$RUNNING_SERVICES" -lt "$EXPECTED_SERVICES" ]; then
      echo "  WARNING: Only $RUNNING_SERVICES/$EXPECTED_SERVICES services running"
      docker compose ps 2>&1
    fi
  else
    echo "  UNHEALTHY after 90s"
    docker compose logs --tail 50 2>&1
    echo ""
    echo "  Attempting restart..."
    docker compose restart 2>&1
    sleep 15
    if curl -sf "$HEALTH_URL" > /dev/null 2>&1; then
      HEALTHY=true
      echo "  Healthy after restart"
    else
      echo ""
      echo "  DEPLOY FAILED — acceptance tests will run against a dead service"
      echo "  This means ALL acceptance results are UNRELIABLE"
      echo "  Fix the deployment before trusting any acceptance results"
      # Record in report — do not silently continue
    fi
  fi

elif [ -f "go.mod" ]; then
  # ── Go CLI/library ─────────────────────────────────────────────────
  echo "  Building Go project..."
  go build ./... 2>&1 || { echo "  BUILD FAILED"; HEALTHY=false; }
  go build -o bin/ ./cmd/... 2>&1 || true
  HEALTHY=true

elif [ -f "package.json" ]; then
  # ── Node project ───────────────────────────────────────────────────
  echo "  Building Node project..."
  npm ci 2>&1 && npm run build 2>&1 || { echo "  BUILD FAILED"; HEALTHY=false; }
  HEALTHY=true

elif [ -f "Cargo.toml" ]; then
  # ── Rust project ───────────────────────────────────────────────────
  echo "  Building Rust project..."
  cargo build --release 2>&1 || { echo "  BUILD FAILED"; HEALTHY=false; }
  HEALTHY=true
fi

# Record deploy status for the acceptance report
mkdir -p agent_state/accept
cat > agent_state/accept/deploy_status.json << EOF
{
  "ts": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "healthy": $( [ "$HEALTHY" = true ] && echo true || echo false ),
  "deploy_type": "$( [ -f docker-compose.yml ] && echo 'docker' || echo 'binary' )",
  "health_url": "${HEALTH_URL:-N/A}"
}
EOF
```

### Deploy health gate

```bash
if [ "$HEALTHY" != true ]; then
  echo ""
  echo "  DEPLOY STATUS: UNHEALTHY"
  echo "  All acceptance test results will be marked UNRELIABLE in the report"
  echo "  Acceptance report header will show: 'TESTED AGAINST: UNHEALTHY DEPLOYMENT'"
  # Continue running tests (they document what fails) but verdict cannot be READY
fi
```

**Impact on release readiness:** If deploy is unhealthy, the acceptance report's release readiness is capped at `NOT READY` regardless of test results. You cannot prove the product works if it won't start.

---

## Step 0b — Full E2E + Integration Regression (ALL phases, ALL tiers)

**Before any acceptance testing, run the complete test suite from ALL phases.**

This is the final cross-phase regression gate. Per-phase gates run regression during `/develop`, but `/accept` is the checkpoint that verifies the ENTIRE product works together after all phases have accumulated.

```bash
echo "Running full cross-phase regression (all tiers, all phases)..."

# Read test commands from IMPLEMENTATION_GUIDELINES
UNIT_CMD=$(read_from_guidelines "unit_test_command")
INTEG_CMD=$(read_from_guidelines "integration_test_command")
E2E_CMD=$(read_from_guidelines "e2e_test_command")

echo "  Tier 1: Unit tests..."
eval "$UNIT_CMD" 2>&1 | tee agent_state/accept/regression_unit.txt
UNIT_EXIT=$?

echo "  Tier 2: Integration tests..."
eval "$INTEG_CMD" 2>&1 | tee agent_state/accept/regression_integration.txt
INTEG_EXIT=$?

echo "  Tier 3: E2E tests..."
eval "$E2E_CMD" 2>&1 | tee agent_state/accept/regression_e2e.txt
E2E_EXIT=$?

echo ""
echo "Cross-phase regression results:"
echo "  Unit:        $([ $UNIT_EXIT -eq 0 ] && echo 'PASS' || echo 'FAIL')"
echo "  Integration: $([ $INTEG_EXIT -eq 0 ] && echo 'PASS' || echo 'FAIL')"
echo "  E2E:         $([ $E2E_EXIT -eq 0 ] && echo 'PASS' || echo 'FAIL')"

if [ $UNIT_EXIT -ne 0 ] || [ $INTEG_EXIT -ne 0 ] || [ $E2E_EXIT -ne 0 ]; then
  echo ""
  echo "⛔ REGRESSION FAILURES DETECTED at the FINAL acceptance gate."
  echo "   Acceptance tests run against a product that passes all lower tiers."
  # ⛔ /accept is the capstone gate before release — a red regression here MUST NOT ship.
  # Cap release readiness at NOT READY and do not emit a "READY" acceptance verdict.
  echo "   Release readiness → NOT READY (regression must be green to release)."
  mkdir -p agent_state/accept
  echo "{\"release_readiness\":\"NOT READY\",\"reason\":\"cross-phase regression failing\",\"unit\":$UNIT_EXIT,\"integration\":$INTEG_EXIT,\"e2e\":$E2E_EXIT}" \
    > agent_state/accept/release-readiness.json
  # Escalation path: fix the regression, or the human explicitly overrides with a documented waiver.
  # Only an explicit --force-accept (with a logged reason) may proceed past this — never a silent continue.
  if [ "${FORCE_ACCEPT:-false}" != "true" ]; then
    echo "   Blocking acceptance. Re-run after the regression is green, or pass --force-accept with a reason."
    exit 1
  fi
  echo "   ⚠ --force-accept set — proceeding with NOT READY recorded. This is a logged waiver, not a pass."
fi
```

### Per-Phase Test Accumulation Summary

```bash
echo ""
echo "Test Accumulation (all phases):"
echo "  Phase | Unit | Integration | E2E | Acceptance"
echo "  ------|------|-------------|-----|----------"
for MANIFEST in agent_state/phases/*/manifest.json; do
  PHASE_NUM=$(python3 -c "import json; print(json.load(open('$MANIFEST')).get('phase','?'))")
  python3 -c "
import json
m = json.load(open('$MANIFEST'))
tr = m.get('test_results', {})
def tier(t):
    r = tr.get(t, {})
    return f\"{r.get('total', 0)}\"
print(f'  {$PHASE_NUM:>5} | {tier(\"unit\"):>4} | {tier(\"integration\"):>11} | {tier(\"e2e\"):>3} | {tier(\"acceptance\")}')
" 2>/dev/null
done
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

## Step 3b — Cross-Phase TC-* ID Inventory Reconciliation

**Purpose:** Verify that ALL test case IDs defined across ALL phase specs are implemented in the final codebase. This catches deferred TC-* IDs that were never picked up by later phases.

### Algorithm

```bash
# 1. Collect ALL TC-* IDs from ALL phase specs
ALL_SPEC_IDS=""
for PHASE_DIR in docs/design/phases/*/; do
  PHASE_NUM=$(basename "$PHASE_DIR")
  SPEC_IDS=$(grep -rhoP 'TC-[A-Z]+-\d+' "$PHASE_DIR/specs/" 2>/dev/null | sort -u)
  ALL_SPEC_IDS="$ALL_SPEC_IDS\n$SPEC_IDS"
done
ALL_SPEC_IDS=$(echo -e "$ALL_SPEC_IDS" | grep 'TC-' | sort -u)
TOTAL_SPEC=$(echo "$ALL_SPEC_IDS" | grep -c 'TC-' 2>/dev/null || echo 0)

# 2. Collect ALL TC-* IDs from ALL test files
ALL_IMPL_IDS=$(grep -rhoP 'TC-[A-Z]+-\d+' tests/ src/ test/ 2>/dev/null \
  --include="*_test.*" --include="*.test.*" --include="*.spec.*" | sort -u)
TOTAL_IMPL=$(echo "$ALL_IMPL_IDS" | grep -c 'TC-' 2>/dev/null || echo 0)

# 3. Reconcile
MISSING=$(comm -23 <(echo "$ALL_SPEC_IDS") <(echo "$ALL_IMPL_IDS"))
MISSING_COUNT=$(echo "$MISSING" | grep -c 'TC-' 2>/dev/null || echo 0)
COVERAGE_PCT=$(( TOTAL_IMPL * 100 / TOTAL_SPEC ))

echo "Global TC-* Inventory: ${TOTAL_IMPL}/${TOTAL_SPEC} (${COVERAGE_PCT}%)"
if [ "$MISSING_COUNT" -gt 0 ]; then
  echo "MISSING: $MISSING_COUNT TC-* IDs never implemented across any phase"
fi
```

### Check per-phase deferred IDs

```bash
# For each phase manifest, check deferred_ids were picked up
for MANIFEST in agent_state/phases/*/manifest.json; do
  PHASE=$(python3 -c "import json; print(json.load(open('$MANIFEST')).get('phase','?'))")
  DEFERRED=$(python3 -c "
import json
m = json.load(open('$MANIFEST'))
inv = m.get('test_case_inventory', {})
deferred = inv.get('deferred_ids', [])
if deferred:
    for d in deferred: print(d)
" 2>/dev/null)
  if [ -n "$DEFERRED" ]; then
    echo "Phase $PHASE deferred TC-* IDs:"
    for ID in $DEFERRED; do
      if echo "$ALL_IMPL_IDS" | grep -q "$ID"; then
        echo "  $ID — RESOLVED (implemented in a later phase)"
      else
        echo "  $ID — STILL MISSING (never implemented)"
      fi
    done
  fi
done
```

### Output

Add to acceptance report:

```markdown
## Global TC-* ID Inventory
| Metric | Value |
|--------|-------|
| Total TC-* IDs (all phases) | N |
| Implemented | N |
| Missing | N |
| Coverage | N% |

### Missing TC-* IDs (Global)
| TC ID | Category | Originally Defined In | Deferred By | Status |
|-------|----------|----------------------|-------------|--------|

### Per-Phase TC-* Coverage
| Phase | Spec Count | Implemented | Deferred | Missing | Coverage |
|-------|-----------|-------------|----------|---------|----------|
```

**Gate impact:** Missing TC-* IDs appear in the acceptance report as findings. If coverage < 100%, the release readiness verdict is `NOT READY` or `CONDITIONAL` — never `READY`.

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

## Step 5b — Pipeline Completeness Validation (Holistic Chain Audit)

**Agent:** `pipeline_completeness_agent`

**Purpose:** Validate the ENTIRE SDLC chain as a connected whole — not just individual links. This is the capstone validation that proves every requirement was carried through BRD -> specs -> code -> tests -> acceptance without being dropped, and every piece of code traces back to a justified requirement.

**Why this runs here (after acceptance, before release notes):** Per-phase reconcilers validate individual links during `/plan` and `/develop`. But no step prior to this verifies:
1. Requirements that were logged as MISSING in reconciliation reports were actually resolved
2. Forced gate blockers were addressed in later phases
3. Requirements split across phases are fully covered when all phases combine
4. The full forward chain (requirements -> acceptance) is unbroken for EVERY requirement
5. The full reverse chain (code -> requirements) has no unjustified artifacts

### Execution

```
Agent prompt: "You are running the Pipeline Completeness Validator.
Read: requirements/, docs/BRD.md, docs/IMPLEMENTATION_GUIDELINES.md
Read: ALL agent_state/reconciliation/ reports (one phase at a time)
Read: ALL agent_state/phases/*/manifest.json (one phase at a time)
Read: agent_state/accept/acceptance_report.md
If exists: agent_state/autonomous/auto-resolved.jsonl

Produce:
  - agent_state/accept/pipeline_completeness_report.md (scored verdict)
  - agent_state/accept/traceability_matrix.md (full forward+reverse chain)
  - agent_state/accept/unresolved_gaps.md (all gaps never resolved)

Follow the 6-step protocol defined in your agent definition."
```

### Verification

```bash
# All three output files must exist
test -f agent_state/accept/pipeline_completeness_report.md || echo "BLOCKED: completeness report missing"
test -f agent_state/accept/traceability_matrix.md || echo "BLOCKED: traceability matrix missing"
test -f agent_state/accept/unresolved_gaps.md || echo "BLOCKED: unresolved gaps report missing"

# Report must contain a scored verdict
if ! grep -qP '(COMPLETE|NEAR COMPLETE|INCOMPLETE|FAILING)' agent_state/accept/pipeline_completeness_report.md 2>/dev/null; then
  echo "BLOCKED: completeness report has no verdict"
fi
```

### Impact on Release Readiness

The completeness verdict feeds directly into the release readiness decision:

| Completeness Verdict | Release Readiness Impact |
|---------------------|--------------------------|
| COMPLETE (95-100%) | No impact — proceed |
| NEAR COMPLETE (80-94%) | Release readiness = `CONDITIONAL` (review unresolved items) |
| INCOMPLETE (60-79%) | Release readiness = `NOT READY` (significant gaps) |
| FAILING (<60%) | Release readiness = `NOT READY` (major chain breaks) |

If the acceptance report says `READY` but completeness says `INCOMPLETE`, the final verdict is `NOT READY`. Completeness is a veto — the product may work, but if traceability is broken, we can't prove it works for the right reasons.

---

## Output: `agent_state/accept/acceptance_report.md`

```markdown
# Global Acceptance Report
<project> — <timestamp>

## Deployment Status
TESTED AGAINST: <HEALTHY | UNHEALTHY | NOT DEPLOYED>
Deploy type: <docker | binary | N/A>
Health URL: <url or N/A>
Deploy log: agent_state/accept/deploy_status.json

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

## Pipeline Completeness
Score: N% — VERDICT
Forward traceability: N/N requirements fully traced
Reverse traceability: N unspecced items
Reconciliation gaps: N/N resolved
Full report: agent_state/accept/pipeline_completeness_report.md
Traceability matrix: agent_state/accept/traceability_matrix.md

## Release Readiness
READY — all use cases pass AND pipeline completeness >= 95%
NOT READY — N failures must be resolved OR pipeline completeness < 80%
CONDITIONAL — N partial passes OR pipeline completeness 80-94%, product owner acceptance required
```

---

## Step 6 — Release Notes Generation

After acceptance report is produced, auto-generate release notes from project artifacts:

1. **Read all phase manifests** — extract `brd_requirements_met` per phase
   ```bash
   for MANIFEST in agent_state/phases/*/manifest.json; do
     # Extract brd_requirements_met array
   done
   ```

2. **Read BRD** — get FR-* titles and OBJ-* descriptions for implemented items
   ```bash
   # Parse docs/BRD.md for each FR-* and OBJ-* referenced in manifests
   ```

3. **Read decision logs** — surface significant architectural decisions
   ```bash
   # Read agent_state/debates/*-verdict.json for key ADRs
   # Read agent_state/phases/*/reports/ for optimization decisions
   ```

4. **Read known issues** — from all `carried_forward[]` and forced gates
   ```bash
   # Parse manifests for carried_forward[]
   # Parse gate.passed files for FORCED flags
   ```

Write `docs/RELEASE_NOTES.md`:

```markdown
# Release Notes — <PROJECT_NAME> v<VERSION>

## What's New
- <FR-001>: <one-line description from BRD>
- <FR-002>: <one-line description>
- ...

## Improvements
- <optimization summaries from code_optimizer reports>

## Known Issues
- <carried_forward items with context>
- <forced gate items with justification>

## Technical Decisions
- <key ADRs summarized — one line each>

## Contributors
- Agents: <list of agents that contributed across all phases>
- Human reviews: <checkpoint decisions from gate files>
```

**Version numbering:**
- If all phases complete with no forced gates: `v1.0.0`
- If any forced gates: `v1.0.0-rc.1`
- If partial phases: `v0.<highest-phase>.0`

---

## Rules

- `/accept` does not replace per-phase acceptance tests — it complements them
- User-provided `requirements/test-data/global.yaml` always takes precedence over generated data
- Realistic seed data — plausible names, valid emails, meaningful content
- Cross-persona flows must be explicit — don't assume inter-persona behavior works without testing it
- Every FR-* in BRD §FR-* must appear in the traceability matrix — gaps are findings
- Unresolved failures block release, not just documentation
