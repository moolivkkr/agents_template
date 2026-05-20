---
skill: performance-rust
description: Rust performance archetype — connection pooling (sqlx, deadpool-redis, reqwest), memory optimization, async tuning, database performance, profiling, compilation optimization, hot path patterns
version: "1.0"
tags:
  - rust
  - performance
  - pooling
  - async
  - profiling
  - optimization
  - archetype
  - backend
---

# Performance Archetype (Rust)

> **CANONICAL REFERENCE**: This file is the single source of truth for Rust backend performance patterns. All other Rust skill packs that mention pooling, caching, async tuning, or profiling should defer to this file.

Production-grade performance patterns for Rust services. Every generated service MUST follow these patterns for connection management, memory efficiency, async execution, and database optimization.

---

## Connection Pooling

### sqlx PgPool Configuration

```rust
use sqlx::postgres::{PgPoolOptions, PgConnectOptions};
use std::time::Duration;

pub async fn create_db_pool(database_url: &str) -> Result<sqlx::PgPool, sqlx::Error> {
    let connect_options: PgConnectOptions = database_url.parse()?;

    PgPoolOptions::new()
        // Max connections: start conservative, tune based on load testing.
        // Rule of thumb: (2 * CPU cores) + number of disks on the DB server.
        // For a typical 4-core DB: max 10-20 connections per service instance.
        .max_connections(20)
        // Min connections: keep warm connections to avoid cold-start latency.
        // Set to ~25% of max for services with steady traffic.
        .min_connections(5)
        // Acquire timeout: how long to wait for a connection from the pool.
        // If this fires frequently, increase max_connections or investigate slow queries.
        .acquire_timeout(Duration::from_secs(3))
        // Idle timeout: close connections idle longer than this.
        // Prevents stale connections after traffic spikes.
        .idle_timeout(Duration::from_secs(600))
        // Max lifetime: close connections older than this regardless of activity.
        // Prevents issues with server-side connection limits and memory leaks.
        .max_lifetime(Duration::from_secs(1800))
        // Test connections before handing them out.
        .test_before_acquire(true)
        .connect_with(connect_options)
        .await
}
```

### Pool Health Monitoring

```rust
use sqlx::PgPool;

/// Expose pool stats for metrics collection.
/// Call periodically (e.g., every 30s) or on each /health check.
pub fn record_pool_metrics(pool: &PgPool, metrics: &AppMetrics) {
    let size = pool.size() as i64;
    let idle = pool.num_idle() as i64;
    let active = size - idle;

    metrics.db_pool_size.record(size, &[]);
    metrics.db_pool_active.record(active, &[]);
    metrics.db_pool_idle.record(idle, &[]);
}

/// Health check: verify the pool can acquire a connection and execute a query.
pub async fn check_db_health(pool: &PgPool) -> Result<(), String> {
    sqlx::query("SELECT 1")
        .execute(pool)
        .await
        .map(|_| ())
        .map_err(|e| format!("database health check failed: {e}"))
}
```

### deadpool-redis Pool Settings

```rust
use deadpool_redis::{Config, Pool, Runtime};

pub fn create_redis_pool(redis_url: &str) -> Pool {
    let cfg = Config::from_url(redis_url);
    cfg.builder()
        .expect("failed to create redis pool builder")
        // Max pool size: Redis is single-threaded, so more connections
        // than ~50 per instance rarely helps.
        .max_size(16)
        // Wait timeout: how long to wait for a connection.
        .wait_timeout(Some(Duration::from_secs(2)))
        // Create timeout: how long to wait for a new connection to be established.
        .create_timeout(Some(Duration::from_secs(3)))
        // Recycle timeout: how long to wait for connection recycling (health check).
        .recycle_timeout(Some(Duration::from_secs(1)))
        .runtime(Runtime::Tokio1)
        .build()
        .expect("failed to create redis pool")
}
```

### reqwest HTTP Client with Connection Pooling

```rust
use reqwest::Client;
use std::time::Duration;

/// Create a shared HTTP client. Reqwest keeps connections alive by default.
/// IMPORTANT: Create ONE client and share it (via Arc<AppState>) — do NOT create per-request.
pub fn create_http_client() -> Client {
    Client::builder()
        // Connection pool: reqwest reuses connections per host automatically.
        .pool_max_idle_per_host(10)
        .pool_idle_timeout(Duration::from_secs(90))
        // Timeouts: prevent hanging on slow upstreams.
        .connect_timeout(Duration::from_secs(5))
        .timeout(Duration::from_secs(30))
        // Enable gzip/brotli decompression.
        .gzip(true)
        .brotli(true)
        // TCP keepalive for long-lived connections.
        .tcp_keepalive(Duration::from_secs(60))
        .build()
        .expect("failed to build HTTP client")
}

// BAD: creates a new client per request (no connection reuse)
async fn bad_call_service() {
    let client = reqwest::Client::new(); // allocation + TLS handshake every time
    client.get("http://service/api").send().await.unwrap();
}

// GOOD: shared client from AppState
async fn good_call_service(client: &Client) {
    client.get("http://service/api").send().await.unwrap();
}
```

