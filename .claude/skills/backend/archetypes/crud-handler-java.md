---
skill: crud-handler-java
description: Spring Boot REST controller archetype — @RestController, request/response DTOs, response envelope, cursor pagination, error mapping, auth, OpenAPI annotations, structured logging
version: "1.0"
tags:
  - java
  - spring-boot
  - controller
  - rest
  - archetype
  - backend
---

# CRUD Handler Archetype (Spring Boot)

Complete, production-ready Spring Boot REST controller template. Every generated controller MUST follow this pattern.

## Entity and DTOs

```java
package com.example.app.model.entity;

import jakarta.persistence.*;
import org.hibernate.annotations.SQLDelete;
import org.hibernate.annotations.SQLRestriction;

import java.time.Instant;
import java.util.UUID;

// The full entity (audit fields in AuditableEntity, getters/setters) is in crud-repository-java.md.
@Entity
@Table(name = "widgets")
@SQLDelete(sql = "UPDATE widgets SET deleted_at = NOW() WHERE id = ? AND version = ?") // JDBC ? placeholders
@SQLRestriction("deleted_at IS NULL") // Hibernate 7 removed @Where
public class Widget {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(nullable = false)
    private UUID tenantId;

    @Column(nullable = false, length = 255)
    private String name;

    @Column(length = 2000)
    private String description;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private WidgetStatus status;

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

    // Getters, setters, equals/hashCode on id only
}
```

```java
package com.example.app.model.dto;

import com.example.app.model.entity.Widget;
import com.example.app.model.entity.WidgetStatus;
import jakarta.validation.constraints.*;

import java.time.Instant;
import java.util.UUID;

// Request DTOs — Java records with validation annotations

public record CreateWidgetRequest(
    @NotBlank(message = "Name is required")
    @Size(max = 255, message = "Name must be 255 characters or fewer")
    String name,

    @Size(max = 2000, message = "Description must be 2000 characters or fewer")
    String description
) {}

public record UpdateWidgetRequest(
    @NotBlank(message = "Name is required")
    @Size(max = 255, message = "Name must be 255 characters or fewer")
    String name,

    @Size(max = 2000, message = "Description must be 2000 characters or fewer")
    String description,

    @NotNull(message = "Version is required for optimistic locking")
    Integer version
) {}

// Response DTOs — never expose JPA entities directly

public record WidgetResponse(
    UUID id,
    String name,
    String description,
    WidgetStatus status,
    Instant createdAt,
    Instant updatedAt,
    UUID createdBy,
    int version
) {
    public static WidgetResponse from(Widget entity) {
        return new WidgetResponse(
            entity.getId(),
            entity.getName(),
            entity.getDescription(),
            entity.getStatus(),
            entity.getCreatedAt(),
            entity.getUpdatedAt(),
            entity.getCreatedBy(),
            entity.getVersion()
        );
    }
}
```

## Response Envelope Types

The shape is `~/.claude/skills/api/response-envelope.md` — success `{data, meta}`, error `{error}`, never
both; list metadata in `meta.pagination`. Error bodies are written only by `GlobalExceptionHandler`
(`error-handling-java.md`). Envelope keys are snake_case (`request_id`, `next_cursor`, …) via
`@JsonProperty`; never serialize a Spring Data `Page<T>` (`content`, `totalPages`, `pageable`).

```java
package com.example.app.common;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

// Success envelope: a single resource or a list
public record ApiResponse<T>(
    T data,
    ResponseMeta meta
) {
    public static <T> ApiResponse<T> of(T data, String requestId) {
        return new ApiResponse<>(data, new ResponseMeta(requestId, null));
    }

    /** List response: data is always an array ([] when empty, never null). */
    public static <T> ApiResponse<List<T>> list(List<T> items, Pagination pagination, String requestId) {
        return new ApiResponse<>(items == null ? List.of() : items, new ResponseMeta(requestId, pagination));
    }
}

public record ResponseMeta(
    @JsonProperty("request_id") String requestId,
    @JsonInclude(JsonInclude.Include.NON_NULL) Pagination pagination // lists only
) {}

public record Pagination(
    @JsonProperty("next_cursor") String nextCursor, // serialized as null when has_more is false
    @JsonProperty("has_more") boolean hasMore,
    int limit,
    @JsonProperty("total_count") @JsonInclude(JsonInclude.Include.NON_NULL) Long totalCount // only if cheap AND documented
) {}
```

## Pagination — cursor only

