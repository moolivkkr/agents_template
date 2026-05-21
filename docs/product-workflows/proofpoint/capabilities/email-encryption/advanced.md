# Email Encryption Policies — Advanced Configuration Reference

> All options documented, organized by screen.
> Evidence grade notation: A = Official docs | B = Vendor training/video | C = Demo | D = Community | E = Inferred | U = Assumption (flagged)
> INCOMPLETE sections indicate the feature exists but the admin UI is behind Proofpoint's authentication wall.

---

## Screen 1: Security Settings > Email > Filter Policies (Outbound tab)

**Navigation:** Log in to Proofpoint Essentials admin console > Security Settings (top nav) > Email > Filter Policies > Outbound tab

This is the primary configuration screen for encryption policies in Proofpoint Essentials and Proofpoint on Demand.

### Fields — Filter List View

| Field | Type | Required | Default | Options | Validation | Description | Source |
|-------|------|----------|---------|---------|------------|-------------|--------|
| Filter list order | drag-and-drop | — | Order of creation | Visual position in list | N/A | Determines execution priority alongside Priority field; drag-reorder changes actual execution order | B — V9, V20 |
| Enable/Disable toggle | toggle | — | Enabled on creation | On / Off | N/A | Disables filter without deleting it | A — [S1]; E — inferred from filter lifecycle |

---

## Screen 2: Security Settings > Email > Filter Policies > Outbound > New Filter (or Edit Filter)

**Navigation:** Outbound tab > New Filter button (or click an existing filter name)

This screen is the central configuration point for encryption trigger rules.

### Fields

| Field | Type | Required | Default | Options | Validation | Description | Gotcha | Source |
|-------|------|----------|---------|---------|------------|-------------|--------|--------|
| Filter Name | text | YES | — | Free text | Non-empty, unique within direction | Internal identifier only; not shown to message recipients | None | A — [S1] |
| Direction | dropdown | YES | — | Inbound, Outbound | Must select one | Determines mail flow direction | CRITICAL: Encrypt action disappears from Do dropdown if Direction ≠ Outbound | A — [S1]; B — V7 |
| Scope | dropdown | YES | — | Company, Group, User | Must select one | Organizational level the filter applies to | CRITICAL: Encrypt action disappears from Do dropdown if Scope ≠ Company. Cannot set per-group or per-user encryption via this UI. | B — V7 |
| Priority | dropdown | NO | Low | Low, Normal, High | — | Processing order; High fires before Normal and Low | High-priority filters with "Stop Processing Additional Filters" enabled will silently prevent lower-priority DLP or compliance filters from executing | A — [S1]; B — V20 |
| If (Condition Type) | dropdown | YES | — | See condition types table below | Must select one | The email attribute evaluated to trigger the filter | — | A — [S1] |
| Operator | dropdown | YES | — | See operators table below | Must select one | Matching logic between condition type and value | IS requires exact full-string match; CONTAIN(S) ANY OF is preferred for keywords | A — [S1] |
| Condition Value | text | YES | — | Format depends on Condition Type | Non-empty; format validated per type | Value matched against the condition type | For subject keyword triggers, ensure keyword includes brackets (e.g., [ENCRYPT]) and use CONTAIN(S) ANY OF operator, not IS | A — [S1]; D — [S17] |
| Do (Primary Action) | dropdown | YES | — | See primary actions table below | Must select one | Primary disposition for matching messages | Encrypt only appears when Direction=Outbound AND Scope=Company | A — [S1]; B — V7 |
| Stop Processing Additional Filters | toggle | NO | Off | On / Off | — | Halts evaluation of lower-priority filters when this filter matches | Silently breaks downstream DLP and compliance filter chain — any filter with lower priority will never fire for matched messages | B — V20 |
| Override Previous Destination | toggle | NO | Off | On / Off | — | Changes message destination even if a higher-priority filter already set a destination | Can cause quarantine-then-deliver confusion with complex filter stacks | B — V20 |
| Hide Logs | checkbox | NO | Disabled | Enabled / Disabled | — | Hides this filter's activity from end-user log views | Use for internal compliance filters you do not want end users to see | A — [S1] |
| Enforce Completely Secure SMTP Delivery | checkbox | NO | Disabled | Enabled / Disabled | — | Forces TLS with valid certificate; falls back to Proofpoint Encryption if TLS fails | This checkbox IS the TLS fallback encryption trigger — enables sub-capability 6.2 without needing Do=Encrypt | A — [S1]; B — [S14] |
| Enforce only TLS on SMTP Delivery | checkbox | NO | Disabled | Enabled / Disabled | — | Forces TLS without certificate validation (no Proofpoint Encryption fallback) | If TLS fails with this option only, delivery fails — not encrypted | A — [S1] |

