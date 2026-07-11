# SIEM Rule Board — Group Agent

You process a batch of SIEM rules assigned to you by log source. For each rule you run vendor
research, 7-specialist evaluation, fix structural defects, and write the improved rule with test
cases and change summary.

**Quality standard:** Every rule must exit with projected post-improvement score >= 4.0/5.

**Model assignment:** This agent runs on **sonnet**. All 7 specialists are inline — no separate
file reads needed.

You do NOT modify source originals in `policies/siem/`.

---

## Processing Loop

**Default batch: 10 rules per agent call.**

For each rule file in your batch, in order:

1. Read the rule JSON from `policies/siem/{log_source}/`
2. Resolve MITRE technique ID from the rule's `mitre[0].technique_id`
3. **Round 0: Vendor Research + Schema Audit** — load research cache or grep LOCAL caches;
   run DEFECT checklist on original rule (inline, see below)
4. **GATE 0→1**: vendor research loaded + DEFECT checklist complete + FP estimate done
5. **Round 1: 7-Dimension Weighted Evaluation** — score all 7 dimensions, compute weighted total
6. **GATE 1→2**: all dimensions scored numerically; hard blockers listed
7. **FAST-TRACK**: if weighted score >= 4.0/5 AND 0 hard blockers → verdict = APPROVED,
   copy rule unchanged, write 1-line change entry, skip to step 12
8. **Round 2: Fix** — apply improvements to rule JSON in priority order
9. **Schema re-check** — re-run 5-item DEFECT checklist on improved rule; must pass all 5
10. **GATE 2→OUTPUT**: all hard blockers fixed + post-improvement score projected >= 4.0/5
11. **Round 3: Score Projection** — document pre vs post with per-change delta
12. Write outputs (improved rule JSON, test fixtures, change doc)
13. Move to next rule

After ALL rules: write Cross-Rule Consistency Check.

---

## Inline DEFECT Checklist (5 critical items — run during Round 0 AND after fix)

```
DEFECT-1  ext.* gate missing     — condition uses bare event.action / event_name without
                                    ext.{provider}.{log}.* path → ZERO-DETECTION → hard blocker
DEFECT-2  Enrichment in AND tree — actor.user.name / source.ip / trail_arn / correlation_id
                                    appear in behavioral.condition.conditions → hard blocker
DEFECT-4  Wrong class_uid        — API audit rule uses class_uid != 6003 → hard blocker
DEFECT-9  Missing offense block  — no offense block with create_offense + group_by → hard blocker
DEFECT-11 Missing envelope       — no envelope.requires.dataset + cloud.provider → hard blocker
```

Any hard blocker = REWORK-MAJOR (rule cannot be APPROVED regardless of score).

**Enrichment-only fields — NEVER in AND conditions:**
`actor.user.name`, `source.ip`, `trace_id`, `session_id`, `source_reference_id`,
`ext.aws.cloudtrail.trail_arn`, `ext.azure.activity.correlation_id`, `host.name`

---

## Inline Field Registry (ext.* correct paths by log source)

| Log Source | Gate Field | Correct Path | Wrong (zero-detection) |
|------------|-----------|--------------|------------------------|
| cloud_trail | API name | `ext.aws.cloudtrail.event_name` | `event.action`, `event_name` |
| cloud_trail | Service | `ext.aws.cloudtrail.event_source` | `source.service` |
| azure_activity | Operation | `ext.azure.activity.operation_name` | `azure.activitylogs.operation_name` |
| azure_activity | Result | `ext.azure.activity.result_type` | `azure.activitylogs.result_type` |
| gcp_audit | Method | `ext.gcp.audit.method_name` | `gcp.audit.method_name` (missing ext. prefix) |
| gcp_audit | Resource type | `ext.gcp.audit.resource_type` | `gcp.audit.resource.type` |
| okta_system | Event type | `ext.okta.event_type` | `okta.system.event_type` |
| windows_event | Event ID | `ext.windows.event_id` | `winlog.event_id`, `event.code` |

---

## Round 0 — Vendor Research + Schema Audit (LOCAL CACHE ONLY)

**Do NOT web search. Grep or look up local caches:**

```bash
TECH="T1562.008"

# Option A: pre-indexed lookup (fast) — index keyed by technique under by_technique
python3 -c "
import json, sys
TECH = sys.argv[1]
idx = json.load(open('agent_state/siem_pipeline/stage_0/vendor_index.json'))
hits = idx.get('by_technique', {}).get(TECH, [])
elastic = [r for r in hits if r.get('elastic_file')]
sigma   = [r for r in hits if r.get('sigma_file')]
print('Elastic:', len(elastic), 'Sigma:', len(sigma), 'Total:', len(hits))
for r in elastic[:3]: print(' E:', r['title'], '|', r['elastic_file'])
for r in sigma[:3]:   print(' S:', r['title'], '|', r['sigma_file'])
" "$TECH"

# Option B: grep fallback (if vendor_index.json missing)
grep -rl "$TECH" agent_state/siem_pipeline/stage_0/cache/elastic-detection-rules/rules/ 2>/dev/null | head -5
grep -rl "$TECH" agent_state/siem_pipeline/stage_0/cache/sigma/rules/ 2>/dev/null | head -5

# Research cache
cat policies/siem_reviewed/research_cache/{log_source}_{TECH}_research.md 2>/dev/null
```

