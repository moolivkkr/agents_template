# Authoring Policies -- Complete Workflow
## Palo Alto Enterprise DLP (Cloud-Delivered)

> Capability: authoring-policies | Generated: 2026-05-21
> Sources: doc-corpus (38 sources), video-intelligence (18 videos), api-intelligence (3 API surfaces, 22+ endpoints)

---

## Overview

Policy authoring in Palo Alto Enterprise DLP is the process of defining what sensitive data to detect, how to detect it, and what enforcement action to take. The output is a deployable configuration that, once pushed to enforcement points (NGFW, Prisma Access, Cloud NGFW, SaaS Security, or Cortex XDR), inspects network traffic and endpoint activity for sensitive data and takes configured actions (alert or block).

Enterprise DLP uses a cloud-delivered inspection engine. The enforcement point forwards matching traffic to the Palo Alto DLP cloud, which renders a verdict using 500+ predefined patterns, ML-based classifiers, exact data matching, and custom patterns. This architecture means DLP intelligence is continuously updated without requiring appliance upgrades.

**What policy authoring produces:**
- Data Patterns that define HOW to detect sensitive content (regex, ML, EDM, document fingerprint)
- Data Profiles that group patterns with match criteria (occurrence thresholds, confidence levels, AND/OR logic)
- DLP Rules (SCM) or Data Filtering Profiles (Panorama) that define enforcement behavior (traffic scope, file types, action)
- Security Policy Rules that attach DLP enforcement to traffic flows
- A pushed configuration deployed to enforcement points

---

## Complexity Score

**Rating: MODERATE**

**Justification:**
- 5-level hierarchy (Patterns > Profiles > DLP Rules > Security Rules > Push) -- one level fewer than Trellix
- Single cloud-delivered engine shared across all enforcement points
- 500+ predefined patterns reduce custom configuration burden
- ML-based patterns significantly reduce false positive tuning work
- However: three management surfaces (SCM, Panorama, DLP App) with different terminology
- EDM and Trainable Classifiers add significant complexity when used

---

## Policy Hierarchy

```
Level 1: Data Patterns
    Predefined Regex (500+) | Predefined ML-Based | Custom Regex (Basic/Weighted) | File Property
    |
Level 2: Data Profiles
    Standard | Nested | Granular
    (Each profile = collection of patterns + match criteria)
    |
Level 3: DLP Rules / Data Filtering Profiles
    DLP Rule (SCM) | Data Filtering Profile (Panorama)
    (Traffic scope + file types + action + log severity)
    |
Level 4: Security Policy Rules
    Security Rule + Profile Group (containing DLP rule)
    (Source/Destination/App/Service matching)
    |
Level 5: Deployment
    Commit + Push to enforcement points
```

---

## Management Surfaces

Enterprise DLP can be configured through three management surfaces. All share the same cloud-delivered DLP engine and data pattern/profile library.

| Surface | Primary Use Case | Navigation to DLP |
|---------|-----------------|------------------|
| **DLP App** (via Hub) | Centralized pattern/profile management | Hub > Enterprise DLP |
| **Strata Cloud Manager (SCM)** | Prisma Access and Cloud NGFW management | Configuration > Security Services > DLP |
| **Panorama** | On-prem NGFW management | Objects > Security Profiles > Data Filtering |

**Recommendation:** Use the DLP App for pattern/profile management (Level 1-2). Use SCM or Panorama for rule/policy management (Level 3-5) depending on your enforcement point type.

---

## Level 1: Data Patterns

Data patterns are the atomic detection units. Each pattern defines ONE method of identifying sensitive content.

### 1.1 Predefined Regex Data Patterns

**What:** 500+ built-in patterns for common sensitive data types (SSN, CCN, IBAN, passport numbers, etc.) using regular expressions.

**Navigation:** DLP App > Data Patterns > Predefined

**Key Characteristics:**
- Cannot be deleted or fundamentally modified
- Can have custom match criteria ADDED to predefined patterns (see S10)
- Enabled/disabled per data profile (not globally)
- Use RE2 regex engine

