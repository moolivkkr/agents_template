# Authoring Policies -- Quickstart Guide
## Minimum Viable Policy in 15 Minutes

> Capability: authoring-policies | Generated: 2026-05-21
> Goal: Create a working DLP policy from zero -- detect SSN in sanctioned cloud services, create incident and alert

---

## Prerequisites (Must Be Done Before Starting)

- [ ] Skyhigh Security tenant provisioned and accessible
- [ ] At least one sanctioned cloud service connected (e.g., Microsoft 365, Box, Google Workspace)
- [ ] You have a Skyhigh account with DLP Administrator permissions
- [ ] DLP module is visible under Policy > DLP Policy

---

## The 5 Steps

### Step 1: Create a Classification (3 min)

**What:** Define a classification that detects US Social Security Numbers using a built-in advanced pattern.

1. Log into Skyhigh Security Dashboard
2. Navigate to **Policy > DLP Policy > Classifications**
3. Click **Create Classification**

| Field | Value |
|-------|-------|
| Classification Name | `PII - US Social Security Number` |
| Description | `Detects US SSNs for PII protection` |

4. Under **Definition Type**, select **Advanced Pattern**
5. In the pattern list, search for and select the built-in `Social Security Number` pattern
6. Set **Score Threshold**: `1` (trigger on any match)
7. Set **Location**: `Body` (scan full document body)
8. Click **Save**

> **Tip:** Skyhigh includes many built-in advanced patterns. Search for "Social Security" to find the predefined regex with Luhn validation already configured.

---

### Step 2: Create a DLP Policy (3 min)

**What:** Create a sanctioned DLP policy container.

1. Navigate to **Policy > DLP Policy > Policies**
2. Click **Create Policy** (or use the **Policy Wizard** for guided creation)

| Field | Value |
|-------|-------|
| Policy Name | `Quickstart - PII Protection` |
| Description | `Detects and alerts on PII (SSN) in sanctioned cloud services` |
| Status | `Enabled` |

3. Click **Next** (or Save, depending on whether using wizard)

---

### Step 3: Add Rules and Rule Groups (5 min)

**What:** Add a classification rule within a rule group that references your SSN classification.

1. In the policy editor, navigate to the **Rules** section
2. Click **New Rule Group** to create a rule group:

| Field | Value |
|-------|-------|
| Rule Group Name | `PII Detection Group` |
| Severity | `Critical` |

3. Within the rule group, click **Add Rule**
4. Select **Classification Rule**

| Field | Value |
|-------|-------|
| Classification | Select **PII - US Social Security Number** (from Step 1) |
| Threshold | `1` (one or more matches) |

5. Click **Save Rule**

> **Note:** Rule Groups use OR logic between groups. Rules within a group can use AND or OR logic. For this quickstart, one group with one rule is sufficient.

---

### Step 4: Configure Response Actions (2 min)

**What:** Define what happens when the policy is triggered.

1. Navigate to the **Response Actions** section of the policy
2. Click **Add Response Action**

| Field | Value |
|-------|-------|
| Action | **Create Incident** |
| Severity | **Critical** (matched from rule group severity) |
| Incident Status | `New` |

3. Optionally add a second response action:

| Field | Value |
|-------|-------|
| Action | **Email Notification** |
| Recipient | `dlp-alerts@yourcompany.com` |
| Subject | `DLP Alert: SSN Detected in Cloud Service` |

4. Click **Save**

> **Note:** For the quickstart, we use Alert (Create Incident) instead of Block. Monitor first, then escalate to blocking after validating detection accuracy.

---

### Step 5: Review and Activate (2 min)

**What:** Review the complete policy and ensure it is active.

1. Click **Review** (or navigate to the policy summary page)
2. Verify:
   - Policy Status: Enabled
   - Rule Group: PII Detection Group (Critical)
   - Rule: Classification Rule referencing PII - US SSN
   - Response: Create Incident + Email Notification
3. Click **Done** or **Save Policy**

> **Verification:** Upload a test file containing a fake SSN (e.g., `123-45-6789`) to a connected sanctioned cloud service (OneDrive, Box, etc.). Wait a few minutes for the API scan to process. Check the Incidents page for a new DLP incident.

---

## What You Built

```
Classification: PII - US Social Security Number
    (Advanced Pattern: SSN regex, Score: 1, Location: Body)
    |
    v
Rule: Classification Rule (threshold: 1 match)
    |
    v
Rule Group: PII Detection Group (severity: Critical)
    |
    v
Policy: Quickstart - PII Protection (status: Enabled)
    |
    v
Response: Create Incident (Critical) + Email Notification
    |
    v
Active on: All connected sanctioned cloud services
```

---

## Next Steps

1. **Add more classifications** -- Create classifications for credit cards (PCI), HIPAA data, GDPR identifiers
2. **Add proximity matching** -- Enhance the SSN classification by requiring SSN regex to appear within 100 characters of keywords like "social security" or "SSN" to reduce false positives
3. **Use the Policy Wizard** -- For your next policy, try the guided Policy Wizard which walks through each step with templates
4. **Enable Shadow/Web DLP** -- Create a Shadow/Web DLP policy to extend protection to unmanaged cloud services and web traffic
5. **Switch to blocking** -- After monitoring incidents for 1-2 weeks, add a Block response action for confirmed-true-positive patterns
6. **Try ML Auto Classifiers** -- If you have Advanced tier, add ML Auto Classifier definitions for automatic detection of financial reports, patient records, and source code
7. **Set up EDM** -- For high-accuracy detection, create an EDM fingerprint from your customer database

See [workflow.md](workflow.md) for the complete deep-dive and [advanced.md](advanced.md) for the full field reference.
