---
skill: grpc-pattern-rust
description: Rust gRPC archetype — tonic, prost, interceptors/layers, streaming, health check, reflection
version: "1.0"
tags:
  - rust
  - grpc
  - tonic
  - prost
  - streaming
  - archetype
  - backend
---

# gRPC Pattern — Rust

> Rust samples compile-checked 2026-09-30 (tests/archetype-compile/rust/run.sh): rustc 1.98.1, tonic 0.14.6, prost 0.14.4, tonic-prost-build 0.14.6 (protoc 36.2, grpc-pattern.md's .proto files), tonic-health/-reflection 0.14.6. Compiled, not run.

> **Canonical reference**: This is the Rust counterpart to `grpc-pattern.md` (language-neutral). Read that first for concepts and contracts.

Rust gRPC uses `tonic` for the server/client runtime and `prost` for Protobuf serialization. Code generation happens at build time via `tonic-prost-build` (tonic 0.14; earlier versions used `tonic-build`), which needs `protoc` installed.

## Build Setup

```toml
# Cargo.toml
[dependencies]
tonic = "0.14"
tonic-prost = "0.14"        # prost codec the generated code uses (split out of tonic in 0.14)
prost = "0.14"
prost-types = "0.14"        # google.protobuf.Timestamp
tokio = { version = "1", features = ["full"] }
tokio-stream = "0.1"        # ReceiverStream for server streaming
tonic-health = "0.14"
tonic-reflection = "0.14"
tower = "0.5"
http = "1"                  # the auth layer is a tower Service over http::Request
uuid = { version = "1", features = ["v4", "serde"] }
tracing = "0.1"

[build-dependencies]
tonic-prost-build = "0.14"  # was tonic-build before 0.14; needs protoc on PATH
```

```rust
// build.rs — tonic 0.14 moved prost codegen to tonic-prost-build (needs `protoc` on PATH)
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let out_dir = std::path::PathBuf::from(std::env::var("OUT_DIR")?);
    tonic_prost_build::configure()
        .build_server(true)
        .build_client(true)
        // RPCs this server does not implement yet answer UNIMPLEMENTED (Go: embed Unimplemented…Server)
        .generate_default_stubs(true)
        // for tonic-reflection: proto::FILE_DESCRIPTOR_SET below
        .file_descriptor_set_path(out_dir.join("yourapp_descriptor.bin"))
        .compile_protos(
            &["proto/yourapp/v1/widget_service.proto"],
            &["proto"],
        )?;
    Ok(())
}
```

## Server Implementation

```rust
// src/grpc/widget_server.rs

use tonic::{Request, Response, Status};
use tracing::{info, error};
use uuid::Uuid;

pub mod proto {
    tonic::include_proto!("yourapp.v1");
    pub const FILE_DESCRIPTOR_SET: &[u8] = tonic::include_file_descriptor_set!("yourapp_descriptor");
}

use proto::widget_service_server::WidgetService;
use proto::*;

use crate::services::WidgetSvc;
use crate::grpc::context::{tenant_id_from_request, user_id_from_request};
use crate::grpc::convert::{event_to_proto, to_proto}; // domain → proto mapping (not shown)
use crate::grpc::errors::map_error;

/// What a server-streaming RPC returns when build.rs sets generate_default_stubs(true).
type WidgetEventStream =
    std::pin::Pin<Box<dyn tokio_stream::Stream<Item = Result<WidgetEvent, Status>> + Send + 'static>>;

pub struct WidgetGrpcServer {
    svc: std::sync::Arc<dyn WidgetSvc>,
}

impl WidgetGrpcServer {
    pub fn new(svc: std::sync::Arc<dyn WidgetSvc>) -> Self {
        Self { svc }
    }
}

#[tonic::async_trait]
impl WidgetService for WidgetGrpcServer {
    async fn create_widget(
        &self,
        request: Request<CreateWidgetRequest>,
    ) -> Result<Response<CreateWidgetResponse>, Status> {
        let tenant_id = tenant_id_from_request(&request)?;
        let user_id = user_id_from_request(&request)?;
        let req = request.into_inner();

        if req.name.is_empty() {
            return Err(Status::invalid_argument("name is required"));
        }

        let result = self.svc
            .create(tenant_id, user_id, &req.name, &req.description)
            .await
            .map_err(map_error)?;

        Ok(Response::new(CreateWidgetResponse {
            widget: Some(to_proto(&result)),
        }))
    }

    async fn get_widget(
        &self,
        request: Request<GetWidgetRequest>,
    ) -> Result<Response<GetWidgetResponse>, Status> {
        let tenant_id = tenant_id_from_request(&request)?;
        let req = request.into_inner();

        let id = Uuid::parse_str(&req.id)
            .map_err(|_| Status::invalid_argument("invalid widget ID"))?;

        let result = self.svc
            .get(tenant_id, id)
            .await
            .map_err(map_error)?;

        Ok(Response::new(GetWidgetResponse {
            widget: Some(to_proto(&result)),
        }))
    }

    async fn list_widgets(
        &self,
        request: Request<ListWidgetsRequest>,
    ) -> Result<Response<ListWidgetsResponse>, Status> {
        let tenant_id = tenant_id_from_request(&request)?;
        let req = request.into_inner();

        let page_size = req.page_size.max(1).min(100);
        let cursor = if req.page_token.is_empty() { None } else { Some(req.page_token) };

        let result = self.svc
            .list(tenant_id, cursor, page_size as usize)
            .await
            .map_err(map_error)?;

        Ok(Response::new(ListWidgetsResponse {
            widgets: result.items.iter().map(to_proto).collect(),
            next_page_token: result.next_cursor.unwrap_or_default(),
            total_count: result.total as i32,
        }))
    }

    // Server streaming. With generate_default_stubs(true) (build.rs) a streaming RPC returns a boxed
    // stream; without it, declare `type WatchWidgetsStream = ReceiverStream<…>;` and return that.
    async fn watch_widgets(
        &self,
        request: Request<WatchWidgetsRequest>,
    ) -> Result<Response<WidgetEventStream>, Status> {
        let tenant_id = tenant_id_from_request(&request)?;

        let (tx, rx) = tokio::sync::mpsc::channel(128);
        let svc = self.svc.clone();

        tokio::spawn(async move {
            let mut events = svc.subscribe(tenant_id).await;
            while let Some(event) = events.recv().await {
                if tx.send(Ok(event_to_proto(&event))).await.is_err() {
                    break; // Client disconnected
                }
            }
            info!(tenant_id = %tenant_id, "watch.ended");
        });

        Ok(Response::new(Box::pin(tokio_stream::wrappers::ReceiverStream::new(rx))))
    }

    // Client streaming
    async fn import_widgets(
        &self,
        request: Request<tonic::Streaming<ImportWidgetRequest>>,
    ) -> Result<Response<ImportWidgetsResponse>, Status> {
        let tenant_id = tenant_id_from_request(&request)?;
        let user_id = user_id_from_request(&request)?;
        let mut stream = request.into_inner();

        let mut imported = 0i32;
        let mut failed = 0i32;
        let mut errors = Vec::new();

        while let Some(req) = stream.message().await? {
            match self.svc.create(tenant_id, user_id, &req.name, &req.description).await {
                Ok(_) => imported += 1,
                Err(e) => {
                    failed += 1;
                    // user-safe text only; the cause (Display) stays in the server log
                    tracing::warn!(error = %e, row = imported + failed, "import row failed");
                    errors.push(format!("row {}: {}", imported + failed, e.user_message()));
                }
            }
        }

        Ok(Response::new(ImportWidgetsResponse {
            imported_count: imported,
            failed_count: failed,
            errors,
        }))
    }
}
```

## Interceptor (Tower Layer)

```rust
// src/grpc/auth_layer.rs

use std::task::{Context, Poll};
use tonic::Status;
use tower::{Layer, Service};
use uuid::Uuid;

use crate::auth::JwtValidator; // your token validator: validate(&str) -> Result<Claims, _> (not shown)

/// Extension type stored in tonic::Request extensions.
#[derive(Debug, Clone)]
pub struct AuthContext {
    pub tenant_id: Uuid,
    pub user_id: Uuid,
}

#[derive(Clone)]
pub struct AuthLayer {
    jwt_validator: std::sync::Arc<dyn JwtValidator>,
}

impl AuthLayer {
    pub fn new(jwt_validator: std::sync::Arc<dyn JwtValidator>) -> Self {
        Self { jwt_validator }
    }
}

impl<S> Layer<S> for AuthLayer {
    type Service = AuthService<S>;

    fn layer(&self, inner: S) -> Self::Service {
        AuthService {
            inner,
            jwt_validator: self.jwt_validator.clone(),
        }
    }
}

#[derive(Clone)]
pub struct AuthService<S> {
    inner: S,
    jwt_validator: std::sync::Arc<dyn JwtValidator>,
}

impl<S, B> Service<http::Request<B>> for AuthService<S>
where
    S: Service<http::Request<B>, Response = http::Response<tonic::body::Body>> // BoxBody before tonic 0.13
        + Clone
        + Send
        + 'static,
    S::Future: Send + 'static,
    B: Send + 'static,
{
    type Response = S::Response;
    type Error = S::Error;
    type Future = std::pin::Pin<
        Box<dyn std::future::Future<Output = Result<Self::Response, Self::Error>> + Send>,
    >;

    fn poll_ready(&mut self, cx: &mut Context<'_>) -> Poll<Result<(), Self::Error>> {
        self.inner.poll_ready(cx)
    }

    fn call(&mut self, mut req: http::Request<B>) -> Self::Future {
        let path = req.uri().path().to_string();

        // Skip auth for health checks
        if path.contains("grpc.health.v1.Health") {
            let mut inner = self.inner.clone();
            return Box::pin(async move { inner.call(req).await });
        }

        let token = req
            .headers()
            .get("authorization")
            .and_then(|v| v.to_str().ok())
            .map(|s| s.strip_prefix("Bearer ").unwrap_or(s).to_string());

        let validator = self.jwt_validator.clone();
        let mut inner = self.inner.clone();

        Box::pin(async move {
            // A rejection is a gRPC status sent as the HTTP response (the inner service's error
            // type is generic, so a Status can't be returned with `?`)
            let Some(token) = token else {
                return Ok(Status::unauthenticated("missing authorization").into_http());
            };
            let Ok(claims) = validator.validate(&token) else {
                return Ok(Status::unauthenticated("invalid token").into_http());
            };

            req.extensions_mut().insert(AuthContext {
                tenant_id: claims.tenant_id,
                user_id: claims.user_id,
            });

            inner.call(req).await
        })
    }
}
```

## Context Helpers

```rust
// src/grpc/context.rs

use tonic::{Request, Status};
use uuid::Uuid;

use crate::grpc::auth_layer::AuthContext;

pub fn tenant_id_from_request<T>(request: &Request<T>) -> Result<Uuid, Status> {
    request
        .extensions()
        .get::<AuthContext>()
        .map(|ctx| ctx.tenant_id)
        .ok_or_else(|| Status::unauthenticated("missing auth context"))
}

pub fn user_id_from_request<T>(request: &Request<T>) -> Result<Uuid, Status> {
    request
        .extensions()
        .get::<AuthContext>()
        .map(|ctx| ctx.user_id)
        .ok_or_else(|| Status::unauthenticated("missing auth context"))
}
```

## Error Mapping

```rust
// src/grpc/errors.rs

use tonic::Status;
use crate::error::AppError; // the one AppError (error-handling-rust.md)

/// AppError → gRPC status (grpc-pattern.md table). The message is the same user-safe text the HTTP
/// envelope carries; the cause (Display) goes to the log only.
pub fn map_error(err: AppError) -> Status {
    let msg = err.user_message();
    match &err {
        AppError::MalformedRequest(_) | AppError::Validation { .. } => Status::invalid_argument(msg),
        AppError::Unauthenticated => Status::unauthenticated(msg),
        AppError::Forbidden => Status::permission_denied(msg),
        AppError::NotFound { .. } => Status::not_found(msg),
        AppError::Conflict { .. } | AppError::IdempotencyKeyReused => Status::already_exists(msg),
        AppError::BusinessRule { .. } => Status::failed_precondition(msg),
        AppError::RateLimited { .. } => Status::resource_exhausted(msg),
        AppError::Unavailable { .. } => Status::unavailable(msg),
        AppError::Internal(_) => {
            tracing::error!(error = %err, "grpc request failed");
            Status::internal(msg)
        }
    }
}
```

## Server Startup

```rust
// src/main.rs

mod app; // your wiring: wire() -> (Arc<dyn WidgetSvc>, Arc<dyn JwtValidator>) (not shown)
mod grpc; // widget_server, auth_layer, context, convert, errors

use tonic::transport::Server;
use tonic_health::server::health_reporter;
use tonic_reflection::server::Builder as ReflectionBuilder;

use grpc::auth_layer::AuthLayer;
use grpc::widget_server::{proto, WidgetGrpcServer};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    tracing_subscriber::fmt::init();

    let addr = "[::]:50051".parse()?;
    // Your wiring (not shown): the WidgetSvc implementation and the JWT validator
    let (widget_svc, jwt_validator) = app::wire().await?;

    // Health service
    let (health_reporter, health_service) = health_reporter();
    health_reporter
        .set_serving::<proto::widget_service_server::WidgetServiceServer<WidgetGrpcServer>>()
        .await;

    // Reflection (development only)
    let reflection_service = if std::env::var("ENABLE_REFLECTION").is_ok() {
        Some(
            ReflectionBuilder::configure()
                .register_encoded_file_descriptor_set(proto::FILE_DESCRIPTOR_SET)
                .build_v1()?, // grpc.reflection.v1 (build_v1alpha() for older clients)
        )
    } else {
        None
    };

    let widget_server = WidgetGrpcServer::new(widget_svc);

    let mut builder = Server::builder()
        .layer(AuthLayer::new(jwt_validator))
        .add_service(health_service)
        .add_service(proto::widget_service_server::WidgetServiceServer::new(widget_server));

    if let Some(reflection) = reflection_service {
        builder = builder.add_service(reflection);
    }

    tracing::info!("gRPC server listening on {}", addr);
    builder.serve_with_shutdown(addr, shutdown_signal()).await?;

    Ok(())
}

/// SIGTERM is what Kubernetes and Docker send on stop; Ctrl+C (SIGINT) for local runs.
async fn shutdown_signal() {
    let mut sigterm = tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate())
        .expect("failed to install SIGTERM handler");
    tokio::select! {
        _ = tokio::signal::ctrl_c() => {}
        _ = sigterm.recv() => {}
    }
    tracing::info!("shutdown signal received");
}
```

## Critical Rules

- Use `tonic::include_proto!` to include generated code — compiled at build time via `build.rs`
- Use `#[tonic::async_trait]` on service implementations — required for async trait methods
- Use `Request::extensions()` for auth context — injected by Tower middleware layer
- Return `Status::xxx()` for all errors — tonic maps them to proper gRPC codes
- Server streaming returns a boxed `ReceiverStream` (the generated signature with `generate_default_stubs(true)`) — use `mpsc::channel` and spawn a task
- Client streaming receives `tonic::Streaming<T>` — iterate with `stream.message().await`
- Use `serve_with_shutdown` for graceful shutdown — takes a future that resolves on signal
- Use `tonic-health` for standard health check service
- Use `tonic-reflection` with `FILE_DESCRIPTOR_SET` for reflection support
- Tower layers wrap the service — use `Server::builder().layer()` for interceptors
