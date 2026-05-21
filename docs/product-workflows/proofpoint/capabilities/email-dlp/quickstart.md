# Data Loss Prevention (DLP) Policies — Quickstart
## Proofpoint Email DLP (Essentials)

> Get a basic outbound DLP rule running with SSN detection, quarantine action, and admin notification.
> Time estimate: 20–30 minutes (plus 5–30 min propagation)
> Prerequisites: Admin access to Proofpoint Essentials console; DLP module licensed

---

## Before You Start

Confirm the following before starting. Each item is required:

| Check | Where to Verify | Source |
|-------|----------------|--------|
| Admin account with Essentials console access | Login to Essentials console — verify you see Security Settings menu | [S1, Grade A] |
| DLP module licensed | Contact Proofpoint account team or check Features page | [S24, Grade B] |
| Proofpoint Encryption licensed (optional — needed for Encrypt action only) | Contact account team | [S14, Grade B] |

---

## Step 1: Navigate to Filter Policies — Outbound

Navigate to: **Security Settings > Email > Filter Policies > Outbound tab**

Source: Video 7 ~0:45 [Grade B]; Video 20 ~0:30 [Grade B].

---

## Step 2: Create the DLP Filter

Click **New Filter**. Fill in the following required fields:

| Field | Value | Notes |
|-------|-------|-------|
| Filter Name | "Block SSN — Outbound" (or descriptive equivalent) | Internal only — not shown to end users |
| Direction | **Outbound** | Required for DLP; enables Encrypt action |
| Scope | **User** | Start at User scope for safe testing — see Step 5 |
| Priority | Normal | Default is acceptable for initial testing |
| Condition Type | **Email Message Content** | Matches message body and inline content |
| Operator | **CONTAINS ALL OF** | Preferred over CONTAINS ANY OF to reduce false positives |
| Condition Value | (enter your smart identifier name, e.g., "SSN") | Must reference a configured smart identifier |
| Primary Action | **Quarantine** | Safer than Reject during initial rollout |

Source: [S1, Grade A]; Video 20 [Grade B].

Click **Save Filter**.

---

## Step 3: Add Admin Notification (Recommended)

While still in the filter edit view, enable:

| Field | Value |
|-------|-------|
| Notify Admin | Checked |
| Tag Subject | Checked (optional — adds "[DLP ALERT]" to subject for visibility during testing) |

Source: Video 20 ~3:00 [Grade B].

---

## Step 4: Wait for Propagation

After saving, wait **5–30 minutes** before testing. Testing immediately after save produces false negatives because the rule has not yet propagated to all processing nodes.

Source: Videos 2, 20 [Grade B].

---

## Step 5: Test at User Scope, Then Promote

Send a test email from your own address containing a fake SSN pattern (e.g., "123-45-6789 — TEST ONLY") to an external address. Verify the message is quarantined.

Once verified:
1. Edit the filter and change Scope from **User** to **Group** (pilot team)
2. Monitor for 3–5 days; check quarantine for false positives
3. Edit the filter and change Scope to **Company** for production enforcement

Source: Video 20 ~4:30 [Grade B].

---

## Verify It Works

| Verification | How |
|-------------|-----|
| Message quarantined | Check quarantine console — the test message should appear under DLP/content category |
| Admin notification received | Check compliance team inbox for the notification |
| No false positives for normal mail | Monitor quarantine for 2–3 days after scope promotion |

---

## Common Failure Modes to Check

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Encrypt action not in dropdown | Scope is not Company, or Direction is not Outbound | Change Scope to Company + Direction to Outbound |
| Rule not firing | Propagation delay | Wait 5–30 min after save |
| DLP rule silent (never fires) | "Stop Processing Additional Filters" is ON in a higher-priority filter | Audit all higher-priority filters for this toggle |
| Per-user safe sender overrides blocking DLP | User-level filter override at Company scope | Audit per-user filter lists in User Management |

Source: Videos 2, 7, 20 [Grade B].

---

## Next Steps

- For all configuration options, including Encrypt integration, document fingerprinting, and PPS-specific DLP: see [advanced.md](advanced.md)
- For prerequisite dependencies and time estimates: see [prerequisites.md](prerequisites.md)
- For known issues and workarounds: see [gotchas.md](gotchas.md)
- For Adaptive Email DLP (behavioral AI): see [advanced.md](advanced.md) — Adaptive DLP section
