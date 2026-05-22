# API Intelligence: Skyhigh Security DLP -- Policy Authoring

> Researched: 2026-05-21 | API surfaces: 2 | Documented endpoints: Limited
> Confidence: MODERATE (primary surface is CASB API; DLP-specific API coverage is narrow)

---

## Executive Summary

Skyhigh Security DLP exposes a **limited API surface** for policy automation. The primary API is the **Skyhigh CASB API**, which provides access to sanctioned application management, incident retrieval, and some policy operations. However, the core DLP policy authoring operations (creating classifications, rule groups, rules) have **minimal to no API coverage** for direct CRUD operations.

The CASB API supports **API-based DLP scanning** of sanctioned cloud services (Lightning Link model), and the DLP Policy Wizard can create policies through the web console. But programmatic policy authoring (classifications, rules, rule groups) remains predominantly a console-only activity.

**Key finding:** Skyhigh DLP focuses its API on scanning and incident management, not policy authoring. Classification and policy creation are console-first activities with limited automation support.

---

## API Surfaces Discovered

| # | Type | Base URL Pattern | Auth Model | Docs Quality | Status |
|---|------|-----------------|------------|-------------|--------|
| 1 | REST (CASB API) | `https://<tenant>.myshn.net/api/...` | OAuth2 / API Token | MODERATE -- some endpoints documented | Active |
| 2 | REST (Trellix ePO - for Endpoint DLP) | `https://<ePO-server>:8443/remote/<command>` | HTTP Basic over TLS | GOOD -- see Trellix API intelligence | Active (Endpoint only) |

### Notes on Surfaces

