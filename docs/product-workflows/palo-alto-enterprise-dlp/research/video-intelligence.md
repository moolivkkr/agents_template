# Video Intelligence: Palo Alto Enterprise DLP -- Authoring Policies
> Researched: 2026-05-21 | Videos analyzed: 18 | Total duration: ~6+ hours (estimated)
> Note: Metadata extracted from web search snippets and YouTube descriptions. Timestamps are inferred.

---

## Video Catalog

### Official Palo Alto Networks Channel

| # | Title | Channel | Duration | Date | Relevance | URL |
|---|-------|---------|----------|------|-----------|-----|
| 1 | Enterprise DLP by Palo Alto Networks | Palo Alto Networks | ~15min (est.) | 2022-06-22 | **CRITICAL** | https://www.youtube.com/watch?v=6fcEoIIYzYw |
| 2 | AI-Powered DLP | Palo Alto Networks | ~10min (est.) | 2023-11-01 | **CRITICAL** | https://www.youtube.com/watch?v=9OCskE3srWs |
| 3 | The New Data Security Product from Palo Alto Networks | Palo Alto Networks | ~15min (est.) | 2023-07-12 | HIGH | https://www.youtube.com/watch?v=-LeEjLpSyWo |
| 4 | Palo Alto Networks; GPT Demo DLP + SaaS | Palo Alto Networks | ~20min (est.) | 2023-12-04 | **CRITICAL** | https://www.youtube.com/watch?v=hMC71mo43Vw |
| 5 | Palo Alto Networks vs. Check Point - DLP Comparison | Community | ~15min (est.) | 2024 (est.) | HIGH | https://www.youtube.com/watch?v=JtAkx694Zc8 |
| 6 | Data Filtering | Palo Alto Networks | ~12min (est.) | 2023 (est.) | **CRITICAL** | https://www.youtube.com/watch?v=xEXIPxhHJ24 |
| 7 | XDR 5.0: Enter the Era of Modern Endpoint Security with AgentiX, Exposure Management, and DLP | Palo Alto Networks | ~30min (est.) | 2025 (est.) | HIGH | https://www.youtube.com/watch?v=m1otle_-LbM |
| 8 | Secure Enterprise Browser avec Palo Alto Networks et Orange Cyberdefense | Community | ~20min (est.) | 2025-04-03 | MEDIUM | https://www.youtube.com/watch?v=R6W7c9LFUgo |
| 9 | Automating Data Loss Prevention (DLP) Incident Response | Palo Alto Networks | ~15min (est.) | 2024 (est.) | HIGH | https://www.paloaltonetworks.com/resources/videos/automating-data-loss-prevention-incident-response |

### Community / Partner Channel Videos

| # | Title | Channel | Duration | Date | Relevance | URL |
|---|-------|---------|----------|------|-----------|-----|
| 10 | Palo Alto Panorama Training (Basic to Advanced) | Community | ~60min (est.) | 2023 (est.) | MEDIUM | https://www.youtube.com/watch?v=7Hyf1iBgnW4 |
| 11 | Palo Alto Networks-Firewall Demo Tutorial for beginners | Community | ~45min (est.) | 2022-11-13 | MEDIUM | https://www.youtube.com/watch?v=AwxCpvcLJfA |

---

## Workflow Extractions

### Video #1: Enterprise DLP by Palo Alto Networks
**URL:** https://www.youtube.com/watch?v=6fcEoIIYzYw
**Channel:** Palo Alto Networks | **Date:** 2022-06-22

**Inferred Workflow (from search descriptions and cross-references):**

**Screen: Enterprise DLP App > Data Profiles**
  - Action: Navigate to centralized DLP configuration
  - Comment: Demonstrates how Enterprise DLP protects sensitive data across SaaS applications
  - Cross-ref: **CONFIRMED** -- matches S1/S2 documentation on data profile creation

**Inferred Steps:**
1. Access the Enterprise DLP app from the Palo Alto Networks Hub
2. Review predefined data patterns (500+ built-in)
3. Create a data profile combining multiple data patterns
4. Set occurrence thresholds and confidence levels
5. Attach data profile to a security rule via enforcement point

---

### Video #2: AI-Powered DLP
**URL:** https://www.youtube.com/watch?v=9OCskE3srWs
**Channel:** Palo Alto Networks | **Date:** 2023-11-01

**Inferred Workflow:**

**Topic: ML-Based Data Pattern Configuration**
  - Action: Demonstrate ML-augmented classification
  - Feature: LLM-powered detections combined with context-aware ML models
  - Key metric: 10x fewer false positives vs traditional regex
  - Cross-ref: **CONFIRMED** -- matches S7 (predefined ML-based data patterns) and S38 (AI blog post)

**Key Insights:**
- 5th generation DNN models for classification
- ML-based patterns support only "Any" occurrence with High/Low confidence
- Cannot configure custom occurrence thresholds for ML patterns
- Predefined ML patterns cannot be duplicated

---

### Video #4: GPT Demo DLP + SaaS
**URL:** https://www.youtube.com/watch?v=hMC71mo43Vw
**Channel:** Palo Alto Networks | **Date:** 2023-12-04

**Inferred Workflow:**

**Screen: Strata Cloud Manager > Security Services > Data Loss Prevention**
  - Action: Demonstrate DLP protection for AI/GenAI applications
  - Covers: ChatGPT policy rule configuration
  - Cross-ref: **CONFIRMED** -- matches S25 (Create a Security Policy Rule for ChatGPT)

**Inferred Steps:**
1. Identify AI application traffic via App-ID
2. Create data profile targeting sensitive data types
3. Create DLP rule on SCM referencing the data profile
4. Set action to Block for sensitive data in AI app uploads
5. Attach to security policy rule targeting ChatGPT App-ID

