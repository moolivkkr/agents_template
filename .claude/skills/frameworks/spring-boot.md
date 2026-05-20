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

```java
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(ResourceNotFoundException.class)
    public ResponseEntity<ProblemDetail> handleNotFound(ResourceNotFoundException ex) {
        var problem = ProblemDetail.forStatusAndDetail(HttpStatus.NOT_FOUND, ex.getMessage());
        problem.setTitle("Resource Not Found");
        problem.setProperty("resource", ex.getResource());
        return ResponseEntity.status(HttpStatus.NOT_FOUND).body(problem);
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ProblemDetail> handleValidation(MethodArgumentNotValidException ex) {
        var errors = ex.getBindingResult().getFieldErrors().stream()
            .collect(Collectors.toMap(FieldError::getField, FieldError::getDefaultMessage));
        var problem = ProblemDetail.forStatusAndDetail(HttpStatus.UNPROCESSABLE_ENTITY, "Validation failed");
        problem.setTitle("Validation Error");
        problem.setProperty("fieldErrors", errors);
        return ResponseEntity.status(HttpStatus.UNPROCESSABLE_ENTITY).body(problem);
    }
}
```

- Use `ProblemDetail` (RFC 7807) — Spring 6+ has native support.
- Single `@RestControllerAdvice` handles ALL exception types in one place.
- NEVER catch `Exception` in controllers — let the advice handle it.

## Validation

```java
public record CreateWidgetRequest(
    @NotBlank @Size(max = 255) String name,
    @Size(max = 2000) String description,
    @NotNull WidgetStatus status
) {}

// In controller:
@PostMapping
public ResponseEntity<WidgetResponse> create(@Valid @RequestBody CreateWidgetRequest request) { ... }
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
    public SecurityFilterChain filterChain(HttpSecurity http, JwtAuthenticationFilter jwtFilter) throws Exception {
        return http
            .csrf(AbstractHttpConfigurer::disable)
            .sessionManagement(sm -> sm.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/api/public/**", "/actuator/health").permitAll()
                .requestMatchers("/api/admin/**").hasRole("ADMIN")
                .anyRequest().authenticated()
            )
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
    static PostgreSQLContainer<?> pg = new PostgreSQLContainer<>("postgres:16-alpine");
}

// Controller test — web layer only
@WebMvcTest(WidgetController.class)
class WidgetControllerTest {
    @Autowired MockMvc mockMvc;
    @MockBean WidgetService widgetService;
}

// Repository test — JPA layer only
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
- `@RestControllerAdvice` for all error mapping — no try-catch in controllers.
- `@Transactional` on service methods, never on controllers or repositories.
- Test slices (`@WebMvcTest`, `@DataJpaTest`) over full `@SpringBootTest` when possible.
