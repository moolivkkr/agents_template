# PPS/PoD Rule Creation and Email Firewall — Gotchas and Known Limitations

> Product: Proofpoint Protection Server (PPS) / Proofpoint on Demand (PoD) 8.22.x
> Evidence grades: B (vendor training video), C (vendor KB/XSOAR docs), D (community)
> Note: No Grade A source (authenticated admin guide) was accessible for PPS field-level detail.

---

## Summary

| # | Gotcha | Severity | Source Grade | Version-Specific |
|---|--------|----------|-------------|-----------------|
| G1 | Omitting Route condition applies rule to ALL routes including outbound relay | HIGH | B | No |
| G2 | New rules default to Off (disabled); must be explicitly enabled | HIGH | B | No |
| G3 | Rule execution order = visual position in list, NOT Rule ID | HIGH | B | No |
| G4 | Anti-spoof rule ships disabled by default — not active out of the box | HIGH | D | No |
| G5 | Rule changes require 5–30 minutes propagation before taking effect | MEDIUM | B | No |
| G6 | Quarantine folders must be pre-created; referencing a nonexistent folder causes silent failure | HIGH | B, C | No |
| G7 | Messages can only be moved between quarantine folders of the SAME module type | MEDIUM | C | No |
| G8 | Policy Route menu is PPS-specific; not present in Proofpoint Essentials | HIGH | B | No — product-level distinction |
| G9 | Spam Settings and Email Firewall rules are independent; tuning one does not affect the other | MEDIUM | B | No |
| G10 | Module Precedence controls which module fires first; misconfiguring can cause DLP bypass | HIGH | B | No |
| G11 | Spam module best practice: tune incrementally from score 100 down; aggressive bulk tuning causes false positive surge | MEDIUM | D | No |
| G12 | PPS on-prem and PoD cloud console may have different navigation paths for policy routes | MEDIUM | B | No — platform distinction |
| G13 | PPS admin guide is behind authentication; screen-level field enumeration incomplete for this documentation | LOW (documentation gap, not runtime issue) | B | No |

---

## Details

### G1: Omitting Route Condition Applies Rule to ALL Routes
**Severity:** HIGH

**What you'd expect:** Creating a rule targeting inbound mail without specifying a Route condition would default to inbound mail only, since that is the typical intent.

**What actually happens:** The rule applies to ALL policy routes including outbound relay traffic. An inbound blocking rule will also fire on outbound messages, potentially blocking or quarantining legitimate outbound mail.

**Workaround:** Always add a Route condition as the first condition on any inbound-specific rule. Set Condition Type = Route, Value = `default_inbound` (or your custom inbound route name). Verify route names in System > Policy Route before creating rules.

**Source:** C [V2 ~2:00] — vendor training video demonstration; B [S2] training documentation
**Versions affected:** All PPS/PoD versions

---

### G2: New Rules Default to Off (Disabled)
**Severity:** HIGH

**What you'd expect:** Saving a completed rule activates it immediately.

**What actually happens:** Every newly created rule defaults to Enable = Off. The rule exists in the system but evaluates no mail until explicitly set to On.

**Workaround:** After creation and execution order verification, go to Email Firewall > Rules, find the rule, and set Enable = On. This is a two-step process: create the rule, then enable it.

**Source:** C [V2 ~0:30] — vendor training video
**Versions affected:** All PPS/PoD versions

---

### G3: Rule Execution Order Is Visual Position, Not Rule ID
**Severity:** HIGH

**What you'd expect:** Rules with lower Rule IDs or earlier creation dates fire before rules with higher IDs.

**What actually happens:** Execution order is determined by the visual top-to-bottom position of rules in the Email Firewall > Rules list. Rule IDs are identifiers only and do not determine firing order. Dragging a rule in the list immediately changes its execution position.

**Workaround:** After creating rules, verify their position in the visual list. When creating multiple related rules, drag them into the correct order (most specific allow-rules above general blocks; DLP/security rules before allow-list releases). Do not rely on Rule ID for order assumptions.

**Source:** C [V9 ~0:30] — vendor training video on filter ordering
**Versions affected:** All PPS/PoD versions

---

### G4: Anti-Spoof Rule Ships Disabled
**Severity:** HIGH

**What you'd expect:** The anti-spoof rule that ships with PPS is active by default as a security baseline.

**What actually happens:** The anti-spoof firewall rule is pre-installed but ships with Enable = Off. In default PPS deployments, no anti-spoofing protection is active unless the rule is explicitly enabled.

**Workaround:** Navigate to Email Firewall > Rules, locate the anti-spoof rule, and set Enable = On. This should be a first-day configuration step after any PPS deployment.

**Source:** D [community article — proofpoint.my.site.com] — community-sourced; not corroborated in video evidence
**Versions affected:** All PPS versions (community article; version range not specified)

