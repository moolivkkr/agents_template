# Security Awareness Training Policies — Advanced Configuration Reference

> Full field reference organized by screen. Every field documented including optional fields omitted from quickstart.md.
> Source for all documented fields: [S3 — Proofpoint Essentials Security Awareness Admin Guide, April 2020]
> Stale source warning: S3 is dated April 2020. Current UI may have additional fields or changed option labels.

---

## Training > Assignments (List Screen)

**Navigation:** Training (top nav) > Assignments

The list view displays all assignments — both Scheduled and Duration types. Columns: Name, Type, Start Date, Due Date, Status, Actions. No documented sort or filter controls in S3.

**Actions available from list:** Create new assignment (Add Assignment button); Edit, Delete, or Clone individual assignments (per-row actions — exact UI controls not enumerated in S3).

---

## Training > Assignments > Add Assignment (Scheduled)

**Navigation:** Training > Assignments > Add Assignment, then select Type = Scheduled

### Fields

| Field | Type | Required | Default | Options / Validation | Description |
|-------|------|----------|---------|----------------------|-------------|
| Name | Text | Yes | — | Unique; no documented character limit | Internal assignment identifier; NOT visible to end users |
| Type | Dropdown | Yes | Scheduled | Scheduled, Duration | Determines date model. Switching type resets date fields. |
| Start Date | Date | Yes | — | Future date recommended | Notification email sent at 12:01 AM ET. Time zone is hardcoded to ET. |
| Due Date | Date | Yes | — | Must be after Start Date | Compliance deadline. 30-day grace period applies silently after this date. |
| Training Notification | Dropdown | No | Default | None, Always Active, Default | Email sent to user when assigned. Default uses system template. |
| Completion Notification | Dropdown | No | Default | None, Always Active, Default | Email sent when user completes assignment. |
| Reminders | Date List | No | — | Comma-separated dates | Sent ONLY to users who have not completed the assignment. Completed users do not receive reminders. |
| High Priority | Checkbox | No | Disabled | Enabled / Disabled | Locks all other assignments for the user until this one is completed. IRREVERSIBLE while active. |
| Enforce Module Order | Checkbox | No | Disabled | Enabled / Disabled | Forces sequential completion of modules in listed order. |
| Modules | Multiselect | Yes | — | Filter: Custom / Licensed / All | Training content to deliver. Only licensed modules appear in the Licensed filter. |
| Users | Multiselect | Yes | — | Filter: date range, groups | Users who will receive the assignment. |

### Conditional Fields

None — all fields are visible on the Scheduled form regardless of other selections.

### Edge Cases

- **ET time zone lock:** Start date notification fires at 12:01 AM Eastern Time. Users in UTC+8 or later time zones receive notification at a time that may be 12-13 hours after the start date in their local time.
- **High Priority + active modules:** If High Priority is enabled on an assignment after users have started other modules, those in-progress modules are immediately locked. Users must complete the High Priority assignment before resuming.
- **30-day grace period is hidden:** The Due Date shown to users is the hard deadline in their portal. The 30-day window is an admin-side extension that is not surfaced to end users.

---

## Training > Assignments > Add Assignment (Duration)

**Navigation:** Training > Assignments > Add Assignment, then select Type = Duration

### Fields

| Field | Type | Required | Default | Options / Validation | Description |
|-------|------|----------|---------|----------------------|-------------|
| Name | Text | Yes | — | Unique | Internal name |
| Type | Dropdown | Yes | Scheduled | Scheduled, Duration | Must be set to Duration |
| Training Notification | Dropdown | No | Default | None, Always Active, Default | Sent when user is enrolled |
| Completion Notification | Dropdown | No | Default | None, Always Active, Default | Sent when user completes |
| Enrollment Delay | Number | No | — | Days (0 = ~30 min delay) | Days after being added before enrollment begins |
| Assignment Due Within | Number | No | — | Days | Days after enrollment by which user must complete. Behavior when blank is UNKNOWN — not documented in S3. |
| High Priority | Checkbox | No | Disabled | Enabled / Disabled | Locks other assignments |
| Enforce Module Order | Checkbox | No | Disabled | Enabled / Disabled | Sequential completion |
| Modules | Multiselect | Yes | — | Filter: Custom / Licensed / All | Training content |
| Users | Multiselect | Yes | — | Filter: date range, groups | Initial user pool |

