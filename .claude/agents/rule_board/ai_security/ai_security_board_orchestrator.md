# /ai-security-board — AI Security Rule Quality Board Orchestrator (Ultra-Deep)

Runs the full AI Security Rule Quality Board on rules in `policies/ai_security/`. Four vendor specialists (Protect AI, Lakera Guard, Microsoft AI Safety, Palo Alto AI-SPM) debate each rule across 4 rounds with mandatory quality gates, then produce improved rules + test fixtures + analyst docs + change summaries.

**Quality standard:** Every rule must exit the pipeline with a projected post-improvement score >= 4.0/5. Groups with rules that cannot reach this threshold escalate to the orchestrator for cross-group re-review.

## Invocation

```
/ai-security-board --all                                     # all rules (3 parallel groups)
/ai-security-board --category aws_bedrock                    # single category
/ai-security-board --category azure_openai
/ai-security-board --category general
/ai-security-board --rule ai_security_rule_bedrock_prompt_injection   # single rule
/ai-security-board --pilot                                   # 3 pilot rules (sequential, format validation)
```

## Output Structure

```
policies/ai_security_reviewed/
  aws_bedrock/
    {rule_id}.json             <- improved rule (do NOT modify originals)
  azure_openai/
    {rule_id}.json
  general/
    {rule_id}.json
  tests/
    {rule_id}_tests.json       <- TP (>=8) + TN (>=8) + evasion (>=5) test fixtures
  docs/
    {rule_id}.md               <- analyst help page (13 sections)
  changes/
    {rule_id}_changes.md       <- full R0->R1->R2->R3 debate record (8+ sections)
    CROSS_RULE_{group}.md      <- cross-rule consistency per group
  REVIEW_SUMMARY.md            <- cross-category findings + systemic issues
  OPPORTUNITY_REPORT.md        <- ranked improvement opportunities + companion rule backlog
```

---

## Step 0 — Discovery and Batching

```bash
cd /Users/kishoremoli/development/dlp-composer

# Find all individual ai_security_rule_*.json files (exclude rulesets and shared)
find policies/ai_security -name "ai_security_rule_*.json" \
  | grep -v "ruleset" \
  | sort > /tmp/ai_security_board_all_rules.txt

TOTAL=$(wc -l < /tmp/ai_security_board_all_rules.txt | tr -d ' ')
echo "Total AI Security rules to review: $TOTAL"

# Ensure output directories exist
mkdir -p policies/ai_security_reviewed/{aws_bedrock,azure_openai,general,tests,docs,changes,research_cache}
```

---

## Step 0.5 — Pre-flight Research Phase (run BEFORE group agents)

**Purpose:** R0 vendor research is technique-scoped, not rule-scoped. All 4 specialists'
research findings for "prompt injection" are identical whether the rule targets Bedrock or
Azure OpenAI. Running R0 once per technique family and caching it eliminates the biggest
time bottleneck (~48 min per sequential run becomes ~10-15 min parallel, then free for all rules).

Read the technique taxonomy to understand the 8 families and which rules map to each:
`.claude/agents/rule_board/ai_security/technique_taxonomy.md`

### Check cache first

```bash
ls policies/ai_security_reviewed/research_cache/ 2>/dev/null | grep "_research.md" | wc -l
```

If all 8 cache files already exist → **skip this step entirely**, proceed to Step 1.
If any are missing → spawn research agents for the missing families only.

### Spawn research agents in PARALLEL (one per missing technique family)

Spawn all missing family agents simultaneously. Each agent produces one cache file.