---

### G5: Rule Changes Require 5–30 Minute Propagation
**Severity:** MEDIUM

**What you'd expect:** After saving a rule change or enabling a rule, the change takes effect immediately.

**What actually happens:** Rule changes propagate across the PPS/PoD infrastructure asynchronously. Testing immediately after a save will produce false negatives — the rule appears to not fire because it has not yet taken effect.

**Workaround:** After enabling a rule or making changes, wait at minimum 5 minutes before initial testing. For thorough validation, wait the full 30 minutes. Official documentation does not state a propagation time; this finding is video-only.

**Source:** C [V2 ~3:00] — vendor training video; C [V20 ~4:00] — Essentials video corroborates timing
**Versions affected:** All PPS/PoD versions

---

### G6: Quarantine Folder Must Pre-Exist Before Rule References It
**Severity:** HIGH

**What you'd expect:** Specifying a quarantine folder name in a rule disposition creates the folder if it does not exist.

**What actually happens:** The rule requires an already-created quarantine folder to reference. If the folder does not exist, the disposition behavior is undefined — likely a silent failure where quarantine does not occur (exact error behavior not documented in accessible sources).

**Workaround:** Create all quarantine folders in the quarantine management section BEFORE creating rules that reference them. Use the exact folder name from the quarantine management screen when setting the rule's Disposition > Quarantine Folder field.

**Source:** B [S2] training documentation; C [S16] XSOAR integration docs (quarantine operations reference existing folder names)
**Versions affected:** All PPS/PoD versions

---

### G7: Quarantine Messages Can Only Move Between Same-Module-Type Folders
**Severity:** MEDIUM

**What you'd expect:** Quarantined messages can be moved to any quarantine folder by admins or via API.

**What actually happens:** The `proofpoint-pps-quarantine-message-move` API command, and the UI equivalent, only permits moving messages between folders of the same module type. A message quarantined by the spam module cannot be moved to a content/DLP quarantine folder and vice versa.

**Workaround:** When designing the quarantine folder architecture, create separate folders per module type. Do not attempt to consolidate spam and content quarantine into a single folder for simplified review — the move restriction makes this operationally limiting.

**Source:** C [S16] — XSOAR integration reference documentation
**Versions affected:** PPS 8.16.2 / 8.14.2 (confirmed); assumed to apply to all versions

---

### G8: Policy Route Menu Is PPS-Specific (Not in Essentials)
**Severity:** HIGH

**What you'd expect:** Administrators familiar with Proofpoint Essentials expect to find routing and filter policy configuration in a single unified interface.

**What actually happens:** The System > Policy Route menu is only present in the PPS on-premises (and PoD cloud) admin console. Proofpoint Essentials does not have this menu. Essentials uses Filter Policies for content-based routing control; PPS/PoD uses Policy Routes + Email Firewall as separate systems. An admin trained on Essentials who is deployed on PPS will not find the routing configuration where they expect it.

**Workaround:** Use System (top navigation menu) > Policy Route in the PPS console. This top-level System menu is PPS/PoD-specific. Do not look for routing configuration under Email Firewall in PPS.

**Source:** B [S2] training doc; C [V3 ~0:45] — PPS-specific navigation confirmed
**Versions affected:** All versions — this is a product-level architecture difference

---

### G9: Spam Module and Email Firewall Rules Are Independent Systems
**Severity:** MEDIUM

**What you'd expect:** Adjusting spam aggressiveness in PPS affects overall spam handling including Email Firewall rule behavior.

**What actually happens:** The spam module (with its threshold slider and classifier configuration) and the Email Firewall rules module are separate systems in the PPS filtering pipeline. Changes to spam threshold do not affect Email Firewall rules, and vice versa. Both must be configured independently to achieve the intended spam policy.

**Workaround:** When tuning spam handling, configure BOTH the spam module threshold (via spam settings) AND review Email Firewall rules that may override spam module decisions (e.g., allow-list rules that release spam-scored messages). Review Module Precedence to understand which system acts first.

**Source:** B [S2] training; C [V21 ~1:00] video intelligence — confirmed as separate UIs
**Versions affected:** All PPS/PoD versions

---

### G10: Module Precedence Misconfiguration Can Cause DLP Bypass
**Severity:** HIGH

**What you'd expect:** All filtering modules (spam, virus, DLP, firewall) evaluate every message regardless of other modules' actions.

**What actually happens:** Module Precedence determines the order in which filtering modules process messages. If a Firewall module rule with a Deliver Now disposition fires BEFORE the DLP/content module evaluates the message, the DLP check may be bypassed. The exact bypass behavior depends on how Delivery Precedence interacts with Module Precedence — this interaction is INCOMPLETE in accessible sources.

