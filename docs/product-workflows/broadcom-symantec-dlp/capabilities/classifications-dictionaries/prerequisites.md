# Classifications & Dictionaries — Prerequisites
## Broadcom Symantec DLP (Enforce Server, version 16.x/25.x/26.x)

> **Purpose:** Infrastructure prerequisites, dependency order, and checklist for classification and dictionary configuration.
> **Evidence sources:** doc-corpus.md [S1-S28], video-intelligence.md [V1-V45], api-intelligence.md

---

## 1. Infrastructure Prerequisites

### 1.1 Core Infrastructure (Required)

| Component | Requirement | Notes | Evidence |
|-----------|------------|-------|----------|
| **Enforce Server** | Running and accessible | All classification configuration happens in the Enforce console | A [S1, S4] |
| **Oracle Database** | Oracle 19c (DLP 16.0+) | Stores dictionary data, policy definitions, classification rules | A [S1, S4] |
| **Detection Servers** | At least 1 registered and online | Receives deployed policies containing classification rules | A [S1, S4] |
| **Web Browser** | Current version of Chrome, Firefox, or Edge | Console access for dictionary import and classification rule creation | A [S1] |

### 1.2 Component-Specific Prerequisites

| Component | Additional Prerequisites | Why Needed | Evidence |
|-----------|------------------------|-----------|----------|
| **System Data Identifiers** | None | Built-in, available immediately | A [S1, S4] |
| **Custom Dictionaries** | Dictionary file prepared (CSV or TXT) | Source file for import into keyword rules | A [S1, S8] |
| **Classification Policies** | Data identifiers and/or dictionaries defined first | Policies reference detection rules that use identifiers/dictionaries | A [S1, S4] |
| **MIP Sensitivity Labels** | MIP SDK installed on Enforce Server; Azure AD tenant configured; Service principal registered | Label read/write requires connectivity to Microsoft cloud | A [S1, S2, S3] |
| **MIP Label Application** | MIP SDK + Network access to *.microsoftonline.com | Response rule "Apply Classification Label" requires live connection | A [S2] |

### 1.3 MIP Integration Prerequisites (Detailed)

| Prerequisite | Configuration Location | Version Requirement | Evidence |
|-------------|----------------------|---------------------|----------|
| MIP SDK installed | Enforce Server (local installation) | DLP 15.8+ (initial), 16.0+ (enhanced), 16.1+ (auto-label) | A [S1, S2] |
| Azure AD tenant ID | Enforce Server > MIP configuration | Any Azure AD tenant with sensitivity labels | A [S2] |
| Service principal (app registration) | Azure AD portal > App registrations | Application with label read/write permissions | A [S2] |
| Client ID and secret | Enforce Server > MIP configuration | From app registration | A [S2] |
| Sensitivity labels published | Azure AD > Security & Compliance > Labels | Labels must be published to users/groups | A [S2] |
| Network access from Enforce | Firewall rules | Allow Enforce Server to reach: `login.microsoftonline.com`, `*.protection.outlook.com`, `*.aadrm.com` | A [S2] |
| TLS 1.2+ | Enforce Server SSL configuration | Required for Azure AD communication | A [S2] |

---

## 2. Dependency Order

### 2.1 Classification Configuration Sequence

```
PHASE 1: Foundation (must exist first)
  |
  +-- Enforce Server operational
  +-- Oracle DB operational
  +-- At least 1 detection server registered
  |
  v
PHASE 2: Detection Technologies (some required before classification)
  |
  +-- EDM profiles created and indexed (if classifications reference EDM)
  +-- IDM profiles created and fingerprinted (if classifications reference IDM)
  +-- VML profiles trained and accepted (if classifications reference VML)
  +-- MIP SDK installed (if classifications use MIP labels)
  |
  v
PHASE 3: Dictionary and Identifier Preparation
  |
  +-- Dictionary CSV/TXT files prepared and validated
  +-- Custom data identifiers defined (if needed beyond built-in)
  +-- Dictionary threshold strategy determined
  |
  v
PHASE 4: Classification Rule Creation
  |
  +-- Detection rules created (reference identifiers + dictionaries)
  +-- Compound rules assembled (multi-condition AND logic)
  +-- Severity tiers assigned per classification level
  |
  v
PHASE 5: MIP Integration (if applicable)
  |
  +-- MIP tag detection rules configured
  +-- MIP label application response rules configured
  +-- Label mapping documented (DLP severity -> MIP label)
  |
  v
PHASE 6: Policy Assembly and Deployment
  |
  +-- Rules assembled into policies
  +-- Policies assigned to policy groups
  +-- Deployed in "Test Without Notifications" mode
```

### 2.2 Why Order Matters

| Dependency | Reason | Error if Skipped |
|-----------|--------|-----------------|
| Detection technologies before classification rules | Classification rules reference data profiles (EDM, IDM, VML) | Rule cannot select non-existent profile |
| Dictionary files before import | Dictionary import reads from file | Import fails with "file not found" or empty dictionary |
| MIP SDK before MIP tag rules | Tag rule queries MIP label data | Rule fails to enumerate available labels |
| MIP SDK before label application | Apply Classification Label action requires MIP connectivity | Response action fails silently or errors |
| Classification rules before policies | Policies assemble rules | Policy has no detection logic |
| Severity strategy before rule creation | Each rule needs a severity assignment | Inconsistent severity across rules |

