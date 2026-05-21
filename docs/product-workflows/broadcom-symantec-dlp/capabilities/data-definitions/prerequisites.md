# Data Definitions — Prerequisites
## Broadcom Symantec DLP (Enforce Server, version 16.x/25.x/26.x)

> **Purpose:** Infrastructure prerequisites, configuration order, and dependency graph for defining and deploying data definitions.
> **Evidence sources:** doc-corpus.md [S1-S28], video-intelligence.md [V1-V45], api-intelligence.md

---

## 1. Infrastructure Prerequisites

### 1.1 Core Infrastructure (Required for ALL Data Definitions)

| Component | Requirement | Version | Notes | Evidence |
|-----------|------------|---------|-------|----------|
| **Oracle Database** | Oracle Enterprise Edition | 19c (DLP 16.0+) | Stores data profile definitions, index metadata, policy configurations. Embedded DB option for <250 agents. | A [S1, S4, V9] |
| **Enforce Server** | Central management hub | DLP 16.0+ / 25.1+ / 26.1 | Hosts the administration console where all data definitions are created and managed. Single instance per deployment. | A [S1, S4, V10] |
| **Detection Server(s)** | At least 1 detection server | Same major version as Enforce | Receives deployed data profiles (EDM indexes, IDM fingerprints, VML models) from Enforce Server. | A [S1, S4, V11] |
| **Web Browser** | Admin console access | Chrome, Firefox, Edge (current versions) | Enforce Server admin UI is browser-based. Required for all data definition tasks (no API for profile creation). | A [S1] |

### 1.2 Technology-Specific Prerequisites

| Technology | Additional Infrastructure | Why Needed | Evidence |
|-----------|-------------------------|-----------|----------|
| **EDM** | CSV/TSV file OR database connection OR LDAP connection | Source data for indexing | A [S1, S4] |
| **EDM (large scale)** | Remote EDM Indexer host | Off-server indexing for >1M row datasets to avoid Enforce Server degradation | A [S1, S4] |
| **IDM** | File share or document repository with network access from Enforce | Source documents for fingerprinting | A [S1, S4] |
| **IDM (cloud)** | Remote Indexer Tool installed | Creates cloud-compatible index files (`.ridx`) for CloudSOC/CASB deployment | A [S1, S24] |
| **VML** | 50+ positive AND 50+ negative training documents (text-based) | Statistical model training requires examples of both classes | A [S7, V20] |
| **Form Recognition** | Blank form template (PDF/TIFF/PNG at 300+ DPI) | Image template for layout matching | A [S1, V21] |
| **Form Recognition (scanned)** | OCR enabled on detection servers | Extract text from scanned images for combined content + form detection | A [S1, S4] |
| **Data Identifiers** | No additional infrastructure | Built-in; ready to use immediately | A [S1, S4] |
| **Custom Regex/Keywords** | No additional infrastructure | Pattern-based; no pre-processing required | A [S1, S8] |
| **File Properties** | No additional infrastructure | Metadata-based; no pre-processing required | A [S1, S4] |

### 1.3 Network Requirements

| From | To | Protocol/Port | Purpose | Required For | Evidence |
|------|----|--------------|---------|-------------|----------|
| Enforce Server | Oracle DB | TCP/1521 (default) | Database connectivity | ALL (profile storage) | A [S1, S4] |
| Enforce Server | Detection Servers | HTTPS/443 | Policy and profile deployment | ALL (profile distribution) | A [S1, S4] |
| Enforce Server | File Shares | SMB/CIFS (TCP/445) | EDM file source, IDM document source | EDM (file), IDM | A [S1, S4] |
| Enforce Server | External Database | JDBC (varies) | EDM database source | EDM (database) | A [S1, S4] |
| Enforce Server | LDAP/AD | LDAP/389 or LDAPS/636 | EDM LDAP source, DGM rules | EDM (LDAP) | A [S1, S4] |
| Remote EDM Indexer | Enforce Server | HTTPS/443 | Index file upload | EDM (large scale) | A [S1, S4] |
| Remote IDM Indexer | CloudSOC | HTTPS/443 | Cloud index upload | IDM (cloud) | A [S1, S24] |
| Detection Servers | Endpoints | HTTPS/443 | Profile distribution to agents | Endpoint detection | A [S1, S4] |

