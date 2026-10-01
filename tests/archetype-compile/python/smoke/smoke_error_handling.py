# harness smoke: register_exception_handlers writes the one error envelope (api/response-envelope.md)
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.errors import NotFoundError, RateLimitError, UnavailableError
from app.errors.handlers import register_exception_handlers

app = FastAPI()
register_exception_handlers(app)


@app.get("/nf")
async def nf() -> None:
    raise NotFoundError("Widget")


@app.get("/rl")
async def rl() -> None:
    raise RateLimitError(3)


@app.get("/down")
async def down() -> None:
    raise UnavailableError("postgres", cause=TimeoutError("statement timeout"))


@app.get("/boom")
async def boom() -> None:
    raise RuntimeError("secret internals")


@app.get("/q")
async def q(limit: int) -> dict[str, int]:
    return {"limit": limit}


c = TestClient(app, raise_server_exceptions=False)
r = c.get("/nf")
body = r.json()
assert r.status_code == 404, r.text
assert body == {"error": {"code": "NOT_FOUND", "message": "Widget not found.",
                          "request_id": r.headers["x-request-id"], "retryable": False}}, body
r = c.get("/rl")
assert r.status_code == 429 and r.headers["retry-after"] == "3" and r.json()["error"]["retryable"] is True, r.text
r = c.get("/down")
assert r.status_code == 503 and "postgres" not in r.text and "timeout" not in r.text, r.text
r = c.get("/boom")
assert r.status_code == 500 and "secret" not in r.text and r.json()["error"]["code"] == "INTERNAL", r.text
r = c.get("/q?limit=x")
assert r.status_code == 400, r.text
assert r.json()["error"]["details"] == [{"field": "limit", "code": "invalid_type", "message": "Must be a whole number."}], r.text
r = c.get("/missing")
assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND", r.text
r = c.post("/nf")
assert r.status_code == 400 and r.json()["error"]["code"] == "MALFORMED_REQUEST", r.text  # 405 → re-shaped by status

# details[].code: pydantic's own error types are mapped onto the closed set in api/response-envelope.md
from enum import Enum  # noqa: E402
from typing import Literal  # noqa: E402
from datetime import date, datetime  # noqa: E402
from uuid import UUID  # noqa: E402

from pydantic import BaseModel, ConfigDict, Field, field_validator  # noqa: E402

CLOSED_SET = {"required", "invalid_type", "invalid_format", "invalid_value", "out_of_range", "too_short",
              "too_long", "unknown_field", "invalid_cursor", "already_exists"}


class Color(str, Enum):
    RED = "red"


class Probe(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=5)
    count: int = Field(ge=1, le=10)
    owner: UUID
    color: Color
    kind: Literal["a", "b"]
    tags: list[str] = Field(default_factory=list, max_length=2)
    nickname: str | None = None
    due: date | None = None
    at: datetime | None = None

    @field_validator("nickname")
    @classmethod
    def not_reserved(cls, v: str | None) -> str | None:
        if v == "admin":
            raise ValueError("internal: reserved by tenant 42")  # value_error: no closer code → invalid_value
        return v


@app.post("/probe")
async def probe(body: Probe) -> dict[str, str]:
    return {"name": body.name}


VALID = {"name": "abc", "count": 5, "owner": "6f1c8c2e-7a5b-4d0e-9b1a-3c2d1e0f9a8b", "color": "red", "kind": "a"}
CASES = [  # (field overrides, field, expected code)
    ({"name": None}, "name", "required"),  # key removed below
    ({"name": "a"}, "name", "too_short"),
    ({"name": "abcdefg"}, "name", "too_long"),
    ({"count": 0}, "count", "out_of_range"),
    ({"count": 11}, "count", "out_of_range"),
    ({"count": "many"}, "count", "invalid_type"),
    ({"owner": "not-a-uuid"}, "owner", "invalid_format"),
    ({"color": "blue"}, "color", "invalid_value"),
    ({"kind": "c"}, "kind", "invalid_value"),
    ({"tags": ["x", "y", "z"]}, "tags", "too_long"),
    ({"surprise": 1}, "surprise", "unknown_field"),
    ({"nickname": "admin"}, "nickname", "invalid_value"),
    ({"due": "2026-13-45"}, "due", "invalid_format"),  # pydantic: date_from_datetime_parsing
    ({"at": "yesterday"}, "at", "invalid_format"),  # pydantic: datetime_from_date_parsing
]
for overrides, field, expected in CASES:
    payload = {**VALID, **overrides}
    if overrides == {"name": None}:
        del payload["name"]
    r = c.post("/probe", json=payload)
    assert r.status_code == 400, (overrides, r.text)
    details = r.json()["error"]["details"]
    assert [(d["field"], d["code"]) for d in details] == [(field, expected)], (overrides, details)
    assert "internal" not in r.text and "tenant 42" not in r.text, r.text  # the validator's text never leaks
seen = {code for _, _, code in CASES}
assert seen <= CLOSED_SET, seen - CLOSED_SET
print(f"details[].code: {len(CASES)} pydantic errors mapped onto {sorted(seen)}")
