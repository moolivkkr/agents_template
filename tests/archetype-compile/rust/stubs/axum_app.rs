// HARNESS STUBS — app names frameworks/axum.md's snippets use but never define: the config, the JWT
// service, the widget handlers the router names, the panic layer, and the test helpers its router test
// calls. The doc's router, auth middleware, state, shutdown, envelope and tests are what is checked.
#![allow(dead_code)]
use std::sync::Arc;

use axum::{
    extract::{Extension, Request},
    http::StatusCode,
    middleware::Next,
    response::{IntoResponse, Response},
    routing::get,
    Json, Router,
};
use jsonwebtoken::{decode, encode, Algorithm, DecodingKey, EncodingKey, Header, Validation};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use crate::error::AppPath;
use crate::response::ApiResponse;
use crate::state::AppState;

#[derive(Clone)]
pub struct AppConfig {
    pub database_url: String,
    pub redis_url: String,
    pub jwt_secret: String,
}

const ISSUER: &str = "https://auth.example.test";
const AUDIENCE: &str = "widgets-api";

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Claims {
    pub sub: Uuid,
    pub tenant_id: Uuid,
    pub exp: i64,
    pub iss: String,
    pub aud: String,
}

/// HS256 verifier: signature, exp, iss and aud (what the doc's comment says it checks).
pub struct JwtService {
    decoding: DecodingKey,
    encoding: EncodingKey,
    validation: Validation,
}

impl JwtService {
    pub fn new(secret: &str) -> Self {
        let mut validation = Validation::new(Algorithm::HS256);
        validation.set_issuer(&[ISSUER]);
        validation.set_audience(&[AUDIENCE]);
        validation.set_required_spec_claims(&["exp", "iss", "aud", "sub"]);
        Self {
            decoding: DecodingKey::from_secret(secret.as_bytes()),
            encoding: EncodingKey::from_secret(secret.as_bytes()),
            validation,
        }
    }

    pub fn verify(&self, token: &str) -> Result<Claims, jsonwebtoken::errors::Error> {
        decode::<Claims>(token, &self.decoding, &self.validation).map(|data| data.claims)
    }
}

// error-handling-rust.md has the real recovery_middleware (panic → 500 envelope), written for its own
// AppError; a pass-through here keeps the router's layer order as the doc shows it.
pub async fn recovery_middleware(req: Request, next: Next) -> Response {
    next.run(req).await
}

pub fn user_routes() -> Router<Arc<AppState>> {
    Router::new().route("/me", get(|| async { StatusCode::NOT_IMPLEMENTED }))
}

// The widget handlers the router names (frameworks/axum.md shows only their signatures). get_widget
// answers from the verified claims so the router test can run without a database.
pub async fn get_widget(Extension(claims): Extension<Claims>, AppPath(id): AppPath<Uuid>) -> impl IntoResponse {
    Json(ApiResponse::success(serde_json::json!({ "id": id, "tenant_id": claims.tenant_id })))
}

pub async fn list_widgets() -> StatusCode {
    StatusCode::NOT_IMPLEMENTED
}

pub async fn create_widget() -> StatusCode {
    StatusCode::NOT_IMPLEMENTED
}

pub async fn update_widget() -> StatusCode {
    StatusCode::NOT_IMPLEMENTED
}

pub async fn delete_widget() -> StatusCode {
    StatusCode::NOT_IMPLEMENTED
}

// The Extractors section's DTOs
#[derive(Deserialize)]
pub struct ListParams {
    pub limit: Option<i64>,
    pub cursor: Option<String>,
}

#[derive(Deserialize)]
pub struct CreateInput {
    pub name: String,
}

#[derive(Deserialize)]
pub struct UpdateInput {
    pub name: Option<String>,
}

// Test helpers the router test calls ("your test helpers"). No network: the pools connect lazily.
pub struct Widget {
    pub id: Uuid,
    pub tenant_id: Uuid,
}

pub async fn test_app_state() -> AppState {
    AppState {
        db: sqlx::postgres::PgPoolOptions::new().connect_lazy("postgres://unused@127.0.0.1:1/unused").unwrap(),
        redis: deadpool_redis::Config::from_url("redis://127.0.0.1:1")
            .create_pool(Some(deadpool_redis::Runtime::Tokio1))
            .unwrap(),
        jwt: JwtService::new("test-secret-not-for-production"),
        config: AppConfig { database_url: String::new(), redis_url: String::new(), jwt_secret: String::new() },
    }
}

pub async fn seed_widget(_state: &AppState) -> Widget {
    Widget { id: Uuid::new_v4(), tenant_id: Uuid::new_v4() }
}

pub fn test_token(state: &AppState, tenant_id: Uuid) -> String {
    let claims = Claims {
        sub: Uuid::new_v4(),
        tenant_id,
        exp: (chrono::Utc::now() + chrono::Duration::minutes(5)).timestamp(),
        iss: ISSUER.into(),
        aud: AUDIENCE.into(),
    };
    encode(&Header::default(), &claims, &state.jwt.encoding).unwrap()
}
