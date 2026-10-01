---
skill: tailwind
description: Tailwind CSS utility patterns for layout, spacing, flex/grid, and responsive design
version: "1.0"
tags:
  - tailwind
  - css
  - layout
  - responsive
  - ui
---

# Tailwind CSS utility patterns for layout, spacing, and responsive design.

> Code samples compile-checked: tsc (TypeScript 7.0.2, strict + noUncheckedIndexedAccess) against tailwindcss 4.3.3's `Config` type, tailwind-merge 3.7, clsx 2.1 and next-themes 0.4.6; the token CSS (generated file + app tokens) built by `next build` (Next.js 16.3.8, @tailwindcss/postcss 4.3.3, shadcn 4.21's `shadcn/tailwind.css`) and checked in 4 Playwright 1.63 tests on Chrome (each token utility's computed color in light and dark, radius, axe contrast); the class-string list skipped (`tests/archetype-compile/ui-packs/run.sh`, 2026-09-30).

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
<div class="bg-destructive text-white">  <!-- shadcn v4 has no --destructive-foreground -->

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
  variant === "error" && "bg-destructive text-white",
  className  // allow parent to override
)} />
```

## Tailwind Config Customization
Tailwind CSS v4 (4.3 is current) is configured in CSS: `@import "tailwindcss";`, theme values in an
`@theme { --color-brand-500: #3b82f6; }` block, and `@custom-variant dark (&:where(.dark, .dark *));` for the
class strategy. A JavaScript config like the one below still works, but v4 only loads it through
`@config "../tailwind.config.ts";` in that CSS file. New projects use `@theme`.
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
)} />
```

## Dark Mode (class strategy) and the token file
This is the `globals.css` that `npx shadcn@latest init` writes for Tailwind CSS v4 (shadcn 4.21, "neutral"
base color). Tokens are full colors (`oklch(…)`), not the bare HSL triplets of the Tailwind v3 era
(`--primary: 222.2 47.4% 11.2%` + `hsl(var(--primary))`). `@theme inline` maps each token to a Tailwind color
(`--color-primary` → `bg-primary`, `text-primary`, `bg-primary/50`) and keeps the `var()` reference, so the
`.dark` values apply wherever the `dark` variant's class is set.
```css
/* app/globals.css — written by `npx shadcn@latest init` for Tailwind CSS v4 (shadcn 4.21, neutral) */
@import "tailwindcss";
@import "shadcn/tailwind.css";

@custom-variant dark (&:is(.dark *));

@theme inline {
  --color-background: var(--background);
  --color-foreground: var(--foreground);
  --color-card: var(--card);
  --color-card-foreground: var(--card-foreground);
  --color-popover: var(--popover);
  --color-popover-foreground: var(--popover-foreground);
  --color-primary: var(--primary);
  --color-primary-foreground: var(--primary-foreground);
  --color-secondary: var(--secondary);
  --color-secondary-foreground: var(--secondary-foreground);
  --color-muted: var(--muted);
  --color-muted-foreground: var(--muted-foreground);
  --color-accent: var(--accent);
  --color-accent-foreground: var(--accent-foreground);
  --color-destructive: var(--destructive);
  --color-border: var(--border);
  --color-input: var(--input);
  --color-ring: var(--ring);
  --color-chart-1: var(--chart-1);
  --color-chart-2: var(--chart-2);
  --color-chart-3: var(--chart-3);
  --color-chart-4: var(--chart-4);
  --color-chart-5: var(--chart-5);
  --color-sidebar: var(--sidebar);
  --color-sidebar-foreground: var(--sidebar-foreground);
  --color-sidebar-primary: var(--sidebar-primary);
  --color-sidebar-primary-foreground: var(--sidebar-primary-foreground);
  --color-sidebar-accent: var(--sidebar-accent);
  --color-sidebar-accent-foreground: var(--sidebar-accent-foreground);
  --color-sidebar-border: var(--sidebar-border);
  --color-sidebar-ring: var(--sidebar-ring);
  --radius-sm: calc(var(--radius) * 0.6);
  --radius-md: calc(var(--radius) * 0.8);
  --radius-lg: var(--radius);
  --radius-xl: calc(var(--radius) * 1.4);
  --radius-2xl: calc(var(--radius) * 1.8);
  --radius-3xl: calc(var(--radius) * 2.2);
  --radius-4xl: calc(var(--radius) * 2.6);
}

