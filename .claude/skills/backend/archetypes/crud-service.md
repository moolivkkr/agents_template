---
skill: crud-service
description: Go service layer archetype — CRUD operations with cache-aside, audit logging, metrics, tenant isolation, transaction support, and input validation
version: "1.0"
tags:
  - go
  - service
  - crud
  - archetype
  - backend
---

# CRUD Service Archetype

Complete, production-ready Go service layer template. Every generated service MUST follow this pattern.

## Domain Types

```go
package domain

import (
    "time"

    "github.com/google/uuid"
)

// Entity is the base for all domain objects.
type Entity struct {
    ID        uuid.UUID  `json:"id"`
    TenantID  uuid.UUID  `json:"tenant_id"`
    CreatedAt time.Time  `json:"created_at"`
    UpdatedAt time.Time  `json:"updated_at"`
    DeletedAt *time.Time `json:"deleted_at,omitempty"`
    CreatedBy uuid.UUID  `json:"created_by"`
    UpdatedBy uuid.UUID  `json:"updated_by"`
    Version   int        `json:"version"`
}

// ListFilters defines common filter parameters for list operations.
type ListFilters struct {
    Cursor   string            `json:"cursor,omitempty"`
    PageSize int               `json:"page_size"`
    SortBy   string            `json:"sort_by"`
    SortDir  string            `json:"sort_dir"`
    Fields   map[string]string `json:"fields,omitempty"` // dynamic field filters
}

// ListResult wraps paginated results.
type ListResult[T any] struct {
    Items   []T    `json:"items"`
    Cursor  string `json:"cursor,omitempty"`
    HasMore bool   `json:"has_more"`
    Total   int    `json:"total"`
}

// AuditEntry records a mutation for compliance.
type AuditEntry struct {
    Action    string    `json:"action"`
    EntityID  uuid.UUID `json:"entity_id"`
    TenantID  uuid.UUID `json:"tenant_id"`
    ActorID   uuid.UUID `json:"actor_id"`
    Timestamp time.Time `json:"timestamp"`
    Changes   any       `json:"changes,omitempty"`
}
```

## Interface Definition

```go
package widget

import (
    "context"

    "github.com/google/uuid"
    "yourapp/internal/domain"
)

// Service defines the business operations for widgets.
// Rule: Keep interfaces small (3-7 methods). Split if > 7.
type Service interface {
    Create(ctx context.Context, input CreateInput) (*Widget, error)
    Get(ctx context.Context, id uuid.UUID) (*Widget, error)
    Update(ctx context.Context, id uuid.UUID, input UpdateInput) (*Widget, error)
    Delete(ctx context.Context, id uuid.UUID) error
    List(ctx context.Context, filters domain.ListFilters) (*domain.ListResult[Widget], error)
}

// Repository defines the data access contract. Owned by the consumer (service).
type Repository interface {
    Create(ctx context.Context, w *Widget) error
    GetByID(ctx context.Context, tenantID, id uuid.UUID) (*Widget, error)
    Update(ctx context.Context, w *Widget) error
    SoftDelete(ctx context.Context, tenantID, id uuid.UUID) error
    List(ctx context.Context, tenantID uuid.UUID, filters domain.ListFilters) (*domain.ListResult[Widget], error)
}

// Cache abstracts the caching layer.
type Cache interface {
    Get(ctx context.Context, key string) ([]byte, error)
    Set(ctx context.Context, key string, value []byte, ttl time.Duration) error
    Delete(ctx context.Context, key string) error
}
```

## Constructor with Dependency Injection

