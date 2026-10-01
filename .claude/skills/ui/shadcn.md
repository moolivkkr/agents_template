---
skill: shadcn
description: shadcn/ui patterns for composable, accessible React components — install, theming, and component usage conventions
version: "1.0"
tags:
  - shadcn
  - components
  - react
  - tailwind
  - ui
---

# shadcn/ui patterns for composable, accessible React components.

> Code samples compile-checked: tsc (TypeScript 7.0.2, strict + noUncheckedIndexedAccess) against React 19.3, radix-ui 1.6, lucide-react 1.49, sonner 2.0, react-hook-form 7.89 and Zod 4.6, with shadcn/ui component stubs (Field copied from the registry); the Field + Controller form ran in 1 Vitest 5.0.3 test; the theme override CSS was built by `next build` (Next.js 16.3.8, @tailwindcss/postcss 4.3.3) and its tokens checked by computed style in Chrome (`tests/archetype-compile/ui-packs/run.sh`, 2026-09-30).

## Install and Add Components
```bash
# Initialize shadcn/ui in a project
npx shadcn@latest init

# Add individual components (copies source into your project)
npx shadcn@latest add button
npx shadcn@latest add dialog
npx shadcn@latest add field      # forms: Field + react-hook-form Controller (see below)
npx shadcn@latest add input
npx shadcn@latest add table
npx shadcn@latest add select
npx shadcn@latest add dropdown-menu
npx shadcn@latest add sonner     # toasts: the CLI marks "toast" deprecated by "sonner" (shadcn 4.21)
npx shadcn@latest add card
npx shadcn@latest add tabs
```
- Components are copied to `src/components/ui/` — you own the source, customize freely
- Run `add` again to update a component to the latest version (overwrites local changes)

## Button Variants
```tsx
import { Button } from "@/components/ui/button"

<Button variant="default">Save</Button>
<Button variant="destructive">Delete</Button>
<Button variant="outline">Cancel</Button>
<Button variant="ghost">Settings</Button>
<Button variant="link">Learn more</Button>
<Button size="sm">Small</Button>
<Button size="icon" aria-label="Delete"><TrashIcon className="h-4 w-4" /></Button>
<Button disabled>Saving...</Button>
<Button asChild><Link href="/dashboard">Go</Link></Button>
```

## Dialog
```tsx
import {
  Dialog, DialogContent, DialogDescription,
  DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog"

<Dialog>
  <DialogTrigger asChild>
    <Button variant="outline">Edit Profile</Button>
  </DialogTrigger>
  <DialogContent className="sm:max-w-[425px]">
    <DialogHeader>
      <DialogTitle>Edit profile</DialogTitle>
      <DialogDescription>Make changes and click save.</DialogDescription>
    </DialogHeader>
    <form onSubmit={handleSubmit}>
      <Input id="name" defaultValue={user.name} />
      <DialogFooter>
        <Button type="submit">Save changes</Button>
      </DialogFooter>
    </form>
  </DialogContent>
</Dialog>
```

## Form with react-hook-form + zod (`Field` + `Controller`)
shadcn's form guides (React Hook Form, TanStack Form) build fields from the `Field` primitives with the form
library's own `Controller`, not the older `Form` / `FormField` / `FormItem` / `FormControl` / `FormMessage`
wrapper. `form` is still in the registry with no deprecation flag (checked 2026-09-30), so an existing
project that uses it keeps working; new forms use `Field` (`npx shadcn@latest add field`).
```tsx
import { Controller, useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

const schema = z.object({
  email: z.email("Invalid email"),
  name: z.string().min(2, "Name must be at least 2 characters"),
})
type CreateUserValues = z.infer<typeof schema>

export function CreateUserForm({ onCreate }: { onCreate: (values: CreateUserValues) => void }) {
  const form = useForm<CreateUserValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", name: "" },
  })

  return (
    <form onSubmit={form.handleSubmit(onCreate)} noValidate>
      <FieldGroup>
        <Controller
          control={form.control}
          name="email"
          render={({ field, fieldState }) => (
            <Field data-invalid={fieldState.invalid}>
              <FieldLabel htmlFor="create-user-email">Email</FieldLabel>
              <Input {...field} id="create-user-email" placeholder="alice@example.com" aria-invalid={fieldState.invalid} />
              {fieldState.invalid && <FieldError errors={[fieldState.error]} />}
            </Field>
          )}
        />
        {/* every field in the schema needs its own Controller, or the form can never pass validation */}
        <Controller
          control={form.control}
          name="name"
          render={({ field, fieldState }) => (
            <Field data-invalid={fieldState.invalid}>
              <FieldLabel htmlFor="create-user-name">Name</FieldLabel>
              <Input {...field} id="create-user-name" placeholder="Alice" aria-invalid={fieldState.invalid} />
              {fieldState.invalid && <FieldError errors={[fieldState.error]} />}
            </Field>
          )}
        />
        <Button type="submit">Create</Button>
      </FieldGroup>
    </form>
  )
}
```

