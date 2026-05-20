> **This file contains Go-specific patterns for: CRUD Repository Test Archetype.** The language-neutral version at [crud-repository-test.md](crud-repository-test.md) contains the same Go patterns and serves as the canonical reference. This file exists for consistent `{{LANG}}` placeholder resolution by `agent_factory`.

---
skill: crud-repository-test
description: Go integration test archetype for repository layer — testcontainers PostgreSQL, transaction-per-test isolation, real DB queries, pagination, tenant isolation, optimistic locking, error mapping
version: "1.0"
tags:
  - go
  - repository
  - integration-test
  - postgres
  - testcontainers
  - archetype
  - backend
  - testing
---

# CRUD Repository Test Archetype

Complete integration test template for the repository layer using a real PostgreSQL database. Every generated repository test MUST follow this pattern.

## Test File Location

```
internal/widget/postgres/
  repository.go           <- production code
  repository_test.go      <- THIS file (integration tests)
```

Rule: Integration tests live in the same package as the repository implementation. Use build tags if needed to separate from unit tests.

## Test Infrastructure — testcontainers + Migrations

```go
package postgres

import (
    "context"
    "fmt"
    "log"
    "os"
    "testing"
    "time"

    "github.com/google/uuid"
    "github.com/jackc/pgx/v5/pgxpool"
    "github.com/stretchr/testify/assert"
    "github.com/stretchr/testify/require"
    "github.com/testcontainers/testcontainers-go"
    "github.com/testcontainers/testcontainers-go/modules/postgres"
    "github.com/testcontainers/testcontainers-go/wait"

    "yourapp/internal/domain"
    "yourapp/internal/widget"
)

var testPool *pgxpool.Pool

// TestMain starts a PostgreSQL container, runs migrations, and creates a shared pool.
// All tests in this package share the same container (fast startup) but each test
// gets its own transaction for isolation.
func TestMain(m *testing.M) {
    ctx := context.Background()

    // 1. Start PostgreSQL container
    pgContainer, err := postgres.Run(ctx,
        "postgres:16-alpine",
        postgres.WithDatabase("testdb"),
        postgres.WithUsername("test"),
        postgres.WithPassword("test"),
        testcontainers.WithWaitStrategy(
            wait.ForLog("database system is ready to accept connections").
                WithOccurrence(2).
                WithStartupTimeout(30*time.Second),
        ),
    )
    if err != nil {
        log.Fatalf("failed to start postgres container: %v", err)
    }

    // 2. Get connection string
    connStr, err := pgContainer.ConnectionString(ctx, "sslmode=disable")
    if err != nil {
        log.Fatalf("failed to get connection string: %v", err)
    }

    // 3. Create pool
    poolCfg, err := pgxpool.ParseConfig(connStr)
    if err != nil {
        log.Fatalf("failed to parse pool config: %v", err)
    }
    poolCfg.MaxConns = 10
    testPool, err = pgxpool.NewWithConfig(ctx, poolCfg)
    if err != nil {
        log.Fatalf("failed to create pool: %v", err)
    }

    // 4. Run migrations
    if err := runMigrations(ctx, testPool); err != nil {
        log.Fatalf("failed to run migrations: %v", err)
    }

    // 5. Run tests
    code := m.Run()

    // 6. Cleanup
    testPool.Close()
    if err := pgContainer.Terminate(ctx); err != nil {
        log.Printf("failed to terminate container: %v", err)
    }

    os.Exit(code)
}

// runMigrations applies the SQL schema needed for widget tests.
// In production, use golang-migrate or atlas. For tests, inline SQL is fine.
func runMigrations(ctx context.Context, pool *pgxpool.Pool) error {
    schema := `
        CREATE TABLE IF NOT EXISTS widgets (
            id         UUID PRIMARY KEY,
            tenant_id  UUID NOT NULL,
            name       VARCHAR(255) NOT NULL,
            description TEXT DEFAULT '',
            status     VARCHAR(50) NOT NULL DEFAULT 'active',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            deleted_at TIMESTAMPTZ,
            created_by UUID NOT NULL,
            updated_by UUID NOT NULL,
            version    INT NOT NULL DEFAULT 1,

            CONSTRAINT uq_widgets_tenant_name UNIQUE (tenant_id, name) WHERE deleted_at IS NULL
        );

        CREATE INDEX IF NOT EXISTS idx_widgets_tenant_id ON widgets(tenant_id) WHERE deleted_at IS NULL;
        CREATE INDEX IF NOT EXISTS idx_widgets_tenant_created ON widgets(tenant_id, created_at DESC) WHERE deleted_at IS NULL;
        CREATE INDEX IF NOT EXISTS idx_widgets_tenant_status ON widgets(tenant_id, status) WHERE deleted_at IS NULL;
    `
    _, err := pool.Exec(ctx, schema)
    return err
}
```

