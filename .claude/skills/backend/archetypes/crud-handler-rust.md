---
skill: crud-handler-rust
description: Axum handler archetype — extractors, JSON request/response envelope, cursor pagination, error mapping, tracing, structured validation
version: "1.0"
tags:
  - rust
  - axum
  - handler
  - http
  - archetype
  - backend
---

# CRUD Handler Archetype (Rust / Axum)

> Rust samples compile-checked 2026-09-30 (tests/archetype-compile/rust/run.sh): rustc 1.98.1, axum 0.8.9, validator 0.21.0, sqlx 0.9.0, composed with the auth, service and repository archetypes; crud-handler-test-rust.md's integration tests ran against it on Postgres 17 and pass.

Complete Axum handler set for REST APIs. Every generated handler MUST follow this pattern.

## Handler Module and Router

```rust
use axum::{
    Router,
    extract::State,
    http::StatusCode,
    response::IntoResponse,
    routing::{get, post, put, delete},
    Json,
};
use std::sync::Arc;
use uuid::Uuid;

use crate::domain::ListFilters;
use crate::error::{AppError, AppJson, AppPath, AppQuery};
use crate::extractors::auth_user::AuthUser; // auth-middleware-rust.md
use crate::startup::AppState;

/// Build widget routes. Mount into the main router:
/// `Router::new().nest("/api/v1/widgets", widget_routes())`
pub fn widget_routes() -> Router<Arc<AppState>> {
    Router::new()
        .route("/", post(create_widget).get(list_widgets))
        .route("/{id}", get(get_widget).put(update_widget).delete(delete_widget))
}
```

## Response Envelope Types

The shape is `~/.claude/skills/api/response-envelope.md` — success `{data, meta}`, error `{error}`, never
both; list metadata in `meta.pagination`. Error bodies are written only by `AppError`'s `IntoResponse`
impl (`error-handling-rust.md`).

```rust
use serde::Serialize;

/// Envelope wraps every success response: a single resource or a list.
#[derive(Serialize)]
pub struct Envelope<T: Serialize> {
    pub data: T,
    pub meta: Meta,
}

#[derive(Serialize)]
pub struct Meta {
    pub request_id: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub pagination: Option<Pagination>, // lists only
}

#[derive(Serialize)]
pub struct Pagination {
    pub next_cursor: Option<String>, // serialized as null when has_more is false
    pub has_more: bool,
    pub limit: i64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub total_count: Option<i64>, // only if cheap AND documented
}

fn new_meta(request_id: &str) -> Meta {
    Meta {
        request_id: request_id.to_owned(),
        pagination: None,
    }
}
```

## Create Handler

```rust
#[tracing::instrument(skip(state, auth, input), fields(request_id))]
async fn create_widget(
    State(state): State<Arc<AppState>>,
    auth: AuthUser,
    AppJson(input): AppJson<CreateWidgetInput>, // bad JSON → 400 MALFORMED_REQUEST envelope
) -> Result<impl IntoResponse, AppError> {
    let request_id = auth.request_id();
    tracing::Span::current().record("request_id", &request_id);

    // Function-level authorization: viewers read, editors and admins write (→ 403 FORBIDDEN)
    auth.require_any_role(&["admin", "editor"])?;

    // 1. Validate input (→ 400 VALIDATION_FAILED with details[])
    input.validate()?;

    // 2. Call service
    let widget = state.widget_service.create(auth.tenant_id, auth.user_id, input).await?;

    // 3. Return 201 Created with envelope
    Ok((
        StatusCode::CREATED,
        Json(Envelope {
            data: widget,
            meta: new_meta(&request_id),
        }),
    ))
}
```

## Get Handler

```rust
#[tracing::instrument(skip(state, auth), fields(request_id, widget_id = %id))]
async fn get_widget(
    State(state): State<Arc<AppState>>,
    auth: AuthUser,
    AppPath(id): AppPath<Uuid>, // not a UUID → 400 VALIDATION_FAILED envelope
) -> Result<impl IntoResponse, AppError> {
    let request_id = auth.request_id();
    tracing::Span::current().record("request_id", &request_id);

    let widget = state.widget_service.get(auth.tenant_id, id).await?;

    Ok(Json(Envelope {
        data: widget,
        meta: new_meta(&request_id),
    }))
}
```

## Update Handler

