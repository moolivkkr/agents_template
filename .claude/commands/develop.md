---
command: develop
description: Implement a phase end-to-end. Audit → implement → test (unit + integration + e2e) → review → gate. Auto-detects current phase. Zero required inputs.
arguments:
  - name: phase
    required: false
    description: "Override phase number. Omit to auto-detect from gate state."
  - name: audit_only
    required: false
    default: false
    description: "Produce gap report only — no implementation, no code changes"
  - name: test_only
    required: false
    default: false
    description: "Run tests only — no implementation changes"
  - name: force_gate
    required: false
    default: false
    description: "Force gate to pass even with failures (e.g. known test flakes). Writes gate.passed with ⚠ FORCED flag. Use with caution."
  - name: auto
    required: false
    default: false
    description: "Autonomous mode — all escalations use recommended defaults. Gate failures auto-fix (max 3 cycles) then force-gate with logging. No user prompts."
---

# /develop — Autonomous Phase Implementation

Fully autonomous phase implementation. Detects where you are, implements all specs, tests, reviews, and writes the phase gate.

**One decision point:** at the end — advance to the next phase or not.

**Concurrent access:** Single developer per phase assumed. Two developers on same phase → file conflicts in `agent_state/phases/N/`.

---

## Agent Execution Logging Protocol

Every agent appends to `agent_state/phases/${PHASE}/execution.jsonl` (append-only, read at Step 7):

```json
{"ts":"<ISO>","agent":"<agent_name>","phase":N,"step":"<step_id>","status":"started"}
{"ts":"<ISO>","agent":"<agent_name>","phase":N,"step":"<step_id>","status":"completed","duration_s":<N>,"findings":{"blocking":<N>,"warning":<N>},"output":"<primary_output_path>"}
{"ts":"<ISO>","agent":"<agent_name>","phase":N,"step":"<step_id>","status":"failed","error":"<one_line_reason>","attempt":<N>}
{"ts":"<ISO>","event":"pipeline_complete","phase":N,"status":"gate_passed|gate_failed|gate_forced","total_duration_s":<N>,"agents_run":<N>,"agents_failed":<N>}
```

---

## Session Context Budget

> Full protocol: `.claude/skills/core/context-budget-protocol.md`.

**Agent result discipline:** Every agent ends with:
```
✅ <agent-name> complete → wrote <output-file-path>
   Summary: <3 lines max>
   Issues: none | <count + severity>
```
Never echo file contents back to parent conversation.

**Read discipline:** Read → act → don't re-read same file in same step. `phase_context.md` read once at Step 0, referenced from memory thereafter.

**Step isolation:** Each step writes output files then finishes. Mid-step context overflow → resume by reading output files from `agent_state/phases/${PHASE}/`.

**Per-step context budget targets:**
| Step | Target | What to load |
|------|--------|---|
| Step 0 Orient | ~10K | phase_context.md (6-8K) + gate files |
| Step 1 Audit | ~20K | phase_context.md + per-spec file (one at a time) + prev manifest |
| Step 2 Implement (per agent) | ~25K | phase_context.md + own component spec + prev manifest |
| Step 3 Test | ~20K | phase_context.md + git diff this phase + spec edge cases |
| Step 3d Reconcile C | ~25K | all phase specs + agent implementation summaries (from manifests) |
| Step 3e Reconcile D | ~20K | spec test-coverage sections + test file list |
| Step 3f Optimize (per agent) | ~20K | phase_context.md + git diff this phase + skill pack patterns |
| Step 3g Re-test | ~10K | test commands only |
| Step 4 Review | ~20K | code diff this phase only + skill pack patterns |
| Step 5 Acceptance | ~15K | phase_context.md requirements + acceptance criteria + seed data |
| Step 6 Gate | ~8K | report file first 20 lines each (summary rows only) |

`phase_context.md` is 6-8K but replaces 30-70K of BRD + IMPL_GUIDELINES. Loading it in every step is intentional.

---

## Pipeline Anti-Rationalization Guard

Never skip a step, shortcut a gate, or accept partial results.

| Your Internal Reasoning | Correct Response |
|---|---|
| "Tests pass, so implementation is correct" | Tests verify what author thought to check. Specs define what MUST exist. Run reconciliation. |
| "Simple phase, skip audit" | Simple phases hide assumptions. Run the audit. |
| "Only one minor blocker, I'll pass it" | A blocker is a blocker. Fix it or `--force_gate` with user approval. |
| "I reviewed this when I wrote it" | Authors don't find their own bugs. Reviewers are separate agents for a reason. |
| "Optimization not needed — barely any code" | Runs every phase. 5 lines of dead code compound over 10 phases. |
| "Previous phase tests still pass, skip regression" | Run anyway. Silent import breakage is #1 cross-phase regression. |
| "Skip acceptance — unit/integration cover everything" | Unit/integration test code paths. Acceptance tests verify USER EXPERIENCE. |
| "Combine review stages to save time" | Spec compliance and code quality are DIFFERENT concerns. Keep separate. |

---

## Phase Re-Development Protocol

When re-developing (e.g., `gate.passed` removed or `/reset-phase` run):

```bash
# Archive previous attempt
ATTEMPT=$(git tag -l "phase-${PHASE}-attempt-*" | wc -l | tr -d ' ')
ATTEMPT=$((ATTEMPT + 1))
git tag "phase-${PHASE}-attempt-${ATTEMPT}" -m "Phase ${PHASE} attempt ${ATTEMPT}: $(date)"
if [ -d "agent_state/phases/${PHASE}/reports" ]; then
  mv "agent_state/phases/${PHASE}/reports" "agent_state/phases/${PHASE}/reports.attempt-${ATTEMPT}"
fi
rm -f agent_state/phases/${PHASE}/.*_ready
```

During re-run: all agents run fresh (no caching). Previous code NOT auto-reverted. Clean slate → user should `git reset` to tag first.

After completion manifest includes: `"attempt": N, "previous_attempts": [...]`. Gate report includes diff from previous attempt showing blocker resolution progression.

### Detection (Step 0)
```bash
if [ -d "agent_state/phases/${PHASE}/reports" ] || [ -d "agent_state/phases/${PHASE}/reports.attempt-1" ]; then
  echo "⚠ Phase ${PHASE} re-development detected — archiving previous attempt"
fi
```

---

## Step 0 — Orient

### Detect current phase
```bash
LAST_PASSED=$(ls agent_state/phases/*/gate.passed 2>/dev/null | grep -oP 'phases/\K\d+' | sort -n | tail -1)
PHASE=${ARG_PHASE:-$(( ${LAST_PASSED:-0} + 1 ))}
echo "▶ Running Phase $PHASE"
```

