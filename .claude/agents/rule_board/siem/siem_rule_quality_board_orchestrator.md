# /siem-board — SIEM Rule Quality Board Orchestrator (Ultra-Deep)

Runs the full SIEM Rule Quality Board on rules in `policies/siem/`. Six primary vendor specialists
(Elastic, Splunk ESCU, Wiz, Palo Alto XSIAM, Prophet Security, Matano) plus Sigma overlap reference
debate each rule across 4 rounds with mandatory quality gates, then produce improved rules + test
fixtures + analyst docs + change summaries.

**Quality standard:** Every rule must exit the pipeline with a projected post-improvement score >= 4.0/5.
Groups with rules that cannot reach this threshold escalate to the orchestrator for re-review.

**Mode:** Construction + fine-tuning — no publish, no UI, no `plugin.go` compile gate.

## Model Assignment (read this first — do not deviate)

| Step | Agent spawned | Model | Rationale |
|------|--------------|-------|-----------|
| Step 0.5 | Research cache agents | **sonnet** | Structured research, reused across runs |
| Step 2 | Group agents (R0–R3 debate, all 7 specialists) | **sonnet** | Structured format; high throughput needed |
| Step 2b | Escalation re-review (rules < 4.0/5) | **opus** | Failed rules need deepest structural analysis |
| Step 3 | Consolidator | **sonnet** | Aggregating docs, not making quality judgments |
| Step 4 | Final quality validation | **opus** | Hard gate — determines publish eligibility |
| Step 5 | Report writer | orchestrator/parent | Lightweight summary only |
| `--rule` mode | Single rule full review | **opus** | Scoped; quality > cost |
| `--pilot` mode | Format validation | **sonnet** | Dry run only |

**Non-negotiable:** Steps 2b and 4 ALWAYS use opus regardless of `--model` argument.
Any agent that deviates and uses sonnet for Step 4 produces an unreliable quality gate.

## Invocation

```
/siem-board --all                                     # all rules (parallel by log source)
/siem-board --scope cloud_trail                       # single log source (pilot)
/siem-board --rule siem_rule_aws_cloudtrail_stop_logging
/siem-board --refresh-cache                           # regenerate missing research_cache/*.md
/siem-board --improve-only                            # only existing policies/siem/** rules
/siem-board --add-missing                             # gap handoff → rules-plugin Stage 2
/siem-board --consolidate-only                        # skip groups; run consolidator only
/siem-board --pilot                                   # single rule + cache + format validation
```

Alias (Cursor skill): `/rule-board --plugin siem` → this orchestrator.

## Output Structure

```
policies/siem_reviewed/
  {log_source}/                 # e.g. cloud_trail/
    {rule_id}.json             <- improved rule (do NOT modify originals)
  tests/
    {rule_id}_tests.json       <- TP (>=8) + TN (>=8) + evasion (>=5) test fixtures
  docs/
    {rule_id}.md               <- analyst help page (13 sections)
  changes/
    {rule_id}_changes.md       <- full R0->R1->R2->R3 debate record (10 sections)
    CROSS_RULE_{log_source}.md <- cross-rule consistency per log source
  research_cache/
    {logsource}_{technique}_research.md
  REVIEW_SUMMARY.md            <- cross-log-source findings + systemic issues
  OPPORTUNITY_REPORT.md        <- ranked improvement opportunities + companion backlog

agent_state/rule_board/siem/
  coverage_index.json           # authored vs inventory gaps
```

---

## Step 0 — Merge Stage 0 inventory (rules-plugin)

**Do not re-clone Elastic/Sigma here** — Stage 0 is owned by `rule_source_consolidator_agent`.

```bash
cd /Users/kishoremoli/development/dlp-composer

INVENTORY=agent_state/siem_pipeline/stage_0/consolidated_inventory.json
test -f "$INVENTORY" || echo "BLOCKED: run /startup/rules-plugin --plugin siem --stage 0 first"

mkdir -p policies/siem_reviewed/{cloud_trail,tests,docs,changes,research_cache}
mkdir -p agent_state/rule_board/siem
```

