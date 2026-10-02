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
  - name: auto
    required: false
    default: false
    description: "Autonomous mode (set by /autonomous): no prompts; ambiguous results are logged and reported, never waited on."
  - name: force_accept
    required: false
    default: false
    description: "Proceed past a failing cross-phase regression with a logged NOT-READY waiver (sets FORCE_ACCEPT=true). Never produces a READY verdict — it records an explicit override. Use only with a documented reason."
---

# /accept — Global Acceptance Testing

> **Spawning agents:** follow `~/.claude/skills/core/child-returns.md`. Wait for every agent you spawn before using its result, and act on its first line: `NEEDS_INPUT` (ask the user, or record a default under `--auto`), `NEEDS_DECISION <topic>` (run `debate_moderator`, then relaunch the agent with the decision), or a progress note (re-spawn it, at most twice).

> **Auto mode.** `--auto` is set, OR `agent_state/autonomous/run.json` has `"status":"running"` (this
> command was invoked by `/autonomous`). In auto mode, never wait for the user: every "surface to
> user" / "escalate to user" / STOP-for-input point below instead auto-resolves with the recommended
> option, is logged to `agent_state/autonomous/auto-resolved.jsonl` (full question, options, choice,
> rationale, category; `"category":"security","security_flag":true` for security topics), and is
> carried forward to the next human checkpoint. The exception is a security decision with no
> hardened default, which sets `run.json` `status` to `awaiting_human`. The closing "▶ Next: …" line
> is for standalone use only; under `/autonomous`, return control to it without ending the turn.

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
    GATE_AGE=$(( ($(date +%s) - $(stat -c %Y "$GATE" 2>/dev/null || stat -f %m "$GATE" 2>/dev/null)) / 86400 ))
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
if [ -f "deploy/k8s/app.env" ]; then
  # ── Kubernetes lab cluster (skill: infrastructure/lima-k8s-lab.md) ──
  # Release candidate = this tree, built once in dev; qa is RESET (fresh database), re-promoted with
  # dev's exact digests and re-seeded, so acceptance runs on a clean, byte-identical deployment.
  . deploy/k8s/app.env
  DEPLOY_TYPE=k8s; HEALTHY=false
  HEALTH_URL="http://${APP}-qa.localhost:${INGRESS_PORT}"
  if scripts/k8s/deploy.sh dev && scripts/k8s/env-reset.sh qa; then HEALTHY=true; fi
  # deploy.sh qa's verdict already includes smoke + digest parity (qa pods run dev's digests).
  # On the release candidate, acceptance_test_agent runs the committed specs (commands."x:acceptance"),
  # performance_agent the NFR-PERF load test and system_test_agent the qa system checks — each writes its
  # sdlc.test-results/v1 sidecar under agent_state/accept/, and release readiness requires all PASS.
  cat agent_state/deploy/last-deploy-status.json

elif [ -f "docker-compose.yml" ] || [ -f "compose.yml" ]; then
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
  HEALTH_URL="http://localhost:${APP_PORT:-8080}/healthz"   # runtime contract liveness; /readyz for readiness
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

else
  # ── CLI tool / library, any language: the Commands and versions table's install + build rows ──
  V=agent_state/config/verify-commands.json
  HEALTHY=false
  INSTALL="$(jq -r '.commands.install // empty' "$V" 2>/dev/null)"
  BUILD="$(jq -r '.commands.build // empty' "$V" 2>/dev/null)"
  if [ -z "$BUILD" ]; then
    echo "  BUILD NOT RUN — no build row in $V (IMPLEMENTATION_GUIDELINES → Commands and versions)"
  elif { [ -z "$INSTALL" ] || bash -o pipefail -c "$INSTALL"; } && bash -o pipefail -c "$BUILD"; then
    HEALTHY=true
  else
    echo "  BUILD FAILED"
  fi
fi

