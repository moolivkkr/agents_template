> **Foundation:** This file extends [shared-backend-patterns.md](../core/shared-backend-patterns.md) with language-specific implementations. Read the shared patterns first for language-agnostic contracts.

---
skill: java
description: Java patterns for Spring Boot — layered architecture, dependency injection, JPA/Hibernate, records, streams, JUnit 5 testing
version: "1.0"
tags:
  - java
  - spring-boot
  - jpa
  - patterns
  - testing
---

# Java patterns and conventions for Spring Boot applications.

> Java samples compile-checked 2026-09-30: JDK 25.0.4.1, Spring Boot 4.1.1, Maven 3.9.16; the Gradle blocks built with Gradle 9.8.0 (`tests/archetype-compile/java/run.sh`). The tenant filter, the repository queries (keyset, `Limit`, projections, specifications) and the Redis cache serializer were also run, on PostgreSQL 16.

## Project Structure
```
src/main/java/com/company/app/
  domain/          # entities, value objects, domain services
  application/     # use cases, application services
  infrastructure/  # repositories impl, external adapters
  api/             # controllers, DTOs, mappers
  config/          # Spring configuration classes
src/test/java/
  unit/
  integration/
```

## Dependency Injection
- Constructor injection always — not field injection (`@Autowired` on field)
- Makes dependencies explicit and classes testable without Spring context
```java
// Good
@Service
public class UserService {
    private final UserRepository repo;
    public UserService(UserRepository repo) { this.repo = repo; }
}

// Bad
@Service
public class UserService {
    @Autowired private UserRepository repo;
}
```

## Records for DTOs
```java
public record CreateUserRequest(
    @NotBlank String email,
    @Size(min = 8) String password
) {}
```
Use Java records for immutable DTOs — no Lombok needed.

## Optional
- Never return `null` from public methods — use `Optional<T>`
- Never call `.get()` without checking — use `.orElseThrow()` or `.orElse()`
- Don't use `Optional` as method parameter — use overloads

---

## Spring Boot Patterns

### Annotation Guide
```java
// @Service — business logic layer
@Service
@Transactional(readOnly = true) // default read-only for queries
public class OrderService {
    private final OrderRepository orderRepo;
    private final EventPublisher eventPublisher;
    private final CacheManager cacheManager;

    // Single constructor — @Autowired is implicit
    public OrderService(
        OrderRepository orderRepo,
        EventPublisher eventPublisher,
        CacheManager cacheManager
    ) {
        this.orderRepo = orderRepo;
        this.eventPublisher = eventPublisher;
        this.cacheManager = cacheManager;
    }

    @Transactional // read-write override for mutations
    public Order createOrder(UUID tenantId, CreateOrderRequest request) {
        var order = Order.create(tenantId, request);
        order = orderRepo.save(order);
        eventPublisher.publish(new OrderCreatedEvent(order));
        return order;
    }

    public Optional<Order> findById(UUID tenantId, UUID orderId) {
        return orderRepo.findByTenantIdAndIdAndDeletedAtIsNull(tenantId, orderId);
    }
}

// @Repository — data access layer
@Repository
public interface OrderRepository extends JpaRepository<Order, UUID> {
    Optional<Order> findByTenantIdAndIdAndDeletedAtIsNull(UUID tenantId, UUID id);
    List<Order> findByTenantIdAndStatusAndDeletedAtIsNull(UUID tenantId, OrderStatus status);
}

// @RestController — HTTP layer
@RestController
@RequestMapping("/api/v1/orders")
public class OrderController {
    private final OrderService orderService;

    public OrderController(OrderService orderService) { this.orderService = orderService; }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public ApiResponse<OrderResponse> createOrder(@Valid @RequestBody CreateOrderRequest request) {
        // set by TenantFilter from the verified JWT — never from a request header or body
        var order = orderService.createOrder(TenantContext.getCurrentTenantId(), request);
        return ApiResponse.success(OrderMapper.toResponse(order));
    }
}
```

### Profiles and Configuration
```yaml
# application.yml — base config
spring:
  profiles:
    active: ${SPRING_PROFILES_ACTIVE:local}

# application-local.yml — dev overrides
spring:
  datasource:
    url: jdbc:postgresql://localhost:5432/myapp
  jpa:
    show-sql: true

# application-prod.yml — production
spring:
  datasource:
    url: ${DATABASE_URL}
  jpa:
    show-sql: false
```

```java
// Type-safe config binding
@ConfigurationProperties(prefix = "app")
public record AppProperties(
    String name,
    Duration requestTimeout,
    int maxRetries,
    TenantDefaults tenantDefaults
) {
    public record TenantDefaults(int maxUsers, long storageLimitBytes) {}
}

// Enable with @EnableConfigurationProperties(AppProperties.class) in @Configuration
```

### @Transactional Rules
```java
// Service layer owns transactions — not repository, not controller
@Service
@Transactional(readOnly = true) // class-level default: read-only
public class PaymentService {
    private final PaymentRepository paymentRepo;
    private final LedgerService ledgerService;

    public PaymentService(PaymentRepository paymentRepo, LedgerService ledgerService) {
        this.paymentRepo = paymentRepo;
        this.ledgerService = ledgerService;
    }

    @Transactional // method-level: read-write
    public Payment processPayment(UUID tenantId, PaymentRequest request) {
        // Entire method runs in a single transaction
        var payment = Payment.create(tenantId, request);
        payment = paymentRepo.save(payment);
        ledgerService.recordEntry(tenantId, payment); // same transaction
        return payment;
    }

    // readOnly = true: Hibernate skips dirty checking and flushing; a routing DataSource can send it to a replica
    public List<Payment> listPayments(UUID tenantId) {
        return paymentRepo.findByTenantId(tenantId);
    }
}

// NEVER: @Transactional on @Controller — keeps transactions too long
// NEVER: @Transactional on private methods — Spring proxies can't intercept them
// CAUTION: self-invocation bypasses @Transactional proxy — use separate beans
```

