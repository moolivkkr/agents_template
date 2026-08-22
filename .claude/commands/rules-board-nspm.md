---
command: rules-board-nspm
description: "Run the NSPM Rule Quality Board — reviews Network Security Posture rules for framework accuracy (NIST 800-41/207/125B, PCI §1, CIS, MANRS), fact-vocabulary soundness (registry closure), posture-vs-behavioral modality, scope-boundary discipline (no CSPM cloud-SG/NACL/VPC or KSPM NetworkPolicy duplication), FP risk (management networks, intended exceptions), compliance mapping, and severity calibration. Produces improved rules, fact-snapshot test fixtures, and change docs."
arguments:
  - name: scope
    required: false
    description: "Scope: --all (all rules), --domain firewall_policy (single domain), --rule nspm_rule_firewall_policy_any_any_permit (single rule deep review). Defaults to --all."
  - name: model
    required: false
    default: sonnet
    description: "Model for review agents. Default: sonnet (opus for --rule deep review)."
  - name: batch_size
    required: false
    default: 40
    description: "Rules per batch."
---

# /rules-board-nspm — NSPM Rule Quality Board

Read `.claude/agents/rule_board/nspm/nspm_rule_quality_board_orchestrator.md` and execute it.

## Pre-flight

1. Count NSPM rules:
```bash
python3 -c "
import json, glob, os
n=0
for f in glob.glob('policies/nspm/**/nspm_rule_*.json', recursive=True):
    if os.sep+'tests'+os.sep in f or os.sep+'changes'+os.sep in f: continue
    try:
        d=json.load(open(f))
        if d.get('entity_type')=='nspm_rule': n+=1
    except: pass
print(f'NSPM rules to review: {n}')
"
```

2. Verify research inputs (the board compares against these, NOT training knowledge):
```bash
test -f research/nspm/research_cache/nspm_fact_registry.json && echo "fact registry OK"
test -f research/nspm/research_cache/nspm_unified_index.json && echo "unified index OK"
test -f .claude/agents/rule_board/nspm/NSPM_RULE_AUTHORING_STANDARDS.md && echo "standards OK"
```

3. Run the corpus validation gate first — the board starts from a green corpus:
```bash
python3 tests/nspm_corpus_validation_test.py
```

## Execution

Follow the orchestrator:
- Step 0: Discovery + filter
- Step 1: Group by NSPM domain (4 groups)
- Step 2: Spawn group agents (sonnet, batched) — fact-registry + unified-index lookups, NOT training knowledge
- Step 2b: Quality gate (every rule ≥ 4.0/5)
- Step 3: Consolidation (cross-domain severity parity, modality drift, fact-registry closure, scope-boundary audit)
- Step 4: Final report

## Cost Optimization

Same posture as the CSPM/KSPM/DSPM boards:
1. Inline protocol (group agents do NOT read other agent .md files)
2. Lookups via `nspm_unified_index.json` + `nspm_fact_registry.json` (no web search, no training knowledge)
3. Fast-track APPROVED (1 line) for rules already ≥4.0 with 0 hard blockers
4. Reduced DEFECT checklist (the hard blockers from standards §1 + B4 scope boundary)
5. Batch 40 rules per agent
6. Full fixtures (8 TP + 6 TN + evasion) only for REWORK rules; APPROVED rules keep their fixtures
