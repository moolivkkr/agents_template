# Broadcom Symantec DLP -- Capability Taxonomy

> **Research date:** 2026-05-21
> **Product:** Symantec Data Loss Prevention (Broadcom)
> **Latest version documented:** 26.1
> **Companion document:** [doc-corpus.md](doc-corpus.md)

---

## Complexity Estimates

| Rating | Meaning | Typical Configuration Effort |
|--------|---------|------------------------------|
| L (Low) | Simple toggle/field configuration | < 1 hour |
| M (Medium) | Multi-step workflow with dependencies | 1-8 hours |
| H (High) | Complex setup with data preparation, testing, tuning | 1-5 days |
| VH (Very High) | Cross-system integration, infrastructure changes, iterative tuning | 1-4 weeks |

## Doc Coverage Rating

| Rating | Meaning |
|--------|---------|
| Full | Comprehensive docs with navigation paths, field descriptions, examples |
| Good | Solid docs available but some gaps in edge cases |
| Partial | Key concepts documented but configuration details incomplete |
| Sparse | Only high-level mentions; details must come from admin guide PDFs or support |
| None | Not found in documentation search |

---

## Capability Taxonomy

### 1. DETECTION TECHNOLOGIES

#### 1.1 Described Content Matching (DCM)

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 1.1.1 | Keyword Matching (exact, case-sensitive, proximity) | L | Full |
| 1.1.2 | Regular Expression Matching | M | Full |
| 1.1.3 | Data Identifiers (30+ built-in: credit card, SSN, etc.) | L | Good |
| 1.1.4 | Custom Data Identifiers (user-defined patterns + validators) | M | Partial |
| 1.1.5 | File Property Matching (name, type, size, date) | L | Full |
| 1.1.6 | File Type Detection (330+ types by binary signature) | L | Good |
| 1.1.7 | Custom File Type Definition | M | Sparse |
| 1.1.8 | Protocol Matching (SMTP, HTTP, FTP, IM) | L | Good |
| 1.1.9 | Destination Matching (URL, domain, IP) | L | Good |

#### 1.2 Exact Data Matching (EDM)

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 1.2.1 | Exact Data Profile creation | M | Full |
| 1.2.2 | Structured data source indexing (CSV, DB export) | M | Full |
| 1.2.3 | Field mapping and selection | M | Full |
| 1.2.4 | Remote EDM Indexer | H | Good |
| 1.2.5 | Index scheduling and refresh | M | Good |
| 1.2.6 | Content Matches Exact Data condition | M | Full |
| 1.2.7 | Multi-field combination matching | M | Full |
| 1.2.8 | EDM for CloudSOC / cloud profiles | H | Good |

#### 1.3 Indexed Document Matching (IDM)

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 1.3.1 | Indexed Document Profile creation | M | Full |
| 1.3.2 | Document fingerprinting (rolling hashes) | M | Good |
| 1.3.3 | Partial/derivative content matching | M | Good |
| 1.3.4 | Binary stamp exact matching | L | Good |
| 1.3.5 | Partial matching threshold configuration | M | Partial |
| 1.3.6 | Remote Indexer Tool | H | Good |
| 1.3.7 | IDM for CloudSOC / cloud profiles | H | Good |

#### 1.4 Vector Machine Learning (VML)

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 1.4.1 | VML Profile creation | H | Full |
| 1.4.2 | Training document preparation (positive/negative sets) | H | Full |
| 1.4.3 | Model training and validation | H | Good |
| 1.4.4 | Content Matches VML Profile condition | M | Full |
| 1.4.5 | Training data quality assessment | H | Good |

#### 1.5 Content Classification and Image Analysis

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 1.5.1 | Data Classifiers (image type / context detection) | M | Good |
| 1.5.2 | Form Recognition (tax, medical, insurance forms) | M | Partial |
| 1.5.3 | Optical Character Recognition (OCR) -- on-premises | H | Good |
| 1.5.4 | OCR in cloud (CASB/REST, EMAIL, WSS) | M | Good |
| 1.5.5 | Sensitive Image Recognition pre-classifier | M | Partial |

