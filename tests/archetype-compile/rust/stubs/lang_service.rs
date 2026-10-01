// HARNESS STUB — the OrderService languages/rust.md's handlers and tests call. The doc shows the
// repository trait it depends on (above), not the service; this is the obvious one, so the doc's
// mock-based tests exercise real calls: create_order saves through the repository, get_order maps
// "no row" to NotFound.
pub struct OrderService {
    repo: Arc<dyn OrderRepository>,
}

impl OrderService {
    pub fn new(repo: Arc<dyn OrderRepository>) -> Self {
        Self { repo }
    }

    pub async fn create_order(&self, tenant_id: Uuid, request: CreateOrderRequest) -> Result<Order, DomainError> {
        let order = Order { total_cents: request.total_cents, ..Order::new(Uuid::new_v4(), tenant_id) };
        self.repo.save(&order).await
    }

    pub async fn get_order(&self, tenant_id: Uuid, id: Uuid) -> Result<Order, DomainError> {
        self.repo.find_by_id(tenant_id, id).await?.ok_or(DomainError::NotFound { resource: "Order", id })
    }

    pub async fn list_orders(&self, _tenant_id: Uuid, _cursor: Option<&str>, _limit: i64) -> Result<(Vec<Order>, Option<String>), DomainError> {
        Ok((Vec::new(), None))
    }
}

/// For the harness smoke tests: a repository with no rows.
pub struct EmptyOrderRepository;

#[async_trait]
impl OrderRepository for EmptyOrderRepository {
    async fn find_by_id(&self, _tenant_id: Uuid, _id: Uuid) -> Result<Option<Order>, DomainError> {
        Ok(None)
    }

    async fn save(&self, order: &Order) -> Result<Order, DomainError> {
        Ok(order.clone())
    }

    async fn soft_delete(&self, _tenant_id: Uuid, _id: Uuid) -> Result<(), DomainError> {
        Ok(())
    }
}
