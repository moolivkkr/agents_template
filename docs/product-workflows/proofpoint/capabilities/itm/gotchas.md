# ITM/ObserveIT Policy Configuration — Gotchas & Known Limitations

## Summary

| # | Gotcha | Severity | Source Grade | Version-Specific |
|---|--------|----------|-------------|-----------------|
| G1 | Key Logging is disabled by default — keystroke evidence never captured | HIGH | A | No (all 7.18.0) |
| G2 | Prevention rules silently do nothing in Agent Passive Mode | HIGH | A | No |
| G3 | Enable API is disabled by default — SOAR/SIEM integrations silently fail | HIGH | A | No |
| G4 | No severity default documented — alert rules may fire as Informational only | HIGH | B | No |
| G5 | Rule Type is irreversible — cannot change from Alert to Prevention after save | HIGH | A (inferred) | No |
| G6 | Newly created rules lack documented default priority — may land at lowest position | MEDIUM | B | No |
| G7 | OS Type mismatch causes rules to silently never fire | MEDIUM | B | No |
| G8 | Library updates require manual ZIP import — activated rules may be outdated | MEDIUM | A | No |
| G9 | Stealth/Privacy Policy for Windows not fully documented in accessible sources | MEDIUM | A (gap) | No |
| G10 | Custom condition syntax not documented publicly | MEDIUM | A (gap) | No |
| G11 | Continuous Recording and Color images multiply storage 3–5x without warning | MEDIUM | A | No |
| G12 | Identification Services configuration not fully documented | LOW | A (gap) | No |
| G13 | Alert rule severity default: informational alerts invisible in filtered dashboards | HIGH | B | No |

---

## Details

### G1: Key Logging is Disabled by Default

**What you'd expect:** An insider threat monitoring product would capture keystrokes and paste actions automatically.
**What actually happens:** Enable Key Logging is OFF by default. Rules designed to detect keystroke patterns (e.g., typing "password" or pasting large text blocks) will produce no evidence because the capture feature is not running.
**Workaround:** Navigate to Configuration → System Policy Settings → Enable Key Logging = ON before creating any keystroke-based detection rules.
**Source:** [S4] prod.docs.oit.proofpoint.com/configuration_guide/system_policy_settings.htm — ITM 7.18.0
**Versions affected:** All (default documented for ITM 7.18.0)

---

### G2: Prevention Rules Silently Do Nothing in Agent Passive Mode

**What you'd expect:** A Prevention Rule configured correctly will block the targeted user action.
**What actually happens:** If Enable Agent Passive Mode is ON in System Policy Settings, the agent observes events but cannot intercept them. Prevention rules will never block any action. No error or warning is shown in the rule configuration UI or the alert console.
**Workaround:** Before deploying prevention rules, verify Configuration → System Policy Settings → Enable Agent Passive Mode = OFF (or confirm the default is OFF — default not documented).
**Source:** [S4] prod.docs.oit.proofpoint.com/configuration_guide/system_policy_settings.htm — ITM 7.18.0
**Versions affected:** All

---

### G3: Enable API is Disabled by Default

**What you'd expect:** The ITM Agent API would be accessible after server installation for programmatic use.
**What actually happens:** Enable API is OFF by default. Any SOAR playbook, SIEM integration, or custom script that calls the ITM Agent API will fail silently until this toggle is enabled.
**Workaround:** Navigate to Configuration → System Policy Settings → Enable API = ON as part of initial deployment if API-triggered recording is part of the architecture.
**Source:** [S4] prod.docs.oit.proofpoint.com/configuration_guide/system_policy_settings.htm — ITM 7.18.0
**Versions affected:** All (Windows/Mac only — API not available on Unix)

---

### G4 / G13: Alert Severity Not Defaulted — Informational Alerts Invisible in Dashboards

**What you'd expect:** An alert rule that fires will appear in the alert dashboard.
**What actually happens:** No documented default severity exists for new rules. Video observation at ~3:00 suggests rules without explicit severity assignment default to Informational. Most ITM alert dashboards are configured to surface High and Critical alerts only. Informational alerts are logged but do not surface.
**Workaround:** Always explicitly set Severity = High (or appropriate level) on every new rule. Do not leave severity at the wizard's default state.
**Source:** Video 16 ~3:00 [B — Vendor training video]; [S6]
**Versions affected:** All (7.18.0 confirmed in video; likely broader)

---

### G5: Rule Type is Irreversible After Save

**What you'd expect:** You could change an Alert Rule to a Prevention Rule if you decide to escalate from monitoring to blocking.
**What actually happens:** Rule Type cannot be changed after the rule is saved. To change type, you must recreate the rule from scratch.
**Workaround:** Always start with Alert Rule type when testing a new detection pattern. Only create Prevention Rules once the alert pattern has been validated as low false-positive over at least 1–2 weeks of observation. [Video 16 workflow pattern, B]
**Source:** Inferred from workflow and rule structure [S6]; consistent with Video 16 [B]
**Versions affected:** All

---

### G6: New Rules Have No Documented Default Priority

