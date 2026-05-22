# Enterprise DLP: ML Models & LLM Usage -- Deep Dive Research

> **Last updated:** 2026-05-21
> **Methodology:** Web searches, vendor documentation, technical blog posts, academic publications, press releases.
> **Evidence grading:** A = vendor documentation / published paper, B = vendor blog / press release, C = third-party analysis / inference.

---

## Table of Contents

1. [Palo Alto Networks Enterprise DLP](#1-palo-alto-networks-enterprise-dlp)
2. [Symantec / Broadcom DLP](#2-symantec--broadcom-dlp)
3. [Microsoft Purview](#3-microsoft-purview)
4. [Nightfall AI](#4-nightfall-ai)
5. [Netskope (SkopeAI)](#5-netskope-skopeai)
6. [Forcepoint (AI Mesh / Getvisibility)](#6-forcepoint-ai-mesh--getvisibility)
7. [Zscaler DLP](#7-zscaler-dlp)
8. [Skyhigh Security DLP](#8-skyhigh-security-dlp)
9. [Cross-Vendor Comparison Matrix](#9-cross-vendor-comparison-matrix)
10. [Key Takeaways for Our DLP Product](#10-key-takeaways-for-our-dlp-product)

---

## 1. Palo Alto Networks Enterprise DLP

### 1.1 ML Model Inventory

| Model Name / Component | Type | What It Detects | Training Approach | Accuracy Claims | Customer-Trainable? | Evidence Grade |
|---|---|---|---|---|---|---|
| DNN Document Classifiers (100+) | Deep Neural Network (5th generation) | Financial docs, legal docs, healthcare docs, source code, ID cards, tax forms | Supervised learning on labeled corpora | >90% false-positive reduction vs regex | No (predefined) | A -- vendor docs |
| Contrastive Credibility Propagation (CCP) | Semi-supervised DNN (PyTorch) | Sensitive vs. non-sensitive text documents | Iterative semi-supervised with soft pseudo-labels; handles noisy/imbalanced data | Outperforms state-of-the-art SSL on 5 data quality scenarios | No (internal R&D) | A -- AAAI '24 paper + open-source PyTorch impl |
| LLM-Augmented Classifiers | Transformer-based LLM | Contextual PII, GDPR data, financial data across 250+ data patterns | LLM augments pattern-based detections with semantic context | Not disclosed | No | B -- vendor blog |
| Small Language Models (SLMs) | Transformer (few million to few billion params) | Real-time security tasks, nuanced data classification | Hyper-specialized fine-tuning for specific security domains | Not disclosed | No | B -- community blog |
| Graph-Based Detection | Graph neural networks | Relationship patterns between entities in documents | Trained on document structure and entity relationships | Not disclosed | No | B -- vendor blog |
| Custom Document Types | Supervised ML | Customer-defined document categories | Customer uploads 30+ sample documents per category | Not disclosed | Yes | A -- vendor docs |
| OCR + ML Pipeline | CNN + DNN | Sensitive data in images (ID cards, checks, screenshots) | Pre-trained image recognition models | Not disclosed | No | B -- vendor blog |

### 1.2 Detection Pipeline Architecture

```
                                 Palo Alto Enterprise DLP Detection Pipeline
                                 ==========================================

  [Content Ingress]
       |
       v
  +--------------------+     +---------------------+     +------------------------+
  | Content Extraction  |---->| Pattern Matching    |---->| ML/DNN Classification  |
  | (text, images, OCR) |     | (regex, keywords,   |     | (100+ DNN classifiers, |
  |                     |     |  data identifiers)  |     |  5th-gen models)       |
  +--------------------+     +---------------------+     +------------------------+
                                                                |
                                                                v
                                                   +-------------------------+
                                                   | LLM Contextual          |
                                                   | Augmentation            |
                                                   | (semantic analysis,     |
                                                   |  NLP, graph-based)      |
                                                   +-------------------------+
                                                                |
                                                                v
                                                   +-------------------------+
                                                   | Confidence Scoring &    |
                                                   | Policy Enforcement      |
                                                   +-------------------------+
                                                                |
                                                                v
                                                         [Alert / Block]
```

**Infrastructure:** NVIDIA Triton Inference Server on GPUs for model serving. Migrated from CPU-only to GPU inference, reducing compute cost to ~$33/hour while dramatically improving throughput. NVIDIA AI Enterprise stack provides dynamic model hosting for various DNN architectures.

### 1.3 LLM Usage

| Aspect | Detail |
|---|---|
| **Where used** | Contextual augmentation layer on top of pattern matching + DNN classifiers |
| **Model size** | Not disclosed; uses both LLMs (complex reasoning, data generation) and SLMs (real-time execution) |
| **Runtime vs. offline** | Hybrid -- SLMs for real-time inline inspection; LLMs for offline model training and data generation |
| **Specific tasks** | Semantic context evaluation around detected patterns; reducing false positives; understanding document intent; augmenting 250+ data patterns with contextual understanding |
| **Architecture** | Transformer-based; served via NVIDIA Triton on GPU clusters |

### 1.4 Pre-trained Classifier Categories (Named)

**Business categories for predefined data patterns:**
- Academia
- Confidential
- Employment
- Financial
- Government
- Healthcare
- Legal
- Marketing
- Source Code

**Specific data pattern examples (250+ total):**
- CCN (Credit Card Number)
- SSN (Social Security Number)
- ID Card -- USA -- Driving License
- Source Code -- Go, Python, Java, C/C++, JavaScript, etc.
- Financial Accounting Documents
- Healthcare / Medical Records
- Legal Contracts
- Tax Documents
- Passport Numbers (multi-country)
- GDPR-related PII patterns
- Bank Account Numbers / IBAN
- Personally Identifiable Information (multi-region, tagged by geography)

### 1.5 Unique ML Capabilities

- **Contrastive Credibility Propagation (CCP):** Published at AAAI '24, open-sourced on GitHub. Novel semi-supervised learning that handles noisy labels, class imbalance, and limited labeled data -- common in enterprise DLP where labeled sensitive documents are scarce.
- **NVIDIA Triton + GPU inference:** One of the few DLP vendors publicly documenting GPU-accelerated ML inference at scale.
- **5th-generation DNN:** Integrates NLP, deep learning, and graph-based detection in a single classifier generation.
- **Geographic tagging:** Every predefined data pattern tagged with applicable geography (Global, USA, EU, etc.).

### 1.6 Limitations

- Specific model architectures and parameter counts not publicly disclosed.
- Custom document types require 30+ sample documents per category.
- LLM model details (which LLM, parameter count) not documented.
- No public benchmark comparisons against other vendors.

---

## 2. Symantec / Broadcom DLP

### 2.1 ML Model Inventory

| Model Name / Component | Type | What It Detects | Training Approach | Accuracy Claims | Customer-Trainable? | Evidence Grade |
|---|---|---|---|---|---|---|
| Vector Machine Learning (VML) | Statistical / SVM-like | Unstructured sensitive documents (proprietary, confidential info) | Customer trains with 50-500 positive + negative example docs | Vendor claims high accuracy with 250+ positive/negative samples | Yes (core feature) | A -- vendor docs + best practices guide |
| Exact Data Matching (EDM) | Hashing / fingerprinting | Structured data (PII, financial records, database rows) | Customer indexes structured data sources | Exact match -- near 100% precision | Yes (customer indexes data) | A -- vendor docs |
| Indexed Document Matching (IDM) | Document fingerprinting | Unstructured document content and images | Customer fingerprints sensitive documents | Partial + derivative matching | Yes (customer indexes docs) | A -- vendor docs |
| Form Recognition | Template matching + ML | Structured forms (tax forms, applications, healthcare forms) | Pre-trained on common form layouts | Not disclosed | No | A -- vendor docs |
| Exact Match Data Identifier (EMDI) | Pattern matching + validation | Structured identifiers (SSN, CCN, passport numbers) | Pre-built algorithms with checksum validation | 30+ predefined identifiers | No (predefined) | A -- vendor docs |
| Described Content Matching (DCM) | Keyword + regex + proximity | Content matching via keywords, regex, dictionaries | Rule-based | N/A | Yes (customer configures) | A -- vendor docs |

### 2.2 Detection Pipeline Architecture

```
                              Symantec DLP Detection Pipeline
                              ================================

  [Content Ingress]
       |
       v
  +--------------------+     +---------------------+     +------------------------+
  | Content Extraction  |---->| EDM / EMDI          |---->| IDM                    |
  | (text, images,     |     | (exact structured    |     | (document fingerprint  |
  |  200+ file types)  |     |  data matching)      |     |  matching)             |
  +--------------------+     +---------------------+     +------------------------+
                                      |                           |
                                      v                           v
                              +---------------------+     +------------------------+
                              | DCM                  |     | VML                    |
                              | (keywords, regex,   |     | (Vector Machine        |
                              |  dictionaries)       |     |  Learning classifier)  |
                              +---------------------+     +------------------------+
                                      |                           |
                                      v                           v
                              +------------------------------------------------+
                              | Policy Engine (combine multiple detection       |
                              | results, apply confidence thresholds)           |
                              +------------------------------------------------+
                                                    |
                                                    v
                                              [Alert / Block / Quarantine]
```

### 2.3 LLM Usage

| Aspect | Detail |
|---|---|
| **LLM presence** | **None documented.** Symantec DLP relies on classical ML (VML) and fingerprinting techniques. |
| **Modern ML** | VML is the primary ML component -- a statistical model based on keyword frequency analysis, closer to TF-IDF/SVM than deep learning. |
| **Gap** | No transformer-based or LLM-augmented detection as of DLP 16.x / 25.x / 26.x. This is the oldest DLP platform and ML has not been modernized. |

### 2.4 Pre-trained Policy Template Categories (Named)

**Regulatory compliance:**
- HIPAA and HITECH (including PHI)
- Caldicott Report (UK NHS)
- GLBA (Gramm-Leach-Bliley Act)
- PCI DSS
- SOX (Sarbanes-Oxley)
- GDPR
- CCPA
- US Intelligence Control Markings (CAPCO) and DCID 1/7

**Data type templates:**
- Customer Data Protection
- Employee Data Protection
- Financial Information
- Encrypted Data
- Developer Keys and Secrets (added in DLP 16.0.1)
- Network Diagrams
- Publishing Documents
- Resumes
- Design Documents
- Merger & Acquisition
- Board Communications
- Fraud Detection
- Violence and Weapons
- Yahoo/MSN Messenger Activity
- Webmail Monitoring

**Geographic-specific identifiers:**
- UK: Driver's License, Electoral Roll, NHS Number, National Insurance, Passport, Tax ID
- US: Social Security Numbers, States Driver's License Numbers
- Canada, Australia, EU countries (multiple per country)

**Pre-built data identifiers (30+):**
- Credit Card Numbers (with Luhn validation)
- Social Security Numbers
- Passport Numbers
- Driver's License Numbers
- Bank Account Numbers
- Tax Identification Numbers
- National Insurance Numbers
- Healthcare identifiers

### 2.5 Unique ML Capabilities

- **VML customer training:** The most mature customer-trainable ML classifier in the industry. Supports training with as few as 50 documents per class.
- **IDM partial matching:** Can detect derivatives and partial copies of fingerprinted documents.
- **EDM structured data:** Handles billions of indexed records for exact data matching.
- **Largest installed base:** Legacy enterprise DLP with the widest deployment footprint.

### 2.6 Limitations

- VML is based on classical statistical models (bag-of-words / keyword frequency), not deep learning.
- No LLM, transformer, or modern NLP integration documented.
- No pre-trained document classifiers (customer must train VML themselves).
- No image-based ML classification (relies on OCR + text matching).
- Aging architecture -- Broadcom acquisition slowed innovation.

---

## 3. Microsoft Purview

### 3.1 ML Model Inventory

| Model Name / Component | Type | What It Detects | Training Approach | Accuracy Claims | Customer-Trainable? | Evidence Grade |
|---|---|---|---|---|---|---|
| Pre-trained Trainable Classifiers (60+) | Transformer-based NLP | Document categories: financial, legal, HR, healthcare, source code, communications compliance | Microsoft-trained on large internal corpora | Not disclosed per-classifier | No (pre-built) | A -- Microsoft Learn docs |
| Custom Trainable Classifiers | Transformer-based NLP | Customer-defined document categories | Customer provides 50-500+ seed documents; Microsoft trains model | Not disclosed | Yes | A -- Microsoft Learn docs |
| Sensitive Information Types (SITs) | Pattern matching + ML validation | PII, financial data, health data (300+ types across 60+ countries) | Pre-built with regex + ML confidence scoring | Not disclosed | Partially (custom SITs) | A -- Microsoft Learn docs |
| Adult/Racy/Gory Image Classifier | CNN (image classification) | Inappropriate images | Microsoft-trained on image datasets | Not disclosed | No | A -- Microsoft Learn docs |
| Prompt Shields | Transformer (likely) | Adversarial prompt injection / jailbreak attempts in GenAI | Trained on adversarial prompt datasets | Not disclosed | No | A -- Microsoft Learn docs |
| Protected Material Detector | Transformer (likely) | Copyrighted / branded text in GenAI responses | Trained on known protected content | Not disclosed | No | A -- Microsoft Learn docs |
| Optical Character Recognition | CNN + transformer | Text in images | Azure AI Vision services | Not disclosed | No | B -- inferred from platform |

### 3.2 Detection Pipeline Architecture

```
                            Microsoft Purview Detection Pipeline
                            ====================================

  [Content Ingress: Exchange, SharePoint, OneDrive, Teams, Endpoints, GenAI apps]
       |
       v
  +--------------------+     +---------------------+     +------------------------+
  | Content Extraction  |---->| Sensitive Info Types |---->| Trainable Classifiers  |
  | (text, metadata,   |     | (300+ SITs: regex +  |     | (60+ pre-trained       |
  |  images via OCR)   |     |  ML confidence)      |     |  transformer models)   |
  +--------------------+     +---------------------+     +------------------------+
                                                                |
                                                                v
                                                   +-------------------------+
                                                   | Contextual Summary &    |
                                                   | Keyword Highlighting    |
                                                   | (NLP-powered)           |
                                                   +-------------------------+
                                                                |
                                                                v
                                                   +-------------------------+
                                                   | Sensitivity Labels &    |
                                                   | DLP Policy Engine       |
                                                   +-------------------------+
                                                                |
                                                                v
                                              [Alert / Block / Encrypt / Restrict]
```

### 3.3 LLM Usage

| Aspect | Detail |
|---|---|
| **Where used** | Trainable classifiers use transformer architecture (not explicitly called "LLM" but same foundation). Prompt Shields and Protected Material classifiers specifically target GenAI workflows. |
| **Model size** | Not disclosed; runs in Azure cloud infrastructure. |
| **Runtime vs. offline** | Runtime classification for DLP policy enforcement; classifiers are pre-trained offline. |
| **Specific tasks** | Document classification across 60+ categories; GenAI prompt/response monitoring; contextual summary generation with keyword highlighting. |
| **Copilot integration** | Purview Copilot uses LLMs for policy recommendations and data classification insights. |

### 3.4 Complete Pre-trained Classifier List (ALL Named Classifiers)

Extracted from Microsoft Learn documentation (2026-05-18 update):

| # | Classifier Name | Category |
|---|---|---|
| 1 | Actuary Reports | Finance / Insurance |
| 2 | Adult, Racy, and Gory Images | Content Safety (Image) |
| 3 | Agreements | Legal |
| 4 | Asset Management | Finance |
| 5 | Bank Statement | Finance |
| 6 | Budget | Finance |
| 7 | Business Context (Preview) | Business / General |
| 8 | Business Plan | Business / Strategy |
| 9 | Completion Certificates | Project Management |
| 10 | Compliance Policies | Regulatory (GDPR, HIPAA, ISO, PCI, SOC, SSAE 18) |
| 11 | Construction Specifications | Engineering |
| 12 | Control System and SCADA Files | Industrial / OT Security |
| 13 | Corporate Sabotage | Communications Compliance |
| 14 | Credit Report | Finance |
| 15 | Customer Complaints | Communications Compliance |
| 16 | Customer Files | Business |
| 17 | Discrimination | Communications Compliance |
| 18 | Employee Disciplinary Action | HR |
| 19 | Employee Insurance | HR / Benefits |
| 20 | Employment Agreement | HR / Legal |
| 21 | Employee Pension Records | HR / Finance |
| 22 | Employee Stocks and Financial Bond Records | HR / Finance |
| 23 | Enterprise Risk Management | Risk / Governance |
| 24 | Environmental Permits and Clearances | Regulatory |
| 25 | Facility Permits | Regulatory |
| 26 | Factory Incident Investigation Reports | Safety / Compliance |
| 27 | Finance | Finance (broad) |
| 28 | Financial Audit | Finance / Audit |
| 29 | Financial Statement | Finance |
| 30 | Freight Documents | Supply Chain / Logistics |
| 31 | Garnishment | Legal / Payroll |
| 32 | Gifts & Entertainment | Communications Compliance (FCPA, UK Bribery Act) |
| 33 | Harassment | Communications Compliance |
| 34 | Health/Medical Forms | Healthcare |
| 35 | Healthcare | Healthcare (broad) |
| 36 | Human Resources | HR (broad) |
| 37 | Invoice | Finance / Procurement |
| 38 | Intellectual Property | IP / Legal |
| 39 | Information Technology | IT / Security |
| 40 | IT Infra and Network Security Documents | IT / Security |
| 41 | Lease Deeds | Legal / Real Estate |
| 42 | Legal Affairs | Legal (broad) |
| 43 | Legal Agreements | Legal |
| 44 | Letters of Credit | Finance / Banking |
| 45 | License Agreement | Legal / IP |
| 46 | Loan Agreements and Offer Letters | Finance / Banking |
| 47 | Manufacturing Batch Records | Manufacturing / Quality |
| 48 | Marketing Collaterals | Marketing |
| 49 | Merger and Acquisition Files | M&A / Legal |
| 50 | Meeting Notes | Business |
| 51 | Money Laundering | Communications Compliance (BSA, Patriot Act) |
| 52 | MoU Files (Memorandum of Understanding) | Legal |
| 53 | Network Design Files | IT / Engineering |
| 54 | Non-Disclosure Agreement | Legal |
| 55 | OSHA Records | Safety / Regulatory |
| 56 | Paystub | HR / Payroll |
| 57 | Personal Financial Information | Finance / PII |
| 58 | Procurement | Finance / Operations |
| 59 | Profanity | Communications Compliance |
| 60 | Project Documents | Project Management |
| 61 | Prompt Shields | GenAI Security |
| 62 | Protected Material | GenAI / IP |
| 63 | Quotation | Sales / Finance |
| 64 | Regulatory Collusion | Communications Compliance (Sherman Act, SEC) |
| 65 | Resume | HR / Recruitment |
| 66 | Safety Records | Safety / Compliance |
| 67 | Sales and Revenue | Finance / Sales |
| 68 | Software Product Development Files | Engineering / IT |
| 69 | Source Code | Engineering (23 languages, 70+ file extensions) |
| 70 | Standard Operating Procedures and Manuals | Operations |
| 71 | Statement of Accounts | Finance |
| 72 | Statement of Work | Legal / Project Management |
| 73 | Stock Manipulation | Communications Compliance (SEC, FINRA) |
| 74 | Tax Documents | Finance / Regulatory |
| 75 | Threat | Communications Compliance |
| 76 | Unauthorized Disclosure | Communications Compliance (FINRA, SEC) |
| 77 | Wire Transfer | Finance / Banking |

**Multi-language support for Communications Compliance classifiers:** Arabic, Chinese (Simplified), Chinese (Traditional), Dutch, English, French, German, Italian, Korean, Japanese, Portuguese, Spanish.

### 3.5 Unique ML Capabilities

- **Largest pre-trained classifier library:** 77 named classifiers across finance, legal, HR, healthcare, IT, communications compliance, and GenAI safety -- far more than any competitor.
- **GenAI-specific classifiers:** Prompt Shields (jailbreak detection) and Protected Material (copyright detection) are unique to Purview.
- **Contextual summary + keyword highlighting:** Most classifiers generate human-readable explanations of why content was flagged.
- **Custom trainable classifiers:** Customers can train their own models with seed documents.
- **Deep M365 integration:** Classifiers run natively across Exchange, SharePoint, OneDrive, Teams, and endpoint.
- **300+ Sensitive Information Types** with ML-powered confidence scoring beyond simple regex.

### 3.6 Limitations

- Model architecture details (which transformer, parameter count) not disclosed.
- Pre-trained classifiers overwhelmingly English-only (only Harassment, Profanity, and Threat support multiple languages).
- Custom trainable classifiers require significant seed data and training time.
- Tightly coupled to Microsoft 365 ecosystem.
- No GPU inference details disclosed.

---

## 4. Nightfall AI

### 4.1 ML Model Inventory

| Model Name / Component | Type | What It Detects | Training Approach | Accuracy Claims | Customer-Trainable? | Evidence Grade |
|---|---|---|---|---|---|---|
| PII/PCI Entity Detectors | CNN (Convolutional Neural Network) | SSN, credit cards, driver's licenses, passport numbers, bank accounts | Fine-tuned on 125M parameters | 90-95% precision; 1.5x more precise than AWS/Google/Microsoft for PII; 2x for PCI | No (pre-built) | A -- vendor docs + benchmarks |
| LLM Contextual Embeddings | Transformer (fine-tuned, 125M params) | Context evaluation around detected entities | LLM-generated embeddings feed into CNN for context | Reduces false positives by up to 85% vs regex | No | B -- vendor blog |
| File Classifiers (22 types) | LLM-based (transformer) | Intellectual property, source code, financial docs, legal docs, HR files, medical docs | Trained on document structure, purpose, semantics | Not disclosed | Yes (natural language descriptions) | A -- vendor docs + press release |
| Prompt-Based File Classifier | LLM (generative) | Custom document categories defined via natural language | Zero-shot / few-shot with natural language prompts | Not disclosed | Yes (no training data needed) | A -- vendor docs |
| Image Detectors | CNN | Credit/debit cards, driver's licenses, passports, SSN cards | Trained on image datasets of identity documents | Not disclosed | No | A -- vendor docs |
| Secret/Credential Detectors | ML + pattern matching | API keys, JWT tokens, passwords, database connection strings | Specialized models per vendor/secret type | Not disclosed | No | A -- vendor docs |

### 4.2 Detection Pipeline Architecture

```
                              Nightfall AI Detection Pipeline
                              ================================

  [Content Ingress: SaaS apps, GenAI tools, endpoints, APIs]
       |
       v
  +--------------------+     +---------------------+
  | Content Extraction  |---->| Entity Detection     |
  | (text, images,     |     | (CNN, 125M params,   |
  |  files, code)      |     |  4 CNN detectors for  |
  +--------------------+     |  PII/PCI)             |
                              +---------------------+
                                      |
                                      v
                              +---------------------+
                              | LLM Context Layer    |
                              | (Transformer, 125M   |
                              |  params, generates   |
                              |  embeddings for CNN) |
                              +---------------------+
                                      |
                         +------------+------------+
                         |                         |
                         v                         v
                +----------------+     +------------------------+
                | File Classifiers|    | Image Classifiers       |
                | (22 doc types,  |    | (CNN for ID docs,       |
                |  LLM-based)     |    |  cards, passports)      |
                +----------------+     +------------------------+
                         |                         |
                         v                         v
                +------------------------------------------------+
                | Confidence Scoring + Justification Metadata     |
                +------------------------------------------------+
                                      |
                                      v
                              [Alert / Quarantine / Redact]
```

### 4.3 LLM Usage

| Aspect | Detail |
|---|---|
| **Where used** | (1) Contextual embedding generation for CNN entity detectors; (2) File Classifiers for document-level classification; (3) Prompt-based custom file classifiers |
| **Model size** | 125 million parameters (transformer, fine-tuned) |
| **Runtime vs. offline** | Runtime -- all detection is inline/real-time |
| **Specific tasks** | Context evaluation around PII/PCI entities; document purpose/structure/intent analysis; zero-shot custom document classification via natural language |
| **Architecture** | CNN for entity detection + Transformer for contextual embeddings; 4 CNN detectors + 1 Transformer model working together |

### 4.4 Complete Detector List (Named)

**PII Detectors:**
- Social Security Number (US)
- Date of Birth
- Person's Name (first, middle, last)
- Email Address
- Phone Number (with area/country codes)
- Street Address (address, city, state, zip)
- IP Address
- MAC Address
- Age
- Gender
- Ethnicity
- Marital Status

**Financial / PCI Detectors:**
- Credit Card Number
- Debit Card Number
- Bank Account Number (multi-country: US, Canadian, etc.)
- Bank Routing Number (ABA)
- IBAN
- SWIFT/BIC Code

**PHI / Healthcare Detectors:**
- Medical Record Number
- Health Plan Beneficiary Number
- FDA Approval Number
- Drug Name
- Medical Condition / Diagnosis

**Identification Document Detectors:**
- US Driver's License Number (state-specific)
- US Passport Number
- US Social Security Card (image)
- Driver's License Image (any nation)
- Passport / Visa Image (any nation)
- National ID Numbers (multi-country)

**Country-specific Detectors:**
- Brazilian CPF, CNPJ, Passport
- Mexican CURP, RFC
- Canadian SIN, Bank Account
- Colombian NIT, Cedula
- UK National Insurance Number
- UK NHS Number
- India Aadhaar, PAN
- Australian TFN, Medicare

**Credentials & Secrets Detectors:**
- API Key (multi-vendor: AWS, Azure, GCP, GitHub, Slack, etc.)
- JWT Token
- Password (in code and natural language)
- Database Connection String
- Private Key (RSA, SSH, PGP)
- OAuth Token
- Webhook URL

**File Classifiers (22 document types):**
1. Internal Source Code & Engineering Artifacts
2. Product Roadmaps & R&D Specifications
3. Financial Statements & Revenue Reports
4. Tax Filings
5. Audit Documents
6. Compliance Records
7. Contracts
8. NDAs
9. Legal Agreements
10. HR Records & Personnel Files
11. Medical / Patient-Related Documents
12. Customer Lists
13. Invoices
14. Operational Documents
15. Confidential Internal Materials
16. Strategy Documents
17. M&A Materials
18. Board Communications
19. Proprietary Research
20. Marketing Materials
21. Insurance Documents
22. Regulatory Filings

### 4.5 Unique ML Capabilities

- **125M parameter model publicly documented** -- most transparent about model size among DLP vendors.
- **CNN + Transformer hybrid architecture** -- unique approach using CNN for entity detection with LLM-generated embeddings for context.
- **Zero-shot file classification** -- customers define new document types via natural language descriptions, no training data required.
- **Published benchmarks** -- claims 1.5x PII precision and 2x PCI precision vs. AWS, Google, Microsoft.
- **Confidence scoring + justification metadata** -- every detection includes explanation of why flagged.
- **Image-based detection** -- dedicated CNN models for identity document images from any nation.

### 4.6 Limitations

- 125M parameters is relatively small by LLM standards (closer to BERT-base than GPT-class).
- No customer-trainable entity detectors (only file classifiers are customizable).
- Primarily SaaS-focused; limited endpoint DLP capabilities.
- No EDM/IDM fingerprinting for structured data.
- Relatively new vendor compared to Symantec/Palo Alto.

---

## 5. Netskope (SkopeAI)

### 5.1 ML Model Inventory

| Model Name / Component | Type | What It Detects | Training Approach | Accuracy Claims | Customer-Trainable? | Evidence Grade |
|---|---|---|---|---|---|---|
| Document Classifiers (ML) | Transformer-based encoder | Source code, tax forms, patents, NDAs, bank statements, M&A docs | Pre-trained language model encodes documents into numeric vectors | Not disclosed | No (predefined) | B -- vendor whitepaper |
| Image Classifiers (CNN) | Convolutional Neural Network | Passports, driver's licenses, checks, payment cards, screenshots, medical cards, photo IDs | Deep learning on image datasets | Not disclosed | No (predefined) | B -- vendor whitepaper |
| Train Your Own Classifier (TYOC) | Transfer learning (CNN/Transformer) | Customer-defined categories (any document or image type) | Customer uploads 20-30 example documents; "train and forget" | Not disclosed | Yes (core feature) | A -- vendor docs + blog |
| Source Code Classifier | ML (deep learning) | Source code across multiple programming languages | Trained on code corpora | Not disclosed | No | B -- vendor blog |
| Context-Aware NLP | NLP / Transformer | Semantic understanding of surrounding text context | Pre-trained NLP model | Not disclosed | No | B -- vendor whitepaper |
| 3,000+ Data Classifiers | Pattern matching + ML | PII, PHI, PCI, credentials, multi-country regulatory data | Combination of regex, ML validation, and context | Not disclosed | Partially (custom regex) | B -- press release |

### 5.2 Detection Pipeline Architecture

```
                              Netskope SkopeAI Detection Pipeline
                              ====================================

  [Content Ingress: Inline (CASB/SWG), API (SaaS), SSPM, GenAI apps]
       |
       v
  +--------------------+     +---------------------+     +------------------------+
  | Content Extraction  |---->| Pattern Matching     |---->| ML Document Classifier |
  | (text via NLP,     |     | (3,000+ data         |     | (Transformer encoder   |
  |  images via CNN,   |     |  classifiers, regex, |     |  for text docs)        |
  |  OCR)              |     |  keyword matching)   |     +------------------------+
  +--------------------+     +---------------------+              |
                                                                  v
                              +---------------------+     +------------------------+
                              | TYOC Custom Models   |     | Image Classifier (CNN) |
                              | (customer-trained,  |     | (passports, IDs, cards,|
                              |  20-30 samples)     |     |  screenshots, checks)  |
                              +---------------------+     +------------------------+
                                      |                           |
                                      v                           v
                              +------------------------------------------------+
                              | Context-Aware NLP Layer                         |
                              | (reduces false positives, semantic analysis)    |
                              +------------------------------------------------+
                                                    |
                                                    v
                                              [Alert / Block / Coach]
```

### 5.3 LLM Usage

| Aspect | Detail |
|---|---|
| **Where used** | Document classification uses transformer-based encoder; NLP for context analysis |
| **Model size** | Not disclosed |
| **Runtime vs. offline** | Runtime -- real-time inline classification |
| **Specific tasks** | Document encoding to semantic vectors; image classification; context-aware false positive reduction |
| **LLM specifics** | Uses "pre-trained language model as encoder" (likely BERT-family); CNN for image classification; no explicit LLM/GPT-class model documented |

### 5.4 Complete Classifier Categories (Named)

**Predefined ML File Classifiers:**
- Passports
- Driver's Licenses
- Photo IDs
- Checks
- Payment Cards (credit/debit)
- Screenshots
- Source Code (multi-language)
- Tax Forms
- Patents
- Resumes
- Bank Statements
- Business Agreements / NDAs
- M&A Documents
- Medical Cards
- Credit Cards (image)

**Data Classifiers (3,000+ across regulatory frameworks):**
- PCI DSS (credit card numbers, cardholder data)
- HIPAA / HITECH (PHI, medical records)
- GDPR (EU personal data)
- CCPA (California consumer data)
- GLBA (financial data)
- SOX (financial reporting)
- PII: SSN, driver's license, passport, national ID, tax ID (multi-country)
- Credentials: API keys, passwords, tokens
- Financial: bank account, routing number, IBAN, SWIFT

### 5.5 Unique ML Capabilities

- **TYOC (Train Your Own Classifier):** Only 20-30 sample documents needed -- lowest barrier of any vendor. "Train and forget" approach with adaptive learning.
- **3,000+ data classifiers:** Largest claimed classifier count (includes regex + ML).
- **SkopeAI unified platform:** Single ML architecture spanning inline, API, SSPM, and GenAI protection.
- **Patent:** TYOC technology is patented.
- **CNN + Transformer combination:** Uses appropriate ML architecture per content type (CNN for images, transformer for text).

### 5.6 Limitations

- Model architecture details and parameter counts not publicly disclosed.
- No published accuracy benchmarks or third-party validations.
- "3,000+ classifiers" likely includes simple regex patterns alongside ML classifiers.
- No published research papers on their ML approach.
- TYOC accuracy depends heavily on quality and representativeness of customer-provided samples.

---

## 6. Forcepoint (AI Mesh / Getvisibility)

### 6.1 ML Model Inventory

| Model Name / Component | Type | What It Detects | Training Approach | Accuracy Claims | Customer-Trainable? | Evidence Grade |
|---|---|---|---|---|---|---|
| Small Language Model (SLM) | Transformer (small, CPU-runnable) | Semantic understanding of document content and intent | Pre-trained + fine-tuned for classification | "Highly precise" (no numbers) | No | B -- vendor blog |
| Deep Neural Network Classifiers | DNN | Sentiment analysis of document content | Pre-trained on labeled corpora | Not disclosed | No | B -- vendor blog |
| Bag of Words Classifier | BoW (classical ML) | Topic determination | Statistical model on word frequencies | Not disclosed | No | B -- vendor blog |
| Bayesian Inference Model | Naive Bayes / Bayesian | Predictive modeling of text categories | Bayesian probability estimation | Not disclosed | No | B -- vendor blog |
| Regex Filters | Pattern matching | Structured identifiers (SSN, CCN, etc.) | Rule-based | N/A | Yes (custom regex) | B -- vendor blog |
| Named Entity Recognition (NER) | NER model (likely transformer-based) | PII: names, addresses, phone numbers, emails | Pre-trained NER model | Not disclosed | No | B -- vendor blog |
| ARIA Assistant | LLM (conversational AI) | Policy recommendations, insight surfacing | Not disclosed | Not disclosed | No | B -- vendor marketing |

### 6.2 Detection Pipeline Architecture

```
                              Forcepoint AI Mesh Detection Pipeline
                              ======================================

  [Content Ingress: DSPM scan, DLP policy enforcement, email, endpoint]
       |
       v
  +--------------------+
  | Content Extraction  |
  | (text, metadata,   |
  |  file properties)  |
  +--------------------+
       |
       v
  +------------------------------------------------------------------+
  |                         AI MESH (~80 nodes)                       |
  |                                                                    |
  |  +-------------+  +-------------+  +--------------+  +----------+ |
  |  | Regex       |  | Bag of      |  | Bayesian     |  | NER      | |
  |  | Filters     |  | Words       |  | Inference    |  | Model    | |
  |  | (pattern    |  | (topic      |  | (predictive  |  | (PII     | |
  |  |  matching)  |  |  detection) |  |  text model) |  |  detect) | |
  |  +-------------+  +-------------+  +--------------+  +----------+ |
  |                                                                    |
  |  +-------------+  +-------------+  +---------------------------+  |
  |  | DNN         |  | SLM         |  | Data flows freely between |  |
  |  | Classifiers |  | (Semantic   |  | nodes as needed for       |  |
  |  | (sentiment) |  |  analysis)  |  | classification            |  |
  |  +-------------+  +-------------+  +---------------------------+  |
  +------------------------------------------------------------------+
       |
       v
  +------------------------------------------------------------------+
  | Classification Labels                                              |
  | (regulatory compliance labels + categories + subcategories + tags)|
  +------------------------------------------------------------------+
       |
       v
  +------------------------------------------------------------------+
  | ARIA AI Assistant (optional)                                       |
  | (surfaces insights, recommends protection, deploys policies)      |
  +------------------------------------------------------------------+
       |
       v
  [Classification Label Applied / DLP Policy Enforced]
```

### 6.3 LLM Usage

| Aspect | Detail |
|---|---|
| **Where used** | (1) SLM within AI Mesh for semantic document analysis; (2) ARIA conversational assistant for policy management |
| **Model size** | SLM: small enough to run on CPU (likely < 3B parameters). ARIA: not disclosed. |
| **Runtime vs. offline** | SLM: runtime classification within AI Mesh. ARIA: interactive assistant. |
| **Specific tasks** | SLM: semantic understanding, contextual classification. ARIA: 1,800+ classifier/policy template recommendations, natural language policy configuration. |
| **Key advantage** | SLM runs on CPU -- no GPU required. Enables cost-efficient deployment at scale. |

### 6.4 Classifier Categories

**AI Mesh classification labels (regulatory compliance):**
- GDPR
- HIPAA
- PCI DSS
- SOX
- CCPA
- GLBA

**Data categories and subcategories:**
- PII (names, addresses, phone numbers, emails, SSN, etc.)
- Financial Data
- Healthcare / Medical Data
- Legal Documents
- Intellectual Property
- Source Code
- Confidential Business Data
- Employee Data

**ARIA: 1,800+ classifiers and policy templates** (specific names not enumerated in public documentation)

### 6.5 Unique ML Capabilities

- **AI Mesh architecture:** ~80 interconnected AI nodes with heterogeneous models (SLM, DNN, BoW, Bayesian, NER, regex) -- data flows freely between nodes. Most architecturally novel approach.
- **SLM on CPU:** No GPU required for classification -- significant cost/deployment advantage.
- **Getvisibility heritage:** Acquired AI classification startup with deep NLP expertise.
- **ARIA conversational assistant:** LLM-powered policy management is unique among DLP vendors.
- **Self-learning:** System continuously learns and delivers predictive classifications.
- **Explainable AI:** AI Mesh produces explainable classification decisions.

### 6.6 Limitations

- Model details (architecture, parameter counts, training data) not disclosed.
- "1,800+ classifiers" not individually named in public documentation.
- No published benchmarks or accuracy metrics.
- AI Mesh is primarily for data discovery/classification (DSPM), not inline DLP inspection.
- Relatively new offering (Getvisibility acquisition 2024).
- SLM may lack the capability of larger models for nuanced content understanding.

---

## 7. Zscaler DLP

### 7.1 ML Model Inventory

| Model Name / Component | Type | What It Detects | Training Approach | Accuracy Claims | Customer-Trainable? | Evidence Grade |
|---|---|---|---|---|---|---|
| LLM Classification | Large Language Model (transformer) | Abstract/nuanced sensitive data: financial planning docs, medical content, manufacturing content, complex document types | Not disclosed | "Finds data that could never be found before" (no metrics) | No | B -- vendor blog |
| Predefined DLP Dictionaries | Pattern matching + ML validation | PII, PCI, PHI, credentials, financial data, medical info | Pre-built with regex + validation logic | Not disclosed | Editable (tune sensitivity) | A -- help portal |
| Exact Data Match (EDM) | Hashing / fingerprinting | Structured data (database records, PII in tables) | Customer indexes specific data records | Near 100% precision for indexed data | Yes (customer indexes data) | A -- help portal |
| Indexed Document Match (IDM) | Document fingerprinting | Unstructured documents (contracts, IP, designs) | Customer fingerprints sensitive documents | Not disclosed | Yes (customer indexes docs) | A -- help portal |
| OCR Engine | CNN (likely) | Text in images | Pre-trained OCR model | Not disclosed | No | A -- help portal |
| AI/ML URL Categorization | CNN + NLP (text + visual analysis) | Web URL classification into security categories | Trained on URL text content and page visuals | Not disclosed | No | B -- vendor blog |
| Trainable Classifiers | ML (not specified) | Customer-defined data types and patterns | Customer-trained | Not disclosed | Yes | B -- vendor blog |

### 7.2 Detection Pipeline Architecture

```
                              Zscaler DLP Detection Pipeline
                              ===============================

  [Content Ingress: ZIA inline proxy, ZPA, Endpoint, GenAI apps]
       |
       v
  +--------------------+     +---------------------+
  | Content Extraction  |---->| DCM: Described       |
  | (text, images via  |     | Content Matching     |
  |  OCR, metadata)    |     | (dictionaries,       |
  +--------------------+     |  keywords, regex)    |
                              +---------------------+
                                      |
                         +------------+------------+
                         |            |            |
                         v            v            v
                +----------+  +----------+  +----------+
                | EDM      |  | IDM      |  | LLM      |
                | (exact   |  | (indexed |  | Classif. |
                |  data    |  |  document|  | (nuanced |
                |  match)  |  |  match)  |  |  content)|
                +----------+  +----------+  +----------+
                         |            |            |
                         v            v            v
                +------------------------------------------------+
                | DLP Engine (combines signals, applies policies) |
                +------------------------------------------------+
                                      |
                                      v
                              [Alert / Block / Caution / Isolate]
```

### 7.3 LLM Usage

| Aspect | Detail |
|---|---|
| **Where used** | LLM Classification as a separate detection method alongside DCM, EDM, IDM |
| **Model size** | Not disclosed |
| **Runtime vs. offline** | Runtime -- available across Web, SaaS, IaaS, and Endpoint |
| **Specific tasks** | Detecting abstract/nuanced sensitive data that regex cannot find: financial planning documents, medical content, manufacturing content, complex business documents |
| **Key positioning** | LLM Classification presented as essential complement to regex, not replacement |

### 7.4 Predefined DLP Dictionary / Engine Categories (Named)

**Predefined DLP Engines:**
- CCPA (California Consumer Privacy Act)
- HIPAA (Health Insurance Portability and Accountability Act)
- GLBA (Gramm-Leach-Bliley Act)
- PCI DSS (Payment Card Industry Data Security Standard)
- Finance Engine
- Credentials and Secrets Engine

**Predefined Dictionaries (within engines):**
- Social Security Numbers (US)
- Tax Identification Number (US)
- Names (US)
- Credit Cards (with Luhn validation)
- ABA Bank Routing Number
- International Bank Account Number (IBAN)
- Financial Statements
- Medical Information
- Diseases Information
- Drugs Information
- Credentials and Secrets
- Driver's License (United States)
- Passport Number (European Union)
- Bulgaria Uniform Civil Number
- VAT Numbers (multiple EU countries)
- Medical Information Dictionaries (expanded)
- PII Dictionaries (expanded)

### 7.5 Unique ML Capabilities

- **LLM Classification as a product feature:** Explicitly named and marketed as a distinct detection method; available inline across all traffic types (Web, SaaS, IaaS, Endpoint).
- **Inline LLM at cloud scale:** Running LLM classification on the world's largest security cloud (Zscaler Zero Trust Exchange).
- **GenAI app protection:** LLM classification specifically applied to monitor data going into GenAI applications.
- **EDM + IDM + LLM combination:** Can layer all three detection methods in a single policy.

### 7.6 Limitations

- LLM model details (architecture, parameter count, serving infrastructure) completely undisclosed.
- Predefined dictionary list appears smaller than competitors (no image classifiers, no document-type classifiers).
- No published benchmarks for LLM classification accuracy.
- No customer-trainable ML classifiers (only trainable classifiers mentioned briefly, not detailed).
- EDM/IDM require customer effort to index data.

---

## 8. Skyhigh Security DLP

### 8.1 ML Model Inventory

| Model Name / Component | Type | What It Detects | Training Approach | Accuracy Claims | Customer-Trainable? | Evidence Grade |
|---|---|---|---|---|---|---|
| ML Text Auto Classifiers | Multi-class + binary classifiers (statistical + neural) | Financial reports, patient records, patents, source code, legal docs | Skyhigh-trained on internal corpus (no customer data) | Confidence scoring; threshold-based | No | A -- vendor docs |
| ML Image Auto Classifiers | CNN (likely) | ID documents, payment cards, medical images | Pre-trained on image datasets | Not disclosed | No | A -- vendor docs |
| AI RegEx Generator | LLM (generative, conversational) | Generates Google RE2-compliant regex from natural language descriptions | Backed by LLM | N/A (generates rules, not classifications) | N/A | A -- vendor press release |
| Data Identifier Rules | Pattern matching + validation | PII, financial, healthcare, identity documents (multi-country) | Pre-built algorithms with validation | Not disclosed | No (predefined) | A -- vendor docs |

### 8.2 Detection Pipeline Architecture

```
                              Skyhigh Security DLP Detection Pipeline
                              ========================================

  [Content Ingress: CASB (sanctioned + shadow), SWG, Endpoint]
       |
       v
  +--------------------+     +---------------------+     +------------------------+
  | Content Extraction  |---->| Data Identifier      |---->| ML Auto Classifiers    |
  | (text, images,     |     | Rules (pattern       |     | (text: multi-class +   |
  |  up to 50MB)       |     |  matching + Luhn,    |     |  binary classifiers;   |
  +--------------------+     |  checksum validation)|     |  image: CNN)           |
                              +---------------------+     +------------------------+
                                                                |
                                                                v
                                                   +-------------------------+
                                                   | Confidence Scoring      |
                                                   | (threshold-based,       |
                                                   |  whole-document score)  |
                                                   +-------------------------+
                                                                |
                                                                v
                                                   +-------------------------+
                                                   | DLP Policy Engine       |
                                                   | (classifications +      |
                                                   |  data identifiers +     |
                                                   |  fingerprints)          |
                                                   +-------------------------+
                                                                |
                                                                v
                                              [Alert / Block / Encrypt / Coach]
```

### 8.3 LLM Usage

| Aspect | Detail |
|---|---|
| **Where used** | AI RegEx Generator (conversational interface for creating regex rules); Skyhigh AI assistant |
| **Model size** | Not disclosed |
| **Runtime vs. offline** | Offline -- LLM used for rule creation, not runtime classification |
| **Specific tasks** | Generating Google RE2-compliant regular expressions from natural language; policy recommendations |
| **Key distinction** | LLM is used for RULE CREATION, not data classification. ML Auto Classifiers handle classification without LLM. |

### 8.4 Data Identifier Categories (Named)

**Regional PII categories:**
- African Personal Identity
- Asia-Pacific Personal Identity
- European Personal Identity
- Middle Eastern Personal Identity
- North American Personal Identity
- South American Personal Identity

**Functional categories:**
- Financial (credit cards, bank accounts, routing numbers)
- Healthcare (medical record numbers, insurance IDs)
- Information Technology (credentials, IP addresses)
- Cryptocurrency Addresses
- U.S. Driver's License Numbers (state-specific)
- Miscellaneous

**ML Auto Classifier categories:**
- Financial Reports and Statements
- Patient Records
- Patents
- Source Code
- ID Files (passports, driver's licenses, national IDs)

### 8.5 Unique ML Capabilities

- **AI RegEx Generator:** First vendor to offer LLM-powered regex generation from natural language -- lowers the barrier for creating custom DLP rules.
- **Whole-document confidence scoring:** ML classifiers score the entire document (not individual matches), providing holistic classification.
- **50MB file processing:** Can classify large text and image files up to 50MB.
- **Privacy-preserving training:** Models trained exclusively on Skyhigh's own corpus; no customer data used.
- **McAfee DLP heritage:** Inherited mature DLP engine from McAfee acquisition.

### 8.6 Limitations

- ML Auto Classifiers are NOT customer-trainable (cannot create custom ML categories).
- Relatively few ML classifier categories compared to Microsoft Purview or Nightfall.
- Model architecture details not disclosed (referred to generically as "statistical methods and neural network techniques").
- LLM used only for regex generation, not classification.
- No image-based document classification beyond ID documents.
- Legacy data identifiers being deprecated in favor of data classifications.

---

## 9. Cross-Vendor Comparison Matrix

### 9.1 ML Architecture Comparison

| Vendor | Primary ML Type | LLM Usage in Classification | Customer-Trainable ML | Published Model Details | GPU Inference |
|---|---|---|---|---|---|
| **Palo Alto** | 5th-gen DNN + LLM augmentation | Yes (contextual augmentation) | Yes (custom doc types) | CCP paper (AAAI '24) | Yes (NVIDIA Triton) |
| **Symantec** | VML (statistical/SVM-like) | No | Yes (VML training) | No | No |
| **Microsoft Purview** | Transformer classifiers | Yes (implicit in classifiers + GenAI) | Yes (custom classifiers) | No | Not disclosed |
| **Nightfall** | CNN + Transformer hybrid | Yes (contextual embeddings + file classifiers) | Yes (prompt-based file classifiers) | 125M params disclosed | Not disclosed |
| **Netskope** | Transformer encoder + CNN | Implicit (transformer encoder) | Yes (TYOC, 20-30 samples) | No | Not disclosed |
| **Forcepoint** | AI Mesh (SLM + DNN + BoW + Bayesian) | Yes (SLM in mesh + ARIA) | No | No | No (CPU-only SLM) |
| **Zscaler** | LLM Classification | Yes (explicit LLM classifier) | Partially (trainable classifiers, limited detail) | No | Not disclosed |
| **Skyhigh** | Statistical + Neural network | No (LLM for regex gen only) | No | No | Not disclosed |

### 9.2 Pre-trained Classifier Count Comparison

| Vendor | Pre-trained ML Classifiers | Data Patterns / Dictionaries | Total Claimed |
|---|---|---|---|
| **Palo Alto** | 100+ DNN classifiers | 250+ data patterns | 350+ |
| **Symantec** | 0 (VML is customer-trained) | 30+ data identifiers + policy templates | 30+ |
| **Microsoft Purview** | 77 trainable classifiers | 300+ SITs | 377+ |
| **Nightfall** | 100+ entity detectors + 22 file classifiers | N/A (ML-first) | 122+ |
| **Netskope** | ~15 file classifiers | 3,000+ data classifiers | 3,000+ (includes regex) |
| **Forcepoint** | 1,800+ (AI Mesh + ARIA) | Integrated into AI Mesh | 1,800+ |
| **Zscaler** | LLM classifier (1 model, multiple categories) | ~25 predefined dictionaries | ~26+ |
| **Skyhigh** | ~5 ML auto classifier categories | Multi-country data identifiers | ~50+ |

### 9.3 Detection Technique Matrix

| Technique | Palo Alto | Symantec | Microsoft | Nightfall | Netskope | Forcepoint | Zscaler | Skyhigh |
|---|---|---|---|---|---|---|---|---|
| Regex / Pattern | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| Exact Data Match (EDM) | Yes | Yes | Yes | No | Yes | No | Yes | No |
| Document Fingerprint (IDM) | No | Yes | No | No | No | No | Yes | No |
| DNN / Deep Learning | Yes | No | Yes | Yes | Yes | Yes | No* | Yes |
| Transformer / LLM | Yes | No | Yes | Yes | Yes | Yes | Yes | No |
| CNN (Image) | Yes | No | Yes | Yes | Yes | No | No | Yes |
| Customer-Trainable ML | Yes | Yes | Yes | Yes | Yes | No | Partial | No |
| OCR | Yes | Yes | Yes | Yes | Yes | No | Yes | Yes |
| NER | Yes* | No | Yes* | Yes | Yes* | Yes | No | No |

*Implied but not explicitly documented as separate NER component.

---

## 10. Key Takeaways for Our DLP Product

### 10.1 Architecture Patterns

1. **Layered detection is universal:** Every vendor uses regex/pattern matching as the first layer, with ML as a secondary enrichment/validation layer. No vendor relies solely on ML.

2. **CNN for images, Transformer for text:** This is the standard split across Palo Alto, Nightfall, Netskope, and Skyhigh. Forcepoint uniquely uses SLM on CPU.

3. **LLM as augmentation, not replacement:** Even Zscaler's "LLM Classification" sits alongside EDM/IDM/DCM. LLMs add contextual understanding but don't replace structured detection.

4. **Confidence scoring is standard:** Every ML-based vendor produces confidence scores; threshold-based policy enforcement is the norm.

### 10.2 ML Model Insights

5. **125M parameters is the disclosed benchmark:** Nightfall's 125M-parameter model achieves 90-95% precision. This suggests BERT-base-sized models are sufficient for entity detection.

6. **SLMs are emerging:** Both Palo Alto and Forcepoint explicitly use Small Language Models (< 3B params) for cost-efficient, CPU-runnable classification. This is the trend.

7. **Customer-trainable ML is a differentiator:** Netskope (20-30 samples), Symantec (50-500 samples), Microsoft (50-500 samples), and Palo Alto (30+ samples) all offer it. Nightfall's zero-shot approach (natural language descriptions) is the most advanced.

8. **CCP (semi-supervised learning) solves the labeled data problem:** Palo Alto's AAAI '24 paper demonstrates how to train DLP classifiers with noisy, imbalanced data -- directly relevant to enterprise deployments where labeled sensitive documents are scarce.

### 10.3 Competitive Gaps to Exploit

9. **No vendor publishes comprehensive benchmarks:** There is no industry-standard DLP ML benchmark. Nightfall's comparison to AWS/Google/Microsoft is the closest.

10. **Symantec is frozen in time:** VML is 10+ year-old technology with no deep learning. The largest installed base is running the oldest ML.

11. **Forcepoint's AI Mesh is architecturally innovative but unproven:** ~80 interconnected AI nodes is unique but no accuracy metrics or benchmarks exist.

12. **Microsoft Purview has the most classifiers but is M365-locked:** 77 pre-trained classifiers is unmatched, but useless outside Microsoft ecosystem.

13. **No vendor does real-time LLM inference at line speed:** All vendors either use smaller models (SLM/BERT-class) for real-time or apply LLM classification asynchronously/offline.

### 10.4 Recommended Technical Direction

Based on this research:

| Decision | Recommendation | Rationale |
|---|---|---|
| **Entity detection** | CNN or BERT-base (100-125M params) | Nightfall's 125M-param CNN+Transformer proves this is sufficient for 90-95% precision |
| **Document classification** | Fine-tuned transformer encoder (BERT/RoBERTa class) | Netskope and Palo Alto both use transformer encoders for document classification |
| **Contextual augmentation** | SLM (1-3B params) for inline; larger LLM for offline | Follows Palo Alto's hybrid SLM/LLM pattern and Forcepoint's CPU-runnable SLM |
| **Image classification** | CNN (ResNet/EfficientNet class) | Standard across Nightfall, Netskope, Skyhigh for ID document detection |
| **Customer trainability** | Few-shot or zero-shot with LLM | Nightfall's natural-language approach is the most user-friendly and innovative |
| **Training approach** | Semi-supervised (CCP-inspired) | Addresses the fundamental problem of scarce labeled sensitive data in enterprise |
| **Inference** | GPU for throughput (NVIDIA Triton) | Palo Alto documented 3x cost reduction moving to GPU inference |

---

## Sources

### Palo Alto Networks
- [Enterprise DLP Product Page](https://www.paloaltonetworks.com/sase/enterprise-data-loss-prevention)
- [Transforming Data Security with AI-Powered Classification](https://www.paloaltonetworks.com/blog/sase/transforming-data-security-with-ai-powered-classification/)
- [CCP Algorithm in Action (Unit 42)](https://unit42.paloaltonetworks.com/contrastive-credibility-propagation/)
- [CCP PyTorch Implementation (GitHub)](https://github.com/PaloAltoNetworks/ccp-as-pytorch)
- [Preventing Data Loss at Enterprise Scale with NVIDIA](https://www.paloaltonetworks.com/blog/2024/10/data-loss-at-enterprise-scale-with-nvidia/)
- [How SLMs are Revolutionizing Cybersecurity](https://live.paloaltonetworks.com/t5/community-blogs/how-small-language-models-are-quietly-revolutionizing/ba-p/1233840)
- [Data Patterns, Document Types, and Data Profiles](https://docs.paloaltonetworks.com/enterprise-dlp/getting-started/data-patterns-and-data-filtering-profiles)
- [Embracing AI-Powered Data Security](https://www.paloaltonetworks.com/blog/sase/embracing-ai-powered-data-security-for-the-digital-age/)

### Symantec / Broadcom
- [VML Best Practices Guide (PDF)](https://techdocs.broadcom.com/content/dam/broadcom/techdocs/symantec-security-software/information-security/data-loss-prevention/generated-pdfs/Symantec_DLP_15.5_VML_Best_Practices_Guide.pdf)
- [Introducing VML](https://techdocs.broadcom.com/us/en/symantec-security-software/information-security/data-loss-prevention/16-0-1/about-data-loss-prevention-policies-v27576413-d327e9/introducing-vector-machine-learning-vml-v40065952-d327e33606.html)
- [Library of Policy Templates](https://techdocs.broadcom.com/us/en/symantec-security-software/information-security/data-loss-prevention/16-0/about-data-loss-prevention-policies-v27576413-d327e9/library-of-policy-templates.html)
- [DLP Machine Learning Whitepaper](https://www.ioactive.com/wp-content/uploads/2012/11/b-dlp_machine_learning.WP_en-us.pdf)

### Microsoft Purview
- [Trainable Classifier Definitions](https://learn.microsoft.com/en-us/purview/trainable-classifiers-definitions)
- [Learn About Trainable Classifiers](https://learn.microsoft.com/en-us/purview/trainable-classifiers-learn-about)
- [Get Started with Trainable Classifiers](https://learn.microsoft.com/en-us/purview/trainable-classifiers-get-started-with)

### Nightfall AI
- [AI-Based DLP Detectors](https://www.nightfall.ai/ai-based-dlp-detectors)
- [GenAI Detectors Revolutionizing Cloud DLP](https://www.nightfall.ai/blog/nightfalls-new-genai-detectors-are-revolutionizing-the-cloud-dlp-landscape-heres-how)
- [Detector Glossary](https://help.nightfall.ai/detection_platform/detection_glossary)
- [Detectors Documentation](https://help.nightfall.ai/detection_platform/detectors)
- [AI File Classifier Detectors (Press Release)](https://www.prnewswire.com/news-releases/nightfall-unveils-industry-first-ai-powered-file-classifiers-to-close-the-blind-spot-legacy-dlp-misses-ip-exfiltration-302618540.html)
- [What Types of Detectors Are Supported](https://help.nightfall.ai/developer-api/faqs/detector_types)

### Netskope
- [SkopeAI: AI-Powered Data Protection](https://www.netskope.com/blog/skopeai-ai-powered-data-protection-that-mimics-the-human-brain)
- [TYOC for Image Data Protection](https://www.netskope.com/blog/train-your-own-classifier-tyoc-for-image-data-protection)
- [File Classifiers Documentation](https://docs.netskope.com/en/file-classifiers/)
- [ML-Based Source Code Classifier](https://www.netskope.com/blog/the-importance-of-a-machine-learning-based-source-code-classifier)
- [Protecting Data Using AI and ML (Whitepaper)](https://www.netskope.com/es/wp-content/uploads/2023/11/protecting-data-using-artificial-intelligence-and-machine-learning.pdf)

### Forcepoint
- [How Forcepoint AI Classification Works](https://www.forcepoint.com/blog/insights/how-forcepoint-ai-classification-works)
- [The Real Deal Behind AI Mesh](https://www.forcepoint.com/blog/insights/forcepoint-dspm-ai-mesh)
- [AI Mesh Product Page](https://www.forcepoint.com/ai-mesh)
- [Forcepoint Classification powered by Getvisibility](https://www.forcepoint.com/blog/insights/forcepoint-classification-artificial-intelligence)
- [Forcepoint Data Classification (PDF)](https://www.forcepoint.com/sites/default/files/2024-08/solution-brief-forcepoint-data-classification-en.pdf)

### Zscaler
- [Data Security Innovations (Zenith Live '25)](https://www.zscaler.com/blogs/product-insights/cutting-edge-data-security-innovations-zenith-live-25)
- [DLP Do-Over: Learning From Gen AI Mistakes](https://www.zscaler.com/blogs/product-insights/dlp-do-over-learning-gen-ai-mistakes)
- [Understanding Predefined DLP Dictionaries](https://help.zscaler.com/zia/understanding-predefined-dlp-dictionaries)
- [About DLP Dictionaries](https://help.zscaler.com/zia/about-dlp-dictionaries)
- [What Is Exact Data Match](https://www.zscaler.com/resources/security-terms-glossary/what-is-exact-data-match)

### Skyhigh Security
- [About Usage of AI in Skyhigh DLP](https://success.skyhighsecurity.com/Skyhigh_and_AI/Usage_of_AI_in_Skyhigh_DLP/About_Usage_of_AI_in_Skyhigh_DLP)
- [ML Auto Classifiers](https://success.skyhighsecurity.com/Skyhigh_Data_Loss_Prevention/02_Advance_DLP_Capabilities/AI_Powered_DLP_Capabilities/AI-ML_Auto_Classifiers)
- [AI RegEx Generator (Press Release)](https://www.skyhighsecurity.com/about/newsroom/newswire/skyhigh-security-introduces-first-ai-powered-dlp-assistant-regular-expression-generator-for-instant-data-classifiers.html)
- [Data Identifiers](https://success.skyhighsecurity.com/Skyhigh_Data_Loss_Prevention/Data_Identifiers)
- [Enhanced Security Using AI and ML](https://success.skyhighsecurity.com/Skyhigh_AI/Leverage_AI_and_ML_Capabilities_in_the_Skyhigh_SSE_Platform/01_Enhance_Security_and_Data_Protection_Using_AI_and_ML)
