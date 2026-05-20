---
skill: crud-repository-java
description: Spring Data JPA repository archetype — JpaRepository, custom queries, Specification API, pagination, soft delete, optimistic locking, multi-tenant filtering
version: "1.0"
tags:
  - java
  - spring-boot
  - jpa
  - repository
  - archetype
  - backend
---

# CRUD Repository Archetype (Spring Data JPA)

Complete, production-ready Spring Data JPA repository template. Every generated repository MUST follow this pattern.

## Entity Base Class

```java
package com.example.app.model.entity;

import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;

 * Base entity with audit fields, soft delete, and optimistic locking.
 * All domain entities MUST extend this class.
@MappedSuperclass
public abstract class AuditableEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(nullable = false, updatable = false)
    private UUID tenantId;

    @Column(nullable = false, updatable = false)
    private Instant createdAt;

    @Column(nullable = false)
    private Instant updatedAt;

    private Instant deletedAt;

    @Column(nullable = false, updatable = false)
    private UUID createdBy;

    @Column(nullable = false)
    private UUID updatedBy;

    @Version
    private Integer version;

    @PrePersist
    protected void onCreate() {
        var now = Instant.now();
        if (this.createdAt == null) this.createdAt = now;
        if (this.updatedAt == null) this.updatedAt = now;
    }

    @PreUpdate
    protected void onUpdate() {
        this.updatedAt = Instant.now();
    }

    // Getters and setters
    public UUID getId() { return id; }
    public void setId(UUID id) { this.id = id; }
    public UUID getTenantId() { return tenantId; }
    public void setTenantId(UUID tenantId) { this.tenantId = tenantId; }
    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }
    public Instant getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(Instant updatedAt) { this.updatedAt = updatedAt; }
    public Instant getDeletedAt() { return deletedAt; }
    public void setDeletedAt(Instant deletedAt) { this.deletedAt = deletedAt; }
    public UUID getCreatedBy() { return createdBy; }
    public void setCreatedBy(UUID createdBy) { this.createdBy = createdBy; }
    public UUID getUpdatedBy() { return updatedBy; }
    public void setUpdatedBy(UUID updatedBy) { this.updatedBy = updatedBy; }
    public Integer getVersion() { return version; }
    public void setVersion(Integer version) { this.version = version; }
}
```

## Widget Entity

```java
package com.example.app.model.entity;

import jakarta.persistence.*;
import org.hibernate.annotations.SQLDelete;
import org.hibernate.annotations.SQLRestriction;

@Entity
@Table(name = "widgets", indexes = {
    @Index(name = "idx_widgets_tenant_id", columnList = "tenantId"),
    @Index(name = "idx_widgets_tenant_status", columnList = "tenantId, status"),
    @Index(name = "idx_widgets_tenant_name", columnList = "tenantId, name", unique = true)
})
@SQLDelete(sql = "UPDATE widgets SET deleted_at = NOW(), updated_at = NOW() WHERE id = ? AND version = ?")
@SQLRestriction("deleted_at IS NULL")
public class Widget extends AuditableEntity {

    @Column(nullable = false, length = 255)
    private String name;

    @Column(length = 2000)
    private String description;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    private WidgetStatus status;

    // Getters and setters
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }
    public WidgetStatus getStatus() { return status; }
    public void setStatus(WidgetStatus status) { this.status = status; }
}

public enum WidgetStatus {
    ACTIVE, INACTIVE, ARCHIVED
}
```

## Repository Interface

