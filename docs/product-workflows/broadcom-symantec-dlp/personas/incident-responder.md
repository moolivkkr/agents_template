# Persona: SOC Analyst / Incident Responder

> **Product:** Broadcom Symantec Data Loss Prevention
> **Persona:** SOC Analyst / Incident Responder
> **RBAC Requirement:** Incident access (scoped by role) + Smart Response execution privileges
> **Typical Title:** SOC Analyst, DLP Incident Responder, Security Operations Analyst, Data Protection Analyst

---

## Role Overview

The Incident Responder is the operational persona in Symantec DLP. This role interacts primarily with DLP incidents after detection: triaging by severity, investigating matched content, determining whether incidents are true positives or false positives, executing remediation actions, and feeding tuning recommendations back to the Policy Author.

This is the highest-volume persona. In a typical enterprise deployment, Incident Responders handle tens to hundreds of incidents daily. Efficiency depends on well-tuned policies (set by the Policy Author) and automation (SOAR integrations, automated response rules, ServiceNow workflows).

This persona is the **heaviest API user**. The incident management API is the most mature and comprehensive surface in Symantec DLP, and SOAR platforms (Cortex XSOAR, FortiSOAR, Swimlane) consume it extensively.

**Key responsibilities:**
- Triage incoming DLP incidents by severity and policy type
- Investigate incident details (matched content, sender/recipient, policy, detection context)
- Determine true positive vs. false positive
- Execute Smart Response remediation actions
- Escalate high-severity incidents
- Provide tuning feedback to Policy Authors (false positive patterns, missing exceptions)
- Manage incident lifecycle (New > In Process > Resolved/False Positive/Escalated)
- Integrate with SIEM, SOAR, and ticketing systems

---

## Triage > Investigate > Remediate > Tune Workflow

```
                        INCIDENT RESPONDER WORKFLOW
  ============================================================================

  +-----------+     +-------------+     +-------------+     +-----------+
  |  TRIAGE   |     | INVESTIGATE |     | REMEDIATE   |     |   TUNE    |
  |  (2 min)  |---->|  (5-15 min) |---->|  (2-10 min) |---->| (ongoing) |
  +-----------+     +-------------+     +-------------+     +-----------+
  |             |   |               |   |               |   |             |
  | Review      |   | View matched  |   | Execute Smart |   | Report FP   |
  | severity    |   | content       |   | Response      |   | patterns to |
  | and policy  |   |               |   |               |   | Policy      |
  |             |   | Check sender/ |   | Set status    |   | Author      |
  | Check       |   | recipient     |   | (Resolved,    |   |             |
  | detection   |   |               |   | FP, Escalated)|   | Suggest new |
  | channel     |   | Review file   |   |               |   | exceptions  |
  | (Network,   |   | properties    |   | Add notes/    |   |             |
  | Endpoint,   |   |               |   | justification |   | Identify    |
  | Discover)   |   | Check user    |   |               |   | missing     |
  |             |   | risk score    |   | Trigger SOAR  |   | detection   |
  | Prioritize  |   | (ICA)         |   | playbook      |   | rules       |
  | by severity |   |               |   |               |   |             |
  | High > Med  |   | Review        |   | Notify data   |   |             |
  | > Low       |   | incident      |   | owner         |   |             |
  |             |   | history       |   |               |   |             |
  +-----------+     +-------------+     +-------------+     +-----------+
       |                  |                   |                    |
       |    API: POST     |  API: GET         | API: PATCH         |
       |    /incidents    |  /incidents/{id}  | /incidents          |
       |    (query)       |  /components      | (update status,     |
       |                  |  /history         |  notes, attributes) |
       |                  |  /originalMessage |                     |
       v                  v                   v                    v
  +------------------------------------------------------------------+
  |                     SOAR / SIEM INTEGRATION                       |
  |  Cortex XSOAR | FortiSOAR | Swimlane | Splunk SOAR | ServiceNow |
  +------------------------------------------------------------------+
```

---

## Step-by-Step Narrative

### Step 1: Triage (2 minutes per incident)

**Console Navigation:** Incidents > [Network | Endpoint | Discover] > Incident List

