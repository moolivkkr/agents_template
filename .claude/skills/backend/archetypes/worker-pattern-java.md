---
skill: worker-pattern-java
description: Java/Spring Boot worker archetype — @Scheduled, CompletableFuture, Spring Cloud Stream, ShedLock, graceful shutdown, structured logging
version: "1.0"
tags:
  - java
  - spring-boot
  - worker
  - scheduled
  - background-job
  - archetype
  - backend
---

# Worker / Background Job Pattern — Java (Spring Boot)

> **Canonical reference**: This is the Java counterpart to `worker-pattern.md` (language-neutral). Read that first for concepts and contracts.

Spring Boot workers use `@Scheduled` with ShedLock for cron jobs, `ThreadPoolTaskExecutor` for async processing, and Spring Cloud Stream or Spring AMQP for message-driven consumers.

## Job Domain Model

```java
package com.example.app.worker.model;

import java.time.Instant;
import java.util.Map;
import java.util.UUID;

public record Job(
    String id,
    String type,
    Map<String, Object> payload,
    UUID tenantId,
    int attempt,
    int maxRetries,
    Instant createdAt,
    String correlationId
) {
    public Job withAttempt(int newAttempt) {
        return new Job(id, type, payload, tenantId, newAttempt, maxRetries, createdAt, correlationId);
    }
}
```

## Job Handler Interface

```java
package com.example.app.worker;

public interface JobHandler {
    /** The job type this handler processes, e.g. "email.send". */
    String type();

    /** Process a job. Must be idempotent. */
    void handle(Job job) throws Exception;
}
```

## Worker Service with Thread Pool

```java
package com.example.app.worker;

import com.example.app.worker.model.Job;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.stereotype.Service;

import jakarta.annotation.PreDestroy;
import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

@Service
public class WorkerService {

    private static final Logger log = LoggerFactory.getLogger(WorkerService.class);

    private final Map<String, JobHandler> handlers = new ConcurrentHashMap<>();
    private final QueueClient queueClient;
    private final IdempotencyStore idempotencyStore;
    private final ExecutorService executor;
    private final int concurrency;
    private final Duration jobTimeout;
    private final int maxRetries;

    private final AtomicInteger inFlight = new AtomicInteger(0);
    private final AtomicReference<Instant> lastJobAt = new AtomicReference<>();
    private volatile boolean running = true;

    public WorkerService(
            QueueClient queueClient,
            IdempotencyStore idempotencyStore,
            WorkerConfig config,
            java.util.List<JobHandler> handlerList) {

        this.queueClient = queueClient;
        this.idempotencyStore = idempotencyStore;
        this.concurrency = config.getConcurrency();
        this.jobTimeout = config.getJobTimeout();
        this.maxRetries = config.getMaxRetries();

        this.executor = Executors.newFixedThreadPool(concurrency, r -> {
            Thread t = new Thread(r);
            t.setName("worker-" + t.getId());
            t.setDaemon(true);
            return t;
        });

        // Register all handlers by type
        handlerList.forEach(h -> handlers.put(h.type(), h));
    }

    /** Start consuming jobs. Call from ApplicationRunner. */
    public void start() {
        log.info("worker.starting, concurrency={}, handlers={}", concurrency, handlers.size());

        for (int i = 0; i < concurrency; i++) {
            final String consumerId = "consumer-" + i;
            executor.submit(() -> consumeLoop(consumerId));
        }
    }

    private void consumeLoop(String consumerId) {
        log.info("consumer.started, consumer={}", consumerId);

        while (running) {
            try {
                Job job = queueClient.receive(Duration.ofSeconds(30));
                if (job == null) continue;

                processJob(consumerId, job);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                break;
            } catch (Exception e) {
                log.error("consumer.receive_error, consumer={}", consumerId, e);
                sleep(Duration.ofSeconds(1));
            }
        }

        log.info("consumer.stopped, consumer={}", consumerId);
    }

    private void processJob(String consumerId, Job job) {
        MDC.put("jobId", job.id());
        MDC.put("jobType", job.type());
        MDC.put("tenantId", job.tenantId().toString());
        MDC.put("attempt", String.valueOf(job.attempt()));

        inFlight.incrementAndGet();
        Instant start = Instant.now();

        try {
            // Idempotency check
            if (idempotencyStore.isProcessed(job.id())) {
                log.info("job.duplicate_skipped");
                queueClient.ack(job);
                return;
            }

            // Find handler
            JobHandler handler = handlers.get(job.type());
            if (handler == null) {
                log.error("job.unknown_type");
                queueClient.sendToDlq(job, "unknown job type: " + job.type());
                return;
            }

            // Execute with timeout
            CompletableFuture<Void> future = CompletableFuture.runAsync(
                () -> {
                    try { handler.handle(job); }
                    catch (Exception e) { throw new CompletionException(e); }
                },
                executor
            );

            future.get(jobTimeout.toMillis(), TimeUnit.MILLISECONDS);

            // Success
            idempotencyStore.markProcessed(job.id(), Duration.ofHours(24));
            queueClient.ack(job);
            lastJobAt.set(Instant.now());

            Duration elapsed = Duration.between(start, Instant.now());
            log.info("job.completed, duration={}ms", elapsed.toMillis());

        } catch (TimeoutException e) {
            log.error("job.timeout");
            handleRetryOrDlq(job, "timeout after " + jobTimeout);
        } catch (Exception e) {
            Throwable cause = (e instanceof ExecutionException) ? e.getCause() : e;
            log.error("job.failed", cause);
            handleRetryOrDlq(job, cause.getMessage());
        } finally {
            inFlight.decrementAndGet();
            MDC.clear();
        }
    }

    private void handleRetryOrDlq(Job job, String reason) {
        if (job.attempt() >= maxRetries) {
            queueClient.sendToDlq(job, reason);
            log.warn("job.dead_lettered");
        } else {
            Duration delay = exponentialBackoff(job.attempt());
            queueClient.nack(job, delay);
        }
    }

    static Duration exponentialBackoff(int attempt) {
        long baseMs = 1000;
        long maxMs = 300_000; // 5 minutes
        long delay = (long) (baseMs * Math.pow(2, attempt - 1));
        delay = Math.min(delay, maxMs);
        // Full jitter
        delay = ThreadLocalRandom.current().nextLong(0, delay + 1);
        return Duration.ofMillis(delay);
    }

    @PreDestroy
    public void shutdown() {
        log.info("worker.shutdown_requested");
        running = false;

        executor.shutdown();
        try {
            if (!executor.awaitTermination(30, TimeUnit.SECONDS)) {
                log.warn("worker.shutdown_timeout, forcing");
                executor.shutdownNow();
            }
        } catch (InterruptedException e) {
            executor.shutdownNow();
            Thread.currentThread().interrupt();
        }

        log.info("worker.shutdown_complete");
    }

    private void sleep(Duration duration) {
        try { Thread.sleep(duration.toMillis()); }
        catch (InterruptedException e) { Thread.currentThread().interrupt(); }
    }
}
```

