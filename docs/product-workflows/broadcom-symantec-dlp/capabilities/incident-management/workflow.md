# Incident Management Workflow -- Broadcom Symantec DLP

> **Capability:** DLP Incident Lifecycle -- from detection to resolution
> **Enforce Console Path:** Incidents > [Network | Endpoint | Discover]
> **Sources:** [S1] Help Center 16.0, [S2] Help Center 25.1, [S3] Help Center 26.1, [S4] Full PDF 16.0, Video #4 (Remediation), Video #24-28 (Incident/ServiceNow), API Intelligence Report

---

## Table of Contents

1. [Overview](#1-overview)
2. [Incident Creation](#2-incident-creation)
3. [Incident Triage](#3-incident-triage)
4. [Incident Investigation](#4-incident-investigation)
5. [Incident Remediation](#5-incident-remediation)
6. [Incident Workflow and Status Transitions](#6-incident-workflow-and-status-transitions)
7. [Smart Response Rules](#7-smart-response-rules)
8. [Automated Response Rules](#8-automated-response-rules)
9. [End User Remediation](#9-end-user-remediation)
10. [SOAR Integration](#10-soar-integration)
11. [Incident REST API](#11-incident-rest-api)
12. [Incident Workflows (DLP 26.1)](#12-incident-workflows-dlp-261)
13. [End-to-End Lifecycle Summary](#13-end-to-end-lifecycle-summary)

---

## 1. Overview

Every time Symantec DLP detects a policy violation -- an employee emails a spreadsheet containing credit card numbers, a USB copy of an IDM-protected document is attempted, or a network scan finds SSNs on a file share -- the system creates an **incident**. The incident is the central artifact around which all DLP operational activity revolves: triage, investigation, remediation, reporting, and compliance evidence.

### Incident Sources

| Source | Detection Server | Data State | Example |
|--------|-----------------|------------|---------|
| Email violation | Network Prevent for Email | Data in Motion | Employee emails PCI data to external recipient |
| Web upload violation | Network Prevent for Web | Data in Motion | User uploads confidential doc to personal cloud via web browser |
| Network traffic violation | Network Monitor | Data in Motion | FTP transfer containing SSNs detected on span port |
| Endpoint copy/paste | Endpoint Prevent | Data in Use | Copy PII from CRM to clipboard, paste to chat app |
| Endpoint USB copy | Endpoint Prevent | Data in Use | Copy customer list to USB drive |
| Endpoint print | Endpoint Prevent | Data in Use | Print document containing financial data |
| File share scan | Network Discover | Data at Rest | Weekly scan finds credit cards in Excel files on HR share |
| Cloud storage scan | Cloud Storage Discover | Data at Rest | Box scan finds HIPAA data shared externally |
| Cloud app monitoring | CloudSOC / CDS | Data in Motion | Sensitive data uploaded to Salesforce |
| API detection | Detection REST API 2.0 | On-demand | Custom app submits content for policy evaluation |

### Incident Volume Context

A typical mid-size enterprise (5,000-20,000 users) generates:
- 500-5,000 incidents per day with basic policies
- 50-500 high/critical incidents per week requiring human review
- Proper policy tuning reduces false positive rate from 40-60% (initial) to 5-15% (tuned)

---

## 2. Incident Creation

### What Triggers an Incident

An incident is created when:
1. Content passes through a detection server (email, web, endpoint, discover)
2. Content inspection matches one or more detection rules in an active policy
3. All compound rule conditions are satisfied (for compound rules, ALL conditions must match)
4. No exception overrides the match

### Incident Record Fields

When an incident is created, the system captures:

| Field Category | Fields | Description |
|----------------|--------|-------------|
| **Identity** | Incident ID (auto-generated), creation timestamp | Unique identifier and when it was created |
| **Detection** | Policy name, rule name(s), detection server, detection method | What triggered the incident |
| **Severity** | Severity level (1-4: High, Medium, Low, Informational) | Risk level assigned by the policy |
| **Content** | Matched content snippets, match count, data identifiers triggered | What sensitive data was detected |
| **Evidence** | Original message/file (if captured), matched content context | Forensic evidence |
| **Context** | Protocol (SMTP, HTTP, FTP, USB, etc.), file name, file type | How the data was being moved |
| **People** | Sender/source, recipient/destination, endpoint user, endpoint hostname | Who was involved |
| **Network** | Source IP, destination IP/URL, endpoint hostname | Where it happened |
| **Status** | Status (default: New), assignment, remediation status | Current workflow state |
| **Custom** | Custom attributes (up to N, defined by admin) | Organization-specific fields (cost center, data classification, etc.) |

### Evidence Capture

DLP captures different levels of evidence depending on configuration:

| Evidence Level | What Is Captured | Storage Impact |
|---------------|-----------------|----------------|
| **Full** | Original message/file + matched content + context | Highest -- stores complete evidence |
| **Matched Content Only** | Only the portions matching detection rules | Moderate |
| **Metadata Only** | Incident metadata without content | Lowest -- for high-volume, low-risk policies |

Evidence storage configuration: **Manage > Policies > Response Rules > Limit Incident Data Retention**

### Severity Assignment

Severity is defined in the policy and assigned at incident creation:

| Level | Numeric | Label | Typical Use |
|-------|---------|-------|-------------|
| 1 | 1 | High | Credit card numbers, SSNs, health records leaving organization |
| 2 | 2 | Medium | Internal confidential documents, partial PII matches |
| 3 | 3 | Low | Policy violations with limited data exposure |
| 4 | 4 | Informational | Monitoring-only; tracking data movement patterns |

Severity can be overridden by response rules or manually adjusted during investigation.

---

## 3. Incident Triage

### Incident List View

**Navigation:** `Incidents > [Network | Endpoint | Discover]`

The incident list is the primary triage interface:

```
+------------------------------------------------------------------------+
| Incidents > Network                                            [Filters]|
+------------------------------------------------------------------------+
| [ ] | ID     | Severity | Policy          | Sender       | Status     |
+------------------------------------------------------------------------+
| [ ] | 12345  | HIGH     | PCI-DSS         | j.smith@corp | New        |
| [ ] | 12346  | MEDIUM   | HIPAA-PHI       | m.jones@corp | New        |
| [ ] | 12347  | LOW      | IP-Confidential | r.doe@corp   | In Process |
| [ ] | 12348  | HIGH     | PCI-DSS         | a.lee@corp   | Escalated  |
| [ ] | 12349  | INFO     | Email-Monitor   | k.park@corp  | New        |
+------------------------------------------------------------------------+
| Selected: 0  | Total: 1,247  | Page 1 of 63          [< Prev] [Next >]|
+------------------------------------------------------------------------+
```

### Filtering Incidents

Available filters (can be combined):

| Filter | Values | Purpose |
|--------|--------|---------|
| Severity | High, Medium, Low, Informational | Focus on high-risk incidents |
| Status | New, In Process, Escalated, False Positive, Resolved, etc. | Find open incidents |
| Policy | Any active policy name | Filter by compliance domain (PCI, HIPAA, GDPR) |
| Date Range | Start date to end date | Time-bounded triage |
| Detection Server | Network, Endpoint, Discover | Filter by detection channel |
| Sender/User | Username, email, hostname | Find all incidents for a specific user |
| Match Count | Minimum match count | Prioritize incidents with many matches |
| Custom Attribute | Any custom attribute value | Filter by department, cost center, etc. |

### Bulk Operations

Select multiple incidents with checkboxes, then apply:
- **Set Status**: Change status of all selected incidents
- **Set Severity**: Reclassify severity in bulk
- **Assign**: Assign all to a specific user/role
- **Execute Smart Response**: Apply a Smart Response rule to all selected
- **Export**: Export selected incidents to CSV

### Saved Searches (Reports)

Save frequently used filter combinations:
1. Set your desired filters
2. Click **Save As**
3. Name the saved search (e.g., "Open PCI Incidents - High Severity")
4. Set visibility: Private (you only) or Shared (your role)
5. Re-run saved searches from the report dropdown

---

## 4. Incident Investigation

### Incident Detail View (Incident Snapshot)

**Navigation:** Click any incident ID to open the detail view.

```
+------------------------------------------------------------------------+
| Incident #12345 -- PCI-DSS Policy Violation                           |
+------------------------------------------------------------------------+
| Status: [New v]     Severity: [HIGH v]     Assigned: [-- Unassigned v] |
+------------------------------------------------------------------------+
| DETECTION TAB                                                          |
|   Policy: PCI DSS - Credit Card Numbers                               |
|   Rule: Content Matches Data Identifier (Credit Card - Luhn)          |
|   Detection Server: network-prevent-email-01                           |
|   Protocol: SMTP                                                       |
|   Match Count: 3                                                       |
+------------------------------------------------------------------------+
| MATCHED CONTENT TAB                                                    |
|   [REDACTED] 4111-XXXX-XXXX-1234  (Visa, Luhn validated)            |
|   [REDACTED] 5500-XXXX-XXXX-5678  (Mastercard, Luhn validated)      |
|   [REDACTED] 3782-XXXX-XXXX-9012  (Amex, Luhn validated)            |
|   Context: Found in attachment "Q1-Payments.xlsx", Sheet "Transactions"|
+------------------------------------------------------------------------+
| MESSAGE TAB                                                            |
|   From: john.smith@corp.local                                          |
|   To: external-auditor@audit-firm.com                                  |
|   Subject: "Q1 Payment Records for Audit"                             |
|   Date: 2026-05-20 14:32:07 UTC                                       |
|   Attachment: Q1-Payments.xlsx (2.3 MB)                                |
+------------------------------------------------------------------------+
| HISTORY TAB                                                            |
|   2026-05-20 14:32:07 - Incident created (auto)                      |
|   2026-05-20 14:32:08 - Response: Block Message (auto)               |
|   2026-05-20 14:32:08 - Response: Send Notification to sender (auto) |
+------------------------------------------------------------------------+
| NOTES TAB                                                              |
|   (No notes yet)                                                       |
|   [Add Note]                                                           |
+------------------------------------------------------------------------+
| ACTIONS                                                                |
|   [Smart Response v]  [Export]  [View Original Message]               |
+------------------------------------------------------------------------+
```

### Content Inspection

The **Matched Content** tab shows exactly what DLP detected:

- **Highlighted matches**: The specific text/patterns that triggered detection
- **Context window**: Surrounding text for analyst review
- **Data identifier details**: Which data identifier matched (e.g., "Credit Card Number - Luhn Check")
- **Match confidence**: For VML matches, the confidence score
- **MIP label**: If the content had a Microsoft Information Protection label

### User Investigation

From an incident, investigate the user's DLP history:

1. Click the sender/user name in the incident
2. View **User Incident History**: All incidents for this user across all channels
3. **User Risk Score** (if ICA integration is enabled): 1-100 behavioral risk score
4. **Department/Manager** (if LDAP lookup plugin is configured): Organizational context

**Example investigation questions:**
- Is this user's first incident, or a repeat offender?
- Are incidents concentrated in one policy (PCI) or across many?
- Has the user's incident frequency been increasing?
- What is their risk score trend?

### Data Flow Analysis

Understand where data was going:

| Channel | Data Flow Details |
|---------|-------------------|
| Email | Sender -> Recipient(s), Subject, Attachment name |
| Web | Source user -> Destination URL, HTTP method, upload type |
| USB | User -> Device serial number, file name, device type |
| Clipboard | Source application -> Destination application |
| Print | User -> Printer name, document title |
| Cloud | User -> Cloud app name, file name, sharing status |
| Discover | File location (UNC path), file owner, access permissions |

### Evidence Preservation

For incidents requiring forensic investigation:

1. **View Original Message**: Incidents > [incident] > View Original Message
   - Downloads the complete original email/file as it was captured
   - Available if evidence capture was set to "Full"

2. **Export Incident**: Includes all metadata, matched content, history
   - CSV export for documentation
   - JSON export via API for automated processing

3. **Chain of Custody**: The incident history tab provides an immutable audit trail of:
   - Who viewed the incident
   - Who changed status/severity
   - What remediation actions were taken and when
   - What notes were added

---

## 5. Incident Remediation

### Remediation Approaches

| Approach | Description | When to Use |
|----------|-------------|-------------|
| **Automated Response** | System takes action immediately on detection | Well-understood policy violations (e.g., block PCI data in email) |
| **Smart Response** | Human triggers predefined action from incident view | Analyst reviews incident, then applies appropriate remediation |
| **Manual Remediation** | Analyst takes ad-hoc action (notes, status change, external action) | Complex or unusual situations requiring judgment |
| **End User Remediation** | Data owner/violator resolves the incident themselves | High-volume, low-risk incidents; decentralized operations |

### Remediation Actions by Channel

| Action | Email | Web | Endpoint | Discover | Cloud |
|--------|-------|-----|----------|----------|-------|
| Block/Prevent | Yes | Yes | Yes | N/A | Yes |
| Quarantine | Yes (SMG) | No | No | Yes | Yes |
| Encrypt | Yes (gateway) | No | Yes | Yes | Yes (MIP) |
| Notify User | Yes | Yes | Yes (popup) | Yes | Yes |
| Redirect | Yes (email) | No | No | No | No |
| Add Header | Yes (X-header) | No | No | No | No |
| Remove Sharing | No | No | No | No | Yes |
| Apply MIP Label | No | No | No | Yes | Yes |
| Tag/Label | No | No | No | Yes | Yes |
| Copy to Evidence | No | No | No | Yes | No |
| User Cancel (with justification) | No | No | Yes | No | No |

### Remediation Status Tracking

Each incident has a remediation status field:

| Status | Meaning |
|--------|---------|
| Not Set | No remediation attempted |
| Pending | Remediation in progress |
| Completed | Remediation action succeeded |
| Failed | Remediation action failed (e.g., quarantine path inaccessible) |

### Justification Collection

For endpoints with **User Cancel** response rules:

1. Endpoint user triggers a policy violation (e.g., copy to USB)
2. DLP popup appears with options: "Cancel" or "Proceed with Justification"
3. If user clicks "Proceed", they must enter a justification reason
4. Justification is stored in the incident record
5. Analyst can review justifications to identify policy exceptions or training needs

---

## 6. Incident Workflow and Status Transitions

### Default Statuses

Symantec DLP comes with these default incident statuses:

| Status | Purpose | Typical Usage |
|--------|---------|---------------|
| **New** | Just created, not yet reviewed | Auto-assigned on incident creation |
| **In Process** | Being investigated | Analyst picks up the incident |
| **Escalated** | Requires higher-level review | Analyst cannot resolve; escalates to manager |
| **False Positive** | Incorrectly triggered | Matched content is not actually sensitive |
| **Configuration Error** | Policy needs tuning | Detection rule is too broad or incorrect |
| **Resolved** | Remediation complete | Incident fully handled |

### Custom Statuses

Admins can add custom statuses:

**Navigation:** System > Incident Data > Attributes > Incident Statuses

Examples of custom statuses:
- "Waiting for User Response" -- sent to data owner, awaiting reply
- "Under Legal Review" -- escalated to legal department
- "Training Assigned" -- user enrolled in security awareness training
- "Exception Granted" -- approved business exception

### Status Transition Workflow

```
                  +-------+
                  |  New  |
                  +---+---+
                      |
           +----------+----------+
           |                     |
     +-----v------+      +------v-----+
     | In Process |      | False      |
     +-----+------+      | Positive   |
           |              +------------+
     +-----+------+
     |            |
+----v---+  +----v------+
|Resolved|  | Escalated |
+--------+  +-----+-----+
                  |
            +-----v------+
            | Resolved   |
            +------------+
```

**Typical workflow:**
1. Incident created -> Status: **New**
2. Analyst opens incident -> Changes status to: **In Process**
3. Analyst investigates matched content, user history, context
4. Decision:
   - False positive -> Status: **False Positive** (done)
   - Needs policy tuning -> Status: **Configuration Error** (escalate to policy admin)
   - Legitimate violation, resolved -> Status: **Resolved** (done)
   - Complex/serious violation -> Status: **Escalated** (to incident manager or legal)
5. Escalated incident reviewed by senior analyst/manager
6. Resolution -> Status: **Resolved**

### Assignment

Incidents can be assigned to:
- **Specific users**: Manual assignment to named analysts
- **Roles**: Assigned to a DLP role (any user in that role can work it)
- **Round-robin**: Automatic distribution across analysts (requires custom automation)
- **Skill-based**: Route PCI incidents to PCI-trained analysts, HIPAA to healthcare team

Assignment is set in the incident detail view via the "Assigned" dropdown.

### Escalation

Escalation mechanisms:
- **Manual**: Analyst changes status to "Escalated" and assigns to a manager/senior role
- **Time-based**: Automated response rule monitors incident age; if not resolved within SLA, auto-escalate
- **Severity-based**: Automated response rule escalates all Critical/High incidents automatically
- **SOAR-driven**: Cortex XSOAR or ServiceNow playbook handles escalation logic

### Custom Attributes

Custom attributes add organization-specific context to incidents:

**Navigation:** System > Incident Data > Attributes > Custom Attributes tab

| Custom Attribute | Type | Purpose |
|-----------------|------|---------|
| Cost Center | Dropdown | Map incident to business unit |
| Data Classification | Dropdown | Confidential, Internal, Public |
| Remediation Owner | Text | Name of person responsible for remediation |
| Risk Assessment | Dropdown | Critical Risk, High Risk, Acceptable Risk |
| Regulatory Scope | Multi-select | PCI, HIPAA, GDPR, SOX |
| Training Status | Dropdown | Not Required, Assigned, Completed |

Custom attributes can be:
- Populated manually by analysts
- Auto-populated by **Lookup Plugins** (e.g., LDAP lookup populates "Department" from Active Directory)
- Used in reporting filters and dashboard widgets
- Updated via REST API (`PATCH /incidents`)

### Incident Comments and Audit Trail

**Comments:**
- Added via the Notes tab on the incident detail view
- Support free-text entries
- Timestamped with the username of the commenter
- Used for investigation notes, communication between analysts, resolution documentation

**Audit Trail:**
- Accessed via the History tab on the incident detail view
- Immutable record of all changes to the incident:
  - Status changes (who, when, from/to)
  - Severity changes
  - Assignment changes
  - Response rule executions
  - Notes added
  - Custom attribute changes
  - Evidence viewed/exported
- Available via REST API: `GET /incidents/{id}/history` (DLP 15.8+)

---

## 7. Smart Response Rules

Smart Response rules are **human-triggered** remediation actions that analysts can execute from the incident detail view.

### What Smart Responses Can Do

| Action | Description |
|--------|-------------|
| Set Status | Change incident status to a predefined value |
| Set Custom Attribute | Set a custom attribute value |
| Send Email Notification | Send a notification email (to manager, data owner, legal, etc.) |
| Log to Syslog | Send a syslog message to SIEM |
| Add Note | Add a predefined note to the incident |

### What Smart Responses Cannot Do

- Cannot block, quarantine, or encrypt (those are Automated Response actions only)
- Cannot trigger conditions (always available when manually invoked)
- Are limited to the actions listed above

### Creating a Smart Response Rule

**Navigation:** Manage > Policies > Response Rules > Add Response Rule > Smart Response

1. Click **Add Response Rule**
2. Select **Smart Response**
3. Enter rule name: "Escalate to Legal"
4. Click **Next** to configure actions
5. Add Action: **Send Email Notification**
   - To: `legal-team@corp.com`
   - Subject: "DLP Incident Escalation: {IncidentID}"
   - Body: "Incident #{IncidentID} requires legal review. Policy: {PolicyName}. Severity: {Severity}."
6. Add Action: **Set Status** -> "Under Legal Review"
7. Add Action: **Add Note** -> "Escalated to legal team for review"
8. Click **Save**

### Using Smart Responses

1. Open an incident in the detail view
2. Click the **Smart Response** dropdown
3. Select "Escalate to Legal"
4. Confirm execution
5. Actions execute: email sent, status changed, note added
6. History tab records the Smart Response execution

### Example Smart Response Rules

| Rule Name | Actions | Use Case |
|-----------|---------|----------|
| Mark as False Positive | Set Status: False Positive + Add Note: "Confirmed false positive by analyst" | Quick false positive dismissal |
| Escalate to Manager | Send Email to manager + Set Status: Escalated + Set Attr: "Escalation Reason: Manager Review Required" | Escalation workflow |
| Assign Security Training | Set Attr: "Training Status: Assigned" + Send Email to user: "Complete DLP training by {date}" | User education |
| Request User Justification | Send Email to user: "Please provide business justification for incident #{ID}" + Set Status: "Waiting for User Response" | Justification collection |
| Close - Business Exception | Set Status: Resolved + Set Attr: "Resolution: Approved Business Exception" + Add Note: "Exception approved by {analyst}" | Approved exceptions |

---

## 8. Automated Response Rules

Automated Response rules execute **without human intervention** when an incident is created and conditions are met.

### Condition-Action Model

```
IF [Conditions are met]
THEN [Execute Actions]
```

If no conditions are specified, the actions execute on every incident matched by associated policies.

### Available Conditions

| Condition | Description | Example |
|-----------|-------------|---------|
| Severity | Trigger based on severity level | "Only if severity is High or Critical" |
| Policy | Trigger for specific policies | "Only for PCI DSS policy" |
| Detection Server | Trigger for specific server types | "Only for Endpoint Prevent incidents" |
| Protocol | Trigger based on protocol | "Only for SMTP incidents" |
| Sender Pattern | Trigger based on sender matching | "Only for sender in @external.com" |
| Recipient Pattern | Trigger based on recipient | "Only if recipient is external" |

### Available Actions (by Detection Server)

**All Detection Servers:**
- Log to Syslog Server (UDP/TCP)
- Set Status (auto-set incident status)
- Set Attribute (auto-populate custom attributes)
- Send Email Notification
- Limit Incident Data Retention

**Network Prevent for Email:**
- Block Message
- Modify Message (add/remove headers, redirect)
- Quarantine Message (via Symantec Messaging Gateway)
- Add X-Header
- Encrypt (via email gateway integration)

**Network Prevent for Web:**
- Block (return block page to user via ICAP)
- Allow (let traffic pass)
- Content Removal (strip sensitive content from HTML)

**Endpoint Prevent:**
- Block (prevent data transfer + display popup)
- Notify (display popup without blocking)
- Encrypt (encrypt file using endpoint encryption provider)
- User Cancel (prompt user to cancel or justify)
- FlexResponse (custom plugin actions)

**Network Discover / Protect:**
- Quarantine File
- Copy File
- Encrypt in Place
- Apply DRM
- Apply MIP Label

**Cloud Applications:**
- Quarantine
- Block Sharing
- Add Two-Factor Authentication
- Notify
- Apply Classification Label

### Creating an Automated Response Rule

**Navigation:** Manage > Policies > Response Rules > Add Response Rule > Automated Response

1. Click **Add Response Rule**
2. Select **Automated Response**
3. Enter rule name: "Block PCI Email to External"
4. Click **Next** to configure
5. Add **Condition**: Severity = High
6. Add **Condition**: Protocol = SMTP
7. Add **Action**: Block Message
   - Block reason: "This message has been blocked because it contains payment card data. Contact the DLP team for assistance."
8. Add **Action**: Send Email Notification
   - To: sender (notify the user their email was blocked)
   - Subject: "Your email was blocked by DLP"
   - Body: "Your email to {recipients} was blocked because it contained payment card information."
9. Add **Action**: Log to Syslog
   - Host: siem.corp.local
   - Port: 514
   - Protocol: TCP
   - Message: CEF format (see compliance-reporting for CEF template)
10. Click **Save**
11. Associate with the PCI DSS policy

### Response Rule Priority

When multiple response rules trigger for the same incident:
- All non-conflicting actions execute (e.g., both "Log to Syslog" and "Send Notification")
- For conflicting actions (e.g., Block vs. Allow), the **highest-priority** action wins
- Priority is determined by rule order (configurable by dragging rules in the list)
- "Block" always takes priority over "Allow" by default

---

## 9. End User Remediation

### Overview [S1, S2, Video #4, Video #25]

End User Remediation distributes incident resolution to the people closest to the data -- data owners, department managers, or the users who caused the violation -- rather than funneling everything through the security team.

### Built-in End User Remediation (DLP 15.8+)

1. **Configure** which incidents are eligible for end user remediation
2. **Define** what information the remediator can see (matched content, policy name, etc.)
3. **Define** available remediation actions (resolve, justify, escalate)
4. **System routes** incidents to the appropriate end user
5. End user receives **email notification** with a link to a remediation portal
6. End user reviews the incident and takes action
7. Action syncs back to the Enforce Console incident record

### Configuration Steps

1. Navigate to **System > Settings > End User Remediation**
2. Enable End User Remediation
3. Configure:
   - **Incident visibility**: What the end user can see (policy name, matched content snippets, file details)
   - **Available actions**: Resolve, Justify, Delete File, Request Exception, Escalate
   - **Timeout**: How long the end user has to respond (e.g., 7 days)
   - **Escalation**: What happens if the end user does not respond within timeout
   - **Out-of-Office handling**: Route to alternate contact if primary is unavailable

### Remediator Selection

How the system identifies the appropriate end user:
- **Sender/Source User**: The person who triggered the incident (most common for endpoint/email)
- **LDAP Manager**: The manager of the person who triggered the incident
- **File Owner**: The owner of the file (for discovery incidents, via Data Insight or LDAP)
- **Custom Attribute**: Route based on a custom attribute value (e.g., "Data Steward")

### ServiceNow Integration for End User Remediation [Video #25, Video #28]

For organizations using ServiceNow:

1. **Install** the Symantec DLP integration from the ServiceNow Store
2. **Configure** bidirectional sync between DLP Enforce and ServiceNow
3. DLP incidents **automatically create** ServiceNow tickets
4. ServiceNow workflows handle:
   - Assignment to appropriate remediation team
   - SLA tracking and escalation
   - User notification and response collection
   - Status sync back to DLP (resolving in ServiceNow resolves in DLP)
5. **Bidirectional sync** is the key differentiator -- changes in either system reflect in the other

---

## 10. SOAR Integration

### Cortex XSOAR (Palo Alto Networks)

Official integration pack (v2) with full command set:

| Command | Description |
|---------|-------------|
| `symantec-dlp-list-incidents` | Query incidents with filters |
| `symantec-dlp-get-incident-details` | Get full incident details |
| `symantec-dlp-update-incident` | Update status, severity, notes, custom attributes |
| `symantec-dlp-get-incident-history` | Get incident audit trail |
| `symantec-dlp-get-incident-original-message` | Retrieve original evidence |
| `symantec-dlp-list-incident-status` | Get available status values |
| `symantec-dlp-list-custom-attributes` | Get custom attribute definitions |
| `symantec-dlp-list-sender-recipient-patterns` | Get reusable patterns |
| `symantec-dlp-create-sender-recipient-pattern` | Create a new pattern |
| `symantec-dlp-update-sender-recipient-pattern` | Update an existing pattern |

**Typical XSOAR Playbook for DLP:**
1. Polling: Fetch new DLP incidents every 5 minutes
2. Enrichment: Lookup user in Active Directory, check risk score
3. Triage: Auto-classify based on severity and policy
4. Notification: Email data owner and manager
5. Wait for response: Collect justification or remediation confirmation
6. Resolution: Update DLP incident status via API
7. Reporting: Log to investigation timeline

### FortiSOAR (Fortinet)

Connector v2.2.0:

| Action | Description |
|--------|-------------|
| Get Incidents | Fetch incidents from DLP with filters |
| Get Incident Details | Retrieve specific incident details |
| Get Incident Statuses | List available status values |
| Update Incident | Change status, add notes, update attributes |
| Get DLP Components | Retrieve matched content details |

### Swimlane Turbine

| Action | Description |
|--------|-------------|
| Get Incidents | Query DLP incidents |
| Get Incident Details | Full incident retrieval |
| Get Original Message | Download evidence |
| Update Incident | Status, severity, notes |
| Get Policy Matches | Matched policy details |

### ServiceNow DLP Incident Response

Dedicated integration on the ServiceNow Store:
- Automatic incident import from DLP to ServiceNow
- Bidirectional status synchronization
- SLA tracking within ServiceNow
- Remediation workflow automation
- Works with Endpoint, Network, Email, and Cloud incidents

### Generic SOAR Integration via REST API

Any SOAR platform can integrate using the DLP REST API directly:

```bash
# Poll for new incidents (every 5 minutes from cron/scheduler)
curl -s -u 'api-user:password' \
  -X POST \
  -H 'Content-Type: application/json' \
  -d '{
    "savedReportId": 0,
    "incidentCreationDateGreaterThan": "2026-05-21T00:00:00Z",
    "filters": {
      "filterType": "AND",
      "filters": [
        {
          "filterType": "booleanFilter",
          "filterName": "incidentStatusName",
          "filterValue": "New"
        }
      ]
    }
  }' \
  'https://enforce.corp.local/ProtectManager/webservices/v2/incidents'

# Update incident after SOAR playbook completes
curl -s -u 'api-user:password' \
  -X PATCH \
  -H 'Content-Type: application/json' \
  -d '{
    "incidents": [
      {
        "incidentId": 12345,
        "incidentStatusName": "Resolved",
        "incidentNotes": "Resolved by SOAR playbook: User confirmed authorized use."
      }
    ]
  }' \
  'https://enforce.corp.local/ProtectManager/webservices/v2/incidents'
```

---

## 11. Incident REST API

### Complete Endpoint Reference

**Base URL:** `https://<enforce>/ProtectManager/webservices/v2/`

| # | Method | Endpoint | Description | DLP Version |
|---|--------|----------|-------------|-------------|
| 1 | POST | `/incidents` | Query incidents by report ID with filters | 15.7+ |
| 2 | GET | `/incidents/{incidentId}` | Get full incident details | 15.7+ |
| 3 | PATCH | `/incidents` | Update one or more incidents (status, severity, notes, custom attributes) | 15.7+ |
| 4 | GET | `/incidents/{incidentId}/history` | Get incident audit/history trail | 15.8+ |
| 5 | GET | `/incidents/{incidentId}/originalMessage` | Retrieve original captured message/file | 15.8+ |
| 6 | GET | `/incidents/{incidentId}/components` | Get matched content and policy details | 15.7+ |
| 7 | GET | `/incidents/incidentStatuses` | List all incident status values | 15.7+ |
| 8 | GET | `/incidents/incidentEditable` | List editable incident attributes | 15.7+ |
| 9 | GET | `/incidents/preventActionStatuses` | Get prevent action status values | 15.7+ |
| 10 | GET | `/incidents/protectActionStatuses` | Get protect action status values | 15.7+ |
| 11 | GET | `/incidents/listCustomAttributes` | List custom attribute definitions | 15.7+ |
| 12 | POST | `/incidents/export` | Export incidents as JSON | 16.0+ |
| 13 | GET | `/reports/{reportId}/filters` | Retrieve saved report filter criteria | 16.0+ |

### Authentication

```
Method: HTTP Basic Authentication over TLS
Header: Authorization: Basic <base64(username:password)>
Port: 443 (HTTPS)
Role required: "Incident Reporting API Web Service" role
```

Alternative authentication (DLP 16.0 RU2+):
- Kerberos
- Certificate-based
- JWT with configurable IdP (DLP 26.1+)

### Query Incidents (POST /incidents)

```bash
curl -s -u 'api-user:password' \
  -X POST \
  -H 'Content-Type: application/json' \
  -d '{
    "savedReportId": 0,
    "incidentCreationDateGreaterThan": "2026-05-01T00:00:00Z",
    "incidentCreationDateLessThan": "2026-05-21T23:59:59Z",
    "filters": {
      "filterType": "AND",
      "filters": [
        {
          "filterType": "booleanFilter",
          "filterName": "severity",
          "filterValue": "HIGH"
        },
        {
          "filterType": "booleanFilter",
          "filterName": "incidentStatusName",
          "filterValue": "New"
        }
      ]
    },
    "pageSize": 50,
    "pageNumber": 1
  }' \
  'https://enforce.corp.local/ProtectManager/webservices/v2/incidents'
```

### Get Incident Details (GET /incidents/{id})

```bash
curl -s -u 'api-user:password' \
  'https://enforce.corp.local/ProtectManager/webservices/v2/incidents/12345'
```

Response includes: incident metadata, policy details, sender/recipient, detection server, severity, status, custom attributes, match count.

### Update Incidents (PATCH /incidents)

```bash
# Update single incident
curl -s -u 'api-user:password' \
  -X PATCH \
  -H 'Content-Type: application/json' \
  -d '{
    "incidents": [
      {
        "incidentId": 12345,
        "incidentStatusName": "In Process",
        "severity": "HIGH",
        "incidentNotes": "Investigation started by SOC analyst J. Smith",
        "customAttributes": [
          {
            "name": "Remediation Owner",
            "value": "Jane Smith"
          },
          {
            "name": "Risk Assessment",
            "value": "High Risk"
          }
        ]
      }
    ]
  }' \
  'https://enforce.corp.local/ProtectManager/webservices/v2/incidents'

# Bulk update multiple incidents
curl -s -u 'api-user:password' \
  -X PATCH \
  -H 'Content-Type: application/json' \
  -d '{
    "incidents": [
      {"incidentId": 12345, "incidentStatusName": "Resolved"},
      {"incidentId": 12346, "incidentStatusName": "Resolved"},
      {"incidentId": 12347, "incidentStatusName": "False Positive"}
    ]
  }' \
  'https://enforce.corp.local/ProtectManager/webservices/v2/incidents'
```

### Get Incident History (GET /incidents/{id}/history)

```bash
curl -s -u 'api-user:password' \
  'https://enforce.corp.local/ProtectManager/webservices/v2/incidents/12345/history'
```

Returns chronological audit trail: who changed what, when.

### Get Original Message (GET /incidents/{id}/originalMessage)

```bash
curl -s -u 'api-user:password' \
  -o original_message.eml \
  'https://enforce.corp.local/ProtectManager/webservices/v2/incidents/12345/originalMessage'
```

Downloads the original email/file as captured by DLP.

### Get Incident Components (GET /incidents/{id}/components)

```bash
curl -s -u 'api-user:password' \
  'https://enforce.corp.local/ProtectManager/webservices/v2/incidents/12345/components'
```

Returns matched content details: which rules matched, what content was detected, confidence scores.

### List Available Statuses

```bash
curl -s -u 'api-user:password' \
  'https://enforce.corp.local/ProtectManager/webservices/v2/incidents/incidentStatuses'
```

### List Custom Attributes

```bash
curl -s -u 'api-user:password' \
  'https://enforce.corp.local/ProtectManager/webservices/v2/incidents/listCustomAttributes'
```

---

## 12. Incident Workflows (DLP 26.1)

### New in DLP 26.1

DLP 26.1 introduces **Incident Workflows** -- a framework for scheduling and automating tasks throughout the incident lifecycle.

### Capabilities

- **Automated task scheduling**: Define tasks that execute at specific points in the incident lifecycle
- **Conditional branching**: Route incidents through different paths based on attributes (severity, policy, custom attributes)
- **Time-based escalation**: Automatically escalate incidents that remain unresolved past SLA thresholds
- **Assignment automation**: Auto-assign incidents to analysts based on policy type, severity, or custom rules
- **Notification chains**: Sequence of notifications at different lifecycle stages

### Configuration

**Navigation:** System > Incident Workflows (DLP 26.1+)

This feature replaces or supplements the manual status transitions described in Section 6, providing a more formalized workflow engine built into the DLP platform.

---

## 13. End-to-End Lifecycle Summary

### Phase 1: Detection (Automatic)

1. Content passes through a detection server
2. Detection engine evaluates content against all policies in the assigned policy group
3. Policy violation found -- incident created with severity, status "New"
4. Automated Response rules execute immediately (block, notify, log)
5. Incident appears in the Enforce Console incident queue

### Phase 2: Triage (Analyst)

6. Analyst opens the incident queue (Incidents > [channel])
7. Filters by severity (High first), status (New), date (most recent)
8. Opens each incident to review: matched content, sender, recipient, context
9. Quick decisions:
   - Obviously false positive -> Mark "False Positive"
   - Obviously legitimate violation -> Continue to investigation
   - Unclear -> Assign to senior analyst

### Phase 3: Investigation (Analyst)

10. Examine matched content in detail (what data was detected?)
11. Check user history (repeat offender? first-time?)
12. Check user risk score (if ICA integration enabled)
13. Analyze data flow (where was data going? authorized recipient?)
14. Review original message/file if needed
15. Consult with data owner or user's manager if unclear

### Phase 4: Remediation (Analyst or System)

16. Execute Smart Response (e.g., "Escalate to Legal", "Assign Training")
17. Or update incident manually: set status, add notes, assign owner
18. Or send to End User Remediation (data owner resolves directly)
19. SOAR playbook handles complex remediation flows

### Phase 5: Resolution (Analyst)

20. Remediation confirmed complete
21. Set status to "Resolved"
22. Add final notes documenting resolution
23. Incident enters the compliance reporting pipeline

### Phase 6: Reporting and Compliance (Ongoing)

24. Resolved incidents feed compliance reports
25. Trend analysis identifies policy tuning opportunities
26. High-volume false positive patterns trigger policy refinement
27. Repeat offender patterns trigger targeted training
28. Audit trail preserved for regulatory evidence

---

*End of incident management workflow. For quickstart guide, see quickstart.md. For API details and SOAR integration, see advanced.md.*
