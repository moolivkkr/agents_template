# Data Definitions — Complete Workflow
## Broadcom Symantec DLP (Enforce Server, version 16.x/25.x/26.x)

> **Capability:** Data Definitions (Data Identifiers, Custom Data Profiles, EDM, IDM, VML, Form Recognition, File Properties)
> **Complexity Score:** COMPLEX
> **Evidence sources:** doc-corpus.md [S1-S28], video-intelligence.md [V1-V45], api-intelligence.md [API surfaces 1-6]

---

## Overview

Data definitions in Broadcom Symantec DLP answer the foundational question: **"What sensitive data are we protecting?"** Before any detection rule, exception, response rule, or policy can be created, the data to be protected must be defined using one or more of Symantec's seven detection technology families.

This capability sits at Layer 1 of the Symantec DLP authoring hierarchy. Everything above it -- rules, exceptions, responses, policies, deployment -- references data definitions. If the data definition is wrong, everything built on top of it is wrong.

**The seven data definition technologies:**

| # | Technology | Type | Pre-Setup | Best For | Evidence |
|---|-----------|------|-----------|----------|----------|
| 1 | Data Identifiers (built-in) | Pattern + validator | None | Credit cards, SSNs, IBANs, passports | A [S1, S4, S8] |
| 2 | Custom Data Profiles | Regex + keywords + proximity | None | Organization-specific patterns, project codes | A [S1, S8] |
| 3 | Exact Data Matching (EDM) | Structured data fingerprint | Index required | Employee PII, customer records, account numbers | A [S1, S4, V19] |
| 4 | Indexed Document Matching (IDM) | Document fingerprint | Index required | Confidential documents, source code, legal contracts | A [S1, S4, V22] |
| 5 | Vector Machine Learning (VML) | Statistical ML classifier | Training required | Financial reports, IP documents, medical records | A [S1, S7, V20] |
| 6 | Form Recognition | Template image matching | Template upload required | Tax forms (W-2, 1099), medical intake, insurance claims | A [S1, V21] |
| 7 | File Properties | Metadata match | None | File type, size, name patterns, custom properties | A [S1, S4] |

**How Symantec differs from competitors on data definitions:**

| Aspect | Symantec DLP | Trellix DLP | Microsoft Purview |
|--------|-------------|-------------|-------------------|
| Built-in identifiers | 30+ with validation algorithms | ~100+ classification rules | 300+ Sensitive Information Types (SITs) |
| Custom structured data | EDM (hash-based fingerprint) | Fingerprinting (limited) | EDM (token-based) |
| Document fingerprinting | IDM (rolling hash, partial match) | Document Registration (full match) | No equivalent |
| ML classification | VML (statistical, self-trained) | N/A (rule-based only) | Trainable classifiers (Azure ML) |
| Form detection | Form Recognition (image template) | N/A | N/A |
| File type detection | 330+ types by binary signature | 300+ types | Built into Microsoft ecosystem |

[S1, S4, S7, S8, V19, V20, V21, V22]

---

## Complexity Score: COMPLEX

**Justification:**

1. **Seven distinct technologies** -- each with different data preparation, configuration, and maintenance requirements
2. **EDM lifecycle management** -- data source preparation, column mapping, indexing, scheduling, staleness monitoring
3. **IDM partial matching** -- configurable thresholds, binary vs text matching, endpoint opt-in requirements
4. **VML training pipeline** -- positive/negative set preparation, training, accuracy evaluation, retraining cadence
5. **Cross-technology composition** -- a single detection rule can combine multiple data definition technologies
6. **API gaps** -- EDM/IDM/VML profile creation is console-only; only EDM index triggering has an API endpoint
7. **Index/model maintenance** -- EDM indexes, IDM fingerprints, and VML models all require periodic refresh or retraining

---

## Technology 1: Data Identifiers (Built-In)

### What Data Identifiers Do

Data identifiers are pre-built detection patterns that combine regular expression matching with algorithmic validation to detect common sensitive data types with high accuracy and low false positive rates. Unlike raw regex patterns, data identifiers include checksums (Luhn for credit cards), format validators (area number ranges for SSNs), and normalization logic (strip dashes, spaces) that dramatically reduce false positives. [S1, S4, S8]

**Navigation:** Manage > Policies > Policy List > [policy] > Detection > Add Rule > Content Matches Data Identifier

### Configuration Screen

```
+=========================================================================+
|  Add Detection Rule                                                      |
+=========================================================================+
|  Rule Type: [Content Matches Data Identifier]                            |
|                                                                          |
|  Data Identifier:  [Credit Card Number         ] [v]                     |
|                                                                          |
|  Minimum Matches:  [1         ]                                          |
|  Match Counting:   (*) Count unique values only                          |
|                    ( ) Count all matches                                  |
|                                                                          |
|  Check for Existence Only: [ ]                                           |
|                                                                          |
|  Breadth:  ( ) Narrow  (strict format, fewest false positives)           |
|            (*) Medium  (moderate flexibility)                             |
|            ( ) Wide    (catch-all, most false positives)                  |
|                                                                          |
|  Look In:                                                                |
|    [x] Message Body                                                      |
|    [x] Message Subject                                                   |
|    [x] Attachments                                                       |
|    [ ] Envelope (sender/recipient headers)                               |
|                                                                          |
|  Severity:  ( ) 1 - High   (*) 2 - Medium   ( ) 3 - Low   ( ) 4 - Info |
|                                                                          |
|                                               [Cancel]  [Save Rule]      |
+=========================================================================+
```

### Field Reference

| Field | Type | Required | Default | Options | Evidence |
|-------|------|----------|---------|---------|----------|
| Data Identifier | Dropdown | Yes | -- | 30+ built-in (see catalog below) + custom | A [S1, S4] |
| Minimum Matches | Integer | Yes | 1 | 1-999 | A [S1, S4] |
| Match Counting | Radio | Yes | Unique | Unique (count distinct values), All (count every match) | A [S4] |
| Check for Existence | Checkbox | No | Unchecked | Checked = trigger on any match regardless of count | B [S8] |
| Breadth | Radio | No | Medium | Narrow, Medium, Wide (controls pattern strictness) | A [S1, S8] |
| Look In | Checkboxes | Yes | Body + Attachments | Body, Subject, Attachments, Envelope | A [S1, S4] |
| Severity | Radio | Yes | 2 - Medium | 1-High, 2-Medium, 3-Low, 4-Informational | A [S1, S4] |

**API Coverage:** GAP -- Data identifier configuration within detection rules is console-only. CloudSOC API (`GET /api/clouddlp/protect/public/dataIdentifiers`) can list available identifiers but not create/edit rules referencing them in on-prem Enforce. [API-intelligence]

### Built-In Data Identifier Catalog

#### Payment Card Industry (PCI)

| Identifier | Pattern | Validator | Breadth Modes | Evidence |
|-----------|---------|-----------|---------------|----------|
| Credit Card Number | 13-19 digit sequences | Luhn algorithm (mod-10 checksum) | Narrow: with dashes/spaces; Medium: flexible separators; Wide: any digit sequence | A [S1, S4, S8] |
| Visa Card | Starts with 4, 13 or 16 digits | Luhn | Narrow/Medium/Wide | A [S1] |
| Mastercard | Starts with 51-55 or 2221-2720 | Luhn | Narrow/Medium/Wide | A [S1] |
| American Express | Starts with 34 or 37, 15 digits | Luhn | Narrow/Medium/Wide | A [S1] |
| Discover Card | Starts with 6011/644-649/65, 16 digits | Luhn | Narrow/Medium/Wide | A [S1] |
| JCB Card | Starts with 3528-3589, 15-16 digits | Luhn | Narrow/Medium/Wide | B [S4] |
| UnionPay Card | Starts with 62, 16-19 digits | Luhn | Narrow/Medium/Wide | B [S4] |
| Diners Club | Starts with 300-305/36/38, 14 digits | Luhn | Narrow/Medium/Wide | B [S4] |

