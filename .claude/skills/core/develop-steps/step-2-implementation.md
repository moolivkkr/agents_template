<!-- Part of /develop (~/.claude/commands/startup/develop.md). Read when executing this step. -->

## Step 2 — Implementation (Build-step Parallel Execution)

> **Vocabulary note:** "Wave 1–6" is RESERVED for the six-wave macro model (Orient/Audit,
> Implement, Test, Review, Iterate, Gate) used throughout this file and `/develop-orchestrator`.
> Step 2's internal build order below uses a SEPARATE, non-colliding label — **Build-step B\*** — so
> no "Wave N" ever means two different things. This entire Step 2 tree is the internal decomposition
> of macro Wave 2 (IMPLEMENT).

**Agents:** Generated agents from `.claude/agents/generated/` per component type

Run implementation in the build-steps defined in `PHASE_PLAN.md`. Each build-step runs its agents in
parallel; build-steps are sequential.

**Typical build-step structure:**
```text
Build-step B1 (parallel):
  ├─ database_agent     → schema design + docs/design/database.md
  └─ migration_agent    → migration files (up + down)

Build-step B1-gate (sequential gate — validates migrations before applying):
  └─ Migration Validation → dry-run migrations against test DB
      Checks:
      1. Migration files parse without syntax errors
      2. UP migration applies cleanly to empty test DB
      3. DOWN migration reverses the UP cleanly
      4. UP re-applies after DOWN (idempotency)
      If validation fails → block Build-step B2a, surface error to migration_agent for fix (max 1 retry)
```

### Migration Failure Auto-Recovery

If UP migration fails:
1. Immediately run the DOWN migration for the failed file to restore schema consistency
2. Log the specific error: `⛔ Migration ${FILE} UP failed: ${ERROR}`
3. Log the rollback: `↩ Auto-rolled back ${FILE} DOWN to restore schema`
4. Route back to migration_agent with the specific error for fix (max 1 retry)
5. After fix: re-run UP → validate → proceed if success

If DOWN rollback also fails:
- STOP immediately — schema is now in an unknown state
- Surface: `⛔ CRITICAL: Migration UP failed AND DOWN rollback failed. Manual intervention required.`
- Write to agent_state/phases/${PHASE}/migration_failure.json with full error details
- Do NOT proceed to Build-step B2a

This prevents the common failure where Phase N migration adds a table, fails partway through,
and Phase N re-development tries to add the same table again.

**Migration Safety Gate (BLOCKING):**
- Zero CRITICAL findings in migration_safety.md
- All DOWN migrations exist and are non-empty
- Irreversible migrations explicitly acknowledged in migration metadata
- If any CRITICAL finding: STOP — do not apply migration until resolved

```text
Build-step B2a (sequential — api_developer depends on backend service interfaces):
  └─ backend_developer  → domain models, services, repositories
       ↓ writes manifest with service method return types (list/single/none)

Build-step B2a-check (COMPILE/TYPECHECK GATE — BLOCKING):
  └─ Build verification: compile/typecheck the codebase
       See "Build-step B2a-check — Compile/Typecheck Gate" section below
       If FAILS → route back to backend_developer for fix (max 2 attempts)
       Do NOT proceed to Build-step B2b on broken code
```

### Build-step B2a-check — Compile/Typecheck Gate (BLOCKING)

**Purpose:** Catch compilation errors before downstream agents build on broken code. This is cheap (seconds to run) but prevents expensive downstream failures where api_developer builds on code that doesn't compile.

**Command:** the `typecheck` row (falling back to `build`) of `agent_state/config/verify-commands.json` — the
same command the orchestrator's 2A build gate and `verify-gate.sh` run. The table below only shows what
that row typically holds per language; when the project's row differs, the row wins.

**Typical rows:**
| Language | Command | Pass Condition |
|----------|---------|---------------|
| Go | `go build ./...` | Exit code 0 |
| TypeScript | `tsc --noEmit` | Exit code 0 |
| Python | `python -m py_compile <changed_files>` + `mypy <changed_files>` (if mypy configured) | Exit code 0 |
| Java | `mvn compile -q` or `gradle compileJava` | Exit code 0 |
| Rust | `cargo check` | Exit code 0 |

```bash
V=agent_state/config/verify-commands.json
CMD="$(jq -r '.commands.typecheck // .commands.build // empty' "$V")"
# no row (or no file) must stop here: `bash -c ""` exits 0 and the gate would pass having run nothing
[ -n "$CMD" ] || { echo "⛔ BLOCKED: no typecheck/build row in $V"; exit 1; }
PHASE="${PHASE}" bash -o pipefail -c "$CMD"
# What such a row typically holds:
#   Go:         go build ./...
#   TypeScript: npx tsc --noEmit
#   Python:     python -m py_compile $(git diff --name-only --diff-filter=AM HEAD -- '*.py')
#   Java:       mvn compile -q  OR  gradle compileJava
#   Rust:       cargo check
```

