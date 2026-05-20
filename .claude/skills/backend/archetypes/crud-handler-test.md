---
skill: crud-handler-test
description: Go HTTP handler test archetype — httptest, chi router, JSON request/response validation, auth tests, error mapping, pagination, response envelope assertions
version: "1.0"
tags:
  - go
  - handler
  - http
  - unit-test
  - archetype
  - backend
  - testing
---

# CRUD Handler Test Archetype

Complete HTTP handler test template. Every generated handler test file MUST follow this pattern.

## Test File Location

```
internal/widget/
  handler.go           <- production code
  handler_test.go      <- THIS file
  mock_service.go      <- mock implementing Service interface
```

## Service Mock

```go
package widget

import (
    "context"

    "github.com/google/uuid"
    "github.com/stretchr/testify/mock"
    "yourapp/internal/domain"
)

type mockService struct {
    mock.Mock
}

func (m *mockService) Create(ctx context.Context, input CreateInput) (*Widget, error) {
    args := m.Called(ctx, input)
    if args.Get(0) == nil {
        return nil, args.Error(1)
    }
    return args.Get(0).(*Widget), args.Error(1)
}

func (m *mockService) Get(ctx context.Context, id uuid.UUID) (*Widget, error) {
    args := m.Called(ctx, id)
    if args.Get(0) == nil {
        return nil, args.Error(1)
    }
    return args.Get(0).(*Widget), args.Error(1)
}

func (m *mockService) Update(ctx context.Context, id uuid.UUID, input UpdateInput) (*Widget, error) {
    args := m.Called(ctx, id, input)
    if args.Get(0) == nil {
        return nil, args.Error(1)
    }
    return args.Get(0).(*Widget), args.Error(1)
}

func (m *mockService) Delete(ctx context.Context, id uuid.UUID) error {
    args := m.Called(ctx, id)
    return args.Error(0)
}

func (m *mockService) List(ctx context.Context, filters domain.ListFilters) (*domain.ListResult[Widget], error) {
    args := m.Called(ctx, filters)
    if args.Get(0) == nil {
        return nil, args.Error(1)
    }
    return args.Get(0).(*domain.ListResult[Widget]), args.Error(1)
}
```

## Test Setup and Helpers

```go
package widget

import (
    "bytes"
    "context"
    "encoding/json"
    "fmt"
    "io"
    "log/slog"
    "net/http"
    "net/http/httptest"
    "os"
    "testing"

    "github.com/go-chi/chi/v5"
    "github.com/google/uuid"
    "github.com/stretchr/testify/assert"
    "github.com/stretchr/testify/mock"
    "github.com/stretchr/testify/require"

    "yourapp/internal/apperr"
    "yourapp/internal/domain"
)

// testRouter creates a chi router with the handler mounted and auth middleware injected.
func testRouter(t *testing.T, svc Service) *chi.Mux {
    t.Helper()
    logger := slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: slog.LevelError}))
    h := NewHandler(svc, logger)

    r := chi.NewRouter()

    // Inject tenant/user/request-id context via test middleware
    r.Use(func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            ctx := r.Context()
            // Default test tenant/user — override per-test if needed
            if _, err := TenantIDFromContext(ctx); err != nil {
                ctx = context.WithValue(ctx, ctxKeyTenantID, uuid.MustParse("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))
                ctx = context.WithValue(ctx, ctxKeyUserID, uuid.MustParse("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"))
            }
            if RequestIDFromContext(ctx) == "" {
                ctx = context.WithValue(ctx, ctxKeyRequestID, "test-req-id")
            }
            next.ServeHTTP(w, r.WithContext(ctx))
        })
    })

    r.Mount("/api/v1/widgets", h.Routes())
    return r
}

// makeRequest constructs an HTTP request with optional JSON body and headers.
func makeRequest(t *testing.T, method, path string, body any, headers map[string]string) *http.Request {
    t.Helper()

    var bodyReader io.Reader
    if body != nil {
        data, err := json.Marshal(body)
        require.NoError(t, err)
        bodyReader = bytes.NewReader(data)
    }

    req := httptest.NewRequest(method, path, bodyReader)
    if body != nil {
        req.Header.Set("Content-Type", "application/json")
    }
    for k, v := range headers {
        req.Header.Set(k, v)
    }
    return req
}

// executeRequest sends a request through the router and returns the recorded response.
func executeRequest(t *testing.T, router http.Handler, req *http.Request) *httptest.ResponseRecorder {
    t.Helper()
    rr := httptest.NewRecorder()
    router.ServeHTTP(rr, req)
    return rr
}

// decodeResponse unmarshals the response body into the target struct.
func decodeResponse[T any](t *testing.T, resp *httptest.ResponseRecorder) T {
    t.Helper()
    var result T
    err := json.NewDecoder(resp.Body).Decode(&result)
    require.NoError(t, err, "failed to decode response body: %s", resp.Body.String())
    return result
}

// assertJSONResponse checks status code and returns the decoded envelope.
func assertJSONResponse(t *testing.T, resp *httptest.ResponseRecorder, wantStatus int) map[string]any {
    t.Helper()
    assert.Equal(t, wantStatus, resp.Code, "unexpected status code; body: %s", resp.Body.String())
    assert.Contains(t, resp.Header().Get("Content-Type"), "application/json")

    var result map[string]any
    err := json.NewDecoder(resp.Body).Decode(&result)
    require.NoError(t, err)
    return result
}

// assertErrorResponse checks the error envelope structure.
func assertErrorResponse(t *testing.T, resp *httptest.ResponseRecorder, wantStatus int, wantCode string) {
    t.Helper()
    result := assertJSONResponse(t, resp, wantStatus)

    errObj, ok := result["error"].(map[string]any)
    require.True(t, ok, "expected 'error' key in response")
    assert.Equal(t, wantCode, errObj["code"])
    assert.NotEmpty(t, errObj["message"])
}
```

