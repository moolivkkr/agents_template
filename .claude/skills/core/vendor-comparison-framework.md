# Vendor & Open-Source Comparison Framework

## Purpose

Structured taxonomy for evaluating software products against vendors and open-source alternatives. Goes beyond feature checklists into architecture, economics, viability, and strategic fit. Used by research agents during Step 1 (Market Landscape) and Step 2 (Capability Matrix).

## 18 Evaluation Dimensions

---

### 1. Functional Capabilities

- **Core feature coverage** — map vendor capabilities to domain taxonomy. Use Full / Partial / Gap / Roadmap labels, not binary yes/no.
- **Capability depth vs. breadth** — does vendor do 10 things shallowly or 3 deeply?
- **Differentiated capabilities** — what does each do that others don't? Genuine moats vs. commodity.
- **Roadmap maturity** — classify as DEPLOYED / ANNOUNCED / ROADMAP. Vendors sell futures as present-state.

### 2. Architecture & Technical Design

- **Deployment model** — SaaS, self-hosted, hybrid, air-gapped
- **Control plane vs. data plane separation** — unified or bolted-together?
- **Multi-tenancy model** — single-tenant, pooled, siloed. Affects blast radius and isolation.
- **Scalability** — endpoints supported, throughput, latency P50/P95/P99, horizontal vs. vertical limits
- **Data residency & sovereignty** — where stored, processed, replicated
- **Extensibility** — plugins, webhooks, rules engines, SDK, IaC support (Terraform, Pulumi)
- **API surface** — REST/gRPC/GraphQL, completeness (API parity with UI?), rate limits, versioning

### 3. Integration & Ecosystem Fit

- **Native integrations** — count and quality with your existing stack
- **Standards support** — OTEL, OpAMP, OpenAPI, OCSF, STIX/TAXII, SPIFFE, OIDC, SAML, SCIM, FIDO2
- **Data portability** — export formats, schema docs, lock-in risk
- **Workflow integration** — Slack/Teams, PagerDuty, Jira/ServiceNow, Git-based config
- **Identity integration** — IdP support, SCIM provisioning, RBAC/ABAC granularity, JIT access

### 4. Security & Compliance

- **Compliance certifications** — SOC 2 Type II, ISO 27001, FedRAMP, HIPAA, PCI-DSS, HITRUST. Verify currency.
- **Cryptographic posture** — FIPS 140-3 validation, post-quantum readiness, TLS versions, key management
- **Supply chain security** — SBOM availability, signing (Sigstore, in-toto), SLSA level, dependency hygiene
- **Vulnerability history** — CVE track record, MTTR on disclosed vulns, advisory cadence
- **Tenant isolation guarantees** — cross-tenant attack history
- **Auditability** — immutable logs, retention, tamper evidence, who-did-what-when granularity

### 5. Operational Characteristics

- **Observability** — metrics, logs, traces; OTEL-native or proprietary; dashboard quality
- **Reliability** — SLA tier, historical uptime, regional failover, DR RPO/RTO
- **Upgrade model** — rolling, blue/green, maintenance windows; agent upgrade story
- **Day-2 operations** — backup/restore, config management, policy-as-code, drift detection
- **Incident response** — vendor's IR process; customer notification SLAs

### 6. Total Cost of Ownership (TCO)

- **Licensing model** — per-endpoint, per-user, per-GB, per-API-call, capacity-based
- **Implementation cost** — professional services, integration engineering, training
- **Operational cost** — FTEs to run it (a "free" OSS tool needing 3 SREs > $500K SaaS)
- **Infrastructure cost** — compute, storage, egress (often hidden)
- **Hidden costs** — premium support, sandboxes, connectors, AI/ML add-ons
- **Exit cost** — data migration, retraining, contract penalties
- **3-year and 5-year TCO** — vendors discount Year 1 then escalate. Model full term.

### 7. Vendor Viability & Risk

- **Financial health** — funding stage, runway, profitability, public filings
- **Customer base** — logos, reference customers in your industry/size, churn signals
- **Acquisition risk** — likely acquired? By whom? Product fate?
- **Strategic alignment** — core to vendor or sidecar they'll deprecate?
- **Executive stability** — CEO/CTO/CISO turnover
- **Geopolitical exposure** — country of origin, data flows, export controls, sanctions

### 8. Open-Source Specific

