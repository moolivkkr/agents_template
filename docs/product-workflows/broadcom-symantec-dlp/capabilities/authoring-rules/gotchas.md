# Authoring Rules — Gotchas
## Broadcom Symantec DLP (Enforce Server, version 16.x/25.x/26.x)

> **Purpose:** Comprehensive collection of gotchas, pitfalls, and best-practice warnings for DLP rule authoring.
> **Evidence sources:** doc-corpus.md [S1-S28], video-intelligence.md [V1-V45, tribal knowledge], api-intelligence.md

---

## Table of Contents

1. [Detection Technology Gotchas](#1-detection-technology-gotchas)
2. [EDM-Specific Gotchas](#2-edm-specific-gotchas)
3. [IDM-Specific Gotchas](#3-idm-specific-gotchas)
4. [VML-Specific Gotchas](#4-vml-specific-gotchas)
5. [Detection Rule Gotchas](#5-detection-rule-gotchas)
6. [Exception Gotchas](#6-exception-gotchas)
7. [Response Rule Gotchas](#7-response-rule-gotchas)
8. [Policy Gotchas](#8-policy-gotchas)
9. [Deployment & Infrastructure Gotchas](#9-deployment--infrastructure-gotchas)
10. [API & Integration Gotchas](#10-api--integration-gotchas)
11. [Upgrade & Migration Gotchas](#11-upgrade--migration-gotchas)
12. [Operational Gotchas](#12-operational-gotchas)

---

## 1. Detection Technology Gotchas

### G-DT-1: Keywords in email disclaimers trigger constant false positives
**Impact:** HIGH
**Symptom:** Keyword rule for "CONFIDENTIAL" triggers on nearly every email.
**Root cause:** Most corporate email footers contain legal disclaimers with "CONFIDENTIAL" and "PRIVILEGED."
**Mitigation:** Either (a) add a content exception for the standard disclaimer text, (b) increase the minimum match threshold to 2+, or (c) use keyword proximity matching to require "CONFIDENTIAL" near other sensitive terms.
**Evidence:** B [S8, V17, tribal knowledge]

### G-DT-2: Data identifier breadth setting dramatically changes false positive rate
**Impact:** MEDIUM
**Symptom:** SSN detection triggers on phone numbers, zip+4 codes, or random 9-digit sequences.
**Root cause:** "Wide" breadth setting on US SSN data identifier matches 9-digit sequences without dashes. Many non-SSN numbers happen to pass format validation.
**Mitigation:** Start with "Narrow" breadth (XXX-XX-XXXX format only). Only use "Wide" if you need to catch non-dashed SSNs, and combine with other conditions (e.g., keyword proximity) to reduce false positives.
**Evidence:** A [S1, S8]

### G-DT-3: File type detection is by binary signature, not extension
**Impact:** LOW (positive -- this is a security strength)
**Context:** Renaming "data.xlsx" to "data.txt" does NOT bypass file type detection. Symantec recognizes 330+ file types by binary signature.
**Implication:** File name-based rules are supplementary, not primary. Binary signature detection is the reliable mechanism.
**Evidence:** A [S1, S4]

### G-DT-4: Custom data identifiers lack built-in validation
**Impact:** MEDIUM
**Symptom:** Custom data identifier pattern matches too many non-sensitive values.
**Root cause:** Built-in identifiers (CC, SSN) include validators (Luhn, area number check). Custom identifiers have pattern matching only unless a custom validator script is attached.
**Mitigation:** Add custom validator scripts where possible. Test custom patterns against large sample data before deployment.
**Evidence:** B [S8]

### G-DT-5: OCR must be explicitly enabled for image-based detection
**Impact:** HIGH
**Symptom:** Scanned PDFs and image files pass through DLP without detection.
**Root cause:** OCR is not enabled by default. Without OCR, DLP cannot extract text from images.
**Mitigation:** Enable OCR on detection servers. Note: OCR increases CPU load and detection time.
**Evidence:** A [S1, S4]

---

## 2. EDM-Specific Gotchas

### G-EDM-1: Stale indexes miss new sensitive data (SILENT FAILURE)
**Impact:** HIGH
**Symptom:** New employees/customers added to the database are not detected by EDM rules.
**Root cause:** EDM indexes are snapshots. If the source data changes and the index is not refreshed, new records are invisible to detection.
**Mitigation:** Schedule automated re-indexing (daily for high-turnover data, weekly for stable data). Monitor indexing status in the profile management screen.
**Evidence:** A [S1, S4, V19, tribal knowledge]

### G-EDM-2: Error threshold (5% default) causes silent indexing failures
**Impact:** MEDIUM
**Symptom:** EDM indexing silently fails or skips records. Policy appears active but detection is incomplete.
**Root cause:** If empty cells, wrong-type data, or extra cells exceed 5% of rows, indexing stops at the error threshold.
**Mitigation:** Clean source data before indexing (remove empty rows, validate data types). Increase error threshold to 10% for messy data sources, but investigate and fix data quality issues.
**Evidence:** A [S1, V19, tribal knowledge]

### G-EDM-3: Large data sources impact Enforce Server performance
**Impact:** HIGH
**Symptom:** Enforce Server becomes slow or unresponsive during EDM indexing of large (1M+ record) datasets.
**Root cause:** Indexing runs on the Enforce Server by default, competing with policy management and incident processing for CPU and memory.
**Mitigation:** Use the Remote EDM Indexer tool for large data sources. Schedule indexing during off-peak hours (2-4 AM).
**Evidence:** A [S1, S4]

### G-EDM-4: "2 of N fields" matching may be too broad
**Impact:** MEDIUM
**Symptom:** EDM rule triggers on common name + email combinations that are not from the protected dataset.
**Root cause:** "Match 2 of 5 fields" can match on First Name + Email Address, which are common values that may coincidentally match records.
**Mitigation:** Require at least one key field (SSN, CC number, employee ID) to be among the matched fields. Increase the required match count.
**Evidence:** B [S4]

### G-EDM-5: EDM profiles require special handling during DLP version upgrades
**Impact:** HIGH
**Symptom:** After DLP upgrade, EDM profiles are corrupted or non-functional.
**Root cause:** EDM index format changes between major versions. Profiles must be re-indexed after upgrade.
**Mitigation:** Follow EDM-specific upgrade instructions in the release notes. Verify profiles and re-index after upgrade. Test detection with known data samples.
**Evidence:** A [V-gotcha]

### G-EDM-6: Database source queries run on Enforce Server
**Impact:** MEDIUM
**Symptom:** Database-sourced EDM profiles add load to the Enforce Server during index refresh.
**Root cause:** The Enforce Server executes the database query directly. Large result sets consume memory and CPU.
**Mitigation:** Use optimized queries with WHERE clauses to limit result size. Consider exporting to CSV and using file-based source instead for very large tables.
**Evidence:** B [S4]

---

## 3. IDM-Specific Gotchas

### G-IDM-1: Binary files only support exact match, not partial content matching
**Impact:** MEDIUM
**Symptom:** Modified version of a CAD file or JPEG does not trigger IDM detection.
**Root cause:** Binary files (JPEG, CAD, multimedia) are matched by binary stamp (exact binary comparison). Partial content matching only works for text-extractable formats (Office, PDF).
**Mitigation:** For binary files, accept that only exact copies are detected. For derivative detection, convert binary formats to text-based equivalents before indexing (e.g., CAD to STEP export).
**Evidence:** A [S1, S4]

### G-IDM-2: Partial matching threshold must be tuned per document size
**Impact:** MEDIUM
**Symptom:** Short documents false-positive; long documents false-negative.
**Root cause:** A 15% partial threshold on a 100-page document means ~15 pages of overlap. On a 2-page document, 15% is about 4 sentences -- may be too easy to trigger accidentally.
**Mitigation:** Use different IDM profiles with different thresholds for different document sizes/types. Or group documents by size category and adjust thresholds accordingly.
**Evidence:** B [S4]

### G-IDM-3: Source documents change but IDM index is not re-built
**Impact:** HIGH (same as EDM-1)
**Symptom:** New confidential documents added to the source directory are not detected.
**Mitigation:** Schedule regular re-indexing. For rapidly changing document sets, consider weekly or even daily re-indexing.
**Evidence:** A [tribal knowledge]

### G-IDM-4: Endpoint partial matching requires explicit opt-in
**Impact:** HIGH
**Symptom:** IDM partial matching works on network detection servers but not on endpoints.
**Root cause:** "Enable IDM support for endpoints" is a separate checkbox that is off by default. Without it, endpoints only detect full document matches.
**Mitigation:** Enable endpoint IDM in the profile settings. Note: this increases endpoint agent resource usage.
**Evidence:** B [V22]

---

## 4. VML-Specific Gotchas

### G-VML-1: Training data quality matters more than quantity
**Impact:** HIGH
**Symptom:** VML profile accuracy is low (below 80%) despite having many training documents.
**Root cause:** Training documents are too similar (e.g., all from the same author, department, or time period), or negative examples are too different from the positive set.
**Mitigation:** Use diverse, representative training documents. Include variety in format, author, department, and content style. Negative examples should be "near misses" -- documents that are similar to positive examples but should NOT trigger.
**Evidence:** A [S7, V20, tribal knowledge]

### G-VML-2: Too few training documents produce unreliable profiles
**Impact:** HIGH
**Symptom:** VML accuracy score looks acceptable in training but produces many false positives/negatives in production.
**Root cause:** Insufficient training data means the model learns noise rather than signal. Minimum viable is 50 documents per set; recommended is 250+ per set.
**Mitigation:** Gather at least 50 documents per category (positive and negative). Target 250+ for production profiles. If accuracy is below 85%, add more diverse documents and retrain.
**Evidence:** A [S7, V20]

### G-VML-3: VML models decay as content patterns evolve
**Impact:** MEDIUM
**Symptom:** VML profile that was accurate 2 years ago now has high false negative rate.
**Root cause:** Language, terminology, and document formats evolve. A model trained on 2022 financial reports may not recognize 2024 report patterns.
**Mitigation:** Re-train VML profiles annually or when false negative rate increases. Add recent documents to training sets.
**Evidence:** B [S7]

### G-VML-4: VML only works on text content, not binary data
**Impact:** LOW
**Symptom:** VML profile does not detect binary files (executables, images, compiled code).
**Root cause:** VML uses statistical text analysis (word frequencies, patterns). Binary data has no "words" for the model to analyze.
**Mitigation:** Use IDM for binary file detection. Use File Properties for file-type-based detection.
**Evidence:** A [S7]

---

## 5. Detection Rule Gotchas

### G-DR-1: Compound rules use AND logic only -- there is no OR
**Impact:** HIGH
**Symptom:** Compound rule does not trigger when only one of two conditions matches.
**Root cause:** Compound rules require ALL conditions to match. There is no built-in OR operator for compound rules.
**Mitigation:** For OR logic, create separate simple rules. Each simple rule is evaluated independently, and ANY match triggers an incident.
**Evidence:** A [S1, S4]

### G-DR-2: Severity assignment is per-rule, not per-incident
**Impact:** MEDIUM
**Symptom:** An incident has unexpected severity level.
**Root cause:** If multiple rules in a policy match the same content, the highest severity rule wins. Severity is assigned at the rule level, not calculated at the incident level.
**Mitigation:** Be intentional about severity assignment across rules in the same policy. The highest-severity matching rule determines the incident severity.
**Evidence:** A [S1, S4]

### G-DR-3: "Look In" selection determines detection scope
**Impact:** HIGH
**Symptom:** Detection rule misses content in email subject lines or message headers.
**Root cause:** The "Look In" checkboxes (Body, Subject, Attachments, Envelope, Headers) determine which message parts are inspected. If "Subject" is unchecked, content in the subject line is invisible to the rule.
**Mitigation:** Check all relevant "Look In" options. For PCI compliance, include Subject (users sometimes put CC numbers in email subjects).
**Evidence:** A [S1, S4]

### G-DR-4: Regex performance degrades on large files
**Impact:** MEDIUM
**Symptom:** Detection latency increases significantly for messages with large attachments.
**Root cause:** Complex regex patterns (especially with greedy quantifiers or backtracking) can take exponential time on large input.
**Mitigation:** Keep regex patterns as specific as possible. Avoid `.*` at the beginning of patterns. Use anchors and character classes to limit backtracking.
**Evidence:** B [S8]

### G-DR-5: Directory group membership must be current for DGM rules
**Impact:** HIGH
**Symptom:** User-based detection/exception rule does not match expected users.
**Root cause:** DGM rules query AD/LDAP group membership. If a user was added/removed from a group recently, the directory sync may not have propagated yet.
**Mitigation:** Verify directory sync schedule. Test DGM rules by confirming the user appears in the expected AD group.
**Evidence:** A [S1, S4]

---

## 6. Exception Gotchas

### G-EX-1: Exceptions evaluated AFTER detection -- not during
**Impact:** LOW (informational)
**Context:** Many admins assume exceptions prevent content inspection. In reality, content is always inspected; exceptions suppress incident creation after a match.
**Implication:** This means excepted content still consumes detection resources. Exceptions reduce incident noise but not detection processing load.
**Evidence:** A [S1, S4]

### G-EX-2: Exception decay -- temporary exceptions become permanent
**Impact:** HIGH
**Symptom:** An exception added for a one-time business event (e.g., M&A data room) is never removed, creating a permanent detection gap.
**Root cause:** No built-in expiration mechanism for exceptions. They persist until manually removed.
**Mitigation:** Document the reason and expected expiration date for every exception. Schedule quarterly exception reviews. Tag exceptions with creation date and justification.
**Evidence:** B [tribal knowledge]

### G-EX-3: Email address patterns do NOT support regex or wildcards
**Impact:** HIGH
**Symptom:** Exception with `*@company.com` does not work. Exception with regex does not work.
**Root cause:** Email address exception fields use exact match or simple patterns (no regex, no wildcard). This is a known field limitation.
**Mitigation:** Use exact email addresses. For domain-based exceptions, use the URL domain field (which may have different pattern support). For broader patterns, use "Sender/User Based on Directory Server Group" condition instead.
**Evidence:** A [S1, S4]

### G-EX-4: Domain exception field has a 512-character limit
**Impact:** MEDIUM
**Symptom:** Cannot add all required domains to a single exception.
**Root cause:** The domain field has a hard 512-character limit.
**Mitigation:** Create multiple exceptions if you need more domains. Or use IP-based exceptions (which do support regex/wildcard) for network-level exclusions.
**Evidence:** A [S1, S4]

### G-EX-5: Broad sender/group exceptions create bypass vectors
**Impact:** CRITICAL
**Symptom:** Executive team exception allows any content from any executive to bypass DLP.
**Root cause:** A message-level exception based on sender group bypasses ALL detection for that sender, regardless of content sensitivity.
**Mitigation:** Narrow exceptions with additional conditions (e.g., recipient domain, content keyword marker). Use component-level exceptions instead of message-level when possible.
**Evidence:** B [tribal knowledge]

### G-EX-6: Encrypted file exceptions create an evasion technique
**Impact:** HIGH
**Symptom:** Users encrypt files before sending to bypass DLP detection.
**Root cause:** Exception for encrypted/password-protected archives means DLP cannot inspect these files AND does not create incidents for them.
**Mitigation:** Instead of excepting encrypted files, create a separate detection policy that FLAGS encrypted files being sent externally. Monitor encrypted file volume as a separate security indicator.
**Evidence:** B [tribal knowledge]

---

## 7. Response Rule Gotchas

### G-RR-1: Deploying blocking responses on Day 1 causes employee backlash
**Impact:** CRITICAL
**Symptom:** Legitimate business emails blocked, executives complain, DLP program loses credibility.
**Root cause:** Detection rules have not been tuned. False positives trigger blocking actions on legitimate communications.
**Mitigation:** ALWAYS start with "Test Without Notifications" mode. Graduate through: Test -> Notify -> Soft Block (User Cancel) -> Hard Block. Allow 2-4 weeks per stage for tuning. This is the single most common mistake in DLP deployments.
**Evidence:** A [V17, tribal knowledge -- "political backlash"]

### G-RR-2: Response rule conditions default to "no conditions" = always execute
**Impact:** MEDIUM
**Symptom:** Response rule fires on incidents it was not intended for.
**Root cause:** If no conditions are added to a response rule, it fires on every incident from every policy it is attached to.
**Mitigation:** Always add at least one condition (severity level, detection server type, or protocol) to scope the response rule appropriately.
**Evidence:** A [S1, S4]

### G-RR-3: Email gateway must be configured for X-header-based actions
**Impact:** HIGH
**Symptom:** "Add Header" or "Encrypt" response action does not actually encrypt the email.
**Root cause:** DLP adds an X-header to the message. The downstream email gateway must be configured to read that header and trigger encryption. Without gateway configuration, the header is ignored.
**Mitigation:** Configure the email gateway (SMG, Exchange, etc.) to process DLP X-headers BEFORE enabling header-based response rules.
**Evidence:** A [S1, S4, S13]

### G-RR-4: Smart Response rules have limited action sets
**Impact:** LOW (informational)
**Context:** Smart Response rules (manual remediation) cannot block, quarantine, or encrypt. They are limited to: set status, add note, send email notification, log.
**Implication:** Smart Response is for administrative actions by remediators, not for enforcement actions.
**Evidence:** A [S1, S4]

### G-RR-5: Syslog CEF message template variables must match exactly
**Impact:** MEDIUM
**Symptom:** SIEM receives syslog messages with blank fields instead of incident data.
**Root cause:** Typo in variable name (e.g., `$INCIDENT_ID` instead of `$INCIDENT_ID$`) produces blank output, not an error.
**Mitigation:** Test syslog message templates with a known incident. Verify all variable names match the documented list. Send test events and check SIEM output.
**Evidence:** B [API-intelligence, tribal knowledge]

### G-RR-6: Endpoint block notification appears as OS popup
**Impact:** LOW (informational)
**Context:** The endpoint block notification is a desktop popup. On busy systems, it may be obscured by other windows. Users may not see the notification.
**Mitigation:** Customize notification text with HTML formatting for visibility. Consider enabling the "User Cancel" action (with timeout) instead of silent block to ensure user awareness.
**Evidence:** A [S1, V23]

### G-RR-7: User Cancel timeout auto-blocks if user does not respond
**Impact:** MEDIUM
**Symptom:** User was away from desk; print job auto-blocked after timeout.
**Root cause:** User Cancel action has a configurable timeout. If no response, the default action (block) executes.
**Mitigation:** Set appropriate timeout based on the action type. For print: 60-120 seconds. For file transfer: 30-60 seconds. Document the timeout behavior for end users.
**Evidence:** A [S1, S4, V23]

---

## 8. Policy Gotchas

### G-POL-1: Disabled policies create undetected detection gaps
**Impact:** MEDIUM
**Symptom:** After disabling a policy, no one realizes that a class of sensitive data is no longer monitored.
**Root cause:** Disabling a policy removes its detection rules from evaluation. There is no alert that detection coverage has decreased.
**Mitigation:** Audit policy coverage when disabling any policy. Document why the policy was disabled and when it should be re-evaluated.
**Evidence:** B [tribal knowledge]

### G-POL-2: Policy evaluation order -- highest severity rule wins
**Impact:** LOW (informational)
**Context:** When multiple rules in the same policy match the same content, the incident is assigned the highest severity among the matching rules.
**Implication:** If you want different response actions at different severity levels, ensure your response rules have severity conditions.
**Evidence:** A [S1, S4]

### G-POL-3: Template defaults may not match your environment
**Impact:** MEDIUM
**Symptom:** Policy from template generates excessive incidents or misses expected content.
**Root cause:** Templates are designed for broad applicability. Default thresholds, data identifiers, and exceptions may not match your specific data patterns.
**Mitigation:** Always review and customize template-based policies before production deployment. Adjust thresholds, add exceptions for known business processes, and verify data identifier settings.
**Evidence:** A [S1, S4, V16]

### G-POL-4: Adding too many policies to Default Policy Group degrades performance
**Impact:** HIGH
**Symptom:** Detection servers slow down; incident creation latency increases.
**Root cause:** Every policy in the Default Policy Group is evaluated by every detection server on every piece of inspected content.
**Mitigation:** Use custom policy groups to target policies to specific detection servers. Only keep essential, broad-coverage policies in the Default group.
**Evidence:** B [S1, S4]

### G-POL-5: Policy import/export XML may contain environment-specific references
**Impact:** MEDIUM
**Symptom:** Imported policy references EDM profile or directory group that does not exist in the target environment.
**Root cause:** Policy XML contains references to data profiles, directory groups, and response rules by name or ID. These may differ between environments.
**Mitigation:** After importing, review all policy references. Re-link data profiles, directory connections, and response rules to the target environment's objects.
**Evidence:** B [API-intelligence]

---

## 9. Deployment & Infrastructure Gotchas

### G-INF-1: Oracle 19c required for DLP 16.0 (breaking change)
**Impact:** CRITICAL
**Symptom:** DLP 16.0 installation or upgrade fails.
**Root cause:** DLP 16.0 dropped support for Oracle 12c/18c. Oracle 19c must be installed/upgraded before DLP 16.0.
**Mitigation:** Run Upgrade Readiness Tool (URT) before upgrade. Upgrade Oracle to 19c first, verify database functionality, then upgrade DLP.
**Evidence:** A [S1, V-gotcha]

### G-INF-2: Load balancer without "Source IP persistence" causes split incident data
**Impact:** HIGH
**Symptom:** Endpoint agents report to different Endpoint Prevent Servers, causing split or missing incident data.
**Root cause:** Without sticky sessions (source IP persistence), the load balancer distributes requests round-robin across Endpoint Servers. An agent may check in with Server A, then Server B, causing data fragmentation.
**Mitigation:** Configure load balancer with "Source IP persistence" set to 24 hours. This ensures each agent always communicates with the same Endpoint Server.
**Evidence:** B [tribal knowledge, KB article]

### G-INF-3: DLP Agent policy push takes up to 15 minutes
**Impact:** MEDIUM
**Symptom:** Policy change does not take effect on endpoints immediately after deployment.
**Root cause:** DLP Agents check in with the Endpoint Prevent Server every 15 minutes. Policy changes propagate at the next check-in.
**Mitigation:** Accept the 15-minute propagation window. For urgent policy changes, consider forcing an agent check-in via the Enforce console (if available) or waiting the full 15 minutes before testing.
**Evidence:** A [S1, S4]

### G-INF-4: Agent package build locks in Endpoint Server address type
**Impact:** MEDIUM
**Symptom:** After network migration, agents cannot connect because the embedded server address is invalid.
**Root cause:** The identification type (IP, hostname, FQDN) specified during agent package build is baked into the agent installer. Changing it later requires a new agent build and redeployment.
**Mitigation:** Use FQDN for the Endpoint Server address during package build. FQDNs survive IP changes and network migrations.
**Evidence:** B [V29, tribal knowledge]

### G-INF-5: DMZ Endpoint Servers required for remote/VPN workers
**Impact:** HIGH
**Symptom:** Remote agents queue incidents locally and only sync when on corporate network.
**Root cause:** Without DMZ-facing Endpoint Servers, remote agents cannot reach the corporate Endpoint Server.
**Mitigation:** Deploy 2+ Endpoint Prevent Servers in the DMZ. Configure agents to fail over between LAN and DMZ servers.
**Evidence:** B [tribal knowledge]

### G-INF-6: SSL cipher suite mismatch between Enforce and Detection Servers
**Impact:** HIGH
**Symptom:** Detection servers cannot register or communicate with Enforce Server.
**Root cause:** SSLcipherSuites settings must match between Enforce Server and all Detection Servers.
**Mitigation:** Verify SSLcipherSuites settings on all servers after installation or TLS configuration changes.
**Evidence:** B [V-gotcha, KB article]

### G-INF-7: Local drive monitoring on endpoints kills performance
**Impact:** HIGH
**Symptom:** Endpoint becomes sluggish; users complain about application slowdowns.
**Root cause:** Monitoring every file created/modified on local drives forces the DLP agent to inspect all file I/O, which is extremely resource-intensive.
**Mitigation:** Be selective about endpoint monitoring channels. Disable local drive monitoring unless specifically needed. Focus on: USB, email client, web browser, clipboard, print.
**Evidence:** A [tribal knowledge, KB 176182]

---

## 10. API & Integration Gotchas

### G-API-1: No API for individual rule/classification CRUD (on-prem)
**Impact:** CRITICAL
**Symptom:** Cannot automate policy authoring via API. All rule creation must be done in the console.
**Root cause:** The Enforce Server REST API covers policy list, import/export, and deployment, but NOT individual rule, classification, EDM profile, IDM profile, VML profile, or response rule creation.
**Mitigation:** Use the policy import/export API (DLP 25.1+) as a workaround. Author policies in the console, export as XML, store in version control, and import to other environments via API. This enables a "DLP-as-code" workflow.
**Evidence:** A [API-intelligence]

### G-API-2: CloudSOC API is a separate surface from on-prem API
**Impact:** MEDIUM
**Symptom:** API calls that work against Enforce Server fail against CloudSOC (different endpoints, different auth).
**Root cause:** On-prem and cloud have distinct API surfaces: Enforce REST API (Basic/Kerberos/JWT auth) vs. CloudSOC API (API key/OAuth2, different base URL).
**Mitigation:** Maintain separate integration codebases for on-prem and cloud APIs. The CloudSOC API actually has MORE granular policy authoring (profile creation with embedded rules) than the on-prem API.
**Evidence:** A [API-intelligence]

### G-API-3: No native webhook support -- polling required for event-driven architectures
**Impact:** MEDIUM
**Symptom:** Cannot receive real-time notifications via HTTP callback when incidents are created.
**Root cause:** Symantec DLP does not support outbound webhooks. Event notification uses syslog (push) or API polling (pull).
**Mitigation:** Use syslog response rules for near-real-time event streaming to SIEM/SOAR. For API-based consumers, poll the incident API at regular intervals (e.g., every 60 seconds).
**Evidence:** A [API-intelligence]

### G-API-4: No OpenAPI/Swagger specification available
**Impact:** MEDIUM
**Symptom:** Cannot auto-generate client libraries or mock API for testing.
**Root cause:** Symantec DLP documents its API via HTML pages, PDFs, and an interactive portal -- not a standard OpenAPI spec.
**Mitigation:** Manually create OpenAPI specification from documentation if needed for client generation. Community client libraries are available in Python and PowerShell.
**Evidence:** A [API-intelligence]

---

## 11. Upgrade & Migration Gotchas

### G-UPG-1: Direct upgrade from pre-15.7 to 16.0 is NOT supported
**Impact:** CRITICAL
**Symptom:** Upgrade fails or produces corrupted installation.
**Root cause:** Versions 14.x and 15.0-15.5 must first be upgraded to 15.7 or 15.8, then to 16.0.
**Mitigation:** Follow the supported upgrade path: 14.x -> 15.7/15.8 -> 16.0. Run Upgrade Readiness Tool at each stage.
**Evidence:** A [V-gotcha]

### G-UPG-2: Version numbers jump from 16.x to 25.1 (no 17-24)
**Impact:** LOW (informational)
**Context:** Broadcom's acquisition caused version renumbering. There are no versions 17 through 24.
**Evidence:** A [S1]

### G-UPG-3: SOAP API deprecated in 16.0 -- REST API is required
**Impact:** HIGH
**Symptom:** Existing SOAP API integrations break after upgrade to 16.0.
**Root cause:** SOAP Incident Reporting API is deprecated (still functional for backward compatibility but may be removed in future versions).
**Mitigation:** Migrate all SOAP API integrations to REST API before or during upgrade to 16.0+.
**Evidence:** A [S1, API-intelligence]

---

## 12. Operational Gotchas

### G-OPS-1: "Cherry-picking" advanced detection is a common mistake
**Impact:** HIGH
**Symptom:** Organization only uses keyword matching when EDM, IDM, or VML would be more accurate.
**Root cause:** Keywords are easiest to configure. EDM/IDM/VML require data preparation and ongoing maintenance. Teams default to the easiest option.
**Mitigation:** Invest in EDM for structured data (customer/employee records), IDM for confidential documents, and VML for unstructured IP classification. Keywords should be a supplement, not the primary detection method for important data.
**Evidence:** B [tribal knowledge]

### G-OPS-2: Incident volume overwhelms security team
**Impact:** HIGH
**Symptom:** Thousands of incidents per day; security team ignores DLP alerts.
**Root cause:** Overly sensitive detection rules combined with too few exceptions. Monitoring-only policies without incident data retention limits.
**Mitigation:** Tune detection rules to reduce false positives (target <5% FP rate). Set incident data retention limits on high-volume policies. Use severity-based triage (address High first, batch-process Low/Informational).
**Evidence:** B [V17, tribal knowledge]

### G-OPS-3: No one reviews the exception list after initial deployment
**Impact:** HIGH
**Symptom:** Exceptions accumulate. Some were for temporary situations that ended months ago. Security gaps grow silently.
**Root cause:** No built-in exception expiration mechanism. No audit alert when exception count grows.
**Mitigation:** Schedule quarterly exception reviews. Document reason and expected expiration for every exception. Track exception count as a security metric.
**Evidence:** B [tribal knowledge]

### G-OPS-4: Test data in production incidents
**Impact:** MEDIUM
**Symptom:** Incident database contains test incidents mixed with real incidents, complicating reporting and metrics.
**Root cause:** Using real-format test data (e.g., test credit card 4111-1111-1111-1111) against production policies.
**Mitigation:** Use a dedicated test policy group and test detection server. Keep test incidents separate from production incidents. Or purge test incidents after validation.
**Evidence:** B [general practice]

### G-OPS-5: Policy mode changes require explicit "Save" and "Apply"
**Impact:** MEDIUM
**Symptom:** Changed policy mode (e.g., from Test to Enabled) does not take effect.
**Root cause:** Mode changes in the policy editor must be saved. Depending on the version, an explicit "Apply" action may be needed to push changes to detection servers.
**Mitigation:** Always verify policy status after making changes. Check the policy list to confirm the status badge reflects the intended mode.
**Evidence:** A [S1, S4]

---

## Summary: Top 10 Gotchas by Impact

| Rank | Gotcha ID | Summary | Impact |
|------|-----------|---------|--------|
| 1 | G-RR-1 | Deploying blocking on Day 1 causes employee backlash | CRITICAL |
| 2 | G-INF-1 | Oracle 19c required for DLP 16.0 | CRITICAL |
| 3 | G-UPG-1 | Direct upgrade from pre-15.7 to 16.0 not supported | CRITICAL |
| 4 | G-EX-5 | Broad sender/group exceptions create bypass vectors | CRITICAL |
| 5 | G-API-1 | No API for individual rule CRUD (console-only) | CRITICAL |
| 6 | G-EDM-1 | Stale EDM indexes miss new data (silent failure) | HIGH |
| 7 | G-INF-2 | Load balancer without Source IP persistence | HIGH |
| 8 | G-INF-7 | Local drive monitoring kills endpoint performance | HIGH |
| 9 | G-OPS-1 | Cherry-picking keywords instead of EDM/IDM/VML | HIGH |
| 10 | G-DT-5 | OCR must be explicitly enabled for image detection | HIGH |

---

*End of gotchas document. Total gotchas documented: 47 across 12 categories. Every gotcha includes impact level, root cause, and mitigation.*
