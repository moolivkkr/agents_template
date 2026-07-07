---
skill: svelte
description: SvelteKit patterns — file-based routing, load functions, runes ($state/$derived/$effect), form actions, and server/client data boundaries
version: "1.0"
tags:
  - svelte
  - sveltekit
  - frontend
  - runes
  - ssr
---

# SvelteKit patterns for reactive, server-rendered frontends.

## Routing & Structure
File-based routing under `src/routes/`. `+page.svelte` renders; `+page.ts`/`+page.server.ts` load data; `+layout.svelte` wraps children.

```
src/routes/
  +layout.svelte          # app shell
  users/
    +page.svelte          # /users
    +page.server.ts       # load() runs on server
    [id]/
      +page.svelte        # /users/:id
      +page.ts            # load() runs on server + client
```

## Load Functions
```ts
// +page.server.ts — server-only (DB, secrets); never shipped to client
import type { PageServerLoad } from './$types';
export const load: PageServerLoad = async ({ params, fetch }) => {
  const res = await fetch(`/api/v1/users/${params.id}`);
  if (!res.ok) throw error(res.status, 'user not found');
  return { user: await res.json() };
};
```

- `+page.server.ts` for anything touching secrets/DB; `+page.ts` for universal (public) loads
- Return plain serializable data — it is streamed to the client
- Throw `error(status, msg)` / `redirect(status, location)` from `@sveltejs/kit`, don't return them

## Runes (Svelte 5 reactivity)
```svelte
<script lang="ts">
  let count = $state(0);                       // reactive state
  let doubled = $derived(count * 2);           // computed
  $effect(() => { console.log(count); });      // side effect on change
  let { user } = $props();                     // component props
</script>
<button onclick={() => count++}>{count} / {doubled}</button>
```

- Use `$state` for mutable local state, `$derived` for computed values (never recompute manually)
- `$effect` is for side effects only — not for deriving state (that's `$derived`)
- Prefer runes over legacy `$:` reactive statements in new code

## Form Actions
```ts
// +page.server.ts
export const actions = {
  create: async ({ request }) => {
    const data = await request.formData();
    const parsed = schema.safeParse(Object.fromEntries(data));
    if (!parsed.success) return fail(422, { errors: parsed.error.flatten() });
    await db.users.create(parsed.data);
    return { success: true };
  }
};
```

- Progressive enhancement: `<form method="POST" use:enhance>` works with and without JS
- Return `fail(status, data)` for validation errors — keeps the form state
- Validate server-side always; client validation is UX, not security

## Rules
- Keep secrets in `$env/static/private` / `$env/dynamic/private` — never import into client code
- Data flows down via `load` → `data` prop; mutations go up via form actions or `fetch`
- Set page metadata with `<svelte:head>`; guard routes in `+layout.server.ts` load
- Use `$app/state` (or `$app/stores`) for `page`, `navigating` — don't hand-roll routing state
