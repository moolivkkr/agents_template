# Endpoint DLP — Gotchas
## Broadcom Symantec DLP (Enforce Server, version 16.x/25.x/26.x)

> **Purpose:** Comprehensive collection of gotchas, pitfalls, and best-practice warnings for endpoint DLP deployment and operation.
> **Evidence sources:** doc-corpus.md [S1-S28], video-intelligence.md [V1-V45, tribal knowledge], api-intelligence.md

---

## Table of Contents

1. [Agent Deployment Gotchas](#1-agent-deployment-gotchas)
2. [Offline and Connectivity Gotchas](#2-offline-and-connectivity-gotchas)
3. [Channel-Specific Gotchas](#3-channel-specific-gotchas)
4. [Performance Gotchas](#4-performance-gotchas)
5. [Response Action Gotchas](#5-response-action-gotchas)
6. [Agent Group and Configuration Gotchas](#6-agent-group-and-configuration-gotchas)
7. [Browser Integration Gotchas](#7-browser-integration-gotchas)
8. [Upgrade and Migration Gotchas](#8-upgrade-and-migration-gotchas)
9. [Platform-Specific Gotchas](#9-platform-specific-gotchas)
10. [Operational Gotchas](#10-operational-gotchas)

---

## 1. Agent Deployment Gotchas

### G-ED-1: Agent package bakes in server address at build time
**Impact:** HIGH
**Symptom:** Deployed agents cannot connect to Endpoint Prevent Server after server IP change or server migration.
**Root cause:** The Endpoint Server address (IP, hostname, or FQDN) is embedded in the MSI package at build time. Once deployed, agents use this hardcoded address.
**Mitigation:** ALWAYS use FQDN when building agent packages. FQDNs survive IP changes and server migrations -- update DNS instead of rebuilding packages. If IP or hostname was used, a new agent package must be built and redeployed to all endpoints.
**Evidence:** A [S1, V29, V-tribal]

### G-ED-2: Load balancer without Source IP persistence causes split reporting
**Impact:** HIGH
**Symptom:** Incidents from the same agent appear on different Endpoint Servers. Agent status shows intermittent online/offline. Policies may not update consistently.
**Root cause:** Load balancer round-robins agent connections to different Endpoint Servers. Each check-in goes to a different server, causing state fragmentation.
**Mitigation:** Configure load balancer with "Source IP persistence" (sticky sessions) set to 24 hours. This ensures each agent consistently connects to the same Endpoint Server.
**Evidence:** A [KB173958, V-tribal]

### G-ED-3: Deploying blocking policies on day 1 causes employee backlash
**Impact:** HIGH
**Symptom:** Help desk overwhelmed with "I can't send email" or "I can't copy files" complaints. Executive pushback on DLP program.
**Root cause:** Aggressive blocking policies deployed simultaneously with new endpoint agents. Users experience unexpected workflow disruption.
**Mitigation:** ALWAYS use staged rollout:
1. **Week 1-2:** Deploy agents with "Test Without Notifications" (invisible monitoring)
2. **Week 3-4:** Switch to "Test With Notifications" (users see warnings but nothing is blocked)
3. **Week 5+:** Enable blocking on highest-severity policies only
4. **Ongoing:** Gradually expand blocking based on false positive analysis
**Evidence:** B [V-tribal, best practices]

### G-ED-4: Agent deployment via GPO fails if MSI path uses local drive letter
**Impact:** MEDIUM
**Symptom:** GPO software installation fails with "package not found" errors on client machines.
**Root cause:** MSI path in GPO must be a UNC path (`\\server\share\agent.msi`), not a mapped drive letter (`Z:\agent.msi`). During computer startup, drive mappings are not yet available.
**Mitigation:** Always use UNC paths for MSI packages in Group Policy software installation.
**Evidence:** B [V30]

### G-ED-5: Agent tamper protection prevents legitimate uninstall
**Impact:** MEDIUM
**Symptom:** IT admin cannot uninstall or upgrade the DLP agent without the admin password.
**Root cause:** Tamper protection (enabled by default) prevents agent uninstall and service stop without the configured admin password.
**Mitigation:** Document the agent admin password in your password manager. If the password is lost, contact Broadcom Support for a recovery procedure. For automated upgrades via LiveUpdate, tamper protection does not interfere (server-initiated upgrades bypass it).
**Evidence:** A [S1]

---

## 2. Offline and Connectivity Gotchas

### G-ED-6: Policy changes take up to 15 minutes to reach agents
**Impact:** MEDIUM
**Symptom:** Emergency policy change (e.g., blocking a data breach in progress) does not take effect immediately on endpoints.
**Root cause:** DLP agents poll the Endpoint Prevent Server at a configurable interval (default: 15 minutes). There is no push mechanism to force immediate policy delivery.
**Mitigation:** For urgent situations, the only option is to wait for the next polling cycle. Consider reducing the polling interval to 5 minutes for high-risk agent groups (increases server load). For extreme urgency, network-level blocking (firewall rules, proxy blocks) may be faster than waiting for DLP policy propagation.
**Evidence:** A [S1, S4]

### G-ED-7: Offline agents accumulate incidents that flood the server on reconnect
**Impact:** MEDIUM
**Symptom:** After a large group of agents reconnect (e.g., Monday morning for remote workers), the Endpoint Prevent Server experiences a spike in incident uploads causing performance degradation.
**Root cause:** All queued incidents from offline agents upload simultaneously when connectivity is restored.
**Mitigation:** Increase Endpoint Prevent Server resources for environments with many remote workers. The agent staggers uploads slightly, but hundreds of agents reconnecting simultaneously still creates a burst. Consider staggering VPN connectivity requirements across departments.
**Evidence:** B [S1, V-tribal]

### G-ED-8: Offline queue overflow silently drops oldest incidents
**Impact:** HIGH
**Symptom:** Incidents from a prolonged offline period (e.g., employee on 2-week vacation) are missing from the incident database.
**Root cause:** The offline incident queue has a size limit (default: 100 MB). When the queue is full, the oldest incidents are dropped (FIFO) to make room for new ones. No alert is generated for dropped incidents.
**Mitigation:** Increase max offline queue size for remote worker agent groups (recommend 500 MB+). Monitor agent status in Enforce console -- agents offline for extended periods may have lost incidents.
**Evidence:** A [S1]

### G-ED-9: VPN split-tunnel configuration breaks agent communication
**Impact:** HIGH
**Symptom:** Remote agents show as "Offline" in Enforce console despite the user being connected to VPN.
**Root cause:** Split-tunnel VPN routes only corporate-specific traffic through the VPN. DLP agent traffic to the Endpoint Server (especially if using DMZ server with public IP) may be routed directly to the internet instead of through the VPN tunnel.
**Mitigation:** Ensure the Endpoint Server IP range is included in the VPN split-tunnel routing table. Alternatively, use full-tunnel VPN or deploy DMZ Endpoint Servers with publicly resolvable FQDNs.
**Evidence:** B [V-tribal]

---

## 3. Channel-Specific Gotchas

### G-ED-10: Local drive scanning (Endpoint Discover) kills endpoint performance
**Impact:** HIGH
**Symptom:** Users complain of slow machines, high CPU usage, disk thrashing during Endpoint Discover scans.
**Root cause:** Endpoint Discover scans read and analyze every file in the scan scope. Even with CPU throttling (default 25%), disk I/O contention slows down other applications.
**Mitigation:**
- Restrict scan scope to user data directories (e.g., `C:\Users\`), NOT entire drives
- Exclude system directories (`C:\Windows\`, `C:\Program Files\`, `C:\Program Files (x86)\`)
- Set CPU throttle to 10-15% for user endpoints (25% is too high for interactive use)
- Run scans during off-hours only
- Use incremental scanning (only new/modified files after first full scan)
- Stagger scans across agent groups (scan Finance this week, Engineering next week)
**Evidence:** A [S1, KB176182, V-tribal]

### G-ED-11: Endpoint Discover scans cannot be scheduled
**Impact:** MEDIUM
**Symptom:** Admin must manually start and stop Endpoint Discover scans. No way to automate recurring scans.
**Root cause:** This is a documented product limitation. Unlike Network Discover (which supports full scheduling), Endpoint Discover is manual start/stop only.
**Mitigation:** Create operational procedures for periodic manual scan initiation. Consider using Network Discover to scan network-accessible endpoint data (user home drives on file servers) instead of Endpoint Discover.
**Evidence:** A [S1, S4]

### G-ED-12: Screen capture monitoring is unreliable with modern capture tools
**Impact:** MEDIUM
**Symptom:** Screenshots taken with certain tools (e.g., OBS, Camtasia, newer Snipping Tool versions) are not detected.
**Root cause:** Screen capture monitoring hooks specific Windows APIs. Modern capture tools may use different APIs (DirectX capture, GPU-based capture) that bypass the monitored hooks.
**Mitigation:** Treat screen capture monitoring as a supplementary control, not a primary DLP mechanism. Combine with other controls (data classification labels that persist in screenshots, watermarking). Multi-monitor setups further reduce reliability.
**Evidence:** B [S1, doc-corpus gap analysis]

### G-ED-13: Clipboard monitoring with "All applications" generates overwhelming event volume
**Impact:** HIGH
**Symptom:** Thousands of clipboard incidents per day per endpoint. Endpoint performance degradation. Analysts cannot find real incidents among the noise.
**Root cause:** Users perform hundreds of copy-paste operations per day. Monitoring all applications captures every clipboard operation, including benign intra-office-suite copies.
**Mitigation:**
- NEVER use "All applications" for both source and target
- Restrict source apps to high-risk applications (database tools, CRM, financial apps)
- Restrict target apps to exfiltration vectors (browsers, messaging apps, email)
- Set minimum clipboard size threshold (100+ characters) to filter out small copies
**Evidence:** A [S1, KB176182]

### G-ED-14: Cloud File Sync detection fires on sync folder placement, not actual cloud upload
**Impact:** LOW
**Symptom:** DLP incident shows "file synced to Dropbox" but the file was only placed in the Dropbox sync folder -- the Dropbox client was not running and the file never actually uploaded.
**Root cause:** Endpoint DLP monitors file operations on the sync folder, not the actual cloud sync protocol. Placing a file in the Dropbox folder triggers the policy regardless of whether the Dropbox sync client is active.
**Mitigation:** This is generally acceptable behavior (the intent to sync is captured). If precise "actual upload" detection is needed, combine with Network Prevent for Web (ICAP) or CloudSOC monitoring for defense-in-depth.
**Evidence:** B [S1, V-tribal]

---

## 4. Performance Gotchas

### G-ED-15: Enabling all channels simultaneously degrades endpoint performance significantly
**Impact:** HIGH
**Symptom:** Users experience noticeable slowdown in application responsiveness, file operations, and email composition.
**Root cause:** Each channel adds CPU, memory, and I/O overhead. The cumulative impact of 12 channels is substantial.
**Mitigation:** Enable channels selectively based on risk assessment:
- **Always enable (low overhead):** Email, USB, Network Share, Cloud File Sync, Print
- **Enable selectively:** Web/HTTP(S) (with URL whitelisting), Clipboard (restrict apps)
- **Avoid on user endpoints:** Application File Access (all apps), Endpoint Discover (off-hours only)
**Evidence:** A [KB176182, V-tribal]

### G-ED-16: Large archive files cause agent timeout and missed detection
**Impact:** MEDIUM
**Symptom:** ZIP/RAR files containing sensitive data pass through without triggering DLP policies.
**Root cause:** Agent has a per-file processing timeout (default: 120 seconds). Large or deeply nested archives may exceed this timeout, causing the agent to skip the file.
**Mitigation:** Increase processing timeout for agent groups that handle large archives. Limit max archive depth (default: 5 levels) to prevent zip-bomb scenarios. Increase max extracted archive size if needed.
**Evidence:** A [S1]

### G-ED-17: OCR on endpoints consumes significant CPU
**Impact:** MEDIUM
**Symptom:** Endpoint performance degrades when processing image-heavy documents or scanned PDFs.
**Root cause:** OCR (Optical Character Recognition) is computationally expensive. Each image must be processed to extract text before DLP rules can be evaluated.
**Mitigation:** Enable endpoint OCR only for agent groups that regularly handle scanned documents (e.g., Legal, Compliance). For other groups, rely on Network DLP or Cloud DLP OCR instead.
**Evidence:** A [S1, S4]

---

## 5. Response Action Gotchas

### G-ED-18: "User Cancel" timeout defaults to 30 seconds -- too short for complex justifications
**Impact:** MEDIUM
**Symptom:** Users cannot type a meaningful justification before the timeout expires and the transfer is blocked.
**Root cause:** Default User Cancel timeout is 30 seconds. Users unfamiliar with the prompt spend time reading the message, leaving little time for typing.
**Mitigation:** Increase timeout to 60-90 seconds. Include clear, concise instructions in the notification template. Provide example justifications in the prompt text.
**Evidence:** A [S1, V23]

### G-ED-19: Block action on email channel blocks the entire email, not just the sensitive attachment
**Impact:** MEDIUM
**Symptom:** User cannot send an email with 5 attachments because 1 attachment contains sensitive data. The entire email is blocked, not just the problematic attachment.
**Root cause:** Endpoint email DLP operates at the message level, not the attachment level. The block action prevents the entire send operation.
**Mitigation:** User notification should explain which attachment triggered the policy (use `$FILE_NAME$` variable). User can remove the sensitive attachment and resend. Consider using "Encrypt" action instead of "Block" for policies where the content can be sent in encrypted form.
**Evidence:** A [S1, V23]

### G-ED-20: Encrypt action fails silently if encryption provider is not installed
**Impact:** HIGH
**Symptom:** Response rule is configured to encrypt files on USB write, but files are written unencrypted. No error visible to user or admin.
**Root cause:** The Encrypt response action requires an encryption provider (Symantec Endpoint Encryption, BitLocker) installed on the endpoint. If the provider is missing or malfunctioning, the encrypt action fails silently (default behavior).
**Mitigation:** Configure "Fallback if encrypt fails" to "Block" in the agent configuration. This ensures that if encryption fails, the file write is blocked rather than allowed unencrypted. Regularly verify encryption provider health on all endpoints.
**Evidence:** A [S1, S4]

---

## 6. Agent Group and Configuration Gotchas

### G-ED-21: Agent group membership changes take up to 15 minutes to apply
**Impact:** LOW
**Symptom:** Moving a user's OU in Active Directory does not immediately change their DLP agent configuration.
**Root cause:** Agent group membership is evaluated at each polling interval. AD group changes must also replicate across domain controllers.
**Mitigation:** Allow 15-30 minutes for agent group changes to take effect (polling interval + AD replication). For urgent changes, consider network-level controls as an interim measure.
**Evidence:** A [S1]

### G-ED-22: Default agent configuration applies to all unassigned agents
**Impact:** MEDIUM
**Symptom:** New agents deployed to a department not covered by any agent group receive the Default configuration, which may be too permissive or too restrictive.
**Root cause:** Agents not matched by any agent group criteria fall into the Default configuration. Many organizations forget to configure the Default configuration appropriately.
**Mitigation:** Treat the Default configuration as your baseline security posture. It should include core channels (email, USB, web) in monitor-only mode at minimum.
**Evidence:** A [S1, S4]

---

## 7. Browser Integration Gotchas

### G-ED-23: Chrome/Edge browser extension blocked by enterprise browser policy
**Impact:** HIGH
**Symptom:** Web/HTTP(S) monitoring does not work. No web upload incidents are generated.
**Root cause:** The organization's Chrome/Edge admin policy blocks all extensions, or only allows a specific allowlist that does not include the Symantec DLP extension.
**Mitigation:** Add the Symantec DLP Content Analysis extension ID to the enterprise browser allowlist or force-install list. Coordinate with the browser admin team before agent deployment.
**Evidence:** A [S1, S6, V-tribal]

### G-ED-24: Firefox connector requires separate installation from Chrome/Edge
**Impact:** LOW
**Symptom:** Web monitoring works in Chrome and Edge but not in Firefox.
**Root cause:** The Firefox Content Analysis Connector is a separate add-on from the Chrome/Edge extension and requires DLP 16.0.1+. It is not automatically installed with the DLP agent.
**Mitigation:** Deploy the Firefox connector separately via Firefox enterprise policy or manual installation. Ensure DLP version is 16.0.1 or later.
**Evidence:** A [S6]

### G-ED-25: Browser upgrade breaks Content Analysis Connector
**Impact:** MEDIUM
**Symptom:** Web monitoring stops working after a Chrome or Edge major version update.
**Root cause:** Browser API changes in major versions may break the Content Analysis Connector. Symantec releases connector updates to match browser versions, but there can be a lag.
**Mitigation:** Test browser major version updates on a pilot group before enterprise-wide rollout. Check Broadcom release notes and KB articles for browser version compatibility.
**Evidence:** B [V-tribal]

---

## 8. Upgrade and Migration Gotchas

### G-ED-26: Agent auto-upgrade via LiveUpdate causes simultaneous network spike
**Impact:** MEDIUM
**Symptom:** Network bandwidth saturates when thousands of agents download updates simultaneously.
**Root cause:** Without a randomization window, all agents check for updates at their next polling interval and download simultaneously.
**Mitigation:** DLP 25.1+ supports LiveUpdate randomization windows. Set the randomization window to 4-8 hours to stagger agent updates across the window.
**Evidence:** A [S2]

### G-ED-27: Pre-15.7 agents cannot direct-upgrade to 16.0+
**Impact:** CRITICAL
**Symptom:** Upgrade fails. Agent becomes unresponsive or disconnected from server.
**Root cause:** There is no direct upgrade path from DLP 14.x or 15.0-15.5 agents to DLP 16.0+. An intermediate upgrade to 15.7 or 15.8 is required.
**Mitigation:** Follow the supported upgrade path: 14.x/15.0-15.5 -> 15.7 or 15.8 -> 16.0+. Plan for two upgrade cycles if starting from older versions. Use the Upgrade Readiness Tool (URT) before each upgrade.
**Evidence:** A [V-gotcha]

---

## 9. Platform-Specific Gotchas

### G-ED-28: macOS system extension approval blocks DLP functionality until approved
**Impact:** HIGH
**Symptom:** DLP agent is installed on macOS but no detection or prevention works.
**Root cause:** macOS 10.15+ requires explicit user approval for system extensions. Without approval, the DLP agent cannot hook into OS-level file and network operations.
**Mitigation:** Deploy an MDM profile that pre-approves the Symantec DLP system extension before agent installation. Without MDM, each user must manually approve in System Preferences > Security & Privacy > General > "Allow."
**Evidence:** A [S1, V-tribal]

### G-ED-29: macOS Full Disk Access required for Endpoint Discover
**Impact:** MEDIUM
**Symptom:** Endpoint Discover scans on macOS return no results or skip user directories.
**Root cause:** macOS privacy protections prevent applications from accessing user data directories (Desktop, Documents, Downloads) without Full Disk Access permission.
**Mitigation:** Grant Full Disk Access to the DLP Agent via MDM profile or manual approval in System Preferences > Security & Privacy > Privacy > Full Disk Access.
**Evidence:** A [S1]

### G-ED-30: Linux agents support Endpoint Discover ONLY -- no prevention channels
**Impact:** MEDIUM (expectations management)
**Symptom:** IT requests USB blocking on Linux endpoints but it is not available.
**Root cause:** Linux DLP agents (DLP 16.0+) support only Endpoint Discover (local drive scanning for data at rest). No prevention channels (USB, email, web, clipboard, etc.) are available on Linux.
**Mitigation:** For Linux endpoint protection, use Network DLP (Network Prevent for Email, Network Prevent for Web) to monitor data leaving Linux machines via network channels. Endpoint Discover on Linux can identify sensitive data at rest on Linux file systems.
**Evidence:** A [S1, S2]

---

## 10. Operational Gotchas

### G-ED-31: Outlook add-in conflicts with other Outlook add-ins
**Impact:** MEDIUM
**Symptom:** Outlook crashes, hangs, or runs slowly after DLP agent installation.
**Root cause:** The Symantec DLP Outlook add-in can conflict with other add-ins, particularly older antivirus email scanners, compliance tools, or custom add-ins.
**Mitigation:** Check for add-in conflicts in Outlook > File > Options > Add-ins. Disable conflicting add-ins or adjust load order. The DLP Outlook add-in should load before other content-scanning add-ins.
**Evidence:** B [V-tribal]

### G-ED-32: Agent log files consume disk space if not rotated
**Impact:** LOW
**Symptom:** Endpoint disk space gradually decreases. Agent log directory grows to several GB.
**Root cause:** Agent log rotation is configured with defaults (50 MB per file, 5 rotation files = 250 MB max). If logging is set to "Debug" level, logs can fill faster.
**Mitigation:** Keep agent log level at "Warning" for production. Only increase to "Debug" temporarily for troubleshooting. Verify log rotation settings in Agent Configuration > Advanced.
**Evidence:** A [S1, S18]

### G-ED-33: "Political backlash" from overly aggressive endpoint monitoring
**Impact:** HIGH (organizational, not technical)
**Symptom:** Employees resist DLP, file complaints with HR, or find workarounds (personal devices, phone photos of screens).
**Root cause:** Deploying aggressive blocking + clipboard monitoring + screen capture monitoring simultaneously creates a feeling of surveillance.
**Mitigation:** Communicate the DLP program purpose before agent deployment. Start with transparent monitoring (notifications that inform, not block). Engage HR and Legal in the communication plan. Executive sponsorship is critical. This is the single most common cause of DLP program failure.
**Evidence:** B [V-tribal, best practices]

### G-ED-34: No API for forcing immediate policy push to agents
**Impact:** MEDIUM
**Symptom:** During an active data breach, you need a blocking policy to take effect immediately on all endpoints but must wait up to 15 minutes.
**Root cause:** The DLP agent uses a pull model (polling) not a push model. There is no API or console mechanism to force immediate policy delivery.
**Mitigation:** For emergency response, combine DLP policy deployment with network-level controls (firewall rules, proxy blocks, DNS sinkholing) that take effect immediately while waiting for DLP policies to propagate.
**Evidence:** A [S1, API-intelligence]

---

## Gotcha Severity Summary

| Severity | Count | IDs |
|----------|-------|-----|
| CRITICAL | 1 | G-ED-27 |
| HIGH | 13 | G-ED-1, G-ED-2, G-ED-3, G-ED-8, G-ED-9, G-ED-10, G-ED-13, G-ED-15, G-ED-20, G-ED-23, G-ED-28, G-ED-33, G-ED-34 |
| MEDIUM | 16 | G-ED-4, G-ED-5, G-ED-6, G-ED-7, G-ED-11, G-ED-12, G-ED-16, G-ED-17, G-ED-18, G-ED-19, G-ED-22, G-ED-25, G-ED-26, G-ED-29, G-ED-30, G-ED-32 |
| LOW | 4 | G-ED-14, G-ED-21, G-ED-24, G-ED-31 |

[S1, S2, S3, S4, S6, S18, V12, V23, V29, V30, V-tribal, KB173958, KB176182, KB159522, API-intelligence] Evidence: A-B
