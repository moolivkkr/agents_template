# Browser/Email Isolation Policies — Advanced Configuration Reference

> Sub-capabilities: 11.1 – 11.7 | Product: Proofpoint Isolation
> Evidence base: S15 (Grade B — data sheet), Video 17 (Grade C — demo 2019), Video 18 (Grade C — demo 2022)
> Coverage level: MODERATE at capability description level; LOW at field/screen level

---

## Coverage Warning

Admin console field-level documentation for Isolation requires authentication. The data sheet (S15) describes capability dimensions for each sub-capability. Screen names, field names, required fields, and navigation paths are INCOMPLETE unless explicitly quoted from S15 or derived from videos. Grade U ASSUMPTION items are marked.

The one confirmed navigation path in accessible sources is: **Isolation Console > Policies > Redirect Rules** [S15 — Grade B].

---

## Screen: Isolation Console > Policies > Redirect Rules (Sub-capability 11.3)

**Navigation:** Isolation Console > Policies > Redirect Rules [S15 — Grade B — confirmed]
**Purpose:** Define which URLs or URL categories cause Proofpoint to intercept navigation and render content in the cloud isolation container.

### Fields

| Field | Type | Required | Default | Options | Validation | Description | Source |
|-------|------|----------|---------|---------|------------|-------------|--------|
| Rule Name | Text | Yes | None | Free text | Non-empty, unique | Internal identifier | E — Inferred |
| URL / URL Pattern | Text | No | None | Specific URL or wildcard (e.g., *.newdomain.com) | Valid URL syntax | Exact URL or pattern that triggers isolation | E — Inferred from S15 |
| URL Category | Dropdown/multiselect | No | None | Newly Registered Domains, Uncategorized, Adult, Gambling, etc. (exact category list UNKNOWN) | — | Category-based redirect triggers | E — Inferred from S15 restriction category descriptions |
| User / Group Scope | Multi-select | No | All users | Synced user groups | — | Narrows redirect rule to specific user populations | S15 — Grade B (per-group policies confirmed) |
| Action | Select | Yes | Unknown | Isolate, Block, Allow | — | What to do when URL matches rule | E — Inferred from product capability |
| Rule Priority | Number | No | Unknown | Numeric | — | Evaluation order when multiple rules match | Grade U — **ASSUMPTION** |
| Rule Enabled | Toggle | Yes | Unknown | Enabled/Disabled | — | Must be enabled for rule to fire | Grade U — **ASSUMPTION** |

### Conditional Fields

When Action = **Block**: a user-facing block page message field may appear. [Grade U — **ASSUMPTION**]

### Edge Cases

- URL category lists are managed by Proofpoint and update automatically — no admin action required to receive category updates. [Grade U — **ASSUMPTION** based on standard URL categorization service]
- A URL matching multiple redirect rules is processed by the highest-priority rule. If two rules conflict (one isolates, one blocks), the outcome depends on the priority ordering. [Grade U — **ASSUMPTION**]

---

## Screen: Isolation Console > Policies > Browsing Policies (Sub-capability 11.1)

**Navigation:** INCOMPLETE — navigated from Isolation Console Policies section
**Purpose:** Control what users can do within isolated browser sessions. Different groups can have different access levels (e.g., executives get read-only for unknown sites; researchers need full interactivity).
**Source:** S15 — Grade B ("browsing policies per-group access controls — researchers get less restrictive access; executives get stricter controls")

### Fields

| Field | Type | Required | Default | Options | Validation | Description | Source |
|-------|------|----------|---------|---------|------------|-------------|--------|
| Policy Name | Text | Yes | None | Free text | Non-empty, unique | Internal identifier | E — Inferred |
| User Group | Multi-select | Yes | None | Synced user groups | At least one group | Which groups this policy applies to | S15 — Grade B |
| Interaction Level | Select | Yes | Unknown | Read-Only, Limited Interaction, Full Interactive (options UNCONFIRMED) | — | Determines what user can do in isolated session | Grade U — **ASSUMPTION** |
| URL Category Permissions | Multi-select | No | None | URL categories (list UNKNOWN) | — | Allow or restrict specific URL categories within isolation | E — Inferred from S15 |
| Copy/Paste Control | Select | No | Unknown | Allow, Block, Alert (options UNCONFIRMED) | — | Control clipboard operations in isolated session | Grade U — **ASSUMPTION** |
| Print Control | Select | No | Unknown | Allow, Block | — | Control printing from isolated sessions | Grade U — **ASSUMPTION** |

