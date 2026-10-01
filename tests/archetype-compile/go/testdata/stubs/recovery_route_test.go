// HARNESS SMOKE TEST (tests/archetype-compile/go) — not archetype code.
// A panic behind chi + the RequestID middleware must be logged with the route template. The earlier
// sample logged r.Pattern, which chi sets only on the request copy it hands the final handler: the
// recovery middleware, earlier in the chain, logged "route":"".

package apperr_test

import (
	"bytes"
	"encoding/json"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/go-chi/chi/v5"

	"yourapp/internal/apperr"
	"yourapp/internal/middleware"
)

func TestRecoveryLogsChiRouteTemplate(t *testing.T) {
	var buf bytes.Buffer
	logger := slog.New(slog.NewJSONHandler(&buf, nil))
	r := chi.NewRouter()
	// SetupMiddleware's order: middleware after Recovery (LogEnrichment, JWTAuth) passes on a copy
	// of the request, so chi's r.Pattern never reaches the *http.Request Recovery holds.
	r.Use(middleware.RequestID)
	r.Use(apperr.RecoveryMiddleware(logger))
	r.Use(middleware.LogEnrichment(slog.New(slog.DiscardHandler)))
	r.Route("/api/v1/widgets", func(r chi.Router) {
		r.Get("/{id}", func(http.ResponseWriter, *http.Request) { panic("boom") })
	})

	rec := httptest.NewRecorder()
	r.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/api/v1/widgets/42", nil))

	if rec.Code != http.StatusInternalServerError {
		t.Fatalf("status %d", rec.Code)
	}
	var line struct {
		Route     string `json:"route"`
		RequestID string `json:"request_id"`
	}
	if err := json.Unmarshal(buf.Bytes(), &line); err != nil {
		t.Fatalf("log %q: %v", buf.String(), err)
	}
	if line.Route != "/api/v1/widgets/{id}" || line.RequestID == "" {
		t.Fatalf("panic log route=%q request_id=%q, want the template and an ID", line.Route, line.RequestID)
	}
}
