# Security Awareness Training Policies — Quickstart

> Get a training assignment and a phishing campaign running with minimal configuration. All defaults accepted.
> Time estimate: 20 minutes (10 min per workflow)
> Prerequisites: Proofpoint Essentials SAT organization provisioned; at least one user or group exists; at least one training module licensed

**Source for all steps:** [S3 — Proofpoint Essentials Security Awareness Admin Guide, April 2020]

---

## Before You Start

Confirm these are in place before starting:

1. **Proofpoint Essentials SAT is provisioned** — your organization has access to the SAT admin console
2. **Users exist** — at least one user or group is visible in Users & Groups
3. **A training module is licensed** — visible in Training > Assignments > Add Assignment > Modules with filter set to Licensed

If any of these are missing, SAT configuration cannot proceed. Contact your Proofpoint account team for provisioning.

---

## Path A: Create a Scheduled Training Assignment (~10 minutes)

### Step 1: Open the Assignment Creation Form

Navigate to: **Training > Assignments > Add Assignment**

### Step 2: Set Required Fields

| Field | Set To |
|-------|--------|
| Name | Any unique internal name (e.g., "Q1 Security Basics") |
| Type | Scheduled (default) |
| Start Date | Tomorrow's date (allows time for notification delivery) |
| Due Date | 30 days from start date |
| Modules | Select at least one module from the Licensed list |
| Users | Select the user group or individual users to assign |

Leave all other fields at defaults.

### Step 3: Save

Click **Save**. The assignment is created. Notification emails will be sent to assigned users at 12:01 AM Eastern Time on the Start Date.

### Verify It Works

On or after the Start Date, navigate to **Training > Assignments**. The assignment should show status Active. Users will see the training in their portal.

---

## Path B: Create a Drive-by Phishing Campaign (~10 minutes)

### Step 1: Open the Campaign Creation Form

Navigate to: **Phishing > Campaigns > Add Campaign > Drive-by**

### Step 2: Set Required Fields

| Field | Set To |
|-------|--------|
| Campaign Title | Any unique internal name (e.g., "Q1 Phishing Test") |
| Email Templates | Select 1-3 templates; filter by Language = English to start |
| Campaign Users | Select the same user group as the training assignment |
| Teachable Moment | Select any available option matching your preferred language |
| Schedule | Random (recommended for most groups) |
| Data Collection Period | 14 days (extend beyond the default 7 to capture slow openers) |

### Step 3: Save

Click **Save**. The campaign is created in Pending state. Emails will be distributed randomly to users on the scheduled dates.

### Verify It Works

Navigate to **Phishing > Campaigns**. The campaign row should show Pending status. After the scheduled send window, status changes to In Progress. Click the campaign to see delivery and click statistics.

---

## Next Steps

- For Duration (new-hire) assignments: see [advanced.md](advanced.md#duration-training-assignment)
- For Data Entry and Attachment campaign types: see [advanced.md](advanced.md#phishing-campaign-types)
- For Follow-Up campaigns targeting users who clicked: see [advanced.md](advanced.md#follow-up-campaign)
- For known issues and gotchas: see [gotchas.md](gotchas.md)
- For full field reference: see [workflow.md](workflow.md)
