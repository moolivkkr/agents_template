# Email Filtering Policies (Proofpoint Essentials) — Quickstart

> Get a working inbound email filter in Proofpoint Essentials using minimal configuration.
> Time estimate: 10–15 minutes (plus 5–30 minute propagation wait)
> Prerequisites: Active Proofpoint Essentials organization, at least one verified email domain, Organization Admin role

---

## Before You Start

Confirm the following are true before creating your first filter:

1. **Organization is provisioned** — you can log in to the Proofpoint Essentials admin console
2. **At least one domain is configured** — check Settings > Domains for your verified domain
3. **You have Organization Admin role** — confirm in Users & Groups > [your account] > Role = Organization Admin
4. **MX records are live** — email is routing through Proofpoint (not just DNS-configured)

If any of these are missing, see [prerequisites.md](prerequisites.md) before continuing.

---

## What This Quickstart Builds

A single inbound filter that **quarantines emails with executable attachments** from any sender. This is the most common first filter new administrators deploy and demonstrates the full create-verify cycle.

---

## Step 1: Navigate to Filter Policies

Go to: **Security Settings > Email > Filter Policies**

Make sure you are on the **Inbound** tab (this is the default).

Source: [V20 ~0:30] (Grade B — Proofpoint Essentials training video, 2023)

---

## Step 2: Click New Filter

Click the **New Filter** button at the top right of the Inbound filter list.

---

## Step 3: Fill in the Required Fields

| Field | Value to Enter | Why |
|-------|---------------|-----|
| Name / Description | `Block Executable Attachments` | Descriptive name for audit trail |
| Scope | `Company` | Applies to all users in the organization |
| Priority | `Normal` | Default; adjust later if needed |
| Condition Type | `Attachment Type` | Match on file category, not extension |
| Operator | `IS ANY OF` | Match any executable category |
| Condition Value | `Windows executable components, installers, other executable components` | Pre-defined categories for executables |
| Primary Action | `Quarantine` | Holds for admin review without bouncing |

Leave all other fields at their defaults (all toggles off, no secondary actions).

Source: [S1] (Grade A — Proofpoint Essentials Admin Guide)

---

## Step 4: Save the Filter

Click **Save Filter** at the bottom of the form.

You will be returned to the Filter Policies list. Confirm your new filter appears in the Inbound list with status **Enabled**.

---

## Step 5: Wait for Propagation

**Do not test immediately.** Filter changes take **5–15 minutes** to become active, and up to **30 minutes** in some cases.

Set a timer for 10 minutes before proceeding to verification.

Source: [V20 ~4:00, V2 ~3:00] (Grade B — vendor training videos) — **NOTE: propagation time is not stated in official docs; this is video-sourced finding only.**

---

## Step 6: Verify It Works

1. From an external email account (outside your organization), send an email with a test `.exe` file attached to any address in your organization
2. Check the Proofpoint Essentials quarantine console (Security Settings > Quarantine) for the test message
3. Confirm it appears in quarantine with the filter name `Block Executable Attachments` as the reason

If the message is not in quarantine after 30 minutes, see [gotchas.md](gotchas.md) — start with G1 (propagation delay) and G2 (scope/precedence override).

---

## Next Steps

- **Add more conditions:** Edit the filter to add a second condition (e.g., `Attachment Name IS ANY OF *.bat, *.cmd, *.ps1`) to extend coverage to script files
- **Create an outbound filter:** See [advanced.md](advanced.md) for outbound encryption trigger configuration
- **Understand scope hierarchy:** See [workflow.md](workflow.md) — the scope processing order (User > Group > Company) is the most important concept for avoiding silent filter bypasses
- **Review known issues:** See [gotchas.md](gotchas.md) before deploying more aggressive rules
- **Add safe/blocked senders:** See [workflow.md](workflow.md) — Sub-capability 1.9 for organization-level allow/deny lists