### Conditional Fields

No Start Date or Due Date fields appear on Duration type — these are replaced by Enrollment Delay and Assignment Due Within, which are per-user relative timers.

### Edge Cases

- **Adding users post-creation:** New users added to an existing Duration assignment start their individual enrollment delay timer from the date of addition — not from the original assignment creation date. This is the intended new-hire behavior.
- **Enrollment Delay = 0:** Does not mean instant enrollment. Processing delay of approximately 30 minutes applies.
- **Assignment Due Within blank:** Behavior is UNKNOWN per S3. Assumption [Grade U]: assignment runs indefinitely without a due date — verify in current UI before relying on this for compliance purposes.

---

## Phishing > Campaigns (List Screen)

**Navigation:** Phishing (top nav) > Campaigns

List view of all campaigns. Status values observed in S3: Pending, In Progress, Completed, Cancelled, Archived. Actions per row: Edit (Pending only), Clone, Cancel (In Progress only), Archive (Completed/Cancelled), Unarchive (Archived), Delete (any state — permanent).

---

## Drive-by Phishing Campaign

**Navigation:** Phishing > Campaigns > Add Campaign > Drive-by

Simulates a click-based phishing attack. Users who click the phishing link are redirected to a Teachable Moment. No credentials or data are collected.

### Fields

| Field | Type | Required | Default | Options / Validation | Description |
|-------|------|----------|---------|----------------------|-------------|
| Campaign Title | Text | Yes | — | Unique | Internal name only; not visible to users |
| Email Templates | Multiselect | Yes | — | Filter: Language, Category, AFR | One or more phishing email templates. Each user receives one from the pool. |
| Campaign Users | Multiselect | Yes | — | Groups, lists, completed campaign results | Target recipients |
| Teachable Moment | Dropdown | Yes | — | Filter: Category, Language | Educational page shown post-click. Single selection; applies to all users in the campaign. |
| Schedule | Radio | Yes | — | Specific Date/Time, Random | Delivery timing |
| Data Collection Period | Select/Number | No | 7 days | Custom days or indefinite | Window for recording interactions |

### Conditional Fields

| Condition | Effect |
|-----------|--------|
| Schedule = Specific Date/Time | Date and time picker fields appear |
| Schedule = Random | Date range (window start/end) and time-of-day range fields appear — INCOMPLETE: exact sub-fields for random window not enumerated in S3 |

---

## Data Entry Phishing Campaign

**Navigation:** Phishing > Campaigns > Add Campaign > Data Entry

All fields identical to Drive-by. The distinction is in the template pool — Data Entry templates include a landing page that prompts for credentials. Passwords entered are NOT stored; only the submission event (user attempted to enter credentials) is recorded.

### Additional Notes

- Requires legal/privacy team clearance before first use — credential harvesting simulation may have GDPR or employment law implications in some jurisdictions. [S3 — implied by note that passwords are not collected; privacy implication is ASSUMPTION Grade U]
- Landing page customization (custom logos, text) is referenced in S3 but the customization workflow is not documented — INCOMPLETE.

---

## Classic Attachment Phishing Campaign

**Navigation:** Phishing > Campaigns > Add Campaign > Classic Attachment

All fields identical to Drive-by. Uses DOC or HTML file attachments. Records whether the user opened the attachment.

### Edge Cases

- HTML attachment-based campaigns may be blocked by recipient email clients with strict HTML mail policies. If failure rates appear abnormally low, check whether corporate email gateways are stripping HTML attachments before delivery.

---

## Attachment Phishing Campaign (PDF / DOCX / XLSX)

