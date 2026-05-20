---
command: research
description: "Ultra-deep product & market research. Analyzes vendors, capabilities, personas, data requirements, and competitive moats. Produces research/ folder that seeds /init."
arguments:
  - name: domain
    required: true
    description: "Product domain to research (e.g., 'XDR/EDR cybersecurity', 'observability platform', 'API gateway')"
  - name: depth
    required: false
    default: "deep"
    description: "Research depth: 'quick' (1-2 hours), 'deep' (full 6-phase), 'ultra' (deep + technical architecture analysis)"
  - name: focus
    required: false
    description: "Focus on specific aspect: 'vendors', 'capabilities', 'technical', 'personas', 'moats', or 'all' (default)"
---

# /research — Ultra-Deep Product & Market Research

Produces comprehensive market research that feeds into `/init` as the `requirements/` folder. Research is thorough enough that BRD sections auto-generate from it.

**Output:** `requirements/research/` | **Next step:** `/startup:init` reads `requirements/` and produces BRD.

---

## How It Works

```
Step 0:  Scope & Strategy     Define product category and research plan
Step 1:  Market Landscape     6 parallel research agents gather vendor + market data
Step 2:  Capability Matrix    Build feature taxonomy from vendor research
Step 3:  Technical Deep Dive  Architecture, data model, technology analysis
Step 4:  Persona & Workflow   Map user types and critical workflows
Step 5:  Gap & Moat Analysis  Identify opportunities and defensible advantages
Step 6:  Requirements Seed    Auto-generate draft BRD sections
Step 7:  Human Review         Present findings, user refines priorities
```

---

## Step 0 — Scope & Strategy

Define research target: product category, 6 core research questions (vendors, capability taxonomy, technical architecture, personas/workflows, gaps, competitive moat), known context.

---

## Step 1 — Market Landscape (6 PARALLEL Agents)

| Agent | Search Focus | Output |
|-------|-------------|--------|
| Vendor Discovery | Gartner, Forrester, G2, industry reports | `01-vendors.md` |
| Market Dynamics | Market size, growth, funding, M&A | `02-market-dynamics.md` |
| Vendor Leaders | Top 5-8 product pages, docs, pricing | `03-vendor-leaders.md` |
| Vendor Challengers | Next 10-15 vendors, funding | `04-vendor-challengers.md` |
| Open Source | GitHub, community projects | `05-open-source.md` |
| Regulatory | Compliance frameworks (SOC2, HIPAA, PCI) | `06-compliance.md` |

All agents follow `deep-research.md` skill pack format.

---

## Step 2 — Capability Matrix + Integration Ecosystem

**Depends on:** Step 1

Three parallel sub-agents:
- **Taxonomy Builder** — extract every feature from all vendors → hierarchical taxonomy, rate vendors per capability → `07-capability-matrix.md`
- **Capability Detail** — HOW vendors implement each capability, data requirements, build/buy assessment → `07b-capability-details.md`
- **Integration Ecosystem** — map vendor integrations, catalog categories, assess effort → `07c-integration-ecosystem.md`

Capabilities become FR-* requirements, integrations become architecture decisions.

---

## Step 3 — Technical Deep Dive (PARALLEL with Step 2)

**Depends on:** Step 1

- **Architecture Patterns** — how leaders architect systems → `08-architecture.md`
- **Data Requirements** — collection, storage, retention, privacy → `09-data-requirements.md`
- **Tech Stack Survey** — common tech choices and rationale → `10-tech-stack.md`

---

## Step 4 — Persona & Workflow Mapping

**Depends on:** Step 2

Identify personas from vendor marketing/docs/job postings. For each: role, goals, daily workflows, pain points, tools, metrics. Map capabilities per persona. Identify workflow gaps.

**Output:** `11-personas.md`

---

## Step 5 — Gap & Moat Analysis

**Depends on:** Steps 2 + 3 + 4

Analyze: capability gaps (no vendor does well), segment gaps (underserved buyers), UX gaps (painful workflows), integration gaps (missing connections), technical moats (hard to build), business moats (network effects, data advantages).

**Output:** `12-gaps-and-moats.md`

---

## Step 6 — Requirements Seed

Auto-generate from all research:
- `draft-brd-objectives.md` — from gaps + moats
- `draft-brd-personas.md` — from persona research
- `draft-brd-requirements.md` — from capability taxonomy (prioritized)
- `draft-brd-nfrs.md` — from technical + compliance
- `draft-brd-constraints.md` — from regulatory + market
- `draft-brd-differentiators.md` — from moat analysis
- `IMPLEMENTATION_GUIDELINES.md` — from tech stack research

---

## Step 7 — Human Review

Present: key findings (vendor/capability/persona counts, market size), top 5 competitive gaps, recommended moat strategy, draft requirements generated. User reviews `requirements/research/`, modifies priorities, then runs `/startup:init`.

---

## Research Agent Guidelines

- **Cite everything** — vendor name + URL for every claim
- **Quantify** — revenue, customers, funding, response times (not "large" or "fast")
- **Cross-reference** — verify claims across 2+ sources
- **Prefer primary sources** — vendor docs over analyst summaries
- **Check recency** — flag data older than 18 months
- **Include contrarian views** — criticisms and limitations too
- **Search job postings** — reveals what vendors are building NEXT
- **Search GitHub** — reveals actual open-source capabilities
- **Search SEC filings** — public company revenue/customer data
- **Search patent filings** — R&D direction
