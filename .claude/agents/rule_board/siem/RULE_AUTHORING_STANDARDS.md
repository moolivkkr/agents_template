# SIEM Rule Authoring Standards
# Derived from board review of pilot CloudTrail rules + MODULE_09 field contract
# Version: 2.0 — apply to ALL `siem_rule` authoring (Stage 2 developer + board-reviewed output)

## Scope

These standards govern **cloud/SIEM correlation rules** evaluated on the unified SIEM stream
(OCSF-normalized CloudAuditLog and sibling event types). They complement:

- `.claude/agents/generated/siem_rule_developer_agent.md` — Stage 2 authoring
- `.claude/agents/rule_board/siem/siem_board_group_agent.md` — four-artifact board output
- `policies/siem/shared/field_registry.yaml` — gate vs enrichment roles

**Not in scope:** DLP channel rules, EDR ProcessCreate rules, AI Security LLM rules (see
`rule_board/ai_security/RULE_AUTHORING_STANDARDS.md` for that plugin).

---

## Critical Fixes From Board Review (Systemic Defects Found)

### DEFECT-1: Bare `event.action` / unscoped API operation gate (caused zero-detection on mis-mapped ingest)

NEVER gate on bare `event.action` for CloudTrail API audit without dataset guard and `ext.*` path.

| Log source | Correct gate field | Wrong field |
|------------|-------------------|-------------|
| AWS CloudTrail | `ext.aws.cloudtrail.event_name` | `event.action` alone |
| Azure Activity | `ext.azure.activity.operation_name` | `event.action` alone |
| GCP Audit | `ext.gcp.audit.method_name` | `event.action` alone |
| Windows Security | `ext.windows.event_id` + logsource guard | bare `event.code` |
| Okta System Log | `ext.okta.event_type` | generic `event.action` |

Rule: if ingest may populate ECS `event.action` but not MODULE_09 `ext.*`, document as evasion blind spot or add normalization companion — do not silently assume dual-field coverage.

### DEFECT-2: Enrichment fields in AND conditions (gated detection)

Fields that may not be present on every event MUST NOT appear in AND condition branches.
They belong ONLY in `behavioral.enrichment_fields`.

BAD:
```json
{ "field": "ext.aws.cloudtrail.trail_arn", "operator": "exists" }   // IN conditions
{ "field": "source_reference_id", "operator": "exists" }            // IN conditions
{ "field": "actor.user.name", "operator": "exists" }                // IN conditions (unless statistically required)
```

GOOD:
```json
"enrichment_fields": ["ext.aws.cloudtrail.trail_arn", "source_reference_id", "actor.user.name"]
```

Rule: if the field is absent ~30%+ of the time, it is an enrichment field, not a gate (FC-05).

### DEFECT-3: Missing or incomplete `source_provenance`

When `stage_0_import: consolidated`, `source_provenance` MUST cite Stage 0 inventory IDs.

| `overlap_status` | Required |
|------------------|----------|
| `both` | `elastic.rule_id` AND `sigma.rule_id` with source files |
| `elastic_only` | `elastic` block complete; sigma gap in `adaptation_notes` |
| `sigma_only` | `sigma` block complete; MODULE_09 rewrite documented |

Missing provenance = immediate REWORK-MAJOR until fixed.

### DEFECT-4: Wrong OCSF `class_uid` for event type

| Event envelope | Correct class_uid | class_name |
|----------------|-------------------|------------|
| CloudAuditLog API calls | **6003** | API Activity |
| Authentication events | 3002 | Authentication |
| Network activity | 4001 | Network Activity |
| Process execution (log-derived) | 1007 | Process Activity |

CloudTrail StopLogging with `class_uid: 6003` — NOT 6001 or defaulted.

### DEFECT-5: `overlap_status: both` without both vendor blocks

Hard blocker. Inventory `overlap_status` must match rule `source_provenance.overlap_status`.

### DEFECT-6: Gate on `source_reference_id`, `session_id`, or `trace_id`

These are pivot/enrichment fields per FC-05. NEVER in AND tree.

### DEFECT-7: Missing `event.outcome` gate when failure does not create threat

For destructive/impairment APIs (StopLogging, DeleteTrail, DisableKey), successful outcome
creates the visibility gap. Failed calls (SCP deny, AccessDenied) must NOT fire.

### DEFECT-8: EDR-only or DLP-only fields in SIEM rule → WRONG-LAYER

ProcessCreate, file hash, network payload content → EDR/DLP channels.
SIEM rules consume **ingested log correlation** only.

### DEFECT-9: Missing or incomplete `offense` block

Production rules with `quality_thresholds.require_offense_block: true` require:

- `create_offense: true`
- `severity`, `severity_id`, `risk_score`
- `group_by` — stable correlation keys
- `title_template` / `description_template`
- `mitre_mapping[]` aligned with root `mitre[]`
- `response_actions[]` — at least `alert`
- `investigation_pivot` — hot query + `evidence_refs`

### DEFECT-10: Sigma multi-API bundle imported as single rule without SPLIT-NEEDED

When Sigma covers StopLogging + DeleteTrail + UpdateTrail in one OR-tree, authored rules MUST
either document intentional narrowing in `adaptation_notes` + `companion_rule_refs`, or receive
verdict **SPLIT-NEEDED**.

### DEFECT-11: Missing `envelope.requires` routing (FC-02)

Behavioral evaluation MUST NOT run before envelope routes to correct dataset + provider.

```json
"envelope": {
  "event_type": "CloudAuditLog",
  "requires": { "dataset": "aws.cloudtrail", "cloud.provider": "aws" }
}
```

### DEFECT-12: CRITICAL offense severity with alert-only response

CRITICAL `offense.severity` without `notify_soc`, investigation pivot, or containment path
→ REWORK-MINOR minimum.

---

## Quality Gate — Weighted Scoring Rubric (1–5 per dimension)

Every SIEM rule is evaluated on **7 weighted dimensions**. Score = `(weighted_sum / 50) * 5`.

| Dimension | Weight | 1 (Poor) | 3 (Acceptable) | 5 (Excellent) |
|-----------|--------|----------|----------------|---------------|
| **Signal Strength** | 2x | Generic keyword; fires on benign admin noise | Single-API gate with outcome | Narrow API + outcome + logsource guard; high-fidelity |
| **Overlap / Provenance** | 2x | No source_provenance | One vendor cited | Both vendors cited; adaptation_notes explain narrowing |
| **Evasion Resistance** | 1.5x | Trivial sibling-API bypass undocumented | Gaps listed; companions referenced | Companions spec'd; ingest blind spots in tests |
| **Coverage** | 1.5x | Single API only; no companion plan | Companions referenced | Companions authored or full family coverage plan |
| **Log-Source Fit** | 1x | Wrong class_uid or envelope | Correct envelope | envelope + OCSF + field_registry aligned |
| **Offense Calibration** | 1x | Missing offense block | severity + group_by present | Full offense + investigation pivot + SOAR actions |
| **FP Risk** | 1x | No FP guidance; maintenance will flood SOC | FP table in doc | Tuning plan + excluded activity table |

### Verdict determination

| Score | Verdict | Mandatory actions |
|-------|---------|-------------------|
| ≥ 4.0/5 | **APPROVED** | Minor improvements optional; post score validated |
| 3.5–3.9/5 | **REWORK-MINOR** | Targeted fixes; projected post ≥ 4.0/5 |
| < 3.5/5 | **REWORK-MAJOR** | Structural redesign; provenance/offense/gates fixed |
| Any score, EDR/DLP fields only | **WRONG-LAYER** | Move to correct channel |
| Any score, Sigma bundle undivided | **SPLIT-NEEDED** | Split into per-API rules or document OR with FP analysis |

### Hard blockers — any of these = immediate REWORK-MAJOR

1. Enrichment field in AND condition tree (DEFECT-2)
2. `overlap_status: both` without both vendor IDs (DEFECT-5)
3. Wrong `ocsf.class_uid` for CloudAuditLog API (DEFECT-4)
4. Gate on `source_reference_id` (DEFECT-6)
5. Missing `source_provenance` when `stage_0_import: consolidated` (DEFECT-3)
6. Bare `event.action` gate without ext.* path and ingest blind spot documented (DEFECT-1)

---

## Required Rule Structure (all fields mandatory for board-reviewed rules)

