# Prerequisites: Data Discovery (Network Discover)

> **Applies to:** Broadcom Symantec DLP 16.0 through 26.1
> **Purpose:** Everything that must be in place before you create your first discovery scan target

---

## Infrastructure Requirements

### 1. Enforce Server (Must Be Installed First)

| Requirement | Details |
|-------------|---------|
| Enforce Server | Installed and operational (hub of all DLP management) |
| Oracle Database | Oracle 19c+ backing the Enforce Server (or embedded DB for small deployments) |
| Web Console Access | Browser access to `https://enforce-server/ProtectManager` |
| Admin Account | Account with System Administration privilege |

### 2. Network Discover Server

| Requirement | Details |
|-------------|---------|
| Server Hardware | Dedicated server (physical or VM); not co-located with Enforce for production |
| Operating System | Windows Server 2016/2019/2022 or RHEL 7/8/9 |
| CPU | Minimum 8 cores; 16+ recommended for high-throughput scanning |
| RAM | Minimum 16 GB; 32 GB recommended for concurrent multi-target scans |
| Disk | 100 GB+ for temporary content extraction; SSD recommended for scan cache |
| Network | High-bandwidth connection to scan targets (1 Gbps+ recommended) |
| Registration | Must be registered with the Enforce Server and showing **Running** status |
| Policy Group | At least one policy group must be assigned to the Discover server |

**Verify the Discover server is online:**
```
Enforce Console > System > Servers and Detectors > Overview
  > Confirm Network Discover Server shows "Running"
```

### 3. Cloud Storage Discover Server (For Cloud Targets Only)

| Requirement | Details |
|-------------|---------|
| CloudSOC Account | Active Symantec CloudSOC subscription |
| Cloud Detection Service (CDS) | Enabled in CloudSOC admin settings |
| Cloud App Authorization | OAuth2 app credentials for target cloud services (Box, Google, Microsoft 365) |
| Network Access | Outbound HTTPS to cloud provider APIs |

---

## Credentials and Access Requirements

### File Share Scanning (CIFS/SMB)

| Requirement | Details |
|-------------|---------|
| Service Account | Active Directory domain account (e.g., `CORP\dlp-scanner-svc`) |
| Permission Level | **Read** access to all shares being scanned (for Discover) |
| Write Permission | **Read + Write** only if using Network Protect actions (quarantine, encrypt) |
| Account Type | Managed Service Account (gMSA) recommended for automatic password rotation |
| Authentication | NTLM or Kerberos (Kerberos preferred for security) |

**Verify access from the Discover server:**
```cmd
# From the Network Discover Server, test share access:
dir \\fileserver01\share-name\
# Must list files without error
```

### SharePoint Scanning

| Requirement | Details |
|-------------|---------|
| Service Account | Domain account with SharePoint access |
| Permission Level | **Site Collection Reader** on all site collections to scan |
| Authentication | NTLM (most common), Kerberos, or Claims-based |
| SharePoint Version | SharePoint 2013, 2016, 2019, or Subscription Edition |
| Network Access | HTTPS access from Discover server to SharePoint web front-end |

### Exchange / Mailbox Scanning

| Requirement | Details |
|-------------|---------|
| Service Account | Domain account with Exchange permissions |
| Permission Level | **ApplicationImpersonation** management role |
| Exchange Version | Exchange 2013, 2016, 2019, or Exchange Online (via CloudSOC) |
| Connection Type | EWS (Exchange Web Services) recommended for Exchange 2016+ |
| Network Access | HTTPS access from Discover server to Exchange CAS/EWS endpoint |

**Grant ApplicationImpersonation in Exchange Management Shell:**
```powershell
New-ManagementRoleAssignment -Name "DLP Scanner Impersonation" `
  -Role ApplicationImpersonation `
  -User "CORP\dlp-exchange-svc" `
  -CustomRecipientWriteScope "DLP Scan Scope"
