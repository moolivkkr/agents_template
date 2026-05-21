# Network DLP — Prerequisites
## Broadcom Symantec DLP (Enforce Server, version 16.x/25.x/26.x)

> **Purpose:** Infrastructure prerequisites, server placement requirements, integration dependencies, and dependency graph for network DLP.
> **Evidence sources:** doc-corpus.md [S1-S28], video-intelligence.md [V1-V45], api-intelligence.md

---

## 1. Infrastructure Prerequisites

### 1.1 Core Infrastructure (Required for All Network DLP)

| Component | Requirement | Version | Notes | Evidence |
|-----------|------------|---------|-------|----------|
| **Oracle Database** | Oracle Enterprise Edition | 19c (DLP 16.0+) | Stores all policies, incidents, scan results, quarantine records | A [S1, S4, V9] |
| **Enforce Server** | Central management hub | DLP 16.0+ / 25.1+ / 26.1 | Single Enforce Server manages all detection servers | A [S1, S4, V10] |
| **Web Browser** | Admin console access | Chrome, Firefox, Edge (current) | For Enforce console | A [S1] |

### 1.2 Per-Server-Type Prerequisites

#### Network Monitor Server

| Requirement | Specification | Notes | Evidence |
|-------------|-------------|-------|----------|
| OS | Linux (RHEL 7/8) recommended; Windows Server 2016+ | Linux preferred for network monitoring performance | A [S1, S19] |
| NICs | 2 minimum (management + monitoring) | Monitoring NIC dedicated to SPAN traffic; management NIC for Enforce communication | A [S1, S4] |
| Network tap/SPAN | Switch must support port mirroring | SPAN session configured to copy traffic to monitoring NIC | A [S1] |
| CPU | 4-16 cores (based on traffic volume) | More cores = higher throughput for concurrent session tracking | B [S9] |
| RAM | 8-32 GB | Packet reassembly buffers scale with RAM | B [S9] |
| Disk | 100-500 GB | Incident staging; log storage | B [S9] |
| Monitoring NIC | 1 Gbps or 10 Gbps (match monitored link speed) | NIC must handle full mirror traffic volume without drops | B [S9] |

#### Network Prevent for Email Server

| Requirement | Specification | Notes | Evidence |
|-------------|-------------|-------|----------|
| OS | Linux (RHEL 7/8) or Windows Server 2016+ | Same OS family as other detection servers recommended | A [S1, S19, S20] |
| MTA integration | Postfix, Sendmail, or Microsoft Exchange | MTA must be configured to route email through DLP | A [S1, S13] |
| Network | Reachable from MTA on DLP listen port (default: 10025) | Bidirectional: DLP returns inspected mail to MTA | A [S1, S13] |
| CPU | 4-16 cores (based on email volume) | Scales with messages per hour | B [S9] |
| RAM | 8-32 GB | Scales with concurrent email connections | B [S9] |
| Disk | 100 GB+ | Message staging during inspection | B [S9] |
| Optional: SMG | Symantec Messaging Gateway | Required for advanced quarantine workflows | A [S1, S14] |
| Optional: Encryption gateway | PGP Universal, ZixEncrypt, etc. | Required for email encryption response action | A [S1] |

#### Network Prevent for Web Server

| Requirement | Specification | Notes | Evidence |
|-------------|-------------|-------|----------|
| OS | Linux (RHEL 7/8) or Windows Server 2016+ | | A [S1, S19, S20] |
| Web proxy | ICAP-compliant proxy required | Blue Coat/ProxySG, Squid 3.5.x, Zscaler, Check Point, Cisco WSA, Palo Alto | A [S1, S15] |
| Network | Reachable from proxy on ICAP port (default: 1344 or 11344 for secure) | Proxy routes ICAP requests to DLP server | A [S1, S15] |
| CPU | 4-16 cores (based on concurrent ICAP connections) | | B [S9] |
| RAM | 8-32 GB | | B [S9] |
| Disk | 100 GB+ | | B [S9] |
| Optional: stunnel | For Secure ICAP with Squid | Squid does not natively support TLS ICAP; use stunnel | A [S15] |
| Keystore | JKS keystore for Secure ICAP | Path: `DetectionServer/keystore/secureicap.jks` | A [S15] |

#### Network Discover Server

