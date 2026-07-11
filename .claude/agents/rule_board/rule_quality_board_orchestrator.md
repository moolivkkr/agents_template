# /rule-board — EDR Rule Quality Board Orchestrator

A 9-specialist debate pipeline that reviews every EDR rule for signal quality, FP risk, channel
correctness, evasion resistance, and completeness. Six vendor specialists + schema validator +
SOC analyst + moderator evaluate each rule through quality-gated rounds, then produce improved
rules with weighted scoring, test fixtures, and analyst documentation.

**Quality standard:** Every rule must exit with projected post-improvement score >= 4.0/5.

**Specialists (9):**
- 6 vendor parity: Falcon, Cortex XDR, Singularity, Elastic, Defender for Endpoint, Carbon Black (sonnet)
- Schema Validator: DEFECT-1 through DEFECT-15 checklist (sonnet)
- SOC Analyst: alert fatigue, triage speed, response safety (sonnet)
- Moderator: consensus resolution, gap analysis, final verdict (**sonnet** — inline in group agent)

**New rule authoring:** to create NEW rules (not review existing ones), use
`.claude/agents/rule_board/edr_rule_author.md` — the schema-valid rule generator that
authors from a MITRE technique and pre-hardens against DEFECT-CAT-1..9.

**Standards:** `.claude/agents/rule_board/EDR_RULE_AUTHORING_STANDARDS.md`

## Model Assignment

| Step | Agent | Model | Reason |
|------|-------|-------|--------|
| Step 0 | Discovery / batching | **orchestrator/parent** | Shell only — no LLM agent spawned |
| Step 0.5 | Vendor cache verification | **orchestrator/parent** | Shell only — no LLM agent spawned |
| Step 1 | Group assignment | **orchestrator/parent** | Deterministic split — no LLM agent spawned |
| Step 2 | Group agents (R0–R3 debate) | **sonnet** | Structured format; all 7 specialists run inline |
| Step 2b | Logic validation | **sonnet** | Runs inline inside group agents — same model |
| Step 3 | Consolidation | **sonnet** | Aggregating change docs, not making quality calls |
| Step 4 | Final report | **orchestrator/parent** | Formatting only — no quality gate agent spawned |
| `--rule` single rule | Full deep review | **opus** | Scoped to one rule; quality matters more than cost |

The `{{model}}` argument controls Step 2 group agents only. Default: **sonnet**.
**Do NOT use opus for group agents** — structured debate format does not benefit from it.

## Invocation

```
/rule-board --all                              # process all rules (4 parallel groups)
/rule-board --tactic defense_evasion           # single tactic
/rule-board --technique T1003                  # all rules for a MITRE technique
/rule-board --rule edr_rule_process_injection  # single rule (full deep debate)
```

## Output

All output goes to `policies/edr/` (the unified corpus — NOT edr_reviewed/):

```
policies/edr/
  {tactic}/
    {rule_id}.json             ← improved rule (in-place update)
  tests/
    {rule_id}_tests.json       ← test fixtures (true pos + true neg + evasion blind spots)
  docs/
    {rule_id}.md               ← rule help page (analyst/engineer reference)
  changes/
    {rule_id}_changes.md       ← what changed, why, what was rejected
    CROSS_RULE_{group}.md      ← cross-rule consistency findings per group
  REVIEW_SUMMARY.md            ← cross-tactic patterns + systemic issues
  OPPORTUNITY_REPORT.md        ← ranked improvement opportunities
```

---

## Step 0 — Discovery and Batching `[MODEL: orchestrator/parent]`

```bash
# Find all individual edr_rule_*.json files (exclude rulesets and sequence rules)
find policies/edr -name "edr_rule_*.json" \
  -not -path "*/tests/*" -not -path "*/changes/*" -not -path "*/docs/*" \
  -not -path "*/shared/*" -not -path "*/research_cache/*" \
  -not -path "*/edr_legacy/*" \
  | grep -v "edr_ruleset" \
  | sort > /tmp/rule_board_all_rules.txt

TOTAL=$(wc -l < /tmp/rule_board_all_rules.txt | tr -d ' ')
echo "Total rules to review: $TOTAL"

# Ensure output directories exist
mkdir -p policies/edr/{changes,tests,docs}
```

## Step 0.5 — Vendor Cache Verification (REQUIRED) `[MODEL: orchestrator/parent]`

