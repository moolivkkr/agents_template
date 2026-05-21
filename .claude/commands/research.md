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
Step 0:    Scope & Strategy           Define the exact product category and research plan
Step 1:    Market Landscape           6 parallel research agents gather vendor + market data
Step 2:    Capability Matrix          Build complete feature taxonomy from vendor research
Step 3:    Technical Deep Dive        Architecture, data model, technology analysis
Step 3.5:  Behavioral Edge Cases      Document boundary behavior for every P0 capability
Step 3.6:  Performance Baselines      Research SLAs, user perception thresholds, competitor benchmarks
Step 3.7:  Visual Specifications      Exact measurements for UI fidelity targets (UI products only)
Step 4:    Persona & Workflow         Map every user type, their interaction journeys, SLA expectations
Step 5:    Gap & Moat Analysis        Identify opportunities and defensible advantages
Step 6:    Requirements Seed          Auto-generate draft BRD sections from all research
Step 6.5:  Contradiction Audit        Cross-check research findings against input requirements for conflicts
Step 6.8:  Completeness Self-Audit    Verify all 17 gap-analysis dimensions are covered before handoff
Step 7:    Human Review               Present findings, user refines priorities
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
7. **What are the behavioral edge cases?** (where do users hit unexpected behavior?)
8. **What are the evidence-based performance expectations?** (not assumptions)

## Known Context
[Anything the user already knows — target market, tech preferences, constraints]

## Evaluation Framework
Load `.claude/skills/core/vendor-comparison-framework.md` and select applicable dimensions:
- SaaS/enterprise product → all 18 dimensions
- Developer tool / OSS → dimensions 1-5, 8-9, 13-14, 17
- Consumer product clone → dimensions 1, 2, 9, 13-14
- Internal tool → dimensions 1-5, 9, 12
- API/infrastructure → dimensions 1-3, 5-6, 8-9

Document which dimensions apply and which are N/A (with reason).
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

### Vendor Evaluation Standards (from vendor-comparison-framework.md)

For every vendor, competitor, or OSS project evaluated:

**Claim classification** — categorize EVERY capability claim:
- **Vendor-stated** — from marketing materials or sales decks (lowest confidence)
- **Independently-verified** — confirmed via documentation, live demo, or hands-on testing
- **Customer-reference-verified** — confirmed by a named customer or peer review

