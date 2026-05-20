# Deep Research Protocol — Ultra-Deep Product & Market Research

## Purpose

Before writing a single requirement, research the domain so thoroughly that the BRD writes itself. This protocol produces a complete market analysis, capability matrix, persona map, and competitive moat strategy — all from automated research.

## The 6-Phase Research Framework

```
Phase 1: Market Landscape    → Who are the players? What do they offer?
Phase 2: Capability Matrix   → What features exist? What's the full taxonomy?
Phase 3: Technical Deep Dive → How are they built? What architectures? What data?
Phase 4: Persona & Workflow  → Who uses these products? What are their daily workflows?
Phase 5: Gap & Moat Analysis → What's missing? Where can we differentiate?
Phase 6: Requirements Seed   → Auto-generate draft BRD sections from research
```

---

## Phase 1: Market Landscape

### 1a — Vendor Discovery
Research and catalog EVERY vendor in the space:

```markdown
## Vendor Registry

### Tier 1 — Market Leaders (>$500M revenue or >5000 customers)
| Vendor | Founded | HQ | Revenue | Customers | Key Product |
|--------|---------|-----|---------|-----------|-------------|

### Tier 2 — Established Players ($50M-$500M)
| Vendor | Founded | HQ | Revenue | Customers | Key Product |
|--------|---------|-----|---------|-----------|-------------|

### Tier 3 — Emerging / Startup (<$50M or <3 years old)
| Vendor | Founded | HQ | Funding | Customers | Key Product |
|--------|---------|-----|---------|-----------|-------------|

### Tier 4 — Open Source / Community
| Project | Stars | Contributors | License | Commercial Support |
|---------|-------|-------------|---------|-------------------|
```

### 1b — Market Dynamics
```markdown
## Market Overview
- TAM / SAM / SOM estimates with sources
- Growth rate (CAGR) and projections
- Key market drivers (regulations, threats, trends)
- Buyer segments (enterprise, mid-market, SMB, government)
- Pricing models (per-endpoint, per-user, per-GB, flat)
- Distribution channels (direct, partners, marketplace)
- Regulatory landscape (compliance requirements that DRIVE adoption)
```

### 1c — Acquisition & Consolidation Map
```markdown
## M&A Activity (last 3 years)
| Acquirer | Target | Date | Price | Strategic Rationale |
|----------|--------|------|-------|---------------------|

## Partnerships & Integrations
| Vendor A | Vendor B | Integration Type | What It Does |
|----------|----------|-----------------|-------------|
```

---

## Phase 2: Capability Matrix

### 2a — Feature Taxonomy
Build the COMPLETE feature taxonomy for the product category. Every capability that ANY vendor offers, organized hierarchically:

```markdown
## Capability Taxonomy

### 1. Detection & Prevention
  1.1 Endpoint Detection
    1.1.1 File-based malware detection (signature, heuristic, ML)
    1.1.2 Fileless attack detection (memory, script, LOLBins)
    1.1.3 Behavioral analysis (process trees, anomaly detection)
    1.1.4 Exploit prevention (memory corruption, buffer overflow)
  1.2 Network Detection
    1.2.1 Network traffic analysis (DPI, flow analysis)
    1.2.2 DNS threat detection
    1.2.3 Lateral movement detection
  1.3 Email/Identity Detection
    1.3.1 Phishing detection
    1.3.2 Identity threat detection (impossible travel, credential abuse)
  ...

### 2. Investigation & Response
  2.1 Alert Triage
  2.2 Threat Hunting
  2.3 Forensic Analysis
  2.4 Automated Response (SOAR)
  ...

### 3. Data Collection & Telemetry
  3.1 Endpoint telemetry
  3.2 Network telemetry
  3.3 Cloud telemetry
  3.4 Identity/IAM telemetry
  ...

[Continue for ALL capability areas]
```

### 2b — Vendor × Capability Matrix
For EVERY vendor and EVERY capability, rate coverage:

```markdown
| Capability | Vendor A | Vendor B | Vendor C | ... |
|------------|----------|----------|----------|-----|
| 1.1.1 File malware | ●●●● | ●●●○ | ●●○○ | ... |
| 1.1.2 Fileless | ●●●○ | ●●●● | ●○○○ | ... |
| 1.1.3 Behavioral | ●●●● | ●●○○ | ●●●○ | ... |

Legend: ●●●● = Best in class, ●●●○ = Strong, ●●○○ = Basic, ●○○○ = Minimal, ○○○○ = Not offered
```

### 2c — Pricing & Packaging Comparison
```markdown
| Vendor | Pricing Model | Entry Price | Mid-Market | Enterprise | Free Tier |
|--------|--------------|-------------|-----------|-----------|-----------|
```

---

## Phase 3: Technical Deep Dive

### 3a — Architecture Patterns
For each major vendor, research:
```markdown
## Architecture Analysis: [Vendor]
- Agent architecture (kernel driver? user-mode? eBPF?)
- Cloud backend (multi-tenant? single-tenant? hybrid?)
- Data pipeline (real-time streaming? batch? event-driven?)
- Storage (data lake? time-series DB? graph DB?)
- Detection engine (rules? ML models? behavioral graphs?)
- API architecture (REST? GraphQL? gRPC?)
- Integration ecosystem (SIEM, SOAR, ticketing, cloud)
- Deployment model (SaaS, on-prem, hybrid, air-gapped)
```

### 3b — Data Requirements
```markdown
## Data Model Analysis
- What data do they collect? (processes, files, network, registry, etc.)
- Data volume estimates (GB/day per endpoint)
- Data retention policies (hot/warm/cold storage tiers)
- Data formats (CEF, JSON, STIX/TAXII, custom)
- Data enrichment sources (threat intel, GeoIP, WHOIS, ASN)
- Privacy considerations (PII in telemetry, GDPR, data residency)
```

