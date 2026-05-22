# API Intelligence: Palo Alto Enterprise DLP -- Policy Authoring

> Researched: 2026-05-21 | API surfaces: 3 | Documented endpoints: 20+
> Confidence: HIGH (corroborated across pan.dev, official docs, Prisma SASE API reference)

---

## Executive Summary

Palo Alto Enterprise DLP exposes a **significantly more comprehensive** REST API compared to legacy DLP products. The primary API surface is the **DLP API** (accessible via pan.dev), which provides programmatic access to data patterns, data profiles, reports, and scanning operations. A secondary surface is the **Prisma SASE API** for managing DLP rules within the broader SASE policy framework. Together, these APIs cover a substantial portion of the policy authoring workflow -- a notable competitive advantage.

**Key finding:** Data profiles and data patterns CAN be managed via API. The DLP API at pan.dev documents CRUD operations for the core policy objects. This is a significant improvement over competitors (Trellix, Symantec) where policy authoring is console-only.

---

## API Surfaces Discovered

| # | Type | Base URL Pattern | Auth Model | Docs Quality | Status |
|---|------|-----------------|------------|-------------|--------|
| 1 | REST (DLP API) | `https://api.dlp.paloaltonetworks.com/v1/...` | OAuth2 (via TSG) | GOOD -- pan.dev interactive docs | Active |
| 2 | REST (Prisma SASE API) | `https://pa-<region>.api.prismaaccess.com/...` | OAuth2 (via TSG) | GOOD -- pan.dev SASE docs | Active |
| 3 | REST (Strata Cloud Manager API) | `https://api.strata.paloaltonetworks.com/...` | OAuth2 (via TSG) | MODERATE -- newer surface | Active |

### Notes on Surfaces

