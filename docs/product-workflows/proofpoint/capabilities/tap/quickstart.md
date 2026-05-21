# Targeted Attack Protection (TAP) — Quickstart

> Get TAP URL Defense working with minimal configuration. Defaults accepted for all optional fields.
> Time estimate: 15 minutes (after licensing is confirmed)
> Prerequisites: PPS/PoD account provisioned, TAP module licensed

---

## Before You Start

Confirm these are complete before proceeding:

1. **PPS/PoD account active** — you can log into the Proofpoint admin console
2. **TAP module licensed** — contact your Proofpoint account representative or check Administration > Account Management to confirm TAP is on your subscription
3. **Admin role** — you have administrator access to the PPS/PoD console

If TAP is not yet licensed, no configuration in this guide will have any effect. License confirmation must come first.

---

## Step 1: Enable URL Defense (5 minutes)

Navigate to: **Administration > Account Management > Features**

Set: **URL Defense** = **Enabled**

Click **Save**.

> URL Defense is disabled by default after TAP provisioning, even if Proofpoint documentation implies it activates automatically. The vendor tutorial video at Administration > Account Management > Features shows this explicit enable step is required. Source: Video 5 ~0:30 [B — vendor training video]

> Wait 5–30 minutes after saving before testing. Changes require propagation time. Source: Videos 2, 20 [B]

**What this does:** All inbound email URLs are now rewritten to `https://urldefense.com/` format. When a user clicks a link, Proofpoint performs real-time analysis before allowing the browser to navigate to the destination.

---

## Step 2: Enable Attachment Defense (5 minutes)

Navigate to: **TAP > Settings > Attachment Defense**

Set: **Attachment Defense Mode** = enabled (accept default mode for now)

Click **Save**.

> Exact field name and options are not fully documented in accessible sources — the TAP Settings screen is behind the Proofpoint authentication wall. Navigate to the Attachment Defense tab within TAP Settings and enable the feature. Source: [B, S2 — training outline]

**What this does:** Suspicious email attachments are submitted to a sandbox environment before or after delivery. Confirmed-malicious attachments are quarantined. Attachments are encrypted at rest during analysis and deleted after verdict. Source: [C, S22]

---

## Step 3: Verify TAP Is Active (5 minutes)

Navigate to: **TAP Dashboard**

Confirm: Dashboard shows active URL Defense and Attachment Defense modules

Send a test email to your organization containing any external link. After 5–30 minutes of propagation time, the link in the delivered message should show the `urldefense.com` rewrite prefix.

> If rewritten URLs do not appear, return to Step 1 and confirm the URL Defense toggle is saved as Enabled. Source: Video 5 [B]

---

## What You Now Have

- All inbound email URLs rewritten and inspected at click-time
- Suspicious attachments sandboxed and malicious ones quarantined
- TAP Dashboard available for threat visibility

---

## Next Steps

- To protect specific high-risk users with browser isolation: see [advanced.md](advanced.md) — URL Isolation for VIPs/VAPs section
- To enable TAP only for a specific group (pilot rollout): see [advanced.md](advanced.md) — Per-Group TAP Enablement section
- To suppress TAP alerts for trusted senders (pen-test vendors): see [advanced.md](advanced.md) — Sender Exemptions section
- For known issues and gotchas: see [gotchas.md](gotchas.md)
- For complete field reference: see [workflow.md](workflow.md)
