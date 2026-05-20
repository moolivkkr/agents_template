---
skill: crud-handler
description: Go HTTP handler archetype — chi router, JSON request/response, cursor pagination, error mapping, OpenTelemetry, structured logging
version: "1.0"
tags:
  - go
  - handler
  - http
  - chi
  - archetype
  - backend
---

# CRUD Handler Archetype

Complete HTTP handler set for chi router. Every generated handler MUST follow this pattern.

## Handler Struct and Constructor

```go
package widget

import (
    "encoding/json"
    "log/slog"
    "net/http"
    "strconv"

    "github.com/go-chi/chi/v5"
    "github.com/google/uuid"
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/attribute"
    "go.opentelemetry.io/otel/trace"

    "yourapp/internal/domain"
    "yourapp/internal/apperr"
)

type Handler struct {
    svc    Service
    logger *slog.Logger
    tracer trace.Tracer
}

func NewHandler(svc Service, logger *slog.Logger) *Handler {
    return &Handler{
        svc:    svc,
        logger: logger.With("handler", "widget"),
        tracer: otel.Tracer("widget-handler"),
    }
}
```

## Route Registration

```go
// Routes returns a chi.Router with all widget endpoints mounted.
// Mount this into the main router: r.Mount("/api/v1/widgets", widgetHandler.Routes())
func (h *Handler) Routes() chi.Router {
    r := chi.NewRouter()

    r.Post("/", h.Create)
    r.Get("/", h.List)
    r.Route("/{id}", func(r chi.Router) {
        r.Get("/", h.Get)
        r.Put("/", h.Update)
        r.Delete("/", h.Delete)
    })

    return r
}
```

## Response Envelope Types

```go
// Envelope wraps a single resource response.
type Envelope[T any] struct {
    Data T    `json:"data"`
    Meta Meta `json:"meta"`
}

// ListEnvelope wraps a paginated list response.
type ListEnvelope[T any] struct {
    Data []T      `json:"data"`
    Meta ListMeta `json:"meta"`
}

type Meta struct {
    RequestID string `json:"request_id"`
    Timestamp string `json:"timestamp"`
}

type ListMeta struct {
    Cursor  string `json:"cursor,omitempty"`
    HasMore bool   `json:"has_more"`
    Total   int    `json:"total"`
    RequestID string `json:"request_id"`
    Timestamp string `json:"timestamp"`
}

// ErrorBody is the standard error response format.
type ErrorBody struct {
    Error ErrorDetail `json:"error"`
}

type ErrorDetail struct {
    Code    string         `json:"code"`
    Message string         `json:"message"`
    Details map[string]any `json:"details,omitempty"`
}
```

## Create Handler

```go
func (h *Handler) Create(w http.ResponseWriter, r *http.Request) {
    ctx, span := h.tracer.Start(r.Context(), "handler.widget.create")
    defer span.End()

    reqID := RequestIDFromContext(ctx)
    logger := h.logger.With("request_id", reqID, "method", "Create")

    // 1. Decode request body
    var input CreateInput
    if err := decodeJSON(r, &input); err != nil {
        logger.WarnContext(ctx, "invalid request body", "error", err)
        writeError(w, apperr.NewValidationError("body", err))
        return
    }

    // 2. Sanitize inputs
    input.Sanitize()

    // 3. Call service
    result, err := h.svc.Create(ctx, input)
    if err != nil {
        logger.ErrorContext(ctx, "create failed", "error", err)
        writeError(w, err)
        return
    }

    // 4. Return response
    span.SetAttributes(attribute.String("widget.id", result.ID.String()))
    writeJSON(w, http.StatusCreated, Envelope[*Widget]{
        Data: result,
        Meta: newMeta(reqID),
    })
}
```

## Get Handler

```go
func (h *Handler) Get(w http.ResponseWriter, r *http.Request) {
    ctx, span := h.tracer.Start(r.Context(), "handler.widget.get")
    defer span.End()

    reqID := RequestIDFromContext(ctx)
    logger := h.logger.With("request_id", reqID, "method", "Get")

    // 1. Parse path parameter
    id, err := parseUUID(chi.URLParam(r, "id"))
    if err != nil {
        writeError(w, apperr.NewValidationError("id", err))
        return
    }

    // 2. Call service
    result, err := h.svc.Get(ctx, id)
    if err != nil {
        logger.ErrorContext(ctx, "get failed", "widget_id", id, "error", err)
        writeError(w, err)
        return
    }

    writeJSON(w, http.StatusOK, Envelope[*Widget]{
        Data: result,
        Meta: newMeta(reqID),
    })
}
```

