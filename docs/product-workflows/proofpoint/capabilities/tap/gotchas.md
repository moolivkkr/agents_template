# Targeted Attack Protection (TAP) — Gotchas and Known Limitations

---

## Summary

| # | Gotcha | Severity | Source Grade | Version-Specific |
|---|--------|----------|-------------|-----------------|
| G1 | URL Defense is disabled by default after TAP provisioning — must be explicitly enabled | HIGH | B — vendor training video | Not version-specific; applies to all TAP deployments |
| G2 | TAP sender exemption and Email Protection safe-sender list are independent — adding to one does NOT update the other | HIGH | C — community KB | All versions |
| G3 | TAP VAP list for URL Isolation does not auto-sync from TAP Dashboard — manual re-import required after every threat review | HIGH | C — confirmed in official docs (word "import") | All versions; predates 2019 rebranding |
| G4 | TAP sender exemption suppresses alerts only — scanning (URL rewriting + attachment sandboxing) continues regardless | MEDIUM | C — community KB | All versions |
| G5 | Contradiction: official docs imply URL Defense auto-activates; vendor tutorial video shows manual enable step | MEDIUM | B contradicted by B | Likely version-dependent — treat video as current behavior |
| G6 | TAP module configuration screens are almost entirely behind the Proofpoint authentication wall — no public field documentation | MEDIUM | E — corpus gap analysis | All versions |
| G7 | TAP URL Isolation for VAPs requires Proofpoint Isolation as a separately licensed product — TAP license alone is insufficient | HIGH | B — Isolation data sheet | All versions |
| G8 | New VAPs identified after last import cycle receive only standard URL Defense until the list is manually re-imported | HIGH | C — Video 17 ~1:30 | All versions |
| G9 | Hold-and-release Attachment Defense mode increases email delivery latency — operational teams may object | MEDIUM | E — inferred from delivery model | All versions |
| G10 | Group must exist in PPS/PoD directory before per-group TAP enablement — no inline group creation on that screen | MEDIUM | C — community KB | All versions |

---

## Details

### G1: URL Defense disabled by default after provisioning

**What you'd expect:** TAP URL Defense activates automatically when the TAP module is licensed and provisioned — some official documentation phrasing implies this ("you do not need to do anything to activate it once enabled").

**What actually happens:** URL Defense is disabled at Administration > Account Management > Features after provisioning. An explicit enable step is required. If this step is skipped, no URL rewriting occurs — the feature is silently inactive and messages receive no TAP URL protection.

**Workaround:** As the first post-licensing configuration step, navigate to Administration > Account Management > Features and explicitly enable URL Defense. Do not proceed with any other TAP configuration until this toggle is confirmed saved as Enabled.

**Source:** Video 5 ~0:30 [B — vendor training video]

**Note on doc contradiction:** Official documentation ("you do not need to do anything to activate it once enabled") conflicts with the video. The video is more procedurally specific and likely reflects the current deployment behavior. The phrase "once enabled" in the docs may refer to the license-level enable, not the console toggle. Follow the video.

**Versions affected:** All TAP deployments observed in training video corpus (2018–current)

---

### G2: TAP exemption list and Email Protection safe-sender list are independent

**What you'd expect:** Adding a sender to the Email Protection safe-sender list (Company Settings > Filters or equivalent) would also suppress TAP alerts for that sender.

**What actually happens:** The TAP Dashboard exemption list and the Email Protection safe-sender/allow-list are entirely separate configurations in separate UIs. Adding a sender to one has NO effect on the other. An admin who whitelists a trusted vendor in Email Protection will still receive TAP Dashboard alerts for every email from that vendor.

**Workaround:** When you want to trust a sender across both systems, you must add them in two places:
1. Email Protection safe-sender list (to bypass spam/filter actions)
2. TAP Dashboard exemption list (to suppress TAP alerts)

**Source:** Proofpoint Community KB [C, S21] + video intelligence tribal knowledge

**Versions affected:** All versions

---

### G3: VAP list for URL Isolation requires manual re-import — no automatic sync

**What you'd expect:** The VAP (Very Attacked People) list maintained in the TAP Dashboard automatically propagates to the URL Isolation policy so that newly identified high-risk users receive isolation-enhanced protection immediately.

**What actually happens:** The VAP list must be manually exported from the TAP Dashboard and manually imported into the Isolation Console's URL Isolation policy. Proofpoint's own documentation uses the word "import" (not "sync"), confirming the manual nature of this operation. There is no API or webhook to automate the sync.

