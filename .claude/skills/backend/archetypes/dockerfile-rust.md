---
skill: dockerfile-rust
description: Rust optimized Docker archetype — multi-stage with cargo-chef dependency caching, minimal runtime (debian-slim or alpine+musl), static linking, non-root user, health check, .dockerignore, Docker Compose, cross-compilation tips
version: "1.0"
tags:
  - rust
  - docker
  - dockerfile
  - devops
  - archetype
  - backend
---

# Dockerfile Archetype (Rust)

Optimized multi-stage Docker build for Rust projects. Every generated project MUST follow this pattern.

## Project Structure

```
.
├── Cargo.toml
├── Cargo.lock
├── .dockerignore
├── Dockerfile
├── docker-compose.yml
├── migrations/
├── .sqlx/                  <- offline query cache (committed)
└── src/
    └── main.rs
```

## .dockerignore

```dockerignore
# .dockerignore — Keep the build context small and fast.

# Build artifacts (rebuilding inside Docker anyway)
target/

# Version control
.git/
.gitignore

# IDE / editor files
.idea/
.vscode/
*.swp
*.swo
*~

# CI/CD
.github/
.gitlab-ci.yml

# Documentation (not needed at runtime)
docs/
*.md
LICENSE

# Tests (not needed in production image)
tests/
benches/

# Local environment
.env
.env.*
docker-compose*.yml

# OS files
.DS_Store
Thumbs.db
```

## Dockerfile: Multi-Stage with cargo-chef

```dockerfile
# =============================================================================
# Stage 1: Chef — Prepare the dependency recipe
# =============================================================================
FROM rust:1.82-bookworm AS chef

# Install cargo-chef for dependency caching
RUN cargo install cargo-chef --locked
WORKDIR /app

# =============================================================================
# Stage 2: Planner — Analyze dependencies and create a recipe
# =============================================================================
FROM chef AS planner

# Copy only the files needed to compute the dependency graph
COPY Cargo.toml Cargo.lock ./
COPY src/ src/

# Generate the recipe (dependency graph without source code)
RUN cargo chef prepare --recipe-path recipe.json

# =============================================================================
# Stage 3: Builder — Build dependencies (cached), then build the application
# =============================================================================
FROM chef AS builder

# Copy the recipe from planner
COPY --from=planner /app/recipe.json recipe.json

# Build ONLY dependencies (this layer is cached until Cargo.toml/Cargo.lock change)
RUN cargo chef cook --release --recipe-path recipe.json

# Now copy the actual source code
COPY . .

# Copy the sqlx offline cache for compile-time query checking
# This allows building without a live database connection.
COPY .sqlx/ .sqlx/
ENV SQLX_OFFLINE=true

# Build the application
RUN cargo build --release --bin yourapp

# Strip debug symbols to reduce binary size (~50-70% reduction)
RUN strip target/release/yourapp

# =============================================================================
# Stage 4: Runtime — Minimal production image
# =============================================================================
FROM debian:bookworm-slim AS runtime

# Install runtime dependencies
#   - ca-certificates: for HTTPS connections (to external APIs, DBs with TLS)
#   - libssl3: for OpenSSL-linked builds (not needed if using rustls)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user for security
RUN groupadd --gid 1001 appuser && \
    useradd --uid 1001 --gid appuser --shell /bin/false --create-home appuser

WORKDIR /app

# Copy the built binary from the builder stage
COPY --from=builder /app/target/release/yourapp /app/yourapp

# Copy migrations (if running at startup via embedded sqlx::migrate!)
# Not strictly necessary if migrations are embedded, but useful for manual runs.
COPY --from=builder /app/migrations /app/migrations

# Switch to non-root user
USER appuser

# Expose the application port
EXPOSE 8080

# Health check — adjust the endpoint and interval as needed
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run the application
ENTRYPOINT ["/app/yourapp"]
```

## Dockerfile: Static Binary with musl (Alpine Runtime)

