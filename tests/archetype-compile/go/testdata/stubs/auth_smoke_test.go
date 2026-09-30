// HARNESS SMOKE TEST (tests/archetype-compile/go) — not archetype code.
// Drives auth-middleware-go.md's RequestID + JWTAuth with tokens signed by the pinned golang-jwt:
// a valid token reaches the handler with the token's tenant/user in the context; every rejection
// is a 401 in the one error envelope with request_id == X-Request-Id.

package middleware

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"github.com/google/uuid"
)

var (
	testKey    = []byte("test-only-hmac-key-0123456789abcdef")
	testTenant = uuid.MustParse("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
	testUser   = uuid.MustParse("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
	testCfg    = JWTConfig{VerifyKey: testKey, Issuer: "https://auth.example.com", Audience: "widgets-api", SigningMethod: "HS256"}
)

func sign(t *testing.T, method jwt.SigningMethod, key any, mutate func(*CustomClaims)) string {
	t.Helper()
	c := &CustomClaims{
		RegisteredClaims: jwt.RegisteredClaims{
			Subject:   testUser.String(),
			Issuer:    testCfg.Issuer,
			Audience:  jwt.ClaimStrings{testCfg.Audience},
			ExpiresAt: jwt.NewNumericDate(time.Now().Add(time.Hour)),
		},
		TenantID: testTenant.String(),
		Roles:    []string{"member"},
	}
	if mutate != nil {
		mutate(c)
	}
	s, err := jwt.NewWithClaims(method, c).SignedString(key)
	if err != nil {
		t.Fatal(err)
	}
	return s
}

func serve(t *testing.T, authz string) (*httptest.ResponseRecorder, bool) {
	t.Helper()
	reached := false
	h := RequestID(JWTAuth(testCfg)(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		reached = true
		tenant, err := TenantIDFromContext(r.Context())
		user, err2 := UserIDFromContext(r.Context())
		if err != nil || err2 != nil || tenant != testTenant || user != testUser {
			t.Errorf("identity in context = %v/%v (%v, %v)", tenant, user, err, err2)
		}
		w.WriteHeader(http.StatusNoContent)
	})))
	req := httptest.NewRequest(http.MethodGet, "/api/v1/widgets", nil)
	if authz != "" {
		req.Header.Set("Authorization", authz)
	}
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	return rec, reached
}

func TestJWTAuthAcceptsValidToken(t *testing.T) {
	rec, reached := serve(t, "Bearer "+sign(t, jwt.SigningMethodHS256, testKey, nil))
	if !reached || rec.Code != http.StatusNoContent {
		t.Fatalf("valid token: status %d, reached %v, body %s", rec.Code, reached, rec.Body)
	}
}

func TestJWTAuthRejections(t *testing.T) {
	other := []byte("some-other-key-0123456789abcdefgh")
	cases := map[string]string{
		"missing header":  "",
		"not bearer":      "Basic dXNlcjpwYXNz",
		"wrong key":       "Bearer " + sign(t, jwt.SigningMethodHS256, other, nil),
		"wrong algorithm": "Bearer " + sign(t, jwt.SigningMethodHS512, testKey, nil),
		"expired":         "Bearer " + sign(t, jwt.SigningMethodHS256, testKey, func(c *CustomClaims) { c.ExpiresAt = jwt.NewNumericDate(time.Now().Add(-time.Minute)) }),
		"no exp":          "Bearer " + sign(t, jwt.SigningMethodHS256, testKey, func(c *CustomClaims) { c.ExpiresAt = nil }),
		"wrong audience":  "Bearer " + sign(t, jwt.SigningMethodHS256, testKey, func(c *CustomClaims) { c.Audience = jwt.ClaimStrings{"other-api"} }),
		"wrong issuer":    "Bearer " + sign(t, jwt.SigningMethodHS256, testKey, func(c *CustomClaims) { c.Issuer = "https://evil.example.com" }),
		"bad tenant":      "Bearer " + sign(t, jwt.SigningMethodHS256, testKey, func(c *CustomClaims) { c.TenantID = "not-a-uuid" }),
	}
	for name, authz := range cases {
		t.Run(name, func(t *testing.T) {
			rec, reached := serve(t, authz)
			if reached || rec.Code != http.StatusUnauthorized {
				t.Fatalf("status %d, reached %v", rec.Code, reached)
			}
			if rec.Header().Get("WWW-Authenticate") != "Bearer" {
				t.Errorf("WWW-Authenticate = %q", rec.Header().Get("WWW-Authenticate"))
			}
			var body struct {
				Error struct {
					Code      string `json:"code"`
					RequestID string `json:"request_id"`
					Retryable *bool  `json:"retryable"`
				} `json:"error"`
			}
			if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
				t.Fatalf("body %q: %v", rec.Body, err)
			}
			if body.Error.Code != "UNAUTHENTICATED" || body.Error.Retryable == nil ||
				body.Error.RequestID == "" || body.Error.RequestID != rec.Header().Get("X-Request-Id") {
				t.Errorf("error envelope = %s (X-Request-Id %q)", rec.Body, rec.Header().Get("X-Request-Id"))
			}
		})
	}
}
