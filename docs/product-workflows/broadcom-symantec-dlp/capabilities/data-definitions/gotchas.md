# Data Definitions — Gotchas
## Broadcom Symantec DLP (Enforce Server, version 16.x/25.x/26.x)

> **Purpose:** Comprehensive collection of gotchas, pitfalls, and best-practice warnings specific to data definition technologies (Data Identifiers, EDM, IDM, VML, Form Recognition, File Properties).
> **Evidence sources:** doc-corpus.md [S1-S28], video-intelligence.md [V1-V45, tribal knowledge], api-intelligence.md

---

## Table of Contents

1. [Data Identifier Gotchas](#1-data-identifier-gotchas)
2. [EDM Gotchas](#2-edm-gotchas)
3. [IDM Gotchas](#3-idm-gotchas)
4. [VML Gotchas](#4-vml-gotchas)
5. [Form Recognition Gotchas](#5-form-recognition-gotchas)
6. [File Properties Gotchas](#6-file-properties-gotchas)
7. [Cross-Technology Gotchas](#7-cross-technology-gotchas)
8. [API Gotchas for Data Definitions](#8-api-gotchas-for-data-definitions)

---

## 1. Data Identifier Gotchas

### G-DI-1: SSN "Wide" breadth matches phone numbers, zip+4, and random 9-digit sequences
**Impact:** HIGH
**Symptom:** US SSN detection rule triggers thousands of false positives per day.
**Root cause:** "Wide" breadth matches any 9-digit sequence that passes the area/group/serial validation. US phone numbers (without area code parentheses), zip+4 codes (555121234), and random 9-digit sequences frequently pass this validation.
**Mitigation:** Start with "Narrow" breadth (XXX-XX-XXXX dashed format only). If detection coverage is insufficient, move to "Medium" (accepts dashes and spaces). Only use "Wide" if combined with keyword proximity (e.g., require "SSN" or "social security" within 50 characters).
**Evidence:** A [S1, S8, tribal knowledge]

### G-DI-2: Credit card Luhn validator is strong but not infallible
**Impact:** LOW
**Symptom:** Occasional false positives on non-credit-card numbers that happen to pass Luhn.
**Root cause:** The Luhn algorithm validates ~90% of random number sequences as invalid, but ~10% of random 16-digit sequences will coincidentally pass Luhn. Long numeric sequences in scientific data, tracking numbers, and serial numbers occasionally match.
**Mitigation:** Combine credit card detection with file type or keyword proximity conditions for compound rules. Standalone credit card detection with "Narrow" or "Medium" breadth and Luhn validation has an acceptable FP rate for most environments.
**Evidence:** A [S1, S4, S8]

### G-DI-3: Custom data identifiers lack built-in validation algorithms
**Impact:** MEDIUM
**Symptom:** Custom data identifier matches far more content than expected.
**Root cause:** Built-in identifiers (CC, SSN, IBAN) include domain-specific validators (Luhn, area number check, modulo 97). Custom identifiers use regex patterns only. A custom regex for employee IDs (`EMP-\d{6}`) will match any text that looks like that format, including unrelated strings in vendor documents.
**Mitigation:** Add custom validator scripts where possible. Test custom patterns against a large corpus of real production data before deploying. Set minimum match thresholds higher (e.g., 3+) for custom identifiers without validators.
**Evidence:** B [S8]

### G-DI-4: Data identifier breadth setting is per-rule, not per-identifier
**Impact:** LOW (informational)
**Symptom:** Admin expects to set breadth globally for "US SSN" but finds it must be set in each rule that uses the identifier.
**Root cause:** Breadth is a rule-level setting, not a profile-level setting. The same data identifier can be used with different breadth settings in different rules.
**Mitigation:** Document the intended breadth setting for each identifier in a policy design guide. Review breadth consistency across rules during policy audits.
**Evidence:** A [S1, S8]

### G-DI-5: "Count unique" vs "Count all" changes detection behavior dramatically
**Impact:** MEDIUM
**Symptom:** Rule with "minimum 5 matches" triggers on a document with 1 SSN repeated 5 times (Count All mode) but not on a document with 4 unique SSNs (Count Unique mode).
**Root cause:** "Count unique" only counts distinct matched values. "Count all" counts every occurrence, including repeats of the same value. The use case determines which is correct.
**Mitigation:** Use "Count unique" when you want to detect bulk data exposure (many different SSNs = database extract). Use "Count all" when you want to detect any mention volume (same SSN repeated = user copying their own SSN multiple times).
**Evidence:** A [S4]

### G-DI-6: International data identifiers may not cover all sub-national formats
**Impact:** MEDIUM
**Symptom:** US Driver License identifier misses licenses from certain states.
**Root cause:** US Driver License formats vary by state. While Symantec covers all 50 states + DC, state format changes (new license designs) may not be immediately reflected in the built-in identifier.
**Mitigation:** Test the identifier against sample license numbers from your organization's primary states. For critical coverage gaps, create custom regex patterns to supplement the built-in identifier.
**Evidence:** B [S4]

---

## 2. EDM Gotchas

### G-EDM-1: Stale indexes are a SILENT FAILURE — new records are invisible
**Impact:** CRITICAL
**Symptom:** New employees, customers, or records added to the source database after the last index run are not detected by EDM rules. No error, no warning, no alert.
**Root cause:** EDM indexes are point-in-time snapshots. The index only contains records that existed at the time of indexing. New records are completely invisible until the next re-index.
**Mitigation:**
1. Schedule automated re-indexing (daily for high-turnover data, weekly for stable data)
2. Monitor the "Last Indexed" timestamp in the profile management screen
3. Set calendar reminders to verify index freshness after major data loads
4. Consider a monitoring script that checks index age via the EDM index API (`POST /edm/index`)
**Evidence:** A [S1, S4, V19, tribal knowledge]

### G-EDM-2: Error threshold (5% default) causes silent indexing failures
**Impact:** HIGH
**Symptom:** EDM indexing completes but skips a significant portion of records. The index appears active but coverage is incomplete.
**Root cause:** If empty cells, wrong-type data, extra columns, or formatting errors exceed 5% of rows, indexing either stops entirely or silently skips the affected rows (behavior depends on version).
**Mitigation:**
1. Pre-validate data source before indexing (check for blank mandatory fields, format consistency)
2. Review indexing error report after each index run (profile > View Errors)
3. Increase error threshold to 10% only for data sources with known quality issues, and investigate the root cause
4. Never set threshold above 15% -- high thresholds mask data quality problems
**Evidence:** A [S1, V19, tribal knowledge]

### G-EDM-3: Large-scale indexing degrades Enforce Server performance
**Impact:** HIGH
**Symptom:** Enforce Server becomes slow or unresponsive during EDM indexing of datasets with 1M+ rows. Console users experience timeouts.
**Root cause:** Default indexing runs on the Enforce Server, competing with the management console, incident processing, and policy deployment for CPU, memory, and I/O.
**Mitigation:**
1. Use Remote EDM Indexer for data sources >1M rows
2. Schedule indexing during off-peak hours (2-4 AM)
3. Monitor Enforce Server resource utilization during index runs
4. For very large datasets (>5M rows), consider nightly incremental updates rather than full re-indexing
**Evidence:** A [S1, S4]

### G-EDM-4: "2 of N fields" matching without KEY requirement generates massive false positives
**Impact:** HIGH
**Symptom:** EDM rule matches on common Name + Email combinations that coincidentally exist in the protected dataset, triggering on legitimate email signatures and CC lists.
**Root cause:** First Name + Email Address are extremely common corroborative values. Without requiring a KEY field (SSN, employee ID, account number), any email mentioning a common name and email address can trigger a match.
**Mitigation:** ALWAYS enable "At least one KEY field must be among matched fields." Mark unique identifiers (SSN, employee ID, CC number, account number) as KEY fields. Never rely solely on corroborative fields (name, DOB, email) for matching.
**Evidence:** B [S4, tribal knowledge]

### G-EDM-5: EDM profiles require special handling during DLP version upgrades
**Impact:** HIGH
**Symptom:** After DLP version upgrade, EDM profiles are corrupted, produce no matches, or throw errors.
**Root cause:** EDM index format changes between major DLP versions. Index files created under 15.x may be incompatible with 16.x.
**Mitigation:**
1. Before upgrade: document all EDM profiles and their source data locations
2. After upgrade: re-index ALL EDM profiles from source data
3. After upgrade: test each EDM profile with known matching content to verify detection
4. Follow EDM-specific upgrade instructions in the release notes (version-specific)
**Evidence:** A [V-gotcha]

### G-EDM-6: Database-sourced EDM queries run on the Enforce Server
**Impact:** MEDIUM
**Symptom:** Database-sourced EDM profiles add load to the Enforce Server during index refresh, because the JDBC query executes from the Enforce Server process.
**Root cause:** The Enforce Server establishes the database connection and executes the query directly. Large result sets consume memory and CPU on the Enforce Server during retrieval and indexing.
**Mitigation:**
1. Optimize SQL queries with WHERE clauses to limit result size (e.g., `WHERE status = 'ACTIVE'`)
2. For very large tables (>1M rows), export to CSV and use file-based source instead
3. Schedule database-sourced indexing during off-peak hours
**Evidence:** B [S4]

### G-EDM-7: Volatile fields (balance, GPA, timestamps) cause stale-match failures
**Impact:** MEDIUM
**Symptom:** EDM matches stop working after a few days because the source data has changed for volatile fields.
**Root cause:** If you include frequently changing fields (account balance, GPA, login timestamp) in the EDM index, the hashed values become stale immediately after the field values change. A "2 of N" match that requires balance as one of the 2 fields will fail as soon as the balance changes.
**Mitigation:** ONLY index stable identifiers (SSN, employee ID, name, DOB, email). Never index: balances, prices (use current value), timestamps, session IDs, or any field that changes daily.
**Evidence:** B [S4, tribal knowledge]

---

## 3. IDM Gotchas

### G-IDM-1: Binary files only support exact match — NOT partial content matching
**Impact:** MEDIUM
**Symptom:** A modified version of a CAD file (rotated, annotated, scaled) does not trigger IDM detection.
**Root cause:** Binary files (JPEG, CAD, executables, multimedia) are matched by binary stamp -- an exact byte-for-byte comparison. The rolling hash partial matching algorithm only works on files from which text can be extracted (Microsoft Office, PDF, plain text).
**Mitigation:** For binary file protection, accept that only exact copies are detected. For derivative detection of binary formats, convert to text-based equivalents before indexing (e.g., CAD to STEP export, or use File Properties detection as a complementary rule).
**Evidence:** A [S1, S4]

### G-IDM-2: Partial matching threshold that is too low causes false positives on short documents
**Impact:** MEDIUM
**Symptom:** Short documents (2-5 pages) trigger IDM partial matches on unrelated documents that happen to share common phrases or boilerplate.
**Root cause:** A 10% partial threshold on a 2-page document means ~2-3 sentences of overlap trigger a match. Common phrases ("please find attached", "as discussed", company boilerplate) easily exceed this threshold.
**Mitigation:** Use different IDM profiles with different thresholds based on document length. For short documents (<5 pages), use 20-30% threshold. For long documents (>20 pages), 10% is appropriate. Alternatively, group documents by length category.
**Evidence:** B [S4, tribal knowledge]

### G-IDM-3: Source documents change but IDM index is not rebuilt — new documents are unprotected
**Impact:** HIGH
**Symptom:** New confidential documents added to the source directory since the last index run are not detected.
**Root cause:** Same as EDM staleness (G-EDM-1). IDM fingerprints are point-in-time snapshots.
**Mitigation:** Schedule regular re-indexing. For document collections that change frequently (active M&A, ongoing litigation), use weekly re-indexing. For stable collections, monthly is sufficient.
**Evidence:** A [tribal knowledge]

### G-IDM-4: Endpoint partial matching requires explicit opt-in (off by default)
**Impact:** HIGH
**Symptom:** IDM partial matching works on Network Prevent servers but not on endpoint agents. Endpoints only detect full document copies.
**Root cause:** "Enable IDM support for endpoints" is a separate configuration checkbox in the IDM profile that is OFF by default. This is intentional because partial matching increases endpoint agent CPU and memory usage.
**Mitigation:** Enable endpoint IDM in the profile settings if endpoint partial matching is required for your use case. Test endpoint performance after enabling to ensure acceptable user experience.
**Evidence:** B [V22]

### G-IDM-5: Open-source and template code in IDM source causes false positives
**Impact:** MEDIUM
**Symptom:** IDM profile for source code IP detects open-source library files and standard boilerplate code as policy violations.
**Root cause:** If the source directory includes open-source dependencies (`/vendor/`, `/node_modules/`, `/third_party/`), those files are fingerprinted and will match anytime someone uses the same open-source code.
**Mitigation:** Exclude open-source directories and common template files from the IDM source path. Focus on proprietary business logic files only. Create separate profiles for open-source monitoring if needed.
**Evidence:** B [tribal knowledge]

### G-IDM-6: Common document templates cause cross-document false positives
**Impact:** MEDIUM
**Symptom:** IDM partial matching triggers on any document that uses the company's standard PowerPoint or Word template.
**Root cause:** Corporate document templates (title slides, cover pages, headers/footers) contain identical content across all documents. If the template content exceeds the partial match threshold, any document using the template triggers a match.
**Mitigation:** Either exclude template files from the IDM source or raise the partial match threshold above the template content percentage. For a 20-slide PowerPoint with 2 template slides, the template is 10% of the document -- set threshold above 10%.
**Evidence:** B [tribal knowledge]

---

## 4. VML Gotchas

### G-VML-1: Training data quality matters more than quantity
**Impact:** CRITICAL
**Symptom:** VML profile accuracy is low (<80%) despite having hundreds of training documents. Or accuracy appears high in training but false positive/negative rates are unacceptable in production.
**Root cause:** Training documents are not representative of the content type:
- All positive documents from the same author (model learns writing style, not content type)
- All positive documents from the same time period (model learns temporal patterns)
- Negative documents too different from positive (model learns topic, not sensitivity level)
**Mitigation:**
1. Use diverse positive examples (multiple authors, departments, time periods, sub-topics)
2. Use "near-miss" negative examples (same domain, different sensitivity level)
3. Target 250+ documents per set
4. Validate with a held-out test set (don't use all documents for training)
**Evidence:** A [S7, V20, tribal knowledge]

### G-VML-2: Too few training documents produce unreliable models
**Impact:** HIGH
**Symptom:** VML accuracy score looks acceptable (~85%) during training but produces many false positives and negatives in production because the model overfits to the small training set.
**Root cause:** With fewer than 50 documents per set, the statistical model learns noise and coincidental patterns rather than meaningful content signals.
**Mitigation:** Minimum: 50 documents per set. Recommended: 250+ per set. If you cannot reach 50, do NOT use VML -- use IDM (fingerprinting) or keyword patterns instead until sufficient training data is available.
**Evidence:** A [S7, V20]

### G-VML-3: VML models decay as content evolves over time
**Impact:** MEDIUM
**Symptom:** VML profile that was 92% accurate when trained 2 years ago now has a 15% false negative rate.
**Root cause:** Language, terminology, document formats, and writing styles evolve. A model trained on 2022 financial reports may not recognize 2025 report formats that use new financial terms, layout changes, or regulatory language.
**Mitigation:** Retrain VML profiles annually, or whenever the false negative rate exceeds 10%. Add recent documents to the training sets and retrain the model.
**Evidence:** B [S7]

### G-VML-4: VML only works on text-extractable content — not binary files
**Impact:** LOW (but important to understand)
**Symptom:** VML profile does not detect images, executables, compiled code, or proprietary binary formats.
**Root cause:** VML uses statistical text analysis (word frequencies, n-gram patterns). Binary data has no extractable "words" for the model to analyze.
**Mitigation:** Use IDM for binary file detection (exact match). Use File Properties for binary file type detection. VML is exclusively for text-based documents.
**Evidence:** A [S7]

### G-VML-5: Using real sensitive data for VML training creates a secondary data protection problem
**Impact:** HIGH
**Symptom:** VML training directory contains actual confidential documents (real patient records, real financial data). The training directory itself becomes a data protection liability.
**Root cause:** VML training requires example documents. If those examples contain real sensitive data, the training directory must be protected to the same standard as the data it is designed to detect.
**Mitigation:** Use de-identified or anonymized training data wherever possible. For healthcare: work with the privacy officer to prepare anonymized clinical notes. For financial: use sanitized report templates with fictional data. If real data must be used, restrict access to the training directory.
**Evidence:** B [tribal knowledge]

---

## 5. Form Recognition Gotchas

### G-FR-1: Form layout changes break recognition — requires template re-registration
**Impact:** MEDIUM
**Symptom:** Updated version of a tax form (e.g., new W-2 layout for the current tax year) is not detected.
**Root cause:** Form Recognition matches layout and structure. When the IRS, CMS, or any organization updates a form's layout, the existing template no longer matches the new version.
**Mitigation:** Re-register form templates whenever the form design changes. For tax forms (W-2, 1099, W-4), update templates annually during tax season. For regulatory forms, monitor issuing agencies for layout updates.
**Evidence:** A [S1, V21]

### G-FR-2: Low-resolution scans (<150 DPI) cause recognition failures
**Impact:** MEDIUM
**Symptom:** Scanned forms that are clearly the registered form type are not detected.
**Root cause:** OCR and layout recognition algorithms require minimum resolution to identify field boundaries and text content. Below 150 DPI, form structure becomes ambiguous.
**Mitigation:** Set scanning standards to 300 DPI minimum for all forms. Communicate resolution requirements to departments that scan forms (HR, finance, clinics). Consider adding a file property rule as a secondary check for form-like files.
**Evidence:** B [V21]

### G-FR-3: Filled forms match better than blank forms in most cases
**Impact:** LOW (informational)
**Symptom:** Registration with a blank form template sometimes fails to detect filled versions that have significantly more content than the blank template.
**Root cause:** The filled content (handwritten or typed entries in form fields) changes the visual profile of the form compared to the blank template.
**Mitigation:** Register the BLANK form as the primary template (this is the recommended approach). If detection accuracy is low, register 2-3 sample filled forms as additional reference templates. The system uses the best match.
**Evidence:** B [V21]

---

## 6. File Properties Gotchas

### G-FP-1: File extension renaming does NOT bypass detection (this is a STRENGTH)
**Impact:** N/A (positive -- security feature)
**Symptom:** Users rename "data.xlsx" to "data.txt" hoping to bypass DLP. Detection still catches it.
**Root cause:** Symantec DLP detects file types by binary signature (magic bytes), not by file extension. The 330+ file type recognizers examine the file content to determine the true type.
**Mitigation:** N/A -- this is a security strength. Document this in user awareness training to discourage evasion attempts.
**Evidence:** A [S1, S4]

### G-FP-2: Encrypted/password-protected archives cannot be content-inspected
**Impact:** HIGH
**Symptom:** DLP detects that a file is an encrypted ZIP but cannot inspect the contents inside.
**Root cause:** Without the password, DLP cannot decompress and inspect archive contents. File type detection identifies it as "encrypted archive" but content-based rules (data identifiers, EDM, IDM, VML) cannot evaluate the encrypted content.
**Mitigation:** Create a dedicated policy that DETECTS encrypted file transfers (using file property detection). Flag encrypted outbound files as a security event regardless of content. Do NOT create exceptions for encrypted files -- that teaches users to encrypt to bypass DLP.
**Evidence:** B [tribal knowledge]

### G-FP-3: Archive extraction depth may miss nested archives
**Impact:** MEDIUM
**Symptom:** A ZIP file inside another ZIP file (nested archive) is not inspected at the inner level.
**Root cause:** Archive extraction has configurable depth limits (default varies by deployment). Deeply nested archives may not be fully extracted.
**Mitigation:** Verify archive extraction depth settings on detection servers. For high-security environments, set extraction depth to 5+ levels. Note that deep extraction increases CPU usage.
**Evidence:** B [S4]

### G-FP-4: File size rules generate excessive noise without compound conditions
**Impact:** MEDIUM
**Symptom:** "File size > 25 MB" rule generates hundreds of incidents per day from legitimate large file transfers (marketing images, video files, software packages).
**Root cause:** Standalone file size rules are too broad. Many legitimate business operations involve large files.
**Mitigation:** ALWAYS combine file size rules with other conditions (file type, sender group, recipient domain) in compound rules. Use file size as a secondary indicator, not a primary detection method.
**Evidence:** B [tribal knowledge]

### G-FP-5: Custom document properties are application-specific
**Impact:** LOW
**Symptom:** Custom document property detection works for Microsoft Office but not for PDF or other formats.
**Root cause:** Custom properties (e.g., "Classification: Confidential" in Office Document Properties) are stored differently in each file format. Detection coverage varies by format.
**Mitigation:** Test custom property detection against each target file format. For cross-format classification, consider using MIP sensitivity labels instead of custom document properties.
**Evidence:** B [S4]

---

## 7. Cross-Technology Gotchas

### G-CROSS-1: Choosing the wrong technology for the data type wastes effort
**Impact:** HIGH
**Symptom:** Organization spends weeks building keyword rules for structured data that should use EDM, or training VML models for data that should use data identifiers.
**Root cause:** Teams default to the technology they understand (usually keywords) rather than the technology that is best suited for the data type.
**Mitigation:** Technology selection decision tree:
- **Known structured data (CSV/DB)** --> EDM
- **Known unstructured documents** --> IDM
- **Known data format (SSN, CC, IBAN)** --> Built-in Data Identifiers
- **Organization-specific format** --> Custom Regex/Keywords
- **Content type (financial reports, code)** --> VML
- **Known form layout** --> Form Recognition
- **File type/metadata concern** --> File Properties
**Evidence:** B [tribal knowledge]

### G-CROSS-2: EDM and VML address different problems — not interchangeable
**Impact:** MEDIUM
**Symptom:** Admin tries to use EDM to detect "financial reports" (a content type) or VML to detect "specific SSNs" (specific data values).
**Root cause:** EDM detects SPECIFIC DATA VALUES (e.g., John Smith's SSN is 123-45-6789). VML detects CONTENT TYPES (e.g., "this document looks like a financial report"). They answer different questions.
**Mitigation:** Use EDM when you know the exact data to protect (databases, records). Use VML when you know the type of content to protect but cannot enumerate every instance (document classification).
**Evidence:** A [S1, S7]

### G-CROSS-3: Regex patterns are a poor substitute for data identifiers
**Impact:** MEDIUM
**Symptom:** Custom regex for SSN detection (`\d{3}-\d{2}-\d{4}`) generates 10x more false positives than the built-in US SSN data identifier.
**Root cause:** Built-in data identifiers include domain-specific validators (area number range check, Luhn algorithm) that eliminate most false positives. Raw regex only validates format.
**Mitigation:** ALWAYS use built-in data identifiers when available. Only create custom regex patterns when no built-in identifier exists for your data type. If you must use regex, combine it with keyword proximity to add contextual validation.
**Evidence:** A [S1, S8]

### G-CROSS-4: Multiple technologies on the same content increase latency
**Impact:** MEDIUM
**Symptom:** Compound rule with EDM + VML + 3 data identifiers takes 2-3 seconds per message.
**Root cause:** Each technology in a compound rule evaluates the content independently. EDM performs hash lookups, VML performs statistical analysis, and data identifiers perform pattern matching. These are additive.
**Mitigation:** Only use multiple technologies in a compound rule when all conditions must match (AND logic). For OR logic (any technology triggers), use separate simple rules. Monitor detection latency and simplify compound rules if latency exceeds SLA.
**Evidence:** B [S8]

---

## 8. API Gotchas for Data Definitions

### G-API-1: No API for creating EDM/IDM/VML profiles (console-only)
**Impact:** CRITICAL
**Symptom:** Cannot automate data definition setup via API. All profile creation, column mapping, document registration, and model training must be done in the Enforce console.
**Root cause:** The Enforce Server REST API covers policy management (list, import, export, deploy) but NOT individual data profile creation. The only data-definition API is the EDM index trigger (`POST /edm/index`, DLP 16.0 RU2+).
**Mitigation:**
1. Create profiles manually in the console
2. Trigger re-indexing via API for EDM (`POST /edm/index`)
3. For cross-environment promotion: export policies containing profile references via policy export API (25.1+), then import on target
4. Note: CloudSOC API has more granular profile creation capabilities than the on-prem API
**Evidence:** A [API-intelligence]

### G-API-2: Policy export includes profile REFERENCES, not profile DATA
**Impact:** HIGH
**Symptom:** Importing a policy XML on a target Enforce Server fails because the referenced EDM/IDM/VML profiles do not exist on the target.
**Root cause:** Policy export XML contains profile names and IDs as references. The actual index data (EDM hashes, IDM fingerprints, VML model) is NOT included in the export.
**Mitigation:** Before importing policies, create the referenced data profiles on the target Enforce Server first. Then import the policy XML. After import, verify all profile references are correctly linked.
**Evidence:** B [API-intelligence, tribal knowledge]

### G-API-3: CloudSOC API has better data identifier access than on-prem API
**Impact:** MEDIUM (informational)
**Symptom:** Admin discovers that CloudSOC API can list and create profiles with data identifiers, but the on-prem Enforce API cannot.
**Root cause:** CloudSOC was built with a more modern API-first architecture. The on-prem Enforce Server API is an evolving surface that started with incident management and is progressively adding more domains.
**Mitigation:** For cloud/CASB deployments, leverage the CloudSOC API (`GET /api/clouddlp/protect/public/dataIdentifiers`) for data identifier enumeration and profile management. For on-prem, use the console.
**Evidence:** A [API-intelligence]

---

## Summary: Top 10 Data Definition Gotchas by Impact

| Rank | Gotcha ID | Summary | Impact |
|------|-----------|---------|--------|
| 1 | G-EDM-1 | Stale EDM indexes miss new records (SILENT FAILURE) | CRITICAL |
| 2 | G-VML-1 | Training data quality > quantity; poor diversity ruins accuracy | CRITICAL |
| 3 | G-API-1 | No API for EDM/IDM/VML profile creation (console-only) | CRITICAL |
| 4 | G-DI-1 | SSN "Wide" breadth matches phone numbers, zip codes | HIGH |
| 5 | G-EDM-2 | 5% error threshold causes silent indexing failures | HIGH |
| 6 | G-EDM-3 | Large-scale indexing degrades Enforce Server | HIGH |
| 7 | G-EDM-4 | "2 of N" without KEY field generates massive false positives | HIGH |
| 8 | G-IDM-4 | Endpoint IDM partial matching off by default | HIGH |
| 9 | G-FP-2 | Encrypted archives cannot be content-inspected | HIGH |
| 10 | G-CROSS-1 | Choosing the wrong technology for the data type | HIGH |

---

*End of data definitions gotchas document. Total gotchas documented: 31 across 8 categories. Every gotcha includes impact level, root cause, and mitigation.*
