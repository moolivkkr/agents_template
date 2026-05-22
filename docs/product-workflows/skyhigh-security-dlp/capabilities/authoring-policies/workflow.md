# Authoring Policies -- Complete Workflow
## Skyhigh Security DLP (SSE Platform)

> Capability: authoring-policies | Generated: 2026-05-21
> Sources: doc-corpus (42 sources), video-intelligence (12 videos/labs), api-intelligence (2 API surfaces)

---

## Overview

Policy authoring in Skyhigh Security DLP is the process of defining what sensitive data to detect (Classifications), how to combine detection criteria into enforceable rules (Rule Groups and Rules within Sanctioned DLP Policies), and what to do when violations are detected (Response Actions). The output is one or more active DLP policies that enforce data protection across sanctioned cloud services (CASB), shadow IT/web traffic (SWG), and optionally desktop endpoints (via Trellix DLP integration).

Skyhigh's DLP is embedded within the broader Security Service Edge (SSE) platform, which unifies Secure Web Gateway (SWG), Cloud Access Security Broker (CASB), Private Access (ZTNA), and DLP into a single cloud-native solution. This means classifications created for DLP are available across all SSE components.

**What policy authoring produces:**
- Classifications that define HOW to detect sensitive content (10 definition types)
- Sanctioned DLP Policies containing Rule Groups, Rules, Exceptions, and Response Actions
- Shadow/Web DLP Policies for SWG-channel enforcement
- Optionally: Endpoint DLP configuration synced to Trellix ePO

---

## Complexity Score

**Rating: MODERATE-TO-COMPLEX**

**Justification:**
- 10 classification definition types (highest variety among competitors)
- Two-level Boolean logic (Rule Groups with OR, Rules within groups with AND/OR)
- Three separate policy types per channel (Sanctioned, Shadow/Web, Endpoint)
- Two separate DLP engines (Cloud-native for CASB/SWG, Trellix for Endpoint)
- AI-powered features (ML Auto Classifiers, AI RegEx Generator) reduce manual work
- Policy templates accelerate initial setup
- But: no API for policy authoring; everything is console-only

---

## Policy Hierarchy

```
Level 1: Classifications (WHAT to detect)
    10 Definition Types:
    Dictionary | Advanced Pattern (Regex) | Keyword | EDM | IDM | ML Auto Classifier
    Document Properties | File Name Set | File Sizes | True File Type
    + Proximity (combining definition types by character distance)
    |
Level 2: Sanctioned DLP Policies (HOW to enforce)
    |
    +--> Rule Groups (Boolean OR between groups)
    |        |
    |        +--> Rules (AND/OR within groups)
    |                Classification Rules | Keyword Rules | User Risk Rules
    |                Structured Fingerprint Rules | Unstructured Fingerprint Rules
    |
    +--> Exceptions (WHEN to ignore)
    |        Same rule types as Rules, combined with Boolean logic
    |
    +--> Response Actions (WHAT to do on match)
             Create Incident | Email Notification | Block | Quarantine | Encrypt
             Coach User | Apply Label | Custom Action
    |
Level 3: Channels (WHERE to enforce)
    Sanctioned (CASB - API + inline)
    Shadow/Web (SWG - inline proxy)
    Endpoint (Trellix DLP agent)
```

---

## Level 1: Classifications

Classifications are the foundation. They define WHAT sensitive data looks like. Every classification is composed of one or more definition types and can include proximity matching.

### 1.1 Dictionary Classifications

**What:** Collections of related keywords/phrases with scored matching. Each dictionary entry contributes to a cumulative score; when the score threshold is met, the classification triggers.

**Navigation:** Policy > DLP Policy > Classifications > Create Classification > Dictionary

**Workflow:**
1. Click **Create Classification**
2. Enter classification name and description
3. Select **Definition Type: Dictionary**
4. Select a built-in dictionary or create custom
5. Configure:
   - **Score Threshold**: Minimum cumulative score to trigger (e.g., 5)
   - **Location**: Header / Footer / Body / First N characters
6. Click **Save**

**Example -- Medical Terminology:**
```
Classification Name: HIPAA - Medical Terms
Definition Type: Dictionary
Dictionary: Medical Terminology (built-in)
Score Threshold: 5
Location: Body
```

**Example -- Financial Keywords:**
```
Classification Name: Financial - Earnings Keywords
Definition Type: Dictionary
Dictionary: Custom (revenue, profit, loss, EBITDA, margin, forecast, guidance, Q1-Q4)
Score Threshold: 3
Location: Body
```