**On failure:**
1. Capture compiler error output (first 50 lines)
2. Route back to `backend_developer` with the error output as context
3. Max 2 fix attempts — backend_developer reads compiler errors, fixes, then re-runs compile check
4. If still failing after 2 attempts: **STOP** — surface compiler errors to user
5. Do **NOT** proceed to Build-step B2b (api_developer) on broken code — api_developer will build on a broken foundation

**On success:**
```text
✅ Build-step B2a-check — Compile/Typecheck Gate PASSED
   Language: <detected language>
   Command: <command run>
   → Proceeding to Build-step B2b (api_developer)
```

**Log to execution.jsonl:**
```bash
echo "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"compile_check\",\"step\":\"B2a-check\",\"status\":\"passed|failed\",\"language\":\"<lang>\",\"attempt\":${ATTEMPT:-1}}" >> "agent_state/phases/${PHASE}/execution.jsonl"
```

### Agent Handoff Protocol (Build-step B2a → B2b)

After backend_developer completes — **atomic write + verified ready signal:**
1. Write manifest to `.tmp` first: `agent_state/phases/${PHASE}/backend_developer/manifest.json.tmp`
2. Validate JSON: `python3 -c "import json,sys; json.load(sys.stdin)" < agent_state/phases/${PHASE}/backend_developer/manifest.json.tmp`
3. If valid: atomic move: `mv manifest.json.tmp manifest.json`
4. If invalid: STOP — do not touch ready signal. Log error and retry manifest write (max 1 retry).
5. Verify report exists: `test -f agent_state/phases/${PHASE}/reports/backend_developer.md`
6. **Only after steps 1-5 succeed:** Touch ready signal: `touch agent_state/phases/${PHASE}/.backend_developer_VERIFIED`

```bash
# Atomic agent handoff — prevents downstream agents from reading partial manifests
MANIFEST_DIR="agent_state/phases/${PHASE}/backend_developer"
python3 -c "import json,sys; json.load(sys.stdin)" < "${MANIFEST_DIR}/manifest.json.tmp" && \
  mv "${MANIFEST_DIR}/manifest.json.tmp" "${MANIFEST_DIR}/manifest.json" && \
  touch "agent_state/phases/${PHASE}/.backend_developer_VERIFIED" || \
  { echo "⛔ backend_developer manifest invalid — blocking handoff"; exit 1; }
```

Before api_developer starts:
1. Check: `test -f agent_state/phases/${PHASE}/.backend_developer_VERIFIED` (**VERIFIED, not just ready**)
2. If missing: WAIT or FAIL — do not proceed with stale/missing data
3. Validate manifest is readable: `python3 -c "import json,sys; json.load(sys.stdin)" < agent_state/phases/${PHASE}/backend_developer/manifest.json`
4. Read `backend_developer/manifest.json` for service method return types

This pattern applies to ALL wave transitions where one agent depends on another's output. The **atomic write + verified ready signal** prevents race conditions where a downstream agent reads a partial or corrupt manifest.

```text
Build-step B2b (depends on B2a passing build + backend_developer ready signal):
  └─ api_developer      → API handlers, routes, middleware, DTOs, api-contracts.md
       ↓ reads data-contracts.md from /plan as MANDATORY source of truth for response shapes
       ↓ api-contracts.md is DERIVED from data-contracts.md (validates, doesn't reinvent)
       ↓ if api-contracts.md shapes differ from data-contracts.md → BLOCKER
       ↓ reads backend_developer manifest to pick respondList/respondOne/respondError

Build-step B2b-check (API LAYER COMPILE CHECK — BLOCKING):
  └─ Build verification: compile/typecheck after api_developer's changes
       Same compile/typecheck command as Build-step B2a-check
       Verifies api_developer's changes compile cleanly WITH backend_developer's code
       If FAILS → route back to api_developer for fix (max 2 attempts), then STOP
```

### Build-step B2b-check — API Layer Compile Check (BLOCKING)

**Purpose:** Verify that api_developer's changes compile cleanly alongside backend_developer's code. API handlers frequently reference service interfaces, DTOs, and error types — type mismatches between layers are the most common inter-agent failure mode.

**Command:** Same language-specific compile/typecheck command as Build-step B2a-check (see table above).

**On failure:**
1. Capture compiler error output (first 50 lines)
2. Route back to `api_developer` with the error output as context
3. Max 2 fix attempts — api_developer reads compiler errors, fixes, then re-runs compile check
4. If still failing after 2 attempts: **STOP** — surface compiler errors to user
5. Do **NOT** proceed to Build-step B2-contract/B2-smoke/B3 on broken code

**On success:**
```text
✅ Build-step B2b-check — API Layer Compile Check PASSED
   Language: <detected language>
   Command: <command run>
   → Proceeding to Build-step B2-contract/B2-smoke (contract validation / smoke test)
```

**Log to execution.jsonl:**
```bash
echo "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"compile_check\",\"step\":\"B2b-check\",\"status\":\"passed|failed\",\"language\":\"<lang>\",\"attempt\":${ATTEMPT:-1}}" >> "agent_state/phases/${PHASE}/execution.jsonl"
```

