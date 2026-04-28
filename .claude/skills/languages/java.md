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

## Error Handling
- Checked exceptions only at system boundaries (I/O, external calls)
- Domain layer: unchecked `RuntimeException` subclasses
- `@ControllerAdvice` for centralized HTTP error mapping
- Never swallow exceptions — log + rethrow or convert

## Records for DTOs
```java
public record CreateUserRequest(
    @NotBlank String email,
    @Size(min = 8) String password
) {}
```
Use Java records for immutable DTOs — no Lombok needed.

## Testing
```java
@ParameterizedTest
@CsvSource({"valid@email.com,true", "not-email,false"})
void testEmailValidation(String email, boolean expected) {
    assertEquals(expected, EmailValidator.isValid(email));
}
```
- JUnit 5 with `@ParameterizedTest` for data-driven tests
- Mockito for mocking; `@MockBean` only in Spring integration tests
- `@DataJpaTest` for repository tests (uses embedded DB)
- `@WebMvcTest` for controller tests (no full context)

## Optional
- Never return `null` from public methods — use `Optional<T>`
- Never call `.get()` without checking — use `.orElseThrow()` or `.orElse()`
- Don't use `Optional` as method parameter — use overloads

## Rules
- `final` on all fields that don't change after construction
- Streams over imperative loops for collection transformations
- `@Transactional` at service layer, not repository layer
- Flyway for DB migrations
- Never use `System.out.println` — use SLF4J logger
