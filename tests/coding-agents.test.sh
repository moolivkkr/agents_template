#!/usr/bin/env bash
# coding-agents.test.sh — deterministic guards for the coding side of the 2026-09-30 board review
# (docs/AGENT_BOARD_REVIEW_2026-09-30.md). Every check names the finding ID it protects, so a failure
# says which regression came back. Portable: runs under macOS /bin/bash 3.2 with BSD grep/sed/awk.
# Run: bash tests/coding-agents.test.sh   (exit 0 = pass)
set -uo pipefail
TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${CODING_AGENTS_ROOT:-$(cd "$TEST_DIR/.." && pwd)}"   # override to run the checks against a copy
C="$ROOT/.claude"
T="$C/agents/templates"
A="$C/agents/core"
PASS=0; FAIL=0
ok()  { echo "  ✓ $1"; PASS=$((PASS+1)); }
bad() { echo "  ✗ FAIL: $1"; FAIL=$((FAIL+1)); }
check() { if [ "$1" = 0 ]; then ok "$2"; else bad "$2"; fi; }   # check <status> <label>

CODING="api_developer backend_developer database_agent migration_agent ui_developer mobile_developer"
ENVELOPE_USERS="api_developer backend_developer ui_developer mobile_developer"
OPTIMIZERS="$A/code_optimizer.md $A/ui_code_optimizer.md $C/commands/optimize.md"
# Every file this side of the review owns (templates, core agents, commands, skills).
OWNED="$T/api_developer.tmpl $T/backend_developer.tmpl $T/database_agent.tmpl $T/migration_agent.tmpl $T/ui_developer.tmpl $T/mobile_developer.tmpl $A/code_optimizer.md $A/ui_code_optimizer.md $A/solution_selector.md $A/impl_guidelines_agent.md $A/deployment_agent.md $A/ci_cd_agent.md $A/backend_audit_agent.md $A/ui_audit_agent.md $A/agent_factory.md $C/commands/rollback.md $C/commands/optimize.md $C/skills/infrastructure/docker.md $C/skills/infrastructure/github-actions.md"
NEG='never|not |n.t |no |forbid|wrong|instead|supersed|without|avoid|refus|out of date|isn.t|nothing'

frontmatter() { awk 'NR==1 && /^---$/ {f=1; next} f && /^---$/ {exit} f' "$1"; }
dod()         { awk '/^## Definition of Done/{f=1} /^## Lessons Write-Back/{f=0} f' "$1"; }
# Lines matching $1 in files $2.. that carry no negation word — i.e. that RECOMMEND the pattern.
positive()    { local pat="$1"; shift; grep -nE "$pat" "$@" 2>/dev/null | grep -viE "$NEG"; }

echo "── Coding templates: packs, ownership, existing code, build gate ─────────────────"
for r in $CODING; do
  f="$T/$r.tmpl"
  frontmatter "$f" | grep -q 'skills/security/secure-coding.md'
  check $? "$r loads security/secure-coding.md (SEC-05)"
  grep -q '^## Ownership' "$f"
  check $? "$r has an Ownership section — one writer per artifact type (ARCH-03, DEV-05)"
  grep -qE 'audit_report(_ui)?\.md' "$f"
  check $? "$r reads the Wave 1 audit report before writing (DEV-04)"
  dod "$f" | grep -qi 'build gate'
  check $? "$r has a build gate in its Definition of Done (DEV-02)"
  # The frontmatter packs must reach the body (Claude Code ignores skill_packs:) — _sync-contract.sh ran.
  miss=0
  for p in $(frontmatter "$f" | grep -oE 'skills/[A-Za-z0-9_./{}-]+\.md'); do
    awk '/BEGIN reference-packs/,/END reference-packs/' "$f" | grep -qF "$p" || { miss=1; echo "      missing in reference-packs: $p"; }
  done
  check $miss "$r reference-packs block matches its skill_packs (run .claude/agents/_sync-contract.sh)"
done
for r in api_developer backend_developer migration_agent ui_developer mobile_developer; do
  grep -q 'verify-commands.json' "$T/$r.tmpl"
  check $? "$r's build gate uses agent_state/config/verify-commands.json (DEV-02, OPS-06)"
