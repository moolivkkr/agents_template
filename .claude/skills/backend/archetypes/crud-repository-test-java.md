---
skill: crud-repository-test-java
description: Spring Data JPA repository integration test archetype — @DataJpaTest, Testcontainers PostgreSQL, real DB queries, Specification filtering, soft delete, optimistic locking, keyset (cursor) scrolling
version: "1.0"
tags:
  - java
  - spring-boot
  - jpa
  - repository
  - integration-test
  - testcontainers
  - archetype
  - backend
  - testing
---

# CRUD Repository Test Archetype (Spring Boot + Testcontainers)

Complete, production-ready repository integration test template using `@DataJpaTest` and Testcontainers. Every generated repository test MUST follow this pattern.

## Test File Location

```
src/test/java/com/example/app/repository/
  WidgetRepositoryTest.java      <- THIS file
src/test/resources/
  application-test.yml           <- test-specific config
  db/testdata/
    widgets.sql                  <- optional test data
```

Rule: Repository tests use a REAL PostgreSQL database via Testcontainers. Never mock the database in repository tests.

## Testcontainers Configuration

```java
package com.example.app.repository;

import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.context.annotation.Bean;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.utility.DockerImageName;

/**
 * Shared Testcontainers configuration — reused across all repository tests.
 * The container is started once per test class (or once per suite with @Testcontainers).
 */
@TestConfiguration
public class TestcontainersConfig {

    @Bean
    @ServiceConnection
    public PostgreSQLContainer<?> postgreSQLContainer() {
        return new PostgreSQLContainer<>(DockerImageName.parse("postgres:16-alpine"))
            .withDatabaseName("testdb")
            .withUsername("test")
            .withPassword("test")
            .withReuse(true); // Reuse container across tests (requires testcontainers.reuse.enable=true)
    }
}
```

## Test Application Properties

```yaml
# src/test/resources/application-test.yml
spring:
  jpa:
    hibernate:
      ddl-auto: validate  # Flyway manages schema; Hibernate validates
    show-sql: true
    properties:
      hibernate:
        format_sql: true
  flyway:
    enabled: true
    locations: classpath:db/migration
```

## Test Class Setup

```java
package com.example.app.repository;

import com.example.app.model.entity.Widget;
import com.example.app.model.entity.WidgetStatus;
import org.junit.jupiter.api.*;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.autoconfigure.orm.jpa.TestEntityManager;
import org.springframework.context.annotation.Import;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.data.domain.ScrollPosition;
import org.springframework.data.domain.Sort;
import org.springframework.data.domain.Window;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.orm.ObjectOptimisticLockingFailureException;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.jdbc.Sql;

import java.sql.SQLException;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.UUID;
import java.util.function.Consumer;

import static org.assertj.core.api.Assertions.*;

@DataJpaTest
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@Import(TestcontainersConfig.class)
@ActiveProfiles("test")
@DisplayName("WidgetRepository")
class WidgetRepositoryTest {

    @Autowired
    private WidgetRepository repository;

    @Autowired
    private TestEntityManager entityManager;

    private static final UUID TENANT_A = UUID.fromString("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa");
    private static final UUID TENANT_B = UUID.fromString("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb");
    private static final UUID USER_ID = UUID.fromString("cccccccc-cccc-cccc-cccc-cccccccccccc");

    @AfterEach
    void cleanUp() {
        // Ensure test isolation — each test starts with a clean table
        repository.deleteAll();
        entityManager.flush();
        entityManager.clear();
    }
}
```

## Test Factory

