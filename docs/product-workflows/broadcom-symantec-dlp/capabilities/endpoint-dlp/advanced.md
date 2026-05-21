# Endpoint DLP — Advanced Reference
## Broadcom Symantec DLP (Enforce Server, version 16.x/25.x/26.x)

> **Purpose:** Complete field reference for every endpoint channel's config screens, ASCII UI diagrams, per-channel examples, advanced agent configuration scenarios, and API integration patterns.
> **Evidence sources:** doc-corpus.md [S1-S28], video-intelligence.md [V1-V45], api-intelligence.md

---

## Table of Contents

1. [Per-Channel Configuration Reference](#1-per-channel-configuration-reference)
2. [Advanced Agent Configuration Screens](#2-advanced-agent-configuration-screens)
3. [Agent Deployment Scenarios](#3-agent-deployment-scenarios)
4. [Endpoint Response Rule Deep Dive](#4-endpoint-response-rule-deep-dive)
5. [Endpoint Discover (Data-at-Rest) Deep Dive](#5-endpoint-discover-data-at-rest-deep-dive)
6. [Browser Integration Architecture](#6-browser-integration-architecture)
7. [Offline Enforcement Model](#7-offline-enforcement-model)
8. [Agent Group Strategy Patterns](#8-agent-group-strategy-patterns)
9. [Performance Tuning Reference](#9-performance-tuning-reference)
10. [FlexResponse on Endpoints](#10-flexresponse-on-endpoints)
11. [API Integration for Endpoint Incidents](#11-api-integration-for-endpoint-incidents)
12. [End-to-End Enterprise Scenario](#12-end-to-end-enterprise-scenario)

---

## 1. Per-Channel Configuration Reference

### 1.1 Email Channel — Full Field Reference

**Navigation:** System > Agents > Agent Configuration > [config] > Channels > Email

```
+=========================================================================+
|  Agent Configuration: Finance-Strict                                     |
+=========================================================================+
|  [General] [Channels] [Advanced] [Notifications]                [Save]  |
+-------------------------------------------------------------------------+
|  Channels > Email                                                       |
+-------------------------------------------------------------------------+
|                                                                         |
|  Enable Outlook Monitoring:    [x] Enabled                              |
|  Enable Lotus Notes Monitoring: [ ] Disabled (Windows only)             |
|                                                                         |
|  Outlook Settings:                                                       |
|    Monitor Mode:               (o) Monitor and Prevent                   |
|                                ( ) Monitor Only                          |
|    Content to scan:                                                      |
|      [x] Subject line                                                    |
|      [x] Message body                                                    |
|      [x] Attachments                                                     |
|      [x] Embedded images                                                |
|    Max attachment size (MB):   [50   ]                                   |
|    Scan recipients:            [x] TO    [x] CC    [x] BCC             |
|                                                                         |
|  Corporate vs Personal Email Detection:                                  |
|    Detect personal email:      [x] (webmail via browser channel)        |
|    Corporate email domains:    [corp.example.com                  ]     |
|                                [subsidiary.example.com             ]     |
|    Personal indicators:        [gmail.com, yahoo.com, hotmail.com  ]    |
|                                                                         |
|  Outlook Add-in Settings:                                                |
|    Display toolbar icon:       [x]                                       |
|    Scan on Send:               [x] (scan when user clicks Send)         |
|    Pre-Send check:             [x] (lightweight check before full scan) |
|                                                                         |
+=========================================================================+
```

| Field | Type | Default | Description | API | Evidence |
|-------|------|---------|-------------|-----|----------|
| Enable Outlook Monitoring | Checkbox | Enabled | Master toggle for Outlook email DLP | GAP | A [S1, S4] |
| Enable Lotus Notes | Checkbox | Disabled | Windows-only Lotus Notes monitoring | GAP | A [S1] |
| Monitor Mode | Radio | Monitor and Prevent | Monitor Only = incidents without blocking; M&P = full enforcement | GAP | A [S1, S4] |
| Subject line | Checkbox | Enabled | Scan email subject for policy matches | GAP | A [S1] |
| Message body | Checkbox | Enabled | Scan email body text and HTML | GAP | A [S1] |
| Attachments | Checkbox | Enabled | Scan email attachments (binary signature + content) | GAP | A [S1] |
| Embedded images | Checkbox | Enabled | OCR-scan embedded images (requires OCR enabled) | GAP | A [S1] |
| Max attachment size | Number (MB) | 50 | Skip attachments larger than this | GAP | A [S1] |
| Detect personal email | Checkbox | Disabled | Flag emails to personal domains (DLP 16.1+) | GAP | A [S6] |
| Corporate email domains | Text list | Empty | Domains considered corporate (internal) | GAP | A [S6] |
| Scan on Send | Checkbox | Enabled | Full DLP scan triggered when user clicks Send | GAP | A [S1] |
| Pre-Send check | Checkbox | Enabled | Lightweight pre-check for faster user experience | GAP | B [S1] |

**Example 1 -- Detect personal email forwarding of corporate data:**
Configure "Detect personal email" with corporate domains `corp.example.com`. When a user sends an email from Outlook to `jsmith@gmail.com` containing 5+ SSNs, the policy triggers with the additional context that the recipient is a personal email address. This context is captured in the incident for investigation. [S6]

**Example 2 -- Large attachment handling:**
Set max attachment size to 100 MB for engineering groups who regularly email large CAD files. Files above 100 MB pass through without scanning. Combine with Network Prevent for Email (which scans the same attachment at the MTA level) for defense-in-depth.

**Example 3 -- Lotus Notes integration (legacy):**
For organizations still using Lotus Notes, enable the Notes add-in. This installs a Notes plug-in that intercepts email composition. Note: Lotus Notes monitoring is Windows-only and being deprecated in favor of modern email clients.

**Example 4 -- Outlook add-in toolbar:**
When Display toolbar icon is enabled, users see a small DLP icon in the Outlook toolbar. This serves as a visual reminder that DLP is active and can display the last scan result when clicked.

[S1, S4, S6, V12, V23] Evidence: A

---

### 1.2 Web/HTTP(S) Channel — Full Field Reference

**Navigation:** System > Agents > Agent Configuration > [config] > Channels > Web/HTTP(S)

```
+=========================================================================+
|  Channels > Web/HTTP(S) -- Detailed Configuration                        |
+=========================================================================+
|                                                                         |
|  Enable Web Monitoring:        [x] Enabled                              |
|  Monitor Mode:                 (o) Monitor and Prevent                   |
|                                ( ) Monitor Only                          |
|                                                                         |
|  Browser Support:                                                        |
|  +-------------------------------------------------------------------+ |
|  | Browser          | Method                | Status      | Version  | |
|  |------------------|-----------------------|-------------|----------| |
|  | Google Chrome    | Content Analysis Conn.| [x] Enabled | 16.0+   | |
|  | Microsoft Edge   | Content Analysis Conn.| [x] Enabled | 16.0+   | |
|  | Mozilla Firefox  | Content Analysis Conn.| [x] Enabled | 16.0.1+ | |
|  | Internet Explorer| Native agent hook     | [x] Enabled | Legacy   | |
|  +-------------------------------------------------------------------+ |
|                                                                         |
|  HTTPS Inspection:                                                       |
|    Enable HTTPS decryption:    [x]                                       |
|    Certificate source:         [Agent-managed certificate     v]        |
|    Certificate auto-install:   [x] (install to browser cert store)      |
|                                                                         |
|  URL Filtering:                                                          |
|    Whitelisted domains:                                                  |
|      [corporate-intranet.example.com                            ]       |
|      [*.example.com                                              ]       |
|      [*.microsoft.com                                            ]       |
|      [+ Add Domain]                                                      |
|    Blacklisted domains (always scan):                                    |
|      [*.personal-cloud.com                                       ]       |
|      [chat.openai.com                                            ]       |
|      [+ Add Domain]                                                      |
|                                                                         |
|  Cloud Application Detection:                                            |
|    Enable cloud app recognition:  [x]                                    |
|    Known cloud apps monitored:                                           |
|      [x] Google Drive          [x] Dropbox                              |
|      [x] Box                   [x] OneDrive (personal)                  |
|      [x] iCloud Drive          [x] WeTransfer                           |
|      [x] Slack (file upload)   [x] ChatGPT / Generative AI             |
|                                                                         |
|  Upload Scanning:                                                        |
|    Max upload scan size (MB):  [100]                                     |
|    Scan timeout (seconds):     [30 ]                                     |
|    Scan multipart form data:   [x]                                       |
|    Scan HTTP PUT uploads:      [x]                                       |
|    Scan WebSocket data:        [ ] (performance-intensive)              |
|                                                                         |
+=========================================================================+
```

| Field | Type | Default | Description | API | Evidence |
|-------|------|---------|-------------|-----|----------|
| Browser Integration | Per-browser toggles | Chrome + Edge enabled | Content analysis connectors per browser | GAP | A [S1, S6] |
| HTTPS decryption | Checkbox | Enabled | Decrypt HTTPS for content inspection | GAP | A [S1] |
| Certificate auto-install | Checkbox | Enabled | Auto-install DLP certificate to browser store | GAP | A [S1] |
| Whitelisted domains | Text list | Empty | Domains exempt from DLP scanning | GAP | A [S1] |
| Blacklisted domains | Text list | Empty | Domains always scanned (priority over whitelist) | GAP | B [S1] |
| Cloud app recognition | Checkbox | Enabled | Identify uploads to known SaaS apps | GAP | A [S1, S4] |
| Max upload scan size | Number (MB) | 100 | Skip uploads larger than this | GAP | A [S1] |
| Scan timeout | Seconds | 30 | Abort scan after timeout (user sees brief delay) | GAP | A [S1] |
| Scan multipart form | Checkbox | Enabled | Inspect multipart/form-data uploads | GAP | A [S1] |

**Example 1 -- Generative AI protection:**
Enable cloud app recognition for "ChatGPT / Generative AI." Create a policy with VML profile trained on proprietary source code and confidential documents. When a developer pastes code into ChatGPT via Chrome, the content analysis connector intercepts the upload, DLP scans the content, and a User Cancel action prompts: "You are about to submit content to an AI service that matches our source code protection policy. Provide justification to proceed." [V35, V36]

**Example 2 -- Differentiate corporate vs personal OneDrive:**
Whitelist `*.sharepoint.com` (corporate OneDrive/SharePoint tenant). Leave personal OneDrive (`onedrive.live.com`) unwhitelisted. Policy triggers only when sensitive data is uploaded to personal OneDrive, not corporate. [S1]

**Example 3 -- WeTransfer large file monitoring:**
Create a web upload policy that triggers when files > 10 MB are uploaded to WeTransfer containing any EDM-matched customer data. Response: Block with notification redirecting user to the corporate secure file transfer solution.

**Example 4 -- WebSocket monitoring caution:**
WebSocket scanning is disabled by default because it monitors persistent connections and generates high CPU load. Enable only if you have a specific use case (e.g., real-time chat app data loss) and test thoroughly on representative endpoints first. [KB176182]

[S1, S4, S6, V35, V36] Evidence: A

---

### 1.3 Removable Storage Channel — Full Field Reference

**Navigation:** System > Agents > Agent Configuration > [config] > Channels > Removable Storage

```
+=========================================================================+
|  Channels > Removable Storage -- Detailed Configuration                  |
+=========================================================================+
|                                                                         |
|  Enable Removable Storage:     [x] Enabled                              |
|  Monitor Mode:                 (o) Monitor and Prevent                   |
|                                ( ) Monitor Only                          |
|                                                                         |
|  Device Policy:                                                          |
|    (o) Content-aware: scan files, apply DLP policies                    |
|    ( ) Full block: block ALL removable device access (no scanning)      |
|                                                                         |
|  Device Whitelist:                                                       |
|  +-------------------------------------------------------------------+ |
|  | # | Vendor ID | Product ID | Serial       | Description           | |
|  |---|-----------|------------|--------------|----------------------| |
|  | 1 | 0951      | 1666       | *            | Kingston IronKey     | |
|  | 2 | 0781      | 5583       | AA00012345   | Corp SanDisk #123    | |
|  | 3 | 13FE      | 4200       | *            | Patriot Encrypted    | |
|  +-------------------------------------------------------------------+ |
|  [+ Add Device]  [Import from CSV]  [Clear All]                         |
|                                                                         |
|  File Operations:                                                        |
|    Monitor file WRITE to USB:  [x]                                       |
|    Monitor file READ from USB: [ ]                                       |
|    Monitor file DELETE on USB: [ ]                                       |
|                                                                         |
|  File Type Filtering:                                                    |
|    Scan all file types:        (o)                                       |
|    Scan specific types only:   ( )                                       |
|      [ ] Office documents      [ ] PDFs                                 |
|      [ ] Executables           [ ] Archives (zip, rar)                  |
|      [ ] Source code           [ ] Database exports                     |
|                                                                         |
|  Size Limits:                                                            |
|    Max file size to scan (MB): [200]                                     |
|    Min file size to scan (KB): [1  ]                                     |
|                                                                         |
|  Encryption Integration:                                                 |
|    Auto-encrypt on write:      [x]                                       |
|    Encryption provider:        [Symantec Endpoint Encryption  v]        |
|    Fallback if encrypt fails:  [Block                          v]       |
|                                                                         |
+=========================================================================+
```

| Field | Type | Default | Description | API | Evidence |
|-------|------|---------|-------------|-----|----------|
| Device Policy | Radio | Content-aware | Content-aware = scan + policy; Full block = block all USB | GAP | A [S1, S4] |
| Device Whitelist | Table | Empty | Exempt specific devices by VID/PID/Serial | GAP | A [S1, S4] |
| Import from CSV | Button | N/A | Bulk import device whitelist from CSV file | GAP | B [S1] |
| Monitor file WRITE | Checkbox | Enabled | Scan files being written to USB | GAP | A [S1] |
| Monitor file READ | Checkbox | Disabled | Scan files being read from USB (data import tracking) | GAP | B [S1] |
| File Type Filtering | Radio + checkboxes | All types | Restrict scanning to specific file types for performance | GAP | A [S1] |
| Max file size | Number (MB) | 200 | Skip files larger than this | GAP | A [S1] |
| Auto-encrypt on write | Checkbox | Disabled | Encrypt files written to USB | GAP | A [S1, S4] |
| Fallback if encrypt fails | Dropdown | Block | What to do if encryption fails (Block or Allow) | GAP | A [S1] |

**Example 1 -- Tiered USB policy by department:**
- **Finance**: Full block on all non-whitelisted USB devices. Whitelisted corporate IronKey drives require content scanning -- PCI data is encrypted before write.
- **Engineering**: Content-aware mode. Monitor file writes to USB. Block only if VML source code profile matches. Allow all other data.
- **Executives**: Monitor only. All USB writes generate incidents but are never blocked.

**Example 2 -- USB device inventory via read monitoring:**
Enable "Monitor file READ" on a pilot group to discover what data employees are bringing into the organization via USB. Incidents show files read from USB that match DLP policies, revealing data import patterns. This is typically used during a risk assessment phase, not ongoing monitoring. [S1]

**Example 3 -- Encrypted USB with fallback blocking:**
Enable auto-encrypt with Symantec Endpoint Encryption. If the encryption engine fails (e.g., agent corruption, license issue), the fallback action is "Block" -- preventing unencrypted sensitive data from reaching the USB. This ensures no data loss even in degraded mode. [S1]

**Example 4 -- CSV bulk import of approved devices:**
For organizations with 100+ approved USB devices, create a CSV file with columns: VendorID, ProductID, SerialNumber, Description. Import via the "Import from CSV" button. CSV format:
```csv
VendorID,ProductID,SerialNumber,Description
0951,1666,*,Kingston IronKey (all serials)
0781,5583,AA00012345,Corp SanDisk Unit 123
0781,5583,AA00012346,Corp SanDisk Unit 124
```

**Example 5 -- Block executables on USB but allow documents:**
Set File Type Filtering to "Scan specific types only" and select "Executables" and "Archives." Create a policy that blocks ALL executables and archives written to USB (regardless of content). This prevents malware distribution via USB while allowing regular document sharing. Combine with content-aware policy for document DLP. [S1]

[S1, S4, V12, V23] Evidence: A

---

### 1.4 Clipboard Channel — Full Field Reference

**Navigation:** System > Agents > Agent Configuration > [config] > Channels > Clipboard

```
+=========================================================================+
|  Channels > Clipboard -- Detailed Configuration                          |
+=========================================================================+
|                                                                         |
|  Enable Clipboard Monitoring:   [x] Enabled                             |
|                                                                         |
|  Monitoring Scope:                                                       |
|    [x] Cross-application paste (source != target app)                   |
|    [ ] Same-application paste (source == target app)                    |
|                                                                         |
|  Application Filtering:                                                  |
|    Source application filter:                                            |
|      (o) All applications                                                |
|      ( ) Specific applications:                                          |
|          [ssms.exe       ] (SQL Server Management Studio)               |
|          [toad.exe       ] (Toad for Oracle)                            |
|          [excel.exe      ] (Microsoft Excel)                            |
|                                                                         |
|    Target application filter:                                            |
|      ( ) All applications                                                |
|      (o) Specific applications:                                          |
|          [chrome.exe     ] (Google Chrome)                               |
|          [slack.exe      ] (Slack)                                       |
|          [teams.exe      ] (Microsoft Teams)                            |
|          [outlook.exe    ] (Outlook)                                     |
|                                                                         |
|  Content Thresholds:                                                     |
|    Min clipboard size (chars): [50  ] (ignore small copies)             |
|    Max clipboard size (KB):    [1024] (skip very large copies)          |
|                                                                         |
+=========================================================================+
```

| Field | Type | Default | Description | API | Evidence |
|-------|------|---------|-------------|-----|----------|
| Cross-application paste | Checkbox | Enabled | Monitor paste between different applications | GAP | A [S1] |
| Same-application paste | Checkbox | Disabled | Monitor paste within same application | GAP | A [S1] |
| Source application filter | Radio + list | All | Restrict source apps to monitor | GAP | A [S1] |
| Target application filter | Radio + list | All | Restrict target apps to monitor | GAP | A [S1] |
| Min clipboard size | Number (chars) | 50 | Ignore clipboard operations below this size | GAP | B [S1] |
| Max clipboard size | Number (KB) | 1024 | Skip very large clipboard operations | GAP | B [S1] |

**Example 1 -- Database to browser exfiltration detection:**
Source filter: `ssms.exe`, `toad.exe`, `pgadmin4.exe` (database tools). Target filter: `chrome.exe`, `msedge.exe`, `firefox.exe` (browsers). This catches the specific pattern of copying query results from a database tool and pasting into a web form (webmail, cloud storage upload, etc.) while ignoring clipboard operations between productivity apps. [S1]

**Example 2 -- Minimum size filter to reduce noise:**
Set min clipboard size to 100 characters. Single words, short phrases, and file paths are ignored. Only bulk data copies (tabular data, document fragments) are scanned. This dramatically reduces clipboard event volume while catching meaningful data exfiltration attempts. [S1]

**Example 3 -- Block paste to messaging apps:**
Target filter: `slack.exe`, `teams.exe`, `discord.exe`. Policy: EDM profile matching customer PII. When an employee copies customer records from any source and pastes into a messaging app, the paste is blocked. Paste to other applications (Word, Excel) is allowed. [S1]

[S1, S4] Evidence: A

---

### 1.5 Print Channel — Full Field Reference

**Navigation:** System > Agents > Agent Configuration > [config] > Channels > Print

```
+=========================================================================+
|  Channels > Print -- Detailed Configuration                              |
+=========================================================================+
|                                                                         |
|  Enable Print Monitoring:      [x] Enabled                              |
|  Monitor Mode:                 (o) Monitor and Prevent                   |
|                                ( ) Monitor Only                          |
|                                                                         |
|  Printer Type Monitoring:                                                |
|    [x] Local printers (directly connected)                              |
|    [x] Network printers (shared/queue-based)                            |
|    [x] Virtual printers (PDF print drivers)                             |
|    [x] Fax devices (Windows only)                                       |
|                                                                         |
|  Printer Whitelist (exempt from DLP):                                    |
|    Printer 1: [\\printserver\HR-Secure-Printer          ]              |
|    Printer 2: [\\printserver\Legal-Secure-Printer        ]              |
|    Printer 3: [Local: HP LaserJet in Badge-Access Room   ]              |
|    [+ Add Printer]                                                       |
|                                                                         |
|  Advanced:                                                               |
|    Scan print spool data:      [x]                                       |
|    Capture print content:      [x] (store content in incident)          |
|    Max pages to scan:          [100]                                     |
|                                                                         |
+=========================================================================+
```

**Example 1 -- Detect bulk PII printing for investigation:**
Policy triggers when a single print job contains 50+ SSN matches. Response: Notify user + set incident severity to Critical + log to SIEM. This catches intentional bulk data printing (an employee printing the entire customer database before leaving the company). [S1]

**Example 2 -- Block printing of documents with MIP "Highly Confidential" label:**
Policy uses "Content Matches MIP Tag Rule" condition for "Highly Confidential" label. Response: Block print job. Exception: Whitelisted printer `\\printserver\Legal-Secure-Printer` in the physically secured legal department print room. [S1, S2]

**Example 3 -- Virtual printer (PDF) monitoring:**
Virtual printers (e.g., Microsoft Print to PDF, CutePDF) are monitored to detect "print to PDF" as a data extraction technique. An employee might print a confidential document to PDF and then email or upload the PDF. The print channel catches the initial PDF creation; the email/web channels catch the subsequent distribution. [S1]

[S1, S4] Evidence: A

---

### 1.6 Screen Capture Channel — Full Field Reference

```
+=========================================================================+
|  Channels > Screen Capture -- Detailed Configuration                     |
+=========================================================================+
|                                                                         |
|  Enable Screen Capture:        [x] Enabled                              |
|  Monitor Mode:                 (o) Monitor Only                          |
|                                ( ) Monitor and Prevent                   |
|                                                                         |
|  Capture Methods Monitored:                                              |
|    [x] PrintScreen key (PrtScn, Alt+PrtScn)                            |
|    [x] Snipping Tool / Snip & Sketch                                   |
|    [x] Third-party capture tools (SnagIt, Greenshot, etc.)             |
|    [ ] Video recording tools (OBS, Camtasia)                            |
|                                                                         |
|  Application Scope:                                                      |
|    (o) All foreground applications                                       |
|    ( ) Specific applications only:                                       |
|        [sap.exe          ]                                               |
|        [oracle.exe       ]                                               |
|                                                                         |
+=========================================================================+
```

**Limitation:** Screen capture monitoring is documented as "Partial" on Windows. Known limitations include:
- Multi-monitor setups may not detect captures on secondary monitors
- Some modern screen recording tools bypass the monitored API hooks
- macOS is not supported for screen capture monitoring
- Video recording tool monitoring is experimental

**Example -- Monitor screenshots of financial applications:**
Enable screen capture monitoring scoped to `sap.exe` and `oracle.exe`. When a user takes a screenshot while SAP is the foreground application and the visible content matches EDM financial data profile, an incident is created. Monitor-only mode is recommended (blocking screenshots reliably is technically challenging). [S1]

[S1, S4] Evidence: B

---

### 1.7 Network Share Channel — Full Field Reference

```
+=========================================================================+
|  Channels > Network Share -- Detailed Configuration                      |
+=========================================================================+
|                                                                         |
|  Enable Network Share Monitoring: [x] Enabled                           |
|  Monitor Mode:                 (o) Monitor and Prevent                   |
|                                ( ) Monitor Only                          |
|                                                                         |
|  Share Whitelist (exempt):                                               |
|    [\\fileserver\Public\                                        ]       |
|    [\\dfs\CompanyWide\Templates\                                ]       |
|    [+ Add Share]                                                         |
|                                                                         |
|  Share Blacklist (always scan):                                          |
|    [\\personalNAS\*                                             ]       |
|    [+ Add Share]                                                         |
|                                                                         |
|  Operations Monitored:                                                   |
|    [x] File copy to network share                                        |
|    [x] File move to network share                                        |
|    [ ] File open from network share (read access)                       |
|                                                                         |
+=========================================================================+
```

**Example 1 -- Block sensitive data copies to personal NAS devices:**
Policy detects EDM customer data match on file copy to any share matching `\\personalNAS\*` or non-corporate share paths. Response: Block. [S1]

**Example 2 -- Monitor department-to-department data sharing:**
Policy detects when Finance department users copy files containing financial report IDM profiles to Engineering department shares. No blocking -- generates incident for awareness of cross-department sensitive data movement. [S1]

[S1, S4] Evidence: A

---

### 1.8 Cloud File Sync Channel — Full Field Reference

```
+=========================================================================+
|  Channels > Cloud File Sync -- Detailed Configuration                    |
+=========================================================================+
|                                                                         |
|  Enable Cloud Sync Monitoring:  [x] Enabled                             |
|  Monitor Mode:                  (o) Monitor and Prevent                  |
|                                 ( ) Monitor Only                         |
|                                                                         |
|  Sync Client Detection:                                                  |
|  +-------------------------------------------------------------------+ |
|  | Service          | Sync Folder Path          | Status              | |
|  |------------------|---------------------------|--------------------| |
|  | Box Sync         | C:\Users\*\Box Sync\      | [x] Monitor        | |
|  | Dropbox          | C:\Users\*\Dropbox\        | [x] Monitor        | |
|  | Google Drive     | C:\Users\*\Google Drive\   | [x] Monitor        | |
|  | OneDrive Personal| C:\Users\*\OneDrive\       | [x] Monitor        | |
|  | OneDrive Business| C:\Users\*\OneDrive - Corp\| [ ] Exempt         | |
|  | iCloud Drive     | C:\Users\*\iCloudDrive\    | [x] Monitor        | |
|  +-------------------------------------------------------------------+ |
|                                                                         |
|  Custom Sync Paths:                                                      |
|    [C:\Users\*\CustomCloud\                                      ]      |
|    [+ Add Path]                                                          |
|                                                                         |
+=========================================================================+
```

**Example 1 -- Corporate OneDrive exempt, personal blocked:**
Configure OneDrive Business (identified by sync folder path `OneDrive - Corp`) as exempt. Personal OneDrive, Dropbox, Google Drive, and Box are monitored with content-aware policies. Sensitive data to personal cloud = Block. Non-sensitive data = Allow. [S1]

**Example 2 -- Custom cloud app sync folder:**
Your organization uses a custom cloud storage solution with a sync client that syncs to `C:\Users\*\AcmeCloud\`. Add this path as a custom sync path. DLP monitors files placed in this folder just like any other cloud sync client. [S1]

[S1, S4] Evidence: A

---

### 1.9 CD/DVD and FTP Channels

These channels have simpler configurations.

**CD/DVD:**
```
Enable CD/DVD Monitoring: [x] Enabled
Monitor Mode: Monitor and Prevent
```
Monitors all burn operations. No device whitelisting (unlike USB). Windows only.

**FTP:**
```
Enable FTP Monitoring: [x] Enabled
Monitor Mode: Monitor and Prevent
FTP Applications Monitored: All FTP clients
```
Monitors file uploads via FTP protocol from any FTP client. Windows only.

[S1, S4] Evidence: A

---

## 2. Advanced Agent Configuration Screens

### 2.1 Advanced Settings Tab

**Navigation:** System > Agents > Agent Configuration > [config] > Advanced

```
+=========================================================================+
|  Agent Configuration > Advanced                                          |
+=========================================================================+
|                                                                         |
|  Agent Communication:                                                    |
|    Polling interval (min):       [15  ]                                  |
|    Heartbeat interval (min):     [60  ]                                  |
|    Connection timeout (sec):     [30  ]                                  |
|    Retry attempts:               [3   ]                                  |
|    Retry delay (sec):            [60  ]                                  |
|                                                                         |
|  Content Processing:                                                     |
|    Max file processing time (s): [120 ] (per-file scan timeout)         |
|    Max archive depth:            [5   ] (nested zip/rar levels)         |
|    Max extracted archive size:   [500 ] (MB)                            |
|    Enable OCR on endpoint:       [x]                                     |
|    OCR languages:                [English, Spanish, French       v]     |
|                                                                         |
|  Tamper Protection:                                                      |
|    Prevent agent uninstall:      [x] (requires admin password)          |
|    Prevent agent stop:           [x] (blocks Stop service action)       |
|    Admin password:               [********                       ]      |
|                                                                         |
|  Logging:                                                                |
|    Agent log level:              [Warning                        v]     |
|    Max log file size (MB):       [50  ]                                  |
|    Log rotation count:           [5   ]                                  |
|                                                                         |
|  Windows-Specific:                                                       |
|    HVCI compatibility (16.0+):   [x] (Windows 11 HVCI support)         |
|    LSA Protection support (25.1):[x] (Windows 11 LSA Protection)        |
|    Virtual Desktop support (26.1):[x] (VDI/App-V compatibility)         |
|                                                                         |
+=========================================================================+
```

| Field | Type | Default | Description | Evidence |
|-------|------|---------|-------------|----------|
| Polling interval | Minutes | 15 | Policy update check frequency | A [S1, S4] |
| Max file processing time | Seconds | 120 | Per-file DLP scan timeout | A [S1] |
| Max archive depth | Number | 5 | How deep to scan nested archives (zip-in-zip) | A [S1] |
| Enable OCR on endpoint | Checkbox | Disabled | Endpoint-level OCR for images/scanned PDFs | A [S1] |
| Prevent agent uninstall | Checkbox | Enabled | Requires admin password for uninstall | A [S1] |
| HVCI compatibility | Checkbox | Enabled | Windows 11 Hypervisor-protected Code Integrity | A [S1] |
| LSA Protection | Checkbox | Enabled | Windows 11 LSA Protection support (DLP 25.1+) | A [S2] |
| Virtual Desktop support | Checkbox | Disabled | VDI/Virtual App compatibility (DLP 26.1+) | A [S3] |

[S1, S2, S3, S4] Evidence: A

---

### 2.2 Notification Templates

**Navigation:** System > Agents > Agent Configuration > [config] > Notifications

```
+=========================================================================+
|  Agent Configuration > Notifications                                     |
+=========================================================================+
|                                                                         |
|  Block Notification Template:                                            |
|  +-------------------------------------------------------------------+ |
|  | <div style="font-family: Segoe UI; font-size: 14px;">             | |
|  |   <h3>Data Transfer Blocked</h3>                                  | |
|  |   <p>Your $ACTION_TYPE$ was blocked because the content           | |
|  |   matches policy: <b>$POLICY_NAME$</b></p>                        | |
|  |   <p>File: $FILE_NAME$</p>                                        | |
|  |   <p>Contact: dlp-support@corp.example.com</p>                    | |
|  | </div>                                                             | |
|  +-------------------------------------------------------------------+ |
|                                                                         |
|  Available Variables:                                                    |
|    $POLICY_NAME$     -- Name of the matched policy                      |
|    $ACTION_TYPE$     -- Type of action (copy, email, print, etc.)       |
|    $FILE_NAME$       -- Name of the file involved                        |
|    $MATCH_COUNT$     -- Number of policy matches found                   |
|    $SEVERITY$        -- Incident severity level                          |
|    $USER_NAME$       -- Currently logged-in user                         |
|    $HOSTNAME$        -- Machine hostname                                 |
|                                                                         |
|  Localization:                                                           |
|    Default language:           [English                          v]     |
|    Additional languages:       [x] Spanish  [x] French  [ ] German     |
|                                                                         |
|  User Cancel Template:                                                   |
|  +-------------------------------------------------------------------+ |
|  | <h3>Sensitive Data Detected</h3>                                   | |
|  | <p>Please provide a business justification to proceed.</p>        | |
|  | <p>Timeout: $TIMEOUT$ seconds</p>                                  | |
|  +-------------------------------------------------------------------+ |
|                                                                         |
+=========================================================================+
```

**Example -- Multi-language notification:**
For a global deployment, configure notifications in English (default), Spanish, and French. The agent detects the Windows locale and displays the notification in the user's language. If the locale does not match any configured language, English is used as fallback. [KB159522]

[S1, KB159522] Evidence: A-B

---

## 3. Agent Deployment Scenarios

### 3.1 Enterprise GPO Deployment (1000+ endpoints)

```
Phase 1 (Week 1): Deploy to IT department (50 agents)
  - Validate agent installation, registration, policy download
  - Test all channels with sample sensitive data
  - Identify and resolve firewall/proxy issues

Phase 2 (Week 2-3): Deploy to Finance + Legal (200 agents)
  - Use "Finance-Strict" and "Legal-Strict" agent configurations
  - Monitor-only mode for first week
  - Enable blocking in week 3 after false positive tuning

Phase 3 (Week 4-6): Deploy to all remaining departments (750 agents)
  - Use "Default" agent configuration
  - Stagger GPO deployment across OUs (200/day)
  - Monitor server load on Endpoint Prevent Server

Phase 4 (Ongoing): Continuous monitoring and tuning
  - Weekly false positive review
  - Monthly policy refinement
  - Quarterly agent group optimization
```

[V-tribal, KB173958] Evidence: B

### 3.2 Remote Workforce Deployment

```
Architecture:
  Corporate LAN agents -> LAN Endpoint Servers (primary)
  Remote/VPN agents -> DMZ Endpoint Servers via load balancer

Load Balancer Configuration:
  - VIP: dlp-endpoint.corp.example.com:443
  - Backend: dlp-eps-dmz01:443, dlp-eps-dmz02:443
  - Persistence: Source IP, timeout 24 hours
  - Health check: TCP port 443

Agent Package:
  - FQDN: dlp-endpoint.corp.example.com (load balancer VIP)
  - Agents on VPN resolve FQDN to load balancer
  - Agents on LAN also resolve to same VIP (or separate LAN package)

Offline Behavior:
  - Remote agents may go offline (no VPN for hours/days)
  - Cached policies enforce locally
  - Incidents queue up to 500 MB (increased for remote config)
  - Upload on next VPN connection
```

[KB173958, V-tribal] Evidence: A-B

### 3.3 Virtual Desktop Infrastructure (VDI)

DLP 26.1 introduced Virtual Desktop and Virtual Application support with Endpoint Prevent.

```
Supported Platforms:
  - Citrix Virtual Apps and Desktops
  - VMware Horizon
  - Microsoft Azure Virtual Desktop

Configuration:
  - Install DLP agent in the golden image
  - Agent registers on first boot of each VDI session
  - Non-persistent desktops: agent state may not persist between sessions
  - Persistent desktops: standard agent behavior

Considerations:
  - Pool VDI sessions share an image; agent deployment is per-image
  - LiveUpdate should be disabled for non-persistent VDI
  - Agent groups should include VDI-specific configurations
```

[S3] Evidence: A

---

## 4. Endpoint Response Rule Deep Dive

### 4.1 Response Action Priority

When multiple response rules match an incident, Symantec DLP evaluates them in this priority order for endpoint actions:

```
Priority 1: Block (strongest -- if any rule says Block, transfer is blocked)
Priority 2: User Cancel (if no Block rule, User Cancel prompts the user)
Priority 3: Encrypt (if no Block or User Cancel, file is encrypted)
Priority 4: Notify (weakest -- notification is always shown regardless)
```

**Example:** A file copy to USB matches two policies:
- Policy A: Severity High -> Response: Block
- Policy B: Severity Medium -> Response: User Cancel

Result: Block wins (higher priority). The user sees the Block notification, not the User Cancel prompt.

[S1, S4] Evidence: A

### 4.2 Response Rule Conditions for Endpoint

| Condition | Description | Example |
|-----------|-------------|---------|
| Severity | Trigger only for specific severity levels | Only block High and Critical |
| Policy | Trigger only for specific policies | Only for PCI-DSS policies |
| Detection server type | Trigger only on specific server types | Endpoint Prevent only |
| Protocol | Trigger based on endpoint channel | USB only, or Email only |
| Sender/User pattern | Trigger based on user identity | Not for VIP users |

**Example -- Different responses by severity:**
- Severity: Critical -> Block + SIEM alert + email to CISO
- Severity: High -> Block + user notification
- Severity: Medium -> User Cancel (justification required)
- Severity: Low -> Notify only (informational popup)

[S1, S4] Evidence: A

---

## 5. Endpoint Discover (Data-at-Rest) Deep Dive

### 5.1 Endpoint Discover vs. Network Discover

| Aspect | Endpoint Discover | Network Discover |
|--------|-------------------|-----------------|
| What it scans | Local drives on the endpoint | Network file shares, databases, SharePoint, Exchange |
| Agent required | Yes (DLP Agent) | No (Detection Server scans remotely) |
| Scheduling | Manual start/stop ONLY | Full scheduling (one-time, recurring, incremental) |
| OS support | Windows, macOS, Linux (16.0+) | N/A (server-side) |
| Performance impact | On the endpoint (CPU throttle configurable) | On the Detection Server + network |
| Remediation | Limited (tag, notify) | Full (quarantine, copy, encrypt, DRM) |
| Network drives | Does NOT scan network-mounted drives | Primary purpose |
| Scan progress | Per-agent reporting to Enforce | Centralized in Enforce Discover UI |

### 5.2 Running an Endpoint Discover Scan

**Navigation:** System > Agents > Agent Configuration > Channels > Endpoint Discover

```
Steps:
1. Enable Endpoint Discover in the Agent Configuration
2. Configure scan paths (e.g., C:\Users\)
3. Set exclusions (C:\Windows\, C:\Program Files\)
4. Set CPU throttle (25% recommended)
5. Save configuration
6. Wait for agents to receive updated configuration (up to 15 min)
7. Start scan: System > Agents > Endpoint Discover > Start Scan
8. Monitor progress in Enforce console
9. Stop scan when complete or manually stop
```

**Incremental scanning:** After the first full scan, subsequent scans only inspect new or modified files. File metadata (last modified timestamp, file hash) is cached locally on the endpoint.

[S1, S4] Evidence: A

---

## 6. Browser Integration Architecture

### 6.1 Content Analysis Connector Architecture

DLP 16.0 re-architected browser monitoring to use Content Analysis Connectors instead of the older local proxy approach.

```
Pre-16.0 Architecture (Legacy):
  Browser -> Local Agent Proxy -> DLP Agent -> Endpoint Server
  (Agent intercepted HTTP/HTTPS at network layer)

16.0+ Architecture (Current):
  Browser -> Content Analysis Connector (Extension) -> DLP Agent -> Endpoint Server
  (Extension captures upload content directly from browser DOM)
```

**Advantages of the new architecture:**
- No local proxy configuration required
- No certificate injection into browser (less SSL/TLS issues)
- More reliable HTTPS inspection (works with HSTS, cert pinning)
- Per-browser granularity (enable/disable per browser)
- Lower performance overhead

**Browser-specific notes:**
| Browser | Connector | Install Method | Notes |
|---------|-----------|---------------|-------|
| Chrome | Symantec DLP Content Analysis extension | Chrome Web Store or GPO sideload | Extension ID must be whitelisted in Chrome admin policy |
| Edge | Same extension (Chromium-based) | Edge Add-ons or GPO sideload | Works identically to Chrome |
| Firefox | Symantec DLP Firefox connector | Firefox Add-ons or policy sideload | Available from DLP 16.0.1 |
| IE | Legacy native agent hook | Built into agent | Deprecated; IE end of life |

[S1, S6, V-tribal] Evidence: A

---

## 7. Offline Enforcement Model

### 7.1 How Offline Works

```
Agent Online (Normal):
  1. Agent polls Endpoint Server every 15 minutes
  2. Receives latest policy set
  3. Caches policy locally
  4. Performs detection locally using cached policy
  5. Uploads incidents to server in real-time

Agent Offline (No server connectivity):
  1. Agent cannot reach Endpoint Server
  2. Uses LAST CACHED policy set for enforcement
  3. All detection still works locally (DCM, EDM, IDM, VML)
  4. Incidents stored in local queue (disk-based)
  5. Queue grows up to configured max (default: 100 MB)
  6. When queue is full, oldest incidents are dropped (FIFO)

Agent Reconnects:
  1. Agent reaches Endpoint Server on next poll
  2. Downloads any policy updates
  3. Uploads all queued incidents
  4. Resumes normal operation
```

### 7.2 Offline Implications

| Concern | Impact | Mitigation |
|---------|--------|------------|
| Policy changes not applied | Stale policies enforce until reconnect | Critical policies should be deployed well before any expected offline period |
| Incidents delayed | Queued incidents not visible to analysts | Increase offline queue size for remote workers |
| Queue overflow | Oldest incidents lost if queue fills up | Increase max offline queue (500+ MB for remote workers) |
| No server-side response rules | Server-side actions (email notification to admin) delayed | Configure endpoint-local actions (block, notify) that work offline |
| VML/EDM index updates delayed | New index data not available until reconnect | Schedule index updates before known offline periods |

[S1, S4] Evidence: A

---

## 8. Agent Group Strategy Patterns

### 8.1 Department-Based Groups

```
Agent Group: Finance
  Criteria: AD OU = OU=Finance,DC=corp,DC=example,DC=com
  Configuration: Finance-Strict (all channels, block mode)
  Policies: PCI-DSS, SOX, GLBA

Agent Group: Engineering
  Criteria: AD OU = OU=Engineering,DC=corp,DC=example,DC=com
  Configuration: Dev-Monitor (relaxed, monitor-only)
  Policies: IP-Protection, Source-Code-Protect

Agent Group: HR
  Criteria: AD OU = OU=HR,DC=corp,DC=example,DC=com
  Configuration: HR-Strict (all channels, block mode)
  Policies: PII-Protection, HIPAA, Employee-Records

Agent Group: Executives
  Criteria: AD Security Group = CN=C-Suite
  Configuration: Exec-Light (monitor-only, no blocking)
  Policies: All policies (for visibility) but no blocking response rules
```

### 8.2 Risk-Based Groups

```
Agent Group: High-Risk Users
  Criteria: ICA Risk Score > 80 (via AD attribute sync)
  Configuration: High-Risk (all channels, aggressive blocking)
  Policies: All policies with Block response rules

Agent Group: Normal Users
  Criteria: ICA Risk Score <= 80
  Configuration: Standard (key channels only, notify mode)
  Policies: All policies with Notify response rules
```

[S1, S4, S25] Evidence: A-B

---

## 9. Performance Tuning Reference

### 9.1 Channel Performance Impact

| Channel | CPU Impact | Memory Impact | Disk I/O Impact | Recommendation |
|---------|-----------|---------------|-----------------|----------------|
| Email (Outlook) | Low | Low | Low | Always enable -- low overhead |
| Web/HTTP(S) | Medium | Medium | Low | Enable -- use URL whitelisting to reduce scans |
| USB | Low | Low | Medium (during writes) | Always enable -- critical DLP channel |
| Clipboard | HIGH | Medium | Low | Enable selectively -- restrict source/target apps |
| Print | Low | Low | Low | Always enable -- low overhead |
| Screen Capture | Medium | Low | Low | Enable selectively -- limited reliability |
| Local Drives (Discover) | HIGH | HIGH | HIGH | Use CPU throttle + scheduled off-hours |
| Application File Access | HIGH | Medium | Medium | Restrict to specific apps |
| Network Share | Low | Low | Medium | Always enable |
| Cloud File Sync | Low | Low | Low | Always enable |
| CD/DVD | Low | Low | Low | Always enable |
| FTP | Low | Low | Low | Always enable |

### 9.2 Recommended Starting Configuration

For a balanced security/performance starting point:

```
ENABLE (low overhead):     Email, Web, USB, Print, Network Share, Cloud Sync, FTP
SELECTIVE (use cautiously): Clipboard (restrict apps), Screen Capture (monitor-only)
SCHEDULE CAREFULLY:        Local Drives (Endpoint Discover) -- off-hours only
RESTRICT APPS:             Application File Access (specific apps only)
```

[S1, KB176182] Evidence: A-B

---

## 10. FlexResponse on Endpoints

### 10.1 What FlexResponse Does

FlexResponse is a plug-in framework that allows custom response actions on endpoints beyond the built-in block/notify/encrypt/user-cancel options. It executes Java JAR files on the endpoint when a policy violation is detected.

### 10.2 FlexResponse Examples

| Plugin | Action | Use Case |
|--------|--------|----------|
| Custom DRM application | Apply digital rights management to detected file | Protect IP with persistent encryption/access control |
| Custom tagging | Write metadata tag to file properties | Integrate with data classification system |
| Custom quarantine | Move file to a secure quarantine folder on endpoint | Local quarantine without server connectivity |
| Custom notification | Send notification via custom channel (webhook, SMS) | Alert via non-standard communication channel |
| Custom audit | Write detailed audit log to local file or syslog | Compliance audit trail beyond standard DLP logging |

### 10.3 FlexResponse Configuration

```
Server-side:
  Configuration file: <DLP_Install>/Protect/config/Plugins.properties
  Plugin registration: add plugin class path and JAR location

Endpoint-side:
  Plugin JAR deployed to: <Agent_Install>/plugins/
  Plugin configuration via Enforce console or embedded in JAR
```

[S1, S4, S10] Evidence: A-B

---

## 11. API Integration for Endpoint Incidents

### 11.1 Querying Endpoint Incidents via REST API

The Enforce Server REST API exposes endpoint incidents through the same incident API used for network and discover incidents.

```
POST https://<enforce>/ProtectManager/webservices/v2/incidents
Content-Type: application/json
Authorization: Basic <base64(user:pass)>

{
  "savedReportId": 12345,
  "incidentCreationDateGreaterThan": "2025-01-01T00:00:00.000Z"
}
```

Endpoint-specific fields in incident response:
- `endpointMachine` -- hostname of the endpoint
- `endpointUserName` -- logged-in user at time of violation
- `endpointApplicationName` -- application involved (e.g., OUTLOOK.EXE)
- `endpointDeviceId` -- USB device ID (for removable storage incidents)
- `endpointChannel` -- channel type (EMAIL, HTTP, REMOVABLE_STORAGE, CLIPBOARD, etc.)

### 11.2 Updating Endpoint Incidents

```
PATCH https://<enforce>/ProtectManager/webservices/v2/incidents
Content-Type: application/json
Authorization: Basic <base64(user:pass)>

{
  "incidents": [
    {
      "incidentId": 10001,
      "incidentAttributes": {
        "status": "IN_PROGRESS",
        "customAttributes": {
          "ReviewedBy": "analyst@corp.example.com",
          "FalsePositive": "No"
        },
        "incidentNotes": "Confirmed PCI violation. Employee counseled."
      }
    }
  ]
}
```

### 11.3 API Gaps for Endpoint Management

| Operation | API Available | Workaround |
|-----------|-------------|------------|
| List endpoint incidents | YES (incident API) | -- |
| Update endpoint incidents | YES (PATCH /incidents) | -- |
| Deploy agent packages | NO | Use GPO, SCCM, Intune |
| Configure agent settings | NO | Enforce console only |
| Create agent groups | NO | Enforce console only |
| Start Endpoint Discover scan | NO | Enforce console only |
| View agent status | NO | Enforce console only |
| Force policy push to agent | NO | Not possible (agent polls) |

[API-intelligence, S1] Evidence: A

---

## 12. End-to-End Enterprise Scenario

### Scenario: Global Financial Institution -- 5000 Endpoints

**Requirement:** Protect PCI cardholder data, customer PII, and proprietary trading algorithms across 5000 Windows endpoints in 3 regions (US, EU, APAC).

**Architecture:**
```
US Region (New York):
  Enforce Server: dlp-enforce-us.corp.example.com
  Oracle DB: dlp-db-us.corp.example.com
  Endpoint Servers (LAN): dlp-eps-us01, dlp-eps-us02
  Endpoint Servers (DMZ): dlp-eps-us-dmz01, dlp-eps-us-dmz02
  Load Balancer: dlp-endpoint-us.corp.example.com

EU Region (London):
  Endpoint Servers (LAN): dlp-eps-eu01, dlp-eps-eu02
  (Connected to US Enforce Server via WAN)

APAC Region (Singapore):
  Endpoint Servers (LAN): dlp-eps-apac01
  (Connected to US Enforce Server via WAN)
```

**Agent Groups:**
```
Group: US-Trading-Floor (800 agents)
  Config: Trading-Strict (all channels, block mode, no USB, no cloud sync)
  Policies: PCI-DSS, Trading-Algorithm-Protect, SOX

Group: EU-All (1500 agents)
  Config: EU-GDPR (all channels, GDPR-focused, multi-language notifications)
  Policies: GDPR, PCI-DSS, PII-EU

Group: APAC-All (700 agents)
  Config: APAC-Standard (all channels, English + regional language)
  Policies: PCI-DSS, PII-APAC, PDPA

Group: Remote-Workers (1500 agents, cross-region)
  Config: Remote-Config (500 MB offline queue, DMZ servers via LB)
  Policies: All regional policies
  Endpoint Server: dlp-endpoint-{region}.corp.example.com (load balanced)

Group: IT-Admin (500 agents)
  Config: IT-Monitor-Only (monitor-only, no blocking, all channels)
  Policies: All policies for visibility
```

**Deployment Timeline:**
```
Month 1: Infrastructure setup (Enforce, Endpoint Servers, Oracle)
Month 2: IT pilot (500 agents, all regions)
Month 3: Finance + Trading (800 agents, US)
Month 4: EU rollout (1500 agents, GDPR compliance)
Month 5: APAC rollout (700 agents)
Month 6: Remote workers (1500 agents, DMZ servers)
Month 7+: Ongoing tuning, policy refinement, audit
```

[S1, S4, V-tribal, KB173958] Evidence: A-B

---

## Summary

This advanced reference covers every endpoint channel's configuration screen, advanced agent settings, deployment scenarios (GPO, SCCM, VDI, remote workforce), response rule priority logic, browser integration architecture, offline enforcement, agent group strategies, performance tuning, FlexResponse extensibility, and API integration patterns. The endpoint DLP capability is Symantec's most operationally complex channel due to the 12+ detection channels, multi-OS support matrix, agent deployment logistics, and offline enforcement model.

[S1, S2, S3, S4, S6, V12, V23, V29, V30, V35, V36, KB159522, KB173958, KB176182, API-intelligence] Evidence: A