---

## 3. RBAC Prerequisites

| Action | Required Privilege | Notes | Evidence |
|--------|-------------------|-------|----------|
| Create keyword rules with dictionaries | Policy Authoring | Includes dictionary import | A [S1, S4] |
| Select data identifiers in rules | Policy Authoring | Built-in identifiers available to all policy authors | A [S1, S4] |
| Create compound classification rules | Policy Authoring | Multi-condition rule creation | A [S1, S4] |
| Configure MIP integration | System Administration | MIP SDK setup and tenant configuration | A [S1, S2] |
| Create MIP tag detection rules | Policy Authoring | References MIP labels in detection conditions | A [S1, S2] |
| Create "Apply Classification Label" response | Response Rule Management | Creates response rules with MIP label actions | A [S1, S2] |
| Manage policy groups | Server Administration | Required for deployment targeting | A [S1, S4] |
| Access CloudSOC API for identifier listing | CloudSOC Admin role | For API-based identifier enumeration | A [API-intelligence] |

---

## 4. Pre-Configuration Checklist

| # | Check | How to Verify | Required For | Evidence |
|---|-------|---------------|-------------|----------|
| 1 | Enforce Server running and accessible | Navigate to console URL | ALL | A [S1] |
| 2 | At least 1 detection server online | System > Servers and Detectors > Overview | ALL | A [S1, S4] |
| 3 | User has Policy Authoring privilege | System > Login Management > Roles | ALL | A [S1, S4] |
| 4 | Dictionary CSV/TXT files prepared | File exists on accessible path with correct format (UTF-8) | Custom Dictionaries | A [S1, S8] |
| 5 | Dictionary entries validated (no blanks, proper encoding) | Open file, check for empty lines and encoding issues | Custom Dictionaries | B [S8] |
| 6 | Threshold strategy documented | Written document specifying threshold per dictionary | Custom Dictionaries | B [tribal knowledge] |
| 7 | Weight assignment completed (if using weighted scoring) | CSV has weight column populated for all entries | Weighted Dictionaries | B [S8] |
| 8 | EDM profiles exist and indexed (if referenced) | Manage > Data Profiles > Exact Data Profiles shows CURRENT | Compound Classifications | A [S1, S4] |
| 9 | VML profiles trained and accepted (if referenced) | Manage > Data Profiles > VML Profiles shows accepted model | Compound Classifications | A [S7] |
| 10 | MIP SDK installed on Enforce Server | Verify MIP configuration section in Enforce console | MIP Integration | A [S2] |
| 11 | Azure AD service principal configured | MIP tenant connection test succeeds | MIP Integration | A [S2] |
| 12 | Sensitivity labels published in Azure AD | Labels visible in MIP tag rule configuration | MIP Integration | A [S2] |
| 13 | Network connectivity to Azure AD endpoints | From Enforce Server: test connectivity to login.microsoftonline.com | MIP Integration | A [S2] |
| 14 | Classification tier design documented | Written specification of tier names, severity mapping, response actions | Multi-Tier Classification | B [tribal knowledge] |

---

## 5. Capacity Considerations

### 5.1 Dictionary Impact on System Resources

| Dictionary Size | Memory Impact per Detection Server | Disk Impact | Notes | Evidence |
|-----------------|----------------------------------|-------------|-------|----------|
| 10-1,000 entries | <10 MB | Negligible | No concern | A [S1] |
| 1,000-10,000 entries | 10-100 MB | <1 GB | Monitor detection latency | B [S8] |
| 10,000-50,000 entries | 100-500 MB | 1-5 GB | Consider splitting dictionaries | B [S8] |
| 50,000+ entries | 500 MB+ | 5+ GB | Split into sub-dictionaries; use high thresholds | B [S8] |

### 5.2 MIP Label Processing Impact

| Operation | Latency Added | CPU Impact | Network Impact | Evidence |
|-----------|-------------|-----------|---------------|----------|
| Read MIP label from document | 50-200 ms | Low | None (local file metadata) | B [S2] |
| Apply MIP label (local) | 100-500 ms | Medium | Moderate (Azure AD auth) | B [S2] |
| Apply MIP label + RMS encrypt | 500 ms - 2 s | Medium-High | High (RMS template download) | B [S2] |
| High Speed Discovery label scan | Varies | High (at scale) | Moderate | A [S6] |

---

## 6. Version-Specific Classification Features

| DLP Version | Classification Enhancement | Evidence |
|-------------|---------------------------|----------|
| 15.0 | Form Recognition for classifying form-based documents | A [S1] |
| 15.5 | Expanded data identifier library | A [S5] |
| 15.8 | MIP tag detection ("Content Matches MIP Tag Rule"); easier data classification workflow | A [S1, S2] |
| 16.0 | Enhanced data identifier breadth modes; expanded built-in identifiers | A [S1] |
| 16.0.1 | Improved MIP label detection for email | A [S6] |
| 16.1 | Auto-classify with MIP labels (response rule can apply label); High Speed Discovery label detection | A [S6] |
| 25.1 | Policy import/export API enables classification portability between environments | A [API-intelligence] |
| 26.1 | No new classification-specific features confirmed | A [S3] |

---

*End of prerequisites document. 6 sections covering infrastructure, MIP-specific requirements, dependency order, RBAC, checklist, capacity planning, and version features.*
