---
skill: observability-java
description: Java/Spring Boot observability archetype — OpenTelemetry traces, Micrometer metrics, structured logging with Logback, MDC correlation, tenant-aware instrumentation, Docker Compose collector stack
version: "1.0"
tags:
  - java
  - spring-boot
  - observability
  - opentelemetry
  - micrometer
  - tracing
  - metrics
  - logging
  - archetype
  - backend
---

# Observability Archetype (Spring Boot)

> Java samples compile-checked 2026-09-30: JDK 25.0.4.1, Spring Boot 4.1.1, Maven 3.9.16; the Gradle and Maven dependency snippets resolve and compile (Gradle 9.8.0) with no OpenTelemetry API downgrade (`tests/archetype-compile/java/run.sh`).

> **CANONICAL REFERENCE**: This file is the single source of truth for Java/Spring Boot observability patterns. All other Java skill packs that mention tracing, metrics, or structured logging should defer to this file. For language-agnostic concepts (error taxonomy, SLOs and alerting, log levels), see `observability-patterns.md`.

Complete OpenTelemetry integration for Spring Boot services. Every generated service MUST follow this pattern.

---

## Dependencies (Gradle)

```kotlin
// build.gradle.kts
plugins {
    id("org.springframework.boot") version "4.1.1"
    id("io.spring.dependency-management") version "1.1.7"
}

dependencyManagement {
    imports {
        // After Spring Boot's BOM, so it wins: Boot pins an older OpenTelemetry API than the starter needs
        mavenBom("io.opentelemetry.instrumentation:opentelemetry-instrumentation-bom:2.31.1")
    }
}

dependencies {
    // --- Observability Core ---
    implementation("org.springframework.boot:spring-boot-starter-actuator")

    // OpenTelemetry Spring Boot starter (traces + metrics + logs); Spring Boot 4 needs 2.23 or later
    implementation("io.opentelemetry.instrumentation:opentelemetry-spring-boot-starter")

    // Micrometer -> OTel bridge for custom metrics
    implementation("io.micrometer:micrometer-registry-otlp")

    // Structured logging (9.x is on Jackson 3, like Spring Boot 4)
    implementation("net.logstash.logback:logstash-logback-encoder:9.0")

    // OTel annotations (@WithSpan)
    implementation("io.opentelemetry.instrumentation:opentelemetry-instrumentation-annotations")
}
```

### Maven Alternative

With `spring-boot-starter-parent`, a BOM imported in your own `<dependencyManagement>` overrides the
OpenTelemetry versions the parent manages, which is what the starter needs.

```xml
<dependencyManagement>
    <dependencies>
        <dependency>
            <groupId>io.opentelemetry.instrumentation</groupId>
            <artifactId>opentelemetry-instrumentation-bom</artifactId>
            <version>2.31.1</version>
            <type>pom</type>
            <scope>import</scope>
        </dependency>
    </dependencies>
</dependencyManagement>

<dependencies>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-actuator</artifactId>
    </dependency>
    <dependency>
        <groupId>io.opentelemetry.instrumentation</groupId>
        <artifactId>opentelemetry-spring-boot-starter</artifactId>
    </dependency>
    <dependency>
        <groupId>io.micrometer</groupId>
        <artifactId>micrometer-registry-otlp</artifactId>
    </dependency>
    <dependency>
        <groupId>net.logstash.logback</groupId>
        <artifactId>logstash-logback-encoder</artifactId>
        <version>9.0</version>
    </dependency>
    <dependency>
        <groupId>io.opentelemetry.instrumentation</groupId>
        <artifactId>opentelemetry-instrumentation-annotations</artifactId>
    </dependency>
</dependencies>
```

---

## 1. Distributed Tracing

### 1a. OTel Java Agent (Recommended — Zero-Code Instrumentation)

The Java agent auto-instruments Spring MVC, WebFlux, JDBC, JPA, Redis, HTTP clients, gRPC, Kafka, and more. Attach it at JVM startup — no code changes required for framework-level spans.

```dockerfile
# Dockerfile — download and attach the OTel Java agent
FROM eclipse-temurin:21-jre-alpine

# Download OTel Java agent
ADD https://github.com/open-telemetry/opentelemetry-java-instrumentation/releases/download/v2.6.0/opentelemetry-javaagent.jar /opt/otel/opentelemetry-javaagent.jar

COPY build/libs/app.jar /app/app.jar

ENV JAVA_TOOL_OPTIONS="-javaagent:/opt/otel/opentelemetry-javaagent.jar"
ENV OTEL_SERVICE_NAME="order-service"
ENV OTEL_EXPORTER_OTLP_ENDPOINT="http://otel-collector:4318"
ENV OTEL_EXPORTER_OTLP_PROTOCOL="http/protobuf"
ENV OTEL_METRICS_EXPORTER="otlp"
ENV OTEL_LOGS_EXPORTER="otlp"
ENV OTEL_TRACES_SAMPLER="parentbased_traceidratio"
ENV OTEL_TRACES_SAMPLER_ARG="0.1"

ENTRYPOINT ["java", "-jar", "/app/app.jar"]
```

**Key agent environment variables:**

| Variable | Value | Purpose |
|----------|-------|---------|
| `OTEL_SERVICE_NAME` | `order-service` | Identifies the service in traces |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://otel-collector:4318` | OTLP HTTP endpoint |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | `http/protobuf` | Protocol (http/protobuf or grpc) |
| `OTEL_TRACES_SAMPLER` | `parentbased_traceidratio` | Sampling strategy |
| `OTEL_TRACES_SAMPLER_ARG` | `0.1` | Sample 10% of root traces |
| `OTEL_RESOURCE_ATTRIBUTES` | `deployment.environment=prod` | Additional resource attributes |
| `OTEL_INSTRUMENTATION_COMMON_DB_STATEMENT_SANITIZER_ENABLED` | `true` | Sanitize SQL in spans |

