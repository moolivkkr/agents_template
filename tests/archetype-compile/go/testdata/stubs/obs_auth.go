// HARNESS STUB (tests/archetype-compile/go) — not archetype code.
// observability-go.md 4.2 puts AuthMiddleware in the chain; it is auth-middleware-go.md's
// JWTAuth(cfg), which verifies the token and puts tenant and user into the context.

package middleware

import "net/http"

func AuthMiddleware(next http.Handler) http.Handler { return next }