```
Research agent prompt template (per family):
"You are the AI Security R0 Research Agent for technique family: {TECH_ID} — {FAMILY_NAME}

Read all 4 specialist agent files in full:
  .claude/agents/rule_board/ai_security/protect_ai_specialist.md
  .claude/agents/rule_board/ai_security/lakera_guard_specialist.md
  .claude/agents/rule_board/ai_security/microsoft_ai_safety_specialist.md
  .claude/agents/rule_board/ai_security/palo_alto_ai_spm_specialist.md

Read the technique taxonomy for context on this family:
  .claude/agents/rule_board/ai_security/technique_taxonomy.md

Your job: execute the full R0 research protocol from each specialist's agent file
for this technique family. Produce a single cache file containing all 4 specialists'
complete R0 research blocks.

Technique family: {TECH_ID}
OWASP LLM: {OWASP_CATEGORY}
MITRE ATLAS: {ATLAS_TECHNIQUE}
Threat summary: {THREAT_SUMMARY from taxonomy}

Output file: policies/ai_security_reviewed/research_cache/{TECH_ID}_research.md

Format the cache file as:

# R0 Research Cache — {TECH_ID}: {FAMILY_NAME}
Generated: {date}
Technique family: {TECH_ID}
OWASP LLM: {OWASP_CATEGORY}
MITRE ATLAS: {ATLAS_TECHNIQUE}
Rules covered: {list of rule_ids in this family}

---

## [PROTECT AI] R0 Research
[PROTECT AI RESEARCH]
[Full R0 block — all questions from protect_ai_specialist.md, fully answered for this technique]

=== PRELIMINARY VERDICT ===
Estimated score contribution: N/5
Hard blockers likely for rules in this family: [list or NONE]
Guardrail dependency score typical for this family: N/5
Shadow AI coverage: YES / NO / PARTIAL

---

## [LAKERA] R0 Research
[LAKERA RESEARCH]
[Full R0 block — all questions from lakera_guard_specialist.md, fully answered]

=== BYPASS PREVIEW (applies to all rules in this family) ===
Bypass 1 (trivial): [describe]
Bypass 2 (intermediate): [describe]
Bypass 3 (advanced): [describe]
Gandalf level: Level N

---

## [MICROSOFT] R0 Research
[MICROSOFT RESEARCH]
[Full R0 block — all questions from microsoft_ai_safety_specialist.md, fully answered]

=== FIVE-QUESTIONS BASELINE (for rules in this family) ===
WHO: N/1 — [what field needed]
FROM WHERE: N/1 — [what field needed]
AGAINST WHAT: N/1 — [what field needed]
HOW RISKY: N/1 — [what signal available]
WHAT BEFORE: N/1 — [what correlation possible]

---

## [PALO ALTO AI-SPM] R0 Research
[PALO ALTO AI-SPM RESEARCH]
[Full R0 block — all questions from palo_alto_ai_spm_specialist.md, fully answered]

=== AI RISK SCORE BASELINE (typical for this family) ===
Component scores:
  Internet exposure: +N (typical)
  Guardrail disabled: +N (typical)
  Sensitive data access: +N (typical)
  Human identity: +N (typical)
  High-value asset: +N (typical)
Baseline AI Risk Score range: N-N/100

---

## Provider-Specific Notes
(These supplement the cache during R1 for individual rules)

### AWS Bedrock variant:
[Fields, event names, guardrail API specifics for Bedrock rules in this family]

### Azure OpenAI variant:
[Fields, event names, Prompt Shields specifics for Azure rules in this family]

### General/cross-provider variant:
[Event type, network fields, sensor requirements for general rules in this family]

Write completion marker: /tmp/ai_security_research_{TECH_ID}.done"
```

### Technique family assignments for parallel spawn

| Agent # | TECH_ID | Family Name | OWASP | Rules |
|---------|---------|-------------|-------|-------|
| 1 | TECH_01_prompt_injection | Prompt Injection / Jailbreak | LLM01.1+01.2 | bedrock_prompt_injection, aoai_jailbreak_attempt, bedrock_guardrail_bypass, aoai_content_filter_bypass |
| 2 | TECH_02_sensitive_data_ai | Sensitive Data in AI | LLM06 | bedrock_sensitive_content, aoai_pii_in_prompt, rag_data_exfil |
| 3 | TECH_03_shadow_ai | Shadow AI / Unauthorized Service | LLM06+LLM05 | shadow_ai_usage, ollama_external_access |
| 4 | TECH_04_model_theft | Model Theft / Extraction | LLM10 | bedrock_model_copy |
| 5 | TECH_05_supply_chain | Supply Chain / Training Data Poisoning | LLM05+LLM03 | bedrock_data_source_modified, model_poisoning, bedrock_model_customization |
| 6 | TECH_06_resource_abuse | Resource Abuse / Model DoS | LLM04 | bedrock_excessive_invocations, aoai_excessive_token_usage |
| 7 | TECH_07_infra_tampering | AI Infrastructure Tampering | LLM07 | bedrock_agent_modified, aoai_deployment_modified |
| 8 | TECH_08_credential_exposure | AI Credential Exposure | LLM06 | llm_api_key_exposure |