### Initialize Execution Log
```bash
mkdir -p agent_state/phases/${PHASE}
echo "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"pipeline_start\",\"phase\":${PHASE},\"attempt\":${ATTEMPT:-1}}" >> agent_state/phases/${PHASE}/execution.jsonl
```

### Failure Pattern Detection

```bash
PREV_FAILURES=$(ls agent_state/phases/${PHASE}/gate.failed* 2>/dev/null)
if [ -n "$PREV_FAILURES" ]; then
  echo "⚠ Phase ${PHASE} has previous failure(s):"
  for f in $PREV_FAILURES; do
    BLOCKERS=$(python3 -c "import json; d=json.load(open('$f')); print(', '.join(b.get('gate_item','?') for b in d.get('blockers',[])))" 2>/dev/null)
    echo "  - $(basename $f): blocked by $BLOCKERS"
  done
fi
```

Previously-failed steps get extra scrutiny: test steps run TWICE (normal + verbose), review steps lower threshold (MEDIUM → BLOCKING for failing areas), gate explicitly verifies previously-blocking items first.

### Phase Lock (Advisory)

```bash
LOCK_FILE="agent_state/phases/${PHASE}/.lock"
if [ -f "$LOCK_FILE" ]; then
  LOCK_OWNER=$(cat "$LOCK_FILE" | head -1)
  LOCK_TIME=$(cat "$LOCK_FILE" | tail -1)
  echo "⚠ Phase ${PHASE} is locked by ${LOCK_OWNER} since ${LOCK_TIME}"
  echo "  If stale, remove with: rm ${LOCK_FILE}"
  # --auto mode: STOP. Interactive: ask user.
fi
echo "$(whoami)@$(hostname)" > "$LOCK_FILE"
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$LOCK_FILE"
```
Release at end of Step 6: `rm -f "agent_state/phases/${PHASE}/.lock"`

### Gate check
- PHASE > 1 and `agent_state/phases/$((PHASE-1))/gate.passed` missing → **STOP** — run previous phase first
- `docs/design/phases/${PHASE}/INDEX.md` missing → auto-run `/plan --phase=${PHASE}` first

### Load previous phase context
Read `agent_state/phases/$((PHASE-1))/manifest.json` (if PHASE > 1): surface `carried_forward[]` issues, note existing code paths/API routes/DB schema.

### Cross-Phase Contract Validation (Phase > 1)

1. Read `docs/design/phases/${PHASE}/specs/data-contracts.md`
2. Compare against Phase N-1 manifest's `api_routes` and `artifacts.code` for changed endpoints/fields
3. Stale contracts (endpoints modified/renamed/removed) → **BLOCKING** — re-run `/plan`
4. Extended endpoints → verify existing fields match Phase N-1 actual code (not just spec). Mismatch → `⚠ STALE CONTRACT`
5. **Schema evolution:** Phase N-1 response shape must be subset of Phase N (additive only):
   - Field removed → **BLOCKING**; Field renamed → **BLOCKING**; Type changed → **BLOCKING**
   - Optional field added → OK; Required request field added → WARNING

### Breaking Change Detection (HARD BLOCK)

- **Field REMOVED** → `⛔ HARD BLOCK: Field '${field}' in Phase ${N-1} response but missing in Phase ${N}`
- **Field RENAMED** → `⛔ HARD BLOCK: '${oldName}' → '${newName}', consumers reference old name`
- **Field TYPE CHANGED** → `⛔ HARD BLOCK: '${field}' ${oldType} → ${newType}`
- **Optional field ADDED** → OK
- **Required request field ADDED** → WARNING

Hard blocks CANNOT be force-gated. Fix contract or provide migration path (deprecated field alias).

```bash
# Quick staleness check
if [ $PHASE -gt 1 ]; then
  PREV_MANIFEST="agent_state/phases/$((PHASE-1))/manifest.json"
  CONTRACTS="docs/design/phases/${PHASE}/specs/data-contracts.md"
  if [ -f "$PREV_MANIFEST" ] && [ -f "$CONTRACTS" ]; then
    python3 -c "
import json, sys
manifest = json.load(open('$PREV_MANIFEST'))
routes = manifest.get('artifacts', {}).get('api_routes', [])
contracts = open('$CONTRACTS').read()
stale = [r for r in routes if r.split()[-1] not in contracts]
if stale:
    print('⚠ STALE CONTRACTS — routes in previous manifest not found in data-contracts.md:')
    for r in stale: print(f'  - {r}')
    sys.exit(1)
print('✅ Data contracts consistent with Phase $((PHASE-1)) manifest')
" || echo "⚠ Contract validation failed — review data-contracts.md before proceeding"
  fi
fi
```

### Schema Evolution Validation (PHASE > 1)

Load ALL previous phases' `data-contracts.md` (not just N-1). For each shared interface:
- Field additions → ALLOWED (INFO)
- Field removals → ⛔ BREAKING: Option A (restore), B (version endpoint), C (confirm + document as `breaking_changes[]`)
- Type changes → ⛔ BREAKING: same routing
- Array↔Object → ⛔ CRITICAL: must version endpoint

Output: `agent_state/phases/${PHASE}/reports/schema_evolution.md`
Manifest: `"breaking_changes": [{"field":"...","action":"removed|type_changed","resolution":"versioned|confirmed|restored"}]`

```bash
if [ $PHASE -gt 1 ]; then
  CURRENT_CONTRACTS="docs/design/phases/${PHASE}/specs/data-contracts.md"
  if [ -f "$CURRENT_CONTRACTS" ]; then
    for PREV_PHASE in $(seq 1 $((PHASE - 1))); do
      PREV_CONTRACTS="docs/design/phases/${PREV_PHASE}/specs/data-contracts.md"
      if [ -f "$PREV_CONTRACTS" ]; then
        python3 -c "
import re, sys
def parse_interfaces(text):
    interfaces = {}
    current = None
    for line in text.split('\n'):
        m = re.match(r'(?:export\s+)?interface\s+(\w+)', line)
        if m:
            current = m.group(1)
            interfaces[current] = {}
            continue
        if current and re.match(r'\s*}', line):
            current = None
            continue
        if current:
            fm = re.match(r'\s+(\w+)\??\s*:\s*(.+);', line)
            if fm:
                interfaces[current][fm.group(1)] = fm.group(2).strip()
    return interfaces
prev = parse_interfaces(open('$PREV_CONTRACTS').read())
curr = parse_interfaces(open('$CURRENT_CONTRACTS').read())
breaking = []
for iface in prev:
    if iface not in curr: continue
    for field, ftype in prev[iface].items():
        if field not in curr[iface]:
            breaking.append(f'⛔ BREAKING: {iface}.{field} REMOVED (was {ftype})')
        elif curr[iface][field] != ftype:
            breaking.append(f'⛔ BREAKING: {iface}.{field} TYPE CHANGED: {ftype} → {curr[iface][field]}')
if breaking:
    print('Schema evolution issues (Phase ${PREV_PHASE} → Phase ${PHASE}):')
    for b in breaking: print(f'  {b}')
    sys.exit(1)
else:
    print('✅ Schema evolution clean: Phase ${PREV_PHASE} → Phase ${PHASE}')
" || echo "⚠ Schema evolution validation failed"
      fi
    done
  fi
fi
```

