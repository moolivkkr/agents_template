# Email Security Administrator — Workflow Summary

> Generated: 2026-05-21 | Product: Proofpoint (Essentials + PPS/PoD + TAP + Encryption)
> Primary user of: Email Filtering, Spam, Virus, Email DLP, Email Encryption, TAP, Quarantine

---

## Role Overview

The Email Security Administrator configures and maintains Proofpoint's inbound and outbound email protection stack. They own filter policies, spam thresholds, AV settings, email encryption triggers, TAP URL/Attachment Defense, and quarantine management. In Essentials environments they work in a single admin console; in PPS/PoD environments they work across the Email Firewall, Policy Routes, and quarantine folder systems. This persona is responsible for the "authoring policies" workflow for all email-channel capabilities.

**Typical profile:** Information Security Engineer, IT Security Administrator, or Mail Administrator with Proofpoint admin console access.

**Prerequisite knowledge:** Email routing fundamentals, SMTP basics, regular expressions, organizational domain and sender landscape, quarantine escalation procedures.

---

## Daily Flow

```
+------------------+   +-----------------+   +-------------------+   +------------------+
| 1. Spam/AV       | > | 2. Email Filter  | > | 3. Quarantine     | > | 4. TAP Config    |
| Baseline Config  |   | Policy Authoring |   | Review + Tune     |   | (initial setup)  |
| (15-30 min)      |   | (1-3 hrs)        |   | (30-60 min daily) |   | (1-2 hrs)        |
|                  |   |                  |   |                   |   |                  |
| Spam Settings    |   | Filter Policies  |   | Quarantine console|   | URL Defense +    |
| AV bypass list   |   | DLP conditions   |   | Release decisions |   | Att. Defense     |
| API: PARTIAL     |   | API: PARTIAL     |   | API: PARTIAL      |   | API: GAP         |
+------------------+   +-----------------+   +-------------------+   +------------------+
        |                       |
        v                       v
+------------------+   +-----------------+
| 5. Encryption    | > | 6. Ongoing       |
| Filter Setup     |   | Policy Tuning    |
| (30-60 min)      |   | (daily/weekly)   |
|                  |   |                  |
| Outbound filter  |   | False positive   |
| Outbound+Company |   | review, priority |
| scope only       |   | reorder, new     |
| API: PARTIAL     |   | sender exceptions|
+------------------+   +-----------------+
```

---

## Capability Touchpoints

| Capability | How This Persona Uses It | Frequency | Complexity | API Coverage |
|-----------|-------------------------|-----------|------------|-------------|
| Spam Policy | Set threshold, bulk email, DNS checks | Initial + quarterly | SIMPLE | PARTIAL |
| Virus Policy | Manage AV bypass list for trusted senders | As-needed | SIMPLE | GAP |
| Email Filter Policies | Create/edit inbound/outbound content rules | Weekly | COMPLEX | PARTIAL |
| Email DLP | Configure DLP conditions in filter policies | Weekly | COMPLEX | PARTIAL |
| Email Encryption | Create outbound encryption trigger filters | Initial + change-driven | COMPLEX | PARTIAL |
| Quarantine Management | Configure categories, digest, retention; daily release review | Daily | MODERATE | PARTIAL |
| TAP URL Defense | Enable URL Defense, configure per-group, set exemptions | Initial + ongoing | COMPLEX | GAP |
| TAP Attachment Defense | Enable sandboxing, configure hold-vs-deliver mode | Initial + ongoing | COMPLEX | GAP |

---

## Narrative

### 1. Spam and AV Baseline Configuration (15-30 min)

**Screen:** Security Settings > Email > Spam Settings

**Actions:**
- Set spam threshold aggressiveness (slider — exact numeric range undocumented in [S1])
- Enable or disable Bulk Email Quarantine (caution: quarantines legitimately subscribed newsletters)
- Configure Stamp & Forward (marks spam for delivery rather than quarantine)
- Enable Easy Spam Reporting if users should be able to report spam
- Configure Inbound Sender DNS checks (SPF/DKIM/DMARC alignment)
- Navigate to Company Settings > Virus → verify AV bypass list is empty or add trusted-sender exemptions

