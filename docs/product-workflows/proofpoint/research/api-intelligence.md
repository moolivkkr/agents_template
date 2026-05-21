# API Intelligence: Proofpoint Security Suite

> Generated: 2026-05-21 | Research Method: Web search + documentation fetch across 14+ API surfaces
> Covers: Essentials, PPS/PoD, TAP, TRAP, PSAT, ITM, CASB, Isolation, Archive, SER, Tessian, Sigma Platform

---

## 1. API Surfaces Discovered

Proofpoint exposes **12+ distinct API surfaces** across its product suite. Unlike vendors with a single unified API, Proofpoint's API landscape is fragmented across product acquisitions and deployment tiers (Essentials vs. Enterprise/PoD).

| # | API Surface | Base URL | Auth Model | Docs Quality | Swagger/OpenAPI |
|---|------------|----------|------------|-------------|-----------------|
| 1 | **TAP SIEM API** | `https://tap-api-v2.proofpoint.com` | HTTP Basic (principal:secret) | HIGH | Yes (referenced) |
| 2 | **TAP Campaign API** | `https://tap-api-v2.proofpoint.com` | HTTP Basic (principal:secret) | HIGH | Yes (referenced) |
| 3 | **TAP People API** | `https://tap-api-v2.proofpoint.com` | HTTP Basic (principal:secret) | HIGH | Yes (referenced) |
| 4 | **TAP Forensics API** | `https://tap-api-v2.proofpoint.com` | HTTP Basic (principal:secret) | HIGH | Yes (referenced) |
| 5 | **TAP Threats API** | `https://tap-api-v2.proofpoint.com` | HTTP Basic (principal:secret) | HIGH | Yes (referenced) |
| 6 | **TAP URL Decoder API** | `https://tap-api-v2.proofpoint.com` | HTTP Basic (optional) | HIGH | Yes (referenced) |
| 7 | **TAP Reports API** | `https://threatprotection-api.proofpoint.com` | Bearer Token (OAuth) | HIGH | Likely |
| 8 | **Essentials Admin API** | `https://us{1-5}.proofpointessentials.com/api/v1` | X-User/X-Password headers | MEDIUM | Yes (referenced) |
| 9 | **Essentials Threat API** | `https://us-siem.proofpointessentials.com` | HTTP Basic (integration keys) | HIGH | No |
| 10 | **Essentials Stats API** | `https://stack#.spambrella.cloud-protect.net/api/v1` | X-User/X-Password headers | MEDIUM | No |
| 11 | **PoD Threat Protection API** | `https://{cluster}.pphosted.com` | OAuth2 (client_id/client_secret) | LOW (private) | Unknown |
| 12 | **PPS Admin API** | `https://{hostname}.pphosted.com:10000` | Username/Password | MEDIUM | Unknown |
| 13 | **TRAP API** | `https://{trap-host}/api` | API Key | MEDIUM | Unknown |
| 14 | **PSAT Results API** | `https://{region}.results.us.securityeducation.com` | API Key | MEDIUM | No |
| 15 | **ITM On-Prem API** | Console-hosted (port-based) | Session auth (console) | LOW | Yes (portal) |
| 16 | **ITM Cloud API** | `https://{tenant}.analyze.proofpoint.com` | OAuth2 (client_id/client_secret) | LOW | Unknown |
| 17 | **CASB API** | `https://{subdomain}.analyze.proofpoint.com` | Bearer Token (OAuth) | LOW | Unknown |
| 18 | **Isolation Reporting API** | `https://proofpointisolation.com/api/v2` | API Key | LOW | No |
| 19 | **NPRE API** | `https://peoplecentric.proofpoint.com` | Bearer Token (OAuth) | LOW | No |
| 20 | **SER Mail API** | `https://api-docs.ser.proofpoint.com` | API Key | MEDIUM | Yes |
| 21 | **SER Admin API** | `https://admin-api-docs.ser.proofpoint.com` | API Key | MEDIUM | Yes |
| 22 | **Tessian/Core Email Protection API** | `https://{subdomain}.tessian-platform.com` | API Key / Bearer Token | MEDIUM | Yes |
| 23 | **Archive API** | Private (behind auth) | OAuth2 | LOW | Unknown |

---

## 2. Authentication Models

Proofpoint uses **5 different authentication models** across its API surfaces:

| Auth Model | APIs Using It | Details |
|-----------|--------------|---------|
| **HTTP Basic Auth** | TAP (SIEM, Campaign, People, Forensics, Threats, URL Decoder) | Service principal + secret; created in TAP Dashboard > Settings |
| **Header-Based Auth** | Essentials Admin API, Essentials Stats API | `X-User` + `X-Password` headers; Org Admin credentials |
| **OAuth2 Client Credentials** | PoD Threat Protection, ITM Cloud, CASB, Archive, NPRE | `client_id` + `client_secret` -> Bearer token; registered via Dev Portal |
| **Bearer Token (separate flow)** | TAP Reports API | Token obtained from `https://auth.proofpoint.com/v1/token` |
| **API Key** | PSAT, Isolation Reporting, TRAP, SER | Static key provisioned per tenant; region-specific |

**Key observation**: There is NO unified authentication. Each product line requires separate credentials, and some (PoD) require filing a support ticket to obtain API access roles.

---

## 3. Endpoint Inventory by Capability

### 3.1 TAP SIEM API (Threat Telemetry)

