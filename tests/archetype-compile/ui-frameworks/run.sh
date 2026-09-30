#!/usr/bin/env bash
# run.sh — compile-check, then run, every code example in the non-React UI framework packs:
#   .claude/skills/frameworks/vue.md      → Vite + Vue 3 project,   vue-tsc --noEmit (strictTemplates), vitest run
#   .claude/skills/frameworks/svelte.md   → SvelteKit project,      svelte-check --fail-on-warnings,     vitest run
#   .claude/skills/frameworks/angular.md  → Angular CLI workspace,  ngc -p (AOT, strictTemplates),       ng test
#
# Each pack's blocks are extracted at run time (extract.py): a block whose first line is `// file: src/…`
# (or `<!-- file: src/… -->`) is written to that path; every other block must have a row in skips.tsv
# with a reason, or the run fails. The envelope types come from api/response-envelope.md and the MSW
# envelope helpers from testing/msw.md, extracted at run time too, so the packs compile against the
# shared packs themselves. Stubs (payload types, i18n, pages a pack doesn't show) live only in stubs*/.
#
# Usage:   bash tests/archetype-compile/ui-frameworks/run.sh [vue] [svelte] [angular]   (default: all)
# Env:     UI_COMPILE_WORKDIR   where projects + node_modules live (default ${TMPDIR:-/tmp}/sdlc-ui-frameworks-compile)
#          UI_COMPILE_SKIP_TESTS=1   type-check only
#          UI_COMPILE_UPDATE_LOCK=1  npm install (not ci) and copy package-lock.json back into the scaffold
# Needs:   node >= 22.12, npm, python3; network for the first install (npm ci --ignore-scripts).
# Exit 0 = every block compiled and every test passed. bash 3.2 compatible.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
WORK="${UI_COMPILE_WORKDIR:-${TMPDIR:-/tmp}/sdlc-ui-frameworks-compile}"
PACKS="$REPO/.claude/skills/frameworks"
SHARED_ENVELOPE="$REPO/.claude/skills/api/response-envelope.md"
SHARED_MSW="$REPO/.claude/skills/testing/msw.md"
if [ "$#" -gt 0 ]; then FRAMEWORKS="$*"; else FRAMEWORKS="vue svelte angular"; fi

RC=0
SUMMARY=""

root_of() { case "$1" in vue) echo src ;; svelte) echo src/lib ;; angular) echo src/app ;; esac; }

check_cmd() {
  case "$1" in
    vue) echo "npx vue-tsc --noEmit -p tsconfig.json" ;;
    svelte) echo "npx svelte-kit sync && npx svelte-check --tsconfig ./tsconfig.json --fail-on-warnings --output human" ;;
    angular) echo "npx ngc -p tsconfig.json" ;;
  esac
}

test_cmd() {
  case "$1" in
    vue | svelte) echo "npx vitest run" ;;
    angular) echo "npx ng test --watch=false" ;;
  esac
}

install_deps() { # dir fw
  local dir="$1" fw="$2" sha
  if [ "${UI_COMPILE_UPDATE_LOCK:-0}" = 1 ]; then
    (cd "$dir" && npm install --ignore-scripts --no-audit --no-fund) || return 1
    cp "$dir/package-lock.json" "$HERE/$fw/package-lock.json"
    return 0
  fi
  [ -f "$dir/package-lock.json" ] || { echo "no package-lock.json for $fw — run with UI_COMPILE_UPDATE_LOCK=1"; return 1; }
  sha="$(shasum "$dir/package-lock.json" | cut -d' ' -f1)"
  if [ "$(cat "$dir/node_modules/.harness-lock-sha" 2>/dev/null)" != "$sha" ]; then
    (cd "$dir" && npm ci --ignore-scripts --no-audit --no-fund) || return 1
    echo "$sha" > "$dir/node_modules/.harness-lock-sha"
  fi
}