### Conditional Fields

Multiple browsing policies can be created for different groups. If a user belongs to multiple groups with conflicting policies, the highest-priority or most restrictive policy may apply — precedence behavior UNKNOWN. [Grade U — **ASSUMPTION**]

---

## Screen: Isolation Console > Policies > Upload/Download Restrictions (Sub-capability 11.2)

**Navigation:** INCOMPLETE
**Purpose:** Block, alert on, or log file transfers during isolated browser sessions. S15 documents five restriction dimensions.
**Source:** S15 — Grade B ("upload/download restrictions by URL, URL category, file type, sensitive data, malware")

### Fields

| Field | Type | Required | Default | Options | Validation | Description | Source |
|-------|------|----------|---------|---------|------------|-------------|--------|
| Restriction Name | Text | Yes | None | Free text | Non-empty, unique | Internal identifier | E — Inferred |
| Direction | Select | Yes | Both | Uploads, Downloads, Both | — | Which transfer direction to restrict | E — Inferred from S15 |
| URL Filter | Text | No | None | Specific URL or pattern | Valid URL | Restrict transfers from/to specific URLs | S15 — Grade B |
| URL Category Filter | Multi-select | No | None | URL categories | — | Restrict transfers from URL categories | S15 — Grade B |
| File Type Filter | Multi-select | No | None | .exe, .zip, .pdf, .docx, etc. (exact list UNKNOWN) | — | Restrict specific file types | S15 — Grade B |
| Sensitive Data Detection (Inline DLP) | Toggle | No | Disabled | Enabled/Disabled | Requires Enterprise DLP integration | Activates real-time DLP scanning on transfers | S15 — Grade B |
| Malware Scan | Toggle | No | Unknown | Enabled/Disabled | — | Block transfers detected as malware | S15 — Grade B |
| Action on Match | Select | Yes | None | Block, Alert, Allow-with-log | — | What happens when restriction matches | E — Inferred from product capability |
| User Notification | Toggle | No | Unknown | Enabled/Disabled | — | Notify user when restriction triggers | Grade U — **ASSUMPTION** |

### Conditional Fields

When **Sensitive Data Detection** = Enabled: Enterprise DLP classifier configuration becomes active for isolation sessions. The DLP rules and classifiers used are managed in the Enterprise DLP platform (Proofpoint Data Security), not in the Isolation Console. [S15 — Grade B for feature; integration details Grade U — **ASSUMPTION**]

### Edge Cases

- Enabling malware scan may introduce latency for large file downloads depending on scan engine throughput. [Grade U — **ASSUMPTION**]
- If Sensitive Data Detection is enabled but Enterprise DLP integration is not configured, behavior (fail-open vs fail-closed) is UNKNOWN. [Grade U — **ASSUMPTION**]

---

## Screen: Isolation Console > Policies > User Input Controls (Sub-capability 11.6)

**Navigation:** INCOMPLETE
**Purpose:** Dynamically limit what users can type into web forms during isolation sessions. Primary use case: prevent corporate credential entry on phishing/impersonation sites that are being isolated rather than blocked.
**Source:** S15 — Grade B ("dynamic limits on form input to prevent credential theft")

### Fields

| Field | Type | Required | Default | Options | Validation | Description | Source |
|-------|------|----------|---------|---------|------------|-------------|--------|
| Control Name | Text | Yes | None | Free text | Non-empty | Internal identifier | E — Inferred |
| Input Restriction Type | Select | Yes | Unknown | Read-Only (no input), Controlled (limited), Full (unrestricted) (options UNCONFIRMED) | — | Level of form input restriction | Grade U — **ASSUMPTION** |
| Target Scope | Select/Text | No | All isolated sites | URL, URL category, or all isolated sessions | — | Which sites this control applies to | E — Inferred from S15 |
| Credential Pattern Detection | Toggle | No | Unknown | Enabled/Disabled | — | Detect credential-style entries and warn or block | Grade U — **ASSUMPTION** |
| User Warning Message | Text | No | None | Custom message | — | Message shown to user when input is restricted | Grade U — **ASSUMPTION** |

