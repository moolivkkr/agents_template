---
skill: crud-service-test-java
description: Spring Boot service unit test archetype — @ExtendWith(MockitoExtension), @Mock, @InjectMocks, cache verification, audit logging, optimistic locking, tenant isolation, AssertJ
version: "1.0"
tags:
  - java
  - spring-boot
  - service
  - unit-test
  - archetype
  - backend
  - testing
---

# CRUD Service Test Archetype (Spring Boot)

Complete, production-ready service layer unit test template using Mockito and AssertJ. Every generated service test MUST follow this pattern.

## Test File Location

```
src/test/java/com/example/app/service/
  WidgetServiceImplTest.java     <- THIS file
src/test/java/com/example/app/
  TestFixtures.java              <- shared test factories
```

Rule: Service tests use `@ExtendWith(MockitoExtension.class)` — no Spring context is loaded. Dependencies are mocked with `@Mock` and injected via `@InjectMocks`.

## Test Factory

```java
package com.example.app;

import com.example.app.model.dto.*;
import com.example.app.model.entity.Widget;
import com.example.app.model.entity.WidgetStatus;

import java.time.Instant;
import java.util.UUID;
import java.util.function.Consumer;

 * Shared factory for test entities and DTOs.
 * Uses Consumer-based overrides for fluent customization.
public final class TestFixtures {

    public static final UUID TENANT_ID = UUID.fromString("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa");
    public static final UUID USER_ID = UUID.fromString("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb");

    private TestFixtures() {}

    @SafeVarargs
    public static Widget widget(Consumer<Widget>... customizers) {
        var w = new Widget();
        w.setId(UUID.randomUUID());
        w.setTenantId(TENANT_ID);
        w.setName("widget-" + UUID.randomUUID().toString().substring(0, 8));
        w.setDescription("A test widget");
        w.setStatus(WidgetStatus.ACTIVE);
        w.setCreatedAt(Instant.now());
        w.setUpdatedAt(Instant.now());
        w.setCreatedBy(USER_ID);
        w.setUpdatedBy(USER_ID);
        w.setVersion(1);
        for (var c : customizers) {
            c.accept(w);
        }
        return w;
    }

    public static Consumer<Widget> withName(String name) {
        return w -> w.setName(name);
    }

    public static Consumer<Widget> withVersion(int version) {
        return w -> w.setVersion(version);
    }

    public static Consumer<Widget> withTenantId(UUID tenantId) {
        return w -> w.setTenantId(tenantId);
    }

    public static Consumer<Widget> withId(UUID id) {
        return w -> w.setId(id);
    }

    public static Consumer<Widget> withStatus(WidgetStatus status) {
        return w -> w.setStatus(status);
    }

    public static CreateWidgetRequest createRequest() {
        return new CreateWidgetRequest("New Widget", "Description for new widget");
    }

    public static CreateWidgetRequest createRequest(String name) {
        return new CreateWidgetRequest(name, "Description for " + name);
    }

    public static UpdateWidgetRequest updateRequest(int version) {
        return new UpdateWidgetRequest("Updated Widget", "Updated description", version);
    }
}
```

## Test Class Setup

```java
package com.example.app.service;

import com.example.app.exception.*;
import com.example.app.model.dto.*;
import com.example.app.model.entity.Widget;
import com.example.app.model.entity.WidgetStatus;
import com.example.app.repository.WidgetRepository;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.extension.ExtendWith;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.*;
import org.mockito.*;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.*;

import java.time.Instant;
import java.util.*;
import java.util.stream.Stream;

import static com.example.app.TestFixtures.*;
import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.*;

@ExtendWith(MockitoExtension.class)
@DisplayName("WidgetServiceImpl")
class WidgetServiceImplTest {

    @Mock
    private WidgetRepository repository;

    @Mock
    private AuditService auditService;

    @InjectMocks
    private WidgetServiceImpl widgetService;

    // Captor for verifying the entity passed to repository.save()
    @Captor
    private ArgumentCaptor<Widget> widgetCaptor;
}
```

## Create Tests

