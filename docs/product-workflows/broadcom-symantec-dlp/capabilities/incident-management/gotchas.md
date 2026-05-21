# Gotchas: Incident Management

> **Source:** Broadcom TechDocs, Video Intelligence Report, API Intelligence Report, Community KB articles
> **Impact Ratings:** CRITICAL = data loss or compliance failure; HIGH = significant operational impact; MEDIUM = workflow friction; LOW = minor inconvenience

---

## Incident Volume Management

### 1. Untuned Policies Generate Overwhelming Incident Volume (CRITICAL)

**Problem:** Deploying policies without tuning generates thousands of incidents per day. At this volume, analysts cannot review them, critical incidents get buried, and the DLP program loses credibility.

**Symptoms:** Incident queue shows 10,000+ unreviewed incidents; analysts stop checking; high-severity incidents missed for days.

**Mitigation:**
- Start all policies in "Test Without Notifications" mode
- Tune policies (add exceptions, refine rules) until false positive rate is below 15%
- Only then switch to enforcement mode
- Deploy policies incrementally: one policy at a time, not all at once
- Use severity levels to prioritize: only High/Critical incidents require human review initially

### 2. Discovery Scans Flood the Incident Queue (HIGH)

**Problem:** A single Network Discover scan of a large file share can generate 50,000+ incidents. These discovery incidents overwhelm the incident queue and obscure real-time email/endpoint incidents.

**Symptoms:** After a discover scan completes, the incident list is dominated by discover incidents; email/endpoint incidents pushed to page 50+.

**Mitigation:**
- Use separate incident views for different channels (Incidents > Discover vs. Incidents > Network)
- Create saved searches for non-discovery incidents
- Use the "Limit Incident Data Retention" response rule to auto-purge old discovery incidents
- Review discovery incidents in a separate workflow from real-time incident triage

### 3. Incident Database Growth Degrades Console Performance (HIGH)

**Problem:** The Oracle database backing the Enforce Server grows continuously with incident data. Millions of incidents with full evidence degrade console responsiveness.

**Symptoms:** Incident list takes 30+ seconds to load; dashboard rendering is slow; report generation times out.

**Mitigation:**
- Define and enforce an incident retention policy (e.g., purge resolved incidents older than 180 days)
- Use the "Limit Incident Data Retention" response rule to automatically purge evidence data
- Archive incidents before purging (export to CSV/JSON via API)
- Optimize Oracle database: regular statistics gathering, index maintenance
- DLP 26.1 dashboards support up to 12 reports; older versions limit to 6

---

## False Positive Management

### 4. False Positive Rate Is 40-60% for New Deployments (HIGH)

**Problem:** Out-of-the-box policy templates match broadly. Without tuning, nearly half of incidents are false positives. This wastes analyst time and erodes trust.

**Symptoms:** Analysts report that most incidents they review are not real violations; team morale drops; management questions DLP value.

**Mitigation:**
- **Policy tuning cycle**: Run policy in test mode -> review 100 incidents -> identify false positive patterns -> add exceptions -> repeat
- **Data identifier validation**: Use data identifiers with validators (e.g., credit card with Luhn check) instead of raw regex
- **Compound rules**: Combine multiple conditions (e.g., credit card number AND sender is external AND file type is spreadsheet)
- **Policy exceptions**: Whitelist known-good senders, recipients, domains, file names
- **Feedback loop**: Track false positive rate per policy; target < 15%

### 5. Marking False Positive Does Not Automatically Tune the Policy (MEDIUM)

**Problem:** When an analyst marks an incident as "False Positive", it only changes the incident status. The policy is not automatically adjusted to prevent similar false positives.

**Symptoms:** Same type of false positive recurs day after day; analysts mark it false positive each time; no policy improvement.

**Mitigation:**
- Establish a **policy feedback process**: Weekly review of all "False Positive" incidents grouped by policy
- Policy admin reviews patterns and adds exceptions or refines rules
- Track false positive rate per policy over time to measure improvement
- Consider creating a "Configuration Error" status for incidents that indicate the policy itself needs fixing

---

## Evidence and Privacy

### 6. Evidence Storage Contains Actual Sensitive Data (CRITICAL)

**Problem:** When DLP captures evidence (matched content, original messages), the DLP system itself now stores sensitive data -- credit card numbers, SSNs, health records. The DLP database becomes a target.

**Symptoms:** Security audit finds that the DLP Enforce database contains unencrypted PCI data; the DLP system itself becomes a compliance risk.

**Mitigation:**
- Enable database encryption (Oracle TDE) on the Enforce database
- Use the "Limit Incident Data Retention" response rule to purge evidence after a defined period
- Restrict "View Masked Data" privilege to only personnel who need it
- Use content masking: configure policies to store only partial matches (e.g., last 4 digits of credit card)
- Include the DLP system in your organization's data handling and access control policies

### 7. Incident History Is Immutable -- Cannot Delete Notes or History (LOW)

**Problem:** Once a note is added to an incident or a status change is made, it is permanently recorded in the audit trail. There is no "undo" or "delete note" function.

**Symptoms:** Analyst adds incorrect note to wrong incident; sensitive information typed into notes cannot be removed.

**Mitigation:**
- Train analysts to review before saving notes
- Add a corrective note if a mistake is made ("Previous note was added in error; disregard")
- The immutable audit trail is actually a compliance benefit for regulatory audits

---

## Workflow and Assignment

### 8. No Built-in Round-Robin Assignment (MEDIUM)

**Problem:** Symantec DLP does not have native round-robin or load-balanced incident assignment. Incidents default to "Unassigned" and require manual pickup or external automation.

**Symptoms:** Some analysts get overloaded while others have empty queues; incidents sit unassigned.

