# Compliance Officer — Workflow Summary

> Generated: 2026-05-21 | Product: Proofpoint (Essentials + Data Security + Archive + SAT)
> Primary user of: Email DLP, Email Encryption, Endpoint DLP, Archive, Quarantine (audit), SAT

---

## Role Overview

The Compliance Officer is responsible for ensuring that Proofpoint configurations satisfy regulatory requirements (HIPAA, GDPR, PCI-DSS, SOX, FINRA, etc.) and that appropriate data protection controls are in place for email and endpoint channels. They typically do not author policies directly but must validate that policies are correct, that archive retention periods match regulatory minimums, that DLP coverage is complete, and that security awareness training is tracked. In organizations without a dedicated DLP Admin, this persona may configure Archive retention and SAT assignments directly.

**Typical profile:** Compliance Manager, Data Protection Officer, Risk & Compliance Analyst, or Information Governance Specialist.

**Prerequisite knowledge:** Regulatory requirements applicable to the organization (HIPAA, PCI-DSS, etc.), audit documentation standards, basic email security concepts.

---

## Weekly Flow

```
+-------------------+   +-------------------+   +--------------------+   +-------------------+
| 1. DLP Policy     | > | 2. Archive        | > | 3. SAT Program     | > | 4. Audit Review   |
| Compliance Audit  |   | Retention Verify  |   | Tracking           |   | + Reporting       |
| (30-60 min/week)  |   | (15 min/month)    |   | (30-60 min/month)  |   | (1-2 hrs/quarter) |
|                   |   |                   |   |                    |   |                   |
| Filter policies   |   | Settings >        |   | Assignment status, |   | Quarantine logs,  |
| DLP quarantine    |   | Retention period  |   | phishing results,  |   | DLP incidents,    |
| Endpoint DLP      |   | vs regulation     |   | completion rates   |   | encryption events |
| API: PARTIAL      |   | API: GAP          |   | API: GAP           |   | API: PARTIAL      |
+-------------------+   +-------------------+   +--------------------+   +-------------------+
```

---

## Capability Touchpoints

| Capability | How This Persona Uses It | Frequency | Complexity | API Coverage |
|-----------|-------------------------|-----------|------------|-------------|
| Email DLP | Verify DLP filters cover required data types; review DLP quarantine | Weekly | COMPLEX | PARTIAL |
| Email Encryption | Confirm encryption triggers cover regulated outbound channels | Monthly | COMPLEX | PARTIAL |
| Endpoint DLP | Review detection rules cover required data types; verify rule sets assigned | Monthly | COMPLEX | PARTIAL |
| Archive Retention | Configure/verify retention period matches regulatory requirement | Initial + change-driven | SIMPLE | GAP |
| Archive Legal Hold | Activate/deactivate for litigation or regulatory investigations | As-needed | SIMPLE | GAP |
| Quarantine Management | Audit policy-quarantined messages; verify admin-only for Policy category | Monthly | MODERATE | PARTIAL |
| SAT (Training) | Create/monitor training assignments; track completion for compliance evidence | Quarterly | COMPLEX | GAP |
| SAT (Phishing) | Run phishing simulations; track click rates for compliance reporting | Quarterly | COMPLEX | GAP |

---

## Narrative

### 1. DLP Policy Compliance Audit (30-60 min/week)

**Screen:** Security Settings > Email > Filter Policies (audit view); Data Security > Detection Rules (audit view)

**Actions:**
- Review all active DLP filters in Filter Policies — verify each required regulation (HIPAA PHI, PCI PAN, GDPR personal data, PII) has an active filter
- Audit Policy quarantine category settings: confirm Policy category is admin-only AND excluded from user digest (two independent settings — both required)
- Check for filters with "Stop Processing Additional Filters" enabled that are ABOVE DLP filters in priority — these could be silently suppressing DLP evaluation
- Review Endpoint DLP detection rules: confirm active rules reference populated Rule Sets, and Rule Sets are assigned to Agent Policies
- Spot-check: verify detection rules have explicit severity assigned (unset severity defaults to Informational — invisible in most dashboards)
- Export/document current filter list and rule list as compliance evidence

**Decisions:**
- Is the Policy quarantine category visible to users in the digest? If yes, DLP-flagged message subjects are readable by the senders — fix by excluding Policy category from digest AND setting it to admin-only release.
- Are there any Detection Rules with no Rule Set assignment? If yes, those rules are silently not firing — assign Rule Sets.
- Are any DLP filters below an allow-list filter with "Stop Processing" enabled? If yes, the DLP filter may never evaluate.

