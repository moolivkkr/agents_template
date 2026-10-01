# chi v5 patterns for Go HTTP APIs.

> Go samples compile-checked (go build + go vet) 2026-09-30 with Go 1.27.1, chi v5.3.2, and run: a smoke test drives the router (malformed id → 400, a found user → the data/meta envelope, RequireTenant without identity → 401) (tests/archetype-compile/go/run.sh).

## Router Setup
```go
import (
    "github.com/go-chi/chi/v5"
    chimw "github.com/go-chi/chi/v5/middleware"

    "yourapp/internal/apperr"     // backend/archetypes/error-handling-go.md
    "yourapp/internal/middleware" // backend/archetypes/auth-middleware-go.md
)

func NewRouter(handlers *Handlers, mw *Middleware, logger *slog.Logger) *chi.Mux {
    r := chi.NewRouter()
    r.Use(middleware.RequestID)              // validated X-Request-ID or a new one (chimw.RequestID trusts any value)
    r.Use(chimw.RealIP)                      // only behind a proxy that overwrites X-Forwarded-For / X-Real-IP
    r.Use(apperr.RecoveryMiddleware(logger)) // panic → INTERNAL error envelope (chimw.Recoverer sends an empty 500)
    r.Use(mw.Logger)
    r.Use(mw.Timeout(30 * time.Second))

    r.Route("/api/v1", func(r chi.Router) {
        r.Use(mw.Auth) // middleware.JWTAuth: tenant and user come from the verified token only
        r.Route("/users", func(r chi.Router) {
            r.Get("/", handlers.ListUsers)
            r.Post("/", handlers.CreateUser)
            r.Route("/{id}", func(r chi.Router) {
                r.Get("/", handlers.GetUser)
                r.Put("/", handlers.UpdateUser)
                r.Delete("/", handlers.DeleteUser)
            })
        })
    })
    return r
}
```
- Use `chi.NewRouter()` — stdlib-compatible `http.Handler`
- Group routes with `r.Route("/prefix", func(r chi.Router) { ... })` — clean nesting
- Middleware via `r.Use()` at any level — applies to all routes below

## URL Parameters
```go
func (h *Handler) GetUser(w http.ResponseWriter, r *http.Request) {
    id, err := uuid.Parse(chi.URLParam(r, "id")) // from /{id} in route
    if err != nil {
        apperr.ErrorMapper(w, r, apperr.NewValidationError("id", "invalid_format", "Must be a valid ID."))
        return
    }
    user, err := h.service.Get(r.Context(), id) // the service scopes by the verified tenant
    if err != nil {
        apperr.ErrorMapper(w, r, err)
        return
    }
    respondJSON(w, r, http.StatusOK, user)
}
```
- `chi.URLParam(r, "name")` — always returns string, validate/parse yourself
- Define URL params as `{name}` in route pattern (not `:name`)

## Middleware Pattern
```go
// The tenant is never read from the request (header, path, body): middleware.JWTAuth puts the
// verified token's tenant in the context. A route middleware only checks it is there.
func RequireTenant(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        if _, err := middleware.TenantIDFromContext(r.Context()); err != nil {
            apperr.ErrorMapper(w, r, apperr.NewUnauthenticatedError())
            return
        }
        next.ServeHTTP(w, r)
    })
}
```
- chi middleware is stdlib `func(http.Handler) http.Handler`
- Use `r.Context()` / `r.WithContext()` for request-scoped values
- Chain: `r.Use(A, B, C)` — A runs first, C runs last

## Response Pattern
```go
// The one success envelope (api/response-envelope.md): {"data": ..., "meta": {"request_id": ...}}.
// Errors go through apperr.ErrorMapper — never a second shape.
func respondJSON(w http.ResponseWriter, r *http.Request, status int, data any) {
    w.Header().Set("Content-Type", "application/json; charset=utf-8")
    w.WriteHeader(status)
    body := map[string]any{
        "data": data,
        "meta": map[string]any{"request_id": middleware.RequestIDFromContext(r.Context())},
    }
    if err := json.NewEncoder(w).Encode(body); err != nil {
        slog.ErrorContext(r.Context(), "write response", "error", err) // the status is already sent
    }
}
```
- chi doesn't have built-in response helpers — create your own in `internal/dto/`
- Always set Content-Type before WriteHeader
- Use `render.JSON` from `go-chi/render` if you want a helper

## Subrouters and Mounting
```go
// Mount a separate router (e.g., protocol endpoints on a different port)
protocolRouter := chi.NewRouter()
protocolRouter.Get("/ocsp", handlers.OCSP)
protocolRouter.Get("/crl/{caID}", handlers.CRL)
mainRouter.Mount("/protocols", protocolRouter)
```

## Testing
```go
// chi routes work with httptest because they implement http.Handler
ts := httptest.NewServer(router)
defer ts.Close()
req, err := http.NewRequestWithContext(t.Context(), http.MethodGet, ts.URL+"/api/v1/users", nil)
require.NoError(t, err)
req.Header.Set("Authorization", "Bearer "+token) // the API routes are behind JWTAuth
resp, err := ts.Client().Do(req)
require.NoError(t, err)
defer resp.Body.Close()
assert.Equal(t, http.StatusOK, resp.StatusCode)
```
- Use `httptest.NewServer(router)` — chi router is stdlib-compatible
- No special test helpers needed