---

## 2. Configuration Order

### 2.1 Dependency Chain

Data definition technologies must be prepared BEFORE they can be referenced in detection rules. The dependency chain is:

```
Infrastructure (Oracle + Enforce + Detection Servers)
  |
  v
Data Source Preparation (CSV export, document collection, training data)
  |
  v
Data Profile Creation (EDM profile, IDM profile, VML profile)
  |
  v
Data Profile Activation (indexing, fingerprinting, training)
  |
  v
Detection Rule Creation (rule references activated profile)
  |
  v
Policy Assembly (rule added to policy)
  |
  v
Policy Deployment (policy assigned to policy group, deployed to servers)
```

### 2.2 Technology-Specific Preparation Steps

#### EDM Preparation (before creating EDM detection rules)

```
Step 1: Extract source data to CSV/TSV/DB query result
  ├── Clean data (remove blanks, validate formats)
  ├── Ensure key fields (SSN, CC, ID) are populated
  └── Verify error rate will be <5% (default threshold)

Step 2: Create Exact Data Profile
  ├── Navigate: Manage > Data Profiles > Exact Data Profiles
  ├── Upload data source or configure database connection
  └── Map columns to field types (KEY vs CORROBORATIVE)

Step 3: Run initial indexing
  ├── Indexing creates non-reversible hashes
  ├── Time: minutes (small) to hours (millions of rows)
  └── Verify: index status shows "CURRENT" on all servers

Step 4: (Optional) Configure automated re-indexing schedule
  └── Daily/Weekly/Monthly depending on data change rate
```

#### IDM Preparation (before creating IDM detection rules)

```
Step 1: Collect source documents in accessible location
  ├── Network file share (UNC path) or upload directory
  ├── Organize by document group if needed
  └── Include all versions to protect (current + recent)

Step 2: Create Indexed Document Profile
  ├── Navigate: Manage > Data Profiles > Indexed Document Profiles
  ├── Specify source path
  └── Configure matching mode (exact, partial, both)

Step 3: Run initial fingerprinting
  ├── System generates rolling hashes for all documents
  ├── Configure partial match threshold (10% recommended start)
  └── Enable Endpoint IDM if needed (off by default)

Step 4: (Optional) Configure re-indexing schedule
  └── Weekly/Monthly depending on document change rate
```

#### VML Preparation (before creating VML detection rules)

```
Step 1: Prepare training document sets
  ├── POSITIVE set: 250+ documents of the type to protect
  |   ├── Diverse authors, time periods, sub-topics
  |   └── Text-based (Office, PDF, TXT -- NOT binary files)
  ├── NEGATIVE set: 250+ "near-miss" documents
  |   ├── Same domain but NOT sensitive
  |   └── Example: public filings (negative) vs internal reports (positive)
  └── Balanced: approximately equal counts in both sets

Step 2: Create VML Profile
  ├── Navigate: Manage > Data Profiles > Vector Machine Learning Profiles
  └── Upload positive and negative document sets

Step 3: Train the model
  ├── System performs statistical analysis
  ├── Review accuracy score (target: >85%)
  └── If accuracy <85%, add more diverse training documents

Step 4: Accept the profile
  └── Profile becomes available for policy rule references
```

---

## 3. RBAC Prerequisites

| Action | Required Privilege | Notes | Evidence |
|--------|-------------------|-------|----------|
| Create EDM profiles | Policy Authoring | Profile creation and column mapping | A [S1, S4] |
| Create IDM profiles | Policy Authoring | Profile creation and fingerprint configuration | A [S1, S4] |
| Create VML profiles | Policy Authoring | Profile creation and model training | A [S1, S4] |
| Run EDM indexing | Policy Authoring | Manual or scheduled indexing | A [S1, S4] |
| Trigger EDM indexing via API | "Incident Reporting API Web Service" role | `POST /edm/index` (16.0 RU2+) | A [API-intelligence] |
| Create detection rules with data identifiers | Policy Authoring | Rule creation within policy editor | A [S1, S4] |
| View data profile status | Policy Authoring or read-only equivalent | View index status, training results | A [S1, S4] |
| Configure Remote EDM Indexer | System Administration | Infrastructure configuration | A [S1, S4] |
| Access directory connections (for EDM LDAP source) | System Administration | System > Settings > Directory Connections | A [S1, S4] |

