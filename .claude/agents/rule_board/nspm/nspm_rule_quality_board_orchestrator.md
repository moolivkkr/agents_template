# /nspm-board — NSPM Rule Quality Board Orchestrator

Reviews `nspm_rule` files for framework accuracy, fact-vocabulary soundness, posture-vs-
behavioral **modality**, **scope-boundary discipline** (no CSPM/KSPM duplication), false-
positive risk (management networks, intended exceptions), compliance mapping, and severity.

**Quality standard:** every rule exits with projected post-improvement score ≥ 4.0/5.

**Specialists (7 lenses, applied inline per rule — group agents do NOT spawn sub-agents):**
- **Framework Accuracy** — the control maps to a real NIST 800-41/207/125B/77, PCI §1, CIS, or MANRS section.
- **Fact Soundness** — every `posture_predicates` leaf field is in the registry, correctly typed, correct quantifier; modality is right.
- **Scope Boundary** — the rule is network-device/fabric or cross-environment segmentation, NOT a cloud-SG/NACL/VPC (→CSPM) or k8s NetworkPolicy (→KSPM) check.
- **FP Risk** — management/OOB networks, intended exceptions, break-glass accounts handled via `exemption_refs`/`baseline_refs`.
- **Modality & Evasion** — posture config vs behavioral event correct; TNs cover realistic compliant/exception shapes.
- **Compliance** — `compliance_frameworks` cite the grounded anchor; `source_check_refs` cite vendor/benchmark.
- **Severity** — calibrated; critical ≤ 25%.

**Group agent:** `.claude/agents/rule_board/nspm/nspm_board_group_agent.md`

## Model Assignment
| Step | Agent | Model |
|---|---|---|
| Step 0-1 | Discovery / batching | orchestrator/parent |
| Step 2 | Group agents (batch review) | **sonnet** |
| Step 3 | Consolidation | **sonnet** |

## Output (in-place under policies/nspm/)
- improved rule JSON (REWORK only, edited in place)
- `policies/nspm/tests/{rule_id}_tests.json` — fixtures (8 TP + 6 TN + evasion for REWORK)
- `policies/nspm/changes/{rule_id}_changes.md` — REWORK change docs
- `policies/nspm/changes/BATCH_{group}_scores.json` — per-rule scores
- `policies/nspm/changes/CROSS_RULE_{group}.md` — cross-rule consistency + coverage gaps

## Step 0 — Discovery and Batching
Glob `policies/nspm/**/nspm_rule_*.json` (exclude `/tests/`, `/changes/`). Group by domain.

## Step 0.5 — Inputs Verification (REQUIRED — use these, NOT training knowledge)
```bash
test -f research/nspm/research_cache/nspm_fact_registry.json || echo "BLOCKED: fact registry missing"
test -f research/nspm/research_cache/nspm_unified_index.json || echo "BLOCKED: unified index missing"
```
| Input | Role |
|---|---|
| `research/nspm/research_cache/nspm_fact_registry.json` | the closed set of legal fact paths — any leaf field NOT here is a hard blocker (B1) |
| `research/nspm/research_cache/nspm_unified_index.json` | domain → fact coverage; vendor/framework parity |
| `research/nspm/policies/00-catalog-overview.md` | catalog target per domain (coverage gaps) |
| `.claude/agents/rule_board/nspm/NSPM_RULE_AUTHORING_STANDARDS.md` | schema + the 3 non-negotiables + hard blockers |

Group agents load these ONCE per batch and use dict lookups — no web search, no training knowledge.

## Step 1 — Assign Rules to Groups (4 groups)
- **G1 perimeter** — firewall_policy, perimeter_exposure
- **G2 segmentation** — segmentation_microseg, ztna
- **G3 device** — mgmt_plane, device_hardening, nac_8021x
- **G4 transport** — vpn_ipsec, routing_bgp, dns_dhcp, compliance

## Step 2 — Spawn Group Agents in PARALLEL (sonnet)
Each loads the inputs + `nspm_board_group_agent.md` protocol, reviews its rules (batch 40),
applies the hard-blocker scan + 7-dimension scoring, improves REWORK rules in place, writes
`BATCH_{GROUP}_scores.json`.

## Step 2b — Quality Gate Verification
Every rule must have `score_post ≥ 4.0` and `blockers` resolved. Re-run any group with a
sub-4.0 rule. Re-run `tests/nspm_corpus_validation_test.py` — must stay PASS.

## Step 3 — Consolidation (sonnet)
Cross-domain severity parity (same risk → same severity), modality-drift audit, **scope-
boundary audit** (flag any rule that should move to CSPM/KSPM), fact-registry closure
(every fact used is registered), catalog coverage gaps. Write `changes/REVIEW_SUMMARY.md`.

## Step 4 — Final Report
Totals, score distribution (pre/post), blockers fixed, modality split, critical%, coverage
gaps, and any rules recommended for relocation to CSPM/KSPM.
