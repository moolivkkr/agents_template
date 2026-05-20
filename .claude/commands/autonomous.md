---
command: autonomous
description: "Run the full SDLC pipeline end-to-end with minimal human interaction. Auto-researches decisions, one human checkpoint before implementation, then fully autonomous develop + gate."
arguments:
  - name: confirm_each_phase
    required: false
    default: false
    description: "Pause for human review before EACH phase's /develop (default: only before Phase 1)"
  - name: resume
    required: false
    default: false
    description: "Resume from last checkpoint instead of starting fresh"
  - name: skip_init
    required: false
    default: false
    description: "Skip /init (use existing BRD + IMPL_GUIDELINES)"
  - name: max_phases
    required: false
    description: "Limit to N phases (default: all phases from BRD)"
---

# /autonomous — Full SDLC Pipeline (Minimal Human Interaction)

Runs `/init` → `/plan` → `/develop` for all phases with auto-research for decisions and ONE human checkpoint before implementation begins.

```
Phase 0:  Environment pre-flight
Phase 1:  /init --auto (research all decisions)
Phase 2:  /plan --auto --phase=1
Phase 3:  🛑 HUMAN CHECKPOINT (review all decisions)
Phase 4:  /develop --auto --phase=1
Phase 5:  Repeat plan→develop for remaining phases
Phase 6:  /accept --auto (global acceptance)
Phase 7:  Final report
```

---

## Step 0 — Environment Pre-Flight

Verify the development environment is ready BEFORE spending tokens on agents.

```bash
echo "🔍 Environment pre-flight check..."

# 1. Docker running
docker info > /dev/null 2>&1 || { echo "⛔ Docker not running"; exit 1; }

# 2. Required tools available (read from IMPLEMENTATION_GUIDELINES if exists)
for cmd in git node npm; do
  command -v $cmd > /dev/null 2>&1 || echo "⚠ $cmd not found in PATH"
done

# 3. Ports not occupied (common dev ports)
for port in 3000 5432 8080; do
  lsof -i :$port > /dev/null 2>&1 && echo "⚠ Port $port already in use"
done

# 4. requirements/ directory exists and is non-empty
if [ ! -d "requirements/" ] || [ -z "$(ls requirements/)" ]; then
  echo "⛔ requirements/ directory empty or missing. Add requirement documents first."
  exit 1
fi

echo "✅ Pre-flight passed"
```

If ANY critical check fails: **STOP** with specific fix instructions. Don't waste tokens on a doomed run.

---

## Step 1 — Initialize (`/init --auto`)

**Skip if:** `--skip_init` flag AND `docs/BRD.md` + `docs/IMPLEMENTATION_GUIDELINES.md` exist

Run `/init` with auto-research protocol:
- `brd_interviewer`: researches all gaps using the 5-level ladder (docs → infer → web → default → flag)
- `impl_guidelines_agent`: researches tech decisions using same protocol
- All decisions logged to `agent_state/autonomous/decisions.md` with confidence levels

**Checkpoint:** Write `agent_state/autonomous/checkpoint.json`:
```json
{ "step": "init_complete", "timestamp": "...", "decisions_count": 24, "low_confidence": 3 }
```

---

## Step 2 — Plan Phase 1 (`/plan --auto --phase=1`)

Run `/plan` with auto scope assignment:
- `project_planner` auto-assigns FR-* to Phase 1 by dependency analysis (foundational requirements first)
- All specs, data contracts, UI specs produced
- Verification + reconciliation runs

**Checkpoint:** Write checkpoint with phase plan summary.

---

## Step 3 — HUMAN CHECKPOINT (before any implementation)

**This is the ONE required human interaction in the entire pipeline.**

Present a structured review document:

```markdown
# 🛑 Pre-Implementation Review

## Project Summary
[1-paragraph from BRD executive summary]

## Decisions Made (auto-researched)
### ⚠ LOW Confidence — NEEDS YOUR INPUT (N items)
| # | Question | Auto-Answer | Evidence | Risk |
|---|----------|------------|----------|------|

### 📋 MEDIUM Confidence — Quick Review (N items)
| # | Question | Auto-Answer | Evidence |
|---|----------|------------|----------|

### ✅ HIGH Confidence — Auto-Approved (N items)
[collapsed table — expand to review]

## Phase 1 Scope
- FR-* requirements: [list]
- Components: [list]
- Data contracts: [N endpoints typed]
- UI specs: [N screens]

## Tech Stack
[from IMPLEMENTATION_GUIDELINES]

## Key Assumptions
[from assumptions registry]

────────────────────────────────────────
To proceed: type "go" or "approve"
To modify: describe what to change
To stop: type "stop"
────────────────────────────────────────
```

**Wait for explicit user approval.** Do NOT proceed without it.

After approval:
- Lock all decisions as APPROVED
- Any LOW confidence items the user didn't modify: mark as "USER_ACCEPTED"
- Write `agent_state/autonomous/approved.json` with timestamp

---

## Step 4 — Develop Phase 1 (`/develop --auto --phase=1`)

Fully autonomous — no more human prompts.

