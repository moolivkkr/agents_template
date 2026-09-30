---
skill: error-handling-java
description: Java/Spring Boot error handling archetype — exception hierarchy, one @RestControllerAdvice writing the API error envelope, validation → details[], Spring Security 401/403, database error mapping
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

> **CANONICAL REFERENCE**: This file is the single source of truth for Java/Spring Boot error handling patterns.
> The wire shape it produces is the error envelope in `~/.claude/skills/api/response-envelope.md`
> (`{"error": {code, message, details[], request_id, retryable}}`); if the two ever disagree, the envelope wins. All other Java skill packs that mention error handling should defer to this file. For the Go equivalent, see `backend/archetypes/error-handling-go.md`.

Complete error handling system for Spring Boot services. Every generated service MUST follow this pattern.

## Exception Hierarchy

```java
package com.example.app.exception;

import org.springframework.http.HttpStatus;

import java.util.List;
import java.util.Map;

/**
 * One entry of error.details[] — field-level problems for VALIDATION_FAILED.
 * `code` is a stable lower_snake identifier; `message` comes from a fixed catalog,
 * never from a validator's or an exception's text.
 */
public record FieldError(String field, String code, String message) {

    // Jakarta constraint name (Spring's FieldError#getCode(), e.g. "NotBlank") → stable code
    private static final Map<String, String> CODES = Map.of(
        "NotNull", "required", "NotBlank", "required", "NotEmpty", "required",
        "Size", "invalid_length", "Email", "invalid_format", "Pattern", "invalid_format",
        "Min", "out_of_range", "Max", "out_of_range");

    private static final Map<String, String> MESSAGES = Map.of(
        "required", "This field is required.",
        "invalid_length", "This value is too short or too long.",
        "invalid_format", "This value has the wrong format.",
        "out_of_range", "This value is out of range.",
        "invalid", "This value is invalid.");

    public static FieldError fromConstraint(String field, String constraint) {
        var code = CODES.getOrDefault(constraint, "invalid");
        return new FieldError(field, code, MESSAGES.get(code));
    }
}

/**
 * Sealed base class for all application exceptions — the Java counterpart of Go's AppError
 * (error-handling-go.md). Each subtype carries everything GlobalExceptionHandler needs to write
 * the envelope. Every application exception MUST extend this class.
 */
public abstract sealed class DomainException extends RuntimeException
    permits MalformedRequestException, ValidationException, UnauthenticatedException, ForbiddenException,
            ResourceNotFoundException, ConflictException, BusinessRuleException, RateLimitException,
            UpstreamServiceException, InternalException {

    private final String errorCode;          // UPPER_SNAKE, stable: VALIDATION_FAILED, NOT_FOUND, ...
    private final HttpStatus status;         // not serialized — the HTTP status carries the class
    private final String userMessage;        // user-safe; the UI shows it as-is
    private final String resource;           // log context only
    private final List<FieldError> details;  // serialized as error.details (VALIDATION_FAILED)
    private final boolean retryable;         // serialized as error.retryable
    private final Integer retryAfterSeconds; // sets the Retry-After header (429/503)

    protected DomainException(String errorCode, HttpStatus status, String userMessage, String resource,
                              List<FieldError> details, boolean retryable, Integer retryAfterSeconds,
                              Throwable cause) {
        super(errorCode + ": " + userMessage, cause); // server-side text; the cause is logged, never sent
        this.errorCode = errorCode;
        this.status = status;
        this.userMessage = userMessage;
        this.resource = resource;
        this.details = details == null ? List.of() : List.copyOf(details);
        this.retryable = retryable;
        this.retryAfterSeconds = retryAfterSeconds;
    }

    protected DomainException(String errorCode, HttpStatus status, String userMessage, String resource) {
        this(errorCode, status, userMessage, resource, List.of(), false, null, null);
    }

    public String getErrorCode() { return errorCode; }
    public HttpStatus getStatus() { return status; }
    public String getUserMessage() { return userMessage; }
    public String getResource() { return resource; }
    public List<FieldError> getDetails() { return details; }
    public boolean isRetryable() { return retryable; }
    public Integer getRetryAfterSeconds() { return retryAfterSeconds; }
}
```

## Exception Taxonomy

The codes and statuses are the table in `api/response-envelope.md`. Messages are user-safe and fixed, or
written by the caller for users; nothing from a parser, driver or upstream reaches the client.

