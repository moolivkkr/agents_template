# Page Archetype: Detail Page

## When to Use
Any screen showing a single resource: user profile, order details, invoice view, project settings.

## Component Tree — Desktop (1280px)
```
div.space-y-6
├── Breadcrumb
│   ├── BreadcrumbItem > Link → "Users"
│   ├── BreadcrumbSeparator
│   └── BreadcrumbItem → data.name (current page)
│
├── PageHeader (div.flex.items-center.justify-between)
│   ├── div.flex.items-center.gap-4
│   │   ├── Avatar(lg) > AvatarImage + AvatarFallback
│   │   ├── div
│   │   │   ├── h1.text-2xl.font-bold → data.name
│   │   │   └── p.text-muted-foreground → data.email
│   │   └── Badge → data.role
│   └── div.flex.gap-2
│       ├── Button(outline) → "Edit" → navigate to /users/:id/edit
│       └── AlertDialog
│           ├── AlertDialogTrigger > Button(destructive, outline) → "Delete"
│           └── AlertDialogContent → confirm deletion
│
├── Tabs
│   ├── TabsList
│   │   ├── TabsTrigger → "Overview"
│   │   ├── TabsTrigger → "Activity"
│   │   └── TabsTrigger → "Settings"
│   ├── TabsContent(overview)
│   │   └── Card > CardContent
│   │       └── dl.grid.grid-cols-1.gap-4.sm:grid-cols-2
│   │           ├── div > dt.text-sm.text-muted-foreground + dd.font-medium
│   │           └── ... (label-value pairs for each field)
│   ├── TabsContent(activity)
│   │   └── Card > list of activity items with timestamps
│   └── TabsContent(settings)
│       └── Card > user-specific settings form
```

## Component Tree — Mobile (375px)
- Breadcrumb: simplified (just back arrow + parent name)
- Header: stacked (avatar + name above, action buttons full-width below)
- Tabs: scrollable horizontal TabsList
- Content: single-column dl, no grid

## Data Flow
```tsx
const { id } = useParams();
const { data, isLoading, isError, error, refetch } = useQuery(
  resourceQueries.detail(id)
);
// data type: { data: Resource } — SINGLE OBJECT

const deleteResource = useDeleteResource();
```

## 4 States

### Loading
```tsx
<div className="space-y-6">
  <div className="flex items-center gap-4">
    <Skeleton className="size-16 rounded-full" />
    <div className="space-y-2">
      <Skeleton className="h-6 w-48" />
      <Skeleton className="h-4 w-32" />
    </div>
  </div>
  <div className="grid gap-4 sm:grid-cols-2">
    {Array.from({ length: 6 }).map((_, i) => (
      <div key={i} className="space-y-1">
        <Skeleton className="h-3 w-20" />
        <Skeleton className="h-5 w-40" />
      </div>
    ))}
  </div>
</div>
```

### Not Found (404)
- Icon: `FileQuestion`
- Title: "User not found"
- Description: "This user may have been deleted or the link is incorrect."
- CTA: Button "Back to users" → navigate to list

### Error
- Icon: `AlertCircle` (destructive)
- Message: `{error.message}`
- Action: Button(outline) "Try again" → `refetch()`

### Populated
- Full detail view with tabs
