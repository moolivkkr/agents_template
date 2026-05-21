# Broadcom Symantec DLP -- Integration Map

> **Product:** Symantec Data Loss Prevention (Broadcom)
> **Scope:** All integration touchpoints -- inbound, outbound, bidirectional
> **Evidence:** doc-corpus.md [S1-S28], api-intelligence.md, video-intelligence.md

---

## Integration Summary

| Direction | Count | Key Technologies |
|-----------|-------|-----------------|
| **Inbound** | 8 | ICAP, MIP, AD/LDAP, Entra ID, email MTA, cloud apps, directory services, ICA |
| **Outbound** | 10 | Syslog/CEF, SOAR, ServiceNow, email notification, quarantine, encryption, MIP labels |
| **Bidirectional** | 6 | REST API, CloudSOC, ServiceNow, Data Insight, FlexResponse, Detection REST API 2.0 |

---

## Inbound Integrations

These integrations send data INTO Symantec DLP for inspection, identity resolution, or policy enrichment.

### 1. ICAP (Web Proxy Integration)

| Attribute | Value |
|-----------|-------|
| **Protocol** | ICAP (RFC 3507) |
| **Direction** | Inbound (proxy sends content to DLP for inspection) |
| **DLP Component** | Network Prevent for Web Server |
| **Port** | 1344 (default), configurable |
| **Modes** | REQMOD (request modification), RESPMOD (response modification) |
| **Secure ICAP** | TLS supported (via stunnel or native) |
| **Compatible Proxies** | Blue Coat/ProxySG, Squid 3.5.x, Zscaler, Check Point, Cisco WSA, Palo Alto |
| **Configuration** | ICAP keystore at `DetectionServer/keystore/secureicap.jks` |
| **Performance** | Must match concurrent ICAP connections between proxy and Web Prevent |
| **Evidence** | A [S1, S4, S15] |

**Flow:**
```
User Browser --> Web Proxy --> ICAP REQMOD --> DLP Web Prevent --> Policy Evaluation
                                                                        |
                                              ICAP Response (Block/Allow) <--+
```

### 2. Microsoft Information Protection (MIP) -- Inbound Label Reading

| Attribute | Value |
|-----------|-------|
| **Protocol** | MIP SDK |
| **Direction** | Inbound (DLP reads MIP sensitivity labels on documents) |
| **DLP Component** | Enforce Server + Detection Servers |
| **Condition** | "Content Matches MIP Tag Rule" in detection rules |
| **Versions** | DLP 15.8+ (read), 16.0+ (enhanced), 16.1+ (auto-classify) |
| **Configuration** | MIP SDK connector on Enforce Server; tenant credentials |
| **Use Case** | Policy conditions based on existing MIP labels |
| **Evidence** | A [S1, S2, S3, V37] |

### 3. Active Directory / LDAP

| Attribute | Value |
|-----------|-------|
| **Protocol** | LDAP / LDAPS |
| **Direction** | Inbound (DLP queries AD for user groups, attributes) |
| **DLP Component** | Enforce Server |
| **Navigation** | System > Settings > Directory Connections |
| **Used For** | Directory Group Matching (DGM), user-based exceptions, RBAC, Lookup Plugins |
| **Configuration** | Hostname, port, base DN, encryption, bind credentials |
| **Gotcha** | Kerberos domain names must be CAPITALIZED in krb5.ini/krb5.conf |
| **Evidence** | A [S1, S4] |

### 4. Microsoft Entra ID

| Attribute | Value |
|-----------|-------|
| **Protocol** | REST / Graph API |
| **Direction** | Inbound (DLP syncs Entra ID identities with Enforce Server) |
| **DLP Component** | Enforce Server |
| **Versions** | DLP 25.1+ (DGM via Entra ID), 26.1 (full Entra ID authentication) |
| **Used For** | Cloud identity sync, DGM policy evaluation via onPremisesSecurityIdentifier |
| **Evidence** | A [S3] |

### 5. Email MTA (Mail Transfer Agent)

| Attribute | Value |
|-----------|-------|
| **Protocol** | SMTP (reflecting mode) |
| **Direction** | Inbound (MTA routes email through DLP for inspection) |
| **DLP Component** | Network Prevent for Email Server |
| **Compatible MTAs** | Postfix, Sendmail, Microsoft Exchange |
| **Mode** | Reflecting -- message analyzed, returned with X-headers |
| **Used With** | Symantec Messaging Gateway (SMG) for quarantine/encryption |
| **Evidence** | A [S1, S4, S13] |

