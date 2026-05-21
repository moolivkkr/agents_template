# Capability Taxonomy: Proofpoint — Authoring Policies

> Generated: 2026-05-21 | Products: Essentials, PPS/PoD, TAP, Data Security, ITM, CASB, Isolation, SAT, Archive
> Total sub-capabilities: 137 | Simple: 48 | Moderate: 56 | Complex: 33
> Priority P0 (Critical): 58 | P1 (High): 55 | P2 (Medium): 24

---

```
Proofpoint — Authoring Policies
├── 1. Email Filtering Policies (Essentials)          MODERATE | API: PARTIAL
│   ├── 1.1  Inbound Filter Creation                  Moderate | HIGH coverage
│   ├── 1.2  Outbound Filter Creation                 Moderate | HIGH coverage
│   ├── 1.3  Filter Scope (Company/Group/User)        Simple   | HIGH coverage
│   ├── 1.4  Filter Priority and Ordering             Simple   | HIGH coverage
│   ├── 1.5  Filter Condition Types (10 types)        Moderate | HIGH coverage
│   ├── 1.6  Filter Operators (7 types)               Simple   | HIGH coverage
│   ├── 1.7  Filter Actions (Allow/Quarantine/etc.)   Moderate | HIGH coverage
│   ├── 1.8  Filter Lifecycle (Create/Edit/Delete)    Simple   | HIGH coverage
│   ├── 1.9  Safe/Blocked Sender Lists                Simple   | HIGH coverage
│   └── 1.10 Filter Search                            Simple   | HIGH coverage
│
├── 2. PPS/PoD Rule Creation and Email Firewall       COMPLEX  | API: PARTIAL
│   ├── 2.1  Policy Route Configuration               Complex  | LOW coverage
│   ├── 2.2  Email Firewall Rule Creation             Complex  | LOW coverage
│   ├── 2.3  Rule Conditions Configuration            Complex  | LOW coverage
│   ├── 2.4  Quarantine Folder Management             Moderate | LOW coverage
│   ├── 2.5  Disposition Type Selection               Moderate | LOW coverage
│   ├── 2.6  Custom Spam Rules                        Moderate | LOW coverage
│   ├── 2.7  Dictionary Management                    Moderate | LOW coverage
│   ├── 2.8  Module Precedence Configuration          Complex  | LOW coverage
│   ├── 2.9  PDR Configuration                        Moderate | LOW coverage
│   ├── 2.10 Recipient Verification Setup             Moderate | LOW coverage
│   ├── 2.11 SMTP Rate Control                        Simple   | LOW coverage
│   └── 2.12 End User Digest Configuration            Moderate | LOW coverage
│
├── 3. Spam Policy Configuration                      SIMPLE   | API: PARTIAL
│   ├── 3.1  Spam Threshold Adjustment                Simple   | HIGH coverage
│   ├── 3.2  Bulk Email Quarantine Toggle             Simple   | HIGH coverage
│   ├── 3.3  Stamp & Forward Configuration            Simple   | HIGH coverage
│   ├── 3.4  Easy Spam Reporting Setup                Simple   | HIGH coverage
│   ├── 3.5  Inbound Sender DNS Checks                Moderate | HIGH coverage
│   ├── 3.6  Per-User Spam Threshold Override         Simple   | HIGH coverage
│   ├── 3.7  Organization-Wide Spam Settings Push     Simple   | HIGH coverage
│   ├── 3.8  PPS Spam Module Classifier Config        Complex  | LOW coverage
│   └── 3.9  PPS Spam Module Tuning                   Complex  | LOW coverage
│
├── 4. Virus Policy Configuration                     SIMPLE   | API: GAP
│   ├── 4.1  AV Bypass List Management (Essentials)   Simple   | HIGH coverage
│   ├── 4.2  PPS Multi-Layer Virus Protection         Moderate | LOW coverage
│   ├── 4.3  PPS Zero-Hour Anti-Virus                 Moderate | LOW coverage
│   └── 4.4  Group-Level Encrypted File Exceptions    Moderate | LOW coverage
│
├── 5. Email DLP Policies                             COMPLEX  | API: PARTIAL
│   ├── 5.1  DLP Filter Policy Creation (Essentials)  Complex  | MODERATE coverage
│   ├── 5.2  Smart Identifier Configuration           Complex  | LOW coverage
│   ├── 5.3  DLP Dictionary Creation                  Moderate | MODERATE coverage
│   ├── 5.4  Custom Regex Pattern Definition          Moderate | MODERATE coverage
│   ├── 5.5  PPS Email Firewall DLP Rule              Complex  | LOW coverage
│   ├── 5.6  PPS Smart Identifier Integration         Complex  | LOW coverage
│   ├── 5.7  Adaptive Email DLP Configuration         Complex  | MODERATE coverage
│   └── 5.8  DLP-to-Encryption Trigger Setup         Complex  | MODERATE coverage
│
├── 6. Email Encryption Policies                      COMPLEX  | API: PARTIAL
│   ├── 6.1  Outbound Encryption Filter Creation      Complex  | MODERATE coverage
│   ├── 6.2  TLS Enforcement / Fallback Config        Moderate | MODERATE coverage
│   ├── 6.3  Trusted Partner TLS Configuration        Moderate | MODERATE coverage
│   ├── 6.4  Message Expiration Configuration         Moderate | LOW coverage
│   ├── 6.5  Message Revocation                       Moderate | LOW coverage
│   ├── 6.6  PPS Encryption Rule Configuration        Complex  | LOW coverage
│   ├── 6.7  Secure Reader Branding                   Simple   | LOW coverage
│   ├── 6.8  Key Management                           Complex  | LOW coverage
│   ├── 6.9  End User Key Mgmt Delegation             Moderate | LOW coverage
│   ├── 6.10 Classified Document Encryption           Moderate | LOW coverage
│   └── 6.11 Inbound Decryption                       Moderate | LOW coverage
│
├── 7. Targeted Attack Protection (TAP)               COMPLEX  | API: GAP
│   ├── 7.1  URL Defense Enable + Global Config       Complex  | MODERATE coverage
│   ├── 7.2  Attachment Defense Configuration         Complex  | MODERATE coverage
│   ├── 7.3  Per-Group TAP Enablement                 Moderate | MODERATE coverage
│   ├── 7.4  TAP Sender Exemptions                    Simple   | MODERATE coverage
│   ├── 7.5  TAP Alert Configuration                  Complex  | LOW coverage
│   ├── 7.6  URL Isolation for VIPs/VAPs              Complex  | MODERATE coverage
│   └── 7.7  TAP Dashboard and Reporting              Moderate | LOW coverage
│
├── 8. Insider Threat Management (ITM / ObserveIT)    COMPLEX  | API: GAP
│   ├── 8.1  System Policy Settings                   Complex  | HIGH coverage
│   ├── 8.2  Alert Rule Creation (Threat Library)     Complex  | HIGH coverage
│   ├── 8.3  Prevention Rule Creation                 Complex  | HIGH coverage
│   ├── 8.4  Rule Import/Export                       Simple   | HIGH coverage
│   ├── 8.5  Windows Stealth/Privacy Policy           Moderate | LOW coverage
│   ├── 8.6  Unix Notification Configuration          Moderate | MODERATE coverage
│   └── 8.7  Identification Services Configuration    Moderate | LOW coverage
│
├── 9. Data Security / Endpoint DLP                   COMPLEX  | API: PARTIAL
│   ├── 9.1  Data Classes / Detectors Configuration   Complex  | MODERATE coverage
│   ├── 9.2  Realm Configuration                      Complex  | LOW coverage
│   ├── 9.3  Detection Rule Creation                  Complex  | HIGH coverage
│   ├── 9.4  Prevention Rule Creation                 Complex  | HIGH coverage
│   ├── 9.5  Rule Set Management                      Moderate | HIGH coverage
│   ├── 9.6  Agent Policy (General Settings)          Complex  | HIGH coverage
│   ├── 9.7  Agent Policy (Details / If-Then Logic)   Complex  | HIGH coverage
│   └── 9.8  GenAI Data Redaction (2025+)             Complex  | MODERATE coverage
│
├── 10. CASB Policies                                 COMPLEX  | API: GAP
│    ├── 10.1 Cloud App Connector Setup               Complex  | LOW coverage
│    ├── 10.2 User / Group Sync Configuration         Moderate | LOW coverage
│    ├── 10.3 CASB DLP Rule Creation                  Complex  | LOW coverage
│    ├── 10.4 CASB Threat Rule Creation               Complex  | LOW coverage
│    └── 10.5 IaaS Infrastructure Assessment          Complex  | LOW coverage
│
├── 11. Browser / Email Isolation                     COMPLEX  | API: GAP
│    ├── 11.1 Isolation Console Setup                 Complex  | LOW coverage
│    ├── 11.2 Redirect Rule Creation                  Complex  | MODERATE coverage
│    ├── 11.3 VIP/VAP User Assignment                 Complex  | MODERATE coverage
│    ├── 11.4 Upload/Download Restrictions            Complex  | LOW coverage
│    ├── 11.5 Email Isolation Configuration           Complex  | LOW coverage
│    └── 11.6 User Input Controls                     Moderate | LOW coverage
│
├── 12. Security Awareness Training (SAT)             COMPLEX  | API: GAP
│    ├── 12.1 Training Assignment (Scheduled)         Complex  | HIGH coverage
│    ├── 12.2 Training Assignment (Duration)          Complex  | HIGH coverage
│    ├── 12.3 Phishing Campaign (Drive-by)            Complex  | HIGH coverage
│    ├── 12.4 Phishing Campaign (Data Entry)          Complex  | HIGH coverage
│    ├── 12.5 Phishing Campaign (Attachment)          Complex  | HIGH coverage
│    ├── 12.6 Follow-Up Campaign Configuration        Complex  | HIGH coverage
│    └── 12.7 Campaign Reporting and Analytics        Moderate | MODERATE coverage
│
├── 13. Archive & Retention Policies                  SIMPLE   | API: GAP
│    ├── 13.1 Retention Period Configuration          Simple   | MODERATE coverage
│    ├── 13.2 Legal Hold Configuration                Simple   | MODERATE coverage
│    └── 13.3 Archive Search Configuration            Moderate | LOW coverage
│
└── 14. Quarantine Management                         MODERATE | API: PARTIAL
     ├── 14.1 Quarantine Category Config              Moderate | MODERATE coverage
     ├── 14.2 Quarantine Digest Configuration         Simple   | MODERATE coverage
     ├── 14.3 Quarantine Retention Period             Simple   | HIGH coverage
     ├── 14.4 Admin Quarantine Console Operations     Moderate | MODERATE coverage
     ├── 14.5 End-User Self-Release Configuration     Simple   | MODERATE coverage
     └── 14.6 PPS Quarantine Folder Management        Moderate | LOW coverage
```

