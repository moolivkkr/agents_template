# Accessibility Patterns — WCAG 2.2 AA Implementation Reference

## Semantic HTML Rules — Decision Table

| User Action | Correct Element | Never Use |
|---|---|---|
| Triggers an action (save, delete, toggle) | `<button>` | `<div onClick>`, `<span onClick>` |
| Navigates to another page/URL | `<a href="...">` | `<button>` for navigation |
| Groups navigation links | `<nav>` | `<div className="nav">` |
| Main page content | `<main>` | `<div className="main">` |
| Page heading hierarchy | `<h1>` → `<h2>` → `<h3>` (sequential) | Skipping levels, multiple `<h1>` |
| Form input | `<input>` with `<label htmlFor>` | `<div contenteditable>` |
| List of items | `<ul>` / `<ol>` with `<li>` | Divs with line breaks |
| Data grid | `<table>` with `<thead>`/`<tbody>` | Grid of divs |

## ARIA Patterns with Code

### Icon-Only Buttons (most common violation)
```tsx
// BAD — screen reader says nothing
<Button variant="ghost" size="icon"><Trash className="size-4" /></Button>

// GOOD — option 1: aria-label
<Button variant="ghost" size="icon" aria-label="Delete item">
  <Trash className="size-4" />
</Button>

// GOOD — option 2: sr-only text
<Button variant="ghost" size="icon">
  <Trash className="size-4" />
  <span className="sr-only">Delete item</span>
</Button>
```

### Form Inputs
```tsx
// GOOD — visible label connected to input
<div className="space-y-2">
  <Label htmlFor="email">Email address</Label>
  <Input id="email" type="email" placeholder="jane@company.com" />
</div>

// GOOD — visually hidden label for search
<div>
  <Label htmlFor="search" className="sr-only">Search users</Label>
  <Input id="search" placeholder="Search..." />
</div>
```

### Dynamic Content Updates
```tsx
// Toast notifications — Sonner handles role="status" automatically

// Search results count — announce to screen readers
<p aria-live="polite" aria-atomic="true" className="text-sm text-muted-foreground">
  {results.length} results found
</p>

// Error alerts — announce immediately
<div role="alert" className="text-sm text-destructive">
  {error.message}
</div>
```

### Expandable Sections
```tsx
<Button
  variant="ghost"
  onClick={() => setExpanded(!expanded)}
  aria-expanded={expanded}
  aria-controls="details-panel"
>
  Details <ChevronDown className={cn("size-4 transition-transform", expanded && "rotate-180")} />
</Button>
<div id="details-panel" hidden={!expanded}>
  {/* Expandable content */}
</div>
```

### Modal/Dialog Focus Management
```tsx
// shadcn Dialog handles automatically via Radix:
// ✅ Focus moves to dialog on open
// ✅ Tab is trapped within dialog
// ✅ Escape closes dialog
// ✅ Focus returns to trigger on close
// ✅ aria-modal="true" and role="dialog" set

// ALWAYS use shadcn Dialog/Sheet/AlertDialog — never build custom modals
```

## Keyboard Navigation Checklist

| Element | Tab | Enter | Escape | Arrow Keys |
|---------|-----|-------|--------|------------|
| Button | Focus | Activate | — | — |
| Link | Focus | Navigate | — | — |
| Dialog | — | — | Close | — |
| Dropdown menu | Open | Select item | Close | Navigate items |
| Tabs | Focus tab list | — | — | Switch tabs |
| Select | Open | Select | Close | Navigate options |

## Color & Contrast

```
Minimum contrast ratios (WCAG AA):
- Normal text (<18px): 4.5:1
- Large text (≥18px bold or ≥24px): 3:1
- UI components (borders, icons): 3:1
- Placeholder text: 4.5:1 (commonly violated!)

Common failures:
- text-muted-foreground on bg-muted — CHECK contrast
- Placeholder text too light
- Disabled elements (exempt from contrast but must be distinguishable)
```

## Required Page Elements

```tsx
// 1. Skip navigation link (first element in body)
<a href="#main-content"
   className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:p-4 focus:bg-background">
  Skip to main content
</a>

// 2. Language attribute
<html lang="en">

// 3. Main landmark
<main id="main-content">{children}</main>

// 4. Heading hierarchy — one h1 per page, sequential levels
<h1>Users</h1>
  <h2>Active Users</h2>
    <h3>Admins</h3>
  <h2>Inactive Users</h2>
```

## Anti-Patterns

| Never Do | Instead Do |
|----------|-----------|
| `outline-none` without replacement | `focus-visible:ring-2 ring-ring ring-offset-2` |
| Color alone to convey meaning | Color + icon + text (e.g., red + warning icon + "Error") |
| `<div onClick>` for buttons | `<button>` or `<Button>` |
| Auto-playing media | Require user action to play |
| `tabIndex > 0` | Natural DOM order or `tabIndex={0}` |
| Nested interactive elements | Separate click targets |
| Missing alt text on images | `alt="Description"` or `alt=""` for decorative |
| Heading level skips (h1 → h3) | Sequential: h1 → h2 → h3 |