```text
Build-step B2-contract (sequential gate, UI phases only):
  └─ Contract Validation → verify api-contracts.md exists, all endpoints documented, shapes are unambiguous

Build-step B2-smoke (SMOKE TEST — before expensive UI implementation):
  └─ Quick smoke test: does the app start? Does GET /health respond?
       docker compose up -d && curl -sf http://localhost:PORT/healthz   (the runtime contract's liveness path)
       If FAILS → route back to api_developer for fix (max 1 retry)
       This catches catastrophic failures before spending tokens on UI + test agents

Build-step B3 (parallel, UI phases only — BLOCKED until Build-step B2-smoke passes):
  └─ ui_developer       → screen implementation from UI specs + api-contracts.md + data-contracts.md

Build-step B3-check (FRONTEND BUILD CHECK — BLOCKING, UI phases only):
  └─ Build verification: full frontend build after ui_developer's changes
       See "Build-step B3-check — Frontend Build Check" section below
       If FAILS → route back to ui_developer for fix (max 2 attempts), then STOP
```

### Build-step B3-check — Frontend Build Check (BLOCKING, if UI phase)

**Purpose:** Catch frontend build failures before expensive test agents run. UI code frequently has TypeScript errors, missing imports, or JSX/TSX issues that are invisible until a full build runs.

**Skip if:** `frontend.enabled = false` or this phase has no UI components (no Build-step B3).

**Command:** the frontend's `build` row in `agent_state/config/verify-commands.json` (or an `x:` row the
table defines for the UI). Typical rows:

| Framework | Command | Pass Condition |
|-----------|---------|---------------|
| React (CRA) | `npm run build` | Exit code 0 |
| Next.js | `npx next build` | Exit code 0 |
| Vue/Nuxt | `npm run build` | Exit code 0 |
| Vite | `npx vite build` | Exit code 0 |
| Angular | `npx ng build` | Exit code 0 |

**Additional checks (run after build passes):**
- TypeScript strict mode: `tsc --noEmit --strict` (if `tsconfig.json` has `strict: true`)
- ESLint: `npx eslint src/ --max-warnings 0` (zero warnings policy — catches unused imports, type issues)

**Detection:** Read `package.json` to determine the framework and build command. Fall back to `npm run build` if unclear.

```bash
# Detect frontend framework and run build check
# Read package.json for scripts.build or framework-specific dependencies
# Examples:
#   React/CRA:  npm run build
#   Next.js:    npx next build
#   Vue:        npm run build
#   Vite:       npx vite build
#
# Additional TypeScript check (if tsconfig.json exists):
#   npx tsc --noEmit
#
# ESLint check (if eslint.config.* exists — ESLint 10 ignores .eslintrc*):
#   npx eslint src/ --max-warnings 0
```

**On failure:**
1. Capture build error output (first 50 lines)
2. Route back to `ui_developer` with the error output as context
3. Max 2 fix attempts — ui_developer reads build errors, fixes, then re-runs build check
4. If still failing after 2 attempts: **STOP** — surface build errors to user
5. Do **NOT** proceed to Build-step B4 (test agents) on broken frontend code

**On success:**
```text
✅ Build-step B3-check — Frontend Build Check PASSED
   Framework: <detected framework>
   Build command: <command run>
   TypeScript check: PASSED | SKIPPED (no tsconfig)
   ESLint check: PASSED | SKIPPED (no eslint config)
   → Proceeding to Build-step B4 (test agents)
```

**Log to execution.jsonl:**
```bash
echo "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"frontend_build_check\",\"step\":\"B3-check\",\"status\":\"passed|failed\",\"framework\":\"<framework>\",\"attempt\":${ATTEMPT:-1}}" >> "agent_state/phases/${PHASE}/execution.jsonl"
```

```text
Build-step B4 (parallel — test agents read BOTH specs AND implementation code):
  ├─ unit_test_agent     → unit tests for all new code (reads actual functions, not just specs)
  └─ integration_test_agent → integration tests for service↔infra + contract shape tests
```

> **Note:** Build-step B4 above is the initial unit/integration test authoring that runs INSIDE macro
> Wave 2's implement loop. It does not replace macro **Wave 3 (TEST)**, which spawns the separate
> per-tier test agents (unit / integration / e2e) under `/develop-orchestrator`.

Each agent:
1. Reads ALL Step 0 context + its specific spec files
2. Reads its activated skill pack (`~/.claude/skills/languages/{{LANG}}.md` etc.)
3. Implements only what is in scope for this phase (prev manifest shows what exists)
4. Writes an agent-level manifest to `agent_state/phases/${PHASE}/<agent>/manifest.json`

---

> Config blocks checked 2026-09-30 (`bash tests/archetype-compile/config-packs/run.sh --live`): 5 bash blocks: bash -n (macOS bash 3.2.57) + shellcheck 0.11.0; 2 run in fixture scenarios on macOS bash 3.2.57; 1 block not checked (pseudo-step).
