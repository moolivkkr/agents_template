# Advanced: Incident Management

> **Scope:** All incident fields, workflow states, Smart Response configuration, SOAR integration patterns, API endpoints with curl examples
> **Versions:** DLP 15.7 through 26.1
> **Sources:** [S1] Help Center 16.0, [S2] Help Center 25.1, [S3] Help Center 26.1, [S4] Full PDF 16.0, API Intelligence Report, SOAR connector documentation

---

## Table of Contents

1. [Complete Incident Field Reference](#1-complete-incident-field-reference)
2. [Advanced Filtering and Saved Searches](#2-advanced-filtering-and-saved-searches)
3. [Smart Response Rule Deep Dive](#3-smart-response-rule-deep-dive)
4. [Automated Response Rule Deep Dive](#4-automated-response-rule-deep-dive)
5. [Lookup Plugin Configuration](#5-lookup-plugin-configuration)
6. [End User Remediation Deep Dive](#6-end-user-remediation-deep-dive)
7. [SOAR Integration Patterns](#7-soar-integration-patterns)
8. [REST API Complete Reference with Examples](#8-rest-api-complete-reference-with-examples)
9. [SIEM Integration: Syslog and CEF](#9-siem-integration-syslog-and-cef)
10. [Incident Workflows (DLP 26.1)](#10-incident-workflows-dlp-261)
11. [Performance Optimization](#11-performance-optimization)
12. [Incident Retention and Archival](#12-incident-retention-and-archival)
13. [Troubleshooting Reference](#13-troubleshooting-reference)

---

## 1. Complete Incident Field Reference

### Standard Incident Fields

| Field | Type | Editable | API Name | Description |
|-------|------|----------|----------|-------------|
| Incident ID | Integer | No | `incidentId` | Auto-generated unique identifier |
| Creation Date | Timestamp | No | `incidentCreationDate` | When the incident was created |
| Detection Date | Timestamp | No | `detectionDate` | When the violation was detected (may differ from creation) |
| Severity | Enum (1-4) | Yes | `severity` | 1=High, 2=Medium, 3=Low, 4=Informational |
| Status | String | Yes | `incidentStatusName` | Current workflow status |
| Policy Name | String | No | `policyName` | Policy that triggered the incident |
| Policy ID | Integer | No | `policyId` | Internal policy identifier |
| Policy Group | String | No | `policyGroupName` | Policy group containing the policy |
| Rule Name(s) | String[] | No | `matchedRules` | Detection rules that matched |
| Detection Server | String | No | `detectionServerName` | Server that detected the violation |
| Detection Server Type | Enum | No | `detectionServerType` | NETWORK, ENDPOINT, DISCOVER |
| Match Count | Integer | No | `matchCount` | Number of content matches |
| Protocol | String | No | `protocol` | SMTP, HTTP, FTP, USB, PRINT, CLIPBOARD, etc. |
| Sender | String | No | `sender` | Email sender or source user |
| Recipient(s) | String[] | No | `recipients` | Email recipients or destination |
| Subject | String | No | `subject` | Email subject or file name |
| File Name | String | No | `fileName` | Name of file containing violation |
| File Type | String | No | `fileType` | Detected file format |
| Endpoint User | String | No | `endpointUser` | Username on the endpoint |
| Endpoint Hostname | String | No | `endpointMachine` | Hostname of the endpoint |
| Source IP | String | No | `machineIp` | IP address of the source |
| Target URL | String | No | `targetUrl` | Destination URL (web incidents) |
| Prevent Action Status | Enum | No | `preventActionStatus` | Block/Allow/Quarantine result |
| Protect Action Status | Enum | No | `protectActionStatus` | Discover remediation action result |
| Remediation Status | String | Yes | `remediationStatus` | Status of remediation actions |
| Notes | Text | Yes | `incidentNotes` | Free-text investigation notes |
| Custom Attributes | Map | Yes | `customAttributes` | Organization-defined attributes |

### Endpoint-Specific Fields

| Field | Description | Example |
|-------|-------------|---------|
| Application Name | Application that triggered the violation | "Microsoft Outlook", "Chrome" |
| Device Type | Type of endpoint device | "Removable Storage", "Local Drive", "Printer" |
| Device Serial | USB device serial number (for removable storage) | "SN-A1B2C3D4E5" |
| Justification | User-provided justification (User Cancel response) | "Approved by manager for audit purposes" |
| Agent Version | DLP agent version on the endpoint | "16.0.2.1234" |

### Discovery-Specific Fields

| Field | Description | Example |
|-------|-------------|---------|
| File Path | Full path to the file on the target | `\\fs01\hr\employee-ssn-list.xlsx` |
| File Owner | Owner of the file (from filesystem metadata) | `CORP\john.smith` |
| File Created | File creation timestamp | 2025-03-15T10:30:00Z |
| File Modified | File last-modified timestamp | 2026-01-20T14:22:00Z |
| Scan Target | Name of the discover scan target | "HR File Share - Weekly PII Scan" |
| Remediation Action | Protect action taken on the file | "Quarantined to \\quarantine\dlp\" |

---

## 2. Advanced Filtering and Saved Searches

### Filter Operators

| Operator | Applicable Fields | Description |
|----------|------------------|-------------|
| Equals | All string/enum fields | Exact match |
| Contains | String fields | Substring match |
| Starts With | String fields | Prefix match |
| Ends With | String fields | Suffix match |
| Greater Than | Date, numeric fields | After date / above threshold |
| Less Than | Date, numeric fields | Before date / below threshold |
| Between | Date, numeric fields | Range match |
| Is Empty | All fields | Field has no value |
| Is Not Empty | All fields | Field has a value |
| In List | Enum fields | Matches any value in a list |

### Compound Filters

Filters can be combined with AND/OR logic:

```
(Severity = HIGH OR Severity = CRITICAL)
AND (Status = New)
AND (Policy Name CONTAINS "PCI")
AND (Detection Date > 2026-05-01)
```

### Saved Search Configuration

**Navigation:** Incidents > [set filters] > Save As

| Setting | Options | Description |
|---------|---------|-------------|
| Name | Text | Name for the saved search |
| Description | Text | Optional description |
| Visibility | Private / Shared | Private: only you; Shared: everyone in your role |
| Dashboard | Yes/No | Include in dashboard as a widget |
| Schedule | None / Daily / Weekly | Auto-run and email results |
| Recipients | Email addresses | Who receives scheduled reports |

### Recommended Saved Searches

| Name | Filters | Purpose |
|------|---------|---------|
| Open PCI - High | Severity=High, Policy contains "PCI", Status=New or In Process | PCI analyst daily queue |
| Open HIPAA | Policy contains "HIPAA", Status=New or In Process | Healthcare compliance queue |
| False Positives This Week | Status=False Positive, Date=last 7 days | Weekly false positive review |
| Unassigned > 24hrs | Status=New, Date < 24 hours ago, Assigned=empty | SLA breach candidates |
| Repeat Offenders | Group by Sender, Count > 5 in 30 days | User training candidates |
| Discovery Findings - Unremediated | Detection Server Type=DISCOVER, Protect Action Status=Pending | Discover remediation backlog |

---

## 3. Smart Response Rule Deep Dive

### Complete Smart Response Configuration

**Navigation:** Manage > Policies > Response Rules > Add Response Rule > Smart Response

**Screen layout (logical structure):**
```
+---------------------------------------------------------------+
| New Smart Response Rule                                        |
+---------------------------------------------------------------+
| General Tab                                                    |
|   Rule Name: [_________________________]                       |
|   Description: [_________________________]                     |
+---------------------------------------------------------------+
| Actions Tab                                                    |
|   +--------------------------------------------------+         |
|   | Action Type          | Configuration              |        |
|   | Set Status           | [dropdown: status value]   |        |
|   | Set Attribute        | [attr name] = [value]      |        |
|   | Send Email           | To/Subject/Body template   |        |
|   | Log to Syslog        | Host/Port/Message          |        |
|   | Add Note             | [note text template]       |        |
|   +--------------------------------------------------+         |
|   [Add Action]                                                 |
+---------------------------------------------------------------+
| [Save] [Cancel]                                                |
+---------------------------------------------------------------+
```

### Smart Response Action: Send Email Notification

| Field | Description | Example |
|-------|-------------|---------|
| To | Recipient(s) | `{sender.manager}`, `dlp-team@corp.com`, `legal@corp.com` |
| CC | CC recipient(s) | Optional |
| Subject | Subject line (supports variables) | "DLP Incident #{incidentId} - {policyName}" |
| Body | Email body (supports variables, HTML) | See template below |
| Attachment | Attach incident summary | Yes/No |

**Email variables available:**
- `{incidentId}` -- Incident ID
- `{policyName}` -- Policy that triggered
- `{severity}` -- Severity level
- `{sender}` -- Sender/source user
- `{recipients}` -- Recipient(s)
- `{matchCount}` -- Number of matches
- `{detectionServer}` -- Detection server name
- `{protocol}` -- Protocol
- `{fileName}` -- File name
- `{subject}` -- Message subject
- `{timestamp}` -- Detection timestamp
- `{endpointUser}` -- Endpoint username
- `{endpointMachine}` -- Endpoint hostname

**Example email body template:**
```html
<h3>DLP Incident Escalation</h3>
<p>A DLP incident requires your attention:</p>
<table border="1" cellpadding="5">
  <tr><td><b>Incident ID</b></td><td>{incidentId}</td></tr>
  <tr><td><b>Policy</b></td><td>{policyName}</td></tr>
  <tr><td><b>Severity</b></td><td>{severity}</td></tr>
  <tr><td><b>User</b></td><td>{sender}</td></tr>
  <tr><td><b>Matches</b></td><td>{matchCount}</td></tr>
  <tr><td><b>Detection</b></td><td>{detectionServer} via {protocol}</td></tr>
</table>
<p>Please review this incident in the DLP console:
<a href="https://enforce-server/ProtectManager/incident/{incidentId}">View Incident</a></p>
```

### Comprehensive Smart Response Rule Library

| Rule Name | Actions | Variables Used |
|-----------|---------|----------------|
| Escalate to Manager | Set Status: Escalated + Email to `{sender.manager}` + Note: "Escalated to manager" | sender.manager |
| Escalate to Legal | Set Status: Under Legal Review + Email to `legal@corp.com` + Note: "Referred to legal" | -- |
| Mark False Positive | Set Status: False Positive + Note: "Confirmed FP by {currentUser}" | currentUser |
| Assign Training | Set Attr: Training=Assigned + Email to sender + Note: "Training assigned" | sender |
| Grant Exception | Set Status: Resolved + Set Attr: Resolution=Exception + Note: "Exception granted per policy XYZ" | -- |
| Request Justification | Email to sender asking for justification + Set Status: Waiting for Response | sender |
| Close - No Action | Set Status: Resolved + Set Attr: Resolution=No Action Required + Note: "Reviewed, no action needed" | -- |

---

## 4. Automated Response Rule Deep Dive

### Complete Automated Response Configuration

**Navigation:** Manage > Policies > Response Rules > Add Response Rule > Automated Response

**Screen layout (logical structure):**
```
+---------------------------------------------------------------+
| New Automated Response Rule                                     |
+---------------------------------------------------------------+
| General Tab                                                     |
|   Rule Name: [_________________________]                        |
|   Description: [_________________________]                      |
+---------------------------------------------------------------+
| Conditions Tab                                                  |
|   +--------------------------------------------------+          |
|   | Condition Type       | Operator | Value            |        |
|   | Severity             | Equals   | [High v]         |        |
|   | Protocol             | Equals   | [SMTP v]         |        |
|   | Recipient Pattern    | Matches  | [*@external.com] |        |
|   +--------------------------------------------------+          |
|   [Add Condition]                                               |
|   Condition Logic: ( ) ALL conditions match  (o) ANY matches    |
+---------------------------------------------------------------+
| Actions Tab                                                     |
|   +--------------------------------------------------+          |
|   | Action Type          | Configuration              |         |
|   | Block Message        | Block reason text          |         |
|   | Send Notification    | To/Subject/Body            |         |
|   | Log to Syslog        | Host/Port/Message/Protocol |         |
|   | Set Status           | [In Process v]             |         |
|   +--------------------------------------------------+          |
|   [Add Action]                                                  |
+---------------------------------------------------------------+
| [Save] [Cancel]                                                 |
+---------------------------------------------------------------+
```

### Response Rule Actions -- Complete Configuration Reference

#### Block Message (Network Prevent for Email)

| Field | Description | Default |
|-------|-------------|---------|
| Block Reason | Text shown to sender when message is bounced | "This message was blocked by the DLP system." |
| NDR Template | Non-delivery report template | Customizable |
| Notify Sender | Send notification to original sender | Yes |
| Notify Admin | CC admin on block notification | Optional |

#### Block (Network Prevent for Web / ICAP)

| Field | Description | Default |
|-------|-------------|---------|
| Block Page | HTML page returned to user's browser via proxy | "Access denied by DLP policy." |
| Custom URL | Redirect to custom block page | Optional |
| Log Request | Log blocked request details | Yes |

#### Block (Endpoint Prevent)

| Field | Description | Default |
|-------|-------------|---------|
| Popup Message | Text displayed in the endpoint popup | "This action is blocked by corporate policy." |
| Popup Title | Title of the notification popup | "Data Loss Prevention" |
| Allow Justify | Let user provide justification to proceed | No (full block) |
| Custom Branding | Organization logo in popup | Optional |

#### User Cancel (Endpoint Prevent)

| Field | Description | Default |
|-------|-------------|---------|
| Popup Message | Text explaining the violation and options | "Sensitive data detected. Cancel or justify." |
| Timeout | Seconds before auto-block if no response | 120 seconds |
| Justification Required | User must enter text justification to proceed | Yes |
| Justification Options | Dropdown of predefined reasons | "Business need", "Manager approved", "Test data" |

#### Quarantine Message (Network Prevent for Email via SMG)

| Field | Description |
|-------|-------------|
| SMG Server | Symantec Messaging Gateway hostname |
| Quarantine Folder | Folder in SMG quarantine |
| Notification | Email to sender about quarantine |
| Release Workflow | Who can release quarantined messages |

#### Quarantine File (Network Discover / Protect)

| Field | Description |
|-------|-------------|
| Quarantine Path | UNC path to quarantine directory |
| Subfolder Template | `{Year}/{Month}/{PolicyName}/` |
| Breadcrumb | Template file left at original location |
| Preserve Permissions | Copy file ACLs to quarantine |

#### Log to Syslog Server

| Field | Description | Example |
|-------|-------------|---------|
| Host | Syslog server hostname/IP | `siem.corp.local` |
| Port | Syslog port | 514 |
| Protocol | UDP or TCP | TCP |
| Facility | Syslog facility | LOCAL0 (default) |
| Level | Syslog severity level | WARNING |
| Message Template | CEF or custom format | See Section 9 |

#### Send Email Notification

| Field | Description |
|-------|-------------|
| To | Recipient(s) -- supports variables and static addresses |
| CC | CC recipients |
| Subject | Subject template with variables |
| Body | HTML body template with variables |
| Attach Summary | Include incident summary as attachment |

#### Set Status

| Field | Description |
|-------|-------------|
| Status | Dropdown of available incident statuses |

#### Set Attribute

| Field | Description |
|-------|-------------|
| Attribute Name | Custom attribute to set |
| Attribute Value | Value to assign |

#### Limit Incident Data Retention

| Field | Description |
|-------|-------------|
| Retain For | Number of days to keep full incident data |
| After Retention | Delete evidence, keep metadata only |
| Apply To | Current policy or global |

---

## 5. Lookup Plugin Configuration

### LDAP Lookup Plugin -- Complete Configuration

**Navigation:** System > Lookup Plugins > New Plugin > LDAP

**Step 1: Create Directory Connection**
```
System > Settings > Directory Connections > Add
  Server: ldap.corp.local
  Port: 389 (LDAP) or 636 (LDAPS)
  Base DN: dc=corp,dc=local
  Bind DN: cn=dlp-lookup,ou=Service Accounts,dc=corp,dc=local
  Bind Password: ************
  Encryption: LDAPS (recommended)
```

**Step 2: Create LDAP Plugin**
```
System > Lookup Plugins > Add Plugin > LDAP
  Name: "Active Directory User Lookup"
  Directory Connection: (select from Step 1)
  Execution: On Incident Creation (automatic)
```

**Step 3: Map Attributes**

The mapping format is:
```
attr.<CustomAttributeName> = <searchBase>:(<searchFilter>=<$variable$>):<ldapAttribute>
```

Example mappings:
```properties
# Map user department from AD
attr.Department = ou=Users,dc=corp,dc=local:(sAMAccountName=$sender.login$):department

# Map user's manager
attr.Manager = ou=Users,dc=corp,dc=local:(sAMAccountName=$sender.login$):manager

# Map user's email for notification routing
attr.UserEmail = ou=Users,dc=corp,dc=local:(sAMAccountName=$sender.login$):mail

# Map cost center from AD extension attribute
attr.CostCenter = ou=Users,dc=corp,dc=local:(sAMAccountName=$sender.login$):extensionAttribute1

# Map office location
attr.OfficeLocation = ou=Users,dc=corp,dc=local:(sAMAccountName=$sender.login$):physicalDeliveryOfficeName
```

**Available variables:**
- `$sender.login$` -- Sender username (sAMAccountName)
- `$sender.email$` -- Sender email address
- `$sender.ip$` -- Sender IP address
- `$recipient.email$` -- Recipient email address

### Script Lookup Plugin

For enrichment that cannot come from LDAP:

```
System > Lookup Plugins > Add Plugin > Script
  Name: "Risk Score Lookup"
  Script Path: /opt/dlp/scripts/risk-score.sh
  Execution: On Incident Creation
  Parameters: $sender.login$
```

The script receives incident data as input and returns custom attribute values.

---

## 6. End User Remediation Deep Dive

### Configuration

**Navigation:** System > Settings > End User Remediation

| Setting | Options | Description |
|---------|---------|-------------|
| Enable | On/Off | Master switch for end user remediation |
| Eligible Incidents | By policy, severity, channel | Which incidents can be sent to end users |
| Visible Information | Policy name, matched content (masked/unmasked), file details | What the end user can see |
| Available Actions | Resolve, Justify, Delete, Request Exception, Escalate | What the end user can do |
| Timeout Period | 1-30 days | How long user has to respond |
| Timeout Action | Escalate / Auto-resolve / Do nothing | What happens on timeout |
| Out-of-Office Handling | Route to alternate / Hold | Handle unavailable users |
| Portal URL | URL | Remediation portal accessible by end users |

### User Experience Flow

1. User triggers a DLP incident (e.g., email blocked)
2. User receives email: "A DLP violation was detected. Please review and take action."
3. Email contains a link to the remediation portal
4. User clicks link, authenticates, sees the incident details
5. User sees:
   - Policy violated
   - Summary of matched content (may be masked)
   - Available actions
6. User selects an action:
   - "This was intentional and authorized" -> Provides justification -> Incident resolved
   - "This was a mistake" -> Incident resolved with user acknowledgment
   - "I need an exception" -> Routes to security team for exception review
   - "I need help" -> Escalates to manager or DLP team
7. Action syncs back to Enforce Console: incident status updated, user response recorded

---

## 7. SOAR Integration Patterns

### Pattern 1: Cortex XSOAR Incident Polling Playbook

```yaml
# Cortex XSOAR Playbook: DLP Incident Triage
name: DLP Incident Triage
trigger:
  type: fetch_incidents
  source: Symantec DLP v2
  interval: 2m
  filter: severity=HIGH

tasks:
  1_enrich:
    name: Enrich User Data
    commands:
      - command: ad-get-user
        args: username=${incident.sender}
      - command: symantec-dlp-get-incident-details
        args: incident_id=${incident.incidentId}

  2_classify:
    name: Auto-Classify
    condition:
      if: ${incident.policyName} contains "PCI"
      then: goto task 3_pci
      else: goto task 4_general

  3_pci:
    name: PCI Response
    commands:
      - command: symantec-dlp-update-incident
        args:
          incident_id: ${incident.incidentId}
          status: "In Process"
          notes: "Auto-classified as PCI incident by XSOAR playbook"
          custom_attributes: "Regulatory Scope=PCI"
      - command: send-mail
        args:
          to: pci-compliance@corp.com
          subject: "PCI DLP Incident #${incident.incidentId}"

  4_general:
    name: General Response
    commands:
      - command: symantec-dlp-update-incident
        args:
          incident_id: ${incident.incidentId}
          status: "In Process"
          notes: "Under SOAR review"
```

### Pattern 2: ServiceNow Bidirectional Sync

```
DLP Enforce                    ServiceNow
     |                              |
     |  1. Incident created         |
     |----------------------------->|  2. Security Incident auto-created
     |                              |
     |                              |  3. ServiceNow workflow assigns to team
     |                              |
     |                              |  4. Analyst resolves in ServiceNow
     |  5. Status synced back       |
     |<-----------------------------|
     |                              |
     |  (Status: Resolved)          |  (Closed with resolution notes)
```

**ServiceNow Integration Configuration:**
1. Install "Symantec DLP Incident Response" from ServiceNow Store
2. Configure connection: Enforce Server URL, API credentials
3. Set polling interval (default: 5 minutes)
4. Map DLP statuses to ServiceNow states
5. Map DLP custom attributes to ServiceNow fields
6. Enable bidirectional sync (ServiceNow -> DLP status updates)

### Pattern 3: Custom SOAR via REST API Polling

```bash
#!/bin/bash
# soar-poller.sh - Custom SOAR integration
# Runs every 2 minutes via cron

ENFORCE="https://enforce.corp.local"
CREDS="soar-svc:password"
LAST_CHECK_FILE="/var/soar/dlp-last-check.txt"

# Get timestamp of last check
LAST_CHECK=$(cat "$LAST_CHECK_FILE" 2>/dev/null || echo "2026-05-21T00:00:00Z")

# Query for new HIGH severity incidents since last check
INCIDENTS=$(curl -s -u "$CREDS" \
  -X POST \
  -H 'Content-Type: application/json' \
  -d "{
    \"savedReportId\": 0,
    \"incidentCreationDateGreaterThan\": \"$LAST_CHECK\",
    \"filters\": {
      \"filterType\": \"AND\",
      \"filters\": [
        {\"filterType\": \"booleanFilter\", \"filterName\": \"severity\", \"filterValue\": \"HIGH\"},
        {\"filterType\": \"booleanFilter\", \"filterName\": \"incidentStatusName\", \"filterValue\": \"New\"}
      ]
    }
  }" \
  "$ENFORCE/ProtectManager/webservices/v2/incidents")

# Process each new incident
echo "$INCIDENTS" | jq -r '.incidents[].incidentId' | while read ID; do
  # Get full details
  DETAIL=$(curl -s -u "$CREDS" "$ENFORCE/ProtectManager/webservices/v2/incidents/$ID")

  # Extract key fields
  POLICY=$(echo "$DETAIL" | jq -r '.policyName')
  SENDER=$(echo "$DETAIL" | jq -r '.sender')
  SEVERITY=$(echo "$DETAIL" | jq -r '.severity')

  # Send to SOAR webhook/API
  curl -s -X POST \
    -H 'Content-Type: application/json' \
    -d "{\"incident_id\": $ID, \"policy\": \"$POLICY\", \"sender\": \"$SENDER\", \"severity\": \"$SEVERITY\"}" \
    "https://soar.corp.local/api/webhooks/dlp-incident"

  # Mark as "In Process" in DLP
  curl -s -u "$CREDS" \
    -X PATCH \
    -H 'Content-Type: application/json' \
    -d "{\"incidents\": [{\"incidentId\": $ID, \"incidentStatusName\": \"In Process\", \"incidentNotes\": \"Routed to SOAR platform\"}]}" \
    "$ENFORCE/ProtectManager/webservices/v2/incidents"
done

# Update last check timestamp
date -u +"%Y-%m-%dT%H:%M:%SZ" > "$LAST_CHECK_FILE"
```

### Pattern 4: Incident SLA Breach Monitor

```bash
#!/bin/bash
# sla-monitor.sh - Escalate incidents that exceed SLA
# SLA: High severity must be triaged within 4 hours

ENFORCE="https://enforce.corp.local"
CREDS="soar-svc:password"
SLA_HOURS=4

# Calculate SLA cutoff (4 hours ago)
SLA_CUTOFF=$(date -u -v-${SLA_HOURS}H +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || \
  date -u -d "${SLA_HOURS} hours ago" +"%Y-%m-%dT%H:%M:%SZ")

# Find HIGH severity incidents older than SLA that are still "New"
BREACHED=$(curl -s -u "$CREDS" \
  -X POST \
  -H 'Content-Type: application/json' \
  -d "{
    \"savedReportId\": 0,
    \"incidentCreationDateLessThan\": \"$SLA_CUTOFF\",
    \"filters\": {
      \"filterType\": \"AND\",
      \"filters\": [
        {\"filterType\": \"booleanFilter\", \"filterName\": \"severity\", \"filterValue\": \"HIGH\"},
        {\"filterType\": \"booleanFilter\", \"filterName\": \"incidentStatusName\", \"filterValue\": \"New\"}
      ]
    }
  }" \
  "$ENFORCE/ProtectManager/webservices/v2/incidents")

# Escalate each breached incident
echo "$BREACHED" | jq -r '.incidents[].incidentId' | while read ID; do
  curl -s -u "$CREDS" \
    -X PATCH \
    -H 'Content-Type: application/json' \
    -d "{\"incidents\": [{
      \"incidentId\": $ID,
      \"incidentStatusName\": \"Escalated\",
      \"incidentNotes\": \"Auto-escalated: SLA breach (${SLA_HOURS}hr triage SLA exceeded)\"
    }]}" \
    "$ENFORCE/ProtectManager/webservices/v2/incidents"

  # Alert SOC manager
  curl -s -X POST "https://slack.com/api/chat.postMessage" \
    -H "Authorization: Bearer $SLACK_TOKEN" \
    -d "channel=soc-alerts&text=DLP SLA Breach: Incident #$ID has been open for >$SLA_HOURS hours"
done
```

---

## 8. REST API Complete Reference with Examples

### Authentication Setup

```bash
# Basic Authentication (most common)
export DLP_USER="api-user"
export DLP_PASS="api-password"
export DLP_HOST="https://enforce.corp.local"
export DLP_AUTH="$DLP_USER:$DLP_PASS"
export DLP_BASE="$DLP_HOST/ProtectManager/webservices/v2"
```

### Query Incidents with Complex Filters

```bash
# Find PCI incidents from the last 7 days with severity HIGH or CRITICAL
curl -s -u "$DLP_AUTH" \
  -X POST \
  -H 'Content-Type: application/json' \
  -d '{
    "savedReportId": 0,
    "incidentCreationDateGreaterThan": "2026-05-14T00:00:00Z",
    "filters": {
      "filterType": "AND",
      "filters": [
        {
          "filterType": "OR",
          "filters": [
            {"filterType": "booleanFilter", "filterName": "severity", "filterValue": "HIGH"},
            {"filterType": "booleanFilter", "filterName": "severity", "filterValue": "CRITICAL"}
          ]
        },
        {
          "filterType": "booleanFilter",
          "filterName": "policyName",
          "filterOperator": "CONTAINS",
          "filterValue": "PCI"
        }
      ]
    },
    "pageSize": 100,
    "pageNumber": 1
  }' \
  "$DLP_BASE/incidents" | jq '.'
```

### Get Incident with All Components

```bash
# Get incident details
curl -s -u "$DLP_AUTH" "$DLP_BASE/incidents/12345" | jq '.'

# Get matched content (policy violations, detected data)
curl -s -u "$DLP_AUTH" "$DLP_BASE/incidents/12345/components" | jq '.'

# Get full audit trail
curl -s -u "$DLP_AUTH" "$DLP_BASE/incidents/12345/history" | jq '.'

# Download original captured message/file
curl -s -u "$DLP_AUTH" -o incident_12345_original.eml \
  "$DLP_BASE/incidents/12345/originalMessage"
```

### Bulk Update Incidents

```bash
# Resolve all FALSE POSITIVE incidents older than 90 days
# Step 1: Query old FP incidents
OLD_FP=$(curl -s -u "$DLP_AUTH" \
  -X POST \
  -H 'Content-Type: application/json' \
  -d '{
    "savedReportId": 0,
    "incidentCreationDateLessThan": "2026-02-20T00:00:00Z",
    "filters": {
      "filterType": "booleanFilter",
      "filterName": "incidentStatusName",
      "filterValue": "False Positive"
    },
    "pageSize": 500
  }' \
  "$DLP_BASE/incidents")

# Step 2: Extract IDs and build update payload
IDS=$(echo "$OLD_FP" | jq '[.incidents[].incidentId]')

# Step 3: Bulk update (change to Resolved + add note)
echo "$IDS" | jq '{incidents: [.[] | {incidentId: ., incidentStatusName: "Resolved", incidentNotes: "Auto-archived: FP incident older than 90 days"}]}' | \
curl -s -u "$DLP_AUTH" \
  -X PATCH \
  -H 'Content-Type: application/json' \
  -d @- \
  "$DLP_BASE/incidents"
```

### List System Reference Data

```bash
# Get all available incident statuses
curl -s -u "$DLP_AUTH" "$DLP_BASE/incidents/incidentStatuses" | jq '.'

# Get all custom attribute definitions
curl -s -u "$DLP_AUTH" "$DLP_BASE/incidents/listCustomAttributes" | jq '.'

# Get editable incident fields
curl -s -u "$DLP_AUTH" "$DLP_BASE/incidents/incidentEditable" | jq '.'

# Get prevent action status values
curl -s -u "$DLP_AUTH" "$DLP_BASE/incidents/preventActionStatuses" | jq '.'

# Get protect action status values (discover remediation)
curl -s -u "$DLP_AUTH" "$DLP_BASE/incidents/protectActionStatuses" | jq '.'
```

### Export Incidents

```bash
# Export all incidents from May 2026 as JSON
curl -s -u "$DLP_AUTH" \
  -X POST \
  -H 'Content-Type: application/json' \
  -d '{
    "incidentCreationDateGreaterThan": "2026-05-01T00:00:00Z",
    "incidentCreationDateLessThan": "2026-05-31T23:59:59Z"
  }' \
  "$DLP_BASE/incidents/export" > may-2026-incidents.json
```

### Sender/Recipient Pattern Management

```bash
# Create a reusable sender/recipient pattern
curl -s -u "$DLP_AUTH" \
  -X POST \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "External Finance Partners",
    "type": "RECIPIENT",
    "patterns": [
      "*@audit-firm.com",
      "*@accounting-partner.com",
      "*@tax-advisor.com"
    ]
  }' \
  "$DLP_BASE/senderRecipientPattern"

# Get pattern details
curl -s -u "$DLP_AUTH" "$DLP_BASE/senderRecipientPattern/5" | jq '.'

# Update pattern
curl -s -u "$DLP_AUTH" \
  -X PUT \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "External Finance Partners (Updated)",
    "patterns": [
      "*@audit-firm.com",
      "*@accounting-partner.com",
      "*@tax-advisor.com",
      "*@new-partner.com"
    ]
  }' \
  "$DLP_BASE/senderRecipientPattern/5"
```

---

## 9. SIEM Integration: Syslog and CEF

### CEF Message Format for DLP Incidents

```
CEF:0|Broadcom|Data Loss Prevention|16.0|{ruleId}|{policyName}|{cefSeverity}|
  INCIDENT_ID={incidentId}
  POLICY={policyName}
  RULES={matchedRules}
  SEVERITY={severity}
  BLOCKED={preventActionStatus}
  APPLICATION_USER={endpointUser}
  ENDPOINT_MACHINE={endpointMachine}
  ENDPOINT_USERNAME={endpointUser}
  MACHINE_IP={machineIp}
  FILE_NAME={fileName}
  RECIPIENTS={recipients}
  SENDER={sender}
  SUBJECT={subject}
  MATCH_COUNT={matchCount}
  PROTOCOL={protocol}
```

### Configuring Syslog Response Rule

1. Navigate to **Manage > Policies > Response Rules > Add > Automated Response**
2. Add Action: **Log to a Syslog Server**
3. Configure:

| Field | Value |
|-------|-------|
| Host | `siem.corp.local` |
| Port | 514 |
| Protocol | TCP (recommended for reliability) |
| Facility | LOCAL0 |
| Level | WARNING (or map to severity) |
| Message | CEF format template (above) |

### SIEM-Specific Configuration

| SIEM | Connector Type | Setup |
|------|---------------|-------|
| Splunk | Splunk Add-on for Symantec DLP | Install add-on; configure syslog input; DLP-specific dashboards included |
| Microsoft Sentinel | CEF via AMA connector | Configure syslog forwarder; Sentinel parses CEF automatically |
| Google Chronicle | Native Symantec DLP parser | Forward syslog; Chronicle auto-parses DLP events |
| QRadar (JSA) | Juniper JSA DSM for Symantec DLP | Install DSM; configure syslog source; auto-normalization |
| LogRhythm | Syslog CEF parser | Configure syslog input; LogRhythm parses CEF fields |
| ManageEngine EventLog | Built-in Symantec DLP support | Configure syslog input; pre-built reports available |

---

## 10. Incident Workflows (DLP 26.1)

### Overview

DLP 26.1 introduces a native **Incident Workflow** engine that replaces or supplements manual status transitions with automated, configurable workflow logic.

### Capabilities

| Feature | Description |
|---------|-------------|
| Task Scheduling | Define automated tasks at lifecycle milestones |
| Conditional Routing | Route incidents based on severity, policy, custom attributes |
| Time-Based Escalation | Auto-escalate after configurable time thresholds |
| Assignment Rules | Auto-assign based on incident characteristics |
| Notification Chains | Sequenced notifications (immediate, 24hr reminder, 72hr escalation) |

### Configuration

**Navigation:** System > Incident Workflows (DLP 26.1+)

### Example Workflow: PCI Incident Triage

```
[New Incident] --> [Severity = HIGH?]
    |                    |
    | No                 | Yes
    v                    v
[Assign to           [Assign to PCI Team]
 General Queue]      [Send Alert Email]
    |                    |
    v                    v
[Wait 24 hours]      [Wait 4 hours]
    |                    |
    v                    v
[If still New:       [If still New:
 Send Reminder]       Escalate to Manager]
    |                    |
    v                    v
[Wait 72 hours]      [Wait 24 hours]
    |                    |
    v                    v
[If still open:      [If still open:
 Auto-escalate]       Alert CISO]
```

---

## 11. Performance Optimization

### Incident Query Performance

| Issue | Solution |
|-------|----------|
| Slow incident list loading | Use more specific filters; reduce date range; use saved searches |
| Dashboard timeout | Reduce number of dashboard widgets (max 12 in 26.1, 6 in prior) |
| API query timeout | Reduce page size; add more filter conditions; paginate results |
| Report generation slow | Schedule reports for off-hours; reduce date range; use CSV not PDF |

### Database Optimization

| Optimization | Description |
|-------------|-------------|
| Oracle statistics | Run `DBMS_STATS.GATHER_SCHEMA_STATS` weekly |
| Index maintenance | Rebuild fragmented indexes monthly |
| Tablespace management | Monitor tablespace usage; extend before 80% |
| Archival | Export and purge incidents older than retention period |
| Partitioning | Partition incident table by date (Oracle Enterprise) |

---

## 12. Incident Retention and Archival

### Retention Strategy

| Data Type | Recommended Retention | Rationale |
|-----------|----------------------|-----------|
| High severity incidents | 3-7 years | Regulatory compliance (PCI: 1 year, HIPAA: 6 years) |
| Medium severity incidents | 1-2 years | Trend analysis, pattern detection |
| Low/Info incidents | 90-180 days | Operational context; purge regularly |
| Discovery incidents | 180 days - 1 year | Compliance evidence; refresh with next scan |
| False positive incidents | 90 days | Policy tuning reference; purge after tuning cycle |
| Evidence (original messages) | 90-365 days | Forensic use; storage-intensive |
| Audit trail | 3-7 years | Regulatory requirement; minimal storage impact |

### Automated Retention with Response Rules

```
Response Rule: "Limit Data Retention - Low Severity"
  Condition: Severity = Low OR Severity = Informational
  Action: Limit Incident Data Retention
    Retain evidence for: 90 days
    After retention: Delete evidence, keep metadata

Response Rule: "Limit Data Retention - Discovery"
  Condition: Detection Server Type = DISCOVER
  Action: Limit Incident Data Retention
    Retain evidence for: 180 days
    After retention: Delete evidence, keep metadata
```

### API-Based Archival

```bash
#!/bin/bash
# archive-incidents.sh - Export and flag old resolved incidents
# Run monthly

ENFORCE="https://enforce.corp.local"
CREDS="api-user:password"
ARCHIVE_DIR="/data/dlp-archives"
CUTOFF=$(date -u -v-180d +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || \
  date -u -d "180 days ago" +"%Y-%m-%dT%H:%M:%SZ")

# Export resolved incidents older than 180 days
curl -s -u "$CREDS" \
  -X POST \
  -H 'Content-Type: application/json' \
  -d "{
    \"savedReportId\": 0,
    \"incidentCreationDateLessThan\": \"$CUTOFF\",
    \"filters\": {
      \"filterType\": \"booleanFilter\",
      \"filterName\": \"incidentStatusName\",
      \"filterValue\": \"Resolved\"
    }
  }" \
  "$ENFORCE/ProtectManager/webservices/v2/incidents/export" \
  > "$ARCHIVE_DIR/archived-incidents-$(date +%Y%m).json"

echo "Archive complete: $ARCHIVE_DIR/archived-incidents-$(date +%Y%m).json"
```

---

## 13. Troubleshooting Reference

### Common Issues

| Symptom | Cause | Resolution |
|---------|-------|------------|
| No incidents appearing | No active policy; detection server offline; wrong policy group | Verify policy is enabled and deployed to running detection server |
| Incidents created but no notification | SMTP not configured; response rule missing email action | Check System > Settings > General for SMTP config |
| Smart Response button grayed out | User role lacks "Execute Smart Response" privilege | Update role privileges |
| API returns 401 Unauthorized | Wrong credentials or user lacks API role | Verify user has "Incident Reporting API" role |
| API returns 403 Forbidden | User authenticated but lacks permission for this operation | Check role privileges for the specific API operation |
| Incident detail shows "Content Not Available" | Evidence was purged by retention rule; or incident was metadata-only | Expected if retention rule removed evidence |
| Syslog messages not reaching SIEM | Firewall blocking; wrong port/protocol; syslog not configured | Verify connectivity; test with netcat |
| ServiceNow sync stopped | API credentials changed; connection timeout; ServiceNow maintenance | Re-verify connection; check ServiceNow integration logs |
| Custom attributes not populating | Lookup plugin misconfigured; LDAP connection failed; attribute name mismatch | Verify plugin config; test LDAP connection; match attribute names exactly |

### Log Files for Incident Management

| Log | Location | Content |
|-----|----------|---------|
| Incident processing | `<install>/Protect/logs/debug/IncidentPersister.log` | Incident creation and persistence |
| Response rule execution | `<install>/Protect/logs/debug/ResponseRuleLog.log` | Response rule evaluation and action execution |
| Email notification | `<install>/Protect/logs/debug/SmtpLog.log` | Email sending for notifications |
| API requests | `<install>/Protect/logs/debug/RestApiLog.log` | REST API request/response logging |
| Lookup plugin | `<install>/Protect/logs/debug/LookupPluginLog.log` | Plugin execution and LDAP queries |

---

*End of advanced incident management guide. Total coverage: 13 field categories, 7+ response action types, 4 SOAR integration patterns, 13 API endpoints with curl examples, CEF/syslog configuration, and troubleshooting reference.*
