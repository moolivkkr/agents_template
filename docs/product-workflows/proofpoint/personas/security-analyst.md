# Security Analyst — Workflow Summary

> Generated: 2026-05-21 | Product: Proofpoint (TAP + ITM + Endpoint DLP + CASB + Quarantine)
> Primary user of: TAP Dashboard, Quarantine console, ITM alerts, Endpoint DLP incidents, CASB alerts, Isolation monitoring

---

## Role Overview

The Security Analyst is a reactive responder who investigates threats and incidents surfaced by Proofpoint detections. They do not author policies (that is the Email Security Admin's and Endpoint DLP Admin's role) but they triage TAP alerts, release or escalate quarantined messages, review ITM insider threat alerts, investigate endpoint DLP detections, and escalate policy tuning requests when false positive rates are high. They are the primary consumer of Proofpoint's detection output and the persona most directly impacted by detection rule misconfiguration.

**Typical profile:** Security Operations Center (SOC) Analyst, Threat Intelligence Analyst, Incident Responder.

**Prerequisite knowledge:** Email threat analysis, log review, escalation procedures, basic understanding of Proofpoint quarantine categories.

---

## Daily Triage Flow

```
+-------------------+   +-------------------+   +--------------------+   +-------------------+
| 1. TAP Dashboard  | > | 2. Quarantine     | > | 3. Endpoint DLP    | > | 4. ITM Alert      |
| Alert Review      |   | Admin Review      |   | Incident Triage    |   | Investigation     |
| (30-60 min/day)   |   | (20-30 min/day)   |   | (30-60 min/day)    |   | (60-120 min/week) |
|                   |   |                   |   |                    |   |                   |
| TAP Dashboard     |   | Quarantine tab    |   | Data Security      |   | ITM console;      |
| URL/Attachment    |   | Phishing/virus/   |   | incidents + alerts;|   | screenshots,      |
| threat summary    |   | spoofed: admin    |   | evidence review    |   | keystrokes        |
| API: GAP          |   | release only      |   | API: PARTIAL       |   | API: GAP          |
+-------------------+   +-------------------+   +--------------------+   +-------------------+
```

---

## Capability Touchpoints

| Capability | How This Persona Uses It | Frequency | Complexity | API Coverage |
|-----------|-------------------------|-----------|------------|-------------|
| TAP | Review URL/Attachment Defense alerts; manage VAP list | Daily | COMPLEX | GAP |
| Quarantine Management | Review and release admin-only quarantine categories (phishing, virus, spoofed) | Daily | MODERATE | PARTIAL |
| Endpoint DLP | Triage detection rule alerts; review evidence; escalate to DLP Admin for rule tuning | Daily | COMPLEX | PARTIAL |
| ITM / ObserveIT | Review insider threat alerts; investigate keystroke/screenshot evidence | Weekly | COMPLEX | GAP |
| CASB | Review CASB threat and DLP alerts from cloud app monitoring | Weekly | COMPLEX | GAP |
| Isolation | Monitor isolation session alerts; review attempted access to isolated URLs | As-needed | COMPLEX | GAP |

---

## Narrative

### 1. TAP Dashboard Alert Review (30-60 min/day)

**Screen:** TAP Dashboard (separate portal from Email Protection console)

**Actions:**
- Review daily threat summary: new clicks on malicious URLs, attachment verdicts (malicious/suspicious/clean), VAP activity
- For malicious URL click alerts: identify the recipient user, determine if the URL was accessed in isolation or direct browser, assess scope
- For malicious attachment verdicts: confirm the message was held (hold-and-release mode) or delivered (retroactive quarantine mode) — follow up if delivered
- Review VAP list updates: if new users are added to the VAP list, immediately check whether they are protected by Isolation (if licensed) — manually import updated VAP list to Isolation Console if needed
- Manage TAP sender exemptions (alert suppression only — does NOT stop URL rewriting or sandboxing)

**Critical action — VAP list import (if Isolation is licensed):**
1. Export current VAP list from TAP Dashboard
2. Navigate to Isolation Console (separate portal — obtain URL from account team)
3. Import VAP list to Isolation policy
4. Confirm new VAPs appear in the isolation policy user list

**Output:** Threat summary reviewed; active incidents escalated; VAP list current in Isolation

**Automation:** MANUAL ONLY — TAP Dashboard and Isolation Console have no public API coverage for the operations this persona performs [gap — corpus]

