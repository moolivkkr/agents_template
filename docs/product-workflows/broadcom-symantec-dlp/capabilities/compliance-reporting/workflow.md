# Compliance Reporting Workflow -- Broadcom Symantec DLP

> **Capability:** DLP reporting for compliance, audit, and executive visibility
> **Enforce Console Path:** Incidents > [filters/dashboards], System > Servers and Detectors > Events/Audit Logs
> **Sources:** [S1] Help Center 16.0, [S2] Help Center 25.1, [S3] Help Center 26.1, [S4] Full PDF 16.0, API Intelligence Report

---

## Table of Contents

1. [Overview](#1-overview)
2. [Built-in Reports](#2-built-in-reports)
3. [Custom Reports](#3-custom-reports)
4. [Dashboards](#4-dashboards)
5. [Report Export and Distribution](#5-report-export-and-distribution)
6. [SIEM Forwarding](#6-siem-forwarding)
7. [Compliance Evidence](#7-compliance-evidence)
8. [Programmatic Reporting via REST API](#8-programmatic-reporting-via-rest-api)
9. [Regulatory Compliance Mapping](#9-regulatory-compliance-mapping)
10. [End-to-End Reporting Workflow](#10-end-to-end-reporting-workflow)

---

## 1. Overview

Symantec DLP reporting serves three audiences with different needs:

| Audience | Need | Report Type |
|----------|------|-------------|
| **Security Operations** | Daily incident queue management, SLA tracking, workload distribution | Operational dashboards, saved searches |
| **Compliance Officers** | Evidence of policy enforcement, regulatory adherence, audit trail | Compliance reports, data discovery findings, retention evidence |
| **Executives / CISO** | Risk posture, trend analysis, program ROI, incident reduction over time | Executive dashboards, trend reports, summary metrics |

### Reporting Data Sources

All DLP reports draw from the same underlying data in the Enforce Server Oracle database:

| Data Source | What It Contains | Report Use |
|-------------|-----------------|------------|
| **Incidents** | Every policy violation detected across all channels | Volume, trends, policy effectiveness, compliance evidence |
| **Policies** | Active policy configurations and their detection rules | Coverage analysis, regulatory mapping |
| **System Events** | Server health, detection errors, capacity metrics | Operational health reports |
| **Audit Logs** | Admin actions: policy changes, config modifications, incident actions | Change management, SOX/audit compliance |
| **Discovery Results** | Sensitive data locations found by Network Discover | Data inventory, risk assessment, remediation tracking |
| **Agent Status** | Endpoint agent deployment and health | Endpoint coverage reports |

### Report Categories

| Category | Description | Examples |
|----------|-------------|---------|
| **Incident Reports** | Who, what, when, where of DLP violations | Policy summary, severity summary, user summary |
| **System Reports** | Operational health of DLP infrastructure | Server status, agent health, scan progress |
| **Discovery Reports** | Where sensitive data was found at rest | Data inventory by server, by policy, by department |
| **Compliance Reports** | Regulatory evidence and adherence metrics | PCI-specific incidents, HIPAA violations, GDPR data subject activity |
| **Executive Reports** | High-level risk posture and trend analysis | Risk trend, top policies, top users, channel distribution |

---

## 2. Built-in Reports

### 2.1 Policy Summary Report

**What it shows:** Incident count broken down by policy, with trend data.

**Navigation:** Incidents > [set filter: group by Policy Name]

| Column | Description |
|--------|-------------|
| Policy Name | Name of the DLP policy |
| Total Incidents | Count of incidents for this policy in the date range |
| High Severity | Count of high-severity incidents |
| Medium Severity | Count of medium-severity incidents |
| Low Severity | Count of low-severity incidents |
| Trend | Sparkline or percentage change vs. prior period |

**Use case:** Identify which policies generate the most violations. High-volume policies may need tuning; low-volume policies may indicate poor coverage.

### 2.2 Severity Summary Report

**What it shows:** Incident distribution by severity level across all policies.

| Severity | Count | Percentage | Trend |
|----------|-------|-----------|-------|
| High | 245 | 12% | -5% vs. prior month |
| Medium | 891 | 44% | +2% vs. prior month |
| Low | 632 | 31% | -8% vs. prior month |
| Informational | 267 | 13% | +1% vs. prior month |

**Use case:** Executive reporting on risk distribution. A decreasing High severity trend indicates program effectiveness.

### 2.3 User Summary Report

**What it shows:** Top users by incident count, with policy breakdown.

| User | Department | Total Incidents | PCI | HIPAA | IP | Risk Score |
|------|-----------|----------------|-----|-------|-----|-----------|
| j.smith@corp | Finance | 47 | 32 | 0 | 15 | 78 |
| m.jones@corp | Sales | 38 | 0 | 0 | 38 | 65 |
| r.doe@corp | Healthcare | 29 | 0 | 29 | 0 | 55 |

**Use case:** Identify users who need targeted training or closer monitoring. Users with high incident counts across multiple policies may indicate insider risk.

### 2.4 Channel Summary Report

**What it shows:** Incidents by detection channel (email, web, endpoint, discover, cloud).

| Channel | Count | Percentage | Top Policy |
|---------|-------|-----------|------------|
| Email (Network Prevent) | 892 | 35% | PCI DSS |
| Web (Network Prevent) | 456 | 18% | IP - Confidential |
| Endpoint (USB) | 312 | 12% | PII - SSN |
| Endpoint (Clipboard) | 289 | 11% | IP - Source Code |
| Endpoint (Print) | 67 | 3% | HIPAA - PHI |
| Discover (File Shares) | 410 | 16% | PCI DSS |
| Cloud (CloudSOC) | 109 | 5% | GDPR - EU PII |

**Use case:** Understand how sensitive data moves in the organization. High email volume may justify stronger email encryption; high USB volume may justify USB restrictions.

### 2.5 Compliance-Specific Reports

**PCI DSS Incident Summary:**
- Filter: Policies tagged with "PCI" or "Payment Card"
- Content: All incidents matching PCI-related policies
- Evidence: Credit card numbers detected, channels used, remediation actions taken
- Meets: PCI DSS Requirement 12.10 (incident response documentation)

**HIPAA PHI Report:**
- Filter: Policies tagged with "HIPAA" or "PHI"
- Content: All incidents involving protected health information
- Evidence: PHI types detected (patient names, medical records, insurance IDs)
- Meets: HIPAA Security Rule 164.312 (audit controls)

**GDPR Data Subject Activity:**
- Filter: Policies tagged with "GDPR" or "EU PII"
- Content: Incidents involving EU personal data
- Evidence: Data categories, processing activities detected, cross-border transfers
- Meets: GDPR Article 30 (records of processing activities)

**SOX Financial Data Report:**
- Filter: Policies tagged with "SOX" or "Financial"
- Content: Incidents involving financial data, earnings reports, material non-public information
- Meets: SOX Section 302/404 (internal controls over financial reporting)

**GLBA Consumer Financial Data:**
- Filter: Policies tagged with "GLBA"
- Content: Incidents involving consumer financial information (account numbers, credit scores)
- Meets: GLBA Safeguards Rule (protection of customer information)

### 2.6 Data Discovery Reports

**Sensitive Data Inventory:**
- Source: Network Discover scan results
- Content: Where sensitive data was found, organized by:
  - File server / share path
  - Data type (PCI, PII, PHI, IP)
  - Policy matched
  - Count of violations per location
- Use: Annual data inventory for compliance audits

**Discovery Remediation Report:**
- Source: Network Protect action results
- Content: Files quarantined, encrypted, labeled, or copied
- Status: Remediation pending, completed, or failed
- Use: Evidence that sensitive data exposure was addressed

### 2.7 System Event Reports

**Navigation:** System > Servers and Detectors > Events

| Report | Content | Use |
|--------|---------|-----|
| Server Health | Detection server status, uptime, errors | Operational health monitoring |
| Agent Status | Endpoint agent deployment, version, connectivity | Endpoint coverage verification |
| Scan Status | Discovery scan progress, completion, errors | Scan monitoring |
| Detection Capacity | Policy evaluation throughput, queue depth | Capacity planning |

---

## 3. Custom Reports

### 3.1 Report Builder

Symantec DLP uses a filter-based report builder:

**Navigation:** Incidents > [set filters] > Save As

**Building a custom report:**
1. Navigate to the appropriate incident view (Network, Endpoint, Discover)
2. Set **filters** to define report scope:
   - Date range (mandatory for meaningful reports)
   - Severity level(s)
   - Policy/policy group
   - Status
   - Detection channel
   - Custom attributes (department, cost center, etc.)
3. Set **grouping** to organize results:
   - Group by: Policy, Severity, User, Channel, Custom Attribute
4. Set **columns** to display:
   - Available columns: all standard and custom incident fields
   - Drag columns to reorder
5. Click **Save As**:
   - Name: Descriptive name (e.g., "PCI Quarterly Compliance Report")
   - Description: Purpose and intended audience
   - Visibility: Private (you only) or Shared (your role)

### 3.2 Saved Report Properties

| Property | Options | Description |
|----------|---------|-------------|
| Name | Text | Report name (appears in report list) |
| Description | Text | Optional description |
| Visibility | Private / Shared | Who can see and run this report |
| Date Range | Relative / Absolute | "Last 30 days" (relative) or "2026-01-01 to 2026-03-31" (absolute) |
| Auto-Refresh | On/Off | Re-run with current data each time opened |
| Schedule | None / Daily / Weekly / Monthly | Automatic execution and delivery |
| Distribution | Email addresses | Recipients of scheduled reports |
| Format | CSV / On-screen | Export format for scheduled delivery |

### 3.3 Report Scheduling and Distribution

1. Open a saved report
2. Click **Schedule**
3. Configure:
   - Frequency: Daily, Weekly (specify day), Monthly (specify date)
   - Time: When to generate the report
   - Format: CSV attachment or inline summary
   - Recipients: Email addresses (comma-separated)
   - Subject: Email subject template
4. Click **Save Schedule**

The Enforce Server generates the report at the scheduled time and emails it to recipients.

### 3.4 Role-Based Report Visibility

Reports are governed by RBAC:

| Rule | Description |
|------|-------------|
| Users see reports for their current role | A user with multiple roles sees only reports associated with their active role |
| Shared reports are visible to all users in the role | Shared by role, not globally |
| Users can only edit/delete their own reports | Even shared reports can only be modified by the creator |
| Administrator has unrestricted report access | Default admin user (not a role member) sees all reports |
| Incident access scope applies to reports | If your role can only see PCI incidents, your reports only include PCI data |

---

## 4. Dashboards

### 4.1 Dashboard Overview

**Navigation:** Incidents > Dashboards

Dashboards provide visual, at-a-glance views of DLP metrics. Each dashboard consists of multiple saved reports displayed as widgets.

### 4.2 Dashboard Configuration

| Feature | DLP 16.0 | DLP 26.1 |
|---------|----------|----------|
| Max reports per dashboard | 6 | 12 |
| Chart types | Bar, pie, line, table | Bar, pie, line, table + dynamic chart type |
| Custom dashboards | Yes | Yes (enhanced) |
| Role-based visibility | Yes | Yes |
| Auto-refresh | Yes | Yes |
| Drill-down | Click chart element to see underlying incidents | Same |

### 4.3 Dashboard Types

**Executive Dashboard:**
- Widgets: Severity distribution (pie), Incident trend (line), Top policies (bar), Top users (table)
- Audience: CISO, VP of Security, Board reporting
- Date range: Last 90 days, trend comparison to prior quarter

**Operational Dashboard:**
- Widgets: Open incidents by status (bar), Incidents by channel (pie), SLA compliance (gauge), Analyst workload (table)
- Audience: SOC manager, DLP team lead
- Date range: Last 7 days, real-time refresh

**Compliance Dashboard:**
- Widgets: PCI incidents by month (line), HIPAA incidents by department (bar), GDPR incidents by data type (pie), Discovery findings by server (table)
- Audience: Compliance officer, audit team
- Date range: Current quarter, comparison to prior quarter

**Discovery Dashboard:**
- Widgets: Data inventory by location (treemap/table), Sensitive data types found (pie), Remediation status (bar), Scan coverage (gauge)
- Audience: Data governance team
- Date range: Last scan cycle

### 4.4 Creating a Custom Dashboard

1. Navigate to **Incidents > Dashboards**
2. Click **Create Dashboard** (or edit existing)
3. Enter dashboard name: "Q2 2026 PCI Compliance"
4. Click **Add Report Widget**
5. Select from saved reports:
   - Widget 1: "PCI Incidents - Monthly Trend" (line chart)
   - Widget 2: "PCI Incidents - By Severity" (pie chart)
   - Widget 3: "PCI Incidents - Top 10 Users" (table)
   - Widget 4: "PCI Discovery Findings" (bar chart)
   - Widget 5: "PCI Remediation Status" (bar chart)
   - Widget 6: "PCI Channel Distribution" (pie chart)
6. Arrange widgets in the dashboard layout
7. Set chart type for each widget (DLP 26.1: dynamic chart type selection)
8. Set auto-refresh interval (e.g., every 15 minutes)
9. Click **Save**

---

## 5. Report Export and Distribution

### 5.1 Export Formats

| Format | Method | Use Case |
|--------|--------|----------|
| CSV | Console: Incidents > [filter] > Export | Spreadsheet analysis, data manipulation |
| JSON | REST API: `POST /incidents/export` | Programmatic processing, data pipelines |
| PDF | Dashboard print / scheduled report | Executive presentations, audit evidence |
| On-screen | Console view | Real-time triage and review |

### 5.2 CSV Export

1. Navigate to **Incidents > [channel]**
2. Set filters for the desired report scope
3. Click **Export** button
4. Select **CSV** format
5. Choose columns to include
6. Click **Export**
7. CSV file downloads to your browser

**Columns typically included in compliance exports:**
- Incident ID, Creation Date, Severity, Status
- Policy Name, Match Count
- Sender/User, Recipient/Destination
- Channel/Protocol
- Remediation Status, Resolution Category
- Custom Attributes (Department, Cost Center, Regulatory Scope)

### 5.3 Scheduled Report Delivery

1. Save a report (Incidents > [filter] > Save As)
2. Click **Schedule** on the saved report
3. Configure:
   - Frequency: Monthly (for compliance) or Weekly (for operations)
   - Format: CSV attachment
   - Recipients: `compliance@corp.com`, `ciso@corp.com`
4. The report is generated and emailed automatically

### 5.4 API-Based Export

```bash
# Export incidents for Q1 2026 compliance report
curl -s -u 'api-user:password' \
  -X POST \
  -H 'Content-Type: application/json' \
  -d '{
    "incidentCreationDateGreaterThan": "2026-01-01T00:00:00Z",
    "incidentCreationDateLessThan": "2026-03-31T23:59:59Z",
    "filters": {
      "filterType": "booleanFilter",
      "filterName": "policyName",
      "filterOperator": "CONTAINS",
      "filterValue": "PCI"
    }
  }' \
  'https://enforce.corp.local/ProtectManager/webservices/v2/incidents/export' \
  > pci-q1-2026-report.json
```

---

## 6. SIEM Forwarding

### 6.1 Syslog Integration

DLP forwards incident data to SIEM via syslog, configured through response rules.

**Two levels of syslog integration:**

| Level | Source | Configuration |
|-------|--------|---------------|
| **Incident-level** | Each incident triggers a syslog message | Response Rule > Action: Log to Syslog Server |
| **System-level** | System events and audit logs forwarded | System > Settings > Syslog configuration |

### 6.2 CEF Format for DLP Incidents

Common Event Format (CEF) is the standard for DLP-to-SIEM integration:

```
CEF:0|Broadcom|Data Loss Prevention|16.0|$RULE_ID$|$POLICY$|$CEF_SEVERITY$|
  INCIDENT_ID=$INCIDENT_ID$
  POLICY=$POLICY$
  RULES=$RULES$
  SEVERITY=$SEVERITY$
  BLOCKED=$BLOCKED$
  APPLICATION_USER=$APPLICATION_USER$
  ENDPOINT_MACHINE=$ENDPOINT_MACHINE$
  ENDPOINT_USERNAME=$ENDPOINT_USERNAME$
  MACHINE_IP=$MACHINE_IP$
  FILE_NAME=$FILE_NAME$
  RECIPIENTS=$RECIPIENTS$
  SENDER=$SENDER$
  SUBJECT=$SUBJECT$
  MATCH_COUNT=$MATCH_COUNT$
  PROTOCOL=$PROTOCOL$
```

**CEF severity mapping:**

| DLP Severity | CEF Severity (0-10) |
|-------------|---------------------|
| High (1) | 8 |
| Medium (2) | 5 |
| Low (3) | 3 |
| Informational (4) | 1 |

### 6.3 Audit Log Forwarding

**Navigation:** System > Servers and Detectors > Audit Logs > Syslog Configuration

Audit logs capture admin actions:
- Policy changes (create, modify, delete, enable, disable)
- Configuration changes (server settings, role changes)
- Incident actions (status changes, note additions)
- User management (account creation, role assignment)

Forwarding audit logs to SIEM provides:
- Change management evidence (SOX compliance)
- Admin activity monitoring (insider threat detection)
- Correlation with incident data (who modified the policy before the false positive spike?)

---

## 7. Compliance Evidence

### 7.1 Audit Trail for Policy Changes

Every policy modification is logged in the audit trail:

| Event | Logged Details |
|-------|---------------|
| Policy Created | Who, when, policy name, initial rules |
| Policy Modified | Who, when, what changed (rule added/removed, threshold changed) |
| Policy Enabled/Disabled | Who, when, previous state |
| Policy Deployed | Who, when, target policy group |
| Response Rule Changed | Who, when, what changed |

**Accessing audit logs:**
```
System > Servers and Detectors > Audit Logs
```

Export audit logs: Click **Export** for CSV download.

REST API access (DLP 16.0 RU1+):
```bash
curl -s -u 'api-user:password' \
  'https://enforce.corp.local/ProtectManager/webservices/v2/auditLogs?startDate=2026-01-01&endDate=2026-05-21'
```

### 7.2 Incident Resolution Documentation

Each resolved incident serves as compliance evidence:
- **What was detected**: Matched content, data type, match count
- **When it was detected**: Timestamp with timezone
- **How it was handled**: Block, quarantine, encrypt, notify (automated actions)
- **Who reviewed it**: Analyst name, investigation notes
- **What was the outcome**: Resolution status, remediation actions, justification
- **Full audit trail**: Every action taken on the incident, timestamped and attributed

### 7.3 Regulatory Compliance Mapping

Map DLP policies to specific regulatory requirements:

| Regulation | Requirement | DLP Policy | Evidence |
|-----------|-------------|-----------|----------|
| PCI DSS 3.4 | Render PAN unreadable wherever stored | "PCI - Credit Card at Rest" | Discovery scan findings + remediation |
| PCI DSS 4.1 | Encrypt sensitive data in transit | "PCI - Credit Card in Email" | Incident report showing email encryption |
| PCI DSS 12.10 | Incident response plan | Response rules + incident workflow | Incident resolution records |
| HIPAA 164.312(a) | Access controls | "HIPAA - PHI Detection" | Incident report showing unauthorized access attempts |
| HIPAA 164.312(b) | Audit controls | DLP audit logs | Audit log export showing policy management |
| GDPR Art. 30 | Records of processing | "GDPR - EU PII" policies | Incident reports documenting data processing activities |
| GDPR Art. 33 | Breach notification (72 hrs) | High-severity incident alerts | Incident creation timestamp + notification timestamp |
| SOX 302/404 | Internal controls | Financial data policies + audit logs | Policy change audit trail + incident resolution records |
| GLBA Safeguards | Customer info protection | "GLBA - Consumer Financial" | Incident report + remediation evidence |

### 7.4 Data Retention for Compliance

Different regulations require different retention periods for DLP evidence:

| Regulation | Minimum Retention | What to Retain |
|-----------|-------------------|----------------|
| PCI DSS | 1 year (audit logs), 3 months (data) | Incident records, audit logs, policy change history |
| HIPAA | 6 years | Incident records, audit logs, evidence of policy enforcement |
| GDPR | Duration of processing + dispute period | Incident records, processing activity logs, consent records |
| SOX | 7 years | Audit logs, policy change records, financial data incident records |
| GLBA | 5 years | Incident records, customer data handling evidence |

**Configure retention in DLP:**
1. Define retention periods per policy using "Limit Incident Data Retention" response rule
2. Archive data before purging (API export or CSV export)
3. Verify Oracle database backup includes incident data
4. Document retention policy and map to regulatory requirements

---

## 8. Programmatic Reporting via REST API

### 8.1 Building Custom Compliance Reports

The REST API enables automated report generation outside the Enforce Console.

**Common patterns:**

```bash
# Monthly PCI compliance report
curl -s -u "$DLP_AUTH" \
  -X POST \
  -H 'Content-Type: application/json' \
  -d '{
    "savedReportId": 0,
    "incidentCreationDateGreaterThan": "2026-05-01T00:00:00Z",
    "incidentCreationDateLessThan": "2026-05-31T23:59:59Z",
    "filters": {
      "filterType": "booleanFilter",
      "filterName": "policyName",
      "filterOperator": "CONTAINS",
      "filterValue": "PCI"
    },
    "pageSize": 1000
  }' \
  "$DLP_BASE/incidents" | jq '
  {
    report_period: "May 2026",
    total_incidents: (.incidents | length),
    by_severity: (.incidents | group_by(.severity) | map({severity: .[0].severity, count: length})),
    by_status: (.incidents | group_by(.incidentStatusName) | map({status: .[0].incidentStatusName, count: length})),
    blocked_count: [.incidents[] | select(.preventActionStatus == "BLOCKED")] | length,
    resolved_count: [.incidents[] | select(.incidentStatusName == "Resolved")] | length
  }'
```

### 8.2 Automated Report Pipeline

```bash
#!/bin/bash
# compliance-report-pipeline.sh
# Generates monthly compliance reports for PCI, HIPAA, GDPR
# Run on the first of each month via cron

ENFORCE="https://enforce.corp.local"
CREDS="report-svc:password"
REPORT_DIR="/reports/dlp-compliance"
PREV_MONTH=$(date -v-1m +"%Y-%m" 2>/dev/null || date -d "last month" +"%Y-%m")
START="${PREV_MONTH}-01T00:00:00Z"
END=$(date -v-1d +"%Y-%m-%dT23:59:59Z" 2>/dev/null || date -d "yesterday" +"%Y-%m-%dT23:59:59Z")

mkdir -p "$REPORT_DIR/$PREV_MONTH"

# Generate PCI report
echo "Generating PCI compliance report for $PREV_MONTH..."
curl -s -u "$CREDS" \
  -X POST \
  -H 'Content-Type: application/json' \
  -d "{
    \"savedReportId\": 0,
    \"incidentCreationDateGreaterThan\": \"$START\",
    \"incidentCreationDateLessThan\": \"$END\",
    \"filters\": {
      \"filterType\": \"booleanFilter\",
      \"filterName\": \"policyName\",
      \"filterOperator\": \"CONTAINS\",
      \"filterValue\": \"PCI\"
    },
    \"pageSize\": 5000
  }" \
  "$ENFORCE/ProtectManager/webservices/v2/incidents" \
  > "$REPORT_DIR/$PREV_MONTH/pci-incidents.json"

# Generate HIPAA report
echo "Generating HIPAA compliance report for $PREV_MONTH..."
curl -s -u "$CREDS" \
  -X POST \
  -H 'Content-Type: application/json' \
  -d "{
    \"savedReportId\": 0,
    \"incidentCreationDateGreaterThan\": \"$START\",
    \"incidentCreationDateLessThan\": \"$END\",
    \"filters\": {
      \"filterType\": \"booleanFilter\",
      \"filterName\": \"policyName\",
      \"filterOperator\": \"CONTAINS\",
      \"filterValue\": \"HIPAA\"
    },
    \"pageSize\": 5000
  }" \
  "$ENFORCE/ProtectManager/webservices/v2/incidents" \
  > "$REPORT_DIR/$PREV_MONTH/hipaa-incidents.json"

# Generate GDPR report
echo "Generating GDPR compliance report for $PREV_MONTH..."
curl -s -u "$CREDS" \
  -X POST \
  -H 'Content-Type: application/json' \
  -d "{
    \"savedReportId\": 0,
    \"incidentCreationDateGreaterThan\": \"$START\",
    \"incidentCreationDateLessThan\": \"$END\",
    \"filters\": {
      \"filterType\": \"booleanFilter\",
      \"filterName\": \"policyName\",
      \"filterOperator\": \"CONTAINS\",
      \"filterValue\": \"GDPR\"
    },
    \"pageSize\": 5000
  }" \
  "$ENFORCE/ProtectManager/webservices/v2/incidents" \
  > "$REPORT_DIR/$PREV_MONTH/gdpr-incidents.json"

echo "Reports generated in $REPORT_DIR/$PREV_MONTH/"
```

### 8.3 Retrieving Saved Report Filters

```bash
# Get filter criteria for a saved report (to replicate it programmatically)
curl -s -u "$DLP_AUTH" \
  "$DLP_BASE/reports/42/filters" | jq '.'
```

---

## 9. Regulatory Compliance Mapping

### 9.1 PCI DSS Compliance Evidence from DLP

| PCI DSS Requirement | DLP Evidence | Report/Data Source |
|--------------------|-------------|-------------------|
| **Req 3.1** | Render PAN unreadable wherever stored | Discovery scan: where credit card data was found + remediation (quarantine/encrypt) |
| **Req 3.4** | Protection of stored cardholder data | Discovery scan results showing no unprotected cardholder data |
| **Req 4.1** | Encrypt transmission of cardholder data | Email Prevent incidents showing blocked unencrypted PCI emails |
| **Req 7.1** | Limit access to cardholder data | Endpoint Prevent incidents showing blocked unauthorized access |
| **Req 10.2** | Track all access to cardholder data | DLP audit logs + incident records |
| **Req 10.7** | Retain audit trail history for >= 1 year | Audit log retention configuration |
| **Req 12.10** | Maintain incident response plan | Incident workflow configuration + response rule documentation |

### 9.2 HIPAA Compliance Evidence from DLP

| HIPAA Rule | DLP Evidence | Report/Data Source |
|-----------|-------------|-------------------|
| **164.308(a)(1)** | Security management process | DLP policy documentation + incident management workflow |
| **164.312(a)(1)** | Access control | Endpoint Prevent blocking unauthorized PHI access |
| **164.312(b)** | Audit controls | DLP audit logs showing all PHI-related policy and incident activity |
| **164.312(e)(1)** | Transmission security | Email Prevent blocking unencrypted PHI in transit |
| **164.314** | Business associate requirements | Discovery scans of third-party file shares for PHI |
| **Breach notification** | 60-day notification deadline | Incident creation timestamp -> notification timestamp |

### 9.3 GDPR Compliance Evidence from DLP

| GDPR Article | DLP Evidence | Report/Data Source |
|-------------|-------------|-------------------|
| **Art. 5(1)(f)** | Integrity and confidentiality | All DLP incident reports showing data protection enforcement |
| **Art. 25** | Data protection by design | DLP policy configuration documentation |
| **Art. 30** | Records of processing activities | DLP incident data documenting data processing observed |
| **Art. 32** | Security of processing | DLP enforcement actions (block, encrypt, quarantine) |
| **Art. 33** | Notification to supervisory authority | High-severity incident alerts + response timestamps |
| **Art. 35** | Data protection impact assessment | Discovery scan results informing DPIA |

---

## 10. End-to-End Reporting Workflow

### Phase 1: Operational Reporting (Daily/Weekly)

1. **Daily triage report**: Open incidents by severity and status
   - Generate: Saved search "Open Incidents - High Severity"
   - Audience: SOC analysts
   - Delivery: Auto-refresh on operational dashboard

2. **Weekly operations report**: Incident volume, SLA compliance, analyst workload
   - Generate: Scheduled report "Weekly DLP Operations Summary"
   - Audience: SOC manager
   - Delivery: Email every Monday morning

3. **False positive review**: False positives by policy for tuning
   - Generate: Saved search "False Positives - Last 7 Days - By Policy"
   - Audience: Policy administrators
   - Delivery: Weekly email to policy-admin@corp.com

### Phase 2: Compliance Reporting (Monthly/Quarterly)

4. **Monthly compliance reports**: PCI, HIPAA, GDPR incident summaries
   - Generate: Automated pipeline (see Section 8.2) or scheduled saved reports
   - Audience: Compliance officers
   - Delivery: First week of each month

5. **Quarterly discovery report**: Data inventory, remediation progress
   - Generate: Discovery incident summary grouped by file server and policy
   - Audience: Data governance team, compliance officers
   - Delivery: Within 2 weeks of quarter end

6. **Quarterly trend report**: Risk posture change, program effectiveness metrics
   - Generate: Comparison dashboard (current quarter vs. prior quarter)
   - Audience: CISO, executive leadership
   - Delivery: Executive dashboard, quarterly business review

### Phase 3: Audit Evidence (Annual/On-Demand)

7. **Annual audit package**: Complete compliance evidence for external auditors
   - Contents:
     - Policy configuration documentation
     - Incident summary reports by regulation
     - Audit log export (all policy changes for the year)
     - Discovery scan results and remediation evidence
     - Agent deployment coverage report
   - Format: CSV exports + dashboard screenshots + policy XML exports
   - Delivery: Secure file share for audit team

8. **On-demand audit response**: Answer specific auditor questions
   - Use saved searches and API queries to pull specific incident data
   - Export individual incident details with full audit trail
   - Provide evidence of response rule enforcement (block, quarantine records)

---

*End of compliance reporting workflow. For quickstart guide, see quickstart.md. For advanced report builder, SIEM format, and examples, see advanced.md.*
