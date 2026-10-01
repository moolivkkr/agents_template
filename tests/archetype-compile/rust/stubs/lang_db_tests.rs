// HARNESS-ONLY DB tests (not part of the doc): languages/rust.md's repository SQL run against the doc's
// own migration (RLS on orders and inventory). #[sqlx::test] makes a fresh database per test and
// migrates it as the server's admin user, who then owns the tables. Every repository call below runs
// through `app_pool`: a NOSUPERUSER NOBYPASSRLS role that owns nothing and has DML grants only — the
// way a deployed service connects — so the RLS policies apply to every query.
use sqlx::{postgres::PgPoolOptions, PgPool};
use uuid::Uuid;
use yourapp::domain::{CreateOrderRequest, Order, OrderItemRequest, OrderStatus};
use yourapp::error::DomainError;
use yourapp::repositories::{begin_tenant_tx, create_order_with_inventory, list_paginated, OrderRepository};

const APP_ROLE: &str = "lang_app_rls";

/// A pool connected as the app role (created once per server; tests run in parallel).
async fn app_pool(admin: &PgPool) -> PgPool {
    sqlx::raw_sql(
        "DO $$ BEGIN
             CREATE ROLE lang_app_rls LOGIN PASSWORD 'lang_app_rls' NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
         EXCEPTION WHEN duplicate_object OR unique_violation THEN NULL; END $$;
         GRANT USAGE ON SCHEMA public TO lang_app_rls;
         GRANT SELECT, INSERT, UPDATE, DELETE ON orders, inventory TO lang_app_rls;",
    )
    .execute(admin)
    .await
    .unwrap();
    let opts = (*admin.connect_options()).clone().username(APP_ROLE).password(APP_ROLE);
    let app = PgPoolOptions::new().max_connections(4).connect_with(opts).await.unwrap();

    // the role is what this file claims: not a superuser, can't bypass RLS, owns no table
    let (superuser, bypass): (bool, bool) =
        sqlx::query_as("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
            .fetch_one(&app)
            .await
            .unwrap();
    let owned: i64 = sqlx::query_scalar(
        "SELECT count(*) FROM pg_class WHERE relowner = (SELECT oid FROM pg_roles WHERE rolname = current_user)",
    )
    .fetch_one(&app)
    .await
    .unwrap();
    assert!(!superuser && !bypass && owned == 0, "app role: super={superuser} bypassrls={bypass} owns={owned}");
    app
}

async fn insert_order(app: &PgPool, tenant_id: Uuid, created_at: &str) -> Uuid {
    let id = Uuid::new_v4();
    let mut tx = begin_tenant_tx(app, tenant_id).await.unwrap();
    sqlx::query("INSERT INTO orders (id, tenant_id, total_cents, created_at) VALUES ($1, $2, 100, $3::timestamptz)")
        .bind(id)
        .bind(tenant_id)
        .bind(created_at)
        .execute(&mut *tx)
        .await
        .unwrap();
    tx.commit().await.unwrap();
    id
}

/// What RLS lets this tenant see with NO tenant_id in the WHERE clause.
async fn visible_order_count(app: &PgPool, tenant_id: Uuid) -> i64 {
    let mut tx = begin_tenant_tx(app, tenant_id).await.unwrap();
    let n = sqlx::query_scalar("SELECT count(*) FROM orders").fetch_one(&mut *tx).await.unwrap();
    tx.commit().await.unwrap();
    n
}

#[sqlx::test(migrations = "./migrations")]
async fn keyset_pages_return_every_row_once_even_when_created_at_ties(admin: PgPool) {
    let app = app_pool(&admin).await;
    let tenant = Uuid::new_v4();
    let mut want = Vec::new();
    for _ in 0..5 {
        want.push(insert_order(&app, tenant, "2026-01-01T00:00:00Z").await); // all the same created_at
    }
    want.push(insert_order(&app, tenant, "2026-01-02T00:00:00.123456Z").await);
    insert_order(&app, Uuid::new_v4(), "2026-01-01T00:00:00Z").await; // another tenant's

    let (mut seen, mut cursor, mut pages) = (Vec::new(), None::<String>, 0);
    loop {
        let (page, next) = list_paginated(&app, tenant, cursor.as_deref(), 2).await.unwrap();
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
    app.close().await;
}

#[sqlx::test(migrations = "./migrations")]
async fn a_garbled_cursor_is_a_400_on_cursor(admin: PgPool) {
    let app = app_pool(&admin).await;
    for bad in ["%%%", "Zm9v", "MjAyNi0wMS0wMXxub3QtYS11dWlk"] {
        match list_paginated(&app, Uuid::new_v4(), Some(bad), 10).await {
            Err(DomainError::Validation(details)) => {
                assert_eq!((details[0].field.as_str(), details[0].code), ("cursor", "invalid_cursor"))
            }
            other => panic!("cursor {bad:?}: {:?}", other.map(|(o, c)| (o.len(), c))),
        }
    }
    app.close().await;
}

#[sqlx::test(migrations = "./migrations")]
async fn short_stock_rolls_the_whole_order_back(admin: PgPool) {
    let app = app_pool(&admin).await;
    let tenant = Uuid::new_v4();
    let mut tx = begin_tenant_tx(&app, tenant).await.unwrap();
    sqlx::query("INSERT INTO inventory (tenant_id, sku, quantity) VALUES ($1, 'A', 5), ($1, 'B', 1)")
        .bind(tenant)
        .execute(&mut *tx)
        .await
        .unwrap();
    tx.commit().await.unwrap();
    let item = |sku: &str, quantity| OrderItemRequest { sku: sku.into(), quantity };
    let stock_of_a = || async {
        let mut tx = begin_tenant_tx(&app, tenant).await.unwrap();
        let q: i32 = sqlx::query_scalar("SELECT quantity FROM inventory WHERE sku = 'A'").fetch_one(&mut *tx).await.unwrap();
        q
    };

    let short = CreateOrderRequest { total_cents: 500, items: vec![item("A", 2), item("B", 2)] };
    let err = create_order_with_inventory(&app, tenant, short).await.unwrap_err();
    assert!(matches!(err, DomainError::Conflict(_)), "{err:?}");
    assert_eq!((visible_order_count(&app, tenant).await, stock_of_a().await), (0, 5), "order and A's reservation rolled back");

    let enough = CreateOrderRequest { total_cents: 200, items: vec![item("A", 2)] };
    let order = create_order_with_inventory(&app, tenant, enough).await.unwrap();
    assert_eq!((order.status, order.total_cents, order.version), (OrderStatus::Pending, 200, 1));
    assert_eq!(stock_of_a().await, 3);

    // another tenant's identical SKU is invisible to this tenant's reservation
    let other = Uuid::new_v4();
    let err = create_order_with_inventory(&app, other, CreateOrderRequest { total_cents: 1, items: vec![item("A", 1)] }).await;
    assert!(matches!(err, Err(DomainError::Conflict(_))), "{err:?}");
    app.close().await;
}

#[sqlx::test(migrations = "./migrations")]
async fn optimistic_lock_conflict_is_409_and_a_missing_order_404(admin: PgPool) {
    let app = app_pool(&admin).await;
    let repo = OrderRepository::new(app.clone());
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
    app.close().await;
}

#[sqlx::test(migrations = "./migrations")]
async fn rls_keeps_tenants_apart_even_without_a_where_clause(admin: PgPool) {
    let app = app_pool(&admin).await;
    let repo = OrderRepository::new(app.clone());
    let (a, b) = (Uuid::new_v4(), Uuid::new_v4());
    let a_order = repo.save(&Order::new(Uuid::new_v4(), a)).await.unwrap();
    repo.save(&Order::new(Uuid::new_v4(), a)).await.unwrap();
    repo.save(&Order::new(Uuid::new_v4(), b)).await.unwrap();

    // the policy alone: SELECT count(*) FROM orders, no tenant_id filter
    assert_eq!(visible_order_count(&app, a).await, 2);
    assert_eq!(visible_order_count(&app, b).await, 1);
    // and through the doc's code
    assert!(repo.find_by_id(b, a_order.id).await.unwrap().is_none(), "B must not see A's order");
    assert_eq!(list_paginated(&app, b, None, 100).await.unwrap().0.len(), 1);

    // WITH CHECK: a transaction for B can't write a row for A
    let mut tx = begin_tenant_tx(&app, b).await.unwrap();
    let err = sqlx::query("INSERT INTO orders (id, tenant_id, total_cents) VALUES ($1, $2, 1)")
        .bind(Uuid::new_v4())
        .bind(a)
        .execute(&mut *tx)
        .await
        .expect_err("a row for another tenant violates the policy");
    assert!(err.to_string().contains("row-level security"), "{err}");
    drop(tx); // rolled back; app.close() waits for every connection to come home
    app.close().await;
}

#[sqlx::test(migrations = "./migrations")]
async fn a_query_without_the_tenant_setting_errors(admin: PgPool) {
    let app = app_pool(&admin).await;
    // a fresh session: app.current_tenant_id was never set
    let err = sqlx::query("SELECT count(*) FROM orders").execute(&app).await.expect_err("no tenant set");
    assert!(err.to_string().contains("app.current_tenant_id"), "{err}");

    // the pool's next user of a connection after the doc's begin_tenant_tx: one connection, so it is
    // the same session — the tenant must not have outlived the transaction (set_config(.., true))
    // (a row must exist: on an empty table the policy expression is never evaluated, and the
    // statement prepared inside the transaction is reused without being planned again)
    let tenant = Uuid::new_v4();
    insert_order(&app, tenant, "2026-01-01T00:00:00Z").await;
    let one = PgPoolOptions::new().max_connections(1).connect_with((*app.connect_options()).clone()).await.unwrap();
    let mut tx = begin_tenant_tx(&one, tenant).await.unwrap();
    let n: i64 = sqlx::query_scalar("SELECT count(*) FROM orders").fetch_one(&mut *tx).await.expect("inside the tenant transaction");
    assert_eq!(n, 1);
    tx.commit().await.unwrap();
    let err = sqlx::query("SELECT count(*) FROM orders").execute(&one).await.expect_err("the tenant leaked into the session");
    assert!(err.to_string().contains("uuid") || err.to_string().contains("app.current_tenant_id"), "{err}");
    one.close().await;
    app.close().await;
}
