# Virus Policy Configuration — Gotchas & Known Limitations

## Summary

| # | Gotcha | Severity | Source Grade | Version-Specific |
|---|--------|----------|-------------|-----------------|
| G1 | Domain-level AV bypass exempts ALL senders at that domain, including spoofed/compromised accounts | HIGH | A — S1 | All versions |
| G2 | AV scanning cannot be disabled entirely in Essentials — bypass is the only control | MEDIUM | A — S1 | Essentials only |
| G3 | Virus-quarantined messages require admin release — end users cannot self-release | MEDIUM | D — S19 | All versions |
| G4 | PPS multi-layer AV and zero-hour AV configuration are entirely undocumented in accessible sources | MEDIUM | B — S2 (gap) | PPS/PoD only |

---

## Details

### G1: Domain-level AV bypass creates broad security exposure

**What you'd expect:** Bypassing a partner domain exempts that partner's legitimate messages.
**What actually happens:** Entering `partner.com` in the AV Bypass Address field bypasses AV scanning for ALL messages from any sender using that domain — including spoofed messages where an attacker claims to be from partner.com, and any email sent from a compromised account at partner.com.
**Workaround:** Use specific email addresses (`user@partner.com`) instead of domain-level entries whenever possible. For high-trust partners sending from multiple addresses, document the specific addresses and add them individually.
**Source:** [A — S1] — field description and format documentation
**Versions affected:** All Proofpoint Essentials versions

---

### G2: AV scanning cannot be disabled entirely in Essentials

**What you'd expect:** An On/Off toggle for AV scanning in the Virus settings page.
**What actually happens:** Proofpoint Essentials does not expose an AV enable/disable toggle. AV scanning is always active. The Virus settings page only manages the bypass list.
**Workaround:** If you need to test AV behavior, use the bypass list to exempt specific test senders. There is no global disable option.
**Source:** [A — S1] — only bypass list field documented; no enable/disable toggle present
**Versions affected:** Essentials only (PPS may have additional controls — INCOMPLETE)

---

### G3: Virus-quarantined messages require admin release — end users cannot self-release

**What you'd expect:** End users can release their own quarantined messages, similar to spam quarantine.
**What actually happens:** Messages quarantined for virus detection are held in an admin-only quarantine category. End users cannot release virus-quarantined messages via the quarantine digest or self-service portal.
**Workaround:** Administrators must manually review and release virus-quarantined messages when false positives are confirmed. Establish an internal process for users to submit false positive reports to the mail admin team.
**Source:** [D — S19] — community quarantine guide; confirmed category behavior
**Versions affected:** All versions

---

### G4: PPS multi-layer AV and zero-hour AV configuration are not documented in accessible sources

**What you'd expect:** Detailed configuration guidance for PPS AV engine settings.
**What actually happens:** The PPS admin guide is behind an authentication wall. Training material [S2] confirms multi-layer virus protection and zero-hour anti-virus exist in PPS, but step-by-step configuration fields, defaults, and options are not available in accessible sources.
**Workaround:** Consult Proofpoint documentation portal (help.proofpoint.com) with valid credentials, or contact Proofpoint support for PPS AV configuration guidance.
**Source:** Gap identified from [B — S2] training outline; admin guide inaccessible
**Versions affected:** PPS/PoD only

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| Essentials (2023 UI refresh) | Navigation may have shifted from "Company Settings > Virus" to within Security Settings hierarchy | S1 (2014) documents "Company Settings > Virus"; post-2023 nav path should be verified [B — video-intelligence.md, tribal knowledge] |

---

## No Additional Gotchas Identified

Checked sources: [S1] admin guide, [S2] training material, [S19] community quarantine guide. The Essentials virus configuration surface is a single field (bypass list), which limits the gotcha surface area. PPS-specific gotchas are underrepresented due to LOW source coverage — additional gotchas likely exist in PPS AV module configuration but are not documented in accessible sources.
