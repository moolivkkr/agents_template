# /kspm-board — KSPM Rule Quality Board Orchestrator

A 7-specialist review pipeline for Kubernetes Security Posture Management rules. Evaluates every
`kspm_rule` for CIS/NSA-CISA accuracy, **posture-fact-vocabulary soundness**, posture-vs-behavioral
**modality**, false-positive risk (system namespaces, managed clusters), vendor parity, compliance
mapping, and severity calibration.

**Quality standard:** Every rule must exit with projected post-improvement score >= 4.0/5.

**Specialists (7 lenses, applied inline per rule — group agents do NOT spawn separate sub-agents):**
- **CIS-K8s Accuracy** — recommendation IDs (CIS Kubernetes Benchmark v1.12.0), section structure, flag/field correctness
- **NSA/CISA Hardening** — hardening-domain alignment (pod security, network separation, authn/authz, audit, upgrading)
- **Vendor Parity** — Wiz / Prisma / Aqua / Datadog / Sysdig coverage + Kubescape `C-00xx` / Trivy `KSV` / Checkov `CKV_K8S` / kube-bench CIS §
- **Policy-as-Code** — Kyverno / OPA-Gatekeeper enforceability of the equivalent control
- **Posture-Fact Soundness** — every `posture_predicates` leaf field is registered, correctly typed, correct quantifier; modality is right
- **FP / Ops Readiness** — suppression refs present, `applies_to [self_managed]` on control-plane/kubelet, unknown-fact safety, triage clarity
- **Compliance Mapper** — CIS K8s, NSA/CISA, NIST 800-190, PSS level, ATT&CK Containers technique correctly cited

**Standards:** `.claude/agents/rule_board/kspm/KSPM_RULE_AUTHORING_STANDARDS.md`
**Group agent:** `.claude/agents/rule_board/kspm/kspm_board_group_agent.md`
**Consolidator (shared):** `.claude/agents/rule_board/rule_board_consolidator.md`

## Model Assignment

| Step | Agent | Model |
|------|-------|-------|
| Step 0-1 | Discovery / batching | orchestrator/parent |
| Step 2 | Group agents (batch review) | **sonnet** |
| Step 3 | Consolidation | **sonnet** |
| `--rule` single rule | Full deep review | **opus** |

## Invocation

```
/kspm-board --all                                   # all rules (parallel by domain group)
/kspm-board --domain rbac                            # single domain
/kspm-board --rule kspm_rule_cluster_admin_binding   # single rule deep review (opus)
```

## Output (in-place under policies/kspm/)

```
policies/kspm/
  {domain}/{rule_id}.json          ← improved rule (in-place update)
  tests/{rule_id}_tests.json        ← fixtures (8 TP + 6 TN + evasion for REWORK; 3+3 kept for APPROVED)
  changes/{rule_id}_changes.md      ← what changed, why
  changes/BATCH_{group}_scores.json ← per-rule scores
  changes/CROSS_RULE_{group}.md     ← cross-rule consistency
  REVIEW_SUMMARY.md                 ← cross-domain findings
```

---

## Step 0 — Discovery and Batching

```bash
find policies/kspm -name "kspm_rule_*.json" -not -path "*/tests/*" | sort > /tmp/kspm_board_all_rules.txt
TOTAL=$(wc -l < /tmp/kspm_board_all_rules.txt | tr -d ' ')
echo "Total KSPM rules to review: $TOTAL"
mkdir -p policies/kspm/changes policies/kspm/tests
```

Filter: skip files with `test_suite_version`; skip files whose `entity_type` != `kspm_rule`.

## Step 0.5 — Inputs Verification (REQUIRED — use these, NOT training knowledge)

```bash
test -f research/kspm/research_cache/kspm_unified_index.json || echo "BLOCKED: run /startup:research kspm first"
test -f research/kspm/research_cache/kspm_fact_registry.json  || echo "BLOCKED: fact registry missing"
```

| Input | Role |
|-------|------|
| `research/kspm/research_cache/kspm_unified_index.json` | vendor/OSS check coverage per domain (Kubescape, Trivy, Checkov, kube-bench, Wiz, Prisma, Aqua, Datadog, Sysdig) |
| `research/kspm/research_cache/kspm_fact_registry.json` | the closed set of legal `posture_predicates` fact paths — any leaf field NOT here is a hard blocker |
| `research/kspm/policies/00-catalog-overview.md` | the 12-domain catalog target (for coverage-gap detection) |
| `.claude/agents/rule_board/kspm/KSPM_RULE_AUTHORING_STANDARDS.md` | schema + §6 hard blockers |

Group agents load these ONCE per batch and use dict lookups — no web search, no training knowledge.

## Step 1 — Assign Rules to Groups by K8s Domain

| Group | Domains | ~Rules |
|-------|---------|-------:|
| **G1 — Workload** | `rbac/` + `pod_security/` + `workload_config/` | ~58 |
| **G2 — Network & Admission** | `network_policy/` + `admission_control/` + `multi_tenancy/` | ~23 |
| **G3 — Control Plane** | `control_plane/` + `kubelet/` + `secrets/` | ~38 |
| **G4 — Supply Chain & Audit** | `supply_chain/` + `logging_audit/` + `compliance/` | ~23 |

## Step 2 — Spawn Group Agents in PARALLEL (sonnet)

