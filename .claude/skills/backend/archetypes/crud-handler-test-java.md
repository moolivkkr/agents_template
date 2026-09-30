---
skill: crud-handler-test-java
description: Spring Boot controller test archetype — @WebMvcTest, MockMvc, @MockBean, JSON path assertions, pagination, validation, auth, error responses, parameterized tests
version: "1.0"
tags:
  - java
  - spring-boot
  - controller
  - unit-test
  - archetype
  - backend
  - testing
---

# CRUD Handler Test Archetype (Spring Boot)

Complete, production-ready Spring Boot controller test template. Every generated controller test MUST follow this pattern.

## Test File Location

```
src/test/java/com/example/app/controller/
  WidgetControllerTest.java      <- THIS file
src/test/java/com/example/app/
  TestFixtures.java              <- shared test factories
```

Rule: Controller tests use `@WebMvcTest` slicing — only the controller layer and its dependencies are loaded. The service layer is mocked via `@MockBean`.

## Test Setup

```java
package com.example.app.controller;

import com.example.app.common.ApiResponse;
import com.example.app.exception.*;
import com.example.app.model.dto.*;
import com.example.app.model.entity.Widget;
import com.example.app.model.entity.WidgetStatus;
import com.example.app.security.SecurityConfig;
import com.example.app.security.SecurityErrorDelegate;
import com.example.app.security.UserPrincipal;
import com.example.app.service.WidgetService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.*;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.bean.MockBean;
import org.springframework.context.annotation.Import;
import org.springframework.data.domain.*;
import org.springframework.http.MediaType;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;

import java.time.Instant;
import java.util.*;
import java.util.stream.Stream;

import static org.hamcrest.Matchers.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.willDoNothing;
import static org.mockito.BDDMockito.willThrow;
import static org.mockito.Mockito.*;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.user;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@WebMvcTest(WidgetController.class)
// The app's filter chain, wired to SecurityErrorDelegate so 401/403 use the error envelope (error-handling-java.md).
// GlobalExceptionHandler (@RestControllerAdvice) and RequestIdFilter (a Filter bean) are picked up by @WebMvcTest.
@Import({SecurityConfig.class, SecurityErrorDelegate.class})
@DisplayName("WidgetController")
class WidgetControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @MockBean
    private WidgetService widgetService;

    private static final UUID TENANT_ID = UUID.fromString("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa");
    private static final UUID USER_ID = UUID.fromString("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb");
    private static final String BASE_URL = "/api/v1/widgets";

    // Test principal — simulates an authenticated user with ROLE_USER
    private UserPrincipal testPrincipal() {
        return new UserPrincipal(
            USER_ID,
            TENANT_ID,
            "test@example.com",
            List.of(new SimpleGrantedAuthority("ROLE_USER"))
        );
    }

    // Admin principal — simulates an authenticated admin
    private UserPrincipal adminPrincipal() {
        return new UserPrincipal(
            USER_ID,
            TENANT_ID,
            "admin@example.com",
            List.of(
                new SimpleGrantedAuthority("ROLE_USER"),
                new SimpleGrantedAuthority("ROLE_ADMIN")
            )
        );
    }

    // Build a test widget entity with sensible defaults
    private Widget makeWidget() {
        return makeWidget(UUID.randomUUID(), "Test Widget");
    }

    private Widget makeWidget(UUID id, String name) {
        var widget = new Widget();
        widget.setId(id);
        widget.setTenantId(TENANT_ID);
        widget.setName(name);
        widget.setDescription("A test widget");
        widget.setStatus(WidgetStatus.ACTIVE);
        widget.setCreatedAt(Instant.parse("2026-01-15T10:00:00Z"));
        widget.setUpdatedAt(Instant.parse("2026-01-15T10:00:00Z"));
        widget.setCreatedBy(USER_ID);
        widget.setUpdatedBy(USER_ID);
        widget.setVersion(1);
        return widget;
    }

    // A keyset Window as the service returns it; each row's position is its (createdAt, id)
    private Window<Widget> window(List<Widget> items, boolean hasNext) {
        return Window.from(items, i -> ScrollPosition.forward(Map.of(
            "createdAt", items.get(i).getCreatedAt(),
            "id", items.get(i).getId())), hasNext);
    }
}
```

## Create Endpoint Tests (POST /api/v1/widgets)

