---
skill: observability-python
description: Python observability archetype — OpenTelemetry traces/metrics/logs for FastAPI, structlog JSON pipeline, auto-instrumentation (SQLAlchemy, Redis, httpx), Prometheus endpoint, tenant-aware context propagation
version: "1.0"
tags:
  - python
  - observability
  - opentelemetry
  - tracing
  - metrics
  - logging
  - structlog
  - fastapi
  - archetype
  - backend
---

# Observability Archetype — Python (FastAPI + OpenTelemetry)

> **Canonical reference**: This is the Python counterpart to `core/observability-patterns.md` (Go/TypeScript). All three produce identical metric names, span naming conventions, and required log fields so dashboards and alerts work across polyglot services.

Complete observability stack for Python backend services built on FastAPI. Every generated Python service MUST follow this pattern.

---

## Dependencies

```toml
# pyproject.toml — observability deps
[project]
dependencies = [
    # OpenTelemetry core
    "opentelemetry-api>=1.25.0",
    "opentelemetry-sdk>=1.25.0",
    "opentelemetry-exporter-otlp-proto-grpc>=1.25.0",

    # Auto-instrumentation
    "opentelemetry-instrumentation-fastapi>=0.46b0",
    "opentelemetry-instrumentation-sqlalchemy>=0.46b0",
    "opentelemetry-instrumentation-redis>=0.46b0",
    "opentelemetry-instrumentation-httpx>=0.46b0",
    "opentelemetry-instrumentation-logging>=0.46b0",

    # Structured logging
    "structlog>=24.1.0",

    # Prometheus (optional — if exposing /metrics directly)
    "prometheus-fastapi-instrumentator>=7.0.0",
]
```

---

## 1. Tracing

### 1.1 TracerProvider Setup

```python
# app/observability/tracing.py

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.config import settings


def configure_tracing() -> TracerProvider:
    """
    Initialise the global TracerProvider.

    Call once during application startup (in the FastAPI lifespan).
    """
    resource = Resource.create(
        {
            SERVICE_NAME: settings.SERVICE_NAME,
            SERVICE_VERSION: settings.SERVICE_VERSION,
            "deployment.environment": settings.ENVIRONMENT,
        }
    )

    provider = TracerProvider(resource=resource)

    if settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        exporter = OTLPSpanExporter(
            endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,
            insecure=settings.OTEL_EXPORTER_INSECURE,
        )
        provider.add_span_processor(
            BatchSpanProcessor(
                exporter,
                max_queue_size=2048,
                max_export_batch_size=512,
                schedule_delay_millis=5000,
            )
        )

    trace.set_tracer_provider(provider)
    return provider
```

### 1.2 Auto-Instrumentation

```python
# app/observability/instruments.py

from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.metrics import NoOpMeterProvider


def instrument_auto(app, engine=None):
    """
    Enable auto-instrumentation for FastAPI, SQLAlchemy, Redis, and httpx.

    Call after configure_tracing() in the FastAPI lifespan.
    """
    # FastAPI — creates root spans for every request
    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls="health,ready,metrics",
        # MetricsMiddleware (2.3) is the single source of HTTP server metrics; don't record a second set
        meter_provider=NoOpMeterProvider(),
    )

    # SQLAlchemy — wraps every query in a child span
    if engine is not None:
        SQLAlchemyInstrumentor().instrument(
            engine=engine,
            enable_commenter=True,  # adds /*traceparent=...*/ SQL comment
        )

    # Redis — wraps every command in a child span
    RedisInstrumentor().instrument()

    # httpx — wraps outbound HTTP calls and propagates trace context
    HTTPXClientInstrumentor().instrument()
```

### 1.3 Manual Spans in Services and Repositories

