# Data Security / Endpoint DLP Policies — Gotchas & Known Limitations

> Capability: endpoint-dlp | Product: Proofpoint Data Security | Generated: 2026-05-21

---

## Summary

| # | Gotcha | Severity | Source Grade | Version-Specific |
|---|--------|----------|-------------|-----------------|
| G1 | Signal Type (DLP Only vs ITM) is irreversible after policy save | HIGH | A | All versions |
| G2 | Detection Rules with no Rule Set assignment never fire — no warning | HIGH | A | All versions |
| G3 | Priority semantics are INVERTED between Agent Policies and Detection Rules | HIGH | A + C | All versions |
| G4 | Prevention rule Detectors must be in Realm Data Classes or rule silently fails | HIGH | A | All versions |
| G5 | Web file upload blocking is Windows-only; applying to Mac has no effect | HIGH | A | All versions |
| G6 | Detection rules without explicit severity default to Informational/Low, invisible in most dashboards | HIGH | C | All versions |
| G7 | Empty If conditions in Agent Policy Details = catch-all for all Realm agents | MEDIUM | A | All versions |
| G8 | Default Account Policy is always-active fallback — editing it affects all Realms | MEDIUM | A | All versions |
| G9 | 100-rule tenant limit (combined detection + prevention); not self-service to increase | MEDIUM | A | All versions |
| G10 | Agent policy push interval unknown — immediate testing after save may give false negatives | MEDIUM | U (ASSUMPTION) | All versions |
| G11 | Data Redaction for GenAI requires GenAI integration provisioned separately | MEDIUM | C | 2025+ |
| G12 | Realm and Data Class configuration paths not accessible in public docs | MEDIUM | A (gap) | All versions |
| G13 | OS Type filter in If conditions is undocumented in main admin guide | LOW | C | All versions |
| G14 | Rule rollback is non-destructive (saved as new version) — version history grows indefinitely | LOW | A | All versions |

---

## Details

### G1: Signal Type is irreversible after Agent Policy save

**What you'd expect:** Signal Type (DLP Only vs ITM) can be changed at any time by editing the Agent Policy.

**What actually happens:** Once an Agent Policy is saved, the Signal Type field is locked. To change signal type, the entire policy must be deleted and recreated. All If/Then condition blocks and Prevention Rule associations in the Details tab are lost and must be reconfigured from scratch.

**Workaround:** Before saving a new Agent Policy, confirm the Signal Type with stakeholders — particularly HR and Legal, since ITM captures screenshots and keystrokes and may require disclosure obligations in many jurisdictions.

**Source:** [S7] — A [docs.public.analyze.proofpoint.com/admin/agent_policies_overview.htm] (architecture description implies immutability); UI lock behavior is **ASSUMPTION** [U] as explicit "field is locked" statement not found in accessible docs.

**Versions affected:** All

---

### G2: Detection Rules with no Rule Set assignment never fire — no warning

**What you'd expect:** A saved Detection Rule is active and firing on agents.

**What actually happens:** A Detection Rule that has no Rule Sets assigned (Step 1 of the wizard) is saved successfully with no error or warning, but it fires on no agents because Rule Sets are the bridge between rules and Realms. The rule appears in the list, has a valid configuration, and looks active — but zero events are ever generated from it.

**Workaround:** Always assign at least one Rule Set in Step 1 of the Detection Rule wizard before saving. After saving, verify the Rule Set assignment is reflected in the rule detail view.

**Source:** [S10] — A [docs.public.analyze.proofpoint.com/rules/rules_detection.htm] (Rule Set required for Realm linking — documented; silent failure on empty assignment is inferred — E)

**Versions affected:** All

---

### G3: Priority semantics are inverted between Agent Policies and Detection Rules

**What you'd expect:** Both Agent Policies and Detection Rules use the same priority convention — lower number = higher priority.

**What actually happens:** Agent Policies use lower number = higher priority. Detection Rules use higher number = higher priority (higher number fires first within a Rule Set). Administering both simultaneously without awareness of this inversion leads to misconfigured evaluation order.

**Workaround:** When setting priorities, use comments or naming conventions that clarify intent (e.g., "Priority 1000 = fires first" for detection rules, "Priority 1 = evaluated first" for agent policies). Document the inversion in any operational runbook.

**Source:** Agent Policy priority direction: [S8] — A. Detection Rule priority direction: [Video 16 ~3:00] — C (stated as "1–1000; higher number triggers first").

**Versions affected:** All

---

### G4: Prevention rule Detectors must be listed in Realm's Data Classes or rule silently fails

**What you'd expect:** Creating a Prevention Rule with a Detector assignment is sufficient for the rule to fire.

