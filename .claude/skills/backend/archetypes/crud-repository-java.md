---
skill: crud-repository-java
description: Spring Data JPA repository archetype — JpaRepository, custom queries, Specification API, keyset (cursor) scrolling with Window/ScrollPosition, soft delete, optimistic locking, multi-tenant filtering
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

> Java samples compile-checked 2026-09-30: JDK 25.0.4.1, Spring Boot 4.1.1, Maven 3.9.16 (`tests/archetype-compile/java/run.sh`).

Complete, production-ready Spring Data JPA repository template. Every generated repository MUST follow this pattern.

## Entity Base Class

```java
package com.example.app.model.entity;

import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;

/**
 * Base entity with audit fields, soft delete, and optimistic locking.
 * All domain entities MUST extend this class.
 */
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
    @Index(name = "idx_widgets_tenant_name", columnList = "tenantId, name", unique = true),
    @Index(name = "idx_widgets_tenant_created_id", columnList = "tenantId, createdAt, id") // keyset scroll
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
import org.springframework.data.domain.ScrollPosition;
import org.springframework.data.domain.Window;
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

    boolean existsByTenantIdAndNameIgnoreCase(UUID tenantId, String name);

    long countByTenantId(UUID tenantId);

    // --- Lists: keyset (cursor) scrolling only — no Page, Pageable or OFFSET ---
    //
    // API list endpoints scroll through JpaSpecificationExecutor#findBy with a tenant Specification,
    // so filters (status, name search, date range) compose at runtime (see "Pagination — keyset
    // (cursor) only" below):
    //   repository.findBy(WidgetSpecs.belongsToTenant(tenantId).and(WidgetSpecs.hasStatus(status)),
    //       q -> q.sortBy(sort).limit(limit).scroll(position));          // → Window<Widget>
    //
    // A fixed list can also be a derived query with a static limit:
    Window<Widget> findFirst20ByTenantIdOrderByCreatedAtDescIdDesc(UUID tenantId, ScrollPosition position);

    // --- JPQL queries (for joins and complex conditions) — always with the tenant predicate ---

    @Query("""
        SELECT COUNT(w) FROM Widget w
        WHERE w.tenantId = :tenantId
        AND w.status IN :statuses
        """)
    long countByTenantIdAndStatusIn(@Param("tenantId") UUID tenantId,
                                    @Param("statuses") List<WidgetStatus> statuses);

    // --- Native queries (when JPQL cannot express the query) ---

    @Query(value = """
        SELECT w.* FROM widgets w
        WHERE w.tenant_id = :tenantId
        AND w.deleted_at IS NULL
        AND w.created_at >= NOW() - (:days * INTERVAL '1 day')
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

/**
 * Reusable Specifications for dynamic query composition.
 * Compose with .and() and .or() to build complex filters at runtime.
 *
 * Usage in service (every chain starts with belongsToTenant):
 *   var spec = WidgetSpecs.belongsToTenant(tenantId)
 *       .and(WidgetSpecs.hasStatus(status))
 *       .and(WidgetSpecs.nameContains(search));
 *   repository.findBy(spec, q -> q.sortBy(sort).limit(limit).scroll(position)); // → Window<Widget>
 */
public final class WidgetSpecs {
    private WidgetSpecs() {}

    /**
     * REQUIRED: Every query MUST be scoped to a tenant.
     */
    public static Specification<Widget> belongsToTenant(UUID tenantId) {
        return (root, query, cb) -> cb.equal(root.get("tenantId"), tenantId);
    }

    /**
     * Filter by exact status match.
     */
    public static Specification<Widget> hasStatus(WidgetStatus status) {
        if (status == null) return (root, query, cb) -> cb.conjunction(); // no-op; Specification.where(null) is rejected since Spring Data JPA 4.0
        return (root, query, cb) -> cb.equal(root.get("status"), status);
    }

    /**
     * Filter by any of several statuses.
     */
    public static Specification<Widget> hasStatusIn(java.util.Collection<WidgetStatus> statuses) {
        if (statuses == null || statuses.isEmpty()) return (root, query, cb) -> cb.conjunction(); // no-op; Specification.where(null) is rejected since Spring Data JPA 4.0
        return (root, query, cb) -> root.get("status").in(statuses);
    }

    /**
     * Case-insensitive name search (LIKE %search%).
     */
    public static Specification<Widget> nameContains(String search) {
        if (search == null || search.isBlank()) return (root, query, cb) -> cb.conjunction(); // no-op; Specification.where(null) is rejected since Spring Data JPA 4.0
        return (root, query, cb) ->
            cb.like(cb.lower(root.get("name")), "%" + search.toLowerCase() + "%");
    }

    /**
     * Filter by creation date range.
     */
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

    /**
     * Soft delete filter — only include non-deleted records.
     * Note: @SQLRestriction on the entity handles this automatically for most queries.
     * Use this Specification only when building manual Specification chains
     * that bypass entity-level filters.
     */
    public static Specification<Widget> notDeleted() {
        return (root, query, cb) -> cb.isNull(root.get("deletedAt"));
    }
}
```