### 1b. Spring Boot Starter (Code-Based Setup)

When you need fine-grained control or cannot use the Java agent (e.g., native images):

```yaml
# application.yml
spring:
  application:
    name: order-service

otel:
  exporter:
    otlp:
      endpoint: ${OTEL_EXPORTER_OTLP_ENDPOINT:http://localhost:4318}
      protocol: http/protobuf
  resource:
    attributes:
      service.name: ${spring.application.name}
      service.version: ${APP_VERSION:0.0.1}
      deployment.environment: ${DEPLOY_ENV:local}

management:
  otlp:
    tracing:
      endpoint: ${OTEL_EXPORTER_OTLP_ENDPOINT:http://localhost:4318}/v1/traces
  tracing:
    sampling:
      probability: ${OTEL_TRACES_SAMPLE_RATE:1.0}
```

### 1c. Manual Spans with @WithSpan Annotation

Use `@WithSpan` to create spans for business-logic methods that are not auto-instrumented. The annotation creates a child span under the current active span.

```java
package com.example.app.service;

import io.opentelemetry.api.trace.Span;
import io.opentelemetry.api.trace.StatusCode;
import io.opentelemetry.instrumentation.annotations.SpanAttribute;
import io.opentelemetry.instrumentation.annotations.WithSpan;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

@Service
public class OrderService {

    private static final Logger log = LoggerFactory.getLogger(OrderService.class);

    private final OrderRepository orderRepository;
    private final PaymentClient paymentClient;
    private final InventoryClient inventoryClient;

    public OrderService(OrderRepository orderRepository,
                        PaymentClient paymentClient,
                        InventoryClient inventoryClient) {
        this.orderRepository = orderRepository;
        this.paymentClient = paymentClient;
        this.inventoryClient = inventoryClient;
    }

    /**
     * @WithSpan creates a span named "OrderService.createOrder" by default.
     * @SpanAttribute adds the parameter as a span attribute automatically.
     */
    @WithSpan
    public Order createOrder(
            @SpanAttribute("tenant_id") String tenantId,
            @SpanAttribute("user_id") String userId,
            CreateOrderRequest request) {

        log.info("Creating order for tenant={} user={} items={}",
                tenantId, userId, request.getItems().size());

        // Validate inventory — child span via @WithSpan on inventoryClient
        inventoryClient.reserveStock(tenantId, request.getItems());

        // Create order entity
        Order order = Order.create(tenantId, userId, request);
        order = orderRepository.save(order);

        // Charge payment — child span via @WithSpan on paymentClient
        paymentClient.charge(tenantId, order.getId(), order.getTotal());

        // Add order_id to current span after creation
        Span.current().setAttribute("order_id", order.getId().toString());
        Span.current().setAttribute("order_total", order.getTotal().doubleValue());

        log.info("Order created orderId={} total={}", order.getId(), order.getTotal());
        return order;
    }
}
```

### 1d. Programmatic Spans with Tracer Bean

For loops, conditional logic, or when you need to control span lifecycle directly:

```java
package com.example.app.service;

import io.opentelemetry.api.common.AttributeKey;
import io.opentelemetry.api.common.Attributes;
import io.opentelemetry.api.trace.Span;
import io.opentelemetry.api.trace.StatusCode;
import io.opentelemetry.api.trace.Tracer;
import io.opentelemetry.context.Scope;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class BatchProcessingService {

    private final Tracer tracer;
    private final OrderRepository orderRepository;

    public BatchProcessingService(Tracer tracer, OrderRepository orderRepository) {
        this.tracer = tracer;
        this.orderRepository = orderRepository;
    }

    public BatchResult processBatch(String tenantId, List<OrderRequest> requests) {
        Span batchSpan = tracer.spanBuilder("BatchProcessingService.processBatch")
                .setAttribute("tenant_id", tenantId)
                .setAttribute("batch_size", requests.size())
                .startSpan();

        try (Scope scope = batchSpan.makeCurrent()) {
            int successCount = 0;
            int failureCount = 0;

            for (int i = 0; i < requests.size(); i++) {
                OrderRequest req = requests.get(i);
                Span itemSpan = tracer.spanBuilder("processBatchItem")
                        .setAttribute("tenant_id", tenantId)
                        .setAttribute("batch_index", i)
                        .setAttribute("item_id", req.getItemId())
                        .startSpan();

                try (Scope itemScope = itemSpan.makeCurrent()) {
                    orderRepository.save(Order.fromRequest(tenantId, req));
                    successCount++;
                } catch (Exception e) {
                    failureCount++;
                    itemSpan.recordException(e);
                    itemSpan.setStatus(StatusCode.ERROR, e.getMessage());
                } finally {
                    itemSpan.end();
                }
            }

            batchSpan.setAttribute("success_count", successCount);
            batchSpan.setAttribute("failure_count", failureCount);

            return new BatchResult(successCount, failureCount);

        } catch (Exception e) {
            batchSpan.recordException(e);
            batchSpan.setStatus(StatusCode.ERROR, e.getMessage());
            throw e;
        } finally {
            batchSpan.end();
        }
    }
}
```

### 1e. Context Propagation Through @Async and CompletableFuture

