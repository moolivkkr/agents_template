// HARNESS STUB: the project's i18n function (vue-i18n's global t, Paraglide messages, Angular $localize…).
// The packs call t("key", params); tests assert the English strings below.
const en: Record<string, string> = {
  "app.name": "Acme",
  "a11y.skipToContent": "Skip to content",
  "actions.retry": "Retry",
  "actions.loadMore": "Load more",
  "actions.nextPage": "Next page",
  "errors.generic": "Something went wrong.",
  "errors.supportHint": "If this keeps happening, contact support with reference {requestId}.",
  "login.title": "Sign in",
  "orders.title": "Orders",
  "orders.loading": "Loading orders",
  "orders.empty.title": "No orders yet",
  "orders.empty.description": "Orders you create appear here.",
  "orders.empty.cta": "Create order",
  "orders.form.title": "New order",
  "orders.form.email": "Customer email",
  "orders.form.quantity": "Quantity",
  "orders.form.submit": "Create order",
}

export function t(key: string, params: Record<string, string | number> = {}): string {
  return (en[key] ?? key).replace(/\{(\w+)\}/g, (_m, name: string) => String(params[name] ?? `{${name}}`))
}
