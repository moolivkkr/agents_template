# Quarantine Management — Advanced Configuration Reference
## Proofpoint (Essentials + PPS/PoD)

> All options documented, organized by screen.
> INCOMPLETE sections indicate fields behind authentication walls or otherwise undocumented in accessible sources.

---

## Screen 1: Company Settings > Quarantine > Categories

**Navigation:** Proofpoint Essentials admin console > Company Settings > Quarantine > Categories tab
**Source:** [S1, Grade A]; [S19, Grade D]

```
+---------------------------------------------------------------+
| Company Settings > Quarantine                                 |
| [Categories]  [Digest]  [Retention]                           |
+---------------------------------------------------------------+
|                                                               |
|  Category            User Release    Status                   |
|  +-----------------+--------------+----------+                |
|  | Spam            | [x] Enabled  | Editable |                |
|  | Bulk            | [x] Enabled  | Editable |                |
|  | Adult           | [ ] Disabled | Editable |                |
|  | Policy (DLP)    | [ ] Disabled | Editable |                |
|  | Phishing        |   Admin-only | Locked   |                |
|  | Virus/Malware   |   Admin-only | Locked   |                |
|  | Spoofed Email   |   Admin-only | Locked   |                |
|  +-----------------+--------------+----------+                |
|                                                               |
|  +--------+                                                   |
|  | Save   |                                                   |
|  +--------+                                                   |
+---------------------------------------------------------------+
```

### All Fields

| Field | Type | Required | Default | Options | Validation | Description | Source |
|-------|------|----------|---------|---------|------------|-------------|--------|
| Spam — User Release | checkbox | No | Enabled | Enabled / Disabled | Toggle | Allows end users to self-release spam-quarantined messages via digest link or portal | [S1, Grade A] |
| Bulk — User Release | checkbox | No | UNKNOWN [U — ASSUMPTION: Enabled] | Enabled / Disabled | Toggle | Controls user self-release for bulk/marketing quarantine category | [U — ASSUMPTION] |
| Adult — User Release | checkbox | No | UNKNOWN [U — ASSUMPTION: Disabled] | Enabled / Disabled | Toggle | Controls user self-release for adult content quarantine category | [U — ASSUMPTION] |
| Policy — User Release | checkbox | No | UNKNOWN [U — ASSUMPTION: Disabled] | Enabled / Disabled | Toggle | Controls user self-release for compliance/DLP-quarantined messages | [U — ASSUMPTION; D — S19] |
| Phishing — Release | read_only | N/A | Admin-only (locked) | Not configurable | N/A | Phishing-classified messages require admin release. Cannot be changed. | [D — S19] |
| Virus/Malware — Release | read_only | N/A | Admin-only (locked) | Not configurable | N/A | Virus-detected messages require admin release. Cannot be changed. | [S1, Grade A] |
| Spoofed Email — Release | read_only | N/A | Admin-only (locked) | Not configurable | N/A | Spoofed sender messages require admin release. Cannot be changed. | [D — S19] |

### Edge Cases

| Scenario | Behavior | Source |
|----------|----------|--------|
| User release enabled for Policy category | End users can release DLP-quarantined messages, bypassing compliance controls | [D — S19] |
| Admin release of phishing message | Message delivered to inbox — recipient should be warned | [D — S19] |
| Multiple categories apply to one message | UNKNOWN — which category takes precedence (e.g., message flagged as both spam and policy) | INCOMPLETE |
| User-releasable category + digest exclusion | User cannot see the message in digest but CAN release via quarantine portal if they navigate directly | [D — S19] |

---

## Screen 2: Company Settings > Quarantine > Digest

**Navigation:** Company Settings > Quarantine > Digest tab
**Source:** [S1, Grade A]; [S19, Grade D]

```
+---------------------------------------------------------------+
| Company Settings > Quarantine                                 |
| [Categories]  [Digest]  [Retention]                           |
+---------------------------------------------------------------+
|                                                               |
|  Quarantine Digest Settings                                   |
|                                                               |
|  Digest Enabled:    [x] Enabled                               |
|                                                               |
|  Frequency:         [Daily       v]                           |
|                                                               |
|  Delivery Time:     [08:00 AM    v]  (UNKNOWN — not confirmed)|
|                                                               |
|  Exclude Categories:                                          |
|  [ ] Spam                                                     |
|  [x] Adult                                                    |
|  [ ] Bulk                                                     |
|  [ ] Policy                                                   |
|                                                               |
|  +--------+                                                   |
|  | Save   |                                                   |
|  +--------+                                                   |
+---------------------------------------------------------------+
```

### All Fields

