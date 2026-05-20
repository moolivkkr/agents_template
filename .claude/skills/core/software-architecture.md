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

Architectural principles and patterns for building maintainable, extensible, production-grade systems. All code generation must follow these patterns.

## SOLID Principles

### S — Single Responsibility

One struct/class should have one reason to change. If a struct handles both business logic and persistence, it has two reasons to change.

```go
// BAD — UserService does validation, business logic, persistence, and notifications
type UserService struct {
    db *sql.DB
}

func (s *UserService) CreateUser(ctx context.Context, req CreateUserRequest) (*User, error) {
    // validates input (reason to change #1)
    // hashes password (reason to change #2)
    // inserts into DB (reason to change #3)
    // sends welcome email (reason to change #4)
}

// GOOD — each struct has one responsibility
type UserValidator struct{}
func (v *UserValidator) Validate(req CreateUserRequest) error { /* validation only */ }

type UserRepository struct{ db *sql.DB }
func (r *UserRepository) Save(ctx context.Context, user *User) error { /* persistence only */ }

type UserNotifier struct{ mailer Mailer }
func (n *UserNotifier) SendWelcome(ctx context.Context, user *User) error { /* notification only */ }

type UserService struct {
    validator *UserValidator
    repo      *UserRepository
    notifier  *UserNotifier
}
func (s *UserService) CreateUser(ctx context.Context, req CreateUserRequest) (*User, error) {
    // orchestrates the others — single responsibility: coordination
}
```

```typescript
// BAD — one class does everything
class OrderManager {
  async createOrder(req: CreateOrderReq): Promise<Order> { /* validate + save + notify + invoice */ }
}

// GOOD — separated concerns
class OrderValidator { validate(req: CreateOrderReq): ValidationResult { /* ... */ } }
class OrderRepository { async save(order: Order): Promise<Order> { /* ... */ } }
class InvoiceService { async generate(order: Order): Promise<Invoice> { /* ... */ } }

class OrderService {
  constructor(
    private validator: OrderValidator,
    private repo: OrderRepository,
    private invoicing: InvoiceService,
  ) {}
  async createOrder(req: CreateOrderReq): Promise<Order> { /* orchestration only */ }
}
```

### O — Open/Closed

Open for extension, closed for modification. Use interfaces to add behavior without changing existing code.

```go
// BAD — adding a new payment type requires modifying this function
func ProcessPayment(method string, amount decimal.Decimal) error {
    switch method {
    case "credit_card":
        // process credit card
    case "paypal":
        // process paypal
    case "crypto": // have to modify existing code to add this
        // process crypto
    }
}

// GOOD — new payment types implement the interface, no existing code changes
type PaymentProcessor interface {
    Process(ctx context.Context, amount decimal.Decimal) error
    SupportsMethod(method string) bool
}

type CreditCardProcessor struct{}
func (p *CreditCardProcessor) Process(ctx context.Context, amount decimal.Decimal) error { /* ... */ }
func (p *CreditCardProcessor) SupportsMethod(method string) bool { return method == "credit_card" }

type PayPalProcessor struct{}
func (p *PayPalProcessor) Process(ctx context.Context, amount decimal.Decimal) error { /* ... */ }
func (p *PayPalProcessor) SupportsMethod(method string) bool { return method == "paypal" }

// Adding crypto: just add a new struct implementing PaymentProcessor — zero changes to existing code
type CryptoProcessor struct{}
func (p *CryptoProcessor) Process(ctx context.Context, amount decimal.Decimal) error { /* ... */ }
func (p *CryptoProcessor) SupportsMethod(method string) bool { return method == "crypto" }
```

### L — Liskov Substitution

Subtypes must be substitutable for their base types without breaking correctness. If code works with an interface, any implementation of that interface must honor the contract.

```go
// BAD — ReadOnlyRepo violates the contract by panicking on Save
type Repository interface {
    FindByID(ctx context.Context, id string) (*Entity, error)
    Save(ctx context.Context, entity *Entity) error
}

type ReadOnlyRepo struct{}
func (r *ReadOnlyRepo) FindByID(ctx context.Context, id string) (*Entity, error) { /* works */ }
func (r *ReadOnlyRepo) Save(ctx context.Context, entity *Entity) error {
    panic("read-only repository cannot save") // violates LSP
}

// GOOD — separate interfaces so each implementation is honest
type Reader interface {
    FindByID(ctx context.Context, id string) (*Entity, error)
}

type Writer interface {
    Save(ctx context.Context, entity *Entity) error
}

type ReadWriter interface {
    Reader
    Writer
}

// ReadOnlyRepo implements Reader only — no contract violation
type ReadOnlyRepo struct{}
func (r *ReadOnlyRepo) FindByID(ctx context.Context, id string) (*Entity, error) { /* works */ }
```

