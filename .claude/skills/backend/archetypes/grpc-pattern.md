---
skill: grpc-pattern
description: Language-neutral gRPC archetype — proto design, unary/streaming RPCs, error handling, interceptors, health checks, reflection, versioning
version: "1.0"
tags:
  - grpc
  - protobuf
  - rpc
  - streaming
  - archetype
  - backend
---

# gRPC Pattern

Complete production-ready gRPC pattern for service-to-service communication. Every generated gRPC service MUST follow this pattern.

> **Language-specific variants**: See `grpc-pattern-go.md`, `grpc-pattern-python.md`, `grpc-pattern-java.md`, `grpc-pattern-rust.md`, `grpc-pattern-typescript.md` for idiomatic implementations.

## Proto File Design Conventions

### Project Structure

```
proto/
  yourapp/
    v1/
      widget_service.proto    # Service definition
      widget.proto            # Message types
      common.proto            # Shared types (pagination, errors)
  buf.yaml                    # Buf configuration
  buf.gen.yaml                # Code generation config
```

### Service Definition

```protobuf
// proto/yourapp/v1/widget_service.proto

syntax = "proto3";

package yourapp.v1;

option go_package = "yourapp/gen/proto/yourapp/v1;widgetv1";
option java_package = "com.example.yourapp.v1";
option java_multiple_files = true;

import "yourapp/v1/widget.proto";
import "yourapp/v1/common.proto";

// WidgetService manages widget resources.
service WidgetService {
  // Unary RPCs
  rpc CreateWidget(CreateWidgetRequest) returns (CreateWidgetResponse);
  rpc GetWidget(GetWidgetRequest) returns (GetWidgetResponse);
  rpc UpdateWidget(UpdateWidgetRequest) returns (UpdateWidgetResponse);
  rpc DeleteWidget(DeleteWidgetRequest) returns (DeleteWidgetResponse);
  rpc ListWidgets(ListWidgetsRequest) returns (ListWidgetsResponse);

  // Server streaming: real-time updates
  rpc WatchWidgets(WatchWidgetsRequest) returns (stream WidgetEvent);

  // Client streaming: batch import
  rpc ImportWidgets(stream ImportWidgetRequest) returns (ImportWidgetsResponse);

  // Bidirectional streaming: collaborative editing
  rpc EditWidget(stream EditWidgetRequest) returns (stream EditWidgetResponse);
}
```

### Message Types

```protobuf
// proto/yourapp/v1/widget.proto

syntax = "proto3";

package yourapp.v1;

import "google/protobuf/timestamp.proto";

// Widget is the core domain entity.
message Widget {
  string id = 1;           // UUID
  string tenant_id = 2;    // UUID — tenant isolation
  string name = 3;
  string description = 4;
  WidgetStatus status = 5;
  google.protobuf.Timestamp created_at = 6;
  google.protobuf.Timestamp updated_at = 7;
  string created_by = 8;   // UUID
  int32 version = 9;       // Optimistic locking
}

enum WidgetStatus {
  WIDGET_STATUS_UNSPECIFIED = 0;  // Always have an unspecified zero value
  WIDGET_STATUS_ACTIVE = 1;
  WIDGET_STATUS_INACTIVE = 2;
  WIDGET_STATUS_ARCHIVED = 3;
}

// Request/Response messages
message CreateWidgetRequest {
  string name = 1;
  string description = 2;
  // tenant_id comes from auth context, not the request
}

message CreateWidgetResponse {
  Widget widget = 1;
}

message GetWidgetRequest {
  string id = 1;
}

message GetWidgetResponse {
  Widget widget = 1;
}

message UpdateWidgetRequest {
  string id = 1;
  string name = 2;
  string description = 3;
  int32 version = 4;  // Optimistic locking
}

message UpdateWidgetResponse {
  Widget widget = 1;
}

message DeleteWidgetRequest {
  string id = 1;
}

message DeleteWidgetResponse {}

message ListWidgetsRequest {
  int32 page_size = 1;      // Max 100
  string page_token = 2;    // Opaque cursor
  string order_by = 3;      // e.g., "created_at desc"
}

message ListWidgetsResponse {
  repeated Widget widgets = 1;
  string next_page_token = 2;
  int32 total_count = 3;
}
```

