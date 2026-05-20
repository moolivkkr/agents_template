# Go Dockerfile Archetype

> Production-ready, multi-stage Docker builds for Go services.
> Static binaries, distroless runtime, build-cache optimization, and security hardening.

---

## Multi-Stage Build (Production)

```dockerfile
# ============================================================
# Stage 1: Build — compile a static Go binary
# ============================================================
FROM golang:1.22-alpine AS builder

# Build arguments for version metadata injection
ARG VERSION=dev
ARG COMMIT_SHA=unknown
ARG BUILD_TIME=unknown

# Install git (needed for go mod download with private repos) and ca-certificates
RUN apk add --no-cache git ca-certificates tzdata

WORKDIR /src

# Copy dependency manifests first — Docker caches this layer
COPY go.mod go.sum ./
RUN --mount=type=cache,target=/go/pkg/mod \
    go mod download

# Copy source code
COPY . .

# Build a fully static binary
# - CGO_ENABLED=0: no C dependencies, pure Go — required for scratch/distroless
# - -ldflags="-s -w": strip debug info and DWARF symbols (~30% smaller binary)
# - -ldflags with -X: inject version metadata at build time
# - -trimpath: remove local filesystem paths from the binary (reproducible builds)
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 GOOS=linux \
    go build \
      -trimpath \
      -ldflags="-s -w \
        -X main.version=${VERSION} \
        -X main.commitSHA=${COMMIT_SHA} \
        -X main.buildTime=${BUILD_TIME}" \
      -o /bin/server ./cmd/server

# ============================================================
# Stage 2: Runtime — minimal, secure container
# ============================================================
FROM gcr.io/distroless/static-debian12:nonroot

# Copy timezone data and CA certificates from builder
COPY --from=builder /usr/share/zoneinfo /usr/share/zoneinfo
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/

# Copy the binary
COPY --from=builder /bin/server /server

# Copy any config files or migrations if needed
# COPY --from=builder /src/migrations /migrations
# COPY --from=builder /src/config.yaml /config.yaml

# Metadata labels
LABEL org.opencontainers.image.source="https://github.com/org/repo"
LABEL org.opencontainers.image.version="${VERSION}"

# Distroless 'nonroot' tag already runs as uid 65534
# Explicitly declare it for clarity
USER nonroot:nonroot

# Expose the service port
EXPOSE 8080

# Health check — requires a /healthz endpoint in the Go service
# Note: distroless has no shell, so HEALTHCHECK with curl won't work.
# Use Docker Compose or orchestrator-level health checks instead.
# If you need in-image health checks, use the debug variant or a Go-based checker.

ENTRYPOINT ["/server"]
```

### Key Decisions

| Decision | Rationale |
|----------|-----------|
| `golang:1.22-alpine` builder | Small builder image, fast downloads |
| `CGO_ENABLED=0` | Produces a static binary — no glibc dependency at runtime |
| `-ldflags="-s -w"` | Strips symbol table and DWARF debug info (~30% smaller) |
| `-trimpath` | Removes local paths from binary for reproducible builds |
| `--mount=type=cache` | Caches Go module downloads and build artifacts across builds |
| `distroless/static-debian12` | No shell, no package manager, no OS-level CVEs to patch |
| `nonroot` tag | Runs as UID 65534 — never root, even if container escapes |

### Alternative: scratch Base Image

```dockerfile
# Even smaller than distroless — literally empty filesystem
FROM scratch

# Must copy CA certs manually (no OS, no certs)
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
COPY --from=builder /usr/share/zoneinfo /usr/share/zoneinfo

# Must copy passwd for non-root user
COPY --from=builder /etc/passwd /etc/passwd

COPY --from=builder /bin/server /server

USER nobody

ENTRYPOINT ["/server"]
```

When to use `scratch` vs `distroless`:
- **scratch**: Absolute minimum size. Use when you control the entire deployment and need no debugging capabilities.
- **distroless**: Slightly larger, but includes timezone data, CA certs, and a non-root user by default. Preferred for most production deployments.

---

## Development Dockerfile

