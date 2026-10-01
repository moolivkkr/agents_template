---
skill: board-hat-senior-dev
description: Board review hat — senior developer. Instructions and examples that are actually correct, build/lint/test gates named, minimal diffs in existing code, fix-agent discipline, never editing tests to pass
version: "1.0"
tags:
  - review
  - board-review
  - development
---

# Hat: senior developer

Follow `protocol.md` in this directory (format, severity, evidence, report-everything). Prefix: `DEV`.

**Your question:** would a strong engineer who followed this agent file to the letter produce
correct, mergeable work in an existing codebase? Where the file is wrong, the agent is wrong.

## Read

- every target agent in full
- its skill packs
- the orchestrator section that spawns it (prompt text included)

## Checklist

1. **Examples are correct.** Every code sample, command and API the file teaches must exist and
   work as shown.
   - Run the ones you can in a scratch directory: compile the snippet, run the command, check the
     flag. Example from the last run: `@axe-core/playwright` has no `injectAxe`.
   - Wrong syntax, nonexistent APIs and version claims you can't verify are findings.
2. **Agent and packs agree.** The agent's own examples must match its packs, and its "✅ CORRECT"
   samples must match the contract they claim to follow.
3. **Build gates are named.** The Definition of Done must name the real commands it runs
   (typecheck, lint, test), taken from the project's commands table. "Make sure it compiles"
   isn't a gate.
4. **Existing code.**
   - Does the agent read before editing, follow existing conventions, keep diffs minimal, and read
     the audit report it's given?
   - Instructions that assume an empty repo are findings.
5. **Fix agents get the same discipline.** Agents spawned to fix review findings need the same
   packs, contracts and gates as the original author, and the fix needs re-testing.
6. **Tests are never weakened to pass.**
   - Any instruction that lets an agent edit a test, mock, fixture or snapshot to match changed
     behaviour must name the spec row that justifies it. Without that, it's a finding.
   - Optimizers must find dead code by static reachability, never by "tests still pass".
7. **Error handling.** Errors must be kept, wrapped with context and returned in the contract's
   shape. Swallowed errors, and "simplify by removing error paths", are findings.
8. **Portability of shell recipes.**
   - BSD vs GNU flags: `sed -i ''`, `grep -P` (macOS has no `-P` in plain bash), `stat -f` vs `-c`.
   - Fail-open exit codes: `cmd | tee` without `pipefail`, `|| true` hiding failures.
   - Test caches: `go test` without `-count=1`.
9. **Language idioms.** In each language the template covers, check the idioms an expert would flag.

## Defect classes the 2026-09-30 run found (check they're still fixed)

- optimizers told to "update test expectation" after cleanup
- no compile gate in canonical Wave 2
- fix agents untyped, with a five-line prompt
- Go tests in a `tests/unit` layout that defeats per-package coverage
