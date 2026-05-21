# Spam Policy Configuration — Advanced Configuration Reference
## Proofpoint (Essentials + PPS/PoD)

> All options documented, organized by screen.
> INCOMPLETE sections indicate fields behind authentication walls or otherwise undocumented in accessible sources.

---

## Screen 1: Security Settings > Email > Spam Settings

**Navigation:** Proofpoint Essentials admin console > Security Settings (top nav) > Email > Spam Settings
**Source:** [S1, Grade A]; Video 21 [Grade B]

```
+---------------------------------------------------------------+
| Security Settings > Email > Spam Settings                     |
+---------------------------------------------------------------+
|                                                               |
|  Spam Trigger Level                                           |
|  [--|------|------O------|--]                                  |
|  More aggressive          Less aggressive                     |
|                                                               |
|  [x] Quarantine Bulk Email                                    |
|                                                               |
|  Stamp & Forward:  [No           v]                           |
|                    | No            |                           |
|                    | Partial(9-19) |                           |
|                    | All           |                           |
|                    +---------------+                           |
|                                                               |
|  [x] Easy Spam Reporting                                      |
|                                                               |
|  [x] Inbound Sender DNS                                       |
|                                                               |
|  [ ] Update for all users                                     |
|                                                               |
|  +--------+                                                   |
|  | Save   |                                                   |
|  +--------+                                                   |
+---------------------------------------------------------------+
```

### All Fields

| Field | Type | Required | Default | Options | Validation | Description | Source |
|-------|------|----------|---------|---------|------------|-------------|--------|
| Spam Trigger Level | slider | No | System default (numeric value not published) | Numeric threshold — lower = more aggressive | Numeric; exact range UNKNOWN | Adjusts spam detection engine sensitivity. Lower value increases spam catch rate at cost of potential false positives. | [S1, Grade A] |
| Quarantine Bulk Email | checkbox | No | Disabled | Enabled / Disabled | Toggle | When enabled, bulk/marketing email (newsletters, automated mailings) is quarantined rather than delivered to inbox. | [S1, Grade A] |
| Stamp & Forward | dropdown | No | No | No, Partial (score 9-19), All | Select | Appends configurable text (default: "***Spam***") to subject line. "Partial" stamps messages scoring 9-19; "All" stamps all classified spam. | [S1, Grade A] |
| Easy Spam Reporting | checkbox | No | Disabled | Enabled / Disabled | Toggle | Appends a disclaimer to delivered messages with a link allowing end users to report the message as spam to Proofpoint. | [S1, Grade A] |
| Inbound Sender DNS | checkbox | No | Enabled | Enabled / Disabled | Toggle | Performs MX record checks on inbound sender domains and rejects connections from private IP address ranges. | [S1, Grade A] |
| Update for all users | checkbox | No | Disabled (unchecked) | Enabled / Disabled | Toggle | One-time push: overwrites ALL per-user spam thresholds with org-wide values on Save. Does NOT create persistent lock — users can re-customize immediately after. | [S1, Grade A] |

### Conditional Fields

| Field | Appears When | Description | Source |
|-------|-------------|-------------|--------|
| Stamp text customization | Stamp & Forward != No | UNKNOWN — whether the stamp text ("***Spam***") is customizable not documented in grade-A | INCOMPLETE |
| Per-user override lock | NEVER — not available | No persistent mechanism to prevent per-user spam threshold overrides documented | [S1, Grade A] (gap) |

### Edge Cases

| Scenario | Behavior | Source |
|----------|----------|--------|
| Spam Trigger Level at minimum (most aggressive) | High false positive rate; legitimate business email quarantined | [S1, Grade A]; [D — S19] |
| Quarantine Bulk Email enabled + newsletter subscription | Subscribed newsletters from bulk senders (Mailchimp, etc.) quarantined | [S1, Grade A] |
| Stamp & Forward = All + Spam Trigger Level aggressive | Nearly all external email may receive spam stamp — user confusion | [S1, Grade A] (inferred) |
| Update for all users checked, saved, then unchecked | Push already happened — all per-user settings already overwritten; unchecking does not restore them | [S1, Grade A] |
| Easy Spam Reporting link clicked by attacker | UNKNOWN — whether the reporting link could be abused for feedback loops | INCOMPLETE |

---

## Screen 2: Users & Groups > [User] > Spam Settings

**Navigation:** Users & Groups > select user > Spam tab
**Source:** [S1, Grade A]

```
+---------------------------------------------------------------+
| Users & Groups > user@company.com > Spam                      |
+---------------------------------------------------------------+
|                                                               |
|  Personal Spam Trigger Level                                  |
|  [--|------|------O------|--]                                  |
|  More aggressive          Less aggressive                     |
|                                                               |
|  Note: This overrides the organization-wide setting           |
|  for this user only.                                          |
|                                                               |
|  +--------+                                                   |
|  | Save   |                                                   |
|  +--------+                                                   |
+---------------------------------------------------------------+
```

