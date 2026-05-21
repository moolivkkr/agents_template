# Classifications & Dictionaries — Complete Workflow
## Broadcom Symantec DLP (Enforce Server, version 16.x/25.x/26.x)

> **Capability:** Classifications & Dictionaries (System-Defined Data Identifiers, Custom Dictionaries, Classification Policies, Sensitivity Labels)
> **Complexity Score:** MEDIUM-HIGH
> **Evidence sources:** doc-corpus.md [S1-S28], video-intelligence.md [V1-V45], api-intelligence.md [API surfaces 1-6]

---

## Overview

Classifications and dictionaries in Broadcom Symantec DLP represent the **organizational layer** on top of raw data definitions. While data definitions answer "what patterns exist in this content?", classifications and dictionaries answer "what does this content MEAN in our organization's data governance framework?"

This capability bridges raw detection technology (data identifiers, regex, keywords) with organizational data governance (classification hierarchies, sensitivity levels, compliance mappings). It is the layer where technical detection becomes business-meaningful classification.

**The four classification components:**

| # | Component | Purpose | Depends On | Evidence |
|---|-----------|---------|-----------|----------|
| 1 | System-Defined Data Identifiers | Pre-built detection library organized by regulation/category | Built-in (no setup) | A [S1, S4, S8] |
| 2 | Custom Dictionaries | Organization-specific word/phrase lists for domain detection | Manual creation or CSV import | A [S1, S8] |
| 3 | Classification Policies | Rules combining identifiers + dictionaries with scoring/severity | Data identifiers + dictionaries must exist first | A [S1, S4] |
| 4 | Sensitivity Labels (MIP) | Integration with Microsoft Information Protection labels | MIP SDK installed on Enforce Server | A [S1, S2, S3] |

**How these components relate:**

```
+------------------------------------------------------------------+
|  CLASSIFICATION HIERARCHY                                         |
+------------------------------------------------------------------+
|                                                                    |
|  System-Defined Data Identifiers (30+)                            |
|  +-- PCI: Credit Card, Visa, MC, Amex, Discover, JCB, UnionPay  |
|  +-- PII: SSN, Passport, Driver License, National IDs             |
|  +-- PHI: DEA, NPI, ICD, NDC, HICN                               |
|  +-- Financial: IBAN, SWIFT, Routing Number                       |
|  +-- Regional: per-country identifiers                            |
|           |                                                        |
|           v                                                        |
|  Custom Dictionaries                                               |
|  +-- Medical terminology (2,800 terms)                            |
|  +-- Legal terminology (1,500 terms)                              |
|  +-- Financial jargon (900 terms)                                 |
|  +-- Project code names (50 terms)                                |
|  +-- Competitor names (200 terms)                                 |
|           |                                                        |
|           v                                                        |
|  Classification Policies                                           |
|  +-- "PCI Data" = CC identifier + financial dictionary             |
|  +-- "HIPAA PHI" = SSN + DEA + medical dictionary + EDM           |
|  +-- "Confidential IP" = project codes + VML + IDM                |
|  +-- Compound scoring: high/medium/low based on match quality      |
|           |                                                        |
|           v                                                        |
|  Sensitivity Labels (MIP Integration)                              |
|  +-- Read labels: detect labeled documents                        |
|  +-- Write labels: apply labels based on DLP classification       |
|  +-- Cross-platform: labels persist in Office, PDF, email         |
|                                                                    |
+------------------------------------------------------------------+
```

[S1, S4, S8, V3, V6, V22]

---

## Complexity Score: MEDIUM-HIGH

**Justification:**

1. **30+ built-in data identifiers** with per-identifier configuration (breadth, threshold, validation algorithms)
2. **Custom dictionary lifecycle** -- creation, import, threshold tuning, versioning, ongoing maintenance
3. **Compound classification logic** -- AND/OR/NOT combinations of identifiers and dictionaries with weighted scoring
4. **Multi-tier severity mapping** -- different severity levels based on match quantity and quality
5. **MIP label integration** -- bidirectional label reading/writing requires SDK setup and tenant configuration
6. **False positive management** -- dictionary threshold tuning is iterative and environment-specific
7. **API gap for on-prem** -- classification creation is console-only; CloudSOC API has more granular profile/identifier access

---

## Component 1: System-Defined Data Identifiers

### What System-Defined Data Identifiers Are

System-defined data identifiers are Symantec's pre-built detection library. Each identifier combines a pattern (regular expression or algorithm) with a domain-specific validator that reduces false positives. They are available out-of-the-box and require no configuration beyond selecting them in a detection rule. [S1, S4, S8]

**Navigation:** Policy editor > Add Rule > Content Matches Data Identifier > [select from dropdown]

### Identifier Selection Screen

