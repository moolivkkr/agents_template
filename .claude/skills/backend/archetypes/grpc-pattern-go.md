---
skill: grpc-pattern-go
description: Go gRPC archetype — google.golang.org/grpc, protoc-gen-go, interceptors, server/client streaming, health check, reflection
version: "1.0"
tags:
  - go
  - grpc
  - protobuf
  - streaming
  - archetype
  - backend
---

# gRPC Pattern — Go

> Go samples compile-checked (go build + go vet) 2026-09-30 with Go 1.27.1, grpc v1.84.0, protobuf v1.36.12, against code generated from grpc-pattern.md's protos by protoc-gen-go v1.36.12 and protoc-gen-go-grpc v1.6.2 (tests/archetype-compile/go/run.sh). Not run against a live server.

> **Canonical reference**: This is the Go counterpart to `grpc-pattern.md` (language-neutral). Read that first for concepts and contracts.

Go gRPC uses `google.golang.org/grpc` for the runtime and `protoc-gen-go` + `protoc-gen-go-grpc` for code generation.

## Code Generation Setup

```bash
# Install tools
go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest

# Or use buf (recommended)
# buf.gen.yaml
version: v1
plugins:
  - plugin: go
    out: gen/proto
    opt: paths=source_relative
  - plugin: go-grpc
    out: gen/proto
    opt: paths=source_relative

# Generate
buf generate
```

## Server Implementation

```go
package widget

import (
    "context"
    "errors"
    "fmt"
    "io"
    "log/slog"
    "strings"

    "google.golang.org/grpc/codes"
    "google.golang.org/grpc/status"
    "google.golang.org/protobuf/types/known/timestamppb"

    pb "yourapp/gen/proto/yourapp/v1"
    "yourapp/internal/apperr"
    "yourapp/internal/domain"
    "yourapp/internal/interceptor"
)

// WidgetService is the business API this server adapts. Tenant and user are explicit arguments,
// taken from the verified token by the auth interceptors — never from a request message.
type WidgetService interface {
    Create(ctx context.Context, tenantID, userID string, in domain.CreateWidgetInput) (*domain.Widget, error)
    Get(ctx context.Context, tenantID, id string) (*domain.Widget, error)
    List(ctx context.Context, tenantID string, f domain.ListFilters) (*domain.ListResult[*domain.Widget], error)
    Subscribe(ctx context.Context, tenantID string) <-chan domain.WidgetEvent
}

type Server struct {
    pb.UnimplementedWidgetServiceServer // Forward compatibility
    svc    WidgetService
    logger *slog.Logger
}

func NewServer(svc WidgetService, logger *slog.Logger) *Server {
    return &Server{
        svc:    svc,
        logger: logger.With("server", "widget-grpc"),
    }
}

// identity returns the tenant and user the auth interceptor took from the verified token.
func identity(ctx context.Context) (tenantID, userID string, err error) {
    tenantID, userID = interceptor.TenantIDFromContext(ctx), interceptor.UserIDFromContext(ctx)
    if tenantID == "" {
        return "", "", status.Error(codes.Unauthenticated, "unauthenticated")
    }
    return tenantID, userID, nil
}

// CreateWidget implements the unary CreateWidget RPC.
func (s *Server) CreateWidget(ctx context.Context, req *pb.CreateWidgetRequest) (*pb.CreateWidgetResponse, error) {
    // tenant_id and user_id come from interceptor context
    tenantID, userID, err := identity(ctx)
    if err != nil {
        return nil, err
    }

    logger := s.logger.With("method", "CreateWidget", "tenant_id", tenantID)

    if req.Name == "" {
        return nil, status.Error(codes.InvalidArgument, "name is required")
    }

    result, err := s.svc.Create(ctx, tenantID, userID, domain.CreateWidgetInput{
        Name:        req.Name,
        Description: req.Description,
    })
    if err != nil {
        logger.ErrorContext(ctx, "create failed", "error", err)
        return nil, mapError(err)
    }

    return &pb.CreateWidgetResponse{
        Widget: toProto(result),
    }, nil
}

// GetWidget implements the unary GetWidget RPC.
func (s *Server) GetWidget(ctx context.Context, req *pb.GetWidgetRequest) (*pb.GetWidgetResponse, error) {
    tenantID, _, err := identity(ctx)
    if err != nil {
        return nil, err
    }

    result, err := s.svc.Get(ctx, tenantID, req.Id)
    if err != nil {
        return nil, mapError(err)
    }

    return &pb.GetWidgetResponse{
        Widget: toProto(result),
    }, nil
}

// ListWidgets implements the unary ListWidgets RPC with cursor (page_token) pagination.
func (s *Server) ListWidgets(ctx context.Context, req *pb.ListWidgetsRequest) (*pb.ListWidgetsResponse, error) {
    tenantID, _, err := identity(ctx)
    if err != nil {
        return nil, err
    }

    // AIP-158: page_size 0 means the default; above the maximum is coerced to the maximum.
    pageSize := int(req.PageSize)
    if pageSize < 0 {
        return nil, status.Error(codes.InvalidArgument, "page_size must not be negative")
    }
    if pageSize == 0 {
        pageSize = 20
    }
    if pageSize > 100 {
        pageSize = 100
    }

    // order_by is "field [asc|desc]"; the service/repository allow-list both parts.
    sortBy, sortDir, _ := strings.Cut(strings.TrimSpace(req.OrderBy), " ")

    result, err := s.svc.List(ctx, tenantID, domain.ListFilters{
        Cursor:   req.PageToken,
        PageSize: pageSize,
        SortBy:   sortBy,
        SortDir:  strings.ToLower(strings.TrimSpace(sortDir)),
    })
    if err != nil {
        return nil, mapError(err)
    }

    widgets := make([]*pb.Widget, len(result.Items))
    for i, w := range result.Items {
        widgets[i] = toProto(w)
    }

    return &pb.ListWidgetsResponse{
        Widgets:       widgets,
        NextPageToken: result.Cursor, // "" when there are no more pages
        TotalCount:    int32(result.Total),
    }, nil
}
```

