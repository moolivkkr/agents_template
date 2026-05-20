# Business Objectives Patterns — Measurable OBJ-* That Drive Prioritization

## OBJ Anatomy (All Parts Required)

```
OBJ-NNN: [Goal Title]
  Goal:     [What outcome we want — one sentence]
  Metric:   [How we measure it — specific, queryable]
  Baseline: [Current value — "none" if greenfield]
  Target:   [Desired value — specific number]
  Timeline: [By when — quarter or date]
  Linked:   [Which FR-* requirements support this objective]
```

## Weak → Measurable Transformations

| Weak OBJ | Problem | Measurable OBJ |
|---|---|---|
| "Improve user engagement" | No metric, no baseline, no target | "Increase DAU/MAU ratio from 25% to 40% by Q3" |
| "Reduce churn" | No number | "Reduce 30-day churn from 12% to 6% by launch + 90 days" |
| "Faster onboarding" | What's fast? | "New user completes first task within 5 min (currently 20 min)" |
| "Better user experience" | Unmeasurable | "Increase task completion rate from 72% to 92% (measured via analytics)" |
| "Scale the platform" | Scale what? | "Support 10K concurrent users with p95 < 500ms (currently 500 users)" |
| "Increase revenue" | By how much? | "Achieve $50K MRR within 6 months of launch" |

## Linking FR-* to OBJ-*

Every FR-* should trace to at least one OBJ-*:

```
OBJ-001: Reduce onboarding time from 20 min to 5 min
  ├─ FR-001: Single-page registration (reduces steps)
  ├─ FR-002: Guided first-task wizard (reduces confusion)
  └─ FR-003: Pre-configured templates (reduces setup)

OBJ-002: Increase 30-day retention from 40% to 55%
  ├─ FR-010: Email reminders for incomplete tasks
  ├─ FR-011: Dashboard showing progress/value delivered
  └─ FR-012: Weekly summary email with activity highlights
```

**If an FR-* doesn't link to any OBJ-*:** Question whether it should be in scope.

## When to Split Objectives

If an OBJ has multiple independent metrics, split it:

```
# BAD — two metrics in one OBJ
OBJ-001: Improve engagement and reduce support costs

# GOOD — separate OBJs with own metrics
OBJ-001: Increase DAU/MAU ratio from 25% to 40%
OBJ-002: Reduce support tickets per user from 2.1/month to 0.8/month
```

## Measurement Validation

For each OBJ, verify:

```
□ Metric is queryable (can you write a SQL/analytics query for it?)
□ Baseline exists or is marked "greenfield — establish in first 30 days"
□ Target is ambitious but realistic (not 10x overnight)
□ Timeline is specific (Q3 2026, not "soon")
□ At least one FR-* supports this objective
□ No two OBJs have conflicting metrics
```

## Anti-Patterns

| Pattern | Problem | Fix |
|---------|---------|-----|
| "Make users happy" | Unmeasurable | NPS score, task completion rate, support ticket volume |
| OBJ with no timeline | Never verified | Add specific quarter or date |
| OBJ with no baseline | Can't measure improvement | Establish baseline in first 30 days or from analytics |
| All FR linked to one OBJ | OBJ is too broad | Split into sub-objectives |
| OBJ not linked to any FR | Objective without implementation | Either add FR-* or remove the OBJ |