### Breaking Change Propagation

When confirmed (not restored): identify all consuming phases via manifests' `artifacts.api_routes` → check if their tests pass with new contract → if fail, version endpoint or cross-phase fix. Log in `schema_evolution.md`.

```bash
if [ $PHASE -gt 1 ] && [ -f "agent_state/phases/${PHASE}/reports/schema_evolution.md" ]; then
  BREAKING_COUNT=$(grep -c "⛔ BREAKING" "agent_state/phases/${PHASE}/reports/schema_evolution.md" 2>/dev/null || echo 0)
  if [ "$BREAKING_COUNT" -gt 0 ]; then
    echo "⚠ ${BREAKING_COUNT} breaking change(s) — checking consuming phases..."
    for PREV_PHASE in $(seq 1 $((PHASE - 1))); do
      PREV_MANIFEST="agent_state/phases/${PREV_PHASE}/manifest.json"
      if [ -f "$PREV_MANIFEST" ]; then
        python3 -c "
import json
manifest = json.load(open('$PREV_MANIFEST'))
routes = manifest.get('artifacts', {}).get('api_routes', [])
if routes:
    print(f'  Phase ${PREV_PHASE} consumes {len(routes)} API routes — verify compatibility')
    for r in routes: print(f'    - {r}')
"
      fi
    done
    echo "  → Resolve breaking changes (version endpoint or update consumers) before proceeding."
  fi
fi
```

### Phase Context Staleness Detection

```bash
CONTEXT_FILE="docs/design/phases/${PHASE}/phase_context.md"
BRD_FILE="docs/BRD.md"
if [ -f "$CONTEXT_FILE" ] && [ -f "$BRD_FILE" ]; then
  CONTEXT_MTIME=$(stat -f %m "$CONTEXT_FILE" 2>/dev/null || stat -c %Y "$CONTEXT_FILE")
  BRD_MTIME=$(stat -f %m "$BRD_FILE" 2>/dev/null || stat -c %Y "$BRD_FILE")
  if [ "$BRD_MTIME" -gt "$CONTEXT_MTIME" ]; then
    echo "⚠ BRD modified AFTER phase_context.md — consider re-running /plan --phase=${PHASE}"
  fi
fi
```

BRD diff includes new FR-* IDs not in `phase_context.md` → **BLOCKING** (re-run `/plan`). Editorial BRD changes (no new FR-*) → WARNING only.

### Spec Staleness Warning

```bash
SPEC_DIR="docs/design/phases/${PHASE}/specs"
if [ -d "$SPEC_DIR" ]; then
  NOW=$(date +%s)
  for SPEC in "$SPEC_DIR"/*.md; do
    [ -f "$SPEC" ] || continue
    SPEC_MTIME=$(stat -f %m "$SPEC" 2>/dev/null || stat -c %Y "$SPEC")
    DAYS_OLD=$(( (NOW - SPEC_MTIME) / 86400 ))
    if [ "$DAYS_OLD" -gt 60 ]; then
      echo "⛔ Spec $(basename $SPEC) is ${DAYS_OLD} days old — strongly recommend /plan --refresh"
    elif [ "$DAYS_OLD" -gt 30 ]; then
      echo "⚠ Spec $(basename $SPEC) is ${DAYS_OLD} days old — consider re-running /plan"
    fi
  done
fi
```

Not BLOCKING — user decides. Surface all stale specs together, then continue.

### Start infrastructure
```bash
docker compose up -d  # from IMPLEMENTATION_GUIDELINES Section 5
# Wait for DB readiness (up to 60s)
```

### Token/Cost Estimation

Rough order-of-magnitude for budgeting. Count components: `NUM_COMPONENTS = spec file count` (exclude data-contracts.md, phase_context.md, INDEX.md). `HAS_UI = true if wireframe specs exist`. `PREV_PHASES = PHASE - 1`.

**Per-agent estimates (input + output tokens):**
| Agent | Model | Tokens | When |
|-------|-------|--------|------|
| backend_audit_agent | sonnet | ~15K | Always |
| ui_audit_agent | sonnet | ~15K | If HAS_UI |
| database_agent | opus | ~25K x NUM_DB_TABLES | Always |
| migration_agent | opus | ~20K | Always |
| backend_developer | opus | ~40K x NUM_COMPONENTS | Always |
| api_developer | opus | ~35K x NUM_COMPONENTS | Always |
| ui_developer | opus | ~45K x NUM_COMPONENTS | If HAS_UI |
| unit_test_agent | opus | ~30K x NUM_COMPONENTS | Always |
| integration_test_agent | opus | ~25K x NUM_COMPONENTS | Always |
| e2e_orchestrator | sonnet | ~20K | If e2e unlocked |
| acceptance_test_agent | opus | ~30K | Always |
| code_reviewer_I | sonnet | ~15K | Always |
| code_reviewer_II | opus | ~25K | Always |
| security_reviewer | opus | ~30K | Always |
| tenant_isolation_verifier | opus | ~20K | Always |
| code_quality_verifier | sonnet | ~10K | Always |
| spec_impl_reconciler | opus | ~25K | Always |
| spec_test_reconciler | sonnet | ~15K | Always |
| code_optimizer | sonnet | ~20K | Always |
| ui_code_optimizer | sonnet | ~20K | If HAS_UI |
| documentation_agent | sonnet | ~15K | Always |

Example: 3-component backend-only → ~655K tokens. 5-component full-stack → ~1.2M tokens.

If TOTAL_TOKENS > 1,500,000: `"Consider splitting into smaller phases or running /plan --split."`

```bash
echo "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"estimate\",\"phase\":${PHASE},\"estimated_tokens\":${TOTAL_TOKENS},\"components\":${NUM_COMPONENTS},\"has_ui\":${HAS_UI}}" >> agent_state/phases/${PHASE}/execution.jsonl
```

### Decision Log Protocol

All agents append to `agent_state/phases/${PHASE}/decision-log.md`:
```markdown
## Decision: <short title>
- **Agent:** <agent name>
- **Context:** <what prompted this>
- **Options considered:** <alternatives>
- **Decision:** <chosen>
- **Rationale:** <why>
- **Impact:** <downstream effects>
```
Log when: choosing between alternatives, deviating from spec, making assumptions, choosing unprescribed libraries/patterns.

