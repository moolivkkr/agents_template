// HARNESS STUB (tests/archetype-compile/go) — not archetype code.
// Project-specific inputs the service/handler archetypes reference but leave to the project:
// UpdateInput (crud-service-go.md shows only CreateInput) and the multi-step-write types of the
// "Transaction Support" example. Validation mirrors CreateInput.Validate.

package widget

import (
	"context"
	"strings"
	"time"

	"github.com/google/uuid"

	"yourapp/internal/apperr"
	"yourapp/internal/domain"
)

type UpdateInput struct {
	Name        string `json:"name"`
	Description string `json:"description"`
	Version     int    `json:"version"`
}

func (i UpdateInput) Validate() error {
	if strings.TrimSpace(i.Name) == "" {
		return apperr.NewValidationError("name", "required", "Name is required.")
	}
	if i.Version < 1 {
		return apperr.NewValidationError("version", "required", "Version is required.")
	}
	return nil
}

func (i *UpdateInput) Sanitize() {
	i.Name = strings.TrimSpace(i.Name)
	i.Description = strings.TrimSpace(i.Description)
}

type Component struct {
	ID       uuid.UUID
	WidgetID uuid.UUID
	Name     string
}

type ComponentRepository interface {
	Create(ctx context.Context, c *Component) error
}

type CreateWithRelationsInput struct {
	CreateInput
	Components []Component
}

func (i CreateWithRelationsInput) ToWidget(tenantID uuid.UUID) *Widget {
	now := time.Now().UTC()
	return &Widget{
		Entity: domain.Entity{ID: uuid.New(), TenantID: tenantID, CreatedAt: now, UpdatedAt: now, Version: 1},
		Name:   i.Name, Description: i.Description, Status: StatusActive,
	}
}
