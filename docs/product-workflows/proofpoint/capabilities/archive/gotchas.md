# Archive & Retention Policies — Gotchas & Known Limitations

## Summary

| # | Gotcha | Severity | Source Grade | Version-Specific |
|---|--------|----------|-------------|-----------------|
| G1 | Default 12-month retention is insufficient for most regulated industries | HIGH | A — S27 | All versions |
| G2 | Legal hold is company-wide only — no per-user or per-custodian hold documented | HIGH | A — S27 (gap) | Essentials |
| G3 | Archive and quarantine are separate systems — quarantined messages are not automatically archived | HIGH | A — S1, A — S27 | All versions |
| G4 | Messages that passed retention date during a legal hold may become immediately eligible for deletion when hold is deactivated | HIGH | U — ASSUMPTION (behavior not documented) | All versions |
| G5 | Maximum retention period is 10 years — cannot be exceeded | MEDIUM | A — S27 | All versions |
| G6 | Archive search policy configuration is undocumented in accessible sources | MEDIUM | A — S27 (gap) | All versions |
| G7 | Retention period set after archive accumulates messages does not retroactively protect messages that have already aged past the new retention period | HIGH | U — ASSUMPTION (standard archive behavior; not explicitly documented for Proofpoint) | All versions |

---

## Details

### G1: Default 12-month retention is insufficient for most regulated industries

**What you'd expect:** A default retention period suitable for compliance.
**What actually happens:** Proofpoint Essentials Archive defaults to 12 months (1 year). After 1 year, messages are eligible for deletion. Most regulated industries require 3–7 years of email retention. Organizations that accept the default and later face a compliance audit or litigation may find that required messages have been deleted.
**Workaround:** Change the retention period immediately after archive provisioning, before any messages accumulate. Use the regulatory reference table in [workflow.md](workflow.md) Step 2 to determine the correct retention period for your industry.
**Source:** [A — S27] — 12-month default and 10-year maximum documented
**Versions affected:** All Proofpoint Essentials Archive versions

---

### G2: Legal hold is company-wide only — no per-user or per-custodian hold documented

**What you'd expect:** Ability to place a legal hold on specific users (custodians) for targeted e-discovery.
**What actually happens:** The accessible documentation for Proofpoint Essentials Archive describes only a company-wide legal hold toggle. Per-user or per-custodian legal hold (standard in enterprise e-discovery systems) is not documented in accessible grade-A sources. Activating the company-wide hold to preserve one custodian's messages stops ALL retention deletions for the entire organization.
**Workaround:** If per-custodian hold is legally required, confirm with Proofpoint whether Essentials Archive supports this feature (may be in the authenticated admin guide). As a temporary measure, activate company-wide hold when a specific custodian's messages need to be preserved. This is storage-intensive and should be managed carefully.
**Source:** [A — S27] — only company-wide hold described; per-user hold not mentioned (absence of evidence)
**Versions affected:** Essentials (Enterprise/PoD may support per-custodian hold — INCOMPLETE)

---

### G3: Archive and quarantine are completely separate systems

**What you'd expect:** Messages quarantined for policy violations are also captured in the compliance archive.
**What actually happens:** Quarantine and Archive are independent systems. The quarantine has its own 30-day retention period; the archive has a separately configured retention. A spam-classified message quarantined for 30 days and then deleted is NOT in the archive unless the archive independently captured it on delivery. The same email message being in quarantine does not place it in the archive.
**Workaround:** If compliance requires that all messages (including those that trigger spam or DLP policies) be archived, verify the archive is configured to capture messages at the MTA level (before quarantine disposition), not just delivered messages. Archive capture scope configuration is INCOMPLETE in accessible sources.
**Source:** [A — S1] (quarantine retention 30 days documented separately from archive); [A — S27] (archive retention documented separately)
**Versions affected:** All versions

---

### G4: Deactivating legal hold may cause immediate deletion of messages that aged past retention during the hold

**What you'd expect:** When legal hold is deactivated, the system resumes normal deletion for new messages only.
**What actually happens:** The behavior when legal hold is deactivated and some archived messages have already passed their retention date during the hold period is NOT documented in accessible sources. Based on standard archive system behavior, those messages may become immediately eligible for deletion upon hold deactivation.
**Workaround:** Before deactivating a legal hold, consult with legal counsel about which messages need to be preserved and consider exporting or separately preserving those messages. Do not deactivate legal hold without understanding which messages may become deletion-eligible.
**Source:** [U — ASSUMPTION — standard archive system behavior; exact Proofpoint behavior not documented in accessible sources. Mark as HIGH severity because the risk of unexpected deletion is significant.]
**Versions affected:** All versions

---

### G5: Maximum retention period is 10 years

**What you'd expect:** Ability to set unlimited retention.
**What actually happens:** Proofpoint Essentials Archive maximum retention period is 10 years. Organizations requiring longer retention (rare, but exists in some government/legal sectors) cannot configure longer periods without using an alternative archive system.
**Workaround:** For organizations requiring >10 year retention, evaluate Proofpoint Enterprise Archive or a third-party archive solution. Contact Proofpoint for options.
**Source:** [A — S27]
**Versions affected:** All Proofpoint Essentials Archive versions

---

### G6: Archive search policy configuration is undocumented in accessible sources

**What you'd expect:** Documented workflow for configuring who can search the archive and what results they can see.
**What actually happens:** Archive search exists as a feature in Proofpoint Essentials Archive, but the configuration of search policies, search permissions, and result visibility is not documented in accessible grade-A sources. [S1] references archive search; [S27] covers only retention and legal hold.
**Workaround:** Consult the full Essentials Archive admin guide at help.proofpoint.com (requires authentication) or contact Proofpoint support for archive search policy configuration guidance.
**Source:** Gap identified from [A — S27] (S27 does not cover search); [A — S1] (references search feature only)
**Versions affected:** All versions

---

### G7: Increasing retention period after archive accumulates messages does not retroactively save already-deleted messages

**What you'd expect:** Changing retention to 7 years will preserve 7 years of email going forward AND retroactively.
**What actually happens:** If your archive was running with 12-month retention for 6 months and you then increase to 7 years, only messages from that point forward are protected by the 7-year window. Messages already deleted under the 12-month policy (i.e., messages older than 12 months at the time of deletion) are gone permanently. The new retention period applies from the change date forward.
**Workaround:** Configure the correct retention period immediately after archive provisioning, before any messages are eligible for deletion under an incorrect period.
**Source:** [U — ASSUMPTION — standard archive behavior; Proofpoint does not document retroactivity behavior in accessible sources. Marked HIGH because the data loss consequence is significant.]
**Versions affected:** All versions

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| Essentials Archive (all accessible versions) | S27 content is behind authentication — full feature set may be larger than documented | Archive capabilities beyond retention/legal hold are not mappable from accessible sources |

---

## No Additional Gotchas Identified

Checked sources: [S27] archive retention documentation, [S1] Essentials admin guide, [S19] community quarantine guide. The archive configuration surface is small (2-3 fields), but the consequences of misconfiguration are disproportionately large (compliance failure, data loss). All identified high-severity risks have been documented above.