## Transaction-Per-Test Isolation

```go
// testTx starts a transaction and returns a cleanup function that rolls it back.
// Every test gets a fresh, isolated view of the database.
func testTx(t *testing.T) (*pgxpool.Pool, func()) {
    t.Helper()
    ctx := context.Background()

    // Use a savepoint-based approach: acquire a connection, start a tx,
    // and wrap the pool interface so all queries go through this tx.
    // For simplicity, we use truncation here.
    cleanup := func() {
        _, err := testPool.Exec(ctx, "DELETE FROM widgets")
        if err != nil {
            t.Logf("cleanup failed: %v", err)
        }
    }
    // Pre-clean to ensure isolation from other tests
    cleanup()

    return testPool, cleanup
}

// Alternative: Savepoint-per-test using pgx transactions (more efficient for large datasets).
// Uses a wrapper pool that routes all queries through a single transaction.
// See: https://github.com/jackc/pgx/issues/xxx for pgxpool transaction wrapper patterns.
```

## Test Factory

```go
// makeWidget builds a test widget with sensible defaults for DB insertion.
func makeWidget(t *testing.T, opts ...func(*widget.Widget)) *widget.Widget {
    t.Helper()
    now := time.Now().UTC().Truncate(time.Microsecond) // Postgres truncates to microsecond
    w := &widget.Widget{
        Entity: domain.Entity{
            ID:        uuid.New(),
            TenantID:  uuid.New(),
            CreatedAt: now,
            UpdatedAt: now,
            CreatedBy: uuid.New(),
            UpdatedBy: uuid.New(),
            Version:   1,
        },
        Name:        fmt.Sprintf("widget-%s", uuid.New().String()[:8]),
        Description: "Test widget description",
        Status:      "active",
    }
    for _, opt := range opts {
        opt(w)
    }
    return w
}

func withTenant(id uuid.UUID) func(*widget.Widget) {
    return func(w *widget.Widget) { w.TenantID = id }
}

func withID(id uuid.UUID) func(*widget.Widget) {
    return func(w *widget.Widget) { w.ID = id }
}

func withName(name string) func(*widget.Widget) {
    return func(w *widget.Widget) { w.Name = name }
}

func withStatus(status string) func(*widget.Widget) {
    return func(w *widget.Widget) { w.Status = status }
}

func withVersion(v int) func(*widget.Widget) {
    return func(w *widget.Widget) { w.Version = v }
}

func withCreatedAt(t time.Time) func(*widget.Widget) {
    return func(w *widget.Widget) { w.CreatedAt = t.Truncate(time.Microsecond) }
}

// seedWidgets bulk-inserts widgets into the database for test setup.
func seedWidgets(t *testing.T, ctx context.Context, repo widget.Repository, widgets ...*widget.Widget) {
    t.Helper()
    for _, w := range widgets {
        err := repo.Create(ctx, w)
        require.NoError(t, err, "failed to seed widget %s", w.ID)
    }
}

// newTestRepo creates a repository instance with the test pool and no-op Redis.
func newTestRepo(t *testing.T, pool *pgxpool.Pool) *widgetRepo {
    t.Helper()
    logger := slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: slog.LevelError}))
    return NewWidgetRepo(pool, &noopRedis{}, logger)
}

// noopRedis implements RedisClient for tests that don't need caching.
type noopRedis struct{}

func (n *noopRedis) Get(ctx context.Context, key string) ([]byte, error) {
    return nil, fmt.Errorf("miss")
}
func (n *noopRedis) Set(ctx context.Context, key string, val []byte, ttl time.Duration) error {
    return nil
}
func (n *noopRedis) Delete(ctx context.Context, key string) error {
    return nil
}
```

