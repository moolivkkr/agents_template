# /dspm-board — DSPM Posture Rule Quality Board Orchestrator

A multi-specialist review pipeline for Data Security Posture Management **posture rules**. Evaluates
every `posture_rule` for fact-vocabulary accuracy, predicate soundness, false-positive risk, vendor/
catalog parity, compliance mapping, severity calibration, and coverage/phasing.

**Quality standard:** Every rule must exit with projected post-improvement score >= 4.0/5.

**What this board is NOT:** it does not detect log/API/process events (that's CSPM/SIEM/EDR). A posture
rule is a sensitivity gate ANDed with a predicate tree over **asset facts**.

**Specialists (inline in the group agent):** 5 DSPM vendor lenses (Cyera, Sentra/Wiz, Varonis,
BigID/Securiti, Purview) + Fact Validator + DSPM Analyst + Compliance Mapper.

**Standards:** `.claude/agents/rule_board/dspm/DSPM_RULE_AUTHORING_STANDARDS.md`
**Group protocol:** `.claude/agents/rule_board/dspm/dspm_board_group_agent.md`
**Parity index (the catalog):** `research/dspm/policies/` (00 overview + 01–08 + 09–14 gap-fill)

## Prerequisite — there must be rules to review

This board reviews **authored** `posture_rule` files. It is the **review stage** that pairs with
authoring (`/startup:rules-plugin dspm`). If `policies/dspm/` has no rules yet, the board has nothing
to do except the engine seed. Discovery (Step 0) handles all three cases:
- `policies/dspm/**/*.json` — the composer-authored corpus (primary target)
- `--seed` — review the engine seed `../dspm_engine/internal/posture/rules/seed/posture_rules.json`
- empty → report "no rules to review; author with /startup:rules-plugin dspm first" and exit cleanly.

## Model Assignment

| Step | Agent | Model |
|------|-------|-------|
| Step 0–1 | Discovery / grouping | orchestrator/parent |
| Step 2 | Group agents (batch review) | **sonnet** |
| Step 3 | Consolidation | **sonnet** |
| `--rule` single rule | Full deep review | **opus** |

## Invocation

```
/dspm-board --all                         # all posture rules (parallel by category)
/dspm-board --category exposure           # single category group
/dspm-board --rule prule_public_sensitive # single rule deep review (opus)
/dspm-board --seed                        # review the engine's 6-rule seed
```

## Output

All output to `policies/dspm/` (in-place):

```
policies/dspm/
  {category}/
    {rule_id}.json              ← improved rule (in-place update)
  tests/
    {rule_id}_tests.json        ← fact-snapshot fixtures (TP + TN + coverage-gap)
  changes/
    {rule_id}_changes.md        ← what changed, why
    BATCH_{group}_scores.json   ← per-group scores
    CROSS_RULE_{group}.md       ← cross-rule consistency
  REVIEW_SUMMARY.md             ← cross-category findings
```

---

## Step 0 — Discovery and Filtering

```bash
find policies/dspm -name "*.json" \
  -not -path "*/tests/*" -not -path "*/changes/*" -not -path "*/shared/*" \
  | sort > /tmp/dspm_board_all_rules.txt
TOTAL=$(wc -l < /tmp/dspm_board_all_rules.txt | tr -d ' ')
echo "Posture rules to review: $TOTAL"
mkdir -p policies/dspm/{changes,tests}
```

Filter to actual rules (skip test fixtures):
```python
import json
d = json.load(open(path))
if 'test_suite_version' in d: skip          # test fixture, not a rule
if d.get('entity_type') != 'posture_rule': skip
```

If TOTAL == 0: print the "author first" guidance above and exit (unless `--seed`).

## Step 1 — Assign Rules to Groups by Catalog Category

Group by the policy catalog's category (maps to `policies/dspm/{category}/` and the catalog docs the
group loads as its parity index). Suggested grouping (rebalance to ~50/agent):

| Group | Categories (catalog docs) | Parity files to load |
|-------|---------------------------|----------------------|
| **G1 Exposure** | exposure & sharing | 01 |
| **G2 Access** | access & permissions | 02 |
| **G3 Encryption** | encryption & protection | 03 |
| **G4 Residency+Retention** | residency, retention/ROT | 04, 05 |
| **G5 Hygiene+Compliance** | environment/hygiene, compliance-driven | 06, 07 |
| **G6 AI** | DSPM-for-AI | 08 |
| **G7 Store-native** | warehouse, NoSQL, block/file | 10, 11, 12 |
| **G8 Column-level** | structured/column-level (P2) | 13 |

Every group also loads `00-catalog-overview.md` (the canonical fact vocabulary §2 + schema gaps §3).

## Step 2 — Spawn Group Agents in PARALLEL (sonnet)

