# Forcepoint DLP Policy Authoring -- Advanced Reference

> Full field reference with UI navigation paths, configuration details, and 5-7 examples per section.
> Intended as a comprehensive lookup for experienced administrators.

---

## Table of Contents

1. [Forcepoint Security Manager Navigation](#1-forcepoint-security-manager-navigation)
2. [Content Classifiers: Full Reference](#2-content-classifiers-full-reference)
3. [Policy Rule Wizard: Full Field Reference](#3-policy-rule-wizard-full-field-reference)
4. [Action Plans: Full Configuration Reference](#4-action-plans-full-configuration-reference)
5. [Fingerprinting: Full Configuration Reference](#5-fingerprinting-full-configuration-reference)
6. [Risk-Adaptive Protection: Full Configuration](#6-risk-adaptive-protection-full-configuration)
7. [Drip DLP: Full Configuration Reference](#7-drip-dlp-full-configuration-reference)
8. [Discovery Tasks: Full Configuration](#8-discovery-tasks-full-configuration)
9. [OCR Configuration](#9-ocr-configuration)
10. [AI Mesh and Classification Labels](#10-ai-mesh-and-classification-labels)
11. [REST API: Full Endpoint Reference](#11-rest-api-full-endpoint-reference)
12. [SIEM Integration: Full Configuration](#12-siem-integration-full-configuration)
13. [Policy Import/Export: Full Reference](#13-policy-importexport-full-reference)
14. [Predefined Policy Catalog](#14-predefined-policy-catalog)
15. [Advanced Condition Logic Patterns](#15-advanced-condition-logic-patterns)

---

## 1. Forcepoint Security Manager Navigation

### 1.1 UI Layout

```
+------------------------------------------------------------------+
|  Forcepoint Security Manager                        [Deploy] [?]  |
+------------------------------------------------------------------+
|  Main  |  Settings  |  Reporting                                  |
+--------+------------+---------------------------------------------+
|                                                                    |
|  Main > Policy Management                                         |
|    +-- DLP Policies                                               |
|    +-- Content Classifiers                                        |
|    +-- Action Plans                                               |
|    +-- Resources                                                  |
|    +-- Discovery Tasks                                            |
|                                                                    |
|  Main > Reporting                                                 |
|    +-- Incident Manager                                           |
|    +-- DLP Reports                                                |
|    +-- Discovery Reports                                          |
|                                                                    |
|  Settings > General                                               |
|    +-- System Modules                                             |
|    +-- Remediation (syslog, email notifications)                  |
|    +-- Administrators                                             |
|    +-- Endpoint Configuration                                     |
|                                                                    |
+------------------------------------------------------------------+
```

### 1.2 Key Navigation Paths

| Task | Navigation Path |
|------|----------------|
| Create/edit DLP policies | Main > Policy Management > DLP Policies |
| Create/edit classifiers | Main > Policy Management > Content Classifiers |
| Configure action plans | Main > Policy Management > Action Plans |
| Manage resources (sources/destinations) | Main > Policy Management > Resources |
| Create discovery tasks | Main > Policy Management > Discovery Tasks |
| View incidents | Main > Reporting > Incident Manager |
| Configure syslog/SIEM | Settings > General > Remediation |
| Manage administrators | Settings > General > Administrators |
| Configure system modules | Settings > General > System Modules |
| Deploy changes | Toolbar > Deploy button (top right) |
| Check deployment status | Toolbar > Status indicator (next to Deploy) |

---

## 2. Content Classifiers: Full Reference

### 2.1 Navigation

**Path:** Main > Policy Management > Content Classifiers

### 2.2 Patterns & Phrases Tab

**Location:** Content Classifiers > Patterns & Phrases

| Field | Description | Values/Options |
|-------|-------------|----------------|
| Name | Classifier name | Free text, max 255 chars |
| Type | Classifier sub-type | Script, Regular Expression, Dictionary, Key Phrase |
| Status | Active/inactive | Enabled / Disabled |
| Description | Admin notes | Free text |
| Sensitivity | Sensitivity level | Low, Medium, High, Critical |

#### 2.2.1 Regular Expression Fields

| Field | Description | Notes |
|-------|-------------|-------|
| Pattern | The regex pattern | Standard regex syntax |
| Validation script | Optional Lua script for additional validation | Used for checksum validation (e.g., Luhn for credit cards) |
| Weight | Match weight for threshold calculation | Integer, higher = more significant |
| Proximity | Proximity window for context matching | Number of characters to search for context |

**Example 1: US Social Security Number (with context)**
```
Pattern:        \b\d{3}-\d{2}-\d{4}\b
Context phrase: "Social Security|SSN|ITIN|TIN"
Proximity:      200 characters
Weight:         10
WHY:            Context reduces false positives from random 9-digit numbers
GOTCHA:         Proximity window applies to surrounding text only; does not span across pages
```

**Example 2: Visa Credit Card (with Luhn validation)**
```
Pattern:           \b4[0-9]{12}(?:[0-9]{3})?\b
Validation script: Luhn checksum (built-in)
Weight:            15
WHY:               Luhn validation eliminates most false positives
GOTCHA:            Luhn validates the number but does not confirm it is an active card
```

**Example 3: UK National Insurance Number**
```
Pattern:        \b[A-CEGHJ-PR-TW-Z][A-CEGHJ-NPR-TW-Z]\s?\d{2}\s?\d{2}\s?\d{2}\s?[A-D]\b
Weight:         10
WHY:            UK-specific PII format required for GDPR/UK DPA compliance
GOTCHA:         The pattern excludes certain letter combinations (BG, GB, NK, KN, TN, NT, ZZ prefix); use the predefined UK NI classifier for guaranteed accuracy
```

**Example 4: Custom Internal ID Format**
```
Pattern:        \bPROJ-[A-Z]{3}-\d{6}\b
Weight:         5
WHY:            Organization-specific project ID format (e.g., PROJ-FIN-001234)
GOTCHA:         Update the pattern if the ID format changes. Consider a dictionary classifier for known project IDs instead of regex for finite ID sets.
```

**Example 5: AWS Secret Access Key**
```
Pattern:        \b[A-Za-z0-9/+=]{40}\b
Context phrase: "aws_secret|AWS_SECRET|SecretAccessKey"
Proximity:      500 characters
Weight:         20
WHY:            Detect AWS credentials in code, configs, or documents
GOTCHA:         Base64-encoded strings also match 40-char alphanumeric patterns; context matching is essential to reduce false positives
```

**Example 6: IP Address (IPv4)**
```
Pattern:        \b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b
Weight:         3
WHY:            Detect infrastructure details in documents
GOTCHA:         Extremely high false positive rate in technical documents. Only useful combined with other classifiers (e.g., AND "password" dictionary).
```

#### 2.2.2 Key Phrase Fields

| Field | Description | Notes |
|-------|-------------|-------|
| Phrase text | The exact phrase to match | Up to 255 characters |
| Case sensitive | Whether matching is case-sensitive | Boolean |
| Whole word | Match whole words only | Boolean (prevents "confidential" matching "confidentialism") |
| Weight | Match weight | Integer |

**Example 1: Confidentiality Marker**
```
Phrase:         "CONFIDENTIAL"
Case sensitive: No
Whole word:     Yes
Weight:         5
WHY:            Detect documents marked as confidential
GOTCHA:         Email signatures with "This email is confidential" generate noise. Consider proximity matching with file attachments.
```

**Example 2: Acquisition Code Name**
```
Phrase:         "Project Everest"
Case sensitive: No
Whole word:     Yes
Weight:         20
WHY:            Protect M&A confidentiality during active deal
GOTCHA:         Remove or disable after the deal closes or becomes public. Old code names generate false positives from archived communications.
```

**Example 3: MNPI Indicator**
```
Phrase:         "material non-public information"
Case sensitive: No
Whole word:     No
Weight:         15
WHY:            Detect discussion of MNPI in financial services
GOTCHA:         Training materials and compliance documents also contain this phrase. Create exceptions for compliance@company.com.
```

**Example 4: Export Control Marker**
```
Phrase:         "ITAR controlled"
Case sensitive: No
Whole word:     No
Weight:         25
WHY:            Detect export-controlled data for ITAR/EAR compliance
GOTCHA:         Absence of the marker does not mean absence of controlled data. Supplement with file fingerprinting for known controlled documents.
```

**Example 5: Custom Classification Label**
```
Phrase:         "//INTERNAL ONLY//"
Case sensitive: Yes
Whole word:     No
Weight:         10
WHY:            Organization uses custom classification markers in document headers
GOTCHA:         If classification markers are applied via Forcepoint Classification (AI Mesh), use the native label classifier instead of key phrases for better accuracy.
```

#### 2.2.3 Dictionary Fields

| Field | Description | Notes |
|-------|-------------|-------|
| Dictionary name | Name of the word list | Free text |
| Language | Language of the dictionary | English, French, German, etc. |
| Terms | List of words/expressions | One per line or imported from file |
| Match type | Exact match or contains | Exact recommended for precision |
| Weight per term | Weight assigned to each matched term | Integer |

**Example 1: Medical Conditions (Built-in)**
```
Dictionary:  Medical Conditions
Terms:       ~4,000 medical terms (diseases, conditions, procedures)
Language:    English
WHY:         Core component of HIPAA PHI detection
GOTCHA:      Medical terms in news articles, health blogs, and HR wellness communications trigger matches. Always AND with PII classifiers for PHI detection.
```

**Example 2: Financial Instruments**
```
Dictionary:  Custom - Financial Instruments
Terms:       "call option", "put option", "swap", "forward contract", "credit default swap",
             "collateralized debt obligation", "mortgage-backed security"
Language:    English
Weight:      5 per term
WHY:         Detect trading strategy documents and financial analysis
GOTCHA:      General business communications mention "options" and "contracts" frequently. Use high threshold (5+ matches) to filter noise.
```

**Example 3: Country-Specific ID Labels**
```
Dictionary:  Custom - PII Indicators (Multi-language)
Terms:       "Sozialversicherungsnummer" (DE), "numero de securite sociale" (FR),
             "codice fiscale" (IT), "numero de identificacion fiscal" (ES),
             "burgerservicenummer" (NL)
Language:    Multi-language
WHY:         Detect PII context clues in European documents
GOTCHA:      Each term should be paired with the corresponding regex pattern for that country's ID format. Dictionary alone is insufficient for PII detection.
```

**Example 4: Competitor Intelligence Terms**
```
Dictionary:  Custom - Competitive Intelligence
Terms:       [Competitor company names], [Competitor product names],
             [Competitor executive names], "market share", "win/loss",
             "competitive analysis", "battle card"
Language:    English
Weight:      3 per term
WHY:         Detect competitive intelligence documents being shared externally
GOTCHA:      Common words as company names (e.g., "Apple", "Shell") cause massive false positives. Increase weight for unique competitor names; decrease for common words.
```

**Example 5: Prohibited Data Types (Custom)**
```
Dictionary:  Custom - Prohibited Data Indicators
Terms:       "password", "secret key", "API key", "private key",
             "access token", "bearer token", "client_secret",
             "ssh-rsa", "BEGIN RSA PRIVATE KEY", "BEGIN CERTIFICATE"
Language:    English
Weight:      20 per term
WHY:         Detect credentials and secrets in documents, emails, and code
GOTCHA:      Technical documentation legitimately discusses these terms. Use source/destination filtering: apply only to outbound channels (external email, cloud uploads, USB).
```

### 2.3 File Properties Tab

**Location:** Content Classifiers > File Properties

| Field | Description | Values/Options |
|-------|-------------|----------------|
| File name | Match by file name or extension | Wildcard patterns (e.g., *.xlsx, budget*) |
| File type | Match by internal file type (magic number) | Dropdown list of 400+ file types |
| File size | Match by file size | Min/max size in KB/MB/GB |
| Encrypted | Match encrypted/password-protected files | Boolean |

**Example 1: Large Spreadsheets**
```
File type:  Microsoft Excel (xlsx, xls)
File size:  > 10 MB
WHY:        Large spreadsheets often contain bulk data exports (customer lists, financial data)
GOTCHA:     Pivot tables and embedded charts inflate file size. Combine with content classifiers for accuracy.
```

**Example 2: Executable Files**
```
File type:  PE Executable, DLL, Batch file, PowerShell script, Shell script
WHY:        Block malware/unauthorized software distribution
GOTCHA:     IT teams legitimately share utilities. Create exceptions for IT admin users and approved software distribution channels.
```

**Example 3: Database Export Files**
```
File name:  *.sql, *.bak, *.dump, *.mdf
File type:  SQL dump, database backup
WHY:        Database dumps contain bulk sensitive data
GOTCHA:     DBA teams need to share database backups. Create exceptions for DBA group to approved backup destinations only.
```

**Example 4: CAD/Engineering Designs**
```
File type:  AutoCAD (dwg), STEP, STL, IGES, SolidWorks
WHY:        Protect manufacturing IP and engineering designs
GOTCHA:     Content inspection is limited for binary CAD formats. Pair with file fingerprinting and source/destination controls.
```

**Example 5: Encrypted/Password-Protected Files**
```
Encrypted:  Yes
WHY:        Encrypted files cannot be content-inspected; they may hide sensitive data from DLP
GOTCHA:     Some organizations mandate encryption. Whitelist approved encryption methods (e.g., BitLocker, company-approved ZIP encryption).
```

**Example 6: Image Files (for OCR)**
```
File type:  JPEG, PNG, TIFF, BMP, GIF
File size:  > 5 KB and < 25 MB
WHY:        Trigger OCR scanning for images that may contain text (screenshots, scanned docs)
GOTCHA:     Non-text images (photos, graphics) waste OCR processing time. Consider a classifier chain: file type = image AND OCR text extraction has results.
```

---

## 3. Policy Rule Wizard: Full Field Reference

### 3.1 Tab 1: General

| Field | Description | Required | Default |
|-------|-------------|----------|---------|
| Rule name | Descriptive name for the rule | Yes | "New Rule" |
| Description | Admin notes about the rule's purpose | No | Empty |
| Enabled | Whether the rule is active | Yes | Enabled |
| Channels | Which DLP channels this rule applies to | Yes | All channels |

**Channel Options:**
- Email (SMTP, Exchange, cloud email)
- Web (HTTP/HTTPS uploads and posts)
- Endpoint (USB, print, clipboard, local save, application, LAN, screen capture)
- Cloud (CASB-monitored cloud applications)
- Network (FTP, custom protocols)
- Discovery (data at rest scanning)

**Example 1: Email-Only Rule**
```
Name:     "PHI in External Email"
Channels: Email only
WHY:      Different action plans for email vs. endpoint (quarantine vs. block)
GOTCHA:   Channel-specific rules create gaps if you forget to cover other channels. Always create companion rules for remaining channels.
```

**Example 2: All-Channel Rule**
```
Name:     "Credit Card Data - All Channels"
Channels: All
WHY:      Consistent enforcement regardless of how data leaves
GOTCHA:   "Quarantine" action only works on email channel. If your action plan includes quarantine, it is ignored on non-email channels.
```

**Example 3: Endpoint-Only Rule**
```
Name:     "USB Block for Source Code"
Channels: Endpoint only
WHY:      Block source code copying to USB drives without affecting email/web
GOTCHA:   Endpoint rules require the endpoint agent to be installed and connected. Remote workers without agent connectivity are unprotected.
```

**Example 4: Discovery-Only Rule**
```
Name:     "Find PII at Rest on File Shares"
Channels: Discovery only
WHY:      Scan file shares for stored PII without affecting real-time traffic
GOTCHA:   Discovery rules do not prevent data from being shared; they only identify where sensitive data resides. Use in combination with transit rules.
```

**Example 5: Cloud-Only Rule**
```
Name:     "Block PII Upload to Personal Cloud"
Channels: Cloud only
WHY:      Target cloud applications specifically (Dropbox, Google Drive personal, etc.)
GOTCHA:   Requires CASB integration (Forcepoint ONE or cloud gateway). Without CASB, cloud channel rules have no enforcement point.
```

### 3.2 Tab 2: Condition

| Field | Description | Notes |
|-------|-------------|-------|
| Classifier selection | Choose content classifiers | Multi-select from existing classifiers |
| Logic operators | AND, OR, NOT between conditions | Drag-and-drop or dropdown |
| Parentheses | Group conditions | Click to add/remove grouping |
| Trigger mode | "All conditions must match" vs. "Any condition" | Radio button |

**Condition Builder UI:**
```
+-----------------------------------------+
|  Condition Builder                       |
|                                         |
|  [+] Add Condition                      |
|                                         |
|  IF:                                    |
|    ( SSN Pattern    )    [AND]          |
|    ( Medical Terms  )                   |
|                                         |
|  [+] Add Group  [OR]  [NOT]            |
|                                         |
+-----------------------------------------+
```

**Example 1: Simple AND**
```
IF: (SSN Pattern) AND (Medical Terms Dictionary)
WHY: Both PII and medical context required = PHI
```

**Example 2: OR with Multiple Patterns**
```
IF: (Visa CC) OR (Mastercard CC) OR (Amex CC) OR (Discover CC)
WHY: Catch any credit card brand
```

**Example 3: AND + OR Combined**
```
IF: (SSN OR DOB OR Driver License) AND (Medical Terms OR Diagnosis Codes)
WHY: Any PII type combined with any medical context = PHI
```

**Example 4: NOT for Exclusion**
```
IF: (Financial Terms Dictionary) AND NOT (Key Phrase: "published" OR "annual report")
WHY: Detect non-public financial data; exclude published materials
```

**Example 5: Complex Nested Logic**
```
IF: ( (SSN OR CC OR IBAN) AND (Customer Name Dictionary) )
    OR
    ( (File Fingerprint: Customer DB) AND (File Size > 1 MB) )
WHY: Either content-based detection OR fingerprint-based detection, covering both scenarios
GOTCHA: Complex logic is hard to debug. Test each sub-condition independently before combining.
```

**Example 6: Proximity-Based Condition**
```
IF: (Regex: \b\d{3}-\d{2}-\d{4}\b) within 200 chars of (Key Phrase: "SSN|Social Security|Tax ID")
WHY: SSN pattern near SSN context = high confidence PII detection
GOTCHA: Proximity matching is configured at the classifier level, not the rule level. Set proximity when creating the regex classifier.
```

### 3.3 Tab 3: Severity & Action

| Field | Description | Notes |
|-------|-------------|-------|
| Threshold rows | "Where there are at least N matches" | Multiple rows for graduated response |
| Severity | Severity level for this threshold | Low, Medium, High, Critical |
| Action plan | Which action plan to execute | Select from configured action plans |
| Cumulative toggle | "Accumulate matches before creating an incident" | Checkbox for drip DLP |
| Time period | Sliding window for cumulative detection | Hours, days, weeks |
| Match calculation | How to count matches | "Greatest number" or "Sum of all" |
| RAP columns | One action plan per risk level (1-5) | Only visible when RAP is enabled |

**Severity & Action Table (Standard):**
```
+---------------------------------------------------+
| Threshold        | Severity | Action Plan          |
+------------------+----------+----------------------+
| >= 1 match       | Low      | Audit Only           |
| >= 5 matches     | Medium   | Audit & Notify       |
| >= 20 matches    | High     | Block & Escalate     |
| >= 100 matches   | Critical | Block & SIEM & CISO  |
+---------------------------------------------------+
```

**Severity & Action Table (with RAP):**
```
+---------------------------------------------------------------------------------+
| Threshold    | Severity | Risk 1    | Risk 2      | Risk 3    | Risk 4  | Risk 5  |
+--------------+----------+-----------+-------------+-----------+---------+---------+
| >= 1 match   | Low      | Permit    | Audit       | Notify    | Block   | Block++ |
| >= 5 matches | Medium   | Audit     | Notify      | Block     | Block++ | Block++ |
| >= 20 matches| High     | Notify    | Block       | Block++   | Block++ | Block++ |
+--------------+----------+-----------+-------------+-----------+---------+---------+
Block++ = Block + Escalate to CISO + SIEM Alert
```

**Example 1: Single Threshold (Simple)**
```
>= 1 match -> Medium -> Audit & Notify Manager
WHY: Every match is significant (e.g., database fingerprint match)
GOTCHA: High-volume classifiers with single threshold create alert storms. Use tiered thresholds for pattern-based classifiers.
```

**Example 2: Four-Tier Graduated Response**
```
>= 1   -> Low      -> Audit
>= 5   -> Medium   -> Audit + Notify user
>= 20  -> High     -> Block + Notify manager
>= 100 -> Critical -> Block + Escalate + SIEM
WHY: Proportional response reduces false positive business impact
GOTCHA: Ensure the threshold gaps are large enough to differentiate legitimate from malicious activity.
```

**Example 3: Cumulative (Drip DLP)**
```
Cumulative: Yes
Time period: 7 days (sliding window)
Threshold: >= 50 matches
Match calculation: Sum of all matched conditions
Severity: High
Action: Block + Escalate
WHY: Catch slow exfiltration (2-3 records per email, 10 emails per day, 7 days)
GOTCHA: Sliding window resets on each match. If attacker pauses for > 7 days, count resets.
```

**Example 4: RAP-Enhanced Credit Card Policy**
```
>= 1 match:
  Risk 1 (trusted):  Audit
  Risk 2 (low):      Audit
  Risk 3 (medium):   Audit + Notify
  Risk 4 (high):     Block
  Risk 5 (critical): Block + CISO + SIEM

>= 10 matches:
  Risk 1: Audit + Notify
  Risk 2: Block
  Risk 3-5: Block + CISO + SIEM
WHY: Trusted payment processors can handle cards; at-risk users cannot
GOTCHA: RAP risk scores lag behind real-time events. A sudden insider threat may not be reflected in the risk score for hours.
```

**Example 5: Discovery-Specific Severity**
```
>= 1 file with PII at rest -> Low -> Audit (log finding)
>= 100 files with PII at rest -> High -> Audit + Notify data owner + Remediation script
WHY: A few PII files are normal; 100+ indicates a data hoarding problem
GOTCHA: Discovery remediation (move/delete/quarantine files) is destructive. Always audit first, remediate second.
```

### 3.4 Tab 4: Source

| Field | Description | Options |
|-------|-------------|---------|
| All sources | Apply to everyone/everything | Checkbox (default: checked) |
| Specific users/groups | AD users or groups | AD browser / manual entry |
| Specific OUs | AD organizational units | AD browser |
| Specific computers | Computer names or patterns | Manual entry or AD computer groups |
| IP address ranges | Network-based source filtering | CIDR notation or range |
| Domains | Email domains as source | Domain list |

**Example 1: All Sources (Default)**
```
Selection: All sources (checked)
WHY: Broadest coverage for initial deployment
GOTCHA: Includes service accounts, shared mailboxes, and system processes. These generate noise. Narrow after baseline.
```

**Example 2: Single Department**
```
Selection: AD Group = "SG-Finance-All"
WHY: Financial data policy only relevant to finance users
GOTCHA: Cross-functional team members (e.g., finance analyst in marketing) may not be in the finance group. Review group membership quarterly.
```

**Example 3: Executive Users (Named List)**
```
Selection: Users = "jsmith@company.com", "mjones@company.com" (10 named users)
WHY: High-value target monitoring with specific action plans
GOTCHA: Named lists require manual maintenance when executives join/leave. Use AD groups instead when possible.
```

**Example 4: Network Segment**
```
Selection: IP Range = 10.50.0.0/16
WHY: R&D lab network requires stricter controls than general office
GOTCHA: VPN users may appear from unexpected IP ranges. Combine network-based sources with user-based sources.
```

**Example 5: Exclude Specific Groups**
```
Selection: All sources EXCEPT AD Group = "SG-DLP-Exceptions"
WHY: Most users are monitored; DLP-exempted users (e.g., DLP admins, legal hold) are excluded
GOTCHA: The exceptions group must be audited regularly. Users should not remain in the exceptions group indefinitely.
```

### 3.5 Tab 5: Destination

| Field | Description | Options |
|-------|-------------|---------|
| All destinations | Apply to all outbound targets | Checkbox (default: checked) |
| Email domains | Specific email domains | Domain list (include/exclude) |
| Cloud applications | Specific cloud apps | App list from CASB catalog |
| URLs/URL categories | Web destinations | URL patterns or Forcepoint URL categories |
| Removable media | USB drives, external storage | Boolean toggle |
| Printers | Print channel | Boolean toggle or specific printer list |
| Network destinations | IP ranges, FTP servers | CIDR notation or hostname |
| Applications | Specific desktop applications | Application names or categories |

**Example 1: External Email Only**
```
Selection: Email domains NOT matching "@company.com" OR "@company.co.uk"
WHY: Only inspect email going outside the organization
GOTCHA: Partner domains that should be allowed (e.g., @lawfirm.com, @auditor.com) need explicit whitelisting.
```

**Example 2: Personal Cloud Storage**
```
Selection: Cloud apps = "Dropbox Personal", "Google Drive Personal", "iCloud Drive", "OneDrive Personal"
WHY: Block data to personal cloud while allowing corporate cloud
GOTCHA: Distinguishing personal from corporate requires CASB instance-level detection. Without it, all Dropbox traffic is treated the same.
```

**Example 3: USB and Removable Media**
```
Selection: Removable media = Yes
WHY: Prevent data copying to USB drives
GOTCHA: Hardware tokens (YubiKey), encrypted backup drives, and USB mice/keyboards are all "removable media." Use device ID whitelists for approved devices.
```

**Example 4: AI Chatbot Applications**
```
Selection: URLs matching "chat.openai.com/*", "claude.ai/*", "gemini.google.com/*", "copilot.microsoft.com/*"
WHY: Prevent sensitive data from being pasted into AI chatbots
GOTCHA: URL-based blocking does not catch AI tools embedded in applications (e.g., Copilot in Word). Use application-level controls for comprehensive coverage.
```

**Example 5: Non-Corporate GitHub**
```
Selection: URLs matching "github.com/*" EXCEPT "github.com/our-company/*"
WHY: Block code push to personal GitHub repos while allowing corporate
GOTCHA: GitHub CLI, git protocol, and SSH-based pushes may not be caught by URL-based rules. Use endpoint DLP application controls for git client monitoring.
```

**Example 6: Print Channel (Restricted)**
```
Selection: Printers = All printers
WHY: Detect/block printing of classified documents
GOTCHA: "Print to PDF" on the endpoint is treated as a print action. Screenshot/screen capture is a separate channel.
```

---

## 4. Action Plans: Full Configuration Reference

### 4.1 Navigation

**Path:** Main > Policy Management > Action Plans

### 4.2 Creating an Action Plan

| Field | Description | Required |
|-------|-------------|----------|
| Name | Action plan name | Yes |
| Description | Admin notes | No |
| Actions | Selected actions from available list | At least one |

### 4.3 Full Action Catalog

| Action | Applies To | Description | Config Options |
|--------|-----------|-------------|----------------|
| **Audit incident** | All channels | Log incident to database | Always selected (default) |
| **Permit** | All channels | Allow the transaction | No additional config |
| **Block** | All channels | Prevent the transaction | Customizable block message |
| **Quarantine** | Email only | Hold email for review | Auto-release timer, reviewer assignment |
| **Encrypt on release** | Email only | Encrypt when released from quarantine | Encryption method selection |
| **Send email notification** | All channels | Email to recipients | Recipient list, template, subject |
| **Send syslog message** | All channels | Forward to SIEM | Syslog server config (Settings > Remediation) |
| **Run endpoint remediation script** | Endpoint only | Execute script on endpoint | Script path, parameters |
| **Notify end user** | Endpoint only | Popup notification on endpoint | Custom message text |
| **Confirm/Justify** | Endpoint only | User must justify action | Custom prompt text, justification logged |
| **Custom actions** | Email, Network | Organization-defined | Custom action scripts |

### 4.4 Action Plan Examples

**Example 1: "Audit Only"**
```
Actions: Audit incident
Use for: Initial policy rollout, monitoring phase
WHY: Zero business impact while gathering baseline data
GOTCHA: Still consumes incident storage. Monitor database growth.
```

**Example 2: "Audit + Notify User"**
```
Actions: Audit incident + Notify end user (popup: "This action was logged per company policy. If intentional, no action needed.")
Use for: Low-severity awareness campaigns
WHY: Educates users without blocking productivity
GOTCHA: Popup fatigue if too many policies trigger notifications. Limit to high-value policies.
```

**Example 3: "Block + Notify + SIEM"**
```
Actions: Audit incident + Block + Notify end user (popup: "This file transfer was blocked. Contact security@company.com if this is a business need.") + Send syslog message
Use for: High-severity enforcement
WHY: Blocks the action, informs the user, and alerts the SOC
GOTCHA: Block message should include clear escalation path (who to contact, how to request an exception).
```

**Example 4: "Quarantine + Review"**
```
Actions: Audit incident + Quarantine + Send email notification (to dlp-team@company.com: "Email quarantined for DLP review. Policy: {policy_name}. Sender: {sender}.")
Use for: Medium-severity email containing potential PII
WHY: Holds email for human review before delivery
GOTCHA: Quarantine queue must be staffed. Set auto-release after 48 hours to avoid business disruption.
```

**Example 5: "Confirm/Justify + Audit"**
```
Actions: Audit incident + Confirm/Justify (prompt: "This file contains sensitive data. Please provide a business justification to proceed.")
Use for: Medium-severity endpoint actions where user override is acceptable
WHY: Adds friction and accountability without fully blocking
GOTCHA: Justification text is logged. Review justifications periodically for policy abuse (e.g., users entering "test" or "asdf").
```

**Example 6: "Full Escalation"**
```
Actions: Audit incident + Block + Send email notification (to CISO + HR) + Send syslog message + Run endpoint remediation script (quarantine file to locked folder)
Use for: Critical severity (suspected data breach, insider threat)
WHY: Maximum response for maximum-severity events
GOTCHA: Only assign to Critical/High severity thresholds. If triggered at Low severity, alert fatigue will undermine the entire incident response program.
```

**Example 7: "Discovery Remediation"**
```
Actions: Audit incident + Run endpoint remediation script (move to quarantine folder) + Send email notification (to data owner: "Sensitive data found at rest. Location: {file_path}. Action: Moved to quarantine.")
Use for: Discovery task findings
WHY: Automatically remediates sensitive data found at rest
GOTCHA: Test the remediation script thoroughly. Moving files can break application dependencies.
```

---

## 5. Fingerprinting: Full Configuration Reference

### 5.1 Database Fingerprinting

**Navigation:** Main > Policy Management > Content Classifiers > Database Fingerprinting

#### Configuration Wizard

| Step | Field | Description |
|------|-------|-------------|
| 1. General | Name | Classifier name |
| | Description | Admin notes |
| | Database type | SQL Server, Oracle, MySQL, Salesforce, CSV |
| 2. Connection | Server/host | Database server address |
| | Port | Database port |
| | Credentials | Username/password or integrated auth |
| | Database name | Target database |
| 3. Table/Fields | Table selection | Which tables to fingerprint |
| | Field selection | Which columns (max 32 per table) |
| | Minimum records | Min records to fingerprint |
| 4. Schedule | Scan frequency | One-time, daily, weekly, monthly |
| | Scan window | Time range for scanning |
| 5. Threshold | Minimum matches | How many field matches required for a hit |

**Example 1: CRM Customer Database**
```
DB Type:     SQL Server
Table:       customers
Fields:      customer_name, email, phone, account_id, address (5 fields)
Schedule:    Daily at 2:00 AM
Threshold:   3 of 5 fields must match
WHY:         Detect customer PII even in reformatted exports
GOTCHA:      5 fields provides good balance of accuracy and performance. 1-2 fields = too many false positives. All 32 = too slow.
```

**Example 2: HR Employee Records**
```
DB Type:     Oracle
Table:       employees
Fields:      employee_id, ssn, first_name, last_name, salary, hire_date, manager_id (7 fields)
Schedule:    Weekly (Sunday 1:00 AM)
Threshold:   3 of 7 fields must match
WHY:         Prevent mass export of employee data (salary info, SSNs)
GOTCHA:      SSN field is most identifying. If SSN is not available, increase threshold to 4+ fields.
```

**Example 3: Salesforce Contacts**
```
DB Type:     Salesforce
Object:      Contact
Fields:      Name, Email, Phone, Account.Name, MailingAddress (5 fields)
Schedule:    Daily
Threshold:   3 of 5 fields
WHY:         Detect Salesforce data exports being shared externally
GOTCHA:      Salesforce API limits may affect fingerprinting speed. Schedule during off-peak.
```

**Example 4: CSV File (Static Data)**
```
DB Type:     CSV
File:        \\server\data\customer_list.csv
Fields:      Column A (name), Column C (email), Column E (account_number)
Schedule:    One-time (or weekly if CSV is updated)
Threshold:   2 of 3 fields
WHY:         Quick fingerprinting without database connectivity
GOTCHA:      CSV path must be accessible from the management server. UNC paths require service account permissions.
```

**Example 5: Patient Records (HIPAA)**
```
DB Type:     SQL Server
Table:       patients
Fields:      patient_name, dob, mrn, insurance_id, diagnosis_code, attending_physician (6 fields)
Schedule:    Daily at midnight
Threshold:   3 of 6 fields
WHY:         HIPAA ePHI protection for healthcare organizations
GOTCHA:      High patient volume databases (millions of records) may take hours to fingerprint. Use off-peak scheduling and monitor management server performance.
```

### 5.2 File Fingerprinting

**Navigation:** Main > Policy Management > Content Classifiers > File System Fingerprinting

| Field | Description |
|-------|-------------|
| Source path | UNC path or local path to scan |
| File filtering | Include/exclude by file type, name, size |
| Matching method | Content similarity or Exact match |
| Confidence score | Minimum match percentage (10%-100%, multiples of 10) |
| Schedule | Scan frequency |

**Example 1: Board Presentations**
```
Source:      \\exec-share\board\presentations\
File types:  .pptx, .pdf
Method:      Content similarity
Confidence:  70%
Schedule:    Weekly
WHY:         Detect partial copies of board materials (even edited versions)
GOTCHA:      70% confidence catches edited versions but may match similar-themed presentations. Increase to 80-90% if false positives are high.
```

**Example 2: Source Code Repository**
```
Source:      \\dev-share\repos\main-product\
File types:  .py, .go, .java, .ts, .cpp, .h
Method:      Content similarity
Confidence:  60%
Schedule:    Weekly (after code freeze)
WHY:         Detect code theft even with variable renaming
GOTCHA:      60% is intentionally low to catch heavily modified code. This will generate some false positives from common boilerplate. Tune confidence based on observed FP rate.
```

**Example 3: Legal Contracts**
```
Source:      \\legal\contracts\active\
File types:  .docx, .pdf
Method:      Content similarity
Confidence:  80%
Schedule:    Daily
WHY:         Detect unauthorized sharing of active contracts
GOTCHA:      Legal templates and standard clauses will match across different contracts. Create exceptions for the legal team or approved contract portals.
```

**Example 4: Product Design Files**
```
Source:      \\engineering\designs\current-release\
File types:  .dwg, .step, .stl, .iges, .sldprt
Method:      Exact match (binary)
Confidence:  100%
Schedule:    Weekly
WHY:         Detect exact copies of engineering designs being exfiltrated
GOTCHA:      Exact match only catches identical files. Any modification (even metadata change) evades detection. Use Content Similarity if modifications are a concern, but note that binary CAD formats may not support content similarity well.
```

**Example 5: Training Materials (Negative Fingerprint)**
```
Source:      \\hr\training\public-materials\
File types:  .pptx, .pdf, .docx
Method:      Content similarity
Confidence:  90%
Use as:      EXCEPTION (NOT condition in rule logic)
WHY:         Exclude public training materials from triggering "Confidential Documents" policy
GOTCHA:      This is a negative fingerprint -- it defines what should NOT trigger. Add it as a NOT condition in the rule: (Confidential Fingerprint) AND NOT (Public Training Fingerprint).
```

---

## 6. Risk-Adaptive Protection: Full Configuration

### 6.1 Prerequisites

- Forcepoint UEBA deployed and operational
- UEBA risk scores flowing to DLP management server
- RAP license activated
- At least one policy with RAP-enabled Severity & Action configuration

### 6.2 Risk Level Definitions

| Level | Score Range | Meaning | Typical Indicators |
|-------|------------|---------|-------------------|
| 1 | 0-20 | Trusted | Normal behavior, consistent with role |
| 2 | 21-40 | Low risk | Minor anomalies, new employee |
| 3 | 41-60 | Medium risk | Behavioral changes, unusual access patterns |
| 4 | 61-80 | High risk | Significant anomalies, policy violations |
| 5 | 81-100 | Critical risk | Active threat indicators, multiple violations |

### 6.3 UEBA Signals That Affect Risk Score

| Signal | Impact |
|--------|--------|
| Unusual login time/location | Increases risk |
| Access to data outside normal role | Increases risk |
| Bulk data download | Increases risk |
| Multiple DLP policy violations | Increases risk |
| Resignation/termination notice (HR feed) | Increases risk |
| Performance improvement plan (HR feed) | Increases risk |
| Consistent normal behavior | Decreases risk over time |
| Completed security training | Decreases risk slightly |

---

## 7. Drip DLP: Full Configuration Reference

### 7.1 Configuration Location

**Path:** Policy Rule Wizard > Tab 3: Severity & Action > "Accumulate matches before creating an incident"

### 7.2 Fields

| Field | Description | Options |
|-------|-------------|---------|
| Enable cumulative | Toggle cumulative detection | Checkbox |
| Time period | Sliding window duration | 1 hour to 90 days |
| Minimum matches | Threshold for incident creation | Integer (e.g., 5, 10, 50, 100) |
| Match calculation | How to count matches across transactions | "Greatest number of matched conditions" / "Sum of all matched conditions" |
| Source tracking | What defines a "source" for accumulation | User, computer, IP address |

### 7.3 Sliding Window Behavior

```
Day 1: User sends 3 credit cards in email         Running total: 3
Day 2: User sends 2 credit cards in email         Running total: 5  --> THRESHOLD MET (5)
Day 3: (no activity)                               Running total: 5
Day 8: (if window is 7 days, Day 1 data expires)  Running total: 2
```

The window slides forward, dropping off older data as it ages out of the configured period.

### 7.4 Drip DLP Examples

**Example 1: Credit Card Drip (7-Day Window)**
```
Classifier:     Credit card (Luhn-validated)
Cumulative:     Yes
Time period:    7 days
Threshold:      20 credit cards
Calculation:    Sum of all matched conditions
Action:         Block + Escalate
WHY:            20 credit cards over 7 days = systematic extraction
GOTCHA:         A payment processor sending 5 invoices with card data per day hits this in 4 days. Create source exceptions for payment processing roles.
```

**Example 2: Customer Record Drip (30-Day Window)**
```
Classifier:     Database fingerprint (customer CRM, 3+ field match)
Cumulative:     Yes
Time period:    30 days
Threshold:      100 records
Calculation:    Sum of all matched conditions
Action:         Block + Notify security + SIEM
WHY:            100 customer records over a month = likely data theft
GOTCHA:         Sales reps who email customer information daily will hit this. Set threshold high enough for legitimate volume or use role-based exceptions.
```

**Example 3: Document Accumulation (14-Day Window)**
```
Classifier:     File fingerprint (company documents, 60%+ similarity)
Cumulative:     Yes
Time period:    14 days
Threshold:      50 documents
Calculation:    Sum of all matched conditions
Action:         Notify manager + require justification
WHY:            50 company documents to personal email in 2 weeks = concerning
GOTCHA:         End-of-quarter reporting, audits, and project handoffs may legitimately involve bulk document sharing. Consider seasonal threshold adjustments.
```

**Example 4: PII Drip (90-Day Window)**
```
Classifier:     EU PII patterns (national IDs, IBANs)
Cumulative:     Yes
Time period:    90 days
Threshold:      500 PII records
Calculation:    Sum of all matched conditions
Action:         Block + DPO notification + SIEM
WHY:            GDPR: 500 PII records over 3 months to non-EU destinations = reportable
GOTCHA:         90-day windows consume more storage and processing. Monitor management server performance.
```

**Example 5: Multi-Channel Drip (7-Day Window)**
```
Classifier:     Any sensitive data (PII OR PCI OR PHI)
Cumulative:     Yes
Time period:    7 days
Threshold:      100 matches across ALL channels
Calculation:    Sum of all matched conditions
Action:         Block all channels + escalate
WHY:            Catch exfiltration that splits data across email (some), cloud (some), USB (some)
GOTCHA:         Multi-channel cumulative detection requires all channels to report to the same management server. Ensure complete component deployment.
```

---

## 8. Discovery Tasks: Full Configuration

### 8.1 Navigation

**Path:** Main > Policy Management > Discovery Tasks

### 8.2 Discovery Task Types

| Type | Targets | Agent Required |
|------|---------|---------------|
| Network Discovery | File shares, SharePoint, Domino, databases, Exchange, PST files | No (server-side scan) |
| Cloud Discovery | Cloud application content (O365, Google, Box, Salesforce) | No (API-based) |
| Endpoint Discovery | Local files on endpoints | Yes (endpoint agent) |

### 8.3 Network Discovery Configuration

| Field | Description |
|-------|-------------|
| Task name | Descriptive name |
| Target type | File share, SharePoint site, database, Exchange mailbox, Domino |
| Path/URL | UNC path, SharePoint URL, or connection string |
| Credentials | Service account for accessing the target |
| File filtering | Include/exclude by type, size, date modified |
| Schedule | One-time, daily, weekly, monthly |
| Throttling | Max concurrent scans, bandwidth limits |
| Policy | Which DLP policy to apply during discovery |

### 8.4 Endpoint Discovery Configuration

| Field | Description |
|-------|-------------|
| Task name | Descriptive name |
| Endpoint groups | Which endpoint groups to scan |
| Scan locations | Specific folders (My Documents, Desktop, etc.) or full disk |
| File filtering | Include/exclude by type, size, age |
| Schedule | Once, daily, weekly |
| Bandwidth throttle | CPU/IO limits during scan |

---

## 9. OCR Configuration

### 9.1 Navigation

**Path:** Settings > General > System Modules > OCR Server

### 9.2 Requirements

| Requirement | Detail |
|-------------|--------|
| Server | Supplemental Forcepoint DLP server with OCR component installed |
| Supported formats | JPEG, PNG, TIFF, BMP, GIF, PDF (scanned), Office docs with embedded images |
| Min file size | 5 KB |
| Max file size | 25 MB |
| Not supported | Handwriting, text skewed > 10 degrees |

### 9.3 OCR + DLP Policy Integration

OCR is transparent to policy authoring. When OCR is enabled, the policy engine automatically:
1. Detects image/scanned content in transactions
2. Sends to OCR server for text extraction
3. Applies content classifiers to extracted text
4. Triggers policy rules based on OCR results

No special classifier configuration is needed -- the same classifiers that detect text also detect OCR-extracted text.

---

## 10. AI Mesh and Classification Labels

### 10.1 How Labels Become Classifiers

```
Document --> Forcepoint Classification (AI Mesh) --> Label: "Confidential - Financial"
                                                         |
DLP Policy Rule Condition: Classification Label = "Confidential - Financial"
                                                         |
                                                   Rule triggers
```

### 10.2 Available Label Categories

Labels are organization-defined. Common examples:
- Public
- Internal Only
- Confidential
- Confidential - Financial
- Confidential - HR
- Restricted
- Top Secret
- ITAR Controlled

### 10.3 Configuration

1. Deploy Forcepoint Classification (AI Mesh) with trained models
2. Documents are automatically labeled during classification scan
3. In DLP policy rule conditions, select "Classification Label" as classifier type
4. Choose the specific label(s) to match
5. Combine with other classifiers using AND/OR logic

---

## 11. REST API: Full Endpoint Reference

### 11.1 Base URL

```
https://<DLP_Manager_IP>:<port>/dlp/rest/v1/
```

### 11.2 Authentication Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/auth/refresh-token` | Get refresh token (username + password) |
| POST | `/auth/access-token` | Get access token (refresh token) |

### 11.3 Incident Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/incidents` | List incidents (with filters) |
| GET | `/incidents/{id}` | Get incident details |
| PUT | `/incidents/{id}` | Update incident |
| GET | `/discovery-incidents` | List discovery incidents |

### 11.4 Policy Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/policies` | List enabled policies |
| GET | `/policies/{id}` | Get policy details |
| PUT | `/policies/{id}/enable` | Enable a policy |
| PUT | `/policies/{id}/disable` | Disable a policy |
| POST | `/policies/import` | Import policies |
| POST | `/policies/export` | Export policies |

### 11.5 Deploy Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/deploy` | Trigger deployment |
| GET | `/deploy/status` | Check deployment status |

---

## 12. SIEM Integration: Full Configuration

### 12.1 Navigation

**Path:** Settings > General > Remediation

### 12.2 Syslog Configuration

| Field | Description | Options |
|-------|-------------|---------|
| Syslog server | SIEM server hostname/IP | Hostname or IP address |
| Port | Syslog port | 514 (default), custom |
| Protocol | Transport protocol | UDP or TCP (TCP recommended for reliability) |
| Format | SIEM log format | CEF, Key-Value Pairs, LEEF, Custom |

### 12.3 Trigger Configuration

Syslog messages are triggered per-incident by adding "Send syslog message" to the action plan. Only incidents matching policies with this action will forward to SIEM.

---

## 13. Policy Import/Export: Full Reference

### 13.1 Use Cases

| Use Case | Direction | Method |
|----------|-----------|--------|
| Dev -> UAT migration | Export from dev, import to UAT | REST API or FSM UI |
| UAT -> Prod promotion | Export from UAT, import to prod | REST API |
| Backup/restore | Export all policies | REST API or FSM backup |
| Multi-site sync | Export from primary, import to secondary | REST API |

### 13.2 API Workflow

```bash
# Export from source environment
curl -X POST https://dev-dlp:443/dlp/rest/v1/policies/export \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -o policies_export.json

# Import to target environment
curl -X POST https://prod-dlp:443/dlp/rest/v1/policies/import \
  -H "Authorization: Bearer $PROD_TOKEN" \
  -H "Content-Type: application/json" \
  -d @policies_export.json

# Deploy in target environment
curl -X POST https://prod-dlp:443/dlp/rest/v1/deploy \
  -H "Authorization: Bearer $PROD_TOKEN"
```

---

## 14. Predefined Policy Catalog

### 14.1 By Compliance Framework

| Framework | Example Policies | Region |
|-----------|-----------------|--------|
| HIPAA | PHI detection, ePHI in email, ePHI at rest | US |
| PCI-DSS | Credit card detection (all brands), cardholder data | Global |
| GDPR | EU PII, cross-border transfer, consent data | EU |
| CCPA | California consumer data, privacy rights | US (CA) |
| SOX | Financial reporting data, earnings | US |
| GLBA | Financial customer data, account info | US |
| FERPA | Student education records | US |
| PIPEDA | Canadian personal information | Canada |
| LGPD | Brazilian personal data | Brazil |
| POPIA | South African personal information | South Africa |
| PDPA | Singapore personal data | Singapore |
| Australian Privacy Act | Australian PII formats | Australia |
| UK Data Protection Act | UK PII, NI numbers | UK |

### 14.2 By Data Type

| Category | Count (Approx.) | Examples |
|----------|-----------------|----------|
| PII patterns | 500+ | SSN, national IDs (90+ countries), driver's licenses, passport numbers |
| Financial | 100+ | Credit cards, IBANs, SWIFT codes, account numbers |
| Healthcare | 50+ | MRNs, ICD codes, medical terms, prescription data |
| IP / Trade Secrets | 30+ | Source code, designs, formulas, patents |
| Credentials | 20+ | Passwords, API keys, certificates, tokens |

---

## 15. Advanced Condition Logic Patterns

### 15.1 Pattern: High-Confidence PII Detection

```
( RegexClassifier:SSN AND DictionaryClassifier:SSN_Context )
OR
( RegexClassifier:CreditCard AND ValidationScript:Luhn )
OR
( DatabaseFingerprint:CustomerDB, threshold >= 3 fields )
```
**WHY:** Three independent detection methods for maximum coverage with minimum false positives.

### 15.2 Pattern: Graduated Context Sensitivity

```
Rule 1 (Low confidence):  RegexClassifier:SSN alone          -> Audit only
Rule 2 (Med confidence):  RegexClassifier:SSN AND Context    -> Notify
Rule 3 (High confidence): DatabaseFingerprint:EmployeeDB     -> Block
```
**WHY:** Different rules for different confidence levels, each with appropriate response.

### 15.3 Pattern: Channel-Specific Action Override

```
Rule 1: PHI classifiers, Channel: Email        -> Quarantine
Rule 2: PHI classifiers, Channel: Cloud         -> Block
Rule 3: PHI classifiers, Channel: Endpoint/USB  -> Confirm/Justify
Rule 4: PHI classifiers, Channel: Discovery     -> Audit + Remediate
```
**WHY:** Same data, different enforcement per channel because different channels have different business impacts and available actions.

### 15.4 Pattern: Time-Based Policy (Business Hours vs. After Hours)

```
Rule 1: Sensitive data + source:all + destination:external
        During business hours (8am-6pm): Audit + Notify
        After hours (6pm-8am + weekends): Block + Escalate
```
**WHY:** After-hours data transfers are higher risk than business-hours transfers.
**GOTCHA:** Time-based rules require RAP or custom scripting. Not natively available in standard rule conditions. Implement via UEBA risk scoring (after-hours access increases risk score).

### 15.5 Pattern: Negative Fingerprint (Exclude Known Safe Content)

```
IF: (PII Classifiers match)
AND NOT: (FileFingerprint:PublicDocuments, 90% confidence)
AND NOT: (KeyPhrase: "This document is approved for public release")
```
**WHY:** Exclude known-safe content from triggering PII policies.

### 15.6 Pattern: Multi-Stage Escalation

```
Stage 1: First offense     -> Audit + User notification (educational)
Stage 2: 2nd offense (7d)  -> Audit + Manager notification (escalation)
Stage 3: 3rd offense (30d) -> Block + Security team notification (investigation)
Stage 4: 4th+ offense      -> Block + HR notification + SIEM alert (disciplinary)
```
**WHY:** Progressive discipline model aligned with HR policy.
**GOTCHA:** Multi-stage escalation requires cumulative/drip DLP configuration with careful threshold settings. Stage tracking resets when the time window expires.

### 15.7 Pattern: Data Sovereignty Enforcement

```
IF: (EU PII Classifiers: any EU member state national ID or IBAN)
AND: (Source: EU office users or EU cloud region)
AND: (Destination: non-EU cloud regions or non-EU email domains)
AND NOT: (Destination: adequate countries list [UK, JP, CA, etc.])
AND NOT: (Destination: SCC partner list [approved contractual partners])
THEN: Block + Notify DPO + SIEM alert
```
**WHY:** GDPR Article 44-49 compliance for cross-border data transfers.
**GOTCHA:** Adequacy decisions change over time (e.g., EU-US Data Privacy Framework). Maintain the adequate countries list and SCC partner list as living documents.