**What actually happens:** The Prevention Rule's Detectors must also appear in the Data Classes assigned to the target Realm. If the Realm's Data Class list does not include the Detector referenced by the prevention rule, the rule is never triggered. No error message or health indicator alerts the admin to this mismatch.

**Workaround:** When creating a Prevention Rule, immediately cross-check the Realm configuration to confirm the Detector is in the Realm's Data Class list. Add the Detector to the Realm's Data Classes if it is missing.

**Source:** [S11] — A [docs.public.analyze.proofpoint.com/rules/prevention_rules_overview.htm] (cross-reference: "Detectors must be included in Data Classes of assigned Realm")

**Versions affected:** All

---

### G5: Web file upload blocking is Windows-only

**What you'd expect:** A Prevention Rule with Action = Block and Scope = web file uploads applies to all endpoints regardless of OS.

**What actually happens:** Web file upload blocking is only enforced on Windows agents. macOS agents silently ignore web upload block prevention rules. No warning is shown in the console when configuring the rule.

**Workaround:** Use OS Type filters in the Agent Policy If/Then conditions to scope web upload prevention rules to Windows-only agents. Create a separate, less-restrictive policy for macOS users if needed.

**Source:** [S11] — A [docs.public.analyze.proofpoint.com/rules/prevention_rules_overview.htm] ("Block web file uploads (Windows only)")

**Versions affected:** All

---

### G6: Detection rules without explicit severity default to Informational/Low — invisible in most dashboards

**What you'd expect:** A newly created Detection Rule generates visible alerts when it fires.

**What actually happens:** If Severity is not explicitly set during rule creation (Step 3 of the wizard), the rule defaults to the lowest severity tier (documented as Informational in community context, implied as Low in official sources). Most SOC dashboards are configured to surface High or Critical severity detections only. Low/Informational detections are logged but never reviewed, creating a false sense that the rule is not firing.

**Workaround:** Always explicitly set Severity to High or Critical on enforcement rules during creation. Use Low or Medium only for monitoring-phase rules that are being baselined. After the baselining period, promote severity before enforcement.

**Source:** [Video 16 ~3:00] — C ("Severity not set = Informational; may not surface in dashboards configured to show only High/Critical")

**Versions affected:** All

---

### G7: Empty If conditions in Agent Policy Details = catch-all for ALL Realm agents

**What you'd expect:** An Agent Policy Details tab with no If conditions configured is effectively "inactive" or "not yet set up."

**What actually happens:** An empty If condition block means the Then settings apply to every agent in the Realm — there is no filter. This is functionally equivalent to a default/catch-all configuration. If a Then — Prevention Rule is associated in this state, it fires for every agent in the Realm without any scoping.

**Workaround:** If you intend a targeted policy (specific users or groups only), always add If conditions before associating Prevention Rules. If you intend a blanket policy, the empty If configuration is correct behavior — but be deliberate about it.

**Source:** [S9] — A [docs.public.analyze.proofpoint.com/admin/agent_policies_details.htm] (If/Then logic — empty condition = universal match)

**Versions affected:** All

---

### G8: Default Account Policy is always-active and editing it affects ALL Realms

**What you'd expect:** The Default Account Policy only affects unassigned agents.

**What actually happens:** The Default Account Policy is assigned to ALL Realms as a fallback. It cannot be deleted. Any change to the Default Account Policy immediately affects all Realms that rely on it as a catch-all — including Realms that have custom policies, where the Default Account Policy still applies to agents that don't match any custom policy's conditions.

**Workaround:** Treat the Default Account Policy as read-only in normal operations. Only modify it during a change-controlled procedure and after auditing which Realms and agents will be affected.

**Source:** [S7] — A [docs.public.analyze.proofpoint.com/admin/agent_policies_overview.htm] ("pre-configured, assigned to all Realms, inheritable")

**Versions affected:** All

---

### G9: 100-rule tenant limit (combined detection + prevention) is not self-service to increase

**What you'd expect:** The product scales to however many rules the organization needs.

**What actually happens:** The default maximum is 100 combined active rules (detection + prevention) across the entire tenant. Large organizations with granular rule requirements hit this limit. Increasing the limit requires opening a support request with Proofpoint — it cannot be self-managed in the admin console.

**Workaround:** Plan the rule estate carefully before deployment. Use Threat Library conditions (which cover broad scenarios in a single rule) rather than granular custom rules. Consolidate rules by using tags and condition filters rather than creating separate rules per department or use case. If the limit is hit, contact Proofpoint support.

**Source:** [S12] — A [docs.public.analyze.proofpoint.com/rules/rules_overview.htm] ("Default maximum: 100 combined active rules (detection + prevention) — Adjustable via Proofpoint support request")

**Versions affected:** All

---

### G10: Agent policy push interval is unknown — testing immediately after save may show stale behavior

**What you'd expect:** Policy changes take effect on endpoints immediately after saving.

