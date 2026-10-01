# Rust testing patterns for backend services.

> Rust samples compile-checked 2026-09-30 (tests/archetype-compile/rust/run.sh): rustc 1.98.1, mockall 0.15.0, proptest 1.11.0, sqlx 0.9.0, inside the Rust CRUD archetypes' widget app. Every test here ran (the database ones on Postgres 17) and passes.

The examples test the widget service of the Rust CRUD archetypes (`backend/archetypes/crud-*-rust.md`):
`crate::models::Widget`, `crate::services::widget::WidgetService`, the `#[automock]` traits in
`crate::traits`, and `yourapp::startup::build_app`.

## Unit Test Module Pattern
```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sanitize_column_allows_known() {
        assert_eq!(sanitize_column("name"), "name");
        assert_eq!(sanitize_column("created_at"), "created_at");
    }

    #[test]
    fn test_sanitize_column_rejects_unknown() {
        assert_eq!(sanitize_column("'; DROP TABLE--"), "created_at");
    }
}
```
- Place `#[cfg(test)] mod tests` at the bottom of each module — tests live next to the code
- Tests compile only when running `cargo test` — zero production overhead
- Access private functions via `use super::*`

## Async Tests with Tokio
```rust
#[cfg(test)]
mod tests {
    use super::*;
    use crate::test_fixtures::{tenant_id, user_id};

    #[tokio::test]
    async fn test_create_widget() {
        let service = setup_test_service().await;
        let input = CreateWidgetInput {
            name: "Test Widget".into(),
            description: Some("A test".into()),
        };

        let result = service.create(tenant_id(), user_id(), input).await;
        assert!(result.is_ok());

        let widget = result.unwrap();
        assert_eq!(widget.name, "Test Widget");
        assert_eq!(widget.version, 1);
    }

    #[tokio::test]
    async fn test_get_nonexistent_returns_not_found() {
        let service = setup_test_service().await;
        let result = service.get(tenant_id(), Uuid::new_v4()).await;

        assert!(matches!(result, Err(AppError::NotFound { .. })));
    }
}
```
- Use `#[tokio::test]` for any async function — sets up the tokio runtime automatically
- Default is `flavor = "current_thread"` — use `#[tokio::test(flavor = "multi_thread")]` only when testing concurrent behavior

## Mocking with mockall
The service's dependencies are traits with `#[automock]` on them, in `src/traits/`
(`backend/archetypes/crud-service-test-rust.md`). Mock those — never a hand-copied subset of the trait,
which drifts from the real one.
```rust
#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Arc;

    use crate::test_fixtures::{tenant_id, user_id};
    use crate::traits::{audit::MockAuditWriter, cache::MockCache, repository::MockWidgetRepository};

    #[tokio::test]
    async fn test_service_calls_repo_create() {
        let mut mock_repo = MockWidgetRepository::new();
        mock_repo
            .expect_create()
            .withf(|w: &Widget| w.name == "Test" && w.tenant_id == tenant_id())
            .times(1)
            .returning(|_| Ok(()));

        let mock_cache = MockCache::new(); // no expectations: create must not touch the cache
        let mut mock_audit = MockAuditWriter::new();
        mock_audit.expect_write().times(1).returning(|_| Ok(())); // create writes one audit entry

        let service = WidgetService::new(
            Arc::new(mock_repo),
            Arc::new(mock_cache),
            Arc::new(mock_audit),
        );

        let input = CreateWidgetInput { name: "Test".into(), description: None };
        let result = service.create(tenant_id(), user_id(), input).await;
        assert!(result.is_ok());
    }
}
```
- `#[automock]` above the trait definition makes mockall generate `MockWidgetRepository`
- Use `expect_*()` to set expectations, `returning()` to provide return values
- Use `withf()` for predicate-based argument matching
- Mock objects panic on unexpected calls — this is intentional (catches incorrect usage), so every call
  the code under test makes needs an expectation