```dockerfile
# ============================================================
# Dockerfile.dev — Hot reload with air, debugger with delve
# ============================================================
FROM golang:1.22-alpine

# Install development tools
RUN go install github.com/air-verse/air@latest && \
    go install github.com/go-delve/delve/cmd/dlv@latest

WORKDIR /app

# Copy dependency manifests and download (cached layer)
COPY go.mod go.sum ./
RUN go mod download

# Source code will be volume-mounted at runtime — don't COPY it here
# The air watcher detects changes and rebuilds automatically

# Air config — expects .air.toml in project root
# See .air.toml example below

# Expose service port + delve debugger port
EXPOSE 8080 2345

# Default: run with hot reload
CMD ["air", "-c", ".air.toml"]
```

### .air.toml (Hot Reload Configuration)

```toml
# .air.toml — place in project root
root = "."
tmp_dir = "tmp"

[build]
  cmd = "go build -gcflags='all=-N -l' -o ./tmp/server ./cmd/server"
  bin = "./tmp/server"
  # Watch these file extensions
  include_ext = ["go", "tpl", "tmpl", "html", "yaml", "toml"]
  # Ignore these directories
  exclude_dir = ["assets", "tmp", "vendor", "testdata", "node_modules"]
  # Delay before rebuild (milliseconds)
  delay = 500

[log]
  time = false

[misc]
  clean_on_exit = true
```

### Delve Debugger Setup

```dockerfile
# To start with delve instead of air, override the CMD:
# docker compose exec app dlv debug ./cmd/server --headless --listen=:2345 --api-version=2 --accept-multiclient

# Or add a separate debug profile to docker-compose.override.yml
```

---

## Docker Compose Snippet

```yaml
# docker-compose.yml
services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
      args:
        VERSION: ${VERSION:-dev}
        COMMIT_SHA: ${COMMIT_SHA:-unknown}
    ports:
      - "8080:8080"
    environment:
      - DATABASE_URL=postgres://app:secret@db:5432/appdb?sslmode=disable
      - LOG_LEVEL=info
      - ENV=production
    depends_on:
      db:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "/server", "--health-check"]
      # Alternative if your binary supports wget-less health checks:
      # test: ["CMD-SHELL", "wget -qO- http://localhost:8080/healthz || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 5s
    deploy:
      resources:
        limits:
          memory: 256M
          cpus: "0.5"
    read_only: true
    tmpfs:
      - /tmp
    security_opt:
      - no-new-privileges:true

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: appdb
      POSTGRES_USER: app
      POSTGRES_PASSWORD: secret
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app -d appdb"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  pgdata:
```

### Development Override

```yaml
# docker-compose.override.yml — loaded automatically by docker compose
services:
  app:
    build:
      dockerfile: Dockerfile.dev
    volumes:
      # Mount source code for hot reload
      - .:/app
      # Named volume for go module cache — survives container recreation
      - gomod:/go/pkg/mod
      # Named volume for go build cache — faster rebuilds
      - gobuild:/root/.cache/go-build
    environment:
      - LOG_LEVEL=debug
      - ENV=development
    ports:
      - "8080:8080"
      - "2345:2345"   # delve debugger

volumes:
  gomod:
  gobuild:
```

---

## Build Arguments and Multi-Platform

### Version Metadata Injection

```bash
# Pass build metadata at build time
docker build \
  --build-arg VERSION=$(git describe --tags --always) \
  --build-arg COMMIT_SHA=$(git rev-parse HEAD) \
  --build-arg BUILD_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ) \
  -t myapp:latest .
```

```go
// cmd/server/main.go — receive injected build metadata
package main

var (
    version   = "dev"     // set by -ldflags
    commitSHA = "unknown" // set by -ldflags
    buildTime = "unknown" // set by -ldflags
)

func main() {
    log.Info("starting",
        slog.String("version", version),
        slog.String("commit", commitSHA),
        slog.String("built_at", buildTime),
    )
    // ...
}
```

### Multi-Platform Builds (ARM64 + AMD64)

```bash
# Build for multiple architectures — useful for M-series Mac + Linux servers
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --build-arg VERSION=$(git describe --tags --always) \
  -t ghcr.io/org/myapp:latest \
  --push .
```

```dockerfile
# The Dockerfile handles multi-platform automatically when using:
# - CGO_ENABLED=0 (no C cross-compilation needed)
# - Go's built-in cross-compilation via GOOS/GOARCH
# Docker buildx sets TARGETARCH automatically

FROM golang:1.22-alpine AS builder
ARG TARGETARCH

RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 GOOS=linux GOARCH=${TARGETARCH} \
    go build -trimpath -ldflags="-s -w" -o /bin/server ./cmd/server
```

