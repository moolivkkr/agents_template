# Authoring Policies -- Quickstart Guide
## Minimum Viable Policy in 20 Minutes

> Capability: authoring-policies | Generated: 2026-05-21
> Goal: Create a working DLP policy from zero -- detect credit card numbers in web uploads, alert and log

---

## Prerequisites (Must Be Done Before Starting)

- [ ] Enterprise DLP license activated on your Palo Alto Networks tenant
- [ ] Strata Cloud Manager (SCM) accessible at `https://stratacloud.paloaltonetworks.com`
- [ ] At least one Prisma Access instance or NGFW connected to SCM
- [ ] You have an SCM account with DLP Admin role
- [ ] Enforcement point has internet connectivity to Palo Alto DLP cloud

---

## The 5 Steps

### Step 1: Verify Predefined Data Patterns (2 min)

**What:** Confirm that predefined data patterns are available (they should be enabled by default with Enterprise DLP license).

1. Log into **Strata Cloud Manager**: `https://stratacloud.paloaltonetworks.com`
2. Navigate to **Shared Resources > Data Loss Prevention > Data Patterns**
3. In the search bar, type `Credit Card`
4. Verify you see predefined patterns such as:
   - `Credit Card Number` (regex-based)
   - `Credit Card Number - ML` (ML-based, if available)
   - `Credit Card Track Data`

> **Note:** Predefined patterns cannot be modified or deleted. They are ready to use as-is.

If no patterns appear, verify your Enterprise DLP license is active under the Hub.

---

### Step 2: Create a Data Profile (5 min)

**What:** Create a data profile that groups credit card detection patterns together.

1. Navigate to **Shared Resources > Data Loss Prevention > Data Profiles**
2. Click **Add Data Profile**

| Field | Value |
|-------|-------|
| Profile Name | `Quickstart - PCI Credit Cards` |
| Description | `Detects credit card numbers in content for PCI-DSS compliance` |

3. In the **Match Criteria** section, click **Add Match Criteria**
4. Configure the first match criterion:

| Field | Value |
|-------|-------|
| Data Pattern | Select **Credit Card Number** |
| Detection Type | Cloud (default -- sends to Enterprise DLP cloud for verdict) |
| Occurrence | `Any` (triggers on any match) |
| Confidence Level | `High` (if using ML pattern) |

5. Optionally, add a second match criterion:
   - Click **Add Match Criteria** again
   - Select **Credit Card Track Data** pattern
   - Same occurrence/confidence settings

6. Set the **Match Logic** (if multiple criteria):
   - Select **OR** (match if ANY criterion triggers)

7. Click **Save**

> **What happened:** You now have a data profile that detects credit card numbers (regex + optional ML) in inspected content.

---

### Step 3: Create a DLP Rule (5 min)

**What:** Create a DLP rule that specifies which traffic to inspect and what action to take.

1. Navigate to **Configuration > Security Services > Data Loss Prevention**
2. Click **Add Rule**

| Field | Value |
|-------|-------|
| Rule Name | `Quickstart - Alert on Credit Cards` |
| Description | `Alert when credit card data detected in web uploads` |

3. Configure the rule settings:

| Field | Value |
|-------|-------|
| Data Profile | Select **Quickstart - PCI Credit Cards** (from Step 2) |
| Direction | **Upload** (inspect outbound data only) |
| File Types | **All** (inspect all file types) |
| Action | **Alert** (log but do not block -- monitor mode for quickstart) |
| Log Severity | **High** |

4. Click **Save**

> **What happened:** You have a DLP rule that inspects all uploaded file types for credit card data and generates an alert when detected.

---

### Step 4: Attach to a Security Policy Rule (5 min)

**What:** Create or modify a security policy rule to apply the DLP rule to web traffic.

**Option A: Create a new security rule (recommended for quickstart)**

1. Navigate to **Configuration > Security Services > Security Policy**
2. Click **Add Rule**

| Field | Value |
|-------|-------|
| Rule Name | `Quickstart - DLP Web Inspection` |
| Source Zone | `Trust` (or your internal zone) |
| Destination Zone | `Untrust` (or your internet zone) |
| Source Address | `Any` |
| Destination Address | `Any` |
| Application | `Any` (or restrict to `web-browsing`, `ssl`) |
| Service | `application-default` |
| Action | `Allow` |

3. In the **Security Profiles** section:
   - Click **Profile Group** or **Profiles**
   - Under **Data Loss Prevention**, select **Quickstart - Alert on Credit Cards**
   - (Or create a Profile Group first and assign the DLP profile to it)

4. Click **Save**

**Option B: Add DLP to an existing rule**

1. Find your existing internet access rule
2. Click **Edit**
3. Navigate to the Security Profiles section
4. Add the DLP profile to the rule
5. Click **Save**

---

### Step 5: Commit and Push (3 min)

**What:** Deploy the configuration to enforcement points.

1. Click the **Push Config** button (top-right of SCM)
2. Select the target scope:
   - For Prisma Access: select your Prisma Access instance
   - For NGFW: select the target device group or firewall
3. Review the pending changes (should show the new DLP rule and security rule)
4. Click **Push**
5. Wait for the push to complete (typically 1-3 minutes)

> **Verification:** Open a web browser on a monitored endpoint. Create a test file containing a fake credit card number like `4111-1111-1111-1111`. Upload it to a web-based file sharing service. Check the Enterprise DLP incident dashboard for an alert.

---

## What You Built

```
Data Pattern: Credit Card Number (predefined, regex-based)
    |
    v
Data Profile: "Quickstart - PCI Credit Cards"
    |         (occurrence: Any, confidence: High)
    v
DLP Rule: "Quickstart - Alert on Credit Cards"
    |      (direction: Upload, file types: All, action: Alert)
    v
Security Policy Rule: "Quickstart - DLP Web Inspection"
    |                  (Trust -> Untrust, action: Allow + DLP profile)
    v
Push to enforcement point (Prisma Access / NGFW)
```

---

## Next Steps

Once the quickstart policy is verified working:

1. **Add more data patterns** -- Add SSN, HIPAA, GDPR patterns to the same data profile to broaden detection
2. **Switch to Block action** -- After monitoring alerts for 1-2 weeks, change the DLP rule action from Alert to Block for confirmed-true-positive patterns
3. **Create a Granular Data Profile** -- Use granular profiles to apply different actions per pattern (e.g., Alert for SSN, Block for credit cards)
4. **Add EDM** -- Set up Exact Data Matching for your customer database to detect specific records with near-zero false positives
5. **Enable Endpoint DLP** -- If you have Cortex XDR 5.0, create Endpoint DLP policy rules for desktop application monitoring
6. **Create Nested Profiles** -- Consolidate multiple data profiles into a nested profile for cleaner security rule management
7. **Target AI applications** -- Create a separate security rule targeting ChatGPT (App-ID) with a stricter DLP profile (Block action)

See [workflow.md](workflow.md) for the complete deep-dive and [advanced.md](advanced.md) for the full field reference.
