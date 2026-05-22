# Forcepoint DLP Policy Authoring -- Gotchas

> Known limitations, common pitfalls, and hard-won lessons for Forcepoint DLP policy authoring.

---

## 1. Deployment Gotchas

### 1.1 Deploy Pushes ALL Pending Changes

**Problem:** The Deploy button deploys ALL pending configuration changes across all policies, classifiers, and system settings -- not just the change you just made.

**Impact:** If another admin made untested changes, your deployment pushes their changes too.

**Mitigation:**
- Always review all pending changes before clicking Deploy
- Coordinate deployments with other admins
- Use the REST API deploy endpoint in CI/CD pipelines where change sets are controlled
- Consider a change management process with designated deployment windows

### 1.2 Changes Saved but Not Active

**Problem:** Clicking OK in the Security Manager saves changes to the management server database immediately, but they have zero effect on actual DLP enforcement until Deploy is clicked.

**Impact:** Admins think a policy is active after saving. Users remain unprotected until deployment.

**Mitigation:** Always deploy after making changes. Add "Deploy" to your checklist for every policy change.

### 1.3 Deployment Failures Are Per-Component

**Problem:** Deployment can succeed for some components and fail for others. A partial deployment means some channels are enforcing the new policy while others are not.

**Impact:** Inconsistent enforcement across channels (e.g., email blocks but endpoint allows).

**Mitigation:** Always check the deployment status table. Re-deploy if any component shows "Failed". Investigate connectivity to failed components.

---

## 2. Classifier Gotchas

### 2.1 Regex Without Context = False Positive Storm

**Problem:** A regex pattern like `\b\d{3}-\d{2}-\d{4}\b` (SSN format) also matches phone numbers, order IDs, and other 9-digit sequences.

**Impact:** Thousands of false positive incidents in the first week.

**Mitigation:**
- Always combine regex classifiers with context classifiers (key phrases, dictionaries)
- Use AND logic: SSN regex AND ("Social Security" OR "SSN" OR "tax" key phrases)
- Start with Audit-only to measure false positive rates before enabling Block actions
- Leverage Forcepoint's predefined SSN classifiers, which include built-in validation logic

### 2.2 Single-Field Database Fingerprinting

**Problem:** Fingerprinting a single database field (e.g., just "email") produces very high false positive rates because common strings match too easily.

**Impact:** Every email address in any document triggers a match, even if it has nothing to do with the protected database.

**Mitigation:**
- Always fingerprint 3+ fields per table
- If only 1 field is available, set minimum threshold to 5 matches
- Maximum: 32 fields per table
- Best practice: Choose the most uniquely identifying fields (composite keys, IDs, names + unique identifiers)

### 2.3 Fingerprints Are Point-in-Time Snapshots

**Problem:** Database and file fingerprints capture data at the time of the scan. New records added after fingerprinting are not detected until the next fingerprint scan.

**Impact:** Recently added customer records, new employees, or updated documents are unprotected between scans.

**Mitigation:**
- Schedule regular re-fingerprinting (daily for high-change databases, weekly for file shares)
- For high-velocity data (e.g., customer sign-ups), combine fingerprinting with regex/pattern classifiers as a safety net

### 2.4 File Property Detection by Magic Number, Not Extension

**Problem (actually a feature):** Forcepoint identifies file types by their internal "magic number" (binary signature), not by file extension. A .txt file that is actually a renamed .exe will be detected as an executable.

**Impact (positive):** Rename-based evasion does not work.

**Gotcha:** This means you cannot use file extension-based exceptions to allow specific files. If you whitelist ".txt" files, a renamed executable will NOT be whitelisted because Forcepoint sees it as an executable internally.

### 2.5 Machine Learning Classifiers Need Quality Training Data

**Problem:** ML classifiers are only as good as their training sets. Insufficient or unbalanced training data produces unreliable classification.

**Impact:** High false positive or false negative rates.