```java
package com.example.app.repository;

import com.example.app.model.entity.Widget;
import com.example.app.model.entity.WidgetStatus;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface WidgetRepository extends JpaRepository<Widget, UUID>, JpaSpecificationExecutor<Widget> {

    // --- Derived query methods (Spring generates SQL from method name) ---

    Optional<Widget> findByIdAndTenantId(UUID id, UUID tenantId);

    Page<Widget> findByTenantId(UUID tenantId, Pageable pageable);

    Page<Widget> findByTenantIdAndStatus(UUID tenantId, WidgetStatus status, Pageable pageable);

    boolean existsByTenantIdAndNameIgnoreCase(UUID tenantId, String name);

    long countByTenantId(UUID tenantId);

    // --- JPQL queries (for joins and complex conditions) ---

    @Query("""
        SELECT w FROM Widget w
        WHERE w.tenantId = :tenantId
        AND LOWER(w.name) LIKE LOWER(CONCAT('%', :search, '%'))
        ORDER BY w.createdAt DESC
        """)
    Page<Widget> searchByName(@Param("tenantId") UUID tenantId,
                              @Param("search") String search,
                              Pageable pageable);

    @Query("""
        SELECT w FROM Widget w
        WHERE w.tenantId = :tenantId
        AND w.status IN :statuses
        """)
    Page<Widget> findByTenantIdAndStatusIn(@Param("tenantId") UUID tenantId,
                                           @Param("statuses") List<WidgetStatus> statuses,
                                           Pageable pageable);

    // --- Native queries (when JPQL cannot express the query) ---

    @Query(value = """
        SELECT w.* FROM widgets w
        WHERE w.tenant_id = :tenantId
        AND w.deleted_at IS NULL
        AND w.created_at >= NOW() - INTERVAL ':days days'
        ORDER BY w.created_at DESC
        """, nativeQuery = true)
    List<Widget> findRecentByTenant(@Param("tenantId") UUID tenantId,
                                    @Param("days") int days);

    // --- Bulk operations ---

    @Modifying
    @Query("UPDATE Widget w SET w.status = :status, w.updatedAt = CURRENT_TIMESTAMP WHERE w.tenantId = :tenantId AND w.status = :fromStatus")
    int bulkUpdateStatus(@Param("tenantId") UUID tenantId,
                         @Param("fromStatus") WidgetStatus fromStatus,
                         @Param("status") WidgetStatus status);

    @Modifying
    @Query("UPDATE Widget w SET w.deletedAt = CURRENT_TIMESTAMP, w.updatedAt = CURRENT_TIMESTAMP WHERE w.tenantId = :tenantId AND w.id IN :ids AND w.deletedAt IS NULL")
    int bulkSoftDelete(@Param("tenantId") UUID tenantId, @Param("ids") List<UUID> ids);
}
```

## Specification API for Dynamic Filtering

```java
package com.example.app.repository;

import com.example.app.model.entity.Widget;
import com.example.app.model.entity.WidgetStatus;
import org.springframework.data.jpa.domain.Specification;

import java.time.Instant;
import java.util.UUID;

 * Reusable Specifications for dynamic query composition.
 * Compose with .and() and .or() to build complex filters at runtime.
 * Usage in service:
 *   var spec = WidgetSpecs.belongsToTenant(tenantId)
 *       .and(WidgetSpecs.hasStatus(status))
 *       .and(WidgetSpecs.nameContains(search));
 *   repository.findAll(spec, pageable);
public final class WidgetSpecs {
    private WidgetSpecs() {}

     * REQUIRED: Every query MUST be scoped to a tenant.
    public static Specification<Widget> belongsToTenant(UUID tenantId) {
        return (root, query, cb) -> cb.equal(root.get("tenantId"), tenantId);
    }

     * Filter by exact status match.
    public static Specification<Widget> hasStatus(WidgetStatus status) {
        if (status == null) return Specification.where(null);
        return (root, query, cb) -> cb.equal(root.get("status"), status);
    }

     * Case-insensitive name search (LIKE %search%).
    public static Specification<Widget> nameContains(String search) {
        if (search == null || search.isBlank()) return Specification.where(null);
        return (root, query, cb) ->
            cb.like(cb.lower(root.get("name")), "%" + search.toLowerCase() + "%");
    }

     * Filter by creation date range.
    public static Specification<Widget> createdBetween(Instant from, Instant to) {
        return (root, query, cb) -> {
            if (from != null && to != null) {
                return cb.between(root.get("createdAt"), from, to);
            } else if (from != null) {
                return cb.greaterThanOrEqualTo(root.get("createdAt"), from);
            } else if (to != null) {
                return cb.lessThanOrEqualTo(root.get("createdAt"), to);
            }
            return cb.conjunction(); // no-op predicate
        };
    }

     * Soft delete filter — only include non-deleted records.
     * Note: @SQLRestriction on the entity handles this automatically for most queries.
     * Use this Specification only when building manual Specification chains
     * that bypass entity-level filters.
    public static Specification<Widget> notDeleted() {
        return (root, query, cb) -> cb.isNull(root.get("deletedAt"));
    }
}
```

