# Gap Analysis Checklist — 17 Dimensions for Requirement Completeness

## How to Use

For each dimension, ask: "Is this covered in the requirements?" If NO, categorize the gap:
- **Critical** — blocks BRD completion; must resolve before writing
- **Important** — reduces quality; should resolve, can defer with documented reason
- **Nice-to-have** — enhancement; defer to future version

## The 17 Dimensions

### Core (from brd_analyzer — always check)

| # | Dimension | Key Questions | Critical If Missing |
|---|-----------|--------------|---------------------|
| 1 | **Target Users / Actors** | Who uses it? How many persona types? | Yes — can't scope features |
| 2 | **Business Objectives** | Why build it? What's the measurable goal? | Yes — can't prioritize |
| 3 | **Scope Boundary** | What's explicitly OUT of scope? | Yes — scope creep guarantee |
| 4 | **Non-Functional Targets** | Performance, security, availability numbers? | Yes — can't verify "done" |
| 5 | **Error / Failure Handling** | What happens when things break? | Yes — silent failures |
| 6 | **External Integrations** | What third-party systems? Auth? Payments? | Yes — unknown dependencies |
| 7 | **Data Ownership** | Who owns the data? Retention? Deletion? | Important — legal risk |
| 8 | **Compliance** | GDPR, HIPAA, SOC2, PCI? | Depends on domain |
| 9 | **Rollout / Phasing** | MVP definition? Launch strategy? | Important — over-building |

### Extended (often missed — check these too)

| # | Dimension | Key Questions | Critical If Missing |
|---|-----------|--------------|---------------------|
| 10 | **Disaster Recovery** | Backup frequency? RTO/RPO? Failover? | Important for production |
| 11 | **Localization / i18n** | Multiple languages? RTL support? Date formats? | If international users |
| 12 | **Data Retention** | How long is data kept? Archival policy? Purge schedule? | Important — storage + compliance |
| 13 | **Deprecation** | How are features retired? API versioning? | If evolving product |
| 14 | **Third-Party Dependencies** | SLAs of dependencies? Fallback if down? | If using external APIs |
| 15 | **Audit Trail** | Who did what, when? Required for compliance? | If regulated domain |
| 16 | **Data Import/Export** | Can users bring data in? Take data out? | If replacing existing tool |
| 17 | **Rate Limiting** | Per-user limits? Per-tenant? API quotas? | If multi-tenant or public API |

## Gap Severity Heuristic

```
CRITICAL if:
  - Downstream agents cannot make implementation decisions without it
  - Multiple valid interpretations would lead to different architectures
  - Legal/compliance risk if undefined

IMPORTANT if:
  - Implementation can proceed with a reasonable assumption
  - The assumption is documented and can be validated later
  - Risk of rework is moderate (< 1 sprint)

NICE-TO-HAVE if:
  - Clearly a v2 concern
  - No current user impact
  - Can be added without architectural changes
```

## Domain-Specific Dimensions

### SaaS / Multi-Tenant
- Tenant isolation model (shared DB? schema per tenant? DB per tenant?)
- Tenant onboarding/offboarding flow
- Usage metering and billing integration
- White-labeling / branding per tenant

### E-Commerce
- Payment processing (Stripe? PayPal? PCI compliance scope)
- Inventory management (real-time stock? pre-orders?)
- Shipping integration (carrier APIs? tracking?)
- Returns/refunds policy and automation

### Internal Tools
- SSO / corporate auth integration
- Role hierarchy and permission model
- Data sensitivity classification
- Integration with existing internal systems (Slack, Jira, etc.)
