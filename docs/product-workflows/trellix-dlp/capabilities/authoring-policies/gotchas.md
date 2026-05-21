# Authoring Policies -- Known Limitations & Tribal Knowledge
## Trellix DLP (ePO-managed, version 11.x)

> Capability: authoring-policies | Generated: 2026-05-21
> Sources aggregated: Video research (13 tribal knowledge items, 10 gotchas), API research (12 console-only gaps), Doc research (11 documentation gaps), Community forums

---

## Critical Gotchas (Will Break Your Deployment If Ignored)

### 1. Regex Engine is RE2, NOT PCRE -- Negative Lookahead/Lookbehind Not Supported

**Impact:** HIGH -- Classification rules using unsupported regex features silently fail or cause errors. Patterns that work in regex testers (regex101.com, etc.) may not work in Trellix DLP.

**Details:** Trellix DLP uses the RE2 regex engine. RE2 does NOT support:
- Negative lookahead: `(?!...)`
- Negative lookbehind: `(?<!...)`
- Positive lookbehind: `(?<=...)`
- Backreferences: `\1`, `\2`
- Atomic groups
- Possessive quantifiers

**Workaround:** Rewrite patterns to use only RE2-supported syntax. Use character classes, alternation, and the "Ignored Expressions" field to exclude false positives instead of lookahead/lookbehind.

**Source:** Trellix docs, Skyhigh Security documentation, video gotcha #6
**Evidence Grade:** A

---

### 2. Two Definition Namespaces -- Classification vs Policy Manager Definitions Are NOT Shared

**Impact:** HIGH -- Admins frequently create a definition in the wrong context, then cannot find it when configuring a classification or rule.

**Details:** Definitions exist in TWO separate, invisible-to-each-other namespaces:
- **Classification Definitions** (Menu > Data Protection > Classification > Definitions tab) -- usable ONLY in classification criteria
- **Policy Manager Definitions** (Menu > Data Protection > DLP Policy Manager > Definitions tab) -- usable ONLY in rule conditions

A Dictionary created under Classification Definitions is invisible when configuring Rule conditions. An End-User Group created under Policy Manager Definitions is invisible in Classification criteria.

**Workaround:** Understand which definition types belong where:
- Content-matching definitions (regex, dictionaries, file types) go in Classification Definitions
- Source/destination definitions (users, emails, URLs, networks, apps) go in Policy Manager Definitions
- Some types (Advanced Patterns, Dictionaries) exist in BOTH contexts -- you may need to create them in both places

**Source:** S73 community post, doc-corpus section on definitions
**Evidence Grade:** A

---

### 3. Protection Rules Referencing Undefined Classifications Will Not Trigger

**Impact:** CRITICAL -- Rules appear active and enabled but NEVER match any data. No error or warning is displayed.

**Details:** If a rule's Classification reference points to a classification that has no configured criteria (empty criteria list), or the classification references a definition that has been deleted, the rule will silently never trigger. The rule shows as "Enabled" in the console with no indication of the problem.

**Workaround:** Always create and TEST classifications BEFORE creating protection rules. Use the Classification Tester tool (available in the Classification interface) to verify that your classification matches expected content. After creating a rule, generate test violations to confirm the rule triggers.

**Source:** Video #4 (Creating Custom DLP Policy), video gotcha #9
**Evidence Grade:** B

---

### 4. DLP Policy Assignment is System-Based Only -- User-Based Assignment Does NOT Work

**Impact:** HIGH -- Admins who attempt to use ePO's user-based policy assignment rules for DLP discover that it has no effect.

**Details:** DLP policies can only be assigned to SYSTEMS via the ePO System Tree. ePO's "Policy Assignment Rules" feature (which supports user-based assignment for other products) does NOT work with DLP. The DLP product explicitly does not support this assignment method.

**Workaround:** Use End-User Groups within individual rules to scope enforcement per-user. The policy itself is assigned to systems (machine groups), but rules inside the policy can target specific AD users/groups.

