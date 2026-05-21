# Data Discovery Workflow -- Broadcom Symantec DLP

> **Capability:** Network Discover / Network Protect -- scanning data at rest across the enterprise
> **Enforce Console Path:** Manage > Discover > Discover Targets
> **Detection Server Type:** Network Discover Server, Cloud Storage Discover Server
> **Sources:** [S1] Help Center 16.0, [S2] Help Center 25.1, [S4] Full PDF 16.0, [S17] Network Discover Tuning Guide 15.8, Video #11 (Deploy Detection Servers), API Intelligence Report

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [File Server Scanning (CIFS/SMB)](#3-file-server-scanning-cifssmb)
4. [SharePoint Scanning](#4-sharepoint-scanning)
5. [Exchange / Mailbox Scanning](#5-exchange--mailbox-scanning)
6. [Database Scanning](#6-database-scanning)
7. [Cloud Storage Scanning](#7-cloud-storage-scanning)
8. [Custom Targets](#8-custom-targets)
9. [Scan Configuration](#9-scan-configuration)
10. [Discovery Actions (Remediation)](#10-discovery-actions-remediation)
11. [Scan Target Management](#11-scan-target-management)
12. [API-Driven Discovery Management](#12-api-driven-discovery-management)
13. [End-to-End Workflow Summary](#13-end-to-end-workflow-summary)

---

## 1. Overview

Network Discover is the Symantec DLP component that finds sensitive data already sitting on file shares, databases, SharePoint sites, Exchange mailboxes, and cloud storage. It does not monitor data in transit -- it proactively scans data at rest.

**Why it matters:** Organizations accumulate years of sensitive data across thousands of repositories. Regulatory audits (PCI DSS Requirement 3, HIPAA, GDPR Article 30) demand that you know where sensitive data lives. Network Discover answers the question: "Where is our sensitive data right now?"

**Key distinction:**
- **Network Discover** = Scanning engine (finds sensitive data)
- **Network Protect** = Remediation engine (acts on what Discover found -- quarantine, encrypt, tag, apply DRM)

Both run on the same Network Discover Server but serve different purposes.

### What Network Discover Scans

| Target Type | Protocol | Read/Write | Typical Use |
|-------------|----------|------------|-------------|
| Windows File Shares | CIFS/SMB | Read (Discover) / Write (Protect) | File servers, NAS, DFS |
| NFS Shares | NFS | Read only | Linux/Unix file servers |
| SharePoint | HTTP/HTTPS | Read (Discover) / Write (Protect) | On-prem SharePoint |
| Exchange | MAPI/EWS | Read only | Mailbox content, PST archives |
| SQL Databases | JDBC | Read only | Oracle, SQL Server, DB2 |
| Lotus Notes | NRPC | Read only | Notes databases |
| Cloud Storage | REST/API | Read (Discover) / Write (Protect) | Box, Dropbox, Google Drive, OneDrive |
| Custom/SFTP | Various | Varies | Documentum, custom repositories |

### Detection Capabilities During Discovery

Network Discover applies the **full detection engine** to scanned content:
- Described Content Matching (DCM) -- keywords, regex, data identifiers (30+ built-in)
- Exact Data Matching (EDM) -- fingerprinted structured data
- Indexed Document Matching (IDM) -- fingerprinted documents, partial matching
- Vector Machine Learning (VML) -- statistical content classification
- Optical Character Recognition (OCR) -- text from images in scanned files
- Form Recognition -- scanned tax forms, medical forms, applications
- MIP Label Detection -- Microsoft Information Protection sensitivity labels (DLP 16.1+)
- 330+ file types recognized by binary signature

---

## 2. Architecture

### Component Layout

```
                   +-------------------+
                   |   Enforce Server   |
                   | (Policy + Incident |
                   |   Management)     |
                   +--------+----------+
                            |
              +-------------+-------------+
              |                           |
    +---------v----------+    +-----------v----------+
    | Network Discover   |    | Cloud Storage        |
    | Server             |    | Discover Server      |
    | (On-Prem Targets)  |    | (Cloud Targets)      |
    +----+------+--------+    +----------+-----------+
         |      |                        |
    +----v-+ +--v----+            +------v-------+
    | CIFS | | Share- |           | Box/GDrive/  |
    | NFS  | | Point  |           | OneDrive/    |
    | DFS  | | Exch.  |           | Dropbox      |
    +------+ | DB/SQL |           +--------------+
             +--------+
```

### How a Discovery Scan Executes

1. **Admin creates scan target** in Enforce Console (or via REST API in DLP 25.1+)
2. **Admin configures policies** in the policy group assigned to the Discover server
3. **Admin starts the scan** (manual trigger, schedule, or API)
4. **Network Discover Server** connects to the target using configured credentials
5. **Server enumerates** files/records in scope (filtered by path, file type, size, age)
6. **Content extraction** -- text extracted from each file (330+ formats supported)
7. **Detection engine** applies all policies in the assigned policy group
8. **Incidents created** for each policy violation found
9. **Network Protect actions** execute on files with violations (if configured)
10. **Results** appear in Enforce Console under Incidents > Discover/Network

### Sizing Guidelines [S17]

| Metric | Guideline |
|--------|-----------|
| Throughput | Up to 1 TB/hour with High Speed Discovery (DLP 16.1+) |
| Concurrent scans | Multiple targets can scan simultaneously |
| Memory per scan | 4-8 GB RAM recommended per concurrent scan target |
| Network bandwidth | Depends on target -- CIFS scans pull file content over network |
| Incremental scan benefit | 80-95% reduction in scan time after initial full scan |

---

## 3. File Server Scanning (CIFS/SMB)

File server scanning is the most common Network Discover use case. It scans Windows file shares (CIFS/SMB), NFS exports, and DFS namespaces for sensitive content.

### Navigation

```
Enforce Console > Manage > Discover > Discover Targets > New Target > File System
```

### Configuration Fields

| Field | Required | Description | Example Value |
|-------|----------|-------------|---------------|
| Target Name | Yes | Descriptive name for the scan | "HR File Share - Weekly PII Scan" |
| Discover Server | Yes | Which Network Discover server runs this scan | "discover-server-01.corp.local" |
| Policy Group | Yes | Which policies to evaluate against | "PCI + PII Policy Group" |
| Scan Type | Yes | File System (CIFS), NFS, or DFS | "File System" |
| Server/Share Root(s) | Yes | UNC paths to scan | `\\fileserver01\hr-data\` |
| Credentials | Yes | Domain account with read access to shares | "CORP\dlp-scanner-svc" |
| Content Filters | No | File type, size, age restrictions | "*.docx, *.xlsx, *.pdf; <100MB; modified within 365 days" |
| Schedule | No | When to run the scan | "Every Sunday at 02:00 AM" |
| Incremental | No | Only scan new/modified files since last scan | Enabled (recommended after first full scan) |
| Bandwidth Throttle | No | Max concurrent connections / bandwidth cap | "10 concurrent connections" |

### Step-by-Step: Create a File Share Scan Target

1. Navigate to **Manage > Discover > Discover Targets**
2. Click **New Target**
3. Select **File System** as the target type
4. Enter a **Target Name** (e.g., "Finance File Server - PCI Weekly")
5. Select the **Network Discover Server** that will execute this scan
6. Select the **Policy Group** containing the policies to evaluate
7. Under **Scan Paths**, click **Add** and enter UNC paths:
   - `\\fs-finance-01.corp.local\accounting\`
   - `\\fs-finance-01.corp.local\payroll\`
8. Under **Credentials**, enter the service account:
   - Username: `CORP\dlp-scanner-svc`
   - Password: (stored encrypted in Enforce database)
9. Under **Content Filters**, optionally restrict:
   - File types: Include only `.docx`, `.xlsx`, `.pdf`, `.csv`
   - File size: Maximum 100 MB
   - File age: Modified within last 365 days
10. Under **Schedule**, set:
    - Recurring: Weekly
    - Day: Sunday
    - Time: 02:00 AM
    - Enable Incremental: Yes
11. Click **Save**
12. Optionally click **Start** to run immediately

### Examples

**Example 1: Scan HR file share for SSNs weekly**
- Target Name: "HR Server - SSN Detection"
- Scan Paths: `\\hr-fileserver\employee-records\`, `\\hr-fileserver\benefits\`
- Policy Group: "PII Detection Group" (contains SSN data identifier policy)
- Schedule: Every Sunday at 01:00 AM, incremental
- Content Filter: `.docx`, `.xlsx`, `.pdf`, `.csv`, `.txt`

**Example 2: Scan engineering shares for source code leakage**
- Target Name: "Engineering - Confidential Code Scan"
- Scan Paths: `\\eng-nas\projects\`, `\\eng-nas\prototypes\`
- Policy Group: "IP Protection Group" (contains IDM profiles for confidential docs, VML for source code)
- Schedule: Daily at 03:00 AM, incremental
- Content Filter: All file types, max 500 MB per file

**Example 3: Full PCI audit scan across all department shares**
- Target Name: "PCI DSS Quarterly Audit - All Shares"
- Scan Paths: `\\fileserver01\*`, `\\fileserver02\*`, `\\nas-cluster\*`
- Policy Group: "PCI DSS Compliance Group"
- Schedule: First Sunday of each quarter, full scan (not incremental)
- Content Filter: None (scan everything for audit completeness)

**Example 4: DFS namespace scan**
- Target Name: "DFS Root - Global Office Scan"
- Scan Paths: `\\corp.local\DFSRoot\offices\`
- Note: DFS scanning requires a **Windows-based** Network Discover Server
- Policy Group: "GDPR + PCI Combined Group"
- Schedule: Weekly, incremental

**Example 5: NFS share scan (Linux file server)**
- Target Name: "Linux Data Lake - PII Discovery"
- Scan Type: NFS
- Scan Paths: `/exports/data-lake/`, `/exports/analytics/`
- Server: `linux-nfs-01.corp.local`
- Policy Group: "PII Detection Group"
- Schedule: Weekly, incremental

### Gotchas -- File Server Scanning

| Issue | Impact | Mitigation |
|-------|--------|------------|
| **Credential expiry** | Scan fails silently when service account password expires | Use managed service accounts (gMSA) or set calendar reminders for credential rotation |
| **Large file shares (10+ TB)** | Initial full scan can take days, generate network load | Run first full scan on a weekend; enable incremental for subsequent scans; use bandwidth throttling |
| **Open file handles** | Files locked by users cannot be scanned | Schedule scans during off-hours; locked files are skipped and retried on next scan |
| **DFS requires Windows Discover Server** | DFS namespace resolution uses Windows-only APIs | Deploy a Windows-based Network Discover Server for DFS targets |
| **Deep directory trees** | Path length >260 characters causes scan failures on some targets | Monitor scan logs for path-too-long errors; pre-filter to shorter path roots |
| **Antivirus interference** | AV on the Discover server may scan every file pulled for inspection | Exclude the Discover server temp directory from AV scanning |
| **Incremental scan cache corruption** | Corrupted cache forces unintended full re-scan | Monitor scan duration; if incremental scan takes as long as full scan, rebuild cache |

---

## 4. SharePoint Scanning

### Navigation

```
Enforce Console > Manage > Discover > Discover Targets > New Target > SharePoint
```

### Configuration Fields

| Field | Required | Description | Example Value |
|-------|----------|-------------|---------------|
| Target Name | Yes | Descriptive name | "SharePoint Intranet - PII Scan" |
| SharePoint URL | Yes | Root URL of SharePoint farm | `https://sharepoint.corp.local` |
| Site Collections | Yes | Which site collections to scan | `/sites/hr`, `/sites/finance` |
| Credentials | Yes | Account with Read access to site collections | "CORP\dlp-sp-scanner" |
| Authentication | Yes | NTLM, Kerberos, or Claims | NTLM (most common for on-prem) |
| Content Filter | No | Document libraries, file types, metadata filters | "Document Libraries only; .docx, .xlsx, .pdf" |
| Include Versions | No | Scan document version history | Disabled (recommended for performance) |
| Schedule | No | Scan timing | "Weekly, Sundays at 03:00 AM" |

### Step-by-Step: Create a SharePoint Scan Target

1. Navigate to **Manage > Discover > Discover Targets > New Target > SharePoint**
2. Enter **Target Name**: "SharePoint HR Portal - PII Weekly"
3. Enter **SharePoint Web Application URL**: `https://sharepoint.corp.local`
4. Under **Site Collections**, click **Add**:
   - `/sites/human-resources`
   - `/sites/benefits`
   - `/sites/recruiting`
5. Under **Credentials**:
   - Authentication: NTLM
   - Username: `CORP\dlp-sp-scanner`
   - Password: (stored encrypted)
6. Under **Content Filters**:
   - Scan: Document Libraries only (skip lists, discussions)
   - File types: `.docx`, `.xlsx`, `.pdf`, `.csv`
7. Under **Schedule**: Weekly, Sunday 03:00 AM, incremental
8. Click **Save**

### Examples

**Example 1: Scan HR SharePoint for employee PII**
- Target: `https://sharepoint.corp.local/sites/hr`
- Content: All document libraries
- Policy Group: "PII + HIPAA Policy Group"
- Schedule: Weekly

**Example 2: Scan finance SharePoint for PCI data**
- Target: `https://sharepoint.corp.local/sites/finance`
- Content: "Invoices" and "Statements" libraries only
- Policy Group: "PCI DSS Policy Group"
- Schedule: Daily, incremental

**Example 3: Full intranet scan for GDPR compliance audit**
- Target: `https://sharepoint.corp.local` (all site collections)
- Content: All document libraries across all sites
- Policy Group: "GDPR Compliance Group"
- Schedule: Monthly, full scan (not incremental)

### Gotchas -- SharePoint Scanning

| Issue | Impact | Mitigation |
|-------|--------|------------|
| **SharePoint throttling (HTTP 429)** | SharePoint rate-limits API calls; scan slows dramatically | Reduce concurrent connections; schedule during off-peak hours; contact SharePoint admin to increase limits |
| **Claims-based authentication** | Requires specific auth configuration that differs from NTLM | Test authentication separately before running scan; use NTLM if possible |
| **Version history scanning** | Scanning all versions multiplies scan time by 5-10x | Disable version scanning unless specifically required for audit |
| **Large document libraries (100K+ docs)** | Enumeration timeout before scan starts | Split into multiple targets by site collection |
| **Custom content types** | Custom SharePoint content types may not extract properly | Test with sample documents before production scan |

---

## 5. Exchange / Mailbox Scanning

### Navigation

```
Enforce Console > Manage > Discover > Discover Targets > New Target > Exchange
```

### Configuration Fields

| Field | Required | Description | Example Value |
|-------|----------|-------------|---------------|
| Target Name | Yes | Descriptive name | "Executive Mailboxes - PCI Scan" |
| Exchange Server | Yes | Exchange server hostname | "exchange01.corp.local" |
| Connection Type | Yes | MAPI or EWS (Exchange Web Services) | EWS (recommended for Exchange 2016+) |
| Mailbox Selection | Yes | Which mailboxes to scan | "Distribution Group: Finance-Team" or individual mailboxes |
| Credentials | Yes | Account with impersonation or full-access rights | "CORP\dlp-exchange-svc" |
| Content Scope | No | Mail items, calendar, contacts, tasks | "Mail Items only" |
| Date Range | No | Only scan messages within a date range | "Last 365 days" |
| PST Files | No | Include PST archives if mounted | Enabled/Disabled |
| Schedule | No | Scan timing | "Monthly, first Saturday at 01:00 AM" |

### Step-by-Step: Create an Exchange Scan Target

1. Navigate to **Manage > Discover > Discover Targets > New Target > Exchange**
2. Enter **Target Name**: "Finance Team Mailboxes - PCI Monthly"
3. Enter **Exchange Server**: `exchange01.corp.local`
4. Select **Connection Type**: EWS
5. Under **Mailbox Selection**:
   - Method: Active Directory Group
   - Group: "Finance-Team"
   - (Alternatively, enter individual mailbox addresses)
6. Under **Credentials**:
   - Username: `CORP\dlp-exchange-svc`
   - Password: (stored encrypted)
   - Permission: ApplicationImpersonation role required
7. Under **Content Scope**:
   - Scan: Mail Items
   - Date Range: Messages from last 365 days
8. Under **Schedule**: Monthly, first Saturday, 01:00 AM
9. Click **Save**

### Examples

**Example 1: Scan executive mailboxes for PCI violations**
- Mailboxes: C-suite distribution group
- Date Range: Last 180 days
- Policy Group: "PCI DSS + Executive IP Protection"

**Example 2: Scan all mailboxes for HIPAA-protected data**
- Mailboxes: All users in "Healthcare" OU
- Date Range: Last 365 days
- Policy Group: "HIPAA PHI Detection"

**Example 3: Scan PST archive files**
- Target Type: PST files mounted on file share
- Path: `\\archive-server\pst-archives\`
- Policy Group: "PII + HIPAA + PCI Combined"
- Note: PST scanning is a variant of file system scanning -- point the file share scanner at the PST file locations

### Gotchas -- Exchange Scanning

| Issue | Impact | Mitigation |
|-------|--------|------------|
| **ApplicationImpersonation required** | Without this Exchange role, scan cannot read other users' mailboxes | Work with Exchange admin to grant role to service account |
| **EWS throttling** | Exchange throttles EWS requests; large mailbox scans time out | Reduce concurrent mailbox connections; split into smaller mailbox groups |
| **Journaling alternative** | Scanning mailboxes is resource-intensive; journaling captures in transit | Consider using Network Prevent for Email instead of retrospective mailbox scanning |
| **PST file detection** | PST files on file shares are a common source of uncontrolled email data | Combine file share scanning (for PSTs) with Exchange scanning (for live mailboxes) |

---

## 6. Database Scanning

### Navigation

```
Enforce Console > Manage > Discover > Discover Targets > New Target > SQL Database
```

### Configuration Fields

| Field | Required | Description | Example Value |
|-------|----------|-------------|---------------|
| Target Name | Yes | Descriptive name | "Customer DB - PCI Cardholder Scan" |
| Database Type | Yes | Oracle, SQL Server, DB2 | "SQL Server" |
| JDBC Connection | Yes | Connection string | `jdbc:sqlserver://db-server:1433;databaseName=CRM` |
| Credentials | Yes | Database account with SELECT access | "dlp_scanner" (DB user) |
| Table/Column Selection | Yes | Which tables and columns to scan | "customers.*, payments.card_number, payments.expiry" |
| Query-Based Scan | No | Custom SQL query defining scan scope | `SELECT * FROM customers WHERE region='EU'` |
| Row Limit | No | Maximum rows to scan per table | 1,000,000 |
| Schedule | No | Scan timing | "Weekly, Saturday at 04:00 AM" |

### Step-by-Step: Create a Database Scan Target

1. Navigate to **Manage > Discover > Discover Targets > New Target > SQL Database**
2. Enter **Target Name**: "CRM Database - PCI Card Data Scan"
3. Select **Database Type**: SQL Server
4. Enter **JDBC Connection String**: `jdbc:sqlserver://crm-db.corp.local:1433;databaseName=CRM_Production`
5. Under **Credentials**:
   - Username: `dlp_scanner_ro`
   - Password: (stored encrypted)
   - Note: This account needs SELECT-only permissions
6. Under **Table Selection**:
   - Method: Select Tables
   - Tables: `customers`, `payments`, `orders`
   - Columns: All (or specify `card_number`, `ssn`, `email` for targeted scan)
7. Optionally configure **Query-Based Scan**:
   - `SELECT customer_name, ssn, card_number, email FROM customers WHERE status='active'`
8. Under **Row Limit**: 500,000 per table
9. Under **Schedule**: Weekly, Saturday, 04:00 AM
10. Click **Save**

### Examples

**Example 1: Scan customer database for credit card numbers**
- Database: SQL Server CRM
- Tables: `payments`, `orders`, `customer_profiles`
- Policy: "PCI DSS - Credit Card Numbers" (uses credit card data identifier with Luhn check)
- Schedule: Weekly

**Example 2: Scan HR database for SSNs in non-authorized tables**
- Database: Oracle HRM
- Query: `SELECT * FROM emp_profiles UNION SELECT * FROM temp_reports`
- Policy: "PII - SSN Detection"
- Purpose: Find SSNs that leaked into reporting tables from the authorized HR tables

**Example 3: Scan data warehouse for EU personal data (GDPR)**
- Database: DB2 Enterprise Data Warehouse
- Tables: All tables in `customer_data` schema
- Policy: "GDPR - EU PII Detection" (EU national IDs, IBAN, passport numbers)
- Schedule: Monthly

### Gotchas -- Database Scanning

| Issue | Impact | Mitigation |
|-------|--------|------------|
| **JDBC driver compatibility** | Wrong JDBC driver version causes connection failures | Verify JDBC driver version matches database version; place driver JAR in correct Discover server directory |
| **Large table scans lock resources** | Full table scans can cause database performance degradation | Use query-based scans with WHERE clauses; schedule during maintenance windows; set row limits |
| **BLOB/CLOB columns** | Binary content in BLOB columns requires special handling | Ensure BLOB scanning is enabled in scan configuration; content extraction depends on format |
| **Encrypted columns** | TDE or column-level encryption prevents DLP from reading content | DLP scans post-decryption if connection uses proper credentials; discuss with DBA |
| **Read-only access critical** | Never give DLP write access to production databases | Create a dedicated read-only user with SELECT permission only |

---

## 7. Cloud Storage Scanning

### Navigation (On-Prem Enforce Console)

```
Enforce Console > Manage > Discover > Discover Targets > New Target > Cloud Storage
```

### Navigation (CloudSOC Console)

```
CloudSOC > Protect > DLP Profiles > Cloud Storage Scan
```

### Supported Cloud Targets

| Cloud Service | Scanning Method | Actions Available |
|---------------|----------------|-------------------|
| Box (Business/Enterprise) | CloudSOC API or Cloud Storage Discover Server | Quarantine, label, notify, remove sharing |
| Dropbox (Business) | CloudSOC API | Quarantine, label, notify |
| Google Drive (Workspace) | CloudSOC API | Quarantine, label, notify |
| Microsoft OneDrive (M365) | CloudSOC API | Quarantine, label, notify, apply MIP label |
| SharePoint Online | CloudSOC API | Quarantine, label, notify |
| Salesforce (files/attachments) | CloudSOC API | Quarantine, notify |

### Configuration Fields

| Field | Required | Description | Example Value |
|-------|----------|-------------|---------------|
| Target Name | Yes | Descriptive name | "Box Enterprise - PCI Scan" |
| Cloud Service | Yes | Which cloud provider | "Box" |
| Connection | Yes | OAuth/API credentials for cloud service | Box Enterprise API key |
| Scope | Yes | All users, specific users, specific folders | "All users in Finance department" |
| DLP Profile | Yes | Which DLP profile to scan with | "PCI DSS Cloud Profile" |
| Schedule | No | Scan frequency | "Daily, incremental" |

### Step-by-Step: Configure Cloud Storage Scanning via CloudSOC

1. Navigate to **CloudSOC Admin > DLP Configuration**
2. Ensure **Cloud Detection Service (CDS)** is enabled
3. Navigate to **Protect > DLP Profiles**
4. Create or select a DLP profile (e.g., "PCI DSS Cloud Profile")
5. Navigate to **Protect > Cloud Apps > Box** (or target cloud service)
6. Under **Scanning Configuration**:
   - Scope: All users (or specific groups via directory integration)
   - DLP Profile: "PCI DSS Cloud Profile"
   - Schedule: Continuous (real-time for new uploads) + weekly full scan
7. Under **Actions**:
   - On violation: Quarantine file + Notify user + Notify admin
8. Click **Enable**

### Examples

**Example 1: Scan Box Enterprise for credit card numbers in Finance folders**
- Cloud Service: Box Enterprise
- Scope: Finance department users
- DLP Profile: PCI DSS (credit card data identifier)
- Action: Quarantine to admin folder, notify user via email

**Example 2: Scan Google Drive for HIPAA-protected health records**
- Cloud Service: Google Workspace
- Scope: Healthcare division users
- DLP Profile: HIPAA PHI Detection
- Action: Remove external sharing, apply "Confidential" label

**Example 3: Scan OneDrive for MIP-labeled documents shared externally**
- Cloud Service: Microsoft 365 OneDrive
- Scope: All users
- DLP Profile: "MIP Confidential + External Share Detection"
- Action: Remove external link, notify data owner

### Gotchas -- Cloud Storage Scanning

| Issue | Impact | Mitigation |
|-------|--------|------------|
| **API rate limits** | Cloud providers throttle API calls; large tenants hit limits | CloudSOC manages throttling automatically; for very large tenants, extend scan windows |
| **OAuth token expiry** | Cloud connection tokens expire; scan stops until re-authorized | Set up token refresh alerts; CloudSOC handles auto-refresh for most providers |
| **Personal accounts mixed with corporate** | Users storing corporate data in personal cloud accounts cannot be scanned | Deploy Endpoint Prevent to catch uploads to personal cloud services |
| **Encrypted files in cloud** | Client-side encrypted files cannot be scanned | Policy to detect and flag encrypted files; require corporate encryption solutions with key escrow |

---

## 8. Custom Targets

### Supported Custom Target Types

| Target | Protocol | Notes |
|--------|----------|-------|
| SFTP Servers | SFTP (SSH File Transfer) | Requires SSH key or username/password |
| Documentum | DCTM API | Enterprise content management scanning |
| Lotus Notes | NRPC (Notes Remote Procedure Call) | Legacy Notes databases (.nsf files) |
| Local File Systems | Direct disk access | Windows, Linux, AIX, Solaris local drives |
| Custom File Systems | FlexResponse plugin | Extensible via custom Java plugins |

### SFTP Server Scanning

1. Navigate to **Manage > Discover > Discover Targets > New Target > File System**
2. Select connection type: SFTP
3. Enter SFTP server hostname and port (default 22)
4. Enter remote directory paths to scan
5. Provide SSH credentials (key-based or password)
6. Configure policy group and schedule

### Lotus Notes Database Scanning

1. Navigate to **Manage > Discover > Discover Targets > New Target > Lotus Notes**
2. Enter Domino server hostname
3. Specify database paths (`.nsf` files)
4. Provide Notes credentials
5. Configure policy group and schedule

### Local File System Scanning (Network Discover vs. Endpoint Discover)

**Network Discover** can scan local file systems on the Discover server itself or remote systems with appropriate access. For scanning local drives on user endpoints, use **Endpoint Discover** instead:

| Feature | Network Discover (Local FS) | Endpoint Discover |
|---------|---------------------------|-------------------|
| Runs on | Network Discover Server | DLP Agent on endpoint |
| Scheduling | Console-managed schedule | Manual start/stop only |
| Scope | Server-accessible file systems | Local drives only (no network, no removable) |
| Performance | High throughput (server-class hardware) | Limited by endpoint resources |
| Actions | Full Protect actions (quarantine, encrypt, DRM) | Tag, notify |

---

## 9. Scan Configuration

### 9.1 Full Scan vs. Incremental Scan

| Scan Mode | Description | When to Use |
|-----------|-------------|-------------|
| **Full Scan** | Scans every file/record in scope, regardless of prior scan history | First-ever scan of a target; quarterly audit scans; after policy changes |
| **Incremental Scan** | Only scans files modified since the last scan | All recurring scans after initial full scan; daily/weekly maintenance scans |

**How incremental scanning works:**
1. Network Discover maintains a scan cache (file path, modification timestamp, hash)
2. On incremental scan, Discover queries the target for file metadata
3. Only files with changed timestamps or new files are pulled for content inspection
4. Deleted files are removed from incident tracking
5. Result: 80-95% reduction in scan time and network load

### 9.2 Scan Scheduling

| Schedule Type | Description | Example |
|---------------|-------------|---------|
| **One-Time** | Runs once when manually started | Initial discovery scan |
| **Recurring** | Runs on a defined schedule (daily, weekly, monthly) | Weekly PCI compliance scan |
| **Continuous** | Runs indefinitely, restarting immediately after completion | High-priority data repositories |

**Configuration path:** Discover Target > Schedule tab

Schedule fields:
- Start date and time
- Recurrence pattern (daily, weekly, monthly)
- End date (optional)
- Incremental enabled (checkbox)

### 9.3 Content Filtering

Content filters reduce scan scope to improve performance and relevance.

| Filter Type | Description | Example |
|-------------|-------------|---------|
| **File Type Include** | Only scan specific file types | `.docx, .xlsx, .pdf, .csv, .txt` |
| **File Type Exclude** | Skip specific file types | `.exe, .dll, .sys, .log` |
| **File Size Maximum** | Skip files larger than threshold | 100 MB (skip large media files) |
| **File Size Minimum** | Skip files smaller than threshold | 1 KB (skip empty/tiny files) |
| **File Age** | Only scan files modified within a date range | "Modified within last 365 days" |
| **Path Include** | Only scan files within specific paths | `\confidential\`, `\hr\` |
| **Path Exclude** | Skip specific subdirectories | `\temp\`, `\cache\`, `\backup-archive\` |

### 9.4 Performance Tuning [S17]

| Setting | Description | Default | Recommended |
|---------|-------------|---------|-------------|
| **Concurrent connections** | Max simultaneous connections to target | 10 | 5-20 depending on target capacity |
| **Bandwidth throttle** | Max network bandwidth consumed | Unlimited | Set during business hours; unlimited off-hours |
| **Thread count** | Content inspection threads on Discover server | Auto | Match to CPU cores (1 thread per core) |
| **Scan priority** | Relative priority when multiple scans run | Normal | Lower priority for large audit scans |
| **High Speed Discovery** | Optimized scanning for file systems (DLP 16.1+) | Disabled | Enable for CIFS targets; up to 1 TB/hour |

### 9.5 Scan Credentials Management

Each scan target requires credentials with appropriate access:

| Target Type | Minimum Permission | Credential Storage |
|-------------|-------------------|-------------------|
| CIFS/SMB | Read access to shares | Encrypted in Enforce database |
| SharePoint | Site Collection Reader | Encrypted in Enforce database |
| Exchange | ApplicationImpersonation role | Encrypted in Enforce database |
| Database | SELECT permission | Encrypted in Enforce database |
| NFS | Read access (UID-based) | Configured on Discover server |
| Cloud (via CloudSOC) | OAuth2 app credentials | CloudSOC credential store |

**Best practices:**
- Use dedicated service accounts (not personal accounts)
- Use managed service accounts (gMSA) where possible for automatic password rotation
- Grant minimum required permissions (read-only for Discover; read-write only for Protect actions)
- Separate read credentials from write credentials in targets that support both
- Set up monitoring for credential expiry

---

## 10. Discovery Actions (Remediation)

When Network Discover finds sensitive data, **Network Protect** can take automated or manual remediation actions on the files.

### Available Actions

| Action | Description | Requires Network Protect | Target Types |
|--------|-------------|------------------------|--------------|
| **Create Incident** | Log the finding as a DLP incident in the Enforce database | No | All |
| **Tag/Label** | Apply a metadata tag or MIP sensitivity label | Yes | File shares, SharePoint, Cloud |
| **Quarantine** | Move file to a secure quarantine location; leave breadcrumb file in original location | Yes | File shares, SharePoint |
| **Encrypt in Place** | Apply encryption to the file without moving it | Yes | File shares |
| **Copy to Secure Location** | Copy file to an investigation share for analysis | Yes | File shares |
| **Notify Data Owner** | Send email to the file owner (via LDAP lookup) | No | All |
| **Apply DRM** | Apply Digital Rights Management restrictions | Yes | File shares, SharePoint |
| **Apply Retention Policy** | Tag for retention/deletion per compliance schedule | Yes | SharePoint |
| **Remove Sharing** | Remove external or public sharing links | N/A (CloudSOC) | Cloud storage |

### Quarantine Workflow (File Shares)

1. Network Discover finds sensitive data in `\\fs01\hr\employee-ssn-list.xlsx`
2. Network Protect **moves** the file to quarantine location (e.g., `\\quarantine-server\dlp-quarantine\`)
3. A **breadcrumb file** is left at the original location:
   - `\\fs01\hr\employee-ssn-list.xlsx.quarantined.txt`
   - Contents: "This file has been quarantined by the DLP system. Contact dlp-team@corp.com for assistance. Reference: Incident #12345"
4. An **incident** is created in the Enforce Console with the quarantine action logged
5. The file owner receives an **email notification** (if configured)
6. A remediation analyst reviews the incident and either:
   - **Releases** the file back to original location (false positive)
   - **Permanently deletes** the file from quarantine (confirmed violation)
   - **Encrypts** the file and returns it (sensitive but authorized)

### Configuring Protect Actions

1. Navigate to **Manage > Policies > Response Rules**
2. Click **Add Response Rule > Automated Response**
3. Add **Condition**: Detection Server = Network Discover
4. Add **Action**: Quarantine File
5. Configure quarantine settings:
   - Quarantine directory path
   - Breadcrumb file template
   - Email notification template
6. Associate response rule with the policy
7. Deploy policy to the Discover server's policy group

### MIP Label Application (DLP 16.1+)

For environments using Microsoft Information Protection:

1. Configure MIP SDK connector on the Enforce Server
2. Create a response rule with action "Apply Classification Label"
3. Map DLP severity to MIP sensitivity labels:
   - High Severity violations -> "Highly Confidential" label
   - Medium Severity -> "Confidential" label
   - Low Severity -> "Internal" label
4. Network Discover applies labels to files scanned via High Speed Discovery
5. Labels persist on the file and are enforced by Microsoft 365 apps

---

## 11. Scan Target Management

### Monitoring Active Scans

**Navigation:** Manage > Discover > Discover Targets

The target list shows:
| Column | Description |
|--------|-------------|
| Target Name | Name of the scan target |
| Status | Running, Completed, Failed, Paused, Scheduled |
| Progress | Percentage complete (for running scans) |
| Files Scanned | Count of files inspected |
| Incidents Found | Count of policy violations detected |
| Last Scan Date | When the scan last completed |
| Next Scheduled | When the scan will next run (if recurring) |

### Scan Operations

| Operation | How | Notes |
|-----------|-----|-------|
| **Start** | Select target > Click Start | Manual trigger |
| **Stop** | Select target > Click Stop | Saves progress; can resume |
| **Pause** | Select target > Click Pause | Temporary halt; resumes from same point |
| **Resume** | Select target > Click Resume | Continues from pause point |
| **Delete** | Select target > Click Delete | Removes target configuration (incidents preserved) |
| **Edit** | Click target name | Modify paths, credentials, schedule |

### Scan History and Results

After a scan completes:

1. **Scan Summary**: Manage > Discover > Discover Targets > [target name] > Scan History
   - Total files scanned
   - Files with violations
   - Scan duration
   - Errors encountered (inaccessible files, credential failures)

2. **Incidents**: Incidents > Discover/Network
   - Filter by target name or scan date
   - View matched content, policy details, file location
   - Take remediation actions

3. **Remediation Tracking**: For targets with Protect actions
   - Track which files were quarantined, encrypted, or labeled
   - Verify remediation status (completed, pending, failed)
   - Release quarantined files if false positive

### Bulk Target Management

For enterprises with hundreds of scan targets:

1. **Import target list**: Upload CSV with target paths and configurations
2. **Clone targets**: Duplicate an existing target and modify paths
3. **API management (DLP 25.1+)**: Create/update/delete targets via REST API (see Section 12)

---

## 12. API-Driven Discovery Management

Starting with DLP 25.1, Network Discover scan targets can be managed via the Enforce Server REST API.

### Available API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/discover/targets` | List all scan targets |
| POST | `/discover/targets` | Create a new scan target |
| PUT | `/discover/targets/{id}` | Update an existing target |
| DELETE | `/discover/targets/{id}` | Delete a scan target |

### List All Scan Targets

```bash
curl -s -u 'admin:password' \
  -H 'Content-Type: application/json' \
  'https://enforce.corp.local/ProtectManager/webservices/v2/discover/targets' \
  | jq '.targets[]'
```

### Create a New File Share Scan Target

```bash
curl -s -u 'admin:password' \
  -X POST \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "HR File Share - PII Weekly",
    "type": "FILE_SYSTEM",
    "discoverServerId": 1,
    "policyGroupId": 3,
    "paths": [
      "\\\\fileserver01\\hr-data\\",
      "\\\\fileserver01\\benefits\\"
    ],
    "credentials": {
      "username": "CORP\\dlp-scanner-svc",
      "password": "SERVICE_ACCOUNT_PASSWORD"
    },
    "schedule": {
      "recurrence": "WEEKLY",
      "dayOfWeek": "SUNDAY",
      "timeOfDay": "02:00",
      "incremental": true
    }
  }' \
  'https://enforce.corp.local/ProtectManager/webservices/v2/discover/targets'
```

### Update a Scan Target

```bash
curl -s -u 'admin:password' \
  -X PUT \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "HR File Share - PII Weekly (Updated)",
    "paths": [
      "\\\\fileserver01\\hr-data\\",
      "\\\\fileserver01\\benefits\\",
      "\\\\fileserver01\\recruiting\\"
    ]
  }' \
  'https://enforce.corp.local/ProtectManager/webservices/v2/discover/targets/42'
```

### Delete a Scan Target

```bash
curl -s -u 'admin:password' \
  -X DELETE \
  'https://enforce.corp.local/ProtectManager/webservices/v2/discover/targets/42'
```

### Viewing Discover Scan Results via Incident API

Discover scan results appear as incidents. Query them with the incident API:

```bash
curl -s -u 'admin:password' \
  -X POST \
  -H 'Content-Type: application/json' \
  -d '{
    "savedReportId": 0,
    "incidentCreationDateGreaterThan": "2026-01-01T00:00:00Z",
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
  'https://enforce.corp.local/ProtectManager/webservices/v2/incidents'
```

### API Limitations

| Operation | API Support | Notes |
|-----------|------------|-------|
| List targets | Full (25.1+) | |
| Create targets | Full (25.1+) | |
| Update targets | Full (25.1+) | |
| Delete targets | Full (25.1+) | |
| Start/stop/pause scan | Not available | Console only |
| View scan progress | Not available | Console only |
| Scan schedule configuration | Partial | May be part of target config |
| View scan results | Via incident API | Discover incidents queried like any other incident |

---

## 13. End-to-End Workflow Summary

### Phase 1: Planning

1. **Inventory your data repositories** -- File servers, SharePoint sites, Exchange servers, databases, cloud storage
2. **Classify by sensitivity** -- Which repositories are most likely to contain sensitive data?
3. **Deploy Network Discover Server(s)** -- One or more, depending on geographic distribution and scan volume
4. **Create service accounts** -- Read-only accounts for each target type with appropriate permissions
5. **Verify network connectivity** -- Discover server must reach all targets on required ports

### Phase 2: Initial Discovery

6. **Create scan targets** for highest-priority repositories (start with HR/Finance file shares)
7. **Assign policy groups** with relevant detection policies (PCI, PII, HIPAA, etc.)
8. **Run full scans** on each target (schedule during off-hours)
9. **Review initial results** -- Expect high incident volumes on first run
10. **Tune policies** -- Adjust for false positives; add exceptions for known-good patterns

### Phase 3: Ongoing Operations

11. **Switch to incremental scans** for all recurring targets
12. **Enable Protect actions** (quarantine, encrypt, label) for confirmed-sensitive repositories
13. **Add new targets** as you discover additional repositories
14. **Schedule quarterly full scans** for compliance audit evidence
15. **Monitor credential expiry** and renew before scans fail
16. **Review scan performance** metrics and tune (concurrent connections, bandwidth, file filters)

### Phase 4: Compliance Reporting

17. **Generate Discovery reports** from Incidents > Discover/Network
18. **Export findings** for audit documentation
19. **Track remediation** -- Ensure quarantined files are reviewed and resolved
20. **Trend analysis** -- Compare scan results over time to measure risk reduction

---

*End of data discovery workflow. Total target types covered: 8+. For quickstart guide, see quickstart.md.*
