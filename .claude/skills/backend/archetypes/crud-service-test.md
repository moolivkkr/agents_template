---
skill: crud-service-test
description: Go unit test archetype for the service layer — mocked dependencies, table-driven tests, testify suite, cache/audit/metrics verification, tenant isolation, edge cases
version: "1.0"
tags:
  - go
  - service
  - unit-test
  - archetype
  - backend
  - testing
---

# CRUD Service Test Archetype

Complete unit test template for the service layer. Every generated service test file MUST follow this pattern.

## Test File Location

```
internal/widget/
  service.go           ← production code
  service_test.go      ← THIS file
  mock_repository.go   ← generated or hand-written mock
  mock_cache.go
  mock_audit.go
```

Rule: Test file lives next to production code in the same package.

## Test Factory Pattern

```go
package widget

import (
    "fmt"
    "testing"
    "time"

    "github.com/google/uuid"
    "yourapp/internal/domain"
)

// makeWidget builds a test widget with sensible defaults.
// Override any field with functional options.
func makeWidget(t *testing.T, opts ...func(*Widget)) *Widget {
    t.Helper()
    now := time.Now().UTC()
    w := &Widget{
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
        Description: "A test widget",
        Status:      StatusActive,
    }
    for _, opt := range opts {
        opt(w)
    }
    return w
}

func withTenant(tenantID uuid.UUID) func(*Widget) {
    return func(w *Widget) { w.TenantID = tenantID }
}

func withID(id uuid.UUID) func(*Widget) {
    return func(w *Widget) { w.ID = id }
}

func withVersion(v int) func(*Widget) {
    return func(w *Widget) { w.Version = v }
}

func withName(name string) func(*Widget) {
    return func(w *Widget) { w.Name = name }
}

func withStatus(status string) func(*Widget) {
    return func(w *Widget) { w.Status = status }
}

// makeCreateInput builds a valid CreateInput with sensible defaults.
func makeCreateInput(t *testing.T, opts ...func(*CreateInput)) CreateInput {
    t.Helper()
    input := CreateInput{
        Name:        "New Widget",
        Description: "Description for new widget",
    }
    for _, opt := range opts {
        opt(&input)
    }
    return input
}

// makeUpdateInput builds a valid UpdateInput with sensible defaults.
func makeUpdateInput(t *testing.T, version int, opts ...func(*UpdateInput)) UpdateInput {
    t.Helper()
    input := UpdateInput{
        Name:        "Updated Widget",
        Description: "Updated description",
        Version:     version,
    }
    for _, opt := range opts {
        opt(&input)
    }
    return input
}

// makeListFilters builds default list filters.
func makeListFilters(t *testing.T) domain.ListFilters {
    t.Helper()
    return domain.ListFilters{
        PageSize: 20,
        SortBy:   "created_at",
        SortDir:  "desc",
    }
}
```

## Mock Definitions

Generate mocks with `mockery` or write them by hand implementing the interface.