#### Personally Identifiable Information (PII) -- United States

| Identifier | Pattern | Validator | Notes | Evidence |
|-----------|---------|-----------|-------|----------|
| US Social Security Number (SSN) | XXX-XX-XXXX | Area number range validation (001-899, not 666), group/serial non-zero | Narrow: dashed only; Wide: 9 digits no separator | A [S1, S4, S8] |
| US Driver License | State-specific patterns | State format validation (CA: 1 letter + 7 digits, NY: 9 digits, etc.) | Coverage for all 50 states + DC | A [S1, S4] |
| US Passport Number | 9 alphanumeric characters | Format validation | -- | A [S1] |
| US Individual Taxpayer ID (ITIN) | 9XX-XX-XXXX | Starts with 9, 4th digit 7-8 | -- | B [S4] |
| US Employer Identification Number (EIN) | XX-XXXXXXX | Campus prefix validation | -- | B [S4] |

#### PII -- International

| Identifier | Pattern | Region | Validator | Evidence |
|-----------|---------|--------|-----------|----------|
| UK National Insurance Number (NINO) | 2 letters + 6 digits + 1 letter | UK | Prefix validation (not D, F, I, Q, U, V; not BG, GB, NK, KN, TN, NT, ZZ) | A [S1] |
| UK Passport Number | 9 digits | UK | Format validation | B [S4] |
| Canada Social Insurance Number (SIN) | XXX-XXX-XXX | Canada | Luhn algorithm | A [S1] |
| Australia Tax File Number (TFN) | 8-9 digits | Australia | Weighted checksum | B [S4] |
| France INSEE/NIR | 13 digits + 2 check digits | France | Modulo-97 checksum | B [S4] |
| Germany Personal ID (Personalausweisnummer) | 10 alphanumeric | Germany | Check digit algorithm | B [S4] |
| Japan My Number | 12 digits | Japan | Check digit (modulo 11) | B [S4] |
| South Korea RRN | 13 digits (YYMMDD-GXXXXXX) | South Korea | Gender digit + checksum | B [S4] |
| India Aadhaar Number | 12 digits | India | Verhoeff algorithm | B [S4] |
| Brazil CPF | XXX.XXX.XXX-XX | Brazil | 2 check digits (modulo 11) | B [S4] |
| China Resident Identity Card | 18 digits | China | Checksum (ISO 7064) | B [S4] |

#### Financial

| Identifier | Pattern | Validator | Evidence |
|-----------|---------|-----------|----------|
| IBAN (International Bank Account Number) | 2 letter country + 2 check digits + up to 30 alphanumeric | ISO 13616 check digit validation (modulo 97) | A [S1, S4] |
| SWIFT/BIC Code | 8 or 11 alphanumeric | Bank code + country code format | A [S1] |
| US ABA Routing Number | 9 digits | Checksum (3-7-1 weighting) | B [S4] |
| US Bank Account Number | Variable (8-17 digits) | Format only (no universal checksum) | B [S4] |

#### Healthcare / HIPAA

| Identifier | Pattern | Validator | Evidence |
|-----------|---------|-----------|----------|
| ICD-9/ICD-10 Code | ICD-9: XXX.XX; ICD-10: alpha + 2-7 alnum | Format + code range validation | B [S4] |
| NDC (National Drug Code) | 10-11 digits in 3 segments | Segment format validation (4-4-2, 5-3-2, 5-4-1) | B [S4] |
| DEA Number | 2 letters + 7 digits | Check digit algorithm (letters identify registrant type) | B [S4] |
| NPI (National Provider Identifier) | 10 digits starting with 1 or 2 | Luhn algorithm on 15-digit prefixed number | B [S4] |
| HICN (Health Insurance Claim Number) | Alphanumeric (Medicare format) | Prefix validation | B [S4] |

### Worked Examples

**Example 1: Detect Credit Card Numbers in Email (PCI Compliance)**

| Aspect | Detail |
|--------|--------|
| Data Identifier | Credit Card Number |
| Breadth | Narrow (dashed/spaced format only) |
| Minimum Matches | 1 (PCI requires detecting even a single card number) |
| Match Counting | Unique |
| Look In | Body + Subject + Attachments |
| Severity | 1 - High |
| **WHY** | PCI DSS requires detecting any credit card number in transit. Narrow breadth reduces FPs from random number sequences. |
| **GOTCHA** | If users transmit card numbers without separators (4111111111111111), Narrow breadth will miss them. Switch to Medium after initial tuning period. |

**Example 2: Bulk SSN Detection in Spreadsheets**

| Aspect | Detail |
|--------|--------|
| Data Identifier | US Social Security Number |
| Breadth | Medium (catches dashed and undashed formats) |
| Minimum Matches | 10 (target bulk exposure, not individual SSNs) |
| Match Counting | Unique (10 distinct SSNs, not 10 occurrences of the same one) |
| Look In | Attachments only |
| Severity | 1 - High |
| **WHY** | A spreadsheet with 10+ unique SSNs is a database export. Single SSNs in email body are often the sender's own SSN, which is lower risk. |
| **GOTCHA** | "Unique" counting means a spreadsheet with the same SSN repeated 100 times counts as 1. Use "All" counting if you need to detect volume regardless of uniqueness. |

**Example 3: International IBAN Detection for Cross-Border Transfers**

| Aspect | Detail |
|--------|--------|
| Data Identifier | IBAN |
| Breadth | Medium |
| Minimum Matches | 1 |
| Match Counting | All |
| Look In | Body + Attachments |
| Severity | 2 - Medium |
| **WHY** | GDPR and financial regulations require monitoring international bank account numbers in transit. |
| **GOTCHA** | IBAN format varies by country (Germany: DE + 20 digits; UK: GB + 18 alphanumeric). The built-in validator handles per-country formats but check that your target countries are covered. |

**Example 4: Healthcare Provider ID Detection (HIPAA)**

| Aspect | Detail |
|--------|--------|
| Data Identifier | DEA Number |
| Breadth | Narrow |
| Minimum Matches | 1 |
| Match Counting | Unique |
| Look In | Body + Attachments |
| Severity | 2 - Medium |
| **WHY** | DEA numbers identify prescribers. Exposure enables prescription fraud. HIPAA requires protecting healthcare identifiers. |
| **GOTCHA** | DEA numbers are often found in legitimate prescription documents. Add exceptions for pharmacy and healthcare department senders to reduce false positive volume. |

**Example 5: UK National Insurance Number for GDPR**

| Aspect | Detail |
|--------|--------|
| Data Identifier | UK National Insurance Number (NINO) |
| Breadth | Narrow |
| Minimum Matches | 1 |
| Match Counting | Unique |
| Look In | Body + Subject + Attachments |
| Severity | 1 - High |
| **WHY** | NINO is a core UK personal identifier. GDPR Article 9 requires special protection for national identification numbers. |
| **GOTCHA** | NINO format (2 letters + 6 digits + 1 letter) can false-positive on alphanumeric product codes. Narrow breadth helps, but combine with keyword proximity (e.g., "national insurance" or "NI number" within 50 characters) for best accuracy. |

**Example 6: Multi-Identifier Rule for Compound PII Detection**

| Aspect | Detail |
|--------|--------|
| Data Identifiers | US SSN AND Driver License (compound rule: both must match) |
| Breadth | Medium for both |
| Minimum Matches | 1 each |
| Look In | Body + Attachments |
| Severity | 1 - High |
| **WHY** | A document containing both SSN and driver license is an identity theft risk. Requiring both reduces false positives from individual identifier matches. |
| **GOTCHA** | Compound rules use AND logic only. Both conditions must match in the same message. If you want OR (either SSN or DL), create two separate simple rules. |

---

## Technology 2: Custom Data Profiles

### What Custom Data Profiles Do