```typescript
// BAD — square breaks rectangle's contract
class Rectangle {
  setWidth(w: number): void { this.width = w; }
  setHeight(h: number): void { this.height = h; }
  area(): number { return this.width * this.height; }
}
class Square extends Rectangle {
  setWidth(w: number): void { this.width = w; this.height = w; } // breaks contract
}

// GOOD — use composition or separate types
interface Shape {
  area(): number;
}
class Rectangle implements Shape { /* width + height */ }
class Square implements Shape { /* side only */ }
```

### I — Interface Segregation

Clients should not be forced to depend on methods they don't use. In Go, small interfaces (1-3 methods) are ideal.

```go
// BAD — fat interface forces implementors to stub unused methods
type UserStore interface {
    FindByID(ctx context.Context, id string) (*User, error)
    FindByEmail(ctx context.Context, email string) (*User, error)
    List(ctx context.Context, filter UserFilter) ([]*User, error)
    Save(ctx context.Context, user *User) error
    Delete(ctx context.Context, id string) error
    UpdatePassword(ctx context.Context, id string, hash string) error
    CountByTenant(ctx context.Context, tenantID string) (int, error)
}

// GOOD — small, focused interfaces composed as needed
type UserReader interface {
    FindByID(ctx context.Context, id string) (*User, error)
    FindByEmail(ctx context.Context, email string) (*User, error)
}

type UserWriter interface {
    Save(ctx context.Context, user *User) error
    Delete(ctx context.Context, id string) error
}

type UserLister interface {
    List(ctx context.Context, filter UserFilter) ([]*User, error)
    CountByTenant(ctx context.Context, tenantID string) (int, error)
}

// Services depend only on what they need
type AuthService struct {
    users UserReader // only needs lookup
}

type AdminService struct {
    users interface { // compose at the call site if needed
        UserReader
        UserWriter
        UserLister
    }
}
```

```typescript
// BAD
interface DataStore {
  get(id: string): Promise<Entity>;
  list(): Promise<Entity[]>;
  save(entity: Entity): Promise<void>;
  delete(id: string): Promise<void>;
  backup(): Promise<void>;
  migrate(): Promise<void>;
}

// GOOD
interface Readable<T> { get(id: string): Promise<T>; }
interface Listable<T> { list(filter?: Filter): Promise<T[]>; }
interface Writable<T> { save(entity: T): Promise<void>; }
interface Deletable   { delete(id: string): Promise<void>; }
```

### D — Dependency Inversion

High-level modules should not depend on low-level modules. Both should depend on abstractions. Inject dependencies via constructors.

```go
// BAD — service directly depends on concrete Postgres implementation
type UserService struct {
    db *pgxpool.Pool // concrete dependency
}

func (s *UserService) GetUser(ctx context.Context, id string) (*User, error) {
    row := s.db.QueryRow(ctx, "SELECT * FROM users WHERE id = $1", id)
    // directly coupled to Postgres
}

// GOOD — depend on abstraction, inject via constructor
type UserRepository interface {
    FindByID(ctx context.Context, id string) (*User, error)
    Save(ctx context.Context, user *User) error
}

type UserService struct {
    repo   UserRepository
    cache  Cache
    logger *slog.Logger
}

func NewUserService(repo UserRepository, cache Cache, logger *slog.Logger) *UserService {
    return &UserService{
        repo:   repo,
        cache:  cache,
        logger: logger,
    }
}
```

```typescript
// BAD — direct dependency
class UserService {
  private db = new PostgresClient(); // hardcoded
  async getUser(id: string): Promise<User> { return this.db.query(...); }
}

// GOOD — injected abstraction
interface UserRepository {
  findById(id: string): Promise<User | null>;
  save(user: User): Promise<User>;
}

class UserService {
  constructor(
    private readonly repo: UserRepository,
    private readonly cache: CacheService,
    private readonly logger: Logger,
  ) {}
}

// In composition root / main
const repo = new PostgresUserRepository(pool);
const cache = new RedisCache(redisClient);
const service = new UserService(repo, cache, logger);
```

