# Documentation Corpus: Palo Alto Enterprise DLP -- Authoring Policies
> Researched: 2026-05-21 | Sources: 38 | Version: Enterprise DLP (cloud-delivered, Strata Cloud Manager + Panorama managed)

---

## Source Index

| # | Title | URL | Grade | Covers |
|---|-------|-----|-------|--------|
| S1 | Data Profiles | https://docs.paloaltonetworks.com/enterprise-dlp/administration/configure-enterprise-dlp/create-an-enterprise-dlp-data-profile | A | Data profile creation, match criteria, activation, nested profiles |
| S2 | Create a Data Profile | https://docs.paloaltonetworks.com/enterprise-dlp/administration/configure-enterprise-dlp/create-an-enterprise-dlp-data-profile/create-a-data-profile | A | Step-by-step data profile creation, predefined + custom data patterns, AND/OR logic |
| S3 | Create a Nested Data Profile | https://docs.paloaltonetworks.com/enterprise-dlp/administration/configure-enterprise-dlp/create-an-enterprise-dlp-data-profile/create-a-nested-data-profile | A | Consolidating multiple profiles into a single nested profile |
| S4 | Create a Granular Data Profile | https://docs.paloaltonetworks.com/enterprise-dlp/administration/configure-enterprise-dlp/create-an-enterprise-dlp-data-profile/create-a-granular-data-profile | A | Differentiated inline inspection with per-match-criteria actions |
| S5 | Update a Data Profile | https://docs.paloaltonetworks.com/enterprise-dlp/administration/configure-enterprise-dlp/create-an-enterprise-dlp-data-profile/update-a-data-profile | B | Updating existing profiles, re-attaching to security rules |
| S6 | Configure Enterprise DLP | https://docs.paloaltonetworks.com/content/techdocs/en_US/enterprise-dlp/administration/configure-enterprise-dlp | A | Top-level configuration guide -- data patterns, profiles, rules, EDM, document types |
| S7 | Data Patterns, Document Types, and Data Profiles (Predefined/ML) | https://docs.paloaltonetworks.com/enterprise-dlp/enterprise-dlp-admin/enterprise-dlp-overview/predefined-ml-based-data-patterns | A | Predefined regex + ML-based data patterns, LLM-augmented detection, DNN models |
| S8 | Create a Custom Data Pattern | https://docs.paloaltonetworks.com/enterprise-dlp/administration/configure-enterprise-dlp/create-an-enterprise-dlp-data-pattern/create-a-custom-data-pattern | A | Custom regex patterns, basic vs weighted, score thresholds |
| S9 | Configure Regular Expressions | https://docs.paloaltonetworks.com/enterprise-dlp/administration/configure-enterprise-dlp/create-an-enterprise-dlp-data-pattern/configure-regular-expressions | A | Regex syntax guide, RE2 engine, expression builder |
| S10 | Add Custom Match Criteria to a Predefined Data Pattern | https://docs.paloaltonetworks.com/enterprise-dlp/administration/configure-enterprise-dlp/create-an-enterprise-dlp-data-pattern/add-custom-match-criteria-to-a-predefined-data-pattern | B | Extending predefined patterns with custom secondary criteria |
| S11 | Create a File Property Data Pattern | https://docs.paloaltonetworks.com/enterprise-dlp/enterprise-dlp-admin/configure-enterprise-dlp/create-an-enterprise-dlp-data-pattern/create-a-data-pattern-on-the-dlp-app/create-a-file-property-data-pattern-on-the-dlp-app | B | File metadata matching -- author, title, keywords |
| S12 | Exact Data Matching (EDM) | https://docs.paloaltonetworks.com/enterprise-dlp/administration/configure-enterprise-dlp/configure-exact-data-matching | A | EDM overview, CLI app, dataset creation, upload, indexing |
| S13 | Enable Exact Data Matching (EDM) | https://docs.paloaltonetworks.com/enterprise-dlp/activation-and-onboarding/enable-edm | A | EDM activation prerequisites, tenant-level enable |
| S14 | Set Up the EDM CLI App | https://docs.paloaltonetworks.com/enterprise-dlp/administration/configure-enterprise-dlp/configure-exact-data-matching/set-up-the-exact-data-matching-cli-application | A | EDM CLI install, Windows + Linux, hashing and encryption |
| S15 | Create and Upload EDM Data (Interactive Mode) | https://docs.paloaltonetworks.com/enterprise-dlp/administration/configure-enterprise-dlp/configure-exact-data-matching/create-and-upload-an-encrypted-edm-data-set-to-the-dlp-cloud-service-interactive-mode | A | Interactive CSV upload, SHA256 + AES-256 encryption |
| S16 | Create and Upload EDM Data (Config File) | https://docs.paloaltonetworks.com/enterprise-dlp/administration/configure-enterprise-dlp/configure-exact-data-matching/upload-an-encrypted-edm-data-set-to-the-dlp-cloud-service-using-a-configuration-file/create-and-upload-an-encrypted-edm-data-set-using-a-configuration-file | B | Batch upload via JSON config file |
| S17 | About Custom Document Types | https://docs.paloaltonetworks.com/enterprise-dlp/administration/configure-enterprise-dlp/custom-document-types-for-enterprise-dlp/about-custom-document-types | A | Indexed Document Matching, Trainable Classifiers, positive/negative training sets |
| S18 | Custom Document Types for Enterprise DLP | https://docs.paloaltonetworks.com/enterprise-dlp/administration/configure-enterprise-dlp/custom-document-types-for-enterprise-dlp | A | Document type upload, .zip requirements, ML model training |
| S19 | Test a Custom Document Type | https://docs.paloaltonetworks.com/enterprise-dlp/administration/configure-enterprise-dlp/custom-document-types-for-enterprise-dlp/test-a-custom-document-type | B | Testing uploaded document types against sample files |
| S20 | Security Profile: Data Filtering | https://docs.paloaltonetworks.com/network-security/security-policy/administration/security-profiles/security-profile-data-filtering | A | Data Filtering Profile on NGFW, attaching data profiles to security rules |
| S21 | Objects > Security Profiles > Data Filtering | https://docs.paloaltonetworks.com/ngfw/help/11-1/objects/objects-security-profiles-data-filtering | A | NGFW field-level reference for Data Filtering profile |
| S22 | Modify a DLP Rule on Strata Cloud Manager | https://docs.paloaltonetworks.com/enterprise-dlp/administration/configure-enterprise-dlp/modify-a-dlp-rule-on-prisma-access-cloud-managed | A | DLP rule configuration on SCM -- traffic, file types, action, severity |
| S23 | Edit the Enterprise DLP Data Filtering Settings | https://docs.paloaltonetworks.com/enterprise-dlp/getting-started/edit-the-enterprise-dlp-data-filtering-settings | B | Enabling/disabling Enterprise DLP inline inspection |
| S24 | Recommendations for Security Policy Rules | https://docs.paloaltonetworks.com/enterprise-dlp/administration/configure-enterprise-dlp/recommendations-for-security-rules | A | Best practices for security rule ordering, profile group attachment |
| S25 | Create a Security Policy Rule for ChatGPT | https://docs.paloaltonetworks.com/enterprise-dlp/administration/configure-enterprise-dlp/enterprise-dlp-and-ai-apps/create-a-security-policy-rule-for-chatgpt | B | AI application DLP policy, ChatGPT-specific configuration |
| S26 | Create an Endpoint DLP Policy Rule | https://docs.paloaltonetworks.com/enterprise-dlp/administration/configure-enterprise-dlp/endpoint-dlp/create-an-endpoint-dlp-policy-rule | A | Cortex XDR-based endpoint DLP, classification on device |
| S27 | Enable Existing Data Patterns and Filtering Profiles | https://docs.paloaltonetworks.com/enterprise-dlp/administration/configure-enterprise-dlp/enable-existing-data-patterns-and-filtering-profiles | B | Activating predefined patterns from the DLP app |
| S28 | Managing Enterprise DLP Configuration Changes | https://docs.paloaltonetworks.com/enterprise-dlp/getting-started/managing-enterprise-dlp-configuration-changes | B | Change management, push workflow, configuration staging |
| S29 | Reduce False Positive Detections | https://docs.paloaltonetworks.com/enterprise-dlp/administration/configure-enterprise-dlp/reduce-false-positive-detections | A | Weighted regex, confidence tuning, proximity, secondary criteria |
| S30 | Configuration: Enterprise DLP (Strata Cloud Manager) | https://docs.paloaltonetworks.com/strata-cloud-manager/getting-started/configuration-scm/manage-configuration-enterprise-dlp | A | SCM-specific DLP management, data profiles, DLP rules, Profile Groups |
| S31 | Create a Data Profile on Panorama | https://docs.paloaltonetworks.com/enterprise-dlp/administration/configure-enterprise-dlp/create-an-enterprise-dlp-data-profile/create-a-data-profile/create-a-data-profile-panorama | A | Panorama-managed data profile creation |
| S32 | Enterprise DLP Incident Management | https://docs.paloaltonetworks.com/content/techdocs/en_US/enterprise-dlp/administration/monitor-enterprise-dlp/enterprise-dlp-incident-management | A | Incident dashboard, case management, manual + automated response |
| S33 | Incident Case Management | https://docs.paloaltonetworks.com/enterprise-dlp/administration/monitor-enterprise-dlp/enterprise-dlp-incident-management/incident-case-management | B | Priority levels P1-P5, incident lifecycle, bulk operations |
| S34 | View an Enterprise DLP Incident | https://docs.paloaltonetworks.com/enterprise-dlp/administration/monitor-enterprise-dlp/view-dlp-log-details | B | Log detail view, data pattern match details, evidence |
| S35 | Report a False Positive Detection | https://docs.paloaltonetworks.com/enterprise-dlp/administration/monitor-enterprise-dlp/enterprise-dlp-incident-management/report-a-false-positive-detection | B | False positive feedback loop for ML model improvement |
| S36 | Data Loss Prevention APIs | https://pan.dev/dlp/api/ | A | REST API reference -- data profiles, data patterns, reports, scanning |
| S37 | Prisma SASE API Get Started | https://pan.dev/sase/docs/getstarted/ | A | OAuth2 auth, TSG scoping, API base URLs |
| S38 | Transforming Data Security with AI-Powered Classification | https://www.paloaltonetworks.com/blog/sase/transforming-data-security-with-ai-powered-classification/ | B | LLM-powered detection, 5th-gen DNN models, 10x fewer false positives |

