---
skill: crud-handler-java
description: Spring Boot REST controller archetype — @RestController, request/response DTOs, pagination, error mapping, auth, OpenAPI annotations, structured logging
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
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "widgets")
@SQLDelete(sql = "UPDATE widgets SET deleted_at = NOW() WHERE id = ?1 AND version = ?2")
@Where(clause = "deleted_at IS NULL")
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

import jakarta.validation.constraints.*;
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

```java
package com.example.app.common;

import java.time.Instant;
import java.util.List;

// Single resource envelope
public record ApiResponse<T>(
    T data,
    ResponseMeta meta
) {
    public static <T> ApiResponse<T> of(T data, String requestId) {
        return new ApiResponse<>(data, new ResponseMeta(requestId, Instant.now()));
    }
}

// Paginated list envelope
public record PagedResponse<T>(
    List<T> data,
    PageMeta meta
) {
    public static <T> PagedResponse<T> of(List<T> data, PageMeta meta) {
        return new PagedResponse<>(data, meta);
    }
}

public record ResponseMeta(String requestId, Instant timestamp) {}

public record PageMeta(
    int page,
    int size,
    long totalElements,
    int totalPages,
    String requestId,
    Instant timestamp
) {}
```

## Controller

```java
package com.example.app.controller;

import com.example.app.common.*;
import com.example.app.model.dto.*;
import com.example.app.service.WidgetService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.time.Instant;
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
    @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "422", description = "Validation error")
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
    @Operation(summary = "List widgets with pagination and filtering")
    @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "Paginated widget list")
    public ResponseEntity<PagedResponse<WidgetResponse>> list(
            @Parameter(description = "Zero-based page number") @RequestParam(defaultValue = "0") int page,
            @Parameter(description = "Page size (max 100)") @RequestParam(defaultValue = "20") int size,
            @Parameter(description = "Sort field") @RequestParam(defaultValue = "createdAt") String sortBy,
            @Parameter(description = "Sort direction") @RequestParam(defaultValue = "desc") String sortDir,
            @Parameter(description = "Filter by status") @RequestParam(required = false) WidgetStatus status,
            @AuthenticationPrincipal UserPrincipal principal) {

        var requestId = MDC.get("requestId");

        // Enforce pagination bounds
        size = Math.max(1, Math.min(size, MAX_PAGE_SIZE));
        if (!ALLOWED_SORT_FIELDS.contains(sortBy)) {
            sortBy = "createdAt";
        }
        var direction = "asc".equalsIgnoreCase(sortDir) ? Sort.Direction.ASC : Sort.Direction.DESC;
        var pageable = PageRequest.of(page, size, Sort.by(direction, sortBy));

        Page<Widget> result = widgetService.findAll(principal.getTenantId(), status, pageable);

        var items = result.getContent().stream()
            .map(WidgetResponse::from)
            .toList();

        var meta = new PageMeta(
            result.getNumber(),
            result.getSize(),
            result.getTotalElements(),
            result.getTotalPages(),
            requestId,
            Instant.now()
        );

        log.info("Listed widgets, tenant={}, page={}, resultCount={}, total={}",
            principal.getTenantId(), page, items.size(), result.getTotalElements());

        return ResponseEntity.ok(PagedResponse.of(items, meta));
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

     * Strip all HTML tags and trim whitespace.
     * Call this in the service layer before persisting user-supplied strings.
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
- ALWAYS use `MDC.get("requestId")` for request tracing — set by the `RequestIdFilter`.
- Pagination MUST enforce max page size (100) — never return unbounded lists.
- Sort fields MUST be allow-listed — never allow sorting by arbitrary columns.
- DELETE returns 204 No Content — no response body.
- POST create returns 201 Created with the created resource.
- Error responses use RFC 7807 ProblemDetail — handled by `@RestControllerAdvice`, not controllers.
- Every response uses the envelope format: `{"data": T, "meta": {...}}`.
- Log at INFO for mutations (create, update, delete), DEBUG for reads — include tenant and entity ID.
