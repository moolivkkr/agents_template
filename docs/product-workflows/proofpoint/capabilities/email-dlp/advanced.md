# Data Loss Prevention (DLP) Policies — Advanced Configuration Reference
## Proofpoint Email DLP (Essentials / PPS / Adaptive)

> All options documented, organized by screen.
> INCOMPLETE sections indicate fields behind authentication walls or otherwise undocumented in accessible sources.

---

## Screen 1: Security Settings > Email > Filter Policies

**Navigation:** Essentials console > Security Settings (left nav) > Email > Filter Policies
**Source:** Video 7 ~0:45 [Grade B]; Video 20 ~0:30 [Grade B]; [S1, Grade A]

### List View Controls

| Control | Description | Source |
|---------|-------------|--------|
| Inbound tab | Shows all inbound filter policies | [S1, Grade A] |
| Outbound tab | Shows all outbound filter policies | [S1, Grade A] |
| New Filter button | Opens filter creation form | [S1, Grade A] |
| Filter list | All existing policies in priority order | [S1, Grade A] |

---

## Screen 2: Filter Policy Creation / Edit Form (DLP Context)

**Navigation:** Filter Policies > New Filter (or click existing filter name to edit)
**Source:** [S1, Grade A]; Video 20 [Grade B]; Video 7 [Grade B]

### All Fields

| Field | Type | Required | Default | Options | Validation | Description | Source |
|-------|------|----------|---------|---------|------------|-------------|--------|
| Filter Name / Description | text | Yes | None | Free text | Any characters | Internal identifier only; not shown to end users | [S1, Grade A] |
| Direction | dropdown | Yes | None | Inbound, Outbound | Must select one | Direction of mail flow this rule applies to | [S1, Grade A] |
| Scope | dropdown | Yes | None | Company, Group, User | Must select one | Level at which this filter is applied | [S1, Grade A] |
| Priority | dropdown | No | Low | Low, Normal, High | — | Relative priority within same scope | [S1, Grade A] |
| Condition Type | dropdown | Yes | None | Sender Address, Recipient Address, Email Size (kb), Client IP Country, Email Subject, Email Headers, Email Message Content, Raw Email, Attachment Type, Attachment Name | Must select at least one | The email attribute evaluated by this condition | [S1, Grade A] |
| Operator | dropdown | Yes | None | IS, IS NOT, IS ANY OF, IS NONE OF, CONTAINS ALL OF, CONTAINS ANY OF, CONTAINS NONE OF | Must select one per condition | Logical matching operator | [S1, Grade A] |
| Condition Value | text | Yes | None | Free text, smart ID name, keyword, regex | Must provide value | The string, pattern, or identifier name to match against | [S18, Grade D] |
| Primary Action | dropdown | Yes | None | Quarantine, Allow, Reject, Nothing | Must select one | Primary disposition when all conditions match | [S1, Grade A]; Video 20 ~2:30 [Grade B] |
| Encrypt (Do / Secondary Action) | dropdown | No | None | Encrypt | Outbound + Company scope required | Triggers Proofpoint Encryption for matched message | Video 7 ~2:00 [Grade B] |
| Notify Recipient | checkbox | No | Disabled | Enabled/Disabled | — | Sends notification to message recipient | Video 20 ~3:00 [Grade B]; [S18, Grade D] |
| Notify Admin / Sender | checkbox | No | Disabled | Enabled/Disabled | — | Sends compliance alert to admin or notifies sender | [S18, Grade D]; Video 20 ~3:00 [Grade B] |
| Add Header | checkbox | No | Disabled | Enabled/Disabled | — | Inserts custom header into matched message | Video 20 ~3:00 [Grade B] |
| Tag Subject | checkbox | No | Disabled | Enabled/Disabled | — | Prepends configurable tag (e.g., "[DLP ALERT]") to subject line | Video 20 ~3:00 [Grade B] |
| Override Previous Destination | toggle | No | Disabled (Off) | On/Off | — | Forces this filter's action to override higher-priority filter's destination | Video 20 ~3:30 [Grade B] |
| Stop Processing Additional Filters | toggle | No | Disabled (Off) | On/Off | — | Halts filter chain evaluation after this filter matches | Video 20 ~3:30 [Grade B]; [S17, Grade D] |
| Enforce Completely Secure SMTP Delivery | checkbox | No | Disabled | Enabled/Disabled | — | Forces TLS with valid certificate check on delivery | [S1, Grade A] |
| Enforce only TLS on SMTP Delivery | checkbox | No | Disabled | Enabled/Disabled | — | Forces TLS without certificate validation | [S1, Grade A] |
| Hide Logs | checkbox | No | Disabled | Enabled/Disabled | — | Hides filter match log from end-user view | [S1, Grade A] |