```rust
#[tracing::instrument(skip(state, auth, input), fields(request_id, widget_id = %id))]
async fn update_widget(
    State(state): State<Arc<AppState>>,
    auth: AuthUser,
    AppPath(id): AppPath<Uuid>,
    AppJson(input): AppJson<UpdateWidgetInput>,
) -> Result<impl IntoResponse, AppError> {
    let request_id = auth.request_id();
    tracing::Span::current().record("request_id", &request_id);
    auth.require_any_role(&["admin", "editor"])?; // → 403 FORBIDDEN for a viewer

    // 1. Validate input
    input.validate()?;

    // 2. Call service
    let widget = state.widget_service.update(auth.tenant_id, auth.user_id, id, input).await?;

    Ok(Json(Envelope {
        data: widget,
        meta: new_meta(&request_id),
    }))
}
```

## Delete Handler

```rust
#[tracing::instrument(skip(state, auth), fields(request_id, widget_id = %id))]
async fn delete_widget(
    State(state): State<Arc<AppState>>,
    auth: AuthUser,
    AppPath(id): AppPath<Uuid>,
) -> Result<impl IntoResponse, AppError> {
    let request_id = auth.request_id();
    tracing::Span::current().record("request_id", &request_id);
    auth.require_any_role(&["admin", "editor"])?; // → 403 FORBIDDEN for a viewer

    state.widget_service.delete(auth.tenant_id, auth.user_id, id).await?;

    Ok(StatusCode::NO_CONTENT)
}
```

## Pagination — cursor only

List endpoints take `?cursor=<next_cursor>&limit=<n>` and return `meta.pagination`. There is no offset or
page-number variant: offset pages skip or repeat rows under concurrent writes, and `OFFSET 10000` still
scans 10,000 rows. For "jump to page N" admin tables, filter instead (date range, search, status). A spec
that truly needs numbered pages records it in `docs/DECISIONS.md` and still uses the envelope.

## List Handler with Cursor Pagination

```rust
/// Query params for list endpoints: `?cursor=&limit=&sort_by=&sort_dir=&filter[field]=`.
#[derive(Debug, Deserialize)]
pub struct ListParams {
    pub cursor: Option<String>,
    /// A string on purpose: with `#[serde(flatten)]` below, the query deserializer hands every value
    /// over as a string, so an integer field would reject `?limit=20`.
    pub limit: Option<String>,
    pub sort_by: Option<String>,
    pub sort_dir: Option<String>,
    /// Dynamic field filters: `filter[status]=active&filter[priority]=high`
    #[serde(flatten)]
    pub extra: std::collections::HashMap<String, String>,
}

impl ListParams {
    /// Convert query params into validated domain filters.
    /// `limit` defaults to 20. A value outside 1..=100, or not a whole number, is 400 VALIDATION_FAILED
    /// with a details[] entry for "limit" — never clamped silently: a client asking for 500 and
    /// getting 100 can't tell it was truncated (api/response-envelope.md).
    fn into_filters(self) -> Result<ListFilters, AppError> {
        let page_size = match self.limit.as_deref() {
            None => 20,
            Some(raw) => raw
                .parse::<i64>()
                .ok()
                .filter(|n| (1..=100).contains(n))
                .ok_or_else(|| {
                    AppError::validation("limit", "out_of_range", "Limit must be a whole number from 1 to 100.")
                })?,
        };

        let allowed_sorts = ["created_at", "updated_at", "name"];
        let sort_by = self.sort_by
            .filter(|s| allowed_sorts.contains(&s.as_str()))
            .unwrap_or_else(|| "created_at".to_owned());

        let sort_dir = self.sort_dir
            .filter(|d| d == "asc" || d == "desc")
            .unwrap_or_else(|| "desc".to_owned());

        // Extract filter[field]=value from flattened extra params
        let allowed_filters = ["status", "priority"]; // columns that exist (migration-pattern-rust.md)
        let fields: std::collections::HashMap<String, String> = self.extra.into_iter()
            .filter_map(|(k, v)| {
                k.strip_prefix("filter[")
                    .and_then(|rest| rest.strip_suffix(']'))
                    .filter(|field| allowed_filters.contains(field))
                    .map(|field| (field.to_owned(), v))
            })
            .collect();

        Ok(ListFilters {
            cursor: self.cursor,
            page_size,
            sort_by,
            sort_dir,
            fields,
        })
    }
}