OTel context does not propagate automatically across thread boundaries. Wrap executors to propagate trace context.

```java
package com.example.app.config;

import io.opentelemetry.context.Context;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableAsync;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;

import java.util.concurrent.Executor;

@Configuration
@EnableAsync
public class AsyncConfig {

    /**
     * Custom executor that propagates OTel context to async threads.
     * Without this, @Async methods lose trace_id and span_id.
     */
    @Bean("taskExecutor")
    public Executor taskExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(4);
        executor.setMaxPoolSize(16);
        executor.setQueueCapacity(100);
        executor.setThreadNamePrefix("async-");
        executor.setTaskDecorator(runnable -> {
            // Capture OTel context from the calling thread
            Context otelContext = Context.current();
            return () -> {
                // Restore OTel context in the async thread
                try (var scope = otelContext.makeCurrent()) {
                    runnable.run();
                }
            };
        });
        executor.initialize();
        return executor;
    }
}
```

```java
// CompletableFuture with context propagation
import io.opentelemetry.context.Context;

public class ContextAwareCompletableFuture {

    /**
     * Run async work with OTel context propagated.
     */
    public static <T> CompletableFuture<T> supplyAsync(
            Supplier<T> supplier, Executor executor) {
        Context otelContext = Context.current();
        return CompletableFuture.supplyAsync(() -> {
            try (var scope = otelContext.makeCurrent()) {
                return supplier.get();
            }
        }, executor);
    }
}

// Usage
@WithSpan
public OrderEnrichment enrichOrder(String tenantId, Order order) {
    CompletableFuture<CustomerProfile> profileFuture =
            ContextAwareCompletableFuture.supplyAsync(
                    () -> customerClient.getProfile(tenantId, order.getUserId()),
                    taskExecutor);

    CompletableFuture<ShippingEstimate> shippingFuture =
            ContextAwareCompletableFuture.supplyAsync(
                    () -> shippingClient.estimate(tenantId, order.getAddress()),
                    taskExecutor);

    return profileFuture.thenCombine(shippingFuture,
            (profile, shipping) -> new OrderEnrichment(order, profile, shipping))
            .join();
}
```

### 1f. JDBC/JPA and Redis Auto-Instrumentation

The Java agent auto-instruments JDBC, Hibernate, and Lettuce/Jedis. No code changes needed. Spans are created automatically for:

- Every JDBC query (with sanitized SQL)
- Every Hibernate session operation
- Every Redis command

To add tenant context to auto-instrumented spans, use a `SpanProcessor`:

```java
package com.example.app.config;

import io.opentelemetry.api.common.AttributeKey;
import io.opentelemetry.context.Context;
import io.opentelemetry.sdk.trace.ReadWriteSpan;
import io.opentelemetry.sdk.trace.ReadableSpan;
import io.opentelemetry.sdk.trace.SpanProcessor;
import org.slf4j.MDC;
import org.springframework.stereotype.Component;

/**
 * Injects tenant_id from MDC into every span (including auto-instrumented ones).
 * This ensures JDBC, Redis, and HTTP client spans carry tenant context.
 */
@Component
public class TenantSpanProcessor implements SpanProcessor {

    private static final AttributeKey<String> TENANT_ID = AttributeKey.stringKey("tenant_id");
    private static final AttributeKey<String> REQUEST_ID = AttributeKey.stringKey("request_id");

    @Override
    public void onStart(Context parentContext, ReadWriteSpan span) {
        String tenantId = MDC.get("tenant_id");
        if (tenantId != null) {
            span.setAttribute(TENANT_ID, tenantId);
        }
        String requestId = MDC.get("request_id");
        if (requestId != null) {
            span.setAttribute(REQUEST_ID, requestId);
        }
    }

    @Override
    public boolean isStartRequired() { return true; }

    @Override
    public void onEnd(ReadableSpan span) { }

    @Override
    public boolean isEndRequired() { return false; }
}
```

### Span Naming Convention

| Layer | Pattern | Example |
|-------|---------|---------|
| HTTP handler | `HTTP {METHOD} {path}` | `HTTP POST /api/v1/orders` |
| Service method | `{ServiceName}.{methodName}` | `OrderService.createOrder` |
| Repository | `{system}.{table}.{operation}` | `postgres.orders.insert` |
| External call | `{service}.{operation}` | `payment-gateway.charge` |
| Batch item | `{operation}Item` | `processBatchItem` |
| Async task | `async.{taskName}` | `async.sendNotification` |

---

## 2. Metrics

### 2a. Micrometer with OTel Bridge

Spring Boot Actuator + Micrometer is the standard metrics layer. The OTLP registry exports to the OTel Collector.

**HTTP server metrics: one source, with the stable OTel names.** The OTel Java agent (1a) and the
starter (1b) record `http.server.request.duration` in seconds, with the stable HTTP semantic-convention
attributes:
- `http.request.method` (`_OTHER` for unknown methods);
- `http.route`, the Spring MVC route **template** (for example `/api/v1/orders/{id}`, never the raw
  URI);
- `http.response.status_code`, `url.scheme`, and `error.type` on failures.

Its count is the request count, so don't add a request counter. Spring's Micrometer timer
`http.server.requests` measures the same thing (its `uri` tag is also the template). Build SLIs on one
of the two, not both, and give the Micrometer timer the semconv buckets below.

Neither metric carries `tenant_id`, and no tag you add may either: every distinct value is a new time
series. If you really need a per-tenant dimension, the only one allowed is a bounded `tenant.tier`
(free/pro/enterprise). Ask per-tenant questions of traces and logs.

