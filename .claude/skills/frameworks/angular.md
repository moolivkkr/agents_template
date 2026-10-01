---
skill: angular
description: Angular 22 patterns for ui_developer and ui_test_agent — HttpClient + interceptor for the one envelope, httpResource cursor lists, the 4 states with control flow, Signal Forms with server details[] on fields, XSRF + cookie session + functional guards, [innerHTML]/bypassSecurityTrust rules, route focus, Testing Library + MSW + axe tests on Vitest
version: "1.0"
tags:
  - angular
  - frontend
  - signals
  - httpresource
  - signal-forms
  - rxjs
---

# Angular patterns

> Verified against @angular/core 22.2.1, @angular/cli and @angular/build 22.2.0, Zod 4.6.5, @testing-library/angular 19.5.0, MSW 3.0.1, Vitest 5.0.3 and TypeScript 6.0.3 (npm registry and angular.dev, 2026-09-30). Angular 22 requires TypeScript `>=6.0 <6.1`, so TS 7 isn't supported yet. According to angular.dev's API reference, `httpResource`, `resource` and Signal Forms (`form`, `FormField`, `FormRoot`, `submit`, `validateStandardSchema`) are **stable since v22.0**. TanStack Query for Angular is still published as `@tanstack/angular-query-experimental`, so don't build on it. Every `file:` block below compiles under `ngc` with `strictTemplates`, and its tests pass under `ng test` (Vitest): `bash tests/archetype-compile/ui-frameworks/run.sh angular`.

This pack is the Angular translation of `ui_developer`'s React-flavoured examples. The rules live in the shared packs, which win on conflict: `api/response-envelope.md` (the shape), `ui/secure-rendering.md` (rendering, `safeHref`, `safeReturnTo`), `infrastructure/auth-session-flows.md` (sessions) and `testing/msw.md` (mocks). `app/api/types.ts` is the module generated from the contract (envelope plus payload types). `t()` is the project's i18n function (Transloco, or a wrapper over `$localize`).

## Components and state
- Components are standalone (the default) and use `ChangeDetectionStrategy.OnPush`. New CLI apps are zoneless (the default since v21).
- Use `input()`, `output()`, `signal()` and `computed()`, plus `linkedSignal()` for state that resets when its source changes.
- Templates use the built-in control flow (`@if`, `@for … track`, `@switch`).
- Server data comes from `httpResource`, which is reactive and read-only. Writes go through `HttpClient`, as the docs advise against using `httpResource` for mutations.
- Use `inject()`, never constructor parameters. Call `inject()` before any `await`: the injection context ends at the first `await`.

## 1. Typed API client: HttpClient plus an interceptor that unwraps the one envelope

```ts
// file: src/app/api/api-client.ts
import { HttpClient, HttpErrorResponse, HttpHeaders, type HttpInterceptorFn } from "@angular/common/http"
import { inject, Injectable } from "@angular/core"
import { Router } from "@angular/router"
import { catchError, map, type Observable, throwError } from "rxjs"
import type { ApiErrorBody, ApiSuccess, FieldError } from "./types"

/** Every failed call becomes this: the envelope's error plus the HTTP status (0 = no response). */
export class ApiError extends Error {
  constructor(readonly status: number, readonly code: string, message: string, readonly details: FieldError[] = [],
    readonly requestId?: string, readonly retryable = false) { super(message); this.name = "ApiError" }
}

export const API = "/api/v1" // same-origin; never an API URL baked in at build time

export function toApiError(e: unknown): ApiError {
  if (e instanceof ApiError) return e
  if (!(e instanceof HttpErrorResponse)) return new ApiError(0, "UNKNOWN", "Something went wrong.")
  if (e.status === 0) return new ApiError(0, "NETWORK_ERROR", "Can't reach the server. Check your connection and retry.", [], undefined, true)
  const err = (e.error as ApiErrorBody | null)?.error // branch on status, never error === null
  return new ApiError(e.status, err?.code ?? "UNKNOWN", err?.message ?? "Something went wrong.", err?.details ?? [],
    err?.request_id ?? e.headers.get("X-Request-Id") ?? undefined, err?.retryable ?? (e.status === 429 || e.status >= 503))
}

/** HttpClient errors become ApiError; a 401 sends the user to sign in and back (the guard handles /session). */
export const apiErrorInterceptor: HttpInterceptorFn = (req, next) => {
  const router = inject(Router)
  return next(req).pipe(catchError((e: unknown) => {
    const err = toApiError(e)
    if (err.status === 401 && !req.url.endsWith("/session")) void router.navigate(["/login"], { queryParams: { returnTo: router.url } })
    return throwError(() => err)
  }))
}

type Params = Record<string, string | number | null | undefined>
const defined = (p: Params = {}) => Object.fromEntries(Object.entries(p).filter(([, v]) => v != null)) as Record<string, string | number>

@Injectable({ providedIn: "root" })
export class ApiClient {
  private readonly http = inject(HttpClient)
  get<T>(path: string, params?: Params): Observable<T> {
    return this.http.get<ApiSuccess<T>>(API + path, { params: defined(params) }).pipe(map((r) => r.data))
  }
  /** Lists keep the whole envelope: data is always an array, the cursor is in meta.pagination. */
  list<T>(path: string, params?: Params): Observable<ApiSuccess<T[]>> {
    return this.http.get<ApiSuccess<T[]>>(API + path, { params: defined(params) })
  }
  create<T>(path: string, body: unknown, idempotencyKey?: string): Observable<T> {
    const headers = idempotencyKey ? new HttpHeaders({ "Idempotency-Key": idempotencyKey }) : undefined
    return this.http.post<ApiSuccess<T>>(API + path, body, { headers }).pipe(map((r) => r.data))
  }
  remove(path: string): Observable<void> {
    return this.http.delete<void>(API + path)
  }
}
```

