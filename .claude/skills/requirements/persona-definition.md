# Persona Definition Patterns — Sharp Personas That Drive Feature Scope

## Persona Anatomy (All 6 Parts Required)

```markdown
## Persona: [Name] — [Role Title]

**Primary Goal:** [One sentence — what they need to accomplish]
**Key Constraint:** [What limits them — time, skill, access, volume]
**Frequency:** [How often they use the system — daily, weekly, monthly]

### User Journeys (minimum 3)
1. [Most common task — the 80% use case]
2. [Secondary task — weekly or situational]
3. [Edge case task — rare but important]

### Needs (ranked)
1. [Most important capability]
2. [Second most important]
3. [Third]

### Frustrations
- [What annoys them about current solutions]
- [What wastes their time]

### Success Metric
[How this persona measures "the system works for me"]
```

## Weak vs Sharp Personas

### Weak (avoid)
```
Persona: User
Goal: Use the system
Needs: Everything works
```
**Problem:** Describes everyone, guides nothing. Cannot answer "would this persona use this feature?"

### Sharp (use)
```
Persona: Sarah — Operations Manager (5-person startup)
Primary Goal: Onboard new hires in < 30 minutes without IT help
Key Constraint: Non-technical, manages 3-8 hires/month, no dedicated HR
Frequency: Weekly during hiring, monthly otherwise

Journeys:
1. Invite new team member → set role → verify they can log in (10 min)
2. Update existing member's role when they change teams (2 min)
3. Off-board departing member → revoke access → export their data (5 min)

Needs:
1. Single-screen invite flow (email + role, that's it)
2. Bulk role changes (when team restructures)
3. Audit trail (who was given access when — for compliance)

Frustrations:
- Current tool requires 12 clicks to invite one person
- No way to see "who has access to what" in one view

Success Metric: New hire has working access within 15 minutes of starting
```

## The Persona Test

For every feature decision, ask:

> "Which specific persona needs this, and in which journey?"

- If you can answer → feature is justified
- If you can't → feature may be scope creep

Example:
- "Add dark mode" → Sarah doesn't care. Is there another persona who works in low-light? If not, defer.
- "Add bulk invite CSV upload" → Sarah needs this for the "3-8 hires/month" journey. Justified.

## When to Split by Persona

Same feature, different UX needs = separate requirements:

```
FR-015: View team members (Admin Sarah)
  → Full list with edit/remove actions, role management, audit trail

FR-016: View team members (Team Member Alex)
  → Read-only list, see who's on my team, no edit actions
```

Both view the same data, but the UI, permissions, and actions differ.

## Minimum Viable Persona Set

Every project needs at minimum:

| Persona Type | Why Required |
|---|---|
| **Primary user** | The person the product is built FOR |
| **Admin/power user** | Manages settings, users, permissions |
| **New/first-time user** | Onboarding experience, empty states |
| **External/limited user** | Guest, viewer, or API consumer (if applicable) |

## Anti-Patterns

| Pattern | Problem | Fix |
|---------|---------|-----|
| "The User" | Describes everyone, guides nothing | Split into 2-4 specific personas |
| Demographics only (age, location) | Irrelevant to feature decisions | Focus on goals, constraints, journeys |
| Too many personas (8+) | Can't prioritize; every feature "needed" | 3-5 max; merge similar ones |
| Persona without constraint | Can't make tradeoff decisions | Add the ONE thing that limits them |
| Same needs across personas | Personas aren't distinct | Differentiate by journey, not just title |
| Fictional persona not grounded in research | May not represent real users | Base on interviews, support tickets, analytics |