### Conditional Fields

| Field | Appears When | Description | Source |
|-------|-------------|-------------|--------|
| Encrypt (in Do dropdown) | Direction = Outbound AND Scope = Company | Only this combination exposes the Encrypt option | Video 7 ~2:00 [Grade B] |
| Group selector | Scope = Group | Displays a group chooser to select which group(s) the filter applies to | [S1, Grade A] |
| User selector | Scope = User | Displays a user chooser | [S1, Grade A] |

### Multiple Conditions

Multiple conditions can be added to a single filter. Conditions within one filter use AND logic by default (all must match). Multiple conditions of the same type using IS ANY OF implements OR logic within that condition. Source: [S1, Grade A].

### Edge Cases

| Scenario | Behavior | Source |
|----------|----------|--------|
| Scope = User or Group with Direction = Outbound | Encrypt action not available; silently removed from dropdown | Video 7 ~2:00 [Grade B] |
| Stop Processing = ON on a spam allow-list filter above a DLP filter | DLP filter never fires for messages matched by the spam filter | Video 20 ~3:30 [Grade B] |
| User-scope filter with conflicting action to Company-scope DLP filter | User-scope wins; company DLP is suppressed silently | Video 20 ~1:30 [Grade B] |
| Override Previous Destination = ON on a lower-priority filter | Lower-priority filter's action overrides a higher-priority filter's quarantine decision | Video 20 ~3:30 [Grade B] |
| CONTAINS ANY OF with large dictionary | Very broad matching; high false positive rate | Video 20 ~3:00 [Grade B] |

---

## Screen 3: Smart Identifier / Content Definition Configuration

**Navigation:** INCOMPLETE — exact path behind Essentials auth wall. Likely under Security Settings or a DLP-specific submenu.
**Source:** [S18, Grade D]; [S24, Grade B] confirms feature set exists

**NOTE: This entire screen is INCOMPLETE. Fields documented below are based on Grade D (third-party guide) and Grade B (product page) sources only. Admin guide behind auth wall.**

### Smart Identifiers (Pre-Built)

| Identifier | Data Type | Notes | Source |
|-----------|----------|-------|--------|
| Credit Card Number | Payment card data (PCI) | Multiple card types (Visa, MC, Amex, Discover) | [S18, Grade D]; [S24, Grade B] |
| US Social Security Number | US PII | Standard 9-digit format | [S18, Grade D]; [S24, Grade B] |
| Bank Account Number | Financial | INCOMPLETE — specific formats unknown | [S18, Grade D] |
| HIPAA / Health Information | Protected health info | Broad HIPAA-related patterns | [S18, Grade D]; [S24, Grade B] |
| Driver's License | US state IDs | INCOMPLETE — which states/formats unknown | [S18, Grade D] |
| Passport Number | Travel documents | INCOMPLETE — which countries unknown | [S18, Grade D] |
| (240+ additional classifiers) | Various regulated and industry categories | Full list: Proofpoint Email DLP product page | [S24, Grade B] |

### Custom Dictionary Configuration

| Field | Type | Description | Source |
|-------|------|-------------|--------|
| Dictionary Name | text | Identifier for this dictionary | [S18, Grade D] |
| Keywords / Phrases | text area or file upload | Word/phrase list (INCOMPLETE — upload format unknown, size limit unknown) | [S18, Grade D] |
| Case Sensitivity | UNKNOWN | INCOMPLETE — whether matching is case-sensitive not documented | INCOMPLETE |
| Minimum Match Count | UNKNOWN | INCOMPLETE — whether occurrence threshold is configurable not documented | INCOMPLETE |