## Mandatory Design Patterns

### 1. Repository Pattern — Data Access Abstraction

Encapsulate all data access behind an interface. Business logic never touches SQL, ORM, or storage API directly.

```go
type OrderRepository interface {
    FindByID(ctx context.Context, id string) (*Order, error)
    FindByTenant(ctx context.Context, tenantID string, filter OrderFilter) ([]*Order, error)
    Save(ctx context.Context, order *Order) error
    Delete(ctx context.Context, id string) error
}

type postgresOrderRepo struct {
    pool *pgxpool.Pool
}

func NewPostgresOrderRepo(pool *pgxpool.Pool) OrderRepository {
    return &postgresOrderRepo{pool: pool}
}

func (r *postgresOrderRepo) FindByID(ctx context.Context, id string) (*Order, error) {
    row := r.pool.QueryRow(ctx, `SELECT id, tenant_id, status, total FROM orders WHERE id = $1`, id)
    var o Order
    if err := row.Scan(&o.ID, &o.TenantID, &o.Status, &o.Total); err != nil {
        if errors.Is(err, pgx.ErrNoRows) {
            return nil, ErrOrderNotFound
        }
        return nil, fmt.Errorf("scanning order: %w", err)
    }
    return &o, nil
}
```

**When to use:** Always. Every data store interaction goes through a repository.

### 2. Service Pattern — Business Logic Orchestration

Services contain business rules and coordinate between repositories, caches, and external services. Services never handle HTTP concerns.

```go
type OrderService struct {
    orders    OrderRepository
    inventory InventoryService
    payments  PaymentService
    events    EventPublisher
    logger    *slog.Logger
}

func NewOrderService(orders OrderRepository, inventory InventoryService,
    payments PaymentService, events EventPublisher, logger *slog.Logger) *OrderService {
    return &OrderService{orders: orders, inventory: inventory,
        payments: payments, events: events, logger: logger}
}

func (s *OrderService) PlaceOrder(ctx context.Context, req PlaceOrderRequest) (*Order, error) {
    // Business logic lives here — not in handlers, not in repositories
    if err := s.inventory.Reserve(ctx, req.Items); err != nil {
        return nil, fmt.Errorf("reserving inventory: %w", err)
    }
    order := NewOrder(req)
    if err := s.orders.Save(ctx, order); err != nil {
        return nil, fmt.Errorf("saving order: %w", err)
    }
    s.events.Publish(ctx, OrderPlacedEvent{OrderID: order.ID})
    return order, nil
}
```

**When to use:** Always. Business logic lives in services, not handlers or repositories.

### 3. Strategy Pattern — Interchangeable Algorithms

Use when you have multiple algorithms for the same task and need to switch between them at runtime.

```go
type PricingStrategy interface {
    Calculate(ctx context.Context, order *Order) (decimal.Decimal, error)
}

type StandardPricing struct{}
func (p *StandardPricing) Calculate(ctx context.Context, order *Order) (decimal.Decimal, error) {
    // sum of item prices
}

type DiscountPricing struct{ discountPct decimal.Decimal }
func (p *DiscountPricing) Calculate(ctx context.Context, order *Order) (decimal.Decimal, error) {
    // apply percentage discount
}

type TieredPricing struct{ tiers []PriceTier }
func (p *TieredPricing) Calculate(ctx context.Context, order *Order) (decimal.Decimal, error) {
    // volume-based pricing
}

// Usage — strategy is injected or selected at runtime
type OrderService struct {
    pricing PricingStrategy
}
```

**When to use:** Multiple algorithms for the same operation. Price calculation, sorting strategies, notification routing.

### 4. Factory Pattern — Complex Object Creation

Use when object creation involves validation, defaults, or conditional logic that shouldn't live in the caller.

```go
func NewOrder(req PlaceOrderRequest) *Order {
    return &Order{
        ID:        uuid.New().String(),
        TenantID:  req.TenantID,
        Status:    OrderStatusPending,
        Items:     req.Items,
        Total:     calculateTotal(req.Items),
        CreatedAt: time.Now(),
        UpdatedAt: time.Now(),
    }
}
```

