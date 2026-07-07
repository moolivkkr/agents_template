---
skill: deep-research
description: Ultra-deep product and market research protocol — vendor/capability/persona analysis feeding /init and /research
version: "1.0"
tags:
  - research
  - market
  - vendors
  - personas
  - core
---

# Deep Research Protocol — Ultra-Deep Product & Market Research

## Purpose

Before writing a single requirement, research the domain so thoroughly that the BRD writes itself. This protocol produces a complete market analysis, capability matrix, persona map, competitive moat strategy, behavioral edge case inventory, evidence-based performance baselines, and completeness audit — all from automated research.

## The Research Framework

```
Phase 1:   Market Landscape       → Who are the players? What do they offer?
Phase 2:   Capability Matrix      → What features exist? What's the full taxonomy?
Phase 3:   Technical Deep Dive    → How are they built? What architectures? What data?
Phase 3.5: Behavioral Edge Cases  → What happens at the boundaries of every P0 feature?
Phase 3.6: Performance Baselines  → What are evidence-based latency/SLA targets?
Phase 3.7: Visual Specifications  → What are the exact measurements? (UI products only)
Phase 4:   Persona & Workflow     → Who uses these products? What are their interaction journeys?
Phase 5:   Gap & Moat Analysis    → What's missing? Where can we differentiate?
Phase 6:   Requirements Seed      → Auto-generate draft BRD sections from research
Phase 6.5: Contradiction Audit    → Do research findings conflict with input requirements?
Phase 6.8: Completeness Audit     → Are all 17 gap-analysis dimensions covered?
```

---

## Phase 1: Market Landscape

### 1a — Vendor Discovery
Research and catalog EVERY vendor in the space:

```markdown
## Vendor Registry

### Tier 1 — Market Leaders (>$500M revenue or >5000 customers)
| Vendor | Founded | HQ | Revenue | Customers | Key Product |

### Tier 2 — Established Players ($50M-$500M)
| Vendor | Founded | HQ | Revenue | Customers | Key Product |

### Tier 3 — Emerging / Startup (<$50M or <3 years old)
| Vendor | Founded | HQ | Funding | Customers | Key Product |

### Tier 4 — Open Source / Community
| Project | Stars | Contributors | License | Commercial Support |
```

### 1a.5 — Startup Deep Dive (CRITICAL — these are your direct competitors)

Startups matter MORE than incumbents for moat analysis. Research EVERY startup in the space:

For each startup (minimum 10-15): Name, Founded, Funding (total + last round + investors), Team background, Technical approach, Go-to-market, Traction, Positioning, Open source strategy, Technical moat claim + actual assessment.

**Startup Comparison Matrix:** Approach | Moat Claim | Funding | Traction | Threat Level

**Research sources for startups:**
- Crunchbase / PitchBook — funding, investors, team
- Product Hunt — launch positioning, early traction signals
- GitHub — OSS repos reveal actual tech stack and approach
- LinkedIn — founder backgrounds, team growth rate
- Job postings — what they're building next
- Y Combinator / TechStars batches — recent cohort companies in this space

### 1b — Market Dynamics
TAM / SAM / SOM estimates with sources. Growth rate (CAGR). Key market drivers. Buyer segments. Pricing models. Distribution channels. Regulatory landscape.

### 1c — Acquisition & Consolidation Map
M&A Activity (last 3 years): Acquirer, Target, Date, Price, Strategic Rationale.
Partnerships: Vendor A, Vendor B, Integration Type, What It Does.

---

## Phase 2: Capability Matrix

### 2a — Feature Taxonomy
Build the COMPLETE feature taxonomy for the product category. Every capability that ANY vendor offers, organized hierarchically.

### 2b — Capability Groups (CRITICAL — must be exhaustive)
Group capabilities into logical clusters that map to product modules. Each group becomes a potential product pillar. For each group: capabilities, description, who needs it, buy vs build assessment, table-stakes vs differentiator.

### 2c — Detailed Capability Specifications
For EACH capability: How vendors implement it (approaches + strengths/weaknesses), data requirements (input, volume, retention, format), user expectations (latency, accuracy), integration points, implementation priority/approach/complexity.

### 2d — Vendor × Capability Matrix
Rate every vendor on every capability: `●●●●` (best) to `○○○○` (not offered).

### 2e — Pricing & Packaging Comparison
Vendor, Pricing Model, Entry Price, Mid-Market, Enterprise, Free Tier.

---

## Phase 2.5: Integration Ecosystem Analysis (CRITICAL)

### Per Major Vendor
- Native integrations (built-in): Integration, Category, Direction, What It Does
- API/SDK: Type, Auth, Rate Limits, Docs Quality
- Marketplace: Items, Categories, Developer Program, Revenue Share

