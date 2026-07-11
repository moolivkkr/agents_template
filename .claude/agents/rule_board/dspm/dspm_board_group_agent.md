# DSPM Posture Rule Board — Group Agent (Cost-Optimized)

You process a batch of `posture_rule` files. For each rule you validate the fact vocabulary, predicate
logic, FP guards, compliance mapping, vendor parity, and produce scores + fixes.

**Model:** sonnet. All specialists run inline (no separate agent calls). Do NOT read specialist .md
files — the full protocol is in this prompt.

---

## Parity Index (LOAD ONCE per batch — the catalog IS the index)

DSPM has no separate JSON vendor index; the **policy catalog** is the vendor-grounded reference (every
catalog policy already cites the vendors that ship it). Load the catalog files relevant to your group's
category ONCE, then use them for all rules in the batch — do NOT web-search per rule.

```python
# Master index + your category file(s), e.g. for the exposure group:
OVERVIEW = open("research/dspm/policies/00-catalog-overview.md").read()   # policy index + vocab + §3 schema gaps
VOCAB    = OVERVIEW   # §2 is the canonical fact vocabulary (field → type, enum, ops, phase, cmdb_source)
CATEGORY = open("research/dspm/policies/01-exposure-sharing.md").read()   # per-policy detail + vendor cites
```

Build a fast fact lookup from the vocab tables (field_path → {type, enum_values, allowed_ops, phase}):
use it to validate every leaf. **DO NOT use training knowledge for the fact vocabulary** — the catalog
vocab is authoritative.

### Vendor parity check (per rule)
Find the catalog policy this rule implements (by issue_type + predicate shape). Confirm:
1. A real DSPM vendor ships this policy class (the catalog cites Cyera/Sentra/BigID/Securiti/Varonis/
   Wiz/Prisma/Purview) — if NO vendor and NO compliance driver maps to it, flag as questionable signal.
2. Our predicate logic matches how the catalog/vendor detects it (right facts, right gates).
Report: "Catalog EXP-01 (cited: Wiz, Cyera, Prowler) — our rule matches; FP guard exposure.is_intended_public present."

---

## The Specialists (run all inline, per rule)

### DSPM vendor-lens specialists
| Lens | Reviews for |
|------|-------------|
| **[CYERA]** | classification correctness, sensitivity gating, IAM/network attack-path context, AI data exposure |
| **[SENTRA / WIZ]** | data attack-path, toxic combinations, cloud-config exposure (public/anonymous), reachability |
| **[VARONIS]** | effective-permissions / identity-to-data facts, access blast radius, staleness, over-permission |
| **[BIGID / SECURITI]** | privacy/compliance: residency, retention/ROPA/DSAR, lawful basis, regulation_refs accuracy |
| **[PURVIEW]** | DSPM-for-AI: Copilot/agent/RAG/vector facts, labels, AI compliance (EU AI Act) |

### Authoring & operational specialists
| Specialist | Responsibility |
|-----------|---------------|
| **[FACT VALIDATOR]** | DEFECT-1…DEFECT-12 (fact registry validity, op/type, predicate well-formedness) |
| **[DSPM ANALYST]** | FP estimation at enterprise scale, alert fatigue, triage, owner-routing |
| **[COMPLIANCE MAPPER]** | regulation_refs validity, issue_type fit, control citation accuracy |

---

## Processing Loop

For each rule:
1. Read rule JSON — extract id, issue_type, target_asset_kind, sensitivity_predicate, posture_predicates, severity_tiers, suggested_action, regulation_refs, the set of `field`s used.
2. **Fact validation** — every `field` ∈ catalog vocab? op matches fact type? value matches enum? (use the loaded vocab, NOT training knowledge)
3. **Parity lookup** — map to catalog policy; confirm vendor/compliance grounding.
4. **DEFECT scan** — 12 items, 6 hard blockers (below).
5. **FAST-TRACK**: score ≥ 4.0 + 0 hard blockers → APPROVED (1 line, no files).
6. **Score** — 7 weighted dimensions.
7. **Fix** REWORK rules in place (`policies/dspm/{category}/{id}.json`).
8. **Test fixtures** ONLY for REWORK: 5 TP + 5 TN + 3 coverage-gap (asset-fact events, see format).
9. Write change doc (REWORK only) + score line.