---

## Memory Performance

### Zero-Copy with &str and &[u8]

```rust
// BAD: unnecessary allocation
fn process_name(name: &str) -> String {
    let owned = name.to_string(); // allocates on heap
    if owned.starts_with("test_") {
        owned[5..].to_string() // another allocation
    } else {
        owned
    }
}

// GOOD: borrow as long as possible
fn process_name(name: &str) -> &str {
    if name.starts_with("test_") {
        &name[5..]
    } else {
        name
    }
}
```

### Cow for Conditional Ownership

```rust
use std::borrow::Cow;

/// Returns borrowed &str when no transformation needed, owned String only when modified.
fn normalize_tenant_id(input: &str) -> Cow<'_, str> {
    if input.chars().all(|c| c.is_lowercase() || c == '-') {
        // No allocation — just borrows the input
        Cow::Borrowed(input)
    } else {
        // Only allocates when we actually need to transform
        Cow::Owned(input.to_lowercase().replace(' ', "-"))
    }
}

/// Use Cow in structs that may or may not own their data.
#[derive(Debug)]
struct LogEntry<'a> {
    message: Cow<'a, str>,
    tenant_id: Cow<'a, str>,
}
```

### Avoid Unnecessary Clones

```rust
// BAD: cloning when a reference suffices
fn find_order(orders: &[Order], id: &str) -> Option<Order> {
    orders.iter().find(|o| o.id == id).cloned() // unnecessary clone
}

// GOOD: return a reference
fn find_order<'a>(orders: &'a [Order], id: &str) -> Option<&'a Order> {
    orders.iter().find(|o| o.id == id)
}

// GOOD: use Arc for shared ownership across tasks
use std::sync::Arc;

struct AppState {
    config: Arc<AppConfig>,  // shared across request handlers, zero-cost clone
    db_pool: PgPool,
}

// Arc clone is just an atomic increment — not a deep copy
let state = Arc::new(app_state);
```

### SmallVec for Small Collections

```rust
use smallvec::SmallVec;

/// When you know most collections will be small (e.g., <=8 items),
/// SmallVec stores them on the stack and only heap-allocates when exceeded.
fn validate_fields(input: &CreateRequest) -> Result<(), ValidationErrors> {
    // Most validation runs produce 0-3 errors. Stack allocation avoids heap.
    let mut errors: SmallVec<[FieldError; 4]> = SmallVec::new();

    if input.name.is_empty() {
        errors.push(FieldError::new("name", "required"));
    }
    if input.email.is_empty() {
        errors.push(FieldError::new("email", "required"));
    }

    if errors.is_empty() {
        Ok(())
    } else {
        Err(ValidationErrors(errors.into_vec()))
    }
}
```

### Pre-Allocated Buffers

```rust
// BAD: Vec grows and reallocates multiple times
fn collect_ids(items: &[Item]) -> Vec<String> {
    let mut ids = Vec::new(); // starts at capacity 0
    for item in items {
        ids.push(item.id.clone()); // may reallocate at 1, 2, 4, 8, 16...
    }
    ids
}

// GOOD: pre-allocate to known size
fn collect_ids(items: &[Item]) -> Vec<String> {
    let mut ids = Vec::with_capacity(items.len()); // one allocation
    for item in items {
        ids.push(item.id.clone());
    }
    ids
}

// BEST: use iterator collect (which calls size_hint for pre-allocation)
fn collect_ids(items: &[Item]) -> Vec<String> {
    items.iter().map(|item| item.id.clone()).collect()
}

// Pre-allocate strings when building output
fn build_csv(rows: &[Row]) -> String {
    let estimated_size = rows.len() * 100; // ~100 bytes per row
    let mut output = String::with_capacity(estimated_size);
    for row in rows {
        use std::fmt::Write;
        writeln!(output, "{},{},{}", row.id, row.name, row.value).unwrap();
    }
    output
}
```

### Stack vs Heap