```
Agent prompt (per group):
"You are running the KSPM Rule Quality Board for group {GROUP} (domains: {DOMAINS}).

INPUTS (load ONCE, use for ALL rules — NOT training knowledge):
  research/kspm/research_cache/kspm_fact_registry.json     (legal fact paths)
  research/kspm/research_cache/kspm_unified_index.json     (vendor/OSS coverage)
  research/kspm/policies/00-catalog-overview.md            (catalog target for this group's domains)
  .claude/agents/rule_board/kspm/KSPM_RULE_AUTHORING_STANDARDS.md  (schema + §6 hard blockers)

PROTOCOL (everything is in this prompt — do NOT read other agent .md files except the standards):
For each rule in policies/kspm/{domain}/kspm_rule_*.json:
1. Read rule → id, domain, rule_type, target_resource_kind, severity.
2. HARD-BLOCKER scan (standards §6) — REWORK-MAJOR if any:
   B1 every posture_predicates leaf field ∈ fact_registry  (else unregistered fact)
   B2 modality correct  (audit-only concept must not be a posture leaf; static config must not be behavioral-only)
   B3 suppression present where FP-prone  (exemption_refs/baseline_refs/allowlist_refs, not inline lists)
   B4 control_plane/kubelet/etcd-encryption rules carry applies_to:[self_managed]
   B5 compliance anchor present  (cis_benchmark recommendation OR source_check_refs; behavioral → mitre)
   B6 no inline namespace/SA/registry lists in conditions
   B7 severity calibrated  (no critical for a hardening gap; corpus critical ≤ 25%)
3. Vendor/OSS lookup → confirm the rule maps to a real check ID in kspm_unified_index.json; note parity gaps.
4. Score → 7 dimensions (below). Verdict: ≥4.0→APPROVED(1 line) · 3.5-4.0→REWORK-MINOR · <3.5→REWORK-MAJOR.
5. Improve REWORK rules IN PLACE; expand their fixtures to 8 TP + 6 TN + 3 evasion in policies/kspm/tests/.
6. Write changes to policies/kspm/changes/{rule_id}_changes.md (REWORK only).
7. Write policies/kspm/changes/BATCH_{GROUP}_scores.json: [{rule_id, score_pre, score_post, verdict, blockers:[...]}].

Coverage-gap pass: compare this group's rules to the catalog target (00-catalog-overview.md) and list any
catalog check with NO rule. Write to changes/CROSS_RULE_{GROUP}.md."
```

## Step 2b — Quality Gate Verification

```python
import json, os
for g in ['G1','G2','G3','G4']:
    sf = f'policies/kspm/changes/BATCH_{g}_scores.json'
    if not os.path.exists(sf): print(f'BLOCKED: {g} score file missing'); continue
    for r in json.load(open(sf)):
        if r.get('score_post', r.get('score', 0)) < 4.0:
            print(f"QUALITY GATE: {r['rule_id']} at {r.get('score_post')}/5")
```

Then re-run `python3 tests/kspm_corpus_validation_test.py` — must stay 13/13.

## Step 3 — Consolidation

Spawn the shared consolidator (`rule_board_consolidator.md`) to produce `policies/kspm/REVIEW_SUMMARY.md`:
cross-domain severity consistency, posture/behavioral modality drift, **fact-registry closure** (rebuild
`kspm_fact_registry.json` from the post-board corpus; flag any new facts), and catalog coverage gaps.

## Step 4 — Final Report

```
KSPM Rule Quality Board Complete
═══════════════════════════════════════════════════════
Rules reviewed:      N
  APPROVED:          N
  REWORK-MINOR:      N
  REWORK-MAJOR:      N
  WRONG-MODALITY:    N   (posture authored as behavioral-only or vice-versa)
Score improvement:   pre N.N/5 → post N.N/5
Domain coverage:     12 domains, N catalog gaps remaining
Hard blockers fixed: B1..B7 counts
═══════════════════════════════════════════════════════
```

---

## 7 Evaluation Dimensions (KSPM-specific)

| # | Dimension | Weight | What It Measures |
|---|-----------|--------|------------------|
| 1 | **CIS/Fact Accuracy** | 2× | Correct CIS v1.12.0 recommendation ID; every posture leaf field registered + correctly typed |
| 2 | **FP Risk** | 2× | System-namespace / managed-cluster / IaC FP rate; suppression refs; unknown-fact safety |
| 3 | **Modality & Evasion Resistance** | 1.5× | Posture vs behavioral correct; alternative manifests (Deployment/CronJob wrappers), API-version variants |
| 4 | **Vendor Parity** | 1.5× | Maps to a real Kubescape/Trivy/Checkov/kube-bench/commercial check? Cross-domain consistency? |
| 5 | **Compliance Mapping** | 1× | CIS K8s, NSA/CISA, NIST 800-190, PSS level, ATT&CK Containers correctly cited |
| 6 | **Severity Calibration** | 1× | Blast radius × velocity; critical reserved for one-step cluster compromise/host escape |
| 7 | **Posture Soundness / Ops** | 1× | target_resource_kind correct; remediation is a concrete kubectl/flag fix; triage clarity |

**Score = weighted_sum / 50 × 5 = N.N/5**

## Hard Blockers (= REWORK-MAJOR) — standards §6

- `posture_predicates` leaf references a `field` not in `kspm_fact_registry.json`
- Audit-only concept (deletion/actor) authored as a posture leaf, or static config authored behavioral-only
- FP-prone rule with no `exemption_refs`/`baseline_refs`/`allowlist_refs`
- control_plane / kubelet / etcd-encryption rule missing `applies_to: ["self_managed"]` (false-fires on EKS/GKE/AKS)
- No `cis_benchmark` recommendation and no `source_check_refs` (behavioral rules: no `mitre`)
- Inline namespace / service-account / registry list copied into conditions
- `severity: critical` on a hardening gap, or corpus over the 25% critical cap