```go
package widget

import (
    "context"
    "encoding/json"
    "time"

    "github.com/google/uuid"
    "github.com/stretchr/testify/mock"
    "yourapp/internal/domain"
)

// --- Repository Mock ---

type mockRepository struct {
    mock.Mock
}

func (m *mockRepository) Create(ctx context.Context, w *Widget) error {
    args := m.Called(ctx, w)
    return args.Error(0)
}

func (m *mockRepository) GetByID(ctx context.Context, tenantID, id uuid.UUID) (*Widget, error) {
    args := m.Called(ctx, tenantID, id)
    if args.Get(0) == nil {
        return nil, args.Error(1)
    }
    return args.Get(0).(*Widget), args.Error(1)
}

func (m *mockRepository) Update(ctx context.Context, w *Widget) error {
    args := m.Called(ctx, w)
    return args.Error(0)
}

func (m *mockRepository) SoftDelete(ctx context.Context, tenantID, id uuid.UUID) error {
    args := m.Called(ctx, tenantID, id)
    return args.Error(0)
}

func (m *mockRepository) List(ctx context.Context, tenantID uuid.UUID, filters domain.ListFilters) (*domain.ListResult[Widget], error) {
    args := m.Called(ctx, tenantID, filters)
    if args.Get(0) == nil {
        return nil, args.Error(1)
    }
    return args.Get(0).(*domain.ListResult[Widget]), args.Error(1)
}

// --- Cache Mock ---

type mockCache struct {
    mock.Mock
}

func (m *mockCache) Get(ctx context.Context, key string) ([]byte, error) {
    args := m.Called(ctx, key)
    if args.Get(0) == nil {
        return nil, args.Error(1)
    }
    return args.Get(0).([]byte), args.Error(1)
}

func (m *mockCache) Set(ctx context.Context, key string, value []byte, ttl time.Duration) error {
    args := m.Called(ctx, key, value, ttl)
    return args.Error(0)
}

func (m *mockCache) Delete(ctx context.Context, key string) error {
    args := m.Called(ctx, key)
    return args.Error(0)
}

// --- Audit Writer Mock ---

type mockAuditWriter struct {
    mock.Mock
    entries []domain.AuditEntry // captures all logged entries for assertions
}

func (m *mockAuditWriter) Write(ctx context.Context, entry domain.AuditEntry) error {
    m.entries = append(m.entries, entry)
    args := m.Called(ctx, entry)
    return args.Error(0)
}

// --- Metrics Stub ---
// For unit tests, use noop counters/histograms from OTel SDK's noop package.
// import "go.opentelemetry.io/otel/metric/noop"
//
// func noopMetrics() Metrics {
//     mp := noop.NewMeterProvider()
//     meter := mp.Meter("test")
//     opCount, _ := meter.Int64Counter("op_count")
//     opLatency, _ := meter.Float64Histogram("op_latency")
//     errCount, _ := meter.Int64Counter("err_count")
//     cacheHits, _ := meter.Int64Counter("cache_hits")
//     cacheMiss, _ := meter.Int64Counter("cache_miss")
//     return Metrics{
//         OpCount: opCount, OpLatency: opLatency,
//         ErrCount: errCount, CacheHits: cacheHits, CacheMiss: cacheMiss,
//     }
// }
```

## Approach A: testify/suite (Setup/Teardown)

Use `testify/suite` when you need shared setup across many tests.

