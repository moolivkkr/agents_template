---
command: rules-board-dspm
description: "Run the DSPM Posture Rule Quality Board — reviews data-security posture rules for fact-vocabulary accuracy, predicate soundness, FP risk, vendor/catalog parity, compliance mapping, severity calibration, and coverage. Produces improved rules, fact-snapshot test fixtures, and change docs."
arguments:
  - name: scope
    required: false
    description: "Scope: --all (all rules), --category exposure (single category), --rule prule_public_sensitive (single rule deep review), --seed (review the engine's 6-rule seed). Defaults to --all."
  - name: model
    required: false
    default: opus
    description: "Model for review agents. Default: opus (Claude Opus 5.5); pass sonnet for large low-risk batches at about half the cost."
  - name: batch_size
    required: false
    default: 50
    description: "Rules per batch."
---

# /rules-board-dspm — DSPM Posture Rule Quality Board

Read `.claude/agents/rule_board/dspm/dspm_rule_quality_board_orchestrator.md` and execute it.

Reviews `posture_rule` entities (sensitivity gate + predicate tree over the asset-fact vocabulary) —
NOT log/API/event detections. The vendor-parity reference is the policy catalog in
`research/dspm/policies/` (00 overview + 01–14). Standards:
`.claude/agents/rule_board/dspm/DSPM_RULE_AUTHORING_STANDARDS.md`.

## Pre-flight

1. Count DSPM posture rules (exclude test fixtures):
```bash
python3 -c "
import json, os
count = 0
root_dir = 'policies/dspm'
if not os.path.isdir(root_dir):
    print('No policies/dspm/ yet — author the corpus first with /startup:rules-plugin dspm, or use --seed.')
else:
    for root, dirs, files in os.walk(root_dir):
        if any(x in root for x in ('/tests','/changes','/shared')): continue
        for f in files:
            if not f.endswith('.json'): continue
            try:
                d = json.load(open(os.path.join(root, f)))
                if d.get('entity_type') == 'posture_rule' and 'test_suite_version' not in d:
                    count += 1
            except: pass
    print(f'DSPM posture rules to review: {count}')
"
```

2. Backfill missing entity_type / id before review:
```bash
python3 -c "
import json, os
fixed = 0
for root, dirs, files in os.walk('policies/dspm') if os.path.isdir('policies/dspm') else []:
    if any(x in root for x in ('/tests','/changes','/shared')): continue
    for f in files:
        if not f.endswith('.json'): continue
        path = os.path.join(root, f)
        try: d = json.load(open(path))
        except: continue
        if 'test_suite_version' in d: continue
        changed = False
        if 'entity_type' not in d:
            d['entity_type'] = 'posture_rule'; changed = True
        if 'id' not in d and 'rule_id' in d:
            d['id'] = d['rule_id']; changed = True
        if changed:
            json.dump(d, open(path,'w'), indent=2); fixed += 1
print(f'Fixed {fixed} files')
"
```

3. Verify the parity index (catalog) exists:
```bash
test -f research/dspm/policies/00-catalog-overview.md \
  || echo "BLOCKED: DSPM policy catalog missing — research/dspm/policies/ is the vendor-parity index."
```

## Execution

Follow the orchestrator:
- Step 0: Discovery + filter test fixtures (handles empty corpus + --seed)
- Step 1: Group by catalog category (G1 Exposure … G8 Column-level)
- Step 2: Spawn group agents ({{model}}, batched ~50) — each loads its catalog files ONCE as the parity index
- Step 2b: Quality gate (post-score >= 4.0)
- Step 3: Consolidation (shared `rule_board_consolidator.md`) — cross-category consistency + catalog-coverage gaps + fact-registry drift
- Step 4: Final report

## Cost Optimization

Same 6 optimizations as the CSPM/EDR boards:
1. Inline protocol (group agents do NOT read specialist .md files)
2. Parity index = the catalog files, loaded ONCE per batch (no per-rule web search, no training-knowledge vocab)
3. Fast-track APPROVED (1 line)
4. DEFECT checklist 12 items, 6 critical
5. Batch 50 rules per agent
6. Test fixtures only for REWORK
