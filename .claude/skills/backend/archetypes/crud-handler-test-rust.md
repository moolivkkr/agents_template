---
skill: crud-handler-test-rust
description: Axum handler test archetype — TestApp helper, reqwest integration tests, CRUD endpoint coverage, cursor pagination, validation errors, auth tests, response envelope assertions, helper macros
version: "1.0"
tags:
  - rust
  - axum
  - handler
  - http
  - integration-test
  - archetype
  - backend
  - testing
---

# CRUD Handler Test Archetype (Rust / Axum)

Complete Axum handler test template. Every generated handler test file MUST follow this pattern.

## Test File Location

```
tests/
  api/
    mod.rs
    helpers.rs         <- TestApp, spawn_app, assertion helpers
    widget_test.rs     <- THIS file (integration tests)
src/
  handlers/
    widget.rs          <- production code
```

Rule: Integration tests live in `tests/` directory. Unit tests (with mocks) live in `#[cfg(test)] mod tests` within the handler file.

## Test Dependencies (Cargo.toml)

```toml
[dev-dependencies]
tokio = { version = "1", features = ["full", "test-util"] }
reqwest = { version = "0.12", features = ["json"] }
serde_json = "1"
uuid = { version = "1", features = ["v4"] }
sqlx = { version = "0.8", features = ["runtime-tokio", "postgres", "migrate"] }
once_cell = "1"
wiremock = "0.6"          # for mocking external services
fake = { version = "3", features = ["derive"] }
claims = "0.7"            # for JWT test helpers
```

## TestApp Helper

```rust
// tests/api/helpers.rs

use std::net::SocketAddr;
use std::sync::Arc;

use sqlx::{PgPool, Executor};
use uuid::Uuid;

use yourapp::config::Config;
use yourapp::startup::build_app;

/// Test application — spawns the real Axum server on a random port with a
/// dedicated test database. Dropped databases are cleaned up automatically.
pub struct TestApp {
    pub addr: SocketAddr,
    pub port: u16,
    pub pool: PgPool,
    pub client: reqwest::Client,
    pub db_name: String,
}

impl TestApp {
    /// Base URL for requests against this test instance.
    pub fn url(&self, path: &str) -> String {
        format!("http://{}:{}{}", self.addr.ip(), self.port, path)
    }

    /// Generate a valid JWT for the given tenant/user/roles.
    pub fn auth_token(&self, tenant_id: Uuid, user_id: Uuid, roles: Vec<String>) -> String {
        use jsonwebtoken::{encode, EncodingKey, Header};
        use yourapp::auth::JwtClaims;
        use chrono::{Utc, Duration};

        let claims = JwtClaims {
            sub: user_id,
            tenant_id,
            roles,
            exp: (Utc::now() + Duration::hours(1)).timestamp() as usize,
            iat: Utc::now().timestamp() as usize,
        };

        encode(
            &Header::default(),
            &claims,
            &EncodingKey::from_secret(b"test-secret"),
        )
        .expect("JWT encoding must not fail in tests")
    }

    /// Convenience: Authorization header value for the default test tenant/user.
    pub fn default_auth_header(&self) -> String {
        let token = self.auth_token(
            self.default_tenant_id(),
            self.default_user_id(),
            vec!["admin".into()],
        );
        format!("Bearer {token}")
    }

    pub fn default_tenant_id(&self) -> Uuid {
        Uuid::parse_str("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa").unwrap()
    }

    pub fn default_user_id(&self) -> Uuid {
        Uuid::parse_str("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb").unwrap()
    }

    /// Insert a widget directly into the database (bypasses the API).
    pub async fn seed_widget(&self, tenant_id: Uuid, name: &str) -> serde_json::Value {
        let id = Uuid::new_v4();
        let now = chrono::Utc::now();
        let user_id = self.default_user_id();

        sqlx::query!(
            r#"
            INSERT INTO widgets (id, tenant_id, name, description, status,
                                 created_at, updated_at, created_by, updated_by, version)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            "#,
            id, tenant_id, name, "seeded", "active", now, now, user_id, user_id, 1_i32,
        )
        .execute(&self.pool)
        .await
        .expect("seed_widget insert must succeed");

        serde_json::json!({
            "id": id.to_string(),
            "name": name,
            "version": 1,
        })
    }
}

/// Spawn a fresh test application with an isolated database.
pub async fn spawn_app() -> TestApp {
    // 1. Create a unique test database
    let db_name = format!("test_{}", Uuid::new_v4().to_string().replace('-', ""));
    let maintenance_url = std::env::var("DATABASE_URL")
        .unwrap_or_else(|_| "postgres://postgres:postgres@localhost:5432/postgres".into());

    let maintenance_pool = PgPool::connect(&maintenance_url)
        .await
        .expect("failed to connect to maintenance DB");

    maintenance_pool
        .execute(format!(r#"CREATE DATABASE "{db_name}""#).as_str())
        .await
        .expect("failed to create test database");

    let db_url = format!(
        "postgres://postgres:postgres@localhost:5432/{db_name}"
    );

    // 2. Connect and run migrations
    let pool = PgPool::connect(&db_url)
        .await
        .expect("failed to connect to test DB");

    sqlx::migrate!("./migrations")
        .run(&pool)
        .await
        .expect("failed to run migrations");

    // 3. Build and spawn the app on port 0 (OS assigns random port)
    let mut config = Config::test_defaults();
    config.database_url = db_url;
    config.jwt_secret = "test-secret".into();

    let app = build_app(config, pool.clone()).await;

    let listener = tokio::net::TcpListener::bind("127.0.0.1:0")
        .await
        .expect("failed to bind random port");
    let addr = listener.local_addr().unwrap();

    tokio::spawn(async move {
        axum::serve(listener, app).await.unwrap();
    });

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(10))
        .build()
        .expect("failed to build reqwest client");

    TestApp {
        addr,
        port: addr.port(),
        pool,
        client,
        db_name,
    }
}

/// Cleanup: drop the test database after all tests complete.
impl Drop for TestApp {
    fn drop(&mut self) {
        let db_name = self.db_name.clone();
        // Best-effort cleanup — can't use async in Drop, so spawn a blocking task.
        // In practice, a CI cleanup script also handles stale test DBs.
        let _ = std::thread::spawn(move || {
            let rt = tokio::runtime::Runtime::new().unwrap();
            rt.block_on(async {
                let maintenance_url = std::env::var("DATABASE_URL")
                    .unwrap_or_else(|_| "postgres://postgres:postgres@localhost:5432/postgres".into());
                if let Ok(pool) = PgPool::connect(&maintenance_url).await {
                    // Terminate active connections before dropping
                    let _ = pool
                        .execute(
                            format!(
                                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{db_name}'"
                            ).as_str(),
                        )
                        .await;
                    let _ = pool.execute(format!(r#"DROP DATABASE IF EXISTS "{db_name}""#).as_str()).await;
                }
            });
        });
    }
}
```

