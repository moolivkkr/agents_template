# Authoring Policies -- Known Limitations & Tribal Knowledge
## Palo Alto Enterprise DLP (Cloud-Delivered)

> Capability: authoring-policies | Generated: 2026-05-21
> Sources aggregated: Video research (6 tribal knowledge items, 4 gotchas), API research (5 console-only gaps), Doc research (7 documentation gaps)

---

## Critical Gotchas (Will Break Your Deployment If Ignored)

### 1. Enterprise DLP Is Cloud-Delivered -- No Internet = No DLP Verdicts

**Impact:** CRITICAL -- All inline DLP inspection requires the enforcement point (NGFW, Prisma Access) to reach the Palo Alto Networks DLP cloud service. If internet connectivity is interrupted, DLP verdicts cannot be rendered.

**Details:** Unlike traditional DLP products that perform local inspection, Palo Alto Enterprise DLP sends content to a cloud-based inspection engine. The NGFW or Prisma Access node forwards matching traffic to the DLP cloud, which renders a verdict (match/no-match) and returns it. If the cloud is unreachable:
- **Fail-open (default):** Traffic passes without DLP inspection. Sensitive data can exfiltrate.
- **Fail-close (configurable):** Traffic is blocked entirely. Business operations may halt.

**Workaround:**
- Ensure redundant internet connectivity for enforcement points
- Configure the fail-open/fail-close behavior based on your risk tolerance
- Monitor cloud connectivity health in SCM
- For air-gapped environments, consider Cortex XDR Endpoint DLP (on-device classification)

**Source:** Video #1 (Enterprise DLP), doc-corpus architecture sections
**Evidence Grade:** A

---

### 2. Data Profiles Are Inactive Until Attached to a Security Policy Rule

**Impact:** CRITICAL -- Creating a data profile does nothing by itself. The profile must be attached to a DLP Rule/Data Filtering Profile, which must be attached to a Security Policy Rule, which must be pushed to an enforcement point.

**Details:** This is a four-level activation chain:
```
Data Profile (created) -> DLP Rule (references profile) -> Security Rule (references DLP rule via Profile Group) -> Push (deployed to enforcement point)
```
If ANY link in this chain is missing, no DLP inspection occurs. The most common failure is creating a data profile and DLP rule but forgetting to attach the DLP rule to a security policy rule. The DLP rule exists but has no traffic to inspect.

**Workaround:** Always verify the complete chain:
1. Data Profile exists and has match criteria
2. DLP Rule exists and references the data profile
3. Security Policy Rule exists and references the DLP rule (via Profile Group or inline profile)
4. Configuration is pushed to the enforcement point
5. Traffic matching the security rule is flowing through the enforcement point

**Source:** S1 (Data Profiles), S24 (Recommendations for Security Rules)
**Evidence Grade:** A

---

### 3. ML-Based Data Patterns Have Severe Configuration Constraints

**Impact:** HIGH -- Admins expecting granular control over ML-based patterns will find they are almost entirely non-configurable.

**Details:** Predefined ML-based data patterns:
- Support ONLY the "Any" occurrence condition -- cannot set "trigger on 5+ matches"
- Offer ONLY High or Low confidence levels -- no numeric score, no custom threshold
- Cannot be duplicated or cloned
- Cannot have custom match criteria added to them (unlike predefined regex patterns)
- The internal model scoring is opaque -- "High" and "Low" are not precisely defined

**Workaround:**
- Use ML-based patterns for broad coverage with high accuracy
- Use regex-based patterns if you need occurrence thresholds or custom criteria
- Combine both in a data profile: ML for accuracy, regex for threshold control
- Test with sample data at both High and Low confidence to calibrate

**Source:** S7 (Predefined ML-based patterns), Video #2 (AI-Powered DLP)
**Evidence Grade:** A

---

### 4. Panorama "Data Filtering Profile" and SCM "DLP Rule" Are the Same Concept with Different Names

**Impact:** HIGH -- Admins managing both Panorama and Strata Cloud Manager will encounter different terminology for the same enforcement object, causing confusion.

**Details:**
| Concept | Panorama Term | SCM Term |
|---------|-------------|---------|
| The enforcement rule that references a data profile | **Data Filtering Profile** | **DLP Rule** |
| The security profile container | **Security Profile Group** | **Profile Group** |
| Where to attach it | **Security Policy Rule > Profile Group** | **Security Policy > Profile Setting** |

The underlying DLP engine is identical. The data profiles and data patterns are shared. Only the management UI terminology differs.

**Workaround:** Create a terminology mapping document for your team. When discussing DLP configuration, always clarify which management surface you are referencing. The doc-corpus (S20 vs S22) documents both surfaces.

**Source:** S20 (Security Profile: Data Filtering), S22 (Modify a DLP Rule on SCM), Video #6 (Data Filtering)
**Evidence Grade:** A

---

### 5. Weighted Regex Score Threshold Interaction with Occurrence Conditions Is Underdocumented

**Impact:** MEDIUM -- When a custom data pattern uses weighted scoring AND the data profile sets an occurrence condition, the interaction between these two threshold mechanisms is not clearly defined.