---

## Summary by Complexity

| Complexity | Count | Capability Groups |
|-----------|-------|-----------------|
| COMPLEX | 33 | Email DLP, Email Encryption, PPS Rules, TAP, ITM, Endpoint DLP, CASB, Isolation, SAT |
| MODERATE | 56 | Most sub-capabilities within above groups; Quarantine Management |
| SIMPLE | 48 | Spam, Virus, Archive, Filter Lifecycle operations, Sender Lists |

## Summary by Documentation Coverage

| Coverage Level | Count | Notes |
|---------------|-------|-------|
| HIGH | ~40 sub-capabilities | Essentials admin guide (2014), ITM 7.18.0, Data Security (current) |
| MODERATE | ~55 sub-capabilities | Video sources, data sheets, KB articles |
| LOW | ~42 sub-capabilities | Behind auth wall: PPS admin guide, CASB full docs, TAP admin guide |
| INCOMPLETE | ~5+ sub-capabilities | CASB field names, Isolation browsing policy fields, ITM stealth policy |

## Summary by Priority

| Priority | Count | Description |
|---------|-------|-------------|
| P0 — Critical | 58 | Must work for basic protection; blocking if missing |
| P1 — High | 55 | Significantly impacts security posture if absent |
| P2 — Medium | 24 | Optimization, advanced use cases |