```java
@Nested
@DisplayName("POST /api/v1/widgets")
class CreateWidgetTests {

    @Test
    @DisplayName("201 Created — valid request creates widget")
    void create_HappyPath_Returns201() throws Exception {
        var widget = makeWidget();
        given(widgetService.create(any(CreateWidgetRequest.class), eq(TENANT_ID), eq(USER_ID)))
            .willReturn(widget);

        var request = new CreateWidgetRequest("New Widget", "A fine widget");

        mockMvc.perform(post(BASE_URL)
                .with(user(testPrincipal()))
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(request)))
            .andExpect(status().isCreated())
            .andExpect(jsonPath("$.data.id").value(widget.getId().toString()))
            .andExpect(jsonPath("$.data.name").value("Test Widget"))
            .andExpect(jsonPath("$.data.status").value("ACTIVE"))
            .andExpect(jsonPath("$.data.version").value(1))
            .andExpect(jsonPath("$.meta.request_id").isNotEmpty())
            .andExpect(jsonPath("$.error").doesNotExist());

        verify(widgetService).create(any(CreateWidgetRequest.class), eq(TENANT_ID), eq(USER_ID));
    }

    @Test
    @DisplayName("400 MALFORMED_REQUEST — malformed JSON body")
    void create_MalformedJson_Returns400() throws Exception {
        mockMvc.perform(post(BASE_URL)
                .with(user(testPrincipal()))
                .contentType(MediaType.APPLICATION_JSON)
                .content("{invalid json"))
            .andExpect(status().isBadRequest())
            .andExpect(jsonPath("$.error.code").value("MALFORMED_REQUEST"));

        verifyNoInteractions(widgetService);
    }

    @Test
    @DisplayName("400 MALFORMED_REQUEST — empty request body")
    void create_EmptyBody_Returns400() throws Exception {
        mockMvc.perform(post(BASE_URL)
                .with(user(testPrincipal()))
                .contentType(MediaType.APPLICATION_JSON)
                .content(""))
            .andExpect(status().isBadRequest())
            .andExpect(jsonPath("$.error.code").value("MALFORMED_REQUEST"));

        verifyNoInteractions(widgetService);
    }

    @ParameterizedTest(name = "400 Validation — {0}")
    @MethodSource("com.example.app.controller.WidgetControllerTest#invalidCreateRequests")
    @DisplayName("400 VALIDATION_FAILED — validation failures")
    void create_ValidationFailures_Returns400(String scenario, String body) throws Exception {
        mockMvc.perform(post(BASE_URL)
                .with(user(testPrincipal()))
                .contentType(MediaType.APPLICATION_JSON)
                .content(body))
            .andExpect(status().isBadRequest())
            .andExpect(jsonPath("$.error.code").value("VALIDATION_FAILED"))
            .andExpect(jsonPath("$.error.message").isNotEmpty())
            .andExpect(jsonPath("$.error.details[0].field").isNotEmpty())
            .andExpect(jsonPath("$.error.details[0].code").isNotEmpty());

        verifyNoInteractions(widgetService);
    }

    @Test
    @DisplayName("409 Conflict — duplicate name for tenant")
    void create_DuplicateName_Returns409() throws Exception {
        given(widgetService.create(any(), eq(TENANT_ID), eq(USER_ID)))
            .willThrow(new ConflictException("widget", "A widget with name 'Existing' already exists"));

        var request = new CreateWidgetRequest("Existing", "Duplicate name");

        mockMvc.perform(post(BASE_URL)
                .with(user(testPrincipal()))
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(request)))
            .andExpect(status().isConflict())
            .andExpect(jsonPath("$.error.code").value("CONFLICT"))
            .andExpect(jsonPath("$.error.message").isNotEmpty());
    }
}

// Parameterized test data: invalid create requests
static Stream<Arguments> invalidCreateRequests() {
    return Stream.of(
        Arguments.of("blank name", """
            {"name": "", "description": "desc"}"""),
        Arguments.of("null name", """
            {"name": null, "description": "desc"}"""),
        Arguments.of("name too long (256 chars)", """
            {"name": "%s", "description": "desc"}"""
            .formatted("A".repeat(256))),
        Arguments.of("description too long (2001 chars)", """
            {"name": "Valid", "description": "%s"}"""
            .formatted("D".repeat(2001)))
    );
}
```

## Get Endpoint Tests (GET /api/v1/widgets/{id})

