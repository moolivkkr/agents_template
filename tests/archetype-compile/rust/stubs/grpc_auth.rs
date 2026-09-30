// HARNESS STUB — grpc-pattern-rust.md's AuthLayer uses an app-specific `crate::auth::JwtValidator`
// ("not shown"). A real one verifies signature, expiry and audience with a pinned algorithm.
use uuid::Uuid;

pub struct Claims {
    pub tenant_id: Uuid,
    pub user_id: Uuid,
}

#[derive(Debug)]
pub struct InvalidToken;

pub trait JwtValidator: Send + Sync + 'static {
    fn validate(&self, token: &str) -> Result<Claims, InvalidToken>;
}
