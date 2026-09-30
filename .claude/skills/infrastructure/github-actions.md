# GitHub Actions patterns for reliable CI/CD pipelines.

CI runs **the same commands** as `test_runner` and the phase gate: the rows of IMPLEMENTATION_GUIDELINES
`## Commands and versions` (`~/.claude/skills/core/commands-and-versions.md`), verbatim. Toolchain and
service versions come from that table too — `<PostgreSQL>` below stands for its value. A workflow
never names a version or a test flag the table doesn't.

## CI Workflow Structure
```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5          # or setup-node / setup-python
        with:
          go-version-file: go.mod          # the toolchain file the versions table names; never a literal
          cache: true                      # keyed on go.sum
      - run: <commands.lint>               # e.g. golangci-lint run ./...
      - run: <commands.typecheck>

  test:
    needs: lint
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:<PostgreSQL>-alpine   # the versions table's major — same as testcontainers and k8s
        env:
          POSTGRES_USER: app
          POSTGRES_PASSWORD: test
          POSTGRES_DB: app_test              # the database the tests connect to must exist
        ports:
          - 5432:5432                        # without this, localhost:5432 is unreachable from the job's steps
        options: >-
          --health-cmd "pg_isready -U app -d app_test"
          --health-interval 5s
          --health-timeout 5s
          --health-retries 10
    env:
      PHASE: ci
      DATABASE_URL: postgres://app:test@localhost:5432/app_test?sslmode=disable
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with:
          go-version-file: go.mod
          cache: true
      - run: mkdir -p agent_state/phases/ci/junit
      - run: <commands["test:unit"]>         # e.g. gotestsum --junitfile … -- -count=1 -race ./internal/...
      - run: <commands["test:integration"]>  # e.g. gotestsum --junitfile … -- -count=1 -tags=integration ./...
      - uses: actions/upload-artifact@v4
        if: always()                         # keep results for passing and failing runs
        with:
          name: junit
          path: agent_state/phases/ci/junit/

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: <commands.build>
      - name: Build Docker image
        run: docker build --build-arg GIT_SHA=${GITHUB_SHA::12} -t myapp:${GITHUB_SHA::12} .
```
Replace each `<commands.X>` with the table's row verbatim when generating the workflow.

## Caching Strategy
```yaml
# setup-go / setup-node have built-in caching keyed on the lockfile (go.sum, package-lock.json).
# For anything else: key on OS + lockfile hash.
key: ${{ runner.os }}-<lang>-${{ hashFiles('**/go.sum') }}
restore-keys: ${{ runner.os }}-<lang>-

# Language-specific paths:
# Go:     ~/go/pkg/mod
# Node:   ~/.npm
# Python: ~/.cache/pip
# Java:   ~/.m2/repository
```

## Secrets
```yaml
env:
  DATABASE_URL: ${{ secrets.DATABASE_URL }}
  # Never: DATABASE_URL: "hardcoded-connection-string"
```
- Secrets via `${{ secrets.NAME }}` — never hardcoded (the test database above is a throwaway service container)
- Use environments (`staging`, `production`) for deployment protection rules
- `GITHUB_TOKEN` is auto-provided — use for GitHub API calls, with the least `permissions:` the job needs

## CD with Manual Approval
```yaml
deploy-prod:
  needs: deploy-staging
  environment: production     # requires manual approval if configured
  steps:
    - run: ./deploy.sh prod
    - run: curl -fsS "$PROD_URL/healthz" && curl -fsS "$PROD_URL/readyz"   # the runtime contract's paths
```

## Rules
- Pin action versions (`@v4` not `@main`); pin third-party actions to a commit SHA — prevents supply chain attacks
- `needs:` to enforce job ordering (lint → test → build → deploy)
- Versions from the table: `go-version-file` / `node-version-file` and service images at the table's major; a version matrix only adds versions the project supports (listed in the table or DECISIONS.md)
- Every job `services:` entry that steps reach on `localhost` has a `ports:` mapping and a health check
- **No silent retries:** no retry actions, `continue-on-error: true` or `|| true` around test and build steps. Playwright runs with `retries: 0`, or with `failOnFlakyTests: true` if the table sets retries; Go tests with `-count=1`. A test that passes only on retry is a failure
- `concurrency` to cancel in-progress runs on new push
- Upload test results (JUnit, coverage) with `if: always()` + `actions/upload-artifact`
