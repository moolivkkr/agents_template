---
skill: junit-mockito
description: JUnit 5 + Mockito skill pack — unit tests, controller tests with MockMvc, repository tests with @DataJpaTest, integration tests with Testcontainers, AssertJ, JaCoCo coverage
version: "1.0"
tags:
  - java
  - junit
  - mockito
  - testing
  - spring-boot
---

# JUnit 5 + Mockito Testing Patterns

> Java samples compile-checked 2026-09-30: JDK 25.0.4.1, Spring Boot 4.1.1, Maven 3.9.16 (`tests/archetype-compile/java/run.sh`). The unit, validation, controller and repository tests were also run against the Widget archetypes they test (the repository test on PostgreSQL 16), and the JaCoCo block with `mvn verify`.

## Unit Tests (No Spring Context)

```java
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.*;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.BDDMockito.*;

@ExtendWith(MockitoExtension.class)
class WidgetServiceTest {

    @Mock WidgetRepository repository;
    @Mock AuditService auditService;
    @InjectMocks WidgetServiceImpl service;

    private UUID tenantId;
    private UUID userId;

    @BeforeEach
    void setUp() {
        tenantId = UUID.randomUUID();
        userId = UUID.randomUUID();
    }

    @Test
    @DisplayName("create - persists widget and returns it")
    void create_validInput_persistsAndReturns() {
        var request = new CreateWidgetRequest("My Widget", "A description");
        given(repository.existsByTenantIdAndNameIgnoreCase(tenantId, "My Widget")).willReturn(false);
        given(repository.save(any(Widget.class))).willAnswer(invocation -> invocation.getArgument(0));

        var result = service.create(request, tenantId, userId);

        assertThat(result.getName()).isEqualTo("My Widget");
        assertThat(result.getTenantId()).isEqualTo(tenantId);
        assertThat(result.getStatus()).isEqualTo(WidgetStatus.ACTIVE);

        then(repository).should().save(any(Widget.class));
        then(auditService).should().log(eq("widget.created"), any(), eq(tenantId), eq(userId), any());
    }

    @Test
    @DisplayName("create - duplicate name throws ConflictException")
    void create_duplicateName_throwsConflict() {
        given(repository.existsByTenantIdAndNameIgnoreCase(tenantId, "Existing"))
            .willReturn(true);

        assertThatThrownBy(() -> service.create(new CreateWidgetRequest("Existing", null), tenantId, userId))
            .isInstanceOf(ConflictException.class)
            .hasMessageContaining("already exists");

        then(repository).should(never()).save(any());
    }

    @Test
    @DisplayName("findById - not found throws ResourceNotFoundException")
    void findById_notFound_throws() {
        var id = UUID.randomUUID();
        given(repository.findByIdAndTenantId(id, tenantId)).willReturn(Optional.empty());

        assertThatThrownBy(() -> service.findById(id, tenantId))
            .isInstanceOf(ResourceNotFoundException.class)
            .hasFieldOrPropertyWithValue("userMessage", "Widget not found.") // what the client sees: no id
            .hasFieldOrPropertyWithValue("identifier", id.toString());      // the id is log context only
    }

    @Nested
    @DisplayName("update")
    class UpdateTests {

        @Test
        @DisplayName("version mismatch throws ConflictException")
        void versionMismatch_throwsConflict() {
            var id = UUID.randomUUID();
            var existing = new Widget();
            existing.setVersion(3);
            given(repository.findByIdAndTenantId(id, tenantId)).willReturn(Optional.of(existing));

            var request = new UpdateWidgetRequest("New Name", "desc", 1); // stale version

            assertThatThrownBy(() -> service.update(id, request, tenantId, userId))
                .isInstanceOf(ConflictException.class)
                .hasMessageContaining("Version mismatch");
        }
    }
}
```

## Parameterized Tests

```java
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.*;

class WidgetValidationTest {

    private final Validator validator = Validation.buildDefaultValidatorFactory().getValidator();

    @ParameterizedTest
    @NullAndEmptySource
    @ValueSource(strings = {"   ", "\t"})
    @DisplayName("blank names are rejected")
    void blankNames_rejected(String name) {
        var request = new CreateWidgetRequest(name, "desc");
        var violations = validator.validate(request);
        assertThat(violations).anyMatch(v -> v.getPropertyPath().toString().equals("name"));
    }

    @ParameterizedTest
    @CsvSource({
        "2000, true",
        "2001, false"
    })
    void description_atMost2000Characters(int length, boolean valid) {
        var request = new CreateWidgetRequest("name", "x".repeat(length));
        assertThat(validator.validate(request).isEmpty()).isEqualTo(valid);
    }

    @ParameterizedTest
    @MethodSource("invalidNameProvider")
    void invalidNames_rejected(String name, String expectedMessage) {
        var request = new CreateWidgetRequest(name, null);
        var violations = validator.validate(request);
        assertThat(violations).anyMatch(v -> v.getMessage().contains(expectedMessage));
    }

    static Stream<Arguments> invalidNameProvider() {
        return Stream.of(
            Arguments.of("", "Name is required"),
            Arguments.of("x".repeat(256), "255 characters or fewer")
        );
    }
}
```