```java
@Nested
@DisplayName("GET /api/v1/widgets/{id}")
class GetWidgetTests {

    @Test
    @DisplayName("200 OK — returns widget by ID")
    void getById_HappyPath_Returns200() throws Exception {
        var widget = makeWidget();
        given(widgetService.findById(widget.getId(), TENANT_ID)).willReturn(widget);

        mockMvc.perform(get(BASE_URL + "/{id}", widget.getId())
                .with(user(testPrincipal())))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.data.id").value(widget.getId().toString()))
            .andExpect(jsonPath("$.data.name").value("Test Widget"))
            .andExpect(jsonPath("$.data.createdAt").isNotEmpty())
            .andExpect(jsonPath("$.data.version").value(1))
            .andExpect(jsonPath("$.meta.request_id").isNotEmpty());
    }

    @Test
    @DisplayName("404 Not Found — widget does not exist")
    void getById_NotFound_Returns404() throws Exception {
        var id = UUID.randomUUID();
        given(widgetService.findById(id, TENANT_ID))
            .willThrow(new ResourceNotFoundException("widget", id.toString()));

        mockMvc.perform(get(BASE_URL + "/{id}", id)
                .with(user(testPrincipal())))
            .andExpect(status().isNotFound())
            .andExpect(jsonPath("$.error.code").value("NOT_FOUND"))
            .andExpect(jsonPath("$.error.message", containsString("not found")));
    }

    @Test
    @DisplayName("400 VALIDATION_FAILED — invalid UUID format")
    void getById_InvalidUUID_Returns400() throws Exception {
        mockMvc.perform(get(BASE_URL + "/not-a-uuid")
                .with(user(testPrincipal())))
            .andExpect(status().isBadRequest())
            .andExpect(jsonPath("$.error.code").value("VALIDATION_FAILED"))
            .andExpect(jsonPath("$.error.details[0].field").value("id"));

        verifyNoInteractions(widgetService);
    }

    @Test
    @DisplayName("404 Not Found — wrong tenant returns not found, not forbidden")
    void getById_WrongTenant_Returns404NotForbidden() throws Exception {
        // CRITICAL: wrong tenant sees 404, not 403 — prevents entity enumeration
        var id = UUID.randomUUID();
        given(widgetService.findById(id, TENANT_ID))
            .willThrow(new ResourceNotFoundException("widget", id.toString()));

        mockMvc.perform(get(BASE_URL + "/{id}", id)
                .with(user(testPrincipal())))
            .andExpect(status().isNotFound())
            .andExpect(jsonPath("$.error.code").value("NOT_FOUND"));
    }
}
```

## Update Endpoint Tests (PUT /api/v1/widgets/{id})

```java
@Nested
@DisplayName("PUT /api/v1/widgets/{id}")
class UpdateWidgetTests {

    @Test
    @DisplayName("200 OK — updates widget with correct version")
    void update_HappyPath_Returns200() throws Exception {
        var widget = makeWidget();
        widget.setVersion(2);
        widget.setName("Updated Name");

        given(widgetService.update(eq(widget.getId()), any(UpdateWidgetRequest.class), eq(TENANT_ID), eq(USER_ID)))
            .willReturn(widget);

        var request = new UpdateWidgetRequest("Updated Name", "Updated desc", 1);

        mockMvc.perform(put(BASE_URL + "/{id}", widget.getId())
                .with(user(testPrincipal()))
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(request)))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.data.name").value("Updated Name"))
            .andExpect(jsonPath("$.data.version").value(2))
            .andExpect(jsonPath("$.meta.request_id").isNotEmpty());
    }

    @Test
    @DisplayName("409 Conflict — version mismatch (optimistic locking)")
    void update_VersionConflict_Returns409() throws Exception {
        var id = UUID.randomUUID();
        given(widgetService.update(eq(id), any(), eq(TENANT_ID), eq(USER_ID)))
            .willThrow(new ConflictException("widget", "Version mismatch: expected 3, got 1. Reload and retry."));

        var request = new UpdateWidgetRequest("Updated", "desc", 1);

        mockMvc.perform(put(BASE_URL + "/{id}", id)
                .with(user(testPrincipal()))
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(request)))
            .andExpect(status().isConflict())
            .andExpect(jsonPath("$.error.code").value("CONFLICT"))
            .andExpect(jsonPath("$.error.message", containsString("Version mismatch")));
    }

    @Test
    @DisplayName("404 Not Found — widget does not exist")
    void update_NotFound_Returns404() throws Exception {
        var id = UUID.randomUUID();
        given(widgetService.update(eq(id), any(), eq(TENANT_ID), eq(USER_ID)))
            .willThrow(new ResourceNotFoundException("widget", id.toString()));

        var request = new UpdateWidgetRequest("Name", "desc", 1);

        mockMvc.perform(put(BASE_URL + "/{id}", id)
                .with(user(testPrincipal()))
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(request)))
            .andExpect(status().isNotFound())
            .andExpect(jsonPath("$.error.code").value("NOT_FOUND"));
    }

    @Test
    @DisplayName("400 MALFORMED_REQUEST — malformed JSON body")
    void update_MalformedJson_Returns400() throws Exception {
        var id = UUID.randomUUID();

        mockMvc.perform(put(BASE_URL + "/{id}", id)
                .with(user(testPrincipal()))
                .contentType(MediaType.APPLICATION_JSON)
                .content("{bad json"))
            .andExpect(status().isBadRequest())
            .andExpect(jsonPath("$.error.code").value("MALFORMED_REQUEST"));

        verifyNoInteractions(widgetService);
    }

    @ParameterizedTest(name = "400 Validation — {0}")
    @MethodSource("com.example.app.controller.WidgetControllerTest#invalidUpdateRequests")
    @DisplayName("400 VALIDATION_FAILED — validation failures")
    void update_ValidationFailures_Returns400(String scenario, String body) throws Exception {
        var id = UUID.randomUUID();

        mockMvc.perform(put(BASE_URL + "/{id}", id)
                .with(user(testPrincipal()))
                .contentType(MediaType.APPLICATION_JSON)
                .content(body))
            .andExpect(status().isBadRequest())
            .andExpect(jsonPath("$.error.code").value("VALIDATION_FAILED"))
            .andExpect(jsonPath("$.error.details").isArray());

        verifyNoInteractions(widgetService);
    }
}

// Parameterized test data: invalid update requests
static Stream<Arguments> invalidUpdateRequests() {
    return Stream.of(
        Arguments.of("blank name", """
            {"name": "", "description": "desc", "version": 1}"""),
        Arguments.of("null version", """
            {"name": "Valid", "description": "desc", "version": null}"""),
        Arguments.of("missing version field", """
            {"name": "Valid", "description": "desc"}"""),
        Arguments.of("name too long", """
            {"name": "%s", "description": "desc", "version": 1}"""
            .formatted("A".repeat(256)))
    );
}
```

