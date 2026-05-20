---
skill: crud-repository-test-rust
description: Rust repository integration test archetype — sqlx::test with automatic migration + rollback, real PostgreSQL CRUD, cursor + offset pagination, soft delete, optimistic locking, unique constraints, multi-tenant isolation, batch operations
version: "1.0"
tags:
  - rust
  - sqlx
  - repository
  - postgres
  - integration-test
  - archetype
  - backend
  - testing
---

# CRUD Repository Test Archetype (Rust / sqlx::test)

Complete integration test template for the repository layer against a real PostgreSQL database. Every generated repository test MUST follow this pattern.

## Test File Location

```
tests/
  repository/
    mod.rs
    widget_repo_test.rs  <- THIS file
src/
  repositories/
    widget.rs            <- production code (PgWidgetRepository)
```

Rule: Repository integration tests live in `tests/` and run against real Postgres. They use `#[sqlx::test]` for automatic database creation, migration, and rollback.

## Dependencies (Cargo.toml)

```toml
[dev-dependencies]
tokio = { version = "1", features = ["full", "test-util"] }
sqlx = { version = "0.8", features = ["runtime-tokio", "postgres", "migrate"] }
uuid = { version = "1", features = ["v4"] }
chrono = { version = "0.4", features = ["serde"] }
serde_json = "1"
```

## Test Configuration

```rust
// tests/repository/mod.rs

/// Set DATABASE_URL in .env or environment:
///   DATABASE_URL=postgres://postgres:postgres@localhost:5432/postgres
///
/// sqlx::test creates a temporary database per test, runs migrations,
/// and drops it after the test completes (even on panic).
///
/// Migrations must be in `./migrations/` directory.
```

## Test Factory

```rust
// tests/repository/widget_repo_test.rs

use chrono::Utc;
use sqlx::PgPool;
use uuid::Uuid;

use yourapp::domain::{ListFilters, OffsetListFilters};
use yourapp::error::AppError;
use yourapp::models::Widget;
use yourapp::repositories::widget::PgWidgetRepository;
use yourapp::traits::repository::WidgetRepository;

/// Build a Widget with sensible defaults for a given tenant.
fn make_widget(tenant_id: Uuid) -> Widget {
    let now = Utc::now();
    let user_id = Uuid::new_v4();
    Widget {
        id: Uuid::new_v4(),
        tenant_id,
        name: format!("widget-{}", &Uuid::new_v4().to_string()[..8]),
        description: Some("integration test widget".into()),
        status: "active".into(),
        created_at: now,
        updated_at: now,
        deleted_at: None,
        created_by: user_id,
        updated_by: user_id,
        version: 1,
    }
}

/// Build a Widget with a specific name (for uniqueness testing).
fn make_widget_named(tenant_id: Uuid, name: &str) -> Widget {
    let mut w = make_widget(tenant_id);
    w.name = name.into();
    w
}

/// Build a Widget with a specific version (for optimistic locking tests).
fn make_widget_versioned(tenant_id: Uuid, version: i32) -> Widget {
    let mut w = make_widget(tenant_id);
    w.version = version;
    w
}
```

## Create Tests

