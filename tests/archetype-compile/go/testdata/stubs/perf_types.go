// HARNESS STUB (tests/archetype-compile/go) — not archetype code.
// performance-go.md's illustrative fragments (2.2–2.4, 5.1, 6.1, 6.5) use the project's order/item
// types, repositories and a per-item function without defining them. Order itself is the doc's
// (2.3); these are the rest, shaped by how the fragments use them.

package perf

import (
	"context"
	"database/sql"

	"github.com/jackc/pgx/v5/pgxpool"
)

type Item struct {
	ID        string
	ProductID string
	Quantity  int
	Price     int64 // minor units
}

type Result struct{ ItemID string }

func process(item Item) Result { return Result{ItemID: item.ID} }

type OrderItem struct {
	SKU        string
	PriceCents int64
}

func (o *Order) recalculateTotal() {}

type PostgresOrderRepo struct {
	db               *sql.DB
	pool             *pgxpool.Pool
	stmtGetByID      *sql.Stmt
	stmtListByTenant *sql.Stmt
}

type PostgresItemRepo struct{ pool *pgxpool.Pool }

type OrderWithItems struct {
	Order Order
	Items []Item
}

type Service struct {
	orderRepo interface {
		ListByTenant(ctx context.Context, tenantID string) ([]Order, error)
	}
	itemRepo interface {
		ListByOrderID(ctx context.Context, orderID string) ([]Item, error)
	}
}
