---
skill: crud-service-rust
description: Rust service layer archetype — async CRUD with trait-object repositories, cache-aside, audit logging, tracing, tenant isolation, transaction support, input validation
version: "1.0"
tags:
  - rust
  - service
  - crud
  - archetype
  - backend
---

# CRUD Service Archetype (Rust)

Complete, production-ready Rust service layer template. Every generated service MUST follow this pattern.

## Domain Types

```rust
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Base fields embedded in all domain entities.
#[derive(Debug, Clone, Serialize, Deserialize, sqlx::FromRow)]
pub struct Entity {
    pub id: Uuid,
    pub tenant_id: Uuid,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
    pub deleted_at: Option<DateTime<Utc>>,
    pub created_by: Uuid,
    pub updated_by: Uuid,
    pub version: i32,
}

/// Cursor-paginated list filters.
#[derive(Debug, Clone)]
pub struct ListFilters {
    pub cursor: Option<String>,
    pub page_size: i64,
    pub sort_by: String,
    pub sort_dir: String,
    pub fields: std::collections::HashMap<String, String>,
}

/// Cursor-paginated result set.
#[derive(Debug, Serialize)]
pub struct ListResult<T: Serialize> {
    pub items: Vec<T>,
    pub cursor: Option<String>,
    pub has_more: bool,
    pub total: i64,
}

/// Offset-paginated list filters.
#[derive(Debug, Clone)]
pub struct OffsetListFilters {
    pub page: i64,
    pub per_page: i64,
    pub sort_by: String,
    pub sort_dir: String,
    pub fields: std::collections::HashMap<String, String>,
}

/// Offset-paginated result set.
#[derive(Debug, Serialize)]
pub struct OffsetListResult<T: Serialize> {
    pub items: Vec<T>,
    pub total: i64,
}

/// Audit entry for compliance logging.
#[derive(Debug, Serialize)]
pub struct AuditEntry {
    pub action: String,
    pub entity_id: Uuid,
    pub tenant_id: Uuid,
    pub actor_id: Uuid,
    pub timestamp: DateTime<Utc>,
    pub changes: Option<serde_json::Value>,
}
```

## Trait Definitions

```rust
use async_trait::async_trait;

/// Repository trait — owned by the service (consumer), implemented by the persistence layer.
/// Rule: Keep interfaces small (3-7 methods). Split if > 7.
#[async_trait]
pub trait WidgetRepository: Send + Sync {
    async fn create(&self, widget: &Widget) -> Result<(), AppError>;
    async fn get_by_id(&self, tenant_id: Uuid, id: Uuid) -> Result<Widget, AppError>;
    async fn update(&self, widget: &Widget) -> Result<(), AppError>;
    async fn soft_delete(&self, tenant_id: Uuid, id: Uuid) -> Result<(), AppError>;
    async fn list(&self, tenant_id: Uuid, filters: &ListFilters) -> Result<ListResult<Widget>, AppError>;
}

/// Cache trait — abstracts Redis or any other caching backend.
#[async_trait]
pub trait Cache: Send + Sync {
    async fn get(&self, key: &str) -> Result<Option<Vec<u8>>, AppError>;
    async fn set(&self, key: &str, value: &[u8], ttl: std::time::Duration) -> Result<(), AppError>;
    async fn delete(&self, key: &str) -> Result<(), AppError>;
}

/// Audit writer — abstracts the audit log sink (DB, event bus, etc.).
#[async_trait]
pub trait AuditWriter: Send + Sync {
    async fn write(&self, entry: AuditEntry) -> Result<(), AppError>;
}
```

## Service Struct with Dependency Injection

```rust
use std::sync::Arc;
use std::time::Duration;

pub struct WidgetService {
    repo: Arc<dyn WidgetRepository>,
    cache: Arc<dyn Cache>,
    audit: Arc<dyn AuditWriter>,
    cache_ttl: Duration,
}

/// Constructor — every dependency explicit. No global state.
impl WidgetService {
    pub fn new(
        repo: Arc<dyn WidgetRepository>,
        cache: Arc<dyn Cache>,
        audit: Arc<dyn AuditWriter>,
    ) -> Self {
        Self {
            repo,
            cache,
            audit,
            cache_ttl: Duration::from_secs(300), // 5 minutes
        }
    }
}
```