#[tracing::instrument(skip(state, auth), fields(request_id))]
async fn list_widgets(
    State(state): State<Arc<AppState>>,
    auth: AuthUser,
    AppQuery(params): AppQuery<ListParams>,
) -> Result<impl IntoResponse, AppError> {
    let request_id = auth.request_id();
    tracing::Span::current().record("request_id", &request_id);

    let filters = params.into_filters()?; // bad limit → 400 VALIDATION_FAILED
    let limit = filters.page_size;
    let result = state.widget_service.list(auth.tenant_id, filters).await?;

    // data is [] (never null) when empty; next_cursor is null unless has_more
    let next_cursor = if result.has_more { result.cursor } else { None };
    Ok(Json(Envelope {
        data: result.items,
        meta: Meta {
            request_id,
            pagination: Some(Pagination {
                next_cursor,
                has_more: result.has_more,
                limit,
                total_count: None,
            }),
        },
    }))
}
```

## AuthUser Extractor

`AuthUser` is defined once, in `auth-middleware-rust.md` (`src/extractors/auth_user.rs`). It carries
`tenant_id`, `user_id` and `roles` from the verified `JwtClaims`, plus `request_id()`. Import it; do not
write a second one here. A missing claim → 401 `UNAUTHENTICATED` envelope with `WWW-Authenticate: Bearer`.

## Request/Response DTOs with Validation

```rust
use serde::Deserialize; // Serialize is imported with the envelope types above (same module)
use validator::Validate;

#[derive(Debug, Clone, Deserialize, Validate)]
pub struct CreateWidgetInput {
    #[validate(length(min = 1, max = 255, message = "name must be 1-255 characters"))]
    pub name: String,
    #[validate(length(max = 2000, message = "description must be 2000 characters or fewer"))]
    pub description: Option<String>,
}

#[derive(Debug, Clone, Deserialize, Validate)]
pub struct UpdateWidgetInput {
    #[validate(length(min = 1, max = 255, message = "name must be 1-255 characters"))]
    pub name: String,
    #[validate(length(max = 2000, message = "description must be 2000 characters or fewer"))]
    pub description: Option<String>,
    /// Optimistic locking — client must send current version.
    pub version: i32,
}

impl CreateWidgetInput {
    pub fn validate(&self) -> Result<(), AppError> {
        <Self as Validate>::validate(self)
            .map_err(|e| AppError::validation_from_validator(e))
    }
}

impl UpdateWidgetInput {
    pub fn validate(&self) -> Result<(), AppError> {
        <Self as Validate>::validate(self)
            .map_err(|e| AppError::validation_from_validator(e))
    }
}

/// Widget response DTO — only expose fields safe for clients.
#[derive(Debug, Serialize, sqlx::FromRow)]
pub struct WidgetResponse {
    pub id: Uuid,
    pub name: String,
    pub description: Option<String>,
    pub status: crate::models::WidgetStatus, // the Postgres enum widget_status
    pub version: i32,
    pub created_at: chrono::DateTime<chrono::Utc>,
    pub updated_at: chrono::DateTime<chrono::Utc>,
}
```

## Critical Rules

- Every handler MUST use `#[tracing::instrument]` with `skip` for large args and `fields(request_id)`
- Every handler MUST extract `AuthUser` — tenant ID comes from JWT, never from path/body
- Write handlers MUST check the caller's role (`auth.require_any_role(...)`) — a viewer gets 403 `FORBIDDEN`
- Request body validation MUST happen before any side effects (DB, cache, external calls)
- Error responses MUST use the `AppError` → `IntoResponse` path — never manual status codes or hand-built error JSON
- Extract with `AppJson` / `AppPath` / `AppQuery` (error-handling-rust.md), not axum's `Json` / `Path` / `Query`, so rejections become envelope errors
- Internal error messages MUST NOT leak to clients — `AppError::Internal` returns a generic message
- List endpoints are cursor-only: `?cursor=&limit=`. `limit` defaults to 20; outside 1..100 (or not a whole number) it is 400 `VALIDATION_FAILED` with a `details[]` entry for `limit` — never clamped silently, never an unbounded list
- Filter fields MUST be allow-listed — never pass arbitrary query params to the DB
- Sort fields MUST be allow-listed — never allow sorting by arbitrary columns
- Every success response MUST follow `~/.claude/skills/api/response-envelope.md`: `{"data": T, "meta": {"request_id"}}`; lists add `meta.pagination` `{next_cursor, has_more, limit}` and `data` is `[]` when empty
- DELETE returns 204 No Content — no body
- POST create returns 201 Created with the created resource in the body
- Extractors MUST be ordered: State, AuthUser, AppPath, AppQuery before AppJson (body-consuming)
