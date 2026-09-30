---
skill: crud-service-java
description: Spring Boot service layer archetype — @Service, @Transactional, cache-aside, audit logging, custom exceptions, business logic, tenant isolation
version: "1.0"
tags:
  - java
  - spring-boot
  - service
  - crud
  - archetype
  - backend
---

# CRUD Service Archetype (Spring Boot)

Complete, production-ready Spring Boot service layer template. Every generated service MUST follow this pattern.

## Service Interface

```java
package com.example.app.service;

import com.example.app.model.dto.*;
import com.example.app.model.entity.Widget;
import com.example.app.model.entity.WidgetStatus;
import org.springframework.data.domain.ScrollPosition;
import org.springframework.data.domain.Sort;
import org.springframework.data.domain.Window;

import java.util.UUID;

/**
 * Business operations for widgets.
 * Rule: Keep interfaces focused (3-7 methods). Split if exceeding 7.
 */
public interface WidgetService {
    Widget create(CreateWidgetRequest request, UUID tenantId, UUID userId);
    Widget findById(UUID id, UUID tenantId);
    Widget update(UUID id, UpdateWidgetRequest request, UUID tenantId, UUID userId);
    void delete(UUID id, UUID tenantId, UUID userId);
    /** Cursor (keyset) list: one window of at most `limit` rows after `position`. No offset, no COUNT. */
    Window<Widget> findAll(UUID tenantId, WidgetStatus status, ScrollPosition position, Sort sort, int limit);
}
```

## Service Implementation

```java
package com.example.app.service;

import com.example.app.common.Sanitizer;
import com.example.app.exception.*;
import com.example.app.model.dto.*;
import com.example.app.model.entity.Widget;
import com.example.app.model.entity.WidgetStatus;
import com.example.app.repository.WidgetRepository;
import com.example.app.repository.WidgetSpecs;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.data.domain.ScrollPosition;
import org.springframework.data.domain.Sort;
import org.springframework.data.domain.Window;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.UUID;

@Service
@Transactional(readOnly = true) // Default: read-only for query methods
public class WidgetServiceImpl implements WidgetService {

    private static final Logger log = LoggerFactory.getLogger(WidgetServiceImpl.class);

    private final WidgetRepository repository;
    private final AuditService auditService;

    // Constructor injection — the only acceptable DI pattern
    public WidgetServiceImpl(WidgetRepository repository, AuditService auditService) {
        this.repository = repository;
        this.auditService = auditService;
    }

    @Override
    @Transactional
    public Widget create(CreateWidgetRequest request, UUID tenantId, UUID userId) {
        var requestId = MDC.get("requestId");
        log.info("Creating widget, name={}, tenant={}, requestId={}", request.name(), tenantId, requestId);

        // 1. Sanitize input
        var sanitizedName = Sanitizer.clean(request.name());
        var sanitizedDesc = Sanitizer.clean(request.description());

        // 2. Check business rules (e.g., unique name per tenant)
        if (repository.existsByTenantIdAndNameIgnoreCase(tenantId, sanitizedName)) {
            throw new ConflictException("widget", "A widget with name '" + sanitizedName + "' already exists");
        }

        // 3. Build entity
        var now = Instant.now();
        var widget = new Widget();
        widget.setTenantId(tenantId);
        widget.setName(sanitizedName);
        widget.setDescription(sanitizedDesc);
        widget.setStatus(WidgetStatus.ACTIVE);
        widget.setCreatedAt(now);
        widget.setUpdatedAt(now);
        widget.setCreatedBy(userId);
        widget.setUpdatedBy(userId);

        // 4. Persist
        widget = repository.save(widget);

        // 5. Audit log
        auditService.log("widget.created", widget.getId(), tenantId, userId, widget);

        log.info("Widget created, id={}, tenant={}, requestId={}", widget.getId(), tenantId, requestId);
        return widget;
    }

    @Override
    @Cacheable(value = "widgets", key = "#tenantId + ':' + #id")
    public Widget findById(UUID id, UUID tenantId) {
        var requestId = MDC.get("requestId");
        log.debug("Fetching widget, id={}, tenant={}, requestId={}", id, tenantId, requestId);

        // Missing, soft-deleted or another tenant's: all 404 NOT_FOUND
        return repository.findByIdAndTenantId(id, tenantId)
            .orElseThrow(() -> new ResourceNotFoundException("Widget", id.toString()));
    }

    @Override
    @Transactional
    @CacheEvict(value = "widgets", key = "#tenantId + ':' + #id")
    public Widget update(UUID id, UpdateWidgetRequest request, UUID tenantId, UUID userId) {
        var requestId = MDC.get("requestId");
        log.info("Updating widget, id={}, version={}, tenant={}, requestId={}",
            id, request.version(), tenantId, requestId);

        // 1. Fetch existing (tenant-scoped)
        var existing = repository.findByIdAndTenantId(id, tenantId)
            .orElseThrow(() -> new ResourceNotFoundException("Widget", id.toString()));

        // 2. Optimistic lock check — client must send current version
        if (!existing.getVersion().equals(request.version())) {
            throw new ConflictException("widget",
                "Version mismatch: expected " + existing.getVersion() + ", got " + request.version() + ". Reload and retry.");
        }

        // 3. Sanitize and apply changes
        existing.setName(Sanitizer.clean(request.name()));
        existing.setDescription(Sanitizer.clean(request.description()));
        existing.setUpdatedAt(Instant.now());
        existing.setUpdatedBy(userId);

        // 4. Persist (JPA @Version auto-increments and throws OptimisticLockingFailureException on conflict)
        existing = repository.save(existing);

        // 5. Audit log
        auditService.log("widget.updated", existing.getId(), tenantId, userId, request);

        log.info("Widget updated, id={}, newVersion={}, requestId={}", id, existing.getVersion(), requestId);
        return existing;
    }

    @Override
    @Transactional
    @CacheEvict(value = "widgets", key = "#tenantId + ':' + #id")
    public void delete(UUID id, UUID tenantId, UUID userId) {
        var requestId = MDC.get("requestId");
        log.info("Deleting widget, id={}, tenant={}, requestId={}", id, tenantId, requestId);

        // 1. Verify exists and belongs to tenant
        var widget = repository.findByIdAndTenantId(id, tenantId)
            .orElseThrow(() -> new ResourceNotFoundException("Widget", id.toString()));

        // 2. Soft delete (via @SQLDelete on entity — sets deleted_at)
        repository.delete(widget);

        // 3. Audit log
        auditService.log("widget.deleted", id, tenantId, userId, null);

        log.info("Widget deleted, id={}, tenant={}, requestId={}", id, tenantId, requestId);
    }

    @Override
    public Window<Widget> findAll(UUID tenantId, WidgetStatus status, ScrollPosition position, Sort sort, int limit) {
        var requestId = MDC.get("requestId");
        log.debug("Listing widgets, tenant={}, status={}, limit={}, requestId={}",
            tenantId, status, limit, requestId);

        // Keyset scroll: WHERE (sort key, id) after the cursor ORDER BY sort LIMIT limit+1 — no OFFSET, no COUNT.
        // `sort` ends with id (the controller adds it) so every position is unique.
        var spec = WidgetSpecs.belongsToTenant(tenantId).and(WidgetSpecs.hasStatus(status));
        Window<Widget> result = repository.findBy(spec, q -> q.sortBy(sort).limit(limit).scroll(position));

        log.info("Listed widgets, tenant={}, resultCount={}, hasNext={}, requestId={}",
            tenantId, result.size(), result.hasNext(), requestId);
        return result;
    }
}
```

