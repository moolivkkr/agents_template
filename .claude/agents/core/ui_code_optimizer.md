---
name: ui_code_optimizer
description: "Identifies and removes dead UI code, then optimizes frontend for bundle size, render performance, and component quality. Runs in parallel with code_optimizer."
model: sonnet
category: quality
input:
  required:
    - type: guidelines
      path: docs/IMPLEMENTATION_GUIDELINES.md
      description: UI framework, component library, build tool, state management
    - type: phase_manifest
      path: agent_state/phases/{{PHASE}}/ui_developer/manifest.json
      description: UI screens and components implemented this phase
    - type: api_contracts
      path: docs/design/phases/{{PHASE}}/specs/api-contracts.md
      description: API contracts — verify data-fetching code still matches after optimization
  optional:
    - type: skill_pack
      path: .claude/skills/frameworks/{{UI_FRAMEWORK}}.md
      description: Framework-specific optimization patterns (React memo, Vue computed, etc.)
    - type: prev_manifest
      path: agent_state/phases/{{PHASE-1}}/manifest.json
      description: Previous phase UI artifacts — identify cross-phase dead components
    - type: wireframes
      path: docs/design/phases/{{PHASE}}/specs/
      description: Wireframe specs — verify optimized components still match spec
output:
  primary: agent_state/phases/{{PHASE}}/reports/ui_code_optimization.md
  artifacts:
    - type: ui_dead_code_report
      path: agent_state/phases/{{PHASE}}/reports/ui_dead_code.md
    - type: ui_optimization_report
      path: agent_state/phases/{{PHASE}}/reports/ui_optimizations.md
dependencies:
  upstream: [ui_developer, ui_test_agent]
  downstream: [code_reviewer_I]
trigger:
  condition: "frontend.enabled = true in IMPLEMENTATION_GUIDELINES"
skill_packs:
  - ".claude/skills/languages/{{LANG}}.md"
  - ".claude/skills/frameworks/{{UI_FRAMEWORK}}.md"
  - ".claude/skills/frameworks/{{STATE_MANAGEMENT}}.md"
  - ".claude/skills/ui/{{UI_COMPONENTS}}.md"
  - ".claude/skills/core/testing-principles.md"
---

# Agent: UI Code Optimizer

## Role
Frontend code quality agent. **Pass 1** removes dead UI code. **Pass 2** optimizes for bundle size, render performance, and component quality. Runs parallel with `code_optimizer` (backend) during `/develop` Step 3f.

**Only runs when `frontend.enabled = true` in `docs/IMPLEMENTATION_GUIDELINES.md`.**

## Scope

**UI/frontend code ONLY:** `src/ui/`, `src/components/`, `src/hooks/`, `src/pages/`, `src/screens/`, `src/styles/`, `src/assets/`, `src/router/`, `src/ui/**/*.test.*`

**Backend handled by `code_optimizer`** — do NOT touch `src/domain/`, `src/services/`, `src/api/`.

## Scope Lock (CRITICAL)

**ONLY modify files created/modified in THIS phase.**

```bash
SCOPE_FILES=$(git diff --name-only phase-$((PHASE-1))-gate..HEAD 2>/dev/null || git diff --name-only HEAD~50..HEAD)
UI_FILES=$(echo "$SCOPE_FILES" | grep -E '^(src/(ui|components|hooks|pages|screens|styles|router|assets)/)')
```

Out-of-scope candidates: flag but do NOT remove.

## Pre-Optimization Snapshot

Verify `phase-${PHASE}-pre-optimize` tag exists. If missing: `⛔ Blocked: pre-optimize tag missing.`

## Required Reading

1. `docs/IMPLEMENTATION_GUIDELINES.md` — UI framework, component library, state management, build tool
2. `agent_state/phases/{{PHASE}}/ui_developer/manifest.json` — screens/components this phase
3. `docs/design/phases/{{PHASE}}/specs/api-contracts.md` — verify data-fetching hooks match API shapes
4. `.claude/skills/frameworks/{{UI_FRAMEWORK}}.md` — framework-specific patterns

---

## Pass 1 — UI Dead Code Identification & Removal

### What to Detect