```rust
// Stack: fixed-size, no allocation overhead
struct Point { x: f64, y: f64 }  // 16 bytes on stack

// Heap: dynamic size, allocation cost
let points: Vec<Point> = Vec::new();  // Vec header on stack, data on heap

// Prefer arrays over Vec for known small fixed sizes
fn transform_rgb(pixel: [u8; 3]) -> [u8; 3] {
    [pixel[0] / 2, pixel[1] / 2, pixel[2] / 2]  // entirely on stack
}

// Use Box only when you need heap allocation (large structs, trait objects, recursive types)
struct LargeConfig { /* 10KB of fields */ }

// Pass by reference, not by value (avoids copying 10KB on the stack)
fn apply_config(config: &LargeConfig) { /* ... */ }
```

---

## Async Performance

### Tokio Runtime Configuration

```rust
fn main() {
    tokio::runtime::Builder::new_multi_thread()
        // Worker threads: defaults to number of CPU cores.
        // Only override if you have a specific reason.
        .worker_threads(num_cpus::get())
        // Max blocking threads: for spawn_blocking tasks (file I/O, CPU-heavy work).
        // Default is 512. Reduce if memory is constrained.
        .max_blocking_threads(64)
        // Thread names for debugging
        .thread_name("order-svc-worker")
        // Enable all features (time, I/O, signal)
        .enable_all()
        .build()
        .expect("failed to build tokio runtime")
        .block_on(async_main());
}
```

### Avoid Blocking in Async Context

```rust
// BAD: blocks the tokio worker thread — starves other tasks
async fn hash_password(password: &str) -> String {
    bcrypt::hash(password, 12).unwrap() // CPU-intensive, blocks worker
}

// GOOD: offload to blocking thread pool
async fn hash_password(password: String) -> Result<String, AppError> {
    tokio::task::spawn_blocking(move || {
        bcrypt::hash(&password, 12).map_err(|e| AppError::Internal(e.into()))
    })
    .await
    .map_err(|e| AppError::Internal(e.into()))?
}

// BAD: synchronous file I/O in async context
async fn read_config() -> String {
    std::fs::read_to_string("config.toml").unwrap() // blocks worker
}

// GOOD: use tokio's async file I/O
async fn read_config() -> Result<String, std::io::Error> {
    tokio::fs::read_to_string("config.toml").await
}
```

### Buffer Unordered for Concurrent Stream Processing

```rust
use futures::stream::{self, StreamExt};

/// Process multiple items concurrently with bounded parallelism.
async fn enrich_orders(
    orders: Vec<Order>,
    enrichment_service: &EnrichmentService,
) -> Vec<EnrichedOrder> {
    stream::iter(orders)
        .map(|order| async move {
            enrichment_service.enrich(order).await
        })
        // Process up to 10 concurrently, return results as they complete.
        .buffer_unordered(10)
        .collect()
        .await
}

/// Fan out to multiple services, collect all results.
async fn fetch_dashboard_data(
    tenant_id: &str,
    services: &AppServices,
) -> DashboardData {
    let (orders, users, metrics) = tokio::join!(
        services.orders.list_recent(tenant_id),
        services.users.count_active(tenant_id),
        services.metrics.get_summary(tenant_id),
    );

    DashboardData {
        recent_orders: orders.unwrap_or_default(),
        active_users: users.unwrap_or(0),
        summary: metrics.unwrap_or_default(),
    }
}
```

### Semaphore for Limiting Concurrent Operations

```rust
use tokio::sync::Semaphore;
use std::sync::Arc;

struct RateLimitedClient {
    client: reqwest::Client,
    semaphore: Arc<Semaphore>,
}

impl RateLimitedClient {
    pub fn new(max_concurrent: usize) -> Self {
        Self {
            client: create_http_client(),
            semaphore: Arc::new(Semaphore::new(max_concurrent)),
        }
    }

    pub async fn get(&self, url: &str) -> Result<reqwest::Response, AppError> {
        // Acquire a permit — blocks if max_concurrent requests are in flight
        let _permit = self.semaphore.acquire().await
            .map_err(|_| AppError::Internal(anyhow::anyhow!("semaphore closed")))?;

        self.client.get(url).send().await.map_err(|e| {
            AppError::upstream("external-service", e)
        })
        // permit is dropped here, releasing the slot
    }
}
```

### Channel Sizing