**Gotchas:**
- URL Defense is DISABLED by default after provisioning — if this persona notices zero URL rewriting, it means URL Defense was never enabled [V5 — Grade B]
- TAP sender exemption suppresses alerts but URL rewriting continues — a "safe" sender still has their links rewritten [S21 — Grade C]
- TAP exemption list and Email Protection safe-sender list are independent — exempting in one does not exempt in the other [S21 — Grade C]
- VAP list does NOT auto-sync to Isolation — each new VAP requires a manual import cycle; users identified as high-risk may go days without isolation protection [V17 — Grade C, S15 — Grade B]
- Isolation does not block — it renders safely in a container; users can still be socially engineered if interaction level is set to "Full Interactive" [V18 — Grade C]
- New VAPs unprotected by Isolation until manual re-import — during an active targeted attack, this window is operationally significant [V17 — Grade C]
- Hold-and-release Attachment Defense adds delivery latency — operational teams escalate complaint about delayed mail during active incidents [inferred — Grade E]

---

### 2. Quarantine Console — Admin Category Review (20-30 min/day)

**Screen:** Proofpoint Essentials > Quarantine tab (admin view)

**Actions:**
- Filter for admin-only categories: phishing, virus/malware, spoofed email
- Review each flagged message: sender, recipient, subject, headers, category
- For confirmed malicious: delete without release
- For suspected false positives: release message + notify user; document for filter tuning request
- Check quarantine volume by category — sudden spikes indicate a campaign or tuning issue

**Decisions:**
- Phishing, virus, and spoofed categories are hardcoded admin-only — no user self-release [S19 — Grade D]
- Policy category: if user-releasable was configured (compliance risk — should be admin-only), check for unauthorized user releases
- Any message released that should not have been → escalate to Email Security Admin for remediation

**Output:** Admin-only quarantine cleared; false positives released; potential tuning requests raised

**Automation:** PARTIAL AUTOMATE — PPS: `proofpoint-pps-quarantine-message-release`, `-delete`, `-resubmit`, `-forward` via XSOAR API [S16 — Grade C]; Essentials: manual-only quarantine release

**Gotchas:**
- Messages permanently deleted when retention expires — no warning, no recovery [S1 — Grade A]
- PPS quarantine: messages can only be moved between same-module-type folders — spam module messages cannot move to DLP folder via API [S16 — Grade C]
- Policy-quarantined message subjects visible in user digest if Policy category not excluded — if users are reporting seeing DLP-flagged subjects in their digest, this is a quarantine configuration issue [S19 — Grade D]

---

### 3. Endpoint DLP Incident Triage (30-60 min/day)

**Screen:** Proofpoint Data Security > Incidents / Alerts console

**Actions:**
- Review new detection alerts: identify rule triggered, user involved, data type matched, destination (USB, web upload, email, print, etc.)
- Review evidence if "Store Original Evidence" was enabled on the rule (stored file/content captures)
- Triage severity: Critical/High (immediate investigation) vs Medium/Low (bulk review)
- For confirmed data loss events: escalate per IR procedure; document incident
- For false positives: document the pattern and raise tuning request to the DLP Admin (analyst does not author rules — escalate)
- For Prevention Rule blocks: confirm block occurred; review if user received notification message; check if user acknowledged warning

**Analyst-to-admin escalation triggers:**
- False positive rate on a rule exceeds 20% of alerts — request rule condition tightening
- A high-severity rule is generating zero alerts over 7+ days — likely misconfigured (no Rule Set assignment, empty detector, or passive mode)
- Prevention rules not blocking — verify Agent Passive Mode is OFF in ITM System Policy

**Output:** Incident documentation; escalation requests for rule tuning; IR escalation for confirmed events

**Automation:** PARTIAL AUTOMATE — Data Security REST API supports incident retrieval and evidence collection; rule disable/enable is NOT automatable [S28, S10 — Grade A/C]

**Gotchas:**
- Detection rules with no Rule Set assignment fire on no agents — analyst sees zero alerts from a "configured" rule [S10 — Grade A]
- Rules without explicit severity default to Informational — invisible in dashboards configured for High/Critical only [V16 — Grade C]
- Prevention rules silently do nothing in Agent Passive Mode — if passive mode is enabled, all prevention blocks are inoperable [S4 — Grade A]
- Priority semantics INVERTED: Agent Policies use lower number = higher priority; Detection Rules use higher number = higher priority — confusing when coordinating with DLP Admin [S8 — Grade A, V16 — Grade C]
- Web file upload blocking is Windows-only — Mac endpoints silently ignore web upload block rules [S11 — Grade A]
- Agent policy push interval unknown — policy changes may take 15-30+ minutes to reach endpoints after DLP Admin saves changes [U — ASSUMPTION based on analogous propagation delay]
- 100-rule tenant limit (combined detection + prevention) — analyst escalation requests for new rules may be blocked by this limit [S12 — Grade A]

---

### 4. ITM Alert Investigation (60-120 min/week)

**Screen:** ITM console (prod.docs.oit.proofpoint.com interface OR ObserveIT on-prem console)

