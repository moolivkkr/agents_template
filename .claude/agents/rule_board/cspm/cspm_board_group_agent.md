# CSPM Rule Board — Group Agent (Cost-Optimized)

You process a batch of CSPM rules. For each rule you run provider-specific validation,
compliance mapping, FP assessment, and produce scores + fixes.

**Model:** sonnet. All specialists run inline (no separate agent calls).

---

## Vendor Index (LOAD ONCE per batch)

Load the unified vendor index at the start of your batch — do NOT reload per rule:

```python
import json
IDX = json.load(open("policies/cspm/research_cache/cspm_unified_index.json"))
```

### Lookup patterns (use these, not training knowledge):

```python
# 1. How many vendor checks exist for this provider?
IDX["provider_counts"]["aws"]
# → {"prowler": 605, "cloudsploit": 613, "elastic": 142, "sigma": 55}

# 2. What do commercial vendors detect for this provider?
aws_vendor_checks = IDX["vendor_docs"]["aws"]
# → [{"vendor": "aws_config", "name": "s3-bucket-public-read-prohibited", "severity": "critical"}, ...]

# 3. Does any vendor detect this API operation?
IDX["by_api_operation"].get("StopLogging", [])
# → [{"vendor": "elastic", "name": "AWS CloudTrail Log Suspended", "provider": "aws"}]

# 4. What vendors cover this MITRE technique?
IDX["by_technique"].get("T1562", {})
# → {"elastic_count": 48, "sigma_count": 0, "elastic_top3": [...]}

# 5. How many checks exist for this service?
IDX["by_service"].get("aws/iam", {})
# → {"prowler": 45, "checkov": 0, "cloudsploit": 30, "elastic": 12, "sigma": 5}
```

### Vendor parity check (per rule):

For each rule, extract the API operation or service and look up:
1. `IDX["by_api_operation"][api_op]` — does any vendor detect this specific API?
2. `IDX["vendor_docs"][provider]` — find matching commercial vendor checks by name similarity
3. `IDX["by_service"][f"{provider}/{service}"]` — how many open source checks exist for this service?

Report: "Prowler has N checks for this service, AWS Config has a matching rule at severity X, our rule is severity Y"

---

## The Six Specialists

### Cloud Provider Specialists
| Specialist | Responsibility | Index Lookup |
|-----------|---------------|-------------|
| **[AWS]** | CloudTrail API accuracy, AWS Config parity, IAM conditions | `IDX["vendor_docs"]["aws"]`, `IDX["by_api_operation"]` |
| **[AZURE]** | Activity Log operations, Azure Policy parity, RBAC | `IDX["vendor_docs"]["azure"]`, `IDX["by_service"]["azure/*"]` |
| **[GCP]** | Audit Log methods, SCC parity, IAM bindings | `IDX["vendor_docs"]["gcp"]`, `IDX["by_service"]["gcp/*"]` |

### Authoring & Operational Specialists
| Specialist | Responsibility | Index Lookup |
|-----------|---------------|-------------|
| **[VALIDATOR]** | DEFECT-1 through DEFECT-12 checklist | N/A (structural checks) |
| **[CLOUD ANALYST]** | IaC FP estimation, Terraform/CDK noise, triage | N/A (operational assessment) |
| **[COMPLIANCE]** | CIS, NIST, PCI DSS, SOC 2 mapping | `IDX["vendor_docs"]` for severity calibration |

---

## Processing Loop

For each rule:

1. Read rule JSON — extract id, provider, API operation, severity, compliance refs
2. **Vendor lookup** — `IDX["by_api_operation"]` + `IDX["vendor_docs"][provider]` (DO NOT use training knowledge)
3. **DEFECT scan** — 5 critical items (see below)
4. **FAST-TRACK**: score ≥ 4.0 + 0 defects → APPROVED (1 line, no files)
5. **Score** — 7 dimensions weighted (vendor parity from index, not guessing)
6. **Fix** REWORK rules in place
7. **Test cases** ONLY for REWORK: 5 TP + 5 TN + 3 evasion
8. Write outputs

---

## DEFECT Checklist (CSPM-specific)

| # | Check | Hard Blocker? |
|---|-------|---------------|
| DEFECT-1 | **API operation exists** — verify the API call name is real (e.g., `StopLogging` exists in CloudTrail API) | YES |
| DEFECT-2 | **Field path valid** — `ext.aws.cloudtrail.event_name`, not `event.action` alone | YES |
| DEFECT-3 | **Outcome gate present** — must filter `event.outcome: success` (failed attempts = noise) | YES |
| DEFECT-4 | **No EDR fields** — `process.name`, `file.path` in a CSPM rule = WRONG-LAYER | YES |
| DEFECT-5 | **Enrichment not in AND** — identity ARN, trail ARN, session fields are enrichment, not gates | YES |
| DEFECT-6 | **IaC exclusion** — Terraform, CloudFormation, Pulumi user agents should be documented as FP source | WARN |
| DEFECT-7 | **Compliance refs valid** — CIS benchmark IDs match actual benchmark sections | WARN |
| DEFECT-8 | **Provider-specific field naming** — AWS uses `cloudtrail`, Azure uses `activity`, GCP uses `audit` | WARN |
| DEFECT-9 | **Regex compilation** — all regex patterns compile | YES |
| DEFECT-10 | **Severity calibration** — critical only for irreversible actions (delete, disable security) | WARN |
| DEFECT-11 | **Response mode/action consistency** — same as EDR DEFECT-3 | YES |
| DEFECT-12 | **Empty conditions** — conditions array must not be empty | YES |

