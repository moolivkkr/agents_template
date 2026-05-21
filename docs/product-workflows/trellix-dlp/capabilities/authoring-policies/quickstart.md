# Authoring Policies -- Quickstart Guide
## Minimum Viable Policy in 15 Minutes

> Capability: authoring-policies | Generated: 2026-05-21
> Goal: Create a working DLP policy from zero -- detect SSN in outbound email, block and notify user

---

## Prerequisites (Must Be Done Before Starting)

These infrastructure items must already be in place. If any are missing, stop and configure them first (see prerequisites.md for details).

- [ ] Trellix ePO server installed and accessible via web console
- [ ] DLP extension (11.x) installed in ePO (Menu > Software > Extensions > verify "Data Loss Prevention" is listed)
- [ ] At least one endpoint with Trellix Agent + DLP Endpoint agent deployed
- [ ] Endpoint assigned to a System Tree group
- [ ] You have an ePO administrator account with DLP permissions

---

## The 6 Steps

### Step 1: Create a Regex Definition (2 min)

**What:** Define the pattern for US Social Security Numbers.

1. Log into ePO console: `https://<epo-server>:8443`
2. Navigate to **Menu > Data Protection > Classification**
3. You will see the Classification page with tabs. Click the **Definitions** tab
4. In the left tree, expand **Advanced Patterns**
5. Look for the built-in pattern **"Social Security Number (US)"** -- if it exists, skip to Step 2 (it is pre-built in most installations)
6. If no built-in pattern exists, click **Actions > New Item**:

| Field | Value |
|-------|-------|
| Name | `SSN - US Social Security Number` |
| Description | `Matches US SSN in XXX-XX-XXXX format` |
| Matched Expression | `\b\d{3}-\d{2}-\d{4}\b` |
| Ignored Expressions | (leave empty) |
| Validator | `None` (accept default for quickstart) |
| Score | `1` |

7. Click **Save**

> **Tip:** For production, select the `Luhn 10` validator or add a more precise regex. The quickstart pattern will have some false positives.

---

### Step 2: Create a Classification (2 min)

**What:** Create a classification that uses the SSN definition to identify sensitive content.

1. Stay on **Menu > Data Protection > Classification**
2. Click the **Content Classification Criteria** tab (should be the first tab)
3. Click **Actions > New Classification**

| Field | Value |
|-------|-------|
| Name | `PII - Social Security Numbers` |
| Description | `Detects US Social Security Numbers in content` |

4. The classification opens. Click the **+** icon (or **Add Component** button) to add criteria
5. Select **Advanced Pattern** from the dropdown
6. Select your SSN pattern (either the built-in or the one you created in Step 1)
7. Leave the default settings (score threshold = 1, occurrence count = 1)
8. Click **Save**

> **What happened:** You now have a classification that triggers when any document or message contains a US SSN pattern.

---

### Step 3: Create an Email Protection Rule (3 min)

**What:** Create a rule that blocks outbound emails containing SSNs and notifies the user.

1. Navigate to **Menu > Data Protection > DLP Policy Manager**
2. Click the **Rule Sets** tab
3. Click **Actions > New Rule Set**

| Field | Value |
|-------|-------|
| Name | `Quickstart - PII Protection` |
| Description | `Basic PII email protection` |

4. Click the new rule set name to open it
5. Click **Actions > New Rule > Email Protection**

**On the Rule Configuration screen:**

**Condition tab:**

| Field | Value |
|-------|-------|
| Classification | Select **"PII - Social Security Numbers"** (the one you created in Step 2) |
| Sender | (leave as "Any" -- applies to all users) |
| Recipient | (leave as "Any" -- applies to all recipients) |

**Reaction tab:**

| Field | Value |
|-------|-------|
| Action | **Block** |
| Notify User | **Enabled** -- enter message: `This email was blocked because it contains Social Security Numbers. Please remove sensitive data and try again.` |
| Report to ePO | **Yes** (checked) |
| Store Original Evidence | **No** (leave unchecked for quickstart) |
| Severity | **High** |

