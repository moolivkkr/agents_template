# Authoring Policies -- Complete Field Reference
## Palo Alto Enterprise DLP (Cloud-Delivered)

> Capability: authoring-policies | Generated: 2026-05-21
> Organization: By screen (not by workflow step) -- this is the reference manual
> Enhanced: UI diagrams, worked examples, WHY/GOTCHA annotations per object type

---

## How to Use This Document

This document serves as both a **reference manual** and a **learning guide**. Every major screen includes:

1. **ASCII UI Diagram** -- visual layout of the screen
2. **Field Table** -- every field, type, default, and constraint
3. **Worked Examples** -- complete configurations with all field values filled in (5-7 per object type)
4. **WHY / GOTCHA annotations** -- reasoning and traps

Examples are cross-referenced across levels. Pattern examples feed into profile examples, which feed into rule examples. Reading end-to-end gives a coherent, deployable policy suite.

---

## Screen Index

| # | Screen | Navigation | Section |
|---|--------|-----------|---------|
| 1 | Data Patterns List | DLP App > Data Patterns | [S1](#s1-data-patterns-list) |
| 2 | Create Custom Data Pattern (Basic Regex) | Data Patterns > Create > Regex > Basic | [S2](#s2-create-custom-data-pattern-basic-regex) |
| 3 | Create Custom Data Pattern (Weighted Regex) | Data Patterns > Create > Regex > Weighted | [S3](#s3-create-custom-data-pattern-weighted-regex) |
| 4 | Create File Property Data Pattern | Data Patterns > Create > File Property | [S4](#s4-create-file-property-data-pattern) |
| 5 | Predefined ML-Based Data Pattern Detail | Data Patterns > Predefined > ML pattern | [S5](#s5-predefined-ml-based-data-pattern) |
| 6 | EDM Dataset Configuration | DLP App > EDM > Upload | [S6](#s6-edm-dataset-configuration) |
| 7 | Custom Document Type Upload | DLP App > Custom Document Types > Upload | [S7](#s7-custom-document-type-upload) |
| 8 | Data Profiles List | DLP App > Data Profiles | [S8](#s8-data-profiles-list) |
| 9 | Create Data Profile (Standard) | Data Profiles > Create | [S9](#s9-create-data-profile-standard) |
| 10 | Create Nested Data Profile | Data Profiles > Create > Nested | [S10](#s10-create-nested-data-profile) |
| 11 | Create Granular Data Profile | Data Profiles > Create > Granular | [S11](#s11-create-granular-data-profile) |
| 12 | DLP Rules (SCM) | SCM > Configuration > Security Services > DLP | [S12](#s12-dlp-rules-scm) |
| 13 | Data Filtering Profile (Panorama) | Panorama > Objects > Security Profiles > Data Filtering | [S13](#s13-data-filtering-profile-panorama) |
| 14 | Endpoint DLP Policy Rule (Cortex XDR) | Cortex XDR > Policy > DLP | [S14](#s14-endpoint-dlp-policy-rule) |
| 15 | Security Policy Rule (SCM) | SCM > Configuration > Security Policy | [S15](#s15-security-policy-rule-scm) |
| 16 | Profile Group (SCM) | SCM > Configuration > Profile Groups | [S16](#s16-profile-group-scm) |
| 17 | Push Configuration (SCM) | SCM > Push Config | [S17](#s17-push-configuration) |
| 18 | Incident Management Dashboard | SCM > Incidents > DLP | [S18](#s18-incident-management-dashboard) |

---

## S1: Data Patterns List

**Navigation:** DLP App > Data Patterns
**Purpose:** Browse, search, and manage all data patterns (predefined and custom)

### UI Diagram

```
+-------------------------------------------------------------------------+
| Enterprise DLP > Data Patterns                                           |
+-------------------------------------------------------------------------+
| [+ Create Data Pattern]  Search: [________________]  Filter: [All Types] |
+-------------------------------------------------------------------------+
| Name                    | Type       | Detection | Status    | Actions   |
|-------------------------|------------|-----------|-----------|-----------|
| Credit Card Number      | Predefined | Regex     | Active    | View      |
| Credit Card Number - ML | Predefined | ML-Based  | Active    | View      |
| SSN (US)                | Predefined | Regex     | Active    | View      |
| SSN (US) - ML           | Predefined | ML-Based  | Active    | View      |
| IBAN (International)    | Predefined | Regex     | Active    | View      |
| AWS Access Key          | Predefined | Regex     | Active    | View      |
| Internal Project Codes  | Custom     | Regex     | Active    | Edit/Del  |
| Financial Doc Indicators| Custom     | Weighted  | Active    | Edit/Del  |
| Exec Authored Docs      | Custom     | File Prop | Active    | Edit/Del  |
| Customer DB (EDM)       | EDM        | Exact     | Active    | Edit/Del  |
|                         |            |           |           |           |
| Showing 500+ patterns   |            |           |           | Page 1/25 |
+-------------------------------------------------------------------------+
```

**Key observations:**
- Predefined patterns have "View" only (no edit/delete)
- Custom patterns have Edit and Delete actions
- ML-based patterns are flagged with an ML icon
- EDM patterns show as "Exact" detection type

---

## S2: Create Custom Data Pattern (Basic Regex)

**Navigation:** DLP App > Data Patterns > Create Data Pattern > Regular Expression > Basic

### UI Diagram

```
+-------------------------------------------------------------------------+
| Create Data Pattern                                                      |
+-------------------------------------------------------------------------+
| Pattern Name:    [________________________________]                       |
| Description:     [________________________________]                       |
|                                                                          |
| Pattern Type:    (x) Regular Expression  ( ) File Property               |
| Mode:            (x) Basic               ( ) Weighted                    |
|                                                                          |
| Regular Expressions (one per line, up to 100):                           |
| +---------------------------------------------------------------------+ |
| | \bEMP-\d{6}\b                                                       | |
| | \bCONT-\d{8}\b                                                      | |
| |                                                                     | |
| +---------------------------------------------------------------------+ |
|                                                                          |
| [ Test Pattern ]                                                         |
|                                                                          |
| [Cancel]                                        [Save]                   |
+-------------------------------------------------------------------------+
```

### Field Reference

| Field | Type | Required | Default | Constraints | Notes |
|-------|------|----------|---------|-------------|-------|
| Pattern Name | Text | Yes | -- | Max 255 chars, unique | Descriptive, include data type |
| Description | Text | No | -- | Max 1024 chars | Explain what this detects and why |
| Pattern Type | Radio | Yes | Regular Expression | Regex or File Property | Determines available fields |
| Mode | Radio | Yes | Basic | Basic or Weighted | Weighted adds per-line scores |
| Expressions | Multiline text | Yes | -- | 1-100 lines, RE2 syntax | One regex per line |

**RE2 Regex Engine Constraints:**
- Supported: Character classes, alternation, quantifiers, groups, anchors
- NOT supported: Negative lookahead `(?!...)`, lookbehind `(?<=...)`, backreferences `\1`, possessive quantifiers
- Max expression length: undocumented (test empirically)

### Worked Examples

**Example 1: US Social Security Number (Custom)**
```
Pattern Name: Custom SSN Detection
Description: Matches US SSNs in XXX-XX-XXXX and XXXXXXXXX formats
Mode: Basic
Expressions:
  \b\d{3}-\d{2}-\d{4}\b
  \b\d{9}\b
```
> **WHY separate lines:** The first catches hyphenated format, the second catches continuous digits. RE2 cannot use alternation across format types efficiently in a single expression.

**Example 2: AWS Credentials**
```
Pattern Name: AWS Credential Leak Detection
Description: Detects AWS access keys and secret keys in content
Mode: Basic
Expressions:
  \bAKIA[0-9A-Z]{16}\b
  \b[0-9a-zA-Z/+]{40}\b
```
> **GOTCHA:** The secret key pattern (`[0-9a-zA-Z/+]{40}`) is very broad. This WILL produce false positives. Use in combination with proximity to "aws_secret" keywords or weighted scoring.

**Example 3: SWIFT/BIC Code**
```
Pattern Name: SWIFT BIC Code
Description: Matches SWIFT/BIC bank identifier codes
Mode: Basic
Expressions:
  \b[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?\b
```

**Example 4: Internal Document Classification Labels**
```
Pattern Name: Document Classification Labels
Description: Detects internal classification markings
Mode: Basic
Expressions:
  \b(TOP SECRET|SECRET|CONFIDENTIAL|RESTRICTED|INTERNAL ONLY)\b
  \bClassification:\s*(TS|S|C|R|IO)\b
```

**Example 5: Medical Record Numbers**
```
Pattern Name: Hospital MRN Format
Description: Matches our organization's MRN format
Mode: Basic
Expressions:
  \bMRN[:\s]*\d{7,10}\b
  \bPatient\s+ID[:\s]*[A-Z]\d{6,9}\b
```

---

## S3: Create Custom Data Pattern (Weighted Regex)

**Navigation:** DLP App > Data Patterns > Create Data Pattern > Regular Expression > Weighted

### UI Diagram

```
+-------------------------------------------------------------------------+
| Create Data Pattern                                                      |
+-------------------------------------------------------------------------+
| Pattern Name:    [________________________________]                       |
| Description:     [________________________________]                       |
|                                                                          |
| Pattern Type:    (x) Regular Expression  ( ) File Property               |
| Mode:            ( ) Basic               (x) Weighted                    |
|                                                                          |
| Score Threshold: [____15____]                                            |
|                                                                          |
| Weighted Expressions:                                                    |
| +-------------------------------------------+----------+               |
| | Expression                                | Weight   |               |
| |-------------------------------------------|----------|               |
| | \b(CONFIDENTIAL)\b                        |    10    |               |
| | \b(revenue|profit|loss)\b                 |     5    |               |
| | \b(Q[1-4]\s+20\d{2})\b                   |     5    |               |
| | \b(public|press release)\b                |   -10    |               |
| +-------------------------------------------+----------+               |
|                                                                          |
| [ + Add Expression ]    [ Test Pattern ]                                 |
|                                                                          |
| [Cancel]                                        [Save]                   |
+-------------------------------------------------------------------------+
```

### Field Reference

| Field | Type | Required | Default | Constraints | Notes |
|-------|------|----------|---------|-------------|-------|
| Score Threshold | Integer | Yes | -- | 1 to 9999 | Cumulative score to trigger match |
| Expression | Text | Yes | -- | RE2 syntax per line | One regex per row |
| Weight | Integer | Yes | -- | -9999 to 9999 | Negative weights suppress false positives |

### Worked Examples

**Example 6: M&A Document Detection**
```
Pattern Name: Merger & Acquisition Documents
Score Threshold: 25

Expressions:
  \b(merger|acquisition|takeover|buyout)\b                  | 10
  \b(target company|acquiring entity|deal value)\b          | 10
  \b(due diligence|letter of intent|LOI)\b                  |  8
  \b(synergy|integration plan|post-merger)\b                |  5
  \b(press release|SEC filing|public announcement)\b        | -15
  \b(draft|confidential|internal)\b                         |  5
```
> **WHY negative weights:** Documents that mention "press release" or "SEC filing" are public -- we do NOT want to flag those. The -15 weight ensures public documents about M&A don't trigger false positives.

**Example 7: PII Composite Detection**
```
Pattern Name: PII Composite Score
Score Threshold: 20

Expressions:
  \b\d{3}-\d{2}-\d{4}\b                                    | 15    SSN
  \b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b              | 12    Credit card
  \b(date of birth|DOB|born on)\b                           |  5    DOB keyword
  \b[A-Z][a-z]+\s+[A-Z][a-z]+\b                            |  2    Person name
  \b\d{5}(-\d{4})?\b                                        |  1    ZIP code
  \b(test|sample|example|dummy)\b                           | -20   Test data
```
> **WHY:** A document with SSN (15) + DOB keyword (5) = 20, triggering the match. But a test document with "sample" (-20) ensures no false positive.

---

## S4: Create File Property Data Pattern

**Navigation:** DLP App > Data Patterns > Create Data Pattern > File Property

### Field Reference

| Field | Type | Required | Default | Constraints |
|-------|------|----------|---------|-------------|
| Pattern Name | Text | Yes | -- | Max 255 chars |
| Property | Dropdown | Yes | -- | Author, Title, Subject, Keywords, Company, Manager |
| Match Type | Dropdown | Yes | Contains | Contains, Equals, Starts With, Ends With, Regex |
| Value | Text | Yes | -- | Depends on Match Type |

### Worked Example

**Example 8: Executive Document Detection**
```
Pattern Name: C-Suite Authored Documents
Property: Author
Match Type: Contains
Value: CEO|CFO|CTO|COO|CISO
```

---

## S5: Predefined ML-Based Data Pattern

**Navigation:** DLP App > Data Patterns > Predefined > [ML Pattern]

### Field Reference (Read-Only)

| Field | Value | Configurable? |
|-------|-------|-------------|
| Pattern Name | (predefined, e.g., "Credit Card Number - ML") | No |
| Detection Type | ML-Based | No |
| Occurrence | Any | No -- FIXED |
| Confidence | High / Low | Yes -- ONLY these two options |
| Duplication | Not supported | N/A |
| Custom criteria | Not supported | N/A |

> **GOTCHA:** This is the most constrained object in the entire DLP system. You can ONLY toggle between High and Low confidence. Everything else is locked.

---

## S6: EDM Dataset Configuration

**Navigation:** DLP App > EDM > Manage Datasets

### EDM CLI Workflow

```
Step 1: Prepare CSV
+------------------------------------------------------------------+
| ssn,first_name,last_name,dob,account_number                      |
| 123-45-6789,John,Doe,1990-01-15,ACC-001234                      |
| 987-65-4321,Jane,Smith,1985-03-22,ACC-005678                    |
| ...                                                               |
+------------------------------------------------------------------+

Step 2: Run EDM CLI
$ ./edm-cli --source customer_records.csv --config edm-config.json

Step 3: CLI Output
  Hashing 50,000 records with SHA256...
  Encrypting dataset with AES-256...
  Compressed to encrypted_edm_2026-05-21.zip (2.3 MB)

Step 4: Upload to DLP Cloud
  Uploading to Enterprise DLP EDM storage...
  Upload complete. Dataset ID: edm-dataset-12345

Step 5: Create EDM Data Pattern
  Navigate to DLP App > Data Patterns > Create > EDM
  Select dataset: edm-dataset-12345
  Configure column mappings and match criteria
```

### EDM Column Configuration

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| Column Name | Text | Yes | Must match CSV header |
| Data Type | Dropdown | Yes | SSN, NAME, DATE, EMAIL, PHONE, ADDRESS, CUSTOM |
| Primary Key | Boolean | No | At least one column should be primary |
| Indexed | Boolean | Yes (default: Yes) | Indexed columns are searchable |

### Worked Example

**Example 9: Customer Database EDM**
```
Dataset Name: Customer PII Database Q2 2026
Source: customer_export_2026Q2.csv
Records: 50,000

Column Configuration:
  | Column | Type | Primary | Indexed |
  |--------|------|---------|---------|
  | ssn | SSN | Yes | Yes |
  | first_name | NAME | No | Yes |
  | last_name | NAME | No | Yes |
  | dob | DATE | No | Yes |
  | email | EMAIL | No | Yes |
  | account_num | CUSTOM | No | Yes |
```

---

## S7: Custom Document Type Upload

**Navigation:** DLP App > Custom Document Types > Upload

### Field Reference

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| Document Type Name | Text | Yes | Max 255 chars |
| Description | Text | No | Max 1024 chars |
| Positive Training Set (.zip) | File upload | Yes | Min 20 files, recommended 50+, text-only, 500+ chars each |
| Negative Training Set (.zip) | File upload | Yes | Min 20 files, documents that are NOT this type |
| Detection Method | Dropdown | Yes | Indexed Document Matching / Trainable Classifier |

### Worked Example

**Example 10: Patent Application Detection**
```
Document Type Name: Patent Application Draft
Description: Detects internal patent application drafts before filing
Detection Method: Trainable Classifier
Positive Set: patent_drafts_positive.zip (55 patent draft documents)
Negative Set: patent_drafts_negative.zip (50 non-patent technical documents)
```

---

## S9: Create Data Profile (Standard)

**Navigation:** DLP App > Data Profiles > Create Data Profile

### UI Diagram

```
+-------------------------------------------------------------------------+
| Create Data Profile                                                      |
+-------------------------------------------------------------------------+
| Profile Name:    [________________________________]                       |
| Description:     [________________________________]                       |
| Profile Type:    (x) Standard  ( ) Nested  ( ) Granular                 |
|                                                                          |
| Match Criteria:                                                          |
| +-------------------------------------------------------------------+ |
| | # | Data Pattern          | Occurrence | Confidence | Detection   | |
| |---|----------------------|------------|------------|-------------| |
| | 1 | Credit Card Number   | Any        | --         | Cloud       | |
| | 2 | CCN - ML             | Any        | High       | Cloud       | |
| | 3 | CC Track Data        | Any        | --         | Cloud       | |
| +-------------------------------------------------------------------+ |
| [ + Add Match Criteria ]                                                |
|                                                                          |
| Match Logic: (x) OR (any criterion)  ( ) AND (all criteria)            |
|                                                                          |
| [Cancel]                                        [Save]                   |
+-------------------------------------------------------------------------+
```

### Field Reference

| Field | Type | Required | Default | Constraints |
|-------|------|----------|---------|-------------|
| Profile Name | Text | Yes | -- | Max 255 chars, unique |
| Description | Text | No | -- | Max 1024 chars |
| Profile Type | Radio | Yes | Standard | Standard, Nested, Granular |
| Data Pattern | Dropdown | Yes | -- | Select from available patterns |
| Occurrence | Dropdown/Number | Yes | Any | Any / 1-999 |
| Confidence | Dropdown | Conditional | -- | High / Low (ML patterns only) |
| Detection Type | Dropdown | Yes | Cloud | Cloud Only / Local + Cloud |
| Match Logic | Radio | Yes | OR | OR (any) / AND (all) |

### Worked Examples

**Example 11: PCI-DSS Compliance Profile**
```
Profile Name: PCI-DSS - Payment Card Industry Data
Profile Type: Standard
Match Criteria:
  1. Credit Card Number (regex) | Occurrence: Any | Detection: Cloud
  2. Credit Card Number - ML | Occurrence: Any | Confidence: High | Detection: Cloud
  3. Credit Card Track Data | Occurrence: Any | Detection: Cloud
  4. Credit Card Magnetic Stripe | Occurrence: Any | Detection: Cloud
Match Logic: OR
```

**Example 12: GDPR EU Personal Data Profile**
```
Profile Name: GDPR - EU Personal Data Protection
Profile Type: Standard
Match Criteria:
  1. IBAN (International) | Occurrence: 2+ | Detection: Cloud
  2. EU National ID | Occurrence: Any | Detection: Cloud
  3. EU Passport Number | Occurrence: Any | Detection: Cloud
  4. EU Driver License | Occurrence: Any | Detection: Cloud
  5. GDPR Identifiers - ML | Occurrence: Any | Confidence: High | Detection: Cloud
Match Logic: OR
```

**Example 13: Healthcare PHI Profile**
```
Profile Name: HIPAA - Protected Health Information
Profile Type: Standard
Match Criteria:
  1. Social Security Number - ML | Occurrence: Any | Confidence: High
  2. Medical Record Number | Occurrence: Any
  3. ICD-10 Diagnosis Code | Occurrence: 3+
  4. Patient DB (EDM) | Occurrence: Any
  5. Drug Prescription (custom regex) | Occurrence: Any
Match Logic: OR
```

**Example 14: Source Code and IP Protection**
```
Profile Name: IP - Proprietary Source Code Protection
Profile Type: Standard
Match Criteria:
  1. Proprietary Source Code (custom weighted, threshold: 20) | Occurrence: Any
  2. AWS Access Key | Occurrence: Any
  3. Internal Project Codes (custom basic) | Occurrence: 3+
  4. Patent Draft (custom document type) | Occurrence: Any
Match Logic: OR
```

**Example 15: AI/GenAI Data Leakage Profile**
```
Profile Name: AI Safety - Prevent Data Leakage to GenAI
Profile Type: Standard
Match Criteria:
  1. Credit Card Number - ML | Confidence: High
  2. Social Security Number - ML | Confidence: High
  3. Proprietary Source Code (custom weighted) | Occurrence: Any
  4. Internal Project Codes (custom basic) | Occurrence: 1+
  5. M&A Documents (custom weighted) | Occurrence: Any
Match Logic: OR
```
> **WHY this profile:** Specifically designed for AI app security rules. Combines financial PII, code, and business-sensitive data patterns.

---

## S10: Create Nested Data Profile

**Navigation:** DLP App > Data Profiles > Create Data Profile > Nested

### Field Reference

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| Profile Name | Text | Yes | Max 255 chars |
| Profile Type | Radio | Yes | Must be "Nested" |
| Child Profiles | Multi-select | Yes | Select 2+ existing standard profiles |
| Evaluation | Fixed | -- | OR (any child match triggers parent) |

### Worked Example

**Example 16: All Compliance Nested Profile**
```
Profile Name: All Compliance - Unified Detection
Profile Type: Nested
Child Profiles:
  1. PCI-DSS - Payment Card Industry Data
  2. HIPAA - Protected Health Information
  3. GDPR - EU Personal Data Protection
  4. IP - Proprietary Source Code Protection
  5. AI Safety - Prevent Data Leakage to GenAI
Evaluation: OR (any child triggers parent)
```
> **WHY:** Attach this single nested profile to a security rule instead of creating 5 separate rules. Massively simplifies rule management.

---

## S11: Create Granular Data Profile

**Navigation:** DLP App > Data Profiles > Create Data Profile > Granular

### Field Reference

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| Profile Name | Text | Yes | Max 255 chars |
| Profile Type | Radio | Yes | Must be "Granular" |
| Match Criteria | List | Yes | Each criterion has its own action |
| Per-Criteria Action | Dropdown | Yes | Alert / Block / Allow per criterion |
| Per-Criteria Severity | Dropdown | Yes | Critical / High / Medium / Low / Info |

### Worked Example

**Example 17: Tiered Response Profile**
```
Profile Name: Tiered - Mixed Severity Response
Profile Type: Granular
Match Criteria:
  1. Credit Card Number - ML | Confidence: High | Action: Block | Severity: Critical
  2. SSN - ML | Confidence: High | Action: Block | Severity: Critical
  3. IBAN (International) | Occurrence: 2+ | Action: Alert | Severity: High
  4. Internal Project Codes | Occurrence: 3+ | Action: Alert | Severity: Medium
  5. Source Code Keywords | Occurrence: 5+ | Action: Log Only | Severity: Low
```
> **WHY granular:** Credit card and SSN get blocked immediately. IBAN triggers an alert for review. Project codes and source code are logged for trending analysis.

---

## S12: DLP Rules (SCM)

**Navigation:** SCM > Configuration > Security Services > Data Loss Prevention

### UI Diagram

```
+-------------------------------------------------------------------------+
| Data Loss Prevention Rules                                               |
+-------------------------------------------------------------------------+
| [+ Add Rule]  Search: [________________]                                 |
+-------------------------------------------------------------------------+
| # | Rule Name                    | Data Profile      | Action | Sev    |
|---|-----------------------------|--------------------|--------|--------|
| 1 | Block PCI in Uploads        | PCI-DSS            | Block  | Crit   |
| 2 | Alert HIPAA All Directions  | HIPAA              | Alert  | High   |
| 3 | Block IP to GenAI           | AI Safety          | Block  | Crit   |
| 4 | Monitor GDPR Downloads      | GDPR               | Alert  | Med    |
| 5 | Alert Source Code Upload    | IP Protection      | Alert  | High   |
+-------------------------------------------------------------------------+
```

### Field Reference

| Field | Type | Required | Default | Constraints |
|-------|------|----------|---------|-------------|
| Rule Name | Text | Yes | -- | Max 255 chars |
| Description | Text | No | -- | Max 1024 chars |
| Data Profile | Dropdown | Yes | -- | Must select existing profile |
| Direction | Dropdown | Yes | Both | Upload / Download / Both |
| File Types | Multi-select | Yes | All | All / specific types |
| Action | Dropdown | Yes | Alert | Alert / Block / Allow |
| Log Severity | Dropdown | Yes | Medium | Critical / High / Medium / Low / Informational |

### Worked Examples (5 DLP Rules)

**Rule 1: Block PCI Data in Web Uploads**
```
Rule Name: Block PCI Data in Web Uploads
Data Profile: PCI-DSS - Payment Card Industry Data
Direction: Upload
File Types: All
Action: Block
Log Severity: Critical
```

**Rule 2: Alert on HIPAA Data in All Traffic**
```
Rule Name: Alert HIPAA PHI All Directions
Data Profile: HIPAA - Protected Health Information
Direction: Both
File Types: All
Action: Alert
Log Severity: High
```

**Rule 3: Block Sensitive Data to AI Applications**
```
Rule Name: Block Sensitive Data to GenAI Apps
Data Profile: AI Safety - Prevent Data Leakage to GenAI
Direction: Upload
File Types: All
Action: Block
Log Severity: Critical
```

**Rule 4: Monitor GDPR Data in Downloads**
```
Rule Name: Monitor GDPR Personal Data Downloads
Data Profile: GDPR - EU Personal Data Protection
Direction: Download
File Types: Office Documents, PDF, Text
Action: Alert
Log Severity: Medium
```

**Rule 5: Tiered Response (Granular Profile)**
```
Rule Name: Tiered Data Protection Response
Data Profile: Tiered - Mixed Severity Response
Direction: Both
File Types: All
Action: (per-criteria -- defined in granular profile)
Log Severity: (per-criteria -- defined in granular profile)
```

---

## S13: Data Filtering Profile (Panorama)

**Navigation:** Panorama > Objects > Security Profiles > Data Filtering

### UI Diagram

```
+-------------------------------------------------------------------------+
| Data Filtering Profile                                                   |
+-------------------------------------------------------------------------+
| Profile Name: [________________________________]                         |
|                                                                          |
| Rules:                                                                   |
| +-------------------------------------------------------------------+ |
| | Data Profile | App | File Type | Dir | Alert Thr | Block Thr | Sev | |
| |-------------|-----|-----------|-----|-----------|-----------|-----| |
| | PCI-DSS     | Any | All       | Up  | 1         | 1         | Crit| |
| | HIPAA       | Any | All       | Both| 1         | 10        | High| |
| | Source Code | Web | Text,Code | Up  | 3         | --        | Med | |
| +-------------------------------------------------------------------+ |
| [ + Add Rule ]                                                          |
|                                                                          |
| [Cancel]  [OK]                                                           |
+-------------------------------------------------------------------------+
```

### Panorama-Specific Fields

| Field | Type | Notes |
|-------|------|-------|
| Alert Threshold | Integer | Number of matches to trigger alert |
| Block Threshold | Integer | Number of matches to trigger block |
| Applications | Multi-select | Specific App-IDs or "Any" |

> **KEY DIFFERENCE:** Panorama Data Filtering Profiles support threshold-based escalation (alert at N, block at M) which SCM DLP Rules do NOT support. This gives Panorama users more granular control.

---

## S15: Security Policy Rule (SCM)

**Navigation:** SCM > Configuration > Security Services > Security Policy

### Field Reference

| Field | Type | Required | Default |
|-------|------|----------|---------|
| Rule Name | Text | Yes | -- |
| Source Zone | Multi-select | Yes | Any |
| Destination Zone | Multi-select | Yes | Any |
| Source Address | Multi-select | Yes | Any |
| Destination Address | Multi-select | Yes | Any |
| Source User | Multi-select | No | Any |
| Application | Multi-select | Yes | Any |
| Service | Dropdown | Yes | application-default |
| Action | Dropdown | Yes | Allow |
| Profile Group | Dropdown | No | None |
| Log at Session Start | Boolean | No | No |
| Log at Session End | Boolean | Yes | Yes |
| Log Forwarding | Dropdown | No | None |

### Worked Examples (5 Security Rules with DLP)

**Security Rule 1: General Internet with DLP**
```
Rule Name: Internet Access - DLP Enforced
Source Zone: Trust
Destination Zone: Untrust
Application: Any
Action: Allow
Profile Group: Standard-Security-DLP (contains PCI + HIPAA DLP rules)
```

**Security Rule 2: AI Application Restrictions**
```
Rule Name: AI Apps - Strict DLP Block
Source Zone: Trust
Destination Zone: Untrust
Application: openai-chatgpt, github-copilot, google-gemini, anthropic-claude
Action: Allow
Profile Group: AI-App-Strict-DLP (contains AI Safety block rule)
```

**Security Rule 3: SaaS Application Monitoring**
```
Rule Name: SaaS Uploads - DLP Monitor
Source Zone: Trust
Destination Zone: Untrust
Application: office365-base, box-upload, dropbox-base, google-drive-base
Action: Allow
Profile Group: SaaS-Monitor-DLP (contains GDPR + IP alert rules)
```

**Security Rule 4: Partner Network Access**
```
Rule Name: Partner Zone - Enhanced DLP
Source Zone: Partner-DMZ
Destination Zone: Untrust
Application: Any
Action: Allow
Profile Group: Enhanced-DLP (contains nested All Compliance profile)
```

**Security Rule 5: Guest WiFi - No DLP**
```
Rule Name: Guest WiFi - No DLP Inspection
Source Zone: Guest
Destination Zone: Untrust
Application: web-browsing, ssl
Action: Allow
Profile Group: Basic-Security-No-DLP (AV/AS only, no DLP)
```
> **WHY no DLP on guest:** Guest traffic is not corporate data. DLP inspection wastes resources and may violate privacy expectations.

---

## S18: Incident Management Dashboard

**Navigation:** SCM > Incidents > DLP

### Dashboard Fields

| Field | Description | Values |
|-------|------------|--------|
| Incident ID | Unique identifier | Auto-generated |
| Severity | Severity from DLP rule | Critical / High / Medium / Low |
| Data Profile | Which profile matched | Profile name |
| Data Pattern | Which pattern(s) matched | Pattern name(s) |
| Source | User/IP that triggered | IP address, username |
| Destination | Where data was going | URL, IP, service |
| Action Taken | What enforcement action was applied | Alert / Block |
| File Name | Name of the inspected file | Filename |
| Timestamp | When the incident occurred | Date/time |
| Priority | Incident management priority | P1-P5 |
| Status | Incident lifecycle status | New / Assigned / Resolved / Closed |
| Owner | Assigned analyst | Username |

### Incident Management Modes

| Mode | How It Works |
|------|-------------|
| **Manual** | Security admins manually assign, manage, and resolve incidents |
| **Automatic** | Automation rules assign, manage, and resolve incidents matching configured scope |

### Incident Priority Levels

| Priority | Response Time | Use For |
|----------|-------------|---------|
| P1 | Immediate | Confirmed data breach, active exfiltration |
| P2 | Same day | High-confidence sensitive data exposure |
| P3 | Next business day | Moderate-confidence alerts requiring review |
| P4 | Within a week | Low-confidence alerts, potential false positives |
| P5 | Backlog | Informational, trend analysis |

---

## Complete Cross-Reference: Examples End-to-End

This section shows how all the examples connect into a deployable configuration.

```
PATTERNS (S2-S7)
  Example 1: Custom SSN Detection --------+
  Example 2: AWS Credential Leak --------+|
  Example 3: SWIFT BIC Code ----------+  ||
  Example 4: Classification Labels -+ |  ||
  Example 5: Hospital MRN --------+ | |  ||
  Example 6: M&A Document ------+ | | |  ||
  Example 7: PII Composite ---+ | | | |  ||
  Example 8: C-Suite Docs --+ | | | | |  ||
  Example 9: Customer EDM + | | | | | |  ||
  Example 10: Patent Draft|+|+|+|+|+|+|+||
                          |||||||||||||||  |
PROFILES (S9-S11)         vvvvvvvvvvvvvvv  v
  Example 11: PCI-DSS Profile (predefined CCN + ML)
  Example 12: GDPR Profile (IBAN + EU IDs)
  Example 13: HIPAA Profile (SSN ML + MRN + EDM)
  Example 14: IP Protection Profile (Source Code + AWS + Patent)
  Example 15: AI Safety Profile (aggregates PII + IP)
  Example 16: Nested All Compliance (wraps 11-15)
  Example 17: Tiered Granular (mixed actions per criterion)

DLP RULES (S12-S13)
  Rule 1: Block PCI Uploads (references Example 11)
  Rule 2: Alert HIPAA (references Example 13)
  Rule 3: Block GenAI (references Example 15)
  Rule 4: Monitor GDPR (references Example 12)
  Rule 5: Tiered Response (references Example 17)

SECURITY RULES (S15)
  SecRule 1: Internet + DLP (references Rules 1+2)
  SecRule 2: AI Apps + Strict DLP (references Rule 3)
  SecRule 3: SaaS + Monitor DLP (references Rules 4+5)
  SecRule 4: Partner + Enhanced DLP (references Example 16 nested)
  SecRule 5: Guest WiFi (no DLP)
```

---

## Version and Platform Compatibility Notes

| Feature | PAN-OS 10.x | PAN-OS 11.x | Prisma Access | Cloud NGFW | Cortex XDR 5.x |
|---------|------------|------------|---------------|-----------|----------------|
| Predefined regex patterns | Yes | Yes | Yes | Yes | Yes |
| ML-based patterns | Yes | Yes | Yes | Yes | Yes |
| Custom regex (basic) | Yes | Yes | Yes | Yes | Yes |
| Custom regex (weighted) | Yes | Yes | Yes | Yes | Yes |
| EDM | Yes | Yes | Yes | Yes | TBD |
| Trainable classifiers | Yes | Yes | Yes | Yes | TBD |
| Granular profiles | Limited | Yes | Yes | Yes | TBD |
| Nested profiles | Limited | Yes | Yes | Yes | TBD |
| Endpoint DLP | No | No | No | No | Yes |
| API management | Partial | Yes | Yes | Yes | Separate API |

---

## Regex Testing Reference

### Tools for Testing RE2 Regex

| Tool | URL | Notes |
|------|-----|-------|
| regex101.com | https://regex101.com | Select "Golang" flavor (closest to RE2) |
| DLP App Test Pattern | Built into DLP App | Test against sample content directly |
| re2 online | https://re2js.leopard.in.ua/ | True RE2 syntax validation |

### Common RE2 Regex Patterns for DLP

| Pattern | Regex | Notes |
|---------|-------|-------|
| US SSN | `\b\d{3}-\d{2}-\d{4}\b` | Hyphenated format |
| Credit Card (Visa) | `\b4\d{3}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b` | Starts with 4 |
| Credit Card (MC) | `\b5[1-5]\d{2}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b` | Starts with 51-55 |
| Email Address | `\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z]{2,}\b` | Basic email |
| IPv4 Address | `\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b` | No validation |
| AWS Access Key | `\bAKIA[0-9A-Z]{16}\b` | Prefix-based |
| US Phone | `\b(\+1[\s-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b` | Multiple formats |
