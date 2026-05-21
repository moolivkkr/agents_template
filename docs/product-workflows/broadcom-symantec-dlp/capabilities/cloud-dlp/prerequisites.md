# Cloud DLP — Prerequisites
## Broadcom Symantec DLP (Enforce Server, version 16.x/25.x/26.x)

> **Purpose:** Infrastructure prerequisites, cloud app API requirements, proxy configuration requirements, and dependency graph for cloud DLP.
> **Evidence sources:** doc-corpus.md [S1-S28], video-intelligence.md [V1-V45], api-intelligence.md

---

## 1. Infrastructure Prerequisites

### 1.1 CloudSOC Platform (Required)

| Component | Requirement | Notes | Evidence |
|-----------|------------|-------|----------|
| **CloudSOC Account** | Active subscription (app.elastica.net or app.eu.elastica.net) | Cloud-hosted CASB management console | A [S24] |
| **Cloud Detection Service (CDS)** | Enabled in CloudSOC admin settings | Cloud-hosted DLP scanning engine. No on-prem hardware needed. | A [S11, S24] |
| **Admin Account** | CloudSOC administrator privileges | Required to connect apps, create profiles, manage incidents | A [S24] |

### 1.2 On-Premises Infrastructure (Optional -- Hybrid Mode)

| Component | Requirement | When Required | Evidence |
|-----------|------------|--------------|----------|
| **Enforce Server** | DLP 16.0+ with CDS connectivity | For Enforce-managed cloud policies | A [S1, S2] |
| **Oracle Database** | Oracle 19c (DLP 16.0+) | Required if using Enforce Server | A [S1] |
| **Remote Indexer Tool** | Installed on Windows server | Required for EDM/IDM cloud indexes | A [S1, S24] |
| **MIP SDK** | Installed on Enforce Server | Required for MIP label response actions | A [S1, S2] |

### 1.3 Proxy Infrastructure (Optional -- Inline Mode)

| Component | Requirement | When Required | Evidence |
|-----------|------------|--------------|----------|
| **Symantec Web Security Service (WSS/SWG)** | Active subscription | For proxy-based inline inspection and Shadow IT detection | A [S1, S24] |
| **Proxy PAC file or GPO** | Traffic routing to cloud proxy | All user traffic must route through proxy | A [S24] |
| **SSL inspection certificate** | CA certificate for HTTPS inspection | Required for inspecting encrypted web traffic | A [S24] |

---

## 2. Per-Cloud-App Prerequisites

### 2.1 Microsoft 365

| Prerequisite | Details | How to Obtain | Evidence |
|-------------|---------|--------------|----------|
| **Azure AD App Registration** | Application registered in Azure AD | Azure Portal > Azure AD > App registrations | A [S24] |
| **Global Admin Consent** | Admin consent for API permissions | Azure Portal > Enterprise Applications > Grant consent | A [S24] |
| **API Permissions** | Microsoft Graph: Files.Read.All, Mail.Read, Sites.Read.All, User.Read.All, Chat.Read.All (optional for Teams) | Azure Portal > App Registration > API Permissions | A [S24] |
| **Application (Client) ID** | Azure AD application ID | From App Registration overview page | A [S24] |
| **Directory (Tenant) ID** | Azure AD tenant ID | From App Registration overview page | A [S24] |
| **Client Secret or Certificate** | Authentication credential for API access | Azure Portal > App Registration > Certificates & secrets | A [S24] |
| **Microsoft 365 License** | Business or Enterprise license | E3, E5, Business Premium, or equivalent | A [S24] |

**Permissions detail:**
| Permission | Type | Purpose | Required For |
|-----------|------|---------|-------------|
| Files.Read.All | Application | Read all OneDrive and SharePoint files | OneDrive + SharePoint scanning |
| Mail.Read | Application | Read all Exchange Online email | Exchange Online scanning |
| Sites.Read.All | Application | Read all SharePoint site collections | SharePoint scanning |
| User.Read.All | Application | Read user profiles | Identity resolution (who owns files) |
| Chat.Read.All | Application | Read Teams chat messages | Teams scanning (optional) |
| Mail.ReadWrite | Application | Modify email (quarantine) | Email quarantine response action |
| Files.ReadWrite.All | Application | Modify files (quarantine, labels) | File quarantine and label application |

**Note:** ReadWrite permissions are only needed if quarantine or label response actions are configured. Start with Read-only permissions for monitoring, then upgrade when enforcement is enabled.

[S24] Evidence: A

