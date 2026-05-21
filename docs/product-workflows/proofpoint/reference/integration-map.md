# Integration Map: Proofpoint — Authoring Policies

> Generated: 2026-05-21 | Scope: All integration touchpoints across 14 capability groups
> Source evidence grades: A = Official docs | B = Vendor training/video | C = Demo/KB | D = Community | U = Assumption

---

## Integration Points

| # | Integration | Direction | Protocol | Auth | Data Format | Capability | API Coverage | Source |
|---|------------|-----------|----------|------|-------------|-----------|-------------|--------|
| 1 | LDAP / Active Directory (user sync) | Inbound | LDAPS / LDAP | Service Account | LDIF | TAP per-group config, Endpoint DLP Agent Policies (If conditions) | PARTIAL | S2 — Grade B |
| 2 | SOAR Platform (XSOAR) | Bidirectional | REST | API Key | JSON | PPS Quarantine Management, PPS rule operations | PARTIAL | S16 — Grade C |
| 3 | SIEM Platform | Outbound | Syslog / CEF | Certificate / Token | CEF/Syslog | TAP alerts, Email filtering events, Endpoint DLP incidents | PARTIAL | S4 — Grade A (ITM API) |
| 4 | Proofpoint Isolation Console | Bidirectional | REST (internal) | Admin session | JSON | TAP VAP/VIP list import; URL Isolation redirect | GAP (manual import) | S15 — Grade B |
| 5 | TAP Dashboard | Outbound (alerts) | HTTPS portal | Admin session | Web UI | TAP URL/Attachment Defense alerts, VAP list | GAP | S21, S22 — Grade C |
| 6 | Proofpoint Data Security (CASB integration) | Bidirectional | Internal API | Internal | Internal | CASB DLP shares classifiers with Email DLP | PARTIAL | S13 — Grade A |
| 7 | Cloud Applications (Microsoft 365, Google Workspace, Salesforce, etc.) | Inbound | OAuth 2.0 / HTTPS | OAuth token | JSON | CASB visibility, threat detection, DLP enforcement | GAP (connector setup) | S13 — Grade A |
| 8 | IaaS Cloud Providers (AWS, Azure, GCP) | Inbound | REST / Cloud APIs | IAM role / Service Principal | JSON | CASB Infrastructure Security Assessment | GAP | S13 — Grade A |
| 9 | Proofpoint Archive | Outbound (message capture) | Internal MTA | Internal | MIME/email | Archive Retention, Legal Hold — captures email pre-delivery | GAP | S27 — Grade A |
| 10 | PhishAlarm (Outlook/Gmail add-in) | Inbound | HTTPS | OAuth / Service Account | Phishing report payload | SAT Follow-Up campaigns — "Reported Phishing" criterion | GAP | S3 — Grade A |
| 11 | Proofpoint Essentials REST API | Bidirectional | REST/HTTPS | API Key | JSON | Email filter CRUD, user management, quarantine operations | PARTIAL | S26 — Grade B |
| 12 | Proofpoint ITM Agent API | Outbound (events) | REST/HTTPS | API Key (must enable) | JSON | ITM alert retrieval, playbook integration | PARTIAL (off by default) | S4 — Grade A |
| 13 | Proofpoint Data Security REST API | Outbound (incidents) | REST/HTTPS | API Key | JSON | Endpoint DLP incident retrieval, evidence collection | PARTIAL | S28 — Grade C |
| 14 | Insider Threat Library (Proofpoint-hosted ZIP) | Inbound | Manual ZIP import | Admin (manual) | ZIP | ITM Alert + Prevention rule library updates | GAP (manual only) | S5 — Grade A |
| 15 | End-user browser (Isolation) | Bidirectional | HTTPS (cloud container) | Session token | HTML render | Browser isolation session rendering | N/A (runtime) | S15 — Grade B |
| 16 | SMTP Gateway (outbound email) | Outbound | SMTP/TLS | Relay auth | MIME | Email Encryption — TLS enforcement with fallback to Proofpoint Encryption | PARTIAL | S14 — Grade B |
| 17 | Proofpoint Secure Reader (email recipients) | Outbound | HTTPS | Portal auth | Encrypted message portal | Email Encryption — recipient decryption portal | N/A (runtime) | S14 — Grade B |

---

## Direction Legend

- **Inbound:** External system pushes data INTO Proofpoint
- **Outbound:** Proofpoint sends data TO external system
- **Bidirectional:** Data flows both ways
- **N/A (runtime):** Protocol operates at message delivery time, not configuration time

---

## Integration Architecture Diagram

