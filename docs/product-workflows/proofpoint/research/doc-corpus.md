# Documentation Corpus: Proofpoint -- Authoring Policies
> Researched: 2026-05-21 | Sources: 28 | Version: PPS 8.22.x / Essentials (current) / ITM 7.18.0 / Data Security (current)
> Capabilities documented: 11 product lines | Gaps identified: 14
> Corpus confidence: MEDIUM -- Multiple official sources ingested but key admin guides (PPS, PoD) require authentication; reliance on grade-B/C/D sources for some areas

---

## Source Index

| # | Title | URL | Grade | Type | Version | Covers |
|---|-------|-----|-------|------|---------|--------|
| S1 | Proofpoint Essentials Administrator Guide (PDF) | https://d3xh1dlqxy2hb.cloudfront.net/pdf/proofpoint/Proofpoint-Essentials-Administrator-Guide-7-16-14.pdf | A | admin_guide | Essentials (July 2014) | Filters, spam, virus, domains, digests, disclaimers, archive, user management |
| S2 | Enterprise Protection for the Administrator (Training Datasheet) | https://www.proofpoint.com/sites/default/files/PPS-Protect-WBT-VILT_0.pdf | B | training_material | PPS (current) | PPS architecture, filtering, rule creation, policy routes, conditions, quarantine, spam module, virus module, TAP, email firewall, PDR, recipient verification, rate control |
| S3 | Proofpoint Essentials Security Awareness Admin Guide (PDF) | https://www.pax8nebula.com/m/290b594b2d79ab17/original/Proofpoint-Essentials-Security-Awareness-Training-Admin-Guide.pdf | A | admin_guide | SAT (April 2020) | Training assignments, phishing campaigns, campaign types, reports |
| S4 | ITM On-Prem Configuration Guide -- System Policy Settings | https://prod.docs.oit.proofpoint.com/configuration_guide/system_policy_settings.htm | A | admin_guide | ITM 7.18.0 | Recording controls, activity monitoring, screen capture, notification, privacy, API |
| S5 | ITM On-Prem -- Insider Threat Library Overview | https://prod.docs.oit.proofpoint.com/insider_threat_library/itl_overview.htm | A | product_guide | ITM 7.18.0 | 300+ rules, detection categories, user group targeting, rule updates |
| S6 | ITM On-Prem -- Exporting and Importing Rules | https://prod.docs.oit.proofpoint.com/configuration_guide/exporting_and_importing_rules.htm | A | admin_guide | ITM 7.18.0 | Alert rules, prevention rules, policy rules, system rules, import/export |
| S7 | Proofpoint Data Security -- Agent Policies Overview | https://docs.public.analyze.proofpoint.com/admin/agent_policies_overview.htm | A | product_guide | Data Security (current) | DLP-only vs ITM signal types, default account policy, realm assignment |
| S8 | Proofpoint Data Security -- Setting Up Agent Policies | https://docs.public.analyze.proofpoint.com/admin/agent_policies_setting_up.htm | A | admin_guide | Data Security (current) | Add/edit agent policy workflow, priority management, general settings, details |
| S9 | Proofpoint Data Security -- Agent Policy Details | https://docs.public.analyze.proofpoint.com/admin/agent_policies_details.htm | A | admin_guide | Data Security (current) | If/then logic, conditions, settings, DLP toggle, screenshots, prevention rules |
| S10 | Proofpoint Data Security -- Detection Rules | https://docs.public.analyze.proofpoint.com/rules/rules_detection.htm | A | admin_guide | Data Security (current) | Rule creation, conditions, severity, rule sets, actions, notifications, tags |
| S11 | Proofpoint Data Security -- Prevention Rules | https://docs.public.analyze.proofpoint.com/rules/prevention_rules_overview.htm | A | admin_guide | Data Security (current) | Block, prompt, allow actions, data redaction for GenAI, file retention |
| S12 | Proofpoint Data Security -- ITM/Endpoint DLP Rules Overview | https://docs.public.analyze.proofpoint.com/rules/rules_overview.htm | A | product_guide | Data Security (current) | Policy rules, prevention rules, endpoint rules, 100-rule limit |
| S13 | Proofpoint CASB Overview | https://docs.public.analyze.proofpoint.com/pcasb/casb_overview.htm | A | product_guide | Data Security (current) | Threat protection, access control, DLP, app visibility, infrastructure security |
| S14 | Proofpoint Encryption Data Sheet | https://www.proofpoint.com/sites/default/files/pfpt-us-ds-encryption.pdf | B | product_guide | Encryption (current) | Policy-based encryption, AES-256, key management, triggers, TLS fallback, Secure Reader |
| S15 | Proofpoint Isolation Data Sheet | https://www.proofpoint.com/sites/default/files/pfpt-us-ds-browser-isolation.pdf | B | product_guide | Isolation (Aug 2023) | URL isolation, browser isolation, DLP integration, adaptive security, browsing policies |
| S16 | Proofpoint Protection Server v2 XSOAR Integration | https://xsoar.pan.dev/docs/reference/integrations/proofpoint-protection-server-v2 | C | integration_guide | PPS 8.16.2 / 8.14.2 | Smart search, quarantine management, policy routes, disposition, user management API |
| S17 | How to Configure Email Filtering Policies in Proofpoint (InventiveHQ) | https://inventivehq.com/knowledge-base/proofpoint/how-to-configure-email-filtering | D | third_party_guide | Essentials (current) | Filter creation, conditions, actions, scope, priority, testing protocol |
| S18 | How to Configure DLP Rules in Proofpoint (InventiveHQ) | https://inventivehq.com/knowledge-base/proofpoint/how-to-configure-dlp-rules | D | third_party_guide | Essentials (current) | DLP policy creation, smart identifiers, dictionaries, regex, encryption integration |
| S19 | How to Manage the Quarantine Console in Proofpoint (InventiveHQ) | https://inventivehq.com/knowledge-base/proofpoint/how-to-manage-quarantine | D | third_party_guide | Essentials (current) | Quarantine types, release procedures, digest configuration, retention |
| S20 | Proofpoint Community -- Email Firewall Rule (PPS/PoD) | https://proofpoint.my.site.com/community/s/article/VIDEO-How-to-enable-or-modify-Email-Firewall-Rule-in-Proofpoint-Protection-Server | C | kb_article | PPS/PoD (current) | Email firewall rules, enable/modify |
| S21 | Proofpoint Community -- TAP Sender Exemption | https://proofpoint.my.site.com/community/s/article/TAP-How-to-exempt-a-sender-from-TAP-alerts | C | kb_article | TAP (current) | TAP alert exemptions |
| S22 | Proofpoint Community -- Enabling TAP for User Groups | https://proofpoint.my.site.com/community/s/article/Enabling-TAP-Attachment-Defense-and-or-URL-Defense-for-a-specific-group-of-users | C | kb_article | TAP (current) | TAP per-group enablement |
| S23 | Proofpoint Adaptive Email DLP Product Page | https://www.proofpoint.com/us/products/adaptive-email-dlp | B | product_guide | Adaptive DLP (current) | Behavioral AI, misdirected email, human error prevention |
| S24 | Proofpoint Email DLP Product Page | https://www.proofpoint.com/us/products/information-protection/email-dlp | B | product_guide | Email DLP (current) | 240+ classifiers, smart identifiers, custom dictionaries |
| S25 | CASB DLP Configuration Training Datasheet | https://www.proofpoint.com/sites/default/files/pfpt-us-ds-casb-dlp-configuration-level-1.pdf | B | training_material | CASB (current) | DLP rule workflow, detectors, remediation |
| S26 | Proofpoint Essentials API Docs (Landing) | https://us1.proofpointessentials.com/api/v1/docs/index.php | B | api_reference | Essentials API v1 | REST API, filters, organizations, users, quarantine |
| S27 | Proofpoint Archive -- Managing Retention and Legal Holds | https://help.proofpoint.com/Proofpoint_Essentials/Email_Security/Administrator_Topics/150_emailarchive/Managing_Retention_and_Legal_Holds | A | admin_guide | Essentials Archive (current) | Retention period, legal hold, archive settings |
| S28 | Proofpoint Data Security Innovations Blog (Q1/Q3 2025) | https://www.proofpoint.com/us/blog/information-protection/proofpoint-data-security-innovations-q3-2025 | C | release_notes | Data Security 2025 | GenAI DLP, endpoint prevention, detection rule simulation |