- **CASB API (#1)** handles sanctioned cloud service integration, DLP scanning via API-based policies, and incident/anomaly management. Policy CRUD operations are limited.
- **Trellix ePO API (#2)** applies ONLY to endpoint DLP, which uses the Trellix DLP engine managed via ePO. See the Trellix DLP API intelligence document for full details.

---

## Authentication Model

### Skyhigh CASB API

```
Method: OAuth2 / API Token
Token: Generated from Skyhigh Security Dashboard > Settings > API Keys
Header: x-api-key: <api_key>
         or
         Authorization: Bearer <oauth_token>
Base URL: https://<tenant>.myshn.net/api/v1/...
```

---

## Endpoint Inventory

### A. Skyhigh CASB API -- DLP-Related Endpoints

| # | Method | Path | Description | Maps To (Policy Layer) |
|---|--------|------|-------------|----------------------|
| 1 | GET | `/api/v1/incidents` | List DLP policy incidents | Incident query |
| 2 | GET | `/api/v1/incidents/{id}` | Get incident details | Incident details |
| 3 | PUT | `/api/v1/incidents/{id}` | Update incident status/resolution | Incident management |
| 4 | GET | `/api/v1/anomalies` | List anomalies (DLP-triggered) | Anomaly query |
| 5 | GET | `/api/v1/policies` | List DLP policies | Policy listing |
| 6 | POST | `/api/v1/scan` | Trigger API-based DLP scan on content | Content inspection |
| 7 | GET | `/api/v1/services` | List connected cloud services | Service inventory |
| 8 | GET | `/api/v1/classifications` | List classifications (if available) | Classification query |

> **Note:** The exact endpoint paths may vary by tenant and API version. The above are representative based on available documentation and community sources.

### B. API-Based DLP Scanning (Lightning Link)

Skyhigh's "Lightning Link" model combines API-based scanning with inline enforcement:

| Capability | Description |
|-----------|-------------|
| API Scan | CASB scans sanctioned cloud service content via API after upload |
| Inline Enforcement | SWG/proxy inspects content in real-time for shadow/web traffic |
| Combined | Lightning Link blends API + inline for comprehensive coverage |

---

## API-to-UI Coverage Matrix

### Classification Layer

| # | Operation | UI Screen | API Endpoint | Coverage | Impact |
|---|-----------|-----------|-------------|----------|--------|
| 1 | Create classification | Policy > DLP > Classifications | None (confirmed) | **GAP** | **CRITICAL** -- Cannot create classifications via API |
| 2 | Edit classification | Policy > DLP > Classifications > Edit | None | **GAP** | **CRITICAL** |
| 3 | List classifications | Policy > DLP > Classifications | `GET /api/v1/classifications` (limited) | **PARTIAL** | Can list but not create/edit |
| 4 | Delete classification | Policy > DLP > Classifications > Delete | None | **GAP** | MEDIUM |

### Policy Layer

| # | Operation | UI Screen | API Endpoint | Coverage | Impact |
|---|-----------|-----------|-------------|----------|--------|
| 5 | Create policy | Policy > DLP > Policies > Create | None (confirmed for full CRUD) | **GAP** | **CRITICAL** |
| 6 | List policies | Policy > DLP > Policies | `GET /api/v1/policies` | **PARTIAL** | Can list existing policies |
| 7 | Edit policy rules | Policy > DLP > Policies > Edit | None | **GAP** | **CRITICAL** |
| 8 | Delete policy | Policy > DLP > Policies > Delete | None | **GAP** | MEDIUM |

### Rule Layer

| # | Operation | UI Screen | API Endpoint | Coverage | Impact |
|---|-----------|-----------|-------------|----------|--------|
| 9 | Create rule group | Policy > DLP > Policy > Rule Groups | None | **GAP** | **CRITICAL** |
| 10 | Create rule | Policy > DLP > Policy > Rules | None | **GAP** | **CRITICAL** |
| 11 | Edit rule | Policy > DLP > Policy > Rules > Edit | None | **GAP** | **CRITICAL** |

### Incident Layer (Read/Write)

| # | Operation | UI Screen | API Endpoint | Coverage | Impact |
|---|-----------|-----------|-------------|----------|--------|
| 12 | Query incidents | Incidents > DLP | `GET /api/v1/incidents` | **FULL** | Incident query |
| 13 | Get incident details | Incidents > Detail | `GET /api/v1/incidents/{id}` | **FULL** | Detail retrieval |
| 14 | Update incident | Incidents > Edit | `PUT /api/v1/incidents/{id}` | **FULL** | Status/resolution update |
| 15 | Query anomalies | Anomalies | `GET /api/v1/anomalies` | **FULL** | Anomaly listing |

### Scanning Layer

| # | Operation | UI Screen | API Endpoint | Coverage | Impact |
|---|-----------|-----------|-------------|----------|--------|
| 16 | API-based content scan | N/A (programmatic) | `POST /api/v1/scan` | **FULL** | On-demand scanning |
| 17 | Service management | Settings > Services | `GET /api/v1/services` | **FULL** | Service listing |

---

## API Gaps -- Console-Only Operations (Sorted by Impact)

| # | Operation | Impact | Workaround | Notes |
|---|-----------|--------|-----------|-------|
| 1 | Create/edit classifications | **CRITICAL** | Console-only via Skyhigh Dashboard | Core authoring has no API |
| 2 | Create/edit DLP policies | **CRITICAL** | Console-only; Policy Wizard available | Cannot automate policy creation |
| 3 | Create/edit rule groups | **CRITICAL** | Console-only | Boolean logic configuration manual only |
| 4 | Create/edit rules within policies | **CRITICAL** | Console-only | Rule CRUD entirely manual |
| 5 | Create/manage EDM fingerprints | **HIGH** | Console + DLP Integrator tool | On-prem tool required |
| 6 | Create/manage IDM fingerprints | **HIGH** | Console + IDMTrain tool | On-prem tool required |
| 7 | Policy template import/customization | **MEDIUM** | Console-only | Templates available in wizard |
| 8 | ML Auto Classifier configuration | **LOW** | Console-only; pre-trained models | Limited configuration options anyway |

**Summary: 8 of ~17 operations have API gaps. The entire policy authoring pipeline (classify > build rules > build rule groups > create policy) has ZERO API support. Only incident management and content scanning have full API coverage.**

---

## Integration Capabilities

### SIEM Integration

| Capability | Status | Mechanism |
|-----------|--------|-----------|
| Syslog (CEF) | YES | Configurable log forwarding |
| Splunk | YES | Skyhigh Security Add-on for Splunk |
| Microsoft Sentinel | YES | Via syslog connector |
| Google Chronicle | YES | Native parser |
| Generic SIEM | YES | CEF/LEEF over syslog |

### SOAR Integration

| Capability | Status | Details |
|-----------|--------|---------|
| XSOAR (Palo Alto) | PARTIAL | Via API integration |
| ServiceNow | YES | Incident forwarding |
| Custom webhooks | PARTIAL | Anomaly notification to webhook URLs |

### Cloud Service Integration (CASB)

| Service | Integration Type | DLP Support |
|---------|-----------------|-------------|
| Microsoft 365 | API + Inline | Full (Exchange, OneDrive, SharePoint, Teams) |
| Google Workspace | API + Inline | Full (Gmail, Drive) |
| Box | API + Inline | Full |
| Salesforce | API | Full |
| Slack | API + Inline | Full |
| Dropbox | API + Inline | Full |
| ServiceNow | API | Full |

---

## Key Findings

### 1. Massive Policy Authoring API Gap (CRITICAL)

Like Trellix (its parent lineage), Skyhigh DLP has no API for creating classifications, policies, rules, or rule groups. All policy authoring is console-only. This means:
- No DLP-as-code capability
- No CI/CD integration for policy management
- No programmatic multi-tenant policy templating
- Manual console work required for all policy changes

### 2. Incident and Scanning API Is Functional (STRENGTH)

The CASB API provides good coverage for:
- Incident querying and management
- API-based content scanning (Lightning Link)
- Service management
- Anomaly tracking

### 3. Two Divergent DLP Engines

Cloud DLP (CASB/SWG) uses the Skyhigh-native engine. Endpoint DLP uses the Trellix DLP engine managed via ePO. These are separate systems with separate APIs, separate authentication, and separate policy management.

### 4. Lightning Link Is a Unique Strength

The Lightning Link model (API + inline enforcement) provides broader coverage than pure API-based or pure inline CASB solutions. This is a competitive differentiator.

### 5. Competitive Intelligence

For a competing product, the API gaps represent opportunities:
- Full CRUD API for classifications and policies
- Policy-as-code with version control
- Unified API across cloud and endpoint DLP
- OpenAPI/Swagger specification
- Terraform/Pulumi providers

---

## Sources

- [API-Based Data Loss Prevention Policies](https://success.skyhighsecurity.com/Skyhigh_CASB/06_Skyhigh_CASB_Sanctioned_Applications/01_Skyhigh_CASB_Native_Sanctioned_Apps/Skyhigh_CASB_for_Salesforce/Configure_Skyhigh_CASB_for_Salesforce/API-Based_Data_Loss_Prevention_Policies)
- [Integrating DLP Policies with SWG (On-Prem) DLP](https://success.skyhighsecurity.com/Skyhigh_Data_Loss_Prevention/Skyhigh_CASB_DLP_Integrations/Integrating_DLP_Policies_with_SWG_(On-Prem)_DLP)
- [Integrating DLP policies with Skyhigh Security Cloud (Trellix docs)](https://docs.trellix.com/bundle/data-loss-prevention-11.11.x-product-guide/page/UUID-1da8a80b-045b-66c1-c1d9-baf362e1b3c4.html)
- [Create a Cloud DLP policy using the Policy Wizard](https://success.skyhighsecurity.com/Skyhigh_Data_Loss_Prevention/01_Data_Loss_Prevention_Concepts/Create_a_DLP_policy_using_the_Policy_Wizard)
- [Skyhigh CASB for Microsoft Teams](https://success.skyhighsecurity.com/Skyhigh_CASB/06_Skyhigh_CASB_Sanctioned_Applications/01_Skyhigh_CASB_Native_Sanctioned_Apps/Skyhigh_CASB_for_Microsoft_Teams/About_Skyhigh_CASB_for_Microsoft_Teams)