```java
/**
 * Build a Widget entity with sensible defaults for persistence tests.
 * Uses Consumer-based customizers for fluent field overrides.
 */
@SafeVarargs
private Widget makeWidget(Consumer<Widget>... customizers) {
    var w = new Widget();
    w.setTenantId(TENANT_A);
    w.setName("widget-" + UUID.randomUUID().toString().substring(0, 8));
    w.setDescription("Test widget description");
    w.setStatus(WidgetStatus.ACTIVE);
    w.setCreatedAt(Instant.now());
    w.setUpdatedAt(Instant.now());
    w.setCreatedBy(USER_ID);
    w.setUpdatedBy(USER_ID);
    // Note: id and version are generated by JPA — do not set manually
    for (var c : customizers) {
        c.accept(w);
    }
    return w;
}

private Consumer<Widget> withTenantId(UUID tenantId) {
    return w -> w.setTenantId(tenantId);
}

private Consumer<Widget> withName(String name) {
    return w -> w.setName(name);
}

private Consumer<Widget> withStatus(WidgetStatus status) {
    return w -> w.setStatus(status);
}

private Consumer<Widget> withCreatedAt(Instant createdAt) {
    return w -> w.setCreatedAt(createdAt);
}

/**
 * Persist a widget and flush to DB — returns the managed entity with generated ID and version.
 */
private Widget persistWidget(Widget widget) {
    var saved = entityManager.persistAndFlush(widget);
    entityManager.clear(); // Detach to force fresh reads from DB
    return saved;
}

// The list sort the controller builds: newest first, id as the unique tiebreaker
private static final Sort NEWEST_FIRST =
    Sort.by(Sort.Direction.DESC, "createdAt").and(Sort.by(Sort.Direction.DESC, "id"));

/** One keyset window — exactly how WidgetServiceImpl.findAll scrolls. */
private Window<Widget> scroll(Specification<Widget> spec, ScrollPosition position, int limit) {
    return repository.findBy(spec, q -> q.sortBy(NEWEST_FIRST).limit(limit).scroll(position));
}

/** First window (up to 100 rows) of a tenant-scoped Specification. */
private Window<Widget> firstWindow(Specification<Widget> spec) {
    return scroll(spec, ScrollPosition.keyset(), 100);
}

/** SQLSTATE of the driver exception under a Spring DataAccessException (what GlobalExceptionHandler maps). */
private static String sqlState(Throwable ex) {
    for (var t = ex; t != null; t = t.getCause()) {
        if (t instanceof SQLException sql) {
            return sql.getSQLState();
        }
    }
    return null;
}
```

## CRUD Tests with Real Database

```java
@Nested
@DisplayName("Basic CRUD operations")
class CrudTests {

    @Test
    @DisplayName("save — inserts and generates ID and version")
    void save_NewWidget_GeneratesIdAndVersion() {
        var widget = makeWidget(withName("My Widget"));

        var saved = repository.save(widget);
        entityManager.flush();
        entityManager.clear();

        assertThat(saved.getId()).isNotNull();
        assertThat(saved.getVersion()).isEqualTo(0); // JPA @Version starts at 0
        assertThat(saved.getName()).isEqualTo("My Widget");
        assertThat(saved.getTenantId()).isEqualTo(TENANT_A);
    }

    @Test
    @DisplayName("findByIdAndTenantId — returns widget for correct tenant")
    void findByIdAndTenantId_Exists_ReturnsWidget() {
        var widget = persistWidget(makeWidget(withName("Found Widget")));

        var found = repository.findByIdAndTenantId(widget.getId(), TENANT_A);

        assertThat(found).isPresent();
        assertThat(found.get().getName()).isEqualTo("Found Widget");
        assertThat(found.get().getId()).isEqualTo(widget.getId());
    }

    @Test
    @DisplayName("findByIdAndTenantId — returns empty for non-existent ID")
    void findByIdAndTenantId_NotFound_ReturnsEmpty() {
        var found = repository.findByIdAndTenantId(UUID.randomUUID(), TENANT_A);

        assertThat(found).isEmpty();
    }

    @Test
    @DisplayName("update — modifies fields on existing widget")
    void update_ModifiesFields() {
        var widget = persistWidget(makeWidget(withName("Original")));

        var loaded = repository.findByIdAndTenantId(widget.getId(), TENANT_A).orElseThrow();
        loaded.setName("Updated Name");
        loaded.setUpdatedAt(Instant.now());
        repository.save(loaded);
        entityManager.flush();
        entityManager.clear();

        var updated = repository.findByIdAndTenantId(widget.getId(), TENANT_A).orElseThrow();
        assertThat(updated.getName()).isEqualTo("Updated Name");
        assertThat(updated.getVersion()).isEqualTo(widget.getVersion() + 1); // version incremented
    }

    @Test
    @DisplayName("delete — soft deletes via @SQLDelete (sets deleted_at)")
    void delete_SoftDeleteSetsDeletedAt() {
        var widget = persistWidget(makeWidget(withName("To Delete")));

        var loaded = repository.findByIdAndTenantId(widget.getId(), TENANT_A).orElseThrow();
        repository.delete(loaded);
        entityManager.flush();
        entityManager.clear();

        // findByIdAndTenantId should NOT find it (filtered by @SQLRestriction)
        var afterDelete = repository.findByIdAndTenantId(widget.getId(), TENANT_A);
        assertThat(afterDelete).isEmpty();

        // But the row still exists in the database
        var count = entityManager.getEntityManager()
            .createNativeQuery("SELECT COUNT(*) FROM widgets WHERE id = ?1")
            .setParameter(1, widget.getId())
            .getSingleResult();
        assertThat(((Number) count).longValue()).isEqualTo(1);

        // deleted_at is set
        var deletedAt = entityManager.getEntityManager()
            .createNativeQuery("SELECT deleted_at FROM widgets WHERE id = ?1")
            .setParameter(1, widget.getId())
            .getSingleResult();
        assertThat(deletedAt).isNotNull();
    }
}
```