## CRUD Tests with Real Database

```go
func TestCreate_InsertsAndReturns(t *testing.T) {
    pool, cleanup := testTx(t)
    defer cleanup()
    ctx := context.Background()
    repo := newTestRepo(t, pool)

    w := makeWidget(t)
    err := repo.Create(ctx, w)
    require.NoError(t, err)

    // Verify it was persisted
    got, err := repo.GetByID(ctx, w.TenantID, w.ID)
    require.NoError(t, err)
    assert.Equal(t, w.ID, got.ID)
    assert.Equal(t, w.TenantID, got.TenantID)
    assert.Equal(t, w.Name, got.Name)
    assert.Equal(t, w.Description, got.Description)
    assert.Equal(t, 1, got.Version)
    assert.Nil(t, got.DeletedAt)
}

func TestGetByID_ReturnsWidget(t *testing.T) {
    pool, cleanup := testTx(t)
    defer cleanup()
    ctx := context.Background()
    repo := newTestRepo(t, pool)

    w := makeWidget(t)
    seedWidgets(t, ctx, repo, w)

    got, err := repo.GetByID(ctx, w.TenantID, w.ID)
    require.NoError(t, err)
    assert.Equal(t, w.ID, got.ID)
    assert.Equal(t, w.Name, got.Name)
}

func TestGetByID_NotFound(t *testing.T) {
    pool, cleanup := testTx(t)
    defer cleanup()
    ctx := context.Background()
    repo := newTestRepo(t, pool)

    got, err := repo.GetByID(ctx, uuid.New(), uuid.New())
    assert.Nil(t, got)
    assert.Error(t, err)
    assertIsNotFoundError(t, err)
}

func TestUpdate_IncrementsVersion(t *testing.T) {
    pool, cleanup := testTx(t)
    defer cleanup()
    ctx := context.Background()
    repo := newTestRepo(t, pool)

    w := makeWidget(t)
    seedWidgets(t, ctx, repo, w)

    // Update fields and increment version
    w.Name = "Updated Name"
    w.UpdatedAt = time.Now().UTC().Truncate(time.Microsecond)
    w.Version = 2 // new version
    err := repo.Update(ctx, w)
    require.NoError(t, err)

    // Verify updated
    got, err := repo.GetByID(ctx, w.TenantID, w.ID)
    require.NoError(t, err)
    assert.Equal(t, "Updated Name", got.Name)
    assert.Equal(t, 2, got.Version)
}

func TestSoftDelete_SetsDeletedAt(t *testing.T) {
    pool, cleanup := testTx(t)
    defer cleanup()
    ctx := context.Background()
    repo := newTestRepo(t, pool)

    w := makeWidget(t)
    seedWidgets(t, ctx, repo, w)

    err := repo.SoftDelete(ctx, w.TenantID, w.ID)
    require.NoError(t, err)

    // GetByID should NOT find it (filtered by deleted_at IS NULL)
    got, err := repo.GetByID(ctx, w.TenantID, w.ID)
    assert.Nil(t, got)
    assertIsNotFoundError(t, err)

    // But the row still exists in the database with deleted_at set
    var deletedAt *time.Time
    err = pool.QueryRow(ctx,
        "SELECT deleted_at FROM widgets WHERE id = $1", w.ID,
    ).Scan(&deletedAt)
    require.NoError(t, err)
    assert.NotNil(t, deletedAt, "deleted_at should be set after soft delete")
}

func TestSoftDelete_NonExistent_ReturnsNotFound(t *testing.T) {
    pool, cleanup := testTx(t)
    defer cleanup()
    ctx := context.Background()
    repo := newTestRepo(t, pool)

    err := repo.SoftDelete(ctx, uuid.New(), uuid.New())
    assertIsNotFoundError(t, err)
}
```

## Pagination Tests

