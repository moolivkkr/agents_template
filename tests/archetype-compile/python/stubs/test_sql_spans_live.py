"""harness-only (--live): observability-python.md's sql_spans.py on the engine the archetypes use
(SQLAlchemy 2.1 async + asyncpg, PostgreSQL 16). One CLIENT span per statement, child of the span that
was current in the coroutine that awaited the query (also with two requests' queries interleaved), with
the stable semconv db attributes and no parameter values; a failing statement's span records the error.
"""
import asyncio

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind, StatusCode
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from app.observability.sql_spans import instrument_sql

EXPORTER = InMemorySpanExporter()
_provider = TracerProvider()
_provider.add_span_processor(SimpleSpanProcessor(EXPORTER))
trace.set_tracer_provider(_provider)
tracer = trace.get_tracer("harness")


def _sql_spans() -> list[ReadableSpan]:
    return [s for s in EXPORTER.get_finished_spans() if s.kind == SpanKind.CLIENT]


async def _request(engine: AsyncEngine, name: str, started: asyncio.Event, other: asyncio.Event) -> int:
    """One 'request': a parent span, a query, a wait for the other request, a second query."""
    with tracer.start_as_current_span(name) as parent:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT pg_sleep(0.05)"))
            started.set()
            await other.wait()  # the other request's queries run while this one is open
            await conn.execute(text("SELECT CAST(:secret AS text)"), {"secret": f"value-of-{name}"})
        return parent.get_span_context().span_id


@pytest.mark.asyncio
async def test_sql_spans_on_asyncpg(pg_url: str) -> None:
    engine = create_async_engine(pg_url, poolclass=NullPool)
    instrument_sql(engine)
    instrument_sql(engine)  # twice: still one span per statement
    EXPORTER.clear()
    try:
        a_started, b_started = asyncio.Event(), asyncio.Event()
        a_id, b_id = await asyncio.gather(
            _request(engine, "request-a", a_started, b_started),
            _request(engine, "request-b", b_started, a_started),
        )
        with tracer.start_as_current_span("request-c") as c_span:
            async with engine.connect() as conn:
                with pytest.raises(ProgrammingError):
                    await conn.execute(text("SELECT * FROM no_such_table"))
        c_id = c_span.get_span_context().span_id
    finally:
        await engine.dispose()

    spans = _sql_spans()
    by_parent: dict[int, list[ReadableSpan]] = {}
    for s in spans:
        assert s.parent is not None, f"{s.name} has no parent"
        by_parent.setdefault(s.parent.span_id, []).append(s)
    assert sorted(len(v) for v in (by_parent[a_id], by_parent[b_id])) == [2, 2], {
        k: [s.name for s in v] for k, v in by_parent.items()}
    assert len(by_parent[c_id]) == 1 and len(spans) == 5, [s.name for s in spans]

    ok = by_parent[a_id][-1]
    attrs = dict(ok.attributes or {})
    assert ok.name == "SELECT test", ok.name  # "{db.operation.name} {db.namespace}"
    assert attrs["db.system.name"] == "postgresql" and attrs["db.namespace"] == "test", attrs
    assert attrs["db.operation.name"] == "SELECT" and attrs["db.query.text"] == "SELECT CAST($1 AS text)", attrs
    assert isinstance(attrs["server.port"], int) and attrs["server.address"], attrs
    assert not any("value-of-" in str(v) for s in spans for v in (s.attributes or {}).values())

    failed = by_parent[c_id][0]
    assert failed.status.status_code == StatusCode.ERROR, failed.status
    fattrs = dict(failed.attributes or {})
    assert fattrs["error.type"] == "42P01" and fattrs["db.response.status_code"] == "42P01", fattrs
    assert any(e.name == "exception" for e in failed.events), failed.events
    print("asyncpg SQL spans:", [(s.name, s.parent.span_id == a_id if s.parent else None) for s in spans])