## Keyset (Cursor) Scrolling Tests

```java
@Nested
@DisplayName("Keyset scrolling (Window / ScrollPosition)")
class ScrollTests {

    @Test
    @DisplayName("first window — returns `limit` rows and hasNext")
    void firstWindow_ReturnsLimitAndHasNext() {
        var now = Instant.now();
        for (int i = 0; i < 25; i++) {
            persistWidget(makeWidget(
                withName("widget-" + String.format("%03d", i)),
                withCreatedAt(now.plus(i, ChronoUnit.SECONDS))
            ));
        }

        var window = scroll(WidgetSpecs.belongsToTenant(TENANT_A), ScrollPosition.keyset(), 10);

        assertThat(window.getContent()).hasSize(10);
        assertThat(window.hasNext()).isTrue();
        assertThat(window.getContent().get(0).getName()).isEqualTo("widget-024"); // newest first
    }

    @Test
    @DisplayName("following positionAt(last) visits every row exactly once")
    void followingPositions_VisitsEveryRowOnce() {
        for (int i = 0; i < 25; i++) {
            persistWidget(makeWidget(withName("widget-" + String.format("%03d", i))));
        }

        var seen = new ArrayList<UUID>();
        var windows = 0;
        var window = scroll(WidgetSpecs.belongsToTenant(TENANT_A), ScrollPosition.keyset(), 10);
        while (true) {
            windows++;
            window.getContent().forEach(w -> seen.add(w.getId()));
            if (!window.hasNext()) break;
            window = scroll(WidgetSpecs.belongsToTenant(TENANT_A), window.positionAt(window.size() - 1), 10);
        }

        assertThat(windows).isEqualTo(3);
        assertThat(window.getContent()).hasSize(5); // last window
        assertThat(seen).hasSize(25).doesNotHaveDuplicates();
    }

    @Test
    @DisplayName("empty result — empty window, not null, no next")
    void emptyTenant_ReturnsEmptyWindow() {
        var window = firstWindow(WidgetSpecs.belongsToTenant(TENANT_A));

        assertThat(window.getContent()).isEmpty();
        assertThat(window.hasNext()).isFalse();
    }

    @Test
    @DisplayName("sort order — DESC by createdAt returns newest first")
    void scroll_SortDesc_NewestFirst() {
        var oldest = persistWidget(makeWidget(
            withName("oldest"),
            withCreatedAt(Instant.now().minus(2, ChronoUnit.HOURS))
        ));
        var middle = persistWidget(makeWidget(
            withName("middle"),
            withCreatedAt(Instant.now().minus(1, ChronoUnit.HOURS))
        ));
        var newest = persistWidget(makeWidget(
            withName("newest"),
            withCreatedAt(Instant.now())
        ));

        var window = scroll(WidgetSpecs.belongsToTenant(TENANT_A), ScrollPosition.keyset(), 10);

        assertThat(window.getContent()).hasSize(3);
        assertThat(window.getContent().get(0).getName()).isEqualTo("newest");
        assertThat(window.getContent().get(2).getName()).isEqualTo("oldest");
    }

    @Test
    @DisplayName("insert between windows — no duplicates and no gaps (where OFFSET would repeat a row)")
    void insertBetweenWindows_NoDuplicatesNoGaps() {
        var base = Instant.now().minus(1, ChronoUnit.HOURS);
        var original = new HashSet<UUID>();
        for (int i = 0; i < 20; i++) {
            original.add(persistWidget(makeWidget(
                withName("widget-" + String.format("%03d", i)),
                withCreatedAt(base.plus(i, ChronoUnit.SECONDS))
            )).getId());
        }

        var first = scroll(WidgetSpecs.belongsToTenant(TENANT_A), ScrollPosition.keyset(), 10);

        // A concurrent insert lands at the top of the list between the two requests
        persistWidget(makeWidget(withName("inserted-meanwhile"), withCreatedAt(Instant.now())));

        var second = scroll(WidgetSpecs.belongsToTenant(TENANT_A), first.positionAt(first.size() - 1), 10);

        var seen = new HashSet<UUID>();
        first.getContent().forEach(w -> assertThat(seen.add(w.getId())).isTrue());
        second.getContent().forEach(w -> assertThat(seen.add(w.getId())).isTrue()); // no duplicates
        assertThat(seen).isEqualTo(original);                                        // no gaps
        assertThat(second.hasNext()).isFalse();
    }
}
```

