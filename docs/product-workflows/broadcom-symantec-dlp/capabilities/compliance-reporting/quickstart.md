# Quickstart: Generate Your First PCI Compliance Report

> **Time to complete:** 15-20 minutes
> **Result:** A saved PCI compliance report that you can run on demand or schedule for monthly delivery
> **Prerequisites:** Enforce Server accessible, at least some PCI-related incidents exist (from a policy like "PCI DSS - Credit Card Numbers")

---

## Step 1: Navigate to the Incident View (1 minute)

1. Log in to the **Enforce Console** at `https://enforce-server/ProtectManager`
2. Click **Incidents** in the top navigation
3. Select **Network** (or the channel where most of your PCI incidents come from)
   - If unsure, start with Network (email-based PCI violations are most common)

---

## Step 2: Set Filters for PCI Incidents (5 minutes)

1. On the incident list page, locate the **Filters** panel
2. Set the following filters:

| Filter | Value | Purpose |
|--------|-------|---------|
| Date Range | Last 30 days (or current quarter) | Scope the report to a relevant period |
| Policy | Contains "PCI" (or select your specific PCI policy) | Only show PCI-related incidents |
| Severity | All (or High + Medium for focused view) | Include all PCI violations |

3. Click **Apply** (or the filter refreshes automatically)
4. You should now see only PCI-related incidents in the list

---

## Step 3: Verify the Results Make Sense (2 minutes)

1. Scan the incident list:
   - Do the policies look correct? (Should all be PCI-related)
   - Is the date range correct?
   - Are there a reasonable number of incidents?
2. Click on one incident to verify:
   - Matched content shows credit card numbers or other PCI data
   - The policy name is your PCI policy
3. Navigate back to the incident list

---

## Step 4: Save as a Report (3 minutes)

1. Click **Save As** (button near the top of the incident list)
2. Fill in the report details:

| Field | Value |
|-------|-------|
| Name | "PCI Compliance Report - Monthly" |
| Description | "All PCI DSS policy incidents for compliance reporting. Includes all severity levels." |
| Visibility | **Shared** (so your compliance team can access it) |

3. Click **Save**

The report is now available in your saved reports list.

---

## Step 5: Run the Report (1 minute)

1. Your newly saved report should appear in the report dropdown (or saved searches area)
2. Click it to run
3. Results display with current data matching your filter criteria
4. You can modify the date range at any time to run for different periods

---

## Step 6: Export to CSV (2 minutes)

1. With the report results displayed, click **Export**
2. Select **CSV** format
3. Choose which columns to include (recommended for compliance):
   - Incident ID, Creation Date, Severity, Status
   - Policy Name, Match Count
   - Sender/User, Recipient/Destination
   - Remediation Status
4. Click **Export**
5. CSV file downloads -- this is your PCI compliance evidence

---

## Step 7: Schedule Monthly Delivery (3 minutes)

1. Open your saved report ("PCI Compliance Report - Monthly")
2. Click **Schedule** (if available for your DLP version)
3. Configure:

| Field | Value |
|-------|-------|
| Frequency | Monthly |
| Day | 1st of each month |
| Time | 06:00 AM |
| Format | CSV attachment |
| Recipients | `compliance@corp.com`, `ciso@corp.com` |

4. Click **Save Schedule**

The report will now be automatically generated and emailed on the 1st of every month.

---

## What You Have Now

After completing this quickstart:

- A **saved PCI compliance report** that filters incidents by your PCI policies
- The ability to **run it on demand** for any date range
- A **CSV export** of PCI incidents for audit evidence
- **Monthly scheduled delivery** to your compliance team (if configured)

## What This Report Tells Auditors

When sharing this report during a PCI DSS audit:

1. **Policy Enforcement**: The report shows your organization actively monitors for credit card data
2. **Incident Volume**: How many PCI violations were detected (demonstrates the system is working)
3. **Response Actions**: Status column shows incidents were reviewed and resolved
4. **Trend Data**: Monthly reports show whether PCI risk is increasing or decreasing

## Next Steps

1. **Add a HIPAA report**: Same process with filters set to HIPAA policies
2. **Create a compliance dashboard**: Combine PCI + HIPAA + GDPR reports into a single dashboard (see workflow.md Section 4)
3. **Add discovery findings**: Include Network Discover scan results showing where PCI data was found at rest
4. **API automation**: For more sophisticated reporting, use the REST API (see advanced.md)
5. **SIEM integration**: Forward DLP incidents to your SIEM for correlation with other security events
