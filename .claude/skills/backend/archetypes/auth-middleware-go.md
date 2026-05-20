> **This file contains Go-specific patterns for: Auth Middleware Archetype.** The language-neutral version at [auth-middleware.md](auth-middleware.md) contains the same Go patterns and serves as the canonical reference. This file exists for consistent `{{LANG}}` placeholder resolution by `agent_factory`.

---
skill: auth-middleware
description: Go auth middleware archetype — JWT validation, RBAC, tenant context, rate limiting, CORS, API key auth, request ID, structured logging
version: "1.0"
tags:
  - go
  - middleware
  - auth
  - jwt
  - rbac
  - archetype
  - backend
---
# Auth Middleware Archetype

Complete authentication and authorization middleware for chi router. Every generated auth layer MUST follow this pattern.

## Context Key Types

```go
package middleware

import (
    "context"
    "crypto/subtle"
    "errors"
    "fmt"
    "log/slog"
    "net/http"
    "strings"
    "sync"
    "time"

    "github.com/go-chi/chi/v5"
    "github.com/golang-jwt/jwt/v5"
    "github.com/google/uuid"
    "golang.org/x/time/rate"
)

// Context key types — unexported to prevent collisions.
type contextKey int

const (
    ctxKeyUserID contextKey = iota
    ctxKeyTenantID
    ctxKeyRoles
    ctxKeyPermissions
    ctxKeyRequestID
    ctxKeyLogger
)
```

## Context Helpers

```go
// TenantIDFromContext extracts the authenticated tenant ID.
// Returns error if no tenant context is set (middleware was bypassed).
func TenantIDFromContext(ctx context.Context) (uuid.UUID, error) {
    id, ok := ctx.Value(ctxKeyTenantID).(uuid.UUID)
    if !ok || id == uuid.Nil {
        return uuid.Nil, errors.New("tenant_id not found in context")
    }
    return id, nil
}

// UserIDFromContext extracts the authenticated user ID.
func UserIDFromContext(ctx context.Context) (uuid.UUID, error) {
    id, ok := ctx.Value(ctxKeyUserID).(uuid.UUID)
    if !ok || id == uuid.Nil {
        return uuid.Nil, errors.New("user_id not found in context")
    }
    return id, nil
}

// RolesFromContext extracts the user's roles.
func RolesFromContext(ctx context.Context) []string {
    roles, _ := ctx.Value(ctxKeyRoles).([]string)
    return roles
}

// PermissionsFromContext extracts the user's permissions.
func PermissionsFromContext(ctx context.Context) []string {
    perms, _ := ctx.Value(ctxKeyPermissions).([]string)
    return perms
}

// LoggerFromContext returns the request-scoped logger enriched with auth context.
func LoggerFromContext(ctx context.Context) *slog.Logger {
    if l, ok := ctx.Value(ctxKeyLogger).(*slog.Logger); ok {
        return l
    }
    return slog.Default()
}
```

## Request ID Middleware

```go
// RequestID generates or extracts a unique request ID for tracing.
// Checks X-Request-ID header first (client correlation), generates UUID if absent.
func RequestID(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        reqID := r.Header.Get("X-Request-ID")
        if reqID == "" {
            reqID = uuid.New().String()
        }

        // Set on response header for client correlation
        w.Header().Set("X-Request-ID", reqID)

        ctx := context.WithValue(r.Context(), ctxKeyRequestID, reqID)
        next.ServeHTTP(w, r.WithContext(ctx))
    })
}

// RequestIDFromContext extracts the request ID set by the RequestID middleware.
func RequestIDFromContext(ctx context.Context) string {
    if id, ok := ctx.Value(ctxKeyRequestID).(string); ok {
        return id
    }
    return ""
}
```

## JWT Authentication Middleware