**Source:** S73 Trellix community forum post
**Evidence Grade:** A

---

### 5. Policy Push Must Be Explicitly Allowed -- "Allow Policy Push" Does Not Auto-Apply Changes

**Impact:** HIGH -- Configuration changes sit in staging and are NOT deployed to endpoints until explicitly pushed.

**Details:** After making changes to DLP policies, classifications, or rules in the ePO console, the changes are saved to the ePO database but are NOT automatically pushed to endpoints. The "Allow Policy Push" setting must be explicitly activated, AND agents must either reach their ASCI interval or be woken up.

**Workaround:** After saving policy changes:
1. Review all changes
2. Explicitly select "Allow Policy Push" (if this setting is required in your ePO configuration)
3. Navigate to System Tree > select target systems > Actions > Agent > Wake Up Agents
4. Check "Force complete policy update"
5. Wait 1-2 minutes for deployment

**Source:** Trellix docs 11.11.x, video gotcha #7
**Evidence Grade:** A

---

## Deployment Gotchas

### 6. USB "Block All" Rule Can Block Keyboards and Mice

**Impact:** HIGH -- Endpoints become unusable if input devices are classified as removable storage and blocked.

**Details:** A Removable Storage Protection rule configured to "Block" with no device-type scoping will apply to ALL USB devices, potentially including USB keyboards, mice, and other HID devices that the OS treats as removable.

**Workaround:**
1. ALWAYS deploy in Monitor mode first (Action = Monitor, not Block)
2. Review incidents for 1-2 weeks to see what devices are being detected
3. Refine the Device Type filter to target only USB storage devices, not all USB
4. Only then switch to Block action

**Source:** DLP 001/002 (Jay Appell), video tribal knowledge #10
**Evidence Grade:** B

---

### 7. DLP Bypass Mode Can Silently Disable Protection

**Impact:** HIGH -- The endpoint DLP agent may enter bypass mode under certain conditions, stopping all enforcement without alerting the end user.

**Details:** DLP Bypass Mode activates when the DLP endpoint agent encounters certain error conditions (memory pressure, driver conflicts, service crashes). In bypass mode, ALL protection rules are suspended. The agent may remain in bypass mode until restarted.

**Workaround:**
- Monitor for bypass mode events in ePO (DLP operational events)
- Configure bypass mode alerts in ePO Queries & Reports
- Regularly check endpoint DLP agent health status
- Consider setting up automated remediation via server tasks

**Source:** DLP 011 (Jay Appell), video tribal knowledge #4
**Evidence Grade:** B

---

### 8. Screen Capture Protection Fails with Multiple Browser Tabs

**Impact:** MEDIUM -- Sensitive content may be captured in multi-tab scenarios even when Screen Capture Protection is enabled.

**Details:** A known issue (KB88967) where screen capture protection does not work correctly when the user has multiple browser tabs open. The DLP agent may fail to detect the protected content in the visible tab context.

**Workaround:** Check Trellix KB88967 for patches or hotfixes. Consider supplementing screen capture rules with clipboard protection and application file access rules for defense-in-depth.

**Source:** Trellix KB88967, video gotcha #4
**Evidence Grade:** B

---

### 9. Manual Classification on Office Products Is Difficult to Remove Once Deployed

**Impact:** MEDIUM -- Once manual classification is enabled and users are trained to use it, disabling it causes confusion and may leave orphaned classification metadata in documents.

**Details:** Manual classification adds UI elements (context menus, ribbon buttons) to Microsoft Office applications. If deployed and then removed, existing documents retain their classification metadata, but users lose the ability to see or change it. The "sticky" nature of these UI elements also means that users habituate to them and disabling causes workflow disruption.

**Workaround:** Configure force-classify options carefully before deployment. Test manual classification with a pilot group first. Plan for the long term -- treat manual classification as a commitment, not an experiment.

**Source:** Trellix Community Forum, video gotcha #5
**Evidence Grade:** C

---

