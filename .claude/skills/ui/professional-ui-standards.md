# Professional UI Standards — Master Reference

## Design Token System

### Colors — Semantic Only (never raw hex/Tailwind colors)
```css
/* Use these CSS variable-based classes — never bg-blue-500 or text-gray-700 */
--background / --foreground          /* Page background and default text */
--card / --card-foreground           /* Card surfaces */
--popover / --popover-foreground     /* Dropdown/popover surfaces */
--primary / --primary-foreground     /* Primary actions, CTAs */
--secondary / --secondary-foreground /* Secondary actions */
--muted / --muted-foreground         /* Disabled, placeholder, secondary text */
--accent / --accent-foreground       /* Hover highlights */
--destructive / --destructive-foreground /* Delete, error actions */
--border                             /* All borders */
--input                              /* Form input borders */
--ring                               /* Focus rings */
```

### Spacing Scale — 4px Grid (ONLY these values)
```
gap-1 / p-1   →  4px   (icon-to-text within button)
gap-2 / p-2   →  8px   (label-to-input, tight grouping)
gap-3 / p-3   → 12px   (between related items)
gap-4 / p-4   → 16px   (between form fields, list items — DEFAULT)
gap-6 / p-6   → 24px   (between sections in a card, card padding)
gap-8 / p-8   → 32px   (between major page sections)
gap-12 / p-12 → 48px   (page-level vertical spacing)
```
Never use arbitrary values like `mt-[13px]` or `gap-5` (20px breaks the 4px grid).

### Typography Scale
```tsx
// Headings
"text-4xl font-extrabold tracking-tight"          // Page title (h1)
"text-3xl font-semibold tracking-tight"            // Section title (h2)
"text-2xl font-semibold tracking-tight"            // Subsection (h3)
"text-xl font-semibold tracking-tight"             // Card title (h4)

// Body
"text-base leading-7"                              // Default body text
"text-sm text-muted-foreground"                    // Secondary/helper text
"text-xs text-muted-foreground"                    // Captions, timestamps

// Special
"text-xl text-muted-foreground"                    // Lead/intro paragraph
"text-lg font-semibold"                            // Large label
"text-sm font-medium leading-none"                 // Small label
```

### Border Radius — Consistent (pick ONE, use everywhere)
```
rounded-sm  → 4px   (small elements: badges, chips)
rounded-md  → 8px   (inputs, buttons)
rounded-lg  → 12px  (cards, dialogs — DEFAULT for most projects)
rounded-xl  → 16px  (hero sections, large cards)
rounded-full → pill  (avatars, tags)
```

### Shadow System
```
shadow-sm   → cards, elevated surfaces
shadow-md   → dropdowns, popovers
shadow-lg   → modals, dialogs, sheets
shadow-none → flat elements within cards
```

### Z-Index Scale
```
z-0    → default content
z-10   → sticky headers, floating action buttons
z-20   → dropdowns, popovers
z-30   → mobile navigation overlay
z-40   → modals, dialogs
z-50   → toasts, notifications (highest)
```

---

## The 4 States Rule (MANDATORY)

EVERY data-dependent component MUST render all 4 states. No exceptions.

```tsx
function ResourceList() {
  const { data, isLoading, isError, error, refetch } = useQuery(resourceQueries.list());

  // 1. LOADING — skeleton matching content layout
  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="flex items-center gap-4 rounded-lg border p-4">
            <Skeleton className="size-10 rounded-full" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-3 w-48" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  // 2. ERROR — message + retry action
  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-16">
        <AlertCircle className="size-12 text-destructive" />
        <p className="text-sm text-muted-foreground">{error.message}</p>
        <Button variant="outline" onClick={() => refetch()}>
          <RefreshCw className="mr-2 size-4" /> Try again
        </Button>
      </div>
    );
  }

  // 3. EMPTY — icon + message + CTA
  if (!data?.length) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-16 text-center">
        <div className="rounded-full bg-muted p-4">
          <Inbox className="size-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">No items yet</h3>
        <p className="max-w-sm text-sm text-muted-foreground">
          Get started by creating your first item.
        </p>
        <Button onClick={openCreateDialog}>
          <Plus className="mr-2 size-4" /> Create item
        </Button>
      </div>
    );
  }

  // 4. DATA — the actual content
  return (
    <div className="space-y-3">
      {data.map((item) => (
        <ResourceCard key={item.id} item={item} />
      ))}
    </div>
  );
}
```

---
## Professional Polish Patterns

### Interactive Elements — ALL must have these states
```tsx
// Button baseline (shadcn provides most of this)
"transition-colors duration-200"
"hover:bg-accent hover:text-accent-foreground"     // Hover
"focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"  // Focus
"disabled:pointer-events-none disabled:opacity-50"  // Disabled
"active:scale-[0.98]"                               // Press feedback (optional)
```

### Card Structure
```tsx
<Card className="overflow-hidden">
  <CardHeader className="pb-3">
    <CardTitle className="text-lg">{title}</CardTitle>
    <CardDescription>{subtitle}</CardDescription>
  </CardHeader>
  <CardContent className="space-y-4">
    {/* Content with consistent internal spacing */}
  </CardContent>
  <CardFooter className="flex justify-end gap-2 border-t bg-muted/50 px-6 py-3">
    <Button variant="outline">Cancel</Button>
    <Button>Save</Button>
  </CardFooter>
</Card>
```

### Page Layout Structure
```tsx
<div className="space-y-6">
  {/* Page header */}
  <div className="flex items-center justify-between">
    <div>
      <h1 className="text-3xl font-bold tracking-tight">Page Title</h1>
      <p className="text-muted-foreground">Page description here.</p>
    </div>
    <Button><Plus className="mr-2 size-4" /> Create</Button>
  </div>

  {/* Content sections with consistent gap */}
  <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
    {/* Cards or content blocks */}
  </div>
</div>
```

---

## Anti-Patterns (NEVER DO)

| Never Do | Instead Do |
|----------|-----------|
| `<div onClick={fn}>` | `<button onClick={fn}>` or `<Button>` |
| `style={{ color: 'red' }}` | `className="text-destructive"` |
| `bg-blue-500`, `text-gray-700` | `bg-primary`, `text-muted-foreground` |
| `w-[347px]`, `mt-[13px]` | `w-full max-w-sm`, `mt-3` |
| `outline-none` (removing focus) | `focus-visible:ring-2 ring-ring` |
| Generic spinner for all loading | Skeleton screen matching content layout |
| Blank screen when empty | Empty state with icon + message + CTA |
| `"Error"` with no context | Specific error message + retry action |
| Fetch in `useEffect` | TanStack Query `useQuery` |
| Store API data in `useState` | Let TanStack Query cache manage it |
| Mix component libraries | Use ONLY shadcn/ui primitives |
| Create CSS when Tailwind class exists | Use the Tailwind utility |
| Skip TypeScript types for API data | Type every API response shape |
| `<img>` without alt text | `alt="Description"` or `alt=""` for decorative |
