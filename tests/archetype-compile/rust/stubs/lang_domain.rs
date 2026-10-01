// HARNESS STUBS — the request/response DTOs languages/rust.md's handlers and transaction sample use
// (their fields follow those samples: request.total_cents, request.items[].sku / .quantity).
#[derive(Debug, Clone, Deserialize)]
pub struct CreateOrderRequest {
    pub total_cents: i64,
    pub items: Vec<OrderItemRequest>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct OrderItemRequest {
    pub sku: String,
    pub quantity: i32,
}

#[derive(Debug, Serialize)]
pub struct OrderResponse {
    pub id: Uuid,
    pub status: OrderStatus,
    pub total_cents: i64,
    pub created_at: DateTime<Utc>,
}

impl From<Order> for OrderResponse {
    fn from(order: Order) -> Self {
        Self { id: order.id, status: order.status, total_cents: order.total_cents, created_at: order.created_at }
    }
}