```yaml
# application.yml
management:
  endpoints:
    web:
      exposure:
        include: health,info,metrics,prometheus
  metrics:
    tags:
      application: ${spring.application.name}
      environment: ${DEPLOY_ENV:local}
    distribution:
      # Explicit buckets = the OTel semconv boundaries; the NFR latency threshold must be one of them
      slo:
        http.server.requests: 5ms, 10ms, 25ms, 50ms, 75ms, 100ms, 250ms, 500ms, 750ms, 1s, 2500ms, 5s, 7500ms, 10s
  otlp:
    metrics:
      export:
        url: ${OTEL_EXPORTER_OTLP_ENDPOINT:http://localhost:4318}/v1/metrics
        step: 30s
```

### 2b. Counter — Business Event Counting

```java
package com.example.app.metrics;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.stereotype.Component;

@Component
public class AppMetrics {

    private final MeterRegistry meterRegistry;

    public AppMetrics(MeterRegistry meterRegistry) {
        this.meterRegistry = meterRegistry;
    }

    // No request counter: the http.server.request.duration histogram's count IS the request count.

    /**
     * Business event counter — track domain events for KPI dashboards.
     * Tags are small enums only: no tenant_id, user or entity IDs, or error messages.
     */
    public void recordBusinessEvent(String eventType, String outcome) {
        meterRegistry.counter("business.events.total",
                "event_type", eventType,
                "outcome", outcome
        ).increment();
    }

    /**
     * Record order value for revenue tracking.
     */
    public void recordOrderValue(double amount, String paymentMethod) {
        meterRegistry.counter("business.order.revenue",
                "payment_method", paymentMethod
        ).increment(amount);
    }
}
```

### 2c. Timer — Latency Measurement with @Timed

```java
package com.example.app.service;

import io.micrometer.core.annotation.Timed;
import org.springframework.stereotype.Service;

@Service
public class OrderService {

    private final OrderRepository orderRepository;

    public OrderService(OrderRepository orderRepository) {
        this.orderRepository = orderRepository;
    }

    /**
     * @Timed creates a Timer metric that records invocation duration.
     * histogram=true enables percentile histograms for p50/p95/p99 queries.
     */
    @Timed(
        value = "order.create.duration",
        description = "Time to create an order",
        histogram = true,
        extraTags = {"operation", "create"}
    )
    public Order createOrder(String tenantId, CreateOrderRequest request) {
        // business logic — duration is recorded automatically
        return orderRepository.save(Order.create(tenantId, request));
    }
}
```

Enable `@Timed` support with a `TimedAspect` bean:

```java
package com.example.app.config;

import io.micrometer.core.aop.TimedAspect;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class MetricsConfig {

    @Bean
    public TimedAspect timedAspect(MeterRegistry registry) {
        return new TimedAspect(registry);
    }
}
```

Programmatic timer for complex flows:

```java
import io.micrometer.core.instrument.Timer;

public void processPayment(String tenantId, PaymentRequest request) {
    Timer.Sample sample = Timer.start(meterRegistry);
    try {
        paymentGateway.charge(request);
        sample.stop(Timer.builder("payment.processing.duration")
                .tag("method", request.getMethod()) // payment method: a small enum. No tenant_id.
                .tag("outcome", "success")
                .register(meterRegistry));
    } catch (Exception e) {
        sample.stop(Timer.builder("payment.processing.duration")
                .tag("method", request.getMethod())
                .tag("outcome", "failure")
                .register(meterRegistry));
        throw e;
    }
}
```

### 2d. Gauge — Active Connections and Thread Pool Sizes

```java
package com.example.app.config;

import io.micrometer.core.instrument.Gauge;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.binder.MeterBinder;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;
import org.springframework.stereotype.Component;

import javax.sql.DataSource;
import com.zaxxer.hikari.HikariDataSource;

@Component
public class InfrastructureMetrics implements MeterBinder {

    private final DataSource dataSource;
    private final ThreadPoolTaskExecutor taskExecutor;

    public InfrastructureMetrics(DataSource dataSource,
                                  ThreadPoolTaskExecutor taskExecutor) {
        this.dataSource = dataSource;
        this.taskExecutor = taskExecutor;
    }

    @Override
    public void bindTo(MeterRegistry registry) {
        // HikariCP pool metrics (also auto-bound by Spring Boot, shown for illustration)
        if (dataSource instanceof HikariDataSource hikari) {
            Gauge.builder("db.pool.active_connections", hikari,
                    ds -> ds.getHikariPoolMXBean().getActiveConnections())
                    .description("Active database connections")
                    .register(registry);

            Gauge.builder("db.pool.idle_connections", hikari,
                    ds -> ds.getHikariPoolMXBean().getIdleConnections())
                    .description("Idle database connections")
                    .register(registry);

            Gauge.builder("db.pool.pending_threads", hikari,
                    ds -> ds.getHikariPoolMXBean().getThreadsAwaitingConnection())
                    .description("Threads waiting for a connection")
                    .register(registry);
        }

        // Thread pool gauges
        Gauge.builder("thread_pool.active", taskExecutor,
                ThreadPoolTaskExecutor::getActiveCount)
                .description("Active threads in task executor")
                .register(registry);

        Gauge.builder("thread_pool.queue_size", taskExecutor,
                e -> e.getThreadPoolExecutor().getQueue().size())
                .description("Task executor queue depth")
                .register(registry);

        Gauge.builder("thread_pool.pool_size", taskExecutor,
                ThreadPoolTaskExecutor::getPoolSize)
                .description("Current thread pool size")
                .register(registry);
    }
}
```

