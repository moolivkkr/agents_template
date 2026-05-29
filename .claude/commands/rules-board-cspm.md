---
command: rules-board-cspm
description: "Run the CSPM Rule Quality Board — reviews cloud posture rules for API accuracy, provider parity, compliance mapping, FP risk, and evasion resistance. Produces improved rules, test fixtures, and change docs."
arguments:
  - name: scope
    required: false
    description: "Scope: --all (all rules), --provider aws (single provider), --rule cspm_rule_aws_s3_public (single rule). Defaults to --all."
  - name: model
    required: false
    default: sonnet
    description: "Model for review agents. Default: sonnet."
  - name: batch_size
    required: false
    default: 50
    description: "Rules per batch."
---

# /rules-board-cspm — CSPM Rule Quality Board

Read `.claude/agents/rule_board/cspm/cspm_rule_quality_board_orchestrator.md` and execute it.

## Pre-flight

1. Count CSPM rules (exclude test fixtures):
```bash
python3 -c "
import json, os
count = 0
for root, dirs, files in os.walk('policies/cspm'):
    for f in files:
        if not f.endswith('.json'): continue
        if '/tests/' in root or '/changes/' in root or '/shared/' in root: continue
        try:
            d = json.load(open(os.path.join(root, f)))
            if d.get('entity_type') == 'cspm_rule' and 'test_suite_version' not in d:
                count += 1
        except: pass
print(f'CSPM rules to review: {count}')
"
```

2. Fix files with missing entity_type before review:
```bash
python3 -c "
import json, os
fixed = 0
for root, dirs, files in os.walk('policies/cspm'):
    for f in files:
        if not f.startswith('cspm_rule_') or not f.endswith('.json'): continue
        path = os.path.join(root, f)
        d = json.load(open(path))
        if 'entity_type' not in d and 'test_suite_version' not in d:
            d['entity_type'] = 'cspm_rule'
            if 'id' not in d and 'rule_id' in d:
                d['id'] = d['rule_id']
            json.dump(d, open(path, 'w'), indent=2)
            fixed += 1
print(f'Fixed {fixed} files with missing entity_type')
"
```

## Execution

Follow the orchestrator:
- Step 0: Discovery + filter test fixtures
- Step 1: Group by provider (aws / azure / gcp+multi / identity)
- Step 2: Spawn group agents (sonnet, batched)
- Step 3: Consolidation
- Step 4: Final report

## Cost Optimization

Same 6 optimizations as EDR board:
1. Inline protocol (no agent file reads)
2. No vendor cache needed (CSPM vendors are simpler)
3. Fast-track APPROVED (1 line)
4. Reduced DEFECT checklist (12 items, 5 critical)
5. Batch 50 rules per agent
6. Test cases only for REWORK