| Field | Type | Required | Default | Options | Validation | Description | Source |
|-------|------|----------|---------|---------|------------|-------------|--------|
| Digest Enabled | checkbox | No | Enabled | Enabled / Disabled | Toggle | Master on/off for quarantine digest email delivery to end users | [S1, Grade A] |
| Digest Frequency | dropdown | No | Daily (inferred) | Daily, Weekly, UNKNOWN (full list not documented) | Select | How often the quarantine digest email is sent | [D — S19] |
| Digest Time | time | No | UNKNOWN | Time of day (format UNKNOWN) | UNKNOWN | Time of day the digest email is sent. Not documented in grade-A sources. | INCOMPLETE |
| Digest Category Exclusions | multiselect | No | None (all categories included) | Spam, Adult, Bulk, Policy | Checkbox per category | Controls which quarantine categories appear in the user-facing digest. Phishing/Virus/Spoofed not shown regardless. | [D — S19] |

### Conditional Fields

| Field | Appears When | Description | Source |
|-------|-------------|-------------|--------|
| Frequency options | Digest Enabled = checked | Frequency dropdown only active when digest is enabled | [S1, Grade A] (inferred) |
| Category exclusions | Digest Enabled = checked | Exclusion checkboxes only active when digest is enabled | [D — S19] (inferred) |

### Edge Cases

| Scenario | Behavior | Source |
|----------|----------|--------|
| Digest disabled + user release enabled | Users can still self-release via quarantine portal URL but receive no notification about quarantined messages | [S1, Grade A] (inferred) |
| All user-visible categories excluded from digest | Digest email is empty or not sent — UNKNOWN behavior | INCOMPLETE |
| Adult category included in digest | Adult content subjects appear in user inbox notification emails | [D — S19] |
| Digest sent during user timezone vs. org timezone | UNKNOWN — whether digest time is per-user timezone or organization-wide | INCOMPLETE |

---

## Screen 3: Company Settings > Quarantine > Retention

**Navigation:** Company Settings > Quarantine > Retention tab
**Source:** [S1, Grade A]

```
+---------------------------------------------------------------+
| Company Settings > Quarantine                                 |
| [Categories]  [Digest]  [Retention]                           |
+---------------------------------------------------------------+
|                                                               |
|  Quarantine Retention Period                                  |
|                                                               |
|  Days:  [30]                                                  |
|                                                               |
|  Messages older than this period are permanently deleted.     |
|  No warning is sent before deletion.                          |
|                                                               |
|  +--------+                                                   |
|  | Save   |                                                   |
|  +--------+                                                   |
+---------------------------------------------------------------+
```

### All Fields

| Field | Type | Required | Default | Options | Validation | Description | Source |
|-------|------|----------|---------|---------|------------|-------------|--------|
| Quarantine Retention Period | number | No | 30 days | Days (range UNKNOWN; 30 days documented) | Numeric; minimum and maximum not documented | Number of days quarantined messages are retained before automatic permanent deletion | [S1, Grade A] |

### Edge Cases

| Scenario | Behavior | Source |
|----------|----------|--------|
| Retention reduced from 30 to 14 days | Messages currently aged 15–30 days become immediately eligible for deletion | [U — ASSUMPTION; standard quarantine behavior] |
| Retention set to 0 days | UNKNOWN — whether immediate deletion or a minimum floor applies | INCOMPLETE |
| Message released 1 day before retention expires | Message delivered normally — release resets the lifecycle | [S1, Grade A] (inferred) |

---

## Screen 4: Quarantine Console (Admin View)

**Navigation:** Proofpoint Essentials > Quarantine tab (top navigation)
**Source:** [S1, Grade A]; [S19, Grade D]

```
+---------------------------------------------------------------+
| Quarantine Console                                            |
+---------------------------------------------------------------+
| Search: [_____________] [Category: v] [Date: ____-____]      |
|                                                               |
| [ ] | Sender          | Recipient    | Subject     | Category |
| [x] | spam@bad.com    | user@co.com  | Buy now!!   | Spam     |
| [ ] | news@legit.com  | user@co.com  | Newsletter  | Bulk     |
| [x] | evil@phish.net  | admin@co.com | Urgent!!    | Phishing |
|                                                               |
| Actions: [Release v] [Delete] [Release+Allow] [Not Spam]     |
+---------------------------------------------------------------+
```

### All Fields

| Field | Type | Required | Default | Options | Validation | Description | Source |
|-------|------|----------|---------|---------|------------|-------------|--------|
| Search / Filter | text | No | None | Free text search by sender, recipient, subject | Any characters | Searches quarantine by message attributes | [S1, Grade A] |
| Category Filter | dropdown | No | All | Spam, Bulk, Adult, Policy, Phishing, Virus, Spoofed | Select | Filters quarantine view by category | [D — S19] |
| Date Range Filter | date_range | No | None | Start date, end date | Valid dates within retention period | Filters by quarantine date | [S1, Grade A] (inferred) |
| Message Selection | checkbox | No | None | Per-message checkbox | At least one selected for actions | Selects messages for bulk actions | [S1, Grade A] |

### Admin Actions