**Example -- Profanity Filter:**
```
Classification Name: Content - Profanity Detection
Definition Type: Dictionary
Dictionary: Profanity (built-in)
Score Threshold: 1
Location: Body
```

### 1.2 Advanced Pattern Classifications (Regex)

**What:** Google RE2-compliant regular expressions with optional validators (Luhn, BIN, checksum).

**Navigation:** Policy > DLP Policy > Classifications > Create Classification > Advanced Pattern

**Workflow:**
1. Click **Create Classification**
2. Enter classification name
3. Select **Definition Type: Advanced Pattern**
4. Enter or select regex pattern
5. Optionally add validators:
   - **Luhn Validator**: Validates credit card numbers using Luhn algorithm
   - **BIN Validator**: Validates Bank Identification Number prefix
   - **Checksum Validator**: Custom checksum validation
6. Configure:
   - **Score Threshold**: Number of pattern matches required
   - **Location**: Header / Footer / Body / First N characters
7. Click **Save**

**Using the AI RegEx Generator:**
1. Click **AI RegEx Generator** button
2. Enter a natural language description: "Match US Social Security Numbers in XXX-XX-XXXX format"
3. Review the generated RE2 regex
4. Click **Use This Pattern** to insert into the classification
5. Test with sample data

**Example -- US Social Security Number:**
```
Classification Name: PII - US SSN
Definition Type: Advanced Pattern
Pattern: \b\d{3}-\d{2}-\d{4}\b
Validator: None (or custom format validator)
Score Threshold: 1
Location: Body
```

**Example -- Credit Card Number with Luhn:**
```
Classification Name: PCI - Credit Card Number
Definition Type: Advanced Pattern
Pattern: \b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b
Validator: Luhn Algorithm
Score Threshold: 1
Location: Body
```

**Example -- IBAN with BIN:**
```
Classification Name: Financial - IBAN
Definition Type: Advanced Pattern
Pattern: \b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}([A-Z0-9]?){0,16}\b
Validator: None
Score Threshold: 2
Location: Body
```

**Example -- AWS Access Key:**
```
Classification Name: DevOps - AWS Key
Definition Type: Advanced Pattern
Pattern: \bAKIA[0-9A-Z]{16}\b
Validator: None
Score Threshold: 1
Location: Body
```

**Example -- Internal Document ID:**
```
Classification Name: Internal - Document ID
Definition Type: Advanced Pattern
Pattern: \bDOC-[A-Z]{3}-\d{6}\b
Validator: None
Score Threshold: 1
Location: Body
```

### 1.3 Keyword Classifications

**What:** Simple string matching. A keyword is a literal string value that triggers when found in content.

**Navigation:** Policy > DLP Policy > Classifications > Create Classification > Keyword

**Example:**
```
Classification Name: Classification Labels - Confidential
Definition Type: Keyword
Keyword: CONFIDENTIAL
Score Threshold: 1
Location: Header, Footer
```

### 1.4 Proximity Classifications

**What:** Combines two definition types and requires them to appear within a configurable character distance.

**Navigation:** Policy > DLP Policy > Classifications > Create Classification (with Proximity enabled)

**Workflow:**
1. Create a classification with an Advanced Pattern (e.g., SSN regex)
2. Enable **Proximity**
3. Select the second definition type (e.g., Keyword "social security")
4. Set **Proximity Distance**: 1-10000 characters
5. Set **Direction**: Before / After / Both

**Example -- SSN Near Keyword:**
```
Classification Name: PII - SSN with Context
Primary: Advanced Pattern (\b\d{3}-\d{2}-\d{4}\b)
Proximity: Keyword "social security" OR "SSN"
Distance: 100 characters
Direction: Both (before or after)
```

**Example -- Credit Card Near Card Keyword:**
```
Classification Name: PCI - CCN with Context
Primary: Advanced Pattern (credit card regex with Luhn)
Proximity: Dictionary (card number, credit card, visa, mastercard, amex)
Distance: 150 characters
Direction: Both
```

### 1.5 EDM (Exact Data Match) Classifications

**What:** Fingerprinted structured data from CSV files. Matches exact values from databases.