## Scheduled Jobs with ShedLock (Leader Election)

```java
package com.example.app.worker.cron;

import net.javacrumbs.shedlock.core.SchedulerLock;
import net.javacrumbs.shedlock.spring.annotation.EnableSchedulerLock;
import net.javacrumbs.shedlock.spring.annotation.SchedulerLock;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
@EnableScheduling
@EnableSchedulerLock(defaultLockAtMostFor = "PT5M")
public class ScheduledTasks {

    private static final Logger log = LoggerFactory.getLogger(ScheduledTasks.class);

    private final SessionCleanupService sessionCleanup;
    private final ReportService reportService;

    public ScheduledTasks(SessionCleanupService sessionCleanup, ReportService reportService) {
        this.sessionCleanup = sessionCleanup;
        this.reportService = reportService;
    }

    @Scheduled(fixedRate = 900_000) // Every 15 minutes
    @SchedulerLock(name = "cleanupExpiredSessions", lockAtMostFor = "PT14M", lockAtLeastFor = "PT5M")
    public void cleanupExpiredSessions() {
        log.info("cron.started, job=cleanupExpiredSessions");
        try {
            int cleaned = sessionCleanup.cleanExpired();
            log.info("cron.completed, job=cleanupExpiredSessions, cleaned={}", cleaned);
        } catch (Exception e) {
            log.error("cron.failed, job=cleanupExpiredSessions", e);
        }
    }

    @Scheduled(cron = "0 0 2 * * *") // 2:00 AM UTC daily
    @SchedulerLock(name = "generateDailyReport", lockAtMostFor = "PT30M", lockAtLeastFor = "PT5M")
    public void generateDailyReport() {
        log.info("cron.started, job=generateDailyReport");
        try {
            reportService.generateDaily();
            log.info("cron.completed, job=generateDailyReport");
        } catch (Exception e) {
            log.error("cron.failed, job=generateDailyReport", e);
        }
    }
}
```

