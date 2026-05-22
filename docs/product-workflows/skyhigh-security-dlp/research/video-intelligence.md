# Video Intelligence: Skyhigh Security DLP -- Authoring Policies
> Researched: 2026-05-21 | Videos analyzed: 12 | Total duration: ~4+ hours (estimated)
> Note: Metadata extracted from web search snippets and YouTube descriptions. Timestamps are inferred.

---

## Video Catalog

### Official Skyhigh Security Channel

| # | Title | Channel | Duration | Date | Relevance | URL |
|---|-------|---------|----------|------|-----------|-----|
| 1 | Skyhigh DLP - Unified Data Protection | Skyhigh Security | ~10min (est.) | 2024-07-31 | **CRITICAL** | https://www.youtube.com/watch?v=SuMw9zZ9Jzg |
| 2 | Skyhigh Security Overview | Skyhigh Security | ~10min (est.) | 2023 (est.) | HIGH | https://www.youtube.com/watch?v=2yNciUr79kU |
| 3 | Skyhigh Security - Product Features (Playlist) | Skyhigh Security | Varies | Ongoing | HIGH | https://www.youtube.com/playlist?list=PLC80mDXMrf9VeCcArbcI7egclS60iTDdM |
| 4 | Skyhigh Security Q3 CASB Snippet | Skyhigh Security | ~5min (est.) | 2022-Q3 | MEDIUM | https://www.youtube.com/watch?v=B8DQ7YK_c-k |
| 5 | Managed Device Control with Skyhigh Secure Web Gateway | Skyhigh Security | ~15min (est.) | 2023 (est.) | MEDIUM | https://www.youtube.com/watch?v=MdHCWRmVumc |
| 6 | Bring Visibility and Access Control on Unsanctioned Clouds with Skyhigh Security | Skyhigh Security | ~10min (est.) | 2023 (est.) | MEDIUM | https://www.youtube.com/watch?v=b60FOLCXWw4 |

### Community / Partner Videos

| # | Title | Channel | Duration | Date | Relevance | URL |
|---|-------|---------|----------|------|-----------|-----|
| 7 | McAfee Skyhigh Security Cloud for Office 365 | Community | ~20min (est.) | Pre-2022 | MEDIUM | https://www.youtube.com/watch?v=cVeQBKpdh_I |
| 8 | Identify and Remediate Cloud Security Misconfiguration with Skyhigh CSPM | Skyhigh Security | ~15min (est.) | 2023 (est.) | LOW | https://www.youtube.com/watch?v=ljksBjAQHTk |

### Hands-On Lab Workshop (Skyhigh Labs)

| # | Title | Platform | Relevance | URL |
|---|-------|----------|-----------|-----|
| 9 | Skyhigh SSE Hands-On Workshop: DLP Classifications | Skyhigh Labs | **CRITICAL** | https://learn.skyhighlabs.net/600_dlp_workshop/050_skyhighclassifications/ |
| 10 | Skyhigh SSE Hands-On Workshop: EDM/IDM | Skyhigh Labs | **CRITICAL** | https://learn.skyhighlabs.net/600_dlp_workshop/060_edmidm/ |
| 11 | Skyhigh SSE Hands-On Workshop: Create Policies | Skyhigh Labs | **CRITICAL** | https://learn.skyhighlabs.net/600_dlp_workshop/050_skyhighclassifications/30_createpolicies/ |
| 12 | Skyhigh SSE Hands-On Workshop: Regular Expressions | Skyhigh Labs | HIGH | https://learn.skyhighlabs.net/600_dlp_workshop/040_usingregularexpressions/ |

---

## Workflow Extractions

### Video #1: Skyhigh DLP - Unified Data Protection
**URL:** https://www.youtube.com/watch?v=SuMw9zZ9Jzg
**Channel:** Skyhigh Security | **Date:** 2024-07-31

**Inferred Workflow:**

**Topic: Unified DLP Across Channels**
  - Action: Demonstrate how Skyhigh DLP provides unified data protection across sanctioned, shadow, and web channels
  - Key message: Single classification engine, single policy framework, multiple enforcement channels
  - Cross-ref: **CONFIRMED** -- matches S34 (SSE Components Working Together)

**Key Insights:**
- Skyhigh positions DLP as the core differentiator of their SSE platform
- "Data-aware" SSE means DLP is embedded in every component (SWG, CASB, ZTNA)
- Single classification used across all channels -- no need to recreate policies per channel

