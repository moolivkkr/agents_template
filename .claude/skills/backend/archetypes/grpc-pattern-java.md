---
skill: grpc-pattern-java
description: Java gRPC archetype — grpc-java, protobuf-gradle-plugin, interceptors, streaming, health check, Spring integration
version: "1.0"
tags:
  - java
  - grpc
  - protobuf
  - grpc-java
  - archetype
  - backend
---

# gRPC Pattern — Java

> **Canonical reference**: This is the Java counterpart to `grpc-pattern.md` (language-neutral). Read that first for concepts and contracts.

Java gRPC uses `grpc-java` for the runtime, `protobuf-gradle-plugin` or `protobuf-maven-plugin` for code generation, and optionally `grpc-spring-boot-starter` for Spring Boot integration.

## Gradle Setup

```groovy
// build.gradle
plugins {
    id 'com.google.protobuf' version '0.9.4'
}

dependencies {
    implementation 'io.grpc:grpc-netty-shaded:1.62.2'
    implementation 'io.grpc:grpc-protobuf:1.62.2'
    implementation 'io.grpc:grpc-stub:1.62.2'
    implementation 'io.grpc:grpc-services:1.62.2'  // health, reflection
    compileOnly 'org.apache.tomcat:annotations-api:6.0.53'
}

protobuf {
    protoc { artifact = 'com.google.protobuf:protoc:3.25.3' }
    plugins {
        grpc { artifact = 'io.grpc:protoc-gen-grpc-java:1.62.2' }
    }
    generateProtoTasks {
        all()*.plugins { grpc {} }
    }
}
```

## Server Implementation

```java
package com.example.app.grpc;

import com.example.app.model.entity.Widget;
import com.example.app.service.WidgetService;
import com.example.gen.yourapp.v1.*;
import com.google.protobuf.Timestamp;
import io.grpc.Status;
import io.grpc.stub.StreamObserver;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.Instant;
import java.util.UUID;

public class WidgetGrpcService extends WidgetServiceGrpc.WidgetServiceImplBase {

    private static final Logger log = LoggerFactory.getLogger(WidgetGrpcService.class);
    private final WidgetService widgetService;

    public WidgetGrpcService(WidgetService widgetService) {
        this.widgetService = widgetService;
    }

    @Override
    public void createWidget(
            CreateWidgetRequest request,
            StreamObserver<CreateWidgetResponse> responseObserver) {

        UUID tenantId = GrpcContext.getTenantId();
        UUID userId = GrpcContext.getUserId();

        if (request.getName().isBlank()) {
            responseObserver.onError(
                Status.INVALID_ARGUMENT.withDescription("name is required").asRuntimeException()
            );
            return;
        }

        try {
            Widget result = widgetService.create(
                request.getName(),
                request.getDescription(),
                tenantId,
                userId
            );

            responseObserver.onNext(
                CreateWidgetResponse.newBuilder()
                    .setWidget(toProto(result))
                    .build()
            );
            responseObserver.onCompleted();

        } catch (Exception e) {
            log.error("createWidget failed", e);
            responseObserver.onError(GrpcErrorMapper.map(e));
        }
    }

    @Override
    public void getWidget(
            GetWidgetRequest request,
            StreamObserver<GetWidgetResponse> responseObserver) {

        UUID tenantId = GrpcContext.getTenantId();

        try {
            Widget result = widgetService.findById(UUID.fromString(request.getId()), tenantId);

            responseObserver.onNext(
                GetWidgetResponse.newBuilder()
                    .setWidget(toProto(result))
                    .build()
            );
            responseObserver.onCompleted();

        } catch (Exception e) {
            responseObserver.onError(GrpcErrorMapper.map(e));
        }
    }

    @Override
    public void listWidgets(
            ListWidgetsRequest request,
            StreamObserver<ListWidgetsResponse> responseObserver) {

        UUID tenantId = GrpcContext.getTenantId();
        int pageSize = Math.max(1, Math.min(request.getPageSize() > 0 ? request.getPageSize() : 20, 100));

        try {
            var result = widgetService.list(tenantId, request.getPageToken(), pageSize);

            var builder = ListWidgetsResponse.newBuilder()
                .setTotalCount(result.getTotal());

            if (result.getNextCursor() != null) {
                builder.setNextPageToken(result.getNextCursor());
            }

            result.getItems().forEach(w -> builder.addWidgets(toProto(w)));

            responseObserver.onNext(builder.build());
            responseObserver.onCompleted();

        } catch (Exception e) {
            responseObserver.onError(GrpcErrorMapper.map(e));
        }
    }

    private static WidgetProto toProto(Widget w) {
        return WidgetProto.newBuilder()
            .setId(w.getId().toString())
            .setTenantId(w.getTenantId().toString())
            .setName(w.getName())
            .setDescription(w.getDescription() != null ? w.getDescription() : "")
            .setStatus(WidgetStatus.valueOf("WIDGET_STATUS_" + w.getStatus().name()))
            .setCreatedAt(toTimestamp(w.getCreatedAt()))
            .setUpdatedAt(toTimestamp(w.getUpdatedAt()))
            .setCreatedBy(w.getCreatedBy().toString())
            .setVersion(w.getVersion())
            .build();
    }

    private static Timestamp toTimestamp(Instant instant) {
        return Timestamp.newBuilder()
            .setSeconds(instant.getEpochSecond())
            .setNanos(instant.getNano())
            .build();
    }
}
```

