#!/usr/bin/env bash
# stitch-core.test.sh — Google Stitch is the core, two-way designer (skills/ui/stitch-design.md).
# Guards the decisions behind it, so a later edit can't quietly turn Stitch back into an optional extra:
#   1. Stitch is /design's default; the text-wireframe path is --source=wireframe (fallback only)
#   2. approval: the owner interactively, design_quality_reviewer under /autonomous + an owner-review list
#   3. /stitch import / adopt / request / sync-back exist with their mechanics
#   4. ui_developer / mobile_developer build against the approved render and record stitch_deviations[]
#   5. stitch.json schema: good and bad fixtures (tests/lib/stitch_cases.py), schema file in step
#   6. the gate check: verify-gate.sh (g) PASS and BLOCK cases (here + tests/verify-gate.test.sh)
#   7. the import capture (stitch-capture.mjs, run live against a local static page when Playwright is
#      installed) and the fidelity scorer on known images
# Bash 3.2 compatible. No network: the live capture serves tests/fixtures/stitch/site on 127.0.0.1.
# Run: bash tests/stitch-core.test.sh   (exit 0 = pass)
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
C="$ROOT/.claude/commands"; A="$ROOT/.claude/agents"; H="$ROOT/.claude/hooks"; SK="$ROOT/.claude/skills/ui/stitch-design.md"
PASS=0; FAIL=0
ok()  { echo "  ✓ $1"; PASS=$((PASS+1)); }
bad() { echo "  ✗ FAIL: $1"; FAIL=$((FAIL+1)); }
has() { grep -qF -- "$2" "$1"; }   # has <file> <literal>
TMP="$(mktemp -d)"; SERVER_PID=""
cleanup() { if [ -n "$SERVER_PID" ]; then kill "$SERVER_PID" 2>/dev/null; wait "$SERVER_PID" 2>/dev/null; fi; rm -rf "$TMP"; }
trap cleanup EXIT

echo "── 1. Stitch is the default designer ──"
if grep -qE 'Omit \(default\) = pure-agent|--source=stitch = enrich' "$C/design.md"; then bad "/design still makes the pure-agent path the default"; else ok "/design no longer defaults to the pure-agent path"; fi
has "$C/design.md" 'Omit (default) = Google Stitch, the core designer' && ok "/design: omitting --source means Stitch" || bad "/design does not make Stitch the default"
has "$C/design.md" '--source=wireframe' && ok "/design keeps the text-wireframe path as --source=wireframe" || bad "/design has no --source=wireframe fallback"
has "$C/design.md" 'NEEDS_INPUT: connect Stitch' && ok "/design interactive: Stitch unavailable → NEEDS_INPUT 'connect Stitch'" || bad "/design doesn't stop for 'connect Stitch' interactively"
has "$C/design.md" 'stitch-state.py defer' && ok "/design --auto: Stitch unavailable → screens deferred (no_baseline + queue)" || bad "/design --auto doesn't defer screens when Stitch is down"
if grep -n -- '--source=stitch' "$C/autonomous.md" >/dev/null; then bad "/autonomous still passes the old opt-in --source=stitch"; else ok "/autonomous runs /design with Stitch as the default (no opt-in flag)"; fi
has "$SK" 'Stitch is the designer whenever the `stitch` MCP server is configured' && ok "stitch-design.md states the default" || bad "stitch-design.md doesn't state Stitch is the default"
has "$ROOT/.claude/templates/CLAUDE.md.template" '/stitch <init\|import\|adopt\|request\|sync-back' && ok "CLAUDE.md template lists the new /stitch actions" || bad "CLAUDE.md template still lists the old /stitch actions"

echo "── 2. Approval rules ──"
has "$C/stitch.md" 'stitch-state.py approve <key> --by owner' && ok "/stitch: the owner approves interactively" || bad "/stitch: no owner approval step"
has "$C/stitch.md" 'Approve <key> rev <n>?  [approve] or type an edit prompt' && ok "/stitch: approve-or-edit-prompt loop" || bad "/stitch: no approve/edit loop"
grep -q 'docs/design/stitch/<key>/screenshot.png' "$C/stitch.md" && ok "/stitch shows the owner the local screenshot path" || bad "/stitch never shows the render's local path"
has "$C/stitch.md" '--by design_quality_reviewer' && ok "/stitch --auto: design_quality_reviewer approves" || bad "/stitch has no autonomous approver"
has "$C/autonomous.md" 'stitch-state.py review-list' && ok "/autonomous lists autonomously approved screens for the owner" || bad "/autonomous has no owner-review list"
has "$C/autonomous.md" '## Designs Awaiting Your Review (Google Stitch)' && ok "/autonomous final report carries the owner-review list" || bad "/autonomous final report omits pending design reviews"
has "$A/core/design_quality_reviewer.md" 'RENDER-APPROVAL mode' && ok "design_quality_reviewer has a render-approval mode for autonomous runs" || bad "design_quality_reviewer can't approve renders"
has "$A/core/design_quality_reviewer.md" 'Never APPROVE an import below its fidelity threshold' && ok "design_quality_reviewer never approves a low-fidelity import" || bad "design_quality_reviewer may approve low-fidelity imports"
has "$SK" 'Nothing is normalized or implemented from a render that isn' && ok "skill: nothing is implemented from an unapproved render" || bad "skill lets unapproved renders through"