**Decisions:**
- Bulk Email Quarantine: enabling without pre-existing exceptions for newsletter senders causes legitimate mail disruption. Audit inbound mail for bulk-sender patterns first.
- "Update for all users": checking this overwrites all per-user spam customizations immediately and cannot be undone. Use only when resetting user overrides is intentional.

**Output:** Spam threshold active; AV bypass list configured (or confirmed empty)

**Automation:** PARTIAL AUTOMATE — Spam threshold requires UI; user-level spam settings are partially readable via Essentials API v1 [S26]

**Gotchas:**
- Spam Settings and Filter Policies are separate UIs — changing spam threshold does NOT affect filter rules [V21 — Grade B]
- "Update for all users" is a one-time destructive push — no undo [S1 — Grade A]
- Propagation delay: 5–30 min after save before changes take effect [V21, V2 — Grade B]
- Bulk Email classification identifies by sending infrastructure, not subscription status — legitimate newsletters will be quarantined [S1 — Grade A]

---

### 2. Email Filter Policy Authoring (1-3 hours — initial; 30 min per new rule)

**Screen:** Security Settings > Email > Filter Policies (post-2023 nav) OR Company Settings > Filters (pre-2023)

**Actions:**
- Create new Inbound or Outbound filter (direction set by tab selection — cannot be changed after creation)
- Set filter name, scope (Company/Group/User), and priority
- Configure condition rows: Sender Address, Recipient Address, Subject, Header, Attachment Type, Message Size, Country, IP Address
- Select operators: IS / IS NOT / CONTAINS / BEGINS WITH / ENDS WITH / IS ANY OF / IS NONE OF
- Set Primary Action: Allow / Quarantine / Block / Tag Subject / Encrypt (Outbound+Company only) / Deliver with Modifications
- Optionally set Secondary Action: Notify Admin / BCC / Stamp Subject
- Set "Stop Processing Additional Filters" toggle (HIGH risk — disables all lower-priority filters for matching messages)
- Set "Override Previous Destination" toggle (use sparingly — can override quarantine decisions from higher-priority filters)

**Staged deployment pattern (required for Company-scope filters):**
1. Create at User scope (target own mailbox) — test 24 hours
2. Expand to Group scope (IT pilot, 5-10 users) — test 48 hours
3. Expand to Company scope — monitor quarantine volume
4. Delete User and Group test copies

**Output:** Active filter policy in the evaluation chain

**Automation:** PARTIAL AUTOMATE — Essentials API v1 [S26] exposes filter CRUD endpoints; field parity with UI not fully documented

**Gotchas:**
- Scope evaluation order is User → Group → Company — user-level allow filters fire BEFORE company DLP filters [V20 — Grade B, S1 — Grade A]
- "Stop Processing Additional Filters" on any allow-list filter silently breaks downstream DLP/compliance filters [V20 — Grade B]
- Encrypt action only appears when Direction=Outbound AND Scope=Company — if either is wrong, option disappears without explanation [V7 — Grade B]
- Direction cannot be changed after filter creation — must delete and recreate [S1 — Grade A, inferred]
- Deploying aggressive HTML/attachment/keyword filters directly to Company scope causes org-wide mail disruption [V20 — Grade B]
- "Override Previous Destination" on a lower-priority filter can release messages quarantined by a higher-priority DLP rule [V20 — Grade B]
- Max filter count per org undocumented — capacity planning not possible from public sources [gap — doc-corpus.md]
- Primary doc source [S1] from 2014 — navigation path changed post-2023 [V20 — Grade B]

---

### 3. Quarantine Configuration and Daily Review (30-60 min daily)

**Screen:** Company Settings > Quarantine (Categories / Digest / Retention tabs)

