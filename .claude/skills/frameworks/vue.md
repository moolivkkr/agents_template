---
skill: vue
description: Vue 3 patterns for ui_developer and ui_test_agent — typed client for the one envelope, TanStack Vue Query cursor lists, the 4 states, VeeValidate + Zod forms with server details[] on fields, cookie session + router guards, v-html rules, route focus, Testing Library + MSW + axe tests
version: "2.0"
tags:
  - vue
  - frontend
  - composition-api
  - tanstack-query
  - vee-validate
  - pinia
---

# Vue 3 patterns

> Verified against Vue 3.5.43, vue-router 5.3.1, Pinia 4.0.3, @tanstack/vue-query 5.104.0, VeeValidate 4.15.1, Zod 4.6.5, @testing-library/vue 8.1.0, MSW 3.0.1, Vitest 5.0.3 and TypeScript 6.0.3 (npm registry and the official docs, 2026-09-30). Every `file:` block compiles under `vue-tsc --noEmit` with `strictTemplates`, and its tests pass: `bash tests/archetype-compile/ui-frameworks/run.sh vue`.

This pack is the Vue translation of `ui_developer`'s React-flavoured examples. The rules live in the shared packs, which win on conflict: `api/response-envelope.md` (the shape), `ui/secure-rendering.md` (rendering, `safeHref`, `safeReturnTo`), `infrastructure/auth-session-flows.md` (sessions) and `testing/msw.md` (mocks). `@/api/types` is the module generated from the contract (envelope plus payload types). `t()` is the project's i18n function.

## Components and reactivity
- `<script setup lang="ts">` everywhere, with `defineProps<{…}>()` and `defineEmits<{ name: [arg: T] }>()`. Use `ref` for state, `computed` for derived values, and `watch` for side effects only.
- Server data lives in TanStack Vue Query (§2), never fetched in `onMounted`/`watch` into a `ref`. Pinia holds **client** state only (the signed-in profile, preferences), never lists copied from the API.
- Type-check with `vue-tsc --noEmit`. With `vueCompilerOptions.strictTemplates`, add `"dataAttributes": ["data-*"]`, or every `data-testid` is a type error.

## 1. Typed API client: unwraps the one envelope

```ts
// file: src/api/client.ts
import type { ApiErrorBody, ApiSuccess, FieldError } from "@/api/types"

/** Every failed call becomes this: the envelope's error plus the HTTP status (0 = no response). */
export class ApiError extends Error {
  constructor(readonly status: number, readonly code: string, message: string, readonly details: FieldError[] = [],
    readonly requestId?: string, readonly retryable = false) { super(message); this.name = "ApiError" }
}

type Query = Record<string, string | number | undefined>
type Init = { query?: Query; body?: unknown; idempotencyKey?: string; signal?: AbortSignal }
const BASE = "/api/v1" // same-origin; never an API URL baked in at build time

async function send(method: string, path: string, init: Init = {}): Promise<Response> {
  const url = new URL(BASE + path, window.location.origin)
  for (const [k, v] of Object.entries(init.query ?? {})) if (v !== undefined) url.searchParams.set(k, String(v))
  const headers = new Headers({ Accept: "application/json" })
  if (init.body !== undefined) headers.set("Content-Type", "application/json")
  if (init.idempotencyKey) headers.set("Idempotency-Key", init.idempotencyKey)
  // Double-submit CSRF: the server sets a readable XSRF-TOKEN cookie (not a credential); echo it on writes.
  const csrf = document.cookie.match(/(?:^|;\s*)XSRF-TOKEN=([^;]+)/)?.[1]
  if (method !== "GET" && csrf) headers.set("X-XSRF-TOKEN", decodeURIComponent(csrf))
  let res: Response
  try {
    const body = init.body === undefined ? undefined : JSON.stringify(init.body)
    res = await fetch(url, { method, headers, body, credentials: "same-origin", signal: init.signal })
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

export const api = {
  get: async <T>(path: string, query?: Query) => (await envelope<T>(send("GET", path, { query }))).data,
  /** Lists keep the whole envelope: data is always an array, the cursor is in meta.pagination. */
  list: <T>(path: string, query?: Query, signal?: AbortSignal) => envelope<T[]>(send("GET", path, { query, signal })),
  create: async <T>(path: string, body: unknown, idempotencyKey?: string) =>
    (await envelope<T>(send("POST", path, { body, idempotencyKey }))).data,
  remove: async (path: string) => void (await send("DELETE", path)),
}
```