---

## Sub-capability 11.4: TAP URL Isolation Integration

**Navigation:** TAP Dashboard settings + Isolation Console VIP/VAP management
**Purpose:** Configure TAP to send URL clicks from VIP/VAP users to the Isolation container instead of the user's local browser.
**Source:** S15 — Grade B; Video 17 — Grade C (~1:30 timestamp)

This sub-capability involves configuration in two products:

**In the TAP Dashboard (Email Protection console):**
- Enable URL Isolation for target user groups (exact field names UNKNOWN — TAP config behind auth wall)
- TAP Dashboard can be accessed to view and export the current VAP list [Video 15 — Grade C]

**In the Isolation Console:**
- Import the VAP list from TAP (manual process — does NOT auto-sync) [S15 — Grade B; Video 17 — Grade C]
- Apply a strict browsing policy to the imported VAP group
- Any TAP-rewritten URL clicked by a VAP is intercepted and rendered in isolation

**Critical limitation:** The VAP list is static until manually re-imported. See [gotchas.md G1](gotchas.md).

---

## Sub-capability 11.5: Inline DLP for Isolation Sessions

**Navigation:** Enabled within Upload/Download Restriction policy (no separate screen documented)
**Purpose:** Apply Enterprise DLP classification to file transfers occurring in isolated sessions.
**Source:** S15 — Grade B ("inline real-time DLP for uploads/downloads")

### Integration architecture

```
Isolation Container
    → User uploads file
    → Upload/Download Restriction policy detects upload
    → Sensitive Data Detection = Enabled
    → Content sent to Enterprise DLP engine for classification
    → DLP rule match: action applied (block / alert / allow)
    → Isolation Console shows alert event
```

**Prerequisites for this sub-capability:**
1. Enterprise DLP platform (Proofpoint Data Security) active with defined detection rules [S10 — Grade A; cross-reference]
2. Isolation <> Enterprise DLP integration configured (integration config screen UNKNOWN — INCOMPLETE)
3. Upload/Download Restriction policy with Sensitive Data Detection enabled (Step 4 in workflow.md)

---

## Sub-capability 11.7: VIP/VAP List Import from TAP

**Navigation:** Isolation Console > Users / VIP-VAP (exact path UNKNOWN)
**Purpose:** Identify high-risk users from TAP data and apply stricter isolation policies to them.
**Source:** S15 — Grade B; Video 17 — Grade C

### Process

| Step | Action | Notes | Source |
|------|--------|-------|--------|
| 1 | Review TAP Dashboard VAP list | Identify currently Most Attacked People | Video 15 — Grade C |
| 2 | Export VAP list from TAP Dashboard | Export format UNKNOWN | S15 — Grade B ("import" wording implies export step) |
| 3 | Navigate to Isolation Console VIP/VAP section | Exact navigation UNKNOWN | S15 — Grade B |
| 4 | Import VAP list | File format UNKNOWN | S15 — Grade B |
| 5 | Import VIP list from Proofpoint User Center | For executive users who may not be on VAP list | S15 — Grade B |
| 6 | Assign strict browsing policy to VIP/VAP group | Use more restrictive Access Level than standard users | E — Inferred from S15 per-group policy architecture |
| 7 | Re-import after next TAP threat review | VAP roster changes over time | Video 17 ~1:30 — Grade C |

---

## Version Notes

| Product Generation | Notes | Source |
|-------------------|-------|--------|
| TAP Browser Isolation (2019) | Original integration within TAP suite; Video 17 reflects this era | Video 17 — Grade C |
| Proofpoint Isolation (2022+) | Rebranded as standalone product; Video 18 reflects current state; UI may differ from Video 17 | Video 18 — Grade C |
| Isolation data sheet (Aug 2023) | Current capabilities documented in S15 | S15 — Grade B |