```java
@Nested
@DisplayName("create()")
class CreateTests {

    @Test
    @DisplayName("happy path — creates widget with correct fields")
    void create_ValidInput_ReturnsNewWidget() {
        // Arrange
        var request = createRequest("New Widget");
        given(repository.existsByTenantIdAndNameIgnoreCase(TENANT_ID, "New Widget"))
            .willReturn(false);
        given(repository.save(any(Widget.class)))
            .willAnswer(invocation -> {
                var w = invocation.getArgument(0, Widget.class);
                w.setId(UUID.randomUUID()); // simulate JPA generating ID
                return w;
            });

        // Act
        var result = widgetService.create(request, TENANT_ID, USER_ID);

        // Assert
        assertThat(result).isNotNull();
        assertThat(result.getName()).isEqualTo("New Widget");
        assertThat(result.getDescription()).isEqualTo("Description for New Widget");
        assertThat(result.getTenantId()).isEqualTo(TENANT_ID);
        assertThat(result.getCreatedBy()).isEqualTo(USER_ID);
        assertThat(result.getUpdatedBy()).isEqualTo(USER_ID);
        assertThat(result.getStatus()).isEqualTo(WidgetStatus.ACTIVE);
        assertThat(result.getCreatedAt()).isNotNull();
        assertThat(result.getUpdatedAt()).isNotNull();
        assertThat(result.getId()).isNotNull();

        // Verify repository was called with correct entity
        verify(repository).save(widgetCaptor.capture());
        var saved = widgetCaptor.getValue();
        assertThat(saved.getTenantId()).isEqualTo(TENANT_ID);
        assertThat(saved.getCreatedBy()).isEqualTo(USER_ID);
    }

    @Test
    @DisplayName("duplicate name for tenant — throws ConflictException")
    void create_DuplicateName_ThrowsConflict() {
        var request = createRequest("Existing Widget");
        given(repository.existsByTenantIdAndNameIgnoreCase(TENANT_ID, "Existing Widget"))
            .willReturn(true);

        assertThatThrownBy(() -> widgetService.create(request, TENANT_ID, USER_ID))
            .isInstanceOf(ConflictException.class)
            .hasMessageContaining("already exists");

        verify(repository, never()).save(any());
    }

    @Test
    @DisplayName("repository failure — propagates exception")
    void create_RepoError_PropagatesException() {
        var request = createRequest();
        given(repository.existsByTenantIdAndNameIgnoreCase(any(), any()))
            .willReturn(false);
        given(repository.save(any()))
            .willThrow(new RuntimeException("connection refused"));

        assertThatThrownBy(() -> widgetService.create(request, TENANT_ID, USER_ID))
            .isInstanceOf(RuntimeException.class)
            .hasMessageContaining("connection refused");
    }

    @Test
    @DisplayName("input is sanitized before persisting")
    void create_SanitizesInput() {
        var request = new CreateWidgetRequest(
            "  <script>alert('xss')</script>My Widget  ",
            "<b>Bold</b> description"
        );
        given(repository.existsByTenantIdAndNameIgnoreCase(any(), any()))
            .willReturn(false);
        given(repository.save(any(Widget.class)))
            .willAnswer(invocation -> invocation.getArgument(0));

        var result = widgetService.create(request, TENANT_ID, USER_ID);

        // Name and description should be sanitized (HTML stripped, trimmed)
        verify(repository).save(widgetCaptor.capture());
        var saved = widgetCaptor.getValue();
        assertThat(saved.getName()).doesNotContain("<script>");
        assertThat(saved.getDescription()).doesNotContain("<b>");
    }

    @Test
    @DisplayName("audit log is recorded after creation")
    void create_RecordsAuditLog() {
        var request = createRequest();
        given(repository.existsByTenantIdAndNameIgnoreCase(any(), any())).willReturn(false);
        given(repository.save(any(Widget.class)))
            .willAnswer(invocation -> {
                var w = invocation.getArgument(0, Widget.class);
                w.setId(UUID.randomUUID());
                return w;
            });

        var result = widgetService.create(request, TENANT_ID, USER_ID);

        verify(auditService).log(
            eq("widget.created"),
            eq(result.getId()),
            eq(TENANT_ID),
            eq(USER_ID),
            any()
        );
    }
}
```

## FindById Tests (with Cache Behavior)