## Create Implementation

```rust
impl WidgetService {
    #[tracing::instrument(skip(self, input), fields(tenant_id = %tenant_id, user_id = %user_id))]
    pub async fn create(
        &self,
        tenant_id: Uuid,
        user_id: Uuid,
        input: CreateWidgetInput,
    ) -> Result<Widget, AppError> {
        // 1. Validate input (already called in handler, but defense-in-depth)
        input.validate()?;

        // 2. Build domain object
        let now = Utc::now();
        let widget = Widget {
            id: Uuid::new_v4(),
            tenant_id,
            name: input.name,
            description: input.description,
            status: "active".to_owned(),
            created_at: now,
            updated_at: now,
            deleted_at: None,
            created_by: user_id,
            updated_by: user_id,
            version: 1,
        };

        // 3. Persist
        self.repo.create(&widget).await.map_err(|e| {
            tracing::error!(error = %e, "widget create failed");
            e
        })?;

        // 4. Audit log (fire-and-forget — never block the business operation)
        self.audit_log("widget.created", widget.id, tenant_id, user_id, Some(&widget)).await;

        tracing::info!(widget_id = %widget.id, "widget created");
        Ok(widget)
    }
}
```

## Get with Cache-Aside Pattern

```rust
impl WidgetService {
    #[tracing::instrument(skip(self), fields(tenant_id = %tenant_id, widget_id = %id))]
    pub async fn get(
        &self,
        tenant_id: Uuid,
        id: Uuid,
    ) -> Result<Widget, AppError> {
        let cache_key = format!("widget:{tenant_id}:{id}");

        // 1. Check cache
        if let Ok(Some(data)) = self.cache.get(&cache_key).await {
            if let Ok(widget) = serde_json::from_slice::<Widget>(&data) {
                tracing::debug!("cache hit");
                return Ok(widget);
            }
        }
        tracing::debug!("cache miss, querying database");

        // 2. Query DB
        let widget = self.repo.get_by_id(tenant_id, id).await?;

        // 3. Populate cache (best-effort — don't fail the request on cache errors)
        if let Ok(data) = serde_json::to_vec(&widget) {
            let _ = self.cache.set(&cache_key, &data, self.cache_ttl).await;
        }

        Ok(widget)
    }
}
```

## Update with Cache Invalidation and Optimistic Locking

```rust
impl WidgetService {
    #[tracing::instrument(skip(self, input), fields(tenant_id = %tenant_id, widget_id = %id))]
    pub async fn update(
        &self,
        tenant_id: Uuid,
        user_id: Uuid,
        id: Uuid,
        input: UpdateWidgetInput,
    ) -> Result<Widget, AppError> {
        // 1. Validate input
        input.validate()?;

        // 2. Fetch current (ensures tenant-scoping)
        let mut existing = self.repo.get_by_id(tenant_id, id).await?;

        // 3. Optimistic lock check
        if input.version != existing.version {
            return Err(AppError::Conflict {
                resource: "widget".into(),
                reason: "version mismatch -- reload and retry".into(),
            });
        }

        // 4. Apply changes
        existing.name = input.name;
        existing.description = input.description;
        existing.updated_at = Utc::now();
        existing.updated_by = user_id;
        existing.version += 1;

        // 5. Persist
        self.repo.update(&existing).await.map_err(|e| {
            tracing::error!(error = %e, "widget update failed");
            e
        })?;

        // 6. Invalidate cache
        let cache_key = format!("widget:{tenant_id}:{id}");
        let _ = self.cache.delete(&cache_key).await;

        // 7. Audit log
        self.audit_log("widget.updated", id, tenant_id, user_id, Some(&input)).await;

        tracing::info!("widget updated");
        Ok(existing)
    }
}
```