## Delete Endpoint Tests (DELETE /api/v1/widgets/{id})

```java
@Nested
@DisplayName("DELETE /api/v1/widgets/{id}")
class DeleteWidgetTests {

    @Test
    @DisplayName("204 No Content — deletes widget successfully")
    void delete_HappyPath_Returns204() throws Exception {
        var id = UUID.randomUUID();
        willDoNothing().given(widgetService).delete(id, TENANT_ID, USER_ID);

        mockMvc.perform(delete(BASE_URL + "/{id}", id)
                .with(user(testPrincipal())))
            .andExpect(status().isNoContent())
            .andExpect(content().string(""));

        verify(widgetService).delete(id, TENANT_ID, USER_ID);
    }

    @Test
    @DisplayName("404 Not Found — widget does not exist")
    void delete_NotFound_Returns404() throws Exception {
        var id = UUID.randomUUID();
        willThrow(new ResourceNotFoundException("widget", id.toString()))
            .given(widgetService).delete(id, TENANT_ID, USER_ID);

        mockMvc.perform(delete(BASE_URL + "/{id}", id)
                .with(user(testPrincipal())))
            .andExpect(status().isNotFound())
            .andExpect(jsonPath("$.error.code").value("NOT_FOUND"));
    }

    @Test
    @DisplayName("400 VALIDATION_FAILED — invalid UUID format")
    void delete_InvalidUUID_Returns400() throws Exception {
        mockMvc.perform(delete(BASE_URL + "/not-a-uuid")
                .with(user(testPrincipal())))
            .andExpect(status().isBadRequest())
            .andExpect(jsonPath("$.error.code").value("VALIDATION_FAILED"));

        verifyNoInteractions(widgetService);
    }
}
```

## List Endpoint Tests (GET /api/v1/widgets)