**Mitigation:**
- Use SOAR integration (XSOAR, ServiceNow) for automated assignment
- Create a custom automation script using the REST API to distribute incidents
- Alternatively, assign incidents by policy type (PCI analyst, HIPAA analyst) rather than round-robin
- DLP 26.1 Incident Workflows provide some automation capability natively

### 9. Status Transitions Are Not Enforced (MEDIUM)

**Problem:** Any analyst can change an incident from any status to any other status. There is no enforcement of a workflow sequence (e.g., must go New -> In Process -> Resolved, not New -> Resolved directly).

**Symptoms:** Analysts skip investigation steps; incidents marked "Resolved" without proper review.

**Mitigation:**
- Establish and document a standard operating procedure (SOP) for incident handling
- Use custom attributes to track workflow compliance (e.g., "Investigation Completed: Yes/No")
- DLP 26.1 Incident Workflows add formalized workflow capabilities
- SOAR playbooks can enforce workflow order

### 10. Analyst Can See Incidents Outside Their Responsibility (MEDIUM)

**Problem:** If roles are not properly scoped, analysts can see incidents for policies or departments outside their area. This is both an efficiency and privacy concern.

**Symptoms:** PCI analyst sees HIPAA incidents; US analyst sees EU GDPR incidents they should not access.

**Mitigation:**
- Define roles with **Incident Access** scoped to specific policies or policy groups
- Create separate roles for PCI analysts, HIPAA analysts, GDPR analysts
- Use the role-based report visibility to control who sees which dashboards

---

## API and Integration Issues

### 11. REST API Polling Has No Push/Webhook Alternative (HIGH)

**Problem:** Symantec DLP does not support webhooks or event streaming. SOAR platforms must poll the REST API at intervals, introducing latency between incident creation and SOAR response.

**Symptoms:** SOAR playbook does not trigger until the next polling cycle (e.g., 5 minutes); high-severity incidents have a delay before automated response.

**Mitigation:**
- Set polling interval as low as practical (1-2 minutes for high-priority environments)
- Use syslog response rules for near-real-time event notification to SIEM/SOAR
- Combine: syslog for real-time alerting + API polling for detailed incident data

### 12. API Does Not Support Smart Response Execution (MEDIUM)

**Problem:** Smart Response rules can only be triggered from the Enforce Console UI. There is no API endpoint to execute a Smart Response programmatically.

**Symptoms:** SOAR playbook cannot trigger Smart Responses; must use direct API operations (status change, note, email) instead.

**Mitigation:**
- Replicate Smart Response logic in your SOAR playbook using individual API calls:
  - `PATCH /incidents` to change status and custom attributes
  - Send notification via SOAR's email capability
  - Log to syslog via SOAR's syslog integration
- This achieves the same outcome without the Smart Response button

### 13. SOAP API Deprecated But Still Required by Some Integrations (MEDIUM)

**Problem:** The SOAP API was deprecated in DLP 16.0 in favor of REST, but some older integrations (SCCM plugins, legacy scripts) still rely on it. The SOAP API remains functional but is no longer enhanced.

**Symptoms:** Legacy scripts break after DLP upgrade if SOAP endpoint changes; no new features in SOAP API.

**Mitigation:**
- Migrate all integrations from SOAP to REST API
- REST API covers all SOAP incident operations plus additional capabilities
- SOAP WSDL: `https://enforce/ProtectManager/services/v2011/incidents?wsdl`
- REST base URL: `https://enforce/ProtectManager/webservices/v2/`

---

## Operational Issues

### 14. Bulk Operations Are Limited to 500 Incidents (MEDIUM)

**Problem:** The Enforce Console limits bulk operations (status change, export) to the incidents visible on the current page or selected. Processing thousands of incidents requires multiple batches.

**Symptoms:** Analyst needs to resolve 5,000 discovery incidents after a scan; must do it in batches of 100.

**Mitigation:**
- Use the REST API for bulk operations -- `PATCH /incidents` supports updating multiple incidents in a single request
- Create automation scripts for large-scale incident management operations
- Example: Script that queries all "New" Discover incidents older than 90 days and sets status to "Resolved"

### 15. Incident Export Includes Evidence by Default (MEDIUM)

**Problem:** Exporting incidents to CSV or JSON includes matched content snippets. If the export file is emailed or stored insecurely, it becomes a data leak of the very data DLP is protecting.

**Symptoms:** Compliance officer requests incident report; analyst emails CSV containing credit card number snippets to the officer.

**Mitigation:**
- Establish a secure channel for incident report sharing (encrypted file share, secure portal)
- Use role-based access to restrict who can export incidents
- Configure content masking in reports where possible
- Train analysts that incident exports contain sensitive data and must be handled accordingly

### 16. Timezone Discrepancies Between Console and API (LOW)

**Problem:** The Enforce Console displays timestamps in the server's local timezone (or the user's configured timezone), while the REST API returns timestamps in UTC. This can cause confusion when correlating.

**Symptoms:** Console shows incident at "2:30 PM EST" but API returns "2026-05-21T19:30:00Z"; analyst thinks they are different incidents.

**Mitigation:**
- Standardize on UTC for all programmatic operations
- Document the timezone behavior for analysts
- API date filter parameters accept ISO 8601 format with timezone designator

### 17. Deleted Detection Server Orphans Its Incidents (LOW)

**Problem:** If a detection server is removed from the deployment, incidents generated by that server remain in the database but their "Detection Server" field references a server that no longer exists.

**Symptoms:** Old incidents show "Unknown Server" in the detection server field; no impact on data but confusing for analysts.

**Mitigation:** Before decommissioning a detection server, archive or bulk-resolve all incidents from that server. The incidents are preserved for compliance but should be marked as historical.