```
+=========================================================================+
|  Data Identifier Selection                                               |
+=========================================================================+
|                                                                          |
|  Search: [                    ] [Filter]                                 |
|                                                                          |
|  Category Filter: [All Categories        v]                              |
|                                                                          |
|  +------------------------------------------------------------------+   |
|  | Category          | Identifier                | Validator         |   |
|  |-------------------|---------------------------|-------------------|   |
|  | Payment Cards     | Credit Card Number        | Luhn (mod-10)     |   |
|  | Payment Cards     | Visa Card                 | Luhn + prefix     |   |
|  | Payment Cards     | Mastercard                | Luhn + prefix     |   |
|  | Payment Cards     | American Express          | Luhn + prefix     |   |
|  | Payment Cards     | Discover                  | Luhn + prefix     |   |
|  | Payment Cards     | JCB                       | Luhn + prefix     |   |
|  | Payment Cards     | UnionPay                  | Luhn + prefix     |   |
|  | Payment Cards     | Diners Club               | Luhn + prefix     |   |
|  |-------------------|---------------------------|-------------------|   |
|  | US PII            | US Social Security Number | Area/group/serial |   |
|  | US PII            | US Driver License         | Per-state format  |   |
|  | US PII            | US Passport Number        | Format            |   |
|  | US PII            | US ITIN                   | Prefix (9xx)      |   |
|  | US PII            | US EIN                    | Campus prefix     |   |
|  |-------------------|---------------------------|-------------------|   |
|  | UK PII            | UK NINO                   | Prefix exclusion  |   |
|  | UK PII            | UK Passport               | Format            |   |
|  | UK PII            | UK NHS Number             | Modulo 11         |   |
|  |-------------------|---------------------------|-------------------|   |
|  | Canada PII        | Canada SIN                | Luhn              |   |
|  | Canada PII        | Canada Driver License     | Per-province      |   |
|  |-------------------|---------------------------|-------------------|   |
|  | Europe PII        | France INSEE/NIR          | Modulo 97         |   |
|  | Europe PII        | Germany Personal ID       | Check digit       |   |
|  | Europe PII        | Germany Steuer-IdNr       | ISO 7064          |   |
|  | Europe PII        | Italy Codice Fiscale      | Check character   |   |
|  | Europe PII        | Spain DNI/NIE             | Check letter      |   |
|  | Europe PII        | Netherlands BSN           | Eleven-test       |   |
|  | Europe PII        | Sweden Personal Number    | Luhn variant      |   |
|  | Europe PII        | Poland PESEL              | Modulo 10         |   |
|  |-------------------|---------------------------|-------------------|   |
|  | Asia-Pacific PII  | Japan My Number           | Modulo 11         |   |
|  | Asia-Pacific PII  | South Korea RRN           | Gender + checksum |   |
|  | Asia-Pacific PII  | India Aadhaar             | Verhoeff          |   |
|  | Asia-Pacific PII  | India PAN                 | Check character   |   |
|  | Asia-Pacific PII  | China Resident ID         | ISO 7064          |   |
|  | Asia-Pacific PII  | Australia TFN             | Weighted checksum |   |
|  | Asia-Pacific PII  | Singapore NRIC            | Checksum          |   |
|  |-------------------|---------------------------|-------------------|   |
|  | Americas PII      | Brazil CPF                | Modulo 11 (x2)   |   |
|  | Americas PII      | Brazil CNPJ               | Modulo 11 (x2)   |   |
|  | Americas PII      | Mexico CURP               | Check digit       |   |
|  |-------------------|---------------------------|-------------------|   |
|  | Financial         | IBAN                      | ISO 13616 mod-97  |   |
|  | Financial         | SWIFT/BIC Code            | Bank+country code |   |
|  | Financial         | US ABA Routing Number     | 3-7-1 checksum    |   |
|  | Financial         | CUSIP                     | Check digit       |   |
|  | Financial         | ISIN                      | Luhn variant      |   |
|  |-------------------|---------------------------|-------------------|   |
|  | Healthcare        | ICD-9/ICD-10 Code         | Code range        |   |
|  | Healthcare        | NDC (Nat'l Drug Code)     | Segment format    |   |
|  | Healthcare        | DEA Number                | Check digit       |   |
|  | Healthcare        | NPI                       | Luhn (prefixed)   |   |
|  | Healthcare        | HICN/MBI                  | Prefix format     |   |
|  |-------------------|---------------------------|-------------------|   |
|  | Custom            | (user-defined)            | (user-defined)    |   |
|  +------------------------------------------------------------------+   |
|                                                                          |
+=========================================================================+
```

### Identifier Configuration by Regulation

#### PCI DSS Compliance

