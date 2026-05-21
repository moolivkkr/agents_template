# Capability Taxonomy: Proofpoint -- Authoring Policies
> Discovered: 2026-05-21 | Method: documentation analysis across 28 sources
> Products covered: Essentials, PPS/PoD, TAP, DLP, Encryption, ITM, Data Security, CASB, Isolation, SAT, Archive

---

## Taxonomy

### 1. Email Filtering Policies (Proofpoint Essentials)

| # | Sub-Capability | Complexity | Doc Coverage | Priority | Source |
|---|---------------|-----------|-------------|----------|--------|
| 1.1 | Inbound Filter Creation (conditions + actions) | Moderate | HIGH [S1] | P0 | [S1, S17] |
| 1.2 | Outbound Filter Creation | Moderate | HIGH [S1] | P0 | [S1, S17] |
| 1.3 | Filter Scope Management (Company/Group/User) | Simple | HIGH [S1] | P0 | [S1] |
| 1.4 | Filter Priority and Ordering | Simple | HIGH [S1] | P1 | [S1, S17] |
| 1.5 | Filter Condition Types (10 types) | Moderate | HIGH [S1] | P0 | [S1] |
| 1.6 | Filter Operators (7 types) | Simple | HIGH [S1] | P0 | [S1] |
| 1.7 | Filter Actions (Allow/Quarantine/TLS enforcement) | Moderate | HIGH [S1] | P0 | [S1] |
| 1.8 | Filter Lifecycle (Create/Edit/Duplicate/Delete/Enable/Disable) | Simple | HIGH [S1] | P1 | [S1] |
| 1.9 | Safe/Blocked Sender Lists (Organization + User) | Simple | HIGH [S1] | P0 | [S1] |
| 1.10 | Filter Search | Simple | HIGH [S1] | P2 | [S1] |

### 2. PPS/PoD Rule Creation and Email Firewall

| # | Sub-Capability | Complexity | Doc Coverage | Priority | Source |
|---|---------------|-----------|-------------|----------|--------|
| 2.1 | Policy Route Configuration | Complex | LOW [S2] | P0 | [S2, S16] |
| 2.2 | Email Firewall Rule Creation | Complex | LOW [S2, S20] | P0 | [S2, S20] |
| 2.3 | Rule Conditions Configuration | Complex | LOW [S2] | P0 | [S2] |
| 2.4 | Quarantine Folder Management | Moderate | LOW [S16] | P1 | [S16, S19] |
| 2.5 | Disposition Type Selection | Moderate | LOW [S2] | P0 | [S2] |
| 2.6 | Custom Spam Rules | Moderate | LOW [S2] | P1 | [S2] |
| 2.7 | Dictionary Management | Moderate | LOW [S2] | P1 | [S2] |
| 2.8 | Module Precedence Configuration | Complex | LOW [S2] | P1 | [S2] |
| 2.9 | Proofpoint Dynamic Reputation (PDR) Configuration | Moderate | LOW [S2] | P1 | [S2] |
| 2.10 | Recipient Verification (RV) Setup | Moderate | LOW [S2] | P1 | [S2] |
| 2.11 | SMTP Rate Control Configuration | Simple | LOW [S2] | P2 | [S2] |
| 2.12 | End User Digest Configuration | Moderate | LOW [S2] | P2 | [S2] |

### 3. Spam Policy Configuration

| # | Sub-Capability | Complexity | Doc Coverage | Priority | Source |
|---|---------------|-----------|-------------|----------|--------|
| 3.1 | Spam Threshold Adjustment | Simple | HIGH [S1] | P0 | [S1] |
| 3.2 | Bulk Email Quarantine Toggle | Simple | HIGH [S1] | P1 | [S1] |
| 3.3 | Stamp & Forward Configuration | Simple | HIGH [S1] | P1 | [S1] |
| 3.4 | Easy Spam Reporting Setup | Simple | HIGH [S1] | P2 | [S1] |
| 3.5 | Inbound Sender DNS Checks | Moderate | HIGH [S1] | P1 | [S1] |
| 3.6 | Per-User Spam Threshold Override | Simple | HIGH [S1] | P1 | [S1] |
| 3.7 | Organization-Wide Spam Settings Push | Simple | HIGH [S1] | P2 | [S1] |
| 3.8 | PPS Spam Module Classifier Configuration | Complex | LOW [S2] | P1 | [S2] |
| 3.9 | PPS Spam Module Tuning (Best Practices) | Complex | LOW [S2] | P2 | [S2] |