## Controller Tests with MockMvc

```java
import com.example.app.config.SecurityConfig;
import com.example.app.security.SecurityErrorDelegate;
import com.example.app.security.UserPrincipal;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;       // Spring Boot 4 package
import org.springframework.context.annotation.Import;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.context.bean.override.mockito.MockitoBean;  // @MockBean was removed in Spring Boot 4
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.user;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@WebMvcTest(WidgetController.class)
@Import({SecurityConfig.class, SecurityErrorDelegate.class}) // the app's filter chain (auth-middleware-java.md)
@TestPropertySource(properties = {                            // JwtAuthenticationFilter is a Filter bean: test key
    "app.jwt.secret=test-only-hmac-key-of-at-least-32-bytes", "app.jwt.issuer=test", "app.jwt.audience=test"})
class WidgetControllerTest {

    private static final UUID TENANT_ID = UUID.fromString("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa");
    private static final UUID USER_ID = UUID.fromString("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb");

    @Autowired MockMvc mockMvc;
    @MockitoBean WidgetService widgetService;

    // The tenant comes from the authenticated principal, never from a header or the body
    private static UserPrincipal principal() {
        return new UserPrincipal(USER_ID, TENANT_ID, "test@example.com",
            List.of(new SimpleGrantedAuthority("ROLE_USER")));
    }

    private static Widget buildWidget(String name) {
        var widget = new Widget();
        widget.setId(UUID.randomUUID());
        widget.setTenantId(TENANT_ID);
        widget.setName(name);
        widget.setStatus(WidgetStatus.ACTIVE);
        widget.setCreatedAt(Instant.now());
        widget.setUpdatedAt(Instant.now());
        widget.setCreatedBy(USER_ID);
        widget.setVersion(1);
        return widget;
    }

    @Test
    void create_validRequest_returns201() throws Exception {
        given(widgetService.create(any(), eq(TENANT_ID), eq(USER_ID))).willReturn(buildWidget("Test Widget"));

        mockMvc.perform(post("/api/v1/widgets")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                    {"name": "Test Widget", "description": "A test widget"}
                    """)
                .with(user(principal())))
            .andExpect(status().isCreated())
            .andExpect(jsonPath("$.data.name").value("Test Widget"))
            .andExpect(jsonPath("$.meta.request_id").exists()); // the envelope's key (api/response-envelope.md)
    }

    @Test
    void list_limitOver100_returns400() throws Exception {
        mockMvc.perform(get("/api/v1/widgets")
                .param("limit", "500") // over the max: rejected, never silently clamped
                .with(user(principal())))
            .andExpect(status().isBadRequest())
            .andExpect(jsonPath("$.error.code").value("VALIDATION_FAILED"))
            .andExpect(jsonPath("$.error.details[0].field").value("limit"));

        then(widgetService).shouldHaveNoInteractions();
    }

    @Test
    void delete_returnsNoContent() throws Exception {
        var id = UUID.randomUUID();

        mockMvc.perform(delete("/api/v1/widgets/{id}", id)
                .with(user(principal())))
            .andExpect(status().isNoContent())
            .andExpect(content().string(""));

        then(widgetService).should().delete(id, TENANT_ID, USER_ID);
    }
}
```

## Repository Tests with @DataJpaTest