---

### 2.2 Google Workspace

| Prerequisite | Details | How to Obtain | Evidence |
|-------------|---------|--------------|----------|
| **Google Cloud Project** | Project with APIs enabled | Google Cloud Console > New Project | A [S24] |
| **Service Account** | Service account with domain-wide delegation | Google Cloud Console > IAM > Service Accounts | A [S24] |
| **Domain-Wide Delegation** | Admin consent for service account | Google Admin Console > Security > API Controls | A [S24] |
| **OAuth Scopes** | `drive.readonly`, `gmail.readonly` | Configured in domain-wide delegation settings | A [S24] |
| **Google Workspace License** | Business Starter or above | Enterprise recommended for full API access | A [S24] |

**Service Account Scopes:**
| Scope | Purpose |
|-------|---------|
| `https://www.googleapis.com/auth/drive.readonly` | Read Google Drive files |
| `https://www.googleapis.com/auth/drive` | Read + modify (for quarantine) |
| `https://www.googleapis.com/auth/gmail.readonly` | Read Gmail messages |
| `https://www.googleapis.com/auth/admin.directory.user.readonly` | Read user directory |

[S24] Evidence: A

---

### 2.3 Box

| Prerequisite | Details | How to Obtain | Evidence |
|-------------|---------|--------------|----------|
| **Box Enterprise Account** | Business or Enterprise plan | Box admin portal | A [S24] |
| **Custom App (JWT)** | Server Authentication (JWT) app | Box Developer Console > Create New App | A [S24] |
| **App Authorization** | Admin authorization in Box Admin Console | Box Admin Console > Apps > Custom Apps > Authorize | A [S24] |
| **Enterprise Admin** | Box Enterprise Admin role | Required to authorize the custom app | A [S24] |

[S24] Evidence: A

---

### 2.4 Dropbox

| Prerequisite | Details | How to Obtain | Evidence |
|-------------|---------|--------------|----------|
| **Dropbox Business Account** | Business or Enterprise plan | Dropbox admin portal | A [S24] |
| **API App** | Full Dropbox API app | Dropbox App Console | A [S24] |
| **Team Admin** | Dropbox Business admin role | Required to authorize API access | A [S24] |

[S24] Evidence: A

---

### 2.5 Salesforce

| Prerequisite | Details | How to Obtain | Evidence |
|-------------|---------|--------------|----------|
| **Salesforce Edition** | Enterprise, Unlimited, or Developer | Salesforce admin portal | A [S24] |
| **Connected App** | OAuth2 Connected App registration | Salesforce Setup > Apps > App Manager > New Connected App | A [S24] |
| **Consumer Key/Secret** | OAuth credentials | From Connected App settings | A [S24] |
| **System Admin Profile** | Admin access for API authorization | Required for Connected App setup | A [S24] |
| **API Access** | API Enabled permission set | Salesforce Setup > Profiles > API Enabled | A [S24] |

[S24] Evidence: A

---

## 3. Cloud Detection Service Prerequisites

### 3.1 CDS Enablement

| Requirement | Details | Evidence |
|-------------|---------|----------|
| CloudSOC subscription with CDS entitlement | CDS is a licensed feature within CloudSOC | A [S11] |
| CDS provisioning | Enable via CloudSOC Admin > DLP Configuration > Enable Cloud Detection Service | A [S11, V8] |
| Policy source configuration | Select: Enforce-managed, CloudSOC profiles, or both | A [S11] |

### 3.2 Detection Technology Support in CDS

| Technology | Cloud Support | Notes | Evidence |
|-----------|--------------|-------|----------|
| DCM (Keywords, Regex, Data Identifiers) | Full | Built into CDS | A [S11, S24] |
| EDM (Exact Data Matching) | Full (via Remote Indexer) | Requires cloud-compatible index | A [S1, S24] |
| IDM (Indexed Document Matching) | Full (via Remote Indexer) | Requires cloud-compatible index | A [S1, S24] |
| VML (Vector Machine Learning) | Requires re-training or policy import | On-prem VML models not directly portable | B [S1, S24] |
| OCR (image text extraction) | Full | Cloud-hosted OCR engine | A [S1, S24] |
| MIP Label Detection | Full | Reads MIP labels on cloud documents | A [S1, S2] |

---

## 4. Proxy Prerequisites (Inline Mode)

### 4.1 Symantec Web Security Service (WSS/SWG)