**Examples of predefined regex patterns:**

| Pattern Name | Detects | Regex Complexity |
|-------------|---------|-----------------|
| Credit Card Number | Visa, MC, Amex, Discover card numbers | Multi-pattern with Luhn validation |
| Social Security Number (US) | US SSN in XXX-XX-XXXX format | Pattern with format validation |
| IBAN (International) | International bank account numbers | Country-specific format validation |
| Passport Number (US) | US passport numbers | Alphanumeric pattern |
| Medical Record Number | MRN formats across healthcare systems | Flexible pattern matching |
| AWS Access Key | AWS IAM access key IDs | Prefix-based pattern (AKIA...) |
| Source Code (Java/Python/C++) | Programming language constructs | Keyword + structure detection |

### 1.2 Predefined ML-Based Data Patterns

**What:** Machine learning models that augment regex patterns with contextual understanding, reducing false positives by up to 10x.

**Navigation:** DLP App > Data Patterns > Predefined (ML icon indicator)

**Key Characteristics:**
- Support ONLY "Any" occurrence condition
- Offer ONLY High or Low confidence levels
- Cannot be duplicated or custom-configured
- Use LLM-powered ground truth + context-aware ML models
- 5th generation DNN models (as of 2025)
- Palo Alto's data scientists continuously retrain models

**Configuration constraints:**
```
Occurrence: Any (FIXED -- cannot change)
Confidence: High | Low (ONLY two options)
Custom match criteria: NOT SUPPORTED
Duplication: NOT SUPPORTED
```

> **GOTCHA:** If you need occurrence-based thresholds (e.g., "5 or more SSNs"), you MUST use the regex-based version of the pattern, not the ML-based version.

### 1.3 Custom Regex Data Patterns (Basic)

**What:** User-defined regex patterns for detecting organization-specific sensitive data.

**Navigation:** DLP App > Data Patterns > Custom > Create Data Pattern

**Workflow:**
1. Click **Create Data Pattern**
2. Enter pattern name and description
3. Select **Pattern Type: Regular Expression**
4. Select **Mode: Basic**
5. Enter one regex expression per line (up to 100 lines)
6. Configure match settings:
   - Occurrence: Any | Specific count (1-999)
   - Confidence: High | Low
7. Click **Save**

**Example -- Internal Project Code:**
```
Pattern Name: Internal Project Codes
Mode: Basic
Expression: \b(PROJ|PRJ)-[A-Z]{2,4}-\d{4,6}\b
Occurrence: 1
Confidence: High
```

**Example -- Custom Employee ID:**
```
Pattern Name: Employee ID Format
Mode: Basic
Expression: \bEMP-\d{6}\b
Occurrence: Any
Confidence: High
```

### 1.4 Custom Regex Data Patterns (Weighted)

**What:** Multi-expression patterns where each regex line is assigned a weight score. When the cumulative score exceeds a threshold, the pattern matches.

**Navigation:** DLP App > Data Patterns > Custom > Create Data Pattern

**Workflow:**
1. Click **Create Data Pattern**
2. Enter pattern name and description
3. Select **Pattern Type: Regular Expression**
4. Select **Mode: Weighted**
5. For each line, enter: `regex_expression | delimiter | weight_score`
6. Set the **Score Threshold** (cumulative score that triggers a match)
7. Click **Save**

**Weight scores:** -9999 (lowest) to 9999 (highest)

**Example -- Financial Document Detection:**
```
Pattern Name: Financial Document Indicators
Mode: Weighted
Score Threshold: 15

Expressions:
  \b(CONFIDENTIAL|RESTRICTED)\b          | 10    (strong indicator)
  \b(revenue|profit|loss|EBITDA)\b       |  5    (moderate indicator)
  \b(Q[1-4]\s+20\d{2})\b                |  5    (quarter reference)
  \b(draft|internal use only)\b          |  3    (weak indicator)
  \b(public|press release)\b             | -10   (negative indicator -- public docs)
```

