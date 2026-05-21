# Advanced: Data Discovery (Network Discover)

> **Scope:** All target types, all scan options, UI diagrams, detailed examples per target type
> **Versions:** DLP 16.0 through 26.1
> **Sources:** [S1] Help Center 16.0, [S2] Help Center 25.1, [S4] Full PDF 16.0, [S17] Network Discover Tuning Guide 15.8, API Intelligence Report

---

## Table of Contents

1. [Target Type Deep Dives](#1-target-type-deep-dives)
2. [High Speed Discovery (DLP 16.1+)](#2-high-speed-discovery-dlp-161)
3. [MIP Label Detection and Application](#3-mip-label-detection-and-application)
4. [Endpoint Discover vs. Network Discover](#4-endpoint-discover-vs-network-discover)
5. [Multi-Server Discovery Architecture](#5-multi-server-discovery-architecture)
6. [Content Filtering Advanced Configuration](#6-content-filtering-advanced-configuration)
7. [Network Protect Deep Dive](#7-network-protect-deep-dive)
8. [API Automation Patterns](#8-api-automation-patterns)
9. [Performance Tuning Reference](#9-performance-tuning-reference)
10. [Discovery Reporting](#10-discovery-reporting)
11. [Integration with Data Insight](#11-integration-with-data-insight)
12. [Troubleshooting Reference](#12-troubleshooting-reference)

---

## 1. Target Type Deep Dives

### 1.1 CIFS/SMB File System Targets

#### UI Navigation and Field Reference

```
Enforce Console > Manage > Discover > Discover Targets > New Target > File System
```

**Screen layout (logical structure):**
```
+---------------------------------------------------------------+
| New File System Target                                        |
+---------------------------------------------------------------+
| General Tab                                                   |
|   Target Name: [_________________________]                    |
|   Description: [_________________________]                    |
|   Discover Server: [dropdown]                                 |
|   Policy Group:    [dropdown]                                 |
+---------------------------------------------------------------+
| Scan Paths Tab                                                |
|   +--------------------------------------------------+        |
|   | Path                              | Action       |        |
|   | \\server\share\                   | [Remove]     |        |
|   | \\server\share2\                  | [Remove]     |        |
|   +--------------------------------------------------+        |
|   [Add Path] [Import from CSV]                                |
|                                                               |
|   Include Filters:                                            |
|     Paths: [___________]  File Types: [___________]           |
|   Exclude Filters:                                            |
|     Paths: [___________]  File Types: [___________]           |
|   File Size: Min [___] MB  Max [___] MB                       |
|   File Age: Modified after [date picker]                      |
+---------------------------------------------------------------+
| Credentials Tab                                               |
|   Read Credentials:                                           |
|     Username: [DOMAIN\user_________]                          |
|     Password: [********************]                          |
|   Write Credentials (for Protect actions):                    |
|     Username: [DOMAIN\user_________]                          |
|     Password: [********************]                          |
+---------------------------------------------------------------+
| Schedule Tab                                                  |
|   Run: ( ) One-time  (o) Recurring  ( ) Continuous            |
|   Frequency: [Weekly v]  Day: [Sunday v]  Time: [02:00 AM]   |
|   [x] Incremental scan                                       |
|   Start Date: [date picker]  End Date: [date picker]          |
+---------------------------------------------------------------+
| Advanced Tab                                                  |
|   Concurrent Connections: [10]                                |
|   Bandwidth Limit: [Unlimited v]                              |
|   Scan Priority: [Normal v]                                   |
|   [x] Enable High Speed Discovery (16.1+)                    |
|   [x] Follow symbolic links                                  |
|   [ ] Scan hidden files                                       |
+---------------------------------------------------------------+
| [Save] [Save and Start] [Cancel]                              |
+---------------------------------------------------------------+
```

#### Complete Field Reference

| Field | Tab | Type | Required | Default | Description |
|-------|-----|------|----------|---------|-------------|
| Target Name | General | Text | Yes | -- | Unique name for this scan target |
| Description | General | Text | No | -- | Free-text description |
| Discover Server | General | Dropdown | Yes | -- | Which Discover server executes this scan |
| Policy Group | General | Dropdown | Yes | Default | Which policies to evaluate |
| Scan Paths | Paths | List | Yes | -- | UNC paths (e.g., `\\server\share\`) |
| Include Path Filter | Paths | Text | No | * (all) | Only scan paths matching pattern |
| Exclude Path Filter | Paths | Text | No | None | Skip paths matching pattern |
| Include File Types | Paths | Text | No | * (all) | File extensions to include |
| Exclude File Types | Paths | Text | No | None | File extensions to skip |
| Min File Size | Paths | Number | No | 0 | Minimum file size in KB |
| Max File Size | Paths | Number | No | Unlimited | Maximum file size in MB |
| Modified After | Paths | Date | No | None | Only scan files modified after this date |
| Read Username | Credentials | Text | Yes | -- | Domain\user for read access |
| Read Password | Credentials | Password | Yes | -- | Encrypted in Enforce database |
| Write Username | Credentials | Text | No | -- | Domain\user for Protect write actions |
| Write Password | Credentials | Password | No | -- | Required only for Protect actions |
| Schedule Type | Schedule | Radio | Yes | One-time | One-time, Recurring, or Continuous |
| Frequency | Schedule | Dropdown | Conditional | Weekly | Daily, Weekly, Monthly |
| Day of Week | Schedule | Dropdown | Conditional | Sunday | For weekly schedules |
| Time | Schedule | Time | Conditional | 00:00 | Start time |
| Incremental | Schedule | Checkbox | No | Disabled | Enable incremental scanning |
| Start Date | Schedule | Date | No | Today | When to begin scheduled scans |
| End Date | Schedule | Date | No | None | When to stop scheduled scans |
| Concurrent Connections | Advanced | Number | No | 10 | Max simultaneous file reads |
| Bandwidth Limit | Advanced | Dropdown | No | Unlimited | Network bandwidth cap |
| Scan Priority | Advanced | Dropdown | No | Normal | Priority relative to other scans |
| High Speed Discovery | Advanced | Checkbox | No | Disabled | Enable optimized CIFS scanning (16.1+) |
| Follow Symlinks | Advanced | Checkbox | No | Enabled | Follow symbolic/junction links |
| Scan Hidden Files | Advanced | Checkbox | No | Disabled | Include hidden/system files |

#### DFS Namespace Scanning

DFS (Distributed File System) targets are configured as File System targets but with DFS namespace roots:

- Path format: `\\domain.com\DFSRoot\namespace\`
- **Requirement:** Network Discover Server must be Windows-based
- DFS namespace resolution happens transparently
- DFS referrals are followed to underlying file servers
- Incremental scanning works across DFS namespaces

**Example DFS Configuration:**
```
Scan Paths:
  \\corp.local\DFSRoot\departments\finance\
  \\corp.local\DFSRoot\departments\hr\
  \\corp.local\DFSRoot\shared\projects\

Credentials: CORP\dlp-scanner-svc (must have read access to all underlying DFS targets)
```

#### NFS Target Scanning

NFS targets use a different configuration:

- Path format: `server:/export/path`
- Authentication: UID/GID-based (configured on the Discover server)
- The Discover server mounts the NFS export and scans locally
- NFS v3 and v4 supported

**Example NFS Configuration:**
```
Scan Type: NFS
Server: nfs-server-01.corp.local
Export Path: /exports/data-lake
Mount Options: -o ro,vers=4
```

### 1.2 SharePoint Targets -- Detailed Configuration

#### UI Navigation

```
Enforce Console > Manage > Discover > Discover Targets > New Target > SharePoint
```

**Screen layout (logical structure):**
```
+---------------------------------------------------------------+
| New SharePoint Target                                         |
+---------------------------------------------------------------+
| General Tab                                                   |
|   Target Name: [_________________________]                    |
|   SharePoint Web Application URL: [https://sp.corp.local____]|
|   Authentication: ( ) NTLM  (o) Kerberos  ( ) Claims         |
|   Discover Server: [dropdown]                                 |
|   Policy Group:    [dropdown]                                 |
+---------------------------------------------------------------+
| Site Collections Tab                                          |
|   +--------------------------------------------------+        |
|   | Site Collection Path         | Action             |       |
|   | /sites/human-resources       | [Remove]           |       |
|   | /sites/finance               | [Remove]           |       |
|   +--------------------------------------------------+        |
|   [Add] [Add All] [Import from CSV]                           |
|                                                               |
|   Scope: (o) Document Libraries  ( ) All Content              |
|   [x] Include sub-sites                                       |
|   [ ] Include version history                                 |
+---------------------------------------------------------------+
| Credentials Tab                                               |
|   Username: [DOMAIN\sp-scanner___]                            |
|   Password: [********************]                            |
+---------------------------------------------------------------+
| Filters Tab                                                   |
|   File Types: [.docx, .xlsx, .pdf, .csv]                     |
|   Max File Size: [100] MB                                     |
|   Modified After: [date picker]                               |
+---------------------------------------------------------------+
| Schedule Tab                                                  |
|   (same as file system target)                                |
+---------------------------------------------------------------+
```

#### SharePoint-Specific Configuration

| Setting | Options | Recommendation |
|---------|---------|----------------|
| Authentication | NTLM, Kerberos, Claims | NTLM for simplicity; Kerberos for security |
| Scope | Document Libraries Only, All Content | Document Libraries Only (skip lists, discussions) |
| Include Sub-Sites | Yes/No | Yes (scan all sub-sites under selected collections) |
| Include Version History | Yes/No | No (dramatically increases scan time; enable only for compliance audits) |

#### Example Configurations

**Example: HR SharePoint with strict PII scanning**
```
Target Name: SharePoint HR Portal - PII Weekly
URL: https://sharepoint.corp.local
Site Collections: /sites/human-resources, /sites/benefits, /sites/recruiting
Authentication: NTLM
Credentials: CORP\dlp-sp-scanner
Scope: Document Libraries Only
Include Sub-Sites: Yes
Include Version History: No
File Types: .docx, .xlsx, .pdf, .csv, .pptx
Schedule: Weekly, Sunday, 03:00 AM, Incremental
Policy Group: PII + HIPAA Policy Group
```

**Example: Full intranet audit for GDPR**
```
Target Name: SharePoint Full Intranet - GDPR Quarterly Audit
URL: https://sharepoint.corp.local
Site Collections: [Add All] (every site collection)
Authentication: Kerberos
Scope: Document Libraries + Lists
Include Sub-Sites: Yes
Include Version History: Yes (required for audit)
Schedule: First Sunday of each quarter, Full Scan
Policy Group: GDPR Compliance Group
```

**Example: SharePoint Online via CloudSOC**
```
Platform: CloudSOC Console (not Enforce Console)
Cloud App: Microsoft 365 SharePoint Online
Scope: All site collections in Finance tenant
DLP Profile: PCI DSS Cloud Profile
Schedule: Continuous (real-time for new uploads) + Monthly full scan
Actions: Remove external sharing + Notify site admin
```

### 1.3 Exchange / Mailbox Targets -- Detailed Configuration

#### UI Navigation

```
Enforce Console > Manage > Discover > Discover Targets > New Target > Exchange
```

#### Configuration Detail

| Setting | Options | Notes |
|---------|---------|-------|
| Connection Type | MAPI, EWS | EWS recommended for Exchange 2016+ and Exchange Online hybrid |
| Mailbox Selection | Individual mailboxes, Distribution Groups, OU-based | Distribution Group selection is most efficient for large deployments |
| Content Scope | Mail Items, Calendar, Contacts, Tasks | Mail Items only for most DLP use cases |
| Date Range | All, Last N days, Custom range | Limit to reduce scan time (e.g., last 365 days) |
| PST Scanning | Via file system target | Mount PST files as file share; scan as file system target |
| Journal Mailbox | Special configuration | Scan the journal mailbox to catch all email that passed through Exchange |

#### Example: Executive Mailbox PCI Audit

```
Target Name: C-Suite Mailboxes - PCI Quarterly
Connection: EWS
Exchange Server: https://mail.corp.local/EWS/Exchange.asmx
Mailboxes: CEO, CFO, CTO, COO, General Counsel (individual selection)
Credentials: CORP\dlp-exchange-svc (with ApplicationImpersonation)
Content: Mail Items only
Date Range: Last 180 days
Schedule: Quarterly, Full Scan
Policy Group: PCI DSS + Executive IP Protection
```

#### Example: Department-Wide HIPAA Scan

```
Target Name: Healthcare Dept Mailboxes - HIPAA Monthly
Connection: EWS
Mailboxes: Distribution Group "Healthcare-All-Staff" (250 mailboxes)
Content: Mail Items only
Date Range: Last 90 days
Schedule: Monthly, first Saturday, 01:00 AM
Policy Group: HIPAA PHI Detection
```

### 1.4 SQL Database Targets -- Detailed Configuration

#### UI Navigation

```
Enforce Console > Manage > Discover > Discover Targets > New Target > SQL Database
```

#### Database-Specific JDBC Configuration

| Database | JDBC Driver | Connection String Format | Default Port |
|----------|-------------|------------------------|--------------|
| Oracle | ojdbc8.jar / ojdbc11.jar | `jdbc:oracle:thin:@host:1521:SID` | 1521 |
| SQL Server | mssql-jdbc-*.jar | `jdbc:sqlserver://host:1433;databaseName=DB` | 1433 |
| DB2 | db2jcc4.jar | `jdbc:db2://host:50000/DB` | 50000 |
| MySQL | mysql-connector-java-*.jar | `jdbc:mysql://host:3306/DB` | 3306 |
| PostgreSQL | postgresql-*.jar | `jdbc:postgresql://host:5432/DB` | 5432 |

#### Scan Methods

| Method | Description | Use Case |
|--------|-------------|----------|
| **Table Selection** | Select specific tables and columns to scan | Known schema; targeted scan |
| **Schema Scan** | Scan all tables in a schema | Broad discovery of unknown PII locations |
| **Query-Based** | Custom SQL query defines scan scope | Complex filtering; joining tables; sampling |

#### Example: Customer CRM Database PCI Scan

```
Target Name: CRM Database - Credit Card Detection
Database: SQL Server
JDBC: jdbc:sqlserver://crm-db.corp.local:1433;databaseName=CRM_Production
Credentials: dlp_scanner_ro (SELECT only)
Method: Table Selection
Tables:
  - customers (all columns)
  - payments (card_number, card_expiry, card_holder)
  - orders (billing_address, payment_method)
Row Limit: 1,000,000 per table
Schedule: Weekly, Saturday, 04:00 AM
Policy Group: PCI DSS Policy Group
```

#### Example: HR Database SSN Discovery with Query

```
Target Name: HR Database - SSN in Non-Authorized Tables
Database: Oracle
JDBC: jdbc:oracle:thin:@hrdb.corp.local:1521:HRPROD
Credentials: dlp_hr_reader (SELECT only)
Method: Query-Based
Query:
  SELECT table_name, column_name, data
  FROM all_tab_columns
  WHERE table_name NOT IN ('EMPLOYEES', 'HR_MASTER')
  -- Scan all tables EXCEPT the authorized HR tables
  -- Purpose: Find SSNs that leaked to reporting/staging tables
Row Limit: 500,000
Schedule: Monthly
Policy Group: PII - SSN Detection
```

#### Example: Data Warehouse EU PII (GDPR)

```
Target Name: Enterprise DW - EU Personal Data Discovery
Database: DB2
JDBC: jdbc:db2://dw-host.corp.local:50000/ENTDW
Credentials: dlp_dw_ro
Method: Schema Scan
Schema: CUSTOMER_DATA (all tables)
Row Limit: 2,000,000 per table
Schedule: Monthly, first Saturday
Policy Group: GDPR - EU PII Detection (EU national IDs, IBAN, passport numbers)
```

### 1.5 Cloud Storage Targets -- Detailed Configuration

#### Supported Providers and Capabilities

| Provider | Scanning | Quarantine | Label | Remove Sharing | Encrypt | Notify |
|----------|----------|------------|-------|---------------|---------|--------|
| Box Enterprise | Yes | Yes | Yes | Yes | No | Yes |
| Dropbox Business | Yes | Yes | Yes | Yes | No | Yes |
| Google Drive (Workspace) | Yes | Yes | Yes | Yes | No | Yes |
| Microsoft OneDrive/SharePoint Online | Yes | Yes | Yes (MIP) | Yes | Yes (MIP) | Yes |
| Salesforce | Yes | Yes | No | No | No | Yes |

#### CloudSOC DLP Profile Configuration

```
CloudSOC Console > Protect > DLP Profiles > New Profile
```

**Profile fields:**
| Field | Description |
|-------|-------------|
| Profile Name | Name for the cloud DLP profile |
| Data Identifiers | Select from 200+ built-in or create custom |
| Detection Rules | Keyword, regex, data identifier, proximity |
| Severity Mapping | Map rule matches to severity levels |
| Response Actions | Quarantine, label, remove sharing, notify |
| Target Cloud Apps | Which cloud applications this profile applies to |

#### Example: Box Enterprise PCI Scanning

```
CloudSOC Profile: PCI-DSS-Box-Scan
Data Identifiers:
  - Credit Card Number (Luhn validated)
  - Credit Card Magnetic Stripe
  - PCI Data (combined identifier)
Target: Box Enterprise - All users in "Finance" department
Schedule: Continuous (real-time) + Weekly full scan
Actions:
  On High severity: Quarantine to admin folder + Notify user + Notify DLP team
  On Medium severity: Notify user + Add "PCI Violation" tag
  On Low severity: Log only
```

#### Example: Microsoft 365 GDPR Scanning

```
CloudSOC Profile: GDPR-M365-Scan
Data Identifiers:
  - EU National ID Numbers (all countries)
  - IBAN Account Numbers
  - EU Passport Numbers
  - EU Driver License Numbers
Target: Microsoft 365 OneDrive + SharePoint Online - EU office users
Schedule: Continuous + Monthly full scan
Actions:
  On violation: Apply MIP "Confidential" label + Remove external sharing + Notify data owner
```

### 1.6 Lotus Notes Database Targets

#### Configuration

```
Target Name: Notes Archive - PII Discovery
Server: domino01.corp.local
Database Paths:
  - hr\personnel.nsf
  - finance\expenses.nsf
  - legal\contracts.nsf
Credentials: Notes ID with Reader access
Schedule: Monthly
Policy Group: PII + PCI Combined
```

**Note:** Lotus Notes/Domino is legacy. Many organizations are migrating to Exchange/M365. Scan to identify and migrate sensitive content before decommissioning.

---

## 2. High Speed Discovery (DLP 16.1+)

### What It Is

High Speed Discovery is an optimized scanning mode for file system (CIFS/SMB) targets that dramatically improves throughput -- up to **1 TB per hour** compared to standard scanning speeds.

### How It Works

1. Standard scanning: Discover server reads file content over SMB, extracts text, runs detection -- sequential per file
2. High Speed Discovery: Parallel file enumeration, batched content extraction, multi-threaded detection pipeline
3. Optimization: Metadata-first filtering (skip files by type/size/age before downloading content)

### Enabling High Speed Discovery

1. Navigate to **Manage > Discover > Discover Targets > [target] > Advanced Tab**
2. Check **Enable High Speed Discovery**
3. Save and restart the scan

### Limitations

| Limitation | Detail |
|------------|--------|
| Target types | File System (CIFS/SMB) only -- not SharePoint, Exchange, databases |
| DLP version | 16.1+ required |
| MIP labeling | High Speed Discovery supports MIP label detection AND application (16.1+) |
| OCR | OCR still available but may reduce throughput |
| Incremental | Compatible with incremental scanning |

### Performance Comparison

| Metric | Standard Scanning | High Speed Discovery |
|--------|-------------------|---------------------|
| Throughput | 100-200 GB/hour | Up to 1 TB/hour |
| CPU utilization | 40-60% | 80-95% |
| Network utilization | Moderate | High |
| Memory | 4-8 GB | 8-16 GB recommended |
| Best for | Small targets, mixed target types | Large file shares (1 TB+) |

---

## 3. MIP Label Detection and Application

### Reading MIP Labels During Discovery

Starting with DLP 16.0, Network Discover can **read** Microsoft Information Protection (MIP) sensitivity labels on files:

- Detection rule condition: "Content Matches MIP Tag Rule"
- Policies can trigger based on label presence, absence, or specific label value
- Example: "Alert if file labeled 'Highly Confidential' is found on a non-secured file share"

### Writing MIP Labels During Discovery (16.1+)

With High Speed Discovery enabled (16.1+), Network Discover can **apply** MIP labels:

1. Create a response rule with action "Apply Classification Label"
2. Map DLP policy violations to MIP label IDs
3. When Discover finds a violation, it applies the MIP label to the file
4. MIP-aware applications (Office 365, SharePoint) then enforce the label's protections

### Configuration Steps

1. **Install MIP SDK Connector** on the Enforce Server
2. **Configure Azure AD app registration** with MIP SDK permissions
3. **Map labels** in the Enforce Console: System > Settings > MIP Configuration
4. **Create response rule**: Apply Classification Label > Select MIP label
5. **Associate** response rule with discovery policies
6. **Enable High Speed Discovery** on file system targets

---

## 4. Endpoint Discover vs. Network Discover

| Feature | Network Discover | Endpoint Discover |
|---------|-----------------|-------------------|
| **Runs on** | Dedicated Network Discover Server | DLP Agent on endpoint |
| **Scanning** | Remote scanning over network (SMB, HTTPS, JDBC) | Local disk scanning |
| **Scheduling** | Console-managed: one-time, recurring, continuous | Manual start/stop only (no scheduling) |
| **Scope** | File shares, SharePoint, Exchange, databases, cloud | Local drives only (no network, no removable media) |
| **Throughput** | High (server-class hardware, High Speed Discovery) | Limited by endpoint CPU/RAM |
| **Protect Actions** | Quarantine, encrypt, DRM, label, copy | Tag, notify only |
| **Incremental** | Yes (automatic cache-based) | Yes |
| **Platforms** | Windows, Linux (Discover Server) | Windows, macOS, Linux (Agent) |
| **Use Case** | Centralized scanning of enterprise repositories | Scanning laptop/desktop local drives |

**When to use which:**
- **Network Discover**: File servers, SharePoint, Exchange, databases, NAS, cloud storage -- anything accessible over the network
- **Endpoint Discover**: Laptops with local data (sales reps, executives, remote workers) that may store sensitive files locally

---

## 5. Multi-Server Discovery Architecture

### When to Deploy Multiple Discover Servers

| Scenario | Recommendation |
|----------|---------------|
| Scanning > 10 TB of data | Multiple Discover servers for parallel scanning |
| Geographically distributed targets | Discover server per region (reduce WAN traffic) |
| DFS scanning required | At least one Windows Discover server |
| Mixed target types | Dedicated server per target type for performance isolation |
| Cloud + on-prem | Separate Cloud Storage Discover Server for cloud targets |

### Architecture Example: Global Enterprise

```
                        +-------------------+
                        |   Enforce Server   |
                        |   (Headquarters)   |
                        +--------+----------+
                                 |
          +----------------------+----------------------+
          |                      |                      |
+---------v--------+   +---------v--------+   +---------v--------+
| Discover Server  |   | Discover Server  |   | Cloud Storage    |
| US East          |   | EU (London)      |   | Discover Server  |
| Windows (DFS)    |   | Linux            |   | (Cloud targets)  |
+--------+---------+   +--------+---------+   +--------+---------+
         |                      |                      |
  US File Shares         EU File Shares         Box, OneDrive,
  US SharePoint          EU SharePoint          Google Drive,
  US Exchange            EU Exchange            Dropbox
  US Databases           EU Databases
```

### Policy Group Assignment

Each Discover server can be assigned a different policy group:
- US Discover: "US PII + PCI" policy group
- EU Discover: "GDPR + US PII + PCI" policy group (GDPR applies in EU)
- Cloud Discover: "Cloud DLP" policy group

---

## 6. Content Filtering Advanced Configuration

### Filter Precedence

Filters are evaluated in this order:
1. **Path Include** -- Only paths matching this pattern are entered
2. **Path Exclude** -- Paths matching this pattern are skipped (even if they matched Include)
3. **File Type Include** -- Only files of these types are read
4. **File Type Exclude** -- Files of these types are skipped
5. **File Size** -- Files outside min/max range are skipped
6. **File Age** -- Files older than the cutoff are skipped

### Advanced Filter Patterns

| Pattern | Meaning | Example |
|---------|---------|---------|
| `*.docx` | All Word documents | Include only Word files |
| `*.xlsx,*.csv` | Multiple types (comma-separated) | Spreadsheets and CSV files |
| `\confidential\` | Path contains "confidential" | Target sensitive directories |
| `\temp\,\cache\,\$Recycle.Bin\` | Exclude temp/cache/recycle | Skip non-productive content |
| Modified after 2025-01-01 | Files modified in current year | Skip old archival data |

### Recommended Filter Profiles

**Profile: Office Documents Only (Fast)**
```
Include Types: .docx, .xlsx, .pptx, .pdf, .csv, .txt, .rtf
Exclude Paths: \temp\, \cache\, \$Recycle.Bin\, \Windows\
Max Size: 100 MB
```

**Profile: All Content (Thorough)**
```
Include Types: * (all)
Exclude Types: .exe, .dll, .sys, .msi, .cab, .wim, .iso
Exclude Paths: \Windows\, \Program Files\, \$Recycle.Bin\
Max Size: 500 MB
```

**Profile: Image-Focused (OCR)**
```
Include Types: .jpg, .jpeg, .png, .tiff, .bmp, .gif, .pdf
Exclude Paths: \thumbnails\, \cache\
Max Size: 50 MB
Note: Requires OCR/Sensitive Image Recognition license
```

---

## 7. Network Protect Deep Dive

### Protect Action Configuration

Network Protect actions are configured as **response rules** associated with policies in the Discover server's policy group.

#### Quarantine Action Detail

```
Manage > Policies > Response Rules > New > Automated Response
```

Configuration:
| Field | Description | Example |
|-------|-------------|---------|
| Action Type | Quarantine File | -- |
| Quarantine Path | UNC path to quarantine location | `\\quarantine-server\dlp-quarantine\` |
| Quarantine Subfolder | Organize quarantined files | `{Year}\{Month}\{PolicyName}\` |
| Breadcrumb File | Template for the file left in place | See template below |
| Breadcrumb Extension | Extension appended to original name | `.quarantined.txt` |
| Preserve Path | Maintain directory structure in quarantine | Yes |
| Credentials | Write credentials for quarantine location | `CORP\dlp-quarantine-svc` |

**Breadcrumb file template:**
```
NOTICE: This file has been quarantined by the Data Loss Prevention system.

Original File: {OriginalFileName}
Quarantine Date: {Date}
Policy Violated: {PolicyName}
Incident ID: {IncidentID}
Severity: {Severity}

This file contained sensitive data that violates corporate data handling policies.
To request file restoration, contact: dlp-team@corp.com
Reference this Incident ID in your request.
```

#### Encrypt-in-Place Action

| Field | Description |
|-------|-------------|
| Encryption Provider | MIP (Microsoft Information Protection) or third-party |
| Encryption Level | Map to MIP sensitivity label or encryption template |
| Key Management | Managed by MIP RMS or third-party KMS |
| Original File | Replaced with encrypted version in same location |
| User Experience | Authorized users can still open (MIP-integrated apps); unauthorized users see encrypted blob |

#### Copy-to-Secure-Location Action

| Field | Description |
|-------|-------------|
| Destination Path | UNC path for copies (e.g., `\\forensics\dlp-evidence\`) |
| Subfolder Template | `{Year}\{Month}\{IncidentID}\` |
| Preserve Metadata | Copy with original timestamps, permissions |
| Purpose | Forensic investigation; preserve evidence before remediation |

#### DRM (Digital Rights Management) Action

| Field | Description |
|-------|-------------|
| DRM Provider | Microsoft RMS, Symantec IRM, or third-party |
| Rights Template | Read-only, No-print, No-forward |
| Application | Applied to the original file in place |
| Scope | Controls who can access the file post-DRM application |

### Quarantine Release Workflow

When a file is quarantined by mistake (false positive):

1. Remediation analyst reviews the incident in Enforce Console
2. Analyst determines the quarantine was incorrect (false positive)
3. Analyst clicks **Release** on the quarantine action in the incident detail
4. Network Protect moves the file from quarantine back to original location
5. The breadcrumb file is removed
6. Incident status is updated to "False Positive"

**Important:** Release requires the write credentials configured in the scan target to be valid and the original path to still exist.

---

## 8. API Automation Patterns

### Pattern 1: Infrastructure-as-Code Scan Target Management

```bash
#!/bin/bash
# deploy-discovery-targets.sh
# Create discovery scan targets from a configuration file

ENFORCE="https://enforce.corp.local"
CREDS="api-user:api-password"

# Read targets from JSON config
for target in $(cat discovery-targets.json | jq -c '.targets[]'); do
  name=$(echo $target | jq -r '.name')
  type=$(echo $target | jq -r '.type')
  paths=$(echo $target | jq -c '.paths')

  echo "Creating target: $name"

  curl -s -u "$CREDS" \
    -X POST \
    -H 'Content-Type: application/json' \
    -d "$target" \
    "$ENFORCE/ProtectManager/webservices/v2/discover/targets"
done
```

### Pattern 2: Discovery Results Export for Compliance

```bash
#!/bin/bash
# export-discovery-findings.sh
# Export all discovery incidents from the last quarter

ENFORCE="https://enforce.corp.local"
CREDS="api-user:api-password"

curl -s -u "$CREDS" \
  -X POST \
  -H 'Content-Type: application/json' \
  -d '{
    "savedReportId": 0,
    "incidentCreationDateGreaterThan": "2026-01-01T00:00:00Z",
    "incidentCreationDateLessThan": "2026-03-31T23:59:59Z",
    "filters": {
      "filterType": "AND",
      "filters": [
        {
          "filterType": "booleanFilter",
          "filterName": "detectionServerType",
          "filterValue": "DISCOVER"
        }
      ]
    }
  }' \
  "$ENFORCE/ProtectManager/webservices/v2/incidents" \
  | jq '.' > discovery-findings-Q1-2026.json
```

### Pattern 3: Bulk Target Update (Credential Rotation)

```bash
#!/bin/bash
# rotate-credentials.sh
# Update credentials on all discovery targets after password rotation

ENFORCE="https://enforce.corp.local"
CREDS="api-user:api-password"
NEW_SCAN_PASSWORD="new-service-account-password"

# Get all targets
targets=$(curl -s -u "$CREDS" \
  "$ENFORCE/ProtectManager/webservices/v2/discover/targets" \
  | jq -r '.targets[].id')

for id in $targets; do
  echo "Updating credentials for target $id"
  curl -s -u "$CREDS" \
    -X PUT \
    -H 'Content-Type: application/json' \
    -d "{
      \"credentials\": {
        \"username\": \"CORP\\\\dlp-scanner-svc\",
        \"password\": \"$NEW_SCAN_PASSWORD\"
      }
    }" \
    "$ENFORCE/ProtectManager/webservices/v2/discover/targets/$id"
done
```

---

## 9. Performance Tuning Reference

### Tuning Parameters [S17]

| Parameter | Location | Default | Range | Impact |
|-----------|----------|---------|-------|--------|
| Concurrent Connections | Target > Advanced | 10 | 1-100 | Higher = faster scan, more load on target |
| Thread Count | Discover server config | Auto | 1-32 | Match to CPU cores |
| Scan Buffer Size | Discover server config | 4 MB | 1-64 MB | Larger = fewer I/O ops |
| Content Extraction Timeout | Discover server config | 120s | 30-600s | Increase for complex documents |
| Max File Size for Detection | Discover server config | 100 MB | 1-1000 MB | Skip very large files |
| Index Cache Location | Discover server config | Local disk | SSD path | SSD dramatically improves incremental |

### Performance Benchmarks [S17]

| Target Type | Concurrent Connections | Files/Hour | GB/Hour | Notes |
|-------------|----------------------|------------|---------|-------|
| CIFS (Standard) | 10 | 50,000-100,000 | 100-200 | Average file size 2 MB |
| CIFS (High Speed) | 20 | 200,000-500,000 | 500-1000 | DLP 16.1+ only |
| SharePoint | 5 | 10,000-30,000 | 20-60 | Subject to SP throttling |
| Exchange (EWS) | 3 | 5,000-15,000 | 10-30 | Per mailbox batch |
| Database | 1 | 100,000-500,000 rows/hr | N/A | Depends on row width |
| Cloud (via CDS) | Managed | Varies | Varies | Cloud provider rate limits apply |

### Tuning Workflow

1. **Baseline**: Run first scan with defaults; note duration, throughput, error count
2. **Identify bottleneck**: CPU (increase threads), Network (adjust connections), Disk (use SSD)
3. **Adjust one parameter at a time** and re-scan
4. **Monitor target impact**: Check file server CPU/disk/network during scan
5. **Optimize filters**: Exclude file types that never contain sensitive data
6. **Enable High Speed Discovery** for CIFS targets (single biggest improvement)

---

## 10. Discovery Reporting

### Built-in Discovery Reports

| Report | Navigation | Content |
|--------|------------|---------|
| Discover Incidents | Incidents > Discover/Network | All incidents from discovery scans |
| Discover Summary | Incidents > Dashboards > Discovery | Aggregated view: incidents by target, policy, severity |
| Data Inventory | Custom report | Where sensitive data was found (by file server, share, path) |
| Remediation Status | Custom report | Quarantine/encrypt/label actions taken and their status |

### Custom Discovery Report

1. Navigate to **Incidents > Discover/Network**
2. Set filters:
   - Date range: Last 90 days
   - Severity: High and Critical
   - Status: All
3. Click **Save As** to save as a custom report
4. Name: "Discovery - High Severity - Last 90 Days"
5. Set visibility: Shared (visible to other DLP admins)
6. Schedule delivery: Weekly email to compliance team

### Exporting Discovery Data

| Method | Format | Use Case |
|--------|--------|----------|
| Console Export | CSV | Ad-hoc reporting, Excel analysis |
| REST API Export | JSON | Automated reporting pipelines, SIEM integration |
| Syslog | CEF/Syslog | SIEM real-time feed of discovery findings |
| Scheduled Report | Email (CSV/PDF) | Regular compliance reports to stakeholders |

---

## 11. Integration with Data Insight

### Symantec Data Insight + Network Discover [S12]

Data Insight integration enriches discovery results with data governance context:

| DLP Provides | Data Insight Provides |
|-------------|----------------------|
| Sensitive file identification | File ownership information |
| Policy violation details | Access permissions analysis |
| Remediation actions | Data custodian identification |
| Content classification | Usage analytics (who accessed, when, how often) |

### Integration Benefits

1. **Data ownership resolution**: Discovery finds sensitive file -> Data Insight identifies the owner -> Incident assigned to the correct person
2. **Access risk analysis**: Discovery finds PCI data on a share -> Data Insight shows 500 users have access -> Prioritize remediation
3. **Self-service remediation**: Data owners receive Data Insight Self-Service Portal notifications about sensitive files in their areas
4. **Open access reporting**: Identify files with sensitive data AND overly broad access permissions

### Configuration

1. Install and configure Veritas Data Insight
2. Configure bidirectional integration in Enforce Console: System > Settings > Data Insight
3. Data Insight scans shares for access metadata
4. Network Discover scans shares for sensitive content
5. Integration correlates findings by file path

---

## 12. Troubleshooting Reference

### Common Issues and Resolution

| Symptom | Likely Cause | Resolution |
|---------|-------------|------------|
| Scan stuck at 0% | Credential failure | Verify credentials; test access from Discover server command line |
| Scan completes with 0 incidents | No policy violations found, OR wrong policy group | Verify policies exist in the assigned policy group; test with a known-sensitive file |
| Scan fails with "Connection refused" | Firewall blocking access | Verify port 445 (CIFS), 443 (SharePoint), or database port is open |
| Scan extremely slow | Too many small files, no filtering | Add content filters; enable High Speed Discovery for CIFS |
| Duplicate incidents | Overlapping scan paths | Ensure no two targets scan the same path; review target configurations |
| "Content not available" on incidents | Encrypted files or unsupported format | Expected for encrypted files; check file format against 330+ supported types |
| Incremental scan as slow as full | Cache corruption | Delete scan cache and run one full scan to rebuild |
| SharePoint scan HTTP 429 errors | SharePoint throttling | Reduce concurrent connections; schedule off-peak |
| Database scan "out of memory" | BLOB columns too large | Set row/column size limits; increase Discover server heap |
| Cloud scan "Authorization required" | OAuth token expired | Re-authorize cloud app in CloudSOC admin |

### Log Files

| Log | Location | Content |
|-----|----------|---------|
| Discover scan log | `<install>/Protect/logs/debug/DiscoverScanLog.log` | Scan progress, file-level details |
| Detection log | `<install>/Protect/logs/debug/DetectionServerLog.log` | Policy evaluation results |
| Communication log | `<install>/Protect/logs/debug/CommunicationsLog.log` | Enforce-to-Discover communication |
| System events | Enforce Console > System > Servers and Detectors > Events | Server-level events and errors |

### Health Check Commands

```bash
# Verify Discover server is responsive (from Enforce server)
curl -k https://discover-server:8443/status

# Check disk space on Discover server (scan cache)
df -h /opt/Vontu/Protect/

# Monitor active network connections (during scan)
netstat -an | grep :445 | wc -l    # CIFS connections
netstat -an | grep :443 | wc -l    # SharePoint/Cloud connections

# Check scan cache size
du -sh /opt/Vontu/Protect/cache/
```

---

*End of advanced data discovery guide. Total coverage: 8 target types, 12 configuration areas, API automation, performance tuning, and troubleshooting.*
