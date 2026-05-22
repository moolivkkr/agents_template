# Documentation Corpus: Skyhigh Security DLP -- Authoring Policies
> Researched: 2026-05-21 | Sources: 42 | Version: Skyhigh Security SSE Platform (cloud-native)

---

## Source Index

| # | Title | URL | Grade | Covers |
|---|-------|-----|-------|--------|
| S1 | About Classifications | https://success.skyhighsecurity.com/Skyhigh_Data_Loss_Prevention/Classifications/01_About_Classifications | A | Classification overview, definition types (Dictionary, Regex, EDM, IDM, Keyword), proximity, location |
| S2 | Create a Classification | https://success.skyhighsecurity.com/Skyhigh_Data_Loss_Prevention/Classifications/02_Create_a_Classification | A | Step-by-step classification creation, definition types, match criteria |
| S3 | Data Classifications | https://success.skyhighsecurity.com/Skyhigh_Data_Loss_Prevention/01_Data_Loss_Prevention_Concepts/Data_Classifications | A | Conceptual overview, built-in vs custom classifications |
| S4 | About Data Loss Prevention (DLP) | https://success.skyhighsecurity.com/Skyhigh_Data_Loss_Prevention/01_Data_Loss_Prevention_Concepts/01_Protect_Data | A | DLP concepts, policy flow, channels (sanctioned, shadow, web, endpoint) |
| S5 | Create a Sanctioned DLP Policy | https://success.skyhighsecurity.com/Skyhigh_Data_Loss_Prevention/Sanctioned_DLP_Policies_and_Rules/Sanctioned_DLP_Policies/Create_a_Sanctioned_DLP_Policy | A | Full policy creation walkthrough, wizard steps |
| S6 | About Sanctioned DLP Policies | https://success.skyhighsecurity.com/Skyhigh_Data_Loss_Prevention/Sanctioned_DLP_Policies_and_Rules/Sanctioned_DLP_Policies/About_Sanctioned_DLP_Policies | A | Policy concepts, scope, structure |
| S7 | About Sanctioned DLP Policy Rules and Rule Groups | https://success.skyhighsecurity.com/Skyhigh_Data_Loss_Prevention/Sanctioned_DLP_Policies_and_Rules/Sanctioned_DLP_Policies_Rules_and_Rule_Groups/About_Sanctioned_DLP_Policy_Rules_and_Rule_Groups | A | Rule types, rule groups, Boolean logic (AND/OR), evaluation order |
| S8 | Sanctioned DLP Policy Response Actions | https://success.skyhighsecurity.com/Skyhigh_Data_Loss_Prevention/Sanctioned_DLP_Policies_and_Rules/Sanctioned_DLP_Policies/Sanctioned_DLP_Policy_Response_Actions | A | Response actions per channel, conditional actions by severity |
| S9 | Sanctioned DLP Policy Exceptions | https://success.skyhighsecurity.com/Skyhigh_Data_Loss_Prevention/Sanctioned_DLP_Policies_and_Rules/Sanctioned_DLP_Policies/Sanctioned_DLP_Policy_Exceptions | B | Exception rule groups, whitelisting specific conditions |
| S10 | Classification Label Rules | https://success.skyhighsecurity.com/Skyhigh_Data_Loss_Prevention/Sanctioned_DLP_Policies_and_Rules/Sanctioned_DLP_Policies_Rules_and_Rule_Groups/Classification_Rules | A | Classification-based rules, threshold, severity assignment |
| S11 | Keyword Rules | https://success.skyhighsecurity.com/Skyhigh_Data_Loss_Prevention/Sanctioned_DLP_Policies_and_Rules/Sanctioned_DLP_Policies_Rules_and_Rule_Groups/Keyword_Rules | B | Keyword matching in policy rules |
| S12 | User Risk Rules | https://success.skyhighsecurity.com/Skyhigh_Data_Loss_Prevention/Sanctioned_DLP_Policies_and_Rules/Sanctioned_DLP_Policies_Rules_and_Rule_Groups/User_Risk_Rules | B | Risk-based rules using UEBA scores |
| S13 | Structured Data Fingerprint Rules | https://success.skyhighsecurity.com/Skyhigh_Data_Loss_Prevention/Sanctioned_DLP_Policies_and_Rules/Sanctioned_DLP_Policies_Rules_and_Rule_Groups/Structured_Data_Fingerprint_Rules | A | EDM-based rules in sanctioned policies |
| S14 | Evaluate Policy Rules | https://success.skyhighsecurity.com/Skyhigh_Data_Loss_Prevention/Sanctioned_DLP_Policies_and_Rules/Sanctioned_DLP_Policies_Rules_and_Rule_Groups/Evaluate_Policy_Rules | B | Rule evaluation tool, testing before deployment |
| S15 | Create a Classification using Dictionary | https://success.skyhighsecurity.com/Skyhigh_Data_Loss_Prevention/Classifications/Create_a_Classification_using_Dictionary | A | Dictionary definition type, score-based matching |
| S16 | Create a Classification using Proximity | https://success.skyhighsecurity.com/Skyhigh_Data_Loss_Prevention/Classifications/Create_a_Classification_using_Proximity | A | Proximity matching between definition types, distance configuration |
| S17 | Proximity Use Cases | https://success.skyhighsecurity.com/Skyhigh_Data_Loss_Prevention/Classifications/Create_a_Classification_using_Proximity/Proximity_Use_Cases | B | SSN near keyword "social security", CCN near "card number" |
| S18 | Create Advanced Patterns | https://success.skyhighsecurity.com/Skyhigh_Data_Loss_Prevention/Classifications/Create_Custom_Advanced_Patterns | A | Custom regex patterns, Google RE2, validators (Luhn, BIN, checksum) |
| S19 | AI RegEx Generator for Custom Advanced Patterns | https://success.skyhighsecurity.com/Skyhigh_Data_Loss_Prevention/Classifications/Create_Custom_Advanced_Patterns/AI_RegEx_Generator_for_Custom_Advanced_Patterns | A | AI-powered regex builder, conversational interface, RE2-compliant output |
| S20 | Add BIN Validator | https://success.skyhighsecurity.com/Skyhigh_Data_Loss_Prevention/Classifications/Create_Custom_Advanced_Patterns/Add_BIN_Validator | B | Bank Identification Number validation for credit card patterns |
| S21 | About ML-driven Auto Classifiers | https://success.skyhighsecurity.com/Skyhigh_Data_Loss_Prevention/02_Advance_DLP_Capabilities/AI_Powered_DLP_Capabilities/AI-ML_Auto_Classifiers | A | ML auto classifiers, text + image classifiers, pre-trained models |
| S22 | Create a Classification using ML Auto Classifier | https://success.skyhighsecurity.com/Skyhigh_Data_Loss_Prevention/Classifications/Create_a_Classification_using_ML_Auto_Classifier | A | Configuring ML auto classifiers in classifications |
| S23 | ML Auto Classifiers (list) | https://success.skyhighsecurity.com/Skyhigh_Data_Loss_Prevention/Classifications/Create_a_Classification_using_ML_Auto_Classifier/AI-ML_Auto_Classifiers | B | Full list of available pre-trained classifiers |
| S24 | About Exact Data Match (EDM) Fingerprints | https://success.skyhighsecurity.com/Skyhigh_Data_Loss_Prevention/Exact_Data_Match_(EDM)/01_About_Exact_Data_Match_(EDM)_Fingerprints | A | EDM overview, structured data fingerprinting |
| S25 | Create an EDM (Enhanced) Fingerprint | https://success.skyhighsecurity.com/Skyhigh_Data_Loss_Prevention/Exact_Data_Match_(EDM)/01_Create_an_Exact_Data_Match_(EDM)_Fingerprint | A | EDM creation steps, CSV/TSV source files |
| S26 | About Enhanced Index Document Matching (IDM) Fingerprints | https://success.skyhighsecurity.com/Skyhigh_Data_Loss_Prevention/Unified_Index_Document_Matching_(IDM)/About_Enhanced_Index_Document_Matching_(IDM)_Fingerprints | A | Unstructured document fingerprinting |
| S27 | Prepare the IDM (Enhanced) Fingerprint File | https://success.skyhighsecurity.com/Skyhigh_Data_Loss_Prevention/Unified_Index_Document_Matching_(IDM)/Prepare_the_IDM_(Enhanced)_Fingerprint_File | A | IDM file preparation, DLP Integrator, IDMTrain tool |
| S28 | IDM (Enhanced) Fingerprint Match Criteria | https://success.skyhighsecurity.com/Skyhigh_Data_Loss_Prevention/Unified_Index_Document_Matching_(IDM)/IDM_(Enhanced)_Fingerprint_Match_Criteria | B | Match percentage, partial vs full document match |
| S29 | Create Unstructured Match Condition (IDM) Classification | https://success.skyhighsecurity.com/Skyhigh_Data_Loss_Prevention/Classifications/Create_Unstructured_Match_Condition_(IDM_)_Classification | A | IDM-based classification, match rate configuration |
| S30 | DLP File Classifications in Skyhigh | https://success.skyhighsecurity.com/Skyhigh_Data_Loss_Prevention/Skyhigh_CASB_DLP_Integrations/DLP_File_Classifications_in_Skyhigh | B | How file classifications work in CASB context |
| S31 | Policy Templates for Compliance and DLP | https://success.skyhighsecurity.com/Skyhigh_Data_Loss_Prevention/Policy_Templates/Policy_Templates_for_Compliance_and_DLP | A | Pre-built policy templates (GDPR, HIPAA, PCI, GLBA, SOX) |
| S32 | Create a Cloud DLP policy using the Policy Wizard | https://success.skyhighsecurity.com/Skyhigh_Data_Loss_Prevention/01_Data_Loss_Prevention_Concepts/Create_a_DLP_policy_using_the_Policy_Wizard | A | Step-by-step wizard walkthrough |
| S33 | Create a Shadow/Web DLP Policy | https://success.skyhighsecurity.com/Skyhigh_Data_Loss_Prevention/Shadow%2F%2FWeb_DLP_Policies/Create_a_Shadow%2F%2FWeb_DLP_Policy | B | Shadow IT and web traffic DLP policies |
| S34 | How the Skyhigh SSE Components Work Together | https://success.skyhighsecurity.com/Start_Here_with_Skyhigh_Security/Skyhigh_Security_Service_Edge/How_the_Skyhigh_Security_Service_Edge_Components_Work_Together | A | SSE architecture: SWG + CASB + ZTNA + DLP unified |
| S35 | Skyhigh Security SSE Packaging | https://success.skyhighsecurity.com/Start_Here_with_Skyhigh_Security/Skyhigh_Security_Service_Edge/Skyhigh_Security_SSE_Packaging | B | License tiers, DLP feature availability per tier |
| S36 | Quick Start to Advanced DLP | https://success.skyhighsecurity.com/Skyhigh_Data_Loss_Prevention/02_Advance_DLP_Capabilities/Getting_Started_with_Advanced_DLP/Quick_Start_to_Advanced_DLP | A | Advanced DLP activation, EDM + IDM + ML auto classifiers |
| S37 | Enhanced Security and Efficiency using AI and ML | https://success.skyhighsecurity.com/Skyhigh_AI/Leverage_AI_and_ML_Capabilities_in_the_Skyhigh_SSE_Platform/01_Enhance_Security_and_Data_Protection_Using_AI_and_ML | B | AI/ML features overview across SSE platform |
| S38 | About Usage of AI in Skyhigh DLP | https://success.skyhighsecurity.com/Skyhigh_and_AI/Usage_of_AI_in_Skyhigh_DLP/About_Usage_of_AI_in_Skyhigh_DLP | B | AI integration points in DLP |
| S39 | About Policy Incidents | https://success.skyhighsecurity.com/Skyhigh_Data_Loss_Prevention/Sanctioned_DLP_Policies_and_Rules/Sanctioned_DLP_Policies/Policy_Incidents_Page | B | Incident page, status, severity, resolution |
| S40 | DLP Policy Incident Statuses | https://success.skyhighsecurity.com/Skyhigh_Data_Loss_Prevention/Sanctioned_DLP_Policies_and_Rules/Sanctioned_DLP_Policies/DLP_Policy_Incident_Statuses | B | Incident lifecycle statuses |
| S41 | Enable Incident Management | https://success.skyhighsecurity.com/Skyhigh_Data_Loss_Prevention/Policy_Settings/Incident_Management/Enable_Incident_Management | B | Enabling incident management features |
| S42 | Skyhigh Security SSE Hands-On Workshop | https://learn.skyhighlabs.net/600_dlp_workshop/050_skyhighclassifications/30_createpolicies/index.html | A | Lab-style walkthrough of classifications and policies |