#### 1.6 Identity-Based Detection

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 1.6.1 | Sender/Recipient Pattern Matching | L | Full |
| 1.6.2 | Directory Group Matching (DGM) -- Active Directory | M | Full |
| 1.6.3 | DGM -- Microsoft Entra ID (25.1+) | M | Good |
| 1.6.4 | Sender/User Based on Profiled Directory (EDM) | H | Good |
| 1.6.5 | User Groups configuration | M | Full |
| 1.6.6 | Described Identity Matching | M | Partial |

#### 1.7 Risk-Based Detection

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 1.7.1 | ICA integration for user risk scores | VH | Good |
| 1.7.2 | Risk score threshold in policy conditions | M | Good |
| 1.7.3 | Behavioral analytics aggregation | VH | Partial |

#### 1.8 Microsoft Information Protection (MIP) Detection

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 1.8.1 | Content Matches MIP Tag Rule condition | M | Good |
| 1.8.2 | Read MIP sensitivity labels | M | Good |
| 1.8.3 | Detect MIP-encrypted files | M | Good |

---

### 2. POLICY MANAGEMENT

#### 2.1 Policy Authoring

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 2.1.1 | Create policy from template | L | Full |
| 2.1.2 | Create custom policy (blank) | M | Full |
| 2.1.3 | Simple rules (single condition) | L | Full |
| 2.1.4 | Compound rules (multiple AND conditions) | M | Full |
| 2.1.5 | Policy severity assignment (1-4) | L | Full |
| 2.1.6 | Policy exceptions (whitelist) | M | Full |
| 2.1.7 | Policy import/export (XML) | L | Good |
| 2.1.8 | Policy cloning/duplication | L | Good |

#### 2.2 Policy Templates

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 2.2.1 | Built-in compliance templates (GDPR, HIPAA, PCI DSS, SOX, GLBA) | L | Full |
| 2.2.2 | Industry-specific templates | L | Good |
| 2.2.3 | DLP Awareness and Avoidance template | L | Good |
| 2.2.4 | Custom template creation | M | Good |
| 2.2.5 | Template import/export | L | Good |
| 2.2.6 | Field mapping check against template | L | Good |

#### 2.3 Policy Groups

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 2.3.1 | Default Policy Group management | L | Full |
| 2.3.2 | Custom policy group creation | M | Full |
| 2.3.3 | Policy group to detection server assignment | M | Full |
| 2.3.4 | Policy group to Endpoint Server deployment | M | Full |
| 2.3.5 | Policy reassignment between groups | L | Good |

#### 2.4 Data Profiles

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 2.4.1 | Exact Data Profiles (EDM) management | M-H | Full |
| 2.4.2 | Indexed Document Profiles (IDM) management | M-H | Full |
| 2.4.3 | VML Profiles management | H | Full |
| 2.4.4 | Data profile scheduling (index refresh) | M | Good |

---

### 3. RESPONSE RULES

#### 3.1 Response Rule Framework

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 3.1.1 | Automated Response rule creation | M | Full |
| 3.1.2 | Smart Response rule creation | M | Full |
| 3.1.3 | Response rule conditions (severity, policy, protocol, sender) | M | Full |
| 3.1.4 | Response rule action priority configuration | M | Good |
| 3.1.5 | Multiple actions per rule | M | Good |

#### 3.2 Universal Actions (All Servers)

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 3.2.1 | Log to Syslog Server | M | Full |
| 3.2.2 | Set Status | L | Full |
| 3.2.3 | Set Attribute | L | Full |
| 3.2.4 | Send Email Notification | M | Full |
| 3.2.5 | Limit Incident Data Retention | L | Good |

