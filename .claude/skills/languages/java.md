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
@RequiredArgsConstructor
public class OrderController {
    private final OrderService orderService;

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public ApiResponse<OrderResponse> createOrder(
        @AuthenticationPrincipal TenantContext tenant,
        @Valid @RequestBody CreateOrderRequest request
    ) {
        var order = orderService.createOrder(tenant.getTenantId(), request);
        return ApiResponse.success(OrderMapper.toResponse(order));
    }
}
```

### Profiles and Configuration
```java
// application.yml — base config
spring:
  profiles:
    active: ${SPRING_PROFILES_ACTIVE:local}

// application-local.yml — dev overrides
spring:
  datasource:
    url: jdbc:postgresql://localhost:5432/myapp
  jpa:
    show-sql: true

// application-prod.yml — production
spring:
  datasource:
    url: ${DATABASE_URL}
  jpa:
    show-sql: false

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

    @Transactional // method-level: read-write
    public Payment processPayment(UUID tenantId, PaymentRequest request) {
        // Entire method runs in a single transaction
        var payment = Payment.create(tenantId, request);
        payment = paymentRepo.save(payment);
        ledgerService.recordEntry(tenantId, payment); // same transaction
        return payment;
    }

    // readOnly = true: Hibernate uses read-only flush mode, DB may use read replica
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
@Where(clause = "deleted_at IS NULL") // soft delete filter
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

// Enable filter per request via interceptor
@Component
public class TenantFilterInterceptor implements HandlerInterceptor {
    private final EntityManager entityManager;

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) {
        UUID tenantId = TenantContext.getCurrentTenantId();
        Session session = entityManager.unwrap(Session.class);
        session.enableFilter("tenantFilter").setParameter("tenantId", tenantId);
        return true;
    }
}
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

