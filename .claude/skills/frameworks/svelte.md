---
skill: svelte
description: SvelteKit 2 + Svelte 5 patterns for ui_developer and ui_test_agent — typed client for the one envelope (load fetch + handleFetch), streamed cursor lists and TanStack Svelte Query, the 4 states, Superforms + Zod actions with server details[] on fields, cookie session in hooks, {@html} rules, route focus, Testing Library + MSW + axe tests
version: "2.0"
tags:
  - svelte
  - sveltekit
  - frontend
  - runes
  - ssr
  - superforms
---

# SvelteKit and Svelte 5 patterns

> Verified against Svelte 5.57.1, @sveltejs/kit 2.70.3, sveltekit-superforms 2.31.0, @tanstack/svelte-query 6.3.0, Zod 4.6.5, @testing-library/svelte 5.4.2, MSW 2.15.0, Vitest 5.0.3, svelte-check 4.7.6 and TypeScript 6.0.3 (npm registry and the official docs, 2026-09-30). svelte-check doesn't support TypeScript 7 yet (its peer range is `^5 || ^6`). **Pin `msw@^2.15` for now.** MSW 3 (3.0.0 shipped 2026-09-28) fails under `svelteTesting()`: that plugin adds the `browser` resolve condition, and `@mswjs/interceptors` 0.45 maps `./ClientRequest` to `null` for `browser`, so `msw/node` won't load. Every `file:` block below passes `svelte-check --fail-on-warnings`, and its tests pass: `bash tests/archetype-compile/ui-frameworks/run.sh svelte`.

This pack is the SvelteKit translation of `ui_developer`'s React-flavoured examples. The rules live in the shared packs, which win on conflict: `api/response-envelope.md` (the shape), `ui/secure-rendering.md` (rendering, `safeHref`, `safeReturnTo`), `infrastructure/auth-session-flows.md` (sessions) and `testing/msw.md` (mocks). `$lib/api/types` is the module generated from the contract (envelope plus payload types). `t()` is the project's i18n function (Paraglide, svelte-i18n or an equivalent).

## Routing, load and runes
- Files: `+page.svelte` renders; `+page.ts` is a universal load (it runs on the server and in the browser); `+page.server.ts` is server-only (actions, secrets); `+layout.*` wraps its children; `(group)` folders share a layout without adding a URL segment.
- In components: `let { data }: PageProps = $props()`. Use `$state` for local state, `$derived` for computed values, and `$effect` for side effects only.
- Call `error()` and `redirect()` from `@sveltejs/kit` bare (they throw).
- Secrets come only from `$env/*/private`, never in code that reaches the browser. Remote functions are still `experimental` in Kit 2.70 (behind `kit.experimental.remoteFunctions`), so don't build on them.
- SvelteKit acts as the BFF here. Loads and actions call the API through SvelteKit's `fetch`, and `handleFetch` (§5) routes `/api` to the API service with the user's cookie. In SPA mode (`ssr = false`) the same client runs in the browser against same-origin `/api`.

## 1. Typed API client: unwraps the one envelope