### 10. URL-Based Definitions Have Inconsistent Support Across Rule Types

**Impact:** MEDIUM -- URL Lists created for web protection may not work when referenced in other rule types.

**Details:** URL-based definitions are supported by Web Protection, Cloud Protection, Clipboard Protection, Printing Protection, and Screenshot Protection rules. They are NOT supported by all rule types. An admin may create a URL List definition expecting to use it in a Network Communication rule, only to find it is not available in that rule type's condition configuration.

**Workaround:** Check the Trellix documentation (11.6.x+) for which rule types support URL-based scoping before creating URL definitions for those rule types.

**Source:** Trellix docs 11.6.x, video gotcha #10
**Evidence Grade:** B

---

## API & Automation Gotchas

### 11. ENTIRE Policy Authoring Pipeline Has No API -- Console Only

**Impact:** CRITICAL -- Cannot implement DLP-as-code, CI/CD for policies, or programmatic policy management.

**Details:** The following operations have ZERO API support and require manual ePO console interaction:
1. Create/edit classifications
2. Create/edit data protection rules
3. Create/edit rule sets
4. Assign rule sets to policies
5. Create regex/pattern definitions
6. Create dictionary definitions
7. Register document fingerprints
8. Export/import classifications
9. Enable/disable individual rules
10. Create network/application definitions
11. Configure DLP Discover scans
12. Manage operational events settings

The API only supports the "last mile" -- deploying existing policies to endpoints, importing email/URL lists, and querying incidents.

**Workaround:** No workaround for policy authoring automation. All policy creation must be done manually through the ePO web console. For definition lists (email, URL), use `dlp.importDefinitions` API to automate list updates. For policy deployment, use `dlp.applyPolicies` to automate the push step.

**Source:** api-intelligence research, Trellix community forums (2019-2020 confirmation: "classification cannot be created outside the ePO console")
**Evidence Grade:** A

---

### 12. Two Divergent API Surfaces -- On-Prem vs SaaS Have Different APIs

**Impact:** MEDIUM -- Customers on hybrid deployments (on-prem ePO + SaaS) must maintain two separate integration codebases.

**Details:**
- On-prem: ePO remote commands (`https://<epo>:8443/remote/<cmd>`) + DLP REST API, using HTTP Basic auth
- SaaS: OAuth2-based REST API via Trellix Developer Portal (`https://api.manage.trellix.com/dlp/...`)

There is no unified API surface. Endpoints, auth models, and response formats differ completely.

**Workaround:** Abstract API calls behind a common interface layer if building integrations. Use ePO on-prem API for policy operations and SaaS API only if managing cloud-only DLP instances.

**Source:** api-intelligence research
**Evidence Grade:** A

---

### 13. No Native Webhooks -- Event-Driven Automation Requires OpenDXL or Syslog Parsing

**Impact:** MEDIUM -- Cannot receive push notifications when DLP events occur; must poll or parse syslog.

**Details:** Trellix DLP does not expose native webhook endpoints. There is no way to register a callback URL that receives DLP incident notifications in real-time.

**Workaround:**
- Use **OpenDXL** (DXL fabric) to subscribe to DLP events via pub/sub (requires DXL broker setup)
- Use **Syslog forwarding** (CEF/LEEF format) and parse syslog with a SIEM or custom consumer
- Use **n8n integration** (community connector) for webhook-to-ePO workflows
- Poll `/rest/dlp/event/incidents` API on a schedule

**Source:** api-intelligence research
**Evidence Grade:** A

---

## Operational Gotchas

### 14. Evidence Viewing Fails in Workgroup (Non-Domain) Environments

**Impact:** HIGH -- DLP Incident Manager cannot display evidence files from non-domain-joined endpoints.

**Details:** When endpoints are in a workgroup (not domain-joined), the evidence storage and retrieval mechanism fails. The DLP Incident Manager shows incidents but the evidence link returns an error or empty result.

