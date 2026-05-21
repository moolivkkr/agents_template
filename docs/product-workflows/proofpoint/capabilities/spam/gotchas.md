# Spam Policy Configuration — Gotchas & Known Limitations

## Summary

| # | Gotcha | Severity | Source Grade | Version-Specific |
|---|--------|----------|-------------|-----------------|
| G1 | Spam Settings and Filter Policies are separate UIs — changes in one do not affect the other | HIGH | B — Video 21 | All versions |
| G2 | "Update for all users" overwrites per-user spam thresholds immediately with no undo | HIGH | A — S1 | All versions |
| G3 | Propagation delay of 5–30 minutes after save causes false negatives during testing | MEDIUM | B — Video 21 | All versions |
| G4 | "Quarantine Bulk Email" can quarantine legitimately subscribed newsletters | MEDIUM | A — S1 | All versions |
| G5 | Per-user spam threshold overrides silently suppress organization spam policy for that user | MEDIUM | A — S1 | All versions |
| G6 | Spam trigger level numeric range is undocumented | LOW | A — S1 (gap) | All versions |
| G7 | PPS spam module tuning: aggressive single-pass threshold reduction is a documented common mistake | HIGH | D — community article | PPS/PoD only |

---

## Details

### G1: Spam Settings and Filter Policies are independent UIs

**What you'd expect:** Adjusting spam sensitivity in Spam Settings also affects spam-related filter rules.
**What actually happens:** Spam Settings (Security Settings > Email > Spam Settings) and Filter Policies (Security Settings > Email > Filter Policies) are completely independent. Changing the spam threshold does not alter any filter rules. Both must be configured separately when tuning spam behavior.
**Workaround:** When spam behavior needs tuning, check BOTH the Spam Settings page AND the Filter Policies list. Changes to one are not visible in the other.
**Source:** [B — Video 21, ~1:00] — confirmed in video walkthrough
**Versions affected:** All Proofpoint Essentials versions

---

### G2: "Update for all users" is a destructive one-time push with no undo

**What you'd expect:** A checkbox that toggles whether per-user overrides are allowed going forward.
**What actually happens:** "Update for all users" is a one-time push. When you save with this checked, all per-user spam threshold customizations are immediately overwritten. Users can re-customize their settings immediately after you save — the setting does not create a persistent lock.
**Workaround:** Before using "Update for all users," export or document any per-user configurations you want to preserve. There is no rollback.
**Source:** [A — S1]
**Versions affected:** All Proofpoint Essentials versions

---

### G3: Propagation delay causes false test negatives immediately after save

**What you'd expect:** Changes take effect as soon as you click Save.
**What actually happens:** Spam setting changes require 5–30 minutes to propagate through the Proofpoint mail processing infrastructure. Testing immediately after save will show the old behavior.
**Workaround:** Wait at least 5 minutes (ideally 30) before testing spam classification after a settings change.
**Source:** [B — Video 21, ~1:00; B — Video 2, ~3:00]
**Versions affected:** All Proofpoint Essentials versions

---

### G4: "Quarantine Bulk Email" will quarantine legitimately subscribed newsletters

**What you'd expect:** "Bulk Email" means unwanted promotional mail.
**What actually happens:** Proofpoint's bulk email classifier identifies mass-sent email by sending infrastructure patterns, not by whether the recipient subscribed. Legitimate newsletters, service notifications, and subscription digests from bulk sending services (Mailchimp, Constant Contact, etc.) will be quarantined.
**Workaround:** Before enabling "Quarantine Bulk Email," audit the organization's inbound mail for bulk-classified messages and create filter exceptions for trusted bulk senders.
**Source:** [A — S1] — behavior inferred from field description; classification mechanism confirmed at grade A
**Versions affected:** All Proofpoint Essentials versions

---

### G5: Per-user spam threshold overrides silently suppress organization policy for individual users

**What you'd expect:** Organization spam settings apply to all users.
**What actually happens:** Any user who has customized their personal spam threshold has that setting take precedence over the organization default. This means a user can effectively disable aggressive spam filtering for themselves without admin awareness.
**Workaround:** Periodically audit per-user spam settings via Users & Groups. When a user reports missing spam filtering, check their personal settings first.
**Source:** [A — S1]
**Versions affected:** All Proofpoint Essentials versions

---

### G6: Spam trigger level numeric range is not documented

**What you'd expect:** Knowing the valid range (e.g., 1–100) to understand what "lower" and "higher" thresholds mean in absolute terms.
**What actually happens:** The Proofpoint Essentials Admin Guide [S1] describes the field as a sliding threshold but does not publish the numeric range or default value.
**Workaround:** Use the visual slider position as a relative guide. Community sources suggest starting at the default and making incremental adjustments while monitoring quarantine volume.
**Source:** Gap identified in [A — S1]
**Versions affected:** All (gap may be resolved in current UI tooltip — not accessible without authentication)

---

### G7: PPS spam module — aggressive single-pass tuning is a documented common mistake

**What you'd expect:** Setting the spam threshold to maximum aggressiveness catches all spam immediately.
**What actually happens:** Aggressive single-pass threshold reduction in the PPS spam module produces high false positive rates, especially in the first hours after the change. The spam classifier scoring is sensitive to incremental adjustments.
**Workaround:** Start with the highest-confidence rules (score 100) and monitor false positives for 24–48 hours before further tightening. Incrementally reduce threshold in small steps with monitoring between each change.
**Source:** [D — community article, proofpoint.my.site.com — Best Practices for Tuning Spam Module Rules]
**Versions affected:** PPS/PoD deployments only

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| Essentials (2023 UI refresh) | Navigation updated to Security Settings > Email > Spam Settings | Videos pre-2023 may show slightly different nav path [B — video-intelligence.md, tribal knowledge] |
| PPS (all versions) | Spam module configuration in separate admin console from Essentials | PPS-specific tuning (items 3.8, 3.9) requires PPS admin console access; not available in Essentials [B — S2] |

---

## No Additional Gotchas Identified

Checked sources: [S1] admin guide, [S2] training material, [S19] community quarantine guide, [V21] official training video, [V2] official training video, community articles (proofpoint.my.site.com). The spam configuration surface in Essentials is small (6 fields) which limits the gotcha surface area. PPS-specific gotchas are underrepresented due to LOW source coverage.