---

## Multi-Tenancy in Java

### Hibernate Filters for Tenant Isolation
```java
// Entity with tenant annotation
@Entity
@Table(name = "orders")
@FilterDef(name = "tenantFilter", parameters = @ParamDef(name = "tenantId", type = UUID.class))
@Filter(name = "tenantFilter", condition = "tenant_id = :tenantId")
@SQLRestriction("deleted_at IS NULL") // soft delete filter (@Where is gone in Hibernate 7)
public class Order {
    @Id
    private UUID id;

    @Column(name = "tenant_id", nullable = false)
    private UUID tenantId;

    @Column(name = "deleted_at")
    private Instant deletedAt;

    @Version
    private Integer version; // optimistic locking
}

// Enable the filter INSIDE each transaction. A Hibernate filter belongs to one Session, and with
// spring.jpa.open-in-view=false (spring-boot.md) the Session a @Transactional method uses only exists once
// its transaction starts. Enabled earlier (a HandlerInterceptor, a servlet filter), it lands on a Session no
// repository call uses, and every tenant's rows come back.
@Component
public class TenantFilterActivator {
    private final EntityManager entityManager;

    public TenantFilterActivator(EntityManager entityManager) {
        this.entityManager = entityManager;
    }

    /** First call in every @Transactional service method that reads tenant data. */
    public void enable() {
        entityManager.unwrap(Session.class)
            .enableFilter("tenantFilter")
            .setParameter("tenantId", TenantContext.getCurrentTenantId());
    }
}

// In the service:
//   @Transactional(readOnly = true)
//   public List<Order> listOrders() {
//       tenantFilter.enable();       // the transaction's Session exists now
//       return orderRepo.findAll();  // ... WHERE tenant_id = ? AND deleted_at IS NULL
//   }
// Filters cover queries, not load-by-id: findById/em.find return another tenant's row unless the
// @FilterDef sets applyToLoadByKey = true. Keep tenantId in by-id lookups (findByTenantIdAndId...).
```

### ThreadLocal Tenant Context
```java
public class TenantContext {
    private static final ThreadLocal<UUID> CURRENT_TENANT = new ThreadLocal<>();

    public static void setCurrentTenantId(UUID tenantId) {
        CURRENT_TENANT.set(tenantId);
    }

    public static UUID getCurrentTenantId() {
        UUID tenantId = CURRENT_TENANT.get();
        if (tenantId == null) {
            throw new IllegalStateException("No tenant context set");
        }
        return tenantId;
    }

    public static void clear() {
        CURRENT_TENANT.remove(); // CRITICAL: prevent memory leaks in thread pools
    }
}

// Filter sets and clears tenant context. The tenant comes from the VERIFIED JWT, never from a
// client-supplied header on its own (anyone can send one: cross-tenant access).
// Not a @Component: Boot would also register it as a servlet filter that runs BEFORE authentication.
// SecurityConfig adds it after BearerTokenAuthenticationFilter, once the token's signature is checked.
public class TenantFilter extends OncePerRequestFilter {
    @Override
    protected void doFilterInternal(
        HttpServletRequest request, HttpServletResponse response, FilterChain chain
    ) throws ServletException, IOException {
        try {
            if (!(SecurityContextHolder.getContext().getAuthentication() instanceof JwtAuthenticationToken auth)) {
                chain.doFilter(request, response); // no token: authorizeHttpRequests answers 401 (envelope)
                return;
            }
            UUID tenantId = resolveTenant(auth.getToken(), request.getHeader("X-Tenant-ID"));
            if (tenantId == null) {
                // Filters run outside @RestControllerAdvice, and sendError() would render Spring Boot's
                // /error body, which is not the envelope — write the envelope directly.
                ErrorResponse.of("FORBIDDEN", "You don't have permission to do this.", List.of(), false)
                    .writeTo(response, 403);
                return;
            }
            TenantContext.setCurrentTenantId(tenantId);
            MDC.put("tenant_id", tenantId.toString()); // structured logging
            chain.doFilter(request, response);
        } finally {
            TenantContext.clear();
            MDC.remove("tenant_id");
        }
    }

    // The token's tenant_id claim. For users who belong to several tenants, X-Tenant-ID may only
    // SELECT one the token already lists in tenant_ids; it can never add a tenant. Otherwise → 403.
    private static UUID resolveTenant(Jwt jwt, String requested) {
        String home = jwt.getClaimAsString("tenant_id");
        List<String> allowed = Optional.ofNullable(jwt.getClaimAsStringList("tenant_ids")).orElse(List.of());
        String chosen = requested == null ? home : requested;
        boolean permitted = chosen != null && (chosen.equals(home) || allowed.contains(chosen));
        return permitted ? UUID.fromString(chosen) : null;
    }
}
```