## Using Specifications in the Service

```java
@Override
public Window<Widget> search(UUID tenantId, WidgetSearchCriteria criteria,
                             ScrollPosition position, Sort sort, int limit) {
    var requestId = MDC.get("requestId");
    log.debug("Searching widgets, tenant={}, criteria={}, requestId={}", tenantId, criteria, requestId);

    var spec = WidgetSpecs.belongsToTenant(tenantId)
        .and(WidgetSpecs.hasStatus(criteria.status()))
        .and(WidgetSpecs.nameContains(criteria.search()))
        .and(WidgetSpecs.createdBetween(criteria.createdFrom(), criteria.createdTo()));

    // Keyset scroll: at most `limit` rows after `position` — no OFFSET, no COUNT query
    return repository.findBy(spec, q -> q.sortBy(sort).limit(limit).scroll(position));
}

public record WidgetSearchCriteria(
    WidgetStatus status,
    String search,
    Instant createdFrom,
    Instant createdTo
) {}
```

## Pagination — keyset (cursor) only

List endpoints take `?cursor=<next_cursor>&limit=<n>` and return `meta.pagination`
(`~/.claude/skills/api/response-envelope.md`). There is no offset or page-number variant: offset pages
skip or repeat rows under concurrent writes, and `OFFSET 10000` still scans 10,000 rows. For "jump to
page N" admin tables, filter instead (date range, search, status). A spec that truly needs numbered
pages records it in `docs/DECISIONS.md` and still uses the envelope.

```java
// Controller builds the Sort and decodes the cursor (crud-handler-java.md):
var sort = Sort.by(direction, sortBy).and(Sort.by(direction, "id")); // id makes every position unique
var position = CursorCodec.decode(cursor, sort);                      // ScrollPosition.keyset() on page 1

// Service scrolls one window (crud-service-java.md):
Window<Widget> window = repository.findBy(
    WidgetSpecs.belongsToTenant(tenantId).and(WidgetSpecs.hasStatus(status)),
    q -> q.sortBy(sort).limit(limit).scroll(position));

// Window<Widget> gives:
// - getContent()                → List<Widget> in this window ([] when empty)
// - hasNext()                   → meta.pagination.has_more
// - positionAt(size() - 1)      → the next position; CursorCodec.encode(...) → meta.pagination.next_cursor
//
// Spring Data generates a keyset predicate instead of OFFSET, and no COUNT query:
//   SELECT w.* FROM widgets w
//   WHERE w.tenant_id = ? AND w.deleted_at IS NULL
//     AND (w.created_at < ? OR (w.created_at = ? AND w.id < ?))
//   ORDER BY w.created_at DESC, w.id DESC LIMIT ?
//
// Keyset rules: sort keys must be NOT NULL, and an index should match (tenant_id, sort key, id).
```

## Soft Delete Setup