echo "── 3. import / adopt / request / sync-back ──"
head -12 "$C/stitch.md" | grep -q 'init | import | adopt | request | sync-back' && ok "/stitch action list includes import, adopt, request, sync-back" || bad "/stitch action list lacks the new actions"
for sec in "## import — " "## adopt — " "## request — " "## sync-back — "; do
  has "$C/stitch.md" "$sec" && ok "/stitch has section '$sec'" || bad "/stitch lacks section '$sec'"
done
has "$C/stitch.md" 'stitch-capture.mjs' && has "$C/stitch.md" 'stitch-fidelity.py score' && ok "import captures with Playwright and scores fidelity" || bad "import doesn't capture + score"
has "$C/stitch.md" 'At most 3 corrections' && has "$C/stitch.md" 'import_low_fidelity' && ok "import corrects up to 3 times, then import_low_fidelity" || bad "import lacks the correction limit / low-fidelity status"
has "$C/stitch.md" 'mcp__stitch__list_screens' && ok "adopt maps list_screens to routes" || bad "adopt doesn't use list_screens"
has "$C/stitch.md" '--op sync_back --source deviation' && ok "sync-back records a sync_back revision from accepted deviations" || bad "sync-back doesn't record its revision"
has "$C/hotfix.md" '/stitch request <key>' && ok "/hotfix sends user-visible UI changes to Stitch first" || bad "/hotfix bypasses Stitch"
has "$C/recon.md" '/stitch sync-back' && has "$C/recon.md" '/stitch request <key>' && ok "/recon routes UI drift through Stitch in both directions" || bad "/recon ignores Stitch"
has "$A/core/product_manager.md" 'UI impact (Stitch)' && ok "product_manager CR lists UI impact for Stitch first" || bad "product_manager CRs skip Stitch"
has "$C/plan.md" 'stitch-baseline.md' && ok "/plan records the phase's Stitch baseline list" || bad "/plan has no Stitch baseline list"
has "$C/develop-orchestrator.md" 'stitch-state.py ready --phase' && ok "/develop blocks UI implementation without an approved, current render (pre-Wave 2)" || bad "/develop has no pre-Wave-2 Stitch check"
has "$C/develop-orchestrator.md" '### Wave 4s — Stitch deviations and sync-back' && ok "/develop has the post-review sync-back step" || bad "/develop has no sync-back step"
grep -q 'stitch-state.py' "$C/develop-orchestrator.md" && grep -q 'stitch-state.py stitch-capture.mjs stitch-fidelity.py' "$C/develop-orchestrator.md" && ok "/develop Wave 0c stages the Stitch hooks" || bad "/develop doesn't stage the Stitch hooks"

echo "── 4. Developers consume the render ──"
for t in ui_developer mobile_developer; do
  f="$A/templates/$t.tmpl"
  has "$f" 'stitch_deviations' && ok "$t records stitch_deviations[]" || bad "$t never records deviations"
  has "$f" 'stitch-state.py ready <key>' && ok "$t checks the render is approved and current before building" || bad "$t doesn't check render readiness"
  has "$f" '"stitch_screen"' && has "$f" '"stitch_rev"' && ok "$t manifest names stitch_screen + stitch_rev" || bad "$t manifest lacks stitch_screen/stitch_rev"
  grep -qiE "never (paste|port)" "$f" && ok "$t never pastes Stitch's HTML" || bad "$t may paste Stitch's HTML"
  grep -q 'skills/ui/stitch-design.md' "$f" && ok "$t loads stitch-design.md" || bad "$t doesn't load stitch-design.md"
done
has "$A/core/ux_designer.md" 'Render ref' && ok "ux_designer's Data Element Inventory ties each element to the render" || bad "ux_designer inventory has no Render ref"
has "$A/core/ux_designer.md" 'Only an approved latest revision' && ok "ux_designer normalizes only approved renders" || bad "ux_designer may normalize unapproved renders"
has "$A/core/ui_standards_auditor.md" '## Step 3b — Resolve developer deviations (fix or accept)' && ok "ui_standards_auditor resolves deviations (fix → drift / accept → sync-back)" || bad "ui_standards_auditor doesn't resolve deviations"
has "$A/core/ui_standards_auditor.md" '"op": "sync_back"' && ok "ui_standards_auditor emits sync_back requests" || bad "no sync_back requests from the auditor"