**Workflow:**
1. **Prepare CSV source file** with sensitive data (SSN, names, account numbers)
2. **Install DLP Integrator v6.4.0+** on secure Windows/Linux server
3. **Create Enhanced Fingerprint:**
   - Navigate to Policy > DLP Policy > Fingerprints > EDM
   - Click Create Fingerprint > Structured Fingerprint > Create Enhanced Fingerprint
   - Enter path to CSV/TSV source file
   - Configure column types and indexing
4. **Upload fingerprint** to Skyhigh Security cloud
5. **Create classification** referencing the EDM fingerprint

**Example:**
```
EDM Fingerprint Name: Customer PII Database
Source: customer_records.csv
Columns: SSN (primary), FirstName, LastName, DOB, Email
Classification Name: PII - Customer Database Match
Definition Type: EDM Fingerprint
Fingerprint: Customer PII Database
Score Threshold: 1
```

### 1.6 IDM (Index Document Matching) Classifications

**What:** Fingerprinted unstructured documents. Matches complete or partial copies of indexed documents.

**Workflow:**
1. **Install DLP Integrator v6.4.0+** (includes IDMTrain tool)
2. **Prepare document collection** (contracts, patents, proprietary docs)
3. **Run IDMTrain** to create fingerprint index
4. **Upload IDM fingerprint** to Skyhigh Security
5. **Create classification** with Unstructured Match Condition
6. **Configure match percentage** (full document or partial match %)

**Example:**
```
IDM Fingerprint Name: Patent Application Drafts
Source: 50 patent draft documents
Match Percentage: 30% (partial match threshold)
Classification Name: IP - Patent Draft Match
Definition Type: IDM Fingerprint
```

### 1.7 ML Auto Classifier Classifications

**What:** Pre-trained ML models that automatically detect sensitive content types.

**Navigation:** Policy > DLP Policy > Classifications > Create Classification > ML Auto Classifier

**Available Text Classifiers:**
- Financial Reports / Financial Statements
- Patient Records
- Patents
- Source Code

**Available Image Classifiers:**
- ID Documents (passports, driver licenses)
- Credit Cards
- Checks

**Example:**
```
Classification Name: Financial - ML Auto Detect
Definition Type: ML Auto Classifier
Classifier: Financial Reports/Statements
Location: Body
```

**Example:**
```
Classification Name: Healthcare - ML Patient Records
Definition Type: ML Auto Classifier
Classifier: Patient Records
Location: Body
```

---

## Level 2: Sanctioned DLP Policies

### 2.1 Policy Creation

**Navigation:** Policy > DLP Policy > Policies > Create Policy

**Two creation paths:**

**Path A: Policy Wizard (Guided)**
1. Navigate to Policy > DLP Policy
2. Click **Create a DLP Policy using the Policy Wizard**
3. Follow wizard steps:
   - Step 1: Name, description, status
   - Step 2: Select policy template (or start blank)
   - Step 3: Configure rules
   - Step 4: Configure exceptions
   - Step 5: Configure response actions
   - Step 6: Review and save

**Path B: Manual Creation**
1. Navigate to Policy > DLP Policy > Policies
2. Click **Create Policy**
3. Configure each section manually

**Policy Fields:**

| Field | Type | Required | Values |
|-------|------|----------|--------|
| Policy Name | Text | Yes | Max 255 chars |
| Description | Text | No | Free text |
| Status | Toggle | Yes | Enabled / Disabled |
| Scope | Dropdown | Yes | All Services / Specific Services |

### 2.2 Rule Groups

Rule Groups are Boolean containers. Multiple Rule Groups within a policy are combined with **OR** logic.

**Workflow:**
1. In the policy editor, click **New Rule Group**
2. Name the rule group
3. Set the severity: **Critical / Major / Minor / Warning / Info**
4. Add rules within the group

**Example Rule Groups for a PCI Policy:**
```
Rule Group 1: "Credit Card Detection" (Severity: Critical)
  -> Rules within this group are AND'd together
  -> Rule A: Classification "PCI - CCN with Context" threshold 1
  -> Rule B: True File Type is NOT "image/*" (exclude images)

Rule Group 2: "Track Data Detection" (Severity: Critical)
  -> Rule A: Classification "PCI - Track Data" threshold 1

Rule Group 3: "Financial Keywords (Low Confidence)" (Severity: Minor)
  -> Rule A: Classification "Financial - Earnings Keywords" threshold 5

Policy evaluation:
  IF RuleGroup1 matches OR RuleGroup2 matches OR RuleGroup3 matches -> Policy triggers
  Severity of the triggered group determines response action
```

