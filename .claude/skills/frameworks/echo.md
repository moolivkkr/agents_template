# Echo framework patterns for Go HTTP APIs.

> Go samples compile-checked (go build + go vet) 2026-09-30 with Go 1.27.1, Echo v5.4.0, validator v10.30.5, and run: a smoke test drives the router (unknown route 404, no token 401, validation 400 named by json field, malformed 400, created 201 envelope, malformed inbound X-Request-ID replaced) (tests/archetype-compile/go/run.sh).

Echo v5 (`github.com/labstack/echo/v5`): handlers take `*echo.Context`. Echo v4 gets security and bug
fixes only until 2026-12-31 — new code starts on v5.

## Router Setup
```go
import (
    "github.com/labstack/echo/v5"
    echomw "github.com/labstack/echo/v5/middleware"

    "yourapp/internal/middleware" // backend/archetypes/auth-middleware-go.md
)

func NewRouter(handlers *Handlers, jwtCfg middleware.JWTConfig) *echo.Echo {
    e := echo.New()
    e.HTTPErrorHandler = errorHandler // the one error envelope (Custom Error Handler below)
    e.Validator = newRequestValidator()
    e.Use(echo.WrapMiddleware(middleware.RequestID)) // validated X-Request-ID (echomw.RequestID trusts any value)
    e.Use(echomw.Recover())                          // a panic becomes an error → errorHandler → INTERNAL envelope
    e.Use(echomw.RequestLogger())

    v1 := e.Group("/api/v1")
    v1.Use(echo.WrapMiddleware(middleware.JWTAuth(jwtCfg))) // tenant + user from the verified token only

    users := v1.Group("/users")
    users.GET("", handlers.ListUsers)
    users.POST("", handlers.CreateUser)
    users.GET("/:id", handlers.GetUser)
    return e
}
```

## Handlers
```go
func (h *Handler) CreateUser(c *echo.Context) error {
    var req CreateUserRequest
    if err := c.Bind(&req); err != nil {
        return apperr.NewMalformedRequestError(err) // the binder's text is logged, never sent
    }
    if err := c.Validate(&req); err != nil {
        return err // requestValidator: VALIDATION_FAILED with one detail per field
    }
    user, err := h.service.Create(c.Request().Context(), req)
    if err != nil {
        return err // domain error (*apperr.AppError), written by errorHandler
    }
    return c.JSON(http.StatusCreated, map[string]any{ // the one success envelope
        "data": user,
        "meta": map[string]any{"request_id": middleware.RequestIDFromContext(c.Request().Context())},
    })
}
```

## Custom Error Handler
```go
// errorHandler is e.HTTPErrorHandler: every error — echo's own or a domain error — leaves as the one
// error envelope, written by apperr.ErrorMapper (backend/archetypes/error-handling-go.md).
func errorHandler(c *echo.Context, err error) {
    if resp, uerr := echo.UnwrapResponse(c.Response()); uerr == nil && resp.Committed {
        return // the handler already wrote its response
    }
    var appErr *apperr.AppError
    if !errors.As(err, &appErr) {
        // echo's own errors carry a status (echo.StatusCode): unknown route, wrong method, oversized body, ...
        switch code := echo.StatusCode(err); {
        case code == http.StatusNotFound || code == http.StatusMethodNotAllowed:
            err = apperr.NewNotFoundError("Route")
        case code == http.StatusUnauthorized:
            err = apperr.NewUnauthenticatedError()
        case code >= 400 && code < 500:
            err = apperr.NewMalformedRequestError(err)
        } // anything else: unknown → 500 INTERNAL, detail logged only
    }
    apperr.ErrorMapper(c.Response(), c.Request(), err)
}

// requestValidator is e.Validator: go-playground/validator, failures as VALIDATION_FAILED details
// named by the json field.
type requestValidator struct{ v *validator.Validate }

func newRequestValidator() *requestValidator {
    v := validator.New()
    v.RegisterTagNameFunc(func(f reflect.StructField) string {
        return strings.SplitN(f.Tag.Get("json"), ",", 2)[0]
    })
    return &requestValidator{v: v}
}

func (rv *requestValidator) Validate(i any) error {
    err := rv.v.Struct(i)
    var verrs validator.ValidationErrors
    if !errors.As(err, &verrs) {
        return err // nil, or not a struct: a programming error → 500
    }
    fields := make([]apperr.FieldError, 0, len(verrs))
    for _, fe := range verrs {
        fields = append(fields, apperr.FieldError{Field: fe.Field(), Code: fe.Tag(), Message: "This value is not valid."})
    }
    return apperr.NewMultiValidationError(fields)
}
```

## Rules
- Register a custom validator on `e.Validator` — don't skip validation
- Use `c.Request().Context()` for service calls — never `context.Background()`
- Return `*apperr.AppError` (domain) errors; `errorHandler` writes every error as the one envelope
- Graceful shutdown (v5 has no `e.Shutdown`): `echo.StartConfig{Address: ":8080", GracefulTimeout: 25 * time.Second}.Start(ctx, e)`
  with `ctx` from `signal.NotifyContext(ctx, syscall.SIGINT, syscall.SIGTERM)`
