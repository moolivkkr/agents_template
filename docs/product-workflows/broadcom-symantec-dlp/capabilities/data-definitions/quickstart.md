# Data Definitions — Quickstart Guide
## Broadcom Symantec DLP (Enforce Server, version 16.x/25.x/26.x)

> **Goal:** Fastest path from zero to detecting US Social Security Numbers using a built-in data identifier.
> **Time estimate:** 10-15 minutes.
> **Prerequisites:** Enforce Server running, at least one detection server registered, Oracle DB operational.

---

## The 4-Step Fast Path

```
Step 1: Create a new policy
Step 2: Add a detection rule using the US SSN data identifier
Step 3: Assign to a policy group
Step 4: Deploy in test mode
```

---

## Step 1: Create a New Policy

**Navigation:** Manage > Policies > Policy List > New Policy > Create New Policy

1. In the Enforce console, navigate to **Manage > Policies > Policy List**
2. Click **New Policy** in the upper right
3. Select **Create New Policy** (not Template List -- we are building from scratch to learn the data identifier workflow)
4. Enter a policy name: **"SSN Detection - Quickstart"**
5. Enter description: **"Detects US Social Security Numbers using built-in data identifier"**

```
+=========================================================================+
|  New Policy -- General                                                   |
+=========================================================================+
|                                                                          |
|  Policy Name:  [SSN Detection - Quickstart                   ]           |
|                                                                          |
|  Description:  [Detects US Social Security Numbers using     ]           |
|                [built-in data identifier.                    ]           |
|                                                                          |
|  Policy Group: [Default Policy Group     ] [v]                           |
|                                                                          |
|  Policy Mode:                                                            |
|    (*) Test Without Notifications                                        |
|    ( ) Test With Notifications                                           |
|    ( ) Enabled                                                           |
|    ( ) Disabled                                                          |
|                                                                          |
|                                               [Cancel]  [Next >]         |
+=========================================================================+
```

**Keep the default mode: "Test Without Notifications".** This mode detects SSNs and creates incidents but does not block anything or notify users. Safe for learning.

[S1, S4, V16] Evidence: A

---

## Step 2: Add Detection Rule with SSN Data Identifier

After creating the policy, the Detection tab opens.

1. Click **+ Add Rule**
2. From the dropdown, select **Content Matches Data Identifier**
3. Configure the rule as follows:

```
+=========================================================================+
|  Add Detection Rule                                                      |
+=========================================================================+
|                                                                          |
|  Rule Type: [Content Matches Data Identifier]                            |
|                                                                          |
|  Data Identifier:  [US Social Security Number  ] [v]                     |
|                                                                          |
|  Minimum Matches:  [1         ]                                          |
|  Match Counting:   (*) Count unique values only                          |
|                    ( ) Count all matches                                  |
|                                                                          |
|  Breadth:  (*) Narrow  (XXX-XX-XXXX format only)                         |
|            ( ) Medium  (with or without dashes)                           |
|            ( ) Wide    (any 9-digit sequence passing validation)          |
|                                                                          |
|  Look In:                                                                |
|    [x] Message Body                                                      |
|    [x] Message Subject                                                   |
|    [x] Attachments                                                       |
|    [ ] Envelope (sender/recipient headers)                               |
|                                                                          |
|  Severity:  (*) 1 - High   ( ) 2 - Medium   ( ) 3 - Low   ( ) 4 - Info |
|                                                                          |
|                                               [Cancel]  [Save Rule]      |
+=========================================================================+
```

### Settings Explained

| Setting | Value | Why |
|---------|-------|-----|
| Data Identifier | US Social Security Number | Built-in identifier with format validation + area number range check |
| Minimum Matches | 1 | Detect even a single SSN |
| Match Counting | Unique | Counts distinct SSN values (not repeated occurrences of the same SSN) |
| Breadth | Narrow | Only matches XXX-XX-XXXX format. Fewest false positives. Start here. |
| Look In | Body + Subject + Attachments | Covers all message components where SSNs might appear |
| Severity | 1 - High | SSN exposure is always high severity |

4. Click **Save Rule**

[S1, S4, S8] Evidence: A

---

## Step 3: Verify Policy Group Assignment

1. Click the **Groups** tab
2. Verify the policy is assigned to **Default Policy Group**
   - Default Policy Group deploys to ALL detection servers
   - For quickstart, this is correct -- you want all channels monitored

