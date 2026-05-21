# Security Awareness Training Policies — Gotchas and Known Limitations

> Source for all SAT-specific findings: [S3 — Proofpoint Essentials Security Awareness Admin Guide, April 2020]
> No video coverage exists for SAT — video-intelligence.md confirms zero SAT video findings.
> No community/forum sources were identified for SAT-specific gotchas during research.
> Stale source note: S3 is 6 years old (April 2020). Some behaviors may have changed in current UI.

---

## Summary

| # | Gotcha | Severity | Source Grade | Version-Specific |
|---|--------|----------|-------------|-----------------|
| G1 | Start date notification fires at 12:01 AM Eastern Time (ET) regardless of user time zone | HIGH | A [S3] | All documented versions |
| G2 | 30-day grace period after Due Date is hidden from end users | HIGH | A [S3] | All documented versions |
| G3 | High Priority assignment immediately locks all other in-progress training | HIGH | A [S3] | All documented versions |
| G4 | Edit is only allowed in Pending state — campaign cannot be modified after launch | HIGH | A [S3] | All documented versions |
| G5 | Enrollment Delay = 0 does not mean instant enrollment (~30-minute processing delay) | MEDIUM | A [S3] | All documented versions |
| G6 | Reminders fire only to incomplete users — completed users receive nothing | MEDIUM | A [S3] | All documented versions |
| G7 | Data Entry campaigns: passwords are NOT collected, but legal/privacy clearance still required | MEDIUM | A [S3] | All documented versions |
| G8 | Data collection period default (7 days) is often too short for compliance use cases | MEDIUM | A [S3] | All documented versions |
| G9 | Follow-Up campaign requires source campaign in Completed or Archived state | MEDIUM | A [S3] | All documented versions |
| G10 | Reported Phishing criterion in Follow-Up campaigns requires PhishAlarm deployment | MEDIUM | A [S3] | All documented versions |
| G11 | Template distribution across multiple selected templates is undocumented | LOW | E — Inferred from S3 field description | All documented versions |
| G12 | Campaigns sent as large batches (Specific schedule) enable recipient-to-recipient advance warning | LOW | A [S3] — inferred from Random scheduling recommendation | All documented versions |
| G13 | Duration assignment: adding users to existing assignment restarts their individual delay timer | MEDIUM | A [S3] | All documented versions |
| G14 | S3 source is 6 years old — UI and feature set may have changed substantially | HIGH | A [S3] — stale source risk | Documented behavior: SAT April 2020 |

---

## Details

### G1: Start Date Notification Fires at 12:01 AM Eastern Time

**What you'd expect:** Notification emails sent "on the start date" would deliver at a reasonable time in each user's local time zone.

**What actually happens:** All training notifications fire at 12:01 AM Eastern Time (ET) on the start date. For users in UTC+5 or later, the notification arrives at the start of their business day. For users in UTC-8 (Pacific), it arrives the night before their start date. For users in UTC+8 or later (Asia-Pacific), the notification may arrive on what they consider the previous day.

**Workaround:** Set the Start Date one day earlier than the intended program start for users in UTC+8 or later time zones. For globally distributed organizations, consider creating time-zone-specific assignments with adjusted start dates.

**Source:** [S3 — SAT Admin Guide, April 2020] — Grade A
**Versions affected:** All (April 2020 admin guide; behavior may persist in current version)

---

### G2: 30-Day Grace Period After Due Date is Hidden From End Users

**What you'd expect:** The Due Date shown to users is the final deadline. After that date, the assignment closes.

**What actually happens:** Admins have a 30-day grace period after the Due Date during which users can still complete the assignment. However, the Due Date shown in the user portal does NOT reflect this grace period. Users believe the Due Date is a hard cutoff.

**Impact on compliance reporting:** If a user completes training on Day 35 after the Due Date (within the grace period), the completion is recorded. However, reports may flag the user as late, creating an inaccurate compliance picture depending on how reports interpret completion timestamps.

**Workaround:** Set the formal Due Date 30 days before the actual compliance deadline to use the grace period as the real enforcement window. Document this practice for auditors.

**Source:** [S3] — Grade A
**Versions affected:** All

---

### G3: High Priority Assignment Immediately Locks All Other In-Progress Training

**What you'd expect:** Enabling High Priority on an assignment would only affect future assignments, not ones users have already started.

**What actually happens:** If High Priority is enabled on an assignment after users have already started other training modules, those in-progress modules are immediately locked. Users receive no advance warning. This can cause user confusion and helpdesk tickets ("my training disappeared").

**Workaround:** Only enable High Priority at assignment creation time, before users receive their notifications. Never toggle High Priority on an active assignment unless you intentionally want to halt all other training for all assigned users.

