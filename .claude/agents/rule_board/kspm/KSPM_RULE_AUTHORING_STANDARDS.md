# KSPM Rule Authoring Standards

> The contract for every `kspm_rule`. Shared by the rules-plugin authoring pipeline (Phase B) and the
> KSPM Rule Quality Board (Phase C). Grounded in `research/kspm/` (catalog `policies/00-catalog-overview.md`,
> gap map `12-gaps-and-moats.md`, unified index `research_cache/kspm_unified_index.json`).
>
> **Framework pins:** CIS Kubernetes Benchmark **v1.12.0** · NSA/CISA Hardening Guide **v1.2** ·
> NIST SP 800-190 · Pod Security Standards (Baseline/Restricted) · MITRE ATT&CK Containers.

---

## 0. The core decision — DUAL FORM (posture-primary)

KSPM is a **config-scan posture** product: the `kspm_engine` snapshots live cluster *state* and evaluates
**config facts** (DSPM `posture_predicates` model). It does **not** primarily evaluate audit events.

The existing 39 rules are authored as `rule_type: "behavioral"` over `KubernetesAuditLog` events. We **keep**
that behavioral form (it feeds the SIEM/audit modality and links to `cwp_rule_k8s_*` runtime rules) and
**add a posture form** that the engine consumes. Every rule therefore declares one of:

| `rule_type` | Has `posture` block | Has `behavioral` block | Engine-consumed | When |
|-------------|:---:|:---:|:---:|------|
| `posture`    | ✅ | — | ✅ | Pure config fact (e.g. control-plane flags, file perms) — no audit-event form exists |
| `hybrid`     | ✅ | ✅ | ✅ (posture) | Config fact that ALSO has a meaningful audit-event form (e.g. "cluster-admin binding exists" + "binding was created") |
| `behavioral` | — | ✅ | ❌ | Only meaningful as a live event (e.g. "policy was *deleted*", "actor X did Y") — stays out of the posture bundle |

**Posture bundle = all `posture` + `hybrid` rules.** The ~6 behavioral-only rules (control deletions, actor-context)
are flagged `"posture_check": false` and excluded from the compiled engine bundle.

---

## 1. Rule schema

