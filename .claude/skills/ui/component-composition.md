# Component Composition Patterns — shadcn/ui + React

## Component Hierarchy (Atomic Design for shadcn)

```
Primitives (from shadcn/ui — don't rebuild):
  Button, Input, Badge, Avatar, Skeleton, Separator, Label

Molecules (compose primitives):
  SearchInput, FormField, UserAvatar, StatusBadge, EmptyState

Organisms (compose molecules):
  DataTable, UserCard, NavigationMenu, CreateUserForm

Templates (page structure):
  DashboardLayout, AuthLayout, SettingsLayout

Pages (route components):
  UsersPage, SettingsPage, DashboardPage
```

## File Organization
```
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
        destructive: "border-destructive/50 text-destructive bg-destructive/10",
        warning: "border-yellow-500/50 text-yellow-700 bg-yellow-50",
        success: "border-green-500/50 text-green-700 bg-green-50",
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
      {description && <p className="text-sm opacity-80">{description}</p>}
    </div>
  );
}
```

### Forward Refs (required for form inputs, tooltips)
```tsx
const CustomInput = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, ...props }, ref) => (
    <Input className={cn("custom-styles", className)} ref={ref} {...props} />
  )
);
CustomInput.displayName = "CustomInput";
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
          <TableHead className="w-12"><Checkbox /></TableHead>
          <TableHead>Name</TableHead>
          <TableHead>Email</TableHead>
          <TableHead>Role</TableHead>
          <TableHead className="text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {users.map(user => (
          <TableRow key={user.id}>
            <TableCell><Checkbox /></TableCell>
            <TableCell className="font-medium">{user.name}</TableCell>
            <TableCell>{user.email}</TableCell>
            <TableCell><StatusBadge status={user.role} /></TableCell>
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

  {/* Pagination */}
  <div className="flex items-center justify-between">
    <p className="text-sm text-muted-foreground">{total} total users</p>
    <div className="flex gap-2">
      <Button variant="outline" size="sm" disabled={page === 1} onClick={() => setPage(p => p - 1)}>Previous</Button>
      <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>Next</Button>
    </div>
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