**Navigation:** Phishing > Campaigns > Add Campaign > Attachment

All fields identical to Drive-by. PDF, DOCX, and XLSX formats available — broader than Classic Attachment (DOC/HTML only).

### Edge Cases

- DOCX and XLSX tracking may depend on macro enablement. Users with macro execution disabled in Office will not trigger the open-tracking event for DOCX/XLSX templates. [S3 — inferred from how macro-based tracking works; ASSUMPTION Grade U for specific tracking mechanism]
- PDF tracking typically uses an embedded image or link. This tracking is generally more reliable across email clients than macro-based tracking.

---

## Follow-Up Campaign

**Navigation:** Phishing > Campaigns > Add Campaign > Follow Up

Targets users based on prior campaign performance. Requires a completed or archived campaign as the source.

### Fields

| Field | Type | Required | Default | Options / Validation | Description |
|-------|------|----------|---------|----------------------|-------------|
| Campaign Title | Text | Yes | — | Unique | Internal name |
| Source Campaign | Dropdown | Yes | — | Completed or Archived campaigns | Campaign whose results define the user pool |
| User Selection Criteria | Multiselect | Yes | — | Clicked, Submitted Data, Opened Attachment, Reported Phishing | Which failure category to target |
| Email Templates | Multiselect | Yes | — | As per campaign type | Templates for this follow-up |
| Teachable Moment | Dropdown | Yes | — | Category, Language | Post-interaction education |
| Schedule | Radio | Yes | — | Specific, Random | Delivery timing |
| Data Collection Period | Select/Number | No | 7 days | Custom days, indefinite | Data recording window |

### Edge Cases

- **Reported Phishing criterion** requires PhishAlarm to be deployed. If PhishAlarm is not deployed, this criterion will return zero users.
- **Source campaign must be Completed or Archived** — the campaign must have finished its data collection period. An In Progress campaign cannot be used as a source.
- **Empty user pool:** If the source campaign had zero clicks/submissions/opens, the Follow-Up campaign user pool will be empty. Verify user count before saving.

---

## Phishing Template Selection and Customization

**Navigation:** Within any campaign creation form > Email Templates field

### Filter Options

| Filter | Values | Source |
|--------|--------|--------|
| Language | Multiple languages (exact list not enumerated in S3) | [S3] |
| Category | Template themes — exact categories not enumerated in S3 — INCOMPLETE | [S3] |
| Average Failure Rate (AFR) | Numeric percentage; sortable — exact UI controls not documented | [S3] |

**Template distribution when multiple selected:** When multiple templates are selected for one campaign, each user receives one template from the pool. The distribution algorithm (random, sequential, or AFR-weighted) is UNKNOWN — not documented in S3.

**Template customization:** Custom phishing template creation is referenced but the workflow is not documented in S3 — INCOMPLETE. Custom templates likely require elevated license tier.

---

## Teachable Moment Selection

**Navigation:** Within any campaign creation form > Teachable Moment field

Selection by Category and Language. Multilingual support documented. Custom Teachable Moment creation is referenced in S3 but the creation workflow is not documented — INCOMPLETE; behind auth wall per doc-corpus gap analysis.

---

## Campaign Scheduling — Random Mode

**Navigation:** Within campaign creation form > Schedule = Random

Random scheduling distributes emails across a window of days and times. Exact sub-fields (window start date, window end date, allowed delivery hours, allowed delivery days of week) are not enumerated in S3. **INCOMPLETE — random scheduling sub-field configuration requires UI verification.**

---

## Data Collection Period — Extended Reference

| Value | Behavior |
|-------|----------|
| 7 days (default) | Data recorded for 7 days after campaign launch |
| Custom (N days) | Data recorded for N days after launch |
| Indefinite | Data recorded until admin manually closes collection — exact mechanism for closing indefinite collection not documented in S3 |

Post-period interactions (clicks, opens) are silently ignored and do not appear in reports. [S3]
