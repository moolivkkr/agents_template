> **Foundation:** This file extends [shared-backend-patterns.md](../core/shared-backend-patterns.md) with language-specific implementations. Read the shared patterns first for language-agnostic contracts.

# Java Patterns (Spring Boot)

## Project Structure
```
src/main/java/com/company/app/
  domain/          # entities, value objects, domain services
  application/     # use cases, application services
  infrastructure/  # repositories impl, external adapters
  api/             # controllers, DTOs, mappers
  config/          # Spring configuration classes
src/test/java/ (unit/, integration/)
```

## Core Conventions
- Constructor injection always (not `@Autowired` on fields)
- Records for immutable DTOs (no Lombok needed)
- Never return `null` — use `Optional<T>` with `.orElseThrow()` or `.orElse()`
- Don't use `Optional` as method parameter — use overloads

```java
@Service
public class UserService {
    private final UserRepository repo;
    public UserService(UserRepository repo) { this.repo = repo; } // single constructor, @Autowired implicit
}

public record CreateUserRequest(@NotBlank String email, @Size(min = 8) String password) {}
```

## Spring Boot Patterns

```java
// Service layer
@Service
@Transactional(readOnly = true)
public class OrderService {
    private final OrderRepository orderRepo;
    private final EventPublisher eventPublisher;
    public OrderService(OrderRepository orderRepo, EventPublisher eventPublisher) { ... }

    @Transactional // read-write override
    public Order createOrder(UUID tenantId, CreateOrderRequest request) {
        var order = Order.create(tenantId, request);
        order = orderRepo.save(order);
        eventPublisher.publish(new OrderCreatedEvent(order));
        return order;
    }
}

// Repository
@Repository
public interface OrderRepository extends JpaRepository<Order, UUID> {
    Optional<Order> findByTenantIdAndIdAndDeletedAtIsNull(UUID tenantId, UUID id);

    @Query("""
        SELECT o FROM Order o WHERE o.tenantId = :tenantId AND o.status IN :statuses AND o.deletedAt IS NULL
        ORDER BY o.createdAt DESC""")
    List<Order> findByStatuses(@Param("tenantId") UUID tenantId, @Param("statuses") Set<OrderStatus> statuses, Pageable pageable);

    @Modifying
    @Query("UPDATE Order o SET o.deletedAt = CURRENT_TIMESTAMP WHERE o.tenantId = :tenantId AND o.id = :id")
    int softDelete(@Param("tenantId") UUID tenantId, @Param("id") UUID id);
}

// Controller
@RestController @RequestMapping("/api/v1/orders")
public class OrderController {
    private final OrderService orderService;
    @PostMapping @ResponseStatus(HttpStatus.CREATED)
    public ApiResponse<OrderResponse> createOrder(@AuthenticationPrincipal TenantContext tenant, @Valid @RequestBody CreateOrderRequest request) {
        return ApiResponse.success(OrderMapper.toResponse(orderService.createOrder(tenant.getTenantId(), request)));
    }
}
```

### Config & Profiles
```java
// Type-safe config
@ConfigurationProperties(prefix = "app")
public record AppProperties(String name, Duration requestTimeout, int maxRetries, TenantDefaults tenantDefaults) {
    public record TenantDefaults(int maxUsers, long storageLimitBytes) {}
}
```

