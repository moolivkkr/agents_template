// HARNESS-ONLY smoke tests for frameworks/actix-web.md (not part of the doc): the auth middleware
// rejects what it must, every rejection is the envelope with the echoed request id, and extractor
// failures go through the *Config handlers.
use actix_web::{middleware, test, web, App};
use archetype_actix::app::{test_app_state, test_token, TEST_AUDIENCE, TEST_ISSUER};
use archetype_actix::config::{json_config, path_config, query_config};
use archetype_actix::error::request_id;
use archetype_actix::routes::api_config;
use jsonwebtoken::{encode, EncodingKey, Header};

async fn call(req: test::TestRequest) -> (u16, String, serde_json::Value) {
    let state = web::Data::new(test_app_state().await);
    let app = test::init_service(
        App::new()
            .app_data(state)
            .app_data(json_config())
            .app_data(query_config())
            .app_data(path_config())
            .wrap(middleware::from_fn(request_id))
            .configure(api_config),
    )
    .await;
    let resp = test::call_service(&app, req.to_request()).await;
    let status = resp.status().as_u16();
    let id = resp.headers().get("x-request-id").expect("X-Request-Id echoed").to_str().unwrap().to_owned();
    let body = test::read_body(resp).await;
    (status, id, serde_json::from_slice(&body).unwrap_or(serde_json::Value::Null))
}

fn token_with(secret: &str, iss: &str, aud: &str, exp_offset_secs: i64) -> String {
    let claims = serde_json::json!({
        "sub": uuid::Uuid::new_v4(), "tenant_id": uuid::Uuid::new_v4(), "iss": iss, "aud": aud,
        "exp": chrono::Utc::now().timestamp() + exp_offset_secs,
    });
    encode(&Header::default(), &claims, &EncodingKey::from_secret(secret.as_bytes())).unwrap()
}

#[actix_rt::test]
async fn bad_tokens_are_401_envelopes_with_the_request_id() {
    let secret = "test-secret-not-for-production";
    let cases = [
        ("none", None),
        ("not a jwt", Some("test-token".to_owned())),
        ("wrong key", Some(token_with("another-secret", TEST_ISSUER, TEST_AUDIENCE, 300))),
        ("wrong issuer", Some(token_with(secret, "https://evil.example", TEST_AUDIENCE, 300))),
        ("wrong audience", Some(token_with(secret, TEST_ISSUER, "other-api", 300))),
        ("expired", Some(token_with(secret, TEST_ISSUER, TEST_AUDIENCE, -3600))),
    ];
    for (what, token) in cases {
        let mut req = test::TestRequest::get().uri("/api/v1/widgets/00000000-0000-0000-0000-000000000001");
        if let Some(t) = token {
            req = req.insert_header(("Authorization", format!("Bearer {t}")));
        }
        let (status, id, body) = call(req).await;
        assert_eq!(status, 401, "{what}");
        assert_eq!(body["error"]["code"], "UNAUTHENTICATED", "{what}");
        assert_eq!(body["error"]["request_id"], id.as_str(), "{what}");
    }
}

#[actix_rt::test]
async fn a_malformed_id_is_400_validation_failed_on_id() {
    let state = test_app_state().await;
    let req = test::TestRequest::get()
        .uri("/api/v1/widgets/not-a-uuid")
        .insert_header(("Authorization", format!("Bearer {}", test_token(&state, uuid::Uuid::new_v4()))));
    let (status, _, body) = call(req).await;
    assert_eq!(status, 400);
    assert_eq!(body["error"]["code"], "VALIDATION_FAILED");
    assert_eq!(body["error"]["details"][0]["field"], "id");
}

#[actix_rt::test]
async fn a_malformed_body_is_400_malformed_request() {
    let state = test_app_state().await;
    let req = test::TestRequest::post()
        .uri("/api/v1/widgets")
        .insert_header(("Authorization", format!("Bearer {}", test_token(&state, uuid::Uuid::new_v4()))))
        .insert_header(("Content-Type", "application/json"))
        .set_payload("{not json");
    let (status, _, body) = call(req).await;
    assert_eq!(status, 400);
    assert_eq!(body["error"]["code"], "MALFORMED_REQUEST");
}

#[actix_rt::test]
async fn an_incoming_request_id_is_kept_only_when_well_formed() {
    let (_, id, _) = call(test::TestRequest::get().uri("/api/v1/widgets").insert_header(("x-request-id", "abc-123"))).await;
    assert_eq!(id, "abc-123");
    let (_, id, body) = call(test::TestRequest::get().uri("/api/v1/widgets").insert_header(("x-request-id", "has spaces/and slashes"))).await;
    assert_ne!(id, "has spaces/and slashes");
    assert_eq!(body["error"]["request_id"], id.as_str());
}