**Initial configuration actions:**
- Set per-category release permissions: spam (user-releasable OK), policy (admin-only for DLP compliance), adult (admin-only recommended), phishing/virus/spoofed (hardcoded admin-only — cannot change)
- Configure digest: enable, set frequency (daily recommended), set delivery time, exclude Adult category from digest
- Set retention period: default 30 days; extend for compliance environments needing longer hold

**Daily review actions:**
- Navigate to Quarantine tab (top nav) — review admin-only categories (phishing, virus, spoofed)
- Release false positives, delete confirmed malicious messages
- Note: messages deleted at retention expiry with NO warning and NO recovery path

**Output:** Quarantined messages processed; digest configured for end-user visibility

**Automation:** PARTIAL AUTOMATE — PPS quarantine management via XSOAR API commands [S16 — Grade C]; Essentials quarantine review is primarily manual

**Gotchas:**
- Messages permanently deleted at retention expiry — no warning, no recovery [S1 — Grade A]
- DLP-flagged message subjects visible in user digest if Policy category not excluded or made admin-only [S19 — Grade D]
- Digest exclusions and release permissions are independent — must set BOTH to make a category truly admin-controlled [S19 — Grade D]
- Quarantine and Archive are separate systems — quarantined messages are NOT auto-archived [S1, S27 — Grade A]
- PPS quarantine: messages can only be moved between same-module-type folders via API [S16 — Grade C]

---

### 4. TAP URL Defense and Attachment Defense Configuration (1-2 hours — initial setup)

**Screen:** Administration > Account Management > Features (URL Defense enable); TAP Settings (per-group config)

**Actions:**
- Step 1: Navigate to Administration > Account Management > Features — enable URL Defense explicitly (IT IS DISABLED BY DEFAULT after provisioning)
- Step 2: Configure URL Defense per-group (pilot group first, then expand)
- Step 3: Configure Attachment Defense mode: hold-and-release vs deliver-with-retroactive-quarantine
- Step 4: Configure TAP sender exemptions (does NOT bypass URL rewriting — only suppresses alerts)
- Step 5: Test by sending a message with a URL — confirm links are rewritten to urldefense.com format

**Output:** URL Defense active for all or targeted user groups; attachment sandboxing configured

**Automation:** MANUAL ONLY — TAP configuration screens behind auth wall; no public API for TAP settings configuration [gap — corpus]

**Gotchas:**
- URL Defense is DISABLED by default after TAP provisioning — must be explicitly enabled [V5 — Grade B]
- Contradiction: official docs imply auto-activation; video shows manual enable step — FOLLOW THE VIDEO [V5 vs doc corpus]
- TAP sender exemption suppresses ALERTS only — URL rewriting and attachment sandboxing continue regardless [S21 — Grade C]
- TAP exemption list and Email Protection safe-sender list are independent systems — must configure both [S21 — Grade C]
- Per-group TAP enablement requires the group to exist in PPS/PoD directory before configuration — no inline group creation [S22 — Grade C]
- Hold-and-release Attachment Defense adds delivery latency — operational teams may object for time-sensitive mail [inferred — Grade E]

---

### 5. Email Encryption Filter Setup (30-60 min)

**Screen:** Security Settings > Email > Filter Policies > [New Outbound filter at Company scope]

**Actions:**
- Create a new filter: Direction = Outbound, Scope = Company (BOTH required before Encrypt option appears)
- Add content condition: Attachment IS ANY / Subject CONTAINS [regulated terms] / Body CONTAINS [regulated terms]
- Set Primary Action = Encrypt (only visible after Direction+Scope are set correctly)
- Optionally: configure "Enforce Completely Secure SMTP Delivery" checkbox on a separate filter for TLS enforcement with encryption fallback (DIFFERENT from always-encrypt — TLS-capable recipients receive TLS, not Proofpoint Encryption)
- Save and wait 5-30 minutes for propagation before testing

