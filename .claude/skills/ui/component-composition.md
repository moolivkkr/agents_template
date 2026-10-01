---
skill: component-composition
description: Component composition patterns — building from shadcn/ui primitives, compound components, slots, and React composition over configuration
version: "1.0"
tags:
  - components
  - shadcn
  - composition
  - react
  - ui
---

# Component Composition Patterns — shadcn/ui + React

> Code samples compile-checked: tsc (TypeScript 7.0.2, strict + noUncheckedIndexedAccess) against React 19.3, class-variance-authority 0.7 and shadcn/ui component stubs on radix-ui 1.6; the Alert also rendered in the Tailwind v4 theme probe (`next build` + Playwright on Chrome: token colors and axe WCAG 2 AA contrast, light and dark) (`tests/archetype-compile/ui-packs/run.sh`, 2026-09-30).

## Component Hierarchy (Atomic Design for shadcn)

```text
Primitives (from shadcn/ui — don't rebuild):
  Button, Input, Badge, Avatar, Skeleton, Separator, Label

Molecules (compose primitives):
  SearchInput, Field (label + control + error), UserAvatar, StatusBadge, EmptyState

Organisms (compose molecules):
  DataTable, UserCard, NavigationMenu, CreateUserForm

Templates (page structure):
  DashboardLayout, AuthLayout, SettingsLayout

Pages (route components):
  UsersPage, SettingsPage, DashboardPage
```

## File Organization
```text
src/components/
  ui/           → shadcn primitives (auto-generated, minimal customization)
  common/       → app-wide molecules (SearchInput, EmptyState, StatusBadge)
  features/     → feature-specific organisms (UserTable, InvoiceForm)
  layouts/      → page layouts (DashboardLayout, AuthLayout)
```

## Component API Conventions

### Always Accept className (merge with cn)
```tsx
import { cn } from "@/lib/utils";

interface StatusBadgeProps {
  status: "active" | "inactive" | "pending";
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  return (
    <Badge
      variant={status === "active" ? "default" : "secondary"}
      className={cn("capitalize", className)}
    >
      {status}
    </Badge>
  );
}
```

### Variant System with cva
```tsx
import { cva, type VariantProps } from "class-variance-authority";

const alertVariants = cva(
  "relative w-full rounded-lg border p-4 [&>svg]:absolute [&>svg]:left-4 [&>svg]:top-4",
  {
    variants: {
      variant: {
        default: "bg-background text-foreground",
        // Semantic tokens only, never palette colors: --warning / --success are app tokens (tailwind.md
        // §Dark Mode), so every variant follows the theme and dark mode. Colored text sits on bg-card, as in
        // shadcn's own Alert: on a 10% tint of its own color it drops under 4.5:1 (axe measured 4.0 for
        // destructive and 4.37 for warning)
        destructive: "border-destructive/50 bg-card text-destructive",
        warning: "border-warning/50 bg-card text-warning",
        success: "border-success/50 bg-card text-success",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

interface AlertProps extends VariantProps<typeof alertVariants> {
  title: string;
  description?: string;
  className?: string;
}

export function Alert({ title, description, variant, className }: AlertProps) {
  return (
    <div className={cn(alertVariants({ variant }), className)} role="alert">
      <h5 className="mb-1 font-medium leading-none tracking-tight">{title}</h5>
      {description && <p className="text-sm">{description}</p>}{/* no opacity-80: it cost contrast */}
    </div>
  );
}
```

### Refs (required for form inputs, tooltips)
React 19 passes `ref` to function components as a regular prop, so a wrapper forwards it with the rest of the
props: no `forwardRef`, no `displayName`. Current shadcn/ui components are written this way and type their
props as `React.ComponentProps<…>` (there is no exported `InputProps`).
```tsx
function CustomInput({ className, ...props }: React.ComponentProps<typeof Input>) {
  return <Input className={cn("custom-styles", className)} {...props} />; // props includes ref
}
```

## Compound Component Pattern

### Card Composition (shadcn built-in)
```tsx
<Card>
  <CardHeader>
    <CardTitle>Team Members</CardTitle>
    <CardDescription>Manage your team and permissions.</CardDescription>
  </CardHeader>
  <CardContent className="space-y-4">
    {members.map(m => <MemberRow key={m.id} member={m} />)}
  </CardContent>
  <CardFooter className="flex justify-between border-t pt-4">
    <p className="text-sm text-muted-foreground">{members.length} members</p>
    <Button size="sm">Invite</Button>
  </CardFooter>
</Card>
```

### Data Table Composition
```tsx
<div className="space-y-4">
  {/* Toolbar */}
  <div className="flex items-center gap-4">
    <SearchInput value={search} onChange={setSearch} placeholder="Search users..." />
    <Select value={roleFilter} onValueChange={setRoleFilter}>
      <SelectTrigger className="w-40"><SelectValue placeholder="All roles" /></SelectTrigger>
      <SelectContent>
        <SelectItem value="all">All roles</SelectItem>
        <SelectItem value="admin">Admin</SelectItem>
        <SelectItem value="member">Member</SelectItem>
      </SelectContent>
    </Select>
    <Button className="ml-auto"><Plus className="mr-2 size-4" /> Add user</Button>
  </div>

  {/* Table */}
  <div className="rounded-md border">
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-12"><Checkbox aria-label="Select all users" /></TableHead>
          <TableHead>Name</TableHead>
          <TableHead>Email</TableHead>
          <TableHead>Role</TableHead>
          <TableHead className="text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {users.map(user => (
          <TableRow key={user.id}>
            <TableCell><Checkbox aria-label={`Select ${user.name}`} /></TableCell>
            <TableCell className="font-medium">{user.name}</TableCell>
            <TableCell>{user.email}</TableCell>
            <TableCell><Badge variant="secondary">{user.role}</Badge></TableCell>
            <TableCell className="text-right">
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon" aria-label={`Actions for ${user.name}`}>
                    <MoreHorizontal className="size-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem>Edit</DropdownMenuItem>
                  <DropdownMenuItem className="text-destructive">Delete</DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  </div>

  {/* Pagination — cursor-based (meta.pagination): no page numbers, no total unless documented */}
  <div className="flex items-center justify-between">
    <p className="text-sm text-muted-foreground">{users.length} users shown</p>
    <Button variant="outline" size="sm" disabled={!hasNextPage || isFetchingNextPage} onClick={() => fetchNextPage()}>
      {isFetchingNextPage ? "Loading…" : "Load more"}
    </Button>
  </div>
</div>
```

## Prop Drilling Prevention

| Depth | Solution |
|-------|----------|
| 1-2 levels | Pass props directly |
| 3+ levels | React Context or composition (children/render props) |
| Server data | TanStack Query — components fetch their own data |
| UI state (theme, sidebar) | Zustand with selectors |

## Anti-Patterns

| Never Do | Instead Do |
|----------|-----------|
| Component with > 10 props | Split into compound components |
| Business logic in UI components | Extract to custom hooks |
| Duplicate shadcn components | Customize the existing copy in `ui/` |
| Create utils used by only 1 component | Colocate in same file |
| Default exports for components | Named exports (default only for pages) |
| Prop drilling 3+ levels | Context, composition, or TanStack Query |