| Regulation Requirement | Data Identifier(s) | Breadth | Threshold | Severity | Evidence |
|-----------------------|--------------------|---------|-----------|---------|---------|
| Detect primary account numbers (PAN) | Credit Card Number | Medium | 1 | High | A [S1, S4] |
| Detect by card brand (Visa, MC, Amex) | Brand-specific identifiers | Medium | 1 | High | A [S1] |
| Detect bulk cardholder data | Credit Card Number | Medium | 10 (unique) | High | A [S1, S4] |
| Detect magnetic stripe data | Custom regex (Track 1/2 format) | -- | 1 | High | B [S8] |

**PCI Best Practice:** Use the generic "Credit Card Number" identifier rather than brand-specific identifiers unless you need to differentiate actions by card brand. The generic identifier detects all brands with Luhn validation. [S1, S4]

#### HIPAA/PHI Compliance

| PHI Category | Data Identifier(s) | Additional Detection | Severity | Evidence |
|-------------|--------------------|--------------------|---------|----------|
| Patient names | EDM (patient records) | N/A (names are not pattern-matchable) | High | A [S1, S4] |
| Geographic data (zip, address) | N/A | EDM corroborative field | Medium | A [S1] |
| Dates (DOB, admission, discharge) | N/A | EDM corroborative field | Medium | A [S1] |
| Phone/fax numbers | Custom regex | N/A | Low | B [S8] |
| Email addresses | Custom regex | N/A | Low | B [S8] |
| SSN | US SSN | Narrow breadth | High | A [S1, S4] |
| Medical record numbers | Custom regex (organization-specific) | EDM KEY field | High | A [S1] |
| Health plan beneficiary | HICN/MBI | N/A | High | B [S4] |
| Account numbers | EDM KEY field | N/A | High | A [S1] |
| Certificate/license | DEA, NPI | N/A | Medium | B [S4] |
| Device identifiers | Custom regex | N/A | Medium | B [S8] |
| Biometric identifiers | N/A | Custom detection (specialized) | High | E [inferred] |

**HIPAA Best Practice:** HIPAA defines 18 PHI identifier categories. No single detection technology covers all 18. Use a combination of EDM (for structured patient data), data identifiers (for standard formats like SSN, DEA, NPI), VML (for clinical notes), and keywords/dictionaries (for medical terminology). [S1, S4, S7]

#### GDPR Compliance

| GDPR Data Category | Data Identifier(s) | Countries Covered | Severity | Evidence |
|-------------------|--------------------|-----------------|---------|---------|
| National ID numbers | Per-country identifiers (NINO, INSEE, BSN, PESEL, etc.) | UK, FR, DE, NL, SE, PL, IT, ES, and more | High | A [S1, S4] |
| Passport numbers | Per-country passport identifiers | Multi-country | High | B [S4] |
| Financial identifiers | IBAN, SWIFT/BIC | 70+ countries | High | A [S1] |
| Health data | ICD codes, NDC, DEA, NPI | Primarily US; combine with custom for EU | High | B [S4] |
| Biometric/genetic data | Custom detection required | N/A | High | E [inferred] |

---

## Component 2: Custom Dictionaries

### What Custom Dictionaries Are

Custom dictionaries are organization-specific word and phrase lists used for keyword-based detection. Unlike individual keyword rules (which define keywords inline within a rule), dictionaries are reusable, maintainable collections that can be shared across multiple rules and policies. [S1, S8]

**Navigation:** Policy editor > Add Rule > Content Matches Keyword (dictionary can be imported as keyword source)

### Dictionary Creation Workflow

#### Step 1: Dictionary Design

Determine the purpose, scope, and maintenance cadence for the dictionary.

```
+=========================================================================+
|  Dictionary Planning Checklist                                           |
+=========================================================================+
|                                                                          |
|  Dictionary Name: [Medical Drug Names                        ]           |
|                                                                          |
|  Purpose: [Detect medical drug names indicating patient records]         |
|                                                                          |
|  Entry count (estimated): [2,800         ]                               |
|                                                                          |
|  Source of entries:                                                       |
|    [x] Industry standard list (FDA drug database, WHO INN list)          |
|    [ ] Organization-specific terms                                       |
|    [ ] Regulatory compliance requirement                                 |
|                                                                          |
|  Maintenance cadence:                                                    |
|    ( ) One-time (static list)                                            |
|    (*) Quarterly (add new drug approvals)                                |
|    ( ) Annually                                                          |
|                                                                          |
|  Matching options:                                                       |
|    [x] Case insensitive                                                  |
|    [x] Whole words only                                                  |
|    [ ] Stemming enabled                                                  |
|                                                                          |
|  Threshold: [3   ] words from dictionary must appear to trigger          |
|                                                                          |
+=========================================================================+
```

#### Step 2: Prepare Dictionary File

