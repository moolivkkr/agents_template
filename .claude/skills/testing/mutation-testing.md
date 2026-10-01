# Mutation testing — do the tests notice when the code is wrong?

Line coverage says a line **ran** during the tests. It doesn't say any test would fail if that line
were wrong. A mutation tool makes small deliberate bugs (mutants) in the code:
- flip `<` to `<=`;
- negate a condition;
- replace a return value with zero;
- delete a call.

It then runs the tests against each mutant. A mutant the tests catch is **killed**. One they don't
catch **survived**, and each survivor is an assertion nobody wrote.

This is the check the 2026-09-30 board review found missing (TEST-06): every tier was gated on counts
and ID presence, and nothing ever observed a test failing against broken code. It complements
red-first (`reproduction-first.md`), which watches one new test fail once.

## Scope: the code changed this phase

Mutation runs are expensive, so run them on changed **source** files only. Exclude tests, generated
code, mocks and migrations:

```bash
P="${PHASE:?}"; BASE="$(cat "agent_state/phases/$P/base_sha")" || exit 1
# git diff on its own line: in a pipe its failure (bad base) is hidden behind grep's exit code,
# and grep -v exits 1 for "no lines left", which is a valid empty scope
CHANGED="$(git diff --name-only --diff-filter=AM "$BASE"..HEAD -- . ':(exclude)agent_state' ':(exclude)docs' ':(exclude).claude')" || exit 1
printf '%s\n' "$CHANGED" \
  | grep -Ev '^$|(_test\.go|\.test\.[jt]sx?|\.spec\.[jt]sx?|(^|/)test_[^/]*\.py|_test\.py|Test\.java|/mocks?/|/generated/|/migrations/)' \
  > "agent_state/phases/$P/mutation_scope.txt" || true
```

## Commands

Use `commands."x:mutation"` from `agent_state/config/verify-commands.json` when the project defines
one (`core/commands-and-versions.md`). Otherwise, use the stack default below and write in the report
that the default was used, with the table row to add. Write the tool's report under
`agent_state/phases/$P/mutation/`.

| Stack | Tool | Changed-files run | Machine-readable output | Built-in floor |
|---|---|---|---|---|
| Go | **gremlins** (`go-gremlins/gremlins`) | `gremlins unleash --diff "$BASE" --output agent_state/phases/$P/mutation/gremlins.json ./...` (tests only mutants inside the diff, and only covered ones) | `--output` JSON | `--threshold-efficacy N` exits 10 below N% killed; `--threshold-mcover N` exits 11 |
| Go (alternative) | go-mutesting (avito-tech fork) | `go-mutesting <changed packages>` | text: `The mutation score is …` | none (check the score yourself) |
| JS / TS | **StrykerJS** | `npx stryker run --mutate "$(paste -sd, agent_state/phases/$P/mutation_scope.txt)" --reporters json,clear-text` | `reports/mutation/mutation.json` (copy it under `mutation/`) | `thresholds.break` in `stryker.config.*` fails the run below it |
| Python | **mutmut** (3.x) | set `[tool.mutmut] paths_to_mutate = [<changed files>]` in `pyproject.toml` for the run, then `mutmut run` | `mutmut results` (survivors), `mutmut show <id>` (diff) | none (check the score yourself) |
| Java / Kotlin | PIT (`pitest-maven` / gradle plugin) | `mvn org.pitest:pitest-maven:mutationCoverage -DtargetClasses=<changed classes> -DoutputFormats=XML,HTML` | `target/pit-reports/mutations.xml` | `-DmutationThreshold=N` |
| Rust | cargo-mutants | `git diff "$BASE"..HEAD > /tmp/phase.diff && cargo mutants --in-diff /tmp/phase.diff` | `mutants.out/outcomes.json` | none (check the score yourself) |

- **Budget:** cap the run at about 20 minutes. Use the tool's worker or timeout options
  (`--workers`, `--timeout-coefficient`, `concurrency`). If the scope is too large, mutate the
  files behind HIGH-priority TC rows first, and say what you skipped.
- **Tests must be green first.** A mutation run over a failing suite measures nothing. Run it after
  the tier passes.
- Run the tool against **committed** code, with the tree clean. Mutation tools edit and restore
  source files, so never run one while another agent is writing to the same tree.

## Report

`agent_state/phases/$P/reports/mutation_report.md`, with `mutation_results.json` beside it:

```json
{"schema": "sdlc.mutation/v1", "tool": "gremlins", "command": "…", "scope_files": 12,
 "killed": 140, "survived": 9, "timed_out": 2, "not_covered": 5, "score": 0.94,
 "floor": null, "verdict": "ADVISORY",
 "survivors": [{"file": "internal/order/total.go", "line": 42, "mutation": "CONDITIONALS_BOUNDARY < → <=",
                "tc_rows": ["TC-UNIT-20102"], "action": "add boundary assertion | equivalent: <reason>"}]}
```

Score is killed / (killed + survived). Timed-out mutants count as killed. Report not-covered
mutants separately: they are a coverage gap, not a weak assertion.

## Acting on survivors

Each survivor points at a behaviour no test pins down:
1. Find the spec row it belongs to (TC ID). Write, or strengthen, the test **named with that ID** so
   it asserts the spec's literal expected value at that boundary. The test must fail against the
   mutant.
2. An **equivalent mutant** (the change can't alter observable behaviour, e.g. mutating a log line)
   gets `action: "equivalent: <why>"`. Don't write a test for it.
3. Never delete or loosen code to make a mutant disappear.

## Policy: advisory first, then a floor

| Stage | When | Effect |
|---|---|---|
| **Advisory** (default) | no floor recorded | `verdict: ADVISORY`. Survivors are listed in `test_results.md` as WARNING for the owning test agent. The gate doesn't read it. |
| **Floor** | a `DECISIONS.md` entry records the floor (e.g. "mutation score ≥ 0.70 on changed files behind HIGH TC rows"), and the command table's `x:mutation` row carries the tool's threshold flag | below the floor: `verdict: FAIL`, and `test_runner` lists it as BLOCKING in `test_results.md` for the owning writer to fix in Wave 5 |

Start advisory. Record the floor once two or three phases of advisory scores show what the codebase
can reach. A floor above what the suite achieves turns into equivalent-mutant arguments, not better
tests.

## Anti-patterns

| Anti-pattern | Why it fails |
|---|---|
| Mutating the whole repo every phase | Hours of runtime; it gets skipped. Mutate the diff. |
| Chasing 100 % | Equivalent mutants make it unreachable; effort goes into arguing, not testing. |
| Adding assertions on implementation details to kill a mutant | It kills the mutant but pins the code, not the behaviour. Assert the spec's outcome. |
| Counting not-covered mutants as survivors | It mixes "no test ran this" with "a test ran it and didn't notice". Report both, separately. |

> Config blocks checked 2026-09-30 (`bash tests/archetype-compile/config-packs/run.sh --live`): 1 bash block: bash -n (macOS bash 3.2.57) + shellcheck 0.11.0; 1 run in fixture scenarios on macOS bash 3.2.57; 1 JSON block parsed.