**Capability labeling** — use graduated labels, not binary:
- **Full** — complete implementation, production-ready
- **Partial** — exists but limited (document what's missing)
- **Gap** — not offered
- **Roadmap** — announced but not deployed (flag as ANNOUNCED vs ROADMAP)

**OSS-specific evaluation** (when applicable):
- License type and SaaS implications (AGPL, BSL, SSPL risks)
- Governance model (foundation vs. single-vendor — relicensing risk: HashiCorp, Elastic precedents)
- Community health: contributor count, bus factor, commit frequency, issue response time
- Fork risk history

---

## Step 2 — Capability Matrix + Integration Ecosystem

**Depends on:** Step 1 (all vendor research complete)

```
Step 2 (PARALLEL sub-agents):
  ├─ Agent: Capability Taxonomy Builder
  │   Extract EVERY feature from ALL vendors → hierarchical taxonomy
  │   Group into capability clusters (product pillars)
  │   Rate each vendor on each capability
  │   Output: requirements/research/07-capability-matrix.md
  │
  ├─ Agent: Capability Detail Researcher
  │   For each capability: HOW vendors implement it, data requirements,
  │   user expectations, integration points, build/buy/integrate assessment
  │   Output: requirements/research/07b-capability-details.md
  │
  └─ Agent: Integration Ecosystem Analyzer
      Map EVERY vendor's integration ecosystem
      Catalog ALL integration categories (data sources, actions, enrichment, compliance)
      Assess integration effort for our product (must-have vs nice-to-have)
      Output: requirements/research/07c-integration-ecosystem.md
```

This is the most valuable step — capabilities become FR-* requirements, integrations become architecture decisions.

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

## Step 3.5 — Behavioral Edge Cases (CRITICAL — NEW)

**Depends on:** Step 2 (capability matrix must exist)
**Business impact:** Without this step, implementation teams make inconsistent assumptions about undefined behavior. This causes 20-30% rework when edge cases surface during QA or user testing. Every ambiguous behavior that reaches code without a documented decision = a future bug report.

For EVERY P0 capability in the capability matrix, systematically research and document:

### What to Research

```
1. BOUNDARY BEHAVIOR
   - What happens at zero input? Negative input? Maximum value?
   - What happens on overflow? Underflow? Empty input?
   - Example: Calculator display at exactly 9 digits vs 10 digits — when does notation switch?

2. INVALID INPUT
   - What happens with wrong data type? Special characters? SQL injection chars?
   - What happens when user pastes garbage from clipboard?
   - What happens with conflicting state (e.g., two decimal points)?
   - Example: Paste "abc" into a number field — ignore? error? partial parse?

3. STATE-DEPENDENT BEHAVIOR
   - Same operation producing DIFFERENT results based on current state
   - This is the #1 source of wrong implementations
   - Example: "%" means "divide by 100" standalone, but "add X% of left operand" when chained

4. OPERATION SEQUENCING
   - What happens when operations combine unexpectedly?
   - Operator after operator, equals after equals, function after error, rapid input
   - Example: Press "+" then "−" — does it replace the operator or subtract?

5. ERROR RECOVERY
   - Exact path from EVERY error state back to valid state
   - Which buttons work in error state? Which don't?
   - Does pressing a digit clear the error? Or only AC?
   - Example: After "Error" (division by zero) — can you press "5" to start fresh?

6. COPY/PASTE
   - Paste valid number, paste text, paste formatted number (with commas/currency)
   - Paste number with multiple decimal points
   - Copy result — what format? With or without thousands separators?

7. DISPLAY FORMATTING
   - At what exact point does auto-scaling font size kick in?
   - Do thousands separators appear DURING input or only after result?
   - When do trailing zeros get stripped? During input or only on result display?
```

### Output Format

```markdown
## Edge Cases: [Feature Name]

| # | Input/Action | Precondition | Expected Behavior | Source | Verified? |
|---|-------------|-------------|-------------------|--------|-----------|
| 1 | Press % with no pending operator | Display shows "50" | 50 / 100 = 0.5 | Apple docs | Yes |
| 2 | Press % after + operator | "100 + 10 %" | 100 + (10% of 100) = 110 | Tested on macOS | Yes |
| 3 | Press % after × operator | "100 × 50 %" | 100 × 0.5 = 50 | Tested on macOS | Yes |
| 4 | Paste "abc" | Any state | Ignore paste, no state change | ASSUMPTION | No |
```

**Output:** `requirements/research/08b-edge-cases.md`

**CRITICAL:** Mark unverifiable behaviors as **ASSUMPTION** — these MUST be flagged for human review before `/init` consumes them.

---

## Step 3.6 — Performance Baselines & SLA Research (NEW)

**Depends on:** Steps 1 + 3
**Business impact:** Without evidence-based performance targets, NFRs are pulled from thin air. Too aggressive = wasted engineering effort on premature optimization. Too lenient = poor user experience and trust erosion. Every NFR-PERF-* should trace to actual research, not a guess.

### What to Research

```
1. USER PERCEPTION THRESHOLDS (cite UX research)
   Source: Jakob Nielsen / NNGroup / Google Web Vitals
   - Instant feedback: < 100ms (user feels system is reacting directly)
   - Responsive: 100ms - 1s (user notices delay but stays focused)
   - Attention break: > 1s (user's flow of thought is interrupted)
   - Abandonment: > 3s (user may leave or lose trust)

2. COMPETITOR BENCHMARKS (measure real products)
   - Run Lighthouse on 3-5 competitor/similar products
   - Document: Performance score, FCP, LCP, TBT, CLS
   - Document: Bundle sizes (view-source or DevTools Network tab)
   - Document: Time to Interactive

3. DOMAIN-SPECIFIC SLAs
   - What response time does THIS type of product demand?
   - For a calculator: users expect INSTANT response (< 50ms)
   - For a dashboard: users tolerate 1-2s initial load
   - What's the cost of being slow? (user abandonment curves, trust research)

4. INFRASTRUCTURE BASELINES
   - Typical PostgreSQL simple query latency: 1-5ms
   - Go HTTP handler overhead: < 1ms
   - React render cycle: 5-15ms
   - Network round trip (localhost): < 1ms
   - Network round trip (same region): 10-50ms

5. PER-PERSONA SLA EXPECTATIONS
   | Persona | Operation | Expected Latency | Why | Source |
   |---------|-----------|-----------------|-----|--------|
   | Power User | Keyboard input → display update | < 16ms (1 frame) | Types rapidly, expects instant | Nielsen |
   | End User | Button click → result | < 100ms | Feels instant | NNGroup |
   | Developer | Page load → interactive | < 2s | Typical web app expectation | Web Vitals |
```

**Output:** `requirements/research/08c-performance-baselines.md`

Every NFR-PERF-* in the draft BRD MUST trace to a finding in this document.

---

## Step 3.7 — Visual Specifications (UI Products Only — NEW)

**Depends on:** Step 1
**Business impact:** For any product with a UI fidelity goal (e.g., "pixel-accurate recreation"), research must produce measurable visual specs. Without exact measurements, the UI phase becomes subjective ("does this look right?") instead of objective ("is this 12px border-radius or 16px?"). This prevents infinite design iteration cycles.

**Skip this step** if the product has no visual fidelity goal.

### What to Research

```
1. COLOR PALETTE — every unique color with hex values
   | Element | Light Mode | Dark Mode |
   |---------|-----------|-----------|
   | Background | #FFFFFF | #1C1C1C |
   | Number button | #E0E0E0 | #505050 |
   | Operator button | #FF9500 | #FF9500 |
   | Button text | #000000 | #FFFFFF |
   | Hover state | +10% brightness | +10% brightness |
   | Active state | -10% brightness | -10% brightness |

2. TYPOGRAPHY
   | Context | Font | Weight | Size |
   |---------|------|--------|------|
   | Display result | SF Pro Display / system | 300 (Light) | 48px |
   | Button label (number) | SF Pro Display / system | 400 | 24px |
   | Button label (operator) | SF Pro Display / system | 400 | 28px |

3. SPACING & DIMENSIONS
   | Element | Width | Height | Padding | Margin/Gap |
   |---------|-------|--------|---------|-----------|
   | Button (standard) | 72px | 48px | — | 1px |
   | Button (zero, wide) | 146px | 48px | — | 1px |
   | Calculator window (basic) | 320px | 420px | — | — |
   | Display area | 100% | 80px | 16px | — |

4. BORDER RADIUS
   | Element | Radius |
   |---------|--------|
   | Calculator window | 12px |
   | Buttons | 12px (or 50% if circular in Sequoia) |
   | Display area | 0 |

5. SHADOWS & EFFECTS
   - Window shadow: 0 20px 60px rgba(0,0,0,0.3)
   - Button: none (flat)
   - Glassmorphism: backdrop-filter: blur(20px)

6. INTERACTIVE STATES per element
   | Element | Default | Hover | Active | Focused |
   |---------|---------|-------|--------|---------|

7. ANIMATIONS
   | Trigger | Property | Duration | Easing |
   |---------|----------|----------|--------|
   | Button press | transform: scale(0.95) | 100ms | ease-out |
   | Button release | transform: scale(1) | 100ms | ease-out |
   | Mode switch | width, height | 300ms | ease-in-out |
   | History panel | transform: translateX | 250ms | ease-out |

8. AUTO-SCALING RULES
   | Content Length | Font Size | When |
   |--------------|-----------|------|
   | 1-6 digits | 48px | Normal |
   | 7-9 digits | 36px | Getting long |
   | 10+ digits | 24px | Overflow to scientific notation |
```

**Output:** `requirements/research/08d-visual-specifications.md`

Every visual claim must include source: documentation URL, measured from screenshot, or inferred (flagged as ASSUMPTION).

---

## Step 4 — Persona & Workflow Mapping (ENHANCED)

**Depends on:** Step 2 (capability matrix — need to know what features personas use)

### 4a — Static Persona Profile (same as before)
For each persona: role, goals, daily workflows, pain points, tools, metrics.

### 4b — Feature Interaction Matrix (NEW — REQUIRED)

For EACH persona, create a matrix showing how they interact with every major feature:

```markdown
## Feature Interaction Matrix: P-2 End User

| Feature | Uses It? | Frequency | Criticality | Typical Workflow |
|---------|----------|-----------|-------------|-----------------|
| Basic arithmetic | Yes | 50x/day | Critical | Quick calculations |
| Scientific functions | No | Never | N/A | — |
| Programmer mode | No | Never | N/A | — |
| History panel | Yes | 5x/day | Medium | Review past calculations |
| Keyboard input | Yes | 30x/day | High | Number pad + operators |
| Theme toggle | Once | Setup | Low | Match system preference |
```

### 4c — Journey Maps (NEW — REQUIRED)

For each persona's top 3 workflows, document the EXACT step-by-step interaction:

```markdown
## Journey: P-3 Power User → Hex-to-Binary Conversion

1. User presses Alt+3 to switch to Programmer mode
   - Sees: Programmer keypad with hex A-F, base selector, bit display
   - SLA: Mode switch animation < 300ms

2. User clicks "HEX" base selector
   - Sees: Base indicator changes, A-F keys enable
   - Error path: If already in HEX, no-op
   - SLA: Instant (< 50ms)

3. User types "FF" using keyboard
   - Sees: Display shows "FF", bit display shows 11111111
   - Error path: Typing "G" does nothing (not valid hex)
   - SLA: Keystroke to display < 16ms (1 frame)

4. User clicks "BIN" base selector
   - Sees: Display changes to "11111111", bit display unchanged
   - SLA: Instant (< 50ms)
```

### 4d — Persona-to-NFR Mapping (NEW — REQUIRED)

```markdown
| Persona | Performance Expectation | Accessibility Need | Why |
|---------|----------------------|-------------------|-----|
| P-2 End User | < 100ms button response | Standard (mouse + keyboard) | Casual use, expects "feels instant" |
| P-3 Power User | < 16ms keyboard response | Full keyboard navigation | Types rapidly, any lag breaks flow |
| P-4 Accessibility User | < 100ms result announcement | Screen reader, high contrast, zoom | Relies on assistive technology |
```

**Output:** `requirements/research/11-personas.md`

---

## Step 5 — Gap, Moat & Market Analysis

**Depends on:** Steps 2 + 3 + 3.5 + 4 (need full picture including edge cases)

### 5a — Gap Identification

1. **Capability gaps:** Features no vendor does well (or at all)
2. **Segment gaps:** Buyer types underserved by current market
3. **UX gaps:** Workflows that are possible but terrible
4. **Integration gaps:** Systems that should connect but don't
5. **Edge case gaps (NEW):** Features where competitors have WRONG behavior that we can get right. These are high-value differentiators because users notice correctness immediately.

### 5b — Competitive Positioning (from vendor-comparison-framework dimensions 14, 17)

- **Market leaders** by revenue AND mindshare (often different — verify independently via 10-K, PitchBook)
- **OSS disruptors** with commercial backing that reset pricing floors (e.g., Grafana/Prometheus disrupted observability)
- **Hyperscaler encroachment** — is AWS/Azure/GCP commoditizing this from below?
- **Adjacent platform consolidators** — who's absorbing this category?
- **Differentiation thesis:** What we do that incumbents **structurally cannot** (their architecture, business model, or org structure prevents copying)
- **Anti-thesis (CRITICAL):** What's the **strongest argument AGAINST** our approach? If you can't articulate it convincingly, the thesis hasn't been stress-tested.
- **Wedge strategy:** Narrow entry point where we're 10x better, then expand

### 5c — Market Sizing (from vendor-comparison-framework dimension 13)

- **TAM** — total annual spend globally. Top-down (analyst reports: Gartner, IDC, Forrester) cross-checked with bottom-up (unit economics × buyer count). Always cite year and growth rate.
- **SAM** — realistically serviceable given geography, segment, regulatory, deployment model. Usually 30-40% of TAM.
- **SOM** — realistically capturable in 3-5 years. 1-5% of SAM for new entrant; 10-20% for strong incumbent.
- **CAGR** — segment-specific, not aggregate. Growth hides in averages.
- **Market maturity** — emerging / growth / mature / declining. Maps to Gartner Hype Cycle phase.
- **Market structure** — fragmented (ripe for consolidation) vs. concentrated (top 3 own 60%+)

### 5d — GTM & Acquisition Economics (from framework dimensions 15-16)

If applicable to this product category (skip for internal tools / consumer clones with reason):

- **Primary GTM motion:** sales-led, PLG, channel-led, community-led, marketplace-led
- **Buyer persona and budget owner** — different buyers = different cycles and procurement paths
- **Penetration scenarios:** Model 0.5% / 1% / 2% / 5% of SAM at realistic ACV
  - **Decompose the path:** SAM × capture% = target ARR → ÷ ACV = customers needed → ÷ close rate = qualified opps → ÷ qualification rate = leads needed → ÷ rep quota = reps → × 2 = customer-facing FTE → × 1.8 = total FTE
  - "The binding constraint is usually hiring and org management, not market demand"
- **CAC by channel:** direct sales, channel/VAR, marketplace, PLG, partner
- **CAC payback:** Best-in-class SaaS: <12 months. Acceptable: 12-24. Concerning: >24.
- **LTV/CAC ratio:** >3:1 healthy; >5:1 underinvesting; <1:1 broken
- **Time to value (TTV):** PoC complexity kills deals — if PoC needs 6 weeks, expect attrition

Mark dimensions as **N/A** with reason if not applicable.

### 5e — Moat Strategy

- **Technical moats:** Accuracy, speed, platform extensibility — with defensibility + build effort ratings
- **Business moats:** Network effects, switching costs, integration depth, data advantages, ecosystem lock-in
- **Analyst validation (framework dimension 18):** Gartner MQ / Forrester Wave coverage, reference architecture inclusion (NIST, CISA, MITRE), industry recognition

**Output:** `requirements/research/12-gaps-and-moats.md` (enhanced with market sizing, competitive positioning, GTM economics, and moat strategy)

---

## Step 6 — Requirements Seed

**Depends on:** All previous steps

Auto-generate draft BRD sections directly from research:

```
requirements/
  research/
    01-vendors.md through 08-architecture.md
    08b-edge-cases.md          ← NEW: behavioral edge cases
    08c-performance-baselines.md  ← NEW: evidence-based SLAs
    08d-visual-specifications.md  ← NEW: exact visual measurements
    09-data-requirements.md through 12-gaps-and-moats.md

  GENERATED FROM RESEARCH:
    draft-brd-objectives.md      ← measurable success criteria with SPECIFIC NUMBERS
    draft-brd-personas.md        ← includes feature interaction matrix + SLA expectations
    draft-brd-requirements.md    ← P0 FRs MUST have ACs: happy path + 2 error paths + 1 boundary
    draft-brd-nfrs.md            ← every NFR cites source from 08c-performance-baselines.md
    draft-brd-constraints.md     ← from regulatory + market constraints
    draft-brd-differentiators.md ← from moat analysis + edge case advantages
    IMPLEMENTATION_GUIDELINES.md ← from tech stack research
    contradiction-audit.md       ← NEW: conflicts between spec and research
    completeness-audit.md        ← NEW: gap analysis quality gate
```

These files become the input to `/startup:init`, which produces the final BRD.

---

## Step 6.5 — Contradiction Audit (CRITICAL — NEW)

**Depends on:** Step 6
**Business impact:** A single contradiction between the product spec and research findings can propagate through the entire pipeline — into the BRD, into specs, into code. Catching conflicts HERE prevents full feature rewrites later.

Re-read the original `requirements/` documents (product-spec.md, etc.).
For EVERY claim in the input requirements, verify it against research findings:

```markdown
## Contradiction Audit

| # | Spec Claim | Location | Research Finding | Status | Source |
|---|-----------|----------|-----------------|--------|--------|
| 1 | "follows operator precedence" | product-spec.md FR-1 | Basic mode uses LEFT-TO-RIGHT, not precedence | CONFLICT | Apple Support docs |
| 2 | "Maximum 9-digit display" | product-spec.md FR-1 | macOS shows 10 digits (9 significant + decimal) | CORRECTION | Apple Calculator observation |
| 3 | "< 2 second page load" | product-spec.md NFR-PERF-1 | FCP < 1.0s is current standard; 2s is TTI | REFINEMENT | Web Vitals research |
| 4 | "Division by zero shows Error" | product-spec.md FR-1 | macOS Sequoia shows "Not a Number" | CORRECTION | Apple Support docs |
| 5 | "React + TypeScript" | product-spec.md | Confirmed: best fit for calculator UI | CONFIRMED | 08-architecture.md |

## Status Key
- CONFIRMED: Research supports the claim (cite source)
- CONFLICT: Research disproves the claim (provide correct value + source)
- CORRECTION: Claim is partially wrong (provide corrected version)
- REFINEMENT: Claim is vague, research provides specific numbers
- UNVERIFIABLE: No research data available (flag for human decision)
```

**Output:** `requirements/research/contradiction-audit.md`

**CONFLICTS and CORRECTIONS must be listed prominently at the top** — these are the highest-value findings of the entire research process.

---

## Step 6.8 — Completeness Self-Audit (NEW)

**Depends on:** All previous steps
**Business impact:** Research currently has no quality gate. Without a self-check, incomplete research produces incomplete BRDs, which produce incomplete code. The gap-analysis-checklist has 17 dimensions that downstream agents expect to be covered.

Audit ALL research output against the 17-dimension gap-analysis checklist:

```markdown
## Completeness Audit

| # | Dimension | Covered? | Primary Source | Completeness | Gap if Incomplete |
|---|-----------|----------|---------------|-------------|-------------------|
| 1 | Target Users / Actors | Yes | 11-personas.md | 95% | — |
| 2 | Business Objectives | Yes | draft-brd-objectives.md | 85% | Missing measurement methodology for OBJ-3 |
| 3 | Scope Boundary | Yes | 07-capability-matrix.md | 90% | Out-of-scope items documented |
| 4 | Non-Functional Targets | Yes | draft-brd-nfrs.md + 08c-performance-baselines.md | 90% | — |
| 5 | Error / Failure Handling | Partial | 08b-edge-cases.md | 70% | Missing API error recovery paths |
| 6 | External Integrations | N/A | — | N/A | No external integrations |
| 7 | Data Ownership | Partial | draft-brd-nfrs.md | 60% | Missing session data cleanup policy |
| 8 | Compliance | N/A | — | N/A | No compliance requirements |
| 9 | Rollout / Phasing | Yes | 07-capability-matrix.md | 85% | Phase plan in capability matrix |
| 10 | Disaster Recovery | N/A | — | N/A | Local dev only |
| 11 | Localization / i18n | No | — | 0% | No locale research — thousands sep format? |
| 12 | Data Retention | Partial | draft-brd-nfrs.md | 50% | Session expiry undefined |
| 13-17 | ... | ... | ... | ... | ... |

## Additional Quality Checks

### Can acceptance criteria be written for every FR?
- ✅ FR-1 through FR-5: Yes (08b-edge-cases.md provides boundary cases)
- ⚠️ FR-6 Keyboard: Partial (missing scientific mode shortcuts)
- ⚠️ FR-7 UI Fidelity: Partial (needs 08d-visual-specifications.md values)

### Does every NFR cite a source?
- ✅ NFR-PERF-1 through NFR-PERF-4: Yes (08c-performance-baselines.md)
- ⚠️ NFR-SEC-1: No source (industry standard assumption)

### Does every persona have a journey map?
- ✅ P-1 Developer: Yes
- ✅ P-2 End User: Yes
- ⚠️ P-3 Power User: Partial (Scientific workflow only, missing Programmer)

## Overall Completeness: 78%
## Dimensions below 70%: 2 (Localization, Data Retention)
```

**Output:** `requirements/research/completeness-audit.md`

Any dimension scored below 70% coverage is flagged as **INCOMPLETE**. The user MUST see this audit before proceeding to `/init`.

---

## Step 7 — Human Review

Present research summary for user review:

```markdown
# Research Complete: [Domain]

## Key Findings
- Vendors analyzed: N (Tier 1: N, Tier 2: N, Tier 3: N, Open Source: N)
- Capabilities mapped: N across N categories
- Edge cases documented: N across N P0 features
- Personas identified: N with N workflow journey maps
- Performance baselines: N metrics with sources

## Contradiction Audit Summary
- CONFIRMED: N claims | CONFLICT: N claims | CORRECTION: N claims
- ⚠️ Top conflicts: [list the most impactful conflicts]

## Completeness Audit Summary
- Overall: X% complete across 17 dimensions
- INCOMPLETE dimensions: [list any below 70%]

## Top 5 Competitive Gaps (our opportunity)
1. [Gap 1 — what's missing, why it matters]
2. [Gap 2]
...

## Draft Requirements Generated
- Objectives: N (with measurable criteria)
- Functional requirements: N (with acceptance criteria on all P0s)
- Personas: N (with interaction matrices and journey maps)
- NFRs: N (all citing performance baseline sources)

────────────────────────────────────
Review requirements/research/ — especially:
  • contradiction-audit.md (fix conflicts before /init)
  • completeness-audit.md (fill gaps before /init)
  • 08b-edge-cases.md (verify ASSUMPTION items)
Then run: /startup:init
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
- **Document behavior, not just features** — "what happens when X" is more valuable than "supports X"
- **Flag assumptions** — if you cannot verify a behavior from primary sources, mark it explicitly as **ASSUMPTION** for human review. Never silently guess.
- **Search SEC filings** — for public company revenue/customer data
- **Search patent filings** — reveals technical approaches and R&D direction