**Best practice:** Pair a custom dictionary with the corresponding smart identifier using AND logic to reduce false positives. Example: HIPAA smart identifier AND medical terminology dictionary. Source: [S24, Grade B].

### Custom Regular Expression Patterns

| Field | Type | Description | Source |
|-------|------|-------------|--------|
| Pattern Name | text | Identifier for this regex | [S18, Grade D] |
| Regex Pattern | regex | Custom pattern for organization-specific data | [S18, Grade D] |
| Regex Syntax Standard | UNKNOWN | INCOMPLETE — PCRE, ECMAScript, or other not documented | INCOMPLETE |
| Test Utility | UNKNOWN | INCOMPLETE — whether inline test capability exists is unknown | INCOMPLETE |

### Document Fingerprinting

| Field | Type | Description | Source |
|-------|------|-------------|--------|
| Template Document | file upload | Reference document to fingerprint (contracts, forms, etc.) | [S14, Grade B]; [S18, Grade D] |
| Matching Mode | UNKNOWN | Full match vs partial match. Digital Asset Security module supports both. | [S14, Grade B] |
| Match Threshold | UNKNOWN | INCOMPLETE — percentage or character count threshold for partial matching unknown | INCOMPLETE |
| Supported File Formats | UNKNOWN | INCOMPLETE — which document types accepted for fingerprinting unknown | INCOMPLETE |

---

## Screen 4: Adaptive Email DLP Configuration

**Navigation:** INCOMPLETE — separate admin surface from Filter Policies. Not accessible via standard Security Settings > Email path.
**Source:** [S23, Grade B]; Video 22 (Jan 2025 webinar) [Grade B]

**NOTE: This entire screen is INCOMPLETE. No admin walkthrough video or public documentation found for the Adaptive DLP configuration UI.**

### Feature Characteristics (Confirmed from Product Page and Webinar)

| Characteristic | Description | Source |
|---------------|-------------|--------|
| Detection method | Behavioral AI; learns from organization's email patterns | [S23, Grade B] |
| Target scenarios | Misdirected email (wrong recipient), human error, accidental disclosure | [S23, Grade B] |
| Enforcement mechanism | Pre-send warning banners displayed to sender requiring acknowledgment — NOT post-send quarantine | Video 22 [Grade B] |
| User acknowledgment | Sender must acknowledge warning before message is delivered | Video 22 [Grade B] |
| Architecture | Architecturally distinct from rule-based Filter Policies; coexists but separate admin interface | Video 22 [Grade B] |

### AI Learning Period

| Phase | Description | Timeline | Source |
|-------|-------------|---------|--------|
| Learning / Warm-up | Model ingests org email patterns; enforcement not active | UNKNOWN — no published timeline | Video 22 [Grade B]; NOVEL finding |
| Monitor Mode | Detections are logged; no enforcement actions | UNKNOWN | [S23, Grade B] |
| Enforcement Mode | Warning banners active; sender acknowledgment required | After learning period | Video 22 [Grade B] |

**CRITICAL:** Activating enforcement before the learning period is complete produces high false positive rates. Source: Video 22 [Grade B].

---

## Screen 5: PPS Admin Console — Email Firewall > Rules (DLP Context)

**Navigation:** PPS Admin Console > Email Firewall > Rules
**Source:** Video 2 ~1:00 [Grade B]; [S2, Grade B]

**NOTE: Field-level detail is INCOMPLETE — PPS admin guide is behind authentication wall. Fields documented from video observations and training material only.**

### Documented Fields (Video-Sourced)