// Filter sets and clears tenant context
@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class TenantFilter extends OncePerRequestFilter {
    @Override
    protected void doFilterInternal(
        HttpServletRequest request, HttpServletResponse response, FilterChain chain
    ) throws ServletException, IOException {
        try {
            String tenantHeader = request.getHeader("X-Tenant-ID");
            if (tenantHeader == null) {
                response.sendError(401, "Missing tenant context");
                return;
            }
            TenantContext.setCurrentTenantId(UUID.fromString(tenantHeader));
            MDC.put("tenant_id", tenantHeader); // structured logging
            chain.doFilter(request, response);
        } finally {
            TenantContext.clear();
            MDC.remove("tenant_id");
        }
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
        return http
            .addFilterBefore(tenantFilter, UsernamePasswordAuthenticationFilter.class)
            .oauth2ResourceServer(oauth2 -> oauth2
                .jwt(jwt -> jwt.jwtAuthenticationConverter(tenantJwtConverter()))
            )
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/api/v1/health").permitAll()
                .requestMatchers("/api/v1/**").authenticated()
            )
            .build();
    }

    private JwtAuthenticationConverter tenantJwtConverter() {
        var converter = new JwtAuthenticationConverter();
        converter.setJwtGrantedAuthoritiesConverter(jwt -> {
            // Extract tenant_id from JWT claims and set context
            String tenantId = jwt.getClaimAsString("tenant_id");
            TenantContext.setCurrentTenantId(UUID.fromString(tenantId));
            // Extract roles/permissions
            return extractAuthorities(jwt);
        });
        return converter;
    }
}
```

---

## Error Handling

### @ControllerAdvice with @ExceptionHandler
```java
@ControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    @ExceptionHandler(AppException.class)
    public ResponseEntity<ErrorResponse> handleAppException(AppException ex) {
        log.warn("app_error: code={}, message={}", ex.getCode(), ex.getMessage());
        return ResponseEntity
            .status(ex.getStatusCode())
            .body(ErrorResponse.of(ex.getCode(), ex.getMessage()));
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ErrorResponse> handleValidation(MethodArgumentNotValidException ex) {
        var details = ex.getBindingResult().getFieldErrors().stream()
            .map(e -> new FieldError(e.getField(), e.getDefaultMessage()))
            .toList();
        return ResponseEntity
            .status(HttpStatus.BAD_REQUEST)
            .body(ErrorResponse.validation(details));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ErrorResponse> handleUnexpected(Exception ex) {
        log.error("unhandled_error", ex);
        return ResponseEntity
            .status(HttpStatus.INTERNAL_SERVER_ERROR)
            .body(ErrorResponse.of("INTERNAL_ERROR", "Something went wrong"));
    }
}
```

### Custom Exception Hierarchy
```java
// Base exception
public abstract class AppException extends RuntimeException {
    private final String code;
    private final int statusCode;

    protected AppException(String code, String message, int statusCode) {
        super(message);
        this.code = code;
        this.statusCode = statusCode;
    }

    protected AppException(String code, String message, int statusCode, Throwable cause) {
        super(message, cause);
        this.code = code;
        this.statusCode = statusCode;
    }

    public String getCode() { return code; }
    public int getStatusCode() { return statusCode; }
}

// 8 domain error types matching the shared contract
public class ValidationException extends AppException {
    private final List<FieldError> fields;
    public ValidationException(List<FieldError> fields) {
        super("VALIDATION_ERROR", "Validation failed", 400);
        this.fields = fields;
    }
    public List<FieldError> getFields() { return fields; }
}

public class NotFoundException extends AppException {
    public NotFoundException(String resource, String id) {
        super("NOT_FOUND", resource + " " + id + " not found", 404);
    }
}

public class ConflictException extends AppException {
    public ConflictException(String message) {
        super("CONFLICT", message, 409);
    }
}

public class UnauthorizedException extends AppException {
    public UnauthorizedException() {
        super("UNAUTHORIZED", "Authentication required", 401);
    }
}

public class ForbiddenException extends AppException {
    public ForbiddenException(String action) {
        super("FORBIDDEN", "Not allowed to perform: " + action, 403);
    }
}

public class RateLimitException extends AppException {
    private final int retryAfter;
    public RateLimitException(int retryAfterSeconds) {
        super("RATE_LIMITED", "Rate limit exceeded", 429);
        this.retryAfter = retryAfterSeconds;
    }
    public int getRetryAfter() { return retryAfter; }
}

public class UpstreamException extends AppException {
    public UpstreamException(String service, Throwable cause) {
        super("UPSTREAM_ERROR", "Upstream service " + service + " failed", 502, cause);
    }
}

public class InternalException extends AppException {
    public InternalException(String detail, Throwable cause) {
        super("INTERNAL_ERROR", detail, 500, cause);
    }
}
```

### ProblemDetail (RFC 7807) — Spring 6+
```java
@ControllerAdvice
public class ProblemDetailExceptionHandler extends ResponseEntityExceptionHandler {

    @ExceptionHandler(NotFoundException.class)
    public ProblemDetail handleNotFound(NotFoundException ex) {
        ProblemDetail detail = ProblemDetail.forStatusAndDetail(
            HttpStatus.NOT_FOUND, ex.getMessage()
        );
        detail.setType(URI.create("https://api.myapp.com/errors/not-found"));
        detail.setTitle("Resource Not Found");
        detail.setProperty("code", ex.getCode());
        return detail;
    }
}
// Response:
// {
//   "type": "https://api.myapp.com/errors/not-found",
//   "title": "Resource Not Found",
//   "status": 404,
//   "detail": "Order abc123 not found",
//   "code": "NOT_FOUND"
// }
```

---

## Repository Pattern

### Spring Data JPA Repositories
```java
public interface OrderRepository extends JpaRepository<Order, UUID> {

    // Derived query methods — Spring generates SQL from method name
    Optional<Order> findByTenantIdAndIdAndDeletedAtIsNull(UUID tenantId, UUID id);

    List<Order> findByTenantIdAndStatusAndDeletedAtIsNull(
        UUID tenantId, OrderStatus status, Pageable pageable
    );

    // JPQL for complex queries
    @Query("""
        SELECT o FROM Order o
        WHERE o.tenantId = :tenantId
          AND o.status IN :statuses
          AND o.deletedAt IS NULL
        ORDER BY o.createdAt DESC
        """)
    List<Order> findByStatuses(
        @Param("tenantId") UUID tenantId,
        @Param("statuses") Set<OrderStatus> statuses,
        Pageable pageable
    );

    // Native query for performance-critical operations
    @Query(value = """
        SELECT o.* FROM orders o
        WHERE o.tenant_id = :tenantId
          AND o.created_at < :cursor
          AND o.deleted_at IS NULL
        ORDER BY o.created_at DESC
        LIMIT :limit
        """, nativeQuery = true)
    List<Order> findWithCursor(
        @Param("tenantId") UUID tenantId,
        @Param("cursor") Instant cursor,
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

// Usage — compose specifications dynamically
Specification<Order> spec = Specification
    .where(belongsToTenant(tenantId))
    .and(isNotDeleted())
    .and(hasStatus(PENDING))
    .and(createdBetween(startDate, endDate));

List<Order> orders = orderRepo.findAll(spec, PageRequest.of(0, 20));
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

// Repository returns projection
List<OrderSummary> findByTenantIdAndDeletedAtIsNull(UUID tenantId, Pageable pageable);

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
            .extracting(e -> ((ValidationException) e).getFields())
            .asList()
            .hasSize(1);
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
// Slim test — only loads JPA layer
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

        var results = orderRepo.findByTenantIdAndDeletedAtIsNull(tenantId);

        assertThat(results).containsExactly(active);
        assertThat(results).doesNotContain(deleted);
    }
}

// Full integration test — loads entire context
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class OrderApiIntegrationTest {

    @Autowired private TestRestTemplate restTemplate;

    @Test
    void createOrder_returns201() {
        var request = new CreateOrderRequest(List.of(new LineItem("SKU-001", 1, BigDecimal.TEN)));
        var headers = new HttpHeaders();
        headers.set("X-Tenant-ID", TENANT_ID.toString());

        var response = restTemplate.exchange(
            "/api/v1/orders", HttpMethod.POST,
            new HttpEntity<>(request, headers), ApiResponse.class
        );

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.CREATED);
    }
}
```

### Testcontainers
```java
@Testcontainers
@SpringBootTest
class IntegrationTestBase {

    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16-alpine")
        .withDatabaseName("testdb")
        .withUsername("test")
        .withPassword("test");