---

## Documentation Coverage Assessment

| Policy Area | Coverage | Best Grade | Notes |
|-------------|----------|------------|-------|
| Email Filtering (Essentials) | HIGH | A [S1] | Full admin guide extracted -- filters, conditions, actions, scope |
| Email Filtering (PPS/PoD) | LOW | B [S2] | Training outline only; detailed admin guide requires auth |
| Spam Policies | HIGH | A [S1] | Threshold, bulk email, stamp-and-forward, DNS checks |
| Virus Policies | MODERATE | A [S1] | AV bypass list documented; virus rule creation from training only [S2] |
| DLP Policies (Essentials) | MODERATE | A [S1] via D [S18] | Smart identifiers referenced; detailed workflow from third-party only |
| DLP Policies (PPS/PoD) | LOW | B [S2] | Training mentions DLP; no detailed admin guide accessible |
| Email Encryption Policies | MODERATE | B [S14] | Policy-based triggers documented; encryption filter setup needs auth [help.proofpoint.com] |
| TAP (URL/Attachment Defense) | MODERATE | C [S21,S22] | KB articles cover group enablement and exemptions; detailed config needs auth |
| ITM/ObserveIT Policies | HIGH | A [S4,S5,S6] | System policy, threat library, rule import/export -- all from official docs |
| Data Security Agent Policies | HIGH | A [S7,S8,S9] | DLP/ITM signal types, if-then logic, realm assignment |
| Detection Rules (Data Security) | HIGH | A [S10] | Rule creation, severity, actions, tags, versioning |
| Prevention Rules (Data Security) | HIGH | A [S11] | Block, prompt, allow, GenAI redaction, file retention |
| CASB Policies | LOW | A [S13] via B [S25] | Overview documented; detailed policy config requires auth |
| Browser/Email Isolation | MODERATE | B [S15] | Data sheet level -- browsing policies, DLP integration, adaptive security |
| Security Awareness Training | HIGH | A [S3] | Full admin guide -- campaign types, assignments, scheduling, reports |
| Archive Retention/Legal Hold | MODERATE | A [S27] | Retention config and legal hold documented; page requires auth for full content |
| PPS Email Firewall Rules | LOW | B [S2] via C [S20] | Training outline + KB article; detailed rule creation needs auth |
| PPS Policy Routes | LOW | B [S2] via C [S16] | Known concept from training + XSOAR integration; no admin guide detail |
| API Policy Management | LOW | B [S26] | API landing page found; full endpoint docs behind auth wall |

