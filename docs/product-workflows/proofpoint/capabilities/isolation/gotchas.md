# Browser/Email Isolation Policies — Gotchas & Known Limitations

> Capability: Browser/Email Isolation Policies (group 11) | Product: Proofpoint Isolation
> Evidence base: S15 (Grade B), Video 17 (Grade C), Video 18 (Grade C), video-intelligence.md (gotchas table)

---

## Summary

| # | Gotcha | Severity | Source Grade | Version-Specific |
|---|--------|----------|-------------|-----------------|
| G1 | VAP list does NOT auto-sync from TAP to Isolation | HIGH | C — confirmed in Video 17; B — S15 wording confirms manual import | No |
| G2 | No admin policy authoring walkthrough video exists | HIGH | B — video-intelligence.md confirmed absence | No |
| G3 | Isolation Console is a separate portal from all other Proofpoint consoles | HIGH | B — S15; product architecture | No |
| G4 | TAP-era documentation (2019) and current Isolation (2022+) may reflect different UI | MEDIUM | C — Video 17 vs Video 18 | Version-specific |
| G5 | Inline DLP for isolation requires Enterprise DLP integration — not self-contained | HIGH | B — S15 | No |
| G6 | Per-group browsing policies require user sync complete before policy is effective | MEDIUM | B — S15, inferred | No |
| G7 | "Isolation" behavior (rendered container) is architecturally distinct from "Block" — users can still interact with isolated sites | MEDIUM | C — Video 18 end-user experience | No |
| G8 | URL category definitions are managed by Proofpoint — admin cannot add custom categories | MEDIUM | Grade U — **ASSUMPTION** based on standard URL categorization model | No |

---

## Details

### G1: VAP list does NOT auto-sync from TAP to Isolation — manual import required

**What you'd expect:** When a new user appears on the TAP VAP (Very Attacked People) list, they are automatically added to the strict isolation policy.
**What actually happens:** S15 states "you can import your VIP user list from User Center and the VAP list from TAP" — the word "import" confirms this is a manual, one-time action per import cycle. Video 17 at ~1:30 further establishes that the VAP list must be manually imported: "TAP VAP list requires that the VAP list is manually imported from the TAP Dashboard to the Isolation policy — it does not automatically sync."
**Impact:** New VAPs who appear between import cycles browse the web without the stricter isolation controls until the next manual re-import. For a user who becomes a VAP due to an active targeted attack, this window can span days or weeks.
**Workaround:** Schedule regular VAP list re-import. Trigger an import immediately after any TAP threat summary review that changes the VAP roster. Set a calendar reminder or, if Proofpoint provides a webhook/API for VAP roster changes, automate the trigger. [Video 17 ~1:30 — Grade C; S15 — Grade B]
**Source:** Video 17 ~1:30 — Grade C (Proofpoint TAP Browser Isolation Product Demo, 2019-08-15); S15 — Grade B (Isolation data sheet, Aug 2023 — "import" wording)
**Versions affected:** All — this is an architectural limitation of the TAP <> Isolation integration, not a version-specific bug

---

### G2: No admin policy authoring walkthrough video exists for Isolation

**What you'd expect:** Like Email Protection and ITM features, Proofpoint provides YouTube tutorial videos demonstrating how to create and configure Isolation policies in the admin console.
**What actually happens:** Two Isolation videos exist (Video 17, Video 18) but both are product demos showing the end-user isolation experience. Neither demonstrates the admin workflow for creating redirect rules, browsing policies, or assigning VAP groups. The video intelligence corpus explicitly confirms: "Browser Isolation — Policy Authoring: PARTIAL — Neither video demonstrates the admin workflow for creating or modifying URL Isolation Policies or assigning VAP/VIP user groups to isolation policies."
**Impact:** Administrators configuring Isolation for the first time have no video walkthrough to reference. All guidance must come from admin docs (behind auth wall) or Proofpoint Professional Services.
**Workaround:** Access docs.public.analyze.proofpoint.com with authenticated Proofpoint credentials, or request the Isolation Administrator Guide from Proofpoint Support. Consider engaging Proofpoint Professional Services for initial setup.
**Source:** video-intelligence.md — Coverage Gaps table
**Versions affected:** All — as of research date 2026-05-21

---

