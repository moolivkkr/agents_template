---
command: rules-board-edr
description: "Run the EDR Rule Quality Board (dedicated, self-contained) — reviews endpoint behavioral rules for signal quality, FP risk, evasion resistance, coverage, channel fit, and response calibration across 6 vendor lenses + validator + SOC analyst. Produces improved rules, test fixtures, and change docs. Separate entry point from the generic /startup:rules-board."
arguments:
  - name: scope
    required: false
    description: "Scope: --all (all rules), --tactic defense_evasion (single tactic), --technique T1003 (single MITRE technique), --rule edr_rule_amsi_bypass (single rule deep review). Defaults to --all."
  - name: model
    required: false
    default: opus
    description: "Model for review agents: opus (default) or sonnet (about half the cost, for large low-risk batches). Orchestrator uses the parent model."
  - name: batch_size
    required: false
    default: 50
    description: "Rules per agent batch."
---

# /rules-board-edr — EDR Rule Quality Board (dedicated)

Read `.claude/agents/rule_board/edr/edr_rule_quality_board_orchestrator.md` and execute it.

This is the **tailored, self-contained** EDR board — the group agent
(`.claude/agents/rule_board/edr/edr_board_group_agent.md`) inlines all 9 lenses (6 vendor + validator +
SOC analyst + moderator), the DEFECT-1..15 checklist, and the systemic DEFECT-CAT-1..9 screen, so it does
**not** read the standalone specialist `.md` files each run. It is a separate entry point from the generic
multi-plugin `/startup:rules-board`; running it does not affect that command.

**Standards:** `.claude/agents/rule_board/edr/EDR_RULE_AUTHORING_STANDARDS.md`

## Pre-flight

1. Count EDR rules to review (exclude test fixtures + rulesets):
```bash
TOTAL=$(find policies/edr -name "edr_rule_*.json" \
  -not -path "*/tests/*" -not -path "*/changes/*" -not -path "*/docs/*" \
  -not -path "*/shared/*" -not -path "*/research_cache/*" -not -path "*/edr_legacy/*" \
  | grep -v "edr_ruleset" | wc -l | tr -d ' ')
echo "Total rules to review: $TOTAL"
```

2. Verify Stage 0 vendor cache (Elastic + Sigma) — REQUIRED (board grep-grounds against it, no web search):
```bash
ELASTIC=$(find agent_state/siem_pipeline/stage_0/cache/elastic-detection-rules -name "*.toml" 2>/dev/null | wc -l | tr -d ' ')
SIGMA=$(find agent_state/siem_pipeline/stage_0/cache/sigma -name "*.yml" 2>/dev/null | wc -l | tr -d ' ')
echo "Vendor cache: Elastic=$ELASTIC Sigma=$SIGMA"
if [ "$ELASTIC" -lt 100 ] || [ "$SIGMA" -lt 100 ]; then
  echo "BLOCKED: Vendor cache incomplete. Run Stage 0 download first (e.g. /startup:rules-plugin --plugin siem --stage 0)."
  exit 1
fi
```

3. Check research cache:
```bash
echo "Research cache: $(ls policies/edr/research_cache/ 2>/dev/null | wc -l | tr -d ' ') technique files"
```

## Scope Resolution

- `--all` or empty: all rules, split into 4 groups by tactic (per the orchestrator)
- `--tactic {name}`: rules in `policies/edr/{name}/`
- `--technique {Txxxx}`: rules with matching MITRE technique_id
- `--rule {rule_id}`: single rule deep review (opus)

## Execution

Follow the orchestrator steps exactly:
- Step 0: Discovery + filter (exclude tests/, changes/, docs/, shared/, research_cache/, edr_legacy/, rulesets)
- Step 0.5: Vendor cache verification (BLOCK if incomplete)
- Step 1: Assign rules to 4 groups by tactic
- Step 2: Spawn group agents in parallel on `{{model}}` — each runs the inline protocol:
  vendor grounding → VALIDATOR DEFECT-1..15 → SOC FP estimate → 6 vendor lenses → fast-track/score →
  fix in place → logic-validate → test fixtures (REWORK only)
- Step 3: Consolidation (`.claude/agents/rule_board/rule_board_consolidator.md`)
- Step 4: Final report with verdict counts + score improvement

## Cost Optimization (same 6 as the other tailored boards)

1. Inline protocol — group agents do NOT read the specialist `.md` files.
2. Vendor cache grepped ONCE per technique, reused across rules — no per-rule web search.
3. Fast-track APPROVED (score ≥ 4.0 + 0 hard blockers) = 1 line, no files.
4. Full DEFECT checklist inline (15 items + DEFECT-CAT-1..9 systemic screen).
5. Batch ~50 rules per agent; all group agents on `{{model}}` (single-rule `--rule` = opus).
6. Test fixtures + change docs only for REWORK rules.
