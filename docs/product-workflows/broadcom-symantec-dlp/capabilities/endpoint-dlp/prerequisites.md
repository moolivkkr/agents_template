# Endpoint DLP — Prerequisites
## Broadcom Symantec DLP (Enforce Server, version 16.x/25.x/26.x)

> **Purpose:** Infrastructure prerequisites, agent deployment requirements, connectivity requirements, and dependency graph for endpoint DLP.
> **Evidence sources:** doc-corpus.md [S1-S28], video-intelligence.md [V1-V45], api-intelligence.md

---

## 1. Infrastructure Prerequisites

### 1.1 Core Infrastructure (Required)

| Component | Requirement | Version | Notes | Evidence |
|-----------|------------|---------|-------|----------|
| **Oracle Database** | Oracle Enterprise Edition | 19c (DLP 16.0+) | Stores all policies, incidents, agent state. Embedded DB available for <250 agents. | A [S1, S4, V9] |
| **Enforce Server** | Central management hub | DLP 16.0+ / 25.1+ / 26.1 | Single Enforce Server per deployment. Hosts console, manages all detection servers. | A [S1, S4, V10] |
| **Endpoint Prevent Server** | Agent communication hub | Same version as Enforce | At least 1 required. Receives agent check-ins, distributes policies, collects incidents. | A [S1, S4, V11] |
| **Web Browser** | Enforce console access | Chrome, Firefox, Edge (current versions) | For admin console access. | A [S1] |

### 1.2 Endpoint Prevent Server Requirements

| Requirement | Specification | Notes | Evidence |
|-------------|-------------|-------|----------|
| OS | Windows Server 2016+ or RHEL 7/8 | Match Enforce Server version requirements | A [S19, S20] |
| CPU | 4+ cores (8 recommended for 1000+ agents) | Scales with agent count and incident volume | B [S9] |
| RAM | 8 GB minimum (16 GB recommended) | More RAM = more concurrent agent connections | B [S9] |
| Disk | 100 GB+ for incident staging | Incidents cached on server before database write | B [S9] |
| Network | Accessible from all agent locations (LAN, VPN, DMZ) | Port 443 (TLS) by default | A [S1, S4] |
| Certificates | TLS certificate for agent-to-server communication | Self-signed or CA-issued. Must be trusted by agents. | A [S1] |

### 1.3 Endpoint Prevent Server Sizing

| Agent Count | Endpoint Servers | Configuration | Evidence |
|-------------|-----------------|---------------|----------|
| 1-250 | 1 (single) | Can co-locate with Enforce for POC | B [S9] |
| 250-1000 | 2 (primary + failover) | Separate servers in same LAN | B [S9] |
| 1000-5000 | 4 (2 LAN + 2 DMZ) | Load-balanced with source IP persistence | A [KB173958] |
| 5000-10000 | 6-8 (3-4 LAN + 3-4 DMZ) | Multiple load balancers, regional placement | B [KB173958] |
| 10000+ | 8+ with regional distribution | Consult Broadcom Professional Services | B [S9] |

**CRITICAL:** Load balancer must use "Source IP persistence" set to 24 hours when deploying multiple Endpoint Servers behind a load balancer. Without this, agents may report to different servers between check-ins, causing split incident data and broken policy enforcement. [KB173958, V-tribal]

---

## 2. Endpoint Agent Requirements

### 2.1 Supported Operating Systems

| OS | Version | Architecture | DLP Version | Channel Coverage | Evidence |
|----|---------|-------------|-------------|-----------------|----------|
| Windows 10 | 1809+ | x64 | 15.5+ | Full (all 12 channels) | A [S1, S4] |
| Windows 11 | 21H2+ | x64 | 16.0+ | Full (all 12 channels) | A [S1, S2] |
| Windows 11 | 21H2+ | ARM64 | 25.1+ | Full (all 12 channels) | A [S2] |
| Windows Server | 2016, 2019, 2022, 2025 | x64 | 15.5+ (2025: 25.1+) | Full | A [S1, S2] |
| macOS | 11+ (Big Sur+) | x64, Apple Silicon | 16.0+ | Partial (email, web, USB write, clipboard, local drives) | A [S1, S2] |
| Linux | RHEL 7/8, Ubuntu 18.04+ | x64 | 16.0+ | Endpoint Discover only (local drive scanning) | A [S1, S2] |

### 2.2 Endpoint Agent Software Requirements

