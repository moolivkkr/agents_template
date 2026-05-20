---
skill: performance-java
description: Java/Spring Boot performance archetype — HikariCP tuning, JVM container settings, GC selection, JPA batch optimization, virtual threads, Caffeine caching, profiling with JFR, connection pooling, concurrency patterns
version: "1.0"
tags:
  - java
  - spring-boot
  - performance
  - hikaricp
  - jvm
  - caching
  - profiling
  - concurrency
  - archetype
  - backend
---

# Performance Archetype (Spring Boot)

> **CANONICAL REFERENCE**: This file is the single source of truth for Java/Spring Boot performance patterns. All other Java skill packs that mention connection pooling, caching, JVM tuning, or profiling should defer to this file.

Complete performance optimization patterns for Spring Boot services. Apply these patterns from day one — retrofitting performance is expensive.

---

## 1. Connection Pooling

### 1a. HikariCP Configuration

HikariCP is Spring Boot's default connection pool. Misconfiguration is the #1 cause of production database issues.

```yaml
# application.yml
spring:
  datasource:
    url: jdbc:postgresql://${DB_HOST:localhost}:${DB_PORT:5432}/${DB_NAME:orders}
    username: ${DB_USER:app}
    password: ${DB_PASSWORD:secret}
    hikari:
      # Pool sizing — start here, tune based on load testing
      maximum-pool-size: ${HIKARI_MAX_POOL:10}
      minimum-idle: ${HIKARI_MIN_IDLE:5}

      # Timeouts
      connection-timeout: 5000        # 5s — fail fast if pool exhausted
      idle-timeout: 300000             # 5min — release idle connections
      max-lifetime: 1800000            # 30min — recycle before DB kills them
      validation-timeout: 3000         # 3s — how long to wait for validation query
      leak-detection-threshold: 30000  # 30s — log warning if connection not returned

      # Connection validation
      connection-test-query: SELECT 1

      # Pool name for metrics
      pool-name: order-service-pool

      # Auto-commit (disable for JPA — Spring manages transactions)
      auto-commit: false
```

**Pool sizing formula:**

```
connections = ((core_count * 2) + effective_spindle_count)

For SSD with 4 cores:  (4 * 2) + 1 = 9 ≈ 10
For cloud DB (Aurora):  Start with 10, scale based on load tests
```

**Rules:**
- Start with `maximum-pool-size: 10` — almost always enough
- Set `minimum-idle` equal to `maximum-pool-size` for steady workloads
- Set `connection-timeout: 5000` — fail fast, never block threads for 30s
- Set `max-lifetime` shorter than the database's `wait_timeout`
- Enable `leak-detection-threshold` in all environments
- Monitor `db.pool.active_connections` gauge (see `observability-java.md`)

### 1b. Spring Data JPA Pool Tuning

```yaml
# application.yml — JPA-specific tuning
spring:
  jpa:
    open-in-view: false              # CRITICAL: disable OSIV — holds connections too long
    properties:
      hibernate:
        connection:
          provider_disables_autocommit: true  # Skip unnecessary autocommit toggle
        jdbc:
          batch_size: 50             # Batch inserts/updates (see §4a)
          fetch_size: 100            # JDBC fetch size for large result sets
        order_inserts: true          # Group inserts by entity type for batching
        order_updates: true          # Group updates by entity type for batching
```

**CRITICAL**: Always set `spring.jpa.open-in-view: false`. OSIV holds a database connection for the entire HTTP request lifecycle, including view rendering. This wastes pool connections and causes pool exhaustion under load.

### 1c. Redis Connection Pool (Lettuce)

```yaml
# application.yml
spring:
  data:
    redis:
      host: ${REDIS_HOST:localhost}
      port: ${REDIS_PORT:6379}
      lettuce:
        pool:
          max-active: 16           # Maximum connections
          max-idle: 8              # Maximum idle connections
          min-idle: 4              # Minimum idle connections
          max-wait: 2000ms         # Maximum wait for connection from pool
        shutdown-timeout: 200ms
      timeout: 2000ms              # Command timeout
```

### 1d. HTTP Client Connection Pool (RestClient / WebClient)

```java
package com.example.app.config;

import org.apache.hc.client5.http.impl.classic.CloseableHttpClient;
import org.apache.hc.client5.http.impl.classic.HttpClients;
import org.apache.hc.client5.http.impl.io.PoolingHttpClientConnectionManager;
import org.apache.hc.core5.util.TimeValue;
import org.apache.hc.core5.util.Timeout;
import org.springframework.boot.web.client.RestTemplateBuilder;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.HttpComponentsClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

import java.time.Duration;

@Configuration
public class HttpClientConfig {

    @Bean
    public RestClient restClient() {
        PoolingHttpClientConnectionManager connectionManager =
                new PoolingHttpClientConnectionManager();
        connectionManager.setMaxTotal(100);                    // Max total connections
        connectionManager.setDefaultMaxPerRoute(20);           // Max per host
        connectionManager.setValidateAfterInactivity(TimeValue.ofSeconds(5));

        CloseableHttpClient httpClient = HttpClients.custom()
                .setConnectionManager(connectionManager)
                .evictExpiredConnections()
                .evictIdleConnections(TimeValue.ofMinutes(5))
                .setDefaultRequestConfig(
                        org.apache.hc.client5.http.config.RequestConfig.custom()
                                .setConnectionRequestTimeout(Timeout.ofSeconds(2))
                                .setResponseTimeout(Timeout.ofSeconds(10))
                                .build())
                .build();

        return RestClient.builder()
                .requestFactory(new HttpComponentsClientHttpRequestFactory(httpClient))
                .build();
    }
}
```