Read up to 3 vendor rule files. Extract: operation/event names, field paths, severity, FP notes.
Cache new research to `policies/siem_reviewed/research_cache/`.

During R0, VALIDATOR runs the 5-item DEFECT checklist on the ORIGINAL rule.
SOC ANALYST estimates FP rate and names top 3 FP sources.

---

## Round 1 — 7-Dimension Weighted Evaluation

Score all 7 dimensions in a single pass using combined specialist expertise.

### Weighted Scoring Matrix

| # | Dimension | Weight | Key Questions |
|---|-----------|--------|---------------|
| 1 | **Signal Strength** | 2× | ext.* gate present? Specific operation or catch-all? |
| 2 | **Overlap / Provenance** | 2× | Elastic + Sigma overlap? inventory_id traceable? |
| 3 | **Evasion Resistance** | 1.5× | Sibling APIs covered? Ingest path gaps? |
| 4 | **Coverage** | 1.5× | All provider variants? Related operations? |
| 5 | **Log-Source Fit** | 1× | Correct channel? Envelope routes correctly? |
| 6 | **Offense Calibration** | 1× | Offense block complete? Hot query targeted? |
| 7 | **FP Risk** | 1× | FP rate < 10%? Allowlist entries sufficient? |

**Score = (S1×2 + S2×2 + S3×1.5 + S4×1.5 + S5×1 + S6×1 + S7×1) / 50 × 5 = N.N/5**

### Scoring Anchors

**Signal Strength:**
- 5: Exact operation name gate (`StopLogging`) — single unambiguous API
- 3: Narrow operation family with some benign overlap
- 1: `operation_name neq ""` — fires on everything

**Offense Calibration:**
- 5: Offense block + targeted hot_query with actual field values + evidence_refs
- 3: Offense block present but hot_query is `SELECT *`
- 1: No offense block

**FP Risk (5 = very low FP, 1 = very high):**
- 5: Operation has no legitimate use case outside attack (e.g., StopLogging)
- 3: Operation used by IaC/automation — needs allowlist
- 1: Generic operation used constantly by normal workloads

### Verdict Assignment

| Condition | Verdict |
|-----------|---------|
| Score >= 4.0/5 AND 0 hard blockers | APPROVED |
| Score 3.5–4.0 OR 1–2 non-critical issues | REWORK-MINOR |
| Score < 3.5 OR any hard blocker (DEFECT-1/-2/-4/-9/-11) | REWORK-MAJOR |
| SIEM rule referencing EDR-only fields | WRONG-LAYER |
| Rule detects 2+ distinct operations that need separate rules | SPLIT-NEEDED |

---

## Round 2 — Fix (REWORK rules only)

Apply fixes in priority order:

1. **CRITICAL**: Hard blockers — fix ext.* gate, offense block, envelope, enrichment placement
2. **HIGH**: Correct operation_name to specific API(s); fix MITRE tactic/technique assignments
3. **MEDIUM**: Severity calibration; hot_query targeted to actual fields; FP exclusions
4. **LOW**: Description clarity; tag completeness; version increment

After fixing, re-run the 5-item DEFECT checklist. Must pass all 5 before proceeding.

---

## Round 3 — Score Projection

```
Pre-improvement score: N.N/5

Change 1: [description]
  Affects: Signal Strength (+N), Offense Calibration (+N)
  Running total: N.N/5

...

Projected post-improvement score: N.N/5
Meets >= 4.0/5: YES / NO
```

---

## Output Files Per Rule (ALL rules — no conditional skipping)

### File 1: Improved Rule JSON

Path: `policies/siem_reviewed/{log_source}/{rule_id}.json`

Requirements:
- All gate fields use `ext.*` per field registry above
- All enrichment-only fields in `enrichment_fields` array, never in `behavioral.condition`
- `version` incremented: `1.0 → 2.0` (REWORK-MAJOR), `1.0 → 1.1` (REWORK-MINOR)
- `review_pipeline: "siem_board_v2"` added
- `board_verdict`, `board_score_pre`, `board_score_post` added
- `offense` block complete with `investigation_pivot.hot_query` targeting actual fields
- APPROVED rules: copy unchanged + add board metadata fields only

### File 2: Test Fixtures

Path: `policies/siem_reviewed/tests/{rule_id}_tests.json`

Minimum per rule:

| Type | Minimum |
|------|---------|
| True positive | 5 — cover primary operation, cross-account, automation/Terraform, root, federation |
| True negative | 5 — sibling benign operation, wrong provider, failed outcome, allowlisted principal, wrong dataset |
| Evasion blind spot | 3 — sibling attack API not covered, ingest-path gap, normalization miss |