**Details:** Custom data patterns can be configured as "Weighted" with per-expression scores from -9999 to 9999 and an overall score threshold. Independently, the data profile can set an occurrence count (e.g., "5 or more matches"). The documentation does not clearly state:
- Does the occurrence count apply to individual regex matches or to the aggregate weighted score?
- Can a single document trigger on score alone even with 0 occurrences above the individual expression threshold?
- What happens when the weighted score exceeds the threshold but the occurrence count is not met?

**Workaround:** Test empirically with sample documents. Based on observed behavior:
- Weighted score threshold appears to override occurrence count when both are set
- Occurrence count applies to the number of distinct match locations, not the aggregate score
- For maximum clarity, use EITHER weighted scoring OR occurrence count, not both

**Source:** S8 (Custom Data Pattern), S29 (Reduce False Positive Detections)
**Evidence Grade:** C

---

## Deployment Gotchas

### 6. Configuration Push Is Required After Every Change -- No Auto-Deploy

**Impact:** HIGH -- All configuration changes (data profiles, DLP rules, security rules) exist only in staging until explicitly pushed. Forgetting to push means enforcement points run stale configuration.

**Details:** Enterprise DLP follows a commit-then-push model:
1. Changes are saved in SCM/Panorama (staging)
2. An explicit "Push Config" action is required
3. Changes propagate to enforcement points

Unlike some products that auto-deploy on save, Palo Alto requires explicit push. This is intentional for change control but catches new admins who expect immediate enforcement.

**Workaround:**
- Always click "Push Config" after saving changes
- Use the pending changes indicator in SCM (shows unsaved/unpushed changes)
- Consider API-based push automation via `POST /sse/config/v1/config-versions`
- For Panorama: Commit > Push to Device Group/Template Stack

**Source:** S28 (Managing Configuration Changes)
**Evidence Grade:** A

---

### 7. ChatGPT/AI App DLP Requires Correct App-ID -- URL Filtering Is Insufficient

**Impact:** HIGH -- DLP rules targeting AI applications like ChatGPT must use App-ID-based matching, not URL-based. If App-ID is not recognized (signatures outdated), the DLP rule will not match AI app traffic.

**Details:** Palo Alto identifies applications via App-ID, a layer-7 application signature engine. For DLP to inspect ChatGPT traffic:
- The security rule must match on App-ID `openai-chatgpt` (or equivalent)
- App-ID signatures must be current (auto-updated with content updates)
- If App-ID fails to identify the application (e.g., new AI tool, encrypted traffic), the security rule will not match and DLP inspection is skipped

**Workaround:**
- Keep App-ID signatures updated (enable automatic content updates)
- Use App-ID + URL filtering together for defense-in-depth
- Check App-ID coverage for your target AI applications before creating rules
- For unrecognized AI apps, use URL-based matching as a fallback in a separate rule

**Source:** S25 (Security Rule for ChatGPT), Video #4 (GPT Demo)
**Evidence Grade:** B

---

### 8. Endpoint DLP (Cortex XDR) Is a Separate Management Surface

**Impact:** HIGH -- Endpoint DLP policies are managed through Cortex XDR, NOT through SCM or Panorama. This creates potential for policy drift between network and endpoint DLP.

**Details:** The Cortex XDR 5.0 DLP module:
- Has its own policy creation interface in the Cortex XDR console
- Uses the same Enterprise DLP data profiles and patterns (shared classification engine)
- But enforcement rules, actions, and scope are configured separately
- There is no unified view showing "here is what is enforced on network AND endpoint"

**Workaround:**
- Maintain a policy matrix document tracking which data profiles are enforced on which enforcement points (NGFW, Prisma Access, Cortex XDR)
- Use the same data profile names across surfaces for consistency
- Review both SCM and Cortex XDR configurations during audit cycles

**Source:** S26 (Endpoint DLP Policy Rule), Video #7 (XDR 5.0)
**Evidence Grade:** B

---

### 9. Custom Document Type Training Requires Minimum 20 Documents (50 Recommended)

**Impact:** MEDIUM -- Uploading a .zip with fewer than 20 documents for trainable classifier training will fail. The error messages may be cryptic.

**Details:** Requirements for custom document types:
- Minimum 20 documents in the .zip file
- Recommended 50+ documents for accurate ML training
- All documents must be text-based (no images, no scanned PDFs without OCR)
- Each document must have at least 500 characters
- Must include at least one positive AND one negative training document set
- The .zip file size has undocumented limits

**Workaround:**
- Collect at least 50 representative documents per document type
- Ensure all documents are text-extractable (not scanned images)
- Include diverse examples -- different authors, formats, lengths
- Test the document type after upload before using in production profiles

**Source:** S17 (About Custom Document Types), S18 (Custom Document Types)
**Evidence Grade:** A

---

## API & Automation Gotchas

### 10. Three Separate API Surfaces for End-to-End Policy Automation

**Impact:** MEDIUM -- Full policy automation requires calls to three different API surfaces (DLP API, SASE API, SCM API) with the same OAuth2 token but different base URLs and endpoint structures.

