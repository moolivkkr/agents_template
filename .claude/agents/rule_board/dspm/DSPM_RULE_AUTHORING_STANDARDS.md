# DSPM Posture Rule Authoring Standards
# Derived from the DSPM posture-policy catalog (research/dspm/policies/) + board review findings
# Version: 1.0

## Scope

Applies to every `posture_rule` entity (composer-authored DSPM posture detections compiled to
`policies/dspm/`, loaded by `../dspm_engine/internal/posture/rules`). A posture rule is a
**sensitivity gate ANDed with a predicate tree over asset facts** — NOT an event/API detection
(that's CSPM/SIEM/EDR). If a rule reasons about a log event, an API call, or a process, it is the
WRONG LAYER.

Authoritative references:
- Policy catalog + IDs: `research/dspm/policies/00-catalog-overview.md` (+ `14-gap-fill-consolidation.md`)
- Fact vocabulary (the ONLY allowed predicate fields): `00-catalog-overview.md §2` + `14 §2`
- Entity/schema design: `docs/design/dspm-posture-rules/entity-model.md`
- Engine schema: `../dspm_engine/internal/posture/rules/rule.go`

## The posture_rule shape

```json
{
  "entity_type": "posture_rule",
  "id": "prule_public_sensitive",
  "name": "Sensitive data publicly exposed",
  "enabled": true,
  "tenant_id": "compliance_library",
  "target_asset_kind": "store",                 // store|schema|table|column (§ sub-asset)
  "detection_refs": [],                          // optional classifier bindings
  "sensitivity_predicate": { "tier_in": ["Restricted", "Confidential"] },
  "posture_predicates": {                         // all|any|not tree of {field, op, value}
    "all": [ { "field": "exposure.is_public", "op": "eq", "value": true } ]
  },
  "issue_type": "PublicExposure",
  "severity_tiers": [ { "when": "match", "severity": "critical" } ],
  "suggested_action": "revoke",
  "regulation_refs": [ { "entity_id": "reg_gdpr" } ],
  "channels": ["cloud_discover", "endpoint_discover", "network_discover"]
}
```

## Critical Rules

### 1. Every predicate `field` MUST be a registered posture_fact
No invented fields. Each `field` must exist in the catalog vocabulary (`00 §2` / `14 §2`). Unknown
fields are rejected at parse time by the engine (`allowedFields`). When proposing a genuinely new
fact, it must be added to the registry first, with type/allowed_ops/asset_level/phase/cmdb_source.

### 2. Operator must match the fact's type
- `bool` → `eq`
- `enum`/`string` → `eq`, `in`
- `int`/`float` → `gt`, `lt`, `gte`, `lte`
- `string[]` → `contains`, `in`
- tri-state control presence → `exists` / `is_set`
Wrong op/type pairing (e.g. `gt` on a bool, `in` with a scalar value) is a hard blocker.

### 3. Always gate on sensitivity
A posture rule that fires regardless of sensitivity is noise. `sensitivity_predicate` must be present
and scoped (`tier_in` of Restricted/Confidential, and/or `category_in` for data-category-specific
policies). Firing "unencrypted" on a Public/Internal asset is a false positive by design.

### 4. Mandatory FP guards
Author the relevant suppression facts as `not{}` branches or conjuncts. The universal/most-common:
- `legal.is_on_hold = false` — on EVERY deletion/retention rule (legal hold is the #1 cross-vendor FP)
- `data.is_synthetic = false` and `data.in_sanctioned_store = false` — on environment/hygiene rules
- `exposure.is_intended_public = false` — on public-exposure rules (intentional public assets)
- `retention.is_immutable = false`, `retention.under_statutory_minimum = false` — on retention rules
Missing the category-appropriate FP guard = REWORK.

### 5. Unknown-fact handling: never fire on absent telemetry
Facts can be absent (no collector for that asset). Design so **unknown ⇒ predicate does NOT match**.
Do NOT author a rule whose violation depends on the *absence* of a positive fact unless you use
`exists`/`is_set` explicitly. Example: "unencrypted" must assert `encryption.is_encrypted == false`
(a collected false), not "encryption fact missing." This prevents missing-collector → false violation.

### 6. Two-fact comparisons use the precomputed derived boolean
The engine compares one fact to a literal. Relational checks (age-vs-limit, storage-region-vs-allowed,
subject-vs-storage, prev-vs-current) MUST consume the enrichment-precomputed boolean
(`retention.exceeds_limit`, `location.is_cross_border`, `location.is_in_allowed_regions`,
`location.subject_storage_mismatch`, `replication.target_in_allowed_regions`), NOT raw two-field math
in the rule. Authoring `age_days gt limit_days` as two leaves is wrong — there is no cross-field op.

### 7. Severity tiers: order matters, first match wins
`severity_tiers` is evaluated top-down; the first matching tier wins. A bare
`[{ "when": "match", "severity": "X" }]` is fine for single-severity rules. For value/threshold-scaled
severity, order most-severe first and give each a predicate `when`/`where`. Don't put `match` before a
predicate tier (it short-circuits).

### 8. issue_type, suggested_action, regulation_refs must be valid
- `issue_type` ∈ the catalog issue_type set (`00 §4.2` + `14 §2`). Prefer reusing the consolidated
  types (e.g. one `MissingDataOwner`) over near-duplicates.
- `suggested_action` ∈ {revoke, encrypt, ticket, relocate, delete, archive, quarantine, redact, tag,
  notify_owner, rotate}. Action must fit the issue (don't `encrypt` an over-permission finding).
- `regulation_refs[].entity_id` must reference a real `compliance_regulation` entity (the seed 5 +
  the 13 added: reg_iso27001, reg_nist_800_53, reg_glba, reg_ferpa, reg_fedramp, reg_dpdp, reg_lgpd,
  reg_pipl, reg_doj_eo14117, reg_iso_27701, reg_eu_ai_act, reg_iso_42001, reg_nist_ai_rmf).

### 9. target_asset_kind must match the facts used
A rule using `column.*`/`table.*`/`schema.*` facts must set `target_asset_kind` accordingly. A
store-level rule (`target_asset_kind: store`) may consume roll-up facts (e.g. `table.sensitive_column_count`)
but not column-leaf facts directly. Column/table-level rules are P2 (require the sub-asset model).

### 10. Phase honesty
Tag the rule's effective phase by the highest-cost fact it uses (P0 cheap-config, P1 graph/IdP/HRMS,
P2 lineage/AI-graph/stateful/sub-asset). A P0-labeled rule that secretly needs a graph fact is a
coverage lie — it will silently never fire until P1/P2 lands.

## Severity calibration (DSPM)
- **critical**: sensitive data publicly/anonymously reachable, or special-category/regulated data with
  no protection + broad/external exposure (toxic combination).
- **high**: external/over-broad sharing, unencrypted regulated data, residency/localization violation,
  erasure overdue.
- **medium**: hygiene/governance gaps (no owner, no label, stale), retention breaches without exposure.
- **low**: ROT/minimization debt, duplicate copies, trivial data.
Severity must track **blast radius × data sensitivity × reversibility** — not the rule's category.

## Entity Type Requirements
- `entity_type: "posture_rule"` on every rule file (not a test fixture).
- Stable `id` (prule_*), `tenant_id` (`compliance_library` for built-ins), `enabled`.
- Test fixtures carry `test_suite_version` and are excluded from review counts.

## Model Assignment
- Batch review: sonnet. Single-rule deep review (`--rule`): opus.
