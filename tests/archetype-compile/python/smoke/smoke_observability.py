# harness smoke: run observability-python.md's app (lifespan → instrument_app, middleware stack) and
# check the rules its prose states: one http.server.request.duration series per route TEMPLATE, from
# ONE source (MetricsMiddleware), a server span per request, the request id echoed, sensitive keys
# redacted in the structlog output.
import io
import logging

import structlog
from fastapi.testclient import TestClient
from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind

# Read metrics and spans in-process. configure_metrics()/configure_tracing() later try to set their
# own providers; OTel keeps the first one, so the proxies created at import report here.
reader = InMemoryMetricReader()
metrics.set_meter_provider(MeterProvider(metric_readers=[reader]))
spans = InMemorySpanExporter()
tracer_provider = TracerProvider()
tracer_provider.add_span_processor(SimpleSpanProcessor(spans))
trace.set_tracer_provider(tracer_provider)

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
    c.get("/healthz")  # probe traffic: skipped by MetricsMiddleware (else a series without http.route)
    c.get("/readyz")

logged = buf.getvalue()
assert "order_read" in logged and "hunter2" not in logged and "Bearer x" not in logged, logged
assert "[REDACTED]" in logged, logged

routes: set[object] = set()
sources: set[str] = set()
for rm in reader.get_metrics_data().resource_metrics:
    for sm in rm.scope_metrics:
        for m in sm.metrics:
            if m.name == "http.server.request.duration":
                sources.add(sm.scope.name)
                for dp in m.data.data_points:
                    routes.add(dp.attributes.get("http.route"))
assert routes == {"/api/v1/orders/{order_id}"}, routes
assert sources == {"order-service"}, sources  # MetricsMiddleware only: no second (native FastAPI) series

server = [sp for sp in spans.get_finished_spans() if sp.kind == SpanKind.SERVER]
server_routes = {(sp.attributes or {}).get("http.route") for sp in server}
assert server_routes == {"/api/v1/orders/{order_id}"}, [(sp.name, sp.attributes) for sp in server]
assert len(server) == 3, [sp.name for sp in server]  # the three order requests; probes excluded

assert redact_sensitive({"password": "p", "nested": {"api_key": "k"}, "rows": [{"token": "t"}], "ok": 1}) == {
    "password": "[REDACTED]", "nested": {"api_key": "[REDACTED]"}, "rows": [{"token": "[REDACTED]"}], "ok": 1}
