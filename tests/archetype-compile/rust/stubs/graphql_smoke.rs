// HARNESS-ONLY smoke tests for frameworks/graphql.md's Rust resolvers (not part of the doc): `first`
// outside 1..=100 is an error (not clamped), and a service error reaches the client as its code and
// user-safe message — never its Display text.
#[cfg(test)]
mod harness_smoke {
    use std::sync::Arc;

    use async_graphql::{dataloader::DataLoader, EmptyMutation, EmptySubscription, Schema};
    use uuid::Uuid;

    use crate::app::{AuthContext, QueryRoot, UserLoader, WidgetService};
    use crate::error::AppError;

    async fn run(query: &str, fail: Option<fn() -> AppError>) -> serde_json::Value {
        let schema = Schema::build(QueryRoot, EmptyMutation, EmptySubscription)
            .data(AuthContext { tenant_id: Uuid::new_v4() })
            .data(Arc::new(WidgetService { fail }))
            .data(DataLoader::new(UserLoader, tokio::spawn))
            .finish();
        serde_json::to_value(schema.execute(query).await).unwrap()
    }

    #[tokio::test]
    async fn first_out_of_range_is_validation_failed_not_clamped() {
        for first in [0, -1, 101, 500] {
            let resp = run(&format!("{{ widgets(first: {first}) {{ pageSize }} }}"), None).await;
            assert_eq!(resp["errors"][0]["extensions"]["code"], "VALIDATION_FAILED", "first = {first}: {resp}");
            assert_eq!(resp["errors"][0]["extensions"]["field"], "first");
        }
        let resp = run("{ widgets { pageSize } }", None).await;
        assert_eq!(resp["data"]["widgets"]["pageSize"], 20, "{resp}");
        let resp = run("{ widgets(first: 100) { pageSize } }", None).await;
        assert_eq!(resp["data"]["widgets"]["pageSize"], 100, "{resp}");
    }

    #[tokio::test]
    async fn an_internal_error_never_reaches_the_client() {
        let fail: fn() -> AppError = || AppError::internal("connection to 10.0.0.5 failed: password authentication failed for user app");
        let resp = run("{ widget(id: \"00000000-0000-0000-0000-000000000001\") { createdBy { id } } }", Some(fail)).await;
        let error = &resp["errors"][0];
        assert_eq!(error["extensions"]["code"], "INTERNAL", "{resp}");
        assert!(!resp.to_string().contains("password"), "{resp}");
    }

    #[tokio::test]
    async fn the_data_loader_resolves_created_by() {
        let resp = run("{ widget(id: \"00000000-0000-0000-0000-000000000001\") { createdBy { id } } }", None).await;
        assert!(resp["data"]["widget"]["createdBy"]["id"].is_string(), "{resp}");
    }
}
