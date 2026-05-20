---
skill: grpc-pattern-python
description: Python gRPC archetype — grpcio, grpc-tools, interceptors, streaming, health check, asyncio support
version: "1.0"
tags:
  - python
  - grpc
  - protobuf
  - grpcio
  - archetype
  - backend
---

# gRPC Pattern — Python

> **Canonical reference**: This is the Python counterpart to `grpc-pattern.md` (language-neutral). Read that first for concepts and contracts.

Python gRPC uses `grpcio` for the runtime and `grpcio-tools` (or `buf`) for code generation. Use the async API (`grpc.aio`) for production services.

## Code Generation

```bash
# Install
pip install grpcio grpcio-tools grpcio-health-checking grpcio-reflection

# Generate (using grpc_tools)
python -m grpc_tools.protoc \
    -I proto/ \
    --python_out=gen/ \
    --grpc_python_out=gen/ \
    --pyi_out=gen/ \
    proto/yourapp/v1/widget_service.proto

# Or use buf (recommended)
buf generate
```

## Server Implementation (Async)

```python
# app/grpc/widget_server.py

import logging
from uuid import UUID

import grpc
from google.protobuf.timestamp_pb2 import Timestamp

from gen.yourapp.v1 import widget_service_pb2 as pb
from gen.yourapp.v1 import widget_service_pb2_grpc as pb_grpc
from app.services.widget import WidgetService
from app.grpc.context import tenant_id_from_context, user_id_from_context
from app.grpc.errors import map_error

logger = logging.getLogger(__name__)

class WidgetServicer(pb_grpc.WidgetServiceServicer):
    """gRPC service implementation for WidgetService."""

    def __init__(self, svc: WidgetService) -> None:
        self._svc = svc

    async def CreateWidget(
        self, request: pb.CreateWidgetRequest, context: grpc.aio.ServicerContext,
    ) -> pb.CreateWidgetResponse:
        tenant_id = tenant_id_from_context(context)
        user_id = user_id_from_context(context)

        if not request.name:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "name is required")

        try:
            result = await self._svc.create(
                tenant_id=tenant_id,
                user_id=user_id,
                name=request.name,
                description=request.description,
            )
            return pb.CreateWidgetResponse(widget=_to_proto(result))
        except Exception as exc:
            raise map_error(exc) from exc

    async def GetWidget(
        self, request: pb.GetWidgetRequest, context: grpc.aio.ServicerContext,
    ) -> pb.GetWidgetResponse:
        tenant_id = tenant_id_from_context(context)

        try:
            result = await self._svc.get(tenant_id=tenant_id, widget_id=UUID(request.id))
            return pb.GetWidgetResponse(widget=_to_proto(result))
        except Exception as exc:
            raise map_error(exc) from exc

    async def ListWidgets(
        self, request: pb.ListWidgetsRequest, context: grpc.aio.ServicerContext,
    ) -> pb.ListWidgetsResponse:
        tenant_id = tenant_id_from_context(context)

        page_size = max(1, min(request.page_size or 20, 100))

        try:
            result = await self._svc.list(
                tenant_id=tenant_id,
                cursor=request.page_token or None,
                page_size=page_size,
                order_by=request.order_by or "created_at desc",
            )
            return pb.ListWidgetsResponse(
                widgets=[_to_proto(w) for w in result.items],
                next_page_token=result.next_cursor or "",
                total_count=result.total,
            )
        except Exception as exc:
            raise map_error(exc) from exc

    async def WatchWidgets(
        self, request: pb.WatchWidgetsRequest, context: grpc.aio.ServicerContext,
    ):
        """Server streaming: push widget events to the client."""
        tenant_id = tenant_id_from_context(context)
        logger.info("watch.started", extra={"tenant_id": str(tenant_id)})

        async for event in self._svc.subscribe(tenant_id):
            if context.cancelled():
                break
            yield _event_to_proto(event)

        logger.info("watch.ended", extra={"tenant_id": str(tenant_id)})

    async def ImportWidgets(
        self, request_iterator, context: grpc.aio.ServicerContext,
    ) -> pb.ImportWidgetsResponse:
        """Client streaming: receive a stream of widgets to import."""
        tenant_id = tenant_id_from_context(context)
        user_id = user_id_from_context(context)

        imported = 0
        failed = 0
        errors = []

        async for req in request_iterator:
            try:
                await self._svc.create(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    name=req.name,
                    description=req.description,
                )
                imported += 1
            except Exception as exc:
                failed += 1
                errors.append(f"row {imported + failed}: {exc}")

        return pb.ImportWidgetsResponse(
            imported_count=imported,
            failed_count=failed,
            errors=errors,
        )

def _to_proto(widget) -> pb.Widget:
    ts_created = Timestamp()
    ts_created.FromDatetime(widget.created_at)
    ts_updated = Timestamp()
    ts_updated.FromDatetime(widget.updated_at)

    return pb.Widget(
        id=str(widget.id),
        tenant_id=str(widget.tenant_id),
        name=widget.name,
        description=widget.description,
        status=_status_to_proto(widget.status),
        created_at=ts_created,
        updated_at=ts_updated,
        created_by=str(widget.created_by),
        version=widget.version,
    )
```

## Interceptors