**Details:**
| Step | API Surface | Base URL |
|------|-----------|---------|
| Create data pattern | DLP API | `api.dlp.paloaltonetworks.com` |
| Create data profile | DLP API | `api.dlp.paloaltonetworks.com` |
| Create DLP rule | SCM API | `api.strata.paloaltonetworks.com` |
| Create security rule | SASE API | `pa-<region>.api.prismaaccess.com` |
| Push configuration | SASE API | `pa-<region>.api.prismaaccess.com` |

**Workaround:** Build an abstraction layer that wraps all three surfaces behind a unified interface. Use the same OAuth2 token (TSG-scoped) across all surfaces.

**Source:** API intelligence research, pan.dev documentation
**Evidence Grade:** A

---

### 11. EDM Data Preparation Still Requires On-Prem CLI App

**Impact:** MEDIUM -- While EDM dataset upload has API endpoints, the critical data preparation step (SHA256 hashing + AES-256 encryption) must be performed by the EDM CLI app running on a Windows or Linux machine. This breaks full cloud/API automation.

**Details:** The EDM security architecture requires:
1. Raw sensitive data (CSV/TSV) is loaded into the EDM CLI app
2. CLI app hashes each field with SHA256
3. CLI app encrypts the dataset with AES-256
4. Only the encrypted hash is uploaded to the DLP cloud
5. Raw data never leaves the organization's network

This design is intentional for security (raw data never touches the cloud) but prevents fully automated EDM pipelines.

**Workaround:**
- Automate the EDM CLI app via scripts (it supports a configuration file mode for batch processing -- S16)
- Run the CLI app as a scheduled task on a secure server with access to the source CSV
- Pipe the encrypted output to the API upload endpoint

**Source:** S12-S16 (EDM documentation), API intelligence
**Evidence Grade:** A

---

## Tribal Knowledge (Undocumented Best Practices)

### 12. Start with Predefined Patterns in Alert Mode -- Tune Before Blocking

**Impact:** CRITICAL -- Deploying blocking rules with broad predefined patterns will cause business disruption from false positives.

**Details:** Recommended phased approach:
1. **Phase 1 -- Alert:** Deploy with Action = Alert for all data profiles. Run for 2-4 weeks.
2. **Phase 2 -- Analyze:** Review DLP incidents. Identify false positive patterns. Adjust occurrence thresholds, switch to ML-based patterns for noisy regex patterns.
3. **Phase 3 -- Selective Block:** Switch to Block for high-confidence, low-false-positive patterns (e.g., credit card numbers). Keep Alert for lower-confidence patterns (e.g., "confidential" keyword).
4. **Phase 4 -- Expand:** Add more enforcement points, more data profiles, more document types.

**Source:** S24 (Recommendations for Security Rules), Video #2 (AI-Powered DLP)
**Evidence Grade:** B

---

### 13. Use Granular Data Profiles for Mixed-Severity Enforcement

**Impact:** HIGH -- Instead of creating separate security rules per data pattern, use Granular Data Profiles to apply different actions per match criterion within a single profile.

**Details:** A Granular Data Profile allows:
- Match criterion A (Credit Card Number): Action = Block
- Match criterion B (Social Security Number): Action = Alert
- Match criterion C (Custom Project Code): Action = Log Only

All within a single data profile attached to a single security rule. This dramatically reduces rule count and management complexity.

**Source:** S4 (Granular Data Profiles)
**Evidence Grade:** A

---

### 14. Nested Data Profiles Reduce Security Rule Sprawl

**Impact:** MEDIUM -- In large deployments with 10+ data profiles, each profile would traditionally need its own security rule. Nested profiles allow consolidation.

**Details:** A Nested Data Profile can contain multiple child profiles. Attach the single nested profile to one security rule. When any child profile matches, the parent profile triggers. This keeps security rule count manageable and simplifies change management.

**Source:** S3 (Nested Data Profiles)
**Evidence Grade:** A

---

### 15. Use the False Positive Reporting Feature to Improve ML Models

**Impact:** MEDIUM -- Palo Alto collects false positive reports to retrain ML models. Reporting false positives improves detection accuracy over time for ALL customers using Enterprise DLP.

**Details:** When a DLP incident is a confirmed false positive:
1. Navigate to the incident in the DLP dashboard
2. Use the "Report False Positive" action
3. Provide context on why it was a false positive
4. Palo Alto uses this feedback to retrain ML/LLM models

This creates a virtuous cycle: more feedback = better models = fewer false positives.

**Source:** S35 (Report a False Positive Detection), S38 (AI-Powered Classification blog)
**Evidence Grade:** B

---

## Summary Statistics

| Category | Count | Critical/High Impact |
|----------|-------|---------------------|
| Critical gotchas (deployment-breaking) | 5 (#1-5) | 5 |
| Deployment gotchas | 4 (#6-9) | 3 |
| API/automation gotchas | 2 (#10-11) | 0 |
| Tribal knowledge (best practices) | 4 (#12-15) | 3 |
| **Total** | **15** | **11** |