```go
func TestList_CursorPagination(t *testing.T) {
    pool, cleanup := testTx(t)
    defer cleanup()
    ctx := context.Background()
    repo := newTestRepo(t, pool)

    tenantID := uuid.New()

    // Insert 25 widgets with staggered creation times
    baseTime := time.Now().UTC().Add(-1 * time.Hour).Truncate(time.Microsecond)
    for i := 0; i < 25; i++ {
        w := makeWidget(t,
            withTenant(tenantID),
            withCreatedAt(baseTime.Add(time.Duration(i)*time.Second)),
            withName(fmt.Sprintf("widget-%03d", i)),
        )
        seedWidgets(t, ctx, repo, w)
    }

    // Page 1: fetch first 20
    page1, err := repo.List(ctx, tenantID, domain.ListFilters{
        PageSize: 20,
        SortBy:   "created_at",
        SortDir:  "desc",
    })
    require.NoError(t, err)
    assert.Len(t, page1.Items, 20)
    assert.True(t, page1.HasMore)
    assert.NotEmpty(t, page1.Cursor, "cursor must be set when has_more=true")
    assert.Equal(t, 25, page1.Total)

    // Page 2: fetch remaining 5 using cursor
    page2, err := repo.List(ctx, tenantID, domain.ListFilters{
        PageSize: 20,
        Cursor:   page1.Cursor,
        SortBy:   "created_at",
        SortDir:  "desc",
    })
    require.NoError(t, err)
    assert.Len(t, page2.Items, 5)
    assert.False(t, page2.HasMore)

    // Verify no duplicates between pages
    page1IDs := make(map[uuid.UUID]bool)
    for _, w := range page1.Items {
        page1IDs[w.ID] = true
    }
    for _, w := range page2.Items {
        assert.False(t, page1IDs[w.ID], "page 2 item %s was already in page 1", w.ID)
    }
}

func TestList_EmptyResult(t *testing.T) {
    pool, cleanup := testTx(t)
    defer cleanup()
    ctx := context.Background()
    repo := newTestRepo(t, pool)

    result, err := repo.List(ctx, uuid.New(), domain.ListFilters{
        PageSize: 20,
        SortBy:   "created_at",
        SortDir:  "desc",
    })
    require.NoError(t, err)
    assert.Len(t, result.Items, 0)
    assert.False(t, result.HasMore)
    assert.Empty(t, result.Cursor)
    assert.Equal(t, 0, result.Total)
}

func TestList_SortOrder(t *testing.T) {
    pool, cleanup := testTx(t)
    defer cleanup()
    ctx := context.Background()
    repo := newTestRepo(t, pool)

    tenantID := uuid.New()
    baseTime := time.Now().UTC().Truncate(time.Microsecond)

    w1 := makeWidget(t, withTenant(tenantID), withCreatedAt(baseTime), withName("alpha"))
    w2 := makeWidget(t, withTenant(tenantID), withCreatedAt(baseTime.Add(time.Second)), withName("bravo"))
    w3 := makeWidget(t, withTenant(tenantID), withCreatedAt(baseTime.Add(2*time.Second)), withName("charlie"))
    seedWidgets(t, ctx, repo, w1, w2, w3)

    // Ascending order
    result, err := repo.List(ctx, tenantID, domain.ListFilters{
        PageSize: 10, SortBy: "created_at", SortDir: "asc",
    })
    require.NoError(t, err)
    require.Len(t, result.Items, 3)
    assert.Equal(t, w1.ID, result.Items[0].ID, "first item should be oldest")
    assert.Equal(t, w3.ID, result.Items[2].ID, "last item should be newest")

    // Descending order
    result, err = repo.List(ctx, tenantID, domain.ListFilters{
        PageSize: 10, SortBy: "created_at", SortDir: "desc",
    })
    require.NoError(t, err)
    require.Len(t, result.Items, 3)
    assert.Equal(t, w3.ID, result.Items[0].ID, "first item should be newest")
    assert.Equal(t, w1.ID, result.Items[2].ID, "last item should be oldest")
}
```

## Tenant Isolation Tests