```java
// --- 400 MALFORMED_REQUEST: unreadable JSON, empty body, wrong content type, body too large ---
public final class MalformedRequestException extends DomainException {
    public MalformedRequestException(Throwable cause) {
        super("MALFORMED_REQUEST", HttpStatus.BAD_REQUEST, "The request could not be read.", null,
              List.of(), false, null, cause);
    }
}

// --- 400 VALIDATION_FAILED: input fails schema/field validation; details[] lists the fields ---
public final class ValidationException extends DomainException {
    public ValidationException(List<FieldError> details) {
        super("VALIDATION_FAILED", HttpStatus.BAD_REQUEST, "Some fields are invalid.", null,
              details, false, null, null);
    }

    public ValidationException(String field, String code, String message) {
        this(List.of(new FieldError(field, code, message)));
    }
}

// --- 401 UNAUTHENTICATED: missing, invalid or expired credentials ---
public final class UnauthenticatedException extends DomainException {
    public UnauthenticatedException() {
        super("UNAUTHENTICATED", HttpStatus.UNAUTHORIZED, "Sign in to continue.", null);
    }
}

// --- 403 FORBIDDEN: authenticated but not allowed (function-level) ---
public final class ForbiddenException extends DomainException {
    public ForbiddenException() {
        super("FORBIDDEN", HttpStatus.FORBIDDEN, "You don't have permission to do this.", null);
    }

    /** action/resource are log context; the client gets the fixed message. */
    public ForbiddenException(String action, String resource) {
        super("FORBIDDEN", HttpStatus.FORBIDDEN, "You don't have permission to do this.", action + " " + resource);
    }
}

// --- 404 NOT_FOUND: missing, soft-deleted, OR another tenant's/owner's object (never 403 for those) ---
public final class ResourceNotFoundException extends DomainException {
    private final String identifier; // log context only — the message doesn't echo it

    public ResourceNotFoundException(String resource, String identifier) {
        super("NOT_FOUND", HttpStatus.NOT_FOUND, resource + " not found.", resource);
        this.identifier = identifier;
    }

    public String getIdentifier() { return identifier; }
}

// --- 409 CONFLICT / IDEMPOTENCY_KEY_REUSED: duplicate entry, version mismatch, state conflict ---
public final class ConflictException extends DomainException {
    /** `reason` is shown to the user as-is: write it for users (no SQL, no constraint names). */
    public ConflictException(String resource, String reason) {
        this("CONFLICT", resource, reason);
    }

    /** The same Idempotency-Key was replayed with a different request body. */
    public static ConflictException idempotencyKeyReused() {
        return new ConflictException("IDEMPOTENCY_KEY_REUSED", null,
            "This Idempotency-Key was already used with a different request.");
    }

    private ConflictException(String errorCode, String resource, String message) {
        super(errorCode, HttpStatus.CONFLICT, message, resource);
    }
}

// --- 422 BUSINESS_RULE_VIOLATION: valid shape, rejected by a domain rule ---
public final class BusinessRuleException extends DomainException {
    private final String rule;

    /** `rule` is shown to the user as-is: write it for users. */
    public BusinessRuleException(String resource, String rule) {
        super("BUSINESS_RULE_VIOLATION", HttpStatus.UNPROCESSABLE_ENTITY, rule, resource);
        this.rule = rule;
    }

    public String getRule() { return rule; }
}

// --- 429 RATE_LIMITED ---
public final class RateLimitException extends DomainException {
    public RateLimitException(int retryAfterSeconds) {
        super("RATE_LIMITED", HttpStatus.TOO_MANY_REQUESTS, "Too many requests. Try again shortly.", null,
              List.of(), true, retryAfterSeconds, null);
    }
}

// --- 503 UNAVAILABLE: a dependency (DB, cache, upstream API) failed or timed out ---
// The service name and the cause go to the log, not the client.
public final class UpstreamServiceException extends DomainException {
    public UpstreamServiceException(String service, Throwable cause) {
        super("UNAVAILABLE", HttpStatus.SERVICE_UNAVAILABLE, "The service is temporarily unavailable.", service,
              List.of(), true, 5, cause);
    }
}

// --- 500 INTERNAL: anything unexpected ---
public final class InternalException extends DomainException {
    public InternalException(Throwable cause) {
        super("INTERNAL", HttpStatus.INTERNAL_SERVER_ERROR, "Something went wrong.", null,
              List.of(), false, null, cause);
    }
}
```