| Requirement | Windows | macOS | Linux | Evidence |
|-------------|---------|-------|-------|----------|
| .NET Framework | 4.5.2+ (DLP 15.x), 4.7.2+ (DLP 16.0+) | N/A | N/A | A [S1, S20] |
| Disk space | 500 MB minimum | 300 MB minimum | 200 MB minimum | A [S1] |
| RAM | 512 MB available | 512 MB available | 256 MB available | B [S1] |
| Admin rights | Required for installation | Required for installation | Root required | A [S1] |
| Network connectivity | Port 443 to Endpoint Server | Port 443 to Endpoint Server | Port 443 to Endpoint Server | A [S1] |

### 2.3 Windows-Specific Requirements

| Feature | Requirement | Notes | Evidence |
|---------|------------|-------|----------|
| HVCI compatibility | Windows 11 with HVCI enabled | DLP 16.0+ supports Hypervisor-protected Code Integrity | A [S1] |
| LSA Protection | Windows 11 with LSA Protection | DLP 25.1+ supports Local Security Authority protection | A [S2] |
| Virtual Desktop | Citrix, VMware Horizon, Azure VD | DLP 26.1+ supports VDI/Virtual App environments | A [S3] |
| Browser extensions | Chrome, Edge, Firefox | Content Analysis Connectors require browser extension installation | A [S1, S6] |
| Outlook add-in | Microsoft Outlook 2016+ / Microsoft 365 | Email channel requires Outlook add-in | A [S1] |

### 2.4 macOS-Specific Requirements

| Feature | Requirement | Notes | Evidence |
|---------|------------|-------|----------|
| System Extensions | macOS 10.15+ system extension approval | Required for kernel-level monitoring. Must approve in System Preferences > Security & Privacy. | A [S1] |
| MDM profile | Recommended for silent approval | Deploy MDM profile to pre-approve DLP system extension | B [V-tribal] |
| Full Disk Access | Required for Endpoint Discover | Grant Full Disk Access to DLP Agent in Privacy settings | A [S1] |
| Gatekeeper | Must allow DLP agent installation | Notarized installer or MDM bypass | A [S1] |

---

## 3. Network and Connectivity Requirements

### 3.1 Required Network Ports

| Source | Destination | Port | Protocol | Purpose | Evidence |
|--------|------------|------|----------|---------|----------|
| DLP Agent | Endpoint Prevent Server | 443 | HTTPS (TLS 1.2/1.3) | Agent check-in, policy download, incident upload | A [S1, S4] |
| Endpoint Prevent Server | Enforce Server | 443 | HTTPS (TLS 1.2/1.3) | Policy distribution, incident forwarding | A [S1, S4] |
| Enforce Server | Oracle Database | 1521 | Oracle Net (encrypted) | Policy/incident data storage | A [S1, S4] |
| Admin Browser | Enforce Server | 443 | HTTPS | Console access | A [S1] |
| DLP Agent | DNS | 53 | UDP/TCP | Hostname resolution for Endpoint Server FQDN | A [S1] |
| DLP Agent | AD/LDAP | 389/636 | LDAP/LDAPS | Agent group membership resolution | A [S1] |

### 3.2 Firewall Rules

```
REQUIRED:
  Agent -> Endpoint Server:443        (TLS, bidirectional, persistent)
  Endpoint Server -> Enforce:443      (TLS, bidirectional)
  Enforce -> Oracle:1521              (Oracle Net, bidirectional)
  Agent -> DNS:53                     (UDP/TCP)

OPTIONAL:
  Agent -> LDAP:389/636               (for DGM, if agent resolves groups)
  Endpoint Server -> Syslog:514       (UDP/TCP, if syslog response rule)
  Enforce -> SMTP:25                  (for email notifications)
```

### 3.3 VPN and Remote Access

| Scenario | Requirement | Notes | Evidence |
|----------|------------|-------|----------|
| Split-tunnel VPN | Agent traffic must route to Endpoint Server | Ensure DLP traffic is NOT split-tunneled (must go through corporate network or DMZ) | B [V-tribal] |
| Full-tunnel VPN | Works by default | All traffic routes through corporate network | A [S1] |
| No VPN (remote) | DMZ Endpoint Server required | Agents connect directly to DMZ-facing Endpoint Server via internet | A [KB173958] |
| Zero Trust / ZTNA | Agent must have direct path to Endpoint Server | ZTNA policies must allow agent-to-server communication on port 443 | B [V-tribal] |

---

## 4. Browser Extension Prerequisites

### 4.1 Content Analysis Connector Requirements

| Browser | Extension | Installation Method | Prerequisites | Evidence |
|---------|-----------|--------------------|--------------| ---------|
| Chrome | Symantec DLP Content Analysis | Chrome Web Store or GPO force-install | Extension ID must be in Chrome admin allowlist | A [S1, S6] |
| Edge | Symantec DLP Content Analysis | Edge Add-ons or GPO force-install | Same extension as Chrome (Chromium-based) | A [S1, S6] |
| Firefox | Symantec DLP Firefox Connector | Firefox Add-ons or enterprise policy | DLP 16.0.1+ required | A [S6] |

