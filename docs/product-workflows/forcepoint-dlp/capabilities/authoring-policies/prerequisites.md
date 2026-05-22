# Forcepoint DLP Policy Authoring -- Prerequisites

> Dependency chain for Forcepoint DLP policy authoring. Everything that must be in place
> before you can create, test, and deploy DLP policies.

---

## 1. Infrastructure Dependencies

### 1.1 Forcepoint Management Server

| Requirement | Detail |
|-------------|--------|
| Component | Forcepoint Security Manager (FSM) |
| Role | Central management console for all DLP operations |
| Required for | Policy creation, classifier management, incident viewing, deployment |
| Minimum version | v9.0 for REST API support; v10.x recommended for AI Mesh and latest features |
| OS | Windows Server (see deployment guide for specific OS versions per DLP version) |
| Database | Microsoft SQL Server (for incident storage, policy configuration) |
| Network | Must be reachable by all DLP components (agents, protectors, gateways) |

### 1.2 DLP Components (At Least One Required)

| Component | Purpose | Required For |
|-----------|---------|-------------|
| **Endpoint Agent** | Monitors data on user devices (USB, print, clipboard, local files) | Endpoint channel policies |
| **Network Protector** | Inspects network traffic (email, web, FTP) | Network channel policies |
| **Email Gateway Integration** | Inspects and controls email flow | Email-specific policies (quarantine, encrypt) |
| **Cloud Gateway / CASB** | Monitors cloud application usage | Cloud channel policies |
| **Discovery Engine** | Scans data at rest (file shares, databases, cloud storage) | Data discovery tasks |

**Minimum viable deployment:** Management Server + 1 Endpoint Agent OR 1 Network Protector.

### 1.3 Database Requirements

| Component | Purpose |
|-----------|---------|
| SQL Server | Stores incidents, policy configurations, fingerprint data |
| Fingerprint Database | Stores document and database fingerprints (on management server, pushed to components) |

### 1.4 OCR Server (Optional)

| Requirement | Detail |
|-------------|--------|
| When needed | If you need to scan images, scanned PDFs, or screenshots for sensitive content |
| How to install | Included in supplemental Forcepoint DLP server installations |
| Limitations | Max file size: 25 MB; Min file size: 5 KB; No handwriting; Text skew < 10 degrees |

---

## 2. Software and Licensing

### 2.1 License Requirements

| License | Enables |
|---------|---------|
| **Forcepoint DLP** (base) | Core policy authoring, predefined classifiers, incident management |
| **Forcepoint DLP Endpoint** | Endpoint agent deployment and endpoint channel policies |
| **Forcepoint DLP Network** | Network protector and network channel monitoring |
| **Forcepoint DLP Cloud** | Cloud application monitoring and CASB integration |
| **Forcepoint DLP Discovery** | Data-at-rest scanning (file shares, databases, cloud storage) |
| **Risk-Adaptive Protection (RAP)** | UEBA-based dynamic policy enforcement (5 risk levels) |
| **Forcepoint Data Classification** | AI Mesh classification labels integration |
| **Forcepoint ONE Data Security (SaaS)** | Cloud-native DLP (alternative to on-prem) |

### 2.2 Deployment Options

| Option | Description | License Model |
|--------|-------------|---------------|
| **On-premises** | Management server and components in your data center | Per-user or per-device |
| **SaaS (Forcepoint ONE)** | Cloud-hosted management and enforcement | Subscription |
| **Hybrid** | On-prem management with cloud enforcement points | Combined |

---

## 3. Access and Permissions

### 3.1 Administrator Roles

| Role | Can Do | Cannot Do |
|------|--------|-----------|
| **Super Administrator** | Everything: policy CRUD, deploy, incidents, system config | N/A |
| **Policy Administrator** | Create/edit policies, classifiers, rules | System configuration, user management |
| **Incident Administrator** | View/manage incidents, change status, assign | Create/edit policies |
| **Application Administrator** | REST API access (JWT authentication) | UI access (API only) |
| **Read-Only Administrator** | View policies and incidents | Make any changes |

### 3.2 For REST API Access

- Must create an **Application Administrator** account in FSM
- Only this account type can request refresh tokens via the REST API
- Credentials are used to obtain JWT tokens for API authentication

### 3.3 For Active Directory Integration

| Requirement | Purpose |
|-------------|---------|
| AD connectivity | User and group resolution for source/destination filtering |
| Service account | FSM needs a service account to query AD for user/group information |
| OU structure | Policy sources reference AD OUs, groups, or user objects |

---

## 4. Network Prerequisites

### 4.1 Communication Paths

```
Endpoint Agents  <--->  Management Server  (policy download, incident upload)
Network Protector <--->  Management Server  (policy download, incident upload)
Email Gateway     <--->  Management Server  (policy download, incident upload)
Cloud Gateway     <--->  Management Server  (policy download, incident upload)
Admin Browser     <--->  Management Server  (HTTPS for Security Manager UI)
SIEM Server       <--->  Management Server  (syslog for incident forwarding)
REST API Client   <--->  Management Server  (HTTPS for API calls)
```

### 4.2 Required Ports

| Port | Protocol | Direction | Purpose |
|------|----------|-----------|---------|
| 443 (HTTPS) | TCP | Inbound to FSM | Security Manager UI and REST API |
| Various (see deploy guide) | TCP | FSM <-> Components | Policy push and incident upload |
| 514 | UDP/TCP | FSM -> SIEM | Syslog incident forwarding |