## Global Exception Handler (@RestControllerAdvice)

```java
package com.example.app.exception;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.dao.QueryTimeoutException;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.orm.ObjectOptimisticLockingFailureException;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.core.AuthenticationException;
import org.springframework.web.HttpMediaTypeNotSupportedException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.web.servlet.resource.NoResourceFoundException;

import java.sql.SQLException;
import java.util.List;

/**
 * Error envelope (api/response-envelope.md): {"error": {code, message, details?, request_id, retryable}}.
 * An error body has no "data" key.
 */
public record ErrorBody(ApiError error) {}

public record ApiError(
    String code,
    String message,
    @JsonInclude(JsonInclude.Include.NON_EMPTY) List<FieldError> details,
    @JsonProperty("request_id") String requestId,
    boolean retryable
) {}

/**
 * Centralized exception handler — the ONLY code that writes an error response.
 * Controllers MUST NOT catch exceptions — let this advice handle them.
 */
@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    // --- Application exceptions (services, repositories) ---

    @ExceptionHandler(DomainException.class)
    public ResponseEntity<ErrorBody> handleDomain(DomainException ex) {
        return write(ex);
    }

    // --- Request could not be read: bad JSON, empty body, wrong Content-Type → 400 MALFORMED_REQUEST ---

    @ExceptionHandler({HttpMessageNotReadableException.class, HttpMediaTypeNotSupportedException.class})
    public ResponseEntity<ErrorBody> handleUnreadable(Exception ex) {
        return write(new MalformedRequestException(ex));
    }

    // --- @Valid failures → 400 VALIDATION_FAILED; details[] are codes + catalog messages, not validator text ---

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ErrorBody> handleValidation(MethodArgumentNotValidException ex) {
        var details = ex.getBindingResult().getFieldErrors().stream()
            .map(fe -> FieldError.fromConstraint(fe.getField(), fe.getCode()))
            .toList();
        return write(new ValidationException(details));
    }

    // --- Path/query parameter of the wrong type (e.g. /widgets/not-a-uuid) → 400 VALIDATION_FAILED ---

    @ExceptionHandler(MethodArgumentTypeMismatchException.class)
    public ResponseEntity<ErrorBody> handleTypeMismatch(MethodArgumentTypeMismatchException ex) {
        // The rejected value is raw user input: it is not echoed back
        return write(new ValidationException(ex.getName(), "invalid_format", "This value has the wrong format."));
    }

    // --- Unknown route → 404 NOT_FOUND (instead of falling through to the catch-all 500) ---

    @ExceptionHandler(NoResourceFoundException.class)
    public ResponseEntity<ErrorBody> handleNoRoute(NoResourceFoundException ex) {
        return write(new ResourceNotFoundException("Resource", ex.getResourcePath()));
    }

    // --- Spring Security, routed here by SecurityErrorDelegate (below) ---

    @ExceptionHandler(AuthenticationException.class)
    public ResponseEntity<ErrorBody> handleUnauthenticated(AuthenticationException ex) {
        return write(new UnauthenticatedException());
    }

    @ExceptionHandler(AccessDeniedException.class)
    public ResponseEntity<ErrorBody> handleAccessDenied(AccessDeniedException ex) {
        return write(new ForbiddenException());
    }

    // --- JPA / database: SQLSTATE picks the class; constraint names and driver text stay in the log ---

    @ExceptionHandler(ObjectOptimisticLockingFailureException.class)
    public ResponseEntity<ErrorBody> handleOptimisticLock(ObjectOptimisticLockingFailureException ex) {
        return write(new ConflictException(null, "This item was changed by someone else. Reload and try again."));
    }

    @ExceptionHandler(DataIntegrityViolationException.class)
    public ResponseEntity<ErrorBody> handleDataIntegrity(DataIntegrityViolationException ex) {
        var sqlState = sqlState(ex);
        log.warn("Data integrity violation, sqlState={}, requestId={}", sqlState, MDC.get("requestId"), ex);
        if ("23505".equals(sqlState)) { // unique_violation
            return write(new ConflictException(null, "This conflicts with existing data."));
        }
        // foreign_key_violation (23503), check_violation (23514), not_null_violation (23502)
        return write(new BusinessRuleException(null, "This change conflicts with related data."));
    }

    @ExceptionHandler({QueryTimeoutException.class, DataAccessResourceFailureException.class})
    public ResponseEntity<ErrorBody> handleDatabaseUnavailable(Exception ex) {
        // Statement timeout, connection refused, pool exhausted → 503 UNAVAILABLE, retryable
        return write(new UpstreamServiceException("database", ex));
    }

    // --- Catch-all: anything unexpected → 500 INTERNAL with a generic message ---

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ErrorBody> handleUnexpected(Exception ex) {
        return write(new InternalException(ex));
    }

    // --- The one writer ---

    private ResponseEntity<ErrorBody> write(DomainException ex) {
        var requestId = MDC.get("requestId"); // set by RequestIdFilter (crud-handler-java.md)
        if (ex.getStatus().is5xxServerError()) {
            // The cause chain goes to the log under requestId — never to the client
            log.error("Request failed, code={}, resource={}, requestId={}",
                ex.getErrorCode(), ex.getResource(), requestId, ex);
        } else {
            log.debug("Request rejected, code={}, resource={}, requestId={}",
                ex.getErrorCode(), ex.getResource(), requestId);
        }

        var headers = new HttpHeaders();
        // X-Request-Id: RequestIdFilter already set it on this response (errors included) from the same
        // MDC value. Not re-added here: ResponseEntity headers are appended, which would send it twice.
        if (ex.getRetryAfterSeconds() != null) {
            headers.set(HttpHeaders.RETRY_AFTER, String.valueOf(ex.getRetryAfterSeconds()));
        }
        if (ex.getStatus() == HttpStatus.UNAUTHORIZED) {
            headers.set(HttpHeaders.WWW_AUTHENTICATE, "Bearer");
        }

        var body = new ErrorBody(new ApiError(
            ex.getErrorCode(), ex.getUserMessage(), ex.getDetails(), requestId, ex.isRetryable()));
        return ResponseEntity.status(ex.getStatus())
            .headers(headers)
            .contentType(MediaType.APPLICATION_JSON)
            .body(body);
    }

    private static String sqlState(Throwable ex) {
        for (var t = ex; t != null; t = t.getCause()) {
            if (t instanceof SQLException sql) {
                return sql.getSQLState();
            }
        }
        return null;
    }
}
```