## Server Streaming

```go
// WatchWidgets implements server streaming — pushes events to the client.
func (s *Server) WatchWidgets(req *pb.WatchWidgetsRequest, stream pb.WidgetService_WatchWidgetsServer) error {
    ctx := stream.Context()
    tenantID, _, err := identity(ctx) // set by AuthStreamInterceptor
    if err != nil {
        return err
    }

    s.logger.InfoContext(ctx, "watch started", "tenant_id", tenantID)
    defer s.logger.InfoContext(ctx, "watch ended", "tenant_id", tenantID)

    // Subscribe to this tenant's events only (e.g., from a channel or event bus)
    eventCh := s.svc.Subscribe(ctx, tenantID)

    for {
        select {
        case <-ctx.Done():
            return nil // Client disconnected or deadline exceeded
        case event, ok := <-eventCh:
            if !ok {
                return nil // Channel closed
            }
            if err := stream.Send(eventToProto(event)); err != nil {
                return err
            }
        }
    }
}
```

## Client Streaming

```go
// ImportWidgets implements client streaming — receives a stream of widgets.
func (s *Server) ImportWidgets(stream pb.WidgetService_ImportWidgetsServer) error {
    ctx := stream.Context()
    tenantID, userID, err := identity(ctx) // set by AuthStreamInterceptor
    if err != nil {
        return err
    }

    var imported, failed int32
    var rowErrors []string

    for {
        req, err := stream.Recv()
        if errors.Is(err, io.EOF) {
            // Client finished sending
            return stream.SendAndClose(&pb.ImportWidgetsResponse{
                ImportedCount: imported,
                FailedCount:   failed,
                Errors:        rowErrors,
            })
        }
        if err != nil {
            return status.Error(codes.Internal, "receive error")
        }

        if _, err := s.svc.Create(ctx, tenantID, userID, domain.CreateWidgetInput{
            Name:        req.Name,
            Description: req.Description,
        }); err != nil {
            failed++
            // The client sees the mapped, user-safe message — never err.Error()
            rowErrors = append(rowErrors, fmt.Sprintf("row %d: %s", imported+failed, status.Convert(mapError(err)).Message()))
        } else {
            imported++
        }
    }
}
```

## Interceptors