```rust
use tokio::sync::mpsc;

// Bounded channel: prevents memory blowup if consumer is slower than producer.
// Size based on expected burst: too small = backpressure, too large = memory waste.
let (tx, mut rx) = mpsc::channel::<Event>(1000);

// Producer
tokio::spawn(async move {
    for event in events {
        // Blocks (awaits) if channel is full — natural backpressure
        if tx.send(event).await.is_err() {
            tracing::warn!("event receiver dropped");
            break;
        }
    }
});

// Consumer
tokio::spawn(async move {
    while let Some(event) = rx.recv().await {
        process_event(event).await;
    }
});

// For fire-and-forget with overflow dropping (metrics, non-critical events):
let (tx, rx) = mpsc::channel::<MetricEvent>(100);
// Use try_send to avoid blocking the hot path
if tx.try_send(metric_event).is_err() {
    // Channel full — drop the metric rather than blocking
    tracing::debug!("metric channel full, dropping event");
}
```

### Select for Racing Multiple Futures

```rust
use tokio::time::{timeout, Duration};

/// Fetch from cache, fall back to database with timeout.
async fn get_with_fallback(
    cache: &RedisCache,
    db: &PgPool,
    key: &str,
) -> Result<Data, AppError> {
    tokio::select! {
        // Race cache lookup against a tight timeout
        result = cache.get(key) => {
            match result {
                Ok(Some(data)) => return Ok(data),
                Ok(None) => { /* cache miss, fall through to DB */ }
                Err(e) => {
                    tracing::warn!(error = %e, "cache read failed, falling back to DB");
                }
            }
        }
        _ = tokio::time::sleep(Duration::from_millis(50)) => {
            tracing::warn!("cache lookup timed out, falling back to DB");
        }
    }

    // Fall back to database
    fetch_from_db(db, key).await
}
```

---

## Database Performance

### Prepared Statements (sqlx Caches Automatically)

sqlx caches prepared statements per connection automatically. Use `sqlx::query!` and `sqlx::query_as!` for compile-time checked queries that are prepared once and reused.

```rust
// sqlx::query! — prepared statement, cached per connection, compile-time SQL validation
let orders = sqlx::query_as!(
    Order,
    r#"
    SELECT id, tenant_id, user_id, total, status as "status: OrderStatus", created_at
    FROM orders
    WHERE tenant_id = $1 AND status = $2
    ORDER BY created_at DESC
    LIMIT $3
    "#,
    tenant_id,
    status.as_str(),
    limit as i64,
)
.fetch_all(&self.pool)
.await?;
```

### Batch Inserts

```rust
/// Insert multiple rows in a single query — dramatically faster than individual INSERTs.
pub async fn batch_insert_items(
    pool: &PgPool,
    items: &[OrderItem],
) -> Result<(), sqlx::Error> {
    // Build a multi-row INSERT dynamically.
    // For very large batches (>1000), chunk into groups.
    const CHUNK_SIZE: usize = 500;

    for chunk in items.chunks(CHUNK_SIZE) {
        let mut query_builder = sqlx::QueryBuilder::new(
            "INSERT INTO order_items (id, order_id, tenant_id, product_id, quantity, price) "
        );

        query_builder.push_values(chunk, |mut b, item| {
            b.push_bind(&item.id)
                .push_bind(&item.order_id)
                .push_bind(&item.tenant_id)
                .push_bind(&item.product_id)
                .push_bind(item.quantity)
                .push_bind(item.price);
        });

        query_builder.build().execute(pool).await?;
    }

    Ok(())
}

/// For massive datasets: use COPY for maximum throughput.
/// Requires raw connection (not through pool query interface).
pub async fn copy_insert_events(
    pool: &PgPool,
    events: &[Event],
) -> Result<u64, sqlx::Error> {
    let mut conn = pool.acquire().await?;

    let mut copy = conn
        .copy_in_raw("COPY events (id, tenant_id, event_type, payload, created_at) FROM STDIN WITH (FORMAT csv)")
        .await?;

    let mut buf = Vec::with_capacity(events.len() * 200);
    for event in events {
        use std::fmt::Write;
        writeln!(
            buf,
            "{},{},{},{},{}",
            event.id, event.tenant_id, event.event_type,
            event.payload.replace(',', "\\,"),
            event.created_at.to_rfc3339()
        ).unwrap();
    }

    copy.send(buf).await?;
    let rows = copy.finish().await?;
    Ok(rows)
}
```

### Read Replicas

