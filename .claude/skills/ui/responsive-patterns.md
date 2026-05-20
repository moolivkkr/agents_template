# Responsive Design Patterns — Mobile-First Reference

## Breakpoint Strategy (Mobile-First)

Build for mobile FIRST. Add complexity at larger breakpoints.

```
Base (0-639px):   Single column, full-width, stacked layout
sm: (640px+):     Minor adjustments (2-column where appropriate)
md: (768px+):     Sidebar appears, 2-column grids
lg: (1024px+):    3-column grids, full navigation
xl: (1280px+):    Max-width container, generous spacing
```

## Common Layout Patterns

### Responsive Grid
```tsx
<div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
  {items.map(item => <Card key={item.id} />)}
</div>
```

### Sidebar Layout (hidden on mobile)
```tsx
<div className="flex min-h-screen">
  {/* Sidebar — hidden on mobile, visible on desktop */}
  <aside className="hidden w-64 border-r bg-card md:block">
    <nav className="space-y-1 p-4">{/* Nav links */}</nav>
  </aside>

  {/* Mobile hamburger trigger */}
  <Sheet>
    <SheetTrigger asChild>
      <Button variant="ghost" size="icon" className="md:hidden">
        <Menu className="size-5" />
        <span className="sr-only">Open menu</span>
      </Button>
    </SheetTrigger>
    <SheetContent side="left" className="w-64 p-0">
      <nav className="space-y-1 p-4">{/* Same nav links */}</nav>
    </SheetContent>
  </Sheet>

  <main className="flex-1 p-4 md:p-6">{children}</main>
</div>
```

### Responsive Navigation
```tsx
function MainNav() {
  return (
    <header className="sticky top-0 z-10 border-b bg-background">
      <div className="mx-auto flex h-14 max-w-7xl items-center px-4">
        <Logo />

        {/* Desktop nav — hidden on mobile */}
        <nav className="ml-6 hidden items-center gap-6 md:flex">
          <NavLink href="/dashboard">Dashboard</NavLink>
          <NavLink href="/users">Users</NavLink>
          <NavLink href="/settings">Settings</NavLink>
        </nav>

        {/* Mobile nav — hamburger */}
        <Sheet>
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon" className="ml-auto md:hidden">
              <Menu className="size-5" />
              <span className="sr-only">Menu</span>
            </Button>
          </SheetTrigger>
          <SheetContent side="right">
            <nav className="flex flex-col gap-4 pt-8">
              <NavLink href="/dashboard">Dashboard</NavLink>
              <NavLink href="/users">Users</NavLink>
              <NavLink href="/settings">Settings</NavLink>
            </nav>
          </SheetContent>
        </Sheet>
      </div>
    </header>
  );
}
```

## Responsive Component Swaps

### Data Table → Card List on Mobile
```tsx
{/* Desktop: table */}
<div className="hidden md:block">
  <DataTable columns={columns} data={users} />
</div>

{/* Mobile: card list */}
<div className="space-y-3 md:hidden">
  {users.map(user => (
    <Card key={user.id} className="p-4">
      <div className="flex items-center gap-3">
        <Avatar><AvatarImage src={user.avatar} /><AvatarFallback>{user.initials}</AvatarFallback></Avatar>
        <div className="flex-1 min-w-0">
          <p className="font-medium truncate">{user.name}</p>
          <p className="text-sm text-muted-foreground truncate">{user.email}</p>
        </div>
        <Badge variant={user.active ? "default" : "secondary"}>{user.role}</Badge>
      </div>
    </Card>
  ))}
</div>
```

### Modal → Full-Screen Sheet on Mobile
```tsx
{/* Desktop: centered dialog */}
<Dialog>
  <DialogContent className="hidden sm:block sm:max-w-lg">
    {/* Form content */}
  </DialogContent>
</Dialog>

{/* Mobile: full-screen sheet */}
<Sheet>
  <SheetContent side="bottom" className="h-[90vh] sm:hidden">
    {/* Same form content */}
  </SheetContent>
</Sheet>
```

## Touch Target Rules

Minimum **44x44px** on mobile (WCAG 2.2 AAA, AA recommends 24px minimum).

```tsx
// Ensure touch targets on mobile
<Button size="sm" className="min-h-11 min-w-11 md:min-h-0 md:min-w-0">
  {/* Content */}
</Button>

// Icon buttons — already 40px (h-10 w-10), add padding for touch
<Button variant="ghost" size="icon" className="size-11">
  <Trash className="size-4" />
</Button>
```

## Typography Scaling
```tsx
// Page titles
<h1 className="text-2xl font-bold tracking-tight md:text-3xl lg:text-4xl">Title</h1>

// Section headings
<h2 className="text-xl font-semibold md:text-2xl">Section</h2>

// Body text stays consistent (no scaling needed at base size)
<p className="text-sm text-muted-foreground md:text-base">Body text</p>
```

## Anti-Patterns

| Never Do | Instead Do |
|----------|-----------|
| Fixed pixel widths (`w-[400px]`) | Responsive: `w-full max-w-md` |
| Hide content on mobile | Restructure it (table → cards) |
| `hover:` without touch fallback | Use `hover:` + ensure tap works without hover |
| Assume landscape orientation | Test portrait and landscape |
| Tiny tap targets on mobile | `min-h-11 min-w-11` (44px) |
| Horizontal scroll on mobile | `overflow-x-auto` on tables, responsive grids elsewhere |