**Flow:**
```
Email Sender --> MTA --> DLP Email Prevent --> Policy Evaluation
                  ^                                    |
                  |            X-Headers Added <--------+
                  |                    |
                  +--- SMG (quarantine/encrypt/block based on headers)
```

### 6. Cloud Applications (via CloudSOC/CASB)

| Attribute | Value |
|-----------|-------|
| **Protocol** | CloudSOC API + Cloud Connectors |
| **Direction** | Inbound (cloud app content sent to DLP for inspection) |
| **DLP Component** | Cloud Detection Service (CDS) |
| **Supported Apps** | 100+ including Office 365, G-Suite, Box, Dropbox, Salesforce, OneDrive, Google Drive |
| **Capabilities** | DIM (Data in Motion) + DAR (Data at Rest) scanning |
| **Evidence** | A [S1, S2, S24, V34, V38] |

### 7. Information Centric Analytics (ICA)

| Attribute | Value |
|-----------|-------|
| **Protocol** | Internal (Enforce Server to ICA Server) |
| **Direction** | Inbound (ICA provides user risk scores to DLP) |
| **DLP Component** | Enforce Server |
| **Navigation** | System > Servers and Detectors > ICA |
| **Data Provided** | User risk scores (1-100), behavioral analytics |
| **Used For** | Risk-based detection conditions in policies |
| **Evidence** | B [S2, S25] |

### 8. Detection REST API 2.0 (Content Submission)

| Attribute | Value |
|-----------|-------|
| **Protocol** | HTTPS (REST) |
| **Direction** | Inbound (external applications submit content for DLP scanning) |
| **DLP Component** | Cloud Detection Service or API Detection Appliance |
| **Endpoint** | `POST /v2.0/DetectionRequests` |
| **Auth** | Certificate-based mutual TLS |
| **Use Cases** | Custom app DLP scanning, LLM/GenAI prompt safety, CI/CD pipeline scanning |
| **Evidence** | A [S21, API intelligence] |

---

## Outbound Integrations

These integrations send data FROM Symantec DLP to external systems.

### 1. Syslog / CEF (SIEM Forwarding)

| Attribute | Value |
|-----------|-------|
| **Protocol** | Syslog (UDP/TCP/TLS) |
| **Direction** | Outbound (DLP pushes events to SIEM) |
| **DLP Component** | Enforce Server (via response rules) |
| **Format** | CEF (Common Event Format), configurable message template |
| **Data** | Incidents, system events, audit logs |
| **Trigger** | Response rule action: "Log to Syslog Server" |
| **Configuration** | Response Rule > Action > Log to Syslog (host, port, message, protocol, level) |
| **System-level** | Manager.properties for system event syslog |
| **Evidence** | A [S1, S4, KB-8, KB-9] |

**CEF Variables Available:**
`$INCIDENT_ID$`, `$POLICY$`, `$RULES$`, `$SEVERITY$`, `$BLOCKED$`, `$APPLICATION_USER$`, `$ENDPOINT_MACHINE$`, `$ENDPOINT_USERNAME$`, `$MACHINE_IP$`, `$FILE_NAME$`, `$RECIPIENTS$`, `$SENDER$`, `$SUBJECT$`, `$MATCH_COUNT$`, `$PROTOCOL$`

**Compatible SIEMs:**

| SIEM | Integration Method | Official Support |
|------|-------------------|-----------------|
| Splunk | Official Add-on for Symantec DLP | YES |
| Microsoft Sentinel | CEF via AMA connector | YES |
| Google Chronicle | Native Symantec DLP parser | YES |
| IBM QRadar / JSA | DSM for Symantec DLP | YES |
| LogRhythm | Syslog CEF parser | YES |
| ManageEngine EventLog Analyzer | Built-in application support | YES |
| ArcSight | CEF native | YES |
| Generic SIEM | Syslog/CEF ingestion | YES |

### 2. SOAR Platforms (via REST API)

