// HARNESS STUB — grpc-pattern-rust.md's server calls an app-specific `crate::services::WidgetSvc`
// ("not shown"); no archetype defines this trait or its types.
#![allow(dead_code)]
use async_trait::async_trait;
use tokio::sync::mpsc;
use uuid::Uuid;

use crate::error::AppError;

#[derive(Debug, Clone)]
pub struct Widget {
    pub id: Uuid,
    pub name: String,
    pub description: String,
}

pub struct WidgetPage {
    pub items: Vec<Widget>,
    pub next_cursor: Option<String>,
    pub total: i64,
}

#[derive(Debug, Clone)]
pub struct WidgetChange {
    pub widget: Widget,
}

#[async_trait]
pub trait WidgetSvc: Send + Sync + 'static {
    async fn create(&self, tenant_id: Uuid, user_id: Uuid, name: &str, description: &str) -> Result<Widget, AppError>;
    async fn get(&self, tenant_id: Uuid, id: Uuid) -> Result<Widget, AppError>;
    async fn list(&self, tenant_id: Uuid, cursor: Option<String>, page_size: usize) -> Result<WidgetPage, AppError>;
    async fn subscribe(&self, tenant_id: Uuid) -> mpsc::Receiver<WidgetChange>;
}
