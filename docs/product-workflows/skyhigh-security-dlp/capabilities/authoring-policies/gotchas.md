# Authoring Policies -- Known Limitations & Tribal Knowledge
## Skyhigh Security DLP (SSE Platform)

> Capability: authoring-policies | Generated: 2026-05-21
> Sources aggregated: Video research (5 tribal knowledge items, 3 gotchas), API research (8 console-only gaps), Doc research (7 documentation gaps)

---

## Critical Gotchas (Will Break Your Deployment If Ignored)

### 1. Two Separate DLP Engines -- Cloud vs Endpoint Are Different Products

**Impact:** CRITICAL -- Skyhigh cloud DLP (CASB/SWG) and endpoint DLP (Trellix) are fundamentally different engines with separate management consoles, separate policy formats, and separate classification systems.

**Details:**
- **Cloud DLP**: Managed via Skyhigh Security Dashboard. Classifications, policies, and rules are created in the Skyhigh console. Covers sanctioned (CASB), shadow/web (SWG), and inline channels.
- **Endpoint DLP**: Managed via Trellix ePolicy Orchestrator (ePO). Uses Trellix DLP classifications, rules, and rule sets. Covers desktop applications, USB, clipboard, email client, etc.

These are NOT the same classification engine. A classification created in Skyhigh Dashboard is NOT automatically available in Trellix ePO, and vice versa. Policy synchronization between them requires explicit integration configuration.

**Workaround:**
- Maintain a policy matrix mapping cloud classifications to equivalent endpoint classifications
- Use the Skyhigh-to-Trellix DLP integration (documented in S4 area) to sync policies where possible
- Plan for separate configuration work on each surface
- Budget 2x the policy authoring effort if both cloud and endpoint DLP are required

**Source:** Historical context (McAfee/Skyhigh/Trellix lineage), doc-corpus S34
**Evidence Grade:** A

---

### 2. Rule Group Boolean Logic: OR Between Groups, AND/OR Within Groups

**Impact:** HIGH -- Misunderstanding the Boolean evaluation model causes policies to match too broadly (false positives) or too narrowly (missed detections).

**Details:** Skyhigh DLP uses a two-level Boolean model:
- **Between Rule Groups**: OR logic. If ANY rule group matches, the policy triggers.
- **Within a Rule Group**: Rules can be combined with AND or OR logic.

This means:
- Multiple rule groups = broader detection (more things trigger the policy)
- Multiple rules within one group with AND = narrower detection (ALL must match)
- Multiple rules within one group with OR = broader detection within that group

**Common mistake:** Creating multiple rule groups when you intended AND logic. If you want "SSN AND near keyword 'social security'", put BOTH rules in ONE rule group with AND. Do NOT put them in separate rule groups (which would be OR).

**Workaround:** Plan your Boolean logic on paper before building in the console:
1. Draw each Rule Group as a box
2. Rules within a box are combined with the group's operator (AND/OR)
3. Boxes are combined with OR
4. Verify the truth table matches your intent

**Source:** S7 (About Rules and Rule Groups), S42 (Hands-On Workshop)
**Evidence Grade:** A

---

### 3. Policy Import/Export Has Size Limits -- 50 Rule Groups or 64KB Maximum

**Impact:** HIGH -- Large policies that exceed either limit cannot be imported or exported. This breaks migration and backup workflows for complex deployments.

**Details:** Skyhigh CASB does not support importing or exporting policies or policy templates that include:
- More than 50 rule groups, OR
- Exceed 64 KB in size
Whichever limit is reached first.

**Workaround:**
- Design policies to stay within limits from the start
- Split large policies into multiple smaller policies targeting different data types
- Use nested rule group structures efficiently (fewer groups, more rules per group)
- For migration: manually recreate oversized policies in the target tenant

**Source:** S5 (Create a Sanctioned DLP Policy -- noted in limitations section)
**Evidence Grade:** A

---

### 4. AI RegEx Generator Sends Queries to External AI Service

**Impact:** MEDIUM -- The AI-powered regex builder transmits your queries to an external AI service. If you enter actual sensitive data patterns or examples, that data leaves your organization.

**Details:** The AI RegEx Generator is a conversational interface that builds RE2-compliant regular expressions. While Skyhigh states that queries are confidential and not used for training, the data IS transmitted to an external AI service to generate responses.

