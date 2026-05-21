# Virus Policy Configuration — Advanced Configuration Reference
## Proofpoint (Essentials + PPS/PoD)

> All options documented, organized by screen.
> INCOMPLETE sections indicate fields behind authentication walls or otherwise undocumented in accessible sources.

---

## Screen 1: Company Settings > Virus

**Navigation:** Proofpoint Essentials admin console > Company Settings > Virus
**Source:** [S1, Grade A]

```
+---------------------------------------------------------------+
| Company Settings > Virus                                      |
+---------------------------------------------------------------+
|                                                               |
|  Anti-Virus Protection: ALWAYS ON (not configurable)          |
|                                                               |
|  AV Bypass List                                               |
|  +-------------------------------------------+                |
|  | partner@trusted.com                        |  [Remove]     |
|  | encrypted-sender.com                       |  [Remove]     |
|  +-------------------------------------------+                |
|                                                               |
|  Add Bypass Address:                                          |
|  [_________________________]  [Save]                          |
|                                                               |
|  Accepted formats:                                            |
|  - user@domain.com  (specific sender)                         |
|  - domain.com       (all senders at domain)                   |
|                                                               |
+---------------------------------------------------------------+
```

### All Fields

| Field | Type | Required | Default | Options | Validation | Description | Source |
|-------|------|----------|---------|---------|------------|-------------|--------|
| AV Bypass Address | text | No | Empty list | user@domain.com or domain.com | Valid email address or domain name | Adds a sender or sender domain to the AV bypass list. Messages from bypassed senders skip virus scanning entirely. Entries are additive. | [S1, Grade A] |

### Bypass List Entry Formats

| Format | Scope | Risk Level | Example | Source |
|--------|-------|-----------|---------|--------|
| user@domain.com | Single sender only | LOW — narrow scope | partner-admin@vendor.com | [S1, Grade A] |
| domain.com | All senders at entire domain | HIGH — includes spoofed/compromised accounts | vendor.com | [S1, Grade A] |

### Actions

| Action | Type | Description | Source |
|--------|------|-------------|--------|
| Save (Add) | button | Adds the entered address/domain to the bypass list. Propagation: 5-30 minutes (assumed). | [S1, Grade A] |
| Remove | button | Removes selected entry from bypass list. Scanning resumes for that sender after propagation. | [S1, Grade A] |

### Edge Cases

| Scenario | Behavior | Source |
|----------|----------|--------|
| Domain-level bypass + spoofed sender at that domain | Spoofed messages claiming to be from bypassed domain also skip AV scanning | [S1, Grade A] |
| Same sender on bypass list AND in a filter rule with Quarantine action | UNKNOWN — whether AV bypass takes precedence or filter quarantine overrides | INCOMPLETE |
| Bypass list entry with wildcard (*.domain.com) | UNKNOWN — whether wildcard patterns are supported | INCOMPLETE |
| Maximum number of bypass list entries | UNKNOWN — not documented; no published limit | INCOMPLETE |
| Duplicate entry added to bypass list | UNKNOWN — whether UI prevents duplicates or silently accepts | INCOMPLETE |

---

## Screen 2: Virus Quarantine (Admin View — via Quarantine Console)

**Navigation:** Proofpoint Essentials > Quarantine tab > Category: Virus/Malware
**Source:** [S1, Grade A]; [D — S19]

```
+---------------------------------------------------------------+
| Quarantine Console — Virus/Malware Category                   |
+---------------------------------------------------------------+
| Category: [Virus/Malware v]  Date: [____-____]                |
|                                                               |
| [ ] | Sender           | Recipient    | Subject     | Threat  |
| [x] | sender@ext.com   | user@co.com  | Invoice.pdf | Trojan  |
| [ ] | partner@ven.com  | admin@co.com | Report.zip  | Encrypt |
|                                                               |
| Actions: [Release] [Delete]                                   |
| (Release+Allow and Not Spam NOT available for Virus category) |
|                                                               |
| NOTE: Admin-only — end users CANNOT release virus-quarantined |
| messages via digest or self-service portal.                    |
+---------------------------------------------------------------+
```

### Admin Actions for Virus Quarantine

| Action | Description | Risk | Source |
|--------|-------------|------|--------|
| Release | Delivers virus-quarantined message to recipient inbox | HIGH — message may contain active malware | [S1, Grade A] |
| Delete | Permanently removes message from quarantine | NONE — safe operation | [S1, Grade A] |

### Restrictions

