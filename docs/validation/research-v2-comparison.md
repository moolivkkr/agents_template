# Research V2 Comparison Report: Verbose vs Compressed Agents

> Generated: 2026-05-20
> Verbose agents: 946-line prompt, 4.0MB .claude/ (calc/)
> Compressed agents: 377-line prompt, 3.4MB .claude/ (calc-compressed/)
> Product: macOS Calculator web clone (same product-spec.md for both)
> V2 Research: 17 files per version (5 new files vs V1's 12 files)

---

## 1. Per-File Scoring Table

### Scoring Dimensions (0-10 each)
- **Coverage** = all expected topics present?
- **Depth** = quality of details, specific values, code patterns?
- **Actionability** = can a developer directly use this?
- **Citations** = real URLs? specific names? quantified claims?

### File-by-File Comparison

| # | File | Dim | VERBOSE | COMPRESSED | Winner |
|---|------|-----|---------|------------|--------|
| 1 | **01-macos-calculator-features.md** | | | | |
| | | Coverage | 9 | 8 | V |
| | | Depth | 9 | 8 | V |
| | | Actionability | 9 | 8 | V |
| | | Citations | 9 | 7 | V |
| | | **Subtotal** | **36** | **31** | **VERBOSE** |
| 2 | **02-existing-web-calculators.md** | | | | |
| | | Coverage | 8 | 9 | C |
| | | Depth | 7 | 8 | C |
| | | Actionability | 8 | 9 | C |
| | | Citations | 7 | 9 | C |
| | | **Subtotal** | **30** | **35** | **COMPRESSED** |
| 3 | **03-technical-architecture.md** | | | | |
| | | Coverage | 10 | 9 | V |
| | | Depth | 10 | 9 | V |
| | | Actionability | 10 | 9 | V |
| | | Citations | 8 | 7 | V |
| | | **Subtotal** | **38** | **34** | **VERBOSE** |
| 4 | **04-ui-ux-patterns.md** | | | | |
| | | Coverage | 9 | 9 | TIE |
| | | Depth | 9 | 9 | TIE |
| | | Actionability | 8 | 9 | C |
| | | Citations | 8 | 7 | V |
| | | **Subtotal** | **34** | **34** | **TIE** |
| 5 | **05-keyboard-accessibility.md** | | | | |
| | | Coverage | 10 | 9 | V |
| | | Depth | 9 | 9 | TIE |
| | | Actionability | 9 | 9 | TIE |
| | | Citations | 9 | 8 | V |
| | | **Subtotal** | **37** | **35** | **VERBOSE** |
| 6 | **06-capability-matrix.md** | | | | |
| | | Coverage | 10 | 9 | V |
| | | Depth | 9 | 8 | V |
| | | Actionability | 10 | 9 | V |
| | | Citations | 7 | 6 | V |
| | | **Subtotal** | **36** | **32** | **VERBOSE** |
| 7 | **07-gaps-and-opportunities.md** | | | | |
| | | Coverage | 9 | 9 | TIE |
| | | Depth | 9 | 8 | V |
| | | Actionability | 9 | 9 | TIE |
| | | Citations | 7 | 6 | V |
| | | **Subtotal** | **34** | **32** | **VERBOSE** |
| 8 | **08b-edge-cases.md** (NEW) | | | | |
| | | Coverage | 10 | 9 | V |
| | | Depth | 10 | 9 | V |
| | | Actionability | 10 | 9 | V |
| | | Citations | 8 | 8 | TIE |
| | | **Subtotal** | **38** | **35** | **VERBOSE** |
| 9 | **08c-performance-baselines.md** (NEW) | | | | |
| | | Coverage | 10 | 9 | V |
| | | Depth | 10 | 9 | V |
| | | Actionability | 10 | 9 | V |
| | | Citations | 9 | 8 | V |
| | | **Subtotal** | **39** | **35** | **VERBOSE** |
| 10 | **08d-visual-specifications.md** (NEW) | | | | |
| | | Coverage | 9 | 9 | TIE |
| | | Depth | 9 | 9 | TIE |
| | | Actionability | 9 | 9 | TIE |
| | | Citations | 8 | 8 | TIE |
| | | **Subtotal** | **35** | **35** | **TIE** |
| 11 | **contradiction-audit.md** (NEW) | | | | |
| | | Coverage | 10 | 10 | TIE |
| | | Depth | 10 | 9 | V |
| | | Actionability | 10 | 9 | V |
| | | Citations | 9 | 8 | V |
| | | **Subtotal** | **39** | **36** | **VERBOSE** |
| 12 | **completeness-audit.md** (NEW) | | | | |
| | | Coverage | 10 | 9 | V |
| | | Depth | 9 | 9 | TIE |
| | | Actionability | 9 | 9 | TIE |
| | | Citations | 8 | 7 | V |
| | | **Subtotal** | **36** | **34** | **VERBOSE** |
| 13 | **draft-brd-objectives.md** | | | | |
| | | Coverage | 10 | 9 | V |
| | | Depth | 9 | 9 | TIE |
| | | Actionability | 10 | 9 | V |
| | | Citations | 9 | 8 | V |
| | | **Subtotal** | **38** | **35** | **VERBOSE** |
| 14 | **draft-brd-personas.md** | | | | |
| | | Coverage | 10 | 9 | V |
| | | Depth | 10 | 9 | V |
| | | Actionability | 10 | 10 | TIE |
| | | Citations | 9 | 8 | V |
| | | **Subtotal** | **39** | **36** | **VERBOSE** |
| 15 | **draft-brd-requirements.md** | | | | |
| | | Coverage | 9 | 9 | TIE |
| | | Depth | 9 | 9 | TIE |
| | | Actionability | 10 | 10 | TIE |
| | | Citations | 8 | 8 | TIE |
| | | **Subtotal** | **36** | **36** | **TIE** |
| 16 | **draft-brd-nfrs.md** | | | | |
| | | Coverage | 10 | 9 | V |
| | | Depth | 10 | 9 | V |
| | | Actionability | 10 | 10 | TIE |
| | | Citations | 10 | 9 | V |
| | | **Subtotal** | **40** | **37** | **VERBOSE** |
| 17 | **IMPLEMENTATION_GUIDELINES.md** | | | | |
| | | Coverage | 10 | 10 | TIE |
| | | Depth | 9 | 9 | TIE |
| | | Actionability | 10 | 10 | TIE |
| | | Citations | 7 | 7 | TIE |
| | | **Subtotal** | **36** | **36** | **TIE** |

---

## 2. Aggregate Scores

| Metric | VERBOSE | COMPRESSED | Delta |
|--------|---------|------------|-------|
| **Total (out of 680)** | **621** | **588** | **+33 (+5.6%)** |
| Total files | 17 | 17 | 0 |
| Total lines | 4,000 | 2,958 | +1,042 (+35%) |
| Total file size | ~183KB | ~142KB | +41KB (+29%) |
| Average per file | 36.5/40 | 34.6/40 | +1.9 |
| Wins | **12** | **1** | |
| Ties | 4 | 4 | |
| Losses | 1 | 12 | |

### Score Distribution by Dimension (totals across 17 files)

| Dimension | VERBOSE (170 max) | COMPRESSED (170 max) | Delta |
|-----------|-------------------|----------------------|-------|
| Coverage | 163 | 154 | +9 |
| Depth | 160 | 150 | +10 |
| Actionability | 161 | 156 | +5 |
| Citations | 140 | 128 | +12 |

**Key insight:** Citations is where the gap is largest (+12 points). The verbose agents produced more sourced claims and cited real URLs more consistently. Depth was the second biggest gap (+10).

---

## 3. Winner per File and Overall

| File | Winner | Margin |
|------|--------|--------|
| 01-macos-calculator-features.md | VERBOSE | +5 |
| 02-existing-web-calculators.md | **COMPRESSED** | +5 |
| 03-technical-architecture.md | VERBOSE | +4 |
| 04-ui-ux-patterns.md | TIE | 0 |
| 05-keyboard-accessibility.md | VERBOSE | +2 |
| 06-capability-matrix.md | VERBOSE | +4 |
| 07-gaps-and-opportunities.md | VERBOSE | +2 |
| 08b-edge-cases.md | VERBOSE | +3 |
| 08c-performance-baselines.md | VERBOSE | +4 |
| 08d-visual-specifications.md | TIE | 0 |
| contradiction-audit.md | VERBOSE | +3 |
| completeness-audit.md | VERBOSE | +2 |
| draft-brd-objectives.md | VERBOSE | +3 |
| draft-brd-personas.md | VERBOSE | +3 |
| draft-brd-requirements.md | TIE | 0 |
| draft-brd-nfrs.md | VERBOSE | +3 |
| IMPLEMENTATION_GUIDELINES.md | TIE | 0 |

### OVERALL WINNER: VERBOSE (621 vs 588, +5.6%)

The compressed agents only won 1 file (02-existing-web-calculators.md) where they found better-sourced competitor projects with direct URLs and more actionable details.

---

## 4. V1 vs V2 Improvement Assessment

### V1 Scores (from previous run, 12 files each)

| Version | V1 Score | V2 Score | Delta | Files |
|---------|----------|----------|-------|-------|
| VERBOSE | 402/480 | 621/680 | +219 (raw), +5.2% (avg/file) | 12 -> 17 |
| COMPRESSED | 412/480 | 588/680 | +176 (raw), +0.3% (avg/file) | 12 -> 17 |

### Normalized Comparison (average score per file, out of 40)

| Version | V1 Avg/File | V2 Avg/File | Change |
|---------|-------------|-------------|--------|
| VERBOSE | 33.5/40 | 36.5/40 | **+3.0 (+9.0%)** |
| COMPRESSED | 34.3/40 | 34.6/40 | **+0.3 (+0.9%)** |

### Key Findings: V1 vs V2

1. **V1 compressed beat verbose. V2 verbose beats compressed.** The roles reversed. In V1, the compressed agents scored 412 vs 402 (compressed won). In V2, verbose scores 621 vs 588 (verbose wins by 33 points).

2. **Verbose agents benefited much more from the V2 prompt improvements.** The verbose agents improved by +3.0 points per file (9.0% improvement). The compressed agents barely improved at +0.3 points per file (0.9%). This suggests the verbose prompts had more "room" to effectively convey the new instructions.

3. **The 5 new files raised the bar.** Edge cases, performance baselines, visual specs, contradiction audit, and completeness audit added specialized depth that requires nuanced instruction-following. The verbose prompts encoded these instructions more completely.

4. **V1 gap was closing; V2 gap widened.** V1 had a 10-point gap favoring compressed. V2 has a 33-point gap favoring verbose. The improved prompts amplified the quality advantage of having more detailed instructions.

---

## 5. Did the 6 Prompt Improvements Actually Work?

### Improvement 1: Edge Cases (08b-edge-cases.md)

| Metric | VERBOSE | COMPRESSED |
|--------|---------|------------|
| Total edge cases documented | **110** | **98** |
| Verified cases | 52 (47%) | 72 (73%) |
| ASSUMPTION cases | 58 (53%) | 26 (27%) |
| Categories covered | 13 | 13 |
| Percentage behavior caught? | **YES** (10 cases, context-dependent behavior fully documented with table showing 5 preconditions) | **YES** (6 cases, context-dependent behavior documented) |
| Copy/paste edge cases | **11 cases** | 7 cases |
| Parentheses edge cases | **6 cases** | 1 case (inline) |

**Verdict: BOTH succeeded, different tradeoffs.**
- Verbose produced MORE edge cases (110 vs 98) with more granularity (copy/paste, parentheses, backspace as dedicated sections).
- Compressed produced HIGHER verification rate (73% vs 47%) -- it was more honest about what it actually verified vs assumed.
- Both caught the critical percentage context-dependent behavior.
- Verbose scores higher on Coverage (10 vs 9) because it found more obscure cases. Compressed scores higher on verification honesty.

### Improvement 2: Performance Baselines (08c-performance-baselines.md)

| Metric | VERBOSE | COMPRESSED |
|--------|---------|------------|
| NFRs cited to sources? | **YES** -- every SLA has a named source | **YES** -- every SLA has a named source |
| Real NNGroup data? | **YES** -- Jakob Nielsen 1993 thresholds + 2017 latency study (54ms median, 34-137ms range) | **YES** -- Jakob Nielsen thresholds cited with URL |
| Real Lighthouse data? | **YES** -- v12 metric weights, CWV thresholds, 2025 Web Almanac pass rates (48% mobile, 56% desktop) | **YES** -- v12 metric weights, CWV thresholds, competitor score estimates |
| RAIL Model? | **YES** -- full 4-category breakdown | Implicit (referenced but not detailed) |
| Bundle budget with math? | **YES** -- React 45KB + decimal.js 12KB + app 50KB + CSS 15KB = 137KB | **YES** -- React 45KB + decimal.js 12KB + app 40KB + CSS 15KB = 150KB |
| SLA traceability table? | **YES** -- 14 numbered SLAs (SLA-1 through SLA-14) | Referenced but no numbered SLA table |
| Per-persona SLAs? | **YES** -- 10 per-persona expectations with sources | **YES** -- 11 per-persona expectations |
| API round-trip budget? | **YES** -- itemized 10ms localhost / 68ms deployed | **YES** -- itemized 5-20ms localhost |

**Verdict: VERBOSE wins clearly.**
- Verbose has the 2017 latency perception study (54ms median) that compressed omits -- a genuinely useful research finding.
- Verbose has the 2025 Web Almanac statistics (48%/56% CWV pass rates) providing real industry context.
- Verbose creates a formal SLA numbering system (SLA-1 through SLA-14) that downstream documents reference consistently. Compressed references "Section 3" and "Section 4" but lacks formal SLA IDs.

### Improvement 3: Visual Specifications (08d-visual-specifications.md)

| Metric | VERBOSE | COMPRESSED |
|--------|---------|------------|
| Exact hex colors (dark mode) | 15 values | 14 values |
| Exact hex colors (light mode) | 13 values | 11 values |
| px dimensions for windows | Basic: 232x322, Scientific: 456x322, Programmer: 456x380 | Basic: 232x340, Scientific: 460x340, Programmer: 460x440 |
| Button dimensions | Standard: 52x40px, Wide: 108x40px, Gap: 1px, Radius: 8px | Standard: 52x52px, Wide: 108x52px, Gap: 8px, Radius: 50% |
| Animation values | 10 animations with durations and easing | 10 animations with durations and easing |
| Auto-scaling breakpoints | 4 tiers (1-6, 7-8, 9-10, 11+) | 8 tiers (1-9, 10, 11, 12, 13, 14, 15, 16+) with scale factors |
| Verification status summary | YES -- 77 specs: 22 verified (29%), 55 ASSUMPTION (71%) | Confidence assessment table with LOW/MEDIUM/HIGH ratings |
| Bit visualization specs | Basic mention | **Detailed layout with cell size (16x20px), nibble gap (6px), byte separator, active/inactive colors** |

**Verdict: TIE (35 vs 35).**
- Verbose has more color values and a formal verification status count.
- Compressed has more granular auto-scaling breakpoints (8 tiers vs 4), correctly identifies Sequoia buttons as fully rounded (50% radius vs 8px), and has better bit visualization specs.
- Both have useful but different strengths. A developer would want to merge both.

### Improvement 4: Contradiction Audit

| Metric | VERBOSE | COMPRESSED |
|--------|---------|------------|
| Total claims audited | **25** | **32** |
| CONFLICTS found | **1** (operator precedence -- CRITICAL) | **1** (9-digit display limit) |
| CORRECTIONS found | **3** (div-by-zero text, digit limit, missing 4th mode) | 0 |
| REFINEMENTS found | 6 | 6 |
| CONFIRMED claims | 11 | 24 |
| UNVERIFIABLE claims | **3** (with specific resolution recommendations) | 0 |
| Operator precedence conflict caught? | **YES** -- flagged as #1 CONFLICT with exact quote and citation | **NO** -- incorrectly marked as CONFIRMED ("PEMDAS, not chain/left-to-right") |
| 9-digit error caught? | **YES** -- flagged as CORRECTION #3 with explanation that macOS shows ~10 digits | **YES** -- flagged as the sole CONFLICT |
| Division-by-zero text caught? | **YES** -- flagged that macOS shows "Not a Number" not "Error" | **NO** -- confirmed "Error" as correct (it is wrong) |
| Missing 4th mode (Conversion) caught? | **YES** -- flagged as CORRECTION #5 | YES -- flagged as REFINEMENT #1 |
| Actionable fix instructions? | **YES** -- 5 specific "FIX product-spec.md" items with exact text changes | YES -- specific resolution for display conflict |

**Verdict: VERBOSE wins decisively.**
This is the most important finding in the entire comparison:

- **Verbose caught the operator precedence conflict.** This is arguably the single most critical bug in the product spec. macOS Basic mode uses LEFT-TO-RIGHT evaluation (2 + 3 * 4 = 20), not PEMDAS (which would give 14). The compressed version incorrectly marked this as CONFIRMED -- a dangerous false negative that would have led to a fundamentally wrong calculator.

- **Verbose caught the division-by-zero text error.** macOS shows "Not a Number", not "Error". Compressed confirmed "Error" as correct.

- **Verbose identified 3 UNVERIFIABLE items** with specific instructions to verify on actual macOS Sequoia -- a more honest and rigorous approach.

### Improvement 5: Completeness Audit

| Metric | VERBOSE | COMPRESSED |
|--------|---------|------------|
| Dimensions assessed | **17** | **17** |
| Overall completeness score | **75%** | **90.3%** |
| Dimensions below 70% | **5** (i18n, observability, compliance, data ownership, data retention) | **0** |
| Honest self-assessment? | **YES** -- brutally honest, identified real gaps | **Optimistic** -- no dimensions below 75% feels inflated |
| FR acceptance criteria audit | **YES** -- all 19 FRs checked, 12 ACs flagged as ASSUMPTION | **YES** -- all 7 FRs checked with happy/error/boundary |
| NFR source audit | **YES** -- 12/13 sourced, 1 partial | **YES** -- 11/12 sourced, 1 partial |
| Persona journey map audit | **YES** -- all 4 personas checked, gaps identified (P-1 and P-4 need more journeys) | **YES** -- all 3 personas checked, 9 journeys total |
| Gap recommendations with effort estimates | **YES** -- 6 recommendations with LOW/MEDIUM effort ratings | **YES** -- 5 known gaps with mitigations |
| i18n gap identified? | **YES** -- scored 10%, flagged as major gap | **YES** -- noted as known gap, but did not penalize score |
| Logging/observability gap? | **YES** -- scored 20%, explicit gap | Not assessed separately |

**Verdict: VERBOSE wins.**
- Verbose produced a genuinely self-critical audit. Scoring itself at 75% with 5 dimensions below 70% shows intellectual honesty. It identified real gaps (i18n at 10%, logging at 20%) that could cause problems downstream.
- Compressed scored itself at 90.3% with zero dimensions below 75% -- this is optimistic. It noted i18n and other gaps but did not penalize its own score, which reduces the audit's value as a quality gate.

### Improvement 6: Enhanced Personas (draft-brd-personas.md)

| Metric | VERBOSE | COMPRESSED |
|--------|---------|------------|
| Personas defined | **4** (Developer, End User, Power User, Accessibility User) | **3** (Developer, End User, Power User) |
| Feature interaction matrices | **YES** -- all 4 personas | **YES** -- all 3 personas |
| Journey maps | **8** total (P-1: 1, P-2: 3, P-3: 3, P-4: 1) | **9** total (P-1: 3, P-2: 3, P-3: 3) |
| SLA per journey step | **YES** -- every step has a specific SLA with source reference | **YES** -- every step has an expected SLA |
| Error paths per journey | **YES** -- every journey includes error paths | **YES** |
| Persona-to-NFR mapping table | **YES** -- explicit 4-persona mapping with SLA references | **YES** -- explicit 3-persona mapping |
| Accessibility persona | **YES** -- P-4 with VoiceOver journey map | **NO** -- accessibility folded into P-2 |

**Verdict: VERBOSE wins.**
- The addition of P-4 (Accessibility User) as a dedicated persona is significant. It forces explicit consideration of screen reader workflows, tab navigation, and announcement timing as first-class requirements. Compressed handles accessibility through NFRs and P-2 but lacks the dedicated persona journey that surfaces real screen-reader UX issues.

---

## 6. Summary: Prompt Improvement Effectiveness

| Improvement | Worked for Verbose? | Worked for Compressed? | Evidence |
|-------------|---------------------|----------------------|----------|
| **Edge cases** | YES (110 cases, 13 categories) | YES (98 cases, 13 categories) | Both produced comprehensive edge case tables with ASSUMPTION tracking |
| **Performance baselines** | YES (14 SLAs, real research data) | YES (sourced but less formal) | Verbose has better industry data (2017 study, Web Almanac) |
| **Visual specifications** | YES (77 specs with verification %) | YES (good specs, confidence ratings) | TIE -- different strengths, both usable |
| **Contradiction audit** | **YES** (caught ALL critical bugs) | **PARTIAL** (missed operator precedence, div-by-zero text) | Verbose caught 2 critical bugs that compressed missed |
| **Completeness audit** | **YES** (honest 75%, real gaps) | **PARTIAL** (optimistic 90%, underweighted gaps) | Verbose self-assessment is more useful as quality gate |
| **Enhanced personas** | **YES** (4 personas incl. accessibility) | **PARTIAL** (3 personas, no dedicated a11y persona) | Verbose added P-4 Accessibility User with VoiceOver journey |

### Overall Prompt Improvement Score

| Agent Type | Improvements Fully Working | Partially Working | Not Working |
|------------|---------------------------|-------------------|-------------|
| VERBOSE | **6/6** | 0/6 | 0/6 |
| COMPRESSED | **3/6** | 3/6 | 0/6 |

The 6 prompt improvements were 100% effective for the verbose agents and ~67% effective for the compressed agents. The compressed agents handled the structured, formulaic improvements (edge cases, performance baselines, visual specs) well, but struggled with the judgment-intensive improvements (contradiction audit, completeness self-assessment, persona enrichment) where the fuller prompt instructions provided crucial context.

---

## 7. Critical Findings

### 7.1 The Operator Precedence Catch

The single most important finding: **Verbose caught that macOS Calculator Basic mode uses LEFT-TO-RIGHT evaluation, not PEMDAS.** This means `2 + 3 * 4 = 20` (not 14). The product-spec.md claims "follows operator precedence" which is wrong for Basic mode (only Scientific mode uses PEMDAS).

The compressed version **incorrectly confirmed this as correct**, which would have resulted in a fundamentally broken calculator. This single catch justifies the entire verbose agent approach.

### 7.2 The Division-by-Zero Text

Verbose caught that macOS shows "Not a Number" (not "Error"). Compressed confirmed "Error" as correct. This is a minor but visible fidelity gap.

### 7.3 The Honesty Gap

Verbose's completeness audit scored itself at 75% with 5 gaps below 70%. Compressed scored itself at 90.3% with zero gaps below 75%. The verbose self-assessment is more honest and more useful -- it identifies real problems (i18n, logging, security model) before they become implementation surprises.

### 7.4 Compression Tax on Judgment Tasks

The 3 improvements that compressed agents struggled with (contradiction audit, completeness audit, persona enrichment) all require nuanced judgment rather than formulaic structure. This suggests that prompt compression works well for structured outputs but loses signal for tasks requiring critical thinking.

---

## 8. Recommendations

1. **Use verbose agents for research** -- the 9% quality improvement and critical bug catches justify the extra prompt size.

2. **The compression savings are real but insufficient for research quality** -- 35% fewer lines and 29% less file size, but at the cost of missing critical contradictions.

3. **Consider hybrid approach** -- compressed agents for structured outputs (capability matrix, implementation guidelines), verbose agents for judgment tasks (contradiction audit, completeness audit, edge cases).

4. **The 6 prompt improvements are validated** -- all 6 produced measurable quality improvements in the verbose run. Keep them in V3.

5. **Contradiction audit is the highest-value new step** -- catching the operator precedence bug alone prevents days of wasted implementation work.

---

## 9. Final Scorecard

| Metric | V1 VERBOSE | V1 COMPRESSED | V2 VERBOSE | V2 COMPRESSED |
|--------|-----------|---------------|-----------|---------------|
| Score (raw) | 402/480 | 412/480 | **621/680** | 588/680 |
| Score (%) | 83.8% | 85.8% | **91.3%** | 86.5% |
| Avg/file | 33.5/40 | 34.3/40 | **36.5/40** | 34.6/40 |
| Winner? | | V1 WINNER | **V2 WINNER** | |
| Files | 12 | 12 | 17 | 17 |
| Critical bugs caught | N/A | N/A | **3** (operator precedence, div-by-zero text, 9-digit limit) | **1** (9-digit limit only) |

**V2 Verbose is the clear winner at 91.3% (621/680), up from V1's best of 85.8%.**

The prompt improvements raised the verbose agent quality by +7.5 percentage points while barely moving the compressed agents (+0.7 pp). The research command V2 improvements are validated, especially for agents with sufficient prompt context to execute them.