### 4.2 Browser Admin Policy (Chrome/Edge)

To deploy browser extensions silently via Group Policy:

```
Chrome GPO Path:
  Computer Configuration > Administrative Templates > Google Chrome > Extensions
  "Configure the list of force-installed apps and extensions"
  Value: <extension_id>;https://clients2.google.com/service/update2/crx

Edge GPO Path:
  Computer Configuration > Administrative Templates > Microsoft Edge > Extensions
  "Control which extensions are installed silently"
  Value: <extension_id>;https://edge.microsoft.com/extensionwebstorebase/v1/crx
```

[S1, S6] Evidence: A

---

## 5. Encryption Integration Prerequisites

### 5.1 For Endpoint Prevent Encrypt Action

| Component | Requirement | Notes | Evidence |
|-----------|------------|-------|----------|
| Symantec Endpoint Encryption | SEE 11.x+ installed on endpoint | Provides encryption engine for USB encrypt response action | A [S1, S4] |
| BitLocker | Windows BitLocker enabled | Alternative encryption provider for USB drives | B [S1] |
| MIP/RMS | Microsoft Information Protection SDK on Enforce Server | For MIP label-based encryption response action | A [S1, S2] |

---

## 6. Configuration Order

### 6.1 Recommended Setup Sequence

```
Step 1: Oracle Database installed and running
          |
Step 2: Enforce Server installed, connected to Oracle
          |
Step 3: Endpoint Prevent Server installed, registered with Enforce
          |
Step 4: Agent Package built (FQDN addressing recommended)
          |
Step 5: Agent Configuration created (channels, thresholds)
          |
Step 6: Agent Groups defined (AD/OU criteria)
          |
Step 7: Policies created with response rules
          |
Step 8: Policies assigned to policy group targeting Endpoint Server
          |
Step 9: Agent deployed to test machines (validate registration)
          |
Step 10: Test detection on all enabled channels
          |
Step 11: Expand deployment to production endpoints
```

**CRITICAL:** Steps 3-8 must be completed BEFORE deploying agents. If agents are deployed without an Endpoint Prevent Server running or without policies assigned, agents will register but not enforce anything. [S1, S4, V12]

[S1, S4, V9, V10, V11, V12] Evidence: A

---

## 7. Upgrade Prerequisites

### 7.1 Agent Upgrade Path

| Current Version | Target Version | Prerequisites | Evidence |
|----------------|---------------|---------------|----------|
| 15.5 agent | 16.0 agent | Upgrade Enforce + Endpoint Server to 16.0 FIRST. Agent auto-upgrades on next check-in (if LiveUpdate enabled). | A [S1] |
| 15.7/15.8 agent | 16.0 agent | Same as above. Direct upgrade supported. | A [S1] |
| 16.0 agent | 25.1 agent | Upgrade Enforce + Endpoint Server to 25.1 FIRST. LiveUpdate with randomization window (25.1+). | A [S2] |
| Pre-15.7 agent | 16.0+ agent | CANNOT direct upgrade. Must upgrade to 15.7/15.8 first, then to 16.0+. | A [V-gotcha] |

**CRITICAL:** Always upgrade the server infrastructure (Oracle, Enforce, Detection Servers) BEFORE upgrading agents. Agent upgrades happen automatically via LiveUpdate when the server is upgraded. Upgrading agents before servers causes protocol mismatches and failed check-ins. [S1, V-gotcha]

---

## 8. Capacity Planning Checklist

```
[ ] Oracle DB disk space: 50 GB base + 1 GB per 1000 incidents/month
[ ] Enforce Server: 16 GB RAM, 8 cores for 5000+ agents
[ ] Endpoint Server(s): 1 server per 1000-2500 agents (sizing varies by incident volume)
[ ] Load balancer configured with Source IP persistence = 24 hours
[ ] Network bandwidth: ~50 KB per agent per check-in (15-min interval)
[ ] DNS resolution: All agents can resolve Endpoint Server FQDN
[ ] Firewall rules: Port 443 open from all agent locations to Endpoint Server(s)
[ ] Browser extension deployment: GPO or MDM for Chrome/Edge/Firefox
[ ] Encryption provider: SEE or BitLocker deployed if Encrypt action needed
[ ] AD/LDAP connectivity: For agent group membership and DGM policies
[ ] Syslog server: For incident forwarding to SIEM
[ ] Incident storage: Plan for incident volume (1 incident = ~5-50 KB depending on content capture)
```

[S1, S4, S9, KB173958] Evidence: A-B
