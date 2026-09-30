# harness smoke: run observability-python.md's app (lifespan → instrument_app, middleware stack) and
# check the rules its prose states: one http.server.request.duration series per route TEMPLATE, the
# request id echoed, sensitive keys redacted in the structlog output.
import io
import logging

import structlog
from fastapi.testclient import TestClient
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader

# Read the metrics in-process. configure_metrics() later tries to set its own provider; OTel keeps
# the first one, so its instruments (created as proxies at import) report here.
reader = InMemoryMetricReader()
metrics.set_meter_provider(MeterProvider(metric_readers=[reader]))

from app.main import app  # noqa: E402
from app.observability.logging import redact_sensitive  # noqa: E402


@app.get("/api/v1/orders/{order_id}")
async def get_order(order_id: str) -> dict[str, str]:
    structlog.get_logger().info("order_read", password="hunter2", nested={"Authorization": "Bearer x"})
    return {"id": order_id}


auth = {"Authorization": "Bearer harness-token"}
with TestClient(app) as c:
    root = logging.getLogger()
    buf = io.StringIO()
    for h in root.handlers:
        if isinstance(h, logging.StreamHandler):
            h.setStream(buf)
    for oid in ("123", "456"):
        r = c.get(f"/api/v1/orders/{oid}", headers={**auth, "X-Request-ID": "req-abcdefgh"})
        assert r.status_code == 200, r.text
        assert r.headers["x-request-id"] == "req-abcdefgh", r.headers
    r = c.get("/api/v1/orders/789", headers={**auth, "X-Request-ID": "bad\nid"})
    assert r.headers["x-request-id"].startswith("req_"), r.headers  # invalid inbound id replaced

logged = buf.getvalue()
assert "order_read" in logged and "hunter2" not in logged and "Bearer x" not in logged, logged
assert "[REDACTED]" in logged, logged

routes: set[object] = set()
for rm in reader.get_metrics_data().resource_metrics:
    for sm in rm.scope_metrics:
        for m in sm.metrics:
            if m.name == "http.server.request.duration":
                for dp in m.data.data_points:
                    routes.add(dp.attributes.get("http.route"))
assert routes == {"/api/v1/orders/{order_id}"}, routes

assert redact_sensitive({"password": "p", "nested": {"api_key": "k"}, "rows": [{"token": "t"}], "ok": 1}) == {
    "password": "[REDACTED]", "nested": {"api_key": "[REDACTED]"}, "rows": [{"token": "[REDACTED]"}], "ok": 1}