```ts
// file: src/lib/api/client.ts
import { browser } from "$app/environment"
import type { ApiErrorBody, ApiSuccess, FieldError } from "$lib/api/types"

/** Every failed call becomes this: the envelope's error plus the HTTP status (0 = no response). */
export class ApiError extends Error {
  constructor(readonly status: number, readonly code: string, message: string, readonly details: FieldError[] = [],
    readonly requestId?: string, readonly retryable = false) { super(message); this.name = "ApiError" }
}

type Query = Record<string, string | number | null | undefined>
type Init = { query?: Query; body?: unknown; idempotencyKey?: string; signal?: AbortSignal }

/** In load functions and actions pass SvelteKit's `fetch` (cookies, handleFetch); the default is the browser's. */
export function createApi(fetchFn: typeof fetch = fetch) {
  async function send(method: string, path: string, init: Init = {}): Promise<Response> {
    const qs = new URLSearchParams()
    for (const [k, v] of Object.entries(init.query ?? {})) if (v != null) qs.set(k, String(v))
    const headers = new Headers({ Accept: "application/json" })
    if (init.body !== undefined) headers.set("Content-Type", "application/json")
    if (init.idempotencyKey) headers.set("Idempotency-Key", init.idempotencyKey)
    // Double-submit CSRF in the browser; on the server, handleFetch echoes the cookie (§5).
    const csrf = browser ? document.cookie.match(/(?:^|;\s*)XSRF-TOKEN=([^;]+)/)?.[1] : undefined
    if (method !== "GET" && csrf) headers.set("X-XSRF-TOKEN", decodeURIComponent(csrf))
    const q = qs.toString()
    let res: Response
    try {
      const body = init.body === undefined ? undefined : JSON.stringify(init.body)
      res = await fetchFn(`/api/v1${path}${q ? `?${q}` : ""}`, { method, headers, body, credentials: "same-origin", signal: init.signal })
    } catch (e) {
      if (init.signal?.aborted) throw e
      throw new ApiError(0, "NETWORK_ERROR", "Can't reach the server. Check your connection and retry.", [], undefined, true)
    }
    if (res.ok) return res
    const err = ((await res.json().catch(() => null)) as ApiErrorBody | null)?.error // branch on status, never error === null
    throw new ApiError(res.status, err?.code ?? "UNKNOWN", err?.message ?? "Something went wrong.", err?.details ?? [],
      err?.request_id ?? res.headers.get("X-Request-Id") ?? undefined, err?.retryable ?? (res.status === 429 || res.status >= 503))
  }
  const envelope = async <T>(res: Promise<Response>) => (await (await res).json()) as ApiSuccess<T>
  return {
    get: async <T>(path: string, query?: Query) => (await envelope<T>(send("GET", path, { query }))).data,
    /** Lists keep the whole envelope: data is always an array, the cursor is in meta.pagination. */
    list: <T>(path: string, query?: Query, signal?: AbortSignal) => envelope<T[]>(send("GET", path, { query, signal })),
    create: async <T>(path: string, body: unknown, idempotencyKey?: string) =>
      (await envelope<T>(send("POST", path, { body, idempotencyKey }))).data,
    remove: async (path: string) => void (await send("DELETE", path)),
  }
}
```

## 2. Server state: a cursor-paginated list

**Load function (the default).** The cursor lives in the URL, so back, forward and shared links all work.
The promise is returned without `await`, so the page renders its skeleton at once and the list streams in.

```ts
// file: src/routes/(app)/orders/+page.ts
import { createApi } from "$lib/api/client"
import type { Order } from "$lib/api/types"
import type { PageLoad } from "./$types"

export const load: PageLoad = ({ fetch, url, depends }) => {
  depends("app:orders") // invalidate("app:orders") re-runs this load (the retry button)
  const orders = createApi(fetch).list<Order>("/orders", { limit: 20, cursor: url.searchParams.get("cursor") })
  orders.catch(() => {}) // rendered by {:catch}; stops an unhandled rejection before the page awaits it
  return { orders }
}
```

**TanStack Svelte Query** is for "load more" and infinite lists, when the project chose it. v6 is rune-based: options go in a function, and the result is read as `query.data`, not `$query`. Mount `QueryClientProvider` in the root layout (§7), and set `enabled: browser` so queries don't run during SSR.

```ts
// file: src/lib/api/orders-query.ts
import { createInfiniteQuery } from "@tanstack/svelte-query"
import { createApi } from "$lib/api/client"
import type { Order } from "$lib/api/types"

export function createOrdersQuery(status: () => string | undefined) {
  const api = createApi()
  return createInfiniteQuery(() => ({
    queryKey: ["orders", "list", { status: status() }],
    queryFn: ({ pageParam, signal }) => api.list<Order>("/orders", { limit: 20, cursor: pageParam, status: status() }, signal),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => (last.meta.pagination?.has_more ? (last.meta.pagination.next_cursor ?? undefined) : undefined),
  }))
}
```