done
for r in api_developer backend_developer ui_developer mobile_developer; do
  grep -q 'never `git add -A`' "$T/$r.tmpl"
  check $? "$r stages only its own paths (DEV-04, parallel 2A.5/2A.6)"
done
for r in $ENVELOPE_USERS; do
  frontmatter "$T/$r.tmpl" | grep -q 'skills/api/response-envelope.md'
  check $? "$r loads api/response-envelope.md (ARCH-01, DEV-03)"
done

echo "── One envelope: no contradicting examples (ARCH-01, DEV-03, SEC-16) ─────────────"
CODING_FILES=""; for r in $CODING; do CODING_FILES="$CODING_FILES $T/$r.tmpl"; done
hits="$(grep -nE '"pagination"[[:space:]]*:|"offset"[[:space:]]*:' $CODING_FILES 2>/dev/null)"
[ -z "$hits" ]; check $? "no coding template shows a top-level pagination object or offset paging${hits:+ — $hits}"
hits="$(grep -nE '"detail"[[:space:]]*:' $CODING_FILES 2>/dev/null)"
[ -z "$hits" ]; check $? "no coding template shows an error \"detail\" field (SEC-16)${hits:+ — $hits}"
hits="$(grep -nE '"error"[[:space:]]*:[[:space:]]*null|[^=!]error:[[:space:]]*null' $CODING_FILES 2>/dev/null)"
[ -z "$hits" ]; check $? "no coding template shows error: null in a success body${hits:+ — $hits}"

echo "── Security while writing (SEC-08, SEC-09, SEC-10, DEV-14/SEC-14) ─────────────────"
hits="$(positive 'localStorage|sessionStorage' $OWNED)"
[ -z "$hits" ]; check $? "no owned file recommends localStorage/sessionStorage for tokens${hits:+ — $hits}"
hits="$(positive '\?token=' $OWNED)"
[ -z "$hits" ]; check $? "no owned file recommends a token in a URL / WebSocket query string${hits:+ — $hits}"
grep -q 'DOMPurify' "$T/ui_developer.tmpl" && grep -q 'dangerouslySetInnerHTML' "$T/ui_developer.tmpl"
check $? "ui_developer requires DOMPurify before any dangerouslySetInnerHTML (SEC-09)"
grep -qiE 'short-lived, single-use ticket|ticket fetched' "$T/ui_developer.tmpl"
check $? "ui_developer authenticates WebSockets with a ticket or cookie (SEC-08)"
hits="$(grep -nE 'direct LLM|AI_PROVIDER|composer-ai|aiService' "$T/ui_developer.tmpl")"
[ -z "$hits" ]; check $? "ui_developer has no browser-side LLM section (DEV-14/SEC-14)${hits:+ — $hits}"
hits="$(grep -niE 'vertix' $CODING_FILES)"
[ -z "$hits" ]; check $? "no coding template carries Vertix-specific sections or packs (#14, ARCH-14)${hits:+ — $hits}"
grep -q 'unless `APP_ENV` is exactly `local`, `dev` or `test`' "$T/backend_developer.tmpl" && ! grep -q 'Environment == "production"' "$T/backend_developer.tmpl"
check $? "backend_developer: secrets fail closed unless APP_ENV is exactly local|dev|test (SEC-10)"

echo "── Runtime contract and reliability (OPS-01, ARCH-10, DEV-10, SRE-03..07, SRE-16) ─"
for r in api_developer backend_developer; do
  grep -q '/healthz' "$T/$r.tmpl" && grep -q '/readyz' "$T/$r.tmpl" && grep -q 'Runtime contract' "$T/$r.tmpl"
  check $? "$r implements the runtime contract with /healthz + /readyz (OPS-01, ARCH-10, DEV-10)"
