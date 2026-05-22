# Forcepoint DLP Policy Authoring -- Workflow

> Covers the end-to-end policy authoring pipeline: classifiers, DLP objects, policies, and deployment.
> Includes Risk-Adaptive Protection (RAP), Drip DLP, AI Mesh, and ARIA.

---

## Table of Contents

1. [Policy Authoring Mental Model](#1-policy-authoring-mental-model)
2. [Stage 1: Content Classifiers](#2-stage-1-content-classifiers)
3. [Stage 2: DLP Objects (Resources)](#3-stage-2-dlp-objects-resources)
4. [Stage 3: Rules](#4-stage-3-rules)
5. [Stage 4: Action Plans](#5-stage-4-action-plans)
6. [Stage 5: Policies](#6-stage-5-policies)
7. [Stage 6: Deployment](#7-stage-6-deployment)
8. [Risk-Adaptive Protection (RAP)](#8-risk-adaptive-protection-rap)
9. [Drip DLP (Cumulative Detection)](#9-drip-dlp-cumulative-detection)
10. [AI Mesh and ARIA](#10-ai-mesh-and-aria)
11. [Incident Workflow](#11-incident-workflow)
12. [Discovery Tasks](#12-discovery-tasks)
13. [End-to-End Examples](#13-end-to-end-examples)

---

## 1. Policy Authoring Mental Model

### 1.1 The Pipeline

```
Classifiers --> DLP Objects --> Rules --> Action Plans --> Policies --> Deploy
     |              |            |            |              |           |
  "WHAT data"  "WHO/WHERE"  "IF/THEN"   "DO what"    "Package"   "Activate"
```

### 1.2 Object Hierarchy

```
Policy
  |
  +-- Rule 1
  |     |
  |     +-- Condition (AND/OR/NOT logic over classifiers)
  |     |     +-- Classifier A (regex: SSN pattern)
  |     |     +-- Classifier B (dictionary: medical terms)
  |     |
  |     +-- Severity & Action (threshold -> action plan mapping)
  |     |     +-- >= 1 match  -> Low severity  -> Audit
  |     |     +-- >= 10 matches -> Medium       -> Audit & Notify
  |     |     +-- >= 50 matches -> High         -> Block
  |     |
  |     +-- Source (who/where data originates)
  |     +-- Destination (where data is going)
  |
  +-- Rule 2
  |     +-- ...
  |
  +-- Exception 1 (overrides Rule 1 for specific cases)
        +-- Condition
        +-- Action (typically: Permit)
```

### 1.3 Key Principle: Classify First, Policy Second

Forcepoint DLP separates **what you detect** (classifiers) from **how you respond** (policies). Classifiers are reusable building blocks. A single classifier can appear in multiple rules across multiple policies. This separation means:

- Updating a classifier's detection logic automatically updates every rule that references it.
- You can test classifiers independently before embedding them in enforcement policies.
- Teams can divide labor: data stewards own classifiers, security engineers own policies.

---

## 2. Stage 1: Content Classifiers

### 2.1 Classifier Types

| Type | Detects | Best For | Accuracy | Performance |
|------|---------|----------|----------|-------------|
| **Regex patterns** | Alphanumeric strings matching a pattern | SSNs, credit cards, IBANs, account numbers | Medium (needs validation) | Fast |
| **Key phrases** | Exact word/phrase matches (up to 255 chars) | "Confidential", "Internal Only", project code names | High for exact terms | Very fast |
| **Dictionaries** | Lists of terms by category | Medical terms, financial jargon, profanity lists | High for domain terms | Fast |
| **Scripts** | Custom detection logic (Lua scripts) | Complex multi-field validation, checksums | Very high (custom) | Variable |
| **File properties** | File name, type (magic number), size | Block .exe uploads, detect renamed files | High for file-level | Very fast |
| **File fingerprinting** | Whole or partial document matching | Contracts, design docs, source code | Very high | Medium |
| **Database fingerprinting** | Records from DB/CSV/Salesforce | Customer records, employee PII, patient data | Very high | Medium |
| **Machine learning** | Trained pattern recognition | Unstructured sensitive content, legal docs | High (when trained well) | Slower |
| **OCR** | Text extracted from images/scans | Screenshots, scanned docs, photos of screens | Medium-High | Slow |
| **AI Mesh (Classification labels)** | Document classification labels | Labeled documents: "Top Secret", "Restricted" | Very high | Fast (label lookup) |

### 2.2 Examples: Regex Patterns

**Example 1: US Social Security Number**
- Pattern: `\b\d{3}-\d{2}-\d{4}\b`
- WHY: Detects SSN format (123-45-6789) in text content
- GOTCHA: Also matches random 9-digit sequences -- combine with a dictionary classifier for "SSN", "Social Security", or similar context phrases to reduce false positives

**Example 2: Credit Card (Visa)**
- Pattern: `\b4[0-9]{12}(?:[0-9]{3})?\b`
- WHY: Visa cards start with 4, are 13 or 16 digits
- GOTCHA: Must add Luhn checksum validation via script classifier to avoid matching random 16-digit numbers

**Example 3: IBAN (International Bank Account Number)**
- Pattern: `\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}([A-Z0-9]?){0,16}\b`
- WHY: Covers most EU/international bank account formats
- GOTCHA: IBAN formats vary by country (DE = 22 chars, GB = 22 chars, FR = 27 chars) -- Forcepoint predefined classifiers handle per-country validation

**Example 4: Email Address**
- Pattern: `\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b`
- WHY: Detect email addresses in documents for PII detection
- GOTCHA: Very high match rate -- only useful when combined with other classifiers (e.g., AND medical-terms dictionary) to find PII in context

**Example 5: AWS Access Key**
- Pattern: `\bAKIA[0-9A-Z]{16}\b`
- WHY: Detects AWS access key IDs that could be leaked in code or documents
- GOTCHA: Pair with a secret key pattern `[A-Za-z0-9/+=]{40}` for more confidence

### 2.3 Examples: Dictionaries

**Example 1: Medical Conditions (Built-in)**
- Dictionary: "Medical Conditions" (pre-loaded)
- Contains: ~4,000 medical terms (diseases, conditions, procedures)
- WHY: Core component of PHI detection for HIPAA compliance
- GOTCHA: Medical terms appear in non-PHI contexts (news articles, research papers) -- combine with PII classifiers (patient names, MRNs) for precision

**Example 2: Financial Terms (Built-in)**
- Dictionary: "Financial Terms"
- Contains: Trading terms, account types, instrument names
- WHY: Detects financial analysis, trading strategies, earnings data
- GOTCHA: Very broad -- use for insider trading detection only when combined with time-based context (e.g., before earnings announcements)

**Example 3: Custom Profanity Filter**
- Dictionary: User-created with organization-specific offensive terms
- WHY: HR compliance, communication monitoring
- GOTCHA: Language evolves; update quarterly. Consider multi-language dictionaries.

**Example 4: Project Code Names**
- Dictionary: User-created with active project names ("Project Phoenix", "Moonshot")
- WHY: Detect discussion of confidential projects outside approved channels
- GOTCHA: Update when projects launch or are cancelled. Old code names generate noise.

**Example 5: Competitor Names**
- Dictionary: User-created with competitor company names, product names, exec names
- WHY: Detect potential competitive intelligence sharing
- GOTCHA: Common words as company names (e.g., "Apple", "Amazon") generate massive false positives -- use proximity matching with other context classifiers

### 2.4 Examples: File Properties

**Example 1: Block Executable Uploads**
- File type: .exe, .dll, .bat, .cmd, .ps1, .sh
- WHY: Prevent malware distribution or unauthorized software sharing
- GOTCHA: Forcepoint identifies files by magic number, not just extension -- a renamed .exe will still be detected by its PE header signature

**Example 2: Large File Exfiltration**
- File size: > 50 MB
- WHY: Detect bulk data exfiltration attempts
- GOTCHA: Legitimate large files (presentations, videos) will trigger -- combine with content classifiers for precision

**Example 3: CAD/Engineering Files**
- File type: .dwg, .step, .stl, .iges
- WHY: Protect intellectual property (manufacturing designs, engineering drawings)
- GOTCHA: These file types are binary; content inspection is limited to metadata. Combine with file fingerprinting for better coverage.

**Example 4: Source Code Files**
- File type: .py, .java, .go, .ts, .cpp
- WHY: Prevent proprietary source code from leaving the organization
- GOTCHA: Developers legitimately share code snippets; use source/destination filtering to allow internal collaboration while blocking external sharing

**Example 5: Encrypted/Password-Protected Files**
- File property: encrypted flag / password-protected
- WHY: Encrypted files may hide sensitive content from DLP inspection
- GOTCHA: Some organizations require encryption -- create an exception for approved encryption tools (BitLocker, VeraCrypt) and block only ad-hoc encryption

### 2.5 Examples: Fingerprinting

**Example 1: Database Fingerprint -- Customer Records**
- Source: CRM database (Salesforce, SQL Server)
- Fields fingerprinted: customer_name, email, phone, account_number (4 fields)
- WHY: Detect customer PII even when reformatted (e.g., copied into a spreadsheet, pasted into an email)
- GOTCHA: Scan at least 3 fields for accuracy. Single-field fingerprinting has high false positive rates. Set minimum threshold to 5 for single-field scans.

**Example 2: File Fingerprint -- Board Presentation**
- Source: File share path `\\server\board\presentations\`
- Method: Content similarity (70% confidence)
- WHY: Detect partial copies of board materials, even edited versions
- GOTCHA: Content similarity detects sections of the document; exact match only detects byte-identical copies. Always prefer content similarity for document protection.

**Example 3: Database Fingerprint -- Employee HR Records**
- Source: HRIS database
- Fields: employee_id, ssn, salary, hire_date, manager
- WHY: Prevent mass export of employee data
- GOTCHA: Maximum 32 fields per table. Select the most identifying fields. Schedule regular re-fingerprinting as data changes.

**Example 4: File Fingerprint -- Source Code Repository**
- Source: Git repository export (periodic)
- Method: Content similarity (60% confidence)
- WHY: Detect code theft even when variable names are changed
- GOTCHA: Requires periodic re-fingerprinting as code evolves. High-churn repositories may need weekly fingerprinting schedules.

**Example 5: Database Fingerprint -- Patient Records (HIPAA)**
- Source: EHR database
- Fields: patient_name, DOB, MRN, diagnosis_code, insurance_id
- WHY: HIPAA compliance -- detect ePHI in any channel
- GOTCHA: Fingerprinting captures point-in-time snapshots. New patients added after fingerprinting will not be detected until next scan. Schedule daily for high-volume healthcare systems.

### 2.6 Examples: Machine Learning

**Example 1: Legal Document Classification**
- Positive training set: 200 legal contracts, NDAs, settlement agreements
- Negative training set: 200 marketing materials, blog posts, press releases
- WHY: Detect legal documents without enumerating every possible pattern
- GOTCHA: Training quality determines accuracy. Minimum recommended: 100 positive + 100 negative examples. Retrain quarterly as document styles evolve.

**Example 2: Financial Report Detection**
- Positive: Quarterly earnings reports, board presentations, financial models
- Negative: Marketing decks, product documentation, training materials
- WHY: Protect pre-release financial data (insider trading prevention)
- GOTCHA: ML classifiers are slower than pattern-based classifiers. Do not use on high-volume, low-risk channels.

**Example 3: Resume/CV Detection**
- Positive: 150 employee resumes in various formats
- Negative: Job descriptions, company profiles, LinkedIn pages
- WHY: Detect employees preparing to leave (uploading resumes externally)
- GOTCHA: HR teams legitimately handle resumes -- create exceptions for HR department users and recruiting platforms

**Example 4: R&D Documents**
- Positive: Patent applications, research papers, lab notebooks
- Negative: Published research, public domain papers
- WHY: Protect pre-publication research and patent-pending work
- GOTCHA: Published vs. unpublished research can look very similar. High-quality negative training set is critical.

**Example 5: Customer Correspondence**
- Positive: Customer complaint emails, support tickets, escalation threads
- Negative: Internal discussion threads, meeting notes
- WHY: Detect customer data being shared outside support channels
- GOTCHA: Overlap between internal discussion about customers and actual customer correspondence causes false positives. Supplement with source filtering (only from support@domain).

---

## 3. Stage 2: DLP Objects (Resources)

### 3.1 Object Types

Resources define the **who**, **where**, and **what context** for rules.

| Object Type | Purpose | Examples |
|-------------|---------|----------|
| **Sources** | Where data originates | User groups, computers, IP ranges, domains, Active Directory OUs |
| **Destinations** | Where data is going | External email domains, cloud apps, USB drives, printers, URLs |
| **Endpoint groups** | Endpoint device groups | "Engineering laptops", "Executive devices", "BYOD" |
| **Business units** | Organizational mapping | Department, cost center, AD group |
| **Networks** | Network segments | "DMZ", "Guest WiFi", "VPN" |
| **Cloud applications** | SaaS apps | Office 365, Google Workspace, Box, Salesforce, Dropbox |

### 3.2 Examples: Sources

**Example 1: All Employees (Default)**
- Configuration: "All" sources selected (default)
- WHY: Start with all users to get baseline incident data
- GOTCHA: The default monitors everyone. Narrow sources after initial monitoring period to reduce noise.

**Example 2: Finance Department Only**
- Configuration: AD Group = "Finance" or OU = "Finance"
- WHY: Financial data policies apply only to finance users
- GOTCHA: Contractors in finance may not be in the AD group. Include contractor OUs too.

**Example 3: Executive Team**
- Configuration: Named user list (CEO, CFO, CTO, board members)
- WHY: High-value targets require stricter monitoring
- GOTCHA: Executive assistants also handle executive data -- include them or create companion rules.

**Example 4: Specific Subnet**
- Configuration: IP range 10.20.30.0/24
- WHY: R&D lab network has stricter data controls
- GOTCHA: Users on VPN may appear from different subnets. Combine with user-based sources for accuracy.

**Example 5: Endpoint Group -- Engineering Laptops**
- Configuration: Computer group "Engineering" (by computer name pattern or AD computer OU)
- WHY: Source code policies apply to engineering machines
- GOTCHA: Hot-desking or shared machines complicate this approach. Prefer user-based sources when possible.

### 3.3 Examples: Destinations

**Example 1: External Email Domains**
- Configuration: Destination = "All external email" (not @company.com)
- WHY: Detect data leaving via email to outside parties
- GOTCHA: Partner domains (suppliers, customers) may be legitimate. Create a "trusted external domains" list and exclude them.

**Example 2: Personal Cloud Storage**
- Configuration: Destination = cloud apps: Dropbox (personal), Google Drive (personal), iCloud
- WHY: Prevent shadow IT data storage
- GOTCHA: Corporate Dropbox/Google Workspace should be allowed. Distinguish personal vs. corporate cloud accounts.

**Example 3: USB/Removable Media**
- Configuration: Destination = "Removable storage devices"
- WHY: Prevent data theft via USB drives
- GOTCHA: Some USB devices are legitimate (encrypted backup drives, hardware tokens). Create an approved USB device whitelist by device ID.

**Example 4: Print Channel**
- Configuration: Destination = "Printers" (all or specific printer groups)
- WHY: Prevent printing of highly classified documents
- GOTCHA: Network printers are identified by name/IP. Local printers on endpoints require endpoint DLP agent.

**Example 5: AI/LLM Applications**
- Configuration: Destination = cloud apps: ChatGPT, Claude, Gemini, Copilot
- WHY: Prevent sensitive data from being pasted into AI chatbots
- GOTCHA: AI tools are increasingly embedded in business applications (e.g., Microsoft 365 Copilot). Web URL blocking alone may not catch embedded AI features.

**Example 6: Code Repositories**
- Configuration: Destination = URLs matching github.com/*, gitlab.com/*, bitbucket.org/* (excluding corporate org URLs)
- WHY: Prevent source code from being pushed to personal repositories
- GOTCHA: Allow corporate GitHub org URLs. Block only personal/unknown organizations.

**Example 7: FTP/SFTP Servers**
- Configuration: Destination = FTP protocol or specific FTP server IPs
- WHY: Legacy data transfer channels are common exfiltration paths
- GOTCHA: Some business processes legitimately use FTP. Whitelist approved FTP endpoints.

---

## 4. Stage 3: Rules

### 4.1 Rule Structure

A rule combines classifiers (conditions) with logic to define **when** to trigger:

```
Rule = Conditions + Logic + Threshold + Severity/Action + Source + Destination
```

### 4.2 Condition Logic Operators

| Operator | Meaning | Example |
|----------|---------|---------|
| AND | All conditions must match | SSN pattern AND "Social Security" phrase |
| OR | Any condition matches | Credit card pattern OR bank account pattern |
| NOT | Exclude matches | Medical terms AND NOT "published research" |
| Parentheses | Group logic | (SSN OR DOB) AND (medical terms) |

### 4.3 Examples: Rules

**Example 1: HIPAA PHI Detection**
- Condition: (SSN pattern OR MRN pattern OR DOB pattern) AND (Medical Conditions dictionary)
- Threshold: >= 1 match
- WHY: Detects ePHI when medical context is present alongside PII
- GOTCHA: Medical terms alone are not PHI. The AND with PII patterns is critical for HIPAA accuracy.

**Example 2: PCI Credit Card Bulk**
- Condition: Credit Card pattern (Luhn-validated)
- Threshold: >= 1 match -> Low/Audit; >= 10 matches -> Medium/Notify; >= 50 matches -> High/Block
- WHY: Single credit card in an email may be legitimate; 50 in a spreadsheet is a breach
- GOTCHA: Tiered thresholds are essential for PCI. Block only at high volumes to avoid disrupting legitimate business.

**Example 3: Source Code Exfiltration**
- Condition: (File property: .py OR .go OR .java OR .ts) AND (File fingerprint: company repo, 60% similarity)
- Source: Engineering department
- Destination: External (not corporate GitHub)
- WHY: Detects proprietary code being shared externally
- GOTCHA: Open-source contributions are legitimate. Create exceptions for approved open-source projects.

**Example 4: Executive Communication Protection**
- Condition: (Key phrase: "board meeting" OR "quarterly results" OR "acquisition target") AND (Source: Executive team)
- Destination: External email
- WHY: Protect privileged executive communications
- GOTCHA: Assistants forwarding calendar invites may trigger this. Tune phrases carefully.

**Example 5: GDPR Personal Data Cross-Border**
- Condition: (EU PII classifiers: national ID patterns for DE, FR, UK, IT, ES) OR (IBAN patterns)
- Source: EU office networks/users
- Destination: Non-EU destinations (by IP geolocation or cloud app region)
- WHY: GDPR restricts personal data transfer outside the EU
- GOTCHA: Adequacy decisions allow transfers to some non-EU countries (UK, Japan, etc.). Whitelist approved transfer destinations.

---

## 5. Stage 4: Action Plans

### 5.1 Available Actions

| Action | Channel | Description |
|--------|---------|-------------|
| **Audit incident** | All | Log the incident in the incident database (default, always selected) |
| **Permit** | All | Allow the transaction to proceed |
| **Block** | All | Prevent the transaction (block email, deny upload, prevent copy) |
| **Quarantine** | Email | Hold the message for administrator review before delivery |
| **Encrypt on release** | Email | Encrypt the message when released from quarantine |
| **Send email notification** | All | Notify designated recipients (manager, DLP team, data owner) |
| **Send syslog message** | All | Forward incident to SIEM/ticketing system |
| **Run endpoint remediation script** | Endpoint | Execute a custom script on the endpoint when incident occurs |
| **Notify end user** | Endpoint | Display a popup to the user explaining the policy violation |
| **Confirm/Justify** | Endpoint | Require user to provide justification before proceeding |
| **Custom actions** | Email, Network | Organization-defined actions (e.g., strip attachment, add disclaimer) |

### 5.2 Examples: Action Plans

**Example 1: Audit Only (Monitoring Phase)**
- Actions: Audit incident
- WHY: During initial policy rollout, audit-only mode lets you measure false positive rates without disrupting users
- GOTCHA: Audit-only policies still consume incident storage. Monitor incident volumes and adjust thresholds before enabling enforcement.

**Example 2: Audit & Notify Manager**
- Actions: Audit incident + Send email notification (to user's manager)
- WHY: Low-severity violations where awareness is the goal
- GOTCHA: High-volume policies can flood manager inboxes. Use digest notifications or escalation rules.

**Example 3: Block & Notify User**
- Actions: Block + Audit incident + Notify end user (popup)
- WHY: Prevent data loss while educating the user about the policy
- GOTCHA: Blocking without explanation causes support tickets. Always pair Block with a user notification explaining what was blocked and why.

**Example 4: Quarantine for Review**
- Actions: Quarantine + Audit incident + Send email notification (to DLP team)
- WHY: Email containing potential PII is held for human review before delivery
- GOTCHA: Quarantine creates operational overhead. Only use for high-severity, low-volume scenarios. Unreviewed quarantine queues cause business delays.

**Example 5: Block + Escalate + SIEM**
- Actions: Block + Audit incident + Send email notification (to CISO) + Send syslog message
- WHY: Critical violations (50+ credit cards, executive data exfiltration) require immediate attention
- GOTCHA: Reserve for highest severity only. Alert fatigue at this level undermines incident response.

**Example 6: Confirm/Justify (User Override)**
- Actions: Confirm/Justify + Audit incident
- WHY: User is warned about the policy and can proceed by providing a business justification
- GOTCHA: Justification text is logged in the incident. Review justifications periodically to detect policy abuse.

**Example 7: Endpoint Remediation Script**
- Actions: Run endpoint remediation script + Audit incident + Block
- WHY: Automatically move/delete/encrypt the offending file on the endpoint
- GOTCHA: Remediation scripts must be tested thoroughly. A buggy script running at scale can cause data loss or system instability.

---

## 6. Stage 5: Policies

### 6.1 Policy Types

| Type | Description | Use Case |
|------|-------------|----------|
| **Predefined** | Out-of-the-box, compliance-ready | HIPAA, PCI-DSS, GDPR, CCPA, SOX, etc. |
| **Custom** | User-created from scratch | Organization-specific data protection |
| **Cloned** | Copy of predefined, then customized | Compliance policy with org-specific adjustments |

### 6.2 Predefined Policy Categories

| Category | Example Policies | Classifier Count |
|----------|-----------------|------------------|
| Regulations, Compliance, and Standards | HIPAA, PCI-DSS, GDPR, CCPA, SOX, GLBA, FERPA | 100+ |
| Credit Cards | Visa, MasterCard, Amex, Discover, JCB, UnionPay | 20+ |
| Financial Data | Trading data, earnings reports, wire transfers | 50+ |
| Protected Health Information (PHI) | US PHI, UK PHI, Sweden PHI, India PHI | 40+ |
| Personally Identifiable Information (PII) | SSN, driver's license, passport (90+ countries) | 500+ |
| Company Confidential / IP | Source code, design documents, trade secrets | 30+ |
| National ID Numbers | Per-country formats (US, UK, DE, FR, AU, JP, etc.) | 200+ |
| Privacy Laws by Region | 160+ regional privacy regulations | 300+ |

**Total: 1,800+ predefined classifiers across 90+ countries and 160+ regions.**

### 6.3 Creating a Custom Policy: The 5-Tab Wizard

**Tab 1: General**
- Policy name and description
- Enable/disable toggle
- Policy category assignment

**Tab 2: Condition**
- Select content classifiers
- Build logic: AND / OR / NOT with parentheses
- Each condition references a classifier (regex, dictionary, fingerprint, ML, file property, etc.)

**Tab 3: Severity & Action**
- Map match thresholds to severity levels and action plans
- Define graduated response (e.g., 1 match = Low/Audit; 10 = Medium/Notify; 50 = High/Block)
- Configure cumulative/drip DLP settings (time window, accumulation threshold)
- RAP integration: 5 risk levels with independent action plans per level

**Tab 4: Source**
- Define who/where the rule applies (users, groups, OUs, computers, networks, IP ranges)
- Default: All sources

**Tab 5: Destination**
- Define where data is going (email domains, cloud apps, USB, printers, URLs, FTP)
- Default: All destinations

### 6.4 Examples: Complete Policies

**Example 1: HIPAA PHI Protection**
- Rules: 3 rules (PHI in email, PHI in cloud uploads, PHI on endpoints)
- Classifiers: SSN, MRN, DOB, Medical Conditions dictionary, HIPAA predefined classifiers
- Thresholds: 1 match = Audit; 5 = Notify compliance officer; 20 = Block
- Source: All users in healthcare OU
- Destination: External email, personal cloud apps, USB drives
- Exception: Encrypted email to approved insurance partners

**Example 2: PCI-DSS Credit Card Protection**
- Rules: 2 rules (credit card in transit, credit card at rest)
- Classifiers: Credit card patterns (Luhn-validated), PCI predefined classifiers
- Thresholds: 1 = Audit; 10 = Notify + quarantine email; 50 = Block all channels
- Source: All users
- Destination: All external destinations
- Exception: Payment processing team to approved merchant endpoints

**Example 3: Intellectual Property Protection**
- Rules: 4 rules (source code, design docs, patents, R&D data)
- Classifiers: File properties (.py, .go, .dwg), file fingerprints, ML (R&D docs), project name dictionary
- Thresholds: 1 = Audit; 3 = Notify manager; 1 (for fingerprinted docs) = Block
- Source: Engineering, R&D departments
- Destination: External (excluding approved partners)
- Exception: Open-source contribution list, approved vendor shares

**Example 4: GDPR EU Data Residency**
- Rules: 2 rules (PII cross-border, consent documents)
- Classifiers: EU national ID patterns (27 member states), IBAN, EU PII predefined
- Thresholds: 1 PII record = Audit; 10 = Notify DPO; 100 = Block
- Source: EU office users and EU cloud infrastructure
- Destination: Non-EU/non-adequate destinations
- Exception: Adequate countries (UK, Japan, Canada), Standard Contractual Clauses partners

**Example 5: Insider Threat Detection**
- Rules: 3 rules (bulk download, after-hours access, resignation-correlated)
- Classifiers: File size > 50MB, cumulative file count (Drip DLP), customer database fingerprint
- Thresholds: Cumulative: 100 files in 7 days = Notify security; 500 files = Block + escalate
- Source: All users (with RAP risk scoring)
- Destination: Personal email, personal cloud storage, USB drives
- Exception: IT backup operations, approved data migration projects

---

## 7. Stage 6: Deployment

### 7.1 How Deployment Works

Changes in Forcepoint Security Manager are **saved immediately** to the management server but are **NOT active** until explicitly deployed.

```
Edit policy --> Save (immediate, to mgmt server) --> Deploy (propagates to all components)
```

### 7.2 Deployment Process

1. Make policy/classifier/rule changes in the Security Manager UI
2. Click the **Deploy** button in the toolbar
3. Confirm the deployment when prompted
4. Monitor status table:
   - Each component shows: Processing -> Success or Failed
   - Components: Protector, agents, gateways, endpoint hosts, policy engine
5. Status of last deployment is shown via indicator next to Deploy button

### 7.3 Deployment Targets

| Component | What Gets Updated |
|-----------|-------------------|
| Policy Engine | Rule logic, classifiers, thresholds |
| Endpoint Agents | Endpoint DLP policies, fingerprint databases |
| Network Protector | Network DLP inspection rules |
| Email Gateway | Email-specific policies, quarantine rules |
| Cloud Gateway | Cloud application policies |
| Discovery Engine | Discovery task configurations |

### 7.4 Deployment via REST API

```
POST /dlp/rest/v1/deploy          # Trigger deployment
GET  /dlp/rest/v1/deploy/status   # Monitor rollout
```

### 7.5 Examples: Deployment Scenarios

**Example 1: First-Time Deployment (Audit Only)**
- Enable 3 predefined policies (HIPAA, PCI, GDPR) with Audit-only action plans
- Deploy to all components
- Monitor incidents for 2 weeks before adding enforcement actions
- WHY: Baseline false positive rates before blocking anything
- GOTCHA: Even audit-only policies generate incident load. Ensure incident database has sufficient storage.

**Example 2: Emergency Policy Push**
- Disable a misconfigured policy that is blocking legitimate business email
- Deploy immediately
- WHY: Business continuity requires fast policy changes
- GOTCHA: Deploy pushes ALL pending changes, not just the one you just edited. Review all pending changes before emergency deployments.

**Example 3: Staged Rollout**
- Create policy for Engineering department only (source = Engineering OU)
- Deploy and monitor for 1 week
- Expand source to "All users" after tuning
- Deploy again
- WHY: Limits blast radius during policy tuning
- GOTCHA: Users not in the initial source group have no protection during staged rollout. Communicate the rollout plan to stakeholders.

**Example 4: Scheduled Deployment (via API)**
- CI/CD pipeline exports policy from UAT environment
- Imports into production during maintenance window
- Triggers deploy via REST API
- Monitors status until Success
- WHY: Automated policy lifecycle management
- GOTCHA: API deployment is all-or-nothing. No partial deploy capability.

**Example 5: Post-Incident Policy Hardening**
- After a data breach incident, add a new rule to existing policy
- Reduce thresholds (from 10 to 1 match for Block action)
- Deploy immediately
- WHY: Rapid response to active threats
- GOTCHA: Aggressive thresholds after incidents cause false positive spikes. Plan to relax thresholds after the immediate threat passes.

---

## 8. Risk-Adaptive Protection (RAP)

### 8.1 What RAP Does

Risk-Adaptive Protection dynamically adjusts DLP policy enforcement based on real-time user risk scores calculated by Forcepoint's UEBA (User and Entity Behavior Analytics) engine.

### 8.2 How RAP Works

```
User behavior   -->  UEBA engine  -->  Risk score (1-5)  -->  DLP policy action
(login anomalies,    calculates        1 = Low risk           selected based on
 data access         real-time         5 = Critical risk      risk level
 patterns, etc.)     risk score
```

### 8.3 Five Risk Levels

| Risk Level | Label | Typical Action |
|------------|-------|----------------|
| 1 | Trusted | Permit (no restrictions) |
| 2 | Low | Audit only |
| 3 | Medium | Audit + Notify manager |
| 4 | High | Block + Investigate |
| 5 | Critical | Block + Escalate + SIEM alert |

### 8.4 RAP Configuration in Policy

In the Severity & Action tab, when RAP is enabled, each severity row has 5 action plan columns (one per risk level). This creates a **severity x risk matrix**:

```
                   Risk Level 1    Risk Level 2    Risk Level 3    Risk Level 4    Risk Level 5
Low severity       Permit          Audit           Audit+Notify    Block           Block+Escalate
Medium severity    Audit           Audit+Notify    Block           Block+Escalate  Block+Escalate
High severity      Block           Block           Block+Escalate  Block+Escalate  Block+Escalate
```

### 8.5 Examples: RAP-Enhanced Policies

**Example 1: Credit Card Policy with RAP**
- Risk Level 1 (trusted user): 10 credit cards in email = Audit only
- Risk Level 3 (medium risk user): 10 credit cards in email = Block + notify manager
- Risk Level 5 (critical risk user): 1 credit card in email = Block + escalate to CISO
- WHY: Trusted users in payment processing need latitude; flagged users need strict controls
- GOTCHA: RAP requires Forcepoint UEBA license and agent deployment. It does not work with DLP standalone.

**Example 2: Source Code with RAP**
- Risk Level 1-2: File fingerprint match = Audit
- Risk Level 3: File fingerprint match = Confirm/Justify
- Risk Level 4-5: File fingerprint match = Block
- WHY: Normal developers can be monitored; at-risk developers (e.g., recently gave notice) are blocked
- GOTCHA: HR events (resignation, PIP) should trigger risk score increases. Integrate with HR systems.

---

## 9. Drip DLP (Cumulative Detection)

### 9.1 What Drip DLP Does

Drip DLP detects **low-and-slow exfiltration** -- data being leaked one record at a time over extended periods, evading per-transaction detection thresholds.

### 9.2 How It Works

```
Transaction 1: 2 credit cards  (below threshold, Audit only)
Transaction 2: 3 credit cards  (below threshold, Audit only)
Transaction 3: 2 credit cards  (below threshold, Audit only)
                                 ------
         Cumulative: 7 credit cards in 24 hours --> Exceeds threshold (5) --> BLOCK
```

### 9.3 Configuration

In the Severity & Action tab:
1. Check **"Accumulate matches before creating an incident"**
2. Set the **time period** (sliding window that resets on each match)
3. Set the **threshold** ("Where there are at least N matches")
4. Choose match calculation method:
   - **Greatest number of matched conditions** -- only the largest single match count
   - **Sum of all matched conditions** -- cumulative total across all transactions

### 9.4 Examples: Drip DLP Policies

**Example 1: Credit Card Drip Detection**
- Classifier: Credit card (Luhn-validated)
- Per-transaction threshold: >= 1 = Audit
- Cumulative threshold: >= 20 in 7 days = Block + escalate
- WHY: An employee sending 2-3 credit cards per day for a week could exfiltrate hundreds
- GOTCHA: The time window is a sliding window that resets on each match. If matches stop, the window eventually expires and the count resets.

**Example 2: Customer Record Drip**
- Classifier: Database fingerprint (customer CRM)
- Per-transaction: >= 1 = Audit
- Cumulative: >= 100 records in 30 days = Block + notify security team
- WHY: Sales reps stealing customer lists before leaving
- GOTCHA: Legitimate CRM exports by admins will trigger. Create exceptions for CRM admin roles.

**Example 3: Source Code Snippet Drip**
- Classifier: File fingerprint (code repo, 50% similarity)
- Per-transaction: >= 1 = Audit
- Cumulative: >= 50 code files in 14 days = Block + escalate
- WHY: Developers copying code files one at a time to personal storage
- GOTCHA: Active developers touch many files daily. Set threshold high enough to avoid flagging normal work.

**Example 4: Document Accumulation**
- Classifier: File property (any Office document) AND destination (personal email)
- Per-transaction: >= 1 = Audit
- Cumulative: >= 25 documents in 7 days = Notify manager + require justification
- WHY: Employees sending company documents to personal email before resignation
- GOTCHA: Some roles legitimately email many documents externally (sales, consulting). Use source filtering.

**Example 5: PII Record Drip (GDPR)**
- Classifier: EU PII classifiers (national IDs, IBANs)
- Per-transaction: >= 1 = Audit
- Cumulative: >= 50 PII records in 30 days to non-EU destinations = Block + notify DPO
- WHY: GDPR compliance for gradual data transfer detection
- GOTCHA: Cross-border data transfers are often legitimate and contractual. The DPO notification allows human review before escalation.

---

## 10. AI Mesh and ARIA

### 10.1 AI Mesh Overview

AI Mesh is Forcepoint's multi-model AI classification engine that works alongside traditional DLP classifiers.

**Architecture:**
```
Document --> AI Mesh
              |
              +-- Small Language Model (SLM) --> vector representation
              +-- Deep Neural Network classifiers --> category prediction
              +-- Machine learning models --> confidence scoring
              |
              v
          Classification label (e.g., "Confidential - Financial")
              |
              v
          DLP policy condition (classifier = AI Mesh label)
```

### 10.2 How AI Mesh Integrates with DLP

1. AI Mesh analyzes documents and applies classification labels
2. Labels are stored as metadata on the document
3. DLP policies can use classification labels as content classifier conditions
4. Example: Rule condition = "AI Mesh label equals 'Confidential - Financial'" AND destination = "External email"

### 10.3 ARIA (Adaptive Risk Intelligence Assistant)

ARIA is an AI assistant that:
- Surfaces insights from DSPM (Data Security Posture Management) and DDR (Data Detection and Response)
- Recommends DLP policies based on detected data exposure risks
- Can deploy recommended policies directly from the chat interface

**ARIA Workflow:**
```
DSPM detects: "500 unprotected customer records in S3 bucket"
    |
    v
ARIA recommends: "Create PII protection policy for AWS S3 channel"
    |
    v
Admin reviews and approves in ARIA chat
    |
    v
ARIA deploys the policy automatically
```

### 10.4 1,800+ Classifiers

The AI Mesh platform includes 1,800+ classifiers and policy templates that combine traditional pattern matching with AI-powered classification for:
- Structured data (PII, PCI, PHI patterns)
- Unstructured data (documents, emails, chat messages)
- Image data (via OCR + AI classification)
- Multi-language content (90+ countries)

---

## 11. Incident Workflow

### 11.1 Incident Lifecycle

```
Detection --> Triage --> Investigation --> Resolution --> Closure
```

### 11.2 Workflow Actions

| Action | Description |
|--------|-------------|
| Assign incident | Route to specific analyst or team |
| Change status | New -> In Progress -> Resolved -> Closed |
| Change severity | Upgrade or downgrade based on investigation findings |
| Mark as ignored | False positive or accepted risk |
| Tag incident | Apply labels for categorization and reporting |
| Add comment | Document investigation findings |

### 11.3 Severity-Based Response Matrix

| Level | Severity | Response Actions |
|-------|----------|-----------------|
| 1 | Low | Audit only -- log and monitor |
| 2 | Low-Medium | Audit + automated user notification |
| 3 | Medium | Restrict + notify manager + log |
| 4 | High | Restrict + investigate + automated policy enforcement |
| 5 | Critical | Block + investigate + escalate + automated policy enforcement |

### 11.4 Best Practice: Automate Low, Investigate High

- Levels 1-2: Full automation (notify user, log, close after 30 days if no recurrence)
- Level 3: Semi-automated (notify manager, require acknowledgment)
- Levels 4-5: Human investigation required (assign to analyst, SLA tracking)

---

## 12. Discovery Tasks

### 12.1 Discovery Types

| Type | Scans | Targets |
|------|-------|---------|
| **Network Discovery** | File shares, SharePoint, Domino, databases, Exchange, PST files | On-premises storage |
| **Cloud Discovery** | Cloud application content | O365, Google Workspace, Box, etc. |
| **Endpoint Discovery** | Local files on endpoint devices | Laptops, desktops |

### 12.2 Discovery Workflow

```
Schedule task --> Crawl targets --> Apply classifiers --> Generate incidents --> Remediate
```

Discovery uses the **same classifiers and policies** as real-time DLP, ensuring consistent detection across data-at-rest and data-in-motion.

---

## 13. End-to-End Examples

### 13.1 Example: Healthcare Organization (HIPAA Compliance)

**Objective:** Prevent ePHI from leaving the organization via any channel.

**Step 1: Classifiers**
- Enable predefined HIPAA classifiers (SSN, MRN, DOB, ICD codes)
- Add Medical Conditions dictionary
- Create database fingerprint from EHR system (patient_name, DOB, MRN, insurance_id, diagnosis_code)

**Step 2: Resources**
- Source: All healthcare staff (clinical + administrative)
- Destinations: External email, personal cloud apps, USB drives, AI chatbots
- Exception source: Encrypted communication to approved insurance partners

**Step 3: Rules**
- Rule 1 (Email): PHI classifiers AND external email -> tiered response
- Rule 2 (Cloud): PHI classifiers AND cloud upload (not approved apps) -> Block
- Rule 3 (Endpoint): PHI classifiers AND USB/print -> Confirm/Justify
- Rule 4 (Drip): Cumulative PHI records >= 50 in 7 days -> Block + escalate

**Step 4: Action Plans**
- Tier 1 (1-5 PHI matches): Audit + notify user
- Tier 2 (5-20 PHI matches): Audit + notify compliance officer
- Tier 3 (20+ PHI matches): Block + notify CISO + SIEM alert
- Drip trigger: Block + escalate to incident response team

**Step 5: Policy**
- Create "HIPAA ePHI Protection" policy containing all 4 rules
- Enable RAP integration for dynamic enforcement (risk level 4+ users get blocked at 1 match)

**Step 6: Deploy**
- Phase 1: Deploy Audit-only to all users for 2 weeks
- Phase 2: Enable Tier 1-2 enforcement, review incidents
- Phase 3: Enable full enforcement (Tier 3 + Drip)

### 13.2 Example: Financial Services (PCI-DSS + Insider Threat)

**Objective:** Protect cardholder data and detect insider exfiltration.

**Step 1: Classifiers**
- Enable predefined PCI-DSS classifiers (all card brands, Luhn-validated)
- Create database fingerprint from customer accounts database
- Enable ML classifier trained on financial reports

**Step 2: Resources**
- Source: All employees
- RAP-enhanced: Risk levels 1-5 with graduated enforcement
- Destinations: All external channels

**Step 3: Rules**
- Rule 1: Credit card data in email/web/cloud -> tiered by count
- Rule 2: Financial reports (ML classifier) to external -> Block for risk level 3+
- Rule 3: Customer database records (fingerprint) -> Drip DLP (100 records / 30 days)
- Rule 4: Bulk file download (>50 MB) to USB -> Confirm/Justify

**Step 4: Deploy**
- Deploy with RAP enabled
- Trusted employees (level 1-2) get Audit + Notify
- At-risk employees (level 3-5) get Block + Escalate

### 13.3 Example: Technology Company (IP Protection)

**Objective:** Prevent source code and design document theft.

**Step 1: Classifiers**
- File properties: .py, .go, .java, .ts, .cpp, .h, .rs, .swift
- File fingerprints: Weekly scan of main code repositories (content similarity, 60%)
- Dictionary: Project code names, internal tool names
- ML classifier: Trained on patent applications and R&D documents

**Step 2: Resources**
- Source: Engineering and R&D departments
- Destinations: Personal email, personal cloud storage, non-corporate GitHub, USB drives
- Exceptions: Corporate GitHub org, approved vendor code shares, open-source project list

**Step 3: Rules**
- Rule 1: Code files to external destinations -> Block (risk level 3+), Confirm/Justify (level 1-2)
- Rule 2: Fingerprinted code (60%+ similarity) to any external -> Block all levels
- Rule 3: R&D documents (ML) to external -> Audit + notify manager
- Rule 4: Drip DLP: >= 50 code files in 14 days to personal storage -> Block + escalate

**Step 4: Deploy**
- Staged: Engineering first (1 week), then R&D (1 week), then all staff
- Monitor false positives from open-source work; add exceptions as needed
