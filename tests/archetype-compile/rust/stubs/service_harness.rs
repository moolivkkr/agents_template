// HARNESS STUBS for crud-service-rust.md compiled on its own — only names no archetype defines.
use chrono::Utc;
use uuid::Uuid;

use crate::error::AppError;
use crate::models::Widget;

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
            status: "active".into(),
            created_at: now,
            updated_at: now,
            deleted_at: None,
            created_by: user_id,
            updated_by: user_id,
            version: 1,
        }
    }
}