**Output:** DLP coverage map; compliance gap list; evidence documentation

**Automation:** PARTIAL AUTOMATE — Essentials API can list filters; Data Security API can list detection rules. Verification of coverage gaps against regulatory requirements is manual.

**Gotchas:**
- User-scope filters override Company DLP policies — a user's personal safe-sender list can allow DLP-governed mail to bypass the DLP filter [V20 — Grade B]
- "Stop Processing Additional Filters" on any higher-priority filter silently disables downstream DLP rules — must audit all higher-priority filters for this toggle [V20 — Grade B]
- Detection Rules with no Rule Set assignment look active but fire on no agents — no warning in UI [S10 — Grade A]
- DLP-flagged subjects visible in user digest if Policy category not excluded from digest AND not set to admin-only — both controls must be set [S19 — Grade D]
- Adaptive Email DLP uses pre-send user warnings, not admin quarantine — cannot use it as the sole DLP control if admin review of violations is required [V22 — Grade B]
- Allowing user self-release for Policy category allows users to bypass compliance controls [S19 — Grade D]

---

### 2. Archive Retention Period Verification (15 min/month)

**Screen:** Proofpoint Essentials Archive admin > Settings > Retention

**Actions:**
- Navigate to Archive Settings > Retention — verify Years + Months fields match regulatory requirement
- Consult the regulatory reference table to confirm correct period:
  - HIPAA: 6 years minimum
  - SEC Rule 17a-4: 7 years for broker-dealers
  - FINRA Rule 4511: 3-6 years
  - SOX Section 802: 7 years
  - GDPR: varies by data category
- Navigate to Settings > Legal Hold — confirm legal hold state (Active/Inactive) is correct for current legal situation
- Document current retention period and legal hold state for compliance records

**Decisions:**
- If retention period is at default (12 months), this is insufficient for all regulated industries — must be changed immediately before messages accumulate and are deleted
- If legal hold is Active and no litigation is pending, it must be deactivated (storage grows indefinitely when active — costs compound)
- If legal hold is being deactivated after a hold period, coordinate with legal counsel — messages that aged past retention date during the hold may be immediately eligible for deletion upon deactivation

**Output:** Retention period confirmed; legal hold state documented

**Automation:** MANUAL ONLY — Archive retention and legal hold configuration has no API coverage in accessible sources [S27 — Grade A]

**Gotchas:**
- Default 12-month retention is insufficient for nearly all regulated industries [S27 — Grade A] — HIGH severity
- Legal hold is company-wide only — no per-custodian hold documented for Essentials [S27 — Grade A] — blocks targeted e-discovery workflows
- Archive and quarantine are separate systems — quarantined messages are NOT automatically archived [S1, S27 — Grade A]
- Increasing retention period after archive accumulates messages does not retroactively save already-deleted messages [U — ASSUMPTION; standard archive behavior]
- Deactivating legal hold may cause immediate deletion of messages that aged past retention during the hold — consult legal counsel first [U — ASSUMPTION]
- Maximum retention is 10 years — organizations requiring longer must evaluate alternative archive [S27 — Grade A]

---

### 3. SAT Training Program Tracking (30-60 min/month)

**Screen:** Security Awareness > Assignments (view completion rates); Security Awareness > Campaigns (view phishing results)

**Actions:**
- Review assignment completion rates for each active Scheduled or Duration assignment
- Check overdue users (incomplete after Due Date) — note: 30-day grace period exists after Due Date but is HIDDEN from users
- Review phishing campaign results: Click Rate, Submitted Data Rate, Reported Phishing (requires PhishAlarm deployment)
- For Follow-Up campaigns: verify source campaign is in Completed or Archived state before configuring follow-up targeting
- Export reports for compliance audit trail (completion evidence for regulatory training requirements)

**New assignment creation (if needed):**
- Navigate to Security Awareness > Assignments > New Assignment
- Select Scheduled (fixed date window for all users) or Duration (rolling window per-user from enrollment)
- Set Start Date (note: notification fires at 12:01 AM Eastern — adjust for global teams)
- Set Due Date (set 30 days before actual deadline to use grace period as real enforcement window)
- Set High Priority only if this assignment must preempt ALL other in-progress training — activating High Priority immediately locks all other training for all assigned users

**Output:** Completion rate reports; phishing simulation results for compliance evidence

**Automation:** MANUAL ONLY — SAT configuration and reporting has no API coverage in accessible sources [S3 — Grade A]

