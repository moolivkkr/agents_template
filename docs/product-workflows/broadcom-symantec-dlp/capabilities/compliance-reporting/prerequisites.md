# Prerequisites: Compliance Reporting

> **Applies to:** Broadcom Symantec DLP 16.0 through 26.1
> **Purpose:** Everything that must be in place before generating meaningful DLP compliance reports

---

## Incidents Must Exist

The most fundamental prerequisite: reports summarize incidents. Without incidents, reports are empty.

### Minimum for Meaningful Reporting

| Requirement | Why | How to Verify |
|-------------|-----|---------------|
| Active detection policies | Policies generate incidents when violations occur | Manage > Policies > Policy List -- at least one Enabled policy |
| Running detection servers | Servers execute policies against content | System > Servers and Detectors > Overview -- at least one Running server |
| Data flowing through DLP | Content must pass through detection points | Check: email via MTA integration, web via proxy/ICAP, endpoints via agents |
| Sufficient time window | Meaningful trends require at least 30 days of data | Wait for at least one month of incident data before generating compliance reports |

### Data at Rest (Discovery) Reports

For discovery reports specifically:

| Requirement | Why |
|-------------|-----|
| Network Discover Server running | Generates discover incidents |
| At least one completed scan | Scan results populate discover incidents |
| Scan targets configured | Define what to scan (file shares, SharePoint, etc.) |

---

## User Roles for Reporting

### Role Privileges Required

| Privilege | Required For | Navigation |
|-----------|-------------|------------|
| **View Incidents** | See any incident data in reports | System > Login Management > Roles |
| **View Reports** | Access saved reports and dashboards | Must be enabled for reporting roles |
| **Create/Edit Reports** | Create and modify saved searches | For analysts who build custom reports |
| **View Masked Data** | See unmasked content in incident details | For investigators who need full evidence |
| **System Administration** | Access system event reports and audit logs | For IT/security admins |

### Recommended Reporting Roles

| Role | Access Level | Assigned To |
|------|-------------|------------|
| Compliance Reporter | View Incidents + View Reports (scoped to compliance policies) | Compliance officers |
| DLP Analyst | View + Create Reports + View Masked Data | SOC analysts |
| Executive Viewer | View Reports (dashboards only, no incident detail) | CISO, VP Security |
| Audit Access | View Incidents + View Reports + System Administration (audit logs) | Internal/external auditors |

### Incident Access Scope

Reports only include incidents the user's role is authorized to see:

| Role Configuration | Report Content |
|-------------------|----------------|
| Role sees all incidents | Report includes all incidents matching filters |
| Role sees only PCI policy incidents | Report includes only PCI incidents, even if other filters are broader |
| Role sees only US office incidents | Report includes only incidents from US detection servers |

**Configuration:** System > Login Management > Roles > [role] > Incident Access

---

## SMTP Configuration (For Scheduled Reports)

Scheduled report delivery requires email sending capability:

| Requirement | Details |
|-------------|---------|
| SMTP Server | Configured in System > Settings > General |
| From Address | Valid email address (e.g., `dlp-reports@corp.com`) |
| Relay Permission | SMTP server must accept mail from the Enforce Server |
| TLS | Recommended for email security |

**Verify:** Send a test email from the Enforce Console to confirm SMTP is working.

---

## Syslog Configuration (For SIEM Forwarding)

If compliance reporting includes SIEM-correlated DLP data:

| Requirement | Details |
|-------------|---------|
| Syslog Server | Running and accessible from Enforce Server |
| Protocol | UDP (port 514) or TCP (port 514 or custom) |
| Firewall | Port open from Enforce Server to syslog server |
| Format | CEF recommended for structured parsing |
| Response Rule | At least one "Log to Syslog" response rule active |

---

## Custom Attributes (Recommended for Compliance Reports)

Custom attributes add compliance-relevant context to incidents:

| Attribute | Purpose | Helps With |
|-----------|---------|------------|
| Regulatory Scope | Tag incidents by regulation (PCI, HIPAA, GDPR) | Filter reports by regulation |
| Department | Business unit of the user involved | Department-level compliance metrics |
| Cost Center | Financial grouping | Cost allocation for DLP program |
| Resolution Category | Why the incident was resolved | Compliance outcome analysis |
| Risk Assessment | Analyst-assigned risk level | Risk-based reporting |

**Navigation:** System > Incident Data > Attributes > Custom Attributes tab

These should be defined before incidents start flowing so that lookup plugins can auto-populate them from the beginning.

---

## Policy Tagging for Compliance Reports

For regulatory compliance reports, policies should be organized by regulation:

### Policy Naming Convention

Use a consistent naming convention that includes the regulation:
- `PCI-DSS-CreditCard-Email`
- `HIPAA-PHI-Endpoint`
- `GDPR-EU-PII-CloudStorage`
- `SOX-FinancialData-Discover`

This enables filtering reports by regulation using the "Policy Name contains" filter.

### Policy Group Organization

Alternatively, organize policies into compliance-oriented policy groups:
- "PCI DSS Compliance Group" -- all PCI-related policies
- "HIPAA Compliance Group" -- all HIPAA-related policies
- "GDPR Compliance Group" -- all GDPR-related policies

---

## Database Sizing for Report Performance

Reports query the Oracle database. Performance depends on data volume:

| Metric | Impact on Reporting |
|--------|-------------------|
| Total incidents | More incidents = slower queries |
| Evidence storage | Large evidence blobs increase DB size |
| Concurrent report users | Multiple users running reports simultaneously |
| Date range | Wider date ranges = more data to scan |

### Recommendations

| Database Size | Report Performance | Action |
|--------------|-------------------|--------|
| < 1 million incidents | Fast (< 5 seconds) | No optimization needed |
| 1-5 million incidents | Moderate (5-30 seconds) | Ensure Oracle statistics are current |
| 5-20 million incidents | Slow (30+ seconds) | Add Oracle indexes; consider partitioning |
| > 20 million incidents | Very slow | Implement incident archival; consider dedicated reporting replica |

---

## Pre-Launch Checklist for Compliance Reporting

- [ ] At least 30 days of incident data exists for trending
- [ ] Policies are named with regulatory tags (PCI, HIPAA, GDPR) for easy filtering
- [ ] Reporting roles are created and assigned to compliance staff
- [ ] Incident access is scoped appropriately per role
- [ ] Custom attributes are defined (Regulatory Scope, Department, Resolution Category)
- [ ] LDAP lookup plugin auto-populates Department and Manager fields
- [ ] SMTP is configured for scheduled report delivery
- [ ] Syslog is configured if SIEM integration is required
- [ ] Dashboards are created for executive, operational, and compliance views
- [ ] Report naming convention is documented
- [ ] Incident retention policy is defined and aligns with regulatory requirements
- [ ] Oracle database performance is acceptable for report workloads
