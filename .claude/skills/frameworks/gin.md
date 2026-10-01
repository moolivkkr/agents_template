# Gin framework patterns for Go HTTP APIs.

> Go samples compile-checked (go build + go vet) 2026-09-30 with Go 1.27.1, gin v1.12.0, and run: a smoke test drives the router (panic → INTERNAL envelope, validation and malformed body → 400, created → envelope with request_id) (tests/archetype-compile/go/run.sh).

## Router Setup
```go
func NewRouter(handlers *Handlers, middleware *Middleware) *gin.Engine {
    jsonFieldNames() // details[].field is the json name ("email"), not the Go name ("Email")
    r := gin.New()
    r.Use(middleware.RequestID()) // validated X-Request-ID or a new one, echoed as X-Request-Id
    r.Use(gin.CustomRecovery(func(c *gin.Context, rec any) {
        // the INTERNAL error envelope; gin.Recovery() sends an empty 500
        apperr.ErrorMapper(c.Writer, c.Request, fmt.Errorf("panic: %v", rec))
    }))
    r.Use(middleware.Logger())

    v1 := r.Group("/api/v1")
    v1.Use(middleware.Auth()) // tenant and user from the verified token only
    {
        users := v1.Group("/users")
        users.GET("", handlers.ListUsers)
        users.POST("", handlers.CreateUser)
        users.GET("/:id", handlers.GetUser)
    }
    return r
}
```
- Always use `gin.New()` not `gin.Default()` — explicit middleware control
- Group routes by resource; version with `/api/v1/` prefix
- No business logic in route setup — only handler registration

## Request Binding
```go
func (h *Handler) CreateUser(c *gin.Context) {
    var req CreateUserRequest
    if err := c.ShouldBindJSON(&req); err != nil {
        // the one error envelope; the binder's text (Go types, field paths) is never sent
        apperr.ErrorMapper(c.Writer, c.Request, bindError(err))
        return
    }
    user, err := h.service.Create(c.Request.Context(), req)
    if err != nil {
        apperr.ErrorMapper(c.Writer, c.Request, err)
        return
    }
    Created(c, user)
}

// bindError: a validation failure is VALIDATION_FAILED with one detail per field, its code mapped
// onto the closed set by apperr.ValidationDetail (never fe.Tag()); anything else is MALFORMED_REQUEST.
func bindError(err error) error {
    var verrs validator.ValidationErrors
    if !errors.As(err, &verrs) {
        return apperr.NewMalformedRequestError(err)
    }
    fields := make([]apperr.FieldError, 0, len(verrs))
    for _, fe := range verrs {
        fields = append(fields, apperr.ValidationDetail(fe))
    }
    return apperr.NewMultiValidationError(fields)
}

// jsonFieldNames makes gin's validator report each field by its json name.
func jsonFieldNames() {
    if v, ok := binding.Validator.Engine().(*validator.Validate); ok {
        v.RegisterTagNameFunc(func(f reflect.StructField) string {
            if name := strings.SplitN(f.Tag.Get("json"), ",", 2)[0]; name != "-" {
                return name
            }
            return ""
        })
    }
}
```
- `ShouldBindJSON` (not `BindJSON`) — doesn't abort on error, lets you handle it
- Define request structs with `binding:"required"` tags
- Validate at handler level before calling service

## Response Helpers
```go
// The one envelope (api/response-envelope.md). Errors: apperr.ErrorMapper(c.Writer, c.Request, err).
func Success(c *gin.Context, data any) {
    c.JSON(http.StatusOK, gin.H{"data": data, "meta": meta(c)})
}
func Created(c *gin.Context, data any) {
    c.JSON(http.StatusCreated, gin.H{"data": data, "meta": meta(c)})
}
func meta(c *gin.Context) gin.H {
    return gin.H{"request_id": c.Writer.Header().Get("X-Request-Id")} // set by the RequestID middleware
}
```
Define project-wide response helpers — consistent response shape across all endpoints.

## Error Middleware
```go
// ErrorHandler writes the error envelope for an error a handler recorded with c.Error(err).
func ErrorHandler() gin.HandlerFunc {
    return func(c *gin.Context) {
        c.Next()
        if len(c.Errors) > 0 && !c.Writer.Written() {
            apperr.ErrorMapper(c.Writer, c.Request, c.Errors.Last().Err) // domain error → status + envelope
        }
    }
}
```

## Graceful Shutdown
```go
func serve(router http.Handler) error {
    srv := &http.Server{Addr: ":8080", Handler: router, ReadHeaderTimeout: 5 * time.Second}
    errc := make(chan error, 1)
    go func() { errc <- srv.ListenAndServe() }()

    ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
    defer stop()
    select {
    case err := <-errc:
        return err // could not listen (port in use, ...)
    case <-ctx.Done():
    }
    shutdownCtx, cancel := context.WithTimeout(context.Background(), 25*time.Second) // inside the pod's grace period
    defer cancel()
    return srv.Shutdown(shutdownCtx) // stop accepting; wait for in-flight requests
}
```

## Rules
- No `c.Abort()` inside handlers — use early return
- Pass `context.Context` from `c.Request.Context()` to service calls
- Never store mutable state in handlers — handlers are stateless
- Use `gin.H` only for simple responses; define structs for complex shapes
