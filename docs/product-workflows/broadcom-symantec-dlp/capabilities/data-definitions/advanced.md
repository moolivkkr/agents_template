# Data Definitions — Advanced Reference
## Broadcom Symantec DLP (Enforce Server, version 16.x/25.x/26.x)

> **Purpose:** Complete field reference, full data identifier catalog, every EDM/IDM/VML option, advanced configuration patterns, and extensive worked examples.
> **Evidence sources:** doc-corpus.md [S1-S28], video-intelligence.md [V1-V45], api-intelligence.md

---

## Table of Contents

1. [Full Data Identifier Catalog](#1-full-data-identifier-catalog)
2. [Data Identifier Configuration — Every Field](#2-data-identifier-configuration--every-field)
3. [Custom Pattern Reference — Regex and Keywords](#3-custom-pattern-reference--regex-and-keywords)
4. [EDM Advanced Configuration](#4-edm-advanced-configuration)
5. [IDM Advanced Configuration](#5-idm-advanced-configuration)
6. [VML Advanced Configuration](#6-vml-advanced-configuration)
7. [Form Recognition Advanced](#7-form-recognition-advanced)
8. [File Properties Advanced](#8-file-properties-advanced)
9. [Cross-Technology Compound Examples](#9-cross-technology-compound-examples)
10. [API-Based Data Definition Management](#10-api-based-data-definition-management)
11. [Regulation-to-Technology Mapping](#11-regulation-to-technology-mapping)
12. [Performance Tuning by Technology](#12-performance-tuning-by-technology)

---

## 1. Full Data Identifier Catalog

### 1.1 Payment Card Industry (PCI DSS)

```
+=========================================================================+
|  PCI Data Identifiers                                                    |
+=========================================================================+
|                                                                          |
|  Category: Payment Card Numbers                                          |
|  +------------------------------------------------------------------+   |
|  | Identifier          | Pattern          | Validator     | Breadth |   |
|  |---------------------|------------------|---------------|---------|   |
|  | Credit Card Number  | 13-19 digits     | Luhn (mod-10) | N/M/W   |   |
|  |   > Visa            | 4xxx (13/16 dig) | Luhn          | N/M/W   |   |
|  |   > Mastercard      | 51-55/2221-2720  | Luhn          | N/M/W   |   |
|  |   > Amex            | 34/37 (15 dig)   | Luhn          | N/M/W   |   |
|  |   > Discover        | 6011/644-649/65  | Luhn          | N/M/W   |   |
|  |   > JCB             | 3528-3589        | Luhn          | N/M/W   |   |
|  |   > UnionPay        | 62 (16-19 dig)   | Luhn          | N/M/W   |   |
|  |   > Diners Club     | 300-305/36/38    | Luhn          | N/M/W   |   |
|  |   > Maestro         | 5018/5020/5038   | Luhn          | N/M/W   |   |
|  +------------------------------------------------------------------+   |
|                                                                          |
|  N=Narrow (strict format, separators required)                           |
|  M=Medium (flexible separators)                                          |
|  W=Wide (any matching digit sequence)                                    |
+=========================================================================+
```

**Luhn Algorithm Detail:**

The Luhn algorithm (modulo 10) validates credit card numbers by:
1. Starting from the rightmost digit, double every second digit
2. If doubling results in a number >9, subtract 9
3. Sum all digits
4. If total modulo 10 equals 0, the number is valid

This validator eliminates ~90% of false positives from random number sequences. [S1, S4, S8]

### 1.2 Personally Identifiable Information (PII) — US

```
+=========================================================================+
|  US PII Data Identifiers                                                 |
+=========================================================================+
|  +------------------------------------------------------------------+   |
|  | Identifier               | Format          | Validator           |   |
|  |--------------------------|-----------------|---------------------|   |
|  | US SSN                   | XXX-XX-XXXX     | Area: 001-899(!666) |   |
|  |                          |                 | Group: 01-99        |   |
|  |                          |                 | Serial: 0001-9999   |   |
|  |--------------------------|-----------------|---------------------|   |
|  | US Driver License        | State-specific  | Per-state format    |   |
|  |   > California           | 1 letter+7 dig  | Letter prefix       |   |
|  |   > New York             | 9 digits        | Checksum            |   |
|  |   > Texas                | 8 digits        | Format only         |   |
|  |   > Florida              | 1 letter+12 dig | Letter prefix       |   |
|  |   > Illinois             | 1 letter+11 dig | Letter prefix       |   |
|  |   > (all 50 states + DC) | Varies          | Per-state           |   |
|  |--------------------------|-----------------|---------------------|   |
|  | US Passport              | 9 alphanumeric  | Format validation   |   |
|  |--------------------------|-----------------|---------------------|   |
|  | US ITIN                  | 9XX-XX-XXXX     | 4th digit: 7 or 8   |   |
|  |--------------------------|-----------------|---------------------|   |
|  | US EIN                   | XX-XXXXXXX      | Campus prefix valid. |   |
|  |--------------------------|-----------------|---------------------|   |
|  | US Voter Registration    | State-specific  | Format only         |   |
|  +------------------------------------------------------------------+   |
+=========================================================================+
```

**SSN Breadth Modes Detail:**

| Breadth | Pattern Matched | Example Matches | Example Non-Matches | False Positive Risk |
|---------|----------------|-----------------|---------------------|---------------------|
| Narrow | XXX-XX-XXXX (dashes required) | 123-45-6789 | 123456789, 123 45 6789 | Very Low |
| Medium | XXX-XX-XXXX or XXX XX XXXX | 123-45-6789, 123 45 6789 | 123456789 | Low |
| Wide | Any 9-digit sequence passing area/group/serial validation | 123-45-6789, 123456789, 123 45 6789 | 999-00-0000 (invalid area) | High (phone numbers, zip+4) |

[S1, S4, S8]

### 1.3 PII — International (by Region)

#### Europe

| Identifier | Country | Format | Validator | Regulation | Evidence |
|-----------|---------|--------|-----------|-----------|----------|
| UK NINO | UK | 2L+6D+1L | Prefix validation (excl. D,F,I,Q,U,V; excl. BG,GB,NK,KN,TN,NT,ZZ) | UK DPA / GDPR | A [S1] |
| UK Passport | UK | 9 digits | Format validation | UK DPA | B [S4] |
| UK NHS Number | UK | 10 digits (3-3-4) | Modulo 11 checksum | GDPR/NHS | B [S4] |
| France INSEE/NIR | France | 13D+2 check | Modulo 97 | GDPR / CNIL | B [S4] |
| France Passport | France | 9 alphanumeric | Format validation | GDPR | B [S4] |
| Germany Personal ID | Germany | 10 alphanumeric | Check digit algorithm | GDPR / BDSG | B [S4] |
| Germany Tax ID (Steuer-IdNr) | Germany | 11 digits | ISO 7064 Mod 11,10 | GDPR / AO | B [S4] |
| Italy Fiscal Code (Codice Fiscale) | Italy | 16 alphanumeric | Check character algorithm | GDPR | B [S4] |
| Spain DNI/NIE | Spain | 8D+1L (DNI) / L+7D+L (NIE) | Check letter (mod 23) | GDPR / LOPD | B [S4] |
| Netherlands BSN | Netherlands | 9 digits | Eleven-test (mod 11) | GDPR / AVG | B [S4] |
| Sweden Personal Number | Sweden | YYYYMMDD-XXXX | Luhn on last 10 digits | GDPR | B [S4] |
| Poland PESEL | Poland | 11 digits | Modulo 10 checksum | GDPR | B [S4] |

#### Asia-Pacific

| Identifier | Country | Format | Validator | Regulation | Evidence |
|-----------|---------|--------|-----------|-----------|----------|
| Japan My Number | Japan | 12 digits | Modulo 11 check digit | APPI | B [S4] |
| South Korea RRN | South Korea | 13D (YYMMDD-G######) | Gender digit + checksum | PIPA | B [S4] |
| India Aadhaar | India | 12 digits | Verhoeff algorithm | IT Act | B [S4] |
| India PAN | India | 5L+4D+1L | Format + check character | IT Act | B [S4] |
| China Resident ID | China | 18 digits | ISO 7064 Mod 11,2 | PIPL | B [S4] |
| Australia TFN | Australia | 8-9 digits | Weighted checksum | Privacy Act | B [S4] |
| Australia Medicare | Australia | 10-11 digits | Check digit | Privacy Act | B [S4] |
| Singapore NRIC | Singapore | 1L+7D+1L | Checksum | PDPA | B [S4] |
| Hong Kong HKID | Hong Kong | 1-2L+6D+(check) | Check digit | PDPO | B [S4] |

#### Americas

| Identifier | Country | Format | Validator | Regulation | Evidence |
|-----------|---------|--------|-----------|-----------|----------|
| Canada SIN | Canada | XXX-XXX-XXX | Luhn algorithm | PIPEDA | A [S1] |
| Canada Driver License | Canada | Province-specific | Per-province format | PIPEDA | B [S4] |
| Brazil CPF | Brazil | XXX.XXX.XXX-XX | 2 check digits (mod 11) | LGPD | B [S4] |
| Brazil CNPJ | Brazil | XX.XXX.XXX/XXXX-XX | 2 check digits | LGPD | B [S4] |
| Mexico CURP | Mexico | 18 alphanumeric | Check digit | LFPDPPP | B [S4] |
| Argentina DNI | Argentina | XX.XXX.XXX | Format only | PDPA | B [S4] |

### 1.4 Financial Identifiers

```
+=========================================================================+
|  Financial Data Identifiers                                              |
+=========================================================================+
|  +------------------------------------------------------------------+   |
|  | Identifier               | Format            | Validator          |   |
|  |--------------------------|-------------------|--------------------|   |
|  | IBAN                     | CC+2check+30 alp  | ISO 13616 (mod 97) |   |
|  |   > Germany (DE)         | DE+2+18 digits    | Mod 97             |   |
|  |   > UK (GB)              | GB+2+18 alnum     | Mod 97             |   |
|  |   > France (FR)          | FR+2+23 alnum     | Mod 97             |   |
|  |   > Switzerland (CH)     | CH+2+17 alnum     | Mod 97             |   |
|  |   > (70+ countries)      | Varies            | Mod 97             |   |
|  |--------------------------|-------------------|--------------------|   |
|  | SWIFT/BIC                | 8 or 11 alnum     | Bank+country code  |   |
|  |--------------------------|-------------------|--------------------|   |
|  | US ABA Routing Number    | 9 digits          | 3-7-1 checksum     |   |
|  |--------------------------|-------------------|--------------------|   |
|  | US Bank Account Number   | 8-17 digits       | Format only        |   |
|  |--------------------------|-------------------|--------------------|   |
|  | CUSIP (Securities)       | 9 alphanumeric    | Check digit        |   |
|  |--------------------------|-------------------|--------------------|   |
|  | ISIN (Securities)        | 2L+9alnum+1check  | Luhn (doubled)     |   |
|  |--------------------------|-------------------|--------------------|   |
|  | SEDOL (UK Securities)    | 7 alphanumeric    | Weighted checksum  |   |
|  +------------------------------------------------------------------+   |
+=========================================================================+
```

[S1, S4]

### 1.5 Healthcare / HIPAA Identifiers

| Identifier | Format | Validator | HIPAA PHI Category | Evidence |
|-----------|--------|-----------|-------------------|----------|
| ICD-9 Code | XXX.XX (3-5 characters) | Code range validation | Diagnosis codes | B [S4] |
| ICD-10 Code | A##.#### (alpha + 2-7 alnum) | Code range validation | Diagnosis codes | B [S4] |
| NDC (National Drug Code) | 10-11 digits (4-4-2 / 5-3-2 / 5-4-1) | Segment format | Medication identifiers | B [S4] |
| DEA Number | 2L+7D | Check digit algorithm (sum of positions 1,3,5 + 2x sum of 2,4,6 = check) | Prescriber identifiers | B [S4] |
| NPI | 10 digits (starts 1/2) | Luhn on 15-digit prefixed number (80840+NPI) | Provider identifiers | B [S4] |
| HICN | Alphanumeric (Medicare) | Prefix validation (1-3 digits + 1-2 alpha suffix) | Insurance identifiers | B [S4] |
| MBI (Medicare Beneficiary ID) | 11 alphanumeric (C-AN-A-AN-A-AN-AN-A-N-A-N) | Position-based format | Insurance identifiers (new) | B [S4] |

### 1.6 GDPR-Specific Identifiers

| Identifier | Scope | Detection Method | Notes | Evidence |
|-----------|-------|-----------------|-------|----------|
| Email Address | Global | Pattern matching (RFC 5322 format) | High FP risk; combine with other identifiers | A [S1] |
| Phone Number (international) | Global | ITU-T E.164 format | Country code + subscriber number | B [S4] |
| IP Address (IPv4/IPv6) | Global | Dotted quad / colon-hex | Context needed to determine sensitivity | B [S4] |
| GPS Coordinates | Global | Decimal degree / DMS format | Rarely used alone; corroborative | B [S4] |
| Genetic Data markers | EU | Specialized patterns | Emerging; consult GDPR Article 9 | E [inferred] |
| Biometric Template Data | EU | Binary patterns | Specialized; requires custom identifier | E [inferred] |

---

## 2. Data Identifier Configuration — Every Field

### 2.1 Rule-Level Configuration

```
+=========================================================================+
|  Detection Rule: Content Matches Data Identifier — Full Options          |
+=========================================================================+
|                                                                          |
|  Data Identifier:  [                              ] [v]                  |
|    System identifiers:                                                   |
|    +-- Payment Cards                                                     |
|    |   +-- Credit Card Number                                            |
|    |   +-- Visa Card                                                     |
|    |   +-- Mastercard                                                    |
|    |   +-- American Express                                              |
|    |   +-- Discover                                                      |
|    |   +-- JCB                                                           |
|    |   +-- UnionPay                                                      |
|    |   +-- Diners Club                                                   |
|    +-- US PII                                                            |
|    |   +-- US Social Security Number                                     |
|    |   +-- US Driver License                                             |
|    |   +-- US Passport Number                                            |
|    |   +-- US ITIN                                                       |
|    |   +-- US EIN                                                        |
|    +-- International PII                                                 |
|    |   +-- UK National Insurance Number                                  |
|    |   +-- Canada Social Insurance Number                                |
|    |   +-- France INSEE/NIR                                              |
|    |   +-- Germany Personal ID                                           |
|    |   +-- (region-specific identifiers...)                              |
|    +-- Financial                                                         |
|    |   +-- IBAN                                                          |
|    |   +-- SWIFT/BIC                                                     |
|    |   +-- US ABA Routing Number                                         |
|    +-- Healthcare                                                        |
|    |   +-- ICD-9 / ICD-10                                                |
|    |   +-- NDC                                                           |
|    |   +-- DEA Number                                                    |
|    |   +-- NPI                                                           |
|    +-- Custom                                                            |
|        +-- (user-defined identifiers)                                    |
|                                                                          |
|  Minimum Matches:  [        ]    (integer 1-999)                         |
|                                                                          |
|  Match Counting:                                                         |
|    (*) Count unique values only                                          |
|        Example: "123-45-6789" appearing 5 times = 1 match               |
|    ( ) Count all matches                                                 |
|        Example: "123-45-6789" appearing 5 times = 5 matches             |
|                                                                          |
|  Check for Existence Only:  [ ]                                          |
|    When checked: triggers on any match, ignores minimum threshold        |
|    When unchecked: requires minimum match count to be met                |
|                                                                          |
|  Breadth:                                                                |
|    ( ) Narrow   -- Strict format (separators required)                   |
|                    Fewest false positives                                 |
|                    May miss non-standard formatting                       |
|    (*) Medium   -- Flexible separators (dash, space, none)               |
|                    Balanced accuracy                                      |
|                    Recommended starting point                             |
|    ( ) Wide     -- Any matching character sequence                        |
|                    Catches all variations                                 |
|                    Most false positives                                   |
|                                                                          |
|  Look In:                                                                |
|    [x] Message Body        -- Email body, document text                  |
|    [x] Message Subject     -- Email subject line                         |
|    [x] Attachments         -- File attachments (all supported types)     |
|    [ ] Envelope            -- Sender/recipient headers                   |
|    [ ] Custom Headers      -- X-headers (DLP 16.0+)                      |
|                                                                          |
|  Severity:                                                               |
|    ( ) 1 - High            -- Critical data exposure                     |
|    (*) 2 - Medium          -- Significant but non-critical               |
|    ( ) 3 - Low             -- Minor policy violation                     |
|    ( ) 4 - Informational   -- Monitoring only                            |
|                                                                          |
+=========================================================================+
```

### 2.2 Severity Assignment Matrix

| Severity | When to Use | Response Action Typical | Evidence |
|----------|-----------|------------------------|----------|
| 1 - High | SSNs, credit cards, health records, trade secrets | Block + Notify + Syslog | A [S1, S4] |
| 2 - Medium | IBAN, passport, internal project codes | Notify + Syslog | A [S1, S4] |
| 3 - Low | File type violations, single keyword matches | Syslog only | A [S1, S4] |
| 4 - Informational | Monitoring policies, shadow IT tracking | Log only (no notification) | A [S1, S4] |

### 2.3 Breadth Mode Impact Analysis

| Identifier | Narrow FP Rate | Medium FP Rate | Wide FP Rate | Recommendation |
|-----------|---------------|----------------|-------------|----------------|
| Credit Card | <0.1% | ~1% | ~5% | Start Medium (Luhn catches most FPs) |
| US SSN | <0.5% | ~2% | ~15% | Start Narrow (no Luhn; area check is weaker) |
| IBAN | <0.1% | ~0.5% | ~2% | Start Medium (mod-97 is strong validator) |
| US Driver License | ~1% | ~3% | ~10% | Start Narrow (state formats overlap with other patterns) |
| UK NINO | <0.5% | ~1% | ~5% | Start Narrow (prefix validation is effective) |

[S1, S8, tribal knowledge]

---

## 3. Custom Pattern Reference — Regex and Keywords

### 3.1 Regex Pattern Library

**Proven patterns for common custom identifiers:**

| Use Case | Pattern | Notes | FP Risk |
|----------|---------|-------|---------|
| US Phone Number | `\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}` | Matches (555) 123-4567, 555-123-4567, 5551234567 | Medium |
| Email Address | `[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}` | RFC 5322 simplified | Low |
| IPv4 Address | `\b(?:(?:25[0-5]\|2[0-4]\d\|[01]?\d\d?)\.){3}(?:25[0-5]\|2[0-4]\d\|[01]?\d\d?)\b` | Validates octet ranges | Low |
| Date of Birth | `\b(?:0[1-9]\|1[012])[/-](?:0[1-9]\|[12]\d\|3[01])[/-](?:19\|20)\d{2}\b` | MM/DD/YYYY or MM-DD-YYYY | Medium |
| Internal Employee ID | `EMP-\d{6}` | Organization-specific | Low (if format is unique) |
| Internal Project Code | `PROJ-[A-Z]{2,4}-\d{4,8}` | Organization-specific | Low |
| AWS Access Key | `AKIA[0-9A-Z]{16}` | AWS IAM access key ID | Very Low |
| AWS Secret Key | `[A-Za-z0-9/+=]{40}` | 40-char base64 (combine with keyword "secret") | High (standalone) |
| GitHub Personal Token | `ghp_[A-Za-z0-9]{36}` | GitHub PAT format | Very Low |
| Slack Webhook | `https://hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]+` | Slack incoming webhook URL | Very Low |
| API Key (generic) | `[A-Za-z0-9]{32,64}` | Very broad; MUST combine with keyword proximity | Very High (standalone) |
| Bitcoin Address | `[13][a-km-zA-HJ-NP-Z1-9]{25,34}` | Legacy Bitcoin addresses | Low |
| Ethereum Address | `0x[a-fA-F0-9]{40}` | Ethereum hex address | Low |

### 3.2 Keyword Proximity Patterns

```
+=========================================================================+
|  Keyword + Proximity Configuration                                       |
+=========================================================================+
|                                                                          |
|  Effective pattern: "KEYWORD_A within N characters of KEYWORD_B"         |
|                                                                          |
|  Example 1: SSN proximity                                                |
|    Keywords: "social security", "SSN", "social security number"          |
|    Proximity: 50 characters                                              |
|    Combined with: US SSN data identifier                                 |
|    WHY: Reduces FPs by requiring SSN-like numbers to appear near SSN     |
|         context words                                                    |
|                                                                          |
|  Example 2: Salary information                                           |
|    Keywords: "salary", "compensation", "base pay", "annual wage"         |
|    Proximity: 100 characters                                             |
|    Combined with: currency pattern ($\d{2,3},?\d{3})                     |
|    WHY: Dollar amounts alone are everywhere. Dollar amounts near         |
|         salary keywords = compensation data                              |
|                                                                          |
|  Example 3: Medical diagnosis                                            |
|    Keywords: "diagnosis", "diagnosed with", "ICD", "condition"           |
|    Proximity: 75 characters                                              |
|    Combined with: ICD-10 data identifier                                 |
|    WHY: ICD codes in medical contexts are PHI. ICD codes in billing      |
|         department communications are routine business                    |
|                                                                          |
+=========================================================================+
```

### 3.3 Dictionary Import Configuration

```
+=========================================================================+
|  Dictionary Import (for Keyword Rules)                                   |
+=========================================================================+
|                                                                          |
|  Import Source:  (*) CSV file   ( ) Text file (one word per line)        |
|                                                                          |
|  File: [medical_terms_dictionary.csv        ] [Browse...]                |
|                                                                          |
|  Import Options:                                                         |
|    [x] Case insensitive matching                                         |
|    [x] Match whole words only                                            |
|    [ ] Enable stemming (match word forms)                                |
|                                                                          |
|  Threshold:  [3  ]  (minimum number of dictionary words to trigger)      |
|                                                                          |
|  Preview:                                                                |
|    Row 1: metformin                                                      |
|    Row 2: atorvastatin                                                   |
|    Row 3: lisinopril                                                     |
|    ...                                                                   |
|    Total entries: 2,847                                                  |
|                                                                          |
|                                               [Cancel]  [Import]         |
+=========================================================================+
```

---

## 4. EDM Advanced Configuration

### 4.1 Data Source Connectivity Options

```
+=========================================================================+
|  EDM Data Source — Advanced                                              |
+=========================================================================+
|                                                                          |
|  Source Type:                                                             |
|    (*) Delimited File (CSV/TSV/Pipe)                                     |
|    ( ) Oracle Database                                                   |
|    ( ) SQL Server                                                        |
|    ( ) MySQL / MariaDB                                                   |
|    ( ) LDAP / Active Directory                                           |
|                                                                          |
|  --- Delimited File Options ---                                          |
|  File Path:  [\\share\exports\hr_data.csv                   ]           |
|  Delimiter:  (*) Comma  ( ) Tab  ( ) Pipe  ( ) Custom: [;  ]            |
|  Text Qualifier: (*) " (double quote)  ( ) ' (single)  ( ) None         |
|  Character Encoding: [UTF-8        v]                                    |
|  Header Row:  (*) Yes  ( ) No                                            |
|  Skip Rows: [0   ] (skip first N data rows)                             |
|                                                                          |
|  --- Database Options ---                                                |
|  JDBC URL: [jdbc:oracle:thin:@dbhost:1521:HRDB             ]            |
|  Username: [dlp_reader                                      ]            |
|  Password: [********                                        ]            |
|  SQL Query: [SELECT first_name, last_name, ssn, dob, email  ]           |
|             [FROM employees WHERE status = 'ACTIVE'          ]           |
|                                                                          |
|  --- LDAP Options ---                                                    |
|  LDAP URL: [ldap://dc01.corp.local:389                      ]           |
|  Base DN:  [OU=Employees,DC=corp,DC=local                   ]           |
|  Filter:   [(objectClass=person)                             ]           |
|  Attributes: [cn, sAMAccountName, employeeID, mail          ]           |
|                                                                          |
+=========================================================================+
```

### 4.2 Column Mapping — Advanced Field Types

| Field Type | Use For | Key-Eligible | Typical Examples | Evidence |
|-----------|---------|-------------|-----------------|----------|
| SSN | US Social Security Number | Yes (recommended) | 123-45-6789 | A [S1, S4] |
| Credit Card Number | Payment card numbers | Yes | 4111-1111-1111-1111 | A [S1, S4] |
| First Name | Person's given name | No (too common) | John, Maria | A [S1, S4] |
| Last Name | Person's surname | No (too common) | Smith, Garcia | A [S1, S4] |
| Email Address | Contact email | Sometimes (if unique domain) | john@company.com | A [S1, S4] |
| Phone Number | Contact phone | Sometimes | (555) 123-4567 | A [S1, S4] |
| Date of Birth | Birth date | No (shared values) | 01/15/1985 | A [S1, S4] |
| Address | Street address | No (too many words) | 123 Main St | A [S1, S4] |
| City | City name | No (too common) | New York | A [S1, S4] |
| State/Province | State code | No (too common) | CA, NY | A [S1, S4] |
| Zip/Postal Code | Postal code | No (too common) | 90210 | A [S1, S4] |
| Country | Country name/code | No (too common) | US, United States | A [S1, S4] |
| Custom ID | Organization-specific ID | Yes (recommended) | EMP-001234, ACCT-78901 | A [S1, S4] |
| Custom Text | Any text field | Depends on uniqueness | Project code, department | B [S4] |
| Account Number | Financial account | Yes (recommended) | 1234567890 | A [S1, S4] |
| Driver License | DL number | Yes | D1234567 | A [S1, S4] |
| Passport | Passport number | Yes | AB1234567 | A [S1, S4] |

### 4.3 Multi-Field Matching Logic

```
+=========================================================================+
|  EDM Multi-Field Matching -- Examples                                    |
+=========================================================================+
|                                                                          |
|  6-Column Profile: [Name, SSN(K), DOB, Email, Phone, EmpID(K)]          |
|                                                                          |
|  "Match 2 of 6, at least 1 KEY"                                         |
|    MATCH:   SSN + Name       (KEY + corroborative)                       |
|    MATCH:   SSN + Email      (KEY + corroborative)                       |
|    MATCH:   EmpID + DOB      (KEY + corroborative)                       |
|    NO MATCH: Name + DOB      (no KEY field present)                      |
|    NO MATCH: Name + Email    (no KEY field present)                      |
|    NO MATCH: SSN alone       (only 1 of 2 required fields)              |
|                                                                          |
|  "Match 3 of 6, at least 1 KEY"                                         |
|    MATCH:   SSN + Name + DOB    (KEY + 2 corroborative)                  |
|    MATCH:   EmpID + Name + Email (KEY + 2 corroborative)                 |
|    NO MATCH: SSN + Name         (only 2 of 3 required)                   |
|    NO MATCH: Name + DOB + Email (no KEY field)                           |
|                                                                          |
|  GOTCHA: "2 of N" with corroborative fields like Name + Email           |
|          matches ANY person whose name and email appear together.         |
|          This could be in a signature block, not a data breach.          |
|          ALWAYS require at least 1 KEY field.                            |
|                                                                          |
+=========================================================================+
```

### 4.4 EDM Index Management

```
+=========================================================================+
|  Manage > Data Profiles > Exact Data Profiles > [profile] > Index Status |
+=========================================================================+
|                                                                          |
|  Profile: Employee PII Protection                                        |
|                                                                          |
|  Index Status:                                                           |
|    Current Index:  v2024.11.17 (indexed: 2024-11-17 02:15 AM)           |
|    Records:        48,723                                                |
|    Fields:         6                                                     |
|    Index Size:     1.2 GB                                                |
|    Error Rate:     0.3% (within 5% threshold)                            |
|    Errors:         147 rows skipped (empty SSN field)                    |
|                                                                          |
|  Distribution Status:                                                    |
|    Detection Server 1 (Network Prevent Email):  CURRENT                  |
|    Detection Server 2 (Network Prevent Web):    CURRENT                  |
|    Detection Server 3 (Endpoint Prevent):       CURRENT                  |
|    Detection Server 4 (Network Discover):       CURRENT                  |
|                                                                          |
|  Schedule:                                                               |
|    Next Index: 2024-11-24 02:00 AM (Sunday)                              |
|    Frequency:  Weekly                                                    |
|                                                                          |
|  Actions:                                                                |
|    [Re-Index Now]  [Edit Schedule]  [View Errors]  [Export Profile]      |
|                                                                          |
+=========================================================================+
```

### 4.5 Remote EDM Indexer Configuration

| Field | Type | Required | Default | Options | Evidence |
|-------|------|----------|---------|---------|----------|
| Indexer Location | Text (hostname/IP) | Yes | -- | FQDN of Remote Indexer machine | A [S1, S4] |
| Port | Integer | Yes | 443 | Custom port | A [S1] |
| Authentication | Certificate | Yes | -- | TLS client certificate | A [S1] |
| Index Output Path | Text | Yes | -- | Local path on indexer machine for index files | A [S1] |
| Upload to Enforce | Checkbox | Yes | Checked | Auto-upload index to Enforce Server after creation | A [S1] |
| Compression | Checkbox | No | Enabled | Compress index during transfer | B [S4] |

**When to use Remote Indexer:**
- Data source exceeds 1M rows
- Indexing causes Enforce Server performance degradation
- Data source is in a network segment the Enforce Server cannot reach directly
- CloudSOC/CASB deployment requires cloud-compatible index format

[S1, S4]

---

## 5. IDM Advanced Configuration

### 5.1 Matching Mode Deep Dive

| Mode | Algorithm | Detects | Performance Impact | Best For | Evidence |
|------|-----------|---------|-------------------|----------|----------|
| Exact (Binary Stamp) | Full binary hash comparison | Identical file copies only | Very Low | Binary files (CAD, images, executables) | A [S1, S4] |
| Partial (Rolling Hash) | Content-level fingerprint with sliding window | Fragments, copy-paste, derived content | Medium | Text documents (Office, PDF, source code) | A [S1, S4] |
| Both | Both algorithms applied | All of the above | Medium-High | Mixed document collections | A [S1, S4] |

### 5.2 Partial Matching Threshold Guide

| Threshold | Documents Caught | False Positive Risk | Recommended For | Evidence |
|-----------|-----------------|---------------------|----------------|----------|
| 1-5% | 1-2 sentences matching | Very High | Ultra-sensitive documents only (nuclear codes) | B [S4] |
| 5-10% | 1-2 paragraphs matching | High | Legal contracts, M&A term sheets | A [S1, S4] |
| 10-20% | Multiple paragraphs or pages | Medium | Source code, design docs, general confidential docs | A [S1, S4] |
| 20-40% | Major sections of document | Low | Large reports, manuals, multi-chapter documents | B [S4] |
| 40-60% | Half or more of document | Very Low | Final documents where near-complete copies are the threat | B [S4] |
| 60-100% | Nearly complete copies | Negligible | When only full document theft matters | B [S4] |

### 5.3 Document Group Management

```
+=========================================================================+
|  IDM Document Groups                                                     |
+=========================================================================+
|                                                                          |
|  Groups organize documents by sensitivity, department, or type.          |
|  Policy rules can target specific groups within a profile.               |
|                                                                          |
|  +------------------------------------------------------------------+   |
|  | Group Name              | Documents | Last Updated   | Profile    |   |
|  |-------------------------|-----------|----------------|------------|   |
|  | M&A Confidential        | 47        | 2024-11-15     | Legal Docs |   |
|  | Board Materials          | 112       | 2024-11-01     | Legal Docs |   |
|  | Engineering IP           | 3,450     | 2024-11-10     | Eng Docs   |   |
|  | Financial Reports        | 298       | 2024-10-28     | Finance    |   |
|  | HR Policies (non-sens.)  | 85        | 2024-09-15     | HR Docs    |   |
|  +------------------------------------------------------------------+   |
|                                                                          |
+=========================================================================+
```

### 5.4 CloudSOC IDM (Remote Indexer Workflow)

For cloud-based IDM detection via CloudSOC:

1. Install Remote Indexer Tool on a machine with access to source documents
2. Run Remote Indexer to create cloud-compatible index file (`.ridx`)
3. Upload `.ridx` file to CloudSOC (Protect > DLP Profiles > IDM tab)
4. Add IDM index to a DLP Profile in CloudSOC
5. CloudSOC policies reference the cloud IDM profile

```
Source Documents --> Remote Indexer --> .ridx file --> CloudSOC Upload --> Cloud DLP Profile
```

[S1, S24]

---

## 6. VML Advanced Configuration

### 6.1 Training Data Quality Matrix

| Factor | Good Training Data | Poor Training Data | Impact on Accuracy |
|--------|-------------------|-------------------|-------------------|
| Diversity | Documents from multiple authors/departments | All from one author | -15-25% accuracy |
| Volume | 250+ per set | <50 per set | -10-20% accuracy |
| Balance | Equal positive and negative count | 500 positive, 20 negative | -10-15% accuracy |
| Negative relevance | "Near-miss" documents from same domain | Random unrelated documents | -15-20% accuracy |
| Recency | Documents from recent 2-3 years | Documents from 10+ years ago | -5-10% (varies) |
| Format consistency | All text-based, extractable | Mix of scanned images and text | -5-10% accuracy |

[S7, V20]

### 6.2 Accuracy Interpretation

| Score | Interpretation | Action | Evidence |
|-------|---------------|--------|----------|
| 95-100% | Excellent (may be overfitting) | Verify with held-out test set; may need more diverse negative examples | A [S7] |
| 90-95% | Very Good | Accept for production use | A [S7] |
| 85-90% | Good | Acceptable for most use cases; consider adding more training data | A [S7] |
| 80-85% | Adequate | Supplement with keyword/regex rules for edge cases | A [S7] |
| 75-80% | Marginal | Add diverse training data, retrain before production | A [S7] |
| <75% | Poor | Insufficient or poor training data; rebuild training sets | A [S7] |

### 6.3 VML Retraining Strategy

```
+=========================================================================+
|  VML Retraining Decision Tree                                            |
+=========================================================================+
|                                                                          |
|  1. Check false negative rate quarterly                                  |
|     |                                                                    |
|     +-- FN rate < 5%  --> No action needed                               |
|     |                                                                    |
|     +-- FN rate 5-15% --> Add 20-50 recent documents to positive set     |
|     |                     and retrain                                     |
|     |                                                                    |
|     +-- FN rate > 15% --> Full retraining with fresh training sets        |
|                           (250+ documents per set)                       |
|                                                                          |
|  2. Check false positive rate quarterly                                  |
|     |                                                                    |
|     +-- FP rate < 3%  --> No action needed                               |
|     |                                                                    |
|     +-- FP rate 3-10% --> Add false-positive examples to negative set    |
|     |                     and retrain                                     |
|     |                                                                    |
|     +-- FP rate > 10% --> Investigate root cause:                        |
|                           - Training data too similar?                    |
|                           - Negative set not representative?              |
|                           - Content patterns changed?                     |
|                           Full retraining recommended                     |
|                                                                          |
+=========================================================================+
```

---

## 7. Form Recognition Advanced

### 7.1 Supported Form Types

| Form Category | Examples | Template Quality | Detection Accuracy | Evidence |
|--------------|---------|-----------------|-------------------|----------|
| Tax Forms | W-2, W-9, 1099, 1040 | High (standardized) | 95%+ | A [S1, V21] |
| Medical Forms | Patient intake, CMS-1500, UB-04 | Medium-High | 90-95% | B [V21] |
| Insurance Forms | Application, claim, coverage summary | Medium | 85-92% | B [V21] |
| Financial Forms | Account opening, wire transfer, KYC | Medium | 85-90% | E [inferred] |
| Government Forms | Passport application, visa, birth cert. | High (standardized) | 93-97% | B [S4] |
| HR Forms | I-9, W-4, benefits enrollment | High (standardized) | 95%+ | B [S4] |

### 7.2 Template Registration Best Practices

| Factor | Best Practice | Impact |
|--------|--------------|--------|
| Resolution | Scan blank form at 300 DPI minimum | <150 DPI causes recognition failures |
| Orientation | Portrait, standard orientation | Rotated scans reduce accuracy by 10-20% |
| Color vs B&W | Color preferred; B&W acceptable | Color improves field boundary detection |
| Blank vs Filled | Register BLANK form as template | Filled forms include variable data that confuses template matching |
| Multiple pages | Register each page as separate template | Multi-page forms need per-page registration |
| Version tracking | Re-register when form layout changes | Stale templates miss updated form versions |

---

## 8. File Properties Advanced

### 8.1 True File Type Detection — Full Category List

```
+=========================================================================+
|  File Type Categories (330+ types by binary signature)                   |
+=========================================================================+
|                                                                          |
|  +-- Documents                                                           |
|  |   +-- Microsoft Office (DOC, DOCX, XLS, XLSX, PPT, PPTX, etc.)      |
|  |   +-- OpenDocument (ODT, ODS, ODP)                                    |
|  |   +-- PDF                                                             |
|  |   +-- Rich Text Format (RTF)                                          |
|  |   +-- Plain Text (TXT, CSV, TSV, LOG)                                 |
|  |   +-- XML, HTML, JSON                                                 |
|  |                                                                       |
|  +-- Databases                                                           |
|  |   +-- Microsoft Access (MDB, ACCDB)                                   |
|  |   +-- SQLite                                                          |
|  |   +-- dBASE (DBF)                                                     |
|  |   +-- Lotus Notes (NSF)                                               |
|  |                                                                       |
|  +-- Archives                                                            |
|  |   +-- ZIP, RAR, 7Z, TAR, GZ, BZ2                                     |
|  |   +-- CAB, ISO, DMG                                                   |
|  |   +-- Password-protected archives (detectable but not inspectable)    |
|  |                                                                       |
|  +-- Images                                                              |
|  |   +-- JPEG, PNG, GIF, BMP, TIFF, WEBP                                |
|  |   +-- RAW formats (CR2, NEF, ARW)                                     |
|  |   +-- SVG, EPS, AI                                                    |
|  |                                                                       |
|  +-- Audio/Video                                                         |
|  |   +-- MP3, WAV, AAC, FLAC, OGG                                       |
|  |   +-- MP4, AVI, MKV, MOV, WMV                                        |
|  |                                                                       |
|  +-- Executables                                                         |
|  |   +-- PE (EXE, DLL, SYS, OCX)                                        |
|  |   +-- MSI, MSP                                                        |
|  |   +-- ELF (Linux executables)                                         |
|  |   +-- Mach-O (macOS executables)                                      |
|  |   +-- JAR (Java archives)                                             |
|  |                                                                       |
|  +-- Scripts                                                             |
|  |   +-- BAT, CMD, PS1, VBS, JS                                         |
|  |   +-- SH, PY, RB, PL                                                 |
|  |                                                                       |
|  +-- Engineering/CAD                                                     |
|  |   +-- AutoCAD (DWG, DXF)                                              |
|  |   +-- SolidWorks (SLDPRT, SLDASM, SLDDRW)                            |
|  |   +-- STEP, IGES, STL                                                 |
|  |   +-- Revit (RVT)                                                     |
|  |   +-- CATIA, Pro/E                                                    |
|  |                                                                       |
|  +-- Email                                                               |
|  |   +-- MSG (Outlook), EML, PST, OST, MBOX                             |
|  |                                                                       |
|  +-- Certificates & Keys                                                 |
|  |   +-- PEM, CER, CRT, PFX, P12, KEY                                   |
|  |                                                                       |
|  +-- Source Code (by extension, not binary sig)                          |
|      +-- Java, C/C++, Python, Go, JavaScript, TypeScript, etc.          |
|                                                                          |
+=========================================================================+
```

**Key insight:** File type detection uses binary signatures (magic bytes at the start of the file), NOT file extensions. Renaming `data.xlsx` to `data.txt` does NOT bypass detection. The binary signature reveals the true file type. [S1, S4]

### 8.2 Custom Document Properties

| Property Source | Property Types | How Accessed | Evidence |
|----------------|---------------|-------------|----------|
| Microsoft Office | Author, Company, Title, Subject, Keywords, Comments, Category, Manager, Custom Properties | OLE/OOXML metadata | A [S1, S4] |
| PDF | Author, Creator, Producer, Title, Subject, Keywords, Custom metadata | PDF metadata dictionary | A [S1, S4] |
| Image EXIF | Camera model, GPS coordinates, date taken, software | EXIF/IPTC/XMP metadata | B [S4] |
| Email | X-headers, Message-ID, custom headers | MIME headers | A [S1, S4] |

---

## 9. Cross-Technology Compound Examples

### Example 1: HIPAA Full Coverage (EDM + VML + Data Identifiers)

```
Policy: HIPAA-Comprehensive-PHI-Protection
  |
  +-- Rule 1: Patient Record Detection (EDM)
  |   Type: Content Matches Exact Data
  |   Profile: Patient Records (500K patients)
  |   Match: 2 of 7 fields, 1 KEY required
  |   Severity: 1 - High
  |
  +-- Rule 2: Clinical Note Classification (VML)
  |   Type: Content Matches VML Profile
  |   Profile: Clinical Notes Classifier (92% accuracy)
  |   Severity: 2 - Medium
  |
  +-- Rule 3: Healthcare ID Detection (Data Identifier)
  |   Type: Content Matches Data Identifier
  |   Identifiers: DEA Number + NPI (compound: both must match)
  |   Minimum Matches: 1 each
  |   Severity: 2 - Medium
  |
  +-- Rule 4: Medical Form Detection (Form Recognition)
  |   Type: Content Matches Form
  |   Forms: CMS-1500, Patient Intake, HIPAA Authorization
  |   Severity: 1 - High
```

### Example 2: PCI + SOX Financial (EDM + Data Identifiers + File Properties)

```
Policy: Financial-Data-Complete-Protection
  |
  +-- Rule 1: Credit Card Numbers (Data Identifier)
  |   Type: Content Matches Data Identifier
  |   Identifier: Credit Card Number
  |   Breadth: Medium
  |   Minimum: 1
  |   Severity: 1 - High
  |
  +-- Rule 2: Customer Account Data (EDM)
  |   Type: Content Matches Exact Data
  |   Profile: Customer Financial Records (2M customers)
  |   Match: 2 of 6, 1 KEY (Account Number)
  |   Severity: 1 - High
  |
  +-- Rule 3: Database File Exfiltration (File Properties)
  |   Type: File Property Match
  |   File Types: MDB, ACCDB, SQLite, SQL
  |   Severity: 1 - High
  |
  +-- Rule 4: Bulk Spreadsheet Export (Compound)
  |   Conditions (ALL must match):
  |     1. File Type: XLS, XLSX, CSV
  |     2. Data Identifier: Credit Card Number >= 10 unique
  |   Severity: 1 - High
```

### Example 3: IP Protection (IDM + VML + Keywords + File Properties)

```
Policy: Intellectual-Property-Protection
  |
  +-- Rule 1: Source Code Fingerprints (IDM)
  |   Type: Content Matches Indexed Documents
  |   Profile: Core IP Source Code (10,000 files)
  |   Partial Match: 15%
  |   Endpoint IDM: Enabled
  |   Severity: 1 - High
  |
  +-- Rule 2: Engineering Doc Classification (VML)
  |   Type: Content Matches VML Profile
  |   Profile: Engineering Design Specs (88% accuracy)
  |   Severity: 2 - Medium
  |
  +-- Rule 3: Project Code Name (Keywords)
  |   Type: Content Matches Keyword
  |   Keywords: "Project Orion", "Phase 3 Design", "Gen4 Architecture"
  |   Case sensitive: Yes
  |   Severity: 2 - Medium
  |
  +-- Rule 4: CAD/Design Files (File Properties)
  |   Type: File Property Match
  |   File Types: DWG, DXF, SLDPRT, STEP, IGES, STL
  |   Severity: 2 - Medium
```

---

## 10. API-Based Data Definition Management

### 10.1 CloudSOC Data Identifier API

```
# List all available data identifiers
GET /api/clouddlp/protect/public/dataIdentifiers

Response:
{
  "dataIdentifiers": [
    {
      "id": "credit_card_number",
      "name": "Credit Card Number",
      "category": "PCI",
      "builtIn": true,
      "description": "Detects credit card numbers with Luhn validation"
    },
    {
      "id": "us_ssn",
      "name": "US Social Security Number",
      "category": "PII",
      "builtIn": true,
      "description": "Detects US SSNs with area/group/serial validation"
    }
    ...
  ]
}
```

### 10.2 EDM Index Trigger API

```
# Trigger EDM re-indexing
POST /ProtectManager/webservices/v2/edm/index

Authorization: Basic <base64(username:password)>
Content-Type: application/json

{
  "profileId": 12345,
  "fullReindex": true
}

Response:
{
  "status": "INDEXING_STARTED",
  "profileId": 12345,
  "estimatedCompletion": "2024-11-17T02:45:00Z"
}
```

Available since DLP 16.0 RU2. [API-intelligence]

### 10.3 Policy Import/Export for Data Definitions

```
# Export policy containing data definitions
POST /ProtectManager/webservices/v2/policies/export

{
  "policyIds": [101, 102, 103],
  "includeDataProfiles": true,
  "includeResponseRules": true
}

Response: XML document containing complete policy definition
```

**Important:** This exports the policy XML, which includes references to data profiles (EDM/IDM/VML). The data profiles themselves (and their indexed data) are NOT exported. Profiles must exist on the target environment before importing the policy. [API-intelligence]

### 10.4 API Coverage Summary for Data Definitions

| Operation | On-Prem API | CloudSOC API | Evidence |
|-----------|-----------|-------------|---------|
| List data identifiers | GAP | FULL (`GET /dataIdentifiers`) | A [API-intelligence] |
| Create custom identifier | GAP | PARTIAL (within profile creation) | A [API-intelligence] |
| Create EDM profile | GAP | GAP | A [API-intelligence] |
| Trigger EDM indexing | FULL (`POST /edm/index`, 16.0 RU2+) | GAP | A [API-intelligence] |
| Create IDM profile | GAP | GAP (Remote Indexer tool) | A [API-intelligence] |
| Create VML profile | GAP | GAP | A [API-intelligence] |
| Export policy with data defs | FULL (25.1+) | N/A | A [API-intelligence] |
| Import policy with data defs | FULL (25.1+) | N/A | A [API-intelligence] |

---

## 11. Regulation-to-Technology Mapping

### 11.1 Which Technologies to Use for Each Regulation

| Regulation | Primary Technology | Secondary Technology | Tertiary | Evidence |
|-----------|-------------------|---------------------|----------|----------|
| PCI DSS | Data Identifiers (CC numbers) | EDM (customer cardholder data) | File Properties (database files) | A [S1, S4] |
| HIPAA | EDM (patient records) | VML (clinical notes) | Data Identifiers (DEA, NPI) + Form Recognition | A [S1, S4, S7] |
| GDPR | Data Identifiers (national IDs per country) | EDM (customer databases) | Keywords (consent, processing) | A [S1, S4] |
| SOX | VML (financial reports) | EDM (financial records) | Keywords (insider, forecast, earnings) | A [S1, S7] |
| GLBA | EDM (customer financial records) | Data Identifiers (account numbers) | File Properties (database files) | A [S1, S4] |
| FERPA | EDM (student records) | Data Identifiers (SSN, student ID) | Keywords (transcript, grades, GPA) | B [S4] |
| ITAR/EAR | IDM (controlled technical data) | VML (engineering docs) | File Properties (CAD files) | B [S4] |
| CCPA | Data Identifiers (CA-specific PII) | EDM (consumer databases) | Keywords (consumer, personal info) | B [S4] |
| PIPEDA | Data Identifiers (Canada SIN, DL) | EDM (customer records) | Keywords (personal information) | A [S1] |

### 11.2 Pre-Built Policy Templates by Regulation

| Template Name | Detection Technologies Used | Data Identifiers Included | Evidence |
|--------------|---------------------------|--------------------------|----------|
| PCI DSS - Credit Card Numbers | Data Identifiers | Credit Card Number (all brands) | A [S1, S4] |
| PCI DSS - All | Data Identifiers, Keywords | CC, ABA Routing, Account Number | A [S1, S4] |
| HIPAA (Including PHI) | Data Identifiers, Keywords | SSN, DEA, NPI, NDC, ICD codes | A [S1, S4] |
| GDPR - Personal Data | Data Identifiers, Keywords | EU national IDs (multi-country) | A [S1, S4] |
| SOX Compliance | Keywords, Data Identifiers | Financial terms + account numbers | A [S1, S4] |
| GLBA | Data Identifiers, Keywords | SSN, CC, ABA, account numbers | A [S1, S4] |
| UK DPA | Data Identifiers | UK NINO, UK Passport, NHS Number | A [S1, S4] |
| Canada PIPEDA | Data Identifiers | Canada SIN, Driver License | A [S1] |
| California CCPA | Data Identifiers, Keywords | SSN, DL, financial identifiers | B [S4] |

---

## 12. Performance Tuning by Technology

### 12.1 Detection Latency by Technology

| Technology | Typical Latency (per message) | Factors | Evidence |
|-----------|------------------------------|---------|----------|
| Data Identifiers | <100ms | Pattern complexity, message size | A [S1] |
| Keywords | <50ms | Number of keywords, proximity enabled | A [S1] |
| Regular Expressions | 50-500ms | Regex complexity, backtracking, message size | B [S8] |
| EDM | 100-500ms | Index size, number of fields, message size | A [S1, S4] |
| IDM (Exact) | <200ms | Index size | A [S1, S4] |
| IDM (Partial) | 200ms-2s | Index size, threshold, message size | A [S1, S4] |
| VML | 100-500ms | Model complexity, document size | A [S7] |
| Form Recognition | 500ms-3s | Image resolution, OCR required | B [V21] |
| File Properties | <10ms | Metadata read only | A [S1] |

### 12.2 Resource Consumption by Technology

| Technology | CPU Impact | Memory Impact | Storage Impact | Evidence |
|-----------|-----------|---------------|---------------|----------|
| Data Identifiers | Low | Low | None | A [S1] |
| Keywords | Very Low | Low (dictionary in memory) | None | A [S1] |
| Regular Expressions | Medium (complex patterns) | Low | None | B [S8] |
| EDM | Medium | High (index loaded in memory) | High (index files: 1-20+ GB) | A [S1, S4] |
| IDM | Medium | High (fingerprints in memory) | High (fingerprint DB) | A [S1, S4] |
| VML | Medium | Medium (model in memory) | Low (model files: 10-100 MB) | A [S7] |
| Form Recognition + OCR | High | High | Medium (template images) | B [V21] |
| File Properties | Very Low | Very Low | None | A [S1] |

### 12.3 Optimization Recommendations

| Scenario | Recommendation | Impact | Evidence |
|----------|---------------|--------|----------|
| EDM index >5M rows | Use Remote EDM Indexer | Prevents Enforce Server degradation during indexing | A [S1, S4] |
| Complex regex causing latency | Simplify regex; use anchors; avoid `.*` at start | 50-90% latency reduction | B [S8] |
| VML low accuracy (<80%) | Add 100+ diverse documents to training set | 5-15% accuracy improvement | A [S7] |
| IDM partial matching on endpoints | Raise threshold from 10% to 20% | Reduces endpoint CPU usage by ~30% | B [S4] |
| Too many policies in Default Group | Move niche policies to custom policy groups | Reduces per-message evaluation time | B [S1] |
| Keyword dictionary >10,000 entries | Split into multiple dictionaries; increase threshold | Reduces memory footprint and FP rate | B [S8] |

---

*End of advanced reference. Total sections: 12. Full data identifier catalog covering 80+ identifiers across PCI, PII, Financial, Healthcare, and GDPR regulations. Cross-technology compound examples, API reference, regulation mapping, and performance tuning guidance.*