### 3c — Technology Stack Research
```markdown
## Common Technology Choices in This Space
| Layer | Common Choices | Why | Our Consideration |
|-------|---------------|-----|-------------------|
| Agent language | C/C++, Rust, Go | Performance, low-level access | |
| Backend | Go, Java, Scala | Scale, streaming | |
| Data pipeline | Kafka, Pulsar, Kinesis | Real-time event streaming | |
| Storage | ClickHouse, Elasticsearch, S3+Parquet | Time-series queries + long retention | |
| Detection | Python/ML, YARA, Sigma rules | Flexibility + community rules | |
| Frontend | React, TypeScript | Rich investigation UI | |
| API | REST + GraphQL | CRUD + complex queries | |
```

---

## Phase 4: Persona & Workflow Mapping

### 4a — Persona Discovery
Research EVERY persona who interacts with this product:

```markdown
## Persona: SOC Analyst (Tier 1)
- **Role:** First responder to alerts
- **Daily workflow:** Monitor dashboard → triage alerts → escalate or close
- **Pain points:** Alert fatigue, too many false positives, context switching
- **Tools they use today:** SIEM, ticketing, email, wiki
- **Key metric:** Mean time to triage (MTTT), alerts processed per shift
- **What they need from us:** Fewer false positives, auto-triage, one-click context

## Persona: Threat Hunter
- **Role:** Proactive search for undetected threats
- **Daily workflow:** Form hypothesis → query data → investigate → document findings
- **Pain points:** Slow queries, limited data retention, can't correlate across sources
- ...

## Persona: CISO / Security Director
- **Role:** Strategic oversight, budget, compliance
- **Key concerns:** Risk posture, compliance, ROI, board reporting
- ...

[Map ALL personas with this depth]
```

### 4b — Workflow Mapping
For each persona, map their critical workflows:
```markdown
## Workflow: Alert Investigation (SOC Analyst Tier 1)
1. Alert fires in dashboard
2. Analyst reads alert summary (what, where, when, severity)
3. Analyst checks: is this a known false positive? (lookup in tuning rules)
4. If not known: examine process tree, file details, network connections
5. Check threat intel: is this IOC known malicious?
6. Decision: escalate to Tier 2, close as false positive, or auto-remediate
7. Document decision and evidence

## Workflow: Incident Response (Tier 2/3)
...

## Workflow: Compliance Reporting (CISO)
...
```

---

## Phase 5: Gap & Moat Analysis

### 5a — Gap Identification
From the capability matrix, identify:
```markdown
## Gaps in Current Market

### Underserved Capabilities (no vendor does this well)
| Gap | Current State | Why It Matters | Opportunity Size |
|-----|--------------|----------------|-----------------|

### Underserved Segments (buyer types not well served)
| Segment | Current Options | Why Underserved | Opportunity |
|---------|----------------|-----------------|-------------|

### Integration Gaps (things that should connect but don't)
| System A | System B | Gap | Impact |
|----------|----------|-----|--------|

### UX Gaps (things that are possible but painful)
| Workflow | Current UX | Pain | Better Approach |
|----------|-----------|------|----------------|
```

### 5b — Competitive Moat Strategy
```markdown
## Potential Moats

### Technical Moats
| Moat | Description | Defensibility | Build Effort |
|------|-------------|--------------|-------------|
| Detection accuracy | Better ML models, lower FP rate | HIGH (data advantage) | HIGH |
| Query speed | Sub-second search on petabytes | HIGH (engineering) | HIGH |
| API-first platform | Developers build on top of us | MEDIUM (network effect) | MEDIUM |

### Business Moats
| Moat | Description | Defensibility | Build Effort |
|------|-------------|--------------|-------------|
| Open source core | Community + commercial | HIGH (community lock-in) | MEDIUM |
| Data network effect | More customers = better detection | VERY HIGH | LONG |
| Integration ecosystem | Marketplace of integrations | HIGH (switching cost) | MEDIUM |

### Strategic Positioning
[Where we sit vs incumbents — "we are X for Y" framing]
```

---

## Phase 6: Requirements Seed (Auto-Generate Draft BRD Sections)

From all research above, auto-generate:

```markdown
## Draft Business Objectives (from market analysis)
OBJ-001: [derived from market gap]
OBJ-002: [derived from underserved segment]

## Draft Personas (from persona research)
[Complete persona definitions with workflows]

## Draft Functional Requirements (from capability taxonomy)
FR-001: [each capability becomes a candidate FR]
FR-002: ...

## Draft Non-Functional Requirements (from technical deep dive)
NFR-PERF-001: [from competitor benchmarks]
NFR-SEC-001: [from compliance requirements]
NFR-SCALE-001: [from data volume estimates]

## Draft Constraints (from market dynamics)
CON-001: [regulatory constraints]
CON-002: [deployment constraints]

## Competitive Differentiators (from moat analysis)
[Features/approaches that set us apart]
```

This becomes the input to `/startup:init` — the `requirements/` folder.

---

## Research Quality Standards

- **Every claim cited** — vendor name, URL, or document
- **Quantitative where possible** — revenue numbers, customer counts, response times
- **Recency bias** — prefer 2025-2026 sources over older data
- **Multiple sources** — cross-reference claims across 2+ sources
- **Competitor product pages** — primary source for feature claims
- **Gartner/Forrester/IDC** — for market sizing and positioning
- **GitHub/docs** — for open-source projects' actual capabilities
- **Job postings** — reveal what vendors are building next