## Update Handler

```go
func (h *Handler) Update(w http.ResponseWriter, r *http.Request) {
    ctx, span := h.tracer.Start(r.Context(), "handler.widget.update")
    defer span.End()

    reqID := RequestIDFromContext(ctx)
    logger := h.logger.With("request_id", reqID, "method", "Update")

    // 1. Parse path parameter
    id, err := parseUUID(chi.URLParam(r, "id"))
    if err != nil {
        writeError(w, apperr.NewValidationError("id", err))
        return
    }

    // 2. Decode request body
    var input UpdateInput
    if err := decodeJSON(r, &input); err != nil {
        logger.WarnContext(ctx, "invalid request body", "error", err)
        writeError(w, apperr.NewValidationError("body", err))
        return
    }

    input.Sanitize()

    // 3. Call service
    result, err := h.svc.Update(ctx, id, input)
    if err != nil {
        logger.ErrorContext(ctx, "update failed", "widget_id", id, "error", err)
        writeError(w, err)
        return
    }

    writeJSON(w, http.StatusOK, Envelope[*Widget]{
        Data: result,
        Meta: newMeta(reqID),
    })
}
```

## Delete Handler

```go
func (h *Handler) Delete(w http.ResponseWriter, r *http.Request) {
    ctx, span := h.tracer.Start(r.Context(), "handler.widget.delete")
    defer span.End()

    reqID := RequestIDFromContext(ctx)
    logger := h.logger.With("request_id", reqID, "method", "Delete")

    // 1. Parse path parameter
    id, err := parseUUID(chi.URLParam(r, "id"))
    if err != nil {
        writeError(w, apperr.NewValidationError("id", err))
        return
    }

    // 2. Call service
    if err := h.svc.Delete(ctx, id); err != nil {
        logger.ErrorContext(ctx, "delete failed", "widget_id", id, "error", err)
        writeError(w, err)
        return
    }

    w.WriteHeader(http.StatusNoContent)
}
```

## List Handler with Cursor Pagination and Filters

```go
func (h *Handler) List(w http.ResponseWriter, r *http.Request) {
    ctx, span := h.tracer.Start(r.Context(), "handler.widget.list")
    defer span.End()

    reqID := RequestIDFromContext(ctx)

    // 1. Parse pagination and filter params from query string
    filters := parseListFilters(r)

    // 2. Call service
    result, err := h.svc.List(ctx, filters)
    if err != nil {
        h.logger.ErrorContext(ctx, "list failed", "request_id", reqID, "error", err)
        writeError(w, err)
        return
    }

    // 3. Return paginated response
    writeJSON(w, http.StatusOK, ListEnvelope[Widget]{
        Data: result.Items,
        Meta: ListMeta{
            Cursor:    result.Cursor,
            HasMore:   result.HasMore,
            Total:     result.Total,
            RequestID: reqID,
            Timestamp: time.Now().UTC().Format(time.RFC3339),
        },
    })
}

// parseListFilters extracts pagination and filter parameters from the query string.
func parseListFilters(r *http.Request) domain.ListFilters {
    q := r.URL.Query()

    pageSize, _ := strconv.Atoi(q.Get("page_size"))
    if pageSize <= 0 {
        pageSize = 20
    }
    if pageSize > 100 {
        pageSize = 100
    }

    sortBy := q.Get("sort_by")
    allowedSorts := map[string]bool{"created_at": true, "updated_at": true, "name": true}
    if !allowedSorts[sortBy] {
        sortBy = "created_at"
    }

    sortDir := q.Get("sort_dir")
    if sortDir != "asc" && sortDir != "desc" {
        sortDir = "desc"
    }

    // Dynamic field filters: ?filter[status]=active&filter[priority]=high
    fields := make(map[string]string)
    allowedFilters := map[string]bool{"status": true, "priority": true, "category": true}
    for key, vals := range q {
        if len(key) > 7 && key[:7] == "filter[" && key[len(key)-1] == ']' {
            field := key[7 : len(key)-1]
            if allowedFilters[field] && len(vals) > 0 {
                fields[field] = vals[0]
            }
        }
    }

    return domain.ListFilters{
        Cursor:   q.Get("cursor"),
        PageSize: pageSize,
        SortBy:   sortBy,
        SortDir:  sortDir,
        Fields:   fields,
    }
}
```

