# CSPM Rule Authoring Standards
# Derived from board review findings + cloud security best practices
# Version: 1.0

## Scope

These standards govern **cloud security posture management rules** — detecting misconfigurations,
policy violations, and suspicious API calls across AWS, Azure, and GCP.

---

## Critical Rules

### 1. Always gate on `event.outcome: success`

Failed API calls generate noise. An `AccessDeniedException` on `StopLogging` means the attacker
was BLOCKED — alerting on it wastes SOC time.

Exception: brute-force/enumeration rules (threshold on failures).

### 2. Use provider-specific field paths, not bare `event.action`

| Provider | Correct Field | Wrong Field |
|----------|--------------|-------------|
| AWS | `ext.aws.cloudtrail.event_name` | `event.action` alone |
| Azure | `ext.azure.activity.operation_name` | `event.action` alone |
| GCP | `ext.gcp.audit.method_name` | `event.action` alone |

If ingest populates only `event.action` and not the `ext.*` path, document as evasion blind spot.

### 3. Enrichment fields are NOT gates

Fields absent >30% of the time belong in `enrichment_fields`, not in AND conditions:
- `actor.user.arn` / `actor.user.name` (absent in assumed-role sessions)
- `ext.aws.cloudtrail.trail_arn` (absent in organization-level trails)
- `source_reference_id` / `session_id` / `trace_id`

### 4. Document IaC false positive sources

Every CSPM rule must document which IaC tools trigger it:
- **Terraform**: `plan` (read-only, no alert) vs `apply` (mutating, alert)
- **CloudFormation**: stack create/update/delete
- **CDK**: `cdk deploy` via CloudFormation
- **Pulumi**: direct API calls with Pulumi user agent

### 5. Cover alternative APIs (sibling evasion)

Most cloud security actions have 2-3 APIs achieving the same result:

| Security Action | AWS APIs |
|----------------|----------|
| Disable logging | `StopLogging`, `DeleteTrail`, `PutEventSelectors` |
| Escalate privileges | `AttachUserPolicy`, `PutUserPolicy`, `CreatePolicyVersion` |
| Create persistence | `CreateUser`, `CreateAccessKey`, `CreateLoginProfile` |
| Disable security | `DeleteFlowLogs`, `DisableGuardDuty`, `UpdateDetector` |

A rule covering only one API is trivially evaded. Document gaps as companion rules.

### 6. Severity calibration for cloud

| Action Type | Severity | Examples |
|-------------|----------|----------|
| Irreversible security disable | critical | DeleteTrail, DisableGuardDuty, DeleteFlowLogs |
| Reversible security change | high | StopLogging, ModifyDBInstance (public), CreateUser |
| Configuration drift | medium | SecurityGroupIngress, BucketPolicy, IAM policy change |
| Informational / audit | low | DescribeInstances, ListBuckets, GetCallerIdentity |

### 7. Cross-provider parity

Every AWS rule should have an equivalent Azure + GCP rule (where the service exists):

| AWS | Azure | GCP |
|-----|-------|-----|
| CloudTrail | Activity Log | Audit Log |
| GuardDuty | Defender for Cloud | Security Command Center |
| IAM | Entra ID / RBAC | IAM |
| Security Groups | NSG | VPC Firewall Rules |
| S3 | Blob Storage | Cloud Storage |
| KMS | Key Vault | Cloud KMS |

---

## Entity Type Requirements

Every `cspm_rule` MUST have:
- `entity_type: "cspm_rule"`
- `id` matching filename
- `name`, `description`
- `rule_type: "behavioral"` or `"posture_check"`
- `severity: "critical" | "high" | "medium" | "low"`
- `behavioral.event_type` (CloudAPICall, CloudAuditLog, etc.)
- `behavioral.condition` with structured logic/conditions
- `mitre` array with technique_id
- `compliance_frameworks` with benchmark references
- `tags` including provider name
- `response` with mode and actions
- `remediation` with steps

---

## Model Assignment

| Agent | Model |
|-------|-------|
| All group agents | sonnet |
| Consolidator | sonnet |
| Single-rule deep review | opus |