### Condition Types

| Condition Type | Format | Example | Notes | Source |
|----------------|--------|---------|-------|--------|
| Sender Address | user@domain.com or domain.com | finance@acme.com | Matches specific senders or entire sending domains | A — [S1] |
| Recipient Address | user@domain.com or domain.com | @partner.com | Matches specific recipients or entire recipient domains | A — [S1] |
| Email Size (kb) | Numeric (kilobytes) | 5000 | Useful for encrypting large attachments | A — [S1] |
| Client IP Country | Country code or name | US, UK | Based on sending MTA geographic location | A — [S1] |
| Email Subject | Text string | [ENCRYPT] | User-initiated encryption keyword trigger | A — [S1]; D — [S17] |
| Email Headers | Header field and value | X-Classification: Confidential | For IAM/MIP header-based triggers | A — [S1] |
| Email Message Content | Text string or keyword | SSN, credit card | DLP content-based trigger | A — [S1] |
| Raw Email | Text string | Pattern in raw MIME | Advanced use; matches against full MIME source | A — [S1] |
| Attachment Type | Category | office documents, archives | See attachment type categories below | A — [S1] |
| Attachment Name | Filename pattern | *.pdf, contract*.docx | Wildcard matching on filename | A — [S1] |

### Attachment Type Categories

| Category | Included Formats | Source |
|----------|-----------------|--------|
| Windows executable components | .exe, .dll, .sys and similar | A — [S1] |
| Installers | Setup packages, MSI | A — [S1] |
| Other executable components | Scripts, batch files | A — [S1] |
| Office documents | Word, Excel, PowerPoint, PDF | A — [S1] |
| Archives | ZIP, RAR, TAR, 7Z | A — [S1] |
| Audio/visual | MP3, MP4, AVI, image formats | A — [S1] |
| PGP encrypted files | PGP/GPG encrypted formats | A — [S1] |

### Operators

| Operator | Behavior | Best For | Source |
|----------|----------|----------|--------|
| IS | Exact full-string match | Known exact senders/recipients | A — [S1] |
| IS NOT | Exact full-string non-match | Exclusion rules | A — [S1] |
| IS ANY OF | Exact match against list of values | Multiple senders/domains | A — [S1] |
| IS NONE OF | No match against list | Exclusion from set | A — [S1] |
| CONTAIN(S) ALL OF | All listed values present | Multi-keyword AND logic | A — [S1] |
| CONTAIN(S) ANY OF | Any listed value present | Keyword detection (preferred for [ENCRYPT] style triggers) | A — [S1] |
| CONTAIN(S) NONE OF | None of listed values present | Exclusion from keyword set | A — [S1] |

### Primary Actions (Do dropdown)

| Action | When Available | Effect | Source |
|--------|---------------|--------|--------|
| Encrypt | Direction=Outbound AND Scope=Company ONLY | Applies AES-256 encryption; recipient receives Secure Reader link | B — V7; B — [S14] |
| Allow (skipping spam filter) | All direction/scope combinations | Delivers immediately, bypasses spam scanning | A — [S1] |
| Allow (but filter for spam) | All direction/scope combinations | Delivers but continues spam evaluation | A — [S1] |
| Quarantine | All direction/scope combinations | Holds message for admin review | A — [S1] |
| Reject | All direction/scope combinations | Rejects at SMTP; sender receives bounce | B — V20 |
| Nothing | All direction/scope combinations | Takes no action (used for passive monitoring with secondary actions) | B — V20 |

### Secondary Actions (available in addition to primary action)

**Note:** Secondary actions list sourced primarily from grade-D and grade-B video sources. Confirm in current UI.

| Secondary Action | Description | Source |
|-----------------|-------------|--------|
| Notify Recipient | Sends notification email to message recipient | B — V20 ~3:00; D — [S17] |
| Notify Admin | Sends alert to configured admin email | B — V20 ~3:00; D — [S17] |
| Add Header | Inserts custom X-header into message | B — V20 ~3:00; D — [S17] |
| Tag Subject | Prepends tag text to message subject | B — V20 ~3:00; D — [S17] |

### Conditional Fields

| Condition | Field That Appears/Disappears | Behavior |
|-----------|------------------------------|----------|
| Direction=Inbound selected | "Encrypt" option in Do dropdown | Disappears |
| Scope=Group or Scope=User selected | "Encrypt" option in Do dropdown | Disappears |
| Direction=Outbound AND Scope=Company both selected | "Encrypt" option in Do dropdown | Appears |