## Transaction Support for Multi-Step Operations

```java
@Transactional
public Widget createWithComponents(CreateWidgetWithComponentsRequest request, UUID tenantId, UUID userId) {
    var requestId = MDC.get("requestId");
    log.info("Creating widget with components, tenant={}, requestId={}", tenantId, requestId);

    // Step 1: Create parent widget
    var widget = new Widget();
    widget.setTenantId(tenantId);
    widget.setName(Sanitizer.clean(request.name()));
    widget.setDescription(Sanitizer.clean(request.description()));
    widget.setStatus(WidgetStatus.ACTIVE);
    widget.setCreatedAt(Instant.now());
    widget.setUpdatedAt(Instant.now());
    widget.setCreatedBy(userId);
    widget.setUpdatedBy(userId);
    widget = repository.save(widget);

    // Step 2: Create child components — all within same transaction
    // If any component fails, the entire transaction (including parent) rolls back
    for (var compRequest : request.components()) {
        var component = new WidgetComponent();
        component.setWidgetId(widget.getId());
        component.setTenantId(tenantId);
        component.setName(Sanitizer.clean(compRequest.name()));
        component.setCreatedBy(userId);
        componentRepository.save(component);
    }

    auditService.log("widget.created_with_components", widget.getId(), tenantId, userId, request);
    return widget;
}
```

## Audit Service

```java
package com.example.app.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.UUID;

@Service
public class AuditService {

    private static final Logger log = LoggerFactory.getLogger(AuditService.class);
    private final AuditEntryRepository auditRepository;
    private final ObjectMapper objectMapper;

    public AuditService(AuditEntryRepository auditRepository, ObjectMapper objectMapper) {
        this.auditRepository = auditRepository;
        this.objectMapper = objectMapper;
    }

    /**
     * Record an audit entry. Fire-and-forget — must never block the business operation.
     * In production, consider publishing to a message queue instead of direct DB write.
     */
    @Async
    public void log(String action, UUID entityId, UUID tenantId, UUID actorId, Object changes) {
        try {
            var entry = new AuditEntry();
            entry.setAction(action);
            entry.setEntityId(entityId);
            entry.setTenantId(tenantId);
            entry.setActorId(actorId);
            entry.setTimestamp(Instant.now());
            if (changes != null) {
                entry.setChanges(objectMapper.writeValueAsString(changes));
            }
            auditRepository.save(entry);
        } catch (Exception e) {
            // Audit failure must never propagate to the caller
            log.error("Audit log failed: action={}, entityId={}, error={}", action, entityId, e.getMessage(), e);
        }
    }
}
```

