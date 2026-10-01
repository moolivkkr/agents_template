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

> Python samples checked 2026-09-30 on Python 3.12.8 with pyright 1.1.414 (`tests/archetype-compile/python/run.sh`): code generated from grpc-pattern.md's .proto files with grpcio-tools 1.84.0 (protobuf 7.36.2; the harness adds the two imports its common.proto lacks), type-checked against the generated stubs, and `serve()` run in-process against a real client (unary, both streaming kinds, auth, health, SIGINT shutdown). grpcio 1.84.0.

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

`protoc` generates code only for the files it's given: list `widget.proto` and `common.proto` as well
(`buf generate` does that for you). The generated modules import each other as `yourapp.v1.*`, so put
`gen/` on the import path (`PYTHONPATH=gen`, or your packaging's equivalent).

## Server Implementation (Async)

```python
# app/grpc/widget_server.py

import logging
from collections.abc import AsyncIterator
from typing import Protocol
from uuid import UUID

import grpc
from google.protobuf.timestamp_pb2 import Timestamp

# Messages are in the module of the .proto that defines them (widget.proto, common.proto);
# widget_service_pb2_grpc has the servicer base class.
from yourapp.v1 import common_pb2, widget_pb2
from yourapp.v1 import widget_service_pb2_grpc as pb_grpc

from app.domain.widget import Widget, WidgetStatus
from app.errors import AppError
from app.grpc.context import tenant_id_from_context, user_id_from_context
from app.grpc.errors import abort_with
from app.services.widget import WidgetService

logger = logging.getLogger(__name__)


class WidgetEventSource(Protocol):
    """Feeds WatchWidgets: Redis pub/sub, a message-queue consumer, Postgres LISTEN/NOTIFY, ..."""

    def subscribe(self, tenant_id: UUID) -> AsyncIterator[common_pb2.WidgetEvent]: ...


class WidgetServicer(pb_grpc.WidgetServiceServicer):
    """gRPC service implementation for WidgetService."""

    def __init__(self, svc: WidgetService, events: WidgetEventSource) -> None:
        self._svc = svc
        self._events = events

    async def CreateWidget(
        self, request: widget_pb2.CreateWidgetRequest, context: grpc.aio.ServicerContext,
    ) -> widget_pb2.CreateWidgetResponse:
        if not request.name:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "name is required")

        try:
            result = await self._svc.create(
                tenant_id=tenant_id_from_context(),
                user_id=user_id_from_context(),
                name=request.name,
                description=request.description,
            )
            return widget_pb2.CreateWidgetResponse(widget=_to_proto(result))
        except Exception as exc:
            await abort_with(context, exc)

    async def GetWidget(
        self, request: widget_pb2.GetWidgetRequest, context: grpc.aio.ServicerContext,
    ) -> widget_pb2.GetWidgetResponse:
        try:
            widget_id = UUID(request.id)
        except ValueError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "id must be a UUID")

        try:
            result = await self._svc.get(tenant_id=tenant_id_from_context(), widget_id=widget_id)
            return widget_pb2.GetWidgetResponse(widget=_to_proto(result))
        except Exception as exc:
            await abort_with(context, exc)

    async def ListWidgets(
        self, request: widget_pb2.ListWidgetsRequest, context: grpc.aio.ServicerContext,
    ) -> widget_pb2.ListWidgetsResponse:
        # AIP-158: 0 means the default, above the maximum is coerced to it, negative is an error.
        if request.page_size < 0:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "page_size must not be negative")
        page_size = min(request.page_size or 20, 100)
        # order_by is "<field> <asc|desc>"; the service allow-lists both parts
        sort_by, _, sort_dir = (request.order_by or "created_at desc").partition(" ")

        try:
            result = await self._svc.list(
                tenant_id=tenant_id_from_context(),
                cursor=request.page_token or None,
                limit=page_size,
                sort_by=sort_by,
                sort_dir=sort_dir or "desc",
            )
            return widget_pb2.ListWidgetsResponse(
                widgets=[_to_proto(w) for w in result.items],
                next_page_token=result.cursor if result.has_more and result.cursor else "",
                total_count=result.total,
            )
        except Exception as exc:
            await abort_with(context, exc)

    async def WatchWidgets(
        self, request: common_pb2.WatchWidgetsRequest, context: grpc.aio.ServicerContext,
    ) -> AsyncIterator[common_pb2.WidgetEvent]:
        """Server streaming: push widget events to the client."""
        tenant_id = tenant_id_from_context()
        logger.info("watch.started", extra={"tenant_id": str(tenant_id)})

        async for event in self._events.subscribe(tenant_id):
            if context.cancelled():
                break
            yield event

        logger.info("watch.ended", extra={"tenant_id": str(tenant_id)})

    async def ImportWidgets(
        self,
        request_iterator: AsyncIterator[common_pb2.ImportWidgetRequest],
        context: grpc.aio.ServicerContext,
    ) -> common_pb2.ImportWidgetsResponse:
        """Client streaming: receive a stream of widgets to import."""
        tenant_id = tenant_id_from_context()
        user_id = user_id_from_context()

        imported = 0
        failed = 0
        errors: list[str] = []

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
                # user-safe text only: an AppError message, never str(exc) of anything else
                reason = exc.message if isinstance(exc, AppError) else "internal error"
                errors.append(f"row {imported + failed}: {reason}")

        return common_pb2.ImportWidgetsResponse(
            imported_count=imported,
            failed_count=failed,
            errors=errors,
        )


_STATUS_TO_PROTO = {
    WidgetStatus.ACTIVE: widget_pb2.WIDGET_STATUS_ACTIVE,
    WidgetStatus.INACTIVE: widget_pb2.WIDGET_STATUS_INACTIVE,
    WidgetStatus.ARCHIVED: widget_pb2.WIDGET_STATUS_ARCHIVED,
}


def _to_proto(widget: Widget) -> widget_pb2.Widget:
    ts_created = Timestamp()
    ts_created.FromDatetime(widget.created_at)
    ts_updated = Timestamp()
    ts_updated.FromDatetime(widget.updated_at)

    return widget_pb2.Widget(
        id=str(widget.id),
        tenant_id=str(widget.tenant_id),
        name=widget.name,
        description=widget.description,
        status=_STATUS_TO_PROTO.get(widget.status, widget_pb2.WIDGET_STATUS_UNSPECIFIED),
        created_at=ts_created,
        updated_at=ts_updated,
        created_by=str(widget.created_by),
        version=widget.version,
    )
```

## Interceptors

```python
# app/grpc/interceptors.py

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, Protocol, TypeAlias

import grpc
from grpc import aio

from app.grpc.context import Caller, set_caller

logger = logging.getLogger(__name__)

SKIP_AUTH_METHODS = {
    "/grpc.health.v1.Health/Check",
    "/grpc.health.v1.Health/Watch",
}

# A string: the type stubs make RpcMethodHandler generic, the runtime class isn't subscriptable
Continuation: TypeAlias = "Callable[[grpc.HandlerCallDetails], Awaitable[grpc.RpcMethodHandler[Any, Any] | None]]"


class JWTValidator(Protocol):
    def validate(self, token: str) -> Caller:
        """Verify signature, exp, iss and aud; return the caller from the claims; raise if invalid."""
        ...


class AuthInterceptor(aio.ServerInterceptor):
    """Validates the JWT from metadata and records the verified caller for the handler."""

    def __init__(self, jwt_validator: JWTValidator) -> None:
        self._validator = jwt_validator

    async def intercept_service(
        self, continuation: Continuation, handler_call_details: grpc.HandlerCallDetails,
    ) -> grpc.RpcMethodHandler[Any, Any] | None:
        if handler_call_details.method in SKIP_AUTH_METHODS:
            return await continuation(handler_call_details)

        token = ""
        for key, value in handler_call_details.invocation_metadata or ():
            if key == "authorization" and isinstance(value, str) and value.startswith("Bearer "):
                token = value[len("Bearer "):]

        if not token:
            return await _abort_handler(continuation, handler_call_details, "missing authorization")

        try:
            caller = self._validator.validate(token)
        except Exception:
            return await _abort_handler(continuation, handler_call_details, "invalid token")

        # HandlerCallDetails is read-only, and metadata is client input anyway. The handler runs in
        # this task, so it reads the verified caller from the ContextVar (app.grpc.context).
        set_caller(caller)
        return await continuation(handler_call_details)


class LoggingInterceptor(aio.ServerInterceptor):
    """Logs every RPC dispatch (the handler runs after this returns; time it in the handler for latency)."""

    async def intercept_service(
        self, continuation: Continuation, handler_call_details: grpc.HandlerCallDetails,
    ) -> grpc.RpcMethodHandler[Any, Any] | None:
        method = handler_call_details.method
        start = time.monotonic()

        handler = await continuation(handler_call_details)

        duration = time.monotonic() - start
        logger.info("grpc.request", extra={
            "method": method,
            "duration_ms": round(duration * 1000, 2),
        })

        return handler


async def _abort_handler(
    continuation: Continuation, handler_call_details: grpc.HandlerCallDetails, message: str,
) -> grpc.RpcMethodHandler[Any, Any] | None:
    """A handler of the same shape as the real one (unary or streaming) that aborts UNAUTHENTICATED."""
    real = await continuation(handler_call_details)
    if real is None:
        return None

    async def abort(request: Any, context: aio.ServicerContext) -> Any:
        await context.abort(grpc.StatusCode.UNAUTHENTICATED, message)

    async def abort_stream(request: Any, context: aio.ServicerContext) -> Any:
        await context.abort(grpc.StatusCode.UNAUTHENTICATED, message)
        yield  # unreachable; makes this an async generator for server-streaming RPCs

    if real.request_streaming and real.response_streaming:
        return grpc.stream_stream_rpc_method_handler(abort_stream)
    if real.request_streaming:
        return grpc.stream_unary_rpc_method_handler(abort)
    if real.response_streaming:
        return grpc.unary_stream_rpc_method_handler(abort_stream)
    return grpc.unary_unary_rpc_method_handler(abort)
```

## Context Helpers

```python
# app/grpc/context.py

from contextvars import ContextVar
from dataclasses import dataclass
from uuid import UUID

from app.errors import UnauthenticatedError


@dataclass(frozen=True, slots=True)
class Caller:
    """The verified caller. AuthInterceptor sets it from the token's claims — never from metadata,
    which a client can send (an x-tenant-id header is client input)."""

    tenant_id: UUID
    user_id: UUID


_caller: ContextVar[Caller | None] = ContextVar("grpc_caller", default=None)


def set_caller(caller: Caller) -> None:
    _caller.set(caller)


def _current() -> Caller:
    caller = _caller.get()
    if caller is None:  # AuthInterceptor not installed, or a method it skips
        raise UnauthenticatedError()
    return caller


def tenant_id_from_context() -> UUID:
    return _current().tenant_id


def user_id_from_context() -> UUID:
    return _current().user_id
```

## Error Mapping

```python
# app/grpc/errors.py

import logging
from typing import NoReturn

import grpc

from app.errors import (
    AppError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthenticatedError,
    ValidationFailedError,
)

logger = logging.getLogger(__name__)

_ERROR_MAP: dict[type[AppError], grpc.StatusCode] = {
    NotFoundError: grpc.StatusCode.NOT_FOUND,
    ConflictError: grpc.StatusCode.ALREADY_EXISTS,
    ValidationFailedError: grpc.StatusCode.INVALID_ARGUMENT,
    ForbiddenError: grpc.StatusCode.PERMISSION_DENIED,
    UnauthenticatedError: grpc.StatusCode.UNAUTHENTICATED,
}


async def abort_with(context: grpc.aio.ServicerContext, exc: Exception) -> NoReturn:
    """End the RPC with the status for a domain error; context.abort() raises, so nothing returns.
    Raising grpc.aio.AbortError yourself sets no status: the client would get UNKNOWN."""
    if isinstance(exc, grpc.aio.AbortError):
        raise exc  # context.abort() already ran
    if isinstance(exc, AppError):
        await context.abort(_ERROR_MAP.get(type(exc), grpc.StatusCode.INTERNAL), exc.message)
    logger.error("grpc.unhandled_error", exc_info=exc)  # the cause stays in the log
    await context.abort(grpc.StatusCode.INTERNAL, "internal error")
```

## Server Startup

```python
# app/grpc/server.py

import asyncio
import logging
import os
import signal

from grpc import aio
from grpc_health.v1 import health_pb2, health_pb2_grpc
from grpc_health.v1.health import aio as health_aio
from grpc_reflection.v1alpha import reflection

from yourapp.v1 import widget_service_pb2_grpc as pb_grpc
from app.grpc.interceptors import AuthInterceptor, JWTValidator, LoggingInterceptor
from app.grpc.widget_server import WidgetEventSource, WidgetServicer
from app.services.widget import WidgetService

logger = logging.getLogger(__name__)


async def serve(
    widget_svc: WidgetService,
    events: WidgetEventSource,
    jwt_validator: JWTValidator,
    port: int = 50051,
) -> None:
    server = aio.server(
        interceptors=[
            LoggingInterceptor(),
            AuthInterceptor(jwt_validator),
        ],
    )

    # Register services
    widget_servicer = WidgetServicer(widget_svc, events)
    pb_grpc.add_WidgetServiceServicer_to_server(widget_servicer, server)

    # Health check (the asyncio servicer: this is an aio server)
    health_servicer = health_aio.HealthServicer()
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)
    await health_servicer.set("yourapp.v1.WidgetService", health_pb2.HealthCheckResponse.SERVING)

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

    def _signal_handler() -> None:
        logger.info("shutdown signal received")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    await stop_event.wait()
    await server.stop(grace=5)
    logger.info("gRPC server stopped")


# Entry point: build the service, event source and JWT validator from your settings, then
# asyncio.run(serve(widget_svc, events, jwt_validator)).
```

## Critical Rules

- Use `grpc.aio` (async) API for production — synchronous `grpc` API blocks the thread
- Use `await context.abort(code, message)` for errors (via `abort_with`) — never raise plain Python exceptions, and never raise `grpc.aio.AbortError` yourself (the client gets `UNKNOWN`)
- Take the tenant from the verified caller the auth interceptor puts in a `ContextVar` — never from `invocation_metadata`, which the client controls (and `HandlerCallDetails` is read-only)
- Register `grpc_health` service on every server (the `health.aio.HealthServicer` on an aio server) — required for load balancer probes
- Enable reflection via `grpc_reflection` only when `ENABLE_REFLECTION` is set
- Use `server.stop(grace=N)` for graceful shutdown — waits N seconds for in-flight RPCs
- Streaming RPCs MUST check `context.cancelled()` in loops — detect client disconnection
- Use `async for` with request iterators in client streaming — native async iteration
- Use `yield` in server streaming servicer methods — grpcio-tools generates async generator stubs
