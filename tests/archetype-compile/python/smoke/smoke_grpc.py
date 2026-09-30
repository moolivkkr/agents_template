# harness smoke: run grpc-pattern-python.md's serve() in-process (real grpc.aio server, generated code,
# interceptors, health servicer) over crud-service-python.md's real WidgetService with in-memory
# repository/cache/audit, and drive it with a real client. Stopped with SIGINT, as in production.
import asyncio
import os
import signal
import socket
import uuid
from collections.abc import AsyncIterator

import grpc
from grpc_health.v1 import health_pb2, health_pb2_grpc
from yourapp.v1 import common_pb2, widget_pb2
from yourapp.v1 import widget_service_pb2_grpc as pb_grpc

from app.domain.base import ListFilters, ListResult
from app.domain.widget import Widget
from app.grpc.context import Caller
from app.grpc.server import serve
from app.services.widget import WidgetService

TENANT, USER = uuid.uuid4(), uuid.uuid4()


class MemRepo:
    def __init__(self) -> None:
        self.rows: dict[tuple[uuid.UUID, uuid.UUID], Widget] = {}

    async def create(self, widget: Widget) -> None:
        self.rows[(widget.tenant_id, widget.id)] = widget

    async def get_by_id(self, tenant_id: uuid.UUID, widget_id: uuid.UUID) -> Widget | None:
        return self.rows.get((tenant_id, widget_id))

    async def update(self, widget: Widget) -> bool:
        return True

    async def soft_delete(self, tenant_id: uuid.UUID, widget_id: uuid.UUID) -> bool:
        return self.rows.pop((tenant_id, widget_id), None) is not None

    async def list(self, tenant_id: uuid.UUID, filters: ListFilters) -> ListResult[Widget]:
        items = [w for (t, _), w in self.rows.items() if t == tenant_id]
        return ListResult(items=items[: filters.page_size], total=len(items))


class MemCache:
    async def get(self, key: str) -> bytes | None:
        return None

    async def set(self, key: str, value: bytes, ttl_seconds: int) -> None: ...

    async def delete(self, key: str) -> None: ...


class MemAudit:
    async def write(self, entry: object) -> None: ...


class Events:
    async def subscribe(self, tenant_id: uuid.UUID) -> AsyncIterator[common_pb2.WidgetEvent]:
        for kind in (common_pb2.WIDGET_EVENT_TYPE_CREATED, common_pb2.WIDGET_EVENT_TYPE_DELETED):
            yield common_pb2.WidgetEvent(type=kind, widget=widget_pb2.Widget(tenant_id=str(tenant_id)))


class Validator:
    def validate(self, token: str) -> Caller:
        if token != "good":
            raise ValueError("bad token")
        return Caller(tenant_id=TENANT, user_id=USER)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def expect_code(coro: object, code: grpc.StatusCode) -> str:
    try:
        await coro  # type: ignore[misc]
    except grpc.aio.AioRpcError as e:
        assert e.code() == code, (e.code(), e.details(), code)
        return e.details() or ""
    raise AssertionError(f"expected {code}")


async def client(port: int) -> None:
    auth = (("authorization", "Bearer good"),)
    async with grpc.aio.insecure_channel(f"localhost:{port}") as ch:
        await ch.channel_ready()
        health = await health_pb2_grpc.HealthStub(ch).Check(health_pb2.HealthCheckRequest(service="yourapp.v1.WidgetService"))
        assert health.status == health_pb2.HealthCheckResponse.SERVING, health

        stub = pb_grpc.WidgetServiceStub(ch)
        await expect_code(stub.CreateWidget(widget_pb2.CreateWidgetRequest(name="w")), grpc.StatusCode.UNAUTHENTICATED)
        await expect_code(stub.CreateWidget(widget_pb2.CreateWidgetRequest(name="w"),
                                            metadata=(("authorization", "Bearer bad"),)), grpc.StatusCode.UNAUTHENTICATED)
        # a client-sent tenant header changes nothing: the tenant comes from the verified token
        created = await stub.CreateWidget(widget_pb2.CreateWidgetRequest(name="w1", description="d"),
                                          metadata=(*auth, ("x-tenant-id", str(uuid.uuid4()))))
        assert created.widget.tenant_id == str(TENANT) and created.widget.status == widget_pb2.WIDGET_STATUS_ACTIVE, created
        got = await stub.GetWidget(widget_pb2.GetWidgetRequest(id=created.widget.id), metadata=auth)
        assert got.widget.name == "w1", got
        await expect_code(stub.GetWidget(widget_pb2.GetWidgetRequest(id=str(uuid.uuid4())), metadata=auth),
                          grpc.StatusCode.NOT_FOUND)
        await expect_code(stub.GetWidget(widget_pb2.GetWidgetRequest(id="nope"), metadata=auth),
                          grpc.StatusCode.INVALID_ARGUMENT)
        await expect_code(stub.CreateWidget(widget_pb2.CreateWidgetRequest(name=" "), metadata=auth),
                          grpc.StatusCode.INVALID_ARGUMENT)
        listed = await stub.ListWidgets(widget_pb2.ListWidgetsRequest(page_size=10), metadata=auth)
        assert len(listed.widgets) == 1 and listed.total_count == 1 and listed.next_page_token == "", listed

        events = [e async for e in stub.WatchWidgets(common_pb2.WatchWidgetsRequest(), metadata=auth)]
        assert [e.type for e in events] == [common_pb2.WIDGET_EVENT_TYPE_CREATED, common_pb2.WIDGET_EVENT_TYPE_DELETED]
        await expect_code(_drain(stub.WatchWidgets(common_pb2.WatchWidgetsRequest())), grpc.StatusCode.UNAUTHENTICATED)

        async def rows() -> AsyncIterator[common_pb2.ImportWidgetRequest]:
            yield common_pb2.ImportWidgetRequest(name="ok")
            yield common_pb2.ImportWidgetRequest(name="")
        res = await stub.ImportWidgets(rows(), metadata=auth)
        assert res.imported_count == 1 and res.failed_count == 1, res
        assert list(res.errors) == ["row 2: Some fields are invalid."], res.errors
        await expect_code(stub.ImportWidgets(rows()), grpc.StatusCode.UNAUTHENTICATED)
    os.kill(os.getpid(), signal.SIGINT)  # serve() stops gracefully on SIGINT/SIGTERM


async def _drain(call: object) -> None:
    async for _ in call:  # type: ignore[attr-defined]
        pass


async def main() -> None:
    port = free_port()
    svc = WidgetService(repo=MemRepo(), cache=MemCache(), audit_writer=MemAudit())
    server_task = asyncio.create_task(serve(svc, Events(), Validator(), port=port))
    try:
        await asyncio.wait_for(client(port), timeout=30)
    finally:
        await asyncio.wait_for(server_task, timeout=15)


asyncio.run(main())