### Spring Security Integration
```java
@Configuration
@EnableWebSecurity
public class SecurityConfig {

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        // Security's 401/403 happen in the filter chain, outside @RestControllerAdvice — write the envelope here
        AuthenticationEntryPoint unauthenticated = (req, res, e) -> ErrorResponse
            .of("UNAUTHENTICATED", "Sign in to continue.", List.of(), false).writeTo(res, 401);
        AccessDeniedHandler forbidden = (req, res, e) -> ErrorResponse
            .of("FORBIDDEN", "You don't have permission to do this.", List.of(), false).writeTo(res, 403);
        return http
            // after the bearer token is verified — TenantFilter reads the tenant from that token
            .addFilterAfter(new TenantFilter(), BearerTokenAuthenticationFilter.class)
            .oauth2ResourceServer(oauth2 -> oauth2
                .jwt(jwt -> jwt.jwtAuthenticationConverter(tenantJwtConverter()))
                .authenticationEntryPoint(unauthenticated) // invalid/expired bearer token
            )
            .exceptionHandling(ex -> ex
                .authenticationEntryPoint(unauthenticated)
                .accessDeniedHandler(forbidden)
            )
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/api/v1/health").permitAll()
                .requestMatchers("/api/v1/**").authenticated()
            )
            .build();
    }

    private JwtAuthenticationConverter tenantJwtConverter() {
        var converter = new JwtAuthenticationConverter();
        // Roles/permissions only. The tenant is set (and cleared) per request by TenantFilter —
        // setting a ThreadLocal here would never be cleared.
        converter.setJwtGrantedAuthoritiesConverter(jwt -> extractAuthorities(jwt));
        return converter;
    }

    // The token's "roles" claim → ROLE_* authorities
    private static Collection<GrantedAuthority> extractAuthorities(Jwt jwt) {
        return Optional.ofNullable(jwt.getClaimAsStringList("roles")).orElse(List.of()).stream()
            .map(role -> (GrantedAuthority) new SimpleGrantedAuthority("ROLE_" + role))
            .toList();
    }
}
```

---

## API Response Envelope

Every body is the envelope in `api/response-envelope.md`; if anything here disagrees, that file wins.

```java
// Success: {"data": …, "meta": {"request_id": …}}; lists add meta.pagination (cursor only, never offset)
public record ApiResponse<T>(T data, Meta meta) {

    public record Meta(
        @JsonProperty("request_id") String requestId,
        @JsonInclude(JsonInclude.Include.NON_NULL) Pagination pagination // lists only
    ) {}

    public record Pagination(
        @JsonProperty("next_cursor") String nextCursor, // serialized as null when hasMore is false
        @JsonProperty("has_more") boolean hasMore,
        int limit,
        @JsonProperty("total_count") @JsonInclude(JsonInclude.Include.NON_NULL) Long totalCount // only if cheap and shown
    ) {}

    public static <T> ApiResponse<T> success(T data) {
        return new ApiResponse<>(data, new Meta(RequestId.current(), null));
    }

    public static <T> ApiResponse<List<T>> page(List<T> data, String nextCursor, int limit) {
        return new ApiResponse<>(data, new Meta(RequestId.current(),
            new Pagination(nextCursor, nextCursor != null, limit, null)));
    }
}

// Error: {"error": {code, message, details?, request_id, retryable}} — no data key, no stack, no cause
public record ErrorResponse(Body error) {

    public record Body(
        String code,    // UPPER_SNAKE, stable: VALIDATION_FAILED, NOT_FOUND, …
        String message, // user-safe catalog text
        @JsonInclude(JsonInclude.Include.NON_EMPTY) List<FieldError> details, // VALIDATION_FAILED only
        @JsonProperty("request_id") String requestId,
        boolean retryable
    ) {}

    public record FieldError(String field, String code, String message) {} // code is lower_snake

    public static ErrorResponse of(String code, String message, List<FieldError> details, boolean retryable) {
        return new ErrorResponse(new Body(code, message, details, RequestId.current(), retryable));
    }

    private static final JsonMapper MAPPER = JsonMapper.shared(); // Jackson 3 (tools.jackson), as Spring Boot 4

    // For servlet filters and Spring Security handlers, which run outside @RestControllerAdvice
    public void writeTo(HttpServletResponse response, int status) throws IOException {
        response.setStatus(status);
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        if (status == 401) response.setHeader(HttpHeaders.WWW_AUTHENTICATE, "Bearer");
        MAPPER.writeValue(response.getOutputStream(), this);
    }
}

// RequestId.current(): the id a first-in-chain filter took from X-Request-Id (or generated), put in MDC
// as "request_id" and echoed on the response header, so the body and the header always match.

// List endpoint: ?cursor=<opaque>&limit=<n>. A limit outside 1..100 is a 400 with details[], never clamped:
// a client asking for 500 must learn it gets at most 100.
@GetMapping
public ApiResponse<List<OrderResponse>> listOrders(
    @RequestParam(required = false) String cursor,
    @RequestParam(defaultValue = "20") int limit
) {
    if (limit < 1 || limit > 100) {
        throw new ValidationException(List.of(new ErrorResponse.FieldError(
            "limit", "out_of_range", "Limit must be a whole number from 1 to 100.")));
    }
    var page = orderService.listOrders(TenantContext.getCurrentTenantId(), cursor, limit); // from the verified JWT
    return ApiResponse.page(page.items().stream().map(OrderMapper::toResponse).toList(), page.nextCursor(), limit);
}
```

## Error Handling

