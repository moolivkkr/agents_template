# Cloud DLP — Advanced Reference
## Broadcom Symantec DLP (Enforce Server, version 16.x/25.x/26.x)

> **Purpose:** Per-cloud-app configuration details, API vs proxy mode deep dive, cloud-specific response actions, DLP profile management via API, EDM/IDM cloud indexing, and end-to-end scenarios.
> **Evidence sources:** doc-corpus.md [S1-S28], video-intelligence.md [V1-V45], api-intelligence.md

---

## Table of Contents

1. [Per-Cloud-App Configuration](#1-per-cloud-app-configuration)
2. [API Mode vs Proxy Mode Deep Dive](#2-api-mode-vs-proxy-mode-deep-dive)
3. [DLP Profile Configuration](#3-dlp-profile-configuration)
4. [Cloud-Specific Response Actions](#4-cloud-specific-response-actions)
5. [EDM/IDM Cloud Indexing](#5-edmidm-cloud-indexing)
6. [Generative AI Protection](#6-generative-ai-protection)
7. [Cloud DLP API Reference](#7-cloud-dlp-api-reference)
8. [Hybrid Deployment Patterns](#8-hybrid-deployment-patterns)
9. [Cloud Incident Management](#9-cloud-incident-management)
10. [End-to-End Enterprise Scenario](#10-end-to-end-enterprise-scenario)

---

## 1. Per-Cloud-App Configuration

### 1.1 Microsoft 365 — Complete Configuration

#### OneDrive for Business

```
+=========================================================================+
|  Microsoft 365 > OneDrive Configuration                                  |
+=========================================================================+
|                                                                         |
|  Scan Scope:                                                             |
|    User scope:          (o) All users   ( ) Specific users/groups       |
|    Specific users:      [                                        ]      |
|    AD group filter:     [SG-DLP-OneDrive-Scan                   ]      |
|                                                                         |
|  Content Types:                                                          |
|    [x] Documents (Office, PDF)                                           |
|    [x] Spreadsheets                                                      |
|    [x] Presentations                                                     |
|    [x] Images (OCR-enabled)                                              |
|    [x] Archives (zip, rar)                                               |
|    [x] Text files                                                        |
|    [ ] Video files                                                       |
|    [ ] Audio files                                                       |
|                                                                         |
|  Sharing Monitoring:                                                     |
|    [x] Detect externally shared files                                    |
|    [x] Detect anonymous sharing links                                    |
|    [x] Detect sharing with personal email addresses                     |
|                                                                         |
|  Scan Limits:                                                            |
|    Max file size (MB):   [100 ]                                          |
|    Max files per scan:   [10000]                                         |
|                                                                         |
+=========================================================================+
```

**Example 1 -- Scope to high-risk departments:**
Set User scope to "Specific users/groups" and filter by AD group `SG-Finance-Users`. Only Finance department OneDrive accounts are scanned. Engineering and Marketing are excluded to reduce scanning volume and API consumption.

**Example 2 -- OCR scanning for scanned documents:**
Enable "Images (OCR-enabled)" to scan screenshots and scanned PDFs uploaded to OneDrive. CDS uses cloud OCR to extract text from images before applying DLP rules. This catches scanned contracts, photographed documents, and screenshots of sensitive applications.

[S24] Evidence: A

#### SharePoint Online

```
+=========================================================================+
|  Microsoft 365 > SharePoint Configuration                                |
+=========================================================================+
|                                                                         |
|  Scan Scope:                                                             |
|    [x] All site collections                                              |
|    [ ] Specific site collections only:                                   |
|        [https://corp.sharepoint.com/sites/Finance      ]               |
|        [https://corp.sharepoint.com/sites/Legal         ]               |
|                                                                         |
|  Content Types:                                                          |
|    [x] Document libraries                                                |
|    [x] List attachments                                                  |
|    [x] Page content (wiki, modern pages)                                |
|    [ ] Site templates and assets                                        |
|                                                                         |
|  Version Handling:                                                       |
|    (o) Current version only                                              |
|    ( ) All versions (increases scan volume significantly)               |
|                                                                         |
+=========================================================================+
```

**Example -- Scan sensitive site collections only:**
Configure SharePoint to scan only `Finance` and `Legal` site collections. These contain the most sensitive data. General-purpose sites (IT, Marketing) are excluded to stay within API rate limits.

[S24] Evidence: A

#### Exchange Online

```
+=========================================================================+
|  Microsoft 365 > Exchange Online Configuration                           |
+=========================================================================+
|                                                                         |
|  Scan Scope:                                                             |
|    [x] All mailboxes                                                     |
|    [ ] Specific mailboxes only                                          |
|                                                                         |
|  Folder Scope:                                                           |
|    [x] Inbox          [x] Sent Items                                    |
|    [x] Drafts         [ ] Deleted Items                                 |
|    [x] Custom folders                                                    |
|                                                                         |
|  Content Scope:                                                          |
|    [x] Email body                                                        |
|    [x] Attachments                                                       |
|    [x] Embedded images (OCR)                                            |
|                                                                         |
|  Time Range:                                                             |
|    Scan emails from:   [Last 90 days              v]                    |
|                                                                         |
+=========================================================================+
```

**Example -- Historical email compliance scan:**
Set time range to "Last 365 days" for initial compliance audit. CDS scans all email from the past year for HIPAA-relevant content. After the initial scan, switch to "Last 90 days" for ongoing monitoring. This approach catches historical compliance violations while reducing ongoing scan volume.

[S24] Evidence: A

#### Teams

```
+=========================================================================+
|  Microsoft 365 > Teams Configuration                                     |
+=========================================================================+
|                                                                         |
|  Scan Scope:                                                             |
|    [x] Files shared in Teams channels                                    |
|    [x] Files shared in Teams private chats                              |
|    [ ] Channel message text (API limitations)                           |
|    [ ] Chat message text (API limitations)                              |
|                                                                         |
|  Note: Teams chat message content scanning requires Microsoft           |
|  Compliance APIs with additional licensing. File scanning is             |
|  available via the standard Microsoft Graph API.                        |
|                                                                         |
+=========================================================================+
```

**Limitation:** Teams chat message content scanning (the text of messages, not attached files) requires Microsoft Graph Compliance APIs and may require additional Microsoft licensing. File attachments shared in Teams are scanned via OneDrive/SharePoint APIs (since Teams files are stored in SharePoint).

[S24] Evidence: A-B

---

### 1.2 Google Workspace — Complete Configuration

```
+=========================================================================+
|  Google Workspace > Complete Configuration                               |
+=========================================================================+
|                                                                         |
|  Google Drive:                                                           |
|    Scan scope:                                                           |
|      [x] My Drive (all users)                                            |
|      [x] Shared Drives (formerly Team Drives)                            |
|      [x] Shared with Me files                                           |
|    Content types:   [All supported file types              v]           |
|    Max file size:   [100 MB                                 ]           |
|                                                                         |
|  Gmail:                                                                  |
|    Scan scope:                                                           |
|      [x] All user mailboxes                                              |
|      [x] Sent mail                                                       |
|      [x] Attachments                                                     |
|    Time range:      [Last 90 days                          v]           |
|                                                                         |
|  Sharing Detection:                                                      |
|    [x] Detect files shared externally (outside domain)                  |
|    [x] Detect files shared with "Anyone with the link"                  |
|    [x] Detect files shared with personal Gmail addresses                |
|                                                                         |
+=========================================================================+
```

**Example -- Detect externally shared customer data in Google Drive:**
DLP profile with EDM profile of customer database. When a sales rep shares a Google Sheet containing customer records via "Anyone with the link," CDS detects the EDM match. Response: change sharing to "Restricted" (removes public link) and notify file owner.

[S24] Evidence: A

---

### 1.3 Box Enterprise — Complete Configuration

```
+=========================================================================+
|  Box Enterprise > Complete Configuration                                 |
+=========================================================================+
|                                                                         |
|  Authentication:                                                         |
|    Method:    [JWT Server Authentication                    v]          |
|    Client ID: [abc123def456ghi789                            ]          |
|    Box App:   Authorized in Box Admin Console > Apps                    |
|                                                                         |
|  Scan Scope:                                                             |
|    [x] All managed user accounts                                         |
|    [x] Shared folders and collaborations                                |
|    [x] Box Relay workflows                                              |
|                                                                         |
|  External Collaboration:                                                 |
|    [x] Detect external collaborator access                              |
|    [x] Detect public shared links                                        |
|    [x] Detect Box Notes shared externally                               |
|                                                                         |
|  Content Types:                                                          |
|    [x] All file types (Box supports 120+ preview types)                 |
|                                                                         |
+=========================================================================+
```

**Example 1 -- Quarantine externally shared PCI data:**
EDM profile detects credit card data in Excel file shared with external collaborator via Box. Response: (a) move file to admin quarantine folder, (b) remove external collaborator, (c) notify file owner.

**Example 2 -- Monitor Box Relay workflows:**
Box Relay (automated workflows) may process sensitive data without human oversight. DLP scans files passing through Relay workflows to ensure automated processes do not expose sensitive content.

[S24] Evidence: A

---

### 1.4 Salesforce — Complete Configuration

```
+=========================================================================+
|  Salesforce > Complete Configuration                                     |
+=========================================================================+
|                                                                         |
|  Authentication:                                                         |
|    Method:       [Connected App (OAuth2)                    v]          |
|    Consumer Key: [3MVG9...                                   ]          |
|    Login URL:    [https://login.salesforce.com                ]         |
|                                                                         |
|  Scan Scope:                                                             |
|    [x] Attachments (classic attachments on records)                     |
|    [x] Salesforce Files (ContentVersion / Content Library)              |
|    [x] Chatter file attachments                                          |
|    [x] Notes & Attachments on Accounts, Contacts, Cases                 |
|    [ ] Record field content (requires custom configuration)             |
|                                                                         |
|  Object Scope:                                                           |
|    [x] Account     [x] Contact     [x] Case                            |
|    [x] Opportunity  [x] Lead       [ ] Custom Objects                   |
|                                                                         |
+=========================================================================+
```

**Example -- Detect credit card data in Case attachments:**
Support reps receive customer credit card data via screenshots or documents attached to Cases. DLP scans all Case attachments. When credit card numbers are detected, the attachment is quarantined and the support rep is notified to use the secure payment processing system instead.

[S24] Evidence: A

---

## 2. API Mode vs Proxy Mode Deep Dive

### 2.1 Coverage Matrix

| Capability | API Mode | Proxy Mode |
|-----------|---------|-----------|
| Scan existing data (at rest) | YES | NO |
| Real-time upload blocking | NO (near-real-time, 1-15 min delay) | YES (inline blocking) |
| Scan data in transit | Near-real-time | YES (inline) |
| Sanctioned app coverage | YES (apps with API connectors) | YES |
| Unsanctioned app coverage | NO | YES (Shadow IT) |
| HTTPS inspection needed | NO (API access, no traffic interception) | YES (proxy SSL inspection) |
| Quarantine in cloud app | YES (native cloud quarantine) | NO (block at proxy, not in app) |
| Revoke sharing | YES | NO |
| Apply sensitivity label | YES (MIP integration) | NO |
| User coaching page | NO | YES |
| Works with managed devices only | NO (scans all data regardless of device) | YES (requires proxy routing) |
| Works with unmanaged devices (BYOD) | Partial (scans data they access) | NO (unless proxy is enforced) |

### 2.2 When to Use Each Mode

| Scenario | Recommended Mode | Rationale |
|----------|-----------------|-----------|
| Compliance audit of existing cloud data | API | Need to scan data at rest |
| Block sensitive uploads in real-time | Proxy | Need inline blocking |
| Protect against Shadow IT | Proxy | Only proxy sees unsanctioned app traffic |
| Quarantine files in cloud apps | API | Cloud-native quarantine actions |
| BYOD / unmanaged device coverage | API | Proxy requires device enrollment |
| GenAI prompt protection | Proxy | Need to intercept form submissions |
| Shared drive/folder remediation | API | Need to revoke sharing links |
| Maximum coverage | Both (API + Proxy) | Defense-in-depth |

[S1, S2, S24] Evidence: A

---

## 3. DLP Profile Configuration

### 3.1 DLP Profile Structure (CloudSOC)

```
DLP Profile
  |
  +-- Profile Metadata (name, description, severity)
  |
  +-- Rules (one or more detection rules)
  |     |
  |     +-- Rule 1: Data Identifier (Credit Card Number)
  |     +-- Rule 2: Keyword Match ("CONFIDENTIAL")
  |     +-- Rule 3: EDM Profile (customer database index)
  |     +-- Rule 4: IDM Profile (confidential document index)
  |     +-- Rule 5: Regex Pattern (custom pattern)
  |
  +-- Response Actions
  |     |
  |     +-- Quarantine
  |     +-- Revoke Sharing
  |     +-- Apply Label
  |     +-- Notify
  |     +-- Two-Factor Auth
  |
  +-- App Assignment (which apps this profile applies to)
```

### 3.2 Advanced Rule Configuration

```
+=========================================================================+
|  DLP Profile: Financial-Data-Protect                                     |
+=========================================================================+
|                                                                         |
|  Rules:                                                                  |
|                                                                         |
|  Rule 1: Compound Rule (AND)                                            |
|    Condition A: Data Identifier = Credit Card Number (Luhn)             |
|    AND                                                                   |
|    Condition B: Keyword proximity = "customer" NEAR "payment"           |
|    Minimum matches: 3                                                    |
|    Severity: Critical                                                    |
|                                                                         |
|  Rule 2: EDM Rule                                                        |
|    EDM Index: Customer-PII-Index (SSN, Name, Email, Phone)             |
|    Match fields: 3 of 4                                                  |
|    Severity: High                                                        |
|                                                                         |
|  Rule 3: IDM Rule                                                        |
|    IDM Index: Financial-Reports-Index                                    |
|    Match threshold: 40% content similarity                              |
|    Severity: High                                                        |
|                                                                         |
|  Rule 4: MIP Label Rule                                                  |
|    Detect files labeled "Highly Confidential"                           |
|    AND shared externally                                                 |
|    Severity: Critical                                                    |
|                                                                         |
+=========================================================================+
```

**Example 1 -- Compound rule for PCI with context:**
Rule requires BOTH credit card number detection AND proximity to payment-related keywords. This eliminates false positives from test data, documentation, or code containing credit card number patterns.

**Example 2 -- EDM with partial field matching:**
Match 3 of 4 fields (SSN, Name, Email, Phone) from the customer database. This catches records even when one field is missing (e.g., phone number not present in the document).

**Example 3 -- MIP label + sharing detection:**
Detect files with "Highly Confidential" MIP label that are shared externally. This combines classification awareness with sharing analysis -- the label alone is not a violation, but sharing a labeled file externally is.

[S24, API-intelligence] Evidence: A

---

## 4. Cloud-Specific Response Actions

### 4.1 Quarantine in Cloud

```
Quarantine Flow (OneDrive example):

  1. DLP detects violation in file: /Users/jsmith/Documents/customer_data.xlsx
  2. CDS sends quarantine action to O365 connector
  3. Connector executes via Microsoft Graph API:
     a. Move file to admin quarantine folder:
        /DLP-Quarantine/2025-05-21/customer_data.xlsx
     b. Set file permissions: admin-only access
     c. Remove all sharing links
     d. Replace original file with tombstone (optional)
  4. Incident created in CloudSOC
  5. File owner notified via email
```

**Quarantine folder options:**
| Option | Location | Access | Evidence |
|--------|----------|--------|----------|
| Admin-owned quarantine folder | Dedicated admin OneDrive or SharePoint site | Admin only | A [S24] |
| In-place quarantine | Same location, permissions restricted | Admin only | A [S24] |
| Compliance quarantine | Microsoft 365 Compliance Center hold | Legal/compliance team | B [S24] |

### 4.2 Revoke Sharing

```
Revoke Sharing Flow:

  Before:
    File: customer_report.xlsx
    Sharing: "Anyone with the link" (anonymous access)
    External collaborator: partner@external.com
    Internal sharing: 5 team members

  After DLP Response:
    File: customer_report.xlsx
    Sharing: "Specific people" (only original owner)
    External collaborator: REMOVED
    Internal sharing: REMOVED (optional, configurable)
    Anonymous link: DELETED
```

**Configurable revoke options:**
| Option | Behavior | Use Case |
|--------|----------|----------|
| Revoke external sharing only | Remove external collaborators and anonymous links; keep internal sharing | Balance security with internal collaboration |
| Revoke all sharing | Remove ALL sharing (external + internal) | Maximum security for highly sensitive data |
| Revoke anonymous links only | Remove "Anyone with the link" but keep named collaborators | Remove public access while preserving known partnerships |

[S24] Evidence: A

### 4.3 Apply Sensitivity Label

```
Label Application Flow:

  1. DLP detects financial data (IDM match) in SharePoint document
  2. Document has no MIP sensitivity label
  3. Response action: Apply "Confidential - Finance" label
  4. MIP SDK applies label:
     a. Label metadata written to document
     b. MIP encryption policy applied (if configured)
     c. Access restrictions enforced based on label policy
  5. Subsequent access requires MIP-authorized identity
```

**Prerequisites for MIP label response action:**
- MIP SDK configured on Enforce Server or CDS
- MIP tenant credentials registered
- Sensitivity labels published in Microsoft 365 Compliance Center
- Label policy mapped to DLP profile in CloudSOC

[S1, S2, S3] Evidence: A

---

## 5. EDM/IDM Cloud Indexing

### 5.1 Remote Indexer Tool Workflow

```
Cloud EDM/IDM Index Creation:

  Step 1: Create EDM/IDM profile on Enforce Server (standard workflow)
  Step 2: Export index data
  Step 3: Run Remote Indexer Tool:
           RemoteIndexer.exe -profile "Customer-PII" -output "customer_cloud.idx"
  Step 4: Upload cloud index to CloudSOC:
           CloudSOC > Protect > DLP Profiles > [profile] > Add Index
  Step 5: CDS uses cloud index for detection
```

### 5.2 Remote Indexer Configuration

```
Remote Indexer Command:

  # For EDM:
  RemoteIndexer.exe
    -type EDM
    -profile "Customer-PII-EDM"
    -source "C:\exports\customer_data.csv"
    -output "C:\indexes\customer_cloud_edm.idx"
    -delimiter ","
    -encoding UTF-8

  # For IDM:
  RemoteIndexer.exe
    -type IDM
    -profile "Financial-Reports-IDM"
    -source "C:\confidential_docs\"
    -output "C:\indexes\financial_cloud_idm.idx"
    -recursive
```

**Index refresh schedule:**
| Frequency | Use Case | Notes |
|-----------|----------|-------|
| Daily | Customer database (changes frequently) | Schedule overnight |
| Weekly | Employee records | Moderate change rate |
| Monthly | Document fingerprints (rarely change) | IDM indexes are relatively stable |
| On-demand | After major data imports | Trigger via API (POST /edm/index) for on-prem; manual upload for cloud |

[S1, S24] Evidence: A

---

## 6. Generative AI Protection

### 6.1 Architecture

```
GenAI DLP Protection:

  User (browser)
       |
       v
  Symantec Web Security Service (SWG/proxy)
       |
  (1) User navigates to chat.openai.com
       |
  (2) User types prompt containing code/data
       |
  (3) User clicks Submit (HTTP POST)
       |
  (4) Proxy intercepts POST body
       |
  (5) Content sent to CDS for DLP scanning
       |
  (6a) No violation: POST forwarded to ChatGPT
  (6b) Violation detected:
       - BLOCK: Proxy returns block page
       - COACH: Proxy shows coaching page
       - LOG: Post allowed, incident created
```

### 6.2 GenAI Policy Configuration

```
+=========================================================================+
|  DLP Profile: GenAI-Protection                                           |
+=========================================================================+
|                                                                         |
|  Rules:                                                                  |
|    Rule 1: VML Profile = "Proprietary Source Code"                      |
|    Rule 2: EDM Profile = "Customer PII Database"                        |
|    Rule 3: Data Identifier = "Credit Card Number"                       |
|    Rule 4: Keyword = "CONFIDENTIAL", "INTERNAL ONLY", "RESTRICTED"     |
|    Rule 5: IDM Profile = "Trade Secret Documents"                       |
|                                                                         |
|  Target URLs (proxy policy):                                             |
|    chat.openai.com                                                       |
|    claude.ai                                                             |
|    gemini.google.com                                                     |
|    copilot.microsoft.com                                                 |
|    *.anthropic.com                                                       |
|    *.bard.google.com                                                     |
|                                                                         |
|  Response:                                                               |
|    Rule 1 (source code): BLOCK                                          |
|    Rule 2 (customer PII): BLOCK                                         |
|    Rule 3 (credit cards): BLOCK                                         |
|    Rule 4 (keywords): COACH (user can proceed with justification)       |
|    Rule 5 (trade secrets): BLOCK                                        |
|                                                                         |
+=========================================================================+
```

**Example 1 -- Block source code submission to ChatGPT:**
Developer pastes a function containing proprietary algorithm into ChatGPT prompt. VML source code profile matches. Proxy blocks the submission. Developer sees: "Your submission to this AI service was blocked because it contains content matching our source code protection policy."

**Example 2 -- Coach on keyword-matched submissions:**
Employee submits a document outline containing "CONFIDENTIAL" header to an AI tool. Keyword rule matches. Proxy shows coaching page: "This content may be confidential. Please confirm it does not contain sensitive information before proceeding." Employee can proceed (logged) or cancel.

**Example 3 -- Detection REST API for custom AI integration:**
Use the Detection REST API 2.0 to integrate DLP scanning directly into custom AI applications. Submit prompts to `POST /v2.0/DetectionRequests` before forwarding to the AI model. If violations detected, block the prompt before it reaches the model.

[V35, V36, API-intelligence] Evidence: A

---

## 7. Cloud DLP API Reference

### 7.1 CloudSOC DLP Profile API

```
Base URL (US): https://app.elastica.net/api/clouddlp/protect/public
Base URL (EU): https://app.eu.elastica.net/api/clouddlp/protect/public

Authentication: API Key (configured in CloudSOC Admin > API Keys)
```

#### List DLP Profiles

```
GET /profile
Authorization: Bearer <api_key>

Response:
{
  "profiles": [
    {
      "id": "prof-001",
      "name": "PCI-Cloud-Protect",
      "description": "Detect credit card data in cloud apps",
      "rules": [...],
      "responseActions": [...],
      "lastModified": "2025-05-18T10:00:00Z"
    }
  ]
}
```

#### Create DLP Profile

```
POST /profile
Authorization: Bearer <api_key>
Content-Type: application/json

{
  "name": "HIPAA-Cloud-Monitor",
  "description": "Monitor cloud apps for HIPAA data",
  "rules": [
    {
      "type": "DATA_IDENTIFIER",
      "identifier": "SSN",
      "minMatches": 5,
      "severity": "HIGH"
    },
    {
      "type": "KEYWORD",
      "keywords": ["patient", "diagnosis", "treatment", "medical record"],
      "matchMode": "ANY",
      "severity": "HIGH"
    }
  ],
  "responseActions": [
    {
      "type": "NOTIFY_OWNER"
    },
    {
      "type": "NOTIFY_ADMIN",
      "adminEmail": "compliance@corp.example.com"
    }
  ]
}
```

#### Update DLP Profile

```
PUT /profile/{id}
Authorization: Bearer <api_key>
Content-Type: application/json

{
  "responseActions": [
    {
      "type": "QUARANTINE"
    },
    {
      "type": "REVOKE_SHARING"
    },
    {
      "type": "NOTIFY_OWNER"
    }
  ]
}
```

#### Get Profile Change History

```
GET /profile/{id}/history
Authorization: Bearer <api_key>

Response:
{
  "changes": [
    {
      "timestamp": "2025-05-18T10:00:00Z",
      "user": "admin@corp.example.com",
      "action": "UPDATED",
      "details": "Added QUARANTINE response action"
    }
  ]
}
```

#### List Data Identifiers

```
GET /dataIdentifiers
Authorization: Bearer <api_key>

Response:
{
  "identifiers": [
    {
      "id": "di-cc",
      "name": "Credit Card Number",
      "type": "BUILT_IN",
      "validator": "LUHN",
      "description": "Detects credit card numbers with Luhn validation"
    },
    {
      "id": "di-ssn",
      "name": "US Social Security Number",
      "type": "BUILT_IN",
      "validator": "AREA_NUMBER",
      "description": "Detects US SSN with area number validation"
    }
  ]
}
```

[API-intelligence, S24] Evidence: A

### 7.2 Detection REST API 2.0 (Content Inspection as a Service)

```
# Submit content for DLP scanning
POST https://<cds>/v2.0/DetectionRequests
Content-Type: application/json
Certificate: <client_certificate>

{
  "options": {
    "policyGroupName": "Cloud-DLP-Default"
  },
  "context": {
    "messageSource": "CUSTOM_APP",
    "sender": "jsmith@corp.example.com",
    "recipients": ["external@partner.com"]
  },
  "content": {
    "contentParts": [
      {
        "name": "customer_report.pdf",
        "contentType": "application/pdf",
        "data": "<base64-encoded-file-content>"
      }
    ]
  }
}

Response:
{
  "violationStatus": "VIOLATED",
  "matchedPolicies": [
    {
      "policyName": "PCI-Cloud-Protect",
      "severity": "HIGH",
      "matchedRules": [
        {
          "ruleName": "Credit Card Number",
          "matchCount": 3
        }
      ]
    }
  ],
  "responseActions": [
    {
      "actionType": "BLOCK",
      "reason": "Content violates PCI-DSS policy"
    }
  ]
}
```

**Use case: LLM/GenAI prompt safety.**
The `safeprompt` open-source project (github.com/dlparchitect/safeprompt) uses the Detection REST API 2.0 to scan LLM prompts before they are submitted to AI models. The application submits the prompt to CDS, receives a violation verdict, and either allows or blocks the prompt.

[API-intelligence] Evidence: A

---

## 8. Hybrid Deployment Patterns

### 8.1 Pattern A: Enforce-Managed Cloud

```
Enforce Server (on-prem)
  |
  +-- Creates policies
  +-- Deploys to on-prem detection servers (Network, Endpoint)
  +-- ALSO deploys to Cloud Detection Service (CDS)
  |
  +-- Incidents from all channels reported in one Enforce console:
      - Network incidents (Network Monitor, Prevent)
      - Endpoint incidents (DLP Agents)
      - Cloud incidents (CDS)
```

**Advantage:** Single console for all DLP management. Unified reporting across on-prem and cloud.
**Limitation:** Requires on-prem Enforce Server. Not suitable for cloud-only organizations.

### 8.2 Pattern B: CloudSOC-Only

```
CloudSOC Console (cloud)
  |
  +-- Creates DLP Profiles (cloud-native)
  +-- Connects to cloud apps via API
  +-- Routes traffic via SWG proxy
  |
  +-- All incidents managed in CloudSOC console
  |
  No on-prem Enforce Server required
```

**Advantage:** No on-prem infrastructure. Fast deployment.
**Limitation:** No on-prem DLP coverage. Limited detection technologies (no on-prem EDM/IDM/VML without Remote Indexer).

### 8.3 Pattern C: Full Hybrid

```
Enforce Server (on-prem)                  CloudSOC (cloud)
  |                                           |
  +-- Network DLP (Monitor, Prevent)          +-- Cloud app API scanning
  +-- Endpoint DLP (Agents)                   +-- Proxy-based inline
  +-- On-prem Discover                        +-- Shadow IT detection
  |                                           |
  +-- Policies deployed to CDS <--> CDS <--> CloudSOC policies
  |                                           |
  +-- Incidents: on-prem channel              +-- Incidents: cloud channel
  |                                           |
  +------- Unified dashboard (Enforce + CloudSOC) -------+
```

**Advantage:** Maximum coverage -- on-prem and cloud.
**Limitation:** Two consoles, two policy engines. Requires coordination between on-prem and cloud teams.

[S1, S2, S11, S24] Evidence: A

---

## 9. Cloud Incident Management

### 9.1 CloudSOC Incident View

```
+=========================================================================+
|  CloudSOC > Investigate > Incidents                                      |
+=========================================================================+
|  Filter: [All Apps v]  [All Severities v]  [Last 7 Days v]  [Search]   |
|                                                                         |
|  +-------------------------------------------------------------------+ |
|  | ID     | App       | File              | Severity | Action  | Time  ||
|  |--------|-----------|-------------------|----------|---------|-------||
|  | C-1001 | O365-OD   | customer_data.xlsx| Critical | Quarant.| 2h ago||
|  | C-1002 | Box       | report_Q4.pdf     | High     | Revoked | 3h ago||
|  | C-1003 | GWS-Drive | sales_leads.csv   | High     | Notified| 5h ago||
|  | C-1004 | Salesforce| case_attach.png   | Medium   | Notified| 1d ago||
|  | C-1005 | O365-SPO  | contracts_2025.docx| High    | Labeled | 1d ago||
|  +-------------------------------------------------------------------+ |
+=========================================================================+
```

### 9.2 Incident Detail (Cloud)

```
+=========================================================================+
|  Incident: C-1001                                                        |
+=========================================================================+
|  DLP Profile:   PCI-Cloud-Protect                                       |
|  App:           Microsoft 365 - OneDrive                                 |
|  File:          customer_data.xlsx                                       |
|  Path:          /Documents/Exports/customer_data.xlsx                   |
|  Owner:         jsmith@corp.example.com                                  |
|  Department:    Finance (from Azure AD)                                  |
|  File Size:     2.4 MB                                                   |
|  Created:       2025-05-21 08:15:22 AM                                  |
|  Modified:      2025-05-21 08:15:22 AM                                  |
|                                                                         |
|  Sharing Status (before remediation):                                    |
|    [x] External sharing link (anonymous)                                |
|    [x] Shared with: partner@external.com                                |
|    [x] Internal: finance-team@corp.example.com                          |
|                                                                         |
|  Matches:                                                                |
|    Credit Card Number: 47 unique matches                                 |
|    SSN: 23 unique matches                                                |
|                                                                         |
|  Actions Taken:                                                          |
|    [x] File quarantined (moved to /DLP-Quarantine/)                     |
|    [x] External sharing revoked                                          |
|    [x] Anonymous link deleted                                            |
|    [x] Owner notified via email                                          |
|    [x] Compliance team notified                                          |
|                                                                         |
+=========================================================================+
```

[S24] Evidence: A

---

## 10. End-to-End Enterprise Scenario

### Scenario: Global Company -- Cloud-First DLP Deployment

**Requirement:** Protect PCI, HIPAA, and IP data across Microsoft 365 (5000 users), Google Workspace (2000 users), Box (1000 users), and Salesforce (500 users). Block sensitive data uploads to GenAI tools. Detect Shadow IT.

**Architecture:** Full Hybrid (Enforce + CloudSOC + SWG)

```
Phase 1 (Month 1): CloudSOC setup + O365 API connection
  - Connect Microsoft 365 with Global Admin consent
  - Create DLP profiles: PCI, HIPAA, IP-Protection
  - Enable OneDrive scanning (API mode, notify only)
  - 2-week monitoring period for false positive tuning

Phase 2 (Month 2): Expand to all cloud apps
  - Connect Google Workspace, Box, Salesforce
  - Apply DLP profiles to all connected apps
  - Enable SharePoint and Exchange Online scanning
  - Enable quarantine and revoke-sharing response actions

Phase 3 (Month 3): Inline proxy deployment
  - Deploy Symantec Web Security Service (SWG)
  - Route user traffic through proxy
  - Enable GenAI protection (block/coach)
  - Enable Shadow IT discovery
  - Block top 10 high-risk unsanctioned apps

Phase 4 (Month 4): Hybrid integration
  - Connect CloudSOC to on-prem Enforce Server
  - Deploy Enforce-managed policies to CDS
  - Create Remote Indexer indexes for EDM/IDM
  - Upload cloud indexes to CloudSOC
  - Unified incident dashboard across on-prem and cloud

Phase 5 (Ongoing): Continuous improvement
  - Weekly false positive review
  - Monthly DLP profile refinement
  - Quarterly Shadow IT assessment
  - Annual EDM/IDM index refresh cycle
```

[S1, S2, S24, V34, V35, V38] Evidence: A

---

## Summary

This advanced reference covers per-cloud-app configuration (O365, Google Workspace, Box, Salesforce), API vs proxy mode selection, DLP profile authoring with compound rules, cloud-specific response actions (quarantine, revoke sharing, label application), EDM/IDM cloud indexing via Remote Indexer Tool, Generative AI protection architecture, cloud DLP API reference, hybrid deployment patterns, and enterprise-scale deployment scenarios. Cloud DLP is the fastest-growing DLP channel, driven by SaaS adoption and GenAI tool proliferation.

[S1, S2, S11, S24, V8, V34, V35, V36, V38, API-intelligence] Evidence: A
