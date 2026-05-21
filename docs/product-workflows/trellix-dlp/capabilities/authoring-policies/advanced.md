# Authoring Policies -- Complete Field Reference
## Trellix DLP (ePO-managed, version 11.x)

> Capability: authoring-policies | Generated: 2026-05-21
> Organization: By screen (not by workflow step) -- this is the reference manual
> Enhanced: UI diagrams, worked examples, WHY/GOTCHA annotations per object type

---

## How to Use This Document

This document serves as both a **reference manual** and a **learning guide**. Every major screen includes:

1. **ASCII UI Diagram** -- visual layout of the screen so you know what you are looking at
2. **Field Table** -- every field, type, default, and constraint
3. **Worked Examples** -- complete configurations with all field values filled in
4. **WHY / GOTCHA annotations** -- explains the reasoning and warns about traps

Examples are **cross-referenced** across levels. The classification examples reference the definition examples by name. The rule examples reference the classification examples by name. The rule set example references the rule examples by name. The policy assignment example references the rule set by name. Reading end-to-end gives you one coherent, deployable policy suite.

---

## Screen Index

| # | Screen | Navigation | Section |
|---|--------|-----------|---------|
| 1 | Classification Page | Menu > Data Protection > Classification | [S1](#s1-classification-page) |
| 2 | Content Classification Criteria | Classification > Content Classification Criteria tab | [S2](#s2-content-classification-criteria) |
| 3 | Manual Classification | Classification > Manual Classification tab | [S3](#s3-manual-classification) |
| 4 | Register Documents | Classification > Register Documents tab | [S4](#s4-register-documents) |
| 5 | Ignored Text | Classification > Ignored Text tab | [S5](#s5-ignored-text) |
| 6 | Classification Definitions | Classification > Definitions tab | [S6](#s6-classification-definitions) |
| 7 | Advanced Pattern Definition | Definitions > Advanced Patterns > New/Edit | [S7](#s7-advanced-pattern-definition) |
| 8 | Dictionary Definition | Definitions > Dictionaries > New/Edit | [S8](#s8-dictionary-definition) |
| 9 | Document Properties Definition | Definitions > Document Properties > New/Edit | [S9](#s9-document-properties-definition) |
| 10 | File Extension Definition | Definitions > File Extensions > New/Edit | [S10](#s10-file-extension-definition) |
| 11 | True File Type Definition | Definitions > True File Type > New/Edit | [S11](#s11-true-file-type-definition) |
| 12 | DLP Policy Manager | Menu > Data Protection > DLP Policy Manager | [S12](#s12-dlp-policy-manager) |
| 13 | Policy Manager Definitions | DLP Policy Manager > Definitions tab | [S13](#s13-policy-manager-definitions) |
| 14 | End-User Groups Definition | PM Definitions > End-User Groups > New/Edit | [S14](#s14-end-user-groups-definition) |
| 15 | Email Address List Definition | PM Definitions > Email Address Lists > New/Edit | [S15](#s15-email-address-list-definition) |
| 16 | URL List Definition | PM Definitions > URL Lists > New/Edit | [S16](#s16-url-list-definition) |
| 17 | Network Definition | PM Definitions > Network Definitions > New/Edit | [S17](#s17-network-definition) |
| 18 | Network Port Definition | PM Definitions > Network Port Definitions > New/Edit | [S18](#s18-network-port-definition) |
| 19 | Network Printer Definition | PM Definitions > Network Printers > New/Edit | [S19](#s19-network-printer-definition) |
| 20 | Application Template Definition | PM Definitions > Application Templates > New/Edit | [S20](#s20-application-template-definition) |
| 21 | Rule Sets Page | DLP Policy Manager > Rule Sets tab | [S21](#s21-rule-sets-page) |
| 22 | Email Protection Rule | Rule Sets > [set] > Add Rule > Email Protection | [S22](#s22-email-protection-rule) |
| 23 | Web Protection Rule | Rule Sets > [set] > Add Rule > Web Protection | [S23](#s23-web-protection-rule) |
| 24 | Cloud Protection Rule | Rule Sets > [set] > Add Rule > Cloud Protection | [S24](#s24-cloud-protection-rule) |
| 25 | Removable Storage Protection Rule | Rule Sets > [set] > Add Rule > Removable Storage | [S25](#s25-removable-storage-protection-rule) |
| 26 | Network Share Protection Rule | Rule Sets > [set] > Add Rule > Network Share | [S26](#s26-network-share-protection-rule) |
| 27 | Network Communication Protection Rule | Rule Sets > [set] > Add Rule > Network Comm | [S27](#s27-network-communication-protection-rule) |
| 28 | Clipboard Protection Rule | Rule Sets > [set] > Add Rule > Clipboard | [S28](#s28-clipboard-protection-rule) |
| 29 | Printer Protection Rule | Rule Sets > [set] > Add Rule > Printer | [S29](#s29-printer-protection-rule) |
| 30 | Application File Access Protection Rule | Rule Sets > [set] > Add Rule > App File Access | [S30](#s30-application-file-access-protection-rule) |
| 31 | Policy Catalog - DLP Policy | Menu > Policy > Policy Catalog > DLP Policy | [S31](#s31-policy-catalog---dlp-policy) |
| 32 | Endpoint Configuration Policy | Policy Catalog > DLP Endpoint Configuration | [S32](#s32-endpoint-configuration-policy) |
| 33 | System Tree - Policy Assignment | Menu > Systems > System Tree > Assigned Policies | [S33](#s33-system-tree---policy-assignment) |
| 34 | EDM Configuration | Classification criteria > EDM condition | [S34](#s34-edm-configuration) |

---

## S1: Classification Page

**Navigation:** Menu > Data Protection > Classification
**Purpose:** Top-level container for all classification management
**Source:** [S10 doc-corpus]

### UI Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  ePO Console > Menu > Data Protection > Classification                       │
├──────────────────────────────────────────────────────────────────────────────┤
│  Actions ▼  [ New Classification ]  [ Duplicate ]  [ Delete ]  [ Import ]    │
│             [ Export ]                                                        │
├─────────────────┬────────────────────────────────────────────────────────────┤
│ Classifications │  [Content Classification Criteria]  [Manual Classification]│
│ (left sidebar)  │  [Register Documents]  [Ignored Text]  [Definitions]       │
│                 │ ─────────────────────────────────────────────────────────── │
│ ▸ PII - US SSN  │                                                            │
│ ▸ PII - US CCN  │  (Tab content area -- see screens S2 through S6)           │
│ ▸ PCI-DSS       │                                                            │
│ ▸ HIPAA         │  When a classification is selected in the left sidebar,    │
│ ▸ GDPR          │  this area shows its configuration across the 5 tabs.      │
│ ▸ Source Code   │                                                            │
│ ▸ Financial     │  When no classification is selected, this area shows       │
│   Confidential  │  a summary / empty state.                                  │
│ ▸ (custom...)   │                                                            │
│                 │                                                            │
│                 │  Status bar: "23 classifications defined"                   │
└─────────────────┴────────────────────────────────────────────────────────────┘
```

**Page Structure:**
- Tab bar with 5 sub-tabs (see screens S2-S6)
- Left sidebar: classification tree (list of all classifications)
- Actions menu: New Classification, Duplicate, Delete, Import, Export

**Page-Level Actions:**

| Action | Behavior | Evidence Grade |
|--------|----------|---------------|
| New Classification | Creates new empty classification; prompts for Name + Description | A |
| Duplicate | Copies existing classification with all criteria | A |
| Delete | Removes classification (blocked if referenced by active rules) | A |
| Import | Import classification from XML file | B |
| Export | Export classification to XML file | B |

---

## S2: Content Classification Criteria

**Navigation:** Classification > [select classification] > Content Classification Criteria tab
**Purpose:** Define rule-based content matching criteria
**Source:** [S9][S10][S54][S55 doc-corpus]

### UI Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Classification: "PCI - Payment Card Data"                                   │
│  Tab: [*Content Classification Criteria*] [Manual] [Register] [Ignored] [Def]│
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Criteria Builder                                                            │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │  Group 1                                          [AND ▼] within group│  │
│  │  ┌──────────────────────────────────────────────────────────────────┐ │  │
│  │  │ Condition: [Advanced Pattern ▼]  Pattern: [CC-Visa-MC       ▼]  │ │  │
│  │  │            Validator: Luhn 10    Threshold: [1]                  │ │  │
│  │  │            [Edit] [Remove]                                      │ │  │
│  │  └──────────────────────────────────────────────────────────────────┘ │  │
│  │  ┌──────────────────────────────────────────────────────────────────┐ │  │
│  │  │ Condition: [Proximity       ▼]  Near: [CC-Visa-MC          ▼]  │ │  │
│  │  │            Keywords: "expir,CVV,CVC,card"   Distance: [300]     │ │  │
│  │  │            [Edit] [Remove]                                      │ │  │
│  │  └──────────────────────────────────────────────────────────────────┘ │  │
│  │  [+ Add Condition to Group 1]                                        │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                              [OR] between groups                             │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │  Group 2                                          [AND ▼] within group│  │
│  │  ┌──────────────────────────────────────────────────────────────────┐ │  │
│  │  │ Condition: [Dictionary      ▼]  Dict: [Financial-Confidential▼] │ │  │
│  │  │            Score Threshold: [15]                                 │ │  │
│  │  │            [Edit] [Remove]                                      │ │  │
│  │  └──────────────────────────────────────────────────────────────────┘ │  │
│  │  [+ Add Condition to Group 2]                                        │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  [+ Add Group]                                                               │
│                                                                              │
│  Score Threshold: [0     ]   Occurrence Count: [1     ]                      │
│                                                                              │
│  [Save]  [Cancel]  [Test Classification]                                     │
└──────────────────────────────────────────────────────────────────────────────┘
```

| Field | Type | Required | Default | Options | Constraints | Evidence Grade |
|-------|------|----------|---------|---------|-------------|---------------|
| Criteria Groups | Visual builder | Yes (min 1 group) | 1 empty group | AND/OR groups | At least one condition per group | A |
| Group Logic | Toggle | Yes | ANY (OR) | ANY (OR), ALL (AND) | Logic between conditions within a group | A |
| Inter-Group Logic | Toggle | Yes | ANY (OR) | ANY (OR), ALL (AND) | Logic between groups | B |
| Condition Type | Dropdown | Yes | -- | Advanced Pattern, Dictionary, Document Properties, True File Type, File Extension, Keyword, Proximity, EDM, Content Fingerprinting | Per-condition | A |
| Score Threshold | Numeric | Conditional | 0 | Positive integer | Only when using score-based evaluation | B |
| Occurrence Count | Numeric | No | 1 | Positive integer (1+) | Minimum matches required to trigger | B |

### Examples

#### Example 1: PII Classification -- Combining Pattern + Dictionary

```yaml
classification: "PII - Personal Identifiable Information"
description: "Detects documents containing US PII via regex patterns or medical term density"
criteria:
  - group: 1
    logic: ANY         # Within group 1, ANY condition triggers
    conditions:
      - type: "Advanced Pattern"
        pattern: "US-SSN-Standard"         # Defined in S7 examples below
        threshold: 1
      - type: "Advanced Pattern"
        pattern: "US-SSN-No-Dashes"        # Second pattern for variant format
        threshold: 1
  - group: 2
    logic: ALL         # Within group 2, ALL conditions must match
    conditions:
      - type: "Dictionary"
        dictionary: "HIPAA-Medical-Terms"  # Defined in S8 examples below
        score_threshold: 10
      - type: "True File Type"
        groups: ["Documents", "Spreadsheets"]
inter_group_logic: ANY  # Group 1 OR Group 2 triggers the classification

# LOGIC: Triggers if:
#   (document has 1+ SSN with dashes OR 1+ SSN without dashes)
#   OR
#   (document has 10+ medical term score AND is a document/spreadsheet)
#
# WHY: Two independent detection strategies -- regex catches structured PII,
#   dictionary catches unstructured medical records. Using OR between groups
#   means EITHER method can trigger, maximizing detection coverage.
# WHY: Group 2 requires True File Type because medical terms in a .exe would
#   be a false positive -- we only want documents and spreadsheets.
# GOTCHA: The dictionary threshold is per-DOCUMENT, not per-match.
#   A document with "patient" appearing 10 times scores 10 (not 1).
# GOTCHA: These patterns must be created in Classification Definitions
#   (S6), NOT in Policy Manager Definitions (S13). Wrong namespace = invisible.
```

#### Example 2: PCI-DSS Classification -- Pattern + Proximity + Validator

```yaml
classification: "PCI - Payment Card Data"
description: "Detects payment card numbers with Luhn validation and contextual proximity"
criteria:
  - group: 1
    logic: ALL         # ALL conditions in group 1 must match
    conditions:
      - type: "Advanced Pattern"
        pattern: "CC-Visa-MC"              # Defined in S7 examples below
        validator: "Luhn 10"
        threshold: 1
      - type: "Proximity"
        near_pattern: "CC-Visa-MC"
        keywords: ["expir", "CVV", "CVC", "card", "visa", "mastercard"]
        distance_chars: 300
inter_group_logic: N/A  # Only one group

# LOGIC: Triggers if card number found AND card-related keywords within 300 chars.
#
# WHY: Proximity reduces false positives dramatically. A 16-digit number alone
#   could be a serial number, tracking code, or UUID. Requiring "CVV" or "expir"
#   nearby confirms it is a payment card context.
# WHY: Luhn validator rejects ~90% of random 16-digit numbers. Combined with
#   proximity, false positive rate drops below 1%.
# GOTCHA: Proximity distance is in CHARACTERS, not words. 300 chars is roughly
#   50-60 words, or about 2-3 lines of text.
# GOTCHA: Proximity keywords are NOT case-sensitive by default.
```

#### Example 3: Intellectual Property -- Source Code Detection

```yaml
classification: "Intellectual Property - Source Code"
description: "Detects source code files and code snippets in documents"
criteria:
  - group: 1
    logic: ANY
    conditions:
      - type: "True File Type"
        groups: ["Source Code", "Scripts"]
  - group: 2
    logic: ALL
    conditions:
      - type: "Dictionary"
        dictionary: "Source-Code-Keywords"  # Custom: "import", "def ", "class ", "function", "#include", "package"
        score_threshold: 20
      - type: "File Extension"
        extensions: [".py", ".js", ".go", ".java", ".cpp", ".ts", ".rs"]
inter_group_logic: ANY

# LOGIC: Triggers if file is a source code binary type, OR if a file with a code
#   extension contains 20+ code keywords.
#
# WHY: Group 1 catches renamed source files (someone renames .py to .txt).
#   True File Type detects by binary signature, ignoring the extension.
# WHY: Group 2 catches code pasted into documents -- a Word doc with 20+
#   "import" / "class" / "function" keywords is likely containing code.
# GOTCHA: Score threshold of 20 is high intentionally. Technical documentation
#   legitimately uses words like "class" and "function". High threshold reduces
#   false positives on technical writing.
# CONSTRUCTED EXAMPLE: based on common enterprise IP protection patterns.
```

---

## S3: Manual Classification

**Navigation:** Classification > Manual Classification tab
**Purpose:** Configure user-applied classification labels on endpoints
**Source:** [S49][S50][S51 doc-corpus]

| Field | Type | Required | Default | Options | Constraints | Evidence Grade |
|-------|------|----------|---------|---------|-------------|---------------|
| Enable Manual Classification | Checkbox | No | Disabled | Enabled/Disabled | Master toggle | A |
| Force Classify on Save | Checkbox | No | Disabled | Enabled/Disabled | Prompts before saving in Office apps | A |
| Force Classify on Send | Checkbox | No | Disabled | Enabled/Disabled | Prompts before sending email | A |
| Force Classify on Print | Checkbox | No | Disabled | Enabled/Disabled | Prompts before printing | A |
| Classification Labels | Editable table | Yes (if enabled) | Built-in set | Name + Color + Description per label | Labels appear in end-user context menu | A |
| Label Name | Text | Yes | (empty) | Free text | Must be unique | A |
| Label Description | Text | No | (empty) | Free text | Shown to end users | B |
| Label Color | Color picker | No | Default | Color values | Visual indicator for labels | B |
| Visual Labels (11.14.x+) | Panel | No | Disabled | Header text, Footer text, Watermark text | Visible markings on documents | A |
| Header Text | Text | No | (empty) | Free text + variables | Appears at top of every page | B |
| Footer Text | Text | No | (empty) | Free text + variables | Appears at bottom of every page | B |
| Watermark Text | Text | No | (empty) | Free text + variables | Semi-transparent overlay | B |
| Persistent Tags | Checkbox | No | Enabled | Enabled/Disabled | Metadata embedded in file properties | B |
| Embedded Tags | Checkbox | No | Enabled | Enabled/Disabled | Stored in document metadata | B |

---

## S4: Register Documents

**Navigation:** Classification > Register Documents tab
**Purpose:** Document fingerprinting for content matching (IDM)
**Source:** [S52][S53 doc-corpus]

| Field | Type | Required | Default | Options | Constraints | Evidence Grade |
|-------|------|----------|---------|---------|-------------|---------------|
| Shared Storage Location | Text (UNC/WebDAV) | Yes | (empty) | UNC path or WebDAV URL | Must be accessible from ePO server | A |
| Document Source | File browser | Yes | (empty) | File share path, folder, individual files | -- | A |
| Recurse Subfolders | Checkbox | No | Checked | Yes/No | Include subdirectories | A |
| Registration Status | Read-only | -- | -- | Registered / Pending / Failed | System-managed | B |
| Last Scan Date | Read-only | -- | -- | Datetime | System-managed | B |
| Auto Registration Schedule | Schedule picker | No | None | Cron-style schedule | Periodic re-scanning | B |
| Match Percentage Threshold | Numeric | No | 80 | 1-100 (percent) | How much of document must match | B |

---

## S5: Ignored Text

**Navigation:** Classification > Ignored Text tab
**Purpose:** Exclude boilerplate text from classification matching (reduces false positives)
**Source:** [S10 doc-corpus]

| Field | Type | Required | Default | Options | Constraints | Evidence Grade |
|-------|------|----------|---------|---------|-------------|---------------|
| Text Entries | Table | No | (empty) | Free text strings or regex patterns | Text matching these entries is ignored during classification | C |
| Import | File upload | No | N/A | Text file | Bulk import boilerplate text | C |

> **Note:** Detailed configuration for Ignored Text was not fully extractable from available documentation. The feature is referenced as a classification sub-tab but specific field layouts and options are documented in the full Interface Reference Guide PDF. Evidence Grade: C.

---

## S6: Classification Definitions

**Navigation:** Classification > Definitions tab
**Purpose:** Manage definitions scoped to classifications (separate from Policy Manager definitions)
**Source:** [S10][S23 doc-corpus]

This tab provides access to the same definition types as the Policy Manager Definitions tab (S13) but scoped to the Classification context. Definitions created here are ONLY usable within Classification criteria, not in Rule conditions.

> **GOTCHA:** This is the #2 most common admin error. Definitions exist in TWO separate namespaces. A Dictionary created under Classification Definitions is invisible when configuring Rule conditions. An Advanced Pattern created under Policy Manager Definitions is invisible in Classification criteria. Content-matching definitions (regex, dictionaries, file types) go here. Source/destination definitions (users, emails, URLs, networks, apps) go in Policy Manager Definitions (S13).

See screens S7-S11 for individual definition type fields.

---

## S7: Advanced Pattern Definition

**Navigation:** Definitions > Advanced Patterns > Actions > New Item (or Edit)
**Purpose:** Create regex-based content patterns
**Source:** [S11][S12][S13][S14][S75 doc-corpus]

### UI Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Advanced Pattern Definition                                          [X]   │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Name:              [US-SSN-Standard                                     ]  │
│                                                                              │
│  Description:       [US Social Security Numbers (XXX-XX-XXXX format)     ]  │
│                     [                                                    ]  │
│                                                                              │
│  Matched Expression (Regex):                                                 │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │ \b\d{3}-\d{2}-\d{4}\b                                                │  │
│  │                                                                        │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  Ignored Expressions:                                                        │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │ 000-\d{2}-\d{4}                                                       │  │
│  │ \d{3}-00-\d{4}                                                        │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  Validator:         [None                    ▼]                              │
│                                                                              │
│  Score:             [1     ]                                                 │
│                                                                              │
│  ○ Required   ● Optional                                                     │
│                                                                              │
│  ☐ Case Sensitive                                                            │
│                                                                              │
│  [Save]  [Cancel]  [Test]                                                    │
└──────────────────────────────────────────────────────────────────────────────┘
```

| Field | Type | Required | Default | Options | Constraints | Evidence Grade |
|-------|------|----------|---------|---------|-------------|---------------|
| Name | Text | Yes | (empty) | Free text | Must be unique within context | A |
| Description | Textarea | No | (empty) | Free text | No length limit documented | A |
| Matched Expression | Textarea (regex) | Yes | (empty) | Regular expression | RE2 engine -- no negative lookahead/lookbehind | A |
| Ignored Expressions | Textarea (regex) | No | (empty) | Regular expression(s) | Patterns to exclude from matches | A |
| Validator | Dropdown | No | None | None, Luhn 10, USPS Checksum, Custom Script | Custom requires script path | A |
| Custom Validator Script | File path | Conditional | (empty) | Path to validation script | Only if Validator = Custom | C |
| Score | Numeric | No | 1 | Positive integer | Weight for score-based classifications | A |
| Required/Optional | Radio | No | Required | Required, Optional | Required must match; Optional contributes score | B |
| Case Sensitive | Checkbox | No | Unchecked | Yes/No | When enabled, regex is case-sensitive | B |

### Examples

#### Example 1: US Social Security Number Detection

```yaml
name: "US-SSN-Standard"
regex: "\\b\\d{3}-\\d{2}-\\d{4}\\b"
ignored_expressions: |
  000-\\d{2}-\\d{4}
  \\d{3}-00-\\d{4}
  666-\\d{2}-\\d{4}
  9\\d{2}-\\d{2}-\\d{4}
case_sensitive: false
validator: "None"
score: 1
required_optional: "Required"
description: "US Social Security Numbers in XXX-XX-XXXX format"

# WHY: Standard SSN format with dashes. Threshold=1 in the classification
#   (not here -- threshold is set at the classification level in S2) because
#   a single SSN is a PII exposure.
# WHY: Ignored expressions exclude known-invalid SSN ranges:
#   - 000-xx-xxxx (SSA never issues 000 area numbers)
#   - xxx-00-xxxx (SSA never issues 00 group numbers)
#   - 666-xx-xxxx (SSA skips 666)
#   - 9xx-xx-xxxx (reserved for ITIN, not SSN)
# GOTCHA: This does NOT catch SSNs without dashes (XXXXXXXXX). You need a
#   SECOND pattern (see Example 2) for the no-dash variant.
# GOTCHA: Trellix uses the RE2 regex engine. No lookahead/lookbehind. You
#   cannot use (?!000) to exclude invalid prefixes -- use Ignored Expressions
#   instead. This is the workaround for RE2's limitations.
# GOTCHA: Validator is "None" for SSN because there is no checksum algorithm
#   for SSNs (unlike credit cards which have Luhn). Format validation via
#   Ignored Expressions is the best you can do.
```

#### Example 2: US SSN Without Dashes (Variant Format)

```yaml
name: "US-SSN-No-Dashes"
regex: "\\b\\d{9}\\b"
ignored_expressions: |
  000\\d{6}
  \\d{3}00\\d{4}
case_sensitive: false
validator: "None"
score: 1
required_optional: "Optional"
description: "US SSNs without dashes (9 consecutive digits)"

# WHY: Optional (not Required) because 9-digit numbers are very common
#   (phone numbers, ZIP+4, order numbers). This pattern generates more
#   false positives than the dashed version. Making it Optional means it
#   contributes to score but does not trigger alone.
# WHY: Pair this with the dashed pattern and a dictionary of PII keywords
#   (e.g., "social security", "SSN", "taxpayer") in a classification with
#   score threshold. The 9-digit match alone scores 1, but combined with
#   PII keywords it crosses the threshold.
# GOTCHA: This WILL match phone numbers (555123456), ZIP+4 (123456789),
#   and many other numeric strings. Never use this pattern as Required
#   with threshold=1. Always combine with proximity or dictionary context.
```

#### Example 3: Credit Card (Visa/Mastercard) with Luhn Validation

```yaml
name: "CC-Visa-MC"
regex: "\\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14})\\b"
ignored_expressions: ""
case_sensitive: false
validator: "Luhn 10"
score: 10
required_optional: "Required"
description: "Visa (4xxx) and Mastercard (51xx-55xx) with Luhn checksum validation"

# WHY: Luhn validator is CRITICAL for credit cards. Without it, any 16-digit
#   number triggers (tracking numbers, UUIDs, serial numbers). Luhn reduces
#   false positives by ~90% because it validates the check digit.
# WHY: Score=10 (high) because a valid credit card number confirmed by Luhn
#   is a very high-confidence match. In a score-threshold classification, one
#   Luhn-validated card number contributes 10 points toward the threshold.
# WHY: Required because if this pattern matches AND passes Luhn, we want
#   it to trigger the classification regardless of other conditions.
# GOTCHA: This regex uses alternation (?:...|...) which IS supported in RE2.
#   The ?: makes it a non-capturing group (also RE2-compatible).
# GOTCHA: This does NOT cover Amex (3xx), Discover (6xxx), or other card types.
#   Create separate patterns for each card network, or combine into one regex:
#   \\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\\b
```

#### Example 4: Custom Regex -- Internal Project Codes

```yaml
name: "ProjectCode-Internal"
regex: "\\bPRJ-[A-Z]{2,4}-\\d{4,6}\\b"
ignored_expressions: ""
case_sensitive: true
validator: "None"
score: 1
required_optional: "Optional"
description: "Internal project codes (PRJ-XX-NNNN to PRJ-XXXX-NNNNNN format)"

# WHY: Case sensitive because project codes are uppercase by convention.
#   Lowercase "prj-" appears in URLs and logs, which are not sensitive.
# WHY: Optional with score=1 because a single project code in a document
#   is normal (people reference projects). Only flag when MANY codes appear
#   (set threshold=5 at the classification level) suggesting a bulk export.
# CONSTRUCTED EXAMPLE: based on common enterprise naming patterns.
```

---

## S8: Dictionary Definition

**Navigation:** Definitions > Dictionaries > Actions > New Item (or Edit / Import)
**Purpose:** Create keyword/phrase collections with scoring
**Source:** [S15][S16][S17 doc-corpus]

### UI Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Dictionary Definition                                                [X]   │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Name:              [HIPAA-Medical-Terms                                 ]  │
│                                                                              │
│  Description:       [Medical and healthcare terminology for HIPAA         ]  │
│                     [compliance detection                                ]  │
│                                                                              │
│  ☐ Case Sensitive                                                            │
│                                                                              │
│  Entries:                                                                     │
│  ┌──────────────────────────────────────────┬───────┬──────────────────┐     │
│  │ Keyword / Phrase                          │ Score │ Match Mode       │     │
│  ├──────────────────────────────────────────┼───────┼──────────────────┤     │
│  │ patient                                   │   1   │ [Contains    ▼] │     │
│  │ diagnosis                                 │   2   │ [Contains    ▼] │     │
│  │ prescription                              │   2   │ [Contains    ▼] │     │
│  │ medical record                            │   5   │ [Exact Match ▼] │     │
│  │ health insurance                          │   3   │ [Contains    ▼] │     │
│  │ treatment plan                            │   5   │ [Exact Match ▼] │     │
│  │ lab results                               │   3   │ [Contains    ▼] │     │
│  │ blood type                                │   5   │ [Exact Match ▼] │     │
│  │ surgical                                  │   2   │ [Contains    ▼] │     │
│  │ prognosis                                 │   3   │ [Contains    ▼] │     │
│  ├──────────────────────────────────────────┼───────┼──────────────────┤     │
│  │ [+ Add Entry]                             │       │                  │     │
│  └──────────────────────────────────────────┴───────┴──────────────────┘     │
│                                                                              │
│  [Import from File...]    Supported: CSV (keyword,score) or TXT (one/line)   │
│                                                                              │
│  [Save]  [Cancel]                                                            │
└──────────────────────────────────────────────────────────────────────────────┘
```

| Field | Type | Required | Default | Options | Constraints | Evidence Grade |
|-------|------|----------|---------|---------|-------------|---------------|
| Name | Text | Yes | (empty) | Free text | Must be unique | A |
| Description | Textarea | No | (empty) | Free text | -- | B |
| Entries | Editable table | Yes (min 1) | (empty) | Keyword + Score per row | One entry per row | A |
| Entry: Keyword | Text | Yes | (empty) | Keyword or phrase string | -- | A |
| Entry: Score | Numeric | No | 1 | Positive integer | Weight when summing for thresholds | A |
| Entry: Match Mode | Dropdown | No | Contains | Start With, End With, Contains, Exact Match | Per-entry matching strategy | B |
| Case Sensitive | Checkbox | No | Unchecked | Yes/No | Global toggle for all entries | B |
| Import Source | File upload | No | N/A | CSV or text file | One keyword per line, or keyword,score CSV | A |

### Examples

#### Example 1: HIPAA Medical Terms

```yaml
name: "HIPAA-Medical-Terms"
description: "Medical and healthcare terminology for HIPAA compliance detection"
case_sensitive: false
entries:
  - { keyword: "patient",          score: 1, match: "Contains" }
  - { keyword: "diagnosis",        score: 2, match: "Contains" }
  - { keyword: "prescription",     score: 2, match: "Contains" }
  - { keyword: "medical record",   score: 5, match: "Exact Match" }
  - { keyword: "health insurance", score: 3, match: "Contains" }
  - { keyword: "treatment plan",   score: 5, match: "Exact Match" }
  - { keyword: "lab results",      score: 3, match: "Contains" }
  - { keyword: "blood type",       score: 5, match: "Exact Match" }
  - { keyword: "surgical",         score: 2, match: "Contains" }
  - { keyword: "prognosis",        score: 3, match: "Contains" }
  - { keyword: "PHI",              score: 5, match: "Exact Match" }
  - { keyword: "HIPAA",            score: 3, match: "Exact Match" }

# WHY: Graduated scoring -- highly specific medical phrases ("medical record",
#   "treatment plan", "blood type") score 5, while generic words ("patient",
#   "surgical") score 1-2. This prevents false positives from customer service
#   emails that casually use "patient" but triggers on actual medical records
#   that use many specific terms.
# WHY: "medical record" and "treatment plan" use Exact Match to avoid partial
#   matches like "patient medical recording" or "treatment planning session".
# WHY: Set the classification (S2) score threshold to ~10-15. A customer
#   service email with "patient" (1pt) and "diagnosis" (2pt) = 3pts -- no
#   trigger. An actual medical record with "patient" + "diagnosis" +
#   "treatment plan" + "lab results" + "blood type" = 1+2+5+3+5 = 16pts --
#   triggers.
# GOTCHA: Score threshold is evaluated per-document. A document with "patient"
#   appearing 100 times still scores 1 (not 100) for that keyword. It is
#   distinct-keyword scoring, not occurrence counting.
# GOTCHA: Built-in HIPAA dictionaries exist and are more comprehensive. Check
#   Classification > Definitions > Dictionaries for Trellix-provided lists
#   before creating custom ones. You can duplicate and extend them.
```

#### Example 2: Financial Classification Keywords

```yaml
name: "Financial-Confidential"
description: "Keywords indicating confidential financial documents"
case_sensitive: false
entries:
  - { keyword: "confidential",        score: 2, match: "Contains" }
  - { keyword: "restricted",          score: 2, match: "Contains" }
  - { keyword: "internal only",       score: 3, match: "Exact Match" }
  - { keyword: "not for distribution", score: 5, match: "Exact Match" }
  - { keyword: "proprietary",         score: 3, match: "Contains" }
  - { keyword: "trade secret",        score: 5, match: "Exact Match" }
  - { keyword: "earnings forecast",   score: 5, match: "Exact Match" }
  - { keyword: "M&A",                 score: 5, match: "Exact Match" }
  - { keyword: "acquisition target",  score: 5, match: "Exact Match" }
  - { keyword: "material nonpublic",  score: 5, match: "Contains" }
  - { keyword: "MNPI",                score: 5, match: "Exact Match" }

# WHY: Lower total threshold (score_threshold=8 in classification) because
#   these terms explicitly mark sensitive documents. "confidential" alone is
#   worth 2, but "confidential" + "earnings forecast" = 7, and with one more
#   term crosses the 8-point threshold.
# WHY: "M&A" uses Exact Match to avoid matching "M&A" inside longer strings.
#   The ampersand makes this distinctive enough that Contains would also work.
# GOTCHA: "confidential" appears in email footers everywhere (e.g., standard
#   "This email is confidential" disclaimers). Use the Ignored Text feature
#   (S5) to exclude standard email disclaimers, OR increase the threshold so
#   "confidential" alone (2pts) never triggers.
```

#### Example 3: Source Code Keywords (for IP Protection)

```yaml
name: "Source-Code-Keywords"
description: "Programming language keywords and constructs indicating source code content"
case_sensitive: true
entries:
  - { keyword: "import ",     score: 1, match: "Contains" }
  - { keyword: "#include",    score: 2, match: "Contains" }
  - { keyword: "def ",        score: 1, match: "Contains" }
  - { keyword: "class ",      score: 1, match: "Contains" }
  - { keyword: "function ",   score: 1, match: "Contains" }
  - { keyword: "package ",    score: 1, match: "Contains" }
  - { keyword: "public static", score: 3, match: "Contains" }
  - { keyword: "private void",  score: 3, match: "Contains" }
  - { keyword: "func (",      score: 2, match: "Contains" }
  - { keyword: "async fn",    score: 3, match: "Contains" }
  - { keyword: "#!/usr/bin",  score: 5, match: "Start With" }

# WHY: Case sensitive because code keywords are lowercase ("import", "class")
#   but the English words "Import" and "Class" appear in business documents
#   with title case. Case sensitivity halves false positives.
# WHY: Trailing spaces after "import ", "def ", "class ", "function " prevent
#   matching words like "important", "default", "classify", "functionality".
# WHY: Multi-word combinations like "public static" and "private void" score
#   higher because they are virtually never used outside source code.
# WHY: Shebang line (#!/usr/bin) scores 5 because it is a definitive indicator
#   of a script file. Start With match mode ensures it appears at line start.
# GOTCHA: Set the classification threshold high (20+). Technical documentation
#   legitimately uses words like "class", "function", and "import". Only a
#   document dense with these terms (actual source code) should trigger.
# CONSTRUCTED EXAMPLE: based on common programming language patterns.
```

---

## S9: Document Properties Definition

**Navigation:** Definitions > Document Properties > Actions > New Item
**Purpose:** Match file metadata (author, title, keywords, etc.)
**Source:** [S18 doc-corpus]

| Field | Type | Required | Default | Options | Constraints | Evidence Grade |
|-------|------|----------|---------|---------|-------------|---------------|
| Name | Text | Yes | (empty) | Free text | Must be unique | A |
| Property Name | Dropdown | Yes | -- | Author, Keywords/Tags, Last Saved By, Subject, Title, Custom Property | Standard document metadata | A |
| Custom Property Name | Text | Conditional | (empty) | Free text | Only if Property Name = Custom | B |
| Property Value | Text | Yes | (empty) | Free text or pattern | Value to match against | A |
| Match Operator | Dropdown | No | Contains | Is, Contains, Starts With, Ends With | -- | B |

---

## S10: File Extension Definition

**Navigation:** Definitions > File Extensions > Actions > New Item
**Purpose:** Match files by extension string
**Source:** [S18][S19 doc-corpus]

| Field | Type | Required | Default | Options | Constraints | Evidence Grade |
|-------|------|----------|---------|---------|-------------|---------------|
| Name | Text | Yes | (empty) | Free text | Must be unique | A |
| Extensions | Text / checklist | Yes | (empty) | File extension strings (e.g., .docx, .pdf, .xlsx) | One per line or comma-separated | A |
| Include/Exclude | Radio | No | Include | Include, Exclude | Match or exclude these extensions | B |

---

## S11: True File Type Definition

**Navigation:** Definitions > True File Type > Actions > New Item
**Purpose:** Match files by binary signature (magic bytes), regardless of extension
**Source:** [S20 doc-corpus]

| Field | Type | Required | Default | Options | Constraints | Evidence Grade |
|-------|------|----------|---------|---------|-------------|---------------|
| Name | Text | Yes | (empty) | Free text | Must be unique | A |
| File Type Groups | Checklist | Yes | (none selected) | Documents, Spreadsheets, Presentations, Images, Archives, Executables, Audio, Video, Database, Source Code, Scripts, CAD, Email, etc. | Select one or more groups | A |
| Individual Types (within group) | Checklist | No | All in group | Individual file types per group | Fine-grained within selected groups | B |

---

## S12: DLP Policy Manager

**Navigation:** Menu > Data Protection > DLP Policy Manager
**Purpose:** Top-level management page for definitions, rule sets, and rules
**Source:** [S23 doc-corpus]

### UI Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  ePO Console > Menu > Data Protection > DLP Policy Manager                   │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  [*Definitions*]  [Rule Sets]                                                │
│                                                                              │
│  ┌──────────────────┬───────────────────────────────────────────────────────┐│
│  │ Definition Types  │  End-User Groups                                     ││
│  │ (left tree)       │ ─────────────────────────────────────────────────── ││
│  │                   │                                                      ││
│  │ ▸ End-User Groups │  Actions ▼  [New Item]  [Edit]  [Duplicate]  [Delete]││
│  │ ▸ Email Address   │                                                      ││
│  │   Lists           │  ┌────────────────┬──────────┬────────────────────┐ ││
│  │ ▸ URL Lists       │  │ Name           │ Type     │ Description        │ ││
│  │ ▸ Network         │  ├────────────────┼──────────┼────────────────────┤ ││
│  │   Definitions     │  │ All Users      │ AD Group │ All domain users   │ ││
│  │ ▸ Network Port    │  │ Finance-Team   │ AD Group │ Finance department │ ││
│  │   Definitions     │  │ Executives     │ AD Group │ C-suite + VPs      │ ││
│  │ ▸ Network Printers│  │ Contractors    │ AD Group │ External vendors   │ ││
│  │ ▸ Application     │  └────────────────┴──────────┴────────────────────┘ ││
│  │   Templates       │                                                      ││
│  └──────────────────┴───────────────────────────────────────────────────────┘│
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Page Structure:**
- Tab bar: Definitions | Rule Sets
- This is the entry point for all policy authoring except classifications

---

## S13: Policy Manager Definitions

**Navigation:** DLP Policy Manager > Definitions tab
**Purpose:** Manage definitions used in Rule conditions (source/destination)
**Source:** [S23][S24 doc-corpus]

**Definition categories listed in left tree:**
- Source/Destination: End-User Groups, Email Address Lists, URL Lists, Network Definitions, Network Port Definitions, Network Printers, Application Templates
- Content: (overlap with Classification Definitions but managed separately)

> **GOTCHA:** These definitions are for RULES, not for Classifications. If you create a Dictionary here, it will NOT appear in Classification criteria. Content-matching definitions belong in Classification > Definitions (S6). Source/destination definitions belong here. Some types (Advanced Patterns, Dictionaries) exist in BOTH contexts and must be created in the correct one.

See screens S14-S20 for individual definition type fields.

---

## S14: End-User Groups Definition

**Navigation:** DLP Policy Manager > Definitions > End-User Groups > New/Edit
**Purpose:** Define user/group scope for rules (via Active Directory)
**Source:** [S23][S73 doc-corpus]

| Field | Type | Required | Default | Options | Constraints | Evidence Grade |
|-------|------|----------|---------|---------|-------------|---------------|
| Name | Text | Yes | (empty) | Free text | Must be unique | A |
| Description | Textarea | No | (empty) | Free text | -- | B |
| Source Type | Selection | Yes | AD Groups | AD Groups, Individual Users, Both | -- | A |
| AD Group Selection | Tree browser | Conditional | (none) | Browse/search LDAP directories | Requires registered LDAP server in ePO | A |
| Individual User: SID | Text | Conditional | (empty) | Windows SID string | If Source Type includes Individual Users | B |
| Individual User: Domain\Username | Text | Conditional | (empty) | DOMAIN\username format | Alternative to SID | B |

### Examples

#### Example 1: Finance Department User Group

```yaml
name: "Finance-Team"
description: "All users in the Finance department OU for PCI/SOX rule scoping"
source_type: "AD Groups"
ad_groups:
  - "CN=Finance,OU=Departments,DC=corp,DC=example,DC=com"
  - "CN=Accounting,OU=Departments,DC=corp,DC=example,DC=com"

# WHY: Separating Finance from "All Users" allows rules to have different
#   reactions per department. Finance gets Block for PCI data; Engineering
#   gets Monitor-only during rollout.
# GOTCHA: "All Users" must exist as an End-User Group BEFORE creating rules
#   that reference it. The ePO console does not auto-create this group.
# GOTCHA: Requires a registered LDAP server in ePO. Without LDAP, the AD
#   Group tree browser shows nothing and you can only add users by SID.
# GOTCHA: DLP policies are assigned to SYSTEMS, not users. This End-User
#   Group is used within individual rules to scope by user. A Finance user
#   on a shared laptop in another department's System Tree group will only
#   be covered if the laptop also has the DLP policy assigned.
```

#### Example 2: Executive Leadership (High-Sensitivity)

```yaml
name: "Executives"
description: "C-suite and VPs -- exempt from user notification but monitored"
source_type: "Both"
ad_groups:
  - "CN=C-Suite,OU=Leadership,DC=corp,DC=example,DC=com"
individual_users:
  - "CORP\\jsmith"    # CEO (backup entry in case AD group changes)

# WHY: "Both" source type provides redundancy. AD group membership is
#   authoritative, but individual SID entries survive AD group restructuring.
# WHY: Executives are a separate group because rules targeting them often
#   use Monitor (not Block) to avoid disrupting C-suite workflows, while
#   still capturing incidents for compliance.
```

---

## S15: Email Address List Definition

**Navigation:** DLP Policy Manager > Definitions > Email Address Lists > New/Edit
**Purpose:** Define email address lists for rule sender/recipient conditions
**Source:** [S23][S43 doc-corpus]

| Field | Type | Required | Default | Options | Constraints | Evidence Grade |
|-------|------|----------|---------|---------|-------------|---------------|
| Name | Text | Yes | (empty) | Free text | Must be unique | A |
| Description | Textarea | No | (empty) | Free text | -- | B |
| Email Addresses | Table / textarea | Yes (min 1) | (empty) | Email addresses, domain wildcards (*@example.com) | One per line | A |
| Import | File upload | No | N/A | CSV file | Bulk import; also via dlp.importDefinitions API | A |

### Examples

#### Example 1: External Recipients (Non-Company Domains)

```yaml
name: "External-Recipients"
description: "All email domains outside the company -- used as recipient filter"
addresses:
  - "*"                    # Match ALL recipients...
exclude:
  - "*@example.com"        # ...except internal domains
  - "*@example.co.uk"
  - "*@subsidiary.com"

# WHY: Inverting the logic (match all, exclude internal) is easier to maintain
#   than listing every possible external domain. New internal domains are rare;
#   new external domains are infinite.
# GOTCHA: The wildcard syntax and exclude behavior depends on how the rule
#   references this list. Check whether your rule uses "is in list" or "is
#   NOT in list" condition. You may need to create an "Internal-Recipients"
#   list instead and use "is NOT in" logic in the rule.
# GOTCHA: Email address lists can be updated via the dlp.importDefinitions
#   API, making them one of the few automatable definition types.
```

---

## S16: URL List Definition

**Navigation:** DLP Policy Manager > Definitions > URL Lists > New/Edit
**Purpose:** Define URL lists for web/cloud rule conditions
**Source:** [S23][S74 doc-corpus]

| Field | Type | Required | Default | Options | Constraints | Evidence Grade |
|-------|------|----------|---------|---------|-------------|---------------|
| Name | Text | Yes | (empty) | Free text | Must be unique | A |
| Description | Textarea | No | (empty) | Free text | -- | B |
| URLs | Table / textarea | Yes (min 1) | (empty) | Full URLs or URL patterns with wildcards | One per line | A |
| Import | File upload | No | N/A | CSV file | Bulk import; also via dlp.importDefinitions API | A |

### Examples

#### Example 1: Code Sharing Sites

```yaml
name: "Code-Sharing-Sites"
description: "Public code repositories and paste sites -- monitor for source code upload"
urls:
  - "github.com/*"
  - "gitlab.com/*"
  - "bitbucket.org/*"
  - "pastebin.com/*"
  - "gist.github.com/*"
  - "codepen.io/*"
  - "jsfiddle.net/*"
  - "replit.com/*"
  - "stackblitz.com/*"

# WHY: Used in Web Protection rules (S23) to detect source code uploads to
#   public repositories. Combined with "Intellectual Property - Source Code"
#   classification for targeted detection.
# GOTCHA: URL lists must be maintained -- new code sharing sites appear
#   frequently. Review and update quarterly.
# GOTCHA: URL lists can be updated via dlp.importDefinitions API, so you
#   can automate updates from a threat intelligence feed.
# GOTCHA: URL lists are supported by Web Protection, Cloud Protection,
#   Clipboard Protection, and Printer Protection rules. They are NOT
#   supported by Network Communication or Removable Storage rules.
```

#### Example 2: AI Chat Services

```yaml
name: "AI-Chat-Services"
description: "AI assistant web interfaces -- monitor for data leakage via prompts"
urls:
  - "chat.openai.com/*"
  - "chatgpt.com/*"
  - "claude.ai/*"
  - "bard.google.com/*"
  - "gemini.google.com/*"
  - "copilot.microsoft.com/*"
  - "poe.com/*"
  - "perplexity.ai/*"

# WHY: AI webchats are a modern data loss vector (DLP Endpoint Complete 2025
#   added explicit support). Users paste confidential data into prompts.
# WHY: Monitor-only initially -- blocking AI tools outright causes shadow IT
#   workarounds. Understand usage patterns first, then create targeted rules.
# GOTCHA: Trellix DLP 11.12.x+ supports Edge Connector and Chrome Enterprise
#   integration for better HTTPS inspection. Older versions may not inspect
#   HTTPS traffic to these sites without explicit proxy configuration.
# CONSTRUCTED EXAMPLE: based on 2025 AI landscape.
```

---

## S17: Network Definition

**Navigation:** DLP Policy Manager > Definitions > Network Definitions > New/Edit
**Purpose:** Define network addresses for network communication rules
**Source:** [S23 doc-corpus]

| Field | Type | Required | Default | Options | Constraints | Evidence Grade |
|-------|------|----------|---------|---------|-------------|---------------|
| Name | Text | Yes | (empty) | Free text | Must be unique | B |
| Description | Textarea | No | (empty) | Free text | -- | B |
| Address Type | Dropdown | Yes | IP Address | IP Address, IP Range, Subnet (mask), CIDR | -- | B |
| Address Value | Text | Yes | (empty) | Valid IP / range / subnet / CIDR notation | Standard network notation | B |

---

## S18: Network Port Definition

**Navigation:** DLP Policy Manager > Definitions > Network Port Definitions > New/Edit
**Purpose:** Define port numbers/ranges for network communication rules
**Source:** [S23 doc-corpus]

| Field | Type | Required | Default | Options | Constraints | Evidence Grade |
|-------|------|----------|---------|---------|-------------|---------------|
| Name | Text | Yes | (empty) | Free text | Must be unique | C |
| Port(s) | Text / numeric | Yes | (empty) | Port number or range (e.g., 80, 443, 8000-9000) | Valid TCP/UDP port range (1-65535) | C |

> **Note:** Detailed field layout not fully captured in available documentation. Evidence Grade: C.

---

## S19: Network Printer Definition

**Navigation:** DLP Policy Manager > Definitions > Network Printers > New/Edit
**Purpose:** Define network printers for printer protection rules
**Source:** [S58 doc-corpus]

| Field | Type | Required | Default | Options | Constraints | Evidence Grade |
|-------|------|----------|---------|---------|-------------|---------------|
| Name | Text | Yes | (empty) | Free text | Must be unique | A |
| UNC Path | Text | Conditional | (empty) | UNC path (\\server\printer) | One of UNC or IP required | A |
| IP Address | Text | Conditional | (empty) | IPv4 address | One of UNC or IP required | A |

---

## S20: Application Template Definition

**Navigation:** DLP Policy Manager > Definitions > Application Templates > New/Edit
**Purpose:** Identify applications for rule scoping and application strategy
**Source:** [S21][S22 doc-corpus]

| Field | Type | Required | Default | Options | Constraints | Evidence Grade |
|-------|------|----------|---------|---------|-------------|---------------|
| Name | Text | Yes | (empty) | Free text | Must be unique | A |
| Description | Textarea | No | (empty) | Free text | -- | B |
| Operating System | Dropdown | Yes | Windows | Windows, macOS | -- | A |
| Product Name | Text | No | (empty) | From file properties metadata | Partial match supported | A |
| Vendor Name | Text | No | (empty) | From file properties metadata | Partial match supported | A |
| Executable File Name | Text | No | (empty) | Exact or wildcard (e.g., chrome.exe, firefox*) | -- | A |
| Window Title | Text | No | (empty) | Contains or equals string | Matched against window title bar | A |
| SHA-256 Hash | Text | No | (empty) | 64-character hex string | Most specific identification | B |
| Strategy | Dropdown | Yes | Monitored | Trusted, Monitored, Blocked | Default DLP behavior for app | A |

---

## S21: Rule Sets Page

**Navigation:** DLP Policy Manager > Rule Sets tab
**Purpose:** Create, manage, and organize containers of data protection rules
**Source:** [S25][S27 doc-corpus]

### UI Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  ePO Console > Data Protection > DLP Policy Manager                          │
├──────────────────────────────────────────────────────────────────────────────┤
│  [Definitions]  [*Rule Sets*]                                                │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Actions ▼  [New Rule Set]  [Duplicate]  [Delete]  [Import]  [Export]        │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐    │
│  │ Rule Set Name              │ State   │ Rules │ Description          │    │
│  ├────────────────────────────┼─────────┼───────┼──────────────────────┤    │
│  │ ▸ PCI-DSS-Compliance-v1   │ Enabled │  5    │ PCI card data across │    │
│  │                            │         │       │ all channels         │    │
│  │ ▸ HIPAA-Compliance-v1     │ Enabled │  4    │ Medical data         │    │
│  │                            │         │       │ protection           │    │
│  │ ▸ IP-Protection-v1        │ Enabled │  3    │ Source code and      │    │
│  │                            │         │       │ trade secrets        │    │
│  │ ▸ USB-Device-Control      │ Enabled │  2    │ Removable storage    │    │
│  │                            │         │       │ restrictions         │    │
│  └────────────────────────────┴─────────┴───────┴──────────────────────┘    │
│                                                                              │
│  Click a rule set name to expand and see its rules.                          │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Page-Level Actions:**

| Action | Behavior | Evidence Grade |
|--------|----------|---------------|
| New Rule Set | Creates empty rule set; prompts for Name + Description | A |
| Duplicate | Copies rule set with all contained rules | A |
| Delete | Removes rule set (warns if assigned to active policy) | A |
| Import | Import from XML/JSON export | B |
| Export | Export rule set configuration | B |

**Per-Rule-Set Fields:**

| Field | Type | Required | Default | Options | Constraints | Evidence Grade |
|-------|------|----------|---------|---------|-------------|---------------|
| Name | Text | Yes | (empty) | Free text | Must be unique | A |
| Description | Textarea | No | (empty) | Free text | -- | A |
| State | Toggle | Yes | Enabled | Enabled / Disabled | Can disable entire set | A |
| Rules | Ordered list | No | (empty) | Data protection rules | Evaluated in order shown | A |

### Examples

#### Example 1: PCI Compliance Rule Set

```yaml
rule_set: "PCI-DSS-Compliance-v1"
description: "Protects payment card data across all channels"
state: "Enabled"
rules:
  - "Email-PCI-CreditCard-Block-v1"         # Email Protection (S22 example)
  - "Web-PCI-CreditCard-Monitor-v1"         # Web Protection (S23 example)
  - "USB-PCI-CreditCard-Block-v1"           # Removable Storage Protection
  - "Print-PCI-CreditCard-Block-v1"         # Printer Protection
  - "Clipboard-PCI-CreditCard-Block-v1"     # Clipboard Protection

# WHY: Multiple rules per rule set -- one per channel. PCI data must be
#   protected EVERYWHERE it can leak. Missing even one channel leaves a gap.
# WHY: Web is Monitor-only initially to avoid blocking legitimate payment
#   processing pages. After 2 weeks of monitoring, promote to Block.
# WHY: Rules are evaluated in the order listed. Place Block rules above
#   Monitor rules so the most restrictive action wins.
# DEPLOYMENT: Start with Email + USB blocking (highest risk channels),
#   add others after a 2-week monitoring period. This follows the phased
#   deployment strategy recommended by Trellix Professional Services.
# GOTCHA: Rule evaluation order matters. If two rules match the same data,
#   both trigger (cumulative), and the most restrictive action is applied.
#   Place higher-severity rules first.
# NAMING: Follows Jay Appell's naming convention:
#   [Channel]-[Compliance]-[DataType]-[Action]-[Version]
```

#### Example 2: Intellectual Property Protection Rule Set

```yaml
rule_set: "IP-Protection-v1"
description: "Protects source code, trade secrets, and proprietary documents"
state: "Enabled"
rules:
  - "Web-IP-SourceCode-Monitor-v1"           # Monitor uploads to code sharing sites
  - "Cloud-IP-SourceCode-Block-v1"           # Block sync to personal cloud storage
  - "Email-IP-TradeSecret-Justify-v1"        # Require justification for emailing

# WHY: Three channels, three different reactions reflecting risk level:
#   - Web: Monitor-only (need to understand developer behavior first)
#   - Cloud: Block (personal Dropbox/Drive is never legitimate for source code)
#   - Email: Request Justification (may be legitimate sharing with partners)
# WHY: No USB/Clipboard/Printer rules yet -- engineering teams use USB for
#   hardware development. Add those rules after the monitoring phase.
```

---

## S22: Email Protection Rule

**Navigation:** Rule Sets > [set] > Actions > New Rule > Email Protection
**Purpose:** Protect email channel (Outlook, SMTP)
**Source:** [S30][S57 doc-corpus]

### UI Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Email Protection Rule                                                       │
├──────────────────────────────────────────────────────────────────────────────┤
│  [*Condition*]  [Reaction]  [General]                                        │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Classification:    [PCI - Payment Card Data              ▼] [+ Add]         │
│                     [PII - Personal Identifiable Info      ] [Remove]         │
│                                                                              │
│  ── Sender ──────────────────────────────────────────────────────────────    │
│  End-User Group:    [Finance-Team                         ▼] [+ Add]         │
│  Email Address:     [Any                                  ▼]                 │
│                                                                              │
│  ── Recipient ───────────────────────────────────────────────────────────    │
│  To:                [External-Recipients                  ▼] [+ Add]         │
│  CC:                [Any                                  ▼]                 │
│  BCC:               [Any                                  ▼]                 │
│  Domain:            [                                     ]                  │
│  Min Recipients:    [   ]   Max Recipients: [   ]                            │
│                                                                              │
│  ── Scan Scope ──────────────────────────────────────────────────────────    │
│  ☑ Envelope   ☑ Header   ☑ Body   ☑ Attachments                            │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Condition Tab

| Field | Type | Required | Default | Options | Constraints | Evidence Grade |
|-------|------|----------|---------|---------|-------------|---------------|
| Classification | Multi-select | Yes | (none) | Available classifications | At least one required | A |
| Sender | Multi-select | No | Any | End-User Groups, Email Address Lists | Source filter | A |
| Recipient (To) | Multi-select | No | Any | Email Address Lists | Destination filter | A |
| Recipient (CC) | Multi-select | No | Any | Email Address Lists | CC filter | B |
| Recipient (BCC) | Multi-select | No | Any | Email Address Lists | BCC filter | B |
| Recipient Domain | Text / list | No | Any | Domain patterns | Domain-level filtering | B |
| Recipient Threshold (Min) | Numeric | No | None | Positive integer | Min recipients to trigger | B |
| Recipient Threshold (Max) | Numeric | No | None | Positive integer | Max recipients to trigger | B |
| Scan: Envelope | Checkbox | No | Checked | Yes/No | Scan email envelope | A |
| Scan: Header | Checkbox | No | Checked | Yes/No | Scan email headers | A |
| Scan: Body | Checkbox | No | Checked | Yes/No | Scan email body content | A |
| Scan: Attachments | Checkbox | No | Checked | Yes/No | Scan attachment content | A |
| End-User | Multi-select | No | All | End-User Group definitions | User scope filter | A |

### Reaction Tab

| Field | Type | Required | Default | Options | Constraints | Evidence Grade |
|-------|------|----------|---------|---------|-------------|---------------|
| Action | Dropdown | Yes | No Action | No Action, Monitor, Block, Encrypt, Quarantine*, Request Justification, Apply RM Policy, Redirect* | *Network Prevent only | A |
| Notify User | Checkbox + text | No | Disabled | Enabled/Disabled + message text | Custom popup to end user | A |
| Report to ePO | Checkbox | No | Checked | Yes/No | Generate incident | A |
| Store Original Evidence | Checkbox | No | Unchecked | Yes/No | Capture triggering data | A |
| Severity | Dropdown | Yes | Medium | Critical, High, Medium, Low, Informational | Incident severity | A |

### General Tab

| Field | Type | Required | Default | Options | Constraints | Evidence Grade |
|-------|------|----------|---------|---------|-------------|---------------|
| Rule Name | Text | Yes | (empty) | Free text | Unique within rule set | A |
| Description | Textarea | No | (empty) | Free text | -- | B |
| State | Toggle | Yes | Enabled | Enabled / Disabled | Rule active/inactive | A |

### Examples

#### Example 1: Block PCI Data via Email

```yaml
rule_name: "Email-PCI-CreditCard-Block-v1"
rule_type: "Email Protection"
state: "Enabled"

# -- Condition Tab --
classification: "PCI - Payment Card Data"         # References S2 Example 2
end_user_group: "All Users"
sender_email: "Any"
recipient_to: "External-Recipients"                # References S15 Example 1
recipient_cc: "Any"
recipient_bcc: "Any"
scan_envelope: true
scan_header: true
scan_body: true
scan_attachments: true

# -- Reaction Tab --
action: "Block"
severity: "Critical"
notify_user: true
notification_text: |
  BLOCKED: This email contains payment card data (credit card numbers)
  and cannot be sent to external recipients.

  If you need to send payment data securely, use the company's encrypted
  file transfer portal at https://secure.example.com or contact
  security@example.com for assistance.
report_to_epo: true
store_evidence: true

# WHY: Block (not Monitor) because sending PCI data via unencrypted email is
#   a PCI-DSS compliance violation that can result in fines.
# WHY: Only triggers for External-Recipients -- internal email between Finance
#   team members is allowed (internal email stays within the corporate network).
# WHY: User notification explains the block AND gives a remediation path
#   (encrypted file transfer portal). Users who see "blocked" with no alternative
#   will try to work around DLP, which is worse.
# WHY: Store evidence = true because PCI compliance audits require proof that
#   violations were detected and blocked.
# GOTCHA: "All Users" End-User Group must exist in Policy Manager > Definitions
#   > End-User Groups BEFORE creating this rule. If it does not exist, the
#   dropdown will be empty and the rule will have no user scope.
# GOTCHA: This rule triggers on BOTH DLP Endpoint (Outlook plugin) and DLP
#   Prevent (SMTP gateway) if both are deployed. The same policy applies to
#   both, which is a feature (defense in depth) not a bug.
```

#### Example 2: Monitor PII in Email (Pre-Enforcement Phase)

```yaml
rule_name: "Email-PII-SSN-Monitor-v1"
rule_type: "Email Protection"
state: "Enabled"

# -- Condition Tab --
classification: "PII - Personal Identifiable Information"  # References S2 Example 1
end_user_group: "All Users"
recipient_to: "Any"                             # Monitor ALL recipients (internal + external)
scan_body: true
scan_attachments: true

# -- Reaction Tab --
action: "Monitor"
severity: "High"
notify_user: false                              # Silent monitoring
report_to_epo: true
store_evidence: true

# WHY: Monitor (not Block) during the initial deployment phase. This follows
#   the phased deployment strategy from Trellix Professional Services:
#   Phase 1 = Monitor for 2-4 weeks to build a baseline.
#   Phase 2 = Switch to Request Justification for high-confidence rules.
#   Phase 3 = Switch to Block after validating low false positive rates.
# WHY: No user notification -- silent monitoring captures the TRUE baseline
#   of PII sharing behavior. If users know they are being monitored, their
#   behavior changes and you get a skewed baseline.
# WHY: Monitor ALL recipients (not just external) to understand internal PII
#   sharing patterns too. You may discover that HR sends SSNs to payroll
#   internally -- that is a legitimate workflow you need to whitelist before
#   switching to Block mode.
# GOTCHA: After the monitoring period, review incidents in DLP Incident Manager.
#   Expect 50-100 false positives in the first week. Tune thresholds and Ignored
#   Text entries before enabling Block.
```

#### Example 3: Require Justification for Trade Secrets via Email

```yaml
rule_name: "Email-IP-TradeSecret-Justify-v1"
rule_type: "Email Protection"
state: "Enabled"

# -- Condition Tab --
classification: "Intellectual Property - Source Code"    # References S2 Example 3
end_user_group: "All Users"
recipient_to: "External-Recipients"

# -- Reaction Tab --
action: "Request Justification"
severity: "High"
notify_user: true
notification_text: |
  This email appears to contain source code or proprietary information.
  Please provide a business justification for sending this externally.

  Select a reason:
  - Partner collaboration (approved NDA on file)
  - Open source contribution (approved project)
  - Other (describe in text box)
report_to_epo: true
store_evidence: true

# WHY: Request Justification is the middle ground between Monitor and Block.
#   It stops the email until the user provides a reason, then lets it through.
#   The justification is stored in the incident record for audit purposes.
# WHY: Useful for IP protection because there ARE legitimate reasons to send
#   source code externally (partner integrations, open source contributions).
#   Blocking outright disrupts engineering workflows; justification adds
#   accountability without blocking.
# GOTCHA: Users can type ANY justification and the email will be sent. This is
#   a deterrent and audit trail, not a hard block. If you need hard enforcement,
#   use Block with an exception process instead.
```

---

## S23: Web Protection Rule

**Navigation:** Rule Sets > [set] > Actions > New Rule > Web Protection
**Source:** [S38 doc-corpus]

### Condition Tab

| Field | Type | Required | Default | Options | Constraints | Evidence Grade |
|-------|------|----------|---------|---------|-------------|---------------|
| Classification | Multi-select | Yes | (none) | Available classifications | At least one required | A |
| URL List | Multi-select | No | Any | URL List definitions | Destination URL filter | A |
| HTTP Method | Multi-select | No | POST | POST, PUT, PATCH, others | Which methods to inspect | B |
| End-User | Multi-select | No | All | End-User Group definitions | User scope | A |
| Application | Multi-select | No | All browsers | Application Template definitions | Browser/app filter | B |

### Reaction Tab

Same structure as Email Protection Rule (S22) except: Encrypt, Quarantine, Apply RM Policy, and Redirect are NOT available.

### General Tab

Same structure as Email Protection Rule (S22).

### Examples

#### Example 1: Monitor Source Code Upload to Code-Sharing Sites

```yaml
rule_name: "Web-IP-SourceCode-Monitor-v1"
rule_type: "Web Protection"
state: "Enabled"

# -- Condition Tab --
classification: "Intellectual Property - Source Code"
url_list: "Code-Sharing-Sites"              # References S16 Example 1
http_method: ["POST", "PUT", "PATCH"]       # Upload methods only
end_user: "All Users"

# -- Reaction Tab --
action: "Monitor"
severity: "High"
notify_user: false
report_to_epo: true
store_evidence: true

# WHY: Monitor (not Block) during initial deployment to build a baseline of
#   developer behavior. Many developers legitimately use GitHub for open-source
#   contributions. Blocking immediately would disrupt workflows.
# WHY: Only POST/PUT/PATCH methods -- these are upload operations. GET requests
#   (browsing GitHub, reading docs) should not be inspected.
# WHY: No user notification during Monitor phase to capture true behavior.
# GOTCHA: URL list "Code-Sharing-Sites" must be created in Policy Manager
#   Definitions (S16) BEFORE creating this rule.
# GOTCHA: HTTPS inspection requires proper certificate deployment or browser
#   extension (Edge Connector 11.12.x+, Chrome Enterprise integration).
#   Without it, the DLP agent cannot inspect encrypted web traffic content.
```

#### Example 2: Monitor Data Pasted into AI Chatbots

```yaml
rule_name: "Web-AI-DataLeakage-Monitor-v1"
rule_type: "Web Protection"
state: "Enabled"

# -- Condition Tab --
classification: "PCI - Payment Card Data"
url_list: "AI-Chat-Services"                # References S16 Example 2
http_method: ["POST"]                        # Chat submissions are POSTs
end_user: "All Users"

# -- Reaction Tab --
action: "Monitor"
severity: "High"
notify_user: false
store_evidence: true

# WHY: AI chatbots are a growing data loss vector. Users paste sensitive data
#   into prompts without realizing it leaves the corporate boundary.
# WHY: Monitor-only because blocking AI tools causes shadow IT -- users will
#   find unmonitored alternatives. Better to understand and educate first.
# GOTCHA: Trellix DLP Endpoint Complete (2025) explicitly supports AI webchat
#   protection. Older versions may not detect these sites properly.
# CONSTRUCTED EXAMPLE: based on 2025 threat landscape and Trellix RSAC 2025.
```

---

## S24: Cloud Protection Rule

**Navigation:** Rule Sets > [set] > Actions > New Rule > Cloud Protection
**Source:** [S36 doc-corpus]

### Condition Tab

| Field | Type | Required | Default | Options | Constraints | Evidence Grade |
|-------|------|----------|---------|---------|-------------|---------------|
| Classification | Multi-select | Yes | (none) | Available classifications | At least one required | A |
| Cloud Service | Multi-select | Yes | (none) | OneDrive, Dropbox, Google Drive, Box, iCloud, others | Target cloud apps | A |
| Operation | Multi-select | No | All | Upload, Download, Sync | Which operations to inspect | B |
| End-User | Multi-select | No | All | End-User Group definitions | User scope | A |

### Reaction Tab

Same structure as Web Protection Rule (S23). Encrypt, Quarantine, Apply RM Policy, and Redirect are NOT available.

### General Tab

Same structure as Email Protection Rule (S22).

### Examples

#### Example 1: Block Source Code Sync to Personal Cloud Storage

```yaml
rule_name: "Cloud-IP-SourceCode-Block-v1"
rule_type: "Cloud Protection"
state: "Enabled"

# -- Condition Tab --
classification: "Intellectual Property - Source Code"
cloud_service: ["Dropbox", "Google Drive", "iCloud", "Box"]  # Personal cloud
operation: ["Upload", "Sync"]
end_user: "All Users"

# -- Reaction Tab --
action: "Block"
severity: "Critical"
notify_user: true
notification_text: |
  BLOCKED: Source code cannot be synced to personal cloud storage.
  Use the corporate OneDrive or approved Git repositories instead.
store_evidence: true

# WHY: Block (not Monitor) because syncing source code to personal Dropbox
#   is never a legitimate workflow. There is no valid business reason.
# WHY: OneDrive is excluded from the cloud service list because it is the
#   corporate-approved cloud storage (managed by IT).
# WHY: Only Upload and Sync operations -- Download is excluded because
#   downloading from personal cloud to a corporate laptop is less risky
#   (the data is coming IN, not going OUT).
# GOTCHA: Cloud Protection requires the DLP agent to detect cloud sync
#   client applications. If a user installs a non-standard cloud client,
#   it may not be detected. Supplement with Web Protection rules.
```

---

## S25: Removable Storage Protection Rule

**Navigation:** Rule Sets > [set] > Actions > New Rule > Removable Storage Protection
**Source:** [S31 doc-corpus]

### Condition Tab

| Field | Type | Required | Default | Options | Constraints | Evidence Grade |
|-------|------|----------|---------|---------|-------------|---------------|
| Classification | Multi-select | Yes | (none) | Available classifications | At least one required | A |
| Device Type | Multi-select | No | All removable | USB Drive, CD/DVD, Bluetooth, SD Card, FireWire, etc. | Target device types | A |
| End-User | Multi-select | No | All | End-User Group definitions | User scope | A |
| File Conditions: True File Type | Multi-select | No | Any | True File Type groups | Binary type filter | B |
| File Conditions: Extension | Multi-select | No | Any | File Extension definitions | Extension filter | B |
| File Conditions: Size | Numeric range | No | Any | Min/Max file size (KB/MB/GB) | Size filter | B |

### Reaction Tab

Same structure as Email Protection Rule (S22) except: Quarantine and Redirect are NOT available. Encrypt and Apply RM Policy ARE available.

### General Tab

Same structure as Email Protection Rule (S22).

### Examples

#### Example 1: Block PCI Data to USB Drives

```yaml
rule_name: "USB-PCI-CreditCard-Block-v1"
rule_type: "Removable Storage Protection"
state: "Enabled"

# -- Condition Tab --
classification: "PCI - Payment Card Data"
device_type: ["USB Drive"]                   # ONLY USB drives, not all removable
end_user: "All Users"

# -- Reaction Tab --
action: "Block"
severity: "Critical"
notify_user: true
notification_text: |
  BLOCKED: Files containing payment card data cannot be copied to USB drives.
  Contact IT Security for approved data transfer methods.
store_evidence: true

# WHY: Block only USB Drive, not all removable devices. Scoping to USB Drive
#   prevents blocking USB keyboards, mice, and other HID devices.
# GOTCHA: A "Block ALL" Removable Storage rule without device-type scoping
#   WILL block USB keyboards and mice, making endpoints unusable. This is
#   the #6 gotcha from the gotchas document. ALWAYS scope to specific device
#   types and ALWAYS deploy in Monitor mode first.
# GOTCHA: Deploy in Monitor mode for 1-2 weeks first, then review incidents
#   to see what devices are being detected, then switch to Block. This is
#   the phased deployment approach from DLP 001/002 (Jay Appell).
```

---

## S26: Network Share Protection Rule

**Navigation:** Rule Sets > [set] > Actions > New Rule > Network Share Protection
**Source:** [S35 doc-corpus]

### Condition Tab

| Field | Type | Required | Default | Options | Constraints | Evidence Grade |
|-------|------|----------|---------|---------|-------------|---------------|
| Classification | Multi-select | Yes | (none) | Available classifications | At least one required | A |
| Network Share Path | Multi-select | No | Any | Network Definitions (UNC paths) | Target share paths | A |
| End-User | Multi-select | No | All | End-User Group definitions | User scope | B |

### Reaction Tab

Same structure as Web Protection Rule (S23). Only Monitor, Block, Request Justification, Notify User, No Action, Store Original File.

### General Tab

Same structure as Email Protection Rule (S22).

---

## S27: Network Communication Protection Rule

**Navigation:** Rule Sets > [set] > Actions > New Rule > Network Communication Protection
**Source:** [S32 doc-corpus]

### Condition Tab

| Field | Type | Required | Default | Options | Constraints | Evidence Grade |
|-------|------|----------|---------|---------|-------------|---------------|
| Classification | Multi-select | Yes | (none) | Available classifications | At least one required | A |
| Protocol/Port | Multi-select | No | Any | Network Port Definitions | Target protocols/ports | A |
| Application | Multi-select | No | Any | Application Template definitions | Source/dest app filter | A |
| Direction | Dropdown | No | Both | Inbound, Outbound, Both | Traffic direction | B |
| End-User | Multi-select | No | All | End-User Group definitions | User scope | B |

### Reaction Tab

Same structure as Web Protection Rule (S23).

### General Tab

Same structure as Email Protection Rule (S22).

---

## S28: Clipboard Protection Rule

**Navigation:** Rule Sets > [set] > Actions > New Rule > Clipboard Protection
**Source:** [S33 doc-corpus]

### Condition Tab

| Field | Type | Required | Default | Options | Constraints | Evidence Grade |
|-------|------|----------|---------|---------|-------------|---------------|
| Classification | Multi-select | Yes | (none) | Available classifications | At least one required | A |
| Source Application | Multi-select | No | Any | Application Template definitions | App where copy originates | A |
| Destination Application | Multi-select | No | Any | Application Template definitions | App where paste targets | A |
| End-User | Multi-select | No | All | End-User Group definitions | User scope | B |

### Reaction Tab

Same structure as Web Protection Rule (S23).

### General Tab

Same structure as Email Protection Rule (S22).

---

## S29: Printer Protection Rule

**Navigation:** Rule Sets > [set] > Actions > New Rule > Printer Protection
**Source:** [S34 doc-corpus]

### Condition Tab

| Field | Type | Required | Default | Options | Constraints | Evidence Grade |
|-------|------|----------|---------|---------|-------------|---------------|
| Classification | Multi-select | Yes | (none) | Available classifications | At least one required | A |
| Printer Type | Dropdown | No | Any | Local Printer, Network Printer, Virtual Printer (PDF) | Target printer type | A |
| Network Printer | Multi-select | Conditional | Any | Network Printer definitions | Only if type = Network | B |
| End-User | Multi-select | No | All | End-User Group definitions | User scope | B |

### Reaction Tab

Same structure as Web Protection Rule (S23).

### General Tab

Same structure as Email Protection Rule (S22).

---

## S30: Application File Access Protection Rule

**Navigation:** Rule Sets > [set] > Actions > New Rule > Application File Access Protection
**Source:** [S37 doc-corpus]

### Condition Tab

| Field | Type | Required | Default | Options | Constraints | Evidence Grade |
|-------|------|----------|---------|---------|-------------|---------------|
| Classification | Multi-select | Yes | (none) | Available classifications | At least one required | A |
| Application | Multi-select | Yes | (none) | Application Template definitions | Which apps trigger rule | A |
| File Location | Text / path | No | Any | File paths, folders | Target file locations | B |
| Access Type | Multi-select | No | Any | Read, Write, Execute | Type of file access | B |
| End-User | Multi-select | No | All | End-User Group definitions | User scope | B |

### Reaction Tab

Same structure as Web Protection Rule (S23).

### General Tab

Same structure as Email Protection Rule (S22).

---

## S31: Policy Catalog - DLP Policy

**Navigation:** Menu > Policy > Policy Catalog > Product: "Data Loss Prevention [version]" > Category: "DLP Policy"
**Purpose:** Top-level policy object assigned to systems
**Source:** [S1][S26][S27 doc-corpus]

### UI Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  ePO Console > Menu > Policy > Policy Catalog                                │
│  Product: [Data Loss Prevention 11.11.x          ▼]                          │
│  Category: [DLP Policy                            ▼]                          │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Actions ▼  [New Policy]  [Duplicate]  [Delete]  [Rename]                    │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐    │
│  │ Policy Name                │ Assigned To    │ Description           │    │
│  ├────────────────────────────┼────────────────┼───────────────────────┤    │
│  │ McAfee Default             │ 0 groups       │ Default DLP policy    │    │
│  │ DLP-Policy-Production-v2   │ 3 groups       │ Production enforcement│    │
│  │ DLP-Policy-Pilot-v1        │ 1 group        │ Pilot group (monitor) │    │
│  └────────────────────────────┴────────────────┴───────────────────────┘    │
│                                                                              │
│  ── Selected: DLP-Policy-Production-v2 ──────────────────────────────────    │
│                                                                              │
│  Application Strategy:  [Monitored              ▼]                           │
│  Privileged Users:      [IT-Admins                ] [+ Add] [Remove]         │
│  Device Class Overrides: [Configure...]                                      │
│                                                                              │
│  Rule Sets (priority order -- top evaluated first):                          │
│  ┌──────────────────────────────────────────────────────────────────────┐    │
│  │  1. PCI-DSS-Compliance-v1          [Enabled]    [▲] [▼] [Remove]   │    │
│  │  2. HIPAA-Compliance-v1            [Enabled]    [▲] [▼] [Remove]   │    │
│  │  3. IP-Protection-v1               [Enabled]    [▲] [▼] [Remove]   │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
│  [+ Add Rule Set]                                                            │
│                                                                              │
│  [Save]  [Cancel]                                                            │
└──────────────────────────────────────────────────────────────────────────────┘
```

| Field | Type | Required | Default | Options | Constraints | Evidence Grade |
|-------|------|----------|---------|---------|-------------|---------------|
| Policy Name | Text | Yes | (empty) | Free text | Must be unique | A |
| Description | Textarea | No | (empty) | Free text | -- | B |
| Application Strategy | Dropdown | Yes | Unknown | Trusted, Monitored, Unknown | Default for unlisted apps | A |
| Device Class Overrides | Config panel | No | None | Device class selections | Windows only; override status/filter | A |
| Privileged Users | Multi-select | No | None | AD users/groups | Exempt from all DLP enforcement | A |
| Rule Sets | Ordered list | Yes (min 1) | (empty) | Available rule sets | Priority order (top-to-bottom) | A |

**Page-Level Actions:**

| Action | Behavior | Evidence Grade |
|--------|----------|---------------|
| New Policy | Create new empty policy | A |
| Duplicate | Copy existing policy with all settings | A |
| Delete | Remove policy (blocked if assigned to systems) | A |
| Rename | Change policy name | B |

### Examples

#### Example 1: Production DLP Policy for Finance Department

```yaml
policy_name: "DLP-Policy-Production-v2"
description: "Full enforcement policy for Finance, HR, and Executive departments"
application_strategy: "Monitored"
privileged_users: ["IT-DLP-Admins"]           # IT security team exempt for testing
rule_sets:
  - "PCI-DSS-Compliance-v1"                    # References S21 Example 1
  - "HIPAA-Compliance-v1"
  - "IP-Protection-v1"                         # References S21 Example 2

# WHY: Application Strategy = "Monitored" means applications not explicitly
#   listed in Application Templates will be monitored (not trusted or blocked).
#   This is the safe default -- unknown applications get DLP inspection.
# WHY: IT-DLP-Admins are privileged users so they can test DLP rules by
#   deliberately triggering violations without generating false incidents.
# WHY: Rule sets are ordered PCI > HIPAA > IP by business priority. PCI
#   violations carry the highest regulatory fines, so PCI rules evaluate first.
# GOTCHA: This policy is assigned to SYSTEMS in the System Tree (S33), not
#   to users. A Finance user on a shared laptop outside the Finance tree group
#   will NOT be protected unless the shared laptop also has this policy.
# GOTCHA: Adding a rule set to the policy does NOT automatically push it to
#   endpoints. You must either wait for the ASCI interval (default 60 min) or
#   manually wake up agents (System Tree > Wake Up Agents).
```

#### Example 2: Pilot / Monitor-Only Policy

```yaml
policy_name: "DLP-Policy-Pilot-v1"
description: "Monitor-only policy for initial rollout -- all rules set to Monitor"
application_strategy: "Monitored"
privileged_users: []
rule_sets:
  - "PCI-DSS-Monitor-Only-v1"                  # Same classifications but all Monitor
  - "PII-Monitor-Only-v1"

# WHY: A separate pilot policy ensures that the monitoring phase does not
#   interfere with production enforcement. Deploy this to a pilot group first,
#   review incidents for 2-4 weeks, then switch the group to the production policy.
# WHY: No privileged users -- during pilot, everyone is monitored equally to
#   build an accurate baseline.
# DEPLOYMENT SEQUENCE:
#   Week 1-2: Assign Pilot policy to a test group of 50 systems
#   Week 3-4: Review incidents, tune thresholds, reduce false positives
#   Week 5: Assign Production policy to pilot group, expand pilot to 200 systems
#   Week 8: Full production deployment
```

---

## S32: Endpoint Configuration Policy

**Navigation:** Policy Catalog > Data Loss Prevention [version] > DLP Endpoint Configuration
**Purpose:** Control DLP agent operational behavior (separate from rule enforcement)
**Source:** [S59][S60][S61 doc-corpus]

| Field | Type | Required | Default | Options | Constraints | Evidence Grade |
|-------|------|----------|---------|---------|-------------|---------------|
| Operational Mode: Data-in-Use | Toggle | Yes | Enabled | Enabled/Disabled | Master toggle for content-aware protection | A |
| Operational Mode: Device Control | Toggle | Yes | Enabled | Enabled/Disabled | Master toggle for device control | A |
| Operational Mode: Discovery | Toggle | Yes | Disabled | Enabled/Disabled | Endpoint discovery scanning | A |
| Active Modules | Checkbox list | Yes | All enabled | Email, Web, Cloud, Removable Storage, Network Share, Network Comm, Clipboard, Printer, App File Access | Selectively enable modules | A |
| Corporate Connectivity: Detection Method | Dropdown | Yes | DNS | DNS query, ePO server ping, Domain controller reachability | How agent determines on/off network | A |
| Corporate Connectivity: On-Network Policy | Dropdown | No | Same | Different policy for on-network | Allows different rules on/off network | B |
| Evidence Server Path | Text (UNC) | No | (empty) | UNC path | Where evidence files are stored | B |
| Logging Level | Dropdown | No | Normal | Minimal, Normal, Verbose, Debug | Agent logging verbosity | B |

---

## S33: System Tree - Policy Assignment

**Navigation:** Menu > Systems > System Tree > [group] > Assigned Policies tab
**Purpose:** Assign DLP policies to system groups
**Source:** [S39][S40][S70][S71 doc-corpus]

### UI Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  ePO Console > Menu > Systems > System Tree                                  │
├─────────────────┬────────────────────────────────────────────────────────────┤
│ System Tree     │  Group: Finance Department                                 │
│ (left sidebar)  │  Tab: [Systems] [*Assigned Policies*] [Client Tasks]       │
│                 │ ─────────────────────────────────────────────────────────── │
│ ▾ My Org        │                                                            │
│   ▸ North       │  Assigned Policies:                                        │
│     America     │  ┌──────────────────┬────────────────┬────────────────┐   │
│   ▾ Finance     │  │ Product          │ Category       │ Assigned Policy│   │
│     Department  │  ├──────────────────┼────────────────┼────────────────┤   │
│     ● ws-fin-01 │  │ Data Loss        │ DLP Policy     │ DLP-Policy-    │   │
│     ● ws-fin-02 │  │ Prevention       │                │ Production-v2  │   │
│     ● ws-fin-03 │  │ 11.11.x          │                │ [Edit Assign.] │   │
│   ▸ Engineering │  │                  │ Endpoint Config│ Default        │   │
│   ▸ HR          │  │                  │                │ [Edit Assign.] │   │
│   ▸ Europe      │  └──────────────────┴────────────────┴────────────────┘   │
│                 │                                                            │
│                 │  Inheritance: ☑ Break inheritance from parent (My Org)     │
│                 │  Lock:        ☐ Lock assignment (prevent child override)    │
│                 │                                                            │
│                 │  [Save]                                                     │
│                 │                                                            │
│                 │  ──────────────────────────────────────────────────────     │
│                 │  Actions ▼  [ Wake Up Agents ]                             │
│                 │                                                            │
│                 │  Wake Up Agents dialog:                                     │
│                 │  Randomization:     [0   ] minutes (0-60)                  │
│                 │  ☑ Force complete policy update                             │
│                 │  ☐ Run client tasks                                         │
│                 │  [OK]  [Cancel]                                             │
└─────────────────┴────────────────────────────────────────────────────────────┘
```

| Field | Type | Required | Default | Options | Constraints | Evidence Grade |
|-------|------|----------|---------|---------|-------------|---------------|
| Product | Read-only | -- | -- | "Data Loss Prevention [version]" | Row in assigned policies table | A |
| Category | Read-only | -- | -- | DLP Policy, Endpoint Configuration, etc. | -- | A |
| Assigned Policy | Dropdown | Yes | Inherited | Available policies in Policy Catalog | Select policy to assign | A |
| Break Inheritance | Checkbox | Conditional | Unchecked | Yes/No | Required to override parent group policy | A |
| Lock Assignment | Checkbox | No | Unchecked | Yes/No | Prevent child groups from overriding | B |

**Wake Up Agents Dialog:**

| Field | Type | Required | Default | Options | Constraints | Evidence Grade |
|-------|------|----------|---------|---------|-------------|---------------|
| Randomization | Numeric | No | 0 | Minutes (0-60) | Spread out agent connections | A |
| Force Complete Policy Update | Checkbox | No | Unchecked | Yes/No | Full policy re-download | A |
| Run Client Tasks | Checkbox | No | Unchecked | Yes/No | Execute pending client tasks | B |

### Examples

#### Example 1: Deploy PCI Compliance to Finance Department

```yaml
system_tree_group: "My Organization > Finance Department"
product: "Data Loss Prevention 11.11.x"
category: "DLP Policy"
assigned_policy: "DLP-Policy-Production-v2"   # References S31 Example 1
break_inheritance: true                        # Override the parent (My Org) default
lock_assignment: true                          # Prevent sub-groups from overriding
agent_wake_up:
  randomization: 0                             # Immediate (small group, no stagger needed)
  force_policy_update: true                    # Full re-download, not incremental
  run_client_tasks: false

# WHY: Break inheritance because Finance needs a stricter policy than the
#   organization-wide default (which is Monitor-only for most departments).
# WHY: Lock assignment = true (enforced) for Finance because they handle the
#   most PCI data. No sub-group admin should be able to weaken the policy.
# WHY: Agent wake-up with force policy update for IMMEDIATE deployment. By
#   default, agents check for policy updates every 60 minutes (ASCI interval).
#   Force update pushes the policy right now.
# WHY: Randomization = 0 because Finance is a small group (50 systems). For
#   large groups (1000+ systems), use randomization = 15-30 minutes to avoid
#   overwhelming the ePO server with simultaneous connections.
# GOTCHA: The policy applies to SYSTEMS in this tree group, not to users.
#   A Finance user on a shared laptop in Engineering's tree group will NOT
#   be covered by this assignment. To cover the USER regardless of machine,
#   add End-User Group conditions (S14) to each rule inside the rule sets.
# GOTCHA: Policy push must be explicitly allowed. After saving the assignment,
#   "Allow Policy Push" may need to be activated in your ePO configuration.
#   Then use Wake Up Agents to force immediate delivery.
# GOTCHA: Verify deployment by checking DLP Incident Manager for test
#   violations, or run a DLP Agent Status query in ePO Queries & Reports.
```

#### Example 2: Phased Pilot Deployment to Engineering

```yaml
system_tree_group: "My Organization > Engineering > Pilot Group"
assigned_policy: "DLP-Policy-Pilot-v1"        # References S31 Example 2
break_inheritance: true
lock_assignment: false                         # Allow pilot leads to override if needed
agent_wake_up:
  randomization: 15                            # Stagger over 15 minutes (200 systems)
  force_policy_update: true

# WHY: Pilot Group is a sub-group of Engineering containing ~200 systems
#   selected for initial DLP rollout. Monitor-only policy during Phase 1.
# WHY: Lock = false so pilot leads can temporarily override with "No Policy"
#   if DLP causes issues during the pilot. Flexibility during testing phase.
# WHY: Randomization = 15 minutes because 200 simultaneous connections could
#   spike ePO server CPU. Staggering spreads the load.
# DEPLOYMENT SEQUENCE:
#   Week 1: Assign Pilot policy, wake up agents
#   Week 2-3: Monitor incidents, tune false positives
#   Week 4: Switch to Production policy, expand to full Engineering
```

#### Example 3: Tag-Based Dynamic Assignment (Advanced)

```yaml
# Instead of static System Tree assignment, use ePO tags + server tasks
# for dynamic policy assignment. This is tribal knowledge from Video #5.

step_1_create_tags:
  - tag: "DLP-HighSensitivity"
    criteria: "Systems in Finance, HR, or Legal OU"
  - tag: "DLP-Standard"
    criteria: "All other managed systems"

step_2_server_task:
  task_name: "Auto-Tag DLP Sensitivity"
  schedule: "Daily at 02:00"
  action: "Apply tags based on System Tree group membership"

step_3_policy_assignment_rule:
  rule: "If tag = DLP-HighSensitivity, assign DLP-Policy-Production-v2"
  rule: "If tag = DLP-Standard, assign DLP-Policy-Pilot-v1"

# WHY: Tag-based assignment is dynamic. When a system moves from Engineering
#   to Finance in the System Tree, it automatically gets the correct DLP
#   policy on the next server task run. Static assignment requires manual
#   re-assignment every time a system moves.
# WHY: Server task runs daily at 02:00 (off-hours) to minimize performance
#   impact on the ePO server.
# GOTCHA: Tag-based policy assignment requires ePO's "Policy Assignment Rules"
#   feature, which works for some products but has LIMITATIONS with DLP.
#   Test thoroughly -- DLP policy assignment via tags may not work in all ePO
#   versions. The System Tree assignment (Examples 1 and 2) is the reliable
#   fallback.
```

---

## S34: EDM Configuration

**Navigation:** Classification criteria > Add Component > Exact Data Match
**Purpose:** Configure exact data matching against fingerprinted structured data
**Source:** [S45][S46][S47][S48 doc-corpus]

### Fingerprint File Upload

| Field | Type | Required | Default | Options | Constraints | Evidence Grade |
|-------|------|----------|---------|---------|-------------|---------------|
| Fingerprint File | File upload | Yes | (empty) | .edm file | Generated by EDMTrain utility | A |
| EDM Version | Selection | Yes | Enhanced | Enhanced (current), Old (legacy) | New deployments should use Enhanced | A |

### Column Configuration

| Field | Type | Required | Default | Options | Constraints | Evidence Grade |
|-------|------|----------|---------|---------|-------------|---------------|
| Column Selection | Checkbox list | Yes (min 1) | All columns | Columns from fingerprint file header | Auto-populated from .edm file | A |
| Required Columns | Checkbox (per column) | No | None | Selected columns | Must match for trigger | A |
| Optional Columns | Checkbox (per column) | No | All non-required | Selected columns | Contribute to match threshold | A |
| Match Threshold | Numeric | Yes | All selected | 1 to N | Minimum columns matching in same row | A |

### EDMTrain Utility (External Tool)

| Parameter | Type | Required | Description | Evidence Grade |
|-----------|------|----------|-------------|---------------|
| Input File | File path | Yes | CSV or TSV with headers | A |
| Output File | File path | Yes | Output .edm fingerprint file | A |
| Delimiter | Flag | No | Column delimiter (comma, tab) | A |
| Column Types | Flag | No | Specify column data types | B |

### Examples

#### Example 1: Customer PII Database (EDM)

```yaml
# Step 1: Prepare source CSV (exported from customer database)
# File: customer_pii_export.csv
# Contents:
#   SSN,FirstName,LastName,DOB,Email,Phone
#   123-45-6789,John,Smith,1985-03-15,john@example.com,555-0123
#   987-65-4321,Jane,Doe,1990-07-22,jane@example.com,555-0456
#   ... (10,000 rows)

# Step 2: Generate fingerprint file with EDMTrain utility
# Command: EDMTrain.exe -i customer_pii_export.csv -o customer_pii.edm -d comma

# Step 3: Upload and configure in ePO
fingerprint_file: "customer_pii.edm"
edm_version: "Enhanced"
column_selection:
  - { column: "SSN",       selected: true, required: true }
  - { column: "FirstName", selected: true, required: false }
  - { column: "LastName",  selected: true, required: false }
  - { column: "DOB",       selected: true, required: false }
  - { column: "Email",     selected: true, required: false }
  - { column: "Phone",     selected: true, required: false }
match_threshold: 3   # At least 3 columns from the same row must match

# LOGIC: Triggers when 3+ values from the SAME ROW appear in a document.
#   Example: "John Smith 123-45-6789" matches SSN (required) + FirstName +
#   LastName = 3 columns from the same row. Triggers.
#   Example: "John Doe 555-0123" -- these values are NOT from the same row
#   (John is row 1, Doe is row 2, 555-0123 is row 1). Does NOT trigger
#   because no single row has 3+ matching columns.
#
# WHY: SSN is Required because it is the strongest identifier. A match without
#   an SSN (just FirstName + LastName + DOB) could be coincidental.
# WHY: Threshold=3 balances detection and false positives. With 6 columns,
#   requiring only 2 would trigger on common names + common phone numbers.
#   Requiring 3 ensures at least one strong identifier (SSN) plus context.
# GOTCHA: EDM fingerprint files must be regenerated when the source database
#   changes. Set up a scheduled task to export, re-fingerprint, and re-upload.
# GOTCHA: EDM works on the ePO server, not on endpoints directly. For endpoint
#   protection, the fingerprints are distributed to DLP agents during policy push.
#   Large fingerprint files (100K+ rows) increase policy download time.
# GOTCHA: The EDMTrain utility runs OUTSIDE the ePO console. It is a command-
#   line tool that must be run on a server with access to the source data.
```

---

## Cross-Reference Map: How Examples Connect

This section shows how the worked examples across all screens form a coherent, deployable policy suite.

```
Level 1: DEFINITIONS
  ├── S7 Ex1: "US-SSN-Standard" (regex pattern)
  ├── S7 Ex2: "US-SSN-No-Dashes" (regex pattern)
  ├── S7 Ex3: "CC-Visa-MC" (regex pattern + Luhn)
  ├── S7 Ex4: "ProjectCode-Internal" (regex pattern)
  ├── S8 Ex1: "HIPAA-Medical-Terms" (dictionary)
  ├── S8 Ex2: "Financial-Confidential" (dictionary)
  ├── S8 Ex3: "Source-Code-Keywords" (dictionary)
  ├── S14 Ex1: "Finance-Team" (end-user group)
  ├── S14 Ex2: "Executives" (end-user group)
  ├── S15 Ex1: "External-Recipients" (email address list)
  ├── S16 Ex1: "Code-Sharing-Sites" (URL list)
  └── S16 Ex2: "AI-Chat-Services" (URL list)
        │
        ▼
Level 2: CLASSIFICATIONS
  ├── S2 Ex1: "PII - Personal Identifiable Information"
  │     Uses: US-SSN-Standard, US-SSN-No-Dashes, HIPAA-Medical-Terms
  ├── S2 Ex2: "PCI - Payment Card Data"
  │     Uses: CC-Visa-MC + Proximity keywords
  └── S2 Ex3: "Intellectual Property - Source Code"
        Uses: Source-Code-Keywords, True File Type
        │
        ▼
Level 3: RULES
  ├── S22 Ex1: "Email-PCI-CreditCard-Block-v1"
  │     Uses: PCI - Payment Card Data, External-Recipients
  ├── S22 Ex2: "Email-PII-SSN-Monitor-v1"
  │     Uses: PII - Personal Identifiable Information
  ├── S22 Ex3: "Email-IP-TradeSecret-Justify-v1"
  │     Uses: Intellectual Property - Source Code, External-Recipients
  ├── S23 Ex1: "Web-IP-SourceCode-Monitor-v1"
  │     Uses: Intellectual Property - Source Code, Code-Sharing-Sites
  ├── S23 Ex2: "Web-AI-DataLeakage-Monitor-v1"
  │     Uses: PCI - Payment Card Data, AI-Chat-Services
  ├── S24 Ex1: "Cloud-IP-SourceCode-Block-v1"
  │     Uses: Intellectual Property - Source Code
  └── S25 Ex1: "USB-PCI-CreditCard-Block-v1"
        Uses: PCI - Payment Card Data
        │
        ▼
Level 4: RULE SETS
  ├── S21 Ex1: "PCI-DSS-Compliance-v1"
  │     Contains: Email-PCI-CreditCard-Block-v1, Web monitor, USB block, etc.
  └── S21 Ex2: "IP-Protection-v1"
        Contains: Web-IP-SourceCode-Monitor-v1, Cloud block, Email justify
        │
        ▼
Level 5: POLICIES
  ├── S31 Ex1: "DLP-Policy-Production-v2"
  │     Contains: PCI-DSS-Compliance-v1, HIPAA-Compliance-v1, IP-Protection-v1
  └── S31 Ex2: "DLP-Policy-Pilot-v1"
        Contains: PCI-DSS-Monitor-Only-v1, PII-Monitor-Only-v1
        │
        ▼
Level 6: ASSIGNMENT
  ├── S33 Ex1: Finance Department → DLP-Policy-Production-v2 (enforced, locked)
  ├── S33 Ex2: Engineering Pilot → DLP-Policy-Pilot-v1 (monitor, unlocked)
  └── S33 Ex3: Tag-based dynamic assignment (advanced)
```

---

## Evidence Grade Legend

| Grade | Meaning | Source Quality |
|-------|---------|---------------|
| **A** | Directly documented in official Trellix product guide or interface reference guide | Official vendor documentation (Grade A sources) |
| **B** | Documented in secondary official sources (training materials, KB articles) or strongly inferred from multiple A sources | Official but indirect |
| **C** | From community forums, third-party articles, or KB articles with limited detail | Community/third-party |
| **D** | Inferred from video descriptions, search snippets, or cross-product analogy | Inference-based |
| **E** | Unverified assumption based on DLP industry conventions | Assumption |
| **U** | Not verified against any source | Unverified |