## Create Handler Tests

```go
func TestCreateHandler_HappyPath(t *testing.T) {
    t.Parallel()

    svc := new(mockService)
    router := testRouter(t, svc)

    created := makeWidget(t, withName("New Widget"))
    svc.On("Create", mock.Anything, mock.AnythingOfType("widget.CreateInput")).
        Return(created, nil)

    body := map[string]any{
        "name":        "New Widget",
        "description": "A fine widget",
    }
    req := makeRequest(t, http.MethodPost, "/api/v1/widgets", body, nil)
    resp := executeRequest(t, router, req)

    // Assert status 201 Created
    result := assertJSONResponse(t, resp, http.StatusCreated)

    // Assert envelope structure: {"data": {...}, "meta": {...}}
    data, ok := result["data"].(map[string]any)
    require.True(t, ok, "expected 'data' key")
    assert.Equal(t, "New Widget", data["name"])

    meta, ok := result["meta"].(map[string]any)
    require.True(t, ok, "expected 'meta' key")
    assert.NotEmpty(t, meta["request_id"])
    assert.NotEmpty(t, meta["timestamp"])

    svc.AssertExpectations(t)
}

func TestCreateHandler_InvalidJSON(t *testing.T) {
    t.Parallel()

    svc := new(mockService)
    router := testRouter(t, svc)

    // Send malformed JSON
    req := httptest.NewRequest(http.MethodPost, "/api/v1/widgets",
        bytes.NewReader([]byte(`{invalid json`)))
    req.Header.Set("Content-Type", "application/json")
    resp := executeRequest(t, router, req)

    // Malformed JSON -> 400 Bad Request (not 422)
    assertErrorResponse(t, resp, http.StatusBadRequest, "BAD_REQUEST")
    svc.AssertNotCalled(t, "Create")
}

func TestCreateHandler_EmptyBody(t *testing.T) {
    t.Parallel()

    svc := new(mockService)
    router := testRouter(t, svc)

    req := httptest.NewRequest(http.MethodPost, "/api/v1/widgets", nil)
    req.Header.Set("Content-Type", "application/json")
    resp := executeRequest(t, router, req)

    // Empty body -> 400 Bad Request
    assert.Equal(t, http.StatusBadRequest, resp.Code)
    svc.AssertNotCalled(t, "Create")
}

func TestCreateHandler_ValidationError(t *testing.T) {
    t.Parallel()

    svc := new(mockService)
    router := testRouter(t, svc)

    // Valid JSON but fails service-level validation
    svc.On("Create", mock.Anything, mock.Anything).
        Return(nil, apperr.NewValidationError("name", fmt.Errorf("name is required")))

    body := map[string]any{"name": "", "description": "desc"}
    req := makeRequest(t, http.MethodPost, "/api/v1/widgets", body, nil)
    resp := executeRequest(t, router, req)

    assertErrorResponse(t, resp, http.StatusUnprocessableEntity, "VALIDATION_ERROR")
}
```

## Get Handler Tests

```go
func TestGetHandler_HappyPath(t *testing.T) {
    t.Parallel()

    svc := new(mockService)
    router := testRouter(t, svc)

    w := makeWidget(t)
    svc.On("Get", mock.Anything, w.ID).Return(w, nil)

    req := makeRequest(t, http.MethodGet, "/api/v1/widgets/"+w.ID.String(), nil, nil)
    resp := executeRequest(t, router, req)

    result := assertJSONResponse(t, resp, http.StatusOK)
    data := result["data"].(map[string]any)
    assert.Equal(t, w.ID.String(), data["id"])
}

func TestGetHandler_InvalidUUID(t *testing.T) {
    t.Parallel()

    svc := new(mockService)
    router := testRouter(t, svc)

    req := makeRequest(t, http.MethodGet, "/api/v1/widgets/not-a-uuid", nil, nil)
    resp := executeRequest(t, router, req)

    assertErrorResponse(t, resp, http.StatusUnprocessableEntity, "VALIDATION_ERROR")
    svc.AssertNotCalled(t, "Get")
}

func TestGetHandler_NotFound(t *testing.T) {
    t.Parallel()

    svc := new(mockService)
    router := testRouter(t, svc)

    id := uuid.New()
    svc.On("Get", mock.Anything, id).
        Return(nil, apperr.NewNotFoundError("widget", id.String()))

    req := makeRequest(t, http.MethodGet, "/api/v1/widgets/"+id.String(), nil, nil)
    resp := executeRequest(t, router, req)

    assertErrorResponse(t, resp, http.StatusNotFound, "NOT_FOUND")
}
```

## Update Handler Tests

```go
func TestUpdateHandler_HappyPath(t *testing.T) {
    t.Parallel()

    svc := new(mockService)
    router := testRouter(t, svc)

    w := makeWidget(t, withVersion(2))
    svc.On("Update", mock.Anything, w.ID, mock.AnythingOfType("widget.UpdateInput")).
        Return(w, nil)

    body := map[string]any{
        "name":        "Updated Name",
        "description": "Updated desc",
        "version":     1,
    }
    req := makeRequest(t, http.MethodPut, "/api/v1/widgets/"+w.ID.String(), body, nil)
    resp := executeRequest(t, router, req)

    result := assertJSONResponse(t, resp, http.StatusOK)
    data := result["data"].(map[string]any)
    assert.Equal(t, float64(2), data["version"])
}

func TestUpdateHandler_VersionConflict(t *testing.T) {
    t.Parallel()

    svc := new(mockService)
    router := testRouter(t, svc)

    id := uuid.New()
    svc.On("Update", mock.Anything, id, mock.Anything).
        Return(nil, apperr.NewConflictError("widget", "version mismatch"))

    body := map[string]any{
        "name":    "Updated",
        "version": 1,
    }
    req := makeRequest(t, http.MethodPut, "/api/v1/widgets/"+id.String(), body, nil)
    resp := executeRequest(t, router, req)

    assertErrorResponse(t, resp, http.StatusConflict, "CONFLICT")
}

func TestUpdateHandler_InvalidJSON(t *testing.T) {
    t.Parallel()

    svc := new(mockService)
    router := testRouter(t, svc)

    id := uuid.New()
    req := httptest.NewRequest(http.MethodPut, "/api/v1/widgets/"+id.String(),
        bytes.NewReader([]byte(`{bad`)))
    req.Header.Set("Content-Type", "application/json")
    resp := executeRequest(t, router, req)

    assertErrorResponse(t, resp, http.StatusBadRequest, "BAD_REQUEST")
    svc.AssertNotCalled(t, "Update")
}
```

## Delete Handler Tests

```go
func TestDeleteHandler_HappyPath(t *testing.T) {
    t.Parallel()

    svc := new(mockService)
    router := testRouter(t, svc)

    id := uuid.New()
    svc.On("Delete", mock.Anything, id).Return(nil)

    req := makeRequest(t, http.MethodDelete, "/api/v1/widgets/"+id.String(), nil, nil)
    resp := executeRequest(t, router, req)

    // DELETE returns 204 No Content with empty body
    assert.Equal(t, http.StatusNoContent, resp.Code)
    assert.Empty(t, resp.Body.String())
}

func TestDeleteHandler_NotFound(t *testing.T) {
    t.Parallel()

    svc := new(mockService)
    router := testRouter(t, svc)

    id := uuid.New()
    svc.On("Delete", mock.Anything, id).
        Return(apperr.NewNotFoundError("widget", id.String()))

    req := makeRequest(t, http.MethodDelete, "/api/v1/widgets/"+id.String(), nil, nil)
    resp := executeRequest(t, router, req)

    assertErrorResponse(t, resp, http.StatusNotFound, "NOT_FOUND")
}

func TestDeleteHandler_InvalidUUID(t *testing.T) {
    t.Parallel()

    svc := new(mockService)
    router := testRouter(t, svc)

    req := makeRequest(t, http.MethodDelete, "/api/v1/widgets/xyz", nil, nil)
    resp := executeRequest(t, router, req)

    assertErrorResponse(t, resp, http.StatusUnprocessableEntity, "VALIDATION_ERROR")
    svc.AssertNotCalled(t, "Delete")
}
```

## List Handler with Pagination Tests

```go
func TestListHandler_HappyPath(t *testing.T) {
    t.Parallel()

    svc := new(mockService)
    router := testRouter(t, svc)

    widgets := []Widget{*makeWidget(t), *makeWidget(t), *makeWidget(t)}
    svc.On("List", mock.Anything, mock.AnythingOfType("domain.ListFilters")).
        Return(&domain.ListResult[Widget]{
            Items:   widgets,
            Cursor:  "next-cursor-token",
            HasMore: true,
            Total:   25,
        }, nil)

    req := makeRequest(t, http.MethodGet, "/api/v1/widgets?page_size=3&sort_by=created_at&sort_dir=desc", nil, nil)
    resp := executeRequest(t, router, req)

    result := assertJSONResponse(t, resp, http.StatusOK)

    // Assert data array
    data, ok := result["data"].([]any)
    require.True(t, ok)
    assert.Len(t, data, 3)

    // Assert pagination meta
    meta, ok := result["meta"].(map[string]any)
    require.True(t, ok)
    assert.Equal(t, "next-cursor-token", meta["cursor"])
    assert.Equal(t, true, meta["has_more"])
    assert.Equal(t, float64(25), meta["total"])
    assert.NotEmpty(t, meta["request_id"])
    assert.NotEmpty(t, meta["timestamp"])
}

func TestListHandler_EmptyResults(t *testing.T) {
    t.Parallel()

    svc := new(mockService)
    router := testRouter(t, svc)

    svc.On("List", mock.Anything, mock.Anything).
        Return(&domain.ListResult[Widget]{
            Items:   []Widget{},
            HasMore: false,
            Total:   0,
        }, nil)

    req := makeRequest(t, http.MethodGet, "/api/v1/widgets", nil, nil)
    resp := executeRequest(t, router, req)

    result := assertJSONResponse(t, resp, http.StatusOK)

    data := result["data"].([]any)
    assert.Len(t, data, 0)

    meta := result["meta"].(map[string]any)
    assert.Equal(t, false, meta["has_more"])
    assert.Equal(t, float64(0), meta["total"])
}

func TestListHandler_NextPageWithCursor(t *testing.T) {
    t.Parallel()

    svc := new(mockService)
    router := testRouter(t, svc)

    svc.On("List", mock.Anything, mock.MatchedBy(func(f domain.ListFilters) bool {
        return f.Cursor == "some-cursor-token" && f.PageSize == 10
    })).Return(&domain.ListResult[Widget]{
        Items:   []Widget{*makeWidget(t)},
        HasMore: false,
        Total:   25,
    }, nil)

    req := makeRequest(t, http.MethodGet, "/api/v1/widgets?cursor=some-cursor-token&page_size=10", nil, nil)
    resp := executeRequest(t, router, req)

    result := assertJSONResponse(t, resp, http.StatusOK)
    meta := result["meta"].(map[string]any)
    assert.Equal(t, false, meta["has_more"])
}

func TestListHandler_PageSizeLimits(t *testing.T) {
    t.Parallel()

    tests := []struct {
        name         string
        queryParam   string
        wantPageSize int
    }{
        {"default when missing", "/api/v1/widgets", 20},
        {"default when zero", "/api/v1/widgets?page_size=0", 20},
        {"default when negative", "/api/v1/widgets?page_size=-5", 20},
        {"clamped to max 100", "/api/v1/widgets?page_size=500", 100},
        {"respects valid size", "/api/v1/widgets?page_size=50", 50},
    }

    for _, tt := range tests {
        tt := tt
        t.Run(tt.name, func(t *testing.T) {
            t.Parallel()

            svc := new(mockService)
            router := testRouter(t, svc)

            svc.On("List", mock.Anything, mock.MatchedBy(func(f domain.ListFilters) bool {
                return f.PageSize == tt.wantPageSize
            })).Return(&domain.ListResult[Widget]{Items: []Widget{}, Total: 0}, nil)

            req := makeRequest(t, http.MethodGet, tt.queryParam, nil, nil)
            resp := executeRequest(t, router, req)

            assert.Equal(t, http.StatusOK, resp.Code)
            svc.AssertExpectations(t)
        })
    }
}

func TestListHandler_FilterParams(t *testing.T) {
    t.Parallel()

    svc := new(mockService)
    router := testRouter(t, svc)

    svc.On("List", mock.Anything, mock.MatchedBy(func(f domain.ListFilters) bool {
        return f.Fields["status"] == "active" && f.Fields["priority"] == "high"
    })).Return(&domain.ListResult[Widget]{Items: []Widget{}, Total: 0}, nil)

    req := makeRequest(t, http.MethodGet,
        "/api/v1/widgets?filter[status]=active&filter[priority]=high", nil, nil)
    resp := executeRequest(t, router, req)

    assert.Equal(t, http.StatusOK, resp.Code)
    svc.AssertExpectations(t)
}

func TestListHandler_DisallowedFilterIgnored(t *testing.T) {
    t.Parallel()

    svc := new(mockService)
    router := testRouter(t, svc)

    svc.On("List", mock.Anything, mock.MatchedBy(func(f domain.ListFilters) bool {
        // "password" filter should NOT be passed through
        _, hasPassword := f.Fields["password"]
        return !hasPassword
    })).Return(&domain.ListResult[Widget]{Items: []Widget{}, Total: 0}, nil)

    req := makeRequest(t, http.MethodGet,
        "/api/v1/widgets?filter[password]=secret", nil, nil)
    resp := executeRequest(t, router, req)

    assert.Equal(t, http.StatusOK, resp.Code)
    svc.AssertExpectations(t)
}

func TestListHandler_SortValidation(t *testing.T) {
    t.Parallel()

    svc := new(mockService)
    router := testRouter(t, svc)

    // Unknown sort_by should default to "created_at"
    svc.On("List", mock.Anything, mock.MatchedBy(func(f domain.ListFilters) bool {
        return f.SortBy == "created_at" && f.SortDir == "desc"
    })).Return(&domain.ListResult[Widget]{Items: []Widget{}, Total: 0}, nil)

    req := makeRequest(t, http.MethodGet,
        "/api/v1/widgets?sort_by=drop_table&sort_dir=invalid", nil, nil)
    resp := executeRequest(t, router, req)

    assert.Equal(t, http.StatusOK, resp.Code)
    svc.AssertExpectations(t)
}
```

## Error Mapping Tests

```go
func TestErrorMapping_ServiceErrors(t *testing.T) {
    t.Parallel()

    tests := []struct {
        name       string
        serviceErr error
        wantStatus int
        wantCode   string
    }{
        {
            name:       "NotFound maps to 404",
            serviceErr: apperr.NewNotFoundError("widget", "123"),
            wantStatus: http.StatusNotFound,
            wantCode:   "NOT_FOUND",
        },
        {
            name:       "Conflict maps to 409",
            serviceErr: apperr.NewConflictError("widget", "version mismatch"),
            wantStatus: http.StatusConflict,
            wantCode:   "CONFLICT",
        },
        {
            name:       "ValidationError maps to 422",
            serviceErr: apperr.NewValidationError("name", fmt.Errorf("required")),
            wantStatus: http.StatusUnprocessableEntity,
            wantCode:   "VALIDATION_ERROR",
        },
        {
            name:       "Unauthorized maps to 401",
            serviceErr: apperr.NewUnauthorizedError("missing token"),
            wantStatus: http.StatusUnauthorized,
            wantCode:   "UNAUTHORIZED",
        },
        {
            name:       "Internal error maps to 500 with generic message",
            serviceErr: fmt.Errorf("unexpected: database connection pool exhausted"),
            wantStatus: http.StatusInternalServerError,
            wantCode:   "INTERNAL_ERROR",
        },
    }

    for _, tt := range tests {
        tt := tt
        t.Run(tt.name, func(t *testing.T) {
            t.Parallel()

            svc := new(mockService)
            router := testRouter(t, svc)

            id := uuid.New()
            svc.On("Get", mock.Anything, id).Return(nil, tt.serviceErr)

            req := makeRequest(t, http.MethodGet, "/api/v1/widgets/"+id.String(), nil, nil)
            resp := executeRequest(t, router, req)

            assertErrorResponse(t, resp, tt.wantStatus, tt.wantCode)

            // CRITICAL: Internal errors must NOT leak details to client
            if tt.wantStatus == http.StatusInternalServerError {
                body := resp.Body.String()
                assert.NotContains(t, body, "database connection pool")
                assert.NotContains(t, body, "unexpected")
            }
        })
    }
}
```

## Auth Tests

```go
func TestAuth_MissingTenantContext(t *testing.T) {
    t.Parallel()

    svc := new(mockService)
    logger := slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: slog.LevelError}))
    h := NewHandler(svc, logger)

    // Router WITHOUT auth middleware — no tenant in context
    r := chi.NewRouter()
    r.Mount("/api/v1/widgets", h.Routes())

    svc.On("Get", mock.Anything, mock.Anything).
        Return(nil, apperr.NewUnauthorizedError("missing tenant context"))

    id := uuid.New()
    req := makeRequest(t, http.MethodGet, "/api/v1/widgets/"+id.String(), nil, nil)
    resp := executeRequest(t, r, req)

    // Without tenant context, service returns Unauthorized
    assertErrorResponse(t, resp, http.StatusUnauthorized, "UNAUTHORIZED")
}

func TestAuth_WrongTenant_ReturnsNotFound_NotForbidden(t *testing.T) {
    t.Parallel()

    svc := new(mockService)
    router := testRouter(t, svc)

    id := uuid.New()
    // Service returns NotFound (not Forbidden) to prevent existence leaking
    svc.On("Get", mock.Anything, id).
        Return(nil, apperr.NewNotFoundError("widget", id.String()))

    req := makeRequest(t, http.MethodGet, "/api/v1/widgets/"+id.String(), nil, nil)
    resp := executeRequest(t, router, req)

    // CRITICAL: wrong tenant sees 404, not 403 — prevents enumeration attacks
    assertErrorResponse(t, resp, http.StatusNotFound, "NOT_FOUND")
}
```

## Response Shape Tests

```go
func TestResponseShape_SingleResource(t *testing.T) {
    t.Parallel()

    svc := new(mockService)
    router := testRouter(t, svc)

    w := makeWidget(t)
    svc.On("Get", mock.Anything, w.ID).Return(w, nil)

    req := makeRequest(t, http.MethodGet, "/api/v1/widgets/"+w.ID.String(), nil, nil)
    resp := executeRequest(t, router, req)

    result := assertJSONResponse(t, resp, http.StatusOK)

    // Must have exactly "data" and "meta" top-level keys
    assert.Contains(t, result, "data")
    assert.Contains(t, result, "meta")
    assert.Len(t, result, 2, "response should only have 'data' and 'meta' keys")

    // data must contain expected widget fields
    data := result["data"].(map[string]any)
    assert.Contains(t, data, "id")
    assert.Contains(t, data, "tenant_id")
    assert.Contains(t, data, "name")
    assert.Contains(t, data, "version")
    assert.Contains(t, data, "created_at")
    assert.Contains(t, data, "updated_at")

    // meta must contain request tracking fields
    meta := result["meta"].(map[string]any)
    assert.Contains(t, meta, "request_id")
    assert.Contains(t, meta, "timestamp")
}

func TestResponseShape_ListResource(t *testing.T) {
    t.Parallel()

    svc := new(mockService)
    router := testRouter(t, svc)

    svc.On("List", mock.Anything, mock.Anything).
        Return(&domain.ListResult[Widget]{
            Items:   []Widget{*makeWidget(t)},
            Cursor:  "abc",
            HasMore: true,
            Total:   10,
        }, nil)

    req := makeRequest(t, http.MethodGet, "/api/v1/widgets", nil, nil)
    resp := executeRequest(t, router, req)

    result := assertJSONResponse(t, resp, http.StatusOK)

    // Must have "data" (array) and "meta" top-level keys
    data, ok := result["data"].([]any)
    require.True(t, ok, "'data' must be an array")
    assert.Len(t, data, 1)

    meta := result["meta"].(map[string]any)
    assert.Contains(t, meta, "cursor")
    assert.Contains(t, meta, "has_more")
    assert.Contains(t, meta, "total")
    assert.Contains(t, meta, "request_id")
    assert.Contains(t, meta, "timestamp")
}

func TestResponseShape_ErrorResource(t *testing.T) {
    t.Parallel()

    svc := new(mockService)
    router := testRouter(t, svc)

    id := uuid.New()
    svc.On("Get", mock.Anything, id).
        Return(nil, apperr.NewNotFoundError("widget", id.String()))

    req := makeRequest(t, http.MethodGet, "/api/v1/widgets/"+id.String(), nil, nil)
    resp := executeRequest(t, router, req)

    result := assertJSONResponse(t, resp, http.StatusNotFound)

    // Error envelope: {"error": {"code": "...", "message": "..."}}
    errObj, ok := result["error"].(map[string]any)
    require.True(t, ok)
    assert.Contains(t, errObj, "code")
    assert.Contains(t, errObj, "message")
}
```

## Critical Rules

- Every handler test MUST use `httptest.NewRecorder` and chi router — no real HTTP server needed for unit tests
- Test middleware MUST inject tenant_id, user_id, request_id into context (mirrors production auth middleware)
- Malformed JSON MUST return 400 Bad Request, not 422 Validation Error
- Wrong tenant MUST return 404 Not Found, not 403 Forbidden — prevents entity enumeration
- Internal errors MUST NOT leak error details to the client — assert generic message in 500 responses
- Every response MUST follow the envelope format: `{"data": T, "meta": {...}}` for success, `{"error": {...}}` for failure
- DELETE MUST return 204 with empty body
- POST create MUST return 201 Created
- List responses MUST include `cursor`, `has_more`, `total` in meta
- Page size MUST be clamped: default to 20 when missing/zero, cap at 100
- Sort and filter fields MUST be allow-listed — disallowed values default to safe values
- Use `t.Parallel()` on every test function for speed
- Use `mock.MatchedBy(func)` to assert specific filter/input values reach the service
- Always call `svc.AssertExpectations(t)` or `svc.AssertNotCalled(t, method)` for unused methods