| Field | Type | Required | Description | Source |
|-------|------|----------|-------------|--------|
| Rule ID | text | Yes | Unique identifier for the rule | Video 2 ~1:00 [Grade B] |
| Route Condition | dropdown | Yes | Which policy route this rule applies to (e.g., "default_inbound") | Video 2 ~2:00 [Grade B] |
| Add Condition button | button | Yes | Opens condition builder; add content-based criteria | Video 2 ~1:00 [Grade B] |
| Condition fields | UNKNOWN | Yes | Types include route, sender, recipient, content dictionaries, regex — full list INCOMPLETE | [S2, Grade B] |
| Dispositions section | UNKNOWN | Yes | Delivery Method dropdown (options: "Deliver Now" confirmed; others INCOMPLETE) | Video 2 ~2:30 [Grade B] |

### PPS Enterprise Privacy Suite — Module Overview

Source: [S14, Grade B]

| Module | Function | Availability |
|--------|---------|-------------|
| Proofpoint Email Firewall | Detects sensitive content in body and subject | PPS base |
| Proofpoint Regulatory Compliance | Smart identifiers for PCI, HIPAA, and other regulated categories | Enterprise Privacy Suite (licensed add-on) |
| Proofpoint Digital Asset Security | Document fingerprinting — full and partial match | Enterprise Privacy Suite (licensed add-on) |
| Proofpoint Encryption | Policy-based encryption when DLP conditions are met | Enterprise Privacy Suite (licensed add-on) |

### PPS Unified DLP (8.22.x)