```rust
#[sqlx::test(migrations = "./migrations")]
async fn create_and_retrieve(pool: PgPool) {
    let repo = PgWidgetRepository::new(pool);
    let tenant_id = Uuid::new_v4();
    let widget = make_widget(tenant_id);
    let widget_id = widget.id;

    // Create
    repo.create(&widget).await.expect("create should succeed");

    // Retrieve
    let fetched = repo.get_by_id(tenant_id, widget_id).await.expect("get should succeed");

    assert_eq!(fetched.id, widget_id);
    assert_eq!(fetched.tenant_id, tenant_id);
    assert_eq!(fetched.name, widget.name);
    assert_eq!(fetched.description, widget.description);
    assert_eq!(fetched.status, "active");
    assert_eq!(fetched.version, 1);
    assert!(fetched.deleted_at.is_none());
}

#[sqlx::test(migrations = "./migrations")]
async fn create_duplicate_id_returns_conflict(pool: PgPool) {
    let repo = PgWidgetRepository::new(pool);
    let tenant_id = Uuid::new_v4();
    let widget = make_widget(tenant_id);

    repo.create(&widget).await.expect("first create should succeed");

    // Attempt to create again with same ID
    let result = repo.create(&widget).await;

    assert!(result.is_err());
    assert!(
        matches!(result.unwrap_err(), AppError::Conflict { .. }),
        "duplicate ID must return Conflict"
    );
}

#[sqlx::test(migrations = "./migrations")]
async fn create_unique_constraint_violation(pool: PgPool) {
    let repo = PgWidgetRepository::new(pool);
    let tenant_id = Uuid::new_v4();

    // Assuming a unique constraint on (tenant_id, name)
    let w1 = make_widget_named(tenant_id, "Unique Name");
    let w2 = make_widget_named(tenant_id, "Unique Name");

    repo.create(&w1).await.expect("first create should succeed");
    let result = repo.create(&w2).await;

    assert!(result.is_err());
    assert!(
        matches!(result.unwrap_err(), AppError::Conflict { .. }),
        "duplicate name within tenant must return Conflict"
    );
}

#[sqlx::test(migrations = "./migrations")]
async fn create_same_name_different_tenants_ok(pool: PgPool) {
    let repo = PgWidgetRepository::new(pool);
    let tenant_a = Uuid::new_v4();
    let tenant_b = Uuid::new_v4();

    let w1 = make_widget_named(tenant_a, "Same Name");
    let w2 = make_widget_named(tenant_b, "Same Name");

    repo.create(&w1).await.expect("tenant A create should succeed");
    repo.create(&w2).await.expect("tenant B create should succeed — different tenant");
}
```

## GetByID Tests

```rust
#[sqlx::test(migrations = "./migrations")]
async fn get_by_id_not_found(pool: PgPool) {
    let repo = PgWidgetRepository::new(pool);
    let tenant_id = Uuid::new_v4();
    let random_id = Uuid::new_v4();

    let result = repo.get_by_id(tenant_id, random_id).await;

    assert!(result.is_err());
    assert!(matches!(result.unwrap_err(), AppError::NotFound { .. }));
}

#[sqlx::test(migrations = "./migrations")]
async fn get_by_id_soft_deleted_returns_not_found(pool: PgPool) {
    let repo = PgWidgetRepository::new(pool);
    let tenant_id = Uuid::new_v4();
    let widget = make_widget(tenant_id);
    let widget_id = widget.id;

    repo.create(&widget).await.unwrap();
    repo.soft_delete(tenant_id, widget_id).await.unwrap();

    // Soft-deleted widget must not be returned
    let result = repo.get_by_id(tenant_id, widget_id).await;
    assert!(result.is_err());
    assert!(matches!(result.unwrap_err(), AppError::NotFound { .. }));
}

#[sqlx::test(migrations = "./migrations")]
async fn get_by_id_wrong_tenant_returns_not_found(pool: PgPool) {
    let repo = PgWidgetRepository::new(pool);
    let tenant_a = Uuid::new_v4();
    let tenant_b = Uuid::new_v4();

    let widget = make_widget(tenant_a);
    let widget_id = widget.id;

    repo.create(&widget).await.unwrap();

    // Tenant B cannot see Tenant A's widget
    let result = repo.get_by_id(tenant_b, widget_id).await;
    assert!(result.is_err());
    assert!(
        matches!(result.unwrap_err(), AppError::NotFound { .. }),
        "wrong tenant must return NotFound, not Forbidden"
    );
}
```

## Update Tests with Optimistic Locking

