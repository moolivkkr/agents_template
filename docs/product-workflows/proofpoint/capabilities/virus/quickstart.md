# Virus Policy Configuration — Quickstart

> Anti-virus scanning is enabled by default — no action required for basic protection.
> This quickstart only applies if you need to exempt specific senders from AV scanning.
> Time estimate: 2 minutes
> Prerequisites: Proofpoint Essentials organization provisioned, admin role assigned.

---

## Before You Start

- AV scanning is **always active** in Proofpoint Essentials. You do not need to enable it.
- Only proceed if you have a specific trusted sender whose email Proofpoint is incorrectly blocking due to encrypted attachments or AV false positives.
- If you have no bypass need, there is nothing to configure here.

---

## Step 1: Open Virus Settings

Navigate to: **Company Settings > Virus**

---

## Step 2: Add AV Bypass Entry

In the **AV Bypass Address** field, enter the sender's email address:

- Use `user@partner.com` (specific sender) — preferred
- Use `partner.com` (entire domain) — only if multiple senders from the same partner domain need bypassing

Click **Save**.

---

## Verify It Works

Wait 5–30 minutes, then send a test message from the exempted sender. Verify the message is delivered without AV blocking.

---

## Next Steps

- For AV bypass entry gotchas and security risks: see [gotchas.md](gotchas.md).
- For quarantine management of virus-detected messages: see [../quarantine/quickstart.md](../quarantine/quickstart.md).
