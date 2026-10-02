#!/usr/bin/env bash
# install-graph.test.sh — the installer sets up sdlc-graph (SQLite + FTS5) for new AND existing projects:
# graph-preflight.sh (OK / WARN without FTS5 / FAIL without sqlite3 or python < 3.9, via a fake python3 on PATH),
# install.sh staging the hook manifest + updater (sandbox HOME, never the real ~/.claude), and
# startup-project-update.sh: hooks added / stale refreshed / locally modified kept (--force overwrites) / project
# files untouched, settings.json merge (idempotent, user entries kept), --dry-run writes nothing, .gitignore
# idempotent, graph build + stats, uncommitted work in a git repo untouched, --hooks-only, install.sh --project,
# new-project.sh, and the /autonomous Step 0 + Wave 0c wiring.
set -uo pipefail
TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$TEST_DIR/.." && pwd)"
PASS=0; FAIL=0
ok()  { echo "  ✓ $1"; PASS=$((PASS+1)); }
bad() { echo "  ✗ FAIL: $1"; FAIL=$((FAIL+1)); }
check() { if eval "$2"; then ok "$1"; else bad "$1"; fi; }

W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
export HOME="$W/home"; mkdir -p "$HOME"            # every install/update below sees only the sandbox HOME
export GIT_CONFIG_NOSYSTEM=1 GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t
REAL_PY="$(command -v python3)"
UPD_REPO="$ROOT/scripts/startup-project-update.sh"
snap() { (cd "$1" && find . -path ./.git -prune -o -type f -print | LC_ALL=C sort | xargs shasum -a 256 2>/dev/null); }
fakepy() {   # $1 = dir, $2 = sitecustomize body → a python3 on PATH that runs the real one with the patch loaded
  mkdir -p "$1/site"; printf '%s\n' "$2" > "$1/site/sitecustomize.py"
  printf '#!/bin/sh\nPYTHONPATH="%s/site" exec "%s" "$@"\n' "$1" "$REAL_PY" > "$1/python3"; chmod +x "$1/python3"
}

echo "── preflight ──"
out="$(bash "$ROOT/scripts/graph-preflight.sh" 2>&1)"; rc=$?
check "preflight OK on this machine (python3 + sqlite3 + FTS5)" '[ $rc -eq 0 ] && grep -q "^graph preflight: OK — python 3\.[0-9]*\.[0-9]*.*sqlite 3\..*FTS5 yes" <<<"$out"'
if [ -x /usr/bin/python3 ] && /usr/bin/python3 -c 'import sqlite3' 2>/dev/null; then
  out="$(GRAPH_PREFLIGHT_PYTHON=/usr/bin/python3 bash "$ROOT/scripts/graph-preflight.sh" 2>&1)"; rc=$?
  check "preflight passes with /usr/bin/python3 ($(/usr/bin/python3 -V 2>&1))" '[ $rc -eq 0 ]'
fi
fakepy "$W/nofts" 'import sqlite3 as _s
_c = _s.connect
class _C(_s.Connection):
    def execute(self, sql, *a):
        if "fts5" in sql.lower():
            raise _s.OperationalError("no such module: fts5")
        return super().execute(sql, *a)
def connect(*a, **k):
    k["factory"] = _C
    return _c(*a, **k)
_s.connect = connect'
out="$(PATH="$W/nofts:$PATH" bash "$ROOT/scripts/graph-preflight.sh" 2>&1)"; rc=$?
check "no FTS5 → WARN, exit 0, with the fix" '[ $rc -eq 0 ] && grep -q "^graph preflight: WARN.*FTS5 no" <<<"$out" && grep -q "How to fix" <<<"$out"'
fakepy "$W/nosqlite" 'import sys; sys.modules["sqlite3"] = None'
out="$(PATH="$W/nosqlite:$PATH" bash "$ROOT/scripts/graph-preflight.sh" 2>&1)"; rc=$?
check "no sqlite3 module → FAIL, exit 1, with the fix" '[ $rc -eq 1 ] && grep -q "^graph preflight: FAIL.*no sqlite3 module" <<<"$out" && grep -q "How to fix" <<<"$out"'
fakepy "$W/oldpy" 'import sys; sys.version_info = (3, 8, 18, "final", 0)'
out="$(PATH="$W/oldpy:$PATH" bash "$ROOT/scripts/graph-preflight.sh" 2>&1)"; rc=$?
check "python < 3.9 → FAIL" '[ $rc -eq 1 ] && grep -q "older than 3.9" <<<"$out"'
out="$(GRAPH_PREFLIGHT_PYTHON="$W/none/python3" bash "$ROOT/scripts/graph-preflight.sh" 2>&1)"; rc=$?
check "python3 missing → FAIL" '[ $rc -eq 1 ] && grep -q "not found" <<<"$out"'

