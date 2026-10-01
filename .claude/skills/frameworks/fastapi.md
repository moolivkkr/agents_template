# FastAPI patterns for Python async HTTP APIs.

> Python samples checked 2026-09-30 on Python 3.12.8 with pyright 1.1.414 (`tests/archetype-compile/python/run.sh`): type-checked, imported, and the app run through TestClient (lifespan, the user route in the envelope, the error handler, request-model validation). FastAPI 0.142.2, Starlette 1.7.0, Pydantic 2.13.5, email-validator 2.3.0.

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

@router.get("/{user_id}", response_model=Envelope[UserResponse])
async def get_user(
    user_id: UUID,
    request: Request,
    service: Annotated[UserService, Depends(get_user_service)],
    current_user: Annotated[User, Depends(require_auth)],
) -> Envelope[UserResponse]:
    # The tenant comes from the verified token, never from the client: another tenant's user is a 404
    user = await service.get(tenant_id=current_user.tenant_id, user_id=user_id)
    return Envelope(data=UserResponse.model_validate(user), meta=Meta(request_id=request.state.request_id))
```
- One router per resource group
- `response_model` on every endpoint — the envelope around an explicit output schema (`Envelope[T]`,
  `ListEnvelope[T]` for lists: `api/response-envelope.md`, models in
  `backend/archetypes/crud-handler-python.md`)
- No business logic in route functions — call service via `Depends`

## Dependency Injection
```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session

async def get_user_service(db: Annotated[AsyncSession, Depends(get_db)]) -> UserService:
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
- `EmailStr` needs the `email-validator` package (`pydantic[email]`)

## Error Handling
```python
@app.exception_handler(UserNotFoundError)
async def user_not_found_handler(request: Request, exc: UserNotFoundError) -> JSONResponse:
    # The one error envelope (api/response-envelope.md); the exception text stays in the logs
    return JSONResponse(status_code=404, content={"error": {
        "code": "NOT_FOUND",
        "message": "User not found.",
        "request_id": request.state.request_id,
        "retryable": False,
    }})
```
- Map domain exceptions to HTTP responses in exception handlers — every body is the error envelope;
  a whole app maps its `AppError` hierarchy in one place (`backend/archetypes/error-handling-python.md`)
- Never raise `HTTPException` from service layer — only from route handlers

## Rules
- `async def` route functions call only async I/O; a blocking call (a sync driver or SDK) inside one
  blocks the event loop. Make such a route a plain `def` (FastAPI runs it in a threadpool) or wrap the
  call in `run_in_threadpool`
- Use `Annotated[X, Depends(...)]` over `X = Depends(...)` (cleaner)
- Background tasks via `BackgroundTasks` — not fire-and-forget coroutines
- Middleware for cross-cutting concerns (request ID, logging, CORS)