## 2. Server state: a cursor-paginated list with TanStack Vue Query

```ts
// file: src/api/query-client.ts
import { MutationCache, QueryCache, QueryClient } from "@tanstack/vue-query"
import type { ApiError } from "@/api/client"

declare module "@tanstack/vue-query" {
  interface Register { defaultError: ApiError } // query.error is an ApiError everywhere
}

export function createQueryClient(onUnauthenticated: () => void) {
  const on401 = (e: ApiError) => { if (e.status === 401) onUnauthenticated() }
  return new QueryClient({
    queryCache: new QueryCache({ onError: on401 }),
    mutationCache: new MutationCache({ onError: on401 }),
    defaultOptions: {
      queries: { staleTime: 30_000, retry: (n, e) => e.retryable && n < 2 }, // GETs are idempotent
      mutations: { retry: 0 }, // never auto-retry a write
    },
  })
}
```

```ts
// file: src/api/orders.ts
import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/vue-query"
import { computed, toValue, type MaybeRefOrGetter } from "vue"
import { api } from "@/api/client"
import type { CreateOrderInput, Order } from "@/api/types"

export const orderKeys = { all: ["orders"] as const, list: (status?: string) => ["orders", "list", { status }] as const }

export function useOrders(status: MaybeRefOrGetter<string | undefined> = undefined) {
  return useInfiniteQuery({
    queryKey: computed(() => orderKeys.list(toValue(status))),
    queryFn: ({ pageParam, signal }) => api.list<Order>("/orders", { limit: 20, cursor: pageParam, status: toValue(status) }, signal),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => (last.meta.pagination?.has_more ? (last.meta.pagination.next_cursor ?? undefined) : undefined),
  })
}

export function useCreateOrder() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (v: { input: CreateOrderInput; idempotencyKey: string }) => api.create<Order>("/orders", v.input, v.idempotencyKey),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: orderKeys.all }),
  })
}
```

## 3. The 4 states

```vue
<!-- file: src/components/OrderList.vue -->
<script setup lang="ts">
import { computed } from "vue"
import { useOrders } from "@/api/orders"
import { t } from "@/i18n"

const emit = defineEmits<{ create: [] }>()
const { data, error, isPending, isError, refetch, hasNextPage, fetchNextPage, isFetchingNextPage } = useOrders()
const orders = computed(() => data.value?.pages.flatMap((p) => p.data) ?? [])
</script>

<template>
  <!-- 1. LOADING: a skeleton shaped like the list, not a spinner -->
  <ul v-if="isPending" aria-busy="true" :aria-label="t('orders.loading')" data-testid="orders-loading">
    <li v-for="n in 5" :key="n" class="h-14 animate-pulse rounded-md bg-muted" />
  </ul>
  <!-- 2. ERROR: the envelope's message, request_id on 5xx, and a retry -->
  <div v-else-if="isError && error" role="alert" data-testid="orders-error">
    <p>{{ error.message }}</p>
    <p v-if="error.status >= 500 && error.requestId" class="text-sm text-muted-foreground">
      {{ t("errors.supportHint", { requestId: error.requestId }) }}
    </p>
    <button type="button" data-testid="orders-error-retry" @click="refetch()">{{ t("actions.retry") }}</button>
  </div>
  <!-- 3. EMPTY (data: []): the design system's icon (aria-hidden), title, description, CTA -->
  <section v-else-if="orders.length === 0" aria-labelledby="orders-empty-title" data-testid="orders-empty">
    <h2 id="orders-empty-title">{{ t("orders.empty.title") }}</h2>
    <p class="text-muted-foreground">{{ t("orders.empty.description") }}</p>
    <button type="button" @click="emit('create')">{{ t("orders.empty.cta") }}</button>
  </section>
  <!-- 4. DATA, with "load more" from meta.pagination -->
  <div v-else>
    <ul data-testid="orders-table">
      <li v-for="order in orders" :key="order.id">{{ order.customer_name }} — {{ order.status }}</li>
    </ul>
    <button v-if="hasNextPage" type="button" :disabled="isFetchingNextPage" data-testid="orders-load-more" @click="fetchNextPage()">
      {{ t("actions.loadMore") }}
    </button>
  </div>
</template>
```