```dockerfile
# =============================================================================
# Variant: Static linking with musl for minimal Alpine runtime
# Produces a ~5-15 MB image (vs ~80-150 MB with debian-slim)
# =============================================================================

# Stage 1: Chef
FROM rust:1.82-bookworm AS chef
RUN cargo install cargo-chef --locked
RUN rustup target add x86_64-unknown-linux-musl
RUN apt-get update && apt-get install -y musl-tools
WORKDIR /app

# Stage 2: Planner
FROM chef AS planner
COPY Cargo.toml Cargo.lock ./
COPY src/ src/
RUN cargo chef prepare --recipe-path recipe.json

# Stage 3: Builder (musl target)
FROM chef AS builder
COPY --from=planner /app/recipe.json recipe.json

# Build dependencies with musl target
RUN cargo chef cook --release --target x86_64-unknown-linux-musl --recipe-path recipe.json

COPY . .
COPY .sqlx/ .sqlx/
ENV SQLX_OFFLINE=true

# Build with musl for fully static binary
RUN cargo build --release --target x86_64-unknown-linux-musl --bin yourapp
RUN strip target/x86_64-unknown-linux-musl/release/yourapp

# Stage 4: Minimal Alpine runtime
FROM alpine:3.20 AS runtime

# Install CA certificates (curl for health check is built into alpine)
RUN apk add --no-cache ca-certificates curl

# Non-root user
RUN addgroup -g 1001 -S appuser && \
    adduser -u 1001 -S appuser -G appuser -s /bin/false

WORKDIR /app
COPY --from=builder /app/target/x86_64-unknown-linux-musl/release/yourapp /app/yourapp
COPY --from=builder /app/migrations /app/migrations

USER appuser
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

ENTRYPOINT ["/app/yourapp"]
```

## Dockerfile: Scratch (Absolute Minimum)

```dockerfile
# =============================================================================
# Variant: FROM scratch — no OS, no shell, no package manager
# Produces ~5-10 MB images. No curl for health check.
# Use only when you have external health check infrastructure.
# =============================================================================

FROM rust:1.82-bookworm AS builder
RUN cargo install cargo-chef --locked
RUN rustup target add x86_64-unknown-linux-musl
RUN apt-get update && apt-get install -y musl-tools
WORKDIR /app

COPY Cargo.toml Cargo.lock ./
COPY src/ src/
COPY .sqlx/ .sqlx/
ENV SQLX_OFFLINE=true

RUN cargo build --release --target x86_64-unknown-linux-musl --bin yourapp
RUN strip target/x86_64-unknown-linux-musl/release/yourapp

FROM scratch
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
COPY --from=builder /app/target/x86_64-unknown-linux-musl/release/yourapp /yourapp

# No USER instruction — scratch has no user database.
# The binary runs as whatever user the container runtime specifies.

EXPOSE 8080
ENTRYPOINT ["/yourapp"]
```

## Docker Compose (Development)

```yaml
# docker-compose.yml

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
      target: runtime     # use the runtime stage
    ports:
      - "8080:8080"
    environment:
      - DATABASE_URL=postgres://postgres:postgres@db:5432/yourapp
      - JWT_SECRET=dev-secret-change-in-production
      - RUST_LOG=yourapp=debug,tower_http=debug
      - REDIS_URL=redis://redis:6379
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s

  db:
    image: postgres:16-alpine
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: yourapp
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 3s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redisdata:/data

volumes:
  pgdata:
  redisdata:
```

## Docker Compose (Development with Hot Reload)

```yaml
# docker-compose.dev.yml
# Usage: docker compose -f docker-compose.yml -f docker-compose.dev.yml up

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
      target: chef          # stop at chef stage, we'll compile locally
    volumes:
      # Mount source code for cargo-watch hot reloading
      - .:/app
      # Use a named volume for target/ to avoid slow bind mounts
      - cargo-target:/app/target
      - cargo-registry:/usr/local/cargo/registry
    command: >
      cargo watch
        --watch src
        --exec 'run --bin yourapp'
    environment:
      - DATABASE_URL=postgres://postgres:postgres@db:5432/yourapp
      - JWT_SECRET=dev-secret-change-in-production
      - RUST_LOG=yourapp=debug,tower_http=debug,sqlx=warn

volumes:
  cargo-target:
  cargo-registry:
```

## Cross-Compilation Tips