```
+=========================================================================+
|  Dictionary File Format                                                  |
+=========================================================================+
|                                                                          |
|  Format: CSV or plain text (one entry per line)                          |
|                                                                          |
|  CSV format (with optional weight column):                               |
|  +--------------------------------------+                                |
|  | term,weight                          |                                |
|  | metformin,1                          |                                |
|  | atorvastatin,1                       |                                |
|  | oxycodone,2    (higher weight =      |                                |
|  |                 more contribution     |                                |
|  |                 to threshold)         |                                |
|  | fentanyl,3     (controlled substance |                                |
|  |                 = highest weight)     |                                |
|  | acetaminophen,1                      |                                |
|  +--------------------------------------+                                |
|                                                                          |
|  Plain text format (equal weight):                                       |
|  +--------------------------------------+                                |
|  | metformin                            |                                |
|  | atorvastatin                         |                                |
|  | oxycodone                            |                                |
|  | fentanyl                             |                                |
|  | acetaminophen                        |                                |
|  +--------------------------------------+                                |
|                                                                          |
|  Character encoding: UTF-8 recommended                                   |
|  Maximum entries: 100,000 per dictionary (practical limit)               |
|                                                                          |
+=========================================================================+
```

#### Step 3: Import and Configure

**Navigation:** Policy editor > Add Rule > Content Matches Keyword > Import keywords from file

```
+=========================================================================+
|  Keyword Rule with Dictionary Import                                     |
+=========================================================================+
|                                                                          |
|  Rule Type: Content Matches Keyword                                      |
|                                                                          |
|  Keywords Source:                                                         |
|    (*) Import from file                                                  |
|    ( ) Enter manually                                                    |
|                                                                          |
|  File: [medical_drug_names.csv           ] [Browse...]  [Import]         |
|                                                                          |
|  Import Results:                                                         |
|    Entries loaded: 2,847                                                 |
|    Duplicates removed: 12                                                |
|    Invalid entries skipped: 3                                            |
|    Final count: 2,832                                                    |
|                                                                          |
|  Matching Options:                                                       |
|    [x] Case insensitive                                                  |
|    [x] Match whole words only                                            |
|    [ ] Match on word forms (stemming)                                    |
|                                                                          |
|  Threshold: [3   ] dictionary entries must match to trigger              |
|                                                                          |
|  Minimum Total Weight: [3   ] (sum of matched entry weights >= 3)        |
|                                                                          |
|  Look In:                                                                |
|    [x] Message Body     [x] Attachments                                  |
|    [x] Message Subject   [ ] Envelope                                    |
|                                                                          |
|  Severity: (*) 2 - Medium                                                |
|                                                                          |
|                                               [Cancel]  [Save Rule]      |
+=========================================================================+
```

### Dictionary Field Reference

| Field | Type | Required | Default | Options | Evidence |
|-------|------|----------|---------|---------|----------|
| Keywords Source | Radio | Yes | Enter manually | Import from file, Enter manually | A [S1, S8] |
| Import File | File upload | If importing | -- | CSV or plain text | A [S1, S8] |
| Case Sensitive | Checkbox | No | Unchecked (case insensitive) | -- | A [S1, S8] |
| Whole Words Only | Checkbox | No | Unchecked | -- | A [S1, S8] |
| Stemming | Checkbox | No | Unchecked | Match word forms (report/reports/reporting) | B [S8] |
| Threshold | Integer | Yes | 1 | 1-999 (entries that must match) | A [S1, S8] |
| Weight | Integer per entry | No | 1 | 1-10 (contribution to threshold score) | B [S8] |
| Minimum Total Weight | Integer | No | Same as threshold | Sum of matched weights must reach this value | B [S8] |
| Look In | Checkboxes | Yes | Body + Attachments | Body, Subject, Attachments, Envelope | A [S1, S4] |
| Severity | Radio | Yes | 2 - Medium | 1-4 | A [S1, S4] |

**API Coverage:** GAP -- Dictionary/keyword rule creation is console-only for on-prem Enforce. CloudSOC API allows profile creation with embedded data identifiers and rules. [API-intelligence]

### Dictionary Worked Examples

**Example 1: Medical Drug Names (HIPAA)**

| Aspect | Detail |
|--------|--------|
| Dictionary | 2,800 FDA-approved drug names (generic + brand) |
| Threshold | 3 (document must contain 3+ drug names) |
| Weighting | Controlled substances: weight 3; Prescription-only: weight 2; OTC: weight 1 |
| Case Sensitive | No |
| Whole Words | Yes (prevent matching "in" within "insulin") |
| **WHY** | A document with 3+ drug names is likely a prescription, formulary, or patient medication list. Single drug mentions are common in general communication. |
| **GOTCHA** | Pharmaceutical companies will have massive false positives because drug names are their daily vocabulary. Add sender exceptions for R&D and regulatory affairs departments. |

**Example 2: Legal Terminology (Attorney-Client Privilege)**

