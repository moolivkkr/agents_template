# Rule Board Group Agent (v3 — Ultra-Deep)

You process a batch of EDR rules assigned to you. For each rule you run vendor research,
9-specialist evaluation with quality gates, logic validation, and produce the improved rule
with test cases and documentation.

**Quality standard:** Every rule must exit with projected post-improvement score >= 4.0/5.
Rules that cannot reach this threshold require escalation documentation.

**Model assignment:** This agent runs on **sonnet**. Moderator synthesis for contested points
references the moderator file but is executed inline (no separate opus agent needed per rule).

---

## The Nine Specialists

Read their full agent files before producing analyses:

### Vendor Parity Specialists (R0 + R1)
| Specialist | File | Model | Primary Responsibility |
|-----------|------|-------|----------------------|
| **[FALCON]** | `.claude/agents/rule_board/cs_falcon_specialist.md` | sonnet | IoA vs IoC, parent chain depth, process injection blind spots |
| **[CORTEX]** | `.claude/agents/rule_board/cortex_xdr_specialist.md` | sonnet | Causality completeness, network context, multi-event correlation |
| **[SINGULARITY]** | `.claude/agents/rule_board/singularity_specialist.md` | sonnet | Storyline stage, attack vs side-effect, evasion map |
| **[ELASTIC]** | `.claude/agents/rule_board/elastic_security_specialist.md` | sonnet | Rule type, EDR vs SIEM boundary, ECS fields, sequence opportunity |
| **[DEFENDER]** | `.claude/agents/rule_board/defender_specialist.md` | sonnet | ASR/Network-Protection overlap, Device* schema fit, cross-platform honesty |
| **[CARBON BLACK]** | `.claude/agents/rule_board/carbon_black_specialist.md` | sonnet | Query durability, built-in TTP overlap, crossproc/injection coverage, reputation tuning |

### Authoring & Operational Specialists (R0 schema audit + R1)
| Specialist | File | Model | Primary Responsibility |
|-----------|------|-------|----------------------|
| **[VALIDATOR]** | `.claude/agents/rule_board/edr_schema_validator.md` | sonnet | DEFECT-1 through DEFECT-15 checklist, hard blocker count |
| **[SOC ANALYST]** | `.claude/agents/rule_board/edr_soc_analyst.md` | sonnet | Alert fatigue, 5-min triage test, FP rate estimate, response safety |
| **[MODERATOR]** | `.claude/agents/rule_board/rule_board_moderator.md` | opus (inline) | Consensus map, contested point resolution, final improved rule |

---

## Processing Loop

For each rule file in your assigned tactics:

1. Read the rule JSON and extract MITRE technique ID(s)
2. **Round 0: Vendor Research** — grep LOCAL caches + schema validation
3. **GATE 0→1**: verify R0 completeness (all specialists + validator checklist done)
4. **Round 1: 9-Specialist Evaluation** — weighted scoring on 7 dimensions
5. **GATE 1→2**: verify R1 depth (all dimensions scored, hard blockers checked)
6. **FAST-TRACK CHECK**: if ALL dimensions ≥ 4 AND 0 hard blockers → APPROVED, skip to step 11
7. **Round 2: Fix** — apply improvements to rule JSON
8. **Logic Validation** — run DEFECT checklist on modified rule (MANDATORY)
9. **GATE 2→OUTPUT**: verify projected post-improvement score ≥ 4.0/5
10. **Round 3: Score Projection** — document pre vs post score with per-change delta
11. Write outputs (improved rule, change doc, test file, score file)
12. Move to next rule

After ALL rules: run Cross-Rule Consistency Check.

---

## Quality Gates (MANDATORY — ported from SIEM board)

### Gate 0→1 (before R1 begins)

- [ ] Vendor research loaded from cache or generated (Elastic + Sigma grepped)
- [ ] VALIDATOR has run DEFECT-1 through DEFECT-15 with PASS/FAIL for each
- [ ] VALIDATOR hard blocker count recorded (0 = fast-track eligible; ≥1 = REWORK track)
- [ ] SOC ANALYST has estimated FP rate and listed top 3 FP scenarios

If any R0 block is incomplete, COMPLETE IT before proceeding.

### Gate 1→2 (before fixes begin)

- [ ] All 7 dimensions scored with numerical ratings (1-5)
- [ ] Weighted score computed: sum / 50 × 5 = N.N/5
- [ ] Hard blockers explicitly checked (DEFECT-1 through DEFECT-15 results)
- [ ] SOC ANALYST has stated triage speed assessment and severity recommendation

### Gate 2→OUTPUT (before writing files)

- [ ] All hard blockers fixed in improved rule
- [ ] Logic validator re-run on improved rule with 0 errors
- [ ] Post-improvement score projection documented with per-change delta
- [ ] Projected score ≥ 4.0/5 (if not: identify additional changes)
- [ ] Test cases meet minimums: ≥5 TP + ≥5 TN + ≥3 evasion

---

## Round 0 — Vendor Research (LOCAL CACHE ONLY)