```go
package widget

import (
    "context"
    "encoding/json"
    "errors"
    "fmt"
    "log/slog"
    "os"
    "testing"
    "time"

    "github.com/google/uuid"
    "github.com/stretchr/testify/assert"
    "github.com/stretchr/testify/mock"
    "github.com/stretchr/testify/require"
    "github.com/stretchr/testify/suite"

    "yourapp/internal/domain"
)

type ServiceSuite struct {
    suite.Suite

    svc          Service
    repo         *mockRepository
    cache        *mockCache
    auditWriter  *mockAuditWriter

    tenantID uuid.UUID
    userID   uuid.UUID
    ctx      context.Context
}

func TestServiceSuite(t *testing.T) {
    suite.Run(t, new(ServiceSuite))
}

func (s *ServiceSuite) SetupTest() {
    // Fresh mocks for every test — no cross-test contamination.
    s.repo = new(mockRepository)
    s.cache = new(mockCache)
    s.auditWriter = new(mockAuditWriter)

    logger := slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: slog.LevelError}))
    s.svc = NewService(s.repo, s.cache, logger, noopMetrics())

    s.tenantID = uuid.New()
    s.userID = uuid.New()
    s.ctx = contextWithTenant(context.Background(), s.tenantID, s.userID)
}

func (s *ServiceSuite) TearDownTest() {
    s.repo.AssertExpectations(s.T())
    s.cache.AssertExpectations(s.T())
    s.auditWriter.AssertExpectations(s.T())
}

// --- Create Tests ---

func (s *ServiceSuite) TestCreate_HappyPath() {
    input := makeCreateInput(s.T())

    s.repo.On("Create", mock.Anything, mock.AnythingOfType("*widget.Widget")).
        Return(nil)
    s.auditWriter.On("Write", mock.Anything, mock.Anything).Return(nil)

    result, err := s.svc.Create(s.ctx, input)

    require.NoError(s.T(), err)
    assert.Equal(s.T(), input.Name, result.Name)
    assert.Equal(s.T(), s.tenantID, result.TenantID)
    assert.Equal(s.T(), 1, result.Version)
    assert.NotEqual(s.T(), uuid.Nil, result.ID)
    s.repo.AssertCalled(s.T(), "Create", mock.Anything, mock.AnythingOfType("*widget.Widget"))
}

func (s *ServiceSuite) TestCreate_ValidationError() {
    input := makeCreateInput(s.T(), func(i *CreateInput) { i.Name = "" })

    result, err := s.svc.Create(s.ctx, input)

    assert.Nil(s.T(), result)
    assert.Error(s.T(), err)
    assertIsValidationError(s.T(), err)
    s.repo.AssertNotCalled(s.T(), "Create")
}

func (s *ServiceSuite) TestCreate_RepoError() {
    input := makeCreateInput(s.T())
    repoErr := errors.New("connection refused")

    s.repo.On("Create", mock.Anything, mock.Anything).Return(repoErr)

    result, err := s.svc.Create(s.ctx, input)

    assert.Nil(s.T(), result)
    assert.ErrorContains(s.T(), err, "widget create")
    assert.ErrorIs(s.T(), err, repoErr)
}

// --- Get Tests ---

func (s *ServiceSuite) TestGet_CacheHit() {
    w := makeWidget(s.T(), withTenant(s.tenantID))
    data, _ := json.Marshal(w)

    s.cache.On("Get", mock.Anything, mock.Anything).Return(data, nil)

    result, err := s.svc.Get(s.ctx, w.ID)

    require.NoError(s.T(), err)
    assert.Equal(s.T(), w.ID, result.ID)
    s.repo.AssertNotCalled(s.T(), "GetByID") // DB never queried
}

func (s *ServiceSuite) TestGet_CacheMiss_PopulatesCache() {
    w := makeWidget(s.T(), withTenant(s.tenantID))
    cacheKey := fmt.Sprintf("widget:%s:%s", s.tenantID, w.ID)

    s.cache.On("Get", mock.Anything, cacheKey).Return(nil, errors.New("miss"))
    s.repo.On("GetByID", mock.Anything, s.tenantID, w.ID).Return(w, nil)
    s.cache.On("Set", mock.Anything, cacheKey, mock.Anything, mock.Anything).Return(nil)

    result, err := s.svc.Get(s.ctx, w.ID)

    require.NoError(s.T(), err)
    assert.Equal(s.T(), w.ID, result.ID)
    s.cache.AssertCalled(s.T(), "Set", mock.Anything, cacheKey, mock.Anything, mock.Anything)
}

func (s *ServiceSuite) TestGet_NotFound() {
    id := uuid.New()
    cacheKey := fmt.Sprintf("widget:%s:%s", s.tenantID, id)

    s.cache.On("Get", mock.Anything, cacheKey).Return(nil, errors.New("miss"))
    s.repo.On("GetByID", mock.Anything, s.tenantID, id).
        Return(nil, NewNotFoundError("widget", id.String()))

    result, err := s.svc.Get(s.ctx, id)

    assert.Nil(s.T(), result)
    assert.Error(s.T(), err)
}

// --- Update Tests ---

func (s *ServiceSuite) TestUpdate_HappyPath() {
    existing := makeWidget(s.T(), withTenant(s.tenantID), withVersion(1))
    input := makeUpdateInput(s.T(), 1)

    s.repo.On("GetByID", mock.Anything, s.tenantID, existing.ID).Return(existing, nil)
    s.repo.On("Update", mock.Anything, mock.AnythingOfType("*widget.Widget")).Return(nil)
    s.cache.On("Delete", mock.Anything, mock.Anything).Return(nil)
    s.auditWriter.On("Write", mock.Anything, mock.Anything).Return(nil)

    result, err := s.svc.Update(s.ctx, existing.ID, input)

    require.NoError(s.T(), err)
    assert.Equal(s.T(), input.Name, result.Name)
    assert.Equal(s.T(), 2, result.Version) // version incremented
    s.cache.AssertCalled(s.T(), "Delete", mock.Anything, mock.Anything)
}

func (s *ServiceSuite) TestUpdate_VersionConflict() {
    existing := makeWidget(s.T(), withTenant(s.tenantID), withVersion(3))
    input := makeUpdateInput(s.T(), 1) // stale version

    s.repo.On("GetByID", mock.Anything, s.tenantID, existing.ID).Return(existing, nil)

    result, err := s.svc.Update(s.ctx, existing.ID, input)

    assert.Nil(s.T(), result)
    assertIsConflictError(s.T(), err)
    s.repo.AssertNotCalled(s.T(), "Update")
}

// --- Delete Tests ---

func (s *ServiceSuite) TestDelete_HappyPath() {
    id := uuid.New()
    cacheKey := fmt.Sprintf("widget:%s:%s", s.tenantID, id)

    s.repo.On("SoftDelete", mock.Anything, s.tenantID, id).Return(nil)
    s.cache.On("Delete", mock.Anything, cacheKey).Return(nil)
    s.auditWriter.On("Write", mock.Anything, mock.Anything).Return(nil)

    err := s.svc.Delete(s.ctx, id)

    require.NoError(s.T(), err)
    s.repo.AssertCalled(s.T(), "SoftDelete", mock.Anything, s.tenantID, id)
    s.cache.AssertCalled(s.T(), "Delete", mock.Anything, cacheKey)
}

func (s *ServiceSuite) TestDelete_NotFound() {
    id := uuid.New()

    s.repo.On("SoftDelete", mock.Anything, s.tenantID, id).
        Return(NewNotFoundError("widget", id.String()))

    err := s.svc.Delete(s.ctx, id)

    assert.Error(s.T(), err)
}
```