| Aspect | Detail |
|--------|--------|
| Dictionary | 1,500 legal terms: "privileged", "attorney-client", "work product", "litigation hold", "settlement", "deposition" |
| Threshold | 5 (requires dense legal language) |
| Weighting | Privilege markers ("attorney-client", "work product"): weight 5; General legal terms: weight 1 |
| Case Sensitive | No |
| Whole Words | Yes |
| **WHY** | Documents dense with legal terminology are likely privileged communications. A threshold of 5 ensures only substantive legal documents trigger, not casual mentions of "legal" or "contract." |
| **GOTCHA** | Legal department staff routinely use these terms. Combine with sender/recipient conditions to focus on external communications, not internal legal team email. |

**Example 3: Financial Jargon (Insider Trading Prevention)**

| Aspect | Detail |
|--------|--------|
| Dictionary | 900 terms: "earnings per share", "EBITDA", "revenue guidance", "material non-public", "quiet period", "blackout window", "analyst consensus" |
| Threshold | 4 |
| Weighting | SEC-specific terms ("material non-public", "insider"): weight 4; Financial metrics ("EBITDA", "EPS"): weight 1 |
| Case Sensitive | No |
| Whole Words | Yes |
| **WHY** | Dense financial language combined with SEC-restricted terms indicates potential insider information. Weighted scoring ensures SEC-specific terms count heavily. |
| **GOTCHA** | Finance and investor relations teams use these terms constantly. Create exceptions for authorized roles. Focus detection on email to external recipients (personal email domains, competitors). |

**Example 4: Project Code Names (M&A / Strategic Initiatives)**

| Aspect | Detail |
|--------|--------|
| Dictionary | 50 terms: "Project Falcon", "Operation Stargate", "Athena Initiative", "Target Alpha", "Blue Horizon" |
| Threshold | 1 (any single code name is significant) |
| Weighting | All equal (weight 1) |
| Case Sensitive | Yes (code names are capitalized by convention) |
| Whole Words | Yes |
| **WHY** | Project code names are assigned specifically to be confidential. Any mention outside authorized channels is a potential leak. |
| **GOTCHA** | Code names should be unique and unlikely to appear in normal conversation. Avoid generic names ("Project Blue", "Phase 2") that generate false positives. Choose distinctive, memorable code names. |

**Example 5: Competitor Intelligence (Trade Secret Protection)**

| Aspect | Detail |
|--------|--------|
| Dictionary | 200 terms: competitor company names, product names, executive names, patent numbers |
| Threshold | 3 |
| Weighting | Competitor executive names: weight 3; Product names: weight 2; Company names: weight 1 |
| Case Sensitive | No |
| Whole Words | Yes |
| **WHY** | Documents referencing multiple competitors by name may contain competitive intelligence, market analysis, or trade secrets about competitive strategy. |
| **GOTCHA** | Sales teams legitimately discuss competitors. Marketing monitors competitor press releases. Set severity to Low/Informational for monitoring, not blocking. Use this for awareness, not enforcement. |

**Example 6: Profanity/Harassment Detection (HR Policy)**

| Aspect | Detail |
|--------|--------|
| Dictionary | 500 terms: profanity, slurs, harassment language, threatening phrases |
| Threshold | 1 (zero tolerance) |
| Weighting | Threatening language: weight 5; Slurs: weight 4; Profanity: weight 1 |
| Case Sensitive | No |
| Whole Words | Yes |
| **WHY** | HR acceptable use policy enforcement. Immediate detection of harassment or threatening language in corporate communications. |
| **GOTCHA** | This dictionary WILL generate false positives from quoted text (forwarded external emails, news articles, book passages). Add exceptions for automated email systems (news aggregators, social media monitors). Review every incident before escalation. |

**Example 7: Executive Names (VIP Protection)**

| Aspect | Detail |
|--------|--------|
| Dictionary | 50 terms: C-suite names, board member names, key executive names |
| Threshold | 2 (combined with financial/strategic keywords) |
| Case Sensitive | No |
| Whole Words | Yes |
| **WHY** | Documents mentioning executive names in combination with strategic keywords may indicate unauthorized disclosure of executive communications or strategy discussions. |
| **GOTCHA** | Executive names appear in email signatures, org charts, press releases, and public filings. ALWAYS combine this dictionary with other conditions (financial dictionary, project codes, or specific recipient patterns) in compound rules. Never use standalone. |

---

## Component 3: Classification Policies

### What Classification Policies Are

Classification policies combine multiple data identifiers, dictionaries, and detection technologies into hierarchical classification schemes. Instead of individual detection rules firing independently, classification policies create a unified classification determination (e.g., "Confidential", "Highly Confidential", "Public") based on the aggregate of matches across multiple detection methods. [S1, S4]

### Compound Classification Logic