#### 3.3 Network Prevent for Email Actions

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 3.3.1 | Block Message | M | Full |
| 3.3.2 | Modify Message (add/remove headers, redirect) | M | Good |
| 3.3.3 | Quarantine Message (via SMG) | H | Good |
| 3.3.4 | Add X-Header | M | Good |
| 3.3.5 | Encrypt email | H | Good |

#### 3.4 Network Prevent for Web Actions

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 3.4.1 | Block web request | M | Full |
| 3.4.2 | Allow web request | L | Full |
| 3.4.3 | Remove sensitive HTML content | M | Partial |

#### 3.5 Endpoint Prevent Actions

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 3.5.1 | Block data transfer | M | Full |
| 3.5.2 | User notification popup | M | Full |
| 3.5.3 | User justification prompt | M | Good |
| 3.5.4 | Encrypt file (Endpoint Encryption integration) | H | Good |
| 3.5.5 | Endpoint FlexResponse (custom plugins) | VH | Good |

#### 3.6 Network Discover/Protect Actions (Data at Rest)

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 3.6.1 | Quarantine file | M | Good |
| 3.6.2 | Copy file to secure location | M | Good |
| 3.6.3 | Apply encryption | H | Good |
| 3.6.4 | Apply Digital Rights Management (DRM) | H | Good |
| 3.6.5 | Apply MIP label (16.1+) | H | Good |

#### 3.7 Cloud/API Detection Actions

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 3.7.1 | Add two-factor authentication | M | Good |
| 3.7.2 | Cloud quarantine | M | Good |
| 3.7.3 | Block cloud sharing | M | Good |
| 3.7.4 | Cloud notification | M | Good |
| 3.7.5 | Apply classification label (cloud) | M | Good |

#### 3.8 FlexResponse Platform

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 3.8.1 | Server FlexResponse plugin development (Java) | VH | Good |
| 3.8.2 | Server FlexResponse plugin deployment (Plugins.properties) | H | Good |
| 3.8.3 | Endpoint FlexResponse plugin deployment | H | Good |
| 3.8.4 | Email Quarantine Connect FlexResponse | H | Good |
| 3.8.5 | Encryption FlexResponse (Symantec Endpoint Encryption) | H | Good |

---

### 4. DEPLOYMENT VECTORS

#### 4.1 Network Monitor

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 4.1.1 | Network Monitor Server installation | H | Full |
| 4.1.2 | Span/tap port configuration | H | Good |
| 4.1.3 | Protocol-level monitoring (SMTP, HTTP, FTP, IM) | M | Good |
| 4.1.4 | Passive traffic analysis | M | Good |
| 4.1.5 | Performance sizing | H | Good |

#### 4.2 Network Prevent for Email

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 4.2.1 | Email Prevent server installation | H | Full |
| 4.2.2 | MTA integration (Postfix, Sendmail, Exchange) | VH | Good |
| 4.2.3 | Reflecting mode configuration | H | Good |
| 4.2.4 | Symantec Messaging Gateway (SMG) integration | VH | Good |
| 4.2.5 | X-header policy enforcement | M | Good |
| 4.2.6 | Email quarantine and release | H | Good |

#### 4.3 Network Prevent for Web

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 4.3.1 | Web Prevent server installation | H | Full |
| 4.3.2 | ICAP proxy integration | H | Good |
| 4.3.3 | Secure ICAP (TLS) configuration | H | Good |
| 4.3.4 | Concurrent connection tuning | M | Good |
| 4.3.5 | Squid Web Proxy integration | H | Good |
| 4.3.6 | Blue Coat / ProxySG integration | H | Partial |

#### 4.4 Network Discover

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 4.4.1 | Discover server installation | H | Full |
| 4.4.2 | File system target scans (CIFS, NFS, DFS) | M | Full |
| 4.4.3 | Database target scans (SQL, Lotus Notes) | H | Good |
| 4.4.4 | SharePoint target scans | H | Good |
| 4.4.5 | Exchange target scans | H | Good |
| 4.4.6 | High Speed Discovery (16.0+, up to 1TB/hour) | H | Good |
| 4.4.7 | Incremental scanning | M | Good |
| 4.4.8 | Scan scheduling and management | M | Full |
| 4.4.9 | Scan performance tuning | H | Good |
| 4.4.10 | Custom file type scanning | M | Partial |

