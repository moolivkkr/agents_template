"""harness: the shared helper testing/test-case-traceability.md's TEST-CHANGE example moved its envelope
assertions into (tests/helpers.py in the doc)."""
from __future__ import annotations

from typing import Any


def assert_order_envelope(resp: Any) -> None:
    body = resp.json()
    assert set(body) == {"data", "meta"}, body
    assert body["meta"]["request_id"], body
    assert {"id", "sku", "quantity"} <= set(body["data"]), body