Custom data profiles allow organizations to define their own detection patterns when the built-in data identifiers do not cover a specific data type. Custom profiles use regular expressions, keyword lists, dictionaries, and proximity rules in combination. [S1, S8]

**Navigation:** Manage > Policies > Policy List > [policy] > Detection > Add Rule > Content Matches Regular Expression / Content Matches Keyword

### Configuration Screen — Regular Expression

```
+=========================================================================+
|  Add Detection Rule                                                      |
+=========================================================================+
|  Rule Type: [Content Matches Regular Expression]                         |
|                                                                          |
|  Match on: (*) Content   ( ) Envelope                                    |
|                                                                          |
|  Regular Expression:                                                     |
|  [PROJ-[A-Z]{2,4}-\d{4,8}                                    ]          |
|                                                                          |
|  Minimum Matches:  [1         ]                                          |
|  Match Counting:   (*) Count unique values only                          |
|                    ( ) Count all matches                                  |
|                                                                          |
|  Look In:                                                                |
|    [x] Message Body     [x] Attachments                                  |
|    [ ] Message Subject   [ ] Envelope                                    |
|                                                                          |
|  Severity:  ( ) 1 - High   (*) 2 - Medium   ( ) 3 - Low   ( ) 4 - Info |
|                                                                          |
|                                               [Cancel]  [Save Rule]      |
+=========================================================================+
```

### Configuration Screen — Keyword Matching

```
+=========================================================================+
|  Add Detection Rule                                                      |
+=========================================================================+
|  Rule Type: [Content Matches Keyword]                                    |
|                                                                          |
|  Match on: (*) Content   ( ) Envelope                                    |
|                                                                          |
|  Enter keywords/phrases (one per line):                                  |
|  +--------------------------------------------------+                    |
|  | Project Orion                                     |                    |
|  | Operation Stargate                                |                    |
|  | Acquisition Target Alpha                          |                    |
|  | Q4 Revenue Forecast CONFIDENTIAL                  |                    |
|  +--------------------------------------------------+                    |
|                                                                          |
|  Keyword Matching:                                                       |
|    [x] Case sensitive                                                    |
|    [x] Match whole words only                                            |
|    [ ] Match on word forms (stemming)                                    |
|                                                                          |
|  Proximity:  [ ] Require keywords within [   ] characters of each other  |
|                                                                          |
|  Minimum Matches:  [1         ]                                          |
|                                                                          |
|  Look In:                                                                |
|    [x] Message Body     [x] Attachments                                  |
|    [x] Message Subject   [ ] Envelope                                    |
|                                                                          |
|  Severity:  ( ) 1 - High   ( ) 2 - Medium   (*) 3 - Low   ( ) 4 - Info |
|                                                                          |
|                                               [Cancel]  [Save Rule]      |
+=========================================================================+
```

### Field Reference — Regular Expression

| Field | Type | Required | Default | Options | Evidence |
|-------|------|----------|---------|---------|----------|
| Regular Expression | Text | Yes | -- | Any valid Java-compatible regex | A [S1, S8] |
| Match on | Radio | Yes | Content | Content, Envelope | A [S1] |
| Minimum Matches | Integer | Yes | 1 | 1-999 | A [S1, S4] |
| Match Counting | Radio | Yes | Unique | Unique, All | A [S4] |
| Look In | Checkboxes | Yes | Body + Attachments | Body, Subject, Attachments, Envelope | A [S1, S4] |
| Severity | Radio | Yes | 2 - Medium | 1-4 | A [S1, S4] |

### Field Reference — Keyword

| Field | Type | Required | Default | Options | Evidence |
|-------|------|----------|---------|---------|----------|
| Keywords | Textarea (one per line) | Yes | -- | Free text, one keyword/phrase per line | A [S1, S8] |
| Case Sensitive | Checkbox | No | Unchecked | -- | A [S1, S8] |
| Whole Words Only | Checkbox | No | Unchecked | -- | A [S1, S8] |
| Word Forms (Stemming) | Checkbox | No | Unchecked | Matches inflections (e.g., "report" matches "reports", "reporting") | B [S8] |
| Proximity | Checkbox + Integer | No | Disabled | Enable + character distance (10-999) | A [S1, S8] |
| Minimum Matches | Integer | Yes | 1 | 1-999 | A [S1, S4] |
| Look In | Checkboxes | Yes | Body + Attachments | Body, Subject, Attachments, Envelope | A [S1, S4] |
| Severity | Radio | Yes | 2 - Medium | 1-4 | A [S1, S4] |

**API Coverage:** GAP -- Custom regex/keyword rule creation is console-only. Policy import/export (25.1+) can transfer policies containing custom patterns between environments. [API-intelligence]

### Worked Examples

**Example 1: Internal Project Code Name Detection**

| Aspect | Detail |
|--------|--------|
| Pattern Type | Regex |
| Regex | `PROJ-[A-Z]{2,4}-\d{4,8}` |
| Minimum Matches | 1 |
| Look In | Body + Subject + Attachments |
| Severity | 2 - Medium |
| **WHY** | Internal project codes (PROJ-AB-12345) should never appear in external communications. |
| **GOTCHA** | Test regex against a corpus of real emails before deploying. Common false positive: similar patterns in vendor tracking numbers. |

**Example 2: Employee ID Number Detection**

| Aspect | Detail |
|--------|--------|
| Pattern Type | Regex |
| Regex | `EMP-\d{6}` (organization-specific format) |
| Minimum Matches | 5 (bulk exposure threshold) |
| Match Counting | Unique |
| Look In | Attachments only |
| Severity | 1 - High |
| **WHY** | A document with 5+ unique employee IDs is an HR data export. Single IDs are normal in email signatures. |
| **GOTCHA** | Custom regex has no built-in validator. Unlike built-in data identifiers (which include Luhn, checksum), this pattern matches purely on format. |

**Example 3: M&A Code Name Protection (Keywords + Proximity)**

| Aspect | Detail |
|--------|--------|
| Pattern Type | Keywords with proximity |
| Keywords | "Project Falcon", "acquisition target", "merger candidate" |
| Case Sensitive | Yes (reduce false positives from generic use of words) |
| Whole Words | Yes |
| Proximity | 100 characters (keywords must appear near each other) |
| Severity | 1 - High |
| **WHY** | M&A code names and related terms appearing together indicate confidential deal information. Proximity matching reduces false positives from unrelated uses of individual terms. |
| **GOTCHA** | Case-sensitive matching means "project falcon" (lowercase) is not detected. Decide based on how your organization uses these terms. |

**Example 4: Medical Terminology Detection (Drug Names)**

| Aspect | Detail |
|--------|--------|
| Pattern Type | Keywords |
| Keywords | "metformin", "atorvastatin", "lisinopril" (50+ drug names) |
| Case Sensitive | No |
| Whole Words | Yes |
| Minimum Matches | 3 (threshold: 3+ drug names = likely medical data) |
| Severity | 2 - Medium |
| **WHY** | Multiple drug names in a document suggest patient medical records. HIPAA PHI protection. |
| **GOTCHA** | Drug name keywords generate high false positive rates in pharmaceutical/healthcare organizations where these terms are routine. Add sender-based exceptions for pharmacy and clinical departments. |

**Example 5: Source Code Detection (Regex for Import Statements)**

| Aspect | Detail |
|--------|--------|
| Pattern Type | Regex |
| Regex | `(import\s+[\w.]+;|#include\s+[<"][^>"]+[>"]|from\s+\w+\s+import\s+\w+)` |
| Minimum Matches | 5 |
| Look In | Attachments only |
| Severity | 2 - Medium |
| **WHY** | Files with multiple import/include statements are likely source code. IP protection for engineering organizations. |
| **GOTCHA** | This is a basic heuristic. VML is a much better technology for source code detection because it learns the statistical patterns of your specific codebase. Use this regex approach only as a stopgap until VML is trained. |

---

## Technology 3: Exact Data Matching (EDM)

