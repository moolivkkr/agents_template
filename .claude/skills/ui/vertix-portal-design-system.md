# Vertix Portal Design System — house style for all module UIs

> **Precedence (see `.claude/skills/ui/README.md`).** For Vertix portal modules this file is **tier 2
> — it OVERRIDES the generic `professional-ui-standards.md` on colors/tokens, the component library,
> theme, severity scale, and card radius/shadow.** The generic standards still govern spacing (4px
> grid), typography, z-index, a11y, and state discipline — this file does not restate those; follow
> both, with this one winning the overlaps.
>
> **Source of truth.** Extracted from `vertix/portal/frontend` — the standardized portal shell +
> shared component library that every module micro-frontend adopts. UI agents building or reviewing
> any Vertix portal module MUST follow this. It supersedes ad-hoc color/spacing choices.
>
> **Golden rules (the whole skill in five lines):**
> 1. **Never hardcode a color.** Use the semantic Tailwind tokens below (`bg-panel`, `text-ink`,
>    `text-crit`, …). They flip light/dark automatically.
> 2. **Reuse `@portal/components` before building anything.** 30+ shared components already exist —
>    DataTable, FilterBar, FormBuilder, Modal, EmptyState, PageHeader, SeverityBadge, KPICard, …
> 3. **Theme is `data-theme` on `<html>`**, driven by `@portal/contracts`. Support both themes; test
>    both. Do not add your own theme toggle.
> 4. **Every data view has 4 states** (loading / error / empty / data) — use `<EmptyState>` and the
>    component `loading`/`emptyMessage` props, never a bare spinner or blank page.
> 5. **Severity/status use the canonical scale + badges**, not custom colors.

---

## 1. Token systems (two, both flip on `<html data-theme="light|dark">`)

The portal runs **two coexisting token systems**, both driven by the `data-theme` attribute:

- **ICC house-style palette** (`--icc-*`, full color values) — the primary "Incident Command Center"
  design language every page adopts. Mapped to semantic Tailwind utilities.
- **shadcn semantic tokens** (`--x` HSL triplets, consumed via `hsl(var(--x))`) — for ported shadcn
  components (`bg-card`, `text-muted-foreground`, `border-border`, `bg-accent`).

Prefer **ICC tokens** for new pages; shadcn tokens are for shadcn-derived components.

### ICC token → Tailwind utility map (use these class names)

| Purpose | Tailwind class | CSS var | Light | Dark |
|---|---|---|---|---|
| App background | `bg-app` | `--icc-bg` | `#f4f6fa` | `#0b0f17` |
| Panel / card surface | `bg-panel` | `--icc-panel` | `#ffffff` | `#121826` |
| Secondary surface | `bg-panel2` | `--icc-panel-2` | `#f1f4f9` | `#0f1420` |
| Chip surface | `bg-chip` | `--icc-chip` | `#eef2f8` | `#1a2233` |
| Borders / dividers | `border-line` | `--icc-line` | `#e4e9f1` | `#1f2937` |
| Primary text | `text-ink` | `--icc-txt` | `#16203a` | `#e6edf6` |
| Secondary text | `text-subtle` | `--icc-muted` | `#5d6b85` | `#8b9bb4` |
| Faint text | `text-faint` | `--icc-muted-2` | `#9aa7bd` | `#5d6b85` |
| Brand / accent | `bg-brand` `text-brand` | `--icc-accent` | `#4361ee` | `#6c8cff` |
| Brand secondary | `bg-brand2` | `--icc-accent-2` | `#8b3dff` | `#a06bff` |
| Header bar | `bg-header` | `--icc-header-bg` | translucent white | translucent dark |

**Severity/status colors** (`text-crit`/`bg-crit`, `text-high`, `text-med`, `text-low`, `text-info`,
`text-ok`):

