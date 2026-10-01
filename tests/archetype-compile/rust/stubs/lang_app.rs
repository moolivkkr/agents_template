// HARNESS STUBS — app names languages/rust.md's snippets call but never define (handlers the routes
// name, the config loader, the JWT check, and the placeholder types of the async/performance
// examples). The doc's own code — error mapping, envelope, extractor, handlers, middleware, queries,
// repository, tests — is what is being checked.
#![allow(dead_code)]
use std::sync::Arc;

use axum::{
    extract::{Request, State},
    http::StatusCode,
    middleware::Next,
    response::Response as AxumResponse,
    routing::get,
    Router,
};
use jsonwebtoken::{decode, Algorithm, DecodingKey, Validation};
use sqlx::PgPool;
use tokio::net::TcpStream;
use uuid::Uuid;

use crate::domain::Order;
use crate::error::DomainError;
use crate::extractors::Claims;
use crate::services::OrderService;

#[derive(Clone)]
pub struct AppState {
    pub order_service: Arc<OrderService>,
}

// The routes name these handlers; the snippet doesn't show them.
pub async fn get_order() -> StatusCode {
    StatusCode::NOT_IMPLEMENTED
}

pub async fn update_order() -> StatusCode {
    StatusCode::NOT_IMPLEMENTED
}

pub async fn delete_order() -> StatusCode {
    StatusCode::NOT_IMPLEMENTED
}

pub fn user_routes() -> Router<AppState> {
    Router::new().route("/users/me", get(|| async { StatusCode::NOT_IMPLEMENTED }))
}

// "Tower Middleware": the app's JWT check. auth-middleware-rust.md has the canonical one, written for
// its own state and error types; this one verifies HS256 with the harness test key and inserts
// languages/rust.md's Claims, which is all tenant_middleware relies on.
pub const TEST_JWT_SECRET: &[u8] = b"harness-test-secret";

pub async fn auth_middleware(State(_state): State<AppState>, mut req: Request, next: Next) -> Result<AxumResponse, DomainError> {
    let token = req
        .headers()
        .get("authorization")
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.strip_prefix("Bearer "))
        .ok_or(DomainError::Unauthenticated)?;
    let mut validation = Validation::new(Algorithm::HS256);
    validation.set_required_spec_claims(&["exp", "sub"]);
    let claims = decode::<Claims>(token, &DecodingKey::from_secret(TEST_JWT_SECRET), &validation)
        .map_err(|_| DomainError::Unauthenticated)?
        .claims;
    req.extensions_mut().insert(claims);
    Ok(next.run(req).await)
}

// "anyhow for Application/Binary Code"
pub struct Config {
    pub database_url: String,
}

pub fn load_config() -> Result<Config, std::env::VarError> {
    Ok(Config { database_url: std::env::var("DATABASE_URL")? })
}

pub async fn serve(_config: Config, _pool: PgPool) -> anyhow::Result<()> {
    Ok(())
}

// "Zero-Cost Abstractions"
pub struct EmailNotification;
pub struct SmsNotification;
pub struct PushNotification;

// "Arc, Mutex, and Channels"
pub struct CachedValue;

#[derive(Debug)]
pub enum Job {
    ProcessOrder(Uuid),
}

pub async fn process_job(_job: Job) {}

// "Tokio Runtime Configuration"
pub async fn run_server() -> anyhow::Result<()> {
    Ok(())
}

// "tokio::select!"
pub struct Response;

pub async fn fetch(_url: &str) -> Result<Response, DomainError> {
    Ok(Response)
}

pub async fn handle_connection(_stream: TcpStream) {}

// "tokio::join!"
pub struct User;
pub struct Preferences;

pub struct UserProfile {
    pub user: User,
    pub orders: Vec<Order>,
    pub preferences: Preferences,
}

pub struct UserRepo;
pub struct UserOrderRepo;
pub struct PreferenceRepo;

impl UserRepo {
    pub async fn find_by_id(&self, _tenant_id: Uuid, _id: Uuid) -> Result<Option<User>, DomainError> {
        Ok(Some(User))
    }
}

impl UserOrderRepo {
    pub async fn find_by_user(&self, _tenant_id: Uuid, _user_id: Uuid) -> Result<Vec<Order>, DomainError> {
        Ok(Vec::new())
    }
}

impl PreferenceRepo {
    pub async fn find_by_user(&self, _tenant_id: Uuid, _user_id: Uuid) -> Result<Preferences, DomainError> {
        Ok(Preferences)
    }
}

pub struct ProfileService {
    pub user_repo: UserRepo,
    pub order_repo: UserOrderRepo,
    pub pref_repo: PreferenceRepo,
}

// "Streaming with futures::Stream"
pub struct Item;
pub struct ProcessedItem;

pub async fn process_item(_item: Item) -> Result<ProcessedItem, DomainError> {
    Ok(ProcessedItem)
}