## 3. The 4 states

The component takes the load's promise and callbacks, so it can be tested without a router.

```svelte
<!-- file: src/lib/components/OrderList.svelte -->
<script lang="ts">
  import { ApiError } from "$lib/api/client"
  import type { ApiSuccess, Order } from "$lib/api/types"
  import { t } from "$lib/i18n"

  type Props = { orders: Promise<ApiSuccess<Order[]>>; onretry: () => void; oncreate: () => void }
  let { orders, onretry, oncreate }: Props = $props()
  const asApiError = (e: unknown) => (e instanceof ApiError ? e : new ApiError(0, "UNKNOWN", t("errors.generic")))
</script>

{#await orders}
  <!-- 1. LOADING: a skeleton shaped like the list, not a spinner -->
  <ul aria-busy="true" aria-label={t("orders.loading")} data-testid="orders-loading">
    {#each [1, 2, 3, 4, 5] as n (n)}<li class="h-14 animate-pulse rounded-md bg-muted"></li>{/each}
  </ul>
{:then res}
  {#if res.data.length === 0}
    <!-- 3. EMPTY (data: []): the design system's icon (aria-hidden), title, description, CTA -->
    <section aria-labelledby="orders-empty-title" data-testid="orders-empty">
      <h2 id="orders-empty-title">{t("orders.empty.title")}</h2>
      <p class="text-muted-foreground">{t("orders.empty.description")}</p>
      <button type="button" onclick={oncreate}>{t("orders.empty.cta")}</button>
    </section>
  {:else}
    <!-- 4. DATA, the next page from meta.pagination.next_cursor -->
    <ul data-testid="orders-table">
      {#each res.data as order (order.id)}<li>{order.customer_name} — {order.status}</li>{/each}
    </ul>
    {#if res.meta.pagination?.has_more && res.meta.pagination.next_cursor}
      <a href={`?${new URLSearchParams({ cursor: res.meta.pagination.next_cursor })}`} data-testid="orders-next">{t("actions.nextPage")}</a>
    {/if}
  {/if}
{:catch err}
  {@const e = asApiError(err)}
  <!-- 2. ERROR: the envelope's message, request_id on 5xx, and a retry -->
  <div role="alert" data-testid="orders-error">
    <p>{e.message}</p>
    {#if e.status >= 500 && e.requestId}
      <p class="text-sm text-muted-foreground">{t("errors.supportHint", { requestId: e.requestId })}</p>
    {/if}
    <button type="button" data-testid="orders-error-retry" onclick={onretry}>{t("actions.retry")}</button>
  </div>
{/await}
```

```svelte
<!-- file: src/routes/(app)/orders/+page.svelte -->
<script lang="ts">
  import { goto, invalidate } from "$app/navigation"
  import OrderList from "$lib/components/OrderList.svelte"
  import { t } from "$lib/i18n"
  import type { PageProps } from "./$types"

  let { data }: PageProps = $props()
</script>

<svelte:head><title>{t("orders.title")} · {t("app.name")}</title></svelte:head>
<h1 tabindex="-1">{t("orders.title")}</h1>
<OrderList orders={data.orders} onretry={() => invalidate("app:orders")} oncreate={() => goto("/orders/new")} />
```

## 4. Forms: a Superforms action with the server's `details[]` on the fields

- Validation runs twice from one Zod schema: `zod4Client` in the browser, for UX, and `zod4` in the action, as the check. The API validates again.
- `details[]` comes back with 400 `VALIDATION_FAILED`, and can come back with 422 `BUSINESS_RULE_VIOLATION`. Branch on `details.length`, not on the status. The form's field names are the contract's field names.
- `use:enhance` keeps the form working without JavaScript. SvelteKit rejects a cross-origin form POST (its CSRF origin check; `csrf.trustedOrigins` is empty by default).