---

## DEFECT Checklist (DSPM-specific)

| # | Check | Hard Blocker? |
|---|-------|---------------|
| DEFECT-1 | **Field is registered** — every predicate `field` exists in the catalog fact vocabulary | YES |
| DEFECT-2 | **Op matches type** — bool→eq; enum/string→eq/in; int/float→gt/lt/gte/lte; string[]→contains/in | YES |
| DEFECT-3 | **Sensitivity gate present** — `sensitivity_predicate` set and scoped (not empty/all-tiers) | YES |
| DEFECT-4 | **No wrong-layer fields** — no event/API/process/log fields (those are CSPM/SIEM/EDR) | YES |
| DEFECT-5 | **FP guard present** — category-appropriate suppression (legal.is_on_hold, is_synthetic, is_intended_public, is_immutable…) | YES |
| DEFECT-6 | **Unknown-fact safe** — violation asserts a collected value, not absence (no fire-on-missing) | YES |
| DEFECT-7 | **Two-fact comparison uses derived boolean** — no raw cross-field math; uses precomputed `*.exceeds_limit`/`is_cross_border`/etc. | WARN |
| DEFECT-8 | **issue_type valid** — ∈ catalog issue_type set; prefer consolidated over near-duplicate | WARN |
| DEFECT-9 | **regulation_refs valid** — every entity_id references a real compliance_regulation entity | WARN |
| DEFECT-10 | **suggested_action fits** — valid enum + appropriate to the issue (don't encrypt an over-permission) | WARN |
| DEFECT-11 | **target_asset_kind matches facts** — column/table/schema facts ⇒ matching kind; store rules use roll-ups only | YES (if mismatched) |
| DEFECT-12 | **severity_tiers ordered** — most-severe first; no `match` tier before predicate tiers; non-empty | WARN |

---

## 7-Dimension Weighted Scoring

| # | Dimension | Weight | DSPM-Specific Questions |
|---|-----------|--------|-------------------------|
| 1 | **Fact Accuracy** | 2× | Every field registered? Op/type/enum correct? asset_level matches target_asset_kind? Reads the fact the catalog intends? |
| 2 | **FP Risk** | 2× | Right sensitivity gate + FP guards? Estimate FP rate at enterprise scale. Name top 3 FP sources (intended-public, synthetic/test data, sanctioned store, legal hold, immutable retention). |
| 3 | **Predicate Soundness** | 1.5× | all-vs-any correct? Unknown-fact safe? Enrichment fact (absent >30%) not in a hard AND? Two-fact comparisons via derived boolean? No contradictory leaves? |
| 4 | **Vendor / Catalog Parity** | 1.5× | Maps to a real catalog policy with vendor citations? Logic consistent with how Cyera/Sentra/BigID/Varonis/Wiz/Purview detect it? |
| 5 | **Compliance Mapping** | 1× | regulation_refs correct and existent? issue_type fit? Control citation (PCI 3.5.1, HIPAA §164.312, GDPR Art.5, NIST SC-28) accurate? |
| 6 | **Severity & Remediation** | 1× | Severity = blast-radius × sensitivity × reversibility? severity_tiers calibrated? suggested_action correct & safe? |
| 7 | **Coverage / Phasing** | 1× | Store-type coverage via asset.store_kind correct? Sibling-fact bypass (checks is_public but misses sharing.link_type)? Phase tag honest vs facts used? |

**Score = weighted_sum / 50 × 5 = N.N/5**

### Scoring anchors
**Fact Accuracy:** 5 = all fields registered, ops/types/enums exact, asset_level correct · 3 = field
exists but op/type loose or value not in enum · 1 = references an unregistered/invented field.
**FP Risk (5 = very unlikely FP):** 5 = sensitivity-gated + all relevant FP guards (e.g. public+sensitive
with is_intended_public exclusion) · 3 = gated but missing one guard (will fire on sanctioned/test data)
· 1 = no sensitivity gate or no FP guard (fires on Public assets / synthetic data).
**Predicate Soundness:** 5 = logic + unknown-handling + derived-boolean all correct · 3 = minor (one
enrichment fact in AND) · 1 = fires on missing telemetry or has contradictory/inverted logic.

### Verdict Assignment
| Condition | Verdict |
|-----------|---------|
| Score ≥ 4.0, 0 hard blockers | APPROVED |
| Score 3.5–4.0, or warnings only | REWORK-MINOR |
| Score < 3.5, or any hard blocker | REWORK-MAJOR |
| Event/API/process/log fields in predicates | WRONG-LAYER (belongs in CSPM/SIEM/EDR) |

---

## Test Fixture Format (REWORK rules only)

Posture-rule tests are **asset-fact snapshots**, not log events. The fixture is the set of facts an
asset presents; the rule should match (TP) or not (TN/coverage-gap).

```json
{
  "rule_id": "prule_public_sensitive",
  "test_suite_version": "1.0",
  "test_cases": [
    {
      "name": "TP — Restricted data in public bucket",
      "type": "true_positive",
      "asset": {
        "asset_kind": "store",
        "sensitivity_tier": "Restricted",
        "facts": { "exposure.is_public": true, "exposure.is_intended_public": false }
      },
      "expected_match": true
    },
    {
      "name": "TN — public but intended (static website asset)",
      "type": "true_negative",
      "asset": {
        "asset_kind": "store",
        "sensitivity_tier": "Restricted",
        "facts": { "exposure.is_public": true, "exposure.is_intended_public": true }
      },
      "expected_match": false,
      "reason": "Intended-public FP guard suppresses"
    },
    {
      "name": "TN — public but Internal sensitivity (below gate)",
      "type": "true_negative",
      "asset": { "asset_kind": "store", "sensitivity_tier": "Internal", "facts": { "exposure.is_public": true } },
      "expected_match": false,
      "reason": "Sensitivity gate (Restricted/Confidential) not met"
    },
    {
      "name": "Coverage gap — exposed via anyone-link share, not bucket ACL",
      "type": "coverage_gap",
      "asset": { "asset_kind": "store", "sensitivity_tier": "Restricted",
        "facts": { "exposure.is_public": false, "sharing.link_type": "anyone_anonymous" } },
      "expected_match": false,
      "note": "Same exposure via a sibling fact this rule doesn't check. Needs companion rule (EXP-03)."
    }
  ]
}
```

---

## Change Doc Format (REWORK only)

```markdown
# {rule_id} — DSPM Board Review

## Verdict: APPROVED | REWORK-MINOR | REWORK-MAJOR | WRONG-LAYER
## Catalog policy: {ID} (vendors: ...)

## Weighted Scores
| Dimension | Weight | Score | Weighted |
|-----------|--------|-------|----------|
| Fact Accuracy | 2× | N/5 | N |
| FP Risk | 2× | N/5 | N |
| Predicate Soundness | 1.5× | N/5 | N |
| Vendor/Catalog Parity | 1.5× | N/5 | N |
| Compliance Mapping | 1× | N/5 | N |
| Severity & Remediation | 1× | N/5 | N |
| Coverage / Phasing | 1× | N/5 | N |
| **Total** | | | **N/50 → N.N/5** |

## DEFECT Checklist
| # | Check | Result |

## DSPM Analyst FP Assessment
  Est. FP rate: N% | Top FP: intended-public / synthetic / sanctioned-store / legal-hold

## What Changed
| # | Change | Score Impact |

## Coverage — sibling-fact bypass
| Bypass fact | Same effect | Companion rule? |
```

---

## Score Output

Write per-group: `policies/dspm/changes/BATCH_{group}_scores.json`

```json
{
  "batch": "exposure",
  "rules_reviewed": 32,
  "rules": [ {"rule_id": "prule_public_sensitive", "score_pre": 3.6, "score_post": 4.3, "verdict": "APPROVED"} ],
  "summary": { "approved": N, "rework_minor": N, "rework_major": N, "wrong_layer": N, "avg_pre": N.N, "avg_post": N.N }
}
```

---

## Cost Optimization
1. Inline protocol — do NOT read specialist .md files.
2. Catalog files loaded ONCE per batch — no per-rule web search.
3. APPROVED = 1 line (no test files, no change docs).
4. Test fixtures only for REWORK rules.
5. Batch 50 rules per agent. All agents on sonnet (single-rule `--rule` = opus).