## Helper Functions

```go
// decodeJSON reads and decodes the request body with size limit.
func decodeJSON(r *http.Request, dst any) error {
    // Cap body at 1MB to prevent abuse
    r.Body = http.MaxBytesReader(nil, r.Body, 1<<20)

    dec := json.NewDecoder(r.Body)
    dec.DisallowUnknownFields()

    if err := dec.Decode(dst); err != nil {
        return fmt.Errorf("invalid JSON: %w", err)
    }
    return nil
}

// writeJSON serializes data to JSON and writes the HTTP response.
func writeJSON(w http.ResponseWriter, status int, data any) {
    w.Header().Set("Content-Type", "application/json; charset=utf-8")
    w.WriteHeader(status)
    if err := json.NewEncoder(w).Encode(data); err != nil {
        // Log but can't change status at this point
        slog.Error("failed to write response", "error", err)
    }
}

// writeError maps a domain error to an HTTP error response.
func writeError(w http.ResponseWriter, err error) {
    var appErr *apperr.AppError
    if errors.As(err, &appErr) {
        writeJSON(w, appErr.HTTPStatus, ErrorBody{
            Error: ErrorDetail{
                Code:    appErr.Code,
                Message: appErr.Message,
                Details: appErr.Details,
            },
        })
        return
    }
    // Fallback: never expose internal error messages to clients
    writeJSON(w, http.StatusInternalServerError, ErrorBody{
        Error: ErrorDetail{
            Code:    "INTERNAL_ERROR",
            Message: "an unexpected error occurred",
        },
    })
}

// parseUUID parses and validates a UUID path parameter.
func parseUUID(raw string) (uuid.UUID, error) {
    id, err := uuid.Parse(raw)
    if err != nil {
        return uuid.Nil, fmt.Errorf("invalid UUID: %q", raw)
    }
    return id, nil
}

// newMeta creates the standard response metadata.
func newMeta(requestID string) Meta {
    return Meta{
        RequestID: requestID,
        Timestamp: time.Now().UTC().Format(time.RFC3339),
    }
}

// RequestIDFromContext extracts the request ID set by middleware.
func RequestIDFromContext(ctx context.Context) string {
    if id, ok := ctx.Value(ctxKeyRequestID).(string); ok {
        return id
    }
    return ""
}
```

## Input Sanitization Pattern

```go
// Sanitize strips leading/trailing whitespace and trims dangerous input.
func (i *CreateInput) Sanitize() {
    i.Name = strings.TrimSpace(i.Name)
    i.Description = strings.TrimSpace(i.Description)
    // Strip any HTML tags if this field will be rendered in a UI
    i.Name = bluemonday.StrictPolicy().Sanitize(i.Name)
}
```

## Critical Rules

- Every handler MUST start an OpenTelemetry span
- Every handler MUST extract `request_id` from context and include it in logs
- Tenant ID comes from context (set by auth middleware) — NEVER from path params or body
- Request body MUST be size-limited (`http.MaxBytesReader`) to prevent abuse
- `json.Decoder.DisallowUnknownFields()` MUST be set to catch typos early
- Error responses MUST map domain errors to correct HTTP status codes
- Internal error messages MUST NOT leak to clients — return generic message for 500s
- Pagination MUST enforce max page size (100) — never return unbounded lists
- Filter fields MUST be allow-listed — never pass arbitrary query params to the DB
- Sort fields MUST be allow-listed — never allow sorting by arbitrary columns
- Every response MUST use the envelope format: `{"data": T, "meta": {...}}`
- DELETE returns 204 No Content — no body
- POST create returns 201 Created with the created resource in the body