    @DynamicPropertySource
    static void configureProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", postgres::getJdbcUrl);
        registry.add("spring.datasource.username", postgres::getUsername);
        registry.add("spring.datasource.password", postgres::getPassword);
    }
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

// Exception assertions
assertThatThrownBy(() -> service.processPayment(TENANT_ID, invalidRequest))
    .isInstanceOf(ValidationException.class)
    .hasMessageContaining("amount")
    .extracting("code")
    .isEqualTo("VALIDATION_ERROR");
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

// Cache config with Redis
@Configuration
@EnableCaching
public class CacheConfig {
    @Bean
    public RedisCacheConfiguration cacheConfiguration() {
        return RedisCacheConfiguration.defaultCacheConfig()
            .entryTtl(Duration.ofMinutes(10))
            .serializeValuesWith(
                SerializationPair.fromSerializer(new GenericJackson2JsonRedisSerializer())
            );
    }
}
```

### Virtual Threads (Java 21+)
```java
// Enable virtual threads in Spring Boot 3.2+
spring:
  threads:
    virtual:
      enabled: true

// Or configure manually
@Bean
public TomcatProtocolHandlerCustomizer<?> protocolHandlerVirtualThreadExecutorCustomizer() {
    return handler -> handler.setExecutor(Executors.newVirtualThreadPerTaskExecutor());
}

// Virtual threads are ideal for I/O-bound workloads (HTTP calls, DB queries)
// No need for reactive (WebFlux) for most services — virtual threads handle blocking I/O efficiently
// CAUTION: avoid synchronized blocks with virtual threads — use ReentrantLock instead
// CAUTION: ThreadLocal may pin virtual threads — use ScopedValues (Java 21 preview) where possible
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
    @GetMapping(value = "/stream/orders", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<OrderEvent> streamOrders(@RequestParam UUID tenantId) {
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
    id("org.springframework.boot") version "3.3.0"
    id("io.spring.dependency-management") version "1.1.5"
}

java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(21)
    }
}

dependencies {
    implementation("org.springframework.boot:spring-boot-starter-web")
    implementation("org.springframework.boot:spring-boot-starter-data-jpa")
    implementation("org.springframework.boot:spring-boot-starter-validation")
    implementation("org.springframework.boot:spring-boot-starter-security")
    implementation("org.springframework.boot:spring-boot-starter-actuator")

    runtimeOnly("org.postgresql:postgresql")
    runtimeOnly("org.flywaydb:flyway-core")

    testImplementation("org.springframework.boot:spring-boot-starter-test")
    testImplementation("org.testcontainers:postgresql")
    testImplementation("org.testcontainers:junit-jupiter")
}

tasks.withType<Test> {
    useJUnitPlatform()
    jvmArgs("--enable-preview") // for virtual threads if needed
}
```

### Dependency Management
```kotlin
// Version catalogs (Gradle 7.4+) — single source of truth for versions
// gradle/libs.versions.toml
[versions]
spring-boot = "3.3.0"
testcontainers = "1.19.8"

[libraries]
spring-boot-web = { module = "org.springframework.boot:spring-boot-starter-web", version.ref = "spring-boot" }
testcontainers-postgres = { module = "org.testcontainers:postgresql", version.ref = "testcontainers" }

// Usage in build.gradle.kts
dependencies {
    implementation(libs.spring.boot.web)
    testImplementation(libs.testcontainers.postgres)
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