### Shared Types

```protobuf
// proto/yourapp/v1/common.proto

syntax = "proto3";

package yourapp.v1;

// WidgetEvent is used in the WatchWidgets server stream.
message WidgetEvent {
  WidgetEventType type = 1;
  Widget widget = 2;
  google.protobuf.Timestamp timestamp = 3;
}

enum WidgetEventType {
  WIDGET_EVENT_TYPE_UNSPECIFIED = 0;
  WIDGET_EVENT_TYPE_CREATED = 1;
  WIDGET_EVENT_TYPE_UPDATED = 2;
  WIDGET_EVENT_TYPE_DELETED = 3;
}

message WatchWidgetsRequest {
  // Filter events by tenant (from auth) and optional status
  WidgetStatus status_filter = 1;
}

message ImportWidgetRequest {
  string name = 1;
  string description = 2;
}

message ImportWidgetsResponse {
  int32 imported_count = 1;
  int32 failed_count = 2;
  repeated string errors = 3;
}

message EditWidgetRequest {
  string widget_id = 1;
  string field = 2;
  string value = 3;
}

message EditWidgetResponse {
  string widget_id = 1;
  string field = 2;
  string value = 3;
  string edited_by = 4;
  google.protobuf.Timestamp timestamp = 5;
}
```

## Proto Design Rules

| Rule | Rationale |
|------|-----------|
| Every enum MUST have a `_UNSPECIFIED = 0` value | Proto3 default is 0; explicit unspecified prevents ambiguity |
| Every RPC has its own Request/Response types | Allows independent evolution without breaking other RPCs |
| Use `google.protobuf.Timestamp` for times | Standard, well-supported across all languages |
| Use `string` for UUIDs | Proto has no native UUID type; string is universally supported |
| Use `int32` for version fields | Sufficient range, efficient on wire |
| Pagination uses `page_token` (not offset) | Cursor-based pagination is more scalable |
| `tenant_id` is in the message (for storage) but NOT in requests | Extracted from auth context by interceptor |
| Field numbers are permanent | Never reuse a field number, even after deleting the field |

## Error Handling — gRPC Status Codes

```
Domain Error        → gRPC Status Code     → HTTP Equivalent
────────────────────────────────────────────────────────────
ValidationError     → INVALID_ARGUMENT (3)  → 400
NotFoundError       → NOT_FOUND (5)         → 404
ConflictError       → ALREADY_EXISTS (6)    → 409
                      ABORTED (10)          → 409 (optimistic lock)
UnauthorizedError   → UNAUTHENTICATED (16)  → 401
ForbiddenError      → PERMISSION_DENIED (7) → 403
RateLimitError      → RESOURCE_EXHAUSTED (8)→ 429
UpstreamError       → UNAVAILABLE (14)      → 503
InternalError       → INTERNAL (13)         → 500
TimeoutError        → DEADLINE_EXCEEDED (4) → 504
```

### Error Details

```
Use google.rpc.Status with details for rich errors:

Status {
    code: INVALID_ARGUMENT
    message: "widget name is required"
    details: [
        BadRequest {
            field_violations: [
                { field: "name", description: "must not be empty" }
            ]
        }
    ]
}
```

## Interceptors / Middleware

Interceptors are the gRPC equivalent of HTTP middleware. They run before/after every RPC.

```
Standard interceptor chain (in order):

1. Recovery      — Catch panics, return INTERNAL
2. Logging       — Log request/response with duration
3. Metrics       — Emit latency histogram, success/failure counters
4. Tracing       — Start OpenTelemetry span, propagate context
5. Auth          — Validate token from metadata, extract tenant/user
6. Tenant        — Inject tenant_id into context
7. Validation    — Validate request message fields
8. Rate Limiting — Per-tenant rate limiting
9. Handler       — Actual RPC implementation
```

### Auth Interceptor Pattern

