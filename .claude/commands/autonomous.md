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

Runs `/init` → `/plan` → `/develop` for all phases with auto-research and ONE human checkpoint before implementation.

```
Phase 0:  Environment pre-flight
Phase 1:  /init --auto (research all decisions)
Phase 2:  /plan --auto --phase=1
Phase 3:  HUMAN CHECKPOINT (review all decisions)
Phase 4:  /develop --auto --phase=1
Phase 5:  Repeat plan→develop for remaining phases
Phase 6:  /accept --auto (global acceptance)
Phase 7:  Final report
```

---

## Step 0 — Environment Pre-Flight

```bash
echo "Environment pre-flight check..."
docker info > /dev/null 2>&1 || { echo "Docker not running"; exit 1; }
for cmd in git node npm; do
  command -v $cmd > /dev/null 2>&1 || echo "⚠ $cmd not found in PATH"
done
for port in 3000 5432 8080; do
  lsof -i :$port > /dev/null 2>&1 && echo "⚠ Port $port already in use"
done
if [ ! -d "requirements/" ] || [ -z "$(ls requirements/)" ]; then
  echo "⛔ requirements/ directory empty or missing."; exit 1
fi
echo "✅ Pre-flight passed"
```

Critical failure → **STOP** with fix instructions.

---

## Step 1 — Initialize (`/init --auto`)

**Skip if:** `--skip_init` AND `docs/BRD.md` + `docs/IMPLEMENTATION_GUIDELINES.md` exist

Run `/init` with auto-research: agents use 5-level ladder (docs → infer → web → default → flag). All decisions logged to `agent_state/autonomous/decisions.md` with confidence levels.

**Checkpoint:** `agent_state/autonomous/checkpoint.json`:
```json
{ "step": "init_complete", "timestamp": "...", "decisions_count": 24, "low_confidence": 3, "auto_resolved_count": 0, "auto_resolved_security_count": 0, "auto_resolved_log": "agent_state/autonomous/auto-resolved.jsonl" }
```

---

## Step 2 — Plan Phase 1 (`/plan --auto --phase=1`)

Auto-assigns FR-* to Phase 1 by dependency analysis. All specs, data contracts, UI specs produced. Verification + reconciliation runs. Checkpoint written.

---

## Step 3 — HUMAN CHECKPOINT

**The ONE required human interaction in the pipeline.**

Present structured review: LOW confidence items (needs input), MEDIUM (quick review), HIGH (auto-approved). Phase 1 scope, tech stack, key assumptions.

**Wait for explicit approval.** After approval: lock decisions as APPROVED, write `agent_state/autonomous/approved.json`.

---

## Step 4 — Develop Phase 1 (`/develop --auto --phase=1`)

Fully autonomous — no more human prompts.

### Auto-mode behaviors:
- **Escalations:** proceed with recommendation, log for review
- **Security escalations:** NEVER auto-resolve permissively. Use hardened default (most restrictive). No clear hardened default → PAUSE even in auto mode. Security domains: auth, token storage, IDOR, encryption, PII, CORS/CSRF, rate limiting.
- **Gate failures:** Auto-fix loop (max 3 cycles): fix→re-test, fresh context→re-test, simplify/skip→log deferred. After 3: force-gate with logging.
- **Test failures:** Fix implementation, not tests (max 3 retries)

### Escalation Circuit Breaker
- **Per step:** max 3 — additional auto-resolve with defaults
- **Per phase:** max 10 — exceeded → EXIT auto mode, surface to user
- Unresolved → `agent_state/debates/unresolved.json`

### Auto-Resolution Logging (MANDATORY)

Every auto-resolved escalation → `agent_state/autonomous/auto-resolved.jsonl`:
```jsonl
{"ts":"<ISO>","phase":N,"step":"<step_id>","escalation_number":N,"topic":"<topic>","question":"<full question>","options":["A: <opt>","B: <opt>"],"auto_selected":"<opt_id>","auto_rationale":"<why>","confidence":"HIGH|MEDIUM|LOW","category":"<architecture|security|data|ux|performance|other>","would_block":false}
```

**Rules:** Log BEFORE applying. Include FULL question + ALL options. Security-adjacent topics → `"category": "security"` + `"security_flag": true`.

### Git branching:
```bash
git checkout -b phase-${PHASE}-implementation
# After gate passes
git tag phase-${PHASE}-complete
git checkout main
git merge phase-${PHASE}-implementation --no-ff -m "Phase ${PHASE} complete"
```

### Checkpointing (after each step):
```json
{ "phase": 1, "step": "tests_complete", "timestamp": "...", "tests": { "unit": "pass", "integration": "pass" }, "next_step": "reconciliation", "auto_resolved_count": 0, "auto_resolved_security_count": 0, "auto_resolved_log": "agent_state/autonomous/auto-resolved.jsonl" }
```

**On catastrophic failure** (build won't compile, infra down after retries): rollback branch, log failure, continue to next phase if independent or STOP if blocking.

---

## Step 5 — Repeat for Remaining Phases

For each phase N (2, 3, ... max_phases): `/plan --auto` → optional checkpoint if `--confirm_each_phase` → `/develop --auto` → checkpoint.

### Post-Phase Auto-Resolution Review

After each phase: read `auto-resolved.jsonl`, filter for completed phase, count by category, generate summary. If ANY security-flagged: surface prominently + include in manifest under `"auto_resolved_security"`.

**Phase dependency:** Force-passed gate items surface as carried-forward critical items in next phase.

---

## Step 6 — Global Acceptance (`/accept --auto`)

Full acceptance across ALL completed phases: all personas, all FR-*, contract shape assertions, cross-phase workflows. Results → `agent_state/autonomous/acceptance-report.md`.

---

## Step 7 — Final Report

```markdown
# Autonomous Run Report

## Summary
- Phases completed: N/N
- Total FR-* implemented: N
- Total tests: N passing
- Forced gates: N
- Low-confidence decisions: N

## Per-Phase Results
| Phase | Goal | Gate | Tests | Issues |

## Decisions Made
- Auto-researched: N (HIGH/MEDIUM/LOW breakdown)
- User-approved at checkpoint: N
- Escalations resolved with default: N

## Auto-Resolution Audit
| Phase | Total | Architecture | Security | Data | UX | Performance |

⚠ Security-Adjacent Auto-Resolutions:
| Phase | Topic | Auto-Selected | Confidence |

Full audit trail: agent_state/autonomous/auto-resolved.jsonl

## Known Issues / Time & Resources / Next Steps
```

---

## Resume Mode (`--resume`)

Read `agent_state/autonomous/checkpoint.json` → resume from exactly where stopped. All previous state, git branches, tags preserved. No re-running completed steps.

---

## Dependencies

```bash
# Install before /develop per phase
[ -f "package.json" ] && npm install
[ -f "go.mod" ] && go mod tidy
[ -f "requirements.txt" ] && pip install -r requirements.txt
[ -f "Cargo.toml" ] && cargo build
```

---

## Safety Guarantees

1. **One human checkpoint** before implementation
2. **Git branch per phase** — clean rollback to any boundary
3. **Checkpoint after every step** — resume from crash
4. **Auto-fix before revert** — tries to fix, doesn't blindly rollback
5. **Force-gate with full logging** — never silently skips
6. **Environment pre-flight** — catches infra issues in seconds
7. **Decision audit trail** — every auto-decision with evidence + confidence
8. **Structured auto-resolution log** — full audit in `auto-resolved.jsonl`
