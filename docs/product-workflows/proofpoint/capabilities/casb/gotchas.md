# CASB Policies — Gotchas & Known Limitations

> Capability: CASB Policies (group 10) | Product: Proofpoint CASB
> Evidence quality note: CASB has LOW documentation coverage. Most gotchas below are derived from Grade A/B sources (general capability descriptions) or are Grade U ASSUMPTIONS based on standard CASB product behavior patterns. Community and Grade D sources specific to Proofpoint CASB policy authoring were not found in the research corpus.

---

## Summary

| # | Gotcha | Severity | Source Grade | Version-Specific |
|---|--------|----------|-------------|-----------------|
| G1 | Policies are non-functional without an active connector | HIGH | A | No |
| G2 | CASB DLP and Email DLP classifiers are shared — misconfiguring one affects the other | HIGH | A | No |
| G3 | No video walkthrough exists for CASB policy authoring | MEDIUM | B | No |
| G4 | Connector OAuth scope requirements are not published in accessible docs | HIGH | U — **ASSUMPTION** | No |
| G5 | User group sync must be complete before scoped policies work | MEDIUM | A (inferred) | No |
| G6 | Alert-only mode vs. enforcement: the default remediation action is unknown | HIGH | U — **ASSUMPTION** | No |
| G7 | CASB admin console requires authentication — no public field-level docs | HIGH | A | No |
| G8 | Infrastructure Assessment requires separate IaaS connector (distinct from SaaS connectors) | MEDIUM | A (inferred) | No |

---

## Details

### G1: Policies are non-functional without an active connector

**What you'd expect:** Creating a CASB policy should immediately begin protecting your cloud applications.
**What actually happens:** CASB policies require at least one active cloud application connector. Without a provisioned connector, no traffic is visible to CASB and policies will not fire, but no error message may indicate this state. [S13 — Grade A confirms connector-based architecture]
**Workaround:** Before creating any policy, verify at least one connector is in Active status in the Connectors management section.
**Source:** S13 — Grade A — docs.public.analyze.proofpoint.com/pcasb/casb_overview.htm
**Versions affected:** All

---

### G2: CASB DLP and Email DLP share classifiers — cross-policy impact

**What you'd expect:** CASB DLP policies and Email DLP policies are configured independently with no cross-impact.
**What actually happens:** Proofpoint explicitly positions CASB DLP and Email DLP as using "shared classifiers and consistent policies across email and cloud apps." [S13 — Grade A] This means classifier changes that affect Email DLP may also affect CASB DLP behavior (or vice versa), depending on how the shared library is managed.
**Workaround:** When tuning DLP classifiers (e.g., adjusting match thresholds for a smart identifier), verify the impact on both Email DLP and CASB DLP alert volumes before saving changes to a shared classifier.
**Source:** S13 — Grade A
**Versions affected:** All (inherent to shared classifier architecture)

---

### G3: No video walkthrough exists for CASB policy authoring

**What you'd expect:** Like most Proofpoint features, a tutorial video would be available on the official YouTube channel.
**What actually happens:** Research across 30+ Proofpoint videos found zero CASB policy authoring content. The video intelligence corpus explicitly documents this as a confirmed gap: "CASB — Policy Rules: NO VIDEO — documentation only." [Video Intelligence — confirmed absence]
**Workaround:** Use the CASB admin console documentation (requires authentication at docs.public.analyze.proofpoint.com/pcasb/) or contact Proofpoint Professional Services for guided policy setup.
**Source:** video-intelligence.md — Coverage Gaps table
**Versions affected:** All (as of research date 2026-05-21)

---

### G4: Connector OAuth scope requirements are not in public documentation

**What you'd expect:** Proofpoint provides a clear list of required OAuth scopes or API permissions for each supported cloud application connector.
**What actually happens:** The CASB overview (S13) describes connector-based architecture but does not document the OAuth scopes or API permissions required for each application. This information is presumably in the authenticated admin docs.
**Workaround:** Before provisioning a connector, access the CASB admin console connector wizard — it typically lists required permissions inline during the setup flow. Have your cloud application admin present for the OAuth authorization step. [Grade U — **ASSUMPTION** based on standard connector UX patterns]
**Source:** S13 — Grade A (connector mentioned without scope details); field details Grade U — **ASSUMPTION**
**Versions affected:** All