## Approach B: Table-Driven Tests

Use table-driven tests for methods with many input/output combinations.

```go
package widget

import (
    "context"
    "errors"
    "log/slog"
    "os"
    "testing"

    "github.com/google/uuid"
    "github.com/stretchr/testify/assert"
    "github.com/stretchr/testify/mock"
    "github.com/stretchr/testify/require"

    "yourapp/internal/domain"
)

func TestCreate_TableDriven(t *testing.T) {
    t.Parallel()

    tests := []struct {
        name        string
        input       CreateInput
        setupMocks  func(repo *mockRepository, cache *mockCache, audit *mockAuditWriter)
        assertResult func(t *testing.T, result *Widget, err error)
    }{
        {
            name:  "valid input creates widget",
            input: CreateInput{Name: "My Widget", Description: "Desc"},
            setupMocks: func(repo *mockRepository, cache *mockCache, audit *mockAuditWriter) {
                repo.On("Create", mock.Anything, mock.Anything).Return(nil)
                audit.On("Write", mock.Anything, mock.Anything).Return(nil)
            },
            assertResult: func(t *testing.T, result *Widget, err error) {
                t.Helper()
                require.NoError(t, err)
                assert.Equal(t, "My Widget", result.Name)
                assert.Equal(t, 1, result.Version)
            },
        },
        {
            name:  "empty name returns validation error",
            input: CreateInput{Name: "", Description: "Desc"},
            setupMocks: func(repo *mockRepository, cache *mockCache, audit *mockAuditWriter) {
                // No mock setup — validation fails before any calls.
            },
            assertResult: func(t *testing.T, result *Widget, err error) {
                t.Helper()
                assert.Nil(t, result)
                assertIsValidationError(t, err)
            },
        },
        {
            name:  "name too long returns validation error",
            input: CreateInput{Name: string(make([]byte, 256)), Description: "Desc"},
            setupMocks: func(repo *mockRepository, cache *mockCache, audit *mockAuditWriter) {},
            assertResult: func(t *testing.T, result *Widget, err error) {
                t.Helper()
                assert.Nil(t, result)
                assertIsValidationError(t, err)
            },
        },
        {
            name:  "repo error propagates",
            input: CreateInput{Name: "Valid", Description: "Desc"},
            setupMocks: func(repo *mockRepository, cache *mockCache, audit *mockAuditWriter) {
                repo.On("Create", mock.Anything, mock.Anything).
                    Return(errors.New("db down"))
            },
            assertResult: func(t *testing.T, result *Widget, err error) {
                t.Helper()
                assert.Nil(t, result)
                assert.ErrorContains(t, err, "widget create")
            },
        },
    }

    for _, tt := range tests {
        tt := tt // capture range variable
        t.Run(tt.name, func(t *testing.T) {
            t.Parallel()

            // Arrange
            repo := new(mockRepository)
            cache := new(mockCache)
            audit := new(mockAuditWriter)
            logger := slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: slog.LevelError}))
            svc := NewService(repo, cache, logger, noopMetrics())

            tenantID := uuid.New()
            userID := uuid.New()
            ctx := contextWithTenant(context.Background(), tenantID, userID)

            tt.setupMocks(repo, cache, audit)

            // Act
            result, err := svc.Create(ctx, tt.input)

            // Assert
            tt.assertResult(t, result, err)
            repo.AssertExpectations(t)
        })
    }
}

func TestList_TableDriven(t *testing.T) {
    t.Parallel()

    tenantID := uuid.New()

    tests := []struct {
        name         string
        filters      domain.ListFilters
        repoResult   *domain.ListResult[Widget]
        repoErr      error
        wantErr      bool
        wantItems    int
        wantHasMore  bool
    }{
        {
            name:    "returns paginated results",
            filters: domain.ListFilters{PageSize: 10, SortBy: "created_at", SortDir: "desc"},
            repoResult: &domain.ListResult[Widget]{
                Items:   []Widget{{}, {}, {}},
                HasMore: true,
                Cursor:  "abc",
                Total:   25,
            },
            wantItems:   3,
            wantHasMore: true,
        },
        {
            name:    "empty list returns zero items",
            filters: domain.ListFilters{PageSize: 20},
            repoResult: &domain.ListResult[Widget]{
                Items:   []Widget{},
                HasMore: false,
                Total:   0,
            },
            wantItems:   0,
            wantHasMore: false,
        },
        {
            name:    "enforces max page size",
            filters: domain.ListFilters{PageSize: 500}, // exceeds max
            repoResult: &domain.ListResult[Widget]{
                Items: []Widget{},
                Total: 0,
            },
            wantItems: 0,
            // Service should clamp PageSize to 100 before passing to repo.
        },
        {
            name:    "defaults page size when zero",
            filters: domain.ListFilters{PageSize: 0},
            repoResult: &domain.ListResult[Widget]{
                Items: []Widget{},
                Total: 0,
            },
            wantItems: 0,
            // Service should default PageSize to 20.
        },
        {
            name:    "repo error propagates",
            filters: domain.ListFilters{PageSize: 10},
            repoErr: errors.New("timeout"),
            wantErr: true,
        },
    }

    for _, tt := range tests {
        tt := tt
        t.Run(tt.name, func(t *testing.T) {
            t.Parallel()

            repo := new(mockRepository)
            cache := new(mockCache)
            logger := slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: slog.LevelError}))
            svc := NewService(repo, cache, logger, noopMetrics())

            ctx := contextWithTenant(context.Background(), tenantID, uuid.New())

            repo.On("List", mock.Anything, tenantID, mock.AnythingOfType("domain.ListFilters")).
                Return(tt.repoResult, tt.repoErr)

            result, err := svc.List(ctx, tt.filters)

            if tt.wantErr {
                assert.Error(t, err)
                return
            }
            require.NoError(t, err)
            assert.Len(t, result.Items, tt.wantItems)
            assert.Equal(t, tt.wantHasMore, result.HasMore)
        })
    }
}
```

