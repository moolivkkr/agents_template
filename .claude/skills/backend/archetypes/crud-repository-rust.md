---
skill: crud-repository-rust
description: Rust sqlx repository archetype — compile-time checked queries, cursor pagination, soft delete, optimistic locking, multi-tenant isolation, batch operations, error mapping
version: "1.0"
tags:
  - rust
  - sqlx
  - repository
  - postgres
  - archetype
  - backend
---

# CRUD Repository Archetype (Rust / sqlx)

> Rust samples compile-checked 2026-09-30 (tests/archetype-compile/rust/run.sh): rustc 1.98.1, sqlx 0.9.0 (query! macros checked against the migration-pattern-rust.md schema on Postgres 17), base64 0.23.1; crud-repository-test-rust.md's tests ran against it and pass.

Complete sqlx-based PostgreSQL repository template. Every generated repository MUST follow this pattern.

## Trait Definition

```rust
use async_trait::async_trait;
use uuid::Uuid;

use crate::domain::{ListFilters, ListResult};
use crate::error::AppError;
use crate::models::{Widget, WidgetStatus};

/// Repository trait — owned by the service (consumer), implemented by the persistence layer.
#[async_trait]
pub trait WidgetRepository: Send + Sync {
    async fn create(&self, widget: &Widget) -> Result<(), AppError>;
    async fn get_by_id(&self, tenant_id: Uuid, id: Uuid) -> Result<Widget, AppError>;
    async fn update(&self, widget: &Widget) -> Result<(), AppError>;
    async fn soft_delete(&self, tenant_id: Uuid, id: Uuid) -> Result<(), AppError>;
    async fn list(&self, tenant_id: Uuid, filters: &ListFilters) -> Result<ListResult<Widget>, AppError>;
    async fn batch_create(&self, widgets: &[Widget]) -> Result<(), AppError>;
}
```

## Implementation Struct and Constructor

```rust
use sqlx::PgPool;

pub struct PgWidgetRepository {
    pool: PgPool,
}

impl PgWidgetRepository {
    pub fn new(pool: PgPool) -> Self {
        Self { pool }
    }
}

/// Recommended pool configuration — apply when creating the pool in main.rs.
pub async fn create_pool(database_url: &str) -> Result<PgPool, AppError> {
    let pool = sqlx::postgres::PgPoolOptions::new()
        .max_connections(50)
        .min_connections(10)
        .max_lifetime(std::time::Duration::from_secs(3600))
        .idle_timeout(std::time::Duration::from_secs(1800))
        .acquire_timeout(std::time::Duration::from_secs(5))
        .connect(database_url)
        .await
        .map_err(|e| AppError::Internal(e.into()))?;

    // Run migrations at startup
    sqlx::migrate!("./migrations")
        .run(&pool)
        .await
        .map_err(|e| AppError::Internal(e.into()))?;

    Ok(pool)
}
```

## Create

```rust
#[async_trait]
impl WidgetRepository for PgWidgetRepository {
    #[tracing::instrument(skip(self, widget), fields(widget_id = %widget.id, tenant_id = %widget.tenant_id))]
    async fn create(&self, widget: &Widget) -> Result<(), AppError> {
        sqlx::query!(
            r#"
            INSERT INTO widgets (id, tenant_id, name, description, status,
                                 created_at, updated_at, created_by, updated_by, version)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            "#,
            widget.id,
            widget.tenant_id,
            widget.name,
            widget.description.as_deref(),
            widget.status as WidgetStatus, // Postgres enum: the macro takes the Rust type's word for it
            widget.created_at,
            widget.updated_at,
            widget.created_by,
            widget.updated_by,
            widget.version,
        )
        .execute(&self.pool)
        .await
        .map_err(|e| map_sqlx_error(e, "create"))?;

        tracing::info!("widget created");
        Ok(())
    }
}
```

## GetByID

```rust
    #[tracing::instrument(skip(self), fields(tenant_id = %tenant_id, widget_id = %id))]
    async fn get_by_id(&self, tenant_id: Uuid, id: Uuid) -> Result<Widget, AppError> {
        let widget = sqlx::query_as!(
            Widget,
            r#"
            SELECT id, tenant_id, name, description, status as "status: WidgetStatus",
                   created_at, updated_at, deleted_at,
                   created_by, updated_by, version
            FROM widgets
            WHERE tenant_id = $1 AND id = $2 AND deleted_at IS NULL
            "#,
            tenant_id,
            id,
        )
        .fetch_optional(&self.pool)
        .await
        .map_err(|e| map_sqlx_error(e, "get_by_id"))?
        // Missing, soft-deleted or another tenant's: all 404 NOT_FOUND
        .ok_or_else(|| AppError::not_found("Widget"))?;

        Ok(widget)
    }
```

## Update with Optimistic Locking