```java
@Nested
@DisplayName("GET /api/v1/widgets")
class ListWidgetTests {

    @Test
    @DisplayName("200 OK — returns one page of widgets with meta.pagination")
    void list_HappyPath_Returns200() throws Exception {
        var widgets = List.of(makeWidget(), makeWidget(UUID.randomUUID(), "Second Widget"));

        given(widgetService.findAll(eq(TENANT_ID), isNull(), any(ScrollPosition.class), any(Sort.class), anyInt()))
            .willReturn(window(widgets, true));

        mockMvc.perform(get(BASE_URL)
                .with(user(testPrincipal()))
                .param("limit", "2")
                .param("sortBy", "createdAt")
                .param("sortDir", "desc"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.data", hasSize(2)))
            .andExpect(jsonPath("$.data[0].name").value("Test Widget"))
            .andExpect(jsonPath("$.meta.request_id").isNotEmpty())
            .andExpect(jsonPath("$.meta.pagination.next_cursor").isNotEmpty())
            .andExpect(jsonPath("$.meta.pagination.has_more").value(true))
            .andExpect(jsonPath("$.meta.pagination.limit").value(2));
    }

    @Test
    @DisplayName("200 OK — empty list is [] with next_cursor null")
    void list_EmptyResult_ReturnsEmptyArray() throws Exception {
        given(widgetService.findAll(eq(TENANT_ID), isNull(), any(ScrollPosition.class), any(Sort.class), anyInt()))
            .willReturn(window(List.of(), false));

        mockMvc.perform(get(BASE_URL)
                .with(user(testPrincipal())))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.data").isArray())
            .andExpect(jsonPath("$.data", hasSize(0)))
            .andExpect(jsonPath("$.meta.pagination.has_more").value(false))
            .andExpect(jsonPath("$.meta.pagination.next_cursor").value(nullValue()));
    }

    @Test
    @DisplayName("200 OK — next_cursor from one page fetches the next")
    void list_NextCursor_RoundTrips() throws Exception {
        var first = makeWidget();
        given(widgetService.findAll(eq(TENANT_ID), isNull(), any(ScrollPosition.class), any(Sort.class), anyInt()))
            .willReturn(window(List.of(first), true));

        var body = mockMvc.perform(get(BASE_URL).with(user(testPrincipal())).param("limit", "1"))
            .andExpect(status().isOk())
            .andReturn().getResponse().getContentAsString();
        String nextCursor = com.jayway.jsonpath.JsonPath.read(body, "$.meta.pagination.next_cursor");

        mockMvc.perform(get(BASE_URL).with(user(testPrincipal())).param("cursor", nextCursor))
            .andExpect(status().isOk());

        // The second call resumes after the first page's last row
        verify(widgetService).findAll(eq(TENANT_ID), isNull(), argThat(position ->
            position instanceof KeysetScrollPosition keyset
                && first.getId().equals(keyset.getKeys().get("id"))), any(Sort.class), anyInt());
    }

    @Test
    @DisplayName("400 VALIDATION_FAILED — tampered cursor")
    void list_InvalidCursor_Returns400() throws Exception {
        mockMvc.perform(get(BASE_URL)
                .with(user(testPrincipal()))
                .param("cursor", "not-a-real-cursor"))
            .andExpect(status().isBadRequest())
            .andExpect(jsonPath("$.error.code").value("VALIDATION_FAILED"))
            .andExpect(jsonPath("$.error.details[0].field").value("cursor"));

        verifyNoInteractions(widgetService);
    }

    @Test
    @DisplayName("200 OK — filters by status")
    void list_WithStatusFilter_FiltersResults() throws Exception {
        var widget = makeWidget();

        given(widgetService.findAll(eq(TENANT_ID), eq(WidgetStatus.ACTIVE), any(ScrollPosition.class), any(Sort.class), anyInt()))
            .willReturn(window(List.of(widget), false));

        mockMvc.perform(get(BASE_URL)
                .with(user(testPrincipal()))
                .param("status", "ACTIVE"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.data", hasSize(1)));

        verify(widgetService).findAll(eq(TENANT_ID), eq(WidgetStatus.ACTIVE), any(ScrollPosition.class), any(Sort.class), anyInt());
    }
}
```

## Pagination Parameter Tests

```java
@Nested
@DisplayName("Pagination parameter handling")
class PaginationTests {

    @ParameterizedTest(name = "limit {0} becomes {1}")
    @CsvSource({
        "0, 20",      // zero defaults to 20
        "-5, 20",     // negative defaults to 20
        "50, 50",     // valid limit passes through
        "500, 100",   // exceeds max, clamped to 100
        "100, 100",   // at max, passes through
    })
    @DisplayName("limit defaults to 20 and is capped at 100")
    void list_LimitClamping(int requestedLimit, int expectedLimit) throws Exception {
        given(widgetService.findAll(eq(TENANT_ID), isNull(), any(ScrollPosition.class), any(Sort.class), anyInt()))
            .willReturn(window(List.of(), false));

        mockMvc.perform(get(BASE_URL)
                .with(user(testPrincipal()))
                .param("limit", String.valueOf(requestedLimit)))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.meta.pagination.limit").value(expectedLimit));

        // Verify the service was called with the clamped limit
        verify(widgetService).findAll(eq(TENANT_ID), isNull(), any(ScrollPosition.class), any(Sort.class), eq(expectedLimit));
    }

    @ParameterizedTest(name = "sort field ''{0}'' resolves to ''{1}''")
    @CsvSource({
        "createdAt, createdAt",
        "updatedAt, updatedAt",
        "name, name",
        "drop_table, createdAt",    // disallowed field defaults to createdAt
        "id; DROP TABLE, createdAt", // SQL injection attempt defaults safely
        "'', createdAt",             // empty defaults to createdAt
    })
    @DisplayName("Sort field is allow-listed — disallowed fields default to createdAt")
    void list_SortFieldAllowList(String requestedSort, String expectedSort) throws Exception {
        given(widgetService.findAll(eq(TENANT_ID), isNull(), any(ScrollPosition.class), any(Sort.class), anyInt()))
            .willReturn(window(List.of(), false));

        mockMvc.perform(get(BASE_URL)
                .with(user(testPrincipal()))
                .param("sortBy", requestedSort))
            .andExpect(status().isOk());

        verify(widgetService).findAll(eq(TENANT_ID), isNull(), any(ScrollPosition.class), argThat(sort ->
            sort.getOrderFor(expectedSort) != null && sort.getOrderFor("id") != null // id tiebreaker for the keyset
        ), anyInt());
    }

    @ParameterizedTest(name = "sort direction ''{0}'' resolves to {1}")
    @CsvSource({
        "asc, ASC",
        "ASC, ASC",
        "desc, DESC",
        "DESC, DESC",
        "invalid, DESC",  // invalid direction defaults to DESC
        "'', DESC",        // empty defaults to DESC
    })
    @DisplayName("Sort direction is validated — invalid values default to DESC")
    void list_SortDirectionValidation(String requestedDir, Sort.Direction expectedDir) throws Exception {
        given(widgetService.findAll(eq(TENANT_ID), isNull(), any(ScrollPosition.class), any(Sort.class), anyInt()))
            .willReturn(window(List.of(), false));

        mockMvc.perform(get(BASE_URL)
                .with(user(testPrincipal()))
                .param("sortDir", requestedDir))
            .andExpect(status().isOk());

        verify(widgetService).findAll(eq(TENANT_ID), isNull(), any(ScrollPosition.class), argThat(sort -> {
            var order = sort.iterator().next();
            return order.getDirection() == expectedDir;
        }), anyInt());
    }
}
```