```mermaid
graph LR
    subgraph "Identity & Directory"
        AD[Active Directory / LDAP]
    end

    subgraph "Proofpoint Core"
        PP_EMAIL[Email Protection<br/>Essentials / PPS / PoD]
        PP_TAP[TAP Dashboard]
        PP_DATA_SEC[Data Security<br/>Endpoint DLP + CASB]
        PP_ITM[ITM On-Prem<br/>ObserveIT]
        PP_ARCHIVE[Essentials Archive]
        PP_ISO[Isolation Console]
        PP_SAT[Security Awareness]
    end

    subgraph "External Enforcement"
        SOAR[SOAR Platform<br/>e.g. XSOAR]
        SIEM[SIEM<br/>Splunk / Sentinel]
        CLOUD_APPS[SaaS Cloud Apps<br/>M365, GWS, etc.]
        IAAS[IaaS Cloud<br/>AWS / Azure / GCP]
    end

    subgraph "End User Touchpoints"
        PHISHALARM[PhishAlarm<br/>Outlook/Gmail Add-in]
        SECURE_READER[Proofpoint Secure Reader<br/>Email decryption portal]
        BROWSER[End User Browser<br/>Isolation sessions]
    end

    AD -->|LDAPS — user sync| PP_EMAIL
    AD -->|LDAPS — user sync| PP_TAP
    AD -->|LDAPS — group sync| PP_DATA_SEC
    AD -->|LDAPS — user sync| PP_ISO

    PP_EMAIL <-->|REST API — filter CRUD, quarantine| SOAR
    PP_DATA_SEC <-->|REST API — incidents| SOAR
    PP_ITM <-->|REST API (if enabled)| SOAR

    PP_EMAIL -->|Syslog/CEF — email events| SIEM
    PP_TAP -->|Syslog/CEF — TAP alerts| SIEM
    PP_DATA_SEC -->|REST — DLP incidents| SIEM
    PP_ITM -->|REST API — ITM alerts| SIEM

    PP_DATA_SEC <-->|OAuth — cloud app visibility| CLOUD_APPS
    PP_DATA_SEC -->|Cloud APIs — IaaS assessment| IAAS

    PP_TAP <-->|Internal — VAP list MANUAL IMPORT| PP_ISO
    PP_DATA_SEC <-->|Internal — shared classifiers| PP_EMAIL

    PP_SAT <-->|HTTPS — simulated phishing delivery| PHISHALARM
    PP_EMAIL -->|SMTP + Secure Reader portal| SECURE_READER
    PP_ISO -->|HTTPS — isolated browser| BROWSER
```

---

## Integration Dependencies

The following integrations are prerequisite to specific capability configurations:

| Downstream Capability | Prerequisite Integration | Why Required |
|----------------------|------------------------|--------------|
| TAP per-group enablement | Active Directory / LDAP | Groups must exist in PPS/PoD directory before per-group TAP config |
| CASB DLP and Threat policies | Cloud App Connectors (OAuth) | Policies fire on no traffic without an active connector |
| CASB Infrastructure Assessment | IaaS Cloud connectors (IAM) | Separate connector from SaaS connectors |
| Isolation VAP protection | TAP Dashboard (manual export) + Isolation Console (manual import) | No auto-sync; both must be operational |
| ITM SOAR/SIEM integration | ITM API toggle (OFF by default) | Admin must enable API in System Policy Settings |
| SAT "Reported Phishing" criterion | PhishAlarm add-in deployed | Criterion returns zero without PhishAlarm |
| Endpoint DLP If/Then user scoping | Active Directory group sync | Agent Policy If conditions reference AD groups |

---

## Integration Gaps

| # | Gap | Capability Affected | Impact | Workaround |
|---|-----|-------------------|--------|-----------|
| 1 | No auto-sync between TAP VAP list and Isolation Console | TAP / Isolation | HIGH — new VAPs unprotected until manual import | Manual export+import cycle; shorten review cadence |
| 2 | ITM API disabled by default | ITM | HIGH — SOAR/SIEM integrations silently fail until enabled | Admin must enable API toggle in System Policy Settings |
| 3 | Library update ZIPs require manual import | ITM | MEDIUM — active rules may be outdated | Quarterly manual check for new library ZIPs |
| 4 | CASB connector OAuth scope requirements not in public docs | CASB | HIGH — provisioning blocked without known required permissions | Use in-console connector wizard; have cloud app admin present |
| 5 | Archive capture scope undocumented | Archive | HIGH — unclear if quarantined messages are archived | Verify capture scope at provisioning; document behavior |
| 6 | Essentials API v1 full field parity unconfirmed | Email Filtering | MEDIUM — automation may miss fields not in API | Validate against live API endpoint documentation |
| 7 | No API for SAT reports or campaign management | SAT | HIGH — compliance reporting is entirely manual | Export reports manually from SAT console |
| 8 | TAP Dashboard has no public API for alert retrieval | TAP | HIGH — TAP alert review is entirely manual | Manual console review; some SIEM export via syslog |
