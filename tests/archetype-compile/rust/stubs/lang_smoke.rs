// HARNESS-ONLY smoke tests for the languages/rust.md handler snippets (not part of the doc): what
// `cargo check` can't see.
#[cfg(test)]
mod harness_smoke {
    use super::*;
    use std::sync::Arc;

    fn state() -> AppState {
        AppState { order_service: Arc::new(OrderService) }
    }

    #[test]
    fn order_routes_build() {
        // axum 0.8 panics while building a route that has a `:id` segment
        let _router: Router<AppState> = order_routes();
    }

    #[tokio::test]
    async fn limit_out_of_range_is_validation_failed_not_clamped() {
        for limit in [0, -1, 101, 500] {
            let params = PaginationParams { cursor: None, limit: Some(limit) };
            let result = list_orders(State(state()), TenantId(uuid::Uuid::new_v4()), Query(params)).await;
            match result.err().expect("an out-of-range limit is rejected") {
                DomainError::Validation(details) => assert_eq!(details[0].field, "limit"),
                other => panic!("limit {limit}: {other:?}"),
            }
        }
        let params = PaginationParams { cursor: None, limit: None };
        let Json(page) = list_orders(State(state()), TenantId(uuid::Uuid::new_v4()), Query(params)).await.expect("default limit");
        assert_eq!(page.meta.pagination.expect("list pagination").limit, 20);
    }

    #[tokio::test]
    async fn tenant_comes_from_the_verified_claims() {
        use axum::extract::FromRequestParts;

        let tenant = uuid::Uuid::new_v4();
        let (mut parts, ()) = axum::http::Request::builder().body(()).unwrap().into_parts();
        assert!(matches!(TenantId::from_request_parts(&mut parts, &()).await, Err(DomainError::Unauthenticated)));

        parts.extensions.insert(crate::extractors::Claims { sub: uuid::Uuid::new_v4(), tenant_id: tenant, tenant_ids: vec![] });
        assert_eq!(TenantId::from_request_parts(&mut parts, &()).await.ok().map(|t| t.0), Some(tenant));
    }
}
