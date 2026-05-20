---
skill: error-handling-java
description: Java/Spring Boot error handling archetype — exception hierarchy, @ControllerAdvice, ProblemDetail (RFC 7807), validation error mapping, structured error responses
version: "1.0"
tags:
  - java
  - spring-boot
  - errors
  - exception-handling
  - archetype
  - backend
---

# Error Handling Archetype (Spring Boot)

> **CANONICAL REFERENCE**: This file is the single source of truth for Java/Spring Boot error handling patterns. All other Java skill packs that mention error handling should defer to this file.

Complete error handling system for Spring Boot services. Every generated service MUST follow this pattern.

## Exception Hierarchy

```java
package com.example.app.exception;

 * Sealed base class for all domain exceptions.
 * Using sealed classes ensures exhaustive handling — the compiler warns about unhandled subtypes.
 * Every domain exception MUST extend this class.
public abstract sealed class DomainException extends RuntimeException
    permits ResourceNotFoundException, ConflictException, BusinessRuleException,
            BadRequestException, ForbiddenException, RateLimitException, UpstreamServiceException {

    private final String errorCode;
    private final String resource;

    protected DomainException(String message, String errorCode, String resource) {
        super(message);
        this.errorCode = errorCode;
        this.resource = resource;
    }

    protected DomainException(String message, String errorCode, String resource, Throwable cause) {
        super(message, cause);
        this.errorCode = errorCode;
        this.resource = resource;
    }

    public String getErrorCode() { return errorCode; }
    public String getResource() { return resource; }
}
```

## Exception Taxonomy

```java
// --- 400 Bad Request: Malformed input (JSON parse errors, wrong content type) ---
public final class BadRequestException extends DomainException {
    public BadRequestException(String reason) {
        super(reason, "BAD_REQUEST", null);
    }
    public BadRequestException(String reason, Throwable cause) {
        super(reason, "BAD_REQUEST", null, cause);
    }
}

// --- 404 Not Found: Resource does not exist or was soft-deleted ---
public final class ResourceNotFoundException extends DomainException {
    private final String identifier;

    public ResourceNotFoundException(String resource, String identifier) {
        super(resource + " '" + identifier + "' not found", "NOT_FOUND", resource);
        this.identifier = identifier;
    }

    public String getIdentifier() { return identifier; }
}

// --- 409 Conflict: Duplicate entry, version mismatch, state transition conflict ---
public final class ConflictException extends DomainException {
    public ConflictException(String resource, String reason) {
        super(resource + " conflict: " + reason, "CONFLICT", resource);
    }
}

// --- 422 Business Rule Violation: Well-formed request that fails domain logic ---
public final class BusinessRuleException extends DomainException {
    private final String rule;

    public BusinessRuleException(String resource, String rule) {
        super("Business rule violated: " + rule, "BUSINESS_RULE_VIOLATION", resource);
        this.rule = rule;
    }

    public String getRule() { return rule; }
}

// --- 403 Forbidden: Valid credentials but insufficient permissions ---
public final class ForbiddenException extends DomainException {
    public ForbiddenException(String action, String resource) {
        super("Insufficient permissions to " + action + " " + resource, "FORBIDDEN", resource);
    }
}

// --- 429 Rate Limited ---
public final class RateLimitException extends DomainException {
    private final int retryAfterSeconds;

    public RateLimitException(int retryAfterSeconds) {
        super("Too many requests — please retry later", "RATE_LIMITED", null);
        this.retryAfterSeconds = retryAfterSeconds;
    }

    public int getRetryAfterSeconds() { return retryAfterSeconds; }
}

// --- 502 Bad Gateway: Upstream service failure ---
public final class UpstreamServiceException extends DomainException {
    public UpstreamServiceException(String service, Throwable cause) {
        super("Upstream service '" + service + "' is unavailable", "UPSTREAM_ERROR", service, cause);
    }
}
```