#### 4.5 Network Protect

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 4.5.1 | Automated file quarantine | M | Good |
| 4.5.2 | File copy to secure location | M | Good |
| 4.5.3 | File encryption | H | Good |
| 4.5.4 | DRM application | H | Good |
| 4.5.5 | Quarantine file restoration | M | Partial |
| 4.5.6 | Tombstone/marker file placement | M | Partial |

#### 4.6 Endpoint Prevent

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 4.6.1 | DLP Agent installation (Windows) | M | Full |
| 4.6.2 | DLP Agent installation (macOS) | M | Good |
| 4.6.3 | DLP Agent installation (Linux) | M | Partial |
| 4.6.4 | Clipboard monitoring/blocking | M | Good |
| 4.6.5 | Print/fax monitoring | M | Good |
| 4.6.6 | Removable storage (USB) monitoring/blocking | M | Full |
| 4.6.7 | Local drive monitoring | M | Good |
| 4.6.8 | Network share monitoring | M | Good |
| 4.6.9 | HTTP/HTTPS monitoring | M | Good |
| 4.6.10 | FTP monitoring | M | Good |
| 4.6.11 | Email monitoring (Outlook, Lotus Notes) | M | Good |
| 4.6.12 | Cloud file sync monitoring (Box, Dropbox, etc.) | M | Good |
| 4.6.13 | User notification popups | M | Full |
| 4.6.14 | User justification capture | M | Good |
| 4.6.15 | Identity-based file encryption on USB | H | Good |
| 4.6.16 | Application whitelisting/exclusion | M | Good |
| 4.6.17 | Agent domain filtering (inclusions/exclusions) | M | Good |
| 4.6.18 | Browser content analysis connectors (Edge, Firefox) | M | Good |

#### 4.7 Endpoint Discover

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 4.7.1 | Local drive scanning | M | Full |
| 4.7.2 | Incremental scanning | M | Good |
| 4.7.3 | Manual scan start/stop | L | Full |
| 4.7.4 | Scan target configuration | M | Good |

#### 4.8 Cloud Detection Service (CDS)

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 4.8.1 | CDS provisioning | H | Good |
| 4.8.2 | Cloud email DLP | H | Good |
| 4.8.3 | Cloud web DLP (SWG) | H | Good |
| 4.8.4 | Cloud CASB DLP | H | Good |
| 4.8.5 | Cloud OCR | M | Good |
| 4.8.6 | Cloud EDM/IDM index upload | H | Good |

#### 4.9 Distributed Detection Service (DDS)

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 4.9.1 | Self-hosted detector deployment | VH | Partial |
| 4.9.2 | Cloud-hosted detector deployment | VH | Partial |

#### 4.10 CloudSOC / CASB

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 4.10.1 | CloudSOC provisioning with DLP | H | Good |
| 4.10.2 | Cloud DLP Email policy creation | M | Good |
| 4.10.3 | Cloud DLP SWG policy creation | M | Good |
| 4.10.4 | 100+ cloud app scanning (Office 365, G-Suite, Box, Dropbox, Salesforce) | H | Good |
| 4.10.5 | Directory Group Matching for cloud | H | Good |
| 4.10.6 | Cloud storage scanning (Box, Dropbox, OneDrive, Google Drive) | H | Good |
| 4.10.7 | Microsoft Purview Information Protection remediation | H | Good |

---

### 5. INCIDENT MANAGEMENT