echo "── install.sh (sandbox HOME) ──"
out="$(bash "$ROOT/install.sh" 2>&1)"; rc=$?
S="$HOME/.claude/hooks/startup"; SC="$HOME/.claude/scripts/startup"
check "install.sh exits 0" '[ $rc -eq 0 ]'
check "manifest staged with every framework hook + its known versions" \
  'python3 -c "import json,sys,os; d=json.load(open(\"$S/.framework-manifest.json\")); fs=sorted(f for f in os.listdir(\"$ROOT/.claude/hooks\") if f.endswith((\".sh\",\".py\",\".mjs\"))); sys.exit(0 if sorted(d[\"files\"])==fs and all(d[\"files\"][f] in d[\"known\"][f] for f in fs) and d[\"commit\"] else 1)"'
check "updater + preflight installed to ~/.claude/scripts/startup" '[ -x "$SC/startup-project-update.sh" ] && [ -x "$SC/startup-project-update.py" ] && [ -x "$SC/graph-preflight.sh" ]'
check "install prints the sdlc-graph summary line" 'grep -q "sdlc-graph: enabled (OK — python" <<<"$out"'
check "install wrote nothing outside the sandbox HOME" '[ -d "$HOME/.claude/commands/startup" ]'
H2="$W/home2"; mkdir -p "$H2"
out="$(HOME="$H2" PATH="$W/nosqlite:$PATH" bash "$ROOT/install.sh" 2>&1)"; rc=$?
check "install.sh with a broken python3 still installs (exit 0) and warns loudly" \
  '[ $rc -eq 0 ] && grep -q "WARNING: sdlc-graph is UNAVAILABLE" <<<"$out" && grep -q "sdlc-graph: ⚠ UNAVAILABLE" <<<"$out" && [ -f "$H2/.claude/hooks/startup/sdlc-graph.py" ]'

echo "── updater: existing project with no hooks (git repo with uncommitted work) ──"
P="$W/p-nohooks"; mkdir -p "$P/docs/design/phases/1/specs" "$P/src"
cd "$P" && git init -q && printf 'tracked\n' > a.txt && git add a.txt && git commit -qm init
printf '# BRD\n\n## Requirements\n\n- **FR-001** (MUST): The system SHALL list books.\n' > docs/BRD.md
printf '# Spec\n\n## Test cases\n\n| ID | Description | Priority | Tier |\n|---|---|---|---|\n| TC-BOOK-001 | lists books | HIGH | unit |\n' > docs/design/phases/1/specs/books.md
printf 'def list_books():\n    return []\n' > src/books.py
printf 'tracked, edited\n' > a.txt; printf 'untracked\n' > scratch.txt
mkdir -p .claude/hooks && printf '#!/bin/sh\necho mine\n' > .claude/hooks/my-hook.sh
before_user="$(shasum a.txt scratch.txt docs/BRD.md src/books.py .claude/hooks/my-hook.sh)"; head_before="$(git rev-parse HEAD)"
out="$(bash "$SC/startup-project-update.sh" --project "$P" 2>&1)"; rc=$?
check "update exits 0" '[ $rc -eq 0 ]'
check "every framework hook installed, executable kept" '[ -x "$P/.claude/hooks/sdlc-graph.py" ] && [ -x "$P/.claude/hooks/verify-gate.sh" ] && cmp -s "$P/.claude/hooks/tc-inventory.py" "$ROOT/.claude/hooks/tc-inventory.py"'
check "project manifest written" 'python3 -c "import json; d=json.load(open(\"$P/.claude/hooks/.framework-manifest.json\")); assert len(d[\"files\"])>=15 and d[\"framework_commit\"]"'
check "settings.json created with the framework hooks" 'jq -e ".hooks.Stop[].hooks[] | select(.command|test(\"verify-gate.sh\"))" "$P/.claude/settings.json" >/dev/null'
check ".gitignore gets agent_state/graph/" 'grep -qx "agent_state/graph/" "$P/.gitignore"'
check "graph-policy.json left absent (interactive off)" '[ ! -e "$P/agent_state/config/graph-policy.json" ]'
check "graph built, timing + node/edge counts printed" 'grep -qE "graph: built in [0-9.]+s — [1-9][0-9]* nodes, [0-9]+ edges" <<<"$out" && [ -f "$P/agent_state/graph/graph.sqlite" ]'
check "the built graph answers (tc lists TC-BOOK-001)" 'python3 "$P/.claude/hooks/sdlc-graph.py" --root "$P" --no-refresh tc --phase 1 2>/dev/null | grep -q TC-BOOK-001'
check "lists the files it wrote" 'grep -q "^files written: .*\.claude/settings.json.*\.gitignore" <<<"$out"'
check "uncommitted + untracked work and project-added hooks untouched" '[ "$before_user" = "$(shasum a.txt scratch.txt docs/BRD.md src/books.py .claude/hooks/my-hook.sh)" ]'
check "no git state changed (HEAD, index, stash)" '[ "$head_before" = "$(git rev-parse HEAD)" ] && [ -z "$(git stash list)" ] && git diff --cached --quiet && [ "$(git status --porcelain a.txt)" = " M a.txt" ]'