```
+=========================================================================+
|  Classification Policy Design                                            |
+=========================================================================+
|                                                                          |
|  Policy: PCI Cardholder Data Classification                              |
|                                                                          |
|  Classification Tier 1: "Highly Confidential"                            |
|    Trigger: Credit Card Number (>= 10 unique matches)                    |
|        AND: File Type is Spreadsheet (XLS, XLSX, CSV)                    |
|    Action: Block + Notify + Encrypt                                      |
|    Severity: 1 - High                                                    |
|                                                                          |
|  Classification Tier 2: "Confidential"                                   |
|    Trigger: Credit Card Number (>= 1 unique match)                       |
|        AND: Financial dictionary (>= 2 terms)                            |
|    Action: Notify + Log to Syslog                                        |
|    Severity: 2 - Medium                                                  |
|                                                                          |
|  Classification Tier 3: "Internal Only"                                  |
|    Trigger: Financial dictionary (>= 5 terms)                            |
|        AND NOT: Recipient domain is company.com                          |
|    Action: Log to Syslog (monitoring only)                               |
|    Severity: 4 - Informational                                           |
|                                                                          |
|  Evaluation Order: Tier 1 first, then Tier 2, then Tier 3               |
|  Highest matching tier determines classification                         |
|                                                                          |
+=========================================================================+
```

### Compound Condition Configuration

```
+=========================================================================+
|  Detection Rule — Compound Conditions                                    |
+=========================================================================+
|                                                                          |
|  Rule Name: [Highly Confidential Financial Data              ]           |
|                                                                          |
|  Conditions (ALL must match):                                            |
|  +------------------------------------------------------------------+   |
|  | # | Condition Type                  | Configuration              |   |
|  |---|-------------------------------|----------------------------|   |
|  | 1 | Content Matches Data Identifier | Credit Card Number >= 10   |   |
|  |   |                                 | Breadth: Medium            |   |
|  |   |                                 | Count: Unique              |   |
|  |---|-------------------------------|----------------------------|   |
|  | 2 | Content Matches Keyword         | Financial dictionary       |   |
|  |   |                                 | Threshold: 2 terms         |   |
|  |---|-------------------------------|----------------------------|   |
|  | 3 | File Property Matches           | Type: Spreadsheet          |   |
|  |   |                                 | (XLS, XLSX, CSV)           |   |
|  +------------------------------------------------------------------+   |
|                                                                          |
|  Logic: ALL conditions must match (AND logic)                            |
|  NOTE: Compound rules support AND only. For OR logic, use separate       |
|        simple rules (each triggers independently).                       |
|                                                                          |
|  Severity: (*) 1 - High                                                  |
|                                                                          |
|                                               [Cancel]  [Save Rule]      |
+=========================================================================+
```

### Weighted Scoring Configuration

Symantec DLP supports weighted scoring through threshold configuration and the Minimum Total Weight field in keyword/dictionary rules.

| Scoring Method | How It Works | Best For | Evidence |
|---------------|-------------|----------|----------|
| Match Count Threshold | Trigger when N distinct matches occur | Bulk data exposure (10+ CC numbers) | A [S1, S4] |
| Dictionary Weight Threshold | Trigger when sum of matched entry weights >= N | Weighted term importance (slurs > profanity) | B [S8] |
| Multi-Rule Severity Escalation | Multiple rules at different severities; highest wins | Tiered classification (any CC = Medium, 10+ CC = High) | A [S1, S4] |
| Compound Conditions | ALL conditions must match (AND) | Cross-technology correlation (CC + spreadsheet + external recipient) | A [S1, S4] |

### Classification Policy Worked Examples

**Example 1: Multi-Tier PII Classification**

```
Policy: Employee PII Classification

Tier: "Restricted" (Severity 1 - High)
  Rule: EDM match on Employee Records (2 of 6 fields, 1 KEY)
  AND: Data Identifier: US SSN >= 1
  Action: Block + Encrypt + Notify + Syslog

Tier: "Confidential" (Severity 2 - Medium)
  Rule: EDM match on Employee Records (2 of 6 fields, 1 KEY)
  (no additional conditions)
  Action: Notify + Syslog

Tier: "Internal" (Severity 3 - Low)
  Rule: Data Identifier: US SSN >= 1 (standalone, no EDM correlation)
  Action: Syslog (monitoring)

WHY: EDM + SSN together = confirmed employee data breach (Restricted).
     EDM alone = employee data exposure without SSN (Confidential).
     SSN alone = possible but unconfirmed employee data (Internal).

GOTCHA: This requires the EDM profile to exist and be current. If the EDM
        index is stale, Tier 1 and 2 will not trigger, falling through to
        Tier 3 (SSN-only detection), which provides weaker classification.
```

**Example 2: Healthcare Data Classification (HIPAA)**