### G3: Isolation Console is a completely separate portal from all other Proofpoint consoles

**What you'd expect:** Isolation policies are configured within the Proofpoint Email Protection console or the Proofpoint Data Security admin portal — the same interfaces used for email filtering, TAP settings, and DLP.
**What actually happens:** Proofpoint Isolation has its own dedicated admin console, distinct from the Email Protection console (where TAP settings and email firewall rules live), the Proofpoint Essentials console (where filter policies live), and the Proofpoint Data Security admin portal (where endpoint DLP and agent policies live). An admin configuring an end-to-end isolation workflow must switch between multiple separate admin portals.
**Impact:** Admins may spend significant time looking for Isolation policy settings in the wrong console. Role-based access may differ between consoles — an admin who has full access to Email Protection may not have admin access to the Isolation Console.
**Workaround:** Confirm the Isolation Console URL with your Proofpoint account team during provisioning. Ensure admin accounts for both the Email Protection console and the Isolation Console are provisioned for the administrators responsible for isolation policy management.
**Source:** S15 — Grade B (Isolation described as standalone product with dedicated console); product architecture evident from separation of TAP Dashboard, Data Security console, and Isolation Console
**Versions affected:** All — architectural separation

---

### G4: TAP-era Isolation documentation (2019) reflects different UI than current product (2022+)

**What you'd expect:** All Proofpoint Isolation documentation and videos are current and consistent.
**What actually happens:** Video 17 (2019) documents the TAP Browser Isolation era, when Isolation was integrated within TAP. Video 18 (2022) shows the rebranded standalone "Proofpoint Isolation" product. The admin console UI and potentially some configuration terminology have changed between these eras. The video intelligence notes: "TAP URL Isolation for VAPs (Video 17, 2019) predates the generalized Browser Isolation product (Video 18, 2022). By 2022 the product is rebranded to 'Proofpoint Isolation' and accessed separately from TAP Dashboard."
**Impact:** Navigation paths, button labels, and configuration terminology documented in Video 17-era resources may not match the current Isolation Console.
**Workaround:** Use S15 (Aug 2023 data sheet) as the most current description of capabilities. Verify navigation paths in the live Isolation Console rather than relying on 2019-era documentation.
**Source:** video-intelligence.md — Version-Specific Notes
**Versions affected:** Affects documentation reliability for TAP Browser Isolation-era deployments vs. standalone Proofpoint Isolation deployments

---

### G5: Inline DLP for isolation sessions requires Enterprise DLP integration — not self-contained

**What you'd expect:** The "inline DLP for uploads/downloads" feature works out of the box once enabled in the Upload/Download Restriction policy.
**What actually happens:** The Isolation DLP capability leverages the Enterprise DLP engine from Proofpoint Data Security for content classification. [S15 — Grade B: "inline real-time DLP for uploads/downloads" with cross-reference to S13's "Isolation DLP | Enterprise DLP | inline real-time DLP for upload/download in isolation sessions"] Enabling the Sensitive Data Detection toggle in the Upload/Download Restriction policy connects to this engine. If Enterprise DLP is not configured with detection rules, the scan runs but has nothing to match against.
**Impact:** An admin who enables inline DLP for isolation sessions without first configuring Enterprise DLP detection rules will see no DLP alerts from isolation sessions, with no error message indicating why.
**Workaround:** Before enabling Sensitive Data Detection in isolation Upload/Download Restrictions:
1. Confirm Proofpoint Data Security is licensed and provisioned
2. Verify at least one detection rule with an active detector is configured in the Enterprise DLP platform
3. Confirm the Isolation <> Enterprise DLP integration is activated (exact configuration UNKNOWN — INCOMPLETE)
**Source:** S15 — Grade B; S13 cross-reference (Grade A); integration config details Grade U — **ASSUMPTION**
**Versions affected:** All — architectural requirement

---

### G6: Per-group browsing policies are silently ineffective until user sync is complete

**What you'd expect:** Creating a browsing policy scoped to a group name takes effect immediately.
**What actually happens:** If the user group has not been synced into the Isolation Console (or if the sync is stale), a group-scoped browsing policy may apply to zero users without any error. Users in that group continue to receive the default browsing policy (or no isolation at all).
**Impact:** An admin who creates a strict browsing policy for "Finance Team" but has not verified the "Finance Team" group is synced will find the policy is non-functional until sync is verified.
**Workaround:** Before creating any group-scoped policy, navigate to the Isolation Console user list and verify the target group appears with the expected members. Run a manual sync if the group was recently created in your identity provider.
**Source:** S15 — Grade B (per-group policies confirmed); timing behavior Grade U — **ASSUMPTION**
**Versions affected:** All

---

### G7: Isolation does not block sites — it renders them safely; users can still interact

**What you'd expect:** URL isolation is a form of blocking — the user cannot access the isolated site's functionality.
**What actually happens:** Isolation renders the web page inside a secure cloud container and delivers a safe visual representation to the user's browser. The user can still see and interact with the page content (depending on the browsing policy's interaction level). Video 18 demonstrates this: the end user experiences a near-normal browsing session, just rendered remotely. The key protection is that executable code (JavaScript, active content) never reaches the user's device.
**Impact:** Users may not realize they are in an isolated session. If the browsing policy interaction level is set to "Full Interactive," a user on a phishing site can still be socially engineered into voluntarily entering their credentials. User Input Controls (sub-capability 11.6) must be configured to prevent credential entry in isolated sessions.
**Workaround:** For high-risk URL categories and VIP/VAP user groups, set the browsing policy interaction level to "Limited" or "Read-Only" AND enable User Input Controls to prevent credential entry. Relying on isolation alone (without input controls) does not prevent credential theft if the user voluntarily types their password.
**Source:** Video 18 — Grade C (Proofpoint Isolation Demo, 2022-12-29 — end-user experience confirmed); S15 — Grade B ("dynamic limits on form input to prevent credential theft" — implies this control is needed in addition to isolation)
**Versions affected:** All — architectural characteristic of isolation technology