### 4. Virus Policy Configuration

| # | Sub-Capability | Complexity | Doc Coverage | Priority | Source |
|---|---------------|-----------|-------------|----------|--------|
| 4.1 | AV Bypass List Management | Simple | HIGH [S1] | P1 | [S1] |
| 4.2 | PPS Multi-Layer Virus Protection Config | Moderate | LOW [S2] | P1 | [S2] |
| 4.3 | PPS Zero-Hour Anti-Virus Config | Complex | LOW [S2] | P1 | [S2] |
| 4.4 | Group-Level Virus Policy (encrypted file exceptions) | Moderate | LOW [S2] | P2 | [S2] |

### 5. Data Loss Prevention (DLP) Policies

| # | Sub-Capability | Complexity | Doc Coverage | Priority | Source |
|---|---------------|-----------|-------------|----------|--------|
| 5.1 | DLP Policy Creation (Essentials) | Moderate | MODERATE [S1, S18] | P0 | [S1, S18, S24] |
| 5.2 | Smart Identifier Selection and Configuration | Moderate | MODERATE [S24] | P0 | [S18, S24] |
| 5.3 | Custom Dictionary Creation and Upload | Moderate | MODERATE [S18] | P0 | [S18] |
| 5.4 | Custom Regular Expression Patterns | Moderate | MODERATE [S18] | P1 | [S18] |
| 5.5 | Document Fingerprinting Configuration | Complex | LOW [S14] | P1 | [S14, S18] |
| 5.6 | DLP Action Configuration (Block/Quarantine/Encrypt/Allow) | Moderate | MODERATE [S18] | P0 | [S18] |
| 5.7 | DLP Exception Management (Recipient/Sender/Content) | Moderate | MODERATE [S18] | P1 | [S18] |
| 5.8 | DLP + Encryption Integration | Complex | MODERATE [S14] | P0 | [S14, S18] |
| 5.9 | PPS Regulatory Compliance Module | Complex | LOW [S14] | P1 | [S14] |
| 5.10 | PPS Digital Asset Security Module | Complex | LOW [S14] | P1 | [S14] |
| 5.11 | Adaptive Email DLP (Behavioral AI) | Complex | LOW [S23] | P1 | [S23] |
| 5.12 | Unified DLP for Email (PPS 8.22.x) | Complex | LOW | P1 | Search only |
| 5.13 | 240+ Pre-built Classifier Library | Simple | MODERATE [S24] | P0 | [S24] |

### 6. Email Encryption Policies

| # | Sub-Capability | Complexity | Doc Coverage | Priority | Source |
|---|---------------|-----------|-------------|----------|--------|
| 6.1 | Policy-Based Encryption Configuration | Complex | MODERATE [S14] | P0 | [S14] |
| 6.2 | Encryption Trigger Rules (content, origin, TLS fallback) | Complex | MODERATE [S14] | P0 | [S14] |
| 6.3 | Encryption Filter Creation (Essentials) | Moderate | LOW (auth wall) | P0 | [S17] |
| 6.4 | Message Expiration Policy | Simple | MODERATE [S14] | P1 | [S14] |
| 6.5 | Message Revocation | Simple | MODERATE [S14] | P2 | [S14] |
| 6.6 | Trusted Partner Encryption Setup | Complex | MODERATE [S14] | P1 | [S14] |
| 6.7 | Secure Reader Branding | Simple | LOW | P2 | [S14] |
| 6.8 | Key Management (Proofpoint Key Service) | Complex | MODERATE [S14] | P1 | [S14] |
| 6.9 | End User Key Management Delegation | Simple | MODERATE [S14] | P2 | [S14] |
| 6.10 | Classified Document Encryption (Microsoft IAM) | Complex | MODERATE [S14] | P2 | [S14] |
| 6.11 | Inbound Encrypted Email Decryption at Gateway | Complex | MODERATE [S14] | P1 | [S14] |

### 7. Targeted Attack Protection (TAP) Policies