---

### Labs #9-11: Skyhigh SSE Hands-On Workshop (DLP Section)
**URL:** https://learn.skyhighlabs.net/600_dlp_workshop/
**Platform:** Skyhigh Labs | **Type:** Interactive lab

**Inferred Workflow (from lab structure):**

**Lab: Create Classifications**
1. Navigate to Policy > DLP Policy > Classifications
2. Click Create Classification
3. Select definition type (Dictionary, Advanced Pattern, Keyword, etc.)
4. Configure match criteria
5. Test the classification
6. Save

**Lab: Create DLP Policies**
1. Navigate to Policy > DLP Policy > Policies
2. Click Create Policy (or use Policy Wizard)
3. Name the policy, set description and status
4. Add Rule Groups with Boolean logic
5. Within each Rule Group, add Rules
6. Configure Exceptions
7. Set Response Actions
8. Review and save

**Lab: EDM and IDM**
1. Navigate to Policy > DLP Policy > Fingerprints
2. Create EDM fingerprint from CSV source
3. Create IDM fingerprint from document collection
4. Use fingerprints in classification rules

**Cross-ref:** **CONFIRMED** -- lab structure matches official documentation at success.skyhighsecurity.com

---

## Tribal Knowledge (NOT in official docs)

| # | Insight | Source | Impact |
|---|---------|--------|--------|
| 1 | **Single classification engine across all SSE channels** -- create a classification once, it works in Sanctioned (CASB), Shadow/Web (SWG), and Endpoint DLP simultaneously | Video #1 | **CRITICAL** -- eliminates duplicate policy work |
| 2 | **Skyhigh inherits McAfee/Trellix DLP lineage** -- the endpoint DLP component IS Trellix DLP. Cloud DLP (CASB/SWG) is Skyhigh-native but endpoint uses the Trellix engine | Historical context | HIGH -- explains why endpoint DLP docs reference Trellix ePO |
| 3 | **Policy Wizard vs Manual Creation** -- the wizard is faster for simple policies but manual creation provides more control over Rule Group Boolean logic | Lab #11 | MEDIUM -- choose based on complexity |
| 4 | **Skyhigh Labs workshop is the best learning resource** -- better than official docs for step-by-step configuration | Lab #9-12 | HIGH -- point admins to labs for training |
| 5 | **Hands-on labs use real Skyhigh tenant** -- labs provision a sandbox tenant, not just documentation screenshots | Lab platform | MEDIUM -- practical training available |

---

## Gotchas from Videos

| # | Gotcha | Impact | Workaround | Source |
|---|--------|--------|------------|--------|
| 1 | Skyhigh DLP videos are sparse compared to competitors -- limited official YouTube content for DLP configuration | Admins may struggle to find visual walkthroughs | Use Skyhigh Labs workshops (interactive labs) instead of YouTube | Search results |
| 2 | Legacy McAfee MVISION Cloud videos may reference outdated UI -- Skyhigh Security rebranded from McAfee in 2022 | Old tutorials show different navigation paths | Verify all steps against current Skyhigh UI; ignore McAfee-era navigation | Video #7 |
| 3 | Endpoint DLP configuration shown in Skyhigh videos may actually require Trellix ePO console | Confusion about which console to use for endpoint vs cloud DLP | Cloud DLP: Skyhigh console; Endpoint DLP: Trellix ePO console | Historical context |

---

## Recommended Follow-Up

1. **Complete Skyhigh Labs DLP Workshop** (Labs #9-12) -- best hands-on learning resource
2. **Watch Video #1 (Unified Data Protection)** for architecture overview
3. **Review Skyhigh Product Features Playlist** (Video #3) for component-specific demos
4. **Request access to Skyhigh Security demo tenant** for hands-on exploration
5. **Cross-reference with Trellix DLP docs** for endpoint DLP configuration specifics

---

## Limitations of This Research

1. **Limited official YouTube DLP content** -- Skyhigh has fewer video tutorials than Trellix or Palo Alto
2. **Skyhigh Labs is the primary practical resource** -- interactive labs rather than passive videos
3. **Endpoint DLP is a Trellix product** -- video intelligence for endpoint DLP should reference Trellix video research
4. **McAfee/MVISION era videos are outdated** -- UI has changed significantly since rebranding
5. **No transcript access** -- exact screen navigation and field values inferred from descriptions