Run coverage_index builder (see prior orchestrator Step 0 python block) — unchanged.

### `--add-missing` handoff

When flag set, write gap backlog to `policies/siem_reviewed/changes/INVENTORY_GAPS.md` and **stop**.

Do **not** author new `siem_rule_*.json` inside the board — Stage 2 owns greenfield.

---

## Step 0.5 — Pre-flight Research Phase (run BEFORE group agents) `[MODEL: sonnet]`

**Purpose:** R0 is logsource+technique scoped. Cache once per family; group agents load cache in Round 0.
Vendor corpora and cross-vendor overlap are built in Step 0.5 (not Stage 0).

```bash
# Vendor cache + overlap index (run once or after --refresh-cache)
python3 agent_state/siem_pipeline/stage_0/build_vendor_overlap.py
```

Read: `agent_state/siem_pipeline/stage_0/vendor_cache/VENDOR_SOURCES.md`
Read overlap: `agent_state/siem_pipeline/stage_0/vendor_overlap_matrix.md`
Read index: `agent_state/siem_pipeline/stage_0/vendor_unique_rules_index.json`

Read taxonomy: `.claude/agents/rule_board/siem/logsource_taxonomy.md`

### Build Vendor Lookup Index (run once — replaces per-rule grep)

Build `agent_state/siem_pipeline/stage_0/vendor_index.json` — a pre-keyed lookup that group agents
use instead of grepping 6,299 files per rule. Generated once; reused across all runs.

```python
# Builds from consolidated_inventory.json (3,952 entries) — richer than raw TOML/YAML grep
import json
from pathlib import Path

INV = Path("agent_state/siem_pipeline/stage_0/consolidated_inventory.json")
OUT = Path("agent_state/siem_pipeline/stage_0/vendor_index.json")

inv     = json.load(INV.open())
entries = inv.get("entries", [])
by_technique = {}

for e in entries:
    techs = set()
    for m in e.get("mitre", []):
        t = m.get("technique_id")
        if t:
            techs.add(t)
            if "." in t:
                techs.add(t.split(".")[0])   # also index parent (T1562 for T1562.008)
    entry = {k: e.get(k, "") for k in
             ["inventory_id", "title", "log_source", "overlap_status",
              "elastic_rule_id", "elastic_file", "sigma_id", "sigma_file"]}
    for t in techs:
        by_technique.setdefault(t, []).append(entry)

index = {
    "generated": "auto",
    "source": "consolidated_inventory.json",
    "total_entries": len(entries),
    "techniques_covered": len(by_technique),
    "by_technique": by_technique,
}
OUT.write_text(json.dumps(index, separators=(",", ":")))
print(f"vendor_index.json: {len(by_technique)} technique keys, {len(entries)} source entries")
```

Group agents look up technique with:
```python
idx  = json.load(open("agent_state/siem_pipeline/stage_0/vendor_index.json"))
hits = idx.get("by_technique", {}).get("T1562.008", [])
elastic = [r for r in hits if r.get("elastic_file")]
sigma   = [r for r in hits if r.get("sigma_file")]
# elastic[i]["elastic_file"] → path relative to elastic-detection-rules/rules/ cache
# sigma[i]["sigma_file"]     → path relative to sigma/rules/ cache
```

Skip rebuild if `vendor_index.json` exists and `--refresh-cache` not set.

### Check cache

```bash
ls policies/siem_reviewed/research_cache/*_research.md 2>/dev/null
```

Pilot requires: `cloud_trail_T1562.008_research.md`

P0 log sources (pre-generated families): `cloud_trail`, `azure_activity`, `gcp_audit`, `okta_system`, `proxy`

If `--refresh-cache` or files missing → spawn research agents **in parallel** (one per missing family).

### Research agent prompt template