### Spec Amendment Protocol

When intentionally deviating from spec:
1. Log in decision-log.md with original spec behavior, actual behavior, rationale, downstream impact
2. Append to spec: `## Implementation Notes (auto-generated)` with deviation summary
3. `spec_impl_reconciler` treats documented deviations as ACKNOWLEDGED (not MISSING)

### Mid-Execution Escalation Protocol

**LOW impact** (reversible, single-option): continue with default → `{"type":"escalation","impact":"LOW","recommendation":"A","continueWithDefault":true}`

**MEDIUM/HIGH impact** (architecture, security, data model): escalate to Debate Team via `agent_state/debates/<step>-<topic>.json`:
```json
{
  "type": "debate_request",
  "from_agent": "<agent>", "from_step": "<step>",
  "decision": "<what>",
  "options": [{"id":"A","label":"...","initial_reasoning":"..."}, {"id":"B","label":"...","initial_reasoning":"..."}],
  "context": "<BRD refs, constraints>",
  "impact": "HIGH|MEDIUM", "domain": "architecture|security|data_model|feature",
  "blocking": true
}
```

Debate flow: Researchers (parallel) → Advocates (parallel, HIGH only) → Arbitrator (scored verdict) → `agent_state/debates/<topic>-verdict.json`.

### Escalation Circuit Breaker

- **Max per step:** 3 — excess → `agent_state/debates/unresolved.json` with defaults
- **`--auto` mode:** continue with defaults, flag as `"⚠ AUTO-RESOLVED — may need review"` in decision log + manifest `known_issues[]`
- **Security exception:** NEVER auto-resolve. Use hardened default (more restrictive). Includes: auth, tokens, IDOR, encryption, PII, CORS/CSRF, rate limiting. No clear hardened default → EXIT auto mode.
- **Max per phase:** 10 — exceeded → EXIT auto mode entirely
- **Max depth:** 2 — second-level auto-resolves with default (except security → hardened). Third-level NEVER allowed.

```json
// agent_state/debates/unresolved.json
{
  "phase": N, "unresolved_count": 4,
  "decisions": [{"topic":"cache_strategy","from_agent":"backend_developer","auto_resolved_with":"A","confidence":"LOW","reason":"escalation_limit_exceeded","needs_review":true}]
}
```

### Universal Agent Return Protocol

Every agent returns ONLY:
```
✅ <agent-name> — <status: complete | blocked | partial>
   Wrote: <output file path>
   Done:  <one line>
   Issues: none | <N blocking / N warning>
```
If blocked: `Blocker: <one-line> → see <file> for details`
Parent reads output file for details — never asks agent to reproduce content.

### Analysis Paralysis Guard

If agent makes **5+ consecutive read-only calls** without any write → STOP exploring, state the blocker in 1 line, then write code or return with `status: blocked`. Exception: audit agents are read-only by design.

---

### Placeholder Convention
- `${PHASE}` / `$((PHASE-1))` — bash variables (numeric)
- `{{PHASE}}` / `{{PHASE-1}}` — in agent `.md` files, substitute at runtime

### Agent Context Protocol — Minimal, targeted reads

**Primary context (load these, nothing more):**
| File | Size | Contains |
|------|------|----------|
| `docs/design/phases/${PHASE}/phase_context.md` | ~6-8K | Full tech stack, conventions, security NFRs, acceptance criteria, existing state, gate checklist |
| `docs/design/phases/${PHASE}/specs/<own-component>.md` | ~5-10K | Interface contracts, data model, edge cases, test requirements |
| `docs/design/phases/${PHASE}/specs/data-contracts.md` | ~3-5K | Typed TypeScript interfaces, ARRAY vs OBJECT explicit |
| `agent_state/phases/$((PHASE-1))/manifest.json` | ~3-5K | Existing routes, schema, services |

`phase_context.md` is a structured 6-8K extract replacing full BRD + IMPL_GUIDELINES.

**Escalation only:** Specific FR-* from BRD, infra commands from IMPL_GUIDELINES §Local Dev, adjacent component spec.
**Never load:** Entire BRD (except: brd_spec_reconciler, requirements_brd_reconciler, acceptance_test_agent), entire IMPL_GUIDELINES (except: agent_factory, architecture_orchestrator), all spec files at once.

---

## Step 0.5 — Implementation Readiness Gate (HARD GATE)

```bash
SPECS_DIR="docs/design/phases/${PHASE}/specs"
SPEC_COUNT=$(ls ${SPECS_DIR}/*.md 2>/dev/null | wc -l)
[ "$SPEC_COUNT" -eq 0 ] && echo "⛔ BLOCKED: No specs at ${SPECS_DIR}/. Run /plan --phase=${PHASE}." && exit 1

CONTEXT_FILE="docs/design/phases/${PHASE}/phase_context.md"
[ ! -f "$CONTEXT_FILE" ] || [ $(wc -l < "$CONTEXT_FILE") -lt 20 ] && echo "⛔ BLOCKED: phase_context.md missing/short. Run /plan." && exit 1

VERIFY_FILE="docs/design/phases/${PHASE}/VERIFICATION_REPORT.md"
[ ! -f "$VERIFY_FILE" ] && echo "⛔ BLOCKED: No verification report. Run /plan." && exit 1

RECON_FILE="agent_state/reconciliation/phase-${PHASE}/brd_vs_specs.md"
[ -f "$RECON_FILE" ] && grep -q "MISSING" "$RECON_FILE" && echo "⚠ BRD↔Spec reconciliation has MISSING coverage."

CONTRACTS_FILE="docs/design/phases/${PHASE}/specs/data-contracts.md"
[ ! -f "$CONTRACTS_FILE" ] && echo "⚠ data-contracts.md missing. API↔UI binding errors likely."
```

Any check fails → STOP, recommend `/plan --phase=${PHASE}`. Incomplete specs produce incomplete implementations.

---

## Step 1 — Audit

**Agents (parallel):** `backend_audit_agent` (always) + `ui_audit_agent` (if `frontend.enabled = true`)

Outputs: `agent_state/phases/${PHASE}/audit_report.md` / `audit_report_ui.md`

```markdown
# Phase N Audit Report
## Carried Forward Issues (from Phase N-1)
## Gap Analysis
| Component | Expected (from spec) | Found (in codebase) | Gap |
## Missing Implementations
## Broken/Incomplete Items
## Recommended Implementation Order
```

If `--audit_only`: stop here.

---

## Step 2 — Implementation (Wave-based Parallel Execution)

Agents from `.claude/agents/generated/` per component type. Waves run in parallel; waves are sequential.

### Wave Structure

**Wave 1** (parallel): `database_agent` → schema + docs/design/database.md; `migration_agent` → migration files (up + down)

