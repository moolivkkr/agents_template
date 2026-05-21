---
command: workstream
description: "Manage parallel workstreams — create, list, switch, status, complete, merge. Enables concurrent work on independent features."
arguments:
  - name: action
    required: true
    description: "Action: 'create', 'list', 'switch', 'status', 'complete', 'merge'"
  - name: name
    required: false
    description: "Workstream name (required for create, switch, complete, merge)"
  - name: phase
    required: false
    description: "Phase(s) this workstream covers. Can be comma-separated (e.g. '3,4' for phases 3 and 4)"
  - name: description
    required: false
    description: "Workstream description (used with 'create')"
  - name: independent
    required: false
    default: true
    description: "Whether this workstream is independent of the main pipeline (default: true)"
---

# /workstream — Parallel Workstream Management

Manages parallel workstreams that allow concurrent work on independent features. Each workstream operates on its own git branch with isolated state tracking, enabling multiple developers or agents to work simultaneously without blocking the sequential phase pipeline.

**When to use:** When features in different phases (or within a single phase) are independent and can be developed concurrently. E.g., auth system (Phase 3) and admin dashboard (Phase 4) have no shared dependencies.

**When NOT to use:** When features share data contracts, database tables, or API endpoints that would create merge conflicts. Use the sequential pipeline (`/develop`) for interdependent features.

---

## Anti-Rationalization Guard

| Your Internal Reasoning | Correct Response |
|---|---|
| "These workstreams touch the same files but it's probably fine" | NO. Check shared files. If overlap >0 files, mark dependency and warn. Silent merge conflicts waste hours. |
| "I'll skip the conflict check — I'll just fix conflicts when merging" | NO. Conflict detection at CREATE time prevents wasted parallel work. A 30-second check saves a 3-hour merge. |
| "The workstream is 95% done, I'll merge without completing the gate" | NO. An unverified merge poisons main. Complete the gate or don't merge. There is no "almost done" for merges. |
| "I'll merge directly without running integration tests on main" | NO. Two workstreams passing independently does NOT mean they pass together. Post-merge regression is mandatory. |
| "I can work on the same phase in two workstreams since they touch different components" | MAYBE — but only if `--independent=true` and zero shared files. Verify with dependency detection first. |
| "The merge conflict is small, I'll resolve it without re-testing" | NO. Every conflict resolution is a manual code change. Manual code changes get tested. No exceptions. |
| "I'll create a workstream for a quick fix" | NO. Quick fixes use `/hotfix`. Workstreams are for sustained parallel development. |

---

## Session Context Budget

> Full protocol: `.claude/skills/core/context-budget-protocol.md`

`/workstream` actions are short-lived (except `merge`). Context budget targets:

| Action | Target input tokens | What to load |
|--------|--------------------|----|
| create | ~5K | registry.json + phase plan files for overlap check |
| list | ~3K | registry.json only |
| switch | ~5K | registry.json + target workstream.json |
| status | ~10K | workstream.json + git diff summary + dependency files |
| complete | ~15K | workstream.json + phase gate files + scoped test results |
| merge | ~25K | workstream.json + git diff vs main + integration test results + post-merge regression |

**Result discipline:** Each action produces filesystem state, not conversation content. Summaries only in the conversation window.

---

## State Directory Structure

```
agent_state/workstreams/
├── registry.json                    # Global workstream registry
├── auth-system/
│   ├── workstream.json              # Workstream metadata and execution log
│   └── progress.md                  # Human-readable progress notes
├── admin-dashboard/
│   ├── workstream.json
│   └── progress.md
└── ...
```

---

## Action: `create`

### Step 0 — Validate Arguments

```bash
NAME=${ARG_NAME}
PHASE=${ARG_PHASE}
DESCRIPTION=${ARG_DESCRIPTION}
INDEPENDENT=${ARG_INDEPENDENT:-true}
```

Required for `create`: `--name` and `--phase`. If missing, STOP:

```
⛔ /workstream create requires --name and --phase

  Usage: /workstream --action=create --name=auth-system --phase=3 --description="Authentication and authorization"
```