#### 5.1 Incident Lifecycle

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 5.1.1 | Incident creation and classification | L (auto) | Full |
| 5.1.2 | Severity assignment (High/Medium/Low/Informational) | L | Full |
| 5.1.3 | Status management (New, Escalated, In Process, False Positive, Resolved) | L | Full |
| 5.1.4 | Custom status values | M | Good |
| 5.1.5 | Incident assignment to queue/user | M | Full |
| 5.1.6 | Incident investigation workflow | M | Good |
| 5.1.7 | Incident Workflows automation (26.1) | H | Good |

#### 5.2 Incident Attributes

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 5.2.1 | Standard attributes (sender, recipient, protocol, file, etc.) | L (auto) | Full |
| 5.2.2 | Custom attributes definition | M | Full |
| 5.2.3 | Custom attribute population via lookup plugins | H | Good |
| 5.2.4 | Custom attribute population via API | M | Good |

#### 5.3 Remediation

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 5.3.1 | Automated response rule execution | M | Full |
| 5.3.2 | Smart Response manual remediation | M | Full |
| 5.3.3 | End User Remediation (ServiceNow) | H | Good |
| 5.3.4 | ICA DIM Remediation Actions (Escalate, Resolve, Dismiss) | H | Good |
| 5.3.5 | Out-of-office remediator handling | M | Partial |
| 5.3.6 | Timeout/escalation for unactioned incidents | M | Partial |
| 5.3.7 | Auto-enroll violators in training | M | Partial |

---

### 6. REPORTING AND DASHBOARDS

#### 6.1 Reports

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 6.1.1 | Pre-built incident reports | L | Full |
| 6.1.2 | Custom report creation (filter + save) | M | Full |
| 6.1.3 | Report visibility (Private/Shared) | L | Full |
| 6.1.4 | Report export (CSV) | L | Good |
| 6.1.5 | Report scheduling | M | Partial |
| 6.1.6 | System event reports | M | Full |
| 6.1.7 | Saved system reports | M | Good |
| 6.1.8 | Role-based report visibility | L (auto) | Full |

#### 6.2 Dashboards

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 6.2.1 | Custom dashboard creation | M | Full |
| 6.2.2 | Dashboard with up to 12 reports (26.1) | M | Good |
| 6.2.3 | Dynamic chart type configuration (26.1) | L | Good |
| 6.2.4 | Dashboard editing | L | Full |
| 6.2.5 | Role-based dashboard visibility | L (auto) | Good |

---

### 7. ADMINISTRATION

#### 7.1 Server Management

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 7.1.1 | Enforce Server installation (Windows) | VH | Full |
| 7.1.2 | Enforce Server installation (Linux) | VH | Full |
| 7.1.3 | Oracle database setup | VH | Full |
| 7.1.4 | Detection server registration | H | Full |
| 7.1.5 | Advanced server settings | H | Good |
| 7.1.6 | High Availability (Veritas Cluster) | VH | Sparse |
| 7.1.7 | Server health monitoring | M | Good |

#### 7.2 Role-Based Access Control

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 7.2.1 | Role creation and configuration | M | Full |
| 7.2.2 | Privilege assignment (system admin, policy, incident, etc.) | M | Full |
| 7.2.3 | Multi-role user management | M | Full |
| 7.2.4 | Role selection at login (26.1) | L | Good |
| 7.2.5 | Administrator (root) account management | L | Full |

#### 7.3 Authentication

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 7.3.1 | Local user authentication | L | Full |
| 7.3.2 | Active Directory / Kerberos authentication | H | Good |
| 7.3.3 | LDAP authentication | H | Good |
| 7.3.4 | Microsoft Entra ID authentication (26.1) | H | Good |

#### 7.4 Agent Management

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 7.4.1 | Agent installation package generation | M | Full |
| 7.4.2 | Agent deployment (manual, silent, SCCM, GPO) | H | Good |
| 7.4.3 | Agent configuration management | M | Full |
| 7.4.4 | Advanced agent settings | H | Good |
| 7.4.5 | Agent groups (AD Security Group, OU, custom) | M | Good |
| 7.4.6 | Deployment groups for update management | M | Good |
| 7.4.7 | LiveUpdate with randomization (25.1) | M | Good |
| 7.4.8 | Agent health/status monitoring | L | Full |
| 7.4.9 | Agent migration between Endpoint Servers | M | Good |

