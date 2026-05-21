# ITM/ObserveIT Policy Configuration — Advanced Configuration Reference

> Version: ITM On-Prem 7.18.0 | Source coverage: HIGH (4 Grade A sources) for system settings and rule types

---

## Screen 1: Configuration > System Policy Settings

**Navigation:** Web Console → Configuration → System Policy Settings
**Source:** [S4] prod.docs.oit.proofpoint.com/configuration_guide/system_policy_settings.htm — ITM 7.18.0

### Fields

| Field | Type | Required | Default | Options | Validation | Description | Gotcha | Source |
|-------|------|----------|---------|---------|------------|-------------|--------|--------|
| Enable Recording | toggle | No | Enabled | Enabled / Disabled | — | Master recording switch for all agent-based capture | Disabling stops ALL rule evaluations — alerts and prevention rules will not fire | [S4] |
| Continue Recording After Lock | toggle | No | N/A | Enabled / Disabled | Visible only when Enable Recording = Disabled | Maintains API-triggered recording sessions when master recording is off | Only relevant for API-driven workflows | [S4] |
| Session Timeout | number | No | 15 minutes | Any positive integer (minutes) | — | Inactivity threshold before session closes in ITM | Setting to 0 may cause session fragmentation in reporting | [S4] |
| Enable Key Logging | toggle | No | Disabled | Enabled / Disabled | — | Captures keystrokes and paste actions | DISABLED by default — clipboard monitoring rules require this to be ON | [S4] |
| Keyboard Frequency | dropdown | No | 1 second | Every keystroke / 0.5s / 1s / 5s / 10s | Configurable only when Enable Key Logging = Enabled | Keystroke sampling interval | "Every keystroke" is extremely CPU-intensive; restrict to investigation-mode only | [S4] |
| Continuous Recording | toggle | No | OFF | ON / OFF | — | Interval-based screen capture independent of user activity | Significantly increases storage and CPU on all targeted endpoints | [S4] |
| Screen Recapturing Mode | radio | No | Focused window only | Focused window only / Entire screen | — | Controls whether capture shows active window or full desktop | Entire screen captures all monitors and all visible content — privacy impact is much higher | [S4] |
| Image Format | dropdown | No | Grayscale Server Compression (Win/Unix); Color (Mac) | Color / Grayscale Server Compression / Grayscale Client Compression | — | Compression mode for screen captures | Switching from Grayscale to Color can multiply storage 3–5x | [S4] |
| Enable Identity Theft Detection | toggle | No | UNKNOWN — not specified | Enabled / Disabled | — | Notifies users about endpoint access; supports secondary login identification | Required prerequisite for Identification Services configuration | [S4] |
| Enable Recording Notification | toggle | No | Disabled | Enabled / Disabled | Unix only | Displays yellow notification bar to Unix users indicating session is recorded | This is the only user-visible recording notification for Unix; Windows/Mac have no equivalent default notification | [S4] |
| Enable Live and Lock Messages | toggle | No | Disabled | Enabled / Disabled | Windows / Mac only | Enables admin console-to-endpoint messaging and session lock capability | — | [S4] |
| Enable API | toggle | No | Disabled | Enabled / Disabled | Windows / Mac only | Enables ITM Agent API for programmatic recording control | DISABLED by default — SOAR/SIEM integrations that trigger recordings will silently fail until enabled | [S4] |
| Enable Agent Passive Mode | toggle | No | UNKNOWN — not documented | Enabled / Disabled | All platforms | Agent receives events alongside applications (observe) vs intercepting them (active) | Prevention rules DO NOT fire in passive mode — blocking requires intercepting mode | [S4] |

### Platform Availability per Field

| Field | Windows | Mac | Unix/Linux |
|-------|---------|-----|-----------|
| Enable Recording | Yes | Yes | Yes |
| Continue Recording After Lock | Yes | Yes | Yes |
| Session Timeout | Yes | Yes | Yes |
| Enable Key Logging | Yes | Yes | No |
| Keyboard Frequency | Yes | Yes | No |
| Continuous Recording | Yes | Yes | No |
| Screen Recapturing Mode | Yes | Yes | No |
| Image Format | Yes | Yes | Yes |
| Enable Identity Theft Detection | Yes | Yes | Yes |
| Enable Recording Notification | No | No | Yes |
| Enable Live and Lock Messages | Yes | Yes | No |
| Enable API | Yes | Yes | No |
| Enable Agent Passive Mode | Yes | Yes | Yes |

Source: [S4]

### Conditional Fields

- **Continue Recording After Lock** is only accessible when **Enable Recording = Disabled**
- **Keyboard Frequency** is only configurable when **Enable Key Logging = Enabled**
- **Enable Recording Notification** only appears for Unix/Linux platform configurations

### Edge Cases

- If **Enable Recording = Disabled** AND **Continue Recording After Lock = Disabled**, the Enable API setting has no practical effect since no recording sessions can be initiated or continued. [S4]
- In passive mode, the agent observes events but cannot intercept them — this means **Prevention Rules will never block an action**, even if correctly configured and active. The only indication that passive mode is active is the toggle in System Policy Settings; there is no runtime warning in the alert console. [S4]

