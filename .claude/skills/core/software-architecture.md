---
skill: software-architecture
description: SOLID principles, design patterns, interface-based development, dependency injection, layer boundaries — with Go and TypeScript examples
version: "1.0"
tags:
  - architecture
  - solid
  - patterns
  - dependency-injection
  - clean-architecture
---

# Software Architecture

Architectural principles and patterns for maintainable, extensible, production-grade systems.

## SOLID Principles

### S — Single Responsibility

One struct/class = one reason to change.

```go
// BAD — UserService does validation + persistence + notification
// GOOD — separate UserValidator, UserRepository, UserNotifier; UserService orchestrates
type UserService struct {
    validator *UserValidator
    repo      *UserRepository
    notifier  *UserNotifier
}
```

### O — Open/Closed

Open for extension, closed for modification. Add behavior via new interface implementations.

```go
// BAD — switch/case that grows with every new type
// GOOD — interface + implementations
type PaymentProcessor interface {
    Process(ctx context.Context, amount decimal.Decimal) error
    SupportsMethod(method string) bool
}
// New payment types: add new struct implementing PaymentProcessor — zero changes to existing code
```

### L — Liskov Substitution

Any implementation of an interface must honor its full contract.

```go
// BAD — ReadOnlyRepo implements Save() with panic
// GOOD — separate Reader and Writer interfaces
type Reader interface { FindByID(ctx context.Context, id string) (*Entity, error) }
type Writer interface { Save(ctx context.Context, entity *Entity) error }
type ReadWriter interface { Reader; Writer }
```

### I — Interface Segregation

Small interfaces (1-3 methods). Clients depend only on what they need.

```go
// BAD — 7-method UserStore forces all implementors to stub unused methods
// GOOD — UserReader (2 methods), UserWriter (2 methods), UserLister (2 methods)
type AuthService struct { users UserReader }  // only needs lookup
```

### D — Dependency Inversion

Depend on abstractions. Inject via constructors.

```go
// BAD — service directly depends on *pgxpool.Pool
// GOOD — depend on UserRepository interface, inject in constructor
func NewUserService(repo UserRepository, cache Cache, logger *slog.Logger) *UserService {
    return &UserService{repo: repo, cache: cache, logger: logger}
}
```

## Mandatory Design Patterns

### 1. Repository — Data Access Abstraction

Encapsulate all data access behind an interface. Business logic never touches SQL/ORM directly.

```go
type OrderRepository interface {
    FindByID(ctx context.Context, id string) (*Order, error)
    FindByTenant(ctx context.Context, tenantID string, filter OrderFilter) ([]*Order, error)
    Save(ctx context.Context, order *Order) error
    Delete(ctx context.Context, id string) error
}
```

### 2. Service — Business Logic Orchestration

Services contain business rules, coordinate repos/caches/external services. Never handle HTTP concerns.

```go
func (s *OrderService) PlaceOrder(ctx context.Context, req PlaceOrderRequest) (*Order, error) {
    if err := s.inventory.Reserve(ctx, req.Items); err != nil { return nil, fmt.Errorf("reserving: %w", err) }
    order := NewOrder(req)
    if err := s.orders.Save(ctx, order); err != nil { return nil, fmt.Errorf("saving: %w", err) }
    s.events.Publish(ctx, OrderPlacedEvent{OrderID: order.ID})
    return order, nil
}
```

### 3. Strategy — Interchangeable Algorithms

Multiple algorithms for same task, switchable at runtime (pricing, sorting, routing).

### 4. Factory — Complex Object Creation

When creation involves validation, defaults, or conditional logic.

### 5. Observer — Event-Driven Decoupling

One action triggers multiple side effects. Publishers don't know subscribers.

```go
type EventBus struct {
    handlers map[string][]EventHandler
}
func (b *EventBus) Subscribe(eventType string, handler EventHandler)
func (b *EventBus) Publish(ctx context.Context, event Event) error
```

### 6. Circuit Breaker — External Call Protection

See `resiliency-patterns.md` for full implementation.

### 7. Decorator — Behavior Extension Without Modification

Stack cross-cutting concerns (logging, caching, metrics) without modifying originals.

```go
// Stack: LoggingRepo wraps CachingRepo wraps PostgresRepo
repo := NewLoggingUserRepo(NewCachingUserRepo(NewPostgresUserRepo(pool), cache, 5*time.Minute), logger)
```

### 8. Builder — Complex Object Construction

Objects with many optional fields; multi-step construction with validation.

```go
query, args := NewQuery("orders").
    Where("tenant_id = $1", tenantID).
    Where("status = $2", "active").
    OrderBy("created_at DESC").
    Limit(50).
    Build()
```

## Interface-Based Development

1. **Define** the interface → 2. **Implement** concretely → 3. **Inject** via constructor in composition root

## DI Constructor Convention

```go
func NewService(repo Repository, cache Cache, logger *slog.Logger) *Service {
    return &Service{repo: repo, cache: cache, logger: logger}
}
```
- Name: `New<TypeName>` | Params: interfaces for deps, concrete for infra | Return: pointer to struct
- No global state, no init() for DI

## Layer Boundaries

```
Handler/Controller  — HTTP: parse, validate, call service, format response
Service             — Business logic: orchestration, rules, domain errors
Repository          — Data access: queries, persistence, wraps DB errors
```

**Rules:**
- Handlers → Services → Repositories. Never skip layers.
- Each layer has own error types — no SQL errors leaking to handlers
- Handlers never import `database/sql`; Repositories never import `net/http`
- Services don't know HTTP status codes

## Critical Rules

- Every dependency injected via constructor — no globals, no singletons
- Interfaces defined by consumer, not implementor
- Small interfaces (1-3 methods) preferred
- Each layer has own error types — never leak implementation details upward
- Handlers=HTTP, Services=logic, Repos=data — no exceptions
- New behavior via interface implementation, not modifying existing code
- Use patterns when they solve a real problem, not because they exist
