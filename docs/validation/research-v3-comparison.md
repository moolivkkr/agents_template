# V3 Research Output Comparison Report

> **Date:** 2026-05-20
> **Evaluator:** Claude Opus 4.6 (1M context)
> **Subject:** Side-by-side evaluation of V3 research outputs from two parallel SDLC pipeline runs
> **Product:** macOS Calculator web clone (product-spec.md)
> **V3 Feature:** Vendor-comparison-framework with 18 evaluation dimensions, claim classification, market sizing

---

## Executive Summary

V3 introduces the vendor-comparison-framework with 18 evaluation dimensions, claim classification (vendor-stated vs independently-verified), capability labels (Full/Partial/Gap), market sizing, and competitive positioning. Both runs produced high-quality research, but they diverge structurally and in specific depth areas. **Verbose wins on core depth and edge case rigor; Compressed wins on framework adherence and structural organization.**

---

## 1. Structural Comparison

### File Counts & Organization

| Aspect | Verbose (calc) | Compressed (calc-compressed) |
|--------|---------------|----------------------------|
| Total files | 17 | 22 |
| Total lines | 3,339 | 3,065 |
| Lines/file avg | 196 | 139 |
| Structure | Consolidated (features + vendors in one file) | Framework-aligned (01-vendors, 02-market-dynamics, etc.) |
| Unique files (not in other) | IMPLEMENTATION_GUIDELINES.md | 02-market-dynamics, 03-vendor-leaders, 04-vendor-challengers, 05-open-source, 06-compliance, 09-data-requirements, 10-tech-stack, 12-gaps-and-moats, draft-brd-constraints |

**Verbose** consolidates related topics (e.g., `01-macos-calculator-features.md` covers all 4 modes + display + accessibility in 207 lines; `02-existing-web-calculators.md` includes vendors + capability comparison + market sizing + competitive positioning in 148 lines).

**Compressed** follows the vendor-comparison-framework's prescribed file structure: separate files for vendors (01), market dynamics (02), leaders (03), challengers (04), OSS ecosystem (05), compliance (06), etc. This produces more files but each is more focused.

### Content Distribution

| Category | Verbose Lines | Compressed Lines | Notes |
|----------|-------------|-----------------|-------|
| Core features/vendors | 355 (01+02) | 312 (01+02+03+04) | V splits into 2 files; C into 4 |
| Architecture/tech | 261 (03) | 382 (08+10) | C separates architecture from tech stack |
| UI/UX/Visual | 463 (04+08d) | 198 (08d) | V has separate UI patterns file |
| Keyboard/Accessibility | 240 (05) | 80 (06-compliance) | V has deep standalone WCAG + ARIA |
| Capability matrix | 139 (06) | 146 (07) | Comparable |
| Gaps/Positioning | 133 (07) | 136 (12) | Comparable |
| Edge cases | 211 (08b) | 169 (08b) | V has 42 more lines |
| Performance | 146 (08c) | 135 (08c) | Comparable |
| Data model | 0 | 141 (09) | C has dedicated data requirements |
| OSS ecosystem | 0 | 129 (05) | C has dedicated OSS evaluation |
| Personas | 295 (draft-brd-personas) | 157+113 (11+draft-brd-personas) | V's personas are richer in BRD |
| Draft BRD total | 880 | 770 | V has more BRD content |
| Audits | 223 (contradiction+completeness) | 213 (contradiction+completeness) | Comparable |

---

## 2. Per-Category Scoring (0-10 each)

### Category 1: Core Research (features, competitors, architecture, UI, keyboard, capabilities)

