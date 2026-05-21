# Archive & Retention Policies — Quickstart

> Set archive retention period to match your compliance requirements immediately after archive provisioning.
> Time estimate: 5 minutes
> Prerequisites: Proofpoint Essentials Archive add-on provisioned, admin role.

---

## Before You Start

- The Essentials Archive is a **paid add-on** — verify it is provisioned before proceeding. If the Archive menu is not visible in your admin console, the add-on is not active.
- Know your organization's regulatory retention requirement (see table below) before accepting any defaults.
- The **default retention period is 12 months (1 year) — this is too short for most regulated industries.**

### Retention Requirements by Regulation

| Regulation | Minimum |
|-----------|---------|
| HIPAA | 6 years |
| SEC Rule 17a-4 | 7 years |
| FINRA Rule 4511 | 3 years |
| SOX Section 802 | 7 years |
| No regulation | 1 year (Proofpoint default) |

---

## Step 1: Open Archive Retention Settings

Navigate to: **Proofpoint Essentials Archive admin > Settings > Retention**

---

## Step 2: Set Retention Period

Set **Retention Period — Years** and **Retention Period — Months** to match your regulatory requirement.

Example — HIPAA: Set Years = 6, Months = 0.

Maximum value: 10 years combined.

Click **Save**.

---

## Step 3: Leave Legal Hold Off

**Company Legal Hold** (Settings > Legal Hold) defaults to Off. Leave it Off unless your legal team has instructed you to activate a litigation hold.

---

## Verify It Works

1. Confirm the Settings > Retention page shows your configured retention period after saving.
2. If archive is newly provisioned, send a test email and verify it appears in the archive search interface (allow up to 30 minutes for indexing — UNKNOWN exact time [U — ASSUMPTION]).

---

## Next Steps

- For legal hold activation when litigation arises: see [workflow.md](workflow.md) Step 4.
- For gotchas about the default 1-year period and compliance risks: see [gotchas.md](gotchas.md).
- For archive search configuration: see [workflow.md](workflow.md) Advanced section (INCOMPLETE — fields not fully documented).