- **License type** — permissive (Apache 2.0, MIT) vs. copyleft (GPL, AGPL) vs. source-available (BSL, SSPL, ELv2). AGPL/source-available impact SaaS deployment.
- **Governance model** — foundation-backed (CNCF, Apache, LF) vs. single-vendor OSS vs. community. Single-vendor carries relicensing risk (HashiCorp, Elastic, Redis precedents).
- **Community health** — contributors, diversity (bus factor), commit frequency, issue response, PR merge rate
- **Commercial support** — enterprise edition, third-party support, self-support ability
- **Fork risk** — has it been forked? OpenSearch, OpenTofu, Valkey are object lessons.
- **Security posture** — CVE response, security team, OpenSSF Scorecard rating
- **Trademark** — can you redistribute, rebrand, offer as a service?

### 9. Developer & User Experience

- **Time to first value** — install to working result
- **Documentation quality** — completeness, accuracy, examples, API reference, runbooks
- **Learning curve** — for operators, admins, end users
- **UI/UX quality** — subjective but drives adoption
- **Local development story** — can a dev run it on a laptop?
- **Error messages and debuggability** — difference between tool people use and one they avoid

### 10. Support & Services

- **Support tiers** — response SLAs by severity, follow-the-sun, named TAM
- **Professional services** — availability, quality, cost, knowledge transfer
- **Training** — certifications, courses, on-site
- **Community** — forums, Slack/Discord, conferences
- **Customer success** — proactive vs. reactive, QBRs

### 11. AI/ML Considerations (if relevant)

- **Model transparency** — what models, where they run, what data trains them
- **Data usage for training** — is your data used? Opt-out?
- **Inference latency and throughput** — inline enforcement paths
- **Explainability** — why did the model flag something?
- **Bring-your-own-model** — can you swap in your own SLM?
- **Adversarial robustness** — evasion, prompt injection, embedding attacks

### 12. Strategic Fit

- **Build vs. buy vs. blend** — replace, augment, or duplicate?
- **Lock-in profile** — data, schema, skills lock-in
- **Partnership potential** — joint roadmap, design partner status, influence
- **Cultural fit** — does the vendor operate like you do?

---

## Market & GTM Dimensions (13-18)

### 13. Market Sizing & Opportunity

- **TAM** — total annual global spend. Top-down (analyst) cross-checked with bottom-up (unit economics × buyers). Cite year + growth rate.
- **SAM** — realistic slice given geography, segment, regulatory, deployment model. Usually 30-40% of TAM.
- **SOM** — realistically capturable in 3-5 years. 1-5% of SAM for new entrant; 10-20% for incumbent.
- **CAGR** — segment-specific, not aggregate. Growth hides in averages.
- **Market maturity** — emerging / growth / mature / declining. Maps to Gartner Hype Cycle.
- **Adjacent expansion** — natural Land → Expand path.
- **Market structure** — fragmented (ripe for consolidation) vs. concentrated (top 3 own 60%+).

### 14. Competitive Landscape & Leaders

- **Market leaders** — top 3-5 by revenue AND mindshare (often different). Gartner MQ, Forrester Wave, IDC as starting points. Verify revenue independently (10-K, PitchBook).
- **Market share distribution** — HHI index. >2500 = concentrated; <1500 = competitive.
- **Challenger/visionary movement** — YoY trajectory matters more than current position.
- **New entrants** — Series B/C startups. Real future competitors, not current leaders.
- **OSS disruptors** — projects with commercial backing that reset pricing floors.
- **Hyperscaler encroachment** — AWS/Azure/GCP commoditizing from below.
- **Platform consolidators** — who's absorbing adjacent categories.
- **Recent M&A** — last 24 months. Signals strategic value and talent concentration.

### 15. Customer Acquisition Economics

- **CAC** — fully loaded sales + marketing ÷ new customers. Enterprise: $50K-$500K+; SMB SaaS: $1K-$10K.
- **CAC by channel** — direct, channel/VAR, marketplace, PLG, partner. Different economics per channel.
- **CAC payback** — months of gross margin to recover. Best: <12mo. Acceptable: 12-24mo. Concerning: >24mo.
- **LTV/CAC** — >3:1 healthy; >5:1 underinvesting in growth; <1:1 broken.
- **Conversion funnel** — TAM → aware → lead → qualified opp → close. Enterprise security: lead→opp ~10-20%, opp→close ~15-25%.
- **Penetration scenarios** — model 0.5% / 1% / 2% / 5% of SAM at realistic ACV.
  - Example: $50B SAM × 1% = $500M ARR → at $250K ACV = 2,000 customers → at 25% close = 8,000 opps → at 15% qual = ~53,000 leads needed.