**Workaround:** Review Module Precedence configuration before enabling DLP-adjacent Firewall rules. Place content analysis modules (DLP) earlier in the precedence order than firewall allow-list rules when DLP compliance is required. The exact configuration path for Module Precedence is INCOMPLETE in accessible sources — consult the authenticated PPS admin guide.

**Source:** B [S2] training documentation — Module Precedence and Delivery Precedence are distinct configurable concepts
**Versions affected:** All PPS/PoD versions — architecture-level behavior

---

### G11: Spam Module Tuning Must Be Done Incrementally
**Severity:** MEDIUM

**What you'd expect:** Setting the spam module to maximum aggressiveness provides the best spam blocking immediately.

**What actually happens:** Aggressive bulk tuning of spam module rules in a single pass produces a surge in false positives. The community-documented best practice (Proofpoint's own guidance) is to start with the highest-confidence rules (score = 100) and monitor false positives for 1–2 weeks before incrementally reducing the threshold.

**Workaround:** Start with score-100 rules active only. After 1–2 weeks monitoring, reduce threshold one increment at a time and monitor for false positive rate change at each step. Do not reduce from maximum to minimum in one change.

**Source:** D [community article — proofpoint.my.site.com — Best Practices for Tuning Spam Module Rules]
**Versions affected:** All versions (community article; version range not specified)

---

### G12: PPS On-Premises vs PoD Cloud Navigation Paths
**Severity:** MEDIUM

**What you'd expect:** Policy Route and Email Firewall configuration paths are identical in PPS on-premises and PoD cloud deployments.

**What actually happens:** The training videos (V3, V9) demonstrating System > Policy Route and Email Firewall configuration are recorded against the PPS on-premises admin interface. PoD is a cloud-hosted version of PPS, but the console navigation may differ. This documentation does not have confirmed evidence of the PoD-specific navigation paths.

**Workaround:** If deploying on PoD, verify navigation paths against the PoD-specific admin guide. Paths documented in this capability (e.g., System > Policy Route) are confirmed for PPS on-premises only.

**Source:** B [S2], C [V3 ~0:45] — on-premises confirmed; PoD navigation not explicitly shown in accessible videos
**Versions affected:** PoD cloud deployments — navigation path discrepancy risk

---

### G13: PPS Admin Guide Behind Authentication Wall (Documentation Gap)
**Severity:** LOW (documentation gap, not a runtime configuration issue)

**What you'd expect:** Complete field-level documentation is available for all PPS Email Firewall configuration screens.

**What actually happens:** The PPS/PoD admin guide requires authentication at help.proofpoint.com. As a result, exact field names, complete Condition Type enumerations, full Disposition Type option lists, PDR configuration fields, RV configuration fields, SMTP Rate Control parameters, End User Digest settings, and Dictionary management navigation paths are all INCOMPLETE in this documentation. These gaps are explicitly marked throughout workflow.md and advanced.md.

**Workaround:** Access the authenticated PPS admin guide via your Proofpoint support portal credentials. Cross-reference all INCOMPLETE sections against that guide. The following sections require verification: Condition Types beyond Route (2.3), Disposition Types beyond Deliver Now/Quarantine/Discard (2.5), PDR (2.9), RV (2.10), SMTP Rate Control (2.11), End User Digest (2.12), Dictionary navigation (2.7), Module Precedence navigation (2.8).

**Source:** Corpus coverage assessment — B [S2] is the highest-grade accessible source for PPS-specific fields
**Versions affected:** This documentation gap applies to all versions

---

## Version-Specific Notes

| Version | Change | Impact | Source |
|---------|--------|--------|--------|
| PPS 8.22.x | Unified DLP introduced — DLP module may have new configuration paths | Email Firewall + DLP module interaction for content-based firewall rules may differ from pre-8.22.x | E — inferred from search results; no official changelog accessible |
| Pre-2023 on-prem UI | Older PPS admin interface (shown in 2017–2018 videos) has different visual styling | Navigation hierarchy documented here remains valid; on-screen visual layout differs in older UI | B [V2, V3, V9] |

---

## Findings With No Gotchas Identified

The following sub-capabilities (2.6 Custom Spam Rules, 2.9 PDR, 2.10 RV, 2.11 SMTP Rate Control, 2.12 End User Digest) have no gotchas documented beyond the general admin guide authentication wall issue (G13). This is a consequence of LOW corpus coverage for these sub-capabilities, not evidence that they are gotcha-free. Undocumented edge cases likely exist and require verification against the authenticated PPS admin guide and community forums.

Sources checked for additional gotchas: B [S2], C [V2, V3, V9, S20, S16], D [community proofpoint.my.site.com spam tuning article, anti-spoof article, TAP exemption article].