---

## 5. Data Prerequisites

### 5.1 Before Creating Policies

| Data Needed | Purpose | How to Obtain |
|-------------|---------|---------------|
| Sensitive data inventory | Know what you are protecting | Data classification exercise, DSPM scan |
| Data flow map | Know how sensitive data moves | Network analysis, user interviews |
| Compliance requirements | Know which regulations apply | Legal/compliance team input |
| User/group structure | Know who accesses what data | AD/HR system integration |
| Approved destinations | Know legitimate data flows | Business process documentation |

### 5.2 Before Fingerprinting

| Data Needed | Purpose |
|-------------|---------|
| Database connection credentials | For database fingerprinting (SQL Server, Oracle, MySQL, Salesforce, CSV) |
| File share paths | For file system fingerprinting (UNC paths or local paths) |
| Training documents (ML) | For machine learning classifiers (100+ positive and 100+ negative examples) |
| File access permissions | FSM service account needs read access to fingerprint targets |

---

## 6. Organizational Prerequisites

### 6.1 People

| Role | Responsibility in Policy Authoring |
|------|-----------------------------------|
| **DLP Administrator** | Creates and manages policies, classifiers, and action plans |
| **Data Owner / Steward** | Defines what data is sensitive and how it should be classified |
| **Compliance Officer** | Specifies regulatory requirements driving policy creation |
| **Security Analyst** | Triages incidents, tunes policies based on false positive analysis |
| **IT Operations** | Deploys and maintains DLP infrastructure components |
| **HR / Legal** | Approves monitoring policies, handles employee privacy considerations |

### 6.2 Process

| Process | When | Purpose |
|---------|------|---------|
| Data classification workshop | Before policy creation | Agree on data categories and sensitivity levels |
| Policy review cycle | Monthly or quarterly | Tune thresholds, add/remove classifiers, update exceptions |
| Incident review meeting | Weekly | Review high-severity incidents, identify trends, update policies |
| Change management | Before each deployment | Approve policy changes, assess business impact |
| Exception approval | As needed | Approve legitimate business exceptions to DLP policies |

---

## 7. Dependency Chain Diagram

```
Level 0 (Foundation)
  |-- Windows Server + SQL Server installed
  |-- Network connectivity verified
  |-- Licenses activated
  |
Level 1 (Infrastructure)
  |-- Forcepoint Security Manager installed
  |-- Management server operational
  |-- AD integration configured
  |
Level 2 (Components)
  |-- At least one DLP component deployed:
  |     Endpoint Agent OR Network Protector OR Email Gateway OR Cloud Gateway
  |-- Initial deployment (Deploy button) successful
  |-- Component status: green/healthy
  |
Level 3 (Data)
  |-- Sensitive data inventory complete
  |-- Data flow map documented
  |-- Compliance requirements identified
  |-- (Optional) Fingerprint sources accessible
  |-- (Optional) ML training data prepared
  |
Level 4 (Policy Authoring) <-- YOU ARE HERE
  |-- Content classifiers created/selected
  |-- Rules defined with condition logic
  |-- Action plans configured
  |-- Policies assembled and enabled
  |-- Policies deployed
  |
Level 5 (Operations)
  |-- Incidents monitored and triaged
  |-- Policies tuned based on incident data
  |-- Regular review cycles established
  |-- SIEM/SOAR integration active (optional)
```

---

## 8. Version Compatibility Matrix

| Feature | v8.9.x | v9.0 | v10.0 | v10.1+ | v10.3+ | v10.4+ |
|---------|--------|------|-------|--------|--------|--------|
| Predefined policies | Yes | Yes | Yes | Yes | Yes | Yes |
| Custom policies | Yes | Yes | Yes | Yes | Yes | Yes |
| REST API | Limited | Yes | Yes | Enhanced | Enhanced | Enhanced |
| RAP integration | Partial | Yes | Yes | Yes | Yes | Yes |
| AI Mesh labels | No | No | Partial | Yes | Yes | Yes |
| Drip DLP | Yes | Yes | Yes | Yes | Yes | Yes |
| OCR | Yes | Yes | Yes | Yes | Yes | Cloud OCR added |
| Database fingerprinting | Yes | Yes | Yes | Yes | Yes | Yes |
| ML classifiers | Yes | Yes | Yes | Yes | Yes | Yes |
| ARIA assistant | No | No | No | No | No | Yes (latest) |
| Deploy API | No | Yes | Yes | Yes | Yes | Yes |
| Policy import/export API | No | Yes | Yes | Yes | Yes | Yes |

---

## 9. Quick Validation Checklist

Run through this before starting policy authoring:

```
[ ] 1. Can you log in to Forcepoint Security Manager?
[ ] 2. Is the Data Security module visible in the navigation?
[ ] 3. Can you see Main > Policy Management > DLP Policies?
[ ] 4. Are predefined policies listed (should see 50+ policies)?
[ ] 5. Can you see Main > Policy Management > Content Classifiers?
[ ] 6. Does the Deploy button appear in the toolbar?
[ ] 7. Is at least one component showing "healthy" status in system modules?
[ ] 8. Can you navigate to Main > Reporting > Incident Manager?
[ ] 9. (For fingerprinting) Can the management server reach target databases/file shares?
[ ] 10. (For REST API) Has an Application Administrator account been created?
```

If all checks pass, proceed to [quickstart.md](quickstart.md).
