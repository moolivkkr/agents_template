# Source Reference: Proofpoint — Authoring Policies

> Total sources: 28 | A: 14 | B: 7 | C: 5 | D: 4 | E: 0 (no pure-inferred sources in corpus)
> Plus: 22 video sources (Grade B: 5, Grade C: 17) from video-intelligence.md
> Agents contributing: doc_researcher, video_researcher, capability_flow_mapper, workflow_synthesizer
> Generated: 2026-05-21

---

## Grade A — Official Documentation

| # | Title | URL | Type | Version | Capabilities Covered | Used By |
|---|-------|-----|------|---------|---------------------|---------|
| S1 | Proofpoint Essentials Administrator Guide | https://d3xh1dlqxy2hb.cloudfront.net/pdf/proofpoint/Proofpoint-Essentials-Administrator-Guide-7-16-14.pdf | Admin Guide | Essentials (July 2014) — **STALE** | Email Filtering, Spam, Virus, Quarantine, Safe/Blocked Sender Lists, Archive (supplemental) | doc_researcher, capability_flow_mapper, workflow_synthesizer |
| S3 | Proofpoint Essentials Security Awareness Admin Guide | https://www.pax8nebula.com/m/290b594b2d79ab17/original/Proofpoint-Essentials-Security-Awareness-Training-Admin-Guide.pdf | Admin Guide | SAT (April 2020) — **STALE** | SAT Training Assignments, Phishing Campaigns, Campaign Types, Reporting | doc_researcher, capability_flow_mapper, workflow_synthesizer |
| S4 | ITM On-Prem Configuration Guide — System Policy Settings | https://prod.docs.oit.proofpoint.com/configuration_guide/system_policy_settings.htm | Admin Guide | ITM 7.18.0 | ITM System Policy, Recording Controls, Activity Monitoring, API toggle | doc_researcher, capability_flow_mapper, workflow_synthesizer |
| S5 | ITM On-Prem — Insider Threat Library Overview | https://prod.docs.oit.proofpoint.com/insider_threat_library/itl_overview.htm | Product Guide | ITM 7.18.0 | ITM Library Rules, Detection Categories, Library Updates | doc_researcher, capability_flow_mapper, workflow_synthesizer |
| S6 | ITM On-Prem — Exporting and Importing Rules | https://prod.docs.oit.proofpoint.com/configuration_guide/exporting_and_importing_rules.htm | Admin Guide | ITM 7.18.0 | ITM Rule Import/Export, Rule Types, Lifecycle | doc_researcher, capability_flow_mapper, workflow_synthesizer |
| S7 | Proofpoint Data Security — Agent Policies Overview | https://docs.public.analyze.proofpoint.com/admin/agent_policies_overview.htm | Product Guide | Data Security (current) | Endpoint DLP Agent Policies, Signal Types, Default Account Policy, Realm Assignment | doc_researcher, capability_flow_mapper, workflow_synthesizer |
| S8 | Proofpoint Data Security — Setting Up Agent Policies | https://docs.public.analyze.proofpoint.com/admin/agent_policies_setting_up.htm | Admin Guide | Data Security (current) | Agent Policy Creation Workflow, Priority Management | doc_researcher, capability_flow_mapper, workflow_synthesizer |
| S9 | Proofpoint Data Security — Agent Policy Details | https://docs.public.analyze.proofpoint.com/admin/agent_policies_details.htm | Admin Guide | Data Security (current) | If/Then Logic, Conditions, DLP Toggle, Prevention Rules Assignment | doc_researcher, capability_flow_mapper, workflow_synthesizer |
| S10 | Proofpoint Data Security — Detection Rules | https://docs.public.analyze.proofpoint.com/rules/rules_detection.htm | Admin Guide | Data Security (current) | Detection Rule Creation, Severity, Rule Sets, Actions, Tags, Versioning | doc_researcher, capability_flow_mapper, workflow_synthesizer |
| S11 | Proofpoint Data Security — Prevention Rules | https://docs.public.analyze.proofpoint.com/rules/prevention_rules_overview.htm | Admin Guide | Data Security (current) | Prevention Rules, Block/Prompt/Allow, GenAI Redaction, Web Upload (Windows-only) | doc_researcher, capability_flow_mapper, workflow_synthesizer |
| S12 | Proofpoint Data Security — ITM/Endpoint DLP Rules Overview | https://docs.public.analyze.proofpoint.com/rules/rules_overview.htm | Product Guide | Data Security (current) | 100-rule tenant limit, Rule Types Overview | doc_researcher, capability_flow_mapper, workflow_synthesizer |
| S13 | Proofpoint CASB Overview | https://docs.public.analyze.proofpoint.com/pcasb/casb_overview.htm | Product Guide | Data Security (current) | CASB Threat Protection, Access Control, DLP, App Visibility, Infrastructure Assessment, Shared Classifiers | doc_researcher, capability_flow_mapper, workflow_synthesizer |
| S27 | Proofpoint Archive — Managing Retention and Legal Holds | https://help.proofpoint.com/Proofpoint_Essentials/Email_Security/Administrator_Topics/150_emailarchive/Managing_Retention_and_Legal_Holds | Admin Guide | Essentials Archive (current) | Archive Retention Period, Legal Hold Configuration | doc_researcher, capability_flow_mapper, workflow_synthesizer |

