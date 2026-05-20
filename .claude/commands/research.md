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

Produces comprehensive market research that directly feeds into `/init` as the `requirements/` folder. The research is so thorough that BRD sections auto-generate from it.

**Output:** `requirements/research/` directory with structured analysis documents.

**Next step after research:** `/startup:init` reads `requirements/` and produces the BRD.

---

## How It Works

```
Step 0:  Scope & Strategy     Define the exact product category and research plan
Step 1:  Market Landscape     6 parallel research agents gather vendor + market data
Step 2:  Capability Matrix    Build complete feature taxonomy from vendor research
Step 3:  Technical Deep Dive  Architecture, data model, technology analysis
Step 4:  Persona & Workflow   Map every user type and their critical workflows
Step 5:  Gap & Moat Analysis  Identify opportunities and defensible advantages
Step 6:  Requirements Seed    Auto-generate draft BRD sections from all research
Step 7:  Human Review         Present findings, user refines priorities
```

---

## Step 0 — Scope & Strategy

Define the research target:

```markdown
# Research Brief

## Product Category
[e.g., "Extended Detection and Response (XDR) / Endpoint Detection and Response (EDR)"]

## Research Questions
1. Who are ALL the vendors in this space? (from market leaders to startups)
2. What is the COMPLETE capability taxonomy? (every feature any vendor offers)
3. How are these products built technically? (architectures, data models, tech stacks)
4. Who uses these products? (every persona, every workflow)
5. What's missing? Where can we build something better?
6. What's our defensible competitive moat?

## Known Context
[Anything the user already knows — target market, tech preferences, constraints]
```

---

## Step 1 — Market Landscape (6 PARALLEL Research Agents)

Launch 6 specialized research agents simultaneously:

```
Step 1 (ALL PARALLEL):
  ├─ Agent 1: Vendor Discovery (Tier 1-4)
  │   Search: Gartner Magic Quadrant, Forrester Wave, G2 Grid, industry reports
  │   Output: requirements/research/01-vendors.md
  │
  ├─ Agent 2: Market Dynamics
  │   Search: Market size reports, growth projections, funding rounds, M&A
  │   Output: requirements/research/02-market-dynamics.md
  │
  ├─ Agent 3: Vendor Deep Dive — Leaders
  │   Search: Product pages, docs, pricing for top 5-8 vendors
  │   Output: requirements/research/03-vendor-leaders.md
  │
  ├─ Agent 4: Vendor Deep Dive — Challengers & Emerging
  │   Search: Product pages, docs, funding for next 10-15 vendors
  │   Output: requirements/research/04-vendor-challengers.md
  │
  ├─ Agent 5: Open Source & Community
  │   Search: GitHub, community projects, open-source alternatives
  │   Output: requirements/research/05-open-source.md
  │
  └─ Agent 6: Regulatory & Compliance Landscape
      Search: Compliance frameworks that drive adoption (SOC2, HIPAA, PCI, etc.)
      Output: requirements/research/06-compliance.md
```

Each agent follows the `deep-research.md` skill pack format.

---

## Step 2 — Capability Matrix

**Depends on:** Step 1 (all vendor research complete)

Synthesize all vendor research into the COMPLETE capability taxonomy:

1. Read all vendor deep dive files from Step 1
2. Extract every feature/capability mentioned by ANY vendor
3. Organize into hierarchical taxonomy (Category → Subcategory → Feature)
4. Build the Vendor × Capability matrix (every vendor rated on every capability)
5. Identify capability clusters (features that always appear together)

**Output:** `requirements/research/07-capability-matrix.md`

This is the most valuable artifact — it becomes the foundation for FR-* requirements.

---

## Step 3 — Technical Deep Dive

**Depends on:** Step 1 (vendor research)
**Can run PARALLEL with Step 2**