```go
func TestTenantIsolation_GetByID(t *testing.T) {
    pool, cleanup := testTx(t)
    defer cleanup()
    ctx := context.Background()
    repo := newTestRepo(t, pool)

    tenantA := uuid.New()
    tenantB := uuid.New()

    wA := makeWidget(t, withTenant(tenantA), withName("tenant-a-widget"))
    seedWidgets(t, ctx, repo, wA)

    // Tenant A can see their own widget
    got, err := repo.GetByID(ctx, tenantA, wA.ID)
    require.NoError(t, err)
    assert.Equal(t, wA.ID, got.ID)

    // Tenant B CANNOT see tenant A's widget
    got, err = repo.GetByID(ctx, tenantB, wA.ID)
    assert.Nil(t, got)
    assertIsNotFoundError(t, err)
}

func TestTenantIsolation_List(t *testing.T) {
    pool, cleanup := testTx(t)
    defer cleanup()
    ctx := context.Background()
    repo := newTestRepo(t, pool)

    tenantA := uuid.New()
    tenantB := uuid.New()

    // Seed 3 widgets for tenant A, 2 for tenant B
    for i := 0; i < 3; i++ {
        seedWidgets(t, ctx, repo, makeWidget(t, withTenant(tenantA), withName(fmt.Sprintf("a-%d", i))))
    }
    for i := 0; i < 2; i++ {
        seedWidgets(t, ctx, repo, makeWidget(t, withTenant(tenantB), withName(fmt.Sprintf("b-%d", i))))
    }

    // Tenant A sees only their 3
    resultA, err := repo.List(ctx, tenantA, domain.ListFilters{
        PageSize: 20, SortBy: "created_at", SortDir: "desc",
    })
    require.NoError(t, err)
    assert.Len(t, resultA.Items, 3)
    assert.Equal(t, 3, resultA.Total)
    for _, w := range resultA.Items {
        assert.Equal(t, tenantA, w.TenantID, "all items must belong to tenant A")
    }

    // Tenant B sees only their 2
    resultB, err := repo.List(ctx, tenantB, domain.ListFilters{
        PageSize: 20, SortBy: "created_at", SortDir: "desc",
    })
    require.NoError(t, err)
    assert.Len(t, resultB.Items, 2)
    assert.Equal(t, 2, resultB.Total)
    for _, w := range resultB.Items {
        assert.Equal(t, tenantB, w.TenantID, "all items must belong to tenant B")
    }
}

func TestTenantIsolation_Update(t *testing.T) {
    pool, cleanup := testTx(t)
    defer cleanup()
    ctx := context.Background()
    repo := newTestRepo(t, pool)

    tenantA := uuid.New()
    tenantB := uuid.New()

    wA := makeWidget(t, withTenant(tenantA))
    seedWidgets(t, ctx, repo, wA)

    // Attempt to update with wrong tenant — should fail (version/tenant mismatch)
    wA.TenantID = tenantB
    wA.Name = "hijacked"
    wA.Version = 2
    err := repo.Update(ctx, wA)
    // Either ConflictError (version mismatch because tenant_id won't match)
    // or the row is simply not affected
    assert.Error(t, err)
}

func TestTenantIsolation_SoftDelete(t *testing.T) {
    pool, cleanup := testTx(t)
    defer cleanup()
    ctx := context.Background()
    repo := newTestRepo(t, pool)

    tenantA := uuid.New()
    tenantB := uuid.New()

    wA := makeWidget(t, withTenant(tenantA))
    seedWidgets(t, ctx, repo, wA)

    // Tenant B cannot delete tenant A's widget
    err := repo.SoftDelete(ctx, tenantB, wA.ID)
    assertIsNotFoundError(t, err)

    // Widget still exists for tenant A
    got, err := repo.GetByID(ctx, tenantA, wA.ID)
    require.NoError(t, err)
    assert.Equal(t, wA.ID, got.ID)
}
```

## Concurrent Access / Optimistic Locking Tests