## Authentication Tests

```java
@Nested
@DisplayName("Authentication")
class AuthenticationTests {

    @Test
    @DisplayName("401 UNAUTHENTICATED — no authentication token")
    void noAuth_Returns401() throws Exception {
        mockMvc.perform(get(BASE_URL)
                .contentType(MediaType.APPLICATION_JSON))
            .andExpect(status().isUnauthorized())
            .andExpect(header().string("WWW-Authenticate", "Bearer"))
            .andExpect(jsonPath("$.error.code").value("UNAUTHENTICATED"))
            .andExpect(jsonPath("$.error.request_id").isNotEmpty());

        verifyNoInteractions(widgetService);
    }

    @Test
    @DisplayName("401 UNAUTHENTICATED — invalid JWT token")
    void invalidToken_Returns401() throws Exception {
        mockMvc.perform(get(BASE_URL)
                .header("Authorization", "Bearer invalid.token.here"))
            .andExpect(status().isUnauthorized())
            .andExpect(jsonPath("$.error.code").value("UNAUTHENTICATED"));

        verifyNoInteractions(widgetService);
    }

    @Test
    @DisplayName("401 UNAUTHENTICATED — expired JWT token")
    void expiredToken_Returns401() throws Exception {
        // Simulated by not providing valid auth — @WebMvcTest rejects invalid tokens
        mockMvc.perform(get(BASE_URL)
                .header("Authorization", "Bearer expired-token"))
            .andExpect(status().isUnauthorized())
            .andExpect(jsonPath("$.error.code").value("UNAUTHENTICATED"));

        verifyNoInteractions(widgetService);
    }

    @Test
    @DisplayName("403 FORBIDDEN — user lacks required role for admin endpoint")
    void insufficientRole_Returns403() throws Exception {
        // Assuming an admin-only endpoint exists
        var regularUser = testPrincipal(); // has ROLE_USER only

        mockMvc.perform(post(BASE_URL + "/admin/bulk-delete")
                .with(user(regularUser))
                .contentType(MediaType.APPLICATION_JSON)
                .content("{}"))
            .andExpect(status().isForbidden())
            .andExpect(jsonPath("$.error.code").value("FORBIDDEN"));
    }

    @ParameterizedTest(name = "authenticated {0} can access GET /api/v1/widgets")
    @ValueSource(strings = {"ROLE_USER", "ROLE_ADMIN"})
    @DisplayName("Any authenticated role can access list endpoint")
    void anyRole_CanAccessList(String role) throws Exception {
        var principal = new UserPrincipal(
            USER_ID, TENANT_ID, "user@example.com",
            List.of(new SimpleGrantedAuthority(role))
        );
        given(widgetService.findAll(eq(TENANT_ID), isNull(), any(ScrollPosition.class), any(Sort.class), anyInt()))
            .willReturn(window(List.of(), false));

        mockMvc.perform(get(BASE_URL).with(user(principal)))
            .andExpect(status().isOk());
    }
}
```

## Error Response Shape Tests

