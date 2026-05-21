# Email Filtering Policies (Proofpoint Essentials) — Advanced Configuration Reference

> All options documented for power users. Organized by screen, not by workflow step.
> For the sequential walkthrough, see [workflow.md](workflow.md).
> For the minimal path, see [quickstart.md](quickstart.md).

---

## Screen 1: Security Settings > Email > Filter Policies (List View)

**Navigation:** Left nav → Security Settings → Email → Filter Policies

**Pre-2023 path:** Company Settings > Filters [S1 — Grade A, 2014 admin guide]
**Post-2023 path:** Security Settings > Email > Filter Policies [V20 — Grade B, 2023 training video]

Both paths reach the same underlying feature. The 2023 UI path is authoritative for current deployments.

### List View Elements

| Element | Type | Description | Source |
|---------|------|-------------|--------|
| Inbound tab | Tab | Shows all inbound filters for the organization | [S1] |
| Outbound tab | Tab | Shows all outbound filters for the organization | [S1] |
| New Filter button | Button | Opens the Create Filter form for the active direction tab | [S1] |
| Filter search field | Text input | Searches filter list by name. Whether condition/action/scope search is supported is INCOMPLETE. | [S1] |
| Filter row: Name | Display | Shows filter name; click to open Edit form | [S1] |
| Filter row: Scope | Display | Company / Group / User | [S1] |
| Filter row: Priority | Display | Low / Normal / High | [S1] |
| Filter row: Status | Display | Enabled / Disabled | [S1] |
| Filter row: Enable/Disable toggle | Toggle | Activates or deactivates the filter without deletion | [S1] |
| Filter row: Edit | Link/button | Opens Edit Filter form | [S1] |
| Filter row: Duplicate | Link/button | Creates a copy with "(copy)" appended to the name | [S1] |
| Filter row: Delete | Link/button | Permanently deletes the filter | [S1] |

### Conditional Fields in List View

None — list view does not have conditional fields.

### Edge Cases

- The Inbound and Outbound tabs are independent lists. You cannot move a filter between directions. If you need to change direction, duplicate the filter, then edit the copy. Note: direction cannot be changed in Edit — you must recreate or use duplicate as a starting point. [S1]
- Disabled filters remain in the list and count toward any platform filter limits (maximum filter count is UNKNOWN — not documented in accessible sources).

---

## Screen 2: Filter Policies > New Filter / Edit Filter

**Navigation:** Filter Policies > New Filter OR Filter Policies > [filter name] > Edit

**Note:** New Filter and Edit Filter use the same form. In Edit mode, the Direction field is read-only.

### All Fields