## Using Specifications in the Service

```java
@Override
public Page<Widget> search(UUID tenantId, WidgetSearchCriteria criteria, Pageable pageable) {
    var requestId = MDC.get("requestId");
    log.debug("Searching widgets, tenant={}, criteria={}, requestId={}", tenantId, criteria, requestId);

    var spec = WidgetSpecs.belongsToTenant(tenantId)
        .and(WidgetSpecs.hasStatus(criteria.status()))
        .and(WidgetSpecs.nameContains(criteria.search()))
        .and(WidgetSpecs.createdBetween(criteria.createdFrom(), criteria.createdTo()));

    return repository.findAll(spec, pageable);
}

public record WidgetSearchCriteria(
    WidgetStatus status,
    String search,
    Instant createdFrom,
    Instant createdTo
) {}
```

## Pagination with Pageable

```java
// Controller creates Pageable from query params (see crud-handler-java.md):
var pageable = PageRequest.of(page, size, Sort.by(direction, sortBy));

// Repository returns Page<Widget> which includes:
// - getContent()           → List<Widget> items on this page
// - getTotalElements()     → total row count across all pages
// - getTotalPages()        → total number of pages
// - getNumber()            → current page number (zero-based)
// - getSize()              → requested page size
// - hasNext()              → true if there is a next page
// - hasPrevious()          → true if there is a previous page

// Spring Data automatically generates:
//   SELECT w.* FROM widgets w WHERE ... ORDER BY ... LIMIT ? OFFSET ?
//   SELECT COUNT(w.id) FROM widgets w WHERE ...
```

## Soft Delete Setup

```java
// On the entity:
@SQLDelete(sql = "UPDATE widgets SET deleted_at = NOW(), updated_at = NOW() WHERE id = ? AND version = ?")
@SQLRestriction("deleted_at IS NULL")
public class Widget extends AuditableEntity { ... }

// @SQLDelete   — intercepts JPA delete() and runs this SQL instead of DELETE FROM.
// @SQLRestriction — appends "AND deleted_at IS NULL" to every SELECT generated by Hibernate.
// Combined effect:
//   repository.delete(widget)       → UPDATE widgets SET deleted_at = NOW() WHERE id = ? AND version = ?
//   repository.findById(id)         → SELECT ... FROM widgets WHERE id = ? AND deleted_at IS NULL
//   repository.findAll(pageable)    → SELECT ... FROM widgets WHERE deleted_at IS NULL ORDER BY ... LIMIT ...
// To query deleted records (admin/audit), use native queries that bypass @SQLRestriction.
```

## Optimistic Locking

```java
// On the entity:
@Version
private Integer version;

// JPA behavior:
//   UPDATE widgets SET name = ?, version = version + 1
//   WHERE id = ? AND version = ?
// If version mismatch → ObjectOptimisticLockingFailureException (Spring wraps JPA's OptimisticLockException)
// Handle in @ControllerAdvice:
@ExceptionHandler(ObjectOptimisticLockingFailureException.class)
public ResponseEntity<ProblemDetail> handleOptimisticLock(ObjectOptimisticLockingFailureException ex) {
    var problem = ProblemDetail.forStatusAndDetail(HttpStatus.CONFLICT,
        "Resource was modified by another request. Reload and retry.");
    problem.setTitle("Conflict");
    return ResponseEntity.status(HttpStatus.CONFLICT).body(problem);
}
```

## Multi-Tenant Filtering

