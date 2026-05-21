# Gotchas: Compliance Reporting

> **Source:** Broadcom TechDocs, Video Intelligence Report, API Intelligence Report, operational experience
> **Impact Ratings:** CRITICAL = audit failure or data loss; HIGH = significant reporting gap; MEDIUM = report accuracy or performance issue; LOW = minor inconvenience

---

## Report Performance

### 1. Reports on Large Datasets Time Out (HIGH)

**Problem:** Running a report across millions of incidents with a wide date range (e.g., "all PCI incidents for the year") can time out in the Enforce Console browser session. The Oracle query exceeds the configured timeout.

**Symptoms:** Report shows "Request timed out" or a blank page after loading for 60+ seconds; browser session expires.

**Mitigation:**
- Narrow the date range: Generate monthly reports and aggregate them externally, rather than querying a full year at once
- Use the REST API for large exports -- the API has configurable timeouts and supports pagination
- Optimize the Oracle database: run `DBMS_STATS.GATHER_SCHEMA_STATS` weekly; ensure indexes on incident creation date, policy name, severity
- Add more specific filters to reduce the result set
- For annual audit reports, pre-compute monthly data and compile offline

### 2. Dashboard Rendering Degrades with Many Widgets (MEDIUM)

**Problem:** Each dashboard widget executes its own database query. Dashboards with many widgets (especially in DLP 26.1 which supports up to 12) can be slow to render.

**Symptoms:** Dashboard takes 30+ seconds to fully render; individual widgets show loading spinners.

**Mitigation:**
- Limit widgets to 6-8 even on DLP 26.1 (even though 12 is supported)
- Use relative date ranges ("last 30 days") rather than absolute ranges spanning years
- Schedule dashboard generation and view static copies rather than live dashboards
- Consider separate dashboards for different audiences rather than one dense dashboard

### 3. Concurrent Report Users Cause Database Contention (MEDIUM)

**Problem:** If multiple analysts run reports simultaneously, Oracle experiences query contention. This is especially problematic when reports run during peak incident processing hours.

**Symptoms:** Reports that normally take 5 seconds take 30+ seconds; incident creation latency increases.

**Mitigation:**
- Schedule heavy compliance reports for off-hours (evenings, weekends)
- Stagger scheduled reports so they do not all run at the same time
- If your Oracle deployment supports it, use a read replica for reporting queries
- Limit who has "Create/Edit Reports" privilege to prevent ad-hoc heavy queries

---

## Timezone Handling

### 4. Console Displays Local Timezone; API Returns UTC (MEDIUM)

**Problem:** The Enforce Console displays incident timestamps in the server's local timezone (or the user's configured timezone preference). The REST API returns all timestamps in UTC (ISO 8601 format). When combining console-generated reports with API-generated reports, timestamps may not align.

**Symptoms:** Console report says "Incident at 2:30 PM EST"; API export says "2026-05-21T19:30:00Z"; analyst thinks they are different incidents.

**Mitigation:**
- Standardize all programmatic reporting on UTC
- Document the timezone behavior for compliance team members
- When creating audit evidence packages that combine console exports and API exports, normalize all timestamps to a single timezone
- API date filter parameters accept ISO 8601 with timezone designator: use explicit UTC

### 5. Scheduled Reports Run in Server Timezone (LOW)

**Problem:** Scheduled report timing is based on the Enforce Server's system timezone. If the server is in UTC but your compliance team expects reports at "8 AM Eastern", you need to account for the offset.

**Symptoms:** Report arrives at unexpected time; "monthly" report includes data from the wrong month boundary.

**Mitigation:** Document the Enforce Server timezone and calculate schedule times accordingly. If the server is UTC, schedule a "8 AM Eastern" report for 1 PM UTC (or 12 PM UTC during daylight saving).

---

## Report Accuracy

### 6. Reports Only Show Incidents Your Role Can See (HIGH)

**Problem:** If a compliance officer's role is scoped to only see PCI incidents, their "all incidents" report will only contain PCI incidents -- but the report will not indicate that data was filtered. The report appears complete but is actually a subset.

**Symptoms:** Compliance report shows 500 incidents for the month; actual total across all policies is 5,000; auditor questions the low number.