| Attribute | Value |
|-----------|-------|
| **Protocol** | HTTPS (REST) |
| **Direction** | Outbound (SOAR platforms pull/push incident data via API) |
| **DLP Component** | Enforce Server REST API |
| **Auth** | HTTP Basic / Kerberos / Certificate / JWT |
| **Evidence** | A [API intelligence, SOAR docs] |

**Supported SOAR Platforms:**

| Platform | Connector | Key Actions |
|----------|-----------|-------------|
| **Cortex XSOAR** (Palo Alto) | Official v2 integration pack | List/get/update incidents, get history, get original message, list patterns |
| **FortiSOAR** (Fortinet) | v2.2.0 connector | Get incidents, details, update status/notes/attributes |
| **Swimlane Turbine** | Connector | Get incidents, original messages, update incidents |
| **Splunk SOAR** | Via REST API integration | Incident management via REST |

### 3. ServiceNow

| Attribute | Value |
|-----------|-------|
| **Protocol** | ServiceNow API + DLP REST API |
| **Direction** | Outbound (DLP incidents imported to ServiceNow) |
| **DLP Component** | Enforce Server |
| **Integration** | DLP Incident Response app (ServiceNow Store) |
| **Capabilities** | Import DLP incidents, view matched data, automated scheduling |
| **End User Remediation** | Built-in decentralized remediation (DLP 15.8+) |
| **Evidence** | A [S1, S2, V25, V28, SOAR-4, SOAR-5] |

### 4. Email Notification

| Attribute | Value |
|-----------|-------|
| **Protocol** | SMTP |
| **Direction** | Outbound (DLP sends email notifications) |
| **DLP Component** | Enforce Server |
| **Trigger** | Response rule action: "Send Email Notification" |
| **Recipients** | Data owner, manager, compliance officer, custom |
| **Evidence** | A [S1, S4] |

### 5. Email Quarantine (via SMG)

| Attribute | Value |
|-----------|-------|
| **Protocol** | X-headers + SMG API |
| **Direction** | Outbound (DLP directs email quarantine) |
| **DLP Component** | Network Prevent for Email + Symantec Messaging Gateway |
| **Mechanism** | DLP adds X-headers; SMG enforces quarantine/release |
| **FlexResponse** | Email Quarantine Connect FlexResponse plugin |
| **Evidence** | A [S1, S4, S14] |

### 6. File Quarantine (Network Protect)

| Attribute | Value |
|-----------|-------|
| **Protocol** | File system operations |
| **Direction** | Outbound (DLP quarantines/copies/encrypts files) |
| **DLP Component** | Network Discover/Protect Server |
| **Actions** | Quarantine to secure location, copy, encrypt, apply DRM |
| **Tombstone** | Original file replaced with marker/tombstone file |
| **Evidence** | A [S1, S4] |

### 7. Endpoint User Notification

| Attribute | Value |
|-----------|-------|
| **Protocol** | Agent-to-user (OS popup) |
| **Direction** | Outbound (DLP agent displays popup to user) |
| **DLP Component** | DLP Agent (Endpoint Prevent) |
| **Actions** | Block notification, justify prompt (User Cancel), notify-only |
| **Customization** | HTML formatting, localization, branding |
| **Evidence** | A [S1, V23, KB-6] |

### 8. Encryption (Endpoint)

| Attribute | Value |
|-----------|-------|
| **Protocol** | Symantec Endpoint Encryption API |
| **Direction** | Outbound (DLP triggers file encryption) |
| **DLP Component** | DLP Agent (Endpoint Prevent) |
| **Trigger** | Response rule action: "Encrypt" |
| **Evidence** | A [S1, S4] |

### 9. MIP Label Application (Outbound)

| Attribute | Value |
|-----------|-------|
| **Protocol** | MIP SDK |
| **Direction** | Outbound (DLP applies MIP sensitivity labels to documents) |
| **DLP Component** | Enforce Server + Detection Servers |
| **Action** | Response rule: "Apply Classification Label" |
| **Versions** | DLP 16.1+ (auto-classify with MIP labels) |
| **Effect** | MIP RMS encryption applied when label is set |
| **Evidence** | A [S1, S2, S3, V37] |

### 10. Audit Log Export