```go
package widget

import (
    "log/slog"
    "time"

    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/metric"
    "go.opentelemetry.io/otel/trace"
)

// Metrics groups all observable counters and histograms for the service.
type Metrics struct {
    OpCount    metric.Int64Counter
    OpLatency  metric.Float64Histogram
    ErrCount   metric.Int64Counter
    CacheHits  metric.Int64Counter
    CacheMiss  metric.Int64Counter
}

type service struct {
    repo    Repository
    cache   Cache
    logger  *slog.Logger
    metrics Metrics
    tracer  trace.Tracer

    cacheTTL time.Duration
}

// NewService creates a widget service with all dependencies injected.
// Rule: Every dependency explicit in constructor. No global state.
func NewService(
    repo Repository,
    cache Cache,
    logger *slog.Logger,
    metrics Metrics,
) *service {
    return &service{
        repo:     repo,
        cache:    cache,
        logger:   logger.With("service", "widget"),
        metrics:  metrics,
        tracer:   otel.Tracer("widget-service"),
        cacheTTL: 5 * time.Minute,
    }
}
```

## Create Implementation

```go
func (s *service) Create(ctx context.Context, input CreateInput) (*Widget, error) {
    ctx, span := s.tracer.Start(ctx, "widget.create")
    defer span.End()
    start := time.Now()
    defer func() {
        s.metrics.OpLatency.Record(ctx, time.Since(start).Seconds(),
            metric.WithAttributes(attribute.String("op", "create")))
    }()

    // 1. Validate input
    if err := input.Validate(); err != nil {
        return nil, NewValidationError("create", err)
    }

    // 2. Extract tenant context — every operation is tenant-scoped
    tenantID, err := TenantIDFromContext(ctx)
    if err != nil {
        return nil, NewUnauthorizedError("missing tenant context")
    }
    userID, _ := UserIDFromContext(ctx)

    // 3. Build domain object
    now := time.Now().UTC()
    w := &Widget{
        Entity: domain.Entity{
            ID:        uuid.New(),
            TenantID:  tenantID,
            CreatedAt: now,
            UpdatedAt: now,
            CreatedBy: userID,
            UpdatedBy: userID,
            Version:   1,
        },
        Name:        input.Name,
        Description: input.Description,
        Status:      StatusActive,
    }

    // 4. Persist
    if err := s.repo.Create(ctx, w); err != nil {
        s.metrics.ErrCount.Add(ctx, 1, metric.WithAttributes(attribute.String("op", "create")))
        return nil, fmt.Errorf("widget create: %w", err)
    }

    // 5. Audit log
    s.auditLog(ctx, "widget.created", w.ID, tenantID, userID, w)

    s.metrics.OpCount.Add(ctx, 1, metric.WithAttributes(attribute.String("op", "create")))
    s.logger.InfoContext(ctx, "widget created",
        "widget_id", w.ID,
        "tenant_id", tenantID,
    )
    return w, nil
}
```

## Get with Cache-Aside Pattern

```go
func (s *service) Get(ctx context.Context, id uuid.UUID) (*Widget, error) {
    ctx, span := s.tracer.Start(ctx, "widget.get")
    defer span.End()
    start := time.Now()
    defer func() {
        s.metrics.OpLatency.Record(ctx, time.Since(start).Seconds(),
            metric.WithAttributes(attribute.String("op", "get")))
    }()

    tenantID, err := TenantIDFromContext(ctx)
    if err != nil {
        return nil, NewUnauthorizedError("missing tenant context")
    }

    // 1. Check cache
    cacheKey := fmt.Sprintf("widget:%s:%s", tenantID, id)
    if data, err := s.cache.Get(ctx, cacheKey); err == nil {
        var w Widget
        if err := json.Unmarshal(data, &w); err == nil {
            s.metrics.CacheHits.Add(ctx, 1)
            return &w, nil
        }
    }
    s.metrics.CacheMiss.Add(ctx, 1)

    // 2. Query DB
    w, err := s.repo.GetByID(ctx, tenantID, id)
    if err != nil {
        return nil, fmt.Errorf("widget get: %w", err)
    }

    // 3. Populate cache
    if data, err := json.Marshal(w); err == nil {
        _ = s.cache.Set(ctx, cacheKey, data, s.cacheTTL)
    }

    return w, nil
}
```