### 2e. Distribution Summary — Response Sizes

```java
import io.micrometer.core.instrument.DistributionSummary;

DistributionSummary responseSizes = DistributionSummary.builder("http.response.size")
        .description("HTTP response body size in bytes")
        .baseUnit("bytes")
        // The route TEMPLATE (request attribute HandlerMapping.BEST_MATCHING_PATTERN_ATTRIBUTE,
        // e.g. "/api/v1/orders/{id}"), never request.getRequestURI(). No tenant_id.
        .tag("http.route", routeTemplate)
        .publishPercentileHistogram()
        .register(meterRegistry);

responseSizes.record(responseBody.length);
```

### 2f. Actuator Endpoints and Prometheus Scraping

```yaml
# application.yml — expose metrics for Prometheus
management:
  endpoints:
    web:
      exposure:
        include: health,info,metrics,prometheus
  endpoint:
    health:
      show-details: when_authorized
      probes:
        enabled: true
  prometheus:
    metrics:
      export:
        enabled: true
```

Prometheus scrape config:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'order-service'
    metrics_path: '/actuator/prometheus'
    scrape_interval: 15s
    static_configs:
      - targets: ['order-service:8080']
```

### Key Metrics to Instrument

| Metric | Type | Tags (all bounded, no tenant_id) | Purpose |
|--------|------|------|---------|
| `http.server.request.duration` | Histogram (s) | (OTel agent/starter) http.request.method, http.route (template), http.response.status_code, url.scheme, error.type | Rate, errors and latency (RED); the count is the request count |
| `http.server.requests` | Timer | (Spring/Micrometer; the alternative to the row above) uri (template), method, status, outcome | The same data under Spring's names. Build SLIs on one of the two, not both |
| `order.create.duration` | Timer | operation | Business operation latency |
| `business.events.total` | Counter | event_type, outcome | Business KPIs |
| `business.order.revenue` | Counter | payment_method | Revenue tracking |
| `db.pool.active_connections` | Gauge | pool_name | Connection saturation |
| `thread_pool.active` | Gauge | pool_name | Thread pool saturation |
| `thread_pool.queue_size` | Gauge | pool_name | Backpressure indicator |
| `http.response.size` | Summary | http.route (template) | Response payload analysis |

**SLIs and alerting.** Don't compute SLIs in-process: no percentile, availability or "budget
remaining" gauges. Percentiles can't be averaged across pods, and an in-memory window resets on every
restart. Compute SLIs at query time from the request histogram (its 5xx share and its bucket counts)
and alert with multi-window burn rates. See `core/observability-patterns.md` §SLOs and Alerting.

---

## 3. Structured Logging

### 3a. Logback Configuration with JSON Encoder

```xml
<!-- src/main/resources/logback-spring.xml -->
<configuration>

    <!-- JSON output for production (Docker, K8s, log aggregators) -->
    <springProfile name="!local">
        <appender name="JSON_STDOUT" class="ch.qos.logback.core.ConsoleAppender">
            <encoder class="net.logstash.logback.encoder.LogstashEncoder">
                <!-- Add MDC fields as top-level JSON keys -->
                <includeMdcKeyName>tenant_id</includeMdcKeyName>
                <includeMdcKeyName>request_id</includeMdcKeyName>
                <includeMdcKeyName>user_id</includeMdcKeyName>
                <includeMdcKeyName>trace_id</includeMdcKeyName>
                <includeMdcKeyName>span_id</includeMdcKeyName>

                <!-- Static fields -->
                <customFields>
                    {"service":"${SERVICE_NAME:-order-service}","version":"${APP_VERSION:-0.0.1}"}</customFields>

                <!-- Shorten logger names for readability -->
                <shortenedLoggerNameLength>36</shortenedLoggerNameLength>

                <!-- Mask sensitive fields (logstash-logback-encoder 9: <decorator>; <jsonGeneratorDecorator> is ignored) -->
                <decorator class="com.example.app.logging.SensitiveDataMaskingDecorator"/>
            </encoder>
        </appender>

        <root level="INFO">
            <appender-ref ref="JSON_STDOUT"/>
        </root>
    </springProfile>

    <!-- Human-readable output for local development -->
    <springProfile name="local">
        <appender name="CONSOLE" class="ch.qos.logback.core.ConsoleAppender">
            <encoder>
                <pattern>%d{HH:mm:ss.SSS} %highlight(%-5level) [%thread] %cyan(%-40.40logger{39}) : [%X{tenant_id:-no-tenant}] [%X{request_id:-no-req}] %msg%n</pattern>
            </encoder>
        </appender>

        <root level="DEBUG">
            <appender-ref ref="CONSOLE"/>
        </root>
    </springProfile>

    <!-- Suppress noisy libraries -->
    <logger name="org.apache.kafka" level="WARN"/>
    <logger name="org.hibernate.SQL" level="DEBUG"/>
    <logger name="io.lettuce" level="WARN"/>
</configuration>
```

### 3b. MDC Correlation Filters

Two filters put the correlation fields into SLF4J MDC, so every log line carries them automatically:
- `CorrelationFilter` runs **before** Spring Security, so even a 401 is logged with its request ID. It
  sets `request_id`, `trace_id` and `span_id`.
- `TenantMdcFilter` runs **after** Spring Security. It sets `tenant_id` and `user_id` from the verified
  credential, never from a client header such as `X-Tenant-ID` or `X-User-ID`, which anyone can send.

```java
package com.example.app.filter;