## Server Streaming

```java
@Override
public void watchWidgets(
        WatchWidgetsRequest request,
        StreamObserver<WidgetEvent> responseObserver) {

    UUID tenantId = GrpcContext.getTenantId();
    log.info("watch.started, tenantId={}", tenantId);

    // Subscribe to events (e.g., from an event bus)
    var subscription = widgetService.subscribe(tenantId, event -> {
        if (Context.current().isCancelled()) {
            return; // Client disconnected
        }
        responseObserver.onNext(toEventProto(event));
    });

    // Wait for client cancellation
    Context.current().addListener(context -> {
        log.info("watch.ended, tenantId={}", tenantId);
        subscription.cancel();
        responseObserver.onCompleted();
    }, MoreExecutors.directExecutor());
}
```

## Client Streaming

```java
@Override
public StreamObserver<ImportWidgetRequest> importWidgets(
        StreamObserver<ImportWidgetsResponse> responseObserver) {

    UUID tenantId = GrpcContext.getTenantId();
    UUID userId = GrpcContext.getUserId();

    return new StreamObserver<>() {
        int imported = 0;
        int failed = 0;
        final List<String> errors = new ArrayList<>();

        @Override
        public void onNext(ImportWidgetRequest request) {
            try {
                widgetService.create(request.getName(), request.getDescription(), tenantId, userId);
                imported++;
            } catch (Exception e) {
                failed++;
                errors.add("row " + (imported + failed) + ": " + e.getMessage());
            }
        }

        @Override
        public void onError(Throwable t) {
            log.error("import.client_error", t);
        }

        @Override
        public void onCompleted() {
            responseObserver.onNext(ImportWidgetsResponse.newBuilder()
                .setImportedCount(imported)
                .setFailedCount(failed)
                .addAllErrors(errors)
                .build());
            responseObserver.onCompleted();
        }
    };
}
```

## Interceptors

```java
package com.example.app.grpc;

import io.grpc.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;

import java.util.Set;
import java.util.UUID;

public class AuthInterceptor implements ServerInterceptor {

    private static final Logger log = LoggerFactory.getLogger(AuthInterceptor.class);
    private static final Metadata.Key<String> AUTH_KEY =
        Metadata.Key.of("authorization", Metadata.ASCII_STRING_MARSHALLER);

    private static final Set<String> SKIP_AUTH = Set.of(
        "grpc.health.v1.Health/Check",
        "grpc.health.v1.Health/Watch"
    );

    private final JwtValidator jwtValidator;

    public AuthInterceptor(JwtValidator jwtValidator) {
        this.jwtValidator = jwtValidator;
    }

    @Override
    public <ReqT, RespT> ServerCall.Listener<ReqT> interceptCall(
            ServerCall<ReqT, RespT> call,
            Metadata headers,
            ServerCallHandler<ReqT, RespT> next) {

        String method = call.getMethodDescriptor().getFullMethodName();
        if (SKIP_AUTH.contains(method)) {
            return next.startCall(call, headers);
        }

        String token = headers.get(AUTH_KEY);
        if (token == null || token.isBlank()) {
            call.close(Status.UNAUTHENTICATED.withDescription("missing authorization"), new Metadata());
            return new ServerCall.Listener<>() {};
        }

        if (token.startsWith("Bearer ")) {
            token = token.substring(7);
        }

        try {
            var claims = jwtValidator.validate(token);

            Context ctx = Context.current()
                .withValue(GrpcContext.TENANT_ID_KEY, claims.getTenantId())
                .withValue(GrpcContext.USER_ID_KEY, claims.getUserId());

            return Contexts.interceptCall(ctx, call, headers, next);

        } catch (Exception e) {
            log.warn("auth failed: {}", e.getMessage());
            call.close(Status.UNAUTHENTICATED.withDescription("invalid token"), new Metadata());
            return new ServerCall.Listener<>() {};
        }
    }
}

// Logging interceptor
public class LoggingInterceptor implements ServerInterceptor {

    private static final Logger log = LoggerFactory.getLogger(LoggingInterceptor.class);

    @Override
    public <ReqT, RespT> ServerCall.Listener<ReqT> interceptCall(
            ServerCall<ReqT, RespT> call,
            Metadata headers,
            ServerCallHandler<ReqT, RespT> next) {

        String method = call.getMethodDescriptor().getFullMethodName();
        long start = System.nanoTime();

        return new ForwardingServerCallListener.SimpleForwardingServerCallListener<>(
            next.startCall(new ForwardingServerCall.SimpleForwardingServerCall<>(call) {
                @Override
                public void close(Status status, Metadata trailers) {
                    long duration = (System.nanoTime() - start) / 1_000_000;
                    log.info("grpc.request method={} status={} duration={}ms",
                        method, status.getCode(), duration);
                    super.close(status, trailers);
                }
            }, headers)
        ) {};
    }
}
```

