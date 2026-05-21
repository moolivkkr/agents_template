# Targeted Attack Protection (TAP) — Advanced Configuration Reference

> Complete field reference organized by screen. Read [workflow.md](workflow.md) for step-by-step context.
> Evidence grades are listed per field and per section.
> INCOMPLETE markers indicate fields that exist but are behind Proofpoint authentication walls.

---

## Screen 1: Administration > Account Management > Features

**Navigation:** Top navigation > Administration section > Account Management > Features tab

**Purpose:** Master feature toggles for TAP modules. This is the first screen you must configure.

### Fields

| Field | Type | Required | Default | Options | Validation | Description | Source |
|-------|------|----------|---------|---------|------------|-------------|--------|
| URL Defense | Toggle | Yes | **Disabled** | Enabled / Disabled | Requires TAP license | Master on/off for URL rewriting across the entire organization | [B, Video 5 ~0:30] |
| Attachment Defense | Toggle | No | UNKNOWN | Enabled / Disabled | Requires Attachment Defense license | Master on/off for attachment sandboxing | [B, S2 — existence confirmed; default not documented] |

### Conditional Fields

None documented for this screen.

### Edge Cases

- URL Defense is disabled by default after TAP provisioning. This contradicts the phrasing in some official documentation. The vendor tutorial video demonstrates an explicit enable step. Follow the video. Source: contradicted in [B vs B — Video 5 vs implied auto-activation in docs].
- Disabling URL Defense here overrides all per-group enablement settings — URL rewriting stops for everyone. Source: [E — inferred from feature toggle architecture].

---

## Screen 2: TAP > Settings > URL Defense

**Navigation:** TAP section > Settings > URL Defense tab

**Purpose:** Configure URL rewrite behavior — which URLs get rewritten and under what conditions.

**Coverage note:** This screen is behind the Proofpoint authentication wall. Field names and options documented below are derived from training material outlines [S2] and are INCOMPLETE. Treat all fields here as requiring verification against the actual UI.

### Fields

| Field | Type | Required | Default | Options | Validation | Description | Source |
|-------|------|----------|---------|---------|------------|-------------|--------|
| URL Rewrite Mode | Dropdown | Yes | UNKNOWN | INCOMPLETE — options not in accessible sources | Requires URL Defense master toggle enabled | Controls scope of URL rewriting: all URLs, selective, or domain-filtered | [B, S2 — field existence; options INCOMPLETE] |
| Rewrite Encoded URLs | Checkbox | No | UNKNOWN | Enabled / Disabled | None documented | Whether to decode and re-wrap URLs that are already encoded/obfuscated | [B, S2 — inferred from training content; field name unconfirmed] |

### Conditional Fields

INCOMPLETE — conditional field behavior behind auth wall.

### Edge Cases

- After URL Defense is enabled, inbound email URLs are rewritten to `https://urldefense.com/` format with the original destination encoded in the path. Source: [B, S2]
- Users clicking rewritten URLs are evaluated at click-time even if they forward the email days later — protection persists on the rewritten link. Source: [E — inferred from URL Defense architecture description]

---

## Screen 3: TAP > Settings > Attachment Defense

**Navigation:** TAP section > Settings > Attachment Defense tab

**Purpose:** Configure attachment sandboxing behavior — delivery mode, file type scope, and verdict actions.

**Coverage note:** INCOMPLETE — detailed field enumeration behind auth wall. Training outline confirms the screen exists [B, S2].

### Fields

| Field | Type | Required | Default | Options | Validation | Description | Source |
|-------|------|----------|---------|---------|------------|-------------|--------|
| Attachment Defense Mode | Dropdown | Yes | UNKNOWN | Hold-and-release / Deliver-and-retroactively-quarantine (names are descriptive; exact UI labels not documented) | Requires Attachment Defense licensed | Controls timing of sandboxing relative to message delivery | [B, S2 — modes inferred from training; labels INCOMPLETE] |
| Sandbox File Types | Multiselect | No | UNKNOWN | INCOMPLETE | None documented | Which attachment types are submitted for sandbox analysis | [B, S2 — feature known; type list INCOMPLETE] |

### Fixed Behaviors (Non-Configurable)

| Behavior | Description | Source |
|----------|-------------|--------|
| Encryption at rest | Sandboxed attachments are encrypted at rest during analysis | [C, S22] |
| Post-verdict deletion | Attachments are deleted from sandbox storage after verdict is returned | [C, S22] |

### Conditional Fields

INCOMPLETE.

### Edge Cases

- In hold-and-release mode, messages containing attachments that require sandbox analysis may have their delivery delayed by the time it takes the sandbox to return a verdict. The duration of that delay is not documented in accessible sources. Source: [E — inferred from hold-and-release delivery model]
- If the sandbox is unavailable or times out, verdict handling behavior (deliver vs hold) is not documented. Source: [E — inferred gap; INCOMPLETE]

---

## Screen 4: TAP > Settings > Per-Group Enablement

**Navigation:** TAP section > Settings > [group configuration sub-section — exact tab name INCOMPLETE]

**Purpose:** Override global URL Defense and Attachment Defense toggles for specific user groups. Used for phased rollouts, pilot programs, or permanent group-scoped TAP policies.

### Fields