| Token | Class | Light | Dark | Use for |
|---|---|---|---|---|
| crit | `*-crit` | `#e5384a` | `#ff4d5e` | critical severity, blocking errors |
| high | `*-high` | `#ec7a1b` | `#ff8a3d` | high severity |
| med | `*-med` | `#c98a00` | `#ffd23d` | medium severity, warnings |
| low | `*-low` | `#2b7fff` | `#3da5ff` | low severity, info-level |
| info | `*-info` | `#9aa7bd` | `#5d6b85` | informational |
| ok | `*-ok` | `#12a06a` | `#2ecc8f` | success, healthy, resolved |

**Shape & elevation:** cards use `rounded-card` (14px radius) + `shadow-card`. Drawers use
`shadow-drawer`. Do not invent other radii/shadows for cards.

### shadcn tokens (for shadcn-derived components only)
`bg-background` `text-foreground` `bg-card`/`text-card-foreground` `bg-muted`/`text-muted-foreground`
`bg-accent`/`text-accent-foreground` `border-border`. Defined as HSL triplets in `index.css`.

---

## 2. Theme mechanism — `@portal/contracts`

Theme is a single source of truth persisted to `localStorage` and broadcast on a custom event; the
`--icc-*` and shadcn tokens both flip on `<html data-theme>`.

```ts
import { initTheme, getTheme, toggleTheme, applyTheme, THEME_CHANGE_EVENT } from '@portal/contracts'

initTheme()            // call once at app startup — applies persisted or default ('light')
getTheme()             // 'light' | 'dark'
toggleTheme()          // flips + persists + dispatches THEME_CHANGE_EVENT
window.addEventListener(THEME_CHANGE_EVENT, (e) => { /* react to (e as CustomEvent).detail */ })
```

**Rules:** never write `document.documentElement.setAttribute('data-theme', …)` directly — go through
`applyTheme`. Never add a second theme toggle in a module; the shell owns it. Never hardcode a hex
color that won't flip — use the tokens in §1.

---

## 3. Shared component library — `@portal/components` (reuse before you build)

Import from `@portal/components`. **Building a table, filter bar, form, modal, badge, empty state,
KPI card, or chart from scratch is a review failure** — these already exist and are themed.

| Component | Key props | Use for |
|---|---|---|
| `DataTable<T>` | `columns: Column<T>[]`, `data`, `onRowClick?`, `loading?`, `emptyMessage?` | Any tabular list. `Column` = `{ key, header, render?(row), width?, sortable? }`. Handles loading + empty internally. |
| `FilterBar` | `fields: FilterField[]`, `values`, `onChange`, `onApply?`, `onReset?` | List/table filtering. `FilterField.type`: `text \| select \| date \| multiselect`. |
| `FormBuilder` | `fields: FormField[]`, `values`, `onChange`, `errors?` | Config/create/edit forms. `FormField.type`: `text \| number \| select \| textarea \| toggle \| json \| tags`; supports `required`, `description`. |
| `Modal` | `open`, `onClose`, `title`, `children`, `footer?`, `size?: sm\|md\|lg\|xl` | Dialogs, drawers, confirmations. |
| `PageHeader` | `title`, `subtitle?`, `breadcrumbs?: BreadcrumbItem[]`, `actions?` | Top of every page. |
| `EmptyState` | `title`, `description?`, `icon?`, `action?` | The empty (and often error/degraded) state of any data view. |
| `KPICard` | `title`, `value`, `subtitle?`, `icon?`, `trend?{direction,value}`, `variant?: default\|warning\|danger\|success` | Dashboard metric tiles. |
| `Badge` | `label`/`children`, `variant?: default\|primary\|success\|warning\|danger\|info`, `size?: sm\|md` | Generic labels/pills. |
| `SeverityBadge` | `severity: Severity` | Severity display — do NOT color severities by hand. |
| `StatusBadge` | `status: IncidentStatus` | Incident/entity status. |
| `PriorityChip`, `RiskChip` | priority/risk value | Priority & risk pills. |
| `Tabs` | `tabs: TabItem[]`, `activeTab`, `onChange`, `children` | Tabbed views; `TabItem` supports a `badge`. |
| `Pagination` | `total`, `limit`, `offset`, `onChange(offset)` | Server-side paginated lists (returns null when it fits one page). |
| `SearchInput`, `FilterBar` | — | Search + filter controls. |
| `Timeline` | `items: TimelineItem[]` | Event/audit timelines. |
| `DataTable` + `ExportButton` | — | Tables with CSV/export. |
| `StackedBarChart`, `DonutChart`, `HeatmapChart`, `ProgressBar` | data points | Charts — use these, not a raw chart lib. |
| `CodeEditor`, `SplitPane`, `TreeView` | — | Code/JSON editing, split layouts, tree nav. |
| `DetectionEvidence`, `EvidenceAttachments`, `SLACountdown`, `TimeAgo`, `CommandCenterView` | domain | Security-domain widgets. |

