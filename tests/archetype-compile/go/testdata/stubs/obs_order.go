// HARNESS STUB (tests/archetype-compile/go) — not archetype code.
// observability-go.md's `order` examples (1.2, 1.7) instrument the project's order handler, service
// and repository without defining the types, constructors or JSON helpers. These are the smallest
// versions that match how the samples use them.

package order

import (
	"context"
	"database/sql"
	"encoding/json"
	"net/http"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/shopspring/decimal"
)

type Item struct {
	SKU      string `json:"sku"`
	Quantity int    `json:"quantity"`
}

type Order struct {
	ID        string          `json:"id"`
	TenantID  string          `json:"tenant_id"`
	UserID    string          `json:"user_id"`
	Items     []Item          `json:"items"`
	Total     decimal.Decimal `json:"total"`
	Currency  string          `json:"currency"`
	Status    string          `json:"status"`
	CreatedAt time.Time       `json:"created_at"`
}

type CreateOrderRequest struct {
	Items    []Item `json:"items"`
	Currency string `json:"currency"`
}

func (r CreateOrderRequest) Validate() error { return nil }

func parseCreateRequest(r *http.Request) CreateOrderRequest {
	var req CreateOrderRequest
	_ = json.NewDecoder(r.Body).Decode(&req)
	return req
}

func newOrder(req CreateOrderRequest) *Order {
	return &Order{Items: req.Items, Currency: req.Currency, Status: "open", CreatedAt: time.Now().UTC()}
}

func respondError(w http.ResponseWriter, err error) { w.WriteHeader(http.StatusInternalServerError) }

func respondJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

// Record is what FindByID returns in the 1.7 error-recording example.
type Record struct{ DeprecatedAt time.Time }

func (r *Record) IsDeprecated() bool { return !r.DeprecatedAt.IsZero() }

type store interface {
	Save(ctx context.Context, order *Order) error
	FindByID(ctx context.Context, id string) (*Record, error)
}

type PostgresOrderRepo struct{ pool *pgxpool.Pool }

func (r *PostgresOrderRepo) FindByID(ctx context.Context, id string) (*Record, error) {
	return &Record{}, nil
}

type Service struct{ repo store }

type Handler struct{ service *Service }

func (h *Handler) GetOrder(w http.ResponseWriter, r *http.Request) {}

func NewPostgresOrderRepo(db *sql.DB) *PostgresOrderRepo { return &PostgresOrderRepo{} }
func NewOrderService(repo *PostgresOrderRepo) *Service   { return &Service{repo: repo} }
func NewOrderHandler(svc *Service) *Handler              { return &Handler{service: svc} }
