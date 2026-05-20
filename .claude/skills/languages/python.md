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

## Type Safety

```python
from typing import TypedDict, Protocol, Literal, TypeVar, overload, Generic

# TypedDict for dictionaries with known shapes (API responses, configs)
class UserResponse(TypedDict):
    id: str
    email: str
    is_active: bool

class PaginatedResponse(TypedDict, Generic[T]):
    data: list[T]
    total: int
    has_more: bool

# Protocol for structural typing — no inheritance required
class Repository(Protocol):
    async def find_by_id(self, id: str) -> dict | None: ...
    async def save(self, entity: dict) -> None: ...

# Any class with matching methods satisfies Repository — no explicit subclassing

# Literal types for fixed values
Status = Literal["active", "inactive", "suspended"]

def update_status(user_id: str, status: Status) -> None:
    ...  # type checker rejects update_status("x", "invalid")

# TypeVar for generic functions
T = TypeVar("T")

def first_or_none(items: list[T]) -> T | None:
    return items[0] if items else None

# @overload for functions with multiple signatures
@overload
def fetch(id: str, *, required: Literal[True]) -> User: ...
@overload
def fetch(id: str, *, required: Literal[False] = ...) -> User | None: ...

def fetch(id: str, *, required: bool = False) -> User | None:
    user = db.get(id)
    if user is None and required:
        raise UserNotFoundError(id)
    return user
```

- Run `mypy --strict` in CI — no exceptions
- Use `TypedDict` for external data shapes (API payloads, JSON config)
- `Protocol` for structural typing — enables dependency inversion without inheritance
- `Literal` for restricted string/int values — catches typos at type-check time
- `@overload` for functions whose return type depends on input values
- All function signatures fully annotated — including `-> None` for void returns

## Performance

```python
import functools
import asyncio
from multiprocessing import Pool
from dataclasses import dataclass

# Generator expressions for large data — avoid materializing full list
def process_large_file(path: Path) -> int:
    # Generator: O(1) memory regardless of file size
    return sum(1 for line in open(path) if "ERROR" in line)
    # NOT: len([line for line in open(path) if "ERROR" in line])  # O(n) memory

# __slots__ for classes with many instances — 40-50% memory savings
@dataclass(slots=True)
class Point:
    x: float
    y: float
    z: float

# Without slots: each instance has a __dict__ (~200 bytes overhead)
# With slots: no __dict__, fields stored directly (~64 bytes per instance)

# functools.lru_cache for expensive pure functions
@functools.lru_cache(maxsize=256)
def fibonacci(n: int) -> int:
    if n < 2:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)

# For methods, use functools.cached_property
class Config:
    @functools.cached_property
    def parsed(self) -> dict:
        return toml.loads(self._raw_content)

# asyncio for I/O-bound concurrency
async def fetch_all(urls: list[str]) -> list[Response]:
    async with aiohttp.ClientSession() as session:
        tasks = [session.get(url) for url in urls]
        return await asyncio.gather(*tasks)

# multiprocessing for CPU-bound work
def process_images(paths: list[Path]) -> list[Result]:
    with Pool() as pool:
        return pool.map(resize_image, paths)
```

- Generator expressions over list comprehensions when you don't need the full list
- `__slots__` (or `@dataclass(slots=True)`) for data classes with many instances
- `functools.lru_cache` for pure functions — set `maxsize` to bound memory
- `asyncio` for I/O-bound work (HTTP, DB, file I/O) — never block the event loop
- `multiprocessing.Pool` for CPU-bound work (image processing, computation)
- Avoid global mutable state — it breaks multiprocessing and makes testing painful

## ML-Specific Patterns

```python
import numpy as np
import torch
from contextlib import contextmanager

# NumPy vectorization — 100x faster than Python loops
def normalize(data: np.ndarray) -> np.ndarray:
    # Vectorized: operates on entire array at C speed
    return (data - data.mean(axis=0)) / data.std(axis=0)
    # NOT: [[(x - mean) / std for x in row] for row in data]  # Python loop — slow

# Batch processing for model inference
def predict_batch(
    model: torch.nn.Module,
    inputs: list[np.ndarray],
    batch_size: int = 32,
) -> list[np.ndarray]:
    results: list[np.ndarray] = []
    for i in range(0, len(inputs), batch_size):
        batch = torch.tensor(np.stack(inputs[i : i + batch_size]))
        with torch.no_grad():
            output = model(batch)
        results.extend(output.cpu().numpy())
    return results

# GPU memory management — explicit cleanup with context managers
@contextmanager
def gpu_scope(device: str = "cuda:0"):
    """Context manager for GPU operations with cleanup."""
    try:
        torch.cuda.set_device(device)
        yield
    finally:
        torch.cuda.empty_cache()
        if torch.cuda.is_available():
            torch.cuda.synchronize()

# Usage:
with gpu_scope():
    results = predict_batch(model, data)

# Data pipeline with generator chains — process streaming data in constant memory
def load_data(path: Path):
    """Generator: yields one record at a time."""
    for line in open(path):
        yield json.loads(line)

def filter_valid(records):
    """Generator: filters without materializing."""
    for record in records:
        if record.get("status") == "active":
            yield record

def transform(records):
    """Generator: transforms without materializing."""
    for record in records:
        yield {
            "id": record["id"],
            "features": extract_features(record),
        }

# Chain generators — entire pipeline runs in O(1) memory
pipeline = transform(filter_valid(load_data("data.jsonl")))
for batch in batched(pipeline, 1000):
    process(batch)

# Reproducibility — seed everything
def set_seeds(seed: int = 42) -> None:
    import random
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    # For fully deterministic behavior:
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

# Model versioning and experiment tracking
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class ExperimentConfig:
    model_name: str
    learning_rate: float
    batch_size: int
    epochs: int
    seed: int = 42
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_artifact_path(self) -> Path:
        return Path(f"runs/{self.model_name}/{self.timestamp}")
```

- NumPy vectorization over Python loops — 10-100x speedup for array operations
- Batch processing for inference — amortizes overhead, controls memory usage
- GPU memory management: explicit `torch.cuda.empty_cache()`, context managers for scope
- Generator chains for data pipelines — process terabytes in constant memory
- Seed everything for reproducibility: `random`, `numpy`, `torch`, and CUDA
- Track experiments: config dataclass, artifact paths, versioned outputs

## Rules
- Never `import *`
- Prefer `pathlib.Path` over `os.path`
- Use `__slots__` on hot dataclasses
- `uv` or `poetry` for dependency management — not bare pip
- 88-char line length (Black default)
