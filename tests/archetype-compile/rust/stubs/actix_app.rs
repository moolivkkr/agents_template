// HARNESS STUBS — app names frameworks/actix-web.md (and languages/rust.md's actix handler) use but never
// define: the config loader, the widget handlers the routes name, the order service, and the test
// helpers its tests call. The doc's server setup, auth, envelope, request id, configs and tests are
// what is checked.
#![allow(dead_code)]
use actix_web::{web, HttpResponse};
use chrono::Utc;
use jsonwebtoken::{encode, EncodingKey, Header};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use crate::auth::extractor::AuthUser;
use crate::auth::middleware::JwtService;
use crate::error::AppError;
use crate::response::ApiResponse;
use crate::state::AppState;

#[derive(Clone)]
pub struct AppConfig {
    pub database_url: String,
    pub jwt_secret: String,
    pub jwt_issuer: String,
    pub jwt_audience: String,
}

impl AppConfig {
    /// Every value is required: a missing one is an error, never a compiled-in default.
    pub fn from_env() -> anyhow::Result<Self> {
        let var = |name: &str| std::env::var(name).map_err(|_| anyhow::anyhow!("{name} is not set"));
        Ok(Self {
            database_url: var("DATABASE_URL")?,
            jwt_secret: var("JWT_SECRET")?,
            jwt_issuer: var("JWT_ISSUER")?,
            jwt_audience: var("JWT_AUDIENCE")?,
        })
    }
}

#[derive(Deserialize)]
pub struct CreateInput {
    pub name: String,
    pub description: Option<String>,
}

#[derive(Deserialize)]
pub struct UpdateInput {
    pub name: Option<String>,
}

// The widget handlers api_config routes to (the Extractors section shows only their signatures).
// They answer from the verified AuthUser so the doc's tests run without a database.
pub async fn get_widget(user: AuthUser, path: web::Path<Uuid>) -> Result<HttpResponse, AppError> {
    let body = serde_json::json!({ "id": path.into_inner(), "tenant_id": user.tenant_id });
    Ok(HttpResponse::Ok().json(ApiResponse::success(body)))
}

pub async fn create_widget(user: AuthUser, body: web::Json<CreateInput>) -> Result<HttpResponse, AppError> {
    let body = serde_json::json!({ "id": Uuid::new_v4(), "name": body.name, "tenant_id": user.tenant_id });
    Ok(HttpResponse::Created().json(ApiResponse::success(body)))
}

pub async fn list_widgets(_user: AuthUser) -> HttpResponse {
    HttpResponse::NotImplemented().finish()
}

pub async fn update_widget(_user: AuthUser) -> HttpResponse {
    HttpResponse::NotImplemented().finish()
}

pub async fn delete_widget(_user: AuthUser) -> HttpResponse {
    HttpResponse::NotImplemented().finish()
}

// Test helpers the doc's tests call ("your test helpers"). No network: the pool connects lazily.
pub const TEST_ISSUER: &str = "https://auth.example.test";
pub const TEST_AUDIENCE: &str = "widgets-api";

pub struct Widget {
    pub id: Uuid,
    pub tenant_id: Uuid,
}

pub async fn test_app_state() -> AppState {
    let config = AppConfig {
        database_url: String::new(),
        jwt_secret: "test-secret-not-for-production".into(),
        jwt_issuer: TEST_ISSUER.into(),
        jwt_audience: TEST_AUDIENCE.into(),
    };
    AppState {
        db: sqlx::postgres::PgPoolOptions::new().connect_lazy("postgres://unused@127.0.0.1:1/unused").unwrap(),
        jwt: JwtService::new(&config.jwt_secret, &config.jwt_issuer, &config.jwt_audience),
        config,
    }
}

pub async fn seed_widget(_state: &AppState) -> Widget {
    Widget { id: Uuid::new_v4(), tenant_id: Uuid::new_v4() }
}

#[derive(Serialize)]
struct TestClaims<'a> {
    sub: Uuid,
    tenant_id: Uuid,
    exp: i64,
    iss: &'a str,
    aud: &'a str,
}

pub fn test_token(state: &AppState, tenant_id: Uuid) -> String {
    let claims = TestClaims {
        sub: Uuid::new_v4(),
        tenant_id,
        exp: (Utc::now() + chrono::Duration::minutes(5)).timestamp(),
        iss: &state.config.jwt_issuer,
        aud: &state.config.jwt_audience,
    };
    encode(&Header::default(), &claims, &EncodingKey::from_secret(state.config.jwt_secret.as_bytes())).unwrap()
}

// languages/rust.md "Actix-web Patterns": the order service and DTOs its handler uses
pub struct Order {
    pub id: Uuid,
}

#[derive(Serialize)]
pub struct OrderResponse {
    pub id: Uuid,
}

impl From<Order> for OrderResponse {
    fn from(order: Order) -> Self {
        Self { id: order.id }
    }
}

pub struct OrderService;

impl OrderService {
    pub async fn get_order(&self, _tenant_id: Uuid, id: Uuid) -> Result<Order, AppError> {
        Ok(Order { id })
    }
}

pub async fn create_order(_user: AuthUser) -> HttpResponse {
    HttpResponse::NotImplemented().finish()
}

pub async fn list_orders(_user: AuthUser) -> HttpResponse {
    HttpResponse::NotImplemented().finish()
}
