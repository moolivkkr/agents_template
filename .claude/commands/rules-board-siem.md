---
command: rules-board-siem
description: "Run the SIEM Rule Quality Board — multi-specialist debate pipeline that reviews siem_rule JSON files for signal quality, FP risk, evasion resistance, vendor parity, and schema compliance. Six SIEM vendor specialists (Elastic SIEM, Splunk ESCU, Sigma, Sentinel, Wiz, Palo Alto XSIAM) debate each rule across 4 rounds. Produces improved rules, test fixtures (8 TP + 8 TN + 5 evasion), analyst docs (13 sections), and change summaries."
arguments:
  - name: scope
    required: false
    description: "Scope: --all (all log sources), --log-source cloud_trail (single source), --technique T1562.008 (single MITRE technique), --rule siem_rule_aws_cloudtrail_stop_logging (single rule), --pilot (one rule + format validation). Defaults to --all."
  - name: model
    required: false
    default: sonnet
    description: "Model for group/specialist agents (default: sonnet). Opus is used automatically for Step 2b escalation (failed rules) and Step 4 final quality gate — do not override these."
  - name: batch_size
    required: false
    default: 10
    description: "Number of rules per group agent batch. Default 10 — matches EDR board pattern (SIEM rules ~2× deeper than EDR)."
  - name: dry_run
    required: false
    default: false
    description: "Review rules but do not write improved versions — report only. Useful for scoping effort before committing."
  - name: refresh_cache
    required: false
    default: false
    description: "Force-regenerate research_cache/*.md even if files exist."
  - name: improve_only
    required: false
    default: false
    description: "Only review rules already in policies/siem/ — skip gap discovery."
---

# /startup:rules-board-siem — SIEM Rule Quality Board

Read `.claude/agents/rule_board/siem/siem_rule_quality_board_orchestrator.md` and execute it.

## Key differences from /startup:rules-board (EDR)

| Dimension | EDR board | SIEM board |
|-----------|-----------|------------|
| Source corpus | `policies/edr/` | `policies/siem/` |
| Output corpus | `policies/edr_reviewed/` | `policies/siem_reviewed/` |
| Rule prefix | `edr_rule_*.json` | `siem_rule_*.json` |
| Scope axis | `--tactic` (MITRE tactic) | `--log-source` (cloud_trail, azure_activity, etc.) |
| Specialists | 4 EDR vendors | 6 SIEM vendors (Elastic, Splunk ESCU, Sigma, Sentinel, Wiz, XSIAM) |
| Test minimum | 8 TP / 6 TN / 3 evasion | **8 TP / 8 TN / 5 evasion** |
| Doc standard | 8 sections | **13 sections** |
| Stage 0 pre-check | Optional | **Required** (vendor overlap matrix) |
| Schema standard | `.claude/agents/rule_board/RULE_AUTHORING_STANDARDS.md` | `.claude/agents/rule_board/siem/RULE_AUTHORING_STANDARDS.md` |
| Hard blocker list | 6 blockers | **12 SIEM-specific blockers** (DEFECT-1 through DEFECT-12) |

## Pre-flight

1. Count rules in scope:
```bash
if [ "{{scope}}" = "--all" ] || [ -z "{{scope}}" ]; then
  TOTAL=$(find policies/siem -name "siem_rule_*.json" | wc -l | tr -d ' ')
  echo "Total siem_rule files: $TOTAL"
else
  echo "Scope: {{scope}}"
fi
```

2. Check Stage 0 inventory (required — unlike EDR where this is optional):
```bash
INVENTORY=agent_state/siem_pipeline/stage_0/consolidated_inventory.json
if [ -f "$INVENTORY" ]; then
  echo "Stage 0 inventory: OK ($(python3 -c 'import json; d=json.load(open("'$INVENTORY'")); print(len(d)) 2>/dev/null || echo "?") rules)"
else
  echo "WARNING: Stage 0 inventory missing. Board will use rules-as-authored without gap context."
  echo "Run: /startup:rules-plugin --plugin siem --stage 0  (to populate)"
fi
```

