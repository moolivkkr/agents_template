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
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;

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
    Page<Widget> findAll(UUID tenantId, WidgetStatus status, Pageable pageable);
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
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
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

        return repository.findByIdAndTenantId(id, tenantId)
            .orElseThrow(() -> new ResourceNotFoundException("widget", id.toString()));
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
            .orElseThrow(() -> new ResourceNotFoundException("widget", id.toString()));

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
            .orElseThrow(() -> new ResourceNotFoundException("widget", id.toString()));

        // 2. Soft delete (via @SQLDelete on entity — sets deleted_at)
        repository.delete(widget);

        // 3. Audit log
        auditService.log("widget.deleted", id, tenantId, userId, null);

        log.info("Widget deleted, id={}, tenant={}, requestId={}", id, tenantId, requestId);
    }

    @Override
    public Page<Widget> findAll(UUID tenantId, WidgetStatus status, Pageable pageable) {
        var requestId = MDC.get("requestId");
        log.debug("Listing widgets, tenant={}, status={}, page={}, requestId={}",
            tenantId, status, pageable.getPageNumber(), requestId);

        Page<Widget> result;
        if (status != null) {
            result = repository.findByTenantIdAndStatus(tenantId, status, pageable);
        } else {
            result = repository.findByTenantId(tenantId, pageable);
        }

        log.info("Listed widgets, tenant={}, resultCount={}, total={}, requestId={}",
            tenantId, result.getNumberOfElements(), result.getTotalElements(), requestId);
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

```java
package com.example.app.exception;

// Base class — all domain exceptions extend this
public abstract sealed class DomainException extends RuntimeException
    permits ResourceNotFoundException, ConflictException, BusinessRuleException, UpstreamServiceException {

    private final String resource;

    protected DomainException(String message, String resource) {
        super(message);
        this.resource = resource;
    }

    protected DomainException(String message, String resource, Throwable cause) {
        super(message, cause);
        this.resource = resource;
    }

    public String getResource() { return resource; }
}

// 404 — resource not found or soft-deleted
public final class ResourceNotFoundException extends DomainException {
    private final String identifier;

    public ResourceNotFoundException(String resource, String identifier) {
        super(resource + " '" + identifier + "' not found", resource);
        this.identifier = identifier;
    }

    public String getIdentifier() { return identifier; }
}

// 409 — duplicate, version mismatch, state conflict
public final class ConflictException extends DomainException {
    public ConflictException(String resource, String reason) {
        super(resource + " conflict: " + reason, resource);
    }
}

// 422 — business rule violation that validation annotations cannot express
public final class BusinessRuleException extends DomainException {
    public BusinessRuleException(String resource, String rule) {
        super("Business rule violated: " + rule, resource);
    }
}

// 502 — upstream service failure
public final class UpstreamServiceException extends DomainException {
    public UpstreamServiceException(String service, Throwable cause) {
        super("Upstream service '" + service + "' is unavailable", service, cause);
    }
}
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
- Never return unbounded collections — always use `Pageable` for list operations.