```go
// JWTConfig holds configuration for JWT token validation.
type JWTConfig struct {
    SigningKey     []byte // HMAC key or public key for RS256
    Issuer        string // Expected issuer claim
    Audience      string // Expected audience claim
    SigningMethod string // "HS256", "RS256", etc.
}

// JWTAuth validates the Bearer token and injects claims into context.
func JWTAuth(cfg JWTConfig) func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            // 1. Extract token from Authorization header
            token, err := extractBearerToken(r)
            if err != nil {
                writeAuthError(w, http.StatusUnauthorized, "UNAUTHORIZED", err.Error())
                return
            }

            // 2. Parse and validate token
            claims, err := validateToken(token, cfg)
            if err != nil {
                writeAuthError(w, http.StatusUnauthorized, "INVALID_TOKEN", "invalid or expired token")
                return
            }

            // 3. Extract claims
            userID, err := uuid.Parse(claims.Subject)
            if err != nil {
                writeAuthError(w, http.StatusUnauthorized, "INVALID_TOKEN", "invalid subject claim")
                return
            }
            tenantID, err := uuid.Parse(claims.TenantID)
            if err != nil {
                writeAuthError(w, http.StatusUnauthorized, "INVALID_TOKEN", "invalid tenant_id claim")
                return
            }

            // 4. Inject into context
            ctx := r.Context()
            ctx = context.WithValue(ctx, ctxKeyUserID, userID)
            ctx = context.WithValue(ctx, ctxKeyTenantID, tenantID)
            ctx = context.WithValue(ctx, ctxKeyRoles, claims.Roles)
            ctx = context.WithValue(ctx, ctxKeyPermissions, claims.Permissions)

            // 5. Enrich logger with auth context
            reqID := RequestIDFromContext(ctx)
            logger := slog.With(
                "user_id", userID,
                "tenant_id", tenantID,
                "roles", claims.Roles,
                "request_id", reqID,
            )
            ctx = context.WithValue(ctx, ctxKeyLogger, logger)

            next.ServeHTTP(w, r.WithContext(ctx))
        })
    }
}

// CustomClaims extends standard JWT claims with application-specific fields.
type CustomClaims struct {
    jwt.RegisteredClaims
    TenantID    string   `json:"tenant_id"`
    Roles       []string `json:"roles"`
    Permissions []string `json:"permissions"`
}

func extractBearerToken(r *http.Request) (string, error) {
    auth := r.Header.Get("Authorization")
    if auth == "" {
        return "", errors.New("missing Authorization header")
    }
    parts := strings.SplitN(auth, " ", 2)
    if len(parts) != 2 || !strings.EqualFold(parts[0], "Bearer") {
        return "", errors.New("invalid Authorization header format — expected 'Bearer <token>'")
    }
    return parts[1], nil
}

func validateToken(tokenString string, cfg JWTConfig) (*CustomClaims, error) {
    claims := &CustomClaims{}

    token, err := jwt.ParseWithClaims(tokenString, claims, func(token *jwt.Token) (any, error) {
        // Verify signing method matches expected
        if token.Method.Alg() != cfg.SigningMethod {
            return nil, fmt.Errorf("unexpected signing method: %s", token.Method.Alg())
        }
        return cfg.SigningKey, nil
    },
        jwt.WithIssuer(cfg.Issuer),
        jwt.WithAudience(cfg.Audience),
        jwt.WithExpirationRequired(),
    )
    if err != nil {
        return nil, fmt.Errorf("token validation: %w", err)
    }
    if !token.Valid {
        return nil, errors.New("invalid token")
    }

    return claims, nil
}
```

## API Key Authentication (Alternative to JWT)

```go
// APIKeyConfig holds configuration for API key validation.
type APIKeyConfig struct {
    // LookupFunc resolves an API key to tenant/user context.
    // In production, this queries a hashed key store (never store keys in plaintext).
    LookupFunc func(ctx context.Context, key string) (*APIKeyIdentity, error)
}

type APIKeyIdentity struct {
    TenantID    uuid.UUID
    UserID      uuid.UUID
    Roles       []string
    Permissions []string
}

// APIKeyAuth validates an API key from the X-API-Key header.
func APIKeyAuth(cfg APIKeyConfig) func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            apiKey := r.Header.Get("X-API-Key")
            if apiKey == "" {
                writeAuthError(w, http.StatusUnauthorized, "UNAUTHORIZED", "missing X-API-Key header")
                return
            }

            identity, err := cfg.LookupFunc(r.Context(), apiKey)
            if err != nil {
                writeAuthError(w, http.StatusUnauthorized, "INVALID_API_KEY", "invalid API key")
                return
            }

            ctx := r.Context()
            ctx = context.WithValue(ctx, ctxKeyUserID, identity.UserID)
            ctx = context.WithValue(ctx, ctxKeyTenantID, identity.TenantID)
            ctx = context.WithValue(ctx, ctxKeyRoles, identity.Roles)
            ctx = context.WithValue(ctx, ctxKeyPermissions, identity.Permissions)

            next.ServeHTTP(w, r.WithContext(ctx))
        })
    }
}
```