import io.opentelemetry.api.trace.Span;
import io.opentelemetry.api.trace.SpanContext;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.MDC;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.UUID;
import java.util.regex.Pattern;

/**
 * Populates MDC with request_id and the trace IDs for every request.
 * Must run early in the filter chain (low order number), before Spring Security.
 */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE + 10)
public class CorrelationFilter extends OncePerRequestFilter {

    // Bounded charset and length: an inbound ID can't inject log lines or bloat every record
    private static final Pattern VALID_REQUEST_ID = Pattern.compile("[A-Za-z0-9._-]{8,128}");

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                     HttpServletResponse response,
                                     FilterChain filterChain)
            throws ServletException, IOException {

        try {
            // Request ID — accept a well-formed inbound ID, otherwise generate one
            String requestId = request.getHeader("X-Request-ID");
            if (requestId == null || !VALID_REQUEST_ID.matcher(requestId).matches()) {
                requestId = "req_" + UUID.randomUUID().toString().replace("-", "").substring(0, 16);
            }
            MDC.put("request_id", requestId);
            response.setHeader("X-Request-ID", requestId);

            // OTel trace/span IDs (if OTel agent is active, these are already in MDC;
            // this is a fallback for non-agent setups)
            SpanContext spanContext = Span.current().getSpanContext();
            if (spanContext.isValid()) {
                MDC.put("trace_id", spanContext.getTraceId());
                MDC.put("span_id", spanContext.getSpanId());
            }

            filterChain.doFilter(request, response);

        } finally {
            MDC.clear();
        }
    }
}
```

```java
package com.example.app.filter;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.MDC;
import org.springframework.boot.security.autoconfigure.web.servlet.SecurityFilterProperties; // Spring Boot 4
import org.springframework.core.annotation.Order;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

/**
 * Adds tenant_id and user_id to MDC from the VERIFIED credential. It runs just after Spring
 * Security's filter chain, once the token has been validated.
 */
@Component
@Order(SecurityFilterProperties.DEFAULT_FILTER_ORDER + 1) // just after Spring Security's filter chain
public class TenantMdcFilter extends OncePerRequestFilter {

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                     HttpServletResponse response,
                                     FilterChain filterChain)
            throws ServletException, IOException {

        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth instanceof JwtAuthenticationToken jwt) {
            String tenantId = jwt.getToken().getClaimAsString("tenant_id"); // claim name per your IdP
            if (tenantId != null) {
                MDC.put("tenant_id", tenantId);
            }
            MDC.put("user_id", jwt.getToken().getSubject());
        }
        try {
            filterChain.doFilter(request, response);
        } finally {
            MDC.remove("tenant_id");
            MDC.remove("user_id");
        }
    }
}
```

### 3c. Structured Logging in Application Code

```java
package com.example.app.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.util.UUID;

@Service
public class OrderService {

    private static final Logger log = LoggerFactory.getLogger(OrderService.class);

    private final OrderRepository orderRepository;
    private final RefundGateway refundGateway;

    public OrderService(OrderRepository orderRepository, RefundGateway refundGateway) {
        this.orderRepository = orderRepository;
        this.refundGateway = refundGateway;
    }

    public Order createOrder(String tenantId, CreateOrderRequest request) {
        // MDC fields (request_id, trace_id; tenant_id, user_id) are added by CorrelationFilter
        // and TenantMdcFilter.
        // They appear in every log line automatically — no need to repeat them.

        log.info("Creating order items={} user={}", request.getItems().size(), request.getUserId());

        // Use structured key-value pairs for additional context
        // logstash-logback-encoder picks up these as JSON fields via markers
        Order order = orderRepository.save(Order.create(tenantId, request));

        log.info("Order created orderId={} total={} paymentMethod={}",
                order.getId(), order.getTotal(), order.getPaymentMethod());

        return order;
    }

    public void processRefund(String tenantId, UUID orderId, BigDecimal amount) {
        // Add operation-scoped MDC fields
        try (MDC.MDCCloseable ignored = MDC.putCloseable("order_id", orderId.toString())) {
            log.info("Processing refund amount={}", amount);

            refundGateway.process(tenantId, orderId, amount);

            log.info("Refund completed amount={}", amount);
        }
        // MDC.putCloseable auto-removes "order_id" when try-block exits
    }
}
```

**JSON output in production:**

```json
{
  "@timestamp": "2024-01-15T10:30:00.123Z",
  "level": "INFO",
  "logger_name": "c.e.a.service.OrderService",
  "message": "Order created orderId=550e8400-e29b-41d4-a716-446655440000 total=99.99 paymentMethod=CARD",
  "service": "order-service",
  "version": "1.2.3",
  "tenant_id": "tenant_abc",
  "request_id": "req_a1b2c3d4e5f67890",
  "user_id": "user_xyz",
  "trace_id": "abc123def456789012345678abcdef01",
  "span_id": "1234567890abcdef",
  "thread_name": "http-nio-8080-exec-1"
}
```

### 3d. OTel Log Bridge

The OTel Java agent automatically bridges Logback/SLF4J logs to the OTel log pipeline. Logs are exported to the OTLP endpoint alongside traces and metrics, with trace context correlation.

When using the Java agent, this requires zero configuration. For non-agent setups:

```yaml
# application.yml
otel:
  logs:
    exporter: otlp
```

### 3e. Sensitive Data Masking

Redaction is enforced in the encoder, not remembered at each call site. The decorator is wired into
`LogstashEncoder` (3a), so every record at every level passes through it. DEBUG gets switched on in
production during incidents, and redaction has to hold then too. It matches **key names**, so a secret
passed as a `{}` argument inside the message text isn't caught. Never put secrets, request bodies or
whole DTOs into a log message, at any level. That also rules out `CommonsRequestLoggingFilter` with
`setIncludePayload(true)`.

```java
package com.example.app.logging;

