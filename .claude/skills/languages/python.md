# Python patterns and conventions for building reliable, maintainable applications.

## Project Structure
```
src/
  myapp/
    __init__.py
    domain/        # entities, value objects
    services/      # business logic
    repositories/  # data access
    api/           # HTTP layer
    config.py
tests/
  unit/
  integration/
pyproject.toml     # prefer over setup.py
```

## Type Hints
- Use everywhere — function signatures, class attributes, return types
- Prefer `X | None` over `Optional[X]` (Python 3.10+)
- Use `TypeAlias` for complex types; `Protocol` for structural typing
- Run `mypy --strict` in CI

## Data Validation
- Use Pydantic v2 for all data at system boundaries (API in/out, config)
- `dataclasses` for pure internal data with no validation
- Never use bare `dict` for structured data — define a model

## Error Handling
```python
# Define domain errors
class UserNotFoundError(Exception):
    def __init__(self, user_id: str) -> None:
        super().__init__(f"User {user_id} not found")

# Wrap infrastructure errors at boundary
try:
    return await db.get_user(user_id)
except DBConnectionError as e:
    raise RepositoryError("Failed to fetch user") from e
```
- Never `except Exception` without re-raising or logging
- Use `from e` to preserve cause chain

## Async
- `async/await` throughout for I/O bound code
- Use `asyncio.gather()` for concurrent independent tasks
- Never mix sync and async — use `run_in_executor` if unavoidable
- `anyio` for library code; `asyncio` directly for app code

## Testing (pytest)
```python
@pytest.mark.parametrize("input,expected", [
    ("valid@email.com", True),
    ("not-an-email", False),
])
def test_email_validation(input: str, expected: bool) -> None:
    assert validate_email(input) == expected
```
- Fixtures for shared setup; `conftest.py` for cross-module fixtures
- `pytest-asyncio` for async tests
- Mock only external I/O — never mock domain logic

## Logging
```python
import structlog
log = structlog.get_logger()
log.info("user_created", user_id=user.id, email=user.email)
```
- Structured logging always — never f-strings in log calls
- Bind request context (request_id, user_id) at middleware level

## Rules
- Never `import *`
- Prefer `pathlib.Path` over `os.path`
- Use `__slots__` on hot dataclasses
- `uv` or `poetry` for dependency management — not bare pip
- 88-char line length (Black default)
