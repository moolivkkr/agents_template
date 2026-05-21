# PPS/PoD Rule Creation and Email Firewall — Advanced Configuration Reference

> Product: Proofpoint Protection Server (PPS) / Proofpoint on Demand (PoD) 8.22.x
> Coverage note: PPS admin guide is behind authentication. Fields marked INCOMPLETE require
> verification against the authenticated admin guide. All documented fields carry evidence citations.

---

## 2.1 System > Policy Routes

**Navigation:** PPS Admin Console > System (top navigation) > Policy Route (left menu)
**Evidence:** B [S2], C [V3 ~0:45 to ~1:30]
**Product scope:** PPS on-premises and PoD. This menu item is NOT present in Proofpoint Essentials.

### Fields

| Field | Type | Required | Default | Options | Validation | Description | Source |
|-------|------|----------|---------|---------|------------|-------------|--------|
| Route Name | text | Yes | Pre-configured: `default_inbound`, `default_outbound` | Custom text | Unique string | Logical name for the mail flow lane. Referenced in Firewall rule Route conditions. | B [S2], C [V3] |
| Host/IP | text | No | null | FQDN or IP address | Valid hostname or IP | Next-hop relay host associated with this route. Used for policy-based email routing. | C [V3 ~1:30] |

### Edge Cases
- If a custom route name is used instead of `default_inbound`, all Firewall rules that hardcode `default_inbound` in their Route condition will silently not fire. Audit rule conditions after any route rename.
- Policy route configuration is a PPS/PoD-specific function. Essentials administrators do not have this menu.

**Evidence:** C [V3 ~0:45]

---

## 2.2 Email Firewall > Rules (Rule Creation)

**Navigation:** PPS Admin Console > Email Firewall > Rules > Add Rule
**Evidence:** B [S2], C [V2 ~0:30 to ~3:00, S20]

### Rule Header Fields

| Field | Type | Required | Default | Options | Validation | Description | Source |
|-------|------|----------|---------|---------|------------|-------------|--------|
| Rule ID | text | Yes | null | Free text | Alphanumeric, unique within rule list | Internal identifier. Appears in mail logs and XSOAR API results. NOT the execution order. | C [V2 ~1:00] |
| Enable | radio | Yes | Off | On, Off | — | Activates the rule. New rules default to Off. Anti-spoof rule ships as Off and must be explicitly enabled. | C [V2 ~0:30], D [community] |

### Rule List Ordering

| Field | Type | Required | Default | Options | Validation | Description | Source |
|-------|------|----------|---------|---------|------------|-------------|--------|
| Execution Position | drag-and-drop | Yes | Creation order | Positional | — | Visual position in rule list = execution order. Top = fires first. This is NOT determined by Rule ID. | C [V9 ~0:30] |

### Conditional Fields
- Enable field toggles between On and Off at any time without recreating the rule.
- Rules can be edited while Disabled (Off) without affecting live mail processing.

### Edge Cases
- Dragging rules in the list immediately changes execution order without a save step. Verify the order after reordering.
- The anti-spoof rule is pre-installed in PPS but ships disabled. It must be explicitly enabled via the Enable toggle.

---

## 2.3 Email Firewall > Rules > Conditions

**Navigation:** PPS Admin Console > Email Firewall > Rules > [Rule] > Conditions section
**Evidence:** B [S2], C [V2 ~1:00 to ~2:00]

### Conditions Fields

| Field | Type | Required | Default | Options | Validation | Description | Source |
|-------|------|----------|---------|---------|------------|-------------|--------|
| Add Condition (button) | button | — | — | — | — | Adds a new condition row to the rule. Multiple conditions use AND logic. | C [V2 ~1:00] |
| Condition Type | dropdown | Yes (per row) | null | Route; additional types INCOMPLETE — full list requires auth | Type-dependent | Attribute of the message to evaluate | B [S2], C [V2] |
| Route (condition value) | dropdown | Strongly recommended | null | `default_inbound`, `default_outbound`, custom route names | Must match a defined route name | Scopes rule to a specific mail flow lane. CRITICAL: omit = applies to all routes. | C [V2 ~2:00] |
| Condition Value / Pattern | text or dropdown | Yes (per row) | null | Type-dependent | Type-dependent (IP, email pattern, dictionary reference, regex) | Value to match against selected condition type. | B [S2] |