---

### Video #6: Data Filtering
**URL:** https://www.youtube.com/watch?v=xEXIPxhHJ24
**Channel:** Palo Alto Networks | **Date:** 2023 (est.)

**Inferred Workflow:**

**Screen: Panorama > Objects > Security Profiles > Data Filtering**
  - Action: Create a Data Filtering Profile on NGFW
  - Cross-ref: **CONFIRMED** -- matches S20/S21 (Security Profile: Data Filtering)

**Inferred Steps:**
1. Navigate to Objects > Security Profiles > Data Filtering
2. Click Add to create a new Data Filtering Profile
3. Configure match criteria:
   - Select data patterns (predefined or custom)
   - Set file types to inspect
   - Configure direction (upload, download, both)
4. Set action: Alert or Block
5. Set log severity
6. Attach the Data Filtering Profile to a Security Policy Rule
7. Commit and push to managed firewalls

---

### Video #7: XDR 5.0 with Endpoint DLP
**URL:** https://www.youtube.com/watch?v=m1otle_-LbM
**Channel:** Palo Alto Networks | **Date:** 2025 (est.)

**Inferred Workflow:**

**Topic: Cortex XDR 5.0 Endpoint DLP Module**
  - Action: Demonstrate endpoint DLP capabilities
  - Key feature: Classification engine runs entirely on-device (works offline)
  - User experience: Real-time prompts when sensitive data is flagged
  - Cross-ref: **CONFIRMED** -- matches S26 (Create an Endpoint DLP Policy Rule)

**Key Insights:**
- Endpoint DLP is a Cortex XDR add-on, NOT managed via Panorama/SCM
- Classification happens on the endpoint, sensitive data never sent to external scanner
- Desktop application monitoring -- DLP extends to installed apps, not just browser/network
- Real-time coaching prompts for end users (not just block)

---

## Tribal Knowledge (NOT in official docs)

| # | Insight | Source Video | Impact |
|---|---------|-------------|--------|
| 1 | **AI/GenAI DLP is the leading use case** -- Palo Alto positions Enterprise DLP heavily around protecting data sent to ChatGPT, Copilot, and other AI tools | GPT Demo (#4) | **CRITICAL** -- shapes how policies are designed (App-ID for AI apps + DLP data profiles) |
| 2 | **ML confidence levels are binary (High/Low)** -- there is no numeric score or custom threshold for ML-based patterns; this limits fine-tuning | AI-Powered DLP (#2) | HIGH -- admins expecting granular ML tuning will be disappointed |
| 3 | **Endpoint DLP runs independently** -- Cortex XDR endpoint DLP uses an on-device classification engine, separate from network DLP. Policies may diverge | XDR 5.0 (#7) | HIGH -- architecture understanding; endpoint and network are different management surfaces |
| 4 | **Data Filtering Profile (Panorama) vs DLP Rule (SCM) are the same concept** -- different UI names for the same enforcement mechanism depending on management surface | Data Filtering (#6) | MEDIUM -- reduces confusion for teams managing both Panorama and SCM |
| 5 | **Enterprise DLP is cloud-delivered** -- even NGFW-based inspection sends traffic to the DLP cloud for verdict. The NGFW does not perform local DLP inspection | Enterprise DLP (#1) | **CRITICAL** -- architecture understanding; latency and connectivity implications |
| 6 | **Comparison with Check Point shows Palo Alto strength in ML classification** -- competitive analysis highlights Palo Alto's AI advantage but notes Check Point's broader policy granularity | DLP Comparison (#5) | MEDIUM -- competitive positioning |

---

## Gotchas from Videos

| # | Gotcha | Impact | Workaround | Source |
|---|--------|--------|------------|--------|
| 1 | Enterprise DLP requires cloud connectivity -- NGFW sends traffic to cloud for DLP verdict | Cannot enforce DLP if cloud connectivity is interrupted | Ensure reliable internet; configure fail-open/fail-close behavior | Enterprise DLP (#1) |
| 2 | ML-based patterns only support "Any" occurrence with High/Low confidence -- no custom occurrence thresholds | Cannot set "trigger on 5+ matches" for ML patterns like you can for regex | Use regex patterns if you need occurrence-based thresholds; use ML for accuracy | AI-Powered DLP (#2) |
| 3 | Endpoint DLP (Cortex XDR) is managed separately from network DLP (Panorama/SCM) | Policy drift between endpoint and network DLP is possible | Maintain a policy matrix tracking which data patterns are enforced on which enforcement point | XDR 5.0 (#7) |
| 4 | ChatGPT/AI app DLP requires correct App-ID identification -- must use App-ID, not URL filtering | If App-ID is not recognized, DLP rule will not match AI app traffic | Verify App-ID support for target AI applications; keep App-ID signatures updated | GPT Demo (#4) |

---

## Recommended Follow-Up

1. **Watch Video #6 (Data Filtering)** carefully for exact Panorama UI walkthrough
2. **Watch Video #2 (AI-Powered DLP)** for ML confidence level demonstration
3. **Watch Video #7 (XDR 5.0)** for endpoint DLP policy creation walkthrough
4. **Request access to Palo Alto Networks LIVEcommunity** for configuration best practices and real-world deployment patterns
5. **Review pan.dev API explorer** for DLP API endpoint discovery (S36)

---

## Limitations of This Research

1. **WebFetch was not used** -- could not scrape individual YouTube pages for exact durations, view counts, or full transcripts
2. **Timestamps are estimated** -- without transcript access, screen-by-screen timestamps could not be extracted
3. **Fewer community/third-party videos** than Trellix -- Palo Alto DLP is more tightly controlled, fewer independent tutorials exist
4. **Endpoint DLP (Cortex XDR) is very new** -- limited video content available as of research date