```java
@Nested
@DisplayName("Error response shape")
class ErrorResponseTests {

    @ParameterizedTest(name = "{0} maps to HTTP {1}")
    @MethodSource("com.example.app.controller.WidgetControllerTest#serviceErrorMappings")
    @DisplayName("Service exceptions map to correct HTTP status codes")
    void serviceError_MapsToCorrectStatus(String scenario, int expectedStatus, String expectedCode,
                                           RuntimeException exception) throws Exception {
        var id = UUID.randomUUID();
        given(widgetService.findById(id, TENANT_ID)).willThrow(exception);

        mockMvc.perform(get(BASE_URL + "/{id}", id)
                .with(user(testPrincipal())))
            .andExpect(status().is(expectedStatus))
            .andExpect(jsonPath("$.error.code").value(expectedCode))
            .andExpect(jsonPath("$.error.message").isNotEmpty())
            .andExpect(jsonPath("$.error.request_id").isNotEmpty())
            .andExpect(jsonPath("$.error.retryable").isBoolean())
            .andExpect(jsonPath("$.data").doesNotExist());
    }

    @Test
    @DisplayName("503 UNAVAILABLE — retryable, with Retry-After")
    void dependencyFailure_Returns503Retryable() throws Exception {
        var id = UUID.randomUUID();
        given(widgetService.findById(id, TENANT_ID))
            .willThrow(new UpstreamServiceException("payment-service", new RuntimeException("read timeout")));

        mockMvc.perform(get(BASE_URL + "/{id}", id)
                .with(user(testPrincipal())))
            .andExpect(status().isServiceUnavailable())
            .andExpect(header().exists("Retry-After"))
            .andExpect(jsonPath("$.error.code").value("UNAVAILABLE"))
            .andExpect(jsonPath("$.error.retryable").value(true))
            .andExpect(content().string(not(containsString("payment-service"))));
    }

    @Test
    @DisplayName("500 INTERNAL — does NOT leak internal details")
    void internalError_DoesNotLeakDetails() throws Exception {
        var id = UUID.randomUUID();
        given(widgetService.findById(id, TENANT_ID))
            .willThrow(new RuntimeException("database connection pool exhausted"));

        mockMvc.perform(get(BASE_URL + "/{id}", id)
                .with(user(testPrincipal())))
            .andExpect(status().isInternalServerError())
            .andExpect(jsonPath("$.error.code").value("INTERNAL"))
            .andExpect(jsonPath("$.error.retryable").value(false))
            // CRITICAL: internal error details MUST NOT leak anywhere in the body
            .andExpect(content().string(not(containsString("database"))))
            .andExpect(content().string(not(containsString("pool"))))
            .andExpect(content().string(not(containsString("connection"))));
    }
}

// Parameterized test data: service exception to HTTP status mapping (api/response-envelope.md)
static Stream<Arguments> serviceErrorMappings() {
    return Stream.of(
        Arguments.of("NotFound", 404, "NOT_FOUND",
            new ResourceNotFoundException("Widget", "123")),
        Arguments.of("Conflict", 409, "CONFLICT",
            new ConflictException("widget", "This widget was changed by someone else. Reload and try again.")),
        Arguments.of("BusinessRule", 422, "BUSINESS_RULE_VIOLATION",
            new BusinessRuleException("widget", "You've reached the limit of 50 widgets.")),
        Arguments.of("Validation", 400, "VALIDATION_FAILED",
            new ValidationException("name", "reserved", "This name is reserved.")),
        Arguments.of("RateLimited", 429, "RATE_LIMITED",
            new RateLimitException(30)),
        Arguments.of("UpstreamService", 503, "UNAVAILABLE",
            new UpstreamServiceException("payment-service", new RuntimeException("timeout")))
    );
}
```

## Response Envelope Structure Tests

```java
@Nested
@DisplayName("Response envelope structure")
class ResponseEnvelopeTests {

    @Test
    @DisplayName("Single resource — has 'data' and 'meta' top-level keys only")
    void singleResource_HasCorrectEnvelopeShape() throws Exception {
        var widget = makeWidget();
        given(widgetService.findById(widget.getId(), TENANT_ID)).willReturn(widget);

        mockMvc.perform(get(BASE_URL + "/{id}", widget.getId())
                .with(user(testPrincipal())))
            .andExpect(status().isOk())
            // Must have exactly "data" and "meta" top-level keys
            .andExpect(jsonPath("$.data").exists())
            .andExpect(jsonPath("$.meta").exists())
            .andExpect(jsonPath("$.error").doesNotExist())
            // data contains expected fields
            .andExpect(jsonPath("$.data.id").exists())
            .andExpect(jsonPath("$.data.name").exists())
            .andExpect(jsonPath("$.data.status").exists())
            .andExpect(jsonPath("$.data.version").exists())
            .andExpect(jsonPath("$.data.createdAt").exists())
            .andExpect(jsonPath("$.data.updatedAt").exists())
            // meta contains request tracking only — no pagination on a single resource
            .andExpect(jsonPath("$.meta.request_id").exists())
            .andExpect(jsonPath("$.meta.pagination").doesNotExist())
            .andExpect(jsonPath("$.meta.timestamp").doesNotExist())
            // data must NOT expose internal fields
            .andExpect(jsonPath("$.data.tenantId").doesNotExist())
            .andExpect(jsonPath("$.data.deletedAt").doesNotExist());
    }

    @Test
    @DisplayName("List resource — has 'data' array and 'meta.pagination'")
    void listResource_HasCorrectEnvelopeShape() throws Exception {
        given(widgetService.findAll(eq(TENANT_ID), isNull(), any(ScrollPosition.class), any(Sort.class), anyInt()))
            .willReturn(window(List.of(makeWidget()), false));

        mockMvc.perform(get(BASE_URL)
                .with(user(testPrincipal())))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.data").isArray())
            .andExpect(jsonPath("$.meta.request_id").isString())
            .andExpect(jsonPath("$.meta.pagination.next_cursor").hasJsonPath())
            .andExpect(jsonPath("$.meta.pagination.has_more").isBoolean())
            .andExpect(jsonPath("$.meta.pagination.limit").isNumber())
            // Not the Spring Data Page<T> shape, and no offset-style keys
            .andExpect(jsonPath("$.content").doesNotExist())
            .andExpect(jsonPath("$.meta.totalPages").doesNotExist())
            .andExpect(jsonPath("$.pagination").doesNotExist());
    }

    @Test
    @DisplayName("Error resource — {error: {code, message, request_id, retryable}}, no 'data'")
    void errorResource_HasCorrectEnvelopeShape() throws Exception {
        var id = UUID.randomUUID();
        given(widgetService.findById(id, TENANT_ID))
            .willThrow(new ResourceNotFoundException("Widget", id.toString()));

        mockMvc.perform(get(BASE_URL + "/{id}", id)
                .with(user(testPrincipal())))
            .andExpect(status().isNotFound())
            .andExpect(header().exists("X-Request-Id"))
            .andExpect(jsonPath("$.error").exists())
            .andExpect(jsonPath("$.error.code").isString())
            .andExpect(jsonPath("$.error.message").isString())
            .andExpect(jsonPath("$.error.request_id").isString())
            .andExpect(jsonPath("$.error.retryable").isBoolean())
            .andExpect(jsonPath("$.error.detail").doesNotExist())
            .andExpect(jsonPath("$.data").doesNotExist());
    }
}
```