## Assertion Helpers

```rust
// tests/api/helpers.rs (continued)

use serde_json::Value;

/// Assert HTTP response has expected status code and return parsed JSON body.
pub async fn assert_json_response(resp: reqwest::Response, expected_status: u16) -> Value {
    let status = resp.status().as_u16();
    let body_text = resp.text().await.expect("failed to read response body");

    assert_eq!(
        status, expected_status,
        "expected status {expected_status}, got {status}; body: {body_text}"
    );

    serde_json::from_str(&body_text).expect("response is not valid JSON")
}

/// Assert the response is an error envelope (api/response-envelope.md) with the expected
/// status and code; returns the parsed body for further checks.
pub async fn assert_error_response(
    resp: reqwest::Response,
    expected_status: u16,
    expected_code: &str,
) -> Value {
    let header_request_id = resp.headers()
        .get("x-request-id")
        .and_then(|v| v.to_str().ok())
        .map(str::to_owned);
    let body = assert_json_response(resp, expected_status).await;

    // {"error": {code, message, details?, request_id, retryable}} — never a 'data' key
    assert!(body.get("data").is_none(), "success and error are exclusive: no 'data' in an error body");
    let error = body.get("error").expect("missing 'error' key in response");
    assert_eq!(
        error.get("code").and_then(|v| v.as_str()),
        Some(expected_code),
        "expected error code '{expected_code}', got: {error}"
    );
    assert!(
        error.get("message").and_then(|v| v.as_str()).is_some_and(|m| !m.is_empty()),
        "error must have a non-empty 'message'"
    );
    let request_id = error.get("request_id")
        .and_then(|v| v.as_str())
        .expect("error must have 'request_id'");
    assert!(!request_id.is_empty(), "'request_id' must not be empty");
    assert_eq!(
        header_request_id.as_deref(),
        Some(request_id),
        "X-Request-Id header must equal error.request_id"
    );
    assert!(
        error.get("retryable").is_some_and(Value::is_boolean),
        "error must have a boolean 'retryable'"
    );
    assert!(error.get("detail").is_none(), "no technical 'detail' field");
    body
}

/// Assert a single-resource success envelope: exactly 'data' + 'meta', 'meta.request_id', no pagination.
pub fn assert_envelope(body: &Value) {
    let obj = body.as_object().expect("response must be a JSON object");
    assert!(obj.contains_key("data"), "response must have 'data' key");
    assert!(obj.contains_key("meta"), "response must have 'meta' key");
    assert!(!obj.contains_key("error"), "success and error are exclusive");

    let meta = &body["meta"];
    assert!(
        meta["request_id"].as_str().is_some_and(|s| !s.is_empty()),
        "meta must have 'request_id'"
    );
    assert!(meta.get("pagination").is_none(), "a single resource has no pagination");
}

/// Assert a list envelope: 'data' is an array ([] when empty) and 'meta.pagination' has
/// 'next_cursor' (string or null), 'has_more' and 'limit'.
pub fn assert_list_envelope(body: &Value) {
    let obj = body.as_object().expect("response must be a JSON object");
    assert_eq!(obj.len(), 2, "only 'data' and 'meta' at the top level");
    assert!(body["data"].is_array(), "'data' must be an array");

    let meta = &body["meta"];
    assert!(
        meta["request_id"].as_str().is_some_and(|s| !s.is_empty()),
        "meta must have 'request_id'"
    );
    let pagination = meta.get("pagination").expect("list responses carry meta.pagination");
    let next = pagination.get("next_cursor").expect("pagination must have 'next_cursor'");
    assert!(next.is_string() || next.is_null(), "'next_cursor' is a string or null");
    assert!(pagination["has_more"].is_boolean(), "pagination must have 'has_more'");
    assert!(pagination["limit"].is_u64(), "pagination must have 'limit'");
}
```