```json
{
  "entity_type": "siem_rule",
  "id": "siem_rule_<provider>_<signal>",
  "name": "<Human-readable name>",
  "version": "1.0",
  "review_pipeline": "siem_board_v2",
  "board_verdict": "APPROVED | REWORK-MINOR | REWORK-MAJOR | WRONG-LAYER | SPLIT-NEEDED | PENDING",
  "board_score_pre": 0.0,
  "board_score_post": 0.0,

  "description": "<What it detects>. COVERAGE LIMITATION: <what it misses>. See companion rules.",

  "rule_type": "behavioral",
  "evaluation_plane": "siem_correlation",

  "envelope": {
    "event_type": "CloudAuditLog",
    "requires": { "dataset": "aws.cloudtrail", "cloud.provider": "aws" }
  },

  "ocsf": {
    "class_uid": 6003,
    "class_name": "API Activity",
    "category_uid": 6,
    "category_name": "Application Activity"
  },

  "behavioral": {
    "event_type": "CloudAuditLog",
    "class_uid": 6003,
    "condition": {
      "logic": "AND",
      "conditions": [
        { "field": "ext.aws.cloudtrail.event_name", "operator": "eq", "value": "StopLogging", "comment": "FC-04" }
      ]
    },
    "enrichment_fields": [
      "actor.user.name", "actor.user.uid", "cloud.account.id", "ext.aws.cloudtrail.trail_arn"
    ]
  },

  "source_provenance": {
    "stage_0_import": "consolidated|elastic|sigma|manual",
    "overlap_status": "both|elastic_only|sigma_only",
    "elastic": {
      "rule_id": "uuid",
      "rule_name": "...",
      "source_file": "rules/integrations/aws/...",
      "source_reference_id": "elastic:uuid",
      "license": "Elastic License 2.0",
      "adaptation_notes": "..."
    },
    "sigma": {
      "rule_id": "uuid",
      "rule_title": "...",
      "source_file": "rules/cloud/aws/...",
      "source_reference_id": "sigma:uuid",
      "adaptation_notes": "..."
    }
  },

  "offense": {
    "create_offense": true,
    "severity": "high",
    "severity_id": 4,
    "risk_score": 75,
    "group_by": ["cloud.account.id", "actor.user.uid"],
    "title_template": "...",
    "description_template": "...",
    "mitre_mapping": [{ "tactic_id": "TA0005", "technique_id": "T1562.008", "technique_name": "..." }],
    "response_actions": ["alert", "notify_soc", "create_ticket"],
    "investigation_pivot": {
      "hot_query": "...",
      "evidence_refs": ["ext.aws.cloudtrail.request_id", "ext.aws.cloudtrail.trail_arn"]
    }
  },

  "companion_rule_refs": [
    {
      "rule_id": "siem_rule_aws_cloudtrail_delete_trail",
      "type": "siem_rule",
      "priority": "P0",
      "gap": "DeleteTrail achieves same visibility loss via different API",
      "authored": false
    }
  ],

  "severity": "high",
  "enabled": true,
  "platform": "aws",
  "tags": ["aws", "cloudtrail", "siem-layer", "mitre-t1562.008"],
  "mitre": [{ "tactic_id": "TA0005", "technique_id": "T1562.008", "technique_name": "Disable or Modify Cloud Logs" }],
  "sensor_map": {
    "siem_hub": { "enabled": true, "mode": "detect", "event_source": "CloudAuditLog", "actions": ["offense"] }
  },
  "scope": { "log_sources": ["cloud_trail"], "channels": ["siem_hub"] }
}
```

---

## MODULE_09 gates (hard requirements)

| Rule | ID | Requirement |
|------|-----|-------------|
| FC-01 | `ext.*` namespace | Vendor gate fields use `ext.{domain}.{field}`. No bare ECS aliases in gates without dataset guard. |
| FC-02 | Envelope | `envelope.event_type` + `envelope.requires` route before payload evaluation. |
| FC-03 | OCSF class | `ocsf.class_uid` / `class_name` required. API audit logs use **class 6003**. |
| FC-04 | API operation | Gate on registry-backed API fields (`ext.aws.cloudtrail.event_name`), not unscoped `event.action`. |
| FC-05 | Gate vs enrichment | Gate fields present on ≥70% of matching events. Pivot fields → `enrichment_fields` only. |

---

## Documentation minimums (board-reviewed — ALL 13 sections required)

Path: `policies/siem_reviewed/docs/{rule_id}.md`

| # | Section | Purpose |
|---|---------|---------|
| 1 | **Overview Table** | Rule ID, MITRE, severity, OCSF class, pipeline version, board verdict, pre/post scores |
| 2 | **What This Rule Detects** | Plain-language summary; per-gate FP rate estimate |
| 3 | **The Cloud/SIEM Threat** | Threat narrative; why endpoint controls miss this; impact chain |
| 4 | **Vendor Detection Parity** | Elastic + Sigma + Splunk ESCU + Sentinel table: coverage, method, severity, gap |
| 5 | **Detection Coverage Matrix** | Log sources, ingest paths, normalization dependencies, enterprise deployment % |
| 6 | **Architectural Note for Analysts** | SIEM-layer vs CSPM vs EDR; deterministic rule vs ML; position in defense-in-depth |
| 7 | **Excluded Legitimate Activity** | Table: category, pattern, rationale, confirm method, over-exclusion risk |
| 8 | **Investigation Guide** | Minimum 8 steps: identity, timeline, sibling APIs, lateral correlation, containment |
| 9 | **Tuning Guidance** | 30-day onboarding, allowlists, severity tuning, coverage expansion |
| 10 | **Known Gaps / Evasion Blind Spots** | Table: gap, sibling API, companion rule, priority, detection tier |
| 11 | **Vendor Alignment (Detailed)** | Per-vendor: what catches, config required, remaining gap |
| 12 | **SOAR / Response Playbook** | Automated actions, escalation paths, evidence preservation |
| 13 | **Version History** | Version, date, change, board verdict, score |

