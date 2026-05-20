---
skill: crud-handler-rust
description: Axum handler archetype — extractors, JSON request/response, cursor + offset pagination, error mapping, tracing, structured validation
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

Complete Axum handler set for REST APIs. Every generated handler MUST follow this pattern.

## Handler Module and Router

```rust
use axum::{
    Router,
    extract::{Path, Query, State, Json},
    http::StatusCode,
    response::IntoResponse,
    routing::{get, post, put, delete},
};
use std::sync::Arc;
use uuid::Uuid;

use crate::domain::{ListFilters, OffsetListFilters};
use crate::error::AppError;
use crate::extractors::AuthUser;

/// Build widget routes. Mount into the main router:
/// `Router::new().nest("/api/v1/widgets", widget_routes(state))`
pub fn widget_routes() -> Router<Arc<AppState>> {
    Router::new()
        .route("/", post(create_widget).get(list_widgets))
        .route("/{id}", get(get_widget).put(update_widget).delete(delete_widget))
}
```

## Response Envelope Types

```rust
use chrono::Utc;
use serde::Serialize;

/// Wraps a single resource response.
#[derive(Serialize)]
pub struct Envelope<T: Serialize> {
    pub data: T,
    pub meta: Meta,
}

/// Wraps a cursor-paginated list response.
#[derive(Serialize)]
pub struct ListEnvelope<T: Serialize> {
    pub data: Vec<T>,
    pub meta: ListMeta,
}

/// Wraps an offset-paginated list response.
#[derive(Serialize)]
pub struct OffsetListEnvelope<T: Serialize> {
    pub data: Vec<T>,
    pub meta: OffsetListMeta,
    pub links: PageLinks,
}

#[derive(Serialize)]
pub struct Meta {
    pub request_id: String,
    pub timestamp: String,
}

#[derive(Serialize)]
pub struct ListMeta {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub cursor: Option<String>,
    pub has_more: bool,
    pub total: i64,
    pub request_id: String,
    pub timestamp: String,
}

#[derive(Serialize)]
pub struct OffsetListMeta {
    pub page: i64,
    pub per_page: i64,
    pub total: i64,
    pub total_pages: i64,
    pub request_id: String,
    pub timestamp: String,
}

#[derive(Serialize)]
pub struct PageLinks {
    #[serde(rename = "self")]
    pub self_link: String,
    pub first: String,
    pub last: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub next: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub prev: Option<String>,
}

/// Error response body — standard JSON error envelope.
#[derive(Serialize)]
pub struct ErrorBody {
    pub error: ErrorDetail,
}

#[derive(Serialize)]
pub struct ErrorDetail {
    pub code: String,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub details: Option<serde_json::Value>,
}

fn new_meta(request_id: &str) -> Meta {
    Meta {
        request_id: request_id.to_owned(),
        timestamp: Utc::now().to_rfc3339(),
    }
}
```

## Create Handler

```rust
#[tracing::instrument(skip(state, auth, input), fields(request_id))]
async fn create_widget(
    State(state): State<Arc<AppState>>,
    auth: AuthUser,
    Json(input): Json<CreateWidgetInput>,
) -> Result<impl IntoResponse, AppError> {
    let request_id = auth.request_id();
    tracing::Span::current().record("request_id", &request_id);

    // 1. Validate input
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
    Path(id): Path<Uuid>,
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
    Path(id): Path<Uuid>,
    Json(input): Json<UpdateWidgetInput>,
) -> Result<impl IntoResponse, AppError> {
    let request_id = auth.request_id();
    tracing::Span::current().record("request_id", &request_id);

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
    Path(id): Path<Uuid>,
) -> Result<impl IntoResponse, AppError> {
    let request_id = auth.request_id();
    tracing::Span::current().record("request_id", &request_id);

    state.widget_service.delete(auth.tenant_id, auth.user_id, id).await?;

    Ok(StatusCode::NO_CONTENT)
}
```

## Pagination Strategy — When to Use Which

| Strategy | Use When | Query Params | Example |
|----------|----------|--------------|---------|
| **Cursor** (default) | Public APIs, real-time feeds, large datasets, infinite scroll | `?cursor=abc&page_size=20` | User-facing list endpoints |
| **Offset** | Admin/reporting UIs, dashboards, "jump to page N", data export previews | `?page=3&per_page=20` | Back-office tables, audit logs |