### Integration Categories
1. **Inbound data sources** — with protocols and formats
2. **Outbound actions** — containment, ticketing, notification
3. **Bidirectional enrichment** — with latency budgets per enrichment type
4. **Compliance/Reporting** — GRC, SOAR, Board reporting

### Integration Build Priority
Must-Have at Launch | Must-Have GA+6mo | Nice-to-Have | Platform (webhooks, REST API, SDK, marketplace)

---

## Phase 3: Technical Deep Dive

### 3a — Architecture Patterns
For each major vendor, research: Agent architecture, cloud backend, data pipeline, storage, detection engine, API architecture, integration ecosystem, deployment model.

### 3b — Data Requirements
What data collected, data volume estimates, retention policies (hot/warm/cold), data formats, enrichment sources, privacy considerations.

### 3c — Technology Stack Research
Common technology choices with rationale: agent language, backend, data pipeline, storage, detection, frontend, API — with our consideration.

---

## Phase 3.5: Behavioral Edge Cases (CRITICAL — NEW)

**Business impact:** Without systematically documenting edge cases, implementation teams make inconsistent assumptions about undefined behavior. This is the #1 cause of rework — estimated 20-30% of development time is spent fixing behaviors that were ambiguous in the requirements.

### What to Research

For EVERY P0 capability in the capability matrix:

**1. Boundary Behavior**
- What happens at zero? Negative? Maximum value? Overflow? Underflow? Empty input?
- At what exact threshold does behavior change? (e.g., 9 digits → 10 digits → scientific notation)

**2. Invalid Input**
- What happens with wrong data type? Special characters? Conflicting state?
- What happens when user pastes garbage from clipboard?
- What happens with ambiguous input (e.g., multiple decimal points)?

**3. State-Dependent Behavior**
- Same operation producing DIFFERENT results based on current state
- This is the #1 source of wrong implementations
- Example: `%` means "÷100" standalone, but "add X% of left operand" after `+`

**4. Operation Sequencing**
- What happens when operations combine unexpectedly?
- Operator after operator, equals after equals, function after error, rapid input

**5. Error Recovery**
- Exact path from EVERY error state back to valid state
- Which buttons work in error state? Which don't?
- Is error auto-cleared on next input, or only by explicit clear?

**6. Copy/Paste Behavior**
- Paste valid number, paste text, paste formatted number (commas, currency)
- Copy result — what format? With or without formatting?

**7. Display Formatting Dynamics**
- When does auto-scaling kick in? Exact breakpoints.
- Do thousands separators appear during input or only on result?
- When are trailing zeros stripped?

### Output Format

```markdown
| # | Feature | Input/Action | Precondition | Expected Behavior | Source | Verified? |
```

Mark unverifiable behaviors as **ASSUMPTION** — flagged for human review.

**Output:** `requirements/research/08b-edge-cases.md`

---

## Phase 3.6: Performance Baselines & SLA Research (NEW)

**Business impact:** Without evidence-based targets, NFRs are arbitrary. Too aggressive = wasted engineering effort on premature optimization. Too lenient = poor UX and user trust erosion.

### What to Research

**1. User Perception Thresholds** (cite UX research)
- Instant feedback: < 100ms (Jakob Nielsen, NNGroup)
- Noticeable delay: 100ms-1s
- Attention break: > 1s
- Abandonment: > 3s (Google research on mobile)

**2. Competitor Benchmarks** (measure real products)
- Lighthouse scores of competitor/similar products
- Time to interactive for comparable web apps
- Bundle sizes of comparable React/JS applications

**3. Domain-Specific SLAs**
- What response time does this product type demand?
- Cost of being slow: user abandonment rate, trust erosion research

**4. Infrastructure Performance Baselines**
- Typical DB query latency for chosen database
- HTTP handler overhead for chosen framework
- React render cycle time for component updates
- Network round-trip estimates for target deployment

**5. Per-Persona SLA Expectations**
```markdown
| Persona | Operation | Expected Latency | Why | Source |
```

**Output:** `requirements/research/08c-performance-baselines.md`

Every NFR-PERF-* in the draft BRD MUST trace to a finding in this document.

---

## Phase 3.7: Visual Specifications (UI Products Only — NEW)

**Business impact:** For any product with a visual fidelity goal, research must produce measurable specs. Without exact measurements, the UI phase becomes subjective ("does this look right?") instead of objective ("is this the correct 12px border-radius?").

**Skip this phase** if the product has no visual fidelity goal.

### What to Research

1. **Color palette** — every unique hex color per element, per theme (light + dark)
2. **Typography** — font family, weights, sizes per context (display, buttons, labels)
3. **Spacing** — padding, margins, gaps, button dimensions in px
4. **Border radius** — per element type
5. **Shadows/effects** — box-shadow, backdrop-filter, opacity values
6. **Window dimensions** — per mode/state
7. **Interactive states** — default, hover, active, focused, disabled for every element
8. **Animations** — property, duration, easing for every transition
9. **Auto-scaling rules** — font size breakpoints by content length