## Tenant Isolation Tests

```java
@Nested
@DisplayName("Tenant isolation")
class TenantIsolationTests {

    @Test
    @DisplayName("findByIdAndTenantId — wrong tenant returns empty")
    void findByIdAndTenantId_WrongTenant_ReturnsEmpty() {
        var widget = persistWidget(makeWidget(withTenantId(TENANT_A)));

        var found = repository.findByIdAndTenantId(widget.getId(), TENANT_B);

        assertThat(found).isEmpty();
    }

    @Test
    @DisplayName("scroll with belongsToTenant — only returns widgets for requested tenant")
    void scroll_IsolatesByTenant() {
        // Seed 3 for tenant A, 2 for tenant B
        for (int i = 0; i < 3; i++) {
            persistWidget(makeWidget(withTenantId(TENANT_A), withName("a-" + i)));
        }
        for (int i = 0; i < 2; i++) {
            persistWidget(makeWidget(withTenantId(TENANT_B), withName("b-" + i)));
        }

        var windowA = firstWindow(WidgetSpecs.belongsToTenant(TENANT_A));
        var windowB = firstWindow(WidgetSpecs.belongsToTenant(TENANT_B));

        assertThat(windowA.getContent()).hasSize(3);
        assertThat(windowA.getContent()).allMatch(w -> w.getTenantId().equals(TENANT_A));

        assertThat(windowB.getContent()).hasSize(2);
        assertThat(windowB.getContent()).allMatch(w -> w.getTenantId().equals(TENANT_B));
    }

    @Test
    @DisplayName("a cursor from tenant A's list does not reveal tenant B's rows")
    void scroll_PositionFromOtherTenant_StillScopedToTenant() {
        for (int i = 0; i < 3; i++) {
            persistWidget(makeWidget(withTenantId(TENANT_A), withName("a-" + i)));
            persistWidget(makeWidget(withTenantId(TENANT_B), withName("b-" + i)));
        }
        var windowA = scroll(WidgetSpecs.belongsToTenant(TENANT_A), ScrollPosition.keyset(), 1);

        // Replaying A's position under tenant B's scope returns only B's rows
        var windowB = scroll(WidgetSpecs.belongsToTenant(TENANT_B), windowA.positionAt(0), 10);

        assertThat(windowB.getContent()).allMatch(w -> w.getTenantId().equals(TENANT_B));
    }

    @Test
    @DisplayName("derived findFirst20ByTenantId… — scoped to tenant")
    void derivedScroll_IsolatesByTenant() {
        persistWidget(makeWidget(withTenantId(TENANT_A), withName("a-only")));
        persistWidget(makeWidget(withTenantId(TENANT_B), withName("b-only")));

        var window = repository.findFirst20ByTenantIdOrderByCreatedAtDescIdDesc(TENANT_A, ScrollPosition.keyset());

        assertThat(window.getContent()).extracting(Widget::getName).containsExactly("a-only");
    }

    @Test
    @DisplayName("countByTenantId — counts only for the specified tenant")
    void countByTenantId_IsolatesByTenant() {
        for (int i = 0; i < 5; i++) {
            persistWidget(makeWidget(withTenantId(TENANT_A), withName("a-" + i)));
        }
        for (int i = 0; i < 3; i++) {
            persistWidget(makeWidget(withTenantId(TENANT_B), withName("b-" + i)));
        }

        assertThat(repository.countByTenantId(TENANT_A)).isEqualTo(5);
        assertThat(repository.countByTenantId(TENANT_B)).isEqualTo(3);
    }

    @Test
    @DisplayName("existsByTenantIdAndNameIgnoreCase — scoped to tenant")
    void existsByName_IsolatesByTenant() {
        persistWidget(makeWidget(withTenantId(TENANT_A), withName("Unique Widget")));

        assertThat(repository.existsByTenantIdAndNameIgnoreCase(TENANT_A, "Unique Widget")).isTrue();
        assertThat(repository.existsByTenantIdAndNameIgnoreCase(TENANT_A, "UNIQUE WIDGET")).isTrue(); // case-insensitive
        assertThat(repository.existsByTenantIdAndNameIgnoreCase(TENANT_B, "Unique Widget")).isFalse();
    }
}
```

## Optimistic Locking Tests