Spring Security rejects requests in its filter chain, before any controller runs, so the advice never sees
those exceptions on its own. Hand them over, so 401/403 get the same envelope and `WWW-Authenticate: Bearer`:

```java
package com.example.app.security;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.web.AuthenticationEntryPoint;
import org.springframework.security.web.access.AccessDeniedHandler;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerExceptionResolver;

/**
 * Wire it in the SecurityFilterChain:
 *   http.exceptionHandling(e -> e.authenticationEntryPoint(delegate).accessDeniedHandler(delegate));
 *   // with a JWT resource server, also: .oauth2ResourceServer(o -> o.jwt(withDefaults()).authenticationEntryPoint(delegate))
 */
@Component
public class SecurityErrorDelegate implements AuthenticationEntryPoint, AccessDeniedHandler {

    private final HandlerExceptionResolver resolver;

    public SecurityErrorDelegate(@Qualifier("handlerExceptionResolver") HandlerExceptionResolver resolver) {
        this.resolver = resolver;
    }

    @Override
    public void commence(HttpServletRequest request, HttpServletResponse response, AuthenticationException ex) {
        resolver.resolveException(request, response, null, ex); // → GlobalExceptionHandler → 401 UNAUTHENTICATED
    }

    @Override
    public void handle(HttpServletRequest request, HttpServletResponse response, AccessDeniedException ex) {
        resolver.resolveException(request, response, null, ex); // → GlobalExceptionHandler → 403 FORBIDDEN
    }
}
```

## Error Response Format

The HTTP status carries the class; the `X-Request-Id` header equals `error.request_id`.

```json
// 400 VALIDATION_FAILED:
{
  "error": {
    "code": "VALIDATION_FAILED",
    "message": "Some fields are invalid.",
    "details": [
      { "field": "name", "code": "required", "message": "This field is required." },
      { "field": "description", "code": "invalid_length", "message": "This value is too short or too long." }
    ],
    "request_id": "b7e1c2…",
    "retryable": false
  }
}

// 404 NOT_FOUND (also for another tenant's widget — don't confirm it exists):
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Widget not found.",
    "request_id": "b7e1c2…",
    "retryable": false
  }
}

// 409 CONFLICT (optimistic lock):
{
  "error": {
    "code": "CONFLICT",
    "message": "This item was changed by someone else. Reload and try again.",
    "request_id": "b7e1c2…",
    "retryable": false
  }
}

// 500 INTERNAL (the cause is in the log line with the same request_id):
{
  "error": {
    "code": "INTERNAL",
    "message": "Something went wrong.",
    "request_id": "b7e1c2…",
    "retryable": false
  }
}

// 503 UNAVAILABLE (with header Retry-After: 5):
{
  "error": {
    "code": "UNAVAILABLE",
    "message": "The service is temporarily unavailable.",
    "request_id": "b7e1c2…",
    "retryable": true
  }
}
```