## Helper Macros

```rust
// tests/api/helpers.rs (continued)

/// Macro: assert response status and extract JSON body.
#[macro_export]
macro_rules! assert_status {
    ($resp:expr, $status:expr) => {{
        let resp = $resp;
        let status = resp.status().as_u16();
        let body = resp.text().await.expect("read body");
        assert_eq!(status, $status, "status mismatch; body: {body}");
        serde_json::from_str::<serde_json::Value>(&body).ok()
    }};
}

/// Macro: build a POST/PUT JSON request with auth header.
#[macro_export]
macro_rules! json_request {
    ($client:expr, $method:ident, $url:expr, $body:expr, $auth:expr) => {{
        $client
            .$method($url)
            .header("Content-Type", "application/json")
            .header("Authorization", $auth)
            .json($body)
    }};
}
```

## Create Endpoint Tests

```rust
// tests/api/widget_test.rs

use crate::helpers::{
    spawn_app, assert_json_response, assert_error_response, assert_envelope, assert_list_envelope,
};
use serde_json::json;
use uuid::Uuid;

#[tokio::test]
async fn create_widget_happy_path() {
    let app = spawn_app().await;
    let auth = app.default_auth_header();

    let body = json!({
        "name": "Test Widget",
        "description": "A fine widget"
    });

    let resp = app.client
        .post(app.url("/api/v1/widgets"))
        .header("Authorization", &auth)
        .header("Content-Type", "application/json")
        .json(&body)
        .send()
        .await
        .expect("request failed");

    let json = assert_json_response(resp, 201).await;
    assert_envelope(&json);

    let data = json.get("data").unwrap();
    assert_eq!(data.get("name").unwrap().as_str(), Some("Test Widget"));
    assert_eq!(data.get("version").unwrap().as_i64(), Some(1));
    assert!(data.get("id").is_some());
    assert!(data.get("created_at").is_some());
    assert!(data.get("updated_at").is_some());
}

#[tokio::test]
async fn create_widget_invalid_json() {
    let app = spawn_app().await;
    let auth = app.default_auth_header();

    let resp = app.client
        .post(app.url("/api/v1/widgets"))
        .header("Authorization", &auth)
        .header("Content-Type", "application/json")
        .body("{invalid json")
        .send()
        .await
        .expect("request failed");

    // Malformed JSON -> 400 MALFORMED_REQUEST (not 422, not VALIDATION_FAILED)
    assert_error_response(resp, 400, "MALFORMED_REQUEST").await;
}

#[tokio::test]
async fn create_widget_empty_body() {
    let app = spawn_app().await;
    let auth = app.default_auth_header();

    let resp = app.client
        .post(app.url("/api/v1/widgets"))
        .header("Authorization", &auth)
        .header("Content-Type", "application/json")
        .send()
        .await
        .expect("request failed");

    assert_error_response(resp, 400, "MALFORMED_REQUEST").await;
}

#[tokio::test]
async fn create_widget_validation_error_empty_name() {
    let app = spawn_app().await;
    let auth = app.default_auth_header();

    let body = json!({
        "name": "",
        "description": "desc"
    });

    let resp = app.client
        .post(app.url("/api/v1/widgets"))
        .header("Authorization", &auth)
        .json(&body)
        .send()
        .await
        .expect("request failed");

    // Field validation -> 400 VALIDATION_FAILED with details[] {field, code, message}
    let json = assert_error_response(resp, 400, "VALIDATION_FAILED").await;
    let details = json["error"]["details"].as_array().expect("details must be an array");
    assert_eq!(details[0]["field"].as_str(), Some("name"));
    assert!(details[0]["code"].as_str().is_some());
}

#[tokio::test]
async fn create_widget_validation_error_name_too_long() {
    let app = spawn_app().await;
    let auth = app.default_auth_header();

    let body = json!({
        "name": "x".repeat(256),
        "description": "desc"
    });

    let resp = app.client
        .post(app.url("/api/v1/widgets"))
        .header("Authorization", &auth)
        .json(&body)
        .send()
        .await
        .expect("request failed");

    assert_error_response(resp, 400, "VALIDATION_FAILED").await;
}
```

