// HARNESS STUBS for the composed widget app — only names no archetype defines.
use std::sync::Arc;
use std::time::Duration;

use async_trait::async_trait;
use axum::http::StatusCode;
use chrono::Utc;
use sqlx::PgPool;
use uuid::Uuid;

use crate::domain::AuditEntry;
use crate::error::AppError;
use crate::models::{Widget, WidgetStatus};
use crate::repositories::widget::PgWidgetRepository;
use crate::services::widget::WidgetService;
use crate::traits::{audit::AuditWriter, cache::Cache};

/// startup.rs routes /health and /ready to the app's own probes.
pub async fn health_check() -> StatusCode {
    StatusCode::OK
}

pub async fn readiness_check() -> StatusCode {
    StatusCode::OK
}

/// Fills startup.rs's `WidgetService::new(/* ... */)` placeholder. The repository is the real
/// PgWidgetRepository, so this also proves it implements the trait the service consumes.
pub fn widget_service(pool: PgPool) -> WidgetService {
    WidgetService::new(Arc::new(PgWidgetRepository::new(pool)), Arc::new(NoCache), Arc::new(LogAudit))
}

struct NoCache;

#[async_trait]
impl Cache for NoCache {
    async fn get(&self, _key: &str) -> Result<Option<Vec<u8>>, AppError> {
        Ok(None)
    }
    async fn set(&self, _key: &str, _value: &[u8], _ttl: Duration) -> Result<(), AppError> {
        Ok(())
    }
    async fn delete(&self, _key: &str) -> Result<(), AppError> {
        Ok(())
    }
}

struct LogAudit;

#[async_trait]
impl AuditWriter for LogAudit {
    async fn write(&self, entry: AuditEntry) -> Result<(), AppError> {
        tracing::info!(action = %entry.action, "audit");
        Ok(())
    }
}

/// crud-service-rust.md's create_with_relations takes this input; no archetype defines it.
#[derive(Debug, Clone)]
pub struct CreateWithRelationsInput {
    pub name: String,
    pub components: Vec<ComponentInput>,
}

#[derive(Debug, Clone)]
pub struct ComponentInput {
    pub name: String,
}

impl CreateWithRelationsInput {
    pub fn validate(&self) -> Result<(), AppError> {
        Ok(())
    }
}

impl Widget {
    /// crud-service-rust.md calls `Widget::new(tenant_id, user_id, &input)`; no archetype defines it.
    pub fn new(tenant_id: Uuid, user_id: Uuid, input: &CreateWithRelationsInput) -> Self {
        let now = Utc::now();
        Self {
            id: Uuid::new_v4(),
            tenant_id,
            name: input.name.clone(),
            description: None,
            status: WidgetStatus::Active,
            created_at: now,
            updated_at: now,
            deleted_at: None,
            created_by: user_id,
            updated_by: user_id,
            version: 1,
        }
    }
}