---

## Capability: Email Filtering Policies (Proofpoint Essentials)

### Official Documentation

Proofpoint Essentials uses a conditions-and-actions framework for email filtering. Filters can block or allow emails based on senders, recipients, content, attachments, email size, and more. [S1]

#### Screens and Navigation
- **Company Settings > Filters**: Organization-level filter management [S1]
- **Company Settings > Filters > Add New Filter**: Create new filter [S1]
- **Users & Groups > [User] > Filters**: User-level filter management [S1]

#### Configuration Fields -- Filter Creation

| Field | Type | Valid Values | Default | Required | Notes | Source |
|-------|------|-------------|---------|----------|-------|--------|
| Name/Description | Text | Free text (e.g., "Allow List") | None | Yes | Internal identifier | [S1] |
| Direction | Select | Inbound, Outbound | None | Yes | Determines mail flow direction | [S1] |
| Scope | Select | Company, Group, User | None | Yes | Application level | [S1] |
| Priority | Select | Low, Normal, High | Low | No | Processing order; high processes first | [S1] |
| Condition Type | Select | Sender Address, Recipient Address, Email Size (kb), Client IP Country, Email Subject, Email Headers, Email Message Content, Raw Email, Attachment Type, Attachment Name | None | Yes | Multiple conditions supported | [S1] |
| Operator | Select | IS, IS NOT, IS ANY OF, IS NONE OF, CONTAIN(S) ALL OF, CONTAIN(S) ANY OF, CONTAIN(S) NONE OF | None | Yes | Pattern matching logic | [S1] |
| Destination/Action | Select | Allow (skipping spam filter), Allow (but filter for spam), Quarantine | None | Yes | Primary disposition | [S1] |
| Hide Logs | Checkbox | Enabled/Disabled | Disabled | No | Hides log from user view | [S1] |
| Enforce Completely Secure SMTP Delivery | Checkbox | Enabled/Disabled | Disabled | No | Forces TLS with valid cert check | [S1] |
| Enforce only TLS on SMTP Delivery | Checkbox | Enabled/Disabled | Disabled | No | Forces TLS without cert validation | [S1] |

#### Attachment Type Categories
Windows executable components, installers, other executable components, office documents, archives, audio/visual, PGP encrypted files [S1]

#### Workflow Steps
1. Click Company Settings tab [S1]
2. Click Filters tab [S1]
3. Click Add New Filter [S1]
4. Enter name/description [S1]
5. Choose direction (Inbound/Outbound) [S1]
6. Choose scope (Company/Group/User) [S1]
7. Set priority [S1]
8. Select condition type and build rule with operator and values [S1]
9. Select destination action [S1]
10. Configure optional actions (Hide Logs, TLS enforcement) [S1]
11. Click Save Filter [S1]

#### Filter Precedence Rules
- Organization filters have precedence over user filters [S1]
- If sender is on user's approved list AND organization blocked list, message is blocked [S1]
- Filters applied in order created; priority field overrides [S1]

#### Prerequisites
- Organization must be provisioned on Proofpoint Essentials [S1]
- Admin role required for organization-level filters [S1]
- End users can create personal filters via UI or quarantine digest link [S1]

### Knowledge Base Findings
- Filters typically activate within 5-15 minutes; full propagation up to 30 minutes [S17]
- Testing recommended at User scope first, then expand to Group and Company [S17]
- "Stop Processing Additional Filters" option halts rule evaluation chain [S17]

### Community Insights
- Impersonation protection: create filter where From Name Contains executive names AND From Domain is not your organization domain, action Quarantine [S17] -- SINGLE_SOURCE, grade D
- Secondary actions available: recipient notification, admin alerts, custom header insertion, subject line tagging [S17] -- SINGLE_SOURCE, grade D; not corroborated in [S1]

### Gaps
- Exact secondary action configuration fields not documented in grade-A source
- Maximum number of filters per organization not documented
- Filter change audit logging not documented
- Regex/wildcard pattern syntax beyond `*@domain.com` not detailed

---

## Capability: Spam Policy Configuration

### Official Documentation

Spam filtering is enabled by default. Administrators can adjust sensitivity via a sliding threshold control. [S1]

#### Screens and Navigation
- **Company Settings > Spam**: Organization-level spam settings [S1]

#### Configuration Fields

| Field | Type | Valid Values | Default | Required | Notes | Source |
|-------|------|-------------|---------|----------|-------|--------|
| Spam Trigger Level | Slider | Numeric threshold (lower = more aggressive) | System default | No | Sensitivity control | [S1] |
| Quarantine Bulk Email | Checkbox | Enabled/Disabled | Disabled | No | Quarantines bulk/marketing email | [S1] |
| Stamp & Forward | Select | No, Partial (score 9-19), All | No | No | Appends configurable text (default: "***Spam***") to subject | [S1] |
| Easy Spam Reporting | Checkbox | Enabled/Disabled | Disabled | No | Appends disclaimer with report link | [S1] |
| Inbound Sender DNS | Checkbox | Enabled/Disabled | Enabled | No | MX record checks + private IP range rejection | [S1] |
| Update for all users | Checkbox | Enabled/Disabled | Disabled | No | Overwrites per-user settings | [S1] |

