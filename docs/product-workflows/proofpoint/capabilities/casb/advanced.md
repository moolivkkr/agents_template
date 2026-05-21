# CASB Policies — Advanced Configuration Reference

> Sub-capabilities: 10.1 – 10.6 | Product: Proofpoint CASB
> Evidence base: S13 (Grade A — overview), S25 (Grade B — training datasheet)
> Coverage level: LOW — most field-level detail is INCOMPLETE

---

## Coverage Warning

The CASB admin console configuration screens require authentication at docs.public.analyze.proofpoint.com/pcasb/. Available public documentation covers capability descriptions and a brief training datasheet outline. All screen names, field names, and navigation paths below are either directly extracted from available sources (noted) or are Grade U ASSUMPTIONS (marked). This document should be treated as a structural scaffold, not a complete reference, until verified against the live admin console.

---

## Screen: CASB > DLP > Detectors (Sub-capability 10.6)

**Navigation:** INCOMPLETE — CASB admin console path unknown
**Purpose:** Build content-matching units that CASB DLP rules reference.
**Source:** S25 — Grade B (training datasheet describes "building detectors to find DLP in documents")

### Fields

| Field | Type | Required | Default | Options | Validation | Description | Source |
|-------|------|----------|---------|---------|------------|-------------|--------|
| Detector Name | Text | Yes | None | Free text | Non-empty, unique | Internal identifier for the detector | E — Inferred from S25 |
| Detection Method | Dropdown | Yes | None | Keywords, Regex, Smart Identifiers, Document Fingerprints (options UNCONFIRMED) | Must select one | How content is identified | E — Inferred from S13 (shared classifier architecture with Email DLP) |
| Content Target | Text/multiselect | Yes | None | Depends on method | Varies | The specific content to detect (keyword list, regex pattern, or classifier reference) | E — Inferred from S25 |
| Match Threshold | Number | No | Unknown | Numeric count | Positive integer | Minimum number of matches before detector fires | Grade U — **ASSUMPTION** |
| Case Sensitive | Checkbox | No | Unknown | Enabled/Disabled | — | Whether keyword matching is case sensitive | Grade U — **ASSUMPTION** |

### Conditional Fields

