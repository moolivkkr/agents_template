# Authoring Rules — Advanced Reference
## Broadcom Symantec DLP (Enforce Server, version 16.x/25.x/26.x)

> **Purpose:** Complete field reference by screen, ASCII UI diagrams, extensive examples, and an end-to-end scenario tying all layers together.
> **Evidence sources:** doc-corpus.md [S1-S28], video-intelligence.md [V1-V45], api-intelligence.md

---

## Table of Contents

1. [Screen-by-Screen Field Reference](#1-screen-by-screen-field-reference)
2. [Detection Technology Examples (5-7 per type)](#2-detection-technology-examples)
3. [Detection Rule Examples (5-7)](#3-detection-rule-examples)
4. [Exception Examples (5-7)](#4-exception-examples)
5. [Response Rule Examples (5-7)](#5-response-rule-examples)
6. [Policy Examples (5-7)](#6-policy-examples)
7. [Policy Group & Deployment Examples (5)](#7-policy-group--deployment-examples)
8. [End-to-End Example: Protecting PCI Data Across Email, Web, and Endpoint](#8-end-to-end-example)
9. [Policy Template Catalog](#9-policy-template-catalog)
10. [Advanced Compound Rule Patterns](#10-advanced-compound-rule-patterns)
11. [FlexResponse Extensibility](#11-flexresponse-extensibility)
12. [API-Based Policy Management](#12-api-based-policy-management)

---

## 1. Screen-by-Screen Field Reference

### Screen 1: Policy List (Main Dashboard)

**Navigation:** Manage > Policies > Policy List

```
+=========================================================================+
|  Manage > Policies > Policy List                                        |
+=========================================================================+
|  [New Policy v]  [Import]  [Export]                      [Search: ____ ]|
|                                                                         |
|  Filter by: [All Groups v] [All Statuses v] [All Severities v]         |
|                                                                         |
|  +-------------------------------------------------------------------+ |
|  | # | Policy Name          | Group    | Status      | Rules | Resp. | |
|  |---|----------------------|----------|-------------|-------|-------| |
|  | 1 | PCI-DSS-CC-Protect   | Default  | Enabled     | 2     | 3     | |
|  | 2 | HIPAA-PHI-Protect    | Comply   | Test/NoNotf | 3     | 1     | |
|  | 3 | IP-Source-Code       | Eng      | Test/Notif  | 4     | 2     | |
|  | 4 | Shadow-IT-Monitor    | Default  | Enabled     | 1     | 1     | |
|  | 5 | Executive-Financial  | Exec     | Disabled    | 2     | 0     | |
|  +-------------------------------------------------------------------+ |
|                                                                         |
|  Showing 1-5 of 23 policies                  [< Prev] [1] [2] [Next >] |
+=========================================================================+
```

| Field/Column | Type | Description | Evidence |
|-------------|------|-------------|----------|
| Policy Name | Link | Click to edit policy | A [S1] |
| Group | Text | Policy group assignment | A [S1] |
| Status | Badge | Enabled, Test/NoNotify, Test/Notify, Disabled | A [S1, S4] |
| Rules | Count | Number of detection rules | A [S1] |
| Resp. | Count | Number of response rules attached | A [S1] |
| New Policy | Button dropdown | Template List or Create New Policy | A [S1, S4] |
| Import/Export | Buttons | XML policy import/export (also via API 25.1+) | A [S1, S4] |
| Filter by Group | Dropdown | Filter by policy group | A [S1] |
| Filter by Status | Dropdown | Filter by policy status | A [S1] |

---

### Screen 2: Policy Editor — General Tab

**Navigation:** Manage > Policies > Policy List > [click policy] > General

```
+=========================================================================+
|  Policy: PCI-DSS-Credit-Card-Protection                                 |
+=========================================================================+
|  [General] [Detection] [Groups] [Response]                    [Save]    |
+-------------------------------------------------------------------------+
|                                                                         |
|  Policy Name:  [PCI-DSS-Credit-Card-Protection          ]               |
|                                                                         |
|  Description:  [Detects and protects credit card data per PCI DSS      ]|
|                [requirements. Covers email, web, and endpoint channels. ]|
|                                                                         |
|  Policy Group: [Default Policy Group     ] [v]                          |
|                                                                         |
|  Policy Mode:                                                           |
|    ( ) Test Without Notifications                                       |
|    ( ) Test With Notifications                                          |
|    (*) Enabled                                                          |
|    ( ) Disabled                                                         |
|                                                                         |
|  Owner: [admin                           ]                              |
|                                                                         |
|  Tags: [pci] [compliance] [credit-card]   [+ Add Tag]                  |
|                                                                         |
+=========================================================================+
```

| Field | Type | Required | Default | Options | Evidence |
|-------|------|----------|---------|---------|----------|
| Policy Name | Text (256 chars max) | Yes | Template name or blank | Free text | A [S1, S4] |
| Description | Textarea (2000 chars max) | No | Template description or blank | Free text | A [S1, S4] |
| Policy Group | Dropdown | Yes | Default Policy Group | All configured policy groups | A [S1, S4] |
| Policy Mode | Radio buttons | Yes | Test Without Notifications | Test/NoNotify, Test/Notify, Enabled, Disabled | A [S1, S4] |
| Owner | Text | No | Current user | Any DLP user | B [S4] |
| Tags | Tag input | No | None | Free-form tags | B [S4] |

---

### Screen 3: Policy Editor — Detection Tab

**Navigation:** Manage > Policies > Policy List > [click policy] > Detection

```
+=========================================================================+
|  Policy: PCI-DSS-Credit-Card-Protection                                 |
+=========================================================================+
|  [General] [Detection] [Groups] [Response]                    [Save]    |
+-------------------------------------------------------------------------+
|                                                                         |
|  Detection Rules                                  [+ Add Rule]          |
|  +-----------------------------------------------------------------+   |
|  | Rule 1: Credit Card Detection (High)                   [Edit]   |   |
|  |   Condition: Content Matches Data Identifier            [Delete] |   |
|  |     Data Identifier: Credit Card Number                          |   |
|  |     Minimum Matches: 1 (Unique)                                  |   |
|  |     Look In: Body, Attachments                                   |   |
|  +-----------------------------------------------------------------+   |
|  | Rule 2: Bulk CC in Spreadsheet (High)                  [Edit]   |   |
|  |   Conditions (Compound):                                [Delete] |   |
|  |     1. Content Matches Data Identifier: CC Number >= 10          |   |
|  |     2. File Type: Spreadsheet (XLS, XLSX, CSV)                   |   |
|  +-----------------------------------------------------------------+   |
|                                                                         |
|  Exceptions                                       [+ Add Exception]    |
|  +-----------------------------------------------------------------+   |
|  | Exception 1: Internal Payment Processing       [Edit] [Delete]  |   |
|  |   Sender matches: payments@company.com                           |   |
|  +-----------------------------------------------------------------+   |
|                                                                         |
+=========================================================================+
```

| Element | Type | Description | Evidence |
|---------|------|-------------|----------|
| Detection Rules list | Table | All rules attached to this policy | A [S1, S4] |
| Add Rule button | Button | Opens rule condition builder | A [S1, S4] |
| Rule display | Expandable row | Shows condition summary, severity | A [S1, S4] |
| Edit/Delete | Buttons | Modify or remove rule | A [S1, S4] |
| Exceptions list | Table | All exceptions on this policy | A [S1, S4] |
| Add Exception button | Button | Opens exception condition builder | A [S1, S4] |

---

### Screen 4: Add Detection Rule — Condition Builder

**Navigation:** Policy > Detection tab > Add Rule

```
+=========================================================================+
|  Add Detection Rule                                                     |
+=========================================================================+
|                                                                         |
|  Rule Name: [                                   ]                       |
|                                                                         |
|  Rule Type:                                                             |
|    (*) Simple Rule (single condition)                                   |
|    ( ) Compound Rule (multiple conditions -- all must match)            |
|                                                                         |
|  ---------------------------------------------------------------        |
|  Condition Type: [Content Matches Data Identifier      ] [v]           |
|  ---------------------------------------------------------------        |
|                                                                         |
|  Available condition types:                                             |
|    - Content Matches Keyword                                            |
|    - Content Matches Regular Expression                                 |
|    - Content Matches Data Identifier                                    |
|    - Content Matches Exact Data                                         |
|    - Content Matches Indexed Documents                                  |
|    - Content Matches VML Profile                                        |
|    - Content Matches MIP Tag Rule                                       |
|    - Sender/Recipient Matches Pattern                                   |
|    - Sender/User Based on Directory Server Group                        |
|    - Endpoint: Device/Location/Action                                   |
|    - File Properties (type, size, name)                                 |
|    - Protocol (SMTP, HTTP, FTP, IM)                                     |
|    - User Risk (ICA integration)                                        |
|                                                                         |
|  ---------------------------------------------------------------        |
|  Configure Selected Condition:                                          |
|                                                                         |
|  Data Identifier: [Credit Card Number              ] [v]               |
|                                                                         |
|  Minimum Matches: [  1  ]                                               |
|                                                                         |
|  Count: (*) Unique matches   ( ) All matches                            |
|                                                                         |
|  Look In:                                                               |
|    [x] Message Body    [x] Message Subject                              |
|    [x] Attachments     [ ] Message Envelope                             |
|    [ ] Message Headers                                                  |
|  ---------------------------------------------------------------        |
|                                                                         |
|  Severity: [High (1)] [v]                                               |
|                                                                         |
|  [Save Rule]  [Cancel]                                                  |
+=========================================================================+
```

| Field | Type | Required | Default | Options | Evidence |
|-------|------|----------|---------|---------|----------|
| Rule Name | Text | Yes | -- | Free text | A [S1, S4] |
| Rule Type | Radio | Yes | Simple | Simple, Compound | A [S1, S4] |
| Condition Type | Dropdown | Yes | -- | 13+ condition types (see list above) | A [S1, S4] |
| Data Identifier | Dropdown (if DI selected) | Yes | -- | 30+ built-in + custom identifiers | A [S1, S4] |
| Minimum Matches | Integer | Yes | 1 | 1-999 | A [S1, S4] |
| Match Counting | Radio | Yes | Unique | Unique, All | A [S4] |
| Look In | Checkboxes | No | Body + Attachments | Body, Subject, Attachments, Envelope, Headers | A [S1, S4] |
| Severity | Dropdown | Yes | Medium | High (1), Medium (2), Low (3), Informational (4) | A [S1, S4] |

---

### Screen 5: EDM Profile Editor

**Navigation:** Manage > Data Profiles > Exact Data Profiles > [profile]

```
+=========================================================================+
|  Exact Data Profile: Employee-PII-Protection                            |
+=========================================================================+
|  [General] [Data Source] [Column Mapping] [Indexing] [History]           |
+-------------------------------------------------------------------------+
|                                                                         |
|  Profile Name: [Employee-PII-Protection           ]                     |
|                                                                         |
|  DATA SOURCE                                                            |
|  ---------------------------------------------------------------        |
|  Source Type: (*) Delimited File  ( ) Database  ( ) LDAP                |
|                                                                         |
|  Current File: employee_records_2024.csv  [Replace...]                  |
|  Rows: 45,231    Columns: 8    Last Updated: 2024-01-15                 |
|                                                                         |
|  Delimiter: [Comma (,)   ] [v]                                          |
|  Text Qualifier: [Double Quote (") ] [v]                                |
|  First Row Contains Headers: [x]                                        |
|  ---------------------------------------------------------------        |
|                                                                         |
|  COLUMN MAPPING                                                         |
|  ---------------------------------------------------------------        |
|  | # | Column Header | Field Type          | Key? | Sample Data       ||
|  |---|---------------|---------------------|------|-------------------||
|  | 1 | First Name    | [First Name    ] [v]| [ ]  | John, Jane, ...   ||
|  | 2 | Last Name     | [Last Name     ] [v]| [ ]  | Smith, Doe, ...   ||
|  | 3 | SSN           | [US SSN        ] [v]| [x]  | ***-**-1234, ...  ||
|  | 4 | Email         | [Email Address ] [v]| [ ]  | jsmith@co.com     ||
|  | 5 | Phone         | [Phone Number  ] [v]| [ ]  | (555) 123-4567    ||
|  | 6 | DOB           | [Date of Birth ] [v]| [ ]  | 1985-03-15        ||
|  | 7 | Employee ID   | [Custom        ] [v]| [x]  | EMP001234         ||
|  | 8 | Department    | [Custom        ] [v]| [ ]  | Engineering       ||
|  ---------------------------------------------------------------        |
|                                                                         |
|  INDEXING                                                               |
|  ---------------------------------------------------------------        |
|  Index Status: [Indexed] (Last: 2024-01-15 02:00 AM)                   |
|  Records Indexed: 45,112 / 45,231 (99.7%)                              |
|  Errors: 119 (0.26%) -- below 5% threshold                             |
|                                                                         |
|  Schedule: (*) Daily at [02:00 AM] [v]                                  |
|            ( ) Weekly on [Sunday ] [v] at [02:00 AM] [v]                |
|            ( ) Manual only                                              |
|                                                                         |
|  Error Threshold: [5  ]%                                                |
|  ---------------------------------------------------------------        |
|                                                                         |
|  [Index Now]  [Save]  [Cancel]                                          |
+=========================================================================+
```

| Field | Type | Required | Default | Options | Evidence |
|-------|------|----------|---------|---------|----------|
| Profile Name | Text | Yes | -- | Free text | A [S1, S4] |
| Source Type | Radio | Yes | Delimited File | Delimited File, Database, LDAP | A [S1, S4] |
| File | File upload | Yes (if delimited) | -- | CSV, TSV, custom-delimited | A [S1, S4] |
| Delimiter | Dropdown | Yes | Comma | Comma, Tab, Pipe, Semicolon, Custom | A [S4] |
| Text Qualifier | Dropdown | No | Double Quote | Double Quote, Single Quote, None | A [S4] |
| First Row Headers | Checkbox | No | Checked | -- | A [S4] |
| Column Field Type | Dropdown per column | Yes | Auto-detected | First Name, Last Name, SSN, Email, Phone, Date, Custom, etc. | A [S1, S4] |
| Key Field | Checkbox per column | Yes (at least 1) | -- | Mark unique identifier columns | A [S1, S4] |
| Schedule | Radio + time | No | Manual | Daily, Weekly, Manual | A [S1, S4] |
| Error Threshold | Percentage | No | 5% | 0-100% | A [S1, V19] |

---

### Screen 6: VML Profile Editor

**Navigation:** Manage > Data Profiles > Vector Machine Learning Profiles > [profile]

```
+=========================================================================+
|  Vector Machine Learning Profile: Financial-Reports-VML                 |
+=========================================================================+
|  [General] [Training] [Accuracy] [History]                              |
+-------------------------------------------------------------------------+
|                                                                         |
|  Profile Name: [Financial-Reports-VML              ]                    |
|                                                                         |
|  TRAINING SETS                                                          |
|  ---------------------------------------------------------------        |
|  Positive Training (content TO protect):                                |
|    Source: [\\finance\confidential-reports\    ] [Browse...]            |
|    Documents loaded: 287                                                 |
|    [Replace Training Set]                                               |
|                                                                         |
|  Negative Training (content NOT to protect):                            |
|    Source: [\\marketing\public-materials\      ] [Browse...]            |
|    Documents loaded: 312                                                 |
|    [Replace Training Set]                                               |
|  ---------------------------------------------------------------        |
|                                                                         |
|  TRAINING RESULTS                                                       |
|  ---------------------------------------------------------------        |
|  Status: [Trained Successfully]                                         |
|  Accuracy Score: 94.2%                                                  |
|  True Positive Rate: 96.1%                                              |
|  False Positive Rate: 3.8%                                              |
|                                                                         |
|  [Re-Train]  [Accept Profile]  [Reject and Re-configure]               |
|  ---------------------------------------------------------------        |
|                                                                         |
+=========================================================================+
```

| Field | Type | Required | Default | Options | Evidence |
|-------|------|----------|---------|---------|----------|
| Profile Name | Text | Yes | -- | Free text | A [S1, S4] |
| Positive Training Set | File/Directory | Yes | -- | ZIP archive or directory path | A [S1, S4, S7] |
| Negative Training Set | File/Directory | Yes | -- | ZIP archive or directory path | A [S1, S4, S7] |
| Accuracy Score | Display only | -- | -- | System-calculated percentage | A [S7] |
| Accept/Reject | Buttons | -- | -- | Accept deploys the profile; Reject returns to configuration | A [S7, V20] |

---

### Screen 7: Response Rule Editor

**Navigation:** Manage > Policies > Response Rules > [rule]

```
+=========================================================================+
|  Response Rule: Block-CC-Email-External                                 |
+=========================================================================+
|  [General] [Conditions] [Actions]                           [Save]      |
+-------------------------------------------------------------------------+
|                                                                         |
|  Rule Name: [Block-CC-Email-External               ]                    |
|  Type: Automated Response Rule                                          |
|                                                                         |
|  CONDITIONS                                                             |
|  ---------------------------------------------------------------        |
|  | Condition 1: Severity                                                |
|  |   Severity equals: [High (1)] [v]                                    |
|  |                                                                      |
|  | Condition 2: Detection Server Type                                   |
|  |   Server type: [Network Prevent for Email] [v]                       |
|  |                                                                      |
|  | [+ Add Condition]                                                    |
|  ---------------------------------------------------------------        |
|                                                                         |
|  ACTIONS                                                                |
|  ---------------------------------------------------------------        |
|  | Action 1: Block Message                                              |
|  |   Block Type: (*) Block entire message                               |
|  |              ( ) Remove violating content only                        |
|  |   Bounce Message: [x] Send bounce notification to sender             |
|  |   Bounce Text: [Your email was blocked due to DLP policy. Contact   ]|
|  |                [security@company.com for assistance.                 ]|
|  |                                                                      |
|  | Action 2: Send Email Notification                                    |
|  |   To:      [dlp-admins@company.com                    ]              |
|  |   CC:      [ciso@company.com                          ]              |
|  |   Subject: [BLOCKED: CC data from $SENDER$ to $RECIPIENTS$]          |
|  |   Body:    [Incident $INCIDENT_ID$: Policy $POLICY$ blocked email   ]|
|  |            [from $SENDER$. Severity: $SEVERITY$. Matches: $MATCHES$.]|
|  |                                                                      |
|  | Action 3: Log to Syslog Server                                       |
|  |   Host: [siem.company.com                  ]                         |
|  |   Port: [514   ]                                                     |
|  |   Protocol: (*) TCP  ( ) UDP                                         |
|  |   Message: [CEF:0|Broadcom|DLP|16.0|$RULES$|$POLICY$|5|...]          |
|  |                                                                      |
|  | [+ Add Action]                                                       |
|  ---------------------------------------------------------------        |
|                                                                         |
+=========================================================================+
```

| Field | Type | Required | Default | Options | Evidence |
|-------|------|----------|---------|---------|----------|
| Rule Name | Text | Yes | -- | Free text | A [S1, S4] |
| Rule Type | Display | -- | Selected at creation | Automated or Smart | A [S1, S4] |
| Conditions | Condition list | No | None (fires on every match) | Severity, Protocol, Server Type, Policy | A [S1, S4] |
| Actions | Action list | Yes (at least 1) | -- | See action catalog per server type | A [S1, S4] |
| Block Type | Radio | Yes (if Block action) | Block entire | Block entire message, Remove violating content | A [S1, S4] |
| Bounce Message | Checkbox + text | No | Unchecked | Custom bounce text | A [S4] |
| Notification To/CC | Email | Yes (if Notify action) | -- | Email addresses, supports variables | A [S1, S4] |
| Notification Subject/Body | Text | Yes (if Notify action) | -- | Free text with variable substitution | A [S1, S4] |
| Syslog Host/Port | Text/Integer | Yes (if Syslog action) | -- | Hostname/IP + port number | A [S1, S4] |
| Syslog Protocol | Radio | Yes (if Syslog action) | TCP | TCP, UDP | A [S1, S4] |
| Syslog Message | Textarea | Yes (if Syslog action) | -- | CEF template with variables | A [S1, S4] |

**Available notification variables:** `$INCIDENT_ID$`, `$POLICY$`, `$RULES$`, `$SEVERITY$`, `$BLOCKED$`, `$APPLICATION_USER$`, `$ENDPOINT_MACHINE$`, `$ENDPOINT_USERNAME$`, `$MACHINE_IP$`, `$FILE_NAME$`, `$RECIPIENTS$`, `$SENDER$`, `$SUBJECT$`, `$MATCH_COUNT$`, `$PROTOCOL$`, `$DATA_OWNER$` [S1, S4, API-intelligence]

---

### Screen 8: Policy Group Management

**Navigation:** System > Servers and Detectors > Policy Groups

```
+=========================================================================+
|  System > Servers and Detectors > Policy Groups                         |
+=========================================================================+
|                                                            [+ Add]      |
|                                                                         |
|  +-------------------------------------------------------------------+ |
|  | Group Name       | Description              | Servers    | Policies| |
|  |------------------|--------------------------|------------|---------|  |
|  | Default          | All detection servers     | 5 servers  | 12      | |
|  | Compliance       | Regulatory compliance     | 3 servers  | 8       | |
|  | Engineering      | Source code protection    | 2 servers  | 4       | |
|  | Executive        | Executive monitoring only | 1 server   | 2       | |
|  +-------------------------------------------------------------------+ |
|                                                                         |
|  Click group to edit...                                                 |
|                                                                         |
|  +-------------------------------------------------------------------+ |
|  | Edit Policy Group: Engineering                                     | |
|  |                                                                    | |
|  | Name: [Engineering                       ]                         | |
|  | Description: [Policies for engineering detection servers    ]      | |
|  |                                                                    | |
|  | Target Detection Servers:                                          | |
|  |   [x] endpoint-prevent-01.eng.company.com                         | |
|  |   [x] network-monitor-02.eng.company.com                          | |
|  |   [ ] email-prevent-01.company.com                                | |
|  |   [ ] web-prevent-01.company.com                                  | |
|  |   [ ] discover-01.company.com                                     | |
|  |                                                                    | |
|  |   [Save]  [Cancel]                                                | |
|  +-------------------------------------------------------------------+ |
+=========================================================================+
```

| Field | Type | Required | Default | Options | Evidence |
|-------|------|----------|---------|---------|----------|
| Group Name | Text | Yes | -- | Free text | A [S1, S4] |
| Description | Text | No | -- | Free text | A [S1, S4] |
| Target Detection Servers | Checkbox list | Yes (at least 1) | -- | All registered detection servers | A [S1, S4] |

**RBAC:** Only users with "Server Administration" privilege can manage policy groups. [S1, S4]

---

## 2. Detection Technology Examples

### 2.1 DCM — Data Identifiers (7 examples)

```yaml
# DI-1: US SSN — narrow breadth (XXX-XX-XXXX only)
detection_method: "data_identifier"
name: "SSN-Narrow"
data_identifier: "US Social Security Number"
breadth: "narrow"
minimum_matches: 1
match_counting: "unique"
severity: "High"
look_in: ["message_body", "attachments"]
# WHY: Narrow breadth = fewest false positives. Only matches dashed format.
# GOTCHA: Misses SSNs without dashes (123456789). Use "wide" if needed.
```

```yaml
# DI-2: US SSN — wide breadth (includes no-dash format)
detection_method: "data_identifier"
name: "SSN-Wide"
data_identifier: "US Social Security Number"
breadth: "wide"
minimum_matches: 1
match_counting: "unique"
severity: "High"
look_in: ["message_body", "attachments"]
# WHY: Wide breadth catches more formats but increases false positives.
# GOTCHA: 9-digit numbers that happen to pass SSN format validation will
#         trigger. Phone numbers, zip+4 codes, etc.
```

```yaml
# DI-3: Credit card — single card (PCI minimal)
detection_method: "data_identifier"
name: "PCI-Single-CC"
data_identifier: "Credit Card Number"
minimum_matches: 1
match_counting: "unique"
severity: "High"
look_in: ["message_body", "attachments", "message_subject"]
# WHY: PCI DSS requires protecting even a single card number.
# GOTCHA: Including "message_subject" catches card numbers accidentally
#         put in email subjects, which is common in customer service.
```

```yaml
# DI-4: Credit card — bulk exfiltration (10+)
detection_method: "data_identifier"
name: "PCI-Bulk-CC"
data_identifier: "Credit Card Number"
minimum_matches: 10
match_counting: "unique"
severity: "High"
look_in: ["message_body", "attachments"]
# WHY: 10+ unique cards = likely data exfiltration, not incidental.
# GOTCHA: A spreadsheet with customer orders may legitimately contain 10+
#         cards. Combine with sender/recipient exceptions for known systems.
```

```yaml
# DI-5: IBAN — European financial data
detection_method: "data_identifier"
name: "EU-IBAN-Detection"
data_identifier: "International Bank Account Number (IBAN)"
minimum_matches: 3
match_counting: "unique"
severity: "Medium"
look_in: ["message_body", "attachments"]
# WHY: 3+ IBANs suggests a customer list, not a single payment reference.
# GOTCHA: IBAN validation includes modulo-97 checksum, so false positive
#         rate is very low. Safe to use moderate thresholds.
```

```yaml
# DI-6: IP address detection (internal network ranges)
detection_method: "data_identifier"
name: "Internal-IP-Leak"
data_identifier: "IP Address"
minimum_matches: 5
match_counting: "unique"
severity: "Low"
look_in: ["message_body", "attachments"]
# WHY: Multiple internal IPs in external communication may leak network
#      topology. Low severity because IP addresses alone are not PII.
# GOTCHA: Very high false positive rate. IP addresses appear in log files,
#         technical documentation, configuration exports. Use only with
#         recipient-based narrowing (external recipients only).
```

```yaml
# DI-7: Custom data identifier — internal part numbers
detection_method: "data_identifier"
name: "Part-Number-Custom-DI"
data_identifier: "Custom: Internal Part Number"
pattern: "PN-[A-Z]{3}-\\d{5}"
validator: "none"
minimum_matches: 5
match_counting: "unique"
severity: "Medium"
look_in: ["message_body", "attachments"]
# WHY: Internal part numbers reveal product roadmap and manufacturing.
# GOTCHA: Custom data identifiers lack built-in validation. Pattern
#         quality is entirely your responsibility. Test thoroughly.
```

### 2.2 DCM — Keywords (5 examples)

```yaml
# KW-1: Classification markers
detection_method: "keyword"
name: "Classification-Markers"
keywords: ["TOP SECRET", "SECRET", "CONFIDENTIAL", "RESTRICTED"]
case_sensitive: false
whole_word_only: true
minimum_matches: 1
severity: "High"
# WHY: Government/defense classification markers require immediate action.
# GOTCHA: "CONFIDENTIAL" in email disclaimers triggers constantly. Add
#         exception for standard disclaimer footer text.
```

```yaml
# KW-2: M&A project code names with proximity
detection_method: "keyword"
name: "MA-Codenames-Proximity"
keywords: ["Project Phoenix"]
proximity_to: ["financial", "valuation", "acquisition", "merger"]
proximity_words: 100
case_sensitive: true
minimum_matches: 1
severity: "High"
# WHY: Code name alone may be coincidental. Near financial terms = real M&A.
# GOTCHA: Proximity window of 100 words is roughly half a page. May be
#         too broad for short emails but appropriate for documents.
```

```yaml
# KW-3: Resume/job search detection (insider threat)
detection_method: "keyword"
name: "Job-Search-Indicators"
keywords: ["curriculum vitae", "resume attached", "cover letter", "seeking employment"]
case_sensitive: false
minimum_matches: 1
severity: "Informational"
# WHY: Monitoring, not blocking. HR may want awareness of departing employees.
# GOTCHA: HR departments legitimately handle resumes. Add HR department exception.
```

```yaml
# KW-4: Negative sentiment / whistleblower detection
detection_method: "keyword"
name: "Whistleblower-Keywords"
keywords: ["SEC complaint", "OSHA complaint", "filing a complaint", "reporting fraud"]
case_sensitive: false
minimum_matches: 1
severity: "Medium"
# WHY: Legal/compliance teams may need awareness of potential whistleblower activity.
# GOTCHA: Legal and ethical considerations. Consult legal counsel before
#         deploying policies that monitor employee communications about
#         regulatory complaints. This may violate whistleblower protections.
```

```yaml
# KW-5: Source code import statements (language-specific)
detection_method: "keyword"
name: "Code-Import-Statements"
keywords: ["import com.company.proprietary", "from company.internal import", "#include \"company/"]
case_sensitive: true
minimum_matches: 3
severity: "Medium"
# WHY: Import statements with internal package names indicate proprietary code.
# GOTCHA: Case-sensitive + minimum 3 reduces false positives from similar
#         open-source imports. Still, test against actual code samples.
```

### 2.3 EDM (5 examples)

```yaml
# EDM-1: Employee PII (standard HR export)
profile_name: "EDM-Employee-PII"
source: "delimited_file"
file: "hr_export_2024.csv"
columns:
  - { col: "SSN", type: "US SSN", key: true }
  - { col: "First Name", type: "First Name" }
  - { col: "Last Name", type: "Last Name" }
  - { col: "Email", type: "Email Address" }
  - { col: "Phone", type: "Phone Number" }
match_criteria: "2_of_5"
error_threshold: 5
schedule: "daily_0200"
# WHY: Employee PII is subject to state privacy laws and GDPR for EU employees.
# GOTCHA: "2 of 5" means First Name + Email alone could trigger (common combo
#         in non-sensitive contexts). Consider requiring SSN as mandatory match field.
```

```yaml
# EDM-2: Customer credit card database (PCI)
profile_name: "EDM-Customer-PCI"
source: "database"
connection: "Oracle-PCI-DB"
query: "SELECT card_number, first_name, last_name, email FROM customers WHERE active=1"
columns:
  - { col: "card_number", type: "Credit Card Number", key: true }
  - { col: "first_name", type: "First Name" }
  - { col: "last_name", type: "Last Name" }
  - { col: "email", type: "Email Address" }
match_criteria: "2_of_4"  # card_number must be one of the 2
error_threshold: 3
schedule: "daily_0300"
# WHY: Database source is more current than CSV exports. Reduces stale data risk.
# GOTCHA: Database query runs on Enforce Server. For 1M+ rows, use Remote EDM
#         Indexer to avoid performance impact on the management server.
```

```yaml
# EDM-3: Patient records (HIPAA)
profile_name: "EDM-Patient-PHI"
source: "delimited_file"
file: "patient_export.csv"
columns:
  - { col: "MRN", type: "Custom", key: true }
  - { col: "SSN", type: "US SSN", key: true }
  - { col: "Patient Name", type: "Full Name" }
  - { col: "DOB", type: "Date of Birth" }
  - { col: "Diagnosis Code", type: "Custom" }
match_criteria: "3_of_5"
error_threshold: 5
schedule: "weekly_sunday_0100"
# WHY: HIPAA requires protecting combinations of identifiers + health data.
# GOTCHA: Medical Record Numbers (MRN) are facility-specific. If your organization
#         has multiple facilities, create separate profiles per facility.
```

```yaml
# EDM-4: Financial account data (banking)
profile_name: "EDM-Bank-Accounts"
source: "delimited_file"
file: "account_master.csv"
columns:
  - { col: "Account Number", type: "Custom", key: true }
  - { col: "Routing Number", type: "ABA Routing Number" }
  - { col: "Account Holder", type: "Full Name" }
  - { col: "Account Type", type: "Custom" }
match_criteria: "2_of_4"
error_threshold: 5
schedule: "daily_0100"
# WHY: Bank account + routing number enables ACH transfers (financial fraud risk).
# GOTCHA: Do NOT include balance or transaction amounts as indexed fields.
#         These change daily and would require constant re-indexing.
```

```yaml
# EDM-5: Partner/vendor price lists (competitive intel)
profile_name: "EDM-Pricing-Data"
source: "delimited_file"
file: "partner_pricing_q1.csv"
columns:
  - { col: "SKU", type: "Custom", key: true }
  - { col: "Partner Name", type: "Full Name" }
  - { col: "Unit Price", type: "Custom" }
  - { col: "Discount Tier", type: "Custom" }
match_criteria: "2_of_4"
error_threshold: 10
schedule: "weekly_monday_0500"
# WHY: Customer-specific pricing is a trade secret. Leaking to competitors
#      gives them unfair negotiation advantage.
# GOTCHA: Pricing changes quarterly. Align re-indexing with pricing cycles.
#         Set higher error threshold (10%) because pricing data formatting
#         is often inconsistent.
```

### 2.4 IDM (5 examples)

```yaml
# IDM-1: M&A legal documents
profile_name: "IDM-MA-Legal"
source: "\\\\legal\\ma-deal-2024\\confidential\\"
match_type: "both"
partial_threshold: 15
enable_endpoint: true
# WHY: M&A documents are the most sensitive legal artifacts.
# GOTCHA: 15% partial threshold is aggressive. May false-positive on
#         standard legal templates shared across deals. Test with real data.
```

```yaml
# IDM-2: Proprietary source code
profile_name: "IDM-Source-Code-Core"
source: "\\\\dev\\repos\\core-platform\\src\\"
match_type: "partial"
partial_threshold: 20
enable_endpoint: true
# WHY: 20% content overlap with core code catches function-level copying.
# GOTCHA: Source code repositories change frequently. Schedule weekly
#         re-indexing or significant new code will be unprotected.
```

```yaml
# IDM-3: Board presentations
profile_name: "IDM-Board-Presentations"
source: "\\\\executive\\board-materials\\2024\\"
match_type: "both"
partial_threshold: 25
# WHY: Board presentations contain financial forecasts and strategic plans.
# GOTCHA: Slides reuse content across quarters. The 25% threshold may trigger
#         on current-quarter presentations that borrow from previous quarters.
```

```yaml
# IDM-4: Patent drafts and invention disclosures
profile_name: "IDM-Patent-Drafts"
source: "\\\\legal\\patents\\pending\\"
match_type: "both"
partial_threshold: 10
enable_endpoint: true
# WHY: Patent drafts before filing are trade secrets. Even 10% content leak
#      could compromise patent priority or reveal invention direction.
# GOTCHA: After patent publication, these documents become public. Remove
#         published patents from the IDM source and re-index.
```

```yaml
# IDM-5: CAD designs and engineering drawings (binary match)
profile_name: "IDM-CAD-Designs"
source: "\\\\engineering\\cad\\current-gen\\"
match_type: "full"
# WHY: Binary files (CAD, JPEG, multimedia) use exact binary match.
# GOTCHA: Partial matching does NOT work for binary files. A modified
#         version of a CAD file will NOT match. Only exact copies detected.
#         For derivative detection, export CAD to text-based format first.
```

### 2.5 VML (5 examples)

```yaml
# VML-1: Financial reports
profile_name: "VML-Financial-Reports"
positive_docs: 300  # Quarterly earnings, annual reports, forecasts
negative_docs: 300  # Marketing materials, press releases, public filings
accuracy_target: 90
# WHY: Financial reports share linguistic patterns (revenue, margin, EBITDA).
# GOTCHA: Re-train annually as financial terminology evolves.
```

```yaml
# VML-2: Source code classification
profile_name: "VML-Proprietary-Code"
positive_docs: 250  # Proprietary Java/Python/Go files
negative_docs: 250  # Open-source library code
accuracy_target: 85
# WHY: Distinguishes proprietary from open-source code patterns.
# GOTCHA: VML works on text content. Binary compiled code is NOT supported.
```

```yaml
# VML-3: Customer communications (legal discovery)
profile_name: "VML-Customer-Comms"
positive_docs: 200  # Customer emails, contracts, proposals
negative_docs: 200  # Internal memos, team chats, marketing content
accuracy_target: 85
# WHY: During legal holds, customer communications must be preserved/controlled.
# GOTCHA: Train with diverse customer types (enterprise, SMB, government)
#         to avoid model bias toward one customer segment.
```

```yaml
# VML-4: Research and development documents
profile_name: "VML-RD-Documents"
positive_docs: 200  # Lab reports, experiment results, research papers
negative_docs: 200  # Published papers, conference proceedings, tutorials
accuracy_target: 88
# WHY: Pre-publication research is IP. VML catches the research "voice."
# GOTCHA: Academic language is similar across pre/post-publication.
#         Model accuracy may plateau at 85-88%. Combine with keyword rules.
```

```yaml
# VML-5: Healthcare clinical trial data
profile_name: "VML-Clinical-Trial"
positive_docs: 150  # Internal trial protocols, patient outcomes, drug data
negative_docs: 150  # Published medical literature, public trial summaries
accuracy_target: 90
# WHY: Clinical trial data is subject to FDA regulations and trade secrets.
# GOTCHA: Smaller training set (150 vs 250 recommended). May need to augment
#         with additional examples to reach 90% accuracy.
```

---

## 3. Detection Rule Examples

```yaml
# DR-1: Simple — SSN in any outbound channel
rule_name: "SSN-Outbound-Simple"
rule_type: "simple"
condition:
  type: "content_matches_data_identifier"
  identifier: "US Social Security Number"
  min_matches: 1
  look_in: ["body", "attachments"]
severity: "High"
# WHY: Catch-all SSN detection across all channels. Simple and reliable.
# GOTCHA: Will trigger on internal emails containing SSNs. Add exceptions
#         for HR-to-HR communications if needed.
# CROSS-REF: Uses DI-1 or DI-2 detection technology.
```

```yaml
# DR-2: Compound — Credit card + external recipient
rule_name: "CC-External-Compound"
rule_type: "compound"
conditions:
  - type: "content_matches_data_identifier"
    identifier: "Credit Card Number"
    min_matches: 1
  - type: "recipient_not_matches"
    pattern: "@company.com"
severity: "High"
# WHY: CC to internal is possibly legitimate (payment processing team).
#      CC to external is almost always a violation.
# GOTCHA: "@company.com" must cover all legitimate internal domains.
#         Include subsidiaries and acquired domains.
# CROSS-REF: Uses DI-3 detection technology.
```

```yaml
# DR-3: EDM-based — employee records detection
rule_name: "Employee-Record-EDM"
rule_type: "simple"
condition:
  type: "content_matches_exact_data"
  profile: "EDM-Employee-PII"
  match_fields: "2_of_5"
severity: "High"
# WHY: EDM provides highest accuracy for structured employee data.
# GOTCHA: "2 of 5" is flexible but may be too broad. A name + email
#         combo is common in non-sensitive contexts.
# CROSS-REF: Uses EDM-1 profile.
```

```yaml
# DR-4: VML + keyword compound — financial reports
rule_name: "Financial-Report-Compound"
rule_type: "compound"
conditions:
  - type: "content_matches_vml_profile"
    profile: "VML-Financial-Reports"
  - type: "content_matches_keyword"
    keywords: ["Q1", "Q2", "Q3", "Q4", "FY20", "earnings"]
    min_matches: 2
severity: "High"
# WHY: VML catches financial report characteristics; keywords confirm it.
# GOTCHA: Compound AND logic means BOTH must match. Legitimate financial
#         reports without quarter references will NOT trigger.
# CROSS-REF: Uses VML-1 profile + KW keywords.
```

```yaml
# DR-5: File property + endpoint action — USB exfiltration
rule_name: "USB-Database-Export"
rule_type: "compound"
conditions:
  - type: "file_name_matches"
    pattern: ".*\\.(sql|bak|mdf|dump|csv)$"
  - type: "endpoint_action"
    action: "removable_storage_copy"
severity: "High"
# WHY: Database exports copied to USB drives is a classic exfiltration vector.
# GOTCHA: File name matching can be bypassed by renaming. Combine with
#         file type detection (binary signature) for defense in depth.
# CROSS-REF: Uses File Properties detection technology.
```

```yaml
# DR-6: IDM-based — confidential document derivative
rule_name: "Confidential-Doc-IDM"
rule_type: "simple"
condition:
  type: "content_matches_indexed_documents"
  profile: "IDM-MA-Legal"
  match_type: "partial"
  threshold: 15
severity: "High"
# WHY: Catches copy-paste from M&A documents into emails or new files.
# GOTCHA: 15% threshold on a 100-page document means ~15 pages of overlap.
#         For short documents, this may be too high. Adjust per document size.
# CROSS-REF: Uses IDM-1 profile.
```

```yaml
# DR-7: Directory group — restrict non-finance users
rule_name: "Finance-Data-Non-Finance-User"
rule_type: "compound"
conditions:
  - type: "content_matches_keyword"
    keywords: ["CONFIDENTIAL FINANCIAL", "INTERNAL FINANCIAL REPORT"]
    min_matches: 1
  - type: "sender_NOT_in_directory_group"
    group: "CN=Finance,OU=Departments,DC=company,DC=com"
severity: "Medium"
# WHY: Financial data is expected from finance team. Non-finance users
#      sending financial markers suggests unauthorized data handling.
# GOTCHA: Directory group membership must be current. Stale AD groups
#         will cause false positives/negatives.
# CROSS-REF: Uses DGM detection technology.
```

---

## 4. Exception Examples

```yaml
# EX-1: Executive team global exception
exception_name: "Executive-Global-Exception"
scope: "message_level"
condition:
  type: "sender_in_directory_group"
  group: "CN=Executives,OU=Groups,DC=company,DC=com"
# WHY: C-suite legitimately shares sensitive data with board/investors.
# GOTCHA: BROAD exception. ANY content from executives bypasses detection.
#         Consider narrowing to specific recipient domains instead.
```

```yaml
# EX-2: HR automated system exception
exception_name: "HR-Automated-Reports"
scope: "message_level"
conditions:
  - type: "sender_matches"
    pattern: "noreply-hr@company.com"
  - type: "recipient_matches"
    pattern: "@company.com"  # Internal only
# WHY: HR system sends SSN-containing reports internally. Multiple conditions
#      ensure the exception only applies to internal HR emails.
# GOTCHA: If the HR system is compromised and sends to external addresses,
#         the recipient condition catches it (exception does NOT apply).
```

```yaml
# EX-3: Payment processing system exception
exception_name: "Payment-Processing-Exception"
scope: "message_level"
condition:
  type: "sender_matches"
  pattern: "payment-gateway@company.com"
# WHY: Payment systems legitimately transmit credit card data.
# GOTCHA: Validate that this exception is still needed quarterly.
#         If the payment gateway changes email addresses, update immediately.
```

```yaml
# EX-4: Legal counsel exception (attorney-client privilege)
exception_name: "Legal-Counsel-Exception"
scope: "message_level"
condition:
  type: "recipient_matches"
  pattern: "@lawfirm.com"  # External legal counsel
# WHY: Communications with legal counsel are privileged and should not
#      be blocked or logged by DLP.
# GOTCHA: Only applies to the specific law firm domain. If counsel changes,
#         update the pattern. Also consider adding internal legal team.
```

```yaml
# EX-5: Encrypted file exception (component-level)
exception_name: "Encrypted-Attachment-Exception"
scope: "component_level"
condition:
  type: "file_type_matches"
  types: ["Password-Protected ZIP", "Encrypted RAR", "PGP Encrypted"]
# WHY: Encrypted files cannot be inspected. Component-level scope means
#      only the encrypted attachment is excluded; other message parts
#      are still inspected.
# GOTCHA: Creates a bypass vector. Monitor encrypted file sending volume
#         separately with a "detect encrypted files" policy.
```

```yaml
# EX-6: Test environment exception (IP-based)
exception_name: "Test-Environment-Exception"
scope: "message_level"
condition:
  type: "source_ip_matches"
  pattern: "10.100.0.0/16"  # Test network range
# WHY: Test environments use synthetic data that matches production patterns.
#      Without this exception, test activities flood incident queues.
# GOTCHA: Ensure test network ranges are accurate. If production servers
#         are accidentally placed in the test range, real incidents are missed.
```

```yaml
# EX-7: Compliance team exception for incident investigation
exception_name: "Compliance-Investigation-Exception"
scope: "message_level"
conditions:
  - type: "sender_in_directory_group"
    group: "CN=Compliance,OU=Groups,DC=company,DC=com"
  - type: "content_matches_keyword"
    keywords: ["DLP-INVESTIGATION-EXEMPT"]
    min_matches: 1
# WHY: Compliance team forwards incident evidence for investigation.
#      Without exception, forwarding detected content creates circular incidents.
# GOTCHA: The keyword "DLP-INVESTIGATION-EXEMPT" must be included in the
#         message. This prevents abuse -- only deliberate exemption requests.
```

---

## 5. Response Rule Examples

```yaml
# RR-1: Block email — high severity PCI violations
response_rule_name: "Block-PCI-Email"
type: "automated"
conditions:
  - severity: "High"
  - server_type: "Network Prevent for Email"
actions:
  - type: "block_message"
    block_type: "entire_message"
    bounce_text: "Your email was blocked because it contains credit card data. Contact security@company.com."
  - type: "send_notification"
    to: "dlp-admins@company.com"
    subject: "BLOCKED: PCI violation by $SENDER$"
# WHY: High-severity PCI violations in email require immediate blocking.
# GOTCHA: Ensure detection rules are well-tuned before enabling. Blocking
#         legitimate emails damages trust in the DLP program.
```

```yaml
# RR-2: Web block — ICAP response to proxy
response_rule_name: "Block-PCI-Web-Upload"
type: "automated"
conditions:
  - severity: "High"
  - server_type: "Network Prevent for Web"
actions:
  - type: "block"
    block_page_url: "https://internal.company.com/dlp-blocked.html"
  - type: "log_to_syslog"
    host: "siem.company.com"
    port: 514
    protocol: "TCP"
    message: "CEF:0|Broadcom|DLP|16.0|$RULES$|$POLICY$|5|..."
# WHY: Web uploads of PCI data to external sites must be blocked at the proxy.
# GOTCHA: The block page URL must be reachable by the user's browser.
#         Proxy must be configured to return DLP-specified block page.
```

```yaml
# RR-3: Endpoint block with user notification
response_rule_name: "Block-Endpoint-USB"
type: "automated"
conditions:
  - server_type: "Endpoint Prevent"
actions:
  - type: "block"
    notification_text: "This file transfer has been blocked because the file contains sensitive data. Contact security@company.com for assistance."
  - type: "send_notification"
    to: "dlp-admins@company.com"
    subject: "ENDPOINT BLOCKED: $ENDPOINT_USERNAME$ on $ENDPOINT_MACHINE$"
# WHY: USB transfers of sensitive data are a primary exfiltration vector.
# GOTCHA: Endpoint block notification appears as a popup on the user's desktop.
#         Customize the message with HTML for branding and clear instructions.
```

```yaml
# RR-4: Quarantine file on file share (Discover/Protect)
response_rule_name: "Quarantine-PII-FileShare"
type: "automated"
conditions:
  - server_type: "Network Discover"
actions:
  - type: "quarantine_file"
    location: "\\\\secure\\dlp-quarantine\\"
    tombstone: "This file has been quarantined by DLP. Contact security@company.com."
  - type: "send_notification"
    to: "$DATA_OWNER$"
    subject: "File quarantined: $FILE_NAME$"
# WHY: Sensitive files on open shares are a data-at-rest risk.
# GOTCHA: Ensure quarantine location has sufficient storage and proper ACLs.
#         Tombstone file replaces the original -- users lose immediate access.
```

```yaml
# RR-5: User Cancel — print with justification
response_rule_name: "UserCancel-Print-Justify"
type: "automated"
conditions:
  - server_type: "Endpoint Prevent"
actions:
  - type: "user_cancel"
    timeout: 60
    timeout_action: "block"
    prompt: "You are printing a document containing sensitive data. Do you want to proceed?"
    require_justification: true
# WHY: Printing may be legitimate (board meeting). User decides with accountability.
# GOTCHA: If user ignores popup for 60 seconds, print is auto-blocked.
#         Justification text is logged in the incident for audit trail.
```

```yaml
# RR-6: Encrypt email via header-based gateway integration
response_rule_name: "Encrypt-Sensitive-Email"
type: "automated"
conditions:
  - severity: "Medium"
  - protocol: "SMTP"
actions:
  - type: "add_header"
    name: "X-DLP-Encrypt"
    value: "true"
  - type: "send_notification"
    to: "$SENDER$"
    subject: "Your email was automatically encrypted by DLP policy"
# WHY: Encrypt rather than block when communication is legitimate but needs protection.
# GOTCHA: Email gateway must be configured to read X-DLP-Encrypt header
#         and trigger encryption. Without gateway config, the header does nothing.
```

```yaml
# RR-7: Apply MIP classification label
response_rule_name: "Apply-Confidential-Label"
type: "automated"
conditions:
  - severity: "High"
actions:
  - type: "apply_classification_label"
    label: "Confidential"
    mip_label_id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
# WHY: Auto-labeling ensures persistent protection. MIP labels travel with
#      the document and enforce access controls regardless of location.
# GOTCHA: MIP SDK must be installed on Enforce Server. MIP tenant credentials
#         must be configured. Label ID must match your Azure/M365 tenant.
```

---

## 6. Policy Examples

```yaml
# POL-1: PCI DSS from template (quickstart path)
policy_name: "PCI-DSS-Complete"
source: "template"
template: "PCI DSS - Credit Card Numbers"
group: "Default Policy Group"
mode: "enabled"
response_rules: ["Block-PCI-Email", "Block-PCI-Web-Upload", "Block-Endpoint-USB"]
# WHY: Template provides complete PCI DSS coverage with minimal configuration.
# GOTCHA: Default template threshold of 1 CC number generates high incident volume.
#         Tune after 1 week of monitoring.
# CROSS-REF: Detection rules from template, response rules RR-1, RR-2, RR-3.
```

```yaml
# POL-2: HIPAA PHI protection (EDM + keyword compound)
policy_name: "HIPAA-PHI-Protection"
source: "custom"
detection_rules:
  - "Patient-Record-EDM"          # EDM-3 profile
  - "HIPAA-Medical-Terms"         # Dictionary rule
  - "SSN-Outbound-Simple"         # Data identifier rule
exceptions:
  - "HR-Automated-Reports"
  - "Legal-Counsel-Exception"
response_rules: ["Block-PCI-Email", "Syslog-All-Violations"]
group: "Compliance Policy Group"
mode: "test_with_notifications"
# WHY: Multi-layered detection catches various PHI exposure scenarios.
# GOTCHA: HIPAA has specific breach notification requirements. Ensure incident
#         workflow includes 60-day notification countdown.
# CROSS-REF: EDM-3, DI dictionary, DR-1, EX-2, EX-4, RR-1.
```

```yaml
# POL-3: Source code IP protection (VML + IDM + keyword)
policy_name: "IP-Source-Code-Protection"
source: "custom"
detection_rules:
  - "VML-Source-Code-Match"       # VML-2 profile
  - "Source-Code-IDM-Match"       # IDM-2 profile
  - "Code-Import-Statements"     # Keyword rule KW-5
exceptions:
  - "CI-CD-Pipeline-Exception"
  - "Open-Source-Contrib-Exception"
response_rules: ["Block-Endpoint-USB", "Notify-Admin-CC-Detection"]
group: "Engineering Policy Group"
mode: "test_without_notifications"
# WHY: Three detection layers cover different code exposure scenarios.
# GOTCHA: Start in test mode. Source code detection generates many false
#         positives initially. Tune VML accuracy and keyword lists first.
# CROSS-REF: VML-2, IDM-2, KW-5.
```

```yaml
# POL-4: Financial data monitoring only (SIEM integration)
policy_name: "Financial-Data-Monitor"
source: "custom"
detection_rules:
  - "Financial-Report-Compound"   # VML + keyword compound (DR-4)
  - "IBAN-Financial-Data"         # Data identifier (DI-5)
exceptions:
  - "Executive-Global-Exception"
response_rules: ["Syslog-All-Violations"]
group: "Default Policy Group"
mode: "enabled"
# WHY: Feed financial data events to SIEM for correlation with other signals.
#      No blocking -- monitoring and analytics only.
# GOTCHA: Monitoring-only policies generate incidents without remediation.
#         Set incident data retention limits to manage database growth.
# CROSS-REF: DR-4, DI-5, EX-1.
```

```yaml
# POL-5: Endpoint-specific policy (USB + cloud + print)
policy_name: "Endpoint-Data-Protection"
source: "custom"
detection_rules:
  - "USB-Database-Export"          # Compound (DR-5)
  - "Cloud-Upload-CC-Data"        # CC + cloud channel compound
  - "Print-Sensitive-Document"    # Keyword + print action compound
exceptions:
  - "Test-Environment-Exception"
response_rules:
  - "Block-Endpoint-USB"
  - "UserCancel-Print-Justify"
  - "Notify-Admin-CC-Detection"
group: "Endpoint Policy Group"
mode: "test_with_notifications"
# WHY: Endpoint-specific policies target data-in-use scenarios.
# GOTCHA: Endpoint policies must be deployed to Endpoint Prevent servers only.
#         If assigned to Default Policy Group, network servers receive unnecessary rules.
# CROSS-REF: DR-5, RR-3, RR-5.
```

```yaml
# POL-6: GDPR personal data (EU operations)
policy_name: "GDPR-Personal-Data-EU"
source: "template"
template: "GDPR - Personal Data"
customizations:
  - add_detection: "EU-IBAN-Detection"
  - add_detection: "EDM-EU-Customer-Records"
  - add_exception: "Data-Processor-Agreement-Exception"
response_rules: ["Encrypt-Sensitive-Email", "Syslog-All-Violations"]
group: "EU Compliance Group"
mode: "enabled"
# WHY: GDPR template provides baseline; customizations add organization-specific data.
# GOTCHA: GDPR requires data breach notification within 72 hours. Ensure
#         incident workflow integration with breach notification process.
# CROSS-REF: DI-5, RR-6.
```

```yaml
# POL-7: Shadow IT detection (cloud upload monitoring)
policy_name: "Shadow-IT-Cloud-Monitor"
source: "custom"
detection_rules:
  - "Large-File-Cloud-Upload"     # File size > 25MB + cloud protocol
  - "Database-Export-Cloud"       # File name pattern + cloud protocol
  - "Source-Code-Cloud"           # Code markers + cloud protocol
exceptions: []  # No exceptions -- monitor everything
response_rules: ["Syslog-All-Violations"]
group: "Default Policy Group"
mode: "enabled"
# WHY: Shadow IT detection feeds security analytics. No blocking to avoid
#      disrupting legitimate cloud usage.
# GOTCHA: High incident volume. Use SIEM correlation to identify patterns
#         (e.g., same user uploading to unapproved cloud storage repeatedly).
```

---

## 7. Policy Group & Deployment Examples

```yaml
# PG-1: Default Policy Group (all servers)
group_name: "Default Policy Group"
description: "Deployed to all detection servers"
servers: "all"
policies: ["PCI-DSS-Complete", "Financial-Data-Monitor", "Shadow-IT-Cloud-Monitor"]
# WHY: Baseline policies that should run everywhere.
# GOTCHA: Adding too many policies to Default slows down all detection servers.
#         Keep only essential, low-overhead policies here.
```

```yaml
# PG-2: Compliance-specific group
group_name: "Compliance Policy Group"
description: "Regulatory compliance policies for compliance detection servers"
servers: ["email-prevent-01", "web-prevent-01", "discover-01"]
policies: ["HIPAA-PHI-Protection", "GDPR-Personal-Data-EU", "SOX-Financial-Compliance"]
# WHY: Compliance policies only need to run on servers handling regulated data.
# GOTCHA: If a new detection server is added, it must be manually added to
#         this group. Forgetting creates a detection gap.
```

```yaml
# PG-3: Engineering-specific group
group_name: "Engineering Policy Group"
description: "IP protection policies for engineering detection infrastructure"
servers: ["endpoint-prevent-eng-01", "network-monitor-eng-02"]
policies: ["IP-Source-Code-Protection"]
# WHY: Source code policies only relevant to engineering endpoints/networks.
# GOTCHA: Engineering VPN users need their agents registered with the
#         engineering endpoint server, or they bypass these policies.
```

```yaml
# PG-4: Endpoint-only group
group_name: "Endpoint Policy Group"
description: "Endpoint-specific policies"
servers: ["endpoint-prevent-01", "endpoint-prevent-02", "endpoint-prevent-dmz-01"]
policies: ["Endpoint-Data-Protection"]
# WHY: Endpoint actions (USB block, print control) only work on endpoint servers.
# GOTCHA: Include DMZ endpoint servers for remote workers. Without DMZ coverage,
#         remote agents have no endpoint policies.
```

```yaml
# PG-5: Executive monitoring group
group_name: "Executive Monitoring Group"
description: "Monitoring-only policies for executive communications"
servers: ["network-monitor-exec"]
policies: ["Executive-Communication-Monitor"]
# WHY: Executive monitoring requires a dedicated, access-controlled server.
#      RBAC limits who can view executive incident data.
# GOTCHA: This creates a separate incident data silo. Ensure the right
#         roles have access to the executive monitoring reports.
```

---

## 8. End-to-End Example: Protecting PCI Data Across Email, Web, and Endpoint

This example demonstrates the complete authoring workflow for a PCI DSS credit card protection policy that covers all three data channels: email, web, and endpoint.

### Step 1: Create Detection Technology Resources

```yaml
# Technology 1: EDM profile for customer credit card database
profile: "EDM-Customer-CC"
type: "exact_data_matching"
source: "database"
connection: "Oracle-PCI-DB"
query: "SELECT card_number, first_name, last_name, email, expiry FROM customers"
key_field: "card_number"
schedule: "daily_0300"
error_threshold: 3
```

```yaml
# Technology 2: Built-in credit card data identifier (already available)
identifier: "Credit Card Number"
type: "data_identifier"
validation: "Luhn algorithm"
```

### Step 2: Create Detection Rules

```yaml
# Rule 1: Single credit card (any channel)
rule: "PCI-Single-CC"
type: "simple"
condition: "Content Matches Data Identifier: Credit Card Number >= 1"
severity: "High"
```

```yaml
# Rule 2: EDM match against customer database (highest confidence)
rule: "PCI-EDM-Customer-Match"
type: "simple"
condition: "Content Matches Exact Data: EDM-Customer-CC (2 of 5 fields)"
severity: "High"
```

```yaml
# Rule 3: Bulk CC numbers (data exfiltration indicator)
rule: "PCI-Bulk-CC"
type: "compound"
conditions:
  - "Content Matches Data Identifier: Credit Card Number >= 10 (unique)"
  - "Recipient NOT matches: @company.com"
severity: "High"
```

### Step 3: Create Exceptions

```yaml
# Exception 1: Payment processing system
exception: "Payment-Gateway-Exception"
scope: "message_level"
condition: "Sender matches: payment-gateway@company.com"
```

```yaml
# Exception 2: PCI compliance team
exception: "PCI-Audit-Exception"
scope: "message_level"
conditions:
  - "Sender in directory group: CN=PCI-Audit,OU=Groups,DC=company,DC=com"
  - "Content matches keyword: PCI-AUDIT-EXEMPT (min 1)"
```

### Step 4: Create Response Rules

```yaml
# Response 1: Block email (Network Prevent for Email)
response: "PCI-Block-Email"
type: "automated"
conditions:
  - severity: "High"
  - server_type: "Network Prevent for Email"
actions:
  - block_message: "entire"
  - send_notification:
      to: "dlp-admins@company.com"
      subject: "BLOCKED: PCI violation by $SENDER$"
  - log_to_syslog:
      host: "siem.company.com"
      port: 514
      message: "CEF:0|Broadcom|DLP|16.0|PCI|$POLICY$|8|INCIDENT_ID=$INCIDENT_ID$ SENDER=$SENDER$ BLOCKED=true"
```

```yaml
# Response 2: Block web upload (Network Prevent for Web)
response: "PCI-Block-Web"
type: "automated"
conditions:
  - severity: "High"
  - server_type: "Network Prevent for Web"
actions:
  - block:
      page_url: "https://internal.company.com/dlp-blocked-pci.html"
  - log_to_syslog:
      host: "siem.company.com"
      port: 514
      message: "CEF:0|Broadcom|DLP|16.0|PCI|$POLICY$|8|INCIDENT_ID=$INCIDENT_ID$ BLOCKED=true"
```

```yaml
# Response 3: Block endpoint transfer (Endpoint Prevent)
response: "PCI-Block-Endpoint"
type: "automated"
conditions:
  - severity: "High"
  - server_type: "Endpoint Prevent"
actions:
  - block:
      notification: "BLOCKED: This transfer contains credit card data and has been blocked per PCI DSS policy. Contact security@company.com."
  - log_to_syslog:
      host: "siem.company.com"
      port: 514
      message: "CEF:0|Broadcom|DLP|16.0|PCI|$POLICY$|8|INCIDENT_ID=$INCIDENT_ID$ ENDPOINT_USER=$ENDPOINT_USERNAME$ MACHINE=$ENDPOINT_MACHINE$"
```

```yaml
# Response 4: Quarantine on file shares (Network Discover)
response: "PCI-Quarantine-Files"
type: "automated"
conditions:
  - severity: "High"
  - server_type: "Network Discover"
actions:
  - quarantine:
      location: "\\\\secure\\pci-quarantine\\"
      tombstone: "This file has been quarantined: contains credit card data."
  - send_notification:
      to: "$DATA_OWNER$"
      subject: "PCI Alert: File quarantined - $FILE_NAME$"
```

### Step 5: Assemble the Policy

```yaml
policy:
  name: "PCI-DSS-Complete-MultiChannel"
  description: "Comprehensive PCI DSS credit card protection across email, web, endpoint, and data-at-rest"
  detection_rules:
    - "PCI-Single-CC"
    - "PCI-EDM-Customer-Match"
    - "PCI-Bulk-CC"
  exceptions:
    - "Payment-Gateway-Exception"
    - "PCI-Audit-Exception"
  response_rules:
    - "PCI-Block-Email"
    - "PCI-Block-Web"
    - "PCI-Block-Endpoint"
    - "PCI-Quarantine-Files"
  policy_group: "Default Policy Group"
  mode: "test_without_notifications"  # Start in test mode!
```

### Step 6: Deployment and Tuning Roadmap

```
Week 1: Test Without Notifications
  - Monitor incident dashboard daily
  - Review false positive rate
  - Identify exceptions needed for business processes
  - Target: <5% false positive rate

Week 2: Test With Notifications
  - Users receive warnings (no blocking)
  - Collect feedback on false positives
  - Add exceptions based on feedback
  - Target: <2% false positive rate

Week 3: Staged Enforcement
  - Enable blocking on email channel first (highest risk)
  - Keep web and endpoint in notify mode
  - Monitor for business impact
  - Target: Zero legitimate email blocked

Week 4+: Full Enforcement
  - Enable blocking on all channels
  - Run Discover scan for data-at-rest
  - Enable quarantine for file shares
  - Continuous monitoring and tuning
```

### Complete Architecture Diagram

```
                              +-------------------+
                              |   Enforce Server   |
                              | (Policy: PCI-DSS)  |
                              +--------+----------+
                                       |
                    +------------------+-----------------+
                    |                  |                 |
           +--------v------+   +------v-------+  +-----v--------+
           | Email Prevent  |   | Web Prevent   |  | Endpoint     |
           | Server         |   | Server        |  | Prevent Svr  |
           +--------+------+   +------+-------+  +------+-------+
                    |                  |                  |
              +-----v------+    +-----v------+    +------v------+
              | Action:     |    | Action:     |    | Action:      |
              | BLOCK email |    | BLOCK web   |    | BLOCK USB/   |
              | + NOTIFY    |    | upload via   |    | print/cloud  |
              | + SYSLOG    |    | ICAP proxy   |    | + NOTIFY     |
              +-----------+     | + SYSLOG    |    | user popup   |
                                +------------+     | + SYSLOG     |
                                                    +-------------+

           + Discover Server: QUARANTINE files on shares + NOTIFY owner
```

---

## 9. Policy Template Catalog

Full list of pre-built policy templates available in Symantec DLP. [S1, S4]

### Compliance Templates

| Category | Templates |
|----------|----------|
| **PCI DSS** | Credit Card Numbers, All PCI Policy Templates |
| **HIPAA** | HIPAA (Including PHI), HIPAA Privacy Rule |
| **GLBA** | GLBA Financial Information, GLBA Customer Data |
| **SOX** | SOX Financial Data, SOX Compliance |
| **GDPR** | EU GDPR Personal Data, EU GDPR Special Categories |
| **CCPA** | California Consumer Privacy |
| **FERPA** | Student Education Records |
| **UK DPA** | UK Data Protection Act |
| **Canadian PIPEDA** | Canadian Personal Information |
| **Australian Privacy** | Australian Privacy Act |

### Industry Templates

| Category | Templates |
|----------|----------|
| **Financial Services** | Bank Account Numbers, ABA Routing, SWIFT, Wire Transfer |
| **Healthcare** | Patient Records, Drug Names, DICOM Images |
| **Government** | Classified Markers, FOUO, CUI, Export Controls (ITAR/EAR) |
| **Technology** | Source Code, API Keys, Encryption Keys |
| **Legal** | Attorney-Client Privilege, Litigation Hold |
| **Human Resources** | Employee PII, Tax Forms (W-2, 1099), Benefits Data |

### Data Protection Templates

| Category | Templates |
|----------|----------|
| **Personal Information** | SSN, Driver License, Passport, Date of Birth |
| **Financial Data** | Credit Card, Bank Account, Tax ID |
| **Credentials** | Passwords, API Keys, Certificates |
| **Intellectual Property** | Source Code, Design Documents, Trade Secrets |

**Template count:** 65+ built-in templates. Additional templates can be created, exported, and imported as XML. [S1, S4]

---

## 10. Advanced Compound Rule Patterns

### Pattern 1: Threshold Escalation

Create multiple rules at different severity levels based on match count:

```yaml
# Low severity: 1-4 credit card numbers (possible incidental)
rule: "PCI-Low-CC"
condition: "CC Number >= 1 AND CC Number < 5"
severity: "Low"

# Medium severity: 5-9 credit card numbers (concerning)
rule: "PCI-Medium-CC"
condition: "CC Number >= 5 AND CC Number < 10"
severity: "Medium"

# High severity: 10+ credit card numbers (exfiltration)
rule: "PCI-High-CC"
condition: "CC Number >= 10"
severity: "High"
```

### Pattern 2: Channel-Specific Detection

```yaml
# Email: SSN + external recipient
rule: "SSN-Email-External"
conditions:
  - "Content Matches DI: US SSN >= 1"
  - "Protocol: SMTP"
  - "Recipient NOT matches: @company.com"
severity: "High"

# Web: SSN + cloud upload
rule: "SSN-Web-Upload"
conditions:
  - "Content Matches DI: US SSN >= 1"
  - "Protocol: HTTP/HTTPS"
severity: "High"

# Endpoint: SSN + USB copy
rule: "SSN-USB-Copy"
conditions:
  - "Content Matches DI: US SSN >= 1"
  - "Endpoint Action: Removable Storage Copy"
severity: "High"
```

### Pattern 3: User Risk-Augmented Detection (ICA Integration, 16.0+)

```yaml
# Low match count + high user risk = High severity
rule: "Risk-Augmented-PCI"
conditions:
  - "Content Matches DI: CC Number >= 1"
  - "User Risk Score > 80"  # ICA integration
severity: "High"
# WHY: A single CC number from a high-risk user is more concerning than
#      the same from a low-risk user. Risk scoring adds context.
```

### Pattern 4: MIP Label-Aware Detection (16.0+)

```yaml
# Detect when Confidential-labeled document is sent externally
rule: "MIP-Confidential-External"
conditions:
  - "Content Matches MIP Tag: Confidential"
  - "Recipient NOT matches: @company.com"
severity: "High"
# WHY: Documents already labeled "Confidential" by MIP should never go external.
```

---

## 11. FlexResponse Extensibility

FlexResponse allows custom remediation actions via Java plug-in architecture. [S1, S4, S10]

### Server FlexResponse

- Custom Java JAR files deployed to detection servers
- Configured via `Plugins.properties` file
- Invoked as response rule actions
- Use cases: custom quarantine, DRM application, integration with third-party systems

### Endpoint FlexResponse

- Custom Java JAR files deployed to endpoint agents
- Invoked when endpoint detection triggers
- Use cases: endpoint-specific encryption, custom file handling, integration with endpoint security tools

### FlexResponse Example

```
# Server FlexResponse: Email quarantine to custom system
# Plugins.properties configuration:
com.symantec.dlp.flexresponse.plugins=EmailQuarantinePlugin
com.symantec.dlp.flexresponse.EmailQuarantinePlugin.jar=email-quarantine-1.0.jar
com.symantec.dlp.flexresponse.EmailQuarantinePlugin.class=com.company.dlp.EmailQuarantineAction
```

---

## 12. API-Based Policy Management

### Policy Import/Export (DLP 25.1+)

The policy import/export API enables a "DLP-as-code" workflow. [API-intelligence]

```bash
# Export all policies as XML
curl -X POST \
  "https://enforce:443/ProtectManager/webservices/v2/policies/export" \
  -H "Authorization: Basic $(echo -n 'admin:password' | base64)" \
  -H "Content-Type: application/json" \
  -o policies-backup.xml

# Import policy XML
curl -X POST \
  "https://enforce:443/ProtectManager/webservices/v2/policies/import" \
  -H "Authorization: Basic $(echo -n 'admin:password' | base64)" \
  -H "Content-Type: application/xml" \
  --data-binary @pci-policy.xml

# Deploy policy changes to detection servers
curl -X POST \
  "https://enforce:443/ProtectManager/webservices/v2/policies/apply" \
  -H "Authorization: Basic $(echo -n 'admin:password' | base64)"

# List policies and policy groups
curl -X GET \
  "https://enforce:443/ProtectManager/webservices/v2/policies" \
  -H "Authorization: Basic $(echo -n 'admin:password' | base64)"
```

### EDM Index Trigger (DLP 16.0 RU2+)

```bash
# Trigger EDM re-indexing on demand
curl -X POST \
  "https://enforce:443/ProtectManager/webservices/v2/edm/index" \
  -H "Authorization: Basic $(echo -n 'admin:password' | base64)" \
  -H "Content-Type: application/json" \
  -d '{"profileId": 12345}'
```

### Detection REST API 2.0 — Content Inspection

```bash
# Submit content for policy scanning
curl -X POST \
  "https://detector:443/v2.0/DetectionRequests" \
  --cert client.pem \
  --key client-key.pem \
  -H "Content-Type: application/json" \
  -d '{
    "options": {},
    "context": {
      "messageSource": "API",
      "sender": "user@company.com",
      "recipients": ["external@partner.com"]
    },
    "content": {
      "contentParts": [{
        "name": "test-file.txt",
        "contentType": "text/plain",
        "data": "'$(echo -n "4111-1111-1111-1111" | base64)'"
      }]
    }
  }'
```

**Response includes:** violation status, matched policies, matched rules, severity level, and recommended response actions (block, quarantine, encrypt, notify). [API-intelligence]

### CloudSOC Cloud DLP API — Profile Management

```bash
# List cloud DLP profiles
curl -X GET \
  "https://app.elastica.net/api/clouddlp/protect/public/profile" \
  -H "Authorization: Bearer <api_key>"

# Create cloud DLP profile with rules and data identifiers
curl -X POST \
  "https://app.elastica.net/api/clouddlp/protect/public/profile" \
  -H "Authorization: Bearer <api_key>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "PCI-Cloud-Profile",
    "rules": [...],
    "dataIdentifiers": [...]
  }'
```

**Note:** The CloudSOC API provides more granular profile authoring than the on-prem Enforce API. Cloud profiles can be created with embedded rules and data identifiers via API, whereas on-prem rule authoring remains console-only. [API-intelligence]

---

*End of advanced reference. Total examples: 60+ across all object types. Total ASCII UI diagrams: 8 key screens. End-to-end PCI scenario covers all 6 layers.*