```rust
    #[tracing::instrument(skip(self, widget), fields(widget_id = %widget.id, tenant_id = %widget.tenant_id))]
    async fn update(&self, widget: &Widget) -> Result<(), AppError> {
        // WHERE version = expected_version ensures no concurrent modification.
        // The service layer increments version before calling update.
        let result = sqlx::query!(
            r#"
            UPDATE widgets
            SET name = $3, description = $4, status = $5,
                updated_at = $6, updated_by = $7, version = $8
            WHERE tenant_id = $1 AND id = $2 AND version = $9 AND deleted_at IS NULL
            "#,
            widget.tenant_id,
            widget.id,
            widget.name,
            widget.description.as_deref(),
            widget.status as WidgetStatus,
            widget.updated_at,
            widget.updated_by,
            widget.version,           // new version
            widget.version - 1,       // expected previous version
        )
        .execute(&self.pool)
        .await
        .map_err(|e| map_sqlx_error(e, "update"))?;

        if result.rows_affected() == 0 {
            return Err(AppError::conflict(
                "This widget was changed by someone else. Reload and try again.",
            ));
        }

        Ok(())
    }
```

## Soft Delete

```rust
    #[tracing::instrument(skip(self), fields(tenant_id = %tenant_id, widget_id = %id))]
    async fn soft_delete(&self, tenant_id: Uuid, id: Uuid) -> Result<(), AppError> {
        let result = sqlx::query!(
            r#"
            UPDATE widgets
            SET deleted_at = NOW(), updated_at = NOW()
            WHERE tenant_id = $1 AND id = $2 AND deleted_at IS NULL
            "#,
            tenant_id,
            id,
        )
        .execute(&self.pool)
        .await
        .map_err(|e| map_sqlx_error(e, "soft_delete"))?;

        if result.rows_affected() == 0 {
            return Err(AppError::not_found("Widget"));
        }

        Ok(())
    }
```

## List with Cursor-Based Pagination

```rust
    #[tracing::instrument(skip(self, filters), fields(tenant_id = %tenant_id))]
    async fn list(
        &self,
        tenant_id: Uuid,
        filters: &ListFilters,
    ) -> Result<ListResult<Widget>, AppError> {
        // Build dynamic query — sqlx::query_as! requires static SQL,
        // so use sqlx::query_as with runtime-built query for dynamic filters.
        let mut qb = QueryBuilder::new(
            "SELECT id, tenant_id, name, description, status, \
             created_at, updated_at, deleted_at, created_by, updated_by, version \
             FROM widgets WHERE tenant_id = "
        );
        qb.push_bind(tenant_id);
        qb.push(" AND deleted_at IS NULL");

        // Apply dynamic field filters (allow-listed columns, typed binds)
        push_filters(&mut qb, &filters.fields)?;

        // Apply cursor: keyset on (sort column, id); the cursor's value is typed for that column
        let col = sanitize_column(&filters.sort_by);
        let dir = if filters.sort_dir == "asc" { "ASC" } else { "DESC" };
        if let Some(ref cursor) = filters.cursor {
            let c = decode_cursor(cursor, col)?;
            let op = if dir == "DESC" { "<" } else { ">" };
            qb.push(format!(" AND ({col}, id) {op} ("));
            match c.key {
                CursorKey::Ts(ts) => qb.push_bind(ts),
                CursorKey::Text(text) => qb.push_bind(text),
            };
            qb.push(", ");
            qb.push_bind(c.id);
            qb.push(")");
        }

        // ORDER BY and LIMIT (request limit+1 to detect has_more)
        qb.push(format!(" ORDER BY {col} {dir}, id {dir} LIMIT "));
        qb.push_bind(filters.page_size + 1);

        let mut items: Vec<Widget> = qb.build_query_as()
            .fetch_all(&self.pool)
            .await
            .map_err(|e| map_sqlx_error(e, "list"))?;

        // Detect has_more and trim
        let has_more = items.len() as i64 > filters.page_size;
        if has_more {
            items.truncate(filters.page_size as usize);
        }

        // Build next cursor from the last item's value of the SORT column (not always created_at)
        let cursor = if has_more {
            items.last().map(|w| encode_cursor(col, w))
        } else {
            None
        };

        // Count total (optional — for UI display)
        let total = self.count_total(tenant_id, filters).await;

        tracing::info!(
            result_count = items.len(),
            has_more = has_more,
            total = total,
            "list completed"
        );

        Ok(ListResult { items, cursor, has_more, total })
    }
```

There is no offset/page-number list: the API is cursor-only (see "Pagination — cursor only" in
`crud-handler-rust.md`).

## Count Helpers