**Wave 1.5** (sequential gate): Migration Validation — dry-run against test DB:
1. Files parse without syntax errors
2. UP applies cleanly to empty DB
3. DOWN reverses UP cleanly
4. UP re-applies after DOWN (idempotency)
Fail → block Wave 2, route to migration_agent (max 1 retry)

### Migration Failure Auto-Recovery
UP fails → immediately run DOWN to restore schema → log error → route back for fix (max 1 retry).
DOWN rollback also fails → **STOP** immediately (unknown schema state) → write `migration_failure.json` → do NOT proceed to Wave 2.

**Migration Safety Gate (BLOCKING):** Zero CRITICAL findings in migration_safety.md, all DOWN migrations exist and non-empty, irreversible migrations acknowledged.

**Wave 2a** (sequential): `backend_developer` → domain models, services, repositories. Writes manifest with service method return types.

**Wave 2a.5** — Compile/Typecheck Gate (BLOCKING):
| Language | Command | Pass |
|----------|---------|------|
| Go | `go build ./...` | Exit 0 |
| TypeScript | `tsc --noEmit` | Exit 0 |
| Python | `python -m py_compile <files>` + `mypy` (if configured) | Exit 0 |
| Java | `mvn compile -q` or `gradle compileJava` | Exit 0 |
| Rust | `cargo check` | Exit 0 |

Fail → route to `backend_developer` with first 50 lines of errors (max 2 attempts) → still failing → STOP. Do NOT proceed to Wave 2b on broken code.

```bash
echo "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"compile_check\",\"step\":\"2a.5\",\"status\":\"passed|failed\",\"language\":\"<lang>\",\"attempt\":${ATTEMPT:-1}}" >> agent_state/phases/${PHASE}/execution.jsonl
```

### Agent Handoff Protocol (Wave 2a → 2b)

Atomic write + verified ready signal:
```bash
MANIFEST_DIR="agent_state/phases/${PHASE}/backend_developer"
python3 -c "import json,sys; json.load(sys.stdin)" < "${MANIFEST_DIR}/manifest.json.tmp" && \
  mv "${MANIFEST_DIR}/manifest.json.tmp" "${MANIFEST_DIR}/manifest.json" && \
  touch "agent_state/phases/${PHASE}/.backend_developer_VERIFIED" || \
  { echo "⛔ backend_developer manifest invalid — blocking handoff"; exit 1; }
```

Before api_developer starts: check `.backend_developer_VERIFIED` exists, validate manifest JSON is readable, then read service method return types. This pattern applies to ALL wave transitions.

**Wave 2b** (depends on 2a + compile gate): `api_developer` → handlers, routes, middleware, DTOs, api-contracts.md. Reads data-contracts.md as MANDATORY source of truth. api-contracts.md derives from data-contracts.md — shape mismatch → BLOCKER.

**Wave 2b.5** — API Layer Compile Check (BLOCKING): Same compile command as 2a.5. Fail → route to `api_developer` (max 2 attempts) → STOP. Do NOT proceed to Wave 2.5/2.75/3.

```bash
echo "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"compile_check\",\"step\":\"2b.5\",\"status\":\"passed|failed\",\"language\":\"<lang>\",\"attempt\":${ATTEMPT:-1}}" >> agent_state/phases/${PHASE}/execution.jsonl
```

**Wave 2.5** (sequential gate, UI only): Contract Validation — verify api-contracts.md exists, all endpoints documented, shapes unambiguous.

**Wave 2.75** (SMOKE TEST): `docker compose up -d && curl -sf http://localhost:PORT/health`. Fail → route to api_developer (max 1 retry). Catches catastrophic failures before expensive UI + test agents.

**Wave 3** (parallel, UI only, blocked until 2.75 passes): `ui_developer` → screens from UI specs + api-contracts.md + data-contracts.md

**Wave 3.5** — Frontend Build Check (BLOCKING, UI only):
| Framework | Command |
|-----------|---------|
| React/CRA | `npm run build` |
| Next.js | `npx next build` |
| Vue/Nuxt | `npm run build` |
| Vite | `npx vite build` |
| Angular | `npx ng build` |

Additional: `tsc --noEmit --strict` (if strict mode), `npx eslint src/ --max-warnings 0`. Fail → route to `ui_developer` (max 2 attempts) → STOP.

```bash
echo "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"frontend_build_check\",\"step\":\"3.5\",\"status\":\"passed|failed\",\"framework\":\"<framework>\",\"attempt\":${ATTEMPT:-1}}" >> agent_state/phases/${PHASE}/execution.jsonl
```

**Wave 4** (parallel): `unit_test_agent` + `integration_test_agent` — read specs AND implementation code.

Each agent: reads Step 0 context + spec files + skill pack → implements in-scope work → writes agent manifest to `agent_state/phases/${PHASE}/<agent>/manifest.json`.

---

## Step 2.5 — API Contract Validation (UI phases only)

Runs after Wave 2 completes, blocks Wave 3.

**Checks:**
1. `api-contracts.md` exists and non-empty
2. All routes in api_developer manifest have matching entry
3. Shape unambiguity: explicit `[]` or `{}`, empty state documented, all fields typed
4. Data contract compliance: field names match data-contracts.md exactly, array/object match. Mismatch → route to api_developer (max 1 retry)
5. Wireframe cross-reference: endpoints exist, fields exist in response shape, list/single matches component expectation

Pass → proceed to Wave 3. Fail → surface specific mismatches, route to api_developer.

---

## Step 3 — Tests

### Step 3a — Unit Tests
**Agent:** `unit_test_agent`. On failure: diagnose → fix implementation (not tests) → rerun. **Max 3 attempts** → surface with reproduction steps.

### Test Attempt Tracking
Track ALL retries: log `"⚠ Test [name] required [N] attempts"`, add to manifest `"flaky_tests"`, carry forward to next phase audit.
```json
"test_results": {"unit": {"status":"passed","total":24,"passed":24,"failed":0,"flaky_tests":["TestCreateUser (attempt 2)","TestListResources (attempt 3)"],"report":"agent_state/phases/N/reports/unit_tests.md"}}
```

### Flaky Test Quarantine
Test in `flaky_tests[]` across 2+ consecutive phases → quarantine:
- Go: `t.Skip("QUARANTINED: flaky across phases N-1, N")`
- Python: `@pytest.mark.skip(reason="QUARANTINED: flaky")`
- TypeScript: `test.skip('QUARANTINED: flaky')`
- Java: `@Disabled("QUARANTINED: flaky")` / Rust: `#[ignore]`

Track in manifest `"quarantined_tests"`. If count > 5 → escalate. Auto-unquarantine after 3 consecutive passing phases.

