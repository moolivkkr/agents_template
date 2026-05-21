# Classifications & Dictionaries — Advanced Reference
## Broadcom Symantec DLP (Enforce Server, version 16.x/25.x/26.x)

> **Purpose:** Full dictionary/identifier reference with examples per regulation, complete MIP configuration, weighted scoring patterns, and multi-tier classification architecture.
> **Evidence sources:** doc-corpus.md [S1-S28], video-intelligence.md [V1-V45], api-intelligence.md

---

## Table of Contents

1. [Full Dictionary Reference by Regulation](#1-full-dictionary-reference-by-regulation)
2. [Dictionary Configuration — Every Option](#2-dictionary-configuration--every-option)
3. [Data Identifier Reference by Category](#3-data-identifier-reference-by-category)
4. [Multi-Tier Classification Architectures](#4-multi-tier-classification-architectures)
5. [Weighted Scoring Patterns](#5-weighted-scoring-patterns)
6. [MIP Integration — Complete Reference](#6-mip-integration--complete-reference)
7. [Compound Classification Examples (5-7 per regulation)](#7-compound-classification-examples)
8. [Dictionary Management Lifecycle](#8-dictionary-management-lifecycle)
9. [Cross-Regulation Classification Matrix](#9-cross-regulation-classification-matrix)
10. [API-Based Classification Management](#10-api-based-classification-management)
11. [Performance Impact of Dictionaries](#11-performance-impact-of-dictionaries)
12. [Migration from Keywords to Dictionaries](#12-migration-from-keywords-to-dictionaries)

---

## 1. Full Dictionary Reference by Regulation

### 1.1 PCI DSS Dictionaries

```
+=========================================================================+
|  PCI DSS Dictionary Collection                                           |
+=========================================================================+
|                                                                          |
|  Dictionary 1: PCI Payment Terms (120 entries)                           |
|  +------------------------------------------------------------------+   |
|  | Term                        | Weight | Category                  |   |
|  |-----------------------------|--------|---------------------------|   |
|  | cardholder                  | 2      | Core PCI                  |   |
|  | primary account number      | 3      | Core PCI                  |   |
|  | PAN                         | 3      | Core PCI (abbreviation)   |   |
|  | card verification value     | 3      | Core PCI                  |   |
|  | CVV                         | 3      | Core PCI (abbreviation)   |   |
|  | CVV2                        | 3      | Core PCI                  |   |
|  | CVC                         | 3      | Core PCI (Mastercard)     |   |
|  | expiration date             | 2      | Card data                 |   |
|  | magnetic stripe             | 3      | Track data                |   |
|  | track data                  | 3      | Track data                |   |
|  | service code                | 2      | Card data                 |   |
|  | PIN block                   | 3      | Authentication            |   |
|  | merchant ID                 | 1      | Processing                |   |
|  | payment processor           | 1      | Processing                |   |
|  | point of sale               | 1      | Processing                |   |
|  | POS terminal                | 1      | Processing                |   |
|  | tokenization                | 1      | Security controls         |   |
|  | payment gateway             | 1      | Processing                |   |
|  | acquirer                    | 1      | Processing                |   |
|  | issuing bank                | 1      | Processing                |   |
|  | chargeback                  | 1      | Processing                |   |
|  | authorization code          | 2      | Transaction               |   |
|  +------------------------------------------------------------------+   |
|                                                                          |
|  Recommended threshold: 3 (weight sum >= 3)                              |
|  Matching: case insensitive, whole words only                            |
|                                                                          |
+=========================================================================+
```

### 1.2 HIPAA / PHI Dictionaries

```
+=========================================================================+
|  HIPAA Dictionary Collection                                             |
+=========================================================================+
|                                                                          |
|  Dictionary 1: Medical Drug Names (2,800 entries)                        |
|  Source: FDA Approved Drug Products (Orange Book)                        |
|  Update frequency: Quarterly (new drug approvals)                        |
|  Threshold: 3 terms                                                      |
|  Weighting:                                                              |
|    Controlled substances (Schedule I-V): weight 3                        |
|    Prescription-only drugs: weight 2                                     |
|    Over-the-counter drugs: weight 1                                      |
|                                                                          |
|  Sample entries:                                                         |
|  +------------------------------------------------------------------+   |
|  | Term                    | Weight | Category                      |   |
|  |-------------------------|--------|-------------------------------|   |
|  | oxycodone               | 3      | Schedule II controlled        |   |
|  | fentanyl                | 3      | Schedule II controlled        |   |
|  | hydrocodone             | 3      | Schedule II controlled        |   |
|  | alprazolam              | 3      | Schedule IV controlled        |   |
|  | metformin               | 2      | Prescription (diabetes)       |   |
|  | atorvastatin            | 2      | Prescription (cholesterol)    |   |
|  | lisinopril              | 2      | Prescription (hypertension)   |   |
|  | amoxicillin             | 2      | Prescription (antibiotic)     |   |
|  | acetaminophen           | 1      | OTC (pain relief)             |   |
|  | ibuprofen               | 1      | OTC (anti-inflammatory)       |   |
|  +------------------------------------------------------------------+   |
|                                                                          |
|  Dictionary 2: Medical Conditions/Diagnoses (1,800 entries)              |
|  Source: ICD-10-CM code descriptions                                     |
|  Update frequency: Annually (ICD updates)                                |
|  Threshold: 3 terms                                                      |
|                                                                          |
|  Sample entries:                                                         |
|  +------------------------------------------------------------------+   |
|  | Term                          | Weight | Category                |   |
|  |-------------------------------|--------|-------------------------|   |
|  | type 2 diabetes mellitus      | 2      | Chronic condition        |   |
|  | major depressive disorder     | 3      | Mental health (sens.)    |   |
|  | substance use disorder        | 3      | Mental health (sens.)    |   |
|  | human immunodeficiency virus  | 3      | Highly sensitive          |   |
|  | HIV                           | 3      | Highly sensitive          |   |
|  | hepatitis C                   | 2      | Infectious disease        |   |
|  | malignant neoplasm            | 2      | Oncology                  |   |
|  | acute myocardial infarction   | 2      | Cardiology                |   |
|  | pregnancy                     | 2      | Reproductive health       |   |
|  | hypertension                  | 1      | Common condition          |   |
|  +------------------------------------------------------------------+   |
|                                                                          |
|  Dictionary 3: Clinical Procedures (800 entries)                         |
|  Source: CPT code descriptions                                           |
|  Threshold: 3 terms                                                      |
|                                                                          |
|  Dictionary 4: HIPAA Privacy Markers (50 entries)                        |
|  Terms: "protected health information", "PHI", "HIPAA",                  |
|         "notice of privacy practices", "patient consent",                |
|         "authorization to release", "minimum necessary",                 |
|         "de-identified", "limited data set", "business associate"        |
|  Threshold: 2 terms (these are high-confidence indicators)               |
|  Weighting: All weight 3 (presence strongly indicates PHI context)       |
|                                                                          |
+=========================================================================+
```

### 1.3 GDPR Dictionaries

```
+=========================================================================+
|  GDPR Dictionary Collection                                              |
+=========================================================================+
|                                                                          |
|  Dictionary 1: GDPR Legal Terms (200 entries)                            |
|  +------------------------------------------------------------------+   |
|  | Term                          | Weight | GDPR Article             |   |
|  |-------------------------------|--------|--------------------------|   |
|  | data subject                  | 2      | Art. 4(1)                |   |
|  | personal data                 | 2      | Art. 4(1)                |   |
|  | data controller               | 2      | Art. 4(7)                |   |
|  | data processor                | 2      | Art. 4(8)                |   |
|  | right to erasure              | 3      | Art. 17                  |   |
|  | right to be forgotten         | 3      | Art. 17                  |   |
|  | data portability              | 2      | Art. 20                  |   |
|  | data protection impact        | 3      | Art. 35                  |   |
|  | legitimate interest           | 2      | Art. 6(1)(f)             |   |
|  | consent                       | 1      | Art. 6(1)(a)             |   |
|  | supervisory authority         | 2      | Art. 51                  |   |
|  | data breach notification      | 3      | Art. 33-34               |   |
|  | cross-border transfer         | 3      | Art. 44-49               |   |
|  | binding corporate rules       | 2      | Art. 47                  |   |
|  | standard contractual clauses  | 2      | Art. 46(2)(c)            |   |
|  +------------------------------------------------------------------+   |
|                                                                          |
|  Threshold: 3 (weight sum >= 3)                                          |
|                                                                          |
|  Dictionary 2: EU Nationality Terms (100 entries)                        |
|  Terms: country names, demonyms, EU institutions                         |
|  Purpose: Contextual indicator that content relates to EU data subjects  |
|  Threshold: 2                                                            |
|                                                                          |
+=========================================================================+
```

### 1.4 SOX / Financial Compliance Dictionaries

```
+=========================================================================+
|  SOX / Financial Dictionary Collection                                   |
+=========================================================================+
|                                                                          |
|  Dictionary 1: Insider Trading Terms (150 entries)                       |
|  +------------------------------------------------------------------+   |
|  | Term                          | Weight | Category                |   |
|  |-------------------------------|--------|-------------------------|   |
|  | material non-public           | 5      | SEC restricted           |   |
|  | MNPI                          | 5      | SEC restricted (abbrev.) |   |
|  | insider information           | 5      | SEC restricted           |   |
|  | blackout period               | 4      | Trading restriction      |   |
|  | quiet period                  | 4      | Pre-earnings             |   |
|  | earnings guidance             | 3      | Pre-release              |   |
|  | revenue forecast              | 3      | Pre-release              |   |
|  | earnings per share            | 2      | Financial metric         |   |
|  | EBITDA                        | 1      | Financial metric         |   |
|  | analyst consensus             | 2      | Market intelligence      |   |
|  | revenue recognition           | 2      | Accounting               |   |
|  | material weakness             | 3      | SOX specific             |   |
|  | restatement                   | 4      | Financial distress       |   |
|  | going concern                 | 4      | Audit opinion            |   |
|  | 10-K draft                    | 3      | Pre-filing               |   |
|  | proxy statement draft         | 3      | Pre-filing               |   |
|  +------------------------------------------------------------------+   |
|                                                                          |
|  Threshold: 4 (weight sum >= 4, ensures meaningful concentration)        |
|                                                                          |
|  Dictionary 2: Financial Metrics (200 entries)                           |
|  Terms: gross margin, net income, operating cash flow, free cash flow,   |
|         return on equity, debt-to-equity, working capital, etc.          |
|  Threshold: 5 (high threshold -- financial metrics are routine)          |
|  Weighting: All weight 1 (contextual, not individually sensitive)        |
|                                                                          |
|  Dictionary 3: M&A Terms (100 entries)                                   |
|  Terms: "due diligence", "letter of intent", "term sheet",              |
|         "acquisition target", "merger agreement", "break-up fee",        |
|         "earnout", "representations and warranties"                      |
|  Threshold: 3                                                            |
|  Weighting: "letter of intent" weight 4; general terms weight 2         |
|                                                                          |
+=========================================================================+
```

### 1.5 ITAR / EAR Export Control Dictionaries

```
+=========================================================================+
|  Export Control Dictionary Collection                                     |
+=========================================================================+
|                                                                          |
|  Dictionary 1: ITAR Controlled Terms (300 entries)                       |
|  Terms: defense article, defense service, USML, significant military     |
|         equipment, technical data, classified information, ITAR,          |
|         International Traffic in Arms Regulations                        |
|  Threshold: 2 (export control terms are always significant)              |
|  Weighting: Classification markers ("SECRET", "CONFIDENTIAL") weight 5   |
|             ITAR-specific ("defense article", "USML") weight 3           |
|             General military ("military", "defense") weight 1            |
|                                                                          |
|  Dictionary 2: EAR Controlled Terms (200 entries)                        |
|  Terms: dual-use, Commerce Control List, CCL, ECCN, export license,      |
|         deemed export, end-use, prohibited parties, entity list          |
|  Threshold: 2                                                            |
|                                                                          |
|  Dictionary 3: Embargoed Countries (30 entries)                          |
|  Terms: country names and codes for sanctioned/embargoed nations         |
|  Threshold: 1 (any mention combined with ITAR/EAR terms is significant) |
|                                                                          |
+=========================================================================+
```

---

## 2. Dictionary Configuration — Every Option

### 2.1 Import Options

```
+=========================================================================+
|  Dictionary Import — Complete Options                                    |
+=========================================================================+
|                                                                          |
|  Source Format:                                                           |
|    (*) Plain text (one term per line)                                    |
|    ( ) CSV with weight column (term,weight)                              |
|    ( ) CSV with weight and category (term,weight,category)               |
|                                                                          |
|  File Encoding:                                                          |
|    (*) UTF-8 (recommended for international characters)                  |
|    ( ) UTF-16                                                            |
|    ( ) ISO-8859-1 (Western European)                                     |
|    ( ) Windows-1252                                                      |
|                                                                          |
|  Import Handling:                                                        |
|    [x] Remove duplicate entries                                          |
|    [x] Trim whitespace                                                   |
|    [ ] Skip entries shorter than [   ] characters                        |
|    [ ] Skip entries longer than [    ] characters                        |
|                                                                          |
|  Preview (first 10 entries):                                             |
|    1. metformin (weight: 2)                                              |
|    2. atorvastatin (weight: 2)                                           |
|    3. oxycodone (weight: 3)                                              |
|    ...                                                                   |
|    Total: 2,847 entries loaded                                           |
|                                                                          |
+=========================================================================+
```

### 2.2 Matching Mode Reference

| Option | What It Does | When to Use | FP Impact | Evidence |
|--------|-------------|-------------|-----------|----------|
| Case Sensitive | Matches exact case | Code names, acronyms, proper nouns | Reduces FPs | A [S1, S8] |
| Case Insensitive | Matches any case | Medical terms, legal terms, general vocabulary | Standard | A [S1, S8] |
| Whole Words Only | Requires word boundaries | Most dictionaries (prevents "in" matching inside "insulin") | Reduces FPs significantly | A [S1, S8] |
| Partial Match (no Whole Words) | Matches within words | Specialized: chemical formulas, code identifiers | Increases FPs | A [S1, S8] |
| Stemming Enabled | Matches word forms | Moderate vocabulary ("report" matches "reporting") | Increases FPs slightly | B [S8] |
| Stemming Disabled | Exact form only | Precise terms where inflections change meaning | Standard | B [S8] |

### 2.3 Threshold Tuning Guide

| Dictionary Size | Low Threshold | Medium Threshold | High Threshold | Evidence |
|-----------------|-------------- |-----------------|----------------|----------|
| 10-50 terms (project codes, exec names) | 1 | 2 | 3 | B [S8] |
| 50-200 terms (legal, financial jargon) | 2-3 | 4-5 | 7-10 | B [S8] |
| 200-1,000 terms (medical drugs, conditions) | 3-4 | 5-7 | 10-15 | B [S8] |
| 1,000-5,000 terms (comprehensive vocabulary) | 5-7 | 10-15 | 20-30 | B [S8] |
| 5,000+ terms (large corpora) | 10+ | 20+ | 50+ | B [S8] |

**Rule of thumb:** Start with a threshold of ~0.1% of dictionary size (100 terms = threshold 1; 1,000 terms = threshold 1-2; 10,000 terms = threshold 10). Adjust based on false positive rate.

---

## 3. Data Identifier Reference by Category

### 3.1 Validation Algorithm Details

| Algorithm | Identifiers Using It | False Positive Rejection Rate | How It Works |
|-----------|---------------------|-------------------------------|-------------|
| **Luhn (mod-10)** | Credit cards, Canada SIN, Sweden PN | ~90% of random sequences | Double every 2nd digit from right, subtract 9 if >9, sum must be divisible by 10 |
| **ISO 13616 (mod-97)** | IBAN | ~99% of random sequences | Convert letters to digits (A=10..Z=35), calculate number mod 97, must equal 1 |
| **Verhoeff** | India Aadhaar | ~100% (catches all single-digit errors, adjacent transpositions) | Uses dihedral group D5 permutation tables |
| **ISO 7064 Mod 11,2** | China Resident ID | ~99% | Weighted sum with modulo 11 check character |
| **Area/Group/Serial** | US SSN | ~40-50% (only excludes invalid ranges) | Area: 001-899 (not 000, 666); Group: 01-99; Serial: 0001-9999 |
| **State Format** | US Driver License | Varies by state | Per-state format validation (letter prefix, digit count) |
| **Prefix Exclusion** | UK NINO | ~60% | Excludes invalid prefix combinations |
| **Modulo 11** | UK NHS, Japan My Number | ~91% | Weighted sum with modulo 11 remainder check |
| **3-7-1 Checksum** | US ABA Routing | ~95% | Digits weighted 3,7,1 alternating, sum divisible by 10 |
| **Check Character** | Italy Codice Fiscale, Spain DNI | Varies | Character position determines check value |

### 3.2 Identifier-to-Regulation Cross-Reference

```
+=========================================================================+
|  Which Identifiers Apply to Which Regulations                            |
+=========================================================================+
|                                                                          |
|            | PCI | HIPAA | GDPR | SOX | GLBA | FERPA | CCPA | PIPEDA |  |
|  ----------|-----|-------|------|-----|------|-------|------|--------|  |
|  CC Number |  X  |       |  X   |     |  X   |       |  X   |   X    |  |
|  US SSN    |     |   X   |      |     |  X   |   X   |  X   |        |  |
|  US DL     |     |       |      |     |      |       |  X   |        |  |
|  US Passp. |     |       |      |     |      |       |  X   |        |  |
|  IBAN      |  X  |       |  X   |     |  X   |       |      |        |  |
|  SWIFT/BIC |     |       |  X   |     |  X   |       |      |        |  |
|  DEA #     |     |   X   |      |     |      |       |      |        |  |
|  NPI       |     |   X   |      |     |      |       |      |        |  |
|  ICD codes |     |   X   |      |     |      |       |      |        |  |
|  UK NINO   |     |       |  X   |     |      |       |      |        |  |
|  Canada SIN|     |       |      |     |      |       |      |   X    |  |
|  FR INSEE  |     |       |  X   |     |      |       |      |        |  |
|  DE Per.ID |     |       |  X   |     |      |       |      |        |  |
|  JP MyNum  |     |       |  X*  |     |      |       |      |        |  |
|  IN Aadhaar|     |       |  X*  |     |      |       |      |        |  |
|  BR CPF    |     |       |  X*  |     |      |       |      |        |  |
|  AU TFN    |     |       |  X*  |     |      |       |      |        |  |
|                                                                          |
|  X = directly required by regulation                                     |
|  X* = required by equivalent national regulation (APPI, PIPL, LGPD)     |
|                                                                          |
+=========================================================================+
```

---

## 4. Multi-Tier Classification Architectures

### 4.1 Standard 4-Tier Classification Model

```
+=========================================================================+
|  4-Tier Enterprise Data Classification                                   |
+=========================================================================+
|                                                                          |
|  TIER 1: RESTRICTED (Severity 1 - High)                                 |
|  +-----------------------------------------------------------------+    |
|  | Definition: Data whose unauthorized disclosure would cause       |    |
|  |            severe harm (regulatory fines, criminal liability,    |    |
|  |            material business impact)                             |    |
|  |                                                                  |    |
|  | Detection:                                                       |    |
|  |   - EDM match on protected records (2+ fields, 1 KEY)           |    |
|  |     AND data identifier match (SSN, CC, DEA, etc.)              |    |
|  |   - OR: IDM match on trade secret documents (>= 15%)            |    |
|  |   - OR: MIP label "Highly Confidential" detected                |    |
|  |                                                                  |    |
|  | Response: Block + Encrypt + Notify + Syslog                      |    |
|  +-----------------------------------------------------------------+    |
|                                                                          |
|  TIER 2: CONFIDENTIAL (Severity 2 - Medium)                             |
|  +-----------------------------------------------------------------+    |
|  | Definition: Data whose disclosure would cause significant        |    |
|  |            business harm (competitive disadvantage, reputation)  |    |
|  |                                                                  |    |
|  | Detection:                                                       |    |
|  |   - EDM match on protected records (no SSN/CC required)          |    |
|  |   - OR: VML classification as confidential (>= 85% confidence)  |    |
|  |   - OR: MIP label "Confidential" detected                       |    |
|  |   - OR: Data identifier match (national IDs, IBAN) standalone   |    |
|  |                                                                  |    |
|  | Response: Notify + Syslog + Apply MIP label                      |    |
|  +-----------------------------------------------------------------+    |
|                                                                          |
|  TIER 3: INTERNAL (Severity 3 - Low)                                    |
|  +-----------------------------------------------------------------+    |
|  | Definition: Data not intended for public release but whose       |    |
|  |            disclosure would cause limited harm                   |    |
|  |                                                                  |    |
|  | Detection:                                                       |    |
|  |   - Dictionary match (financial terms >= 5)                      |    |
|  |     AND recipient is external                                    |    |
|  |   - OR: Dictionary match (project code names >= 1)               |    |
|  |   - OR: File property (engineering file types)                   |    |
|  |                                                                  |    |
|  | Response: Syslog only (monitoring)                                |    |
|  +-----------------------------------------------------------------+    |
|                                                                          |
|  TIER 4: PUBLIC (Severity 4 - Informational)                            |
|  +-----------------------------------------------------------------+    |
|  | Definition: No classification detected, or content explicitly    |    |
|  |            approved for public release                           |    |
|  |                                                                  |    |
|  | Detection: No policies matched (default tier)                    |    |
|  | Response: None                                                    |    |
|  +-----------------------------------------------------------------+    |
|                                                                          |
+=========================================================================+
```

### 4.2 Implementation Pattern

```
+=========================================================================+
|  Policy Structure for 4-Tier Classification                              |
+=========================================================================+
|                                                                          |
|  Policy 1: "Data Classification - Restricted"                            |
|    Rules: compound conditions (EDM+identifier, IDM, MIP HC)              |
|    Severity: 1 - High                                                    |
|    Mode: Enabled (block after tuning)                                    |
|                                                                          |
|  Policy 2: "Data Classification - Confidential"                          |
|    Rules: medium-confidence conditions (EDM, VML, MIP Conf.)            |
|    Severity: 2 - Medium                                                  |
|    Mode: Enabled (notify after tuning)                                   |
|                                                                          |
|  Policy 3: "Data Classification - Internal"                              |
|    Rules: low-confidence conditions (dictionaries, file types)           |
|    Severity: 3 - Low                                                     |
|    Mode: Test With Notifications                                         |
|                                                                          |
|  Evaluation: All three policies evaluate independently.                  |
|  If multiple match, highest severity (Policy 1) determines outcome.      |
|                                                                          |
+=========================================================================+
```

---

## 5. Weighted Scoring Patterns

### 5.1 Dictionary Weight Calculation

```
Example: Medical Dictionary with Weighted Scoring

Document content: "Patient prescribed metformin and oxycodone for diabetes management"

Matched terms:
  metformin    (weight 2)
  oxycodone    (weight 3)

Total weight: 2 + 3 = 5

Threshold configurations:
  If threshold = 3: TRIGGERS (5 >= 3) --> Severity Medium
  If threshold = 5: TRIGGERS (5 >= 5) --> Severity Medium
  If threshold = 6: DOES NOT TRIGGER (5 < 6)

For HIPAA "PHI - Critical" tier:
  Require weight sum >= 8 (needs multiple medical terms + sensitive terms)
  "metformin + oxycodone + HIV + patient consent" = 2+3+3+3 = 11 >= 8 --> TRIGGER
```

### 5.2 Multi-Dictionary Scoring

```
Policy: "Insider Trading Detection"

Rule 1 (compound):
  Condition A: Insider Trading dictionary (weight >= 5)
  Condition B: Financial Metrics dictionary (weight >= 3)
  Logic: A AND B

  Match example:
    "material non-public" (w5) + "earnings per share" (w2) + "revenue forecast" (w3)
    Dict A weight: 5 (PASS >= 5)
    Dict B weight: 5 (PASS >= 3)
    Compound: BOTH pass --> TRIGGER

  Non-match example:
    "EBITDA" (w1 in Dict B) + "gross margin" (w1 in Dict B)
    Dict A weight: 0 (FAIL < 5)
    Dict B weight: 2 (FAIL < 3)
    Compound: NEITHER pass --> NO TRIGGER
```

---

## 6. MIP Integration — Complete Reference

### 6.1 Prerequisites for MIP Integration

| Component | Requirement | Notes | Evidence |
|-----------|------------|-------|----------|
| MIP SDK | Installed on Enforce Server | Download from Microsoft; version must match MIP version | A [S1, S2] |
| Azure AD Tenant | Configured with sensitivity labels | Labels must be published to users | A [S2] |
| Service Principal | App registration in Azure AD | Requires permissions for label read/write | A [S2] |
| TLS Certificate | For Enforce-to-Azure communication | Standard HTTPS | A [S2] |
| Network Access | Enforce Server must reach Azure AD endpoints | *.microsoftonline.com, *.protection.outlook.com | A [S2] |

### 6.2 MIP Label Detection Configuration

```
+=========================================================================+
|  Policy Rule: Content Matches MIP Tag                                    |
+=========================================================================+
|                                                                          |
|  Rule Type: Content Matches MIP Tag Rule                                 |
|                                                                          |
|  Match Criteria:                                                         |
|    ( ) Any sensitivity label present (any label triggers)                |
|    (*) Specific label(s):                                                |
|        Available labels (from connected MIP tenant):                     |
|        +------------------------------------------------------+         |
|        | [x] Highly Confidential                              |         |
|        |     Sublabels:                                        |         |
|        |     [x] All Employees                                |         |
|        |     [x] Specific People                               |         |
|        | [x] Confidential                                      |         |
|        |     Sublabels:                                        |         |
|        |     [ ] All Employees                                |         |
|        |     [x] Finance Team Only                             |         |
|        |     [ ] Legal Team Only                               |         |
|        | [ ] General                                           |         |
|        | [ ] Public                                            |         |
|        +------------------------------------------------------+         |
|                                                                          |
|  Negation:                                                               |
|    [ ] Negate (trigger when label is NOT present)                        |
|                                                                          |
|  Severity: (*) 1 - High                                                  |
|                                                                          |
+=========================================================================+
```

### 6.3 MIP Label Application Response Rule

```
+=========================================================================+
|  Response Rule: Apply MIP Sensitivity Label                              |
+=========================================================================+
|                                                                          |
|  Action Type: Apply Classification Label                                 |
|                                                                          |
|  MIP Label Configuration:                                                |
|    Label: [Confidential - All Employees      ] [v]                       |
|                                                                          |
|  Apply To:                                                               |
|    [x] Document attachments (Office, PDF)                                |
|    [x] Email message (Outlook header label)                              |
|    [ ] Copy of file (apply to quarantine copy only)                      |
|                                                                          |
|  Label Behavior:                                                         |
|    ( ) Never overwrite existing label                                    |
|    (*) Upgrade only (apply if current label is lower sensitivity)        |
|    ( ) Always overwrite (replace any existing label)                     |
|    ( ) Downgrade allowed (can lower sensitivity)                         |
|                                                                          |
|  RMS Encryption:                                                         |
|    [x] Apply Rights Management protection as defined by label            |
|    Template: [Encrypt - Confidential         ] (from MIP)               |
|                                                                          |
|  Justification:                                                          |
|    [x] Log justification for label changes                               |
|    Justification text: [Auto-classified by DLP policy - CC data found]  |
|                                                                          |
|  Conditions (when to apply):                                             |
|    [x] Severity: 1 - High or 2 - Medium                                 |
|    [ ] Protocol: (any)                                                   |
|    [ ] Detection server type: (any)                                      |
|                                                                          |
+=========================================================================+
```

### 6.4 MIP + DLP Classification Workflow Examples

**Example 1: Auto-label unlabeled PCI documents**

| Step | What Happens | Configuration |
|------|-------------|---------------|
| 1 | Content inspected, CC numbers detected | Data Identifier: Credit Card >= 1 |
| 2 | MIP label checked: none present | Condition: "NOT Content Matches MIP Tag: Any" |
| 3 | Response: Apply label "Confidential - PCI" | Apply Classification Label action |
| 4 | RMS encryption applied | Based on label's protection settings |
| **WHY** | Documents containing PCI data that weren't labeled by the creator get auto-classified |
| **GOTCHA** | The document must be in a format that supports MIP labels (Office, PDF). Plain text files cannot receive MIP labels. |

**Example 2: Enforce MIP labels on external email**

| Step | What Happens | Configuration |
|------|-------------|---------------|
| 1 | Email with "Highly Confidential" label detected | Content Matches MIP Tag: "Highly Confidential" |
| 2 | Recipient check: external domain | Recipient matches pattern: NOT @company.com |
| 3 | Response: Block email | Network Prevent for Email: Block action |
| **WHY** | Even if DLP content rules don't match, respect the creator's classification intent |
| **GOTCHA** | Users may downgrade labels before sending. Enable MIP label downgrade justification in Azure AD to audit this behavior. |

**Example 3: Network Discover classification scan**

| Step | What Happens | Configuration |
|------|-------------|---------------|
| 1 | Discover scan finds file with no label | Network Discover target: file shares |
| 2 | DLP detects sensitive content | Any detection rule match |
| 3 | Response: Apply MIP label to file on share | Apply Classification Label (in-place) |
| **WHY** | Retroactively classify files at rest on file shares |
| **GOTCHA** | High Speed Discovery (DLP 16.1+) required for efficient label application at scale. Without it, label application on large file shares can take days. |

---

## 7. Compound Classification Examples

### 7.1 PCI DSS — 7 Classification Examples

| # | Classification | Detection Conditions | Severity | Response |
|---|---------------|---------------------|---------|---------|
| 1 | PCI - Bulk Card Data | CC >= 10 unique AND File Type: Spreadsheet | 1 - High | Block + Encrypt |
| 2 | PCI - Card in Transit | CC >= 1 AND Recipient: external | 1 - High | Block + Notify |
| 3 | PCI - Card + Track Data | CC >= 1 AND custom regex: track data format | 1 - High | Block + Quarantine |
| 4 | PCI - Card in Context | CC >= 1 AND PCI dictionary >= 2 terms | 2 - Medium | Notify + Syslog |
| 5 | PCI - Possible Card Data | CC >= 1 (standalone) | 2 - Medium | Syslog |
| 6 | PCI - Financial Context | PCI dictionary >= 5 terms (no card detected) | 3 - Low | Syslog |
| 7 | PCI - Encrypted Card File | File type: encrypted archive AND CC in filename pattern | 2 - Medium | Notify |

### 7.2 HIPAA — 7 Classification Examples

| # | Classification | Detection Conditions | Severity | Response |
|---|---------------|---------------------|---------|---------|
| 1 | PHI - Confirmed Patient Data | EDM match (3 fields, 1 KEY) AND Medical dict >= 3 | 1 - High | Block + Quarantine |
| 2 | PHI - Patient ID Exposure | EDM match (2 fields, 1 KEY) AND US SSN >= 1 | 1 - High | Block + Notify |
| 3 | PHI - Clinical Notes | VML match (Clinical Notes, >= 90%) | 2 - Medium | Notify + Syslog |
| 4 | PHI - Medical Form | Form Recognition (CMS-1500, Patient Intake) | 2 - Medium | Notify + Syslog |
| 5 | PHI - Drug Names + PII | Medical drug dict >= 3 AND US SSN >= 1 | 2 - Medium | Notify |
| 6 | PHI - Provider IDs | DEA >= 1 AND NPI >= 1 (compound) | 2 - Medium | Syslog |
| 7 | PHI - Possible Medical | Medical conditions dict >= 5 (standalone) | 3 - Low | Syslog |

### 7.3 GDPR — 5 Classification Examples

| # | Classification | Detection Conditions | Severity | Response |
|---|---------------|---------------------|---------|---------|
| 1 | GDPR - Bulk EU PII | EU national ID >= 5 unique AND GDPR dict >= 2 | 1 - High | Block + Notify |
| 2 | GDPR - Cross-Border Transfer | EU national ID >= 1 AND Recipient outside EU | 1 - High | Block |
| 3 | GDPR - Personal Data | IBAN >= 1 AND EU nationality dict >= 2 | 2 - Medium | Notify |
| 4 | GDPR - Special Category | Medical dict >= 3 AND EU national ID >= 1 | 1 - High | Block (Art. 9) |
| 5 | GDPR - Privacy Context | GDPR legal dict >= 3 AND EU nationality >= 1 | 3 - Low | Syslog |

---

## 8. Dictionary Management Lifecycle

### 8.1 Dictionary Versioning

```
+=========================================================================+
|  Dictionary Version Management                                           |
+=========================================================================+
|                                                                          |
|  Dictionary: Medical Drug Names                                          |
|                                                                          |
|  +------------------------------------------------------------------+   |
|  | Version  | Date       | Entries | Changes              | Author  |   |
|  |----------|------------|---------|----------------------|---------|   |
|  | v2024.1  | 2024-01-15 | 2,712   | Initial creation     | admin   |   |
|  | v2024.2  | 2024-04-10 | 2,789   | +77 new FDA approvals| pharma  |   |
|  | v2024.3  | 2024-07-08 | 2,832   | +43 new, -3 recalled | pharma  |   |
|  | v2024.4  | 2024-10-14 | 2,847   | +15 new approvals    | pharma  |   |
|  +------------------------------------------------------------------+   |
|                                                                          |
|  Next update: 2025-01-15 (quarterly schedule)                            |
|  Source: FDA Approved Drug Products (Orange Book)                        |
|  Owner: Pharmaceutical Compliance team                                   |
|                                                                          |
+=========================================================================+
```

**Important:** Symantec DLP does not have built-in dictionary versioning. Versioning must be managed externally (e.g., in a shared document, version control system, or spreadsheet). When updating a dictionary, re-import the full updated file -- it replaces the existing keyword list in the rule. [S1, S8]

### 8.2 Maintenance Schedule Recommendations

| Dictionary Type | Update Frequency | Source for Updates | Evidence |
|-----------------|-----------------|-------------------|----------|
| Medical Drug Names | Quarterly | FDA Orange Book, WHO INN list | B [S8] |
| ICD Codes | Annually (October) | CMS ICD-10-CM update | B [S4] |
| Legal Terms | Annually | Legal department review | B [tribal knowledge] |
| Financial Terms | Semi-annually | Finance team review + regulatory changes | B [tribal knowledge] |
| Project Code Names | Per project (ad-hoc) | Project management office | B [tribal knowledge] |
| Competitor Names | Quarterly | Competitive intelligence team | B [tribal knowledge] |
| Profanity / Harassment | Semi-annually | HR department review | B [tribal knowledge] |
| Executive Names | Per change (ad-hoc) | HR (hiring/departure/board changes) | B [tribal knowledge] |
| Export Control Terms | Annually | Trade compliance team | B [tribal knowledge] |

---

## 9. Cross-Regulation Classification Matrix

```
+=========================================================================+
|  Which Classification Components Apply to Each Regulation                |
+=========================================================================+
|                                                                          |
|             | Sys. ID | Dict. | EDM | IDM | VML | Form | MIP |        |
|  -----------|---------|-------|-----|-----|-----|------|-----|        |
|  PCI DSS    |   X     |   X   |  X  |     |     |      |  X  |        |
|  HIPAA      |   X     |   X   |  X  |     |  X  |  X   |  X  |        |
|  GDPR       |   X     |   X   |  X  |     |     |      |  X  |        |
|  SOX        |         |   X   |  X  |     |  X  |      |  X  |        |
|  GLBA       |   X     |   X   |  X  |     |     |      |     |        |
|  FERPA      |   X     |       |  X  |     |     |      |     |        |
|  ITAR/EAR   |         |   X   |     |  X  |  X  |      |     |        |
|  CCPA       |   X     |   X   |  X  |     |     |      |     |        |
|  IP Protect |         |   X   |     |  X  |  X  |      |  X  |        |
|  HR/Conduct |         |   X   |     |     |     |      |     |        |
|                                                                          |
|  X = primary or required component for this regulation                   |
|                                                                          |
+=========================================================================+
```

---

## 10. API-Based Classification Management

### 10.1 CloudSOC Data Identifier API

```
# List all available data identifiers (CloudSOC)
GET https://app.elastica.net/api/clouddlp/protect/public/dataIdentifiers
Authorization: <API-key>

Response:
{
  "identifiers": [
    {
      "id": "credit_card",
      "name": "Credit Card Number",
      "category": "PCI",
      "validator": "luhn",
      "builtIn": true,
      "regions": ["Global"]
    },
    {
      "id": "us_ssn",
      "name": "US Social Security Number",
      "category": "PII",
      "validator": "area_group_serial",
      "builtIn": true,
      "regions": ["US"]
    },
    {
      "id": "iban",
      "name": "International Bank Account Number",
      "category": "Financial",
      "validator": "iso13616_mod97",
      "builtIn": true,
      "regions": ["Global"]
    }
  ]
}
```

### 10.2 CloudSOC Profile Creation with Identifiers

```
# Create a DLP profile with data identifiers (CloudSOC)
POST https://app.elastica.net/api/clouddlp/protect/public/profile
Authorization: <API-key>
Content-Type: application/json

{
  "name": "PCI Classification Profile",
  "description": "Detects credit card data per PCI DSS",
  "rules": [
    {
      "name": "Credit Card Detection",
      "dataIdentifiers": ["credit_card"],
      "threshold": 1,
      "severity": "HIGH"
    }
  ],
  "enabled": true
}
```

### 10.3 On-Prem API Limitations

| Operation | API Status | Workaround | Evidence |
|-----------|-----------|-----------|----------|
| List data identifiers | GAP (on-prem) | Use CloudSOC API or console | A [API-intelligence] |
| Create classification rule | GAP | Author in console, export via policy XML | A [API-intelligence] |
| Create dictionary | GAP | Author in console | A [API-intelligence] |
| Import classification (in policy) | FULL (25.1+) | `POST /policies/import` | A [API-intelligence] |
| Export classification (in policy) | FULL (25.1+) | `POST /policies/export` | A [API-intelligence] |
| Create MIP tag rule | GAP | Console only | A [API-intelligence] |

---

## 11. Performance Impact of Dictionaries

### 11.1 Dictionary Size vs. Detection Latency

| Dictionary Size | In-Memory Footprint | Per-Message Latency | Recommendation | Evidence |
|-----------------|-------------------|-------------------|---------------|----------|
| 10-100 entries | <1 MB | <10 ms | No performance concern | A [S1] |
| 100-1,000 entries | 1-10 MB | 10-50 ms | No performance concern | A [S1] |
| 1,000-10,000 entries | 10-100 MB | 50-200 ms | Monitor detection latency | B [S8] |
| 10,000-50,000 entries | 100-500 MB | 200-500 ms | Consider splitting into targeted sub-dictionaries | B [S8] |
| 50,000-100,000 entries | 500 MB - 1 GB | 500 ms - 1 s | Split into smaller dictionaries; use threshold + breadth to filter | B [S8] |

### 11.2 Optimization Strategies

| Strategy | How It Helps | When to Use |
|----------|-------------|-------------|
| Split large dictionaries | Reduces per-rule memory; allows targeted deployment | Dictionary > 10,000 entries |
| Increase threshold | Reduces false positives and processing for near-miss content | High FP rate on large dictionaries |
| Disable stemming | Reduces matching permutations | When exact forms are sufficient |
| Enable whole words only | Reduces substring matching overhead | Always (unless partial match needed) |
| Use compound rules | Limits dictionary evaluation to pre-filtered content | When dictionary is secondary condition |

---

## 12. Migration from Keywords to Dictionaries

### 12.1 When to Migrate

| Current State | Trigger for Migration | Evidence |
|---------------|---------------------|----------|
| Individual keyword rules scattered across policies | 10+ policies with similar keyword lists | B [tribal knowledge] |
| Keyword maintenance requires editing many rules | Same term added/removed in multiple rules | B [tribal knowledge] |
| No version tracking for keywords | Cannot audit what terms were active last quarter | B [tribal knowledge] |
| Keywords embedded in compound rules | Need to update keywords without touching rule logic | B [tribal knowledge] |

### 12.2 Migration Steps

```
Step 1: Audit existing keyword rules
  - Export all policies (Manage > Policies > Export)
  - Identify all "Content Matches Keyword" rules
  - Catalog all keywords across all rules

Step 2: Consolidate into dictionaries
  - Group keywords by domain (medical, financial, legal, etc.)
  - Remove duplicates
  - Assign weights based on sensitivity

Step 3: Create dictionary CSV files
  - One file per dictionary
  - Format: term,weight (or plain text for equal weight)
  - Store in version control

Step 4: Update rules to use dictionary import
  - Edit each keyword rule
  - Import dictionary file
  - Set threshold based on previous keyword count
  - Test in "Test Without Notifications" mode

Step 5: Validate
  - Compare incident volume before/after migration
  - Verify FP rate is equal or lower
  - Confirm no detection gaps
```

---

*End of advanced reference. Total sections: 12. Full dictionary reference covering 5 regulatory domains (PCI, HIPAA, GDPR, SOX, ITAR). Complete MIP integration reference. Identifier-to-regulation cross-reference matrix. Dictionary lifecycle management. Performance tuning guide.*