```rust
#[sqlx::test(migrations = "./migrations")]
async fn update_happy_path(pool: PgPool) {
    let repo = PgWidgetRepository::new(pool);
    let tenant_id = Uuid::new_v4();

    let mut widget = make_widget(tenant_id);
    repo.create(&widget).await.unwrap();

    // Apply changes (service layer normally does this)
    widget.name = "Updated Name".into();
    widget.description = Some("Updated description".into());
    widget.updated_at = Utc::now();
    widget.version = 2; // increment from 1 to 2

    repo.update(&widget).await.expect("update should succeed");

    let fetched = repo.get_by_id(tenant_id, widget.id).await.unwrap();
    assert_eq!(fetched.name, "Updated Name");
    assert_eq!(fetched.description.as_deref(), Some("Updated description"));
    assert_eq!(fetched.version, 2);
}

#[sqlx::test(migrations = "./migrations")]
async fn update_version_conflict(pool: PgPool) {
    let repo = PgWidgetRepository::new(pool);
    let tenant_id = Uuid::new_v4();

    let mut widget = make_widget(tenant_id);
    repo.create(&widget).await.unwrap();

    // Simulate concurrent update: set wrong version
    widget.name = "Stale Update".into();
    widget.version = 5; // expects previous version 4, but actual is 1

    let result = repo.update(&widget).await;
    assert!(result.is_err());
    assert!(
        matches!(result.unwrap_err(), AppError::Conflict { .. }),
        "version mismatch must return Conflict"
    );

    // Verify original data unchanged
    let fetched = repo.get_by_id(tenant_id, widget.id).await.unwrap();
    assert_ne!(fetched.name, "Stale Update");
    assert_eq!(fetched.version, 1);
}

#[sqlx::test(migrations = "./migrations")]
async fn update_soft_deleted_returns_conflict(pool: PgPool) {
    let repo = PgWidgetRepository::new(pool);
    let tenant_id = Uuid::new_v4();

    let mut widget = make_widget(tenant_id);
    repo.create(&widget).await.unwrap();
    repo.soft_delete(tenant_id, widget.id).await.unwrap();

    // Attempt to update a soft-deleted widget
    widget.name = "Ghost Update".into();
    widget.version = 2;

    let result = repo.update(&widget).await;
    assert!(result.is_err());
    assert!(
        matches!(result.unwrap_err(), AppError::Conflict { .. }),
        "updating soft-deleted widget must fail"
    );
}

#[sqlx::test(migrations = "./migrations")]
async fn concurrent_updates_one_wins(pool: PgPool) {
    let repo = PgWidgetRepository::new(pool);
    let tenant_id = Uuid::new_v4();

    let widget = make_widget(tenant_id);
    repo.create(&widget).await.unwrap();

    // Two "concurrent" readers get version 1
    let mut update_a = widget.clone();
    let mut update_b = widget.clone();

    update_a.name = "Update A".into();
    update_a.version = 2; // expects previous version 1

    update_b.name = "Update B".into();
    update_b.version = 2; // also expects previous version 1

    // First update succeeds
    repo.update(&update_a).await.expect("first update should succeed");

    // Second update fails — version 1 no longer exists
    let result = repo.update(&update_b).await;
    assert!(result.is_err());
    assert!(matches!(result.unwrap_err(), AppError::Conflict { .. }));

    // Verify A's update won
    let fetched = repo.get_by_id(tenant_id, widget.id).await.unwrap();
    assert_eq!(fetched.name, "Update A");
    assert_eq!(fetched.version, 2);
}
```

## Soft Delete Tests

