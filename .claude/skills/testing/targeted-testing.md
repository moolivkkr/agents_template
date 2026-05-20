# Targeted Component Testing

When you need to test a specific component without running the full test suite:

## Pattern

```bash
# Go — test specific package
go test ./internal/services/auth/... -v -count=1

# Go — test specific function
go test ./internal/services/auth/... -v -count=1 -run TestCreateToken

# Python — test specific module
pytest tests/unit/test_auth.py -v

# Python — test specific function
pytest tests/unit/test_auth.py::test_create_token -v

# Java — test specific class
mvn test -Dtest=AuthServiceTest

# Java — test specific method
mvn test -Dtest=AuthServiceTest#testCreateToken

# Rust — test specific module
cargo test auth:: --lib

# Rust — test specific function
cargo test auth::test_create_token --lib

# TypeScript — test specific file
npx vitest run src/services/auth.test.ts

# TypeScript — test specific pattern
npx vitest run src/services/auth.test.ts -t "create token"
```

## When to Use
- **Hotfix:** only test the fixed component — skip unrelated suites
- **Debugging:** isolate a failing test from noise
- **Development iteration:** fast feedback on the component you are actively editing
- **Code review:** verify a specific change without waiting for the full suite

## When NOT to Use
- **Before merge:** always run the full suite before merging to main
- **After refactoring shared code:** changes to shared utilities need full test coverage
- **CI/CD pipelines:** pipelines should run the full suite (targeted testing is for local dev)

## File Convention: Mapping Source to Test

| Language | Source File | Test File | Convention |
|----------|-----------|-----------|------------|
| Go | `internal/auth/service.go` | `internal/auth/service_test.go` | Same directory, `_test.go` suffix |
| Python | `app/services/auth.py` | `tests/unit/test_auth.py` | `tests/` mirror, `test_` prefix |
| Java | `src/main/java/.../AuthService.java` | `src/test/java/.../AuthServiceTest.java` | `src/test/` mirror, `Test` suffix |
| Rust | `src/services/auth.rs` | `src/services/auth.rs` (inline `#[cfg(test)]`) | Same file, `mod tests` |
| TypeScript | `src/services/auth.ts` | `src/services/auth.test.ts` | Same directory, `.test.ts` suffix |

## Integration with /hotfix

The `/hotfix` command uses targeted testing to scope tests to the affected component:

1. **Identify affected files** — read the manifest or diff to find changed source files
2. **Map source to test files** — use the naming convention above:
   - `auth.go` maps to `auth_test.go`
   - `auth_service.py` maps to `test_auth_service.py`
   - `AuthService.java` maps to `AuthServiceTest.java`
3. **Run only those test files** — execute targeted tests for fast feedback
4. **If all pass** — proceed to scoped review (only review changed files)
5. **If any fail** — fix and re-run targeted tests before proceeding

## Combining with Watch Mode

For active development, use watch mode to re-run targeted tests on file save:

```bash
# Go — use air or gotestsum
gotestsum --watch ./internal/services/auth/...

# Python — pytest-watch
ptw tests/unit/test_auth.py

# Java — use continuous testing in IDE (IntelliJ) or gradle --continuous
./gradlew test --continuous --tests AuthServiceTest

# Rust — cargo-watch
cargo watch -x "test auth::"

# TypeScript — vitest watch mode
npx vitest watch src/services/auth.test.ts
```

## Rules
- Targeted testing is for local development speed — never skip the full suite in CI
- Map source files to test files using the language convention table above
- Use `-count=1` in Go to disable test caching during active development
- Use `-v` (verbose) when debugging — see individual test names and results
- Combine with watch mode for the fastest feedback loop during development
- After targeted tests pass, run the full suite once before committing