### Verify all research agents completed

```bash
for tech in TECH_01_prompt_injection TECH_02_sensitive_data_ai TECH_03_shadow_ai \
            TECH_04_model_theft TECH_05_supply_chain TECH_06_resource_abuse \
            TECH_07_infra_tampering TECH_08_credential_exposure; do
  test -f /tmp/ai_security_research_${tech}.done \
    && echo "DONE: $tech" \
    || echo "MISSING: $tech"
done

# Verify all 8 cache files written
ls policies/ai_security_reviewed/research_cache/*_research.md | wc -l
# Expected: 8
```

Only proceed to Step 1 after all 8 cache files exist.

---

## Step 1 — Assign Rules to 3 Groups

| Group | Category | Rules |
|-------|----------|-------|
| **Group 1** | `aws_bedrock` | ai_security_rule_bedrock_* |
| **Group 2** | `azure_openai` | ai_security_rule_aoai_* |
| **Group 3** | `general` | ai_security_rule_shadow_*, ai_security_rule_llm_*, ai_security_rule_model_*, ai_security_rule_rag_*, ai_security_rule_ollama_* |

---

## Step 2 — Spawn 3 Group Agents in PARALLEL

Spawn all 3 simultaneously. Each runs the full debate pipeline on its assigned rules.

```
Agent prompt template (per group):
"You are running the AI Security Rule Quality Board for Group {N} ({CATEGORY}).

Read the board agent definition:
  .claude/agents/rule_board/ai_security/ai_security_board_group_agent.md

And all 4 specialist files:
  .claude/agents/rule_board/ai_security/protect_ai_specialist.md
  .claude/agents/rule_board/ai_security/lakera_guard_specialist.md
  .claude/agents/rule_board/ai_security/microsoft_ai_safety_specialist.md
  .claude/agents/rule_board/ai_security/palo_alto_ai_spm_specialist.md

Your assigned rules:
  {LIST OF RULE FILES}

QUALITY REQUIREMENTS (non-negotiable):
1. Every rule must exit with projected post-improvement score >= 4.0/5
2. All 4 quality gates between rounds MUST be passed before advancing
3. Lakera MUST demonstrate >= 2 concrete bypasses per rule before issuing verdict
4. Round 2 MUST have >= 8 challenge pairs with genuine tension
5. REWORK-MAJOR rules MUST have condition tree redesigned (not just annotated)
6. Test fixtures MUST meet: >= 8 TP + >= 8 TN + >= 5 evasion cases per rule
7. All identity/enrichment fields MUST be in enrichment_fields, NOT in AND conditions
8. Companion rules for P1 gaps MUST be authored (full spec), NOT just referenced

Process each rule with the full R0->R1->R2->R3 pipeline.
Output improved rules to policies/ai_security_reviewed/{category}/.
Output change summaries to policies/ai_security_reviewed/changes/.
Output test fixtures to policies/ai_security_reviewed/tests/.
Output analyst docs to policies/ai_security_reviewed/docs/.
Do NOT modify originals in policies/ai_security/.
After all rules: write CROSS_RULE_group{N}.md to policies/ai_security_reviewed/changes/.
Write completion marker to /tmp/ai_security_board_group{N}.done
Write score summary to /tmp/ai_security_board_group{N}_scores.json (see format below)"
```

Score summary format (written by each group agent to /tmp):
```json
{
  "group": N,
  "rules": [
    {
      "rule_id": "...",
      "verdict": "REWORK-MAJOR | REWORK-MINOR | APPROVED",
      "score_pre": N.N,
      "score_post": N.N,
      "hard_blockers": ["..."],
      "companion_rules_authored": N,
      "companion_rules_referenced_only": N,
      "test_tp_count": N,
      "test_tn_count": N,
      "test_evasion_count": N
    }
  ]
}
```

