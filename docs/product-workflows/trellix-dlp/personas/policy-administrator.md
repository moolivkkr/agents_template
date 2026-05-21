# Policy Administrator -- Workflow Summary

> Generated: 2026-05-21 | Capability: Authoring Policies | Persona: Primary

---

## Role Overview

The Policy Administrator creates and maintains DLP policies that protect sensitive data across all egress channels. They work across all 6 configuration levels, from defining regex patterns and keyword dictionaries to deploying policies to thousands of endpoints via the ePO System Tree. This is the primary user of the policy authoring capability and the person most impacted by the console-only API gaps.

**Typical profile:** Information Security Engineer, DLP Analyst, or Security Operations team member with ePO console access and DLP Administrator permissions.

**Prerequisite knowledge:** ePO System Tree navigation, regular expressions (RE2 syntax), Active Directory group structure, organizational data classification taxonomy.

---

## Daily Flow

```
+----------------+   +------------------+   +---------------+   +--------------+   +--------------+   +----------------+
| 1. Define      | > | 2. Classify      | > | 3. Create     | > | 4. Group     | > | 5. Assign    | > | 6. Deploy      |
| Patterns       |   | Content          |   | Rules         |   | Rule Sets    |   | Policy       |   | to Systems     |
| (15-30 min)    |   | (15-30 min)      |   | (10-15 min    |   | (5 min)      |   | (5 min)      |   | (5-60 min)     |
|                |   |                  |   | per rule)     |   |              |   |              |   |                |
| Regex, dicts,  |   | AND/OR criteria, |   | 9 rule types, |   | Organize     |   | Policy       |   | System Tree,   |
| doc properties |   | score thresholds |   | reactions,    |   | related      |   | Catalog,     |   | Wake Up Agents |
|                |   |                  |   | severity      |   | rules        |   | rule set     |   |                |
| API: GAP       |   | API: GAP         |   | API: GAP      |   | API: GAP     |   | binding      |   | API: FULL      |
|                |   |                  |   |               |   |              |   | API: PARTIAL |   |                |
+----------------+   +------------------+   +---------------+   +--------------+   +--------------+   +----------------+
```

---

## Capability Touchpoints

| Capability | How Used | Frequency | Complexity | API Automatable? |
|-----------|---------|-----------|------------|-----------------|
| Classification Definitions (regex, dictionaries) | Create patterns for sensitive data detection | Weekly (new data types) | HIGH -- RE2 regex, score tuning | NO -- console only |
| Policy Manager Definitions (users, emails, URLs) | Define who/where/which-apps for rule scoping | Monthly (org changes) | MEDIUM -- AD group selection | PARTIAL -- email/URL lists importable |
| Content Classifications | Assemble definitions into "what to protect" objects | Weekly (new classifications) | HIGH -- boolean logic, score thresholds | NO -- console only |
| Data Protection Rules (9 types) | Create enforcement rules per channel | Weekly (new rules or tuning) | HIGH -- 9 types, reaction matrix | NO -- console only |
| Rule Sets | Organize rules into deployable groups | Monthly (reorganization) | LOW -- simple container | NO -- console only |
| DLP Policy in Policy Catalog | Top-level policy with settings | Monthly (new policies) | MEDIUM -- application strategy, privileged users | PARTIAL -- find/assign via API |
| System Tree Assignment | Connect policy to endpoints | Monthly (new groups) | LOW -- dropdown selection | YES -- policy.assignToGroup |
| Policy Deployment | Push to endpoints | Daily (after changes) | LOW -- wake up agents | YES -- dlp.applyPolicies |
| Incident Review | Review violations, tune rules | Daily | MEDIUM -- incident triage | YES -- REST API for incidents |
| Policy Backup | Backup before changes | Weekly | LOW -- one click | YES -- dlp.createBackup |

---

## Narrative

### 1. Define Detection Patterns (15-30 min)

**Screen:** Menu > Data Protection > Classification > Definitions tab (for Classification Definitions)
**Screen:** Menu > Data Protection > DLP Policy Manager > Definitions tab (for Policy Manager Definitions)