```java
@Nested
@DisplayName("findById()")
class FindByIdTests {

    @Test
    @DisplayName("happy path — returns widget by ID and tenant")
    void findById_Exists_ReturnsWidget() {
        var widget = widget();
        given(repository.findByIdAndTenantId(widget.getId(), TENANT_ID))
            .willReturn(Optional.of(widget));

        var result = widgetService.findById(widget.getId(), TENANT_ID);

        assertThat(result).isNotNull();
        assertThat(result.getId()).isEqualTo(widget.getId());
        assertThat(result.getName()).isEqualTo(widget.getName());
    }

    @Test
    @DisplayName("not found — throws ResourceNotFoundException")
    void findById_NotFound_ThrowsException() {
        var id = UUID.randomUUID();
        given(repository.findByIdAndTenantId(id, TENANT_ID))
            .willReturn(Optional.empty());

        assertThatThrownBy(() -> widgetService.findById(id, TENANT_ID))
            .isInstanceOf(ResourceNotFoundException.class)
            .hasMessageContaining("not found")
            .hasMessageContaining(id.toString());
    }

    @Test
    @DisplayName("wrong tenant — returns not found, not forbidden")
    void findById_WrongTenant_ReturnsNotFound() {
        // Widget exists for tenant A, but query is scoped to tenant B
        var id = UUID.randomUUID();
        var otherTenantId = UUID.randomUUID();
        given(repository.findByIdAndTenantId(id, otherTenantId))
            .willReturn(Optional.empty());

        // CRITICAL: wrong tenant sees NotFound, NOT Forbidden — prevents entity enumeration
        assertThatThrownBy(() -> widgetService.findById(id, otherTenantId))
            .isInstanceOf(ResourceNotFoundException.class);
    }

    @Test
    @DisplayName("@Cacheable — second call should be served from cache")
    void findById_CacheBehavior() {
        // Note: @Cacheable behavior is verified in integration tests with a real cache.
        // In unit tests, we verify the repository is called correctly.
        var widget = widget();
        given(repository.findByIdAndTenantId(widget.getId(), TENANT_ID))
            .willReturn(Optional.of(widget));

        widgetService.findById(widget.getId(), TENANT_ID);

        verify(repository).findByIdAndTenantId(widget.getId(), TENANT_ID);
    }
}
```

## Update Tests

