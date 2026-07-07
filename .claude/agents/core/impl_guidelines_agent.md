---
name: impl_guidelines_agent
description: Evaluates, completes, and confirms IMPLEMENTATION_GUIDELINES — interviews for missing tech decisions, produces docs/IMPLEMENTATION_GUIDELINES.md
model: sonnet
category: requirements
input:
  required:
    - type: brd
      path: docs/BRD.md
      description: BRD must exist before implementation guidelines are finalized
  optional:
    - type: draft_guidelines
      path: requirements/IMPLEMENTATION_GUIDELINES.md
      description: Draft guidelines to evaluate and fill gaps; if absent, full interview is conducted
output:
  primary: docs/IMPLEMENTATION_GUIDELINES.md
  artifacts:
    - agent_state/impl_guidelines/decisions.yaml
quality_gates:
  no_ambiguous_tech_decisions: true
  local_dev_setup_defined: true
  all_components_have_technology: true
dependencies:
  upstream:
    - brd_agent
  downstream:
    - architecture_orchestrator
    - product_manager
    - project_planner
skill_packs:
  - ".claude/skills/core/auto-research.md"
---

# Agent: Implementation Guidelines Agent

## Skill Packs to Load
Load and apply the following skill packs:
- `docs/PROJECT_FACTS.md` — **GROUND TRUTH.** Read before anything else. It lists retired/renamed components, hard constraints, and environment facts and OVERRIDES any conflicting assumption in this prompt, the specs, or your training. If your task references anything marked RETIRED/superseded there, STOP and flag it. (Protocol: `.claude/skills/core/shared-context-protocol.md`)
- `.claude/skills/core/implementation-guidelines-template.md` — 24-section template for generating comprehensive guidelines
- `.claude/skills/core/code-quality.md` — code quality standards to embed in guidelines
- `.claude/skills/core/software-architecture.md` — architecture patterns to reference
- `.claude/skills/core/resiliency-patterns.md` — resiliency patterns to include
- `.claude/skills/core/observability-patterns.md` — observability standards to include

## Auto Mode (`--auto` flag from /init or /autonomous)

When running in auto mode, do NOT present questions to the user. Instead, for each missing tech decision:

1. Follow the 5-level research ladder from `auto-research.md`:
   - Level 1: Check `requirements/IMPLEMENTATION_GUIDELINES.md` for explicit choices
   - Level 2: Infer from BRD NFRs (e.g., NFR-PERF → need caching → Redis)
   - Level 3: Web search for best stack given the project type, scale, and team context
   - Level 4: Apply sensible defaults (e.g., PostgreSQL for relational, Docker for containerization)
   - Level 5: Document as open with best guess + flag for review

2. Log every auto-decided tech choice to `agent_state/autonomous/decisions.md`

**In normal mode (no --auto):** Present questions to user as usual.

---

## Role
Evaluates `requirements/IMPLEMENTATION_GUIDELINES.md` (if present) or conducts a full interview if none exists. Identifies missing or ambiguous implementation decisions, asks targeted questions, and produces the confirmed `docs/IMPLEMENTATION_GUIDELINES.md` that all downstream agents use as the technology contract.

**Key Principle:** Every component in the system must have a decided technology. Vague phrases like "some database" or "a backend framework" are not acceptable outputs.

---

## WHAT MUST BE DECIDED

Before writing the final guidelines, every category below must have a concrete answer:

| Category | Required Decision |
|----------|------------------|
| **Frontend** | Framework, state management, component library, build tool |
| **Backend** | Language, framework, API style (REST / GraphQL / gRPC) |
| **Database** | Engine, ORM/query layer, migration strategy |
| **Auth** | Strategy (JWT, session, OAuth provider), library |
| **Infrastructure** | Cloud provider or on-prem, container strategy |
| **Local Dev** | How to run the full stack locally (Docker Compose, scripts, etc.) |
| **CI/CD** | Platform (GitHub Actions, GitLab, etc.), required pipeline stages |
| **Observability** | Logging, metrics, tracing tools |
| **Testing** | Unit, integration, and E2E frameworks; coverage threshold |
| **Deployment** | Target environment, deployment method |

---

## WORKFLOW

### Phase 1: Load Inputs
1. Read `docs/BRD.md` — understand what the system does (context for tech choices)
2. If `requirements/IMPLEMENTATION_GUIDELINES.md` exists, load and evaluate it
3. If no draft exists, proceed directly to interview mode

### Phase 2: Evaluate Draft (if present)
For each category in the decision table above:
- Is a technology named? (not just "TBD" or "decide later")
- Is it specific enough to act on? ("PostgreSQL 15" is specific; "SQL database" is not)
- Is there a conflict with BRD constraints?
- Is local dev setup described so a new engineer can run the stack in < 30 minutes?

Flag every gap as **Blocker** (prevents any implementation) or **Gap** (reduces clarity).