```rust
#[sqlx::test(migrations = "./migrations")]
async fn soft_delete_happy_path(pool: PgPool) {
    let repo = PgWidgetRepository::new(pool);
    let tenant_id = Uuid::new_v4();

    let widget = make_widget(tenant_id);
    let widget_id = widget.id;
    repo.create(&widget).await.unwrap();

    repo.soft_delete(tenant_id, widget_id).await.expect("soft delete should succeed");

    // Verify get returns NotFound
    let result = repo.get_by_id(tenant_id, widget_id).await;
    assert!(matches!(result.unwrap_err(), AppError::NotFound { .. }));

    // Verify the row still exists in the database (soft deleted)
    let row = sqlx::query!(
        "SELECT deleted_at FROM widgets WHERE id = $1",
        widget_id,
    )
    .fetch_one(&repo.pool_ref())
    .await
    .expect("row must still exist");

    assert!(row.deleted_at.is_some(), "deleted_at must be set");
}

#[sqlx::test(migrations = "./migrations")]
async fn soft_delete_not_found(pool: PgPool) {
    let repo = PgWidgetRepository::new(pool);
    let tenant_id = Uuid::new_v4();
    let random_id = Uuid::new_v4();

    let result = repo.soft_delete(tenant_id, random_id).await;
    assert!(result.is_err());
    assert!(matches!(result.unwrap_err(), AppError::NotFound { .. }));
}

#[sqlx::test(migrations = "./migrations")]
async fn soft_delete_idempotent_returns_not_found(pool: PgPool) {
    let repo = PgWidgetRepository::new(pool);
    let tenant_id = Uuid::new_v4();

    let widget = make_widget(tenant_id);
    let widget_id = widget.id;
    repo.create(&widget).await.unwrap();

    // First delete succeeds
    repo.soft_delete(tenant_id, widget_id).await.unwrap();

    // Second delete returns NotFound (already deleted)
    let result = repo.soft_delete(tenant_id, widget_id).await;
    assert!(matches!(result.unwrap_err(), AppError::NotFound { .. }));
}

#[sqlx::test(migrations = "./migrations")]
async fn soft_delete_wrong_tenant_returns_not_found(pool: PgPool) {
    let repo = PgWidgetRepository::new(pool);
    let tenant_a = Uuid::new_v4();
    let tenant_b = Uuid::new_v4();

    let widget = make_widget(tenant_a);
    let widget_id = widget.id;
    repo.create(&widget).await.unwrap();

    // Tenant B cannot delete Tenant A's widget
    let result = repo.soft_delete(tenant_b, widget_id).await;
    assert!(matches!(result.unwrap_err(), AppError::NotFound { .. }));

    // Verify widget still exists for Tenant A
    let fetched = repo.get_by_id(tenant_a, widget_id).await;
    assert!(fetched.is_ok());
}

#[sqlx::test(migrations = "./migrations")]
async fn soft_deleted_items_excluded_from_list(pool: PgPool) {
    let repo = PgWidgetRepository::new(pool);
    let tenant_id = Uuid::new_v4();

    let w1 = make_widget(tenant_id);
    let w2 = make_widget(tenant_id);
    let w3 = make_widget(tenant_id);
    repo.create(&w1).await.unwrap();
    repo.create(&w2).await.unwrap();
    repo.create(&w3).await.unwrap();

    // Soft delete one widget
    repo.soft_delete(tenant_id, w2.id).await.unwrap();

    let filters = ListFilters {
        cursor: None,
        page_size: 100,
        sort_by: "created_at".into(),
        sort_dir: "desc".into(),
        fields: Default::default(),
    };

    let result = repo.list(tenant_id, &filters).await.unwrap();
    assert_eq!(result.items.len(), 2, "soft-deleted item must be excluded");
    assert_eq!(result.total, 2);

    let ids: Vec<Uuid> = result.items.iter().map(|w| w.id).collect();
    assert!(!ids.contains(&w2.id), "deleted widget must not appear in list");
}
```

## Cursor Pagination Tests