```rust
/// Separate pools for reads and writes.
pub struct DatabasePools {
    pub write: PgPool,  // primary — all writes go here
    pub read: PgPool,   // replica — read queries go here
}

impl DatabasePools {
    pub async fn new(
        write_url: &str,
        read_url: &str,
    ) -> Result<Self, sqlx::Error> {
        let write = PgPoolOptions::new()
            .max_connections(10)
            .connect(write_url)
            .await?;

        let read = PgPoolOptions::new()
            .max_connections(30) // more read capacity
            .connect(read_url)
            .await?;

        Ok(Self { write, read })
    }
}

// Repository usage
impl OrderRepo {
    #[tracing::instrument(skip(self))]
    pub async fn find_by_id(&self, tenant_id: &str, id: &str) -> Result<Order, AppError> {
        // READ from replica
        sqlx::query_as!(Order, "SELECT ... FROM orders WHERE tenant_id = $1 AND id = $2", tenant_id, id)
            .fetch_optional(&self.pools.read)
            .await?
            .ok_or(AppError::not_found("order", id))
    }

    #[tracing::instrument(skip(self, order))]
    pub async fn insert(&self, order: &Order) -> Result<(), AppError> {
        // WRITE to primary
        sqlx::query!("INSERT INTO orders (...) VALUES (...)", /* ... */)
            .execute(&self.pools.write)
            .await?;
        Ok(())
    }
}
```

### Query Result Caching with Redis

```rust
use deadpool_redis::Pool as RedisPool;
use redis::AsyncCommands;
use serde::{de::DeserializeOwned, Serialize};

pub struct CacheLayer {
    redis: RedisPool,
    default_ttl: Duration,
}

impl CacheLayer {
    /// Get from cache or compute + cache the result.
    pub async fn get_or_set<T, F, Fut>(
        &self,
        key: &str,
        ttl: Option<Duration>,
        compute: F,
    ) -> Result<T, AppError>
    where
        T: Serialize + DeserializeOwned,
        F: FnOnce() -> Fut,
        Fut: std::future::Future<Output = Result<T, AppError>>,
    {
        // Try cache first
        if let Some(cached) = self.get::<T>(key).await? {
            return Ok(cached);
        }

        // Compute the value
        let value = compute().await?;

        // Cache it (fire-and-forget — don't fail the request if cache write fails)
        let ttl = ttl.unwrap_or(self.default_ttl);
        if let Err(e) = self.set(key, &value, ttl).await {
            tracing::warn!(key = %key, error = %e, "failed to write cache");
        }

        Ok(value)
    }

    async fn get<T: DeserializeOwned>(&self, key: &str) -> Result<Option<T>, AppError> {
        let mut conn = self.redis.get().await
            .map_err(|e| AppError::Internal(e.into()))?;

        let data: Option<String> = conn.get(key).await
            .map_err(|e| AppError::Internal(e.into()))?;

        match data {
            Some(json) => {
                let value = serde_json::from_str(&json)
                    .map_err(|e| AppError::Internal(e.into()))?;
                Ok(Some(value))
            }
            None => Ok(None),
        }
    }

    async fn set<T: Serialize>(&self, key: &str, value: &T, ttl: Duration) -> Result<(), AppError> {
        let json = serde_json::to_string(value)
            .map_err(|e| AppError::Internal(e.into()))?;

        let mut conn = self.redis.get().await
            .map_err(|e| AppError::Internal(e.into()))?;

        conn.set_ex(key, json, ttl.as_secs()).await
            .map_err(|e| AppError::Internal(e.into()))?;

        Ok(())
    }

    /// Invalidate cache on write operations.
    pub async fn invalidate(&self, key: &str) -> Result<(), AppError> {
        let mut conn = self.redis.get().await
            .map_err(|e| AppError::Internal(e.into()))?;
        conn.del(key).await
            .map_err(|e| AppError::Internal(e.into()))?;
        Ok(())
    }
}

// Usage in service
impl OrderService {
    pub async fn get_order(&self, tenant_id: &str, id: &str) -> Result<Order, AppError> {
        let cache_key = format!("order:{}:{}", tenant_id, id);

        self.cache.get_or_set(&cache_key, None, || async {
            self.repo.find_by_id(tenant_id, id).await
        }).await
    }

    pub async fn update_order(&self, tenant_id: &str, id: &str, req: UpdateOrderRequest) -> Result<Order, AppError> {
        let order = self.repo.update(tenant_id, id, req).await?;

        // Invalidate cache after write
        let cache_key = format!("order:{}:{}", tenant_id, id);
        self.cache.invalidate(&cache_key).await?;

        Ok(order)
    }
}
```

### N+1 Prevention

