# Docker patterns for containerized application builds and local development.

## Multi-Stage Dockerfile
```dockerfile
# Stage 1: Builder
FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download                  # cache layer: deps before source
COPY . .
RUN CGO_ENABLED=0 go build -o /app/server ./cmd/api

# Stage 2: Runtime (minimal)
FROM gcr.io/distroless/static-debian12
COPY --from=builder /app/server /server
USER nonroot:nonroot                 # never run as root
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s CMD ["/server", "--health-check"]
ENTRYPOINT ["/server"]
```
Adapt builder stage for your language. Always use distroless or alpine for runtime.

## .dockerignore
```
.git
.env*
node_modules/
*.test
*_test.go
dist/
.planning/
README.md
docs/
```
Exclude: version control, secrets, test files, local config, large docs.

## docker-compose.local.yml (local dev)
```yaml
services:
  api:
    build: .
    ports: ["8080:8080"]
    environment:
      DATABASE_URL: postgres://user:pass@db:5432/myapp
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - .:/app                       # source mount for hot reload

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
      POSTGRES_DB: myapp
    volumes:
      - db_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "user"]
      interval: 5s
      retries: 5

volumes:
  db_data:
```

## Layer Caching Strategy
```dockerfile
# Copy dependency files FIRST (changes less often)
COPY package.json package-lock.json ./
RUN npm ci

# Copy source AFTER (changes more often)
COPY src/ ./src/
RUN npm run build
```
Order: dependency manifest → install → source copy → build.

## Rules
- Never `COPY . .` before installing dependencies — defeats caching
- No secrets in Dockerfile (ENV or ARG) — use runtime env vars
- `HEALTHCHECK` on every service container
- Named volumes for persistent data (not bind mounts)
- `depends_on` with `condition: service_healthy` — don't race on startup
- `USER nonroot` in production images — never run as root
