# Network DLP — Gotchas
## Broadcom Symantec DLP (Enforce Server, version 16.x/25.x/26.x)

> **Purpose:** Comprehensive collection of gotchas, pitfalls, and best-practice warnings for network DLP deployment and operation.
> **Evidence sources:** doc-corpus.md [S1-S28], video-intelligence.md [V1-V45, tribal knowledge], api-intelligence.md

---

## Table of Contents

1. [Network Monitor Gotchas](#1-network-monitor-gotchas)
2. [Email Prevent Gotchas](#2-email-prevent-gotchas)
3. [Web Prevent / ICAP Gotchas](#3-web-prevent--icap-gotchas)
4. [Network Discover Gotchas](#4-network-discover-gotchas)
5. [SSL/TLS Gotchas](#5-ssltls-gotchas)
6. [Performance Gotchas](#6-performance-gotchas)
7. [Integration Gotchas](#7-integration-gotchas)

---

## 1. Network Monitor Gotchas

### G-NM-1: SPAN port oversubscription causes packet drops and missed detections
**Impact:** HIGH
**Symptom:** DLP detects only a fraction of expected email/web traffic. Incidents are sporadic.
**Root cause:** SPAN/mirror port bandwidth is exceeded by the aggregate traffic being mirrored. Switch silently drops packets that exceed the SPAN port capacity.
**Mitigation:** Ensure the SPAN destination port speed matches or exceeds the sum of mirrored traffic. For high-bandwidth environments, use a network TAP (hardware device) instead of SPAN. TAPs provide full-line-rate copies without drops.
**Evidence:** A [S1, S9]

### G-NM-2: Network Monitor cannot decrypt traffic it does not have the private key for
**Impact:** MEDIUM
**Symptom:** HTTPS traffic passes through Network Monitor without content inspection. All HTTPS sessions show as "encrypted -- not inspected."
**Root cause:** Passive SSL inspection requires the server's private key. For traffic to external sites (Google, Office 365), the private key is obviously unavailable.
**Mitigation:** For external HTTPS inspection, use Network Prevent for Web (ICAP) with a proxy that terminates SSL. The proxy decrypts the traffic and sends cleartext to DLP via ICAP. Network Monitor is only effective for HTTPS inspection of internal servers where you possess the private key.
**Evidence:** A [S1, S4]

### G-NM-3: Network Monitor deployed on wrong network segment misses target traffic
**Impact:** HIGH
**Symptom:** Zero incidents from Network Monitor despite known sensitive data in email traffic.
**Root cause:** The SPAN port is mirroring traffic from a segment that does not carry outbound email (e.g., mirroring a DMZ segment instead of the internal MTA segment).
**Mitigation:** Map your email/web traffic flow before deploying. Identify exactly which switch port(s) carry outbound SMTP/HTTP traffic. Configure SPAN to mirror those specific ports. Verify with tcpdump on the monitoring interface.
**Evidence:** B [S1, V-tribal]

---

## 2. Email Prevent Gotchas

### G-EP-1: DLP Email Prevent in forwarding mode becomes a single point of failure
**Impact:** CRITICAL
**Symptom:** ALL outbound email stops when the DLP Email Prevent server goes down.
**Root cause:** In forwarding mode, the MTA routes email to DLP, and DLP is responsible for forwarding it to the next hop. If DLP is down, email has nowhere to go.
**Mitigation:** Use **reflecting mode** instead of forwarding mode. In reflecting mode, the MTA sends a copy to DLP, DLP returns it with X-headers, and the MTA makes the final delivery decision. If DLP is unreachable, the MTA can be configured to deliver email without inspection (fail-open). Alternatively, deploy redundant Email Prevent servers with failover.
**Evidence:** A [S1, S13]

### G-EP-2: MTA message size limit mismatch causes large emails to bypass DLP
**Impact:** MEDIUM
**Symptom:** Large emails (>50 MB) are delivered without DLP inspection.
**Root cause:** The DLP Email Prevent server has a max message size (default: 50 MB). The MTA's message_size_limit may be higher. Messages exceeding the DLP limit are passed through without scanning.
**Mitigation:** Align message size limits between MTA and DLP. If MTA allows 100 MB messages, either increase DLP max message size to 100 MB or create a network monitor rule to flag large messages that bypass email prevent.
**Evidence:** A [S1, S13]

### G-EP-3: X-header stripping by downstream MTAs removes DLP enforcement
**Impact:** HIGH
**Symptom:** DLP applies X-DLP-Action: BLOCK header, but the email is delivered anyway.
**Root cause:** A downstream MTA or email gateway strips unknown X-headers before processing. The enforcement MTA never sees the DLP headers.
**Mitigation:** Ensure no MTA between DLP and the enforcement point strips X-headers. Test the full email path end-to-end. Some email gateways have "header preservation" settings that must be enabled.
**Evidence:** B [S13, V-tribal]

### G-EP-4: Bounce storms when blocking emails from automated systems
**Impact:** MEDIUM
**Symptom:** Hundreds of bounce messages flood the DLP incident queue and the sender's mailbox.
**Root cause:** Automated systems (monitoring alerts, CRM notifications, batch reports) that send emails containing sensitive data get blocked. Each blocked email generates a bounce, and the automated system may retry, creating a loop.
**Mitigation:** Create policy exceptions for known automated sender addresses (e.g., `monitoring@corp.example.com`, `noreply@crm.corp.example.com`). Alternatively, use "allow with incident" response instead of "block" for automated senders, and investigate the root cause of sensitive data in automated emails.
**Evidence:** B [V-tribal]

### G-EP-5: Email encryption response action requires separate encryption gateway
**Impact:** MEDIUM
**Symptom:** Response rule configured with "Encrypt" action but emails are not encrypted.
**Root cause:** DLP itself does not encrypt email. The Encrypt action adds an X-header that tells a downstream encryption gateway to encrypt. If no encryption gateway is deployed, the X-header has no effect.
**Mitigation:** Deploy an email encryption gateway (PGP Universal, ZixEncrypt, Voltage, etc.) that reads the DLP X-header and encrypts matching messages. Verify the encryption gateway is configured to read the specific X-header name and value.
**Evidence:** A [S1]

---

## 3. Web Prevent / ICAP Gotchas

### G-WP-1: ICAP connection count mismatch causes slow web browsing
**Impact:** HIGH
**Symptom:** Users report slow page loads, timeouts on web uploads, and "proxy error" messages.
**Root cause:** The web proxy is configured with more concurrent ICAP connections than the DLP Web Prevent server can handle. Excess connections queue up, causing delays.
**Mitigation:** Set the concurrent ICAP connection count identically on both the proxy and the DLP server. Monitor queue depth on the DLP server. If queuing is persistent, either increase DLP server resources or add a second DLP server with ICAP load balancing.
**Evidence:** A [S9, S15]

### G-WP-2: Fail-closed ICAP configuration blocks all web traffic during DLP outage
**Impact:** CRITICAL
**Symptom:** All web browsing stops when the DLP Web Prevent server is down.
**Root cause:** The proxy is configured to fail-closed (block traffic if ICAP server is unreachable). When DLP goes down, the proxy cannot process any web requests.
**Mitigation:** Configure the proxy to **fail-open** for ICAP. This allows web traffic to flow without DLP inspection during outages. Monitor DLP server health with high-priority alerts. Combine with endpoint DLP for defense-in-depth during network DLP outages.
**Evidence:** A [S1, S15]

### G-WP-3: Secure ICAP certificate mismatch breaks proxy-to-DLP communication
**Impact:** HIGH
**Symptom:** Proxy logs show "ICAP service unavailable" or "TLS handshake failed."
**Root cause:** The DLP server's Secure ICAP certificate is not trusted by the proxy, or the certificate common name does not match the hostname used in the ICAP URL.
**Mitigation:** Import the DLP server's CA certificate into the proxy's trust store. Ensure the ICAP URL hostname matches the certificate CN or SAN. For self-signed certificates, the exact certificate must be imported (not just the CA).
**Evidence:** B [S15, V-tribal]

### G-WP-4: ICAP preview bytes too small causes unnecessary round-trips
**Impact:** LOW
**Symptom:** Web upload scanning is slower than expected.
**Root cause:** ICAP preview bytes set too low. The proxy sends only a small preview of the upload, DLP cannot make a decision, and requests a full body transfer. This adds a round-trip.
**Mitigation:** Set ICAP preview bytes to 4096 or higher. This allows DLP to inspect enough content in the preview to make allow/deny decisions for most small uploads without a second round-trip.
**Evidence:** B [S15]

### G-WP-5: Content Removal (RESPMOD) modifies web pages in unexpected ways
**Impact:** MEDIUM
**Symptom:** Web pages display incorrectly after DLP content removal. JavaScript breaks, forms malfunction.
**Root cause:** DLP Content Removal modifies the HTML response body. If the removal alters the HTML structure (e.g., removes content within JavaScript, breaks JSON payloads, or removes hidden form fields), the page may not render correctly.
**Mitigation:** Test Content Removal policies thoroughly on representative web pages. Use surgical removal patterns (target specific data patterns like SSNs, not broad content). For critical web applications, use REQMOD (block outbound data) instead of RESPMOD (modify inbound content).
**Evidence:** B [S1, V-tribal]

---

## 4. Network Discover Gotchas

### G-ND-1: Discover scan credentials stored in cleartext in Oracle DB
**Impact:** HIGH
**Symptom:** Security audit flags that Discover target credentials (service account passwords) are accessible in the database.
**Root cause:** Discover target credentials are stored in the Enforce Server database. While the database itself should be encrypted and access-controlled, the credentials within it may be recoverable by anyone with database admin access.
**Mitigation:** Use dedicated service accounts with minimal privileges for Discover scanning. Rotate passwords regularly. Implement Oracle Transparent Data Encryption (TDE) and strict DBA access controls. Consider using Windows Integrated Authentication (NTLM/Kerberos) instead of storing passwords where possible.
**Evidence:** B [S1, V-tribal]

### G-ND-2: Initial full scan of large file shares takes days
**Impact:** MEDIUM
**Symptom:** First Discover scan of a 10+ TB file share runs for 48+ hours and generates heavy network traffic.
**Root cause:** Full scan reads and analyzes every file on the target. For large file shares with millions of files, this is inherently time-consuming.
**Mitigation:**
1. Use file age filters to scan only recent files (e.g., modified within last 365 days)
2. Exclude file types that rarely contain sensitive data (.exe, .dll, .sys, .msi)
3. Set bandwidth limits to prevent network saturation
4. Schedule initial scan over a weekend
5. Enable incremental scanning -- subsequent scans only process new/modified files
6. Use High Speed Discovery (DLP 16.0+) for up to 10x faster scanning
**Evidence:** B [S17]

### G-ND-3: Discover scan locks files on Windows file servers
**Impact:** MEDIUM
**Symptom:** Users report "file in use" errors during Discover scans.
**Root cause:** The Discover server opens files for reading during scanning. On Windows, this can create read locks that interfere with user access.
**Mitigation:** Use read-only credentials with "opportunistic locking" (oplock) support. Schedule scans during off-hours when file contention is minimal. If persistent, reduce max concurrent files setting to lower the number of simultaneously open files.
**Evidence:** B [S17, V-tribal]

### G-ND-4: SharePoint scan skips versioned documents by default
**Impact:** LOW
**Symptom:** Sensitive data in older versions of SharePoint documents is not detected.
**Root cause:** By default, Discover scans only the current version of SharePoint documents. Previous versions may contain sensitive data that was later redacted.
**Mitigation:** Enable "Scan all versions" in the SharePoint target configuration if version-level compliance is required. Be aware this significantly increases scan time.
**Evidence:** B [S1]

### G-ND-5: DFS scan targets only work from Windows Discover Servers
**Impact:** MEDIUM
**Symptom:** DFS scan target creation fails or returns "unsupported target type" error.
**Root cause:** DFS (Distributed File System) targets are only supported on Windows-based Network Discover Servers. Linux Discover Servers cannot scan DFS.
**Mitigation:** Deploy at least one Windows-based Network Discover Server for DFS targets. Linux servers can scan CIFS, NFS, and other target types.
**Evidence:** A [S1]

### G-ND-6: Quarantine tombstone file does not inherit original file permissions
**Impact:** LOW
**Symptom:** Users who had access to the original file cannot read the tombstone file, so they do not know the file was quarantined.
**Root cause:** Tombstone files may be created with different permissions than the original file (depending on the service account creating them).
**Mitigation:** Configure the tombstone to inherit the parent directory permissions, or set the tombstone to "Everyone: Read" so all users can see the quarantine notice.
**Evidence:** B [S1, V-tribal]

---

## 5. SSL/TLS Gotchas

### G-SSL-1: SSL cipher suite mismatch between Enforce and Detection Servers
**Impact:** HIGH
**Symptom:** Detection Servers cannot communicate with Enforce Server. Server status shows "Disconnected" or "Communication Error."
**Root cause:** The `SSLcipherSuites` setting on the Enforce Server and Detection Servers must match. If one side supports only TLS 1.3 ciphers and the other only TLS 1.2, the TLS handshake fails.
**Mitigation:** Verify `SSLcipherSuites` configuration is consistent across all servers. After any SSL/TLS configuration change, check communication between all server pairs.
**Evidence:** B [V-tribal, gotcha #11]

### G-SSL-2: Expired SSL certificates break all server communication
**Impact:** CRITICAL
**Symptom:** All detection servers lose connection to Enforce Server simultaneously. No incidents are reported. Agent check-ins may fail.
**Root cause:** The TLS certificate used for server-to-server communication has expired. DLP validates certificates by default.
**Mitigation:** Set calendar reminders for certificate expiration dates. Implement certificate monitoring with at least 30-day advance warnings. DLP 16.0 RU2+ provides certificate management APIs for monitoring.
**Evidence:** B [V-tribal, API-intelligence]

---

## 6. Performance Gotchas

### G-PF-1: Network Discover scan saturates network bandwidth
**Impact:** HIGH
**Symptom:** Other network services slow down during Discover scans. Users complain about file server performance.
**Root cause:** Discover scans generate significant network traffic as they read files from target servers. Without bandwidth limits, scans can saturate the network link.
**Mitigation:** Set bandwidth limits in the Discover target configuration. 50-100 MB/s is a reasonable limit for most environments. Schedule scans during off-hours. Monitor network utilization during scans.
**Evidence:** B [S17]

### G-PF-2: Email Prevent latency adds visible delay to email delivery
**Impact:** MEDIUM
**Symptom:** Users notice a 2-5 second delay between clicking "Send" in Outlook and the email being accepted by the server.
**Root cause:** The MTA routes the email to DLP for inspection, adding latency for content scanning. Complex policies (EDM, IDM, VML) take longer to evaluate than simple keyword rules.
**Mitigation:** Size the Email Prevent server appropriately for email volume. Simplify high-frequency policies (use data identifiers instead of EDM for initial scan). Consider deploying endpoint DLP for email (faster local scan) and using network email prevent as a second layer.
**Evidence:** B [S9]

### G-PF-3: Web Prevent scanning large file uploads causes browser timeouts
**Impact:** MEDIUM
**Symptom:** Users uploading large files (100+ MB) via browser receive timeout errors.
**Root cause:** Scanning large files takes time. The proxy's ICAP timeout expires before DLP completes the scan.
**Mitigation:** Increase ICAP timeout on both proxy and DLP server (300+ seconds for large uploads). Set reasonable max request body size on the DLP server. Consider excluding very large uploads from DLP scanning by configuring the proxy to skip ICAP for uploads above a size threshold.
**Evidence:** B [S9, S15]

---

## 7. Integration Gotchas

### G-INT-1: Postfix content_filter conflicts with other email filters
**Impact:** MEDIUM
**Symptom:** DLP email inspection breaks when another content filter (spam filter, antivirus) is also configured in Postfix.
**Root cause:** Postfix `content_filter` directive allows only one primary content filter. If both DLP and a spam filter are configured as content filters, one overrides the other.
**Mitigation:** Chain content filters: Postfix -> Spam Filter -> DLP -> back to Postfix. Or use milter for one filter and content_filter for the other. Consult the MTA Integration Guide (S13) for chaining patterns.
**Evidence:** B [S13, V-tribal]

### G-INT-2: Discover target authentication failure is silent
**Impact:** MEDIUM
**Symptom:** Discover scan completes with 0 files scanned. No errors visible in the Enforce console.
**Root cause:** The service account credentials for the scan target are incorrect, expired, or lack sufficient permissions. The Discover server quietly skips targets it cannot authenticate to.
**Mitigation:** Test credentials manually before configuring scan targets (e.g., `net use \\fileserver\share /user:CORP\dlp-scanner` from the Discover server). Monitor scan results for unexpectedly low file counts. Check Discover server logs for authentication errors.
**Evidence:** B [S1, V-tribal]

### G-INT-3: Network Discover API (25.1+) does not support scan start/stop
**Impact:** MEDIUM
**Symptom:** You can create and configure Discover targets via API but cannot programmatically start or stop scans.
**Root cause:** The Discover Target API (DLP 25.1+) supports CRUD operations on targets but not scan lifecycle management. Starting and stopping scans remains a console-only operation.
**Mitigation:** Use the API for target configuration automation. Use the Enforce console for scan management. If automation is critical, consider screen automation or scripting against the Enforce web UI (not recommended for production).
**Evidence:** A [API-intelligence]

---

## Gotcha Severity Summary

| Severity | Count | IDs |
|----------|-------|-----|
| CRITICAL | 3 | G-EP-1, G-WP-2, G-SSL-2 |
| HIGH | 8 | G-NM-1, G-NM-3, G-EP-3, G-WP-1, G-WP-3, G-ND-1, G-SSL-1, G-PF-1 |
| MEDIUM | 12 | G-NM-2, G-EP-2, G-EP-4, G-EP-5, G-WP-5, G-ND-2, G-ND-3, G-ND-5, G-PF-2, G-PF-3, G-INT-1, G-INT-2, G-INT-3 |
| LOW | 3 | G-WP-4, G-ND-4, G-ND-6 |

[S1, S4, S9, S13, S14, S15, S17, V-tribal, API-intelligence] Evidence: A-B