| # | Sub-Capability | Complexity | Doc Coverage | Priority | Source |
|---|---------------|-----------|-------------|----------|--------|
| 7.1 | URL Defense Configuration | Complex | LOW [S2] | P0 | [S2] |
| 7.2 | URL Rewrite Options | Moderate | LOW [S2] | P1 | [S2] |
| 7.3 | Attachment Defense Configuration | Complex | LOW [S2] | P0 | [S2] |
| 7.4 | Per-Group TAP Enablement | Moderate | MODERATE [S22] | P0 | [S22] |
| 7.5 | Sender Exemption from TAP | Simple | MODERATE [S21] | P1 | [S21] |
| 7.6 | TAP URL Isolation for VIPs/VAPs | Complex | MODERATE [S15] | P1 | [S15] |
| 7.7 | TAP Dashboard Settings | Complex | LOW [S2] | P2 | [S2] |

### 8. ITM/ObserveIT Policy Configuration

| # | Sub-Capability | Complexity | Doc Coverage | Priority | Source |
|---|---------------|-----------|-------------|----------|--------|
| 8.1 | System Policy Settings (Recording/Monitoring) | Moderate | HIGH [S4] | P0 | [S4] |
| 8.2 | Key Logging Configuration | Simple | HIGH [S4] | P1 | [S4] |
| 8.3 | Screen Capture Configuration | Moderate | HIGH [S4] | P1 | [S4] |
| 8.4 | Session Timeout Configuration | Simple | HIGH [S4] | P1 | [S4] |
| 8.5 | Recording Notification / Stealth Mode | Simple | HIGH [S4] | P1 | [S4] |
| 8.6 | Insider Threat Library Rule Activation/Deactivation | Moderate | HIGH [S5] | P0 | [S5] |
| 8.7 | Alert Rule Creation | Complex | MODERATE [S6] | P0 | [S6] |
| 8.8 | Prevention Rule Creation | Complex | MODERATE [S6] | P0 | [S6] |
| 8.9 | Policy Rule Creation | Complex | MODERATE [S6] | P0 | [S6] |
| 8.10 | Rule Import/Export | Simple | HIGH [S6] | P1 | [S6] |
| 8.11 | User Group / Risk Level Targeting | Moderate | HIGH [S5] | P1 | [S5] |
| 8.12 | Identification Services (Secondary Login) | Complex | MODERATE [S4] | P2 | [S4] |
| 8.13 | Agent API Configuration | Complex | MODERATE [S4] | P2 | [S4] |

### 9. Data Security / Endpoint DLP Policies

| # | Sub-Capability | Complexity | Doc Coverage | Priority | Source |
|---|---------------|-----------|-------------|----------|--------|
| 9.1 | Agent Policy Creation (Add/Edit) | Moderate | HIGH [S8] | P0 | [S8] |
| 9.2 | DLP-Only vs ITM Signal Type Selection | Simple | HIGH [S7] | P0 | [S7] |
| 9.3 | If/Then Condition Logic Configuration | Complex | HIGH [S9] | P0 | [S9] |
| 9.4 | Agent Policy Priority Management | Simple | HIGH [S8] | P1 | [S8] |
| 9.5 | Default Account Policy Customization | Moderate | HIGH [S7] | P1 | [S7] |
| 9.6 | Detection Rule Creation (from scratch/conditions/Threat Library) | Complex | HIGH [S10] | P0 | [S10] |
| 9.7 | Detection Rule Severity Assignment | Simple | HIGH [S10] | P0 | [S10] |
| 9.8 | Detection Rule Notification Configuration (SMS/email/webhook) | Moderate | HIGH [S10] | P1 | [S10] |
| 9.9 | Prevention Rule Creation | Complex | HIGH [S11] | P0 | [S11] |
| 9.10 | Prevention Rule Actions (Block/Prompt/Allow) | Moderate | HIGH [S11] | P0 | [S11] |
| 9.11 | Data Redaction for GenAI | Complex | MODERATE [S11] | P1 | [S11] |
| 9.12 | File Retention Rules | Moderate | MODERATE [S11] | P2 | [S11] |
| 9.13 | Endpoint Rule On-Demand Policy | Moderate | MODERATE [S12] | P2 | [S12] |
| 9.14 | Rule Versioning and Rollback | Simple | HIGH [S10] | P2 | [S10] |
| 9.15 | Tag Management for Rules | Simple | HIGH [S10] | P2 | [S10] |
| 9.16 | Realm Assignment and Rule Sets | Complex | MODERATE [S10] | P1 | [S10] |