```go
func TestOptimisticLocking_ConcurrentUpdate(t *testing.T) {
    pool, cleanup := testTx(t)
    defer cleanup()
    ctx := context.Background()
    repo := newTestRepo(t, pool)

    w := makeWidget(t)
    seedWidgets(t, ctx, repo, w)

    // Simulate two concurrent reads
    read1, err := repo.GetByID(ctx, w.TenantID, w.ID)
    require.NoError(t, err)

    read2, err := repo.GetByID(ctx, w.TenantID, w.ID)
    require.NoError(t, err)

    // First update succeeds
    read1.Name = "Update A"
    read1.Version = 2
    read1.UpdatedAt = time.Now().UTC().Truncate(time.Microsecond)
    err = repo.Update(ctx, read1)
    require.NoError(t, err, "first update should succeed")

    // Second update fails — version already incremented by first update
    read2.Name = "Update B"
    read2.Version = 2 // same version as read1 expected
    read2.UpdatedAt = time.Now().UTC().Truncate(time.Microsecond)
    err = repo.Update(ctx, read2)
    assert.Error(t, err, "second update should fail with version conflict")
    assertIsConflictError(t, err)

    // Verify the first update persisted
    final, err := repo.GetByID(ctx, w.TenantID, w.ID)
    require.NoError(t, err)
    assert.Equal(t, "Update A", final.Name)
    assert.Equal(t, 2, final.Version)
}

func TestOptimisticLocking_StaleVersion(t *testing.T) {
    pool, cleanup := testTx(t)
    defer cleanup()
    ctx := context.Background()
    repo := newTestRepo(t, pool)

    w := makeWidget(t, withVersion(5))
    seedWidgets(t, ctx, repo, w)

    // Try to update with wrong expected version
    w.Name = "Stale Update"
    w.Version = 3 // expected version 2, but actual is 5
    w.UpdatedAt = time.Now().UTC().Truncate(time.Microsecond)
    err := repo.Update(ctx, w)
    assert.Error(t, err)
    assertIsConflictError(t, err)
}
```

## Filter Tests

```go
func TestList_FilterByStatus(t *testing.T) {
    pool, cleanup := testTx(t)
    defer cleanup()
    ctx := context.Background()
    repo := newTestRepo(t, pool)

    tenantID := uuid.New()
    seedWidgets(t, ctx, repo,
        makeWidget(t, withTenant(tenantID), withStatus("active"), withName("active-1")),
        makeWidget(t, withTenant(tenantID), withStatus("active"), withName("active-2")),
        makeWidget(t, withTenant(tenantID), withStatus("archived"), withName("archived-1")),
    )

    result, err := repo.List(ctx, tenantID, domain.ListFilters{
        PageSize: 20,
        SortBy:   "created_at",
        SortDir:  "desc",
        Fields:   map[string]string{"status": "active"},
    })
    require.NoError(t, err)
    assert.Len(t, result.Items, 2)
    for _, w := range result.Items {
        assert.Equal(t, "active", w.Status)
    }
}

func TestList_CompoundFilters(t *testing.T) {
    pool, cleanup := testTx(t)
    defer cleanup()
    ctx := context.Background()
    repo := newTestRepo(t, pool)

    tenantID := uuid.New()
    seedWidgets(t, ctx, repo,
        makeWidget(t, withTenant(tenantID), withStatus("active"), withName("match")),
        makeWidget(t, withTenant(tenantID), withStatus("archived"), withName("no-match-status")),
        makeWidget(t, withTenant(tenantID), withStatus("active"), withName("other-active")),
    )

    result, err := repo.List(ctx, tenantID, domain.ListFilters{
        PageSize: 20,
        SortBy:   "created_at",
        SortDir:  "desc",
        Fields:   map[string]string{"status": "active"},
    })
    require.NoError(t, err)
    assert.Len(t, result.Items, 2, "should return only active widgets")
}

func TestList_SoftDeletedExcluded(t *testing.T) {
    pool, cleanup := testTx(t)
    defer cleanup()
    ctx := context.Background()
    repo := newTestRepo(t, pool)

    tenantID := uuid.New()
    w1 := makeWidget(t, withTenant(tenantID), withName("visible"))
    w2 := makeWidget(t, withTenant(tenantID), withName("deleted"))
    seedWidgets(t, ctx, repo, w1, w2)

    // Soft-delete w2
    err := repo.SoftDelete(ctx, tenantID, w2.ID)
    require.NoError(t, err)

    result, err := repo.List(ctx, tenantID, domain.ListFilters{
        PageSize: 20, SortBy: "created_at", SortDir: "desc",
    })
    require.NoError(t, err)
    assert.Len(t, result.Items, 1, "soft-deleted widget should be excluded")
    assert.Equal(t, w1.ID, result.Items[0].ID)
}
```