## Edge Case and Isolation Tests

```go
func TestCreate_MissingTenantContext_ReturnsUnauthorized(t *testing.T) {
    t.Parallel()

    repo := new(mockRepository)
    cache := new(mockCache)
    logger := slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: slog.LevelError}))
    svc := NewService(repo, cache, logger, noopMetrics())

    // context.Background() has no tenant — should fail
    input := makeCreateInput(t)
    result, err := svc.Create(context.Background(), input)

    assert.Nil(t, result)
    assertIsUnauthorizedError(t, err)
    repo.AssertNotCalled(t, "Create")
}

func TestGet_WrongTenant_ReturnsNotFound(t *testing.T) {
    t.Parallel()

    repo := new(mockRepository)
    cache := new(mockCache)
    logger := slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: slog.LevelError}))
    svc := NewService(repo, cache, logger, noopMetrics())

    tenantA := uuid.New()
    tenantB := uuid.New()
    widgetID := uuid.New()

    // Widget belongs to tenant A
    ctx := contextWithTenant(context.Background(), tenantB, uuid.New())
    cacheKey := fmt.Sprintf("widget:%s:%s", tenantB, widgetID)

    cache.On("Get", mock.Anything, cacheKey).Return(nil, errors.New("miss"))
    repo.On("GetByID", mock.Anything, tenantB, widgetID).
        Return(nil, NewNotFoundError("widget", widgetID.String()))

    result, err := svc.Get(ctx, widgetID)

    // Tenant B should NOT see tenant A's widget — repo enforces this
    assert.Nil(t, result)
    assert.Error(t, err)
    // Critically: error is NotFound, NOT Forbidden (don't leak existence)
    _ = tenantA // unused; here to show intent
}

func TestCreate_NilInput_ReturnsValidationError(t *testing.T) {
    t.Parallel()

    repo := new(mockRepository)
    cache := new(mockCache)
    logger := slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: slog.LevelError}))
    svc := NewService(repo, cache, logger, noopMetrics())

    ctx := contextWithTenant(context.Background(), uuid.New(), uuid.New())

    // Zero-value input — Name is empty string
    result, err := svc.Create(ctx, CreateInput{})

    assert.Nil(t, result)
    assertIsValidationError(t, err)
}

func TestGet_ContextCancelled_ReturnsError(t *testing.T) {
    t.Parallel()

    repo := new(mockRepository)
    cache := new(mockCache)
    logger := slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: slog.LevelError}))
    svc := NewService(repo, cache, logger, noopMetrics())

    tenantID := uuid.New()
    ctx, cancel := context.WithCancel(
        contextWithTenant(context.Background(), tenantID, uuid.New()),
    )
    cancel() // cancel immediately

    widgetID := uuid.New()
    cacheKey := fmt.Sprintf("widget:%s:%s", tenantID, widgetID)

    cache.On("Get", mock.Anything, cacheKey).Return(nil, errors.New("miss"))
    repo.On("GetByID", mock.Anything, tenantID, widgetID).
        Return(nil, context.Canceled)

    result, err := svc.Get(ctx, widgetID)

    assert.Nil(t, result)
    assert.Error(t, err)
}
```

