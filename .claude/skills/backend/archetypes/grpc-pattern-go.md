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
    "log/slog"

    "google.golang.org/grpc/codes"
    "google.golang.org/grpc/status"
    "google.golang.org/protobuf/types/known/timestamppb"

    pb "yourapp/gen/proto/yourapp/v1"
    "yourapp/internal/domain"
    "yourapp/internal/apperr"
)

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

// CreateWidget implements the unary CreateWidget RPC.
func (s *Server) CreateWidget(ctx context.Context, req *pb.CreateWidgetRequest) (*pb.CreateWidgetResponse, error) {
    // tenant_id and user_id come from interceptor context
    tenantID := TenantIDFromContext(ctx)
    userID := UserIDFromContext(ctx)

    logger := s.logger.With("method", "CreateWidget", "tenant_id", tenantID)

    if req.Name == "" {
        return nil, status.Errorf(codes.InvalidArgument, "name is required")
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
    tenantID := TenantIDFromContext(ctx)

    result, err := s.svc.Get(ctx, tenantID, req.Id)
    if err != nil {
        return nil, mapError(err)
    }

    return &pb.GetWidgetResponse{
        Widget: toProto(result),
    }, nil
}

// ListWidgets implements the unary ListWidgets RPC with pagination.
func (s *Server) ListWidgets(ctx context.Context, req *pb.ListWidgetsRequest) (*pb.ListWidgetsResponse, error) {
    tenantID := TenantIDFromContext(ctx)

    pageSize := int(req.PageSize)
    if pageSize <= 0 {
        pageSize = 20
    }
    if pageSize > 100 {
        pageSize = 100
    }

    result, err := s.svc.List(ctx, tenantID, domain.ListFilters{
        Cursor:   req.PageToken,
        PageSize: pageSize,
        OrderBy:  req.OrderBy,
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
        NextPageToken: result.NextCursor,
        TotalCount:    int32(result.Total),
    }, nil
}
```

## Server Streaming

```go
// WatchWidgets implements server streaming — pushes events to the client.
func (s *Server) WatchWidgets(req *pb.WatchWidgetsRequest, stream pb.WidgetService_WatchWidgetsServer) error {
    ctx := stream.Context()
    tenantID := TenantIDFromContext(ctx)

    s.logger.InfoContext(ctx, "watch started", "tenant_id", tenantID)
    defer s.logger.InfoContext(ctx, "watch ended", "tenant_id", tenantID)

    // Subscribe to events (e.g., from a channel or event bus)
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
    tenantID := TenantIDFromContext(ctx)
    userID := UserIDFromContext(ctx)

    var imported, failed int32
    var errors []string

    for {
        req, err := stream.Recv()
        if err == io.EOF {
            // Client finished sending
            return stream.SendAndClose(&pb.ImportWidgetsResponse{
                ImportedCount: imported,
                FailedCount:   failed,
                Errors:        errors,
            })
        }
        if err != nil {
            return status.Errorf(codes.Internal, "receive error: %v", err)
        }

        if err := s.svc.Create(ctx, tenantID, userID, domain.CreateWidgetInput{
            Name:        req.Name,
            Description: req.Description,
        }); err != nil {
            failed++
            errors = append(errors, fmt.Sprintf("row %d: %s", imported+failed, err.Error()))
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
    "go.opentelemetry.io/otel"
)

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
        ctx = SetUserID(ctx, claims.UserID)

        return handler(ctx, req)
    }
}

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
            "tenant_id", TenantIDFromContext(ctx),
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
                err = status.Errorf(codes.Internal, "internal error")
            }
        }()
        return handler(ctx, req)
    }
}
```

## Error Mapping

```go
// mapError converts domain errors to gRPC status errors.
func mapError(err error) error {
    var appErr *apperr.AppError
    if !errors.As(err, &appErr) {
        return status.Errorf(codes.Internal, "internal error")
    }

    switch {
    case errors.Is(err, apperr.ErrNotFound):
        return status.Errorf(codes.NotFound, appErr.Message)
    case errors.Is(err, apperr.ErrConflict):
        return status.Errorf(codes.AlreadyExists, appErr.Message)
    case errors.Is(err, apperr.ErrValidation):
        return status.Errorf(codes.InvalidArgument, appErr.Message)
    case errors.Is(err, apperr.ErrForbidden):
        return status.Errorf(codes.PermissionDenied, appErr.Message)
    default:
        return status.Errorf(codes.Internal, "internal error")
    }
}
```

## Server Startup

```go
package main

import (
    "net"
    "os"
    "os/signal"
    "syscall"

    "google.golang.org/grpc"
    "google.golang.org/grpc/health"
    healthpb "google.golang.org/grpc/health/grpc_health_v1"
    "google.golang.org/grpc/reflection"

    pb "yourapp/gen/proto/yourapp/v1"
)

func main() {
    logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))

    // Create gRPC server with interceptor chain
    srv := grpc.NewServer(
        grpc.ChainUnaryInterceptor(
            interceptor.RecoveryUnaryInterceptor(logger),
            interceptor.LoggingUnaryInterceptor(logger),
            interceptor.AuthUnaryInterceptor(jwtValidator),
        ),
        grpc.ChainStreamInterceptor(
            // Stream interceptors for streaming RPCs
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
        Status:      pb.WidgetStatus(pb.WidgetStatus_value["WIDGET_STATUS_"+strings.ToUpper(string(w.Status))]),
        CreatedAt:   timestamppb.New(w.CreatedAt),
        UpdatedAt:   timestamppb.New(w.UpdatedAt),
        CreatedBy:   w.CreatedBy.String(),
        Version:     int32(w.Version),
    }
}
```

## Critical Rules

- Embed `UnimplementedXxxServiceServer` in your server struct — required for forward compatibility
- Use `grpc.ChainUnaryInterceptor` for ordered interceptor chains — first interceptor runs first
- Use `metadata.FromIncomingContext` to read headers — gRPC metadata is the equivalent of HTTP headers
- Use `status.Errorf` for all error returns — plain Go errors become INTERNAL
- Register health service on every gRPC server — required for load balancer probes
- Enable reflection only when `ENABLE_REFLECTION` env var is set — never in production
- Use `srv.GracefulStop()` for shutdown — waits for in-flight RPCs to complete
- Streaming RPCs MUST check `ctx.Done()` in their loops — detect client disconnection
- Client streaming: use `io.EOF` from `stream.Recv()` to detect end of client stream