## Error Mapping Tests

```go
func TestCreate_DuplicateKey_ReturnsConflict(t *testing.T) {
    pool, cleanup := testTx(t)
    defer cleanup()
    ctx := context.Background()
    repo := newTestRepo(t, pool)

    tenantID := uuid.New()
    w1 := makeWidget(t, withTenant(tenantID), withName("unique-name"))
    seedWidgets(t, ctx, repo, w1)

    // Insert another with same tenant + name (unique constraint violation)
    w2 := makeWidget(t, withTenant(tenantID), withName("unique-name"))
    err := repo.Create(ctx, w2)
    assert.Error(t, err)
    assertIsConflictError(t, err)
}

func TestCreate_DuplicatePrimaryKey_ReturnsConflict(t *testing.T) {
    pool, cleanup := testTx(t)
    defer cleanup()
    ctx := context.Background()
    repo := newTestRepo(t, pool)

    w := makeWidget(t)
    seedWidgets(t, ctx, repo, w)

    // Try to insert with the same ID
    w2 := makeWidget(t, withID(w.ID), withTenant(w.TenantID), withName("different-name"))
    err := repo.Create(ctx, w2)
    assert.Error(t, err)
    assertIsConflictError(t, err)
}

func TestGetByID_NonExistent_ReturnsNotFound(t *testing.T) {
    pool, cleanup := testTx(t)
    defer cleanup()
    ctx := context.Background()
    repo := newTestRepo(t, pool)

    got, err := repo.GetByID(ctx, uuid.New(), uuid.New())
    assert.Nil(t, got)
    assertIsNotFoundError(t, err)
}

func TestUpdate_NonExistent_ReturnsConflict(t *testing.T) {
    pool, cleanup := testTx(t)
    defer cleanup()
    ctx := context.Background()
    repo := newTestRepo(t, pool)

    w := makeWidget(t, withVersion(2))
    err := repo.Update(ctx, w)
    assert.Error(t, err)
    // RowsAffected == 0 maps to ConflictError
    assertIsConflictError(t, err)
}
```

## Batch Operation Tests

```go
func TestBatchCreate_InsertsAll(t *testing.T) {
    pool, cleanup := testTx(t)
    defer cleanup()
    ctx := context.Background()
    repo := newTestRepo(t, pool)

    tenantID := uuid.New()
    widgets := make([]*widget.Widget, 50)
    for i := range widgets {
        widgets[i] = makeWidget(t, withTenant(tenantID), withName(fmt.Sprintf("batch-%03d", i)))
    }

    err := repo.BatchCreate(ctx, widgets)
    require.NoError(t, err)

    // Verify all were inserted
    result, err := repo.List(ctx, tenantID, domain.ListFilters{
        PageSize: 100, SortBy: "created_at", SortDir: "asc",
    })
    require.NoError(t, err)
    assert.Equal(t, 50, result.Total)
}

func TestBatchUpdate_UpdatesAllWithVersionCheck(t *testing.T) {
    pool, cleanup := testTx(t)
    defer cleanup()
    ctx := context.Background()
    repo := newTestRepo(t, pool)

    tenantID := uuid.New()
    w1 := makeWidget(t, withTenant(tenantID), withName("batch-1"))
    w2 := makeWidget(t, withTenant(tenantID), withName("batch-2"))
    seedWidgets(t, ctx, repo, w1, w2)

    // Update both
    now := time.Now().UTC().Truncate(time.Microsecond)
    w1.Name = "updated-1"
    w1.Version = 2
    w1.UpdatedAt = now
    w2.Name = "updated-2"
    w2.Version = 2
    w2.UpdatedAt = now

    err := repo.BatchUpdate(ctx, []*widget.Widget{w1, w2})
    require.NoError(t, err)

    // Verify
    got1, err := repo.GetByID(ctx, tenantID, w1.ID)
    require.NoError(t, err)
    assert.Equal(t, "updated-1", got1.Name)

    got2, err := repo.GetByID(ctx, tenantID, w2.ID)
    require.NoError(t, err)
    assert.Equal(t, "updated-2", got2.Name)
}
```

