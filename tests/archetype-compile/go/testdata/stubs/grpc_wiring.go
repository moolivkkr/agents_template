// HARNESS STUB (tests/archetype-compile/go) — not archetype code.
// The gRPC Server Startup sample says jwtValidator and widgetSvc "come from your wiring"; these
// declarations stand in for that wiring so the main package type-checks.

package main

import (
	"yourapp/internal/interceptor"
	"yourapp/internal/widget"
)

var (
	jwtValidator interceptor.JWTValidator
	widgetSvc    widget.WidgetService
)