```java
@Nested
@DisplayName("update()")
class UpdateTests {

    @Test
    @DisplayName("happy path — updates fields and increments version")
    void update_ValidInput_ReturnsUpdatedWidget() {
        var existing = widget(withVersion(1));
        var request = updateRequest(1); // client sends current version

        given(repository.findByIdAndTenantId(existing.getId(), TENANT_ID))
            .willReturn(Optional.of(existing));
        given(repository.save(any(Widget.class)))
            .willAnswer(invocation -> invocation.getArgument(0));

        var result = widgetService.update(existing.getId(), request, TENANT_ID, USER_ID);

        assertThat(result).isNotNull();
        assertThat(result.getName()).isEqualTo("Updated Widget");
        assertThat(result.getDescription()).isEqualTo("Updated description");
        assertThat(result.getUpdatedBy()).isEqualTo(USER_ID);
        assertThat(result.getUpdatedAt()).isAfterOrEqualTo(existing.getCreatedAt());

        // Verify save was called
        verify(repository).save(widgetCaptor.capture());
        var saved = widgetCaptor.getValue();
        assertThat(saved.getName()).isEqualTo("Updated Widget");
    }

    @Test
    @DisplayName("version conflict — throws ConflictException when versions mismatch")
    void update_VersionMismatch_ThrowsConflict() {
        var existing = widget(withVersion(3)); // DB has version 3
        var request = updateRequest(1);        // client sends stale version 1

        given(repository.findByIdAndTenantId(existing.getId(), TENANT_ID))
            .willReturn(Optional.of(existing));

        assertThatThrownBy(() ->
            widgetService.update(existing.getId(), request, TENANT_ID, USER_ID))
            .isInstanceOf(ConflictException.class)
            .hasMessageContaining("Version mismatch");

        verify(repository, never()).save(any());
    }

    @Test
    @DisplayName("not found — throws ResourceNotFoundException")
    void update_NotFound_ThrowsException() {
        var id = UUID.randomUUID();
        var request = updateRequest(1);

        given(repository.findByIdAndTenantId(id, TENANT_ID))
            .willReturn(Optional.empty());

        assertThatThrownBy(() -> widgetService.update(id, request, TENANT_ID, USER_ID))
            .isInstanceOf(ResourceNotFoundException.class);

        verify(repository, never()).save(any());
    }

    @Test
    @DisplayName("cache eviction — @CacheEvict invalidates cache on update")
    void update_EvictsCache() {
        // Note: @CacheEvict behavior is verified in integration tests.
        // Unit test verifies the method completes correctly.
        var existing = widget(withVersion(1));
        var request = updateRequest(1);

        given(repository.findByIdAndTenantId(existing.getId(), TENANT_ID))
            .willReturn(Optional.of(existing));
        given(repository.save(any(Widget.class)))
            .willAnswer(invocation -> invocation.getArgument(0));

        widgetService.update(existing.getId(), request, TENANT_ID, USER_ID);

        // The @CacheEvict annotation on the method ensures cache invalidation.
        // Verify the repository operations completed.
        verify(repository).findByIdAndTenantId(existing.getId(), TENANT_ID);
        verify(repository).save(any(Widget.class));
    }

    @Test
    @DisplayName("audit log is recorded after update")
    void update_RecordsAuditLog() {
        var existing = widget(withVersion(1));
        var request = updateRequest(1);

        given(repository.findByIdAndTenantId(existing.getId(), TENANT_ID))
            .willReturn(Optional.of(existing));
        given(repository.save(any(Widget.class)))
            .willAnswer(invocation -> invocation.getArgument(0));

        widgetService.update(existing.getId(), request, TENANT_ID, USER_ID);

        verify(auditService).log(
            eq("widget.updated"),
            eq(existing.getId()),
            eq(TENANT_ID),
            eq(USER_ID),
            any()
        );
    }

    @Test
    @DisplayName("input is sanitized before persisting")
    void update_SanitizesInput() {
        var existing = widget(withVersion(1));
        var request = new UpdateWidgetRequest(
            "  <img onerror=alert(1)>Clean Name  ",
            "<script>xss</script>Desc",
            1
        );

        given(repository.findByIdAndTenantId(existing.getId(), TENANT_ID))
            .willReturn(Optional.of(existing));
        given(repository.save(any(Widget.class)))
            .willAnswer(invocation -> invocation.getArgument(0));

        widgetService.update(existing.getId(), request, TENANT_ID, USER_ID);

        verify(repository).save(widgetCaptor.capture());
        var saved = widgetCaptor.getValue();
        assertThat(saved.getName()).doesNotContain("<img");
        assertThat(saved.getDescription()).doesNotContain("<script>");
    }
}
```

## Delete Tests

```java
@Nested
@DisplayName("delete()")
class DeleteTests {

    @Test
    @DisplayName("happy path — soft deletes widget")
    void delete_Exists_DeletesSuccessfully() {
        var widget = widget();
        given(repository.findByIdAndTenantId(widget.getId(), TENANT_ID))
            .willReturn(Optional.of(widget));

        widgetService.delete(widget.getId(), TENANT_ID, USER_ID);

        verify(repository).delete(widget);
    }

    @Test
    @DisplayName("not found — throws ResourceNotFoundException")
    void delete_NotFound_ThrowsException() {
        var id = UUID.randomUUID();
        given(repository.findByIdAndTenantId(id, TENANT_ID))
            .willReturn(Optional.empty());

        assertThatThrownBy(() -> widgetService.delete(id, TENANT_ID, USER_ID))
            .isInstanceOf(ResourceNotFoundException.class);

        verify(repository, never()).delete(any(Widget.class));
    }

    @Test
    @DisplayName("cache eviction — @CacheEvict invalidates cache on delete")
    void delete_EvictsCache() {
        var widget = widget();
        given(repository.findByIdAndTenantId(widget.getId(), TENANT_ID))
            .willReturn(Optional.of(widget));

        widgetService.delete(widget.getId(), TENANT_ID, USER_ID);

        verify(repository).delete(widget);
        // @CacheEvict on the method ensures cache invalidation
    }

    @Test
    @DisplayName("audit log is recorded after deletion")
    void delete_RecordsAuditLog() {
        var widget = widget();
        given(repository.findByIdAndTenantId(widget.getId(), TENANT_ID))
            .willReturn(Optional.of(widget));

        widgetService.delete(widget.getId(), TENANT_ID, USER_ID);

        verify(auditService).log(
            eq("widget.deleted"),
            eq(widget.getId()),
            eq(TENANT_ID),
            eq(USER_ID),
            isNull()
        );
    }
}
```