---

## Key Documentation Structure

### Management Surfaces

Enterprise DLP can be managed through three different surfaces, each with slightly different workflows:

| Surface | URL Pattern | Manages | Data Profile Path |
|---------|------------|---------|------------------|
| **Strata Cloud Manager (SCM)** | `https://stratacloud.paloaltonetworks.com` | Prisma Access, Cloud NGFW | Configuration > Security Services > Data Loss Prevention |
| **Panorama** | `https://<panorama-ip>` | NGFW (PAN-OS) | Objects > Security Profiles > Data Filtering |
| **Enterprise DLP App** | `https://dlp.paloaltonetworks.com` (via Hub) | Centralized DLP config | DLP app > Data Profiles / Data Patterns |

All three surfaces share the same cloud-delivered Enterprise DLP engine. Data profiles and patterns created in the DLP app are available across SCM, Panorama, and Cloud NGFW.

### Hierarchy: Patterns to Enforcement

```
Level 1: Data Patterns (predefined regex, predefined ML, custom regex, custom weighted, file property)
    |
Level 2: Data Profiles (collection of data patterns + match criteria + occurrence/confidence thresholds)
    |
Level 3: Data Filtering Profile (on NGFW) or DLP Rule (on SCM/Prisma Access)
    |
Level 4: Security Policy Rule (attaches the filtering profile + action: alert/block)
    |
Level 5: Enforcement Point (NGFW, Prisma Access, SaaS Security, Endpoint DLP via Cortex XDR)
```