---

## Grade B — Training Materials and Vendor Documents

| # | Title | URL | Type | Version | Capabilities Covered | Used By |
|---|-------|-----|------|---------|---------------------|---------|
| S2 | Enterprise Protection for the Administrator (Training Datasheet) | https://www.proofpoint.com/sites/default/files/PPS-Protect-WBT-VILT_0.pdf | Training Material | PPS (current) | PPS Architecture, Email Firewall, Policy Routes, Spam Module, Virus Module, TAP, Quarantine, PDR, Rate Control | doc_researcher, capability_flow_mapper, workflow_synthesizer |
| S14 | Proofpoint Encryption Data Sheet | https://www.proofpoint.com/sites/default/files/pfpt-us-ds-encryption.pdf | Product Guide | Encryption (March 2019) — **STALE** | Policy-based Encryption, AES-256, Key Management, TLS Fallback, Secure Reader | doc_researcher, capability_flow_mapper, workflow_synthesizer |
| S15 | Proofpoint Isolation Data Sheet | https://www.proofpoint.com/sites/default/files/pfpt-us-ds-browser-isolation.pdf | Product Guide | Isolation (Aug 2023) | URL Isolation, Browser Isolation, DLP Integration, Browsing Policies, VAP Import | doc_researcher, capability_flow_mapper, workflow_synthesizer |
| S23 | Proofpoint Adaptive Email DLP Product Page | https://www.proofpoint.com/us/products/adaptive-email-dlp | Product Guide | Adaptive DLP (current) | Adaptive Email DLP, Behavioral AI, Pre-send Warnings | doc_researcher, capability_flow_mapper, workflow_synthesizer |
| S24 | Proofpoint Email DLP Product Page | https://www.proofpoint.com/us/products/information-protection/email-dlp | Product Guide | Email DLP (current) | 240+ Classifiers, Smart Identifiers, Custom Dictionaries | doc_researcher, capability_flow_mapper, workflow_synthesizer |
| S25 | CASB DLP Configuration Training Datasheet | https://www.proofpoint.com/sites/default/files/pfpt-us-ds-casb-dlp-configuration-level-1.pdf | Training Material | CASB (current) | CASB DLP Rule Workflow, Detectors, Remediation | doc_researcher, capability_flow_mapper |
| S26 | Proofpoint Essentials API Docs (Landing) | https://us1.proofpointessentials.com/api/v1/docs/index.php | API Reference | Essentials API v1 | REST API for Filters, Organizations, Users, Quarantine | doc_researcher, capability_flow_mapper, workflow_synthesizer |

---

## Grade C — Demo Materials, KB Articles, and Integration References