### What EDM Does

EDM fingerprints structured, tabular data from databases, CSV files, or directory exports. Instead of detecting patterns, EDM detects exact matches of real data values from your organization's datasets. The system creates non-reversible hashes of data records, then compares content against those hashes during detection. [S1, S4, V19]

**Key advantage over pattern matching:** EDM detects actual data values (e.g., the real SSN 123-45-6789 belonging to employee John Smith), not just any string that looks like an SSN. This dramatically reduces false positives.

**Navigation:** Manage > Data Profiles > Exact Data Profiles

### EDM Architecture

```
                                                      +-----------------+
  +------------------+     +-----------+     +---------->  Detection      |
  |  Data Source      |     |  Enforce  |     |        |  Servers        |
  |  (CSV/DB/LDAP)    +---->+  Server   +-----+        +-----------------+
  |                   |     |           |     |
  |  Name | SSN | DOB |     | Index     |     |        +-----------------+
  |  John | 123 | 1/1 |     | Creation  |     +---------->  Endpoint      |
  |  Jane | 456 | 2/2 |     | (hash)    |              |  Agents         |
  +------------------+     +-----------+              +-----------------+
                                |
                                v
                          +------------------+
                          |  Hashed Index     |
                          |  (non-reversible) |
                          |  abc123 -> row 1  |
                          |  def456 -> row 2  |
                          +------------------+
```

### EDM Configuration Workflow

#### Step 1: Prepare Data Source

```
+=========================================================================+
|  Data Source Preparation                                                  |
+=========================================================================+
|                                                                          |
|  Supported formats:                                                      |
|    - CSV (comma-separated values)                                        |
|    - TSV (tab-separated values)                                          |
|    - Pipe-delimited files                                                |
|    - Database connection (Oracle, SQL Server, MySQL)                      |
|    - LDAP/Active Directory export                                        |
|                                                                          |
|  Requirements:                                                           |
|    - First row = column headers (optional but recommended)               |
|    - Consistent delimiters throughout file                                |
|    - UTF-8 encoding recommended                                          |
|    - Maximum recommended: 10M rows (use Remote Indexer for larger)       |
|                                                                          |
+=========================================================================+
```

**Data preparation rules:**
1. Remove blank rows and columns
2. Ensure consistent formatting (dates in same format, no mixed separators)
3. Remove header row duplicates
4. Validate that key fields (SSN, CC, employee ID) are populated for all rows
5. Error rate must be below the configured threshold (default 5%)

#### Step 2: Create Exact Data Profile

**Navigation:** Manage > Data Profiles > Exact Data Profiles > Add Exact Data Profile

```
+=========================================================================+
|  Create Exact Data Profile                                               |
+=========================================================================+
|                                                                          |
|  Profile Name:  [Employee PII Protection                      ]          |
|                                                                          |
|  Description:   [Protects employee records including SSN, DOB, address. ]|
|                 [Source: HR database export (updated weekly).           ] |
|                                                                          |
|  Data Source:                                                            |
|    (*) File Upload                                                       |
|    ( ) Database Connection                                               |
|    ( ) LDAP/AD Connection                                                |
|                                                                          |
|  File:  [employee_pii_2024.csv           ] [Browse...]                   |
|                                                                          |
|  Delimiter:    (*) Comma   ( ) Tab   ( ) Pipe   ( ) Custom: [  ]         |
|  Text Qualifier: (*) Double Quote  ( ) Single Quote  ( ) None            |
|  Header Row:   (*) First row is header   ( ) No header row              |
|                                                                          |
|  Error Threshold: [5   ] %  (indexing stops if errors exceed this %)     |
|                                                                          |
|                                               [Cancel]  [Next >]         |
+=========================================================================+
```

#### Step 3: Map Columns

```
+=========================================================================+
|  Column Mapping                                                          |
+=========================================================================+
|                                                                          |
|  Map each column to a field type. Mark fields as KEY or CORROBORATIVE.   |
|                                                                          |
|  +------------------------------------------------------------------+   |
|  | Column Header  | Sample Data       | Field Type        | Role    |   |
|  |----------------|-------------------|-------------------|---------|   |
|  | First_Name     | John              | [First Name    v] | ( ) Key |   |
|  |                |                   |                   | (*) Cor |   |
|  |----------------|-------------------|-------------------|---------|   |
|  | Last_Name      | Smith             | [Last Name     v] | ( ) Key |   |
|  |                |                   |                   | (*) Cor |   |
|  |----------------|-------------------|-------------------|---------|   |
|  | SSN            | 123-45-6789       | [SSN           v] | (*) Key |   |
|  |                |                   |                   | ( ) Cor |   |
|  |----------------|-------------------|-------------------|---------|   |
|  | DOB            | 01/15/1985        | [Date of Birth v] | ( ) Key |   |
|  |                |                   |                   | (*) Cor |   |
|  |----------------|-------------------|-------------------|---------|   |
|  | Email          | john@company.com  | [Email Address v] | ( ) Key |   |
|  |                |                   |                   | (*) Cor |   |
|  |----------------|-------------------|-------------------|---------|   |
|  | Employee_ID    | EMP-001234        | [Custom ID     v] | (*) Key |   |
|  |                |                   |                   | ( ) Cor |   |
|  +------------------------------------------------------------------+   |
|                                                                          |
|  Minimum fields for match: [2   ] of [6   ] mapped fields               |
|  [x] At least one KEY field must be among matched fields                 |
|                                                                          |
|                                         [< Back]  [Cancel]  [Next >]     |
+=========================================================================+
```

### Column Mapping Field Reference

| Field | Type | Required | Default | Options | Evidence |
|-------|------|----------|---------|---------|----------|
| Field Type | Dropdown per column | Yes (for mapped columns) | -- | First Name, Last Name, SSN, Date of Birth, Email Address, Phone, Address, City, State, Zip, Country, Custom ID, Custom Text | A [S1, S4] |
| Role | Radio per column | Yes | Corroborative | Key (unique identifier) or Corroborative (supporting field) | A [S1, S4] |
| Minimum fields for match | Integer | Yes | 2 | 2 to N (must be >= 2) | A [S1, S4] |
| Require KEY field | Checkbox | No | Checked | Ensures at least one key field matches | A [S1, S4] |
| Error Threshold | Percentage | Yes | 5% | 1-50% (indexing stops if error rate exceeds this) | A [S1, V19] |

#### Step 4: Index Creation and Scheduling

```
+=========================================================================+
|  Index Configuration                                                     |
+=========================================================================+
|                                                                          |
|  Indexing Method:                                                        |
|    (*) Index on Enforce Server (recommended for <1M rows)                |
|    ( ) Remote EDM Indexer (recommended for >1M rows)                     |
|                                                                          |
|  Schedule:                                                               |
|    ( ) Index once (manual re-index)                                      |
|    (*) Recurring schedule                                                |
|        Frequency: [Weekly       v]                                       |
|        Day:       [Sunday       v]                                       |
|        Time:      [02:00 AM     v]                                       |
|                                                                          |
|  Index Status: [ Not yet indexed ]                                       |
|                                                                          |
|                                         [< Back]  [Cancel]  [Create]     |
+=========================================================================+
```

| Field | Type | Required | Default | Options | Evidence |
|-------|------|----------|---------|---------|----------|
| Indexing Method | Radio | Yes | Enforce Server | Enforce Server, Remote EDM Indexer | A [S1, S4] |
| Schedule | Radio + dropdowns | Yes | Index once | Once, Daily, Weekly, Monthly | A [S1, S4] |
| Frequency | Dropdown | If recurring | Weekly | Daily, Weekly, Monthly | A [S1] |
| Day | Dropdown | If weekly/monthly | Sunday | Sun-Sat / 1-28 | A [S1] |
| Time | Dropdown | If recurring | 02:00 AM | Hourly intervals | A [S1] |