```java
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;             // Spring Boot 4 packages
import org.springframework.boot.jdbc.test.autoconfigure.AutoConfigureTestDatabase;
import org.springframework.boot.jpa.test.autoconfigure.TestEntityManager;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.postgresql.PostgreSQLContainer;                             // Testcontainers 2

@DataJpaTest
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE) // real Postgres, not H2
@Testcontainers
class WidgetRepositoryTest {

    @Container
    @ServiceConnection
    static PostgreSQLContainer postgres = new PostgreSQLContainer("postgres:16-alpine");

    @Autowired TestEntityManager entityManager;
    @Autowired WidgetRepository repository;

    private UUID tenantId;

    @BeforeEach
    void setUp() {
        tenantId = UUID.randomUUID();
    }

    @Test
    void findByIdAndTenantId_wrongTenant_returnsEmpty() {
        var widget = createAndPersistWidget("Test", tenantId);
        var otherTenant = UUID.randomUUID();

        var result = repository.findByIdAndTenantId(widget.getId(), otherTenant);

        assertThat(result).isEmpty(); // tenant isolation enforced
    }

    @Test
    void softDelete_setsDeletedAt_excludesFromQueries() {
        var widget = createAndPersistWidget("Test", tenantId);
        entityManager.flush();

        repository.delete(widget); // triggers @SQLDelete
        entityManager.flush();
        entityManager.clear(); // evict from persistence context

        // @SQLRestriction excludes soft-deleted records
        assertThat(repository.findByIdAndTenantId(widget.getId(), tenantId)).isEmpty();
    }

    @Test
    void findFirst20_scrollsByKeyset() { // cursor pagination: no offset, no COUNT
        for (int i = 0; i < 25; i++) {
            createAndPersistWidget("Widget " + i, tenantId);
        }
        entityManager.flush();

        var first = repository.findFirst20ByTenantIdOrderByCreatedAtDescIdDesc(tenantId, ScrollPosition.keyset());
        var second = repository.findFirst20ByTenantIdOrderByCreatedAtDescIdDesc(
            tenantId, first.positionAt(first.size() - 1));

        assertThat(first.getContent()).hasSize(20);
        assertThat(first.hasNext()).isTrue();
        assertThat(second.getContent()).hasSize(5).doesNotContainAnyElementsOf(first.getContent());
        assertThat(second.hasNext()).isFalse();
    }

    private Widget createAndPersistWidget(String name, UUID tenant) {
        var widget = new Widget();
        widget.setTenantId(tenant);
        widget.setName(name);
        widget.setStatus(WidgetStatus.ACTIVE);
        widget.setCreatedAt(Instant.now());
        widget.setUpdatedAt(Instant.now());
        widget.setCreatedBy(UUID.randomUUID());
        widget.setUpdatedBy(UUID.randomUUID());
        return entityManager.persistAndFlush(widget);
    }
}
```

## Integration Tests with Testcontainers

```java
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.springframework.boot.resttestclient.TestRestTemplate;                      // spring-boot-resttestclient
import org.springframework.boot.resttestclient.autoconfigure.AutoConfigureTestRestTemplate;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.core.ParameterizedTypeReference;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.postgresql.PostgreSQLContainer;                             // Testcontainers 2

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT, properties = {
    "app.jwt.secret=" + WidgetIntegrationTest.SECRET, "app.jwt.issuer=test", "app.jwt.audience=test"})
@AutoConfigureTestRestTemplate
@Testcontainers
class WidgetIntegrationTest {

    static final String SECRET = "test-only-hmac-key-of-at-least-32-bytes";
    static final UUID TENANT_ID = UUID.randomUUID();

    @Container
    @ServiceConnection // spring.datasource.* point at the container
    static PostgreSQLContainer postgres = new PostgreSQLContainer("postgres:16-alpine");

    @Autowired TestRestTemplate restTemplate;

    // A token JwtAuthenticationFilter (auth-middleware-java.md) accepts: same key, issuer and audience
    private static HttpHeaders auth() {
        var token = Jwts.builder()
            .subject(UUID.randomUUID().toString()).issuer("test").audience().add("test").and()
            .claim("tenant_id", TENANT_ID.toString()).claim("roles", List.of("USER"))
            .expiration(Date.from(Instant.now().plusSeconds(300)))
            .signWith(Keys.hmacShaKeyFor(SECRET.getBytes(StandardCharsets.UTF_8)))
            .compact();
        var headers = new HttpHeaders();
        headers.setBearerAuth(token);
        return headers;
    }

    @Test
    void fullCrudLifecycle() {
        var widgetType = new ParameterizedTypeReference<ApiResponse<WidgetResponse>>() {};

        // Create
        var created = restTemplate.exchange("/api/v1/widgets", HttpMethod.POST,
            new HttpEntity<>(new CreateWidgetRequest("Integration Test Widget", "desc"), auth()), widgetType);
        assertThat(created.getStatusCode()).isEqualTo(HttpStatus.CREATED);
        var id = created.getBody().data().id();

        // Read
        var read = restTemplate.exchange("/api/v1/widgets/{id}", HttpMethod.GET, new HttpEntity<>(auth()), widgetType, id);
        assertThat(read.getStatusCode()).isEqualTo(HttpStatus.OK);

        // Delete, then the error envelope (not ProblemDetail)
        restTemplate.exchange("/api/v1/widgets/{id}", HttpMethod.DELETE, new HttpEntity<>(auth()), Void.class, id);
        var afterDelete = restTemplate.exchange("/api/v1/widgets/{id}", HttpMethod.GET, new HttpEntity<>(auth()),
            ErrorBody.class, id);
        assertThat(afterDelete.getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
        assertThat(afterDelete.getBody().error().code()).isEqualTo("NOT_FOUND");
    }
}
```

