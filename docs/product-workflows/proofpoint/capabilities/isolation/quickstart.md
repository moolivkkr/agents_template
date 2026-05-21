# Browser/Email Isolation Policies — Quickstart

> Get Proofpoint Isolation protecting your highest-risk users with minimum viable configuration.
> Time estimate: 45–90 minutes (user provisioning time varies by method)
> Prerequisites: Proofpoint Isolation license; TAP provisioned (for VIP/VAP use case)

---

## Coverage Warning

**Isolation admin console field-level detail is INCOMPLETE** in the research corpus. Navigation paths are partially reconstructed from the data sheet (S15 — Grade B). The one confirmed navigation path is: **Isolation Console > Policies > Redirect Rules**. All other paths marked UNKNOWN require verification in the live Isolation Console.

---

## Before You Start

| Prerequisite | Notes |
|-------------|-------|
| Proofpoint Isolation licensed and provisioned | Contact your Proofpoint account team |
| Admin access to the Isolation Console | Separate portal from Email Protection and Data Security consoles |
| TAP provisioned (optional but recommended) | Required for VIP/VAP URL isolation — the highest-value use case |
| List of your VIP users (executives, finance, IT admins) | You will import this in Step 3 |

---

## Step 1: Provision Users in Isolation Console

**Navigate to:** Isolation Console > Users (exact path UNKNOWN — INCOMPLETE)

1. Connect your identity source (SSO/SAML, Proofpoint User Center, or manual import)
2. Verify your target user group (e.g., "Executives") appears in the user list
3. Do not proceed to policy creation until at least one user group is visible

**Why this step is first:** Browsing policies and redirect rules that are scoped to groups are silently non-functional until the group exists in the Isolation Console. [S15 — Grade B, inferred]

---

## Step 2: Create a Redirect Rule for High-Risk URL Categories

**Navigate to:** Isolation Console > Policies > Redirect Rules

This is the only confirmed navigation path in accessible documentation. [S15 — Grade B]

1. Click Create / New Redirect Rule
2. Set **URL Category** = Newly Registered Domains (and/or Uncategorized)
3. Set **User/Group Scope** = your highest-risk group (e.g., Executives, Finance)
4. Set **Action** = Isolate
5. Save the rule

**Why these categories first:** Newly Registered Domains and Uncategorized URLs are the most common phishing delivery vectors. Isolating them for high-risk users provides immediate protection with lower operational risk than isolating all web traffic. [E — Inferred from S15 protection capability descriptions]

---

## Step 3: Import VIP/VAP List from TAP

**Navigate to:** Isolation Console > Users / VIP-VAP (exact path UNKNOWN — INCOMPLETE)

1. Open the TAP Dashboard and note the current VAP (Very Attacked People) list
2. Export the VAP list from TAP Dashboard (format UNKNOWN — INCOMPLETE)
3. Import the VAP list into the Isolation Console
4. Assign your newly created Redirect Rule (from Step 2) to the imported VAP group
5. Set a calendar reminder to re-import this list after your next TAP threat review cycle

**Critical:** The VAP list does NOT automatically sync from TAP to Isolation. Manual re-import is required whenever the VAP roster changes. New VAPs are unprotected until you re-import. [Video 17 ~1:30 — Grade C; S15 — Grade B]

---

## Step 4: Create a Basic Browsing Policy for VIP/VAP Group

**Navigate to:** Isolation Console > Policies > Browsing Policies (exact path UNKNOWN — INCOMPLETE)

1. Click Create / New Browsing Policy
2. Set **Policy Name** = "VIP/VAP Strict Isolation"
3. Set **User Group** = the imported VAP group
4. Set **Access Level** = Limited (not Read-Only, which would prevent legitimate work; not Full Interactive, which allows credential entry on phishing sites)
5. Save the policy

[S15 — Grade B for per-group policy concept; field names Grade U — **ASSUMPTION**]

---

## Verify It Works

1. Using a test account that is in the VIP/VAP group, click a URL from a Proofpoint TAP-rewritten email
2. Verify the page opens in the Proofpoint Isolation container (the visual experience shows a distinct Proofpoint wrapper or URL indicator in the browser — confirmed in Video 18)
3. Attempt to navigate to a Newly Registered Domain in the test account's browser
4. Verify the page renders in isolation rather than the local browser

---

## Next Steps

- Add upload/download restrictions: see [advanced.md — Upload/Download Restrictions](advanced.md)
- Enable inline DLP for isolation sessions: see [advanced.md — Inline DLP](advanced.md)
- Configure user input controls to prevent credential theft: see [advanced.md — User Input Controls](advanced.md)
- For known issues: see [gotchas.md](gotchas.md)
- For the full field-level reference: see [workflow.md](workflow.md)