```
Policy: HIPAA PHI Classification

Tier: "PHI - Critical" (Severity 1 - High)
  Rule: EDM match on Patient Records (3 of 7 fields, 1 KEY)
  AND: Medical dictionary (>= 3 terms)
  Action: Block + Quarantine + Notify + Syslog

Tier: "PHI - Standard" (Severity 2 - Medium)
  Rule: EDM match on Patient Records (2 of 7 fields, 1 KEY)
  Action: Notify + Syslog

Tier: "Possible PHI" (Severity 3 - Low)
  Rule: Medical dictionary (>= 5 terms)
  AND: Data Identifier: US SSN >= 1
  Action: Syslog (monitoring for false positive triage)

WHY: EDM + medical terms = confirmed patient data with clinical context.
     EDM alone = patient record exposure.
     Medical terms + SSN = possible PHI without confirmed patient linkage.
```

**Example 3: Intellectual Property Classification**

```
Policy: Source Code & IP Classification

Tier: "Trade Secret" (Severity 1 - High)
  Rule: IDM partial match (>= 15% of core IP documents)
  AND: Project code name dictionary (>= 1 match)
  Action: Block + Notify + Syslog

Tier: "Confidential IP" (Severity 2 - Medium)
  Rule: VML match (Engineering Docs profile, >= 85% confidence)
  Action: Notify + Syslog

Tier: "Sensitive Technical" (Severity 3 - Low)
  Rule: File Property: CAD types (DWG, DXF, SLDPRT, STEP)
  Action: Syslog (monitoring)

WHY: IDM + project code name = confirmed leak of specific protected IP.
     VML match = document classified as engineering type (may be new IP).
     CAD file type = engineering file leaving the network (low confidence).
```

---

## Component 4: Sensitivity Labels (Microsoft Information Protection)

### What MIP Integration Does

Symantec DLP integrates with Microsoft Information Protection (MIP, formerly Azure Information Protection / AIP) to both READ sensitivity labels on documents and WRITE/APPLY sensitivity labels as a response action. This enables bidirectional classification between the MIP ecosystem and Symantec DLP's detection engine. [S1, S2, S3]

**Navigation:** Policy > Rules > Content Matches MIP Tag Rule (for reading labels); Response Rules > Apply Classification Label (for writing labels)

### MIP Integration Architecture

```
+------------------------------------------------------------------+
|  MIP + DLP Integration Flow                                       |
+------------------------------------------------------------------+
|                                                                    |
|  READING LABELS (detection direction):                             |
|                                                                    |
|  Document with MIP label --> Symantec DLP inspects -->             |
|    Policy condition: "Content Matches MIP Tag Rule"                |
|    --> If label = "Highly Confidential" AND recipient external     |
|    --> Trigger: Block + Notify                                     |
|                                                                    |
|  WRITING LABELS (response direction):                              |
|                                                                    |
|  Document without label --> Symantec DLP detects sensitive data    |
|    --> Response rule: "Apply Classification Label"                 |
|    --> MIP label "Confidential" applied to document                |
|    --> Label persists in Office/PDF/email (cross-platform)         |
|    --> Azure RMS encryption applied (if configured for label)      |
|                                                                    |
+------------------------------------------------------------------+
```

### MIP Configuration

```
+=========================================================================+
|  MIP Tag Rule Configuration                                              |
+=========================================================================+
|                                                                          |
|  Rule Type: Content Matches MIP Tag Rule                                 |
|                                                                          |
|  Label Selection:                                                        |
|    [ ] Any MIP label present                                             |
|    [x] Specific label(s):                                                |
|        [x] Highly Confidential                                           |
|        [x] Confidential                                                  |
|        [ ] Internal                                                      |
|        [ ] Public                                                        |
|        [x] Custom: [Restricted - Finance          ]                      |
|                                                                          |
|  Label Source:                                                           |
|    [x] Document label (embedded in file)                                 |
|    [x] Email label (message header)                                      |
|    [ ] Container label (folder/site label)                               |
|                                                                          |
|  Severity: (*) 1 - High  (match label = high severity)                   |
|                                                                          |
+=========================================================================+
```

### MIP Field Reference

| Field | Type | Required | Default | Options | Evidence |
|-------|------|----------|---------|---------|----------|
| Label Selection | Checkboxes | Yes | None | Any label, or specific label names from MIP tenant | A [S1, S2] |
| Custom Label Name | Text | No | -- | Matches custom MIP labels defined in your tenant | A [S2] |
| Label Source | Checkboxes | Yes | Document + Email | Document, Email, Container | A [S2] |
| Severity | Radio | Yes | 2 - Medium | 1-4 | A [S1, S4] |

### MIP Response Action — Apply Classification Label

