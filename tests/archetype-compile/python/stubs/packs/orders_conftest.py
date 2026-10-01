"""harness: the app-level fixtures and helpers testing/test-case-traceability.md's tests use — a tiny
orders API (bearer auth, per-user ownership: another user's order is 404, never 403), a TestClient, two
users and an order owned by the second."""
from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

VALID_ORDER = {"sku": "W-1", "quantity": 2}
_TOKENS = {"tok-alice": "alice", "tok-bob": "bob"}
_ORDERS: dict[str, dict[str, Any]] = {}


def _err(status: int, code: str) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": code, "request_id": "r", "retryable": False}}, status)


def _app() -> FastAPI:
    app = FastAPI()

    @app.post("/orders")
    def create(body: dict[str, Any], authorization: str | None = Header(None)) -> Any:
        user = _TOKENS.get((authorization or "").removeprefix("Bearer "))
        if user is None:
            return _err(401, "UNAUTHENTICATED")
        order = {"id": str(uuid4()), "owner": user, **body}
        _ORDERS[order["id"]] = order
        return JSONResponse({"data": order, "meta": {"request_id": "r"}}, 201)

    @app.get("/orders/{order_id}")
    def get(order_id: str, authorization: str | None = Header(None)) -> Any:
        user = _TOKENS.get((authorization or "").removeprefix("Bearer "))
        if user is None:
            return _err(401, "UNAUTHENTICATED")
        order = _ORDERS.get(order_id)
        if order is None or order["owner"] != user:
            return _err(404, "NOT_FOUND")
        return {"data": order, "meta": {"request_id": "r"}}

    return app


def auth(token: str | None) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"} if token else {}


@pytest.fixture
def client() -> TestClient:
    return TestClient(_app())


@pytest.fixture
def alice() -> str:
    return "tok-alice"


@pytest.fixture
def bob_order(client: TestClient) -> Any:
    class _Order:
        id = client.post("/orders", json=VALID_ORDER, headers=auth("tok-bob")).json()["data"]["id"]
    return _Order