### Auto-mode behaviors:
- **Escalations:** `continueWithDefault: true` for architecture/feature decisions — proceed with recommendation, log for review
- **⛔ Security escalations:** NEVER auto-resolve with permissive defaults. Use the **hardened default** (most restrictive option). If no clear hardened default exists → PAUSE and surface to user even in auto mode. Security domains: auth patterns, token storage/caching, IDOR mitigation, encryption, PII handling, CORS/CSRF, rate limiting.
- **Gate failures:** Auto-fix loop (max 3 cycles per failing item)
  - Cycle 1: Agent fixes → re-test specific failure
  - Cycle 2: Re-run with fresh context → re-test
  - Cycle 3: Simplify/skip problematic item → log as deferred
  - After 3 cycles: Force-gate with full logging → continue to next phase
- **Test failures:** Fix implementation, not tests (max 3 retries per test agent)

### Escalation Circuit Breaker

Prevent runaway escalation loops in autonomous mode:

- **Max escalations per step:** 3 — additional escalations auto-resolve with recommended defaults
- **In --auto mode:** continue with defaults but flag all as `"⚠ AUTO-RESOLVED — may need review"` in decision log and manifest `known_issues[]`
- **Max total escalations per phase:** 10 — if exceeded, EXIT auto mode entirely and surface to user:
  `"⛔ Phase ${PHASE} exceeded escalation limit (10). Review agent_state/debates/unresolved.json before continuing."`
- Unresolved decisions written to `agent_state/debates/unresolved.json`
- All auto-resolved decisions appear in the final report (Step 7) under "Decisions Made → Escalations resolved with default"

### Git branching:
```bash
# Before each phase
git checkout -b phase-${PHASE}-implementation

# After gate passes
git tag phase-${PHASE}-complete
git checkout main
git merge phase-${PHASE}-implementation --no-ff -m "Phase ${PHASE} complete"
```

### Checkpointing (after each step):
```json
{
  "phase": 1,
  "step": "tests_complete",
  "timestamp": "...",
  "tests": { "unit": "pass", "integration": "pass" },
  "next_step": "reconciliation"
}
```

**On catastrophic failure** (build won't compile, infra won't start after retries):
```bash
# Rollback to last known good state
git checkout main
git branch -D phase-${PHASE}-implementation
```
Log failure report → continue to next phase if independent, or STOP if blocking.

---

## Step 5 — Repeat for Remaining Phases

```
For each phase N (2, 3, ... max_phases):
  1. /plan --auto --phase=N
  2. If --confirm_each_phase: 🛑 HUMAN CHECKPOINT (same format as Step 3)
  3. /develop --auto --phase=N
  4. Checkpoint
```

**Phase dependency:** If Phase N gate was force-passed with known issues, Phase N+1 audit will surface them as carried-forward critical items.

---

## Step 6 — Global Acceptance (`/accept --auto`)

Run full acceptance testing across ALL completed phases:
- All personas exercised
- All FR-* acceptance criteria verified
- Contract shape assertions for every API endpoint
- Cross-phase workflow tests

Results written to `agent_state/autonomous/acceptance-report.md`.

---

## Step 7 — Final Report

```markdown
# Autonomous Run Report

## Summary
- Phases completed: N/N
- Total FR-* implemented: N
- Total tests: N passing
- Forced gates: N (see details below)
- Low-confidence decisions: N (user approved: N, still open: N)

## Per-Phase Results
| Phase | Goal | Gate | Tests | Issues |
|-------|------|------|-------|--------|
| 1 | Auth + Users | PASSED | 48/48 | 0 |
| 2 | Core CRUD | PASSED | 124/124 | 2 warnings |
| 3 | Reports | FORCED (1 blocker) | 86/88 | 1 deferred |

## Decisions Made
- Auto-researched: N (HIGH: N, MEDIUM: N, LOW: N)
- User-approved at checkpoint: N
- Escalations resolved with default: N

## Known Issues
[carried-forward items, forced gate items, deferred features]

## Time & Resources
- Total duration: Xh Xm
- Phases: N × (plan + develop)
- Checkpoints written: N

## Next Steps
[recommendations based on known issues and deferred items]
```

---

## Resume Mode (`--resume`)

If the pipeline was interrupted (context exhaustion, crash, timeout):

```bash
# Read last checkpoint
CHECKPOINT=$(cat agent_state/autonomous/checkpoint.json)
RESUME_PHASE=$CHECKPOINT.phase
RESUME_STEP=$CHECKPOINT.next_step
```

- Resume from exactly where it stopped
- All previous state preserved in `agent_state/`
- Git branches and tags preserved
- No re-running of completed steps

---

## Dependencies

### Install step (before /develop per phase)
```bash
# Run dependency installation BEFORE implementation agents start
cd ${PROJECT_ROOT}

# Detect and run package manager
[ -f "package.json" ] && npm install
[ -f "go.mod" ] && go mod tidy
[ -f "requirements.txt" ] && pip install -r requirements.txt
[ -f "Cargo.toml" ] && cargo build

# Verify
echo "✅ Dependencies installed"
```

---

## Safety Guarantees

1. **One human checkpoint** — review all auto-decisions before implementation
2. **Git branch per phase** — clean rollback to any phase boundary
3. **Checkpoint after every step** — resume from crash without re-work
4. **Auto-fix before revert** — tries to fix failures, doesn't blindly rollback
5. **Force-gate with full logging** — never silently skips failures
6. **Environment pre-flight** — catches infra issues in seconds, not minutes
7. **Decision audit trail** — every auto-decision documented with evidence + confidence
