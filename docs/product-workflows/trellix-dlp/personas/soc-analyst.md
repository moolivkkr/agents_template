# SOC Analyst -- Workflow Summary

> Generated: 2026-05-21 | Capability: Authoring Policies (downstream consumer) | Persona: Secondary

---

## Role Overview

The SOC Analyst is the primary consumer of DLP policy output. They do NOT author policies but triage DLP incidents, review evidence, correlate violations with other security events, and escalate to Policy Administrators when rule tuning is needed. Their workflow begins where the Policy Administrator's ends -- after policies are deployed and violations start generating incidents.

**Typical profile:** Security Operations Center analyst (Tier 1/2), Incident Response specialist, or Compliance Monitoring analyst with read access to ePO DLP Incident Manager and Queries & Reports.

**Prerequisite knowledge:** ePO console navigation, incident triage methodology, organizational data classification taxonomy, SIEM query language (Splunk SPL, Chronicle UDM, etc.).

---

## Daily Flow

```
+------------------+   +-------------------+   +------------------+   +-----------------+   +-------------------+
| 1. Review        | > | 2. Triage         | > | 3. Retrieve      | > | 4. Correlate    | > | 5. Escalate or    |
| Incident Queue   |   | by Severity       |   | Evidence         |   | with SIEM       |   | Close             |
| (continuous)     |   | (5-10 min/event)  |   | (2-5 min/event)  |   | (10-15 min)     |   | (5 min)           |
|                  |   |                   |   |                  |   |                 |   |                   |
| DLP Incident     |   | Critical > High > |   | Evidence file    |   | Cross-reference |   | False positive:   |
| Manager or       |   | Medium > Low      |   | from ePO or      |   | DLP event with  |   | close + request   |
| SIEM dashboard   |   |                   |   | REST API         |   | login, endpoint, |   | rule tuning       |
|                  |   |                   |   |                  |   | network events  |   | True positive:    |
| API: FULL        |   | API: FULL         |   | API: FULL        |   | API: PARTIAL    |   | escalate to IR    |
+------------------+   +-------------------+   +------------------+   +-----------------+   +-------------------+
```

---

## Capability Touchpoints

| Capability | How Used | Frequency | Complexity | API Automatable? |
|-----------|---------|-----------|------------|-----------------|
| DLP Incident Manager | Primary incident review interface | Continuous (real-time monitoring) | LOW -- table view with filters | YES -- `/rest/dlp/event/incidents` |
| Incident Detail View | Deep-dive into individual violations | Per-incident (5-50/day) | LOW -- read-only detail page | YES -- `/rest/dlp/event/incident/{id}` |
| Evidence Retrieval | View captured data that triggered the rule | Per-incident (when needed) | MEDIUM -- decryption required | YES -- `/rest/dlp/event/evidence/get` |
| ePO Queries & Reports | Trend analysis, compliance dashboards | Daily/Weekly | MEDIUM -- query builder | YES -- `core.executeQuery` |
| SIEM Integration | Correlated view of DLP + other events | Continuous | HIGH -- requires parser config | YES -- syslog (CEF/LEEF) |
| Rule Tuning Requests | Feedback loop to Policy Administrator | Weekly (based on FP rate) | N/A (communication, not config) | NO -- human process |
| Incident Manager Filters | Narrow incidents by rule, severity, user, date | Per-session | LOW -- UI filters | PARTIAL (API supports query params) |

---

## Narrative

### 1. Review Incident Queue (Continuous)

**Screen:** Menu > Data Protection > DLP Incident Manager (ePO console)
**Alternative:** SIEM dashboard (Splunk, Chronicle, Devo) receiving DLP events via syslog

**Actions:**
- Open DLP Incident Manager in ePO
- Filter incidents by date range, severity, rule name, or user
- Sort by severity (Critical first) or timestamp (newest first)
- Scan for high-volume rules that may indicate a data exfiltration attempt or a noisy false-positive rule

**Incident fields visible:**
| Field | Description |
|-------|-------------|
| Incident ID | Unique identifier |
| Date/Time | When the violation occurred |
| User | The endpoint user who triggered the rule |
| Computer | The managed system where the violation occurred |
| Rule Name | Which DLP rule was triggered |
| Severity | Critical / High / Medium / Low / Informational |
| Action Taken | What the DLP agent did (Monitor, Block, Encrypt, etc.) |
| Classification | Which classification matched |
| Channel | Data channel (Email, Web, USB, etc.) |

**API:** FULL -- Query incidents programmatically:
```
GET /rest/dlp/event/incidents
```
Returns incident IDs for data-in-use or data-in-motion events. Can be polled on a schedule or triggered via OpenDXL subscription.