done
hits="$(positive '/(health|ready)([^A-Za-z0-9._-]|$)' $OWNED)"
[ -z "$hits" ]; check $? "no owned file uses /health or /ready — one health-path convention (SRE-16, OPS-07)${hits:+ — $hits}"
grep -qE 'serve.*migrate.*seed' "$T/backend_developer.tmpl"
check $? "backend_developer owns the serve/migrate/seed entry points (OPS-01)"
grep -q 'Never retry a non-idempotent call' "$T/backend_developer.tmpl"
check $? "backend_developer retries only idempotent calls (SRE-03)"
grep -q 'Optional dependencies (cache, search, email, feature-flag service) are never part of readiness' "$T/backend_developer.tmpl"
check $? "backend_developer keeps optional dependencies out of readiness (SRE-05)"
grep -q 'SIGTERM' "$T/backend_developer.tmpl" && grep -q 'preStop' "$T/backend_developer.tmpl"
check $? "backend_developer drains on SIGTERM before closing pools; preStop noted (SRE-06)"
grep -q 'max_connections' "$T/backend_developer.tmpl" && grep -q 'max_connections' "$T/database_agent.tmpl"
check $? "backend_developer + database_agent budget pools against max_connections (SRE-07)"
grep -q 'http.route' "$T/backend_developer.tmpl" && grep -q 'http.route' "$T/api_developer.tmpl" && ! grep -q 'tenant_id on every query, log line, and metric' "$T/backend_developer.tmpl"
check $? "metric labels use the route template, never raw paths or tenant_id (SRE-04)"
! grep -q 'Write migrations' "$T/backend_developer.tmpl"
check $? "backend_developer no longer writes migrations (ARCH-03, DEV-05)"

echo "── Migrations (SRE-02, OPS-12, ARCH-11, DEV-17, DEV-19, ARCH-12, ARCH-19) ─────────"
M="$T/migration_agent.tmpl"
! grep -q 'ADD CONSTRAINT IF NOT EXISTS' "$M"
check $? "migration_agent has no ADD CONSTRAINT IF NOT EXISTS — Postgres rejects it (DEV-17, OPS-12)"
grep -q 'pg_constraint' "$M"
check $? "migration_agent guards re-runnable constraints with a pg_constraint check (DEV-17)"
grep -q 'N-1' "$M" && grep -qi 'expand/contract' "$M"
check $? "migration_agent defaults to expand/contract and N-1 compatibility (SRE-02, ARCH-11)"
grep -q 'DOWN files are \*\*optional\*\*' "$M" && grep -q 'never run automatically outside `local`' "$M"
check $? "migration_agent: DOWN optional and never run automatically outside local (OPS-12, DEV-19)"
grep -q 'CONCURRENTLY' "$M" && grep -q 'lock_timeout' "$M"
check $? "migration_agent: CREATE INDEX CONCURRENTLY per tool + lock_timeout (SRE-02)"
awk '/^## Registry/,/^## Build gate/' "$M" | grep -qE '^[[:space:]]+applied:'
[ $? -ne 0 ]; check $? "migration registry stores no per-environment applied state (DEV-19, OPS-12)"
! frontmatter "$M" | grep -q 'reports/migration_safety.md'
check $? "migration_agent does not write migration_safety_reviewer's report path (ARCH-12)"
frontmatter "$M" | grep -q 'migration_agent/manifest.json'
check $? "migration_agent declares its manifest for the next phase (ARCH-19)"

echo "── UI hand-offs (ARCH-04, ARCH-08) ───────────────────────────────────────────────"
U="$T/ui_developer.tmpl"
frontmatter "$U" | awk '/required:/{f=1} /optional:/{f=0} f' | grep -q 'specs/api-contracts.md'
check $? "ui_developer binds to the as-built api-contracts.md (required input) (ARCH-04)"
frontmatter "$U" | grep -q 'ui_developer/manifest.json'
check $? "ui_developer declares ui_developer/manifest.json as an output (ARCH-08)"
miss=0; for k in route component testIDs states api_calls; do grep -q "\"$k\"" "$U" || { miss=1; echo "      manifest schema lacks \"$k\""; }; done
check $miss "ui_developer's manifest schema has route, component, testIDs, states, api_calls (ARCH-08)"