| Restriction | Description | Source |
|-------------|-------------|--------|
| No user self-release | Virus category is hard-locked admin-only; cannot be changed to user-releasable | [D — S19] |
| No "Release and Allow" | Safe list addition not offered for virus category — prevents whitelisting malware senders | [D — S19] (inferred) |
| No "Report as Not Spam" | Spam reporting not applicable to virus detections | [D — S19] (inferred) |

---

## Screen 3: PPS Multi-Layer Virus Protection — INCOMPLETE

**Navigation:** UNKNOWN — PPS admin console; behind authentication wall
**Source:** [S2, Grade B] (training material only)

**NOTE: This entire screen is INCOMPLETE. PPS admin guide is behind authentication wall. All fields below are from Grade B training material and describe features confirmed to exist but without step-by-step configuration detail.**

### PPS Virus Module Components

| Component | Description | Configuration | Source |
|-----------|------------|---------------|--------|
| Multi-Layer AV Engines | Multiple scanning engines for higher detection rate | UNKNOWN — which engines, how to enable/disable individual engines | [S2, Grade B] |
| Zero-Hour Anti-Virus | Heuristic detection of new viruses before signature updates | UNKNOWN — threshold, sensitivity, enable/disable toggle | [S2, Grade B] |
| Virus Policy per Group | Group-level virus policy exceptions | UNKNOWN — group assignment UI, policy priority | [S2, Grade B] |
| Encrypted File Handling | Policies for files that cannot be AV-scanned | See Screen 4 below | [S2, Grade B] |

---

## AV Detection and Action Reference

| Detection Type | Action in Essentials | Action in PPS | User Impact | Source |
|---------------|---------------------|---------------|-------------|--------|
| Known virus (signature match) | Quarantine (admin-only) | Quarantine/Block (configurable) | Message held; user notified via digest only if virus category in digest | [S1, Grade A]; [S2, Grade B] |
| Zero-hour (heuristic) | N/A (Essentials uses single engine) | Quarantine (configurable) | Message held pending analysis | [S2, Grade B] |
| Encrypted file (cannot scan) | UNKNOWN — Essentials behavior not documented | Quarantine by default; group exceptions available | Message held or delivered based on policy | [S2, Grade B] |
| Bypassed sender | Deliver without scanning | N/A (PPS bypass mechanism UNKNOWN) | Message delivered — NO virus check performed | [S1, Grade A] |
| Clean (no virus detected) | Deliver normally | Deliver normally | Normal delivery | [S1, Grade A] |

---

## Bypass List vs. Filter Policy Interaction

| Configuration | Virus Scanning | Filter Policy | Net Result | Source |
|--------------|---------------|---------------|------------|--------|
| Sender NOT on bypass list, no filter rule | AV scans normally | No filter action | Normal AV protection | [S1, Grade A] |
| Sender on bypass list, no filter rule | AV scanning SKIPPED | No filter action | No virus protection for this sender | [S1, Grade A] |
| Sender NOT on bypass list, filter rule = Allow | AV scans normally | Filter allows delivery | AV protects; filter allows non-virus mail | [S1, Grade A]; [U — ASSUMPTION] |
| Sender on bypass list, filter rule = Quarantine | AV scanning SKIPPED | Filter quarantines | Message quarantined by filter; virus not checked | [U — ASSUMPTION; interaction not documented] |

---

## Worked Examples

### Example 1: Adding Trusted Partner for Encrypted File Delivery

```
Scenario: A legal firm regularly sends encrypted ZIP attachments to
your organization. These are quarantined because Proofpoint cannot
scan encrypted files. You need to allow delivery from this specific
partner.

Screen: Company Settings > Virus
  AV Bypass Address: [legal-team@lawfirm.com]
  Click: Save

Wait: 5-30 minutes for propagation

# WHY: Encrypted ZIP files cannot be AV-scanned, so Proofpoint may
# quarantine them. Adding the sender to the bypass list allows the
# encrypted attachments through without scanning.

# GOTCHA: Use the SPECIFIC email address (legal-team@lawfirm.com),
# NOT the domain (lawfirm.com). Domain-level bypass would exempt ALL
# senders at lawfirm.com from virus scanning, including any spoofed
# or compromised accounts at that domain. If the law firm has multiple
# senders, add each address individually.
```

### Example 2: Removing an Unnecessary Domain-Level Bypass