| Method | Endpoint | Description |
|--------|---------|-------------|
| GET | `/v2/siem/clicks/blocked` | Blocked malicious URL clicks |
| GET | `/v2/siem/clicks/permitted` | Permitted malicious URL clicks |
| GET | `/v2/siem/messages/blocked` | Blocked messages with threats |
| GET | `/v2/siem/messages/delivered` | Delivered messages with threats |
| GET | `/v2/siem/issues` | Combined: permitted clicks + delivered threat messages |
| GET | `/v2/siem/all` | All clicks and messages with threats |

**Parameters**: `interval` (ISO8601), `sinceSeconds`, `sinceTime`, `format` (json/syslog), `threatType` (url/attachment/messageText), `threatStatus` (active/cleared/falsePositive)
**Rate limit**: 1800 requests/24h per endpoint

### 3.2 TAP Campaign API

| Method | Endpoint | Description |
|--------|---------|-------------|
| GET | `/v2/campaign/ids` | List campaign IDs in time window |
| GET | `/v2/campaign/{campaignId}` | Campaign details (actors, malware, techniques) |

**Rate limit**: 50 requests/24h for `/ids`; unlimited for `/{campaignId}`

### 3.3 TAP People API

| Method | Endpoint | Description |
|--------|---------|-------------|
| GET | `/v2/people/vap` | Very Attacked People (attack index breakdown) |
| GET | `/v2/people/top-clickers` | Top URL clickers for training prioritization |

**Parameters**: `window` (14/30/90 days), `size`, `page`
**Rate limit**: 50 requests/24h

### 3.4 TAP Forensics API

| Method | Endpoint | Description |
|--------|---------|-------------|
| GET | `/v2/forensics?threatId={id}` | Forensics evidence for a threat |
| GET | `/v2/forensics?campaignId={id}` | Forensics evidence for a campaign |

**Rate limit**: 50/24h per threatId; 1800/24h for campaignId

### 3.5 TAP Threats API

| Method | Endpoint | Description |
|--------|---------|-------------|
| GET | `/v2/threat/summary/{threatId}` | Detailed threat attributes (severity, actors, malware, techniques) |

**Rate limit**: None currently applied

### 3.6 TAP URL Decoder API

| Method | Endpoint | Description |
|--------|---------|-------------|
| POST | `/v2/url/decode` | Decode TAP-rewritten URLs back to originals |

**Request**: `{"urls": ["encoded_url_1", ...]}` | **Rate limit**: 1800/24h

### 3.7 TAP Reports API (50 endpoints)

Base: `https://threatprotection-api.proofpoint.com/api/v1/dash/reports`
Auth: Bearer Token from `https://auth.proofpoint.com/v1/token`

#### Executive Summary (8 endpoints)
| Endpoint | Description |
|---------|-------------|
| `/executive-summary/inbound-Email-protection-Breakdown` | Inbound protection category breakdown |
| `/executive-summary/Inbound-Protection-Overview` | Pre/post-delivery protection metrics |
| `/executive-summary/advanced-threat-detection-messages-protected` | ATD protection stats by type/category |
| `/executive-summary/threat-categories` | Threat category distribution |
| `/executive-summary/threat-landscape-effectiveness` | Protection effectiveness metrics |
| `/executive-summary/very-attacked-people` | Top VAPs summary |
| `/executive-summary/industry-comparison` | Organization vs. industry benchmarks |
| `/executive-summary/top-clickers` | Top clicker summary with VIP flags |

#### Effectiveness Reports (6 endpoints)
| Endpoint | Description |
|---------|-------------|
| `/effectiveness-reports/messages-protected` | Messages protected by breakdown |
| `/effectiveness-reports/messages-protected-trend` | Protection trends over time |
| `/effectiveness-reports/threat-response-quarantines` | Quarantine statistics |
| `/effectiveness-reports/clicks-protected` | Click protection metrics |
| `/effectiveness-reports/url-rewritten-summary` | URL rewrite coverage |
| `/effectiveness-reports/custom-blocklist-activity` | Custom blocklist effectiveness |

#### Landscape Reports (17 endpoints)
| Endpoint | Description |
|---------|-------------|
| `/landscape-reports/threat-categories` | Threat category volumes |
| `/landscape-reports/landscape-trend` | Threat landscape trends |
| `/landscape-reports/top-ten-techniques` | Top 10 attack techniques |
| `/landscape-reports/top-ten-malware` | Top 10 malware families |
| `/landscape-reports/top-ten-actors` | Top 10 threat actors |
| `/landscape-reports/top-ten-families` | Top 10 threat families |
| `/landscape-reports/top-ten-root-domains-for-url-attacks` | Top URL attack root domains |
| `/landscape-reports/top-ten-subdomains-for-url-attacks` | Top URL attack subdomains |
| `/landscape-reports/top-ten-domains-sending-threats` | Top threat-sending domains |
| `/landscape-reports/top-ten-campaigns` | Top 10 threat campaigns |
| `/landscape-reports/overview-headline` | Landscape overview summary |
| `/landscape-reports/top-threat-objectives` | Top threat objectives |
| `/landscape-reports/top-bec-themes` | Top BEC attack themes |
| `/landscape-reports/vertically-targeted-activity` | Vertical targeting patterns |
| `/landscape-reports/threat-types-by-message-volume` | Threat type volume distribution |
| `/landscape-reports/threat-campaigns-vs-individual-threats` | Campaign vs. individual comparison |
| `/landscape-reports/spread-and-targeting` | Threat spread patterns |