**Mitigation:**
- Create a dedicated "Compliance Reporting" role with broad incident visibility
- Clearly label reports with the role/scope used to generate them
- For audit reports requiring complete data, use the Administrator account (unrestricted access)
- Document which role was used to generate each compliance report

### 7. Deleted Policies Leave Orphaned Incidents with "Unknown Policy" (MEDIUM)

**Problem:** If a policy is deleted, incidents generated by that policy still exist in the database. However, the "Policy Name" field may show the original name or become difficult to filter on if the policy configuration is gone.

**Symptoms:** Old incidents reference a policy that no longer exists; reports grouping by policy have an "unknown" or orphaned category.

**Mitigation:**
- Never delete policies -- disable them instead
- Before deleting a policy, archive all associated incidents
- Resolve or export all incidents from the policy before deletion
- Use policy versioning: rename old policies (e.g., "PCI-v1-DEPRECATED") rather than deleting

### 8. Custom Attribute Values Are Not Retroactive (MEDIUM)

**Problem:** When you add a new custom attribute (e.g., "Regulatory Scope"), it is empty for all existing incidents. Only incidents created after the attribute was added (and after lookup plugins or analysts populate it) will have values.

**Symptoms:** Filtering by a custom attribute shows no results for older incidents; compliance report for Q1 is empty because the attribute was added in Q2.

**Mitigation:**
- Define custom attributes before going live with incident generation
- For retroactive population, use the REST API to bulk-update older incidents:
  ```bash
  # Bulk update old PCI incidents with missing "Regulatory Scope" attribute
  curl -s -u 'admin:password' \
    -X PATCH \
    -H 'Content-Type: application/json' \
    -d '{"incidents": [
      {"incidentId": 12345, "customAttributes": [{"name": "Regulatory Scope", "value": "PCI"}]},
      {"incidentId": 12346, "customAttributes": [{"name": "Regulatory Scope", "value": "PCI"}]}
    ]}' \
    'https://enforce.corp.local/ProtectManager/webservices/v2/incidents'
  ```

---

## Scheduled Report Failures

### 9. Scheduled Report Email Delivery Fails Silently (HIGH)

**Problem:** If the SMTP server is unreachable, scheduled reports generate but the email delivery fails. There is no prominent alert in the console -- the failure is logged in system events but not surfaced to the report creator.

**Symptoms:** Compliance team stops receiving scheduled reports; no one notices for weeks; audit deadline approaches with missing reports.

**Mitigation:**
- Configure system event alerts for SMTP failures: System > Servers and Detectors > Events > Alert Configuration
- Periodically verify scheduled reports are being received (add yourself as a CC)
- Set up a monitoring check on the SMTP relay to ensure the Enforce Server can send email
- Create a "heartbeat" scheduled report that runs daily to confirm email delivery works

### 10. Scheduled Reports Use Stale Data If Generation Overlaps with Database Maintenance (LOW)

**Problem:** If a scheduled report runs during Oracle database maintenance (backup, statistics gathering, index rebuild), the report may time out or include incomplete data.

**Symptoms:** Monthly report shows fewer incidents than expected; running the same report manually afterward shows the correct count.

**Mitigation:**
- Schedule reports at a time that does not overlap with Oracle maintenance windows
- If the report fails, re-run it manually and use the manual output for compliance

---

## Compliance-Specific Issues

### 11. Incident Retention Purge Removes Compliance Evidence (CRITICAL)

**Problem:** The "Limit Incident Data Retention" response rule automatically purges incident evidence after the configured period. If the retention period is shorter than the regulatory requirement, compliance evidence is destroyed.

**Symptoms:** Auditor requests incident details from 18 months ago; evidence was purged after 90 days.

**Mitigation:**
- Map retention periods to regulatory requirements BEFORE configuring retention rules:
  - PCI DSS: Keep 1 year minimum
  - HIPAA: Keep 6 years minimum
  - SOX: Keep 7 years minimum
  - GDPR: Keep for duration of processing purpose
- Archive incidents (export to secure storage) before purging
- Use different retention rules for different policies (short retention for low-risk, long for regulated)
- Document the retention policy and have compliance officer approve it

### 12. Audit Log Export Does Not Include Incident Changes Made Before 16.0 RU1 (MEDIUM)

