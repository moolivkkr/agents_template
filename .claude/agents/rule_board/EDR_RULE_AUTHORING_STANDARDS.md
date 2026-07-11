# EDR Rule Authoring Standards
# Derived from board review of 737 rules — systemic defects found and fixed
# Version: 1.0 — apply to ALL edr_rule authoring and board review

## Scope

These standards govern **endpoint behavioral detection rules** evaluated by the EDR agent
on process, file, network, registry, image load, memory, and driver events.

Complements:
- `.claude/agents/rule_board/rule_board_group_agent.md` — board review pipeline
- `.claude/agents/rule_board/edr_schema_validator.md` — DEFECT-1 through DEFECT-15 checklist
- `.claude/agents/rule_board/edr_soc_analyst.md` — alert fatigue and triage assessment
- `policies/edr/shared/` — process allowlist entities

---

## Systemic Defects Found During Board Review

### DEFECT-CAT-1: Broken Regex (3 rules affected)

NEVER ship a rule without compiling all regex patterns with `re.compile()`.

**Example (from T1003 review):**
```
Bad:  "(save|export).*\\(SAM|SECURITY"     ← unterminated group, rule fails to load silently
Good: "(save|export).*\\\\(SAM|SECURITY)"  ← escaped backslash + closed group
```

**Rule:** Every CI pipeline and board review MUST validate regex compilation.

### DEFECT-CAT-2: Catastrophic Response Mode (2 rules affected)

NEVER use `mode: "prevent"` + `isolate_host` on rules scoped to critical infrastructure.

**Example (from T1003 review):**
```
Bad:  DCSync rule with prevent + isolate_host scoped to hg_domain_controllers
      → Would kill Active Directory authentication on first alert
Good: DCSync rule with detect + soar_playbook scoped to hg_domain_controllers
      → Alert + automated investigation, human decides on isolation
```

**Rule:** `isolate_host` requires human confirmation for rules matching ANY of:
- Domain Controllers
- DNS servers
- Certificate Authority servers
- Database servers (production)

### DEFECT-CAT-3: Logical Impossibility in AND Conditions (1 rule affected)

NEVER have two conditions in AND that are mutually exclusive.

**Example (from Group 4 review):**
```
Bad:  AND[
        process.executable NOT starts_with "C:\Windows\System32\",
        process.executable starts_with "C:\Windows\System32\"
      ]
      → Rule can NEVER fire — contradictory conditions
```

**Rule:** Logic validator checks for field contradictions in every AND block.

### DEFECT-CAT-4: OR with Inverted Allowlist (1 rule affected)

NEVER put an exclusion as an OR branch alongside detection conditions.

**Example (from Group 4 review):**
```
Bad:  OR[
        {detection_conditions},
        {process.parent.name NOT_IN [apt, yum, dnf]}
      ]
      → Second branch fires for EVERY process not from a package manager = FP flood
Good: AND[
        {detection_conditions},
        {process.parent.name NOT_IN [apt, yum, dnf]}
      ]
      → Package manager exclusion filters the detection
```

### DEFECT-CAT-5: Root/SYSTEM User Excluded from Detection (1 rule affected)

NEVER exclude root/SYSTEM from attacker-context rules.

**Example (from Group 1 review):**
```
Bad:  Reverse shell rule excludes root user
      → Root-context reverse shells (post-privesc) are the primary C2 pattern
Good: Reverse shell rule includes all users
      → Legitimate root shells excluded via parent process context, not user identity
```

### DEFECT-CAT-6: Terminal/Shell Parent Excluded (1 rule affected)

NEVER exclude Terminal.app/iTerm2/bash from macOS rules where interactive attacker sessions
are the primary attack vector.

**Example (from T1003 review):**
```
Bad:  macOS credential dump excludes parent=Terminal.app
      → Interactive attacker typing dscl commands goes undetected
Good: Exclude MDM/config management parents (Jamf, Puppet, Chef)
      → Catches interactive attacks, suppresses legitimate automation
```