```java
// ShedLock configuration — uses the same database
package com.example.app.config;

import net.javacrumbs.shedlock.core.LockProvider;
import net.javacrumbs.shedlock.provider.jdbctemplate.JdbcTemplateLockProvider;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import javax.sql.DataSource;

@Configuration
public class ShedLockConfig {

    @Bean
    public LockProvider lockProvider(DataSource dataSource) {
        return new JdbcTemplateLockProvider(
            JdbcTemplateLockProvider.Configuration.builder()
                .withJdbcTemplate(new org.springframework.jdbc.core.JdbcTemplate(dataSource))
                .usingDbTime()
                .build()
        );
    }
}

// Required migration:
// CREATE TABLE shedlock (
//     name       VARCHAR(64) NOT NULL PRIMARY KEY,
//     lock_until TIMESTAMP NOT NULL,
//     locked_at  TIMESTAMP NOT NULL,
//     locked_by  VARCHAR(255) NOT NULL
// );
```

## Spring Cloud Stream Consumer (Kafka/RabbitMQ)

```java
package com.example.app.worker.stream;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.messaging.Message;

import java.util.function.Consumer;

@Configuration
public class StreamConsumers {

    private static final Logger log = LoggerFactory.getLogger(StreamConsumers.class);

    private final OrderEventHandler orderEventHandler;

    public StreamConsumers(OrderEventHandler orderEventHandler) {
        this.orderEventHandler = orderEventHandler;
    }

    @Bean
    public Consumer<Message<OrderEvent>> orderCreated() {
        return message -> {
            OrderEvent event = message.getPayload();
            String eventId = message.getHeaders().getId().toString();

            MDC.put("eventId", eventId);
            MDC.put("tenantId", event.tenantId().toString());

            try {
                log.info("event.received, type=order.created, orderId={}", event.orderId());
                orderEventHandler.handleOrderCreated(event);
                log.info("event.processed, type=order.created");
            } catch (Exception e) {
                log.error("event.failed, type=order.created", e);
                throw e; // Spring Cloud Stream handles retry via binder config
            } finally {
                MDC.clear();
            }
        };
    }
}
```

## Health Check

```java
package com.example.app.worker;

import org.springframework.boot.actuate.health.Health;
import org.springframework.boot.actuate.health.HealthIndicator;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.time.Instant;

@Component
public class WorkerHealthIndicator implements HealthIndicator {

    private final WorkerService workerService;

    public WorkerHealthIndicator(WorkerService workerService) {
        this.workerService = workerService;
    }

    @Override
    public Health health() {
        var builder = Health.up();

        // Queue connection
        if (!workerService.isQueueConnected()) {
            return Health.down().withDetail("queue", "disconnected").build();
        }
        builder.withDetail("queue", "connected");

        // Last job recency
        Instant lastJob = workerService.getLastJobAt();
        if (lastJob != null) {
            long agoSeconds = Duration.between(lastJob, Instant.now()).getSeconds();
            builder.withDetail("lastJobSecondsAgo", agoSeconds);
            if (agoSeconds > 300) {
                builder = Health.status("DEGRADED");
            }
        }

        // In-flight
        builder.withDetail("inFlight", workerService.getInFlight());
        builder.withDetail("maxConcurrency", workerService.getConcurrency());

        return builder.build();
    }
}
```

## Application Runner

```java
package com.example.app;

import com.example.app.worker.WorkerService;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.stereotype.Component;

@Component
public class WorkerRunner implements ApplicationRunner {

    private final WorkerService workerService;

    public WorkerRunner(WorkerService workerService) {
        this.workerService = workerService;
    }

    @Override
    public void run(ApplicationArguments args) {
        workerService.start();
    }
}
```

## Critical Rules

- Use `@PreDestroy` for graceful shutdown — Spring calls it before context closes
- Use `ShedLock` for leader election on `@Scheduled` jobs — prevents duplicate execution across replicas
- Set `lockAtLeastFor` in ShedLock to prevent rapid re-execution if the job finishes early
- Use `MDC` for structured logging context — clear it in `finally` blocks
- Use `CompletableFuture.get(timeout)` to enforce job timeouts — never let a job run forever
- Thread pool threads MUST be daemon threads — prevents the JVM from hanging on shutdown
- Use `executor.awaitTermination()` with a timeout — force shutdown if drain takes too long
- Every handler MUST be stateless — no instance-level mutable state shared across jobs
- Spring Cloud Stream `Consumer<Message<T>>` beans auto-bind to Kafka/RabbitMQ topics
- Always set `task_acks_late` equivalent: acknowledge AFTER processing, not before