---

## Screen 2: Configuration > Alerts > Alert & Prevent Rules (List View)

**Navigation:** Configuration → Alerts → Alert & Prevent Rules
**Source:** [S6] prod.docs.oit.proofpoint.com/configuration_guide/exporting_and_importing_rules.htm — ITM 7.18.0

### List View Controls

| Control | Type | Description | Source |
|---------|------|-------------|--------|
| Rule Type Filter | dropdown | Filter list by Alert Rules / Prevention Rules / Policy Rules / System Rules | [S6] |
| New Rule button | button | Opens rule creation wizard | [S6] |
| Import button | button | Opens import dialog | [S6] |
| Export button | button | Initiates export of selected rules | [S6] |
| Insider Threat Library button | button | Opens Library panel | [S5] |

### Rule Type Definitions

| Rule Type | Purpose | Can Block? | Source |
|-----------|---------|-----------|--------|
| Alert Rules | Triggers notifications when conditions match | No | [S6] |
| Prevention Rules | Blocks activities in real-time | Yes | [S6] |
| Policy Rules | Records policy violations without active blocking | No | [S6] |
| System Rules | Pre-built rules from Insider Threat Library | No (read-only structure) | [S6] |

---

## Screen 3: Alert & Prevent Rules > New Rule Wizard

**Navigation:** Configuration → Alerts → Alert & Prevent Rules → New Rule
**Source:** [S6]; supplemented Video 16 [B]

### Fields

| Field | Type | Required | Default | Options | Validation | Description | Gotcha | Source |
|-------|------|----------|---------|---------|------------|-------------|--------|--------|
| Rule Type | radio | Yes | — | Alert Rule / Prevention Rule / Policy Rule | Must be selected before proceeding | Determines rule behavior (notify vs block vs log) | IRREVERSIBLE — cannot change type after save | [S6] |
| Rule Name | text | Yes | — | Free text | Unique within rule type | Internal identifier; displayed in alerts and reports | — | [S6] |
| OS Type | dropdown | Yes | UNKNOWN | Windows/Mac / Unix / Both | — | Limits rule to specified platform(s) | Rules targeting wrong OS will never fire — verify platform in mixed environments | Video 16 ~1:00 [B] |
| Priority | number | No | UNKNOWN | 1–1000 | Lower number = higher priority | Evaluation order among rules of same type | No documented default; new rules may be placed at lowest priority, after conflicting rules | Video 16 ~3:00 [B] |
| Condition | radio | Yes | — | From Library / Threat Library / Custom | — | Detection condition source | Custom conditions require knowledge of ITM condition syntax (not fully documented in accessible sources) | Video 16 ~2:00 [B] |
| Action | multiselect | Yes | — | Alert / Block (Prevention only) / Notify User / Log Only | Block only available when Rule Type = Prevention Rule | What triggers when condition matches | — | Video 16 [B]; [S6] |
| Severity | dropdown | No | UNKNOWN (likely Informational) | Informational / Low / Medium / High / Critical | — | Alert severity level | No documented default; if omitted, alerts may be invisible in dashboards filtered to High/Critical | Video 16 ~3:00 [B] |

### Conditional Fields

- **Block** action is only available when **Rule Type = Prevention Rule**
- **Condition** options differ based on rule type; System Rules have read-only conditions

### Edge Cases

- **Prevention Rules + Passive Mode:** Prevention rules configured correctly will silently fail if Enable Agent Passive Mode is ON. There is no warning at rule creation time about this interaction. [S4]
- **Priority Conflicts:** When multiple rules have the same priority value, evaluation order between them is UNKNOWN — not documented in accessible sources. [E — Inferred from priority field description]
- **Condition Syntax for Custom Conditions:** Custom condition syntax and available operators are not documented in publicly accessible sources. This section is INCOMPLETE — additional research required against ITM admin guide (authentication required). [S6 — partial]

---

## Screen 4: Insider Threat Library

**Navigation:** Configuration → Alerts → Alert & Prevent Rules → Insider Threat Library
**Source:** [S5] prod.docs.oit.proofpoint.com/insider_threat_library/itl_overview.htm — ITM 7.18.0

### Fields

| Field | Type | Required | Default | Options | Description | Source |
|-------|------|----------|---------|---------|-------------|--------|
| Category Filter | dropdown | No | All | INCOMPLETE — specific categories not enumerated in accessible sources | Filters rules by security category | [S5] |
| Platform Filter | dropdown | No | All | Windows / Mac / Unix/Linux / All | Limits view to platform-applicable rules | [S5] |
| Target User Group Filter | dropdown | No | All | Privileged Users / Everyday Users / Remote Vendors / All | Filters by user population | [S5] |
| Rule Status | toggle per rule | No | Active (top performers); Inactive (others) | Active / Inactive | Enables or disables individual library rules | [S5] |