### INCOMPLETE: Condition Type Enumeration
The complete list of available Condition Types (beyond Route) is not documented in accessible sources. Known types inferred from training outline [S2] and XSOAR integration [S16] include connection-level attributes (sender IP, route) and likely include: sender address/domain, recipient address/domain, message content pattern, dictionary match. **Verification against authenticated PPS admin guide required.**

### Conditional Fields
- When Condition Type = Route: value dropdown is populated with defined Policy Routes
- When Condition Type = content/dictionary: value field likely references dictionary name (INCOMPLETE — exact behavior not documented)

### Edge Cases
- Multiple conditions on the same rule use AND logic (all must match). OR logic across conditions: UNKNOWN — not documented in accessible sources.
- Condition syntax for IP ranges (CIDR notation vs range): INCOMPLETE.

---

## 2.4 Email Firewall > Quarantine Folder Management

**Navigation:** PPS Admin Console > Email Firewall > [Quarantine management section]
**Evidence:** B [S2], C [S16 XSOAR integration]

### Fields

| Field | Type | Required | Default | Options | Validation | Description | Source |
|-------|------|----------|---------|---------|------------|-------------|--------|
| Folder Name | text | Yes | null | Custom text | Unique string | Identifier for the quarantine folder. Referenced in rule dispositions and API commands. | C [S16] |
| Folder Type / Module Association | dropdown | Yes | null | INCOMPLETE — module type options not enumerated | Must be a valid module type | Associates folder with filtering module (spam, virus, content/DLP, firewall). | B [S2] |

### API Operations on Quarantine Folders

| API Command | Action | Constraint | Source |
|-------------|--------|-----------|--------|
| `proofpoint-pps-quarantine-messages-list` | Search messages in a folder by sender, recipient, time | Requires folder name parameter | C [S16] |
| `proofpoint-pps-quarantine-message-release` | Release without further scanning | — | C [S16] |
| `proofpoint-pps-quarantine-message-resubmit` | Reprocess through filtering modules | — | C [S16] |
| `proofpoint-pps-quarantine-message-forward` | Forward to alternative recipients | — | C [S16] |
| `proofpoint-pps-quarantine-message-move` | Move to another folder | SAME MODULE TYPE ONLY. Cross-module moves blocked. | C [S16] |
| `proofpoint-pps-quarantine-message-delete` | Delete with optional archive | Optional archive parameter | C [S16] |

### Edge Cases
- Messages can only be moved between folders of the same module type. Attempting to move a spam-quarantined message to a content quarantine folder fails.
- Quarantine folders must exist before being referenced in a rule disposition. Referencing a nonexistent folder causes silent disposition failures.

---

## 2.5 Email Firewall > Rules > Dispositions

**Navigation:** PPS Admin Console > Email Firewall > Rules > [Rule] > Dispositions section
**Evidence:** B [S2], C [V2 ~2:30]

### Fields

| Field | Type | Required | Default | Options | Validation | Description | Source |
|-------|------|----------|---------|---------|------------|-------------|--------|
| Delivery Method | dropdown | Yes | null | Deliver Now, Quarantine, Discard, ADDITIONAL OPTIONS INCOMPLETE | Must be a valid option | Primary action applied to matching messages. | C [V2 ~2:30], B [S2] |
| Quarantine Folder | dropdown | Conditional | null | Pre-created folder names | Must reference existing folder | Target quarantine folder. Only available when Delivery Method = Quarantine. | B [S2], C [S16] |

### Conditional Fields
- Quarantine Folder field: visible and required ONLY when Delivery Method = Quarantine
- Additional disposition fields beyond Delivery Method and Quarantine Folder: INCOMPLETE — full disposition options require authenticated admin guide