## Test Error Assertion Helpers

```go
func assertIsNotFoundError(t *testing.T, err error) {
    t.Helper()
    assert.Error(t, err)
    // Check for domain error type — adjust to match your apperr package
    assert.Contains(t, err.Error(), "not found",
        "expected NotFoundError, got: %v", err)
}

func assertIsConflictError(t *testing.T, err error) {
    t.Helper()
    assert.Error(t, err)
    assert.Contains(t, err.Error(), "conflict",
        "expected ConflictError, got: %v", err)
}
```

## Cache Integration Tests (Optional)

```go
// These tests verify the multi-level cache behavior when using a real Redis.
// Only run in CI environments with Redis available.

func TestCache_GetByID_CacheMissPopulatesL1(t *testing.T) {
    pool, cleanup := testTx(t)
    defer cleanup()
    ctx := context.Background()

    // Use in-memory Redis mock or real testcontainers Redis
    redis := newTestRedis(t)
    repo := NewWidgetRepo(pool, redis, testLogger())

    w := makeWidget(t)
    seedWidgets(t, ctx, repo, w)

    // First call: cache miss, queries DB, populates cache
    got1, err := repo.GetByID(ctx, w.TenantID, w.ID)
    require.NoError(t, err)
    assert.Equal(t, w.ID, got1.ID)

    // Second call: should hit L1 cache (no DB query)
    got2, err := repo.GetByID(ctx, w.TenantID, w.ID)
    require.NoError(t, err)
    assert.Equal(t, w.ID, got2.ID)
}

func TestCache_Update_InvalidatesCache(t *testing.T) {
    pool, cleanup := testTx(t)
    defer cleanup()
    ctx := context.Background()

    redis := newTestRedis(t)
    repo := NewWidgetRepo(pool, redis, testLogger())

    w := makeWidget(t)
    seedWidgets(t, ctx, repo, w)

    // Populate cache
    _, err := repo.GetByID(ctx, w.TenantID, w.ID)
    require.NoError(t, err)

    // Update invalidates cache
    w.Name = "Updated"
    w.Version = 2
    w.UpdatedAt = time.Now().UTC().Truncate(time.Microsecond)
    err = repo.Update(ctx, w)
    require.NoError(t, err)

    // Next read should go to DB (cache was invalidated)
    got, err := repo.GetByID(ctx, w.TenantID, w.ID)
    require.NoError(t, err)
    assert.Equal(t, "Updated", got.Name)
}
```

## Critical Rules

- TestMain MUST start a real PostgreSQL container — never mock the database in repository tests
- Every test MUST clean up its data (transaction rollback or truncation) for isolation
- Time values MUST be truncated to microseconds: `time.Now().UTC().Truncate(time.Microsecond)` (Postgres microsecond precision)
- Test factories MUST generate unique names/IDs to prevent constraint violations between tests
- Pagination tests MUST verify: item count, has_more flag, cursor presence, no duplicates between pages
- Tenant isolation tests MUST verify: GET returns NotFound, LIST returns empty, UPDATE fails, DELETE fails
- Optimistic locking tests MUST simulate two concurrent reads and verify second update fails
- Soft delete tests MUST verify: row exists with deleted_at set, but excluded from queries
- Error mapping tests MUST verify: unique violation -> ConflictError, no rows -> NotFoundError
- Batch operations MUST be tested with meaningful data volumes (10+ rows)
- Never use `t.Parallel()` for integration tests sharing the same database table — use sequential execution or per-test transactions
- Container cleanup MUST happen in TestMain deferred cleanup — never leave orphaned containers