### Detection Methods Taxonomy

| Method | Type | How It Works | Accuracy | Config Complexity |
|--------|------|-------------|----------|-------------------|
| Predefined Regex | Pattern | 500+ built-in regex patterns for SSN, CCN, IBAN, etc. | Moderate (prone to FP) | LOW -- select and enable |
| Predefined ML-based | AI/ML | LLM + context-aware ML models augment regex patterns | High (10x fewer FP) | LOW -- select confidence (High/Low) |
| Custom Regex (Basic) | Pattern | User-defined regex, single expression per line | Varies by regex quality | MEDIUM -- write and test regex |
| Custom Regex (Weighted) | Pattern | User-defined regex with per-expression scoring (-9999 to 9999) | Higher than basic | HIGH -- tune weights and thresholds |
| Exact Data Matching (EDM) | Fingerprint | SHA256 hash of structured CSV data, AES-256 encrypted upload | Very High | HIGH -- CLI app, data pipeline |
| Indexed Document Matching (IDM) | Fingerprint | Document fingerprinting via trainable classifier upload | High | HIGH -- 20+ documents, positive/negative sets |
| Trainable Classifiers | AI/ML | Supervised ML on uploaded document sets, continuously trained | High (improves over time) | HIGH -- 50+ recommended documents per type |
| File Property | Metadata | Match on file author, title, keywords, or other metadata | Moderate | LOW -- simple field matching |
| Custom Document Types | AI/ML | Upload custom doc types for classification training | High | HIGH -- minimum 20 docs, 500 chars each |

