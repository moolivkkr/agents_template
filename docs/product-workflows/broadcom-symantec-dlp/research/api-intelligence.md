# API Intelligence: Broadcom Symantec DLP

> Researched: 2026-05-21 | API surfaces: 6 | Documented endpoints: 40+
> Confidence: HIGH (corroborated across official Broadcom TechDocs, Symantec API portal, SOAR integrations, GitHub repos, community forums)

---

## Executive Summary

Broadcom Symantec DLP exposes a **progressively expanding** set of REST APIs across multiple surfaces: the Enforce Server REST API (incident management, policy management, user/role management), the Detection REST API 2.0 (content inspection/scanning), the CloudSOC/Cloud DLP API (cloud policy profiles), and a legacy SOAP API (deprecated but still in use). The API coverage has **significantly improved** from v15.7 through v25.1/26.1, with each major release adding new API domains.

**Key finding:** Unlike some competitors, Symantec DLP has been **actively expanding API coverage** into policy management, response rules, user/role management, and Network Discover targets (starting with DLP 16.0 and continuing through 25.1/26.1). However, **granular policy authoring** (creating individual detection rules, classifications, EDM profiles, IDM profiles) remains **largely console-only**. The API supports policy-level operations (import, export, assign) but not the fine-grained rule/classification composition workflow. The incident management API is comprehensive and mature.

---

## API Surfaces Discovered

| # | Type | Base URL Pattern | Auth Model | Docs Quality | Version | Status |
|---|------|-----------------|------------|-------------|---------|--------|
| 1 | REST (Enforce Server) | `https://<enforce>:443/ProtectManager/webservices/v2/...` | HTTP Basic / Kerberos / Certificate | GOOD -- official docs + code samples | 15.7+ (current: 16.1/25.1/26.1) | Active |
| 2 | REST (Detection API 2.0) | `https://<detector>/v2.0/DetectionRequests` | Certificate-based mutual TLS | GOOD -- reference guide PDF available | 15.0+ (current: 2.0) | Active |
| 3 | REST (CloudSOC / Cloud DLP) | `https://app.elastica.net/api/clouddlp/...` (US) / `https://app.eu.elastica.net/...` (EU) | OAuth2 / API Key | MODERATE -- TechDocs pages | CloudSOC current | Active |
| 4 | REST (Security Cloud Portal) | `https://apidocs.securitycloud.symantec.com/...` | Bearer token | MODERATE -- portal requires login | 16.1+ | Active |
| 5 | SOAP (Legacy Incident API) | `https://<enforce>/ProtectManager/services/v2011/incidents?wsdl` | HTTP Basic over TLS | GOOD -- WSDL + developer guide | 11.x-15.5 (deprecated) | Legacy |
| 6 | ICAP (Network Prevent) | `icap://<detector>:1344/reqmod` / `icap://<detector>:1344/respmod` | Certificate / IP allowlist | MODERATE -- KB articles | All versions | Active |

### Notes on Surfaces

