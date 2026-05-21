# PPS/PoD Rule Creation and Email Firewall — Quickstart

> Get your first PPS Email Firewall rule working with minimal configuration. All defaults accepted where applicable.
> Time estimate: 20–30 minutes (plus 5–30 minutes propagation wait before testing)
> Prerequisites: PPS/PoD instance provisioned; admin credentials

---

## Before You Start

**Required:**
- PPS or PoD admin console access (browser-based)
- Admin role assigned to your account
- Knowledge of your inbound policy route name (default is `default_inbound`; verify this in System > Policy Route before proceeding)

**Optional prerequisite reading:**
- If using Quarantine as the rule disposition: create a quarantine folder first (Email Firewall > Quarantine management). Attempting to set a Quarantine disposition without a pre-created folder will fail.
- If using keyword-based content conditions: create a Dictionary first (Dictionaries management screen). Navigation path is INCOMPLETE in current documentation — consult your PPS admin guide.

**Evidence:** B [S2], C [V2, V3]

---

## Step 1: Verify Your Inbound Policy Route

Navigate to: **PPS Admin Console > System (top navigation) > Policy Route (left menu)**

Confirm that `default_inbound` exists in the route list. If your organization uses a custom route name, record the exact name — you will use it in Step 3.

No configuration changes are needed here unless your inbound route does not exist.

**Evidence:** B [S2], C [V3 ~0:45]

---

## Step 2: Open the Email Firewall Rule List

Navigate to: **PPS Admin Console > Email Firewall > Rules**

This screen shows all existing firewall rules in execution order (top = first to fire).

Click **Add Rule**.

**Evidence:** B [S2], C [V2 ~0:30 to ~1:00]

---

## Step 3: Configure the Rule Header

| Field | Set To | Notes |
|-------|--------|-------|
| Rule ID | A descriptive alphanumeric name (e.g., `inbound-block-test`) | Must be unique; appears in logs |
| Enable | **Off** (leave off until validated) | You will turn it On in Step 6 |

**Evidence:** C [V2 ~1:00]

---

## Step 4: Add the Route Condition (Critical)

In the **Conditions** section, click **Add Condition**.

| Field | Set To | Why |
|-------|--------|-----|
| Condition Type | Route | Scopes rule to inbound traffic only |
| Condition Value | `default_inbound` (or your custom inbound route name from Step 1) | Prevents rule from firing on outbound or relay traffic |

Add any additional conditions your rule requires (sender address, IP range, content pattern, etc.).

**WARNING:** If you skip the Route condition, the rule applies to ALL mail including outbound relay. This is the most common PPS firewall misconfiguration. Always add the Route condition first.

**Evidence:** C [V2 ~2:00]

---

## Step 5: Set the Disposition

In the **Dispositions** section:

| Field | Set To | Notes |
|-------|--------|-------|
| Delivery Method | `Quarantine` (for blocking/holding) or `Deliver Now` (for explicit allow) | Quarantine requires a pre-existing folder |
| Quarantine Folder | Select the pre-created folder name | Only visible when Delivery Method = Quarantine |

**Evidence:** C [V2 ~2:30], B [S2]

---

## Step 6: Save and Set Execution Order

Click **Save** to create the rule.

Back in the **Email Firewall > Rules** list:
1. Find your new rule in the list.
2. Drag it to the correct position relative to existing rules. Rules fire from top to bottom. Most specific rules (like targeted sender allows) should be positioned above broad content rules.

**Evidence:** C [V9 ~0:30]

---

## Step 7: Enable the Rule

In the **Email Firewall > Rules** list, find your rule and set **Enable = On**.

**Evidence:** C [V2 ~0:30]

---

## Wait for Propagation

After enabling the rule, wait **5–30 minutes** before testing. Rule changes are not applied instantaneously. Testing immediately after enabling will produce false negatives.

**Evidence:** C [V2 ~3:00]

---

## Verify It Works

Use the PPS Smart Search (or XSOAR command `proofpoint-pps-smart-search`) to trace messages that should have matched your rule. Filter by sender, recipient, time window, and expected action (Quarantine or Deliver Now).

If testing Quarantine, confirm the message appears in the target quarantine folder via **Email Firewall > Quarantine** or XSOAR command `proofpoint-pps-quarantine-messages-list`.

**Evidence:** C [S16], C [V14 (Smart Search video)]

---

## Next Steps

- For all configuration options including Conditions, Dispositions, PDR, RV, Rate Control, and Digest: see [advanced.md](advanced.md)
- For the full prerequisite chain and dependency graph: see [prerequisites.md](prerequisites.md)
- For known gotchas, common mistakes, and workarounds: see [gotchas.md](gotchas.md)
