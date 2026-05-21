# CASB Policies — Quickstart

> Get Proofpoint CASB DLP working with minimum viable configuration.
> Time estimate: 30-60 minutes (connector provisioning depends on app-specific OAuth setup)
> Prerequisites: Proofpoint Data Security platform licensed with CASB add-on; admin credentials for target cloud application

---

## Coverage Warning

**CASB has LOW documentation coverage.** This quickstart reflects the minimum logical steps derived from product capability descriptions [S13 — Grade A] and a training datasheet [S25 — Grade B]. Navigation paths, exact field names, and button labels are INCOMPLETE and marked where unknown. Verify all steps against the live CASB admin console before using in production runbooks.

---

## Before You Start

| Prerequisite | Where to configure | Notes |
|-------------|-------------------|-------|
| Proofpoint Data Security licensed with CASB | Proofpoint account management | Contact your Proofpoint account team — CASB is an add-on license |
| Admin credentials for target cloud app (e.g., Microsoft 365 Global Admin) | Your identity provider | Required for OAuth connector provisioning |
| User groups defined in corporate directory | Azure AD / LDAP | Required for policy scoping |

---

## Step 1: Provision a Cloud Application Connector

**Navigate to:** CASB admin console > Connectors (exact path UNKNOWN — INCOMPLETE)

1. Select your cloud application from the list (e.g., Microsoft 365, Google Workspace, Salesforce, Box)
2. Follow the application-specific OAuth authorization flow
3. Confirm the connector status shows as Active/Connected before proceeding

**Why this step is first:** All CASB policies are non-functional without an active connector. There is no enforcement of any policy type until at least one connector is connected and syncing data. [S13 — Grade A]

---

## Step 2: Sync Users and Groups

**Navigate to:** CASB admin console > Users or Directory (exact path UNKNOWN — INCOMPLETE)

1. Connect to your directory source (Azure AD, LDAP, or Proofpoint User Center)
2. Trigger or wait for initial sync to complete
3. Verify your target user group appears in the user list

**Why this step is second:** CASB policies scope to user groups. If groups are not synced, policies apply to all users by default, removing the ability to stage rollouts by group. [S13 — Grade A, inferred from platform architecture]

---

## Step 3: Create a DLP Detector

**Navigate to:** CASB > DLP > Detectors (exact path UNKNOWN — INCOMPLETE)

1. Click Create / New Detector
2. Set a **Detector Name** (e.g., "PII — SSN Detection")
3. Choose a **Detection Method** (recommended: Smart Identifier for lower false-positive rate)
4. Select the content type to detect (e.g., Social Security Numbers)
5. Save the detector

**Minimum required fields:** Name, detection method, content target. All other fields accept defaults. [S25 — Grade B]

---

## Step 4: Create a DLP Rule

**Navigate to:** CASB > DLP > Rules (exact path UNKNOWN — INCOMPLETE)

1. Click Create / New Rule
2. Set a **Rule Name** (e.g., "Block PII in Cloud File Shares")
3. Select the **Detector** created in Step 3
4. Set **Cloud Application Scope** to the application connected in Step 1
5. Set **User/Group Scope** to a small test group first (do NOT deploy to all users initially)
6. Set **Remediation Action** to **Alert** (not Block) for initial testing
7. Save the rule
8. Set rule status to **Enabled**

**Why alert-only first:** Immediately blocking may disrupt legitimate file sharing. Alert mode collects detection data before enforcement begins. [Grade U — **ASSUMPTION** based on standard CASB deployment practice]

---

## Step 5: Monitor and Verify

1. Trigger a test event: share a file containing dummy PII data (e.g., a test SSN like 000-00-0000) in the connected cloud application
2. Wait for CASB to scan the content (scanning latency UNKNOWN — INCOMPLETE)
3. Verify an alert appears in the CASB alerts dashboard
4. After 1-2 weeks of alert-mode monitoring, return to the rule and change Remediation Action to your enforcement action (Quarantine or Block)

---

## Verify It Works

- Alert appears in CASB console for test PII file share
- Alert correctly identifies the user, file, and matched detector
- No false positives on known-clean files

---

## Next Steps

- For all policy types and advanced configuration: see [advanced.md](advanced.md)
- For prerequisite details and time estimates: see [prerequisites.md](prerequisites.md)
- For known issues: see [gotchas.md](gotchas.md)
- For the full field-level reference: see [workflow.md](workflow.md)