#### People Reports (6 endpoints)
| Endpoint | Description |
|---------|-------------|
| `/people-reports/top-ten-recipients` | Most targeted recipients |
| `/people-reports/top-ten-clickers` | Top URL clickers |
| `/people-reports/top-ten-isolated-clickers` | Top isolated clickers |
| `/people-Reports/very-attacked-people/list` | Full VAP list |
| `/people-Reports/very-attacked-people/summary` | VAP summary statistics |
| `/people-Reports/vip-activity` | VIP targeting activity |

#### Organization Reports (2 endpoints)
| Endpoint | Description |
|---------|-------------|
| `/organization-reports/historical-attack-index-trending` | Attack index trends |
| `/organization-reports/industry-comparison` | Industry comparison trends |

#### BEC Reports (6 endpoints)
| Endpoint | Description |
|---------|-------------|
| `/Bec-Reports/Top-Bec-Themes` | Top BEC themes |
| `/Bec-Reports/Bec-Themes-Trend` | BEC trend over time |
| `/Bec-Reports/Vips-Targeted-By-Bec-Threats` | VIPs targeted by BEC |
| `/Bec-Reports/People-Targeted-By-Bec-Threats` | People targeted by BEC |
| `/Bec-Reports/Messages-Protected` | BEC messages protected |
| `/Bec-Reports/Bec-Messages-Protected-Trend` | BEC protection trends |

#### Threat Objectives Reports (3 endpoints)
| Endpoint | Description |
|---------|-------------|
| `/Threat-Objectives-Reports/Industry-Comparison` | Objectives industry comparison |
| `/Threat-Objectives-Reports/Messages-Protected` | Messages protected by objective |
| `/Threat-Objectives-Reports/Threat-Objectives-Trend` | Objectives trend |

#### Actor Reports (1 endpoint)
| Endpoint | Description |
|---------|-------------|
| `/Actor-Reports/Actors` | Actor list with threat metrics |

#### Utility (1 endpoint)
| Endpoint | Description |
|---------|-------------|
| `/industries` | Available industry verticals for comparison |

**Rate limit**: 10 requests/min per API key; 20 requests/day per report section

### 3.8 Proofpoint Essentials Admin API

Base: `https://us{1-5}.proofpointessentials.com/api/v1`

| Method | Endpoint | Description |
|--------|---------|-------------|
| GET | `/orgs/{domain}` | Retrieve organization |
| PATCH | `/orgs/{domain}` | Update organization (is_active) |
| DELETE | `/orgs/{domain}` | Remove organization |
| GET | `/orgs/{domain}/orgs` | List child organizations |
| POST | `/orgs/{domain}/orgs` | Create child organizations |
| GET | `/orgs/{domain}/domains` | List domains |
| POST | `/orgs/{domain}/domains` | Create domains |
| GET | `/orgs/{domain}/domains/{domain}` | Get specific domain |
| PATCH | `/orgs/{domain}/domains/{domain}` | Update domain |
| DELETE | `/orgs/{domain}/domains/{domain}` | Remove domain |
| GET | `/orgs/{domain}/users` | List users |
| POST | `/orgs/{domain}/users` | Create users |
| GET | `/orgs/{domain}/users/{email}` | Get specific user |
| PUT | `/orgs/{domain}/users/{email}` | Update user |
| DELETE | `/orgs/{domain}/users/{email}` | Remove user |
| GET | `/orgs/{domain}/features` | Get available features |
| PUT | `/orgs/{domain}/features` | Update features (URL Defense, Encryption, etc.) |
| GET | `/orgs/{domain}/licensing` | Get licensing info |
| PUT | `/orgs/{domain}/licensing` | Update licensing |
| PUT | `/orgs/{domain}/package` | Update package type |
| GET | `/endpoints/{domain}` | List available stack endpoints |
| POST | `/token` | Generate auth token |
| GET | `/reporting/{domain}` | Email flow reports |

**Additional Essentials endpoints** (confirmed via documentation but exact paths behind auth wall):
- Filter management (create/edit/delete inbound/outbound filters)
- Safe/Blocked sender list CRUD
- Quarantine access and operations
- Emergency Inbox (continuity) access
- Spam settings configuration

### 3.9 Essentials Threat API (SIEM)

Base: `https://us-siem.proofpointessentials.com` or `https://eu-siem.proofpointessentials.com`

Mirrors the TAP SIEM API structure with identical endpoints:
- `/v2/siem/clicks/blocked`, `/v2/siem/clicks/permitted`
- `/v2/siem/messages/blocked`, `/v2/siem/messages/delivered`
- `/v2/siem/issues`, `/v2/siem/all`

Additional parameters: `customerData`, `ownData` (for partner multi-tenant visibility)

### 3.10 Essentials Statistics API

Base: `https://stack#.spambrella.cloud-protect.net/api/v1`

| Method | Endpoint | Description |
|--------|---------|-------------|
| GET | `/stats/{domain}/partner` | Single domain statistics |
| GET | `/stats/{domain}/partner/orgs` | Domain + child org statistics |

**Response metrics** (1d, 7d, 30d, 90d): `active_users`, `ib_total`, `ob_total`, `ib_blocked`, `ob_blocked`, `ib_spam`, `ib_virus`, `ib_mal_att`, `ib_imposter`, `ib_phish`, `ob_enc`