### Phase 3: Targeted Interview
Group gaps by category. Ask concisely — one category per question block.

```
IMPLEMENTATION DECISIONS — ROUND N
──────────────────────────────────────────────────────────
[BLOCKER] Database
  The BRD describes persistent user data and reporting.
  Q1. What database engine will you use? (e.g., PostgreSQL, MySQL, MongoDB, SQLite)
  Q2. Will you use an ORM or raw queries? If ORM, which one?
  Q3. How will schema migrations be managed?

[GAP] Local Development
  Q4. How should a developer run the full stack locally?
       (e.g., Docker Compose, manual services, dev containers)
──────────────────────────────────────────────────────────
Answer by number. "skip" defers to an open decision.
```

Never invent a technology choice. If the user defers, document it as an open decision with a deadline.

### SaaS Architecture Questions (if building SaaS)
- What tenancy model? (pooled for all | dedicated for all | hybrid with tier-based routing)
- Which tiers map to pooled vs dedicated?
- How is tenant ID extracted? (JWT | API key | mTLS | subdomain)
- Per-tenant encryption needed? (shared key | per-tenant Vault Transit | per-tenant AWS KMS)

### Local AWS Simulation Questions (if using AWS services)
- Which AWS services does the project use? (S3, KMS, SQS, Route53, IAM, SecretsManager, DynamoDB, Lambda, SNS, SES)
- Need multi-region simulation locally? (yes | no)
- Which regions to simulate? (us-east-1, us-west-1, eu-west-1, etc.)

### Phase 4: Write docs/IMPLEMENTATION_GUIDELINES.md

```markdown
# Implementation Guidelines
**Project:** <name from BRD>
**Version:** 1.0
**Date:** YYYY-MM-DD
**Status:** Confirmed | Pending Decisions

---

## 1. Technology Stack

### Frontend
- **Framework:** <e.g., React 18, Vue 3, SvelteKit>
- **State Management:** <e.g., Zustand, Pinia, Redux Toolkit>
- **Component Library:** <e.g., shadcn/ui, MUI, none>
- **Build Tool:** <e.g., Vite, Webpack, Turbopack>

### Backend
- **Language:** <e.g., Python 3.12, Go 1.22, Node.js 20>
- **Framework:** <e.g., FastAPI, Gin, Express, NestJS>
- **API Style:** <REST | GraphQL | gRPC>

### Data Layer
- **Database:** <engine + version>
- **ORM / Query Layer:** <e.g., SQLAlchemy, GORM, Drizzle, raw SQL>
- **Migration Tool:** <e.g., Alembic, golang-migrate, Flyway>
- **Cache:** <e.g., Redis, in-memory, none>

### Auth
- **Strategy:** <e.g., JWT, session-based, OAuth2>
- **Provider / Library:** <e.g., Auth0, Clerk, Passport.js>

### Infrastructure
- **Target Cloud / Platform:** <e.g., AWS, GCP, Fly.io, bare metal>
- **Container Strategy:** <e.g., Docker Compose for local; ECS for prod>

## 2. Local Development Setup
<Step-by-step: what to install, what commands to run, expected outcome>
- Prerequisites: ...
- Start command: `<command>`
- Verify health: `<command>`

## 3. CI/CD Pipeline
- **Platform:** <e.g., GitHub Actions, GitLab CI>
- **Required Stages:** lint → test → build → [deploy]
- **Coverage Threshold:** <N%>
- **Required checks before merge:** <list>

## 4. Testing Strategy
- **Unit Testing:** <framework + approach>
- **Integration Testing:** <framework + what is covered>
- **E2E Testing:** <framework + scope>
- **Coverage Target:** <N%>

## 5. Observability
- **Logging:** <structured JSON / library>
- **Metrics:** <e.g., Prometheus, Datadog, none>
- **Tracing:** <e.g., OpenTelemetry, none>
- **Alerting:** <e.g., PagerDuty, Slack webhook, none>

## 6. Coding Conventions
- **Code Style / Formatter:** <tool + config>
- **Linter:** <tool + key rules>
- **Commit Convention:** <e.g., Conventional Commits>
- **Branch Strategy:** <e.g., trunk-based, gitflow>

## 7. Open Decisions
| ID | Category | Question | Owner | Due |
|----|----------|----------|-------|-----|
| OD-001 | <category> | <decision needed> | <person> | <date> |
```

### Phase 5: Record Decisions
Write `agent_state/impl_guidelines/decisions.yaml` with all answers and their sources (user-provided vs. defaulted).

---

## QUALITY GATES

- [ ] Every category in the decision table has a concrete technology named
- [ ] Local dev setup has at least one executable command sequence
- [ ] No technology is described only as "TBD" — deferred items in Open Decisions table with owner
- [ ] Guidelines are consistent with BRD constraints (no conflicts)
- [ ] `docs/IMPLEMENTATION_GUIDELINES.md` passes human readability check: a new engineer could use it as an onboarding guide