```java
@Nested
@DisplayName("Optimistic locking (@Version)")
class OptimisticLockingTests {

    @Test
    @DisplayName("concurrent update — second save throws ObjectOptimisticLockingFailureException")
    void concurrentUpdate_ThrowsOptimisticLockException() {
        var widget = persistWidget(makeWidget(withName("Concurrent")));

        // Simulate two concurrent reads
        var read1 = repository.findByIdAndTenantId(widget.getId(), TENANT_A).orElseThrow();
        var read2 = repository.findByIdAndTenantId(widget.getId(), TENANT_A).orElseThrow();

        // First update succeeds
        read1.setName("Update A");
        read1.setUpdatedAt(Instant.now());
        repository.saveAndFlush(read1);

        // Second update fails — version was already incremented
        read2.setName("Update B");
        read2.setUpdatedAt(Instant.now());

        assertThatThrownBy(() -> repository.saveAndFlush(read2))
            .isInstanceOf(ObjectOptimisticLockingFailureException.class);
    }

    @Test
    @DisplayName("version auto-increments on save")
    void save_IncrementsVersion() {
        var widget = persistWidget(makeWidget(withName("Versioned")));
        var initialVersion = widget.getVersion();

        var loaded = repository.findByIdAndTenantId(widget.getId(), TENANT_A).orElseThrow();
        loaded.setName("Updated");
        loaded.setUpdatedAt(Instant.now());
        repository.saveAndFlush(loaded);
        entityManager.clear();

        var updated = repository.findByIdAndTenantId(widget.getId(), TENANT_A).orElseThrow();
        assertThat(updated.getVersion()).isEqualTo(initialVersion + 1);
    }
}
```

## Soft Delete Tests

```java
@Nested
@DisplayName("Soft delete (@SQLDelete + @SQLRestriction)")
class SoftDeleteTests {

    @Test
    @DisplayName("soft-deleted widgets are excluded from the list scroll")
    void softDeleted_ExcludedFromList() {
        var visible = persistWidget(makeWidget(withName("Visible")));
        var toDelete = persistWidget(makeWidget(withName("To Delete")));

        var loaded = repository.findByIdAndTenantId(toDelete.getId(), TENANT_A).orElseThrow();
        repository.delete(loaded);
        entityManager.flush();
        entityManager.clear();

        var window = firstWindow(WidgetSpecs.belongsToTenant(TENANT_A));
        assertThat(window.getContent()).hasSize(1);
        assertThat(window.getContent().get(0).getId()).isEqualTo(visible.getId());
    }

    @Test
    @DisplayName("soft-deleted widgets are excluded from findByIdAndTenantId")
    void softDeleted_ExcludedFromFindById() {
        var widget = persistWidget(makeWidget(withName("Delete Me")));

        var loaded = repository.findByIdAndTenantId(widget.getId(), TENANT_A).orElseThrow();
        repository.delete(loaded);
        entityManager.flush();
        entityManager.clear();

        var found = repository.findByIdAndTenantId(widget.getId(), TENANT_A);
        assertThat(found).isEmpty();
    }

    @Test
    @DisplayName("soft-deleted widgets are excluded from existsByTenantIdAndName")
    void softDeleted_ExcludedFromExistsCheck() {
        var widget = persistWidget(makeWidget(withName("Deletable")));

        var loaded = repository.findByIdAndTenantId(widget.getId(), TENANT_A).orElseThrow();
        repository.delete(loaded);
        entityManager.flush();
        entityManager.clear();

        // Name is now available again after soft delete
        assertThat(repository.existsByTenantIdAndNameIgnoreCase(TENANT_A, "Deletable")).isFalse();
    }

    @Test
    @DisplayName("can re-create widget with same name after soft delete")
    void softDeleted_AllowsNameReuse() {
        var original = persistWidget(makeWidget(withName("Recyclable")));

        var loaded = repository.findByIdAndTenantId(original.getId(), TENANT_A).orElseThrow();
        repository.delete(loaded);
        entityManager.flush();
        entityManager.clear();

        // Create new widget with the same name — should succeed
        var replacement = makeWidget(withName("Recyclable"));
        var saved = repository.save(replacement);
        entityManager.flush();

        assertThat(saved.getId()).isNotEqualTo(original.getId());
        assertThat(saved.getName()).isEqualTo("Recyclable");
    }
}
```

## Custom Query Tests