## 2. Server state: a cursor-paginated list with `httpResource`

- `httpResource` refetches whenever a signal it reads changes, and it cancels the request in flight. Setting `cursor` loads the next page.
- `linkedSignal` accumulates the pages. While a page loads, `hasValue()` is false, so the list keeps what it has.
- The interceptor has already turned the error into an `ApiError`.
- The resource and its 4 states live in one component (§3).

## 3. The 4 states

The error and loading branches show only while the list is empty. After that, "load more" keeps the rows and disables its button.

```ts
// file: src/app/orders/order-list.ts
import { httpResource } from "@angular/common/http"
import { ChangeDetectionStrategy, Component, computed, linkedSignal, output, signal, untracked } from "@angular/core"
import { API, toApiError } from "../api/api-client"
import type { ApiSuccess, Order } from "../api/types"
import { t } from "../i18n"

type Page = ApiSuccess<Order[]>

@Component({
  selector: "app-order-list",
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (page.isLoading() && orders().length === 0) {
      <!-- 1. LOADING: a skeleton shaped like the list, not a spinner -->
      <ul aria-busy="true" [attr.aria-label]="t('orders.loading')" data-testid="orders-loading">
        @for (n of [1, 2, 3, 4, 5]; track n) { <li class="h-14 animate-pulse rounded-md bg-muted"></li> }
      </ul>
    } @else if (error(); as e) {
      <!-- 2. ERROR: the envelope's message, request_id on 5xx, and a retry -->
      <div role="alert" data-testid="orders-error">
        <p>{{ e.message }}</p>
        @if (e.status >= 500 && e.requestId) {
          <p class="text-sm text-muted-foreground">{{ t("errors.supportHint", { requestId: e.requestId }) }}</p>
        }
        <button type="button" data-testid="orders-error-retry" (click)="page.reload()">{{ t("actions.retry") }}</button>
      </div>
    } @else if (orders().length === 0) {
      <!-- 3. EMPTY (data: []): the design system's icon (aria-hidden), title, description, CTA -->
      <section aria-labelledby="orders-empty-title" data-testid="orders-empty">
        <h2 id="orders-empty-title">{{ t("orders.empty.title") }}</h2>
        <p class="text-muted-foreground">{{ t("orders.empty.description") }}</p>
        <button type="button" (click)="create.emit()">{{ t("orders.empty.cta") }}</button>
      </section>
    } @else {
      <!-- 4. DATA, with "load more" from meta.pagination -->
      <ul data-testid="orders-table">
        @for (order of orders(); track order.id) { <li>{{ order.customer_name }} — {{ order.status }}</li> }
      </ul>
      @if (next(); as cursor) {
        <button type="button" [disabled]="page.isLoading()" data-testid="orders-load-more" (click)="this.cursor.set(cursor)">
          {{ t("actions.loadMore") }}
        </button>
      }
    }
  `,
})
export class OrderList {
  readonly create = output<void>()
  protected readonly t = t
  protected readonly cursor = signal<string | null>(null)
  protected readonly page = httpResource<Page>(() => {
    const params: Record<string, string | number> = { limit: 20 }
    const cursor = this.cursor()
    if (cursor) params["cursor"] = cursor
    return { url: `${API}/orders`, params }
  })
  private readonly loaded = computed(() => (this.page.hasValue() ? this.page.value() : undefined))
  /** First page replaces, later pages append; while a page loads the list keeps what it has. */
  protected readonly orders = linkedSignal<Page | undefined, Order[]>({
    source: this.loaded,
    computation: (res, prev) => {
      const kept = prev?.value ?? []
      if (!res) return kept
      return untracked(this.cursor) ? [...kept, ...res.data] : res.data
    },
  })
  protected readonly next = linkedSignal<Page | undefined, string | null>({
    source: this.loaded,
    computation: (res, prev) => (res ? (res.meta.pagination?.has_more ? (res.meta.pagination.next_cursor ?? null) : null) : (prev?.value ?? null)),
  })
  protected readonly error = computed(() => {
    const e = this.page.error()
    return e && this.orders().length === 0 ? toApiError(e) : undefined
  })
}
```

## 4. Forms: Signal Forms and Zod, with the server's `details[]` on the fields

- `validateStandardSchema` runs the Zod schema. `submit()` marks the fields as touched, skips the action while validation fails, exposes `submitting()`, and routes the errors the action returns onto fields.
- `details[]` comes back with 400 `VALIDATION_FAILED`, and can come back with 422 `BUSINESS_RULE_VIOLATION`. Branch on `details.length`, not on the status. The model's keys are the contract's field names.
- `[formField]` owns the input's `required`, `min`, `max` and `disabled` attributes, and setting them by hand is a compile error (NG8022). Those attributes come from Signal Forms' own validators (`required()`, `min()`); the Zod schema doesn't produce them.
- In an existing reactive-forms app, typed `FormGroup`s with `setErrors({ server: message })` do the same job.

```ts
// file: src/app/orders/order-schema.ts
import { z } from "zod"
import type { CreateOrderInput } from "../api/types"

