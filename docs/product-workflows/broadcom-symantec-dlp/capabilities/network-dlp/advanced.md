# Network DLP — Advanced Reference
## Broadcom Symantec DLP (Enforce Server, version 16.x/25.x/26.x)

> **Purpose:** Complete field reference for every network detection server type's configuration screens, architecture diagrams, per-server examples, and API integration patterns.
> **Evidence sources:** doc-corpus.md [S1-S28], video-intelligence.md [V1-V45], api-intelligence.md

---

## Table of Contents

1. [Network Monitor Deep Dive](#1-network-monitor-deep-dive)
2. [Network Prevent for Email Deep Dive](#2-network-prevent-for-email-deep-dive)
3. [Network Prevent for Web Deep Dive](#3-network-prevent-for-web-deep-dive)
4. [Network Discover Deep Dive](#4-network-discover-deep-dive)
5. [Network Protect Deep Dive](#5-network-protect-deep-dive)
6. [SSL/TLS Inspection Reference](#6-ssltls-inspection-reference)
7. [Performance Sizing Guide](#7-performance-sizing-guide)
8. [Multi-Server Topology Patterns](#8-multi-server-topology-patterns)
9. [MTA Integration Reference](#9-mta-integration-reference)
10. [ICAP Integration Reference](#10-icap-integration-reference)
11. [Discover Target Types — Full Configuration](#11-discover-target-types-full-configuration)
12. [API Integration for Network DLP](#12-api-integration-for-network-dlp)

---

## 1. Network Monitor Deep Dive

### 1.1 Full Configuration Screen

```
+=========================================================================+
|  System > Servers and Detectors > dlp-netmon01 > Configuration           |
+=========================================================================+
|  [General] [Protocols] [SSL] [Performance] [Advanced]           [Save]  |
+-------------------------------------------------------------------------+
|  General:                                                                |
|    Server Name:            [dlp-netmon01.corp.example.com    ]          |
|    Server Type:            Network Monitor (read-only)                   |
|    Policy Group:           [Default Policy Group           v]           |
|    Description:            [Primary SMTP/HTTP monitor       ]           |
+-------------------------------------------------------------------------+
|  Protocols:                                                              |
|    +---------------------------------------------------------------+   |
|    | Protocol | Enabled | Port(s)         | Notes                  |   |
|    |----------|---------|-----------------|------------------------|   |
|    | SMTP     | [x]     | 25, 587         | Outbound email         |   |
|    | HTTP     | [x]     | 80              | Web traffic             |   |
|    | HTTPS    | [x]     | 443             | Requires SSL cert       |   |
|    | FTP      | [x]     | 20, 21          | File transfers          |   |
|    | IM       | [ ]     | Various          | Legacy IM protocols    |   |
|    | Custom   | [ ]     | [____]          | User-defined ports      |   |
|    +---------------------------------------------------------------+   |
+-------------------------------------------------------------------------+
|  SSL/TLS:                                                                |
|    Enable SSL inspection:      [x]                                       |
|    Inspection mode:            (o) Passive (server private key)         |
|                                ( ) Active (MITM, requires proxy)        |
|    Private key store:          [/opt/dlp/certs/server-keys.jks  ]      |
|    Key password:               [********                         ]      |
|    Supported versions:         [x] TLS 1.2   [x] TLS 1.3              |
|    Certificate validation:     [x] Verify server certificates           |
+-------------------------------------------------------------------------+
|  Performance:                                                            |
|    Monitoring interface:       [eth1                          v]        |
|    Promiscuous mode:           [x] Enabled                               |
|    Packet buffer size (MB):    [512  ]                                   |
|    Max concurrent sessions:    [5000 ]                                   |
|    Session timeout (sec):      [300  ]                                   |
|    Reassembly buffer (MB):     [256  ]                                   |
+-------------------------------------------------------------------------+
|  Advanced:                                                               |
|    L7 filtering:                                                         |
|      SMTP sender filter:       [                               ]        |
|      SMTP recipient filter:    [                               ]        |
|      HTTP host filter:         [                               ]        |
|    Logging level:              [Warning                      v]         |
|    Capture mode:               (o) Full content capture                  |
|                                ( ) Metadata only                         |
|                                ( ) Content + metadata                    |
+=========================================================================+
```

**L7 Filtering (Advanced):**

Network Monitor supports Layer 7 filtering to reduce noise by excluding specific senders, recipients, or hosts from monitoring.

| Filter | Type | Description | Evidence |
|--------|------|-------------|----------|
| SMTP sender filter | Regex pattern | Exclude emails from specific senders (e.g., `noreply@.*\.corp\.example\.com`) | A [S1, S4] |
| SMTP recipient filter | Regex pattern | Exclude emails to specific recipients | A [S1, S4] |
| HTTP host filter | Domain pattern | Exclude specific domains from web monitoring | A [S1] |

**Example 1 -- Filter out automated system emails:**
Set SMTP sender filter to `noreply@corp\.example\.com|monitoring@corp\.example\.com` to exclude monitoring alerts and system notifications from DLP scanning. These high-volume, low-risk emails would otherwise generate thousands of false positives.

**Example 2 -- Custom TCP protocol monitoring:**
Enable Custom TCP with port 8443. This monitors traffic on a non-standard HTTPS port used by a custom application that transmits sensitive data.

[S1, S4, S9] Evidence: A

---

## 2. Network Prevent for Email Deep Dive

### 2.1 MTA Integration Patterns

#### Pattern A: Postfix Integration (Recommended)

```
Postfix main.cf Configuration:

# Route outbound email through DLP
content_filter = smtp:[dlp-mailprevent01.corp.example.com]:10025

# Receive inspected email back from DLP
# Add a secondary transport for DLP return path
master.cf:
  dlp-return  unix  -  -  n  -  -  smtpd
    -o smtpd_recipient_restrictions=permit_mynetworks,reject
    -o content_filter=
    -o receive_override_options=no_header_body_checks
    -o mynetworks=10.1.50.200/32  (DLP server IP)
```

```
Email Flow:
  Outlook -> Postfix:25 -> DLP:10025 -> Postfix:10026 -> Internet
                              |
                          (inspection)
                              |
                          X-headers added
```

[S1, S13] Evidence: A

#### Pattern B: Exchange Integration

```
Exchange Transport Rule:
  1. Create a Send Connector in Exchange
     Destination: DLP server (dlp-mailprevent01:10025)
     Usage: Custom connector for DLP inspection

  2. Create a Transport Rule
     Condition: All outbound messages
     Action: Route to DLP Send Connector

  3. Configure Exchange to accept return path
     Receive Connector: Allow relay from DLP server IP
```

[S1, S13] Evidence: A

#### Pattern C: Symantec Messaging Gateway (SMG) Integration

```
SMG provides advanced quarantine capabilities:
  1. Configure SMG to route outbound email through DLP
  2. DLP adds X-headers with verdict
  3. SMG interprets X-headers:
     X-DLP-Action: BLOCK -> SMG quarantines message
     X-DLP-Action: QUARANTINE -> SMG holds for admin review
     X-DLP-Action: ALLOW -> SMG delivers normally
  4. SMG quarantine console allows admin review and release
```

[S1, S14] Evidence: A

### 2.2 X-Header Reference

| X-Header | Values | Purpose | Evidence |
|-----------|--------|---------|----------|
| `X-DLP-Action` | BLOCK, ALLOW, REDIRECT, QUARANTINE | Primary action directive | A [S1, S13] |
| `X-DLP-Policy` | Policy name | Which policy triggered | A [S1] |
| `X-DLP-Severity` | 1-4 (High to Informational) | Incident severity | A [S1] |
| `X-DLP-Rule` | Rule name(s) | Which rules matched | A [S1] |
| `X-DLP-Encrypt` | TRUE/FALSE | Encryption directive for downstream gateway | A [S1] |
| `X-DLP-IncidentID` | Numeric ID | Incident ID for cross-reference | A [S1] |
| `X-DLP-MatchCount` | Numeric | Number of policy matches found | A [S1] |

**Example -- Custom X-header for SIEM integration:**
Add a custom X-header `X-DLP-CEF` with a CEF-formatted message. The email gateway logs this header to syslog, providing DLP incident data directly in the email log stream for SIEM correlation.

### 2.3 Email Prevent Response Rule Configuration

```
+=========================================================================+
|  Response Rule: Email-PCI-Block                                          |
+=========================================================================+
|  Rule Type: Automated Response                                           |
|                                                                         |
|  Conditions:                                                             |
|    [x] Detection server type: Network Prevent for Email                 |
|    [x] Severity is: High                                                |
|                                                                         |
|  Actions:                                                                |
|    Action 1: Network Prevent for Email -- Block Message                 |
|      Block type:        [Reject with bounce     v]                      |
|      Bounce message:    [Message rejected: DLP policy violation   ]     |
|                                                                         |
|    Action 2: Network Prevent for Email -- Add Header                    |
|      Header name:       [X-DLP-Blocked                            ]     |
|      Header value:      [TRUE                                     ]     |
|                                                                         |
|    Action 3: All Servers -- Send Email Notification                     |
|      To:                [dlp-team@corp.example.com                ]     |
|      Subject:           [DLP Alert: PCI data blocked in email     ]     |
|      Body:              [Incident $INCIDENT_ID$: $SENDER$ attempted... ]|
|                                                                         |
|    Action 4: All Servers -- Log to Syslog                               |
|      Host:              [siem.corp.example.com                    ]     |
|      Port:              [514                                      ]     |
|      Protocol:          [TCP                                      ]     |
|      Message:           [CEF:0|Broadcom|DLP|16.0|...              ]     |
|                                                                         |
+=========================================================================+
```

**Example 1 -- Block + Redirect to quarantine:**
Action 1: Block Message (reject to sender). Action 2: Redirect copy to `dlp-quarantine@corp.example.com` for compliance review. This provides both prevention (sender cannot send PCI data) and audit trail (quarantine copy for investigation).

**Example 2 -- Modify subject for sensitive internal email:**
Policy triggers on internal emails containing HIPAA data. Instead of blocking, modify the subject line to prepend "[CONTAINS PHI]". Email is delivered but tagged for awareness.

**Example 3 -- Encrypt via downstream gateway:**
Policy triggers on emails to external recipients containing financial data. Action: Add Header `X-DLP-Encrypt: TRUE`. Downstream email encryption gateway (ZixEncrypt, PGP Universal) reads the header and encrypts the email before delivery.

**Example 4 -- Tiered response by match count:**
- 1-5 credit card matches: Notify compliance team (email notification)
- 5-50 matches: Block message + notify compliance team
- 50+ matches: Block + quarantine + alert CISO + SIEM critical alert (indicates potential data breach)

[S1, S4, S13, S14] Evidence: A

---

## 3. Network Prevent for Web Deep Dive

### 3.1 ICAP Protocol Reference

```
ICAP Request Flow (REQMOD):

  1. User initiates web upload (HTTP POST)
  2. Proxy intercepts the request
  3. Proxy sends ICAP REQMOD to DLP:
     REQMOD icap://dlp-webprevent01:1344/reqmod ICAP/1.0
     Host: dlp-webprevent01
     Encapsulated: req-hdr=0, req-body=150

     [HTTP request headers]
     [HTTP request body (file upload data)]

  4. DLP inspects content, evaluates policies
  5. DLP returns ICAP response:
     ICAP/1.0 200 OK
     (allow) -- proxy forwards request to internet
     OR
     ICAP/1.0 200 OK
     (block) -- proxy returns block page to user
```

```
ICAP Response Flow (RESPMOD):

  1. User requests a web page
  2. Web server returns the page
  3. Proxy sends ICAP RESPMOD to DLP:
     RESPMOD icap://dlp-webprevent01:1344/respmod ICAP/1.0
     Encapsulated: res-hdr=0, res-body=200

     [HTTP response headers]
     [HTTP response body (page content)]

  4. DLP inspects response content
  5. DLP returns modified response (content removal) or allows as-is
```

### 3.2 Proxy-Specific Integration

#### Blue Coat / ProxySG

```
ProxySG Configuration:
  External Services > ICAP > New ICAP Service
    Name: SymantecDLP
    ICAP URL: icap://dlp-webprevent01.corp.example.com:1344/reqmod
    Max connections: 50
    Timeout: 120 seconds
    Fail mode: Fail Open (allow traffic if DLP unreachable)

  Policy > Web Access Layer
    Add rule: route HTTP POST uploads through ICAP service "SymantecDLP"
    Condition: Upload file size > 0 bytes
    Action: ICAP request modification
```

[S1, S15] Evidence: A

#### Squid Integration

```
Squid Configuration (squid.conf):

  # ICAP service definition
  icap_service dlp_reqmod reqmod_precache icap://dlp-webprevent01:1344/reqmod
  icap_service dlp_respmod respmod_precache icap://dlp-webprevent01:1344/respmod

  # ICAP access control
  adaptation_service_set dlp_services dlp_reqmod dlp_respmod
  adaptation_access dlp_services allow all

  # Connection pool (must match DLP server config)
  icap_service dlp_reqmod ... max-conn=50

  # Secure ICAP (via stunnel)
  # Use stunnel to create TLS tunnel between Squid and DLP
  # stunnel config:
  # [dlp-icap]
  # client = yes
  # accept = 127.0.0.1:1344
  # connect = dlp-webprevent01:11344
```

[S15] Evidence: A

### 3.3 Web Prevent Response Rule Configuration

```
+=========================================================================+
|  Response Rule: Web-Upload-Block                                         |
+=========================================================================+
|  Rule Type: Automated Response                                           |
|                                                                         |
|  Conditions:                                                             |
|    [x] Detection server type: Network Prevent for Web                   |
|    [x] Protocol: HTTP/HTTPS                                             |
|                                                                         |
|  Actions:                                                                |
|    Action 1: Network Prevent for Web -- Block                           |
|      Block page type:    [Custom block page         v]                  |
|      Custom HTML:                                                        |
|      +-----------------------------------------------------------+      |
|      | <html><body>                                               |      |
|      | <h2>Upload Blocked</h2>                                    |      |
|      | <p>Your upload was blocked by DLP policy because it        |      |
|      | contains sensitive data ($MATCH_COUNT$ matches found).</p>  |      |
|      | <p>Policy: $POLICY$</p>                                     |      |
|      | <p>Contact: dlp-support@corp.example.com</p>                |      |
|      | </body></html>                                              |      |
|      +-----------------------------------------------------------+      |
|                                                                         |
+=========================================================================+
```

**Example 1 -- Block file uploads containing source code:**
Policy: VML profile trained on proprietary source code. Web Prevent blocks HTTP POST uploads matching the profile. Proxy returns custom block page to user.

**Example 2 -- Allow but log uploads to approved partners:**
Policy exception for `*.approvedpartner.com` domains. All other uploads with sensitive data are blocked. Uploads to approved partners generate incidents but are allowed through.

**Example 3 -- Content removal for inbound web pages:**
RESPMOD mode. Policy detects SSN patterns in inbound HTML responses. Action: Content Removal -- DLP redacts the SSN patterns from the HTML before the page reaches the user's browser. Original server response is modified.

[S1, S4, S15] Evidence: A

---

## 4. Network Discover Deep Dive

### 4.1 Scan Target Configuration — Per Target Type

#### CIFS File Share Target

```
+=========================================================================+
|  Discover Target: Finance-CIFS                                           |
+=========================================================================+
|  Target Type: File Share (CIFS)                                          |
|                                                                         |
|  Scan Roots:                                                             |
|    \\fileserver01\Finance\Reports                                        |
|    \\fileserver01\Finance\CustomerData                                   |
|    \\fileserver02\Shared\Accounting                                     |
|                                                                         |
|  Include/Exclude Filters:                                                |
|    Include patterns:  [*.xlsx, *.csv, *.pdf, *.docx          ]          |
|    Exclude patterns:  [*.exe, *.dll, *.tmp, *.log            ]          |
|    Exclude paths:     [\Archive\, \Backup\, \Temp\            ]         |
|                                                                         |
|  Credentials:                                                            |
|    Read:    CORP\dlp-scanner (read access to all scan roots)            |
|    Write:   CORP\dlp-remediator (write access for quarantine/encrypt)   |
|                                                                         |
|  Schedule:                                                               |
|    Type:    Recurring                                                    |
|    Cadence: Weekly, Sunday 1:00 AM                                      |
|    Incremental: Enabled                                                  |
|                                                                         |
|  Performance:                                                            |
|    Bandwidth limit (MB/s): [50  ]                                        |
|    Max concurrent files:   [20  ]                                        |
|                                                                         |
+=========================================================================+
```

[S1, S4, S17] Evidence: A

#### SharePoint Target

```
+=========================================================================+
|  Discover Target: HR-SharePoint                                          |
+=========================================================================+
|  Target Type: SharePoint                                                 |
|                                                                         |
|  SharePoint URL:                                                         |
|    https://sharepoint.corp.example.com/sites/HR                         |
|    https://sharepoint.corp.example.com/sites/Compliance                 |
|                                                                         |
|  Authentication:                                                         |
|    Auth type:     [NTLM                                   v]           |
|    Username:      [CORP\dlp-sp-scanner                     ]            |
|    Password:      [********                                 ]            |
|                                                                         |
|  Scan Scope:                                                             |
|    [x] Document libraries                                                |
|    [x] Lists with attachments                                            |
|    [ ] Wiki pages                                                        |
|    [ ] Blog posts                                                        |
|                                                                         |
|  Versioning:                                                             |
|    Scan current version only: (o)                                        |
|    Scan all versions:         ( )                                        |
|                                                                         |
+=========================================================================+
```

[S1, S4] Evidence: A

#### SQL Database Target

```
+=========================================================================+
|  Discover Target: Customer-DB                                            |
+=========================================================================+
|  Target Type: SQL Database                                               |
|                                                                         |
|  Connection:                                                             |
|    JDBC URL:      [jdbc:oracle:thin:@db01.corp:1521:CUSTDB  ]          |
|    Driver:        [Oracle JDBC                             v]           |
|    Username:      [dlp_readonly                              ]          |
|    Password:      [********                                  ]          |
|                                                                         |
|  Scan Scope:                                                             |
|    Tables:        [CUSTOMERS, ORDERS, PAYMENTS               ]          |
|    Columns:       [All columns           v]                             |
|    Row limit:     [1000000] (max rows to scan per table)                |
|    SQL filter:    [WHERE created_date > SYSDATE - 365        ]          |
|                                                                         |
+=========================================================================+
```

[S1, S4] Evidence: A

#### Exchange Mailbox Target

```
+=========================================================================+
|  Discover Target: Exchange-Exec                                          |
+=========================================================================+
|  Target Type: Exchange                                                   |
|                                                                         |
|  Exchange Server:                                                        |
|    EWS URL:       [https://exchange.corp.example.com/EWS     ]          |
|    Auth type:     [NTLM                                    v]           |
|    Username:      [CORP\dlp-exchange-scanner                 ]          |
|    Password:      [********                                  ]          |
|                                                                         |
|  Mailbox Scope:                                                          |
|    Scan type:     (o) Specific mailboxes    ( ) All mailboxes           |
|    Mailboxes:     [ceo@corp.example.com                      ]          |
|                   [cfo@corp.example.com                      ]          |
|                   [coo@corp.example.com                      ]          |
|                                                                         |
|  Folder Scope:                                                           |
|    [x] Inbox                                                             |
|    [x] Sent Items                                                        |
|    [x] Drafts                                                            |
|    [ ] Deleted Items                                                     |
|    [x] Custom folders                                                    |
|                                                                         |
+=========================================================================+
```

[S1, S4] Evidence: A

### 4.2 Discover Scan Tuning

**Reference:** Symantec DLP 15.8 Guidelines for Tuning Network Discover Scans (S17)

| Tuning Parameter | Default | Recommendation | Impact | Evidence |
|------------------|---------|----------------|--------|----------|
| Bandwidth limit | Unlimited | 50-100 MB/s | Prevents network saturation during scans | B [S17] |
| Max concurrent files | 10 | 20-50 | Higher = faster scan; lower = less resource impact | B [S17] |
| File size limit | 500 MB | 200 MB (reduce for faster scans) | Skip very large files that are unlikely to contain DLP-relevant data | B [S17] |
| File age filter | None | Last 365 days | Skip old files for faster initial scans | B [S17] |
| Incremental scanning | Enabled | Always enable after first full scan | Dramatically reduces subsequent scan time | A [S1, S17] |
| Exclude patterns | None | `*.exe, *.dll, *.sys, *.msi, *.cab` | Skip binary executables that rarely contain sensitive text | B [S17] |

[S17] Evidence: B

---

## 5. Network Protect Deep Dive

### 5.1 Protect Action Configuration

```
+=========================================================================+
|  Response Rule: Discover-Quarantine-PCI                                  |
+=========================================================================+
|  Rule Type: Automated Response                                           |
|                                                                         |
|  Conditions:                                                             |
|    [x] Detection server type: Network Discover/Protect                  |
|    [x] Severity: High or Critical                                       |
|                                                                         |
|  Actions:                                                                |
|    Action 1: Discover -- Quarantine File                                |
|      Quarantine path:    [\\dlp-quarantine\PCI\              ]          |
|      Tombstone file:     [x] Replace original with tombstone            |
|      Tombstone content:  [See template below                  ]         |
|      Preserve ACLs:      [x] Copy original ACLs to quarantine          |
|                                                                         |
|    Action 2: All -- Send Email Notification                             |
|      To:    [$DATA_OWNER_EMAIL$                               ]         |
|      Subject: [DLP: File quarantined from $FILE_PATH$         ]         |
|                                                                         |
+=========================================================================+
```

### 5.2 Quarantine Workflow

```
1. Discover scan identifies sensitive file
2. Protect action triggered:
   a. Original file copied to quarantine location
   b. Original file permissions preserved on quarantine copy
   c. Original file DELETED from source location
   d. Tombstone file created in original location
   e. Tombstone contains: original path, policy, date, contact info
3. Incident created in Enforce with quarantine details
4. Data owner notified via email
5. Admin can review quarantined files: Manage > Discover > Quarantined Files
6. Admin can RESTORE file to original location if appropriate

Restore Path:
  Manage > Discover Scanning > Quarantined Files
    > Select file(s)
    > Click "Restore"
    > File copied back to original location
    > Tombstone removed
    > Quarantine copy retained for audit
```

[S1, S4] Evidence: A

---

## 6. SSL/TLS Inspection Reference

### 6.1 SSL Inspection by Server Type

| Server Type | SSL Mode | Certificate Required | Notes | Evidence |
|-------------|----------|---------------------|-------|----------|
| Network Monitor | Passive decryption | Server private key OR SSL-offloading upstream | Cannot MITM; needs access to private key or pre-decrypted traffic | A [S1] |
| Network Prevent for Email | Not applicable | MTA handles SSL/TLS | DLP receives email in cleartext from MTA | A [S1, S13] |
| Network Prevent for Web | Active via proxy | Proxy handles SSL termination; ICAP sees cleartext | Proxy decrypts HTTPS; sends cleartext to DLP via ICAP | A [S1, S15] |

### 6.2 Certificate Management

```
Certificate Store Location:
  Network Monitor:     /opt/dlp/certs/ssl-inspect.jks
  Network Prevent Web: /opt/dlp/keystore/secureicap.jks

Certificate Operations (via API, DLP 16.0 RU2+):
  POST   /certificates       -- Add a custom certificate
  GET    /certificates/{id}  -- Retrieve certificate details
  PUT    /certificates/{id}  -- Update certificate
  DELETE /certificates/{id}  -- Delete certificate
  GET    /certificates/{id}/usage -- View certificate usage
```

**Gotcha:** SSL cipher suite settings MUST match between the Enforce Server and all Detection Servers. A cipher mismatch causes TLS handshake failures and server communication breakdowns. Verify `SSLcipherSuites` configuration on all servers after any SSL-related changes. [V-tribal, gotcha #11]

[S1, S4, API-intelligence] Evidence: A

---

## 7. Performance Sizing Guide

### 7.1 Network Monitor Sizing

| Traffic Volume | CPU Cores | RAM | Disk | NIC | Evidence |
|---------------|-----------|-----|------|-----|----------|
| < 100 Mbps | 4 | 8 GB | 100 GB | 1 Gbps | B [S9] |
| 100-500 Mbps | 8 | 16 GB | 200 GB | 1 Gbps | B [S9] |
| 500 Mbps - 1 Gbps | 16 | 32 GB | 500 GB | 10 Gbps | B [S9] |
| > 1 Gbps | Multiple servers | 64 GB each | 1 TB | 10 Gbps | B [S9] |

### 7.2 Network Prevent for Email Sizing

| Email Volume (msg/hr) | CPU Cores | RAM | Concurrent Connections | Evidence |
|----------------------|-----------|-----|----------------------|----------|
| < 5,000 | 4 | 8 GB | 50 | B [S9] |
| 5,000-20,000 | 8 | 16 GB | 100 | B [S9] |
| 20,000-50,000 | 16 | 32 GB | 200 | B [S9] |
| > 50,000 | Multiple servers | 32 GB each | 200 each | B [S9] |

### 7.3 Network Prevent for Web Sizing

| Concurrent ICAP Conn. | CPU Cores | RAM | Notes | Evidence |
|-----------------------|-----------|-----|-------|----------|
| < 50 | 4 | 8 GB | Small office | B [S9] |
| 50-100 | 8 | 16 GB | Medium enterprise | B [S9] |
| 100-200 | 16 | 32 GB | Large enterprise | B [S9] |
| > 200 | Multiple servers behind LB | 32 GB each | Load balance ICAP connections | B [S9] |

**CRITICAL:** Match concurrent ICAP connections between proxy and Web Prevent server. Mismatched settings cause either connection queueing (too few on DLP side) or resource waste (too many on DLP side). [S9, S15]

### 7.4 Network Discover Sizing

| Storage to Scan | CPU Cores | RAM | Scan Rate | Evidence |
|----------------|-----------|-----|-----------|----------|
| < 1 TB | 4 | 8 GB | ~100 GB/hr (standard) | B [S9, S17] |
| 1-10 TB | 8 | 16 GB | ~100-500 GB/hr | B [S9, S17] |
| 10-50 TB | 16 | 32 GB | Up to 1 TB/hr (High Speed Discovery, 16.0+) | A [S1, S6] |
| > 50 TB | Multiple servers | 32 GB each | Parallel scanning across servers | B [S9] |

[S9, S17] Evidence: B

---

## 8. Multi-Server Topology Patterns

### 8.1 Small Enterprise (< 1000 users)

```
Single Network Monitor + Single Email Prevent + Single Discover:

  Internet
     |
  Firewall
     |
  Core Switch ----SPAN----> Network Monitor
     |
  Mail Server (Exchange/O365 hybrid)
     |
  DLP Email Prevent (reflecting mode)
     |
  Web Proxy (Squid)
     |
  DLP Web Prevent (ICAP)
     |
  File Server
     |
  DLP Discover (weekly scan)
```

### 8.2 Large Enterprise (5000+ users)

```
Multiple regions, high availability:

  Region 1 (US):
    Network Monitor x2 (redundant SPAN)
    Email Prevent x2 (active-passive for MTA integration)
    Web Prevent x2 (load-balanced ICAP)
    Discover x2 (parallel scanning of different targets)

  Region 2 (EU):
    Network Monitor x1
    Email Prevent x1
    Web Prevent x1
    Discover x1

  Central:
    Enforce Server (single, HA with Veritas Cluster Server)
    Oracle Database (RAC for HA)
```

[S1, S4, S9] Evidence: A-B

---

## 9. MTA Integration Reference

### 9.1 Postfix Complete Configuration

```
# /etc/postfix/main.cf

# Route ALL outbound email through DLP
content_filter = smtp:[10.1.50.200]:10025

# Maximum message size to route through DLP
message_size_limit = 52428800  # 50 MB (match DLP max message size)

# Timeout for DLP response
smtp_connect_timeout = 60s
smtp_data_done_timeout = 600s


# /etc/postfix/master.cf

# DLP return path (receive inspected email back)
10026  inet  n  -  n  -  10  smtpd
  -o content_filter=
  -o smtpd_recipient_restrictions=permit_mynetworks,reject
  -o mynetworks=10.1.50.200/32
  -o receive_override_options=no_header_body_checks
```

### 9.2 Sendmail Configuration

```
# /etc/mail/sendmail.mc

# Route through DLP
define(`MAIL_FILTER', `dlp, S=inet:10025@10.1.50.200, F=T, T=C:30s;S:120s;R:120s;E:300s')
INPUT_MAIL_FILTER(`dlp', `S=inet:10025@10.1.50.200, F=T')
```

### 9.3 Fail-Open vs Fail-Closed

| Mode | Behavior when DLP is down | Risk | Evidence |
|------|---------------------------|------|----------|
| Fail-Open | MTA delivers email without DLP inspection | Data loss risk during DLP downtime | A [S1, S13] |
| Fail-Closed | MTA queues email until DLP is back | Email delivery delays during DLP downtime | A [S1, S13] |

**Recommendation:** Use fail-open for production email (email availability is typically more critical than DLP). Monitor DLP server health and alert on downtime. Combine with endpoint DLP for defense-in-depth when network DLP is unavailable.

[S1, S13] Evidence: A

---

## 10. ICAP Integration Reference

### 10.1 Secure ICAP Configuration

```
DLP Server (secureicap configuration):
  Keystore: /opt/dlp/keystore/secureicap.jks
  Keystore type: JKS
  Secure ICAP port: 11344
  TLS versions: TLS 1.2, TLS 1.3

  # Generate keystore:
  keytool -genkeypair -alias secureicap -keyalg RSA -keysize 2048 \
    -keystore /opt/dlp/keystore/secureicap.jks \
    -dname "CN=dlp-webprevent01.corp.example.com"

Proxy Configuration (Blue Coat):
  ICAP URL: icaps://dlp-webprevent01.corp.example.com:11344/reqmod
  Trust DLP server certificate: Import DLP CA cert into ProxySG trust store
```

### 10.2 ICAP Troubleshooting

| Symptom | Cause | Fix | Evidence |
|---------|-------|-----|----------|
| Slow web browsing | Too few ICAP connections on DLP side | Increase concurrent connections to match proxy | A [S9, S15] |
| "502 Bad Gateway" | DLP server unreachable | Check network, firewall, DLP service status | B [S15] |
| ICAP timeout errors | Large file uploads exceed timeout | Increase connection timeout on both proxy and DLP | B [S15] |
| Secure ICAP handshake failure | Certificate mismatch | Verify certificate, keystore, and trust store | B [S15, V-tribal] |

[S1, S15] Evidence: A

---

## 11. Discover Target Types — Full Configuration

### 11.1 Target Type Comparison

| Target | Auth | Read Credentials | Write Credentials | Incremental | High Speed | API | Evidence |
|--------|------|-----------------|-------------------|-------------|------------|-----|----------|
| CIFS | Domain/NTLM | Required | Optional (protect) | Yes | Yes (16.0+) | Yes (25.1+) | A [S1] |
| NFS | UID/GID | Required | Optional | Yes | No | Yes (25.1+) | A [S1] |
| DFS | Domain/NTLM | Required | Optional | Yes | No | Yes (25.1+) | A [S1] |
| SharePoint | NTLM/Kerberos | Required | Optional | Yes | No | Yes (25.1+) | A [S1] |
| Exchange | EWS/NTLM | Required | N/A | Yes | No | Yes (25.1+) | A [S1] |
| SQL DB | JDBC | Required | N/A | No | No | Yes (25.1+) | A [S1] |
| Lotus Notes | Notes API | Required | N/A | Yes | No | Likely | A [S1] |
| Local FS | OS local | Required | Optional | Yes | Yes (16.0+) | Yes (25.1+) | A [S1] |

[S1, S4, API-intelligence] Evidence: A

---

## 12. API Integration for Network DLP

### 12.1 Network Discover Target API (DLP 25.1+)

```
# List all Discover targets
GET https://<enforce>/ProtectManager/webservices/v2/discover/targets
Authorization: Basic <base64(user:pass)>

# Create a new Discover target
POST https://<enforce>/ProtectManager/webservices/v2/discover/targets
Content-Type: application/json
{
  "targetName": "Finance-CIFS-Weekly",
  "targetType": "FILE_SHARE",
  "scanRoots": ["\\\\fileserver01\\Finance\\"],
  "credentials": {
    "readUsername": "CORP\\dlp-scanner",
    "readPassword": "***"
  },
  "schedule": {
    "type": "RECURRING",
    "cadence": "WEEKLY",
    "dayOfWeek": "SUNDAY",
    "time": "02:00"
  },
  "incremental": true,
  "policyGroupId": 1
}

# Update a Discover target
PUT https://<enforce>/ProtectManager/webservices/v2/discover/targets/123
Content-Type: application/json
{
  "scanRoots": ["\\\\fileserver01\\Finance\\", "\\\\fileserver02\\Accounting\\"]
}

# Delete a Discover target
DELETE https://<enforce>/ProtectManager/webservices/v2/discover/targets/123
```

### 12.2 Network Incident Query via API

```
# Query network incidents by protocol
POST https://<enforce>/ProtectManager/webservices/v2/incidents
Content-Type: application/json
{
  "savedReportId": 12345,
  "incidentCreationDateGreaterThan": "2025-01-01T00:00:00.000Z"
}

Network-specific incident fields:
  - protocol: SMTP, HTTP, FTP
  - sender: email sender address
  - recipients: email recipient addresses
  - subject: email subject line
  - sourceIp: source IP of network traffic
  - destinationIp: destination IP
  - url: web URL (for HTTP incidents)
  - fileOwner: file owner (for Discover incidents)
  - filePath: file path (for Discover incidents)
```

### 12.3 API Gaps for Network DLP

| Operation | API | Workaround |
|-----------|-----|-----------|
| List network incidents | YES | Incident API with protocol filter |
| Manage Discover targets | YES (25.1+) | Full CRUD |
| Configure Network Monitor | NO | Console only |
| Configure Email Prevent | NO | Console + MTA config files |
| Configure Web Prevent | NO | Console + ICAP config files |
| Start/stop Discover scan | NO | Console only |
| Manage quarantined files | NO | Console only |

[API-intelligence] Evidence: A

---

## Summary

This advanced reference covers every network detection server type's configuration, MTA integration patterns (Postfix, Exchange, SMG), ICAP proxy integration (Blue Coat, Squid), Discover target types (CIFS, SharePoint, SQL, Exchange), SSL/TLS inspection, performance sizing, multi-server topologies, and API integration. Network DLP is the broadest enforcement layer in terms of infrastructure integration, requiring coordination with network, email, web proxy, and storage teams.

[S1, S4, S9, S13, S14, S15, S17, API-intelligence] Evidence: A