## Get Endpoint Tests

```rust
#[tokio::test]
async fn get_widget_happy_path() {
    let app = spawn_app().await;
    let auth = app.default_auth_header();
    let tenant_id = app.default_tenant_id();

    let seeded = app.seed_widget(tenant_id, "Existing Widget").await;
    let widget_id = seeded["id"].as_str().unwrap();

    let resp = app.client
        .get(app.url(&format!("/api/v1/widgets/{widget_id}")))
        .header("Authorization", &auth)
        .send()
        .await
        .expect("request failed");

    let json = assert_json_response(resp, 200).await;
    assert_envelope(&json);

    let data = json.get("data").unwrap();
    assert_eq!(data["id"].as_str(), Some(widget_id));
    assert_eq!(data["name"].as_str(), Some("Existing Widget"));
}

#[tokio::test]
async fn get_widget_not_found() {
    let app = spawn_app().await;
    let auth = app.default_auth_header();
    let random_id = Uuid::new_v4();

    let resp = app.client
        .get(app.url(&format!("/api/v1/widgets/{random_id}")))
        .header("Authorization", &auth)
        .send()
        .await
        .expect("request failed");

    assert_error_response(resp, 404, "NOT_FOUND").await;
}

#[tokio::test]
async fn get_widget_invalid_uuid() {
    let app = spawn_app().await;
    let auth = app.default_auth_header();

    let resp = app.client
        .get(app.url("/api/v1/widgets/not-a-uuid"))
        .header("Authorization", &auth)
        .send()
        .await
        .expect("request failed");

    assert_error_response(resp, 400, "VALIDATION_FAILED").await;
}
```

## Update Endpoint Tests

```rust
#[tokio::test]
async fn update_widget_happy_path() {
    let app = spawn_app().await;
    let auth = app.default_auth_header();
    let tenant_id = app.default_tenant_id();

    let seeded = app.seed_widget(tenant_id, "Old Name").await;
    let widget_id = seeded["id"].as_str().unwrap();

    let body = json!({
        "name": "Updated Name",
        "description": "Updated description",
        "version": 1
    });

    let resp = app.client
        .put(app.url(&format!("/api/v1/widgets/{widget_id}")))
        .header("Authorization", &auth)
        .json(&body)
        .send()
        .await
        .expect("request failed");

    let json = assert_json_response(resp, 200).await;
    assert_envelope(&json);

    let data = json.get("data").unwrap();
    assert_eq!(data["name"].as_str(), Some("Updated Name"));
    assert_eq!(data["version"].as_i64(), Some(2)); // version incremented
}

#[tokio::test]
async fn update_widget_version_conflict() {
    let app = spawn_app().await;
    let auth = app.default_auth_header();
    let tenant_id = app.default_tenant_id();

    let seeded = app.seed_widget(tenant_id, "Widget").await;
    let widget_id = seeded["id"].as_str().unwrap();

    // First update (version 1 -> 2)
    let body = json!({
        "name": "First Update",
        "version": 1
    });
    let resp = app.client
        .put(app.url(&format!("/api/v1/widgets/{widget_id}")))
        .header("Authorization", &auth)
        .json(&body)
        .send()
        .await
        .expect("request failed");
    assert_eq!(resp.status().as_u16(), 200);

    // Second update with stale version (still sends version 1)
    let stale_body = json!({
        "name": "Stale Update",
        "version": 1
    });
    let resp = app.client
        .put(app.url(&format!("/api/v1/widgets/{widget_id}")))
        .header("Authorization", &auth)
        .json(&stale_body)
        .send()
        .await
        .expect("request failed");

    assert_error_response(resp, 409, "CONFLICT").await;
}

#[tokio::test]
async fn update_widget_not_found() {
    let app = spawn_app().await;
    let auth = app.default_auth_header();
    let random_id = Uuid::new_v4();

    let body = json!({
        "name": "Updated",
        "version": 1
    });

    let resp = app.client
        .put(app.url(&format!("/api/v1/widgets/{random_id}")))
        .header("Authorization", &auth)
        .json(&body)
        .send()
        .await
        .expect("request failed");

    assert_error_response(resp, 404, "NOT_FOUND").await;
}

#[tokio::test]
async fn update_widget_invalid_json() {
    let app = spawn_app().await;
    let auth = app.default_auth_header();
    let random_id = Uuid::new_v4();

    let resp = app.client
        .put(app.url(&format!("/api/v1/widgets/{random_id}")))
        .header("Authorization", &auth)
        .header("Content-Type", "application/json")
        .body("{bad json")
        .send()
        .await
        .expect("request failed");

    assert_error_response(resp, 400, "MALFORMED_REQUEST").await;
}
```