```python
# app/services/order_service.py

from opentelemetry import trace
from opentelemetry.trace import StatusCode

tracer = trace.get_tracer("order-service")


class OrderService:
    def __init__(self, repo: OrderRepository, payment_client: PaymentClient):
        self._repo = repo
        self._payment = payment_client

    async def create_order(self, ctx: RequestContext, req: CreateOrderRequest) -> Order:
        with tracer.start_as_current_span(
            "OrderService.create_order",
            attributes={
                "tenant_id": ctx.tenant_id,
                "user_id": ctx.user_id,
                "request_id": ctx.request_id,
            },
        ) as span:
            try:
                # Validation
                req.validate_business_rules()

                # Persist
                order = Order.from_request(req, tenant_id=ctx.tenant_id)
                await self._repo.save(ctx, order)

                # External call — trace context propagates automatically via httpx instrumentation
                charge = await self._payment.charge(ctx, order)

                span.set_attribute("order_id", str(order.id))
                span.set_attribute("order_total", float(order.total))

                # Span event for significant milestones
                span.add_event("order_created", attributes={
                    "order_id": str(order.id),
                    "payment_id": charge.id,
                })

                return order

            except Exception as exc:
                span.record_exception(exc)
                span.set_status(StatusCode.ERROR, str(exc))
                raise
```

### 1.4 Repository Spans

```python
# app/repositories/order_repository.py

from opentelemetry import trace
from opentelemetry.trace import StatusCode

tracer = trace.get_tracer("order-service")


class OrderRepository:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    async def save(self, ctx: RequestContext, order: Order) -> None:
        with tracer.start_as_current_span(
            "postgres.orders.insert",
            attributes={
                "db.system": "postgresql",
                "db.operation": "INSERT",
                "db.sql.table": "orders",
                "tenant_id": ctx.tenant_id,
            },
        ) as span:
            try:
                async with self._session_factory() as session:
                    session.add(order.to_model())
                    await session.commit()
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(StatusCode.ERROR, str(exc))
                raise

    async def find_by_id(self, ctx: RequestContext, order_id: str) -> Order | None:
        with tracer.start_as_current_span(
            "postgres.orders.select",
            attributes={
                "db.system": "postgresql",
                "db.operation": "SELECT",
                "db.sql.table": "orders",
                "tenant_id": ctx.tenant_id,
            },
        ) as span:
            async with self._session_factory() as session:
                result = await session.get(OrderModel, order_id)
                if result is None:
                    span.set_attribute("db.rows_affected", 0)
                    return None
                span.set_attribute("db.rows_affected", 1)
                return Order.from_model(result)
```

### 1.5 Span Attributes — Required Set

Every manual span MUST include these attributes where applicable:

| Attribute | Source | Required On |
|-----------|--------|-------------|
| `tenant_id` | RequestContext | ALL spans |
| `user_id` | RequestContext | Service spans |
| `request_id` | RequestContext | Root/service spans |
| `db.system` | Hardcoded | Repository spans |
| `db.operation` | Hardcoded | Repository spans |
| `db.sql.table` | Hardcoded | Repository spans |
| `order_id`, `entity_id` | Domain logic | After entity is created/resolved |

### 1.6 Context Propagation Through Async Calls

```python
# OpenTelemetry handles context propagation within the same process via
# contextvars automatically. For cross-service calls, inject trace context
# into outbound HTTP headers.

from opentelemetry.propagate import inject
import httpx


async def call_downstream(url: str, payload: dict, ctx: RequestContext) -> httpx.Response:
    """
    If using auto-instrumented httpx, trace context is injected automatically.
    For manual propagation (e.g., with raw aiohttp):
    """
    # No tenant header: the downstream authenticates THIS service (service token or mTLS) and takes the
    # tenant from that credential. A forwarded tenant header would be a spoofable authorization input.
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "X-Request-ID": ctx.request_id,
    }
    # Inject W3C Trace Context (traceparent, tracestate) into headers
    inject(headers)

    async with httpx.AsyncClient() as client:
        return await client.post(url, json=payload, headers=headers)
```

