// HARNESS STUBS — the GraphQL types and service frameworks/graphql.md's Rust resolvers use. The doc
// shows the resolvers (and the error mapping), not the schema types; these are the minimal ones, and
// the service fails on demand so the smoke tests can check what reaches the client.
#![allow(dead_code)]
use std::collections::HashMap;
use std::sync::Arc;

use async_graphql::{dataloader::Loader, InputObject, SimpleObject, ID};
use uuid::Uuid;

use crate::error::AppError;

pub struct QueryRoot;

/// Set per request from the verified token (never from a client header).
pub struct AuthContext {
    pub tenant_id: Uuid,
}

pub struct Widget {
    pub id: Uuid,
    pub created_by_id: Uuid,
}

#[derive(SimpleObject)]
pub struct WidgetConnection {
    pub total_count: i32,
    pub page_size: i32,
}

#[derive(InputObject)]
pub struct WidgetFilter {
    pub status: Option<String>,
}

#[derive(SimpleObject, Clone)]
pub struct User {
    pub id: ID,
}

pub struct UserLoader;

impl Loader<Uuid> for UserLoader {
    type Value = User;
    type Error = Arc<sqlx::Error>;

    async fn load(&self, keys: &[Uuid]) -> Result<HashMap<Uuid, User>, Self::Error> {
        Ok(keys.iter().map(|k| (*k, User { id: ID(k.to_string()) })).collect())
    }
}

/// `fail`: Some(error) makes every call fail with it (smoke tests).
pub struct WidgetService {
    pub fail: Option<fn() -> AppError>,
}

impl WidgetService {
    pub async fn get(&self, _tenant_id: Uuid, id: &ID) -> Result<Option<Widget>, AppError> {
        if let Some(fail) = self.fail {
            return Err(fail());
        }
        let id = Uuid::parse_str(id).map_err(|_| AppError::not_found("Widget"))?;
        Ok(Some(Widget { id, created_by_id: Uuid::new_v4() }))
    }

    pub async fn list(&self, _tenant_id: Uuid, first: i32, _after: Option<String>, _filter: Option<WidgetFilter>) -> Result<WidgetConnection, AppError> {
        if let Some(fail) = self.fail {
            return Err(fail());
        }
        Ok(WidgetConnection { total_count: 0, page_size: first })
    }
}