```rust
// BAD: N+1 — one query per order to get items
async fn list_orders_with_items(pool: &PgPool, tenant_id: &str) -> Result<Vec<OrderWithItems>, AppError> {
    let orders = sqlx::query_as!(Order, "SELECT * FROM orders WHERE tenant_id = $1", tenant_id)
        .fetch_all(pool).await?;

    let mut result = Vec::with_capacity(orders.len());
    for order in orders {
        // This executes N additional queries!
        let items = sqlx::query_as!(OrderItem, "SELECT * FROM order_items WHERE order_id = $1", order.id)
            .fetch_all(pool).await?;
        result.push(OrderWithItems { order, items });
    }
    Ok(result)
}

// GOOD: JOIN query — single round trip
async fn list_orders_with_items(pool: &PgPool, tenant_id: &str) -> Result<Vec<OrderWithItems>, AppError> {
    let rows = sqlx::query_as!(
        OrderItemRow,
        r#"
        SELECT o.id, o.tenant_id, o.total, o.status,
               oi.id as item_id, oi.product_id, oi.quantity, oi.price
        FROM orders o
        LEFT JOIN order_items oi ON o.id = oi.order_id
        WHERE o.tenant_id = $1
        ORDER BY o.created_at DESC
        "#,
        tenant_id,
    )
    .fetch_all(pool)
    .await?;

    Ok(group_rows_into_orders(rows))
}

// GOOD: Batch loading — fetch all items for all orders in one query
async fn list_orders_with_items(pool: &PgPool, tenant_id: &str) -> Result<Vec<OrderWithItems>, AppError> {
    let orders = sqlx::query_as!(Order, "SELECT * FROM orders WHERE tenant_id = $1", tenant_id)
        .fetch_all(pool).await?;

    let order_ids: Vec<&str> = orders.iter().map(|o| o.id.as_str()).collect();

    // Single query for ALL items across ALL orders
    let items = sqlx::query_as!(
        OrderItem,
        "SELECT * FROM order_items WHERE order_id = ANY($1)",
        &order_ids as &[&str],
    )
    .fetch_all(pool)
    .await?;

    // Group items by order_id in memory
    let items_by_order: HashMap<String, Vec<OrderItem>> =
        items.into_iter().fold(HashMap::new(), |mut map, item| {
            map.entry(item.order_id.clone()).or_default().push(item);
            map
        });

    Ok(orders.into_iter().map(|order| {
        let items = items_by_order.get(&order.id).cloned().unwrap_or_default();
        OrderWithItems { order, items }
    }).collect())
}
```

---

## Profiling

### Criterion Benchmarks

```toml
# Cargo.toml
[dev-dependencies]
criterion = { version = "0.5", features = ["html_reports"] }

[[bench]]
name = "order_benchmarks"
harness = false
```

```rust
// benches/order_benchmarks.rs
use criterion::{black_box, criterion_group, criterion_main, Criterion, BenchmarkId};

fn bench_normalize_tenant_id(c: &mut Criterion) {
    let inputs = vec![
        ("already-lowercase", "already-lowercase"),
        ("NEEDS TRANSFORM", "NEEDS TRANSFORM"),
        ("MiXeD-CaSe", "MiXeD-CaSe"),
    ];

    let mut group = c.benchmark_group("normalize_tenant_id");
    for (name, input) in inputs {
        group.bench_with_input(BenchmarkId::new("normalize", name), &input, |b, input| {
            b.iter(|| normalize_tenant_id(black_box(input)))
        });
    }
    group.finish();
}

fn bench_batch_serialize(c: &mut Criterion) {
    let mut group = c.benchmark_group("batch_serialize");

    for size in [10, 100, 1000, 10000] {
        let orders: Vec<Order> = (0..size).map(|i| Order::mock(i)).collect();

        group.bench_with_input(BenchmarkId::new("serde_json", size), &orders, |b, orders| {
            b.iter(|| serde_json::to_string(black_box(orders)).unwrap())
        });
    }
    group.finish();
}

criterion_group!(benches, bench_normalize_tenant_id, bench_batch_serialize);
criterion_main!(benches);
```

Run benchmarks:

```bash
# Run all benchmarks
cargo bench

# Run a specific benchmark group
cargo bench -- normalize_tenant_id

# Compare against baseline
cargo bench -- --save-baseline main
# ... make changes ...
cargo bench -- --baseline main
```

### Flamegraph

```bash
# Install
cargo install flamegraph

# Generate flamegraph (requires perf on Linux, dtrace on macOS)
cargo flamegraph --bin order-service

# With specific workload
cargo flamegraph --bin order-service -- --load-test

# For release profile (more accurate, optimized code paths)
cargo flamegraph --release --bin order-service
```

### DHAT for Heap Profiling