---

## Security Hardening

### .dockerignore

```
# .dockerignore — keep build context small and secure
.git
.github
.gitignore
.env
.env.*
*.md
LICENSE
Makefile
docker-compose*.yml
Dockerfile*
.air.toml
tmp/
vendor/
testdata/
**/*_test.go
*.test
.vscode/
.idea/
.claude/
```

### Security Checklist

| Practice | Implementation |
|----------|---------------|
| No secrets in build args | Use runtime env vars or secret mounts, never `ARG SECRET=...` |
| Non-root user | Use `distroless:nonroot` or explicit `USER nobody` |
| Read-only filesystem | `read_only: true` in compose + `tmpfs: [/tmp]` for scratch space |
| Minimal attack surface | Distroless has no shell, no package manager — nothing to exploit |
| No new privileges | `security_opt: [no-new-privileges:true]` prevents privilege escalation |
| Pin base images | Use digest: `golang:1.22-alpine@sha256:abc123...` for reproducibility |
| Scan images | Run `trivy image myapp:latest` or `grype myapp:latest` in CI |
| Build-time secrets | Use `--mount=type=secret` for private repo access during build |

### Private Module Access During Build

```dockerfile
# For private Go modules, use Docker build secrets — never ARG for tokens
FROM golang:1.22-alpine AS builder

# Mount the secret at build time — it is NOT stored in any layer
RUN --mount=type=secret,id=github_token \
    git config --global url."https://$(cat /run/secrets/github_token)@github.com/".insteadOf "https://github.com/"

COPY go.mod go.sum ./
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=secret,id=github_token \
    GOPRIVATE=github.com/org/* go mod download
```

```bash
# Build with the secret
docker build --secret id=github_token,src=$HOME/.github_token -t myapp .
```

---

## CI Integration

### GitHub Actions Example

```yaml
# .github/workflows/build.yml
name: Build and Push
on:
  push:
    branches: [main]
    tags: ["v*"]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          platforms: linux/amd64,linux/arm64
          push: true
          tags: |
            ghcr.io/${{ github.repository }}:${{ github.sha }}
            ghcr.io/${{ github.repository }}:latest
          build-args: |
            VERSION=${{ github.ref_name }}
            COMMIT_SHA=${{ github.sha }}
            BUILD_TIME=${{ github.event.head_commit.timestamp }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Scan image
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: ghcr.io/${{ github.repository }}:${{ github.sha }}
          severity: CRITICAL,HIGH
          exit-code: 1
```

---

## Health Check Endpoint (Go Implementation)

```go
// internal/handler/health.go
package handler

import (
    "context"
    "encoding/json"
    "net/http"
    "time"
)

type HealthChecker interface {
    Ping(ctx context.Context) error
}

type HealthHandler struct {
    db      HealthChecker
    version string
}

func NewHealthHandler(db HealthChecker, version string) *HealthHandler {
    return &HealthHandler{db: db, version: version}
}

func (h *HealthHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
    ctx, cancel := context.WithTimeout(r.Context(), 3*time.Second)
    defer cancel()

    status := "ok"
    httpStatus := http.StatusOK

    dbErr := h.db.Ping(ctx)
    dbStatus := "ok"
    if dbErr != nil {
        dbStatus = "degraded"
        status = "degraded"
        httpStatus = http.StatusServiceUnavailable
    }

    resp := map[string]any{
        "status":  status,
        "version": h.version,
        "checks": map[string]string{
            "database": dbStatus,
        },
    }

    w.Header().Set("Content-Type", "application/json")
    w.WriteHeader(httpStatus)
    json.NewEncoder(w).Encode(resp)
}
```

---

## Image Size Comparison

| Base Image | Typical Final Size | Shell | Debugging | Use Case |
|------------|-------------------|-------|-----------|----------|
| `scratch` | 5-15 MB | No | None | Maximum minimalism |
| `distroless/static` | 7-20 MB | No | Limited | Production default |
| `alpine` | 15-30 MB | Yes | Full | When you need shell access |
| `debian-slim` | 80-120 MB | Yes | Full | When you need glibc |

Prefer `distroless/static-debian12:nonroot` for production. Use `alpine` only if you need to exec into containers for debugging.