For WebClient (reactive):

```java
import io.netty.channel.ChannelOption;
import io.netty.handler.timeout.ReadTimeoutHandler;
import io.netty.handler.timeout.WriteTimeoutHandler;
import org.springframework.http.client.reactive.ReactorClientHttpConnector;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.netty.http.client.HttpClient;
import reactor.netty.resources.ConnectionProvider;

@Bean
public WebClient webClient() {
    ConnectionProvider provider = ConnectionProvider.builder("custom")
            .maxConnections(100)
            .maxIdleTime(Duration.ofMinutes(5))
            .maxLifeTime(Duration.ofMinutes(30))
            .pendingAcquireMaxCount(50)
            .pendingAcquireTimeout(Duration.ofSeconds(2))
            .build();

    HttpClient httpClient = HttpClient.create(provider)
            .option(ChannelOption.CONNECT_TIMEOUT_MILLIS, 5000)
            .doOnConnected(conn -> conn
                    .addHandlerLast(new ReadTimeoutHandler(10))
                    .addHandlerLast(new WriteTimeoutHandler(5)));

    return WebClient.builder()
            .clientConnector(new ReactorClientHttpConnector(httpClient))
            .build();
}
```

---

## 2. JVM Tuning

### 2a. Container-Aware JVM Settings

```dockerfile
# Dockerfile — production JVM flags
FROM eclipse-temurin:21-jre-alpine

COPY build/libs/app.jar /app/app.jar

ENV JAVA_OPTS="\
  -XX:MaxRAMPercentage=75.0 \
  -XX:InitialRAMPercentage=50.0 \
  -XX:+UseG1GC \
  -XX:MaxGCPauseMillis=200 \
  -XX:+UseStringDeduplication \
  -XX:+OptimizeStringConcat \
  -Djava.security.egd=file:/dev/./urandom \
  -Dfile.encoding=UTF-8"

ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar /app/app.jar"]
```

**Memory allocation strategy:**

| Container Memory | `-XX:MaxRAMPercentage` | Effective Heap | Reason |
|-----------------|----------------------|----------------|--------|
| 256 MB | 75% | ~192 MB | Small service, leave room for metaspace + native |
| 512 MB | 75% | ~384 MB | Typical microservice |
| 1 GB | 75% | ~768 MB | Standard workload |
| 2+ GB | 75% | ~1.5 GB+ | Heavy processing |

**Rules:**
- Always use `-XX:MaxRAMPercentage` instead of `-Xmx` in containers — it adapts to container memory limits
- Never use `-XX:MaxRAMPercentage=100` — the JVM needs ~25% for metaspace, thread stacks, native memory, and code cache
- Set `InitialRAMPercentage` to 50-75% to avoid gradual heap growth
- Use `-Djava.security.egd=file:/dev/./urandom` to avoid entropy starvation in containers

### 2b. GC Selection

| GC | Best For | Flag | Trade-off |
|----|----------|------|-----------|
| **G1GC** | General purpose (default in JDK 17+) | `-XX:+UseG1GC` | Balanced throughput and latency |
| **ZGC** | Low-latency (sub-ms pauses) | `-XX:+UseZGC` | Slightly lower throughput, higher memory |
| **Shenandoah** | Low-latency (alternative to ZGC) | `-XX:+UseShenandoahGC` | Similar to ZGC, available in OpenJDK |
| **Parallel GC** | Batch/throughput workloads | `-XX:+UseParallelGC` | Higher pause times, maximum throughput |

```dockerfile
# Low-latency service (API gateway, real-time pricing)
ENV JAVA_OPTS="\
  -XX:MaxRAMPercentage=75.0 \
  -XX:+UseZGC \
  -XX:+ZGenerational"

# Batch processing service
ENV JAVA_OPTS="\
  -XX:MaxRAMPercentage=75.0 \
  -XX:+UseParallelGC \
  -XX:ParallelGCThreads=4"
```

### 2c. GC Logging

Always enable GC logging in production — zero overhead, invaluable for troubleshooting.

```dockerfile
ENV JAVA_OPTS="\
  -XX:MaxRAMPercentage=75.0 \
  -XX:+UseG1GC \
  -Xlog:gc*:file=/tmp/gc.log:time,uptime,level,tags:filecount=5,filesize=10m"
```

