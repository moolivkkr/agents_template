

# ── harness: the fixtures the doc's tests use but leave to the app's conftest — the REAL crud-service
# WidgetService over in-memory implementations of its protocols ─────────────────────────────────────
from app.services.widget import WidgetService  # noqa: E402
from harness_stubs.pytest_pack import UID, InMemoryAudit, InMemoryCache, InMemoryWidgetRepository  # noqa: E402


@pytest.fixture
def svc() -> WidgetService:
    return WidgetService(repo=InMemoryWidgetRepository(), cache=InMemoryCache(), audit_writer=InMemoryAudit())


@pytest.fixture
def widget_service(svc: WidgetService) -> WidgetService:
    return svc


@pytest.fixture
def user_id():
    return UID