echo "── Optimizers (DEV-01, DEV-06, DEV-07, TEST-14, ARCH-15/16, SEC-18) ───────────────"
hits="$(grep -niE 'update (the )?test expectation|update mock to match|update snapshot if|update test to match|Update test expectation' $OPTIMIZERS)"
[ -z "$hits" ]; check $? "no optimizer instruction edits test expectations, mocks or snapshots (DEV-01)${hits:+ — $hits}"
for f in "$A/code_optimizer.md" "$A/ui_code_optimizer.md"; do
  n="$(basename "$f" .md)"
  grep -qiE 'read-only' "$f" && grep -q 'git revert' "$f"
  check $? "$n: tests/mocks are read-only and a failing test reverts the change (DEV-01, TEST-14)"
  grep -q 'Only through `/optimize`' "$f" && ! grep -q 'MANDATORY during' "$f"
  check $? "$n states it runs only via /optimize, not /develop (DEV-07, ARCH-15)"
  grep -q 'base_sha' "$f" && ! grep -qE 'HEAD~[0-9]|phase-\$\(\(PHASE-1\)\)-gate' "$f"
  check $? "$n scopes from base_sha, not HEAD~50 or a phase-N-gate tag (DEV-07, ARCH-15)"
done
hits="$(grep -nE "If they pass after removal, it's dead|Error handlers for errors that cannot occur|Migration rollback code" "$A/code_optimizer.md")"
[ -z "$hits" ]; check $? "code_optimizer: no dead-code-by-green-tests, no error-handler removal (DEV-06, SRE-17)${hits:+ — $hits}"
grep -q 'deadcode' "$A/code_optimizer.md" && grep -q 'U1000' "$A/code_optimizer.md" && grep -q 'vulture' "$A/code_optimizer.md" && grep -q 'knip' "$A/code_optimizer.md"
check $? "code_optimizer proves dead code with deadcode / staticcheck U1000 / knip / vulture (DEV-06)"
! grep -q 'knip --include components' "$A/ui_code_optimizer.md"
check $? "ui_code_optimizer uses valid knip issue types (DEV-17)"
hits="$(grep -nE 'reset --hard|grep -oP|HEAD~[0-9]' $OPTIMIZERS | grep -viE "$NEG")"
[ -z "$hits" ]; check $? "optimizers + /optimize: no reset --hard, grep -P or HEAD~N scope${hits:+ — $hits}"
grep -q 'base_sha' "$C/commands/optimize.md" && grep -q 'pre_sha' "$C/commands/optimize.md"
check $? "/optimize records base_sha scope and a pre_sha rollback point (DEV-07)"

echo "── Candidate mode parity (DEV-11, ARCH-06) ───────────────────────────────────────"
S="$A/solution_selector.md"
grep -q 'adopt pass' "$S" && grep -q 'api-contracts.md' "$S" && grep -q 'step 5b' "$S"
check $? "solution_selector: the winner leaves the Wave 2A artifacts via the step 5b adopt pass"

echo "── Rollback (SRE-01) ─────────────────────────────────────────────────────────────"
R="$C/commands/rollback.md"
! grep -qi 'migrate reset' "$R"
check $? "rollback.md has no 'migrate reset' example"
redeploy="$(grep -n '^## Step 2 — Redeploy' "$R" | cut -d: -f1)"; down="$(grep -n '^## Step 4 — Reverse schema' "$R" | cut -d: -f1)"
[ -n "$redeploy" ] && [ -n "$down" ] && [ "$redeploy" -lt "$down" ]
check $? "rollback redeploys the previous build before any schema step"
grep -q 'local only' "$R" && ! grep -qE 'last-migrations.json|previous-sha.txt' "$R"
check $? "DOWN migrations are local-only and explicit; no reads of files nothing writes"

echo "── Commands, versions, guidelines sections (OPS-06, OPS-08, OPS-09, OPS-07) ───────"
G="$A/impl_guidelines_agent.md"
SCR="$(mktemp -d)"; trap 'rm -rf "$SCR"' EXIT
awk 'prev=="```markdown" && $0=="## Commands and versions" {f=1} f && /^```$/ {exit} f {print} {prev=$0}' "$G" > "$SCR/cmds.md"
if python3 "$C/hooks/commands-table.py" "$SCR/cmds.md" --out "$SCR/vc.json" >/dev/null 2>&1 \
   && python3 -c "import json,sys; d=json.load(open(sys.argv[1])); assert d['test'] and d['typecheck'] and d['lint'] and d['versions']" "$SCR/vc.json"; then
  ok "impl_guidelines_agent's example Commands table parses with commands-table.py (OPS-06)"