---

## Key Documentation Structure

### Policy Hierarchy

```
Level 1: Classifications (what to detect)
    Dictionary | Advanced Pattern (Regex) | Keyword | EDM | IDM | ML Auto Classifier
    Document Properties | File Name Set | File Sizes | True File Type
    |
Level 2: Sanctioned DLP Policies (enforcement containers)
    |
    Level 2a: Rule Groups (Boolean containers -- OR between groups)
        |
        Level 2b: Rules (AND/OR within groups)
            Classification Rules | Keyword Rules | User Risk Rules
            Structured Fingerprint Rules | Unstructured Fingerprint Rules
            |
    Level 2c: Exceptions (whitelist conditions)
    Level 2d: Response Actions (what happens on match)
    |
Level 3: Channels (where enforcement applies)
    Sanctioned (API-based, inline) | Shadow/Web (SWG) | Endpoint
```

### Classification Definition Types

| Type | How It Works | Configuration Complexity | Use Case |
|------|-------------|------------------------|----------|
| **Dictionary** | Collection of keywords/phrases with scored matching | LOW | Medical terms, profanity, financial keywords |
| **Advanced Pattern** | Google RE2 regex with optional validators (Luhn, BIN, checksum) | MEDIUM | SSN, credit cards, custom identifiers |
| **Keyword** | Simple string matching | LOW | Classification labels, project names |
| **EDM (Exact Data Match)** | Structured data fingerprint from CSV, hashed and indexed | HIGH | Customer databases, employee records |
| **IDM (Index Document Matching)** | Unstructured document fingerprinting | HIGH | Contracts, patents, proprietary documents |
| **ML Auto Classifier** | Pre-trained ML models for text and image classification | LOW | Financial reports, patient records, source code, IDs |
| **Document Properties** | File metadata matching (author, keywords, tags) | LOW | Author-based detection, tag-based classification |
| **File Name Set** | Filename pattern matching | LOW | Files named "confidential*", specific extensions |
| **File Sizes** | File size threshold matching | LOW | Large data exports |
| **True File Type** | File format detection (regardless of extension) | LOW | Block .exe renamed to .txt |