| Attribute | Value |
|-----------|-------|
| **Protocol** | REST API + CSV export |
| **Direction** | Outbound (audit logs exported for compliance) |
| **DLP Component** | Enforce Server |
| **Navigation** | System > Servers and Detectors > Audit Logs |
| **API** | REST API access (DLP 16.0 RU1+) |
| **Syslog** | Audit log syslog forwarding configurable |
| **Evidence** | A [S1, S2, S4] |

---

## Bidirectional Integrations

These integrations involve data flow in both directions between Symantec DLP and the external system.

### 1. Enforce Server REST API

| Attribute | Value |
|-----------|-------|
| **Protocol** | HTTPS (REST) |
| **Direction** | Bidirectional |
| **Base URL** | `https://<enforce>:443/ProtectManager/webservices/v2/` |
| **Auth** | HTTP Basic (primary), Kerberos (16.0 RU2+), Certificate (16.0 RU2+), JWT (26.1+) |
| **Inbound** | Query incidents, retrieve details/history/messages, list policies/users/roles/targets |
| **Outbound** | Update incidents, create users/roles, import policies, trigger EDM indexing, manage certificates |
| **Endpoints** | 38+ documented |
| **Versions** | 15.7+ (incident), 16.0+ (policy/system), 25.1+ (user/role/discover) |
| **Evidence** | A [API intelligence] |

### 2. CloudSOC / CASB

| Attribute | Value |
|-----------|-------|
| **Protocol** | HTTPS (REST) + Cloud Connectors |
| **Direction** | Bidirectional |
| **Base URL** | `https://app.elastica.net/api/...` (US) / `https://app.eu.elastica.net/...` (EU) |
| **Auth** | OAuth2 / API Key |
| **Inbound** | Cloud app content submitted for DLP scanning |
| **Outbound** | DLP profiles, data identifiers, policy enforcement (block, quarantine, label) |
| **API** | Profile CRUD, data identifier listing, policy queries |
| **Evidence** | A [S24, V34, V38, CLOUD-1, CLOUD-2] |

### 3. ServiceNow (Bidirectional Sync)

| Attribute | Value |
|-----------|-------|
| **Protocol** | ServiceNow API + DLP REST API |
| **Direction** | Bidirectional |
| **DLP > ServiceNow** | Import incidents, matched data, policy details |
| **ServiceNow > DLP** | Status updates, remediation actions sync back |
| **End User Remediation** | Data owners remediate via ServiceNow; status syncs to DLP |
| **Evidence** | A [S1, S2, V25, V28] |

### 4. Veritas Data Insight

| Attribute | Value |
|-----------|-------|
| **Protocol** | Internal API |
| **Direction** | Bidirectional |
| **DLP > Data Insight** | Sensitive file information |
| **Data Insight > DLP** | Ownership, access permissions, usage data |
| **Features** | Self-Service Portal, Open Access Reporting |
| **Evidence** | B [S12] |

### 5. FlexResponse Plugins

| Attribute | Value |
|-----------|-------|
| **Protocol** | Java Plugin API |
| **Direction** | Bidirectional |
| **DLP Component** | Enforce Server (Server FlexResponse) + DLP Agents (Endpoint FlexResponse) |
| **Inbound** | Plugin receives incident context from DLP |
| **Outbound** | Plugin executes custom actions (quarantine, encrypt, redact, integrate with external systems) |
| **Configuration** | Server: Plugins.properties file; Endpoint: deployed to each agent |
| **Examples** | Email Quarantine Connect, encryption, DRM, content redaction |
| **Evidence** | A [S10, S14] |

### 6. Detection REST API 2.0 (Content Inspection Service)

| Attribute | Value |
|-----------|-------|
| **Protocol** | HTTPS (REST) |
| **Direction** | Bidirectional |
| **Inbound** | External app submits content for scanning |
| **Outbound** | DLP returns violations, matched policies, response action recommendations |
| **Endpoint** | `POST /v2.0/DetectionRequests` |
| **Auth** | Certificate-based mutual TLS |
| **Use Cases** | Custom app DLP, LLM prompt safety, CASB integration, CI/CD scanning |
| **Evidence** | A [S21] |

---

## Integration Architecture Patterns

### Pattern 1: ICAP Web Inspection
```
Browser --> Web Proxy (Blue Coat/Squid) --> ICAP --> DLP Web Prevent --> Policy Eval
                                                                            |
                        ICAP Response (200 Allow / 403 Block) <-------------+
```