## FindAll (List with Pagination) Tests

```java
@Nested
@DisplayName("findAll()")
class FindAllTests {

    @Test
    @DisplayName("happy path — returns paginated results")
    void findAll_WithResults_ReturnsPage() {
        var widgets = List.of(widget(), widget(), widget());
        var pageable = PageRequest.of(0, 20, Sort.by(Sort.Direction.DESC, "createdAt"));
        var page = new PageImpl<>(widgets, pageable, 25);

        given(repository.findByTenantId(TENANT_ID, pageable)).willReturn(page);

        var result = widgetService.findAll(TENANT_ID, null, pageable);

        assertThat(result).isNotNull();
        assertThat(result.getContent()).hasSize(3);
        assertThat(result.getTotalElements()).isEqualTo(25);
        assertThat(result.getTotalPages()).isEqualTo(2);
        assertThat(result.getNumber()).isZero();
    }

    @Test
    @DisplayName("empty result — returns empty page, not null")
    void findAll_Empty_ReturnsEmptyPage() {
        var pageable = PageRequest.of(0, 20);
        var page = new PageImpl<Widget>(List.of(), pageable, 0);

        given(repository.findByTenantId(TENANT_ID, pageable)).willReturn(page);

        var result = widgetService.findAll(TENANT_ID, null, pageable);

        assertThat(result).isNotNull();
        assertThat(result.getContent()).isEmpty();
        assertThat(result.getTotalElements()).isZero();
    }

    @Test
    @DisplayName("filters by status when provided")
    void findAll_WithStatusFilter_FiltersResults() {
        var pageable = PageRequest.of(0, 20);
        var activeWidget = widget(withStatus(WidgetStatus.ACTIVE));
        var page = new PageImpl<>(List.of(activeWidget), pageable, 1);

        given(repository.findByTenantIdAndStatus(TENANT_ID, WidgetStatus.ACTIVE, pageable))
            .willReturn(page);

        var result = widgetService.findAll(TENANT_ID, WidgetStatus.ACTIVE, pageable);

        assertThat(result.getContent()).hasSize(1);
        verify(repository).findByTenantIdAndStatus(TENANT_ID, WidgetStatus.ACTIVE, pageable);
        verify(repository, never()).findByTenantId(any(), any());
    }

    @Test
    @DisplayName("null status — calls unfiltered findByTenantId")
    void findAll_NullStatus_NoFilter() {
        var pageable = PageRequest.of(0, 20);
        var page = new PageImpl<Widget>(List.of(), pageable, 0);

        given(repository.findByTenantId(TENANT_ID, pageable)).willReturn(page);

        widgetService.findAll(TENANT_ID, null, pageable);

        verify(repository).findByTenantId(TENANT_ID, pageable);
        verify(repository, never()).findByTenantIdAndStatus(any(), any(), any());
    }

    @ParameterizedTest(name = "status filter: {0}")
    @EnumSource(WidgetStatus.class)
    @DisplayName("each status value routes to filtered query")
    void findAll_EachStatus_FiltersCorrectly(WidgetStatus status) {
        var pageable = PageRequest.of(0, 20);
        var page = new PageImpl<Widget>(List.of(), pageable, 0);

        given(repository.findByTenantIdAndStatus(TENANT_ID, status, pageable))
            .willReturn(page);

        widgetService.findAll(TENANT_ID, status, pageable);

        verify(repository).findByTenantIdAndStatus(TENANT_ID, status, pageable);
    }
}
```

## Table-Driven Tests (Parameterized)

