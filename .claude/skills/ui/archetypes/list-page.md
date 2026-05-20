# Page Archetype: List Page

## When to Use
Any screen displaying a collection of resources: users, orders, invoices, projects, etc.

## Component Tree — Desktop (1280px)
```
div.space-y-6
├── PageHeader
│   ├── div
│   │   ├── h1.text-3xl.font-bold.tracking-tight → "Users"
│   │   └── p.text-muted-foreground → "Manage your team members."
│   └── Button → <Plus className="mr-2 size-4" /> "Add user"
│
├── Toolbar (div.flex.items-center.gap-4)
│   ├── SearchInput (div.relative > Search icon + Input) → debounced, URL state via nuqs
│   ├── Select (filter by status/role) → URL state
│   └── DropdownMenu (column visibility toggle) → ml-auto
│
├── Card > div.rounded-md.border
│   └── Table
│       ├── TableHeader > TableRow
│       │   ├── TableHead > Checkbox (select all)
│       │   ├── TableHead → "Name" (sortable, onClick → URL state)
│       │   ├── TableHead → "Email"
│       │   ├── TableHead → "Role"
│       │   └── TableHead.text-right → "Actions"
│       └── TableBody
│           └── TableRow (per item)
│               ├── TableCell > Checkbox
│               ├── TableCell > div.flex.items-center.gap-3
│               │   ├── Avatar > AvatarImage + AvatarFallback
│               │   └── span.font-medium → data.name
│               ├── TableCell → data.email
│               ├── TableCell > Badge → data.role
│               └── TableCell.text-right > DropdownMenu
│                   ├── DropdownMenuItem → "Edit"
│                   └── DropdownMenuItem.text-destructive → "Delete"
│
└── Pagination (div.flex.items-center.justify-between)
    ├── p.text-sm.text-muted-foreground → "{total} users"
    └── div.flex.gap-2
        ├── Button(outline, sm) → "Previous" (disabled if page=1)
        └── Button(outline, sm) → "Next" (disabled if last page)
```

## Component Tree — Mobile (375px)
- Toolbar: stacked full-width (SearchInput full-width, Select full-width below)
- Table → Card list: each item as Card.p-4 with flex layout
- Pagination: centered, smaller buttons with min-h-11 touch targets
- "Add user" button: fixed bottom or in header

## Data Flow
```tsx
const [search, setSearch] = useQueryState("q", parseAsString.withDefault(""));
const [page, setPage] = useQueryState("page", parseAsInteger.withDefault(1));
const [sort, setSort] = useQueryState("sort", parseAsString.withDefault("name"));

const { data, isLoading, isError, error, refetch } = useQuery(
  resourceQueries.list({ search, page, sort })
);
// data type: { data: Resource[], meta: { total, page, per_page } }
```

## 4 States

### Loading
```tsx
<div className="space-y-3">
  {Array.from({ length: 8 }).map((_, i) => (
    <div key={i} className="flex items-center gap-4 rounded-lg border p-4">
      <Skeleton className="size-10 rounded-full" />
      <div className="flex-1 space-y-2">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-3 w-48" />
      </div>
      <Skeleton className="h-6 w-16 rounded-full" />
    </div>
  ))}
</div>
```

### Empty
- Icon: `Users` (from Lucide)
- Title: "No users yet"
- Description: "Get started by adding your first team member."
- CTA: Button "Add user" → opens create dialog

### Error
- Icon: `AlertCircle` (destructive)
- Message: `{error.message}`
- Action: Button(outline) "Try again" → `refetch()`

### Populated
- Table with data rows, sortable headers, row actions
