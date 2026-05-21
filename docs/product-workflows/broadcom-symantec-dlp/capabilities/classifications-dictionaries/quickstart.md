# Classifications & Dictionaries — Quickstart Guide
## Broadcom Symantec DLP (Enforce Server, version 16.x/25.x/26.x)

> **Goal:** Fastest path to creating a PCI classification using built-in credit card data identifiers.
> **Time estimate:** 10-15 minutes.
> **Prerequisites:** Enforce Server running, at least one detection server registered, Oracle DB operational.

---

## The 5-Step Fast Path

```
Step 1: Create a new policy from the PCI DSS template
Step 2: Review the built-in credit card data identifier configuration
Step 3: Add a financial terminology keyword condition (optional)
Step 4: Assign to a policy group
Step 5: Deploy in test mode and verify classification
```

---

## Step 1: Create Policy from PCI DSS Template

**Navigation:** Manage > Policies > Policy List > New Policy > Template List

1. Navigate to **Manage > Policies > Policy List**
2. Click **New Policy** > **Template List**
3. Search for "PCI" in the template search box
4. Select **"PCI DSS - Credit Card Numbers"**
5. Click **Next**

```
+=========================================================================+
|  New Policy -- Select Template                                           |
+=========================================================================+
|  Search: [PCI               ]  [Filter]                                  |
|                                                                          |
|  [x] PCI DSS - Credit Card Numbers                                      |
|  [ ] PCI DSS - All Policy Templates                                     |
|  [ ] Payment Card Industry Data Security Standard                        |
|                                                                          |
|                                                          [Next >]        |
+=========================================================================+
```

**What the template gives you:**
- Pre-configured detection rule using the "Credit Card Number" data identifier
- Luhn algorithm validation (built-in, automatic)
- Default threshold: 1 unique credit card number
- Default severity: High
- Default look-in: Body + Attachments

[S1, S4, V16] Evidence: A

---

## Step 2: Review the Data Identifier Configuration

The template opens in the policy editor. Click the **Detection** tab.

```
+=========================================================================+
|  Policy: PCI DSS - Credit Card Numbers                                   |
+=========================================================================+
|  [General] [Detection] [Groups] [Response]                    [Save]     |
+-------------------------------------------------------------------------+
|                                                                          |
|  Detection Rules                                     [+ Add Rule]       |
|  +-------------------------------------------------------------------+  |
|  | Rule 1: Credit Card Number Detection (High)         [Edit]        |  |
|  |   Condition: Content Matches Data Identifier                      |  |
|  |     Data Identifier: Credit Card Number                           |  |
|  |     Minimum Matches: 1 (Unique)                                   |  |
|  |     Breadth: Medium                                               |  |
|  |     Look In: Body, Attachments                                    |  |
|  |     Severity: 1 - High                                            |  |
|  +-------------------------------------------------------------------+  |
|                                                                          |
+=========================================================================+
```

Review the pre-configured settings:

| Setting | Template Default | Keep Default? | Notes |
|---------|-----------------|---------------|-------|
| Data Identifier | Credit Card Number | Yes | Covers all brands (Visa, MC, Amex, etc.) with Luhn validation |
| Minimum Matches | 1 | Yes (for PCI compliance) | PCI requires detecting even a single card number |
| Match Counting | Unique | Yes | Counts distinct card numbers |
| Breadth | Medium | Yes | Catches dashed and spaced formats, good balance |
| Look In | Body + Attachments | Modify: Add Subject | Users sometimes put card numbers in email subjects |
| Severity | 1 - High | Yes | PCI data is always high severity |

**Recommended modification:** Click **Edit** on the rule and check **Message Subject** in the "Look In" section. Click **Save Rule**.

[S1, S4, S8] Evidence: A

---

## Step 3: (Optional) Add Financial Dictionary Condition

For a more precise PCI classification, add a second rule that combines credit card detection with financial terminology.

1. Click **+ Add Rule**
2. Select **Content Matches Keyword**
3. Enter financial terms (one per line):

```
+=========================================================================+
|  Add Detection Rule                                                      |
+=========================================================================+
|  Rule Type: [Content Matches Keyword]                                    |
|                                                                          |
|  Enter keywords (one per line):                                          |
|  +--------------------------------------------------+                    |
|  | cardholder                                        |                    |
|  | account number                                    |                    |
|  | expiration date                                   |                    |
|  | CVV                                               |                    |
|  | billing address                                   |                    |
|  | payment processing                                |                    |
|  | merchant ID                                       |                    |
|  +--------------------------------------------------+                    |
|                                                                          |
|  Matching:                                                               |
|    [ ] Case sensitive                                                    |
|    [x] Match whole words only                                            |
|                                                                          |
|  Minimum Matches: [2   ] (2+ financial terms must appear)                |
|                                                                          |
|  Look In:                                                                |
|    [x] Message Body     [x] Attachments                                  |
|    [x] Message Subject   [ ] Envelope                                    |
|                                                                          |
|  Severity: (*) 2 - Medium                                                |
|                                                                          |
|                                               [Cancel]  [Save Rule]      |
+=========================================================================+
```