import net.logstash.logback.decorate.JsonGeneratorDecorator;
import tools.jackson.core.JsonGenerator;
import tools.jackson.core.TokenStreamContext;
import tools.jackson.core.util.JsonGeneratorDelegate;

import java.util.regex.Pattern;

/**
 * Masks sensitive fields in JSON log output, by key name.
 * Any field whose name contains "password", "token", "secret", "authorization", "cookie",
 * "api_key", "session", "card", "ssn" and so on is replaced with "[REDACTED]".
 * logstash-logback-encoder 9.x writes with Jackson 3 (tools.jackson.core), like Spring Boot 4.
 */
public class SensitiveDataMaskingDecorator implements JsonGeneratorDecorator {

    private static final Pattern SENSITIVE_KEY = Pattern.compile(
            "(?i)(pass(word|wd)?|secret|token|authorization|cookie|api[-_]?key|session|card|cvv|iban"
                    + "|ssn|social_security|private[-_]?key|^pin$)");

    private static final Pattern EMAIL_PATTERN =
            Pattern.compile("([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\\.[a-zA-Z]{2,})");

    @Override
    public JsonGenerator decorate(JsonGenerator generator) {
        return new MaskingJsonGenerator(generator);
    }

    // JsonGeneratorDelegate forwards every JsonGenerator method; only string values are intercepted.
    // writeStringProperty(name, value) is final in JsonGenerator and goes through writeString, so it is covered.
    private static class MaskingJsonGenerator extends JsonGeneratorDelegate {

        MaskingJsonGenerator(JsonGenerator delegate) {
            // false: POJO values (structured arguments like kv("password", …), markers) are serialized through
            // THIS generator; with true the wrapped one writes them and nothing is masked
            super(delegate, false);
        }

        @Override
        public JsonGenerator writeString(String text) {
            if (text == null) {
                return super.writeString(text);
            }
            return super.writeString(isSensitiveField() ? "[REDACTED]" : maskEmail(text));
        }

        private boolean isSensitiveField() {
            TokenStreamContext ctx = streamWriteContext();
            String fieldName = ctx != null ? ctx.currentName() : null;
            return fieldName != null && SENSITIVE_KEY.matcher(fieldName).find();
        }

        private String maskEmail(String text) {
            return EMAIL_PATTERN.matcher(text).replaceAll("***@$2");
        }
    }
}
```

---

## 4. Full Setup

### 4a. application.yml — Complete OTel Configuration

```yaml
spring:
  application:
    name: order-service

