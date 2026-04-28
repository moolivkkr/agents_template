# Echo framework patterns for Go HTTP APIs.

## Router Setup
```go
e := echo.New()
e.Use(middleware.Recover())
e.Use(middleware.RequestID())
e.Use(middleware.Logger())

v1 := e.Group("/api/v1")
v1.Use(JWTMiddleware())

users := v1.Group("/users")
users.GET("", handlers.ListUsers)
users.POST("", handlers.CreateUser)
users.GET("/:id", handlers.GetUser)
```

## Handlers
```go
func (h *Handler) CreateUser(c echo.Context) error {
    var req CreateUserRequest
    if err := c.Bind(&req); err != nil {
        return echo.NewHTTPError(http.StatusBadRequest, err.Error())
    }
    if err := c.Validate(&req); err != nil {
        return echo.NewHTTPError(http.StatusBadRequest, err.Error())
    }
    user, err := h.service.Create(c.Request().Context(), req)
    if err != nil {
        return err  // handled by custom error handler
    }
    return c.JSON(http.StatusCreated, user)
}
```

## Custom Error Handler
```go
e.HTTPErrorHandler = func(err error, c echo.Context) {
    var he *echo.HTTPError
    if errors.As(err, &he) {
        c.JSON(he.Code, map[string]any{"error": he.Message})
        return
    }
    // map domain errors
    c.JSON(http.StatusInternalServerError, map[string]any{"error": "internal error"})
}
```

## Rules
- Register a custom validator on `e.Validator` — don't skip validation
- Use `c.Request().Context()` for service calls — never `context.Background()`
- `echo.NewHTTPError` for expected HTTP errors; return domain errors and map in error handler
- Graceful shutdown with `e.Shutdown(ctx)`
