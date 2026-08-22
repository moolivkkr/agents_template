---
command: rules-board-kspm
description: "Run the KSPM Rule Quality Board — reviews Kubernetes posture rules for CIS/NSA-CISA accuracy, fact-vocabulary soundness, posture-vs-behavioral modality, vendor parity (Wiz/Aqua/Prisma/Kyverno/OPA), FP risk (system namespaces, managed clusters), compliance mapping, and severity calibration. Produces improved rules, fact-snapshot test fixtures, and change docs."
arguments:
  - name: scope
    required: false
    description: "Scope: --all (all rules), --domain rbac (single domain), --rule kspm_rule_cluster_admin_binding (single rule deep review). Defaults to --all."
  - name: model
    required: false
    default: sonnet
    description: "Model for review agents. Default: sonnet (opus for --rule deep review)."
  - name: batch_size
    required: false
    default: 40
    description: "Rules per batch."
---

# /rules-board-kspm — KSPM Rule Quality Board

Read `.claude/agents/rule_board/kspm/kspm_rule_quality_board_orchestrator.md` and execute it.

## Pre-flight

1. Count KSPM rules (exclude test fixtures / rulesets / shared):
```bash
python3 -c "
import json, glob, os
count = 0
for f in glob.glob('policies/kspm/**/kspm_rule_*.json', recursive=True):
    if os.sep+'tests'+os.sep in f: continue
    try:
        d = json.load(open(f))
        if d.get('entity_type') == 'kspm_rule' and 'test_suite_version' not in d:
            count += 1
    except: pass
print(f'KSPM rules to review: {count}')
"
```

2. Verify the research inputs exist (the board compares against these, NOT training knowledge):
```bash
test -f policies/kspm/../../research/kspm/research_cache/kspm_unified_index.json && echo "unified index OK"
test -f research/kspm/research_cache/kspm_fact_registry.json && echo "fact registry OK"
test -f .claude/agents/rule_board/kspm/KSPM_RULE_AUTHORING_STANDARDS.md && echo "standards OK"
```

3. Run the corpus validation gate first — the board should start from a green corpus:
```bash
python3 tests/kspm_corpus_validation_test.py
```

## Execution

Follow the orchestrator:
- Step 0: Discovery + filter test fixtures
- Step 1: Group by K8s domain (4 groups)
- Step 2: Spawn group agents (sonnet, batched) — fact-registry + unified-index lookups, NOT training knowledge
- Step 2b: Quality gate (every rule ≥ 4.0/5)
- Step 3: Consolidation (cross-domain parity, modality drift, fact-registry closure)
- Step 4: Final report

## Cost Optimization

Same posture as the CSPM/DSPM boards:
1. Inline protocol (group agents do NOT read other agent .md files)
2. Lookups via `kspm_unified_index.json` + `kspm_fact_registry.json` (no web search, no training knowledge)
3. Fast-track APPROVED (1 line) for rules already ≥4.0 with 0 hard blockers
4. Reduced DEFECT checklist (the 7 hard blockers from standards §6)
5. Batch 40 rules per agent
6. Full test fixtures (8 TP + 6 TN + evasion) only for REWORK rules; APPROVED rules keep their 3+3 proof fixtures