## Global Exception Handler (@ControllerAdvice)

```java
package com.example.app.exception;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;
import org.springframework.http.ResponseEntity;
import org.springframework.orm.ObjectOptimisticLockingFailureException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;

import java.net.URI;
import java.time.Instant;
import java.util.Map;
import java.util.stream.Collectors;

 * Centralized exception handler. ALL exception-to-HTTP mapping lives here.
 * Controllers MUST NOT catch exceptions — let this advice handle them.
@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    // --- Domain Exceptions ---

    @ExceptionHandler(ResourceNotFoundException.class)
    public ResponseEntity<ProblemDetail> handleNotFound(ResourceNotFoundException ex) {
        log.debug("Resource not found: {}", ex.getMessage());
        var problem = createProblem(HttpStatus.NOT_FOUND, ex.getErrorCode(), ex.getMessage());
        problem.setProperty("resource", ex.getResource());
        problem.setProperty("identifier", ex.getIdentifier());
        return ResponseEntity.status(HttpStatus.NOT_FOUND).body(problem);
    }

    @ExceptionHandler(ConflictException.class)
    public ResponseEntity<ProblemDetail> handleConflict(ConflictException ex) {
        log.warn("Conflict: {}", ex.getMessage());
        var problem = createProblem(HttpStatus.CONFLICT, ex.getErrorCode(), ex.getMessage());
        problem.setProperty("resource", ex.getResource());
        return ResponseEntity.status(HttpStatus.CONFLICT).body(problem);
    }

    @ExceptionHandler(BusinessRuleException.class)
    public ResponseEntity<ProblemDetail> handleBusinessRule(BusinessRuleException ex) {
        log.warn("Business rule violated: {}", ex.getMessage());
        var problem = createProblem(HttpStatus.UNPROCESSABLE_ENTITY, ex.getErrorCode(), ex.getMessage());
        problem.setProperty("resource", ex.getResource());
        problem.setProperty("rule", ex.getRule());
        return ResponseEntity.status(HttpStatus.UNPROCESSABLE_ENTITY).body(problem);
    }

    @ExceptionHandler(BadRequestException.class)
    public ResponseEntity<ProblemDetail> handleBadRequest(BadRequestException ex) {
        log.debug("Bad request: {}", ex.getMessage());
        var problem = createProblem(HttpStatus.BAD_REQUEST, ex.getErrorCode(), ex.getMessage());
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(problem);
    }

    @ExceptionHandler(ForbiddenException.class)
    public ResponseEntity<ProblemDetail> handleForbidden(ForbiddenException ex) {
        log.warn("Forbidden: {}", ex.getMessage());
        var problem = createProblem(HttpStatus.FORBIDDEN, ex.getErrorCode(), ex.getMessage());
        return ResponseEntity.status(HttpStatus.FORBIDDEN).body(problem);
    }

    @ExceptionHandler(RateLimitException.class)
    public ResponseEntity<ProblemDetail> handleRateLimit(RateLimitException ex) {
        log.warn("Rate limited: {}", ex.getMessage());
        var problem = createProblem(HttpStatus.TOO_MANY_REQUESTS, ex.getErrorCode(), ex.getMessage());
        problem.setProperty("retryAfterSeconds", ex.getRetryAfterSeconds());

        var headers = new HttpHeaders();
        headers.set("Retry-After", String.valueOf(ex.getRetryAfterSeconds()));
        return ResponseEntity.status(HttpStatus.TOO_MANY_REQUESTS).headers(headers).body(problem);
    }

    @ExceptionHandler(UpstreamServiceException.class)
    public ResponseEntity<ProblemDetail> handleUpstream(UpstreamServiceException ex) {
        log.error("Upstream failure: service={}, error={}", ex.getResource(), ex.getMessage(), ex.getCause());
        var problem = createProblem(HttpStatus.BAD_GATEWAY, ex.getErrorCode(),
            "An upstream service is currently unavailable");
        // Never expose internal service names to clients
        return ResponseEntity.status(HttpStatus.BAD_GATEWAY).body(problem);
    }

    // --- Spring/JPA Exceptions ---

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ProblemDetail> handleValidation(MethodArgumentNotValidException ex) {
        var fieldErrors = ex.getBindingResult().getFieldErrors().stream()
            .collect(Collectors.toMap(
                fe -> fe.getField(),
                fe -> fe.getDefaultMessage() != null ? fe.getDefaultMessage() : "invalid",
                (a, b) -> a + "; " + b // merge multiple errors per field
            ));

        log.debug("Validation failed: {}", fieldErrors);
        var problem = createProblem(HttpStatus.UNPROCESSABLE_ENTITY, "VALIDATION_ERROR",
            "One or more fields failed validation");
        problem.setProperty("fieldErrors", fieldErrors);
        return ResponseEntity.status(HttpStatus.UNPROCESSABLE_ENTITY).body(problem);
    }

    @ExceptionHandler(MethodArgumentTypeMismatchException.class)
    public ResponseEntity<ProblemDetail> handleTypeMismatch(MethodArgumentTypeMismatchException ex) {
        var message = String.format("Invalid value '%s' for parameter '%s'", ex.getValue(), ex.getName());
        log.debug("Type mismatch: {}", message);
        var problem = createProblem(HttpStatus.BAD_REQUEST, "BAD_REQUEST", message);
        problem.setProperty("parameter", ex.getName());
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(problem);
    }

    @ExceptionHandler(ObjectOptimisticLockingFailureException.class)
    public ResponseEntity<ProblemDetail> handleOptimisticLock(ObjectOptimisticLockingFailureException ex) {
        log.warn("Optimistic lock failure: {}", ex.getMessage());
        var problem = createProblem(HttpStatus.CONFLICT, "CONFLICT",
            "Resource was modified by another request. Reload and retry.");
        return ResponseEntity.status(HttpStatus.CONFLICT).body(problem);
    }

    @ExceptionHandler(DataIntegrityViolationException.class)
    public ResponseEntity<ProblemDetail> handleDataIntegrity(DataIntegrityViolationException ex) {
        log.error("Data integrity violation: {}", ex.getMessage());
        // Do NOT expose constraint names to clients — log them for debugging
        var problem = createProblem(HttpStatus.CONFLICT, "CONFLICT",
            "The operation conflicts with existing data");
        return ResponseEntity.status(HttpStatus.CONFLICT).body(problem);
    }

    // --- Catch-All ---

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ProblemDetail> handleUnexpected(Exception ex) {
        log.error("Unexpected error: {}", ex.getMessage(), ex);
        // NEVER expose internal error details to clients
        var problem = createProblem(HttpStatus.INTERNAL_SERVER_ERROR, "INTERNAL_ERROR",
            "An unexpected error occurred");
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(problem);
    }

    // --- Helper ---

    private ProblemDetail createProblem(HttpStatus status, String errorCode, String detail) {
        var problem = ProblemDetail.forStatusAndDetail(status, detail);
        problem.setTitle(status.getReasonPhrase());
        problem.setType(URI.create("https://api.example.com/errors/" + errorCode.toLowerCase().replace("_", "-")));
        problem.setProperty("errorCode", errorCode);
        problem.setProperty("requestId", MDC.get("requestId"));
        problem.setProperty("timestamp", Instant.now().toString());
        return problem;
    }
}
```

