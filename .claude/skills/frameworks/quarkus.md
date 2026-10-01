# Quarkus framework patterns for Java cloud-native APIs.

> Java samples compile-checked 2026-09-30: JDK 25.0.4.1, Quarkus 3.40.1, Maven 3.9.16 (`tests/archetype-compile/java/run.sh`). The exception mappers were also run in a Quarkus app (`@QuarkusTest`): application errors, crashes, unknown routes, wrong methods and unreadable bodies all come back in the error envelope with their own status.

## Project Structure
```text
src/main/java/com/example/app/
├── App.java                          # No main class needed — Quarkus manages lifecycle
├── config/
│   └── AppConfig.java                # @ConfigMapping interfaces
├── resource/                         # JAX-RS endpoints (REST layer)
│   └── WidgetResource.java
├── service/
│   ├── WidgetService.java            # Interface
│   └── WidgetServiceImpl.java        # @ApplicationScoped implementation
├── repository/
│   └── WidgetRepository.java         # Panache repository or raw Hibernate
├── model/
│   ├── entity/
│   │   └── Widget.java               # @Entity JPA class
│   └── dto/
│       ├── CreateWidgetRequest.java   # Java record
│       └── WidgetResponse.java        # Java record
├── exception/
│   ├── AppException.java
│   └── AppExceptionMapper.java       # @Provider ExceptionMapper
└── security/
    └── TenantFilter.java             # @Provider ContainerRequestFilter
```
- Quarkus uses CDI for dependency injection — no `@SpringBootApplication` needed
- Resources (JAX-RS) are the HTTP layer — equivalent to Spring `@RestController`
- Services are `@ApplicationScoped` beans — equivalent to Spring `@Service`

## CDI (Context and Dependency Injection)
```java
// Constructor injection via @Inject — the preferred form
@ApplicationScoped
public class WidgetServiceImpl implements WidgetService {

    private final WidgetRepository repository;
    private final CacheManager cacheManager;

    @Inject
    public WidgetServiceImpl(WidgetRepository repository, CacheManager cacheManager) {
        this.repository = repository;
        this.cacheManager = cacheManager;
    }
}

// Alternative: field injection (acceptable in Quarkus due to Arc CDI optimizations)
@ApplicationScoped
public class WidgetServiceImpl implements WidgetService {
    @Inject
    WidgetRepository repository;

    @Inject
    CacheManager cacheManager;
}
```
- `@ApplicationScoped` = singleton (one instance per application) — most common
- `@RequestScoped` = one instance per HTTP request — use for request-scoped state
- `@Dependent` = new instance per injection point — use for stateless helpers
- Quarkus CDI (Arc) is build-time optimized — no runtime reflection overhead
- Constructor injection is preferred for testability, but field injection is acceptable

## CDI vs Spring DI — Key Differences

| Concept | Spring | Quarkus (CDI) |
|---------|--------|---------------|
| Singleton bean | `@Service`, `@Component` | `@ApplicationScoped` |
| Per-request bean | `@RequestScope` | `@RequestScoped` |
| Auto-detection | Component scanning | Build-time bean discovery |
| Conditional bean | `@ConditionalOnProperty` | `@IfBuildProfile("dev")` |
| Event publishing | `ApplicationEventPublisher` | `Event<T>` + `@Observes` |
| Configuration | `@ConfigurationProperties` | `@ConfigMapping` |