## Delete with Cache Invalidation

```rust
impl WidgetService {
    #[tracing::instrument(skip(self), fields(tenant_id = %tenant_id, widget_id = %id))]
    pub async fn delete(
        &self,
        tenant_id: Uuid,
        user_id: Uuid,
        id: Uuid,
    ) -> Result<(), AppError> {
        // 1. Soft delete (sets deleted_at, does not remove the row)
        self.repo.soft_delete(tenant_id, id).await.map_err(|e| {
            tracing::error!(error = %e, "widget delete failed");
            e
        })?;

        // 2. Invalidate cache
        let cache_key = format!("widget:{tenant_id}:{id}");
        let _ = self.cache.delete(&cache_key).await;

        // 3. Audit log
        self.audit_log("widget.deleted", id, tenant_id, user_id, None::<&()>).await;

        tracing::info!("widget deleted");
        Ok(())
    }
}
```

## List with Filters

```rust
impl WidgetService {
    #[tracing::instrument(skip(self, filters), fields(tenant_id = %tenant_id))]
    pub async fn list(
        &self,
        tenant_id: Uuid,
        mut filters: ListFilters,
    ) -> Result<ListResult<Widget>, AppError> {
        // Enforce pagination defaults and maximums
        if filters.page_size <= 0 {
            filters.page_size = 20;
        }
        if filters.page_size > 100 {
            filters.page_size = 100;
        }
        if filters.sort_by.is_empty() {
            filters.sort_by = "created_at".to_owned();
        }
        if filters.sort_dir.is_empty() {
            filters.sort_dir = "desc".to_owned();
        }

        let result = self.repo.list(tenant_id, &filters).await?;

        tracing::info!(
            result_count = result.items.len(),
            has_more = result.has_more,
            "list completed"
        );
        Ok(result)
    }
}
```

## Transaction Support for Multi-Step Operations

```rust
use sqlx::PgPool;

/// Transaction manager wraps sqlx transaction lifecycle.
/// Pass `&PgPool` — the closure receives a `&mut sqlx::Transaction`.
pub async fn with_tx<F, T>(pool: &PgPool, f: F) -> Result<T, AppError>
where
    F: for<'c> FnOnce(&'c mut sqlx::Transaction<'_, sqlx::Postgres>) -> std::pin::Pin<
        Box<dyn std::future::Future<Output = Result<T, AppError>> + Send + 'c>,
    >,
{
    let mut tx = pool.begin().await.map_err(|e| AppError::Internal(e.into()))?;
    let result = f(&mut tx).await?;
    tx.commit().await.map_err(|e| AppError::Internal(e.into()))?;
    Ok(result)
}

// Usage in service:
impl WidgetService {
    pub async fn create_with_relations(
        &self,
        pool: &PgPool,
        tenant_id: Uuid,
        user_id: Uuid,
        input: CreateWithRelationsInput,
    ) -> Result<Widget, AppError> {
        input.validate()?;

        with_tx(pool, |tx| {
            Box::pin(async move {
                // Step 1: Create parent widget within the transaction
                let widget = Widget::new(tenant_id, user_id, &input);
                sqlx::query!(
                    r#"INSERT INTO widgets (id, tenant_id, name, status, created_at, updated_at, created_by, updated_by, version)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)"#,
                    widget.id, widget.tenant_id, widget.name, widget.status,
                    widget.created_at, widget.updated_at, widget.created_by, widget.updated_by, widget.version,
                )
                .execute(&mut **tx)
                .await
                .map_err(|e| AppError::Internal(e.into()))?;

                // Step 2: Create child components (all within same transaction)
                for comp in &input.components {
                    sqlx::query!(
                        "INSERT INTO components (id, widget_id, tenant_id, name) VALUES ($1, $2, $3, $4)",
                        Uuid::new_v4(), widget.id, tenant_id, comp.name,
                    )
                    .execute(&mut **tx)
                    .await
                    .map_err(|e| AppError::Internal(e.into()))?;
                }

                Ok(widget)
            })
        })
        .await
    }
}
```

