# Gin framework patterns for Go HTTP APIs.

## Router Setup
```go
func NewRouter(handlers *Handlers, middleware *Middleware) *gin.Engine {
    r := gin.New()
    r.Use(gin.Recovery())
    r.Use(middleware.Logger())
    r.Use(middleware.RequestID())

    v1 := r.Group("/api/v1")
    v1.Use(middleware.Auth())
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
        c.JSON(http.StatusBadRequest, ErrorResponse{Error: err.Error()})
        return
    }
    // call service
}
```
- `ShouldBindJSON` (not `BindJSON`) — doesn't abort on error, lets you handle it
- Define request structs with `binding:"required"` tags
- Validate at handler level before calling service

## Response Helpers
```go
func Success(c *gin.Context, data any) {
    c.JSON(http.StatusOK, gin.H{"data": data})
}
func Created(c *gin.Context, data any) {
    c.JSON(http.StatusCreated, gin.H{"data": data})
}
func ErrorJSON(c *gin.Context, status int, msg string) {
    c.JSON(status, gin.H{"error": msg})
}
```
Define project-wide response helpers — consistent response shape across all endpoints.

## Error Middleware
```go
func ErrorHandler() gin.HandlerFunc {
    return func(c *gin.Context) {
        c.Next()
        if len(c.Errors) > 0 {
            err := c.Errors.Last()
            // map domain error → HTTP status
        }
    }
}
```

## Graceful Shutdown
```go
srv := &http.Server{Addr: ":8080", Handler: router}
go srv.ListenAndServe()

quit := make(chan os.Signal, 1)
signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
<-quit
ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
defer cancel()
srv.Shutdown(ctx)
```

## Rules
- No `c.Abort()` inside handlers — use early return
- Pass `context.Context` from `c.Request.Context()` to service calls
- Never store mutable state in handlers — handlers are stateless
- Use `gin.H` only for simple responses; define structs for complex shapes