The responder starts their shift by reviewing the incident queue. Incidents are sorted by severity (High > Medium > Low > Informational) and timestamp. The incident list shows summary information: incident ID, severity badge, policy name, detection server type, sender/recipient, file name, timestamp.

**Triage decision tree:**

```
Is severity HIGH?
  YES --> Investigate immediately (SLA: 1 hour)
  NO --> Is severity MEDIUM?
    YES --> Queue for investigation (SLA: 4 hours)
    NO --> Is severity LOW?
      YES --> Batch review (SLA: 24 hours)
      NO --> Informational -- review weekly or skip
```

**API for triage:**
```
POST /ProtectManager/webservices/v2/incidents
Body: { "reportId": <saved_report_id>, "filters": [...], "pageSize": 50 }
```
This endpoint supports nested AND/OR filters, allowing SOAR platforms to pull new incidents matching specific criteria (severity, policy, time range) automatically.

---

### Step 2: Investigate (5-15 minutes per incident)

**Console Navigation:** Incidents > [Click incident] > Incident Snapshot

The Incident Snapshot screen provides:

| Tab/Section | Information | API Endpoint |
|------------|-------------|-------------|
| **Summary** | Incident ID, severity, status, policy name, detection server, timestamp | `GET /incidents/{id}` |
| **Matches** | Matched content snippets, policy rules triggered, match count | `GET /incidents/{id}/components` |
| **Original Message** | Full original content that triggered the incident | `GET /incidents/{id}/originalMessage` |
| **History** | Audit trail of all actions taken on this incident | `GET /incidents/{id}/history` |
| **Custom Attributes** | LDAP-enriched or manually set attributes (department, manager, data owner) | Included in `GET /incidents/{id}` |

**Investigation checklist:**

1. **Review matched content** -- Is the detected content actually sensitive? Does it match the policy intent?
2. **Check sender/recipient context** -- Is this an internal transfer (likely legitimate) or external (likely violation)?
3. **Review file properties** -- File name, type, size -- does the file contain what the policy expected?
4. **Check user risk score** -- If ICA is integrated, is this a high-risk user (repeat offender, departing employee)?
5. **Review incident history** -- Has this user/sender triggered similar incidents before?
6. **Determine classification:**
   - **True Positive**: Content is sensitive and the transmission violates policy
   - **False Positive**: Content matched the pattern but is not actually sensitive
   - **Policy Tuning Needed**: Detection is too broad or too narrow

---

### Step 3: Remediate (2-10 minutes per incident)

**Console Navigation:** Incident Snapshot > [Action buttons and dropdowns]

#### 3.1 Smart Response Rules (Manual Remediation)

Smart Response rules are manually triggered by the responder from the Incident Snapshot screen. They are limited to administrative actions:

| Action | Description | API Automatable? |
|--------|------------|-----------------|
| Set Status | Change incident status (New, In Process, Resolved, False Positive, Escalated) | YES -- `PATCH /incidents` |
| Add Note | Add investigation notes/justification | YES -- `PATCH /incidents` (incidentNotes field) |
| Send Email Notification | Notify data owner, manager, or compliance officer | Console-triggered |
| Log to Syslog | Send event to SIEM for correlation | Console-triggered |

**Limitations:** Smart Response rules CANNOT block, quarantine, encrypt, or modify content. Those are Automated Response rule actions only.

#### 3.2 Automated Response Rules (Pre-Configured)

These fire automatically when incidents are created. The responder does not trigger them manually but observes their effects:

| Server Type | Available Automated Actions |
|-------------|---------------------------|
| **Network Prevent for Email** | Block message, modify headers, redirect, quarantine (SMG), encrypt |
| **Network Prevent for Web** | Block request, allow, remove sensitive content |
| **Endpoint Prevent** | Block data transfer, notify user, encrypt file, User Cancel prompt |
| **Network Discover/Protect** | Quarantine file, copy to secure location, encrypt, apply DRM |
| **Cloud/CASB** | Block sharing, quarantine, add 2FA, apply classification label |
| **All Servers** | Log to syslog, set status, set attribute, send email notification |

#### 3.3 Incident Status Workflow