```
You are the SIEM R0 Research Agent for: {logsource} / {technique_id}

Read all 6 specialist agent files:
  .claude/agents/rule_board/siem/elastic_siem_specialist.md
  .claude/agents/rule_board/siem/sigma_specialist.md
  .claude/agents/rule_board/siem/splunk_escu_specialist.md
  .claude/agents/rule_board/siem/wiz_specialist.md
  .claude/agents/rule_board/siem/palo_alto_specialist.md
  .claude/agents/rule_board/siem/prophet_security_specialist.md
  .claude/agents/rule_board/siem/matano_specialist.md

Read taxonomy: .claude/agents/rule_board/siem/logsource_taxonomy.md
Read inventory: agent_state/siem_pipeline/stage_0/consolidated_inventory.json
Read overlap for this family: policies/siem_reviewed/research_cache/{logsource}_{technique_id}_research.md
  (section ## Cross-Vendor Overlap Summary) and vendor_unique_rules_index.json

Execute full R0 protocol from each specialist for this logsource+technique family.
Produce ONE cache file with all 6 specialists' complete R0 blocks + Sigma overlap summary.

Output: policies/siem_reviewed/research_cache/{logsource}_{technique_id}_research.md

Format:

# R0 Research Cache — {logsource} / {technique_id}
Generated: {date}
Log source: {logsource}
MITRE: {technique_id}
Rules covered: {list}

## Cross-Vendor Overlap Summary
- Consensus rules (3+ vendors): ...
- Vendor-unique highlights: Wiz-only, Palo Alto-only, Splunk-only, Prophet-only, Matano-only, Elastic-only
- Semantic variants (same MITRE, different field logic): ...
- Recommended canonical source for board: elastic | splunk | sigma | ...

---

## [ELASTIC SIEM] R0 Research
[Full R0 block — elastic_siem_specialist.md]

---

## [SIGMA] R0 Research
[Full R0 block — sigma_specialist.md — overlap reference, not 7th primary vendor]

---

## [SPLUNK ESCU] R0 Research
[Full R0 block — splunk_escu_specialist.md]
research_mode: live | stub

---

## [WIZ] R0 Research
[Full R0 block — wiz_specialist.md]
research_mode: live | reference

---

## [PALO ALTO XSIAM] R0 Research
[Full R0 block — palo_alto_specialist.md]

---

## [PROPHET SECURITY] R0 Research
[Full R0 block — prophet_security_specialist.md]
research_mode: reference (no public YAML corpus)

---

## [MATANO] R0 Research
[Full R0 block — matano_specialist.md]

---

## Log-Source-Specific Notes
[Fields, event names, MODULE_09 quirks for rules in this family]

Write marker: /tmp/siem_research_{logsource}_{technique_id}.done
```

### Pilot cache assignments

| Cache file | Log source | MITRE | Inventory entries |
|------------|------------|-------|-------------------|
| `cloud_trail_T1562.008_research.md` | cloud_trail | T1562.008 | inv_cloudtrail_stop_logging, inv_cloudtrail_delete_trail |

Proceed to Step 1 when required cache files exist.

---

## Step 1 — Discovery and batching `[MODEL: orchestrator/parent]`

```bash
find policies/siem -name "siem_rule_*.json" \
  | grep -v "siem_ruleset" \
  | grep -v "/tests/" \
  | sort > /tmp/siem_board_all_rules.txt
```

Group by `scope.log_sources[]` / directory under `policies/siem/`.

---

## Step 2 — Parallel groups by log source `[MODEL: sonnet]`

**Pilot:** one group — `cloud_trail`.

| Group | Log source | Rules (pilot) |
|-------|------------|---------------|
| **G1** | `cloud_trail` | `siem_rule_aws_cloudtrail_stop_logging` |

Skip if `--consolidate-only`.

### Group agent spawn `[MODEL: sonnet]`

