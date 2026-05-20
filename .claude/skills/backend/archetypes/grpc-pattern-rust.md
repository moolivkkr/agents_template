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

> **Canonical reference**: This is the Rust counterpart to `grpc-pattern.md` (language-neutral). Read that first for concepts and contracts.

Rust gRPC uses `tonic` for the server/client runtime and `prost` for Protobuf serialization. Code generation happens at build time via `tonic-build`.

## Build Setup

```toml
# Cargo.toml
[dependencies]
tonic = "0.11"
prost = "0.12"
prost-types = "0.12"
tokio = { version = "1", features = ["full"] }
tonic-health = "0.11"
tonic-reflection = "0.11"
tower = "0.4"
uuid = { version = "1", features = ["v4", "serde"] }
tracing = "0.1"

[build-dependencies]
tonic-build = "0.11"
```

```rust
// build.rs
fn main() -> Result<(), Box<dyn std::error::Error>> {
    tonic_build::configure()
        .build_server(true)
        .build_client(true)
        .compile(
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
}

use proto::widget_service_server::WidgetService;
use proto::*;

use crate::services::WidgetSvc;
use crate::grpc::context::{tenant_id_from_request, user_id_from_request};
use crate::grpc::errors::map_error;

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

    // Server streaming
    type WatchWidgetsStream = tokio_stream::wrappers::ReceiverStream<Result<WidgetEvent, Status>>;

    async fn watch_widgets(
        &self,
        request: Request<WatchWidgetsRequest>,
    ) -> Result<Response<Self::WatchWidgetsStream>, Status> {
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

        Ok(Response::new(tokio_stream::wrappers::ReceiverStream::new(rx)))
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
                    errors.push(format!("row {}: {}", imported + failed, e));
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
use tonic::{Request, Status};
use tower::{Layer, Service};
use uuid::Uuid;

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
    S: Service<http::Request<B>, Response = http::Response<tonic::body::BoxBody>>
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
            let token = token.ok_or_else(|| Status::unauthenticated("missing authorization"))?;

            let claims = validator
                .validate(&token)
                .map_err(|_| Status::unauthenticated("invalid token"))?;

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
use crate::errors::AppError;

pub fn map_error(err: AppError) -> Status {
    match err {
        AppError::NotFound(msg) => Status::not_found(msg),
        AppError::Conflict(msg) => Status::already_exists(msg),
        AppError::Validation(msg) => Status::invalid_argument(msg),
        AppError::Forbidden(msg) => Status::permission_denied(msg),
        AppError::Internal(_) => Status::internal("internal error"),
    }
}
```

## Server Startup

```rust
// src/main.rs

use tonic::transport::Server;
use tonic_health::server::health_reporter;
use tonic_reflection::server::Builder as ReflectionBuilder;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    tracing_subscriber::fmt::init();

    let addr = "[::]:50051".parse()?;

    // Health service
    let (mut health_reporter, health_service) = health_reporter();
    health_reporter
        .set_serving::<proto::widget_service_server::WidgetServiceServer<WidgetGrpcServer>>()
        .await;

    // Reflection (development only)
    let reflection_service = if std::env::var("ENABLE_REFLECTION").is_ok() {
        Some(
            ReflectionBuilder::configure()
                .register_encoded_file_descriptor_set(proto::FILE_DESCRIPTOR_SET)
                .build()?,
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

async fn shutdown_signal() {
    tokio::signal::ctrl_c().await.ok();
    tracing::info!("shutdown signal received");
}
```

## Critical Rules

- Use `tonic::include_proto!` to include generated code — compiled at build time via `build.rs`
- Use `#[tonic::async_trait]` on service implementations — required for async trait methods
- Use `Request::extensions()` for auth context — injected by Tower middleware layer
- Return `Status::xxx()` for all errors — tonic maps them to proper gRPC codes
- Server streaming returns a `ReceiverStream` — use `mpsc::channel` and spawn a task
- Client streaming receives `tonic::Streaming<T>` — iterate with `stream.message().await`
- Use `serve_with_shutdown` for graceful shutdown — takes a future that resolves on signal
- Use `tonic-health` for standard health check service
- Use `tonic-reflection` with `FILE_DESCRIPTOR_SET` for reflection support
- Tower layers wrap the service — use `Server::builder().layer()` for interceptors
