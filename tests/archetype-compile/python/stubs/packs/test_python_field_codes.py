"""harness: pydantic's own error types, produced by a real model, reach the wire through languages/python.md's
request_validation_handler as the envelope's closed details[].code set."""
from datetime import date
from enum import Enum
from typing import Literal
from uuid import UUID

import pydantic
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, Field

from harness_stubs.py_fastapi_main import app


class Color(Enum):
    RED = "red"


class Probe(BaseModel):
    model_config = ConfigDict(extra="forbid")
    req: str
    short: str = Field("ok", min_length=2)
    long: str = Field("ok", max_length=3)
    items: list[str] = Field(["x"], min_length=1)
    ge: int = Field(5, ge=1)
    gt: int = Field(5, gt=0)
    le: int = Field(5, le=10)
    lt: int = Field(5, lt=10)
    mult: int = Field(4, multiple_of=2)
    num: int = 1
    flt: float = 1.0
    flag: bool = True
    tags: list[str] = []
    meta: dict[str, str] = {}
    uid: UUID = UUID(int=1)
    pattern: str = Field("AB", pattern=r"^[A-Z]+$")
    when: date = date(2026, 1, 1)
    color: Color = Color.RED
    kind: Literal["a", "b"] = "a"


@app.post("/probe")
async def probe(body: Probe) -> dict[str, str]:
    return {"ok": "yes"}


BAD = {"short": "a", "long": "abcd", "items": [], "ge": 0, "gt": 0, "le": 11, "lt": 10, "mult": 3, "num": "x",
       "flt": "y", "flag": "maybe", "tags": "nope", "meta": 5, "uid": "not-a-uuid", "pattern": "ab",
       "when": "2026-13-45", "color": "blue", "kind": "c", "extra": 1}
NATIVE = {"req": "missing", "short": "string_too_short", "long": "string_too_long", "items": "too_short",
          "ge": "greater_than_equal", "gt": "greater_than", "le": "less_than_equal", "lt": "less_than",
          "mult": "multiple_of", "num": "int_parsing", "flt": "float_parsing", "flag": "bool_parsing",
          "tags": "list_type", "meta": "dict_type", "uid": "uuid_parsing", "pattern": "string_pattern_mismatch",
          "when": "date_from_datetime_parsing", "color": "enum", "kind": "literal_error", "extra": "extra_forbidden"}
WIRE = {"req": "required", "short": "too_short", "long": "too_long", "items": "too_short", "ge": "out_of_range",
        "gt": "out_of_range", "le": "out_of_range", "lt": "out_of_range", "mult": "out_of_range",
        "num": "invalid_type", "flt": "invalid_type", "flag": "invalid_type", "tags": "invalid_type",
        "meta": "invalid_type", "uid": "invalid_format", "pattern": "invalid_format",
        "when": "invalid_value",  # pydantic's date_from_datetime_parsing isn't in the table: the fallback
        "color": "invalid_value", "kind": "invalid_value", "extra": "unknown_field"}
CLOSED = {"required", "invalid_type", "invalid_format", "invalid_value", "out_of_range", "too_short", "too_long",
          "unknown_field", "invalid_cursor", "already_exists"}


def test_pydantic_native_types_are_what_the_table_maps() -> None:
    try:
        Probe.model_validate(BAD)
    except pydantic.ValidationError as exc:
        native = {str(e["loc"][0]): e["type"] for e in exc.errors()}
    else:
        raise AssertionError("expected a ValidationError")
    assert native == NATIVE, native


def test_wire_codes_are_the_closed_set() -> None:
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post("/probe", headers={"Authorization": "Bearer tok-a"}, json=BAD)
    assert resp.status_code == 400, resp.text
    err = resp.json()["error"]
    assert err["code"] == "VALIDATION_FAILED"
    wire = {d["field"]: d["code"] for d in err["details"]}
    assert wire == WIRE, wire
    assert set(wire.values()) <= CLOSED
    assert all(d["message"].startswith(("This ", "Choose ")) for d in err["details"]), err["details"]