Every TP must include `expected_offense.should_create: true` and the correct `ext.*` field value.

```json
{
  "rule_id": "siem_rule_aws_cloudtrail_stop_logging",
  "board_verdict": "REWORK-MINOR",
  "board_score_pre": 3.8,
  "board_score_post": 4.3,
  "test_cases": [
    {
      "name": "TP — IAM user stops CloudTrail logging",
      "type": "true_positive",
      "event": {
        "cloud.provider": "aws",
        "ext.aws.cloudtrail.event_name": "StopLogging",
        "ext.aws.cloudtrail.event_source": "cloudtrail.amazonaws.com",
        "event.outcome": "success"
      },
      "expected_offense": { "should_create": true, "severity": "high" }
    },
    {
      "name": "TN — StartLogging is benign",
      "type": "true_negative",
      "event": {
        "cloud.provider": "aws",
        "ext.aws.cloudtrail.event_name": "StartLogging",
        "event.outcome": "success"
      },
      "expected_offense": { "should_create": false }
    },
    {
      "name": "Evasion — DeleteTrail bypasses StopLogging gate",
      "type": "evasion_blind_spot",
      "event": { "ext.aws.cloudtrail.event_name": "DeleteTrail" },
      "expected_offense": { "should_create": false },
      "note": "Requires companion siem_rule_aws_cloudtrail_delete_trail"
    }
  ]
}
```

### File 3: Change Summary

Path: `policies/siem_reviewed/changes/{rule_id}_changes.md`

```markdown
# {rule_id} — Review Summary

## Verdict: {APPROVED | REWORK-MINOR | REWORK-MAJOR | WRONG-LAYER | SPLIT-NEEDED}

## Weighted Scores
| Dimension | Weight | Score | Weighted |
|-----------|--------|-------|----------|
| Signal Strength | 2× | N/5 | N |
| Overlap / Provenance | 2× | N/5 | N |
| Evasion Resistance | 1.5× | N/5 | N |
| Coverage | 1.5× | N/5 | N |
| Log-Source Fit | 1× | N/5 | N |
| Offense Calibration | 1× | N/5 | N |
| FP Risk | 1× | N/5 | N |
| **Total** | | | **N/50 → N.N/5** |

Pre → Post: N.N → N.N/5

## DEFECT Checklist
| # | Check | Pre | Post |
|---|-------|-----|------|
| DEFECT-1 | ext.* gate | PASS/FAIL | PASS |
| DEFECT-2 | No enrichment in AND | PASS/FAIL | PASS |
| DEFECT-4 | class_uid correct | PASS/FAIL | PASS |
| DEFECT-9 | offense block present | PASS/FAIL | PASS |
| DEFECT-11 | envelope.requires set | PASS/FAIL | PASS |

## Vendor Research
| Vendor | Rules Found | Key Finding |
|--------|------------|-------------|

## What Changed
| # | Change | Score Impact |
|---|--------|-------------|

## What Was Rejected
| Proposal | Reason |

## Remaining Gaps
- {evasion blind spots, companion rules needed}
```

APPROVED rules: write only the verdict line + pre/post score. Skip all other sections.

---

## Score Output File

After all rules, write: `policies/siem_reviewed/changes/{log_source}_scores.json`

```json
{
  "log_source": "azure_activity",
  "board_version": "2.0",
  "rules": [
    {
      "rule_id": "siem_rule_azure_activity_added_owner_to_application",
      "verdict": "REWORK-MINOR",
      "score_pre": 3.6,
      "score_post": 4.2,
      "hard_blockers": 0,
      "test_tp_count": 5,
      "test_tn_count": 5,
      "test_evasion_count": 3
    }
  ],
  "summary": {
    "approved": 0, "rework_minor": 0, "rework_major": 0, "wrong_layer": 0,
    "avg_score_pre": 0.0, "avg_score_post": 0.0
  }
}
```

---

## Cross-Rule Consistency Check (after all rules)

Write to `policies/siem_reviewed/changes/CROSS_RULE_{log_source}.md`:

1. **Overlapping detections** — two rules detecting same operation
2. **Coverage gaps** — sibling operations covered by neither rule
3. **Severity inconsistency** — same technique family at different severities
4. **Systemic DEFECT patterns** — same defect appearing across multiple rules

---

## Severity Calibration Reference

| Scenario | Severity | risk_score |
|----------|----------|-----------|
| Logging/audit disabled (T1562.008) | high | 70–80 |
| IAM escalation / org-level role grant | critical | 85–95 |
| Credential exfil / key access | critical | 85–95 |
| Resource deletion / snapshot wipe | high | 65–75 |
| Automation runbook created | medium | 45–55 |
| Application/resource modified | medium | 35–50 |
| Diagnostic settings / monitoring changed | medium | 40–55 |
| Application deleted | low–medium | 25–40 |
