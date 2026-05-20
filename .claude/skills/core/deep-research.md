# Deep Research Protocol — Ultra-Deep Product & Market Research

## Purpose

Research the domain thoroughly before writing requirements. Produces market analysis, capability matrix, persona map, and competitive moat strategy.

## The 6-Phase Research Framework

```
Phase 1: Market Landscape    → Players, offerings, dynamics
Phase 2: Capability Matrix   → Feature taxonomy, vendor comparison
Phase 3: Technical Deep Dive → Architectures, data models, tech stacks
Phase 4: Persona & Workflow  → Users, daily workflows, pain points
Phase 5: Gap & Moat Analysis → Market gaps, competitive positioning
Phase 6: Requirements Seed   → Auto-generate draft BRD sections
```

---

## Phase 1: Market Landscape

### 1a — Vendor Discovery

Catalog EVERY vendor:

| Tier | Criteria | Fields |
|------|----------|--------|
| Tier 1 (Leaders) | >$500M rev or >5000 customers | Vendor, Founded, HQ, Revenue, Customers, Key Product |
| Tier 2 (Established) | $50M-$500M | Same |
| Tier 3 (Emerging) | <$50M or <3 years | + Funding |
| Tier 4 (OSS) | Community-driven | Stars, Contributors, License, Commercial Support |

### 1a.5 — Startup Deep Dive (CRITICAL — direct competitors)

For each startup (min 10-15), document: Name, Founded, Funding (total + last round + investors), Team background, Technical approach, GTM, Traction, Positioning, OSS strategy, Moat claim + actual assessment.

**Startup Comparison Matrix:** Approach | Moat Claim | Funding | Traction | Threat Level

**Sources:** Crunchbase/PitchBook, Product Hunt, GitHub, LinkedIn, job postings, YC/TechStars batches, security conference talks.

### 1b — Market Dynamics

TAM/SAM/SOM, CAGR, key drivers, buyer segments, pricing models, distribution channels, regulatory landscape.

### 1c — M&A & Partnerships

Acquisitions (last 3 years): Acquirer, Target, Date, Price, Rationale. Partnerships: Vendor A, Vendor B, Integration Type.

---

## Phase 2: Capability Matrix

### 2a — Feature Taxonomy

Build COMPLETE hierarchical capability taxonomy (every capability any vendor offers).

### 2b — Capability Groups

Group into logical clusters mapping to product modules. Per group: capabilities, description, who needs it, buy vs build assessment, table-stakes vs differentiator.

### 2c — Detailed Capability Specs

Per capability: How vendors implement it (approaches + strengths/weaknesses), data requirements (input, volume, retention, format), user expectations (latency, accuracy), integration points, implementation priority/approach/complexity.

### 2d — Vendor x Capability Matrix

Rate every vendor on every capability: `●●●●` (best) to `○○○○` (not offered).

### 2e — Pricing Comparison

Vendor, Model, Entry/Mid-Market/Enterprise price, Free tier.

---

## Phase 2.5: Integration Ecosystem Analysis

### Per Major Vendor

- Native integrations (built-in): Integration, Category, Direction, What It Does
- API/SDK: Type, Auth, Rate Limits, Docs Quality
- Marketplace: Items, Categories, Developer Program, Revenue Share

### Integration Categories

1. **Inbound data sources:** SIEM, Cloud, Identity, Network, Email, Threat Intel, Vulnerability
2. **Outbound actions:** Firewall, EDR, IAM, Ticketing, Communication
3. **Bidirectional enrichment:** Threat Intel, GeoIP, WHOIS, Asset, User — with latency budgets
4. **Compliance/Reporting:** GRC, SOAR, Board reporting

### Integration Build Priority

Must-Have at Launch | Must-Have GA+6mo | Nice-to-Have | Platform (webhooks, REST API, SDK, marketplace)

---

## Phase 3: Technical Deep Dive

### 3a — Architecture per vendor: Agent arch, cloud backend, data pipeline, storage, detection engine, API, integrations, deployment model.

### 3b — Data requirements: What collected, volume/endpoint, retention tiers, formats, enrichment sources, privacy.

### 3c — Common tech choices: Agent lang, backend, pipeline, storage, detection, frontend, API — with rationale and our consideration.

---

## Phase 4: Persona & Workflow

### 4a — Per persona: Role, daily workflow, pain points, current tools, key metric, what they need from us.

### 4b — Per persona, critical workflow steps: numbered sequence from trigger to resolution.

---

## Phase 5: Gap & Moat Analysis

### 5a — Gaps

- Underserved capabilities (no vendor does well)
- Underserved segments (buyer types not well served)
- Integration gaps (should connect but don't)
- UX gaps (possible but painful)

### 5b — Startup-vs-Startup Moat Comparison

Compare on: Detection approach, Data architecture, OSS strategy, GTM, Funding, Team, Unique capability.

Assess: Where we can win (realistic), where we're behind (honest), recommended positioning statement.

### 5c — Moat Strategy

Technical moats (accuracy, speed, platform) + Business moats (OSS, data network effect, integrations) — with defensibility and build effort ratings.

---

## Phase 6: Requirements Seed

Auto-generate from research: Draft OBJs (from gaps), Personas (from research), FRs (from taxonomy), NFRs (from benchmarks/compliance), Constraints (from regulations/deployment), Differentiators (from moat analysis).

Output goes to `requirements/` folder for `/startup:init`.

---

## Research Quality Standards

- Every claim cited (vendor, URL, document)
- Quantitative where possible (revenue, customers, response times)
- Prefer 2025-2026 sources; cross-reference 2+ sources
- Primary sources: competitor product pages, Gartner/Forrester/IDC, GitHub/docs, job postings