## RESTEasy (JAX-RS Endpoints)
```java
@Path("/api/v1/widgets")
@Produces(MediaType.APPLICATION_JSON)
@Consumes(MediaType.APPLICATION_JSON)
@ApplicationScoped
public class WidgetResource {

    private static final Set<String> SORTABLE = Set.of("createdAt", "name"); // never a raw client string in a query
    private final WidgetService service;

    @Inject
    public WidgetResource(WidgetService service) {
        this.service = service;
    }

    @POST
    public Response create(@Valid CreateWidgetRequest request, @Context SecurityContext ctx) {
        var tenantId = TenantContext.getTenantId(ctx);
        var widget = service.create(tenantId, request);
        return Response.status(Response.Status.CREATED)
                .entity(new Envelope<>(widget, newMeta()))
                .build();
    }

    @GET
    @Path("/{id}")
    public Response get(@PathParam("id") UUID id, @Context SecurityContext ctx) {
        var tenantId = TenantContext.getTenantId(ctx);
        var widget = service.get(tenantId, id);
        return Response.ok(new Envelope<>(widget, newMeta())).build();
    }

    @GET
    public Response list(
            @QueryParam("cursor") String cursor,
            @QueryParam("limit") @DefaultValue("20") int limit,
            @QueryParam("sort_by") @DefaultValue("createdAt") String sortBy,
            @Context SecurityContext ctx) {
        // 1..100, else 400 VALIDATION_FAILED with details[] for limit — never clamped silently
        if (limit < 1 || limit > 100) {
            throw new ValidationException("limit", "out_of_range", "Limit must be a whole number from 1 to 100.");
        }
        var tenantId = TenantContext.getTenantId(ctx);
        var result = service.list(tenantId, cursor, limit, SORTABLE.contains(sortBy) ? sortBy : "createdAt");
        return Response.ok(new ListEnvelope<>(result)).build();
    }

    @PUT
    @Path("/{id}")
    public Response update(@PathParam("id") UUID id, @Valid UpdateWidgetRequest request,
                           @Context SecurityContext ctx) {
        var tenantId = TenantContext.getTenantId(ctx);
        var widget = service.update(tenantId, id, request);
        return Response.ok(new Envelope<>(widget, newMeta())).build();
    }

    @DELETE
    @Path("/{id}")
    public Response delete(@PathParam("id") UUID id, @Context SecurityContext ctx) {
        var tenantId = TenantContext.getTenantId(ctx);
        service.delete(tenantId, id);
        return Response.noContent().build();
    }
}
```
- `@Path`, `@GET`, `@POST`, `@PUT`, `@DELETE` — JAX-RS annotations (not Spring's `@GetMapping`)
- `@Valid` triggers Bean Validation on the request body
- `@Context SecurityContext` for auth context — injected by the container
- `@PathParam`, `@QueryParam`, `@DefaultValue` for path/query parameters

## JAX-RS vs Spring Annotations

| Spring | JAX-RS (Quarkus) |
|--------|------------------|
| `@RestController` | `@Path` + `@Produces` + `@Consumes` |
| `@GetMapping("/path")` | `@GET` + `@Path("/path")` |
| `@RequestBody` | method parameter (auto-bound) |
| `@PathVariable` | `@PathParam` |
| `@RequestParam` | `@QueryParam` |
| `ResponseEntity<T>` | `Response` (JAX-RS) |
| `@ControllerAdvice` | `@Provider` + `ExceptionMapper<T>` |

## Hibernate Reactive (vs Spring Data JPA)
```java
// Panache Active Record pattern (simpler for CRUD)
@Entity
@Table(name = "widgets")
public class Widget extends PanacheEntityBase {
    @Id
    @GeneratedValue
    public UUID id;

    @Column(name = "tenant_id", nullable = false)
    public UUID tenantId;

    @Column(nullable = false)
    public String name;

    @Column(name = "deleted_at")
    public Instant deletedAt; // soft delete: every query below filters on it

    // Panache provides find, persist, delete out of the box
    public static List<Widget> findByTenant(UUID tenantId) {
        return find("tenantId = ?1 and deletedAt is null", tenantId).list();
    }
}

// Panache Repository pattern (better separation)
@ApplicationScoped
public class WidgetRepository implements PanacheRepositoryBase<Widget, UUID> {

    public List<Widget> findByTenant(UUID tenantId) {
        return find("tenantId = ?1 and deletedAt is null", tenantId).list();
    }

    public Optional<Widget> findByTenantAndId(UUID tenantId, UUID id) {
        return find("tenantId = ?1 and id = ?2 and deletedAt is null", tenantId, id)
                .firstResultOptional();
    }
}

// Hibernate Reactive (non-blocking — for reactive endpoints)
@ApplicationScoped
public class ReactiveWidgetRepository {
    @Inject
    Mutiny.SessionFactory sessionFactory;

    public Uni<Widget> findById(UUID tenantId, UUID id) {
        return sessionFactory.withSession(session ->
            session.createQuery("FROM Widget w WHERE w.tenantId = :tid AND w.id = :id", Widget.class)
                .setParameter("tid", tenantId)
                .setParameter("id", id)
                .getSingleResultOrNull()
        );
    }
}
```
- Panache simplifies JPA — less boilerplate than Spring Data
- Active Record pattern: entity methods (simpler, less separation)
- Repository pattern: separate repository class (better testability)
- Hibernate Reactive uses `Uni<T>` (Mutiny) instead of `CompletableFuture`

## Native Compilation with GraalVM
```java
// Register classes for reflection (required for JSON serialization in native mode)
@RegisterForReflection
public record WidgetResponse(
    UUID id,
    String name,
    String description,
    String status,
    Instant createdAt
) {}

// Register third-party classes you serialize but can't annotate (e.g. a client library's DTOs)
@RegisterForReflection(targets = {
    PaymentProviderResponse.class,
    PaymentProviderError.class
})
public class ReflectionConfig {}
```
```properties
# application.properties — native image configuration
quarkus.native.additional-build-args=\
    --initialize-at-run-time=org.bouncycastle,\
    -H:+ReportExceptionStackTraces

# Resources to include in native image
quarkus.native.resources.includes=db/migration/*.sql,META-INF/resources/**
```
- `@RegisterForReflection` on all DTOs, records, and classes used with Jackson
- GraalVM native images have no reflection by default — register everything explicitly
- Build native: `./mvnw package -Dnative` or `./gradlew build -Dquarkus.native.enabled=true`
- Startup time: ~50ms native vs ~2s JVM — massive improvement for serverless/containers

## Dev Mode
```bash
# Live reload with dev services (auto-provisions DB, Kafka, Redis)
./mvnw quarkus:dev

# Dev mode features:
# - Hot reload on code changes (no restart needed)
# - Dev UI at http://localhost:8080/q/dev-ui
# - Automatic Testcontainers for databases (zero config)
# - Continuous testing (re-runs tests on save)
```
```properties
# application.properties — dev services
%dev.quarkus.datasource.devservices.enabled=true
%dev.quarkus.datasource.devservices.image-name=postgres:16-alpine
%dev.quarkus.datasource.devservices.port=5432

# Profile-specific config (like Spring profiles)
%dev.quarkus.log.level=DEBUG
%prod.quarkus.log.level=INFO
```
- `quarkus:dev` provides hot reload, dev UI, and auto-provisioned infrastructure
- Dev services auto-start containers for DB, Redis, Kafka — no manual Docker setup
- Profile prefixes (`%dev.`, `%prod.`, `%test.`) in properties replace Spring profile files

## Configuration
```java
// Type-safe configuration (replaces Spring @ConfigurationProperties)
@ConfigMapping(prefix = "app")
public interface AppConfig {
    String jwtSecret();
    int maxPageSize();

    @WithDefault("5m")
    Duration cacheTtl();

    Optional<String> externalApiUrl();

    DatabaseConfig database();

    interface DatabaseConfig {
        @WithDefault("50")
        int maxPoolSize();

        @WithDefault("10")
        int minPoolSize();
    }
}
```
```properties
# application.properties
app.jwt-secret=${JWT_SECRET}
app.max-page-size=100
app.cache-ttl=5m
app.database.max-pool-size=50
```
- `@ConfigMapping` provides compile-time checked, type-safe configuration
- Nested interfaces for grouped config — no flat property names
- `@WithDefault` for defaults, `Optional<T>` for optional values
- Environment variable substitution: `${ENV_VAR:default}`

## Testing
```java
// Full integration test. @TestSecurity/@JwtSecurity (quarkus-test-security-jwt) authenticate each request
// as a user whose token carries tenant_id — no hand-made token.
@QuarkusTest
@TestSecurity(user = "test-user", roles = "user")
@JwtSecurity(claims = @Claim(key = "tenant_id", value = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))
class WidgetResourceTest {

    @Test
    void createWidget_returnsCreated() {
        given()
            .contentType(ContentType.JSON)
            .body(new CreateWidgetRequest("New Widget", "Description"))
        .when()
            .post("/api/v1/widgets")
        .then()
            .statusCode(201)
            .body("data.name", equalTo("New Widget"));
    }

    @Test
    void getWidget_notFound_returns404() {
        given()
        .when()
            .get("/api/v1/widgets/" + UUID.randomUUID())
        .then()
            .statusCode(404)
            .body("error.code", equalTo("NOT_FOUND"));
    }
}

// Unit test with mocked dependencies
@QuarkusTest
class WidgetServiceTest {

    static final UUID TENANT_ID = UUID.fromString("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa");

    @InjectMock
    WidgetRepository repository;

    @Inject
    WidgetService service;

    @Test
    void create_validInput_persistsWidget() {
        // persist() is void, and a Mockito mock's void method does nothing: no stubbing needed. (The id is
        // generated by Hibernate on a real persist, so a mocked one leaves it null.)
        var result = service.create(TENANT_ID, new CreateWidgetRequest("Test", "Desc"));

        verify(repository).persist(any(Widget.class));
        assertEquals("Test", result.name);
        assertEquals(TENANT_ID, result.tenantId);
    }
}

// Test with custom profile
@QuarkusTest
@TestProfile(IntegrationTestProfile.class)
class WidgetIntegrationTest {
    // Uses test-specific configuration
}

public class IntegrationTestProfile implements QuarkusTestProfile {
    @Override
    public Map<String, String> getConfigOverrides() {
        return Map.of("app.cache-ttl", "0s");
    }
}
```
- `@QuarkusTest` starts the full application — use for integration tests
- `@InjectMock` replaces a CDI bean with a Mockito mock — cleaner than Spring `@MockBean`
- `@TestProfile` for test-specific configuration overrides
- REST-assured is the default HTTP testing library — fluent API

## Health Checks and Metrics
```java
// Custom health check (exposed at /q/health/ready)
@Readiness
@ApplicationScoped
public class DatabaseHealthCheck implements HealthCheck {

    @Inject
    DataSource dataSource;

    @Override
    public HealthCheckResponse call() {
        try (var conn = dataSource.getConnection()) {
            conn.createStatement().execute("SELECT 1");
            return HealthCheckResponse.up("database");
        } catch (Exception e) {
            return HealthCheckResponse.down("database");
        }
    }
}

// Custom metrics (Micrometer, quarkus-micrometer)
@ApplicationScoped
public class WidgetMetrics {

    @Inject
    MeterRegistry registry;

    public void recordCreate(Duration latency) {
        registry.counter("widget.operations", "op", "create").increment();
        registry.timer("widget.latency", "op", "create").record(latency);
    }
}
```
```properties
# Health and metrics endpoints
quarkus.smallrye-health.ui.enable=true
quarkus.micrometer.export.prometheus.enabled=true
# /q/health/ready — readiness probe
# /q/health/live — liveness probe
# /q/metrics — Prometheus metrics
```
- SmallRye Health implements MicroProfile Health — auto-exposed at `/q/health`
- `@Liveness` for liveness probes, `@Readiness` for readiness probes
- Micrometer for metrics — same API as Spring Boot Actuator metrics
- Prometheus endpoint at `/q/metrics` — ready for Grafana dashboards

## Exception Mapping
```java
// The one error envelope (api/response-envelope.md): {"error": {code, message, details?, request_id, retryable}}
final class ErrorEnvelope {
    static Response of(int status, String code, String message, List<?> details) {
        var error = new LinkedHashMap<String, Object>();
        error.put("code", code);
        error.put("message", message);                 // user-safe catalog text, never an exception's message
        if (!details.isEmpty()) {
            error.put("details", details);             // VALIDATION_FAILED: [{field, code, message}]
        }
        error.put("request_id", Objects.toString(MDC.get("request_id"), null)); // set by the request-id filter
        error.put("retryable", status == 429 || status == 503);
        return Response.status(status).entity(Map.of("error", error)).build();
    }

    static String codeFor(int status) {
        return switch (status) {
            case 400 -> "MALFORMED_REQUEST";
            case 401 -> "UNAUTHENTICATED";
            case 403 -> "FORBIDDEN";
            case 404 -> "NOT_FOUND";
            case 409 -> "CONFLICT";
            case 422 -> "BUSINESS_RULE_VIOLATION";
            case 429 -> "RATE_LIMITED";
            case 503 -> "UNAVAILABLE";
            default -> status >= 500 ? "INTERNAL" : "MALFORMED_REQUEST";
        };
    }
}

// AppException carries the envelope's code, its HTTP status and a user-safe message
@Provider
public class AppExceptionMapper implements ExceptionMapper<AppException> {

    @Override
    public Response toResponse(AppException exc) {
        if (exc.getStatus() >= 500) {
            Log.errorf(exc, "request_failed code=%s", exc.getCode()); // the cause goes to the log only
            return ErrorEnvelope.of(exc.getStatus(), "INTERNAL", "Something went wrong.", List.of());
        }
        return ErrorEnvelope.of(exc.getStatus(), exc.getCode(), exc.getUserMessage(), exc.getDetails());
    }
}

// Framework errors (unknown route, wrong method, unreadable body) keep their status in the envelope
@Provider
public class WebApplicationExceptionMapper implements ExceptionMapper<WebApplicationException> {

    @Override
    public Response toResponse(WebApplicationException exc) {
        int status = exc.getResponse().getStatus();
        var code = ErrorEnvelope.codeFor(status);
        var message = switch (code) {
            case "NOT_FOUND" -> "Not found.";
            case "UNAUTHENTICATED" -> "Sign in to continue.";
            case "FORBIDDEN" -> "You don't have permission to do this.";
            case "INTERNAL" -> "Something went wrong.";
            default -> "The request could not be read.";
        };
        return ErrorEnvelope.of(status, code, message, List.of());
    }
}

// Catch-all for unexpected exceptions
@Provider
public class GenericExceptionMapper implements ExceptionMapper<Exception> {

    @Override
    public Response toResponse(Exception exc) {
        Log.error("Unhandled exception", exc);
        return ErrorEnvelope.of(500, "INTERNAL", "Something went wrong.", List.of());
    }
}
```
- `@Provider` + `ExceptionMapper<T>` replaces Spring's `@ControllerAdvice`
- Register one mapper per exception type — Quarkus picks the most specific. Map `WebApplicationException` too:
  without it, the catch-all `ExceptionMapper<Exception>` also turns an unknown route (404) or a wrong method
  (405) into a 500
- Every error body is the envelope above; never expose an exception's message or internals

## Rules
- CDI `@ApplicationScoped` for services — constructor or field injection both acceptable
- JAX-RS annotations for endpoints — not Spring annotations
- `@RegisterForReflection` on all DTOs when targeting GraalVM native
- Dev services for local development — no manual Docker for databases
- `@ConfigMapping` for type-safe configuration — no `@Value` string injection
- `@QuarkusTest` + `@InjectMock` for testing — cleaner than Spring Boot testing
- Panache Repository pattern for data access — better separation than Active Record
- SmallRye Health for health checks — auto-exposed, Kubernetes-ready
- Profiles via `%dev.`, `%prod.`, `%test.` prefixes in properties
- `@Valid` on resource method parameters for Bean Validation — same as Spring

> Config blocks checked 2026-09-30 (`bash tests/archetype-compile/config-packs/run.sh --live`): 1 bash block: bash -n (macOS bash 3.2.57) + shellcheck 0.11.0.