```
  [New] --> [In Process] --> [Resolved]
    |            |
    |            +--> [False Positive]
    |            |
    |            +--> [Configuration Error]
    |
    +--> [Escalated] --> (reassigned to senior analyst or manager)
```

Custom status values can be defined at: System > Incident Data > Attributes > Custom Attributes

---

### Step 4: SOAR Integration for Automated Response

SOAR platforms are the primary automation vehicle for incident response. Symantec DLP integrates with multiple SOAR platforms via the Enforce Server REST API.

#### Cortex XSOAR (Palo Alto Networks) -- Official v2 Integration

| Command | DLP API | Description |
|---------|---------|-------------|
| `symantec-dlp-list-incidents` | `POST /incidents` | Fetch incidents with filters |
| `symantec-dlp-get-incident-details` | `GET /incidents/{id}` | Get full incident details |
| `symantec-dlp-update-incident` | `PATCH /incidents` | Update status, severity, notes |
| `symantec-dlp-get-incident-history` | `GET /incidents/{id}/history` | Get audit trail |
| `symantec-dlp-get-incident-original-message` | `GET /incidents/{id}/originalMessage` | Get original content |
| `symantec-dlp-list-custom-attributes` | `GET /incidents/listCustomAttributes` | List custom attributes |
| `symantec-dlp-list-incident-status` | `GET /incidents/incidentStatuses` | List status values |

#### FortiSOAR (Fortinet) -- v2.2.0 Connector

| Action | DLP API | Description |
|--------|---------|-------------|
| Get Incidents List | `POST /incidents` | Query incidents with filters |
| Get Incident Details | `GET /incidents/{id}` | Full details |
| Update Incident | `PATCH /incidents` | Status, notes, custom attributes |
| Get Custom Status | `GET /incidents/incidentStatuses` | Custom status enumeration |

#### Swimlane Turbine -- Connector

| Action | DLP API | Description |
|--------|---------|-------------|
| Get Incidents | `POST /incidents` | Query with report ID + filters |
| Get Incident Original Message | `GET /incidents/{id}/originalMessage` | Evidence retrieval |
| Update Incident | `PATCH /incidents` | Bulk incident updates |

#### ServiceNow -- DLP Incident Response Integration

| Capability | Mechanism | Direction |
|-----------|-----------|-----------|
| Import DLP incidents as ServiceNow records | Scheduled sync job | DLP > ServiceNow |
| View matched data types and violation snippets | Data mapping | DLP > ServiceNow |
| Update incident status in DLP from ServiceNow | Bidirectional sync | ServiceNow > DLP |
| Assign to data owner for remediation | End User Remediation (15.8+) | Bidirectional |
| Auto-enroll violators in security training | Workflow automation | ServiceNow |

**ServiceNow is the recommended integration for End User Remediation** -- decentralized incident resolution where data owners (not security analysts) remediate their own violations.

---

### Step 5: Tune (Ongoing)

Tuning is the feedback loop from incident response back to policy authoring. The responder identifies patterns that indicate policies need adjustment.

| Pattern Observed | Tuning Action | Who Acts |
|-----------------|---------------|----------|
| High FP rate from email disclaimers | Add content exception for standard disclaimer | Policy Author |
| FP from known test data | Add exception for test credit card patterns | Policy Author |
| User group should be exempt | Add directory group exception | Policy Author |
| Policy too sensitive (low threshold) | Increase match threshold | Policy Author |
| New data type not detected | Create new detection rule or EDM profile | Policy Author |
| Repeat offender from departing employee | Escalate to HR/Legal; increase monitoring | Policy Author + Management |

**API-driven tuning signal:**
```
POST /ProtectManager/webservices/v2/incidents
Filter: status = "False Positive", groupBy = "policyName"
```
This query identifies which policies generate the most false positives, prioritizing tuning efforts.

---

## Incident Management API -- Complete Reference for Responders