**INCOMPLETE** — PPS 8.22.x introduced a Unified DLP module consolidating email DLP surfaces. Configuration changes vs legacy Email Firewall approach are not documented in accessible sources. This is a known gap (Unresolved Question #12 in doc-corpus). Source: search snippets only (Grade E / ASSUMPTION).

---

## Screen 6: DLP + Encryption Integration

**Navigation:** Filter Policies > [DLP filter] > Do dropdown = Encrypt (Outbound + Company scope required)
**Source:** Video 7 ~2:00 [Grade B]; [S14, Grade B]

### Encryption Trigger Options

| Trigger Method | Description | Source |
|---------------|-------------|--------|
| DLP filter Encrypt action | Filter Policy with Encrypt in Do dropdown; fires on content match | Video 7 [Grade B] |
| Subject line keyword | User types [ENCRYPT] or [SECURE] in subject; triggers encryption | [S17, Grade D] |
| TLS fallback | Attempts TLS delivery; falls back to Proofpoint Encryption if TLS negotiation fails | [S14, Grade B] |
| Deep content analysis | PHI, NPI, regulated data, document fingerprints detected by Email Firewall | [S14, Grade B] |
| Partner/origin-based | Based on specific partner domains, sender attributes, attachment types | [S14, Grade B] |
| Microsoft IAM classification | Encrypts documents with Microsoft IAM metadata classification labels | [S14, Grade B] |

### Encryption Features Available

| Feature | Description | Source |
|---------|-------------|--------|
| AES-256 encryption + ECDSA signatures | Message encryption standard | [S14, Grade B] |
| Secure Reader | HTTPS web portal for recipients to read encrypted mail (no software required) | [S14, Grade B] |
| Decrypt Assist | One-step decryption for mobile/laptop/desktop | [S14, Grade B] |
| Trusted Partner Encryption | Gateway-to-gateway transparent decryption between Proofpoint customers | [S14, Grade B] |
| Message Expiration | Time-based expiration configured per policy | [S14, Grade B] |
| Message Revocation | Per-message, per-recipient revocation | [S14, Grade B] |

### Scope Restriction (Critical)

The Encrypt action is available **only** when:
- Direction = **Outbound**
- Scope = **Company**

Any other combination silently removes Encrypt from the action dropdown with no error message. Source: Video 7 ~2:00 [Grade B].

**Workaround for group-level encryption:** Create a Company-scope Outbound encrypt filter. Add a recipient-domain exception condition (CONTAINS NONE OF) for everyone outside the target group. This approximates per-group encryption via Company-scope policy. Source: inferred from Video 7 [Grade B].

---

## DLP Action Reference Table

| Action | Availability | Description | Source |
|--------|-------------|-------------|--------|
| Block / Reject | Primary action — all scopes/directions | Hard block; sender receives NDR | [S1, Grade A]; [S18, Grade D] |
| Quarantine | Primary action — all scopes/directions | Holds message for admin review | [S1, Grade A]; [S18, Grade D] |
| Allow | Primary action — all scopes/directions | Permits delivery (use for exception rules) | [S1, Grade A] |
| Nothing | Primary action — all scopes/directions | Monitor-only; no action on delivery | Video 20 ~2:30 [Grade B] |
| Encrypt | Secondary action (Do dropdown) — Outbound + Company scope only | Auto-encrypts via Proofpoint Encryption | Video 7 ~2:00 [Grade B]; [S14, Grade B] |
| Notify Recipient | Secondary action | Email notification to message recipient | [S18, Grade D]; Video 20 [Grade B] |
| Notify Admin / Sender | Secondary action | Alert to compliance team or sender | [S18, Grade D]; Video 20 [Grade B] |
| Add Header | Secondary action | Inserts custom header | Video 20 ~3:00 [Grade B] |
| Tag Subject | Secondary action | Prepends configurable subject tag | Video 20 ~3:00 [Grade B] |

---

## Exception Management

### Recipient Exceptions

Implemented by adding a condition to the DLP filter:
- Condition Type: Recipient Address
- Operator: IS NONE OF
- Value: [trusted-recipient@domain.com] or [@trusteddomain.com]

This prevents the DLP action from firing when the recipient is a known trusted partner. Source: [S1, Grade A] — inferred from condition logic; [S18, Grade D] describes exception concept.

### Sender Exceptions

Implemented by:
- Condition Type: Sender Address
- Operator: IS NONE OF
- Value: [internal-user@yourcompany.com]

Use case: Exempt specific users (legal team, executives) from certain DLP rules while retaining enforcement for all others.

### Content Exceptions

Implemented by chaining conditions with CONTAINS NONE OF:
- Condition Type: Email Message Content
- Operator: CONTAINS NONE OF
- Value: [exception keyword or phrase]

### Pre-Population Recommendation

Before enabling an attachment-type DLP rule (e.g., blocking HTML attachments), pull 30-day inbound mail logs to enumerate all senders sending that content type and pre-populate the exception list. Source: Video 20 ~2:30 [Grade B].

---

## Pre-Built Classifier Library (240+)

Source: [S24, Grade B]

| Category | Coverage | Notes |
|---------|---------|-------|
| Payment card data (PCI-DSS) | Credit card numbers (all major types) | Included in base smart identifiers |
| US healthcare (HIPAA) | PHI patterns | Included in base smart identifiers |
| US financial | SSN, bank accounts, routing numbers | Included in base smart identifiers |
| International PII | Passports, national IDs (multiple countries) | INCOMPLETE — full country list not documented |
| Industry-specific | Legal, HR, IP, trade secrets | Machine learning classifiers |
| Custom | Org-specific data | Via custom dictionaries and regex |

The 240+ classifier library is a named differentiator in Proofpoint Email DLP marketing materials. Full classifier inventory with country/jurisdiction mapping is not documented in accessible sources. Source: [S24, Grade B].

---

## Version-Specific Notes

| Version / Product | Change | Impact | Source |
|------------------|--------|--------|--------|
| PPS 8.22.x | Unified DLP module introduced consolidating email DLP surfaces | Configuration workflow may differ from legacy Email Firewall approach | Search snippets only [Grade E — ASSUMPTION] |
| Adaptive Email DLP (2025) | Separate behavioral AI product launch | Different admin surface, pre-send enforcement model vs post-send quarantine | [S23, Grade B]; Video 22 [Grade B] |
| Essentials UI refresh (2023) | Cleaner visuals; same navigation hierarchy | Pre-2023 videos show older UI but same nav paths | Video 20 [Grade B] |
| Essentials Admin Guide (2014) | 12-year-old source — UI has changed | Use 2014 guide for field logic; use video sources for current navigation | [S1, Grade A]; stale source warning in doc-corpus |