**Gotchas:**
- Start date notification fires at 12:01 AM Eastern Time — for UTC+8 or later regions, this lands the previous calendar day [S3 — Grade A]
- 30-day grace period after Due Date is hidden from end users — set formal Due Date 30 days early for accurate compliance deadlines [S3 — Grade A]
- High Priority assignment immediately locks all other in-progress training — never enable on an active assignment [S3 — Grade A]
- Campaign cannot be edited after launch — must cancel and recreate to change user list or template [S3 — Grade A]
- "Reported Phishing" criterion in Follow-Up campaigns requires PhishAlarm deployment — without it, criterion returns zero users [S3 — Grade A]
- Data Entry campaigns: passwords NOT collected but legal/privacy consultation still required in many jurisdictions [S3 — Grade A]
- Phishing campaign click rates are systematically underreported with the default 7-day data collection period — extend to 14-30 days [S3 — Grade A]
- S3 source is 6 years old (April 2020) — UI and feature set may have changed [S3 — Grade A stale]

---

### 4. Audit Review and Reporting (1-2 hrs/quarter)

**Screens:** Quarantine console, Filter Policy list, Detection Rule list, Archive Settings, SAT Reports

**Actions:**
- Pull quarantine statistics for Policy-category messages over the quarter (volume, release rate, release by whom)
- Document DLP quarantine review cadence as compliance evidence (who reviews, how often, escalation path)
- Verify encryption filters are active and generating events for outbound regulated-content mail
- Pull SAT completion rates and phishing click rates — format for compliance report
- Verify archive retention period has not been modified (auditors look for unauthorized changes)
- Document any legal hold activations/deactivations with legal justification

**Output:** Quarterly compliance report package; evidence for regulatory audit

**Automation:** PARTIAL AUTOMATE — PPS quarantine statistics via API [S16]; filter list readable via Essentials API [S26]; report generation is largely manual

---

## Prerequisites

- Archive add-on provisioned with retention period set correctly (Day 1 requirement)
- DLP filters and quarantine categories configured by Email Security Admin
- SAT module provisioned; PhishAlarm deployed if "Reported Phishing" follow-up campaigns needed
- Data Security (Endpoint DLP) provisioned and agent policies active for endpoint DLP audit
- Admin role with read access to all relevant consoles (may differ from write-access admin)

---

## Common Pain Points

| # | Pain Point | Capability | Source | Impact |
|---|-----------|-----------|--------|--------|
| 1 | Default 12-month archive retention causes compliance failure before anyone notices | Archive | S27 — Grade A | CRITICAL — data loss + audit failure |
| 2 | Legal hold is company-wide only — per-custodian hold required for e-discovery | Archive | S27 — Grade A | HIGH — e-discovery process limitation |
| 3 | DLP-flagged message subjects visible in user digest — information leakage | Quarantine | S19 — Grade D | HIGH — compliance gap |
| 4 | Detection Rules silently never fire when no Rule Set assigned | Endpoint DLP | S10 — Grade A | HIGH — silent compliance gap |
| 5 | "Stop Processing" on allow filters silently bypasses DLP — invisible to compliance auditors | Email Filtering | V20 — Grade B | HIGH — undetectable compliance gap |
| 6 | SAT completion rates underreported — 7-day data collection too short | SAT | S3 — Grade A | MEDIUM — inaccurate compliance evidence |
| 7 | S3 SAT source 6 years old — documented behaviors may not match current product | SAT | S3 — stale | MEDIUM — documentation reliability |

---

## Automation Summary

| Step | API Coverage | Automation Status | Blocker (if any) |
|------|-------------|-------------------|------------------|
| 1. DLP filter list audit | PARTIAL | PARTIAL AUTOMATE | Coverage gap analysis requires manual judgment |
| 2. Archive retention check | GAP | MANUAL ONLY | No API for archive settings |
| 3. SAT completion tracking | GAP | MANUAL ONLY | No API for SAT reports |
| 4. Quarantine stats pull | PARTIAL | PARTIAL AUTOMATE | PPS via API; Essentials stats manual |
| 4. Endpoint DLP rule audit | PARTIAL | PARTIAL AUTOMATE | Rule list via Data Security API; coverage analysis manual |

## Time Estimate

| Scenario | Time | Notes |
|---------|------|-------|
| Initial archive retention + legal hold setup | 30 min | Configuration + documentation |
| Weekly DLP compliance audit | 30-60 min | Filter review + quarantine spot-check |
| Monthly SAT tracking | 30-60 min | Completion rates + phishing results |
| Quarterly compliance report | 2-4 hours | Full evidence package across all capabilities |

## Complexity: MODERATE
(configuration surface is limited for this persona; complexity comes from cross-capability verification and compliance-specific consequence severity)