```jsonc
{
  "entity_type": "kspm_rule",
  "id": "kspm_rule_<domain_slug>",            // snake_case, globally unique, stable
  "name": "<Human title — Resource + Misconfig>",
  "description": "<what it detects, why it matters, attacker use, CIS ref in prose>",

  "rule_type": "posture | hybrid | behavioral",
  "posture_check": true,                       // true for posture|hybrid; false for behavioral-only
  "domain": "rbac | pod_security | network_policy | admission_control | secrets | control_plane | kubelet | supply_chain | workload_config | multi_tenancy | logging_audit | compliance",
  "platform": "kubernetes",

  // ── POSTURE FORM (consumed by kspm_engine) — required when rule_type is posture|hybrid ──
  "target_resource_kind": "pod_workload | role | clusterrole | rolebinding | clusterrolebinding | serviceaccount | networkpolicy | service | namespace | secret | configmap | apiserver | controllermanager | scheduler | etcd | kubelet | control_plane_file | admission_webhook | cluster",
  "posture_predicates": {
    "all": [                                   // all | any | not (nestable, DSPM-compatible)
      { "leaf": { "field": "<fact.path>", "op": "eq|ne|in|not_in|gt|gte|lt|lte|contains|not_contains|exists|not_exists|matches", "value": <v>,
                  "quantifier": "any|all" } }  // quantifier only for list/container facts; default "any"
    ]
  },
  "issue_type": "<StableCamelCaseIssueType>",  // e.g. ClusterAdminBinding, PrivilegedContainer
  "severity_tiers": [ { "when": "match", "severity": "critical|high|medium|low" } ],
  "suggested_action": "revoke | restrict | encrypt | rotate | isolate | patch_config | ticket | notify | tag | quarantine_workload",

  // ── BEHAVIORAL FORM (audit modality) — required when rule_type is hybrid|behavioral ──
  "behavioral": {
    "event_type": "KubernetesAuditLog",
    "condition": { "logic": "AND|OR|NOT", "conditions": [ { "field": "...", "operator": "...", "value": ... } ] }
  },

  // ── SUPPRESSION (data-driven — DO NOT inline these lists) ──
  "exemption_refs": ["exception_infrastructure_namespaces"],          // shared/ files, by id
  "allowlist_refs": ["allowlist_trusted_registries"],
  "baseline_refs":  ["baseline_infrastructure_service_accounts"],

  // ── SHARED METADATA (every rule) ──
  "severity": "critical|high|medium|low",
  "cis_benchmark": { "framework": "CIS Kubernetes Benchmark", "version": "1.12.0", "section": "5.1.1", "recommendation": "<text>" },
  "compliance_frameworks": ["CIS Kubernetes 1.12.0 - 5.1.1", "NSA-CISA - Authentication & Authorization", "NIST 800-190 - 3.4", "PSS - Restricted"],
  "nsa_cisa_domain": "Authentication & Authorization",
  "nist_800_190_risk": "Orchestrator",
  "pss_level": "baseline | restricted | null",
  "remediation": "<concrete kubectl / manifest / flag fix>",
  "source_check_refs": ["Kubescape:C-0035", "Trivy:KSV041", "Checkov:CKV_K8S_49", "kube-bench:5.1.1"],
  "mitre": [ { "tactic_id": "TA0004", "tactic_name": "Privilege Escalation", "technique_id": "T1078", "technique_name": "Valid Accounts" } ],
  "cross_system_coverage": [ { "entity_id": "cwp_rule_k8s_privileged_container", "entity_type": "cwp_rule", "relationship": "runtime_companion" } ],

  "sensor_map": {
    "kubernetes_audit":     { "enabled": <bool>, "mode": "detect", "actions": ["alert","create_ticket"] },
    "cluster_config_scan":  { "enabled": <bool>, "mode": "detect", "actions": ["alert","create_ticket"] },
    "admission_controller": { "enabled": false },
    "kubelet":              { "enabled": false },
    "pod_security":         { "enabled": false }
  },
  "scope": { "channels": ["cluster_config_scan"] },   // posture rules → cluster_config_scan; behavioral → kubernetes_audit
  "enabled": true,
  "tags": ["kspm", "<domain>", "<technique>", "<severity>"]
}
```

---

## 2. K8s config-fact vocabulary (the fact registry)

The posture engine's resource mappers (Phase E) populate these facts from a cluster snapshot. **Authors MUST
use these paths** — new facts must be added to `research/kspm/research_cache/kspm_fact_registry.json` (built in
consolidation) so the engine contract stays closed. Namespacing is by resource kind.

### `pod_workload.*` (Pod, and pods embedded in Deployment/DaemonSet/StatefulSet/Job/CronJob/ReplicaSet)
`pod_workload.kind`, `.namespace`, `.host_network`(bool), `.host_pid`(bool), `.host_ipc`(bool),
`.share_process_namespace`(bool), `.automount_sa_token`(bool), `.service_account_name`(str),
`.has_controller`(bool), `.liveness_probe_set`(bool), `.readiness_probe_set`(bool),
`.host_path_volumes`(list<str> paths), `.docker_socket_mounted`(bool), `.host_ports`(list<int>),
`.volume_types`(list<str>), `.uses_default_sa`(bool)

### `container.*` (per-container; evaluate with `quantifier`)
`container.privileged`(bool), `.allow_privilege_escalation`(bool), `.run_as_user`(int|null),
`.run_as_non_root`(bool), `.read_only_root_fs`(bool), `.added_capabilities`(list<str>),
`.dropped_capabilities`(list<str>), `.drops_all`(bool), `.seccomp_profile`(str: RuntimeDefault|Localhost|Unconfined|unset),
`.apparmor_profile`(str), `.selinux_options_set`(bool), `.proc_mount`(str), `.has_security_context`(bool),
`.cpu_limit_set`(bool), `.cpu_request_set`(bool), `.memory_limit_set`(bool), `.memory_request_set`(bool),
`.image`(str), `.image_registry`(str), `.image_tag`(str), `.image_pinned_by_digest`(bool),
`.image_pull_policy`(str), `.secret_env_refs`(list<str>), `.unsafe_sysctls`(list<str>)