## Update with Cache Invalidation and Optimistic Locking

```go
func (s *service) Update(ctx context.Context, id uuid.UUID, input UpdateInput) (*Widget, error) {
    ctx, span := s.tracer.Start(ctx, "widget.update")
    defer span.End()
    start := time.Now()
    defer func() {
        s.metrics.OpLatency.Record(ctx, time.Since(start).Seconds(),
            metric.WithAttributes(attribute.String("op", "update")))
    }()

    if err := input.Validate(); err != nil {
        return nil, NewValidationError("update", err)
    }

    tenantID, err := TenantIDFromContext(ctx)
    if err != nil {
        return nil, NewUnauthorizedError("missing tenant context")
    }
    userID, _ := UserIDFromContext(ctx)

    // 1. Fetch current (ensures tenant-scoping)
    existing, err := s.repo.GetByID(ctx, tenantID, id)
    if err != nil {
        return nil, fmt.Errorf("widget update fetch: %w", err)
    }

    // 2. Optimistic lock check
    if input.Version != existing.Version {
        return nil, NewConflictError("widget", "version mismatch — reload and retry")
    }

    // 3. Apply changes
    existing.Name = input.Name
    existing.Description = input.Description
    existing.UpdatedAt = time.Now().UTC()
    existing.UpdatedBy = userID
    existing.Version++

    // 4. Persist
    if err := s.repo.Update(ctx, existing); err != nil {
        s.metrics.ErrCount.Add(ctx, 1, metric.WithAttributes(attribute.String("op", "update")))
        return nil, fmt.Errorf("widget update: %w", err)
    }

    // 5. Invalidate cache
    cacheKey := fmt.Sprintf("widget:%s:%s", tenantID, id)
    _ = s.cache.Delete(ctx, cacheKey)

    // 6. Audit log
    s.auditLog(ctx, "widget.updated", existing.ID, tenantID, userID, input)

    s.metrics.OpCount.Add(ctx, 1, metric.WithAttributes(attribute.String("op", "update")))
    return existing, nil
}
```

## Delete with Cache Invalidation

```go
func (s *service) Delete(ctx context.Context, id uuid.UUID) error {
    ctx, span := s.tracer.Start(ctx, "widget.delete")
    defer span.End()

    tenantID, err := TenantIDFromContext(ctx)
    if err != nil {
        return NewUnauthorizedError("missing tenant context")
    }
    userID, _ := UserIDFromContext(ctx)

    // 1. Soft delete (sets deleted_at, does not remove row)
    if err := s.repo.SoftDelete(ctx, tenantID, id); err != nil {
        s.metrics.ErrCount.Add(ctx, 1, metric.WithAttributes(attribute.String("op", "delete")))
        return fmt.Errorf("widget delete: %w", err)
    }

    // 2. Invalidate cache
    cacheKey := fmt.Sprintf("widget:%s:%s", tenantID, id)
    _ = s.cache.Delete(ctx, cacheKey)

    // 3. Audit log
    s.auditLog(ctx, "widget.deleted", id, tenantID, userID, nil)

    s.metrics.OpCount.Add(ctx, 1, metric.WithAttributes(attribute.String("op", "delete")))
    s.logger.InfoContext(ctx, "widget deleted", "widget_id", id, "tenant_id", tenantID)
    return nil
}
```

## List with Filters

