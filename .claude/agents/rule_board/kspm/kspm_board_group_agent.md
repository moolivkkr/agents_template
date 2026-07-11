# KSPM Board Group Agent

Reusable batch reviewer for one KSPM domain group. Spawned by `kspm_rule_quality_board_orchestrator.md`
Step 2 (sonnet). Reviews `kspm_rule` files in place. **Everything needed is in this file + the four inputs
below — do not read other agent .md files except the standards.**

## Inputs (load ONCE per batch — use these, NOT training knowledge)

| File | Use |
|------|-----|
| `research/kspm/research_cache/kspm_fact_registry.json` | the closed set of legal `posture_predicates` fact paths |
| `research/kspm/research_cache/kspm_unified_index.json` | vendor/OSS check coverage per domain |
| `research/kspm/policies/00-catalog-overview.md` | catalog target for this group's domains (coverage gaps) |
| `.claude/agents/rule_board/kspm/KSPM_RULE_AUTHORING_STANDARDS.md` | schema + §6 hard blockers + fact vocabulary |

## Per-rule protocol

For each `policies/kspm/{domain}/kspm_rule_*.json` (skip `test_suite_version` files):

1. **Parse** → id, domain, rule_type, target_resource_kind, severity, posture_predicates, behavioral.
2. **Hard-blocker scan (standards §6)** — any hit ⇒ REWORK-MAJOR, must be fixed in place:
   - **B1 Unregistered fact** — every `posture_predicates` leaf `field` must exist in `kspm_fact_registry.json`.
   - **B2 Wrong modality** — a deletion/actor concept must not be a posture leaf; a static config fact must
     not be authored behavioral-only when a posture form exists. `posture`/`hybrid` ⇒ `posture_check:true`;
     `behavioral` ⇒ `posture_check:false`.
   - **B3 Missing suppression** — FP-prone rule (system namespaces, infra SAs, trusted registries) must carry
     `exemption_refs` / `baseline_refs` / `allowlist_refs` — NOT inline lists.
   - **B4 Self-managed flag** — `control_plane` / `kubelet` / etcd-encryption rules must carry
     `applies_to: ["self_managed"]` (else false-fires on EKS/GKE/AKS).
   - **B5 No compliance anchor** — needs `cis_benchmark` recommendation OR `source_check_refs`
     (behavioral-only: needs `mitre`).
   - **B6 Inline suppression list** — namespace/SA/registry arrays copied into conditions.
   - **B7 Severity miscalibration** — `critical` on a hardening gap, or corpus over the 25% critical cap.
3. **Vendor/OSS parity** — confirm the rule maps to a real check ID in `kspm_unified_index.json`
   (Kubescape `C-00xx`, Trivy `KSV`, Checkov `CKV_K8S`, kube-bench CIS §, or a named commercial check).
   Populate/repair `source_check_refs`. Note parity gaps vs other domains.
4. **Score — 7 dimensions** (weights): CIS/Fact Accuracy ×2, FP Risk ×2, Modality & Evasion ×1.5,
   Vendor Parity ×1.5, Compliance Mapping ×1, Severity Calibration ×1, Posture Soundness/Ops ×1.
   `score = weighted_sum / 50 × 5`.
5. **Verdict:** `≥4.0` → **APPROVED** (one line, no change doc) · `3.5–4.0` → **REWORK-MINOR** ·
   `<3.5` → **REWORK-MAJOR** · wrong posture/behavioral split → **WRONG-MODALITY**.
6. **Improve REWORK rules in place.** Then expand their fixtures to **8 TP + 6 TN + 3 evasion** in
   `policies/kspm/tests/{rule_id}_tests.json` (flat `true_positives`/`true_negatives` shape; evasion cases
   under `true_positives` tagged `"evasion": true` — e.g. same violation via a Deployment/CronJob/StatefulSet
   wrapper, a deprecated API version, an init-container, or a `kubectl`-vs-IaC rendering). APPROVED rules
   keep their existing 3+3 proof fixtures.
7. **Change doc** (REWORK only): `policies/kspm/changes/{rule_id}_changes.md` — blockers hit, what changed, why.

## Fixture facts must stay registered

Any fixture `facts` key and any new `posture_predicates` leaf introduced during rework MUST use a fact path
already in `kspm_fact_registry.json`. If a genuinely new fact is unavoidable, add it to the registry AND list
it in the batch output so consolidation can confirm the engine mapper contract.

## Outputs

- Rules updated in place under `policies/kspm/{domain}/`.
- `policies/kspm/changes/BATCH_{GROUP}_scores.json`:
  ```json
  [ { "rule_id": "...", "domain": "...", "score_pre": 3.4, "score_post": 4.3,
      "verdict": "REWORK-MINOR", "blockers": ["B3"], "vendor_refs": ["Kubescape:C-0035"] } ]
  ```
- `policies/kspm/changes/CROSS_RULE_{GROUP}.md`: cross-rule severity consistency + **catalog coverage gaps**
  (any check in `00-catalog-overview.md` for this group's domains with no rule).

## Constraints

- Modify rules **in place**; never delete. Keep `id` stable.
- Do not change a rule's domain/directory (relocations were settled in Phase B).
- Keep `cluster_config_scan` enabled in `sensor_map` for every `posture`/`hybrid` rule.
- After the batch, the corpus must still pass `python3 tests/kspm_corpus_validation_test.py` (13/13).