| Dimension | Verbose | Compressed | Notes |
|-----------|---------|-----------|-------|
| macOS feature inventory | 10 | 9 | V: 207-line dedicated file with all 4 modes, display behavior, cross-mode features, accessibility. C: distributed across 03-vendor-leaders.md, less granular |
| Competitor analysis | 9 | 9 | V: 3 tiers of competitors + capability comparison. C: 4 files (vendors, leaders, challengers, OSS) with more framework structure |
| Architecture depth | 9 | 9 | V: full frontend/backend structure + DB schema + API. C: ASCII architecture diagram + FSM state machine + same depth |
| UI/UX patterns | 9 | 7 | V: dedicated 04-ui-ux-patterns.md (209 lines) with interaction patterns, responsive breakpoints, touch/mouse/keyboard, theme system. C: only 08d-visual-specifications |
| Keyboard/accessibility | 10 | 7 | V: dedicated 240-line file with complete keyboard map, WCAG requirements, ARIA implementation, screen reader strategy. C: 80-line compliance file covers WCAG but no ARIA detail |
| Capability matrix | 9 | 9 | V: 139 lines with feature interaction matrix. C: 146 lines with L1/L2 hierarchy |

**Verbose core research score: 9.3/10**
**Compressed core research score: 8.3/10**

### Category 2: Edge Cases (08b)

| Metric | Verbose | Compressed |
|--------|---------|-----------|
| Total edge cases documented | 98 | ~85 |
| Categories covered | 12 (arithmetic, decimal, %, sign, clear, equals, display, error, memory, backspace, copy/paste, parentheses) | 9 (arithmetic, decimal, %, sign, memory, clear, scientific, programmer, cross-mode, keyboard, display) |
| Verified count | 54 (55%) | ~35 (41%) |
| ASSUMPTION count | 44 (45%) | ~50 (59%) |
| Caught % behavior? | YES (8 cases, 5 verified) | YES (5 cases, all ASSUMPTION) |
| Copy/paste edge cases | 10 dedicated | 3 (in keyboard section) |
| Backspace edge cases | 8 dedicated | 0 (not separately addressed) |
| Programmer mode edges | 0 (not in 08b, covered in capabilities) | 17 dedicated cases |
| Scientific mode edges | 0 (not in 08b, covered in capabilities) | 19 dedicated cases |
| Cross-mode edges | 0 | 4 dedicated cases |
| Summary statistics table | YES (explicit breakdown) | NO |

**Key difference:** Verbose focuses on Basic mode depth (backspace, copy/paste, display formatting each get 8-10 cases). Compressed covers more modes (Scientific + Programmer + Cross-mode edge cases are in 08b). Both catch % behavior. Compressed includes Programmer mode overflow/underflow scenarios that Verbose omits from 08b.

**Verbose edge case score: 8/10** (deeper on basic operations, explicit verified/assumption tracking)
**Compressed edge case score: 7.5/10** (broader mode coverage, but more assumptions, no explicit summary stats)

### Category 3: Performance Baselines (08c)

| Metric | Verbose | Compressed |
|--------|---------|-----------|
| Lines | 146 | 135 |
| Academic citations | YES (NNGroup, 3 references) | YES (NNGroup, 2 references) |
| Core Web Vitals | YES (LCP, INP, CLS, FCP, TTFB with Good/Needs/Poor) | YES (FCP, LCP, CLS, TBT with targets) |
| Domain-specific SLAs | YES (11 operations with latency) | YES (7 operations with latency) |
| Competitor benchmarks | YES (4 competitors with Lighthouse estimates, marked ASSUMPTION) | YES (4 competitors) |
| Per-persona SLAs | YES (4 personas x 3-4 ops each = 11 entries) | YES (3 personas x 3-4 ops = 10 entries) |
| NFR traceability map | YES (7 NFRs mapped to sections) | NO (inline in NFR draft instead) |
| Cost of being slow section | YES (5-tier impact table with sources) | NO |
| Infrastructure baselines | YES (11 component latencies) | YES (5 component latencies) |
| Bundle size budget | YES (4 entries with sizes) | YES (7 entries with detailed breakdown) |
| TTI deprecation noted | NO | YES (TTI removed from Lighthouse 10) |

**Verbose performance score: 9/10** (NFR traceability, cost-of-slow, more infrastructure detail)
**Compressed performance score: 8.5/10** (cleaner budget breakdown, TTI deprecation insight, but less depth)