```toml
[dev-dependencies]
dhat = "0.3"

[profile.release]
debug = true  # needed for DHAT symbolication
```

```rust
// Enable DHAT in test or bench mode
#[cfg(feature = "dhat-heap")]
#[global_allocator]
static ALLOC: dhat::Alloc = dhat::Alloc;

#[tokio::main]
async fn main() {
    #[cfg(feature = "dhat-heap")]
    let _profiler = dhat::Profiler::new_heap();

    // ... run application ...
    // DHAT report is written to dhat-heap.json on drop
}
```

```bash
# Run with DHAT
cargo run --features dhat-heap

# View the report
# Open dhat-heap.json in https://nnethercote.github.io/dh_view/dh_view.html
```

### tokio-console for Async Task Monitoring

```toml
[dependencies]
console-subscriber = "0.4"
```

```rust
// In main.rs — replace or combine with tracing-subscriber
fn init_telemetry_with_console() {
    // tokio-console layer for async task inspection
    let console_layer = console_subscriber::spawn();

    tracing_subscriber::registry()
        .with(console_layer)
        .with(tracing_subscriber::fmt::layer())
        .init();
}
```

```bash
# Run with tokio-console support
RUSTFLAGS="--cfg tokio_unstable" cargo run

# In another terminal, connect with tokio-console
tokio-console
```

### tracing-timing for Per-Span Latency

```toml
[dependencies]
tracing-timing = "0.6"
```

```rust
use tracing_timing::{Builder, Histogram};

fn init_timing_layer() {
    let timing_layer = Builder::default()
        .no_span_recursion()
        .layer(|| Histogram::new_with_max(10_000_000, 2).unwrap());

    tracing_subscriber::registry()
        .with(timing_layer)
        .with(tracing_subscriber::fmt::layer())
        .init();
}
```

---

## Compilation Performance

### Release Profile Optimization

```toml
# Cargo.toml

[profile.release]
# Maximum optimization
opt-level = 3
# Link-time optimization: slower compile, faster binary
lto = true
# Single codegen unit: slower compile, better optimization across modules
codegen-units = 1
# Strip debug info from binary (reduces size ~50%)
strip = true
# Abort on panic (smaller binary, no unwinding overhead)
panic = "abort"

[profile.dev]
# Faster dev builds
opt-level = 0
# Incremental compilation (default, but be explicit)
incremental = true

[profile.dev.package."*"]
# Optimize dependencies even in dev mode (faster runtime, same compile time after first build)
opt-level = 2
```

### Build Time Optimization

```bash
# Install sccache for shared compilation cache
cargo install sccache
export RUSTC_WRAPPER=sccache

# Check cache stats
sccache --show-stats
```

### cargo-chef for Docker Builds

```dockerfile
# Stage 1: Plan — extract dependency information
FROM rust:1.82 AS chef
RUN cargo install cargo-chef
WORKDIR /app

FROM chef AS planner
COPY . .
RUN cargo chef prepare --recipe-path recipe.json

# Stage 2: Cook — build only dependencies (cached layer)
FROM chef AS builder
COPY --from=planner /app/recipe.json recipe.json
RUN cargo chef cook --release --recipe-path recipe.json

# Stage 3: Build — only your source code (fast rebuild)
COPY . .
RUN cargo build --release --bin order-service

# Stage 4: Runtime — minimal image
FROM debian:bookworm-slim AS runtime
RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/target/release/order-service /usr/local/bin/
ENTRYPOINT ["/usr/local/bin/order-service"]
```

### Binary Size Reduction

```bash
# Check binary size
ls -lh target/release/order-service

# Strip debug symbols (already in Cargo.toml profile, but also manually)
strip target/release/order-service

# UPX compression (optional — trades startup time for smaller binary)
upx --best target/release/order-service
```

---

## Hot Path Optimization

### Avoid Dynamic Dispatch in Hot Paths

```rust
// BAD in hot path: dynamic dispatch via trait object (vtable indirection)
fn process_events(handlers: &[Box<dyn EventHandler>], events: &[Event]) {
    for event in events {
        for handler in handlers {
            handler.handle(event); // vtable lookup on every call
        }
    }
}

// GOOD in hot path: static dispatch via generics (monomorphized, inlined)
fn process_events<H: EventHandler>(handler: &H, events: &[Event]) {
    for event in events {
        handler.handle(event); // direct call, can be inlined
    }
}

// GOOD: enum dispatch for known variants (no heap allocation, no vtable)
enum EventHandler {
    OrderCreated(OrderCreatedHandler),
    PaymentReceived(PaymentReceivedHandler),
    ShipmentDispatched(ShipmentDispatchedHandler),
}

impl EventHandler {
    fn handle(&self, event: &Event) {
        match self {
            Self::OrderCreated(h) => h.handle(event),
            Self::PaymentReceived(h) => h.handle(event),
            Self::ShipmentDispatched(h) => h.handle(event),
        }
    }
}
```