## Cache-Aside with Redis (deadpool)

```rust
use deadpool_redis::Pool as RedisPool;
use redis::AsyncCommands;

pub struct RedisCache {
    pool: RedisPool,
}

impl RedisCache {
    pub fn new(pool: RedisPool) -> Self {
        Self { pool }
    }
}

#[async_trait]
impl Cache for RedisCache {
    async fn get(&self, key: &str) -> Result<Option<Vec<u8>>, AppError> {
        let mut conn = self.pool.get().await
            .map_err(|e| AppError::Internal(e.into()))?;
        let result: Option<Vec<u8>> = conn.get(key).await
            .map_err(|e| AppError::Internal(e.into()))?;
        Ok(result)
    }

    async fn set(&self, key: &str, value: &[u8], ttl: Duration) -> Result<(), AppError> {
        let mut conn = self.pool.get().await
            .map_err(|e| AppError::Internal(e.into()))?;
        conn.set_ex(key, value, ttl.as_secs()).await
            .map_err(|e| AppError::Internal(e.into()))?;
        Ok(())
    }

    async fn delete(&self, key: &str) -> Result<(), AppError> {
        let mut conn = self.pool.get().await
            .map_err(|e| AppError::Internal(e.into()))?;
        conn.del(key).await
            .map_err(|e| AppError::Internal(e.into()))?;
        Ok(())
    }
}
```

## Audit Logging Helper

```rust
impl WidgetService {
    /// Fire-and-forget audit log. Never blocks the business operation.
    async fn audit_log<T: Serialize>(
        &self,
        action: &str,
        entity_id: Uuid,
        tenant_id: Uuid,
        actor_id: Uuid,
        changes: Option<&T>,
    ) {
        let entry = AuditEntry {
            action: action.to_owned(),
            entity_id,
            tenant_id,
            actor_id,
            timestamp: Utc::now(),
            changes: changes.and_then(|c| serde_json::to_value(c).ok()),
        };

        if let Err(e) = self.audit.write(entry).await {
            tracing::error!(
                error = %e,
                action = action,
                entity_id = %entity_id,
                "audit log failed"
            );
        }
    }
}
```

## Error Taxonomy (enum with thiserror)

```rust
use thiserror::Error;

/// See `error-handling-rust.md` for the full error system.
#[derive(Debug, Error)]
pub enum AppError {
    #[error("validation error: {message}")]
    Validation { message: String, details: Option<serde_json::Value> },

    #[error("{resource} not found")]
    NotFound { resource: String, identifier: String },

    #[error("{resource} conflict: {reason}")]
    Conflict { resource: String, reason: String },

    #[error("unauthorized: {0}")]
    Unauthorized(String),

    #[error("forbidden: insufficient permissions to {action} {resource}")]
    Forbidden { action: String, resource: String },

    #[error("internal error")]
    Internal(#[source] Box<dyn std::error::Error + Send + Sync>),
}
```

## Critical Rules

- Every operation MUST be tenant-scoped — tenant_id comes from auth context, never from user input
- Every mutation MUST produce an audit log entry (fire-and-forget)
- Every public method MUST use `#[tracing::instrument]` with relevant fields
- Cache invalidation MUST happen on every write (Update, Delete)
- Cache misses MUST populate the cache before returning
- Optimistic locking via `version` field — reject stale writes with `Conflict` error
- Input validation MUST happen before any side effects (DB, cache, external calls)
- Errors MUST be typed (`AppError` enum) — no `anyhow` or string errors in the service layer
- Max 40 lines of logic per method — extract helpers for complex steps
- Accept trait objects (`Arc<dyn Repo>`), return concrete types — constructor takes traits, enables testing
- Never return unbounded lists — always enforce page_size max (100)
- Transaction closures MUST be `Send` + `'static`-compatible for sqlx
- Cache errors MUST NOT fail the request — use `let _ =` for best-effort cache ops