### DEFECT-CAT-7: Non-Existent Event Type (3 rules affected)

NEVER use event types that don't exist in the EDR agent schema.

**Example (from Group 3 review):**
```
Bad:  event_type: "FileAccess"  ← does not exist
Good: event_type: "FileRead"    ← valid EDR event type
```

**Valid event types:** ProcessCreate, FileCreate, FileModify, FileRead, FileDelete,
NetworkConnect, RegistryModify, RegistryCreate, ImageLoad, DriverLoad, MemoryAlloc,
DNSQuery, UserLogon, EventLog.

### DEFECT-CAT-8: DGA Regex Matches Legitimate Domains (1 rule affected)

NEVER use character-count-based DGA detection without consonant analysis.

**Example (from new rules review):**
```
Bad:  "^[a-z]{10,20}\.(com|net|org)$" ← matches "salesforce", "cloudflare", "servicenow"
Good: "^[b-df-hj-np-tv-z]{4,}[a-z]{0,3}[b-df-hj-np-tv-z]{4,}\." ← consonant clusters
```

### DEFECT-CAT-9: Wrong Exclusion Blinds Rule to Primary Attack (1 rule affected)

NEVER exclude the authentication protocol used by the primary attack technique.

**Example (from new rules review):**
```
Bad:  Network logon rule excludes NtLmSsp
      → NTLM is the auth method for Pass-the-Hash, PSExec, Impacket
Good: Exclude Kerberos and Negotiate (high-volume expected domain auth)
      → NTLM logons from unusual sources remain visible
```

---

## Model Assignment for Board Agents

| Agent | Model | Rationale |
|-------|-------|-----------|
| **Orchestrator** | opus | Planning, quality gates, final verdict decisions |
| **Group Agent** | sonnet | Structured evaluation, pattern matching, JSON manipulation |
| **Schema Validator** | sonnet | Checklist execution, regex compilation — no reasoning needed |
| **SOC Analyst** | sonnet | FP estimation, volume calculation — pattern-based |
| **Vendor Specialists** | sonnet | Vendor cache grep + comparison — structured output |
| **Moderator** | opus | Resolving contested points, gap analysis, final improved rule |
| **Consolidator** | opus | Cross-group pattern synthesis, opportunity ranking |

**Cost optimization:** Only orchestrator, moderator, and consolidator use opus (~15% of total tokens).
Remaining 85% on sonnet at ~75% cost reduction.

---

## Test Case Standards

Minimum per rule (ported from SIEM board):

| Type | Minimum Count | Purpose |
|------|--------------|---------|
| True positive | 5 | One per major OR branch + edge cases |
| True negative | 5 | One per major FP source (EDR vendor, admin tool, build system) |
| Evasion blind spot | 3 | Document what the rule cannot catch with current telemetry |

Each test case MUST include:
- Realistic field values (real binary names, real paths, plausible command lines)
- `expected_match: true/false`
- `branch` (which condition branch this tests)
- `reason` (why it should/shouldn't match)

---

## Weighted Scoring (ported from SIEM board)

| Dimension | Weight | What It Measures |
|-----------|--------|------------------|
| **Signal Strength** | 2x | IoA vs IoC, behavioral specificity, uniqueness of the detection |
| **FP Risk** | 2x | Enterprise-scale FP rate, allowlist completeness, volume estimate |
| **Evasion Resistance** | 1.5x | Tool variant coverage, rename resilience, injection blind spots |
| **Coverage** | 1.5x | MITRE sub-technique completeness, platform coverage |
| **Channel Fit** | 1x | All fields endpoint-observable, no SIEM-only dependencies |
| **Response Calibration** | 1x | Severity matches confidence * impact, mode matches FP profile |
| **SOC Operability** | 1x | Triage speed, enrichment quality, investigation pivot |

**Score = weighted_sum / 50 × 5 = N.N/5**

**Minimum for APPROVED: 4.0/5**