```ts
// file: src/lib/forms/order-schema.ts
import { z } from "zod"
import type { CreateOrderInput } from "$lib/api/types"

// Derived from the contract's request type (ui/form-validation-protocol.md). idempotency_key is a hidden
// field: the same key goes with a retry of the same submission and never reaches the API as a payload field.
export const orderSchema = z.object({
  customer_email: z.email(),
  quantity: z.number().int().min(1).max(100),
  idempotency_key: z.uuid(),
}) satisfies z.ZodType<CreateOrderInput & { idempotency_key: string }>
```

```ts
// file: src/routes/(app)/orders/new/+page.server.ts
import { fail, redirect } from "@sveltejs/kit"
import { setError, superValidate } from "sveltekit-superforms"
import { zod4 } from "sveltekit-superforms/adapters"
import { ApiError, createApi } from "$lib/api/client"
import type { Order } from "$lib/api/types"
import { orderSchema } from "$lib/forms/order-schema"
import type { Actions, PageServerLoad } from "./$types"

export const load: PageServerLoad = async () => ({
  form: await superValidate({ idempotency_key: crypto.randomUUID() }, zod4(orderSchema), { errors: false }),
})

export const actions = {
  default: async ({ request, fetch }) => {
    const form = await superValidate(request, zod4(orderSchema))
    if (!form.valid) return fail(400, { form })
    const { idempotency_key, ...input } = form.data
    let order: Order
    try {
      order = await createApi(fetch).create<Order>("/orders", input, idempotency_key)
    } catch (e) {
      if (!(e instanceof ApiError)) throw e
      if (e.status > 0 && e.status < 500) form.data.idempotency_key = crypto.randomUUID() // rejected: nothing written
      for (const d of e.details) setError(form, d.field as keyof typeof input, d.message)
      if (e.details.length === 0) form.message = e.message
      return fail(e.status >= 400 ? e.status : 502, { form })
    }
    redirect(303, `/orders/${order.id}`)
  },
} satisfies Actions
```

```svelte
<!-- file: src/routes/(app)/orders/new/+page.svelte -->
<script lang="ts">
  import { superForm } from "sveltekit-superforms"
  import { zod4Client } from "sveltekit-superforms/adapters"
  import { orderSchema } from "$lib/forms/order-schema"
  import { t } from "$lib/i18n"
  import type { PageProps } from "./$types"

  let { data }: PageProps = $props()
  // superForm owns the form state from here on; it focuses the first invalid field after a failed submit.
  // svelte-ignore state_referenced_locally
  const { form, errors, message, submitting, enhance } = superForm(data.form, { validators: zod4Client(orderSchema) })
</script>

<svelte:head><title>{t("orders.form.title")} · {t("app.name")}</title></svelte:head>
<h1 tabindex="-1">{t("orders.form.title")}</h1>
<form method="POST" use:enhance novalidate>
  {#if $message}<p role="alert">{$message}</p>{/if}
  <input type="hidden" name="idempotency_key" bind:value={$form.idempotency_key} />
  <label for="customer_email">{t("orders.form.email")}</label>
  <input id="customer_email" name="customer_email" type="email" autocomplete="email" bind:value={$form.customer_email}
    aria-invalid={$errors.customer_email ? "true" : undefined}
    aria-describedby={$errors.customer_email ? "customer_email-error" : undefined} />
  {#if $errors.customer_email}<p id="customer_email-error" class="text-destructive">{$errors.customer_email[0]}</p>{/if}
  <label for="quantity">{t("orders.form.quantity")}</label>
  <input id="quantity" name="quantity" type="number" min="1" max="100" bind:value={$form.quantity}
    aria-invalid={$errors.quantity ? "true" : undefined}
    aria-describedby={$errors.quantity ? "quantity-error" : undefined} />
  {#if $errors.quantity}<p id="quantity-error" class="text-destructive">{$errors.quantity[0]}</p>{/if}
  <button type="submit" disabled={$submitting}>{t("orders.form.submit")}</button>
</form>
```