## 4. Forms: VeeValidate + Zod, with the server's `details[]` on the fields

VeeValidate 4.15.1 is the current stable release. `@vee-validate/zod` 4.15.1 declares `zod ^3.24`, and passing a Zod schema straight in (Standard Schema) arrives only in VeeValidate 5, which is still `5.0.0-beta.1`. Until then, use this adapter to Zod 4, and delete it on 5. `details[]` comes back with 400 `VALIDATION_FAILED` (and can with 422), so branch on `details.length`, not the status. Field names are the contract's field names.

```ts
// file: src/forms/zod-schema.ts
import type { TypedSchema } from "vee-validate"
import { z } from "zod"
import type { CreateOrderInput } from "@/api/types"

export function zodSchema<S extends z.ZodType>(schema: S): TypedSchema<z.input<S>, z.output<S>> {
  return {
    __type: "VVTypedSchema",
    async parse(values) {
      const result = await schema.safeParseAsync(values)
      if (result.success) return { value: result.data, errors: [] }
      const byPath = new Map<string, string[]>()
      for (const issue of result.error.issues) {
        const path = issue.path.map(String).join(".")
        byPath.set(path, [...(byPath.get(path) ?? []), issue.message])
      }
      return { errors: [...byPath].map(([path, errors]) => ({ path, errors })) }
    },
  }
}

// Derived from the contract's request type (ui/form-validation-protocol.md); the server re-validates.
export const orderSchema = z.object({
  customer_email: z.email(),
  quantity: z.number().int().min(1).max(100),
}) satisfies z.ZodType<CreateOrderInput>
```

```vue
<!-- file: src/components/OrderForm.vue -->
<script setup lang="ts">
import { useForm } from "vee-validate"
import { nextTick, ref } from "vue"
import { ApiError } from "@/api/client"
import { useCreateOrder } from "@/api/orders"
import type { Order } from "@/api/types"
import { orderSchema, zodSchema } from "@/forms/zod-schema"
import { t } from "@/i18n"

const emit = defineEmits<{ created: [order: Order] }>()
const { defineField, errors, handleSubmit, isSubmitting, setFieldError } = useForm({
  validationSchema: zodSchema(orderSchema), initialValues: { customer_email: "", quantity: 1 },
})
const [email, emailAttrs] = defineField("customer_email")
const [quantity, quantityAttrs] = defineField("quantity")
const formError = ref<string>()
const createOrder = useCreateOrder()
let idempotencyKey = crypto.randomUUID() // reused only when a retry may repeat the same write (network/5xx)
const focusFirstInvalid = () => nextTick(() => document.querySelector<HTMLElement>("[aria-invalid='true']")?.focus())

const onSubmit = handleSubmit(async (input) => {
  formError.value = undefined
  try {
    emit("created", await createOrder.mutateAsync({ input, idempotencyKey }))
    idempotencyKey = crypto.randomUUID()
  } catch (e) {
    if (!(e instanceof ApiError)) throw e
    if (e.status > 0 && e.status < 500) idempotencyKey = crypto.randomUUID() // rejected: nothing written
    for (const d of e.details) setFieldError(d.field as keyof typeof input, d.message)
    if (e.details.length === 0) formError.value = e.message
    await focusFirstInvalid()
  }
}, focusFirstInvalid)
</script>

<template>
  <form novalidate @submit="onSubmit">
    <p v-if="formError" role="alert">{{ formError }}</p>
    <label for="customer_email">{{ t("orders.form.email") }}</label>
    <input id="customer_email" v-model="email" v-bind="emailAttrs" type="email" autocomplete="email"
      :aria-invalid="errors.customer_email ? 'true' : undefined" :aria-describedby="errors.customer_email ? 'email-error' : undefined" />
    <p v-if="errors.customer_email" id="email-error" class="text-destructive">{{ errors.customer_email }}</p>
    <label for="quantity">{{ t("orders.form.quantity") }}</label>
    <input id="quantity" v-model.number="quantity" v-bind="quantityAttrs" type="number" min="1" max="100"
      :aria-invalid="errors.quantity ? 'true' : undefined" :aria-describedby="errors.quantity ? 'quantity-error' : undefined" />
    <p v-if="errors.quantity" id="quantity-error" class="text-destructive">{{ errors.quantity }}</p>
    <button type="submit" :disabled="isSubmitting">{{ t("orders.form.submit") }}</button>
  </form>
</template>
```

