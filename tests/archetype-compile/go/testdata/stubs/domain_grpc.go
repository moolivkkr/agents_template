// HARNESS STUB (tests/archetype-compile/go) — not archetype code.
// grpc-pattern-go.md uses the project's domain types (domain.Widget, domain.CreateWidgetInput,
// domain.WidgetEvent) without defining them. These match how its server and toProto use them.

package domain

import (
	"time"

	"github.com/google/uuid"
)

type Widget struct {
	ID          uuid.UUID
	TenantID    uuid.UUID
	Name        string
	Description string
	Status      string
	CreatedAt   time.Time
	UpdatedAt   time.Time
	CreatedBy   uuid.UUID
	Version     int
}

type CreateWidgetInput struct {
	Name        string
	Description string
}

type WidgetEvent struct {
	Type   string // "created", "updated", "deleted"
	Widget *Widget
	At     time.Time
}