# Record deploy status for the acceptance report
mkdir -p agent_state/accept
cat > agent_state/accept/deploy_status.json << EOF
{
  "ts": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "healthy": $( [ "$HEALTHY" = true ] && echo true || echo false ),
  "deploy_type": "${DEPLOY_TYPE:-$( [ -f docker-compose.yml ] && echo 'docker' || echo 'binary' )}",
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

# Test commands from the confirmed §Commands and versions table (same helper as /develop's gate; no default, no eval)
read_cmd_from_guidelines() {   # ${1} = purpose in IMPLEMENTATION_GUIDELINES §Commands and versions (test:unit, …)
  local key="${1}" v="agent_state/config/verify-commands.json"
  [ -f "$v" ] || python3 .claude/hooks/commands-table.py docs/IMPLEMENTATION_GUIDELINES.md --out "$v" >/dev/null || return 1
  jq -r --arg k "$key" '.commands[$k] // empty' "$v"
}
UNIT_CMD=$(read_cmd_from_guidelines 'test:unit')
INTEG_CMD=$(read_cmd_from_guidelines 'test:integration')
E2E_CMD=$(read_cmd_from_guidelines 'test:e2e')
for pair in "unit:$UNIT_CMD" "integration:$INTEG_CMD" "e2e:$E2E_CMD"; do
  [ -n "${pair#*:}" ] || echo "⛔ REGRESSION BLOCKED: no ${pair%%:*} test command in IMPLEMENTATION_GUIDELINES (an empty command would 'pass' by running nothing)"
done

echo "  Tier 1: Unit tests..."
PHASE=accept bash -o pipefail -c "$UNIT_CMD" > agent_state/accept/regression_unit.txt 2>&1; UNIT_EXIT=$?; tail -40 agent_state/accept/regression_unit.txt   # $? of the test itself, not of a tee

echo "  Tier 2: Integration tests..."
PHASE=accept bash -o pipefail -c "$INTEG_CMD" > agent_state/accept/regression_integration.txt 2>&1; INTEG_EXIT=$?; tail -40 agent_state/accept/regression_integration.txt   # $? of the test itself, not of a tee

echo "  Tier 3: E2E tests..."
PHASE=accept bash -o pipefail -c "$E2E_CMD" > agent_state/accept/regression_e2e.txt 2>&1; E2E_EXIT=$?; tail -40 agent_state/accept/regression_e2e.txt   # $? of the test itself, not of a tee

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

## Step 1a — Requirements → Acceptance Map (the BRD as it is TODAY)

`/accept` proves the current BRD, not the BRD each phase saw. Requirements change between phases
(change requests, `/recon --fix=docs --apply`, hand edits) and phases add FRs, so first compute which
FRs have tests that match their current text:
```bash
python3 .claude/hooks/acceptance-map.py --all --out agent_state/accept/acceptance_map.json || true
jq -r '(.delta.add[] | "\(.fr) \(.status) phases=\(.phases|join(",")) \(.detail)"),
       (.delta.update[] | "\(.fr) CHANGED phases=\(.phases|join(",")) \(.detail)"),
       (.delta.retire_rows[] | "retire row \(.id) (\(.reason))"),
       (.delta.retire_tests[] | "retire test \(.id) (\(.reason))")' agent_state/accept/acceptance_map.json
jq -r '.delta.retire_needs_decision[] | "needs decision: \(.kind) \(.id) (phase \(.owner // "?")) \(.reason)"' agent_state/accept/acceptance_map.json
```
`/accept` has no working phase, so `retire_rows`/`retire_tests` are always empty here: **it never
removes an acceptance row or test**. Candidates for removal (rows and tests for requirements that were
dropped or marked Won't, or stale tests) print as "needs decision" with their owning phase.

| Status | What it means | What `/accept` does now |
|---|---|---|
| CHANGED | the FR's text changed after its tests were recorded; they check the old criteria | `spec_writer` `MODE: acceptance-amend` rewrites its TC-ACC rows in the owning phase; Step 3 updates the tests |
| NEW / PARTIAL, as-built or in a gated phase | behaviour exists, rows are missing | same: amend rows, then Step 3 writes the tests |
| NEW, in no phase, not as-built | a requirement nobody has built yet | not fixable here: it stays blocking; the report says "run `/plan`" |
| needs decision (removal candidate) | the FR was dropped or marked Won't, or a test's row is gone | **nothing is removed.** The report lists each with its owning phase under "Acceptance rows/tests awaiting a removal decision"; release readiness is at most `CONDITIONAL` while any remain |

Spawn `spec_writer` (subagent_type: spec_writer) once with `MODE: acceptance-amend`, no
`WORKING_PHASE`, and the fixable FR lines (add/update only), wait for it, and pass the same lines to
Step 3's `acceptance_test_agent` as `CHANGED_FRS`. Neither deletes anything in `/accept`. For a CHANGED
FR whose SHALL was removed, the old row and test stay, noted as pending retirement.

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

**Agent:** `acceptance_test_agent` (its `/accept` mode), with `CHANGED_FRS` from Step 1a.

It runs the **whole committed suite** (`tests/acceptance/`, every phase's TC-ACC tests, through
`commands."x:acceptance"`) against the release candidate, after updating the tests for the
`CHANGED_FRS` rows. Sidecar: `agent_state/accept/acceptance_report.json`. New phases' tests are in
the suite because each phase committed them; changed requirements' tests were brought up to date in
Step 1a; the coverage check after the run (below) proves both.

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

### Requirement coverage check (after the run)
```bash
S=agent_state/accept/acceptance_report.json    # the acceptance_test_agent sidecar for this run
python3 .claude/hooks/acceptance-map.py --all --results "$S" --merge-into "$S" --out agent_state/accept/acceptance_map.json
MAP_RC=$?   # 0 = every Must/Should FR in the BRD has current, passing acceptance tests
```
`agent_state/accept/acceptance_map.md` is the live requirement → test matrix (it replaces the old
`docs/traceability-matrix.md`). `MAP_RC != 0` caps release readiness at `NOT READY` and lists the FRs.
Any `delta.retire_needs_decision` item caps it at `CONDITIONAL` (a removal the owning phase or a human
has to decide).
When the release verdict is READY, record the baseline so the next requirement change is detected:
```bash
python3 .claude/hooks/acceptance-map.py --all --results "$S" --record --out agent_state/accept/acceptance_map.json
```
An FR the product owner says still holds after a wording-only change: `--ack FR-xxx "<why the tests
still hold>"` (human decision; it is kept in the baseline).

---

## Step 3b — Cross-Phase TC-* ID Inventory Reconciliation

**Purpose:** Verify that ALL test case IDs defined across ALL phase specs are implemented in the final codebase. This catches deferred TC-* IDs that were never picked up by later phases.

### Algorithm

```bash
# One deterministic inventory per phase, against THIS acceptance run's results when present.
RES="agent_state/accept/test_results.json"   # written by the Step 0b regression (test_runner, all phases)
mkdir -p agent_state/accept/tc
# The graph's inventory (tc-inventory.py's rules + range-defined and malformed IDs); built once, then queried.
# D-002: range-defined and malformed IDs are WARNINGS (warnings[], not in missing/failed) unless
# agent_state/config/gate-policy.json enforces them; they go in the acceptance report as warnings.
# --source when there is no regression sidecar, so another run's stale sidecars in reports/ aren't picked up.
python3 .claude/hooks/sdlc-graph.py build >/dev/null; GRC=$?
for PD in docs/design/phases/*/; do
  N=$(basename "$PD")
  if [ "$GRC" -eq 0 ]; then
    python3 .claude/hooks/sdlc-graph.py --no-refresh tc --phase "$N" $( [ -f "$RES" ] && echo --results "$RES" || echo --source) \
      --out "agent_state/accept/tc/phase-$N.json" >/dev/null || true
  else   # graph unavailable: same rules without the range/malformed checks — say so in the acceptance report
    python3 .claude/hooks/tc-inventory.py --phase "$N" $( [ -f "$RES" ] && echo --results "$RES") \
      --out "agent_state/accept/tc/phase-$N.json" >/dev/null || true
  fi
done
python3 - <<'PY'
import glob, json
inv = [json.load(open(f)) for f in sorted(glob.glob("agent_state/accept/tc/phase-*.json"))]
total = sum(i["total"] for i in inv); covered = sum(i["passed"] for i in inv)
missing = sorted({m for i in inv for m in i["missing"] + i["failing"]})
dups = sorted({d for i in inv for d in i["duplicate_ids"]})
print(f"Global TC-* Inventory: {covered}/{total} HIGH+MEDIUM covered ({100 * covered // max(total, 1)}%)")
if missing: print(f"MISSING/FAILING: {len(missing)} — " + ", ".join(missing[:40]))
if dups: print(f"IDs defined by more than one phase (ambiguous coverage): {', '.join(dups)}")
warn = {}
for i in inv:
    for w in i.get("warnings", []):
        warn[w["check"]] = warn.get(w["check"], 0) + w["count"]
if warn:   # not blocking (D-002), never silent: list them in the acceptance report with the policy in force
    pol = next((i["policy"] for i in inv if i.get("policy")), {})
    print("WARNINGS (D-002, not blocking): " + ", ".join(f"{k} {v}" for k, v in sorted(warn.items()))
          + f" — policy: {pol.get('source', 'n/a')}; list: sdlc-graph.py warnings; enforce: sdlc-graph.py policy --strict")
json.dump({"covered": [c["name"] for i in inv for c in i["cases"] if c["verdict"] == "PASS"]},
          open("agent_state/accept/tc/covered.json", "w"))
PY
ALL_IMPL_IDS="$(jq -r '.covered[]' agent_state/accept/tc/covered.json)"   # used by the deferred-ID check below
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
Agent prompt (subagent_type: pipeline_completeness_agent): "You are running the Pipeline Completeness Validator.
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
if ! grep -qE '(COMPLETE|NEAR COMPLETE|INCOMPLETE|FAILING)' agent_state/accept/pipeline_completeness_report.md 2>/dev/null; then
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

## Requirements → Acceptance (agent_state/accept/acceptance_map.md)
FRs: N · COVERED N · CHANGED N · NEW N · PARTIAL N · FAILING N · UNTESTED N · orphan TC-ACC rows N

## Release Readiness
READY — all use cases pass AND every Must/Should FR is COVERED in the acceptance map AND pipeline completeness >= 95%
NOT READY — N failures must be resolved OR pipeline completeness < 80%
CONDITIONAL — N partial passes OR pipeline completeness 80-94%, product owner acceptance required
```

---

## Step 6 — Release Notes Generation

Runs when `python3 .claude/hooks/docs-policy.py is-on release_notes` exits 0 (on in the lean profile:
generated from manifests, not maintained by hand). After the acceptance report is produced,
auto-generate release notes from project artifacts:

1. **Read all phase manifests** — extract `brd_requirements_met` per phase
   ```bash
   for MANIFEST in agent_state/phases/*/manifest.json; do
     jq -r '.brd_requirements_met[]?' "$MANIFEST"   # Extract brd_requirements_met array
   done
   ```

2. **Read BRD** — get FR-* titles and OBJ-* descriptions for implemented items
   ```bash
   # Parse docs/BRD.md for each FR-* and OBJ-* referenced in manifests
   ```

3. **Read decision logs** — surface significant architectural decisions
   ```bash
   python3 .claude/hooks/debate-status.py --json   # every debated decision, its D-NNN and any review reason
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
- **Accepted security findings are never shippable.** For every phase, list
  `gate.forced.security_acknowledged[]` and re-check each finding against the current code (the
  `security_reviewer` count line or a targeted re-review). Any that is still present caps release
  readiness at **NOT READY**, not `-rc`. Accepting a risk kept the pipeline moving; it doesn't release it.
- If partial phases: `v0.<highest-phase>.0`

---

## Rules

- `/accept` does not replace per-phase acceptance tests — it complements them
- User-provided `requirements/test-data/global.yaml` always takes precedence over generated data
- Realistic seed data — plausible names, valid emails, meaningful content
- Cross-persona flows must be explicit — don't assume inter-persona behavior works without testing it
- Every FR-* in BRD §FR-* must appear in the traceability matrix — gaps are findings
- Unresolved failures block release, not just documentation