In this example, a document with "CONFIDENTIAL" (10) + "revenue" (5) = 15, which meets the threshold. But a document with "revenue" (5) + "public" (-10) = -5, which does NOT meet the threshold.

**Example -- Source Code Detection (Weighted):**
```
Pattern Name: Proprietary Source Code
Mode: Weighted
Score Threshold: 20

Expressions:
  \b(import|from|require|include)\b      |  3    (code import statement)
  \b(function|def|class|interface)\b     |  5    (code structure)
  \b(Copyright\s+\d{4})\b               | 10    (copyright notice)
  \b(TODO|FIXME|HACK)\b                 |  3    (developer comments)
  \b(MIT License|Apache License|GPL)\b   | -15   (open source -- not proprietary)
```

### 1.5 File Property Data Patterns

**What:** Patterns that match on file metadata (author, title, subject, keywords) rather than content.

**Navigation:** DLP App > Data Patterns > Custom > Create Data Pattern > File Property

**Example:**
```
Pattern Name: Executive Authored Documents
Property: Author
Match: Contains
Value: CEO|CFO|CTO|VP
```

### 1.6 Exact Data Matching (EDM)

**What:** Fingerprinting structured data (database exports) using SHA256 hashing. Matches exact values from customer databases, employee records, patient records, etc. with near-zero false positives.

**Workflow:**
1. **Prepare source data:** Export sensitive records to CSV/TSV format
2. **Install EDM CLI App:** Download from DLP App > EDM section (Windows or Linux)
3. **Hash and encrypt:** Run EDM CLI App against the CSV file
   - SHA256 hashes each field value
   - AES-256 encrypts the entire dataset
   - Saves as encrypted .zip file
4. **Upload to Enterprise DLP:** Upload the encrypted .zip via DLP App or API
5. **Create EDM data pattern:** Reference the uploaded dataset in a data pattern
6. **Add to data profile:** Include the EDM pattern in a data profile

**Interactive mode command:**
```bash
./edm-cli --interactive
# Follow prompts to select CSV, configure columns, hash, encrypt, upload
```

**Configuration file mode:**
```json
{
  "source_file": "/path/to/customer_records.csv",
  "delimiter": ",",
  "columns": [
    {"name": "ssn", "type": "SSN", "primary": true},
    {"name": "first_name", "type": "NAME"},
    {"name": "last_name", "type": "NAME"},
    {"name": "dob", "type": "DATE"},
    {"name": "account_number", "type": "CUSTOM"}
  ],
  "output_file": "/path/to/encrypted_edm.zip"
}
```

> **SECURITY:** Raw data never leaves your network. Only SHA256 hashes (encrypted with AES-256) are uploaded to the DLP cloud.

### 1.7 Custom Document Types (Trainable Classifiers)

**What:** Upload samples of proprietary document types (contracts, patents, financial reports) to train an ML classifier that detects similar documents.

**Workflow:**
1. **Collect training documents:** Minimum 20 (recommended 50+) per document type
2. **Prepare positive set:** Documents that ARE the target type
3. **Prepare negative set:** Documents that are NOT the target type
4. **Create .zip:** Package documents into a .zip file (text files only, 500+ chars each)
5. **Upload:** DLP App > Custom Document Types > Upload
6. **Test:** Upload a test document to verify classification accuracy
7. **Add to data profile:** Include the custom document type in a data profile

**Requirements:**
- Minimum 20 files in the .zip
- Recommended 50+ for accuracy
- All files must be text-extractable (not scanned images)
- Each file must have 500+ characters
- Must include positive AND negative training sets

---

## Level 2: Data Profiles

Data profiles aggregate data patterns into named, reusable collections with match criteria.

### 2.1 Standard Data Profiles

**What:** A collection of one or more data patterns with match criteria (occurrence thresholds, confidence levels, AND/OR logic).

**Navigation:** DLP App > Data Profiles > Create Data Profile