```
MODEL: sonnet

You are running the SIEM Rule Quality Board for log source: {LOG_SOURCE}.

Read the board agent definition:
  .claude/agents/rule_board/siem/siem_board_group_agent.md

And all 7 specialist files:
  .claude/agents/rule_board/siem/elastic_siem_specialist.md
  .claude/agents/rule_board/siem/sigma_specialist.md
  .claude/agents/rule_board/siem/splunk_escu_specialist.md
  .claude/agents/rule_board/siem/sentinel_specialist.md
  .claude/agents/rule_board/siem/siem_policy_author.md
  .claude/agents/rule_board/siem/siem_schema_validator.md
  .claude/agents/rule_board/siem/soc_analyst.md

Your assigned rules:
  {RULE_FILE_LIST}

QUALITY REQUIREMENTS (non-negotiable):
1. Every rule must exit with projected post-improvement score >= 4.0/5
2. All 4 quality gates between rounds MUST be passed before advancing
3. Round 2 MUST have >= 8 challenge pairs with genuine tension
4. REWORK-MAJOR rules MUST have gates/provenance/offense structurally fixed
5. Test fixtures MUST meet: >= 8 TP + >= 8 TN + >= 5 evasion cases per rule
6. All TP fixtures MUST include expected_offense block
7. All enrichment fields MUST be in enrichment_fields, NOT in AND conditions
8. Analyst docs MUST have all 13 sections
9. Splunk/Sentinel stubs MUST document parity GAP when no analytic exists

Load R0 from policies/siem_reviewed/research_cache/ — do NOT repeat web research.

Output to policies/siem_reviewed/{log_source}/
Do NOT modify policies/siem/ originals.

After all rules: write CROSS_RULE_{log_source}.md
Write: /tmp/siem_board_group_{LOG_SOURCE}.done
Write: /tmp/siem_board_group_{LOG_SOURCE}_scores.json
```

**Verify each group completes with quality:**

```bash
test -f /tmp/siem_board_group_cloud_trail.done || echo "BLOCKED: cloud_trail group"

python3 -c "
import json, sys
issues = []
for ls in ['cloud_trail']:
    try:
        scores = json.load(open(f'/tmp/siem_board_group_{ls}_scores.json'))
        for r in scores['rules']:
            if r['score_post'] < 4.0:
                issues.append(f\"{ls} / {r['rule_id']}: post {r['score_post']}/5 < 4.0\")
            if r.get('test_tp_count', 0) < 8:
                issues.append(f\"{ls} / {r['rule_id']}: only {r.get('test_tp_count')} TP (need >= 8)\")
            if r.get('test_evasion_count', 0) < 5:
                issues.append(f\"{ls} / {r['rule_id']}: only {r.get('test_evasion_count')} evasion (need >= 5)\")
    except Exception as e:
        issues.append(f'{ls}: score file missing ({e})')
if issues:
    print('QUALITY GATE FAILURES:')
    for i in issues: print(f'  - {i}')
    sys.exit(1)
else:
    print('All quality gates passed')
"
```

---

## Step 2b — Quality Gate Failure Escalation `[MODEL: opus — ALWAYS, non-negotiable]`

If any rule fails post-improvement score gate (< 4.0/5), spawn targeted re-review:

```
You are re-reviewing SIEM rule {rule_id} which exited at {score_post}/5.

Read improved rule + change summary. Identify structural gaps.
If SPLIT-NEEDED or WRONG-LAYER: document and do not force APPROVED.
Update all 4 artifacts. Increment version. Append escalation section to change summary.
```

---

## Step 3 — Consolidation `[MODEL: sonnet]`

Spawn consolidator with `--plugin siem`:

```
Read: .claude/agents/rule_board/rule_board_consolidator.md (PLUGIN=siem)

Inputs:
  policies/siem_reviewed/changes/*.md
  policies/siem_reviewed/changes/CROSS_RULE_*.md
  /tmp/siem_board_group_*_scores.json
  agent_state/rule_board/siem/coverage_index.json

Outputs:
  policies/siem_reviewed/REVIEW_SUMMARY.md
  policies/siem_reviewed/OPPORTUNITY_REPORT.md
```

---

## Step 4 — Final Quality Validation `[MODEL: opus — ALWAYS, non-negotiable]`