Every visual claim must include source: documentation URL, measured from screenshot, or inferred (flagged as ASSUMPTION).

**Output:** `requirements/research/08d-visual-specifications.md`

---

## Phase 4: Persona & Workflow Mapping (ENHANCED)

### 4a — Persona Discovery (same as before)
Research EVERY persona who interacts with this product. For each: Role, daily workflow, pain points, current tools, key metric, what they need from us.

### 4b — Feature Interaction Matrix (NEW — REQUIRED)
For EACH persona, map which features they use, how frequently, and how critically:

```markdown
| Feature | Uses It? | Frequency | Criticality | Typical Workflow |
```

### 4c — Journey Maps (NEW — REQUIRED)
For each persona's top 3 workflows, document the EXACT step-by-step interaction:
- What they see at each step
- What they input
- What they expect to happen
- What can go wrong (error paths at each step)
- SLA expectation per step (reference Phase 3.6)

### 4d — Persona-to-NFR Mapping (NEW — REQUIRED)
```markdown
| Persona | Performance Expectation | Accessibility Need | Why |
```

**Output:** `requirements/research/11-personas.md`

---

## Phase 5: Gap & Moat Analysis

### 5a — Gap Identification
- **Underserved capabilities** (no vendor does this well)
- **Underserved segments** (buyer types not well served)
- **Integration gaps** (things that should connect but don't)
- **UX gaps** (things that are possible but painful)
- **Edge case gaps (NEW)** — features where competitors have WRONG behavior that we can get right. These are high-value differentiators because users notice correctness immediately.

### 5b — Startup-vs-Startup Moat Comparison
Compare on: approach, data architecture, OSS strategy, GTM, funding, team, unique capability.
Assess: Where we can win (realistic), where we're behind (honest), recommended positioning.

### 5c — Competitive Moat Strategy
Technical moats (accuracy, speed, platform) + Business moats (OSS, data network effect, integrations) — with defensibility and build effort ratings.

---

## Phase 6: Requirements Seed (Auto-Generate Draft BRD Sections)

From all research, auto-generate:

- **`draft-brd-objectives.md`** — every objective MUST have measurable success criteria with specific numbers (not "good performance" but "LCP < 1.5s per Web Vitals standard")
- **`draft-brd-personas.md`** — include feature interaction matrix + SLA expectations per persona
- **`draft-brd-requirements.md`** — every P0 FR MUST have acceptance criteria covering: happy path + 2 error paths + 1 boundary case (sourced from 08b-edge-cases.md)
- **`draft-brd-nfrs.md`** — every NFR MUST cite its evidence source from 08c-performance-baselines.md
- **`draft-brd-constraints.md`** — from regulatory + market constraints
- **`draft-brd-differentiators.md`** — from moat analysis + edge case advantages
- **`IMPLEMENTATION_GUIDELINES.md`** — from tech stack research

---

## Phase 6.5: Contradiction Audit (CRITICAL — NEW)

Re-read the original `requirements/` documents (product-spec.md, etc.).
For EVERY claim in the input requirements, verify it against research findings:

```markdown
| Spec Claim | Location | Research Finding | Status | Source |

Status values:
- CONFIRMED: research supports the claim
- CONFLICT: research disproves the claim (provide correct value)
- CORRECTION: claim is partially wrong (provide corrected version)
- REFINEMENT: claim is vague, research provides specific numbers
- UNVERIFIABLE: no research data available (flag for human decision)
```

**Output:** `requirements/research/contradiction-audit.md`

CONFLICTS and CORRECTIONS must be listed prominently at the top.

---

## Phase 6.8: Completeness Self-Audit (NEW)

Audit ALL research output against the 17-dimension gap-analysis checklist:

```markdown
| # | Dimension | Covered? | Primary Source | Completeness | Gap if Incomplete |
```

Additionally verify:
- Can acceptance criteria be written for every FR? If not → gap in edge cases
- Does every NFR cite a source? If not → gap in performance baselines
- Does every persona have a journey map? If not → gap in workflow mapping

**Output:** `requirements/research/completeness-audit.md`

Any dimension below 70% coverage = INCOMPLETE. User must see this before `/init`.

---

## Research Quality Standards

- **Every claim cited** — vendor name, URL, or document
- **Quantitative where possible** — revenue numbers, customer counts, response times
- **Recency bias** — prefer 2025-2026 sources over older data
- **Multiple sources** — cross-reference claims across 2+ sources
- **Primary sources** — competitor product pages, Gartner/Forrester/IDC, GitHub/docs, job postings
- **Document behavior, not just features** — "what happens when X" is more valuable than "supports X"
- **Flag assumptions explicitly** — unverifiable claims marked ASSUMPTION for human review
