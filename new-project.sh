#!/usr/bin/env bash
# new-project.sh — bootstrap a new project directory
# Usage: ./new-project.sh <project-name> [/path/to/parent]
#
# Creates:
#   <project-name>/
#   ├── requirements/          ← drop your docs here
#   ├── requirements/IMPLEMENTATION_GUIDELINES.md  ← editable template
#   ├── docs/                  ← BRD + phase specs will go here
#   ├── agent_state/           ← phase gates, manifests, reports
#   └── .claude/
#       └── agents/generated/  ← /init will populate this

set -e

PROJECT_NAME="${1:?Usage: $0 <project-name> [/path/to/parent]}"
PARENT_DIR="${2:-$(pwd)}"
PROJECT_DIR="$PARENT_DIR/$PROJECT_NAME"

if [ -d "$PROJECT_DIR" ]; then
  echo "Note: $PROJECT_DIR already exists — continuing with scaffold"
else
  echo "Creating project: $PROJECT_DIR"
fi
echo

# Directory scaffold
mkdir -p "$PROJECT_DIR/requirements"
mkdir -p "$PROJECT_DIR/docs"
mkdir -p "$PROJECT_DIR/agent_state/phases"
mkdir -p "$PROJECT_DIR/agent_state/reconciliation"
mkdir -p "$PROJECT_DIR/.claude/agents/generated"

# IMPLEMENTATION_GUIDELINES template
cat > "$PROJECT_DIR/requirements/IMPLEMENTATION_GUIDELINES.md" << 'TMPL'
# Implementation Guidelines — DRAFT
# Fill in what you know. /init will ask about anything left blank or ambiguous.

## Tech Stack

### Frontend
- Framework:         (e.g. React 18, Vue 3, SvelteKit — or: none)
- State Management:  (e.g. Zustand, Pinia — or: n/a)
- Component Library: (e.g. shadcn/ui, MUI, Tailwind — or: none)

### Backend
- Language:    (e.g. Go 1.22, Python 3.12, TypeScript/Node 20)
- Framework:   (e.g. Gin, FastAPI, Express, NestJS)
- API Style:   (REST / GraphQL / gRPC)

### Data Layer
- Database:       (e.g. PostgreSQL 16, MongoDB 7, SQLite)
- ORM / Query:    (e.g. GORM, SQLAlchemy, Prisma, raw SQL)
- Migration Tool: (e.g. goose, Alembic, Flyway, prisma migrate)
- Cache:          (e.g. Redis — or: none)

### Auth
- Strategy: (e.g. JWT, session-based, OAuth2/OIDC)
- Library:  (e.g. Auth.js, Clerk, Passport.js — or: custom)

### Infrastructure
- Cloud / Platform: (e.g. AWS, GCP, Fly.io, self-hosted)
- Containers:       (e.g. Docker Compose for local + Kubernetes for prod)

## Local Dev
- How to start the stack: (e.g. docker compose up -d)
- How to verify it's healthy: (e.g. curl http://localhost:8080/health)

## CI/CD
- Platform: (e.g. GitHub Actions, GitLab CI)
- Required stages: lint → test → build → deploy

## Testing
- Unit:        (e.g. testify, pytest, vitest)
- Integration: (e.g. testify + real DB, pytest + testcontainers)
- E2E:         (e.g. Playwright, Cypress — or: none)
- Coverage target: 80%

## Notes / Constraints
(Any other technical constraints, naming conventions, or decisions already made)
TMPL

# git init
# git init + .gitignore (append, don't overwrite)
cd "$PROJECT_DIR"
if [ ! -d ".git" ]; then
  git init -q
fi
GITIGNORE_ENTRY=".claude/agents/generated/"
if [ -f ".gitignore" ]; then
  # Append only if not already present
  grep -qxF "$GITIGNORE_ENTRY" .gitignore || echo "$GITIGNORE_ENTRY" >> .gitignore
else
  echo "$GITIGNORE_ENTRY" > .gitignore
fi

echo "✅ Project created: $PROJECT_DIR"
echo
echo "Next steps:"
echo "  1. Edit requirements/IMPLEMENTATION_GUIDELINES.md (or leave blank — /init will ask)"
echo "  2. Drop any specs, user stories, or pitch deck into requirements/"
echo "  3. cd $PROJECT_DIR"
echo "  4. Open Claude Code → /startup/init"