```java
// Option 1: Explicit tenant ID in every query (RECOMMENDED for simplicity)
// Every repository method receives tenantId and includes it in the WHERE clause.
// The service layer extracts tenantId from the authenticated principal.

Optional<Widget> findByIdAndTenantId(UUID id, UUID tenantId);
Page<Widget> findByTenantId(UUID tenantId, Pageable pageable);

// Option 2: Hibernate @Filter for automatic tenant scoping
// Useful when you want tenant filtering applied globally without passing it to every method.

@Entity
@FilterDef(name = "tenantFilter", parameters = @ParamDef(name = "tenantId", type = UUID.class))
@Filter(name = "tenantFilter", condition = "tenant_id = :tenantId")
public class Widget extends AuditableEntity { ... }

// Enable filter per request (in a servlet filter or interceptor):
@Component
public class TenantFilterActivator implements Filter {
    private final EntityManager entityManager;

    @Override
    public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain) {
        var tenantId = // extract from SecurityContext
        entityManager.unwrap(Session.class)
            .enableFilter("tenantFilter")
            .setParameter("tenantId", tenantId);
        chain.doFilter(request, response);
    }
}
```

## Projections for Read-Optimized Queries

```java
// Interface-based projection — Spring generates only the SELECT columns needed
public interface WidgetSummary {
    UUID getId();
    String getName();
    WidgetStatus getStatus();
    Instant getCreatedAt();
}

// In repository:
Page<WidgetSummary> findSummaryByTenantId(UUID tenantId, Pageable pageable);

// Generates: SELECT w.id, w.name, w.status, w.created_at FROM widgets w WHERE ...
// Avoids loading description, updatedBy, etc. — faster for list views.

// Record-based projection (DTO projection):
@Query("""
    SELECT new com.example.app.model.dto.WidgetStats(
        w.status, COUNT(w), MAX(w.createdAt)
    )
    FROM Widget w
    WHERE w.tenantId = :tenantId
    GROUP BY w.status
    """)
List<WidgetStats> getStatsByTenant(@Param("tenantId") UUID tenantId);

public record WidgetStats(WidgetStatus status, long count, Instant latestCreated) {}
```

## Flyway Migration Example

```sql
-- V1__create_widgets.sql
CREATE TABLE widgets (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL,
    name        VARCHAR(255) NOT NULL,
    description VARCHAR(2000),
    status      VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at  TIMESTAMPTZ,
    created_by  UUID NOT NULL,
    updated_by  UUID NOT NULL,
    version     INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_widgets_tenant_id ON widgets (tenant_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_widgets_tenant_status ON widgets (tenant_id, status) WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX idx_widgets_tenant_name ON widgets (tenant_id, LOWER(name)) WHERE deleted_at IS NULL;

-- Partial indexes with WHERE deleted_at IS NULL reduce index size and speed up queries
-- that use @SQLRestriction("deleted_at IS NULL").
```

## Critical Rules

- Every query MUST include tenant scoping — either via method name (`findByTenantIdAnd...`) or Specification (`belongsToTenant`).
- NEVER use `findById()` without tenant scoping — use `findByIdAndTenantId()` to prevent cross-tenant access.
- `@SQLDelete` + `@SQLRestriction` on every entity for soft delete — `DELETE` becomes `UPDATE SET deleted_at`.
- `@Version` on every entity for optimistic locking — JPA auto-increments and rejects stale writes.
- Use `@Query` with JPQL for joins and complex conditions; native queries only when JPQL cannot express it.
- Use Specification API for dynamic filtering at runtime — never build query strings manually.
- Use projections (`WidgetSummary` interfaces, DTO projections) for read-heavy list endpoints — avoid loading full entities.
- Pagination is MANDATORY for all list operations — never return unbounded `List<Widget>`.
- Schema changes go through Flyway/Liquibase — `ddl-auto: validate` in production.
- Use partial indexes (`WHERE deleted_at IS NULL`) in Postgres for soft-deleted tables.
- Bulk operations (`@Modifying` + `@Query`) MUST include `tenantId` in the WHERE clause.
- `@Modifying` queries require `@Transactional` on the calling service method.
- Repository interfaces extend `JpaRepository` + `JpaSpecificationExecutor` — no implementation classes unless absolutely necessary.