**Workaround:** Ensure endpoints are domain-joined, OR configure an alternative evidence storage path that does not rely on domain authentication. Use the REST API (`/rest/dlp/event/evidence/get`) for programmatic evidence retrieval as an alternative.

**Source:** DLP 008 (Jay Appell), video tribal knowledge #3
**Evidence Grade:** B

---

### 15. DLP Event/Evidence Data Accumulates Unbounded -- Requires Periodic Purging

**Impact:** MEDIUM -- ePO database grows continuously without maintenance, eventually causing performance degradation.

**Details:** Every DLP incident, operational event, and evidence file is stored in the ePO database. Over months and years of operation, this data accumulates without limit unless explicitly purged. Large ePO databases (100K+ incidents) slow down the console and incident review workflows.

**Workaround:** Set up scheduled purge tasks:
1. Navigate to Menu > Automation > Server Tasks
2. Create a server task to purge DLP events older than N days
3. Configure evidence retention policies
4. Run purge tasks on a weekly or monthly schedule

**Source:** DLP 014 (Jay Appell), video gotcha #8
**Evidence Grade:** B

---

### 16. Policy Evaluation Order Is Not Clearly Documented

**Impact:** MEDIUM -- When multiple rules in multiple rule sets could match the same data, the order of evaluation (first-match, most-specific, cumulative) is not clearly documented.

**Details:** The official documentation does not clearly specify how rules within a rule set and rule sets within a policy are evaluated. Is it first-match-wins? Are all matching rules applied cumulatively? Does the most restrictive action win? The behavior appears to be: rules within a rule set are evaluated in the order shown (top-to-bottom), and ALL matching rules trigger (cumulative), with the most restrictive action applied.

**Workaround:** Design policies defensively:
- Place higher-severity rules above lower-severity ones in each rule set
- Use explicit Block rules above Monitor rules
- Test with specific scenarios to verify which rules trigger
- Document your expected evaluation order

**Source:** doc-corpus documentation gap #3
**Evidence Grade:** C

---

## Tribal Knowledge (Undocumented Best Practices)

### 17. Naming Convention Best Practices for Production Deployments

**Impact:** HIGH at scale -- prevents rule management chaos when operating hundreds of rules across multiple teams.

**Details:** Official Trellix documentation does not provide naming convention guidance. Community best practice (from experienced practitioners):

**Recommended naming pattern:** `[Channel]-[Compliance]-[DataType]-[Action]-[Version]`

Examples:
- `Email-PCIDSS-CreditCard-Block-v2`
- `Web-HIPAA-PHI-Monitor-v1`
- `USB-Custom-SourceCode-Justify-v3`
- `Cloud-GDPR-EUPersonalData-Block-v1`

**Source:** DLP 003 -- "Naming Rules for the Real World" (Jay Appell), video tribal knowledge #1
**Evidence Grade:** B

---

### 18. Phased Deployment Strategy: Monitor First, Block Later

**Impact:** CRITICAL -- Deploying blocking rules directly to production causes business disruption, false positive floods, and executive escalations.

**Details:** Trellix Professional Services (Ray Marken) recommends a phased approach:
1. **Phase 1 -- Discovery:** Deploy classification-only (no rules) to understand data landscape
2. **Phase 2 -- Monitor:** Deploy all rules in Monitor mode; review incidents for 2-4 weeks
3. **Phase 3 -- Educate:** Switch to Request Justification for high-confidence rules; train users
4. **Phase 4 -- Enforce:** Switch to Block for validated, low-false-positive rules
5. **Phase 5 -- Optimize:** Tune thresholds, add new channels, expand coverage

**Source:** DLP Framework by Trellix (Ray Marken, Principal Consultant), video tribal knowledge #2. Also: DLP 001/002 (Jay Appell) for USB-specific phased approach, video tribal knowledge #10
**Evidence Grade:** B

---

### 19. Tag-Based Policy Assignment for Dynamic Targeting

**Impact:** HIGH -- Static System Tree assignment is fragile for environments where systems move between groups.