**General:**

| Field | Value |
|-------|-------|
| Rule Name | `Block SSN in Outbound Email` |
| State | **Enabled** |

6. Click **Save**

> **What happened:** You now have a rule set containing one email protection rule that blocks emails with SSNs.

---

### Step 4: Add Rule Set to a Policy (2 min)

**What:** Assign the rule set to a DLP Policy in the Policy Catalog.

1. Navigate to **Menu > Policy > Policy Catalog**
2. In the Product dropdown, select **"Data Loss Prevention [version]"**
3. In the Category dropdown, select **"DLP Policy"**
4. You will see existing policies. Either:
   - **Option A (recommended for quickstart):** Click **Duplicate** on the default policy (named "My Default"), name it `Quickstart DLP Policy`
   - **Option B:** Click **Actions > New Policy**, name it `Quickstart DLP Policy`
5. Open the new policy
6. Navigate to the **Rule Sets** section
7. Click **Add Rule Set** (or **Assign Rule Set**)
8. Select **"Quickstart - PII Protection"** from the list
9. Click **Save**

> **What happened:** You now have a DLP Policy containing your rule set, ready to be assigned to systems.

---

### Step 5: Assign Policy via System Tree (3 min)

**What:** Assign the policy to a group of endpoints.

1. Navigate to **Menu > Systems > System Tree**
2. In the left tree, select the group containing your test endpoint(s)
   - For testing: use a small test group, NOT your entire organization
3. Click the **Assigned Policies** tab
4. Find the **"Data Loss Prevention [version]"** row
5. Click **Edit Assignment** next to "DLP Policy"
6. In the policy dropdown, select **"Quickstart DLP Policy"**
7. If this group inherits from a parent, check **"Break inheritance and assign the policy and settings below"**
8. Click **Save**

---

### Step 6: Deploy Policy to Endpoints (3 min)

**What:** Push the policy to the endpoint agents immediately (instead of waiting for the 60-minute ASCI interval).

1. Stay on **Menu > Systems > System Tree**
2. Select the same group (or individual systems) from Step 5
3. Click **Actions > Agent > Wake Up Agents**
4. In the dialog:
   - Randomization: `0 minutes` (push immediately)
   - Check **"Force complete policy update"**
5. Click **OK**
6. Wait 1-2 minutes for agents to receive the policy

> **Verification:** On the test endpoint, open Microsoft Outlook and compose a new email. In the body, type a fake SSN like `123-45-6789`. Try to send it. You should see the DLP block notification.

---

## What You Built

```
Definition: SSN regex pattern
    |
    v
Classification: "PII - Social Security Numbers"
    |
    v
Rule: "Block SSN in Outbound Email" (Email Protection, Block action)
    |
    v
Rule Set: "Quickstart - PII Protection"
    |
    v
Policy: "Quickstart DLP Policy"
    |
    v
System Tree Assignment: [Your test group]
    |
    v
Deployed to endpoints via Agent Wake-Up
```

---

## Next Steps

Once the quickstart policy is verified working:

1. **Add more rule types** -- add Web Protection and Cloud Protection rules to the same rule set to cover additional channels
2. **Refine the classification** -- add Luhn validation, proximity matching (SSN near keywords like "social security"), and dictionary co-occurrence to reduce false positives
3. **Switch to Monitor mode first** -- in production, start with Monitor (not Block) to observe hits before enforcing. Change the Action from Block to Monitor, run for 1-2 weeks, review incidents, then switch to Block
4. **Add more classifications** -- create classifications for credit cards (PCI-DSS), HIPAA data, or custom business data
5. **Use pre-built templates** -- duplicate the built-in compliance rule set templates (GDPR, HIPAA, PCI-DSS) instead of building from scratch
6. **Configure End-User Groups** -- scope rules to specific departments by creating End-User Group definitions from Active Directory

See [workflow.md](workflow.md) for the complete deep-dive and [advanced.md](advanced.md) for the full field reference.