### `rbac.*` (Role/ClusterRole) & `binding.*` (RoleBinding/ClusterRoleBinding)
`rbac.kind`, `rbac.has_wildcard_verb`(bool), `rbac.has_wildcard_resource`(bool), `rbac.has_wildcard_apigroup`(bool),
`rbac.verbs`(list), `rbac.resources`(list), `rbac.api_groups`(list), `rbac.grants_secrets_all_ns`(bool),
`rbac.grants_escalate`(bool), `rbac.grants_bind`(bool), `rbac.grants_impersonate`(bool),
`rbac.grants_pods_exec`(bool), `rbac.grants_pods_portforward`(bool), `rbac.grants_pv_create`(bool),
`rbac.grants_nodes_proxy`(bool), `rbac.manages_rbac`(bool), `rbac.manages_configmaps`(bool),
`binding.role_ref_name`(str), `binding.role_ref_kind`(str), `binding.is_cluster_admin`(bool),
`binding.subject_kinds`(list), `binding.subject_names`(list), `binding.subject_namespaces`(list),
`binding.has_anonymous_subject`(bool), `binding.has_system_masters`(bool), `binding.has_default_sa_subject`(bool),
`binding.subject_is_user`(bool)

### `networkpolicy.*` & `service.*`
`networkpolicy.allows_all_ingress`(bool), `.allows_all_egress`(bool), `.egress_to_internet`(bool),
`.restricts_dns`(bool), `.applies_to_namespace`(str), `.cross_namespace_selector`(bool);
`service.type`(str), `service.is_public_lb`(bool), `service.is_nodeport`(bool)

### `namespace.*`
`namespace.name`, `namespace.has_network_policy`(bool), `namespace.pss_enforce_label`(str: privileged|baseline|restricted|none),
`namespace.has_resource_quota`(bool), `namespace.has_limit_range`(bool), `namespace.is_default`(bool),
`namespace.is_system`(bool)

### `apiserver.*`, `controllermanager.*`, `scheduler.*`, `etcd.*` (control-plane flags)
`apiserver.anonymous_auth`(bool), `.authorization_modes`(list<str>), `.insecure_port`(int),
`.profiling`(bool), `.audit_log_path`(str|empty), `.encryption_provider_config_set`(bool),
`.encryption_provider`(str: aesgcm|aescbc|kms|identity|none), `.admission_plugins`(list<str>),
`.tls_cipher_suites`(list<str>), `.token_auth_enabled`(bool), `.basic_auth_enabled`(bool),
`.audit_log_maxage`(int), `.audit_log_maxbackup`(int), `.audit_log_maxsize`(int);
`controllermanager.use_sa_credentials`(bool), `.rotate_kubelet_server_cert`(bool), `.profiling`(bool), `.bind_address`(str);
`scheduler.profiling`(bool), `.bind_address`(str);
`etcd.cert_file_set`(bool), `.key_file_set`(bool), `.client_cert_auth`(bool), `.auto_tls`(bool),
`.peer_client_cert_auth`(bool), `.peer_auto_tls`(bool), `.unique_ca`(bool)

### `kubelet.*`
`kubelet.anonymous_auth`(bool), `.authorization_mode`(str), `.client_ca_file_set`(bool),
`.read_only_port`(int), `.streaming_connection_idle_timeout`(str), `.make_iptables_util_chains`(bool),
`.rotate_certificates`(bool), `.rotate_server_certificate`(bool), `.tls_cipher_suites`(list), `.seccomp_default`(bool)

### `control_plane_file.*` (PKI / config file perms — CIS §1.1, §4.1)
`control_plane_file.path`(str), `.permissions`(str octal), `.owner`(str), `.group`(str)

### `cluster.*`, `secret.*`, `configmap.*`, `admission.*` (cross-cutting)
`cluster.etcd_encryption_enabled`(bool), `cluster.audit_logging_enabled`(bool), `cluster.kubelet_version`(str),
`cluster.has_external_secret_store`(bool), `cluster.dashboard_deployed`(bool), `cluster.tiller_deployed`(bool),
`cluster.uses_deprecated_api`(bool);
`secret.type`(str), `secret.mounted_unused`(bool);
`configmap.contains_credentials`(bool), `configmap.contains_secret_data`(bool);
`admission.image_signature_verification`(bool), `admission.allowed_registries_policy`(bool),
`admission.validating_webhook_failure_policy`(str), `admission.has_image_provenance_gate`(bool)