**Default to cursor pagination.** Use offset only for admin/reporting UIs where users need to jump to arbitrary pages. Offset pagination degrades at high page numbers (OFFSET 10000 still scans 10000 rows).

## List Handler with Cursor Pagination

```rust
/// Query params for cursor-paginated list endpoints.
#[derive(Debug, Deserialize)]
pub struct ListParams {
    pub cursor: Option<String>,
    pub page_size: Option<i64>,
    pub sort_by: Option<String>,
    pub sort_dir: Option<String>,
    /// Dynamic field filters: `filter[status]=active&filter[priority]=high`
    #[serde(flatten)]
    pub extra: std::collections::HashMap<String, String>,
}

impl ListParams {
    /// Convert query params into validated domain filters.
    fn into_filters(self) -> ListFilters {
        let page_size = self.page_size.unwrap_or(20).clamp(1, 100);

        let allowed_sorts = ["created_at", "updated_at", "name"];
        let sort_by = self.sort_by
            .filter(|s| allowed_sorts.contains(&s.as_str()))
            .unwrap_or_else(|| "created_at".to_owned());

        let sort_dir = self.sort_dir
            .filter(|d| d == "asc" || d == "desc")
            .unwrap_or_else(|| "desc".to_owned());

        // Extract filter[field]=value from flattened extra params
        let allowed_filters = ["status", "priority", "category"];
        let fields: std::collections::HashMap<String, String> = self.extra.into_iter()
            .filter_map(|(k, v)| {
                k.strip_prefix("filter[")
                    .and_then(|rest| rest.strip_suffix(']'))
                    .filter(|field| allowed_filters.contains(field))
                    .map(|field| (field.to_owned(), v))
            })
            .collect();

        ListFilters {
            cursor: self.cursor,
            page_size,
            sort_by,
            sort_dir,
            fields,
        }
    }
}

#[tracing::instrument(skip(state, auth), fields(request_id))]
async fn list_widgets(
    State(state): State<Arc<AppState>>,
    auth: AuthUser,
    Query(params): Query<ListParams>,
) -> Result<impl IntoResponse, AppError> {
    let request_id = auth.request_id();
    tracing::Span::current().record("request_id", &request_id);

    let filters = params.into_filters();
    let result = state.widget_service.list(auth.tenant_id, filters).await?;

    Ok(Json(ListEnvelope {
        data: result.items,
        meta: ListMeta {
            cursor: result.cursor,
            has_more: result.has_more,
            total: result.total,
            request_id,
            timestamp: Utc::now().to_rfc3339(),
        },
    }))
}
```

## List Handler with Offset Pagination (Admin/Reporting)

```rust
#[derive(Debug, Deserialize)]
pub struct OffsetListParams {
    pub page: Option<i64>,
    pub per_page: Option<i64>,
    pub sort_by: Option<String>,
    pub sort_dir: Option<String>,
    #[serde(flatten)]
    pub extra: std::collections::HashMap<String, String>,
}

impl OffsetListParams {
    fn into_filters(self) -> OffsetListFilters {
        let page = self.page.unwrap_or(1).max(1);
        let per_page = self.per_page.unwrap_or(20).clamp(1, 100);

        let allowed_sorts = ["created_at", "updated_at", "name"];
        let sort_by = self.sort_by
            .filter(|s| allowed_sorts.contains(&s.as_str()))
            .unwrap_or_else(|| "created_at".to_owned());

        let sort_dir = self.sort_dir
            .filter(|d| d == "asc" || d == "desc")
            .unwrap_or_else(|| "desc".to_owned());

        let allowed_filters = ["status", "priority", "category"];
        let fields: std::collections::HashMap<String, String> = self.extra.into_iter()
            .filter_map(|(k, v)| {
                k.strip_prefix("filter[")
                    .and_then(|rest| rest.strip_suffix(']'))
                    .filter(|field| allowed_filters.contains(field))
                    .map(|field| (field.to_owned(), v))
            })
            .collect();

        OffsetListFilters { page, per_page, sort_by, sort_dir, fields }
    }
}

#[tracing::instrument(skip(state, auth), fields(request_id))]
async fn list_widgets_admin(
    State(state): State<Arc<AppState>>,
    auth: AuthUser,
    Query(params): Query<OffsetListParams>,
    req: axum::extract::Request,
) -> Result<impl IntoResponse, AppError> {
    let request_id = auth.request_id();
    tracing::Span::current().record("request_id", &request_id);

    let base_path = req.uri().path().to_owned();
    let filters = params.into_filters();
    let page = filters.page;
    let per_page = filters.per_page;

    let result = state.widget_service.list_offset(auth.tenant_id, filters).await?;

    let total_pages = if per_page > 0 { (result.total + per_page - 1) / per_page } else { 0 };
    let links = PageLinks {
        self_link: format!("{base_path}?page={page}&per_page={per_page}"),
        first: format!("{base_path}?page=1&per_page={per_page}"),
        last: format!("{base_path}?page={total_pages}&per_page={per_page}"),
        next: if page < total_pages { Some(format!("{base_path}?page={}&per_page={per_page}", page + 1)) } else { None },
        prev: if page > 1 { Some(format!("{base_path}?page={}&per_page={per_page}", page - 1)) } else { None },
    };

    Ok(Json(OffsetListEnvelope {
        data: result.items,
        meta: OffsetListMeta {
            page,
            per_page,
            total: result.total,
            total_pages,
            request_id,
            timestamp: Utc::now().to_rfc3339(),
        },
        links,
    }))
}
```