---

## Documentation Gaps Identified

| # | Gap | Impact | Workaround |
|---|-----|--------|------------|
| 1 | No published API schema (OpenAPI/Swagger) for DLP REST API | HIGH -- developers must discover endpoints by trial | Use pan.dev interactive API explorer |
| 2 | ML-based pattern confidence thresholds ("High" vs "Low") not precisely defined | MEDIUM -- no numeric score mappings | Test with sample data at both levels and calibrate |
| 3 | Weighted regex score threshold interaction with occurrence conditions underdocumented | MEDIUM -- behavior when both weighted score AND occurrence count are set | Test empirically; weight threshold overrides occurrence in most cases |
| 4 | Endpoint DLP (Cortex XDR) policy rule field reference incomplete | MEDIUM -- new feature, docs still evolving | Cross-reference Cortex XDR 5.x documentation |
| 5 | Nested data profile evaluation order (AND vs OR across nested profiles) not explicit | LOW -- behavior is OR by default but not stated | Assume OR; test with overlapping profiles |
| 6 | Custom Document Type .zip validation errors not well documented | LOW -- error messages are cryptic | Ensure minimum 20 files, all text, 500+ chars each |
| 7 | Data Filtering Profile vs DLP Rule terminology inconsistency across surfaces | MEDIUM -- same concept, different names | Panorama = "Data Filtering Profile"; SCM = "DLP Rule" |

---

## Version / Platform Notes

| Platform | Version | DLP Feature Support | Notes |
|----------|---------|-------------------|-------|
| PAN-OS NGFW (Panorama) | 10.x / 11.x | Data Filtering Profile with E-DLP cloud inspection | Requires Enterprise DLP license + security rule attachment |
| Prisma Access | Cloud-managed | Full DLP Rule support via SCM | Native integration, no additional appliance |
| Cloud NGFW for AWS | Current | E-DLP integration available | See S-doc for AWS-specific config |
| Cortex XDR 5.0 | 5.x | Endpoint DLP module | Classification on-device, offline capable, real-time user prompts |
| SaaS Security (CASB) | Current | API-based and inline DLP scanning | Scans SaaS app content against data profiles |
| Prisma Access Browser | Current | Inline DLP in browser | Embedded Enterprise DLP for browser-based data flows |

---

## Cross-Reference Matrix: Source to Topic

| Topic | Primary Sources | Secondary Sources |
|-------|----------------|-------------------|
| Data Patterns (predefined) | S7, S27 | S38 |
| Data Patterns (custom regex) | S8, S9 | S10, S29 |
| Data Patterns (ML-based) | S7, S38 | S29 |
| Data Profiles | S1, S2 | S5, S30, S31 |
| Nested Data Profiles | S3 | S1 |
| Granular Data Profiles | S4 | S1 |
| EDM | S12, S13, S14, S15, S16 | -- |
| Custom Document Types / IDM | S17, S18, S19 | -- |
| Data Filtering Profile (NGFW) | S20, S21 | S24 |
| DLP Rule (SCM) | S22, S30 | S25 |
| Security Policy Rules | S24, S25 | S20 |
| Endpoint DLP | S26 | -- |
| Incident Management | S32, S33, S34, S35 | -- |
| API | S36, S37 | -- |
| False Positive Reduction | S29 | S10, S38 |
| AI/LLM Classification | S38, S7 | S29 |
