// HARNESS STUB — no archetype defines the config struct; auth-middleware-rust.md and
// crud-handler-test-rust.md use `crate::config::AppConfig` with these fields and `test_defaults()`.
// Real projects load it from the environment with no compiled-in secret defaults.

#[derive(Clone, Debug)]
pub struct AppConfig {
    pub database_url: String,
    pub jwt_secret: String,
}

impl AppConfig {
    /// Test-only values; the tests sign their tokens with "test-secret".
    pub fn test_defaults() -> Self {
        Self {
            database_url: String::new(),
            jwt_secret: "test-secret".into(),
        }
    }
}
