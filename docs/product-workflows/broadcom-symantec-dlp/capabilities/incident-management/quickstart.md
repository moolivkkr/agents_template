# Quickstart: Review and Resolve Your First DLP Incident

> **Time to complete:** 15-20 minutes
> **Result:** You will review a real DLP incident, investigate the matched content, and resolve it
> **Prerequisites:** Enforce Server accessible, at least one incident exists (from a policy violation or discovery scan)

---

## Step 1: Log In to the Enforce Console (1 minute)

1. Open your browser and navigate to `https://enforce-server/ProtectManager`
2. Log in with your DLP administrator or analyst credentials
3. You should see the Enforce Server dashboard

---

## Step 2: Navigate to the Incident Queue (1 minute)

1. Click **Incidents** in the top navigation
2. Choose the channel where you expect incidents:
   - **Network** -- email, web, and passive monitoring incidents
   - **Endpoint** -- USB, clipboard, print, browser incidents
   - **Discover** -- data-at-rest scanning incidents
3. If unsure, start with **Network** (most common source of incidents)

---

## Step 3: Find an Incident to Review (2 minutes)

1. The incident list shows all incidents for the selected channel
2. By default, incidents are sorted by date (newest first)
3. Use the **Severity** filter to show only **High** severity incidents
4. Use the **Status** filter to show only **New** incidents (not yet reviewed)
5. Click on any incident ID to open it

---

## Step 4: Review the Incident Detail (5 minutes)

The incident detail view has several tabs. Review each:

### Detection Tab
- **Policy**: Which policy was violated (e.g., "PCI DSS - Credit Card Numbers")
- **Rule**: Which specific detection rule matched
- **Detection Server**: Which server caught the violation
- **Protocol**: How the data was being moved (SMTP, HTTP, USB, etc.)
- **Match Count**: How many matches were found

### Matched Content Tab
- This shows the **actual sensitive data detected**, with matches highlighted
- Example: You might see `4111-****-****-1234` (a credit card number, partially masked)
- Review the context around the match -- is this genuinely sensitive?

### Message/File Tab (for email/web incidents)
- **Sender**: Who sent the data
- **Recipient**: Where it was going
- **Subject**: Email subject line
- **Attachment**: File name if data was in an attachment
- For endpoint incidents: user name, hostname, application, destination (USB device, printer, etc.)

### History Tab
- Shows what has happened to this incident since creation
- Automated actions (block, notify) already executed will be listed here

---

## Step 5: Make a Decision (2 minutes)

Based on your review, decide:

| Decision | When | Action |
|----------|------|--------|
| **False Positive** | The matched content is not actually sensitive (e.g., test data, public information) | Change Status to "False Positive" |
| **Legitimate Violation** | Real sensitive data was being transferred inappropriately | Continue to Step 6 |
| **Need More Info** | Cannot determine without additional context | Add a note and set status to "In Process" |

---

## Step 6: Resolve the Incident (5 minutes)

### If False Positive:
1. In the incident detail, change **Status** dropdown to **False Positive**
2. Add a **Note**: "Confirmed false positive. Matched content is test/sample data."
3. Click **Save**
4. Done -- consider tuning the policy to reduce false positives

### If Legitimate Violation:
1. Change **Status** to **In Process** (you are now working on it)
2. Add a **Note** describing what you found: "Confirmed PCI violation. 3 credit card numbers in email attachment to external recipient."
3. Check if the data was already blocked:
   - Look at the History tab -- if an Automated Response rule ran "Block Message", the data was stopped
   - If not blocked (monitoring-only policy), consider whether the data exposure needs escalation
4. Take appropriate action:
   - **If a Smart Response is available**: Click the Smart Response dropdown and select an action (e.g., "Notify Manager", "Assign Training")
   - **If no Smart Response**: Manually notify the appropriate team, then document in notes
5. Change **Status** to **Resolved**
6. Add a final **Note**: "Resolved. Email was blocked by automated response. User notified of policy violation."
7. Click **Save**

---

## Step 7: Verify Your Work (2 minutes)

1. Navigate back to the incident list
2. Your resolved incident should now show the updated status
3. Click it again to verify:
   - Status is correct (False Positive or Resolved)
   - Notes are saved
   - History tab shows your status changes

---

## What You Have Now

After completing this quickstart:

- You know how to navigate the incident queue and find incidents
- You can read and interpret incident details (matched content, sender, context)
- You can make triage decisions (false positive vs. legitimate violation)
- You can update incident status and add investigation notes
- You understand the basic incident resolution workflow

## Next Steps

1. **Set up filters**: Save frequently used filter combinations as reports
2. **Learn Smart Responses**: Ask your DLP admin which Smart Response rules are available
3. **Review advanced topics**: See advanced.md for API-based incident management, SOAR integration, and bulk operations
4. **Understand escalation**: Learn your organization's escalation process for high-severity incidents
5. **Policy feedback**: When you find false positives, report them to the policy admin for tuning