### All Fields

| Field | Type | Required | Default | Options | Validation | Description | Source |
|-------|------|----------|---------|---------|------------|-------------|--------|
| Per-user Spam Trigger Level | slider | No | Inherits organization default | Same range as org-wide slider | Numeric | Individual user's spam threshold. Overrides company setting. Reverts to org default when admin uses "Update for all users." | [S1, Grade A] |

### Edge Cases

| Scenario | Behavior | Source |
|----------|----------|--------|
| User sets threshold to maximum (least aggressive) | User effectively disables spam filtering for themselves; no admin notification | [S1, Grade A] |
| Admin pushes "Update for all users" | This user's custom threshold is overwritten with org default | [S1, Grade A] |
| User re-customizes threshold immediately after admin push | New per-user setting takes effect; no mechanism to prevent | [S1, Grade A] |

---

## Screen 3: Safe / Blocked Sender Lists (Spam Context)

**Navigation:** Company Settings > Filters (organization level) OR Users & Groups > [User] > Safe/Blocked Senders
**Source:** [S1, Grade A]

```
+---------------------------------------------------------------+
| Safe Senders                                                  |
+---------------------------------------------------------------+
|  +-------------------------------------------+                |
|  | user@trusted.com                           |  [Remove]     |
|  | @trusteddomain.com                         |  [Remove]     |
|  +-------------------------------------------+                |
|  Add: [__________________]  [Add]                             |
+---------------------------------------------------------------+
| Blocked Senders                                               |
+---------------------------------------------------------------+
|  +-------------------------------------------+                |
|  | spammer@bad.com                            |  [Remove]     |
|  +-------------------------------------------+                |
|  Add: [__________________]  [Add]                             |
+---------------------------------------------------------------+
```

### All Fields

| Field | Type | Required | Default | Options | Validation | Description | Source |
|-------|------|----------|---------|---------|------------|-------------|--------|
| Safe Sender Address | text | No | Empty list | user@domain.com or @domain.com | Valid email or @domain format | Messages from safe senders bypass spam filtering. Organization list takes precedence over user list conflicts. | [S1, Grade A] |
| Blocked Sender Address | text | No | Empty list | user@domain.com or @domain.com | Valid email or @domain format | Messages from blocked senders are always quarantined regardless of spam score. Organization blocked list overrides user safe list. | [S1, Grade A] |

### Precedence Rules

| Scenario | Result | Source |
|----------|--------|--------|
| Sender on organization safe list AND user blocked list | Message DELIVERED (organization safe wins) | [S1, Grade A] |
| Sender on organization blocked list AND user safe list | Message QUARANTINED (organization blocked wins) | [S1, Grade A] |
| Sender on user safe list only | Message delivered (user safe applies) | [S1, Grade A] |
| Sender on user blocked list only | Message quarantined (user blocked applies) | [S1, Grade A] |

---

## Screen 4: PPS Spam Module — INCOMPLETE

**Navigation:** UNKNOWN — PPS admin console; exact path behind authentication wall
**Source:** [S2, Grade B] (training material only)

**NOTE: This entire screen is INCOMPLETE. Fields documented below are from Grade B training material only. PPS admin guide is behind authentication wall.**

### PPS Spam Module Components

| Component | Description | Tunability | Source |
|-----------|------------|------------|--------|
| Spam Classifiers | Multiple scoring classifiers for different spam types | Tunable per-classifier threshold | [S2, Grade B] |
| Suspected Spam Handling | Separate threshold for "likely spam" vs. confirmed spam | Configurable action per threshold | [S2, Grade B] |
| Safe/Blocked Sender Lists | Organization-managed allow/deny lists at module level | Add/remove entries | [S2, Grade B] |
| False Positive/Negative Reporting | Feedback loop for classifier improvement | Submit samples | [S2, Grade B] |
| Custom Spam Rules | Specialized rules beyond classifier scoring | Create/edit/delete | [S2, Grade B] |

### PPS Spam Scoring (Inferred)

| Score Range | Classification | Default Action | Source |
|------------|---------------|----------------|--------|
| 0–8 | Not spam | Deliver | [U — ASSUMPTION from Essentials Stamp & Forward] |
| 9–19 | Suspected/borderline | Stamp subject (if configured) | [S1, Grade A] — Stamp & Forward Partial |
| 20+ | Definite spam | Quarantine | [U — ASSUMPTION] |
| 100 | Highest-confidence | Block/Quarantine | [D — community article] |

**CRITICAL:** Score ranges INFERRED from Essentials Stamp & Forward options. PPS may use a different scale. [S2, Grade B] confirms scoring exists but does not document the range.

---

## Worked Examples

### Example 1: Initial Spam Configuration for New Organization

