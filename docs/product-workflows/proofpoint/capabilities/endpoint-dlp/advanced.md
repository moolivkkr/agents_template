# Data Security / Endpoint DLP Policies — Advanced Configuration Reference

> Capability: endpoint-dlp | Product: Proofpoint Data Security | Generated: 2026-05-21
> All screens and fields documented, including those omitted from the quickstart.

---

## Screen 1: Agent Policies List

**Navigation:** Administration > Endpoint > Agent Policies
**Source:** [S8] — A [docs.public.analyze.proofpoint.com/admin/agent_policies_setting_up.htm]

### Fields

| Field | Type | Required | Default | Options | Validation | Description |
|-------|------|----------|---------|---------|------------|-------------|
| Search / Filter | text | No | null | — | — | Filter policy list by name; real-time filter |
| Policy (row) — Priority | display | — | — | — | — | Shown in column; editable via drag or priority field on edit |
| Policy (row) — Status | display | — | — | Active / Inactive | — | Whether the policy is enabled |
| Policy (row) — Realm | display | — | — | — | — | Which Realm this policy governs |
| Policy (row) — Signal Type | display | — | — | DLP Only / ITM | — | What the agent captures |

### Actions

| Action | Trigger | Result |
|--------|---------|--------|
| Add Policy | Button | Opens Add Agent Policy — General Settings modal |
| Edit | Row action | Opens policy for editing; Signal Type field LOCKED after initial save |
| Delete | Row action | Permanently deletes policy; agents in Realm fall back to Default Account Policy |
| Drag to reorder | Drag handle | Changes priority order for policies in the same Realm |

### Edge Cases

- Deleting a policy immediately falls back agents to the next-highest-priority policy for the Realm, or to the Default Account Policy if no others exist. There is no soft-delete or deactivation confirmation dialog — deletion is immediate. Source: [S8] — A, behavior inferred from documentation structure — E (inference)
- The Default Account Policy always appears at the bottom of the list and cannot be deleted. Source: [S7] — A

---

## Screen 2: Add / Edit Agent Policy — General Settings

**Navigation:** Administration > Endpoint > Agent Policies > Add Policy (or row Edit)
**Source:** [S7] — A, [S8] — A

### Fields

| Field | Type | Required | Default | Options | Validation | Description |
|-------|------|----------|---------|---------|------------|-------------|
| Policy Name | text | Yes | null | — | Must be unique within tenant | Human-readable identifier |
| Realm | dropdown | Yes | null | All configured Realms | Must select existing Realm | The endpoint group this policy governs |
| Priority | number | Yes | UNKNOWN — not documented | Integer | Integer; lower value = higher priority among policies for same Realm | Evaluation order when multiple policies assigned to same Realm |
| Signal Type | radio | Yes | DLP Only | DLP Only, ITM | — | DLP Only: file events only. ITM: all user activity. **IRREVERSIBLE** after save — cannot be changed. |
| Enabled | toggle | No | UNKNOWN — assumed Enabled | Enabled / Disabled | — | Whether agents receive and enforce this policy |

### Conditional Fields

- When **Signal Type = ITM**: the Details tab (Screen 3) exposes additional Then-settings including screenshot capture and extended activity monitoring options not available in DLP Only mode.
- When **Signal Type = DLP Only**: screenshot capture and keystroke logging settings are hidden in the Details tab.

### Edge Cases

- **Signal Type is IRREVERSIBLE**: Once saved, the Signal Type field is locked and cannot be edited. To change signal type, the policy must be deleted and recreated from scratch. All If/Then condition blocks configured in the Details tab are lost. Source: [S7] — A (architecture description implies immutability); confirmed as **ASSUMPTION** [U] for the "locked field" UI behavior specifically, since the lock mechanism is not explicitly stated in accessible docs.
- **Priority default placement**: New policies are placed at UNKNOWN priority position in the Realm's policy list. Verify and manually adjust after creation. Source: [S8] — A (priority management described but default value not stated).

---

## Screen 3: Agent Policy — Details Tab (If/Then Logic)

**Navigation:** Administration > Endpoint > Agent Policies > [Policy] > Details tab
**Source:** [S9] — A [docs.public.analyze.proofpoint.com/admin/agent_policies_details.htm], [Video 16 ~1:00] — C

### Fields

