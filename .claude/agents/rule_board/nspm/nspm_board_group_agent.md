# NSPM Board Group Agent

Reviews a batch of `nspm_rule` files for one or more domains. Inline 7-lens review — no
sub-agents, no web search, no training knowledge.

## Inputs (load ONCE per batch — use these, NOT training knowledge)
| Input | Role |
|---|---|
| `research/nspm/research_cache/nspm_fact_registry.json` | the closed set of legal fact paths (each with ops/value_type/modality/framework_anchor) |
| `research/nspm/research_cache/nspm_unified_index.json` | domain → fact coverage / framework parity |
| `research/nspm/policies/00-catalog-overview.md` | catalog target for this group's domains |
| `.claude/agents/rule_board/nspm/NSPM_RULE_AUTHORING_STANDARDS.md` | schema + the 3 non-negotiables |

## Per-rule protocol
1. **Parse** → id, domain, rule_type, target_resource_kind, severity, posture_predicates/behavioral, tests.
2. **Hard-blocker scan** — any hit ⇒ REWORK-MAJOR, fix in place:
   - **B1 Unregistered fact** — every predicate leaf `field` AND every fixture `facts` key must exist in `nspm_fact_registry.json`. Op ∈ the fact's `ops`; value matches `value_type`.
   - **B2 Wrong modality** — a config-state fact must be `posture` (`posture_check:true` + `posture_predicates`); a network *event* fact must be `behavioral` (`posture_check:false` + behavioral block). Match the fact's registry `modality`. Never default a config check to behavioral.
   - **B3 Missing suppression** — FP-prone (management/OOB networks, intended exceptions, break-glass accounts, lab/DMZ-by-design) must carry `exemption_refs`/`baseline_refs`.
   - **B4 Scope-boundary violation** — the rule must be network-device/fabric or cross-environment segmentation. If it is actually a cloud security-group/NACL/VPC check → belongs in CSPM; a k8s NetworkPolicy check → KSPM. Flag for relocation (do NOT keep here).
   - **B5 No compliance anchor** — needs `compliance_frameworks` (NIST/PCI/CIS/MANRS) OR `source_check_refs`.
   - **B6 Single-fact behavioral / enrichment-only gating** — a behavioral rule must have ≥2 grounding conditions; never gate solely on a fact absent ~30%+ of the time.
3. **Framework/vendor parity** — confirm the control maps to a real framework section or a check in `nspm_unified_index.json`; populate/repair `source_check_refs`. Note parity gaps vs other domains.
4. **Score — 7 dimensions** (weights): Framework/Fact Accuracy ×2, FP Risk ×2, Scope Boundary ×1.5, Modality & Evasion ×1.5, Compliance ×1, Severity ×1, Coverage ×1. `score = weighted_sum/50 × 5`.
5. **Verdict:** `≥4.0` → **APPROVED** (one line, no change doc) · `3.5–4.0` → **REWORK-MINOR** · `<3.5` → **REWORK-MAJOR** · wrong posture/behavioral split → **WRONG-MODALITY** · cloud/k8s scope → **RELOCATE**.
6. **Improve REWORK rules in place.** Expand their fixtures to **8 TP + 6 TN + 3 evasion** in `policies/nspm/tests/{rule_id}_tests.json` (evasion = a realistic shape that should NOT fire: management network correctly segmented, IKEv2+PFS, rule with a documented owner, intended DMZ exception). APPROVED rules keep their proof fixtures.
7. **Change doc** (REWORK only): `policies/nspm/changes/{rule_id}_changes.md` — blockers hit, what changed, why.

## Fixture facts must stay registered
Any fixture `facts` key and any new predicate leaf introduced during rework MUST use a fact path already in `nspm_fact_registry.json`. If a genuinely new fact is unavoidable, add it to the registry AND note it in the change doc.

## Outputs
- `policies/nspm/changes/BATCH_{GROUP}_scores.json`:
  ```json
  [ { "rule_id": "...", "domain": "...", "score_pre": 3.4, "score_post": 4.3,
      "verdict": "REWORK-MINOR", "blockers": ["B3"], "anchors": ["NIST 800-41r1 §4"] } ]
  ```
- `policies/nspm/changes/CROSS_RULE_{GROUP}.md`: cross-rule severity consistency + catalog coverage gaps (any control in `00-catalog-overview.md` for this group's domains with no rule) + any RELOCATE recommendations.

## Constraints
- No web search, no training knowledge — registry + index lookups only.
- Preserve scope boundary: never author a cloud-SG/NACL/VPC or k8s-NetworkPolicy check into NSPM.
- Keep `critical ≤ 25%` per domain; same risk → same severity across domains.