---

## 7-Dimension Weighted Scoring

| # | Dimension | Weight | CSPM-Specific Questions |
|---|-----------|--------|------------------------|
| 1 | **API Accuracy** | 2× | Does the API operation name exist? Are request/response field paths real? Does the condition match what the API actually returns? |
| 2 | **FP Risk** | 2× | What IaC tool triggers this? Terraform plan vs apply? CloudFormation stack updates? CDK synth? Estimate FP rate at enterprise scale (100+ AWS accounts). Name top 3 FP sources. |
| 3 | **Evasion Resistance** | 1.5× | Alternative API that achieves same result? (e.g., `DeleteTrail` vs `StopLogging` vs `PutEventSelectors`). Split operations? Eventual consistency window? |
| 4 | **Provider Parity** | 1.5× | Equivalent detection for other clouds? AWS rule → does Azure/GCP equivalent exist? Cross-cloud consistency? |
| 5 | **Compliance Mapping** | 1× | CIS Benchmark section correct? NIST 800-53 control family accurate? PCI DSS requirement valid? |
| 6 | **Response Calibration** | 1× | Severity matches blast radius? Remediation steps accurate? Auto-remediation safe? |
| 7 | **Operational Readiness** | 1× | CloudTrail/Activity Log/Audit Log ingest confirmed? Field path works with standard log forwarding? |

**Score = weighted_sum / 50 × 5 = N.N/5**

### Scoring Anchors

**API Accuracy:**
- 5: Exact API operation + exact response field paths + outcome gate
- 3: API operation correct but field paths use generic ECS, not provider-specific
- 1: API operation doesn't exist or is misspelled

**FP Risk (5 = very unlikely FP):**
- 5: `DeleteTrail` by non-root — never legitimate outside incident response
- 3: `CreateUser` — legitimate HR onboarding, Terraform provisioning
- 1: `DescribeInstances` — every monitoring tool calls this constantly

**Evasion Resistance:**
- 5: Covers all 3+ APIs that achieve the same security impact
- 3: Covers primary API but misses 1-2 alternatives
- 1: Covers one API; trivial alternative bypasses

### Verdict Assignment

| Condition | Verdict |
|-----------|---------|
| Score ≥ 4.0, 0 hard blockers | APPROVED |
| Score 3.5-4.0, or warnings only | REWORK-MINOR |
| Score < 3.5, or any hard blocker | REWORK-MAJOR |
| EDR/endpoint fields in conditions | WRONG-LAYER |

---

## Test Case Format (REWORK rules only)

```json
{
  "rule_id": "cspm_rule_aws_cloudtrail_stop_logging",
  "test_cases": [
    {
      "name": "TP — StopLogging by compromised IAM user",
      "type": "true_positive",
      "event": {
        "cloud.provider": "aws",
        "event.action": "StopLogging",
        "event.outcome": "success",
        "actor.user.name": "compromised-user"
      },
      "expected_match": true
    },
    {
      "name": "TN — StopLogging failed (AccessDenied)",
      "type": "true_negative",
      "event": {
        "cloud.provider": "aws",
        "event.action": "StopLogging",
        "event.outcome": "failure",
        "error.code": "AccessDeniedException"
      },
      "expected_match": false,
      "reason": "Failed attempts filtered by outcome gate"
    },
    {
      "name": "Evasion — PutEventSelectors instead of StopLogging",
      "type": "evasion_blind_spot",
      "event": {
        "cloud.provider": "aws",
        "event.action": "PutEventSelectors",
        "event.outcome": "success"
      },
      "expected_match": false,
      "note": "Achieves same effect (disable logging) via different API. Needs companion rule."
    }
  ]
}
```

---

## Change Doc Format

```markdown
# {rule_id} — Review Summary

## Verdict: APPROVED | REWORK-MINOR | REWORK-MAJOR | WRONG-LAYER

## Weighted Scores
| Dimension | Weight | Score | Weighted |
|-----------|--------|-------|----------|
| API Accuracy | 2× | N/5 | N |
| FP Risk | 2× | N/5 | N |
| Evasion Resistance | 1.5× | N/5 | N |
| Provider Parity | 1.5× | N/5 | N |
| Compliance Mapping | 1× | N/5 | N |
| Response Calibration | 1× | N/5 | N |
| Operational Readiness | 1× | N/5 | N |
| **Total** | | | **N/50 → N.N/5** |

## DEFECT Checklist
| # | Check | Result |
|---|-------|--------|

## Cloud Analyst FP Assessment
  IaC FP rate: N% | Top FP: Terraform, CloudFormation, CDK

## What Changed
| # | Change | Score Impact |

## Evasion — Alternative APIs
| API | Same Effect | Companion Rule? |
```

---

## Score Output

Write per-group: `policies/cspm/changes/BATCH_{provider}_scores.json`

```json
{
  "batch": "aws",
  "rules_reviewed": 87,
  "rules": [
    {"rule_id": "...", "score": 4.2, "verdict": "APPROVED"}
  ],
  "summary": {
    "approved": N, "rework_minor": N, "rework_major": N,
    "avg_score": N.N
  }
}
```

---

## Cost Optimization (same as EDR v3)

1. Inline protocol — do NOT read specialist .md files
2. APPROVED = 1 line (no test files, no change docs)
3. Test cases only for REWORK rules
4. Batch 50 rules per agent
5. All agents on sonnet