The board MUST use locally cached vendor rules — NOT web searches or training knowledge.

```bash
# Verify vendor caches exist
ELASTIC_CACHE="agent_state/siem_pipeline/stage_0/cache/elastic-detection-rules"
SIGMA_CACHE="agent_state/siem_pipeline/stage_0/cache/sigma"

ELASTIC_COUNT=$(find "$ELASTIC_CACHE" -name "*.toml" 2>/dev/null | wc -l | tr -d ' ')
SIGMA_COUNT=$(find "$SIGMA_CACHE" -name "*.yml" 2>/dev/null | wc -l | tr -d ' ')
RESEARCH_COUNT=$(ls policies/edr/research_cache/ 2>/dev/null | wc -l | tr -d ' ')

echo "Elastic rules cached: $ELASTIC_COUNT"
echo "Sigma rules cached:   $SIGMA_COUNT"
echo "Research cache:       $RESEARCH_COUNT technique files"

if [ "$ELASTIC_COUNT" -lt 100 ] || [ "$SIGMA_COUNT" -lt 100 ]; then
  echo "BLOCKED: Vendor cache incomplete. Run Stage 0 download first."
  exit 1
fi
```

**Round 0 vendor research protocol:**
- For each MITRE technique, grep the LOCAL caches — do NOT web search:
  ```bash
  # Find Elastic rules for T1003
  grep -rl "T1003" agent_state/siem_pipeline/stage_0/cache/elastic-detection-rules/rules/
  # Find Sigma rules for T1003
  grep -rl "T1003" agent_state/siem_pipeline/stage_0/cache/sigma/rules/
  ```
- Read the matching vendor rule files to extract: rule type, conditions, fields, severity, FP notes
- Check `policies/edr/research_cache/{technique_id}_research.md` for pre-compiled research
- Cache new research to `policies/edr/research_cache/` for reuse across rules

## Step 1 — Assign Rules to 4 Groups `[MODEL: orchestrator/parent]`

Split by tactic folder for coherent specialist context within each group:

| Group | Tactics |
|-------|---------|
| **Group 1** | `defense_evasion`, `execution` |
| **Group 2** | `persistence`, `privilege_escalation` |
| **Group 3** | `credential_access`, `discovery`, `collection`, `lateral_movement` |
| **Group 4** | `initial_access`, `impact`, `exfiltration`, `command_and_control`, `cloud_workload`, `identity_and_ad`, `ransomware`, `lolbins`, `fileless_in_memory`, `endpoint_tampering`, `supply_chain`, `insider_threat` |

## Step 2 — Spawn 4 Group Agents in PARALLEL `[MODEL: sonnet]`

Spawn all 4 simultaneously using **sonnet** model. Each runs the full review pipeline.

```
Agent prompt (per group):
"You are running the EDR Rule Quality Board for {GROUP_TACTICS}.

Read these files FIRST:
  .claude/agents/rule_board/rule_board_group_agent.md  (v3 — main pipeline)
  .claude/agents/rule_board/EDR_RULE_AUTHORING_STANDARDS.md  (systemic defect catalog)

Specialist files (reference during evaluation):
  .claude/agents/rule_board/cs_falcon_specialist.md
  .claude/agents/rule_board/cortex_xdr_specialist.md
  .claude/agents/rule_board/singularity_specialist.md
  .claude/agents/rule_board/elastic_security_specialist.md
  .claude/agents/rule_board/defender_specialist.md       (Microsoft Defender for Endpoint)
  .claude/agents/rule_board/carbon_black_specialist.md    (VMware Carbon Black Cloud)
  .claude/agents/rule_board/edr_schema_validator.md     (NEW — DEFECT checklist)
  .claude/agents/rule_board/edr_soc_analyst.md           (NEW — alert fatigue)
  .claude/agents/rule_board/rule_board_moderator.md

Your assigned tactics: {TACTIC_LIST}
Rules: find all edr_rule_*.json in policies/edr/{tactic}/.
Modify rules IN PLACE. Write changes/tests/docs to policies/edr/.

VENDOR CACHE (LOCAL ONLY — no web search):
  Elastic: agent_state/siem_pipeline/stage_0/cache/elastic-detection-rules/rules/
  Sigma: agent_state/siem_pipeline/stage_0/cache/sigma/rules/
  Research: policies/edr/research_cache/

QUALITY GATES (MANDATORY):
  Gate 0→1: VALIDATOR DEFECT checklist + SOC ANALYST FP estimate done before R1
  Gate 1→2: All 7 dimensions scored, weighted total computed
  Gate 2→OUT: Post-improvement score ≥ 4.0/5, logic validator clean

TEST MINIMUMS: ≥5 TP + ≥5 TN + ≥3 evasion per rule

SCORE OUTPUT: Write GROUP{N}_scores.json with pre/post scores per rule"
```