## 5. Session, CSRF and route guards

- The API sets the session as an `HttpOnly; Secure; SameSite` cookie, so JavaScript never holds a token and nothing goes into `localStorage`, `sessionStorage` or a URL (secure-coding §3).
- Writes echo the CSRF cookie (§1). WebSockets authenticate with a one-time ticket or the cookie, never with `?token=`.
- `main.ts` wires the 401 path: `app.use(VueQueryPlugin, { queryClient: createQueryClient(() => { useSession().clear(); router.push({ name: "login", query: { returnTo } }) }) })`. On sign-out, also call `queryClient.clear()`, so the next user never sees the cached data.

```ts
// file: src/session/session.ts
import { defineStore } from "pinia"
import { ref } from "vue"
import { api, ApiError } from "@/api/client"
import type { SessionUser } from "@/api/types"

export const useSession = defineStore("session", () => {
  const user = ref<SessionUser | null>(null) // the profile, never a token
  let loaded: Promise<void> | undefined
  function ensureLoaded() {
    loaded ??= api.get<SessionUser>("/session").then((u) => { user.value = u }, (e: unknown) => {
      loaded = undefined
      if (!(e instanceof ApiError && e.status === 401)) throw e
    })
    return loaded
  }
  function clear() { user.value = null; loaded = Promise.resolve() }
  async function signOut() { await api.remove("/session"); clear() }
  return { user, ensureLoaded, clear, signOut }
})
```

```ts
// file: src/router/index.ts
import { createRouter, createWebHistory } from "vue-router"
import { installRouteA11y } from "@/router/a11y"
import { safeReturnTo } from "@/security/safe-url" // from ui/secure-rendering.md
import { useSession } from "@/session/session"

declare module "vue-router" {
  interface RouteMeta { title: string; public?: boolean } // title is an i18n key
}

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", name: "login", component: () => import("@/pages/LoginPage.vue"), meta: { title: "login.title", public: true } },
    { path: "/orders", name: "orders", component: () => import("@/pages/OrdersPage.vue"), meta: { title: "orders.title" } },
    { path: "/orders/new", name: "order-new", component: () => import("@/pages/NewOrderPage.vue"), meta: { title: "orders.form.title" } },
  ],
})

// Deny by default. Hiding a link is not a control: the API still authorizes every call.
router.beforeEach(async (to) => {
  const session = useSession()
  await session.ensureLoaded()
  if (!to.meta.public && !session.user) return { name: "login", query: { returnTo: to.fullPath } }
  if (to.name === "login" && session.user) return safeReturnTo(to.query.returnTo)
})
installRouteA11y(router)
```

## 6. Safe rendering: `v-html` and URLs

- `{{ }}` escapes. `v-html` doesn't, and Vue doesn't sanitize `:href` or `:src` either, so a `javascript:` URL runs. Bind URLs from data through `safeHref`.
- `v-html` takes only DOMPurify output, sanitized in the same component, with a comment that cites the FR. Error messages and LLM output render as text.

