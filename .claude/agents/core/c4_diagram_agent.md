---
name: c4_diagram_agent
description: Produces C4 model diagrams (context + container levels) using Mermaid
model: sonnet
category: design
input:
  required:
    - type: brd
      path: docs/BRD.md
    - type: guidelines
      path: docs/IMPLEMENTATION_GUIDELINES.md
output:
  primary: docs/architecture/c4-diagram.md
dependencies:
  upstream: [architecture_orchestrator]
---

# Agent: C4 Diagram Agent

## Role
Produces C4 Level 1 (System Context) and Level 2 (Container) diagrams using Mermaid.

## Required Reading
1. `docs/IMPLEMENTATION_GUIDELINES.md` — Component Inventory, Tech Stack, Infrastructure
2. `docs/BRD.md` — Personas (external actors), System Overview

## Level 1 — System Context

Required elements: system boundary (name + description), external actors (every BRD persona), external systems (third-party integrations), labeled data flow arrows with protocol annotations (HTTPS, gRPC, SMTP).

````markdown
```mermaid
C4Context
    title System Context — <PROJECT_NAME>
    Person(admin, "Admin User", "Manages configuration and users")
    System(system, "<PROJECT_NAME>", "Description from BRD")
    System_Ext(auth_provider, "Auth Provider", "SSO / OAuth2")
    Rel(admin, system, "Manages", "HTTPS")
    Rel(system, auth_provider, "Authenticates via", "HTTPS/OAuth2")
```
````

## Level 2 — Container

Required elements: every IMPLEMENTATION_GUIDELINES Component Inventory item, technology labels (language, framework, version), `ContainerDb`/`ContainerQueue` for data stores/brokers, network boundaries, all Level 1 external systems as `System_Ext`.

````markdown
```mermaid
C4Container
    title Container Diagram — <PROJECT_NAME>
    Person(user, "User", "Interacts via browser or API")
    System_Boundary(system, "<PROJECT_NAME>") {
        Container(api, "API Server", "<LANG>/<FRAMEWORK>", "REST API")
        ContainerDb(db, "Database", "<DB_TECH>", "Primary data store")
    }
    Rel(user, api, "API calls", "HTTPS/JSON")
    Rel(api, db, "Reads/Writes", "SQL/TCP")
```
````

## Validation Checklist
- [ ] All Component Inventory items in Container diagram
- [ ] All BRD Personas as Person nodes in Context diagram
- [ ] All external integrations as System_Ext nodes
- [ ] Technology labels match Tech Stack exactly
- [ ] Every arrow has protocol label
- [ ] No orphan containers (all have >= 1 relationship)
- [ ] Mermaid syntax renders without errors

## Rules
- Use names/technologies directly from IMPLEMENTATION_GUIDELINES
- Do not invent infrastructure not in specs
- If >12 containers, split into domain-specific Level 2 diagrams
- Include port numbers where known