### 3.11 PoD Threat Protection API (Enterprise)

Base: `https://{cluster}.pphosted.com` | Auth: OAuth2

| Operation | Description |
|----------|-------------|
| Get Blocklist | Retrieve all org blocklist entries |
| List Blocklist (paginated) | Paginated blocklist retrieval |
| Add to Blocklist | Add entry (attribute, operator, value, comment) |
| Delete from Blocklist | Remove entry |
| Get Safelist | Retrieve all org safelist entries |
| List Safelist (paginated) | Paginated safelist retrieval |
| Add to Safelist | Add entry (attribute, operator, value, comment) |
| Delete from Safelist | Remove entry |

**Supported attributes**: `$from`, `$hfrom`, `$ip`, `$host`, `$helo`, `$rcpt`
**Supported operators**: `equal`, `not_equal`, `contain`, `not_contain`

**CRITICAL LIMITATION**: This API ONLY covers blocklist/safelist management. Policy routes, email firewall rules, module configuration, and all other PPS/PoD settings are NOT exposed via API.

### 3.12 PPS Admin API (On-Prem / Legacy)

Base: `https://{hostname}.pphosted.com:10000` | Port: 10000

| Operation | Description |
|----------|-------------|
| Smart Search | Trace/analyze filtered messages (sender, recipient, subject, action, virus, etc.) |
| Quarantine Message List | Search quarantined messages by folder, sender, recipient, time range |
| Quarantine Message Release | Release without further scanning |
| Quarantine Message Resubmit | Resubmit to filtering modules |
| Quarantine Message Forward | Forward to another recipient |
| Quarantine Message Move | Move to target folder |
| Quarantine Message Delete | Delete from quarantine |
| Quarantine Message Download | Download raw message data |
| Get User | Retrieve user resource |
| Create User | Create new user profile |
| Modify User | Update user fields/attributes |
| Delete User | Remove user profile |

### 3.13 TRAP (Threat Response Auto-Pull) API

| Operation | Description |
|----------|-------------|
| List Incidents | Retrieve incident metadata (filtered by state, dates) |
| Get Incident | Detailed incident by ID |
| Update Incident Comment | Add comments/notes |
| Add User to Incident | Assign user as target/attacker |
| Close Incident | Close with notes |
| Ingest Alert | Ingest JSON alerts (attacker info, classifications, email metadata) |
| Verify Quarantine | Verify email quarantine status |
| Get List | Retrieve list items by ID |
| Add to List | Add IP/URL/domain/hash to list |
| Search Indicator | Search list by filter criteria |
| Delete Indicator | Remove indicator from list |
| Block IP | Add IP to blocklist |
| Block Domain | Add domain to blocklist |
| Block URL | Add URL to blocklist |
| Block Hash | Add file hash to blocklist |

### 3.14 PSAT (Security Awareness Training) Results API

Regional endpoints: US, EU, AP

| Endpoint | Description |
|---------|-------------|
| CyberStrength | CyberStrength assessment results |
| Enrollments | Training enrollment data |
| Phishing | ThreatSim simulated phishing campaign results |
| Phishing Extended | Extended phishing campaign details |
| PhishAlarm | PhishAlarm reporting data |
| Training | Training assignment completion data |
| Users | User roster and status |

All endpoints support pagination (`page_number`, `page_size` up to 1000).

**CRITICAL LIMITATION**: PSAT API is READ-ONLY (reporting/results). There are NO endpoints to create/manage training assignments, phishing campaigns, or campaign configurations via API. All campaign authoring is console-only.

### 3.15 ITM On-Prem (ObserveIT) API

Accessed via integrated API browser in console. Session-authenticated.
Documentation at: `https://docs.preview.observeit.net/portal/index.html`

Key operations (inferred from Python client library):
- Activity Search
- Alert management
- Rule management (import/export)
- User/endpoint management
- Incident management

### 3.16 ITM Cloud API

Auth: OAuth2 (client_id/client_secret from Dev Portal)
- v2 API endpoints
- Activity search
- Alert management
- Webhook integration for SIEM/SOAR alert ingestion
- Endpoint management

### 3.17 CASB API

Auth: Bearer Token (OAuth2)
- Alerts (v1, v2)
- Events
- Metadata Lookup
- Metadata Feed (near real-time activity/alert replication)

### 3.18 Isolation Reporting API

| URL | Description |
|-----|-------------|
| `https://proofpointisolation.com/api/v2/reporting/usage-data` | Browser Isolation usage data |
| `https://urlisolation.com/api/v2/reporting/usage-data` | URL Isolation usage data |

**CRITICAL LIMITATION**: Reporting only. No configuration management API. All isolation policy configuration (redirect rules, VIP assignment, upload/download restrictions) is console-only.

### 3.19 NPRE (Nexus People Risk Explorer) API

Auth: Bearer Token (OAuth2, multi-step)
1. POST to get Bearer Token
2. POST with Bearer Token to get CSV URI
3. GET CSV file

Returns: People risk scores, attack indices, behavioral risk data in CSV format.

### 3.20 SER (Secure Email Relay) APIs

**Mail API** (`https://api-docs.ser.proofpoint.com/`):
- Send email via API (DKIM-signed, spam/virus scanned)
- Attachment support
- Template support

