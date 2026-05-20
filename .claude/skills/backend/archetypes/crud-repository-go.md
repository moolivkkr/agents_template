> **This file contains Go-specific patterns for: CRUD Repository Archetype.** The language-neutral version at [crud-repository.md](crud-repository.md) contains the same Go patterns and serves as the canonical reference. This file exists for consistent `{{LANG}}` placeholder resolution by `agent_factory`.

---
skill: crud-repository
description: Go pgx repository archetype — parameterized queries, cursor pagination, soft delete, multi-level caching, tenant isolation, batch operations, optimistic locking
version: "1.0"
tags:
  - go
  - repository
  - pgx
  - postgres
  - archetype
  - backend
---

# CRUD Repository Archetype

Complete pgx-based PostgreSQL repository template. Every generated repository MUST follow this pattern.

## Interface Definition

```go
package widget

import (
    "context"

    "github.com/google/uuid"
    "yourapp/internal/domain"
)

// Repository defines data access for widgets. Owned by the consumer (service package).
type Repository interface {
    Create(ctx context.Context, w *Widget) error
    GetByID(ctx context.Context, tenantID, id uuid.UUID) (*Widget, error)
    Update(ctx context.Context, w *Widget) error
    SoftDelete(ctx context.Context, tenantID, id uuid.UUID) error
    List(ctx context.Context, tenantID uuid.UUID, filters domain.ListFilters) (*domain.ListResult[Widget], error)
    BatchCreate(ctx context.Context, widgets []*Widget) error
    BatchUpdate(ctx context.Context, widgets []*Widget) error
}
```

## Constructor and Pool Configuration

```go
package postgres

import (
    "context"
    "encoding/base64"
    "encoding/json"
    "errors"
    "fmt"
    "log/slog"
    "strings"
    "sync"
    "time"

    "github.com/google/uuid"
    "github.com/jackc/pgx/v5"
    "github.com/jackc/pgx/v5/pgconn"
    "github.com/jackc/pgx/v5/pgxpool"
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/trace"

    "yourapp/internal/apperr"
    "yourapp/internal/domain"
    "yourapp/internal/widget"
)

type widgetRepo struct {
    pool   *pgxpool.Pool
    l1     sync.Map          // L1: in-memory cache (1min TTL)
    redis  RedisClient       // L2: Redis cache (5min TTL)
    logger *slog.Logger
    tracer trace.Tracer

    l1TTL time.Duration
    l2TTL time.Duration
}

// NewWidgetRepo creates a repository backed by pgxpool with multi-level caching.
func NewWidgetRepo(pool *pgxpool.Pool, redis RedisClient, logger *slog.Logger) *widgetRepo {
    return &widgetRepo{
        pool:   pool,
        redis:  redis,
        logger: logger.With("repo", "widget"),
        tracer: otel.Tracer("widget-repo"),
        l1TTL:  1 * time.Minute,
        l2TTL:  5 * time.Minute,
    }
}

// PoolConfig returns recommended pgxpool configuration.
// Apply this when creating the pool in main.go or service bootstrap.
func PoolConfig(connString string) (*pgxpool.Config, error) {
    cfg, err := pgxpool.ParseConfig(connString)
    if err != nil {
        return nil, fmt.Errorf("parse pool config: %w", err)
    }
    cfg.MaxConns = 50
    cfg.MinConns = 10
    cfg.MaxConnLifetime = time.Hour
    cfg.MaxConnIdleTime = 30 * time.Minute
    cfg.HealthCheckPeriod = time.Minute
    return cfg, nil
}
```

## Create

```go
func (r *widgetRepo) Create(ctx context.Context, w *widget.Widget) error {
    ctx, span := r.tracer.Start(ctx, "repo.widget.create")
    defer span.End()

    reqID := RequestIDFromContext(ctx)
    logger := r.logger.With("request_id", reqID, "method", "Create")

    ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
    defer cancel()

    const query = `
        INSERT INTO widgets (id, tenant_id, name, description, status, created_at, updated_at, created_by, updated_by, version)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)`

    _, err := r.pool.Exec(ctx, query,
        w.ID, w.TenantID, w.Name, w.Description, w.Status,
        w.CreatedAt, w.UpdatedAt, w.CreatedBy, w.UpdatedBy, w.Version,
    )
    if err != nil {
        logger.ErrorContext(ctx, "create failed", "widget_id", w.ID, "error", err)
        return r.mapError(err, "create")
    }

    logger.InfoContext(ctx, "widget created", "widget_id", w.ID, "tenant_id", w.TenantID)
    return nil
}
```

