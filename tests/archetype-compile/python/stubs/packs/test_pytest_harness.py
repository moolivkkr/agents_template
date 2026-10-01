"""harness: uses testing/pytest.md's fixtures the doc's own tests don't (the module-scoped API client and
the autouse request-id reset)."""
from app.middleware.request_id import get_request_id


async def test_harness_api_client(api_client) -> None:
    resp = await api_client.get("/api/v1/widgets/")
    assert resp.status_code == 401, resp.text  # the crud-handler archetype's auth placeholder: always 401
    assert resp.json()["error"]["code"] == "UNAUTHENTICATED"
    assert resp.headers["x-request-id"]


def test_harness_request_context_is_set_for_every_test() -> None:
    assert get_request_id() == "test-request-id"