**What you'd expect:** A new rule would be assigned a sensible default priority (e.g., medium).
**What actually happens:** No default priority is documented. Video observation notes priority range is 1–1000 (lower = higher priority) but does not confirm where new rules land. If a new rule lands at priority 1000 (lowest), it may be evaluated after a conflicting allow-rule at priority 1.
**Workaround:** Explicitly set Priority on every new rule. A recommended starting point is 100 for standard rules; use lower numbers (e.g., 10–50) only for high-priority override rules.
**Source:** Video 16 ~3:00 [B — Vendor training video]
**Versions affected:** All

---

### G7: OS Type Mismatch Causes Rules to Silently Never Fire

**What you'd expect:** A rule would fire for all endpoint agents.
**What actually happens:** Rules scoped to "Windows/Mac" will never evaluate on Unix agents, and vice versa. In mixed-OS environments, this means a rule intended for all users may have no coverage on a significant portion of the fleet.
**Workaround:** In mixed OS environments, set OS Type = "Both" for rules intended to fire universally, or create duplicate rules — one per platform — for platform-specific condition tuning.
**Source:** Video 16 ~1:00 [B — Vendor training video]
**Versions affected:** All

---

### G8: Insider Threat Library Updates Require Manual ZIP Import

**What you'd expect:** Activating a library rule ensures you always have the latest version of that rule.
**What actually happens:** Library updates are distributed as ZIP files by the Content Manager. Activating a rule from the Library today does not guarantee it will update when Proofpoint releases improved detection logic. You must manually check for and import the updated ZIP.
**Workaround:** Establish a routine (quarterly or after Proofpoint security advisories) to check for library update ZIPs and import them via Configuration → Alerts → Alert & Prevent Rules → Import.
**Source:** [S5] prod.docs.oit.proofpoint.com/insider_threat_library/itl_overview.htm — ITM 7.18.0
**Versions affected:** All

---

### G9: Windows Stealth / Privacy Policy Configuration Not Fully Documented

**What you'd expect:** Clear documentation of how to configure stealth mode (silent monitoring without user notification) vs notification mode for Windows endpoints.
**What actually happens:** The Recording Notification (yellow bar) is only documented for Unix. Windows-specific stealth vs notification policy configuration is mentioned in the taxonomy (sub-capability 8.5) but the detailed configuration fields are not documented in accessible public sources.
**Workaround:** Consult the full ITM On-Prem Configuration Guide (authentication required at prod.docs.oit.proofpoint.com) or contact Proofpoint Support for Windows-specific notification policy options.
**Source:** [S4] — gap identified; Unix notification documented, Windows equivalent INCOMPLETE
**Versions affected:** All

---

### G10: Custom Rule Condition Syntax Not Documented Publicly

**What you'd expect:** A reference for available condition operators, field names, and valid values when building a Custom condition in the rule creation wizard.
**What actually happens:** The "Custom" condition path in the New Rule Wizard requires knowledge of ITM's condition syntax and available activity types. This is not documented in the publicly accessible ITM guides indexed in the research corpus.
**Workaround:** Use "Threat Library" conditions as the primary method. For custom conditions, consult the ITM administration guide (behind authentication) or Proofpoint support documentation.
**Source:** [S6] — custom conditions referenced but not detailed; Video 16 [B] shows wizard steps only
**Versions affected:** All

---

### G11: Continuous Recording and Color Image Format Multiply Storage Significantly

**What you'd expect:** Enabling better capture quality settings has a minor infrastructure impact.
**What actually happens:** Enabling Continuous Recording (ON) captures screens at intervals regardless of user activity, generating large volumes of image data. Switching Image Format from Grayscale to Color can multiply storage consumption 3–5x per endpoint. Enabling both simultaneously on a large fleet without storage planning causes rapid disk exhaustion.
**Workaround:** Benchmark storage consumption on a small group (5–10 endpoints) before applying Continuous Recording or Color format fleet-wide. Use Grayscale Server Compression as the default; reserve Color for targeted investigation cases.
**Source:** [S4] — configuration guide notes these as CPU/storage intensive; 3–5x storage multiplier inferred from image format characteristics [E — Inferred from source context]
**Versions affected:** All

---

### G12: Identification Services (Secondary Login) Configuration Incomplete

**What you'd expect:** Full documentation of how to configure secondary login identification for shared accounts.
**What actually happens:** Identification Services is referenced in [S4] as a configuration area but specific screens, fields, and configuration steps are not covered in publicly accessible documentation.
**Workaround:** Contact Proofpoint Support or consult the full ITM administration guide behind authentication for Identification Services setup.
**Source:** [S4] — gap; [S6] — not referenced
**Versions affected:** All

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| ITM 7.18.0 | All documented settings confirmed for this version | Primary version for this document |
| Pre-7.18.0 | System Policy Settings fields and Insider Threat Library rule categories may differ | Verify field availability against your installed version before assuming all settings are present |
| ITM → Data Security migration | Some policy concepts map to Data Security "Agent Policies" (cloud) with different configuration screens | See [workflow.md](workflow.md) Integration Touchpoints section; on-prem ITM and cloud Data Security coexist but are configured independently [S7] |