**What actually happens:** Agents check in on a schedule to receive updated policies. The exact check-in interval is not documented in accessible Grade-A sources. Testing a new or modified rule immediately after saving may reflect the old policy configuration. This is analogous to the propagation delay documented in Proofpoint Essentials Email Filtering (5–30 min per Videos 2 and 20 — B grade) but the endpoint agent interval may differ.

**Workaround:** After saving any policy or rule change, wait for at least one full agent check-in cycle before testing. If the interval is known from Proofpoint support documentation, use that interval. If unknown, wait 15–30 minutes as a conservative estimate.

**Source:** **ASSUMPTION** [U] — agent policy push interval not documented in accessible sources. Propagation delay analogy from Proofpoint Essentials Email Filtering [Video 2 ~3:00] — B.

**Versions affected:** All

---

### G11: Data Redaction for GenAI requires separately provisioned GenAI integration

**What you'd expect:** Data Redaction for GenAI is available as a Prevention Rule action in all Proofpoint Data Security tenants.

**What actually happens:** Data Redaction for GenAI is a newer capability (referenced in Q3 2025 innovations blog) that requires the GenAI integration component to be provisioned for the tenant. Simply selecting the action in the Prevention Rule wizard may not be functional without the underlying integration.

**Workaround:** Before configuring Data Redaction for GenAI prevention rules, confirm with Proofpoint that GenAI integration is provisioned for your tenant. Available as of Q3 2025 product update.

**Source:** [S11] — A (action type documented), [S28] — C [Proofpoint Data Security Innovations Blog Q3 2025] (GenAI DLP confirmed as 2025 innovation). Full configuration detail INCOMPLETE in accessible sources.

**Versions affected:** Data Security 2025+ (Q3 2025 onwards)

---

### G12: Realm and Data Class configuration paths not accessible in public documentation

**What you'd expect:** All configuration steps for Endpoint DLP are accessible from the Proofpoint public documentation at docs.public.analyze.proofpoint.com.

**What actually happens:** The navigation paths for Realm configuration and Data Classes / Detector configuration are not documented in the publicly accessible portions of Proofpoint's documentation. These are foundational prerequisites for Agent Policies and Prevention Rules, respectively. Administrators cannot complete the full Endpoint DLP setup using public docs alone.

**Workaround:** Access Proofpoint's authenticated documentation (requires valid Proofpoint credentials), consult the Proofpoint implementation team during onboarding, or open a Proofpoint support ticket for configuration guidance.

**Source:** Corpus gap documented in research — [S7], [S9], [S10], [S11] all reference Realms and Data Classes but their configuration screens are not accessible in available Grade-A sources.

**Versions affected:** All (documentation gap, not a product version issue)

---

### G13: OS Type filter in Agent Policy If conditions is undocumented in the main admin guide

**What you'd expect:** The OS Type filter is prominently documented as an available If condition category.

**What actually happens:** The ability to filter Agent Policy If conditions by OS Type (Windows, Mac, Unix, Both) is demonstrated in the ITM product demo video (Video 16 ~1:00) but is not listed as a documented option in the official agent policy admin guide accessible at docs.public.analyze.proofpoint.com. Administrators building mixed-OS policies without knowing this filter exists may create overly broad policies.

**Workaround:** When building If conditions, explicitly look for an OS Type category in the Category dropdown. Use it to scope Windows-specific prevention rules (e.g., web upload blocking) to Windows agents only.

**Source:** [Video 16 ~1:00] — C (OS Type filter demonstrated but not called out in official docs [S9] — A)

**Versions affected:** All (documentation gap)

---

### G14: Rule rollback is non-destructive — version history grows indefinitely

**What you'd expect:** Rolling back to a previous version replaces the current version, keeping version history manageable.

**What actually happens:** Rule rollback creates a new version entry that is a copy of the selected historical version. The entire version history, including the version that was "rolled back from," is preserved. Over time, frequently edited rules accumulate large version histories. There is no documented version pruning or archival mechanism.

**Workaround:** Treat this as a feature (complete audit trail) rather than a problem. Document version numbering conventions in operational runbooks so teams can identify stable baseline versions quickly. Source: [S10] — A

**Versions affected:** All

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| Data Security Q3 2025 | Data Redaction for GenAI prevention action added | New prevention action type available; requires GenAI integration provisioning — see G11 |
| Data Security Q1/Q3 2025 | Detection rule simulation feature added | Allows testing detection rules without deploying to live endpoints — reduces risk of new rule testing |
| Data Security Q3 2025 | Endpoint prevention capabilities expanded | Block and Prompt actions extended to additional destination types; specific new destinations not enumerated in accessible sources |

**Source for version notes:** [S28] — C [Proofpoint Data Security Innovations Blog Q1/Q3 2025]
