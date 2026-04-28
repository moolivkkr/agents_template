# FastAPI patterns for Python async HTTP APIs.

## App Structure
```python
# main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()        # startup
    yield
    await db.disconnect()     # shutdown

app = FastAPI(lifespan=lifespan)
app.include_router(users.router, prefix="/api/v1/users")
app.include_router(auth.router, prefix="/api/v1/auth")
```

## Routers
```python
# users/router.py
router = APIRouter(tags=["users"])

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    service: UserService = Depends(get_user_service),
    current_user: User = Depends(require_auth),
) -> UserResponse:
    return await service.get(user_id)
```
- One router per resource group
- `response_model` on every endpoint — explicit output schema
- No business logic in route functions — call service via `Depends`

## Dependency Injection
```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session

async def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(UserRepository(db))
```
- `Depends()` for all service/repo construction
- Generator dependencies for resources needing cleanup (DB sessions)

## Request/Response Models
```python
class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)

class UserResponse(BaseModel):
    id: UUID
    email: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

## Error Handling
```python
@app.exception_handler(UserNotFoundError)
async def user_not_found_handler(request, exc):
    return JSONResponse(status_code=404, content={"error": str(exc)})
```
- Map domain exceptions to HTTP responses in exception handlers
- Never raise `HTTPException` from service layer — only from route handlers

## Rules
- `async def` for all route functions — never `def` (blocks event loop)
- Use `Annotated[X, Depends(...)]` over `X = Depends(...)` (cleaner)
- Background tasks via `BackgroundTasks` — not fire-and-forget coroutines
- Middleware for cross-cutting concerns (request ID, logging, CORS)