| # | Title | URL | Type | Date | Capabilities Covered | Used By |
|---|-------|-----|------|------|---------------------|---------|
| S16 | Proofpoint Protection Server v2 XSOAR Integration | https://xsoar.pan.dev/docs/reference/integrations/proofpoint-protection-server-v2 | Integration Guide | PPS 8.16.2 / 8.14.2 | PPS Quarantine Management API (list/release/resubmit/forward/move/delete), Policy Routes, Smart Search | doc_researcher, capability_flow_mapper, workflow_synthesizer |
| S20 | Proofpoint Community — Email Firewall Rule (PPS/PoD) | https://proofpoint.my.site.com/community/s/article/VIDEO-How-to-enable-or-modify-Email-Firewall-Rule-in-Proofpoint-Protection-Server | KB Article | PPS/PoD (current) | PPS Email Firewall Rules — Enable/Modify | doc_researcher, capability_flow_mapper |
| S21 | Proofpoint Community — TAP Sender Exemption | https://proofpoint.my.site.com/community/s/article/TAP-How-to-exempt-a-sender-from-TAP-alerts | KB Article | TAP (current) | TAP Alert Exemptions, Exemption vs Safe-Sender separation | doc_researcher, capability_flow_mapper, workflow_synthesizer |
| S22 | Proofpoint Community — Enabling TAP for User Groups | https://proofpoint.my.site.com/community/s/article/Enabling-TAP-Attachment-Defense-and-or-URL-Defense-for-a-specific-group-of-users | KB Article | TAP (current) | TAP Per-Group Enablement, Group Prerequisites | doc_researcher, capability_flow_mapper, workflow_synthesizer |
| S28 | Proofpoint Data Security Innovations Blog (Q1/Q3 2025) | https://www.proofpoint.com/us/blog/information-protection/proofpoint-data-security-innovations-q3-2025 | Release Notes | Data Security 2025 | GenAI DLP, Endpoint Prevention Expansion, Detection Rule Simulation | doc_researcher, capability_flow_mapper, workflow_synthesizer |

---

## Grade D — Community Sources and Third-Party Guides

| # | Title | URL | Type | Date | Capabilities Covered | Used By |
|---|-------|-----|------|------|---------------------|---------|
| S17 | How to Configure Email Filtering Policies in Proofpoint (InventiveHQ) | https://inventivehq.com/knowledge-base/proofpoint/how-to-configure-email-filtering | Third-Party Guide | Essentials (current) | Email Filter Creation, Conditions, Actions, Scope, Priority | doc_researcher, capability_flow_mapper, workflow_synthesizer |
| S18 | How to Configure DLP Rules in Proofpoint (InventiveHQ) | https://inventivehq.com/knowledge-base/proofpoint/how-to-configure-dlp-rules | Third-Party Guide | Essentials (current) | DLP Policy Creation, Smart Identifiers, Dictionaries, Regex, Encryption Integration | doc_researcher, capability_flow_mapper, workflow_synthesizer |
| S19 | How to Manage the Quarantine Console in Proofpoint (InventiveHQ) | https://inventivehq.com/knowledge-base/proofpoint/how-to-manage-quarantine | Third-Party Guide | Essentials (current) | Quarantine Types, Release Procedures, Digest Configuration, Retention | doc_researcher, capability_flow_mapper, workflow_synthesizer |
| S_COMM | Proofpoint Community — Best Practices for Tuning Spam Module Rules | https://proofpoint.my.site.com (spam tuning article) | Community Article | PPS (current) | PPS Spam Module Incremental Tuning, Anti-Spoof Rule Default State | doc_researcher, capability_flow_mapper, workflow_synthesizer |

---

## Video Sources (from video-intelligence.md)

| # | Title | Grade | Date | Capabilities Covered |
|---|-------|-------|------|---------------------|
| V2 | How to Enable or Modify Email Firewall Rule (PPS) | B | 2018 | PPS Email Firewall, Route Condition, Propagation Delay |
| V3 | PPS Policy Route Configuration | C | ~2017 | PPS Policy Routes, System Menu Navigation |
| V5 | How to Enable URL Defense (TAP) | B | 2018 | TAP URL Defense Enable (manual step), Default-Disabled state |
| V6 | TAP Attachment Defense Configuration | B | 2018 | TAP Attachment Defense Setup |
| V7 | How to Enable Proofpoint Email Encryption Service | B | 2018 | Email Encryption Filter, Outbound+Company Scope Constraint |
| V9 | PPS Email Firewall Rule Ordering | C | ~2017 | PPS Rule Execution Order = Visual Position |
| V15 | TAP Configuration Walkthrough | C | ~2019 | TAP General Setup |
| V16 | Proofpoint Data Security / ITM Rule Creation Demo | C | ~2021 | Endpoint DLP Detection Rules, Priority, Severity, OS Type |
| V17 | TAP Browser Isolation Product Demo | C | 2019-08-15 | TAP VAP List Manual Import to Isolation, URL Isolation |
| V18 | Proofpoint Isolation Demo (Standalone) | C | 2022-12-29 | Browser Isolation End-User Experience, Isolation = Render Not Block |
| V20 | Proofpoint Essentials — Configure Filter Policy | B | 2023 | Email Filtering, Scope Order, Stop Processing, Propagation Delay, Staged Deployment |
| V21 | Proofpoint Essentials — Manage Spam Settings | B | 2023 | Spam Settings UI Separation, Propagation Delay |
| V22 | Live Demo: Adaptive Email DLP Webinar | B | 2025-01 | Adaptive Email DLP Learning Period, Pre-Send Warning Banners |
| V1-V14, V19, V23+ | Additional Proofpoint training and demo videos | B/C | Various | Various sub-capabilities (full list in video-intelligence.md) |

