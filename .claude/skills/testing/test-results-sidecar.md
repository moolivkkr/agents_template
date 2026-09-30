# Test results sidecar — the only test evidence the phase gate accepts

Every agent that runs tests (`unit_test_agent`, `integration_test_agent`, `ui_test_agent`,
`mobile_test_agent`, `e2e_orchestrator`, `mobile_e2e_orchestrator`, `acceptance_test_agent`,
`performance_agent`, `test_runner`) writes a **JSON sidecar** next to its markdown report. The same goes
for `scripts/k8s/deploy.sh` and `spec_test_reconciler`: the report path it logs in `execution.jsonl` is
`reports/<name>.md`, and the sidecar is `reports/<name>.json`.

`.claude/hooks/verify-gate.sh` reads the sidecar, never the prose. A test agent whose report has no
sidecar BLOCKs the gate, and so does prose that says "all passed" beside a sidecar that doesn't.

## Produce it with code, not by hand

Run the suite with a JUnit XML reporter, then convert. **Write the JUnit XML under
`agent_state/phases/$PHASE/junit/`.** That path is excluded from `code_sha`. Report files written inside
the source tree make it "dirty", and the gate then rejects your evidence.

```bash
python3 .claude/hooks/junit-to-sidecar.py --tier unit --command "<the command you ran>" --exit-code $RC \
  --out agent_state/phases/$PHASE/reports/unit_results.json  path/to/junit*.xml
```

| Stack | JUnit reporter |
|---|---|
| Go | `gotestsum --junitfile unit.xml -- -count=1 -race ./...` (or `go test -json … \| go-junit-report`) |
| Jest / Vitest | `jest --ci --reporters=default --reporters=jest-junit` · `vitest run --reporter=junit --outputFile=unit.xml` |
| pytest | `pytest --junitxml=unit.xml` |
| Playwright | `reporter: [['junit', { outputFile: 'e2e.xml' }]]`, with `failOnFlakyTests: true` in CI |
| Maestro | `maestro test --format junit --output mobile.xml .maestro/` |
| Rust | `cargo nextest run --profile ci` (JUnit enabled in `.config/nextest.toml`) |
| k6 / load | `performance_agent` writes the sidecar directly from k6's `--summary-export` (see its agent file) |

Hand-written sidecars are allowed only where no runner exists: acceptance use cases run by the agent,
and deploys (written by `deploylib.py`). Both must still carry `code_sha` and per-case verdicts.

## Schema — `sdlc.test-results/v1`

```json
{
  "schema": "sdlc.test-results/v1",
  "tier": "unit|integration|ui|e2e|mobile|acceptance|performance|a11y|deploy|tc-inventory|all",
  "verdict": "PASS|FAIL|ERROR|BLOCKED",
  "total": 42, "passed": 41, "failed": 1, "skipped": 0, "flaky": 0,
  "code_sha": "<full sha of the last commit touching code — see below>",
  "dirty": false,
  "env": "local|dev|qa", "base_url": "http://app-qa.localhost:18080",
  "command": "gotestsum --junitfile unit.xml -- -count=1 ./...", "exit_code": 0,
  "cases": [ {"name": "TC-API-001 creates an order", "verdict": "PASS|FAIL|SKIPPED|BLOCKED|UNTESTED",
              "ids": ["TC-API-001"], "priority": "HIGH|MEDIUM|LOW"} ],
  "quarantined": [ {"name": "…", "issue": "#123", "expires": "2026-10-15"} ],
  "ts": "2026-09-30T12:00:00Z"
}
```

### What the gate BLOCKs on

| Condition | Why |
|---|---|
| no sidecar, or `schema` missing | prose isn't evidence |
| `verdict` ≠ `PASS` | runner crashed (`ERROR`), tests failed, or the tier couldn't run (`BLOCKED`) |
| `total` = 0 | nothing ran |
| `failed` > 0 or `flaky` > 0 | a test that passes only on retry is a failing test ([flake policy](#flakes)) |
| a `cases[]` entry with priority HIGH or MEDIUM and verdict FAIL / BLOCKED / UNTESTED | acceptance and TC coverage are per case, not per suite |
| `quarantined[]` entry past `expires`, or without an `issue` | quarantine is temporary and tracked |
| `code_sha` ≠ the repo's current code sha, or `dirty` = true (explicit gate only) | the evidence describes different code than the code being gated |

### `code_sha` — which commit the evidence belongs to

The last commit that changed code, ignoring the paths that change with every wave:

```bash
git log -1 --format=%H -- . ':(exclude)agent_state' ':(exclude)docs' ':(exclude).claude' ':(exclude)deploy/k8s/overlays'
```

`dirty` is true when `git status --porcelain` on the same pathspec is non-empty. **Commit before you run
the suite you report.** Evidence from uncommitted code can't be bound to anything.

## Flakes

- A test that fails and then passes on retry is **FLAKY**. It counts in `flaky`, and flaky > 0 fails the
  gate.
- Fix the cause: shared state, time, ordering, unawaited async, or selectors that race the UI.
- If a fix needs longer than the phase, quarantine the test. Add it to `quarantined[]` with an issue
  link and an `expires` date no more than 14 days out, and exclude it from the run. When the date
  passes, the gate blocks again.
- Never raise retries, sleep longer, or loosen assertions to get a green run. The test-diff check
  (`tc-inventory.py --diff-base`) flags new skips and removed assertions.