## GetByID with Multi-Level Cache

```go
func (r *widgetRepo) GetByID(ctx context.Context, tenantID, id uuid.UUID) (*widget.Widget, error) {
    ctx, span := r.tracer.Start(ctx, "repo.widget.get_by_id")
    defer span.End()

    reqID := RequestIDFromContext(ctx)
    logger := r.logger.With("request_id", reqID, "method", "GetByID", "widget_id", id)

    cacheKey := fmt.Sprintf("widget:%s:%s", tenantID, id)

    // L1: In-memory (sync.Map, < 100ns)
    if entry, ok := r.l1.Load(cacheKey); ok {
        ce := entry.(*cacheEntry)
        if time.Now().Before(ce.expiresAt) {
            return ce.widget, nil
        }
        r.l1.Delete(cacheKey) // expired
    }

    // L2: Redis (< 1ms)
    if data, err := r.redis.Get(ctx, cacheKey); err == nil {
        var w widget.Widget
        if err := json.Unmarshal(data, &w); err == nil {
            r.l1Store(cacheKey, &w) // promote to L1
            return &w, nil
        }
    }

    // L3: PostgreSQL
    ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
    defer cancel()

    const query = `
        SELECT id, tenant_id, name, description, status,
               created_at, updated_at, deleted_at, created_by, updated_by, version
        FROM widgets
        WHERE tenant_id = $1 AND id = $2 AND deleted_at IS NULL`

    var w widget.Widget
    err := r.pool.QueryRow(ctx, query, tenantID, id).Scan(
        &w.ID, &w.TenantID, &w.Name, &w.Description, &w.Status,
        &w.CreatedAt, &w.UpdatedAt, &w.DeletedAt, &w.CreatedBy, &w.UpdatedBy, &w.Version,
    )
    if err != nil {
        logger.ErrorContext(ctx, "get_by_id failed", "error", err)
        return nil, r.mapError(err, "get_by_id")
    }

    logger.DebugContext(ctx, "widget retrieved from database")

    // Populate both cache levels
    r.l1Store(cacheKey, &w)
    r.l2Store(ctx, cacheKey, &w)

    return &w, nil
}

// cacheEntry wraps a cached widget with expiry for L1.
type cacheEntry struct {
    widget    *widget.Widget
    expiresAt time.Time
}

func (r *widgetRepo) l1Store(key string, w *widget.Widget) {
    r.l1.Store(key, &cacheEntry{
        widget:    w,
        expiresAt: time.Now().Add(r.l1TTL),
    })
}

func (r *widgetRepo) l2Store(ctx context.Context, key string, w *widget.Widget) {
    data, err := json.Marshal(w)
    if err != nil {
        r.logger.ErrorContext(ctx, "l2 cache marshal failed", "error", err)
        return
    }
    if err := r.redis.Set(ctx, key, data, r.l2TTL); err != nil {
        r.logger.ErrorContext(ctx, "l2 cache set failed", "error", err)
    }
}

// InvalidateCache removes a widget from all cache levels.
func (r *widgetRepo) InvalidateCache(ctx context.Context, tenantID, id uuid.UUID) {
    key := fmt.Sprintf("widget:%s:%s", tenantID, id)
    r.l1.Delete(key)
    _ = r.redis.Delete(ctx, key)
}
```

## Update with Optimistic Locking

```go
func (r *widgetRepo) Update(ctx context.Context, w *widget.Widget) error {
    ctx, span := r.tracer.Start(ctx, "repo.widget.update")
    defer span.End()

    ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
    defer cancel()

    // Optimistic lock: WHERE version = $expected ensures no concurrent modification
    const query = `
        UPDATE widgets
        SET name = $3, description = $4, status = $5,
            updated_at = $6, updated_by = $7, version = $8
        WHERE tenant_id = $1 AND id = $2 AND version = $9 AND deleted_at IS NULL`

    result, err := r.pool.Exec(ctx, query,
        w.TenantID, w.ID, w.Name, w.Description, w.Status,
        w.UpdatedAt, w.UpdatedBy, w.Version, // new version
        w.Version-1, // expected previous version
    )
    if err != nil {
        return r.mapError(err, "update")
    }
    if result.RowsAffected() == 0 {
        return apperr.NewConflictError("widget", "version mismatch or not found — reload and retry")
    }

    // Invalidate cache on write
    r.InvalidateCache(ctx, w.TenantID, w.ID)

    return nil
}
```