#### Prerequisites
- Per-user spam settings override organization defaults unless "Update for all users" is checked [S1]

### Knowledge Base Findings
- PPS/PoD: Spam module includes classifiers, suspected spam handling, safe/blocked lists, false positive/negative reporting [S2]

### Gaps
- Exact numeric range of spam trigger level not documented
- Available spam module classifiers not enumerated in accessible docs
- Suspected spam vs definite spam threshold boundaries not specified

---

## Capability: Virus Policy Configuration

### Official Documentation

Anti-virus protection is enabled by default. Organizations can configure a bypass list for specific senders. [S1]

#### Screens and Navigation
- **Company Settings > Virus**: AV bypass list management [S1]

#### Configuration Fields

| Field | Type | Valid Values | Default | Required | Notes | Source |
|-------|------|-------------|---------|----------|-------|--------|
| AV Bypass Address | Text | user@domain.com or domain.com | None | Yes | Senders exempt from AV scanning | [S1] |

#### Workflow Steps
1. Navigate to Company Settings > Virus [S1]
2. Enter SMTP address or domain in text field [S1]
3. Click Save [S1]

### Knowledge Base Findings
- PPS includes multi-layer virus protection and zero-hour virus detection [S2]
- PPS supports creating virus policies that allow groups to send encrypted files [S2]

### Gaps
- Virus detection engine names/versions not documented
- Zero-hour anti-virus configuration options not documented in accessible sources
- Per-user virus settings not documented

---

## Capability: Data Loss Prevention Policies (Essentials / PPS)

### Official Documentation

DLP uses smart identifiers (pre-built regex patterns) to locate content such as credit card numbers, SSNs, and health information. Policies can combine smart identifiers with custom dictionaries. [S24]

Proofpoint Email DLP includes 240+ fine-tuned classifiers and allows creation of custom dictionaries and custom identifiers. [S24]

#### Detection Methods

| Method | Description | Source |
|--------|------------|--------|
| Smart Identifiers | Pre-built patterns: credit card, SSN, bank account, HIPAA, drivers license, passport | [S18] |
| Dictionaries | Keyword/phrase lists for industry terms | [S18] |
| Regular Expressions | Custom pattern matching | [S18] |
| Document Fingerprinting | Template matching for contracts, forms | [S18] |
| Machine Learning | Behavioral analysis for unusual transfers | [S18] |

**NOTE:** Detection methods list sourced from grade-D [S18]. Smart identifiers and dictionaries confirmed in grade-B [S24]. Document fingerprinting confirmed in [S14]. Machine learning confirmed in [S23].

#### DLP Actions

| Action | Description | Source |
|--------|------------|--------|
| Block | Prevents message delivery | [S18] |
| Quarantine | Holds for admin review | [S18] |
| Encrypt | Auto-encrypts message via policy | [S18] |
| Allow/Monitor | Permits with notification/logging | [S18] |
| Notify Sender | Alerts user their email was flagged | [S18] |
| Notify Admin | Sends compliance team alert | [S18] |

**NOTE:** Action list sourced from grade-D [S18]. Encrypt action confirmed in grade-B [S14].

### Knowledge Base Findings
- Best practice: use dictionary in conjunction with corresponding smart identifier to reduce false positives [S24]
- Adaptive Email DLP uses behavioral AI to detect misdirected emails and human error patterns [S23]
- Deployment timeline: basic 48 hours, full enterprise 3-6 months for policy tuning [S18] -- grade D

### Gaps
- Exact navigation path for DLP policy creation in Essentials admin console behind auth wall
- Custom smart identifier creation workflow not documented in accessible sources
- DLP policy import/export mechanism not documented
- PPS/PoD DLP module configuration entirely behind auth wall

---

## Capability: Email Encryption Policies

### Official Documentation

Proofpoint Encryption is policy-driven, automatically applying encryption based on organizational policies. Encryption uses AES-256 bit with ECDSA digital signatures. [S14]

#### Encryption Trigger Parameters

| Trigger Type | Description | Source |
|-------------|------------|--------|
| Deep content analysis | Detects PHI, NPI, regulated data, document fingerprints | [S14] |
| Message origin/destination | Based on specific partners, senders, attachment types | [S14] |
| TLS fallback | Delivers via TLS; falls back to Proofpoint Encryption if TLS fails | [S14] |
| User-initiated | Subject line keywords like [ENCRYPT] or [SECURE] trigger encryption | [S17] |

#### Encryption Features

| Feature | Description | Source |
|---------|------------|--------|
| Policy-based encryption | Automatic based on organization policies | [S14] |
| Secure Reader | Web-based interface for recipients to read encrypted mail (HTTPS) | [S14] |
| Decrypt Assist | One-step delivery for mobile/laptop/desktop | [S14] |
| Trusted Partner Encryption | Gateway-to-gateway decryption between Proofpoint customers | [S14] |
| Message Expiration | Time-based expiration per policy | [S14] |
| Message Revocation | Per-message, per-recipient revocation | [S14] |
| Encrypt Classified Data | Encrypts documents with Microsoft IAM metadata classification | [S14] |

#### Enterprise Privacy Suite Components (PPS)