**Admin API** (`https://admin-api-docs.ser.proofpoint.com/`):
- Account management
- Domain management
- Reporting

### 3.21 Tessian/Core Email Protection API

Base: `https://{subdomain}.tessian-platform.com` (EU) or `https://{subdomain}.tessian-app.com` (US)
- Security event data retrieval
- Email quarantine release by event ID
- SOC workflow integration

### 3.22 Archive API

Operations confirmed via documentation:
- Search (full-text, metadata-based)
- Export (PST, EDRM XML)
- Legal Hold (create, manage, release)
- Supervision API (rule creation, review set management)
- LDIF Sync API (directory synchronization)

---

## 4. API <-> UI Coverage Matrix

This maps each of the 14 capability groups from the taxonomy to API coverage.

| # | Capability | UI | API Coverage | API Type | Gap Analysis |
|---|-----------|-----|-------------|----------|-------------|
| 1 | **Email Filtering (Essentials)** | FULL | **PARTIAL** | Essentials Admin API | Filter CRUD confirmed; exact filter condition/action API endpoints behind auth wall. Safe/Blocked sender lists: FULL API. |
| 2 | **PPS/PoD Rules & Email Firewall** | FULL | **GAP** | PoD TP API (blocklist/safelist only) | Policy routes, email firewall rules, quarantine folder mgmt, module precedence, dictionaries, PDR, SMTP rate control: ALL console-only. PoD API only covers blocklist/safelist. |
| 3 | **Spam Policy** | FULL | **PARTIAL** | Essentials Admin API | Essentials: spam threshold via features API. PPS: spam module classifier/tuning is console-only. |
| 4 | **Virus Policy** | FULL | **GAP** | None for policy config | AV bypass list: possibly via Essentials API features. PPS multi-layer AV, zero-hour AV: console-only. No dedicated virus policy API. |
| 5 | **Email DLP** | FULL | **PARTIAL** | Essentials filters + PoD blocklist/safelist | Basic DLP filter creation possible via Essentials filter API. Smart identifiers, PPS DLP rules, Adaptive Email DLP config: console-only. |
| 6 | **Email Encryption** | FULL | **GAP** | None for policy config | TLS enforcement, message expiration/revocation, key management, branding, inbound decryption: ALL console-only. SER API handles relay sending only. |
| 7 | **TAP (Targeted Attack Protection)** | FULL | **EXTRA (read) / GAP (config)** | TAP APIs (all read-only) | TAP has the RICHEST read API (SIEM, Campaigns, People, Forensics, Threats, Reports = 65+ endpoints). But ALL TAP policy configuration (URL Defense, Attachment Defense, per-group enablement, alert config, VIP isolation assignment) is console-only. |
| 8 | **ITM (Insider Threat Management)** | FULL | **PARTIAL** | ITM On-Prem API + ITM Cloud API | Alert rules, prevention rules, import/export: API available. System policies, Windows stealth/privacy, identification services: limited/console-only. |
| 9 | **Endpoint DLP / Data Security** | FULL | **PARTIAL** | ITM/Data Security Cloud API | Detection rules, prevention rules, rule sets, agent policy: API endpoints exist. Data classes/detectors, realm config, GenAI redaction: limited. |
| 10 | **CASB** | FULL | **GAP** | CASB API (alerts/events only) | CASB API provides alert/event retrieval and metadata feed. Cloud app connector setup, DLP rule creation, threat rule creation, IaaS assessment: ALL console-only. |
| 11 | **Isolation** | FULL | **GAP** | Isolation Reporting API only | Reporting API provides usage data only. Console setup, redirect rules, VIP assignment, upload/download restrictions, email isolation config, user input controls: ALL console-only. |
| 12 | **SAT (Security Awareness Training)** | FULL | **PARTIAL (read-only)** | PSAT Results API | Results API provides read access to all campaign/training data (7 endpoints). Campaign CREATION, phishing campaign configuration, follow-up setup: ALL console-only. |
| 13 | **Archive & Retention** | FULL | **PARTIAL** | Archive API | Search, export, legal hold: API confirmed. Retention period configuration, archive search config: limited documentation. |
| 14 | **Quarantine Management** | FULL | **PARTIAL** | PPS Admin API + Essentials API | PPS: full quarantine CRUD (list, release, resubmit, forward, move, delete, download). Essentials: quarantine access. PoD cloud quarantine: limited. Digest configuration: console-only. |

### Coverage Summary

| Coverage Level | Count | Capabilities |
|---------------|-------|-------------|
| **FULL API** | 0 | None - no capability has complete API parity with the UI |
| **EXTRA (read) / GAP (config)** | 1 | TAP (richest read API, zero config API) |
| **PARTIAL** | 8 | Email Filtering, Spam, Email DLP, ITM, Endpoint DLP, SAT (read-only), Archive, Quarantine |
| **GAP** | 5 | PPS/PoD Rules, Virus, Email Encryption, CASB, Isolation |

---

## 5. API Gaps -- Console-Only Operations

These operations can ONLY be performed through the Proofpoint web console and have NO API equivalent.

### CRITICAL GAPS (P0 -- blocking for automation)

