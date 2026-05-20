# Tailwind CSS utility patterns for layout, spacing, and responsive design.

## Layout: Flexbox
```html
<!-- Row with centered items and gap -->
<div class="flex items-center gap-4">
  <Avatar />
  <span>Alice</span>
</div>

<!-- Column layout -->
<div class="flex flex-col gap-2">
  <Label>Email</Label>
  <Input />
</div>

<!-- Space between (header pattern) -->
<header class="flex items-center justify-between px-6 py-4">
  <Logo />
  <Nav />
</header>

<!-- Wrap items -->
<div class="flex flex-wrap gap-2">
  {tags.map(tag => <Badge key={tag}>{tag}</Badge>)}
</div>
```

## Layout: Grid
```html
<!-- Equal columns -->
<div class="grid grid-cols-3 gap-6">
  <Card /><Card /><Card />
</div>

<!-- Responsive columns -->
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
  {items.map(item => <Card key={item.id} />)}
</div>

<!-- Sidebar layout -->
<div class="grid grid-cols-[250px_1fr] gap-0">
  <aside class="border-r">Sidebar</aside>
  <main>Content</main>
</div>
```

## Spacing
```html
<!-- Padding -->
<div class="p-4">          <!-- 1rem all sides -->
<div class="px-6 py-3">    <!-- horizontal 1.5rem, vertical 0.75rem -->
<div class="pt-8">          <!-- top 2rem -->

<!-- Margin -->
<div class="mt-4">          <!-- top 1rem -->
<div class="mx-auto">       <!-- center horizontally -->
<div class="space-y-4">     <!-- 1rem gap between children (vertical stack) -->

<!-- Common scale: 0=0, 1=0.25rem, 2=0.5rem, 3=0.75rem, 4=1rem, 6=1.5rem, 8=2rem, 12=3rem, 16=4rem -->
```

## Responsive Breakpoints
```html
<!-- Mobile-first: base styles, then override at breakpoints -->
<div class="text-sm md:text-base lg:text-lg">Responsive text</div>

<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
  <!-- 1 col on mobile, 2 on sm (640px), 4 on lg (1024px) -->
</div>

<nav class="hidden md:flex">Desktop nav</nav>
<nav class="flex md:hidden">Mobile nav</nav>

<!-- Breakpoints: sm=640px, md=768px, lg=1024px, xl=1280px, 2xl=1536px -->
```

## Typography
```html
<h1 class="text-3xl font-bold tracking-tight">Title</h1>
<p class="text-sm text-muted-foreground">Subtitle text</p>
<p class="text-base leading-7">Body paragraph with relaxed line height</p>
<span class="text-xs font-medium uppercase tracking-wide">Label</span>
<p class="line-clamp-2">Truncate after two lines...</p>
```

## Colors and Dark Mode
```html
<!-- Use semantic color names from shadcn/ui theme -->
<div class="bg-background text-foreground">
<div class="bg-muted text-muted-foreground">
<div class="bg-primary text-primary-foreground">
<div class="border border-border rounded-lg">
<div class="bg-destructive text-destructive-foreground">

<!-- Dark mode with class strategy -->
<div class="bg-white dark:bg-slate-900">
<p class="text-gray-900 dark:text-gray-100">
```

## Common Patterns
```html
<!-- Card -->
<div class="rounded-lg border bg-card p-6 shadow-sm">

<!-- Badge / Chip -->
<span class="inline-flex items-center rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-800">
  Active
</span>

<!-- Full-page centered content -->
<div class="flex min-h-screen items-center justify-center">

<!-- Sticky header -->
<header class="sticky top-0 z-50 border-b bg-background/95 backdrop-blur">

<!-- Truncate text -->
<p class="truncate">Very long text that will be cut off...</p>

<!-- Aspect ratio container -->
<div class="aspect-video overflow-hidden rounded-lg">
  <img class="h-full w-full object-cover" src="..." alt="..." />
</div>
```

## The cn() Utility
```typescript
// lib/utils.ts — used everywhere with shadcn/ui
import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// Usage: merge conditional and override classes safely
<div className={cn(
  "flex items-center gap-2 rounded-md p-3",
  variant === "error" && "bg-destructive text-destructive-foreground",
  className  // allow parent to override
)} />
```