## Context Helpers

```java
package com.example.app.grpc;

import io.grpc.Context;
import java.util.UUID;

public final class GrpcContext {
    public static final Context.Key<UUID> TENANT_ID_KEY = Context.key("tenantId");
    public static final Context.Key<UUID> USER_ID_KEY = Context.key("userId");

    private GrpcContext() {}

    public static UUID getTenantId() {
        return TENANT_ID_KEY.get();
    }

    public static UUID getUserId() {
        return USER_ID_KEY.get();
    }
}
```

## Error Mapping

```java
package com.example.app.grpc;

import com.example.app.errors.*;
import io.grpc.Status;
import io.grpc.StatusRuntimeException;

public final class GrpcErrorMapper {

    private GrpcErrorMapper() {}

    public static StatusRuntimeException map(Exception e) {
        if (e instanceof NotFoundException nfe) {
            return Status.NOT_FOUND.withDescription(nfe.getMessage()).asRuntimeException();
        }
        if (e instanceof ConflictException ce) {
            return Status.ALREADY_EXISTS.withDescription(ce.getMessage()).asRuntimeException();
        }
        if (e instanceof ValidationException ve) {
            return Status.INVALID_ARGUMENT.withDescription(ve.getMessage()).asRuntimeException();
        }
        if (e instanceof ForbiddenException fe) {
            return Status.PERMISSION_DENIED.withDescription(fe.getMessage()).asRuntimeException();
        }
        return Status.INTERNAL.withDescription("internal error").asRuntimeException();
    }
}
```

## Server Startup

```java
package com.example.app;

import io.grpc.Server;
import io.grpc.ServerBuilder;
import io.grpc.protobuf.services.HealthStatusManager;
import io.grpc.protobuf.services.ProtoReflectionService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class GrpcServer {

    private static final Logger log = LoggerFactory.getLogger(GrpcServer.class);

    public static void main(String[] args) throws Exception {
        int port = 50051;

        var healthManager = new HealthStatusManager();

        var builder = ServerBuilder.forPort(port)
            .addService(new WidgetGrpcService(widgetService))
            .addService(healthManager.getHealthService())
            .intercept(new LoggingInterceptor())
            .intercept(new AuthInterceptor(jwtValidator));

        // Reflection (development only)
        if ("true".equals(System.getenv("ENABLE_REFLECTION"))) {
            builder.addService(ProtoReflectionService.newInstance());
        }

        Server server = builder.build().start();

        healthManager.setStatus("yourapp.v1.WidgetService",
            io.grpc.health.v1.HealthCheckResponse.ServingStatus.SERVING);

        log.info("gRPC server listening on port {}", port);

        // Shutdown hook
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            log.info("shutting down gRPC server");
            server.shutdown();
            try {
                server.awaitTermination(30, java.util.concurrent.TimeUnit.SECONDS);
            } catch (InterruptedException e) {
                server.shutdownNow();
            }
        }));

        server.awaitTermination();
    }
}
```

## Critical Rules

- Extend `XxxImplBase` (not `XxxGrpc.XxxBlockingStub`) for server implementations
- Use `Context.key()` for thread-safe context propagation — gRPC `Context` is thread-local
- Use `Contexts.interceptCall()` in interceptors to propagate context with values
- Use `call.close(Status, Metadata)` in interceptors to reject — not `throw`
- Return empty `ServerCall.Listener` after closing — prevents NPE on rejected calls
- Use `HealthStatusManager` for health checks — register per-service health status
- Interceptor order is reversed: last `addInterceptor` runs first (wraps outermost)
- Client streaming uses a returned `StreamObserver` — implement `onNext`, `onError`, `onCompleted`
- Use `Context.current().isCancelled()` in streaming to detect client disconnection
- Always log method name, status code, and duration in the logging interceptor