### @RestControllerAdvice with @ExceptionHandler
```java
@RestControllerAdvice
public class GlobalExceptionHandler extends ResponseEntityExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    @ExceptionHandler(AppException.class)
    public ResponseEntity<ErrorResponse> handleAppException(AppException ex) {
        if (ex.getStatusCode() >= 500) {
            log.error("request_failed code={} request_id={}", ex.getCode(), RequestId.current(), ex); // cause: logs only
        } else {
            log.warn("app_error code={} request_id={}", ex.getCode(), RequestId.current());
        }
        var response = ResponseEntity.status(ex.getStatusCode());
        if (ex.getRetryAfterSeconds() > 0) {
            response.header(HttpHeaders.RETRY_AFTER, String.valueOf(ex.getRetryAfterSeconds()));
        }
        if (ex.getStatusCode() == 401) {
            response.header(HttpHeaders.WWW_AUTHENTICATE, "Bearer");
        }
        return response.body(ErrorResponse.of(ex.getCode(), ex.getUserMessage(), ex.getDetails(), ex.isRetryable()));
    }

    // @Valid body → 400 VALIDATION_FAILED. The constraint becomes a stable lower_snake code with a catalog
    // message; getDefaultMessage() is never sent (it isn't written for your users).
    @Override
    protected ResponseEntity<Object> handleMethodArgumentNotValid(
        MethodArgumentNotValidException ex, HttpHeaders headers, HttpStatusCode status, WebRequest request
    ) {
        var details = ex.getBindingResult().getFieldErrors().stream()
            .map(e -> FieldErrorCatalog.of(e.getField(), e.getCode())) // "NotBlank" → required, "Email" → invalid_format
            .toList();
        return ResponseEntity.badRequest()
            .body(ErrorResponse.of("VALIDATION_FAILED", "Some fields are invalid.", details, false));
    }

    // Every other Spring MVC exception (unreadable JSON, wrong content type, missing or mistyped param,
    // unknown route, wrong method, …) lands here. Its default body is a ProblemDetail, not the envelope:
    // replace it, keep the framework's status (405 keeps its Allow header), and log the framework's text.
    @Override
    protected ResponseEntity<Object> handleExceptionInternal(
        Exception ex, Object body, HttpHeaders headers, HttpStatusCode status, WebRequest request
    ) {
        log.info("framework_error status={} request_id={}", status.value(), RequestId.current(), ex);
        ErrorResponse error;
        if (status.value() == 404) {
            error = ErrorResponse.of("NOT_FOUND", "Not found.", List.of(), false);
        } else if (status.is4xxClientError()) {
            error = ErrorResponse.of("MALFORMED_REQUEST", "The request could not be read.", List.of(), false);
        } else {
            error = ErrorResponse.of("INTERNAL", "Something went wrong.", List.of(), false);
        }
        return ResponseEntity.status(status).headers(headers).body(error);
    }

    // Anything else → 500 INTERNAL with a generic message; the cause is logged under request_id
    @ExceptionHandler(Exception.class)
    public ResponseEntity<ErrorResponse> handleUnexpected(Exception ex) {
        log.error("unhandled_error request_id={}", RequestId.current(), ex);
        return ResponseEntity.internalServerError()
            .body(ErrorResponse.of("INTERNAL", "Something went wrong.", List.of(), false));
    }
}

// Constraint → stable lower_snake code + fixed catalog message (document the codes in data-contracts.md).
// e.getField() is the Java property path — make it the JSON field name if your naming strategy differs.
final class FieldErrorCatalog {
    private record Entry(String code, String message) {}

    private static final Map<String, Entry> BY_CONSTRAINT = Map.of(
        "NotNull",  new Entry("required", "This field is required."),
        "NotBlank", new Entry("required", "This field is required."),
        "Email",    new Entry("invalid_format", "Enter a valid email address."),
        "Size",     new Entry("invalid_length", "This value is too short or too long."),
        "Pattern",  new Entry("invalid_format", "This value has the wrong format."));
    private static final Entry FALLBACK = new Entry("invalid", "This value is invalid.");

    static ErrorResponse.FieldError of(String field, String constraint) {
        var entry = BY_CONSTRAINT.getOrDefault(constraint, FALLBACK);
        return new ErrorResponse.FieldError(field, entry.code(), entry.message());
    }
}
```