## AssertJ Patterns

```java
// Object assertions
assertThat(widget.getName()).isEqualTo("My Widget");
assertThat(widget.getCreatedAt()).isNotNull().isBefore(Instant.now());

// Collection assertions
assertThat(widgets).hasSize(3)
    .extracting(Widget::getName)
    .containsExactly("Alpha", "Beta", "Gamma");

// Exception assertions
assertThatThrownBy(() -> service.findById(id, tenantId))
    .isInstanceOf(ResourceNotFoundException.class)
    .hasMessageContaining("not found")
    .hasFieldOrPropertyWithValue("resource", "Widget");

// Soft assertions (collect multiple failures)
SoftAssertions.assertSoftly(softly -> {
    softly.assertThat(result.getName()).isEqualTo("Test");
    softly.assertThat(result.getStatus()).isEqualTo(WidgetStatus.ACTIVE);
    softly.assertThat(result.getVersion()).isEqualTo(1);
});
```

## JaCoCo Coverage Configuration

```xml
<!-- pom.xml -->
<plugin>
    <groupId>org.jacoco</groupId>
    <artifactId>jacoco-maven-plugin</artifactId>
    <version>0.8.15</version> <!-- 0.8.12 cannot read JDK 25 class files (major version 69) -->
    <executions>
        <execution>
            <goals><goal>prepare-agent</goal></goals>
        </execution>
        <execution>
            <id>report</id>
            <phase>test</phase>
            <goals><goal>report</goal></goals>
        </execution>
        <execution>
            <id>check</id>
            <phase>verify</phase>
            <goals><goal>check</goal></goals>
            <configuration>
                <rules>
                    <rule>
                        <element>BUNDLE</element>
                        <limits>
                            <limit>
                                <counter>LINE</counter>
                                <value>COVEREDRATIO</value>
                                <minimum>0.80</minimum>
                            </limit>
                        </limits>
                    </rule>
                </rules>
                <excludes>
                    <exclude>**/config/**</exclude>
                    <exclude>**/model/dto/**</exclude>
                    <exclude>**/Application.class</exclude>
                </excludes>
            </configuration>
        </execution>
    </executions>
</plugin>
```

## Run Commands

```bash
mvn test                                    # run all tests
mvn test -pl module-name                    # tests for one module
mvn test -Dtest=WidgetServiceTest           # single test class
mvn test -Dtest="WidgetServiceTest#create*" # tests matching pattern
mvn verify                                  # run tests + JaCoCo coverage check
mvn jacoco:report                           # generate HTML coverage report
```

## Rules

- Use `@ExtendWith(MockitoExtension.class)` for unit tests — no Spring context needed.
- Use `@WebMvcTest` for controller tests — loads only the web layer + mocks services.
- Use `@DataJpaTest` for repository tests — JPA layer against Testcontainers Postgres (`@AutoConfigureTestDatabase(replace = NONE)`); H2 hides Postgres behaviour.
- Use `@SpringBootTest` + `@Testcontainers` for integration tests — full context with real Postgres.
- BDDMockito (`given`/`then`) over classic Mockito (`when`/`verify`) — reads like specifications.
- AssertJ over JUnit assertions — fluent, expressive, better error messages.
- `@DisplayName` on every test — describes the scenario, not the method name.
- `@Nested` for grouping related test cases (e.g., all update scenarios).
- `@ParameterizedTest` for testing multiple inputs — avoids copy-paste test methods.
- Never test implementation details — test behavior and outcomes.
- Test tenant isolation explicitly: verify that tenant A cannot access tenant B's data.
- JaCoCo minimum 80% line coverage — exclude config, DTOs, and Application class.

> Config blocks checked 2026-09-30 (`bash tests/archetype-compile/config-packs/run.sh --live`): 1 bash block: bash -n (macOS bash 3.2.57) + shellcheck 0.11.0.
