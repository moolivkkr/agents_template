// HARNESS STUBS — the app types performance-rust.md's snippets are written against. No archetype
// defines them; they exist so the doc's pooling / async / sqlx / redis / profiling code (the part
// being checked) has something to call. Doc-defined types (DatabasePools, CacheLayer) are used as-is.
#![allow(dead_code)]
use chrono::{DateTime, Utc};
use opentelemetry::metrics::Gauge;
use serde::{Deserialize, Serialize};
use sqlx::PgPool;

use crate::caching::CacheLayer;
use crate::error::AppError;
use crate::replicas::DatabasePools;

pub struct AppConfig;

pub struct AppMetrics {
    pub db_pool_size: Gauge<i64>,
    pub db_pool_active: Gauge<i64>,
    pub db_pool_idle: Gauge<i64>,
}

#[derive(Debug, Clone, Serialize, Deserialize, sqlx::Type)]
#[sqlx(type_name = "text", rename_all = "lowercase")]
pub enum OrderStatus {
    Pending,
    Paid,
}

impl OrderStatus {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Pending => "pending",
            Self::Paid => "paid",
        }
    }
}

/// Matches the harness `orders` table (stubs/harness_schema.sql) column for column.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Order {
    pub id: String,
    pub tenant_id: String,
    pub user_id: String,
    pub total: i64,
    pub status: OrderStatus,
    pub created_at: DateTime<Utc>,
}

impl Order {
    pub fn mock(i: u64) -> Self {
        Self {
            id: format!("ord_{i}"),
            tenant_id: "tenant".into(),
            user_id: "user".into(),
            total: i as i64,
            status: OrderStatus::Pending,
            created_at: Utc::now(),
        }
    }
}

/// Matches the harness `order_items` table column for column.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OrderItem {
    pub id: String,
    pub order_id: String,
    pub tenant_id: String,
    pub product_id: String,
    pub quantity: i32,
    pub price: i64,
}

/// The row of the JOIN in "N+1 Prevention" (order_items columns are nullable: LEFT JOIN).
#[derive(Debug)]
pub struct OrderItemRow {
    pub id: String,
    pub tenant_id: String,
    pub total: i64,
    pub status: String,
    pub item_id: Option<String>,
    pub product_id: Option<String>,
    pub quantity: Option<i32>,
    pub price: Option<i64>,
}

pub struct OrderWithItems {
    pub order: Order,
    pub items: Vec<OrderItem>,
}

pub fn group_rows_into_orders(_rows: Vec<OrderItemRow>) -> Vec<OrderWithItems> {
    Vec::new()
}

pub struct Event {
    pub id: String,
    pub tenant_id: String,
    pub event_type: String,
    pub payload: String,
    pub created_at: DateTime<Utc>,
}

pub struct MetricEvent;

pub async fn process_event(_event: Event) {}

pub struct CreateRequest {
    pub name: String,
    pub email: String,
}

pub struct Item {
    pub id: String,
}

pub struct Row {
    pub id: String,
    pub name: String,
    pub value: f64,
}

pub struct EnrichedOrder;

pub struct EnrichmentService;

impl EnrichmentService {
    pub async fn enrich(&self, _order: Order) -> EnrichedOrder {
        EnrichedOrder
    }
}

#[derive(Default)]
pub struct Summary;

pub struct DashboardData {
    pub recent_orders: Vec<Order>,
    pub active_users: i64,
    pub summary: Summary,
}

pub struct OrdersSvc;
pub struct UsersSvc;
pub struct MetricsSvc;

impl OrdersSvc {
    pub async fn list_recent(&self, _tenant_id: &str) -> Result<Vec<Order>, AppError> {
        Ok(Vec::new())
    }
}

impl UsersSvc {
    pub async fn count_active(&self, _tenant_id: &str) -> Result<i64, AppError> {
        Ok(0)
    }
}

impl MetricsSvc {
    pub async fn get_summary(&self, _tenant_id: &str) -> Result<Summary, AppError> {
        Ok(Summary)
    }
}

pub struct AppServices {
    pub orders: OrdersSvc,
    pub users: UsersSvc,
    pub metrics: MetricsSvc,
}

pub struct Data;

pub struct RedisCache;

impl RedisCache {
    pub async fn get(&self, _key: &str) -> Result<Option<Data>, AppError> {
        Ok(None)
    }
}

pub async fn fetch_from_db(_db: &PgPool, _key: &str) -> Result<Data, AppError> {
    Ok(Data)
}

pub struct OrderRepo {
    pub pool: PgPool,
    pub pools: DatabasePools,
}

pub struct UpdateOrderRequest;

impl OrderRepo {
    pub async fn update(&self, _tenant_id: &str, _id: &str, _req: UpdateOrderRequest) -> Result<Order, AppError> {
        Err(AppError::not_found("Order"))
    }
}

pub struct OrderService {
    pub cache: CacheLayer,
    pub repo: OrderRepo,
}

/// The trait "Avoid Dynamic Dispatch" dispatches through (its enum version replaces it).
pub trait EventHandler {
    fn handle(&self, event: &Event);
}

pub struct OrderCreatedHandler;
pub struct PaymentReceivedHandler;
pub struct ShipmentDispatchedHandler;

impl OrderCreatedHandler {
    pub fn handle(&self, _event: &Event) {}
}
impl PaymentReceivedHandler {
    pub fn handle(&self, _event: &Event) {}
}
impl ShipmentDispatchedHandler {
    pub fn handle(&self, _event: &Event) {}
}

#[derive(PartialEq)]
pub enum Status {
    Active,
}

pub struct Account {
    pub status: Status,
}

pub fn write_metric(_msg: &str) {}

pub fn write_metric_parts(_a: &str, _b: &str, _c: &str) {}

pub struct Metric {
    pub name: String,
    pub value: f64,
}

pub async fn async_main() {}