**Verify each group completes with quality:**
```bash
test -f /tmp/ai_security_board_group1.done || echo "BLOCKED: Group 1 not complete"
test -f /tmp/ai_security_board_group2.done || echo "BLOCKED: Group 2 not complete"
test -f /tmp/ai_security_board_group3.done || echo "BLOCKED: Group 3 not complete"

# Check score thresholds
python3 -c "
import json, sys
issues = []
for g in [1,2,3]:
    try:
        scores = json.load(open(f'/tmp/ai_security_board_group{g}_scores.json'))
        for r in scores['rules']:
            if r['score_post'] < 4.0:
                issues.append(f\"Group {g} / {r['rule_id']}: post-improvement score {r['score_post']}/5 < 4.0\")
            if r['test_tp_count'] < 8:
                issues.append(f\"Group {g} / {r['rule_id']}: only {r['test_tp_count']} TP (need >= 8)\")
            if r['test_evasion_count'] < 5:
                issues.append(f\"Group {g} / {r['rule_id']}: only {r['test_evasion_count']} evasion (need >= 5)\")
    except: issues.append(f'Group {g}: score file missing')
if issues:
    print('QUALITY GATE FAILURES:')
    for i in issues: print(f'  - {i}')
    sys.exit(1)
else:
    print('All quality gates passed')
"
```

If quality gate fails: spawn re-review agent for the specific failing rules with escalation prompt (see Step 2b).

---

## Step 2b — Quality Gate Failure Escalation

If any rule fails the post-improvement score gate (< 4.0/5), spawn a targeted re-review:

```
Agent prompt:
"You are re-reviewing AI Security rule {rule_id} which exited the board pipeline at {score_post}/5.
This is below the required 4.0/5 threshold.

Read the existing improved rule: policies/ai_security_reviewed/{category}/{rule_id}.json
Read the existing change summary: policies/ai_security_reviewed/changes/{rule_id}_changes.md

Identify why the projected score could not reach 4.0/5:
1. Are there structural gaps that no improvement can address with this rule architecture?
   If YES: recommend SPLIT-NEEDED or WRONG-LAYER and document why
2. Are there improvements that were not applied due to specialist disagreements?
   Re-evaluate each rejected proposal from section 8 of the change summary.
3. Are companion rules missing that would have satisfied P1 gaps?
   If so, author them now.

Output:
- Updated improved rule (increment version again, note escalation re-review)
- Updated change summary with escalation section appended
- Updated CROSS_RULE file noting the re-review outcome
- Write updated score to /tmp/ai_security_board_group{N}_scores.json"
```

---

## Step 3 — Consolidation

After all 3 groups complete and pass quality gate, spawn the consolidator agent:

```
Agent prompt:
"You are the AI Security Rule Board Consolidator.

Read all per-rule change summaries in: policies/ai_security_reviewed/changes/
Read all improved rules in: policies/ai_security_reviewed/{category}/
Read all cross-rule consistency files: policies/ai_security_reviewed/changes/CROSS_RULE_*.md
Read all group score summaries in: /tmp/ai_security_board_group*_scores.json

Produce:

1. policies/ai_security_reviewed/REVIEW_SUMMARY.md

Format:
## Executive Summary
[5 bullet points: total rules, verdict distribution, key systemic issues found, top 3 improvements applied, companion rule backlog size]

## Verdict Distribution
| Verdict | Count | Rules |
|---------|-------|-------|
| APPROVED | N | [...] |
| REWORK-MINOR | N | [...] |
| REWORK-MAJOR | N | [...] |
| WRONG-LAYER | N | [...] |
| SPLIT-NEEDED | N | [...] |

## Score Distribution
| Score Range | Pre-improvement | Post-improvement |
|-------------|----------------|-----------------|
| 4.0-5.0 | N | N |
| 3.5-4.0 | N | N |
| < 3.5 | N | N |

## OWASP LLM Top 10 Coverage Heatmap
| Category | Sub-category | Coverage Status | Rules | Gaps |
|----------|-------------|-----------------|-------|------|
| LLM01 | 01.1 direct | COVERED / PARTIAL / GAP | [...] | [...] |
| LLM01 | 01.2 indirect/RAG | COVERED / PARTIAL / GAP | [...] | [...] |
... (all 10 categories, all sub-categories)

## Provider Coverage
| Provider | Rules | APPROVED | REWORK | Gap Notes |
|----------|-------|---------|--------|-----------|
| AWS Bedrock | N | N | N | ... |
| Azure OpenAI | N | N | N | ... |
| General/cross-provider | N | N | N | ... |
| GCP Vertex AI | 0 — GAP | — | — | ... |
| Self-hosted (Ollama/vLLM) | 0 — GAP | — | — | ... |

## Top Systemic Issues (across all groups)
| Issue | Rules Affected | Root Cause | Fix Applied | Remaining |
|-------|---------------|-----------|-------------|-----------|
| ... | N | ... | YES/NO | ... |

## Quality Metrics
| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Rules at >= 4.0/5 post-improvement | N% | 100% | PASS/FAIL |
| Avg post-improvement score | N.N/5 | >= 4.0/5 | PASS/FAIL |
| Rules with >= 8 TP test cases | N% | 100% | PASS/FAIL |
| Rules with >= 5 evasion test cases | N% | 100% | PASS/FAIL |
| P1 companion rules authored | N | all | PASS/FAIL |

## Recommended Follow-up Waves
[What rule categories or techniques should be addressed in Wave 2]


2. policies/ai_security_reviewed/OPPORTUNITY_REPORT.md

Format:
## New Rules Needed (not in current corpus)
| Priority | Technique | OWASP Sub-category | MITRE ATLAS | Rationale | Suggested Rule ID |
|----------|-----------|-------------------|-------------|-----------|------------------|
| P1 | ... | LLM01.2 | AML.T0051 | ... | ai_security_rule_... |

## Companion Rules Authored (in this pipeline run)
| Rule ID | Type | Addresses Gap In | Status |
|---------|------|-----------------|--------|
| ... | cspm_rule | ... | authored |

## Companion Rules Referenced But NOT Authored (deferred)
| Rule ID | Type | Addresses Gap In | Priority | Target Wave |
|---------|------|-----------------|----------|-------------|
| ... | sequence_rule | ... | P1 | Wave 2 |

## Cross-Provider Coverage Gaps
| Technique | Covered For | Missing For | New Rule Required |
|-----------|-------------|-------------|-------------------|
| Prompt injection | AWS Bedrock, Azure OpenAI | GCP Vertex AI | ai_security_rule_vertex_prompt_injection |

## OWASP LLM Top 10 Coverage Gaps
| Category | Sub-category | Gap Description | Priority | Target Wave |
|----------|-------------|-----------------|----------|-------------|
| LLM02 | Output handling | No output monitoring rule | P1 | Wave 2 |
| LLM08 | Excessive agency | No agentic action monitoring | P1 | Wave 2 |"
```

---

## Step 4 — Final Quality Validation

Before reporting completion, validate all outputs:

```bash
# Count output files vs expected
RULES=$(wc -l < /tmp/ai_security_board_all_rules.txt | tr -d ' ')
IMPROVED=$(find policies/ai_security_reviewed -name "*.json" ! -name "*_tests.json" | grep -v REVIEW | wc -l | tr -d ' ')
TESTS=$(find policies/ai_security_reviewed/tests -name "*_tests.json" | wc -l | tr -d ' ')
DOCS=$(find policies/ai_security_reviewed/docs -name "*.md" | wc -l | tr -d ' ')
CHANGES=$(find policies/ai_security_reviewed/changes -name "*_changes.md" | wc -l | tr -d ' ')

echo "Expected: $RULES rules"
echo "Improved rules: $IMPROVED (expected $RULES)"
echo "Test fixtures: $TESTS (expected $RULES)"
echo "Analyst docs: $DOCS (expected $RULES)"
echo "Change summaries: $CHANGES (expected $RULES)"

[ "$IMPROVED" = "$RULES" ] && [ "$TESTS" = "$RULES" ] && [ "$DOCS" = "$RULES" ] && [ "$CHANGES" = "$RULES" ] \
  && echo "FILE COUNT: PASS" || echo "FILE COUNT: FAIL — missing output files"

# Verify summary files exist
test -f policies/ai_security_reviewed/REVIEW_SUMMARY.md && echo "REVIEW_SUMMARY: PASS" || echo "REVIEW_SUMMARY: MISSING"
test -f policies/ai_security_reviewed/OPPORTUNITY_REPORT.md && echo "OPPORTUNITY_REPORT: PASS" || echo "OPPORTUNITY_REPORT: MISSING"
```

---

## Step 5 — Final Report