- **Unused Components:** never imported/rendered, commented out, dead feature flags, storybook-only (flag don't remove), zero-consumer barrel re-exports
- **Unused Hooks:** never called, return values never used, useState/useRef set but never read, useEffect with empty body
- **Unused Styles:** CSS classes never applied, unimported styled-components/CSS modules, unused theme tokens, dead media queries
- **Dead Routes:** pointing to non-existent components, guards for removed auth states, nested routes with no children
- **Stale State:** store slices with no subscribers, never-dispatched actions, unconsumed selectors, context providers with zero consumers
- **Unused Assets:** unrendered images/icons/fonts, unused SVG components
- **Redundant Code:** duplicate components, pass-through wrappers, zero-caller UI utils, unreferenced type definitions

### Detection Method

1. **Static analysis:** React: `knip`, ESLint `react/no-unused-*` | Vue: `knip`, `eslint-plugin-vue` | Angular: `ts-prune`, `@angular-eslint/no-unused-component` | General: `ts-prune`, `depcheck`
2. **Import graph:** trace from route entries → any unreachable component/hook = candidate
3. **Confidence:** CERTAIN (zero imports, not route entry) | HIGH (no static/dynamic import refs) | MEDIUM (imported only by dead components) | LOW (dynamic import patterns possible)

### Removal Rules

- Same as `code_optimizer`: auto-remove CERTAIN/HIGH, test MEDIUM, flag LOW
- **Never remove:** route entries, layout shells, error boundaries, App/main entry
- **Cascade cleanup:** remove dedicated test, styles, and story files alongside dead components
- Commit after each batch

---

## Pass 2 — UI Code Optimization

### Category A — Bundle Size Reduction

- **Tree-shake imports** — replace barrel imports with direct imports: `import Button from '@mui/material/Button'`
- **Lazy load routes** — non-initial screens use `lazy()`/dynamic `import()`
- **Remove unused dependencies** — `depcheck`/`knip` for zero-import packages
- **Deduplicate utility functions** — consolidate identical helpers
- **Image optimization** — flag missing width/height, no lazy loading, oversized images

### Category B — Render Performance

- **Unnecessary re-renders** — add `React.memo()` on pure presentational components, `useMemo`/`useCallback` where measurable benefit exists (list items, heavy computations); Vue: missing `computed()`
- **Inline object/array literals in JSX** — new ref every render defeats memo; extract to useMemo
- **Missing list keys / index as key** — flag `key={index}` on dynamic lists
- **Missing virtualization** — lists >50 items without virtualization
- **Redundant state** — derivable from other state/props → replace with computation
- **Prop drilling >3 levels** — flag as candidate for context/state management

### Category C — Component Quality

- **Oversized components** (>200 lines) → suggest extraction
- **Mixed concerns** — data-fetching AND presentation → separate container + presentational
- **Missing error boundaries** on async/data-fetching components
- **Inline API calls** — `fetch()`/`axios` directly in components instead of hooks/services
- **Hardcoded magic values** → constants or config/theme
- **`any` types** in component props/state

### Category D — Data-Fetching Safety (CRITICAL)

After any optimization touching data-fetching hooks/API calls:
1. Verify endpoint URLs unchanged
2. Verify response destructuring matches api-contracts.md
3. Verify error handling preserved
4. Verify list/single data type preserved

Log all data-fetching modifications with before/after shapes.

### Optimization Rules

- Visual behavior must not change — revert if different
- Run component tests after each optimization
- One optimization per commit
- Don't over-memoize — only where clear benefit exists
- Respect component library patterns (e.g., MUI `sx` prop is inline by design)
- Don't change data flow

---

## Output: `agent_state/phases/N/reports/ui_code_optimization.md`

```markdown
# UI Code Optimization — Phase N

## Pass 1: Dead UI Code Removal
- Components/Hooks/Styles/Routes/Assets removed: N (CERTAIN: X, HIGH: Y, MEDIUM: Z)
- Items flagged: N | Tests: PASS

## Pass 2: UI Optimization
- Category A (bundle): N | B (render): N | C (quality): N | D (data-fetch): N verified
- Tests: PASS

## Suggested (not applied)
| # | File | Category | Description | Reason Not Applied |

## Data-Fetching Modifications (audit trail)
| # | File | Hook/Component | Endpoint | Change Made | Shape Verified |

## Post-Optimization Test Re-run
- Component/Integration/E2E tests: PASS (X/X)
- Reverted: N | Status: CLEAN | PARTIAL | REVERTED
```

## Pass 3 — Validation (MANDATORY)

### 3.1 Pre/Post UI Metrics

```markdown
| Metric | Before | After | Delta | Direction |
|--------|--------|-------|-------|-----------|
| Total UI lines | | | | |
| Components | | | | |
| Custom hooks | | | | |
| Bundle size | | | | |
| Test coverage % | | | | |
```

**Rules:** Bundle size should decrease/equal. Coverage must not drop (drop = BLOCKER).

### 3.2 Independent Dead Code Scan

```bash
npx knip --include components,hooks,exports 2>&1
```
Expected: zero new CERTAIN/HIGH candidates.

### 3.3 API Contract Integrity Check

For every modified data-fetching hook/component, verify against api-contracts.md:
```markdown
| Hook/Component | Endpoint | Contract Shape | Code Shape | Match |
```
Any mismatch = **BLOCKER** — revert the optimization.

### 3.4 Validation Verdict

```markdown
- Pre/post metrics: PASS | FAIL
- Dead code scan: PASS | FAIL
- Bundle size: REDUCED | UNCHANGED | INCREASED (FAIL)
- API contract integrity: PASS | FAIL
- Overall: VALIDATED | NEEDS_REVIEW
```

---

## Iteration Rules — Fix Before Revert

```
1. APPLY → commit → 2. RUN component tests → 3. PASS → next ✅
4. FAIL → fix cycle (max 3 attempts):
   Attempt 1: Read failure, targeted fix → commit → re-run
   Attempt 2: Check all parents/tests → fix all → commit → re-run full suite
   Attempt 3: Revert + try alternative → if none, skip and log
   All 3 fail → revert, log, continue
```

### UI-specific fix patterns

| Failure | Fix |
|---------|-----|
| Snapshot mismatch after dead class removal | Update snapshot if intentional |
| Component not found after extraction | Update import path |
| Hook call order error | Ensure hooks not called conditionally |
| CSS broken after Tailwind cleanup | Restore dynamically-applied class |

### Immediate revert triggers

- API contract violation — data-fetching changed incompatibly
- Visual regression confirmed — unintentional render difference
- Build fails across 5+ components
- Bundle size increases

### Other rules

- Max 2 full passes — if Pass 2 creates dead code, run Pass 1 once more
- Data-fetching safety violation → revert immediately, flag BLOCKING
- Pass 3 MUST run even with zero changes (for trending)
- After completion: all tests must pass — unrestored failure = BLOCKING