## Delete Endpoint Tests

```rust
#[tokio::test]
async fn delete_widget_happy_path() {
    let app = spawn_app().await;
    let auth = app.default_auth_header();
    let tenant_id = app.default_tenant_id();

    let seeded = app.seed_widget(tenant_id, "To Delete").await;
    let widget_id = seeded["id"].as_str().unwrap();

    let resp = app.client
        .delete(app.url(&format!("/api/v1/widgets/{widget_id}")))
        .header("Authorization", &auth)
        .send()
        .await
        .expect("request failed");

    // DELETE returns 204 No Content with empty body
    assert_eq!(resp.status().as_u16(), 204);
    let body = resp.text().await.unwrap();
    assert!(body.is_empty(), "DELETE 204 must have empty body");

    // Verify it's gone (soft-deleted)
    let get_resp = app.client
        .get(app.url(&format!("/api/v1/widgets/{widget_id}")))
        .header("Authorization", &auth)
        .send()
        .await
        .expect("request failed");

    assert_error_response(get_resp, 404, "NOT_FOUND").await;
}

#[tokio::test]
async fn delete_widget_not_found() {
    let app = spawn_app().await;
    let auth = app.default_auth_header();
    let random_id = Uuid::new_v4();

    let resp = app.client
        .delete(app.url(&format!("/api/v1/widgets/{random_id}")))
        .header("Authorization", &auth)
        .send()
        .await
        .expect("request failed");

    assert_error_response(resp, 404, "NOT_FOUND").await;
}

#[tokio::test]
async fn delete_widget_invalid_uuid() {
    let app = spawn_app().await;
    let auth = app.default_auth_header();

    let resp = app.client
        .delete(app.url("/api/v1/widgets/xyz"))
        .header("Authorization", &auth)
        .send()
        .await
        .expect("request failed");

    assert_error_response(resp, 400, "VALIDATION_FAILED").await;
}

#[tokio::test]
async fn delete_widget_idempotent() {
    let app = spawn_app().await;
    let auth = app.default_auth_header();
    let tenant_id = app.default_tenant_id();

    let seeded = app.seed_widget(tenant_id, "To Delete Twice").await;
    let widget_id = seeded["id"].as_str().unwrap();

    // First delete succeeds
    let resp = app.client
        .delete(app.url(&format!("/api/v1/widgets/{widget_id}")))
        .header("Authorization", &auth)
        .send()
        .await
        .expect("request failed");
    assert_eq!(resp.status().as_u16(), 204);

    // Second delete returns 404 (already soft-deleted)
    let resp = app.client
        .delete(app.url(&format!("/api/v1/widgets/{widget_id}")))
        .header("Authorization", &auth)
        .send()
        .await
        .expect("request failed");
    assert_error_response(resp, 404, "NOT_FOUND").await;
}
```

## List with Cursor Pagination Tests