```
+=========================================================================+
|  Policy: SSN Detection - Quickstart                                      |
+=========================================================================+
|  [General] [Detection] [Groups] [Response]                    [Save]     |
+-------------------------------------------------------------------------+
|                                                                          |
|  Policy Group: [Default Policy Group     ] [v]                           |
|                                                                          |
|  This policy will be deployed to:                                        |
|    - All Network Monitor servers                                         |
|    - All Network Prevent servers (Email + Web)                           |
|    - All Endpoint Prevent servers                                        |
|    - All Network Discover servers                                        |
|                                                                          |
+=========================================================================+
```

3. Click **Save**

[S1, S4] Evidence: A

---

## Step 4: Deploy and Verify

1. After saving, the policy appears in the Policy List with status **"Test Without Notifications"**
2. The policy is automatically deployed to all detection servers in the Default Policy Group
3. Wait 1-2 minutes for policy propagation to network servers, or up to 15 minutes for endpoint agents

### Verify Deployment

Navigate to **System > Servers and Detectors > Overview**

Confirm all detection servers show a green status indicator. The new policy is now active.

### Test Detection

Send a test email containing a test SSN in the standard format:

```
Subject: Test SSN Detection
Body: This is a test. SSN: 078-05-1120
```

**Note:** Use a known test SSN (078-05-1120 was used in a famous Lifelock advertisement and is widely known as a test value). Do NOT use real SSNs for testing.

### Verify Incident Creation

Navigate to **Incidents > Network** (or **Incidents > Endpoint** depending on where the test was captured)

```
+=========================================================================+
|  Incidents > Network                                                     |
+=========================================================================+
|                                                                          |
|  +-------------------------------------------------------------------+  |
|  | ID    | Severity | Policy                    | Matches | Status   |  |
|  |-------|----------|---------------------------|---------|----------|  |
|  | 10001 | High     | SSN Detection - Quickstart | 1       | New      |  |
|  +-------------------------------------------------------------------+  |
|                                                                          |
+=========================================================================+
```

Click the incident to see:
- **Matched Policy:** SSN Detection - Quickstart
- **Data Identifier:** US Social Security Number
- **Match Count:** 1 (unique)
- **Matched Value:** 078-05-1120 (or partially masked depending on RBAC settings)

---

## What You Just Built

```
+------------------------------------+
|  Policy: SSN Detection - Quickstart |
+------------------------------------+
         |
         v
+------------------------------------+
|  Detection Rule                     |
|  Type: Data Identifier              |
|  Identifier: US SSN                 |
|  Breadth: Narrow                    |
|  Threshold: 1 unique match          |
|  Severity: High                     |
+------------------------------------+
         |
         v
+------------------------------------+
|  Deployed To                        |
|  Default Policy Group               |
|  (all detection servers)            |
+------------------------------------+
```

---

## Next Steps (in order of complexity)

| Step | What | Time | Where |
|------|------|------|-------|
| 1 | Add a response rule (email notification to admin) | 5 min | See: authoring-rules quickstart |
| 2 | Add more data identifiers (Credit Card, IBAN) | 5 min per identifier | See: workflow.md Technology 1 |
| 3 | Adjust breadth to Medium (catch undashed SSNs) | 1 min | Edit rule > Breadth > Medium |
| 4 | Create an EDM profile for employee records | 30-60 min | See: workflow.md Technology 3 |
| 5 | Create an IDM profile for confidential documents | 30-60 min | See: workflow.md Technology 4 |
| 6 | Train a VML model for financial reports | 2-4 hours | See: workflow.md Technology 5 |
| 7 | Graduate from Test to Enabled mode | 1 min (after tuning) | Policy > General > Policy Mode |

---

## Common First-Day Mistakes to Avoid

| Mistake | Impact | Instead Do |
|---------|--------|-----------|
| Setting breadth to Wide | Massive false positives (phone numbers, zip codes trigger) | Start Narrow, expand to Medium only after tuning |
| Enabling blocking mode immediately | Legitimate emails blocked, employee backlash | Stay in Test mode for 2-4 weeks minimum |
| Not checking "Look In: Subject" | SSNs in email subject lines are not detected | Always check Body + Subject + Attachments |
| Using a real SSN for testing | Your real SSN appears in the incident database | Use known test values (078-05-1120) |
| Skipping the incident verification step | No proof the policy is working | Always verify at least one test incident |

---

*End of quickstart. Total time: 10-15 minutes. You now have a working SSN detection policy in test mode.*
