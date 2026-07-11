# /cspm-board — CSPM Rule Quality Board Orchestrator

A 6-specialist review pipeline for Cloud Security Posture Management rules. Evaluates every
cspm_rule for API accuracy, cloud provider parity, compliance mapping, false positive risk,
evasion resistance, and operational readiness.

**Quality standard:** Every rule must exit with projected post-improvement score >= 4.0/5.

**Specialists (6):**
- 3 cloud provider: AWS Security, Azure Security, GCP Security (sonnet)
- Schema Validator: DEFECT-1 through DEFECT-12 checklist (sonnet)
- SOC/Cloud Analyst: alert fatigue, IaC FP estimation, triage speed (sonnet)
- Compliance Mapper: CIS Benchmark, NIST 800-53, SOC 2, PCI DSS mapping (sonnet)

**Standards:** `.claude/agents/rule_board/cspm/CSPM_RULE_AUTHORING_STANDARDS.md`

## Model Assignment

| Step | Agent | Model |
|------|-------|-------|
| Step 0-1 | Discovery / batching | orchestrator/parent |
| Step 2 | Group agents (batch review) | **sonnet** |
| Step 3 | Consolidation | **sonnet** |
| `--rule` single rule | Full deep review | **opus** |

## Invocation

```
/cspm-board --all                              # all rules (parallel by provider)
/cspm-board --provider aws                     # single provider
/cspm-board --rule cspm_rule_aws_s3_public     # single rule deep review
```

## Output

All output to `policies/cspm/` (in-place):

```
policies/cspm/
  {provider}/
    {rule_id}.json             ← improved rule (in-place update)
  tests/
    {rule_id}_tests.json       ← test fixtures (TP + TN + evasion)
  changes/
    {rule_id}_changes.md       ← what changed, why
    CROSS_RULE_{provider}.md   ← cross-rule consistency
  REVIEW_SUMMARY.md            ← cross-provider findings
```

---

## Step 0 — Discovery and Batching

```bash
find policies/cspm -name "cspm_rule_*.json" \
  -not -path "*/tests/*" -not -path "*/changes/*" \
  -not -path "*/shared/*" \
  | sort > /tmp/cspm_board_all_rules.txt

TOTAL=$(wc -l < /tmp/cspm_board_all_rules.txt | tr -d ' ')
echo "Total CSPM rules to review: $TOTAL"

mkdir -p policies/cspm/{changes,tests}
```

Filter out test fixture files (files with `test_suite_version` field):
```python
# Only process actual rules, not test fixture JSONs
import json
d = json.load(open(path))
if 'test_suite_version' in d: skip  # test fixture, not a rule
if d.get('entity_type') != 'cspm_rule': skip
```

## Step 0.5 — Vendor Index Verification (REQUIRED)

CSPM rules are compared against a pre-built unified vendor index containing 3,350 checks from 10 sources.

```bash
INDEX="policies/cspm/research_cache/cspm_unified_index.json"
test -f "$INDEX" || echo "BLOCKED: Run CSPM Stage 0 cache build first"

python3 -c "
import json
idx = json.load(open('$INDEX'))
print('Vendor index loaded:')
for src, count in idx['sources']['open_source'].items():
    print(f'  {src}: {count}')
for src, count in idx['sources']['commercial_docs'].items():
    print(f'  {src}: {count}')
print(f'  Total: {idx[\"sources\"][\"total\"]}')
"
```

**Sources indexed (DO NOT use training knowledge — use the index):**

| Source | Type | Checks |
|--------|------|--------|
| Prowler | Open source posture | 879 |
| CloudSploit | Open source posture | 1,481 |
| Elastic | Cloud SIEM rules | 362 |
| Sigma | Cloud rules | 230 |
| AWS Config | Managed rules (docs) | 76 |
| Azure Policy | Built-in policies (docs) | 78 |
| GCP SCC | Built-in findings (docs) | 72 |
| Wiz | CSPM rules (docs) | 75 |
| Prisma Cloud | Policies (docs) | 80 |

Group agents load `cspm_unified_index.json` ONCE per batch and use dict lookups — no file grep, no web search.

## Step 1 — Assign Rules to Groups by Provider

| Group | Provider/Category | Rules |
|-------|-------------------|-------|
| **G1** | `aws/` | ~87 rules |
| **G2** | `azure/` | ~57 rules |
| **G3** | `gcp/` + `cloud_infrastructure/` + `cloud_iam/` | ~55 rules |
| **G4** | `ai_platform/` + `cloud_identity_provider/` + `hypervisor/` | ~15 rules |