```rust
#[tokio::test]
async fn list_widgets_happy_path() {
    let app = spawn_app().await;
    let auth = app.default_auth_header();
    let tenant_id = app.default_tenant_id();

    // Seed 5 widgets
    for i in 0..5 {
        app.seed_widget(tenant_id, &format!("Widget {i}")).await;
    }

    let resp = app.client
        .get(app.url("/api/v1/widgets?limit=3&sort_by=created_at&sort_dir=desc"))
        .header("Authorization", &auth)
        .send()
        .await
        .expect("request failed");

    let json = assert_json_response(resp, 200).await;
    assert_list_envelope(&json);

    let data = json["data"].as_array().unwrap();
    assert_eq!(data.len(), 3);
    let pagination = &json["meta"]["pagination"];
    assert_eq!(pagination["has_more"].as_bool(), Some(true));
    assert_eq!(pagination["limit"].as_i64(), Some(3));
    assert!(pagination["next_cursor"].as_str().is_some());
}

#[tokio::test]
async fn list_widgets_empty() {
    let app = spawn_app().await;
    let auth = app.default_auth_header();

    let resp = app.client
        .get(app.url("/api/v1/widgets"))
        .header("Authorization", &auth)
        .send()
        .await
        .expect("request failed");

    let json = assert_json_response(resp, 200).await;
    assert_list_envelope(&json);

    let data = json["data"].as_array().expect("empty list is [] — never null");
    assert_eq!(data.len(), 0);
    let pagination = &json["meta"]["pagination"];
    assert_eq!(pagination["has_more"].as_bool(), Some(false));
    assert!(pagination["next_cursor"].is_null(), "next_cursor is null when has_more is false");
}

#[tokio::test]
async fn list_widgets_cursor_pagination() {
    let app = spawn_app().await;
    let auth = app.default_auth_header();
    let tenant_id = app.default_tenant_id();

    // Seed 5 widgets
    for i in 0..5 {
        app.seed_widget(tenant_id, &format!("Widget {i}")).await;
        // Small delay to ensure distinct created_at values for cursor ordering
        tokio::time::sleep(std::time::Duration::from_millis(10)).await;
    }

    // Page 1: get first 3
    let resp = app.client
        .get(app.url("/api/v1/widgets?limit=3"))
        .header("Authorization", &auth)
        .send()
        .await
        .unwrap();

    let json = assert_json_response(resp, 200).await;
    let page1_data = json["data"].as_array().unwrap();
    assert_eq!(page1_data.len(), 3);
    assert_eq!(json["meta"]["pagination"]["has_more"].as_bool(), Some(true));

    let cursor = json["meta"]["pagination"]["next_cursor"].as_str().unwrap();

    // Page 2: follow next_cursor to get the remaining items
    let resp = app.client
        .get(app.url(&format!("/api/v1/widgets?limit=3&cursor={cursor}")))
        .header("Authorization", &auth)
        .send()
        .await
        .unwrap();

    let json = assert_json_response(resp, 200).await;
    let page2_data = json["data"].as_array().unwrap();
    assert_eq!(page2_data.len(), 2);
    assert_eq!(json["meta"]["pagination"]["has_more"].as_bool(), Some(false));
    assert!(json["meta"]["pagination"]["next_cursor"].is_null());

    // Verify no overlap between pages
    let page1_ids: Vec<&str> = page1_data.iter()
        .map(|w| w["id"].as_str().unwrap())
        .collect();
    let page2_ids: Vec<&str> = page2_data.iter()
        .map(|w| w["id"].as_str().unwrap())
        .collect();
    for id in &page2_ids {
        assert!(!page1_ids.contains(id), "cursor pagination must not overlap");
    }
}

#[tokio::test]
async fn list_widgets_limit_defaults_and_caps() {
    let app = spawn_app().await;
    let auth = app.default_auth_header();

    // limit defaults to 20 when missing, zero or negative; capped at 100
    for (query, expected) in [
        ("", 20),
        ("?limit=0", 20),
        ("?limit=-5", 20),
        ("?limit=500", 100),
        ("?limit=50", 50),
    ] {
        let resp = app.client
            .get(app.url(&format!("/api/v1/widgets{query}")))
            .header("Authorization", &auth)
            .send()
            .await
            .unwrap();

        let json = assert_json_response(resp, 200).await;
        assert_eq!(
            json["meta"]["pagination"]["limit"].as_i64(),
            Some(expected),
            "limit for '{query}'"
        );
    }
}

#[tokio::test]
async fn list_widgets_sort_validation() {
    let app = spawn_app().await;
    let auth = app.default_auth_header();

    // Unknown sort_by defaults to "created_at", invalid sort_dir defaults to "desc"
    let resp = app.client
        .get(app.url("/api/v1/widgets?sort_by=drop_table&sort_dir=invalid"))
        .header("Authorization", &auth)
        .send()
        .await
        .unwrap();

    // Must not error — invalid sort fields are silently defaulted
    assert_eq!(resp.status().as_u16(), 200);
}

#[tokio::test]
async fn list_widgets_filter_params() {
    let app = spawn_app().await;
    let auth = app.default_auth_header();

    let resp = app.client
        .get(app.url("/api/v1/widgets?filter[status]=active&filter[priority]=high"))
        .header("Authorization", &auth)
        .send()
        .await
        .unwrap();

    assert_eq!(resp.status().as_u16(), 200);
}

#[tokio::test]
async fn list_widgets_disallowed_filter_ignored() {
    let app = spawn_app().await;
    let auth = app.default_auth_header();

    // "password" filter must not be passed to the DB
    let resp = app.client
        .get(app.url("/api/v1/widgets?filter[password]=secret"))
        .header("Authorization", &auth)
        .send()
        .await
        .unwrap();

    assert_eq!(resp.status().as_u16(), 200);
}
```

