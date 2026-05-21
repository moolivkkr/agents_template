# Archive & Retention Policies — Advanced Configuration Reference
## Proofpoint Essentials Archive (Compliance Archiving)

> All options documented, organized by screen.
> INCOMPLETE sections indicate fields behind authentication walls or otherwise undocumented in accessible sources.

---

## Screen 1: Settings > Retention

**Navigation:** Proofpoint Essentials Archive admin > Settings > Retention
**Source:** [S27, Grade A]; [S1, Grade A] (supplemental)

```
+---------------------------------------------------------------+
| Settings > Retention                                          |
+---------------------------------------------------------------+
|                                                               |
|  Retention Period                                             |
|  +-----------+  +-----------+                                 |
|  | Years [1] |  | Months[0] |                                 |
|  +-----------+  +-----------+                                 |
|                                                               |
|  Default: 12 months (1 year)                                  |
|  Maximum: 10 years                                            |
|                                                               |
|  +--------+                                                   |
|  | Save   |                                                   |
|  +--------+                                                   |
+---------------------------------------------------------------+
```

### All Fields

| Field | Type | Required | Default | Options | Validation | Description | Source |
|-------|------|----------|---------|---------|------------|-------------|--------|
| Retention Period — Years | number | No | 1 | Integer (0–10) | Combined years + months must not exceed 10 years | Years component of the total archive retention window. Messages older than the total period are eligible for deletion. | [S27, Grade A] |
| Retention Period — Months | number | No | 0 (default total is 12 months = 1 year + 0 months) | Integer (0–11) | 0–11; combined with Years must not exceed 10 years total | Months component of the total retention period. Works with Years field. | [S27, Grade A] |

### Edge Cases

| Scenario | Behavior | Source |
|----------|----------|--------|
| Combined years + months exceeds 10 years | UNKNOWN — whether UI rejects or auto-caps not documented | [S27, Grade A] (gap) |
| Retention set to 0 years 0 months | UNKNOWN — whether immediate deletion occurs or a minimum retention applies | INCOMPLETE |
| Retention reduced after messages accumulate | Messages already past the new shorter retention become immediately eligible for deletion | [U — ASSUMPTION; standard archive behavior] |
| Legal Hold active when retention period saved | Retention period is saved but NOT enforced until Legal Hold is deactivated | [S27, Grade A] |

---

## Screen 2: Settings > Legal Hold

**Navigation:** Proofpoint Essentials Archive admin > Settings > Legal Hold
**Source:** [S27, Grade A]

```
+---------------------------------------------------------------+
| Settings > Legal Hold                                         |
+---------------------------------------------------------------+
|                                                               |
|  Company Legal Hold                                           |
|                                                               |
|  +-----------------------+                                    |
|  | [OFF] =========O      |  <-- Slider toggle                |
|  +-----------------------+                                    |
|                                                               |
|  When ON: All archived messages are retained indefinitely.    |
|  Retention-based deletion is suspended company-wide.          |
|                                                               |
+---------------------------------------------------------------+
```

### All Fields

| Field | Type | Required | Default | Options | Validation | Description | Source |
|-------|------|----------|---------|---------|------------|-------------|--------|
| Company Legal Hold | toggle_slider | No | Off (disabled) | On / Off | Toggle; no additional parameters | Suspends retention-based deletion for ALL archived messages company-wide. Messages retained indefinitely until hold is deactivated. | [S27, Grade A] |

### Conditional Fields

| Field | Appears When | Description | Source |
|-------|-------------|-------------|--------|
| Per-User Legal Hold | INCOMPLETE — not documented | Per-user or per-custodian legal hold is not documented in accessible sources. May exist in enterprise tier. | [S27, Grade A] (gap) |

### Edge Cases

| Scenario | Behavior | Source |
|----------|----------|--------|
| Legal Hold activated then deactivated | Messages that aged past retention during hold may become immediately eligible for deletion | [U — ASSUMPTION; not documented] |
| Legal Hold toggled rapidly (On then Off) | UNKNOWN — whether there is a processing lag that affects which messages are preserved | INCOMPLETE |
| Legal Hold active with 0-month retention | All messages retained indefinitely until hold is lifted, regardless of retention setting | [S27, Grade A] (inferred) |

