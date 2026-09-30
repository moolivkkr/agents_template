// HARNESS STUB — auth-middleware-rust.md's startup.rs nests `crate::handlers::admin::admin_routes()`;
// no archetype defines admin routes.
use std::sync::Arc;

use axum::Router;

use crate::startup::AppState;

pub fn admin_routes() -> Router<Arc<AppState>> {
    Router::new()
}
