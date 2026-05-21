# Classifications & Dictionaries — Gotchas
## Broadcom Symantec DLP (Enforce Server, version 16.x/25.x/26.x)

> **Purpose:** Gotchas, pitfalls, and best-practice warnings for dictionary management, data identifier selection, classification policy design, and MIP label integration.
> **Evidence sources:** doc-corpus.md [S1-S28], video-intelligence.md [V1-V45, tribal knowledge], api-intelligence.md

---

## Table of Contents

1. [Dictionary Threshold Gotchas](#1-dictionary-threshold-gotchas)
2. [Dictionary Content Gotchas](#2-dictionary-content-gotchas)
3. [Data Identifier Selection Gotchas](#3-data-identifier-selection-gotchas)
4. [Classification Policy Design Gotchas](#4-classification-policy-design-gotchas)
5. [MIP Integration Gotchas](#5-mip-integration-gotchas)
6. [False Positive Management Gotchas](#6-false-positive-management-gotchas)
7. [Maintenance and Lifecycle Gotchas](#7-maintenance-and-lifecycle-gotchas)

---

## 1. Dictionary Threshold Gotchas

### G-DT-1: Threshold too low on large dictionaries generates massive false positives
**Impact:** HIGH
**Symptom:** Medical drug name dictionary (2,800 entries) with threshold 1 triggers on almost every email because common words like "iron" (mineral supplement), "patch" (nicotine patch), or "plan" (insurance plan) are in the dictionary.
**Root cause:** Large dictionaries inevitably contain entries that overlap with common English words. A threshold of 1 means ANY single match triggers.
**Mitigation:** Set threshold proportional to dictionary size: ~0.1-0.5% of entries. For a 2,800-entry medical dictionary, start with threshold 3-5. For a 50-entry code name list, threshold 1 is appropriate. Always test against a sample of normal business email before deploying.
**Evidence:** B [S8, tribal knowledge]

### G-DT-2: Weighted scoring not intuitive — admins expect count-based behavior
**Impact:** MEDIUM
**Symptom:** Dictionary with threshold 3 and entries weighted 1-5 triggers when 1 high-weight entry matches (e.g., "fentanyl" at weight 3 meets threshold 3), but admin expected 3 separate entries to match.
**Root cause:** The threshold applies to the SUM OF WEIGHTS, not the count of matched entries. A single entry with weight 3 satisfies a threshold of 3.
**Mitigation:** Document whether your threshold is count-based or weight-based. If using weights, set threshold to the minimum weight sum you want. If you want at least 3 entries regardless of weight, set all weights to 1 and threshold to 3.
**Evidence:** B [S8]

### G-DT-3: Threshold changes require policy re-deployment
**Impact:** LOW
**Symptom:** Admin changes dictionary threshold but existing detection servers continue using the old threshold until policy is redeployed.
**Root cause:** Threshold is part of the detection rule configuration. Changes must be saved and deployed (either automatically or via explicit policy apply, depending on version).
**Mitigation:** After threshold changes, verify the policy shows the updated configuration on the detection server. For endpoint agents, allow up to 15 minutes for the updated policy to propagate.
**Evidence:** A [S1, S4]

---

## 2. Dictionary Content Gotchas

### G-DC-1: Common words in specialized dictionaries cause cross-domain false positives
**Impact:** HIGH
**Symptom:** Legal dictionary containing "contract", "agreement", "party", "notice" triggers on routine business emails that are not legal documents.
**Root cause:** Legal, medical, and financial vocabularies overlap significantly with everyday business English. Words like "risk", "exposure", "treatment", "material", "consideration" have different meanings in specialized vs. general contexts.
**Mitigation:**
1. Remove overly common terms from specialized dictionaries
2. Use proximity matching (require specialized terms near each other)
3. Use compound rules (require dictionary match AND another condition like EDM or file type)
4. Set higher thresholds to require term density rather than individual matches
**Evidence:** B [S8, tribal knowledge]

### G-DC-2: Dictionary entries with multiple words match as phrases, not individual words
**Impact:** MEDIUM
**Symptom:** Dictionary entry "social security number" only matches when all three words appear together in that exact order, not when "social", "security", or "number" appear individually.
**Root cause:** Multi-word dictionary entries are matched as phrases by default. This is usually the desired behavior but can be surprising.
**Mitigation:** This is correct behavior for most use cases. If you want to match individual words, enter them as separate dictionary entries. For phrase matching, keep multi-word entries as-is.
**Evidence:** A [S1, S8]

### G-DC-3: Unicode and special characters in dictionaries cause matching failures
**Impact:** MEDIUM
**Symptom:** Dictionary entries with accented characters (e.g., "resume" vs "resume"), em-dashes, smart quotes, or non-ASCII characters fail to match content that uses the ASCII equivalent.
**Root cause:** String matching is character-exact by default. "resume" (with accent) does not match "resume" (without accent) unless normalization is enabled.
**Mitigation:** Include both accented and non-accented versions of terms in the dictionary. Use UTF-8 encoding for the dictionary file. Test matching with real-world content that may use different character representations.
**Evidence:** B [S8]

### G-DC-4: Stemming causes unexpected matches on word forms
**Impact:** MEDIUM
**Symptom:** Dictionary entry "report" with stemming enabled matches "reporting", "reported", "reporter", and "reportedly" -- the last two are not the intended meaning.
**Root cause:** Stemming algorithms reduce words to their root form. "Reporter" stems to "report", which matches the dictionary entry.
**Mitigation:** Disable stemming unless you specifically need it. If stemming is needed, review the stemmed forms of all dictionary entries and add exceptions for unwanted forms. For most classification use cases, exact matching with "whole words only" is more precise.
**Evidence:** B [S8]

### G-DC-5: Dictionary file encoding mismatch causes import failures or garbled entries
**Impact:** MEDIUM
**Symptom:** Dictionary import succeeds but entries contain garbled characters, or import fails with encoding errors.
**Root cause:** The dictionary file was saved in a different encoding (Windows-1252, ISO-8859-1) than what the import process expects (UTF-8).
**Mitigation:** Always save dictionary files as UTF-8 with BOM (Byte Order Mark) for maximum compatibility. Verify encoding before import by opening the file in a text editor that displays encoding.
**Evidence:** B [S8]

---

## 3. Data Identifier Selection Gotchas

### G-ID-1: Using regex instead of built-in data identifiers loses validation
**Impact:** HIGH
**Symptom:** Custom regex for SSN (`\d{3}-\d{2}-\d{4}`) matches 10x more content than the built-in US SSN identifier, including phone numbers, dates, and random number sequences.
**Root cause:** Built-in data identifiers include domain-specific validators (area number range for SSN, Luhn for CC, modulo-97 for IBAN) that reject ~90% of false pattern matches. Custom regex has no validation.
**Mitigation:** ALWAYS use built-in data identifiers when they exist for your data type. Reserve custom regex for data types with no built-in identifier. If you must use regex, combine with keyword proximity (e.g., require "SSN" within 50 characters) to add contextual validation.
**Evidence:** A [S1, S8]

### G-ID-2: Multiple brand-specific CC identifiers are redundant with the generic CC identifier
**Impact:** LOW (informational)
**Symptom:** Admin creates separate rules for Visa, Mastercard, Amex, and Discover when the generic "Credit Card Number" identifier already detects all of them.
**Root cause:** The generic Credit Card Number identifier uses Luhn validation and detects all card brands by their prefix patterns. Brand-specific identifiers are subsets.
**Mitigation:** Use the generic "Credit Card Number" identifier unless you need brand-specific severity or response actions (e.g., block Amex but notify for Visa). For most PCI compliance use cases, the generic identifier is sufficient and simpler.
**Evidence:** A [S1, S4]

### G-ID-3: International identifiers may overlap or conflict with each other
**Impact:** MEDIUM
**Symptom:** A document triggers matches on both "France INSEE" and "Brazil CPF" because both identifiers match the same number sequence.
**Root cause:** Some national identifier formats overlap in digit length and structure. A 13-digit number could potentially pass validation for multiple country identifiers.
**Mitigation:** If your organization operates in a specific region, only enable identifiers for that region. If global coverage is needed, use compound rules that combine national identifiers with country-context dictionaries (e.g., INSEE + French language keywords).
**Evidence:** B [S4]

### G-ID-4: Data identifier breadth is set per-rule, creating inconsistency across policies
**Impact:** MEDIUM
**Symptom:** SSN detection has "Narrow" breadth in the PCI policy but "Wide" breadth in the HIPAA policy, causing different detection behavior for the same data.
**Root cause:** Breadth is a rule-level setting, not a global identifier setting. Different policy authors may choose different breadth settings for the same identifier.
**Mitigation:** Establish a standard breadth setting per identifier in a policy design guide. During policy reviews, audit breadth consistency. Document the rationale for any deviation from the standard.
**Evidence:** A [S1, S8, tribal knowledge]

---

## 4. Classification Policy Design Gotchas

### G-CP-1: AND-only compound rules miss OR scenarios
**Impact:** HIGH
**Symptom:** Classification policy requires CC number AND financial dictionary match. A spreadsheet with 100 credit card numbers but no financial terms is NOT detected because the dictionary condition is not met.
**Root cause:** Compound rules in Symantec DLP use AND logic exclusively. There is no OR operator within a compound rule. All conditions must match.
**Mitigation:** For OR logic, create separate simple rules within the same policy. Each rule evaluates independently. If ANY rule matches, an incident is created. Example: Rule 1 = CC >= 10 (catches bulk cards); Rule 2 = CC >= 1 AND financial dict >= 2 (catches cards in financial context). Both rules exist in the same policy.
**Evidence:** A [S1, S4]

### G-CP-2: Highest severity rule wins — lower-severity rules are overshadowed
**Impact:** MEDIUM
**Symptom:** Admin creates a 3-tier classification with different severities, but all incidents show as "High" because Rule 1 (High) always matches when Rule 2 (Medium) matches.
**Root cause:** If multiple rules in the same policy match, the incident receives the highest severity among the matching rules. A broad High-severity rule that fires on 1 CC number will overshadow a targeted Medium-severity rule that fires on CC + financial context.
**Mitigation:** Design severity tiers so that higher-severity rules are NARROWER (more conditions, higher thresholds) than lower-severity rules. Example: High = CC >= 10 + spreadsheet; Medium = CC >= 1 + financial context; Low = CC >= 1 (standalone). High fires only on bulk data; Medium fires on contextual single cards; Low catches everything else.
**Evidence:** A [S1, S4]

### G-CP-3: Too many classification tiers create confusion
**Impact:** MEDIUM
**Symptom:** 6-tier classification with overlapping conditions generates incidents that analysts cannot triage because they do not understand which tier applies and why.
**Root cause:** Complex classification hierarchies with many overlapping conditions are difficult to maintain, audit, and explain to incident responders.
**Mitigation:** Limit to 3-4 classification tiers maximum (Restricted, Confidential, Internal, Public). Each tier should have clearly differentiated conditions. Document the classification scheme in a reference guide for analysts.
**Evidence:** B [tribal knowledge]

### G-CP-4: Classification policies without response rules are monitoring-only
**Impact:** LOW (informational)
**Symptom:** Classification policy correctly detects and categorizes content, but no enforcement action occurs.
**Root cause:** Detection rules identify content; response rules act on it. Without response rules, incidents are logged but no blocking, notification, encryption, or labeling occurs.
**Mitigation:** For each classification tier, attach appropriate response rules: Restricted = Block + Encrypt; Confidential = Notify + Label; Internal = Syslog only. Even monitoring-only tiers should have at least a Syslog response for SIEM visibility.
**Evidence:** A [S1, S4]

---

## 5. MIP Integration Gotchas

### G-MIP-1: MIP SDK must be updated when Microsoft updates the MIP platform
**Impact:** HIGH
**Symptom:** MIP label detection stops working after a Microsoft cloud update. Labels are not recognized or applied.
**Root cause:** Microsoft periodically updates the MIP/AIP SDK and cloud services. If the SDK version on the Enforce Server is too old, it may not be compatible with the current Microsoft cloud endpoint.
**Mitigation:** Monitor Broadcom release notes for MIP SDK compatibility updates. Test MIP functionality after any Microsoft 365 tenant update. Keep the MIP SDK version within one major version of current.
**Evidence:** B [S2, tribal knowledge]

### G-MIP-2: Users can downgrade MIP labels before sending, bypassing DLP
**Impact:** HIGH
**Symptom:** User labels document as "Highly Confidential", DLP blocks external send. User then downgrades label to "Internal" and resends. DLP no longer triggers the MIP tag rule.
**Root cause:** By default, MIP allows users to downgrade sensitivity labels. DLP only sees the current label, not the label history.
**Mitigation:** Configure MIP label policy in Azure AD to require justification for label downgrades (or prohibit downgrades entirely). This is an Azure AD configuration, not a DLP configuration. DLP should also have content-based detection rules (data identifiers, EDM) that trigger regardless of label status.
**Evidence:** B [S2, tribal knowledge]

### G-MIP-3: MIP label detection does not work on all file formats
**Impact:** MEDIUM
**Symptom:** PDF files and plain text files do not trigger MIP tag detection rules.
**Root cause:** MIP labels are embedded as metadata in supported formats (Microsoft Office documents, Outlook emails). Not all file formats support MIP label embedding. PDF support depends on the PDF being MIP-enabled (created by a MIP-aware application).
**Mitigation:** Do not rely solely on MIP labels for classification. Use MIP labels as a complementary layer alongside content-based detection (data identifiers, EDM, VML). Content-based rules detect sensitive data regardless of whether a label is present.
**Evidence:** B [S2]

### G-MIP-4: Bidirectional label sync creates circular policy triggers
**Impact:** MEDIUM
**Symptom:** DLP applies MIP label -> labeled document triggers MIP tag rule -> response rule tries to re-apply label -> loop.
**Root cause:** If a response rule applies a MIP label and a detection rule triggers on the same label, the response action re-triggers detection.
**Mitigation:** Design MIP rules carefully to avoid circular triggers. Use the "Upgrade only" label behavior (do not re-apply the same label). Separate MIP detection policies from MIP labeling response rules using different policy groups or severity conditions.
**Evidence:** B [tribal knowledge]

### G-MIP-5: Network access requirements for MIP may be blocked by firewall
**Impact:** HIGH
**Symptom:** MIP label application fails with timeout or connection errors.
**Root cause:** The Enforce Server must reach Azure AD authentication endpoints and Azure Rights Management Service. Corporate firewalls may block these endpoints.
**Mitigation:** Ensure the following domains are allowed through the firewall from the Enforce Server:
- `login.microsoftonline.com` (authentication)
- `*.protection.outlook.com` (Rights Management)
- `*.aadrm.com` (Azure RMS)
- `*.informationprotection.azure.com` (MIP service)
**Evidence:** A [S2]

---

## 6. False Positive Management Gotchas

### G-FP-1: Broad dictionaries without compound conditions generate unmanageable incident volume
**Impact:** CRITICAL
**Symptom:** 500+ incidents per day from a medical dictionary rule applied to all email traffic.
**Root cause:** Medical terms like "treatment", "condition", "history", "prescription" appear in everyday business communication. Without a compound condition (like EDM match or sender restriction), the dictionary rule triggers on non-medical content.
**Mitigation:**
1. ALWAYS combine domain dictionaries with a second condition (EDM, file type, sender group, recipient domain)
2. Start with high thresholds and reduce gradually
3. Monitor FP rate for 2 weeks before lowering thresholds
4. Target <5% FP rate before enabling enforcement
**Evidence:** B [S8, tribal knowledge]

### G-FP-2: False positive triage costs exceed the value of monitoring
**Impact:** HIGH
**Symptom:** Security team spends 20+ hours/week reviewing false positive incidents, reducing time for real incident investigation.
**Root cause:** Low-precision classification rules generate high incident volume. Each incident requires manual review to determine if it is a true positive.
**Mitigation:**
1. Tune classification rules to reduce FP rate BEFORE enabling at scale
2. Use severity-based triage (only manually review High and Medium; auto-close Low/Informational)
3. Set incident data retention limits on high-volume, low-severity policies
4. Consider auto-resolution rules for known FP patterns
**Evidence:** B [V17, tribal knowledge]

### G-FP-3: Adding exceptions to fix FPs creates long-term coverage gaps
**Impact:** HIGH
**Symptom:** Over 6 months, 50 exceptions accumulate. Some were for temporary situations that ended months ago. The policy now has 50 permanent bypass paths.
**Root cause:** Exceptions are the fastest way to silence false positives, so admins add them reactively. Symantec DLP has no built-in exception expiration mechanism.
**Mitigation:**
1. Document reason and expected expiration for EVERY exception
2. Schedule quarterly exception reviews (audit and remove stale exceptions)
3. Track exception count as a security metric (growing count = classification design problem)
4. Prefer tuning the classification rule (higher threshold, better dictionary) over adding exceptions
**Evidence:** B [tribal knowledge]

---

## 7. Maintenance and Lifecycle Gotchas

### G-ML-1: Dictionaries become stale without a maintenance owner
**Impact:** HIGH
**Symptom:** Medical drug dictionary created in 2022 does not include drugs approved in 2023-2024. New drug names in patient records are not classified.
**Root cause:** Dictionaries are static after import. Without a designated owner and update schedule, they degrade over time.
**Mitigation:** Assign a dictionary owner (individual or team) for each dictionary. Establish update schedules:
- Medical: quarterly (FDA approvals)
- Legal: annually
- Financial: semi-annually
- Project codes: per-project
- Competitor names: quarterly
Include dictionary updates in the regular DLP maintenance calendar.
**Evidence:** B [tribal knowledge]

### G-ML-2: Dictionary updates require full re-import (no incremental add)
**Impact:** LOW (informational)
**Symptom:** Admin wants to add 5 new entries to a 2,800-entry dictionary but must re-import the entire dictionary file.
**Root cause:** Symantec DLP dictionary import replaces the entire keyword list, not appending to it. There is no "add entry" operation.
**Mitigation:** Maintain the master dictionary file in version control (Git) or a shared document. Add new entries to the master file, then re-import the complete file into the keyword rule. This ensures the master file is the single source of truth.
**Evidence:** B [S8, tribal knowledge]

### G-ML-3: Classification changes without change management cause detection gaps
**Impact:** HIGH
**Symptom:** Admin modifies a classification rule threshold during a false positive spike, reducing detection below acceptable levels. No one notices until a compliance audit.
**Root cause:** Classification changes are not tracked in a change management system. The Enforce console audit log records changes but does not alert on policy modifications.
**Mitigation:**
1. Use the Enforce audit log (System > Servers and Detectors > Audit Logs) to review all policy changes
2. Establish a change management process for classification modifications
3. Require peer review for threshold changes on compliance-critical policies
4. Forward audit logs to SIEM for change detection alerting
**Evidence:** A [S1, S4, tribal knowledge]

### G-ML-4: No built-in classification reporting across all policies
**Impact:** MEDIUM
**Symptom:** Admin cannot easily answer "what data types are we currently classifying?" without manually reviewing every policy.
**Root cause:** Symantec DLP reports on incidents, not on classification coverage. There is no built-in report that shows "all data identifiers in use across all policies" or "all dictionaries in use."
**Mitigation:** Create a manual classification inventory:
- Export all policies as XML (Manage > Policies > Export)
- Parse the XML to extract data identifier references, keyword lists, and data profile references
- Maintain this inventory alongside the policy documentation
- Update after any policy change
**Evidence:** B [tribal knowledge]

### G-ML-5: Testing classification changes in production risks false negatives
**Impact:** MEDIUM
**Symptom:** Admin tests a threshold change on a production policy. During the test period, real incidents are missed because the threshold was set too high.
**Root cause:** No built-in test/staging environment for classification rule changes.
**Mitigation:** Use the "Test Without Notifications" mode for classification experiments. Create a separate test policy group with a dedicated test detection server. Test changes there before applying to production policies.
**Evidence:** A [S1, S4, V17]

---

## Summary: Top 10 Classification & Dictionary Gotchas

| Rank | Gotcha ID | Summary | Impact |
|------|-----------|---------|--------|
| 1 | G-FP-1 | Broad dictionaries without compound conditions = unmanageable incident volume | CRITICAL |
| 2 | G-DT-1 | Low threshold on large dictionaries = massive false positives | HIGH |
| 3 | G-ID-1 | Regex instead of built-in identifiers = loss of validation algorithms | HIGH |
| 4 | G-CP-1 | AND-only compound rules miss OR scenarios | HIGH |
| 5 | G-MIP-2 | Users can downgrade MIP labels, bypassing DLP rules | HIGH |
| 6 | G-MIP-5 | Firewall blocks MIP connectivity from Enforce Server | HIGH |
| 7 | G-FP-3 | Exception accumulation creates permanent coverage gaps | HIGH |
| 8 | G-ML-1 | Dictionaries become stale without maintenance owner | HIGH |
| 9 | G-DC-1 | Common words in specialized dictionaries cause cross-domain FPs | HIGH |
| 10 | G-CP-2 | Highest severity rule wins, overshadowing lower-tier classifications | MEDIUM |

---

*End of classifications & dictionaries gotchas document. Total gotchas documented: 28 across 7 categories. Every gotcha includes impact level, root cause, and mitigation.*
