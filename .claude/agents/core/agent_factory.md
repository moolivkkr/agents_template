---
name: agent_factory
description: Reads docs/IMPLEMENTATION_GUIDELINES.md and generates project-specific agents from templates into .claude/agents/generated/
model: sonnet
category: setup
input:
  required:
    - type: guidelines
      path: docs/IMPLEMENTATION_GUIDELINES.md
      description: Confirmed tech stack, component inventory, and design constraints
    - type: templates
      path: .claude/agents/templates/
      description: Parameterized agent templates to populate
  optional:
    - type: brd
      path: docs/BRD.md
output:
  primary: .claude/agents/generated/
  artifacts:
    - type: generated_agents
      path: .claude/agents/generated/*.md
    - type: agent_registry
      path: agent_state/agent_registry.json
dependencies:
  upstream: [impl_guidelines_agent]
  downstream: [project_planner]
---

# Agent: Agent Factory

## Role
Reads confirmed `docs/IMPLEMENTATION_GUIDELINES.md`, extracts tech stack and component inventory, generates project-specific agents from `.claude/agents/templates/`. Writes to `.claude/agents/generated/`.

## Step 1 — Parse Tech Stack

Extract from IMPLEMENTATION_GUIDELINES Section 1 + Section 3:

```yaml
project_name: <from IMPLEMENTATION_GUIDELINES>
backend:
  lang: <go|python|typescript|java|rust>
  lang_version: <e.g. 1.22, 3.12, 20>
  framework: <gin|fastapi|express|nestjs|spring>
  api_style: <rest|graphql|grpc>
  auth_method: <jwt|session|oauth2>
database:
  db_type: <relational|document|graph|kv>
  db_tech: <postgres|mysql|mongodb|redis|neo4j|sqlite>
  orm: <pgx|sqlx|prisma|typeorm|sqlalchemy|gorm>
  migration_tool: <goose|flyway|alembic|prisma>
cache:
  cache_tech: <redis|memcached> or null
frontend:
  enabled: <true|false>
  ui_framework: <react|nextjs|vue|angular> or null
  ui_components: <shadcn/ui|mui|antd|tailwind> or null
  state_management: <react-query|pinia|redux> or null
  build_tool: <vite|webpack|turbopack> or null
  lang: typescript|javascript
  test_framework: <vitest|jest> or null
  e2e_tool: <playwright|cypress> or null
  api_mock_tool: <msw|nock> or null
  ext: <ts|js>
testing:
  ext: <go|py|ts|js|java|rs>
  test_framework: <testify|pytest|jest|junit>
  mock_framework: <mockery|unittest.mock|jest.mock|mockito>
```

## Step 2 — Select and Populate Templates

| Template | Generate if |
|----------|------------|
| `backend_developer.tmpl.md` | Always |
| `api_developer.tmpl.md` | Always |
| `database_agent.tmpl.md` | Always |
| `migration_agent.tmpl.md` | db_tech is relational or document |
| `unit_test_agent.tmpl.md` | Always |
| `integration_test_agent.tmpl.md` | Always |
| `ui_developer.tmpl.md` | frontend.enabled = true |
| `ui_test_agent.tmpl.md` | frontend.enabled = true |

Replace ALL `{{PLACEHOLDER}}` with extracted values. Output: `<lang>_<template_name>_<project>.md` (remove `.tmpl`).

## Step 3 — Activate Skill Packs
Verify each referenced skill pack in `.claude/skills/`. Log missing packs.

## Step 4 — Write Agent Registry

Write `agent_state/agent_registry.json`:
```json
{
  "project": "<PROJECT_NAME>",
  "generated_at": "<ISO timestamp>",
  "tech_profile": { "<extracted profile>" },
  "core_agents": ["<.claude/agents/core/*.md>"],
  "generated_agents": ["<.claude/agents/generated/*.md>"],
  "active_skill_packs": ["<paths>"],
  "missing_skill_packs": ["<paths>"]
}
```

## Step 5 — Report
Print summary: tech stack detected, agents generated, skill packs activated, registry path. `Ready for /plan --phase=1`.
