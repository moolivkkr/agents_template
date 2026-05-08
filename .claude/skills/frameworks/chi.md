# chi v5 patterns for Go HTTP APIs.

## Router Setup
```go
func NewRouter(handlers *Handlers, mw *Middleware) *chi.Mux {
    r := chi.NewRouter()
    r.Use(middleware.RequestID)
    r.Use(middleware.RealIP)
    r.Use(middleware.Recoverer)
    r.Use(mw.Logger)
    r.Use(mw.Timeout(30 * time.Second))

    r.Route("/api/v1", func(r chi.Router) {
        r.Use(mw.Auth)
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
    id := chi.URLParam(r, "id")  // from /{id} in route
    // ...
}
```
- `chi.URLParam(r, "name")` — always returns string, validate/parse yourself
- Define URL params as `{name}` in route pattern (not `:name`)

## Middleware Pattern
```go
func TenantMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        tenantID := extractTenantID(r)
        ctx := context.WithValue(r.Context(), tenantKey, tenantID)
        next.ServeHTTP(w, r.WithContext(ctx))
    })
}
```
- chi middleware is stdlib `func(http.Handler) http.Handler`
- Use `r.Context()` / `r.WithContext()` for request-scoped values
- Chain: `r.Use(A, B, C)` — A runs first, C runs last

## Response Pattern
```go
func respondJSON(w http.ResponseWriter, status int, data any) {
    w.Header().Set("Content-Type", "application/json")
    w.WriteHeader(status)
    json.NewEncoder(w).Encode(data)
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
resp, err := http.Get(ts.URL + "/api/v1/users")
```
- Use `httptest.NewServer(router)` — chi router is stdlib-compatible
- No special test helpers needed