**Output:** Outbound encryption active for matched message patterns

**Automation:** PARTIAL AUTOMATE — filter creation via Essentials API; encryption method configuration may require UI

**Gotchas:**
- Encrypt action requires BOTH Direction=Outbound AND Scope=Company — no per-group or per-user encryption via standard filter UI [V7 — Grade B]
- Encrypt action completely disappears from dropdown if Direction or Scope is wrong — admin may think encryption module is not licensed [V7 — Grade B]
- "Enforce Completely Secure SMTP Delivery" checkbox and Do=Encrypt are two different behaviors — TLS fallback is NOT the same as Proofpoint Encryption for HIPAA/regulated use [S1 — Grade A, S14 — Grade B]
- Propagation delay: 5–30 min — do not test immediately after save [V2, V20 — Grade B]
- Encryption data sheet [S14] is dated March 2019 — feature set may have expanded [S14 — Grade B stale]

---

## Prerequisites

- Proofpoint Essentials org provisioned OR PPS/PoD deployed
- Admin role with Company Settings access
- TAP license provisioned (for TAP steps 4)
- Encryption module provisioned (for step 5)
- Pilot user group created in directory for staged deployment testing

---

## Common Pain Points

| # | Pain Point | Capability | Source | Impact |
|---|-----------|-----------|--------|--------|
| 1 | "Stop Processing Additional Filters" silently breaks downstream DLP rules | Email Filtering | V20 — Grade B | HIGH — compliance gap |
| 2 | User-scope filters override Company DLP policies silently | Email Filtering | V20, S1 — Grade B/A | HIGH — DLP bypass |
| 3 | URL Defense disabled by default after TAP provisioning | TAP | V5 — Grade B | HIGH — silent unprotected state |
| 4 | Encrypt action disappears when scope/direction wrong | Encryption | V7 — Grade B | HIGH — admin confusion |
| 5 | Propagation delay causes false test negatives — wastes debugging time | All email | V2, V20 — Grade B | MEDIUM — operational friction |
| 6 | Spam Settings and Filter Policies are independent UIs | Spam / Filtering | V21 — Grade B | MEDIUM — incomplete tuning |
| 7 | DLP-flagged subjects visible in user digest if Policy category not excluded | Quarantine | S19 — Grade D | HIGH — information leakage |
| 8 | TAP exemption suppresses alerts but not URL rewriting | TAP | S21 — Grade C | MEDIUM — unexpected behavior |

---

## Automation Summary

| Step | API Coverage | Automation Status | Blocker (if any) |
|------|-------------|-------------------|------------------|
| 1. Spam threshold | PARTIAL | PARTIAL AUTOMATE | Slider field not confirmed in API docs |
| 2. AV bypass list | GAP | MANUAL ONLY | No public API endpoint for virus settings |
| 3. Email filter creation | PARTIAL | PARTIAL AUTOMATE | Essentials API v1 [S26] — full field parity unconfirmed |
| 4. Quarantine config | PARTIAL | PARTIAL AUTOMATE | Category release permissions UI-only; PPS quarantine has API |
| 5. TAP URL Defense enable | GAP | MANUAL ONLY | No public API for TAP settings configuration |
| 6. Encryption filter | PARTIAL | PARTIAL AUTOMATE | Filter creation automatable; encryption config may require UI |

## Time Estimate

| Scenario | Time | Notes |
|---------|------|-------|
| Initial email security baseline (spam + AV + filters) | 2-4 hours | Includes staged pilot testing |
| Adding one new filter rule | 30-60 min | Includes pilot testing |
| TAP initial setup | 1-2 hours | Manual only — no API automation |
| Encryption filter setup | 30-60 min | Filter creation + propagation wait |
| Daily quarantine review | 20-30 min | Manual review of admin-only categories |

## Complexity: COMPLEX
(driven by filter precedence subtleties, scope order inversion, Encrypt constraint, TAP manual-only setup)