## Content Negotiation Tests

```java
@Nested
@DisplayName("Content negotiation")
class ContentNegotiationTests {

    @Test
    @DisplayName("400 MALFORMED_REQUEST — non-JSON content type on POST")
    void unsupportedMediaType_Returns400Malformed() throws Exception {
        mockMvc.perform(post(BASE_URL)
                .with(user(testPrincipal()))
                .contentType(MediaType.TEXT_PLAIN)
                .content("name=widget"))
            .andExpect(status().isBadRequest())
            .andExpect(jsonPath("$.error.code").value("MALFORMED_REQUEST"));

        verifyNoInteractions(widgetService);
    }

    @Test
    @DisplayName("Response Content-Type is application/json")
    void response_HasJsonContentType() throws Exception {
        var widget = makeWidget();
        given(widgetService.findById(widget.getId(), TENANT_ID)).willReturn(widget);

        mockMvc.perform(get(BASE_URL + "/{id}", widget.getId())
                .with(user(testPrincipal())))
            .andExpect(status().isOk())
            .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON));
    }
}
```

## Critical Rules

- Every controller test MUST use `@WebMvcTest` — do NOT use `@SpringBootTest` for controller tests (too slow, loads full context).
- `@MockBean` for every service dependency — controllers are tested in isolation.
- `user(testPrincipal())` MUST be used on every request that requires authentication — this simulates Spring Security's `@AuthenticationPrincipal`.
- Malformed JSON, an empty body or a non-JSON content type MUST return 400 `MALFORMED_REQUEST`.
- `@Valid` constraint violations and bad path/query types MUST return 400 `VALIDATION_FAILED` with `details[]`; domain rules 422 `BUSINESS_RULE_VIOLATION`.
- Wrong tenant MUST return 404 Not Found, not 403 Forbidden — prevents entity enumeration attacks.
- Internal errors (500 `INTERNAL`) MUST NOT leak exception messages to the client — assert on the whole body, not just `message`.
- DELETE MUST return 204 with empty body — `content().string("")`.
- POST create MUST return 201 Created.
- Every response MUST follow `~/.claude/skills/api/response-envelope.md`: `{"data": T, "meta": {"request_id"}}` for success, `{"error": {code, message, details?, request_id, retryable}}` for failure, never both.
- Lists: `meta.pagination` `{next_cursor, has_more, limit}`, `data` is `[]` when empty, `next_cursor` null when `has_more` is false; `limit` defaults to 20 and is capped at 100; sort fields MUST be allow-listed.
- Use `@ParameterizedTest` with `@MethodSource` or `@CsvSource` for table-driven tests.
- Use `@Nested` classes to group tests by endpoint (improves test output readability).
- Use `verifyNoInteractions(widgetService)` when the request should fail before reaching the service layer.
- Use `verify(widgetService).method(...)` to assert the service was called with correct arguments.
- Use `argThat(...)` for complex argument matching on `ScrollPosition`, `Sort`, or DTOs.
- Use `@DisplayName` on every test for human-readable test reports.