```vue
<!-- file: src/components/SafeHtml.vue -->
<script setup lang="ts">
import DOMPurify from "dompurify"
import { computed } from "vue"

// Reason: FR-012 rich-text order notes from the editor. Sanitized here, at render time.
const props = defineProps<{ html: string }>()
const clean = computed(() => DOMPurify.sanitize(props.html, { USE_PROFILES: { html: true } }))
</script>

<template>
  <!-- eslint-disable-next-line vue/no-v-html -- DOMPurify output (secure-rendering.md rule 2) -->
  <div v-html="clean" />
</template>
```

## 7. Accessibility

- Vue Router neither moves focus nor announces navigation. After each in-app navigation, set a unique title and focus the page's `<h1 tabindex="-1">`, which screen readers then read.
- `App.vue` renders a skip link to `<main id="main">`.
- Forms (§4): `aria-invalid` and `aria-describedby` on each field, a `role="alert"` form error, and focus on the first invalid field on submit.
- Lint with `eslint-plugin-vuejs-accessibility`.

```ts
// file: src/router/a11y.ts
import { nextTick } from "vue"
import type { Router } from "vue-router"
import { t } from "@/i18n"

export function installRouteA11y(router: Router) {
  router.afterEach((to, from, failure) => {
    if (failure) return
    document.title = `${t(to.meta.title)} · ${t("app.name")}`
    if (from.matched.length > 0) void nextTick(() => document.querySelector<HTMLElement>("main h1")?.focus())
  })
}
```

## 8. Component tests: Testing Library, MSW and axe (ui_test_agent Part A)

- Response bodies come from `msw.md`'s typed helpers (`ok`, `page`, `apiError` in `src/mocks/envelope.ts`), so a mock that drifts from the contract fails to compile.
- MSW 3 renames `onUnhandledRequest` to `onUnhandledFrame`. Its docs import from `msw/http`, but the root `msw` entry still exports everything in 3.0.1, and it works on 2.x too.
- Each test gets a fresh `QueryClient` with `retry: false`, and each test is named with its TC ID.
- jsdom has no layout, so axe checks names, roles and ARIA here, not contrast (contrast is Part B).

```ts
// file: src/test/setup.ts
import "@testing-library/jest-dom/vitest"
import { cleanup } from "@testing-library/vue"
import { setupServer } from "msw/node"
import { afterAll, afterEach, beforeAll } from "vitest"

export const server = setupServer() // no default handlers: each test declares what the screen calls
beforeAll(() => server.listen({ onUnhandledFrame: "error" }))
afterEach(() => { cleanup(); server.resetHandlers() })
afterAll(() => server.close())
```

```ts
// file: src/test/axe.ts
import axe from "axe-core"
import { expect } from "vitest"

const WCAG = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]
export async function expectNoAxeViolations(el: Element) {
  const { violations } = await axe.run(el, { runOnly: { type: "tag", values: WCAG }, rules: { "color-contrast": { enabled: false } } })
  expect(violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`)).toEqual([])
}
```

```ts
// file: src/components/OrderList.test.ts
import { QueryClient, VueQueryPlugin, type VueQueryPluginOptions } from "@tanstack/vue-query"
import userEvent from "@testing-library/user-event"
import { render, screen } from "@testing-library/vue"
import { delay, http, type PathParams } from "msw"
import { describe, expect, it } from "vitest"
import type { ApiErrorBody, ApiSuccess, Order } from "@/api/types"
import OrderForm from "@/components/OrderForm.vue"
import OrderList from "@/components/OrderList.vue"
import { apiError, page } from "@/mocks/envelope"
import { expectNoAxeViolations } from "@/test/axe"
import { server } from "@/test/setup"

type Res<T> = ApiSuccess<T> | ApiErrorBody // a handler that can answer either way is typed with both
const ORDERS = "/api/v1/orders"
const order = (o: Partial<Order> = {}): Order => ({ id: "o1", customer_name: "Alice", customer_email: "a@example.com",
  quantity: 1, status: "open", total_cents: 1299, created_at: "2026-09-30T12:00:00Z", ...o })
