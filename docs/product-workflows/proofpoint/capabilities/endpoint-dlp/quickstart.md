# Data Security / Endpoint DLP Policies — Quickstart

> Get Endpoint DLP working with minimal configuration. DLP-only signal type. Default options accepted where available.
> Time estimate: 30–45 minutes (assuming Realm and Data Classes already exist)
> Prerequisites: Realm must exist; Data Classes / Detectors must be configured; agents must be deployed to endpoints

---

## Before You Start

Verify these objects exist. If they do not, configure them first (full paths are partially INCOMPLETE per corpus gap — consult Proofpoint admin for Realm and Data Class screens):

1. **Realm** — at least one Realm must exist with endpoints enrolled. Without a Realm, Agent Policies cannot be assigned.
   - Source: [S7] — A [docs.public.analyze.proofpoint.com/admin/agent_policies_overview.htm]

2. **Data Classes / Detectors** — at least one Data Class must be associated with the target Realm. Prevention rules will not trigger without this.
   - Source: [S11] — A [docs.public.analyze.proofpoint.com/rules/prevention_rules_overview.htm]

3. **Proofpoint agents deployed** — agents must be installed on target endpoints and reporting into the Proofpoint Data Security console.
   - Source: [S7] — A

---

## Step 1: Create a Detection Rule

Navigate to: **Administration > Policies > Rules > New Rule**

**Step 1a — Assignment:**
Set: Rule Name = `[descriptive name, e.g., "Sensitive File Upload to Cloud Storage — Detect"]`
Set: Rule Sets = `[select the Rule Set linked to your target Realm]`
Set: Order Priority = `500` (mid-range default; adjust later)

**Step 1b — Condition:**
Set: Condition Source = `Threat Library`
Set: Threat Library scenario = `[select the scenario most relevant to your use case, e.g., data upload to cloud storage]`

**Step 1c — Actions:**
Set: Severity = `High`
Leave all notification fields empty for initial deployment (add notifications after baseline period)
Leave Drop Matching = OFF

Click: **Save Rule**

Time: ~10 minutes
Source: [S10] — A [docs.public.analyze.proofpoint.com/rules/rules_detection.htm], [Video 16 ~2:00] — C

---

## Step 2: Create a Prevention Rule (optional — detection-only deployments skip this step)

Navigate to: **Administration > Policies > Prevention Rules > New Prevention Rule**

Set: Rule Name = `[descriptive name, e.g., "Block Cloud Sync Exfil — Prevent"]`
Set: Action = `Prompt` (recommended for initial deployment — collects justification without hard blocking)
Set: Scope / Target = `[cloud sync destination, e.g., Google Drive sync folder]`
Set: Detectors = `[select the Data Class detector matching your sensitive data type]`

Click: **Save**

Time: ~5 minutes
Source: [S11] — A [docs.public.analyze.proofpoint.com/rules/prevention_rules_overview.htm]

---

## Step 3: Create Agent Policy — General Settings

Navigate to: **Administration > Endpoint > Agent Policies > Add Policy**

Set: Policy Name = `[descriptive name, e.g., "Standard DLP Policy — Finance Realm"]`
Set: Realm = `[select your target Realm]`
Set: Priority = `1` (if this is the only policy for this Realm; adjust if multiple policies coexist)
Set: Signal Type = `DLP Only`

**STOP — CONFIRM Signal Type before proceeding. DLP Only vs ITM is IRREVERSIBLE after save. DLP Only is correct for most deployments. ITM is required only if full user activity monitoring is needed.**

Set: Enabled = `ON`

Click: **Next / Save**

Time: ~5 minutes
Source: [S8] — A [docs.public.analyze.proofpoint.com/admin/agent_policies_setting_up.htm]

---

## Step 4: Configure If/Then Logic

Navigate to: **Administration > Endpoint > Agent Policies > [your new policy] > Details tab**

For a simple all-users deployment, leave If conditions empty. This applies the Then settings to ALL agents in the Realm.

Set: Then — File Activity Monitoring = `ON`
Set: Then — DLP Toggle = `ON` (keeps signal DLP-only, consistent with General Settings)
Set: Then — Prevention Rules = `[select the prevention rule created in Step 2, if applicable]`

Click: **Save**

Time: ~5 minutes
Source: [S9] — A [docs.public.analyze.proofpoint.com/admin/agent_policies_details.htm]

---

## Step 5: Verify Policy is Active

Navigate to: **Administration > Endpoint > Agent Policies**

Confirm:
- Your policy appears in the list with Status = Active
- The Realm column shows the correct Realm
- Priority is correct (Default Account Policy should be at lowest priority as catch-all)

Wait for agent check-in (UNKNOWN — agent policy push interval not documented in accessible sources). Endpoint agents will receive the updated policy on their next configuration sync.

Time: ~5 minutes
Source: [S8] — A

---

## Verify It Works

After agents receive the updated policy:

1. Navigate to **Administration > Alerts** (or the detection events dashboard)
2. Perform a test action that matches your detection rule's Threat Library scenario on a test endpoint
3. Confirm a High-severity detection event appears in the dashboard
4. If prevention rule was configured with Prompt action: confirm the justification dialog appears on the endpoint when the matching action is attempted

Source: [S10] — A, [Video 16 ~3:00] — C

---

## Next Steps

- For all configurable fields including optional ones: see [advanced.md](advanced.md)
- For full prerequisite chain with Mermaid dependency diagram: see [prerequisites.md](prerequisites.md)
- For known limitations and workarounds: see [gotchas.md](gotchas.md)
- For GenAI prompt redaction, file retention, and on-demand endpoint rules: see [advanced.md](advanced.md)
- To add SMS/email/webhook notifications to detection rules: see [advanced.md](advanced.md) — Detection Rule Step 3 section