### 1.7 Span Naming Convention

Consistent naming across all Python services:

| Layer | Pattern | Example |
|-------|---------|---------|
| HTTP handler | `HTTP {METHOD} {path}` | `HTTP POST /api/v1/orders` |
| Service method | `{ServiceName}.{method_name}` | `OrderService.create_order` |
| Repository | `{system}.{table}.{operation}` | `postgres.orders.insert` |
| External call | `{service}.{endpoint}` | `payment-gateway.charge` |
| Background job | `job.{job_name}` | `job.send_invoice_email` |

---

## 2. Metrics

### 2.1 MeterProvider Setup

```python
# app/observability/metrics.py

from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.metrics.view import ExplicitBucketHistogramAggregation, View
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION

from app.config import settings

# OTel HTTP semconv buckets (seconds); the NFR latency threshold must be one of them
HTTP_DURATION_BUCKETS = [0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1, 2.5, 5, 7.5, 10]


def configure_metrics() -> MeterProvider:
    """
    Initialise the global MeterProvider.

    Call once during application startup (in the FastAPI lifespan).
    """
    resource = Resource.create(
        {
            SERVICE_NAME: settings.SERVICE_NAME,
            SERVICE_VERSION: settings.SERVICE_VERSION,
            "deployment.environment": settings.ENVIRONMENT,
        }
    )

    views = [
        View(
            instrument_name="http.server.request.duration",
            aggregation=ExplicitBucketHistogramAggregation(HTTP_DURATION_BUCKETS),
        )
    ]
    provider = MeterProvider(resource=resource, views=views)

    if settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        exporter = OTLPMetricExporter(
            endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,
            insecure=settings.OTEL_EXPORTER_INSECURE,
        )
        reader = PeriodicExportingMetricReader(
            exporter,
            export_interval_millis=30000,
        )
        provider = MeterProvider(resource=resource, metric_readers=[reader], views=views)

    metrics.set_meter_provider(provider)
    return provider
```

### 2.2 Application Metrics

```python
# app/observability/app_metrics.py

from opentelemetry import metrics

meter = metrics.get_meter("order-service")

# No request counter: the http.server.request.duration histogram's count IS the request count.

# ── Histograms ────────────────────────────────────────────────────────
request_duration = meter.create_histogram(
    name="http.server.request.duration",
    description="Duration of HTTP server requests",
    unit="s",  # buckets set by the View in configure_metrics()
)

db_query_duration = meter.create_histogram(
    name="db.query.duration",
    description="Database query duration in seconds",
    unit="s",
)

external_request_duration = meter.create_histogram(
    name="external.request.duration",
    description="External service request duration in seconds",
    unit="s",
)

# ── UpDownCounters ────────────────────────────────────────────────────
active_requests = meter.create_up_down_counter(
    name="http.server.active_requests",
    description="Currently active HTTP requests",
    unit="{request}",
)

# ── Business Metrics ──────────────────────────────────────────────────
order_total = meter.create_counter(
    name="business.order.total",
    description="Total order value processed",
    unit="USD",
)

order_count = meter.create_counter(
    name="business.order.count",
    description="Total orders created",
    unit="{order}",
)
```

### 2.3 Metrics Middleware