```python
# app/grpc/interceptors.py

import logging
import time

import grpc
from grpc import aio

logger = logging.getLogger(__name__)

SKIP_AUTH_METHODS = {
    "/grpc.health.v1.Health/Check",
    "/grpc.health.v1.Health/Watch",
}

class AuthInterceptor(aio.ServerInterceptor):
    """Validates JWT from metadata and injects tenant context."""

    def __init__(self, jwt_validator):
        self._validator = jwt_validator

    async def intercept_service(self, continuation, handler_call_details):
        method = handler_call_details.method

        if method in SKIP_AUTH_METHODS:
            return await continuation(handler_call_details)

        metadata = dict(handler_call_details.invocation_metadata or [])
        token = metadata.get("authorization", "")

        if token.startswith("Bearer "):
            token = token[7:]

        if not token:
            return _abort_handler(grpc.StatusCode.UNAUTHENTICATED, "missing authorization")

        try:
            claims = self._validator.validate(token)
        except Exception:
            return _abort_handler(grpc.StatusCode.UNAUTHENTICATED, "invalid token")

        # Store claims in metadata for downstream access
        handler_call_details.invocation_metadata = list(
            handler_call_details.invocation_metadata or []
        ) + [
            ("x-tenant-id", str(claims.tenant_id)),
            ("x-user-id", str(claims.user_id)),
        ]

        return await continuation(handler_call_details)

class LoggingInterceptor(aio.ServerInterceptor):
    """Logs every RPC with duration and status."""

    async def intercept_service(self, continuation, handler_call_details):
        method = handler_call_details.method
        start = time.monotonic()

        handler = await continuation(handler_call_details)

        duration = time.monotonic() - start
        logger.info("grpc.request", extra={
            "method": method,
            "duration_ms": round(duration * 1000, 2),
        })

        return handler

def _abort_handler(code, message):
    """Create a handler that immediately aborts with the given status."""

    async def abort(request, context):
        await context.abort(code, message)

    return grpc.unary_unary_rpc_method_handler(abort)
```

## Context Helpers

```python
# app/grpc/context.py

from uuid import UUID

import grpc

def tenant_id_from_context(context: grpc.aio.ServicerContext) -> UUID:
    """Extract tenant_id injected by auth interceptor."""
    metadata = dict(context.invocation_metadata())
    tid = metadata.get("x-tenant-id")
    if not tid:
        raise grpc.aio.AbortError(grpc.StatusCode.UNAUTHENTICATED, "missing tenant context")
    return UUID(tid)

def user_id_from_context(context: grpc.aio.ServicerContext) -> UUID:
    """Extract user_id injected by auth interceptor."""
    metadata = dict(context.invocation_metadata())
    uid = metadata.get("x-user-id")
    if not uid:
        raise grpc.aio.AbortError(grpc.StatusCode.UNAUTHENTICATED, "missing user context")
    return UUID(uid)
```

## Error Mapping

```python
# app/grpc/errors.py

import grpc
from app.errors import (
    AppError,
    NotFoundError,
    ConflictError,
    ValidationError,
    ForbiddenError,
)

_ERROR_MAP = {
    NotFoundError: grpc.StatusCode.NOT_FOUND,
    ConflictError: grpc.StatusCode.ALREADY_EXISTS,
    ValidationError: grpc.StatusCode.INVALID_ARGUMENT,
    ForbiddenError: grpc.StatusCode.PERMISSION_DENIED,
}

def map_error(exc: Exception) -> grpc.RpcError:
    """Convert a domain error to a gRPC error."""
    if isinstance(exc, AppError):
        code = _ERROR_MAP.get(type(exc), grpc.StatusCode.INTERNAL)
        return grpc.aio.AbortError(code, exc.message)

    return grpc.aio.AbortError(grpc.StatusCode.INTERNAL, "internal error")
```

## Server Startup

```python
# app/grpc/server.py

import asyncio
import logging
import signal

import grpc
from grpc import aio
from grpc_health.v1 import health_pb2, health_pb2_grpc
from grpc_health.v1.health import HealthServicer
from grpc_reflection.v1alpha import reflection

from gen.yourapp.v1 import widget_service_pb2_grpc as pb_grpc
from app.grpc.widget_server import WidgetServicer
from app.grpc.interceptors import AuthInterceptor, LoggingInterceptor

logger = logging.getLogger(__name__)

async def serve(port: int = 50051) -> None:
    server = aio.server(
        interceptors=[
            LoggingInterceptor(),
            AuthInterceptor(jwt_validator),
        ],
    )

    # Register services
    widget_servicer = WidgetServicer(widget_svc)
    pb_grpc.add_WidgetServiceServicer_to_server(widget_servicer, server)

    # Health check
    health_servicer = HealthServicer()
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)
    health_servicer.set("yourapp.v1.WidgetService", health_pb2.HealthCheckResponse.SERVING)

    # Reflection (development only)
    if os.getenv("ENABLE_REFLECTION") == "true":
        reflection.enable_server_reflection(
            [
                "yourapp.v1.WidgetService",
                reflection.SERVICE_NAME,
                health_pb2.DESCRIPTOR.services_by_name["Health"].full_name,
            ],
            server,
        )

    server.add_insecure_port(f"[::]:{port}")
    await server.start()
    logger.info("gRPC server listening on port %d", port)

    # Graceful shutdown
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _signal_handler():
        logger.info("shutdown signal received")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    await stop_event.wait()
    await server.stop(grace=5)
    logger.info("gRPC server stopped")

if __name__ == "__main__":
    asyncio.run(serve())
```

## Critical Rules

- Use `grpc.aio` (async) API for production — synchronous `grpc` API blocks the thread
- Use `await context.abort(code, message)` for errors — never raise plain Python exceptions
- Extract tenant context from `invocation_metadata` — injected by auth interceptor
- Register `grpc_health` service on every server — required for load balancer probes
- Enable reflection via `grpc_reflection` only when `ENABLE_REFLECTION` is set
- Use `server.stop(grace=N)` for graceful shutdown — waits N seconds for in-flight RPCs
- Streaming RPCs MUST check `context.cancelled()` in loops — detect client disconnection
- Use `async for` with request iterators in client streaming — native async iteration
- Use `yield` in server streaming servicer methods — grpcio-tools generates async generator stubs