| Component | Function | Source |
|-----------|---------|--------|
| Proofpoint Email Firewall | Detects sensitive info in content and subject | [S14] |
| Proofpoint Regulatory Compliance | Smart identifiers for financial, healthcare data | [S14] |
| Proofpoint Digital Asset Security | Document fingerprinting with full/partial matching | [S14] |
| Proofpoint Encryption | Applies encryption based on policy | [S14] |

### Gaps
- Encryption filter creation steps in Essentials behind auth wall (help.proofpoint.com)
- Encryption method selection (Portal Pickup vs PDF vs TLS vs S/MIME) not documented in grade-A/B sources; only in grade-D [S18]
- Key management admin interface not documented
- Branding customization for Secure Reader not documented

---

## Capability: Targeted Attack Protection (TAP) Policies

### Official Documentation

TAP provides URL Defense (rewrites and inspects URLs) and Attachment Defense (sandboxes attachments). URL Defense rewrites URLs to `https://urldefense.com/` format. [S2]

#### Screens and Navigation (PPS)
- TAP in PPS -- Dashboard overview [S2]
- TAP in PPS -- Settings [S2]
- TAP in PPS -- URL Defense [S2]

#### Key Configuration Areas

| Area | Description | Source |
|------|------------|--------|
| URL Defense | Rewrites and inspects URLs in inbound email | [S2] |
| Attachment Defense | Sandboxes suspicious attachments; quarantines malicious ones | [S2] |
| Rewrite Options | Controls URL rewriting behavior | [S2] |
| Per-group enablement | TAP can be enabled for specific user groups | [S22] |
| Sender exemptions | Specific senders can be exempted from TAP alerts | [S21] |
| TAP URL Isolation | Integration with Proofpoint Isolation for VIPs/VAPs | [S15] |

### Knowledge Base Findings
- TAP Attachment Defense can be enabled for specific groups via PPS admin console [S22]
- Senders can be exempted from TAP alerts via community-documented procedure [S21]
- Attachments encrypted at rest, deleted after analysis [S22]

### Gaps
- TAP policy configuration screens and fields entirely behind auth wall
- URL Defense rewrite options not enumerated
- Attachment Defense sandbox configuration not documented
- TAP alert severity levels and thresholds not documented
- TAP integration with DLP policies not detailed

---

## Capability: PPS/PoD Rule Creation and Email Firewall

### Official Documentation

PPS rule creation involves policy routes, conditions, quarantine, and disposition types. The filtering system processes messages through modules in a defined precedence order. [S2]

#### Key Concepts from Training

| Concept | Description | Source |
|---------|------------|--------|
| Policy Routes | Define how messages are routed (e.g., allow_relay, firewallsafe) | [S2, S16] |
| Conditions | Criteria that trigger rule actions | [S2] |
| Quarantine | Message hold area with folder-based organization | [S2] |
| Disposition Types | Actions applied to matched messages | [S2] |
| Dictionaries | Word/phrase lists used in conditions | [S2] |
| Custom Spam Rules | Specialized spam detection rules | [S2] |
| Module Precedence | Order in which filtering modules process messages | [S2] |
| Delivery Precedence | Order in which delivery actions are applied | [S2] |

#### PPS Email Firewall Components

| Component | Description | Source |
|-----------|------------|--------|
| Email Firewall Rules | Connection-level rules for sender management | [S2, S20] |
| Proofpoint Dynamic Reputation (PDR) | Real-time IP reputation scoring | [S2] |
| Recipient Verification (RV) | Validates recipients exist before accepting mail | [S2] |
| SMTP Rate Control | Limits SMTP connection rates | [S2] |

#### PPS API (via XSOAR Integration)

| Command | Action | Source |
|---------|--------|--------|
| proofpoint-pps-smart-search | Trace filtered messages by action, sender, recipient, time | [S16] |
| proofpoint-pps-quarantine-messages-list | Search quarantined messages by folder, sender, recipient | [S16] |
| proofpoint-pps-quarantine-message-release | Release without further scanning | [S16] |
| proofpoint-pps-quarantine-message-resubmit | Reprocess through filtering modules | [S16] |
| proofpoint-pps-quarantine-message-forward | Forward to alternative recipients | [S16] |
| proofpoint-pps-quarantine-message-move | Transfer between quarantine folders (same module type) | [S16] |
| proofpoint-pps-quarantine-message-delete | Delete with optional archive | [S16] |

### Gaps
- Complete list of PPS policy route types not documented in accessible sources
- PPS rule creation UI screens and fields entirely behind auth wall
- Condition types, operators, and valid values for PPS rules not documented
- Quarantine folder types and retention defaults not documented
- Dictionary creation and management workflow not documented for PPS

---

## Capability: ITM/ObserveIT Policies

### Official Documentation

ITM On-Prem (formerly ObserveIT) provides system policy settings controlling recording, monitoring, screen capture, and notifications. The Insider Threat Library contains 300+ rules. [S4, S5]

#### Screens and Navigation
- **Web Console > Configuration**: All configuration tasks [S4]
- **Configuration > Alerts > Alert & Prevent Rules**: Rule management [S6]

#### System Policy Settings