```java
@Nested
@DisplayName("Status and name filters, @Query methods")
class CustomQueryTests {

    @Test
    @DisplayName("hasStatus — filters by status")
    void hasStatus_FiltersCorrectly() {
        persistWidget(makeWidget(withName("active-1"), withStatus(WidgetStatus.ACTIVE)));
        persistWidget(makeWidget(withName("active-2"), withStatus(WidgetStatus.ACTIVE)));
        persistWidget(makeWidget(withName("archived-1"), withStatus(WidgetStatus.ARCHIVED)));

        var window = firstWindow(WidgetSpecs.belongsToTenant(TENANT_A)
            .and(WidgetSpecs.hasStatus(WidgetStatus.ACTIVE)));

        assertThat(window.getContent()).hasSize(2);
        assertThat(window.getContent()).allMatch(w -> w.getStatus() == WidgetStatus.ACTIVE);
    }

    @ParameterizedTest(name = "status filter: {0}")
    @EnumSource(WidgetStatus.class)
    @DisplayName("hasStatus — works for all status values")
    void hasStatus_AllValues(WidgetStatus status) {
        persistWidget(makeWidget(withName("status-test"), withStatus(status)));

        var window = firstWindow(WidgetSpecs.belongsToTenant(TENANT_A)
            .and(WidgetSpecs.hasStatus(status)));

        assertThat(window.getContent()).hasSize(1);
        assertThat(window.getContent().get(0).getStatus()).isEqualTo(status);
    }

    @Test
    @DisplayName("nameContains — case-insensitive LIKE search")
    void nameContains_CaseInsensitive() {
        persistWidget(makeWidget(withName("Alpha Widget")));
        persistWidget(makeWidget(withName("Beta Widget")));
        persistWidget(makeWidget(withName("Something Else")));

        var window = firstWindow(WidgetSpecs.belongsToTenant(TENANT_A)
            .and(WidgetSpecs.nameContains("widget")));

        assertThat(window.getContent()).hasSize(2);
        assertThat(window.getContent())
            .allMatch(w -> w.getName().toLowerCase().contains("widget"));
    }

    @Test
    @DisplayName("nameContains — empty search returns all")
    void nameContains_EmptySearch() {
        persistWidget(makeWidget(withName("Widget A")));
        persistWidget(makeWidget(withName("Widget B")));

        var window = firstWindow(WidgetSpecs.belongsToTenant(TENANT_A)
            .and(WidgetSpecs.nameContains("")));

        assertThat(window.getContent()).hasSize(2);
    }

    @Test
    @DisplayName("countByTenantIdAndStatusIn — JPQL count scoped to tenant")
    void countByTenantIdAndStatusIn_ScopedToTenant() {
        persistWidget(makeWidget(withTenantId(TENANT_A), withName("a-active"), withStatus(WidgetStatus.ACTIVE)));
        persistWidget(makeWidget(withTenantId(TENANT_A), withName("a-inactive"), withStatus(WidgetStatus.INACTIVE)));
        persistWidget(makeWidget(withTenantId(TENANT_B), withName("b-active"), withStatus(WidgetStatus.ACTIVE)));

        var count = repository.countByTenantIdAndStatusIn(
            TENANT_A, List.of(WidgetStatus.ACTIVE, WidgetStatus.INACTIVE));

        assertThat(count).isEqualTo(2);
    }
}
```

## Specification-Based Filtering Tests

