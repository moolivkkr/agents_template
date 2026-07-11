# AI Security Rule Authoring Standards
# Derived from board review of 18 Elastic-derived rules (all REWORK-MAJOR)
# Version: 2.0 — apply to ALL new ai_security_rule, cspm_rule, ciem_rule authoring

## Critical Fixes From Board Review (Systemic Defects Found)

### DEFECT 1: Wrong event_type (caused 100% zero-detection on 13/18 rules)
NEVER default event_type to LLMAuditLog for non-inference events.

| Detection vector          | Correct event_type              |
|---------------------------|---------------------------------|
| AWS CloudTrail API calls  | CloudTrail                      |
| Azure Resource Manager    | AzureActivity / AzureAuditLog   |
| GCP audit log             | GCPAuditLog / GCPModelArmorLog  |
| LLM inference monitoring  | LLMAuditLog                     |
| Network connection        | NetworkConnection               |
| Process execution         | ProcessCreate                   |
| Billing / cost signals    | AIBillingLog                    |
| DNS resolution            | DnsQueryRequest                 |

### DEFECT 2: Enrichment fields in AND conditions (gated detection)
Fields that may not be present on every event MUST NOT appear in AND condition branches.
They belong ONLY in the `enrichment_fields` array.

BAD:
```json
{ "field": "ai.request.user", "operator": "eq", "value": "..." }   // IN conditions
```
GOOD:
```json
"enrichment_fields": ["ai.request.user", "ai.request.session_id"]  // metadata only
```

Rule: if the field is absent ~30%+ of the time, it is an enrichment field, not a gate.

---

## Required Rule Structure (all fields mandatory)

```json
{
  "entity_type": "ai_security_rule",
  "id": "ai_security_rule_<provider>_<threat>",
  "name": "<Provider> <Threat Description> Detected",
  "version": "1.0",
  "review_pipeline": "ai_security_board_v2",
  "board_verdict": "APPROVED | REWORK-MINOR | REWORK-MAJOR",
  "board_score_pre": <float>,
  "board_score_post": <float>,

  "description": "<What it detects>. COVERAGE LIMITATION: <what it misses and why>. See companion rules.",

  "owasp_llm": "LLM01.1",
  "owasp_llm_description": "<short description of the OWASP LLM category>",
  "owasp_llm_gap": "<what this rule does NOT cover — explicit>",

  "mitre_atlas": [
    { "technique_id": "AML.T0051", "technique_name": "...", "tactic": "..." }
  ],

  "blast_radius": "low | medium | high | high_to_critical | critical",
  "blast_radius_note": "<specific conditions that change blast radius>",

  "coverage_notes": {
    "<coverage_dimension>": "<% of deployments affected, bypass rates, documented gaps>"
  },

  "rule_type": "behavioral",
  "behavioral": {
    "event_type": "<CORRECT type per table above — never default LLMAuditLog>",
    "condition": {
      "operator": "OR",
      "branches": [
        {
          "name": "branch_1_<primary_signal>",
          "description": "<what this branch detects>",
          "logic": "AND",
          "conditions": [
            { "field": "<exact field path>", "operator": "eq|in|gt|contains", "value": "...", "comment": "<why this field>" }
          ]
        },
        {
          "name": "branch_2_behavioral_fallback",
          "description": "Non-signal-dependent fallback — fires even when primary guardrail/filter not configured",
          "logic": "AND",
          "conditions": [...]
        },
        {
          "name": "branch_3_<bypass_or_anomaly>",
          "description": "<bypass detection or anomaly>",
          "logic": "AND",
          "conditions": [...]
        }
      ]
    },
    "enrichment_fields": [
      "<fields for analyst context — NOT in condition branches>"
    ]
  },

  "severity": "low | medium | high | critical",
  "severity_escalation": {
    "condition": "<specific field condition that raises severity>",
    "escalated_severity": "critical",
    "escalated_response": ["alert", "notify_soc", "isolate_ai_application", "revoke_session", "create_p1_incident"],
    "rationale": "<why this condition makes it critical>"
  },

  "enabled": true,
  "platform": "saas",
  "tags": ["<provider>", "<threat>", "ai-security", "owasp-llmXX.X", "mitre-atlas-aml-tXXXX", "T<ATTACK>"],

  "mitre": [
    { "tactic_id": "TA0XXX", "tactic_name": "...", "technique_id": "T1XXX", "technique_name": "...", "note": "Secondary. Primary: MITRE ATLAS." }
  ],

  "response": {
    "mode": "detect",
    "severity": "<same as top-level severity>",
    "actions": ["alert", "notify_soc", "create_ticket", "terminate_active_session"],
    "note": "<escalation note referencing severity_escalation condition>"
  },

  "scope": { "channels": ["ai_service"] },

  "sensor_map": {
    "endpoint_windows":  { "enabled": false },
    "endpoint_macos":    { "enabled": false },
    "endpoint_linux":    { "enabled": false },
    "cloud_workload":    { "enabled": false },
    "container_runtime": { "enabled": false },
    "network_sensor":    { "enabled": false },
    "ai_service": {
      "enabled": true,
      "mode": "detect",
      "event_source": "<CloudTrail|GCPAuditLog|AzureAuditLog|LLMAuditLog>",
      "log_sources": ["<specific log stream>"],
      "actions": ["alert", "notify_soc", "create_ticket", "terminate_active_session"]
    }
  },

  "companion_rule_refs": [
    {
      "rule_id": "<companion_rule_id>",
      "type": "cspm_rule | ciem_rule | ai_security_rule | edr_rule | cwp_rule",
      "priority": "P0 | P1 | P2",
      "gap": "<what gap this companion closes>",
      "authored": true | false
    }
  ],

  "cross_system_coverage": {
    "edr_variant": "<edr_rule_id if authored>",
    "cwp_variant": "<cwp_rule_id if authored>",
    "siem_variant": "<this rule>"
  }
}
```