// Derived from the contract's request type (ui/form-validation-protocol.md); the server re-validates.
export const orderSchema = z.object({
  customer_email: z.email(),
  quantity: z.number().int().min(1).max(100),
}) satisfies z.ZodType<CreateOrderInput>
```

```ts
// file: src/app/orders/order-form.ts
import { ChangeDetectionStrategy, Component, inject, output, signal } from "@angular/core"
import { type FieldTree, form, FormField, submit, validateStandardSchema } from "@angular/forms/signals"
import { firstValueFrom } from "rxjs"
import { ApiClient, toApiError } from "../api/api-client"
import type { CreateOrderInput, Order } from "../api/types"
import { t } from "../i18n"
import { orderSchema } from "./order-schema"

@Component({
  selector: "app-order-form",
  imports: [FormField],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <form novalidate (submit)="onSubmit($event)">
      @if (formError(); as message) { <p role="alert">{{ message }}</p> }
      <label for="customer_email">{{ t("orders.form.email") }}</label>
      <input id="customer_email" type="email" autocomplete="email" [formField]="orderForm.customer_email"
        [attr.aria-invalid]="shown(orderForm.customer_email) ? 'true' : undefined"
        [attr.aria-describedby]="shown(orderForm.customer_email) ? 'customer_email-error' : undefined" />
      @if (shown(orderForm.customer_email)) {
        <p id="customer_email-error" class="text-destructive">{{ orderForm.customer_email().errors()[0]?.message }}</p>
      }
      <label for="quantity">{{ t("orders.form.quantity") }}</label>
      <input id="quantity" type="number" [formField]="orderForm.quantity"
        [attr.aria-invalid]="shown(orderForm.quantity) ? 'true' : undefined"
        [attr.aria-describedby]="shown(orderForm.quantity) ? 'quantity-error' : undefined" />
      @if (shown(orderForm.quantity)) {
        <p id="quantity-error" class="text-destructive">{{ orderForm.quantity().errors()[0]?.message }}</p>
      }
      <button type="submit" [disabled]="orderForm().submitting()">{{ t("orders.form.submit") }}</button>
    </form>
  `,
})
export class OrderForm {
  private readonly api = inject(ApiClient)
  readonly created = output<Order>()
  protected readonly t = t
  protected readonly formError = signal<string | undefined>(undefined)
  private idempotencyKey = crypto.randomUUID() // reused only when a retry may repeat the same write (network/5xx)
  protected readonly orderForm = form(signal<CreateOrderInput>({ customer_email: "", quantity: 1 }), (p) => validateStandardSchema(p, orderSchema))

  protected shown(field: FieldTree<unknown>) {
    return field().touched() && field().invalid()
  }

  protected async onSubmit(event: Event) {
    event.preventDefault()
    this.formError.set(undefined)
    const ok = await submit(this.orderForm, async (f) => {
      try {
        this.created.emit(await firstValueFrom(this.api.create<Order>("/orders", f().value(), this.idempotencyKey)))
        this.idempotencyKey = crypto.randomUUID()
        return undefined
      } catch (e) {
        const err = toApiError(e)
        if (err.status > 0 && err.status < 500) this.idempotencyKey = crypto.randomUUID() // rejected: nothing written
        if (err.details.length === 0) {
          this.formError.set(err.message)
          return { kind: "server", message: err.message }
        }
        return err.details.map((d) => ({ kind: "server", message: d.message, fieldTree: f[d.field as keyof CreateOrderInput] }))
      }
    })
    if (!ok) this.orderForm().errorSummary()[0]?.fieldTree().focusBoundControl() // client or server errors: focus the first
  }
}
```

## 5. Session, XSRF, route guards and app config

- The API sets the session as an `HttpOnly; Secure; SameSite` cookie. JavaScript never holds a token, and nothing goes into `localStorage`, `sessionStorage` or a URL (secure-coding §3).
- `HttpClient` echoes the readable `XSRF-TOKEN` cookie as `X-XSRF-TOKEN` on writes to relative URLs. That's on by default; use `withXsrfConfiguration` only when the backend uses other names.
- Guards are functional, deny by default, and redirect with a `UrlTree`. Use `safeReturnTo` from `ui/secure-rendering.md` on `returnTo` after sign-in.

```ts
// file: src/app/session/session.ts
import { inject, Injectable, signal } from "@angular/core"
import { type CanActivateChildFn, Router } from "@angular/router"
import { firstValueFrom } from "rxjs"
import { ApiClient, ApiError } from "../api/api-client"
import type { SessionUser } from "../api/types"

@Injectable({ providedIn: "root" })
export class Session {
  private readonly api = inject(ApiClient)
  readonly user = signal<SessionUser | null>(null) // the profile, never a token
  private loaded?: Promise<void>

  ensureLoaded(): Promise<void> {
    this.loaded ??= firstValueFrom(this.api.get<SessionUser>("/session")).then(
      (u) => this.user.set(u),
      (e: unknown) => {
        this.loaded = undefined
        if (!(e instanceof ApiError && e.status === 401)) throw e
      },
    )
    return this.loaded
  }
  clear() {
    this.user.set(null)
    this.loaded = Promise.resolve()
  }
}

export const authGuard: CanActivateChildFn = async (_route, state) => {
  const session = inject(Session) // inject before the await
  const router = inject(Router)
  await session.ensureLoaded()
  return session.user() ? true : router.createUrlTree(["/login"], { queryParams: { returnTo: state.url } })
}
```

```ts
// file: src/app/app.routes.ts
import type { Routes } from "@angular/router"
import { t } from "./i18n"
import { authGuard } from "./session/session"

// Route titles become document.title (the default TitleStrategy); screen readers read them.
export const routes: Routes = [
  { path: "login", title: t("login.title"), loadComponent: () => import("./pages/login-page").then((m) => m.LoginPage) },
  {
    path: "",
    canActivateChild: [authGuard],
    children: [{ path: "orders", title: t("orders.title"), loadComponent: () => import("./orders/orders-page").then((m) => m.OrdersPage) }],
  },
]
```

```ts
// file: src/app/app.config.ts
import { provideHttpClient, withFetch, withInterceptors } from "@angular/common/http"
import { type ApplicationConfig, provideBrowserGlobalErrorListeners } from "@angular/core"
import { provideRouter } from "@angular/router"
import { provideRouteFocus } from "./a11y/route-focus"
import { apiErrorInterceptor } from "./api/api-client"
import { routes } from "./app.routes"

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes),
    provideHttpClient(withFetch(), withInterceptors([apiErrorInterceptor])),
    provideRouteFocus(),
  ],
}
```

## 6. Safe rendering: `[innerHTML]` and `bypassSecurityTrust*`

- Interpolation escapes.
- `[innerHTML]` runs Angular's sanitizer, but secure-rendering rule 2 still requires DOMPurify output with a comment that cites the FR, and the review grep flags every `[innerHTML]`.
- **`bypassSecurityTrust*` is forbidden.** It switches the sanitizer off, and under Trusted Types it needs the `angular#unsafe-bypass` policy.
- Angular rewrites a `javascript:` `[href]` to `unsafe:…`, but don't rely on that: use `safeHref` from `ui/secure-rendering.md`.
- With `@angular/ssr`, use `isomorphic-dompurify`, because DOMPurify needs a DOM.

```ts
// file: src/app/security/safe-html.ts
import { ChangeDetectionStrategy, Component, computed, input } from "@angular/core"
import DOMPurify from "dompurify"

// Reason: FR-012 rich-text order notes from the editor. Sanitized here, at render time.
@Component({
  selector: "app-safe-html",
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<div [innerHTML]="clean()"></div>`,
})
export class SafeHtml {
  readonly html = input.required<string>()
  protected readonly clean = computed(() => DOMPurify.sanitize(this.html(), { USE_PROFILES: { html: true } }))
}
```

## 7. Accessibility

- The Router doesn't move focus. After each in-app navigation, focus the new page's `<h1 tabindex="-1">`. The route `title` has already set `document.title`. The root `App` renders a skip link to `<main id="main">`, with the `<router-outlet />` inside it.
- Announce dynamic results ("20 more orders loaded") with `LiveAnnouncer` from `@angular/cdk/a11y`, and trap focus in dialogs with `cdkTrapFocus`.
- Forms (§4): `aria-invalid` and `aria-describedby` are bound per field, because Signal Forms doesn't set them. Form-level errors get `role="alert"`, and a failed submit focuses the first error (`focusBoundControl()`).

```ts
// file: src/app/a11y/route-focus.ts
import { afterNextRender, DestroyRef, type EnvironmentProviders, inject, Injector, provideEnvironmentInitializer } from "@angular/core"
import { takeUntilDestroyed } from "@angular/core/rxjs-interop"
import { NavigationEnd, Router } from "@angular/router"
import { filter, skip } from "rxjs"