## ProblemDetail Response Format (RFC 7807)

```json
// 404 Not Found:
{
  "type": "https://api.example.com/errors/not-found",
  "title": "Not Found",
  "status": 404,
  "detail": "widget '550e8400-e29b-41d4-a716-446655440000' not found",
  "errorCode": "NOT_FOUND",
  "requestId": "abc-123",
  "timestamp": "2025-01-15T10:30:00Z",
  "resource": "widget",
  "identifier": "550e8400-e29b-41d4-a716-446655440000"
}

// 422 Validation Error:
{
  "type": "https://api.example.com/errors/validation-error",
  "title": "Unprocessable Entity",
  "status": 422,
  "detail": "One or more fields failed validation",
  "errorCode": "VALIDATION_ERROR",
  "requestId": "abc-124",
  "timestamp": "2025-01-15T10:30:01Z",
  "fieldErrors": {
    "name": "Name is required",
    "description": "Description must be 2000 characters or fewer"
  }
}

// 409 Conflict (optimistic lock):
{
  "type": "https://api.example.com/errors/conflict",
  "title": "Conflict",
  "status": 409,
  "detail": "Resource was modified by another request. Reload and retry.",
  "errorCode": "CONFLICT",
  "requestId": "abc-125",
  "timestamp": "2025-01-15T10:30:02Z"
}

// 500 Internal Error:
{
  "type": "https://api.example.com/errors/internal-error",
  "title": "Internal Server Error",
  "status": 500,
  "detail": "An unexpected error occurred",
  "errorCode": "INTERNAL_ERROR",
  "requestId": "abc-126",
  "timestamp": "2025-01-15T10:30:03Z"
}
```