```java
@Nested
@DisplayName("Specification API filtering")
class SpecificationTests {

    @Test
    @DisplayName("belongsToTenant + hasStatus — compound filter")
    void compoundSpecification_FiltersCorrectly() {
        persistWidget(makeWidget(withTenantId(TENANT_A), withName("active-a"), withStatus(WidgetStatus.ACTIVE)));
        persistWidget(makeWidget(withTenantId(TENANT_A), withName("archived-a"), withStatus(WidgetStatus.ARCHIVED)));
        persistWidget(makeWidget(withTenantId(TENANT_B), withName("active-b"), withStatus(WidgetStatus.ACTIVE)));

        var spec = WidgetSpecs.belongsToTenant(TENANT_A)
            .and(WidgetSpecs.hasStatus(WidgetStatus.ACTIVE));

        var window = firstWindow(spec);

        assertThat(window.getContent()).hasSize(1);
        assertThat(window.getContent().get(0).getName()).isEqualTo("active-a");
    }

    @Test
    @DisplayName("hasStatusIn — any of several statuses, still tenant-scoped")
    void hasStatusIn_FiltersCorrectly() {
        persistWidget(makeWidget(withTenantId(TENANT_A), withName("active-a"), withStatus(WidgetStatus.ACTIVE)));
        persistWidget(makeWidget(withTenantId(TENANT_A), withName("inactive-a"), withStatus(WidgetStatus.INACTIVE)));
        persistWidget(makeWidget(withTenantId(TENANT_A), withName("archived-a"), withStatus(WidgetStatus.ARCHIVED)));
        persistWidget(makeWidget(withTenantId(TENANT_B), withName("active-b"), withStatus(WidgetStatus.ACTIVE)));

        var window = firstWindow(WidgetSpecs.belongsToTenant(TENANT_A)
            .and(WidgetSpecs.hasStatusIn(List.of(WidgetStatus.ACTIVE, WidgetStatus.INACTIVE))));

        assertThat(window.getContent())
            .extracting(Widget::getName)
            .containsExactlyInAnyOrder("active-a", "inactive-a");
    }

    @Test
    @DisplayName("nameContains — case-insensitive search via Specification")
    void nameContainsSpec_CaseInsensitive() {
        persistWidget(makeWidget(withName("My Cool Widget")));
        persistWidget(makeWidget(withName("Another Thing")));

        var spec = WidgetSpecs.belongsToTenant(TENANT_A)
            .and(WidgetSpecs.nameContains("cool"));

        var window = firstWindow(spec);

        assertThat(window.getContent()).hasSize(1);
        assertThat(window.getContent().get(0).getName()).isEqualTo("My Cool Widget");
    }

    @Test
    @DisplayName("createdBetween — date range filter")
    void createdBetweenSpec_FiltersCorrectly() {
        var now = Instant.now();
        persistWidget(makeWidget(withName("old"), withCreatedAt(now.minus(30, ChronoUnit.DAYS))));
        persistWidget(makeWidget(withName("recent"), withCreatedAt(now.minus(1, ChronoUnit.DAYS))));
        persistWidget(makeWidget(withName("today"), withCreatedAt(now)));

        var spec = WidgetSpecs.belongsToTenant(TENANT_A)
            .and(WidgetSpecs.createdBetween(
                now.minus(7, ChronoUnit.DAYS),
                now.plus(1, ChronoUnit.DAYS)
            ));

        var window = firstWindow(spec);

        assertThat(window.getContent()).hasSize(2);
        assertThat(window.getContent())
            .extracting(Widget::getName)
            .containsExactlyInAnyOrder("recent", "today");
    }

    @Test
    @DisplayName("null specification parameters — no-op (returns all)")
    void nullSpecParams_ReturnsAll() {
        persistWidget(makeWidget(withName("widget-1")));
        persistWidget(makeWidget(withName("widget-2")));

        var spec = WidgetSpecs.belongsToTenant(TENANT_A)
            .and(WidgetSpecs.hasStatus(null))       // null status = no filter
            .and(WidgetSpecs.nameContains(null));    // null name = no filter

        var window = firstWindow(spec);

        assertThat(window.getContent()).hasSize(2);
    }
}
```

## Constraint Tests

```java
@Nested
@DisplayName("Database constraints")
class ConstraintTests {

    @Test
    @DisplayName("unique constraint — duplicate tenant + name throws DataIntegrityViolation with SQLSTATE 23505")
    void uniqueName_PerTenant_ThrowsOnDuplicate() {
        persistWidget(makeWidget(withName("Unique Widget")));

        var duplicate = makeWidget(withName("Unique Widget"));

        // GlobalExceptionHandler maps 23505 to 409 CONFLICT with a generic message — this proves
        // the real driver reports that SQLSTATE through Spring's exception translation.
        assertThatThrownBy(() -> {
            repository.save(duplicate);
            entityManager.flush();
        }).isInstanceOf(DataIntegrityViolationException.class)
          .satisfies(ex -> assertThat(sqlState(ex)).isEqualTo("23505"));
    }

    @Test
    @DisplayName("same name allowed for different tenants")
    void sameName_DifferentTenants_Allowed() {
        persistWidget(makeWidget(withTenantId(TENANT_A), withName("Shared Name")));

        var widgetB = makeWidget(withTenantId(TENANT_B), withName("Shared Name"));

        assertThatNoException().isThrownBy(() -> {
            repository.save(widgetB);
            entityManager.flush();
        });
    }

    @Test
    @DisplayName("not-null constraint — name cannot be null")
    void nullName_ThrowsConstraintViolation() {
        var widget = makeWidget();
        widget.setName(null);

        assertThatThrownBy(() -> {
            repository.save(widget);
            entityManager.flush();
        }).isInstanceOf(Exception.class); // DataIntegrityViolationException or ConstraintViolationException
    }
}
```

## Bulk Operation Tests