export function provideRouteFocus(): EnvironmentProviders {
  return provideEnvironmentInitializer(() => {
    const injector = inject(Injector)
    inject(Router).events.pipe(filter((e) => e instanceof NavigationEnd), skip(1), takeUntilDestroyed(inject(DestroyRef)))
      .subscribe(() => afterNextRender(() => document.querySelector<HTMLElement>("main h1")?.focus(), { injector }))
  })
}
```

## 8. Component tests: Testing Library, MSW and axe on Vitest (ui_test_agent Part A)

- `ng test` runs Vitest with jsdom, the CLI default since v21. Register the setup file under the `test` target's `setupFiles` in `angular.json`.
- Render with the app's real providers: `withFetch()` and the interceptor, so the tests exercise the same envelope unwrapping.
- The response bodies come from `msw.md`'s typed helpers (`ok`, `page`, `apiError` in `app/mocks/envelope.ts`). In MSW 3, `onUnhandledRequest` is renamed `onUnhandledFrame`; the root `msw` imports work on 2.x and 3.x.
- jsdom has no layout, so the axe check covers names, roles and ARIA, not contrast (contrast is Part B).

```ts
// file: src/app/testing/setup.ts
import "@testing-library/jest-dom/vitest"
import { setupServer } from "msw/node"
import { afterAll, afterEach, beforeAll } from "vitest"