```bash
# --- Option 1: cargo-zigbuild (recommended for cross-compilation) ---
# Uses Zig as a cross-compiler. Simpler than setting up cross toolchains.

cargo install cargo-zigbuild

# Build for Linux x86_64 from macOS
cargo zigbuild --release --target x86_64-unknown-linux-musl

# Build for Linux ARM64 (e.g., AWS Graviton, Apple Silicon Docker)
cargo zigbuild --release --target aarch64-unknown-linux-musl

# --- Option 2: cross (Docker-based cross-compilation) ---
# Each target runs in a pre-configured Docker container.

cargo install cross --git https://github.com/cross-rs/cross

# Build for Linux ARM64
cross build --release --target aarch64-unknown-linux-musl

# Build for Linux x86_64
cross build --release --target x86_64-unknown-linux-musl

# --- Option 3: Multi-platform Docker build (buildx) ---
# Build images for multiple architectures simultaneously.

docker buildx create --name multiarch --use
docker buildx build \
    --platform linux/amd64,linux/arm64 \
    --tag yourapp:latest \
    --push \
    .

# For local testing (load into local Docker, single platform only):
docker buildx build \
    --platform linux/arm64 \
    --tag yourapp:latest \
    --load \
    .
```

## Build Optimization Tips

```dockerfile
# --- Cargo build flags for smaller/faster binaries ---

# 1. Enable LTO (Link-Time Optimization) — slower build, faster binary
#    Add to Cargo.toml:
#    [profile.release]
#    lto = true
#    codegen-units = 1
#    opt-level = "z"    # optimize for size ("s" for balanced, "3" for speed)
#    strip = true       # strip debug symbols (alternative to manual strip)

# 2. Use sccache for build caching across Docker builds
#    ENV RUSTC_WRAPPER=sccache

# 3. Mount Cargo registry as a Docker cache mount (BuildKit)
RUN --mount=type=cache,target=/usr/local/cargo/registry \
    --mount=type=cache,target=/app/target \
    cargo build --release --bin yourapp && \
    cp target/release/yourapp /app/yourapp-bin
```

## Cargo.toml Release Profile

```toml
[profile.release]
# Link-Time Optimization: merges all crates for better optimization
lto = true
# Single codegen unit: slower compile, better optimization
codegen-units = 1
# Optimize for size (use "3" for max speed instead)
opt-level = "z"
# Strip debug symbols automatically
strip = true
# Abort on panic (smaller binary, no unwinding)
panic = "abort"
```

## Production Checklist

```
[ ] .dockerignore excludes target/, .git/, docs/, tests/
[ ] Multi-stage build: chef -> planner -> builder -> runtime
[ ] Dependencies cached via cargo-chef (rebuild only when Cargo.toml/Cargo.lock change)
[ ] SQLX_OFFLINE=true set in builder stage
[ ] .sqlx/ directory copied into builder stage
[ ] Binary stripped of debug symbols
[ ] Runtime image uses debian-slim or alpine (not the full Rust image)
[ ] Non-root user created and used (USER appuser)
[ ] HEALTHCHECK instruction present
[ ] Only the binary and CA certificates are in the final image
[ ] No .env files, secrets, or source code in the final image
[ ] EXPOSE matches the actual application port
[ ] release profile has lto=true, codegen-units=1, strip=true
```

## Critical Rules

- NEVER use the `rust:*` image as the final runtime — it is ~1.5 GB; use debian-slim (~80 MB) or alpine (~5 MB)
- ALWAYS use cargo-chef for dependency caching — without it, every source change rebuilds all dependencies
- ALWAYS set `SQLX_OFFLINE=true` in the builder stage — compile-time query checking must not require a live database
- ALWAYS commit the `.sqlx/` directory and copy it into the builder stage
- ALWAYS create a non-root user in the runtime image — never run as root
- ALWAYS include a HEALTHCHECK — orchestrators (Kubernetes, ECS, Compose) need it for liveness/readiness
- ALWAYS strip the binary — reduces size by 50-70%
- ALWAYS use `.dockerignore` to exclude `target/`, `.git/`, `tests/`, `docs/`
- PREFER musl static linking for Alpine/scratch images — no runtime library dependencies
- PREFER `panic = "abort"` in release profile — smaller binary, no unwinding overhead
- Use BuildKit cache mounts (`--mount=type=cache`) for Cargo registry in CI
- For multi-architecture support, use `docker buildx build --platform linux/amd64,linux/arm64`
- For cross-compilation from macOS, prefer `cargo-zigbuild` over native cross toolchains
