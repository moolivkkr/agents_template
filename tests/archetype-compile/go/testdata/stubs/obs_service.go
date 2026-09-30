// HARNESS STUB (tests/archetype-compile/go) — not archetype code.
// observability-go.md 2.5 records business metrics from the project's OrderService and Order.

package service

import "github.com/shopspring/decimal"

type Item struct{}

type Order struct {
	PaymentMethod string
	Currency      string
	Total         decimal.Decimal
	Items         []Item
}

type OrderService struct{}
