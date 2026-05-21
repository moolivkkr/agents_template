# Authoring Rules — Quickstart Guide
## Broadcom Symantec DLP (Enforce Server, version 16.x/25.x/26.x)

> **Goal:** Fastest path from zero to a working, deployed DLP policy.
> **Time estimate:** 15-30 minutes for a template-based policy.
> **Prerequisites:** Enforce Server running, at least one detection server registered, Oracle DB operational.

---

## The 5-Step Fast Path

```
Step 1: Select a pre-built policy template (PCI-DSS)
Step 2: Customize detection rule threshold (optional)
Step 3: Add an automated response rule (notify admin)
Step 4: Assign to a policy group
Step 5: Deploy to detection server
```

---

## Step 1: Create Policy from Template

**Navigation:** Manage > Policies > Policy List > New Policy > Template List

1. In the Enforce console, navigate to **Manage > Policies > Policy List**
2. Click **New Policy** in the upper right
3. Select **Template List** (not "Create New Policy")
4. From the template list, select **"PCI DSS - Credit Card Numbers"**
5. Click **Next**

```
+=========================================================================+
|  New Policy -- Select Template                                          |
+=========================================================================+
|  Search: [PCI               ]  [Filter]                                 |
|                                                                         |
|  [x] PCI DSS - Credit Card Numbers                                     |
|  [ ] PCI DSS - All Policy Templates                                    |
|  [ ] HIPAA (Including PHI)                                              |
|  [ ] GLBA                                                               |
|  [ ] SOX Compliance                                                     |
|  [ ] GDPR - Personal Data                                               |
|  [ ] UK DPA                                                             |
|                                                                         |
|                                                          [Next >]       |
+=========================================================================+
```

**What you get from the template:**
- Pre-configured detection rule using the "Credit Card Number" data identifier (Luhn validation)
- Default threshold: 1 unique credit card number match
- Default severity: High
- Default look-in: message body + attachments
- No response rules attached (you add these in Step 3)

[S1, S4, V16] Evidence: A

---

## Step 2: Customize Detection Threshold (Optional)

After selecting the template, the policy editor opens.

1. Click the **Detection** tab
2. Review the pre-configured detection rule
3. Optionally adjust the **Minimum Matches** threshold
   - Default: 1 (triggers on any single credit card number)
   - For less noise: Set to 3 or 5 (triggers only on bulk card data)
4. Leave all other settings at defaults

**Recommended for quickstart:** Keep threshold at **1** for PCI compliance. Adjust later during tuning.

| Field | Default | Keep Default? | Notes |
|-------|---------|--------------|-------|
| Data Identifier | Credit Card Number | Yes | Built-in with Luhn validation |
| Minimum Matches | 1 | Yes | PCI requires detecting even 1 card number |
| Severity | High | Yes | Credit card data is always high severity |
| Look In | Body + Attachments | Yes | Covers email body and file attachments |

[S1, S4, V17] Evidence: A

---

## Step 3: Add an Automated Response Rule

**Navigation:** Manage > Policies > Response Rules > Add Response Rule

1. Navigate to **Manage > Policies > Response Rules**
2. Click **Add Response Rule**
3. Select **Automated Response Rule**
4. Click **Next**

**Configure the rule:**

| Field | Value |
|-------|-------|
| Rule Name | `Notify-Admin-CC-Detection` |
| Conditions | (leave empty -- fires on every match) |
| Action 1 | **Send Email Notification** |
| - To | `dlp-admins@company.com` |
| - Subject | `DLP Alert: Credit card data detected - $POLICY$` |
| - Body | `Incident $INCIDENT_ID$: Policy $POLICY$ violated by $SENDER$. Severity: $SEVERITY$. Review at Enforce console.` |

5. Click **Save**

**Now attach the response rule to your policy:**

1. Go back to **Manage > Policies > Policy List**
2. Click your PCI DSS policy
3. Click the **Response** tab
4. Click **Add Response Rule**
5. Select **Notify-Admin-CC-Detection**
6. Click **Save**

[S1, S4, V23] Evidence: A

---

## Step 4: Assign to a Policy Group

1. In the policy editor, click the **General** tab
2. Under **Policy Group**, select from the dropdown:
   - **Default Policy Group** -- deployed to ALL detection servers (simplest option)
   - Or select a specific policy group if you have custom groups configured

| Field | Value |
|-------|-------|
| Policy Group | Default Policy Group |

3. Click **Save**