## Data Table
```tsx
import {
  Table, TableBody, TableCell, TableHead,
  TableHeader, TableRow,
} from "@/components/ui/table"

<Table>
  <TableHeader>
    <TableRow>
      <TableHead>Name</TableHead>
      <TableHead>Email</TableHead>
      <TableHead className="text-right">Actions</TableHead>
    </TableRow>
  </TableHeader>
  <TableBody>
    {users.map((user) => (
      <TableRow key={user.id}>
        <TableCell className="font-medium">{user.name}</TableCell>
        <TableCell>{user.email}</TableCell>
        <TableCell className="text-right">
          <Button variant="ghost" size="sm">Edit</Button>
        </TableCell>
      </TableRow>
    ))}
  </TableBody>
</Table>
```

## Theming and Customization
Tailwind CSS v4: the tokens are full `oklch(…)` colors in `:root` / `.dark`, mapped to utilities by
`@theme inline` (the whole generated file: `tailwind.md` §Dark Mode). To theme, change the values after the
generated blocks; the `@theme inline` mapping stays as `init` wrote it. Give every color you override a
`.dark` value too: `:root` and `.dark` have the same specificity, so a `:root` override placed after the
generated `.dark` block also wins in dark mode.
```css
/* app/globals.css — overrides, after the :root / .dark blocks `shadcn init` generated */
:root {
  --primary: oklch(0.488 0.243 264.376);       /* Tailwind blue-700 */
  --primary-foreground: oklch(0.985 0 0);
  --radius: 0.5rem;                            /* rounded-lg = 0.5rem; sm/md/xl… scale from it */
}
.dark {
  --primary: oklch(0.707 0.165 254.624);       /* blue-400 */
  --primary-foreground: oklch(0.205 0 0);
}
```

```typescript
// Extend with className — Tailwind classes merge via cn()
<Button className="w-full mt-4">Full Width</Button>
<Card className="border-none shadow-lg">Custom Card</Card>
```

## Composition with asChild
```tsx
// asChild passes props to child element instead of rendering default tag
<Button asChild>
  <Link href="/settings">Settings</Link>     {/* renders <a>, not <button> */}
</Button>

<DialogTrigger asChild>
  <Button variant="outline">Open</Button>    {/* attaches dialog trigger to Button */}
</DialogTrigger>
```

## Skeleton (Loading State)
```tsx
import { Skeleton } from "@/components/ui/skeleton"

// Match the layout of loaded content
<Skeleton className="h-4 w-[250px]" />           {/* Text line */}
<Skeleton className="h-10 w-full" />              {/* Input field */}
<Skeleton className="size-10 rounded-full" />     {/* Avatar */}
<Skeleton className="h-[200px] w-full rounded-lg" /> {/* Image/card */}
```

## Sheet (Mobile Navigation / Side Panels)
```tsx
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"

<Sheet>
  <SheetTrigger asChild>
    <Button variant="ghost" size="icon" className="md:hidden">
      <Menu className="size-5" />
      <span className="sr-only">Open menu</span>
    </Button>
  </SheetTrigger>
  <SheetContent side="left" className="w-64">
    <SheetHeader><SheetTitle>Navigation</SheetTitle></SheetHeader>
    <nav className="flex flex-col gap-2 pt-4">
      <Link href="/dashboard">Dashboard</Link>
      <Link href="/settings">Settings</Link>
    </nav>
  </SheetContent>
</Sheet>
```

