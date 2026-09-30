# harness smoke: auth-middleware-python.md's create_app() with the real widgets router, settings, JWT
# dependency (real PyJWT), middleware stack and error handlers. Only the service is replaced (it needs
# a database). The doc's own tests (tests/test_auth.py) cover issuer/audience, settings and the limiter.
import logging
import time
import uuid

import jwt
from fastapi import Depends
from fastapi.testclient import TestClient

from app.api.v1.widgets import get_widget_service
from app.config import settings
from app.dependencies.auth import require_role
from app.domain.widget import Widget
from app.main import create_app

TENANT = uuid.uuid4()


class FakeService:
    async def get(self, *, tenant_id: uuid.UUID, widget_id: uuid.UUID) -> Widget:
        return Widget(id=widget_id, tenant_id=tenant_id, name="w")


app = create_app()
app.dependency_overrides[get_widget_service] = lambda: FakeService()


@app.get("/admin-only", dependencies=[Depends(require_role("admin"))])
async def admin_only() -> dict[str, bool]:
    return {"ok": True}


def token(**over: object) -> str:
    claims = {"sub": str(uuid.uuid4()), "tenant_id": str(TENANT), "roles": ["user"],
              "iss": settings.jwt_issuer, "aud": settings.jwt_audience, "exp": int(time.time()) + 300}
    claims.update(over)
    return jwt.encode(claims, settings.jwt_secret_key, algorithm="HS256")


class Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


access = Capture()
logging.getLogger("app.access").addHandler(access)
logging.getLogger("app.access").setLevel(logging.INFO)

c = TestClient(app, raise_server_exceptions=False)
wid = uuid.uuid4()
url = f"/api/v1/widgets/{wid}"
origin = {"Origin": "http://localhost:3000"}

r = c.get(url, headers={"Authorization": f"Bearer {token()}", **origin})
assert r.status_code == 200, r.text
assert r.json()["data"]["tenant_id"] == str(TENANT) and r.headers["x-request-id"], r.text
assert r.headers["x-ratelimit-limit"] == "200", r.headers  # the limiter ran, as a dependency

for name, bad in (
    ("no token", {}),
    ("expired", {"Authorization": f"Bearer {token(exp=int(time.time()) - 10)}"}),
    ("wrong audience", {"Authorization": f"Bearer {token(aud='someone-else')}"}),
    ("garbage", {"Authorization": "Bearer not.a.jwt"}),
):
    r = c.get(url, headers={**bad, **origin})
    assert r.status_code == 401, (name, r.status_code, r.text)
    assert r.json()["error"]["code"] == "UNAUTHENTICATED", (name, r.text)
    assert r.headers.get("www-authenticate") == "Bearer", (name, r.headers)
    # an error response still carries the CORS headers the browser needs to read it
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000", (name, r.headers)

# preflight is answered by CORS before anything else runs
r = c.options(url, headers={**origin, "Access-Control-Request-Method": "GET",
                            "Access-Control-Request-Headers": "Authorization"})
assert r.status_code == 200 and r.headers["access-control-allow-origin"] == "http://localhost:3000", r.headers

# the access log line carries the request id (AccessLog runs inside RequestID)
logged = [rec for rec in access.records if getattr(rec, "path", "") == url]
assert logged and all(getattr(rec, "request_id", "") for rec in logged), [vars(x) for x in logged]

r = c.get("/admin-only", headers={"Authorization": f"Bearer {token()}"})
assert r.status_code == 403 and r.json()["error"]["code"] == "FORBIDDEN", r.text
r = c.get("/admin-only", headers={"Authorization": f"Bearer {token(roles=['admin'])}"})
assert r.status_code == 200, r.text