## Soft Delete

```go
func (r *widgetRepo) SoftDelete(ctx context.Context, tenantID, id uuid.UUID) error {
    ctx, span := r.tracer.Start(ctx, "repo.widget.soft_delete")
    defer span.End()

    ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
    defer cancel()

    const query = `
        UPDATE widgets
        SET deleted_at = NOW(), updated_at = NOW()
        WHERE tenant_id = $1 AND id = $2 AND deleted_at IS NULL`

    result, err := r.pool.Exec(ctx, query, tenantID, id)
    if err != nil {
        return r.mapError(err, "soft_delete")
    }
    if result.RowsAffected() == 0 {
        return apperr.NewNotFoundError("widget", id.String())
    }

    r.InvalidateCache(ctx, tenantID, id)

    return nil
}
```

## List with Cursor-Based Pagination

```go
func (r *widgetRepo) List(ctx context.Context, tenantID uuid.UUID, filters domain.ListFilters) (*domain.ListResult[widget.Widget], error) {
    ctx, span := r.tracer.Start(ctx, "repo.widget.list")
    defer span.End()

    reqID := RequestIDFromContext(ctx)
    logger := r.logger.With("request_id", reqID, "method", "List")

    ctx, cancel := context.WithTimeout(ctx, 10*time.Second)
    defer cancel()

    // Build query with dynamic filters
    qb := newQueryBuilder()
    qb.WriteString(`
        SELECT id, tenant_id, name, description, status,
               created_at, updated_at, created_by, updated_by, version
        FROM widgets
        WHERE tenant_id = `)
    qb.AddParam(tenantID)
    qb.WriteString(` AND deleted_at IS NULL`)

    // Apply dynamic field filters (allow-listed in handler)
    for field, value := range filters.Fields {
        qb.WriteString(fmt.Sprintf(` AND %s = `, sanitizeColumn(field)))
        qb.AddParam(value)
    }

    // Apply cursor (decode from opaque base64 token)
    if filters.Cursor != "" {
        ts, cursorID, err := decodeCursor(filters.Cursor)
        if err != nil {
            return nil, apperr.NewValidationError("cursor", err)
        }
        if filters.SortDir == "desc" {
            qb.WriteString(fmt.Sprintf(` AND (%s, id) < (`, sanitizeColumn(filters.SortBy)))
        } else {
            qb.WriteString(fmt.Sprintf(` AND (%s, id) > (`, sanitizeColumn(filters.SortBy)))
        }
        qb.AddParam(ts)
        qb.WriteString(`, `)
        qb.AddParam(cursorID)
        qb.WriteString(`)`)
    }

    // Order and limit (request limit+1 to detect has_more)
    qb.WriteString(fmt.Sprintf(` ORDER BY %s %s, id %s`,
        sanitizeColumn(filters.SortBy), filters.SortDir, filters.SortDir))
    qb.WriteString(` LIMIT `)
    qb.AddParam(filters.PageSize + 1)

    rows, err := r.pool.Query(ctx, qb.String(), qb.Params()...)
    if err != nil {
        return nil, r.mapError(err, "list")
    }
    defer rows.Close()

    var items []widget.Widget
    for rows.Next() {
        var w widget.Widget
        if err := rows.Scan(
            &w.ID, &w.TenantID, &w.Name, &w.Description, &w.Status,
            &w.CreatedAt, &w.UpdatedAt, &w.CreatedBy, &w.UpdatedBy, &w.Version,
        ); err != nil {
            return nil, fmt.Errorf("widget list scan: %w", err)
        }
        items = append(items, w)
    }
    if err := rows.Err(); err != nil {
        return nil, r.mapError(err, "list")
    }

    // Determine has_more and trim to requested page size
    hasMore := len(items) > filters.PageSize
    if hasMore {
        items = items[:filters.PageSize]
    }

    // Build next cursor from last item
    var nextCursor string
    if hasMore && len(items) > 0 {
        last := items[len(items)-1]
        nextCursor = encodeCursor(last.CreatedAt, last.ID)
    }

    // Count total (optional — use for UI, skip for performance on huge tables)
    total := r.countTotal(ctx, tenantID, filters)

    logger.InfoContext(ctx, "list completed",
        "result_count", len(items),
        "has_more", hasMore,
        "total", total,
    )

    return &domain.ListResult[widget.Widget]{
        Items:   items,
        Cursor:  nextCursor,
        HasMore: hasMore,
        Total:   total,
    }, nil
}

func (r *widgetRepo) countTotal(ctx context.Context, tenantID uuid.UUID, filters domain.ListFilters) int {
    qb := newQueryBuilder()
    qb.WriteString(`SELECT COUNT(*) FROM widgets WHERE tenant_id = `)
    qb.AddParam(tenantID)
    qb.WriteString(` AND deleted_at IS NULL`)
    for field, value := range filters.Fields {
        qb.WriteString(fmt.Sprintf(` AND %s = `, sanitizeColumn(field)))
        qb.AddParam(value)
    }
    var count int
    if err := r.pool.QueryRow(ctx, qb.String(), qb.Params()...).Scan(&count); err != nil {
        r.logger.ErrorContext(ctx, "count query failed", "error", err)
        return 0
    }
    return count
}
```

## Cursor Encoding / Decoding

```go
// Cursor = base64(JSON{timestamp, id}) — opaque, stable across inserts.
type cursorPayload struct {
    Timestamp time.Time `json:"ts"`
    ID        uuid.UUID `json:"id"`
}

func encodeCursor(ts time.Time, id uuid.UUID) string {
    payload := cursorPayload{Timestamp: ts, ID: id}
    data, _ := json.Marshal(payload)
    return base64.URLEncoding.EncodeToString(data)
}

func decodeCursor(cursor string) (time.Time, uuid.UUID, error) {
    data, err := base64.URLEncoding.DecodeString(cursor)
    if err != nil {
        return time.Time{}, uuid.Nil, fmt.Errorf("invalid cursor encoding: %w", err)
    }
    var payload cursorPayload
    if err := json.Unmarshal(data, &payload); err != nil {
        return time.Time{}, uuid.Nil, fmt.Errorf("invalid cursor payload: %w", err)
    }
    return payload.Timestamp, payload.ID, nil
}
```

## Batch Operations

```go
func (r *widgetRepo) BatchCreate(ctx context.Context, widgets []*widget.Widget) error {
    ctx, span := r.tracer.Start(ctx, "repo.widget.batch_create")
    defer span.End()

    ctx, cancel := context.WithTimeout(ctx, 30*time.Second)
    defer cancel()

    // Use pgx CopyFrom for high-performance bulk inserts
    columns := []string{
        "id", "tenant_id", "name", "description", "status",
        "created_at", "updated_at", "created_by", "updated_by", "version",
    }

    rows := make([][]any, len(widgets))
    for i, w := range widgets {
        rows[i] = []any{
            w.ID, w.TenantID, w.Name, w.Description, w.Status,
            w.CreatedAt, w.UpdatedAt, w.CreatedBy, w.UpdatedBy, w.Version,
        }
    }

    copied, err := r.pool.CopyFrom(ctx,
        pgx.Identifier{"widgets"},
        columns,
        pgx.CopyFromRows(rows),
    )
    if err != nil {
        return r.mapError(err, "batch_create")
    }
    if int(copied) != len(widgets) {
        return fmt.Errorf("batch_create: expected %d rows, copied %d", len(widgets), copied)
    }
    return nil
}

func (r *widgetRepo) BatchUpdate(ctx context.Context, widgets []*widget.Widget) error {
    ctx, span := r.tracer.Start(ctx, "repo.widget.batch_update")
    defer span.End()

    ctx, cancel := context.WithTimeout(ctx, 30*time.Second)
    defer cancel()

    batch := &pgx.Batch{}
    const query = `
        UPDATE widgets
        SET name = $3, description = $4, status = $5,
            updated_at = $6, updated_by = $7, version = $8
        WHERE tenant_id = $1 AND id = $2 AND version = $9 AND deleted_at IS NULL`

    for _, w := range widgets {
        batch.Queue(query,
            w.TenantID, w.ID, w.Name, w.Description, w.Status,
            w.UpdatedAt, w.UpdatedBy, w.Version,
            w.Version-1,
        )
    }

    br := r.pool.SendBatch(ctx, batch)
    defer br.Close()

    for i := range widgets {
        result, err := br.Exec()
        if err != nil {
            return fmt.Errorf("batch_update item %d: %w", i, r.mapError(err, "batch_update"))
        }
        if result.RowsAffected() == 0 {
            return apperr.NewConflictError("widget", fmt.Sprintf("version mismatch on item %d", i))
        }
    }
    return nil
}
```

## Query Builder for Dynamic Filters

```go
// queryBuilder constructs parameterized SQL queries with numbered placeholders.
// Prevents SQL injection by never interpolating user values into the query string.
type queryBuilder struct {
    buf    strings.Builder
    params []any
}

func newQueryBuilder() *queryBuilder {
    return &queryBuilder{}
}

func (qb *queryBuilder) WriteString(s string) {
    qb.buf.WriteString(s)
}

func (qb *queryBuilder) AddParam(val any) {
    qb.params = append(qb.params, val)
    qb.buf.WriteString(fmt.Sprintf("$%d", len(qb.params)))
}

func (qb *queryBuilder) String() string { return qb.buf.String() }
func (qb *queryBuilder) Params() []any  { return qb.params }

// sanitizeColumn allows only known column names — prevents SQL injection in ORDER BY / WHERE.
func sanitizeColumn(col string) string {
    allowed := map[string]string{
        "created_at": "created_at",
        "updated_at": "updated_at",
        "name":       "name",
        "status":     "status",
        "priority":   "priority",
        "category":   "category",
    }
    if safe, ok := allowed[col]; ok {
        return safe
    }
    return "created_at" // safe default
}
```

## List with Offset-Based Pagination (Admin/Reporting)

Use offset pagination for admin dashboards, reporting UIs, and data export previews where users need "jump to page N" functionality. See the handler archetype's "Pagination Strategy" section for when to use cursor vs. offset.

```go
// OffsetListFilters defines offset-based pagination parameters.
// Add this to the domain package alongside ListFilters.
type OffsetListFilters struct {
    Page    int               `json:"page"`
    PerPage int               `json:"per_page"`
    SortBy  string            `json:"sort_by"`
    SortDir string            `json:"sort_dir"`
    Fields  map[string]string `json:"fields,omitempty"`
}

// OffsetListResult wraps offset-paginated results.
type OffsetListResult[T any] struct {
    Items []T `json:"items"`
    Total int `json:"total"`
}

func (r *widgetRepo) ListOffset(ctx context.Context, tenantID uuid.UUID, filters domain.OffsetListFilters) (*domain.OffsetListResult[widget.Widget], error) {
    ctx, span := r.tracer.Start(ctx, "repo.widget.list_offset")
    defer span.End()

    reqID := RequestIDFromContext(ctx)
    logger := r.logger.With("request_id", reqID, "method", "ListOffset")

    ctx, cancel := context.WithTimeout(ctx, 10*time.Second)
    defer cancel()

    // Calculate offset from page number
    offset := (filters.Page - 1) * filters.PerPage

    // Build query with dynamic filters
    qb := newQueryBuilder()
    qb.WriteString(`
        SELECT id, tenant_id, name, description, status,
               created_at, updated_at, created_by, updated_by, version
        FROM widgets
        WHERE tenant_id = `)
    qb.AddParam(tenantID)
    qb.WriteString(` AND deleted_at IS NULL`)

    // Apply dynamic field filters (allow-listed in handler)
    for field, value := range filters.Fields {
        qb.WriteString(fmt.Sprintf(` AND %s = `, sanitizeColumn(field)))
        qb.AddParam(value)
    }

    // Order, limit, and offset
    qb.WriteString(fmt.Sprintf(` ORDER BY %s %s, id %s`,
        sanitizeColumn(filters.SortBy), filters.SortDir, filters.SortDir))
    qb.WriteString(` LIMIT `)
    qb.AddParam(filters.PerPage)
    qb.WriteString(` OFFSET `)
    qb.AddParam(offset)

    rows, err := r.pool.Query(ctx, qb.String(), qb.Params()...)
    if err != nil {
        logger.ErrorContext(ctx, "list_offset query failed", "error", err)
        return nil, r.mapError(err, "list_offset")
    }
    defer rows.Close()

    var items []widget.Widget
    for rows.Next() {
        var w widget.Widget
        if err := rows.Scan(
            &w.ID, &w.TenantID, &w.Name, &w.Description, &w.Status,
            &w.CreatedAt, &w.UpdatedAt, &w.CreatedBy, &w.UpdatedBy, &w.Version,
        ); err != nil {
            return nil, fmt.Errorf("widget list_offset scan: %w", err)
        }
        items = append(items, w)
    }
    if err := rows.Err(); err != nil {
        return nil, r.mapError(err, "list_offset")
    }

    // Count total (required for offset pagination to calculate total_pages)
    total := r.countTotal(ctx, tenantID, domain.ListFilters{Fields: filters.Fields})

    logger.InfoContext(ctx, "list_offset completed",
        "page", filters.Page,
        "per_page", filters.PerPage,
        "result_count", len(items),
        "total", total,
    )

    return &domain.OffsetListResult[widget.Widget]{
        Items: items,
        Total: total,
    }, nil
}
```

## Error Mapping

```go
// mapError translates pgx/pgconn errors to domain error types.
func (r *widgetRepo) mapError(err error, operation string) error {
    if err == nil {
        return nil
    }

    // No rows found → NotFound
    if errors.Is(err, pgx.ErrNoRows) {
        return apperr.NewNotFoundError("widget", "")
    }

    // PostgreSQL-specific error codes
    var pgErr *pgconn.PgError
    if errors.As(err, &pgErr) {
        switch pgErr.Code {
        case "23505": // unique_violation
            return apperr.NewConflictError("widget",
                fmt.Sprintf("duplicate value on %s", pgErr.ConstraintName))
        case "23503": // foreign_key_violation
            return apperr.NewValidationError(pgErr.ConstraintName,
                fmt.Errorf("referenced resource does not exist"))
        case "23514": // check_violation
            return apperr.NewValidationError(pgErr.ConstraintName,
                fmt.Errorf("value violates constraint %s", pgErr.ConstraintName))
        case "57014": // query_canceled (context timeout)
            return apperr.NewInternalError(fmt.Errorf("query timeout: %w", err))
        }
    }

    // Context errors
    if errors.Is(err, context.DeadlineExceeded) {
        return apperr.NewInternalError(fmt.Errorf("widget %s timeout: %w", operation, err))
    }
    if errors.Is(err, context.Canceled) {
        return apperr.NewInternalError(fmt.Errorf("widget %s canceled: %w", operation, err))
    }

    return apperr.NewInternalError(fmt.Errorf("widget %s: %w", operation, err))
}
```

## Critical Rules

- Every query MUST include `WHERE tenant_id = $N` — no cross-tenant data leaks
- Every query MUST use parameterized placeholders (`$1`, `$2`) — never string interpolation
- Every read query MUST include `AND deleted_at IS NULL` (soft delete filter)
- Every query MUST have a `context.WithTimeout` — never allow unbounded queries
- Update operations MUST use optimistic locking: `WHERE version = $expected`
- Column names in ORDER BY / WHERE MUST be allow-listed via `sanitizeColumn`
- Cursor values MUST be opaque (base64-encoded JSON) — never expose raw DB values
- List queries MUST request `LIMIT + 1` to detect `has_more` without extra count query
- Batch inserts SHOULD use `pgx.CopyFrom` for performance (thousands of rows)
- Batch updates SHOULD use `pgx.Batch` to minimize round trips
- pgx errors MUST be mapped to domain errors at the repository boundary
- Cache MUST be invalidated on every write (Update, Delete) — both L1 and L2
- L1 cache entries MUST have TTL checked on read — stale entries are evicted lazily
- Every repository method MUST extract `request_id` from context and include it in structured log lines
- `RequestIDFromContext(ctx)` extracts the request ID set by auth middleware — propagate it through all layers