Validate name format: lowercase alphanumeric with hyphens only. No spaces, no underscores, no uppercase.

```bash
if ! echo "$NAME" | grep -qE '^[a-z][a-z0-9-]{1,40}$'; then
  echo "⛔ Invalid workstream name: '${NAME}'"
  echo "  Must be: lowercase, alphanumeric + hyphens, 2-41 chars, start with letter"
  exit 1
fi
```

### Step 1 — Check Uniqueness

```bash
REGISTRY="agent_state/workstreams/registry.json"
WORKSTREAM_DIR="agent_state/workstreams/${NAME}"
```

If `${WORKSTREAM_DIR}` already exists:

```
⛔ Workstream '${NAME}' already exists
  Status: <active | paused | complete | merged>
  Branch: workstream/${NAME}

  Options:
    /workstream --action=switch --name=${NAME}     # Resume work
    /workstream --action=status --name=${NAME}     # Check progress
```

### Step 2 — Dependency and Overlap Detection

Parse `--phase` (supports comma-separated: `3,4`):

```bash
PHASES=$(echo "$PHASE" | tr ',' ' ')
```

For each active workstream in registry:
1. Check phase overlap: if any other active (non-merged) workstream covers the same phase(s) AND `--independent=false`, STOP:

```
⛔ Phase overlap detected
  Workstream '${NAME}' covers phase(s): ${PHASES}
  Workstream '${OTHER}' (active) also covers phase(s): ${OVERLAP_PHASES}

  Since --independent=false, these workstreams would conflict.
  Options:
    1. Use --independent=true if the workstreams touch different components
    2. Complete '${OTHER}' first: /workstream --action=complete --name=${OTHER}
    3. Choose different phases
```

2. Check file overlap: scan phase spec files (`docs/design/phases/${P}/specs/`) for component lists. Compare component file paths across workstreams. If shared files detected:

```
⚠ Shared file warning
  Workstream '${NAME}' and '${OTHER}' may both modify:
    - src/middleware/auth.go
    - src/handlers/user.go

  These are potential merge conflict points.
  Proceeding, but tracking as shared_files in workstream state.
```

Track shared files in workstream state regardless of `--independent` flag.

### Step 3 — Create Git Branch

```bash
# Ensure we're on a clean state
git stash --include-untracked -m "workstream-create-${NAME}" 2>/dev/null

# Create branch from main
git checkout -b "workstream/${NAME}" main
```

If branch already exists (orphaned from previous attempt):

```
⚠ Branch workstream/${NAME} already exists but no workstream state found.
  This may be from a previous aborted create.

  Options:
    1. Delete and recreate: git branch -D workstream/${NAME}
    2. Adopt existing branch: manually create workstream state
```

### Step 4 — Create Workstream State

```bash
mkdir -p "agent_state/workstreams/${NAME}"
```

Write `agent_state/workstreams/${NAME}/workstream.json`:

```json
{
  "name": "${NAME}",
  "description": "${DESCRIPTION}",
  "phases": [${PHASES_ARRAY}],
  "branch": "workstream/${NAME}",
  "status": "active",
  "independent": ${INDEPENDENT},
  "created_at": "<ISO-8601>",
  "last_activity": "<ISO-8601>",
  "progress_percent": 0,
  "commands_executed": [],
  "gate_states": {},
  "integration_points": [],
  "shared_files": [${SHARED_FILES}],
  "dependencies": [${DEPENDENCY_WORKSTREAMS}]
}
```

Write `agent_state/workstreams/${NAME}/progress.md`:

```markdown
# Workstream: ${NAME}

**Description:** ${DESCRIPTION}
**Phases:** ${PHASES}
**Branch:** workstream/${NAME}
**Created:** <ISO-8601>

---

## Progress Log

<!-- Append entries as work progresses -->
```

### Step 5 — Update Registry

Read or create `agent_state/workstreams/registry.json`. Add the new workstream entry:

```json
{
  "workstreams": [
    {
      "name": "${NAME}",
      "description": "${DESCRIPTION}",
      "phases": [${PHASES_ARRAY}],
      "branch": "workstream/${NAME}",
      "status": "active",
      "created_at": "<ISO-8601>",
      "last_activity": "<ISO-8601>",
      "progress_percent": 0,
      "dependencies": [${DEPENDENCY_WORKSTREAMS}],
      "shared_files": [${SHARED_FILES}]
    }
  ]
}
```

### Step 6 — Commit and Confirm

```bash
git add agent_state/workstreams/
git commit -m "workstream: create '${NAME}' covering phase(s) ${PHASES}

Branch: workstream/${NAME}
Independent: ${INDEPENDENT}"
```

Pop stash if one was created:

```bash
git stash pop 2>/dev/null
```

Output:

```
✅ Workstream created: ${NAME}

  Branch:      workstream/${NAME}  (checked out)
  Phases:      ${PHASES}
  Independent: ${INDEPENDENT}
  Shared files: ${N} detected (see workstream.json)

  Next steps:
    /plan --phase=${FIRST_PHASE}     # Plan phases for this workstream
    /develop --phase=${FIRST_PHASE}  # Implement when ready
    /workstream --action=list        # See all workstreams
```

---

## Action: `list`

### Step 0 — Read Registry

```bash
REGISTRY="agent_state/workstreams/registry.json"
CURRENT_BRANCH=$(git branch --show-current)
```

If registry does not exist:

```
No workstreams found.
  Create one: /workstream --action=create --name=<name> --phase=<N>
```

### Step 1 — Display Workstreams

For each workstream in the registry, read its `workstream.json` to get current progress. Determine active workstream by matching `CURRENT_BRANCH` to workstream branches.

Output format:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Workstreams
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ● auth-system       (active)   Phase 3      branch: workstream/auth-system       progress: 60%
  ○ admin-dashboard   (paused)   Phase 4      branch: workstream/admin-dashboard   progress: 20%
  ✓ api-core          (done)     Phase 1-2    branch: workstream/api-core          merged: 2026-05-20
  ✗ experiment-x      (aborted)  Phase 5      branch: workstream/experiment-x      aborted: 2026-05-18

  Current branch: ${CURRENT_BRANCH}
  Active workstreams: ${ACTIVE_COUNT}
  Total: ${TOTAL_COUNT}

CROSS-WORKSTREAM DEPENDENCIES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  auth-system ↔ api-core: 2 shared files (auth-middleware, user-handler)
  (none) — if no dependencies

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Status icons:
- `●` = active (currently checked out)
- `○` = paused (exists but not current branch)
- `✓` = done (completed and merged)
- `✗` = aborted

---

## Action: `switch`

### Step 0 — Validate Target

```bash
NAME=${ARG_NAME}
```

Required: `--name`. If missing, STOP and show available workstreams.

Verify workstream exists in registry and is not `merged` or `aborted`:

```
⛔ Cannot switch to workstream '${NAME}' — status is '${STATUS}'

  Merged/aborted workstreams are read-only.
  Active workstreams: [list names]
```

### Step 1 — Check for Uncommitted Changes

```bash
DIRTY=$(git status --porcelain)
```

If dirty:

```
⚠ Uncommitted changes detected on current branch

  Modified:  ${COUNT} files
  Untracked: ${COUNT} files

  Options:
    1. Commit first:  git add -A && git commit -m "wip: save progress"
    2. Stash:         git stash --include-untracked -m "workstream-switch"
    3. Abort switch

  Proceeding with auto-stash...
```

Auto-stash (associated with current workstream if applicable):

```bash
git stash --include-untracked -m "workstream-auto-stash: switching to ${NAME}"
```

### Step 2 — Save Current Workstream State

If the current branch matches an active workstream, update its `last_activity` timestamp in both `workstream.json` and `registry.json`. Set its status to `paused`.

### Step 3 — Switch Branch

```bash
git checkout "workstream/${NAME}"
```

If branch does not exist locally:

```
⛔ Branch workstream/${NAME} not found
  Workstream state exists but branch is missing.

  Options:
    1. Recreate branch from main: git checkout -b workstream/${NAME} main
    2. Delete workstream: remove state from agent_state/workstreams/${NAME}/
```

### Step 4 — Load and Display Context

Update target workstream: set `status` to `active`, update `last_activity`.

Read `workstream.json` and display resume context:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Switched to workstream: ${NAME}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Branch:      workstream/${NAME}
  Phases:      ${PHASES}
  Progress:    ${PROGRESS}%
  Last active: ${LAST_ACTIVITY}

  Last commands executed:
    ${LAST_3_COMMANDS_FROM_COMMANDS_EXECUTED}

  Gate states:
    Phase ${P}: ${STATE}

  Resume point:
    ${RECOMMENDED_NEXT_COMMAND}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Action: `status`

### Step 0 — Identify Target Workstream

```bash
NAME=${ARG_NAME}
```

If `--name` is not provided, infer from current branch:

```bash
CURRENT_BRANCH=$(git branch --show-current)
# If branch matches workstream/<name>, use that name
NAME=$(echo "$CURRENT_BRANCH" | sed 's|^workstream/||')
```

If neither provided nor inferrable, show all workstreams (`list` action).

### Step 1 — Read Workstream State

```bash
WORKSTREAM_JSON="agent_state/workstreams/${NAME}/workstream.json"
```

### Step 2 — Compute Git Diff Summary

```bash
# Files changed vs main
DIFF_STAT=$(git diff --stat main...HEAD)
FILES_CHANGED=$(git diff --name-only main...HEAD | wc -l)
COMMITS_AHEAD=$(git rev-list --count main..HEAD)
```

### Step 3 — Check Dependencies

For each dependency in `workstream.json.dependencies`:
1. Read the dependency workstream's status
2. Check if shared files have diverged (both branches modified the same file)

### Step 4 — Display Status

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Workstream: ${NAME}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Status:      ${STATUS}
  Branch:      workstream/${NAME}
  Phases:      ${PHASES}
  Independent: ${INDEPENDENT}
  Created:     ${CREATED_AT}
  Last active: ${LAST_ACTIVITY}

PROGRESS
━━━━━━━━
  Overall: ${PROGRESS}%
  Commands executed: ${COMMAND_COUNT}

  Phase gate states:
    Phase ${P}: ${STATE} (not_started | in_progress | passed | failed)

  Commands log:
    ${TIMESTAMP} /plan --phase=${P}      → completed
    ${TIMESTAMP} /develop --phase=${P}   → in_progress (Wave 2)
    ...

GIT SUMMARY
━━━━━━━━━━━
  Commits ahead of main: ${COMMITS_AHEAD}
  Files changed: ${FILES_CHANGED}
  Insertions: +${INSERTIONS}  Deletions: -${DELETIONS}

  Key changed paths:
    ${TOP_10_CHANGED_FILES}

DEPENDENCIES
━━━━━━━━━━━━
  Shared files with other workstreams:
    ${FILE}: also modified in '${OTHER_WORKSTREAM}' — ⚠ potential conflict
    (none if clean)

  Integration points:
    ${COMPONENT}: shared with [${OTHER_WORKSTREAMS}] — risk: ${RISK}
    (none if clean)

NEXT ACTION
━━━━━━━━━━━
  ▶ ${RECOMMENDED_COMMAND}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Action: `complete`

### Step 0 — Validate Workstream

```bash
NAME=${ARG_NAME}
WORKSTREAM_JSON="agent_state/workstreams/${NAME}/workstream.json"
```

Required: `--name`. Verify workstream exists and is `active` or `paused`.

If already complete or merged:

```
⛔ Workstream '${NAME}' is already ${STATUS}
```

### Step 1 — Verify Phase Gates

For each phase in the workstream's `phases` array, check for `gate.passed`:

```bash
for PHASE in ${PHASES}; do
  if [ ! -f "agent_state/phases/${PHASE}/gate.passed" ]; then
    MISSING_GATES+=("Phase ${PHASE}")
  fi
done
```

If any gates are missing:

```
⛔ Cannot complete workstream '${NAME}' — phase gates not passed

  Missing gates:
    Phase ${P}: no gate.passed found
    Phase ${Q}: no gate.passed found

  Run: /develop --phase=${P}
  Then: /workstream --action=complete --name=${NAME}
```

### Step 2 — Run Scoped Tests

Run the test suite scoped to this workstream's phases and components:

```bash
# Identify test files for this workstream's phases
# Read phase manifests for test file paths
# Run only those tests
```

If tests fail:

```
⛔ Scoped tests failing — cannot complete workstream

  Failing:
    ${TEST_FILE}: ${FAILURE_REASON}

  Fix with: /hotfix --phase=${P} --component=${C} --description="fix failing test"
  Then retry: /workstream --action=complete --name=${NAME}
```

### Step 3 — Mark Complete

Update `workstream.json`:
- Set `status` to `complete`
- Set `completed_at` to current timestamp
- Set `progress_percent` to 100

Update `registry.json` entry similarly.

Commit:

```bash
git add agent_state/workstreams/
git commit -m "workstream: mark '${NAME}' as complete

All phase gates passed. Scoped tests green.
Phases: ${PHASES}"
```

Output:

```
✅ Workstream '${NAME}' marked as complete

  Phases:     ${PHASES} — all gates passed
  Tests:      ✅ All scoped tests passing
  Branch:     workstream/${NAME}

  Next step:
    /workstream --action=merge --name=${NAME}   # Merge to main when ready
```

---

## Action: `merge`

### Step 0 — Validate Workstream

```bash
NAME=${ARG_NAME}
WORKSTREAM_JSON="agent_state/workstreams/${NAME}/workstream.json"
```

Required: `--name`. Verify workstream exists and status is `complete`:

```
⛔ Cannot merge workstream '${NAME}' — status is '${STATUS}'

  Workstream must be 'complete' before merging.
  Run: /workstream --action=complete --name=${NAME}
```

### Step 1 — Pre-Merge Conflict Check

```bash
git checkout main
git merge --no-commit --no-ff "workstream/${NAME}" 2>&1
MERGE_STATUS=$?
git merge --abort 2>/dev/null
```

If conflicts detected (`MERGE_STATUS != 0`):

```
⚠ Merge conflicts detected

  Conflicting files:
    ${FILE_1}
    ${FILE_2}
    ...

  Resolution approach:
    1. Switch to workstream: git checkout workstream/${NAME}
    2. Rebase onto main:     git rebase main
    3. Resolve conflicts in each file
    4. Re-run scoped tests:  /test --phase=${PHASES}
    5. Re-complete:          /workstream --action=complete --name=${NAME}
    6. Retry merge:          /workstream --action=merge --name=${NAME}
```

STOP here. Do not auto-resolve merge conflicts.

### Step 2 — Merge

```bash
git checkout main
git merge --no-ff "workstream/${NAME}" -m "merge: workstream/${NAME} — ${DESCRIPTION}

Phases: ${PHASES}
Branch: workstream/${NAME}
Workstream completed: ${COMPLETED_AT}"
```

### Step 3 — Post-Merge Regression

Run the FULL test suite on main (not scoped — full regression):

```bash
# Use project's test command from IMPLEMENTATION_GUIDELINES
# This is not optional — two independently valid branches can conflict on merge
```

If regression detected:

```
⛔ Post-merge regression detected on main

  Failing tests:
    ${TEST_FILE}: ${FAILURE_REASON}

  The merge is committed but main is RED.
  Immediate action required:

  Options:
    1. Fix forward: /hotfix --phase=${P} --component=${C} --description="fix merge regression"
    2. Revert merge: git revert -m 1 HEAD  (reverts the merge commit)
       Then investigate on the workstream branch before re-merging.

  ⚠ Do NOT proceed with other merges or deploys until main is green.
```