**What you now have:** Two detection rules in the same policy:
- Rule 1 (from template): Credit card number detected = High severity
- Rule 2 (your addition): Financial terms detected = Medium severity
- Both rules evaluate independently; any match creates an incident at its assigned severity

[S1, S8] Evidence: A

---

## Step 4: Assign to Policy Group and Set Mode

1. Click the **General** tab
2. Set Policy Mode to **"Test Without Notifications"**
3. Verify Policy Group is **"Default Policy Group"**

```
+=========================================================================+
|  Policy: PCI DSS - Credit Card Numbers                                   |
+=========================================================================+
|  [General] [Detection] [Groups] [Response]                    [Save]     |
+-------------------------------------------------------------------------+
|                                                                          |
|  Policy Name:  [PCI DSS - Credit Card Numbers                ]           |
|                                                                          |
|  Policy Group: [Default Policy Group     ] [v]                           |
|                                                                          |
|  Policy Mode:                                                            |
|    (*) Test Without Notifications  <-- Start here                        |
|    ( ) Test With Notifications                                           |
|    ( ) Enabled                                                           |
|    ( ) Disabled                                                          |
|                                                                          |
+=========================================================================+
```

4. Click **Save**

---

## Step 5: Deploy and Verify Classification

### Verify Deployment

The policy deploys automatically to all detection servers in the Default Policy Group.

Navigate to **System > Servers and Detectors > Overview** and confirm all servers show green status.

### Test Classification

Send a test email with a known test credit card number:

```
Subject: Test PCI Classification
Body: Please process payment for order 12345.
      Card: 4111-1111-1111-1111
      Exp: 12/26
      Cardholder: Test User
```

**Test card numbers (industry-standard test values -- NOT real cards):**
- Visa: 4111-1111-1111-1111
- Mastercard: 5500-0000-0000-0004
- Amex: 3400-0000-0000-009

### Verify Incident Creation

Navigate to **Incidents > Network** (or Endpoint)

```
+=========================================================================+
|  Incidents                                                               |
+=========================================================================+
|  +-------------------------------------------------------------------+  |
|  | ID    | Severity | Policy                      | Matches | Status |  |
|  |-------|----------|-----------------------------|---------+--------|  |
|  | 10001 | High     | PCI DSS - Credit Card Nums  | 1 CC    | New    |  |
|  |       | Medium   | (Rule 2: Financial terms)    | 3 terms |        |  |
|  +-------------------------------------------------------------------+  |
|                                                                          |
+=========================================================================+
```

Click the incident to verify:
- **Matched Identifier:** Credit Card Number (Visa)
- **Luhn Validation:** Passed
- **Financial Terms Matched:** "cardholder", "expiration date", "payment processing"
- **Classification Result:** High severity (highest matching rule wins)

---

## What You Just Built

```
+----------------------------------------------------+
|  Policy: PCI DSS - Credit Card Numbers              |
+----------------------------------------------------+
         |
         +-- Rule 1: Credit Card Data Identifier
         |   (Built-in, Luhn validated, Medium breadth)
         |   Severity: HIGH
         |
         +-- Rule 2: Financial Keywords
         |   (7 PCI-related terms, threshold: 2)
         |   Severity: MEDIUM
         |
         +-- Mode: Test Without Notifications
         |
         +-- Deployed: Default Policy Group (all servers)
```

---

## Next Steps

| Step | What | Time | Where |
|------|------|------|-------|
| 1 | Monitor incidents for 2 weeks, check false positive rate | Ongoing | Incidents list |
| 2 | Add exceptions for known PCI-authorized systems | 10 min | Policy > Exceptions |
| 3 | Add response rule (email notification to PCI team) | 5 min | Policy > Response tab |
| 4 | Create EDM profile for cardholder database | 30-60 min | Manage > Data Profiles > EDM |
| 5 | Upgrade to "Test With Notifications" mode | 1 min | Policy > General > Mode |
| 6 | Add more dictionaries (medical terms for HIPAA, legal terms for privilege) | 15 min each | See: advanced.md |
| 7 | Configure MIP label integration | 30 min | See: workflow.md Component 4 |
| 8 | Graduate to "Enabled" mode (blocking) | 1 min (after 4+ weeks of tuning) | Policy > General > Mode |

---

## Common Mistakes to Avoid

| Mistake | Impact | Instead Do |
|---------|--------|-----------|
| Skipping the keyword/dictionary rule | Relies solely on card numbers; misses financial context documents | Add at least a basic financial terms keyword rule |
| Setting dictionary threshold to 1 | Every email mentioning "payment" triggers | Set threshold to 2+ for general financial terms |
| Enabling blocking mode immediately | Legitimate payment processing emails blocked | Stay in Test mode for 4+ weeks |
| Not checking "Look In: Subject" | Card numbers in email subject lines missed | Always check Body + Subject + Attachments |
| Using real credit card numbers for testing | Real card data in incident database | Use industry test numbers (4111-1111-1111-1111) |
| Not documenting the classification design | Next admin does not understand the tiered approach | Document the classification tiers and their rationale |

---

*End of quickstart. Total time: 10-15 minutes. You now have a PCI classification policy with credit card detection and financial terminology keywords in test mode.*