### 10. CASB Policies

| # | Sub-Capability | Complexity | Doc Coverage | Priority | Source |
|---|---------------|-----------|-------------|----------|--------|
| 10.1 | CASB Threat Protection Policies | Complex | LOW [S13] | P1 | [S13] |
| 10.2 | CASB Access Control Policies | Complex | LOW [S13] | P1 | [S13] |
| 10.3 | CASB DLP Policies (Cloud Applications) | Complex | LOW [S13, S25] | P0 | [S13, S25] |
| 10.4 | CASB Application Visibility / Governance | Moderate | LOW [S13] | P1 | [S13] |
| 10.5 | CASB Infrastructure Security Assessment | Complex | LOW [S13] | P2 | [S13] |
| 10.6 | CASB DLP Detector/Rule Creation | Complex | LOW [S25] | P0 | [S25] |

### 11. Browser/Email Isolation Policies

| # | Sub-Capability | Complexity | Doc Coverage | Priority | Source |
|---|---------------|-----------|-------------|----------|--------|
| 11.1 | Browsing Policy Creation (per user group) | Moderate | MODERATE [S15] | P0 | [S15] |
| 11.2 | Upload/Download Restriction Policies | Moderate | MODERATE [S15] | P0 | [S15] |
| 11.3 | Redirect Rule Configuration | Moderate | MODERATE [S15] | P1 | [S15] |
| 11.4 | TAP URL Isolation Integration | Complex | MODERATE [S15] | P1 | [S15] |
| 11.5 | Inline DLP for Isolation Sessions | Complex | MODERATE [S15] | P1 | [S15] |
| 11.6 | User Input Controls (Credential Theft Prevention) | Moderate | MODERATE [S15] | P1 | [S15] |
| 11.7 | VIP/VAP List Import from TAP | Simple | MODERATE [S15] | P2 | [S15] |

### 12. Security Awareness Training Policies

| # | Sub-Capability | Complexity | Doc Coverage | Priority | Source |
|---|---------------|-----------|-------------|----------|--------|
| 12.1 | Scheduled Training Assignment Creation | Moderate | HIGH [S3] | P0 | [S3] |
| 12.2 | Duration Training Assignment Creation | Moderate | HIGH [S3] | P0 | [S3] |
| 12.3 | Training Module Selection and Ordering | Simple | HIGH [S3] | P0 | [S3] |
| 12.4 | Training Notification Configuration | Simple | HIGH [S3] | P1 | [S3] |
| 12.5 | Training Reminder Scheduling | Simple | HIGH [S3] | P1 | [S3] |
| 12.6 | Drive-by Phishing Campaign Creation | Moderate | HIGH [S3] | P0 | [S3] |
| 12.7 | Data Entry Phishing Campaign Creation | Moderate | HIGH [S3] | P0 | [S3] |
| 12.8 | Classic Attachment Phishing Campaign | Moderate | HIGH [S3] | P0 | [S3] |
| 12.9 | Attachment Phishing Campaign (PDF/DOCX/XLSX) | Moderate | HIGH [S3] | P0 | [S3] |
| 12.10 | Follow-Up Campaign (Performance-Based) | Complex | HIGH [S3] | P1 | [S3] |
| 12.11 | Phishing Template Selection and Customization | Moderate | HIGH [S3] | P0 | [S3] |
| 12.12 | Teachable Moment Selection (Category/Language) | Simple | HIGH [S3] | P0 | [S3] |
| 12.13 | Campaign Scheduling (Specific vs Random) | Simple | HIGH [S3] | P1 | [S3] |
| 12.14 | Campaign Lifecycle (Edit/Clone/Cancel/Archive/Delete) | Simple | HIGH [S3] | P1 | [S3] |
| 12.15 | Campaign User/Group Selection | Simple | HIGH [S3] | P0 | [S3] |
| 12.16 | Data Collection Period Configuration | Simple | HIGH [S3] | P2 | [S3] |

### 13. Archive Retention and Legal Hold Policies

| # | Sub-Capability | Complexity | Doc Coverage | Priority | Source |
|---|---------------|-----------|-------------|----------|--------|
| 13.1 | Retention Period Configuration | Simple | MODERATE [S27] | P0 | [S27] |
| 13.2 | Company-Wide Legal Hold Activation | Simple | MODERATE [S27] | P0 | [S27] |
| 13.3 | Archive Search Configuration | Moderate | LOW | P1 | [S1] |