```python
# app/middleware/metrics_middleware.py

import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.observability.app_metrics import (
    request_duration,
    active_requests,
)

_KNOWN_METHODS = frozenset({"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"})


class MetricsMiddleware(BaseHTTPMiddleware):
    """Stable OTel HTTP semconv. Every attribute is bounded: no tenant_id, IDs, raw paths or query strings."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in ("/health", "/ready", "/metrics"):  # skip list only, never a label
            return await call_next(request)

        # The route isn't known until the router has matched, so active_requests has method + scheme only
        base = {
            "http.request.method": request.method if request.method in _KNOWN_METHODS else "_OTHER",
            "url.scheme": request.url.scheme,
        }
        active_requests.add(1, base)
        start = time.perf_counter()
        status = 500  # stays 500 if the app raises

        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            active_requests.add(-1, base)
            attrs = {**base, "http.response.status_code": status}
            # The route TEMPLATE, known only after routing: FastAPI puts the matched APIRoute in
            # scope["route"] (path "/api/v1/orders/{order_id}"). Unmatched (404) → no http.route.
            # NEVER request.url.path: raw paths are unbounded series.
            route = request.scope.get("route")
            if route is not None and getattr(route, "path", None):
                attrs["http.route"] = route.path
            if status >= 500:
                attrs["error.type"] = str(status)
            request_duration.record(time.perf_counter() - start, attrs)
```

Test the route template: request `/api/v1/orders/123` and `/api/v1/orders/456`, then assert there is
exactly one series, with `http.route="/api/v1/orders/{order_id}"`.

### 2.4 Recording Business Metrics

```python
# Inside service methods — record business-level metrics

from app.observability.app_metrics import order_total, order_count


class OrderService:
    async def create_order(self, ctx: RequestContext, req: CreateOrderRequest) -> Order:
        order = await self._process_order(ctx, req)

        # Business metrics — small enums only, no tenant_id (see 2.7)
        metric_attrs = {
            "payment_method": order.payment_method,
            "region": ctx.region,
        }
        order_count.add(1, metric_attrs)
        order_total.add(float(order.total), metric_attrs)

        return order
```

### 2.5 Database Query Metrics

```python
# app/middleware/db_metrics.py

import time
from sqlalchemy import event
from app.observability.app_metrics import db_query_duration


def instrument_db_metrics(engine):
    """Attach SQLAlchemy event listeners to record query duration."""

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def before_execute(conn, cursor, statement, parameters, context, executemany):
        conn.info["query_start"] = time.perf_counter()

    @event.listens_for(engine.sync_engine, "after_cursor_execute")
    def after_execute(conn, cursor, statement, parameters, context, executemany):
        elapsed = time.perf_counter() - conn.info.get("query_start", time.perf_counter())
        # Extract operation (SELECT, INSERT, UPDATE, DELETE) from statement
        operation = statement.strip().split()[0].upper() if statement else "UNKNOWN"
        db_query_duration.record(elapsed, {
            "db.system": "postgresql",
            "db.operation": operation,
        })
```

### 2.6 Prometheus Endpoint (Alternative)

If your infrastructure scrapes Prometheus `/metrics` instead of using OTLP push:

```python
# app/main.py

from prometheus_fastapi_instrumentator import Instrumentator

# After app creation, before adding routes
Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
    should_respect_env_var=False,
    excluded_handlers=["/health", "/ready", "/metrics"],
    inprogress_name="http_requests_inprogress",
    inprogress_labels=True,
).instrument(app).expose(app, endpoint="/metrics")
```

This path uses its own names (`http_request_duration_seconds`, with a `handler` label holding the
route template). Pick one path per service, either OTel (2.2–2.3) or this one, so the SLO queries have
exactly one source. Never add a tenant label to it.

### 2.7 Key Metrics Reference

Every label comes from a small, known set: no `tenant_id`, user or entity IDs, raw paths, query
strings or error messages. If you really need a per-tenant dimension, the only one allowed is a
bounded `tenant.tier` (free/pro/enterprise). Ask per-tenant questions of traces and logs.

| Metric | Type | Labels | Purpose |
|--------|------|--------|---------|
| `http.server.request.duration` | Histogram (s) | http.request.method, http.route (template), http.response.status_code, url.scheme, error.type (5xx) | Rate, errors and latency (RED); the count is the request count |
| `http.server.active_requests` | UpDownCounter | http.request.method, url.scheme | Concurrency / saturation |
| `db.query.duration` | Histogram | db.system, db.operation | Database performance |
| `external.request.duration` | Histogram | service (dependency name), operation (a small fixed set, never the raw URL) | Upstream latency |
| `business.order.total` | Counter | payment_method, region | Revenue KPI |
| `business.order.count` | Counter | payment_method, region | Volume KPI |