3. Check research cache:
```bash
CACHE=$(ls policies/siem_reviewed/research_cache/*_research.md 2>/dev/null | wc -l | tr -d ' ')
echo "Research cache: $CACHE files"
if [ "$CACHE" -eq 0 ]; then
  echo "NOTE: No cache — Step 0.5 will run full vendor research before group agents."
  echo "      Expect ~2x longer first run. Subsequent runs reuse cache."
fi
```

4. Check vendor cache (Elastic + Sigma corpus):
```bash
ELASTIC=$(find agent_state/siem_pipeline/stage_0/vendor_cache/elastic -name "*.toml" 2>/dev/null | wc -l | tr -d ' ')
SIGMA=$(find agent_state/siem_pipeline/stage_0/vendor_cache/sigma -name "*.yml" 2>/dev/null | wc -l | tr -d ' ')
echo "Vendor cache: Elastic=$ELASTIC Sigma=$SIGMA"
```

5. Read the authoring standards (board enforces these):
```bash
cat .claude/agents/rule_board/siem/RULE_AUTHORING_STANDARDS.md | head -50
```

## Scope Resolution

Parse `{{scope}}`:

| Flag | Behavior |
|------|----------|
| `--all` or empty | All log sources — batched in parallel (cloud_trail, azure_activity, gcp_audit, windows_event, okta_system, dns, syslog, proxy) |
| `--log-source {name}` | Single log source directory: `policies/siem/{name}/siem_rule_*.json` |
| `--technique {T-number}` | Filter to rules where `mitre[0].technique_id` matches (or starts with) `{T-number}` |
| `--rule {rule_id}` | Single rule deep review — full 4-specialist, 4-round debate, all 4 output artifacts |
| `--pilot` | One rule (first in cloud_trail) + format validation only — no writes, confirms pipeline runs |

For `--all`: split rules into parallel groups by log source. Each log source → one group agent.
Priority order: cloud_trail → azure_activity → gcp_audit → windows_event → okta_system → dns → syslog → proxy → other.

## Model Selection

Model assignment is fixed per pipeline step — not a single global flag:

| Step | Agent | Model | Reason |
|------|-------|-------|--------|
| Step 0.5 | Research cache generation | **sonnet** | Structured research, no judgment required |
| Step 2 | Group agents (R0–R3 debate) | **sonnet** | Structured format; 7 specialists produce scored output |
| Step 2b | Quality gate failure escalation | **opus** | Rules that couldn't reach 4.0/5 need deepest structural redesign |
| Step 3 | Consolidation | **sonnet** | Aggregating change docs, not making quality calls |
| Step 4 | Final quality validation | **opus** | Hard gate — determines APPROVED vs blocked. Must be highest quality. |
| `--rule` single rule | Full deep review | **opus** | Scoped to one rule; quality matters more than cost |
| `--pilot` | Format validation | **sonnet** | Dry run only |

The `{{model}}` argument controls Step 2 group agents only. Steps 2b and 4 always use opus.

## Execution

Follow the orchestrator exactly — read it now:

```
.claude/agents/rule_board/siem/siem_rule_quality_board_orchestrator.md
```

### Step order

| Step | What happens |
|------|-------------|
| Step 0 | Merge Stage 0 inventory, create output dirs |
| Step 0.5 | Pre-flight research cache (per log-source + technique families, run BEFORE groups) |
| Step 1 | Discover rules, batch by log source |
| Step 2 | Spawn parallel group agents (one per log source, `{{batch_size}}` rules/batch) |
| Step 2b | Quality gate failure escalation (rules that exit < 4.0/5 re-reviewed) |
| Step 3 | Consolidation — cross-log-source consistency check |
| Step 4 | Final quality validation — board_score_post ≥ 4.0 gate |
| Step 5 | Final report → REVIEW_SUMMARY.md + OPPORTUNITY_REPORT.md |

### Output locations