## Cache Configuration

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

@Configuration
@EnableCaching
public class CacheConfig {

    @Bean
    public RedisCacheManager cacheManager(RedisConnectionFactory connectionFactory) {
        var defaultConfig = RedisCacheConfiguration.defaultCacheConfig()
            .entryTtl(Duration.ofMinutes(5))
            .disableCachingNullValues()
            .serializeValuesWith(
                RedisSerializationContext.SerializationPair.fromSerializer(
                    new GenericJackson2JsonRedisSerializer()));

        // Per-cache TTL overrides
        var widgetConfig = defaultConfig.entryTtl(Duration.ofMinutes(10));

        return RedisCacheManager.builder(connectionFactory)
            .cacheDefaults(defaultConfig)
            .withCacheConfiguration("widgets", widgetConfig)
            .build();
    }
}
```

## Custom Exception Hierarchy

The sealed `DomainException` hierarchy is defined once, in `error-handling-java.md`
(`com.example.app.exception`); `GlobalExceptionHandler` turns it into the error envelope from
`api/response-envelope.md`. The service throws:

```java
// new ResourceNotFoundException("Widget", id.toString())  → 404 NOT_FOUND (also another tenant's widget)
// new ConflictException("widget", "…")                    → 409 CONFLICT (duplicate, stale version)
// new BusinessRuleException("widget", "…")                → 422 BUSINESS_RULE_VIOLATION
// new ValidationException("name", "reserved", "…")        → 400 VALIDATION_FAILED, details[] entry
// new UpstreamServiceException("payment-service", e)      → 503 UNAVAILABLE (retryable, Retry-After)
//
// The reason/rule text is shown to users as-is: write it for users, never pass an exception's
// message, SQL or a constraint name.
```

## Input Validation Beyond Annotations

```java
/**
 * For validation rules that Jakarta annotations cannot express,
 * use a validation method in the service layer.
 */
private void validateCreateRequest(CreateWidgetRequest request, UUID tenantId) {
    // Cross-field validation
    if (request.name() != null && request.name().equalsIgnoreCase("default")) {
        throw new BusinessRuleException("widget", "Name 'default' is reserved");
    }

    // Business rule: max 50 widgets per tenant
    long count = repository.countByTenantId(tenantId);
    if (count >= 50) {
        throw new BusinessRuleException("widget", "Maximum widget limit (50) reached for tenant");
    }
}
```

## Event Publishing (Optional)

```java
package com.example.app.event;

import java.time.Instant;
import java.util.UUID;

// Domain events for cross-service communication
public sealed interface WidgetEvent {
    UUID widgetId();
    UUID tenantId();
    Instant occurredAt();

    record Created(UUID widgetId, UUID tenantId, String name, Instant occurredAt) implements WidgetEvent {}
    record Updated(UUID widgetId, UUID tenantId, Instant occurredAt) implements WidgetEvent {}
    record Deleted(UUID widgetId, UUID tenantId, Instant occurredAt) implements WidgetEvent {}
}

// In service:
@Transactional
public Widget create(CreateWidgetRequest request, UUID tenantId, UUID userId) {
    // ... create widget ...

    // Publish domain event — listeners run in the same transaction via @TransactionalEventListener
    applicationEventPublisher.publishEvent(
        new WidgetEvent.Created(widget.getId(), tenantId, widget.getName(), Instant.now())
    );

    return widget;
}
```

## Critical Rules

- Every query and mutation MUST be scoped by `tenantId` — no cross-tenant data leaks.
- Every mutation MUST produce an audit log entry via `AuditService`.
- `@Transactional` goes on service methods, NEVER on controllers or repositories.
- `@Transactional(readOnly = true)` at class level, `@Transactional` on write methods.
- Cache invalidation MUST happen on every write (`@CacheEvict` on update/delete).
- Cache reads use `@Cacheable` with tenant-scoped keys: `tenantId + ':' + entityId`.
- Optimistic locking via JPA `@Version` — client sends version, service validates before save.
- Input sanitization (HTML stripping, trimming) MUST happen in the service layer before persistence.
- Validation annotations handle format rules; service methods handle business rules.
- Custom exceptions use sealed hierarchy — `DomainException` -> `ResourceNotFoundException`, etc.
- Constructor injection ONLY — no `@Autowired` fields.
- Every service method MUST read `requestId` from MDC and include it in log lines.
- Audit logging is async (`@Async`) — audit failures must NEVER block business operations.
- Max 30 lines of logic per method — extract private helpers for complex workflows.
- Never return unbounded collections — list operations take a cursor `ScrollPosition` + `limit` and return a keyset `Window` (no offset pages, no `Page<T>`).