## Database Tests with sqlx
```rust
// In Cargo.toml: sqlx = { features = ["runtime-tokio", "postgres", "migrate", "macros"] }

#[cfg(test)]
mod tests {
    use sqlx::PgPool;

    use super::*;
    use crate::test_fixtures::test_widget;

    // #[sqlx::test] creates a fresh database for each test, runs the migrations in it, and drops it
    // after the test passes.
    #[sqlx::test(migrations = "./migrations")]
    async fn test_create_widget(pool: PgPool) {
        let repo = PgWidgetRepository::new(pool);
        let widget = Widget { name: "DB Test".into(), ..test_widget() };

        let result = repo.create(&widget).await;
        assert!(result.is_ok());

        let fetched = repo.get_by_id(widget.tenant_id, widget.id).await.unwrap();
        assert_eq!(fetched.name, "DB Test");
    }

    #[sqlx::test(migrations = "./migrations")]
    async fn test_soft_delete(pool: PgPool) {
        let repo = PgWidgetRepository::new(pool);
        let widget = test_widget();
        repo.create(&widget).await.unwrap();

        repo.soft_delete(widget.tenant_id, widget.id).await.unwrap();

        // Soft-deleted widget should not be findable
        let result = repo.get_by_id(widget.tenant_id, widget.id).await;
        assert!(matches!(result, Err(AppError::NotFound { .. })));
    }
}
```
- `DATABASE_URL` (env var or `.env`) points at a Postgres server the test user can create databases on
- `#[sqlx::test]` gives every test its own database — tests are isolated and can run in parallel
- `migrations = "./migrations"` runs migrations before each test
- Requires a running Postgres — use docker-compose or testcontainers

## Test Fixtures with std::sync::OnceLock
```rust
// src/test_fixtures.rs — in lib.rs: #[cfg(test)] mod test_fixtures;
use std::sync::OnceLock;

use chrono::Utc;
use uuid::Uuid;

use crate::models::{Widget, WidgetStatus};

static TEST_TENANT: OnceLock<Uuid> = OnceLock::new();
static TEST_USER: OnceLock<Uuid> = OnceLock::new();

pub(crate) fn tenant_id() -> Uuid {
    *TEST_TENANT.get_or_init(|| Uuid::parse_str("11111111-1111-1111-1111-111111111111").unwrap())
}

pub(crate) fn user_id() -> Uuid {
    *TEST_USER.get_or_init(|| Uuid::parse_str("22222222-2222-2222-2222-222222222222").unwrap())
}

pub(crate) fn test_widget() -> Widget {
    let now = Utc::now();
    Widget {
        id: Uuid::new_v4(),
        tenant_id: tenant_id(),
        name: "Test Widget".into(),
        description: Some("fixture".into()),
        status: WidgetStatus::Active,
        created_at: now,
        updated_at: now,
        deleted_at: None,
        created_by: user_id(),
        updated_by: user_id(),
        version: 1,
    }
}
```
- Use `OnceLock` (stable since Rust 1.80) for lazily-initialized test constants
- Avoid `lazy_static` — `OnceLock` is in std and does the same thing
- Integration tests in `tests/` can't see `#[cfg(test)]` items of the crate: they get their own helpers
  (Test Helper below)

## Property-Based Testing with proptest
```rust
// next to encode_cursor / decode_cursor / sanitize_column in the repository module
#[cfg(test)]
mod proptests {
    use super::*;
    use crate::test_fixtures::test_widget;
    use proptest::prelude::*;

    proptest! {
        #[test]
        fn test_cursor_roundtrip(
            secs in 0i64..4_000_000_000,
            id in any::<[u8; 16]>().prop_map(Uuid::from_bytes),
        ) {
            let created_at = DateTime::from_timestamp(secs, 0).unwrap();
            let widget = Widget { id, created_at, ..test_widget() };

            let encoded = encode_cursor("created_at", &widget);
            let decoded = decode_cursor(&encoded, "created_at").unwrap();
            prop_assert_eq!(decoded.id, id);
            prop_assert!(matches!(decoded.key, CursorKey::Ts(ts) if ts == created_at));
            // a cursor issued for one sort order is rejected for another
            prop_assert!(decode_cursor(&encoded, "name").is_err());
        }

        #[test]
        fn test_sanitize_column_never_returns_injection(input in ".*") {
            let result = sanitize_column(&input);
            // Result must be one of the allow-listed columns
            prop_assert!(["created_at", "updated_at", "name"].contains(&result));
        }
    }
}
```
- Use proptest for invariant testing — generates hundreds of random inputs
- `prop_map` transforms generated values into domain types
- Catches edge cases that manual test cases miss