:root {
  --radius: 0.625rem;
  --background: oklch(1 0 0);
  --foreground: oklch(0.145 0 0);
  --card: oklch(1 0 0);
  --card-foreground: oklch(0.145 0 0);
  --popover: oklch(1 0 0);
  --popover-foreground: oklch(0.145 0 0);
  --primary: oklch(0.205 0 0);
  --primary-foreground: oklch(0.985 0 0);
  --secondary: oklch(0.97 0 0);
  --secondary-foreground: oklch(0.205 0 0);
  --muted: oklch(0.97 0 0);
  --muted-foreground: oklch(0.556 0 0);
  --accent: oklch(0.97 0 0);
  --accent-foreground: oklch(0.205 0 0);
  --destructive: oklch(0.577 0.245 27.325);
  --border: oklch(0.922 0 0);
  --input: oklch(0.922 0 0);
  --ring: oklch(0.708 0 0);
  --chart-1: oklch(0.646 0.222 41.116);
  --chart-2: oklch(0.6 0.118 184.704);
  --chart-3: oklch(0.398 0.07 227.392);
  --chart-4: oklch(0.828 0.189 84.429);
  --chart-5: oklch(0.769 0.188 70.08);
  --sidebar: oklch(0.985 0 0);
  --sidebar-foreground: oklch(0.145 0 0);
  --sidebar-primary: oklch(0.205 0 0);
  --sidebar-primary-foreground: oklch(0.985 0 0);
  --sidebar-accent: oklch(0.97 0 0);
  --sidebar-accent-foreground: oklch(0.205 0 0);
  --sidebar-border: oklch(0.922 0 0);
  --sidebar-ring: oklch(0.708 0 0);
}

.dark {
  --background: oklch(0.145 0 0);
  --foreground: oklch(0.985 0 0);
  --card: oklch(0.205 0 0);
  --card-foreground: oklch(0.985 0 0);
  --popover: oklch(0.205 0 0);
  --popover-foreground: oklch(0.985 0 0);
  --primary: oklch(0.922 0 0);
  --primary-foreground: oklch(0.205 0 0);
  --secondary: oklch(0.269 0 0);
  --secondary-foreground: oklch(0.985 0 0);
  --muted: oklch(0.269 0 0);
  --muted-foreground: oklch(0.708 0 0);
  --accent: oklch(0.269 0 0);
  --accent-foreground: oklch(0.985 0 0);
  --destructive: oklch(0.704 0.191 22.216);
  --border: oklch(1 0 0 / 10%);
  --input: oklch(1 0 0 / 15%);
  --ring: oklch(0.556 0 0);
  --chart-1: oklch(0.488 0.243 264.376);
  --chart-2: oklch(0.696 0.17 162.48);
  --chart-3: oklch(0.769 0.188 70.08);
  --chart-4: oklch(0.627 0.265 303.9);
  --chart-5: oklch(0.645 0.246 16.439);
  --sidebar: oklch(0.205 0 0);
  --sidebar-foreground: oklch(0.985 0 0);
  --sidebar-primary: oklch(0.488 0.243 264.376);
  --sidebar-primary-foreground: oklch(0.985 0 0);
  --sidebar-accent: oklch(0.269 0 0);
  --sidebar-accent-foreground: oklch(0.985 0 0);
  --sidebar-border: oklch(1 0 0 / 10%);
  --sidebar-ring: oklch(0.556 0 0);
}

@layer base {
  * {
    @apply border-border outline-ring/50;
  }
  body {
    @apply bg-background text-foreground;
  }
}
```

`shadcn/tailwind.css` ships in the `shadcn` package (animations and `data-*` state variants), which `init`
adds as a dependency. There is no `--destructive-foreground` any more: text on `bg-destructive` is `text-white`,
as in shadcn's own Button. A token the design needs beyond this set (status colors such as warning and
success) is added the same way: a value per mode plus a `--color-*` entry. Pick shades with at least 4.5:1
contrast as text on `--card` in both modes (these do, measured by axe):
```css
/* app/globals.css (continued) — app tokens beyond shadcn's: bg-warning, text-success, border-warning/50 … */
:root {
  --warning: oklch(0.555 0.163 48.998);  /* Tailwind amber-700 */
  --success: oklch(0.527 0.154 150.069); /* Tailwind green-700 */
}
.dark {
  --warning: oklch(0.828 0.189 84.429);  /* amber-400 */
  --success: oklch(0.792 0.209 151.711); /* green-400 */
}
@theme inline {
  --color-warning: var(--warning);
  --color-success: var(--success);
}
```

Use `next-themes` for theme switching:
```tsx
import { useTheme } from "next-themes"
const { resolvedTheme, setTheme } = useTheme()   // resolvedTheme: what "system" resolved to
<Button variant="ghost" size="icon" aria-label="Toggle theme" onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}>
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