## Error Wrapping Guidelines

```java
// --- WRAPPING RULES ---

// 1. Create domain exceptions at the boundary where you KNOW the error type.
//    Repository layer wraps JPA exceptions; service layer wraps business rule violations.
//    // In repository layer — this is where we know "no rows" means "not found":
//    return repository.findByIdAndTenantId(id, tenantId)
//        .orElseThrow(() -> new ResourceNotFoundException("widget", id.toString()));
//    // NOT in the controller — the controller shouldn't know about JPA/Hibernate.

// 2. Never double-wrap domain exceptions.
//    If the error is already a DomainException, let it propagate — @ControllerAdvice handles it.
//    // BAD:
//    try { widgetService.create(request); }
//    catch (ConflictException e) { throw new BadRequestException("conflict", e); } // WRONG
//    // GOOD:
//    widgetService.create(request); // let ConflictException propagate to @ControllerAdvice

// 3. Log errors ONCE at the handler level (via @ControllerAdvice), not at every layer.
//    The @ControllerAdvice logs with appropriate level (debug for 4xx, error for 5xx).

// 4. For cross-service calls, catch infrastructure exceptions and wrap as domain exceptions:
//    try {
//        return externalClient.call();
//    } catch (WebClientResponseException e) {
//        throw new UpstreamServiceException("payment-service", e);
//    }

// 5. Use cause chaining for debugging — internal cause is logged but never sent to clients.
//    throw new ConflictException("widget", "duplicate name").initCause(dataIntegrityException);
```

## Testing Error Handling