```
Agent prompt (per group):
"You are running the DSPM Posture Rule Quality Board for category group {GROUP}.

PARITY INDEX (load ONCE, use for ALL rules — DO NOT web-search per rule, DO NOT use training
knowledge for the fact vocabulary):
  research/dspm/policies/00-catalog-overview.md     (fact vocabulary §2 + schema gaps §3 + issue_types §4)
  research/dspm/policies/{your category files}       (per-policy detail + vendor citations)

PROTOCOL (do NOT read agent .md files — everything is inline here; mirror
.claude/agents/rule_board/dspm/dspm_board_group_agent.md):
For each rule:
1. Read rule → id, issue_type, target_asset_kind, sensitivity_predicate, posture_predicates, severity_tiers, suggested_action, regulation_refs, fields-used.
2. Fact validation → every field ∈ vocab? op matches type? value ∈ enum? (use loaded vocab)
3. Parity → map to catalog policy; confirm vendor/compliance grounding.
4. DEFECT scan → 12 items, 6 hard blockers (DEFECT-1 field registered, -2 op/type, -3 sensitivity gate, -4 no wrong-layer fields, -5 FP guard, -6 unknown-fact safe, -11 asset_kind match).
5. Score → 7 dims weighted (Fact Accuracy 2×, FP Risk 2×, Predicate Soundness 1.5×, Vendor/Catalog Parity 1.5×, Compliance 1×, Severity&Remediation 1×, Coverage/Phasing 1×).
6. Verdict: ≥4.0+0 blockers→APPROVED (1 line); 3.5–4.0→REWORK-MINOR; <3.5 or hard blocker→REWORK-MAJOR; event/API fields→WRONG-LAYER.
7. Fix REWORK rules IN PLACE in policies/dspm/{category}/.
8. Test fixtures ONLY for REWORK: 5 TP + 5 TN + 3 coverage-gap (asset-fact snapshots).

Rules: the posture_rule_*.json files in policies/dspm/{category}/ — exclude test fixtures
(test_suite_version) and non-posture_rule entity types.
Write changes → policies/dspm/changes/. Tests → policies/dspm/tests/.
SCORE OUTPUT: write policies/dspm/changes/BATCH_{group}_scores.json"
```

## Step 2b — Quality Gate Verification

```python
import json, os, glob
for sf in glob.glob('policies/dspm/changes/BATCH_*_scores.json'):
    scores = json.load(open(sf))
    for r in scores.get('rules', []):
        post = r.get('score_post', r.get('score', 0))
        if post < 4.0:
            print(f"QUALITY GATE: {r['rule_id']} at {post}/5 — needs another pass")
```

## Step 3 — Consolidation

Use the shared consolidator (`.claude/agents/rule_board/rule_board_consolidator.md`) to produce
`policies/dspm/REVIEW_SUMMARY.md` + cross-category consistency:
- Duplicate/near-duplicate rules across categories (e.g. an exposure rule re-implemented under compliance)
- issue_type / regulation_ref inconsistencies
- Fact-vocabulary drift (rules using fields not in the registry → propose registry additions)
- Coverage gaps (catalog policies with no authored rule yet)

## Step 4 — Final Report

```
DSPM Posture Rule Quality Board Complete
═══════════════════════════════════════════════════════
Rules reviewed:      N
  APPROVED:          N
  REWORK-MINOR:      N
  REWORK-MAJOR:      N
  WRONG-LAYER:       N   (belongs in CSPM/SIEM/EDR)

Score improvement:    avg pre N.N/5 → post N.N/5

Catalog coverage:     N / 181 catalog policies have an authored rule
  Unauthored (top gaps): ...

Fact-registry health: N rules used unregistered fields (proposed additions: ...)
═══════════════════════════════════════════════════════
```

---

## 7 Evaluation Dimensions (DSPM-specific)

| # | Dimension | Weight | What It Measures |
|---|-----------|--------|------------------|
| 1 | **Fact Accuracy** | 2× | Field registered? Op/type/enum correct? asset_level matches target_asset_kind? |
| 2 | **FP Risk** | 2× | Sensitivity gate + FP guards (intended-public, synthetic, sanctioned, legal-hold, immutable)? |
| 3 | **Predicate Soundness** | 1.5× | all/any correct? Unknown-fact safe? Absent enrichment not in AND? Derived-boolean for 2-fact compares? |
| 4 | **Vendor / Catalog Parity** | 1.5× | Maps to a real, vendor-cited catalog policy with consistent logic? |
| 5 | **Compliance Mapping** | 1× | regulation_refs valid & existent? issue_type fit? control citation accurate? |
| 6 | **Severity & Remediation** | 1× | Severity = blast-radius × sensitivity × reversibility? suggested_action valid & safe? |
| 7 | **Coverage / Phasing** | 1× | store_kind coverage? Sibling-fact bypass? Phase tag honest vs facts used? |

**Score = weighted_sum / 50 × 5 = N.N/5**

## Hard Blockers (= REWORK-MAJOR)

- Predicate references a `field` not in the catalog fact registry
- Operator/type mismatch (e.g. `gt` on a bool, `in` with a scalar, `contains` on a non-array)
- No sensitivity gate (`sensitivity_predicate` empty or all-tiers) → fires on Public/Internal
- Event/API/process/log fields in predicates → WRONG-LAYER (CSPM/SIEM/EDR)
- Missing category-appropriate FP guard (legal hold on deletion rules; intended-public on exposure rules)
- Violation fires on **absent** telemetry (must assert a collected value; see unknown-fact rule)
- `target_asset_kind` mismatched with the facts' asset_level (column facts on a store rule)