## Auth Tests

```rust
#[tokio::test]
async fn auth_missing_authorization_header() {
    let app = spawn_app().await;

    let resp = app.client
        .get(app.url("/api/v1/widgets"))
        .send()
        .await
        .expect("request failed");

    assert_eq!(
        resp.headers().get("www-authenticate").and_then(|v| v.to_str().ok()),
        Some("Bearer"),
        "401 responses carry WWW-Authenticate: Bearer"
    );
    assert_error_response(resp, 401, "UNAUTHENTICATED").await;
}

#[tokio::test]
async fn auth_invalid_jwt_token() {
    let app = spawn_app().await;

    let resp = app.client
        .get(app.url("/api/v1/widgets"))
        .header("Authorization", "Bearer invalid.jwt.token")
        .send()
        .await
        .expect("request failed");

    assert_error_response(resp, 401, "UNAUTHENTICATED").await;
}

#[tokio::test]
async fn auth_expired_jwt_token() {
    let app = spawn_app().await;

    use jsonwebtoken::{encode, EncodingKey, Header};
    use yourapp::auth::JwtClaims;

    let claims = JwtClaims {
        sub: Uuid::new_v4(),
        tenant_id: Uuid::new_v4(),
        roles: vec!["admin".into()],
        exp: 1000000000, // long expired
        iat: 999999000,
    };
    let token = encode(
        &Header::default(),
        &claims,
        &EncodingKey::from_secret(b"test-secret"),
    )
    .unwrap();

    let resp = app.client
        .get(app.url("/api/v1/widgets"))
        .header("Authorization", format!("Bearer {token}"))
        .send()
        .await
        .expect("request failed");

    assert_error_response(resp, 401, "UNAUTHENTICATED").await;
}

#[tokio::test]
async fn auth_wrong_role_forbidden() {
    let app = spawn_app().await;

    // Generate token with "viewer" role — cannot create
    let token = app.auth_token(
        app.default_tenant_id(),
        app.default_user_id(),
        vec!["viewer".into()],
    );

    let body = json!({
        "name": "Forbidden Widget"
    });

    let resp = app.client
        .post(app.url("/api/v1/widgets"))
        .header("Authorization", format!("Bearer {token}"))
        .json(&body)
        .send()
        .await
        .expect("request failed");

    assert_error_response(resp, 403, "FORBIDDEN").await;
}

#[tokio::test]
async fn auth_wrong_tenant_returns_not_found() {
    let app = spawn_app().await;
    let tenant_a = app.default_tenant_id();
    let tenant_b = Uuid::new_v4();

    // Seed widget for tenant A
    let seeded = app.seed_widget(tenant_a, "Tenant A Widget").await;
    let widget_id = seeded["id"].as_str().unwrap();

    // Request with tenant B credentials
    let token_b = app.auth_token(tenant_b, Uuid::new_v4(), vec!["admin".into()]);

    let resp = app.client
        .get(app.url(&format!("/api/v1/widgets/{widget_id}")))
        .header("Authorization", format!("Bearer {token_b}"))
        .send()
        .await
        .expect("request failed");

    // CRITICAL: wrong tenant sees 404, not 403 — prevents enumeration attacks
    assert_error_response(resp, 404, "NOT_FOUND").await;
}
```

## Error Response Shape Tests

