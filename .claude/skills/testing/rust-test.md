# Rust testing patterns for backend services.

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
```rust
use mockall::automock;

#[automock]
#[async_trait]
pub trait WidgetRepository: Send + Sync {
    async fn create(&self, widget: &Widget) -> Result<(), AppError>;
    async fn get_by_id(&self, tenant_id: Uuid, id: Uuid) -> Result<Widget, AppError>;
    async fn update(&self, widget: &Widget) -> Result<(), AppError>;
    async fn soft_delete(&self, tenant_id: Uuid, id: Uuid) -> Result<(), AppError>;
}

#[cfg(test)]
mod tests {
    use super::*;
    use mockall::predicate::*;

    #[tokio::test]
    async fn test_service_calls_repo_create() {
        let mut mock_repo = MockWidgetRepository::new();
        mock_repo
            .expect_create()
            .withf(|w: &Widget| w.name == "Test" && w.tenant_id == tenant_id())
            .times(1)
            .returning(|_| Ok(()));

        let mock_cache = MockCache::new();  // no cache expectations — not called on create
        let mock_audit = MockAuditWriter::new();

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
- Add `#[automock]` above the trait definition — mockall generates `MockWidgetRepository`
- Use `expect_*()` to set expectations, `returning()` to provide return values
- Use `withf()` for predicate-based argument matching
- Mock objects panic on unexpected calls — this is intentional (catches incorrect usage)

## Database Tests with sqlx
```rust
// In Cargo.toml: sqlx = { features = ["runtime-tokio", "postgres", "migrate"] }

#[cfg(test)]
mod tests {
    use sqlx::PgPool;

    // sqlx::test provides a fresh database per test via transactions that roll back.
    #[sqlx::test(migrations = "./migrations")]
    async fn test_create_widget(pool: PgPool) {
        let repo = PgWidgetRepository::new(pool);
        let widget = Widget {
            id: Uuid::new_v4(),
            tenant_id: Uuid::new_v4(),
            name: "DB Test".into(),
            ..Default::default()
        };

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
- Set `DATABASE_URL` in `.env` or env var — sqlx connects to a real Postgres instance
- `#[sqlx::test]` wraps each test in a transaction that rolls back — tests are isolated
- `migrations = "./migrations"` runs migrations before each test
- Requires a running Postgres — use docker-compose or testcontainers

## Test Fixtures with std::sync::OnceLock
```rust
use std::sync::OnceLock;
use uuid::Uuid;

static TEST_TENANT: OnceLock<Uuid> = OnceLock::new();
static TEST_USER: OnceLock<Uuid> = OnceLock::new();

fn tenant_id() -> Uuid {
    *TEST_TENANT.get_or_init(|| Uuid::parse_str("11111111-1111-1111-1111-111111111111").unwrap())
}

fn user_id() -> Uuid {
    *TEST_USER.get_or_init(|| Uuid::parse_str("22222222-2222-2222-2222-222222222222").unwrap())
}

fn test_widget() -> Widget {
    let now = Utc::now();
    Widget {
        id: Uuid::new_v4(),
        tenant_id: tenant_id(),
        name: "Test Widget".into(),
        description: Some("fixture".into()),
        status: "active".into(),
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

## Property-Based Testing with proptest
```rust
use proptest::prelude::*;

proptest! {
    #[test]
    fn test_cursor_roundtrip(
        ts in any::<i64>().prop_map(|secs| DateTime::from_timestamp(secs.abs() % 4_000_000_000, 0).unwrap()),
        id in any::<[u8; 16]>().prop_map(Uuid::from_bytes),
    ) {
        let encoded = encode_cursor(ts, id);
        let (decoded_ts, decoded_id) = decode_cursor(&encoded).unwrap();
        prop_assert_eq!(ts, decoded_ts);
        prop_assert_eq!(id, decoded_id);
    }

    #[test]
    fn test_sanitize_column_never_returns_injection(input in ".*") {
        let result = sanitize_column(&input);
        // Result must be one of the allow-listed columns
        prop_assert!(["created_at", "updated_at", "name", "status", "priority", "category"]
            .contains(&result));
    }
}
```
- Use proptest for invariant testing — generates hundreds of random inputs
- `prop_map` transforms generated values into domain types
- Catches edge cases that manual test cases miss

## Integration Tests (tests/ directory)
```rust
// tests/api_integration.rs — runs as a separate binary
use axum::body::Body;
use axum::http::{Request, StatusCode};
use tower::ServiceExt;

mod common;
use common::TestApp;

#[tokio::test]
async fn test_full_crud_lifecycle() {
    let app = TestApp::spawn().await;

    // Create
    let resp = app.post("/api/v1/widgets", json!({ "name": "Integration" })).await;
    assert_eq!(resp.status(), StatusCode::CREATED);
    let created: serde_json::Value = app.json(resp).await;
    let id = created["data"]["id"].as_str().unwrap();

    // Read
    let resp = app.get(&format!("/api/v1/widgets/{id}")).await;
    assert_eq!(resp.status(), StatusCode::OK);

    // Update
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
pub struct TestApp {
    app: Router,
    token: String,
}

impl TestApp {
    pub async fn spawn() -> Self {
        let pool = test_pool().await;
        let state = Arc::new(AppState::test(pool));
        let app = build_router(state);
        let token = generate_test_jwt(tenant_id(), user_id());
        Self { app, token }
    }

    pub async fn get(&self, path: &str) -> axum::response::Response {
        let req = Request::builder()
            .uri(path)
            .header("authorization", format!("Bearer {}", self.token))
            .body(Body::empty())
            .unwrap();
        self.app.clone().oneshot(req).await.unwrap()
    }

    pub async fn post(&self, path: &str, body: serde_json::Value) -> axum::response::Response {
        let req = Request::builder()
            .method("POST")
            .uri(path)
            .header("authorization", format!("Bearer {}", self.token))
            .header("content-type", "application/json")
            .body(Body::from(serde_json::to_vec(&body).unwrap()))
            .unwrap();
        self.app.clone().oneshot(req).await.unwrap()
    }

    pub async fn json(&self, resp: axum::response::Response) -> serde_json::Value {
        let body = axum::body::to_bytes(resp.into_body(), usize::MAX).await.unwrap();
        serde_json::from_slice(&body).unwrap()
    }
}
```
- `tower::ServiceExt::oneshot` — no TCP server needed, fast and deterministic
- Clone the router for each request (Axum routers are cheaply cloneable)
- Include auth headers in every request for realistic testing