## Step 2b — Logic Validation (MANDATORY after every rule fix) `[MODEL: sonnet]`

Every group agent MUST run this validation after modifying a rule:

```python
# Logic validator — catches impossible conditions, broken regex, contradictions
import json, re

def validate_rule(path):
    d = json.load(open(path))
    errors = []

    # 1. Valid JSON (already passed if we're here)

    # 2. Check for contradictory conditions (AND of mutually exclusive values)
    for block in ('behavioral', 'threshold'):
        b = d.get(block, {})
        if not isinstance(b, dict): continue
        cond = b.get('condition', {})
        if not isinstance(cond, dict): continue
        conditions = cond.get('conditions', [])
        if cond.get('logic') == 'AND':
            # Check for same field with contradictory operators
            field_ops = {}
            for c in conditions:
                if not isinstance(c, dict): continue
                field = c.get('field', '')
                op = c.get('operator', '')
                val = c.get('value', '')
                if field and op:
                    key = f"{field}:{op}"
                    if key in field_ops and field_ops[key] != str(val):
                        # Same field, same operator, different values in AND = suspicious
                        pass  # Could be valid (e.g., not_in with different values)
                    # Check starts_with + not starts_with on same field = possible impossibility
                    if f"{field}:starts_with" in field_ops and op == 'not_starts_with':
                        errors.append(f"Possible contradiction: {field} starts_with AND not_starts_with")
                    field_ops[key] = str(val)

    # 3. Validate regex patterns compile
    def check_regex(obj, path_prefix=""):
        if isinstance(obj, dict):
            op = obj.get('operator', '')
            val = obj.get('value', '')
            if op in ('regex', 'matches', 'not_regex', 'not_matches') and isinstance(val, str):
                try:
                    re.compile(val)
                except re.error as e:
                    errors.append(f"Broken regex at {path_prefix}: {val} — {e}")
            for k, v in obj.items():
                check_regex(v, f"{path_prefix}.{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                check_regex(v, f"{path_prefix}[{i}]")
    check_regex(d)

    # 4. Check response mode vs actions consistency
    resp = d.get('response', {})
    if isinstance(resp, dict):
        mode = resp.get('mode', '')
        actions = resp.get('actions', [])
        if mode == 'prevent' and 'kill_process' not in actions and 'quarantine_file' not in actions:
            errors.append("mode=prevent but no kill_process or quarantine_file action")
        if mode == 'detect' and ('isolate_host' in actions or 'kill_process' in actions):
            errors.append(f"mode=detect but has {[a for a in actions if a in ('isolate_host','kill_process')]}")

    # 5. Check severity exists and is valid
    sev = d.get('severity', '')
    if sev not in ('critical', 'high', 'medium', 'low', 'informational'):
        errors.append(f"Invalid severity: {sev}")

    return errors
```

## Step 2c — Quality Gate Verification (after all groups complete)

```python
import json, os

issues = []
for g in range(1, 5):
    score_file = f'policies/edr/changes/GROUP{g}_scores.json'
    if not os.path.exists(score_file):
        issues.append(f'Group {g}: score file missing')
        continue
    scores = json.load(open(score_file))
    for r in scores.get('rules', []):
        if r.get('score_post', 0) < 4.0:
            issues.append(f"Group {g} / {r['rule_id']}: post {r['score_post']}/5 < 4.0")
        if r.get('test_tp_count', 0) < 5:
            issues.append(f"Group {g} / {r['rule_id']}: only {r.get('test_tp_count')} TP (need ≥5)")
        if r.get('test_evasion_count', 0) < 3:
            issues.append(f"Group {g} / {r['rule_id']}: only {r.get('test_evasion_count')} evasion (need ≥3)")

if issues:
    print('QUALITY GATE FAILURES:')
    for i in issues: print(f'  - {i}')
    # Spawn targeted re-review for failed rules
else:
    print('All quality gates passed')
```

