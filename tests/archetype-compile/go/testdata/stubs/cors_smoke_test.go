// HARNESS SMOKE TEST (tests/archetype-compile/go) — not archetype code.
// Drives auth-middleware-go.md's CORS: only allowlisted origins get CORS headers, credentials only
// with an exact origin, "*" with credentials is refused at construction, "*" alone sends the
// literal "*", and Vary: Origin is always set. The earlier sample echoed any Origin whenever the
// allowlist held "*", with Access-Control-Allow-Credentials: true.

package middleware

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func corsRequest(t *testing.T, cfg CORSConfig, method, origin string) *httptest.ResponseRecorder {
	t.Helper()
	mw, err := CORS(cfg)
	if err != nil {
		t.Fatalf("CORS: %v", err)
	}
	h := mw(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(http.StatusOK) }))
	req := httptest.NewRequest(method, "/api/v1/widgets", nil)
	if origin != "" {
		req.Header.Set("Origin", origin)
	}
	if method == http.MethodOptions {
		req.Header.Set("Access-Control-Request-Method", "POST")
	}
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	return rec
}

func TestCORSAllowlist(t *testing.T) {
	origins, err := ParseOrigins(" https://app.example.com , https://admin.example.com:8443 ")
	if err != nil || len(origins) != 2 {
		t.Fatalf("ParseOrigins = %v, %v", origins, err)
	}
	for _, bad := range []string{"https://app.example.com/", "app.example.com", "https://app.example.com/path", "ftp://x.example.com"} {
		if _, err := ParseOrigins(bad); err == nil {
			t.Errorf("ParseOrigins(%q) accepted a non-origin", bad)
		}
	}

	cfg := CORSConfig{AllowedOrigins: origins, AllowedMethods: []string{"GET", "POST"},
		AllowedHeaders: []string{"Authorization", "Content-Type"}, AllowCredentials: true, MaxAge: 600}

	rec := corsRequest(t, cfg, http.MethodGet, "https://app.example.com")
	if got := rec.Header().Get("Access-Control-Allow-Origin"); got != "https://app.example.com" {
		t.Errorf("allowed origin: ACAO = %q", got)
	}
	if rec.Header().Get("Access-Control-Allow-Credentials") != "true" || rec.Header().Get("Vary") != "Origin" {
		t.Errorf("allowed origin: headers %v", rec.Header())
	}

	rec = corsRequest(t, cfg, http.MethodGet, "https://evil.example.net")
	if rec.Header().Get("Access-Control-Allow-Origin") != "" || rec.Header().Get("Access-Control-Allow-Credentials") != "" {
		t.Errorf("unlisted origin got CORS headers: %v", rec.Header())
	}

	rec = corsRequest(t, cfg, http.MethodOptions, "https://evil.example.net")
	if rec.Code != http.StatusNoContent || rec.Header().Get("Access-Control-Allow-Methods") != "" {
		t.Errorf("preflight from an unlisted origin: %d %v", rec.Code, rec.Header())
	}
	rec = corsRequest(t, cfg, http.MethodOptions, "https://admin.example.com:8443")
	if rec.Header().Get("Access-Control-Allow-Methods") != "GET, POST" {
		t.Errorf("preflight from a listed origin: %v", rec.Header())
	}
}

func TestCORSWildcard(t *testing.T) {
	if _, err := CORS(CORSConfig{AllowedOrigins: []string{"*"}, AllowCredentials: true}); err == nil {
		t.Fatal(`CORS accepted "*" with credentials`)
	}
	rec := corsRequest(t, CORSConfig{AllowedOrigins: []string{"*"}}, http.MethodGet, "https://anyone.example.org")
	if got := rec.Header().Get("Access-Control-Allow-Origin"); got != "*" {
		t.Errorf(`public API: ACAO = %q, want the literal "*"`, got)
	}
	if rec.Header().Get("Access-Control-Allow-Credentials") != "" {
		t.Error("public API sent Access-Control-Allow-Credentials")
	}
}