**RBAC Navigation:** System > Login Management > Roles

**Note:** The built-in "Administrator" user (created at install) has unrestricted access and can perform all data definition operations without explicit role assignment. [S1, S4]

---

## 4. Pre-Configuration Checklist

Before creating any data definitions, verify:

| # | Check | How to Verify | Required For | Evidence |
|---|-------|---------------|-------------|----------|
| 1 | Enforce Server is running | Navigate to console URL in browser | ALL | A [S1] |
| 2 | At least 1 detection server registered and online | System > Servers and Detectors > Overview (green status) | ALL | A [S1, S4] |
| 3 | Oracle database operational | Console loads without errors | ALL | A [S1, S4] |
| 4 | User has Policy Authoring privilege | System > Login Management > Roles > [role] | ALL | A [S1, S4] |
| 5 | EDM data source is prepared and accessible | File share reachable from Enforce, or DB connection tested | EDM | A [S1, S4] |
| 6 | EDM data quality validated (<5% errors) | Pre-validate CSV for blank rows, invalid formats | EDM | A [S1, V19] |
| 7 | IDM source documents collected and accessible | File share reachable from Enforce | IDM | A [S1, S4] |
| 8 | VML training sets prepared (50+ docs each, balanced) | Document counts verified, text-based format confirmed | VML | A [S7, V20] |
| 9 | Blank form templates available (300+ DPI) | PDF/TIFF/PNG of blank forms | Form Recognition | A [S1, V21] |
| 10 | OCR enabled on detection servers (if using Form Recognition on scanned docs) | Detection server settings | Form Recognition (scanned) | A [S1, S4] |
| 11 | Remote EDM Indexer installed (if data source >1M rows) | Verify indexer host is online and connected to Enforce | EDM (large scale) | A [S1, S4] |
| 12 | Remote Indexer Tool installed (if cloud IDM needed) | Verify tool is operational | IDM (cloud/CASB) | A [S1, S24] |
| 13 | Sufficient disk space on Enforce Server for index storage | Check available storage (1-20+ GB per EDM profile) | EDM, IDM | A [S1, S4] |
| 14 | Sufficient disk space on detection servers for distributed profiles | Detection servers need copies of indexes and fingerprints | EDM, IDM, VML | A [S1, S4] |

---

## 5. Capacity Planning for Data Definitions

### 5.1 EDM Profile Sizing

| Records in Source | Indexing Time (Enforce) | Indexing Time (Remote) | Index Storage | RAM Required | Evidence |
|-------------------|------------------------|----------------------|---------------|-------------|----------|
| <10K | <1 minute | N/A (use Enforce) | <100 MB | +256 MB | A [S1, S4] |
| 10K-100K | 1-5 minutes | N/A (use Enforce) | 100 MB - 1 GB | +512 MB | A [S1, S4] |
| 100K-1M | 5-30 minutes | 2-15 minutes | 1-5 GB | +1-2 GB | A [S1, S4] |
| 1M-5M | 30 min - 2 hours | 15-60 minutes | 5-15 GB | +2-4 GB | A [S1, S4] |
| 5M-10M | 2-4 hours | 1-2 hours | 15-25 GB | +4-8 GB | B [S4] |
| >10M | 4+ hours | 2+ hours | 25+ GB | +8+ GB | B [S4] |

### 5.2 IDM Profile Sizing

| Source Documents | Fingerprint Time | Storage | RAM Required | Evidence |
|-----------------|-----------------|---------|-------------|----------|
| <100 | <1 minute | <50 MB | +128 MB | A [S1, S4] |
| 100-1,000 | 1-10 minutes | 50-500 MB | +256 MB | A [S1, S4] |
| 1,000-10,000 | 10-60 minutes | 500 MB - 5 GB | +512 MB - 1 GB | A [S1, S4] |
| 10,000-100,000 | 1-6 hours | 5-50 GB | +1-4 GB | B [S4] |