## Tailwind Config Customization
```typescript
// tailwind.config.ts
import type { Config } from "tailwindcss"

export default {
  darkMode: "class",
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eff6ff",
          500: "#3b82f6",
          900: "#1e3a5f",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      animation: {
        "fade-in": "fadeIn 0.3s ease-out",
      },
      keyframes: {
        fadeIn: { from: { opacity: "0" }, to: { opacity: "1" } },
      },
    },
  },
} satisfies Config
```

## Professional Polish Patterns

### Interactive States (apply to ALL clickable elements)
```tsx
// Button/link hover + focus + disabled + transition
"transition-colors duration-200 hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50"

// Card hover effect
"transition-shadow hover:shadow-md"

// Row hover
"transition-colors hover:bg-muted/50"
```

### Shadow Hierarchy
```
shadow-sm   → cards, elevated surfaces
shadow-md   → dropdowns, popovers
shadow-lg   → modals, dialogs, sheets
shadow-none → flat elements within cards
```

### Group Tailwind Classes Logically
```tsx
<div className={cn(
  // Layout
  "flex items-center justify-between gap-4",
  // Sizing
  "h-16 w-full px-4",
  // Visual
  "rounded-lg border bg-card shadow-sm",
  // Typography
  "text-sm font-medium text-card-foreground",
  // Interactive
  "transition-shadow hover:shadow-md",
  // Responsive
  "md:h-20 md:px-6"
)}>
```

## Dark Mode (class strategy)
```css
/* globals.css — light and dark tokens */
@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 222.2 84% 4.9%;
    --card: 0 0% 100%;
    --primary: 222.2 47.4% 11.2%;
    --muted: 210 40% 96.1%;
    --muted-foreground: 215.4 16.3% 46.9%;
    /* ... all tokens */
  }
  .dark {
    --background: 222.2 84% 4.9%;
    --foreground: 210 40% 98%;
    --card: 222.2 84% 4.9%;
    --primary: 210 40% 98%;
    --muted: 217.2 32.6% 17.5%;
    --muted-foreground: 215 20.2% 65.1%;
  }
}
```

Use `next-themes` for theme switching:
```tsx
import { useTheme } from "next-themes"
const { theme, setTheme } = useTheme()
<Button variant="ghost" size="icon" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
  <Sun className="size-4 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
  <Moon className="absolute size-4 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
</Button>
```

## Anti-Patterns (NEVER DO)

| Never Do | Instead Do |
|----------|-----------|
| `bg-blue-500`, `text-gray-700` | `bg-primary`, `text-muted-foreground` |
| `w-[347px]`, `mt-[13px]` | `w-full max-w-sm`, `mt-3` |
| `outline-none` without replacement | `focus-visible:ring-2 ring-ring ring-offset-2` |
| `style={{ marginTop: '16px' }}` | `className="mt-4"` |
| 20+ classes on one line | Group logically in `cn()` with comments |
| `@apply` for everything | Extract React components instead |
| `gap-3` then `gap-4` then `gap-5` randomly | Pick ONE default gap (`gap-4`) for consistency |
| `bg-white dark:bg-black` | `bg-background` (uses CSS variable, auto dark mode) |
| String concatenation for classes | `cn()` from `@/lib/utils` |
| Mixing `space-y-*` and `gap-*` in same container | Pick one: `gap-*` on flex/grid, `space-y-*` on simple stacks |

## Rules
- Mobile-first: write base styles for small screens, add `sm:`, `md:`, `lg:` for larger
- Use `cn()` for conditional classes — never string concatenation or template literals
- Use semantic color tokens (`bg-primary`, `text-muted-foreground`) over raw colors (`bg-blue-500`)
- Use `gap-*` on flex/grid containers instead of margins on children
- Use `space-y-*` or `space-x-*` for simple vertical/horizontal stacks without flex
- Prefer `rounded-lg border` over `shadow-*` — shadows should be subtle (`shadow-sm`)
- Every `bg-*` must pair with its `text-*-foreground` counterpart
- Stick to the 4px spacing scale: `gap-1` (4px), `gap-2` (8px), `gap-4` (16px), `gap-6` (24px), `gap-8` (32px)
- All interactive elements need `transition-colors duration-200` for smooth state changes