## Step 2 — Spawn Group Agents in PARALLEL (sonnet)

```
Agent prompt (per group):
"You are running the CSPM Rule Quality Board for {PROVIDER}.

VENDOR INDEX (load ONCE, use for ALL rules):
  policies/cspm/research_cache/cspm_unified_index.json
  3,350 checks from Prowler + CloudSploit + Elastic + Sigma + AWS Config + Azure Policy + GCP SCC + Wiz + Prisma Cloud
  Use dict lookups — DO NOT use training knowledge for vendor comparison.

PROTOCOL (do NOT read agent .md files — everything is in this prompt):
For each rule:
1. Read rule → extract id, provider, API operation, severity
2. Vendor lookup → IDX['by_api_operation'][api_op] + IDX['vendor_docs'][provider]
3. DEFECT scan → 5 critical items: API exists(D1), field path(D2), outcome gate(D3), no EDR fields(D4), enrichment not in AND(D5)
4. Score → 7 dimensions (API Accuracy 2×, FP Risk 2×, Evasion 1.5×, Provider Parity 1.5×, Compliance 1×, Response 1×, Ops Ready 1×)
5. Verdict: ≥4.0→APPROVED (1 line), 3.5-4.0→REWORK-MINOR, <3.5→REWORK-MAJOR
6. Test cases ONLY for REWORK: 5 TP + 5 TN + 3 evasion

Rules: find all cspm_rule_*.json in policies/cspm/{provider}/
  — exclude files with 'test_suite_version' (test fixtures)
  — exclude files without entity_type: cspm_rule
Modify rules IN PLACE in policies/cspm/{provider}/.
Write changes to policies/cspm/changes/.
Write test files to policies/cspm/tests/.

SCORE OUTPUT: Write BATCH_{provider}_scores.json"
```

## Step 2b — Quality Gate Verification

```python
import json, os
for provider in ['aws', 'azure', 'gcp_multi', 'identity']:
    score_file = f'policies/cspm/changes/BATCH_{provider}_scores.json'
    if not os.path.exists(score_file):
        print(f'BLOCKED: {provider} score file missing')
        continue
    scores = json.load(open(score_file))
    for r in scores.get('rules', []):
        if r.get('score_post', r.get('score', 0)) < 4.0:
            print(f"QUALITY GATE: {r['rule_id']} at {r.get('score_post', r.get('score'))}/5")
```

## Step 3 — Consolidation

Produce `policies/cspm/REVIEW_SUMMARY.md` and cross-provider findings.

## Step 4 — Final Report

```
CSPM Rule Quality Board Complete
═══════════════════════════════════════════════════════
Rules reviewed:      N
  APPROVED:          N
  REWORK-MINOR:      N
  REWORK-MAJOR:      N
  WRONG-LAYER:       N  (should be SIEM/EDR)

Score improvement:
  Average pre:  N.N/5
  Average post: N.N/5

Provider coverage:
  AWS:    N rules
  Azure:  N rules
  GCP:    N rules
  Other:  N rules
═══════════════════════════════════════════════════════
```

---

## 7 Evaluation Dimensions (CSPM-specific)

| # | Dimension | Weight | What It Measures |
|---|-----------|--------|------------------|
| 1 | **API Accuracy** | 2× | Correct API operation names, field paths, response codes |
| 2 | **FP Risk** | 2× | IaC/Terraform FP rate, org-level policy exceptions, legitimate use cases |
| 3 | **Evasion Resistance** | 1.5× | Alternative APIs achieving same result, split operations, eventual consistency |
| 4 | **Provider Parity** | 1.5× | Equivalent rule exists for other providers? Cross-cloud consistency? |
| 5 | **Compliance Mapping** | 1× | CIS Benchmark, NIST 800-53, PCI DSS, SOC 2 correctly cited? |
| 6 | **Response Calibration** | 1× | Severity matches blast radius? Remediation guidance accurate? |
| 7 | **Operational Readiness** | 1× | CloudTrail/Activity Log/Audit Log field paths correct? Ingest blind spots? |

**Score = weighted_sum / 50 × 5 = N.N/5**

## Hard Blockers (= REWORK-MAJOR)

- API operation name doesn't exist in the cloud provider's API
- Field path references non-existent CloudTrail/Activity Log field
- Enrichment field (identity ARN, trail ARN) in AND condition tree
- Missing `event.outcome: success` gate (fires on failed attempts = noise)
- EDR-only fields (process.name, file.path) in CSPM rule = WRONG-LAYER
- Severity=critical on routine admin API call without anomaly qualifier
- No IaC/Terraform exclusion for configuration-management operations