### 2.3 Rules Within Rule Groups

**Rule Types:**

| Rule Type | Matches On | When to Use |
|-----------|-----------|-------------|
| **Classification Rule** | Classification match (any definition type) | Most common; references a classification |
| **Keyword Rule** | Keyword match in content | Quick keyword detection without full classification |
| **User Risk Rule** | UEBA risk score of the user | Risk-adaptive enforcement |
| **Structured Fingerprint Rule** | EDM fingerprint match | Exact database record matching |
| **Unstructured Fingerprint Rule** | IDM fingerprint match | Document copy/derivative detection |

**Example -- Classification Rule:**
```
Rule Type: Classification
Classification: PII - US SSN
Threshold: 1 (one or more matches)
```

**Example -- User Risk Rule:**
```
Rule Type: User Risk
Risk Level: High
Condition: User has elevated risk score from UEBA
```

**Example -- Keyword Rule:**
```
Rule Type: Keyword
Keywords: "CONFIDENTIAL", "INTERNAL ONLY", "DO NOT DISTRIBUTE"
Match: Any keyword
```

**Example -- Structured Fingerprint Rule:**
```
Rule Type: Structured Fingerprint
Fingerprint: Customer PII Database
Match Columns: SSN + LastName (compound match)
```

**Example -- Unstructured Fingerprint Rule:**
```
Rule Type: Unstructured Fingerprint
Fingerprint: Patent Application Drafts
Match Percentage: 30%
```

### 2.4 Exceptions

Exceptions define WHEN the policy should NOT trigger, even if rules match.

**Workflow:**
1. In the policy editor, navigate to **Exceptions** section
2. Click **Add Exception**
3. Configure exception rule groups (same rule types as Rules section)
4. Exceptions use Boolean logic just like rules

**Example:**
```
Exception Rule Group: "Legal Team Exemption"
  Rule: Source User = legal-team@company.com
  Effect: Policy does not trigger for uploads by the legal team
```

**Example:**
```
Exception Rule Group: "Test Data Exemption"
  Rule: Keyword match "TEST DATA" or "SAMPLE" or "DUMMY"
  Effect: Documents containing test/sample markers are excluded
```

### 2.5 Response Actions

Response Actions define WHAT happens when a policy triggers.

**Available Actions:**

| Action | Channel Support | Description |
|--------|----------------|-------------|
| **Create Incident** | All | Logs the event as a DLP incident |
| **Email Notification** | All | Sends email to admin/manager/custom recipient |
| **Block** | Sanctioned, Shadow/Web | Prevents the data transfer |
| **Quarantine** | Sanctioned | Moves file to quarantine folder |
| **Encrypt** | Sanctioned | Applies encryption to the file |
| **Apply Label** | Sanctioned | Applies a classification label (e.g., AIP) |
| **Coach User** | Sanctioned, Shadow/Web | Shows user a coaching prompt |
| **Custom Action** | Varies | Webhook or custom integration |

**Conditional Response Actions (by Severity):**
```
IF severity = Critical:
  -> Block + Quarantine + Email Admin + Create Incident
IF severity = Major:
  -> Block + Email Admin + Create Incident
IF severity = Minor:
  -> Coach User + Create Incident
IF severity = Warning:
  -> Create Incident only
IF severity = Info:
  -> Log only
```

**Example:**
```
Response Actions for Policy "PCI Protection":
  Critical -> Block upload, Quarantine file, Email security@company.com
  Major -> Block upload, Email security@company.com
  Minor -> Create incident, Coach user with message: "This file may contain payment data"
```

---

## Level 3: Channel-Specific Workflows

### 3.1 Sanctioned Channel (CASB)

**What:** DLP enforcement on approved cloud services connected via API and/or inline proxy.

**How it works:**
1. CASB API scans cloud service content retroactively (API-based)
2. Lightning Link adds real-time inline enforcement (inline-based)
3. Both API and inline scans use the same DLP policies

**Configuration:**
- Policies are automatically active on all connected sanctioned services
- Scope can be narrowed to specific services in the policy

### 3.2 Shadow/Web Channel (SWG)

**What:** DLP enforcement on unmanaged cloud services and general web traffic via Secure Web Gateway.

**Configuration:**
1. Navigate to Policy > DLP Policy > Shadow/Web Policies
2. Create a Shadow/Web DLP Policy (separate from Sanctioned)
3. Classifications are shared; rules and response actions may differ
4. SWG inline proxy inspects traffic in real-time