echo "── 5–6. stitch.json schema, writers, gate, fidelity (tests/lib/stitch_cases.py) ──"
[ -f "$ROOT/.claude/skills/ui/stitch-state.schema.json" ] && python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$ROOT/.claude/skills/ui/stitch-state.schema.json" \
  && ok "stitch-state.schema.json exists and is JSON" || bad "stitch-state.schema.json missing or invalid"
if [ -f "$ROOT/tests/lib/stitch_cases.py" ] && [ -f "$H/stitch-state.py" ]; then
  out="$(python3 "$ROOT/tests/lib/stitch_cases.py" 2>&1)"; rc=$?
  printf '%s\n' "$out" | grep -E '✗|──|passed' | sed 's/^/  /'
  [ "$rc" -eq 0 ] && ok "stitch_cases.py: $(printf '%s' "$out" | tail -1)" || bad "stitch_cases.py failed"
else bad "tests/lib/stitch_cases.py or .claude/hooks/stitch-state.py missing"; fi

echo "── 5b. version tracking is documented where it is used ──"
G="$ROOT/docs/STITCH_DESIGN_GUIDE.md"
has "$SK" '### 2.1 Versions: v0.1 as-is, v0.2 improved, v1.0 approved' && has "$SK" 'stitch-state.py diff <key> <vA> <vB>' && ok "stitch-design.md has the version lifecycle, versions and diff" || bad "stitch-design.md lacks the version lifecycle"
has "$SK" '### 6.7 Verified against the real Stitch API (2026-10-01)' && has "$SK" '=w2560' && has "$SK" '**Still unverified:**' && ok "stitch-design.md records the 2026-10-01 live observations and what is unverified" || bad "stitch-design.md lacks the live-API section"
has "$C/stitch.md" 'revise --op adopt --version v0.1' && has "$C/stitch.md" 'stitch-state.py label <key> --version v0.1' && has "$C/stitch.md" 'GEMINI_3_8_FLASH' && ok "/stitch: import/adopt record v0.1, loops label the final result, chart-placeholder check" || bad "/stitch lacks the version / placeholder steps"
has "$G" 'Versions: keep' && has "$G" 'Verified against the real Stitch API (2026-10-01)' && ok "STITCH_DESIGN_GUIDE.md documents versions and the live verification" || bad "STITCH_DESIGN_GUIDE.md lacks versions / live verification"

echo "── 6b. verify-gate.sh check (g) end to end ──"
if grep -q '(g) Stitch design baseline' "$H/verify-gate.sh"; then ok "verify-gate.sh has check (g)"; else bad "verify-gate.sh has no Stitch check"; fi
D="$TMP/gate"; mkdir -p "$D/agent_state/phases/1/ui_developer" "$D/docs/design"
echo '{"phase":1,"required":["documentation_agent"]}' > "$D/agent_state/phases/1/roster.json"
echo '{"agent":"documentation_agent","phase":1,"status":"completed","report":null,"ts":"t"}' > "$D/agent_state/phases/1/execution.jsonl"
echo '{"phase":"1","agent":"ui_developer","screens":[{"route":"/invoices"}]}' > "$D/agent_state/phases/1/ui_developer/manifest.json"
echo '{"schema":"sdlc.stitch-state/v2","projectId":"1","screens":{}}' > "$D/docs/design/stitch.json"
out="$(CLAUDE_PROJECT_DIR="$D" VERIFY_GATE_SKIP_EXEC=1 bash "$H/verify-gate.sh" 1 2>&1)"; rc=$?
[ "$rc" = 2 ] && printf '%s' "$out" | grep -q 'route /invoices changed in phase 1 but has no Stitch screen' \
  && ok "gate BLOCKs a changed route with no Stitch screen" || bad "gate did not block the unbaselined route (rc=$rc)"
rm "$D/docs/design/stitch.json"
out="$(CLAUDE_PROJECT_DIR="$D" VERIFY_GATE_SKIP_EXEC=1 bash "$H/verify-gate.sh" 1 2>&1)"; rc=$?
[ "$rc" = 0 ] && printf '%s' "$out" | grep -q 'Stitch design gate does not apply' && ok "gate is not applicable without stitch.json" || bad "gate without stitch.json: rc=$rc"