**Source:** [S3 — implied from description of High Priority behavior; exact timing of lock application is inferred] — Grade A (behavior documented) with inferred timing edge (Grade E for the "immediately" qualifier)
**Versions affected:** All

---

### G4: Phishing Campaign Cannot Be Edited After Launch

**What you'd expect:** A running campaign could have its user list or template adjusted.

**What actually happens:** Edit is only available when a campaign is in Pending state (before the scheduled start date). Once a campaign is In Progress, no edits are possible. To change a running campaign, it must be cancelled (stopping further delivery) and re-created.

**Workaround:** Use Clone to create a copy of the campaign before making changes. Schedule the clone for a future date and cancel the original if needed.

**Source:** [S3] — Grade A
**Versions affected:** All

---

### G5: Enrollment Delay = 0 Does Not Mean Instant Enrollment

**What you'd expect:** Setting Enrollment Delay to 0 days enrolls the user immediately upon being added to the Duration assignment.

**What actually happens:** There is an approximately 30-minute processing delay even with Enrollment Delay = 0. Users are not enrolled instantly.

**Workaround:** If immediate enrollment matters (e.g., same-day new-hire onboarding kickoff), account for the 30-minute window in the onboarding process. Do not rely on instant availability of training in the user's portal.

**Source:** [S3] — Grade A
**Versions affected:** All

---

### G6: Reminders Only Go to Incomplete Users

**What you'd expect:** Reminder dates send a notification to all users in the assignment.

**What actually happens:** Reminders are sent ONLY to users who have not yet completed the assignment. Users who have completed it receive no reminder email.

**Impact:** This is the correct and intended behavior. However, admins who use reminder sends as "program pulse" communications (for tracking purposes) will find that completion rate grows as fewer and fewer users receive each reminder. This creates a misleading impression of declining engagement if not accounted for in reporting.

**Workaround:** This is correct behavior — document it for stakeholders who interpret reminder delivery counts as engagement metrics.

**Source:** [S3] — Grade A
**Versions affected:** All

---

### G7: Data Entry Campaigns — Passwords Not Collected, But Legal Review Still Required

**What you'd expect:** Because no passwords are stored, there are no privacy or legal concerns with Data Entry phishing campaigns.

**What actually happens:** Proofpoint does not collect or store passwords entered on simulated credential pages. However, running a credential harvesting simulation may still have implications under GDPR, employment law, or union agreements in some jurisdictions. The simulation itself — not the data collection — may require prior notification to employees or union consultation.

**Workaround:** Consult your legal/HR team before running Data Entry campaigns, especially for organizations with EU employees, unionized workforces, or strict employment contracts. Drive-by campaigns (no credential prompt) carry lower legal risk as a starting point.

**Source:** [S3] — Grade A (documents that passwords are not collected); legal risk implication is ASSUMPTION [Grade U]
**Versions affected:** All

---

### G8: Default Data Collection Period (7 Days) Is Often Too Short

**What you'd expect:** 7 days captures most user interactions with the phishing email.

**What actually happens:** Users who are on vacation, out sick, or simply slow to check email will open/click phishing emails after 7 days. These late interactions are silently dropped after the data collection period closes — they do not appear in reports and cannot be recovered.

**Impact:** Phishing failure rates are systematically underreported with a 7-day collection window, making programs appear more effective than they are.

**Workaround:** Set Data Collection Period to 14–30 days as a default practice. For compliance-tracked campaigns, use indefinite and manually close collection after verifying all users have been captured.

**Source:** [S3 — documents default and customization; underreporting implication is inferred from behavior description] — Grade A (mechanism), Grade E (impact implication)
**Versions affected:** All

---

### G9: Follow-Up Campaign Cannot Use an In-Progress Campaign as Source

**What you'd expect:** You could target users who are actively clicking in a live campaign.

**What actually happens:** Source Campaign must be in Completed or Archived state. The campaign must have finished its full lifecycle before it can feed a Follow-Up campaign.

**Workaround:** Plan the Follow-Up campaign as a distinct phase after the source campaign completes. Factor in the campaign delivery window plus the data collection period before scheduling the Follow-Up.

**Source:** [S3] — Grade A
**Versions affected:** All

---

### G10: Reported Phishing Criterion in Follow-Up Campaigns Requires PhishAlarm

**What you'd expect:** "Reported Phishing" appears as a criterion option and returns users who reported the email regardless of how they reported it.

**What actually happens:** The Reported Phishing criterion specifically captures reports made via the PhishAlarm add-in/button. Users who forward suspicious emails to a security alias or report by other means are NOT captured. Without PhishAlarm deployed to user email clients, this criterion returns zero users.