```rust
impl PgWidgetRepository {
    async fn count_total(&self, tenant_id: Uuid, filters: &ListFilters) -> i64 {
        let mut qb = QueryBuilder::new(
            "SELECT COUNT(*) as count FROM widgets WHERE tenant_id = "
        );
        qb.push_bind(tenant_id);
        qb.push(" AND deleted_at IS NULL");
        if push_filters(&mut qb, &filters.fields).is_err() {
            return 0; // list() has already rejected the filter with a 400
        }

        #[derive(sqlx::FromRow)]
        struct CountRow { count: Option<i64> }

        qb.build_query_as::<CountRow>()
            .fetch_one(&self.pool)
            .await
            .map(|r| r.count.unwrap_or(0))
            .unwrap_or(0)
    }
}
```

## Batch Create

```rust
    #[tracing::instrument(skip(self, widgets), fields(count = widgets.len()))]
    async fn batch_create(&self, widgets: &[Widget]) -> Result<(), AppError> {
        // Use a single multi-row INSERT for high-performance bulk inserts.
        // For very large batches (>1000), chunk into groups.
        const CHUNK_SIZE: usize = 500;

        for chunk in widgets.chunks(CHUNK_SIZE) {
            let mut qb = QueryBuilder::new(
                "INSERT INTO widgets (id, tenant_id, name, description, status, \
                 created_at, updated_at, created_by, updated_by, version) "
            );

            qb.push_values(chunk, |mut b, w| {
                b.push_bind(w.id)
                    .push_bind(w.tenant_id)
                    .push_bind(&w.name)
                    .push_bind(w.description.as_deref())
                    .push_bind(w.status) // typed: widget_status
                    .push_bind(w.created_at)
                    .push_bind(w.updated_at)
                    .push_bind(w.created_by)
                    .push_bind(w.updated_by)
                    .push_bind(w.version);
            });

            qb.build()
                .execute(&self.pool)
                .await
                .map_err(|e| map_sqlx_error(e, "batch_create"))?;
        }

        tracing::info!(count = widgets.len(), "batch create completed");
        Ok(())
    }
```

## Cursor Encoding / Decoding

```rust
use base64::{Engine as _, engine::general_purpose::URL_SAFE};
use chrono::{DateTime, Utc};

/// The last row's value of the sort column, typed for that column (every sortable column needs an arm
/// in encode_cursor: comparing `(name, id)` with a timestamp is a Postgres error).
#[derive(serde::Serialize, serde::Deserialize)]
enum CursorKey {
    Ts(DateTime<Utc>),
    Text(String),
}

#[derive(serde::Serialize, serde::Deserialize)]
struct CursorPayload {
    col: String, // the sort column the cursor was issued for
    key: CursorKey,
    id: Uuid,    // tie-breaker: (col, id) is unique
}

fn encode_cursor(col: &str, w: &Widget) -> String {
    let key = match col {
        "updated_at" => CursorKey::Ts(w.updated_at),
        "name" => CursorKey::Text(w.name.clone()),
        _ => CursorKey::Ts(w.created_at),
    };
    let payload = CursorPayload { col: col.to_owned(), key, id: w.id };
    let json = serde_json::to_vec(&payload).expect("cursor serialization cannot fail");
    URL_SAFE.encode(json)
}

/// A tampered or stale cursor, or one issued for another sort → 400 VALIDATION_FAILED on field "cursor".
fn decode_cursor(cursor: &str, col: &str) -> Result<CursorPayload, AppError> {
    let invalid = || {
        AppError::validation("cursor", "invalid_cursor", "This cursor is not valid. Start from the first page.")
    };
    let bytes = URL_SAFE.decode(cursor).map_err(|_| invalid())?;
    let payload: CursorPayload = serde_json::from_slice(&bytes).map_err(|_| invalid())?;
    if payload.col != col {
        return Err(invalid());
    }
    Ok(payload)
}
```

## Column Sanitization

```rust
use std::collections::HashMap;

use sqlx::{Postgres, QueryBuilder};

/// Allow-list of sortable columns (ORDER BY and the keyset cursor).
/// Prevents SQL injection in dynamic query construction.
fn sanitize_column(col: &str) -> &'static str {
    match col {
        "created_at" => "created_at",
        "updated_at" => "updated_at",
        "name" => "name",
        _ => "created_at", // safe default
    }
}

/// `AND <column> = $n` for each filterable column; any other field is ignored (the handler allow-lists
/// the same set). `status` is the Postgres enum `widget_status`: the value is parsed and bound typed,
/// so an unknown status is a 400 rather than a SQL error.
fn push_filters(qb: &mut QueryBuilder<Postgres>, fields: &HashMap<String, String>) -> Result<(), AppError> {
    for (field, value) in fields {
        match field.as_str() {
            "status" => {
                let status: WidgetStatus = value.parse().map_err(|_| {
                    AppError::validation("filter[status]", "invalid_value", "This status does not exist.")
                })?;
                qb.push(" AND status = ");
                qb.push_bind(status);
            }
            "priority" => {
                qb.push(" AND priority = ");
                qb.push_bind(value.clone());
            }
            _ => {}
        }
    }
    Ok(())
}
```