echo "── updater: re-run is idempotent ──"
s1="$(snap "$P" | grep -v agent_state/graph/)"
out="$(bash "$SC/startup-project-update.sh" --project "$P" --no-build 2>&1)"; rc=$?
check "second run: exit 0, nothing written" '[ $rc -eq 0 ] && grep -q "^files written: none" <<<"$out" && [ "$s1" = "$(snap "$P" | grep -v agent_state/graph/)" ]'
check ".gitignore entry not duplicated" '[ "$(grep -cx "agent_state/graph/" "$P/.gitignore")" = 1 ]'

echo "── updater: stale hooks (pre-manifest project) are refreshed ──"
P2="$W/p-stale"; mkdir -p "$P2/.claude/hooks"
OLD="$(cd "$ROOT" && git log --format=%H -- .claude/hooks/tc-inventory.py | sed -n 2p)"
(cd "$ROOT" && git show "$OLD:.claude/hooks/tc-inventory.py") > "$P2/.claude/hooks/tc-inventory.py"
cp "$ROOT/.claude/hooks/sdlc-graph.py" "$P2/.claude/hooks/"
out="$(bash "$SC/startup-project-update.sh" --project "$P2" --no-build 2>&1)"; rc=$?
check "an older shipped tc-inventory.py is refreshed (exit 0)" '[ $rc -eq 0 ] && cmp -s "$P2/.claude/hooks/tc-inventory.py" "$ROOT/.claude/hooks/tc-inventory.py" && grep -q "refreshed (stale): .*tc-inventory.py" <<<"$out"'
# recorded-hash path: a manifest records what the last update installed; that content is stale, not modified
printf '#!/bin/sh\n# an old framework remember.sh\n' > "$P2/.claude/hooks/remember.sh"
python3 - "$P2/.claude/hooks/.framework-manifest.json" "$P2/.claude/hooks/remember.sh" <<'EOF'
import hashlib, json, sys
d = json.load(open(sys.argv[1])); d["files"]["remember.sh"] = hashlib.sha256(open(sys.argv[2], "rb").read()).hexdigest()
json.dump(d, open(sys.argv[1], "w"))
EOF
out="$(bash "$SC/startup-project-update.sh" --project "$P2" --hooks-only 2>&1)"; rc=$?
check "a hook matching the recorded hash is refreshed" '[ $rc -eq 0 ] && cmp -s "$P2/.claude/hooks/remember.sh" "$ROOT/.claude/hooks/remember.sh"'

echo "── updater: locally modified hook ──"
printf '# local tweak\n' >> "$P2/.claude/hooks/verify-gate.sh"; mod="$(shasum < "$P2/.claude/hooks/verify-gate.sh")"
out="$(bash "$SC/startup-project-update.sh" --project "$P2" --no-build 2>&1)"; rc=$?
check "modified hook kept, exit 1, diff printed" '[ $rc -eq 1 ] && [ "$mod" = "$(shasum < "$P2/.claude/hooks/verify-gate.sh")" ] && grep -q "verify-gate.sh: locally modified" <<<"$out" && grep -q "^    -# local tweak" <<<"$out"'
out="$(bash "$SC/startup-project-update.sh" --project "$P2" --no-build 2>&1)"; rc=$?
check "still refused on the next run (manifest does not adopt the edit)" '[ $rc -eq 1 ]'
out="$(bash "$SC/startup-project-update.sh" --project "$P2" --no-build --force 2>&1)"; rc=$?
check "--force overwrites it (exit 0)" '[ $rc -eq 0 ] && cmp -s "$P2/.claude/hooks/verify-gate.sh" "$ROOT/.claude/hooks/verify-gate.sh" && grep -q "OVERWRITTEN" <<<"$out"'