| Field | Type | Required | Default | Options | Validation | Description |
|-------|------|----------|---------|---------|------------|-------------|
| If — Category | dropdown | Yes (per block) | null | Username, User Group, OS Type, Network Location, Device Type, [INCOMPLETE — full option list not published] | — | Attribute evaluated for this condition block |
| If — Value | text or multiselect | Yes (per block) | null | Depends on Category | — | Specific value to match (e.g., "administrator", "Finance Group") |
| If — Operator | radio | Yes | AND | AND, OR | — | Logical combinator when multiple If blocks exist |
| Then — File Activity Monitoring | toggle | No | UNKNOWN | Enabled / Disabled | — | Enable file read/write/move activity capture for matched agents |
| Then — DLP Toggle | toggle | No | Enabled | Enabled / Disabled | — | When Enabled: limits signal to DLP file events. When Disabled: activates expanded activity capture (relevant for ITM signal type policies). |
| Then — Prevention Rules | multiselect | No | null | All created Prevention Rules | — | Prevention rules that fire for agents matching these conditions |
| Then — Screenshots | toggle | No | UNKNOWN | Enabled / Disabled | Only visible when parent policy Signal Type = ITM | Capture screenshots of user activity for matched agents |
| Then — [Additional ITM settings] | various | No | UNKNOWN | — | Only visible when Signal Type = ITM | INCOMPLETE — additional ITM-specific Then-settings not enumerated in accessible Grade-A sources |

### Conditional Fields

- **Then — Screenshots**: only visible when the parent Agent Policy has Signal Type = ITM.
- **Then — DLP Toggle (disabled)**: only meaningful in ITM-signal policies. Disabling it for a DLP-only policy has no additional effect since ITM capture is already restricted at the Signal Type level.

### Edge Cases

- An If/Then block with no If conditions applies the Then settings to ALL agents in the Realm — equivalent to a default/catch-all within this policy. This is not visually flagged in the UI as a "catch-all" configuration. Source: [S9] — A
- Multiple If/Then blocks within one policy: the first matching block's Then settings apply. If no block matches, the Default Account Policy's settings govern the agent. Source: [S9] — A (architecture implied)
- **OS Type filter** (Windows / Mac / Unix / Both): available in If conditions and useful for mixed-OS environments. This field is mentioned in Video 16 at ~1:00 but not prominently documented in the official admin guide. Source: [Video 16 ~1:00] — C

---

## Screen 4: Default Account Policy

**Navigation:** Administration > Endpoint > Agent Policies > Default Account Policy (pre-existing)
**Source:** [S7] — A

### Fields

Same field schema as Agent Policy General Settings and Details tab. Key behavioral differences:

| Behavioral Difference | Description | Source |
|----------------------|-------------|--------|
| Cannot be deleted | The Default Account Policy persists permanently in the tenant | [S7] — A |
| Automatically assigned to all Realms | All Realms inherit the Default Account Policy as lowest-priority fallback | [S7] — A |
| Inheritable | Individual Realms can inherit or override this policy's settings | [S7] — A |

### Edge Cases

- Modifying the Default Account Policy affects ALL Realms that rely on it as a fallback. Review the impact before editing. Source: [S7] — A

---

## Screen 5: Detection Rules — List View

**Navigation:** Administration > Policies > Rules
**Source:** [S10] — A [docs.public.analyze.proofpoint.com/rules/rules_detection.htm], [S12] — A

### Fields

| Field | Type | Required | Default | Options | Validation | Description |
|-------|------|----------|---------|---------|------------|-------------|
| Search | text | No | null | — | — | Filter rules by name |
| Filter by Tags | multiselect | No | null | All configured tags | — | Show only rules with selected tags |

### Actions

| Action | Result | Notes |
|--------|--------|-------|
| New Rule | Opens detection rule wizard | 4-step wizard (Assignment, Condition, Actions, Review) |
| Edit (row) | Opens rule for edit | Saves as new version on save |
| View Versions (row) | Opens version history modal | Shows all historical versions with date, author, summary |
| Rollback (in version modal) | Reverts to selected version | Saved as new version (rollback is non-destructive to version history) |
| Delete (row) | Permanently deletes rule | No undelete. Rule is removed from all Rule Sets it was assigned to. |
| Manage Tags (row) | Opens tag assignment modal | Add/remove tags; create new tags inline |

### Edge Cases

- **100-rule limit**: the tenant has a default maximum of 100 combined active rules (detection + prevention). Exceeding this requires a support request to Proofpoint to increase the limit. Source: [S12] — A

---

## Screen 6: New Detection Rule — 4-Step Wizard

**Navigation:** Administration > Policies > Rules > New Rule
**Source:** [S10] — A, [Video 16 ~2:00–3:00] — C

### Step 1 — Assignment Fields