## Error Mapping

```rust
/// Map sqlx errors to domain AppError types at the repository boundary.
/// SQLSTATE picks the class. Client messages are fixed; the driver text, SQLSTATE and constraint
/// name go to the log only (5xx causes are logged by `IntoResponse` with request_id).
fn map_sqlx_error(err: sqlx::Error, operation: &str) -> AppError {
    // No rows found
    if matches!(err, sqlx::Error::RowNotFound) {
        return AppError::not_found("Widget");
    }
    // Connection pool exhausted — a dependency timeout
    if matches!(err, sqlx::Error::PoolTimedOut) {
        return AppError::unavailable("postgres", err);
    }

    let db = err.as_database_error();
    let sql_state = db.and_then(|d| d.code()).map(|c| c.into_owned());
    let constraint = db.and_then(|d| d.constraint()).unwrap_or("unknown").to_owned();

    match sql_state.as_deref() {
        // unique_violation — duplicate id or (tenant_id, name)
        Some("23505") => {
            tracing::warn!(operation, %constraint, "widget unique violation");
            AppError::conflict("A widget with these details already exists.")
        }
        // foreign_key_violation / check_violation
        Some("23503") | Some("23514") => {
            tracing::warn!(operation, %constraint, sql_state = ?sql_state, "widget integrity violation");
            AppError::business_rule("This change conflicts with related data.")
        }
        // query_canceled — statement_timeout fired
        Some("57014") => AppError::unavailable("postgres", err),
        // Anything else is unexpected: 500 INTERNAL with a generic message
        _ => AppError::internal(err),
    }
}
```

## Widget Model (sqlx::FromRow)

```rust
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Widget domain model — maps directly to the `widgets` table.
#[derive(Debug, Clone, Serialize, Deserialize, sqlx::FromRow)]
pub struct Widget {
    pub id: Uuid,
    pub tenant_id: Uuid,
    pub name: String,
    pub description: Option<String>,
    pub status: WidgetStatus,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
    pub deleted_at: Option<DateTime<Utc>>,
    pub created_by: Uuid,
    pub updated_by: Uuid,
    pub version: i32,
}

/// Mirrors the Postgres enum `widget_status` (migration-pattern-rust.md, 20240105). JSON carries the
/// lowercase name. In query! / query_as! the column needs a type hint: `status as "status: WidgetStatus"`
/// when reading, `widget.status as WidgetStatus` when binding.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, sqlx::Type)]
#[sqlx(type_name = "widget_status", rename_all = "lowercase")]
#[serde(rename_all = "lowercase")]
pub enum WidgetStatus {
    Active,
    Archived,
    Draft,
    Deleted,
}

impl std::str::FromStr for WidgetStatus {
    type Err = ();

    fn from_str(s: &str) -> Result<Self, ()> {
        match s {
            "active" => Ok(Self::Active),
            "archived" => Ok(Self::Archived),
            "draft" => Ok(Self::Draft),
            "deleted" => Ok(Self::Deleted),
            _ => Err(()),
        }
    }
}
```

## Critical Rules

- Every query MUST include `WHERE tenant_id = $N` — no cross-tenant data leaks
- Every query MUST use sqlx bind parameters (`$1`, `$2`, or `push_bind`) — never string interpolation of user values
- Every read query MUST include `AND deleted_at IS NULL` (soft delete filter)
- Update operations MUST use optimistic locking: `WHERE version = $expected`
- Column names in ORDER BY MUST be allow-listed via `sanitize_column`; filters go through `push_filters` (allow-listed columns, typed binds — an enum column is parsed, an unknown value is a 400)
- Cursor values MUST be opaque (base64-encoded JSON) — never expose raw DB values
- The cursor carries the last row's value of the column being sorted on (typed for it) plus `id`; a cursor from another sort is a 400
- List queries MUST request `LIMIT + 1` to detect `has_more` without an extra count query
- Batch inserts SHOULD use `push_values` with chunking for large datasets
- sqlx errors MUST be mapped to domain `AppError` at the repository boundary: unique violation → 409 `CONFLICT`, FK/check violation → 422 `BUSINESS_RULE_VIOLATION`, statement/pool timeout → 503 `UNAVAILABLE`, all with generic messages (constraint names only in logs)
- No offset/page-number list method — lists are cursor-only (keyset `WHERE (sort_col, id) < cursor`)
- Prefer `sqlx::query_as!` (compile-time checked) for static queries; use `QueryBuilder` only for dynamic filters
- `fetch_optional` + `.ok_or_else` is preferred over `fetch_one` for nullable lookups — gives you control over the NotFound error
- Every repository method MUST use `#[tracing::instrument]` with relevant entity/tenant IDs