Full export list: `packages/components/src/index.ts` in the portal. Check it before assuming a
component is missing.

### Canonical usage pattern (from a real module page)

```tsx
import { Badge, EmptyState, DataTable, type Column } from '@portal/components'

// Map a domain status → Badge variant (don't hardcode colors):
function statusBadge(status?: string): { variant: 'success'|'warning'|'danger'|'default'; label: string } {
  const s = (status ?? '').toLowerCase()
  if (s === 'ok') return { variant: 'success', label: 'ok' }
  if (s === 'error') return { variant: 'danger', label: 'error' }
  if (s === 'stale') return { variant: 'warning', label: s }
  return { variant: 'default', label: s || 'unknown' }
}

// Data view: loading + empty are handled by the component; error → EmptyState.
<DataTable columns={cols} data={rows} loading={loading}
           emptyMessage="No connectors reporting" onRowClick={openDetail} />
```

Each independent fetch **degrades independently** — a 503 (plane disabled) surfaces an informative
`<EmptyState>` without breaking sibling panels. Never let one failed call blank the whole page.

---

## 4. Canonical scales (use the shared types from `@portal/contracts`)

- **Severity:** `'critical' | 'high' | 'medium' | 'low' | 'informational'` (`Severity` type). Render
  via `<SeverityBadge>` / the `*-crit|high|med|low|info` tokens — never a bespoke color map.
- **Status:** `IncidentStatus` (includes `'closed'`, `'open'`, triage states — see
  `packages/contracts/src/incidents.ts`). Render via `<StatusBadge>`.
- **Breadcrumbs:** `BreadcrumbItem` (`packages/contracts/src/navigation.ts`), passed to `PageHeader`.

Import these types from `@portal/contracts` rather than redefining string unions per module.

---

## 5. Rules for UI agents (enforced by design_quality_reviewer)

**MUST:**
- Use the semantic tokens in §1 for every color, surface, border, and text — zero hardcoded hex
  outside `index.css`/`tailwind.config.js`.
- Reuse `@portal/components` for tables, filters, forms, modals, badges, empty states, KPIs, charts,
  page headers, tabs, pagination. Justify in the PR if you build a new primitive.
- Support light AND dark (they flip automatically if you use tokens — so this is mostly free).
- Give every data-bound view all 4 states via component props / `<EmptyState>`.
- Use `<SeverityBadge>`/`<StatusBadge>` and the canonical `Severity`/`IncidentStatus` types.
- Wrap pages in `<PageHeader>` with title + breadcrumbs; cards use `bg-panel rounded-card shadow-card`.

**MUST NOT:**
- Hardcode colors (`#fff`, `text-gray-500`, `bg-slate-800`) — they won't theme.
- Rebuild a component that exists in `@portal/components`.
- Add a module-level theme toggle or set `data-theme` directly.
- Use spinners or blank screens instead of skeletons/`<EmptyState>`.
- Invent severity colors or status strings outside the canonical scale.

**When a needed component genuinely doesn't exist:** build it in the module using §1 tokens and the
existing components' conventions (props shape, 4-state handling), and note it as a candidate to
promote into `@portal/components`.
