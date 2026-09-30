// HARNESS SMOKE TEST (tests/archetype-compile/go) — not archetype code.
// Runs observability-go.md's buildResource against the pinned OTel SDK. The earlier sample merged
// resource.Default() with a semconv v1.26.0 schema URL, which fails at startup with
// "conflicting Schema URL" on any SDK that uses another semconv version.

package main

import (
	"testing"

	"go.opentelemetry.io/otel/attribute"
)

func TestBuildResourceMergesWithSDKDefault(t *testing.T) {
	res, err := buildResource("order-service", "1.0.0", "qa")
	if err != nil {
		t.Fatalf("buildResource: %v", err)
	}
	got, ok := res.Set().Value(attribute.Key("service.name"))
	if !ok || got.AsString() != "order-service" {
		t.Fatalf("service.name = %v (present %v), want order-service", got.AsString(), ok)
	}
	if env, _ := res.Set().Value(attribute.Key("deployment.environment.name")); env.AsString() != "qa" {
		t.Fatalf("deployment.environment.name = %q, want qa", env.AsString())
	}
}