| Field | Type | Required | Default | Options | Validation | Description |
|-------|------|----------|---------|---------|------------|-------------|
| Rule Name | text | Yes | null | — | Must be unique within tenant | Human-readable identifier |
| Rule Sets | multiselect | No | null | All configured Rule Sets | — | Assign to one or more Rule Sets; rule only fires on agents in Realms linked to assigned Rule Sets. Leave empty = rule never fires. |
| Order Priority | number | Yes | UNKNOWN | Integer 1–1000 | Must be integer | Evaluation order within Rule Set. Higher number = fires first. **INVERTED** relative to Agent Policy priority. |
| Tags | multiselect | No | null | All configured tags | — | Organizational labels for filtering |

### Step 2 — Condition Fields

| Field | Type | Required | Default | Options | Validation | Description |
|-------|------|----------|---------|---------|------------|-------------|
| Condition Source | radio | Yes | null | Existing (library), Threat Library, Custom | — | How condition criteria are defined |
| Condition (Existing) | dropdown | Yes (if Existing) | null | Pre-built conditions from library | — | Select a condition from the library |
| Threat Library scenario | dropdown / tree | Yes (if Threat Library) | null | 300+ threat scenarios | — | Select from Insider Threat Library |
| Custom condition fields | dynamic form | Yes (if Custom) | null | INCOMPLETE — full field list not documented | — | Manually define condition criteria |
| Filters | multiselect / form | No | null | User group, OS type, network location, [INCOMPLETE] | — | Narrow condition scope |

### Step 3 — Actions Fields

| Field | Type | Required | Default | Options | Validation | Description |
|-------|------|----------|---------|---------|------------|-------------|
| Severity | dropdown | Yes | UNKNOWN (likely Low/Informational) | Low, Medium, High, Critical | — | Controls dashboard visibility and alert routing |
| Alert Management | toggle/checkbox | No | null | Enabled / Disabled | — | Generate managed alerts in Alert Management interface |
| Notifications — Email | form | No | null | — | — | Recipient addresses and message template for email notifications |
| Notifications — SMS | form | No | null | — | — | SMS recipient phone numbers |
| Notifications — Webhook | form | No | null | — | Valid URL required | Webhook endpoint URL and payload configuration |
| Tags (action-level) | multiselect | No | null | All configured tags | — | Tags automatically applied to events generated by this rule |
| Drop Matching | toggle | No | Disabled | Enabled / Disabled | — | When Enabled: matching events are suppressed from the alert pipeline. Used for noise reduction only. |

### Step 4 — Review

Summary view only. No new fields.

### Conditional Fields

- **Threat Library scenario** is only visible when Condition Source = Threat Library.
- **Custom condition form** is only visible when Condition Source = Custom.
- **Notification sub-forms** are visible regardless of Action settings but have no effect unless filled in.

---

## Screen 7: Prevention Rules

**Navigation:** Administration > Policies > Prevention Rules > New Prevention Rule
**Source:** [S11] — A [docs.public.analyze.proofpoint.com/rules/prevention_rules_overview.htm]

### Fields

| Field | Type | Required | Default | Options | Validation | Description |
|-------|------|----------|---------|---------|------------|-------------|
| Rule Name | text | Yes | null | — | Must be unique | Human-readable identifier |
| Action | radio or dropdown | Yes | null | Block, Prompt, Allow, Data Redaction for GenAI, File Retention | — | Real-time enforcement action |
| Scope / Target | form | Yes | null | Cloud sync, web upload, printing, [INCOMPLETE — full target list not documented] | — | Which file operations or destinations this rule applies to |
| Detectors / Data Classes | multiselect | Yes | null | All configured Data Class detectors | — | Which detector patterns trigger this rule. Detectors must be in Realm's Data Classes. |

### Conditional Fields

| Appears When | Field | Type | Description |
|-------------|-------|------|-------------|
| Action = Prompt | Justification dialog text | text | Message shown to user when prompted |
| Action = Prompt | Response options | multiselect | Options user can select as justification |
| Action = Allow | Allow conditions | form | Specific files, destinations, or users to allow |
| Action = Data Redaction for GenAI | Redaction pattern | form | Text patterns or data classes to redact from GenAI submissions. INCOMPLETE — specific fields not documented in accessible Grade-A sources. |
| Action = File Retention | Storage target | form | External storage destination for retained file copies |

### Prevention Scope Examples (documented)

| Scope | OS Support | Source |
|-------|-----------|--------|
| Block exfiltration to cloud sync folders (e.g., Google Drive) | Windows, Mac | [S11] — A |
| Block web file uploads | Windows only | [S11] — A |
| Block printing to local computers | Windows | [S11] — A |

### Edge Cases