| # | Capability | Console-Only Operation | Impact |
|---|-----------|----------------------|--------|
| 1 | PPS/PoD Rules | Policy route configuration | Cannot automate email routing rules |
| 2 | PPS/PoD Rules | Email firewall rule CRUD | Cannot automate core email security rules |
| 3 | PPS/PoD Rules | Rule condition configuration | Cannot set rule conditions programmatically |
| 4 | PPS/PoD Rules | Module precedence configuration | Cannot automate processing order |
| 5 | PPS/PoD Rules | Dictionary management | Cannot manage detection dictionaries via API |
| 6 | TAP | URL Defense enable/config | Cannot enable or configure URL rewriting |
| 7 | TAP | Attachment Defense configuration | Cannot configure sandbox analysis |
| 8 | TAP | Per-group TAP enablement | Cannot enable TAP per group |
| 9 | TAP | TAP alert configuration | Cannot configure alert rules |
| 10 | Email Encryption | Outbound encryption filter creation | Cannot create encryption policies |
| 11 | Email Encryption | TLS enforcement/fallback config | Cannot configure TLS policies |
| 12 | Email Encryption | Key management | Cannot manage encryption keys |
| 13 | Virus | PPS multi-layer AV configuration | Cannot configure AV policies |
| 14 | CASB | Cloud app connector setup | Cannot onboard cloud apps |
| 15 | CASB | CASB DLP rule creation | Cannot create CASB DLP rules |
| 16 | CASB | CASB threat rule creation | Cannot create CASB threat rules |
| 17 | Isolation | Redirect rule creation | Cannot create isolation redirect rules |
| 18 | Isolation | VIP/VAP user assignment | Cannot assign VIP isolation |
| 19 | Isolation | Upload/download restrictions | Cannot configure data restrictions |
| 20 | SAT | Training assignment creation | Cannot create training assignments via API |
| 21 | SAT | Phishing campaign creation | Cannot create phishing simulations via API |

### HIGH-IMPACT GAPS (P1)

| # | Capability | Console-Only Operation | Impact |
|---|-----------|----------------------|--------|
| 22 | PPS/PoD Rules | Quarantine folder management | Cannot manage quarantine folders |
| 23 | PPS/PoD Rules | Recipient verification setup | Cannot configure recipient verification |
| 24 | PPS/PoD Rules | SMTP rate control | Cannot set rate limits |
| 25 | PPS/PoD Rules | End user digest configuration | Cannot configure digest settings |
| 26 | Email DLP | Smart identifier configuration | Cannot manage DLP smart identifiers |
| 27 | Email DLP | PPS email firewall DLP rule | Cannot create DLP rules in PPS |
| 28 | Email DLP | Adaptive Email DLP configuration | Cannot configure adaptive DLP |
| 29 | Email Encryption | Message expiration config | Cannot set expiration policies |
| 30 | Email Encryption | Message revocation | Cannot revoke encrypted messages |
| 31 | Email Encryption | Secure Reader branding | Cannot customize branding |
| 32 | TAP | URL Isolation for VIPs/VAPs | Cannot configure URL isolation targeting |
| 33 | CASB | User/group sync configuration | Cannot configure user sync |
| 34 | CASB | IaaS infrastructure assessment | Cannot run infrastructure assessments |
| 35 | Isolation | Email isolation configuration | Cannot configure email isolation |
| 36 | Archive | Retention period configuration | Limited API coverage |
| 37 | Spam | PPS spam module classifier config | Cannot tune PPS spam classifiers |
| 38 | Spam | PPS spam module tuning | Cannot adjust PPS spam sensitivity |

---

## 6. Integration Capabilities

### 6.1 Webhooks

| Product | Webhook Support | Direction | Destinations |
|---------|----------------|-----------|-------------|
| ITM / Data Security | YES | Outbound | Slack, Teams, Splunk Cloud, Outlook Groups, ServiceNow (generic template) |
| CASB | YES | Outbound (Metadata Feed) | SIEM, custom endpoints |
| TRAP | YES (via adapters) | Bidirectional | Exchange, O365, Gmail, FireEye EX, JSON |
| TAP | NO native webhooks | N/A | Must poll SIEM API |
| Essentials | NO | N/A | Must poll APIs |
| PSAT | NO | N/A | Must poll Results API |

### 6.2 SIEM Integration

| Integration | Method | Products |
|-------------|--------|----------|
| Splunk | TAP SIEM API + Add-on, Isolation Add-on | TAP, Isolation |
| IBM QRadar | TAP SIEM API | TAP |
| HP ArcSight | TAP SIEM API (CEF format via syslog) | TAP |
| Microsoft Sentinel | TAP connector | TAP |
| Elastic | TAP + ITM integrations | TAP, ITM |
| Sumo Logic | TAP cloud-to-cloud source | TAP |
| Rapid7 InsightIDR | TAP source | TAP |
| Secureworks Taegis | TAP integration | TAP |

### 6.3 SOAR Integration

| Platform | Integration | Commands |
|---------|-------------|----------|
| Cortex XSOAR | TAP v2 | 12 commands (events, forensics, campaigns, people, URL decode) |
| Cortex XSOAR | Threat Protection (PoD) | 10 commands (blocklist/safelist CRUD) |
| Cortex XSOAR | PPS v2 | 12 commands (smart search, quarantine CRUD, user mgmt) |
| Cortex XSOAR | Threat Response (TRAP) | 15 commands (incidents, lists, blocking, alerts) |
| Cortex XSOAR | Isolation | Event collector |
| Cortex XSOAR | Email Security | Event collector (PoD logs) |
| Splunk SOAR | Threat Protection | 7 actions (blocklist/safelist) |
| D3 SOAR | Cloud Threat Response | Incident management |
| D3 SOAR | Essentials | Sender list management |
| Blink | Webhook events | Event-triggered automation |