### Custom Exception Hierarchy
```java
// Base exception — code, status and user message follow api/response-envelope.md
public abstract class AppException extends RuntimeException {
    private final String code;        // UPPER_SNAKE, stable
    private final String userMessage; // user-safe catalog text: the only text a client sees
    private final int statusCode;
    private final boolean retryable;

    // logMessage and cause are server-side only: they reach logs, never the response body
    protected AppException(String code, String userMessage, int statusCode, boolean retryable,
                           String logMessage, Throwable cause) {
        super(logMessage, cause);
        this.code = code;
        this.userMessage = userMessage;
        this.statusCode = statusCode;
        this.retryable = retryable;
    }

    protected AppException(String code, String userMessage, int statusCode) {
        this(code, userMessage, statusCode, false, code + ": " + userMessage, null);
    }

    public String getCode() { return code; }
    public String getUserMessage() { return userMessage; }
    public int getStatusCode() { return statusCode; }
    public boolean isRetryable() { return retryable; }
    public List<ErrorResponse.FieldError> getDetails() { return List.of(); } // ValidationException overrides
    public int getRetryAfterSeconds() { return 0; }                          // 429/503 override
}

// One domain error type per row of the envelope's status table
public class MalformedRequestException extends AppException {  // 400: unreadable body, wrong content type
    public MalformedRequestException(Throwable cause) {
        super("MALFORMED_REQUEST", "The request could not be read.", 400, false, "malformed request", cause);
    }
}

public class ValidationException extends AppException {        // 400: details[] lists the fields
    private final List<ErrorResponse.FieldError> details;
    public ValidationException(List<ErrorResponse.FieldError> details) {
        super("VALIDATION_FAILED", "Some fields are invalid.", 400);
        this.details = List.copyOf(details);
    }
    @Override public List<ErrorResponse.FieldError> getDetails() { return details; }
}

public class UnauthenticatedException extends AppException {   // 401: missing/invalid/expired credentials
    public UnauthenticatedException() {
        super("UNAUTHENTICATED", "Sign in to continue.", 401);
    }
}

public class ForbiddenException extends AppException {         // 403: authenticated, not allowed
    public ForbiddenException(String action) {
        super("FORBIDDEN", "You don't have permission to do this.", 403, false, "forbidden: " + action, null);
    }
}

public class NotFoundException extends AppException {          // 404: missing OR another tenant's (never 403)
    public NotFoundException(String resource, String id) {
        super("NOT_FOUND", resource + " not found.", 404, false, resource + " " + id + " not found", null);
    }
}

public class ConflictException extends AppException {          // 409: duplicate, version mismatch
    public ConflictException(String message) {                  // message: user-safe catalog text
        super("CONFLICT", message, 409);
    }
}

public class BusinessRuleException extends AppException {      // 422: valid shape, rejected by a domain rule
    public BusinessRuleException(String message) {
        super("BUSINESS_RULE_VIOLATION", message, 422);
    }
}

public class RateLimitException extends AppException {         // 429: Retry-After, retryable
    private final int retryAfter;
    public RateLimitException(int retryAfterSeconds) {
        super("RATE_LIMITED", "Too many requests. Try again shortly.", 429, true, "rate limited", null);
        this.retryAfter = retryAfterSeconds;
    }
    @Override public int getRetryAfterSeconds() { return retryAfter; }
}

public class UnavailableException extends AppException {       // 503: a dependency failed or timed out
    public UnavailableException(String service, Throwable cause) {
        super("UNAVAILABLE", "The service is temporarily unavailable.", 503, true,
              "upstream " + service + " failed", cause);        // the service name goes to logs only
    }
    @Override public int getRetryAfterSeconds() { return 5; }
}

public class InternalException extends AppException {          // 500: generic message; detail goes to logs
    public InternalException(String detail, Throwable cause) {
        super("INTERNAL", "Something went wrong.", 500, false, detail, cause);
    }
}
```

### Not ProblemDetail
Spring 6's `ProblemDetail` (RFC 7807: `type`, `title`, `status`, `detail`) is a different error shape. Don't
return it from API handlers: `handleExceptionInternal` above replaces it for Spring's own exceptions. Leave
`spring.mvc.problemdetails.enabled` at its default (`false`).

---

## Repository Pattern

### Spring Data JPA Repositories
```java
public interface OrderRepository extends JpaRepository<Order, UUID>, JpaSpecificationExecutor<Order> {

    // Derived query methods — Spring generates SQL from method name
    Optional<Order> findByTenantIdAndIdAndDeletedAtIsNull(UUID tenantId, UUID id);

    // Limit, not Pageable: lists are cursor-paginated, never by offset (api/response-envelope.md)
    List<Order> findByTenantIdAndStatusAndDeletedAtIsNull(
        UUID tenantId, OrderStatus status, Limit limit
    );

    // JPQL for complex queries
    @Query("""
        SELECT o FROM Order o
        WHERE o.tenantId = :tenantId
          AND o.status IN :statuses
          AND o.deletedAt IS NULL
        ORDER BY o.createdAt DESC, o.id DESC
        """)
    List<Order> findByStatuses(
        @Param("tenantId") UUID tenantId,
        @Param("statuses") Set<OrderStatus> statuses,
        Limit limit
    );

    // Native keyset query. The cursor is (created_at, id), which is unique: on created_at alone, rows that
    // share a timestamp across a page boundary are skipped.
    @Query(value = """
        SELECT o.* FROM orders o
        WHERE o.tenant_id = :tenantId
          AND (o.created_at, o.id) < (:cursorCreatedAt, :cursorId)
          AND o.deleted_at IS NULL
        ORDER BY o.created_at DESC, o.id DESC
        LIMIT :limit
        """, nativeQuery = true)
    List<Order> findWithCursor(
        @Param("tenantId") UUID tenantId,
        @Param("cursorCreatedAt") Instant cursorCreatedAt,
        @Param("cursorId") UUID cursorId,
        @Param("limit") int limit
    );

    // Modifying queries
    @Modifying
    @Query("UPDATE Order o SET o.deletedAt = CURRENT_TIMESTAMP WHERE o.tenantId = :tenantId AND o.id = :id")
    int softDelete(@Param("tenantId") UUID tenantId, @Param("id") UUID id);
}
```