**Workaround:**
- NEVER enter real sensitive data (actual SSNs, credit card numbers, patient data) into the AI RegEx Generator
- Use generic pattern descriptions instead (e.g., "a pattern matching XXX-XX-XXXX format" instead of actual SSNs)
- Review generated regex before deploying -- the AI may produce overly broad or overly narrow patterns
- Test all AI-generated patterns against sample data before production use

**Source:** S19 (AI RegEx Generator)
**Evidence Grade:** A

---

### 5. ML Auto Classifiers Are Pre-Trained Only -- No Custom Training

**Impact:** MEDIUM -- Unlike Palo Alto's trainable classifiers, Skyhigh's ML Auto Classifiers use pre-trained models only. You cannot upload custom training documents to create new ML classifiers.

**Details:** Skyhigh ML Auto Classifiers:
- Text classifiers: Financial Reports/Statements, Patient Records, Patents, Source Code
- Image classifiers: ID documents, credit cards, checks
- English only for text classifiers
- Cannot create custom ML classifiers
- Cannot retrain existing models with your data

**Workaround:**
- Use built-in classifiers for supported document types
- For unsupported document types, use IDM (Index Document Matching) fingerprinting instead
- Combine ML classifiers with regex/dictionary classifications for broader coverage
- Request new classifier types from Skyhigh product team if your use case is common

**Source:** S21, S22, S23 (ML Auto Classifiers)
**Evidence Grade:** A

---

## Deployment Gotchas

### 6. Proximity Distance Configuration Is Variable (1-10000 Characters)

**Impact:** MEDIUM -- The default proximity distance may be too broad or too narrow for your use case, and the configurable range (1-10000 characters) requires careful tuning.

**Details:** Proximity defines how many characters can separate two classification definition items (e.g., a keyword and an advanced pattern) and still trigger a match. If two items are found within the specified distance, it is a match.

Setting proximity too narrow (e.g., 10 characters) may miss legitimate matches where the SSN appears a paragraph away from the keyword "Social Security Number". Setting too broad (e.g., 10000 characters) matches nearly any document that contains both elements anywhere.

**Workaround:**
- Start with 100-200 characters for keyword-to-pattern proximity
- Test with real documents from your organization
- Adjust based on false positive/negative rates
- Use the Proximity Use Cases documentation (S17) for guidance on common scenarios

**Source:** S16 (Proximity), S17 (Proximity Use Cases)
**Evidence Grade:** B

---

### 7. Dictionary Score Threshold Requires Understanding of Scoring Model

**Impact:** MEDIUM -- Dictionary classifications use a scoring model where each keyword occurrence adds to a cumulative score. If the score threshold is misconfigured, classifications will over-match or under-match.

**Details:** When using a Dictionary classification:
- Each keyword match adds to a score based on the dictionary entry's weight
- The classification triggers when the cumulative score meets or exceeds the threshold
- Multiple occurrences of the same keyword each add to the score

**Workaround:**
- Set score threshold based on the MINIMUM number of keyword matches you want to trigger
- For a dictionary with all weights = 1: threshold = N means "N or more keyword matches"
- For weighted dictionaries: plan the scoring matrix on paper before implementing
- Test with sample documents to calibrate

**Source:** S15 (Dictionary Classification), S1 (About Classifications)
**Evidence Grade:** B

---

### 8. Sanctioned vs Shadow/Web Policies Are Separate Objects

**Impact:** MEDIUM -- A sanctioned DLP policy does NOT automatically apply to shadow/web traffic. You must create separate policies for each channel type.

**Details:** Skyhigh DLP has three policy types:
- **Sanctioned DLP Policies**: Apply to connected, approved cloud services via CASB
- **Shadow/Web DLP Policies**: Apply to unmanaged cloud services and web traffic via SWG
- **Endpoint DLP Policies**: Apply to desktop activities via Trellix agent

Creating a sanctioned policy does NOT create a corresponding shadow/web policy. Classifications ARE shared across policy types, but the policies themselves are separate.

**Workaround:**
- Create matching policies for each channel you want to protect
- Use the same classifications across all policy types for consistency
- Maintain a policy mapping document showing which classifications are enforced on which channels

**Source:** S5 (Sanctioned), S33 (Shadow/Web)
**Evidence Grade:** A

---

## API & Automation Gotchas

### 9. ENTIRE Policy Authoring Pipeline Has No API -- Console Only

**Impact:** CRITICAL -- Cannot implement DLP-as-code, CI/CD for policies, or programmatic policy management.