### Policy Channel Types

| Channel | Manages | DLP Enforcement Mode |
|---------|---------|---------------------|
| **Sanctioned** | Known, approved cloud services (O365, Box, Salesforce) | API-based scan + inline (Lightning Link) |
| **Shadow/Web** | Unmanaged cloud services, web traffic via SWG | Inline proxy-based scan |
| **Endpoint** | Desktop applications, file operations | Agent-based (Trellix DLP Endpoint integration) |

---

## Documentation Gaps Identified

| # | Gap | Impact | Workaround |
|---|-----|--------|------------|
| 1 | No public REST API documentation for DLP policy CRUD operations | HIGH -- cannot programmatically manage classifications or policies | Use Trellix ePO API for endpoint DLP; CASB API for sanctioned only |
| 2 | ML Auto Classifier confidence thresholds not published | MEDIUM -- no numeric scoring details | Test with sample files to calibrate |
| 3 | Rule evaluation order within a rule group (top-to-bottom or score-based?) | MEDIUM | Test with overlapping rules; appears to be all-match within group |
| 4 | IDM match percentage defaults and tuning guidance sparse | LOW | Start with default, adjust based on false positive rate |
| 5 | AI RegEx Generator data handling and privacy policy not fully documented | MEDIUM -- queries sent to external AI service | Avoid entering real sensitive data; use patterns only |
| 6 | Endpoint DLP (Trellix integration) policy sync mechanism underdocumented | MEDIUM -- how Skyhigh cloud policies sync to Trellix DLP endpoint | Refer to Trellix DLP documentation for endpoint specifics |
| 7 | Policy import/export size limits (50 rule groups or 64KB) poorly visible | LOW -- hits only large policies | Design policies within limits from the start |

---

## Cross-Reference Matrix: Source to Topic

| Topic | Primary Sources | Secondary Sources |
|-------|----------------|-------------------|
| Classifications (overview) | S1, S2, S3 | S30 |
| Dictionary classifications | S15 | S1 |
| Advanced Pattern (regex) | S18, S19, S20 | S1 |
| Proximity matching | S16, S17 | S1 |
| ML Auto Classifiers | S21, S22, S23 | S37, S38 |
| EDM fingerprints | S24, S25 | S13 |
| IDM fingerprints | S26, S27, S28, S29 | -- |
| Sanctioned DLP Policies | S5, S6 | S32 |
| Rule Groups and Rules | S7, S10, S11, S12, S13 | S14 |
| Response Actions | S8 | S5 |
| Exceptions | S9 | -- |
| Policy Templates | S31 | S32 |
| Shadow/Web DLP Policies | S33 | -- |
| SSE Architecture | S34, S35 | -- |
| Incidents | S39, S40, S41 | -- |
| AI/ML Features | S37, S38 | S21 |
| Hands-On Workshop | S42 | -- |
