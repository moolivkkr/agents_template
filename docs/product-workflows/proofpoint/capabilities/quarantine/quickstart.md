# Quarantine Management — Quickstart

> Configure quarantine categories, digest notifications, and retention in one pass.
> Time estimate: 10 minutes
> Prerequisites: Proofpoint Essentials provisioned, admin role, spam policy configured.

---

## Before You Start

- Spam policy should be configured first so quarantine categories are populated: see [../spam/quickstart.md](../spam/quickstart.md).
- You need the Organization Admin role.

---

## Step 1: Set Release Permissions for Quarantine Categories

Navigate to: **Company Settings > Quarantine > Categories**

Configure per-category release permissions:

| Category | Recommended Setting | Reason |
|----------|-------------------|--------|
| Spam | Allow user release | End users know their own expected mail best [A — S1] |
| Bulk | Allow user release | Users can determine if newsletters are wanted |
| Policy/DLP | Admin-only | Prevents users from bypassing compliance controls [D — S19] |
| Phishing | Admin-only (fixed — cannot change) | By design [D — S19] |
| Virus | Admin-only (fixed — cannot change) | By design [A — S1] |

---

## Step 2: Configure Quarantine Digest

Navigate to: **Company Settings > Quarantine > Digest**

Set these values:
- **Digest Enabled:** Checked
- **Digest Frequency:** Daily
- **Digest Exclusions:** Exclude the Adult category (prevents adult content subjects from appearing in users' inbox digest)

---

## Step 3: Set Retention Period

Navigate to: **Company Settings > Quarantine > Retention** (or Quarantine Settings)

- **Retention Period:** 30 days (default)

Leave at default unless you have a compliance requirement for a longer hold.

---

## Verify It Works

1. Wait for the next scheduled digest delivery.
2. Check that a test user receives a digest email listing their quarantined messages.
3. Confirm the user can click a link in the digest to release spam-classified messages.
4. Confirm virus-quarantined messages do NOT appear in the user-releasable digest.

---

## Next Steps

- For full category and digest configuration options: see [workflow.md](workflow.md).
- For PPS quarantine folder management (API-based): see [workflow.md](workflow.md) Advanced section.
- For known issues: see [gotchas.md](gotchas.md).