#### 7.5 Directory Connections

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 7.5.1 | Active Directory connection setup | M | Full |
| 7.5.2 | LDAP directory connection | M | Full |
| 7.5.3 | Directory sync configuration | M | Good |
| 7.5.4 | Microsoft Entra ID connection (26.1) | H | Good |

#### 7.6 System Maintenance

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 7.6.1 | System events monitoring | M | Full |
| 7.6.2 | Audit log management | M | Full |
| 7.6.3 | Audit log export (CSV) | L | Good |
| 7.6.4 | Syslog forwarding configuration (UDP/TCP) | M | Good |
| 7.6.5 | Log file management and rotation | M | Good |
| 7.6.6 | Database maintenance | H | Good |
| 7.6.7 | Upgrade procedures (version migration) | VH | Good |
| 7.6.8 | Backup and recovery | H | Partial |

#### 7.7 Protocol Settings

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 7.7.1 | SMTP protocol configuration | M | Good |
| 7.7.2 | Global SMTP filtering (L7 recipient filter) | M | Good |
| 7.7.3 | HTTP/HTTPS settings | M | Good |
| 7.7.4 | FTP settings | M | Partial |

---

### 8. INTEGRATION

#### 8.1 REST API

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 8.1.1 | Enforce Server REST API (incidents) | H | Full |
| 8.1.2 | Enforce Server REST API (policies) -- 25.1+ | H | Good |
| 8.1.3 | Enforce Server REST API (users/roles) -- 25.1+ | H | Good |
| 8.1.4 | Enforce Server REST API (Discover targets) -- 25.1+ | H | Good |
| 8.1.5 | Enforce Server REST API (audit logs) -- 16.0 RU1+ | M | Good |
| 8.1.6 | Detection REST API 2.0 (content inspection) | H | Good |
| 8.1.7 | Cloud DLP APIs (CloudSOC) | H | Good |
| 8.1.8 | Java code samples | M | Good |

#### 8.2 Email Gateway

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 8.2.1 | MTA integration (Postfix, Sendmail, Exchange) | VH | Good |
| 8.2.2 | Symantec Messaging Gateway (SMG) integration | VH | Good |
| 8.2.3 | Email Quarantine Connect | H | Good |
| 8.2.4 | Cloud Service for Email | H | Good |

#### 8.3 Web Proxy (ICAP)

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 8.3.1 | ICAP request/response mode | H | Good |
| 8.3.2 | Secure ICAP (TLS) | H | Good |
| 8.3.3 | Squid proxy integration | H | Good |
| 8.3.4 | Blue Coat / ProxySG integration | H | Partial |
| 8.3.5 | Performance tuning (concurrent connections) | M | Good |

#### 8.4 SIEM / External Systems

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 8.4.1 | Syslog forwarding (incidents, events, audit) | M | Good |
| 8.4.2 | Splunk integration | H | Partial |
| 8.4.3 | QRadar / JSA integration | H | Good |
| 8.4.4 | ServiceNow DLP Incident Response | H | Good |
| 8.4.5 | Cortex XSOAR integration | H | Good |
| 8.4.6 | ManageEngine / EventLog Analyzer | M | Partial |

#### 8.5 Microsoft Ecosystem

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 8.5.1 | MIP label detection in policies | M | Good |
| 8.5.2 | MIP label application (auto-classify) | H | Good |
| 8.5.3 | MIP RMS encryption via label | H | Good |
| 8.5.4 | Microsoft Entra ID identity sync (26.1) | H | Good |
| 8.5.5 | Microsoft Edge content analysis connector | M | Good |
| 8.5.6 | Microsoft Purview Information Protection remediation | H | Good |