| Field | Type | Required | Default | Valid Values | Validation | Description | Gotcha | Source |
|-------|------|----------|---------|-------------|------------|-------------|--------|--------|
| Name / Description | Text | Yes | — | Any free text | No documented character limit | Internal identifier. Not shown to end users. | Names are not enforced unique across Inbound/Outbound direction. Duplicate names across directions cause audit confusion. | [S1] |
| Direction | Fixed (read-only in Edit) | Yes | Set by tab at creation | Inbound, Outbound | Cannot be changed after save | Determines mail flow direction for this filter | Must delete and recreate if wrong direction chosen. Use Duplicate first to preserve config. | [S1] |
| Scope | Dropdown | Yes | — | Company, Group, User | Must select one | Determines which mailboxes this filter evaluates against | Processing order is User > Group > Company — per-user filters fire BEFORE Company filters. See G5. | [S1, V20] |
| Group (conditional) | Dropdown | Yes (if Scope=Group) | — | List of provisioned groups | Group must exist | Target group for Group-scope filters | INCOMPLETE: whether multi-group selection is supported is not documented. | [S1] |
| User (conditional) | Text / lookup | Yes (if Scope=User) | — | Valid email address in org | User must be provisioned | Target user for User-scope filters | End users creating their own personal filters also use this scope. Admin-created User-scope filters and user-created filters occupy the same namespace. | [S1] |
| Priority | Dropdown | No | Low | Low, Normal, High | — | Evaluation order within same scope level. Higher priority = evaluated first. | Priority is scoped — "High" priority in Company scope still evaluates AFTER all User-scope filters regardless of priority. | [S1] |
| Condition Type | Dropdown | Yes | — | See Condition Types table | — | The email attribute this condition tests | Multiple conditions can be added; all conditions evaluate with AND logic | [S1] |
| Operator | Dropdown | Yes | — | See Operators table | Depends on condition type | Logical relationship between condition and value | Not all operators available for all condition types. Exact compatibility matrix is INCOMPLETE in accessible sources. | [S1] |
| Condition Value | Text | Yes | — | Depends on condition type | Format depends on type | Value to match against | Wildcard `*@domain.com` supported for address conditions. Regex support is UNCONFIRMED in Grade A sources. | [S1] |
| Add Condition | Button | — | — | — | — | Adds another condition row | Additional conditions use AND logic. OR logic across condition groups not confirmed in Grade A sources. | [S1] |
| Primary Action (Destination) | Dropdown | Yes | — | See Actions table | — | Primary disposition for matching messages | "Encrypt" action only appears when Direction=Outbound AND Scope=Company. Selecting any other combination hides Encrypt. | [S1, V7] |
| Hide Logs | Checkbox | No | Disabled | Enabled / Disabled | — | Hides this filter's match from end-user log and quarantine digest | Does NOT hide from admin logs. Does NOT suppress the filter action — the message is still acted upon. | [S1] |
| Enforce Completely Secure SMTP Delivery | Checkbox | No | Disabled | Enabled / Disabled | — | Requires TLS + valid certificate for delivery. Message delivery FAILS if destination cannot satisfy. | Do not enable org-wide. Survey recipient domain TLS capabilities first. | [S1] |
| Enforce only TLS on SMTP Delivery | Checkbox | No | Disabled | Enabled / Disabled | — | Requires TLS but does not validate certificate | Mutually exclusive with Completely Secure TLS — behavior when both enabled is UNDOCUMENTED. | [S1] |
| Override Previous Destination | Toggle | No | Disabled | Enabled / Disabled | — | When enabled, this filter's Primary Action overrides disposition set by a higher-priority filter | Can cause lower-priority allow filters to undo quarantine decisions from DLP rules. Use with extreme caution. | [V20] |
| Stop Processing Additional Filters | Toggle | No | Disabled | Enabled / Disabled | — | When enabled, halts evaluation of all lower-priority filters in same scope after this filter matches | HIGH RISK: can silently bypass DLP and compliance filters. Audit all filters with this enabled. | [V20, S17] |
| Secondary Actions | Multiselect | No | None | Notify Recipient, Notify Admin, Add Header, Tag Subject | — | Additional actions taken in conjunction with primary action | Source: [V20 ~3:00]. Not fully documented in [S1] (supplemented by [S17] Grade D). | [V20, S17] |

### Conditional Fields (Secondary Actions)

| Condition | Field | Type | Description | Source |
|-----------|-------|------|-------------|--------|
| Secondary Action = Notify Recipient selected | Notification Template | Dropdown | Select notification template to send to message recipient. Template options are INCOMPLETE. | [V20, S17] |
| Secondary Action = Notify Admin selected | Admin Email Address | Text | Email address to receive alert when filter fires | [V20, S17] |
| Secondary Action = Add Header selected | Header Name | Text | SMTP header field name (e.g., `X-Proofpoint-Filter`) | [V20, S17] |
| Secondary Action = Add Header selected | Header Value | Text | Value to set for the header | [V20, S17] |
| Secondary Action = Tag Subject selected | Subject Tag Text | Text | Text prepended to subject line (e.g., `[BLOCKED]`) | [V20, S17] |

### Condition Types — Full Reference

| Condition Type | What It Tests | Operator Compatibility | Value Format | Notes | Source |
|---------------|--------------|----------------------|--------------|-------|--------|
| Sender Address | SMTP From header | IS, IS NOT, IS ANY OF, IS NONE OF | `user@domain.com`, `*@domain.com` | Wildcards supported. Full domain `*@domain.com` matches all senders from that domain. | [S1] |
| Recipient Address | SMTP To header | IS, IS NOT, IS ANY OF, IS NONE OF | `user@domain.com`, `*@domain.com` | Useful for per-department routing or exception rules | [S1] |
| Email Size (kb) | Total message size | IS, IS NOT (numeric) | Integer (kilobytes) | Exact operator compatibility INCOMPLETE. Size-based filtering useful for large file blocking policies. | [S1] |
| Client IP Country | Sender IP geolocation | IS, IS NOT, IS ANY OF, IS NONE OF | Country name or 2-letter code | Geo-blocking use case. Geolocation database accuracy not documented. | [S1] |
| Email Subject | Subject line | CONTAIN(S) ALL OF, CONTAIN(S) ANY OF, CONTAIN(S) NONE OF | Text string | Case sensitivity not documented. | [S1] |
| Email Headers | Any SMTP header field | CONTAIN(S) ALL OF, CONTAIN(S) ANY OF, CONTAIN(S) NONE OF | `Header-Name: value` or value only | Useful for bulk mailer detection or custom X-header filtering | [S1] |
| Email Message Content | Email body (text + HTML) | CONTAIN(S) ALL OF, CONTAIN(S) ANY OF, CONTAIN(S) NONE OF | Text string or keyword | Whether inline images or HTML attributes are scanned is INCOMPLETE. May not scan inside attachments. | [S1] |
| Raw Email | Full RFC 822 message source | CONTAIN(S) ALL OF, CONTAIN(S) ANY OF, CONTAIN(S) NONE OF | Any string | Most permissive; slowest to evaluate. Use sparingly. | [S1] |
| Attachment Type | File category (not extension/MIME type) | IS ANY OF, IS NONE OF | Windows executable components, installers, other executable components, office documents, archives, audio/visual, PGP encrypted files | Category-based buckets. Full category membership (which extensions map to which category) is INCOMPLETE in docs. | [S1] |
| Attachment Name | Attachment filename | IS, IS NOT, IS ANY OF, IS NONE OF, CONTAIN(S) ANY OF | `invoice.exe`, `*.bat` | Whether glob patterns like `*.exe` are supported is INCOMPLETE. | [S1] |