```
AI Security Rule Quality Board Complete
=================================================================
Rules reviewed:      N
  APPROVED:          N  (score >= 4.0/5 pre-improvement)
  REWORK-MINOR:      N  (score 3.5-4.0/5, targeted fixes applied)
  REWORK-MAJOR:      N  (score < 3.5/5, condition tree redesigned)
  WRONG-LAYER:       N  (belongs in SIEM/DLP/network, not ai_service sensor)
  SPLIT-NEEDED:      N  (one rule split into multiple targeted rules)

Score improvement:
  Average pre-improvement:  N.N/5
  Average post-improvement: N.N/5
  Rules reaching >= 4.0/5:  N/N (N%)

Test coverage:
  Total TP test cases:      N (avg N per rule)
  Total TN test cases:      N (avg N per rule)
  Total evasion cases:      N (avg N per rule)

OWASP LLM Top 10 coverage: N/10 categories (N/20 sub-categories) with active detections
Provider coverage: AWS Bedrock: N | Azure OpenAI: N | General/cross: N
Companion rules authored: N | Referenced only (deferred): N

Hard blockers found and fixed:
  Wrong event_type: N rules
  Enrichment fields in AND conditions: N rules
  Single-branch guardrail-only: N rules

Full summary:        policies/ai_security_reviewed/REVIEW_SUMMARY.md
Opportunity report:  policies/ai_security_reviewed/OPPORTUNITY_REPORT.md
=================================================================
```

---

## Board Evaluation Dimensions (all 4 specialists score these)

Every AI Security rule is evaluated on 7 weighted dimensions:

| Dimension | Weight | What It Measures |
|-----------|--------|-----------------|
| **Detection Completeness** | 2x | Coverage of 5 AI attack lifecycle phases |
| **Guardrail Independence** | 2x | Zero-detection risk when guardrail is disabled |
| **Evasion Resistance** | 1.5x | Minimum attacker effort to bypass (Gandalf Level) |
| **Coverage** | 1.5x | Variants, indirect injection, multi-turn coverage |
| **Provider Fit** | 1x | Single-provider dependency vs. cross-platform |
| **Response Calibration** | 1x | Actions proportionate to blast radius |
| **FP Risk** | 1x | Alert volume at enterprise scale |

Score = (weighted_sum / 50) * 5 = N.N/5

## Hard Blockers — any of these = immediate REWORK-MAJOR

1. Rule fires only on vendor guardrail event with no fallback when guardrail is disabled
2. Rule's regex/keyword on prompt text bypassable by paraphrasing (trivial bypass < 30 seconds)
3. Identity/enrichment field (`ai.request.user`, `user.id`, etc.) placed in AND condition tree (gates detection)
4. Wrong `event_type` for the telemetry being targeted (e.g., shadow AI rule using LLMAuditLog)
5. Rule covers only 1 cloud provider for a multi-provider threat with no companion
6. CRITICAL severity with `create_ticket` only response, no containment path
7. OWASP LLM Top 10 not mapped (even just the top-level category)
8. No indirect injection coverage documented (even as acknowledged gap with companion)
9. Shadow AI coverage absent with no companion discovery rule referenced

---

## Pilot Mode (format validation before full run)

```
/ai-security-board --pilot
```

Runs on 3 rules sequentially (not parallel) to validate output format:
- `ai_security_rule_bedrock_prompt_injection`
- `ai_security_rule_aoai_jailbreak_attempt`
- `ai_security_rule_shadow_ai_usage`

After pilot: validate against reference format at `policies/edr_reviewed/changes/edr_rule_linux_credential_dumping_changes.md`

Pilot acceptance criteria (ALL must pass before running --all):
- [ ] All 4 output files present per rule (12 files total)
- [ ] Change summary has all 8 sections (R0, R1, R2, R3, Verdict, Changes, Rejected, Gaps)
- [ ] Help page has all 13 sections
- [ ] Test fixtures meet >= 8 TP + >= 8 TN + >= 5 evasion
- [ ] OWASP sub-category mapped in all rules (LLM0N.N, not just LLM0N)
- [ ] Verdict box formatted correctly with weighted scoring
- [ ] All post-improvement scores >= 4.0/5
- [ ] At least 1 REWORK-MAJOR with genuine condition tree redesign (not just annotations)
- [ ] No enrichment fields in AND conditions in any improved rule
- [ ] All hard blockers checked with YES/NO result in change summaries