**API Coverage:** PARTIAL -- EDM index trigger is available via `POST /edm/index` (DLP 16.0 RU2+), but EDM profile creation, column mapping, and scheduling are console-only. [API-intelligence]

### EDM Worked Examples

**Example 1: Employee PII Protection**

| Aspect | Detail |
|--------|--------|
| Data Source | HR database CSV export (50,000 employees) |
| Columns | First Name, Last Name, SSN (KEY), DOB, Email, Employee ID (KEY) |
| Match Threshold | 2 of 6 fields, at least 1 KEY |
| Index Schedule | Weekly (Sunday 2 AM) |
| **WHY** | Protects employee personal data. SSN or Employee ID as key fields ensures matching is identity-specific, not coincidental name matches. |
| **GOTCHA** | If HR adds 100 new hires this week, their data is not protected until the next index run on Sunday. For high-turnover environments, use daily indexing. |

**Example 2: Customer Financial Records**

| Aspect | Detail |
|--------|--------|
| Data Source | CRM database export (2M customers) |
| Columns | Full Name, Account Number (KEY), CC Last-4, Phone, Address, Email |
| Match Threshold | 2 of 6 fields, at least 1 KEY |
| Index Schedule | Daily (3 AM) |
| **WHY** | Account numbers are the primary identifier. Corroborative fields (name, phone) distinguish real customer data from random number matches. |
| **GOTCHA** | 2M rows requires Remote EDM Indexer. Running on Enforce Server will degrade console performance for 30-60 minutes during indexing. |

**Example 3: Healthcare Patient Data (HIPAA)**

| Aspect | Detail |
|--------|--------|
| Data Source | EHR system CSV export (500K patients) |
| Columns | Patient Name, MRN (KEY), DOB, SSN (KEY), Address, Phone, Insurance ID |
| Match Threshold | 3 of 7 fields, at least 1 KEY |
| Index Schedule | Daily (1 AM) |
| **WHY** | Higher match threshold (3 of 7) reduces false positives in healthcare environments where medical terms and patient names are common in legitimate communications. |
| **GOTCHA** | HIPAA requires protecting 18 PHI identifiers. EDM covers structured identifiers but does NOT detect narrative medical notes. Combine EDM with VML for comprehensive HIPAA coverage. |

**Example 4: Financial Account Numbers (SOX)**

| Aspect | Detail |
|--------|--------|
| Data Source | Financial system export (10K accounts) |
| Columns | Account Name, Account Number (KEY), Routing Number (KEY), Balance, Account Type |
| Match Threshold | 2 of 5 fields, at least 1 KEY |
| Index Schedule | Monthly (1st Sunday, 4 AM) |
| **WHY** | Financial account data changes slowly. Monthly indexing is sufficient for stable financial master data. |
| **GOTCHA** | Do NOT include the Balance column in EDM indexing. Balance values change daily and will cause "2 of N" matches on stale balance values to fail. Only index stable identifiers. |

**Example 5: Student Records (FERPA)**

| Aspect | Detail |
|--------|--------|
| Data Source | Student Information System CSV (200K students) |
| Columns | Student Name, Student ID (KEY), SSN (KEY), DOB, Email, Major, GPA |
| Match Threshold | 2 of 7 fields, at least 1 KEY |
| Index Schedule | Weekly (during semester), Monthly (during breaks) |
| **WHY** | FERPA protects student education records. Student ID is the primary key; SSN is secondary. |
| **GOTCHA** | Do NOT include GPA in the index. GPA values (e.g., 3.5, 2.8) are common numeric values that will cause massive false positives when matched as corroborative fields. |

**Example 6: Vendor Contract Data**

| Aspect | Detail |
|--------|--------|
| Data Source | Procurement system CSV (5K vendors) |
| Columns | Vendor Name, Vendor ID (KEY), Tax ID/EIN (KEY), Contact Name, Contract Value, Contact Email |
| Match Threshold | 2 of 6 fields, at least 1 KEY |
| Index Schedule | Monthly |
| **WHY** | Vendor tax IDs and contract values are confidential business information. Detecting bulk vendor data exports protects procurement intelligence. |
| **GOTCHA** | Vendor names are often common words ("Acme", "Global Services"). Do NOT make Vendor Name a KEY field. Use Tax ID or Vendor ID as key fields. |

**Example 7: Price List Protection**

| Aspect | Detail |
|--------|--------|
| Data Source | Pricing database CSV (50K SKUs) |
| Columns | Product Name, SKU (KEY), Unit Price, Wholesale Price, Customer Tier, Discount Code (KEY) |
| Match Threshold | 3 of 6 fields, at least 1 KEY |
| Index Schedule | Weekly |
| **WHY** | Competitor access to pricing data causes revenue loss. Requiring 3 of 6 fields ensures only bulk pricing extracts are flagged, not individual product mentions. |
| **GOTCHA** | Price values ($19.99) are extremely common in business communications. Never use price columns as KEY fields. SKU and Discount Code are the reliable identifiers. |

---

## Technology 4: Indexed Document Matching (IDM)

### What IDM Does

IDM fingerprints unstructured documents using rolling hash algorithms to detect exact or partial copies of registered documents. Unlike EDM (which works on structured tabular data), IDM works on documents -- Word files, PDFs, source code, images, CAD drawings. [S1, S4, V22]

**Key capability:** IDM detects derivative content. If an employee copies 3 paragraphs from a confidential legal brief into an email, IDM can detect that the email contains content derived from the protected document, even though the email is not the document itself.

**Navigation:** Manage > Data Profiles > Indexed Document Profiles

### IDM Configuration Workflow

#### Step 1: Source Document Registration

```
+=========================================================================+
|  Create Indexed Document Profile                                         |
+=========================================================================+
|                                                                          |
|  Profile Name:  [Legal Contracts - M&A Documents             ]           |
|                                                                          |
|  Description:   [Protects M&A legal contracts and term sheets.          ]|
|                 [Source: Legal department file share.                    ]|
|                                                                          |
|  Document Source:                                                        |
|    (*) File Share (UNC path)                                             |
|    ( ) Upload Directory (ZIP)                                            |
|    ( ) Remote Indexer (for cloud/CASB)                                   |
|                                                                          |
|  Path: [\\legalshare\ma-documents\active\                     ]          |
|                                                                          |
|  Include subfolders: [x]                                                 |
|  File types to index: (*) All supported  ( ) Selected types only        |
|                                                                          |
|                                               [Cancel]  [Next >]         |
+=========================================================================+
```

#### Step 2: Fingerprint Configuration

```
+=========================================================================+
|  Fingerprint Configuration                                               |
+=========================================================================+
|                                                                          |
|  Matching Mode:                                                          |
|    [x] Exact document match (binary stamp)                               |
|    [x] Partial content match (rolling hash)                              |
|                                                                          |
|  Partial Match Threshold:  [10  ] %                                      |
|    (minimum percentage of document content that must match)              |
|                                                                          |
|  Endpoint IDM Support:                                                   |
|    [ ] Enable IDM for endpoint agents                                    |
|    (increases agent resource usage; off by default)                       |
|                                                                          |
|  Document Group:  [M&A Confidential         v]  [+ New Group]            |
|                                                                          |
|  Schedule:                                                               |
|    (*) Re-index on schedule                                              |
|        Frequency: [Weekly       v]                                       |
|        Day:       [Saturday     v]                                       |
|        Time:      [03:00 AM     v]                                       |
|    ( ) Manual re-index only                                              |
|                                                                          |
|                                         [< Back]  [Cancel]  [Create]     |
+=========================================================================+
```

### IDM Field Reference