### 5.3 VML Model Sizing

| Training Documents (total) | Training Time | Model Size | RAM Required | Evidence |
|---------------------------|--------------|------------|-------------|----------|
| 100 (50+50) | 1-5 minutes | 10-20 MB | +128 MB | A [S7] |
| 200 (100+100) | 5-15 minutes | 20-50 MB | +256 MB | A [S7] |
| 500 (250+250) | 15-45 minutes | 50-100 MB | +512 MB | A [S7] |
| 1,000 (500+500) | 45 min - 2 hours | 100-200 MB | +512 MB - 1 GB | B [S7] |

---

## 6. Version-Specific Data Definition Features

| DLP Version | Data Definition Enhancements | Evidence |
|-------------|------------------------------|----------|
| 15.0 | OCR for image-based detection; Form Recognition; Sensitive Image Recognition | A [S1] |
| 15.5 | VML improvements; enhanced data identifier library | A [S5] |
| 15.7 | REST API introduced (incident management only; no data definition APIs) | A [S1] |
| 15.8 | Easier data classification workflow; MIP tag detection as policy condition | A [S1] |
| 16.0 | Data identifier library expanded; High Speed Discovery with file property detection | A [S1] |
| 16.0 RU2 | **EDM indexing API** (`POST /edm/index`) -- first API surface for data definitions | A [API-intelligence] |
| 16.1 | Auto-classify with MPIP labels; High Speed Discovery label application | A [S6] |
| 25.1 | Policy import/export API (includes data definition references); content analysis connectors for Edge/Firefox | A [S2, API-intelligence] |
| 26.1 | Enhanced incident workflows; no new data definition features confirmed | A [S3] |

---

## 7. Dependency Diagram

```
+------------------------------------------------------------------+
|  PREREQUISITES FOR DATA DEFINITIONS                                |
+------------------------------------------------------------------+
|                                                                    |
|  TIER 1: Infrastructure (MUST exist before anything else)          |
|  +------------------------------------------------------------+   |
|  |  Oracle Database (19c) --> Enforce Server --> Detection      |   |
|  |                            Server(s) (at least 1)           |   |
|  +------------------------------------------------------------+   |
|                              |                                     |
|  TIER 2: Data Sources (needed BEFORE profile creation)             |
|  +------------------------------------------------------------+   |
|  |  EDM: CSV file / DB connection / LDAP export               |   |
|  |  IDM: Document file share / upload directory                |   |
|  |  VML: Positive docs (50+) + Negative docs (50+)            |   |
|  |  Form Recognition: Blank form template (300+ DPI)           |   |
|  |  Data Identifiers: (none -- built-in)                       |   |
|  |  Custom Regex/Keywords: (none -- pattern-based)             |   |
|  |  File Properties: (none -- metadata-based)                  |   |
|  +------------------------------------------------------------+   |
|                              |                                     |
|  TIER 3: Profile Creation (needed BEFORE rule creation)            |
|  +------------------------------------------------------------+   |
|  |  EDM Profile + Index (column mapping, hash creation)        |   |
|  |  IDM Profile + Fingerprints (document registration)         |   |
|  |  VML Profile + Training (model training, accuracy eval.)    |   |
|  +------------------------------------------------------------+   |
|                              |                                     |
|  TIER 4: Detection Rules (reference profiles from Tier 3)          |
|  +------------------------------------------------------------+   |
|  |  Rules reference EDM, IDM, VML profiles, data identifiers  |   |
|  |  Rules assembled into policies                              |   |
|  |  Policies deployed via policy groups to detection servers   |   |
|  +------------------------------------------------------------+   |
|                                                                    |
+------------------------------------------------------------------+
```

---

*End of prerequisites document. 7 sections covering infrastructure, technology-specific requirements, network connectivity, RBAC, pre-configuration checklist, capacity planning, and version-specific features.*
