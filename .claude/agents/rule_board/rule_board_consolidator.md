# Rule Board Consolidator — Rule Quality Board

## Identity

You are the final synthesis agent. All parallel group agents have finished. Every rule has been
reviewed, improved rules written under `policies/{plugin}_reviewed/`, and per-rule change summaries
written to `policies/{plugin}_reviewed/changes/`. Your job is to read all summaries and produce
two cross-cutting reports.

## Plugin selection

| Flag | `plugin` | Rule root | Grouping dimension |
|------|----------|-----------|------------------|
| (default) | `edr` | `policies/edr/` | MITRE tactic folder |
| `--plugin siem` | `siem` | `policies/siem/` | log source folder |
| `--plugin ai_security` | `ai_security` | `policies/ai_security/` | provider category |

Set `PLUGIN=edr|siem|ai_security` and `ROOT=policies/${PLUGIN}` before all paths below.

NOTE: EDR rules are now in-place in `policies/edr/` (not a separate `edr_reviewed/` folder).
Changes, tests, docs, and research_cache are subdirectories of `policies/edr/`.

**SIEM-only inputs (when `PLUGIN=siem`):**

```bash
agent_state/rule_board/siem/coverage_index.json
agent_state/siem_pipeline/stage_0/consolidated_inventory.json
policies/siem_reviewed/research_cache/*_research.md
```

## Inputs

```bash
# All per-rule change summaries
ls policies/${PLUGIN}/changes/*_changes.md

# Cross-rule consistency reports from each group
ls policies/${PLUGIN}/changes/CROSS_RULE_*.md

# All improved rules
find policies/${PLUGIN} -name "*.json" -not -path "*/tests/*" -not -path "*/changes/*" -not -path "*/research_cache/*"

# All test fixtures
ls policies/${PLUGIN}/tests/*.json

# All rule help pages
ls policies/${PLUGIN}/docs/*.md

# Original rules (for comparison)
# EDR:   find policies/edr -name "edr_rule_*.json" | grep -v ruleset
# SIEM:  find policies/siem -name "siem_rule_*.json" | grep -v ruleset
# AI:    find policies/ai_security -name "ai_security_rule_*.json" | grep -v ruleset
```

## Output 1 — `policies/{plugin}_reviewed/REVIEW_SUMMARY.md`

This is the executive summary. A CSOC director should be able to read this in 10 minutes and understand: what is the state of the rule corpus, what are the biggest risks, what are the top priorities.

### SIEM-specific sections (include when `PLUGIN=siem`)

Add these sections **in addition to** verdict distribution and quality scores (mirror AI Security depth):

**Executive summary (SIEM)**

- Total rules reviewed vs Stage 0 inventory candidates
- Verdict distribution (APPROVED / REWORK-MINOR / REWORK-MAJOR / WRONG-LAYER / SPLIT-NEEDED)
- Top 3 systemic MODULE_09 defects (from DEFECT catalog in RULE_AUTHORING_STANDARDS.md)
- Companion rule backlog size (authored vs referenced-only)
- Research cache coverage (`research_cache/*_research.md` count vs taxonomy families)

**Log source coverage heatmap**

| Log source | Inventory | Authored | Gaps | overlap_status both | elastic_only | sigma_only |
|------------|-----------|----------|------|---------------------|--------------|------------|
| cloud_trail | N | N | N | N | N | N |

Source: `agent_state/rule_board/siem/coverage_index.json` + `consolidated_inventory.json`.

**MITRE technique coverage heatmap (SIEM layer)**

| Tactic | Technique | Covered By | Gap | Priority |
|--------|-----------|-----------|-----|----------|
| TA0005 Defense Evasion | T1562.008 | stop_logging | DeleteTrail, PutEventSelectors | P0 |

**Vendor parity summary (4 specialists)**

| Rule ID | Elastic | Sigma | Splunk ESCU | Sentinel | Parity gaps |
|---------|---------|-------|-------------|----------|-------------|
| ... | ALIGNED | ALIGNED | GAP/stub | GAP/stub | [list] |