**Workaround:** After every TAP threat summary review where the VAP roster changes:
1. Export VAP list from TAP Dashboard
2. Navigate to Isolation Console > Policies > URL Isolation
3. Import the updated list

Recommend setting a calendar reminder tied to your TAP threat review cycle (weekly or monthly). New VAPs not yet in the Isolation policy receive standard URL Defense protection only — not browser isolation.

**Source:** Proofpoint Isolation documentation + Video 17 ~1:30 [C, confirmed in official docs]

**Versions affected:** All versions; behavior predates the 2022 rebranding to "Proofpoint Isolation"

---

### G4: TAP sender exemption suppresses alerts only — scanning continues

**What you'd expect:** Exempting a sender from TAP means their emails bypass URL Defense and Attachment Defense scanning.

**What actually happens:** TAP exemptions suppress the generation of TAP Dashboard ALERTS for emails from the exempted sender. URL Defense URL rewriting and Attachment Defense sandboxing continue to run on those emails. The sender's links are still rewritten to `urldefense.com` format in the delivered email.

**Impact:** If you are trying to exempt a trusted security-testing vendor whose emails contain intentionally suspicious-looking URLs (red team exercises, phishing simulations), the TAP exemption will suppress the dashboard alerts but will not prevent URL rewriting or attachment analysis from occurring. The simulated phishing URLs will still be rewritten.

**Workaround:** For phishing simulation vendors, the standard approach is to add their sending IP addresses or domains to the Email Protection safe-sender / allow-list at the email filter level, bypassing TAP URL Defense entirely. Consult your Proofpoint support account team for the recommended bypass approach for phishing simulation vendors. Source: [E — inferred from architecture; not directly documented]

**Source:** Community KB [C, S21]

**Versions affected:** All versions

---

### G5: Documentation contradiction — URL Defense activation method unclear

**What you'd expect:** Consistent guidance on how URL Defense activates after licensing.

**What actually happens:** Official documentation states "you do not need to do anything to activate it [URL Defense] (once enabled)" — suggesting automatic activation. Vendor training video (Video 5, ~0:30) shows an explicit UI enable step at Administration > Account Management > Features.

**Workaround:** Always perform the explicit enable step at Administration > Account Management > Features. Do not assume URL Defense is active just because TAP is licensed. Verify by sending a test email and checking whether inbound links are rewritten to `urldefense.com` format.

**Source:** Official docs vs. Video 5 ~0:30 [B vs B — genuine contradiction]

**Versions affected:** Contradiction likely reflects different product versions or deployment types (PPS on-premises vs PoD cloud). The video (2018 PPS tutorial) shows manual enable. If on PoD/cloud, automatic activation may be the correct behavior. Confirm with Proofpoint support for your deployment type.

---

### G6: TAP configuration fields behind authentication wall — incomplete field documentation

**What you'd expect:** Complete field reference for TAP Settings screens (URL Defense, Attachment Defense, per-group configuration).

**What actually happens:** The TAP administration screens within PPS/PoD are accessible only to authenticated administrators, and Proofpoint does not publish a public admin guide with screen-level field documentation for TAP. Training materials [S2] describe TAP capabilities at an outline level but do not enumerate field names, options, or defaults for the TAP Settings screens.

**Impact:** This reference document contains INCOMPLETE markers on TAP Settings screen fields. Admins must refer to the in-product help documentation accessible from within the authenticated console, or contact Proofpoint support for field-level guidance.

**Source:** Corpus coverage analysis [E — gap identified from documentation research]

**Versions affected:** All versions — no public TAP admin guide found in research corpus

---

### G7: URL Isolation for VIPs/VAPs requires Proofpoint Isolation license (separate product)

**What you'd expect:** URL Isolation for VIPs/VAPs is included with the TAP license.

**What actually happens:** URL Isolation requires Proofpoint Isolation, which is a separate licensed product with its own admin console, browsing policies, and configuration requirements. TAP provides the user list (VAPs) and the URL rewrite infrastructure; Isolation provides the remote browser sandbox that renders web content.

**Impact:** Organizations that have TAP but not Proofpoint Isolation cannot configure URL Isolation for VIPs/VAPs. The sub-capability 7.6 in the TAP taxonomy requires a second product license.

**Workaround:** If Isolation is not licensed, VIPs and VAPs still receive standard URL Defense (click-time inspection, block on malicious verdict). The difference is that URL Isolation routes the browsing session through a remote sandbox, so even zero-day malicious sites cannot harm the user's local browser.

**Source:** Proofpoint Isolation Data Sheet [B, S15]

**Versions affected:** All versions

---