# OTel configuration (used by opentelemetry-spring-boot-starter)
otel:
  exporter:
    otlp:
      endpoint: ${OTEL_EXPORTER_OTLP_ENDPOINT:http://localhost:4318}
      protocol: http/protobuf
  resource:
    attributes:
      service.name: ${spring.application.name}
      service.version: ${APP_VERSION:0.0.1}
      deployment.environment: ${DEPLOY_ENV:local}

# Actuator and metrics
management:
  endpoints:
    web:
      exposure:
        include: health,info,metrics,prometheus
  endpoint:
    health:
      show-details: when_authorized
      probes:
        enabled: true
  tracing:
    sampling:
      probability: ${OTEL_TRACES_SAMPLE_RATE:1.0}
  otlp:
    tracing:
      endpoint: ${OTEL_EXPORTER_OTLP_ENDPOINT:http://localhost:4318}/v1/traces
    metrics:
      export:
        url: ${OTEL_EXPORTER_OTLP_ENDPOINT:http://localhost:4318}/v1/metrics
        step: 30s
  metrics:
    tags:
      application: ${spring.application.name}
      environment: ${DEPLOY_ENV:local}
    distribution:
      # OTel semconv buckets (see 2a); the NFR latency threshold must be one of them
      slo:
        http.server.requests: 5ms, 10ms, 25ms, 50ms, 75ms, 100ms, 250ms, 500ms, 750ms, 1s, 2500ms, 5s, 7500ms, 10s
  prometheus:
    metrics:
      export:
        enabled: true

logging:
  level:
    root: INFO
    com.example.app: ${LOG_LEVEL:INFO}
    org.hibernate.SQL: DEBUG
    org.springframework.web: WARN
```

### 4b. OTel Bean Configuration (Non-Agent Setup)

```java
package com.example.app.config;

import io.opentelemetry.api.OpenTelemetry;
import io.opentelemetry.api.trace.Tracer;
import io.opentelemetry.api.metrics.Meter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * When using the opentelemetry-spring-boot-starter, OpenTelemetry, Tracer,
 * and Meter beans are auto-configured. This class shows explicit bean
 * definitions for cases where you need custom configuration.
 */
@Configuration
public class OtelConfig {

    /**
     * Tracer bean for programmatic span creation.
     * Inject this into services that need manual spans.
     */
    @Bean
    public Tracer tracer(OpenTelemetry openTelemetry) {
        return openTelemetry.getTracer("order-service", "1.0.0");
    }

    /**
     * Meter bean for programmatic metric creation.
     */
    @Bean
    public Meter meter(OpenTelemetry openTelemetry) {
        return openTelemetry.getMeter("order-service");
    }
}
```

### 4c. Docker Compose — Collector Stack

```yaml
# docker-compose.observability.yml
version: "3.9"

services:
  # --- Application ---
  order-service:
    build: .
    ports:
      - "8080:8080"
    environment:
      SPRING_PROFILES_ACTIVE: docker
      OTEL_EXPORTER_OTLP_ENDPOINT: http://otel-collector:4318
      OTEL_SERVICE_NAME: order-service
      DEPLOY_ENV: local
    depends_on:
      - otel-collector
      - postgres

  # --- OTel Collector ---
  otel-collector:
    image: otel/opentelemetry-collector-contrib:0.104.0
    ports:
      - "4317:4317"   # gRPC OTLP
      - "4318:4318"   # HTTP OTLP
      - "8888:8888"   # Collector metrics
    volumes:
      - ./config/otel-collector.yml:/etc/otelcol-contrib/config.yaml
    depends_on:
      - jaeger
      - prometheus

  # --- Jaeger (Traces) ---
  jaeger:
    image: jaegertracing/all-in-one:1.58
    ports:
      - "16686:16686"  # Jaeger UI
      - "14250:14250"  # gRPC
    environment:
      COLLECTOR_OTLP_ENABLED: "true"

  # --- Prometheus (Metrics) ---
  prometheus:
    image: prom/prometheus:v2.53.0
    ports:
      - "9090:9090"
    volumes:
      - ./config/prometheus.yml:/etc/prometheus/prometheus.yml

  # --- Grafana (Dashboards) ---
  grafana:
    image: grafana/grafana:11.1.0
    ports:
      - "3000:3000"
    environment:
      GF_SECURITY_ADMIN_PASSWORD: admin
    volumes:
      - ./config/grafana/provisioning:/etc/grafana/provisioning
      - grafana-data:/var/lib/grafana
    depends_on:
      - prometheus
      - jaeger

  # --- Database ---
  postgres:
    image: postgres:16-alpine
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: orders
      POSTGRES_USER: app
      POSTGRES_PASSWORD: secret
    volumes:
      - pg-data:/var/lib/postgresql/data

volumes:
  grafana-data:
  pg-data:
```

### 4d. OTel Collector Configuration

```yaml
# config/otel-collector.yml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 5s
    send_batch_size: 1024

  # Add resource attributes
  resource:
    attributes:
      - key: collector.version
        value: "0.104.0"
        action: upsert

  # Memory limiter to prevent OOM
  memory_limiter:
    check_interval: 5s
    limit_mib: 512
    spike_limit_mib: 128

exporters:
  # Traces -> Jaeger
  otlp/jaeger:
    endpoint: jaeger:4317
    tls:
      insecure: true

  # Metrics -> Prometheus
  prometheus:
    endpoint: 0.0.0.0:8889
    namespace: app

  # Logs -> stdout (replace with Loki/Elasticsearch in production)
  logging:
    verbosity: basic

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [otlp/jaeger]
    metrics:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [prometheus]
    logs:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [logging]
```

---

## 5. Health Check Pattern

```java
package com.example.app.health;

import org.springframework.boot.health.contributor.Health;          // Spring Boot 4 package
import org.springframework.boot.health.contributor.HealthIndicator;
import org.springframework.stereotype.Component;

import javax.sql.DataSource;
import java.sql.Connection;

/**
 * Custom health indicator that checks database connectivity.
 * Spring Boot auto-registers DataSourceHealthIndicator, but this shows
 * the pattern for custom dependencies (Redis, external APIs, etc.).
 */
@Component("database")
public class DatabaseHealthIndicator implements HealthIndicator {

    private final DataSource dataSource;

    public DatabaseHealthIndicator(DataSource dataSource) {
        this.dataSource = dataSource;
    }

    @Override
    public Health health() {
        try (Connection conn = dataSource.getConnection()) {
            conn.createStatement().execute("SELECT 1");
            return Health.up()
                    .withDetail("database", "postgresql")
                    .withDetail("status", "reachable")
                    .build();
        } catch (Exception e) {
            return Health.down()
                    .withDetail("database", "postgresql")
                    .withDetail("error", e.getMessage())
                    .build();
        }
    }
}
```

---

## Critical Rules

- `tenant_id` on every log line and trace span, and on **no metric** (at most a bounded `tenant.tier`). See `observability-patterns.md`.
- Use `@WithSpan` for business methods; use programmatic Tracer for loops and conditional logic
- Always record exceptions on spans: `span.recordException(e)` + `span.setStatus(StatusCode.ERROR, ...)`
- Propagate OTel context through `@Async` and `CompletableFuture` with task decorators
- MDC correlation fields are set once by the filters and appear on every log line. `request_id` (validated inbound, or generated) and the trace IDs come from `CorrelationFilter`. `tenant_id` and `user_id` come from the verified credential via `TenantMdcFilter`, never from `X-Tenant-ID`.
- JSON logs in production, human-readable in local — use `logback-spring.xml` with Spring profiles
- Never log sensitive data. `SensitiveDataMaskingDecorator` redacts by key name at every level. Never log request or response bodies.
- Prefer the Java agent for auto-instrumentation — it covers JDBC, Redis, HTTP clients, Kafka, gRPC with zero code
- HTTP server metrics: one `http.server.request.duration` histogram (from the agent or starter, or Micrometer's `http.server.requests`), with `http.route` as the route template. No request counter.
- Metrics at every boundary — HTTP, service, repository, external calls — with bounded tags only
- `@Timed` for method-level latency; `Counter` for events; `Gauge` for pool/queue sizes
- SLIs come from the request histogram at query time, and alerts use multi-window burn rates. No in-process SLA gauges (see `observability-patterns.md` §SLOs and Alerting).