---

## Test fixture minimums (board-reviewed only)

Path: `policies/siem_reviewed/tests/{rule_id}_tests.json`

| Array | Minimum | Notes |
|-------|---------|-------|
| `true_positives` | **8** | Full OCSF envelope; all AND gates satisfied |
| `true_negatives` | **8** | At least one gate fails; include `_failed_gate` |
| `evasion_blind_spots` | **5** | Sibling APIs, ingest gaps; `_companion_rule_needed` |

### Required metadata block

```json
{
  "rule_id": "...",
  "test_suite_version": "2.0",
  "generated_by": "siem_rule_quality_board_v2",
  "board_verdict": "REWORK-MINOR",
  "board_score_pre": 3.8,
  "board_score_post": 4.3,
  "board_metadata": {
    "log_source": "cloud_trail",
    "mitre_technique": "T1562.008",
    "ocsf_class_uid": 6003,
    "envelope_event_type": "CloudAuditLog",
    "review_pipeline": "siem_board_v2",
    "board_version": "2.0"
  }
}
```

### Required per-fixture fields

Every fixture object includes:

| Field | TP | TN | Evasion |
|-------|----|----|---------|
| `_test` | ✓ | ✓ | ✓ |
| `_scenario` | ✓ | ✓ | ✓ |
| `_fixture_id` | ✓ | ✓ | ✓ |
| `envelope.event_type` | ✓ | ✓ | ✓ |
| `envelope.requires.dataset` | ✓ | ✓ | ✓ |
| `ocsf.class_uid` | ✓ | ✓ | ✓ |
| `cloud.provider` | ✓ | ✓ | ✓ |
| `ext.*` gate paths | ✓ | ✓ | ✓ |
| `_failed_gate` | — | ✓ | — |
| `_companion_rule_needed` | — | — | ✓ |
| `_detection_tier` | — | — | ✓ |
| `expected_offense` | ✓ | optional | optional |

### `expected_offense` block (true positives — required)

```json
"expected_offense": {
  "should_create": true,
  "severity": "high",
  "severity_id": 4,
  "risk_score_min": 70,
  "group_by_keys_present": ["cloud.account.id", "actor.user.uid"],
  "investigation_pivot_valid": true,
  "response_actions": ["alert", "notify_soc"]
}
```

**Seed tests** in `policies/siem/` may be smaller (1 TP / 4 TN / 0 evasion) — not board-quality.

---

## Quality gate checklist (before `board_verdict: APPROVED`)

- [ ] Envelope routes before behavioral evaluation (FC-02)
- [ ] OCSF class_uid correct for log type (6003 for API audit)
- [ ] All gate fields use `ext.*` or scoped standard fields (FC-01, FC-04)
- [ ] No enrichment-only fields in AND conditions (FC-05)
- [ ] `source_provenance` cites Stage 0 inventory IDs
- [ ] `offense` block complete with investigation_pivot
- [ ] `sensor_map.siem_hub` enabled with offense action
- [ ] Board doc exists with **13 sections**
- [ ] Board tests: **≥8 / ≥8 / ≥5**
- [ ] All TP fixtures include `expected_offense`
- [ ] `board_score_post` ≥ 4.0 for APPROVED (REWORK-MAJOR below threshold)

---

## Four-artifact model (EDR / AI Security parity)

| Artifact | Stage 2 (`policies/siem/`) | Board (`policies/siem_reviewed/`) |
|----------|---------------------------|-----------------------------------|
| Rule JSON | Required | Required (improved copy) |
| Tests | Optional seed | Required (board minimums) |
| Analyst doc | — | Required (13 sections) |
| Change summary | — | Required (R0–R3 + verdict block) |

Originals in `policies/siem/` are **never modified** by the board.

---

## Companion rules

When a rule intentionally narrows a vendor bundle (Sigma multi-API → single API), document siblings:

```json
"companion_rule_refs": [
  {
    "rule_id": "siem_rule_aws_cloudtrail_delete_trail",
    "type": "siem_rule",
    "priority": "P0",
    "gap": "DeleteTrail achieves same visibility loss via different API",
    "authored": false
  }
]
```

List the same gaps in doc section 10 and `evasion_blind_spots` test fixtures.

---

## Cross-rule consistency artifact

After each log-source batch, write:
`policies/siem_reviewed/changes/CROSS_RULE_{log_source}.md`

See `siem_board_group_agent.md` for full template (mirrors AI Security `CROSS_RULE_{group}.md`).