### 2.8 SLIs and Alerting

Don't compute SLIs in-process, so no p99, availability or "budget remaining" gauges. Percentiles
can't be averaged across workers or pods, and an in-memory window resets on every restart. Compute
SLIs at query time from the `http.server.request.duration` histogram instead:
- availability is 1 minus the 5xx share of its count;
- the latency SLI is the share of requests at or under the NFR threshold, which must be one of the
  bucket boundaries.

Alert with multi-window burn rates (14.4×, 6×, 1×). See `core/observability-patterns.md` §SLOs and
Alerting.

---

## 3. Structured Logging

### 3.1 structlog Setup — JSON Processor Chain

```python
# app/observability/logging.py

import logging
import re
import sys

import structlog

from app.config import settings


def configure_logging() -> None:
    """
    Configure structlog with a JSON processor chain.

    Call once during application startup, BEFORE configure_tracing().
    """
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        _add_service_info,
        _filter_sensitive_keys,
    ]

    if settings.ENVIRONMENT == "local":
        # Human-readable console output for local development
        renderer = structlog.dev.ConsoleRenderer()
    else:
        # JSON for production — ingestible by Loki, Datadog, CloudWatch, etc.
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        # stdlib records (uvicorn, sqlalchemy, httpx, ...) run through the same chain, redaction included
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    # Suppress noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def _add_service_info(logger, method_name, event_dict):
    """Inject service name and version into every log line."""
    event_dict["service"] = settings.SERVICE_NAME
    event_dict["version"] = settings.SERVICE_VERSION
    return event_dict


# ── Sensitive Data Filter ─────────────────────────────────────────────
# Redaction by KEY NAME, in the processor chain, for every level: DEBUG gets switched on during
# incidents, and it must stay safe then. Call sites don't have to remember anything.

_SENSITIVE_KEY = re.compile(
    r"pass(word|wd)?|secret|token|authorization|cookie|api[-_]?key|session|card|cvv|iban|ssn|private[-_]?key",
    re.IGNORECASE,
)


def redact_sensitive(value):
    """Return a copy with the value of every key matching _SENSITIVE_KEY replaced, at any depth."""
    if isinstance(value, dict):
        return {k: "[REDACTED]" if _SENSITIVE_KEY.search(str(k)) else redact_sensitive(v) for k, v in value.items()}
    if isinstance(value, list):  # not tuples: exc_info=(type, value, tb) must stay a tuple
        return [redact_sensitive(v) for v in value]
    return value


def _filter_sensitive_keys(logger, method_name, event_dict):
    return redact_sensitive(event_dict)
```

Never log request or response bodies. Log an allow-listed set of fields instead. Add a unit test that
logs `password` and `authorization` fields and asserts they come out as `[REDACTED]`.

### 3.2 Log Correlation with Trace ID and Span ID

```python
# app/observability/logging.py  (additional processor)

from opentelemetry import trace


def add_otel_context(logger, method_name, event_dict):
    """
    Inject trace_id and span_id from the current OTel span into every log line.

    Add this processor to the structlog chain AFTER merge_contextvars.
    """
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if ctx.is_valid:
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    return event_dict


# Updated processor chain:
shared_processors = [
    structlog.contextvars.merge_contextvars,
    add_otel_context,                         # <-- NEW
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.UnicodeDecoder(),
    _add_service_info,
    _filter_sensitive_keys,
]
```

### 3.3 Request-Scoped Context via contextvars