**Problem:** The audit log REST API was introduced in DLP 16.0 RU1. Audit log data from before this version is only accessible in the console, not programmatically. If you upgraded from an earlier version, historical audit data cannot be exported via API.

**Symptoms:** API-based audit log export starts from the upgrade date, not from initial deployment.

**Mitigation:**
- For historical audit data, export from the console (System > Servers and Detectors > Audit Logs > Export)
- Going forward, use the API for automated audit log collection
- After upgrade, establish API-based audit log archival immediately

### 13. Discovery Reports Do Not Distinguish "Still Present" from "Remediated" Without Protect (MEDIUM)

**Problem:** Network Discover creates incidents for files found during scans. Without Network Protect (the remediation module), these incidents remain in "New" status indefinitely. The report shows "500 files with PCI data on FileServer01" but does not indicate whether those files were remediated.

**Symptoms:** Auditor asks "Were these files remediated?" and the report cannot answer; Discover incidents sit as "New" for months.

**Mitigation:**
- Deploy Network Protect for automated remediation (quarantine, encrypt, label)
- If Protect is not licensed, establish a manual remediation workflow: Discover incidents reviewed by data owners who manually remediate and update incident status
- Track remediation status via custom attribute: "Remediation Status" = Pending, Completed, Not Required
- Update discover incidents via API after manual remediation

---

## Export and Distribution

### 14. CSV Exports Contain Sensitive Data in Plain Text (HIGH)

**Problem:** When you export incidents to CSV, matched content snippets (credit card numbers, SSNs, etc.) are included in plain text. The CSV file itself becomes a sensitive data artifact.

**Symptoms:** Compliance officer emails CSV to auditor; CSV contains the same PCI data DLP was designed to protect; DLP detects the CSV in transit (irony).

**Mitigation:**
- Establish secure channels for report distribution (encrypted file share, secure portal)
- Configure content masking in reports where possible (partial match display)
- Train all report consumers that DLP exports contain sensitive data
- Consider creating summary reports (counts only, no matched content) for distribution, and provide full-detail reports only on secure channels
- Add the DLP export share path to policy exceptions to avoid the DLP system flagging its own reports

### 15. No Built-in Report Comparison (Before/After) (LOW)

**Problem:** DLP does not have a native "compare two periods" feature. To show that PCI incidents decreased from Q1 to Q2 (demonstrating program effectiveness), you must generate two reports and compare manually.

**Symptoms:** Compliance officer asks "Are we improving?" and the analyst must export two date ranges and build a comparison in Excel.

**Mitigation:**
- Use dashboards with trend line charts (line chart over time shows the trend)
- Export data via API and build comparison reports in a BI tool (Tableau, Power BI, Grafana)
- Build a script that queries two time periods and computes delta metrics:
  ```bash
  # Compare Q1 vs Q2 PCI incidents
  Q1=$(curl -s -u "$AUTH" -X POST ... -d '{"dateRange": "Q1"}' | jq '.incidents | length')
  Q2=$(curl -s -u "$AUTH" -X POST ... -d '{"dateRange": "Q2"}' | jq '.incidents | length')
  echo "Q1: $Q1, Q2: $Q2, Change: $(( Q2 - Q1 )) ($(( (Q2 - Q1) * 100 / Q1 ))%)"
  ```

---

## Operational

### 16. Role Selection Affects Report Visibility (LOW)

**Problem:** If a user has multiple roles, the saved reports they see depend on which role they selected at login. Reports saved under "PCI Analyst" role are not visible when logged in under "General Analyst" role.

**Symptoms:** "I saved a report last week but now I cannot find it" -- user is logged in with a different role.

**Mitigation:**
- Document which role users should use for report creation and viewing
- DLP 26.1 improves role selection with a clearer role list at login
- Create compliance reports under a shared "Compliance" role that all relevant users have access to

### 17. Dashboard Customization Is Per-Role, Not Per-User (LOW)

**Problem:** Dashboard configurations are shared across all users in a role. If one analyst rearranges a shared dashboard, it changes for everyone in that role.

**Symptoms:** Dashboard layout changes unexpectedly; widgets reordered or removed by another user.

**Mitigation:**
- Restrict dashboard editing to team leads or designated dashboard owners
- Create separate roles for users who need different dashboard views
- Document the intended dashboard layout so it can be restored if modified