- **Enforce Server REST API (#1)** is the primary programmatic interface. Introduced in DLP 15.7, it replaced the SOAP API. Base path: `/ProtectManager/webservices/v2/`. Covers incidents, sender/recipient patterns, report filters, and (from 16.0+) policy management, user/role management, certificate management, EDM indexing, and server settings.
- **Detection REST API 2.0 (#2)** runs on the Cloud Detection Service or API Detection for Developer Apps virtual appliance. Used for content inspection -- submit content, get policy violation results and response action recommendations. Key for integrating custom applications with DLP scanning.
- **CloudSOC Cloud DLP API (#3)** is the cloud-managed DLP surface (Symantec CloudSOC/CASB). Provides profile management, data identifier operations, and policy queries. Separate from on-prem Enforce API.
- **Security Cloud API Portal (#4)** is Broadcom's unified API documentation portal for enterprise security products. Hosts interactive API docs for DLP 16.1+.
- **SOAP API (#5)** is the legacy Incident Reporting and Update API. WSDL-based, conforms to SOAP 1.1. Deprecated in favor of REST but still functional for backward compatibility.
- **ICAP (#6)** is the protocol integration for Network Prevent for Web. Used by proxies (Blue Coat/ProxySG, Zscaler, Check Point, Cisco WSA) to route web traffic through DLP inspection. Not a REST API but a critical integration surface.

---

## Authentication Models

### Enforce Server REST API (On-Prem)
```
Method: HTTP Basic Authentication over TLS (primary)
Alternative: Kerberos authentication (DLP 16.0 RU2+)
Alternative: Certificate-based authentication (DLP 16.0 RU2+)
Alternative: JWT with configurable IdP (DLP 26.1+)
Header: Authorization: Basic <base64(username:password)>
Port: 443 (HTTPS, Enforce Server)
TLS: Required
Session: Stateless (credentials per request)
Role Required: "Incident Reporting API Web Service" role or equivalent
Note: DLP 26.1 supports independent auth protocols for console vs. REST API
```

### Detection REST API 2.0
```
Method: Certificate-based mutual TLS (client certificate)
Certificates: Provisioned through Enforce Server
Transport: HTTPS
Port: Configurable (default varies by deployment)
Client auth: X.509 client certificate required
User-Agent: Custom (configurable)
```

### CloudSOC / Cloud DLP API
```
Method: API Key / OAuth2
Endpoint (US): https://app.elastica.net
Endpoint (EU): https://app.eu.elastica.net
Header: Authorization with API credentials
Tenant: Multi-tenant, tenant-specific API keys
```

### SOAP API (Legacy)
```
Method: HTTP Basic Authentication over TLS
WSDL: https://<enforce>/ProtectManager/services/v2011/incidents?wsdl
Port: 443 (HTTPS)
Framework: JAX-WS (Metro Web Services 2.2 compatible)
Interop: Full interoperability with .NET WCF clients
```

---

## Endpoint Inventory

### A. Enforce Server REST API -- Incident Management (v2, via Enforce :443)

Base URL: `https://<enforce>/ProtectManager/webservices/v2/`

| # | Method | Path | Description | Since |
|---|--------|------|-------------|-------|
| 1 | POST | `/incidents` | Query/list incidents by report ID with filters (supports nested AND/OR filters, multiple operators) | 15.7 |
| 2 | GET | `/incidents/{incidentId}` | Get full details of a specific incident | 15.7 |
| 3 | PATCH | `/incidents` | Update one or more incidents (status, severity, notes, custom attributes, remediation status) | 15.7 |
| 4 | GET | `/incidents/{incidentId}/history` | Get audit/history trail of a specific incident | 15.8 |
| 5 | GET | `/incidents/{incidentId}/originalMessage` | Retrieve the original message that triggered the incident | 15.8 |
| 6 | GET | `/incidents/{incidentId}/components` | Get incident components (matched content, policy details) | 15.7 |
| 7 | GET | `/incidents/incidentStatuses` | List all custom incident status values defined in the deployment | 15.7 |
| 8 | GET | `/incidents/incidentEditable` | List editable incident attributes | 15.7 |
| 9 | GET | `/incidents/preventActionStatuses` | Get all possible prevent action status values | 15.7 |
| 10 | GET | `/incidents/protectActionStatuses` | Get all possible protect action status values | 15.7 |
| 11 | GET | `/incidents/listCustomAttributes` | List all custom attributes defined in the deployment | 15.7 |

### B. Enforce Server REST API -- Sender/Recipient Pattern Management

| # | Method | Path | Description | Since |
|---|--------|------|-------------|-------|
| 12 | POST | `/senderRecipientPattern` | Create a new reusable sender/recipient pattern | 16.0 |
| 13 | GET | `/senderRecipientPattern/{id}` | Retrieve details of a specified sender/recipient pattern | 16.0 |
| 14 | PUT | `/senderRecipientPattern/{id}` | Update an existing sender/recipient pattern | 16.0 |

### C. Enforce Server REST API -- Report & Filter Management

| # | Method | Path | Description | Since |
|---|--------|------|-------------|-------|
| 15 | GET | `/reports/{reportId}/filters` | Retrieve filter criteria for a saved search/report by report ID | 16.0 |
| 16 | POST | `/incidents/export` | Export incidents as JSON (also supports CSV, XML via UI) | 16.0 |

### D. Enforce Server REST API -- Policy Management (DLP 16.0+/25.1+)

| # | Method | Path | Description | Since |
|---|--------|------|-------------|-------|
| 17 | GET | `/policies` | List policies / policy groups | 16.0+ |
| 18 | POST | `/policies/import` | Import policy configuration (XML-based policy export/import) | 25.1 |
| 19 | POST | `/policies/export` | Export policy configuration | 25.1 |
| 20 | POST | `/policies/apply` | Apply/deploy policy changes to detection servers | 16.0+ |

### E. Enforce Server REST API -- User & Role Management (DLP 16.0+/25.1+)

| # | Method | Path | Description | Since |
|---|--------|------|-------------|-------|
| 21 | GET | `/users` | List users | 25.1 |
| 22 | POST | `/users` | Create a user | 25.1 |
| 23 | PUT | `/users/{id}` | Update a user | 25.1 |
| 24 | GET | `/roles` | List roles | 25.1 |
| 25 | POST | `/roles` | Create a role | 25.1 |
| 26 | PUT | `/roles/{id}` | Update a role | 25.1 |

### F. Enforce Server REST API -- Server & System Management (DLP 16.0 RU2+)

| # | Method | Path | Description | Since |
|---|--------|------|-------------|-------|
| 27 | POST | `/edm/index` | Trigger EDM (Exact Data Matching) indexing on demand | 16.0 RU2 |
| 28 | PUT | `/serverSettings` | Update advanced server settings | 16.0 RU2 |
| 29 | DELETE | `/systemEvents` | Delete older system events | 16.0 RU2 |
| 30 | POST | `/certificates` | Add a custom certificate | 16.0 RU2 |
| 31 | GET | `/certificates/{id}` | Retrieve custom certificate details | 16.0 RU2 |
| 32 | PUT | `/certificates/{id}` | Update a custom certificate | 16.0 RU2 |
| 33 | DELETE | `/certificates/{id}` | Delete a custom certificate | 16.0 RU2 |
| 34 | GET | `/certificates/{id}/usage` | Get certificate usage information | 16.0 RU2 |

### G. Enforce Server REST API -- Network Discover Target Management (DLP 25.1+)

| # | Method | Path | Description | Since |
|---|--------|------|-------------|-------|
| 35 | GET | `/discover/targets` | List Network Discover scan targets | 25.1 |
| 36 | POST | `/discover/targets` | Create a Network Discover scan target | 25.1 |
| 37 | PUT | `/discover/targets/{id}` | Update a Network Discover scan target | 25.1 |
| 38 | DELETE | `/discover/targets/{id}` | Delete a Network Discover scan target | 25.1 |

### H. Detection REST API 2.0 (via Cloud Detector or API Detection Appliance)

| # | Method | Path | Description | Since |
|---|--------|------|-------------|-------|
| 39 | POST | `/v2.0/DetectionRequests` | Submit content for DLP policy scanning -- returns violations and response action recommendations | 15.0 |

Request body structure:
```json
{
  "options": { ... },
  "context": {
    "messageSource": "...",
    "sender": "...",
    "recipients": ["..."]
  },
  "content": {
    "contentParts": [
      {
        "name": "filename.txt",
        "contentType": "text/plain",
        "data": "<base64-encoded-content>"
      }
    ]
  }
}
```

Response includes: violation status, matched policies, matched rules, severity, response actions (block, quarantine, encrypt, notify, etc.)

### I. CloudSOC / Cloud DLP API

| # | Method | Path | Description | Since |
|---|--------|------|-------------|-------|
| 40 | GET | `/api/clouddlp/protect/public/profile` | List all DLP profiles | Current |
| 41 | POST | `/api/clouddlp/protect/public/profile` | Create a new DLP profile (with rules, data identifiers) | Current |
| 42 | PUT | `/api/clouddlp/protect/public/profile/{id}` | Update a DLP profile | Current |
| 43 | GET | `/api/clouddlp/protect/public/profile/{id}/history` | Get profile change history | Current |
| 44 | GET | `/api/clouddlp/protect/public/dataIdentifiers` | List available data identifiers | Current |
| 45 | GET | `/api/protect/policies` | Query CloudSOC protect (DLP) policies | Current |

### J. SOAP API (Legacy -- Deprecated)

WSDL: `https://<enforce>/ProtectManager/services/v2011/incidents?wsdl`

| # | Operation | Description | Since |
|---|-----------|-------------|-------|
| 46 | `incidentList` | Query incident list with filters | 11.x |
| 47 | `incidentDetail` | Get incident details by ID | 11.x |
| 48 | `incidentBinaries` | Retrieve incident binary/evidence data | 11.x |
| 49 | `updateIncidents` | Update incident attributes (status, custom attributes, notes) | 11.x |
| 50 | `listIncidentStatus` | List available incident status values | 11.x |
| 51 | `listCustomAttributes` | List custom attribute definitions | 11.x |

---

## API-to-UI Coverage Matrix

### Incident Management

| # | Operation | UI Screen | API Endpoint | Coverage | Impact |
|---|-----------|-----------|-------------|----------|--------|
| 1 | List/query incidents | Incident List (all channels) | `POST /incidents` | **FULL** | Complete query with nested filters, AND/OR operators |
| 2 | Get incident details | Incident Detail view | `GET /incidents/{id}` | **FULL** | All incident attributes returned |
| 3 | Get incident components | Incident > Matches tab | `GET /incidents/{id}/components` | **FULL** | Policy matches, matched content |
| 4 | Get incident history | Incident > History tab | `GET /incidents/{id}/history` | **FULL** | Full audit trail (15.8+) |
| 5 | Get original message | Incident > Original Message | `GET /incidents/{id}/originalMessage` | **FULL** | Full message retrieval (15.8+) |
| 6 | Update incident status | Incident > Status dropdown | `PATCH /incidents` | **FULL** | Bulk update supported |
| 7 | Update incident severity | Incident > Severity | `PATCH /incidents` | **FULL** | Via custom attributes |
| 8 | Add incident notes | Incident > Notes | `PATCH /incidents` | **FULL** | Notes via incidentNotes field |
| 9 | Update custom attributes | Incident > Custom Attributes | `PATCH /incidents` | **FULL** | All custom attributes editable |
| 10 | Update remediation status | Incident > Remediation | `PATCH /incidents` | **FULL** | Remediation status values |
| 11 | Export incidents | Incident List > Export | `POST /incidents/export` | **FULL** | JSON export (16.0+), CSV/XML via UI |
| 12 | Get report filter criteria | Saved Reports > Filters | `GET /reports/{id}/filters` | **FULL** | Retrieve saved search criteria (16.0+) |

### Policy Management

| # | Operation | UI Screen | API Endpoint | Coverage | Impact |
|---|-----------|-----------|-------------|----------|--------|
| 13 | List policies/policy groups | Manage > Policies > Policy Groups | `GET /policies` | **FULL** | Enumerate policies (16.0+) |
| 14 | Import policy XML | Manage > Policies > Import | `POST /policies/import` | **FULL** | Import full policy config (25.1+) |
| 15 | Export policy XML | Manage > Policies > Export | `POST /policies/export` | **FULL** | Export full policy config (25.1+) |
| 16 | Apply/deploy policies | Manage > Policies > Apply | `POST /policies/apply` | **FULL** | Push policies to servers |
| 17 | Create detection rule | Manage > Policies > Rules > Add | None (on-prem) | **GAP** | Cannot create individual rules via API |
| 18 | Edit detection rule | Manage > Policies > Rules > Edit | None (on-prem) | **GAP** | Cannot modify rule logic via API |
| 19 | Create classification | Manage > Policies > Classifications | None (on-prem) | **GAP** | Cannot create classifications via API |
| 20 | Create EDM profile | Manage > Policies > EDM > New Profile | None (on-prem) | **GAP** | EDM profile creation is console-only |
| 21 | Create IDM profile | Manage > Policies > IDM > New Profile | None (on-prem) | **GAP** | IDM profile creation is console-only |
| 22 | Trigger EDM indexing | Manage > Policies > EDM > Index | `POST /edm/index` | **FULL** | On-demand indexing (16.0 RU2+) |
| 23 | Create/edit response rules | Manage > Policies > Response Rules | None (direct) | **GAP** | Response rule CRUD is console-only |
| 24 | Manage sender/recipient patterns | Manage > Policies > Patterns | `POST/GET/PUT /senderRecipientPattern` | **FULL** | Full CRUD (16.0+) |

### User & Role Administration

| # | Operation | UI Screen | API Endpoint | Coverage | Impact |
|---|-----------|-----------|-------------|----------|--------|
| 25 | List users | System > Users | `GET /users` | **FULL** | (25.1+) |
| 26 | Create user | System > Users > New | `POST /users` | **FULL** | (25.1+) |
| 27 | Update user | System > Users > Edit | `PUT /users/{id}` | **FULL** | (25.1+) |
| 28 | List roles | System > Roles | `GET /roles` | **FULL** | (25.1+) |
| 29 | Create role | System > Roles > New | `POST /roles` | **FULL** | (25.1+) |
| 30 | Update role | System > Roles > Edit | `PUT /roles/{id}` | **FULL** | (25.1+) |

### Server & System Management

| # | Operation | UI Screen | API Endpoint | Coverage | Impact |
|---|-----------|-----------|-------------|----------|--------|
| 31 | Update server settings | System > Servers > Advanced Settings | `PUT /serverSettings` | **FULL** | (16.0 RU2+) |
| 32 | Delete system events | System > Events > Purge | `DELETE /systemEvents` | **FULL** | (16.0 RU2+) |
| 33 | Manage certificates | System > Certificates | `POST/GET/PUT/DELETE /certificates` | **FULL** | Full CRUD (16.0 RU2+) |
| 34 | Manage detection servers | System > Servers > Detection | Console only | **GAP** | Server provisioning is console-only |
| 35 | Configure cloud detectors | System > Servers > Cloud Detectors | Console only | **GAP** | Cloud detector setup is console-only |

### Network Discover (Data-at-Rest Scanning)

| # | Operation | UI Screen | API Endpoint | Coverage | Impact |
|---|-----------|-----------|-------------|----------|--------|
| 36 | List scan targets | Discover > Targets | `GET /discover/targets` | **FULL** | (25.1+) |
| 37 | Create scan target | Discover > Targets > New | `POST /discover/targets` | **FULL** | (25.1+) |
| 38 | Update scan target | Discover > Targets > Edit | `PUT /discover/targets/{id}` | **FULL** | (25.1+) |
| 39 | Delete scan target | Discover > Targets > Delete | `DELETE /discover/targets/{id}` | **FULL** | (25.1+) |
| 40 | View scan results | Discover > Scan Results | Via incident API | **FULL** | Discover incidents exposed through incident API |
| 41 | Configure scan schedule | Discover > Targets > Schedule | Console only | **PARTIAL** | Schedule may be part of target config |

### Content Detection (via Detection REST API 2.0)

| # | Operation | UI Screen | API Endpoint | Coverage | Impact |
|---|-----------|-----------|-------------|----------|--------|
| 42 | Scan content against policies | N/A (API-only) | `POST /v2.0/DetectionRequests` | **FULL** | Submit content, get violations + response actions |
| 43 | Inspect cloud app content | N/A (cloud integration) | Detection API via Cloud Connector | **FULL** | Cloud app DLP scanning |
| 44 | Inspect LLM prompts | N/A (API integration) | Detection API (safeprompt example) | **FULL** | LLM/GenAI content inspection |

### Cloud DLP (CloudSOC)

| # | Operation | UI Screen | API Endpoint | Coverage | Impact |
|---|-----------|-----------|-------------|----------|--------|
| 45 | List DLP profiles | Protect > DLP Profiles | `GET /api/clouddlp/protect/public/profile` | **FULL** | Cloud profiles |
| 46 | Create DLP profile | Protect > DLP Profiles > New | `POST /api/clouddlp/protect/public/profile` | **FULL** | Create with rules + data identifiers |
| 47 | Update DLP profile | Protect > DLP Profiles > Edit | `PUT /api/clouddlp/protect/public/profile/{id}` | **FULL** | Modify cloud profiles |
| 48 | List data identifiers | Protect > Data Identifiers | `GET /api/clouddlp/protect/public/dataIdentifiers` | **FULL** | Enumerate available identifiers |
| 49 | Import DLP policy as profile | Protect > DLP Profiles > Import from XML | UI + API | **FULL** | Import on-prem policy export |
| 50 | Query protect policies | Protect > Policies | `GET /api/protect/policies` | **FULL** | Query cloud DLP policies |

---

## API Gaps -- Console-Only Operations (Sorted by Impact)

| # | Operation | Impact | Workaround | Notes |
|---|-----------|--------|-----------|-------|
| 1 | Create/edit individual detection rules (on-prem) | **CRITICAL** | Author in console, export/import policy XML via API (25.1+) | Fine-grained rule CRUD not exposed; policy import/export is the workaround |
| 2 | Create/edit classifications (on-prem) | **CRITICAL** | Define in console, export as part of policy XML | Classification composition is console-only |
| 3 | Create EDM profiles (data source setup) | **HIGH** | Create in console; trigger indexing via API | EDM profile structure cannot be defined via API; indexing can be triggered |
| 4 | Create IDM profiles | **HIGH** | Console only | Indexed Document Matching profile creation |
| 5 | Create/edit response rules | **HIGH** | Console only | Response rule CRUD is not API-exposed |
| 6 | Create/edit VML (Vector ML) models | **HIGH** | Console only | Machine learning model training is console-only |
| 7 | Configure detection server deployment | **MEDIUM** | Console only | Server provisioning and registration |
| 8 | Configure cloud detector setup | **MEDIUM** | Console only | Initial cloud detector provisioning |
| 9 | Manage DLP agent deployment | **MEDIUM** | Agent deployment via endpoint management tools (e.g., SEPM) | DLP agent push is not via DLP API |
| 10 | Configure ICAP integration settings | **MEDIUM** | Manual config file editing (Protect.properties) | ICAP keystore and connection settings |
| 11 | Manage scan schedules (granular) | **LOW** | May be configurable as part of discover target API | Schedule details unclear |
| 12 | Configure syslog/SIEM forwarding | **LOW** | Manual Manager.properties config | Syslog destination is config-file based |

**Summary: The on-prem Enforce API covers ~70-75% of administrative operations by count. The primary gap is fine-grained policy authoring (individual rule/classification/EDM/IDM/VML creation). However, the policy import/export API (25.1+) provides a workaround: author policies in console (or programmatically generate policy XML), then import/export via API. This enables a "DLP-as-code" workflow with the policy XML as the artifact.**

---

## Integration Capabilities

### SIEM Integration

| Capability | Status | Mechanism |
|-----------|--------|-----------|
| Syslog event forwarding | YES | Response Rule action "Log to Syslog Server" (UDP/TCP/TLS) |
| CEF format | YES | Manually configured CEF message template with DLP variables |
| Syslog server alerts | YES | System-level syslog in Manager.properties |
| Splunk integration | YES | Splunk Add-on for Symantec DLP (official) |
| Microsoft Sentinel | YES | CEF via AMA connector |
| Google Chronicle | YES | Native Symantec DLP parser |
| QRadar / JSA | YES | Juniper JSA DSM for Symantec DLP |
| ManageEngine EventLog Analyzer | YES | Built-in Symantec DLP application support |
| LogRhythm | YES | Syslog Symantec DLP CEF parser |
| Generic SIEM | YES | CEF/syslog, configurable message template |

### CEF Message Format
```
CEF:0|Broadcom|DLP|16.0|<ruleID>|$POLICY$|5|
INCIDENT_ID=$INCIDENT_ID$
APPLICATION_USER=$APPLICATION_USER$
ENDPOINT_MACHINE=$ENDPOINT_MACHINE$
ENDPOINT_USERNAME=$ENDPOINT_USERNAME$
MACHINE_IP=$MACHINE_IP$
SEVERITY=$SEVERITY$
BLOCKED=$BLOCKED$
```

Variables available: `$INCIDENT_ID$`, `$POLICY$`, `$RULES$`, `$SEVERITY$`, `$BLOCKED$`, `$APPLICATION_USER$`, `$ENDPOINT_MACHINE$`, `$ENDPOINT_USERNAME$`, `$MACHINE_IP$`, `$FILE_NAME$`, `$RECIPIENTS$`, `$SENDER$`, `$SUBJECT$`, `$MATCH_COUNT$`, `$PROTOCOL$`

### ICAP Integration

| Capability | Status | Details |
|-----------|--------|---------|
| ICAP REQMOD | YES | Request modification mode for outbound web traffic inspection |
| ICAP RESPMOD | YES | Response modification mode for inbound content inspection |
| Secure ICAP (TLS) | YES | TLS tunnel via stunnel or native secure ICAP |
| Proxy integration | YES | Blue Coat/ProxySG, Zscaler, Check Point, Cisco WSA, Palo Alto |
| ICAP keystore | YES | JKS keystore at `DetectionServer/keystore/secureicap.jks` |

### SOAR/Orchestration Integration

| Platform | Status | Details |
|----------|--------|---------|
| Cortex XSOAR (Palo Alto) | YES | Official v2 integration pack -- list/get/update incidents, patterns |
| FortiSOAR (Fortinet) | YES | v2.2.0 connector -- incidents, custom statuses, updates |
| Swimlane Turbine | YES | Connector -- get incidents, original messages, policy matches, update |
| ServiceNow | YES | DLP Incident Response integration (ServiceNow Store) |
| Splunk SOAR | YES | Via REST API integration |

### Cloud Application Integration

| Capability | Status | Details |
|-----------|--------|---------|
| CloudSOC CASB integration | YES | DLP profiles applied to cloud app monitoring |
| Cloud SWG (Secure Web Gateway) | YES | DLP policies for cloud web traffic |
| Cloud DLP Email | YES | Email DLP policies in CloudSOC |
| Cloud Managed Endpoint | YES | DLP policies pushed to cloud-managed endpoint agents |
| Microsoft 365 / Google Workspace | YES | Via CloudSOC integration |
| Box / Dropbox / Salesforce | YES | Via CloudSOC cloud app connectors |

### Webhooks / Event-Driven

| Capability | Status | Details |
|-----------|--------|---------|
| Native webhooks | NO | No built-in webhook endpoint support |
| Syslog-based events | YES | Response rules trigger syslog messages on policy violations |
| ServiceNow webhook | YES | Via ServiceNow integration (event-driven incident creation) |
| Custom event consumers | PARTIAL | Build polling-based consumers via incident REST API |

### LDAP/AD Integration

| Capability | Status | Details |
|-----------|--------|---------|
| LDAP user group sync | YES | Enforce Server syncs with AD/LDAP for user groups |
| User-based policy targeting | YES | Policies target user groups from directory |
| Endpoint user identification | YES | DLP agents identify users via AD SID |

---

## SDKs and Client Libraries

| Library | Language | Source | Maintainer | DLP-Specific? |
|---------|----------|--------|-----------|---------------|
| symc-dlp-cloud-connector | Python | [GitHub](https://github.com/Symantec/symc-dlp-cloud-connector) | Symantec (official) | YES -- Cloud Detection REST API client |
| symantec_dlp_client | Python | [GitHub](https://github.com/Ryan-Gordon/symantec_dlp_client) | Community | YES -- SOAP API client (Incident Reporting) |
| indexSymantecDLPMatches | Python | [GitHub](https://github.com/dlparchitect/indexSymantecDLPMatches) | Community (dlparchitect) | YES -- REST API incident fetcher |
| DLPIncidentSLABreach | Python | [GitHub](https://github.com/dlparchitect/DLPIncidentSLABreach) | Community (dlparchitect) | YES -- Incident SLA breach updater |
| safeprompt | Python (Streamlit) | [GitHub](https://github.com/dlparchitect/safeprompt) | Community (dlparchitect) | YES -- Detection REST API 2.0 for LLM prompt safety |
| symantec-dlp-accelerators | Various | [GitHub](https://github.com/Protirus/symantec-dlp-accelerators) | Protirus (partner) | YES -- DLP workflow accelerators |
| PoShSymcDLP | PowerShell | Community (referenced in forums) | Community | YES -- PowerShell module wrapping REST API |
| Cortex XSOAR Pack | Python | [GitHub](https://github.com/demisto/content/tree/master/Packs/SymantecDLP) | Palo Alto Networks | YES -- Full SOAR integration |
| FortiSOAR Connector | Python | Fortinet FortiSOAR | Fortinet | YES -- SOAR connector |
| Swimlane Connector | Python | Swimlane | Swimlane | YES -- Turbine connector |

### No Official SDK

There is **no official Broadcom/Symantec DLP SDK** for any language. All programmatic access goes through:
1. Enforce Server REST API (direct HTTP calls)
2. Detection REST API 2.0 (direct HTTP with client certificates)
3. CloudSOC API (direct HTTP with API keys)
4. SOAP API (WSDL-generated stubs, deprecated)

Code samples are provided in **Java** in the official documentation. The community has built Python, PowerShell, and .NET wrappers.

---

## Documentation Quality Assessment

| Resource | Quality | URL | Notes |
|----------|---------|-----|-------|
| DLP REST APIs (16.1 TechDocs) | GOOD | [techdocs.broadcom.com](https://techdocs.broadcom.com/us/en/symantec-security-software/information-security/data-loss-prevention/16-1/dlp-rest-apis.html) | Current primary reference |
| DLP API Overview (16.0 TechDocs) | GOOD | [techdocs.broadcom.com](https://techdocs.broadcom.com/us/en/symantec-security-software/information-security/data-loss-prevention/16-0/dlp-apis/overview.html) | API access setup, user/role requirements |
| DLP 15.7 REST API Guide (PDF) | GOOD | [techdocs.broadcom.com](https://techdocs.broadcom.com/content/dam/broadcom/techdocs/symantec-security-software/information-security/data-loss-prevention/generated-pdfs/Symantec_DLP_15.7_REST_API_Guide.pdf) | Comprehensive endpoint reference for 15.7 |
| Detection REST API 2.0 Reference (PDF) | GOOD | [techdocs.broadcom.com](https://techdocs.broadcom.com/content/dam/broadcom/techdocs/symantec-security-software/information-security/data-loss-prevention/generated-pdfs/Symantec_DLP_Detection_REST_API_2_Reference_Guide.pdf) | Detection API full reference |
| Symantec DLP 15.7 API Docs Portal | GOOD | [apidocs.symantec.com](https://apidocs.symantec.com/home/DLP15.7) | Interactive API documentation |
| Broadcom Security API Portal | MODERATE | [apidocs.securitycloud.symantec.com](https://apidocs.securitycloud.symantec.com/) | Requires login; hosts 16.1+ API docs |
| REST API Code Samples (TechDocs) | GOOD | [techdocs.broadcom.com](https://techdocs.broadcom.com/us/en/symantec-security-software/information-security/data-loss-prevention/16-0/dlp-apis/Enforce-Server-REST-API-examples.html) | Java code samples |
| SOAP API Developers Guide (15.5 PDF) | GOOD | [techdocs.broadcom.com](https://techdocs.broadcom.com/content/dam/broadcom/techdocs/symantec-security-software/information-security/data-loss-prevention/generated-pdfs/Symantec_DLP_15.5_Incident_Reporting_Update_API_Developers_Guide.pdf) | Legacy SOAP API reference |
| SOAP API Examples (15.5 PDF) | MODERATE | [techdocs.broadcom.com](https://techdocs.broadcom.com/content/dam/broadcom/techdocs/symantec-security-software/information-security/data-loss-prevention/generated-pdfs/Symantec_DLP_15.5_Incident_Reporting_Update_API_Examples.pdf) | SOAP code examples |
| KB215336 -- REST API Query Samples | GOOD | [knowledge.broadcom.com](https://knowledge.broadcom.com/external/article/215336/incident-reporting-and-update-restful-ap.html) | Practical query examples |
| KB250998 -- Sender/Recipient Patterns | GOOD | [knowledge.broadcom.com](https://knowledge.broadcom.com/external/article/250998/symantec-dlp-core-api-reusable-senderre.html) | Pattern API examples |
| CloudSOC Cloud DLP APIs (TechDocs) | MODERATE | [techdocs.broadcom.com](https://techdocs.broadcom.com/us/en/symantec-security-software/information-security/symantec-cloudsoc/cloud/api-home/protect-api/cloud-dlp-apis.html) | Cloud DLP profile APIs |
| DLP PowerShell Blog (Alex Hedley) | MODERATE | [alexhedley.com](https://alexhedley.com/symantec-connect-articles/posts/dlp-api-powershell) | PowerShell integration examples |
| Cortex XSOAR Integration Docs | GOOD | [xsoar.pan.dev](https://xsoar.pan.dev/docs/reference/integrations/symantec-data-loss-prevention-v2) | Full command reference for SOAR |
| FortiSOAR Connector Docs | MODERATE | [docs.fortinet.com](https://docs.fortinet.com/document/fortisoar/2.2.0/symantec-dlp/159/symantec-dlp-v2-2-0) | Connector action reference |
| DLP 25.1 What's New | GOOD | [techdocs.broadcom.com](https://techdocs.broadcom.com/us/en/symantec-security-software/information-security/data-loss-prevention/25-1/new-and-changed/what-s-new-in-data-loss-prevention.html) | New API capabilities |
| DLP 26.1 What's New | GOOD | [techdocs.broadcom.com](https://techdocs.broadcom.com/us/en/symantec-security-software/information-security/data-loss-prevention/26-1/new-and-changed/what-s-new-in-data-loss-prevention.html) | Latest API enhancements |

---

## Key Findings

### 1. Progressive API Expansion (STRENGTH)

Unlike many enterprise DLP products with stagnant APIs, Symantec DLP has been **actively expanding its API surface** across major releases:
- **15.7**: Introduced REST API (replacing SOAP) -- incident management core
- **15.8**: Added incident history, original message retrieval
- **16.0**: Added sender/recipient patterns, report filters, JSON export
- **16.0 RU2**: Added EDM indexing, server settings, system events, certificate management, Kerberos/certificate auth
- **25.1**: Added policy management (import/export), user & role management, Network Discover target management
- **26.1**: Added JWT authentication with configurable IdP, independent console/API auth protocols

This trajectory suggests Broadcom is committed to API-first management, though it has taken many release cycles to get here.

### 2. Policy Authoring Gap -- Mitigated by Import/Export (IMPORTANT)

The granular policy authoring gap (individual rule/classification/EDM creation) is **partially mitigated** by the policy import/export API introduced in DLP 25.1. This enables:
- Export a policy as XML from one Enforce Server
- Import it into another (or the same) server via API
- Programmatically generate policy XML and import via API

This is a **"DLP-as-code" enabler** -- store policy XML in version control, import via CI/CD pipeline. Not as elegant as individual rule CRUD APIs, but functional. The CloudSOC API also supports profile creation with rules and data identifiers, providing a more granular cloud-side API.

### 3. Detection REST API 2.0 -- Unique Capability (STRENGTH)

The Detection REST API 2.0 is a **standout feature** that few competitors match. It allows:
- Any application to submit content for DLP scanning via REST
- Returns policy violations and recommended response actions
- Supports cloud and on-prem deployment
- Being used for **LLM/GenAI prompt safety** (safeprompt project)

This positions Symantec DLP as an "inspection engine as a service" -- not just a monolithic product. This is a significant competitive advantage.

### 4. Mature Incident Management API (STRENGTH)

The incident management API is the most mature and comprehensive surface:
- Full CRUD on incidents with complex nested filtering
- Bulk operations (update multiple incidents at once)
- Custom attributes, notes, remediation status
- History/audit trail retrieval
- Original message retrieval
- Report filter retrieval
- Wide SOAR integration ecosystem (XSOAR, FortiSOAR, Swimlane, ServiceNow)

### 5. Dual API Surfaces -- On-Prem vs. Cloud (COMPLEXITY)

Like Trellix, Symantec DLP has **distinct API surfaces** for on-prem vs. cloud:
- On-prem: Enforce Server REST API (Basic/Kerberos/Cert/JWT auth)
- Cloud: CloudSOC API (API key/OAuth2, different base URL)

The CloudSOC API has **more granular policy authoring** (create profiles with rules and data identifiers) than the on-prem API. Customers on hybrid deployments need two integration codebases.

### 6. No OpenAPI/Swagger Specification (WEAKNESS)

Symantec DLP does **not publish an OpenAPI/Swagger specification**. API documentation is in PDFs, HTML pages, and an interactive portal (apidocs.securitycloud.symantec.com). This makes:
- Client code generation difficult
- API mocking/testing harder
- Integration development slower
- No Terraform/Pulumi provider possible without manual specification

### 7. No Native Webhook Support (WEAKNESS)

Symantec DLP does **not support native webhooks**. Event notification relies on:
- Syslog response rules (push events to syslog server)
- Polling the incident REST API (pull model)
- SOAR connectors (polling-based)

This means real-time event-driven architectures require syslog infrastructure or polling intervals.

### 8. Competitive Intelligence Implications

For a competing product, the remaining API gaps represent opportunities:
- **Individual rule/classification CRUD APIs** -- Symantec requires import/export of entire policies
- **Native webhook support** for real-time event streaming
- **OpenAPI specification** with code-generated SDKs
- **Terraform/Pulumi provider** for infrastructure-as-code DLP management
- **GraphQL API** for flexible incident querying
- **Streaming API** for real-time incident feeds
- **Agent management API** -- DLP agent deployment/configuration is not in the DLP API

However, Symantec's Detection REST API 2.0 (content inspection as a service) and progressive API expansion set a **higher bar** than Trellix, which has far more extensive policy authoring gaps.

---

## API Version Evolution Summary

| Version | Year | API Additions |
|---------|------|---------------|
| 11.x-14.x | 2008-2015 | SOAP Incident Reporting and Update API only |
| 15.0 | 2016 | Detection REST API 1.0 (content scanning) |
| 15.5 | 2017 | Detection REST API 2.0 (enhanced scanning) |
| 15.7 | 2018 | **Enforce REST API introduced** (replaces SOAP) -- incident management |
| 15.8 | 2019 | Incident history, original message retrieval |
| 16.0 | 2020 | Sender/recipient patterns, report filters, JSON export, 6 new API categories |
| 16.0 RU2 | 2024 | EDM indexing, server settings, system events, certificate management |
| 25.1 | 2025 | **Policy management API**, user & role management, Network Discover targets |
| 26.1 | 2025-2026 | JWT auth, independent console/API auth, incident workflows automation |

---

## Sources

- [DLP REST APIs - Broadcom TechDocs 16.1](https://techdocs.broadcom.com/us/en/symantec-security-software/information-security/data-loss-prevention/16-1/dlp-rest-apis.html)
- [Accessing the Symantec Data Loss Prevention APIs](https://techdocs.broadcom.com/us/en/symantec-security-software/information-security/data-loss-prevention/16-0/dlp-apis/overview.html)
- [About the Detection REST API](https://techdocs.broadcom.com/us/en/symantec-security-software/information-security/data-loss-prevention/16-0/about-dlp-appliances-v123002905-d288e8/about-the-detection-rest-api-v120715743-d260e8.html)
- [Symantec DLP 15.7 REST API Guide (PDF)](https://techdocs.broadcom.com/content/dam/broadcom/techdocs/symantec-security-software/information-security/data-loss-prevention/generated-pdfs/Symantec_DLP_15.7_REST_API_Guide.pdf)
- [Symantec DLP Detection REST API 2.0 Reference Guide (PDF)](https://techdocs.broadcom.com/content/dam/broadcom/techdocs/symantec-security-software/information-security/data-loss-prevention/generated-pdfs/Symantec_DLP_Detection_REST_API_2_Reference_Guide.pdf)
- [Symantec DLP 15.7 API Documentation Portal](https://apidocs.symantec.com/home/DLP15.7)
- [Broadcom Enterprise Security API Portal](https://apidocs.securitycloud.symantec.com/)
- [Code Samples for the REST API](https://techdocs.broadcom.com/us/en/symantec-security-software/information-security/data-loss-prevention/16-0/dlp-apis/Enforce-Server-REST-API-examples.html)
- [SOAP Incident Reporting and Update API Developers Guide (15.5)](https://techdocs.broadcom.com/content/dam/broadcom/techdocs/symantec-security-software/information-security/data-loss-prevention/generated-pdfs/Symantec_DLP_15.5_Incident_Reporting_Update_API_Developers_Guide.pdf)
- [KB215336 -- REST API Query Samples](https://knowledge.broadcom.com/external/article/215336/incident-reporting-and-update-restful-ap.html)
- [KB250998 -- Sender/Recipient Pattern API Examples](https://knowledge.broadcom.com/external/article/250998/symantec-dlp-core-api-reusable-senderre.html)
- [CloudSOC Cloud DLP APIs](https://techdocs.broadcom.com/us/en/symantec-security-software/information-security/symantec-cloudsoc/cloud/api-home/protect-api/cloud-dlp-apis.html)
- [CloudSOC Policy API](https://techdocs.broadcom.com/us/en/symantec-security-software/information-security/symantec-cloudsoc/cloud/api-home/protect-api.html)
- [Symantec DLP 16 Blog -- 6 New APIs](https://symantec-enterprise-blogs.security.com/blogs/product-insights/symantec-dlp-16-helping-achieve-your-cybersecurity-goals)
- [The Game Changer -- Incident Reporting in DLP 16.0](https://symantec-enterprise-blogs.security.com/blogs/product-insights/game-changer-incident-reporting-dlp)
- [DLP Features Delivered -- 16.0 RU2 APIs](https://www.security.com/product-insights/dlp-features-you-requested-delivered)
- [DLP 25.1 What's New](https://techdocs.broadcom.com/us/en/symantec-security-software/information-security/data-loss-prevention/25-1/new-and-changed/what-s-new-in-data-loss-prevention.html)
- [DLP 26.1 What's New](https://techdocs.broadcom.com/us/en/symantec-security-software/information-security/data-loss-prevention/26-1/new-and-changed/what-s-new-in-data-loss-prevention.html)
- [Enforce Server Features in DLP 26.1](https://techdocs.broadcom.com/us/en/symantec-security-software/information-security/data-loss-prevention/26-1/new-and-changed/what-s-new-in-data-loss-prevention/enforce-features-in-dlp-26-1.html)
- [Cortex XSOAR Symantec DLP v2 Integration](https://xsoar.pan.dev/docs/reference/integrations/symantec-data-loss-prevention-v2)
- [FortiSOAR Symantec DLP v2.2.0 Connector](https://docs.fortinet.com/document/fortisoar/2.2.0/symantec-dlp/159/symantec-dlp-v2-2-0)
- [Swimlane Symantec DLP Connector](https://docs.swimlane.com/connectors/symantec-dlp)
- [ServiceNow DLP Incident Response Integration](https://docs.servicenow.com/bundle/xanadu-security-management/page/product/dlp-symantec/concept/symantec-dlp-integration.html)
- [GitHub: symc-dlp-cloud-connector (Official)](https://github.com/Symantec/symc-dlp-cloud-connector)
- [GitHub: symantec_dlp_client (Community SOAP)](https://github.com/Ryan-Gordon/symantec_dlp_client)
- [GitHub: indexSymantecDLPMatches (Community REST)](https://github.com/dlparchitect/indexSymantecDLPMatches)
- [GitHub: DLPIncidentSLABreach](https://github.com/dlparchitect/DLPIncidentSLABreach)
- [GitHub: safeprompt -- Detection API 2.0 for LLM Safety](https://github.com/dlparchitect/safeprompt)
- [GitHub: symantec-dlp-accelerators](https://github.com/Protirus/symantec-dlp-accelerators)
- [Syslog CEF Configuration for DLP](https://knowledge.broadcom.com/external/article/256282/how-to-configure-log-to-a-syslog-server.html)
- [Generating Syslog Messages from DLP](https://knowledge.broadcom.com/external/article/159509/generating-syslog-messages-from-data-los.html)
- [Splunk Add-on for Symantec DLP](https://docs.splunk.com/Documentation/AddOns/released/SymantecDLP/Setup)
- [DLP PowerShell Blog -- Alex Hedley](https://alexhedley.com/symantec-connect-articles/posts/dlp-api-powershell)
- [Broadcom Community -- DLP API PowerShell](https://community.broadcom.com/symantecenterprise/viewdocument/dlp-api-powershell?CommunityKey=65cf8c43-bb97-4e96-ae0b-0db8ba1b4d07)