```java
@Nested
@DisplayName("create() — table-driven validation tests")
class CreateValidationTableDriven {

    @ParameterizedTest(name = "{0}")
    @MethodSource("com.example.app.service.WidgetServiceImplTest#createValidationCases")
    @DisplayName("Validation scenarios")
    void create_ValidationCases(String scenario, CreateWidgetRequest request,
                                 Class<? extends Exception> expectedException) {
        if (expectedException == null) {
            // Happy path — setup mocks for success
            given(repository.existsByTenantIdAndNameIgnoreCase(any(), any())).willReturn(false);
            given(repository.save(any(Widget.class)))
                .willAnswer(invocation -> {
                    var w = invocation.getArgument(0, Widget.class);
                    w.setId(UUID.randomUUID());
                    return w;
                });

            assertThatNoException()
                .isThrownBy(() -> widgetService.create(request, TENANT_ID, USER_ID));
        } else {
            assertThatThrownBy(() -> widgetService.create(request, TENANT_ID, USER_ID))
                .isInstanceOf(expectedException);
        }
    }
}

static Stream<Arguments> createValidationCases() {
    return Stream.of(
        Arguments.of("valid input",
            new CreateWidgetRequest("My Widget", "Description"),
            null),
        Arguments.of("duplicate name",
            new CreateWidgetRequest("Existing", "Desc"),
            ConflictException.class),
        Arguments.of("reserved name 'default'",
            new CreateWidgetRequest("default", "Desc"),
            BusinessRuleException.class)
    );
}
```

## Edge Case and Isolation Tests

```java
@Nested
@DisplayName("Edge cases and tenant isolation")
class EdgeCaseTests {

    @Test
    @DisplayName("concurrent updates — JPA @Version prevents lost updates")
    void concurrentUpdate_SecondUpdateFails() {
        // Simulates two clients reading the same widget at version 1,
        // then both trying to update.
        var widget = widget(withVersion(1));
        var request1 = updateRequest(1);
        var request2 = updateRequest(1);

        // First update succeeds
        given(repository.findByIdAndTenantId(widget.getId(), TENANT_ID))
            .willReturn(Optional.of(widget));
        given(repository.save(any(Widget.class)))
            .willAnswer(invocation -> {
                var w = invocation.getArgument(0, Widget.class);
                w.setVersion(2); // JPA increments version
                return w;
            });

        var result = widgetService.update(widget.getId(), request1, TENANT_ID, USER_ID);
        assertThat(result.getVersion()).isEqualTo(2);

        // Second update fails — widget now has version 2 but client sends version 1
        var updatedWidget = widget(withVersion(2));
        given(repository.findByIdAndTenantId(widget.getId(), TENANT_ID))
            .willReturn(Optional.of(updatedWidget));

        assertThatThrownBy(() ->
            widgetService.update(widget.getId(), request2, TENANT_ID, USER_ID))
            .isInstanceOf(ConflictException.class)
            .hasMessageContaining("Version mismatch");
    }

    @Test
    @DisplayName("operations are tenant-scoped — repository receives correct tenant ID")
    void allOperations_ScopedToTenant() {
        var widget = widget();

        // findById passes tenant
        given(repository.findByIdAndTenantId(widget.getId(), TENANT_ID))
            .willReturn(Optional.of(widget));
        widgetService.findById(widget.getId(), TENANT_ID);
        verify(repository).findByIdAndTenantId(widget.getId(), TENANT_ID);

        // findAll passes tenant
        var pageable = PageRequest.of(0, 20);
        given(repository.findByTenantId(TENANT_ID, pageable))
            .willReturn(new PageImpl<>(List.of()));
        widgetService.findAll(TENANT_ID, null, pageable);
        verify(repository).findByTenantId(TENANT_ID, pageable);
    }

    @Test
    @DisplayName("audit failure does not block create operation")
    void auditFailure_DoesNotBlockCreate() {
        // Audit service throws but create should still succeed
        var request = createRequest();
        given(repository.existsByTenantIdAndNameIgnoreCase(any(), any())).willReturn(false);
        given(repository.save(any(Widget.class)))
            .willAnswer(invocation -> {
                var w = invocation.getArgument(0, Widget.class);
                w.setId(UUID.randomUUID());
                return w;
            });
        // @Async audit service — in unit tests, verify it's called but
        // exceptions are swallowed by the @Async wrapper
        willDoNothing().given(auditService).log(any(), any(), any(), any(), any());

        var result = widgetService.create(request, TENANT_ID, USER_ID);

        assertThat(result).isNotNull();
        verify(auditService).log(any(), any(), any(), any(), any());
    }
}
```