```
+=========================================================================+
|  Response Rule: Apply Classification Label                               |
+=========================================================================+
|                                                                          |
|  Action Type: Apply Classification Label                                 |
|                                                                          |
|  Label to Apply:                                                         |
|    [Confidential - Internal Only          ] [v]                          |
|                                                                          |
|  Label Scope:                                                            |
|    [x] Apply to document attachments                                     |
|    [x] Apply to email message                                            |
|                                                                          |
|  Overwrite Existing Label:                                               |
|    ( ) Never (keep existing label)                                       |
|    (*) Upgrade only (apply if higher than existing)                      |
|    ( ) Always (replace any existing label)                               |
|                                                                          |
|  Apply RMS Encryption:                                                   |
|    [x] Apply RMS protection based on label settings                      |
|                                                                          |
|  Conditions (when to apply this action):                                 |
|    [x] Severity: 1 - High or 2 - Medium                                 |
|    [ ] Protocol: (any)                                                   |
|    [ ] Detection server type: (any)                                      |
|                                                                          |
+=========================================================================+
```

### MIP Worked Examples

**Example 1: Block External Sharing of Highly Confidential Documents**

| Aspect | Detail |
|--------|--------|
| Detection | Content Matches MIP Tag: "Highly Confidential" |
| Condition | Recipient is external (not @company.com) |
| Action | Block + Notify sender |
| **WHY** | Documents already labeled as Highly Confidential by the originator should never leave the organization. MIP label detection reinforces the originator's intent. |
| **GOTCHA** | MIP labels can be downgraded by users (depending on MIP policy). If a user downgrades "Highly Confidential" to "Internal" before sending, this rule will not trigger. Enable MIP justification requirements to prevent unauthorized downgrades. |

**Example 2: Auto-Label PCI Data**

| Aspect | Detail |
|--------|--------|
| Detection | Credit Card Number data identifier >= 1 match |
| Action | Apply Classification Label: "Confidential - PCI" |
| Overwrite | Upgrade only (if no label or lower label exists) |
| RMS Encryption | Enabled |
| **WHY** | Automatically classifies unlabeled documents containing credit card data. Ensures PCI data is always labeled and encrypted via RMS, even if the document originator forgot to label it. |
| **GOTCHA** | Auto-labeling may surprise document owners who did not expect their file to be modified. Communicate the auto-labeling policy to all users. Consider starting with "Apply label to copy only" if available. |

**Example 3: Read MIP Label for Network Discover Classification**

| Aspect | Detail |
|--------|--------|
| Detection | Network Discover scan + Content Matches MIP Tag: any label |
| Action | Set Attribute: "MIP Classification = [label name]" |
| **WHY** | During data-at-rest scanning, capture MIP labels from files on file shares. Enables reporting on classification coverage (how many files are labeled vs. unlabeled). |
| **GOTCHA** | High Speed Discovery (DLP 16.1+) supports MIP label detection and application. For large file share scans, ensure High Speed Discovery is enabled. |

---

## Cross-Component Integration

### How All Four Components Work Together

```
+=========================================================================+
|  COMPLETE CLASSIFICATION WORKFLOW                                        |
+=========================================================================+
|                                                                          |
|  1. Content arrives for inspection (email, web upload, USB copy)         |
|     |                                                                    |
|  2. System-Defined Data Identifiers scan for known patterns             |
|     Result: "3 credit card numbers found", "1 US SSN found"             |
|     |                                                                    |
|  3. Custom Dictionaries scan for organizational terms                   |
|     Result: "5 medical terms found", "2 project code names found"       |
|     |                                                                    |
|  4. Classification Policy evaluates compound conditions                 |
|     Input: identifier matches + dictionary matches + EDM/IDM/VML        |
|     Logic: 3 CC + financial terms + spreadsheet = "Highly Confidential"  |
|     |                                                                    |
|  5. MIP Labels checked (if present on document)                         |
|     Result: document already labeled "Confidential"                     |
|     Policy: upgrade label to "Highly Confidential" based on content     |
|     |                                                                    |
|  6. Severity assigned based on highest matching classification tier      |
|     |                                                                    |
|  7. Response rules execute based on severity and classification          |
|                                                                          |
+=========================================================================+
```

---

## API Coverage for Classifications

| Operation | On-Prem Enforce API | CloudSOC API | Evidence |
|-----------|-------------------|-------------|---------|
| List data identifiers | GAP | FULL (`GET /api/clouddlp/protect/public/dataIdentifiers`) | A [API-intelligence] |
| Create dictionary/keyword rule | GAP | PARTIAL (within profile creation) | A [API-intelligence] |
| Create classification policy | GAP | PARTIAL (profile-based) | A [API-intelligence] |
| Create MIP tag rule | GAP | GAP | A [API-intelligence] |
| Apply MIP label (response) | GAP (response rule is console-only) | GAP | A [API-intelligence] |
| Export classification (in policy XML) | FULL (25.1+) | N/A | A [API-intelligence] |
| Import classification (in policy XML) | FULL (25.1+) | N/A | A [API-intelligence] |

---

*End of classifications and dictionaries workflow document. 4 components documented with configuration screens, field references, and 20+ worked examples across PCI, HIPAA, GDPR, IP protection, and MIP integration.*