| Setting | Platforms | Default | Description | Source |
|---------|----------|---------|-------------|--------|
| Enable Recording | Win, Mac, Unix | Enabled | Toggle agent recording | [S4] |
| Continue Recording After Lock | Win, Mac, Unix | N/A (when recording disabled) | Maintains API-triggered sessions | [S4] |
| Session Timeout | Win, Mac, Unix | 15 minutes | Inactivity threshold | [S4] |
| Enable Key Logging | Win, Mac | Disabled | Captures keystrokes, paste actions | [S4] |
| Keyboard Frequency | Win, Mac | 1 second | Every keystroke, 0.5s, 1s, 5s, 10s | [S4] |
| Continuous Recording | Win, Mac | OFF | Interval-based capture (CPU intensive) | [S4] |
| Screen Recapturing Mode | Win, Mac | Focused window only | Focused window vs entire screen | [S4] |
| Image Format | Win, Mac, Unix | Grayscale Server Compression (Win/Unix); Color (Mac) | Color, Grayscale Server, Grayscale Client | [S4] |
| Enable Identity Theft Detection | Win, Mac, Unix | N/A | Notifies users about endpoint access | [S4] |
| Enable Recording Notification | Unix only | Disabled | Yellow notification bar | [S4] |
| Enable Live and Lock Messages | Win, Mac | Disabled | Console-to-user communication | [S4] |
| Enable API | Win, Mac | Disabled | Programmatic agent control | [S4] |
| Enable Agent Passive Mode | All | N/A | Receives events alongside apps vs intercepting | [S4] |

#### Rule Types

| Type | Purpose | Source |
|------|---------|--------|
| Alert Rules | Trigger alerts based on detected activities | [S6] |
| Prevention Rules | Block risky activities in real-time | [S6] |
| Policy Rules | Define organizational policies | [S6] |
| System Rules | Pre-built rules from Insider Threat Library | [S6] |

#### Insider Threat Library
- 300+ out-of-the-box detection scenarios [S5]
- Covers Windows, Mac, Unix/Linux [S5]
- Rules organized by security categories [S5]
- Targets: Privileged Users, Everyday Users, Remote Vendors [S5]
- Top-performing rules activated by default for Windows and Mac [S5]
- Updates distributed as ZIP files by Content Manager [S5]
- Built-in policy notifications for user awareness [S5]

#### Rule Import/Export
- Supports alert, prevention, policy, and system rules [S6]
- Import wizard detects conflicts and missing data [S6]
- User Lists exportable/importable as CSV [S6]
- Requires Admin or Config Admin role [S6]
- Access: Configuration > Alerts > Alert & Prevent Rules [S6]

### Gaps
- Specific rule condition syntax and operators not documented
- Rule testing/simulation workflow not documented
- Stealth and Privacy Policy configuration for Windows not detailed
- Alert severity mapping and escalation configuration not documented

---

## Capability: Data Security Agent Policies and Endpoint DLP

### Official Documentation

Agent Policies define what the Proofpoint Agent captures and are assigned to Realms. Two signal types: DLP Only (file events) and ITM (all events including screenshots). [S7]

#### Screens and Navigation
- **Administration app > Endpoint > Agent Policies**: Policy management [S8]
- **Administration > Policies > Rules**: Detection/prevention rules [S10]

#### Agent Policy Structure

| Component | Description | Source |
|-----------|------------|--------|
| General Settings | Foundational policy configuration | [S8] |
| Details (If/Then) | Conditional logic using categories and values | [S9] |
| DLP Only Toggle | Limits to file activity; disabling enables ITM features | [S9] |
| Priority | Determines precedence when multiple policies per Realm | [S8] |
| Default Account Policy | Pre-configured, assigned to all Realms, inheritable | [S7] |

#### If/Then Logic Configuration

| Section | Description | Source |
|---------|------------|--------|
| If (Conditions) | Categories + values with AND/OR operators (e.g., Username = administrator) | [S9] |
| Then (Settings) | Configurable settings activated when conditions met (e.g., File Activity Monitoring) | [S9] |
| Prevention Rules | Must be associated during policy setup | [S9] |

#### Detection Rules

| Field | Description | Source |
|-------|------------|--------|
| Rule Name | Identifier | [S10] |
| Severity | Low, Medium, High, Critical | [S10] |
| Conditions | From library, Threat Library, or custom fields with filters | [S10] |
| Actions | Alert management, notifications (SMS/email/webhook), tags, drop matching | [S10] |
| Rule Sets | Assign to specific Agent Realms; override source defaults | [S10] |
| Order Priority | Higher numbers (up to 1000) trigger first | [S10] |
| Rule Versions | Track modifications, revert to previous versions | [S10] |

#### Prevention Rules

| Action | Description | Source |
|--------|------------|--------|
| Block | Stop data exfiltration | [S11] |
| Prompt | Request user justification | [S11] |
| Allow | Permit specific files while blocking others | [S11] |
| Data Redaction for GenAI | Redact text in GenAI prompt submissions | [S11] |
| File Retention | Retain files in external storage | [S11] |

#### Prevention Scope Examples
- Block users from exfiltrating to cloud sync folders (Google Drive) [S11]
- Block web file uploads (Windows only) [S11]
- Block printing to local computers [S11]

#### Limits
- Default maximum: 100 combined active rules (detection + prevention) [S12]
- Adjustable via Proofpoint support request [S12]

### Gaps
- Content scanning condition syntax not documented
- Realm configuration and assignment workflow not detailed
- Data class and detector configuration not documented
- GenAI redaction rule template details not available

---

## Capability: CASB Policies

### Official Documentation