## RBAC Middleware

```go
// RequireRole returns middleware that checks the user has at least one of the specified roles.
func RequireRole(roles ...string) func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            userRoles := RolesFromContext(r.Context())
            for _, required := range roles {
                for _, actual := range userRoles {
                    if actual == required {
                        next.ServeHTTP(w, r)
                        return
                    }
                }
            }
            writeAuthError(w, http.StatusForbidden, "FORBIDDEN",
                fmt.Sprintf("requires one of roles: %s", strings.Join(roles, ", ")))
        })
    }
}

// RequirePermission returns middleware that checks the user has all specified permissions.
func RequirePermission(permissions ...string) func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            userPerms := PermissionsFromContext(r.Context())
            permSet := make(map[string]bool, len(userPerms))
            for _, p := range userPerms {
                permSet[p] = true
            }
            for _, required := range permissions {
                if !permSet[required] {
                    writeAuthError(w, http.StatusForbidden, "FORBIDDEN",
                        fmt.Sprintf("missing permission: %s", required))
                    return
                }
            }
            next.ServeHTTP(w, r)
        })
    }
}
```

## Rate Limiting per Tenant

```go
// TenantRateLimiter implements token bucket rate limiting scoped per tenant.
type TenantRateLimiter struct {
    mu       sync.RWMutex
    limiters map[uuid.UUID]*rate.Limiter
    rps      rate.Limit // requests per second
    burst    int        // max burst size
}

func NewTenantRateLimiter(rps float64, burst int) *TenantRateLimiter {
    return &TenantRateLimiter{
        limiters: make(map[uuid.UUID]*rate.Limiter),
        rps:      rate.Limit(rps),
        burst:    burst,
    }
}

func (trl *TenantRateLimiter) getLimiter(tenantID uuid.UUID) *rate.Limiter {
    trl.mu.RLock()
    limiter, ok := trl.limiters[tenantID]
    trl.mu.RUnlock()
    if ok {
        return limiter
    }

    trl.mu.Lock()
    defer trl.mu.Unlock()
    // Double-check after acquiring write lock
    if limiter, ok = trl.limiters[tenantID]; ok {
        return limiter
    }
    limiter = rate.NewLimiter(trl.rps, trl.burst)
    trl.limiters[tenantID] = limiter
    return limiter
}

// RateLimit returns middleware that enforces per-tenant rate limits.
func (trl *TenantRateLimiter) RateLimit() func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            tenantID, err := TenantIDFromContext(r.Context())
            if err != nil {
                // No tenant context — rate limit by IP as fallback
                next.ServeHTTP(w, r)
                return
            }

            limiter := trl.getLimiter(tenantID)
            if !limiter.Allow() {
                w.Header().Set("Retry-After", "1")
                w.Header().Set("X-RateLimit-Limit", fmt.Sprintf("%.0f", float64(trl.rps)))
                w.Header().Set("X-RateLimit-Remaining", "0")
                writeAuthError(w, http.StatusTooManyRequests, "RATE_LIMITED", "too many requests — retry after cooldown")
                return
            }

            next.ServeHTTP(w, r)
        })
    }
}
```

## CORS Configuration