## Error Wrapping Guidelines

```java
// --- WRAPPING RULES ---

// 1. Create domain exceptions at the boundary where you KNOW the error type.
//    Repository layer wraps JPA exceptions; service layer wraps business rule violations.
//
//    // In repository layer — this is where we know "no rows" means "not found":
//    return repository.findByIdAndTenantId(id, tenantId)
//        .orElseThrow(() -> new ResourceNotFoundException("Widget", id.toString()));
//    // NOT in the controller — the controller shouldn't know about JPA/Hibernate.

// 2. Never double-wrap domain exceptions.
//    If the error is already a DomainException, let it propagate — @RestControllerAdvice handles it.
//
//    // BAD:
//    try { widgetService.create(request); }
//    catch (ConflictException e) { throw new MalformedRequestException(e); } // WRONG
//
//    // GOOD:
//    widgetService.create(request); // let ConflictException propagate to @RestControllerAdvice

// 3. Log errors ONCE at the handler level (via @RestControllerAdvice), not at every layer.
//    The advice logs with appropriate level (debug for 4xx, error for 5xx), always with requestId.

// 4. For cross-service calls, catch infrastructure exceptions and wrap as domain exceptions:
//    try {
//        return externalClient.call();
//    } catch (WebClientResponseException e) {
//        throw new UpstreamServiceException("payment-service", e); // 503 UNAVAILABLE, retryable
//    }

// 5. Keep the cause for the log: the exceptions that wrap one (MalformedRequest, UpstreamService,
//    Internal) take it as a constructor argument. It is logged with requestId and never serialized.
//    Text you pass to ConflictException / BusinessRuleException IS shown to users — never pass an
//    exception's message, SQL or a constraint name there.
```

## Testing Error Handling

```java
@WebMvcTest(WidgetController.class)
class WidgetControllerErrorTest {

    @Autowired MockMvc mockMvc;
    @MockBean WidgetService widgetService;

    @Test
    void getById_notFound_returns404Envelope() throws Exception {
        var id = UUID.randomUUID();
        given(widgetService.findById(any(), any()))
            .willThrow(new ResourceNotFoundException("Widget", id.toString()));

        mockMvc.perform(get("/api/v1/widgets/{id}", id))
            .andExpect(status().isNotFound())
            .andExpect(jsonPath("$.error.code").value("NOT_FOUND"))
            .andExpect(jsonPath("$.error.message").value("Widget not found."))
            .andExpect(jsonPath("$.error.request_id").isNotEmpty())
            .andExpect(jsonPath("$.error.retryable").value(false))
            .andExpect(jsonPath("$.data").doesNotExist());
    }

    @Test
    void create_invalidBody_returns400WithFieldDetails() throws Exception {
        var body = """
            {"name": "", "description": "%s"}
            """.formatted("x".repeat(3000));

        mockMvc.perform(post("/api/v1/widgets")
                .contentType(MediaType.APPLICATION_JSON)
                .content(body))
            .andExpect(status().isBadRequest())
            .andExpect(jsonPath("$.error.code").value("VALIDATION_FAILED"))
            .andExpect(jsonPath("$.error.details[?(@.field == 'name')].code").value("required"));
    }

    @Test
    void update_versionConflict_returns409() throws Exception {
        given(widgetService.update(any(), any(), any(), any()))
            .willThrow(new ConflictException("widget", "This widget was changed by someone else. Reload and try again."));

        mockMvc.perform(put("/api/v1/widgets/{id}", UUID.randomUUID())
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                    {"name": "Updated", "description": "desc", "version": 1}
                    """))
            .andExpect(status().isConflict())
            .andExpect(jsonPath("$.error.code").value("CONFLICT"));
    }

    @Test
    void unexpectedException_returns500_noInternalDetails() throws Exception {
        given(widgetService.findById(any(), any()))
            .willThrow(new RuntimeException("database connection pool exhausted"));

        mockMvc.perform(get("/api/v1/widgets/{id}", UUID.randomUUID()))
            .andExpect(status().isInternalServerError())
            .andExpect(jsonPath("$.error.code").value("INTERNAL"))
            .andExpect(jsonPath("$.error.message").value("Something went wrong."))
            // Ensure internal details are NOT leaked anywhere in the body
            .andExpect(content().string(not(containsString("database"))))
            .andExpect(content().string(not(containsString("pool"))));
    }
}
```

