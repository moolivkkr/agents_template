# NSPM Rule Authoring Standards

The contract for every `nspm_rule`. Network Security Posture Management — posture-primary
(network-config scan) with a behavioral companion. Scope: **network-device/fabric +
cross-environment segmentation**. Schema mirrors `kspm_rule` so the composer's posture/
behavioral builders load NSPM rules with zero new work.

## 1. The three non-negotiables

1. **Fact-registry closure (no false positives from invented fields).** Every `field` in a
   predicate MUST be a `fact_path` present in `research/nspm/research_cache/nspm_fact_registry.json`.
   A rule referencing a fact NOT in the registry is INVALID — do not invent fields from
   training knowledge. Use the registry's `value_type` + `ops` for each fact.

2. **Correct type identification (modality).** Set `rule_type` to match the fact's modality
   in the registry:
   - `posture` — config-scan over network-config facts (the default; 232/241 facts). Uses
     `posture_predicates`. Set `posture_check: true`.
   - `behavioral` — a network *event* (config change pushed, route advertised, etc.; 9 facts).
     Uses a `behavioral` block. Do NOT default a config check to behavioral.
   - `hybrid` — both a config-snapshot AND an event companion. `posture_check: true` +
     both blocks. Use sparingly.
   Never label a posture config check as behavioral or vice-versa.

3. **Scope boundary (no duplication of CSPM/KSPM).** NSPM is network-DEVICE/fabric +
   cross-environment segmentation. A rule that is purely a cloud security-group / NACL / VPC
   check belongs in CSPM; a pure k8s NetworkPolicy check belongs in KSPM. Do not author those
   here. (The registry already excludes cloud/k8s-owned facts.)

## 2. Schema (mirror kspm_rule)

```json
{
  "entity_type": "nspm_rule",
  "id": "nspm_rule_<domain>_<short_name>",
  "name": "Human title",
  "description": "What it detects + WHY it matters (the risk).",
  "rule_type": "posture",
  "posture_check": true,
  "domain": "<one of the 11 domains>",
  "platform": "network",
  "target_resource_kind": "firewall_rule | device | zone | vpn_tunnel | switchport | router | resolver",
  "posture_predicates": {
    "all": [ { "leaf": { "field": "<registry fact_path>", "op": "<registry op>", "value": <typed> } } ]
  },
  "issue_type": "CamelCaseIssue",
  "severity_tiers": [ { "when": "match", "severity": "high" } ],
  "suggested_action": "restrict | harden | segment | rotate | ticket | notify",
  "exemption_refs": ["exception_..."],
  "baseline_refs": ["baseline_..."],
  "severity": "critical|high|medium|low",
  "framework_anchor": { "framework": "NIST SP 800-41r1", "section": "§4", "recommendation": "..." },
  "compliance_frameworks": ["NIST 800-41r1 §4", "PCI-DSS v4.0 §1.2", "CIS Controls v8 12.2"],
  "remediation": "Concrete fix.",
  "source_check_refs": ["Tufin:shadowed_rule", "CIS Cisco IOS"],
  "mitre": [ { "tactic_id": "TA0008", "tactic_name": "Lateral Movement", "technique_id": "T1210", "technique_name": "Exploitation of Remote Services" } ],
  "scope": { "channels": ["network_config_scan"] },
  "sensor_map": { "network_sensor": true },
  "tags": ["nspm", "<domain>", "posture"],
  "tests": {
    "true_positives":  [ { "description": "...", "facts": { "<fact_path>": <violating value> }, "expected": "alert" } ],
    "true_negatives":  [ { "description": "...", "facts": { "<fact_path>": <compliant value> }, "expected": "pass" } ]
  }
}
```

Behavioral rules replace `posture_predicates` with:
```json
"behavioral": { "event_type": "NetworkConfigChange", "condition": { "logic": "AND", "conditions": [ { "field": "<fact>", "operator": "eq", "value": ... } ] } }
```

## 3. Predicate + FP discipline

- Predicates are an `all`/`any`/`not`/`leaf` tree; leaf = `{field, op, value}` over registry facts.
- `op` must be one of the fact's registry `ops`; `value` must match the fact's `value_type`
  (bool → true/false, enum → an allowed value, int → number, string_array → list).
- **FP guardrails:** never gate solely on a fact that is absent ~30%+ of the time; for
  behavioral rules, require ≥2 grounding conditions (provider/zone + the signal), never a
  single enrichment field; prefer `exemption_refs`/`baseline_refs` for known-good (management
  networks, intended exceptions) over loosening the predicate.
- Severity calibration: `critical` only for direct exposure/bypass (mgmt-plane to internet,
  any-any permit, default-permit perimeter, weak VPN crypto on remote access). Keep
  `max_critical_pct ≤ 25%`.

## 4. Tests (fact snapshots)

Minimum **8 true-positive** + **6 true-negative** fixtures per rule. Each is a `facts` map
(fact_path → value) that the predicate evaluates over. TPs trip the predicate; TNs are the
realistic compliant/exception shapes (e.g. management network correctly segmented, rule with
a documented owner, IKEv2 + strong DH). Use ONLY registry facts in fixtures.

## 5. Compliance + provenance

- `compliance_frameworks` MUST cite the grounded anchor(s) from the fact's
  `framework_anchor` in the registry (NIST/PCI/CIS/MANRS). ≥1 required.
- `source_check_refs` cite the vendor/benchmark the check came from (research catalogs).

## 6. Output

Write to `policies/nspm/<domain>/nspm_rule_<domain>_<name>.json`, one rule per file.