## AlertDialog (Destructive Confirmations)
```tsx
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel,
  AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from "@/components/ui/alert-dialog"

<AlertDialog>
  <AlertDialogTrigger asChild>
    <Button variant="destructive">Delete</Button>
  </AlertDialogTrigger>
  <AlertDialogContent>
    <AlertDialogHeader>
      <AlertDialogTitle>Are you sure?</AlertDialogTitle>
      <AlertDialogDescription>This action cannot be undone.</AlertDialogDescription>
    </AlertDialogHeader>
    <AlertDialogFooter>
      <AlertDialogCancel>Cancel</AlertDialogCancel>
      <AlertDialogAction onClick={handleDelete}>Delete</AlertDialogAction>
    </AlertDialogFooter>
  </AlertDialogContent>
</AlertDialog>
```

## Badge Variants
```tsx
import { Badge } from "@/components/ui/badge"

<Badge>Default</Badge>
<Badge variant="secondary">Draft</Badge>
<Badge variant="outline">Pending</Badge>
<Badge variant="destructive">Overdue</Badge>
```

## Avatar with Fallback
```tsx
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"

<Avatar>
  {/* wire field name from the contract (snake_case); a URL from data goes through safeHref (secure-rendering.md) */}
  <AvatarImage src={safeHref(user.avatar_url)} alt={user.name} />
  <AvatarFallback>{user.name.slice(0, 2).toUpperCase()}</AvatarFallback>
</Avatar>
```

## Tooltip
```tsx
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"

<TooltipProvider>
  <Tooltip>
    <TooltipTrigger asChild>
      <Button variant="ghost" size="icon" aria-label="Settings">
        <Settings className="size-4" />
      </Button>
    </TooltipTrigger>
    <TooltipContent><p>Settings</p></TooltipContent>
  </Tooltip>
</TooltipProvider>
```

## DropdownMenu
```tsx
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

<DropdownMenu>
  <DropdownMenuTrigger asChild>
    <Button variant="ghost" size="icon" aria-label="Actions">
      <MoreHorizontal className="size-4" />
    </Button>
  </DropdownMenuTrigger>
  <DropdownMenuContent align="end">
    <DropdownMenuItem>Edit</DropdownMenuItem>
    <DropdownMenuItem>Duplicate</DropdownMenuItem>
    <DropdownMenuSeparator />
    <DropdownMenuItem className="text-destructive">Delete</DropdownMenuItem>
  </DropdownMenuContent>
</DropdownMenu>
```

## Toast (Sonner)
```tsx
import { toast } from "sonner"

toast.success("Changes saved");
toast.error("Failed to save", { description: "Check your connection." });
toast.promise(saveData(payload), {
  loading: "Saving...",
  success: "Done!",
  error: "Failed",
});
```

## Card Composition
```tsx
<Card>
  <CardHeader className="pb-3">
    <CardTitle>Title</CardTitle>
    <CardDescription>Subtitle text</CardDescription>
  </CardHeader>
  <CardContent className="space-y-4">{/* Content */}</CardContent>
  <CardFooter className="flex justify-end gap-2 border-t bg-muted/50 px-6 py-3">
    <Button variant="outline">Cancel</Button>
    <Button>Save</Button>
  </CardFooter>
</Card>
```

## Rules
- Always use the `cn()` utility (from `lib/utils`) to merge Tailwind classes — never concatenate strings
- Use `asChild` when you need a different underlying element (Link as Button, etc.)
- Override styling via `className` prop and CSS variables — do not edit component source for one-off changes
- Forms: one react-hook-form `Controller` per field, rendering `Field` > `FieldLabel` + control + `FieldError`
- Components are unstyled by default — theming is controlled entirely by CSS variables in `globals.css`
- Every `Button` with only an icon MUST have `aria-label` or `sr-only` text
- Use `AlertDialog` for destructive confirmations (delete, remove), NOT regular `Dialog`
- Use `Sheet` for mobile navigation and side panels
- Use `Skeleton` for ALL loading states — match the shape of loaded content