### Pattern 2: MTA Email Reflection
```
Email Client --> MTA (Exchange/Postfix) --> DLP Email Prevent --> Policy Eval
                       ^                                              |
                       |          Message + X-Headers <---------------+
                       |                    |
                       +--- SMG (quarantine/encrypt/block per X-headers)
```

### Pattern 3: Agent-to-Server Endpoint
```
DLP Agent (15-min poll) --> Endpoint Prevent Server --> Enforce Server
     |                            |                         |
     +-- Local inspection         +-- Policy distribution   +-- Incident storage
     +-- Block/Notify/Encrypt     +-- Config updates        +-- Reporting
```

### Pattern 4: Cloud Detection Pipeline
```
Cloud App (O365/Box/Salesforce) --> CloudSOC Securlet --> CDS (Cloud Detection)
                                                              |
                                    Policy Evaluation <-------+
                                          |
                          Actions: Block/Quarantine/Label/Notify
```

### Pattern 5: SIEM Forwarding
```
DLP Enforce Server --> Syslog Response Rule --> CEF Message --> SIEM
     |                                                          |
     +-- Incidents                                              +-- Splunk
     +-- System Events                                          +-- Sentinel
     +-- Audit Logs                                             +-- QRadar
                                                                +-- Chronicle
```

### Pattern 6: SOAR Orchestration
```
SOAR Platform (XSOAR/FortiSOAR/Swimlane)
     |
     +-- Poll: POST /incidents (fetch new incidents)
     |
     +-- Enrich: GET /incidents/{id}/components (get matched content)
     |
     +-- Enrich: GET /incidents/{id}/originalMessage (get evidence)
     |
     +-- Decide: Playbook logic (auto-triage, risk scoring)
     |
     +-- Act: PATCH /incidents (update status, notes, attributes)
     |
     +-- Notify: ServiceNow ticket / Slack alert / Email
```

### Pattern 7: DLP-as-Code Pipeline
```
Policy Author --> Console (author rules) --> Export Policy XML
                                                  |
                              Git Repository <----+
                                  |
                              CI/CD Pipeline
                                  |
                   POST /policies/import (25.1+ API)
                                  |
                   POST /policies/apply (deploy to servers)
```

### Pattern 8: LLM/GenAI Safety
```
User Prompt --> Application --> POST /v2.0/DetectionRequests
                                       |
                               DLP Cloud Detection Service
                                       |
                            Response: Violations + Actions
                                       |
                   Application: Allow prompt / Block prompt / Redact
```

---

## Integration Capability Matrix

| Integration | Protocol | Auth | Real-Time | API Maturity | Config Complexity |
|------------|----------|------|-----------|-------------|-------------------|
| ICAP (Web Proxy) | ICAP | Cert/IP | YES | N/A (protocol) | HIGH |
| MIP Labels | MIP SDK | Service principal | YES | GOOD | HIGH |
| AD/LDAP | LDAP/S | Bind creds | Near-real-time (sync) | N/A | MEDIUM |
| Entra ID | REST | OAuth2 | Near-real-time | GOOD | HIGH |
| Email MTA | SMTP | N/A | YES | N/A (protocol) | VH |
| CloudSOC/CASB | REST | OAuth2/API Key | Near-real-time | GOOD | HIGH |
| Syslog/CEF | Syslog | N/A | YES (on incident) | N/A (protocol) | MEDIUM |
| SOAR (XSOAR) | REST | Basic/Kerberos/JWT | Polling-based | EXCELLENT | MEDIUM |
| SOAR (FortiSOAR) | REST | Basic | Polling-based | GOOD | MEDIUM |
| ServiceNow | REST | Basic | Scheduled sync | GOOD | HIGH |
| Detection API 2.0 | REST | mTLS | YES (request/response) | GOOD | MEDIUM |
| Data Insight | Internal | Internal | Periodic sync | MODERATE | VH |
| FlexResponse | Java Plugin | N/A | YES (on incident) | GOOD | VH |
| Enforce REST API | REST | Basic/Kerberos/Cert/JWT | Polling or on-demand | EXCELLENT | LOW-MEDIUM |

---

*Complete integration map covering 24 integration touchpoints across inbound, outbound, and bidirectional directions. 8 architecture patterns documented.*