```rust
#[tokio::test]
async fn response_shape_single_resource() {
    let app = spawn_app().await;
    let auth = app.default_auth_header();
    let tenant_id = app.default_tenant_id();

    let seeded = app.seed_widget(tenant_id, "Shape Test").await;
    let widget_id = seeded["id"].as_str().unwrap();

    let resp = app.client
        .get(app.url(&format!("/api/v1/widgets/{widget_id}")))
        .header("Authorization", &auth)
        .send()
        .await
        .unwrap();

    let json = assert_json_response(resp, 200).await;

    // Must have exactly "data" and "meta" top-level keys
    let obj = json.as_object().unwrap();
    assert!(obj.contains_key("data"));
    assert!(obj.contains_key("meta"));
    assert_eq!(obj.len(), 2, "response should only have 'data' and 'meta' keys");

    // data must contain expected widget fields
    let data = &json["data"];
    for field in &["id", "name", "version", "created_at", "updated_at"] {
        assert!(data.get(field).is_some(), "data must contain '{field}'");
    }

    // meta carries request_id; a single resource has no pagination
    let meta = &json["meta"];
    assert!(meta.get("request_id").is_some());
    assert!(meta.get("pagination").is_none());
}

#[tokio::test]
async fn response_shape_error_envelope() {
    let app = spawn_app().await;
    let auth = app.default_auth_header();

    let resp = app.client
        .get(app.url(&format!("/api/v1/widgets/{}", Uuid::new_v4())))
        .header("Authorization", &auth)
        .send()
        .await
        .unwrap();

    let json = assert_error_response(resp, 404, "NOT_FOUND").await;

    // Error envelope: {"error": {"code", "message", "details"?, "request_id", "retryable"}} — no "data"
    assert_eq!(json.as_object().unwrap().len(), 1, "an error body has only the 'error' key");
    let error = &json["error"];
    for key in ["code", "message", "request_id", "retryable"] {
        assert!(error.get(key).is_some(), "error must contain '{key}'");
    }
}

#[tokio::test]
async fn internal_error_does_not_leak_details() {
    // This test requires a way to trigger an internal error.
    // One approach: close the DB pool and then make a request.
    let app = spawn_app().await;
    let auth = app.default_auth_header();

    // Force-close all pool connections to trigger an internal error
    app.pool.close().await;

    let resp = app.client
        .get(app.url("/api/v1/widgets"))
        .header("Authorization", &auth)
        .send()
        .await
        .expect("request failed");

    let json = assert_error_response(resp, 500, "INTERNAL").await;
    assert_eq!(json["error"]["retryable"].as_bool(), Some(false));

    // CRITICAL: Internal errors must NOT leak database details anywhere in the body
    let body = serde_json::to_string(&json).unwrap();
    assert!(!body.contains("postgres"), "must not leak DB details");
    assert!(!body.contains("connection"), "must not leak connection info");
    assert!(!body.contains("pool"), "must not leak pool info");
}
```

## Critical Rules

- Every integration test MUST use `spawn_app()` to get an isolated test instance with its own database
- Every test database MUST be created fresh and cleaned up after tests
- Malformed JSON MUST return 400 `MALFORMED_REQUEST`; failed field validation 400 `VALIDATION_FAILED`; a domain rule 422 `BUSINESS_RULE_VIOLATION`
- Wrong tenant MUST return 404 Not Found, not 403 Forbidden — prevents entity enumeration
- Internal errors MUST NOT leak error details to the client — assert the 500 `INTERNAL` body has no driver/pool text
- Every response MUST follow `~/.claude/skills/api/response-envelope.md`: `{"data": T, "meta": {"request_id"}}` for success, `{"error": {code, message, details?, request_id, retryable}}` for failure, never both
- Every error assertion MUST check `request_id` (= `X-Request-Id` header) and `retryable` — use `assert_error_response`
- DELETE MUST return 204 with empty body
- POST create MUST return 201 Created
- List responses MUST include `meta.pagination` `{next_cursor, has_more, limit}`; `data` is `[]` when empty; `next_cursor` is null when `has_more` is false
- `limit` MUST be clamped: default to 20 when missing/zero/negative, cap at 100
- Sort and filter fields MUST be allow-listed — disallowed values default to safe values
- Cursor pagination MUST produce non-overlapping pages
- Auth tests MUST cover: missing header (401 `UNAUTHENTICATED` + `WWW-Authenticate`), invalid JWT (401), expired JWT (401), wrong role (403 `FORBIDDEN`), wrong tenant (404 `NOT_FOUND`)
- Use `#[tokio::test]` on every async test function
- Every test function should be self-contained — no shared mutable state between tests