```python
# app/middleware/logging_middleware.py

import re
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger()

# Bounded charset and length: no log injection. fullmatch, because "$" also matches before a trailing "\n".
_VALID_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{8,128}")


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Bind request_id, method and path to structlog contextvars so every log line within this request
    includes them automatically. tenant_id and user_id are NOT read here from headers. The auth
    middleware (inside this one, see 4.2) takes them from the verified token, puts them on
    request.state and binds them with structlog.contextvars.bind_contextvars(...), so every log line
    below it carries them. A client header such as X-Tenant-ID is spoofable and never used.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Clear context from previous request (uvicorn may reuse the worker)
        structlog.contextvars.clear_contextvars()

        # Request ID — accept a well-formed inbound ID, otherwise generate one
        inbound = request.headers.get("x-request-id", "")
        request_id = inbound if _VALID_REQUEST_ID.fullmatch(inbound) else f"req_{uuid.uuid4()}"
        request.state.request_id = request_id

        # Bind to contextvars — all downstream log calls inherit these
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,  # no query string: it can carry tokens and PII
        )

        logger.info("request_started")

        try:
            response = await call_next(request)
        except Exception:
            logger.exception("request_failed", tenant_id=getattr(request.state, "tenant_id", "unknown"))
            raise

        logger.info(
            "request_completed",
            status_code=response.status_code,
            tenant_id=getattr(request.state, "tenant_id", "unknown"),  # set by the auth middleware
        )
        response.headers["X-Request-ID"] = request_id

        return response
```

### 3.4 Using the Logger in Application Code

```python
# app/services/order_service.py

import structlog

logger = structlog.get_logger()


class OrderService:
    async def create_order(self, ctx: RequestContext, req: CreateOrderRequest) -> Order:
        # tenant_id, request_id, trace_id are already bound via middleware
        logger.info(
            "creating_order",
            item_count=len(req.items),
            total=str(req.total),
        )

        order = await self._repo.save(ctx, Order.from_request(req))

        logger.info(
            "order_created",
            order_id=str(order.id),
            total=str(order.total),
        )
        return order


# Output (JSON, production):
# {
#   "timestamp": "2024-01-15T10:30:00.000Z",
#   "level": "info",
#   "logger": "app.services.order_service",
#   "service": "order-service",
#   "version": "1.2.3",
#   "tenant_id": "tenant_abc",
#   "request_id": "req_xyz",
#   "trace_id": "abc123def456789...",
#   "span_id": "0123456789abcdef",
#   "event": "order_created",
#   "order_id": "ord_123",
#   "total": "99.99"
# }
```

### 3.5 Required Fields on Every Log Line

| Field | Source | Purpose |
|-------|--------|---------|
| `timestamp` | structlog TimeStamper | When it happened |
| `level` | structlog add_log_level | Severity |
| `event` | Developer | What happened (structlog uses `event` instead of `msg`) |
| `tenant_id` | contextvars (auth middleware, from the verified token) | Whose request |
| `request_id` | contextvars (LoggingMiddleware, validated or generated) | Correlate within a request |
| `trace_id` | OTel span context | Correlate across services |
| `span_id` | OTel span context | Exact span for log line |
| `service` | _add_service_info processor | Which service |
| `version` | _add_service_info processor | Which deployment |

### 3.6 Log Level Strategy

| Level | When to use | Example |
|-------|------------|---------|
| **ERROR** | Something broke that needs investigation | Database connection lost, unhandled exception |
| **WARNING** | Concerning but handled | Circuit breaker opened, retry succeeded |
| **INFO** | Normal business events | Order created, user signed up |
| **DEBUG** | Troubleshooting detail (off in production) | SQL query, cache hit/miss |

```python
# ERROR — actionable, needs investigation
logger.error(
    "payment_failed",
    order_id=str(order.id),
    payment_method=order.payment_method,
    error=str(exc),
)

# WARNING — concerning but handled
logger.warning(
    "circuit_breaker_opened",
    service="payment-gateway",
    failures=cb.failure_count,
    reset_timeout=cb.reset_timeout,
)

# INFO — business event
logger.info(
    "order_placed",
    order_id=str(order.id),
    total=str(order.total),
    item_count=len(order.items),
)

# DEBUG — troubleshooting (off in production)
logger.debug(
    "cache_lookup",
    cache_key=f"order:{order_id}",
    hit=True,
)
```