| Requirement | Specification | Notes | Evidence |
|-------------|-------------|-------|----------|
| OS | Linux (RHEL 7/8) or Windows Server 2016+ | Windows required for DFS scan targets | A [S1, S19, S20] |
| Network | Reachable from target systems on relevant ports (SMB: 445, NFS: 2049, HTTP: 80/443, etc.) | Discover server initiates connections to scan targets | A [S1] |
| CPU | 4-16 cores (based on data volume) | High Speed Discovery (16.0+) benefits from 8+ cores | B [S9, S17] |
| RAM | 8-32 GB | Large scans benefit from more RAM for index caching | B [S9] |
| Disk | 200 GB+ (SSD recommended for High Speed Discovery) | Scan metadata, temporary content extraction | B [S9, S17] |
| Credentials | Service account with read access to all scan targets | Separate read and write accounts recommended | A [S1] |
| Optional: Write credentials | Service account with write access | Required for Protect actions (quarantine, encrypt) | A [S1] |

---

## 2. MTA Integration Prerequisites

### 2.1 Postfix

| Prerequisite | Details | Evidence |
|-------------|---------|----------|
| Postfix version | 2.10+ recommended | A [S13] |
| content_filter directive | Must be configurable in main.cf | A [S13] |
| master.cf edit access | Required for DLP return path configuration | A [S13] |
| Firewall | Allow MTA -> DLP:10025 and DLP -> MTA:10026 | A [S13] |
| DNS | DLP server must resolve MTA hostname | A [S13] |

### 2.2 Microsoft Exchange

| Prerequisite | Details | Evidence |
|-------------|---------|----------|
| Exchange version | 2016, 2019, or Exchange Online (hybrid) | A [S13] |
| Transport rule access | Exchange admin privileges to create Send Connectors and Transport Rules | A [S13] |
| Receive Connector | Must accept relay from DLP server IP | A [S13] |
| Firewall | Allow Exchange -> DLP:10025 and DLP -> Exchange:25 | A [S13] |

### 2.3 Symantec Messaging Gateway (SMG)

| Prerequisite | Details | Evidence |
|-------------|---------|----------|
| SMG version | 10.7+ | A [S14] |
| Content filtering license | SMG must be licensed for content filtering | A [S14] |
| X-header processing | SMG must be configured to read DLP X-headers | A [S14] |
| Quarantine storage | Sufficient disk space for quarantined messages | A [S14] |

---

## 3. Web Proxy Integration Prerequisites

### 3.1 Blue Coat / ProxySG

| Prerequisite | Details | Evidence |
|-------------|---------|----------|
| ProxySG version | 6.x+ or SGOS 7.x | A [S15] |
| ICAP license | External ICAP service support enabled | A [S15] |
| Admin access | Ability to create ICAP services and policy rules | A [S15] |
| Firewall | Allow ProxySG -> DLP:1344 (or 11344 for secure) | A [S15] |

### 3.2 Squid

| Prerequisite | Details | Evidence |
|-------------|---------|----------|
| Squid version | 3.5.x (verified compatible) | A [S15] |
| ICAP support | Squid compiled with `--enable-icap-client` | A [S15] |
| stunnel | Required for Secure ICAP (Squid lacks native TLS ICAP) | A [S15] |
| Firewall | Allow Squid -> DLP:1344 | A [S15] |

### 3.3 Other Proxies (Zscaler, Check Point, Cisco WSA, Palo Alto)

| Prerequisite | Details | Evidence |
|-------------|---------|----------|
| ICAP client support | Proxy must support RFC 3507 ICAP | A [S1] |
| REQMOD support | Proxy must support ICAP request modification | A [S1] |
| Connection pooling | Must be configurable to match DLP server settings | B [S9] |

---

## 4. Network Discover Target Prerequisites

### 4.1 Per-Target Credential Requirements

| Target Type | Credential Type | Minimum Permissions | Evidence |
|-------------|----------------|-------------------|----------|
| CIFS File Shares | Domain account (NTLM) | Read access to all scan roots. Write access for quarantine. | A [S1] |
| NFS File Shares | UID/GID | Read access to mount points | A [S1] |
| DFS Shares | Domain account (NTLM) | Read access. Windows Discover Server required. | A [S1] |
| SharePoint | Domain account (NTLM/Kerberos) | Read access to site collections. Site Collection Administrator for full access. | A [S1] |
| Exchange | Service account with Application Impersonation role | Impersonation rights to target mailboxes | A [S1] |
| SQL Databases | Database user with SELECT privilege | SELECT on target tables/views | A [S1] |
| Lotus Notes | Notes ID file + password | Reader access to target databases | A [S1] |
| Local File System | Local admin or service account | Read access to target paths | A [S1] |

### 4.2 Network Access Requirements