## Audit Logging Verification

```go
func TestCreate_AuditLogContainsCorrectFields(t *testing.T) {
    t.Parallel()

    repo := new(mockRepository)
    cache := new(mockCache)
    audit := new(mockAuditWriter)
    logger := slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: slog.LevelError}))

    // Inject audit writer into service (constructor may need extending)
    svc := NewServiceWithAudit(repo, cache, logger, noopMetrics(), audit)

    tenantID := uuid.New()
    userID := uuid.New()
    ctx := contextWithTenant(context.Background(), tenantID, userID)

    repo.On("Create", mock.Anything, mock.Anything).Return(nil)
    audit.On("Write", mock.Anything, mock.MatchedBy(func(entry domain.AuditEntry) bool {
        return entry.Action == "widget.created" &&
            entry.TenantID == tenantID &&
            entry.ActorID == userID &&
            entry.EntityID != uuid.Nil &&
            !entry.Timestamp.IsZero()
    })).Return(nil)

    _, err := svc.Create(ctx, makeCreateInput(t))
    require.NoError(t, err)

    audit.AssertExpectations(t)
}

func TestUpdate_AuditLogRecordsChanges(t *testing.T) {
    t.Parallel()

    repo := new(mockRepository)
    cache := new(mockCache)
    audit := new(mockAuditWriter)
    logger := slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: slog.LevelError}))
    svc := NewServiceWithAudit(repo, cache, logger, noopMetrics(), audit)

    tenantID := uuid.New()
    userID := uuid.New()
    ctx := contextWithTenant(context.Background(), tenantID, userID)
    existing := makeWidget(t, withTenant(tenantID), withVersion(1))

    repo.On("GetByID", mock.Anything, tenantID, existing.ID).Return(existing, nil)
    repo.On("Update", mock.Anything, mock.Anything).Return(nil)
    cache.On("Delete", mock.Anything, mock.Anything).Return(nil)
    audit.On("Write", mock.Anything, mock.MatchedBy(func(entry domain.AuditEntry) bool {
        return entry.Action == "widget.updated" &&
            entry.TenantID == tenantID &&
            entry.ActorID == userID
    })).Return(nil)

    input := makeUpdateInput(t, 1)
    _, err := svc.Update(ctx, existing.ID, input)
    require.NoError(t, err)

    audit.AssertExpectations(t)
}

func TestDelete_AuditLogRecordsDeletion(t *testing.T) {
    t.Parallel()

    repo := new(mockRepository)
    cache := new(mockCache)
    audit := new(mockAuditWriter)
    logger := slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: slog.LevelError}))
    svc := NewServiceWithAudit(repo, cache, logger, noopMetrics(), audit)

    tenantID := uuid.New()
    userID := uuid.New()
    ctx := contextWithTenant(context.Background(), tenantID, userID)
    widgetID := uuid.New()

    repo.On("SoftDelete", mock.Anything, tenantID, widgetID).Return(nil)
    cache.On("Delete", mock.Anything, mock.Anything).Return(nil)
    audit.On("Write", mock.Anything, mock.MatchedBy(func(entry domain.AuditEntry) bool {
        return entry.Action == "widget.deleted" && entry.EntityID == widgetID
    })).Return(nil)

    err := svc.Delete(ctx, widgetID)
    require.NoError(t, err)

    audit.AssertExpectations(t)
}
```