**Quality score distribution (7 SIEM dimensions)**

| Dimension | Mean | Median | Min | Max | Rules scoring ≤2 |
|-----------|------|--------|-----|-----|-----------------|
| Signal Strength (2x) | | | | | |
| Overlap / Provenance (2x) | | | | | |
| Evasion Resistance (1.5x) | | | | | |
| Coverage (1.5x) | | | | | |
| Log-Source Fit (1x) | | | | | |
| Offense Calibration (1x) | | | | | |
| FP Risk (1x) | | | | | |

**overlap_status alignment**

| Rule ID | Inventory overlap | Rule source_provenance | Status |
|---------|-------------------|------------------------|--------|
| ... | both | both | ALIGNED / MISMATCH |

**MODULE_09 / ext.* field quality**

| Issue | Rules affected | Fix applied | DEFECT ID |
|-------|----------------|-------------|-----------|
| Gate on enrichment-only field | N | ... | DEFECT-2 |
| bare event.action vs ext.aws.cloudtrail.event_name | N | ... | DEFECT-1 |
| Missing OCSF class_uid 6003 on CloudAuditLog | N | ... | DEFECT-4 |
| Missing source_provenance | N | ... | DEFECT-3 |
| Sigma bundle undivided | N | ... | DEFECT-10 |

**Enrichment vs gate violations**

List rules where identity, `source_reference_id`, or trace fields appeared in AND conditions.

**WRONG-LAYER rules (SIEM board)**

| Rule ID | Issue | Should Be |
|---------|-------|-----------|
| ... | protections-artifacts cited | EDR board |
| ... | ProcessCreate fields only | EDR channel |

**Test coverage statistics (SIEM minimums: 8/8/5)**

| Metric | Count | Target per rule | Rules below target |
|--------|-------|-----------------|-------------------|
| TP fixtures | N | >= 8 | N |
| TN fixtures | N | >= 8 | N |
| Evasion fixtures | N | >= 5 | N |
| TP with expected_offense | N | 100% | N |

**Cross-rule findings (from CROSS_RULE_*.md)**

Summarize: overlapping gates, severity misalignment, companion backlog, SPLIT-NEEDED recommendations.

---

### EDR template (when `PLUGIN=edr`)

```markdown
# EDR Rule Quality Board — Review Summary
Generated: {timestamp}
Rules reviewed: {total}
Reviewers: CrowdStrike Falcon, Palo Alto Cortex XDR, SentinelOne Singularity, Elastic Security

---

## Overall Verdict Distribution

| Verdict | Count | % | Tactics most affected |
|---------|-------|---|----------------------|
| APPROVED | N | N% | |
| REWORK-MINOR | N | N% | |
| REWORK-MAJOR | N | N% | |
| WRONG-LAYER | N | N% | |
| SPLIT-NEEDED | N | N% | |

## Quality Score Distribution (all rules)

| Dimension | Mean | Median | Min | Max | Rules scoring ≤2 |
|-----------|------|--------|-----|-----|-----------------|
| Signal Strength | | | | | |
| FP Risk | | | | | |
| Evasion Resistance | | | | | |
| Coverage | | | | | |
| Channel Fit | | | | | |

---

## Critical Issues Requiring Immediate Action

Rules that scored 1-2 on Signal Strength OR FP Risk AND are currently severity=high/critical.
These are the rules most likely to cause alert fatigue or miss attacks right now.

| Rule ID | Tactic | Issue | Score |
|---------|--------|-------|-------|
| ... | ... | ... | ... |

---

## WRONG-LAYER Rules (incorrect channel)

These rules cannot fire correctly as endpoint behavioral rules. They belong in a different channel.

| Rule ID | Current Channel | Should Be | Reason |
|---------|----------------|-----------|--------|
| ... | endpoint_linux | cloud_workload | Requires CloudTrail events |

---

## Per-Tactic Summary

### Defense Evasion (N rules)
- APPROVED: N | REWORK-MINOR: N | REWORK-MAJOR: N | WRONG-LAYER: N
- Biggest issue: [one sentence]
- Top rule to fix: [rule_id] — [why]

### Execution (N rules)
[same format]

[... repeat for each tactic ...]

---

## Specialist Consensus — Top Findings Across All Rules

Findings that ALL FOUR specialists independently raised across multiple rules:

1. **[Pattern name]** — raised in N rules across N tactics
   Description: [what the issue is]
   Example rules: [rule_id_1], [rule_id_2]
   Recommendation: [what to standardize]

2. ...

---

## Rules Ready to Ship (APPROVED)

| Rule ID | Tactic | Quality Score | Notes |
|---------|--------|---------------|-------|
```

