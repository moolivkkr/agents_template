"""harness: requests through languages/python.md's FastAPI blocks (tenant dependency + middleware, error
hierarchy + handlers, the users DI chain) and the SQLAlchemy tenant filter on SQLite."""
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import String, create_engine, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from app.db_tenant import TenantScoped, current_tenant
from harness_stubs.py_fastapi import ORDERS, TENANT_A, TENANT_B, OrderRow, now
from harness_stubs.py_fastapi_main import app

A = {"Authorization": "Bearer tok-a"}
MULTI = {"Authorization": "Bearer tok-multi"}


@pytest.fixture(scope="module")
def client():
    t0 = now()
    ORDERS[:] = [OrderRow(uuid4(), TENANT_A, 100 + i, t0 + timedelta(seconds=i)) for i in range(3)]
    ORDERS.append(OrderRow(uuid4(), TENANT_B, 999, t0))
    return TestClient(app, raise_server_exceptions=False)


def _error(resp, status, code):
    assert resp.status_code == status, resp.text
    body = resp.json()
    assert set(body) == {"error"} and body["error"]["code"] == code, body
    assert set(body["error"]) <= {"code", "message", "details", "request_id", "retryable"}, body
    assert body["error"]["request_id"] == resp.headers["x-request-id"]
    return body["error"]


def test_orders_cursor_pages_in_the_envelope(client):
    first = client.get("/orders?limit=2", headers=A).json()
    assert [o["total_cents"] for o in first["data"]] == [102, 101]
    page = first["meta"]["pagination"]
    assert page["has_more"] is True and page["limit"] == 2 and page["next_cursor"]
    second = client.get(f"/orders?limit=2&cursor={page['next_cursor']}", headers=A).json()
    assert [o["total_cents"] for o in second["data"]] == [100]
    assert second["meta"]["pagination"] == {"next_cursor": None, "has_more": False, "limit": 2}
    assert second["meta"]["request_id"]


def test_header_only_selects_a_tenant_the_token_lists(client):
    assert [o["total_cents"] for o in client.get("/orders", headers={**MULTI, "X-Tenant-ID": str(TENANT_B)}).json()["data"]] == [999]
    _error(client.get("/orders", headers={**A, "X-Tenant-ID": str(TENANT_B)}), 403, "FORBIDDEN")
    _error(client.get("/orders", headers={**MULTI, "X-Tenant-ID": str(uuid4())}), 403, "FORBIDDEN")


def test_missing_credentials_are_401_with_www_authenticate(client):
    resp = client.get("/orders")
    _error(resp, 401, "UNAUTHENTICATED")
    assert resp.headers["www-authenticate"] == "Bearer"


def test_limit_out_of_range_is_400_validation_failed(client):
    for bad, code in (("0", "too_small"), ("101", "too_large"), ("x", "invalid")):
        err = _error(client.get(f"/orders?limit={bad}", headers=A), 400, "VALIDATION_FAILED")
        assert err["details"][0]["field"] == "limit" and err["details"][0]["code"] == code, err


def test_http_errors_and_unhandled_errors_are_the_envelope(client):
    _error(client.get("/nope", headers=A), 404, "NOT_FOUND")
    resp = client.delete("/orders", headers=A)
    _error(resp, 405, "MALFORMED_REQUEST")
    assert "GET" in resp.headers["allow"]
    resp = client.get("/boom", headers=A)
    err = _error(resp, 500, "INTERNAL")
    assert "internal detail" not in resp.text and err["message"] == "Something went wrong."
    _error(client.post("/users", headers={**A, "Content-Type": "application/json"}, content=b"{not json"), 400,
           "MALFORMED_REQUEST")


def test_create_user_201_in_the_envelope(client):
    resp = client.post("/users", headers={**A, "X-Request-Id": "rid-9"}, json={"email": "n@example.com", "name": "N"})
    assert resp.status_code == 201, resp.text
    assert resp.json()["data"]["email"] == "n@example.com" and resp.json()["meta"] == {"request_id": "rid-9"}


def test_failed_commit_is_a_500_not_a_201(client, monkeypatch):
    async def fail(self):
        raise RuntimeError("commit failed")

    monkeypatch.setattr(AsyncSession, "commit", fail)
    _error(client.post("/users", headers=A, json={"email": "m@example.com", "name": "M"}), 500, "INTERNAL")


# ── the SQLAlchemy tenant filter (sync Session on SQLite; an AsyncSession runs the same Session) ──
class Base(DeclarativeBase):
    pass


class Doc(TenantScoped, Base):
    __tablename__ = "docs"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(20))


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        token = current_tenant.set(TENANT_A)  # writes don't go through the filter; reads do
        s.add_all([Doc(tenant_id=TENANT_A, name="a1"), Doc(tenant_id=TENANT_A, name="a2"),
                   Doc(tenant_id=TENANT_B, name="b1")])
        s.commit()
        s.expunge_all()  # later reads load from the database, through the filter
        current_tenant.reset(token)
        yield s
    engine.dispose()


def _as(tenant: UUID):
    return current_tenant.set(tenant)


def test_select_update_delete_only_touch_the_current_tenant(db):
    token = _as(TENANT_A)
    try:
        assert sorted(d.name for d in db.scalars(select(Doc))) == ["a1", "a2"]
        assert db.get(Doc, 3) is None  # b1, by primary key: filtered too
        db.execute(update(Doc).values(name="x"))
        db.execute(delete(Doc).where(Doc.name == "x"))
        db.commit()
    finally:
        current_tenant.reset(token)
    token = _as(TENANT_B)
    try:
        assert [d.name for d in db.scalars(select(Doc))] == ["b1"]  # B's row neither renamed nor deleted
    finally:
        current_tenant.reset(token)


def test_no_tenant_fails_closed(db):
    db.expunge_all()
    with pytest.raises(LookupError):
        db.scalars(select(Doc)).all()
