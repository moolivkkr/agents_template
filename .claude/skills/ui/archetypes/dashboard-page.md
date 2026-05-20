# Page Archetype: Dashboard Page

## When to Use
Overview/home screens with KPI stats, charts, recent activity, and quick actions.

## Component Tree — Desktop (1280px)
```
div.space-y-6
├── PageHeader
│   ├── h1.text-3xl.font-bold.tracking-tight → "Dashboard"
│   └── p.text-muted-foreground → "Overview of your workspace."
│
├── Suspense(fallback=StatsGridSkeleton)
│   └── StatsGrid (div.grid.gap-4.md:grid-cols-2.lg:grid-cols-4)
│       └── StatCard (×4)
│           └── Card
│               ├── CardHeader.flex.flex-row.items-center.justify-between.pb-2
│               │   ├── CardTitle.text-sm.font-medium → "Total Users"
│               │   └── Users.size-4.text-muted-foreground (Lucide icon)
│               └── CardContent
│                   ├── div.text-2xl.font-bold → "2,350"
│                   └── p.text-xs.text-muted-foreground → "+12% from last month"
│
├── div.grid.gap-6.md:grid-cols-2
│   ├── Suspense(fallback=ChartSkeleton)
│   │   └── Card
│   │       ├── CardHeader > CardTitle → "Revenue" + CardDescription → "Monthly revenue trend"
│   │       └── CardContent
│   │           └── ResponsiveContainer > AreaChart (Recharts)
│   │
│   └── Suspense(fallback=ChartSkeleton)
│       └── Card
│           ├── CardHeader > CardTitle → "Users" + CardDescription → "New signups by week"
│           └── CardContent
│               └── ResponsiveContainer > BarChart (Recharts)
│
├── div.grid.gap-6.md:grid-cols-2
│   ├── Suspense(fallback=ActivitySkeleton)
│   │   └── Card
│   │       ├── CardHeader > CardTitle → "Recent Activity"
│   │       └── CardContent
│   │           └── div.space-y-4
│   │               └── ActivityItem (×5)
│   │                   └── div.flex.items-center.gap-4
│   │                       ├── Avatar(sm)
│   │                       ├── div.flex-1.min-w-0
│   │                       │   ├── p.text-sm.font-medium.truncate → actor name
│   │                       │   └── p.text-xs.text-muted-foreground → action description
│   │                       └── span.text-xs.text-muted-foreground → "2h ago"
│   │
│   └── Suspense(fallback=QuickActionsSkeleton)
│       └── Card
│           ├── CardHeader > CardTitle → "Quick Actions"
│           └── CardContent
│               └── div.grid.gap-3.grid-cols-2
│                   ├── Button(outline, full-width) → "New User"
│                   ├── Button(outline, full-width) → "Create Report"
│                   ├── Button(outline, full-width) → "View Logs"
│                   └── Button(outline, full-width) → "Settings"
```

## Component Tree — Mobile (375px)
- Stats grid: 2 columns (grid-cols-2) instead of 4
- Charts: single column stack
- Activity + Quick Actions: single column stack
- All cards full-width

## Data Flow
```tsx
// Each section uses independent queries — parallel loading
const stats = useQuery(dashboardQueries.stats());
const revenue = useQuery(dashboardQueries.revenueChart());
const signups = useQuery(dashboardQueries.signupChart());
const activity = useQuery(dashboardQueries.recentActivity());
```

Key pattern: **each section wrapped in its own Suspense boundary** with matching skeleton. Sections load independently — fast sections appear first.

## 4 States (per section, NOT per page)

### Loading (per section)
Each section has its OWN skeleton:
- StatsGrid: 4 Card skeletons with Skeleton lines
- Charts: Card with Skeleton rectangle (h-[200px])
- Activity: 5 rows of Avatar + text Skeletons
- Quick Actions: static (no data dependency)

### Empty (stats section)
- Show "0" values with muted styling, not empty state
- Dashboard should never show a full empty state — always show the structure

### Error (per section)
- Failed section shows inline error + retry
- Other sections continue to load/display normally
- Never crash the whole dashboard for one failed query

### Populated
- Stats with real numbers + trend percentages
- Charts with real data
- Activity list with recent items