| # | Method | Path | Description | Since |
|---|--------|------|-------------|-------|
| 1 | POST | `/incidents` | Query incidents with filters (nested AND/OR, pagination) | 15.7 |
| 2 | GET | `/incidents/{id}` | Get full incident details | 15.7 |
| 3 | PATCH | `/incidents` | Update status, severity, notes, custom attributes (bulk) | 15.7 |
| 4 | GET | `/incidents/{id}/history` | Get incident audit trail | 15.8 |
| 5 | GET | `/incidents/{id}/originalMessage` | Retrieve original triggering content | 15.8 |
| 6 | GET | `/incidents/{id}/components` | Get matched content and policy details | 15.7 |
| 7 | GET | `/incidents/incidentStatuses` | List all custom status values | 15.7 |
| 8 | GET | `/incidents/incidentEditable` | List editable incident attributes | 15.7 |
| 9 | GET | `/incidents/preventActionStatuses` | Prevent action status values | 15.7 |
| 10 | GET | `/incidents/protectActionStatuses` | Protect action status values | 15.7 |
| 11 | GET | `/incidents/listCustomAttributes` | List all custom attributes | 15.7 |
| 12 | POST | `/incidents/export` | Export incidents as JSON | 16.0 |
| 13 | GET | `/reports/{id}/filters` | Retrieve saved report filter criteria | 16.0 |

**Authentication:**
- HTTP Basic over TLS (primary)
- Kerberos (16.0 RU2+)
- Certificate-based (16.0 RU2+)
- JWT with configurable IdP (26.1+)

**Base URL:** `https://<enforce>:443/ProtectManager/webservices/v2/`

---

## Syslog / SIEM Integration for Responders

Incidents can be forwarded to SIEM in near-real-time via syslog response rules. The responder monitors these in their SIEM console alongside other security events.

**CEF Message Format:**
```
CEF:0|Broadcom|DLP|16.0|<ruleID>|$POLICY$|5|
INCIDENT_ID=$INCIDENT_ID$
APPLICATION_USER=$APPLICATION_USER$
ENDPOINT_MACHINE=$ENDPOINT_MACHINE$
ENDPOINT_USERNAME=$ENDPOINT_USERNAME$
MACHINE_IP=$MACHINE_IP$
SEVERITY=$SEVERITY$
BLOCKED=$BLOCKED$
```

**Supported SIEMs:**
- Splunk (official Add-on for Symantec DLP)
- Microsoft Sentinel (CEF via AMA connector)
- Google Chronicle (native parser)
- IBM QRadar / JSA (DSM for Symantec DLP)
- LogRhythm (CEF parser)
- ManageEngine EventLog Analyzer (built-in support)
- Any SIEM supporting syslog/CEF ingestion

---

## Incident Volume Management

| Strategy | Implementation | Impact |
|----------|---------------|--------|
| Severity-based triage | Address High first, batch Low/Informational | Reduces time-to-response for critical incidents |
| Incident data retention limits | Response rule: "Limit Incident Data Retention" on high-volume policies | Prevents database bloat from noisy policies |
| Automated status assignment | Response rule: auto-set status for certain policy matches | Reduces manual triage for known-good patterns |
| Custom attributes for routing | Lookup plugins populate department, manager, data owner | Enables automated incident assignment |
| SOAR playbook automation | Auto-triage, auto-enrich, auto-route based on severity + policy | Reduces manual effort by 50-70% |
| End User Remediation (ServiceNow) | Data owners remediate their own incidents | Decentralizes workload away from SOC |

---

## Time Estimates

| Activity | Time per Incident | Daily Volume (typical) | Daily Time |
|----------|-------------------|----------------------|------------|
| Triage (severity review) | 2 minutes | 50-200 incidents | 1.5-6.5 hours |
| Investigation (full review) | 5-15 minutes | 10-50 incidents (High/Medium only) | 1-12.5 hours |
| Remediation (status + action) | 2-10 minutes | 10-50 incidents | 0.3-8 hours |
| Tuning feedback | -- | Weekly aggregate | 2-4 hours/week |

**With SOAR automation:** Triage time drops by 50-70% (automated filtering + enrichment). Investigation time drops by 30% (pre-enriched context). Remediation drops by 40% (automated status updates for clear-cut cases).

---

*Incident Responder persona covering the full triage-investigate-remediate-tune workflow with comprehensive API reference and SOAR integration details.*