### 3.7 Alternative: Python stdlib logging with JSON Formatter

For teams that prefer stdlib logging over structlog:

```python
# app/observability/logging_stdlib.py

import json
import logging
from datetime import datetime, timezone

from opentelemetry import trace

from app.config import settings
from app.observability.logging import redact_sensitive


class JSONFormatter(logging.Formatter):
    """JSON log formatter with OTel trace correlation."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "event": record.getMessage(),
            "service": settings.SERVICE_NAME,
            "version": settings.SERVICE_VERSION,
        }

        # OTel trace context
        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx.is_valid:
            log_entry["trace_id"] = format(ctx.trace_id, "032x")
            log_entry["span_id"] = format(ctx.span_id, "016x")

        # Merge extra fields — redacted by key name, the same rule as the structlog chain, at every level
        if hasattr(record, "extra_fields"):
            log_entry.update(redact_sensitive(record.extra_fields))

        # Exception info
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


def configure_stdlib_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
```

---

## 4. Full Setup — Wiring Everything Together

### 4.1 instrument_app() Function

```python
# app/observability/__init__.py

from app.observability.logging import configure_logging
from app.observability.tracing import configure_tracing
from app.observability.metrics import configure_metrics
from app.observability.instruments import instrument_auto


def instrument_app(app, engine=None):
    """
    One-call setup for all observability.

    Must be called inside the FastAPI lifespan context manager.
    Returns (tracer_provider, meter_provider) for clean shutdown.
    """
    # 1. Logging first — so OTel SDK logs are captured
    configure_logging()

    # 2. Tracing
    tracer_provider = configure_tracing()

    # 3. Metrics
    meter_provider = configure_metrics()

    # 4. Auto-instrumentation
    instrument_auto(app, engine=engine)

    return tracer_provider, meter_provider
```

### 4.2 FastAPI Lifespan with Clean Shutdown

```python
# app/main.py

from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.observability import instrument_app
from app.db import create_engine
from app.middleware.auth_middleware import AuthMiddleware
from app.middleware.logging_middleware import LoggingMiddleware
from app.middleware.metrics_middleware import MetricsMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────
    engine = create_engine()
    tracer_provider, meter_provider = instrument_app(app, engine=engine.sync_engine)

    yield

    # ── Shutdown — flush all telemetry before process exits ───────────
    if tracer_provider:
        tracer_provider.force_flush()
        tracer_provider.shutdown()
    if meter_provider:
        meter_provider.force_flush()
        meter_provider.shutdown()


app = FastAPI(
    title="Order Service",
    lifespan=lifespan,
)

# Middleware order matters — outermost runs first. Starlette: the LAST one added is the OUTERMOST.
app.add_middleware(AuthMiddleware)     # innermost: verifies the token; sets request.state.tenant_id/user_id
                                       # from its claims and binds them to structlog contextvars
app.add_middleware(LoggingMiddleware)  # request_id (validated or generated) + request-scoped log context
app.add_middleware(MetricsMiddleware)  # outermost: sees every response, including 401s
```

### 4.3 Configuration via Environment Variables

```python
# app/config.py

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Service identity
    SERVICE_NAME: str = "order-service"
    SERVICE_VERSION: str = "0.0.0"
    ENVIRONMENT: str = "local"

    # OpenTelemetry
    OTEL_EXPORTER_OTLP_ENDPOINT: str = ""
    OTEL_EXPORTER_INSECURE: bool = True

    # Logging
    LOG_LEVEL: str = "INFO"

    model_config = {"env_prefix": "", "case_sensitive": True}


settings = Settings()
```