## Error Taxonomy Summary

| Exception | HTTP Status | Error Code | When to Use |
|---|---|---|---|
| `MalformedRequestException` (from `HttpMessageNotReadableException`, `HttpMediaTypeNotSupportedException`) | 400 | `MALFORMED_REQUEST` | Malformed JSON, empty body, wrong content type |
| `ValidationException` (from `MethodArgumentNotValidException`, `MethodArgumentTypeMismatchException`) | 400 | `VALIDATION_FAILED` | Field/format validation — `details[]` lists `{field, code, message}` |
| `UnauthenticatedException` (from Spring Security `AuthenticationException`) | 401 | `UNAUTHENTICATED` | Missing, invalid or expired token (`WWW-Authenticate: Bearer`) |
| `ForbiddenException` (also Spring Security `AccessDeniedException`) | 403 | `FORBIDDEN` | Valid credentials but insufficient permissions |
| `ResourceNotFoundException` | 404 | `NOT_FOUND` | Doesn't exist, soft-deleted, **or belongs to another tenant/owner** |
| `ConflictException` (also `ObjectOptimisticLockingFailureException`, unique violation) | 409 | `CONFLICT` | Duplicate entry, version mismatch, state conflict |
| `ConflictException.idempotencyKeyReused()` | 409 | `IDEMPOTENCY_KEY_REUSED` | Idempotency-Key replayed with a different body |
| `BusinessRuleException` (also FK/check violation) | 422 | `BUSINESS_RULE_VIOLATION` | Valid shape, rejected by a domain rule |
| `RateLimitException` | 429 | `RATE_LIMITED` | Too many requests (`Retry-After`, `retryable: true`) |
| `InternalException` (catch-all) | 500 | `INTERNAL` | Unexpected server error — generic message only |
| `UpstreamServiceException` (also `QueryTimeoutException`, `DataAccessResourceFailureException`) | 503 | `UNAVAILABLE` | A dependency failed or timed out (`Retry-After`, `retryable: true`) |

## Critical Rules

- All application exceptions MUST extend `DomainException` (sealed hierarchy).
- `@RestControllerAdvice` (`GlobalExceptionHandler.write`) is the ONLY code that writes an error body — controllers MUST NOT catch exceptions.
- Every error response is the envelope `{"error": {code, message, details?, request_id, retryable}}` with no `data` key. Do not return Spring's RFC 7807 `ProblemDetail` (`type`/`title`/`detail`) or Spring Boot's default error JSON.
- No client-visible field ever contains an exception's message or cause, SQL, a constraint name, a file path or a stack trace. The client message comes from `getUserMessage()`; the cause is logged with `requestId`.
- Validation errors are 400 `VALIDATION_FAILED` with `details[]` of `{field, code, message}` from a fixed catalog (`FieldError.fromConstraint`) — never validator text.
- Malformed bodies are 400 `MALFORMED_REQUEST`; business-rule rejections are 422 `BUSINESS_RULE_VIOLATION`.
- Database errors: unique violation → 409 `CONFLICT`, FK/check violation → 422 `BUSINESS_RULE_VIOLATION`, query timeout/connection failure → 503 `UNAVAILABLE` — all with generic messages.
- Every error response carries `request_id` (= `X-Request-Id`, set by `RequestIdFilter`) and `retryable`.
- Rate limit (429) and unavailable (503) responses MUST include the `Retry-After` header; 401 responses MUST include `WWW-Authenticate: Bearer`.
- Spring Security's 401/403 MUST go through `SecurityErrorDelegate` so they use the same envelope.
- Log at DEBUG for 4xx errors, ERROR for 5xx — once, in the advice.
- Create domain exceptions at the BOUNDARY where you know the error type.
- Never double-wrap domain exceptions — let them propagate to `@RestControllerAdvice`.