### Edge Cases
- Selecting Quarantine without a pre-created folder: disposition fails silently or with an error (behavior not documented in accessible sources)
- Training documentation [S2] references "Delivery Precedence" as a concept distinct from "Module Precedence" — this suggests dispositions may have a precedence ordering when multiple modules match. Full details INCOMPLETE.

---

## 2.6 Custom Spam Rules

**Navigation:** INCOMPLETE — exact path not documented in accessible sources
**Evidence:** B [S2], D [community spam tuning article]

### Overview
Custom Spam Rules are a PPS sub-capability within the spam module that allow administrators to define specialized spam detection rules beyond the default threshold slider. These are distinct from Email Firewall rules — they operate within the spam processing module, not the Email Firewall module.

### Best Practice: Incremental Tuning
| Step | Action | Rationale | Source |
|------|--------|-----------|--------|
| 1 | Start with highest-confidence rules (score = 100) | Lowest false positive risk | D [community] |
| 2 | Monitor false positives for 1–2 weeks | Establish baseline before lowering threshold | D [community] |
| 3 | Reduce threshold incrementally | Avoid bulk aggressive tuning in single pass | D [community] |

### INCOMPLETE
Custom Spam Rule creation fields, operators, and scoring weights are not documented in accessible sources. The authenticated PPS admin guide is required.

---

## 2.7 Dictionary Management

**Navigation:** INCOMPLETE — exact navigation path not documented in accessible sources
**Evidence:** B [S2]

### Fields (Partial)

| Field | Type | Required | Default | Options | Validation | Description | Source |
|-------|------|----------|---------|---------|------------|-------------|--------|
| Dictionary Name | text | Yes | null | Custom text | Unique string | Name used to reference this dictionary in Firewall rule conditions | B [S2] |
| Terms/Phrases | textarea or import | Yes | null | Free-form keyword list | INCOMPLETE — encoding, max terms, weighting not documented | Keyword or phrase list used for content matching | B [S2] |

### INCOMPLETE
Dictionary creation UI navigation path, import file format (CSV, plain text, other), term weighting capability, case sensitivity settings, and proximity rule support are all INCOMPLETE in accessible sources.

---

## 2.8 Module Precedence Configuration

**Navigation:** INCOMPLETE — likely under Email Firewall or System settings; exact path not documented
**Evidence:** B [S2]

### Overview
Module Precedence controls the order in which PPS filtering modules process messages. Training documentation [S2] distinguishes between Module Precedence (order of module evaluation) and Delivery Precedence (order of delivery action application when multiple modules match).

### Modules Known to Exist
| Module | Description | Source |
|--------|-------------|--------|
| Spam module | Spam scoring and classification | B [S2] |
| Virus module | Multi-layer AV and zero-hour detection | B [S2] |
| Content/DLP module | Content analysis, smart identifiers, dictionaries, document fingerprinting | B [S14, S2] |
| Email Firewall module | Connection-level and content-level firewall rules | B [S2] |

### INCOMPLETE
Default module order, field names for precedence configuration, and whether Delivery Precedence is configured on the same screen as Module Precedence are all INCOMPLETE in accessible sources.

---

## 2.9 Proofpoint Dynamic Reputation (PDR) Configuration

**Navigation:** INCOMPLETE — exact path not documented
**Evidence:** B [S2]

### Overview
PDR evaluates the reputation of sending IP addresses in real time against Proofpoint's global threat intelligence database. Provides connection-level IP scoring to block mail from known bad actors before message content is analyzed.

### INCOMPLETE
PDR configuration fields, sensitivity thresholds, exception list management, and integration with Email Firewall rules are all INCOMPLETE in accessible sources. This entire section requires authenticated PPS admin guide access.

---

## 2.10 Recipient Verification (RV) Setup

**Navigation:** INCOMPLETE — exact path not documented
**Evidence:** B [S2]

