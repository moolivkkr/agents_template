# GitHub Actions patterns for reliable CI/CD pipelines.

## CI Workflow Structure
```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5      # or setup-node, setup-python, etc.
        with: { go-version: "1.22" }
      - uses: actions/cache@v4
        with:
          path: ~/go/pkg/mod
          key: ${{ runner.os }}-go-${{ hashFiles('**/go.sum') }}
      - run: golangci-lint run

  test:
    needs: lint
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env: { POSTGRES_PASSWORD: test }
        options: --health-cmd pg_isready --health-interval 5s
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with: { go-version: "1.22" }
      - uses: actions/cache@v4
        with:
          path: ~/go/pkg/mod
          key: ${{ runner.os }}-go-${{ hashFiles('**/go.sum') }}
      - run: go test ./...
      - run: go test -tags=integration ./...
        env:
          DATABASE_URL: postgres://postgres:test@localhost:5432/test

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build Docker image
        run: docker build -t myapp:${{ github.sha }} .
```

## Caching Strategy
```yaml
# Cache key: OS + lock file hash (invalidates when deps change)
key: ${{ runner.os }}-<lang>-${{ hashFiles('**/go.sum') }}
restore-keys: ${{ runner.os }}-<lang>-

# Language-specific paths:
# Go:     ~/go/pkg/mod
# Node:   ~/.npm or node_modules
# Python: ~/.cache/pip
# Java:   ~/.m2/repository
```

## Secrets
```yaml
env:
  DATABASE_URL: ${{ secrets.DATABASE_URL }}
  # Never: DATABASE_URL: "hardcoded-connection-string"
```
- Secrets via `${{ secrets.NAME }}` — never hardcoded
- Use environments (`staging`, `production`) for deployment protection rules
- `GITHUB_TOKEN` is auto-provided — use for GitHub API calls

## CD with Manual Approval
```yaml
deploy-prod:
  needs: deploy-staging
  environment: production     # requires manual approval if configured
  steps:
    - run: ./deploy.sh prod
```

## Rules
- Pin action versions (`@v4` not `@main`) — prevents supply chain attacks
- `needs:` to enforce job ordering (lint → test → build → deploy)
- Matrix builds for multi-version testing: `strategy: matrix: go-version: [1.21, 1.22]`
- `concurrency` to cancel in-progress runs on new push: `concurrency: ci-${{ github.ref }}`
- Upload test artifacts on failure: `if: failure()` + `actions/upload-artifact`