```go
func (s *service) List(ctx context.Context, filters domain.ListFilters) (*domain.ListResult[Widget], error) {
    ctx, span := s.tracer.Start(ctx, "widget.list")
    defer span.End()

    tenantID, err := TenantIDFromContext(ctx)
    if err != nil {
        return nil, NewUnauthorizedError("missing tenant context")
    }

    // Enforce pagination defaults and maximums
    if filters.PageSize <= 0 {
        filters.PageSize = 20
    }
    if filters.PageSize > 100 {
        filters.PageSize = 100
    }
    if filters.SortBy == "" {
        filters.SortBy = "created_at"
    }
    if filters.SortDir == "" {
        filters.SortDir = "desc"
    }

    result, err := s.repo.List(ctx, tenantID, filters)
    if err != nil {
        return nil, fmt.Errorf("widget list: %w", err)
    }

    s.metrics.OpCount.Add(ctx, 1, metric.WithAttributes(attribute.String("op", "list")))
    return result, nil
}
```

## Transaction Support for Multi-Step Operations

```go
// TxManager abstracts database transactions for service-layer orchestration.
type TxManager interface {
    WithTx(ctx context.Context, fn func(ctx context.Context) error) error
}

func (s *service) CreateWithRelations(ctx context.Context, input CreateWithRelationsInput) (*Widget, error) {
    ctx, span := s.tracer.Start(ctx, "widget.create_with_relations")
    defer span.End()

    if err := input.Validate(); err != nil {
        return nil, NewValidationError("create_with_relations", err)
    }

    var created *Widget

    err := s.txManager.WithTx(ctx, func(txCtx context.Context) error {
        // Step 1: Create parent widget
        w, err := s.repo.Create(txCtx, input.ToWidget())
        if err != nil {
            return fmt.Errorf("create widget: %w", err)
        }
        created = w

        // Step 2: Create child components (all within same transaction)
        for _, comp := range input.Components {
            comp.WidgetID = w.ID
            if err := s.componentRepo.Create(txCtx, &comp); err != nil {
                return fmt.Errorf("create component: %w", err)
            }
        }
        return nil
    })
    if err != nil {
        return nil, fmt.Errorf("widget create_with_relations: %w", err)
    }

    return created, nil
}
```

## Audit Logging Helper

```go
func (s *service) auditLog(ctx context.Context, action string, entityID, tenantID, actorID uuid.UUID, changes any) {
    entry := domain.AuditEntry{
        Action:    action,
        EntityID:  entityID,
        TenantID:  tenantID,
        ActorID:   actorID,
        Timestamp: time.Now().UTC(),
        Changes:   changes,
    }
    // Fire-and-forget to audit logger — never block the business operation.
    // In production this publishes to an event bus or writes to an append-only table.
    if err := s.auditWriter.Write(ctx, entry); err != nil {
        s.logger.ErrorContext(ctx, "audit log failed",
            "action", action,
            "entity_id", entityID,
            "error", err,
        )
    }
}
```

## Input Validation Pattern

```go
type CreateInput struct {
    Name        string `json:"name" validate:"required,min=1,max=255"`
    Description string `json:"description" validate:"max=2000"`
}

func (i CreateInput) Validate() error {
    if strings.TrimSpace(i.Name) == "" {
        return NewValidationError("name", errors.New("name is required"))
    }
    if len(i.Name) > 255 {
        return NewValidationError("name", errors.New("name must be 255 characters or fewer"))
    }
    if len(i.Description) > 2000 {
        return NewValidationError("description", errors.New("description must be 2000 characters or fewer"))
    }
    return nil
}
```

## Critical Rules

- Every operation MUST extract `tenant_id` from context — no cross-tenant data leaks
- Every mutation MUST produce an audit log entry
- Every public method MUST start an OpenTelemetry span and record latency
- Cache invalidation MUST happen on every write (Update, Delete)
- Cache misses MUST populate the cache before returning
- Optimistic locking via `version` column — reject stale writes with `ConflictError`
- Input validation MUST happen before any side effects (DB, cache, external calls)
- Errors MUST be wrapped with context at every boundary: `fmt.Errorf("widget create: %w", err)`
- Max 40 lines of logic per function — extract helpers for complex steps
- Accept interfaces, return structs — constructor takes interfaces, returns concrete type
- Never return unbounded lists — always enforce PageSize max (100)