| Field | Type | Required | Default | Options | Validation | Description | Source |
|-------|------|----------|---------|---------|------------|-------------|--------|
| Group | Dropdown | Yes | None | Pre-existing user groups from PPS/PoD directory | Group must exist before this screen is accessed | The user group for which TAP is being overridden | [C, S22] |
| URL Defense (group-level) | Toggle | No | Inherits global setting | Enabled / Disabled | None documented | Override URL Defense for this group specifically | [C, S22] |
| Attachment Defense (group-level) | Toggle | No | Inherits global setting | Enabled / Disabled | None documented | Override Attachment Defense for this group specifically | [C, S22] |

### Conditional Fields

None documented.

### Edge Cases

- User group must exist in the PPS/PoD user directory before it can be referenced here. No inline group creation is available from this screen. Source: [C, S22]
- Behavior when a group-level toggle is Enabled but the global master toggle (Screen 1) is Disabled is not documented. **ASSUMPTION [U]:** a globally disabled feature cannot be overridden at group level — the master toggle has precedence.

---

## Screen 5: TAP Dashboard > Exemptions

**Navigation:** TAP Dashboard > [Exemptions sub-section — exact path INCOMPLETE]

**Purpose:** Add senders whose TAP-generated alerts should be suppressed. URL Defense and Attachment Defense continue scanning; only dashboard alerting is suppressed.

### Fields

| Field | Type | Required | Default | Options | Validation | Description | Source |
|-------|------|----------|---------|---------|------------|-------------|--------|
| Sender Address or Domain | Text | Yes | None | Free text: user@domain.com or domain.com | SMTP format required | The sender address or domain to exempt from TAP alert generation | [C, S21] |
| Exemption Type | Dropdown | No | UNKNOWN | INCOMPLETE — options not in accessible sources | None documented | Scope or category of exemption | [C, S21 — existence inferred] |

### Conditional Fields

None documented.

### Edge Cases

- Adding a sender to this TAP Exemption list does NOT add them to the Email Protection safe-sender list. These are separate, independent lists in separate UIs. A sender on the TAP exemption list still gets their mail filtered by Email Protection spam/virus/firewall rules. Source: [C, S21] + community tribal knowledge.
- Adding a sender to the Email Protection safe-sender list does NOT suppress TAP Dashboard alerts for that sender. Admins must add the sender to both lists independently if both behaviors are desired. Source: [C, S21].
- Whether a full scanning bypass (not just alert suppression) is available via this UI is not documented. **ASSUMPTION [U]:** only alert suppression is configurable here; full bypass would require a policy route or Email Firewall allow-rule change.

---

## Screen 6: TAP Dashboard / Isolation Console > URL Isolation > VIP/VAP Policy

**Navigation:** TAP Dashboard or Isolation Console > Policies > URL Isolation (exact path varies by product version and whether TAP Dashboard or Isolation Console is the entry point)

**Purpose:** Assign VIPs and VAPs to URL Isolation, so their URL clicks are rendered in Proofpoint's remote browser isolation environment rather than their local browser.

### Fields

| Field | Type | Required | Default | Options | Validation | Description | Source |
|-------|------|----------|---------|---------|------------|-------------|--------|
| VIP/VAP User List | File upload | Yes | None | CSV or supported format — exact format INCOMPLETE | Must be exported from User Center or TAP Dashboard first | List of users to receive isolation-enhanced URL protection | [B, S15] |
| Import Source | Dropdown | Yes | UNKNOWN | User Center / TAP VAP export | None documented | System from which the list was exported — determines list type and format handling | [B, S15] |
| Isolation Policy Assignment | Dropdown | Yes | UNKNOWN | Available Isolation policies (from Isolation Console configuration) | Isolation policy must exist before import | Which browsing policy applies when these users click rewritten URLs | [B, S15] |

### Conditional Fields

None documented.

### Edge Cases

- This import is MANUAL. The VAP list in TAP Dashboard does not automatically sync to the Isolation policy. Source: Proofpoint Isolation docs + Video 17 ~1:30 [C, confirmed].
- After any TAP threat review cycle that changes the VAP roster (new high-frequency targets, removed targets), the list must be re-exported from TAP Dashboard and re-imported here. There is no webhook or API to automate this sync. Source: [C, Video 17 ~1:30; B, S15].
- Proofpoint Isolation must be licensed and have its own base configuration complete before this import screen is functional. Source: [B, S15].

---

## Screen 7: TAP Dashboard > Dashboard Settings

**Navigation:** TAP Dashboard > Settings or Preferences

**Purpose:** INCOMPLETE — TAP Dashboard settings screen fields are entirely behind the authentication wall.

Training materials (Video 15) confirm the TAP Dashboard provides real-time insight, analysis, and situational awareness for TAP threat events. Source: [C, Video 15].

**INCOMPLETE — fields require authentication-gated documentation to enumerate.**

---

## TAP URL Rewrite Format Reference

When URL Defense is active, all inbound email URLs are rewritten to:

```
https://urldefense.com/v3/__<original-URL-encoded>__;!!<verification-token>!<hash>$
```

Source: [B, S2 — URL format described in training; exact encoding schema INCOMPLETE]

Users and email clients that render links will see the `urldefense.com` prefix. This is normal and expected behavior — not a sign of filtering errors.

---

## Version-Specific Notes

See [gotchas.md](gotchas.md) for version-specific behavioral differences and known issues.