```
Scenario: A new organization has been provisioned on Proofpoint
Essentials and needs baseline spam protection configured.

Screen: Security Settings > Email > Spam Settings
  Spam Trigger Level:      [System default — do not change yet]
  Quarantine Bulk Email:   [ ] Disabled  (leave off initially)
  Stamp & Forward:         [No]
  Easy Spam Reporting:     [x] Enabled
  Inbound Sender DNS:      [x] Enabled   (leave on — default)
  Update for all users:    [ ] Unchecked
  Click: Save

# WHY: Start with defaults to establish a baseline. Easy Spam Reporting
# empowers users to provide feedback. Inbound Sender DNS is already
# enabled by default and provides connection-level protection.

# GOTCHA: Do NOT enable "Quarantine Bulk Email" on day one. Users may
# have subscribed newsletters that Proofpoint classifies as bulk. Audit
# inbound mail for 1-2 weeks before enabling to identify trusted bulk
# senders and add them to the safe list first.
```

### Example 2: Aggressive Spam Filtering for Executive Protection

```
Scenario: The CEO is receiving targeted spam that bypasses the default
threshold. Admin needs to tighten spam filtering for the CEO only.

Screen: Users & Groups > ceo@company.com > Spam
  Per-user Spam Trigger Level: [Lower/more aggressive]
  Click: Save

# WHY: Per-user threshold allows the CEO to have tighter filtering
# without affecting all users in the organization. This avoids false
# positives for other users who have different spam profiles.

# GOTCHA: If the admin later uses "Update for all users" from the org
# spam settings page, this per-user override will be ERASED. The CEO's
# threshold will revert to the org default. The admin must re-apply
# the per-user setting after any org-wide push.
```

### Example 3: Stamp & Forward for User Awareness

```
Scenario: The organization wants users to be aware of borderline spam
rather than silently quarantining it. Users should see "***Spam***"
in the subject line for messages scoring 9-19.

Screen: Security Settings > Email > Spam Settings
  Stamp & Forward:         [Partial (score 9-19)]
  Click: Save

Wait: 5-30 minutes for propagation

# WHY: Stamp & Forward "Partial" delivers borderline messages to the
# inbox but clearly marks them. Users learn to recognize spam patterns
# and can report via Easy Spam Reporting if enabled.

# GOTCHA: Users will see "***Spam***" prepended to subject lines of
# borderline messages. Some users will be alarmed and report this as
# a system error. COMMUNICATE to users before enabling Stamp & Forward
# that this is intentional and part of the spam filtering strategy.
# Also note: propagation takes 5-30 minutes. Testing immediately
# after save will show old behavior.
```

### Example 4: Configuring Safe Sender List to Prevent Newsletter Quarantine

```
Scenario: After enabling "Quarantine Bulk Email," users report
that newsletters from mailchimp.com and constantcontact.com are
being quarantined.

Screen: Company Settings > Filters (organization-level safe list)
  Safe Sender: [@mailchimp.com]    [Add]
  Safe Sender: [@constantcontact.com]  [Add]

# WHY: Adding bulk sending domains to the organization safe list
# ensures these senders bypass spam filtering for all users. This
# resolves the quarantine issue for subscribed newsletters.

# GOTCHA: Adding @mailchimp.com to the safe list bypasses spam
# filtering for ALL senders using Mailchimp infrastructure — including
# potential spam campaigns sent via Mailchimp. A more precise approach
# is to add specific sender addresses (newsletter@company.com) rather
# than the sending platform's domain. However, many newsletters use
# unique bounce addresses per campaign, making address-level entries
# impractical. Balance precision vs. maintenance burden.
```

### Example 5: Resetting All Per-User Spam Thresholds

```
Scenario: Many users have customized their spam thresholds, some
making them so permissive that spam reaches their inbox.

Screen: Security Settings > Email > Spam Settings
  Spam Trigger Level:    [Desired org-wide level]
  [x] Update for all users  <-- CHECK THIS
  Click: Save

# WHY: Resets all per-user customizations to the org standard.

# GOTCHA: DESTRUCTIVE and IRREVERSIBLE. All per-user settings are
# overwritten on Save. Document any intentional per-user settings
# (VIPs, executives) BEFORE clicking Save. This is a one-time push,
# NOT a lock — users can re-customize immediately after.
```

---

## Version-Specific Notes

| Version / Product | Change | Impact | Source |
|------------------|--------|--------|--------|
| Essentials (2023 UI refresh) | Navigation updated to Security Settings > Email > Spam Settings | Pre-2023 videos show different nav path | Tribal knowledge |
| Essentials Admin Guide (2014) | 12-year-old source — UI has changed | Use for field logic; verify current navigation | [S1, Grade A]; stale source warning |
| PPS (all versions) | Spam module in separate admin console | PPS tuning (items 3.8, 3.9) not available in Essentials UI | [S2, Grade B] |
| PPS community best practice | Incremental tuning recommended | Start at score 100 confidence, reduce gradually over 24-48 hours | [D — community article] |