## 5. Session, CSRF and route guards (hooks)

- The API sets the session as an `HttpOnly; Secure; SameSite` cookie. JavaScript never holds a token, and nothing goes into `localStorage`, `sessionStorage` or a URL (secure-coding §3).
- `handle` resolves the user once per request into `event.locals`, and it denies by default. Client-side navigations fetch server data through `handle` too, so the guard covers them.
- Use `safeReturnTo` from `ui/secure-rendering.md` on `returnTo` after sign-in.

```ts
// file: src/app.d.ts
import type { SessionUser } from "$lib/api/types"

declare global {
  namespace App {
    interface Locals { user: SessionUser | null } // the profile, never a token
  }
}
export {}
```

```ts
// file: src/hooks.server.ts
import { redirect, type Handle, type HandleFetch } from "@sveltejs/kit"
import { env } from "$env/dynamic/private"
import type { ApiSuccess, SessionUser } from "$lib/api/types"

const PUBLIC_PATHS = ["/login"]

export const handle: Handle = async ({ event, resolve }) => {
  event.locals.user = null
  if (event.cookies.get("session")) {
    const res = await event.fetch("/api/v1/session") // through handleFetch below, with the user's cookie
    if (res.ok) event.locals.user = ((await res.json()) as ApiSuccess<SessionUser>).data
  }
  // Deny by default. Hiding a link is not a control: the API still authorizes every call.
  if (!event.locals.user && !PUBLIC_PATHS.some((p) => event.url.pathname.startsWith(p))) {
    redirect(303, `/login?returnTo=${encodeURIComponent(event.url.pathname + event.url.search)}`)
  }
  return resolve(event)
}

// Server-side calls to /api go to the API service, read at runtime (never baked in at build), with the
// user's cookie and the CSRF cookie echoed as a header. SvelteKit has already checked the form's Origin.
export const handleFetch: HandleFetch = async ({ event, request, fetch }) => {
  const url = new URL(request.url)
  if (url.origin === event.url.origin && url.pathname.startsWith("/api/")) {
    request = new Request(new URL(url.pathname + url.search, env.API_INTERNAL_URL), request)
    request.headers.set("cookie", event.request.headers.get("cookie") ?? "")
    const xsrf = event.cookies.get("XSRF-TOKEN")
    if (xsrf && request.method !== "GET" && request.method !== "HEAD") request.headers.set("X-XSRF-TOKEN", xsrf)
  }
  return fetch(request)
}
```

## 6. Safe rendering: `{@html}` and URLs

- `{value}` escapes. `{@html}` does not.
- `{@html}` takes only DOMPurify output, sanitized in the same component, with a comment that cites the FR. Server error messages and LLM output render as text.
- Plain `dompurify` needs a DOM. During SSR use `isomorphic-dompurify`, so the server and the client render the same HTML. Svelte keeps the server's `{@html}` value when hydrating, so a mismatch shows stale content.
- `href`/`src` built from data go through `safeHref` from `ui/secure-rendering.md`; Svelte doesn't block `javascript:`.

```svelte
<!-- file: src/lib/components/SafeHtml.svelte -->
<script lang="ts">
  import DOMPurify from "isomorphic-dompurify"

  // Reason: FR-012 rich-text order notes from the editor. Sanitized here, at render time.
  let { html }: { html: string } = $props()
  const clean = $derived(DOMPurify.sanitize(html, { USE_PROFILES: { html: true } }))
</script>

<div>{@html clean}</div>
```

## 7. Accessibility
- After each navigation, SvelteKit announces the new `<title>` in a live region and focuses `<body>`, so **every page needs a unique `<title>`** (`<svelte:head>`). Move focus to the page's `<h1 tabindex="-1">` with `afterNavigate` when long navigation precedes the content.
- Forms (§4): `aria-invalid` and `aria-describedby` on each field, a `role="alert"` message for form-level errors. Superforms focuses the first error.
- The compiler's a11y warnings are errors in CI (`svelte-check --fail-on-warnings`). Don't add `svelte-ignore` to an a11y rule without a DECISIONS entry.