### Step 3a.5 — Cross-Phase Regression (Smart, if PHASE > 1)

**Artifact Overlap Detection Algorithm:**
1. Extract current phase `artifacts.api_routes`, `artifacts.schemas`, `artifacts.code`
2. For each previous phase P: compute schema/route/code overlap
3. Overlap detected → phase is "affected" → re-run P's unit + integration tests (NOT e2e)
4. No overlap → SKIP (log reason)
5. Failure → BLOCKER → route to implementation agent (max 2 attempts) → escalate if unfixable
6. Output in manifest:
```json
"cross_phase_regression": {
  "phases_checked": [1,2], "phases_skipped": [3],
  "overlap_details": {"phase_1":{"schemas":["users"],"routes":["/api/v1/users"]}},
  "results": {"phase_1":{"unit":"passed","integration":"passed"}}
}
```
Report: `agent_state/phases/${PHASE}/reports/regression_check.md`

### Step 3b — Integration Tests
**Agent:** `integration_test_agent`. Requires infra running. Tests service↔DB, service↔cache. Fix → retry → max 3 attempts.

### Step 3c — E2E Tests (conditional)
**Trigger:** `PHASE_PLAN.md` has non-empty `e2e_workflows_unlocked`. **Agent:** `e2e_orchestrator` + `ui_test_agent` (if UI). Fix → retry → max 2 attempts.

All three tiers must pass before reconciliation.

### Step 3c.5 — Post-Implementation Re-Audit (CLOSED LOOP)

After all tests pass: re-read Step 1 audit report, verify each gap under "Missing Implementations" and "Broken/Incomplete Items" is resolved. Check carried-forward issues. Output: `reports/re_audit.md`. Unresolved audit gaps → warnings in gate. Carried-forward items 2+ phases old → **BLOCKING**.

---

## Step 3d + 3e — Reconciliation (SEQUENTIAL)

3d runs first → 3e reads 3d output. A behavior can't be "untested" if it's not implemented yet.

### 3d: Specs ↔ Implementation (`spec_impl_reconciler`)
4-level verification (Existence → Substantiveness → Wiring → Data Flow), forward + reverse.
Output: `agent_state/reconciliation/phase-N/specs_vs_impl.md`
Missing implementations = **BLOCKER**. Unspecced implementations = LOGGED with classification: `technical_necessity`, `scope_creep`, `test_helper`. `scope_creep` → recommend: add to BRD or remove. Unresolved → `carried_forward[]`.

### 3e: Specs ↔ Tests (`spec_test_reconciler`)
Forward + reverse validation. Output: `agent_state/reconciliation/phase-N/specs_vs_tests.md`
HIGH-priority untested = blocker. MEDIUM/LOW = logged.

---

## Step 3f — Code Optimization (MANDATORY)

Runs every phase, after tests pass + reconciliation complete, before review. Produces report even if zero changes.

### Scope Lock (CRITICAL)
ONLY files created/modified in THIS phase. Never modify previous-phase code.
```bash
SCOPE_FILES=$(git diff --name-only agent_state/phases/$((PHASE-1))/gate.passed..HEAD 2>/dev/null || git diff --name-only HEAD~50..HEAD)
```

### Pre-optimization snapshot
```bash
git tag "phase-${PHASE}-pre-optimize" HEAD
```

### Execution (parallel)
- `code_optimizer` → backend/API (src/domain/, src/services/, src/repositories/, src/api/, src/errors/)
- `ui_code_optimizer` → UI (src/ui/, src/components/, src/hooks/, src/pages/, src/styles/) — if frontend.enabled

Both: Pass 1 (dead code removal) → Pass 2 (code optimization). Each change committed individually.

Outputs: `reports/code_optimization.md`, `reports/ui_code_optimization.md`

---

## Step 3g — Post-Optimization Test Re-run (CONDITIONAL)

Skip if zero changes. Otherwise re-run ALL test tiers (unit, integration, e2e).

### On failure
1. Identify causing optimization via git log since `phase-${PHASE}-pre-optimize`
2. Diagnose + fix (max 2 attempts)
3. If fix fails → `git revert <commit> --no-edit`
4. Max 3 revert cycles → `git reset --hard phase-${PHASE}-pre-optimize` + log
5. Optimization failure is NOT a pipeline blocker but IS logged in gate

Gate checks post-optimization status: CLEAN (all kept), PARTIAL (some reverted), REVERTED (all rolled back) → all acceptable. Tests still failing → **BLOCKER**.

---

## Step 4 — Code Review + Acceptance Tests (PARALLEL TRACKS)

Both tracks read same code, neither modifies it. Both must pass for gate.

### Track A: Code Review (Three-Stage Pipeline)

### Stage 4a — Spec Compliance Review (FIRST)
Independently verify implementation matches specs. Explicit distrust of manifests — read actual code.

**Checks per spec:** interface contracts match, behaviors implemented (not stubbed), edge cases handled, error matrix covered, API↔wireframe bindings match.

**Mismatch → closed loop:** route to implementation agent (max 2 rounds) → re-check changed files only → persist after 2 rounds → `spec_deviation` → gate blocker.

Output: `reports/spec_compliance_review.md`

### Stage 4b — All remaining reviews (PARALLEL after 4a)
```
├─ code_reviewer_I     → style + idioms (language skill pack)
├─ code_reviewer_II    → architecture compliance (IMPLEMENTATION_GUIDELINES)
├─ security_reviewer   → OWASP + adversarial + dynamic checks (SQL injection, auth bypass, CORS, rate limiting)
└─ dependency_scanner  → CVE + outdated packages
```

Max 2 rounds per reviewer. Unresolved → `known_issues` in manifest.

**Blocking rules:** code_reviewer_I: BLOCKING issues; code_reviewer_II: VIOLATION findings; security_reviewer: HIGH severity (static + dynamic); dependency_scanner: CRITICAL/HIGH with available fixes (auto-apply non-breaking).

Reports: `spec_compliance_review.md`, `code_review_I.md`, `code_review_II.md`, `security_review.md`, `dependency_scan.md`, `sast_scan.md`

### Stage 4c — SAST (parallel with review)
```bash
# Language-specific: govulncheck, bandit, semgrep, spotbugs, cargo audit
$SAST_CMD > agent_state/phases/${PHASE}/reports/sast_scan.md
```
CRITICAL/HIGH → BLOCKING; MEDIUM → WARNING; LOW → INFO. No SAST tool configured → skip with warning.

### Track B: Acceptance Tests (PARALLEL with Track A)

**Agent:** `acceptance_test_agent` — validates against BRD FR-* at use case/persona level.

**Data seeding:** `requirements/test-data/phase-${PHASE}.yaml` if present, else agent generates from BRD personas.