```rust
#[sqlx::test(migrations = "./migrations")]
async fn list_cursor_pagination_forward(pool: PgPool) {
    let repo = PgWidgetRepository::new(pool);
    let tenant_id = Uuid::new_v4();

    // Insert 7 widgets with distinct timestamps
    let mut widgets = Vec::new();
    for i in 0..7 {
        let mut w = make_widget_named(tenant_id, &format!("Widget {i:02}"));
        // Offset timestamps to ensure ordering
        w.created_at = Utc::now() + chrono::Duration::milliseconds(i * 100);
        widgets.push(w.clone());
        repo.create(&w).await.unwrap();
    }

    // Page 1: first 3 items
    let filters = ListFilters {
        cursor: None,
        page_size: 3,
        sort_by: "created_at".into(),
        sort_dir: "desc".into(),
        fields: Default::default(),
    };

    let page1 = repo.list(tenant_id, &filters).await.unwrap();
    assert_eq!(page1.items.len(), 3);
    assert!(page1.has_more);
    assert!(page1.cursor.is_some());

    // Page 2: next 3 items using cursor
    let filters2 = ListFilters {
        cursor: page1.cursor,
        page_size: 3,
        sort_by: "created_at".into(),
        sort_dir: "desc".into(),
        fields: Default::default(),
    };

    let page2 = repo.list(tenant_id, &filters2).await.unwrap();
    assert_eq!(page2.items.len(), 3);
    assert!(page2.has_more);

    // Page 3: last 1 item
    let filters3 = ListFilters {
        cursor: page2.cursor,
        page_size: 3,
        sort_by: "created_at".into(),
        sort_dir: "desc".into(),
        fields: Default::default(),
    };

    let page3 = repo.list(tenant_id, &filters3).await.unwrap();
    assert_eq!(page3.items.len(), 1);
    assert!(!page3.has_more);

    // Verify no overlap between pages
    let all_ids: Vec<Uuid> = page1.items.iter()
        .chain(page2.items.iter())
        .chain(page3.items.iter())
        .map(|w| w.id)
        .collect();
    let unique_ids: std::collections::HashSet<Uuid> = all_ids.iter().copied().collect();
    assert_eq!(all_ids.len(), unique_ids.len(), "pages must not overlap");
    assert_eq!(all_ids.len(), 7, "all items must be returned across pages");
}

#[sqlx::test(migrations = "./migrations")]
async fn list_cursor_pagination_ascending(pool: PgPool) {
    let repo = PgWidgetRepository::new(pool);
    let tenant_id = Uuid::new_v4();

    for i in 0..5 {
        let mut w = make_widget_named(tenant_id, &format!("Asc Widget {i:02}"));
        w.created_at = Utc::now() + chrono::Duration::milliseconds(i * 100);
        repo.create(&w).await.unwrap();
    }

    let filters = ListFilters {
        cursor: None,
        page_size: 3,
        sort_by: "created_at".into(),
        sort_dir: "asc".into(),
        fields: Default::default(),
    };

    let page1 = repo.list(tenant_id, &filters).await.unwrap();
    assert_eq!(page1.items.len(), 3);
    assert!(page1.has_more);

    // Verify ascending order
    for i in 0..page1.items.len() - 1 {
        assert!(
            page1.items[i].created_at <= page1.items[i + 1].created_at,
            "items must be in ascending order"
        );
    }
}

#[sqlx::test(migrations = "./migrations")]
async fn list_empty_result(pool: PgPool) {
    let repo = PgWidgetRepository::new(pool);
    let tenant_id = Uuid::new_v4();

    let filters = ListFilters {
        cursor: None,
        page_size: 20,
        sort_by: "created_at".into(),
        sort_dir: "desc".into(),
        fields: Default::default(),
    };

    let result = repo.list(tenant_id, &filters).await.unwrap();
    assert_eq!(result.items.len(), 0);
    assert!(!result.has_more);
    assert_eq!(result.total, 0);
    assert!(result.cursor.is_none());
}

#[sqlx::test(migrations = "./migrations")]
async fn list_invalid_cursor_returns_validation_error(pool: PgPool) {
    let repo = PgWidgetRepository::new(pool);
    let tenant_id = Uuid::new_v4();

    let filters = ListFilters {
        cursor: Some("not-valid-base64-cursor".into()),
        page_size: 20,
        sort_by: "created_at".into(),
        sort_dir: "desc".into(),
        fields: Default::default(),
    };

    let result = repo.list(tenant_id, &filters).await;
    assert!(result.is_err());
    assert!(matches!(result.unwrap_err(), AppError::Validation { .. }));
}
```

## Offset Pagination Tests

```rust
#[sqlx::test(migrations = "./migrations")]
async fn list_offset_pagination(pool: PgPool) {
    let repo = PgWidgetRepository::new(pool);
    let tenant_id = Uuid::new_v4();

    for i in 0..10 {
        let mut w = make_widget_named(tenant_id, &format!("Offset Widget {i:02}"));
        w.created_at = Utc::now() + chrono::Duration::milliseconds(i * 100);
        repo.create(&w).await.unwrap();
    }

    // Page 1
    let filters = OffsetListFilters {
        page: 1,
        per_page: 3,
        sort_by: "created_at".into(),
        sort_dir: "desc".into(),
        fields: Default::default(),
    };

    let page1 = repo.list_offset(tenant_id, &filters).await.unwrap();
    assert_eq!(page1.items.len(), 3);
    assert_eq!(page1.total, 10);

    // Page 2
    let filters2 = OffsetListFilters {
        page: 2,
        per_page: 3,
        ..filters.clone()
    };

    let page2 = repo.list_offset(tenant_id, &filters2).await.unwrap();
    assert_eq!(page2.items.len(), 3);
    assert_eq!(page2.total, 10);

    // Verify no overlap
    let page1_ids: Vec<Uuid> = page1.items.iter().map(|w| w.id).collect();
    let page2_ids: Vec<Uuid> = page2.items.iter().map(|w| w.id).collect();
    for id in &page2_ids {
        assert!(!page1_ids.contains(id), "offset pages must not overlap");
    }

    // Last page (page 4: items 10-10, just 1 item)
    let filters_last = OffsetListFilters {
        page: 4,
        per_page: 3,
        ..filters.clone()
    };

    let last_page = repo.list_offset(tenant_id, &filters_last).await.unwrap();
    assert_eq!(last_page.items.len(), 1);
    assert_eq!(last_page.total, 10);
}

#[sqlx::test(migrations = "./migrations")]
async fn list_offset_beyond_total_returns_empty(pool: PgPool) {
    let repo = PgWidgetRepository::new(pool);
    let tenant_id = Uuid::new_v4();

    let w = make_widget(tenant_id);
    repo.create(&w).await.unwrap();

    let filters = OffsetListFilters {
        page: 100, // far beyond actual data
        per_page: 20,
        sort_by: "created_at".into(),
        sort_dir: "desc".into(),
        fields: Default::default(),
    };

    let result = repo.list_offset(tenant_id, &filters).await.unwrap();
    assert_eq!(result.items.len(), 0);
    assert_eq!(result.total, 1); // total still reflects actual count
}
```

