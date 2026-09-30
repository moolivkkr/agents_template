// HARNESS STUB (tests/archetype-compile/go) — not archetype code.
// The CRUD archetypes use the project's entity, `Widget`, without defining it: every project writes
// its own. This is the smallest entity that matches how the samples use it.

package widget

import "yourapp/internal/domain"

type Widget struct {
	domain.Entity
	Name        string `json:"name"`
	Description string `json:"description"`
	Status      string `json:"status"`
}

const StatusActive = "active"