### Operators — Full Reference

| Operator | Logic | Best For | Notes | Source |
|----------|-------|---------|-------|--------|
| IS | Exact equality match | Single-value exact match (e.g., one specific sender) | Case sensitivity not documented | [S1] |
| IS NOT | Exact non-match | Exclusion of one specific value | | [S1] |
| IS ANY OF | Matches if value is in a list | Allow/block lists with multiple senders or countries | Accepts comma-separated or newline-separated list | [S1] |
| IS NONE OF | Matches if value is not in any item in the list | Inverse of IS ANY OF | | [S1] |
| CONTAIN(S) ALL OF | Matches if value contains every listed term | Strict content matching (must have all keywords) | AND across all terms in the list | [S1] |
| CONTAIN(S) ANY OF | Matches if value contains at least one listed term | Broad content scanning | OR across all terms | [S1] |
| CONTAIN(S) NONE OF | Matches if value contains none of the listed terms | Exclusion content scanning | | [S1] |

### Primary Actions — Full Reference

| Action | Direction | Scope | Description | Impact | Source |
|--------|-----------|-------|-------------|--------|--------|
| Allow (skipping spam filter) | Both | Any | Delivers message; bypasses spam scoring | Trusted sender bypass — use only for verified relay hosts | [S1] |
| Allow (but filter for spam) | Both | Any | Delivers message; spam scoring still runs | Preferred allow action — maintains spam protection | [S1] |
| Quarantine | Both | Any | Message held in quarantine console | Message is not delivered; admin can review and release | [S1] |
| Reject | Both | Any | SMTP 5xx reject; message bounced back to sender MTA | Sender receives bounce notification; can confirm address exists | [S1] |
| Nothing | Both | Any | No action; filter condition is logged but no disposition applied | Use as a passive monitoring condition or as a no-op placeholder | [S1] |
| Encrypt | Outbound only | Company only | Applies Proofpoint Encryption to outbound message | Requires Proofpoint Encryption service to be provisioned. Encrypt action hidden if Scope ≠ Company. | [S1, V7] |

---

## Screen 3: Security Settings > Email > Safe/Blocked Senders

**Navigation:** Security Settings > Email > Safe Senders / Blocked Senders

### Fields

| Field | Type | Required | Default | Valid Values | Description | Gotcha | Source |
|-------|------|----------|---------|-------------|-------------|--------|--------|
| Sender Address / Domain | Text | Yes | — | `user@domain.com` or `domain.com` | Full email address or domain to add to list. `domain.com` applies to all senders from that domain. | Domain wildcard is `domain.com` not `*@domain.com` for these lists. Format differs from filter condition values. | [S1] |
| List selector | Tab / Radio | Yes | Safe Senders | Safe Senders, Blocked Senders | Controls which list you are adding to | Blocked list always overrides Safe list for same sender. Do not add same sender to both. | [S1] |

### Precedence Rules

| Scenario | Result | Source |
|----------|--------|--------|
| Sender on Org Safe list only | Allowed; bypass spam scoring | [S1] |
| Sender on Org Blocked list only | Blocked | [S1] |
| Sender on both Org Safe AND Org Blocked list | **Blocked** (blocked wins) | [S1] |
| Sender on User Safe list, not on Org lists | Allowed for that user | [S1] |
| Sender on Org Blocked list AND User Safe list | **Blocked** (org blocked overrides user safe) | [S1] |
| User has safe-sender entry, org has no entry | Allowed for that user only | [S1] |