## Step 3 — Consolidation `[MODEL: sonnet]`

After all 4 groups complete AND quality gate passes, spawn the consolidator:

```
Agent prompt:
"You are the Rule Board Consolidator.
Read .claude/agents/rule_board/rule_board_consolidator.md and execute it.
All per-rule change summaries are in policies/edr/changes/*.md.
All improved rules are in policies/edr/{tactic}/*.json.
Produce policies/edr/REVIEW_SUMMARY.md and policies/edr/OPPORTUNITY_REPORT.md."
```

## Step 4 — Final Report `[MODEL: orchestrator/parent]`

```
Rule Quality Board Complete
═══════════════════════════════════════════════════════
Rules reviewed:      N
  APPROVED:          N  (no changes needed)
  REWORK-MINOR:      N  (condition tuning, FP reduction)
  REWORK-MAJOR:      N  (significant redesign)
  WRONG-LAYER:       N  (move to SIEM/DLP/network)
  SPLIT-NEEDED:      N  (one rule → multiple targeted rules)

Logic validation:    N rules validated, N errors found
Test case coverage:  N rules with test files

Top systemic issues: see OPPORTUNITY_REPORT.md
Full summary:        policies/edr/REVIEW_SUMMARY.md
═══════════════════════════════════════════════════════
```

---

## 7 Evaluation Dimensions

Every rule is evaluated on these 7 dimensions regardless of tactic:

1. **Signal source** — Is this a process event, file event, or something the endpoint agent cannot actually observe?
2. **IoA vs IoC** — Does this detect behavior (hard to evade) or artifact (easy to evade by renaming)?
3. **False positive risk** — What legitimate process or admin activity matches this condition?
4. **Evasion resistance** — What minimal change does an attacker make to bypass this rule?
5. **Channel fit** — endpoint_linux? cloud_workload? Should it be a SIEM rule? DLP?
6. **Completeness** — Does this cover all variants of the technique? What variants are missed?
7. **Response correctness** — Is alert/block/kill calibrated to actual severity and confidence?

## Hard blockers — any of these = WRONG-LAYER or REWORK-MAJOR

- Rule condition references API call logs, CloudTrail events, or auth logs → WRONG-LAYER (SIEM)
- Rule condition references packet payload, HTTP body, or DNS payload → WRONG-LAYER (network/DLP)
- Rule matches only on binary/script name with no behavioral context → REWORK-MAJOR (IoC, evasion-trivial)
- Parent filter is `bash` or `sh` without further specificity → REWORK-MAJOR (too broad)
- Rule has no exclusions for known admin/package-manager activity → REWORK-MAJOR
- Severity is critical but response is alert-only for confirmed-malicious behavior → REWORK-MINOR
- Logic validator finds broken regex or contradictory conditions → REWORK-MAJOR
- Response mode=prevent but no kill/quarantine action → REWORK-MINOR

## Severity Calibration Matrix

Use this matrix to ensure consistent severity across the corpus:

| MITRE Tactic | Typical Severity | Justification |
|---|---|---|
| Initial Access (TA0001) | high-critical | Active intrusion underway |
| Execution (TA0002) | high | Depends on what's executed |
| Persistence (TA0003) | medium-high | Attacker establishing foothold |
| Privilege Escalation (TA0004) | high-critical | Immediate blast radius expansion |
| Defense Evasion (TA0005) | medium-high | Depends on what's being evaded |
| Credential Access (TA0006) | critical | Direct path to lateral movement |
| Discovery (TA0007) | low-medium | Recon only, no direct impact |
| Lateral Movement (TA0008) | high-critical | Active spread |
| Collection (TA0009) | medium-high | Pre-exfiltration |
| Exfiltration (TA0010) | high-critical | Data leaving the network |
| Command & Control (TA0011) | high | Active adversary communication |
| Impact (TA0040) | critical | Destructive/disruptive action |

**Response mode calibration:**

| Confidence | Severity | Response Mode |
|---|---|---|
| Unambiguous malicious (no FP scenario) | critical | prevent (kill_process + isolate_host) |
| High confidence (rare FP) | critical/high | prevent (kill_process) |
| Medium confidence (some FP) | high/medium | detect (alert + create_ticket) |
| Low confidence (common FP) | medium/low | detect (alert only) |
| Informational (hunting) | low | detect (log only) |
