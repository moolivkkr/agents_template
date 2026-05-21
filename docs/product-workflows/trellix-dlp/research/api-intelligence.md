# API Intelligence: Trellix DLP -- Policy Authoring

> Researched: 2026-05-21 | API surfaces: 4 | Documented endpoints: 18+
> Confidence: HIGH (corroborated across official docs, KB articles, community forums, GitHub repos)

---

## Executive Summary

Trellix DLP exposes a **narrow but functional** REST API for policy operations, primarily through the ePO (ePolicy Orchestrator) on-prem server and a separate DLP SaaS API. The API surface is heavily skewed toward **incident retrieval and definition import** -- the core policy authoring operations (creating classifications, rules, rule sets) are **console-only with no API coverage**. This represents the single largest automation gap in the product.

**Key finding:** Classification and rule creation CANNOT be done via API. Trellix confirmed this in community forums (2019-2020) and the limitation persists as of current documentation (11.11.x). Only definition import (email lists, URL lists) and policy application/deployment have API support.

---

## API Surfaces Discovered

| # | Type | Base URL Pattern | Auth Model | Docs Quality | Version | Status |
|---|------|-----------------|------------|-------------|---------|--------|
| 1 | REST (ePO On-Prem) | `https://<ePO-server>:8443/remote/<command>` | ePO username/password (HTTP Basic over TLS) | GOOD -- scripting reference guide available | ePO 5.10.x+ | Active |
| 2 | REST (DLP Server) | `https://<DLP-server>/rest/dlp/...` | ePO credentials (same auth) | MODERATE -- scattered across product guide | DLP 11.10.x / 11.11.x | Active |
| 3 | REST (DLP SaaS) | `https://api.manage.trellix.com/dlp/...` | OAuth2 access token (client credentials) | MODERATE -- SaaS product guide | DLP SaaS | Active |
| 4 | OpenDXL (Message Bus) | DXL fabric topics (not HTTP) | Certificate-based mutual TLS | GOOD -- GitHub repos with examples | OpenDXL 5.x+ | Active |

### Notes on Surfaces