List endpoints take `?cursor=<next_cursor>&limit=<n>` and return `meta.pagination`. There is no offset or
page-number variant: offset pages skip or repeat rows under concurrent writes, and `OFFSET 10000` still
scans 10,000 rows. For "jump to page N" admin tables, filter instead (date range, search, status). A spec
that truly needs numbered pages records it in `docs/DECISIONS.md` and still uses the envelope.

The service returns a Spring Data keyset `Window<T>` (`crud-service-java.md`); the cursor is that
window's last position, made opaque:

```java
package com.example.app.common;

import com.example.app.exception.ValidationException;
import org.springframework.data.domain.KeysetScrollPosition;
import org.springframework.data.domain.ScrollPosition;
import org.springframework.data.domain.Sort;
import tools.jackson.core.type.TypeReference;
import tools.jackson.databind.ObjectMapper;
import tools.jackson.databind.json.JsonMapper;

import java.time.Instant;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;
import java.util.function.Function;
import java.util.stream.Collectors;

/**
 * Opaque list cursor: base64url(JSON) of a keyset position — the last row's sort key and id.
 * Clients pass it back verbatim as ?cursor=; they never build or parse it.
 */
public final class CursorCodec {

    private static final ObjectMapper JSON = JsonMapper.shared(); // Jackson 3 (Spring Boot 4): tools.jackson.*

    // Sortable attributes and how to restore their type (JPA compares typed values)
    private static final Map<String, Function<String, Object>> TYPES = Map.of(
        "id", UUID::fromString,
        "createdAt", Instant::parse,
        "updatedAt", Instant::parse,
        "name", s -> s);

    private CursorCodec() {}

    public static String encode(ScrollPosition position) {
        var flat = new LinkedHashMap<String, String>();
        ((KeysetScrollPosition) position).getKeys().forEach((k, v) -> flat.put(k, String.valueOf(v)));
        // Jackson 3 exceptions are unchecked (JacksonException); a Map<String, String> always serializes
        return Base64.getUrlEncoder().withoutPadding().encodeToString(JSON.writeValueAsBytes(flat));
    }

    /** First page when absent; 400 VALIDATION_FAILED (field "cursor") when tampered with or from another sort. */
    public static ScrollPosition decode(String cursor, Sort sort) {
        if (cursor == null || cursor.isBlank()) {
            return ScrollPosition.keyset();
        }
        try {
            Map<String, String> flat = JSON.readValue(Base64.getUrlDecoder().decode(cursor), new TypeReference<>() {});
            var expected = sort.stream().map(Sort.Order::getProperty).collect(Collectors.toSet());
            if (!flat.keySet().equals(expected)) {
                throw new IllegalArgumentException("cursor keys do not match the sort");
            }
            var keys = new LinkedHashMap<String, Object>();
            flat.forEach((k, v) -> keys.put(k, TYPES.get(k).apply(v)));
            return ScrollPosition.forward(keys);
        } catch (RuntimeException e) { // bad base64, bad JSON (JacksonException), wrong keys, unparsable value
            throw new ValidationException("cursor", "invalid_cursor", "This cursor is not valid. Start from the first page.");
        }
    }
}
```

## Controller