export const server = setupServer() // no default handlers: each test declares what the screen calls
beforeAll(() => server.listen({ onUnhandledFrame: "error" }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
```

```ts
// file: src/app/testing/axe.ts
import axe from "axe-core"
import { expect } from "vitest"

const WCAG = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]
export async function expectNoAxeViolations(el: Element) {
  const { violations } = await axe.run(el, { runOnly: { type: "tag", values: WCAG }, rules: { "color-contrast": { enabled: false } } })
  expect(violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`)).toEqual([])
}
```

```ts
// file: src/app/orders/order-list.spec.ts
import { provideHttpClient, withFetch, withInterceptors } from "@angular/common/http"
import { provideRouter } from "@angular/router"
import { render, screen } from "@testing-library/angular"
import userEvent from "@testing-library/user-event"
import { delay, http, type PathParams } from "msw"
import { describe, expect, it } from "vitest"
import { apiErrorInterceptor } from "../api/api-client"
import type { ApiErrorBody, ApiSuccess, Order } from "../api/types"
import { apiError, page } from "../mocks/envelope"
import { server } from "../testing/setup"
import { expectNoAxeViolations } from "../testing/axe"
import { OrderForm } from "./order-form"
import { OrderList } from "./order-list"

type Res<T> = ApiSuccess<T> | ApiErrorBody // a handler that can answer either way is typed with both
const ORDERS = "/api/v1/orders"
const providers = [provideRouter([]), provideHttpClient(withFetch(), withInterceptors([apiErrorInterceptor]))]
const order = (o: Partial<Order> = {}): Order => ({ id: "o1", customer_name: "Alice", customer_email: "alice@example.com",
  quantity: 1, status: "open", total_cents: 1299, created_at: "2026-09-30T12:00:00Z", ...o })

describe("OrderList", () => {
  it("TC-UI-20107 shows a skeleton while loading", async () => {
    server.use(http.get(ORDERS, async () => { await delay("infinite"); return page([]) }))
    await render(OrderList, { providers })
    expect(await screen.findByTestId("orders-loading")).toHaveAttribute("aria-busy", "true")
  })
  it("TC-UI-20108 shows the empty state for data: []", async () => {
    server.use(http.get(ORDERS, () => page([])))
    await render(OrderList, { providers })
    expect(await screen.findByRole("heading", { name: "No orders yet" })).toBeVisible()
  })
  it("TC-UI-20109 shows the envelope message and retries", async () => {
    let calls = 0
    server.use(http.get<PathParams, never, Res<Order[]>>(ORDERS, () =>
      ++calls === 1 ? apiError(503, "UNAVAILABLE", "Try again shortly.") : page([order()])))
    await render(OrderList, { providers })
    expect(await screen.findByRole("alert")).toHaveTextContent("Try again shortly.")
    await userEvent.click(screen.getByRole("button", { name: "Retry" }))
    expect(await screen.findByTestId("orders-table")).toHaveTextContent("Alice")
  })
  it("TC-UI-20110 loads the next page with meta.pagination.next_cursor", async () => {
    server.use(http.get(ORDERS, ({ request }) => new URL(request.url).searchParams.get("cursor") === "c2"
      ? page([order({ id: "o2", customer_name: "Bob" })])
      : page([order()], { has_more: true, next_cursor: "c2" })))
    await render(OrderList, { providers })
    await userEvent.click(await screen.findByRole("button", { name: "Load more" }))
    expect(await screen.findByText(/Bob/)).toBeVisible()
    expect(screen.getByText(/Alice/)).toBeVisible()
  })
  it("TC-SEC-20111 XSS-RENDER: markup in a name renders as text", async () => {
    const payload = `<img src=x onerror="window.__xss=1">`
    server.use(http.get(ORDERS, () => page([order({ customer_name: payload })])))
    await render(OrderList, { providers })
    expect(await screen.findByText(payload, { exact: false })).toBeVisible()
    expect("__xss" in window).toBe(false)
  })
  it("TC-A11Y-20112 data state: names and roles pass axe (contrast is Part B)", async () => {
    server.use(http.get(ORDERS, () => page([order()])))
    const { container } = await render(OrderList, { providers })
    await screen.findByTestId("orders-table")
    await expectNoAxeViolations(container)
  })
})

describe("OrderForm", () => {
  it("TC-FORM-20113 puts the server's details[] on the field and focuses it", async () => {
    server.use(http.post(ORDERS, () => apiError(400, "VALIDATION_FAILED", "Some fields are invalid.",
      { details: [{ field: "customer_email", code: "already_exists", message: "That email already has an open order." }] })))
    await render(OrderForm, { providers })
    const email = screen.getByLabelText("Customer email")
    expect(email).not.toHaveAttribute("aria-invalid") // undefined removes the attribute
    await userEvent.type(email, "bob@example.com")
    await userEvent.click(screen.getByRole("button", { name: "Create order" }))
    expect(await screen.findByText("That email already has an open order.")).toBeVisible()
    expect(email).toHaveAttribute("aria-invalid", "true")
    expect(email).toHaveFocus()
  })
})
```

## Rules
- Every call goes through `ApiClient` or `httpResource`, behind `apiErrorInterceptor`. Components never read `response.data` from an unwrapped body.
- Lists render `data` (always an array) and page with `meta.pagination.next_cursor`. Never compute an offset.
- Mutations use `HttpClient`, never `httpResource`. They are never auto-retried, and a creating POST sends an `Idempotency-Key`.
- `Session.user` holds the profile. Tokens are never in JS. Guards deny by default and return a `UrlTree`.
- `[innerHTML]` only on DOMPurify output, with a reason comment. Never `bypassSecurityTrust*`. Every route has a `title`.