- **ePO Web API (#1)** is the primary automation interface. Commands are extension-driven -- DLP installs `dlp.*` commands into ePO.
- **DLP REST API (#2)** runs on the DLP server itself (not ePO). Handles evidence retrieval, incident queries, definition import, and policy application.
- **DLP SaaS API (#3)** is for cloud-managed DLP. Different auth model (OAuth2 via Trellix Developer Portal). Primarily incident/event focused.
- **OpenDXL (#4)** is a message-bus layer that wraps ePO remote commands. Adds pub/sub event capabilities but same underlying command set.

---

## Authentication Models

### ePO On-Prem Web API + DLP REST API
```
Method: HTTP Basic Authentication over TLS
Credentials: ePO administrator username + password
Header: Authorization: Basic <base64(username:password)>
Port: 8443 (ePO default)
TLS: Required (self-signed cert common)
Session: Stateless (credentials per request)
```

### DLP SaaS API (Cloud)
```
Method: OAuth2 Client Credentials
Token endpoint: POST to Trellix IAM service
Grant type: client_credentials
Client ID/Secret: Generated from Trellix Developer Portal
  (https://developer.manage.trellix.com)
Token TTL: 300 seconds (use within 280s recommended)
Header: Authorization: Bearer <access_token>
```

### OpenDXL
```
Method: Mutual TLS with X.509 certificates
Certificates: Provisioned via ePO DXL broker
Transport: DXL fabric (MQTT-based, not HTTP)
Libraries: Python (opendxl-client), JavaScript (opendxl-client-javascript)
```

---

## Endpoint Inventory

### A. ePO Web API -- DLP Commands (via ePO server :8443)

Commands are invoked as: `https://<epo>:8443/remote/<command>?<params>&:output=json`

| # | Command | Method | Description | Maps To (Policy Layer) |
|---|---------|--------|-------------|----------------------|
| 1 | `dlp.applyPolicies` | GET/POST | Apply (deploy) DLP policy to managed endpoints | Policy deployment |
| 2 | `dlp.importDefinitions` | POST | Import definition data (email lists, URL lists) into DLP | Definitions |
| 3 | `dlp.createBackup` | GET/POST | Create a backup of the current DLP policy configuration | Policy backup |
| 4 | `policy.find` | GET | Search for policies by product ID or name (`searchText=<name>`) | Policy lookup |
| 5 | `policy.assignToGroup` | POST | Assign a policy to a System Tree group | Policy assignment |
| 6 | `policy.getAssignments` | GET | View groups/systems where a policy is assigned | Policy assignment query |
| 7 | `system.find` | GET | Find managed systems by criteria | Endpoint targeting |
| 8 | `system.applyTag` | POST | Tag systems (useful for policy assignment rules) | Endpoint grouping |
| 9 | `core.help` | GET | List all available API commands (self-discovery) | Meta/discovery |
| 10 | `core.help?command=<cmd>` | GET | Get help for a specific command | Meta/discovery |
| 11 | `core.executeQuery` | GET | Run a saved ePO query (can query DLP incidents) | Reporting |

**Discovery mechanism:** Hit `https://<epo>:8443/remote/core.help` to enumerate all available commands. DLP extension adds `dlp.*` commands. Available commands vary by installed extensions.

### B. DLP Server REST API (via DLP server, direct)

| # | Method | Path | Description | Maps To |
|---|--------|------|-------------|---------|
| 12 | POST | `/rest/dlp/event/evidence/get` | Retrieve and decrypt referenced DLP evidence file | Incident evidence |
| 13 | GET | `/rest/dlp/event/incidents` | Get incident IDs for data-in-use or data-in-motion events | Incident query |
| 14 | GET | `/rest/dlp/event/incident/{id}` | Get details for a specific incident | Incident details |
| 15 | POST | `/rest/dlp/definitions/import` | Import email/URL definitions (alternative to ePO command) | Definitions |
| 16 | POST | `/rest/dlp/policy/apply` | Apply DLP policy after changes | Policy deployment |
| 17 | POST | `/rest/dlp/policy/backup` | Create policy backup | Policy backup |
| 18 | GET | `/rest/dlp/discover/item` | Get DLP Discover scan item details | Discovery results |

### C. DLP SaaS API (Cloud-managed)

| # | Method | Path | Description | Maps To |
|---|--------|------|-------------|---------|
| 19 | POST | `/iam/v1.1/token` | Get OAuth2 access token | Authentication |
| 20 | GET | `/dlp/v1/incidents` | Get DLP SaaS incidents list | Incident query |
| 21 | GET | `/dlp/v1/incidents/{id}` | Get details of a specific incident | Incident details |
| 22 | POST | `/dlp/v1/events` | Retrieve events of type incidents | Event query |
| 23 | POST | `/dlp/v1/network/analyze` | Monitor and analyze network traffic (DLP Prevent SaaS) | Network DLP |

### D. DLP REST API -- Cloud Gateway Integration

| # | Method | Path | Description | Maps To |
|---|--------|------|-------------|---------|
| 24 | POST | `/dlp/v1/classify` | Send content to DLP engine for classification (cloud gateways) | Content inspection |
| 25 | POST | `/dlp/v1/scan` | Scan content against DLP policies | Content inspection |

---

## API-to-UI Coverage Matrix

This is the critical mapping. For each policy authoring operation in the UI, does an API equivalent exist?

### Definitions Layer

| # | Operation | UI Screen | API Endpoint | Coverage | Impact |
|---|-----------|-----------|-------------|----------|--------|
| 1 | Create regex/advanced pattern definition | Classification > Definitions > Advanced Patterns | None | **GAP** | HIGH -- Cannot programmatically create regex definitions |
| 2 | Create dictionary definition | Classification > Definitions > Dictionaries | None | **GAP** | HIGH -- Cannot create keyword dictionaries via API |
| 3 | Import email address list | DLP Policy Manager > Definitions > Email Addresses | `dlp.importDefinitions` / `/rest/dlp/definitions/import` | **FULL** | Email lists can be bulk-imported |
| 4 | Import URL list | DLP Policy Manager > Definitions > URL Lists | `dlp.importDefinitions` / `/rest/dlp/definitions/import` | **FULL** | URL lists can be bulk-imported |
| 5 | Create network share definition | DLP Policy Manager > Definitions > Network Share | None | **GAP** | MEDIUM -- Manual only |
| 6 | Create application definition | DLP Policy Manager > Definitions > Applications | None | **GAP** | MEDIUM -- Manual only |
| 7 | Create document fingerprint | Classification > Register Documents | None | **GAP** | HIGH -- Fingerprinting is console-only |
| 8 | Import user groups (LDAP/CSV) | DLP Policy Manager > Definitions > Source/Destination > End-User Groups | `dlp.importDefinitions` (CSV format) | **PARTIAL** | Can import user lists via CSV; LDAP sync is console-configured |

### Classifications Layer

| # | Operation | UI Screen | API Endpoint | Coverage | Impact |
|---|-----------|-----------|-------------|----------|--------|
| 9 | Create classification | Classification > New Classification | None | **GAP** | **CRITICAL** -- Core authoring operation has zero API support |
| 10 | Edit classification criteria | Classification > Edit > Criteria | None | **GAP** | **CRITICAL** -- Cannot modify classification logic via API |
| 11 | Add definition to classification | Classification > Edit > Add Component | None | **GAP** | **CRITICAL** -- Cannot compose classifications programmatically |
| 12 | Delete classification | Classification > Delete | None | **GAP** | MEDIUM |
| 13 | Export/import classifications | Classification > Export/Import | UI-only (XML export, manual import) | **GAP** | HIGH -- Export is UI action, no API |

### Rules Layer

| # | Operation | UI Screen | API Endpoint | Coverage | Impact |
|---|-----------|-----------|-------------|----------|--------|
| 14 | Create data protection rule | DLP Policy Manager > Rule Sets > Add Rule | None | **GAP** | **CRITICAL** -- Cannot create rules via API |
| 15 | Edit rule conditions/reactions | DLP Policy Manager > Rule Sets > Edit Rule | None | **GAP** | **CRITICAL** -- Cannot modify rule logic via API |
| 16 | Enable/disable rule | DLP Policy Manager > Rule Sets > Enable/Disable | None | **GAP** | HIGH -- Cannot toggle rules programmatically |
| 17 | Delete rule | DLP Policy Manager > Rule Sets > Delete | None | **GAP** | MEDIUM |

### Rule Sets Layer

| # | Operation | UI Screen | API Endpoint | Coverage | Impact |
|---|-----------|-----------|-------------|----------|--------|
| 18 | Create rule set | DLP Policy Manager > Rule Sets > New Rule Set | None | **GAP** | **CRITICAL** -- Cannot create rule sets via API |
| 19 | Edit rule set | DLP Policy Manager > Rule Sets > Edit | None | **GAP** | **CRITICAL** |
| 20 | Delete rule set | DLP Policy Manager > Rule Sets > Delete | None | **GAP** | MEDIUM |

### Policy Assignment & Deployment Layer

| # | Operation | UI Screen | API Endpoint | Coverage | Impact |
|---|-----------|-----------|-------------|----------|--------|
| 21 | Assign rule set to policy | Policy Catalog > DLP Policy > Rule Set Assignment | None (direct) | **GAP** | HIGH -- Rule set binding is console-only |
| 22 | Find/list policies | Policy Catalog > search | `policy.find` | **FULL** | Can enumerate policies |
| 23 | Assign policy to group | System Tree > Group > Assign Policy | `policy.assignToGroup` | **FULL** | Can assign existing policies to groups |
| 24 | View policy assignments | System Tree > View Assignments | `policy.getAssignments` | **FULL** | Can query current assignments |
| 25 | Deploy policy to endpoints | System Tree > Agent Wake-Up / Policy Apply | `dlp.applyPolicies` | **FULL** | Can trigger policy push to endpoints |
| 26 | Create policy backup | DLP Settings > Backup | `dlp.createBackup` / `/rest/dlp/policy/backup` | **FULL** | Automated backup supported |

### Incident & Evidence Layer (Read-Only)

| # | Operation | UI Screen | API Endpoint | Coverage | Impact |
|---|-----------|-----------|-------------|----------|--------|
| 27 | Query incidents | DLP Incident Manager | `/rest/dlp/event/incidents` | **FULL** | Full incident query |
| 28 | Get incident details | DLP Incident Manager > Detail | `/rest/dlp/event/incident/{id}` | **FULL** | Full detail retrieval |
| 29 | Retrieve evidence | DLP Incident Manager > Evidence | `/rest/dlp/event/evidence/get` | **FULL** | Evidence file retrieval with decryption |
| 30 | Run DLP queries | Queries & Reports | `core.executeQuery` | **FULL** | Can run saved queries |

---

## API Gaps -- Console-Only Operations (Sorted by Impact)

| # | Operation | Impact | Workaround | Notes |
|---|-----------|--------|-----------|-------|
| 1 | Create/edit classification | **CRITICAL** | Manual via ePO console only | Trellix confirmed: "classification cannot be created outside the ePO console" |
| 2 | Create/edit data protection rules | **CRITICAL** | Manual via ePO console only | No API for rule CRUD |
| 3 | Create/edit rule sets | **CRITICAL** | Manual via ePO console only | No API for rule set CRUD |
| 4 | Assign rule sets to policies | **HIGH** | Manual via Policy Catalog | Binding rules to policies is console-only |
| 5 | Create regex/pattern definitions | **HIGH** | Manual via ePO console only | Advanced patterns cannot be API-created |
| 6 | Create dictionary definitions | **HIGH** | Manual via ePO console only | Keyword dictionaries are console-only |
| 7 | Register document fingerprints | **HIGH** | Manual via ePO console only | Exact data matching requires console |
| 8 | Export/import classifications | **HIGH** | XML export via UI, manual re-import | No programmatic export/import |
| 9 | Enable/disable individual rules | **HIGH** | Manual toggle in console | Cannot automate rule activation |
| 10 | Create network/application definitions | **MEDIUM** | Manual via ePO console | Less frequently automated |
| 11 | Configure DLP Discover scans | **MEDIUM** | Manual via ePO console | Scan configuration is console-only |
| 12 | Manage operational events settings | **LOW** | Manual via ePO console | Infrequently changed |

**Summary: 12 of ~30 operations have API gaps. The entire "author a policy from scratch" workflow (define > classify > create rules > build rule sets > assign) is blocked at every step except the final deployment.**

---

## Integration Capabilities

### ePO Web Services (Policy Distribution & Management)

| Capability | Status | Details |
|-----------|--------|---------|
| Remote command execution | YES | All ePO commands available via `https://<epo>:8443/remote/<cmd>` |
| Policy deployment automation | YES | `dlp.applyPolicies` triggers push to endpoints |
| System Tree management | YES | `system.find`, `system.applyTag`, group management |
| Query execution | YES | `core.executeQuery` for saved queries |
| Scheduled tasks | YES | `scheduler.listAllTasks`, task management |
| Python scripting | YES | Documented with examples in ePO Web API Scripting Reference Guide |
| cURL examples | YES | Provided in official documentation |

### SIEM Integration

| Capability | Status | Mechanism |
|-----------|--------|-----------|
| Event forwarding | YES | Syslog (CEF/LEEF format) via DLP appliance |
| ePO event forwarding | YES | Registered server > syslog forwarding |
| Splunk integration | YES | `TA-trellix-epo` Splunk Technology Add-on (community, [GitHub](https://github.com/sarat1kyan/TA-trellix-epo)) |
| Elastic integration | PARTIAL | Requested ([GitHub issue #164115](https://github.com/elastic/kibana/issues/164115)) |
| Google Chronicle | YES | Native parser available (`trellix-dlp` parser) |
| Devo SIEM | YES | Native Trellix DLP collector |
| Generic SIEM | YES | CEF over syslog, configurable |

### LDAP/AD Integration

| Capability | Status | Details |
|-----------|--------|---------|
| User group sync | YES | LDAP/AD configured in ePO; syncs user groups for DLP rules |
| End-user group import | YES | CSV import via `dlp.importDefinitions` or UI |
| Automatic group refresh | YES | ePO LDAP sync on schedule |
| User-based policy assignment | YES | ePO supports user-based (not just system-based) policy rules |

### Webhooks/Events

| Capability | Status | Details |
|-----------|--------|---------|
| Native webhooks | NO | Trellix DLP does not expose native webhook endpoints |
| n8n integration | YES | Community connector for ePO ([n8n.io](https://n8n.io/integrations/webhook/and/trellix-epo/)) |
| OpenDXL pub/sub | YES | Real-time event bus; can subscribe to DLP events |
| XDR correlation | YES | DLP events feed into Trellix XDR for cross-product correlation |
| Custom event consumers | PARTIAL | Via OpenDXL subscriptions or syslog parsing |

---

## SDKs and Client Libraries

| Library | Language | Source | Maintainer | DLP-Specific? |
|---------|----------|--------|-----------|---------------|
| opendxl-epo-client-python | Python | [GitHub](https://github.com/opendxl/opendxl-epo-client-python) | Trellix/OpenDXL | No (wraps all ePO commands including dlp.*) |
| opendxl-epo-client-javascript | JavaScript | [GitHub](https://github.com/opendxl/opendxl-epo-client-javascript) | Trellix/OpenDXL | No (wraps all ePO commands) |
| Trellix-API scripts | Python | [GitHub](https://github.com/Trellix-plb/Trellix-API) | Trellix (unofficial) | Partial (general Trellix API scripts) |
| KB87855 samples | C#, Java, PowerShell | [Trellix KB](https://kcm.trellix.com/corporate/index?page=content&id=KB87855) | Trellix | YES -- DLP endpoint definition samples |
| ePO Web API (raw) | Any (HTTP) | cURL / any HTTP client | N/A | Via ePO remote command URL pattern |
| EDR Integration Scripts | Python | [GitHub](https://github.com/trellix-enterprise/EDR-Integration-Scripts) | Trellix | No (EDR-focused, but demonstrates API patterns) |

### No Official DLP SDK

There is **no official Trellix DLP SDK** (Python, Go, or otherwise). All programmatic access goes through:
1. ePO Web API (HTTP commands)
2. DLP REST endpoints (direct HTTP)
3. OpenDXL client libraries (wrapping ePO commands over DXL)

---

## Documentation Quality Assessment

| Resource | Quality | URL | Notes |
|----------|---------|-----|-------|
| DLP 11.11.x Product Guide -- REST API sections | MODERATE | [docs.trellix.com](https://docs.trellix.com/bundle/data-loss-prevention-11.11.x-product-guide/) | Endpoints documented but scattered across chapters |
| DLP SaaS Product Guide -- API sections | MODERATE | [docs.trellix.com](https://docs.trellix.com/bundle/data-loss-prevention-saas-product-guide/) | SaaS incident APIs well-documented |
| ePO Web API Reference Guide | GOOD | [docs.trellix.com](https://docs.trellix.com/bundle/epolicy-orchestrator-web-api-reference-guide/) | Comprehensive for ePO commands |
| ePO On-Prem Web API Scripting Reference | GOOD | [docs.trellix.com](https://docs.trellix.com/bundle/trellix-epolicy-orchestrator-on-prem-web-api-scripting-reference-guide/) | Python examples, cURL examples |
| DLP 11.10.x Interface Reference Guide | GOOD | [Scribd mirror](https://www.scribd.com/document/652778165/trellix-data-loss-prevention-11-10-x-interface-reference-guide-february-2023-4-11-2023) | UI field reference (useful for gap analysis) |
| KB87855 -- DLP Endpoint definitions sample | GOOD | [Trellix KB](https://kcm.trellix.com/corporate/index?page=content&id=KB87855) | C#, Java, PowerShell samples |
| Trellix Developer Portal | MODERATE | [developer.manage.trellix.com](https://developer.manage.trellix.com/mvision/apis/home) | Cloud/SaaS APIs; requires registration |
| Trellix Community Forums | VALUABLE | [communitym.trellix.com](https://communitym.trellix.com/t5/Data-Loss-Prevention-DLP/REST-APIs-for-DLP-rules/td-p/615043) | Real-world limitations confirmed by staff |

---

## Key Findings

### 1. Massive Policy Authoring Gap (CRITICAL)

The entire policy creation pipeline -- from definitions through classifications to rules and rule sets -- is **console-only**. The API only covers the "last mile" (deploying existing policies to endpoints). This means:
- You cannot build a "DLP-as-code" workflow with Trellix
- Policy authoring cannot be version-controlled or CI/CD'd
- Multi-tenant policy templating requires manual console work per tenant
- Any competing product offering API-first policy authoring has a significant differentiation advantage

### 2. Definition Import Is the Only Authoring API (PARTIAL)

The `dlp.importDefinitions` command can import:
- Email address lists (CSV format)
- URL lists (CSV format)
- End-user groups (CSV format)

But it CANNOT import:
- Regex patterns
- Dictionaries
- Document fingerprints
- Application definitions
- Network share definitions
- Classifications themselves

### 3. Incident/Evidence API Is Comprehensive (STRENGTH)

The read-side API for incidents and evidence is well-developed:
- Query incidents by type (data-in-use, data-in-motion)
- Retrieve incident details
- Decrypt and retrieve evidence files
- Integration with SIEM via syslog/CEF

This is typical of DLP products -- incident response automation is prioritized over policy authoring automation.

### 4. Two Divergent API Surfaces (Complexity)

On-prem (ePO + DLP server) and SaaS have completely different API surfaces:
- On-prem: ePO remote commands + DLP REST API, Basic auth
- SaaS: OAuth2-based REST API via developer portal

There is no unified API. Customers on hybrid deployments must maintain two integration codebases.

### 5. OpenDXL Provides Event Bus but Not New Capabilities

OpenDXL wraps the same ePO commands in a pub/sub model. It does NOT add new DLP-specific capabilities. Its value is:
- Certificate-based auth (better for automation)
- Event-driven architecture (subscribe to DLP events)
- Language-specific client libraries (Python, JavaScript)

### 6. Best Automation Opportunity

The highest-value automation that IS possible today:
1. **Definition import pipeline**: Automate email/URL list updates from threat intelligence feeds
2. **Policy deployment**: Automate `dlp.applyPolicies` after manual policy changes
3. **Incident response**: Automate incident triage/evidence collection via REST API
4. **Compliance reporting**: Automate query execution and report generation

### 7. Competitive Intelligence Implications

For a competing product, the API gaps represent a massive market opportunity:
- API-first policy authoring (definitions, classifications, rules, rule sets)
- Policy-as-code with version control integration
- Programmatic classification management
- Full CRUD on all policy objects
- OpenAPI/Swagger specification (Trellix has none for DLP)
- Terraform/Pulumi providers for DLP policy management

---

## Sources

- [REST API call to apply DLP Policy (11.11.x)](https://docs.trellix.com/bundle/data-loss-prevention-11.11.x-product-guide/page/UUID-fde8c193-c95f-0f3c-2ccf-926691ea31d8.html)
- [REST API for importing definitions and applying policies (11.1.x)](https://docs.trellix.com/bundle/data-loss-prevention-11.1.x-product-guide/page/GUID-6CEDFC84-DC50-4115-9910-FFADEAEBAC45.html)
- [REST API to create a backup of DLP Policy](https://docs.trellix.com/bundle/data-loss-prevention-11.11.x-product-guide/page/UUID-5b0caedf-efe5-f024-e6d8-416abc6445ef.html)
- [REST API call to get incident IDs](https://docs.trellix.com/bundle/data-loss-prevention-11.11.x-product-guide/page/UUID-fbf85735-9c01-7a2a-e634-9aeaadd1a194.html)
- [REST API call to retrieve and decrypt evidence](https://docs.trellix.com/bundle/data-loss-prevention-11.11.x-product-guide/page/UUID-bd795433-beec-fd9b-0b9f-65ae7cb105c0.html)
- [DLP SaaS Incident APIs](https://docs.trellix.com/bundle/data-loss-prevention-saas-product-guide/page/UUID-6d166a4b-20b7-7f54-1b45-7689484f9b18.html)
- [DLP SaaS access token API](https://docs.trellix.com/bundle/data-loss-prevention-saas-product-guide/page/UUID-ca8abf53-5006-9a8f-02d8-3557978877e5.html)
- [Trellix DLP REST API integration with cloud gateways](https://docs.trellix.com/bundle/data-loss-prevention-saas-product-guide/page/UUID-ce07bdcf-eae9-f133-d1b8-251246c22f13.html)
- [ePO Web API Reference Guide](https://docs.trellix.com/bundle/epolicy-orchestrator-web-api-reference-guide/page/GUID-C2771B41-22E7-443E-8383-707BBA0AD61E.html)
- [ePO On-Prem Web API Scripting Reference Guide](https://docs.trellix.com/bundle/trellix-epolicy-orchestrator-on-prem-web-api-scripting-reference-guide/page/UUID-e47e7325-82d7-f819-7648-93dce9903cdf.html)
- [ePO Web API basics](https://docs.trellix.com/bundle/epolicy-orchestrator-web-api-reference-guide/page/GUID-2503B69D-2BCE-4491-9969-041838B39C1F.html)
- [KB87855 -- REST API for DLP Endpoint definitions sample](https://kcm.trellix.com/corporate/index?page=content&id=KB87855)
- [REST API to import a URL list](https://docs.trellix.com/bundle/data-loss-prevention-11.10.x-product-guide/page/GUID-4D7D0FF6-A9E1-4839-90DC-B4EACAD7995A.html)
- [REST API to import an email address list](https://docs.trellix.com/bundle/data-loss-prevention-11.10.x-product-guide/page/GUID-C026B910-0588-477F-A300-65B0B2974FD5.html)
- [Community: REST APIs for DLP rules](https://communitym.trellix.com/t5/Data-Loss-Prevention-DLP/REST-APIs-for-DLP-rules/td-p/615043)
- [Community: rest API for DLP](https://communitym.trellix.com/t5/Data-Loss-Prevention-DLP/rest-API-for-DLP/td-p/674501)
- [Trellix Developer Portal](https://developer.manage.trellix.com/mvision/apis/home)
- [OpenDXL ePO Client JavaScript](https://github.com/opendxl/opendxl-epo-client-javascript)
- [Trellix-API scripts (GitHub)](https://github.com/Trellix-plb/Trellix-API)
- [Splunk TA for Trellix ePO (GitHub)](https://github.com/sarat1kyan/TA-trellix-epo)
- [REST API to import URL list definitions (KB90846)](https://kcm.trellix.com/corporate/index?page=content&id=KB90846)
- [Import/export DLP Endpoint configuration](https://docs.trellix.com/bundle/data-loss-prevention-11.3.x-product-guide/page/GUID-EF258C27-5717-4863-8215-A6AA29AC0E04.html)
- [Export/import repository definitions](https://docs.trellix.com/bundle/data-loss-prevention-11.3.x-product-guide/page/GUID-EA745BE6-C706-4FCF-9F0E-0957E3FA49D0.html)
- [n8n Webhook + Trellix ePO integration](https://n8n.io/integrations/webhook/and/trellix-epo/)
- [Google Chronicle Trellix DLP parser](https://docs.cloud.google.com/chronicle/docs/ingestion/default-parsers/trellix-dlp)