```java
package com.example.app.controller;

import com.example.app.common.*;
import com.example.app.model.dto.*;
import com.example.app.model.entity.Widget;
import com.example.app.model.entity.WidgetStatus;
import com.example.app.security.UserPrincipal;
import com.example.app.service.WidgetService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.data.domain.Sort;
import org.springframework.data.domain.Window;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Set;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/widgets")
@Tag(name = "Widgets", description = "Widget management endpoints")
public class WidgetController {

    private static final Logger log = LoggerFactory.getLogger(WidgetController.class);
    private static final Set<String> ALLOWED_SORT_FIELDS = Set.of("createdAt", "updatedAt", "name");
    private static final int MAX_PAGE_SIZE = 100;
    private static final int DEFAULT_PAGE_SIZE = 20;

    private final WidgetService widgetService;

    public WidgetController(WidgetService widgetService) {
        this.widgetService = widgetService;
    }

    @PostMapping
    @Operation(summary = "Create a widget", description = "Creates a new widget for the authenticated tenant")
    @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "201", description = "Widget created")
    @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "400", description = "MALFORMED_REQUEST or VALIDATION_FAILED")
    public ResponseEntity<ApiResponse<WidgetResponse>> create(
            @Valid @RequestBody CreateWidgetRequest request,
            @AuthenticationPrincipal UserPrincipal principal) {

        var requestId = MDC.get("requestId");
        log.info("Creating widget, name={}, tenant={}", request.name(), principal.getTenantId());

        var widget = widgetService.create(request, principal.getTenantId(), principal.getUserId());
        var response = WidgetResponse.from(widget);

        log.info("Widget created, id={}, tenant={}", widget.getId(), principal.getTenantId());
        return ResponseEntity
            .status(HttpStatus.CREATED)
            .body(ApiResponse.of(response, requestId));
    }

    @GetMapping("/{id}")
    @Operation(summary = "Get a widget by ID")
    @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "Widget found")
    @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "404", description = "Widget not found")
    public ResponseEntity<ApiResponse<WidgetResponse>> getById(
            @PathVariable UUID id,
            @AuthenticationPrincipal UserPrincipal principal) {

        var requestId = MDC.get("requestId");
        log.debug("Fetching widget, id={}, tenant={}", id, principal.getTenantId());

        var widget = widgetService.findById(id, principal.getTenantId());
        return ResponseEntity.ok(ApiResponse.of(WidgetResponse.from(widget), requestId));
    }

    @PutMapping("/{id}")
    @Operation(summary = "Update a widget")
    @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "Widget updated")
    @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "404", description = "Widget not found")
    @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "409", description = "Version conflict")
    public ResponseEntity<ApiResponse<WidgetResponse>> update(
            @PathVariable UUID id,
            @Valid @RequestBody UpdateWidgetRequest request,
            @AuthenticationPrincipal UserPrincipal principal) {

        var requestId = MDC.get("requestId");
        log.info("Updating widget, id={}, version={}, tenant={}", id, request.version(), principal.getTenantId());

        var widget = widgetService.update(id, request, principal.getTenantId(), principal.getUserId());

        log.info("Widget updated, id={}, newVersion={}", id, widget.getVersion());
        return ResponseEntity.ok(ApiResponse.of(WidgetResponse.from(widget), requestId));
    }

    @DeleteMapping("/{id}")
    @Operation(summary = "Delete a widget (soft delete)")
    @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "204", description = "Widget deleted")
    @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "404", description = "Widget not found")
    public ResponseEntity<Void> delete(
            @PathVariable UUID id,
            @AuthenticationPrincipal UserPrincipal principal) {

        log.info("Deleting widget, id={}, tenant={}", id, principal.getTenantId());

        widgetService.delete(id, principal.getTenantId(), principal.getUserId());

        log.info("Widget deleted, id={}, tenant={}", id, principal.getTenantId());
        return ResponseEntity.noContent().build();
    }

    @GetMapping
    @Operation(summary = "List widgets (cursor pagination) with filtering")
    @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "One page of widgets")
    public ResponseEntity<ApiResponse<List<WidgetResponse>>> list(
            @Parameter(description = "Opaque cursor from meta.pagination.next_cursor") @RequestParam(required = false) String cursor,
            @Parameter(description = "Page size (default 20, max 100)") @RequestParam(defaultValue = "20") int limit,
            @Parameter(description = "Sort field") @RequestParam(defaultValue = "createdAt") String sortBy,
            @Parameter(description = "Sort direction") @RequestParam(defaultValue = "desc") String sortDir,
            @Parameter(description = "Filter by status") @RequestParam(required = false) WidgetStatus status,
            @AuthenticationPrincipal UserPrincipal principal) {

        var requestId = MDC.get("requestId");

        // Enforce bounds: default 20 when zero/negative, cap at 100
        limit = limit <= 0 ? DEFAULT_PAGE_SIZE : Math.min(limit, MAX_PAGE_SIZE);
        if (!ALLOWED_SORT_FIELDS.contains(sortBy)) {
            sortBy = "createdAt";
        }
        var direction = "asc".equalsIgnoreCase(sortDir) ? Sort.Direction.ASC : Sort.Direction.DESC;
        var sort = Sort.by(direction, sortBy).and(Sort.by(direction, "id")); // id breaks ties: a unique keyset
        var position = CursorCodec.decode(cursor, sort); // bad cursor → 400 VALIDATION_FAILED

        Window<Widget> window = widgetService.findAll(principal.getTenantId(), status, position, sort, limit);

        var items = window.getContent().stream()
            .map(WidgetResponse::from)
            .toList();

        // next_cursor is null unless there is a next page
        String nextCursor = window.hasNext()
            ? CursorCodec.encode(window.positionAt(window.size() - 1))
            : null;

        log.info("Listed widgets, tenant={}, resultCount={}, hasMore={}",
            principal.getTenantId(), items.size(), window.hasNext());

        return ResponseEntity.ok(ApiResponse.list(
            items, new Pagination(nextCursor, window.hasNext(), limit, null), requestId));
    }
}
```