### Overview
RV validates at SMTP RCPT TO time that the recipient address exists in the downstream mail system (LDAP/Active Directory). Messages to invalid recipients are rejected at the gateway, preventing directory harvest attacks and reducing spam load on downstream mail servers.

### INCOMPLETE
RV configuration fields (LDAP server settings, query attributes, failure behavior, exception lists) are all INCOMPLETE in accessible sources.

---

## 2.11 SMTP Rate Control Configuration

**Navigation:** INCOMPLETE — exact path not documented
**Evidence:** B [S2]

### Overview
Limits the rate of SMTP connections or messages accepted per source IP within a defined time window. Protects against flood attacks and high-volume spam bursts.

### INCOMPLETE
Rate limit unit (connections vs. messages), time period, per-IP vs. global limit, exception list for trusted senders, and soft vs. hard limit behavior are all INCOMPLETE in accessible sources.

---

## 2.12 End User Digest Configuration

**Navigation:** INCOMPLETE — exact path not documented; may overlap with Quarantine settings
**Evidence:** B [S2]

### Overview
Controls the periodic quarantine digest emails sent to end users. Digests list messages quarantined for that user with release/block/allow options. Digest frequency, delivery time, language, included quarantine categories, and per-user opt-out behavior are configurable.

### Fields (Partial)

| Field | Type | Required | Default | Options | Validation | Description | Source |
|-------|------|----------|---------|---------|------------|-------------|--------|
| Digest Frequency | dropdown | No | UNKNOWN | INCOMPLETE — frequency options not enumerated | — | How often digest emails are sent to end users | B [S2] |
| Quarantine Categories Included | multiselect | No | UNKNOWN | INCOMPLETE — category options not enumerated | — | Which quarantine folder categories to include in the digest | B [S2] |
| Delivery Time | time | No | UNKNOWN | UNKNOWN | Valid time | Time of day to send digest | U — ASSUMPTION |
| Language / Template | dropdown | No | UNKNOWN | INCOMPLETE | — | Digest email language and template selection | U — ASSUMPTION |

### INCOMPLETE
Full digest configuration fields, template customization, per-user opt-out, and LDAP-driven recipient list are INCOMPLETE in accessible sources.

---

## API Reference (XSOAR-Documented Endpoints)

**Product version:** PPS 8.16.2 / 8.14.2 (verified)
**Evidence:** C [S16]

| Command | Parameters | Description |
|---------|-----------|-------------|
| `proofpoint-pps-smart-search` | action, sender, recipient, start_time, end_time | Trace filtered messages by action type, sender/recipient, and time window |
| `proofpoint-pps-quarantine-messages-list` | folder, sender, recipient | Search quarantined messages by folder and sender/recipient |
| `proofpoint-pps-quarantine-message-release` | guid | Release message without further scanning |
| `proofpoint-pps-quarantine-message-resubmit` | guid | Reprocess message through filtering modules |
| `proofpoint-pps-quarantine-message-forward` | guid, recipients | Forward to alternative recipient list |
| `proofpoint-pps-quarantine-message-move` | guid, folder | Move between same-module-type folders only |
| `proofpoint-pps-quarantine-message-delete` | guid, archive (bool) | Delete with optional archive copy |

---

## Version-Specific Notes

| Version | Change | Impact | Source |
|---------|--------|--------|--------|
| PPS 8.22.x | Unified DLP introduced — may alter DLP module configuration workflow | Email Firewall + DLP module interaction may differ from pre-8.22.x; verified against 8.22.x only | E — inferred from search results; no official changelog accessible |
| PPS on-prem vs PoD cloud | Policy Route menu at System > Policy Route is confirmed for PPS on-prem. PoD cloud console may have different navigation path for equivalent routing configuration | Admins switching from on-prem to PoD should verify route configuration location | C [V3 ~0:45 — on-prem only shown] |
| Pre-2023 PPS admin interface | Videos 2, 3, 9 (2017–2018) show older UI styling. Navigation hierarchy is the same but visual layout differs | Navigation paths documented here are valid; visual alignment to screenshots may differ | B [V2, V3, V9] |