---

## Screen 3: Archive Search — INCOMPLETE

**Navigation:** UNKNOWN — Proofpoint Essentials Archive search interface
**Source:** [S1, Grade A] (feature exists); [S27, Grade A] (not covered)

**NOTE: This entire screen is INCOMPLETE. Archive search exists as a feature but the configuration UI, search parameters, and access control fields are not documented in accessible grade-A sources.**

### Inferred Fields (from Standard Archive Search Functionality)

| Field | Type | Description | Source |
|-------|------|-------------|--------|
| Date Range | date_range | Start and end dates for search window | [U — ASSUMPTION; standard archive] |
| Sender | text | Sender email address or domain filter | [U — ASSUMPTION; standard archive] |
| Recipient | text | Recipient email address or domain filter | [U — ASSUMPTION; standard archive] |
| Keywords | text | Full-text search across message body and subject | [U — ASSUMPTION; standard archive] |
| Attachment Name | text | Filter by attachment filename | [U — ASSUMPTION; standard archive] |

### Search Access Roles

| Role | Access Level | Source |
|------|-------------|--------|
| Organization Admin | Full archive search | [U — ASSUMPTION] |
| Compliance Officer | UNKNOWN — whether a dedicated compliance role exists | INCOMPLETE |
| End User | UNKNOWN — whether users can search their own archived messages | INCOMPLETE |

---

## Screen 4: Archive Export — INCOMPLETE

**Navigation:** UNKNOWN — likely accessible from Archive Search results
**Source:** INCOMPLETE — no grade-A source documents export workflow

**NOTE: This screen is INCOMPLETE. Export functionality for compliance reporting and e-discovery is a standard archive feature but is not documented in accessible sources for Proofpoint Essentials Archive.**

### Inferred Fields

| Field | Type | Description | Source |
|-------|------|-------------|--------|
| Export Format | dropdown | Output format (PST, EML, PDF) | [U — ASSUMPTION; standard archive] |
| Export Scope | selection | Selected messages vs. full search results | [U — ASSUMPTION; standard archive] |
| Include Attachments | checkbox | Whether to include message attachments in export | [U — ASSUMPTION; standard archive] |
| Export Destination | UNKNOWN | Download, email delivery, or external storage | INCOMPLETE |

---

## Retention Policy Reference Table

| Regulation | Minimum Retention | Proofpoint Setting | Notes | Source |
|-----------|-----------------|-------------------|-------|--------|
| No regulation | 1 year | Years: 1, Months: 0 (default) | Proofpoint default — adequate only for unregulated orgs | [S27, Grade A] |
| FINRA Rule 4511 | 3 years | Years: 3, Months: 0 | Financial industry communications | General compliance guidance |
| HIPAA | 6 years | Years: 6, Months: 0 | Healthcare communications and records | General compliance guidance |
| SEC Rule 17a-4 | 7 years | Years: 7, Months: 0 | Broker-dealer electronic records | General compliance guidance |
| SOX Section 802 | 7 years | Years: 7, Months: 0 | Audit-related records | General compliance guidance |
| Maximum | 10 years | Years: 10, Months: 0 | Proofpoint maximum — cannot exceed | [S27, Grade A] |

---

## Worked Examples

### Example 1: Healthcare Organization — HIPAA Compliant Retention

```
Scenario: A hospital needs 6-year email retention for HIPAA compliance.

Screen: Settings > Retention
  Retention Period — Years: [6]
  Retention Period — Months: [0]
  Click: Save

# WHY: HIPAA requires 6 years of medical records retention. The default
# 12-month retention would leave the organization non-compliant and
# expose them to regulatory fines if audited.

# GOTCHA: Configure this IMMEDIATELY after archive provisioning. If you
# run with the default 12-month retention for any period, messages older
# than 12 months will be deleted and CANNOT be recovered when you later
# increase the retention period.
```

### Example 2: Activating Legal Hold for Litigation