- **Sales cycle** — SMB days/weeks, mid-market months, enterprise 6-18mo, federal 12-24+.
- **ACV bands** — SMB / mid-market / enterprise / strategic distribution.
- **NRR** — expansion - churn. >120% best-in-class; >100% bar; <100% leaky bucket.
- **Logo vs. dollar retention** — small customers churn at higher logo rates but low dollar impact.

### 16. Go-to-Market Motion

- **Primary GTM** — sales-led, PLG, channel-led, community-led, marketplace-led
- **Buyer persona** — CISO, CIO, security architect, SOC director, DevSecOps. Different buyers = different cycles.
- **Buying committee** — enterprise security averages 7-10 stakeholders
- **Procurement path** — direct, marketplace (compresses cycles 40-60%), GSA, channel
- **Pricing model** — per-seat, per-endpoint, per-GB, capacity, outcome-based. Match customer value measurement.
- **Free/freemium/OSS funnel** — works for dev tools; rarely for enterprise security
- **Marketing motion** — content/SEO, events, analyst relations, paid, ABM, community
- **Time to value (TTV)** — PoC complexity kills deals; 6-week PoC = high attrition

### 17. Strategic Positioning & Differentiation

- **Differentiation thesis** — what you do that incumbents structurally cannot (architecture, biz model, org prevents copying)
- **Defensibility moats** — data network effects, switching costs, integration depth, certs, brand, talent
- **Wedge strategy** — narrow 10x-better entry point, then expand
- **Platform vs. point** — point: easier to sell, harder to defend. Platform: harder to sell, harder to displace.
- **Anti-thesis** — strongest argument AGAINST your approach. If you can't articulate it, you haven't stress-tested.

### 18. Analyst & Industry Validation

- **Analyst coverage** — Gartner, Forrester, IDC, 451, GigaOm. Coverage gates enterprise procurement.
- **MQ/Wave/MarketScape positioning** — current and trajectory
- **Reference architecture** — NIST, CISA, MITRE, cloud provider inclusion
- **Recognition** — RSA Innovation Sandbox, Black Hat, CNCF graduation
- **Customer references** — named logos, peer reviews (Gartner Peer Insights, G2, TrustRadius). Quality > quantity.

---

## Output Format

### Coverage Matrix
Capabilities × vendors with Full / Partial / Gap / Roadmap labels + evidence column (link to docs/demo, NOT marketing).

### Claim Classification (CRITICAL)
Every claim must be classified:
- **Vendor-stated** — from marketing or sales materials
- **Independently-verified** — confirmed via docs, demo, or testing
- **Customer-reference-verified** — confirmed by named customer

### Weighted Scoring
Assign weights by priority (e.g., PCI-critical → Compliance weighs more than UX).

### Risk Register
Vendor-specific risks (financial, acquisition, lock-in) tracked separately from feature gaps.

### 3-Year TCO Model
Fully loaded including FTE costs.

### Decision Memo
Recommendation with explicit trade-offs, not sanitized "winner."

---

## Penetration Decomposition Template

When modeling market capture scenarios:

1. **Anchor to SAM, not TAM** — 1% of TAM is usually nonsensical
2. **Decompose the path:**
   - SAM × capture% = target ARR
   - ÷ ACV = customers needed
   - ÷ close rate = qualified opps needed
   - ÷ qualification rate = leads needed
   - ÷ rep quota = reps needed
   - × 2 (SE coverage + support) = customer-facing FTE
   - × 1.8 = total FTE
3. **The binding constraint is usually hiring and org management**, not market demand

---

## When to Apply Which Dimensions

| Research Context | Use Dimensions |
|---|---|
| SaaS/enterprise product | All 18 |
| Developer tool / OSS | 1-5, 8-9, 13-14, 17 |
| Internal tool | 1-5, 9, 12 |
| Consumer product clone | 1, 2, 9, 13-14 |
| API/infrastructure | 1-3, 5-6, 8-9 |