### 4.4 RequestContext Dataclass

```python
# app/context.py

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RequestContext:
    """
    Immutable request context threaded through service and repository layers.
    tenant_id and user_id come from the verified credential (request.state, set by the auth
    middleware), never from client headers.
    """
    tenant_id: str
    user_id: str
    request_id: str
    region: str = ""
```

### 4.5 FastAPI Dependency for RequestContext

```python
# app/dependencies.py

from fastapi import Request

from app.context import RequestContext


async def get_request_context(request: Request) -> RequestContext:
    # tenant_id and user_id come from the VERIFIED token (the auth middleware put them on
    # request.state). Never from a client header such as X-Tenant-ID: anyone can send it.
    return RequestContext(
        tenant_id=request.state.tenant_id,
        user_id=request.state.user_id,
        request_id=request.state.request_id,  # validated or generated by LoggingMiddleware
    )
```

---

## 5. Local Development — Docker Compose Snippet

```yaml
# docker-compose.observability.yml
# Run alongside your main docker-compose.yml:
#   docker compose -f docker-compose.yml -f docker-compose.observability.yml up -d

services:
  jaeger:
    image: jaegertracing/all-in-one:1.54
    ports:
      - "16686:16686"   # Jaeger UI
      - "4317:4317"     # OTLP gRPC receiver
      - "4318:4318"     # OTLP HTTP receiver
    environment:
      COLLECTOR_OTLP_ENABLED: "true"

  prometheus:
    image: prom/prometheus:v2.50.0
    ports:
      - "9090:9090"
    volumes:
      - ./infra/prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana:10.3.0
    ports:
      - "3001:3000"
    environment:
      GF_SECURITY_ADMIN_USER: admin
      GF_SECURITY_ADMIN_PASSWORD: admin
    volumes:
      - grafana-data:/var/lib/grafana

  loki:
    image: grafana/loki:2.9.4
    ports:
      - "3100:3100"

volumes:
  grafana-data:
```

Environment variables for your Python service in local dev:

```yaml
# docker-compose.yml — your app service
services:
  order-service:
    environment:
      OTEL_EXPORTER_OTLP_ENDPOINT: "http://jaeger:4317"
      OTEL_EXPORTER_INSECURE: "true"
      LOG_LEVEL: "DEBUG"
      ENVIRONMENT: "local"
```

---

## 6. Critical Rules

1. **`tenant_id` on every log line and trace span, never on a metric.** At most a bounded `tenant.tier`. The tenant comes from the verified token, never from a client header.
2. **Structured logging only** — no f-string log messages like `logger.info(f"Order {id} created")`; use `logger.info("order_created", order_id=id)` instead
3. **JSON format in production** — human-readable only in local dev
4. **trace_id and span_id on every log line** — via the `add_otel_context` processor
5. **ERROR means a server-side failure someone should look at.** Don't use it for expected business conditions. Alerts come from SLO burn rates, not from counting ERROR lines.
6. **Never log sensitive data.** `_filter_sensitive_keys` redacts by key name, at any depth and at every level, and stdlib records go through it too via `foreign_pre_chain`. Never log request or response bodies.
7. **Metrics at every boundary** (HTTP handler, service method, repository call, external API call), with bounded labels only. `http.route` is the route template (`scope["route"].path`), never `request.url.path`.
8. **Every span records errors** — use `span.record_exception(exc)` + `span.set_status(StatusCode.ERROR)` in the except block
9. **Clean shutdown** — call `force_flush()` and `shutdown()` on both providers in the FastAPI lifespan teardown
10. **Use contextvars.** Bind request_id (validated) in LoggingMiddleware, and tenant_id in the auth middleware, once each. Never pass them manually to every log call.
11. **SLIs come from the histogram at query time.** No in-process SLA gauges. Alert on multi-window burn rates (see 2.8).