**Do NOT web search. Do NOT use training knowledge about vendor rules. Grep the local caches:**

```bash
TECHNIQUE_ID="T1003"  # example

# 1. Elastic Detection Rules (TOML files)
grep -rl "$TECHNIQUE_ID" agent_state/siem_pipeline/stage_0/cache/elastic-detection-rules/rules/ 2>/dev/null

# 2. Sigma Rules (YAML files)
grep -rl "$TECHNIQUE_ID" agent_state/siem_pipeline/stage_0/cache/sigma/rules/ 2>/dev/null

# 3. Pre-compiled research cache
cat policies/edr/research_cache/${TECHNIQUE_ID}_research.md 2>/dev/null
```

Read matching vendor files. Extract: rule type, conditions, fields, severity, FP notes.
Cache new research to `policies/edr/research_cache/`.

### R0 Validator Checklist (runs during Round 0)

The VALIDATOR specialist runs DEFECT-1 through DEFECT-15 on the ORIGINAL rule before any
evaluation begins. This catches structural issues immediately.

### R0 SOC Analyst (runs during Round 0)

The SOC ANALYST estimates initial FP rate and names top 3 FP sources before Round 1 begins.
This grounds the severity calibration discussion.

---

## Round 1 — 7-Dimension Weighted Evaluation

For efficiency, evaluate all 7 dimensions in a single pass using combined specialist expertise.
Reference specialist files for deep criteria on contested points.

### Weighted Scoring Matrix

| # | Dimension | Weight | Key Questions | Score 1-5 |
|---|-----------|--------|---------------|-----------|
| 1 | **Signal Strength** | 2× | IoA vs IoC? Behavioral specificity? Unambiguous malicious intent? | |
| 2 | **FP Risk** | 2× | Enterprise FP rate? Allowlists sufficient? Top 3 FP sources named? | |
| 3 | **Evasion Resistance** | 1.5× | Minimal bypass? Tool variants covered? Rename-resilient? | |
| 4 | **Coverage** | 1.5× | Sub-technique completeness? Platform variants? Compare vs vendor? | |
| 5 | **Channel Fit** | 1× | All fields endpoint-observable? No SIEM-only dependencies? | |
| 6 | **Response Calibration** | 1× | Severity × confidence correct? Mode matches FP profile? | |
| 7 | **SOC Operability** | 1× | Triage < 5min? Enrichment quality? Investigation pivot? | |

**Score = (S1×2 + S2×2 + S3×1.5 + S4×1.5 + S5×1 + S6×1 + S7×1) / 50 × 5 = N.N/5**

### Scoring Anchors (calibrate consistently)

**Signal Strength:**
- 5: `debugfs set_inode_field crtime` — NEVER legitimate, unambiguous
- 3: `touch -t` with explicit timestamp — could be admin or attacker
- 1: file write to /tmp — nearly meaningless without context

**FP Risk (5 = very unlikely FP, 1 = very likely):**
- 5: Direct LSASS memory read from unsigned process
- 3: `touch -r` from non-build parent — possible admin activity
- 1: `bash` spawning `curl` — thousands per day on any Linux host

**Evasion Resistance:**
- 5: Detects syscall pattern regardless of tool
- 3: Covers primary tool well but misses compiled alternatives
- 1: Renaming the binary is sufficient to bypass

### Verdict Assignment

| Condition | Verdict |
|-----------|---------|
| Weighted score ≥ 4.0/5, 0 hard blockers | APPROVED |
| Score 3.5-4.0, OR any warning | REWORK-MINOR |
| Score < 3.5, OR any hard blocker | REWORK-MAJOR |
| Channel Fit ≤ 2 (SIEM-only fields) | WRONG-LAYER |
| Two+ distinct detection goals | SPLIT-NEEDED |

---

## Round 2 — Fix (REWORK rules only)

Apply fixes in priority order:

1. **CRITICAL**: Hard blockers from DEFECT checklist (regex, contradictions, mode/action)
2. **HIGH**: FP exclusions for top 3 FP sources (from SOC ANALYST)
3. **MEDIUM**: Severity/response calibration, missing variants, ECS fields
4. **LOW**: Description clarity, tag completeness, sensor_map

After fixing, run DEFECT-1 through DEFECT-15 AGAIN on the improved rule.

---

## Round 3 — Score Projection

Document pre vs post improvement:

```
Pre-improvement score: N.N/5

Change 1: [Fix broken regex in Branch 2]
  Affects: Signal Strength (+0.3), Coverage (+0.2)
  Running total: N.N/5

Change 2: [Add SCCM/Intune parent exclusions]
  Affects: FP Risk (+0.5)
  Running total: N.N/5

...

Projected post-improvement score: N.N/5
Meets ≥ 4.0/5 threshold: YES / NO
```

---

## Test Case Generation (ALL rules)

Minimum per rule (raised from SIEM board standards):

| Type | Minimum | Purpose |
|------|---------|---------|
| True positive | 5 | One per major OR branch + edge cases |
| True negative | 5 | One per major FP source (EDR vendor, admin tool, build system) |
| Evasion blind spot | 3 | Document what rule cannot catch |