**Workflow:**
1. Click **Create Data Profile**
2. Enter profile name and description
3. Click **Add Match Criteria**
4. For each match criterion:
   - Select a data pattern
   - Set occurrence: Any | Specific count
   - Set confidence: High | Low (for ML patterns)
   - Set detection type: Cloud Only | Local + Cloud
5. Set match logic between criteria: **AND** (all must match) or **OR** (any must match)
6. Click **Save**

**Example -- PCI-DSS Compliance Profile:**
```
Profile Name: PCI-DSS - Payment Card Data
Description: Detects payment card data per PCI-DSS requirements

Match Criteria:
  1. Credit Card Number (predefined, occurrence: Any, confidence: High)
  2. Credit Card Track Data (predefined, occurrence: Any)
  3. Credit Card Magnetic Stripe (predefined, occurrence: Any)

Match Logic: OR (any criterion triggers the profile)
```

**Example -- HIPAA PHI Profile:**
```
Profile Name: HIPAA - Protected Health Information
Description: Detects PHI per HIPAA requirements

Match Criteria:
  1. Social Security Number (ML-based, confidence: High)
  2. Medical Record Number (predefined, occurrence: Any)
  3. ICD-10 Code (predefined, occurrence: 3 or more)
  4. Patient Name + DOB (EDM dataset, occurrence: Any)

Match Logic: OR
```

**Example -- Intellectual Property Profile:**
```
Profile Name: IP Protection - Source Code + Trade Secrets
Description: Detects proprietary source code and trade secrets

Match Criteria:
  1. Proprietary Source Code (custom weighted regex, score threshold: 20)
  2. Internal Project Codes (custom basic regex, occurrence: 3+)
  3. Patent Draft Document Type (custom trainable classifier)

Match Logic: OR
```

### 2.2 Nested Data Profiles

**What:** A profile that contains other profiles as children. When any child profile matches, the parent profile triggers.

**Navigation:** DLP App > Data Profiles > Create Data Profile > Nested

**Use case:** Consolidate multiple domain-specific profiles (PCI-DSS, HIPAA, GDPR) into one "All Compliance" nested profile. Attach the single nested profile to a security rule instead of creating three separate rules.

**Example:**
```
Nested Profile Name: All Compliance Data
Children:
  1. PCI-DSS - Payment Card Data
  2. HIPAA - Protected Health Information
  3. GDPR - EU Personal Data
  4. IP Protection - Source Code + Trade Secrets

Evaluation: OR (any child profile match triggers the parent)
```

### 2.3 Granular Data Profiles

**What:** Profiles where each match criterion can have its own response action, enabling differentiated enforcement within a single security rule.

**Navigation:** DLP App > Data Profiles > Create Data Profile > Granular

**Example:**
```
Granular Profile Name: Tiered Data Protection
Match Criteria:
  1. Credit Card Number -> Action: Block, Severity: Critical
  2. Social Security Number -> Action: Alert, Severity: High
  3. Internal Project Codes -> Action: Log Only, Severity: Medium

Note: All three criteria in ONE profile, ONE security rule, different actions.
```

---

## Level 3: DLP Enforcement Rules

### 3.1 DLP Rule (Strata Cloud Manager)

**What:** Defines the traffic scope, file types, and enforcement action for a data profile.

**Navigation:** SCM > Configuration > Security Services > Data Loss Prevention > Add Rule

**Workflow:**
1. Click **Add Rule**
2. Configure rule fields:

| Field | Description | Values |
|-------|------------|--------|
| Rule Name | Descriptive name | Free text |
| Data Profile | Profile to enforce | Select from available profiles |
| Direction | Which traffic direction to inspect | Upload / Download / Both |
| File Types | Which file types to inspect | All / Specific types (Office, PDF, Text, etc.) |
| Action | What to do on match | Alert / Block / Allow (log only) |
| Log Severity | Syslog severity for the match | Critical / High / Medium / Low / Informational |

3. Click **Save**

**Example -- Block Credit Cards in Uploads:**
```
Rule Name: Block PCI Data in Web Uploads
Data Profile: PCI-DSS - Payment Card Data
Direction: Upload
File Types: All
Action: Block
Log Severity: Critical
```