```go
package interceptor

import (
    "context"
    "log/slog"
    "time"

    "google.golang.org/grpc"
    "google.golang.org/grpc/codes"
    "google.golang.org/grpc/metadata"
    "google.golang.org/grpc/status"
)

// JWTValidator verifies a bearer token (signature, exp, iss, aud) and returns its claims.
type JWTValidator interface {
    Validate(token string) (*Claims, error)
}

// Claims are the identity fields the interceptors copy into the context.
type Claims struct {
    TenantID string
    UserID   string
}

type ctxKey int

const (
    ctxKeyTenantID ctxKey = iota
    ctxKeyUserID
)

func SetTenantID(ctx context.Context, id string) context.Context {
    return context.WithValue(ctx, ctxKeyTenantID, id)
}

func SetUserID(ctx context.Context, id string) context.Context {
    return context.WithValue(ctx, ctxKeyUserID, id)
}

// TenantIDFromContext returns the tenant from the verified token, or "" if none was set.
func TenantIDFromContext(ctx context.Context) string {
    id, _ := ctx.Value(ctxKeyTenantID).(string)
    return id
}

// UserIDFromContext returns the user from the verified token, or "" if none was set.
func UserIDFromContext(ctx context.Context) string {
    id, _ := ctx.Value(ctxKeyUserID).(string)
    return id
}

// authenticate validates the bearer token from the incoming metadata and returns ctx carrying the
// tenant and user from its claims.
func authenticate(ctx context.Context, jwtValidator JWTValidator) (context.Context, error) {
    md, ok := metadata.FromIncomingContext(ctx)
    if !ok {
        return nil, status.Error(codes.Unauthenticated, "missing metadata")
    }

    tokens := md.Get("authorization")
    if len(tokens) == 0 {
        return nil, status.Error(codes.Unauthenticated, "missing authorization")
    }

    token := tokens[0]
    if len(token) > 7 && token[:7] == "Bearer " {
        token = token[7:]
    }

    claims, err := jwtValidator.Validate(token)
    if err != nil {
        return nil, status.Error(codes.Unauthenticated, "invalid token")
    }

    ctx = SetTenantID(ctx, claims.TenantID)
    return SetUserID(ctx, claims.UserID), nil
}

// AuthUnaryInterceptor validates JWT from metadata and injects tenant context.
func AuthUnaryInterceptor(jwtValidator JWTValidator) grpc.UnaryServerInterceptor {
    return func(
        ctx context.Context,
        req any,
        info *grpc.UnaryServerInfo,
        handler grpc.UnaryHandler,
    ) (any, error) {
        // Skip auth for health checks
        if info.FullMethod == "/grpc.health.v1.Health/Check" {
            return handler(ctx, req)
        }

        ctx, err := authenticate(ctx, jwtValidator)
        if err != nil {
            return nil, err
        }
        return handler(ctx, req)
    }
}

// AuthStreamInterceptor does the same for streaming RPCs (WatchWidgets, ImportWidgets): without it
// every stream would run unauthenticated.
func AuthStreamInterceptor(jwtValidator JWTValidator) grpc.StreamServerInterceptor {
    return func(srv any, ss grpc.ServerStream, info *grpc.StreamServerInfo, handler grpc.StreamHandler) error {
        if info.FullMethod == "/grpc.health.v1.Health/Watch" {
            return handler(srv, ss)
        }

        ctx, err := authenticate(ss.Context(), jwtValidator)
        if err != nil {
            return err
        }
        return handler(srv, &authedStream{ServerStream: ss, ctx: ctx})
    }
}

// authedStream overrides the stream's context with the authenticated one.
type authedStream struct {
    grpc.ServerStream
    ctx context.Context
}

func (s *authedStream) Context() context.Context { return s.ctx }

// LoggingUnaryInterceptor logs every RPC with duration and status.
func LoggingUnaryInterceptor(logger *slog.Logger) grpc.UnaryServerInterceptor {
    return func(
        ctx context.Context,
        req any,
        info *grpc.UnaryServerInfo,
        handler grpc.UnaryHandler,
    ) (any, error) {
        start := time.Now()
        resp, err := handler(ctx, req)
        duration := time.Since(start)

        code := codes.OK
        if err != nil {
            code = status.Code(err)
        }

        logger.InfoContext(ctx, "grpc.request",
            "method", info.FullMethod,
            "duration", duration,
            "code", code.String(),
        )

        return resp, err
    }
}

// RecoveryUnaryInterceptor catches panics and returns INTERNAL.
func RecoveryUnaryInterceptor(logger *slog.Logger) grpc.UnaryServerInterceptor {
    return func(
        ctx context.Context,
        req any,
        info *grpc.UnaryServerInfo,
        handler grpc.UnaryHandler,
    ) (resp any, err error) {
        defer func() {
            if r := recover(); r != nil {
                logger.ErrorContext(ctx, "grpc.panic", "method", info.FullMethod, "panic", r)
                err = status.Error(codes.Internal, "internal error")
            }
        }()
        return handler(ctx, req)
    }
}
```

## Error Mapping

```go
// mapError converts domain errors (*apperr.AppError, error-handling-go.md) to gRPC status errors.
// The message is the AppError's user-safe message; unknown errors never expose their text.
func mapError(err error) error {
    var appErr *apperr.AppError
    if !errors.As(err, &appErr) {
        return status.Error(codes.Internal, "internal error")
    }

    switch appErr.Code {
    case "NOT_FOUND":
        return status.Error(codes.NotFound, appErr.Message)
    case "CONFLICT":
        return status.Error(codes.AlreadyExists, appErr.Message)
    case "VALIDATION_FAILED", "MALFORMED_REQUEST":
        return status.Error(codes.InvalidArgument, appErr.Message)
    case "UNAUTHENTICATED":
        return status.Error(codes.Unauthenticated, appErr.Message)
    case "FORBIDDEN":
        return status.Error(codes.PermissionDenied, appErr.Message)
    case "BUSINESS_RULE_VIOLATION":
        return status.Error(codes.FailedPrecondition, appErr.Message)
    case "RATE_LIMITED":
        return status.Error(codes.ResourceExhausted, appErr.Message)
    case "UNAVAILABLE":
        return status.Error(codes.Unavailable, appErr.Message)
    default:
        return status.Error(codes.Internal, "internal error")
    }
}
```