### 14. Quarantine Management Policies

| # | Sub-Capability | Complexity | Doc Coverage | Priority | Source |
|---|---------------|-----------|-------------|----------|--------|
| 14.1 | Quarantine Category Configuration (6 types) | Moderate | MODERATE [S19] | P0 | [S19] |
| 14.2 | End User Release Permissions | Simple | MODERATE [S19] | P0 | [S19] |
| 14.3 | Quarantine Digest Configuration (frequency, time, exclusions) | Moderate | HIGH [S1] | P0 | [S1, S19] |
| 14.4 | Quarantine Retention Period | Simple | HIGH [S1] | P1 | [S1] |
| 14.5 | Admin-Only Release Categories (phishing, malware, spoofed) | Simple | MODERATE [S19] | P1 | [S19] |
| 14.6 | PPS Quarantine Folder Management | Moderate | LOW [S16] | P1 | [S16] |

### 15. API-Based Policy Management

| # | Sub-Capability | Complexity | Doc Coverage | Priority | Source |
|---|---------------|-----------|-------------|----------|--------|
| 15.1 | Essentials REST API -- Filter/Organization Management | Complex | LOW [S26] | P1 | [S26] |
| 15.2 | PPS REST API -- Quarantine Operations | Complex | MODERATE [S16] | P1 | [S16] |
| 15.3 | PPS REST API -- User Management | Complex | MODERATE [S16] | P2 | [S16] |
| 15.4 | PPS REST API -- Smart Search | Complex | MODERATE [S16] | P2 | [S16] |

---

## Summary

| Metric | Count |
|--------|-------|
| Capability groups | 15 |
| Total sub-capabilities | 137 |
| Simple | 48 |
| Moderate | 56 |
| Complex | 33 |

### Coverage Distribution

| Doc Coverage Level | Sub-capabilities | Percentage |
|-------------------|-----------------|------------|
| HIGH | 56 | 41% |
| MODERATE | 45 | 33% |
| LOW | 36 | 26% |

### Priority Distribution

| Priority | Sub-capabilities | Percentage |
|----------|-----------------|------------|
| P0 (Critical) | 58 | 42% |
| P1 (High) | 55 | 40% |
| P2 (Medium) | 24 | 18% |

### Products by Documentation Depth

| Product Line | Sub-capabilities | Coverage Level | Notes |
|-------------|-----------------|----------------|-------|
| Proofpoint Essentials (Email Filtering) | 10 | HIGH | Full admin guide available (dated 2014) |
| Proofpoint Essentials (Spam) | 9 | HIGH | Configuration fully documented |
| Proofpoint Essentials (Virus) | 4 | MIXED | Basic config HIGH, PPS config LOW |
| Data Security / Endpoint DLP | 16 | HIGH | Official docs accessible, well-structured |
| ITM/ObserveIT | 13 | HIGH | Official docs accessible, version 7.18.0 |
| Security Awareness Training | 16 | HIGH | Full admin guide available (dated 2020) |
| DLP Policies | 13 | MODERATE | Mix of official product pages and third-party |
| Email Encryption | 11 | MODERATE | Data sheet level; admin UI not documented |
| Isolation | 7 | MODERATE | Data sheet + product brief; admin console unknown |
| TAP | 7 | LOW | Training outline + KB articles only |
| PPS/PoD Rules | 12 | LOW | Training outline only; admin guide behind auth |
| CASB | 6 | LOW | Overview only; policy config behind auth |
| Archive | 3 | MODERATE | Auth-wall limited |
| Quarantine | 6 | MODERATE | Mix of official and third-party |
| API | 4 | LOW | Endpoint docs behind auth wall |

### Key Risk Areas
1. **PPS/PoD admin guide is entirely behind authentication** -- 12 sub-capabilities at LOW coverage; this is the most deployed Proofpoint product in enterprises
2. **CASB policy authoring is almost undocumented** in accessible sources -- 6 sub-capabilities at LOW coverage
3. **Essentials admin guide is from 2014** -- UI and features have changed substantially; grade-D sources used to fill gaps
4. **TAP configuration details inaccessible** -- URL/Attachment Defense policy screens not documented
5. **API documentation requires authentication** -- Automation capabilities not fully mapped