### @Transactional Rules
- Service layer owns transactions — not repository, not controller
- Class-level `@Transactional(readOnly = true)`, method-level `@Transactional` for writes
- Never on `@Controller` or private methods (proxy can't intercept)
- Self-invocation bypasses proxy — use separate beans

## Multi-Tenancy

```java
// Hibernate filter
@Entity @Table(name = "orders")
@FilterDef(name = "tenantFilter", parameters = @ParamDef(name = "tenantId", type = UUID.class))
@Filter(name = "tenantFilter", condition = "tenant_id = :tenantId")
@Where(clause = "deleted_at IS NULL")
public class Order {
    @Id private UUID id;
    @Column(name = "tenant_id", nullable = false) private UUID tenantId;
    @Version private Integer version; // optimistic locking
}

// ThreadLocal tenant context
public class TenantContext {
    private static final ThreadLocal<UUID> CURRENT_TENANT = new ThreadLocal<>();
    public static void setCurrentTenantId(UUID id) { CURRENT_TENANT.set(id); }
    public static UUID getCurrentTenantId() {
        UUID id = CURRENT_TENANT.get();
        if (id == null) throw new IllegalStateException("No tenant context");
        return id;
    }
    public static void clear() { CURRENT_TENANT.remove(); } // CRITICAL: prevent memory leaks
}

// Tenant filter
@Component @Order(Ordered.HIGHEST_PRECEDENCE)
public class TenantFilter extends OncePerRequestFilter {
    protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res, FilterChain chain) throws ... {
        try {
            String tenantHeader = req.getHeader("X-Tenant-ID");
            if (tenantHeader == null) { res.sendError(401, "Missing tenant"); return; }
            TenantContext.setCurrentTenantId(UUID.fromString(tenantHeader));
            MDC.put("tenant_id", tenantHeader);
            chain.doFilter(req, res);
        } finally { TenantContext.clear(); MDC.remove("tenant_id"); }
    }
}
```

## Error Handling

```java
// Exception hierarchy
public abstract class AppException extends RuntimeException {
    private final String code; private final int statusCode;
    protected AppException(String code, String message, int statusCode) { super(message); this.code = code; this.statusCode = statusCode; }
    protected AppException(String code, String message, int statusCode, Throwable cause) { super(message, cause); this.code = code; this.statusCode = statusCode; }
    public String getCode() { return code; } public int getStatusCode() { return statusCode; }
}

public class ValidationException extends AppException {
    private final List<FieldError> fields;
    public ValidationException(List<FieldError> fields) { super("VALIDATION_ERROR", "Validation failed", 400); this.fields = fields; }
}
public class NotFoundException extends AppException { public NotFoundException(String resource, String id) { super("NOT_FOUND", resource + " " + id + " not found", 404); } }
public class ConflictException extends AppException { public ConflictException(String msg) { super("CONFLICT", msg, 409); } }
public class UnauthorizedException extends AppException { public UnauthorizedException() { super("UNAUTHORIZED", "Authentication required", 401); } }
public class ForbiddenException extends AppException { public ForbiddenException(String action) { super("FORBIDDEN", "Not allowed: " + action, 403); } }
public class RateLimitException extends AppException { private final int retryAfter; public RateLimitException(int s) { super("RATE_LIMITED", "Rate limit exceeded", 429); this.retryAfter = s; } }
public class UpstreamException extends AppException { public UpstreamException(String service, Throwable cause) { super("UPSTREAM_ERROR", "Upstream " + service + " failed", 502, cause); } }

// @ControllerAdvice
@ControllerAdvice
public class GlobalExceptionHandler {
    @ExceptionHandler(AppException.class)
    public ResponseEntity<ErrorResponse> handleAppException(AppException ex) {
        return ResponseEntity.status(ex.getStatusCode()).body(ErrorResponse.of(ex.getCode(), ex.getMessage()));
    }
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ErrorResponse> handleValidation(MethodArgumentNotValidException ex) {
        var details = ex.getBindingResult().getFieldErrors().stream().map(e -> new FieldError(e.getField(), e.getDefaultMessage())).toList();
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(ErrorResponse.validation(details));
    }
    @ExceptionHandler(Exception.class)
    public ResponseEntity<ErrorResponse> handleUnexpected(Exception ex) {
        log.error("unhandled_error", ex);
        return ResponseEntity.status(500).body(ErrorResponse.of("INTERNAL_ERROR", "Something went wrong"));
    }
}
```

## Repository Patterns

```java
// Specifications for dynamic queries
public class OrderSpecifications {
    public static Specification<Order> belongsToTenant(UUID tenantId) { return (root, q, cb) -> cb.equal(root.get("tenantId"), tenantId); }
    public static Specification<Order> isNotDeleted() { return (root, q, cb) -> cb.isNull(root.get("deletedAt")); }
    public static Specification<Order> hasStatus(OrderStatus status) { return (root, q, cb) -> cb.equal(root.get("status"), status); }
}
// Compose: Specification.where(belongsToTenant(id)).and(isNotDeleted()).and(hasStatus(PENDING))

// Projections
public interface OrderSummary { UUID getId(); OrderStatus getStatus(); BigDecimal getTotal(); }
public record OrderStats(OrderStatus status, long count, BigDecimal totalAmount) {}
```

## Testing

```java
// Unit tests with Mockito
@ExtendWith(MockitoExtension.class)
class OrderServiceTest {
    @Mock private OrderRepository orderRepo;
    @InjectMocks private OrderService orderService;

    @Test void createOrder_validRequest_returnsOrder() {
        when(orderRepo.save(any())).thenAnswer(inv -> inv.getArgument(0));
        var order = orderService.createOrder(TENANT_ID, request);
        assertThat(order.getStatus()).isEqualTo(OrderStatus.PENDING);
        verify(eventPublisher).publish(any(OrderCreatedEvent.class));
    }
}

// Parameterized tests
@ParameterizedTest @CsvSource({"valid@email.com, true", "not-email, false"})
void testEmailValidation(String email, boolean expected) { assertEquals(expected, EmailValidator.isValid(email)); }

@ParameterizedTest @MethodSource("orderStatusTransitions")
void testValidStatusTransition(OrderStatus from, OrderStatus to, boolean valid) { assertEquals(valid, Order.isValidTransition(from, to)); }

// Testcontainers
@Testcontainers @SpringBootTest
class IntegrationTestBase {
    @Container static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16-alpine");
    @DynamicPropertySource
    static void configureProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", postgres::getJdbcUrl);
        registry.add("spring.datasource.username", postgres::getUsername);
        registry.add("spring.datasource.password", postgres::getPassword);
    }
}

// AssertJ
assertThat(order).extracting(Order::getStatus, Order::getTenantId).containsExactly(OrderStatus.PENDING, TENANT_ID);
assertThatThrownBy(() -> service.process(invalid)).isInstanceOf(ValidationException.class).hasMessageContaining("amount");
```

## Performance

```yaml
# HikariCP
spring.datasource.hikari:
  minimum-idle: 5
  maximum-pool-size: 20  # (cores * 2) + spindle_count
  leak-detection-threshold: 60000
```

```java
// @Cacheable with Redis
@Cacheable(value = "users", key = "#tenantId + ':' + #userId")
public UserResponse getUser(UUID tenantId, UUID userId) { ... }
@CacheEvict(value = "users", key = "#tenantId + ':' + #userId")
@Transactional
public UserResponse updateUser(UUID tenantId, UUID userId, UpdateUserRequest request) { ... }

// Virtual Threads (Java 21+): spring.threads.virtual.enabled=true
// Prefer Spring MVC + virtual threads over WebFlux for most CRUD services
// Use WebFlux only for streaming (SSE, WebSocket) or 10K+ concurrent connections
// Avoid synchronized blocks with virtual threads — use ReentrantLock
```

## Build (Gradle Kotlin DSL)

```kotlin
plugins {
    java
    id("org.springframework.boot") version "3.3.0"
    id("io.spring.dependency-management") version "1.1.5"
}
java { toolchain { languageVersion = JavaLanguageVersion.of(21) } }
dependencies {
    implementation("org.springframework.boot:spring-boot-starter-web")
    implementation("org.springframework.boot:spring-boot-starter-data-jpa")
    implementation("org.springframework.boot:spring-boot-starter-validation")
    runtimeOnly("org.postgresql:postgresql")
    testImplementation("org.springframework.boot:spring-boot-starter-test")
    testImplementation("org.testcontainers:postgresql")
}
```
- Gradle for new projects (faster, build cache), Maven fine for existing
- Version catalogs (`gradle/libs.versions.toml`) for dependency versions

## Rules
- `final` on all fields that don't change after construction
- Streams over imperative loops for collection transformations
- Flyway for DB migrations
- Never `System.out.println` — use SLF4J
- Domain layer: unchecked `RuntimeException` subclasses
- Checked exceptions only at system boundaries