**SIEM integration:** DLP events forwarded via syslog (CEF/LEEF format). Supported SIEMs:
- Splunk (`TA-trellix-epo` Technology Add-on)
- Google Chronicle (native `trellix-dlp` parser)
- Devo (native Trellix DLP collector)
- Elastic (community, not native -- requested in GitHub issue #164115)
- Any SIEM supporting CEF over syslog

---

### 2. Triage by Severity (5-10 min per event)

**Screen:** DLP Incident Manager > click incident row > Incident Detail

**Actions:**
- Open the incident detail to see full context:
  - Exact content that matched (if evidence stored)
  - Classification criteria that triggered
  - Rule name and configuration
  - User identity (AD account, SID)
  - Endpoint name and IP
  - Application involved (which process triggered the violation)
  - Timestamp and duration
- Assess whether this is a true positive (actual data loss risk) or false positive (benign content matching a broad rule)
- For true positives: determine severity and urgency of response
- For false positives: document the false positive pattern for Policy Administrator feedback

**Triage decision tree:**
```
Is the content actually sensitive?
  |
  +-- YES: Is this an authorized transfer?
  |     |
  |     +-- YES: Close as "Authorized" (if justification provided)
  |     +-- NO: Escalate to Incident Response
  |
  +-- NO (false positive): Close + document pattern
       |
       +-- If FP rate > 10%: Request rule tuning from Policy Admin
```

**API:** FULL -- Get incident details programmatically:
```
GET /rest/dlp/event/incident/{id}
```

---

### 3. Retrieve Evidence (2-5 min per event)

**Screen:** DLP Incident Manager > Incident Detail > Evidence tab

**Actions:**
- Click "View Evidence" to retrieve the captured content
- Evidence is encrypted at rest and decrypted on retrieval
- Review the actual data that triggered the classification match
- For email violations: view the email body, headers, and attachment content
- For USB violations: view the file content that was copied
- For web violations: view the HTTP POST body content
- Screenshot or export evidence for incident documentation

**Gotcha:** "Evidence viewing fails in workgroup (non-domain) environments. The DLP Incident Manager cannot display evidence from non-domain-joined endpoints. Ensure endpoints are domain-joined or use the REST API for programmatic evidence retrieval." [Source: Jay Appell DLP 008]

**Gotcha:** "DLP event and evidence data accumulates without limit. Without periodic purging, the ePO database grows unbounded and eventually causes console performance degradation. Set up scheduled purge tasks for events older than your retention policy requires." [Source: Jay Appell DLP 014]

**API:** FULL -- Retrieve and decrypt evidence programmatically:
```
POST /rest/dlp/event/evidence/get
```
This is a key automation point -- SOC playbooks can automatically collect evidence for Critical severity incidents.

---

### 4. Correlate with SIEM (10-15 min)

**Screen:** External SIEM (Splunk, Chronicle, etc.) or ePO Queries & Reports

**Actions:**
- Cross-reference the DLP incident with other security events:
  - Login events: Was the user's account compromised? (unusual login location/time)
  - Endpoint events: Is the system infected with malware that is exfiltrating data?
  - Network events: Was there unusual outbound traffic volume?
  - Previous DLP incidents: Does this user have a pattern of violations?
- Build a timeline of events around the DLP violation
- Determine if this is an isolated incident or part of a larger attack/insider threat pattern

**ePO Queries:**
- Use built-in DLP queries or create custom queries:
  - "Top 10 users by DLP violations this week"
  - "DLP violations by severity over last 30 days"
  - "Rules with highest false positive rate"
- Run via ePO console or automate via `core.executeQuery` API

**API:** PARTIAL -- Incident query and saved query execution are fully automatable. However, cross-product correlation with non-DLP events requires SIEM integration (syslog forwarding) or XDR correlation via Trellix XDR.

---

### 5. Escalate or Close (5 min)

**Actions based on triage outcome:**

**True Positive -- Data Loss Risk:**
1. Escalate to Incident Response team with evidence package
2. If immediate risk: contact the user's manager and/or IT to restrict access
3. Document the incident in the organization's incident tracking system
4. If the rule action was "Monitor" (not "Block"): flag for Policy Administrator to escalate the rule to "Block" action

**False Positive -- Benign Content:**
1. Close the incident in DLP Incident Manager
2. Document the false positive pattern (what content triggered, why it is benign)
3. If recurring false positive: submit a rule tuning request to the Policy Administrator with:
   - Incident IDs of false positive examples
   - Suggested refinement (more specific regex, higher score threshold, user exclusion)
   - Business justification for the change

**User Justification Response:**
1. If the rule action was "Request Justification" and the user provided justification:
2. Review the justification text
3. Accept (close incident) or reject (escalate to manager)

**API for closing/updating incidents:** GAP -- Incident status management (close, assign, add notes) does not have API coverage in the on-prem DLP REST API. Status updates must be done in the ePO console or tracked in an external system.

---

## Pain Points

1. **Cannot programmatically disable noisy rules** -- When a rule is generating hundreds of false positives per hour (e.g., after a classification change), the SOC analyst cannot toggle the rule off via API. They must wait for the Policy Administrator to manually disable it in the console.

2. **No incident status management API** -- Incident close/assign/annotate operations are console-only. SOC workflows that track incidents in external systems (ServiceNow, Jira) cannot programmatically update DLP incident status.

3. **Evidence retrieval in workgroup environments** -- Non-domain-joined endpoints cannot have their evidence viewed through the standard Incident Manager. The REST API (`/rest/dlp/event/evidence/get`) works but is not widely known.

4. **SIEM parser gaps** -- Native parsers exist for Splunk, Chronicle, and Devo, but Elastic and other SIEMs require custom parsing of CEF/LEEF syslog. This creates integration work for Elastic-based SOCs.

5. **No real-time push notifications** -- Trellix DLP has no native webhook support. SOC teams must either poll the incident API, parse syslog in near-real-time, or use OpenDXL pub/sub (which requires DXL broker infrastructure).

6. **Cross-product correlation requires Trellix XDR** -- Correlating DLP events with EDR, email security, or network detection events is only native within the Trellix XDR platform. SOCs using non-Trellix products must build custom correlation rules in their SIEM.

---

## Automation Opportunities

### What IS Automatable Today

| Operation | API/Mechanism | Use Case |
|-----------|-------------|----------|
| Incident polling | `/rest/dlp/event/incidents` | SOAR playbook: poll for new Critical incidents every 5 min |
| Incident detail retrieval | `/rest/dlp/event/incident/{id}` | Auto-enrich tickets with incident context |
| Evidence collection | `/rest/dlp/event/evidence/get` | Auto-collect evidence for Critical incidents |
| Saved query execution | `core.executeQuery` | Automated daily compliance report generation |
| Syslog forwarding to SIEM | CEF/LEEF over syslog | Real-time event ingestion for dashboards |
| OpenDXL event subscription | DXL fabric pub/sub | Real-time event-driven playbook triggers |

### What WOULD Be Automatable If API Existed

| Operation | Impact | Competitive Opportunity |
|-----------|--------|------------------------|
| Update incident status (close/assign) | HIGH | SOAR integration: close false positives from playbook |
| Disable/enable rules | HIGH | Automated circuit-breaker: disable noisy rule when FP rate exceeds threshold |
| Query incidents with complex filters | MEDIUM | Advanced incident search (user + classification + date range + severity) |
| Push webhook on new incident | HIGH | Real-time alerting without polling or syslog parsing |
| Add analyst notes to incidents | MEDIUM | Audit trail without ePO console access |

---

## Integration Points for SOC Workflows

### SOAR Integration Pattern

```
DLP Incident (syslog/API poll)
    |
    v
SOAR Platform (e.g., Trellix Helix, Palo Alto XSOAR, Splunk SOAR)
    |
    +-- Auto-enrich: GET /rest/dlp/event/incident/{id}
    +-- Auto-collect evidence: POST /rest/dlp/event/evidence/get
    +-- Auto-classify: Check severity, user, classification
    |
    +-- If Critical + sensitive classification:
    |     +-- Create ticket in ServiceNow
    |     +-- Alert SOC Slack channel
    |     +-- Notify user's manager via email
    |
    +-- If recurring false positive:
    |     +-- Create Jira ticket for Policy Admin: "Tune rule X"
    |     +-- Aggregate FP examples for context
    |
    +-- If user provided justification:
          +-- Route to SOC for approval/rejection (manual step)
```

### Reporting Cadence

| Report | Frequency | Source | API |
|--------|-----------|--------|-----|
| Daily incident summary (Critical/High) | Daily | `core.executeQuery` or SIEM | YES |
| Weekly false positive rate by rule | Weekly | `core.executeQuery` | YES |
| Monthly compliance posture | Monthly | `core.executeQuery` | YES |
| Quarterly executive summary | Quarterly | SIEM dashboards + manual analysis | PARTIAL |

---

## Time Estimate

| Scenario | Time | Notes |
|----------|------|-------|
| Morning incident queue review | 30-60 min | Filter Critical/High, triage top incidents |
| Single incident deep-dive | 15-30 min | Evidence review + SIEM correlation |
| False positive documentation | 10-15 min | Per incident, including tuning request |
| Weekly compliance report | 1-2 hours | Query execution + formatting |
| Monthly rule tuning feedback session with Policy Admin | 1-2 hours | Review FP patterns, propose changes |

## Complexity: MODERATE (primarily read-only operations, well-served by existing APIs)