### Step 4 — Update Registry and Clean Up

Update `workstream.json`:
- Set `status` to `merged`
- Set `merged_at` to current timestamp
- Set `merge_commit` to the merge commit SHA

Update `registry.json` entry similarly.

Optionally clean up the branch (suggest, don't auto-delete):

```bash
# Branch can be deleted after merge
# git branch -d "workstream/${NAME}"
```

Commit registry update:

```bash
git add agent_state/workstreams/
git commit -m "workstream: record merge of '${NAME}' to main

Merge commit: ${MERGE_SHA}
Phases: ${PHASES}
Post-merge regression: ${PASS_OR_FAIL}"
```

Output:

```
✅ Workstream '${NAME}' merged to main

  Merge commit:  ${MERGE_SHA}
  Phases:        ${PHASES}
  Regression:    ✅ All tests passing on main
  Branch:        workstream/${NAME} (can be deleted)

  Clean up:
    git branch -d workstream/${NAME}

  Other active workstreams should rebase onto main:
    ${ACTIVE_WORKSTREAMS_LIST}
    For each: git checkout workstream/<name> && git rebase main

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Cross-Workstream Dependency Detection Protocol

This protocol runs during `create` (Step 2) and `status` (Step 3). It detects shared files and integration risks.

### File Overlap Detection

For each phase in the new workstream:
1. Read `docs/design/phases/${P}/specs/*.md` — extract file paths from component specs
2. Read `docs/design/phases/${P}/INDEX.md` — extract component list
3. For each active workstream covering overlapping phases:
   - Compare component file lists
   - If ANY file appears in both workstreams: record in `shared_files`

### Integration Point Detection

Check for cross-workstream integration at these boundaries:
- **API endpoints**: same route path in different workstreams
- **Database tables**: same table modified by multiple workstreams (migrations)
- **Shared middleware**: auth, logging, error handling used across workstreams
- **Config files**: shared config that multiple workstreams modify

Risk classification:
- **low**: shared read-only dependencies (e.g., both read from same config)
- **medium**: shared middleware or utility functions that could be modified
- **high**: same file modified in both workstreams (guaranteed merge conflict)

---

## Workstream + Pipeline Command Integration

When running pipeline commands (`/plan`, `/develop`, `/test`, `/review`) inside a workstream:

1. Commands operate on the workstream's branch (no special handling needed — git branch is already correct)
2. Phase state (`agent_state/phases/`) is shared across workstreams on the same branch
3. After each command execution, update the workstream's `commands_executed` array and `last_activity`
4. Gate states in `workstream.json` should reflect the actual `gate.passed` state for the workstream's phases

**Important:** If two workstreams cover the same phase (allowed with `--independent=true`), their gate states are independent because they're on separate branches. The gate on main is what matters for `/deploy`.

---

## Rules

- **Workstreams are branch-based** — every workstream gets its own git branch. No working on main directly while workstreams exist.
- **Create before you fork** — always create the workstream state before starting parallel work. Ad-hoc branches without workstream state are invisible to the framework.
- **Complete before you merge** — phase gates must pass on the workstream branch before merging to main. No "merge and fix later."
- **Regression after every merge** — full test suite runs on main after every workstream merge. Two green branches can produce a red main.
- **Conflicts block, not warn** — if merge conflicts are detected, the merge STOPS. No auto-resolution of conflicts.
- **Shared files are tracked, not banned** — multiple workstreams CAN touch the same files, but the overlap is recorded and surfaced. The developer decides whether to proceed.
- **One active workstream per checkout** — `switch` changes the active workstream. Only one workstream is active (checked out) at a time per working directory.
- **State lives in the branch** — workstream state (`agent_state/workstreams/`) is committed to the workstream's branch. The registry on main is updated only on merge.
- **Hotfixes are not workstreams** — use `/hotfix` for quick, scoped bug fixes. Workstreams are for sustained parallel development of features.
- **Rebase before merge** — if main has advanced since the workstream was created, rebase the workstream onto main before merging to minimize conflicts.
