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

Full-product acceptance testing against ALL BRD personas and ALL FR-* use cases — not single-phase scoped. Final human-readable proof the product delivers its promises.

**Prerequisites:** All phases must have passing gates (`agent_state/phases/*/gate.passed`).

## Session Context Budget

**Do NOT load all phase manifests simultaneously.** Extract only `brd_requirements_met` and `acceptance_tests.personas_exercised` per manifest (~500 tokens/phase). Per use case: load BRD persona (1 paragraph) + specific FR-* criteria rows (~2K tokens/use case).

---

## Step 0 — Pre-flight

```bash
TOTAL_PLANNED=$(ls docs/design/phases/ | wc -l)
TOTAL_PASSED=$(ls agent_state/phases/*/gate.passed 2>/dev/null | wc -l)
[ "$TOTAL_PLANNED" != "$TOTAL_PASSED" ] && echo "⚠ Not all phases complete"
```

Warn if incomplete — do not block. Acceptance can run on partial product.

### Pre-flight audit
```bash
for PHASE_DIR in agent_state/phases/*/; do
  PHASE_NUM=$(basename "$PHASE_DIR")
  GATE="$PHASE_DIR/gate.passed"
  [ -f "$PHASE_DIR/manifest.json" ] || echo "⚠ Phase $PHASE_NUM: manifest.json missing"
  [ -f "$GATE" ] || echo "⚠ Phase $PHASE_NUM: gate.passed missing"
  if [ -f "$GATE" ]; then
    GATE_AGE=$(( ($(date +%s) - $(stat -f %m "$GATE" 2>/dev/null || stat -c %Y "$GATE" 2>/dev/null)) / 86400 ))
    [ "$GATE_AGE" -gt 30 ] && echo "⚠ Phase $PHASE_NUM: gate is ${GATE_AGE} days old"
    grep -q "FORCED" "$GATE" 2>/dev/null && echo "⚠ Phase $PHASE_NUM: gate was FORCED"
  fi
done
```

Report findings, then start full stack:
```bash
docker compose up -d  # or equivalent from IMPLEMENTATION_GUIDELINES
```

---

## Step 1 — Build Global Use Case Map

**Agent:** `acceptance_test_agent`

Read `docs/BRD.md` (all personas, all FR-*, all gate checklists). Cross-reference with `agent_state/phases/*/manifest.json` for per-phase coverage and carried-forward failures.

Build complete map:
```yaml
personas:
  - name: "Admin User"
    use_cases: [FR-001, FR-005, FR-010]
cross_persona_flows:
  - name: "Admin creates resource, End User consumes it"
    use_cases: [FR-005, FR-006]
```

---

## Step 2 — Prepare Global Seed Data

**Priority:** 1) `requirements/test-data/global.yaml` (user-provided) 2) phase-specific files merged 3) auto-generated from BRD

Seed via API (preferred) or direct DB. Write applied seed to `agent_state/accept/seed-applied.yaml`.

---

## Step 3 — Execute Global Use Cases

**Agent:** `acceptance_test_agent`

**Order:** 1) Foundation (auth, CRUD) 2) Per-persona workflows 3) Cross-persona flows 4) Edge cases

Cross-persona flows test that multi-persona interactions work correctly (admin creates → user consumes → analyst sees in analytics → permissions enforced).

**Iteration:** Fix → re-test → max 2 rounds per use case. Unresolved → logged, product owner must accept risk.

---

## Step 4 — BRD Traceability Validation

Produce traceability matrix: every FR-* in BRD mapped to use case, persona, criteria met, PASS/PARTIAL/FAIL status. Uncovered = not implemented or not tested.

---

## Step 5 — Seed Cleanup Documentation

Write `agent_state/accept/cleanup.md` with entity counts and exact reset commands.

---

## Output: `agent_state/accept/acceptance_report.md`

```markdown
# Global Acceptance Report
<project> — <timestamp>

## Executive Summary
N/N use cases PASSED | N PARTIAL | N FAILED
N/N personas fully covered | N/N FR-* validated

## Persona Coverage / BRD Traceability Matrix / Cross-Persona Flows
## Carried Forward Issues / Unresolved Failures (new)
## Seed Data (source, file, cleanup reference)

## Release Readiness
READY | NOT READY (N failures) | CONDITIONAL (N partial, PO acceptance required)
```

---

## Step 6 — Release Notes Generation

1. Read all phase manifests → extract `brd_requirements_met`
2. Read BRD → FR-* titles and OBJ-* descriptions
3. Read decision logs → significant ADRs
4. Read known issues → `carried_forward[]` and forced gates

Write `docs/RELEASE_NOTES.md`: What's New (FR-* list), Improvements, Known Issues, Technical Decisions, Contributors.

**Version:** All phases + no forced gates → `v1.0.0` | Forced gates → `v1.0.0-rc.1` | Partial → `v0.<highest-phase>.0`

---

## Rules

- `/accept` complements per-phase acceptance tests, doesn't replace them
- User-provided `global.yaml` always takes precedence over generated data
- Realistic seed data — plausible names, valid emails, meaningful content
- Cross-persona flows must be explicitly tested
- Every FR-* in BRD must appear in traceability matrix — gaps are findings
- Unresolved failures block release, not just documentation