**Mitigation:**
- Minimum: 100 positive examples + 100 negative examples
- Ensure negative examples are representative of non-sensitive content in the same domain
- Retrain quarterly as document styles and content evolve
- Monitor ML classifier accuracy via incident false positive analysis

### 2.6 Key Phrases Are Case-Sensitive by Default

**Problem:** Key phrase classifiers may be case-sensitive depending on configuration.

**Impact:** "CONFIDENTIAL" matches but "confidential" or "Confidential" does not.

**Mitigation:** Configure case-insensitive matching when creating key phrase classifiers. Test with multiple case variations.

### 2.7 OCR Limitations

**Problem:** OCR cannot process handwriting or text skewed more than 10 degrees. Maximum file size is 25 MB; minimum is 5 KB.

**Impact:** Handwritten notes, rotated scanned documents, and very large images are not inspected.

**Mitigation:**
- Combine OCR with file property classifiers to block uninspectable image types
- Add a policy for "image files that cannot be scanned" -> Quarantine for manual review

---

## 3. Policy Logic Gotchas

### 3.1 Exception Overrides Rule, Not Policy

**Problem:** Exceptions are evaluated per-rule, not per-policy. If an exception matches, only that specific rule's action is overridden. Other rules in the same policy still fire.

**Impact:** Admins create an exception thinking it exempts a user from the entire policy, but the user is still caught by other rules.

**Mitigation:** If you need to exempt a user from an entire policy, create exceptions on every rule within that policy, or use source filtering to exclude the user from the policy entirely.

### 3.2 AND vs. OR Logic Default

**Problem:** When multiple conditions are added to a rule, the default behavior may be AND (all must match) or OR (any must match) depending on configuration. Misunderstanding the default creates policies that are either too strict or too permissive.

**Impact:** A rule intended to catch "SSN OR credit card" configured as "SSN AND credit card" will only fire when both appear in the same transaction.

**Mitigation:** Always explicitly set the logic operator between conditions. Do not rely on defaults. Test with synthetic data that matches only one condition to verify OR behavior.

### 3.3 Threshold Confusion: Per-Transaction vs. Cumulative

**Problem:** Standard thresholds apply per-transaction (per email, per file upload). Cumulative (drip DLP) thresholds apply across transactions over a time window. Using the wrong type leads to either missed detections or excessive false positives.

**Impact:** Setting a per-transaction threshold of 100 credit cards never triggers because no single email contains 100 cards. But cumulative with 100 over 30 days would catch the drip.

**Mitigation:**
- Per-transaction thresholds: For single-event protection (single email, single upload)
- Cumulative thresholds: For drip/slow exfiltration detection
- Most policies should have BOTH: a per-transaction rule AND a cumulative rule

### 3.4 Drip DLP Sliding Window Reset

**Problem:** The cumulative time window is a sliding window that resets every time a new match is detected. This means as long as matches keep happening, the window keeps extending.

**Impact:** If an attacker stops for longer than the window period, the count resets to zero.

**Mitigation:** Set the time window long enough to capture realistic exfiltration patterns (7-30 days). For very slow exfiltration, consider 90-day windows, but be aware of storage and performance implications.

### 3.5 Match Calculation: Greatest vs. Sum

**Problem:** When configuring cumulative rules, "greatest number of matched conditions" counts only the largest single match, while "sum of all matched conditions" adds all matches together.

**Impact:** Using "greatest" when you mean "sum" dramatically undercounts matches.

**Mitigation:** For drip DLP detection, almost always use "sum of all matched conditions" to capture the true cumulative total.

---

## 4. Action Plan Gotchas

### 4.1 Block Without Notification = Support Tickets

**Problem:** Blocking a user's action without explaining why causes confusion and help desk tickets.

**Impact:** Users call IT saying "email won't send" or "file won't copy" without understanding it is a DLP policy.

**Mitigation:** Always pair Block actions with user notifications (endpoint popup or email notification explaining the violation and next steps).

### 4.2 Quarantine Queue Overflow

**Problem:** Quarantine holds messages for human review. High-volume policies can fill the quarantine queue faster than analysts can review.