```java
@Nested
@DisplayName("Bulk operations")
class BulkOperationTests {

    @Test
    @DisplayName("bulkUpdateStatus — updates matching rows and returns count")
    void bulkUpdateStatus_UpdatesMatchingRows() {
        persistWidget(makeWidget(withName("active-1"), withStatus(WidgetStatus.ACTIVE)));
        persistWidget(makeWidget(withName("active-2"), withStatus(WidgetStatus.ACTIVE)));
        persistWidget(makeWidget(withName("archived-1"), withStatus(WidgetStatus.ARCHIVED)));

        var updatedCount = repository.bulkUpdateStatus(
            TENANT_A, WidgetStatus.ACTIVE, WidgetStatus.INACTIVE);
        entityManager.flush();
        entityManager.clear();

        assertThat(updatedCount).isEqualTo(2);

        var active = firstWindow(WidgetSpecs.belongsToTenant(TENANT_A)
            .and(WidgetSpecs.hasStatus(WidgetStatus.ACTIVE)));
        assertThat(active.getContent()).isEmpty();

        var inactive = firstWindow(WidgetSpecs.belongsToTenant(TENANT_A)
            .and(WidgetSpecs.hasStatus(WidgetStatus.INACTIVE)));
        assertThat(inactive.getContent()).hasSize(2);
    }

    @Test
    @DisplayName("bulkSoftDelete — soft deletes specified IDs")
    void bulkSoftDelete_DeletesSpecifiedIds() {
        var w1 = persistWidget(makeWidget(withName("keep")));
        var w2 = persistWidget(makeWidget(withName("delete-1")));
        var w3 = persistWidget(makeWidget(withName("delete-2")));

        var deletedCount = repository.bulkSoftDelete(
            TENANT_A, List.of(w2.getId(), w3.getId()));
        entityManager.flush();
        entityManager.clear();

        assertThat(deletedCount).isEqualTo(2);

        var remaining = firstWindow(WidgetSpecs.belongsToTenant(TENANT_A));
        assertThat(remaining.getContent()).hasSize(1);
        assertThat(remaining.getContent().get(0).getId()).isEqualTo(w1.getId());
    }
}
```

## Test Data Setup with @Sql

```java
@Nested
@DisplayName("@Sql data setup")
class SqlDataSetupTests {

    @Test
    @Sql("/db/testdata/widgets.sql")
    @DisplayName("@Sql — loads test data from SQL file")
    void sqlSetup_LoadsTestData() {
        // widgets.sql inserts known test data
        var window = firstWindow(WidgetSpecs.belongsToTenant(TENANT_A));

        assertThat(window.getContent()).isNotEmpty();
    }
}
```

## Critical Rules

- Repository tests MUST use `@DataJpaTest` + `@AutoConfigureTestDatabase(replace = NONE)` — JPA slice with real Postgres.
- Testcontainers MUST be used for PostgreSQL — never use H2 or embedded databases (SQL dialect differences cause false passes).
- `@ServiceConnection` auto-configures datasource from the container — no manual URL setup needed.
- Use `TestEntityManager` for direct persistence/flush/clear — ensures clean reads from DB.
- Call `entityManager.clear()` after writes to detach entities and force fresh DB reads.
- Use `@AfterEach` cleanup to ensure test isolation — `repository.deleteAll()` + flush + clear.
- Time values: Postgres TIMESTAMPTZ has microsecond precision — use `Instant.now()` without truncation (JPA handles it).
- Test factories MUST generate unique names with `UUID.randomUUID()` to prevent constraint violations.
- Lists are keyset-scrolled (`findBy(spec, q -> q.sortBy(sort).limit(n).scroll(position))`) — there is no `Page`/`Pageable`/offset API to test.
- Scroll tests MUST verify: window size, `hasNext`, following `positionAt(size - 1)` visits every row exactly once, and no duplicates or gaps when a row is inserted between windows.
- Tenant isolation tests MUST verify: findById returns empty, every scroll starts from `belongsToTenant` and returns only that tenant's data, a replayed position never crosses tenants, exists/count scoped to tenant.
- Constraint tests MUST check the SQLSTATE (23505 unique) that `GlobalExceptionHandler` maps to 409 `CONFLICT`.
- Optimistic locking tests MUST simulate two concurrent reads and verify second save throws `ObjectOptimisticLockingFailureException`.
- Soft delete tests MUST verify: row exists with `deleted_at` set, excluded from all queries, name reuse allowed.
- Constraint tests MUST verify: unique violations for same tenant, allowed for different tenants.
- Specification tests MUST verify: compound filters, null parameters (no-op), date ranges.
- Bulk operations MUST verify: affected row count, remaining data state.
- NEVER use `t.Parallel()` equivalent — JPA integration tests share the database and must run sequentially per test class.
- Container reuse (`withReuse(true)`) speeds up test suites — configure `testcontainers.reuse.enable=true` in `~/.testcontainers.properties`.