```
policies/siem_reviewed/
  {log_source}/
    {rule_id}.json                  ← improved rule (originals in policies/siem/ untouched)
  tests/
    {rule_id}_tests.json            ← 8 TP + 8 TN + 5 evasion fixtures
  docs/
    {rule_id}.md                    ← analyst doc (13 mandatory sections)
  changes/
    {rule_id}_changes.md            ← R0→R1→R2→R3 debate record
    CROSS_RULE_{log_source}.md      ← cross-rule consistency findings per source
  research_cache/
    {logsource}_{technique}_research.md
  REVIEW_SUMMARY.md
  OPPORTUNITY_REPORT.md
```

### Hard blockers (any = immediate REWORK-MAJOR, stops group agent advancement)

Read `.claude/agents/rule_board/siem/RULE_AUTHORING_STANDARDS.md` DEFECT-1 through DEFECT-12.
Most critical:
- **DEFECT-1**: Bare `event.action` gate without `ext.*` path (zero-detection on mis-mapped ingest)
- **DEFECT-2**: Enrichment fields in AND conditions (FC-05 violation)
- **DEFECT-4**: Wrong OCSF `class_uid` for log type (API audit ≠ 3002)
- **DEFECT-9**: Missing or incomplete `offense` block
- **DEFECT-11**: Missing `envelope.requires` routing

## Cost Optimization

Six optimizations (mirrors EDR board, SIEM-calibrated):

| Optimization | Detail |
|---|---|
| **Inline protocol** | Specialist criteria embedded in group agent prompt — no 4–7 .md file reads per call |
| **Pre-indexed vendor cache** | `vendor_index.json` built once at Step 0.5 (Elastic + Sigma keyed by technique). Group agents do key lookup instead of grepping 6,299 files per rule |
| **DEFECT pre-scan fast-track** | 5-item check (DEFECT-1,-2,-4,-9,-11) before R0. Rules with 0 defects + overlap ≥ 2 are APPROVED immediately — no R0–R3, no test files, no docs |
| **Reduced DEFECT checklist** | 5 critical items only (zero-detection set) vs full DEFECT-1–12 during R0. Full checklist runs only on REWORK-MAJOR |
| **Batch amortization** | 20 rules/agent (vs prior 5) — 18K prompt overhead amortized 4× more |
| **Conditional test generation** | Tests only for REWORK-MINOR/MAJOR. Docs (13 sections) only for REWORK-MAJOR. APPROVED rules get 1-line change entry only |

- Research cache (`Step 0.5`): **reuse across runs** — never regenerate unless `--refresh-cache`
- `vendor_index.json`: **build once at Step 0.5** — skip rebuild if file exists
- `--dry-run`: generates verdict + score projection without writing files (saves ~40% cost)

## Specialist roles

Each group agent runs all 6 specialist viewpoints internally (not as separate agents):

| Specialist | Scope | Key concern |
|------------|-------|-------------|
| Elastic SIEM | `elastic/detection-rules` EQL/KQL parity | ECS → MODULE_09 ext.* field mapping |
| Splunk ESCU | ESCU analytic stories + SPL parity | CIM data model alignment, tstats acceleration |
| Sigma | Sigma rule bundle overlap | Multi-API bundle → per-API split decisions |
| Microsoft Sentinel | Sentinel analytic rule parity | KQL translation, ASIM normalization |
| Wiz | Cloud posture signal quality | CSPM companion rule gaps |
| Palo Alto XSIAM | XSIAM correlation rule parity | BIOC/XQL translation |

## SIEM-specific quality dimensions (7 weighted)

| Dimension | Weight |
|-----------|--------|
| Signal Strength | 2x |
| Overlap / Provenance | 2x |
| Evasion Resistance | 1.5x |
| Coverage | 1.5x |
| Log-Source Fit | 1x |
| Offense Calibration | 1x |
| FP Risk | 1x |

Score = `(weighted_sum / 50) × 5`. Target: ≥ 4.0/5 for APPROVED.