**Impact:** Legitimate business emails are delayed or lost. Senders do not know their email is stuck in quarantine.

**Mitigation:**
- Reserve quarantine for high-severity, low-volume scenarios
- Set quarantine auto-release timers (e.g., release after 48 hours if not reviewed)
- Staff the quarantine review queue with SLA targets
- Use Block (reject) instead of Quarantine for high-volume scenarios

### 4.3 Audit Generates Incident Volume

**Problem:** Even Audit-only policies generate incidents in the database. High-volume audit policies can fill incident storage rapidly.

**Impact:** Database growth, slower reporting queries, storage costs.

**Mitigation:**
- Monitor incident database size during audit-only phases
- Set incident retention policies (auto-archive or delete incidents older than X days)
- Use narrow source/destination scoping even during audit phases

### 4.4 Syslog Message Size Limits

**Problem:** Some SIEM platforms have maximum syslog message size limits (e.g., 2048 bytes for UDP). Forcepoint DLP syslog messages for complex incidents may exceed these limits.

**Impact:** Truncated incident data in SIEM.

**Mitigation:** Use TCP instead of UDP for syslog forwarding (TCP does not have the same size limitations). Configure your SIEM to accept larger messages.

### 4.5 Endpoint Remediation Scripts Are Powerful but Dangerous

**Problem:** Remediation scripts run on the endpoint with system-level privileges. A buggy script can delete files, corrupt data, or crash systems.

**Impact:** Data loss, system instability, user productivity impact.

**Mitigation:**
- Test scripts thoroughly in a lab environment before deploying
- Start with read-only scripts (log, notify) before enabling write operations (move, delete, encrypt)
- Include error handling and logging in all scripts
- Roll out scripts to a small pilot group first

---

## 5. Channel-Specific Gotchas

### 5.1 Email: Reply/Forward Chains

**Problem:** When a user replies to or forwards an email that contains sensitive data, the original content is included in the new message. DLP scans the entire message including quoted content.

**Impact:** Users get blocked for quoting content they received, not content they authored.

**Mitigation:** Consider using "source" filtering to focus on the sender's new content, or create exceptions for internal-to-internal email chains. Note: this creates a gap if the original content should not be forwarded externally.

### 5.2 Cloud: Personal vs. Corporate Accounts

**Problem:** Users may have both personal and corporate accounts for cloud services (e.g., personal Gmail + corporate Google Workspace, personal Dropbox + corporate Box).

**Impact:** Blocking "Google Drive" blocks the corporate Google Workspace too. Allowing it allows personal Google Drive.

**Mitigation:** Use cloud application instance-level controls (available in CASB integration) to distinguish personal from corporate cloud accounts. This requires Forcepoint ONE or CASB license.

### 5.3 Endpoint: Offline Mode Behavior

**Problem:** When endpoint agents lose connectivity to the management server, they operate in cached policy mode. Policy updates deployed while the agent is offline are not applied until reconnection.

**Impact:** Remote workers or traveling employees may run outdated policies for extended periods.

**Mitigation:** Design policies with offline scenarios in mind. Set endpoint policies to be more restrictive by default (fail-closed). Monitor agent connectivity status.

### 5.4 Network: Encrypted Traffic (TLS)

**Problem:** Network DLP cannot inspect encrypted (TLS/SSL) traffic without SSL decryption. If SSL inspection is not configured, HTTPS uploads, encrypted email, and VPN traffic are invisible to network DLP.

**Impact:** Significant blind spot for data exfiltration via HTTPS.

**Mitigation:** Deploy SSL inspection (Forcepoint Web Security or third-party proxy). Be aware of legal, privacy, and certificate management implications.

### 5.5 Discovery: Performance Impact on Scanned Systems

**Problem:** Discovery scans read large volumes of data from file shares, databases, and endpoints. This can impact performance on the scanned systems.

**Impact:** File server slowdowns, database performance degradation, endpoint sluggishness during scans.