**Execution:** Each in-scope FR-* executed as declared persona. Every BRD persona exercised by at least 1 use case. Results: PASS / PARTIAL / FAIL per use case.

**Contract shape assertions:** Every API call verifies response matches data-contracts.md (field names, types, array vs object, empty state). Mismatches logged as `CONTRACT_VIOLATION`.

**Iteration:** Failure → implementation fix → re-test → max 2 rounds → unresolved → **gate blocked**.

Outputs: `reports/acceptance_report.md`, `test-data/generated-seed.yaml`, `test-data/seed-cleanup.md`

---

## Step 6 — Phase Gate

Read each gate item's source file, evaluate pass/fail. If NOT met → record blocker, do NOT write `gate.passed`.

```
Gate Item                    Source File                                          Pass Condition
─────────────────────────────────────────────────────────────────────────────────────────────────
Spec compliance              reports/spec_compliance_review.md                    COMPLIANT — no missing implementations
Unit tests                   reports/unit_tests.md                                No FAILED tests
Integration tests            reports/integration_tests.md                         No FAILED tests
E2E tests (if unlocked)      agent_state/e2e/results.md                          No FAILED workflows
Reconciliation C (spec↔impl) reconciliation/phase-N/specs_vs_impl.md             No MISSING impls, unspecced acknowledged
Reconciliation D (spec↔tests)reconciliation/phase-N/specs_vs_tests.md            No HIGH-priority untested
Code optimization            reports/code_optimization.md                         Post-opt tests PASS (CLEAN/PARTIAL ok)
UI code optimization         reports/ui_code_optimization.md                      Post-opt tests PASS (if frontend; else skip)
Code review I                reports/code_review_I.md                             No BLOCKING issues
Code review II               reports/code_review_II.md                            No architecture violations
Security review              reports/security_review.md                           No HIGH severity
SAST scan                    reports/sast_scan.md                                 No CRITICAL/HIGH
Acceptance tests             reports/acceptance_report.md                         All in-scope use cases PASS
Cross-phase regression       manifest.json → cross_phase_regression               All affected phases PASSED (skip if PHASE==1)
Migration safety             reports/migration_safety.md                          Zero CRITICAL, DOWN coverage ≥ 90%
```

E2E gate active only when `PHASE_PLAN.md` has non-empty `e2e_workflows_unlocked`.

### Bug Severity Classification

| Severity | Definition | Gate Impact | Carry-Forward Limit |
|----------|-----------|-------------|---------------------|
| `critical` | Data loss, security breach, feature broken | BLOCKS | 0 phases |
| `high` | Major feature broken, UX degradation | BLOCKS | 1 phase max |
| `medium` | Minor feature broken, workaround exists | No block | 3 phases max |
| `low` | Cosmetic | No block | No limit |

Default if unset: `medium`. Carry-forward enforcement: `critical` in carried_forward → IMMEDIATE BLOCK; `high` >1 phase → auto-escalates to `critical`; `medium` >3 phases → auto-escalates to `high`.

### Gate failure
```bash
cat > agent_state/phases/${PHASE}/gate.failed <<EOF
{"phase":${PHASE},"failed_at":"$(date -u +%Y-%m-%dT%H:%M:%SZ)","blockers":[/* failing items */],"attempt":${ATTEMPT:-1}}
EOF
```

**Gate state machine:** `gate.passed` → completed; `gate.failed` only → unresolved blockers; neither → not attempted; both → `gate.passed` wins.

When resolved: write `gate.passed`, rename `gate.failed` → `gate.failed.resolved`.

### Gate Failure Recovery
1. Identify blocker from specific report file
2. Fix root cause — re-run failing agent only
3. Re-evaluate gate — re-read all reports
4. Gate passes → write `gate.passed` + manifest

Do NOT delete `agent_state/phases/${PHASE}/`, re-run entire pipeline, or modify tests to force pass.

### --force_gate Override
1. Write `gate.passed` with `⚠ FORCED GATE` header listing overridden items
2. Write `gate.forced`:
```json
{"phase":N,"forced_at":"<ISO>","blockers":[{"gate_item":"...","details":"...","severity":"gate_override"}],"user_rationale":"<reason>"}
```
3. Add to manifest `known_issues[]` with `"severity": "gate_override"`

### Forced Gate Carry-Forward Enforcement
Next phase Step 0: check `gate.forced` → surface ALL blockers prominently. Phase N+1 audit lists each as CRITICAL carried-forward. Phase N+1 gate adds extra check: all forced blockers resolved or re-deferred. **2 consecutive forced gates → PERMANENTLY BLOCKING** (cannot force again; fix or remove from scope).

### Manifest Write Protocol (Atomic)
```bash
python3 -c "import json,sys; json.load(sys.stdin)" < agent_state/phases/${PHASE}/manifest.json.tmp && \
  mv agent_state/phases/${PHASE}/manifest.json.tmp agent_state/phases/${PHASE}/manifest.json || \
  { echo "⛔ CORRUPT manifest — aborting"; exit 1; }
```

Also validate required fields:
```bash
python3 -c "
import json, sys
manifest = json.load(sys.stdin)
required = ['phase','goal','started_at','brd_requirements_met','test_results','artifacts','known_issues','carried_forward']
missing = [f for f in required if f not in manifest]
if missing:
    print(f'⛔ MANIFEST MISSING FIELDS: {missing}')
    sys.exit(1)
print('✅ Manifest schema valid')
" < agent_state/phases/${PHASE}/manifest.json.tmp
```

### Phase Completion Tagging
```bash
git tag "phase-${PHASE}-complete" -m "Phase ${PHASE} gate passed: $(date)"
```

### Write gate files + manifest
```bash
mkdir -p agent_state/phases/${PHASE}
touch agent_state/phases/${PHASE}/gate.passed
```

Manifest schema (`agent_state/phases/${PHASE}/manifest.json`):
```json
{
  "phase": N, "goal": "<from PHASE_PLAN.md>",
  "completed_at": "<ISO 8601>",
  "brd_requirements_met": ["FR-001", "FR-002", "NFR-PERF-01"],
  "acceptance_tests": {"use_cases_total":5,"use_cases_passed":5,"personas_exercised":["Admin User","End User"],"seed_data":"agent_state/phases/N/test-data/generated-seed.yaml"},
  "artifacts": {"specs":["..."],"code":["..."],"migrations":["..."],"tests":["..."],"api_routes":["..."]},
  "test_results": {
    "unit": {"status":"passed","total":24,"passed":24,"failed":0,"report":"agent_state/phases/N/reports/unit_tests.md"},
    "integration": {"status":"passed","total":8,"passed":8,"failed":0,"report":"..."},
    "e2e": {"status":"passed|not_run","total":3,"passed":3,"failed":0,"report":"..."}
  },
  "optimization": {
    "backend": {"status":"CLEAN|PARTIAL|REVERTED","dead_code_removed":0,"optimizations_applied":0,"lines_reduced":0,"report":"..."},
    "ui": {"status":"CLEAN|PARTIAL|REVERTED|not_run","dead_code_removed":0,"optimizations_applied":0,"report":"..."},
    "post_optimization_tests": "PASS|PASS_WITH_REVERTS|not_run"
  },
  "known_issues": [], "carried_forward": [],
  "carried_forward_policy": "Items in carried_forward[] MUST be addressed within 1 phase. If an item survives 2 consecutive phases: it becomes BLOCKING — fix or remove from scope via BRD change request. Forced gate overrides count toward this limit."
}
```