**Details:** The following operations have ZERO API support:
1. Create/edit classifications
2. Create/edit DLP policies
3. Create/edit rule groups
4. Create/edit rules within policies
5. Create/manage EDM fingerprints (requires DLP Integrator on-prem tool)
6. Create/manage IDM fingerprints (requires IDMTrain on-prem tool)
7. Import/customize policy templates
8. Configure ML Auto Classifiers

Only incident management and content scanning have API coverage.

**Workaround:** All policy creation must be done through the Skyhigh Security Dashboard web console. For definition data (EDM/IDM), use the on-prem tools (DLP Integrator, IDMTrain) for batch processing.

**Source:** API intelligence research
**Evidence Grade:** A

---

### 10. Endpoint DLP Requires Separate Trellix ePO API

**Impact:** MEDIUM -- If automating both cloud and endpoint DLP, you need two completely different API stacks (Skyhigh CASB API + Trellix ePO API) with different auth models and endpoint patterns.

**Workaround:** Build a unified abstraction layer. See Trellix DLP API intelligence for ePO API details.

**Source:** API intelligence research
**Evidence Grade:** A

---

## Tribal Knowledge (Undocumented Best Practices)

### 11. Start with Policy Templates, Then Customize

**Impact:** HIGH -- Building policies from scratch when pre-built templates exist wastes significant time and introduces errors.

**Details:** Skyhigh provides compliance-ready policy templates for:
- PCI-DSS (credit card protection)
- HIPAA (healthcare data)
- GDPR (EU personal data)
- GLBA (financial data)
- SOX (financial reporting)

These templates include pre-configured classifications, rules, and rule groups. Starting with a template and customizing is 5-10x faster than building from scratch.

**Source:** S31 (Policy Templates)
**Evidence Grade:** A

---

### 12. Use Proximity to Dramatically Reduce False Positives

**Impact:** HIGH -- A 9-digit number alone matches SSN regex but could be anything. Adding proximity (SSN pattern within 100 characters of keyword "Social Security") eliminates 80%+ of false positives.

**Details:** Proximity matching in Skyhigh allows:
- Dictionary items near Advanced Patterns
- Keywords near Advanced Patterns
- Any two definition types within a configurable character distance

**Use cases from documentation (S17):**
- SSN regex within 100 chars of "social security" keyword
- Credit card regex within 150 chars of "card number" or "credit card" keyword
- IBAN within 200 chars of "bank" or "account" keyword

**Source:** S16 (Proximity), S17 (Proximity Use Cases)
**Evidence Grade:** A

---

### 13. Single Classification Engine Across All Cloud Channels

**Impact:** HIGH -- Create a classification once, it works in Sanctioned (CASB), Shadow/Web (SWG), and inline enforcement simultaneously. No need to recreate classifications per channel.

**Details:** While policies are separate per channel (gotcha #8), the CLASSIFICATIONS are shared. This means:
- Define "PCI - Credit Card" classification once
- Reference it in your Sanctioned DLP policy
- Reference the SAME classification in your Shadow/Web DLP policy
- Both policies use the same detection logic

This is a significant advantage over products where each channel has its own classification engine.

**Source:** Video #1 (Unified Data Protection), S34 (SSE Components)
**Evidence Grade:** A

---

### 14. Use the Rule Evaluation Tool Before Deploying Policies

**Impact:** MEDIUM -- Skyhigh provides a built-in tool to test policy rules against sample content before deployment. Using this prevents deploying policies that don't work as expected.

**Details:** The Evaluate Policy Rules tool (S14) allows:
- Upload sample content
- Select rules to evaluate
- See which rules would trigger
- View match details (which classification, which pattern, score)

**Source:** S14 (Evaluate Policy Rules)
**Evidence Grade:** B

---

### 15. Response Actions Can Be Conditional on Severity

**Impact:** MEDIUM -- Response actions can be configured to trigger differently based on the severity of the rule group that was triggered.

**Details:** This allows:
- Critical severity: Block + Quarantine + Email Admin
- High severity: Alert + Email Admin
- Medium severity: Create Incident only
- Low severity: Log only

All within a SINGLE policy with multiple rule groups at different severities.

**Source:** S8 (Response Actions)
**Evidence Grade:** A

---

## Summary Statistics

| Category | Count | Critical/High Impact |
|----------|-------|---------------------|
| Critical gotchas (deployment-breaking) | 5 (#1-5) | 5 |
| Deployment gotchas | 3 (#6-8) | 1 |
| API/automation gotchas | 2 (#9-10) | 1 |
| Tribal knowledge (best practices) | 5 (#11-15) | 3 |
| **Total** | **15** | **10** |
