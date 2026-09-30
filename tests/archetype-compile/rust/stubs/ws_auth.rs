// HARNESS STUB — websocket-pattern-rust.md's upgrade handler authenticates with an app-specific
// credential check that no archetype defines. Returns the verified identity.
use uuid::Uuid;

#[derive(Debug, Clone)]
pub struct WsClaims {
    pub user_id: Uuid,
    pub tenant_id: Uuid,
    pub roles: Vec<String>,
}

#[derive(Debug, thiserror::Error)]
#[error("invalid websocket credential")]
pub struct WsAuthError;

/// Single-use upgrade ticket (websocket-pattern.md Option 1): atomically GET+DELETE from the ticket store.
pub async fn redeem_ws_ticket(_ticket: &str) -> Result<WsClaims, WsAuthError> {
    Err(WsAuthError)
}