---

### G5: User group sync must complete before group-scoped policies are effective

**What you'd expect:** Creating a policy scoped to a user group works immediately.
**What actually happens:** If user group sync has not completed (or the group does not yet exist in the synced directory), a group-scoped policy may either fail to save or silently apply to zero users.
**Workaround:** Verify group membership is visible in the CASB user directory before saving group-scoped policies. Run a manual directory sync if the group was recently created in your identity provider. [S13 — Grade A for user group targeting; timing behavior Grade U — **ASSUMPTION**]
**Source:** S13 — Grade A
**Versions affected:** All

---

### G6: Default remediation action is unknown — may default to enforcement

**What you'd expect:** New CASB DLP rules default to a non-disruptive monitoring mode (Alert Only).
**What actually happens:** The default remediation action for new CASB DLP rules is not documented in accessible sources. If the default is Block or Quarantine (rather than Alert), creating and enabling a new rule could immediately disrupt legitimate cloud file sharing.
**Workaround:** Explicitly set remediation action to Alert-Only (or equivalent monitoring mode) when creating any new DLP rule. Do not accept the default without verifying it is non-disruptive. [Grade U — **ASSUMPTION** based on best practice; actual default UNKNOWN]
**Source:** Grade U — **ASSUMPTION**
**Versions affected:** All

---

### G7: CASB admin console field-level documentation requires authentication

**What you'd expect:** Proofpoint's public documentation portal includes full field references for CASB policy configuration.
**What actually happens:** The research corpus confirms that detailed CASB policy configuration documentation is behind an authentication wall at docs.public.analyze.proofpoint.com/pcasb/. [S13 is a high-level overview only.] This means this document (workflow.md, advanced.md, quickstart.md) is structurally incomplete. Screen names, field names, required fields, and exact navigation paths require direct console access to verify.
**Workaround:** Use docs.public.analyze.proofpoint.com/pcasb/ with authenticated Proofpoint credentials, or contact Proofpoint Support for the CASB Administrator Guide PDF.
**Source:** Research corpus — doc-corpus.md Coverage Assessment table: "CASB Policies: LOW coverage — detailed policy config requires auth"
**Versions affected:** All — this is a documentation access limitation, not a product bug

---

### G8: Infrastructure Assessment requires a separate IaaS connector

**What you'd expect:** The same connector used for Microsoft 365 or Google Workspace CASB coverage also covers your AWS/Azure/GCP infrastructure.
**What actually happens:** IaaS Infrastructure Security Assessment (sub-capability 10.5) is a distinct CASB feature that requires a separate connector provisioned for the IaaS cloud provider (AWS, Azure, or GCP). The SaaS application connectors (Microsoft 365, etc.) do not provide IaaS visibility. [S13 — Grade A describes IaaS assessment as a distinct capability pillar]
**Workaround:** If Infrastructure Assessment is required, provision IaaS connectors separately. Have cloud infrastructure admin credentials (AWS IAM, Azure subscription Reader, GCP project-level access) ready.
**Source:** S13 — Grade A
**Versions affected:** All

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| Data Security current | CASB described as integrated into Data Security platform | Policy alerts appear in Data Security console alongside endpoint DLP events — single-pane management [S13 — Grade A] |
| Unknown — not documented | CASB DLP classifier library aligned with Email DLP library | Shared classifier changes impact both CASB and Email DLP simultaneously [S13 — Grade A] |

---

## Gotchas Not Found — Research Gap Note

The following CASB-specific gotcha categories were checked but found no evidence in the research corpus:

- CASB rule conflict resolution (when multiple rules match the same event) — INCOMPLETE
- Policy evaluation order / priority behavior — INCOMPLETE
- Connector authentication expiry and re-auth workflows — INCOMPLETE
- CASB alert fatigue mitigation settings (suppression, deduplication) — INCOMPLETE
- CASB quarantine release workflow for end users — INCOMPLETE
- Impact of CASB on application performance / latency — INCOMPLETE

These gaps exist because CASB admin console documentation is behind an authentication wall, and no community forum posts or video tutorials covering CASB policy authoring were found in the corpus.