---

## Stale Sources

| # | Title | Listed Version | Current Version | Risk | Notes |
|---|-------|---------------|----------------|------|-------|
| S1 | Proofpoint Essentials Administrator Guide | July 2014 | Current (2023+ UI refresh) | HIGH | Navigation path changed: "Company Settings > Filters" → "Security Settings > Email > Filter Policies". Field names and some options may differ. Use [V20] 2023 video for current navigation. Use [S1] only for conceptual reference (scope precedence, filter logic). |
| S3 | Proofpoint Essentials SAT Admin Guide | April 2020 | Current (2025+ with AIDA) | HIGH | 6 years old. AIDA integration, expanded template library, new reporting dashboards, and potentially new campaign types not reflected. All SAT claims graded A [S3] are authoritative as of April 2020 only. |
| S14 | Proofpoint Encryption Data Sheet | March 2019 | Current | MEDIUM | 7 years old. Post-2019 features (GenAI encryption integration, Unified DLP interaction in PPS 8.22.x) not covered. Treat as confirmed floor for features, not a complete ceiling. |
| S16 | Proofpoint PPS XSOAR Integration | PPS 8.16.2 / 8.14.2 | PPS 8.22.x (current) | MEDIUM | API command names and quarantine operation behavior may have changed in PPS 8.22.x, particularly given the Unified DLP introduction. Verify API commands against current XSOAR integration docs before production use. |

---

## Unresolved Questions (from doc-corpus.md)

| # | Question | Capability | Impact | Status |
|---|---------|-----------|--------|--------|
| Q1 | What is the full list of Condition Types in PPS Email Firewall? | PPS Rules | HIGH | OPEN — admin guide behind auth |
| Q2 | What is the full list of Disposition Types in PPS Email Firewall? | PPS Rules | HIGH | OPEN — admin guide behind auth |
| Q3 | Smart identifier navigation path and configuration fields | Email DLP | HIGH | OPEN — admin guide behind auth |
| Q4 | TAP URL Defense and Attachment Defense field names, defaults, and options | TAP | HIGH | OPEN — admin guide behind auth |
| Q5 | CASB DLP connector OAuth scope requirements per cloud app | CASB | HIGH | OPEN — admin guide behind auth |
| Q6 | CASB policy configuration fields, navigation, and default remediation action | CASB | HIGH | OPEN — admin guide behind auth |
| Q7 | Isolation Console admin navigation paths beyond Policies > Redirect Rules | Isolation | HIGH | OPEN — admin guide behind auth |
| Q8 | Whether per-custodian legal hold is supported in Essentials Archive | Archive | HIGH | OPEN — may require Enterprise Archive |
| Q9 | Archive capture scope (MTA-level vs delivered-messages-only) | Archive | HIGH | OPEN — not documented in accessible sources |
| Q10 | ITM Windows stealth vs. notification policy configuration fields | ITM | MEDIUM | OPEN — admin guide behind auth |
| Q11 | Maximum email filter count per Proofpoint Essentials organization | Email Filtering | MEDIUM | OPEN — no documented limit found |
| Q12 | PPS 8.22.x Unified DLP impact on Email Firewall DLP and Encryption workflows | Email DLP / Encryption | MEDIUM | OPEN — no accessible release notes |
| Q13 | Essentials API v1 full field parity with UI filter operations | Email Filtering | MEDIUM | OPEN — API docs behind auth wall |
| Q14 | Agent policy push interval for Endpoint DLP agents | Endpoint DLP | MEDIUM | OPEN — no documented check-in interval |

---

## Deduplication Notes

- S20 (Proofpoint Community — Email Firewall) and V2 (How to Enable/Modify Email Firewall Rule) cover the same topic from different formats. Both retained: S20 is a KB article reference, V2 is the video demonstration. Different formats, same capability.
- S21 and the TAP exemption section in email-dlp/gotchas.md both reference the same Proofpoint Community article. Deduplicated to S21 as the primary reference.
- PPS spam tuning community article referenced in both spam/gotchas.md (as G7) and pps-rules/gotchas.md (as G11). Single source — listed as S_COMM in this document.
