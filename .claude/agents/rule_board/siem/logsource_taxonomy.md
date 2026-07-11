# SIEM Rule — Log Source Taxonomy

Maps log sources to MITRE techniques and Stage 0 inventory candidates. R0 vendor research
(logsource + technique) runs once per family and is cached in
`policies/siem_reviewed/research_cache/`. Group agents load from cache rather than
regenerating R0 per rule.

**Inventory source of truth:** `agent_state/siem_pipeline/stage_0/consolidated_inventory.json`
(fields: `inventory_id`, `log_source`, `mitre`, `overlap_status`, `elastic_*`, `sigma_*`,
`suggested_siem_rule_id`, `authored_rule_id`, `merged_field_hints`).

**Board specialists per family:** Elastic, Splunk ESCU, Wiz, Palo Alto XSIAM, Prophet (reference), Matano; Sigma (overlap reference).

---

## Log Source → Technique Family Map (Pilot + Planned)

| Log Source | Manifest Key | Event Type | TECH_ID | MITRE (primary) | Rules / Inventory |
|------------|--------------|------------|---------|-----------------|-------------------|
| AWS CloudTrail | `cloud_trail` | `CloudAuditLog` | `TECH_cloud_trail_T1562.008` | T1562.008 Disable Cloud Logs | stop_logging, delete_trail |
| AWS CloudTrail | `cloud_trail` | `CloudAuditLog` | `TECH_cloud_trail_T1530` | T1530 Data from Cloud Storage | put_bucket_policy |
| AWS CloudTrail | `cloud_trail` | `CloudAuditLog` | `TECH_cloud_trail_T1078.004` | T1078.004 Cloud Accounts | create_access_key |

**Planned (not in pilot board groups):**

| Log Source | TECH_ID pattern | Event Type | Notes |
|------------|-----------------|------------|-------|
| `windows_event` | `TECH_windows_event_{technique}` | `WindowsEventLog` | Security 4688/4624/4625 families |
| `azure_activity` | `TECH_azure_activity_{technique}` | `CloudAuditLog` | Activity Log + Entra correlation |
| `gcp_audit` | `TECH_gcp_audit_{technique}` | `CloudAuditLog` | Admin Activity / Data Access |
| `entra_signin` | `TECH_entra_signin_{technique}` | `Authentication` | Sign-in risk + impossible travel |
| `okta_system` | `TECH_okta_system_{technique}` | `ApplicationActivity` | Okta System Log |
| `dns` | `TECH_dns_{technique}` | `DnsQuery` | Resolver / Zeek DNS |
| `proxy` | `TECH_proxy_{technique}` | `NetworkActivity` | Web proxy exfil / C2 |

---

## Detailed Family Definitions

### TECH_cloud_trail_T1562.008 — Disable or Modify Cloud Logs

**Threat summary:** Attacker suspends, deletes, or reconfigures CloudTrail (or equivalent cloud
audit logging) to create an audit visibility gap before destructive, persistence, or exfiltration
activity. Covers StopLogging, DeleteTrail, UpdateTrail logging-disable, PutEventSelectors delivery
tampering, and organization-trail-specific variants.

**Rules in family:**

| rule_id | API / signal | overlap_status | Status |
|---------|--------------|----------------|--------|
| `siem_rule_aws_cloudtrail_stop_logging` | StopLogging + success | both | authored |
| `siem_rule_aws_cloudtrail_delete_trail` | DeleteTrail + success | elastic_only | gap (Stage 2) |
| `siem_rule_aws_cloudtrail_event_selector_tamper` | PutEventSelectors | sigma_only | gap |
| `siem_rule_aws_cloudtrail_update_trail_logging` | UpdateTrail logging disable | sigma_only | gap |

**Inventory entries:**

| inventory_id | overlap_status | suggested_siem_rule_id | authored_rule_id |
|--------------|----------------|------------------------|------------------|
| `inv_cloudtrail_stop_logging` | `both` | `siem_rule_aws_cloudtrail_stop_logging` | `siem_rule_aws_cloudtrail_stop_logging` |
| `inv_cloudtrail_delete_trail` | `elastic_only` | `siem_rule_aws_cloudtrail_delete_trail` | *(null — `--add-missing`)* |

**Key R0 research areas (all 4 specialists):**

- **Elastic SIEM:** `defense_evasion_cloudtrail_logging_suspended.toml` — ECS `event.action` → ext.*;
  risk_score 73; event rule type; investigation guide fields
- **Sigma:** `aws_cloudtrail_disable_logging.yml` — multi-API OR bundle; level medium; SPLIT vs narrow
- **Splunk ESCU:** AWS CloudTrail Log Suspended / Deleted story (stub if repo unavailable)
- **Sentinel:** AWS CloudTrail logging disabled analytic; KQL `EventName=='StopLogging'` (stub OK)
- **MODULE_09:** gate on `ext.aws.cloudtrail.event_name`; outcome=success; class_uid 6003
- **Enrichment vs gate:** trail_arn, identity, request_id in enrichment_fields only (FC-05)