### Use #[inline] Judiciously

```rust
// GOOD: small function that crosses crate boundaries
#[inline]
pub fn tenant_cache_key(tenant_id: &str, resource: &str, id: &str) -> String {
    format!("{}:{}:{}", tenant_id, resource, id)
}

// GOOD: trivial accessor
#[inline]
pub fn is_active(&self) -> bool {
    self.status == Status::Active
}

// BAD: large function body — let the compiler decide
#[inline] // don't do this — compiler is smarter than you here
pub fn process_order(&self, order: &Order) -> Result<(), AppError> {
    // ... 50 lines of logic ...
}
```

### Perfect Hashing for Static Lookup Tables

```rust
use phf::phf_map;

/// Compile-time perfect hash map — zero runtime overhead for lookups.
static HTTP_STATUS_NAMES: phf::Map<u16, &'static str> = phf_map! {
    200u16 => "OK",
    201u16 => "Created",
    204u16 => "No Content",
    400u16 => "Bad Request",
    401u16 => "Unauthorized",
    403u16 => "Forbidden",
    404u16 => "Not Found",
    409u16 => "Conflict",
    422u16 => "Unprocessable Entity",
    500u16 => "Internal Server Error",
    502u16 => "Bad Gateway",
    503u16 => "Service Unavailable",
};

fn status_name(code: u16) -> &'static str {
    HTTP_STATUS_NAMES.get(&code).unwrap_or(&"Unknown")
}
```

### Avoid format!() in Hot Paths

```rust
// BAD: format! allocates a String every call
fn log_request_count(count: u64) {
    let msg = format!("processed {} requests", count); // heap allocation
    write_metric(&msg);
}

// GOOD: use itoa/ryu for number-to-string without allocation overhead
use itoa::Buffer;

fn log_request_count(count: u64) {
    let mut buf = itoa::Buffer::new();
    let count_str = buf.format(count); // writes to stack buffer
    write_metric_parts("processed ", count_str, " requests");
}

// GOOD: use write! to a pre-allocated buffer
fn format_metrics(metrics: &[Metric], buf: &mut String) {
    buf.clear();
    for m in metrics {
        use std::fmt::Write;
        // Writes into existing String capacity — no new allocation if capacity suffices
        writeln!(buf, "{}={}", m.name, m.value).unwrap();
    }
}
```

### SIMD-Friendly Data Layouts

```rust
// Structure of Arrays (SoA) — better for SIMD and cache locality when
// you process one field at a time across many items.

// BAD for batch numeric processing: Array of Structs
struct OrderAoS {
    id: Uuid,
    total: f64,
    quantity: u32,
    // ... other fields
}
let orders: Vec<OrderAoS> = /* ... */; // totals are scattered in memory

// GOOD for batch numeric processing: Structure of Arrays
struct OrderBatch {
    ids: Vec<Uuid>,
    totals: Vec<f64>,    // contiguous in memory — cache-friendly, SIMD-friendly
    quantities: Vec<u32>, // contiguous in memory
}

fn sum_totals(batch: &OrderBatch) -> f64 {
    // Compiler can auto-vectorize this loop (contiguous f64 slice)
    batch.totals.iter().sum()
}
```

---

## Critical Rules

- Create ONE connection pool / HTTP client and share via `Arc<AppState>` -- never per-request
- Pre-allocate containers when size is known (`Vec::with_capacity`, `String::with_capacity`)
- Never block async worker threads -- use `spawn_blocking` for CPU-intensive or sync I/O work
- Use bounded channels and semaphores to prevent unbounded memory growth
- Batch database operations -- multi-row INSERT or COPY instead of individual inserts
- Separate read and write database pools when using replicas
- Profile before optimizing -- use criterion, flamegraph, DHAT, and tokio-console
- Use `cargo-chef` in Docker for layer-cached dependency builds
- Avoid `clone()` when `&` suffices -- use references, `Cow`, and `Arc` for shared ownership
- Hot paths: prefer static dispatch (generics) over dynamic dispatch (trait objects)
- Cache invalidation on writes -- never serve stale data after mutations
- Path normalization in metrics -- replace UUIDs and numeric IDs to prevent label explosion