**Details:** Instead of relying solely on System Tree group assignment, use ePO tags + server tasks for dynamic policy assignment:
1. Define tags based on system criteria (department, OS, sensitivity level)
2. Create server tasks that automatically apply tags based on criteria
3. Use tag-based policy assignment rules to dynamically assign DLP policies
4. Systems that change characteristics automatically get the correct policy

**Source:** Video #5 (Efficient Policy Assignment), video tribal knowledge #9
**Evidence Grade:** B

---

### 20. Single Policy Engine Across Endpoint, Network, Cloud

**Impact:** HIGH -- Architecture understanding; reduces configuration work.

**Details:** Trellix DLP uses a shared classification engine across DLP Endpoint, DLP Prevent (network), and DLP Monitor. A single email protection policy created in ePO enforces on BOTH the endpoint (Outlook plugin) and the network gateway (SMTP proxy). You do NOT need to create separate email rules for endpoint and network.

**Source:** McAfee Streamline webinar (#48), video tribal knowledge #11
**Evidence Grade:** A

---

### 21. Modern Threat Channels: AI Webchats, AirDrop, Emerging Vectors

**Impact:** HIGH -- DLP coverage must evolve beyond traditional channels.

**Details:** As of DLP Endpoint Complete (2025), Trellix has extended protection to:
- AI webchats (ChatGPT, Copilot, etc.) -- via Web Protection rules
- AirDrop (macOS) -- via new channel support
- Non-text formats -- extended content inspection
- Modern browsers -- Edge Connector (11.12.x), Chrome Enterprise integration

These newer channels may require updated Application Templates and URL Lists to be effective.

**Source:** Video #34 (Analyzing Data Protection Needs), RSAC 2025 announcements, video tribal knowledge #12
**Evidence Grade:** B

---

## Documentation Gaps (Known Unknowns)

### 22. Complete Field-Level Reference for Rule Type Screens

**Impact:** MEDIUM -- Exact field names, dropdown values, and checkbox labels for each of the 9 rule types are only fully visible in the Interface Reference Guide PDF (800+ pages, Scribd-hosted).

**Workaround:** Request access to the Trellix DLP 11.10.x Interface Reference Guide PDF (S69 in doc-corpus) or the 11.14.x Product Guide for the most current field-level reference.

**Source:** doc-corpus documentation gap #1
**Evidence Grade:** N/A (gap documentation)

---

### 23. Classification Condition Builder UI Details

**Impact:** MEDIUM -- The exact UI for building AND/OR condition trees with score thresholds is documented in the Interface Reference Guide but not in web-accessible excerpts.

**Source:** doc-corpus documentation gap #2
**Evidence Grade:** N/A (gap documentation)

---

### 24. Import/Export Format Specifications

**Impact:** MEDIUM -- The exact XML/JSON schema for importing/exporting rule sets, definitions, and policies is referenced in documentation but the schema itself is not published.

**Workaround:** Export an existing rule set to see the XML format, then use that as a template for imports.

**Source:** doc-corpus documentation gap #6
**Evidence Grade:** N/A (gap documentation)

---

### 25. Classification Tester Tool

**Impact:** LOW -- A built-in tool for testing classifications exists in the interface but usage details are not well documented in web-accessible content.

**Workaround:** The Classification Tester is accessible from the Classification page in the ePO console. Upload a test document and select a classification to test against.

**Source:** doc-corpus documentation gap #8
**Evidence Grade:** N/A (gap documentation)

---

## Summary Statistics

| Category | Count | Critical/High Impact |
|----------|-------|---------------------|
| Critical gotchas (deployment-breaking) | 5 (#1-5) | 5 |
| Deployment gotchas | 5 (#6-10) | 3 |
| API/automation gotchas | 3 (#11-13) | 1 |
| Operational gotchas | 3 (#14-16) | 1 |
| Tribal knowledge (best practices) | 5 (#17-21) | 4 |
| Documentation gaps | 4 (#22-25) | 0 |
| **Total** | **25** | **14** |