## AuthUser Extractor

```rust
use axum::{
    extract::FromRequestParts,
    http::request::Parts,
};

/// Extracts authenticated user info from request extensions.
/// The auth middleware must run before this extractor is used.
pub struct AuthUser {
    pub tenant_id: Uuid,
    pub user_id: Uuid,
    pub roles: Vec<String>,
    request_id: String,
}

impl AuthUser {
    pub fn request_id(&self) -> String {
        self.request_id.clone()
    }
}

#[axum::async_trait]
impl FromRequestParts<Arc<AppState>> for AuthUser {
    type Rejection = AppError;

    async fn from_request_parts(
        parts: &mut Parts,
        _state: &Arc<AppState>,
    ) -> Result<Self, Self::Rejection> {
        let claims = parts.extensions.get::<JwtClaims>()
            .ok_or_else(|| AppError::Unauthorized("missing auth context".into()))?;

        let request_id = parts.extensions.get::<RequestId>()
            .map(|r| r.0.clone())
            .unwrap_or_default();

        Ok(AuthUser {
            tenant_id: claims.tenant_id,
            user_id: claims.sub,
            roles: claims.roles.clone(),
            request_id,
        })
    }
}
```

## Request/Response DTOs with Validation

```rust
use serde::{Deserialize, Serialize};
use validator::Validate;

#[derive(Debug, Deserialize, Validate)]
pub struct CreateWidgetInput {
    #[validate(length(min = 1, max = 255, message = "name must be 1-255 characters"))]
    pub name: String,
    #[validate(length(max = 2000, message = "description must be 2000 characters or fewer"))]
    pub description: Option<String>,
}

#[derive(Debug, Deserialize, Validate)]
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
    pub status: String,
    pub version: i32,
    pub created_at: chrono::DateTime<Utc>,
    pub updated_at: chrono::DateTime<Utc>,
}
```

## Critical Rules

- Every handler MUST use `#[tracing::instrument]` with `skip` for large args and `fields(request_id)`
- Every handler MUST extract `AuthUser` — tenant ID comes from JWT, never from path/body
- Request body validation MUST happen before any side effects (DB, cache, external calls)
- Error responses MUST use the `AppError` → `IntoResponse` path — never manual status codes
- Internal error messages MUST NOT leak to clients — `AppError::Internal` returns generic message
- Pagination MUST enforce max page size (100) via `.clamp(1, 100)` — never return unbounded lists
- Filter fields MUST be allow-listed — never pass arbitrary query params to the DB
- Sort fields MUST be allow-listed — never allow sorting by arbitrary columns
- Every response MUST use the envelope format: `{"data": T, "meta": {...}}`
- DELETE returns 204 No Content — no body
- POST create returns 201 Created with the created resource in the body
- Extractors MUST be ordered: State, AuthUser, Path, Query before Json (body-consuming)