Proofpoint CASB secures email accounts, applications, and infrastructure against account compromise, malicious files, data loss, and compliance risks. [S13]

#### Five Core Capabilities
1. Threat Protection -- account takeover defense [S13]
2. Access Control -- user behavior analytics [S13]
3. Data Loss Prevention -- DLP across cloud apps and email [S13]
4. Application Visibility -- cloud app governance [S13]
5. Infrastructure Security -- vulnerability assessment [S13]

#### CASB DLP Training (50-minute WBT)
- DLP rule creation workflow [S25]
- Building detectors to find DLP in documents [S25]
- Building rules to detect and remediate DLP violations [S25]

### Gaps
- CASB admin console navigation and screens not documented in accessible sources
- CASB-specific policy types and configuration fields not documented
- CASB DLP classifier/detector configuration not available
- Integration between CASB and Email DLP policies not detailed
- CASB access control policy configuration not documented

---

## Capability: Browser/Email Isolation Policies

### Official Documentation

Proofpoint Isolation renders web pages in a secure cloud container, stripping executable code before delivering safe content to users. Supports browsing policies per user group. [S15]

#### Policy Capabilities

| Feature | Description | Source |
|---------|------------|--------|
| Browsing policies | Per-group access controls (researchers, executives get less restrictive) | [S15] |
| Upload/download restrictions | By URL, URL category, file type, sensitive data, malware | [S15] |
| User input controls | Dynamic limits on form input to prevent credential theft | [S15] |
| TAP integration | Isolates URLs for VIPs/VAPs from TAP dashboard | [S15] |
| DLP integration | Inline real-time DLP for uploads/downloads | [S15] |
| URL Isolation Policy | Import VIP/VAP lists from User Center and TAP | [S15] |
| Redirect Rules | Configurable via Isolation Console > Policies > Redirect Rules | [S15] |

### Gaps
- Isolation admin console screens and navigation paths not documented
- Redirect rule creation workflow not detailed
- URL category list and management not documented
- Policy precedence between isolation and email protection not documented
- User self-registration vs admin-provisioned isolation not detailed

---

## Capability: Security Awareness Training Policies

### Official Documentation

Training administration covers two main areas: Training Assignments and Phishing Campaigns. [S3]

#### Training Assignment Types

| Type | Description | Source |
|------|------------|--------|
| Scheduled | Fixed start and due dates; users added to assignment | [S3] |
| Duration | Ongoing (e.g., new-hire); uses enrollment delay + assignment due within | [S3] |

#### Scheduled Assignment Fields

| Field | Type | Valid Values | Default | Required | Notes | Source |
|-------|------|-------------|---------|----------|-------|--------|
| Name | Text | Unique identifier | None | Yes | Internal only, not visible to users | [S3] |
| Type | Select | Scheduled, Duration | Scheduled | Yes | Determines date behavior | [S3] |
| Start Date | Date | Future date | None | Yes | Notification sent at 12:01 AM ET | [S3] |
| Due Date | Date | After start date | None | Yes | 30-day grace period after due date | [S3] |
| Training Notification | Select | None, Always Active, Default | Default | No | Email notification on assignment | [S3] |
| Completion Notification | Select | None, Always Active, Default | Default | No | Email on completion | [S3] |
| Reminders | Date list | Comma-separated dates | None | No | Only sent to incomplete users | [S3] |
| High Priority | Checkbox | Enabled/Disabled | Disabled | No | Locks other assignments until complete | [S3] |
| Enforce Module Order | Checkbox | Enabled/Disabled | Disabled | No | Requires sequential completion | [S3] |
| Modules | Multi-select | From Available Modules list | None | Yes | Filter by Custom/Licensed/All | [S3] |
| Users | Multi-select | Filter by date range, groups | None | Yes | Checkbox selection | [S3] |

#### Duration Assignment Additional Fields

| Field | Type | Default | Notes | Source |
|-------|------|---------|-------|--------|
| Enrollment Delay | Number (days) | None | Days after adding user before enrollment begins; 0 = 30 min | [S3] |
| Assignment Due Within | Number (days) | None | Days after enrollment that assignment is due | [S3] |

#### Phishing Campaign Types

| Type | Description | Source |
|------|------------|--------|
| Drive-by | Link to simulated malicious website; forwards to Teachable Moment | [S3] |
| Data Entry | Fake website for credential entry; forwards to Teachable Moment. Passwords NOT collected | [S3] |
| Classic Attachment | Simulated malicious DOC or HTML file attachment | [S3] |
| Attachment | Simulated malicious PDF, DOCX, or XLSX attachment | [S3] |
| Follow Up | Campaign targeting users based on performance in previous campaign | [S3] |

#### Phishing Campaign Creation Fields

| Field | Type | Notes | Source |
|-------|------|-------|--------|
| Campaign Title | Text | Unique, not visible to end users | [S3] |
| Email Templates | Multi-select | Filter by Language, Category, Average Failure Rate (AFR) | [S3] |
| Campaign Users | Multi-select | Groups, lists, or from completed campaigns | [S3] |
| Teachable Moment | Select | By category and language; multilingual support | [S3] |
| Schedule | Date/time or Random | Specific delivery or randomized across days/times | [S3] |
| Data Collection Period | Duration | Default 7 days; customizable or indefinite | [S3] |

