# frameworks/fastapi.md: main.py's app with the users router, the DI chain and the UserNotFoundError
# handler, run through TestClient (lifespan included). Wiring the doc leaves to the app: the archetype's
# request-id middleware and AppError handlers (error-handling-python.md).
from datetime import datetime, timezone
from uuid import uuid4

import pydantic
from fastapi.testclient import TestClient

import errors_handler  # noqa: F401 — registers the doc's handler on main.app
from app.errors.handlers import register_exception_handlers
from app.middleware.request_id import RequestIDMiddleware
from harness_stubs.fastapi_app import TENANT_A, TENANT_B, USERS, User, db
from main import app
from users.schemas import CreateUserRequest

app.add_middleware(RequestIDMiddleware)
register_exception_handlers(app)
mine = User(uuid4(), TENANT_A, "me@example.com", datetime.now(timezone.utc))
theirs = User(uuid4(), TENANT_B, "other@example.com", datetime.now(timezone.utc))
USERS.update({mine.id: mine, theirs.id: theirs})
auth = {"Authorization": "Bearer tok-a"}

with TestClient(app) as client:
    assert db.events == ["connect"], db.events  # the lifespan ran its startup half
    r = client.get(f"/api/v1/users/{mine.id}", headers={**auth, "X-Request-Id": "rid-1"})
    assert r.status_code == 200, r.text
    assert r.json() == {"data": {"id": str(mine.id), "email": "me@example.com",
                                 "created_at": mine.created_at.isoformat().replace("+00:00", "Z")},
                        "meta": {"request_id": "rid-1"}}, r.json()
    # another tenant's user and a missing one: the same 404 envelope, no exception text
    for uid in (theirs.id, uuid4()):
        r = client.get(f"/api/v1/users/{uid}", headers={**auth, "X-Request-Id": "rid-2"})
        assert r.status_code == 404, r.text
        assert r.json() == {"error": {"code": "NOT_FOUND", "message": "User not found.", "request_id": "rid-2",
                                      "retryable": False}}, r.json()
    r = client.get(f"/api/v1/users/{mine.id}")
    assert r.status_code == 401 and r.json()["error"]["code"] == "UNAUTHENTICATED", r.text
    assert "/api/v1/users/{user_id}" in app.openapi()["paths"]
assert db.events == ["connect", "disconnect"], db.events

CreateUserRequest(email="ok@example.com", password="long-enough")
for bad in ({"email": "not-an-email", "password": "long-enough"}, {"email": "ok@example.com", "password": "short"}):
    try:
        CreateUserRequest.model_validate(bad)
    except pydantic.ValidationError:
        pass
    else:
        raise AssertionError(f"accepted {bad}")