**Actions:**
- Create Advanced Pattern definitions using RE2 regex syntax for structured data (SSN, credit cards, custom identifiers)
- Build Dictionary definitions with weighted keywords for unstructured data (medical terms, financial jargon, project codenames)
- Configure Document Properties matchers for metadata-based detection (author, title, custom properties)
- Set up True File Type definitions for binary detection that survives file renaming
- Import Email Address Lists and URL Lists for rule scoping (these two are API-automatable via `dlp.importDefinitions`)
- Create End-User Groups referencing Active Directory groups for user-based rule scoping

**Key Decisions:**
- **Regex vs EDM vs IDM:** Structured data with known records (SSN+Name+DOB) benefits from EDM fingerprinting. Unstructured documents benefit from IDM content fingerprinting. General patterns (any credit card number) use regex.
- **Validator selection:** Luhn 10 for credit card patterns (dramatically reduces false positives). No validator for SSN patterns (use proximity matching with dictionaries instead).
- **Score weighting:** High-confidence patterns (full SSN with dashes) get score 10; partial matches (9-digit number without dashes) get score 1. Classification threshold determines sensitivity.

**Gotcha:** "Definitions created under Classification > Definitions are ONLY visible to Classifications. Definitions created under DLP Policy Manager > Definitions are ONLY visible to Rules. Creating a definition in the wrong context means you cannot find it when you need it." [Source: S73 community post, video research]

**API:** GAP -- All definition creation is manual. Only email lists, URL lists, and end-user groups (CSV) can be imported via `dlp.importDefinitions`.

---

### 2. Build Classifications (15-30 min per classification)

**Screen:** Menu > Data Protection > Classification > [New or existing classification] > Content Classification Criteria tab

**Actions:**
- Create a new classification (Actions > New Classification) or duplicate a built-in one (PII, HIPAA, PCI-DSS, etc.)
- Add criteria using the visual condition builder: select definition type (Advanced Pattern, Dictionary, etc.)
- Combine criteria with AND/OR logic -- e.g., "SSN pattern AND medical dictionary term within 100 characters"
- Set score thresholds -- e.g., "total score must exceed 10 to trigger" (each pattern/dictionary entry contributes its score)
- Set occurrence count -- e.g., "at least 3 SSN matches in the same document"
- Optionally configure EDM criteria (for structured data fingerprints)
- Optionally configure Manual Classification labels (for user-applied tags)
- Test classification using the built-in Classification Tester tool

**Key Decisions:**
- **Built-in vs custom:** Built-in classifications (100+ country-specific PII, HIPAA, PCI-DSS) are read-only but can be duplicated and customized. Use built-ins as starting points.
- **Score threshold tuning:** Too low = false positives flood. Too high = missed detections. Start at the default, deploy in Monitor mode, and adjust based on incident volume.
- **AND vs OR grouping:** Use AND for high-confidence detection (SSN + Name + Address). Use OR for broad detection (any of these patterns triggers).