### Specifications for Dynamic Queries
```java
public class OrderSpecifications {

    public static Specification<Order> belongsToTenant(UUID tenantId) {
        return (root, query, cb) -> cb.equal(root.get("tenantId"), tenantId);
    }

    public static Specification<Order> isNotDeleted() {
        return (root, query, cb) -> cb.isNull(root.get("deletedAt"));
    }

    public static Specification<Order> hasStatus(OrderStatus status) {
        return (root, query, cb) -> cb.equal(root.get("status"), status);
    }

    public static Specification<Order> createdBetween(Instant from, Instant to) {
        return (root, query, cb) -> cb.between(root.get("createdAt"), from, to);
    }
}

// Usage — compose specifications dynamically, then scroll by keyset (no offset pages)
Specification<Order> spec = Specification
    .where(belongsToTenant(tenantId))
    .and(isNotDeleted())
    .and(hasStatus(PENDING))
    .and(createdBetween(startDate, endDate));

Window<Order> orders = orderRepo.findBy(spec, q -> q
    .sortBy(Sort.by(Sort.Direction.DESC, "createdAt", "id")) // a unique sort key
    .limit(20)
    .scroll(position)); // ScrollPosition.keyset() first; then orders.positionAt(orders.size() - 1)
```

### Projections
```java
// Interface-based projection — only fetches selected columns
public interface OrderSummary {
    UUID getId();
    OrderStatus getStatus();
    BigDecimal getTotal();
    Instant getCreatedAt();
}

// Repository returns projection — keyset-scrolled, so it exposes the sort keys (createdAt, id)
Window<OrderSummary> findFirst20ByTenantIdAndDeletedAtIsNullOrderByCreatedAtDescIdDesc(
    UUID tenantId, ScrollPosition position);

// Record-based projection (JPA)
public record OrderStats(OrderStatus status, long count, BigDecimal totalAmount) {}

@Query("""
    SELECT new com.company.app.dto.OrderStats(o.status, COUNT(o), SUM(o.total))
    FROM Order o WHERE o.tenantId = :tenantId AND o.deletedAt IS NULL
    GROUP BY o.status
    """)
List<OrderStats> getStatsByTenant(@Param("tenantId") UUID tenantId);
```

---

## Testing in Java

### JUnit 5 Patterns
```java
@ExtendWith(MockitoExtension.class)
class OrderServiceTest {

    @Mock private OrderRepository orderRepo;
    @Mock private EventPublisher eventPublisher;
    @InjectMocks private OrderService orderService;

    private static final UUID TENANT_ID = UUID.fromString("00000000-0000-0000-0000-000000000001");

    @Test
    void createOrder_validRequest_returnsOrder() {
        var request = new CreateOrderRequest(List.of(
            new LineItem("SKU-001", 2, BigDecimal.TEN)
        ));
        when(orderRepo.save(any())).thenAnswer(inv -> inv.getArgument(0));

        var order = orderService.createOrder(TENANT_ID, request);

        assertThat(order.getTenantId()).isEqualTo(TENANT_ID);
        assertThat(order.getStatus()).isEqualTo(OrderStatus.PENDING);
        verify(eventPublisher).publish(any(OrderCreatedEvent.class));
    }

    @Test
    void createOrder_emptyItems_throwsValidation() {
        var request = new CreateOrderRequest(List.of());

        assertThatThrownBy(() -> orderService.createOrder(TENANT_ID, request))
            .isInstanceOf(ValidationException.class)
            .satisfies(e -> assertThat(((ValidationException) e).getDetails()).hasSize(1));
    }
}
```

### @ParameterizedTest
```java
@ParameterizedTest
@CsvSource({
    "valid@email.com, true",
    "not-email, false",
    "'', false",
    "a@b.c, true",
})
void testEmailValidation(String email, boolean expected) {
    assertEquals(expected, EmailValidator.isValid(email));
}

@ParameterizedTest
@MethodSource("orderStatusTransitions")
void testValidStatusTransition(OrderStatus from, OrderStatus to, boolean valid) {
    assertEquals(valid, Order.isValidTransition(from, to));
}

static Stream<Arguments> orderStatusTransitions() {
    return Stream.of(
        Arguments.of(PENDING, CONFIRMED, true),
        Arguments.of(PENDING, CANCELLED, true),
        Arguments.of(CONFIRMED, PENDING, false),
        Arguments.of(SHIPPED, CANCELLED, false)
    );
}
```