---

### G8: URL categories are Proofpoint-managed — admins cannot add custom categories

**What you'd expect:** Admins can create custom URL categories (e.g., "Company Partner Sites") and reference them in redirect rules and restrictions.
**What actually happens:** URL category lists used in redirect rules and upload/download restrictions are managed by Proofpoint's URL reputation service. Admins can apply pre-defined categories but (based on standard CASB/isolation product patterns) typically cannot define custom URL categories. Custom URL targeting requires explicit URL patterns rather than category references.
**Impact:** If your redirect rule strategy relies heavily on categories, you are dependent on Proofpoint's categorization of each URL. Newly registered domains may not yet be categorized, and some high-risk URLs may fall into incorrect categories until Proofpoint's reputation service updates.
**Workaround:** Supplement category-based redirect rules with explicit URL pattern rules for known high-risk domains specific to your organization or industry.
**Source:** Grade U — **ASSUMPTION** based on standard URL categorization service model. Requires verification against live Isolation Console.
**Versions affected:** All (if assumption is correct)

---

## Version-Specific Notes

| Version | Change | Impact | Source |
|---------|--------|--------|--------|
| TAP Browser Isolation (pre-2022) | Integrated into TAP product; admin settings accessed from TAP Dashboard | Navigation paths differ from current Isolation Console | Video 17 — Grade C |
| Proofpoint Isolation (2022+) | Rebranded as standalone product with dedicated Isolation Console | Separate admin portal; different navigation than TAP-era docs | Video 18 — Grade C |
| Isolation data sheet (Aug 2023) | Current capability descriptions | Most reliable current-state reference | S15 — Grade B |

---

## Gotchas Not Found — Research Gap Note

The following Isolation-specific gotcha categories were checked but found no evidence in the research corpus:

- Isolation session performance impact on users (latency, rendering fidelity) — INCOMPLETE
- Browser compatibility requirements for end users in isolation sessions — INCOMPLETE
- Isolation Console RBAC roles (admin vs read-only vs operator) — INCOMPLETE
- Policy precedence when multiple redirect rules match the same URL — INCOMPLETE
- What happens when Isolation service is unavailable (fail-open vs fail-closed) — INCOMPLETE
- Isolation audit logging and session recording capabilities — INCOMPLETE
- Conditional access integration (does Isolation respect existing Conditional Access policies?) — INCOMPLETE

These gaps exist because Isolation admin console documentation is behind authentication and no community forum posts covering Isolation policy authoring edge cases were found in the research corpus.