### Edge Cases

| Scenario | Behavior | Recommendation | Source |
|----------|----------|----------------|--------|
| Filter priority = High + Stop Processing = On + Encrypt action | Encryption fires; all downstream DLP/compliance filters bypass | Only enable Stop Processing on encryption filters if no downstream compliance filters exist | B — V20 |
| Override Previous Destination = On on encryption filter | Encrypts even if higher-priority filter already quarantined the message | Use carefully; may cause quarantined messages to be encrypted and delivered instead | B — V20 |
| Filter set at Scope=Company; user has personal allow-list for recipient domain | User-level allow-list filter applies first; company encryption filter may be overridden | Audit per-user filter lists; user-level filters apply before Group and Company | B — V20 ~1:30 |
| Condition Value contains regex characters without CONTAIN operator | Filter may fail to match or error | Use CONTAIN(S) ANY OF for patterns; test at User scope first | A — [S1]; D — [S17] |

---

## Screen 3: PPS Admin Console — Enterprise Privacy Suite — Encryption Trigger Rules

**Navigation:** INCOMPLETE — PPS/PoD admin console path behind authentication wall

**What is known from [S14]:**

The PPS Enterprise Privacy Suite has four components that work together to trigger encryption:

| Component | Role in Encryption | Source |
|-----------|-------------------|--------|
| Proofpoint Email Firewall | Detects sensitive content in message body and subject | B — [S14] |
| Proofpoint Regulatory Compliance | Smart identifiers for financial, healthcare, and regulated data | B — [S14] |
| Proofpoint Digital Asset Security | Document fingerprinting with full and partial matching | B — [S14] |
| Proofpoint Encryption | Applies AES-256 encryption based on policy decisions from the above components | B — [S14] |

### Encryption Trigger Types (PPS)

| Trigger Type | Description | Configuration Location | Source |
|-------------|-------------|----------------------|--------|
| Deep content analysis | Detects PHI, NPI, regulated data, document fingerprints in message content | Regulatory Compliance module + Digital Asset Security module | B — [S14] |
| Message origin/destination | Based on specific partner senders, internal senders, or attachment types | Email Firewall rule conditions | B — [S14]; B — V2 |
| TLS fallback | Attempts TLS delivery; falls back to Proofpoint Encryption when TLS not available | Email Firewall rule disposition or filter checkbox | B — [S14]; A — [S1] |
| User-initiated keyword | Subject line keyword (e.g., [ENCRYPT]) | Filter Policies condition (Email Subject CONTAIN(S) ANY OF [ENCRYPT]) | D — [S17]; B — V7 |

### PPS Email Firewall Rule Fields (Partial — confirmed from video)

| Field | Type | Required | Default | Description | Source |
|-------|------|----------|---------|-------------|--------|
| Rule ID | text | YES | — | Unique identifier for the rule | B — V2 ~1:00 |
| Route Condition | dropdown | YES | — | Policy route this rule scopes to (e.g., default_inbound, default_outbound, or custom route name) | B — V2 ~2:00 |
| Disposition / Delivery Method | dropdown | YES | — | Action for matching messages (Deliver Now, Encrypt, Quarantine, Discard + others not documented) | B — V2 ~2:30; B — [S14] |
| Add Condition button | button | NO | — | Adds additional conditions to the rule | B — V2 ~1:00 |

**INCOMPLETE:** Full condition types, operators, and disposition options for PPS Email Firewall require admin console access.

---

## Screen 4: PPS — Message Expiration Policy (6.4)

**Navigation:** INCOMPLETE — admin UI not documented in accessible sources

**Known capabilities from [S14]:**
- Message expiration is configured per policy (not per message, though per-message override may exist)
- After the expiration period, the encrypted message becomes inaccessible via Secure Reader
- Expiration period unit and range: UNKNOWN — not documented in accessible sources

**Fields:**

| Field | Type | Required | Default | Description | Source |
|-------|------|----------|---------|-------------|--------|
| Expiration Period | number | UNKNOWN | UNKNOWN | Duration before message expires; unit (hours/days) UNKNOWN | E — Inferred from [S14] |
| Expiration Unit | dropdown | UNKNOWN | UNKNOWN | Hours or days — UNKNOWN | E — Inferred from [S14] |

**INCOMPLETE — requires PPS admin console access**

---

## Screen 5: PPS — Message Revocation (6.5)

**Navigation:** INCOMPLETE — admin UI not documented in accessible sources

**Known capabilities from [S14]:**
- Revocation is per-message and per-recipient
- Senders or administrators can revoke access to a specific encrypted message after delivery
- Revocation requires the message management console, not the policy configuration screen