| Field | Type | Required | Default | Options | Evidence |
|-------|------|----------|---------|---------|----------|
| Profile Name | Text (256 chars) | Yes | -- | Free text | A [S1, S4] |
| Document Source | Radio | Yes | File Share | File Share, Upload, Remote Indexer | A [S1, S4] |
| Path | Text / file browser | Yes | -- | UNC path, local path, or ZIP upload | A [S1, S4] |
| Include Subfolders | Checkbox | No | Checked | -- | A [S1] |
| File Types | Radio | No | All supported | All, or selected from 330+ supported types | A [S1, S4] |
| Exact Document Match | Checkbox | No | Checked | Binary stamp matching for identical files | A [S1, S4] |
| Partial Content Match | Checkbox | No | Checked | Rolling hash for content fragments | A [S1, S4] |
| Partial Match Threshold | Integer (%) | If partial enabled | 10% | 1-100% | A [S1, S4] |
| Endpoint IDM Support | Checkbox | No | Unchecked | Enable partial matching on endpoint agents | B [V22] |
| Document Group | Dropdown | No | Default | Custom groups for organization | A [S1] |
| Schedule | Radio + dropdowns | Yes | Manual | Manual, Daily, Weekly, Monthly | A [S1, S4] |

**API Coverage:** GAP -- IDM profile creation is console-only. Remote Indexer Tool creates cloud-compatible index files for CloudSOC. [API-intelligence]

### IDM Worked Examples

**Example 1: M&A Legal Contracts**