function withQuery() {
  const plugin: [typeof VueQueryPlugin, VueQueryPluginOptions] =
    [VueQueryPlugin, { queryClient: new QueryClient({ defaultOptions: { queries: { retry: false } } }) }]
  return { global: { plugins: [plugin] } }
}

describe("OrderList", () => {
  it("TC-UI-20107 shows a skeleton while loading", async () => {
    server.use(http.get(ORDERS, async () => { await delay("infinite"); return page([]) }))
    render(OrderList, withQuery())
    expect(await screen.findByTestId("orders-loading")).toHaveAttribute("aria-busy", "true")
  })
  it("TC-UI-20108 shows the empty state for data: []", async () => {
    server.use(http.get(ORDERS, () => page([])))
    render(OrderList, withQuery())
    expect(await screen.findByRole("heading", { name: "No orders yet" })).toBeVisible()
  })
  it("TC-UI-20109 shows the envelope message and retries", async () => {
    let calls = 0
    server.use(http.get<PathParams, never, Res<Order[]>>(ORDERS, () =>
      ++calls === 1 ? apiError(503, "UNAVAILABLE", "Try again shortly.") : page([order()])))
    render(OrderList, withQuery())
    expect(await screen.findByRole("alert")).toHaveTextContent("Try again shortly.")
    await userEvent.click(screen.getByRole("button", { name: "Retry" }))
    expect(await screen.findByTestId("orders-table")).toHaveTextContent("Alice")
  })
  it("TC-UI-20110 loads the next page with meta.pagination.next_cursor", async () => {
    server.use(http.get(ORDERS, ({ request }) => new URL(request.url).searchParams.get("cursor") === "c2"
      ? page([order({ id: "o2", customer_name: "Bob" })]) : page([order()], { has_more: true, next_cursor: "c2" })))
    render(OrderList, withQuery())
    await userEvent.click(await screen.findByRole("button", { name: "Load more" }))
    expect(await screen.findByText(/Bob/)).toBeVisible()
    expect(screen.getByText(/Alice/)).toBeVisible()
  })
  it("TC-SEC-20111 XSS-RENDER: markup in a name renders as text", async () => {
    const payload = `<img src=x onerror="window.__xss=1">`
    server.use(http.get(ORDERS, () => page([order({ customer_name: payload })])))
    render(OrderList, withQuery())
    expect(await screen.findByText(payload, { exact: false })).toBeVisible()
    expect("__xss" in window).toBe(false)
  })
  it("TC-A11Y-20112 data state: names and roles pass axe (contrast is Part B)", async () => {
    server.use(http.get(ORDERS, () => page([order()])))
    const { container } = render(OrderList, withQuery())
    await screen.findByTestId("orders-table")
    await expectNoAxeViolations(container)
  })
})

describe("OrderForm", () => {
  it("TC-FORM-20113 puts the server's details[] on the field and focuses it", async () => {
    server.use(http.post(ORDERS, () => apiError(400, "VALIDATION_FAILED", "Some fields are invalid.",
      { details: [{ field: "customer_email", code: "already_exists", message: "That email already has an open order." }] })))
    render(OrderForm, withQuery())
    await userEvent.type(screen.getByLabelText("Customer email"), "bob@example.com")
    await userEvent.click(screen.getByRole("button", { name: "Create order" }))
    expect(await screen.findByText("That email already has an open order.")).toBeVisible()
    expect(screen.getByLabelText("Customer email")).toHaveAttribute("aria-invalid", "true")
    expect(screen.getByLabelText("Customer email")).toHaveFocus()
  })
})
```

## Rules
- Every call goes through `api` (`src/api/client.ts`). Lists render `data` (always an array) and page with `meta.pagination.next_cursor`, never an offset.
- Mutations use `retry: 0`, invalidate the list on success, and send an `Idempotency-Key` on a creating POST.
- The session is a profile in Pinia, and tokens are never in JS. Guards deny by default, and `returnTo` passes `safeReturnTo`.
- `v-html` only on DOMPurify output, with a reason comment. `:href`/`:src` built from data go through `safeHref`.