**Fields:** INCOMPLETE — requires PPS admin console access. [B — S14]

---

## Screen 6: PPS — Trusted Partner Encryption Setup (6.6)

**Navigation:** INCOMPLETE — admin UI not documented in accessible sources

**Known capabilities from [S14]:**
- Requires both sender and recipient organizations to be Proofpoint customers
- Delivers via gateway-to-gateway decryption; recipient does not need to use Secure Reader
- Also described in product materials as "Decrypt Assist"

**Encryption Method Options (Grade D source — confirm in current UI):**

| Method | Description | Source |
|--------|-------------|--------|
| Portal Pickup | Default; recipient uses Secure Reader web portal | D — [S18] SINGLE SOURCE |
| PDF | Encrypted PDF attachment delivery | D — [S18] SINGLE SOURCE |
| TLS | Transport-layer encryption via SMTP TLS | D — [S18] SINGLE SOURCE |
| S/MIME | Certificate-based end-to-end encryption | D — [S18] SINGLE SOURCE |

**WARNING:** Encryption method options list sourced from Grade D [S18] only. Not confirmed in Grade A or B sources. Treat as ASSUMPTION pending verification.

**Fields:** INCOMPLETE — requires PPS admin console access. [B — S14]

---

## Screen 7: PPS — Secure Reader Branding (6.7)

**Navigation:** INCOMPLETE — admin UI not documented in accessible sources

**Known capabilities from [S14]:**
- Organizations can customize the Secure Reader portal with their logo and branding
- Branding is shown to external recipients when they access encrypted messages

**Fields:**

| Field | Type | Required | Default | Description | Source |
|-------|------|----------|---------|-------------|--------|
| Organization Logo | file_upload | NO | Proofpoint default | Logo displayed in Secure Reader for external recipients | E — Inferred from [S14] |
| Brand Name / Display Name | text | NO | UNKNOWN | Organization name shown in Secure Reader | E — Inferred from [S14] |
| Color Scheme | UNKNOWN | NO | UNKNOWN | Portal color customization | E — Inferred from [S14] |

**INCOMPLETE — requires PPS admin console access**

---

## Screen 8: PPS — Key Management / Proofpoint Key Service (6.8)

**Navigation:** INCOMPLETE — admin UI not documented in accessible sources

**Known capabilities from [S14]:**
- Proofpoint Key Service manages AES-256 encryption keys centrally
- Keys are managed at the organizational level, not per-message
- End-user key management delegation (6.9) allows users to manage their own keys

**Fields:** INCOMPLETE — requires PPS admin console access. [B — S14]

---

## Screen 9: Microsoft IAM / MIP Integration — Classified Document Encryption (6.10)

**Navigation:** INCOMPLETE — Proofpoint and Microsoft admin console paths not documented in accessible sources

**Known capabilities from [S14]:**
- Proofpoint reads Microsoft Information Protection (MIP / Azure Information Protection) metadata classification labels on outbound documents
- When a document with a regulated classification label is detected, encryption is automatically applied
- Requires Microsoft IAM integration configured outside the Proofpoint admin console

**Fields:** INCOMPLETE — requires both Proofpoint PPS admin console and Microsoft Azure/MIP configuration. [B — S14]

---

## Screen 10: PPS — Inbound Encrypted Email Decryption at Gateway (6.11)

**Navigation:** INCOMPLETE — admin UI not documented in accessible sources

**Known capabilities from [S14]:**
- Proofpoint gateway can automatically decrypt inbound encrypted messages
- Applies to inbound encrypted messages from non-Proofpoint senders
- Distinct from Trusted Partner decryption (6.6)
- May support S/MIME and PGP inbound decryption

**Fields:** INCOMPLETE — requires PPS admin console access. [B — S14]

---

## Version-Specific Notes

| Version | Change | Impact | Source |
|---------|--------|--------|--------|
| Essentials (current, post-2023 UI refresh) | Cleaner UI visuals; Filter Policies navigation path confirmed at Security Settings > Email > Filter Policies | Navigation paths documented above reflect post-2023 interface | B — video-intelligence.md version notes |
| PPS 8.22.x | Unified DLP for Email introduced — may change how Email DLP and Encryption interact | DLP→Encrypt policy workflow may have changed from documented behavior | E — Inferred from [S12 search context]; INCOMPLETE |
| Encryption Data Sheet [S14] dated March 2019 | Encryption features may have expanded since 2019; GenAI-related encryption policies not covered | Treat [S14] as floor, not ceiling for feature list | B — [S14] stale source warning from doc-corpus |