```java
@WebMvcTest(WidgetController.class)
class WidgetControllerErrorTest {

    @Autowired MockMvc mockMvc;
    @MockBean WidgetService widgetService;

    @Test
    void getById_notFound_returns404ProblemDetail() throws Exception {
        given(widgetService.findById(any(), any()))
            .willThrow(new ResourceNotFoundException("widget", "abc-123"));

        mockMvc.perform(get("/api/v1/widgets/abc-123"))
            .andExpect(status().isNotFound())
            .andExpect(jsonPath("$.errorCode").value("NOT_FOUND"))
            .andExpect(jsonPath("$.resource").value("widget"))
            .andExpect(jsonPath("$.identifier").value("abc-123"))
            .andExpect(jsonPath("$.requestId").exists());
    }

    @Test
    void create_invalidBody_returns422WithFieldErrors() throws Exception {
        var body = """
            {"name": "", "description": "x".repeat(3000)}
            """;

        mockMvc.perform(post("/api/v1/widgets")
                .contentType(MediaType.APPLICATION_JSON)
                .content(body))
            .andExpect(status().isUnprocessableEntity())
            .andExpect(jsonPath("$.errorCode").value("VALIDATION_ERROR"))
            .andExpect(jsonPath("$.fieldErrors.name").exists());
    }

    @Test
    void update_versionConflict_returns409() throws Exception {
        given(widgetService.update(any(), any(), any(), any()))
            .willThrow(new ConflictException("widget", "version mismatch"));

        mockMvc.perform(put("/api/v1/widgets/{id}", UUID.randomUUID())
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                    {"name": "Updated", "description": "desc", "version": 1}
                    """))
            .andExpect(status().isConflict())
            .andExpect(jsonPath("$.errorCode").value("CONFLICT"));
    }

    @Test
    void unexpectedException_returns500_noInternalDetails() throws Exception {
        given(widgetService.findById(any(), any()))
            .willThrow(new RuntimeException("database connection pool exhausted"));

        mockMvc.perform(get("/api/v1/widgets/{id}", UUID.randomUUID()))
            .andExpect(status().isInternalServerError())
            .andExpect(jsonPath("$.errorCode").value("INTERNAL_ERROR"))
            .andExpect(jsonPath("$.detail").value("An unexpected error occurred"))
            // Ensure internal details are NOT leaked
            .andExpect(jsonPath("$.detail").value(not(containsString("database"))))
            .andExpect(jsonPath("$.detail").value(not(containsString("pool"))));
    }
}
```

## Error Taxonomy Summary

| Exception | HTTP Status | Error Code | When to Use |
|---|---|---|---|
| `BadRequestException` | 400 | `BAD_REQUEST` | Malformed JSON, wrong content type, request parsing failure |
| `MethodArgumentNotValidException` | 422 | `VALIDATION_ERROR` | Jakarta validation annotation failures |
| `BusinessRuleException` | 422 | `BUSINESS_RULE_VIOLATION` | Domain logic violations that annotations cannot express |
| `Spring Security (unauthenticated)` | 401 | `UNAUTHORIZED` | Missing or invalid JWT token |
| `ForbiddenException` | 403 | `FORBIDDEN` | Valid credentials but insufficient permissions |
| `ResourceNotFoundException` | 404 | `NOT_FOUND` | Resource does not exist or was soft-deleted |
| `ConflictException` | 409 | `CONFLICT` | Duplicate entry, version mismatch, state conflict |
| `ObjectOptimisticLockingFailureException` | 409 | `CONFLICT` | JPA @Version mismatch |
| `DataIntegrityViolationException` | 409 | `CONFLICT` | Unique constraint violations |
| `RateLimitException` | 429 | `RATE_LIMITED` | Too many requests from tenant/user |
| `catch-all Exception` | 500 | `INTERNAL_ERROR` | Unexpected server error |
| `UpstreamServiceException` | 502 | `UPSTREAM_ERROR` | External service failure |

## Critical Rules

- All domain exceptions MUST extend `DomainException` (sealed hierarchy).
- `@RestControllerAdvice` handles ALL exception mapping — controllers MUST NOT catch exceptions.
- Use `ProblemDetail` (RFC 7807) for ALL error responses — consistent, machine-readable format.
- Internal error messages (500, 502) MUST NOT leak to clients — always return generic message.
- Validation errors (422) MUST include field names and messages in `fieldErrors`.
- Rate limit responses MUST include `Retry-After` header.
- Every error response MUST include `requestId` and `timestamp` for correlation.
- Log at DEBUG for 4xx errors, WARN for business rule violations, ERROR for 5xx — never over-log.
- Create domain exceptions at the BOUNDARY where you know the error type.
- Never double-wrap domain exceptions — let them propagate to `@ControllerAdvice`.
- Spring Security handles 401 via its own filter chain — do not create an `UnauthorizedException`.
- `ObjectOptimisticLockingFailureException` and `DataIntegrityViolationException` get their own handlers to produce clean 409 responses instead of 500s.