### @SpringBootTest & @DataJpaTest
```java
// Slim test — only loads JPA layer (Spring Boot 4: org.springframework.boot.data.jpa.test.autoconfigure)
@DataJpaTest
@AutoConfigureTestDatabase(replace = Replace.NONE) // use testcontainers
class OrderRepositoryTest {

    @Autowired private OrderRepository orderRepo;
    @Autowired private TestEntityManager em;

    @Test
    void findByTenantId_excludesDeletedOrders() {
        var tenantId = UUID.randomUUID();
        var active = createOrder(tenantId, null);
        var deleted = createOrder(tenantId, Instant.now());

        var results = orderRepo.findByTenantIdAndStatusAndDeletedAtIsNull(tenantId, OrderStatus.PENDING);

        assertThat(results).containsExactly(active);
        assertThat(results).doesNotContain(deleted);
    }

    private Order createOrder(UUID tenantId, Instant deletedAt) {
        var order = Order.create(tenantId, new CreateOrderRequest(List.of(new LineItem("SKU-001", 1, BigDecimal.TEN))));
        order.setDeletedAt(deletedAt);
        return em.persistFlushFind(order);
    }
}

// Full integration test — loads entire context. Spring Boot 4: TestRestTemplate is in spring-boot-resttestclient
// (org.springframework.boot.resttestclient) and needs @AutoConfigureTestRestTemplate.
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@AutoConfigureTestRestTemplate
class OrderApiIntegrationTest {

    private static final UUID TENANT_ID = UUID.fromString("00000000-0000-0000-0000-000000000001");
    private static final UUID OTHER_TENANT_ID = UUID.fromString("00000000-0000-0000-0000-000000000002");

    @Autowired private TestRestTemplate restTemplate;

    // TestTokens: signs JWTs with the test key that the test profile's JwtDecoder trusts
    @Test
    void createOrder_returns201() {
        var request = new CreateOrderRequest(List.of(new LineItem("SKU-001", 1, BigDecimal.TEN)));
        var headers = new HttpHeaders();
        headers.setBearerAuth(TestTokens.forTenant(TENANT_ID)); // tenant comes from the token's claim

        var response = restTemplate.exchange(
            "/api/v1/orders", HttpMethod.POST,
            new HttpEntity<>(request, headers), ApiResponse.class
        );

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.CREATED);
    }

    @Test
    void tenantHeaderForAnotherTenant_returns403() {
        var headers = new HttpHeaders();
        headers.setBearerAuth(TestTokens.forTenant(TENANT_ID));
        headers.set("X-Tenant-ID", OTHER_TENANT_ID.toString()); // not in the token's tenants

        var response = restTemplate.exchange(
            "/api/v1/orders", HttpMethod.GET, new HttpEntity<>(headers), ErrorResponse.class
        );

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
        assertThat(response.getBody().error().code()).isEqualTo("FORBIDDEN");
    }
}
```

### Testcontainers
```java
@Testcontainers
@SpringBootTest
class IntegrationTestBase {

    // Testcontainers 2: org.testcontainers.postgresql.PostgreSQLContainer (no type parameter)
    @Container
    @ServiceConnection // Spring Boot points spring.datasource.* at the container
    static PostgreSQLContainer postgres = new PostgreSQLContainer("postgres:16-alpine");
}

// Extend for all integration tests
class OrderServiceIntegrationTest extends IntegrationTestBase {
    @Autowired private OrderService orderService;

    @Test
    void processOrder_endToEnd() {
        // Tests against real PostgreSQL — no mocks
    }
}
```

### AssertJ Fluent Assertions
```java
// Object assertions
assertThat(order)
    .isNotNull()
    .extracting(Order::getStatus, Order::getTenantId)
    .containsExactly(OrderStatus.PENDING, TENANT_ID);

// Collection assertions
assertThat(orders)
    .hasSize(3)
    .extracting(Order::getStatus)
    .containsOnly(OrderStatus.PENDING, OrderStatus.CONFIRMED);

// Exception assertions — the field name is in details[], not in the (catalog) message
assertThatThrownBy(() -> service.processPayment(TENANT_ID, invalidRequest))
    .isInstanceOf(ValidationException.class)
    .satisfies(e -> assertThat(((ValidationException) e).getDetails())
        .extracting(ErrorResponse.FieldError::field)
        .contains("amount"))
    .extracting("code")
    .isEqualTo("VALIDATION_FAILED");
```

---

## Performance

### Connection Pooling (HikariCP)
```yaml
spring:
  datasource:
    hikari:
      minimum-idle: 5
      maximum-pool-size: 20
      idle-timeout: 300000        # 5 minutes
      max-lifetime: 1800000       # 30 minutes
      connection-timeout: 30000   # 30 seconds
      leak-detection-threshold: 60000  # log connections held > 60s
```
- HikariCP is the default in Spring Boot — no need to add dependency
- `maximum-pool-size`: rule of thumb = `(core_count * 2) + effective_spindle_count`
- Monitor `hikaricp_connections_active` metric for right-sizing

### Caching with @Cacheable
```java
@Service
public class UserService {
    private final UserRepository userRepo;

    public UserService(UserRepository userRepo) { this.userRepo = userRepo; }

    @Cacheable(value = "users", key = "#tenantId + ':' + #userId")
    public UserResponse getUser(UUID tenantId, UUID userId) {
        return userRepo.findByTenantIdAndId(tenantId, userId)
            .map(UserMapper::toResponse)
            .orElseThrow(() -> new NotFoundException("User", userId.toString()));
    }

    @CacheEvict(value = "users", key = "#tenantId + ':' + #userId")
    @Transactional
    public UserResponse updateUser(UUID tenantId, UUID userId, UpdateUserRequest request) {
        // Cache is evicted AFTER method completes successfully
        var user = userRepo.findByTenantIdAndId(tenantId, userId)
            .orElseThrow(() -> new NotFoundException("User", userId.toString()));
        user.apply(request);
        return UserMapper.toResponse(userRepo.save(user));
    }

    @CacheEvict(value = "users", allEntries = true)
    public void evictAllUserCache() {
        // Admin operation — clear entire cache
    }
}

// Cache config with Redis. Jackson 3 serializer: Spring Data Redis 4 deprecated the Jackson 2 one for removal.
// The type id brings a cached UserResponse back as one; the validator accepts your packages and the mutable
// JDK collections a cached method returns — named, never all of "java.util." (gadget classes live there).
// List.of(..) / Stream.toList() are final JDK types written without a type id: cache new ArrayList<>(list).
@Configuration
@EnableCaching
public class CacheConfig {
    @Bean
    public RedisCacheConfiguration cacheConfiguration() {
        var serializer = GenericJacksonJsonRedisSerializer.builder()
            .enableDefaultTyping(BasicPolymorphicTypeValidator.builder()
                .allowIfSubType("com.company.app.")
                .allowIfSubType(ArrayList.class)
                .allowIfSubType(HashSet.class)
                .allowIfSubType(HashMap.class)
                .build())
            .build();
        return RedisCacheConfiguration.defaultCacheConfig()
            .entryTtl(Duration.ofMinutes(10))
            .serializeValuesWith(SerializationPair.fromSerializer(serializer));
    }
}
```