```svelte
<!-- file: src/routes/+layout.svelte -->
<script lang="ts">
  import { QueryClient, QueryClientProvider } from "@tanstack/svelte-query"
  import { browser } from "$app/environment"
  import { afterNavigate } from "$app/navigation"
  import { ApiError } from "$lib/api/client"
  import { t } from "$lib/i18n"
  import type { LayoutProps } from "./$types"

  let { children }: LayoutProps = $props()
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { enabled: browser, staleTime: 30_000, retry: (n, e) => e instanceof ApiError && e.retryable && n < 2 },
      mutations: { retry: 0 },
    },
  })
  afterNavigate(({ from }) => { if (from) document.querySelector<HTMLElement>("main h1")?.focus() })
</script>

<a href="#main" class="sr-only focus:not-sr-only">{t("a11y.skipToContent")}</a>
<QueryClientProvider client={queryClient}>
  <main id="main">{@render children()}</main>
</QueryClientProvider>
```

## 8. Component and action tests: Testing Library, MSW and axe (ui_test_agent Part A)

- The response bodies come from `msw.md`'s typed helpers (`ok`, `page`, `apiError` in `$lib/mocks/envelope.ts`). This setup is MSW 2 (`onUnhandledRequest`). When you move to MSW 3, the option becomes `onUnhandledFrame`.
- Vitest runs with `plugins: [sveltekit(), svelteTesting()]` and `environment: "jsdom"`. The `svelteTesting()` plugin cleans up between tests.
- Components are rendered with their props (`render(Component, { …props })`). The server's `details[]` are mapped in the action, so the TC-FORM row tests the action directly.
- jsdom has no layout, so the axe check covers names, roles and ARIA, not contrast (contrast is Part B).

```ts
// file: src/lib/test/setup.ts
import "@testing-library/jest-dom/vitest"
import { setupServer } from "msw/node"
import { afterAll, afterEach, beforeAll } from "vitest"

export const server = setupServer() // no default handlers: each test declares what the screen calls
beforeAll(() => server.listen({ onUnhandledRequest: "error" }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
```

```ts
// file: src/lib/test/axe.ts
import axe from "axe-core"
import { expect } from "vitest"

const WCAG = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]
export async function expectNoAxeViolations(el: Element) {
  const { violations } = await axe.run(el, { runOnly: { type: "tag", values: WCAG }, rules: { "color-contrast": { enabled: false } } })
  expect(violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`)).toEqual([])
}
```

```ts
// file: src/lib/components/OrderList.test.ts
import { render, screen } from "@testing-library/svelte"
import userEvent from "@testing-library/user-event"
import { delay, http } from "msw"
import { describe, expect, it, vi } from "vitest"
import { createApi } from "$lib/api/client"
import type { Order } from "$lib/api/types"
import OrderList from "$lib/components/OrderList.svelte"
import { apiError, page } from "$lib/mocks/envelope"
import { expectNoAxeViolations } from "$lib/test/axe"
import { server } from "$lib/test/setup"

const ORDERS = "/api/v1/orders"
const order = (o: Partial<Order> = {}): Order => ({ id: "o1", customer_name: "Alice", customer_email: "a@example.com",
  quantity: 1, status: "open", total_cents: 1299, created_at: "2026-09-30T12:00:00Z", ...o })
// The component gets what the page's load returns: the list promise from the real client.
const renderList = (onretry = vi.fn()) =>
  render(OrderList, { orders: createApi().list<Order>("/orders", { limit: 20 }), onretry, oncreate: vi.fn() })