When Detection Method = **Smart Identifier**: classifier selection dropdown appears (options drawn from Proofpoint's 240+ classifier library, shared with Email DLP). [S13 — Grade A, S24 — Grade B, cross-capability inference]

When Detection Method = **Document Fingerprints**: document upload field appears to register the template document. [Grade U — **ASSUMPTION** based on S14 fingerprinting capability description]

### Edge Cases

- If no threshold is set, detector may fire on a single match — can produce high false-positive volume for common keywords. [Grade U — **ASSUMPTION**]
- Detector changes may not apply to already-shared content already cached by CASB. [Grade U — **ASSUMPTION**]

---

## Screen: CASB > DLP > Rules (Sub-capabilities 10.3, 10.6)

**Navigation:** INCOMPLETE
**Purpose:** Combine detectors with scoping and remediation to create enforceable DLP rules.
**Source:** S25 — Grade B; S13 — Grade A

### Fields

| Field | Type | Required | Default | Options | Validation | Description | Source |
|-------|------|----------|---------|---------|------------|-------------|--------|
| Rule Name | Text | Yes | None | Free text | Non-empty, unique | Internal identifier | E — Inferred from S25 |
| Detector(s) | Multi-select | Yes | None | List of configured detectors | At least one | Content-matching units this rule enforces | E — Inferred from S25 |
| Cloud Application Scope | Multi-select | Yes | None | Connected applications | At least one connector active | Which apps are monitored by this rule | E — Inferred from S13 |
| Activity Type | Multi-select | No | All | Upload, Download, Share, View, Edit (options UNCONFIRMED) | — | Restricts rule to specific user activities | Grade U — **ASSUMPTION** |
| User / Group Scope | Multi-select | No | All users | Synced user groups | — | Narrows enforcement to a user population | E — Inferred from S13 |
| Remediation Action | Dropdown | Yes | None | Alert, Quarantine, Block, Notify User, Notify Admin (options UNCONFIRMED) | — | Action taken when rule fires | E — Inferred from S13 |
| Notification Recipients | Text/multiselect | No | None | Email addresses or admin roles | Valid email | Who receives alerts when rule fires | Grade U — **ASSUMPTION** |
| Rule Enabled | Toggle | Yes | Disabled | Enabled/Disabled | — | Must be explicitly enabled to enforce | Grade U — **ASSUMPTION** |
| Rule Priority | Number | No | Unknown | Numeric | Positive integer | Order of evaluation when multiple rules apply | Grade U — **ASSUMPTION** |

### Conditional Fields

When Remediation Action = **Quarantine**: additional field for quarantine folder or quarantine notification behavior may appear. [Grade U — **ASSUMPTION**]

When Remediation Action = **Notify User**: notification message template field likely appears. [Grade U — **ASSUMPTION**]

---

## Screen: CASB > Threat Protection > Policies (Sub-capability 10.1)

**Navigation:** INCOMPLETE
**Purpose:** Detect and respond to account compromise, anomalous logins, OAuth app abuse, and malicious file activity.
**Source:** S13 — Grade A

### Known Capability Areas (fields INCOMPLETE)

| Capability | Description | Source |
|-----------|-------------|--------|
| Account takeover defense | Detects credential compromise signals from login anomalies | S13 — Grade A |
| Impossible travel detection | Flags logins from geographically impossible locations | Grade U — **ASSUMPTION** based on standard CASB threat protection pattern |
| OAuth application abuse | Detects over-privileged third-party OAuth apps | Grade U — **ASSUMPTION** |
| Malicious file detection | Scans cloud-stored files for malware | S13 — Grade A |

All field names for Threat Protection policy configuration: INCOMPLETE — requires authentication to access admin docs.

---

## Screen: CASB > Access Control > Policies (Sub-capability 10.2)

**Navigation:** INCOMPLETE
**Purpose:** Enforce user behavior analytics (UBA) to detect and block risky access patterns.
**Source:** S13 — Grade A

### Known Capability Areas (fields INCOMPLETE)

| Capability | Description | Source |
|-----------|-------------|--------|
| User behavior analytics | Baseline normal activity; flag deviations | S13 — Grade A |
| Bulk download detection | Alert or block mass data extraction | Grade U — **ASSUMPTION** |
| Unmanaged device controls | Restrict access or enforce read-only for non-corporate devices | Grade U — **ASSUMPTION** |
| Conditional access | Allow/block based on device posture, location, time | Grade U — **ASSUMPTION** |

All field names for Access Control policy configuration: INCOMPLETE.

---

## Screen: CASB > App Visibility > Governance (Sub-capability 10.4)

**Navigation:** INCOMPLETE
**Purpose:** Discover, classify, and govern sanctioned and unsanctioned cloud application usage.
**Source:** S13 — Grade A

### Known Capability Areas (fields INCOMPLETE)

| Capability | Description | Source |
|-----------|-------------|--------|
| App discovery | Identifies cloud apps used by the organization | S13 — Grade A |
| App risk scoring | Assigns risk level to discovered apps | Grade U — **ASSUMPTION** |
| Governance rules | Allow, block, or monitor specific apps | Grade U — **ASSUMPTION** |
| Sanctioned app list | Approved apps with reduced alert threshold | Grade U — **ASSUMPTION** |

---

## Screen: CASB > Infrastructure > Security Assessment (Sub-capability 10.5)

**Navigation:** INCOMPLETE
**Purpose:** Identify vulnerabilities and compliance risks in cloud IaaS environments (AWS, Azure, GCP).
**Source:** S13 — Grade A

### Known Capability Areas (fields INCOMPLETE)

| Capability | Description | Source |
|-----------|-------------|--------|
| IaaS connector | Connect to AWS/Azure/GCP accounts | S13 — Grade A |
| Configuration assessment | Scan for security misconfigurations (e.g., open S3 buckets) | Grade U — **ASSUMPTION** |
| Compliance framework mapping | Map findings to CIS, NIST, PCI-DSS frameworks | Grade U — **ASSUMPTION** |
| Remediation guidance | Prescriptive fix instructions per finding | Grade U — **ASSUMPTION** |

---

## Integration with Email DLP

Proofpoint positions CASB DLP and Email DLP as a unified protection layer with consistent classifiers across cloud applications and email channels. [S13 — Grade A] This means:

1. Smart identifiers configured for Email DLP are available in CASB DLP detectors (shared classifier library). [S13 — Grade A; S24 — Grade B cross-reference]
2. DLP alerts from both channels surface in the same Data Security administration console. [S13 — Grade A, inferred from platform architecture]
3. Policy tuning for a specific data type (e.g., PII) should be coordinated across both Email DLP and CASB DLP to maintain consistent enforcement. [Grade U — **ASSUMPTION** based on shared-classifier architecture]

---

## What Is Fully INCOMPLETE

The following areas have zero field-level documentation in accessible sources and require direct console access to map:

1. Connector provisioning workflow (field names, OAuth scope requirements per app)
2. User/group sync configuration (directory source options, sync frequency, conflict handling)
3. Threat Protection policy field names and options
4. Access Control policy field names and options
5. App Visibility governance rule field names and options
6. Infrastructure Assessment scan configuration (frequency, scope, alert thresholds)
7. Policy priority/ordering mechanism across all six policy types
8. Notification template configuration for any policy type
9. Alert triage and case management workflow
10. CASB-specific RBAC roles and permissions

For any of the above: access the CASB admin console directly at docs.public.analyze.proofpoint.com/pcasb/ with admin credentials.
