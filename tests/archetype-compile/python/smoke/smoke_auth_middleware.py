# harness smoke: auth-middleware-python.md's create_app() with the real widgets router, JWT dependency
# (real PyJWT), middleware stack and error handlers. Only the service is replaced (it needs a database).
import os
import time
import uuid

import jwt
from fastapi import Depends
from fastapi.testclient import TestClient

from app.api.v1.widgets import get_widget_service
from app.dependencies.auth import require_role
from app.domain.widget import Widget
from app.main import create_app

KEY = os.environ["JWT_SECRET_KEY"]
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
              "iss": "widget-api", "aud": "widget-api", "exp": int(time.time()) + 300}
    claims.update(over)
    return jwt.encode(claims, KEY, algorithm="HS256")


c = TestClient(app, raise_server_exceptions=False)
wid = uuid.uuid4()
url = f"/api/v1/widgets/{wid}"

r = c.get(url, headers={"Authorization": f"Bearer {token()}"})
assert r.status_code == 200, r.text
assert r.json()["data"]["tenant_id"] == str(TENANT) and r.headers["x-request-id"], r.text

for name, bad in (
    ("no token", {}),
    ("expired", {"Authorization": f"Bearer {token(exp=int(time.time()) - 10)}"}),
    ("wrong audience", {"Authorization": f"Bearer {token(aud='someone-else')}"}),
    ("garbage", {"Authorization": "Bearer not.a.jwt"}),
):
    r = c.get(url, headers=bad)
    assert r.status_code == 401, (name, r.status_code, r.text)
    assert r.json()["error"]["code"] == "UNAUTHENTICATED", (name, r.text)
    assert r.headers.get("www-authenticate") == "Bearer", (name, r.headers)

r = c.get("/admin-only", headers={"Authorization": f"Bearer {token()}"})
assert r.status_code == 403 and r.json()["error"]["code"] == "FORBIDDEN", r.text
r = c.get("/admin-only", headers={"Authorization": f"Bearer {token(roles=['admin'])}"})
assert r.status_code == 200, r.text