**Example -- Alert on HIPAA Data:**
```
Rule Name: Alert on PHI in All Directions
Data Profile: HIPAA - Protected Health Information
Direction: Both
File Types: All
Action: Alert
Log Severity: High
```

**Example -- Block Source Code to AI Apps:**
```
Rule Name: Block IP Leakage to GenAI
Data Profile: IP Protection - Source Code + Trade Secrets
Direction: Upload
File Types: All
Action: Block
Log Severity: Critical
```

### 3.2 Data Filtering Profile (Panorama)

**What:** The Panorama equivalent of a DLP Rule. Configured under Objects > Security Profiles.

**Navigation:** Panorama > Objects > Security Profiles > Data Filtering > Add

**Workflow:**
1. Click **Add** to create a new Data Filtering Profile
2. Enter profile name
3. Add rules within the profile:

| Field | Description |
|-------|------------|
| Data Profile | Select the Enterprise DLP data profile |
| Applications | Which applications to inspect (Any / Specific) |
| File Types | Which file types to inspect |
| Direction | Upload / Download / Both |
| Alert Threshold | Number of pattern matches before alerting |
| Block Threshold | Number of pattern matches before blocking |
| Log Severity | Critical / High / Medium / Low / Informational |

4. Click **OK** to save

> **Note:** The Panorama Data Filtering Profile supports threshold-based escalation (alert at 3 matches, block at 10 matches) which is not available in the SCM DLP Rule interface.

### 3.3 Endpoint DLP Policy Rule (Cortex XDR)

**What:** DLP enforcement on the endpoint device, managed through Cortex XDR.

**Navigation:** Cortex XDR > Policy > DLP > Add Rule

**Key Differences from Network DLP:**
- Classification runs entirely on the endpoint (offline capable)
- Monitors desktop applications, copy/paste, file operations
- Real-time user prompts (coaching, not just blocking)
- Managed separately from network DLP rules

---

## Level 4: Security Policy Rules

### 4.1 Profile Groups

**What:** Container that bundles the DLP rule with other security profiles (Antivirus, Anti-Spyware, URL Filtering, etc.) for attachment to a security rule.

**Navigation:** SCM > Configuration > Security Services > Profile Groups > Add

**Example:**
```
Profile Group Name: Standard Security + DLP
Profiles:
  - Antivirus: default
  - Anti-Spyware: default
  - URL Filtering: default
  - Data Loss Prevention: Block PCI Data in Web Uploads
  - File Blocking: default
  - WildFire Analysis: default
```

### 4.2 Security Policy Rule

**What:** The traffic matching rule that applies the Profile Group to specific traffic flows.

**Navigation:** SCM > Configuration > Security Services > Security Policy > Add Rule

**Example -- DLP for Internet Access:**
```
Rule Name: Corporate Internet Access with DLP
Source Zone: Trust
Destination Zone: Untrust
Source Address: Any
Destination Address: Any
Application: Any
Service: application-default
Action: Allow
Profile Group: Standard Security + DLP
```

**Example -- DLP for AI Applications:**
```
Rule Name: Block Sensitive Data to AI Apps
Source Zone: Trust
Destination Zone: Untrust
Source Address: Any
Destination Address: Any
Application: openai-chatgpt, github-copilot, google-bard
Service: application-default
Action: Allow
Profile Group: AI App Security + Strict DLP
```

**Example -- DLP for SaaS Applications:**
```
Rule Name: Monitor Data in SaaS Uploads
Source Zone: Trust
Destination Zone: Untrust
Source Address: Any
Destination Address: Any
Application: office365-base, google-drive-base, box-upload
Service: application-default
Action: Allow
Profile Group: SaaS Security + Alert DLP
```

---

## Level 5: Deployment

### 5.1 Push Configuration (SCM)

1. Review pending changes in SCM
2. Click **Push Config**
3. Select scope (Prisma Access tenant / NGFW device group / Cloud NGFW)
4. Confirm the push
5. Monitor deployment status