echo "── 7. import capture (stitch-capture.mjs) ──"
if [ -f "$H/stitch-capture.mjs" ] && node --check "$H/stitch-capture.mjs" 2>/dev/null; then ok "stitch-capture.mjs parses (node --check)"; else bad "stitch-capture.mjs missing or doesn't parse"; fi
PW="${STITCH_PLAYWRIGHT_DIR:-$ROOT/tests/archetype-compile/ui-packs/web}"
if [ -f "$H/stitch-capture.mjs" ] && [ -d "$PW/node_modules/@playwright/test" ]; then
  PORT="$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])')"
  python3 -m http.server "$PORT" --bind 127.0.0.1 --directory "$ROOT/tests/fixtures/stitch/site" >/dev/null 2>&1 &
  SERVER_PID=$!
  for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do curl -s -o /dev/null "http://127.0.0.1:$PORT/" && break; python3 -c 'import time; time.sleep(0.25)'; done
  out="$(STITCH_PLAYWRIGHT_DIR="$PW" node "$H/stitch-capture.mjs" --base-url "http://127.0.0.1:$PORT" --out "$TMP/cap" --routes /,/orders/,/orders/:id 2>&1)"; rc=$?
  C1="$TMP/cap/orders/desktop/capture.json"; C2="$TMP/cap/orders/mobile/capture.json"
  [ "$rc" = 1 ] && [ -f "$C1" ] && [ -f "$C2" ] && [ -f "$TMP/cap/home/desktop/screenshot.png" ] && [ -f "$TMP/cap/home/mobile/screenshot.png" ] \
    && ok "captured 2 routes × desktop + mobile; the :id route without --param is reported, not guessed" || bad "capture run failed (rc=$rc): $(printf '%s' "$out" | tail -3)"
  python3 - "$C1" "$TMP/cap" <<'PY' && ok "capture.json has the outline (landmarks, h1, buttons, table columns), ARIA, text, tokens; DESIGN.md + index.json written" || bad "capture content incomplete"
import json, os, sys
c = json.load(open(sys.argv[1])); o = c["outline"]
assert {"banner", "navigation", "main"} <= {l["role"] for l in o["landmarks"]}, o["landmarks"]
assert [h["text"] for h in o["headings"]] == ["Orders"]
assert {"Export CSV", "New order"} <= {x["name"] for x in o["controls"] if x["kind"] == "button"}
assert o["tables"][0]["columns"] == ["Order", "Customer", "Status", "Total"] and o["tables"][0]["rows"] == 3
assert "Maria Lopez" in c["text"] and c["status"] == 200 and c["deviceType"] == "DESKTOP"
assert any(t["value"] == "rgb(37, 99, 235)" for t in c["tokens"]["background"]), c["tokens"]["background"]
assert c["aria"] is None or "Export CSV" in c["aria"]
idx = json.load(open(os.path.join(sys.argv[2], "index.json")))
assert len(idx["captures"]) == 4 and len(idx["errors"]) == 2, idx["errors"]
md = open(os.path.join(sys.argv[2], "DESIGN.md")).read()
assert "#2563EB" in md and "Inter" in md and "`8px`" in md, md[:400]
PY
  python3 "$H/stitch-fidelity.py" score --real "$TMP/cap/orders/desktop/screenshot.png" --stitch "$TMP/cap/orders/desktop/screenshot.png" \
    --capture "$C1" --html "$ROOT/tests/fixtures/stitch/site/orders/index.html" >/dev/null \
    && ok "a page scored against its own capture passes the fidelity threshold" || bad "self-score below threshold"
  out="$(STITCH_PLAYWRIGHT_DIR="$PW" node "$H/stitch-capture.mjs" --base-url "http://127.0.0.1:$PORT" --out "$TMP/rec" --routes /orders-recreated/,/ --viewports desktop 2>&1)"
  python3 "$H/stitch-fidelity.py" score --real "$TMP/cap/orders/desktop/screenshot.png" --stitch "$TMP/rec/orders-recreated/desktop/screenshot.png" \
    --capture "$C1" --html "$ROOT/tests/fixtures/stitch/site/orders-recreated/index.html" >/dev/null \
    && ok "a faithful recreation (own markup, font, spacing, colours) passes" || bad "the faithful recreation scored below threshold"
  if python3 "$H/stitch-fidelity.py" score --real "$TMP/cap/orders/desktop/screenshot.png" --stitch "$TMP/rec/home/desktop/screenshot.png" \
    --capture "$C1" --html "$ROOT/tests/fixtures/stitch/site/index.html" >/dev/null; then bad "a different page passed the fidelity threshold"
  else ok "a different page with the same header scores below threshold"; fi
else
  echo "  · SKIP live capture: Playwright not installed at $PW (run: (cd tests/archetype-compile/ui-packs/web && npm ci --ignore-scripts), or set STITCH_PLAYWRIGHT_DIR)"
fi

echo "────────────────────────────────────────────"
echo "stitch-core.test.sh: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