| Requirement | Details | Evidence |
|-------------|---------|----------|
| WSS subscription | Active cloud proxy subscription | A [S24] |
| Traffic routing | PAC file, proxy GPO, or agent-based routing | A [S24] |
| SSL inspection certificate | Deploy trusted CA cert to all endpoints for HTTPS inspection | A [S24] |
| Endpoint agent (optional) | Symantec Endpoint Agent for proxy routing (alternative to PAC) | A [S24] |
| DLP integration | Enable DLP scanning in WSS policy configuration | A [S24] |

### 4.2 SSL Inspection for Proxy Mode

| Requirement | Details | Evidence |
|-------------|---------|----------|
| Root CA certificate | Deployed to all endpoint trust stores | A [S24] |
| Browser trust | Certificate must be trusted by Chrome, Edge, Firefox, Safari | A [S24] |
| Bypass list | Domains that should NOT be SSL-inspected (banking, healthcare portals) | A [S24] |
| Certificate deployment | Via GPO, MDM, or SCCM | A [S24] |

---

## 5. EDM/IDM Cloud Index Prerequisites

### 5.1 Remote Indexer Tool

| Requirement | Details | Evidence |
|-------------|---------|----------|
| Operating System | Windows Server (same version as Enforce) | A [S1, S24] |
| Java | JRE 8+ installed | A [S1] |
| Source data | Access to EDM source data (CSV) or IDM source documents | A [S1] |
| Network | Connectivity to CloudSOC for index upload (HTTPS) | A [S24] |
| Disk space | 2x the size of the source data for index generation | B [S1] |

### 5.2 Index Compatibility

| Scenario | Index Source | Cloud Compatible? | Action Required | Evidence |
|----------|------------|-------------------|----------------|----------|
| New cloud-only deployment | CSV/documents | No (must create cloud index) | Run Remote Indexer Tool | A [S24] |
| Existing on-prem EDM profile | Enforce Server | No (not directly portable) | Re-index with Remote Indexer Tool | A [S1, S24] |
| Existing on-prem IDM profile | Enforce Server | No (not directly portable) | Re-index with Remote Indexer Tool | A [S1, S24] |

---

## 6. Configuration Order

### 6.1 Recommended Setup Sequence

```
Step 1:  Obtain CloudSOC subscription + CDS entitlement
           |
Step 2:  Register API applications in cloud app admin consoles:
           +-> Azure AD app for Microsoft 365
           +-> Google Cloud project + service account for Google Workspace
           +-> Box custom app (JWT) for Box
           +-> Connected App for Salesforce
           |
Step 3:  Connect cloud apps in CloudSOC
           |
Step 4:  Enable Cloud Detection Service
           |
Step 5:  Create DLP Profiles with detection rules
           |
Step 6:  Apply profiles to connected apps (MONITOR ONLY first)
           |
Step 7:  2-week monitoring period -- review incidents, tune false positives
           |
Step 8:  Enable enforcement actions (quarantine, revoke sharing)
           |
Step 9:  (Optional) Deploy proxy for inline inspection
           |
Step 10: (Optional) Connect to on-prem Enforce for hybrid management
           |
Step 11: (Optional) Create cloud EDM/IDM indexes via Remote Indexer
```

**CRITICAL:** Always start with monitoring-only response actions (Notify) before enabling enforcement (Quarantine, Revoke Sharing). Cloud quarantine actions are difficult to reverse at scale -- a misconfigured policy can quarantine thousands of files simultaneously. [S24, V-tribal]

[S1, S2, S11, S24] Evidence: A

---

## 7. Capacity Planning

```
Cloud App API Quotas (must stay within limits):
  [ ] Microsoft Graph API: 10,000 requests per 10 minutes per app
  [ ] Google Drive API: 10,000 requests per 100 seconds per project
  [ ] Box API: 10 requests per second per user (1000/min)
  [ ] Salesforce API: 100,000 requests per 24 hours (Enterprise edition)

CloudSOC Sizing:
  [ ] Number of cloud apps to connect
  [ ] Total data volume across all apps
  [ ] Expected incident volume (affects dashboard performance)
  [ ] Number of concurrent DLP profiles

CDS Capacity:
  [ ] Hosted service -- capacity managed by Broadcom
  [ ] No on-prem sizing required for CDS
  [ ] Large-scale scans may experience delays during peak hours

Proxy Sizing (if using inline mode):
  [ ] Number of concurrent users through proxy
  [ ] Bandwidth requirements
  [ ] SSL inspection certificate deployment scope
```

[S24, API-intelligence] Evidence: A-B