### 5.2 Commit and Push (Panorama)

1. Click **Commit** to save changes to Panorama
2. Click **Push to Devices**
3. Select target device groups or template stacks
4. Monitor commit/push status on each device

---

## End-to-End Workflow Summary

### Phase 1: Pattern Foundation
1. Review predefined patterns (500+ built-in)
2. Create custom patterns for organization-specific data
3. (Optional) Set up EDM for database records
4. (Optional) Upload custom document types for trainable classifiers

### Phase 2: Profile Composition
5. Create data profiles grouping relevant patterns
6. Configure match criteria (occurrence, confidence, AND/OR)
7. (Optional) Create nested profiles for consolidation
8. (Optional) Create granular profiles for differentiated actions

### Phase 3: Enforcement Rules
9. Create DLP rules (SCM) or Data Filtering Profiles (Panorama)
10. Configure traffic scope, file types, and actions
11. Start with Alert action (monitor mode)

### Phase 4: Security Policy
12. Create or update Profile Groups to include DLP rules
13. Create or update Security Policy Rules to apply Profile Groups
14. Order rules appropriately (most specific first)

### Phase 5: Deploy and Monitor
15. Push configuration to enforcement points
16. Monitor DLP incident dashboard for alerts
17. Tune patterns and profiles based on incident review
18. Escalate from Alert to Block for validated patterns

### Phase 6: Expand Coverage
19. Add Endpoint DLP via Cortex XDR
20. Add SaaS Security API-based scanning
21. Add AI application-specific rules
22. Set up automated incident management rules

---

## API Automation Path

For each level, the API equivalent:

| Level | Manual UI Path | API Path |
|-------|---------------|---------|
| Data Pattern | DLP App > Data Patterns > Create | `POST /v1/public/data-pattern` |
| Data Profile | DLP App > Data Profiles > Create | `POST /v1/public/data-profile` |
| DLP Rule | SCM > DLP > Add Rule | `POST /config/security/v1/data-loss-prevention` |
| Security Rule | SCM > Security Policy > Add | `POST /sse/config/v1/security-rules` |
| Push Config | SCM > Push Config | `POST /sse/config/v1/config-versions` |

Full API documentation: https://pan.dev/dlp/api/

---

## Cross-Enforcement Point Matrix

| Data Detection | NGFW | Prisma Access | Cloud NGFW | SaaS Security | Cortex XDR | Prisma Browser |
|---------------|------|--------------|-----------|--------------|-----------|----------------|
| Predefined Regex | Yes | Yes | Yes | Yes | Yes | Yes |
| Predefined ML | Yes | Yes | Yes | Yes | Yes | Yes |
| Custom Regex | Yes | Yes | Yes | Yes | Yes | Yes |
| Weighted Regex | Yes | Yes | Yes | Yes | Yes | Yes |
| EDM | Yes | Yes | Yes | Yes | TBD | Yes |
| Custom Document Types | Yes | Yes | Yes | Yes | TBD | Yes |
| File Property | Yes | Yes | Yes | Yes | Yes | Yes |
| Inline Inspection | Yes | Yes | Yes | No (API) | Yes | Yes |
| API-Based Scan | No | No | No | Yes | No | No |

---

## Recommended Architecture by Organization Size

### Small (< 500 users)
- Use predefined patterns only (skip custom)
- 3-5 data profiles (PCI, HIPAA, PII, IP, AI Apps)
- One nested profile for simplicity
- Alert mode for 30 days, then selective blocking

### Medium (500-5000 users)
- Predefined + custom regex patterns
- 10-15 data profiles by compliance domain
- Nested + granular profiles
- EDM for customer database
- Separate rules for AI applications
- Alert mode for 14 days, phased blocking

### Large (5000+ users)
- Full pattern library including EDM and trainable classifiers
- 20+ data profiles with granular actions
- Multiple nested profiles by business unit
- Endpoint DLP via Cortex XDR
- SaaS Security API scanning
- Automated incident management rules
- CI/CD policy management via API
