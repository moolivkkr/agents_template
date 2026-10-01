// HARNESS-ONLY smoke tests for frameworks/axum.md's router (not part of the doc): the nested routes
// answer where the doc says, auth runs before them, and unknown routes get the envelope.
use std::sync::Arc;

use archetype_axum_pack::app::test_app_state;
use archetype_axum_pack::router::build_router;
use axum::{body::Body, http::Request};
use tower::ServiceExt;

async fn call(req: Request<Body>) -> (u16, serde_json::Value) {
    let app = build_router(Arc::new(test_app_state().await));
    let resp = app.oneshot(req).await.unwrap();
    let status = resp.status().as_u16();
    let body = axum::body::to_bytes(resp.into_body(), usize::MAX).await.unwrap();
    (status, serde_json::from_slice(&body).unwrap_or(serde_json::Value::Null))
}

#[tokio::test]
async fn nested_routes_need_a_token_and_answer_401_envelopes() {
    for uri in ["/api/v1/widgets", "/api/v1/widgets/00000000-0000-0000-0000-000000000001", "/api/v1/users/me"] {
        let (status, body) = call(Request::get(uri).body(Body::empty()).unwrap()).await;
        assert_eq!(status, 401, "{uri}");
        assert_eq!(body["error"]["code"], "UNAUTHENTICATED", "{uri}");
    }
}

#[tokio::test]
async fn a_forged_token_is_401() {
    let req = Request::get("/api/v1/widgets").header("authorization", "Bearer test-token").body(Body::empty()).unwrap();
    assert_eq!(call(req).await.0, 401);
}

#[tokio::test]
async fn an_unknown_route_is_a_404_envelope() {
    let (status, body) = call(Request::get("/nope").body(Body::empty()).unwrap()).await;
    assert_eq!(status, 404);
    assert_eq!(body["error"]["code"], "NOT_FOUND");
    assert!(body["error"]["request_id"].as_str().is_some_and(|id| !id.is_empty()));
}
