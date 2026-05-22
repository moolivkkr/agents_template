# Authoring Policies -- Complete Field Reference
## Skyhigh Security DLP (SSE Platform)

> Capability: authoring-policies | Generated: 2026-05-21
> Organization: By screen (not by workflow step) -- this is the reference manual
> Enhanced: UI diagrams, worked examples, WHY/GOTCHA annotations per object type

---

## How to Use This Document

This document serves as both a **reference manual** and a **learning guide**. Every major screen includes:

1. **ASCII UI Diagram** -- visual layout of the screen
2. **Field Table** -- every field, type, default, and constraint
3. **Worked Examples** -- complete configurations with all field values (5-7 per object type)
4. **WHY / GOTCHA annotations** -- reasoning and traps

Examples are cross-referenced across levels. Classification examples feed into rule examples, which feed into rule group examples, which feed into policy examples.

---

## Screen Index

| # | Screen | Navigation | Section |
|---|--------|-----------|---------|
| 1 | Classifications List | Policy > DLP Policy > Classifications | [S1](#s1-classifications-list) |
| 2 | Create Classification (Dictionary) | Classifications > Create > Dictionary | [S2](#s2-create-classification-dictionary) |
| 3 | Create Classification (Advanced Pattern) | Classifications > Create > Advanced Pattern | [S3](#s3-create-classification-advanced-pattern) |
| 4 | Create Classification (Keyword) | Classifications > Create > Keyword | [S4](#s4-create-classification-keyword) |
| 5 | Create Classification (Proximity) | Classifications > Create (with Proximity) | [S5](#s5-create-classification-with-proximity) |
| 6 | Create Classification (ML Auto Classifier) | Classifications > Create > ML Auto Classifier | [S6](#s6-create-classification-ml-auto-classifier) |
| 7 | Create Classification (EDM/IDM) | Classifications > Create > EDM/IDM | [S7](#s7-create-classification-edm-idm) |
| 8 | AI RegEx Generator | Classifications > Advanced Pattern > AI RegEx Generator | [S8](#s8-ai-regex-generator) |
| 9 | EDM Fingerprint Management | Policy > DLP Policy > Fingerprints > EDM | [S9](#s9-edm-fingerprint-management) |
| 10 | IDM Fingerprint Management | Policy > DLP Policy > Fingerprints > IDM | [S10](#s10-idm-fingerprint-management) |
| 11 | Sanctioned DLP Policy List | Policy > DLP Policy > Policies | [S11](#s11-sanctioned-dlp-policy-list) |
| 12 | Policy Wizard | Policy > DLP Policy > Policy Wizard | [S12](#s12-policy-wizard) |
| 13 | Policy Editor -- Rule Groups | Policy > Edit > Rule Groups | [S13](#s13-policy-editor-rule-groups) |
| 14 | Policy Editor -- Rules | Policy > Edit > Rules (within group) | [S14](#s14-policy-editor-rules) |
| 15 | Policy Editor -- Exceptions | Policy > Edit > Exceptions | [S15](#s15-policy-editor-exceptions) |
| 16 | Policy Editor -- Response Actions | Policy > Edit > Response Actions | [S16](#s16-policy-editor-response-actions) |
| 17 | Evaluate Policy Rules | Policy > DLP Policy > Evaluate Rules | [S17](#s17-evaluate-policy-rules) |
| 18 | Incidents Page | Incidents > DLP | [S18](#s18-incidents-page) |

---

## S1: Classifications List

**Navigation:** Policy > DLP Policy > Classifications
**Purpose:** Browse, search, and manage all classifications

### UI Diagram

```
+-------------------------------------------------------------------------+
| Policy > DLP Policy > Classifications                                    |
+-------------------------------------------------------------------------+
| [+ Create Classification]  Search: [________________]                    |
+-------------------------------------------------------------------------+
| Name                     | Type           | Definition    | Actions     |
|--------------------------|----------------|---------------|-------------|
| PII - US SSN             | Custom         | Adv. Pattern  | Edit | Del  |
| PII - SSN with Context   | Custom         | Proximity     | Edit | Del  |
| PCI - Credit Card        | Built-in       | Adv. Pattern  | View        |
| PCI - CCN with Context   | Custom         | Proximity     | Edit | Del  |
| HIPAA - Medical Terms    | Custom         | Dictionary    | Edit | Del  |
| Financial - IBAN         | Custom         | Adv. Pattern  | Edit | Del  |
| Financial - ML Reports   | Custom         | ML Classifier | Edit | Del  |
| IP - Patent Drafts       | Custom         | IDM           | Edit | Del  |
| Customer DB Match        | Custom         | EDM           | Edit | Del  |
|                          |                |               |             |
| Showing 50 classifications                                | Page 1/3    |
+-------------------------------------------------------------------------+
```

---

## S2: Create Classification (Dictionary)

**Navigation:** Classifications > Create Classification > Dictionary

### UI Diagram

```
+-------------------------------------------------------------------------+
| Create Classification                                                    |
+-------------------------------------------------------------------------+
| Classification Name: [________________________________]                  |
| Description:         [________________________________]                  |
|                                                                          |
| Definition Type:  [Dictionary          v]                                |
|                                                                          |
| Dictionary:       [Medical Terminology v]  [+ Create Custom Dictionary]  |
|                                                                          |
| Score Threshold:  [____5____]                                            |
|                                                                          |
| Location:         [x] Body  [ ] Header  [ ] Footer  [ ] First N chars   |
|                   First N characters: [____]                             |
|                                                                          |
| [ ] Enable Proximity                                                     |
|                                                                          |
| [Cancel]                                        [Save]                   |
+-------------------------------------------------------------------------+
```

### Field Reference

| Field | Type | Required | Default | Constraints | Notes |
|-------|------|----------|---------|-------------|-------|
| Classification Name | Text | Yes | -- | Max 255 chars, unique | Descriptive naming recommended |
| Description | Text | No | -- | Max 1024 chars | Document purpose and data type |
| Definition Type | Dropdown | Yes | -- | Dictionary, Advanced Pattern, Keyword, Document Properties, File Name Set, File Sizes, True File Type, ML Auto Classifier, EDM, IDM | Determines available sub-fields |
| Dictionary | Dropdown | Yes (for Dictionary type) | -- | Built-in or custom dictionaries | Custom dictionaries can be created inline |
| Score Threshold | Integer | Yes | 1 | 1 to N (no documented max) | Number of keyword matches needed |
| Location | Checkbox | Yes | Body | Body, Header, Footer, First N chars | Where in the document to scan |
| Enable Proximity | Checkbox | No | Unchecked | -- | Enables proximity matching with second definition |

### Worked Examples

**Example 1: HIPAA Medical Terminology**
```
Classification Name: HIPAA - Medical Terminology
Definition Type: Dictionary
Dictionary: Medical Terminology (built-in)
Score Threshold: 5
Location: Body
Proximity: Disabled
```
> **WHY threshold 5:** Medical terms appear in general health articles. Requiring 5+ matches ensures the document is a medical record, not a news article.

**Example 2: Financial Earnings Keywords**
```
Classification Name: Financial - Quarterly Earnings
Definition Type: Dictionary
Dictionary: Custom (revenue, net income, earnings per share, EBITDA, operating margin, gross profit, cash flow, guidance, forecast, dividend)
Score Threshold: 4
Location: Body
```
> **WHY threshold 4:** Financial terms individually appear in general business communication. 4+ terms strongly indicates an earnings document.

**Example 3: Profanity Filter**
```
Classification Name: Content - Profanity
Definition Type: Dictionary
Dictionary: Profanity and Offensive Language (built-in)
Score Threshold: 1
Location: Body
```

**Example 4: Legal Contract Terms**
```
Classification Name: Legal - Contract Language
Definition Type: Dictionary
Dictionary: Custom (whereas, hereinafter, indemnify, covenant, warranty, representation, termination clause, liquidated damages, force majeure, arbitration)
Score Threshold: 6
Location: Body
```

**Example 5: Source Code Keywords**
```
Classification Name: DevOps - Source Code Keywords
Definition Type: Dictionary
Dictionary: Custom (import, from, require, function, class, interface, extends, implements, public static void, def __init__)
Score Threshold: 8
Location: Body
```
> **WHY threshold 8:** Low-count code keywords appear in documentation. 8+ strongly indicates actual source code.

---

## S3: Create Classification (Advanced Pattern)

**Navigation:** Classifications > Create Classification > Advanced Pattern

### UI Diagram

```
+-------------------------------------------------------------------------+
| Create Classification                                                    |
+-------------------------------------------------------------------------+
| Classification Name: [________________________________]                  |
| Description:         [________________________________]                  |
|                                                                          |
| Definition Type:  [Advanced Pattern    v]                                |
|                                                                          |
| Pattern:          [Select Pattern      v]  [+ Create Custom Pattern]     |
|                   [AI RegEx Generator]                                   |
|                                                                          |
| Validator:        [ ] Luhn  [ ] BIN  [ ] Checksum  [ ] Custom            |
|                                                                          |
| Score Threshold:  [____1____]                                            |
|                                                                          |
| Location:         [x] Body  [ ] Header  [ ] Footer  [ ] First N chars   |
|                                                                          |
| [ ] Enable Proximity                                                     |
|                                                                          |
| [Cancel]                                        [Save]                   |
+-------------------------------------------------------------------------+
```

### Field Reference

| Field | Type | Required | Default | Constraints |
|-------|------|----------|---------|-------------|
| Pattern | Dropdown/Text | Yes | -- | Google RE2 syntax; select built-in or create custom |
| Validator | Checkbox | No | None | Luhn, BIN, Checksum, Custom |
| Score Threshold | Integer | Yes | 1 | Number of pattern matches required |
| Location | Checkbox | Yes | Body | Where to scan |

### RE2 Regex Engine Constraints

Same as Palo Alto -- Google RE2 engine:
- **Supported:** Character classes, alternation, quantifiers, groups, anchors, named groups
- **NOT supported:** Negative lookahead `(?!...)`, lookbehind `(?<=...)`, backreferences `\1`, possessive quantifiers, atomic groups

### Worked Examples

**Example 6: US Social Security Number**
```
Classification Name: PII - US SSN
Definition Type: Advanced Pattern
Pattern: \b\d{3}-\d{2}-\d{4}\b
Validator: None
Score Threshold: 1
Location: Body
```

**Example 7: Credit Card with Luhn Validation**
```
Classification Name: PCI - Credit Card (Luhn Validated)
Definition Type: Advanced Pattern
Pattern: \b(?:4\d{3}|5[1-5]\d{2}|3[47]\d{2}|6(?:011|5\d{2}))\d{12}\b
Validator: Luhn Algorithm ENABLED
Score Threshold: 1
Location: Body
```
> **WHY Luhn:** Without Luhn validation, any 16-digit number matches. With Luhn, only numbers that pass the credit card checksum algorithm trigger. Reduces false positives by ~90%.

**Example 8: AWS Access Key ID**
```
Classification Name: DevOps - AWS Access Key
Definition Type: Advanced Pattern
Pattern: \bAKIA[0-9A-Z]{16}\b
Validator: None
Score Threshold: 1
Location: Body
```

**Example 9: UK National Insurance Number**
```
Classification Name: GDPR - UK NIN
Definition Type: Advanced Pattern
Pattern: \b[A-CEGHJ-PR-TW-Z]{2}\d{6}[A-D]\b
Validator: None
Score Threshold: 1
Location: Body
```

**Example 10: Custom Internal Project Code**
```
Classification Name: Internal - Project Code
Definition Type: Advanced Pattern
Pattern: \b(PROJ|PRJ)-[A-Z]{2,4}-\d{4,8}\b
Validator: None
Score Threshold: 3
Location: Body
```
> **WHY threshold 3:** A single project code reference is normal. 3+ in one document suggests a project summary or status report.

---

## S4: Create Classification (Keyword)

### Field Reference

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| Keyword | Text | Yes | Simple string value |
| Score Threshold | Integer | Yes | Number of keyword occurrences |
| Location | Checkbox | Yes | Body, Header, Footer, First N chars |

### Worked Example

**Example 11: Classification Label Detection**
```
Classification Name: Labels - Confidential Marking
Definition Type: Keyword
Keyword: CONFIDENTIAL
Score Threshold: 1
Location: Header, Footer
```
> **WHY Header/Footer only:** Classification labels like "CONFIDENTIAL" typically appear in document headers and footers. Scanning the body would match the word in general discussion.

---

## S5: Create Classification (with Proximity)

### UI Diagram

```
+-------------------------------------------------------------------------+
| Create Classification (Proximity Enabled)                                |
+-------------------------------------------------------------------------+
| Classification Name: [PII - SSN with Context_________________________]  |
|                                                                          |
| Primary Definition:                                                      |
|   Type: [Advanced Pattern v]                                             |
|   Pattern: [\b\d{3}-\d{2}-\d{4}\b___________________________]          |
|                                                                          |
| [x] Enable Proximity                                                     |
|                                                                          |
| Secondary Definition:                                                    |
|   Type: [Keyword          v]                                             |
|   Value: [social security_________________________________]              |
|                                                                          |
| Proximity Distance: [___100___] characters                               |
|                                                                          |
| [Cancel]                                        [Save]                   |
+-------------------------------------------------------------------------+
```

### Field Reference

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| Primary Definition | Any definition type | Yes | First pattern to match |
| Secondary Definition | Any definition type | Yes | Second pattern to match |
| Proximity Distance | Integer | Yes | 1 to 10000 characters |

### Worked Examples

**Example 12: SSN Near Social Security Keyword**
```
Classification Name: PII - SSN with Context
Primary: Advanced Pattern (\b\d{3}-\d{2}-\d{4}\b)
Secondary: Keyword "social security"
Proximity Distance: 100 characters
```
> **WHY 100 chars:** In a typical sentence, "Social Security Number: 123-45-6789" spans ~40 characters. 100 characters allows for a brief sentence between the keyword and the number.

**Example 13: Credit Card Near Payment Keywords**
```
Classification Name: PCI - CCN with Payment Context
Primary: Advanced Pattern (credit card regex with Luhn)
Secondary: Dictionary (card number, credit card, visa, mastercard, expiration, CVV)
Proximity Distance: 150 characters
```

**Example 14: IBAN Near Bank Keywords**
```
Classification Name: Financial - IBAN with Bank Context
Primary: Advanced Pattern (IBAN regex)
Secondary: Dictionary (bank, account, transfer, wire, SWIFT, BIC, routing)
Proximity Distance: 200 characters
```

**Example 15: Patient ID Near Medical Keywords**
```
Classification Name: HIPAA - Patient ID with Medical Context
Primary: Advanced Pattern (\bMRN[:\s]*\d{7,10}\b)
Secondary: Dictionary (patient, diagnosis, treatment, prescription, physician, hospital)
Proximity Distance: 300 characters
```
> **WHY 300 chars:** Medical records have denser formatting. Patient IDs may be separated from medical context by headers, tables, or line breaks.

---

## S6: Create Classification (ML Auto Classifier)

### Field Reference

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| Classifier | Dropdown | Yes | Financial Reports, Patient Records, Patents, Source Code (text); ID Documents, Credit Cards, Checks (image) |
| Location | Checkbox | Yes | Body |

### Worked Examples

**Example 16: Financial Report Auto-Detection**
```
Classification Name: Financial - ML Auto Reports
Definition Type: ML Auto Classifier
Classifier: Financial Reports/Statements
Location: Body
```

**Example 17: Source Code Auto-Detection**
```
Classification Name: DevOps - ML Auto Source Code
Definition Type: ML Auto Classifier
Classifier: Source Code
Location: Body
```

> **GOTCHA:** Text-based ML classifiers detect content ONLY in English. Non-English financial reports or patient records will NOT be detected by ML Auto Classifiers. Use regex/dictionary as fallback for non-English content.

---

## S8: AI RegEx Generator

**Navigation:** Classifications > Advanced Pattern > AI RegEx Generator button

### UI Diagram

```
+-------------------------------------------------------------------------+
| AI RegEx Generator                                                       |
+-------------------------------------------------------------------------+
| Ask the AI to build a regex pattern:                                     |
|                                                                          |
| [Match US phone numbers in (XXX) XXX-XXXX format________________]       |
|                                                                          |
| [Generate]                                                               |
|                                                                          |
| Generated Pattern:                                                       |
| +-------------------------------------------------------------------+ |
| | \b\(\d{3}\)\s?\d{3}[-.]?\d{4}\b                                  | |
| +-------------------------------------------------------------------+ |
|                                                                          |
| Explanation:                                                             |
| \b       - Word boundary                                                 |
| \(\d{3}\)- Three digits in parentheses                                   |
| \s?      - Optional space                                                |
| \d{3}    - Three digits                                                  |
| [-.]?    - Optional hyphen or period                                     |
| \d{4}    - Four digits                                                   |
| \b       - Word boundary                                                 |
|                                                                          |
| [Use This Pattern]  [Refine]  [New Query]                                |
+-------------------------------------------------------------------------+
```

### Key Features
- Conversational interface -- refine patterns iteratively
- Generates Google RE2-compliant regex (not PCRE)
- Provides explanation of each regex component
- Integrated directly into classification creation workflow

### Example Queries

| Query | Generated Regex | Use For |
|-------|----------------|---------|
| "Match US phone numbers" | `\b\(\d{3}\)\s?\d{3}[-.]?\d{4}\b` | PII phone detection |
| "Match email addresses" | `\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z]{2,}\b` | PII email detection |
| "Match IPv4 addresses" | `\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b` | Network data detection |
| "Match dates in MM/DD/YYYY format" | `\b(0[1-9]\|1[0-2])/(0[1-9]\|[12]\d\|3[01])/\d{4}\b` | Date detection |
| "Match hex color codes" | `#[0-9a-fA-F]{6}\b` | Source code detection |

> **GOTCHA:** NEVER enter real sensitive data into the AI RegEx Generator. Use pattern descriptions only. The queries are sent to an external AI service.

---

## S9: EDM Fingerprint Management

**Navigation:** Policy > DLP Policy > Fingerprints > EDM

### EDM Creation Workflow

```
Step 1: Install DLP Integrator v6.4.0+
  Platform: Windows or Linux
  Download: From Skyhigh Dashboard > Settings > Downloads

Step 2: Prepare Source CSV
  +------------------------------------------------------------------+
  | ssn,first_name,last_name,dob,email,account_number                |
  | 123-45-6789,John,Doe,1990-01-15,john@company.com,ACC001234      |
  | 987-65-4321,Jane,Smith,1985-03-22,jane@company.com,ACC005678     |
  +------------------------------------------------------------------+

Step 3: Create Enhanced Fingerprint
  Navigate to: Fingerprints > Create > Structured > Enhanced
  Source file: /path/to/customer_records.csv
  Delimiter: Comma
  Configure columns:
    | Column | Type | Primary | Indexed |
    | ssn | SSN | Yes | Yes |
    | first_name | Name | No | Yes |
    | last_name | Name | No | Yes |
    | dob | Date | No | Yes |
    | email | Email | No | Yes |
    | account_number | Custom | No | Yes |

Step 4: Upload to Skyhigh Cloud
  DLP Integrator hashes + encrypts + uploads

Step 5: Create Classification referencing EDM fingerprint
```

### Worked Example

**Example 18: Customer Database EDM**
```
Fingerprint Name: Customer PII Database Q2 2026
Source: customer_export_2026Q2.csv
Records: 100,000
Columns: ssn (primary), first_name, last_name, dob, email, account_number

Classification Name: PII - Customer Database Match
Definition Type: EDM Fingerprint
Fingerprint: Customer PII Database Q2 2026
Score Threshold: 1 (any record match)
```

---

## S10: IDM Fingerprint Management

**Navigation:** Policy > DLP Policy > Fingerprints > IDM

### IDM Creation Workflow

```
Step 1: Install DLP Integrator with IDMTrain tool

Step 2: Collect Training Documents
  /documents/patents/*.pdf (50 patent drafts)
  /documents/contracts/*.docx (30 contract templates)

Step 3: Run IDMTrain
  $ idmtrain --source /documents/patents/ --output patent_fingerprint.idx

Step 4: Upload to Skyhigh Cloud
  Navigate to: Fingerprints > IDM > Upload
  Select fingerprint file

Step 5: Create Classification with Unstructured Match Condition
  Match Percentage: 30% (partial match)
```

### Match Percentage Configuration

| Percentage | Meaning | Use For |
|-----------|---------|---------|
| 10-20% | Very loose match | Detect documents that share small portions |
| 30-50% | Moderate match | Detect partial copies, excerpts, derivatives |
| 60-80% | Tight match | Detect near-complete copies with minor edits |
| 90-100% | Exact match | Detect full copies only |

### Worked Example

**Example 19: Patent Draft IDM**
```
Fingerprint Name: Patent Application Drafts 2026
Source: 55 patent draft PDFs
Match Percentage: 30%

Classification Name: IP - Patent Draft Match
Definition Type: IDM Fingerprint
Fingerprint: Patent Application Drafts 2026
Unstructured Match Condition: 30% content match
```

---

## S13: Policy Editor -- Rule Groups

**Navigation:** Policy > Edit > Rule Groups section

### UI Diagram

```
+-------------------------------------------------------------------------+
| Policy: PCI Protection | Status: Enabled                                |
+-------------------------------------------------------------------------+
| Rules | Exceptions | Response Actions | Review                          |
+-------------------------------------------------------------------------+
| Rule Groups (combined with OR):                                          |
|                                                                          |
| [+ New Rule Group]                                                       |
|                                                                          |
| Rule Group 1: "Credit Card Detection"  [Severity: Critical]             |
|   Logic within group: AND                                                |
|   +---------------------------------------------------------------+     |
|   | Rule 1: Classification "PCI - CCN with Context" >= 1 match    |     |
|   | Rule 2: True File Type IS NOT image/*                         |     |
|   +---------------------------------------------------------------+     |
|   [Edit] [Delete]                                                        |
|                                                                          |
| Rule Group 2: "Track Data Detection"  [Severity: Critical]              |
|   Logic within group: OR                                                 |
|   +---------------------------------------------------------------+     |
|   | Rule 1: Classification "PCI - Track Data" >= 1 match          |     |
|   +---------------------------------------------------------------+     |
|   [Edit] [Delete]                                                        |
|                                                                          |
| Rule Group 3: "Earnings Keywords"  [Severity: Minor]                    |
|   Logic within group: AND                                                |
|   +---------------------------------------------------------------+     |
|   | Rule 1: Classification "Financial - Quarterly Earnings" >= 4  |     |
|   | Rule 2: Classification "Labels - Confidential" >= 1           |     |
|   +---------------------------------------------------------------+     |
|   [Edit] [Delete]                                                        |
+-------------------------------------------------------------------------+
```

### Field Reference

| Field | Type | Required | Default | Constraints |
|-------|------|----------|---------|-------------|
| Rule Group Name | Text | Yes | -- | Max 255 chars |
| Severity | Dropdown | Yes | Warning | Critical / Major / Minor / Warning / Info |
| Logic (within group) | Toggle | Yes | AND | AND / OR |
| Rules | List | Yes (min 1) | -- | At least one rule required per group |

### Worked Examples (5 Rule Group Configurations)

**Example 20: PCI Full Protection**
```
Rule Group: Credit Card Full Detection
Severity: Critical
Logic: AND
Rules:
  1. Classification "PCI - CCN with Context" >= 1
  2. File Type is Office Document OR PDF OR Text
```
> **WHY AND logic:** Both credit card pattern AND non-image file type must match. This prevents flagging credit card numbers in image files (which are typically marketing materials showing card designs).

**Example 21: HIPAA Patient Data**
```
Rule Group: Patient Data Detection
Severity: Major
Logic: OR
Rules:
  1. Classification "HIPAA - Medical Terminology" >= 5
  2. Classification "PII - SSN with Context" >= 1
  3. Classification "HIPAA - Patient ID with Medical Context" >= 1
  4. EDM Fingerprint "Patient Database" >= 1 match
```
> **WHY OR logic:** Any one of these indicators is sufficient to flag potential PHI.

**Example 22: Source Code Leak Prevention**
```
Rule Group: Source Code Exfiltration
Severity: Major
Logic: AND
Rules:
  1. Classification "DevOps - ML Auto Source Code" (ML classifier)
  2. Classification "Internal - Project Code" >= 2
```
> **WHY AND:** ML source code detection alone is too broad (flags any code snippet). Combined with internal project codes, it narrows to OUR proprietary code.

**Example 23: Insider Threat Detection**
```
Rule Group: High-Risk User Activity
Severity: Critical
Logic: AND
Rules:
  1. User Risk Rule: Risk Level = High
  2. Classification "Financial - ML Auto Reports" (ML classifier)
```
> **WHY:** High-risk users (from UEBA) accessing financial reports is a strong insider threat indicator.

**Example 24: Multi-Layer GDPR Detection**
```
Rule Group: EU Personal Data (High Confidence)
Severity: Major
Logic: AND
Rules:
  1. Classification "GDPR - UK NIN" >= 1
  2. Classification "PII - SSN with Context" >= 0 (use as exclusion)

Rule Group: EU Personal Data (Any Match)
Severity: Minor
Logic: OR
Rules:
  1. Classification "Financial - IBAN with Bank Context" >= 1
  2. Classification "GDPR - UK NIN" >= 1
  3. EDM Fingerprint "EU Customer Database" >= 1
```

---

## S16: Policy Editor -- Response Actions

### Field Reference

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| Action | Dropdown | Yes | Create Incident, Email Notification, Block, Quarantine, Encrypt, Coach User, Apply Label, Custom |
| Severity Condition | Dropdown | No | Critical, Major, Minor, Warning, Info |
| Incident Status | Dropdown | Conditional | New, Open, In Progress, Resolved |
| Incident Owner | Dropdown | No | User or group |
| Email Recipient | Text | Conditional | Valid email address |
| User Coaching Message | Text | Conditional | Free text (displayed to user) |

### Worked Example -- Comprehensive Response Configuration

**Example 25: Tiered Response for PCI Policy**
```
Policy: PCI Protection

Response Actions:
  When Severity = Critical:
    1. Block file upload/download
    2. Quarantine file to admin folder
    3. Create Incident (status: New, owner: security-team)
    4. Email notification to security-ops@company.com

  When Severity = Major:
    1. Block file upload/download
    2. Create Incident (status: New, owner: security-team)
    3. Email notification to security-ops@company.com

  When Severity = Minor:
    1. Coach User: "This file may contain payment card data. Please verify before sharing."
    2. Create Incident (status: New, owner: auto-review)

  When Severity = Warning:
    1. Create Incident (status: New, owner: auto-review)
```

---

## S17: Evaluate Policy Rules

**Navigation:** Policy > DLP Policy > Evaluate Rules

### UI Diagram

```
+-------------------------------------------------------------------------+
| Evaluate Policy Rules                                                    |
+-------------------------------------------------------------------------+
| Upload Test Content:  [Choose File]  or  Paste Text: [______________]   |
|                                                                          |
| Select Policy:  [PCI Protection            v]                            |
|                                                                          |
| [Evaluate]                                                               |
|                                                                          |
| Results:                                                                 |
| +-------------------------------------------------------------------+ |
| | Rule Group: Credit Card Detection | MATCHED | Severity: Critical  | |
| |   Rule 1: PCI - CCN with Context | MATCHED (3 matches found)     | |
| |   Rule 2: File Type IS document  | MATCHED                       | |
| |                                                                   | |
| | Rule Group: Track Data           | NOT MATCHED                   | |
| |   Rule 1: PCI - Track Data      | NOT MATCHED (0 matches)       | |
| |                                                                   | |
| | Rule Group: Earnings Keywords    | NOT MATCHED                   | |
| |   Rule 1: Financial Keywords     | NOT MATCHED (1 match < 4)     | |
| +-------------------------------------------------------------------+ |
| Policy Verdict: TRIGGERED (Critical)                                     |
+-------------------------------------------------------------------------+
```

> **WHY use this tool:** Test BEFORE deploying. Catches logic errors, threshold mistakes, and missing classifications without affecting production traffic.

---

## Complete Cross-Reference: Examples End-to-End

```
CLASSIFICATIONS (S2-S7)
  Ex 1: HIPAA Medical Terms (Dictionary) ----+
  Ex 2: Financial Earnings (Dictionary) ----+|
  Ex 3: Profanity (Dictionary) -----------+ ||
  Ex 4: Legal Contract (Dictionary) -----+| ||
  Ex 5: Source Code Keywords (Dict) ----+|| ||
  Ex 6: PII US SSN (Regex) -----------+||| ||
  Ex 7: PCI CCN Luhn (Regex) -------+|||| ||
  Ex 8: AWS Key (Regex) -----------+||||| ||
  Ex 9: UK NIN (Regex) ----------+|||||| ||
  Ex 10: Project Code (Regex) -+||||||| ||
  Ex 11: Confidential (KW) --+|||||||| ||
  Ex 12: SSN+Context (Prox) +||||||||| ||
  Ex 13: CCN+Payment (Prox) |||||||||| ||
  Ex 14: IBAN+Bank (Prox) --|||||||||| ||
  Ex 15: Patient+Med (Prox) |||||||||| ||
  Ex 16: ML Financial ------|||||||||| ||
  Ex 17: ML Source Code ----|||||||||| ||
  Ex 18: Customer EDM -----|||||||||| ||
  Ex 19: Patent IDM -------|||||||||| ||
                            vvvvvvvvvv vv

RULE GROUPS (S13)
  Ex 20: PCI Full Protection (AND: CCN+Context + FileType)
  Ex 21: HIPAA Patient Data (OR: MedTerms OR SSN OR PatientID OR EDM)
  Ex 22: Source Code Leak (AND: ML Source + Project Codes)
  Ex 23: Insider Threat (AND: High Risk User + ML Financial)
  Ex 24: GDPR Multi-Layer (2 groups at different severities)

RESPONSE ACTIONS (S16)
  Ex 25: Tiered Response (Critical->Block, Major->Block, Minor->Coach)

POLICIES
  Policy 1: PCI Protection (groups 20) -> Response Ex 25
  Policy 2: HIPAA Protection (group 21) -> Response: Major=Alert, Critical=Block
  Policy 3: IP Protection (groups 22) -> Response: Major=Block
  Policy 4: Insider Threat (group 23) -> Response: Critical=Block+Quarantine
  Policy 5: GDPR Protection (groups 24) -> Response: Tiered by severity
```

---

## Common Regex Patterns for Skyhigh DLP (RE2 Compatible)

| Pattern | Regex | Validator | Notes |
|---------|-------|-----------|-------|
| US SSN (hyphenated) | `\b\d{3}-\d{2}-\d{4}\b` | None | Basic format |
| US SSN (all formats) | `\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b` | None | Hyphen, space, or none |
| Credit Card (Visa) | `\b4\d{3}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b` | Luhn | Starts with 4 |
| Credit Card (MC) | `\b5[1-5]\d{2}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b` | Luhn | 51-55 prefix |
| Credit Card (Amex) | `\b3[47]\d{2}[\s-]?\d{6}[\s-]?\d{5}\b` | Luhn | 34/37 prefix, 15 digits |
| IBAN | `\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}([A-Z0-9]?){0,16}\b` | None | International |
| Email | `\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z]{2,}\b` | None | Basic |
| US Phone | `\b(\+1[\s-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b` | None | Multiple formats |
| IPv4 | `\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b` | None | No range validation |
| AWS Access Key | `\bAKIA[0-9A-Z]{16}\b` | None | Prefix-based |
| UK NIN | `\b[A-CEGHJ-PR-TW-Z]{2}\d{6}[A-D]\b` | None | UK National Insurance |
| US Passport | `\b[A-Z]\d{8}\b` | None | Letter + 8 digits |
| Date (MM/DD/YYYY) | `\b(0[1-9]\|1[0-2])/(0[1-9]\|[12]\d\|3[01])/\d{4}\b` | None | US format |
| ICD-10 Code | `\b[A-Z]\d{2}(\.\d{1,4})?\b` | None | Medical diagnosis codes |

---

## Skyhigh vs Trellix Classification Mapping

For organizations using both cloud (Skyhigh) and endpoint (Trellix) DLP:

| Skyhigh Classification Type | Trellix Equivalent | Sync? |
|----------------------------|-------------------|-------|
| Dictionary | Dictionary Definition | Manual recreation required |
| Advanced Pattern (regex) | Advanced Pattern Definition | Manual recreation required |
| Keyword | Keyword Definition | Manual recreation required |
| EDM Fingerprint | EDM (via ePO) | Separate EDM instances |
| IDM Fingerprint | Registered Documents | Separate fingerprint instances |
| ML Auto Classifier | No equivalent | Skyhigh-only feature |
| Document Properties | Document Properties Definition | Manual recreation required |
| File Name Set | File Extension Definition | Manual recreation required |
| Proximity | No direct equivalent | Not available in Trellix |
| User Risk (UEBA) | No equivalent | Skyhigh-only feature |

> **CRITICAL:** Classifications do NOT auto-sync between Skyhigh and Trellix. If you need the same detection on both cloud and endpoint, you must configure it in BOTH consoles.