**Gotcha:** "Protection rules referencing a classification with empty criteria (no configured definitions) will NEVER trigger. The rule shows as Enabled with no indication of the problem. Always test classifications before creating rules." [Source: Video #4]

**API:** GAP -- Classification CRUD is entirely console-only. Cannot programmatically create, edit, or manage classifications.

---

### 3. Create Data Protection Rules (10-15 min per rule)

**Screen:** Menu > Data Protection > DLP Policy Manager > Rule Sets > [Rule Set Name] > Add Rule > [Select rule type]

**Actions:**
- Select one of 9 rule types based on the data channel to protect:
  - **Email Protection** -- Outlook, SMTP gateway
  - **Web Protection** -- HTTP/HTTPS web posts, browser uploads
  - **Cloud Protection** -- OneDrive, Dropbox, Google Drive, Box
  - **Removable Storage Protection** -- USB, external media
  - **Network Share Protection** -- SMB/CIFS file shares
  - **Network Communication Protection** -- FTP, IM, custom protocols
  - **Clipboard Protection** -- Copy/paste between applications
  - **Printer Protection** -- Local, network, virtual (PDF) printers
  - **Application File Access Protection** -- Application read/write of files
- On the Condition tab: select classification(s), optionally scope by End-User Group, Application, file conditions
- On the Reaction tab: select action (Monitor, Block, Encrypt, Request Justification, etc.)
- Configure user notification message (popup text shown to end user)
- Set severity (Critical/High/Medium/Low/Informational)
- Enable "Report to ePO" to generate incidents in DLP Incident Manager
- Optionally enable "Store Original Evidence" to capture triggering data

**Key Decisions:**
- **Action selection:** Start with Monitor for all new rules. Switch to Request Justification for validated rules. Only escalate to Block for high-confidence, tested rules with low false positive rates.
- **Severity assignment:** Drives incident prioritization. Critical = immediate SOC review. Informational = audit trail only.
- **Notification text:** Clear, actionable messages reduce help desk tickets. Example: "This action was blocked because the content matches our PCI-DSS data protection policy. If this is a false positive, contact security@company.com."

**Gotcha:** "A 'block all' USB rule without device-type scoping can block USB keyboards and mice, making endpoints unusable. ALWAYS deploy removable storage rules in Monitor mode first." [Source: Jay Appell DLP 001/002]

**API:** GAP -- Rule CRUD is entirely console-only. Cannot create, edit, enable/disable, or delete rules via API.

---

### 4. Group into Rule Sets (5 min)

**Screen:** Menu > Data Protection > DLP Policy Manager > Rule Sets tab

**Actions:**
- Create a new Rule Set (Actions > New Rule Set) or use a pre-built compliance template (GDPR, HIPAA, PCI-DSS, etc.)
- Add rules created in Step 3 to the Rule Set
- Arrange rule priority order (top-to-bottom evaluation within the set)
- Enable/disable entire Rule Set or individual rules within it
- Optionally export Rule Set for backup or sharing with other ePO instances

**Key Decisions:**
- **One rule set per compliance framework** is the recommended organizational pattern (e.g., "PCI-DSS Rules," "HIPAA Rules," "Company IP Rules")
- **Rule ordering:** Place higher-severity Block rules above lower-severity Monitor rules

**Naming convention (tribal knowledge):** `[Channel]-[Compliance]-[DataType]-[Action]-[Version]`
Examples: `Email-PCIDSS-CreditCard-Block-v2`, `Web-HIPAA-PHI-Monitor-v1`

**API:** GAP -- Rule set CRUD is entirely console-only.

---

### 5. Assign to Policy (5 min)

**Screen:** Menu > Policy > Policy Catalog > Product: "Data Loss Prevention [version]" > DLP Policy

**Actions:**
- Create a new DLP Policy (Actions > New Policy) or duplicate existing
- Configure global settings: Application Strategy (Trusted/Monitored/Unknown for unlisted apps)
- Configure Privileged Users (AD accounts exempt from all DLP enforcement)
- Assign one or more Rule Sets to the Policy
- Arrange Rule Set priority order
- Save

**Key Decisions:**
- **Application Strategy:** "Monitored" is safest (all apps are monitored by default). "Trusted" exempts unlisted apps.
- **Privileged Users:** Use sparingly -- typically IT admins and security team members only. Every privileged user is a potential data loss vector.

**API:** PARTIAL -- `policy.find` can locate policies, `policy.assignToGroup` can assign them to System Tree groups. But creating/editing policy content (rule set binding, settings) is console-only.

---

### 6. Deploy to Systems (5-60 min)

**Screen:** Menu > Systems > System Tree > [select group] > Assigned Policies tab

**Actions:**
1. Select target group in System Tree
2. Click "Edit Assignment" for the DLP Policy category
3. Select the policy from dropdown
4. Save assignment
5. For immediate deployment: Actions > Agent > Wake Up Agents > check "Force complete policy update"
6. Wait for agents to receive policy (immediate with wake-up, or up to 60 min on default ASCI)

**Key Decisions:**
- **Scope of deployment:** Start with a small pilot group (e.g., IT department). Expand to broader groups only after monitoring period confirms acceptable false positive rates.
- **Immediate vs scheduled:** Use Wake Up Agents for urgent changes. Otherwise, let the regular ASCI cycle distribute changes during the next communication interval.

**Gotcha:** "Policy changes are NOT automatically pushed to endpoints. The 'Allow Policy Push' setting must be explicitly activated, AND agents must either reach their ASCI interval (default: 60 minutes) or be manually woken up." [Source: S72, Video #7]

**API:** FULL -- This is the most automatable step:
- `policy.assignToGroup` -- assign policy to a System Tree group
- `dlp.applyPolicies` -- trigger policy push to all endpoints
- `system.applyTag` -- tag systems for dynamic policy assignment via server tasks

---

## Pain Points

1. **Dual definition namespaces cause confusion** -- The most frequently reported admin frustration. Classification Definitions and Policy Manager Definitions are separate, invisible to each other, and some types (Advanced Patterns, Dictionaries) exist in both contexts.

2. **No API for policy authoring** -- Cannot script repeatable deployments. Every policy change requires manual console interaction across multiple screens. Multi-tenant environments must repeat the same configuration manually per tenant.

3. **Agent communication interval delays testing** -- The 60-minute default ASCI means a test cycle (change rule > deploy > test > review incident) takes at least 60 minutes unless the admin remembers to manually wake up agents every time.

4. **RE2 regex limitations require pattern rewriting** -- Patterns from other DLP products, compliance frameworks, or regex libraries that use lookahead/lookbehind/backreferences must be rewritten for RE2 compatibility. There is no error message when an unsupported pattern is entered -- it silently fails.

5. **Silent rule failures** -- Rules referencing empty or misconfigured classifications show as "Enabled" with no warning. The admin has no indication that their rule is not matching any data until they notice zero incidents over days/weeks.

6. **No version control for policies** -- Policy changes cannot be tracked, diffed, or rolled back. The only safeguard is the manual backup (`dlp.createBackup`), which creates a full snapshot but not incremental change history.

---

## Automation Opportunities

### What IS Automatable Today

| Operation | API | Use Case |
|-----------|-----|----------|
| Import email/URL/user lists | `dlp.importDefinitions` | Automated list updates from threat intelligence feeds or HR systems |
| Deploy policies to endpoints | `dlp.applyPolicies` | Scheduled or event-triggered policy push |
| Assign policies to groups | `policy.assignToGroup` | Automated onboarding: new system group gets default DLP policy |
| Query incidents | `/rest/dlp/event/incidents` | SIEM integration, automated triage, dashboards |
| Retrieve evidence | `/rest/dlp/event/evidence/get` | Automated evidence collection for forensic workflows |
| Backup policy configuration | `dlp.createBackup` | Scheduled pre-change backups |
| Tag systems | `system.applyTag` | Dynamic policy assignment via tags + server tasks |
| Run saved queries | `core.executeQuery` | Automated compliance reporting |

### What WOULD Be Automatable If API Existed

| Operation | Impact | Competitive Opportunity |
|-----------|--------|------------------------|
| Create/edit classifications | CRITICAL | Policy-as-code: define "what is sensitive" in version-controlled YAML/JSON |
| Create/edit rules | CRITICAL | Templated rule generation across environments (dev/staging/prod) |
| Create/edit rule sets | HIGH | Automated rule organization and compliance template management |
| Create regex/dictionary definitions | HIGH | Automated pattern library updates from threat intelligence |
| Enable/disable rules | HIGH | Automated incident response: disable a noisy rule via playbook |
| Export/import classifications | HIGH | Classification migration between ePO instances (dev > prod) |

---

## Time Estimate

| Scenario | Time | Notes |
|----------|------|-------|
| First policy from scratch (single channel) | 2-3 hours | Including learning the hierarchy |
| First policy using compliance template | 45-60 min | Duplicate template + assign + deploy |
| Additional rule in existing policy | 15-30 min | Classification + rule + reaction |
| Full multi-channel policy with EDM | 1-2 days | All 9 rule types + EDM fingerprinting |
| Production-ready policy suite | 1-2 weeks | All channels + 2-4 week monitoring phase |

## Complexity: COMPLEX