**Note:** The Default Policy Group deploys to every registered detection server. For a quickstart, this is the right choice. Create custom policy groups later when you need different policies on different servers.

[S1, S4] Evidence: A

---

## Step 5: Deploy

**Policy Mode Selection:**

1. In the policy editor **General** tab, set **Policy Mode**:
   - For quickstart testing: **Test Without Notifications** (recommended first)
   - For production: **Enabled** (only after testing confirms low false positive rate)

2. Click **Save**

**The policy is now active.** The Enforce Server automatically pushes the policy to all detection servers in the selected policy group.

**Verification:**
- Navigate to **Incidents > Network** (or Endpoint, depending on your detection servers)
- Send a test email containing a known test credit card number (e.g., `4111-1111-1111-1111`)
- Within seconds (network) or up to 15 minutes (endpoint), an incident should appear

```
+=========================================================================+
|  Incidents > Network                                                    |
+=========================================================================+
|  ID    | Date       | Severity | Policy                | Status        |
|--------|------------|----------|----------------------|---------------|
|  1001  | 2024-01-15 | High     | PCI-DSS-Credit-Card  | New           |
|                                                                         |
|  Click incident for details...                                          |
+=========================================================================+
```

[S1, S4, V12, V17] Evidence: A

---

## What You Now Have

After completing these 5 steps:

| Component | Status |
|-----------|--------|
| Detection rule | PCI DSS template with credit card data identifier (Luhn validation) |
| Response rule | Email notification to DLP admin team |
| Policy | Assigned to Default Policy Group |
| Deployment | Active on all detection servers |
| Policy mode | Test Without Notifications (or Enabled) |

---

## Next Steps (After Quickstart)

### Immediate (Day 1-7)
1. **Monitor incident volume** -- check Incidents dashboard daily
2. **Review false positives** -- adjust threshold if too many false alerts
3. **Promote to "Test With Notifications"** -- users start seeing warnings (no blocking yet)

### Short-term (Week 2-4)
4. **Add exceptions** -- whitelist known-good automated systems, specific sender groups
5. **Add more response rules** -- syslog to SIEM, blocking for email channel
6. **Promote to "Enabled"** -- full enforcement after tuning confirms accuracy

### Medium-term (Month 2+)
7. **Add EDM profiles** -- exact data matching for customer/employee records
8. **Add more policies** -- HIPAA, GDPR, source code protection
9. **Create custom policy groups** -- different policies for different detection servers
10. **Add VML profiles** -- ML-based detection for unstructured content

### Best Practice Rollout Order
```
Week 1:  Monitor    (Test Without Notifications)
Week 2:  Notify     (Test With Notifications)
Week 3:  Soft Block (User Cancel with justification)
Week 4+: Hard Block (Block Message / Block Transfer)
```

[V17, video-intelligence tribal knowledge] Evidence: A-B

---

## Common Quickstart Mistakes

| Mistake | Impact | Fix |
|---------|--------|-----|
| Enabling "Block" response on Day 1 | Employee backlash, legitimate emails blocked | Start with "Test" mode, graduate to blocking |
| Using Default Policy Group for all policies | Every server gets every policy (performance) | Create targeted policy groups as you add policies |
| Not reviewing incidents after deployment | Stale false positives overwhelm the system | Check incident dashboard daily for first 2 weeks |
| Skipping notification step | No visibility when data loss occurs | Always have at least email notification + syslog |
| Testing with real data | Incidents created with real sensitive data in test | Use known test patterns (test CC numbers) |

[V17, video-intelligence Section 3] Evidence: A-B

---

## Quickstart API Alternative (DLP 25.1+)

If you have an existing policy XML from another Enforce Server:

```bash
# Import policy XML via REST API
curl -X POST \
  https://enforce-server:443/ProtectManager/webservices/v2/policies/import \
  -H "Authorization: Basic $(echo -n 'admin:password' | base64)" \
  -H "Content-Type: application/xml" \
  --data-binary @pci-dss-policy.xml

# Deploy policy changes
curl -X POST \
  https://enforce-server:443/ProtectManager/webservices/v2/policies/apply \
  -H "Authorization: Basic $(echo -n 'admin:password' | base64)"
```

**Note:** Individual rule creation is NOT available via API. The import/export workflow is the API-based alternative to console-based policy authoring.

[API-intelligence] Evidence: A

---

*End of quickstart guide. Estimated time to first incident: 15-30 minutes from starting Step 1.*