```go
// CORSConfig defines allowed origins, methods, and headers.
type CORSConfig struct {
    AllowedOrigins   []string
    AllowedMethods   []string
    AllowedHeaders   []string
    ExposedHeaders   []string
    AllowCredentials bool
    MaxAge           int // preflight cache duration in seconds
}

// CORS returns middleware that handles Cross-Origin Resource Sharing.
func CORS(cfg CORSConfig) func(http.Handler) http.Handler {
    originSet := make(map[string]bool, len(cfg.AllowedOrigins))
    for _, o := range cfg.AllowedOrigins {
        originSet[o] = true
    }

    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            origin := r.Header.Get("Origin")

            if originSet[origin] || originSet["*"] {
                w.Header().Set("Access-Control-Allow-Origin", origin)
            }

            if cfg.AllowCredentials {
                w.Header().Set("Access-Control-Allow-Credentials", "true")
            }

            if len(cfg.ExposedHeaders) > 0 {
                w.Header().Set("Access-Control-Expose-Headers", strings.Join(cfg.ExposedHeaders, ", "))
            }

            // Handle preflight
            if r.Method == http.MethodOptions {
                w.Header().Set("Access-Control-Allow-Methods", strings.Join(cfg.AllowedMethods, ", "))
                w.Header().Set("Access-Control-Allow-Headers", strings.Join(cfg.AllowedHeaders, ", "))
                w.Header().Set("Access-Control-Max-Age", fmt.Sprintf("%d", cfg.MaxAge))
                w.WriteHeader(http.StatusNoContent)
                return
            }

            next.ServeHTTP(w, r)
        })
    }
}
```

## Request Logger Enrichment

```go
// LogEnrichment adds request metadata to the structured logger for every downstream handler.
func LogEnrichment(baseLogger *slog.Logger) func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            reqID := RequestIDFromContext(r.Context())
            logger := baseLogger.With(
                "request_id", reqID,
                "method", r.Method,
                "path", r.URL.Path,
                "remote_addr", r.RemoteAddr,
                "user_agent", r.UserAgent(),
            )

            ctx := context.WithValue(r.Context(), ctxKeyLogger, logger)
            next.ServeHTTP(w, r.WithContext(ctx))
        })
    }
}
```

## Middleware Stack Assembly

```go
// SetupMiddleware assembles the full middleware stack in correct order.
// Order matters: outermost middleware runs first.
func SetupMiddleware(r chi.Router, cfg AppConfig) {
    // 1. CORS — must be outermost to handle preflight before auth
    r.Use(CORS(cfg.CORS))

    // 2. Request ID — generate/extract before anything else
    r.Use(RequestID)

    // 3. Log enrichment — enrich logger with request metadata
    r.Use(LogEnrichment(cfg.Logger))

    // 4. Recovery — catch panics, log, return 500
    r.Use(RecoveryMiddleware(cfg.Logger))

    // 5. Authentication — JWT or API key (sets tenant/user context)
    r.Use(JWTAuth(cfg.JWT))

    // 6. Rate limiting — per-tenant, after auth so we know the tenant
    rl := NewTenantRateLimiter(100, 200) // 100 rps, burst 200
    r.Use(rl.RateLimit())

    // Route-level RBAC:
    // r.With(RequireRole("admin")).Post("/admin/settings", adminHandler)
    // r.With(RequirePermission("users:write")).Put("/users/{id}", updateUserHandler)
}
```

## Auth Error Response Helper

```go
func writeAuthError(w http.ResponseWriter, status int, code, message string) {
    w.Header().Set("Content-Type", "application/json; charset=utf-8")
    if status == http.StatusUnauthorized {
        w.Header().Set("WWW-Authenticate", "Bearer")
    }
    w.WriteHeader(status)
    json.NewEncoder(w).Encode(map[string]any{
        "error": map[string]any{
            "code":    code,
            "message": message,
        },
    })
}
```

## Critical Rules

- JWT validation MUST check signature, expiration, issuer, AND audience — never skip any
- Tenant ID MUST come from the validated token, NEVER from request params or body
- API keys MUST be stored as hashes (bcrypt/argon2) — never compare plaintext
- Use `crypto/subtle.ConstantTimeCompare` for any secret comparison to prevent timing attacks
- Rate limiters MUST be per-tenant — shared limits allow noisy neighbor abuse
- CORS MUST NOT use `*` with `AllowCredentials: true` — browsers reject this
- Request ID MUST be set on response headers for client-side correlation
- Logger MUST be enriched with user_id, tenant_id, request_id at the auth boundary
- Middleware order matters: CORS -> RequestID -> Logger -> Recovery -> Auth -> RateLimit
- RBAC checks (RequireRole, RequirePermission) are applied per-route, not globally
- Never log JWT tokens, API keys, or credentials — log only derived identifiers
- Context helpers MUST return errors when values are missing — never return zero values silently