| Aspect | Detail |
|--------|--------|
| Source | Legal file share: `\\legal\ma-contracts\` (200 documents) |
| Match Mode | Exact + Partial (10% threshold) |
| Endpoint IDM | Enabled |
| Schedule | Daily (M&A documents change frequently) |
| **WHY** | M&A information is among the most sensitive in any organization. Even a partial copy of a term sheet leaking can affect stock prices and deal terms. |
| **GOTCHA** | 10% threshold on a 2-page term sheet is about 2-3 sentences. This may be too sensitive for short documents. Consider raising to 20% for documents under 5 pages. |

**Example 2: Source Code Repository**

| Aspect | Detail |
|--------|--------|
| Source | Git export of main branch: `\\eng\source-export\` (10,000 files) |
| Match Mode | Partial only (15% threshold) |
| File Types | Selected: .java, .py, .go, .ts, .js, .c, .cpp, .h |
| Endpoint IDM | Enabled |
| Schedule | Weekly (after CI/CD tag) |
| **WHY** | Source code IP is the core asset. IDM detects when engineers copy code to personal email or external services. |
| **GOTCHA** | Open-source code files (imported libraries, Apache-licensed code) will also be fingerprinted. Exclude `/vendor/`, `/node_modules/`, and similar directories from the source path to avoid false positives on open-source code. |

**Example 3: Board Presentations**

| Aspect | Detail |
|--------|--------|
| Source | Upload ZIP of board decks from last 4 quarters (40 files) |
| Match Mode | Exact + Partial (5% threshold) |
| Endpoint IDM | Enabled |
| Schedule | Quarterly (after each board meeting) |
| **WHY** | Board materials contain unannounced strategy, financials, and executive decisions. Low partial threshold catches even slide-by-slide extraction. |
| **GOTCHA** | PowerPoint files with common templates (company logo slides, agenda slides) may trigger partial matches on non-board documents that use the same template. Add exceptions for the template file itself. |

**Example 4: Engineering Design Documents (CAD/STEP)**

| Aspect | Detail |
|--------|--------|
| Source | Engineering file share: `\\eng\designs\production\` (5,000 files) |
| Match Mode | Exact only (binary stamp) |
| File Types | All (covers .dwg, .step, .stl, .iges, proprietary formats) |
| Endpoint IDM | Disabled (binary stamp only works at network level) |
| Schedule | Weekly |
| **WHY** | Engineering designs are IP. Exact binary match catches unauthorized copies of design files being exfiltrated. |
| **GOTCHA** | Binary files only support exact match, NOT partial content matching. A modified version of a CAD file (rotated, scaled, annotated) will NOT match. For derivative detection, convert CAD to STEP text format and use partial matching on the text output. |

**Example 5: Clinical Trial Protocols (Pharmaceutical)**

| Aspect | Detail |
|--------|--------|
| Source | Regulatory affairs share: `\\ra\clinical-protocols\active\` (300 documents) |
| Match Mode | Exact + Partial (8% threshold) |
| File Types | PDF, DOCX |
| Endpoint IDM | Enabled |
| Schedule | Weekly |
| **WHY** | Clinical trial protocols are trade secrets. Competitor access enables fast-follower clinical trials. 8% threshold is sensitive enough to catch protocol section copy-paste. |
| **GOTCHA** | Clinical protocols use standardized language from regulatory templates (ICH GCP). The boilerplate sections will match across ALL protocols. Use document groups to separate therapeutic areas and reduce cross-protocol false positives. |

---

## Technology 5: Vector Machine Learning (VML)

### What VML Does

VML uses statistical text analysis to classify documents by similarity to training examples. Instead of defining what to look for (patterns, fingerprints), VML learns what sensitive content "looks like" from examples. [S1, S7, V20]

**Key advantage over other technologies:** VML can detect documents that have never been explicitly fingerprinted or indexed. It classifies based on content similarity to the training set, catching new documents that match the learned pattern.

**Navigation:** Manage > Data Profiles > Vector Machine Learning Profiles

### VML Configuration Workflow

#### Step 1: Training Data Preparation

```
+=========================================================================+
|  VML Training Data Requirements                                          |
+=========================================================================+
|                                                                          |
|  POSITIVE training set (documents you WANT to protect):                  |
|    Minimum: 50 documents                                                 |
|    Recommended: 250+ documents                                           |
|    Best practice: 250-500 documents                                      |
|    Requirements:                                                         |
|      - Representative of the content type to protect                     |
|      - Diverse (different authors, time periods, sub-topics)             |
|      - Text-based (VML does not work on binary data)                     |
|                                                                          |
|  NEGATIVE training set (documents that should NOT trigger):              |
|    Minimum: 50 documents                                                 |
|    Recommended: Equal to positive set size                               |
|    Best practice: "Near-miss" documents (similar but not sensitive)      |
|    Requirements:                                                         |
|      - Related to the positive set (same domain, different sensitivity)  |
|      - NOT random documents (that teaches the model nothing)             |
|                                                                          |
|  CRITICAL: Negative examples should be NEAR-MISSES, not random docs.    |
|  For financial reports (positive), use marketing brochures or public     |
|  financial filings as negative -- NOT recipes or sports articles.        |
|                                                                          |
+=========================================================================+
```

#### Step 2: Create VML Profile

```
+=========================================================================+
|  Create VML Profile                                                      |
+=========================================================================+
|                                                                          |
|  Profile Name:  [Financial Reports - Quarterly Earnings      ]           |
|                                                                          |
|  Description:   [Classifies internal financial reports containing       ]|
|                 [non-public quarterly earnings and forecasts.           ]|
|                                                                          |
|  Positive Training Documents:                                            |
|    Source: [\\finance\vml-training\positive\           ] [Browse...]      |
|    Documents found: [312]                                                |
|                                                                          |
|  Negative Training Documents:                                            |
|    Source: [\\finance\vml-training\negative\           ] [Browse...]      |
|    Documents found: [295]                                                |
|                                                                          |
|                                               [Cancel]  [Train Model]    |
+=========================================================================+
```

#### Step 3: Model Training and Evaluation

```
+=========================================================================+
|  VML Training Results                                                    |
+=========================================================================+
|                                                                          |
|  Profile: Financial Reports - Quarterly Earnings                         |
|                                                                          |
|  Training Status: COMPLETE                                               |
|                                                                          |
|  Accuracy Score:  [##############----]  92.4%                            |
|                                                                          |
|  Training Summary:                                                       |
|    Positive documents processed: 312 / 312                               |
|    Negative documents processed: 295 / 295                               |
|    Model features extracted: 4,832                                       |
|                                                                          |
|  Test Results (cross-validation):                                        |
|    True Positive Rate:  94.2%                                            |
|    False Positive Rate:  3.1%                                            |
|    True Negative Rate:  96.9%                                            |
|    False Negative Rate:  5.8%                                            |
|                                                                          |
|  Actions:                                                                |
|    [Accept Profile]  -- Use this model for detection                     |
|    [Retrain]         -- Add more documents and retrain                   |
|    [Delete]          -- Discard this training                            |
|                                                                          |
+=========================================================================+
```

### VML Field Reference

| Field | Type | Required | Default | Options | Evidence |
|-------|------|----------|---------|---------|----------|
| Profile Name | Text (256 chars) | Yes | -- | Free text | A [S1, S7] |
| Positive Training Source | Directory path / upload | Yes | -- | UNC path or ZIP upload | A [S1, S7, V20] |
| Negative Training Source | Directory path / upload | Yes | -- | UNC path or ZIP upload | A [S1, S7, V20] |
| Minimum documents per set | -- | -- | 50 | Recommended: 250+ | A [S7] |
| Accuracy Score | Read-only | -- | -- | 0-100% | A [S7] |
| Accept/Retrain/Delete | Buttons | Post-training | -- | Accept makes profile available for policy use | A [S1, S7] |

**API Coverage:** GAP -- VML profile creation and training is console-only. No API surface exists for VML operations. [API-intelligence]

### VML Worked Examples

**Example 1: Internal Financial Reports (SOX)**

| Aspect | Detail |
|--------|--------|
| Positive Set | 300 internal quarterly/annual earnings reports (last 5 years) |
| Negative Set | 280 public press releases, investor presentations, 10-K filings |
| Target Accuracy | >90% |
| Retraining Schedule | Annually (after each annual report cycle) |
| **WHY** | Non-public earnings data is material insider information under SOX. VML catches new reports that were never explicitly indexed. |
| **GOTCHA** | If all positive examples are from the same author or department, the model may learn writing style rather than content type. Include reports from all business units and time periods. |

**Example 2: Proprietary Source Code Classification**

| Aspect | Detail |
|--------|--------|
| Positive Set | 500 files from proprietary codebase (core algorithms, trade secrets) |
| Negative Set | 500 open-source files from the same language (Apache/MIT-licensed code) |
| Target Accuracy | >85% |
| Retraining Schedule | Every 6 months (codebase evolves) |
| **WHY** | VML learns the statistical patterns of your specific codebase (variable naming, comment style, module structure) vs. generic open-source code. |
| **GOTCHA** | If your proprietary code heavily uses open-source frameworks, the model may confuse framework usage with proprietary code. Select training examples that emphasize unique business logic, not framework glue code. |

**Example 3: Legal Briefs and Memoranda**

| Aspect | Detail |
|--------|--------|
| Positive Set | 250 attorney-client privileged memos and legal briefs |
| Negative Set | 250 published court opinions, public legal filings, generic templates |
| Target Accuracy | >88% |
| Retraining Schedule | Annually |
| **WHY** | Attorney-client privilege requires protecting legal work product. VML distinguishes privileged internal analysis from public legal filings. |
| **GOTCHA** | Legal language is highly standardized. If positive and negative sets both contain dense legal citations, the model may struggle to differentiate. Focus positive set on analysis sections and strategy memos, not citation-heavy procedural documents. |

**Example 4: Engineering Schematics Documentation**

| Aspect | Detail |
|--------|--------|
| Positive Set | 200 internal design specification documents |
| Negative Set | 200 published datasheets, public reference designs, application notes |
| Target Accuracy | >85% |
| Retraining Schedule | Every 6 months |
| **WHY** | Product design specs are IP. Datasheets are public. VML learns the difference between internal engineering detail and public-facing product information. |
| **GOTCHA** | VML only works on text. If engineering specs are primarily diagrams with minimal text, VML accuracy will be low. Supplement with IDM for image-heavy documents. |

**Example 5: Medical Records / Clinical Notes (HIPAA)**

| Aspect | Detail |
|--------|--------|
| Positive Set | 400 de-identified clinical notes and patient summaries |
| Negative Set | 400 published medical journal articles and clinical guideline documents |
| Target Accuracy | >90% |
| Retraining Schedule | Annually |
| **WHY** | Clinical notes contain PHI patterns (patient narratives, diagnosis discussions, treatment plans) that are distinct from published medical literature. |
| **GOTCHA** | Use ONLY de-identified training data. Using real PHI as training data creates a secondary data protection problem. Work with the privacy officer to prepare anonymized training sets. |

---

## Technology 6: Form Recognition

### What Form Recognition Does

Form Recognition detects sensitive information in scanned or digital forms by matching the layout and structure of registered form templates. When a filled-out version of a registered form is detected, it triggers a policy match. [S1, V21]

**Navigation:** Manage > Data Profiles > (Form Recognition section, within policy rules)

### Configuration Workflow

```
+=========================================================================+
|  Form Recognition Configuration                                         |
+=========================================================================+
|                                                                          |
|  Register Form Template:                                                 |
|                                                                          |
|  Form Name:  [IRS W-2 Wage and Tax Statement              ]             |
|                                                                          |
|  Template File:  [w2-blank-template.pdf       ] [Browse...]             |
|                                                                          |
|  Form Type:   (*) Blank form (recommended)                               |
|               ( ) Filled form (for reference matching)                   |
|                                                                          |
|  Matching Behavior:                                                      |
|    [x] Detect filled-out versions of this form                           |
|    [x] Detect blank copies of this form                                  |
|    [ ] Detect partial scans (form fragments)                             |
|                                                                          |
|  Field Configuration (optional):                                         |
|    [x] SSN field present                                                 |
|    [x] Salary/wage fields present                                        |
|    [x] Address fields present                                            |
|                                                                          |
|                                               [Cancel]  [Register]       |
+=========================================================================+
```

### Form Recognition Field Reference

| Field | Type | Required | Default | Options | Evidence |
|-------|------|----------|---------|---------|----------|
| Form Name | Text | Yes | -- | Free text | A [S1] |
| Template File | File upload | Yes | -- | PDF, TIFF, PNG, JPG of blank form | A [S1, V21] |
| Form Type | Radio | Yes | Blank form | Blank (preferred), Filled (reference) | A [S1] |
| Detect Filled Versions | Checkbox | No | Checked | -- | A [S1] |
| Detect Blank Copies | Checkbox | No | Checked | -- | A [S1] |
| Detect Partial Scans | Checkbox | No | Unchecked | Experimental; may increase false positives | B [V21] |
| Field Configuration | Checkboxes | No | None | Tag fields expected in the form | B [V21] |

**API Coverage:** GAP -- Form Recognition is console-only. [API-intelligence]

### Form Recognition Worked Examples

**Example 1: W-2 Tax Forms**

| Aspect | Detail |
|--------|--------|
| Template | Blank IRS W-2 form (current year) |
| Detect | Filled versions + blank copies |
| **WHY** | W-2 forms contain SSN, salary, and employer information. Tax identity theft starts with W-2 data. |
| **GOTCHA** | The IRS updates W-2 layout periodically. Re-register the template when the form design changes (usually annually). |

**Example 2: Medical Intake Forms (HIPAA)**

| Aspect | Detail |
|--------|--------|
| Template | Patient intake form used by the organization's clinics |
| Detect | Filled versions only |
| **WHY** | Patient intake forms contain name, DOB, SSN, insurance, and medical history. PHI protection under HIPAA. |
| **GOTCHA** | Scanned forms at low resolution (below 150 DPI) may not trigger recognition. Ensure scan quality standards are communicated to clinical staff. |

**Example 3: Insurance Claim Forms**

| Aspect | Detail |
|--------|--------|
| Template | CMS-1500 (standard medical insurance claim form) |
| Detect | Filled versions + blank copies |
| **WHY** | Insurance claims contain patient identity, diagnosis codes, and treatment information. |
| **GOTCHA** | CMS-1500 is a standardized form used across the healthcare industry. False positives may occur on forms from external partners. Add sender exceptions for known insurance partners. |

---

## Technology 7: File Properties

### What File Properties Do

File property detection matches on metadata characteristics of files rather than their content. This includes true file type (detected by binary signature, not extension), file size, file name patterns, and custom document properties. [S1, S4]

**Navigation:** Manage > Policies > Policy List > [policy] > Detection > Add Rule > Message Attachment or File Property

### Configuration Screen

```
+=========================================================================+
|  Add Detection Rule - File Properties                                    |
+=========================================================================+
|                                                                          |
|  Rule Type: [Message Attachment or File Property Matches     ]           |
|                                                                          |
|  File Type Detection:                                                    |
|    [x] Detect by true file type (binary signature)                       |
|        Selected types:                                                   |
|        [x] Microsoft Excel (XLS, XLSX)                                   |
|        [x] Microsoft Access (MDB, ACCDB)                                 |
|        [x] Database files (DBF, SQLite)                                  |
|        [x] Archive files (ZIP, RAR, 7Z)                                  |
|        [ ] PDF files                                                     |
|        [ ] Image files (JPG, PNG, BMP, TIFF)                             |
|        [x] Executable files (EXE, DLL, MSI)                              |
|        ...  (330+ file types available)                                   |
|                                                                          |
|  File Name Pattern:                                                      |
|    [ ] Match file name pattern:  [                           ]           |
|        (*) Contains   ( ) Starts with   ( ) Ends with   ( ) Regex       |
|                                                                          |
|  File Size:                                                              |
|    [ ] File size exceeds:  [    ] MB                                     |
|    [ ] File size is between: [    ] MB and [    ] MB                     |
|                                                                          |
|  Custom Properties:                                                      |
|    [ ] Match custom document property:                                   |
|        Property name:  [                    ]                             |
|        Property value: [                    ]                             |
|                                                                          |
|  Severity:  ( ) 1 - High   (*) 2 - Medium   ( ) 3 - Low   ( ) 4 - Info |
|                                                                          |
|                                               [Cancel]  [Save Rule]      |
+=========================================================================+
```

### File Properties Field Reference

| Field | Type | Required | Default | Options | Evidence |
|-------|------|----------|---------|---------|----------|
| True File Type | Checkbox list | At least 1 property required | None | 330+ file types organized by category | A [S1, S4] |
| File Name Pattern | Text + match mode | No | -- | Contains, Starts with, Ends with, Regex | A [S1, S4] |
| File Size | Integer + unit | No | -- | Size in KB/MB/GB, comparison operators | A [S1, S4] |
| Custom Document Properties | Name/Value pairs | No | -- | Microsoft Office document properties, PDF metadata | B [S4] |
| Severity | Radio | Yes | 2 - Medium | 1-4 | A [S1, S4] |

**API Coverage:** GAP -- File property rule creation is console-only. [API-intelligence]

### File Properties Worked Examples

**Example 1: Database File Exfiltration Detection**

| Aspect | Detail |
|--------|--------|
| File Types | Microsoft Access (MDB, ACCDB), SQLite, DBF, SQL dump |
| File Size | Any (no minimum) |
| Severity | 1 - High |
| **WHY** | Database files being sent externally almost always indicate bulk data exfiltration. These file types should never leave the organization. |
| **GOTCHA** | Some legitimate workflows involve sending Access databases (legacy reporting, partner data exchange). Add sender/recipient exceptions for these known workflows BEFORE enabling blocking. |

**Example 2: Executable File Detection in Email**

| Aspect | Detail |
|--------|--------|
| File Types | EXE, DLL, MSI, BAT, CMD, PS1, VBS, JAR |
| File Name Pattern | (not needed -- binary signature detection catches renamed executables) |
| Severity | 1 - High |
| **WHY** | Executables in email are a malware and data exfiltration vector. True file type detection catches executables renamed to .txt or .jpg. |
| **GOTCHA** | ZIP archives containing executables require archive extraction settings to be enabled. Without extraction, the executable inside the ZIP is not inspected. |

**Example 3: Large File Transfer Monitoring**

| Aspect | Detail |
|--------|--------|
| File Size | Exceeds 25 MB |
| File Types | All |
| Severity | 3 - Low (informational monitoring) |
| **WHY** | Unusually large file transfers may indicate bulk data export. Low severity for monitoring without blocking. |
| **GOTCHA** | Marketing departments regularly send large image files and videos. This rule will generate high volume. Use it as a secondary condition in compound rules, not standalone. |

**Example 4: CAD/Engineering Design Files**

| Aspect | Detail |
|--------|--------|
| File Types | AutoCAD (DWG, DXF), SolidWorks (SLDPRT, SLDASM), STEP, IGES, STL |
| Severity | 2 - Medium |
| **WHY** | Engineering design files are IP. Detecting these file types leaving the engineering network protects manufacturing secrets. |
| **GOTCHA** | 3D printing STL files are increasingly used by non-engineering departments (marketing for product renders, facilities for fixture designs). Combine file type detection with sender-based conditions to focus on engineering department exports. |

**Example 5: Encrypted/Password-Protected Archive Detection**

| Aspect | Detail |
|--------|--------|
| File Types | Encrypted ZIP, encrypted RAR, password-protected Office documents |
| File Name Pattern | (not needed) |
| Severity | 2 - Medium |
| **WHY** | Users encrypt files specifically to bypass DLP content inspection. Flagging encrypted outbound files is a critical detection gap control. |
| **GOTCHA** | Do NOT exception encrypted files. Instead, create a dedicated policy that DETECTS encrypted file transfers. If you exception them, you create an evasion technique. Monitor encrypted file volume as a security metric. |

---

## Cross-Technology Prerequisites Summary

| Technology | Pre-Setup Required | Time to First Detection | Refresh/Retraining | Evidence |
|-----------|-------------------|------------------------|--------------------|---------|
| Data Identifiers | None | Minutes (configure rule, deploy) | None (built-in algorithms) | A [S1] |
| Custom Regex/Keywords | None | Minutes (configure rule, deploy) | Manual (update patterns as needed) | A [S1] |
| EDM | Data source + indexing | Hours (data prep + indexing + deploy) | Scheduled (daily/weekly/monthly) | A [S1, S4] |
| IDM | Document collection + indexing | Hours (collection + indexing + deploy) | Scheduled (weekly/monthly) | A [S1, S4] |
| VML | Training data preparation + training | Days (collect training data, train, evaluate) | Periodic (annually or when accuracy degrades) | A [S7] |
| Form Recognition | Form template upload | Minutes (upload + deploy) | On form layout change | A [S1] |
| File Properties | None | Minutes (configure rule, deploy) | None | A [S1] |

---

## API Coverage Summary

| Technology | Profile Creation | Configuration | Index/Train Trigger | List/Query | Evidence |
|-----------|-----------------|---------------|--------------------|-----------|---------|
| Data Identifiers | GAP | GAP | N/A | FULL (CloudSOC: `GET /dataIdentifiers`) | A [API-intelligence] |
| Custom Regex/Keywords | GAP | GAP | N/A | N/A | A [API-intelligence] |
| EDM | GAP | GAP | FULL (`POST /edm/index`, 16.0 RU2+) | GAP | A [API-intelligence] |
| IDM | GAP | GAP | GAP | GAP | A [API-intelligence] |
| VML | GAP | GAP | GAP | GAP | A [API-intelligence] |
| Form Recognition | GAP | GAP | GAP | GAP | A [API-intelligence] |
| File Properties | GAP | GAP | N/A | N/A | A [API-intelligence] |

**Workaround:** Use policy import/export API (DLP 25.1+) to transfer policies containing data definitions between environments. Author data definitions in the console, export the containing policy as XML, store in version control, and import via API. [API-intelligence]

---

*End of data definitions workflow document. 7 technologies documented with configuration screens, field references, and 35+ worked examples. Total gotchas referenced from dedicated gotchas.md.*
