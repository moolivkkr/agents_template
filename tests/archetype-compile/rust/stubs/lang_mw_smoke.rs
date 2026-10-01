// HARNESS-ONLY smoke tests for languages/rust.md "Tower Middleware" (not part of the doc): the stack
// builds, the tenant comes from the verified token (a header can only select among its tenants), and
// success and error bodies carry the id the response echoes as X-Request-Id — one task-local for both.
#[cfg(test)]
mod harness_middleware_smoke {
    use super::*;
    use std::sync::Arc;

    use axum::{body::Body, http::Request};
    use jsonwebtoken::{encode, EncodingKey, Header};
    use tower::ServiceExt;

    fn state() -> AppState {
        let repo = Arc::new(crate::services::EmptyOrderRepository);
        AppState { order_service: Arc::new(crate::services::OrderService::new(repo)) }
    }

    fn token(tenant_id: uuid::Uuid) -> String {
        let exp = (chrono::Utc::now() + chrono::Duration::minutes(5)).timestamp();
        let claims = serde_json::json!({ "sub": uuid::Uuid::new_v4(), "tenant_id": tenant_id, "exp": exp });
        encode(&Header::default(), &claims, &EncodingKey::from_secret(crate::app::TEST_JWT_SECRET)).unwrap()
    }

    async fn call(req: Request<Body>) -> (axum::http::StatusCode, String, serde_json::Value) {
        let resp = app(state()).oneshot(req).await.unwrap();
        let status = resp.status();
        let id = resp.headers().get("x-request-id").expect("X-Request-Id echoed").to_str().unwrap().to_owned();
        let body = axum::body::to_bytes(resp.into_body(), usize::MAX).await.unwrap();
        (status, id, serde_json::from_slice(&body).unwrap())
    }

    #[tokio::test]
    async fn no_token_is_a_401_envelope_with_the_echoed_request_id() {
        let (status, id, body) = call(Request::get("/orders").body(Body::empty()).unwrap()).await;
        assert_eq!(status, 401);
        assert_eq!(body["error"]["code"], "UNAUTHENTICATED");
        assert_eq!(body["error"]["request_id"], id.as_str());
    }

    #[tokio::test]
    async fn a_list_carries_the_same_request_id_in_meta() {
        let req = Request::get("/orders").header("authorization", format!("Bearer {}", token(uuid::Uuid::new_v4())))
            .header("x-request-id", "req-123").body(Body::empty()).unwrap();
        let (status, id, body) = call(req).await;
        assert_eq!(status, 200, "{body}");
        assert_eq!(id, "req-123");
        assert_eq!(body["meta"]["request_id"], "req-123");
        assert_eq!(body["meta"]["pagination"]["limit"], 20);
    }

    #[tokio::test]
    async fn a_header_cannot_select_a_tenant_the_token_lacks() {
        let req = Request::get("/orders").header("authorization", format!("Bearer {}", token(uuid::Uuid::new_v4())))
            .header("x-tenant-id", uuid::Uuid::new_v4().to_string()).body(Body::empty()).unwrap();
        let (status, _, body) = call(req).await;
        assert_eq!(status, 403);
        assert_eq!(body["error"]["code"], "FORBIDDEN");
    }

    #[tokio::test]
    async fn a_malformed_incoming_request_id_is_replaced() {
        let req = Request::get("/orders").header("x-request-id", "x".repeat(300)).body(Body::empty()).unwrap();
        let (_, id, body) = call(req).await;
        assert!(id.len() <= 128 && !id.is_empty());
        assert_eq!(body["error"]["request_id"], id.as_str());
    }
}
