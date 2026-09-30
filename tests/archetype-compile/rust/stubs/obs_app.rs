// HARNESS STUBS — the order-service domain observability-rust.md's examples are written against.
// No archetype defines these types; they exist so the doc's tracing / OpenTelemetry / metrics / axum
// code (the part being checked) has something to call. The doc's own methods are added to
// OrderService / OrderRepo / etc. by the units that wrap its method excerpts in `impl` blocks.
#![allow(dead_code)]
use std::fmt;
use std::sync::Arc;

use axum::{http::StatusCode, Router};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sqlx::PgPool;
use uuid::Uuid;

use crate::config::AppConfig;
use crate::error::AppError;
use crate::metrics::AppMetrics;

pub struct AppState {
    pub config: Arc<AppConfig>,
    pub order_service: OrderService,
    pub metrics: AppMetrics,
    pub prometheus_registry: prometheus::Registry,
}

impl AppState {
    pub async fn from_env() -> anyhow::Result<Self> {
        anyhow::bail!("not wired in the compile harness")
    }
}

#[derive(Debug, Clone, Serialize)]
pub enum OrderStatus {
    Pending,
}

impl OrderStatus {
    pub fn as_str(&self) -> &'static str {
        "pending"
    }
}

#[derive(Debug, Clone, Serialize)]
pub enum PaymentMethod {
    Card,
}

impl fmt::Display for PaymentMethod {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str("card")
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OrderItem {
    pub sku: String,
    pub quantity: i32,
}

#[derive(Debug, Clone, Serialize)]
pub struct Order {
    pub id: String,
    pub tenant_id: String,
    pub user_id: String,
    pub total: i64, // minor units
    pub status: OrderStatus,
    pub payment_method: PaymentMethod,
    pub items: Vec<OrderItem>,
    pub created_at: DateTime<Utc>,
}

impl Order {
    pub fn new(tenant_id: impl ToString, user_id: impl ToString, items: Vec<OrderItem>) -> Self {
        Self {
            id: Uuid::new_v4().to_string(),
            tenant_id: tenant_id.to_string(),
            user_id: user_id.to_string(),
            total: 0,
            status: OrderStatus::Pending,
            payment_method: PaymentMethod::Card,
            items,
            created_at: Utc::now(),
        }
    }
    pub fn total_as_f64(&self) -> f64 {
        self.total as f64 / 100.0
    }
}

#[derive(Debug, Deserialize)]
pub struct CreateOrderRequest {
    pub items: Vec<OrderItem>,
}

impl CreateOrderRequest {
    pub fn validate(&self) -> Result<(), AppError> {
        Ok(())
    }
}

#[derive(Debug)]
pub struct BatchItem {
    pub id: Uuid,
}

pub struct BatchResult {
    pub processed: u64,
    pub failed: u64,
}

pub struct PaymentReceipt {
    pub id: String,
    pub amount: i64,
}

#[derive(Debug)]
pub struct PaymentClient;

impl PaymentClient {
    pub async fn charge(&self, _order: &Order) -> Result<PaymentReceipt, AppError> {
        Err(AppError::unavailable("payment-gateway", "not wired"))
    }
}

pub struct Data;

#[derive(Debug)]
pub struct CacheClient;

impl CacheClient {
    pub async fn get(&self, _key: &str) -> Result<Option<Data>, AppError> {
        Ok(None)
    }
}

pub struct CircuitBreaker;

impl CircuitBreaker {
    pub fn failure_count(&self) -> u32 {
        0
    }
    pub fn reset_timeout(&self) -> std::time::Duration {
        std::time::Duration::from_secs(30)
    }
}

pub struct OrderRepo {
    pub pool: PgPool,
}

pub struct OrderService {
    pub repo: OrderRepo,
    pub metrics: Arc<AppMetrics>,
    pub payment_client: PaymentClient,
    pub cache: CacheClient,
}

impl OrderService {
    pub async fn validate_item(&self, _item: &BatchItem) -> Result<(), AppError> {
        Ok(())
    }
    pub async fn persist_item(&self, _item: &BatchItem) -> Result<(), AppError> {
        Ok(())
    }
    pub async fn fetch_from_db(&self, _key: &str) -> Result<Data, AppError> {
        Ok(Data)
    }
    pub async fn validate(&self, _order: &Order) -> Result<(), AppError> {
        Ok(())
    }
    pub async fn persist(&self, _order: &Order) -> Result<(), AppError> {
        Ok(())
    }
}

#[derive(Debug)]
pub struct User;

#[derive(Debug)]
pub struct CreateUserRequest {
    pub email: String,
}

#[derive(Debug)]
pub struct UserService;

pub fn extract_domain(email: &str) -> &str {
    email.rsplit('@').next().unwrap_or("")
}

pub struct HttpClient {
    pub client: reqwest::Client,
}

pub fn order_routes() -> Router<Arc<AppState>> {
    Router::new()
}

pub async fn health_check() -> StatusCode {
    StatusCode::OK
}