```java
// On the entity:
@SQLDelete(sql = "UPDATE widgets SET deleted_at = NOW(), updated_at = NOW() WHERE id = ? AND version = ?")
@SQLRestriction("deleted_at IS NULL")
public class Widget extends AuditableEntity { ... }

// @SQLDelete   — intercepts JPA delete() and runs this SQL instead of DELETE FROM.
// @SQLRestriction — appends "AND deleted_at IS NULL" to every SELECT generated by Hibernate.
//
// Combined effect:
//   repository.delete(widget)              → UPDATE widgets SET deleted_at = NOW() WHERE id = ? AND version = ?
//   repository.findByIdAndTenantId(id, t)  → SELECT ... WHERE id = ? AND tenant_id = ? AND deleted_at IS NULL
//   repository.findBy(spec, q -> ...scroll)→ SELECT ... WHERE tenant_id = ? AND deleted_at IS NULL AND <keyset> ORDER BY ... LIMIT ...
//
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
//
// If version mismatch → ObjectOptimisticLockingFailureException (Spring wraps JPA's OptimisticLockException)
//
// Do NOT handle it here or in a controller. GlobalExceptionHandler (error-handling-java.md), the only
// error writer, maps it to 409 CONFLICT in the error envelope:
//   {"error": {"code": "CONFLICT", "message": "This item was changed by someone else. Reload and try again.",
//              "request_id": "…", "retryable": false}}
// Likewise DataIntegrityViolationException: SQLSTATE 23505 → 409 CONFLICT, 23503/23514 → 422
// BUSINESS_RULE_VIOLATION — constraint names stay in the log.
```

## Multi-Tenant Filtering

```java
// Option 1: Explicit tenant ID in every query (RECOMMENDED for simplicity)
// Every repository method receives tenantId and includes it in the WHERE clause.
// The service layer extracts tenantId from the authenticated principal.

Optional<Widget> findByIdAndTenantId(UUID id, UUID tenantId);
Window<Widget> findFirst20ByTenantIdOrderByCreatedAtDescIdDesc(UUID tenantId, ScrollPosition position);
// ...and every Specification chain starts with WidgetSpecs.belongsToTenant(tenantId).

// Option 2: Hibernate @Filter for automatic tenant scoping
// Useful when you want tenant filtering applied globally without passing it to every method.

@Entity
@FilterDef(name = "tenantFilter", parameters = @ParamDef(name = "tenantId", type = UUID.class))
@Filter(name = "tenantFilter", condition = "tenant_id = :tenantId")
public class Widget extends AuditableEntity { ... }

// Enable the filter INSIDE each transaction: a Hibernate filter lives on one Session, and the Session a
// @Transactional method uses only exists once it starts. A servlet filter or HandlerInterceptor runs before
// that, so enabling it there filters a Session no repository call uses.
@Component
public class TenantFilterActivator {
    private final EntityManager entityManager;

    public TenantFilterActivator(EntityManager entityManager) {
        this.entityManager = entityManager;
    }

    /** First call in every @Transactional service method; tenantId from the verified principal, never a header. */
    public void enableFor(UUID tenantId) {
        entityManager.unwrap(Session.class)
            .enableFilter("tenantFilter")
            .setParameter("tenantId", tenantId);
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

// In repository — keyset-scrolled like every list; the projection must expose the sort keys
// (createdAt, id) so the next ScrollPosition can be built from the last row:
Window<WidgetSummary> findFirst20SummaryByTenantIdOrderByCreatedAtDescIdDesc(UUID tenantId, ScrollPosition position);

// Generates: SELECT w.id, w.name, w.status, w.created_at FROM widgets w WHERE w.tenant_id = ? AND <keyset> ...
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
CREATE INDEX idx_widgets_tenant_created_id ON widgets (tenant_id, created_at DESC, id DESC) WHERE deleted_at IS NULL; -- keyset scroll

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
- Lists are keyset-scrolled `Window`s (`ScrollPosition` + limit, sort ending in `id`) — never `Page`/`Pageable`/`OFFSET`, never an unbounded `List<Widget>`.
- Error mapping (optimistic lock, integrity violations, timeouts) lives only in `GlobalExceptionHandler` (`error-handling-java.md`) — repositories and controllers never build error bodies.
- Schema changes go through Flyway/Liquibase — `ddl-auto: validate` in production.
- Use partial indexes (`WHERE deleted_at IS NULL`) in Postgres for soft-deleted tables.
- Bulk operations (`@Modifying` + `@Query`) MUST include `tenantId` in the WHERE clause.
- `@Modifying` queries require `@Transactional` on the calling service method.
- Repository interfaces extend `JpaRepository` + `JpaSpecificationExecutor` — no implementation classes unless absolutely necessary.
