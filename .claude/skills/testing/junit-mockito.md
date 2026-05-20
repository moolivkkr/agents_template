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
            .hasMessageContaining(id.toString());
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
        "ACTIVE, true",
        "INACTIVE, true",
        "ARCHIVED, false"
    })
    void isEditable_dependsOnStatus(WidgetStatus status, boolean expected) {
        var widget = new Widget();
        widget.setStatus(status);
        assertThat(widget.isEditable()).isEqualTo(expected);
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
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@WebMvcTest(WidgetController.class)
class WidgetControllerTest {

    @Autowired MockMvc mockMvc;
    @MockBean WidgetService widgetService;

    @Test
    void create_validRequest_returns201() throws Exception {
        var widget = buildWidget("Test Widget");
        given(widgetService.create(any(), any(), any())).willReturn(widget);

        mockMvc.perform(post("/api/v1/widgets")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                    {"name": "Test Widget", "description": "A test widget"}
                    """)
                .with(jwt().jwt(builder -> builder
                    .claim("tenant_id", TENANT_ID.toString())
                    .claim("sub", USER_ID.toString()))))
            .andExpect(status().isCreated())
            .andExpect(jsonPath("$.data.name").value("Test Widget"))
            .andExpect(jsonPath("$.meta.requestId").exists());
    }

    @Test
    void list_pagination_enforcesMaxPageSize() throws Exception {
        given(widgetService.findAll(any(), isNull(), any())).willReturn(Page.empty());

        mockMvc.perform(get("/api/v1/widgets")
                .param("size", "500") // exceeds max
                .with(jwt()))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.meta.size").value(100)); // capped at max
    }

    @Test
    void delete_returnsNoContent() throws Exception {
        var id = UUID.randomUUID();

        mockMvc.perform(delete("/api/v1/widgets/{id}", id)
                .with(jwt()))
            .andExpect(status().isNoContent())
            .andExpect(content().string(""));
    }
}
```

## Repository Tests with @DataJpaTest

```java
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.autoconfigure.orm.jpa.TestEntityManager;

@DataJpaTest
class WidgetRepositoryTest {

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
    void findByTenantId_paginatesCorrectly() {
        for (int i = 0; i < 25; i++) {
            createAndPersistWidget("Widget " + i, tenantId);
        }
        entityManager.flush();

        var page = repository.findByTenantId(tenantId, PageRequest.of(0, 10, Sort.by("name")));

        assertThat(page.getContent()).hasSize(10);
        assertThat(page.getTotalElements()).isEqualTo(25);
        assertThat(page.getTotalPages()).isEqualTo(3);
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
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@Testcontainers
class WidgetIntegrationTest {

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

    @Autowired TestRestTemplate restTemplate;

    @Test
    void fullCrudLifecycle() {
        // Create
        var createResponse = restTemplate.postForEntity("/api/v1/widgets",
            new CreateWidgetRequest("Integration Test Widget", "desc"), ApiResponse.class);
        assertThat(createResponse.getStatusCode()).isEqualTo(HttpStatus.CREATED);

        // Read
        var id = extractId(createResponse);
        var getResponse = restTemplate.getForEntity("/api/v1/widgets/{id}", ApiResponse.class, id);
        assertThat(getResponse.getStatusCode()).isEqualTo(HttpStatus.OK);

        // Delete
        restTemplate.delete("/api/v1/widgets/{id}", id);
        var afterDelete = restTemplate.getForEntity("/api/v1/widgets/{id}", ProblemDetail.class, id);
        assertThat(afterDelete.getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
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
    .hasFieldOrPropertyWithValue("resource", "widget");

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
    <version>0.8.12</version>
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
- Use `@DataJpaTest` for repository tests — loads JPA layer with embedded H2 (or Testcontainers).
- Use `@SpringBootTest` + `@Testcontainers` for integration tests — full context with real Postgres.
- BDDMockito (`given`/`then`) over classic Mockito (`when`/`verify`) — reads like specifications.
- AssertJ over JUnit assertions — fluent, expressive, better error messages.
- `@DisplayName` on every test — describes the scenario, not the method name.
- `@Nested` for grouping related test cases (e.g., all update scenarios).
- `@ParameterizedTest` for testing multiple inputs — avoids copy-paste test methods.
- Never test implementation details — test behavior and outcomes.
- Test tenant isolation explicitly: verify that tenant A cannot access tenant B's data.
- JaCoCo minimum 80% line coverage — exclude config, DTOs, and Application class.
