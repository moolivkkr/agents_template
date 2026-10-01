// HARNESS SMOKE TEST (tests/archetype-compile/go) — not archetype code.
// Runs observability-go.md's server + middleware chain — built on auth-middleware-go.md's RequestID,
// LogEnrichment and JWTAuth in the same package — with in-memory trace and metric SDKs:
//   - the server span is named "HTTP GET /api/v1/orders/{id}" and carries http.route (the earlier
//     sample produced "HTTP GET" behind the chain, and "HTTP GET GET /…" on a bare mux);
//   - the duration histogram is labelled with the route template;
//   - a handler's log line carries request_id, tenant_id and user_id without passing them around.

package main

import (
	"bytes"
	"context"
	"encoding/json"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"github.com/google/uuid"
	"go.opentelemetry.io/otel"
	sdkmetric "go.opentelemetry.io/otel/sdk/metric"
	"go.opentelemetry.io/otel/sdk/metric/metricdata"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	"go.opentelemetry.io/otel/sdk/trace/tracetest"

	"yourapp/internal/middleware"
	"yourapp/internal/server"
)

func TestChainNamesSpanAndLabelsRoute(t *testing.T) {
	spans := tracetest.NewSpanRecorder()
	otel.SetTracerProvider(sdktrace.NewTracerProvider(sdktrace.WithSpanProcessor(spans)))
	reader := sdkmetric.NewManualReader()
	otel.SetMeterProvider(sdkmetric.NewMeterProvider(sdkmetric.WithReader(reader)))

	key := []byte("test-only-hmac-key-0123456789abcdef")
	cfg := middleware.JWTConfig{VerifyKey: key, Issuer: "https://auth.example.com", Audience: "orders-api", SigningMethod: "HS256"}
	tenant, user := uuid.New(), uuid.New()
	token, err := jwt.NewWithClaims(jwt.SigningMethodHS256, &middleware.CustomClaims{
		RegisteredClaims: jwt.RegisteredClaims{
			Subject: user.String(), Issuer: cfg.Issuer, Audience: jwt.ClaimStrings{cfg.Audience},
			ExpiresAt: jwt.NewNumericDate(time.Now().Add(time.Hour)),
		},
		TenantID: tenant.String(),
	}).SignedString(key)
	if err != nil {
		t.Fatal(err)
	}

	var logs bytes.Buffer
	mux := http.NewServeMux()
	mux.HandleFunc("GET /api/v1/orders/{id}", func(w http.ResponseWriter, r *http.Request) {
		middleware.LoggerFromContext(r.Context()).InfoContext(r.Context(), "handled")
		w.WriteHeader(http.StatusOK)
	})
	srv := server.NewServer(middleware.BuildMiddlewareChain(slog.New(slog.NewJSONHandler(&logs, nil)), cfg, mux))

	req := httptest.NewRequest(http.MethodGet, "/api/v1/orders/42", nil)
	req.Header.Set("Authorization", "Bearer "+token)
	rec := httptest.NewRecorder()
	srv.Handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("status %d: %s", rec.Code, rec.Body)
	}

	const route = "/api/v1/orders/{id}"
	ended := spans.Ended()
	if len(ended) == 0 {
		t.Fatal("no span recorded")
	}
	span := ended[len(ended)-1]
	spanRoute := ""
	for _, a := range span.Attributes() {
		if a.Key == "http.route" {
			spanRoute = a.Value.AsString()
		}
	}
	if span.Name() != "HTTP GET "+route || spanRoute != route {
		t.Errorf("server span %q with http.route %q, want %q and %q", span.Name(), spanRoute, "HTTP GET "+route, route)
	}

	var rm metricdata.ResourceMetrics
	if err := reader.Collect(context.Background(), &rm); err != nil {
		t.Fatal(err)
	}
	labelled := false
	for _, sm := range rm.ScopeMetrics {
		for _, m := range sm.Metrics {
			if h, ok := m.Data.(metricdata.Histogram[float64]); ok && m.Name == "http.server.request.duration" {
				for _, dp := range h.DataPoints {
					if v, ok := dp.Attributes.Value("http.route"); ok && v.AsString() == route {
						labelled = true
					}
				}
			}
		}
	}
	if !labelled {
		t.Errorf("http.server.request.duration has no data point with http.route=%q", route)
	}

	var line map[string]any
	if err := json.Unmarshal(logs.Bytes(), &line); err != nil {
		t.Fatalf("log %q: %v", logs.String(), err)
	}
	if line["msg"] != "handled" || line["request_id"] == "" || line["request_id"] == nil ||
		line["tenant_id"] != tenant.String() || line["user_id"] != user.String() {
		t.Errorf("handler log line lacks correlation fields: %s", logs.String())
	}
}
