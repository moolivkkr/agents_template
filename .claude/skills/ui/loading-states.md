---
skill: loading-states
description: Loading patterns — skeleton screens, Suspense, progressive loading, and layout-shift prevention
version: "1.0"
tags:
  - loading
  - skeleton
  - suspense
  - ux
  - ui
---

# Loading State Patterns — Skeletons, Suspense, Progressive Loading

## Primary Rule: Skeleton Screens (NOT Spinners)

Skeleton screens match the layout of loaded content. They reduce perceived load time and prevent layout shift.

### Skeleton Components
```tsx
import { Skeleton } from "@/components/ui/skeleton";

// Card skeleton
function CardSkeleton() {
  return (
    <Card className="p-6">
      <div className="space-y-3">
        <Skeleton className="h-5 w-32" />        {/* Title */}
        <Skeleton className="h-4 w-full" />       {/* Line 1 */}
        <Skeleton className="h-4 w-3/4" />        {/* Line 2 */}
      </div>
    </Card>
  );
}

// Table row skeleton
function TableRowSkeleton() {
  return (
    <div className="flex items-center gap-4 border-b p-4">
      <Skeleton className="size-10 rounded-full" />  {/* Avatar */}
      <div className="flex-1 space-y-2">
        <Skeleton className="h-4 w-32" />             {/* Name */}
        <Skeleton className="h-3 w-48" />             {/* Email */}
      </div>
      <Skeleton className="h-8 w-20" />               {/* Action button */}
    </div>
  );
}

// List skeleton
function ListSkeleton({ count = 5 }: { count?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: count }).map((_, i) => (
        <TableRowSkeleton key={i} />
      ))}
    </div>
  );
}

// Form skeleton
function FormSkeleton({ fields = 3 }: { fields?: number }) {
  return (
    <div className="space-y-6">
      {Array.from({ length: fields }).map((_, i) => (
        <div key={i} className="space-y-2">
          <Skeleton className="h-4 w-20" />    {/* Label */}
          <Skeleton className="h-10 w-full" /> {/* Input */}
        </div>
      ))}
      <Skeleton className="h-10 w-24" />       {/* Submit button */}
    </div>
  );
}

// Stats grid skeleton
function StatsGridSkeleton() {
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <Card key={i} className="p-6">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="mt-2 h-8 w-16" />
          <Skeleton className="mt-1 h-3 w-32" />
        </Card>
      ))}
    </div>
  );
}
```

## When to Use What

| Scenario | Pattern | Example |
|----------|---------|---------|
| Initial page load | Full skeleton layout | `<ListSkeleton />` |
| Data refetch | Keep stale data + subtle indicator | `isFetching && <RefreshIndicator />` |
| Form submission | Disable button + spinner IN button | `<Loader2 className="animate-spin" />` |
| Navigation | Top progress bar | NProgress or `loading.tsx` |
| Infinite scroll | Skeleton rows at bottom | `<TableRowSkeleton />` appended |
| Image loading | Blur placeholder → sharp | Next.js `<Image placeholder="blur">` |
| Long operation | Progress bar | `<Progress value={percent} />` |

## Button Loading Pattern
```tsx
<Button disabled={isPending}>
  {isPending && <Loader2 className="mr-2 size-4 animate-spin" />}
  {isPending ? "Saving..." : "Save changes"}
</Button>
```

## Next.js App Router loading.tsx
```tsx
// app/(dashboard)/users/loading.tsx
import { Skeleton } from "@/components/ui/skeleton";

export default function UsersLoading() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <Skeleton className="h-8 w-48" />   {/* Page title */}
        <Skeleton className="h-10 w-32" />  {/* Create button */}
      </div>
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
    </div>
  );
}
```

## React Suspense Pattern
```tsx
import { Suspense } from "react";

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>

      {/* Each section loads independently */}
      <Suspense fallback={<StatsGridSkeleton />}>
        <StatsGrid />
      </Suspense>

      <div className="grid gap-6 md:grid-cols-2">
        <Suspense fallback={<CardSkeleton />}>
          <RecentActivity />
        </Suspense>
        <Suspense fallback={<CardSkeleton />}>
          <QuickActions />
        </Suspense>
      </div>
    </div>
  );
}
```

## TanStack Query: isLoading vs isFetching

```tsx
function UserList() {
  const { data, isLoading, isFetching } = useQuery(userQueries.list());

  // isLoading = true on FIRST load only (no cached data)
  if (isLoading) return <ListSkeleton />;

  // isFetching = true on refetch (has stale data to show)
  return (
    <div className="relative">
      {isFetching && (
        <div className="absolute right-0 top-0">
          <Loader2 className="size-4 animate-spin text-muted-foreground" />
        </div>
      )}
      {/* Render stale data while refetching */}
      {data?.map(user => <UserRow key={user.id} user={user} />)}
    </div>
  );
}
```

## Anti-Patterns

| Never Do | Instead Do |
|----------|-----------|
| Full-page spinner for initial load | Skeleton matching content layout |
| Blank screen while loading | Always show skeleton or cached data |
| Hide loaded content during refetch | Show stale data + subtle indicator |
| Show loading for < 200ms | Use `startTransition` or add minimum delay |
| Generic spinner for every loading state | Match skeleton to the content being loaded |
| Spinner without text | "Loading..." or specific context ("Loading users...") |