### 6.4 Log Streaming

| Method | Products | Protocol |
|--------|----------|----------|
| WebSocket (WSS) | PoD Log Service | Secure WebSocket |
| Syslog (CEF) | TAP SIEM API | Syslog over TLS |
| REST polling | All TAP APIs, Essentials | HTTPS |
| Metadata Feed | CASB | REST/webhook |

---

## 7. SDKs and Client Libraries

### Official (pfptcommunity)

| Library | Language | API Coverage |
|---------|----------|-------------|
| TAP code snippets | JS, Python, C#, Java, PHP, PowerShell, Google Apps Script, M Code | TAP SIEM/People/Forensics |
| PSAT code snippets | JS, Python, Google Apps Script, M Code | PSAT Results |
| NPRE code snippets | JS, Python, Google Apps Script, M Code | NPRE CSV export |
| SER Mail API | C# | SER email sending |
| psat-api-python | Python (PyPI) | PSAT Results (7 report types) |
| tap-api-python | Python | TAP SIEM |

### Community / Third-Party

| Library | Language | API Coverage | GitHub |
|---------|----------|-------------|--------|
| go-proofpoint | Go | TAP SIEM | greenpau/go-proofpoint |
| proofpoint_itm | Python (PyPI) | ITM Cloud API | drizzo-tech/proofpoint_itm |
| proofpoint_tap | Python (PyPI) | TAP API | drizzo-tech/proofpoint_tap |
| PSProofpoint | PowerShell (Gallery) | Multiple APIs | Midnigh7/PSProofpoint |
| ProofpointTAP | PowerShell | TAP Dashboard | lambdac0de/ProofpointTAP |
| PowerShell-PSAT | PowerShell | PSAT Results | regg00/PowerShell-PSAT |
| Proofpoint.TAP | PowerShell 7 | TAP SIEM/Clickers | bchap1n/Proofpoint.TAP |
| proofpoint_itm SDK | Python | ITM Cloud | yuta519/proofpoint-itm-sdk |
| node-proofpoint-podclient | Node.js | PoD WebSocket logs | lambdac0de |
| async-essentials | Python (async) | Essentials API | symonk |
| ProofpointEssentialsClient | C# | Essentials API | singhkamall |
| Terraform provider | Terraform | Meta Networks | mataneine |

### BI/Reporting Templates

| Tool | APIs Supported |
|------|---------------|
| Excel workbooks | TAP, PSAT, NPRE |
| Power BI dashboards | TAP, NPRE |
| Google Data Studio | TAP |

---

## 8. Key Findings

### 8.1 Architecture: Read-Heavy, Write-Absent

**Proofpoint's API strategy is fundamentally READ-ONLY for security telemetry and ABSENT for policy configuration.**

- **65+ TAP endpoints** provide world-class threat intelligence and reporting data
- **ZERO TAP configuration endpoints** exist -- all policy authoring is console-only
- The Essentials Admin API is the closest to full CRUD, but only for the SMB tier
- Enterprise (PPS/PoD) configuration API covers ONLY blocklist/safelist (2 resources out of 50+)

### 8.2 Fragmentation is the Primary Challenge

- **12+ separate API surfaces** with 5 different auth models
- No unified API gateway or single developer portal
- Different APIs for the same conceptual operation depending on tier (Essentials vs. Enterprise)
- Products from acquisitions (ObserveIT/ITM, Tessian, Meta Networks) retain separate API architectures

### 8.3 Gap Pattern: "Observe Everything, Configure Nothing"

For the 14 capabilities in scope:
- **0 of 14** have FULL API parity with the console
- **5 of 14** have critical configuration gaps (PPS Rules, Virus, Encryption, CASB, Isolation)
- **TAP** has the widest gap: most API endpoints of any capability (65+) but zero configuration
- **SAT** API is explicitly read-only -- campaign creation requires the console

### 8.4 Automation Implications

| Automation Goal | Feasibility | Notes |
|----------------|-------------|-------|
| Threat monitoring/alerting | HIGH | TAP SIEM + Reports APIs are comprehensive |
| People risk assessment | HIGH | People API + NPRE + Reports cover this well |
| Forensic investigation | HIGH | Forensics + Threats + Campaign APIs |
| Blocklist/safelist management | HIGH | Essentials + PoD APIs cover this |
| Quarantine management | MEDIUM | PPS Admin API has full CRUD; PoD cloud quarantine limited |
| Email filter policy authoring | LOW | Only Essentials has some filter API; PPS/PoD is console-only |
| TAP/URL Defense policy config | NONE | Completely console-only |
| Encryption policy management | NONE | Completely console-only |
| CASB policy management | NONE | Completely console-only |
| Isolation policy management | NONE | Completely console-only |
| Training campaign creation | NONE | Completely console-only |

### 8.5 Rate Limiting Considerations

| API | Rate Limit | Impact |
|-----|-----------|--------|
| TAP SIEM | 1800/24h per endpoint | ~1.25 req/min; adequate for polling |
| TAP Campaign IDs | 50/24h | Very restrictive; cache results |
| TAP People | 50/24h | Very restrictive; daily polling only |
| TAP Forensics (threatId) | 50/24h per threatId | Per-threat limit; design for selective queries |
| TAP Reports | 10/min, 20/day per section | Very restrictive for dashboard use |
| Essentials Threat | 1800/24h | Matches TAP SIEM |
| URL Decoder | 1800/24h | Adequate for batch decoding |