```
Scenario: A previous admin added "partner.com" to the AV bypass list.
The partnership has ended. You need to restore AV scanning for that
domain.

Screen: Company Settings > Virus
  Locate: "partner.com" in bypass list
  Click: [Remove] next to "partner.com"

# WHY: Domain-level bypasses create broad security gaps. Removing the
# entry restores AV scanning for all senders at that domain.

# GOTCHA: After removing a bypass entry, allow 5-30 minutes for
# propagation. During this window, messages from partner.com may still
# bypass AV scanning. Do NOT test immediately after removal and
# conclude the removal failed — wait for propagation.
```

### Example 3: Investigating Virus False Positive in Admin Quarantine

```
Scenario: A user reports they are expecting an important document from
a known sender, but it never arrived. Admin suspects AV false positive.

Step 1 — Check quarantine:
  Screen: Quarantine Console (admin view)
  Category Filter: [Virus/Malware]
  Search: [sender@known.com]
  Date Range: [last 7 days]

Step 2 — Verify message:
  Review: Sender address, subject line, attachment name
  Confirm: This is the expected message from the known sender

Step 3 — Release with caution:
  Action: Select message > [Release]

Step 4 — Prevent recurrence (if appropriate):
  Screen: Company Settings > Virus
  AV Bypass Address: [sender@known.com]
  Click: Save

# WHY: The virus quarantine requires admin release by design. After
# confirming the message is legitimate, releasing it delivers to the
# recipient. Adding the sender to bypass prevents future false
# positives from this sender.

# GOTCHA: Before releasing, verify the sender address is genuine (not
# spoofed). Releasing a virus-quarantined message with active malware
# delivers it directly to the user's inbox. The "Release" action for
# virus quarantine does NOT offer "Release and Allow" — you must
# separately add the sender to the bypass list if you want to prevent
# recurrence. Also: adding to bypass list means ALL messages from this
# sender skip AV scanning going forward, not just the attachment type
# that triggered the false positive.
```

### Example 4: Auditing the AV Bypass List for Security Review

```
Scenario: Security team requests an audit of all AV scanning
exceptions as part of quarterly security review.

Screen: Company Settings > Virus
  Review: All entries in AV Bypass List

For each entry, evaluate:
  1. Is this sender/domain still a trusted partner? (Remove if not)
  2. Is the entry at domain level? (Convert to specific addresses)
  3. Is the bypass still needed? (Test without bypass first)

# WHY: AV bypass entries create permanent gaps in virus protection.
# Regular audits ensure the bypass list stays minimal and justified.

# GOTCHA: There is no audit log or timestamp showing WHEN entries
# were added or WHO added them. The bypass list is a flat list with
# no metadata. Maintain an external record (spreadsheet, ticket) of
# bypass list entries with justification, requester, and review date.
# Also: there is no export function documented for the bypass list —
# you must manually record the entries during audit.
```

### Example 5: PPS — Allowing Encrypted Files for Finance Group

```
Scenario (PPS only): The finance department regularly receives
password-protected Excel files from external auditors. These are
quarantined by the PPS virus module because they cannot be scanned.

INCOMPLETE — PPS admin console configuration not documented.

Conceptual workflow (from training material [S2]):
  Screen: PPS admin console > Virus Module > Group Policies (UNKNOWN nav)
  Target Group: [Finance]
  Encrypted File Action: [Allow]
  Click: Save

# WHY: PPS supports group-level exceptions for encrypted files,
# allowing targeted bypass without affecting the entire organization.
# This is superior to the Essentials approach (sender-level bypass)
# because it scopes the exception to a specific user group.

# GOTCHA: This workflow is INCOMPLETE — the exact navigation path,
# field names, and configuration options are behind the PPS
# authentication wall. The feature is confirmed to exist from
# training material [S2] but cannot be documented at field level.
# Consult Proofpoint PPS documentation (help.proofpoint.com with
# valid credentials) or Proofpoint support for step-by-step guidance.
```

---

## Version-Specific Notes

| Version / Product | Change | Impact | Source |
|------------------|--------|--------|--------|
| Essentials (all versions) | AV is always-on; no enable/disable toggle | Only configurable element is bypass list | [S1, Grade A] |
| Essentials (2023 UI refresh) | Navigation may have shifted from "Company Settings > Virus" | Verify current path in admin console | Tribal knowledge |
| Essentials Admin Guide (2014) | 12-year-old source — UI has changed | Use for field logic; verify current navigation | [S1, Grade A]; stale source warning |
| PPS (all versions) | Multi-layer AV, zero-hour, group policies | Deeper AV configuration than Essentials; requires PPS admin console | [S2, Grade B] |
| PPS + TAP | TAP Attachment Defense adds sandbox analysis layer | TAP sandboxing is separate from virus module but complementary | [S2, Grade B] |