### G8: New VAPs unprotected by Isolation until manual re-import

**What you'd expect:** When TAP identifies a new VAP (a user who has been heavily targeted in recent attacks), that user automatically receives isolation-enhanced URL protection.

**What actually happens:** The TAP Dashboard updates its VAP list dynamically based on attack patterns. But the Isolation policy's VIP/VAP assignment is a static import. Until an admin manually re-exports the VAP list from TAP and re-imports it into the Isolation Console, newly identified VAPs receive only standard URL Defense — not browser isolation.

**Impact:** During the gap between TAP VAP identification and the next manual import cycle, high-risk users receive reduced protection. If the VAP list is reviewed and updated monthly, newly targeted users could go 30 days with suboptimal protection.

**Workaround:** Shorten the re-import cycle. Review TAP threat summaries weekly and re-import the VAP list immediately when the roster changes. Consider supplementing with a manually maintained VIP list (executives, finance team, legal) that does not change as frequently and provides a stable baseline of isolation protection.

**Source:** Video 17 ~1:30 [C — demo observation, confirmed by official doc word "import"]

**Versions affected:** All versions

---

### G9: Hold-and-release Attachment Defense adds delivery latency

**What you'd expect:** Email is delivered to recipients with no noticeable delay.

**What actually happens:** When Attachment Defense is configured in hold-and-release mode, messages containing attachments that require sandbox analysis are held in the Proofpoint MTA queue until the sandbox returns a verdict. The analysis duration is not published in accessible documentation.

**Impact:** Operational teams that rely on time-sensitive email (trading confirmations, legal deadline notices, invoice approvals) may experience complaint-generating delivery delays.

**Workaround:** Use deliver-and-retroactively-quarantine mode for latency-sensitive teams while maintaining hold-and-release for executive or finance groups. This requires per-group Attachment Defense mode configuration, which may not be possible in all TAP deployments (field options behind auth wall). Alternatively, configure pre-delivery exemptions for trusted domains that regularly send attachment-heavy operational mail.

**Source:** Inferred from hold-and-release delivery model [E — architectural inference]

**Versions affected:** All versions

---

### G10: Per-group TAP enablement requires pre-existing user groups

**What you'd expect:** When configuring TAP for a specific user group, you can define the group membership inline from the TAP per-group configuration screen.

**What actually happens:** The group selection field in TAP per-group enablement is a dropdown that lists groups already defined in the PPS/PoD user directory. You cannot create a new group from this screen. If the target group does not yet exist, the TAP configuration cannot proceed.

**Workaround:** Create user groups in the PPS/PoD user directory (via LDAP sync or manual group management) before beginning per-group TAP configuration. Plan user groupings (IT Pilot, Executives, Finance, Operations) and create them as a prerequisite step.

**Source:** Community KB [C, S22]

**Versions affected:** All versions

---

## Version-Specific Notes

| Version / Period | Change | Impact |
|---------|--------|--------|
| 2019 | TAP Browser Isolation product demo (Video 17) — TAP URL Isolation for VAPs was an early feature of what became Proofpoint Isolation | At this point TAP and Isolation were more tightly coupled; by 2022 Isolation became a more separate product (Proofpoint Isolation, Video 18). VIP/VAP import workflow may have moved from TAP Dashboard to Isolation Console during this transition. | Import path may vary depending on deployment vintage — consult Proofpoint support for your version. |
| 2022 | Browser Isolation rebranded to "Proofpoint Isolation" (Video 18) | Product name changed; admin console path for URL Isolation policy may differ from earlier documentation references to "TAP Browser Isolation" | Use "Proofpoint Isolation" when contacting support or searching help docs |
| PPS 8.22.x | Unified DLP feature introduced — impact on TAP URL Defense in DLP-detected flows is not documented in accessible sources | Possible interaction between Unified DLP and TAP scanning pipeline not mapped | INCOMPLETE — requires authenticated documentation |

---

## No Gotchas Identified — Checked Sources

All major gotchas in this document were found. The following areas were checked but yielded no additional gotchas beyond what is documented:

- Proofpoint Community articles [S21, S22]
- Vendor training videos [Video 5, 6, 15, 17]
- Proofpoint Isolation data sheet [S15]
- Training datasheet [S2]

Additional community-sourced gotchas may exist but are not accessible without authentication to the Proofpoint Community portal (proofpoint.my.site.com). This capability may have undocumented edge cases in areas behind the authentication wall (specifically: TAP Settings screen field behavior, Attachment Defense sandbox timeout handling, and TAP Dashboard alert threshold configuration).