---

## Branch Design Principles

### Minimum 3 branches required
1. **Primary signal branch** — fires when the AI platform's built-in filter/guardrail is configured and detects the threat
2. **Behavioral fallback branch** — fires independently of any guardrail configuration (rate anomaly, behavioral baseline, CloudTrail API event). Must NOT depend on guardrail being enabled.
3. **Bypass/passthrough detection branch** — detects when the guardrail is disabled, in passthrough mode, or being actively probed

### Branch independence requirement
Each branch MUST be able to fire independently. An AND across branches defeats the purpose of multi-branch detection.

### Provider-specific field paths (use exact paths)

**AWS Bedrock:**
- `ai.bedrock.guardrail.prompt_attack.action` → "BLOCKED" | "DETECTED"
- `ai.bedrock.guardrail.action_mode` → "PASSTHROUGH" | "BLOCK"
- `aws.cloudtrail.event_name` → "InvokeModel" | "UpdateGuardrail" | "DeleteGuardrail"
- `aws.caller_identity.arn` → IAM principal
- `ai.bedrock.model_id` → model identifier

**Azure OpenAI:**
- `azure.openai.content_filter.prompt_attack.action` → "filtered" | "flagged"
- `azure.activity.operation_name` → "Microsoft.CognitiveServices/accounts/deployments/write"
- `azure.openai.document_attack.detected` → true/false (indirect injection classifier)
- `azure.resource.subscription_id` → scope identifier

**GCP Vertex AI / Model Armor:**
- `gcp.proto_payload.response.sanitization_result.filter_results.pi_and_jailbreak.filter_match_state` → "MATCH_FOUND"
- `gcp.proto_payload.response.sanitization_result.filter_results.malicious_uris.filter_match_state` → "MATCH_FOUND"
- `gcp.proto_payload.response.sanitization_result.filter_results.sdp.filter_match_state` → "MATCH_FOUND"
- `gcp.method_name` → "google.cloud.modelarmor.v1.ModelArmor.SanitizeUserPrompt"
- `gcp.method_name` → "google.cloud.aiplatform.v1.PredictionService.GenerateContent"
- `gcp.auth_info.principal_email` → GCP identity
- `gcp.vertex_ai.reasoning_engine_id` → Vertex AI Agent Builder identifier

---

## Severity Escalation Conditions

| Condition | Baseline → Escalated |
|-----------|---------------------|
| Agentic deployment with tool access | high → critical |
| New principal (< 48h old API key) + anomalous rate | medium → high |
| Production environment (vs dev/test) | medium → high |
| Unmanaged device / non-corporate IP | high → critical |
| Projected cost > $10K/day (denial of wallet) | high → critical |
| Multiple consecutive filter bypasses (>3 in 10 min) | high → critical |

---

## CSPM Companion Rule Requirement

Every ai_security_rule with a guardrail/filter dependency MUST have companion CSPM rules for:
1. **The guardrail/filter not being configured at all** (P0) — would cause zero detections
2. **The required audit log being disabled** (P0) — would cause zero detections
3. **Overprivileged IAM permission enabling attacker to disable the guardrail** (P0/P1)

If these CSPM rules don't exist yet, add them as `"authored": false` companions.

---

## Per-System Telemetry Principle

For threats that span multiple detection systems, create separate rule variants:
- `ai_security_rule_*` → SIEM/cloud audit log telemetry (CloudTrail, GCP Audit, Azure Monitor)
- `edr_rule_*` → Endpoint agent telemetry (ProcessCreate, NetworkConnection, DnsQueryRequest from endpoint)
- `cwp_rule_*` → Container/K8s runtime telemetry (Falco syscalls, K8s API audit)

Each variant's `sensor_map` MUST explicitly disable sensors it does not own.
Set `cross_system_coverage` field to link all variants.

---

## Quality Gate Checklist (run before marking authored: true)

- [ ] `event_type` matches the actual log source (not defaulted to LLMAuditLog)
- [ ] No enrichment fields in AND condition branches
- [ ] Minimum 3 branches, each independently detectable
- [ ] Branch 2 does NOT depend on guardrail/filter being enabled
- [ ] `coverage_notes` documents bypass rates and % of deployments at risk
- [ ] `owasp_llm_gap` explicitly states what is NOT covered
- [ ] `severity_escalation` has specific field condition (not vague)
- [ ] CSPM companion rules referenced for each guardrail dependency
- [ ] `sensor_map` has explicit false for all non-applicable sensors
- [ ] `enrichment_fields` has ≥6 analyst-context fields
- [ ] Provider field paths use exact schema paths (not generic names)
- [ ] `board_score_post` ≥ 4.0 (REWORK-MAJOR below this threshold)