```

### Database Scanning

| Requirement | Details |
|-------------|---------|
| Database Account | Database user with SELECT-only permission |
| JDBC Driver | Appropriate JDBC driver installed on the Discover server |
| Supported Databases | Oracle 12c+, SQL Server 2014+, DB2 10.5+ |
| Network Access | TCP access from Discover server to database listener port (1433, 1521, 50000) |

**JDBC driver installation:**
- Place the JDBC JAR file in the Discover server's `lib` directory
- Restart the Discover server service after adding the driver

### Cloud Storage Scanning

| Requirement | Details |
|-------------|---------|
| CloudSOC Subscription | Active Symantec CloudSOC/CASB license |
| Cloud App Registration | OAuth2 application registered in each cloud service |
| Admin Consent | Global admin consent for API access (Microsoft 365, Google Workspace) |
| Box Enterprise | Box Enterprise or Business Plus account (not Starter/Business) |

---

## Policy Requirements

### Minimum Policy Setup

Before running any scan, you need at least one active detection policy in the Discover server's policy group:

1. **Check policy group assignment:**
   ```
   System > Servers and Detectors > [Discover Server] > Policy Group
   ```

2. **Create or verify a policy exists in that group:**
   ```
   Manage > Policies > Policy List
   ```
   - If no policies exist, create one from a template (e.g., "US Social Security Numbers")
   - Ensure the policy is assigned to the correct policy group
   - Ensure the policy is **enabled** (not in Disabled state)

3. **Policy modes for discovery:**
   | Mode | Behavior |
   |------|----------|
   | Test Without Notifications | Incidents created but no notifications sent (safest for initial scan) |
   | Test With Notifications | Incidents created, notifications sent (but no Protect actions) |
   | Production | Incidents created, notifications sent, Protect actions execute |

---

## Network Requirements

### Firewall Rules

| Source | Destination | Port | Protocol | Purpose |
|--------|-------------|------|----------|---------|
| Discover Server | Enforce Server | 443 | HTTPS/TLS | Management, policy deployment, incident reporting |
| Discover Server | File Servers | 445 | SMB/CIFS | File share scanning |
| Discover Server | NFS Servers | 2049 | NFS | NFS share scanning |
| Discover Server | SharePoint | 443 | HTTPS | SharePoint scanning |
| Discover Server | Exchange | 443 | HTTPS/EWS | Mailbox scanning |
| Discover Server | Databases | 1433/1521/50000 | JDBC | Database scanning |
| Discover Server | SFTP Servers | 22 | SSH | SFTP target scanning |
| CloudSOC | Cloud APIs | 443 | HTTPS | Box, Google, Microsoft 365 scanning |

### DNS Resolution

- The Discover server must resolve all target hostnames
- For CIFS scanning, NetBIOS name resolution may be required (WINS or lmhosts)
- For DFS scanning, the Discover server must resolve DFS namespace roots

---

## Licensing Requirements

| Component | License Required |
|-----------|-----------------|
| Network Discover | Symantec DLP Network Discover license |
| Network Protect | Symantec DLP Network Protect license (add-on for remediation actions) |
| Cloud Storage Discover | CloudSOC CASB license + Cloud DLP license |
| High Speed Discovery | Included with Network Discover license (DLP 16.1+) |
| OCR for Discovery | Sensitive Image Recognition add-on license |

---

## Pre-Scan Checklist

Use this checklist before creating your first scan target:

- [ ] Enforce Server is installed and accessible via web console
- [ ] Network Discover Server is installed, registered, and showing "Running" status
- [ ] At least one detection policy exists in the Discover server's policy group
- [ ] Service account credentials are created for target type (file share, SharePoint, Exchange, DB)
- [ ] Service account has appropriate read permissions on the target
- [ ] Network connectivity verified from Discover server to target (ping, telnet to port)
- [ ] Firewall rules allow traffic from Discover server to target on required ports
- [ ] DNS resolution works from Discover server to target hostnames
- [ ] JDBC driver installed (for database scanning only)
- [ ] Sufficient disk space on Discover server for temporary content extraction (100 GB+)
- [ ] Scan window identified (off-hours recommended for initial full scans)
- [ ] Incident review process defined (who reviews discovery incidents?)