### 8.6 Comparison to Competitors

| Dimension | Proofpoint | Typical Competitor (e.g., Mimecast, Microsoft Defender) |
|-----------|-----------|--------------------------------------------------------|
| Threat telemetry API | EXCELLENT (65+ endpoints) | Good |
| Policy configuration API | VERY POOR (blocklist/safelist only for Enterprise) | Moderate to Good |
| Unified authentication | POOR (5 auth models) | Usually 1-2 models |
| API fragmentation | SEVERE (12+ surfaces) | Usually 1-3 surfaces |
| OpenAPI/Swagger specs | PARTIAL (some products) | Usually comprehensive |
| SDK support | MODERATE (community + official snippets) | Usually official SDKs |

---

## 9. Recommendations for Automation Strategy

1. **TAP telemetry is the strong foundation** -- build monitoring, alerting, and reporting automation on the TAP SIEM + Reports APIs first
2. **Accept console-only for policy authoring** -- for TAP config, Encryption, CASB, Isolation, and SAT campaign creation, plan for manual console workflows or browser automation as last resort
3. **Use TRAP for response automation** -- TRAP API provides the best write-capable surface for incident response (blocking IPs/domains/URLs/hashes, managing incidents)
4. **Invest in Essentials API for SMB tier** -- if targeting Essentials customers, the Admin API provides the broadest CRUD coverage
5. **PPS Admin API for quarantine automation** -- leverage the quarantine CRUD operations for email remediation workflows
6. **Watch for Sigma Platform API evolution** -- Proofpoint is converging products onto the Sigma Platform; future unified API may emerge

---

## Sources

- [TAP API Documentation Hub](https://help.proofpoint.com/Threat_Insight_Dashboard/API_Documentation)
- [TAP SIEM API](https://help.proofpoint.com/Threat_Insight_Dashboard/API_Documentation/SIEM_API)
- [TAP Campaign API](https://help.proofpoint.com/Threat_Insight_Dashboard/API_Documentation/Campaign_API)
- [TAP People API](https://help.proofpoint.com/Threat_Insight_Dashboard/API_Documentation/People_API)
- [TAP Forensics API](https://help.proofpoint.com/Threat_Insight_Dashboard/API_Documentation/Forensics_API)
- [TAP Threats API](https://help.proofpoint.com/Threat_Insight_Dashboard/API_Documentation/Threat_API)
- [TAP URL Decoder API](https://help.proofpoint.com/Threat_Insight_Dashboard/API_Documentation/URL_Decoder_API)
- [TAP Reports API](https://help.proofpoint.com/Threat_Insight_Dashboard/API_Documentation/Reports_API)
- [Essentials API Overview](https://us1.proofpointessentials.com/api/v1/docs/index.php)
- [Essentials Threat API](https://help.proofpoint.com/Essentials/Additional_Resources/API_Documentation/Essentials_Threat_API)
- [SER API Documentation](https://api-docs.ser.proofpoint.com/)
- [SER Admin API](https://admin-api-docs.ser.proofpoint.com/)
- [ITM On-Prem API Portal](https://prod.docs.oit.proofpoint.com/configuration_guide/observeit_api_portal.htm)
- [Proofpoint Community API Snippets](https://github.com/pfptcommunity/pfptcommunity)
- [PSAT API Python](https://github.com/pfptcommunity/psat-api-python)
- [TAP API Python](https://github.com/pfptcommunity/tap-api-python)
- [go-proofpoint](https://github.com/greenpau/go-proofpoint)
- [proofpoint_itm Python](https://github.com/drizzo-tech/proofpoint_itm)
- [Proofpoint Threat Protection XSOAR](https://xsoar.pan.dev/docs/reference/integrations/proofpoint-threat-protection)
- [Proofpoint PPS v2 XSOAR](https://xsoar.pan.dev/docs/reference/integrations/proofpoint-protection-server-v2)
- [Proofpoint Threat Response XSOAR](https://xsoar.pan.dev/docs/reference/integrations/proofpoint-threat-response)
- [Proofpoint TAP v2 XSOAR](https://xsoar.pan.dev/docs/reference/integrations/proofpoint-tap-v2)
- [Proofpoint CASB Overview](https://docs.public.analyze.proofpoint.com/pcasb/casb_overview.htm)
- [Proofpoint Isolation Data Sheet](https://www.proofpoint.com/us/resources/data-sheets/browser-isolation)
- [Proofpoint Sigma Platform](https://www.proofpoint.com/sites/default/files/solution-briefs/pfpt-us-sb-sigma-platform.pdf)
- [Tessian/Core Email Protection API](https://developer.tessian.com/documentation/api/index.html)
- [Proofpoint NPRE](https://peoplecentric.proofpoint.com/)
- [PSProofpoint PowerShell](https://www.powershellgallery.com/packages/PSProofpoint)
- [Splunk SOAR Proofpoint Threat Protection](https://github.com/splunk-soar-connectors/proofpoint-threat-protection)
- [Spambrella Essentials API Reference](https://www.spambrella.com/faq/email-security-api/)
- [Spambrella Statistics API](https://www.spambrella.com/faq/proofpoint-statistics-api/)