## Request ID Filter

```java
package com.example.app.common;

import jakarta.servlet.*;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.MDC;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.util.UUID;

@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class RequestIdFilter implements Filter {

    private static final String REQUEST_ID_HEADER = "X-Request-ID";
    private static final String MDC_KEY = "requestId";

    @Override
    public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain)
            throws IOException, ServletException {
        var httpRequest = (HttpServletRequest) request;
        var httpResponse = (HttpServletResponse) response;

        var requestId = httpRequest.getHeader(REQUEST_ID_HEADER);
        if (requestId == null || requestId.isBlank()) {
            requestId = UUID.randomUUID().toString();
        }

        MDC.put(MDC_KEY, requestId);
        httpResponse.setHeader(REQUEST_ID_HEADER, requestId);

        try {
            chain.doFilter(request, response);
        } finally {
            MDC.remove(MDC_KEY);
        }
    }
}
```

## UserPrincipal

```java
package com.example.app.security;

import java.util.Collection;
import java.util.UUID;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.userdetails.UserDetails;

public record UserPrincipal(
    UUID userId,
    UUID tenantId,
    String email,
    Collection<? extends GrantedAuthority> authorities
) implements UserDetails {

    public UUID getUserId() { return userId; }
    public UUID getTenantId() { return tenantId; }

    @Override public String getUsername() { return email; }
    @Override public String getPassword() { return ""; }
    @Override public Collection<? extends GrantedAuthority> getAuthorities() { return authorities; }
}
```

## Input Sanitization

```java
package com.example.app.common;

import org.jsoup.Jsoup;
import org.jsoup.safety.Safelist;

public final class Sanitizer {
    private Sanitizer() {}

    /**
     * Strip all HTML tags and trim whitespace.
     * Call this in the service layer before persisting user-supplied strings.
     */
    public static String clean(String input) {
        if (input == null) return null;
        return Jsoup.clean(input.trim(), Safelist.none());
    }
}
```

## OpenAPI Configuration

```java
package com.example.app.config;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import io.swagger.v3.oas.models.security.SecurityRequirement;
import io.swagger.v3.oas.models.security.SecurityScheme;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class OpenApiConfig {

    @Bean
    public OpenAPI customOpenAPI() {
        return new OpenAPI()
            .info(new Info()
                .title("Widget API")
                .version("1.0")
                .description("Widget management service"))
            .addSecurityItem(new SecurityRequirement().addList("bearerAuth"))
            .schemaRequirement("bearerAuth", new SecurityScheme()
                .type(SecurityScheme.Type.HTTP)
                .scheme("bearer")
                .bearerFormat("JWT"));
    }
}
```

## Critical Rules

- Controllers are THIN: parse request, call service, map response. No business logic.
- NEVER expose JPA entities in responses — always map to response DTOs (records).
- ALWAYS use `@Valid` on `@RequestBody` — let Spring's validator reject invalid input before the service layer.
- ALWAYS use `@AuthenticationPrincipal` to extract tenant/user — NEVER accept tenant ID from path params or body.
- ALWAYS use `MDC.get("requestId")` for request tracing — set by the `RequestIdFilter`, which also sets `X-Request-Id` on every response.
- List endpoints are cursor-only: `?cursor=&limit=` (`limit` defaults to 20, max 100), a keyset `Window` from the service, `meta.pagination` `{next_cursor, has_more, limit}` in the response — never `page`/`size` params or `Page<T>` JSON, never unbounded lists.
- Sort fields MUST be allow-listed — never allow sorting by arbitrary columns.
- DELETE returns 204 No Content — no response body.
- POST create returns 201 Created with the created resource.
- Error responses are the `{"error": {code, message, details?, request_id, retryable}}` envelope, written only by `GlobalExceptionHandler` (`error-handling-java.md`) — never by controllers.
- Every success response follows `~/.claude/skills/api/response-envelope.md`: `{"data": T, "meta": {"request_id"}}`; list `data` is `[]` when empty.
- Log at INFO for mutations (create, update, delete), DEBUG for reads — include tenant and entity ID.
