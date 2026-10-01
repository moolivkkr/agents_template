// HARNESS-ONLY DB tests (not part of the doc): languages/rust.md's repository SQL run against the doc's
// own migration. #[sqlx::test] gives each test a fresh database on DATABASE_URL's server.
use sqlx::PgPool;
use uuid::Uuid;
use yourapp::domain::{CreateOrderRequest, Order, OrderItemRequest, OrderStatus};
use yourapp::error::DomainError;
use yourapp::repositories::{create_order_with_inventory, list_paginated, OrderRepository};

async fn insert_order(pool: &PgPool, tenant_id: Uuid, created_at: &str) -> Uuid {
    let id = Uuid::new_v4();
    sqlx::query("INSERT INTO orders (id, tenant_id, total_cents, created_at) VALUES ($1, $2, 100, $3::timestamptz)")
        .bind(id)
        .bind(tenant_id)
        .bind(created_at)
        .execute(pool)
        .await
        .unwrap();
    id
}

#[sqlx::test(migrations = "./migrations")]
async fn keyset_pages_return_every_row_once_even_when_created_at_ties(pool: PgPool) {
    let tenant = Uuid::new_v4();
    let mut want = Vec::new();
    for _ in 0..5 {
        want.push(insert_order(&pool, tenant, "2026-01-01T00:00:00Z").await); // all the same created_at
    }
    want.push(insert_order(&pool, tenant, "2026-01-02T00:00:00.123456Z").await);
    insert_order(&pool, Uuid::new_v4(), "2026-01-01T00:00:00Z").await; // another tenant's

    let (mut seen, mut cursor, mut pages) = (Vec::new(), None::<String>, 0);
    loop {
        let (page, next) = list_paginated(&pool, tenant, cursor.as_deref(), 2).await.unwrap();
        assert!(page.len() <= 2);
        assert!(page.iter().all(|o| o.tenant_id == tenant));
        seen.extend(page.iter().map(|o| o.id));
        pages += 1;
        match next {
            Some(c) => cursor = Some(c),
            None => break,
        }
    }
    assert_eq!(pages, 3);
    let mut sorted = seen.clone();
    sorted.sort();
    sorted.dedup();
    assert_eq!(sorted.len(), 6, "no row skipped or repeated: {seen:?}");
    want.sort();
    assert_eq!(sorted, want);
}

#[sqlx::test(migrations = "./migrations")]
async fn a_garbled_cursor_is_a_400_on_cursor(pool: PgPool) {
    for bad in ["%%%", "Zm9v", "MjAyNi0wMS0wMXxub3QtYS11dWlk"] {
        match list_paginated(&pool, Uuid::new_v4(), Some(bad), 10).await {
            Err(DomainError::Validation(details)) => assert_eq!(details[0].field, "cursor"),
            other => panic!("cursor {bad:?}: {:?}", other.map(|(o, c)| (o.len(), c))),
        }
    }
}

#[sqlx::test(migrations = "./migrations")]
async fn short_stock_rolls_the_whole_order_back(pool: PgPool) {
    let tenant = Uuid::new_v4();
    sqlx::query("INSERT INTO inventory (tenant_id, sku, quantity) VALUES ($1, 'A', 5), ($1, 'B', 1)")
        .bind(tenant)
        .execute(&pool)
        .await
        .unwrap();
    let item = |sku: &str, quantity| OrderItemRequest { sku: sku.into(), quantity };

    let short = CreateOrderRequest { total_cents: 500, items: vec![item("A", 2), item("B", 2)] };
    let err = create_order_with_inventory(&pool, tenant, short).await.unwrap_err();
    assert!(matches!(err, DomainError::Conflict(_)), "{err:?}");
    let orders: i64 = sqlx::query_scalar("SELECT count(*) FROM orders").fetch_one(&pool).await.unwrap();
    let a: i32 = sqlx::query_scalar("SELECT quantity FROM inventory WHERE sku = 'A'").fetch_one(&pool).await.unwrap();
    assert_eq!((orders, a), (0, 5), "the order insert and A's reservation were rolled back");

    let enough = CreateOrderRequest { total_cents: 200, items: vec![item("A", 2)] };
    let order = create_order_with_inventory(&pool, tenant, enough).await.unwrap();
    assert_eq!((order.status, order.total_cents, order.version), (OrderStatus::Pending, 200, 1));
    let a: i32 = sqlx::query_scalar("SELECT quantity FROM inventory WHERE sku = 'A'").fetch_one(&pool).await.unwrap();
    assert_eq!(a, 3);
}

#[sqlx::test(migrations = "./migrations")]
async fn optimistic_lock_conflict_is_409_and_a_missing_order_404(pool: PgPool) {
    let repo = OrderRepository::new(pool.clone());
    let tenant = Uuid::new_v4();
    let saved = repo.save(&Order::new(Uuid::new_v4(), tenant)).await.unwrap();

    let updated = repo.update_with_optimistic_lock(tenant, saved.id, OrderStatus::Confirmed, 1).await.unwrap();
    assert_eq!((updated.status, updated.version), (OrderStatus::Confirmed, 2));

    let stale = repo.update_with_optimistic_lock(tenant, saved.id, OrderStatus::Shipped, 1).await;
    assert!(matches!(stale, Err(DomainError::Conflict(_))), "stale version");
    let foreign = repo.update_with_optimistic_lock(Uuid::new_v4(), saved.id, OrderStatus::Shipped, 2).await;
    assert!(matches!(foreign, Err(DomainError::NotFound { .. })), "another tenant's order is a 404");

    repo.soft_delete(tenant, saved.id).await.unwrap();
    assert!(matches!(repo.soft_delete(tenant, saved.id).await, Err(DomainError::NotFound { .. })));
}