- **Web file upload block is Windows-only**: attempting to enforce web upload block on Mac agents has no effect. Source: [S11] — A
- **Detector must be in Realm Data Classes**: if the prevention rule's configured detector is not listed in the Realm's Data Classes, the rule silently never triggers. No error or warning is displayed. Source: [S11] — A (cross-reference), corpus cross-reference [S7/S9/S11]

---

## Screen 8: Rule Versioning Modal

**Navigation:** Administration > Policies > Rules > [Rule] > View Versions
**Source:** [S10] — A

### Fields

| Field | Type | Description |
|-------|------|-------------|
| Version # | number | Sequential version identifier |
| Date Modified | timestamp | When this version was saved |
| Modified By | text | User who made the change |
| Change Summary | text | INCOMPLETE — whether Proofpoint captures a change summary field is not confirmed in accessible docs |

### Actions

| Action | Result |
|--------|--------|
| View | Read-only view of selected version's configuration |
| Rollback to this version | Creates new version identical to selected historical version; rollback is non-destructive |

---

## Screen 9: Tag Management Modal

**Navigation:** Administration > Policies > Rules > [Rule] > Manage Tags
**Source:** [S10] — A

### Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| Tag selection | multiselect | No | null | Assign existing tags to the rule |
| New Tag Name | text | No | null | Create a new tag inline |

---

## Sub-capability Coverage Reference

| Sub-capability | Screen(s) | Fields documented | Source |
|---------------|-----------|------------------|--------|
| 9.1 Agent Policy Creation (Add/Edit) | Screen 2 | 5 | [S8] — A |
| 9.2 DLP-Only vs ITM Signal Type Selection | Screen 2 — Signal Type field | 1 | [S7] — A |
| 9.3 If/Then Condition Logic Configuration | Screen 3 | 8 | [S9] — A |
| 9.4 Agent Policy Priority Management | Screen 1 (drag/reorder), Screen 2 (Priority field) | 1 | [S8] — A |
| 9.5 Default Account Policy Customization | Screen 4 | Inherited | [S7] — A |
| 9.6 Detection Rule Creation (from scratch/conditions/Threat Library) | Screen 6 | 14 (across 4 steps) | [S10] — A |
| 9.7 Detection Rule Severity Assignment | Screen 6 — Step 3 Severity field | 1 | [S10] — A |
| 9.8 Detection Rule Notification Configuration | Screen 6 — Step 3 Notifications | 3 (Email/SMS/Webhook) | [S10] — A |
| 9.9 Prevention Rule Creation | Screen 7 | 4 core + conditional | [S11] — A |
| 9.10 Prevention Rule Actions (Block/Prompt/Allow) | Screen 7 — Action field | 3 of 5 options detailed | [S11] — A |
| 9.11 Data Redaction for GenAI | Screen 7 — Action = Data Redaction for GenAI | INCOMPLETE | [S11] — A, [S28] — C |
| 9.12 File Retention Rules | Screen 7 — Action = File Retention | Partial | [S11] — A |
| 9.13 Endpoint Rule On-Demand Policy | INCOMPLETE — screen path not documented | INCOMPLETE | [S12] — A |
| 9.14 Rule Versioning and Rollback | Screen 8 | 4 | [S10] — A |
| 9.15 Tag Management for Rules | Screen 9 | 2 | [S10] — A |
| 9.16 Realm Assignment and Rule Sets | Realm screen (INCOMPLETE) | Partial | [S10] — A, [S7] — A |

---

## Known Incomplete Areas

| Area | What Is Missing | Additional Research Needed |
|------|----------------|---------------------------|
| Custom condition syntax | Full list of condition field names, operators, and valid values for Custom condition type | Proofpoint Data Security admin guide authenticated section at docs.public.analyze.proofpoint.com |
| Realm configuration screen | Exact navigation path and all fields for Realm creation and agent enrollment | Same as above |
| Data Classes / Detector configuration | How to create, modify, and assign Data Classes to Realms | Same as above |
| Data Redaction for GenAI fields | Specific configuration fields within the GenAI redaction action | [S28] blog mentions feature; UI walkthrough not available |
| Endpoint On-Demand Policy | How to configure and trigger on-demand policy runs | [S12] mentions the concept; no configuration detail |
| Agent check-in / policy push interval | How long before deployed agents receive a new or changed policy | Not documented in accessible sources |
| Justification prompt configuration | Exact fields for Prompt action's user-facing dialog text and response options | [S11] describes the action; UI fields not enumerated |
| Rule Set creation screen | Navigation path and fields for creating/managing Rule Sets | Cross-referenced in [S10] but screen not directly documented |