**GC log analysis**: Use [GCViewer](https://github.com/chewiebug/GCViewer) or [GCEasy](https://gceasy.io/) to analyze GC logs and identify:
- GC frequency (should be < 1/sec for G1GC)
- Pause time distribution (p99 should be < 200ms for G1GC)
- Allocation rate (watch for allocation pressure)
- Promotion rate (objects moving to old gen)

### 2d. JIT Warmup

```java
package com.example.app.config;

import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;

/**
 * JIT warmup — exercise critical paths after startup so the JIT compiler
 * optimizes hot code before real traffic arrives.
 * Only needed for latency-sensitive services behind a load balancer.
 */
@Component
public class WarmupRunner {

    private final OrderService orderService;
    private final HealthService healthService;

    public WarmupRunner(OrderService orderService, HealthService healthService) {
        this.orderService = orderService;
        this.healthService = healthService;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void warmup() {
        // Run 100 iterations of critical paths to trigger JIT compilation
        for (int i = 0; i < 100; i++) {
            try {
                healthService.checkAll();
                // Add other latency-critical paths here
            } catch (Exception ignored) {
                // Warmup failures are non-fatal
            }
        }
    }
}
```

---

## 3. Memory Management

### 3a. Avoid Autoboxing in Hot Paths

```java
// BAD — autoboxing creates garbage on every iteration
public long sumPrices(List<Product> products) {
    Long total = 0L;  // autoboxes on every +=
    for (Product p : products) {
        total += p.getPrice();  // creates a new Long object each time
    }
    return total;
}

// GOOD — use primitives
public long sumPrices(List<Product> products) {
    long total = 0L;
    for (Product p : products) {
        total += p.getPrice();
    }
    return total;
}
```

### 3b. StringBuilder for String Concatenation in Loops

```java
// BAD — creates a new StringBuilder and String per iteration
public String buildReport(List<OrderSummary> orders) {
    String report = "";
    for (OrderSummary order : orders) {
        report += order.getId() + ": " + order.getTotal() + "\n";  // O(n²)
    }
    return report;
}

// GOOD — single StringBuilder
public String buildReport(List<OrderSummary> orders) {
    StringBuilder sb = new StringBuilder(orders.size() * 64);  // pre-size
    for (OrderSummary order : orders) {
        sb.append(order.getId()).append(": ").append(order.getTotal()).append('\n');
    }
    return sb.toString();
}
```

### 3c. Object Pooling for Expensive Objects

```java
import org.apache.commons.pool2.BasePooledObjectFactory;
import org.apache.commons.pool2.ObjectPool;
import org.apache.commons.pool2.PooledObject;
import org.apache.commons.pool2.impl.DefaultPooledObject;
import org.apache.commons.pool2.impl.GenericObjectPool;
import org.apache.commons.pool2.impl.GenericObjectPoolConfig;

/**
 * Pool expensive-to-create objects (PDF generators, XML parsers, crypto instances).
 * Do NOT pool lightweight objects — the pool overhead exceeds the allocation cost.
 */
public class PdfGeneratorPool {

    private final ObjectPool<PdfGenerator> pool;

    public PdfGeneratorPool() {
        GenericObjectPoolConfig<PdfGenerator> config = new GenericObjectPoolConfig<>();
        config.setMaxTotal(16);
        config.setMaxIdle(8);
        config.setMinIdle(2);
        config.setMaxWait(Duration.ofSeconds(5));
        config.setTestOnBorrow(true);

        this.pool = new GenericObjectPool<>(new BasePooledObjectFactory<>() {
            @Override
            public PdfGenerator create() {
                return new PdfGenerator(); // expensive initialization
            }

            @Override
            public PooledObject<PdfGenerator> wrap(PdfGenerator obj) {
                return new DefaultPooledObject<>(obj);
            }

            @Override
            public void passivateObject(PooledObject<PdfGenerator> p) {
                p.getObject().reset(); // clean state before returning to pool
            }
        }, config);
    }

    public byte[] generatePdf(ReportData data) throws Exception {
        PdfGenerator generator = pool.borrowObject();
        try {
            return generator.generate(data);
        } finally {
            pool.returnObject(generator);
        }
    }
}
```

### 3d. Weak/Soft References for Caches

```java
import java.lang.ref.SoftReference;
import java.util.concurrent.ConcurrentHashMap;

/**
 * SoftReference cache — entries are evicted when the JVM is under memory pressure.
 * Use for expensive-to-compute but recreatable data (e.g., parsed templates, compiled regex).
 * For production caches, prefer Caffeine (§7a) — this is for niche cases only.
 */
public class SoftReferenceCache<K, V> {

    private final ConcurrentHashMap<K, SoftReference<V>> cache = new ConcurrentHashMap<>();

    public V get(K key) {
        SoftReference<V> ref = cache.get(key);
        return ref != null ? ref.get() : null;
    }

    public void put(K key, V value) {
        cache.put(key, new SoftReference<>(value));
    }
}
```

### 3e. JFR for Allocation Profiling

```bash
# Start JFR recording with allocation profiling
java -XX:StartFlightRecording=filename=allocation.jfr,duration=60s,settings=profile \
     -jar app.jar

# Analyze with jfr command-line tool
jfr print --events jdk.ObjectAllocationInNewTLAB allocation.jfr | head -50
jfr print --events jdk.ObjectAllocationOutsideTLAB allocation.jfr | head -50

# Or open allocation.jfr in JDK Mission Control for visual analysis
```

---

## 4. Database Performance

### 4a. JPA Batch Inserts

```yaml
# application.yml
spring:
  jpa:
    properties:
      hibernate:
        jdbc:
          batch_size: 50
        order_inserts: true
        order_updates: true
```

```java
/**
 * Batch insert with manual flush to control memory.
 * Without periodic flush, Hibernate accumulates all entities in the persistence context.
 */
@Transactional
public void importOrders(String tenantId, List<OrderImport> imports) {
    int batchSize = 50;
    for (int i = 0; i < imports.size(); i++) {
        OrderImport imp = imports.get(i);
        Order order = Order.fromImport(tenantId, imp);
        entityManager.persist(order);

        if (i > 0 && i % batchSize == 0) {
            entityManager.flush();   // Execute batch INSERT
            entityManager.clear();   // Release entities from persistence context
        }
    }
    entityManager.flush();
    entityManager.clear();
}
```

**CRITICAL**: When using `GenerationType.IDENTITY`, Hibernate cannot batch inserts because it needs the DB-generated ID immediately. Use `GenerationType.SEQUENCE` with allocation:

```java
@Id
@GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "order_seq")
@SequenceGenerator(name = "order_seq", sequenceName = "orders_id_seq", allocationSize = 50)
private Long id;
```

Or use `GenerationType.UUID` — UUIDs are generated in-memory and batch perfectly.

### 4b. @EntityGraph for Fetch Optimization

```java
public interface OrderRepository extends JpaRepository<Order, UUID> {

    /**
     * Fetch order with items in a single query — avoids N+1.
     * The @EntityGraph tells JPA to LEFT JOIN FETCH the items collection.
     */
    @EntityGraph(attributePaths = {"items", "items.product"})
    Optional<Order> findWithItemsById(UUID id);

    /**
     * Named entity graph for complex fetch strategies.
     */
    @EntityGraph(value = "Order.withItemsAndCustomer")
    List<Order> findByTenantIdAndStatus(UUID tenantId, OrderStatus status);
}
```

```java
@Entity
@NamedEntityGraph(
    name = "Order.withItemsAndCustomer",
    attributeNodes = {
        @NamedAttributeNode(value = "items", subgraph = "items-product"),
        @NamedAttributeNode("customer")
    },
    subgraphs = {
        @NamedSubgraph(name = "items-product",
            attributeNodes = @NamedAttributeNode("product"))
    }
)
public class Order {
    // ...
    @OneToMany(mappedBy = "order", fetch = FetchType.LAZY)
    private List<OrderItem> items;

    @ManyToOne(fetch = FetchType.LAZY)
    private Customer customer;
}
```

### 4c. Projection Interfaces/DTOs to Avoid SELECT *

```java
/**
 * Projection interface — JPA generates SQL that selects only these columns.
 * Use for list/summary endpoints where you don't need the full entity.
 */
public interface OrderSummaryProjection {
    UUID getId();
    String getStatus();
    BigDecimal getTotal();
    Instant getCreatedAt();
    int getItemCount();
}

public interface OrderRepository extends JpaRepository<Order, UUID> {

    /**
     * Returns only id, status, total, created_at, and item_count — NOT SELECT *.
     */
    List<OrderSummaryProjection> findByTenantId(UUID tenantId, Pageable pageable);

    /**
     * JPQL with DTO constructor expression — even more control.
     */
    @Query("""
        SELECT new com.example.app.dto.OrderListItem(
            o.id, o.status, o.total, o.createdAt, SIZE(o.items)
        )
        FROM Order o
        WHERE o.tenantId = :tenantId
        ORDER BY o.createdAt DESC
        """)
    List<OrderListItem> findOrderList(@Param("tenantId") UUID tenantId, Pageable pageable);
}
```

### 4d. Read Replicas with @Transactional(readOnly = true)

```java
package com.example.app.config;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.boot.autoconfigure.jdbc.DataSourceProperties;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Primary;
import org.springframework.jdbc.datasource.LazyConnectionDataSourceProxy;
import org.springframework.jdbc.datasource.lookup.AbstractRoutingDataSource;
import org.springframework.transaction.support.TransactionSynchronizationManager;

import javax.sql.DataSource;
import java.util.Map;

@Configuration
public class DataSourceRoutingConfig {

    @Bean
    @ConfigurationProperties("spring.datasource.primary")
    public DataSourceProperties primaryProperties() {
        return new DataSourceProperties();
    }

    @Bean
    @ConfigurationProperties("spring.datasource.replica")
    public DataSourceProperties replicaProperties() {
        return new DataSourceProperties();
    }

    @Bean
    public DataSource primaryDataSource() {
        return primaryProperties().initializeDataSourceBuilder().build();
    }

    @Bean
    public DataSource replicaDataSource() {
        return replicaProperties().initializeDataSourceBuilder().build();
    }

    @Bean
    @Primary
    public DataSource routingDataSource() {
        AbstractRoutingDataSource routing = new AbstractRoutingDataSource() {
            @Override
            protected Object determineCurrentLookupKey() {
                return TransactionSynchronizationManager.isCurrentTransactionReadOnly()
                        ? "replica" : "primary";
            }
        };
        routing.setTargetDataSources(Map.of(
                "primary", primaryDataSource(),
                "replica", replicaDataSource()
        ));
        routing.setDefaultTargetDataSource(primaryDataSource());
        return new LazyConnectionDataSourceProxy(routing);
    }
}
```

```java
// Service usage — read-only queries automatically go to replica
@Service
public class OrderQueryService {

    @Transactional(readOnly = true)  // Routes to replica
    public Page<OrderSummaryProjection> listOrders(UUID tenantId, Pageable pageable) {
        return orderRepository.findByTenantId(tenantId, pageable);
    }

    @Transactional  // Routes to primary
    public Order createOrder(String tenantId, CreateOrderRequest request) {
        return orderRepository.save(Order.create(tenantId, request));
    }
}
```

### 4e. Second-Level Cache with Caffeine

```yaml
# application.yml
spring:
  jpa:
    properties:
      hibernate:
        cache:
          use_second_level_cache: true
          region.factory_class: org.hibernate.cache.jcache.JCacheRegionFactory
        javax:
          cache:
            provider: com.github.benmanes.caffeine.jcache.spi.CaffeineCachingProvider
      jakarta:
        persistence:
          sharedCache:
            mode: ENABLE_SELECTIVE
```

```java
@Entity
@Cache(usage = CacheConcurrencyStrategy.READ_WRITE, region = "products")
@Table(name = "products")
public class Product {

    @Id
    private UUID id;

    @Column(nullable = false)
    private String name;

    @Column(nullable = false)
    private BigDecimal price;

    // Product data is read-heavy and changes rarely — good L2 cache candidate
}
```

```xml
<!-- src/main/resources/caffeine-cache.xml -->
<config xmlns="urn:jsr107:config"
        xmlns:caffeine="urn:caffeine:config">
    <cache name="products">
        <expiry>
            <ttl unit="minutes">15</ttl>
        </expiry>
        <caffeine:config maximumSize="1000"/>
    </cache>
</config>
```

### 4f. N+1 Detection

```yaml
# application.yml — enable Hibernate statistics in dev/staging
spring:
  jpa:
    properties:
      hibernate:
        generate_statistics: ${HIBERNATE_STATS:false}
        session:
          events:
            log:
              LOG_QUERIES_SLOWER_THAN_MS: 100
```

```java
/**
 * Log slow queries and N+1 detection in non-production environments.
 * Add this bean only in dev/staging profiles.
 */
@Component
@Profile({"local", "staging"})
public class HibernateStatisticsLogger {

    private static final Logger log = LoggerFactory.getLogger(HibernateStatisticsLogger.class);

    @PersistenceContext
    private EntityManager entityManager;

    @Scheduled(fixedRate = 60_000) // Log every 60 seconds
    public void logStatistics() {
        Session session = entityManager.unwrap(Session.class);
        SessionFactory sf = session.getSessionFactory();
        Statistics stats = sf.getStatistics();

        log.info("Hibernate stats: queries={} entityLoads={} entityInserts={} " +
                        "collectionLoads={} secondLevelCacheHits={} secondLevelCacheMisses={} " +
                        "queryExecutionMaxTime={}ms slowestQuery={}",
                stats.getQueryExecutionCount(),
                stats.getEntityLoadCount(),
                stats.getEntityInsertCount(),
                stats.getCollectionLoadCount(),
                stats.getSecondLevelCacheHitCount(),
                stats.getSecondLevelCacheMissCount(),
                stats.getQueryExecutionMaxTime(),
                stats.getQueryExecutionMaxTimeQueryString()
        );

        stats.clear();
    }
}
```

---

## 5. Profiling

### 5a. Java Flight Recorder (JFR) — Zero-Overhead Production Profiling

```bash
# Start JFR recording on a running JVM (via jcmd)
jcmd <pid> JFR.start name=profile duration=120s filename=/tmp/profile.jfr settings=profile

# Or start with JVM flags (always-on recording with rolling buffer)
java -XX:StartFlightRecording=disk=true,maxage=6h,maxsize=1g,dumponexit=true,filename=/tmp/recording.jfr \
     -jar app.jar

# Dump current recording
jcmd <pid> JFR.dump name=profile filename=/tmp/dump.jfr

# Analyze from command line
jfr print --events jdk.CPULoad /tmp/profile.jfr
jfr print --events jdk.GCPauseEvent /tmp/profile.jfr
jfr print --events jdk.ThreadSleep /tmp/profile.jfr
jfr summary /tmp/profile.jfr
```

**Key JFR events to monitor:**

| Event | What It Tells You |
|-------|-------------------|
| `jdk.CPULoad` | JVM and system CPU usage |
| `jdk.GarbageCollection` | GC frequency and pause times |
| `jdk.ObjectAllocationInNewTLAB` | Where allocations happen (allocation hot spots) |
| `jdk.ThreadPark` | Where threads are blocked/waiting |
| `jdk.JavaMonitorWait` | Lock contention |
| `jdk.SocketRead` / `jdk.SocketWrite` | Network IO latency |
| `jdk.FileRead` / `jdk.FileWrite` | Disk IO latency |

### 5b. async-profiler for CPU and Allocation Profiling

```bash
# CPU profiling (flame graph)
./asprof -d 30 -f /tmp/flamegraph.html <pid>

# Allocation profiling (where memory is allocated)
./asprof -d 30 -e alloc -f /tmp/alloc-flamegraph.html <pid>

# Lock contention profiling
./asprof -d 30 -e lock -f /tmp/lock-flamegraph.html <pid>

# Wall-clock profiling (includes IO wait and sleep — useful for finding slow IO)
./asprof -d 30 -e wall -f /tmp/wall-flamegraph.html <pid>
```

### 5c. Spring Boot Actuator Metrics for Performance Monitoring

```yaml
# Key actuator endpoints for performance diagnosis
management:
  endpoints:
    web:
      exposure:
        include: health,metrics,threaddump,heapdump,caches
```

```bash
# Check HTTP request latency percentiles
curl localhost:8080/actuator/metrics/http.server.requests \
  -d 'tag=uri:/api/v1/orders&tag=method:GET'

# Check HikariCP pool metrics
curl localhost:8080/actuator/metrics/hikaricp.connections.active
curl localhost:8080/actuator/metrics/hikaricp.connections.pending

# Check JVM memory
curl localhost:8080/actuator/metrics/jvm.memory.used
curl localhost:8080/actuator/metrics/jvm.gc.pause

# Get thread dump (identify blocked threads)
curl localhost:8080/actuator/threaddump

# Cache statistics
curl localhost:8080/actuator/caches
```

### 5d. Load Testing with Gatling

```scala
// src/test/scala/OrderSimulation.scala
import io.gatling.core.Predef._
import io.gatling.http.Predef._
import scala.concurrent.duration._

class OrderSimulation extends Simulation {

  val httpProtocol = http
    .baseUrl("http://localhost:8080")
    .header("X-Tenant-ID", "tenant_load_test")
    .header("Content-Type", "application/json")

  val createOrder = scenario("Create Order")
    .exec(
      http("POST /api/v1/orders")
        .post("/api/v1/orders")
        .body(StringBody("""{"items":[{"productId":"prod_1","quantity":2}]}"""))
        .check(status.is(201))
        .check(jsonPath("$.id").saveAs("orderId"))
    )
    .pause(1)
    .exec(
      http("GET /api/v1/orders/{id}")
        .get("/api/v1/orders/${orderId}")
        .check(status.is(200))
    )

  setUp(
    createOrder.inject(
      rampUsersPerSec(1).to(50).during(60.seconds),   // Ramp up
      constantUsersPerSec(50).during(120.seconds),      // Steady state
      rampUsersPerSec(50).to(1).during(30.seconds)      // Ramp down
    )
  ).protocols(httpProtocol)
    .assertions(
      global.responseTime.percentile(99).lt(500),       // p99 < 500ms
      global.successfulRequests.percent.gt(99.0),        // > 99% success
      global.requestsPerSec.gt(100)                      // > 100 RPS
    )
}
```

---

## 6. Concurrency

### 6a. Virtual Threads (Java 21) for IO-Bound Work

```yaml
# application.yml — enable virtual threads for Tomcat
spring:
  threads:
    virtual:
      enabled: true    # All HTTP request handlers run on virtual threads
```

That single line replaces the need for reactive programming (WebFlux) for most IO-bound workloads. Virtual threads are cheap (< 1 KB stack), so thousands can run concurrently.

```java
/**
 * With virtual threads enabled, this blocking code runs efficiently.
 * Each blocking call (DB query, HTTP call) parks the virtual thread
 * and releases the carrier platform thread — no thread pool exhaustion.
 */
@RestController
public class OrderController {

    @GetMapping("/api/v1/orders/{id}/enriched")
    public EnrichedOrder getEnrichedOrder(@PathVariable UUID id) {
        // These blocking calls run on virtual threads — no @Async needed
        Order order = orderRepository.findById(id).orElseThrow();
        CustomerProfile profile = customerClient.getProfile(order.getUserId());  // HTTP call
        ShippingEstimate shipping = shippingClient.estimate(order.getAddress()); // HTTP call
        return new EnrichedOrder(order, profile, shipping);
    }
}
```

### 6b. Structured Concurrency (Preview — Java 21+)

```java
import java.util.concurrent.StructuredTaskScope;

/**
 * Structured concurrency — fan-out, fan-in with proper lifecycle management.
 * If any subtask fails, all others are cancelled. No leaked threads.
 * Requires: --enable-preview
 */
public EnrichedOrder getEnrichedOrder(UUID orderId) throws Exception {
    Order order = orderRepository.findById(orderId).orElseThrow();

    try (var scope = new StructuredTaskScope.ShutdownOnFailure()) {
        var profileTask = scope.fork(() ->
                customerClient.getProfile(order.getUserId()));
        var shippingTask = scope.fork(() ->
                shippingClient.estimate(order.getAddress()));
        var inventoryTask = scope.fork(() ->
                inventoryClient.checkStock(order.getItemIds()));

        scope.join();            // Wait for all tasks
        scope.throwIfFailed();   // Propagate first failure

        return new EnrichedOrder(
                order,
                profileTask.get(),
                shippingTask.get(),
                inventoryTask.get()
        );
    }
}
```

### 6c. CompletableFuture for Async Composition

```java
@Service
public class OrderEnrichmentService {

    private final Executor taskExecutor;

    /**
     * Fan-out to multiple services concurrently, combine results.
     * Use when you need async composition outside of virtual threads.
     */
    public CompletableFuture<EnrichedOrder> enrichAsync(String tenantId, Order order) {
        CompletableFuture<CustomerProfile> profileFuture =
                CompletableFuture.supplyAsync(
                        () -> customerClient.getProfile(tenantId, order.getUserId()),
                        taskExecutor);

        CompletableFuture<ShippingEstimate> shippingFuture =
                CompletableFuture.supplyAsync(
                        () -> shippingClient.estimate(tenantId, order.getAddress()),
                        taskExecutor);

        return profileFuture.thenCombine(shippingFuture,
                (profile, shipping) -> new EnrichedOrder(order, profile, shipping))
                .orTimeout(5, TimeUnit.SECONDS)  // Timeout for the combined operation
                .exceptionally(ex -> {
                    log.error("Enrichment failed for order={}", order.getId(), ex);
                    return new EnrichedOrder(order, null, null); // Graceful degradation
                });
    }
}
```

### 6d. @Async with Custom TaskExecutor (Bounded Queue)

```java
package com.example.app.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableAsync;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;

import java.util.concurrent.Executor;
import java.util.concurrent.RejectedExecutionHandler;
import java.util.concurrent.ThreadPoolExecutor;

@Configuration
@EnableAsync
public class AsyncConfig {

    /**
     * ALWAYS use a bounded queue for @Async executors.
     * Unbounded queues (LinkedBlockingQueue default) will cause OOM under load
     * because tasks accumulate faster than they are processed.
     */
    @Bean("taskExecutor")
    public Executor taskExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(4);          // Start with core_count
        executor.setMaxPoolSize(16);          // Max threads under pressure
        executor.setQueueCapacity(100);       // BOUNDED queue — reject when full
        executor.setThreadNamePrefix("async-");
        executor.setKeepAliveSeconds(60);

        // CallerRunsPolicy — when queue is full, the calling thread executes the task.
        // This provides natural backpressure instead of throwing RejectedExecutionException.
        executor.setRejectedExecutionHandler(new ThreadPoolExecutor.CallerRunsPolicy());

        executor.initialize();
        return executor;
    }
}
```

### 6e. Thread Pool Sizing

| Workload Type | Formula | Example (8 cores) |
|---------------|---------|-------------------|
| **CPU-bound** | `core_count` or `core_count + 1` | 8-9 threads |
| **IO-bound** | `core_count * (1 + wait_time/compute_time)` | 8 * (1 + 10/1) = 88 threads |
| **Mixed** | Profile first, then tune | Start with `core_count * 4` |
| **Virtual threads** | No sizing needed — use `Executors.newVirtualThreadPerTaskExecutor()` | Unlimited virtual threads |

```java
// CPU-bound work — fixed pool sized to core count
ExecutorService cpuPool = Executors.newFixedThreadPool(
        Runtime.getRuntime().availableProcessors());

// IO-bound work — virtual thread executor (Java 21+)
ExecutorService ioPool = Executors.newVirtualThreadPerTaskExecutor();

// Legacy IO-bound (pre-Java 21) — larger fixed pool
ExecutorService legacyIoPool = Executors.newFixedThreadPool(
        Runtime.getRuntime().availableProcessors() * 4);
```

---

## 7. Caching

### 7a. Spring Cache Abstraction with @Cacheable

```java
package com.example.app.config;

import com.github.benmanes.caffeine.cache.Caffeine;
import org.springframework.cache.CacheManager;
import org.springframework.cache.annotation.EnableCaching;
import org.springframework.cache.caffeine.CaffeineCacheManager;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.time.Duration;

@Configuration
@EnableCaching
public class CacheConfig {

    @Bean
    public CacheManager cacheManager() {
        CaffeineCacheManager manager = new CaffeineCacheManager();
        manager.setCaffeine(Caffeine.newBuilder()
                .maximumSize(10_000)
                .expireAfterWrite(Duration.ofMinutes(15))
                .recordStats());     // Enable cache statistics for monitoring
        return manager;
    }

    /**
     * Named caches with different configurations.
     */
    @Bean
    public CacheManager multiCacheManager() {
        CaffeineCacheManager manager = new CaffeineCacheManager();
        manager.registerCustomCache("products",
                Caffeine.newBuilder()
                        .maximumSize(5_000)
                        .expireAfterWrite(Duration.ofMinutes(30))
                        .recordStats()
                        .build());
        manager.registerCustomCache("userProfiles",
                Caffeine.newBuilder()
                        .maximumSize(10_000)
                        .expireAfterAccess(Duration.ofMinutes(10))
                        .recordStats()
                        .build());
        manager.registerCustomCache("configValues",
                Caffeine.newBuilder()
                        .maximumSize(1_000)
                        .expireAfterWrite(Duration.ofHours(1))
                        .refreshAfterWrite(Duration.ofMinutes(30))
                        .recordStats()
                        .build());
        return manager;
    }
}
```

### 7b. @Cacheable in Service Layer

```java
@Service
public class ProductService {

    /**
     * @Cacheable — result is cached after first invocation.
     * Subsequent calls with the same tenantId+productId return the cached value.
     * Key is auto-generated from method parameters.
     */
    @Cacheable(value = "products", key = "#tenantId + ':' + #productId")
    public Product getProduct(String tenantId, UUID productId) {
        log.debug("Cache miss for product tenantId={} productId={}", tenantId, productId);
        return productRepository.findByTenantIdAndId(UUID.fromString(tenantId), productId)
                .orElseThrow(() -> new ResourceNotFoundException("Product", productId.toString()));
    }

    /**
     * @CachePut — always executes the method and updates the cache.
     * Use after create/update to keep the cache fresh.
     */
    @CachePut(value = "products", key = "#tenantId + ':' + #result.id")
    public Product updateProduct(String tenantId, UUID productId, UpdateProductRequest request) {
        Product product = productRepository.findByTenantIdAndId(
                UUID.fromString(tenantId), productId).orElseThrow();
        product.update(request);
        return productRepository.save(product);
    }

    /**
     * @CacheEvict — removes the entry from the cache.
     * Use after delete or when data is known to be stale.
     */
    @CacheEvict(value = "products", key = "#tenantId + ':' + #productId")
    public void deleteProduct(String tenantId, UUID productId) {
        productRepository.deleteByTenantIdAndId(UUID.fromString(tenantId), productId);
    }

    /**
     * @CacheEvict with allEntries — clear the entire cache.
     * Use for bulk operations or admin cache-clear endpoints.
     */
    @CacheEvict(value = "products", allEntries = true)
    public void clearProductCache() {
        log.info("Product cache cleared");
    }
}
```

### 7c. Cache Stampede Prevention with sync=true

```java
/**
 * sync=true — only one thread computes the value on cache miss.
 * Other concurrent requests for the same key wait for the first computation.
 * Prevents cache stampede (thundering herd) on popular keys after expiry.
 */
@Cacheable(value = "products", key = "#tenantId + ':' + #productId", sync = true)
public Product getProduct(String tenantId, UUID productId) {
    return productRepository.findByTenantIdAndId(UUID.fromString(tenantId), productId)
            .orElseThrow();
}
```

### 7d. Redis for Distributed Cache

```yaml
# application.yml
spring:
  cache:
    type: redis
    redis:
      time-to-live: 900000    # 15 minutes in milliseconds
      cache-null-values: false  # Don't cache null results
      key-prefix: "order-service:"
      use-key-prefix: true
  data:
    redis:
      host: ${REDIS_HOST:localhost}
      port: ${REDIS_PORT:6379}
```

```java
package com.example.app.config;

import org.springframework.cache.annotation.EnableCaching;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.cache.RedisCacheConfiguration;
import org.springframework.data.redis.cache.RedisCacheManager;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.serializer.GenericJackson2JsonRedisSerializer;
import org.springframework.data.redis.serializer.RedisSerializationContext;

import java.time.Duration;
import java.util.Map;

@Configuration
@EnableCaching
public class RedisCacheConfig {

    @Bean
    public RedisCacheManager cacheManager(RedisConnectionFactory connectionFactory) {
        RedisCacheConfiguration defaultConfig = RedisCacheConfiguration.defaultCacheConfig()
                .entryTtl(Duration.ofMinutes(15))
                .serializeValuesWith(
                        RedisSerializationContext.SerializationPair.fromSerializer(
                                new GenericJackson2JsonRedisSerializer()))
                .prefixCacheNameWith("order-service:")
                .disableCachingNullValues();

        // Per-cache TTL overrides
        Map<String, RedisCacheConfiguration> cacheConfigs = Map.of(
                "products", defaultConfig.entryTtl(Duration.ofMinutes(30)),
                "userProfiles", defaultConfig.entryTtl(Duration.ofMinutes(10)),
                "configValues", defaultConfig.entryTtl(Duration.ofHours(1))
        );

        return RedisCacheManager.builder(connectionFactory)
                .cacheDefaults(defaultConfig)
                .withInitialCacheConfigurations(cacheConfigs)
                .transactionAware()
                .build();
    }
}
```

### 7e. Two-Tier Cache (Caffeine L1 + Redis L2)

```java
/**
 * Two-tier cache: Caffeine (in-process, microseconds) -> Redis (distributed, milliseconds).
 * Check Caffeine first; on miss, check Redis; on miss, call the database.
 * Write-through: updates write to both caches.
 */
@Service
public class TwoTierCacheService<K, V> {

    private final Cache<K, V> localCache;   // Caffeine
    private final RedisTemplate<String, V> redisTemplate;
    private final String cachePrefix;
    private final Duration redisTtl;

    public TwoTierCacheService(RedisTemplate<String, V> redisTemplate,
                                String cachePrefix, Duration redisTtl,
                                int maxLocalSize, Duration localTtl) {
        this.localCache = Caffeine.newBuilder()
                .maximumSize(maxLocalSize)
                .expireAfterWrite(localTtl)
                .recordStats()
                .build();
        this.redisTemplate = redisTemplate;
        this.cachePrefix = cachePrefix;
        this.redisTtl = redisTtl;
    }

    public V get(K key, Function<K, V> loader) {
        // L1: Caffeine
        V value = localCache.getIfPresent(key);
        if (value != null) return value;

        // L2: Redis
        String redisKey = cachePrefix + key;
        value = redisTemplate.opsForValue().get(redisKey);
        if (value != null) {
            localCache.put(key, value);  // Promote to L1
            return value;
        }

        // L3: Source (database, API, etc.)
        value = loader.apply(key);
        if (value != null) {
            localCache.put(key, value);
            redisTemplate.opsForValue().set(redisKey, value, redisTtl);
        }
        return value;
    }

    public void evict(K key) {
        localCache.invalidate(key);
        redisTemplate.delete(cachePrefix + key);
    }
}
```

---

## Critical Rules

- `spring.jpa.open-in-view: false` — always. OSIV holds DB connections for the entire request
- HikariCP `maximum-pool-size: 10` is the starting point — measure before increasing
- `connection-timeout: 5000` — fail fast, never block threads for 30 seconds
- Use `-XX:MaxRAMPercentage=75` in containers — never hard-code `-Xmx` in Dockerized services
- Enable GC logging in production — zero overhead, invaluable for diagnosis
- Enable `leak-detection-threshold` in all environments — catches unreturned connections
- Use `GenerationType.SEQUENCE` or `UUID` for batch inserts — `IDENTITY` prevents batching
- Use `@EntityGraph` or projections for queries — never `SELECT *` on list endpoints
- `@Cacheable(sync = true)` on popular keys to prevent cache stampede
- Bounded queues for all `@Async` executors — unbounded queues cause OOM
- Virtual threads (Java 21) replace reactive programming for most IO-bound workloads
- Profile before optimizing — use JFR or async-profiler to find real bottlenecks
- Metrics on every pool (DB, thread, HTTP client, cache) — saturation is the leading performance indicator
