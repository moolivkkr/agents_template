# Docker patterns for containerized application builds and local development.

Versions and commands come from IMPLEMENTATION_GUIDELINES `## Commands and versions`
(`~/.claude/skills/core/commands-and-versions.md`); probes, entry points, user and shutdown from
`## Runtime contract`. Nothing below is a version to copy: `<Go>`, `<Node>` and `<PostgreSQL>` stand
for the table's values.

## Multi-Stage Dockerfile (Go example)
```dockerfile
# Stage 1: Builder — the tag's Go version equals the versions table and the `go` line in go.mod.
# Official golang images set GOTOOLCHAIN=local, so an older builder fails on a newer go.mod.
ARG GO_VERSION=<Go>
FROM golang:${GO_VERSION}-alpine AS builder
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -trimpath -ldflags "-s -w" -o /out/app ./cmd/app

# Stage 2: Runtime (minimal, no shell)
FROM gcr.io/distroless/static-debian12
ARG GIT_SHA=unknown
ENV GIT_SHA=${GIT_SHA}
COPY --from=builder /out/app /app
# Numeric user on its own line: Docker keeps a trailing comment as part of the USER value
# and the container then fails to start. A named user fails runAsNonRoot on Kubernetes.
USER 65532:65532
EXPOSE 8080
ENTRYPOINT ["/app"]
CMD ["serve"]
```
- The runtime image has no shell or curl, so there's no Docker `HEALTHCHECK` here: compose and
  Kubernetes probe the runtime contract's `/healthz` and `/readyz` from outside. Add a `HEALTHCHECK`
  only for an image that can run one, and only against a path the app implements.
- `migrate` and `seed` run from the same image with a different command (`CMD`/`args`), never as part
  of `serve`.
- The app writes nothing outside `$TMPDIR`, so the root filesystem can be read-only.
- Other languages: same shape with the table's version (`node:<Node>-slim`, `python:<Python>-slim`),
  a numeric `USER`, and `ARG GIT_SHA` → `ENV GIT_SHA`.

## .dockerignore
```
.git
.env*
secrets.env
node_modules/
*.test
dist/
agent_state/
.claude/
docs/
coverage*
test-results/
playwright-report/
*.junit.xml
README.md
```
Exclude: version control, secrets, local config, agent/pipeline state, test outputs and docs. An
untracked file inside a build context marks the image `-dirty` in the lab deploy.

## docker-compose.local.yml (local dev)
```yaml
services:
  migrate:
    build: .
    command: ["migrate"]
    environment:
      APP_ENV: local
      DATABASE_URL: postgres://app:app@db:5432/app?sslmode=disable
    depends_on:
      db:
        condition: service_healthy

  api:
    build: .
    command: ["serve"]
    ports: ["8080:8080"]
    environment:
      APP_ENV: local
      PORT: "8080"
      DATABASE_URL: postgres://app:app@db:5432/app?sslmode=disable
    depends_on:
      migrate:
        condition: service_completed_successfully
    # No container healthcheck: the distroless image has no shell or curl. The pipeline probes
    # http://localhost:8080/healthz (and /readyz) from the host (develop-orchestrator Wave 3.5).

  db:
    image: postgres:<PostgreSQL>-alpine   # the versions table's major — same as tests, CI and k8s
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app              # local only; never a real credential
      POSTGRES_DB: app
    volumes:
      - db_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "app"]
      interval: 5s
      retries: 5

volumes:
  db_data:
```

## Layer Caching Strategy
```dockerfile
# Copy dependency files FIRST (changes less often)
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts

# Copy source AFTER (changes more often)
COPY src/ ./src/
RUN npm run build
```
Order: dependency manifest → install (lockfile only, lifecycle scripts off) → source copy → build.

## Rules
- Never `COPY . .` before installing dependencies — defeats caching
- Base-image and toolchain versions come from `## Commands and versions`, never guessed
- No secrets in Dockerfile (ENV or ARG) — use runtime env vars
- Numeric non-root `USER` (e.g. `65532:65532`) on a line with no trailing comment
- `ARG GIT_SHA` → `ENV GIT_SHA` so the version route and smoke checks see the deployed commit
- Health checks target `/healthz` + `/readyz` (the runtime contract) — never `/health`
- Named volumes for persistent data (not bind mounts)
- `depends_on` with `condition: service_healthy` (or `service_completed_successfully` for the migrate one-shot) — don't race on startup