## Multi-Tenant Isolation Tests

```rust
#[sqlx::test(migrations = "./migrations")]
async fn tenant_isolation_list(pool: PgPool) {
    let repo = PgWidgetRepository::new(pool);
    let tenant_a = Uuid::new_v4();
    let tenant_b = Uuid::new_v4();

    // Create widgets for both tenants
    for i in 0..3 {
        let w = make_widget_named(tenant_a, &format!("A Widget {i}"));
        repo.create(&w).await.unwrap();
    }
    for i in 0..5 {
        let w = make_widget_named(tenant_b, &format!("B Widget {i}"));
        repo.create(&w).await.unwrap();
    }

    let filters = ListFilters {
        cursor: None,
        page_size: 100,
        sort_by: "created_at".into(),
        sort_dir: "desc".into(),
        fields: Default::default(),
    };

    // Tenant A only sees their 3 widgets
    let result_a = repo.list(tenant_a, &filters).await.unwrap();
    assert_eq!(result_a.items.len(), 3);
    assert_eq!(result_a.total, 3);
    assert!(result_a.items.iter().all(|w| w.tenant_id == tenant_a));

    // Tenant B only sees their 5 widgets
    let result_b = repo.list(tenant_b, &filters).await.unwrap();
    assert_eq!(result_b.items.len(), 5);
    assert_eq!(result_b.total, 5);
    assert!(result_b.items.iter().all(|w| w.tenant_id == tenant_b));
}

#[sqlx::test(migrations = "./migrations")]
async fn tenant_isolation_update(pool: PgPool) {
    let repo = PgWidgetRepository::new(pool);
    let tenant_a = Uuid::new_v4();
    let tenant_b = Uuid::new_v4();

    let widget = make_widget(tenant_a);
    let widget_id = widget.id;
    repo.create(&widget).await.unwrap();

    // Attempt to update with wrong tenant_id
    let mut fake_update = widget.clone();
    fake_update.tenant_id = tenant_b; // wrong tenant
    fake_update.name = "Hijacked".into();
    fake_update.version = 2;

    let result = repo.update(&fake_update).await;
    assert!(result.is_err(), "cross-tenant update must fail");

    // Verify original unchanged
    let fetched = repo.get_by_id(tenant_a, widget_id).await.unwrap();
    assert_ne!(fetched.name, "Hijacked");
}

#[sqlx::test(migrations = "./migrations")]
async fn tenant_isolation_delete(pool: PgPool) {
    let repo = PgWidgetRepository::new(pool);
    let tenant_a = Uuid::new_v4();
    let tenant_b = Uuid::new_v4();

    let widget = make_widget(tenant_a);
    let widget_id = widget.id;
    repo.create(&widget).await.unwrap();

    // Tenant B cannot delete Tenant A's widget
    let result = repo.soft_delete(tenant_b, widget_id).await;
    assert!(matches!(result.unwrap_err(), AppError::NotFound { .. }));

    // Widget still exists for Tenant A
    let fetched = repo.get_by_id(tenant_a, widget_id).await;
    assert!(fetched.is_ok());
}
```

## Batch Operations Tests