### Per-User Sender Lists

End users can manage their own safe and blocked sender lists from:
- The quarantine digest notification email (contains a link to add the sender to their personal list) [S1]
- The user-level UI (if granted access by admin) [S1]

Admin-level organization safe/blocked sender lists are separate from and take precedence over user-level lists. [S1]

---

## Advanced Use Cases

### Use Case 1: Outbound Encryption Trigger

**Goal:** Automatically encrypt all outbound email that contains the word "[SECURE]" in the subject line.

**Configuration:**
- Direction: Outbound
- Scope: Company (required for Encrypt action)
- Condition Type: Email Subject
- Operator: CONTAIN(S) ANY OF
- Condition Value: `[SECURE]`
- Primary Action: Encrypt

**Constraint:** Encrypt action only available at Company + Outbound. [V7 ~2:00]

**Workaround for per-group encryption:** Create a Company-scope outbound encryption filter with a recipient address condition (`IS NONE OF` for all domains outside the target group) to approximate group-scoped behavior. This is inelegant but is the only approach available without per-group Encrypt support. Source: Inferred from [V7 ~2:00] — Grade E.

---

### Use Case 2: Impersonation Protection

**Goal:** Quarantine emails where the From Name contains an executive's name but the From domain is not your organization.

**Configuration:**
- Direction: Inbound
- Scope: Company
- Condition 1: Email Headers — CONTAIN(S) ANY OF — `Firstname Lastname` (executive name)
- Condition 2: Sender Address — IS NONE OF — `*@yourdomain.com`
- Primary Action: Quarantine
- Optional: Secondary Action = Tag Subject with `[IMPERSONATION SUSPECTED]`

Source: [S17] (Grade D — third-party guide, single source). Not confirmed in Grade A docs. Treat as community-validated pattern, not official guidance.

---

### Use Case 3: Staged Deployment for Aggressive Rules

**Recommended pattern for any new rule that may have false positives:**

1. Create filter at **User scope** targeting your own test mailbox
2. Verify correct behavior over 24 hours
3. Duplicate the filter, change scope to **Group** (an IT pilot group)
4. Verify over 48 hours; adjust conditions if false positives occur
5. Duplicate again, change scope to **Company**
6. Disable User and Group test copies, or delete them

Source: [V20 ~4:30] (Grade B — Proofpoint Essentials training video)

---

### Use Case 4: Secondary Action for Passive Monitoring

Before enforcing quarantine on a new DLP content rule, run it in monitoring mode:

1. Set Primary Action to: `Nothing`
2. Add Secondary Action: `Tag Subject` with `[DLP-MONITOR]`
3. Add Secondary Action: `Notify Admin` with your email address

This lets you observe matching volume and tune conditions before switching to `Quarantine`.

Source: Inferred from [V20 ~3:00] workflow pattern — Grade E (ASSUMPTION: no explicit docs confirm "monitoring mode" pattern; inferred from available secondary action options).

---

## Version-Specific Notes

| Version / Date | Change | Impact |
|---------------|--------|--------|
| Pre-2023 UI | Navigation: Company Settings > Filters | Same functionality, different nav path |
| Post-2023 UI | Navigation: Security Settings > Email > Filter Policies | Current authoritative path |
| 2014 admin guide [S1] | Documents filters but UI has been redesigned | Field names may differ; core concepts consistent |

**STALE SOURCE WARNING:** The primary Grade A source [S1] is dated July 2014. Some field names, navigation paths, and available options may differ in the current product. Where video intelligence [V20, V7] (2023/2018) contradicts [S1], the video source reflects more recent behavior.

---

## Sources

| # | Source | Grade | Used For |
|---|--------|-------|----------|
| S1 | Proofpoint Essentials Administrator Guide (PDF, July 2014) | A | All filter fields, condition types, operators, actions, safe/blocked sender lists |
| S17 | How to Configure Email Filtering Policies in Proofpoint (InventiveHQ) | D | Secondary actions, Stop Processing, impersonation use case |
| V7 | How to Enable Proofpoint Email Encryption Service (Proofpoint, 2018) | B | Encrypt action constraint, outbound filter creation |
| V20 | Proofpoint Essentials — Configure Filter Policy (Proofpoint, 2023) | B | Navigation, secondary actions, toggles, scope precedence, propagation time |
| V21 | Proofpoint Essentials — Manage Spam Settings (Proofpoint, 2023) | B | Spam Settings / Filter Policies UI separation |