### Library Structure

| Attribute | Value | Source |
|-----------|-------|--------|
| Total pre-built rules | 300+ | [S5] |
| Platform coverage | Windows, Mac, Unix/Linux | [S5] |
| Default activation | Top-performing rules active for Windows and Mac | [S5] |
| Update mechanism | ZIP file distributed by Content Manager | [S5] |
| User group targets | Privileged Users, Everyday Users, Remote Vendors | [S5] |
| Policy notifications | Built-in policy notifications for user awareness | [S5] |

### Edge Cases

- Library updates are distributed as ZIP files — activating a library rule does not guarantee it is the latest version. Check for pending ZIP file updates from the Content Manager before relying on library rules in a production threat response. [S5]
- Library rule conditions are read-only in the standard rule creation interface. To customize a library rule's condition, export it, modify, and re-import. [S6]

---

## Screen 5: Import/Export Dialog

**Navigation:** Configuration → Alerts → Alert & Prevent Rules → Import or Export button
**Source:** [S6]

### Import Fields

| Field | Type | Required | Default | Options | Description | Source |
|-------|------|----------|---------|---------|-------------|--------|
| Import File | file_upload | Yes | — | ZIP file | File containing previously exported rules | [S6] |
| Conflict Resolution | radio | No | UNKNOWN — not documented | Skip / Overwrite / Rename | Behavior when imported rule name conflicts with existing | [S6] |

### Export Fields

| Field | Type | Required | Default | Options | Description | Source |
|-------|------|----------|---------|---------|-------------|--------|
| Rule Types | multiselect | Yes | — | Alert Rules / Prevention Rules / Policy Rules / System Rules | Rule types to include in export ZIP | [S6] |

### User List Export

- User Lists can be exported/imported as CSV (separate from the rule ZIP export) [S6]
- Requires Admin or Config Admin role [S6]

### Edge Cases

- The import wizard detects both naming conflicts and missing referenced data (e.g., a rule referencing a user group that does not exist in the target environment). Review the wizard's conflict/missing-data summary before confirming the import. [S6]
- Importing System Rules (from Insider Threat Library) via ZIP may overwrite local customizations if Overwrite is selected. Use Skip or Rename for initial library imports to preserve any prior customization. [S6 — inferred from conflict resolution options]

---

## Screen 6: Identification Services

**Navigation:** Configuration → Identification Services
**Source:** [S4] — PARTIAL coverage

### Status: INCOMPLETE

The Identification Services screen is referenced in [S4] as a configuration area for secondary login identification (enabling ITM to identify the real user behind shared or secondary accounts). However, specific field names, configuration options, and workflow steps are not documented in publicly accessible sources.

**Known information:**
- Requires **Enable Identity Theft Detection = ON** in System Policy Settings [S4]
- Supports secondary login scenarios (e.g., IT admin logging into a shared terminal server account) [S4]
- Listed in taxonomy as complexity: Complex [taxonomy group 8.12]

**Missing evidence:** Full configuration workflow requires access to the ITM On-Prem Configuration Guide behind authentication at prod.docs.oit.proofpoint.com.

---

## Sub-Capability Coverage Matrix (Taxonomy Group 8)

| # | Sub-Capability | Coverage in This Document | Notes |
|---|---------------|--------------------------|-------|
| 8.1 | System Policy Settings (Recording/Monitoring) | FULL | Screen 1 — all 13 fields documented |
| 8.2 | Key Logging Configuration | FULL | Covered in Screen 1 (Enable Key Logging + Keyboard Frequency) |
| 8.3 | Screen Capture Configuration | FULL | Covered in Screen 1 (Continuous Recording, Screen Mode, Image Format) |
| 8.4 | Session Timeout Configuration | FULL | Covered in Screen 1 (Session Timeout field) |
| 8.5 | Recording Notification / Stealth Mode | PARTIAL | Unix notification documented; Windows/Mac stealth policy not fully documented [S4] |
| 8.6 | Insider Threat Library Rule Activation | FULL | Screen 4 — activation workflow, filters, update mechanism |
| 8.7 | Alert Rule Creation | PARTIAL | Wizard fields documented; custom condition syntax INCOMPLETE |
| 8.8 | Prevention Rule Creation | PARTIAL | Wizard fields documented; passive mode interaction documented; condition syntax INCOMPLETE |
| 8.9 | Policy Rule Creation | PARTIAL | Wizard fields documented; condition syntax INCOMPLETE |
| 8.10 | Rule Import/Export | FULL | Screen 5 — import/export fields, conflict resolution |
| 8.11 | User Group / Risk Level Targeting | PARTIAL | Library filters documented; custom user group definition workflow INCOMPLETE |
| 8.12 | Identification Services (Secondary Login) | INCOMPLETE | Screen 6 — field-level detail requires authenticated access to full guide |
| 8.13 | Agent API Configuration | PARTIAL | Enable API toggle documented; advanced API parameters INCOMPLETE |