```
Scenario: A company receives a litigation hold notice requiring preservation
of all employee email for pending lawsuit.

Step 1 — Verify current retention:
  Screen: Settings > Retention
  Confirm: Current retention period noted (e.g., 3 years)

Step 2 — Activate legal hold:
  Screen: Settings > Legal Hold
  Company Legal Hold: [ON]
  Save

# WHY: Legal hold suspends ALL retention-based deletions company-wide.
# This ensures no relevant evidence is destroyed during the litigation
# period, satisfying spoliation obligations.

# GOTCHA: Legal hold is COMPANY-WIDE. There is no per-user hold in
# Essentials. Activating the hold preserves ALL messages for ALL users,
# which will cause archive storage to grow indefinitely. Plan for
# increased storage costs during the hold period.
```

### Example 3: Deactivating Legal Hold After Litigation Closes

```
Scenario: Litigation has concluded and legal counsel authorizes lifting
the hold that has been active for 18 months.

Step 1 — Consult with legal counsel (OUTSIDE Proofpoint):
  Confirm: Written authorization to lift hold received

Step 2 — Consider export before deactivation:
  Screen: Archive Search (INCOMPLETE — fields not documented)
  Action: Export relevant custodian messages before lifting hold

Step 3 — Deactivate hold:
  Screen: Settings > Legal Hold
  Company Legal Hold: [OFF]
  Save

# WHY: Normal retention resumes. Storage costs decrease as aged
# messages become eligible for deletion again.

# GOTCHA: Messages that passed their retention date DURING the hold
# period may become IMMEDIATELY eligible for deletion when the hold is
# lifted. If you need to preserve specific messages beyond this point,
# export them BEFORE deactivating the hold. This behavior is ASSUMED
# (not documented in Proofpoint sources) but is standard for archive
# systems. [U — ASSUMPTION]
```

### Example 4: Financial Services — SEC 17a-4 Compliance Setup

```
Scenario: A broker-dealer firm must configure email archiving for
SEC Rule 17a-4 (7-year retention for electronic communications).

Step 1 — Set retention:
  Screen: Settings > Retention
  Retention Period — Years: [7]
  Retention Period — Months: [0]
  Click: Save

Step 2 — Document the configuration:
  Record: "Archive retention set to 7 years per SEC 17a-4 on [date]"
  Rationale: Compliance audit trail

# WHY: SEC Rule 17a-4 requires broker-dealers to retain electronic
# communications for not less than 3 years (first 2 in accessible
# location) with a 7-year general retention. Setting to 7 years
# satisfies both requirements.

# GOTCHA: Proofpoint Essentials Archive maximum is 10 years, which
# covers SEC 17a-4. However, if your firm has additional state-level
# requirements exceeding 10 years, you need a different archive
# solution. Also verify that the archive captures ALL mail (including
# quarantined messages) — quarantine and archive are SEPARATE systems
# and quarantined mail may not be archived.
```

### Example 5: Investigating Whether Archive Captures Quarantined Mail

```
Scenario: A compliance officer asks: "Are spam-quarantined messages
also in our archive?"

Step 1 — Understand the architecture:
  Quarantine: Company Settings > Quarantine (30-day retention, separate)
  Archive: Settings > Retention (configurable, separate)

Step 2 — Test:
  Send a test message that triggers spam quarantine.
  Wait for archive indexing period (UNKNOWN — not documented).
  Search archive for the test message.

# WHY: Quarantine and archive are independent systems in Proofpoint
# Essentials. A quarantined message may or may not appear in the
# archive depending on WHERE in the mail flow the archive captures
# messages (before or after quarantine disposition).

# GOTCHA: Do NOT assume quarantine = archived. The archive capture
# scope (pre-quarantine vs. post-delivery only) is INCOMPLETE in
# accessible documentation. Confirm with Proofpoint support whether
# your archive configuration captures quarantined messages. [A — S1,
# A — S27, gap]
```

---

## Version-Specific Notes

| Version / Product | Change | Impact | Source |
|------------------|--------|--------|--------|
| Essentials Archive (all accessible versions) | Full admin guide behind authentication wall | Features beyond retention and legal hold may exist but are not documented | [S27, Grade A] (gap) |
| Enterprise Archive (Proofpoint) | Enterprise tier may support per-custodian legal hold, granular search, and export | Essentials documentation does not confirm feature parity with Enterprise | INCOMPLETE |
| Essentials UI refresh (2023) | Navigation may have shifted from Archive admin settings | Verify current path in admin console | Tribal knowledge |