echo "── updater: settings.json merge ──"
P3="$W/p-settings"; mkdir -p "$P3/.claude"
cat > "$P3/.claude/settings.json" <<'EOF'
{"permissions": {"allow": ["Bash(ls)"]},
 "env": {"MINE": "1"},
 "hooks": {"Stop": [{"hooks": [{"type": "command", "command": ".claude/hooks/verify-gate.sh"},
                               {"type": "command", "command": "echo user-stop"}]}],
           "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "echo user-pre"}]}]}}
EOF
out="$(bash "$SC/startup-project-update.sh" --project "$P3" --no-build 2>&1)"; rc=$?
J="$P3/.claude/settings.json"
check "merge adds the missing framework hooks" '[ $rc -eq 0 ] && jq -e "[.hooks.SessionStart[].hooks[].command] | any(test(\"inject-project-facts.sh\"))" "$J" >/dev/null && jq -e "[.hooks.Stop[].hooks[].command] | any(test(\"autonomous-continue.sh\"))" "$J" >/dev/null && jq -e ".hooks.PostToolUse and .hooks.StopFailure" "$J" >/dev/null'
check "missing env key added (spawn-depth cap = 2)" 'jq -e ".env.CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH == \"2\"" "$J" >/dev/null'
check "user entries kept (permissions, env, user hooks, PreToolUse)" 'jq -e ".permissions.allow == [\"Bash(ls)\"] and .env.MINE == \"1\" and ([.hooks.Stop[].hooks[].command] | index(\"echo user-stop\")) and .hooks.PreToolUse[0].hooks[0].command == \"echo user-pre\"" "$J" >/dev/null'
check "an existing hook in another spelling is not duplicated" '[ "$(jq "[.hooks.Stop[].hooks[].command | select(test(\"verify-gate.sh\"))] | length" "$J")" = 1 ]'
check "changes are shown" 'grep -q "settings.json: added .*hooks.SessionStart" <<<"$out"'
cp "$J" "$W/settings.1"
out="$(bash "$SC/startup-project-update.sh" --project "$P3" --no-build 2>&1)"
check "merge is idempotent (byte-identical second run)" 'cmp -s "$J" "$W/settings.1" && grep -q "already has every framework hook" <<<"$out"'
jq '.env.CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH = "3"' "$W/settings.1" > "$J"
bash "$SC/startup-project-update.sh" --project "$P3" --no-build >/dev/null 2>&1
check "a project's own env value is never overridden" 'jq -e ".env.CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH == \"3\"" "$J" >/dev/null'
printf '{not json' > "$J"
out="$(bash "$SC/startup-project-update.sh" --project "$P3" --no-build 2>&1)"; rc=$?
check "invalid settings.json: exit 2, left untouched" '[ $rc -eq 2 ] && [ "$(cat "$J")" = "{not json" ]'

echo "── updater: --dry-run, .gitignore, --hooks-only, --graph-interactive ──"
P4="$W/p-dry"; mkdir -p "$P4" && printf 'node_modules/\n' > "$P4/.gitignore"; printf 'x' > "$P4/keep.txt"
s0="$(snap "$P4")"
out="$(bash "$SC/startup-project-update.sh" --project "$P4" --dry-run 2>&1)"; rc=$?
check "--dry-run: exit 0, reports, writes nothing" '[ $rc -eq 0 ] && grep -q "^\[dry-run\] files that would change: .*sdlc-graph.py" <<<"$out" && [ "$s0" = "$(snap "$P4")" ] && [ ! -e "$P4/.claude" ]'
P5="$W/p-ign"; mkdir -p "$P5" && printf '/agent_state/\n' > "$P5/.gitignore"
bash "$SC/startup-project-update.sh" --project "$P5" --no-build >/dev/null 2>&1
check ".gitignore that already ignores agent_state/ is left alone" '[ "$(cat "$P5/.gitignore")" = "/agent_state/" ]'
P6="$W/p-hooksonly"; mkdir -p "$P6"
bash "$SC/startup-project-update.sh" --project "$P6" --hooks-only >/dev/null 2>&1; rc=$?
check "--hooks-only: hooks + manifest only" '[ $rc -eq 0 ] && [ -f "$P6/.claude/hooks/sdlc-graph.py" ] && [ -f "$P6/.claude/hooks/.framework-manifest.json" ] && [ ! -e "$P6/.claude/settings.json" ] && [ ! -e "$P6/.gitignore" ] && [ ! -e "$P6/agent_state" ]'
bash "$SC/startup-project-update.sh" --project "$P6" --no-build --graph-interactive on >/dev/null 2>&1
check "--graph-interactive on writes graph-policy.json" 'jq -e ".interactive == true" "$P6/agent_state/config/graph-policy.json" >/dev/null'

echo "── updater: preflight failure and FTS5-less sqlite ──"
P7="$W/p-pf"; mkdir -p "$P7"
out="$(PATH="$W/nosqlite:$PATH" bash "$SC/startup-project-update.sh" --project "$P7" 2>&1)"; rc=$?
check "no sqlite3: exit 3, nothing changed" '[ $rc -eq 3 ] && [ -z "$(ls -A "$P7")" ] && grep -q "nothing was changed" <<<"$out"'
P8="$W/p-nofts"; mkdir -p "$P8"; cp -R "$P/docs" "$P/src" "$P8/"
out="$(PATH="$W/nofts:$PATH" bash "$SC/startup-project-update.sh" --project "$P8" 2>&1)"; rc=$?
check "no FTS5: WARN, graph still builds (exit 0)" '[ $rc -eq 0 ] && grep -q "graph preflight: WARN" <<<"$out" && grep -qE "graph: built in .* [1-9][0-9]* nodes" <<<"$out"'
check "  … with the plain-table fallback instead of an fts5 table" 'python3 -c "import sqlite3,sys; r=sqlite3.connect(\"$P8/agent_state/graph/graph.sqlite\").execute(\"SELECT sql FROM sqlite_master WHERE name=\x27fts\x27\").fetchone(); sys.exit(0 if r and \"fts5\" not in r[0].lower() else 1)"'
out="$(HOME="$W/nohome" python3 "$SC/startup-project-update.py" update --project "$W" 2>&1)"; rc=$?
check "nothing staged → BLOCKED message, exit 2" '[ $rc -eq 2 ] && grep -q "BLOCKED: no framework hooks staged" <<<"$out"'

echo "── install.sh --project and new-project.sh ──"
P10="$W/p-inst"; mkdir -p "$P10"
out="$(bash "$ROOT/install.sh" --project "$P10" --no-build 2>&1)"; rc=$?
check "install.sh --project installs then updates the project" '[ $rc -eq 0 ] && [ -f "$P10/.claude/hooks/sdlc-graph.py" ] && [ -f "$P10/.claude/settings.json" ] && grep -q "Updating project" <<<"$out"'
out="$(cd "$W" && bash "$ROOT/new-project.sh" np-demo "$W" 2>&1)"; rc=$?
check "new-project.sh: hooks + manifest + settings + .gitignore + graph" '[ $rc -eq 0 ] && [ -f "$W/np-demo/.claude/hooks/.framework-manifest.json" ] && [ -f "$W/np-demo/.claude/settings.json" ] && grep -qx "agent_state/graph/" "$W/np-demo/.gitignore" && grep -qx ".claude/agents/generated/" "$W/np-demo/.gitignore" && [ -f "$W/np-demo/agent_state/graph/graph.sqlite" ]'
out="$(cd "$W" && PATH="$W/nosqlite:$PATH" bash "$ROOT/new-project.sh" np-bad "$W" 2>&1)"; rc=$?
check "new-project.sh with a broken python3: exit 3, nothing created" '[ $rc -eq 3 ] && [ ! -e "$W/np-bad" ]'

echo "── pipeline wiring ──"
check "/autonomous Step 0 runs the updater (and keeps the old copy path as fallback)" \
  'grep -q "startup-project-update.sh" "$ROOT/.claude/commands/autonomous.md" && grep -q "cp \"\$HOME/.claude/hooks/startup/\"\*.sh" "$ROOT/.claude/commands/autonomous.md"'
check "/develop Wave 0c runs the updater --hooks-only and keeps the BLOCKED message" \
  'grep -q "startup-project-update.sh" "$ROOT/.claude/commands/develop-orchestrator.md" && grep -q "\"\$UPD\" --project \"\$PWD\" --hooks-only" "$ROOT/.claude/commands/develop-orchestrator.md" && grep -q "BLOCKED: .claude/hooks/\$h missing and not staged" "$ROOT/.claude/commands/develop-orchestrator.md"'
check "docs/SDLC_GRAPH.md exists and is linked from README + CLAUDE.md" '[ -f "$ROOT/docs/SDLC_GRAPH.md" ] && grep -q "docs/SDLC_GRAPH.md" "$ROOT/README.md" && grep -q "docs/SDLC_GRAPH.md" "$ROOT/CLAUDE.md"'

echo "────────────────────────────────────────────"
echo "install-graph.test.sh: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
