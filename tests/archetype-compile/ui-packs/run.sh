#!/usr/bin/env bash
# Compile-check, and where possible run, every TS/JS sample in the React / Next.js / React Native / UI packs:
#   .claude/skills/frameworks/{react,nextjs,tanstack-query,react-native,react-native-app-patterns}.md
#   .claude/skills/ui/*.md                      (ui/archetypes/ has its own harness: ../typescript)
#   .claude/skills/testing/{msw,playwright,react-native-testing-library,detox,appium-mobile,
#                           mobile-testing-strategy,test-case-generation,test-case-traceability}.md
#
#   bash tests/archetype-compile/ui-packs/run.sh                  # the gate: every unit, every block, every run
#   bash tests/archetype-compile/ui-packs/run.sh --no-run         # type-check only
#   bash tests/archetype-compile/ui-packs/run.sh --unit msw       # one unit (repeatable); --list shows blocks + units
#   bash tests/archetype-compile/ui-packs/run.sh --project rn     # one project: web | rn | device
#   bash tests/archetype-compile/ui-packs/run.sh --keep           # keep <project>/.units/ for debugging
#
# Four npm projects, each pinned by its package-lock.json (installed with `npm ci --ignore-scripts`, repeated
# only when the lockfile changes; node_modules is git-ignored):
#   web/      TypeScript 7.0.2, React 19.3, Next.js 16.3, TanStack Query 5.104, RHF 7.89, Zod 4.6, MSW 3.0.1,
#             Vitest 5.0.3 + jsdom + Testing Library, Playwright 1.63 (+ axe), radix-ui, sonner, lucide-react, axios,
#             Tailwind CSS 4.3 (@tailwindcss/postcss) + shadcn 4.21 (its tailwind.css) for the theme probe
#   rn/       React Native 0.87.1 with the React 19.2.3 / Jest 29.7 / Babel 7 its app template pins, RNTL 14.0.1,
#             msw 2.15.0, FlashList 2.3.2, TS 7.0.2
#   rn-msw3/  the same with msw 3.0.1 + the two Babel plugins the RNTL pack's MSW 3 variant needs
#   device/   Detox 20.51.4 and WebdriverIO 9.32 (Appium) types — TYPE-CHECK ONLY: no simulator, emulator or
#             Appium server is started
# Playwright runs on the system Google Chrome (channel "chrome"): no browser download. Without Chrome the
# playwright unit fails; run --project rn / device, or --no-run, on such hosts.
#
# Exit 0 = every block is checked or skipped with a reason, every block count matches units.FILES, every unit
# type-checks, and every test / build / e2e run passes. Needs node >= 22.13 (RN 0.87), npm, python3 >= 3.8.
# Not part of tests/run-all.sh (it needs the npm registry once); tests/archetype-ui-packs-inventory.test.sh is.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

command -v node >/dev/null || { echo "run.sh: node is required" >&2; exit 2; }
command -v npm >/dev/null || { echo "run.sh: npm is required" >&2; exit 2; }
command -v python3 >/dev/null || { echo "run.sh: python3 is required" >&2; exit 2; }

for project in web rn rn-msw3 device; do
  cd "$DIR/$project"
  want="$(shasum -a 256 package-lock.json 2>/dev/null || sha256sum package-lock.json)"
  want="${want%% *}"
  have="$(cat node_modules/.package-lock.sha256 2>/dev/null || true)"
  if [ "$want" != "$have" ]; then
    echo "run.sh: installing pinned dependencies for $project (npm ci --ignore-scripts)…"
    npm ci --ignore-scripts --no-audit --no-fund --loglevel=error
    printf '%s' "$want" > node_modules/.package-lock.sha256
  fi
done

cd "$DIR"
exec python3 "$DIR/harness.py" "$@"