**Actions:**
- Review ITM alert queue: insider threat library alerts, custom alert rule triggers
- For each alert: review activity log, screenshots, application context, file transfers
- Keystroke review: only available if Enable Key Logging was turned ON in System Policy Settings — if key logging is OFF, no keystroke evidence exists
- Assess: accidental/policy violation vs. intentional data exfiltration
- Escalate insider threat investigations to HR and Legal per IR procedure
- Request Prevention Rule creation from ITM Admin for patterns confirmed as malicious

**Analyst limitations (read-only in most deployments):**
- Cannot create or edit ITM rules (Policy Administrator / ITM Admin role required)
- Cannot modify System Policy Settings (Admin role required)
- Cannot import library update ZIPs (Admin role required)

**Output:** Investigation documentation; insider threat escalations; rule creation requests

**Automation:** MANUAL ONLY — ITM console API is OFF by default; enabling requires admin action [S4 — Grade A]; no public API for ITM alert retrieval in accessible sources

**Gotchas:**
- Key Logging is OFF by default — if analyst expects keystroke evidence, verify Key Logging was enabled before the activity occurred [S4 — Grade A]
- Prevention rules do nothing in Agent Passive Mode — confirm passive mode state before concluding that prevention configuration is wrong [S4 — Grade A]
- ITM API is disabled by default — SOAR integration requires admin to enable API toggle first [S4 — Grade A]
- Rule Type is irreversible after save — if analyst requests an Alert Rule be converted to Prevention, the DLP Admin must recreate it from scratch [S6 — Grade A, inferred]
- Library updates require manual ZIP import — activated library rules may be outdated versions [S5 — Grade A]
- Continuous Recording + Color image format multiplies storage 3-5x — if storage exhaustion occurs during investigation, contact ITM Admin immediately [S4 — Grade A, inferred]

---

## Prerequisites

- Read access to TAP Dashboard
- Admin role on quarantine console (to view and release admin-only categories)
- Read/investigator access to Data Security incident console
- Read access to ITM console (requires ITM license and provisioned investigator role)
- Isolation Console access (if licensed) to verify VAP list status

---

## Common Pain Points

| # | Pain Point | Capability | Source | Impact |
|---|-----------|-----------|--------|--------|
| 1 | VAP list manual re-import required after every threat review — new VAPs unprotected during gap | TAP / Isolation | V17, S15 — Grade C/B | HIGH — security gap during active attack |
| 2 | Detection rules silently fire on no agents when Rule Set not assigned | Endpoint DLP | S10 — Grade A | HIGH — missed detections |
| 3 | Key logging OFF by default — no keystroke evidence for historical incidents | ITM | S4 — Grade A | HIGH — incomplete investigations |
| 4 | Prevention rules inoperable in Agent Passive Mode — no visible indication | ITM / Endpoint DLP | S4 — Grade A | HIGH — silent non-enforcement |
| 5 | Cannot disable individual rules via API during active incident response | Endpoint DLP | API gap | HIGH — manual-only incident containment |
| 6 | ITM API OFF by default — SOAR integration fails silently until admin enables toggle | ITM | S4 — Grade A | HIGH — SOAR playbooks non-functional |
| 7 | Priority semantics inverted between Agent Policies and Detection Rules | Endpoint DLP | S8, V16 — Grade A/C | MEDIUM — coordination confusion |

---

## Automation Summary

| Step | API Coverage | Automation Status | Blocker (if any) |
|------|-------------|-------------------|------------------|
| 1. TAP alert review | GAP | MANUAL ONLY | No public TAP alert API in accessible corpus |
| 2. Quarantine release (PPS) | PARTIAL | PARTIAL AUTOMATE | XSOAR API commands [S16]; Essentials manual |
| 3. Endpoint DLP incident retrieval | PARTIAL | PARTIAL AUTOMATE | Data Security REST API for incidents [S28] |
| 3. Detection rule disable (incident) | GAP | MANUAL ONLY | No API to enable/disable individual rules |
| 4. ITM alert retrieval | GAP | MANUAL ONLY | API off by default; no public retrieval API documented |
| VAP list import to Isolation | GAP | MANUAL ONLY | No auto-sync; requires manual export + import cycle |

## Time Estimate

| Scenario | Time | Notes |
|---------|------|-------|
| Daily TAP + quarantine review | 45-90 min | TAP alerts + admin-only quarantine categories |
| Daily endpoint DLP triage | 30-60 min | Varies with detection volume |
| Active incident investigation | 2-8 hours | Depends on scope and evidence availability |
| Weekly ITM insider threat review | 60-120 min | Alert queue review + escalation decisions |
| VAP list re-import cycle | 15 min | If TAP VAP roster changed since last import |

## Complexity: COMPLEX
(driven by multi-console navigation, manual-only TAP and ITM workflows, silent failure modes in endpoint DLP detection, and absence of API for incident-response rule control)
