// HARNESS STUB — the StripeClient testing/external-service-mocks.md's wiremock test drives. A real
// (minimal) HTTP client, so the test exercises an actual request against the mock server.
use serde::Deserialize;

#[derive(Debug, Deserialize)]
pub struct PaymentIntent {
    pub id: String,
    pub status: String,
    pub amount: i64,
}

pub struct StripeClient {
    http: reqwest::Client,
    base_url: String,
    api_key: String,
}

impl StripeClient {
    pub fn new(base_url: &str, api_key: &str) -> Self {
        Self { http: reqwest::Client::new(), base_url: base_url.trim_end_matches('/').to_owned(), api_key: api_key.to_owned() }
    }

    pub async fn create_payment_intent(&self, amount: i64, currency: &str) -> Result<PaymentIntent, reqwest::Error> {
        self.http
            .post(format!("{}/v1/payment_intents", self.base_url))
            .bearer_auth(&self.api_key)
            .header(reqwest::header::CONTENT_TYPE, "application/x-www-form-urlencoded")
            .body(format!("amount={amount}&currency={currency}"))
            .send()
            .await?
            .error_for_status()?
            .json()
            .await
    }
}