#### Campaign Lifecycle Operations
- Edit (only in pending state, before start date) [S3]
- Clone [S3]
- Cancel in progress [S3]
- Archive / Unarchive [S3]
- Delete [S3]

### Gaps
- PhishAlarm configuration details behind auth wall
- Custom Teachable Moment creation workflow not documented
- Landing page customization for Data Entry campaigns referenced but not detailed
- Report scheduling and export formats not documented

---

## Capability: Archive Retention and Legal Hold

### Official Documentation

Archive retention defaults to 12 months (1 year) with a maximum of 10 years. Legal hold suspends retention policies indefinitely. [S27]

#### Configuration

| Setting | Location | Description | Source |
|---------|----------|-------------|--------|
| Retention Period | Settings > Retention | Years and Months fields; default 12 months, max 10 years | [S27] |
| Company Legal Hold | Settings > Legal Hold | Slider to enable; retains all messages indefinitely | [S27] |

**NOTE:** Full page content from [S27] is behind authentication wall; information sourced from search result snippets.

### Gaps
- Per-user or per-group retention policies not documented
- Legal hold audit trail details not documented
- Archive search policy configuration not documented
- Compliance officer role and permissions not documented

---

## Cross-References

| Capability A | Capability B | Relationship | Source |
|-------------|-------------|--------------|--------|
| Email Filtering | Spam Policies | Filters process AFTER virus blocking, BEFORE delivery; spam threshold independent | [S1] |
| Email Filtering | Encryption | Outbound filters can trigger encryption via [ENCRYPT] subject keyword | [S17] |
| DLP Policies | Encryption | DLP detection can automatically trigger policy-based encryption | [S14, S18] |
| TAP URL Defense | Isolation | TAP can redirect URLs to isolated browsing session for VIPs/VAPs | [S15] |
| Agent Policies | Detection Rules | Detection rules assigned via Rule Sets to Realms linked to Agent Policies | [S10, S9] |
| Agent Policies | Prevention Rules | Prevention rules must be associated with Agent Policies during setup | [S9] |
| Prevention Rules | Realms | Prevention rule Detectors must be included in Data Classes of assigned Realm | [S11] |
| ITM Rules | Agent Policies | ITM signal type enables full activity capture beyond DLP-only | [S7] |
| CASB DLP | Email DLP | Shared classifiers and consistent policies across email and cloud apps | [S13] |
| Isolation DLP | Enterprise DLP | Inline real-time DLP for upload/download in isolation sessions | [S15] |
| Encryption | PPS Email Firewall | Firewall detects sensitive content; encryption component encrypts | [S14] |

---

## Unresolved Questions

| # | Question | Capability | Why It Matters | Sources Checked |
|---|---------|-----------|----------------|-----------------|
| 1 | What are the complete PPS policy route types and their definitions? | PPS Rule Creation | Policy routes are fundamental to PPS rule architecture | [S2, S16] |
| 2 | What conditions and operators are available in PPS rule creation? | PPS Rule Creation | Required to map admin workflow accurately | [S2] |
| 3 | How are DLP smart identifiers configured in Essentials admin console? | DLP Policies | Navigation path and field names needed | [S1, S18, S24] |
| 4 | What are the CASB-specific policy types and their configuration screens? | CASB Policies | Entire CASB policy authoring workflow unknown | [S13, S25] |
| 5 | How does Isolation admin console organize redirect rules and browsing policies? | Isolation Policies | Screen-level detail missing for workflow mapping | [S15] |
| 6 | What are the complete Proofpoint Essentials API endpoints for filter/policy management? | API | Required for automation workflow mapping | [S26] |
| 7 | What is the precedence order between PPS filtering modules (spam, virus, DLP, firewall)? | PPS Filtering | Critical for understanding policy interaction | [S2] |
| 8 | How does the Proofpoint Admin Portal (admin.proofpoint.com) differ from PPS console for policy management? | All | Two admin consoles may have different policy capabilities | All sources |
| 9 | What are the encryption method selection options (Portal Pickup, PDF, TLS, S/MIME) and their triggers? | Encryption | Referenced in grade-D only; needs grade-A confirmation | [S14, S18] |
| 10 | How are DMARC, DKIM, and SPF policies configured in PPS? | Email Authentication | Authentication policies are part of email protection but not covered | None found |
| 11 | What is the maximum filter/rule count for Essentials? | Email Filtering | Capacity planning for policy authoring | [S1] |
| 12 | How does Unified DLP (PPS 8.22.x) change the Email DLP policy workflow? | DLP Policies | Recent feature may alter documented workflows | Search results only |
| 13 | What role-based access controls exist for policy authoring across products? | All | Admin vs config admin vs readonly not fully mapped | [S6] partial |
| 14 | How do Adaptive Email DLP behavioral AI policies differ from traditional DLP rules? | DLP Policies | New product line with potentially different authoring model | [S23] |

---

## Stale Source Warning

| Source | Age Concern | Impact |
|--------|------------|--------|
| [S1] Essentials Admin Guide | Dated July 2014 -- 12 years old | UI may have changed significantly; filter types and actions may differ from current version. Cross-reference with [S17] (current) partially mitigates. |
| [S3] SAT Admin Guide | Dated April 2020 -- 6 years old | Campaign types and UI may have expanded; new features like AIDA integration not covered. |
| [S14] Encryption Data Sheet | Dated March 2019 | Encryption features may have expanded; GenAI-related encryption policies not covered. |