**Mitigation:** Schedule discovery scans during off-hours. Use throttling settings. Scan in stages (one file server per night, not all at once).

---

## 6. Operational Gotchas

### 6.1 Predefined Policies Are Read-Only

**Problem:** Predefined policies cannot be directly edited. You can only enable/disable them and change their action plans.

**Impact:** If you need to modify a predefined policy's rule logic, classifiers, or conditions, you cannot edit in place.

**Mitigation:** Clone the predefined policy, then customize the clone. Disable the original. Keep the clone naming convention consistent (e.g., "HIPAA - Custom" or "HIPAA v2").

### 6.2 No Partial Deployment

**Problem:** The Deploy operation pushes all pending changes to all components. There is no way to deploy changes to specific components or deploy a single policy change.

**Impact:** Testing a policy change requires deploying all pending changes, including changes made by other admins.

**Mitigation:**
- Use a staging/UAT environment for testing before deploying to production
- Coordinate deployment windows with other admins
- Review all pending changes before clicking Deploy
- Use the REST API policy import/export to manage changes programmatically

### 6.3 Incident Database Growth

**Problem:** Active DLP policies generate incidents continuously. Without retention management, the incident database grows indefinitely.

**Impact:** SQL Server storage consumption, slower reporting, backup size increases.

**Mitigation:**
- Configure incident archival (move old incidents to archive database)
- Set retention policies (auto-delete incidents older than N days/months)
- Monitor database size with alerting
- Regularly run cleanup processes (documented in Forcepoint admin guide)

### 6.4 API Rate Limiting Is Undocumented

**Problem:** Forcepoint DLP REST API does not publicly document rate limits.

**Impact:** Aggressive polling can overload the management server or trigger undocumented throttling.

**Mitigation:** Use conservative polling intervals (60 seconds minimum between API calls). Implement exponential backoff on errors. For real-time needs, use syslog push instead of API polling.

### 6.5 RAP Requires UEBA License and Infrastructure

**Problem:** Risk-Adaptive Protection requires a separate Forcepoint UEBA deployment with its own infrastructure (analytics server, data collection).

**Impact:** RAP-enhanced policies configured without UEBA infrastructure will not have risk scores and will default to a single static action.

**Mitigation:** Confirm UEBA is deployed and generating risk scores before configuring RAP-enhanced policies. Test by verifying risk scores appear in the incident reports.

---

## 7. Common Mistakes by Phase

### Phase 1: Initial Deployment

| Mistake | Consequence | Fix |
|---------|-------------|-----|
| Enabling Block actions on day one | Massive business disruption | Start with Audit-only for 2+ weeks |
| Not setting up incident monitoring | Policies run but nobody reviews | Configure incident reports before deployment |
| Deploying all predefined policies at once | Incident overload, database growth | Start with 2-3 highest-priority policies |

### Phase 2: Tuning

| Mistake | Consequence | Fix |
|---------|-------------|-----|
| Not creating exceptions for legitimate flows | False positives persist | Review top 10 false positive sources weekly |
| Setting thresholds too low | Alert fatigue | Use tiered thresholds (audit at low, block at high) |
| Not re-fingerprinting after data changes | New data unprotected | Schedule regular re-fingerprinting |

### Phase 3: Enforcement

| Mistake | Consequence | Fix |
|---------|-------------|-----|
| Blocking without user education | Help desk overload | Notify users + provide self-service justification |
| Not having escalation paths | High-severity incidents stall | Define incident response workflow before enabling Block |
| No change management for policy updates | Uncoordinated changes break things | Implement review/approve/deploy process |

### Phase 4: Optimization

| Mistake | Consequence | Fix |
|---------|-------------|-----|
| Not using RAP when available | Same enforcement for all risk levels | Enable RAP for nuanced, risk-based responses |
| Ignoring Drip DLP | Slow exfiltration goes undetected | Add cumulative rules for key data types |
| Not integrating with SIEM | Incidents siloed in DLP console | Configure syslog or REST API integration |