| Target Type | Protocol | Port | Direction | Evidence |
|-------------|----------|------|-----------|----------|
| CIFS | SMB | 445 | Discover -> File Server | A [S1] |
| NFS | NFS | 2049 | Discover -> NFS Server | A [S1] |
| SharePoint | HTTP/HTTPS | 80/443 | Discover -> SharePoint | A [S1] |
| Exchange | EWS HTTPS | 443 | Discover -> Exchange | A [S1] |
| SQL DB | JDBC | DB-specific (1521 for Oracle, 1433 for SQL Server) | Discover -> DB Server | A [S1] |
| Local FS | Local | N/A | Local access | A [S1] |

---

## 5. SSL/TLS Certificate Prerequisites

### 5.1 Network Monitor (SSL Inspection)

| Requirement | Details | Evidence |
|-------------|---------|----------|
| Server private key | Access to the private key of servers being monitored (for passive decryption) | A [S1] |
| OR SSL-offloading | Traffic must be decrypted upstream (e.g., at load balancer) before reaching SPAN port | A [S1] |
| Certificate store | JKS or PKCS12 keystore with private keys | A [S1] |

### 5.2 Network Prevent for Web (Secure ICAP)

| Requirement | Details | Evidence |
|-------------|---------|----------|
| Keystore | JKS keystore at `DetectionServer/keystore/secureicap.jks` | A [S15] |
| Server certificate | TLS certificate for DLP server (self-signed or CA-issued) | A [S15] |
| Proxy trust store | Proxy must trust the DLP server certificate | A [S15] |
| TLS version | TLS 1.2 or 1.3 | A [S1] |

---

## 6. Configuration Order

### 6.1 Recommended Setup Sequence

```
Step 1:  Oracle Database installed and running
           |
Step 2:  Enforce Server installed, connected to Oracle
           |
Step 3:  Plan network detection server topology
           |
Step 4:  Install detection server(s) in this order:
           |
           +-> Step 4a: Network Monitor (safest first -- passive only)
           |
           +-> Step 4b: Network Prevent for Email (requires MTA config)
           |
           +-> Step 4c: Network Prevent for Web (requires proxy config)
           |
           +-> Step 4d: Network Discover (requires target credentials)
           |
Step 5:  Verify all servers registered in Enforce console
           |
Step 6:  Configure policy groups (assign servers to groups)
           |
Step 7:  Create detection policies + response rules
           |
Step 8:  Test Network Monitor first (passive -- safe to enable)
           |
Step 9:  Test Network Prevent for Email (reflecting mode with fail-open)
           |
Step 10: Test Network Prevent for Web (ICAP with fail-open)
           |
Step 11: Configure and run first Network Discover scan (small target)
           |
Step 12: Expand to production traffic and full scan targets
```

**CRITICAL:** Always start with Network Monitor (passive) before enabling prevention (active blocking). Network Monitor provides visibility without risk. Use the incidents from monitoring to tune policies before enabling blocking on Email Prevent and Web Prevent. [S1, V-tribal]

[S1, S4, S9, S13, S15] Evidence: A

---

## 7. Capacity Planning Checklist

```
Network Monitor:
  [ ] SPAN/mirror port configured on core switch
  [ ] Monitoring NIC speed matches or exceeds monitored link
  [ ] 2 NICs (management + monitoring) on dedicated server
  [ ] Disk space for incident staging (100+ GB)

Network Prevent for Email:
  [ ] MTA routing configured (content_filter or transport rules)
  [ ] Fail-open/fail-closed strategy decided
  [ ] Return path port configured on MTA
  [ ] Firewall rules: MTA <-> DLP bidirectional
  [ ] Message size limit consistent between MTA and DLP
  [ ] SMG deployed if quarantine workflow needed

Network Prevent for Web:
  [ ] Web proxy ICAP configured
  [ ] ICAP concurrent connections matched on proxy and DLP
  [ ] Secure ICAP keystore generated (if TLS required)
  [ ] Fail-open configured on proxy (if DLP unreachable)
  [ ] Block page HTML customized

Network Discover:
  [ ] Service accounts created for all scan targets
  [ ] Read-only accounts for scanning; read-write for protect actions
  [ ] Network access verified from Discover server to all targets
  [ ] Scan schedule planned (off-hours for initial full scan)
  [ ] Quarantine location provisioned (if protect actions needed)
  [ ] Bandwidth limits set to avoid network saturation during scans
```

[S1, S4, S9, S13, S15, S17] Evidence: A-B