### Category 4: Visual Specifications (08d)

| Metric | Verbose | Compressed |
|--------|---------|-----------|
| Lines | 254 | 198 |
| Color palette (dark) | 13 hex values | 12 hex values |
| Color palette (light) | 12 hex values | 13 hex values |
| Typography entries | 8 contexts with sizes | 9 contexts (includes programmer-specific SF Mono) |
| Spacing/dimensions | 14 measurements | 12 measurements |
| Interactive states | 12 state definitions across 3 button types | 6 universal state definitions |
| Animation specs | 9 animations with durations | 7 animations with durations |
| Auto-scaling rules | 6 breakpoints | 6 breakpoints |
| Window chrome specs | 10 elements | 8 elements |
| ASSUMPTION percentage (self-reported) | ~75% | ~95% (nearly all) |
| Monospace font for programmer | NO | YES (SF Mono / ui-monospace) |
| Opacity values | NO | YES (per-element opacity) |
| Dark mode orange variant | #FF9500 (same as light) | #FF9F0A (different dark variant!) |
| Verification recommendation | YES (30-minute exercise described) | YES (4-step measurement process) |

**Notable:** Compressed catches that dark mode uses a DIFFERENT orange (#FF9F0A vs #FF9500) -- this is the correct Apple dark mode orange. Verbose uses the same orange for both themes.

**Verbose visual spec score: 8/10** (more interactive states, more measurements)
**Compressed visual spec score: 8/10** (catches dark orange variant, adds opacity, monospace font, but fewer interactive states)

### Category 5: Personas

| Metric | Verbose | Compressed |
|--------|---------|-----------|
| Total personas | 4 (P-1 Dev, P-2 End User, P-3 Power User, P-4 Accessibility User) | 3 (P-1 Dev, P-2 End User, P-3 Power User) |
| Feature interaction matrix | YES (per persona, 7-11 features each) | YES (per persona, 10-13 features each) |
| Journey maps | 4 (Code Review, Tip Calc, Hex-to-Binary, Scientific Computation) | 3 (Tip Calc, Hex-to-Binary, Docker Validation) |
| Per-step SLAs in journeys | YES | YES |
| Error paths in journeys | YES | YES |
| Persona-to-NFR mapping | YES (per persona) | YES (consolidated table) |
| P-4 Accessibility User | YES (dedicated persona) | NO (missing entirely) |
| Persona priority order | NO | YES (explicit conflict resolution priority) |

**Verbose persona score: 8.5/10** (P-4 accessibility persona is a real differentiator, 4 journey maps)
**Compressed persona score: 7.5/10** (missing P-4, but has persona priority order and Docker validation journey)

### Category 6: Contradiction Audit

| Metric | Verbose | Compressed |
|--------|---------|-----------|
| Total claims audited | 26 | 28 |
| CONFLICTS found | 2 | 1 |
| CORRECTIONS found | 6 | 2 |
| REFINEMENTS found | 6 | 5 |
| CONFIRMED | 10 | 20 |
| UNVERIFIABLE | 2 | 0 |
| Operator precedence caught? | YES (CONFLICT #1) | YES (CONFLICT #1) |
| Division by zero text caught? | YES (CONFLICT #2) | YES (CORRECTION #2) |
| 9-digit display issue caught? | YES (CORRECTION #3: "approximately 10 significant digits") | YES (CONFIRMED #3: confirms 9 digits) |
| Memory location error caught? | YES (CORRECTION #4: memory in Scientific, not Basic) | NO |
| SF Pro licensing caught? | NO (mentioned in visual specs) | YES (CORRECTION #16) |
| 4th mode (Conversion) caught? | YES (CORRECTION #6) | YES (REFINEMENT #27) |
| RPN mode caught? | YES (CORRECTION #7) | NO (not in contradiction audit) |
| Repeat-equals caught? | YES (CORRECTION #8) | NO (not in contradiction audit) |
| TTI deprecation caught? | NO | YES (in 08c, not contradiction audit) |

**Key difference:** Verbose finds MORE contradictions/corrections (14 non-confirmed vs 8). This is arguably more valuable -- the more issues you surface, the better the BRD. Compressed classifies division-by-zero as CORRECTION rather than CONFLICT (debatable but less impactful framing). Verbose catches memory location error, RPN omission, and repeat-equals omission that Compressed misses.

**Verbose contradiction audit score: 9/10**
**Compressed contradiction audit score: 7.5/10**

### Category 7: Completeness Audit

| Metric | Verbose | Compressed |
|--------|---------|-----------|
| Self-reported overall completeness | 77% | 92% |
| Dimensions assessed | 17 (14 applicable, 3 N/A) | 18 (8 applicable, 8 N/A, 2 partial) |
| Dimensions >= 80% | 9 (64%) | 6+ applicable fully covered |
| Dimensions < 70% (INCOMPLETE) | 3 (i18n 40%, monitoring 50%, documentation 60%) | 0 formally flagged |
| FR AC coverage verification | YES (16 FRs verified) | YES (7 FR groups verified) |
| NFR source traceability | YES (15/15 = 100%) | YES (8/8 = 100%) |
| Persona journey map check | YES (P-4 missing flagged) | YES (3/3 covered) |
| Honesty of score | HIGH (flags 3 incomplete dimensions, admits 77%) | MEDIUM-HIGH (92% but misses P-4, misses i18n gap) |
| Recommendations before /init | 7 specific actions | 6 specific gaps |

**Verbose completeness audit score: 9/10** (brutally honest, flags real gaps, lower self-score is more accurate)
**Compressed completeness audit score: 7/10** (inflated self-score of 92%, misses i18n gap, missing P-4 persona)

### Category 8: V3 Framework Application

#### 8a. Claim Classification (vendor-stated vs independently-verified)

| Metric | Verbose | Compressed |
|--------|---------|-----------|
| Used in research? | YES | YES |
| Where used | 02 (GitHub stars), 04 (button colors), 08c (Lighthouse estimates marked ASSUMPTION) | 01 (all tiers), 02 (market data), 03 (Apple docs), 04 (products), 05 (npm data) |
| Consistency | Moderate -- used in 3-4 files | Good -- used in 6+ files |
| ASSUMPTION label used | Extensively in 08b, 08c, 08d | Extensively in 08b, 08d |

**Verbose: 7/10** (uses claim classification but not consistently across all files)
**Compressed: 8/10** (more consistent usage, applies to more files)

#### 8b. Capability Labels (Full/Partial/Gap/Roadmap)

| Metric | Verbose | Compressed |
|--------|---------|-----------|
| Used in research? | YES | YES |
| Where used | 02 (capability comparison table), 06 (vendor comparison) | 01 (clone ratings), 03 (clone dimensions), 04 (gap summary), 07 (full matrix) |
| Roadmap label used? | No (uses "P2/deferred") | No (uses "P2/deferred") |
| Label definition included? | YES ("Full = complete; Partial = limited; Gap = not offered") | YES (in 01-vendors.md) |

**Verbose: 8/10**
**Compressed: 8/10** (tie -- both use labels effectively)

#### 8c. Market Sizing (TAM/SAM/SOM)

| Metric | Verbose | Compressed |
|--------|---------|-----------|
| Present? | YES | YES |
| TAM value | "N/A -- calculator apps are free utilities" | "$2.09B (global calculators market)" with source |
| SAM value | N/A | N/A (with reason) |
| SOM value | N/A | N/A (with reason) |
| N/A justification | YES ("consumer product clone built to demonstrate SDLC pipeline") | YES ("OBJ-1 explicitly states SDLC pipeline validation") |
| Market maturity stated | YES ("Mature / commodity") | YES ("MATURE / Commoditized") |
| Market structure stated | YES ("Platform-dominated") | YES ("Fragmented") |
| CAGR | N/A | 5.42% with source |
| Adjacent market sizes | NO | YES ($89.4B web dev tools, $390.5B SaaS) |
| M&A events | NO | YES (4 events: Desmos acquisition, Wolfram+ChatGPT, etc.) |

**Verbose: 6/10** (present but minimal -- just N/A with justification)
**Compressed: 8.5/10** (actual TAM figure sourced, adjacent markets, M&A events, CAGR -- much richer even while correctly noting N/A for SAM/SOM)

#### 8d. Competitive Positioning (differentiation thesis + anti-thesis)

| Metric | Verbose | Compressed |
|--------|---------|-----------|
| Differentiation thesis | YES (7-point thesis in 07) | YES (4-point thesis in 12) |
| Anti-thesis | YES (3-point counter-argument in 07) | YES (quoted counter-argument in 12) |
| Resolution/Wedge | YES ("real customer is the development process itself") | YES ("vehicle for demonstrating agentic development") |
| Moat analysis | YES (5 technical moats + 4 business moats with defensibility ratings) | NO (implicit in gap analysis) |
| Wedge strategy | NO | YES (expansion path: 5 steps from narrow to broad) |

**Verbose: 8.5/10** (moat analysis is unique and valuable)
**Compressed: 8/10** (wedge strategy is good, but no moat analysis)

#### 8e. OSS Evaluation (license, governance, fork risk)

| Metric | Verbose | Compressed |
|--------|---------|-----------|
| Dedicated file? | NO | YES (05-open-source.md, 129 lines) |
| Libraries evaluated | 4 in architecture file (decimal.js, big.js, mathjs, native JS) | 4 arithmetic libs + 4 expression parsing + 4 state management + CSS approaches + Go frameworks + PG drivers |
| License info | YES (MIT noted for clones) | YES (MIT for all recommended) |
| npm weekly downloads | NO | YES (decimal.js ~10M, big.js ~8M, etc.) |
| TC39 Decimal proposal | NO | YES (Stage 2, future impact noted) |
| Fork risk | NO | NO (not applicable for chosen libs) |
| Governance assessment | NO | NO |

**Verbose: 5/10** (minimal OSS evaluation embedded in architecture)
**Compressed: 8/10** (dedicated file, comprehensive lib evaluation, TC39 awareness)

#### 8f. GTM Economics

| Metric | Verbose | Compressed |
|--------|---------|-----------|
| Present? | YES (07, Section 7) | YES (12, Section 5d) |
| Marked N/A with reason? | YES | YES |
| Dimensions covered | 5 (GTM motion, buyer persona, penetration, CAC, LTV/CAC -- all N/A) | YES (GTM motion, buyer, monetization path, CAC) |
| Hypothetical analysis | NO | YES ("If commercialized: PLG, npm package, organic SEO") |

**Verbose: 7/10** (complete N/A table with all dimensions)
**Compressed: 7.5/10** (N/A plus hypothetical path adds value)

---

## 3. Framework Application Summary Scores

| V3 Dimension | Verbose | Compressed | Better |
|-------------|---------|-----------|--------|
| Claim classification | 7 | 8 | Compressed |
| Capability labels | 8 | 8 | Tie |
| Market sizing (TAM/SAM/SOM) | 6 | 8.5 | Compressed |
| Competitive positioning | 8.5 | 8 | Verbose |
| OSS evaluation | 5 | 8 | Compressed |
| GTM economics | 7 | 7.5 | Compressed |
| **Framework avg** | **6.9** | **8.0** | **Compressed** |

---

## 4. Aggregate Scoring

| Category | Weight | Verbose | Compressed |
|----------|--------|---------|-----------|
| 1. Core research | 20% | 9.3 | 8.3 |
| 2. Edge cases | 15% | 8.0 | 7.5 |
| 3. Performance baselines | 10% | 9.0 | 8.5 |
| 4. Visual specifications | 10% | 8.0 | 8.0 |
| 5. Personas | 10% | 8.5 | 7.5 |
| 6. Contradiction audit | 10% | 9.0 | 7.5 |
| 7. Completeness audit | 10% | 9.0 | 7.0 |
| 8. V3 Framework application | 15% | 6.9 | 8.0 |
| **Weighted total** | **100%** | **8.42** | **7.82** |

**Quality Score (x100):** Verbose = **842**, Compressed = **782**

---

## 5. Cross-Version Summary Table

| Metric | V1 | V2 | V3 |
|--------|----|----|-----|
| Files (verbose / compressed) | 12/12 | 17/17 | 17/22 |
| Lines (verbose / compressed) | 3199/2900 | 4000/2958 | 3339/3065 |
| Quality score (verbose) | 402 | 621 | 842 |
| Quality score (compressed) | 412 | 588 | 782 |
| **Winner** | **Compressed** | **Verbose** | **Verbose** |
| Operator precedence caught? (V/C) | No/No | Yes/No | **Yes/Yes** |
| Division by zero text caught? (V/C) | ?/? | ?/? | **Yes/Yes** |
| 9-digit error caught? (V/C) | ?/? | ?/? | **Yes (as ~10)/No (confirms 9)** |
| Edge cases documented (V/C) | 0/0 | 110/98 | **98/~85** |
| Claim classification used? (V/C) | No/No | No/No | **Yes/Yes** |
| Capability labels used? (V/C) | No/No | No/No | **Yes/Yes** |
| Market sizing present? (V/C) | No/No | No/No | **Yes (N/A)/Yes (TAM $2.09B)** |
| Differentiation thesis? (V/C) | No/No | No/No | **Yes/Yes** |
| Anti-thesis? (V/C) | No/No | No/No | **Yes/Yes** |
| OSS evaluation? (V/C) | No/No | No/No | **Partial/Yes** |
| GTM economics? (V/C) | No/No | No/No | **N/A noted/N/A + hypothetical** |
| Personas with journeys (V/C) | ?/? | ?/? | **4 personas, 4 journeys / 3 personas, 3 journeys** |
| P-4 Accessibility persona? (V/C) | ?/? | ?/? | **Yes/No** |
| Self-reported completeness (V/C) | ?/? | ?/? | **77% (honest)/92% (optimistic)** |
| Moat analysis? (V/C) | No/No | No/No | **Yes/No** |

---

## 6. Key Findings

### Where Verbose Excels

1. **Contradiction rigor:** 14 non-confirmed findings vs 8. Catches memory location error, RPN omission, repeat-equals omission that Compressed misses entirely. This is the single most valuable research output -- surfacing spec errors before they become bugs.

2. **Keyboard & accessibility depth:** Dedicated 240-line file with complete keyboard map for all modes, WCAG criterion-by-criterion analysis, full ARIA implementation example with live region strategy and screen reader announcement table. Compressed has 80 lines of compliance overview.

3. **Honesty of self-assessment:** 77% completeness with 3 dimensions flagged as incomplete (i18n at 40%, monitoring at 50%, documentation at 60%). This is more useful than Compressed's 92% which misses the same gaps.

4. **P-4 Accessibility persona:** Only Verbose creates a dedicated accessibility user persona with feature interaction matrix and SLA expectations. This is important for a product that claims WCAG 2.1 AA compliance.

5. **UI/UX patterns:** Dedicated file with responsive breakpoints, touch vs mouse vs keyboard considerations, and theme system architecture. Compressed has no equivalent.

6. **Moat analysis:** 5 technical moats and 4 business moats rated by defensibility -- honest conclusion that "there is no durable competitive moat for a calculator clone."

### Where Compressed Excels

1. **Framework structure:** File naming follows the vendor-comparison-framework exactly (01-vendors, 02-market-dynamics, etc.). This makes it easier for downstream agents to find specific research by dimension number.

2. **Market sizing:** Actual TAM figure ($2.09B) with source, CAGR (5.42%), adjacent market sizes, and M&A events. Verbose just says "N/A."

3. **OSS ecosystem:** Dedicated 129-line file evaluating 15+ libraries across 6 categories (arithmetic, parsing, state management, CSS, Go frameworks, PG drivers) with npm download counts and TC39 Decimal proposal awareness.

4. **Data requirements:** Dedicated 141-line file with entity definitions, data volumes, flow diagrams (ASCII), session management, privacy assessment, and input validation rules. Verbose has this scattered across architecture.

5. **Architecture diagram:** ASCII architecture diagram clearly showing the three-tier stack. FSM state machine diagram with explicit state transitions.

6. **Claim classification consistency:** Applied more broadly across more files.

7. **Compressed manages to cover MORE topics in FEWER lines.** 22 files in 3,065 lines vs 17 files in 3,339 lines -- 8% fewer lines covering 29% more files.

### Critical Differences

| Item | Verbose | Compressed | Impact |
|------|---------|-----------|--------|
| Dark mode orange | #FF9500 (same as light) | #FF9F0A (correct dark variant) | C catches a real color difference |
| Programmer mode SF Mono | Not mentioned | Specified (ui-monospace stack) | C catches a real font need |
| Memory buttons in Basic mode | Flagged as CORRECTION (Scientific only) | Not flagged | V catches a spec error |
| Repeat-equals feature | Flagged as CORRECTION (missing from spec) | Not flagged | V catches a spec omission |
| i18n gap | Flagged at 40% completeness | Not flagged | V catches a real gap |
| TTI deprecation | Not mentioned | Noted (Lighthouse 10 removed TTI) | C has more current knowledge |
| Edge case count tracking | Explicit table: 98 total, 54 verified, 44 assumption | No summary table | V is more traceable |

---

## 7. V3 vs V2 Improvements

Both versions show clear V3 improvements over V2:

| V3 Feature | Present in V2? | Present in V3 Verbose? | Present in V3 Compressed? |
|-----------|---------------|----------------------|--------------------------|
| Claim classification | No | Yes (3-4 files) | Yes (6+ files) |
| Capability labels (Full/Partial/Gap) | No | Yes (2 files) | Yes (4 files) |
| TAM/SAM/SOM framework | No | Yes (N/A with reason) | Yes (actual TAM + N/A) |
| Differentiation thesis | No | Yes (7-point) | Yes (4-point) |
| Anti-thesis | No | Yes (3-point) | Yes (quoted) |
| GTM economics | No | Yes (N/A table) | Yes (N/A + hypothetical) |
| OSS evaluation | No | Partial (in architecture) | Yes (dedicated file) |
| Moat analysis | No | Yes (9 moats rated) | No |
| Wedge strategy | No | No | Yes (5-step expansion) |
| Vendor-comparison-framework structure | No | No (consolidated) | Yes (numbered files) |

**V3 added the most value in:** claim classification (building trust in findings), capability labels (making comparisons actionable), and competitive positioning (forcing the anti-thesis which keeps the team honest about the product's actual value).

---

## 8. Verdict

### V3 Winner: **Verbose** (842 vs 782)

Verbose wins because contradiction discovery and completeness honesty are the highest-leverage research outputs. Finding 6 additional spec contradictions before implementation prevents 6 potential rework cycles. The P-4 accessibility persona and the 240-line keyboard/WCAG analysis are directly usable during implementation.

However, the margin is narrower than V2 (842 vs 782 = 60 point gap) compared to V2's gap (621 vs 588 = 33). Compressed improved more from V2 to V3 (+194 points) than Verbose did (+221 points), showing the framework structure benefits the compressed format.

**If the scoring weighted V3 framework adherence more heavily (e.g., 25% instead of 15%), Compressed would win.** The framework's value is in structured downstream consumption, which Compressed delivers better.

### Recommendation

For production SDLC pipeline use, consider a **hybrid approach**:
- Use Compressed's file structure (numbered files matching framework dimensions)
- Use Verbose's depth for core files (edge cases, keyboard/accessibility, personas)
- Use Verbose's contradiction rigor (flag more, not fewer)
- Use Compressed's market sizing approach (provide actual figures even when N/A)
- Use Verbose's honesty in completeness audits (flag gaps, don't inflate scores)