> Use `op: exists/not_exists` for "flag set/unset". For "any container violates", set `quantifier: any`.
> When a fact is **unknown** (mapper could not populate it — e.g. control-plane flags on a managed EKS/GKE/AKS
> cluster), the engine treats the leaf as **non-matching** (no false positive). Rules whose entire meaning
> depends on self-managed control plane MUST carry `"applies_to": ["self_managed"]` so managed clusters skip them.

---

## 3. Suppression — data-driven, never inline

Three shared files already exist in `policies/kspm/shared/`:
- `allowlist_trusted_registries.json` (trusted image registries)
- `exception_infrastructure_namespaces.json` (kube-system, etc.)
- `baseline_infrastructure_service_accounts.json` (system SAs)

Rules **reference** them via `allowlist_refs` / `exemption_refs` / `baseline_refs` (by `id`). **Do not** copy
the lists into rule conditions. The engine resolves refs at load and applies them as negative predicates.
Where a behavioral form still needs an inline list for the audit path, keep it minimal and mirror the shared file.

---

## 4. Severity calibration (K8s blast radius × velocity)

| Severity | Rule of thumb | Examples |
|----------|---------------|----------|
| **critical** | Cluster-wide compromise or host escape, one step | cluster-admin binding, privileged+hostPath, anonymous apiserver auth, etcd unencrypted |
| **high** | Namespace compromise / lateral movement / escape primitive | hostNetwork, wildcard RBAC, secrets-all-ns, allow-all-ingress, kubelet anonymous-auth |
| **medium** | Hardening gap, needs chaining | missing seccomp, no resource limits, default namespace, missing probes |
| **low** | Hygiene / best practice | missing labels, no PDB, no priorityClass |

Cap: **≤ 25% of the corpus may be `critical`** (mirror CSPM `max_critical_pct`). Workload-hardening
(`workload_config`) rules are medium/low unless they enable escape.

---

## 5. Test fixtures (per rule)

Each rule ships fixtures in `policies/kspm/tests/<rule_id>_tests.json`:
- **≥ 8 true-positives**: the violating config across resource kinds (raw Pod *and* its Deployment/CronJob
  wrapper), IaC-rendered (Helm/Kustomize) variants.
- **≥ 6 true-negatives**: the compliant config, the suppressed case (system namespace / trusted registry /
  baseline SA), managed-cluster skip (for self-managed-only rules), wrong-kind negative.
- For `hybrid` rules: include **both** a posture-snapshot fixture (resource manifest → facts) and an
  audit-event fixture (`KubernetesAuditLog` record).

---

## 6. Hard blockers (board REJECT — Phase C)

1. **Fact not registered** — a `posture_predicates` leaf references a `field` not in the fact vocabulary (§2) / registry.
2. **Wrong modality** — an audit-only concept (deletion, actor) authored as a posture leaf, or a static config
   fact authored only as behavioral when a posture form exists.
3. **No suppression** — a rule prone to system-namespace/infra FPs with no `exemption_refs`/`baseline_refs`/`allowlist_refs`.
4. **Self-managed FP** — a control-plane/kubelet/etcd rule without `"applies_to": ["self_managed"]` (would false-fire on EKS/GKE/AKS).
5. **Missing compliance anchor** — no `cis_benchmark` recommendation ID and no `source_check_refs`.
6. **Inline suppression list** — namespace/SA/registry lists copied into conditions instead of referenced.
7. **Severity miscalibration** — `critical` for a hardening gap, or corpus over the 25% critical cap.

## 7. Domain placement & relocations

Author into `policies/kspm/<domain>/` per the catalog. Relocations from the existing corpus:
- `image_from_untrusted_registry`, `image_latest_tag` → **supply_chain** (currently in pod_security)
- `api_server_anonymous_auth`, `etcd_encryption_disabled` → **control_plane** / **secrets** (currently admission_control)
- `audit_policy_modified` → **logging_audit** (currently admission_control)

Keep the rule `id` stable across a move (only the directory changes) to preserve traceability.
