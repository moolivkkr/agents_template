# Commands and versions — one table every agent, CI and the gate read

`impl_guidelines_agent` writes this section into `docs/IMPLEMENTATION_GUIDELINES.md`, and `/init`
confirms it. From then on nobody guesses a command:
- coding agents' build gate;
- every test agent and `test_runner`;
- `ci_cd_agent`'s workflows;
- `deploy.sh`'s migrate/seed jobs;
- `verify-gate.sh` check (e).

They all run exactly these. When one is wrong, fix the table, not the caller.

## Format (exact — it's parsed)

```markdown
## Commands and versions

| Purpose | Command |
|---|---|
| install | npm ci --ignore-scripts |
| build | go build ./... |
| typecheck | go vet ./... |
| lint | golangci-lint run ./... |
| test:unit | gotestsum --junitfile agent_state/phases/$PHASE/junit/unit.xml -- -count=1 -race ./internal/... |
| test:integration | gotestsum --junitfile agent_state/phases/$PHASE/junit/integration.xml -- -count=1 -tags=integration ./... |
| test:ui | npx vitest run --reporter=junit --outputFile=agent_state/phases/$PHASE/junit/ui.xml |
| test:e2e | npx playwright test --reporter=junit |
| test:mobile | maestro test --format junit --output agent_state/phases/$PHASE/junit/mobile.xml .maestro/ |
| migrate | ./bin/app migrate |
| seed | ./bin/app seed |
| run | ./bin/app serve |

| Component | Version |
|---|---|
| Go | 1.27 |
| Node | 22 |
| PostgreSQL | 17 |
```

- Purposes are lowercase and fixed: `install build typecheck lint test:unit test:integration test:ui
  test:e2e test:mobile migrate seed run`, plus any project-specific `x:<name>`. Leave a row out when it
  doesn't apply; don't write "N/A".
- `$PHASE` and `$APP_BASE_URL` are substituted at run time. JUnit output goes under
  `agent_state/phases/$PHASE/junit/` (see `testing/test-results-sidecar.md`).
- **Test commands never retry failures silently.** Set Playwright `retries: 0` locally, and use
  `failOnFlakyTests: true` if CI retries. Go tests run with `-count=1` (no cache) and `-race` where
  cgo allows.
- **Versions** pin the toolchain and the datastores. Dockerfiles, CI (`setup-go`/`setup-node`),
  testcontainers images and the k8s manifests all use the same major versions. `ci_cd_agent` and
  `deployment_agent` read this table instead of choosing their own.

## Machine form

```bash
python3 .claude/hooks/commands-table.py docs/IMPLEMENTATION_GUIDELINES.md --out agent_state/config/verify-commands.json
```

The orchestrator runs this in Wave 0c. The output feeds `verify-gate.sh` check (e): `typecheck`
(falling back to `build`), `lint` and `test` (= `test:unit`) run at the gate, and a non-zero exit
BLOCKs. The full `commands` and `versions` maps are there for every other reader.