**Workaround:** Deploy PhishAlarm before running campaigns if "Reported Phishing" criterion is part of your Follow-Up strategy. Alternatively, only use Clicked/Submitted Data/Opened Attachment criteria, which work without PhishAlarm.

**Source:** [S3 — PhishAlarm referenced as PhishAlarm button; full configuration is behind auth wall per doc-corpus gap analysis] — Grade A (criterion referenced), Grade U (zero-user implication without PhishAlarm deployment is ASSUMPTION)
**Versions affected:** All

---

### G11: Template Distribution Logic When Multiple Templates Selected Is Undocumented

**What you'd expect:** Selecting multiple templates gives each user a randomly assigned template.

**What actually happens:** Unknown. S3 documents that multiple templates can be selected and each user receives one, but does not document the distribution algorithm (pure random, sequential, or AFR-weighted). This matters for campaigns targeting populations where even distribution across templates is important for meaningful comparative analysis.

**Workaround:** If controlled template distribution matters for your analysis, create separate single-template campaigns per user cohort and compare results independently.

**Source:** [S3 — field description only; distribution algorithm not documented] — Grade A (field documented), Grade E (distribution logic inferred)
**Versions affected:** Unknown

---

### G12: Simultaneous Delivery (Specific Schedule) Enables Recipient-to-Recipient Warning

**What you'd expect:** Sending all phishing emails at once is the most controlled testing approach.

**What actually happens:** When all recipients receive the phishing email within minutes of each other, recipients who recognize it as a simulation forward warnings to colleagues via Slack, Teams, or email — effectively nullifying the test for those colleagues.

**Workaround:** Use Random scheduling for any campaign exceeding approximately 25 users. Random scheduling spreads delivery across a window of hours/days, reducing the opportunity for peer-to-peer warnings.

**Source:** [S3 — Random scheduling option described with "spread delivery" rationale; warning propagation is inferred from common SAT practice] — Grade A (Random option documented), Grade E (peer-warning mechanism)
**Versions affected:** All

---

### G13: Adding Users to Existing Duration Assignment Restarts Their Individual Timer

**What you'd expect:** Users added to an existing Duration assignment are enrolled based on the assignment's original configuration date.

**What actually happens:** Each user added to a Duration assignment starts their Enrollment Delay timer from the date of their addition — not from when the assignment was created. This is the correct behavior for new-hire programs (each hire starts their own clock), but surprises admins who expect all users to be enrolled on the same timeline.

**Workaround:** For assignments where synchronized enrollment is required, use Scheduled type instead of Duration — Scheduled assigns all users to the same start/due date window.

**Source:** [S3] — Grade A
**Versions affected:** All

---

### G14: Primary Source (S3) Is 6 Years Old — UI and Features May Have Changed

**What you'd expect:** The documented screens, field names, and options accurately reflect the current Proofpoint Essentials SAT UI.

**What actually happens:** S3 is dated April 2020. Proofpoint SAT has received significant platform updates since then, including AIDA (AI-Driven Awareness) integration, expanded phishing template libraries, updated reporting dashboards, and potentially new campaign types. Specific fields, navigation paths, or options documented in workflow.md and advanced.md may not match the current UI.

**Impact:** Any claim in this documentation set graded A [S3] should be treated as "authoritative as of April 2020." Current behavior should be verified against the current admin guide at help.proofpoint.com (requires authentication).

**Workaround:** Cross-reference any critical configuration decisions against the current Proofpoint Essentials documentation (help.proofpoint.com). For new features not covered here (AIDA, expanded reporting), consult the current admin guide directly.

**Source:** [S3 — stale source warning documented in doc-corpus.md] — Grade A (document authenticity), coverage risk acknowledged
**Versions affected:** Post-April 2020 changes not reflected in this documentation

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| Post-April 2020 | AIDA (AI-Driven Awareness) integration referenced in current Proofpoint marketing | Potentially new configuration screens/options not documented in S3 |
| Post-April 2020 | Expanded phishing template library | AFR values and template categories may differ from S3 descriptions |
| April 2020 (S3) | Campaign types: Drive-by, Data Entry, Classic Attachment, Attachment, Follow-Up | Current UI may have additional campaign types not documented here |
| April 2020 (S3) | Assignment types: Scheduled, Duration | Current UI may have additional assignment types or sub-types |

**No video coverage exists for SAT** — video-intelligence.md explicitly confirms zero SAT-specific video findings. All findings in this document are derived from S3 only.

**No community/forum gotchas identified** — no Proofpoint community articles, third-party blog posts, or forum threads specific to SAT configuration were identified during research. If additional community sources are located, G11-G12 (inferred findings) should be cross-referenced against them.
