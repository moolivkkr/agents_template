---
skill: spring-boot
description: Spring Boot framework patterns — project structure, dependency injection, configuration, exception handling, validation, security, testing conventions
version: "1.0"
tags:
  - java
  - spring-boot
  - framework
  - backend
---

# Spring Boot Framework Patterns

> Java samples compile-checked 2026-09-30: JDK 25.0.4.1, Spring Boot 4.1.1, Maven 3.9.16 (`tests/archetype-compile/java/run.sh`).

## Project Structure

```
src/main/java/com/example/app/
├── Application.java                 # @SpringBootApplication entry point
├── config/                          # @Configuration beans
│   ├── SecurityConfig.java
│   ├── CacheConfig.java
│   └── OpenApiConfig.java
├── controller/                      # @RestController — HTTP layer
│   └── WidgetController.java
├── service/                         # @Service — business logic
│   ├── WidgetService.java           # interface
│   └── WidgetServiceImpl.java       # implementation
├── repository/                      # Spring Data JPA interfaces
│   └── WidgetRepository.java
├── model/
│   ├── entity/                      # @Entity JPA classes
│   │   └── Widget.java
│   └── dto/                         # Request/response DTOs (Java records)
│       ├── CreateWidgetRequest.java
│       └── WidgetResponse.java
├── exception/                       # Custom exceptions + @ControllerAdvice
│   ├── ResourceNotFoundException.java
│   └── GlobalExceptionHandler.java
├── security/                        # JWT filter, SecurityContext helpers
│   └── JwtAuthenticationFilter.java
└── common/                          # Shared utilities, base classes
    └── AuditableEntity.java
```

- One class per file. Package-by-feature for large projects, package-by-layer for small.
- Controllers are thin: parse request, call service, return response.
- Services own business logic and transaction boundaries.
- Repositories are Spring Data interfaces only — no implementation classes unless custom queries demand it.

## Dependency Injection

```java
// Constructor injection — the ONLY acceptable form
@Service
public class WidgetServiceImpl implements WidgetService {
    private final WidgetRepository repository;
    private final CacheManager cacheManager;

    // Spring auto-injects when there is exactly one constructor
    public WidgetServiceImpl(WidgetRepository repository, CacheManager cacheManager) {
        this.repository = repository;
        this.cacheManager = cacheManager;
    }
}
```

- NEVER use `@Autowired` on fields — it hides dependencies and breaks testability.
- NEVER use setter injection — it allows partially constructed objects.
- If a class has many constructor params (>5), it needs decomposition, not Lombok `@RequiredArgsConstructor`.

## Configuration

```yaml
# application.yml — base config
spring:
  application:
    name: widget-service
  datasource:
    url: jdbc:postgresql://${DB_HOST:localhost}:${DB_PORT:5432}/${DB_NAME:appdb}
    username: ${DB_USER:app}
    password: ${DB_PASSWORD}
    hikari:
      maximum-pool-size: 20
      minimum-idle: 5
      connection-timeout: 30000
  jpa:
    open-in-view: false          # MUST be false — prevents lazy loading in controllers
    hibernate:
      ddl-auto: validate         # NEVER use update/create in production
    properties:
      hibernate.jdbc.batch_size: 25
  cache:
    type: redis

# application-local.yml — local dev overrides (activated by SPRING_PROFILES_ACTIVE=local)
# application-prod.yml  — production overrides
```

- Use `${ENV_VAR:default}` syntax for environment-specific values.
- ALWAYS set `spring.jpa.open-in-view: false` — it causes N+1 queries and lazy loading surprises.
- ALWAYS set `ddl-auto: validate` — schema changes go through Flyway/Liquibase.
- Profile activation: `SPRING_PROFILES_ACTIVE=local,redis` environment variable.

## Exception Handling

Every error response is the envelope from `~/.claude/skills/api/response-envelope.md`, written by ONE
`@RestControllerAdvice`. The full, canonical version (exception hierarchy, every handler, Spring
Security 401/403, database errors) is `backend/archetypes/error-handling-java.md`; this is its shape:

```java
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(DomainException.class)          // NOT_FOUND, CONFLICT, BUSINESS_RULE_VIOLATION, ...
    public ResponseEntity<ErrorBody> handleDomain(DomainException ex) {
        return write(ex);
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)   // 400 VALIDATION_FAILED + details[]
    public ResponseEntity<ErrorBody> handleValidation(MethodArgumentNotValidException ex) {
        var details = ex.getBindingResult().getFieldErrors().stream()
            .map(FieldError::fromConstraint) // closed-set code (Size → too_short/too_long) + catalog message
            .toList();
        return write(new ValidationException(details));
    }

    @ExceptionHandler(Exception.class)                // anything else: 500 INTERNAL, generic message
    public ResponseEntity<ErrorBody> handleUnexpected(Exception ex) {
        return write(new InternalException(ex));
    }

    // Logs the cause with request_id, sets Retry-After / WWW-Authenticate, and returns
    // {"error": {"code", "message", "details"?, "request_id", "retryable"}} — body in error-handling-java.md
    private ResponseEntity<ErrorBody> write(DomainException ex) { ... }
}
```