**Provider-specific notes (used in R1 supplements):**

- StopLogging-only rule: intentionally excludes DeleteTrail (companion P0)
- GovCloud trails: `cloud.region` us-gov-* — same API gates apply
- Org trails: member account may stop logging on delegated trail — group_by must include account + trail_arn

**Cache file:** `policies/siem_reviewed/research_cache/cloud_trail_T1562.008_research.md`

---

### TECH_cloud_trail_T1530 — Data from Cloud Storage

**Threat summary:** Attacker modifies S3 bucket policies or ACLs to exfiltrate data or enable public access.

**Inventory entries (planned):** `inv_cloudtrail_put_bucket_policy`

**Key R0 research areas:**

- Elastic: S3 bucket policy change detections under `rules/integrations/aws/`
- Sigma: `aws_s3_*` policy rules; field `eventSource=s3.amazonaws.com`
- MODULE_09: `ext.aws.cloudtrail.event_source` gate + `ext.aws.cloudtrail.event_name`

**Cache file (when authored):** `policies/siem_reviewed/research_cache/cloud_trail_T1530_research.md`

---

### TECH_cloud_trail_T1078.004 — Valid Cloud Accounts

**Threat summary:** Attacker creates access keys or login profiles for persistence in compromised cloud accounts.

**Inventory entries (planned):** `inv_cloudtrail_create_access_key`

**Key R0 research areas:**

- Elastic: IAM access key creation rules; correlate with new user / anomalous principal
- Sigma: `aws_cloudtrail_access_key_created.yml` variants
- Offense: group_by `actor.user.uid` + `cloud.account.id`; severity medium-high

**Cache file (when authored):** `policies/siem_reviewed/research_cache/cloud_trail_T1078.004_research.md`

---

## Rule ID → Technique Family Lookup

| rule_id | TECH_ID | log_source | Cache file |
|---------|---------|------------|------------|
| `siem_rule_aws_cloudtrail_stop_logging` | `TECH_cloud_trail_T1562.008` | `cloud_trail` | `cloud_trail_T1562.008_research.md` |

Add rows as new rules are authored. Group agents resolve TECH_ID via this table or by reading
`mitre[].technique_id` + `scope.log_sources[]` from the rule JSON.

---

## Cache File Locations

Pre-flight research is written to:

```
policies/siem_reviewed/research_cache/
  cloud_trail_T1562.008_research.md   # pilot — seeded
  cloud_trail_T1530_research.md     # when family authored
  cloud_trail_T1078.004_research.md  # when family authored
  windows_event_T1059_research.md   # planned
  azure_activity_T1078_research.md  # planned
```

Each file contains all 4 specialists' complete R0 research blocks for that logsource+technique family.

---

## consolidated_inventory.json Field Reference

| Field | Board use |
|-------|-----------|
| `inventory_id` | Stable candidate key; cited in coverage_index gaps |
| `log_source` | Group assignment (`--scope cloud_trail`) |
| `mitre[].technique_id` | TECH_ID suffix (`T1562.008` → `TECH_cloud_trail_T1562.008`) |
| `overlap_status` | `both` / `elastic_only` / `sigma_only` — must match `source_provenance` |
| `elastic_rule_id`, `elastic_file` | Elastic SIEM specialist R0 |
| `sigma_id`, `sigma_file` | Sigma specialist R0 |
| `merged_field_hints` | MODULE_09 gate field candidates |
| `authored_rule_id` | `null` = gap for `--add-missing` handoff |
| `suggested_siem_rule_id` | Target id for Stage 2 / board authoring |

---

## coverage_index.json

Built by the orchestrator in Step 0:

`agent_state/rule_board/siem/coverage_index.json`

Structure:

```json
{
  "generated_at": "ISO-8601",
  "inventory_version": "from consolidated_inventory.json",
  "authored_rules": ["siem_rule_..."],
  "gaps": [{ "inventory_id": "...", "suggested_siem_rule_id": "...", "overlap_status": "..." }],
  "by_log_source": { "cloud_trail": { "inventory": N, "authored": N, "gaps": N } }
}
```

---

## Cross-reference to AI Security technique_taxonomy

| AI Security pattern | SIEM equivalent |
|--------------------|-----------------|
| TECH_01_prompt_injection (8 families) | TECH_{logsource}_{technique} (per log source) |
| R0 cache once per family | Same — `research_cache/{logsource}_{technique}_research.md` |
| 4 specialists | Elastic, Sigma, Splunk ESCU, Sentinel |
| OWASP LLM mapping | MITRE ATT&CK + OCSF class mapping |
| companion_rule_refs | Same pattern for sibling APIs |