else bad "impl_guidelines_agent's example Commands table does not parse with commands-table.py (OPS-06)"; fi
grep -q '^#### `## Runtime contract`' "$G" && grep -q '^#### `## Technology stack`' "$G"
check $? "impl_guidelines_agent writes ## Technology stack and ## Runtime contract (OPS-01, OPS-06)"
hits="$(grep -n 'Component Inventory' $OWNED)"
[ -z "$hits" ]; check $? "no owned file cites the nonexistent 'Component Inventory' section (OPS-06, agent_factory:49)${hits:+ — $hits}"
D="$C/skills/infrastructure/docker.md"
hits="$(grep -nE '^[[:space:]]*USER[[:space:]]+[^[:space:]]+[[:space:]]+#' "$D")"
[ -z "$hits" ]; check $? "docker.md has no USER line with a trailing comment (OPS-09)${hits:+ — $hits}"
hits="$(grep -nE '^[[:space:]]*USER[[:space:]]' "$D" | grep -vE 'USER[[:space:]]+[0-9]+(:[0-9]+)?[[:space:]]*$')"
[ -z "$hits" ] && grep -qE '^USER [0-9]+:[0-9]+$' "$D"
check $? "docker.md USER lines are numeric (lima rule 2)${hits:+ — $hits}"
hits="$(grep -nE 'golang:1\.[0-9]+|go-version: *"?1\.[0-9]|postgres:1[0-9]-' "$D" "$C/skills/infrastructure/github-actions.md")"
[ -z "$hits" ]; check $? "docker/CI skills take versions from the table, no literal Go/Postgres versions (OPS-08, OPS-07)${hits:+ — $hits}"
awk '/services:/{f=1} f' "$C/skills/infrastructure/github-actions.md" | grep -qE '^[[:space:]]+ports:'
check $? "github-actions.md maps the Postgres service port so localhost:5432 is reachable"
grep -q 'Commands and versions' "$A/deployment_agent.md" && grep -q 'Commands and versions' "$A/ci_cd_agent.md" && grep -q 'Runtime contract' "$A/deployment_agent.md"
check $? "deployment_agent + ci_cd_agent read commands/versions (and the runtime contract) from the guidelines"

echo "── Stack and project genericity (#14, ARCH-13, ARCH-14) ─────────────────────────"
# A pack a project didn't choose must never be loaded because an agent's frontmatter names it:
# component libraries come through {{UI_COMPONENTS}}, a design system only through the registry.
hits=""
for f in "$A"/*.md "$T"/*.tmpl; do
  h="$(frontmatter "$f" | grep -nE 'skills/ui/(shadcn|tailwind|[a-z0-9-]+-design-system)\.md')" && hits="$hits $(basename "$f"):$h"
done
[ -z "$hits" ]; check $? "no core agent or template hard-loads a component library or a product design system (ARCH-14)${hits:+ —$hits}"
grep -qE '^  design_system:' "$A/agent_factory.md"
check $? "agent_factory's tech profile carries frontend.design_system (named by the project, never inferred)"
for f in "$A/ux_designer.md" "$A/design_quality_reviewer.md" "$C/commands/design.md" "$C/skills/ui/README.md"; do
  grep -q 'tech_profile.frontend.design_system' "$f"
  check $? "$(basename "$f") resolves the design system from tech_profile.frontend.design_system"
done
grep -q 'without a ui_framework pack\|No pack for the UI framework' "$A/agent_factory.md"
check $? "agent_factory warns when the UI framework has no pack (ui_developer's examples are React-flavoured)"
# Build/verify steps run the Commands-and-versions rows, not a guess about the language.
for f in "$C/commands/develop-orchestrator.md" "$C/commands/accept.md"; do
  hits="$(grep -nE "grep -E '\\\\\.\((ts|go)|elif \[ -f \"(go\.mod|package\.json|Cargo\.toml)\" \]|^[[:space:]]*(go build|npm run build|cargo build)" "$f")"
  [ -z "$hits" ]; check $? "$(basename "$f") builds and verifies via verify-commands.json, not per-language guesses (ARCH-13)${hits:+ — $hits}"
done
grep -q "base_sha)\"..HEAD -- . ':(exclude)agent_state'" "$C/commands/develop-orchestrator.md"
check $? "Wave 2 counts changed code from base_sha in any language, not .ts/.go in HEAD~1 (ARCH-13)"

echo "────────────────────────────────────────────"
echo "coding-agents.test.sh: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