## Server Startup

```go
package main

import (
    "log/slog"
    "net"
    "os"
    "os/signal"
    "syscall"

    "google.golang.org/grpc"
    "google.golang.org/grpc/health"
    healthpb "google.golang.org/grpc/health/grpc_health_v1"
    "google.golang.org/grpc/reflection"

    pb "yourapp/gen/proto/yourapp/v1"
    "yourapp/internal/interceptor"
    "yourapp/internal/widget"
)

func main() {
    logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))

    // jwtValidator (interceptor.JWTValidator) and widgetSvc (widget.WidgetService) come from your
    // wiring: config, key material, DB pool, repositories.

    // Create gRPC server with interceptor chains — unary AND stream RPCs are authenticated
    srv := grpc.NewServer(
        grpc.ChainUnaryInterceptor(
            interceptor.RecoveryUnaryInterceptor(logger),
            interceptor.LoggingUnaryInterceptor(logger),
            interceptor.AuthUnaryInterceptor(jwtValidator),
        ),
        grpc.ChainStreamInterceptor(
            interceptor.AuthStreamInterceptor(jwtValidator),
        ),
    )

    // Register services
    widgetServer := widget.NewServer(widgetSvc, logger)
    pb.RegisterWidgetServiceServer(srv, widgetServer)

    // Health check
    healthServer := health.NewServer()
    healthpb.RegisterHealthServer(srv, healthServer)
    healthServer.SetServingStatus("yourapp.v1.WidgetService", healthpb.HealthCheckResponse_SERVING)

    // Reflection (development only)
    if os.Getenv("ENABLE_REFLECTION") == "true" {
        reflection.Register(srv)
    }

    // Listen
    lis, err := net.Listen("tcp", ":50051")
    if err != nil {
        logger.Error("failed to listen", "error", err)
        os.Exit(1)
    }

    // Graceful shutdown
    go func() {
        sigCh := make(chan os.Signal, 1)
        signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
        <-sigCh
        logger.Info("shutting down gRPC server")
        srv.GracefulStop()
    }()

    logger.Info("gRPC server listening", "addr", ":50051")
    if err := srv.Serve(lis); err != nil {
        logger.Error("server error", "error", err)
    }
}
```

## Proto-to-Domain Conversion

```go
func toProto(w *domain.Widget) *pb.Widget {
    return &pb.Widget{
        Id:          w.ID.String(),
        TenantId:    w.TenantID.String(),
        Name:        w.Name,
        Description: w.Description,
        Status:      pb.WidgetStatus(pb.WidgetStatus_value["WIDGET_STATUS_"+strings.ToUpper(w.Status)]),
        CreatedAt:   timestamppb.New(w.CreatedAt),
        UpdatedAt:   timestamppb.New(w.UpdatedAt),
        CreatedBy:   w.CreatedBy.String(),
        Version:     int32(w.Version),
    }
}

func eventToProto(e domain.WidgetEvent) *pb.WidgetEvent {
    return &pb.WidgetEvent{
        Type:      pb.WidgetEventType(pb.WidgetEventType_value["WIDGET_EVENT_TYPE_"+strings.ToUpper(e.Type)]),
        Widget:    toProto(e.Widget),
        Timestamp: timestamppb.New(e.At),
    }
}
```

## Critical Rules

- Embed `UnimplementedXxxServiceServer` in your server struct — required for forward compatibility
- Use `grpc.ChainUnaryInterceptor` for ordered interceptor chains — first interceptor runs first
- Use `metadata.FromIncomingContext` to read headers — gRPC metadata is the equivalent of HTTP headers
- Return `status.Error` for all errors (plain Go errors become INTERNAL); map `*apperr.AppError` codes, and never send an unknown error's text
- Authenticate streaming RPCs too (`grpc.ChainStreamInterceptor`) — a unary-only auth interceptor leaves every stream open
- Register health service on every gRPC server — required for load balancer probes
- Enable reflection only when `ENABLE_REFLECTION` env var is set — never in production
- Use `srv.GracefulStop()` for shutdown — waits for in-flight RPCs to complete
- Streaming RPCs MUST check `ctx.Done()` in their loops — detect client disconnection
- Client streaming: use `io.EOF` from `stream.Recv()` to detect end of client stream
