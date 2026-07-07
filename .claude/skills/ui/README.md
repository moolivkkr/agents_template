---
skill: ui-standards-index
description: Index and strict precedence order for all UI skills — resolves conflicts by giving each UI skill one non-overlapping scope; UI agents read this first
version: "1.0"
tags:
  - ui-standards
  - precedence
  - index
  - navigation
  - ui
---

# UI Standards — Index & Precedence (READ THIS FIRST)

> **Single source of truth for "which UI rule wins."** There are many UI skills; without a stated
> order they appear to conflict (e.g. card radius: the portal design system says 14px, the generic
> standards say 12px). This index removes that ambiguity: it defines a strict **precedence order**
> and gives every UI skill ONE non-overlapping scope. Every UI agent (ux_designer, ui_developer,
> design_quality_reviewer) reads this first, then loads the skills in the order below.

---

## 1. Precedence order (highest wins on ANY conflict)

```
1. docs/PROJECT_FACTS.md + docs/DECISIONS.md        ← ground truth / settled decisions (always)
2. PROJECT DESIGN SYSTEM                             ← if one exists for this project
     .claude/skills/ui/vertix-portal-design-system.md  (Vertix portal modules)
3. docs/design/phases/N/specs/*.wireframe.{html,md}  ← the phase's concrete UI spec
4. GENERIC HOUSE STANDARDS                           ← professional-ui-standards.md (defaults only)
5. FRAMEWORK MECHANICS                               ← shadcn.md, tailwind.md, {{UI_FRAMEWORK}}.md
```

**Conflict rule:** when two skills disagree, the higher tier wins. Concretely — **if a project design
system (tier 2) exists, its colors, tokens, component library, theme, severity scale, card
radius/shadow OVERRIDE the same topics in `professional-ui-standards.md` (tier 4).** The generic
standards still govern everything the design system is silent on (spacing grid, typography scale,
z-index, state discipline, anti-patterns).

If NO project design system exists, tier 4 (`professional-ui-standards.md`) is the authority for
tokens/colors too.

---

## 2. Who owns what (non-overlapping scopes)

| Skill | AUTHORITATIVE for | Defers to |
|---|---|---|
| **vertix-portal-design-system.md** | Colors & semantic tokens (ICC + shadcn), the `@portal/components` library (reuse-before-build), theme (`data-theme`/`@portal/contracts`), severity/status scale + badges, card radius (14px) & shadows | — (top of UI stack when present) |
| **professional-ui-standards.md** | Spacing (4px grid), typography scale, z-index scale, state discipline (4-state rule), density, motion, anti-patterns. Its color/radius/shadow sections are **defaults, overridden by a project design system** | design system for tokens/colors/components |
| **structured-wireframe-format.md** | The YAML/HTML wireframe spec format ux_designer emits | design system for component names |
| **component-composition.md** | File/folder structure, compound-component patterns, prop conventions | design system for which components exist |
| **accessibility-patterns.md** | WCAG 2.2 AA: semantic HTML, ARIA, focus, keyboard | — |
| **responsive-patterns.md** | Breakpoints, mobile-first, responsive layout | design system for surface tokens |
| **loading-states.md** | Skeletons, Suspense, progressive/optimistic loading | design system for `<EmptyState>`/component `loading` props |
| **error-handling-patterns.md** | Error-type → UI pattern mapping, error boundaries | design system for `<EmptyState>` |
| **form-patterns.md** | React Hook Form + Zod form UX | design system for `<FormBuilder>` when present |
| **form-validation-protocol.md** | Deriving Zod schemas from data-contracts.md | form-patterns for rendering |
| **api-integration-patterns.md** | HTTP client + TanStack Query hooks, cache keys | — |
| **type-generation-protocol.md** | data-contracts.md → `types/api.ts` generation | — |
| **advanced-state-patterns.md** | Complex client state (machines, cross-component) | — |
| **shadcn.md** | shadcn/ui component mechanics (how to compose primitives) | design system for whether to use shadcn vs `@portal/components` |
| **tailwind.md** | Tailwind utility mechanics (layout/spacing syntax) | tokens from tiers 2/4 — never raw `bg-blue-500` |

**Rule of thumb:** design system = *what* (which tokens, which components). Generic standards = *the
discipline* (grid, type, a11y, states). Framework skills = *how* (syntax/mechanics). They compose;
they don't compete — as long as you respect precedence for the few overlaps (colors, components,
card radius/shadow).

---

## 3. Load order for UI agents

**ux_designer** (wireframes): README → project design system → structured-wireframe-format →
professional-ui-standards → accessibility → responsive → (loading/error/form as needed). Map every
widget to a real component name from the design system's library; specify colors as tokens.

**ui_developer** (implementation): README → project design system → professional-ui-standards →
component-composition → api-integration → framework skills ({{UI_FRAMEWORK}}, shadcn, tailwind) →
(form/loading/error/responsive/a11y as the screen needs).

**design_quality_reviewer** (gate): README → project design system → professional-ui-standards →
accessibility. Enforce precedence: a hardcoded color or a rebuilt primitive that exists in the design
system's library is a BLOCKING dimension-11 finding.

---

## 4. Adding a new project design system

For a non-Vertix project, drop a `*-design-system.md` here following the same shape as
`vertix-portal-design-system.md` (tokens table + component inventory + theme + rules), and it slots
into tier 2 automatically — the agents already load "the project design system if it exists." Record
the choice as a decision in `docs/DECISIONS.md` so it's durable.
