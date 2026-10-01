# testing/test-case-traceability.md's TEST-CHANGE fragment: the moved assertion runs on a real response.
from fastapi.testclient import TestClient

from docs_fragments.test_change import _fragment
from tests.conftest import VALID_ORDER, _app, auth

resp = TestClient(_app()).post("/orders", json=VALID_ORDER, headers=auth("tok-alice"))
assert resp.status_code == 201, resp.text
_fragment(resp)