### Virtual Threads (Java 21+)
```yaml
# Enable virtual threads (Spring Boot 3.2+): Tomcat, @Async and scheduling all use them
spring:
  threads:
    virtual:
      enabled: true
```

```java
// Or configure Tomcat manually
@Bean
public TomcatProtocolHandlerCustomizer<?> protocolHandlerVirtualThreadExecutorCustomizer() {
    return handler -> handler.setExecutor(Executors.newVirtualThreadPerTaskExecutor());
}

// Virtual threads are ideal for I/O-bound workloads (HTTP calls, DB queries)
// No need for reactive (WebFlux) for most services — virtual threads handle blocking I/O efficiently
// JDK 21-23: a blocking call inside synchronized pins the carrier thread — use ReentrantLock there.
//   JDK 24+ (JEP 491) no longer pins on synchronized; native code and class initialisation still do.
// ThreadLocal does not pin, but each of millions of virtual threads gets its own copy: prefer ScopedValue
//   (final in JDK 25, JEP 506) for request-scoped context.
```

### Reactive (WebFlux) — When to Use
```java
// Use WebFlux ONLY when:
// 1. Streaming large datasets (SSE, WebSocket)
// 2. Very high concurrency (10K+ concurrent connections)
// 3. Non-blocking I/O is critical throughout the stack
// For most CRUD services: prefer Spring MVC + virtual threads

@RestController
public class StreamController {
    private final OrderEventService orderEventService;

    public StreamController(OrderEventService orderEventService) { this.orderEventService = orderEventService; }

    @GetMapping(value = "/stream/orders", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<OrderEvent> streamOrders(@AuthenticationPrincipal Jwt jwt) {
        // tenant from the verified token — a tenantId query param would let anyone subscribe to any tenant
        UUID tenantId = UUID.fromString(jwt.getClaimAsString("tenant_id"));
        return orderEventService.subscribe(tenantId)
            .filter(event -> event.getTenantId().equals(tenantId));
    }
}
```

---

## Build and Tooling

### Gradle vs Maven
```
Gradle:
  + Faster builds (incremental, build cache, daemon)
  + Kotlin DSL with IDE auto-completion
  + Better for multi-module projects
  - Steeper learning curve
  - Build script can become complex

Maven:
  + Simpler mental model (convention over configuration)
  + XML is declarative and predictable
  + Better IDE integration (out of the box)
  - Slower builds
  - Verbose XML configuration

Recommendation: Gradle for new projects, Maven is fine for existing ones
```

### Gradle Kotlin DSL Example
```kotlin
// build.gradle.kts
plugins {
    java
    id("org.springframework.boot") version "4.1.1"
    id("io.spring.dependency-management") version "1.1.7"
}

java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(25)
    }
}

dependencies {
    implementation("org.springframework.boot:spring-boot-starter-webmvc")
    implementation("org.springframework.boot:spring-boot-starter-data-jpa")
    implementation("org.springframework.boot:spring-boot-starter-validation")
    implementation("org.springframework.boot:spring-boot-starter-security")
    implementation("org.springframework.boot:spring-boot-starter-actuator")
    // Spring Boot 4 moved Flyway's auto-configuration into its own module: with flyway-core alone,
    // no migration runs at startup
    implementation("org.springframework.boot:spring-boot-starter-flyway")

    runtimeOnly("org.postgresql:postgresql")
    runtimeOnly("org.flywaydb:flyway-database-postgresql")

    testImplementation("org.springframework.boot:spring-boot-starter-test")
    testImplementation("org.springframework.boot:spring-boot-testcontainers")
    testImplementation("org.testcontainers:testcontainers-postgresql") // Testcontainers 2 artifact names
    testImplementation("org.testcontainers:testcontainers-junit-jupiter")
}

tasks.withType<Test> {
    useJUnitPlatform() // virtual threads are final since JDK 21: no --enable-preview
}
```

### Dependency Management
Version catalogs (Gradle 7.4+) — single source of truth for versions:

```toml
# gradle/libs.versions.toml
[versions]
spring-boot = "4.1.1"
testcontainers = "2.0.5"

[libraries]
spring-boot-webmvc = { module = "org.springframework.boot:spring-boot-starter-webmvc", version.ref = "spring-boot" }
testcontainers-postgresql = { module = "org.testcontainers:testcontainers-postgresql", version.ref = "testcontainers" }
```

```kotlin
// Usage in build.gradle.kts
dependencies {
    implementation(libs.spring.boot.webmvc)
    testImplementation(libs.testcontainers.postgresql)
}
```

---

## Rules
- `final` on all fields that don't change after construction
- Streams over imperative loops for collection transformations
- `@Transactional` at service layer, not repository layer
- Flyway for DB migrations
- Never use `System.out.println` — use SLF4J logger
- Checked exceptions only at system boundaries (I/O, external calls)
- Domain layer: unchecked `RuntimeException` subclasses
- Never swallow exceptions — log + rethrow or convert