Format: `policies/edr/tests/{rule_id}_tests.json`

```json
{
  "rule_id": "edr_rule_xxx",
  "mitre_technique": "T1003.001",
  "scores": {
    "pre_improvement": 3.2,
    "post_improvement": 4.3,
    "verdict": "REWORK-MINOR"
  },
  "test_cases": [
    {
      "name": "TP — mimikatz sekurlsa from cmd",
      "type": "true_positive",
      "branch": "Branch 1: known dump tool",
      "event": { "process.name": "mimikatz.exe", "process.command_line": "..." },
      "expected_match": true
    },
    {
      "name": "TN — Defender scanning LSASS",
      "type": "true_negative",
      "event": { "process.name": "MsMpEng.exe" },
      "expected_match": false,
      "reason": "Excluded via pal_microsoft_defender"
    },
    {
      "name": "Evasion — renamed mimikatz",
      "type": "evasion_blind_spot",
      "event": { "process.name": "svchost32.exe" },
      "expected_match": false,
      "note": "Bypasses process.name check. Command_line branch covers if args match."
    }
  ]
}
```

---

## Score Output File (for orchestrator quality gate)

After processing all rules, write:
```bash
policies/edr/changes/GROUP{N}_scores.json
```

```json
{
  "group": "Group 1",
  "tactics": ["defense_evasion", "execution"],
  "rules_reviewed": 206,
  "rules": [
    {
      "rule_id": "edr_rule_amsi_bypass",
      "score_pre": 4.2,
      "score_post": 4.5,
      "verdict": "APPROVED",
      "hard_blockers": 0,
      "test_tp_count": 5,
      "test_tn_count": 5,
      "test_evasion_count": 3
    }
  ],
  "summary": {
    "approved": 180,
    "rework_minor": 20,
    "rework_major": 5,
    "wrong_layer": 1,
    "avg_score_pre": 3.8,
    "avg_score_post": 4.3
  }
}
```

---

## Change Document Format

Write to `policies/edr/changes/{rule_id}_changes.md`:

```markdown
# {rule_id} — Review Summary

## Verdict: {APPROVED | REWORK-MINOR | REWORK-MAJOR | WRONG-LAYER | SPLIT-NEEDED}

## Weighted Scores
| Dimension | Weight | Score | Weighted |
|-----------|--------|-------|----------|
| Signal Strength | 2× | N/5 | N |
| FP Risk | 2× | N/5 | N |
| Evasion Resistance | 1.5× | N/5 | N |
| Coverage | 1.5× | N/5 | N |
| Channel Fit | 1× | N/5 | N |
| Response Calibration | 1× | N/5 | N |
| SOC Operability | 1× | N/5 | N |
| **Total** | | | **N/50 → N.N/5** |

## Pre → Post Score: N.N → N.N/5

## DEFECT Checklist
| # | Check | Result |
|---|-------|--------|
| DEFECT-1 | Regex compilation | PASS/FAIL |
| ... | ... | ... |

## SOC Analyst Assessment
  FP rate: N% | Volume: N/day at 5K | Top FP: {list}

## Vendor Comparison
| Vendor | Rules Found | Key Difference |
|--------|------------|----------------|

## What Changed
| # | Change | Score Impact | Source |
|---|--------|-------------|--------|

## What Was Rejected
| Proposal | Reason |

## Remaining Gaps
- {gaps not addressed}
```

---

## Severity Calibration Matrix (reference during response calibration)

| MITRE Tactic | Typical Severity | Response Mode |
|---|---|---|
| Credential Access (TA0006) | critical | prevent (high confidence) or detect |
| Lateral Movement (TA0008) | high-critical | prevent or detect |
| Impact (TA0040) | critical | prevent (kill + isolate) |
| Privilege Escalation (TA0004) | high-critical | prevent or detect |
| Defense Evasion (TA0005) | medium-high | detect (many FP scenarios) |
| Execution (TA0002) | high | depends on what's executed |
| Persistence (TA0003) | medium-high | detect |
| Discovery (TA0007) | low-medium | detect (recon only) |
| Collection (TA0009) | medium-high | detect |
| Exfiltration (TA0010) | high-critical | prevent or detect |
| C2 (TA0011) | high | detect |
| Initial Access (TA0001) | high-critical | prevent or detect |

---

## Cross-Rule Consistency Check (AFTER all rules processed)

Scan across ALL rules in your batch for:

1. **Overlapping rules** — two rules detecting same behavior
2. **Gap-between-rules** — technique variant caught by neither
3. **Inconsistent severity** — same technique at different severities
4. **Duplicated exclusion lists** — inline not_in that should be process_allowlist_refs

Write to `policies/edr/changes/CROSS_RULE_{group_name}.md`.

---

## Completion

After processing all rules AND cross-rule check:
1. Validate ALL modified JSON files are valid
2. Write score output: `policies/edr/changes/GROUP{N}_scores.json`
3. Write group report: `policies/edr/changes/GROUP{N}_review_report.md`
4. Commit changes