### 3.3 Endpoint Channel (Trellix)

**What:** DLP enforcement on desktop applications, USB, clipboard, email clients via Trellix DLP agent.

**Configuration:**
1. Configure in Trellix ePO (separate management console)
2. Policies are synced from Skyhigh to Trellix via integration
3. Endpoint classifications may need to be recreated in Trellix format
4. See Trellix DLP documentation for endpoint-specific configuration

---

## End-to-End Workflow Summary

### Phase 1: Classification Foundation
1. Review built-in classifications and policy templates
2. Create custom classifications for organization-specific data
3. Add proximity matching to reduce false positives
4. (Optional) Set up EDM for database records
5. (Optional) Set up IDM for proprietary documents
6. (Optional) Enable ML Auto Classifiers

### Phase 2: Policy Construction
7. Choose creation path: Policy Wizard or manual
8. Create Rule Groups with appropriate severity levels
9. Add Rules within groups (Classification, Keyword, Fingerprint, User Risk)
10. Configure Boolean logic (AND/OR within groups; OR between groups)
11. Add Exceptions for known-good patterns

### Phase 3: Response Configuration
12. Configure Response Actions per severity level
13. Start with Create Incident (monitoring mode)
14. Add Coach User for medium-severity triggers
15. Reserve Block/Quarantine for high-confidence, critical patterns

### Phase 4: Channel Deployment
16. Activate policy on Sanctioned channel
17. Create matching Shadow/Web policy using same classifications
18. (Optional) Sync to Endpoint DLP via Trellix integration

### Phase 5: Monitor and Tune
19. Review DLP incidents on the Incidents page
20. Identify false positives; refine classifications with proximity, validators
21. Identify false negatives; broaden classifications or add new patterns
22. Escalate from monitoring to blocking for validated patterns
23. Use Rule Evaluation tool (S14) to test changes before deploying

---

## Policy Templates Available

| Template | Compliance | Classifications Included | Rules Included |
|----------|-----------|------------------------|----------------|
| PCI-DSS | Payment Card Industry | Credit card numbers, track data, CVV | Block credit card data in uploads |
| HIPAA | Healthcare | SSN, MRN, PHI indicators, ICD codes | Alert on PHI in cloud services |
| GDPR | EU Privacy | EU national IDs, IBAN, EU passport, email+name combos | Alert on personal data transfers |
| GLBA | Financial | Account numbers, SSN, financial terms | Block financial data exfiltration |
| SOX | Financial Reporting | Financial statements, audit terms, insider terms | Alert on financial report sharing |

---

## Cross-Channel Enforcement Matrix

| Classification | Sanctioned (CASB) | Shadow/Web (SWG) | Endpoint (Trellix) |
|---------------|-------------------|-------------------|-------------------|
| Dictionary | Yes | Yes | Yes (recreate in ePO) |
| Advanced Pattern | Yes | Yes | Yes (recreate in ePO) |
| Keyword | Yes | Yes | Yes (recreate in ePO) |
| EDM | Yes | Yes | Partial (ePO has own EDM) |
| IDM | Yes | Yes | Partial (ePO has own fingerprinting) |
| ML Auto Classifier | Yes | Yes | No (Skyhigh-only) |
| Document Properties | Yes | Yes | Yes (ePO equivalent) |
| File Name Set | Yes | Yes | Yes (ePO equivalent) |
| Proximity | Yes | Yes | No direct equivalent |
| User Risk (UEBA) | Yes | Yes | No (UEBA is cloud-only) |

---

## Recommended Architecture by Organization Size

### Small (< 500 users)
- Use policy templates (PCI, HIPAA, GDPR) -- customize minimally
- 3-5 classifications with proximity matching
- One sanctioned policy, one shadow/web policy
- Monitor for 30 days before blocking
- Skip endpoint DLP initially

### Medium (500-5000 users)
- Templates + custom classifications for proprietary data
- 10-15 classifications
- EDM for customer database
- Multiple policies per channel with severity tiers
- Coach users on medium-severity violations
- Add endpoint DLP if desktop data movements are a concern

### Large (5000+ users)
- Full classification library including EDM, IDM, ML Auto Classifiers
- 20+ classifications with proximity and validators
- Multiple policies per channel per business unit
- Conditional response actions by severity
- Full endpoint DLP via Trellix integration
- Automated incident management
- Policy templates customized per region/business unit