```
Step 3 (PARALLEL sub-agents):
  ├─ Agent: Architecture Patterns
  │   Research how leading vendors architect their systems
  │   Output: requirements/research/08-architecture.md
  │
  ├─ Agent: Data Requirements
  │   Research data collection, storage, retention, privacy
  │   Output: requirements/research/09-data-requirements.md
  │
  └─ Agent: Technology Stack Survey
      Research common tech choices and why
      Output: requirements/research/10-tech-stack.md
```

---

## Step 4 — Persona & Workflow Mapping

**Depends on:** Step 2 (capability matrix — need to know what features personas use)

1. Identify every persona type from vendor marketing, docs, and job postings
2. For each persona: role, goals, daily workflows, pain points, tools, metrics
3. Map which capabilities each persona cares about most
4. Identify workflow gaps (things that are possible but painful)

**Output:** `requirements/research/11-personas.md`

---

## Step 5 — Gap & Moat Analysis

**Depends on:** Steps 2 + 3 + 4 (need full picture)

1. **Capability gaps:** Features no vendor does well (or at all)
2. **Segment gaps:** Buyer types underserved by current market
3. **UX gaps:** Workflows that are possible but terrible
4. **Integration gaps:** Systems that should connect but don't
5. **Technical moats:** What's hard to build that creates lasting advantage
6. **Business moats:** Network effects, data advantages, ecosystem lock-in

**Output:** `requirements/research/12-gaps-and-moats.md`

---

## Step 6 — Requirements Seed

**Depends on:** All previous steps

Auto-generate draft BRD sections directly from research:

```
requirements/
  research/
    01-vendors.md
    02-market-dynamics.md
    03-vendor-leaders.md
    04-vendor-challengers.md
    05-open-source.md
    06-compliance.md
    07-capability-matrix.md
    08-architecture.md
    09-data-requirements.md
    10-tech-stack.md
    11-personas.md
    12-gaps-and-moats.md

  GENERATED FROM RESEARCH:
    draft-brd-objectives.md      ← from market gaps + moat analysis
    draft-brd-personas.md        ← from persona research
    draft-brd-requirements.md    ← from capability taxonomy (prioritized)
    draft-brd-nfrs.md            ← from technical deep dive + compliance
    draft-brd-constraints.md     ← from regulatory + market constraints
    draft-brd-differentiators.md ← from moat analysis
    IMPLEMENTATION_GUIDELINES.md ← from tech stack research
```

These files become the input to `/startup:init`, which produces the final BRD.

---

## Step 7 — Human Review

Present research summary for user review:

```markdown
# Research Complete: [Domain]

## Key Findings
- Vendors analyzed: N (Tier 1: N, Tier 2: N, Tier 3: N, Open Source: N)
- Capabilities mapped: N across N categories
- Personas identified: N with N workflow maps
- Market size: $X (CAGR: Y%)

## Top 5 Competitive Gaps (our opportunity)
1. [Gap 1 — what's missing, why it matters]
2. [Gap 2]
...

## Recommended Moat Strategy
[1-paragraph positioning: "We are X for Y because Z"]

## Draft Requirements Generated
- Objectives: N (from market gaps)
- Functional requirements: N (from capability matrix)
- Personas: N (from workflow research)
- NFRs: N (from technical + compliance analysis)

## Files in requirements/
[list all generated files]

────────────────────────────────────
Review the research in requirements/research/.
Modify priorities, add constraints, adjust positioning.
Then run: /startup:init (or /startup:autonomous)
────────────────────────────────────
```

---

## Research Agent Guidelines

All research agents follow these rules:

- **Cite everything** — vendor name + URL for every claim
- **Quantify** — revenue, customers, funding, response times (not "large" or "fast")
- **Cross-reference** — verify claims across 2+ sources
- **Prefer primary sources** — vendor docs/product pages over analyst summaries
- **Check recency** — flag data older than 18 months
- **Include contrarian views** — not just consensus, also criticisms and limitations
- **Search job postings** — reveals what vendors are building NEXT
- **Search GitHub** — reveals actual capabilities of open-source alternatives
- **Search SEC filings** — for public company revenue/customer data
- **Search patent filings** — reveals technical approaches and R&D direction