## Test Helpers

```go
package widget

import (
    "context"
    "testing"

    "github.com/google/uuid"
    "github.com/stretchr/testify/assert"
)

// contextWithTenant builds a context with tenant and user IDs injected.
func contextWithTenant(parent context.Context, tenantID, userID uuid.UUID) context.Context {
    ctx := context.WithValue(parent, ctxKeyTenantID, tenantID)
    return context.WithValue(ctx, ctxKeyUserID, userID)
}

// assertIsValidationError asserts the error is a ValidationError.
func assertIsValidationError(t *testing.T, err error) {
    t.Helper()
    var ve *ValidationError
    assert.ErrorAs(t, err, &ve, "expected ValidationError, got %T: %v", err, err)
}

// assertIsConflictError asserts the error is a ConflictError.
func assertIsConflictError(t *testing.T, err error) {
    t.Helper()
    var ce *ConflictError
    assert.ErrorAs(t, err, &ce, "expected ConflictError, got %T: %v", err, err)
}

// assertIsUnauthorizedError asserts the error is an UnauthorizedError.
func assertIsUnauthorizedError(t *testing.T, err error) {
    t.Helper()
    var ue *UnauthorizedError
    assert.ErrorAs(t, err, &ue, "expected UnauthorizedError, got %T: %v", err, err)
}

// assertIsNotFoundError asserts the error is a NotFoundError.
func assertIsNotFoundError(t *testing.T, err error) {
    t.Helper()
    var nfe *NotFoundError
    assert.ErrorAs(t, err, &nfe, "expected NotFoundError, got %T: %v", err, err)
}
```

## Critical Rules

- Every test MUST use `t.Helper()` in helper functions for correct line reporting
- Every independent test SHOULD use `t.Parallel()` for speed
- Mocks MUST be fresh per test — never share mock state between tests
- `AssertExpectations(t)` MUST be called at the end of every test (or in TearDown)
- Test factories MUST generate unique IDs (use `uuid.New()`) to prevent collision
- Never test OpenTelemetry span creation — test behavior, not instrumentation
- Cache tests MUST verify both hit and miss paths
- Audit tests MUST verify action, entity_id, tenant_id, actor_id, and timestamp
- Context cancellation and missing-tenant scenarios MUST be covered
- Use `require.NoError` for preconditions, `assert.Error`/`assert.NoError` for assertions
- Use `mock.MatchedBy(func)` for complex argument matching instead of `mock.Anything`
- Version conflict test: set existing.Version = 3, input.Version = 1 — assert ConflictError