describe("OrderList", () => {
  it("TC-UI-20107 shows a skeleton while loading", async () => {
    server.use(http.get(ORDERS, async () => { await delay("infinite"); return page([]) }))
    renderList()
    expect(screen.getByTestId("orders-loading")).toHaveAttribute("aria-busy", "true")
  })
  it("TC-UI-20108 shows the empty state for data: []", async () => {
    server.use(http.get(ORDERS, () => page([])))
    renderList()
    expect(await screen.findByRole("heading", { name: "No orders yet" })).toBeVisible()
  })
  it("TC-UI-20109 shows the envelope message and a retry", async () => {
    server.use(http.get(ORDERS, () => apiError(503, "UNAVAILABLE", "Try again shortly.")))
    const onretry = vi.fn()
    renderList(onretry)
    expect(await screen.findByRole("alert")).toHaveTextContent("Try again shortly.")
    await userEvent.click(screen.getByRole("button", { name: "Retry" }))
    expect(onretry).toHaveBeenCalledOnce()
  })
  it("TC-UI-20110 links the next page with meta.pagination.next_cursor", async () => {
    server.use(http.get(ORDERS, () => page([order()], { has_more: true, next_cursor: "c2" })))
    renderList()
    expect(await screen.findByRole("link", { name: "Next page" })).toHaveAttribute("href", "?cursor=c2")
  })
  it("TC-SEC-20111 XSS-RENDER: markup in a name renders as text", async () => {
    const payload = `<img src=x onerror="window.__xss=1">`
    server.use(http.get(ORDERS, () => page([order({ customer_name: payload })])))
    renderList()
    expect(await screen.findByText(payload, { exact: false })).toBeVisible()
    expect("__xss" in window).toBe(false)
  })
  it("TC-A11Y-20112 data state: names and roles pass axe (contrast is Part B)", async () => {
    server.use(http.get(ORDERS, () => page([order()])))
    const { container } = renderList()
    await screen.findByTestId("orders-table")
    await expectNoAxeViolations(container)
  })
})
```

```ts
// file: src/routes/(app)/orders/new/page.server.test.ts
import { http } from "msw"
import { describe, expect, it } from "vitest"
import { apiError } from "$lib/mocks/envelope"
import { server } from "$lib/test/setup"
import { actions } from "./+page.server"

type ActionEvent = Parameters<typeof actions.default>[0]
const submit = (fields: Record<string, string>) => {
  const body = new FormData()
  for (const [k, v] of Object.entries(fields)) body.set(k, v)
  const request = new Request("http://localhost/orders/new", { method: "POST", body })
  const fetch: typeof globalThis.fetch = (input, init) => globalThis.fetch(new URL(String(input), "http://localhost"), init)
  return actions.default({ request, fetch } as ActionEvent)
}

describe("create order action", () => {
  it("TC-FORM-20113 puts the API's details[] on the field and rotates the idempotency key", async () => {
    server.use(http.post("http://localhost/api/v1/orders", () => apiError(400, "VALIDATION_FAILED", "Some fields are invalid.",
      { details: [{ field: "customer_email", code: "taken", message: "That email already has an open order." }] })))
    const key = crypto.randomUUID()
    const result = await submit({ customer_email: "bob@example.com", quantity: "1", idempotency_key: key })
    expect(result).toMatchObject({ status: 400, data: { form: { errors: { customer_email: ["That email already has an open order."] } } } })
    expect(result?.data.form.data.idempotency_key).not.toBe(key)
  })
})
```

## Rules
- Every call goes through `createApi(fetch)`: SvelteKit's `fetch` in loads and actions, the default in the browser. Never read `response.data` from an unwrapped body.
- Lists render `data` (always an array) and page with `meta.pagination.next_cursor`: a `?cursor=` link, or `fetchNextPage` for infinite lists. Never compute an offset.
- Mutations go through actions (or a `mutation` with `retry: 0`), re-validate on the server, and send an `Idempotency-Key` on a creating POST.
- `event.locals.user` holds the profile. Tokens are never in JS. `handle` denies by default. `returnTo` passes `safeReturnTo`.
- `{@html}` only on DOMPurify output, with a reason comment. Every page sets a unique `<title>`.
