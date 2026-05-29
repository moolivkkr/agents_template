---
command: rules-board
description: "Run the EDR Rule Quality Board — multi-specialist debate pipeline that reviews rules for signal quality, FP risk, evasion resistance, and completeness. Produces improved rules, test cases, change docs."
arguments:
  - name: scope
    required: false
    description: "Scope: --all (all rules), --tactic defense_evasion (single tactic), --technique T1003 (single MITRE technique), --rule edr_rule_amsi_bypass (single rule). Defaults to --all."
  - name: model
    required: false
    default: sonnet
    description: "Model for rule review agents: sonnet (cost-efficient) or opus (highest quality). Orchestrator always uses the parent model."
  - name: batch_size
    required: false
    default: 10
    description: "Number of rules per agent batch. Higher = fewer agent calls but larger context."
  - name: dry_run
    required: false
    default: false
    description: "Review rules but don't write improved versions — report only."
---

# /rules-board — EDR Rule Quality Board

Read `.claude/agents/rule_board/rule_quality_board_orchestrator.md` and execute it.

## Pre-flight

1. Verify the EDR corpus exists and count rules:
```bash
TOTAL=$(find policies/edr -name "edr_rule_*.json" \
  -not -path "*/tests/*" -not -path "*/changes/*" -not -path "*/docs/*" \
  -not -path "*/shared/*" -not -path "*/research_cache/*" -not -path "*/edr_legacy/*" \
  | grep -v "edr_ruleset" | wc -l | tr -d ' ')
echo "Total rules to review: $TOTAL"
```

2. Check Stage 0 vendor cache (Elastic + Sigma) — REQUIRED:
```bash
ELASTIC=$(find agent_state/siem_pipeline/stage_0/cache/elastic-detection-rules -name "*.toml" 2>/dev/null | wc -l | tr -d ' ')
SIGMA=$(find agent_state/siem_pipeline/stage_0/cache/sigma -name "*.yml" 2>/dev/null | wc -l | tr -d ' ')
echo "Vendor cache: Elastic=$ELASTIC Sigma=$SIGMA"

if [ "$ELASTIC" -lt 100 ] || [ "$SIGMA" -lt 100 ]; then
  echo "BLOCKED: Vendor cache incomplete. Run Stage 0 download first."
  exit 1
fi
```

3. Check existing research cache:
```bash
RESEARCH=$(ls policies/edr/research_cache/ 2>/dev/null | wc -l | tr -d ' ')
echo "Research cache: $RESEARCH technique files"
```

## Scope Resolution

Parse the scope argument:
- `--all` or empty: process all rules, split into 4 groups per the orchestrator
- `--tactic {name}`: filter to rules in `policies/edr/{name}/`
- `--technique {T-number}`: filter to rules with matching MITRE technique_id
- `--rule {rule_id}`: single rule deep review

## Model Selection

Use `{{model}}` (default: sonnet) for all group agents. This controls cost:
- `sonnet`: ~75% cheaper, good for structured rule review
- `opus`: highest quality, use for final quality gates or complex rules

## Execution

Follow the orchestrator steps exactly:
- Step 0: Discovery and batching (exclude tests/, changes/, docs/, shared/, research_cache/)
- Step 0.5: Vendor cache verification (BLOCK if cache incomplete)
- Step 1: Assign rules to 4 groups by tactic
- Step 2: Spawn group agents (use {{model}} for agent model)
  - Each agent: vendor research → 7-dimension evaluation → fix → logic validation → test cases
- Step 3: Consolidation (cross-group patterns, opportunity report)
- Step 4: Final report with verdict counts + logic validation summary

## Key Improvements (v2)

1. **Logic validator** — every modified rule runs through regex compilation, contradiction detection, mode/action consistency checks. Catches broken regex, impossible conditions, response mismatches.
2. **Local vendor cache** — agents grep Elastic (2,110 TOML) + Sigma (4,189 YAML) locally. No web searches. No training-knowledge guessing.
3. **Severity calibration matrix** — consistent severity/response across the corpus based on MITRE tactic.
4. **In-place updates** — rules modified directly in policies/edr/ (no separate reviewed folder).
5. **Streamlined group agent** — 7-dimension evaluation with scoring anchors, specialist criteria referenced from specialist files.

## Cost Optimization

- Stage 0 vendor cache: run ONCE, skip on subsequent invocations
- Research cache: per-technique, reuse across rules sharing the same technique
- Batch rules by technique to minimize context switching
- Use `{{model}}` (sonnet by default) for review agents — ~75% cheaper than opus
- Fast-track APPROVED rules (all dimensions ≥ 4) — skip deep review
