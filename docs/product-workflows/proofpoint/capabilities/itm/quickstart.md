# ITM/ObserveIT Policy Configuration — Quickstart

> Get ITM monitoring operational with minimal configuration. All non-critical defaults accepted.
> Time estimate: 30–45 minutes
> Prerequisites: ITM On-Prem server deployed and licensed; admin or Config Admin account

---

## Before You Start

Confirm you have:
- Access to the ITM Web Console (admin or Config Admin role) [S6]
- ITM On-Prem server running (version 7.18.0 or current) [S4]
- Agents deployed to endpoints you want to monitor [S4]

No other capabilities require prior configuration for the basic monitoring path.

---

## Step 1: Verify Recording is Enabled (~2 minutes)

Navigate to: **Web Console → Configuration → System Policy Settings**

Check that **Enable Recording** is toggled ON (default: Enabled). [S4]

If it is ON, proceed to Step 2. If it is OFF, toggle it ON and click **Save**.

> Recording being OFF means no rules will fire, no screen captures will be taken, and no keystrokes will be captured — regardless of what rules are configured.

---

## Step 2: Set Session Timeout (~1 minute)

On the same **System Policy Settings** screen:

Set: **Session Timeout** = `15` (minutes — this is the default; adjust only if your organization requires shorter/longer inactivity windows) [S4]

Click **Save**.

---

## Step 3: Activate Insider Threat Library Rules (~15 minutes)

Navigate to: **Configuration → Alerts → Alert & Prevent Rules → Insider Threat Library**

The fastest path to coverage is the pre-built library of 300+ detection scenarios. [S5]

1. Apply filter: **Platform Filter** = your primary OS (Windows, Mac, or Both)
2. Apply filter: **Target User Group Filter** = `Everyday Users` (broadest applicable group for initial deployment)
3. Review the list — top-performing rules are already Active by default [S5]
4. Activate any additional rules relevant to your environment by clicking the **Activate** toggle on each

> No condition authoring is required for library rules — they are ready to fire immediately after activation.

---

## Step 4: Create Your First Alert Rule (~10 minutes)

Navigate to: **Configuration → Alerts → Alert & Prevent Rules → New Rule**

| Field | Set To |
|-------|--------|
| Rule Type | `Alert Rule` |
| Rule Name | `[Descriptive name — e.g., "Mass File Copy to USB — Everyday Users"]` |
| OS Type | Your primary platform (Windows/Mac or Both) |
| Priority | `100` (a safe mid-range starting value) |
| Condition | `Threat Library` (select a relevant pre-built scenario) |
| Action | `Alert` |
| Severity | `High` (set explicitly — do not leave at default) |

Click through wizard steps → **Save**. [S6, Video 16]

> Always set Severity explicitly. Rules without a severity assignment may default to Informational and will not appear in dashboards filtered to High/Critical alerts.

---

## Step 5: Verify It Works

1. Navigate to **Configuration → Alerts → Alert & Prevent Rules**
2. Confirm your new rule appears in the list with status Active
3. Confirm Insider Threat Library rules are showing as Active for your selected platform [S5]
4. Trigger a test activity matching your alert rule condition from a monitored endpoint
5. Check the alert console for a fired alert within 1–5 minutes

---

## Next Steps

- For full field reference and all system settings: see [advanced.md](advanced.md)
- For prevention rules (blocking behavior): see Step 4 in [workflow.md](workflow.md)
- For known issues and gotchas: see [gotchas.md](gotchas.md)
- For complete prerequisite chain: see [prerequisites.md](prerequisites.md)