```json
{"error": {"code": "NOT_FOUND", "message": "Widget not found.", "request_id": "b7e1c2…", "retryable": false}}
```

- One `@RestControllerAdvice` is the only code that writes an error body — controllers never catch exceptions or build error JSON.
- Do not return Spring's RFC 7807 `ProblemDetail` (`type`/`title`/`detail`); it is a different error shape from the envelope.
- The HTTP status carries the class: 400 `MALFORMED_REQUEST`/`VALIDATION_FAILED`, 401 `UNAUTHENTICATED`, 403 `FORBIDDEN`, 404 `NOT_FOUND`, 409 `CONFLICT`, 422 `BUSINESS_RULE_VIOLATION`, 429 `RATE_LIMITED`, 500 `INTERNAL`, 503 `UNAVAILABLE`.
- No client-visible field contains an exception's message or cause, SQL, a constraint name or a stack trace; the cause goes to the log under `request_id`.
- Spring Security's 401/403 are routed into the same advice by `SecurityErrorDelegate` (wire it in the `SecurityFilterChain` below).

## Validation

```java
public record CreateWidgetRequest(
    @NotBlank @Size(max = 255) String name,
    @Size(max = 2000) String description,
    @NotNull WidgetStatus status
) {}

// In controller — the response is the envelope (ApiResponse, crud-handler-java.md):
@PostMapping
public ResponseEntity<ApiResponse<WidgetResponse>> create(@Valid @RequestBody CreateWidgetRequest request) { ... }
```

- Use `@Valid` on `@RequestBody` — Spring auto-validates and throws `MethodArgumentNotValidException`.
- Use Jakarta Validation annotations (`@NotBlank`, `@Size`, `@Email`, `@Pattern`).
- For cross-field validation, implement `Validator` or use a class-level `@Constraint`.

## Security

```java
@Configuration
@EnableWebSecurity
public class SecurityConfig {

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http, JwtAuthenticationFilter jwtFilter,
                                           SecurityErrorDelegate errors) throws Exception {
        return http
            .csrf(AbstractHttpConfigurer::disable)
            .sessionManagement(sm -> sm.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/api/public/**", "/actuator/health").permitAll()
                .requestMatchers("/api/admin/**").hasRole("ADMIN")
                .anyRequest().authenticated()
            )
            // 401/403 go through GlobalExceptionHandler → error envelope (error-handling-java.md)
            .exceptionHandling(e -> e.authenticationEntryPoint(errors).accessDeniedHandler(errors))
            .addFilterBefore(jwtFilter, UsernamePasswordAuthenticationFilter.class)
            .build();
    }
}
```

- Stateless sessions for REST APIs — JWT in `Authorization: Bearer` header.
- Disable CSRF for stateless APIs.
- Use `@AuthenticationPrincipal` in controllers to extract the current user.
- Never roll your own JWT parsing — use `spring-boot-starter-oauth2-resource-server` or `jjwt`.

## Testing Conventions

```java
// Unit test — no Spring context
@ExtendWith(MockitoExtension.class)
class WidgetServiceTest {
    @Mock WidgetRepository repository;
    @InjectMocks WidgetServiceImpl service;
}

// Integration test — full Spring context
@SpringBootTest
@Testcontainers
class WidgetIntegrationTest {
    @Container
    @ServiceConnection // Testcontainers 2: org.testcontainers.postgresql.PostgreSQLContainer, no type parameter
    static PostgreSQLContainer pg = new PostgreSQLContainer("postgres:16-alpine");
}

// Controller test — web layer only (Spring Boot 4: org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest)
@WebMvcTest(WidgetController.class)
class WidgetControllerTest {
    @Autowired MockMvc mockMvc;
    @MockitoBean WidgetService widgetService; // @MockBean was removed in Spring Boot 4
}

// Repository test — JPA layer only (org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest)
@DataJpaTest
class WidgetRepositoryTest {
    @Autowired TestEntityManager entityManager;
    @Autowired WidgetRepository repository;
}
```

## Rules

- Constructor injection only — no `@Autowired` fields.
- `spring.jpa.open-in-view: false` in every project.
- `ddl-auto: validate` — Flyway/Liquibase for migrations.
- DTOs are Java records — never expose JPA entities in API responses.
- `@RestControllerAdvice` for all error mapping, writing the envelope from `api/response-envelope.md` (`backend/archetypes/error-handling-java.md`) — no try-catch in controllers, no `ProblemDetail`.
- `@Transactional` on service methods, never on controllers or repositories.
- Test slices (`@WebMvcTest`, `@DataJpaTest`) over full `@SpringBootTest` when possible.
