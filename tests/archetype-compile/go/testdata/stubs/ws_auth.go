// HARNESS STUB (tests/archetype-compile/go) — not archetype code.
// websocket-pattern-go.md calls the project's ticket store (redeemTicket) and ID generator
// (generateConnID) without defining them. The stub store knows one ticket, for the smoke test.

package ws

import (
	"context"
	"errors"

	"github.com/google/uuid"
)

type ticketClaims struct {
	UserID   string
	TenantID string
	Roles    []string
}

const testTicket = "valid-ticket"

// redeemTicket atomically gets and deletes a single-use ticket (e.g. Redis GETDEL).
func redeemTicket(ctx context.Context, ticket string) (*ticketClaims, error) {
	if ticket != testTicket {
		return nil, errors.New("unknown ticket")
	}
	return &ticketClaims{UserID: "user-1", TenantID: "tenant-1"}, nil
}

func generateConnID() string { return uuid.NewString() }
