# Spam Policy Configuration — Quickstart

> Get organizational spam filtering configured with sensible defaults.
> Time estimate: 5 minutes
> Prerequisites: Proofpoint Essentials organization provisioned, admin role assigned.

---

## Before You Start

- You must have the organization admin role in Proofpoint Essentials.
- No other capabilities need to be configured first.

---

## Step 1: Open Spam Settings

Navigate to: **Security Settings > Email > Spam Settings**

---

## Step 2: Accept Default Sensitivity

Leave **Spam Trigger Level** at the system default.

Rationale: The system default is calibrated for balanced detection. Adjust only after observing false positives or missed spam in production. [A — S1]

---

## Step 3: Enable Inbound Sender DNS

Confirm **Inbound Sender DNS** is checked (it is enabled by default).

This performs MX record validation and rejects mail from private IP ranges — a significant connection-level protection layer. [A — S1]

---

## Step 4: Save

Click **Save**.

Wait 5–30 minutes before testing. Changes propagate across the mail processing infrastructure before taking effect. [B — Video 21, ~1:00]

---

## Verify It Works

1. Send a test message from an external account.
2. Check message delivery in the Proofpoint message logs.
3. Verify spam-classified messages appear in the quarantine console.

---

## Next Steps

- To tune the spam threshold: see [workflow.md](workflow.md) Step 2.
- To configure quarantine digest notifications for quarantined spam: see [../quarantine/quickstart.md](../quarantine/quickstart.md).
- For known issues and gotchas: see [gotchas.md](gotchas.md).