```
function auth_interceptor(ctx, request, info, handler):
    // Extract token from gRPC metadata (equivalent to HTTP headers)
    token = metadata_from_context(ctx).get("authorization")

    if token is empty:
        return error(UNAUTHENTICATED, "missing authorization")

    // Validate JWT
    claims = validate_jwt(token)
    if claims is invalid:
        return error(UNAUTHENTICATED, "invalid token")

    // Inject user/tenant into context
    ctx = set_tenant_id(ctx, claims.tenant_id)
    ctx = set_user_id(ctx, claims.user_id)

    return handler(ctx, request)
```

## Health Check Service

Every gRPC server MUST implement the standard health check protocol.

```protobuf
// Standard: grpc.health.v1.Health
service Health {
    rpc Check(HealthCheckRequest) returns (HealthCheckResponse);
    rpc Watch(HealthCheckRequest) returns (stream HealthCheckResponse);
}

message HealthCheckRequest {
    string service = 1;  // Service name or empty for server health
}

message HealthCheckResponse {
    enum ServingStatus {
        UNKNOWN = 0;
        SERVING = 1;
        NOT_SERVING = 2;
        SERVICE_UNKNOWN = 3;
    }
    ServingStatus status = 1;
}
```

## Reflection

Enable server reflection in development/staging for debugging with tools like `grpcurl` and `grpcui`.

```
// Enable in development, disable in production
if environment != "production":
    enable_reflection(server)

// Usage with grpcurl:
grpcurl -plaintext localhost:50051 list
grpcurl -plaintext localhost:50051 describe yourapp.v1.WidgetService
grpcurl -plaintext -d '{"name": "test"}' localhost:50051 yourapp.v1.WidgetService/CreateWidget
```

## Proto Versioning Strategy

```
Strategy: Package-level versioning (recommended)

proto/yourapp/v1/   ← current stable version
proto/yourapp/v2/   ← next version (breaking changes)

Rules:
1. Additive changes (new fields, new RPCs) go in the current version
2. Breaking changes (rename field, change type, remove field) require a new version
3. Run both v1 and v2 servers during migration period
4. Deprecate v1 after all clients migrate

What is NOT a breaking change:
  - Adding a new field (existing clients ignore it)
  - Adding a new RPC method
  - Adding a new enum value
  - Adding a new oneof field

What IS a breaking change:
  - Removing or renaming a field
  - Changing a field's type
  - Changing a field number
  - Removing an RPC method
  - Changing an RPC's request/response type
```

## Deadlines and Timeouts

```
// Clients MUST set deadlines on every RPC call
client.GetWidget(ctx_with_deadline(5s), request)

// Servers MUST check deadline before expensive operations
if ctx.deadline_exceeded():
    return error(DEADLINE_EXCEEDED)

// Propagate deadlines across service calls
// gRPC automatically propagates the deadline in metadata
service_a.Call(ctx) → service_b.Call(ctx)  // deadline flows through
```

## Observability

```
Metrics (per RPC method):
    grpc_server_handled_total{method, code}           # counter
    grpc_server_handling_seconds{method}               # histogram
    grpc_server_msg_received_total{method}             # counter (streaming)
    grpc_server_msg_sent_total{method}                 # counter (streaming)

Logging:
    Every RPC logs: method, duration, status_code, tenant_id, request_id

Tracing:
    Every RPC creates an OpenTelemetry span:
    - span name: "grpc.yourapp.v1.WidgetService/GetWidget"
    - attributes: rpc.method, rpc.service, rpc.grpc.status_code
    - propagation: W3C trace context via gRPC metadata
```

## Critical Rules

- Every enum MUST have an `_UNSPECIFIED = 0` zero value
- Every RPC MUST have unique Request/Response message types — no reuse
- Field numbers are permanent — NEVER reuse or reassign
- `tenant_id` MUST come from auth context (interceptor), NEVER from request messages
- Clients MUST set deadlines — servers MUST respect them
- Use `google.rpc.Status` details for structured error information
- Enable health check service on every gRPC server
- Enable reflection only in development/staging — disable in production
- Interceptor order matters: recovery first, auth before handler
- Use `buf` for linting and breaking change detection
- Pagination uses opaque `page_token` — never expose raw database cursors
- Streaming RPCs MUST handle client disconnection gracefully