```typescript
class NotificationFactory {
  static create(channel: NotificationChannel, payload: NotificationPayload): Notification {
    switch (channel) {
      case 'email': return new EmailNotification(payload);
      case 'sms':   return new SMSNotification(payload);
      case 'push':  return new PushNotification(payload);
      default:      throw new Error(`unsupported channel: ${channel}`);
    }
  }
}
```

**When to use:** Complex initialization logic, conditional construction, enforcing invariants at creation time.

### 5. Observer Pattern — Event-Driven Decoupling

Decouple components through events. Publishers don't know about subscribers.

```go
type Event interface {
    EventType() string
    TenantID() string
}

type EventHandler func(ctx context.Context, event Event) error

type EventBus struct {
    mu       sync.RWMutex
    handlers map[string][]EventHandler
}

func (b *EventBus) Subscribe(eventType string, handler EventHandler) {
    b.mu.Lock()
    defer b.mu.Unlock()
    b.handlers[eventType] = append(b.handlers[eventType], handler)
}

func (b *EventBus) Publish(ctx context.Context, event Event) error {
    b.mu.RLock()
    handlers := b.handlers[event.EventType()]
    b.mu.RUnlock()

    for _, h := range handlers {
        if err := h(ctx, event); err != nil {
            slog.ErrorContext(ctx, "event handler failed",
                "event_type", event.EventType(),
                "error", err,
            )
        }
    }
    return nil
}
```

**When to use:** When one action triggers multiple side effects (notifications, audit logs, cache invalidation). When components should not know about each other.

### 6. Circuit Breaker — External Call Protection

Prevent cascading failures by stopping calls to failing dependencies. See `resiliency-patterns.md` for full implementation.

```go
type CircuitBreaker struct {
    maxFailures int
    timeout     time.Duration
    state       CircuitState  // Closed, Open, HalfOpen
    failures    int
    lastFailure time.Time
    mu          sync.RWMutex
}

func (cb *CircuitBreaker) Execute(fn func() error) error {
    if !cb.allowRequest() {
        return ErrCircuitOpen
    }
    err := fn()
    if err != nil {
        cb.recordFailure()
        return err
    }
    cb.recordSuccess()
    return nil
}
```

**When to use:** Every external HTTP call, database connection, cache connection, message queue interaction.

### 7. Decorator Pattern — Behavior Extension Without Modification

Wrap existing functionality with additional behavior (logging, metrics, caching) without changing the original.

```go
// Base interface
type UserRepository interface {
    FindByID(ctx context.Context, id string) (*User, error)
}

// Logging decorator
type loggingUserRepo struct {
    next   UserRepository
    logger *slog.Logger
}

func NewLoggingUserRepo(next UserRepository, logger *slog.Logger) UserRepository {
    return &loggingUserRepo{next: next, logger: logger}
}

func (r *loggingUserRepo) FindByID(ctx context.Context, id string) (*User, error) {
    r.logger.InfoContext(ctx, "finding user", "id", id)
    user, err := r.next.FindByID(ctx, id)
    if err != nil {
        r.logger.ErrorContext(ctx, "find user failed", "id", id, "error", err)
    }
    return user, err
}

// Caching decorator
type cachingUserRepo struct {
    next  UserRepository
    cache Cache
    ttl   time.Duration
}

func (r *cachingUserRepo) FindByID(ctx context.Context, id string) (*User, error) {
    if cached, ok := r.cache.Get(ctx, "user:"+id); ok {
        return cached.(*User), nil
    }
    user, err := r.next.FindByID(ctx, id)
    if err != nil {
        return nil, err
    }
    r.cache.Set(ctx, "user:"+id, user, r.ttl)
    return user, nil
}

// Composition — stack decorators
repo := NewLoggingUserRepo(
    NewCachingUserRepo(
        NewPostgresUserRepo(pool),
        redisCache, 5*time.Minute,
    ),
    logger,
)
```

**When to use:** Cross-cutting concerns (logging, caching, metrics, retry). When you want to add behavior to existing implementations without modifying them.

### 8. Builder Pattern — Complex Object Construction

Use when objects have many optional fields and construction needs validation.