run_fw() { # fw
  local fw="$1" dir="$WORK/$1" root log manifest pass=0 fail=0 skipped=0 status=0
  root="$(root_of "$fw")"
  echo "── $fw ─────────────────────────────────────────────"
  mkdir -p "$dir"
  # scaffold config (everything but stubs/) → project root; src/ is rebuilt from scratch every run
  (cd "$HERE/$fw" && find . -path ./stubs -prune -o -type f -print) | while read -r f; do
    mkdir -p "$dir/$(dirname "$f")" && cp "$HERE/$fw/$f" "$dir/$f"
  done
  rm -rf "$dir/src" "$dir/out-tsc"
  [ -d "$HERE/$fw/stubs" ] && cp -R "$HERE/$fw/stubs/." "$dir/"
  mkdir -p "$dir/$root/api" "$dir/$root/security"
  cp "$HERE/stubs-common/i18n.ts" "$dir/$root/i18n.ts"
  cp "$HERE/stubs-common/safe-url.ts" "$dir/$root/security/safe-url.ts"
  python3 "$HERE/extract.py" block --pack "$SHARED_ENVELOPE" --block-prefix "export type ApiSuccess<T>" \
    --out "$dir/$root/api/types.ts" || status=1
  cat "$HERE/stubs-common/payload-types.ts" >> "$dir/$root/api/types.ts"
  python3 "$HERE/extract.py" block --pack "$SHARED_MSW" --block-prefix "// src/mocks/envelope.ts" \
    --out "$dir/$root/mocks/envelope.ts" || status=1

  manifest="$dir/.manifest.tsv"
  local extract_note=""
  python3 "$HERE/extract.py" pack --pack "$PACKS/$fw.md" --dest "$dir" --skips "$HERE/skips.tsv" \
    --manifest "$manifest" || { status=1; extract_note=" · EXTRACTION ERRORS (unchecked or stale blocks, see above)"; }
  [ "$status" -ne 0 ] && [ -z "$extract_note" ] && extract_note=" · SHARED-PACK EXTRACTION FAILED (see above)"

  install_deps "$dir" "$fw" || { echo "INSTALL-FAIL $fw"; RC=1; SUMMARY="$SUMMARY
$fw.md: install failed"; return; }

  log="$dir/.check.log"
  (cd "$dir" && eval "$(check_cmd "$fw")") > "$log" 2>&1
  local check_rc=$?
  [ "$check_rc" -ne 0 ] && { status=1; cat "$log"; }

  # per-block verdict: a CHECKED block FAILs when the checker's output names its file
  while IFS="$(printf '\t')" read -r st where what reason; do
    case "$st" in
      CHECKED)
        if grep -qF "$what" "$log" && grep -F "$what" "$log" | grep -qiE "error|warn"; then
          fail=$((fail + 1)); echo "  FAIL    $where  $what"
        else
          pass=$((pass + 1)); echo "  PASS    $where  $what"
        fi ;;
      SKIPPED) skipped=$((skipped + 1)); echo "  SKIPPED $where  ${what}  — $reason" ;;
    esac
  done < "$manifest"
  if [ "$check_rc" -ne 0 ] && [ "$fail" -eq 0 ]; then
    fail=1; echo "  FAIL    checker exited $check_rc without naming a pack file (see log above)"
  fi

  local tests="not run"
  if [ "${UI_COMPILE_SKIP_TESTS:-0}" != 1 ] && [ "$check_rc" -eq 0 ]; then
    if (cd "$dir" && eval "$(test_cmd "$fw")") > "$dir/.test.log" 2>&1; then
      tests="PASS"
    else
      tests="FAIL"; status=1; cat "$dir/.test.log"
    fi
    grep -E "Tests? +[0-9]+|passed|failed" "$dir/.test.log" | tail -3 | sed 's/^/  /'
  fi

  [ "$fail" -gt 0 ] && status=1
  [ "$status" -ne 0 ] && RC=1
  SUMMARY="$SUMMARY
$fw.md: compiled $pass PASS / $fail FAIL / $skipped skipped · tests: $tests$extract_note"
}

command -v node > /dev/null || { echo "node not found"; exit 1; }
for fw in $FRAMEWORKS; do
  case "$fw" in vue | svelte | angular) run_fw "$fw" ;; *) echo "unknown framework: $fw"; RC=1 ;; esac
done
echo "──────────────────────────────────────────────────"
echo "${SUMMARY#
}"
[ "$RC" -eq 0 ] && echo "UI FRAMEWORK PACKS: ALL EXAMPLES COMPILE AND PASS" || echo "UI FRAMEWORK PACKS: FAILURES"
exit "$RC"