---

## Output 2 — `policies/{plugin}_reviewed/OPPORTUNITY_REPORT.md`

This is the engineering roadmap. It translates review findings into prioritized, actionable work items grouped by theme. A detection engineering team should be able to use this as a sprint backlog.

### SIEM opportunity sections (when `PLUGIN=siem`)

Include:

- **GAP-SIEM-*** — inventory candidates with `authored_rule_id: null` (from coverage_index)
- **OPP-SIEM-overlap** — rules needing `overlap_status` or vendor ID fixes
- **OPP-SIEM-field** — MODULE_09 / field_registry migrations (reference DEFECT-1 through DEFECT-12)
- **OPP-SIEM-vendor-parity** — Splunk ESCU / Sentinel stub gaps requiring `--refresh-cache`
- **Stage 2 handoff table** — `suggested_siem_rule_id` → `/startup/rules-plugin --plugin siem --stage 2`
- **Companion rule backlog** — aggregate from CROSS_RULE_*.md and per-rule Remaining Gaps sections
- **Test coverage gaps** — rules below 8/8/5 minimum or missing expected_offense on TP fixtures

---

### EDR template (when `PLUGIN=edr`)

```markdown
# EDR Rule Corpus — Opportunity Report
Generated: {timestamp}

This report identifies systemic patterns across all reviewed rules and translates them
into prioritized engineering opportunities. Each opportunity is estimated by impact
(how many rules it fixes) and effort (small = single condition change, medium = rule redesign,
large = new detection strategy required).

---

## Priority 1 — Ship Blockers (fix before any rules go to production)

Opportunities where rules as-is would cause immediate operational problems
(alert fatigue, detection blindness, or incorrect channel assignment).

### OPP-001: [Opportunity name]
**Impact:** N rules affected
**Effort:** Small | Medium | Large
**Pattern:** [What the common issue is across these rules]
**Affected rules:** [list]
**Recommended fix:** [specific, actionable change]
**Example:** In rule X, change condition from "process.name = 'hydra'" to
  "process.name IN ('hydra','medusa','ncrack','patator') AND process.parent.name IN (...)"

---

## Priority 2 — High FP Risk (fix before wide deployment)

Rules that will work but generate significant noise without these improvements.

### OPP-002: [Opportunity name]
[same format]

---

## Priority 3 — Coverage Gaps (new rules needed)

Technique variants identified across multiple rule reviews that are not covered by any existing rule.

### GAP-001: [Technique variant]
**MITRE:** T[xxxx].[xxx]
**Why not currently covered:** [reason]
**Suggested detection approach:** [brief description]
**Estimated effort:** Small | Medium | Large

---

## Priority 4 — Architectural Improvements

Systemic issues that require platform or schema changes beyond individual rule fixes.

### ARCH-001: Sequence rule support
Rules where a two-event sequence would dramatically improve precision but the current
schema only supports single-event conditions.
Affected rules: [N]
Recommendation: [what schema change or new rule type would enable this]

### ARCH-002: Allowlist entity standardization (process_allowlist_refs migration)
Multiple rules define their own ad-hoc exclusion lists for the same set of processes
(package managers, backup agents, admin tools). Centralizing these into shared allowlist
entities would improve consistency and maintainability.
Affected rules: [N]
Current pattern: [example of duplicated allowlists]
Recommendation: [how to centralize]

Search all change summaries for "NEEDS SHARED ENTITY: pal_*" markers left by the moderator.
Compile the full list of missing shared entities that need to be created in `policies/edr/shared/`.

### ARCH-003: Cross-rule overlaps and gaps
Read ALL `CROSS_RULE_*.md` files from each group agent. Compile:
- Overlapping rules (same technique, redundant conditions) → recommend merge or scope split
- Gap-between-rules (variant caught by neither adjacent rule) → recommend new rule
- Inconsistent severity (same technique at different levels without justification) → recommend alignment

---

## IoC vs IoA Distribution

| Category | Count | % |
|----------|-------|---|
| Pure IoA (behavioral, evasion-resistant) | | |
| Mixed (IoA + IoC backup) | | |
| Pure IoC (name/hash matching only) | | |

Pure IoC rules are fragile. Any rule in the Pure IoC category is a candidate
for behavioral redesign.

---

## Evasion Resistance Distribution

| Resistance Level | Count | % | Description |
|-----------------|-------|---|-------------|
| High (requires technique change to bypass) | | | |
| Medium (requires tool substitution) | | | |
| Low (rename binary or change one flag) | | | |
| None (trivially bypassed) | | | |

Low/None evasion resistance rules should be redesigned or replaced with behavioral equivalents.

---

## Coverage Gaps by MITRE Tactic

For each tactic, variants identified during review that are not covered by any rule:

### Defense Evasion
- [Technique variant not covered]
- ...

### Credential Access
- ...

[... repeat per tactic ...]

---

## Companion Rules Backlog

Aggregate all companion rule specs from moderator Step 8 outputs across all rules.
Deduplicate (multiple rules may identify the same companion need).

| Companion Rule ID | Parent Rule(s) | MITRE | Event Type | Sensor Requirement | Priority | Effort |
|------------------|----------------|-------|------------|-------------------|----------|--------|
| `edr_rule_linux_timestomp_syscall` | `edr_rule_linux_timestomp` | T1070.006 | SyscallAudit | auditd/eBPF | P2 | medium |
| ... | ... | ... | ... | ... | ... | ... |

This table is the engineering backlog for expanding coverage beyond ProcessCreate rules.

---

## Test Coverage Statistics

| Metric | Count |
|--------|-------|
| Total test fixture files generated | N |
| Total true positive cases | N |
| Total true negative cases | N |
| Total evasion blind spot cases | N |
| Rules with 0 test cases (NEEDS ATTENTION) | N |

---

## Rule Help Page Index

All rule help pages are in `policies/edr_reviewed/docs/`. Generate an index:

| Rule ID | Tactic | Platform | MITRE | Verdict | Quality Score | Help Page |
|---------|--------|----------|-------|---------|---------------|-----------|
| `{rule_id}` | {tactic} | {platform} | {technique_id} | {verdict} | {avg_score}/5 | [docs/{rule_id}.md](docs/{rule_id}.md) |

This index serves as the entry point for the rule knowledge base.
```

---

## How to generate these reports

1. Read ALL `policies/${PLUGIN}/changes/*_changes.md` files — one by one, do not load all at once
2. When `PLUGIN=siem`, read `agent_state/rule_board/siem/coverage_index.json` and summarize inventory gaps in OPPORTUNITY_REPORT
3. As you read each change summary, extract:
   - Verdict
   - Quality scores (5 dimensions)
   - Key findings
   - Required changes
   - Remaining gaps
   - "NEEDS SHARED ENTITY" markers (for ARCH-002)
   - process_allowlist_refs migration status (EDR only)
   - overlap_status / ext.* field issues (SIEM only)
4. Read ALL `CROSS_RULE_*.md` files and extract overlap/gap/severity findings
5. Aggregate across all rules
6. Identify patterns (same finding appearing in 3+ rules = systemic issue)
7. Write REVIEW_SUMMARY.md to `policies/${PLUGIN}/`
8. Write OPPORTUNITY_REPORT.md to `policies/${PLUGIN}/`
9. Do not load the improved rule JSON files — the change summaries have all the information you need
