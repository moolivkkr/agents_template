# Email Encryption Policies — Quickstart

> Get outbound email encryption working with a subject-line keyword trigger.
> Time estimate: 20 minutes (plus 5–30 minutes propagation)
> Prerequisites: Proofpoint Essentials account with Email Encryption module licensed

---

## Before You Start

1. **Confirm encryption is licensed.** The Encrypt action will not appear in the filter UI unless the Email Encryption module is provisioned on your account. Contact your Proofpoint account representative or check your admin portal license page before proceeding. [S14, Grade B]

2. **Confirm you have Admin role.** Organization-level filter creation requires the Admin role. [S1, Grade A]

3. **No other prerequisites.** You do not need DLP policies configured first for the subject-keyword trigger path.

---

## Step 1: Open Filter Policies

Navigate to: **Security Settings > Email > Filter Policies**

Click the **Outbound** tab.

[B — Video 7 ~0:45, V7]

---

## Step 2: Create a New Outbound Encryption Filter

Click **New Filter**.

Set the following fields:

| Field | Value | Notes |
|-------|-------|-------|
| Filter Name | Encrypt Sensitive Outbound | Any descriptive name |
| Direction | **Outbound** | REQUIRED — Encrypt action is invisible on Inbound |
| Scope | **Company** | REQUIRED — Encrypt action is invisible on Group or User |
| Priority | High | Ensures encryption fires before other outbound filters |
| If (Condition Type) | Email Subject | |
| Operator | CONTAIN(S) ANY OF | |
| Condition Value | [ENCRYPT] | Users add this to subject to trigger encryption |
| Do (Primary Action) | **Encrypt** | Only appears when Direction=Outbound AND Scope=Company |
| Enforce Completely Secure SMTP Delivery | Checked | Enables TLS fallback: delivers via TLS when partner supports it; uses Proofpoint Encryption when TLS fails |
| Stop Processing Additional Filters | Off (default) | Leave Off |

Click **Save Filter**.

[B — Video 7 ~1:30–2:00, V7; A — S1 for field names]

---

## Step 3: Wait for Propagation

Do not test immediately. Filter changes take **5–30 minutes** to propagate across the system.

[B — Video 2 ~3:00, V2; B — Video 20 ~4:00, V20]

---

## Step 4: Verify It Works

1. From an internal mailbox, send a test email to an **external** address (outside your organization).
2. Include **[ENCRYPT]** anywhere in the subject line.
3. Wait a few minutes, then check the external recipient's inbox.
4. The recipient should receive a notification with a **Proofpoint Secure Reader link**.
5. Click the link — the recipient registers or authenticates and reads the message in Secure Reader.

If the Encrypt action does not fire, check:
- Was propagation time (30 min) fully elapsed?
- Is Direction=Outbound and Scope=Company on the filter?
- Is the Encryption module visible in your licensed features?

[E — Inferred from S14 Secure Reader description and V7 workflow; D — S17]

---

## Next Steps

- For content-scan triggers (auto-encrypt PHI, PII): see [advanced.md](advanced.md) — Step 2: Trigger type decision
- For TLS fallback–only configuration: see [advanced.md](advanced.md) — TLS Fallback screen
- For message expiration, revocation, trusted partner setup: see [advanced.md](advanced.md)
- For known limitations: see [gotchas.md](gotchas.md)
- For full field reference: see [workflow.md](workflow.md)
