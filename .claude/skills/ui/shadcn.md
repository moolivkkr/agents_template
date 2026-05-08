# shadcn/ui patterns for composable, accessible React components.

## Install and Add Components
```bash
# Initialize shadcn/ui in a project
npx shadcn@latest init

# Add individual components (copies source into your project)
npx shadcn@latest add button
npx shadcn@latest add dialog
npx shadcn@latest add form
npx shadcn@latest add input
npx shadcn@latest add table
npx shadcn@latest add select
npx shadcn@latest add dropdown-menu
npx shadcn@latest add toast
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
<Button size="icon"><TrashIcon className="h-4 w-4" /></Button>
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

## Form with react-hook-form + zod
```tsx
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import {
  Form, FormControl, FormField, FormItem,
  FormLabel, FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"

const schema = z.object({
  email: z.string().email("Invalid email"),
  name: z.string().min(2, "Name must be at least 2 characters"),
})

export function CreateUserForm() {
  const form = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", name: "" },
  })

  function onSubmit(values: z.infer<typeof schema>) {
    // handle submit
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <FormField
          control={form.control}
          name="email"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Email</FormLabel>
              <FormControl>
                <Input placeholder="alice@example.com" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <Button type="submit">Create</Button>
      </form>
    </Form>
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
```css
/* globals.css — override CSS variables for theming */
@layer base {
  :root {
    --primary: 222.2 47.4% 11.2%;
    --primary-foreground: 210 40% 98%;
    --destructive: 0 84.2% 60.2%;
    --radius: 0.5rem;
  }
  .dark {
    --primary: 210 40% 98%;
    --primary-foreground: 222.2 47.4% 11.2%;
  }
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

## Rules
- Always use the `cn()` utility (from `lib/utils`) to merge Tailwind classes — never concatenate strings
- Use `asChild` when you need a different underlying element (Link as Button, etc.)
- Override styling via `className` prop and CSS variables — do not edit component source for one-off changes
- Form components expect react-hook-form — always pair `FormField` with a `control` prop
- Components are unstyled by default — theming is controlled entirely by CSS variables in `globals.css`