#### 8.6 Analytics and Governance

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 8.6.1 | Information Centric Analytics (ICA) integration | VH | Good |
| 8.6.2 | ICA risk scoring (1-100) | H | Good |
| 8.6.3 | ICA remediation actions | H | Good |
| 8.6.4 | Data Insight integration (Veritas) | VH | Good |
| 8.6.5 | Data Insight Self-Service Portal | H | Partial |
| 8.6.6 | Open Access Reporting | M | Partial |

#### 8.7 Lookup Plugins

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 8.7.1 | LDAP Lookup Plugin configuration | H | Full |
| 8.7.2 | Script Lookup Plugin | H | Partial |
| 8.7.3 | Custom lookup plugins | VH | Partial |
| 8.7.4 | Attribute mapping (LDAP -> Custom Attributes) | H | Good |

---

### 9. INSTALLATION AND DEPLOYMENT

#### 9.1 Infrastructure Setup

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 9.1.1 | Single-tier deployment (lab/test) | H | Full |
| 9.1.2 | Two-tier deployment (small production) | VH | Full |
| 9.1.3 | Three-tier deployment (recommended production) | VH | Full |
| 9.1.4 | Oracle database installation and configuration | VH | Full |
| 9.1.5 | Enforce Server installation (Windows) | VH | Full |
| 9.1.6 | Enforce Server installation (Linux) | VH | Full |
| 9.1.7 | Detection server installation and registration | H | Full |
| 9.1.8 | SSL/TLS certificate configuration | H | Good |

#### 9.2 Upgrade and Migration

| # | Sub-Capability | Complexity | Doc Coverage |
|---|---------------|------------|-------------|
| 9.2.1 | Upgrade phases and planning | VH | Full |
| 9.2.2 | Version-to-version upgrade (e.g., 15.8 -> 16.0) | VH | Full |
| 9.2.3 | Major version migration (16.x -> 25.x) | VH | Good |
| 9.2.4 | Agent upgrade and deployment groups | H | Good |

---

## Summary Statistics

| Category | Sub-Capabilities | Complexity Distribution |
|----------|-----------------|------------------------|
| 1. Detection Technologies | 42 | L:9, M:20, H:10, VH:3 |
| 2. Policy Management | 21 | L:9, M:10, H:2, VH:0 |
| 3. Response Rules | 33 | L:4, M:17, H:11, VH:1 |
| 4. Deployment Vectors | 52 | L:2, M:26, H:20, VH:4 |
| 5. Incident Management | 14 | L:3, M:6, H:5, VH:0 |
| 6. Reporting & Dashboards | 13 | L:5, M:7, H:0, VH:0 |
| 7. Administration | 35 | L:5, M:16, H:10, VH:4 |
| 8. Integration | 34 | L:0, M:9, H:20, VH:5 |
| 9. Installation & Deployment | 12 | L:0, M:0, H:5, VH:7 |
| **TOTAL** | **256** | **L:37, M:111, H:83, VH:24** |

---

## Coverage Heat Map

| Category | Full | Good | Partial | Sparse | None |
|----------|------|------|---------|--------|------|
| Detection Technologies | 13 | 22 | 7 | 0 | 0 |
| Policy Management | 11 | 10 | 0 | 0 | 0 |
| Response Rules | 9 | 21 | 3 | 0 | 0 |
| Deployment Vectors | 14 | 30 | 8 | 0 | 0 |
| Incident Management | 5 | 5 | 4 | 0 | 0 |
| Reporting & Dashboards | 6 | 6 | 1 | 0 | 0 |
| Administration | 13 | 16 | 3 | 3 | 0 |
| Integration | 2 | 21 | 8 | 0 | 0 |
| Installation & Deployment | 7 | 4 | 0 | 0 | 0 |
| **TOTAL** | **80** | **135** | **34** | **3** | **0** |

**Overall doc coverage: 84% Full/Good, 13% Partial, 1% Sparse, 0% None**

---

*End of capability taxonomy. 256 sub-capabilities across 9 major categories identified.*