## Integration Tests (tests/ directory)
```rust
// tests/api_integration.rs — runs as a separate binary
use axum::http::StatusCode;
use serde_json::json;
use sqlx::PgPool;

mod common;
use common::TestApp;

#[sqlx::test(migrations = "./migrations")]
async fn test_full_crud_lifecycle(pool: PgPool) {
    let app = TestApp::spawn(pool).await;

    // Create
    let resp = app.post("/api/v1/widgets", json!({ "name": "Integration" })).await;
    assert_eq!(resp.status(), StatusCode::CREATED);
    let created = app.json(resp).await;
    let id = created["data"]["id"].as_str().unwrap();

    // Read
    let resp = app.get(&format!("/api/v1/widgets/{id}")).await;
    assert_eq!(resp.status(), StatusCode::OK);

    // Update (optimistic lock: send the version you read)
    let resp = app.put(
        &format!("/api/v1/widgets/{id}"),
        json!({ "name": "Updated", "version": 1 }),
    ).await;
    assert_eq!(resp.status(), StatusCode::OK);

    // Delete
    let resp = app.delete(&format!("/api/v1/widgets/{id}")).await;
    assert_eq!(resp.status(), StatusCode::NO_CONTENT);

    // Verify deleted
    let resp = app.get(&format!("/api/v1/widgets/{id}")).await;
    assert_eq!(resp.status(), StatusCode::NOT_FOUND);
}
```
- Integration tests live in `tests/` at the crate root — separate compilation
- Use a `TestApp` helper that builds the router with test state
- Each test gets a fresh database (via `#[sqlx::test]` or manual setup/teardown)
- Run with `cargo test --test api_integration`

## Test Helper (tests/common/mod.rs)
```rust
use axum::{body::Body, http::Request, response::Response, Router};
use jsonwebtoken::{encode, EncodingKey, Header};
use sqlx::PgPool;
use tower::ServiceExt; // oneshot
use uuid::Uuid;
use yourapp::{auth::claims::JwtClaims, config::AppConfig, startup::build_app};

pub struct TestApp {
    app: Router,
    token: String,
}

impl TestApp {
    /// `pool` is the fresh, migrated database #[sqlx::test] hands the test.
    pub async fn spawn(pool: PgPool) -> Self {
        // test-only key; a real deployment loads the secret from its environment
        let config = AppConfig::test_defaults();
        let token = test_jwt(&config.jwt_secret, Uuid::new_v4(), Uuid::new_v4());
        let app = build_app(config, pool).await;
        Self { app, token }
    }

    pub async fn get(&self, path: &str) -> Response {
        self.send("GET", path, Body::empty()).await
    }

    pub async fn post(&self, path: &str, body: serde_json::Value) -> Response {
        self.send("POST", path, Body::from(serde_json::to_vec(&body).unwrap())).await
    }

    pub async fn put(&self, path: &str, body: serde_json::Value) -> Response {
        self.send("PUT", path, Body::from(serde_json::to_vec(&body).unwrap())).await
    }

    pub async fn delete(&self, path: &str) -> Response {
        self.send("DELETE", path, Body::empty()).await
    }

    pub async fn json(&self, resp: Response) -> serde_json::Value {
        let body = axum::body::to_bytes(resp.into_body(), usize::MAX).await.unwrap();
        serde_json::from_slice(&body).unwrap()
    }

    async fn send(&self, method: &str, path: &str, body: Body) -> Response {
        let req = Request::builder()
            .method(method)
            .uri(path)
            .header("authorization", format!("Bearer {}", self.token))
            .header("content-type", "application/json")
            .body(body)
            .unwrap();
        self.app.clone().oneshot(req).await.unwrap()
    }
}

/// A token signed with the test key, for one tenant — the server verifies it like any other.
fn test_jwt(secret: &str, tenant_id: Uuid, user_id: Uuid) -> String {
    let now = chrono::Utc::now();
    let claims = JwtClaims {
        sub: user_id,
        tenant_id,
        roles: vec!["admin".into()],
        iat: now.timestamp() as usize,
        exp: (now + chrono::Duration::hours(1)).timestamp() as usize,
        jti: None,
    };
    encode(&Header::default(), &claims, &EncodingKey::from_secret(secret.as_bytes())).unwrap()
}
```
- `tower::ServiceExt::oneshot` — no TCP server needed, fast and deterministic
- Clone the router for each request (Axum routers are cheaply cloneable)
- Include auth headers in every request for realistic testing