```go
type QueryBuilder struct {
    table      string
    conditions []string
    args       []interface{}
    orderBy    string
    limit      int
    offset     int
}

func NewQuery(table string) *QueryBuilder {
    return &QueryBuilder{table: table, limit: 20}
}

func (q *QueryBuilder) Where(condition string, args ...interface{}) *QueryBuilder {
    q.conditions = append(q.conditions, condition)
    q.args = append(q.args, args...)
    return q
}

func (q *QueryBuilder) OrderBy(field string) *QueryBuilder {
    q.orderBy = field
    return q
}

func (q *QueryBuilder) Limit(n int) *QueryBuilder {
    q.limit = n
    return q
}

func (q *QueryBuilder) Build() (string, []interface{}) {
    sql := fmt.Sprintf("SELECT * FROM %s", q.table)
    if len(q.conditions) > 0 {
        sql += " WHERE " + strings.Join(q.conditions, " AND ")
    }
    if q.orderBy != "" {
        sql += " ORDER BY " + q.orderBy
    }
    sql += fmt.Sprintf(" LIMIT %d OFFSET %d", q.limit, q.offset)
    return sql, q.args
}

// Usage
query, args := NewQuery("orders").
    Where("tenant_id = $1", tenantID).
    Where("status = $2", "active").
    OrderBy("created_at DESC").
    Limit(50).
    Build()
```

**When to use:** Objects with many optional fields. Multi-step construction that needs validation. Fluent configuration APIs.

## Interface-Based Development

Follow this sequence for every new capability:

1. **Define the interface** — what operations are needed?
2. **Implement** — write the concrete implementation
3. **Inject** — wire via constructor in the composition root

```go
// Step 1: Define
type NotificationSender interface {
    Send(ctx context.Context, recipient string, msg Message) error
}

// Step 2: Implement
type EmailSender struct { client *smtp.Client }
func (s *EmailSender) Send(ctx context.Context, recipient string, msg Message) error { /* ... */ }

// Step 3: Inject
func NewNotificationService(sender NotificationSender) *NotificationService {
    return &NotificationService{sender: sender}
}
```

## DI Constructor Convention

All services follow the same constructor pattern: accept interfaces, return concrete type.

```go
func NewService(repo Repository, cache Cache, logger *slog.Logger) *Service {
    return &Service{
        repo:   repo,
        cache:  cache,
        logger: logger,
    }
}
```

- Constructor name: `New<TypeName>`
- Parameters: interfaces for dependencies, concrete types for infrastructure (`*slog.Logger`, config structs)
- Return: pointer to concrete struct (not the interface)
- No global state, no init() functions for DI

## Layer Boundaries

```
┌─────────────────────────────┐
│  Handler / Controller       │  HTTP concerns: parse request, validate, call service, format response
│  (transport layer)          │  Errors: maps service errors → HTTP status codes
├─────────────────────────────┤
│  Service                    │  Business logic: orchestration, rules, validation
│  (business layer)           │  Errors: domain-specific (ErrNotFound, ErrConflict, ErrForbidden)
├─────────────────────────────┤
│  Repository                 │  Data access: queries, persistence, caching
│  (data layer)               │  Errors: wraps DB errors into domain errors
└─────────────────────────────┘
```

**Rules:**
- Handlers call Services. Services call Repositories. Never skip layers.
- Each layer has its own error types — don't leak SQL errors to handlers.
- Handlers never import `database/sql` or ORM packages.
- Repositories never import `net/http`.
- Services don't know about HTTP status codes or request/response shapes.

```go
// Handler → Service → Repository — each layer transforms errors
func (h *OrderHandler) GetOrder(w http.ResponseWriter, r *http.Request) {
    order, err := h.service.GetOrder(r.Context(), chi.URLParam(r, "id"))
    if err != nil {
        switch {
        case errors.Is(err, ErrOrderNotFound):
            respondError(w, http.StatusNotFound, err)
        case errors.Is(err, ErrForbidden):
            respondError(w, http.StatusForbidden, err)
        default:
            respondError(w, http.StatusInternalServerError, err)
        }
        return
    }
    respondJSON(w, http.StatusOK, order)
}
```

## Critical Rules

- Every dependency is injected via constructor — no global variables, no singletons
- Interfaces are defined by the consumer, not the implementor (Go convention)
- Small interfaces (1-3 methods) are preferred over large ones
- Each layer has its own error types — never leak implementation details upward
- Handlers handle HTTP, Services handle business logic, Repositories handle data — no exceptions
- New behavior is added by implementing interfaces, not modifying existing code
- Use patterns when they solve a real problem, not because they exist