| Action | Description | Availability | Source |
|--------|-------------|-------------|--------|
| Release | Delivers message to recipient inbox | All categories (admin) | [S1, Grade A] |
| Delete | Permanently removes message from quarantine | All categories (admin) | [S1, Grade A] |
| Release and Allow | Releases message AND adds sender to safe list | Spam, Bulk categories | [D — S19] |
| Report as Not Spam | Releases and reports false positive to Proofpoint | Spam category | [D — S19] |

---

## Quarantine Category Action Reference

| Category | User-Releasable | Admin Actions | Appears in Digest | Source |
|----------|----------------|---------------|-------------------|--------|
| Spam | Yes (configurable) | Release, Delete, Release+Allow, Not Spam | Yes (unless excluded) | [S1, Grade A] |
| Bulk | Yes (configurable) [U] | Release, Delete, Release+Allow | Yes (unless excluded) | [U — ASSUMPTION] |
| Adult | Configurable [U] | Release, Delete | Yes (unless excluded) | [U — ASSUMPTION] |
| Policy/DLP | Configurable [U] | Release, Delete | Yes (unless excluded) | [U — ASSUMPTION; D — S19] |
| Phishing | No (locked) | Release, Delete | No (not shown to users) | [D — S19] |
| Virus/Malware | No (locked) | Release, Delete | No (not shown to users) | [S1, Grade A] |
| Spoofed | No (locked) | Release, Delete | No (not shown to users) | [D — S19] |

---

## Worked Examples

### Example 1: Secure Quarantine Configuration for Compliance Environment

```
Scenario: A financial services firm needs quarantine configured so
DLP-quarantined messages cannot be self-released by end users.

Screen 1: Company Settings > Quarantine > Categories
  Spam — User Release:     [x] Enabled   (users can manage their own spam)
  Bulk — User Release:     [x] Enabled   (users can manage marketing mail)
  Adult — User Release:    [ ] Disabled  (admin-only)
  Policy — User Release:   [ ] Disabled  (admin-only — CRITICAL for DLP)
  Phishing:                Admin-only    (locked — cannot change)
  Virus/Malware:           Admin-only    (locked — cannot change)
  Spoofed:                 Admin-only    (locked — cannot change)
  Click: Save

Screen 2: Company Settings > Quarantine > Digest
  Digest Enabled:          [x] Enabled
  Frequency:               [Daily]
  Exclude Categories:      [x] Adult     (hide adult subjects from inbox)
                           [x] Policy    (hide DLP-flagged subjects)
  Click: Save

# WHY: Policy category is set to admin-only AND excluded from digest.
# This ensures users cannot see or self-release DLP-quarantined messages.
# Both controls must be set — they are independent.

# GOTCHA: Setting Policy to admin-only in Categories but NOT excluding it
# from the digest means users will SEE the subjects of their DLP-flagged
# messages in the digest email (they just cannot release them). This can
# reveal compliance investigation details to the user. Set BOTH controls.
```

### Example 2: Troubleshooting Missing Newsletter Reports

```
Scenario: Users report they are not receiving a subscribed newsletter.
Admin suspects it is being quarantined as bulk mail.

Screen: Quarantine Console (admin view)
  Search: [newsletter@sender.com]
  Category Filter: [Bulk]
  Date Range: [last 7 days]

  Result: Newsletter found in Bulk quarantine.

  Action: Select message > [Release and Allow]

# WHY: "Release and Allow" delivers the message AND adds the sender to
# the safe list, so future newsletters from this sender bypass quarantine.

# GOTCHA: "Release and Allow" adds the sender to the ORGANIZATION safe
# list, not the individual user's list. This means the newsletter will
# bypass quarantine for ALL users in the organization, not just the
# requesting user. If only one user wants it, use plain "Release" and
# have the user add the sender to their personal safe list.
```

### Example 3: Admin Release of False Positive Phishing Message

```
Scenario: A user reports that an expected message from a partner
was quarantined as phishing. Admin verifies it is legitimate.

Screen: Quarantine Console (admin view)
  Search: [partner@trusted.com]
  Category Filter: [Phishing]

  Review: Verify message headers, URLs, and content are legitimate.

  Action: Select message > [Release]

# WHY: Phishing is admin-only release by design. The admin must
# manually verify before releasing to protect against actual phishing.

# GOTCHA: The "Release" action for phishing does NOT add the sender
# to a safe list. The same sender may be quarantined again for future
# messages. To prevent recurrence, create a Filter Policy with
# Allow action for this sender AFTER releasing. The quarantine console
# does not offer "Release and Allow" for the phishing category.
```

---

## Version-Specific Notes

| Version / Product | Change | Impact | Source |
|------------------|--------|--------|--------|
| Essentials (2023 UI refresh) | Navigation updated; "Company Settings > Quarantine" may have shifted | Pre-2023 videos show older nav path | Tribal knowledge |
| PPS (all versions) | Folder-based quarantine model vs. Essentials category model | Concepts are analogous but UIs are completely different | [S2, Grade B]; [S16, Grade C] |
| Essentials Admin Guide (2014) | 12-year-old source — UI has changed | Use for field logic; verify current navigation via console | [S1, Grade A]; stale source warning |