---

## Step 6b — Documentation (parallel with gate writes)

**Agent:** `documentation_agent` — API docs (OpenAPI/Swagger), README updates, code review annotations. Output: `reports/documentation_update.md`. Does NOT block gate.

---

## Step 7 — Report

```
✅ Phase N complete
  Implemented: Backend: N services, N repos, N routes | UI: N screens | DB: N migrations
  Tests: Unit X/X | Integration X/X | E2E X/X (or not run)
  Reconciliation: Spec↔Impl PASS | Spec↔Tests PASS
  Optimization: Dead code N items (-X lines) | Optimizations N | Flagged N
  Acceptance: X/X passed (FR-001, FR-002) | Personas: [Admin, End User]
  Reviews: Style PASS | Architecture PASS | Security PASS
  Gate: agent_state/phases/N/gate.passed ✅
  Manifest: agent_state/phases/N/manifest.json ✅
  ▶ Next: /plan --phase=N+1
```

### Execution Summary
Read `execution.jsonl`, render agent timings + status, identify slowest agent, total run/failed/retried counts.
```bash
echo "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"pipeline_complete\",\"phase\":${PHASE},\"status\":\"<gate_passed|gate_failed|gate_forced>\",\"total_duration_s\":<N>,\"agents_run\":<N>,\"agents_failed\":<N>}" >> agent_state/phases/${PHASE}/execution.jsonl
```

---

## Step 7b — Phase Post-Mortem (ALWAYS runs, even on forced gates)

Informational only, never blocks gate. Output: `reports/postmortem.md`

### 1. Failure Pattern Analysis
Read all reports: count BLOCKING/CRITICAL/HIGH findings, group by category (security, architecture, style, testing, contract), identify systemic patterns across components.

### 2. Retry Analysis
```bash
AGENTS_RUN=$(grep '"status":"completed"' agent_state/phases/${PHASE}/execution.jsonl | wc -l)
AGENTS_RETRIED=$(grep '"status":"failed"' agent_state/phases/${PHASE}/execution.jsonl | jq -r '.agent' 2>/dev/null | sort -u | wc -l)
if [ "$AGENTS_RUN" -gt 0 ]; then
  RETRY_RATE=$(( AGENTS_RETRIED * 100 / AGENTS_RUN ))
  echo "Retry rate: ${RETRY_RATE}%"
  [ "$RETRY_RATE" -gt 30 ] && echo "⚠ High retry rate — improve specs or skill packs"
fi
```

### 3. Time Distribution
From `execution.jsonl`: % in implementation vs testing vs review. Ideal: ~40/30/20/10. Review > 40% → specs underspecified. Testing > 50% → implementation quality issue.

```bash
python3 -c "
import json, sys
steps = {'implement': 0, 'test': 0, 'review': 0, 'other': 0}
step_map = {
    'audit': 'other', 'orient': 'other', 'gate': 'other', 'documentation': 'other',
    'implement': 'implement', 'database': 'implement', 'migration': 'implement',
    'backend_developer': 'implement', 'api_developer': 'implement', 'ui_developer': 'implement',
    'unit_test': 'test', 'integration_test': 'test', 'e2e': 'test', 'acceptance': 'test',
    'reconcil': 'test', 'optimiz': 'test',
    'review': 'review', 'security': 'review', 'tenant': 'review', 'quality': 'review'
}
for line in open('agent_state/phases/${PHASE}/execution.jsonl'):
    try:
        entry = json.loads(line.strip())
        if 'duration_s' in entry:
            agent = entry.get('agent', entry.get('step', 'other')).lower()
            category = 'other'
            for key, cat in step_map.items():
                if key in agent: category = cat; break
            steps[category] += entry['duration_s']
    except: pass
total = sum(steps.values()) or 1
for cat, secs in steps.items():
    print(f'  {cat}: {int(secs*100/total)}% ({secs:.0f}s)')
if steps['review']*100/total > 40: print('⚠ Review > 40% — specs may be underspecified')
if steps['test']*100/total > 50: print('⚠ Test > 50% — implementation quality issue')
" 2>/dev/null || echo "  (time distribution unavailable)"
```

### 4. Carried-Forward Trend
```bash
python3 -c "
import json, os
trend = []
phase = ${PHASE}
for p in range(1, phase + 1):
    path = f'agent_state/phases/{p}/manifest.json'
    if os.path.exists(path):
        m = json.load(open(path))
        cf, ki = len(m.get('carried_forward',[])), len(m.get('known_issues',[]))
        trend.append({'phase':p,'total':cf+ki})
        print(f'  Phase {p}: {cf+ki} issues ({cf} carried, {ki} known)')
if len(trend) >= 2:
    print('  Trend:', 'DEGRADING ⚠' if trend[-1]['total']>trend[-2]['total'] else 'IMPROVING' if trend[-1]['total']<trend[-2]['total'] else 'STABLE')
" 2>/dev/null || echo "  (trend unavailable)"
```

### 5. Gate Health
```bash
GATE_FORCED=$(ls agent_state/phases/${PHASE}/gate.forced 2>/dev/null)
GATE_FAILED=$(ls agent_state/phases/${PHASE}/gate.failed* 2>/dev/null | wc -l | tr -d ' ')
[ -n "$GATE_FORCED" ] && echo "  Gate: FORCED" || { [ "$GATE_FAILED" -gt 0 ] && echo "  Gate: PASSED on attempt $((GATE_FAILED+1))" || echo "  Gate: PASSED on first attempt"; }
```

### Manifest Addition
```json
"postmortem": {"retry_rate_pct":N,"systemic_patterns":N,"carried_forward_trend":"stable|improving|degrading","recommendations":["..."]}
```

```bash
echo "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"postmortem_complete\",\"phase\":${PHASE},\"retry_rate_pct\":${RETRY_RATE:-0},\"systemic_patterns\":${PATTERN_COUNT:-0},\"carried_forward_trend\":\"${CF_TREND:-baseline}\"}" >> agent_state/phases/${PHASE}/execution.jsonl
```