```bash
RULES=$(wc -l < /tmp/siem_board_all_rules.txt 2>/dev/null | tr -d ' ')
IMPROVED=$(find policies/siem_reviewed -name "*.json" ! -path "*/tests/*" ! -path "*/research_cache/*" | wc -l | tr -d ' ')
TESTS=$(find policies/siem_reviewed/tests -name "*_tests.json" | wc -l | tr -d ' ')
DOCS=$(find policies/siem_reviewed/docs -name "*.md" | wc -l | tr -d ' ')
CHANGES=$(find policies/siem_reviewed/changes -name "*_changes.md" | wc -l | tr -d ' ')

test -f policies/siem_reviewed/REVIEW_SUMMARY.md && echo "REVIEW_SUMMARY: PASS" || echo "MISSING"
test -f policies/siem_reviewed/OPPORTUNITY_REPORT.md && echo "OPPORTUNITY_REPORT: PASS" || echo "MISSING"
```

---

## Step 5 — Final Report `[MODEL: orchestrator/parent]`

```
SIEM Rule Quality Board Complete
=================================================================
Rules reviewed:      N
  APPROVED:          N  (score >= 4.0/5)
  REWORK-MINOR:      N
  REWORK-MAJOR:      N
  WRONG-LAYER:       N
  SPLIT-NEEDED:      N

Score improvement:
  Average pre-improvement:  N.N/5
  Average post-improvement: N.N/5
  Rules reaching >= 4.0/5:  N/N (N%)

Test coverage:
  Total TP test cases:      N (avg N per rule, target >= 8)
  Total TN test cases:      N (avg N per rule, target >= 8)
  Total evasion cases:      N (avg N per rule, target >= 5)

Specialists: Elastic SIEM, Sigma, Splunk ESCU (stub), Sentinel (stub)
Companion rules authored: N | Referenced only: N

Hard blockers found and fixed:
  Enrichment in AND conditions: N rules
  Missing source_provenance: N rules
  bare event.action gates: N rules

Full summary:        policies/siem_reviewed/REVIEW_SUMMARY.md
Opportunity report:  policies/siem_reviewed/OPPORTUNITY_REPORT.md
=================================================================
```

---

## Board Evaluation Dimensions (all 4 specialists score these)

| Dimension | Weight | What It Measures |
|-----------|--------|------------------|
| **Signal Strength** | 2x | API specificity, outcome gate, logsource guard |
| **Overlap / Provenance** | 2x | Elastic + Sigma IDs, adaptation_notes |
| **Evasion Resistance** | 1.5x | Sibling API bypasses, ingest blind spots |
| **Coverage** | 1.5x | Companion rules for excluded vendor branches |
| **Log-Source Fit** | 1x | envelope, OCSF class, dataset |
| **Offense Calibration** | 1x | severity, group_by, investigation_pivot |
| **FP Risk** | 1x | Maintenance FP at enterprise scale |

Score = (weighted_sum / 50) * 5 = N.N/5

## Hard Blockers — any of these = immediate REWORK-MAJOR

1. Enrichment field in AND condition tree (FC-05)
2. `overlap_status: both` without both vendor IDs in `source_provenance`
3. Wrong `ocsf.class_uid` for CloudAuditLog API (6003)
4. Gate on `source_reference_id`, `session_id`, or `trace_id`
5. Missing `source_provenance` when `stage_0_import: consolidated`
6. Bare `event.action` gate without ext.* path and documented ingest blind spot
7. EDR-only fields with no log ingest path → WRONG-LAYER
8. Missing offense block when `require_offense_block: true`
9. Whole Sigma OR-tree imported without SPLIT-NEEDED or companion plan
10. protections-artifacts cited as SIEM parity source

---

## Pilot Mode (format validation before full run)

```
/siem-board --pilot
```

Runs on `siem_rule_aws_cloudtrail_stop_logging` sequentially.

Pilot acceptance criteria (ALL must pass before `--all`):

- [ ] All 4 output files present per rule
- [ ] Change summary has all 10 sections (R0, R1, R2, R3, Verdict, Changes, Rejected, Gaps, Test Delta, scaffold label if pilot)
- [ ] Help page has all **13 sections**
- [ ] Test fixtures meet >= 8 TP + >= 8 TN + >= 5 evasion
- [ ] All TP fixtures include `expected_offense`
- [ ] Verdict box formatted with weighted scoring grid
- [ ] All post-improvement scores >= 4.0/5
- [ ] CROSS_RULE_{log_source}.md present
- [ ] No enrichment fields in AND conditions in improved rule