```rust
#[sqlx::test(migrations = "./migrations")]
async fn batch_create_happy_path(pool: PgPool) {
    let repo = PgWidgetRepository::new(pool);
    let tenant_id = Uuid::new_v4();

    let widgets: Vec<Widget> = (0..50)
        .map(|i| make_widget_named(tenant_id, &format!("Batch Widget {i:03}")))
        .collect();

    repo.batch_create(&widgets).await.expect("batch create should succeed");

    let filters = ListFilters {
        cursor: None,
        page_size: 100,
        sort_by: "created_at".into(),
        sort_dir: "desc".into(),
        fields: Default::default(),
    };

    let result = repo.list(tenant_id, &filters).await.unwrap();
    assert_eq!(result.total, 50);
}

#[sqlx::test(migrations = "./migrations")]
async fn batch_create_empty_slice(pool: PgPool) {
    let repo = PgWidgetRepository::new(pool);

    // Empty batch should succeed (no-op)
    repo.batch_create(&[]).await.expect("empty batch should succeed");
}

#[sqlx::test(migrations = "./migrations")]
async fn batch_create_partial_failure_on_duplicate(pool: PgPool) {
    let repo = PgWidgetRepository::new(pool);
    let tenant_id = Uuid::new_v4();

    let w1 = make_widget(tenant_id);
    repo.create(&w1).await.unwrap();

    // Batch includes the already-existing widget
    let w2 = make_widget(tenant_id);
    let batch = vec![w1.clone(), w2]; // w1 already exists

    let result = repo.batch_create(&batch).await;
    assert!(result.is_err(), "batch with duplicate must fail");
}
```

## Filter Tests

```rust
#[sqlx::test(migrations = "./migrations")]
async fn list_with_status_filter(pool: PgPool) {
    let repo = PgWidgetRepository::new(pool);
    let tenant_id = Uuid::new_v4();

    let mut active = make_widget(tenant_id);
    active.status = "active".into();

    let mut archived = make_widget(tenant_id);
    archived.status = "archived".into();

    repo.create(&active).await.unwrap();
    repo.create(&archived).await.unwrap();

    let mut fields = std::collections::HashMap::new();
    fields.insert("status".into(), "active".into());

    let filters = ListFilters {
        cursor: None,
        page_size: 100,
        sort_by: "created_at".into(),
        sort_dir: "desc".into(),
        fields,
    };

    let result = repo.list(tenant_id, &filters).await.unwrap();
    assert_eq!(result.items.len(), 1);
    assert_eq!(result.items[0].status, "active");
}

#[sqlx::test(migrations = "./migrations")]
async fn list_with_multiple_filters(pool: PgPool) {
    let repo = PgWidgetRepository::new(pool);
    let tenant_id = Uuid::new_v4();

    // Create several widgets with different statuses
    for (name, status) in [("A", "active"), ("B", "active"), ("C", "archived")] {
        let mut w = make_widget_named(tenant_id, name);
        w.status = status.into();
        repo.create(&w).await.unwrap();
    }

    let mut fields = std::collections::HashMap::new();
    fields.insert("status".into(), "active".into());

    let filters = ListFilters {
        cursor: None,
        page_size: 100,
        sort_by: "name".into(),
        sort_dir: "asc".into(),
        fields,
    };

    let result = repo.list(tenant_id, &filters).await.unwrap();
    assert_eq!(result.items.len(), 2);
    assert_eq!(result.items[0].name, "A");
    assert_eq!(result.items[1].name, "B");
}
```

## Critical Rules

- Every test MUST use `#[sqlx::test(migrations = "./migrations")]` — automatic DB creation, migration, and cleanup
- Every test gets its own isolated database — no test can affect another
- Every query tested MUST include tenant_id scoping — verify cross-tenant access is blocked
- Soft delete tests MUST verify that `deleted_at` is set AND that the row still exists
- Soft-deleted items MUST be excluded from `get_by_id` and `list` results
- Optimistic locking tests MUST verify that stale updates are rejected with `Conflict`
- Concurrent update tests MUST verify exactly one writer wins
- Cursor pagination tests MUST verify: no overlap, all items returned, correct ordering
- Offset pagination tests MUST verify: correct page boundaries, total count unchanged
- Batch operations MUST handle empty slices gracefully
- Unique constraint violations MUST map to `AppError::Conflict`
- Invalid cursor values MUST return `AppError::Validation`
- Multi-tenant isolation MUST be tested for all CRUD operations
- Use `Uuid::new_v4()` for every test entity — never hardcode UUIDs
- Factory functions MUST generate unique names to avoid constraint collisions
