// HARNESS STUB — grpc-pattern-rust.md's main.rs calls `app::wire()` ("not shown").
use std::sync::Arc;

use crate::auth::JwtValidator;
use crate::services::WidgetSvc;

pub async fn wire() -> Result<(Arc<dyn WidgetSvc>, Arc<dyn JwtValidator>), Box<dyn std::error::Error>> {
    Err("not wired in the compile harness".into())
}