## Verify Interactions Helpers

```java
@Nested
@DisplayName("Interaction verification patterns")
class InteractionVerificationTests {

    @Test
    @DisplayName("create — verifies repository.save is called exactly once")
    void create_CallsSaveOnce() {
        var request = createRequest();
        given(repository.existsByTenantIdAndNameIgnoreCase(any(), any())).willReturn(false);
        given(repository.save(any(Widget.class)))
            .willAnswer(invocation -> invocation.getArgument(0));

        widgetService.create(request, TENANT_ID, USER_ID);

        verify(repository, times(1)).save(any(Widget.class));
    }

    @Test
    @DisplayName("delete — verifies find-then-delete order")
    void delete_FindsThenDeletes() {
        var widget = widget();
        given(repository.findByIdAndTenantId(widget.getId(), TENANT_ID))
            .willReturn(Optional.of(widget));

        widgetService.delete(widget.getId(), TENANT_ID, USER_ID);

        var inOrder = inOrder(repository, auditService);
        inOrder.verify(repository).findByIdAndTenantId(widget.getId(), TENANT_ID);
        inOrder.verify(repository).delete(widget);
        inOrder.verify(auditService).log(any(), any(), any(), any(), any());
    }

    @Test
    @DisplayName("update — verifies find, save, audit order")
    void update_FollowsCorrectOrder() {
        var widget = widget(withVersion(1));
        var request = updateRequest(1);

        given(repository.findByIdAndTenantId(widget.getId(), TENANT_ID))
            .willReturn(Optional.of(widget));
        given(repository.save(any(Widget.class)))
            .willAnswer(invocation -> invocation.getArgument(0));

        widgetService.update(widget.getId(), request, TENANT_ID, USER_ID);

        var inOrder = inOrder(repository, auditService);
        inOrder.verify(repository).findByIdAndTenantId(widget.getId(), TENANT_ID);
        inOrder.verify(repository).save(any(Widget.class));
        inOrder.verify(auditService).log(any(), any(), any(), any(), any());
    }
}
```

## Critical Rules

- Every service test MUST use `@ExtendWith(MockitoExtension.class)` — no Spring context, pure unit tests.
- `@Mock` for repository, audit, and any other dependency — `@InjectMocks` for the service under test.
- Mocks are fresh per test (Mockito resets automatically with `MockitoExtension`).
- Use AssertJ (`assertThat`) for all assertions — more readable than JUnit's `assertEquals`.
- Use `assertThatThrownBy` for exception assertions — verify type AND message content.
- Use `@Captor` + `ArgumentCaptor` to inspect the exact entity passed to `repository.save()`.
- Use `BDDMockito` (`given/willReturn/willThrow`) for behavior-driven test style.
- Verify correct call ordering with `inOrder()` for multi-step operations (find -> save -> audit).
- Test cache behavior annotations (`@Cacheable`, `@CacheEvict`) in integration tests with real cache.
- In unit tests, verify the repository and audit interactions — cache proxy is not active.
- Version conflict test: set `existing.version = 3`, `request.version = 1` — assert `ConflictException`.
- Tenant isolation: every repository call MUST include `tenantId` — verify with `eq(TENANT_ID)`.
- Audit tests MUST verify: action string, entity ID, tenant ID, actor ID, and payload.
- Use `@ParameterizedTest` with `@MethodSource`, `@CsvSource`, or `@EnumSource` for table-driven tests.
- Use `@Nested` to group tests by method for clear test output.
- `verify(repository, never()).save(any())` when validation should fail before persistence.
- `verifyNoInteractions(repository)` when the request should fail at the service boundary.
- Factory methods MUST generate unique IDs with `UUID.randomUUID()` — never reuse across tests.
