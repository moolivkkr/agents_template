# Quarantine Management — Gotchas & Known Limitations

## Summary

| # | Gotcha | Severity | Source Grade | Version-Specific |
|---|--------|----------|-------------|-----------------|
| G1 | Messages are permanently deleted when retention period expires — no warning, no recovery | HIGH | A — S1 | All versions |
| G2 | Phishing, virus, and spoofed categories are hard admin-only — cannot be changed | MEDIUM | D — S19 | All versions |
| G3 | Excluding Adult category from digest does not quarantine adult content less aggressively — only hides it from notifications | MEDIUM | D — S19 | All versions |
| G4 | Policy-quarantined messages visible in digest if Policy category is not excluded — users can see DLP-flagged subjects | HIGH | D — S19 | Essentials |
| G5 | PPS quarantine move API cannot move messages across module types | MEDIUM | C — S16 | PPS/PoD only |
| G6 | Quarantine and Archive are separate systems — quarantined messages are NOT archived | HIGH | A — S1, A — S27 | All versions |
| G7 | Digest category exclusions and release permissions are separate controls — excluding a category from digest does not make it admin-only | MEDIUM | D — S19 | Essentials |

---

## Details

### G1: Messages deleted at retention expiry with no warning and no recovery

**What you'd expect:** A notification or grace period before messages are permanently deleted.
**What actually happens:** When the quarantine retention period expires (default 30 days), messages are automatically and permanently deleted. There is no pre-deletion warning, no notification to users, and no recovery path.
**Workaround:** Set retention to a longer period (e.g., 60 days) in environments where users commonly report missing mail weeks after the fact. Communicate to end users that quarantined messages older than 30 days cannot be recovered.
**Source:** [A — S1] — retention period documentation
**Versions affected:** All versions

---

### G2: Phishing, virus, and spoofed categories are permanently admin-only — not configurable

**What you'd expect:** The same per-category release permission toggle that exists for spam to also exist for phishing, virus, and spoofed categories.
**What actually happens:** Phishing, virus, and spoofed email quarantine categories are hard-coded as admin-only. No UI toggle exists to enable user self-release for these categories. End users cannot see these categories in their quarantine digest by default.
**Workaround:** There is no workaround for this restriction — it is intentional security design. Administrators must handle release requests for these categories manually.
**Source:** [D — S19]
**Versions affected:** All versions

---

### G3: Excluding Adult category from digest does not change detection aggressiveness

**What you'd expect:** Excluding Adult from the digest reduces how much adult content is quarantined.
**What actually happens:** Digest category exclusions only control whether subjects from that quarantine category appear in the notification email. Messages are still quarantined at the same rate; users just do not see them listed in the digest. They remain in the quarantine portal.
**Workaround:** Use digest exclusions for the Adult category to prevent adult content subjects from appearing in the inbox notification. Separately, use spam threshold and filter settings to control the detection rate.
**Source:** [D — S19]
**Versions affected:** All versions

---

### G4: DLP-flagged message subjects appear in user quarantine digest if Policy category is not excluded or made admin-only

**What you'd expect:** DLP and compliance-quarantined messages are hidden from the user who sent them.
**What actually happens:** If the Policy quarantine category is user-visible in the digest, end users can see the subject lines of their compliance-quarantined outbound messages. In some configurations they can also self-release those messages, potentially defeating DLP controls.
**Workaround:** For any organization using DLP quarantine, configure the Policy quarantine category as admin-only AND exclude it from user-facing digests. This requires coordination between quarantine category settings and filter policy configuration.
**Source:** [D — S19] — category behavior documentation
**Versions affected:** Essentials (Quarantine Console)

---

### G5: PPS quarantine API move command is restricted to same-module-type folders

**What you'd expect:** The `proofpoint-pps-quarantine-message-move` API command can move a message to any quarantine folder.
**What actually happens:** The move command can only transfer messages between folders of the same module type. A message quarantined by the spam module cannot be moved to a DLP module folder via API.
**Workaround:** If cross-module reassignment is needed, use delete and resubmit rather than move. Resubmit (`proofpoint-pps-quarantine-message-resubmit`) reprocesses the message through all filter modules, potentially landing it in a different quarantine folder based on filtering results.
**Source:** [C — S16] — XSOAR integration documentation
**Versions affected:** PPS/PoD only

---

### G6: Quarantine and Email Archive are completely separate systems

**What you'd expect:** Messages held in quarantine are also preserved in the email archive for compliance.
**What actually happens:** Quarantine and Archive are independent systems with separate retention periods and storage. A message quarantined for 30 days is automatically deleted at retention expiry regardless of archive configuration. Messages must be explicitly archived via Archive policy to appear in the archive.
**Workaround:** If compliance requires that quarantined messages be archived (for legal hold or e-discovery), verify that the Archive configuration captures inbound mail independently of quarantine disposition. Do not assume quarantine serves as an archive.
**Source:** [A — S1] quarantine retention; [A — S27] archive retention — cross-system separation inferred
**Versions affected:** All versions

---

### G7: Digest exclusions and release permissions are independent controls that must both be set for admin-only enforcement

**What you'd expect:** Excluding a category from the digest also makes it admin-only release.
**What actually happens:** Digest exclusions and release permission settings are two independent toggles. Excluding a category from the digest prevents users from seeing it in notification emails, but if the category's release permission is set to "user-releasable," users can still navigate to the quarantine portal and release those messages directly.
**Workaround:** To make a quarantine category truly admin-controlled, set BOTH: (1) exclude from digest, AND (2) set release permission to admin-only. Setting only one is insufficient.
**Source:** [D — S19] — category and digest configuration documented separately
**Versions affected:** All versions

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| Essentials (2023 UI refresh) | Navigation may have moved; pre-2023 videos show "Company Settings > Quarantine" path | Verify current navigation path in admin console [B — video-intelligence.md] |
| PPS (all versions) | Quarantine folder model differs from Essentials category model | PPS uses folder-based quarantine; Essentials uses category-based — concepts are analogous but UIs are completely different |
