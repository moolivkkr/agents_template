# Advanced: Compliance Reporting

> **Scope:** All report types, custom report builder fields, dashboard configuration, SIEM format, API-based reporting, regulatory examples
> **Versions:** DLP 16.0 through 26.1
> **Sources:** [S1] Help Center 16.0, [S2] Help Center 25.1, [S3] Help Center 26.1, [S4] Full PDF 16.0, API Intelligence Report, SIEM connector documentation

---

## Table of Contents

1. [Report Types Reference](#1-report-types-reference)
2. [Custom Report Builder Deep Dive](#2-custom-report-builder-deep-dive)
3. [Dashboard Configuration Reference](#3-dashboard-configuration-reference)
4. [SIEM Integration: CEF Format and Variables](#4-siem-integration-cef-format-and-variables)
5. [Audit Log Reporting](#5-audit-log-reporting)
6. [System Event Reporting](#6-system-event-reporting)
7. [API-Based Reporting Patterns](#7-api-based-reporting-patterns)
8. [Regulatory Compliance Report Templates](#8-regulatory-compliance-report-templates)
9. [Data Discovery Reporting](#9-data-discovery-reporting)
10. [Executive Reporting Patterns](#10-executive-reporting-patterns)
11. [Report Archival and Retention](#11-report-archival-and-retention)
12. [Advanced SIEM Configurations](#12-advanced-siem-configurations)
13. [Troubleshooting](#13-troubleshooting)

---

## 1. Report Types Reference

### Incident-Based Reports

| Report Type | Data Source | Grouping Options | Use Case |
|-------------|-----------|-----------------|----------|
| Policy Summary | Incidents | By policy name | Which policies generate the most violations |
| Severity Distribution | Incidents | By severity level | Risk posture overview |
| User/Sender Summary | Incidents | By sender/user | Top violators, training candidates |
| Channel Distribution | Incidents | By protocol/channel | Where data moves (email, web, USB) |
| Status Summary | Incidents | By incident status | Workflow efficiency (open vs. resolved) |
| Trend Analysis | Incidents | By time period (day/week/month) | Program effectiveness over time |
| Custom Attribute Report | Incidents | By any custom attribute | Department, cost center, regulatory scope |
| Match Count Distribution | Incidents | By match count ranges | Severity of violations (1 match vs. 100 matches) |
| Detection Server Report | Incidents | By detection server | Server utilization and effectiveness |
| Remediation Status | Incidents | By remediation status | Remediation progress tracking |

### System-Based Reports

| Report Type | Data Source | Navigation | Use Case |
|-------------|-----------|------------|----------|
| Server Health | System events | System > Servers and Detectors > Events | Detection server uptime and errors |
| Agent Status | Agent telemetry | System > Agents > Overview | Endpoint agent deployment coverage |
| Scan Status | Discover scan data | Manage > Discover > Discover Targets | Discovery scan completion and findings |
| Audit Log | Admin actions | System > Servers and Detectors > Audit Logs | Change management and compliance |
| System Alerts | System events | System > Servers and Detectors > Events > Alerts | Proactive infrastructure monitoring |

### Discovery-Specific Reports

| Report Type | Data Source | Content | Use Case |
|-------------|-----------|---------|----------|
| Data Inventory | Discover incidents | Sensitive data locations by server, share, path | Data classification inventory |
| Scan Coverage | Discover targets | Which targets have been scanned, when, what was found | Coverage gap analysis |
| Remediation Tracking | Protect actions | Files quarantined, encrypted, labeled, and their status | Remediation evidence |
| Data Growth Trend | Discover incidents over time | How sensitive data volume changes across scans | Risk trend for data at rest |

---

## 2. Custom Report Builder Deep Dive

### Filter Field Reference

Complete list of filterable fields for building custom reports:

| Category | Filter Field | Operators | Type |
|----------|-------------|-----------|------|
| **Date** | Incident Creation Date | Greater Than, Less Than, Between | Date/Time |
| **Date** | Detection Date | Greater Than, Less Than, Between | Date/Time |
| **Date** | Last Modified Date | Greater Than, Less Than, Between | Date/Time |
| **Severity** | Severity Level | Equals, In List | Enum (1-4) |
| **Status** | Incident Status | Equals, In List, Not Equals | Enum |
| **Policy** | Policy Name | Equals, Contains, Starts With | String |
| **Policy** | Policy Group | Equals | String |
| **Policy** | Rule Name | Contains | String |
| **Detection** | Detection Server | Equals | String |
| **Detection** | Detection Server Type | Equals, In List | Enum (Network, Endpoint, Discover) |
| **Detection** | Protocol | Equals, In List | Enum (SMTP, HTTP, FTP, USB, etc.) |
| **People** | Sender/User | Equals, Contains, Starts With, Ends With | String |
| **People** | Recipient | Equals, Contains, Starts With, Ends With | String |
| **People** | Endpoint User | Equals, Contains | String |
| **People** | Endpoint Hostname | Equals, Contains | String |
| **Content** | Match Count | Greater Than, Less Than, Between | Integer |
| **Content** | File Name | Contains, Ends With | String |
| **Content** | File Type | Equals, In List | String |
| **Content** | Subject | Contains | String |
| **Network** | Source IP | Equals, Starts With | String |
| **Remediation** | Prevent Action Status | Equals | Enum (Blocked, Allowed, etc.) |
| **Remediation** | Protect Action Status | Equals | Enum (Quarantined, Encrypted, etc.) |
| **Remediation** | Remediation Status | Equals | Enum |
| **Custom** | Any Custom Attribute | Equals, Contains | Varies |

### Grouping and Aggregation

Reports can be grouped by any field above. Grouping creates summaries:

| Group By | Result |
|----------|--------|
| Policy Name | One row per policy with incident count |
| Severity | One row per severity level with count |
| Sender | One row per user with incident count |
| Department (custom attr) | One row per department with count |
| Protocol | One row per channel with count |
| Week/Month | One row per time period with count (trend data) |

### Column Configuration

**Available columns for incident reports:**
```
+------------------------------------------------------------------+
| Column Configuration                                              |
+------------------------------------------------------------------+
| Available Columns          | Selected Columns (drag to reorder)  |
| -------------------------  | ----------------------------------- |
| [ ] Incident ID            | [x] Incident ID                    |
| [ ] Creation Date          | [x] Creation Date                  |
| [ ] Severity               | [x] Severity                       |
| [ ] Status                 | [x] Status                         |
| [ ] Policy Name            | [x] Policy Name                    |
| [ ] Match Count            | [x] Match Count                    |
| [ ] Sender                 | [x] Sender                         |
| [ ] Recipient              | [x] Recipient                      |
| [ ] Protocol               | [ ] File Name                      |
| [ ] File Name              | [ ] Detection Server               |
| [ ] Detection Server       | [ ] Endpoint User                  |
| [ ] Endpoint User          | [ ] Endpoint Hostname              |
| [ ] Endpoint Hostname      | [ ] Prevent Action                 |
| [ ] Prevent Action         | [ ] Remediation Status             |
| [ ] Protect Action         | [ ] Custom: Department             |
| [ ] Remediation Status     | [ ] Custom: Regulatory Scope       |
| [ ] Source IP               |                                    |
| [ ] Subject                |                                    |
| [ ] Custom: Department     |                                    |
| [ ] Custom: Regulatory...  |                                    |
+------------------------------------------------------------------+
```

### Saved Report Templates for Common Use Cases

**Template 1: PCI Quarterly Compliance**
```
Filters:
  Date: [Quarter start] to [Quarter end]
  Policy: Contains "PCI"
  Severity: All
Columns: ID, Date, Severity, Status, Policy, Sender, Recipient, Match Count, Prevent Action
Group By: Severity
Sort: Date descending
Schedule: Monthly, 1st of month, email to compliance@corp.com
```

**Template 2: Weekly Operations Summary**
```
Filters:
  Date: Last 7 days
  Severity: High, Medium
  Status: All
Columns: ID, Date, Severity, Status, Policy, Sender, Protocol, Prevent Action
Group By: Status
Sort: Severity ascending (High first)
Schedule: Weekly, Monday 7 AM, email to dlp-team@corp.com
```

**Template 3: User Risk Report**
```
Filters:
  Date: Last 30 days
  Match Count: Greater than 5
Columns: Sender, Department (custom), Total Incidents, High Count, Policies Triggered
Group By: Sender
Sort: Total Incidents descending
Schedule: Monthly, email to hr-security@corp.com
```

**Template 4: Discovery Data Inventory**
```
Filters:
  Detection Server Type: DISCOVER
  Date: Last scan cycle
  Severity: High, Medium
Columns: File Path, Policy, Severity, Match Count, File Owner, Protect Action, Remediation Status
Group By: Policy
Sort: Match Count descending
Schedule: After each quarterly scan, email to data-governance@corp.com
```

---

## 3. Dashboard Configuration Reference

### Dashboard Layout Options

DLP 26.1 dashboard grid:
```
+-------+-------+-------+-------+
|       |       |       |       |
|  W1   |  W2   |  W3   |  W4   |
|       |       |       |       |
+-------+-------+-------+-------+
|       |       |       |       |
|  W5   |  W6   |  W7   |  W8   |
|       |       |       |       |
+-------+-------+-------+-------+
|       |       |       |       |
|  W9   |  W10  |  W11  |  W12  |
|       |       |       |       |
+-------+-------+-------+-------+
```

### Chart Type Options (DLP 26.1)

| Chart Type | Best For | Example |
|-----------|---------|---------|
| Bar (vertical) | Comparing categories | Incidents by policy |
| Bar (horizontal) | Ranking/top-N lists | Top 10 users by incident count |
| Pie | Proportional distribution | Severity distribution (% per level) |
| Line | Trends over time | Monthly incident trend |
| Table | Detailed data | Open incidents with all fields |
| Donut | Similar to pie, with center metric | Channel distribution with total count in center |

### Pre-Built Dashboard Configurations

**Executive Risk Dashboard:**
```
Widget 1: Severity Distribution (Pie) -- "Incident Risk Levels"
  Source: All incidents, last 90 days, grouped by severity

Widget 2: Monthly Trend (Line) -- "Incident Volume Trend"
  Source: All incidents, last 12 months, grouped by month

Widget 3: Top Policies (Horizontal Bar) -- "Most Violated Policies"
  Source: All incidents, last 90 days, grouped by policy, top 10

Widget 4: Channel Distribution (Donut) -- "How Data Moves"
  Source: All incidents, last 90 days, grouped by protocol

Widget 5: Resolution Rate (Bar) -- "Incident Outcomes"
  Source: All incidents, last 90 days, grouped by status

Widget 6: Top Users (Table) -- "Highest Risk Users"
  Source: All incidents, last 90 days, grouped by sender, top 20
```

**PCI Compliance Dashboard:**
```
Widget 1: PCI Monthly Trend (Line)
  Source: PCI policy incidents, last 12 months

Widget 2: PCI Severity (Pie)
  Source: PCI incidents, current quarter

Widget 3: PCI by Channel (Bar)
  Source: PCI incidents, current quarter, by protocol

Widget 4: PCI Discovery Locations (Table)
  Source: PCI discover incidents, last scan

Widget 5: PCI Remediation Status (Bar)
  Source: PCI incidents with remediation, current quarter

Widget 6: PCI Blocked vs Allowed (Pie)
  Source: PCI incidents, current quarter, by prevent action status
```

**SOC Operations Dashboard:**
```
Widget 1: Open Incidents by Severity (Stacked Bar)
  Source: Status = New or In Process, last 7 days

Widget 2: SLA Status (Table)
  Source: Open incidents older than SLA threshold

Widget 3: Analyst Workload (Horizontal Bar)
  Source: In Process incidents, grouped by assigned analyst

Widget 4: Incidents Per Day (Line)
  Source: All incidents, last 30 days, grouped by day

Widget 5: False Positive Rate (Line)
  Source: All incidents, last 30 days, percentage marked False Positive by policy

Widget 6: Channel Activity (Bar)
  Source: All incidents, last 7 days, by channel
```

---

## 4. SIEM Integration: CEF Format and Variables

### Complete CEF Variable Reference

| Variable | Description | Example Value |
|----------|-------------|---------------|
| `$INCIDENT_ID$` | Unique incident identifier | 12345 |
| `$POLICY$` | Policy name that triggered | "PCI DSS - Credit Card Numbers" |
| `$RULES$` | Detection rules that matched | "Content Matches Data Identifier (Credit Card - Luhn)" |
| `$SEVERITY$` | DLP severity level | "High" |
| `$BLOCKED$` | Whether the action was blocked | "true" / "false" |
| `$APPLICATION_USER$` | Application-level user identity | "john.smith" |
| `$ENDPOINT_MACHINE$` | Endpoint hostname | "LAPTOP-JS01" |
| `$ENDPOINT_USERNAME$` | Endpoint OS username | "CORP\\john.smith" |
| `$MACHINE_IP$` | Source machine IP address | "10.0.1.42" |
| `$FILE_NAME$` | File that triggered the violation | "Q1-Payments.xlsx" |
| `$RECIPIENTS$` | Recipient(s) of the data | "auditor@external.com" |
| `$SENDER$` | Sender/source of the data | "john.smith@corp.com" |
| `$SUBJECT$` | Email subject or document title | "Q1 Payment Records" |
| `$MATCH_COUNT$` | Number of content matches | "3" |
| `$PROTOCOL$` | Detection protocol/channel | "SMTP" |
| `$DETECTION_SERVER$` | Name of detection server | "email-prevent-01" |
| `$INCIDENT_STATUS$` | Current incident status | "New" |
| `$INCIDENT_CREATION_DATE$` | When incident was created | "2026-05-21T14:32:07Z" |

### CEF Template Examples

**Basic CEF for Splunk:**
```
CEF:0|Broadcom|Data Loss Prevention|16.0|$RULES$|$POLICY$|$SEVERITY$|
  act=$BLOCKED$
  src=$MACHINE_IP$
  suser=$SENDER$
  duser=$RECIPIENTS$
  fname=$FILE_NAME$
  msg=$SUBJECT$
  cn1=$INCIDENT_ID$
  cn1Label=IncidentID
  cn2=$MATCH_COUNT$
  cn2Label=MatchCount
  cs1=$PROTOCOL$
  cs1Label=Protocol
  cs2=$ENDPOINT_MACHINE$
  cs2Label=EndpointMachine
```

**Extended CEF for QRadar:**
```
CEF:0|Broadcom|Symantec DLP|16.0|$INCIDENT_ID$|$POLICY$|$SEVERITY$|
  act=$BLOCKED$
  src=$MACHINE_IP$
  suser=$SENDER$
  duser=$RECIPIENTS$
  fname=$FILE_NAME$
  msg=$POLICY$ violation: $MATCH_COUNT$ matches found in $FILE_NAME$ via $PROTOCOL$
  cn1=$INCIDENT_ID$
  cn1Label=DLP_IncidentID
  cn2=$MATCH_COUNT$
  cn2Label=DLP_MatchCount
  cs1=$PROTOCOL$
  cs1Label=DLP_Channel
  cs2=$ENDPOINT_MACHINE$
  cs2Label=DLP_Hostname
  cs3=$ENDPOINT_USERNAME$
  cs3Label=DLP_Username
  cs4=$DETECTION_SERVER$
  cs4Label=DLP_DetectionServer
  cs5=$INCIDENT_STATUS$
  cs5Label=DLP_Status
  deviceCustomDate1=$INCIDENT_CREATION_DATE$
  deviceCustomDate1Label=DLP_IncidentDate
```

### Syslog Configuration for Multiple Severity Levels

Create separate response rules for different severity levels to route to different SIEM severity levels:

**Rule 1: High Severity -> Syslog CRITICAL**
```
Condition: Severity = High
Action: Log to Syslog
  Host: siem.corp.local
  Port: 514
  Protocol: TCP
  Level: CRITICAL
  Message: [CEF template with $SEVERITY$=High]
```

**Rule 2: Medium Severity -> Syslog WARNING**
```
Condition: Severity = Medium
Action: Log to Syslog
  Host: siem.corp.local
  Port: 514
  Protocol: TCP
  Level: WARNING
  Message: [CEF template with $SEVERITY$=Medium]
```

**Rule 3: Low Severity -> Syslog INFO**
```
Condition: Severity = Low
Action: Log to Syslog
  Host: siem.corp.local
  Port: 514
  Protocol: TCP
  Level: INFO
  Message: [CEF template with $SEVERITY$=Low]
```

---

## 5. Audit Log Reporting

### Audit Log Contents

**Navigation:** System > Servers and Detectors > Audit Logs

| Event Type | What Is Logged | Compliance Relevance |
|------------|---------------|---------------------|
| Policy Created | Who, when, policy name, initial config | SOX: change management evidence |
| Policy Modified | Who, when, what changed | SOX: change approval documentation |
| Policy Enabled/Disabled | Who, when, policy name | Coverage gap documentation |
| Policy Deployed | Who, when, target servers | Deployment verification |
| Response Rule Changed | Who, when, rule details | Response configuration audit |
| Role Created/Modified | Who, when, role config | Access control documentation |
| User Created/Modified | Who, when, user details | Account management audit |
| Incident Status Changed | Who, when, from/to status | Incident handling documentation |
| Incident Viewed | Who, when, incident ID | Evidence access tracking |
| Report Generated | Who, when, report name | Report access audit |
| System Setting Changed | Who, when, setting details | Configuration change management |

### Exporting Audit Logs

**Console Export:**
1. Navigate to System > Servers and Detectors > Audit Logs
2. Set date range filter
3. Click **Export** -> CSV

**API Export (DLP 16.0 RU1+):**
```bash
# Export audit logs for Q1 2026
curl -s -u 'admin:password' \
  'https://enforce.corp.local/ProtectManager/webservices/v2/auditLogs?startDate=2026-01-01&endDate=2026-03-31' \
  > audit-log-q1-2026.json
```

### Audit Log Syslog Forwarding

Forward audit logs to SIEM in real-time:

**Configuration:** System > Servers and Detectors > Audit Logs > Syslog Configuration

| Setting | Value |
|---------|-------|
| Enable | Yes |
| Host | siem.corp.local |
| Port | 514 |
| Protocol | TCP |
| Format | CEF |

This ensures every admin action is forwarded to SIEM for correlation, alerting, and long-term retention.

---

## 6. System Event Reporting

### System Event Types

**Navigation:** System > Servers and Detectors > Events

| Event Category | Examples | Monitoring Value |
|---------------|---------|-----------------|
| Server Health | Detection server offline/online, heartbeat failure | Availability SLA |
| Agent Health | Agent disconnected, agent update failed | Endpoint coverage |
| Scan Status | Discovery scan started/completed/failed | Scan monitoring |
| Capacity | Queue depth exceeding threshold, disk space low | Capacity planning |
| Authentication | Login failed, login succeeded, account locked | Security monitoring |
| Policy Deployment | Policy pushed to servers, deployment failed | Policy coverage |

### Configuring System Event Alerts

1. Navigate to System > Servers and Detectors > Events
2. Click **Alert Configuration**
3. Define alert rules:

| Alert | Condition | Action |
|-------|-----------|--------|
| Detection Server Down | Server heartbeat missed for 10 minutes | Email to dlp-ops@corp.com |
| Agent Disconnect Spike | > 100 agents disconnect in 1 hour | Email to dlp-ops@corp.com |
| Scan Failure | Discovery scan fails | Email to scan-admin@corp.com |
| Disk Space Warning | Enforce server disk < 20% free | Email to it-ops@corp.com |
| Login Failure | > 5 failed logins in 10 minutes | Email to security@corp.com |

### Saved System Reports

1. Navigate to System > Servers and Detectors > Events
2. Set filters (date range, event type, server)
3. Click **Save** to create a saved system report
4. Schedule for automatic delivery (same mechanism as incident reports)

---

## 7. API-Based Reporting Patterns

### Pattern 1: Daily Executive Summary Email

```bash
#!/bin/bash
# daily-executive-summary.sh
# Generates a daily summary and sends via email

ENFORCE="https://enforce.corp.local"
CREDS="report-svc:password"
TODAY=$(date -u +"%Y-%m-%dT00:00:00Z")
YESTERDAY=$(date -u -v-1d +"%Y-%m-%dT00:00:00Z" 2>/dev/null || \
  date -u -d "yesterday" +"%Y-%m-%dT00:00:00Z")

# Query yesterday's incidents
RESULT=$(curl -s -u "$CREDS" \
  -X POST \
  -H 'Content-Type: application/json' \
  -d "{
    \"savedReportId\": 0,
    \"incidentCreationDateGreaterThan\": \"$YESTERDAY\",
    \"incidentCreationDateLessThan\": \"$TODAY\",
    \"pageSize\": 10000
  }" \
  "$ENFORCE/ProtectManager/webservices/v2/incidents")

# Calculate summary metrics
TOTAL=$(echo "$RESULT" | jq '.incidents | length')
HIGH=$(echo "$RESULT" | jq '[.incidents[] | select(.severity == "HIGH")] | length')
BLOCKED=$(echo "$RESULT" | jq '[.incidents[] | select(.preventActionStatus == "BLOCKED")] | length')

# Generate HTML email
cat <<EOF | mail -s "DLP Daily Summary - $(date +%Y-%m-%d)" ciso@corp.com
<html>
<h2>DLP Daily Summary</h2>
<table border="1" cellpadding="8">
<tr><td><b>Total Incidents</b></td><td>$TOTAL</td></tr>
<tr><td><b>High Severity</b></td><td>$HIGH</td></tr>
<tr><td><b>Blocked Actions</b></td><td>$BLOCKED</td></tr>
</table>
<p><a href="$ENFORCE/ProtectManager">View in Console</a></p>
</html>
EOF
```

### Pattern 2: Compliance Dashboard Data Feed

```bash
#!/bin/bash
# compliance-dashboard-feed.sh
# Generates JSON data for an external compliance dashboard (Grafana, Power BI, etc.)

ENFORCE="https://enforce.corp.local"
CREDS="report-svc:password"
OUTPUT_DIR="/data/dashboards"

# PCI metrics
PCI_30D=$(curl -s -u "$CREDS" \
  -X POST -H 'Content-Type: application/json' \
  -d "{
    \"savedReportId\": 0,
    \"incidentCreationDateGreaterThan\": \"$(date -u -v-30d +%Y-%m-%dT00:00:00Z)\",
    \"filters\": {\"filterType\": \"booleanFilter\", \"filterName\": \"policyName\", \"filterOperator\": \"CONTAINS\", \"filterValue\": \"PCI\"}
  }" \
  "$ENFORCE/ProtectManager/webservices/v2/incidents")

PCI_COUNT=$(echo "$PCI_30D" | jq '.incidents | length')
PCI_HIGH=$(echo "$PCI_30D" | jq '[.incidents[] | select(.severity == "HIGH")] | length')
PCI_RESOLVED=$(echo "$PCI_30D" | jq '[.incidents[] | select(.incidentStatusName == "Resolved")] | length')

# Output as JSON for dashboard consumption
jq -n \
  --arg date "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --argjson pci_total "$PCI_COUNT" \
  --argjson pci_high "$PCI_HIGH" \
  --argjson pci_resolved "$PCI_RESOLVED" \
  '{
    timestamp: $date,
    pci: {
      total_30d: $pci_total,
      high_severity_30d: $pci_high,
      resolved_30d: $pci_resolved,
      resolution_rate: (if $pci_total > 0 then ($pci_resolved * 100 / $pci_total) else 0 end)
    }
  }' > "$OUTPUT_DIR/compliance-metrics.json"
```

### Pattern 3: Monthly Trend Report Generation

```bash
#!/bin/bash
# monthly-trend.sh
# Generates 12-month trend data for each regulation

ENFORCE="https://enforce.corp.local"
CREDS="report-svc:password"

for REGULATION in PCI HIPAA GDPR SOX; do
  echo "Generating trend for $REGULATION..."
  echo "Month,Total,High,Medium,Low,Blocked,Resolved" > "/reports/${REGULATION}-12month-trend.csv"

  for MONTH_OFFSET in $(seq 11 -1 0); do
    MONTH_START=$(date -u -v-${MONTH_OFFSET}m -v1d +"%Y-%m-01T00:00:00Z" 2>/dev/null)
    MONTH_END=$(date -u -v-${MONTH_OFFSET}m -v1d -v+1m -v-1d +"%Y-%m-%dT23:59:59Z" 2>/dev/null)
    MONTH_LABEL=$(date -u -v-${MONTH_OFFSET}m +"%Y-%m" 2>/dev/null)

    RESULT=$(curl -s -u "$CREDS" \
      -X POST -H 'Content-Type: application/json' \
      -d "{
        \"savedReportId\": 0,
        \"incidentCreationDateGreaterThan\": \"$MONTH_START\",
        \"incidentCreationDateLessThan\": \"$MONTH_END\",
        \"filters\": {\"filterType\": \"booleanFilter\", \"filterName\": \"policyName\", \"filterOperator\": \"CONTAINS\", \"filterValue\": \"$REGULATION\"},
        \"pageSize\": 10000
      }" \
      "$ENFORCE/ProtectManager/webservices/v2/incidents")

    TOTAL=$(echo "$RESULT" | jq '.incidents | length')
    HIGH=$(echo "$RESULT" | jq '[.incidents[] | select(.severity == "HIGH")] | length')
    MEDIUM=$(echo "$RESULT" | jq '[.incidents[] | select(.severity == "MEDIUM")] | length')
    LOW=$(echo "$RESULT" | jq '[.incidents[] | select(.severity == "LOW")] | length')
    BLOCKED=$(echo "$RESULT" | jq '[.incidents[] | select(.preventActionStatus == "BLOCKED")] | length')
    RESOLVED=$(echo "$RESULT" | jq '[.incidents[] | select(.incidentStatusName == "Resolved")] | length')

    echo "$MONTH_LABEL,$TOTAL,$HIGH,$MEDIUM,$LOW,$BLOCKED,$RESOLVED" >> "/reports/${REGULATION}-12month-trend.csv"
  done
done
```

---

## 8. Regulatory Compliance Report Templates

### PCI DSS Audit Report Package

**Required components:**

| Component | Source | Format | Evidence For |
|-----------|--------|--------|-------------|
| PCI Incident Summary | Incident query: Policy contains "PCI" | CSV/PDF | Req 12.10 -- Incident response |
| PCI Discovery Findings | Discover incidents: PCI policies | CSV | Req 3.1 -- Data-at-rest protection |
| PCI Remediation Evidence | Protect action results | CSV | Req 3.4 -- Render PAN unreadable |
| PCI Block Evidence | Email/Web block actions | CSV | Req 4.1 -- Encrypt in transit |
| Policy Configuration | Policy XML export | XML | Req 12.1 -- Security policy |
| Audit Log | Admin actions on PCI policies | CSV | Req 10.2 -- Track access |
| Agent Coverage | Endpoint agent deployment | CSV | Req 5.2 -- Anti-malware/DLP coverage |

**Generation script:**
```bash
#!/bin/bash
# pci-audit-package.sh
QUARTER="Q1-2026"
ENFORCE="https://enforce.corp.local"
CREDS="audit-svc:password"
OUT="/reports/pci-audit/$QUARTER"
mkdir -p "$OUT"

# 1. PCI Incident Summary
curl -s -u "$CREDS" -X POST -H 'Content-Type: application/json' \
  -d '{"savedReportId":0,"incidentCreationDateGreaterThan":"2026-01-01T00:00:00Z","incidentCreationDateLessThan":"2026-03-31T23:59:59Z","filters":{"filterType":"booleanFilter","filterName":"policyName","filterOperator":"CONTAINS","filterValue":"PCI"}}' \
  "$ENFORCE/ProtectManager/webservices/v2/incidents" > "$OUT/pci-incidents.json"

# 2. Export PCI policies
curl -s -u "$CREDS" -X POST -H 'Content-Type: application/json' \
  "$ENFORCE/ProtectManager/webservices/v2/policies/export" > "$OUT/pci-policies.xml"

# 3. Audit log
curl -s -u "$CREDS" \
  "$ENFORCE/ProtectManager/webservices/v2/auditLogs?startDate=2026-01-01&endDate=2026-03-31" \
  > "$OUT/audit-log.json"

echo "PCI audit package generated in $OUT/"
echo "Contents:"
ls -la "$OUT/"
```

### HIPAA Audit Report Package

| Component | Evidence For | Notes |
|-----------|-------------|-------|
| PHI Incident Summary | 164.308(a)(1) -- Security management | All HIPAA policy incidents |
| PHI Block/Encrypt Evidence | 164.312(e)(1) -- Transmission security | Blocked/encrypted emails containing PHI |
| PHI Discovery Findings | 164.312(a)(1) -- Access control | Where PHI was found at rest |
| Audit Trail | 164.312(b) -- Audit controls | All DLP admin actions |
| User Awareness Evidence | 164.308(a)(5) -- Security awareness | Incidents + training assignments |
| Breach Notification Timeline | Art. 33 -- Notification obligation | High-severity incident timestamps vs. notification timestamps |

### GDPR Audit Report Package

| Component | Evidence For | Notes |
|-----------|-------------|-------|
| EU PII Incident Summary | Art. 32 -- Security of processing | All GDPR policy incidents |
| Cross-Border Transfer Detection | Art. 46 -- Transfers safeguards | Incidents where EU data was sent outside EU |
| Data Discovery Inventory | Art. 30 -- Records of processing | Where EU personal data was found |
| DPIA Supporting Data | Art. 35 -- Impact assessment | Discovery results informing risk analysis |
| Breach Detection Timeline | Art. 33 -- 72-hour notification | Time from detection to notification |

---

## 9. Data Discovery Reporting

### Discovery Report Builder

Create reports specifically for data-at-rest findings:

**Filter configuration:**
```
Detection Server Type: DISCOVER
Date Range: [last scan completion date range]
Policy: [specific compliance policy or all]
Severity: [High and Medium recommended]
```

**Useful groupings:**
- Group by **File Path** -- See which directories have the most findings
- Group by **Policy** -- See which data types are most prevalent at rest
- Group by **File Owner** -- Identify who is responsible for sensitive data
- Group by **Scan Target** -- Compare findings across different repositories

### Data Inventory Report Example

**Purpose:** Show auditors exactly where sensitive data lives.

| File Server | Share | Path | Policy Matched | Files Found | Severity | Remediated |
|------------|-------|------|---------------|-------------|----------|------------|
| FS-HR-01 | \\hr-data\ | \employee-records\ | PII - SSN | 142 | High | Yes (Encrypted) |
| FS-HR-01 | \\hr-data\ | \benefits\ | HIPAA - PHI | 89 | High | Yes (Quarantined) |
| FS-FIN-01 | \\accounting\ | \invoices\ | PCI - Credit Card | 23 | High | Yes (Encrypted) |
| FS-SHARED | \\projects\ | \legacy-data\ | PII - SSN | 567 | High | Pending |
| SP-INTRANET | /sites/hr | /Shared Documents | HIPAA - PHI | 34 | Medium | Yes (Labeled) |

### Remediation Tracking Report

Track what happened to sensitive files found by Network Discover:

| File | Protect Action | Action Date | Status | Analyst |
|------|---------------|-------------|--------|---------|
| \\fs01\hr\ssn-list.xlsx | Quarantined | 2026-05-15 | Completed | J. Smith |
| \\fs01\fin\payments.csv | Encrypted | 2026-05-15 | Completed | J. Smith |
| \\fs02\proj\data-dump.sql | Quarantined | 2026-05-16 | Failed (access denied) | M. Jones |
| \\sp\hr\benefits.docx | MIP Label Applied | 2026-05-16 | Completed | M. Jones |

---

## 10. Executive Reporting Patterns

### Key Metrics for Executive Reports

| Metric | Formula | What It Shows |
|--------|---------|--------------|
| **Total Incidents** | Count of all incidents in period | Overall DLP activity level |
| **High Severity Rate** | High / Total * 100 | Risk concentration |
| **Block Rate** | Blocked / Total * 100 | Prevention effectiveness |
| **Resolution Rate** | Resolved / Total * 100 | Operational efficiency |
| **Mean Time to Resolve** | Avg(Resolution Date - Creation Date) | Response speed |
| **False Positive Rate** | False Positive / Total * 100 | Policy accuracy (target < 15%) |
| **Month-over-Month Change** | (This Month - Last Month) / Last Month * 100 | Trend direction |
| **Discovery Coverage** | Scanned Data / Total Data * 100 | Data-at-rest visibility |
| **User Training Rate** | Users Trained / Users with Incidents * 100 | Awareness program effectiveness |

### Executive Slide Deck Data Points

**Slide 1: Risk Posture Summary**
- Total incidents: X (trend: -12% vs. prior quarter)
- High severity: Y (trend: -18%)
- Data blocked from leaving organization: Z GB

**Slide 2: Compliance Status**
- PCI: X incidents, 95% resolved within SLA
- HIPAA: X incidents, 92% resolved within SLA
- GDPR: X incidents, 88% resolved within SLA

**Slide 3: Top Risk Areas**
- Top 3 policies by incident count
- Top 3 channels by incident count
- Top 3 departments by incident count

**Slide 4: Program Effectiveness**
- Block rate: 73% of high-severity violations blocked automatically
- False positive rate: 11% (down from 45% at program launch)
- Discovery: 85% of critical file shares scanned quarterly

---

## 11. Report Archival and Retention

### Archival Strategy

| Report Type | Retention Period | Storage Location | Format |
|-------------|-----------------|------------------|--------|
| Compliance reports | Match regulatory requirement (1-7 years) | Encrypted file share or document management system | CSV + JSON |
| Audit logs | Match regulatory requirement (3-7 years) | SIEM long-term storage + offline archive | JSON + syslog |
| Executive reports | 3 years | SharePoint / document management | PDF |
| Operational reports | 90 days | DLP console saved searches | On-screen (regeneratable) |
| Discovery data | 1-2 years | DLP database + exported archives | JSON |

### Automated Archival

```bash
#!/bin/bash
# archive-compliance-reports.sh
# Run monthly: archive last month's reports to long-term storage

ARCHIVE_ROOT="/archive/dlp-compliance"
PREV_MONTH=$(date -v-1m +"%Y-%m" 2>/dev/null || date -d "last month" +"%Y-%m")
DEST="$ARCHIVE_ROOT/$PREV_MONTH"
mkdir -p "$DEST"

# Copy generated reports
cp /reports/dlp-compliance/$PREV_MONTH/*.json "$DEST/"
cp /reports/dlp-compliance/$PREV_MONTH/*.csv "$DEST/"

# Generate SHA256 checksums for integrity verification
cd "$DEST" && sha256sum * > CHECKSUMS.sha256

# Compress archive
tar czf "$ARCHIVE_ROOT/$PREV_MONTH.tar.gz" -C "$ARCHIVE_ROOT" "$PREV_MONTH"

echo "Archived $PREV_MONTH to $ARCHIVE_ROOT/$PREV_MONTH.tar.gz"
echo "Checksum: $(sha256sum $ARCHIVE_ROOT/$PREV_MONTH.tar.gz)"
```

---

## 12. Advanced SIEM Configurations

### Splunk Add-on for Symantec DLP

**Installation:**
1. Install "Splunk Add-on for Symantec DLP" from Splunkbase
2. Configure syslog input on Splunk (port 514 or custom)
3. Configure DLP syslog response rule pointing to Splunk
4. Verify data appears in Splunk index

**Pre-built Splunk dashboards include:**
- DLP Incident Overview
- Top Policies Dashboard
- User Risk Dashboard
- Channel Analysis
- Data Discovery Summary

### Microsoft Sentinel Integration

**Configuration:**
1. Deploy CEF via AMA (Azure Monitor Agent) connector in Sentinel
2. Configure DLP syslog response rule with CEF format
3. Point syslog to the AMA forwarder
4. Sentinel auto-parses CEF fields
5. Create Sentinel analytics rules for DLP incidents:
   - Alert on High severity DLP incidents
   - Correlate DLP incidents with Azure AD sign-in anomalies
   - Detect patterns: same user triggering DLP across multiple channels

### Google Chronicle Integration

**Configuration:**
1. Enable Symantec DLP parser in Chronicle
2. Configure DLP syslog forwarding to Chronicle ingestion endpoint
3. Chronicle auto-normalizes DLP events into UDM (Unified Data Model)
4. Create Chronicle detection rules for DLP-specific patterns

---

## 13. Troubleshooting

### Report Issues

| Symptom | Cause | Resolution |
|---------|-------|------------|
| Report shows 0 results | Filters too restrictive; no incidents match | Broaden filters; verify incidents exist for the date range |
| Report shows unexpected results | Wrong policy filter; role-based scoping | Verify filter values; check role incident access scope |
| Report times out | Too many incidents; wide date range | Narrow date range; add more specific filters; use API with pagination |
| Scheduled report not delivered | SMTP failure; email bounced; wrong recipient | Check System Events for SMTP errors; verify recipient address |
| Dashboard widgets show different totals | Different date ranges or filters per widget | Verify each widget uses the same parameters |
| CSV export truncated | Browser download limit; large dataset | Use API export for datasets > 100K incidents |
| Syslog messages not in SIEM | Firewall; wrong port; format mismatch | Test with netcat; verify CEF format matches SIEM parser |
| Audit log export empty | Date range has no events; wrong API endpoint | Verify date range; use correct audit log endpoint |

### Performance Tuning for Reports

| Optimization | Impact | How |
|-------------|--------|-----|
| Use date range filters | Major | Always specify a date range; never query "all time" |
| Add severity filter | Moderate | Limit to High/Medium for compliance reports |
| Use saved searches | Moderate | Pre-built queries are optimized |
| Schedule off-hours | Moderate | Avoid concurrent report + incident processing |
| Oracle index optimization | Major | Ensure indexes on creation_date, policy_name, severity |
| API pagination | Major | Use pageSize=500 and iterate rather than requesting all at once |

---

*End of advanced compliance reporting guide. Total coverage: 10+ report types, dashboard configuration, CEF/syslog variables, 3 regulatory audit packages, API reporting patterns, and archival strategies.*