- **DLP API (#1)** is the primary interface for managing data patterns, data profiles, and DLP-specific configuration. Documented at pan.dev/dlp/api/.
- **Prisma SASE API (#2)** manages the broader SASE policy framework, including security rules that reference DLP profiles. Used for end-to-end policy automation.
- **SCM API (#3)** is the Strata Cloud Manager interface for managing configuration across Prisma Access, Cloud NGFW, and on-prem NGFW. DLP configuration is a subset.

---

## Authentication Model

### OAuth2 via Tenant Service Group (TSG)

All three API surfaces use the same authentication model:

```
Method: OAuth2 Client Credentials
Token endpoint: https://auth.apps.paloaltonetworks.com/oauth2/access_token
Grant type: client_credentials
Scope: tsg_id:<TSG_ID>
Client ID: Generated from Strata Cloud Manager > Identity & Access > Service Accounts
Client Secret: Generated alongside Client ID
Token TTL: 900 seconds (15 minutes)
Header: Authorization: Bearer <access_token>
```

**Setup Steps:**
1. Identify or create the Tenant Service Group (TSG) for the scope
2. Create a Service Account in SCM > Identity & Access
3. Assign appropriate roles (DLP Admin, Security Admin)
4. Record Client ID and Client Secret
5. Request token: `POST https://auth.apps.paloaltonetworks.com/oauth2/access_token`
6. Use Bearer token in all subsequent API calls

---

## Endpoint Inventory

### A. DLP API (pan.dev/dlp/api/)

| # | Method | Path | Description | Maps To (Policy Layer) |
|---|--------|------|-------------|----------------------|
| 1 | GET | `/v1/public/data-pattern` | List all data patterns | Data Pattern query |
| 2 | POST | `/v1/public/data-pattern` | Create a custom data pattern | Data Pattern creation |
| 3 | PUT | `/v1/public/data-pattern/{id}` | Update an existing data pattern | Data Pattern update |
| 4 | DELETE | `/v1/public/data-pattern/{id}` | Delete a custom data pattern | Data Pattern deletion |
| 5 | GET | `/v1/public/data-profile` | List all data profiles | Data Profile query |
| 6 | POST | `/v1/public/data-profile` | Create a data profile | Data Profile creation |
| 7 | PUT | `/v1/public/data-profile/{id}` | Update a data profile | Data Profile update |
| 8 | DELETE | `/v1/public/data-profile/{id}` | Delete a data profile | Data Profile deletion |
| 9 | GET | `/v1/public/report/{reportId}` | Retrieve report details | Incident/report query |
| 10 | POST | `/v1/public/scan` | Submit content for DLP scanning | Content inspection |
| 11 | GET | `/v1/public/edm` | List EDM datasets | EDM query |
| 12 | POST | `/v1/public/edm` | Create/upload EDM dataset | EDM creation |

### B. Prisma SASE API (Security Policy)

| # | Method | Path | Description | Maps To |
|---|--------|------|-------------|---------|
| 13 | GET | `/sse/config/v1/security-rules` | List security rules | Security rule query |
| 14 | POST | `/sse/config/v1/security-rules` | Create a security rule (with DLP profile group) | Security rule creation |
| 15 | PUT | `/sse/config/v1/security-rules/{id}` | Update a security rule | Security rule update |
| 16 | GET | `/sse/config/v1/profile-groups` | List profile groups | Profile group query |
| 17 | POST | `/sse/config/v1/profile-groups` | Create a profile group (containing DLP profile) | Profile group creation |
| 18 | POST | `/sse/config/v1/config-versions` | Push configuration changes | Config deployment |

### C. Strata Cloud Manager API (DLP Configuration)

| # | Method | Path | Description | Maps To |
|---|--------|------|-------------|---------|
| 19 | GET | `/config/security/v1/data-loss-prevention` | List DLP rules | DLP rule query |
| 20 | POST | `/config/security/v1/data-loss-prevention` | Create a DLP rule | DLP rule creation |
| 21 | PUT | `/config/security/v1/data-loss-prevention/{id}` | Update a DLP rule | DLP rule update |
| 22 | DELETE | `/config/security/v1/data-loss-prevention/{id}` | Delete a DLP rule | DLP rule deletion |

---

## API-to-UI Coverage Matrix

### Data Pattern Layer

| # | Operation | UI Screen | API Endpoint | Coverage | Impact |
|---|-----------|-----------|-------------|----------|--------|
| 1 | List data patterns | DLP App > Data Patterns | `GET /v1/public/data-pattern` | **FULL** | Can enumerate all patterns |
| 2 | Create custom regex pattern | DLP App > Data Patterns > Create | `POST /v1/public/data-pattern` | **FULL** | Programmatic pattern creation |
| 3 | Update data pattern | DLP App > Data Patterns > Edit | `PUT /v1/public/data-pattern/{id}` | **FULL** | Can modify patterns via API |
| 4 | Delete data pattern | DLP App > Data Patterns > Delete | `DELETE /v1/public/data-pattern/{id}` | **FULL** | Can remove patterns via API |
| 5 | Configure ML-based pattern confidence | DLP App > Data Patterns > ML | None (predefined only) | **PARTIAL** | ML patterns are system-managed, not user-configurable via API |

### Data Profile Layer

| # | Operation | UI Screen | API Endpoint | Coverage | Impact |
|---|-----------|-----------|-------------|----------|--------|
| 6 | List data profiles | DLP App > Data Profiles | `GET /v1/public/data-profile` | **FULL** | Can enumerate profiles |
| 7 | Create data profile | DLP App > Data Profiles > Create | `POST /v1/public/data-profile` | **FULL** | Programmatic profile creation |
| 8 | Update data profile | DLP App > Data Profiles > Edit | `PUT /v1/public/data-profile/{id}` | **FULL** | Can modify profiles via API |
| 9 | Delete data profile | DLP App > Data Profiles > Delete | `DELETE /v1/public/data-profile/{id}` | **FULL** | Can remove profiles via API |
| 10 | Create nested data profile | DLP App > Data Profiles > Nested | Likely via `POST /v1/public/data-profile` with nested structure | **PARTIAL** | Nested profile API structure not fully documented |

### DLP Rule / Data Filtering Profile Layer

| # | Operation | UI Screen | API Endpoint | Coverage | Impact |
|---|-----------|-----------|-------------|----------|--------|
| 11 | Create DLP rule (SCM) | SCM > DLP | `POST /config/security/v1/data-loss-prevention` | **FULL** | Can create DLP rules via API |
| 12 | Create security rule | SCM > Security Policy | `POST /sse/config/v1/security-rules` | **FULL** | Can create security rules with DLP profile attachment |
| 13 | Create profile group | SCM > Profile Groups | `POST /sse/config/v1/profile-groups` | **FULL** | Can create profile groups containing DLP profiles |
| 14 | Push configuration | SCM > Push Config | `POST /sse/config/v1/config-versions` | **FULL** | Can trigger config push via API |

### EDM Layer

| # | Operation | UI Screen | API Endpoint | Coverage | Impact |
|---|-----------|-----------|-------------|----------|--------|
| 15 | List EDM datasets | DLP App > EDM | `GET /v1/public/edm` | **FULL** | Can query EDM datasets |
| 16 | Upload EDM dataset | DLP App > EDM > Upload | `POST /v1/public/edm` | **PARTIAL** | API upload available; CLI app still required for hashing/encryption |

### Incident Layer

| # | Operation | UI Screen | API Endpoint | Coverage | Impact |
|---|-----------|-----------|-------------|----------|--------|
| 17 | Retrieve reports | Incident Management | `GET /v1/public/report/{reportId}` | **FULL** | Report retrieval supported |
| 18 | Submit content for scan | N/A (programmatic) | `POST /v1/public/scan` | **FULL** | On-demand content scanning |

---

## API Gaps -- Console-Only Operations

| # | Operation | Impact | Workaround | Notes |
|---|-----------|--------|-----------|-------|
| 1 | Configure ML-based pattern confidence levels | LOW | Use UI; ML patterns are predefined with High/Low toggle | ML patterns are system-managed |
| 2 | Custom Document Type upload (Trainable Classifiers) | MEDIUM | Must use DLP App UI to upload .zip training sets | Training requires UI feedback loop |
| 3 | EDM data hashing and encryption | MEDIUM | EDM CLI App required for data preparation; API handles upload | Security architecture requires on-prem hashing |
| 4 | Panorama Data Filtering Profile management | MEDIUM | Use Panorama XML API or Panorama GUI | Panorama has separate API surface (XML-based) |
| 5 | Endpoint DLP policy rules (Cortex XDR) | HIGH | Must use Cortex XDR console | Separate management surface entirely |

**Summary: Approximately 5 of ~20 operations have API gaps. The core data pattern and data profile authoring workflow is fully API-accessible -- a significant advantage over competitors.**

---

## Integration Capabilities

### SIEM Integration

| Capability | Status | Mechanism |
|-----------|--------|-----------|
| Cortex XSIAM / Cortex XDR | YES | Native integration |
| Splunk | YES | Palo Alto Networks Add-on for Splunk |
| Syslog (CEF) | YES | Via NGFW log forwarding |
| HTTP/S log forwarding | YES | To any SIEM endpoint |

### SOAR Integration

| Capability | Status | Details |
|-----------|--------|---------|
| Cortex XSOAR | YES | Native DLP playbooks |
| Automated incident response | YES | DLP incident management rules + XSOAR |

### Identity Provider Integration

| Capability | Status | Details |
|-----------|--------|---------|
| LDAP/AD | YES | User-group-based policy scoping |
| SAML/SCIM | YES | Cloud identity integration |
| Cloud Identity Engine (CIE) | YES | Palo Alto's unified identity layer |

---

## SDKs and Client Libraries

| Library | Language | Source | DLP-Specific? |
|---------|----------|--------|---------------|
| pan-python | Python | [GitHub](https://github.com/kevinsteves/pan-python) | No (PAN-OS XML API wrapper) |
| pan-os-python | Python | [GitHub](https://github.com/PaloAltoNetworks/pan-os-python) | No (PAN-OS object management) |
| pan.dev API Explorer | Any (HTTP) | https://pan.dev/dlp/api/ | YES -- interactive DLP API testing |
| Terraform Provider (panos) | HCL | [Terraform Registry](https://registry.terraform.io/providers/PaloAltoNetworks/panos/) | Partial -- NGFW config, some DLP support |
| Ansible Collection | YAML | [Galaxy](https://galaxy.ansible.com/paloaltonetworks/panos) | Partial -- NGFW config |

---

## Key Findings

### 1. Strong API Coverage for Core Policy Objects (STRENGTH)

Unlike Trellix and Symantec, Palo Alto provides full CRUD API access for data patterns and data profiles. This enables:
- DLP-as-code workflows
- CI/CD pipeline integration for policy management
- Multi-tenant policy templating
- Automated pattern management from threat intelligence feeds

### 2. OAuth2 with TSG Scoping (STRENGTH)

The OAuth2 authentication model with Tenant Service Group scoping is well-designed for multi-tenant and enterprise environments. Service accounts with role-based access provide proper API security.

### 3. Three API Surfaces Create Complexity (WEAKNESS)

DLP API, Prisma SASE API, and SCM API are three separate surfaces that must be used together for end-to-end policy automation. There is no single unified API that covers pattern creation through security rule attachment.

### 4. Endpoint DLP API Gap (WEAKNESS)

Cortex XDR endpoint DLP is managed through a completely separate console and API surface. There is no unified API for managing both network and endpoint DLP policies.

### 5. EDM Still Requires CLI App (PARTIAL)

While EDM dataset management has API endpoints, the critical data preparation step (hashing and encryption) still requires the on-prem EDM CLI app. This breaks full API automation for EDM workflows.

### 6. Best Automation Opportunity

The highest-value automation paths:
1. **Data pattern pipeline**: Automate custom regex pattern creation/updates from threat intelligence
2. **Data profile management**: Programmatically compose profiles from patterns
3. **Security rule automation**: Create and update security rules with DLP profile groups
4. **Configuration push**: Automate config deployment via SASE API
5. **Incident/report retrieval**: Automate report generation and incident triage

---

## Sources

- [Data Loss Prevention APIs (pan.dev)](https://pan.dev/dlp/api/)
- [Prisma SASE API Get Started](https://pan.dev/sase/docs/getstarted/)
- [Welcome to Prisma SASE (pan.dev)](https://pan.dev/sase/docs/)
- [Retrieve Report Details API](https://pan.dev/dlp/api/get-v-1-public-report-reportid/)
- [Prisma Access APIs](https://docs.paloaltonetworks.com/prisma-access/administration/prisma-access-overview/prisma-access-apis)
- [Configuration: Enterprise DLP (SCM)](https://docs.paloaltonetworks.com/strata-cloud-manager/getting-started/configuration-scm/manage-configuration-enterprise-dlp)
