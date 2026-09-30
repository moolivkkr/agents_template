// HARNESS STUBS — the order service languages/rust.md's handler snippets call. No archetype defines it;
// the doc's handlers, envelope, error mapping and extractor are what is being checked.
#![allow(dead_code)]
use std::sync::Arc;

use axum::http::StatusCode;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use crate::error::DomainError;

#[derive(Clone)]
pub struct AppState {
    pub order_service: Arc<OrderService>,
}

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

#[derive(Deserialize)]
pub struct CreateOrderRequest {
    pub total_cents: i64,
}

pub struct OrderService;

impl OrderService {
    pub async fn create_order(&self, _tenant_id: Uuid, _request: CreateOrderRequest) -> Result<Order, DomainError> {
        Ok(Order { id: Uuid::new_v4() })
    }

    pub async fn list_orders(&self, _tenant_id: Uuid, _cursor: Option<&str>, _limit: i64) -> Result<(Vec<Order>, Option<String>), DomainError> {
        Ok((Vec::new(), None))
    }
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
