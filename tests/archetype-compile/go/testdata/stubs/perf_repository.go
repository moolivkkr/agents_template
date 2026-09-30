// HARNESS STUB (tests/archetype-compile/go) — not archetype code.
// performance-go.md 6.2 bulk-inserts the project's orders through its pgx repository.

package repository

import (
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/shopspring/decimal"
)

type Order struct {
	ID        string
	TenantID  string
	UserID    string
	Total     decimal.Decimal
	Currency  string
	Status    string
	CreatedAt time.Time
}

type PgxOrderRepo struct{ pool *pgxpool.Pool }
